"""Tests for one-email-per-pull job alerts.

The failure modes worth guarding are all about volume and timing: an
alert for a pull still arriving, an alert sent twice, or a stopped
scheduler coming back and mailing every quarter hour it missed.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.alerts.service import (
    MAX_AGE,
    MAX_LISTED,
    render_html,
    pending_pulls,
    qualifying_jobs,
    render,
    send_pending,
)
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    PollSessionRecord,
)
from backend.app.persistence.sessions import (
    SESSION_BUCKET,
)


NOW = datetime(
    2026,
    9,
    14,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="configured", autouse=True)
def fixture_configured(
    monkeypatch,
):
    """Give ACE somewhere to send.

    Without an address `send_pending` does nothing at all and leaves
    pulls unnotified, which is deliberate: turning alerts on later
    should deliver the recent backlog rather than silently skip
    everything that happened while they were off. It does mean these
    tests have to configure one.
    """

    monkeypatch.setenv(
        "ALERT_EMAIL",
        "owner@example.com",
    )

    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with factory() as session:
        yield session


def make_pull(
    session,
    *,
    started_at,
    qualifying=1,
    notified_at=None,
):
    pull = PollSessionRecord(
        started_at=started_at,
        last_activity_at=started_at,
        jobs_discovered=qualifying,
        qualifying_discovered=qualifying,
        notified_at=notified_at,
    )

    session.add(
        pull,
    )

    session.flush()

    return pull


def add_job(
    session,
    pull,
    *,
    index,
    company="Example Co",
    status="PASS",
    new_grad=False,
):
    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index,
        ),
        company=company,
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build things.",
        official_url=f"https://employer.example/{index}",
        posted_at=NOW,
        content_hash=f"hash-{index}",
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
        first_seen_session_id=pull.id,
    )

    session.add(
        job,
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status=status,
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{index}",
            requirements_verified=True,
            is_early_career=True,
            is_new_grad=new_grad,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def test_a_pull_still_arriving_is_not_alerted(
    session,
) -> None:
    """Half a pull is not worth an email.

    A bucket is fifteen minutes wide and jobs keep landing in it for
    the whole of that, so alerting the moment the first one appears
    would send an email per job in practice.
    """

    make_pull(
        session,
        started_at=NOW - timedelta(minutes=5),
    )

    assert pending_pulls(
        session,
        now=NOW,
    ) == []


def test_a_closed_pull_is_alerted(
    session,
) -> None:
    make_pull(
        session,
        started_at=NOW - SESSION_BUCKET - timedelta(minutes=1),
    )

    assert len(
        pending_pulls(
            session,
            now=NOW,
        )
    ) == 1


def test_a_pull_that_found_nothing_is_never_alerted(
    session,
) -> None:
    """ACE checks constantly and mostly finds nothing. An email saying
    so would be the majority of the emails."""

    make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
        qualifying=0,
    )

    assert pending_pulls(
        session,
        now=NOW,
    ) == []


def test_an_alerted_pull_is_not_alerted_again(
    session,
) -> None:
    """The scheduler decides what to send every few seconds, so without
    this the newest pull would be emailed on a loop."""

    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=1,
    )

    first = send_pending(
        session,
        now=NOW,
    )

    session.flush()

    second = send_pending(
        session,
        now=NOW,
    )

    # Consumed exactly once. Nothing is actually delivered, because no
    # API key is configured and the sender logs instead, but the pull
    # must not be reconsidered on the next cycle either way.
    assert pending_pulls(
        session,
        now=NOW,
    ) == []

    assert second == 0

    assert pull.notified_at is not None


def test_a_stopped_scheduler_does_not_mail_its_backlog(
    session,
) -> None:
    """Coming back after a week must not send a week of quarter hours.

    The jobs are in the queue regardless; an alert is a nudge, and a
    nudge about last Tuesday is noise.
    """

    stale = make_pull(
        session,
        started_at=NOW - MAX_AGE - timedelta(hours=1),
    )

    add_job(
        session,
        stale,
        index=1,
    )

    send_pending(
        session,
        now=NOW,
    )

    session.flush()

    assert stale.notified_at is not None

    assert pending_pulls(
        session,
        now=NOW,
    ) == []


def test_only_gate_passing_jobs_are_listed(
    session,
) -> None:
    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=1,
        company="Kept",
    )

    add_job(
        session,
        pull,
        index=2,
        company="Rejected Co",
        status="REJECT",
    )

    listed = qualifying_jobs(
        session,
        pull,
    )

    assert [
        job.company
        for job, _, _ in listed
    ] == [
        "Kept",
    ]


def test_new_grad_roles_lead_the_email(
    session,
) -> None:
    """The same order the queue leads with."""

    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=1,
        company="Zeta",
    )

    add_job(
        session,
        pull,
        index=2,
        company="Alpha",
        new_grad=True,
    )

    listed = qualifying_jobs(
        session,
        pull,
    )

    assert listed[0][0].company == "Alpha"


def test_the_email_links_to_the_employer_not_to_ace(
    session,
) -> None:
    """The standing invariant, and the point of the email: tapping it
    on a phone has to land on the application form."""

    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=7,
    )

    _, body = render(
        pull,
        qualifying_jobs(
            session,
            pull,
        ),
    )

    assert "https://employer.example/7" in body


def test_a_huge_pull_is_summarised_rather_than_listed(
    session,
) -> None:
    """Two real days produced 140 and 185 qualifying jobs. An email
    running to several phone screens does not get read."""

    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
        qualifying=MAX_LISTED + 10,
    )

    for index in range(
        MAX_LISTED + 10,
    ):
        add_job(
            session,
            pull,
            index=index,
            company=f"Company {index:03d}",
        )

    subject, body = render(
        pull,
        qualifying_jobs(
            session,
            pull,
        ),
    )

    assert str(
        MAX_LISTED + 10,
    ) in subject

    assert "and 10 more" in body

    assert body.count(
        "https://employer.example/",
    ) == MAX_LISTED


def test_the_subject_says_how_many(
    session,
) -> None:
    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=1,
    )

    subject, _ = render(
        pull,
        qualifying_jobs(
            session,
            pull,
        ),
    )

    assert subject == "ACE: 1 new opportunity"


# --- the HTML part -------------------------------------------------


def _one_job_html(
    session,
    **kwargs,
) -> str:
    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        pull,
        index=7,
        **kwargs,
    )

    return render_html(
        pull,
        qualifying_jobs(
            session,
            pull,
        ),
    )


def test_the_html_declares_a_viewport(
    session,
) -> None:
    """Without it a phone lays the mail out at ~980px and zooms out.

    The alert exists so a role can be applied to from a phone, so an
    email that is unreadable on one has failed at its only job. Caught
    by rendering it at 390px and finding a 980px layout.
    """

    body = _one_job_html(
        session,
    )

    assert 'name="viewport"' in body
    assert "width=device-width" in body


def test_the_html_links_to_the_employer(
    session,
) -> None:
    """The standing invariant, and the point of the email."""

    body = _one_job_html(
        session,
    )

    assert "https://employer.example/7" in body


def test_an_unscored_job_never_renders_as_zero(
    session,
) -> None:
    """Unscored means the posting was never readable, which is not a
    bad match. Printing a 0 would be a lie about what ACE knows."""

    body = _one_job_html(
        session,
    )

    assert "Not scored" in body
    assert "MINIMAL 0" not in body


def test_employer_text_is_escaped(
    session,
) -> None:
    """Titles arrive from employers and go straight into markup.

    A stray ampersand is the common case and would break the layout
    rather than anything worse, but the rule is the same either way.
    """

    body = _one_job_html(
        session,
        company="Tom & Jerry <script>",
    )

    assert "Tom &amp; Jerry &lt;script&gt;" in body
    assert "<script>" not in body


def test_the_html_and_text_agree_on_the_count(
    session,
) -> None:
    """Both parts are sent, and a client may show either."""

    pull = make_pull(
        session,
        started_at=NOW - timedelta(hours=1),
        qualifying=2,
    )

    add_job(
        session,
        pull,
        index=1,
    )

    add_job(
        session,
        pull,
        index=2,
    )

    jobs = qualifying_jobs(
        session,
        pull,
    )

    subject, text = render(
        pull,
        jobs,
    )

    html = render_html(
        pull,
        jobs,
    )

    assert "2 new opportunities" in subject
    assert "2 new roles" in text
    assert "2 new opportunities" in html
