"""Adding a company by hand, and reporting what is still unreachable.

Two halves of the same problem, which is that ACE cannot poll a board it
does not know about.

The first half is cheap to fix once and impossible to fix in general: a
person spots a posting ACE missed, and should be able to hand it over
without anyone editing a file. ``add_source`` takes a URL or a company
name and does what a human would -- work out which board it is, check
the board really belongs to that employer, and register it.

The second half is why the first keeps being needed. ``coverage`` says
which of the curated companies ACE currently reaches and which it does
not, so the gap is a number on a page rather than something discovered
by accident months later. A Cursor posting was found by hand precisely
because nothing anywhere said "there are companies you cannot see".

Nothing here trusts what it reads. Every path ends at the same
verification the automated probe uses, because a board registered on a
guess fills the queue with another employer's jobs under a name the user
recognises, which is harder to notice than a gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.audit import (
    caught_late,
    feed_only,
)
from backend.app.coverage.benchmark import (
    company_keys,
    normalise_company,
)
from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
    SOURCE_HOSTS,
    TARGET_COMPANIES,
    registration_interval,
)
from backend.app.coverage.diagnosis import (
    BLOCKED,
    OTHER_ATS,
    diagnose,
    foreign_ats_in,
)
from backend.app.coverage.host_policy import (
    PoliteReader,
    read_robots,
    read_targets,
    refusal_for,
    refused_hosts,
)
from backend.app.coverage.leads import (
    DORMANT,
    NOREADER,
    POLLING,
    REFUSED,
    UNDONE,
    forget_added,
    remember_added,
    voice,
)
from backend.app.coverage.probing import (
    BoardCandidate,
    BoardRef,
    board_belongs_to,
    board_jobs,
    careers_page_token,
    find_board,
    find_board_via_careers_page,
    refuses_automation,
    workday_belongs_to,
    _fetch_json,
    _fetch_robots,
    _fetch_text,
    _post_json,
)
from backend.app.coverage.recovery import (
    dark_sources,
)
from backend.app.discovery.feed_links import (
    existing_board,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    SourceProbeRecord,
    SourceState,
)


@dataclass(frozen=True, slots=True)
class AddResult:
    """What happened when a company was handed to ACE."""

    status: str

    company: str = ""

    source_type: str = ""

    source_account: str = ""

    job_count: int = 0

    evidence: str = ""

    detail: str = ""

    # The stored posting a pasted link names, when ACE holds it.
    job: dict | None = None

    # Whether the owner pasted a link, so the answer can speak of their job.
    linked: bool = False

    last_read_at: str | None = None

    next_check_at: str | None = None

    first_read_seconds: int | None = None


def _name_from_url(
    url: str,
) -> str:
    """Guess the employer's name from a careers URL.

    Only used as the name to verify a board against, never as the
    answer. "cursor.com/careers/..." gives "cursor", which is enough
    for the board to be checked against.
    """

    host = urlsplit(
        url
    ).netloc.lower()

    host = host.removeprefix(
        "www."
    )

    # On an ATS-hosted board the employer is the *first* label and the
    # vendor is the last, which is the opposite way round from a
    # company's own domain. Taking the last label turned
    # "visa.wd5.myworkdayjobs.com" into "myworkdayjobs", and every one
    # of Visa's 793 postings was filed under that name.
    #
    # Only the tenant-per-subdomain vendors are listed. Boards that put
    # the employer in the path rather than the host --
    # jobs.lever.co/<employer> -- are read by careers_page_token
    # instead, and never reach this.
    for vendor in (
        "myworkdayjobs.com",
        "icims.com",
        "avature.net",
        "jobvite.com",
        "applytojob.com",
    ):
        if host.endswith(
            vendor
        ):
            label = host.split(
                "."
            )[0]

            return label or host

    parts = [
        part
        for part in host.split(
            "."
        )
        if part
        not in {
            "com",
            "ai",
            "io",
            "co",
            "dev",
            "org",
            "net",
            "app",
        }
    ]

    return parts[-1] if parts else host


def _verify(
    ref: BoardRef,
    company: str,
    *,
    fetch,
    fetch_text,
    post,
    default_evidence: str = "",
) -> BoardCandidate | None:
    """Turn a board a page pointed at into one ACE will poll.

    Every route into this module ends here, because every route has
    the same way of going wrong: the link is real, the board is real,
    and the board is somebody else's.
    """

    jobs = board_jobs(
        ref,
        fetch=fetch,
        post=post,
    )

    if not jobs:
        return None

    if ref.source_type == "workday":
        evidence = workday_belongs_to(
            company=company,
            token=ref.token,
        )
    else:
        evidence = board_belongs_to(
            company=company,
            source_type=ref.source_type,
            token=ref.token,
            jobs=jobs,
            fetch=fetch,
            fetch_text=fetch_text,
        )

    if evidence is None and not default_evidence:
        return None

    return BoardCandidate(
        company=company,
        source_type=ref.source_type,
        source_account=ref.token,
        job_count=len(
            jobs
        ),
        evidence=(
            evidence
            or default_evidence
        ),
        source_host=ref.source_host,
    )


def _from_board_url(
    url: str,
    *,
    fetch,
    fetch_text,
    post=_post_json,
) -> BoardCandidate | None:
    """Read a board straight out of a URL that already names one.

    A link to jobs.ashbyhq.com/cursor/<id> says which board it is
    without any guessing. The board is still verified, because the URL
    says which board and not whose.
    """

    ref = careers_page_token(
        url
    )

    if ref is None:
        return None

    return _verify(
        ref,
        _name_from_url(
            url
        ),
        fetch=fetch,
        fetch_text=fetch_text,
        post=post,
        # The user handed over this exact board. Confirming whose it
        # is stays worth doing and is reported when it succeeds, but a
        # board that names nobody is still the one that was asked for.
        default_evidence=(
            "named directly by the link given"
        ),
    )


def resolve(
    text: str,
    *,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
    post=_post_json,
) -> BoardCandidate | None:
    """Find the board a URL or company name refers to.

    Ordered cheapest first: a link that already names a board needs no
    guessing, a link to a careers page is read, and a bare name is
    guessed at and then read.
    """

    text = text.strip()

    if not text:
        return None

    if text.startswith(
        "http"
    ):
        direct = _from_board_url(
            text,
            fetch=fetch,
            fetch_text=fetch_text,
            post=post,
        )

        if direct is not None:
            return direct

        html = fetch_text(
            text
        )

        if html:
            ref = careers_page_token(
                html
            )

            if ref is not None:
                # No default evidence here. The link was to a careers
                # page, not to a board, so which board it points at is
                # the page's claim and has to be checked.
                found = _verify(
                    ref,
                    _name_from_url(
                        text
                    ),
                    fetch=fetch,
                    fetch_text=fetch_text,
                    post=post,
                )

                if found is not None:
                    return found

        return None

    direct = find_board(
        text,
        fetch=fetch,
        fetch_text=fetch_text,
    )

    if direct is not None:
        return direct

    return find_board_via_careers_page(
        text,
        fetch=fetch,
        fetch_text=fetch_text,
        post=post,
    )


def _link_tail(
    url: str,
) -> str:
    """The part of a posting's address that names the posting.

    Boards serve one posting under several hosts and locales, and an apply
    page sits under the posting's own address.
    """

    parts = [
        part
        for part in urlsplit(
            url
        ).path.lower().split(
            "/"
        )
        if part
    ]

    if parts and parts[-1] in ("apply", "application"):
        parts = parts[:-1]

    return parts[-1] if parts else ""


def job_from_link(
    session: Session,
    link: str,
    source_type: str,
    source_account: str,
) -> dict | None:
    """The stored posting a pasted link names, on the board it belongs to."""

    tail = _link_tail(
        link
    )

    if not tail:
        return None

    for job_id, title, location, url, active, status in session.execute(
        sa.select(
            JobRecord.id,
            JobRecord.title,
            JobRecord.location,
            JobRecord.official_url,
            JobRecord.is_active,
            JobEvaluationRecord.eligibility_status,
        )
        .outerjoin(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        )
        .where(
            JobRecord.source == source_type,
            JobRecord.source_account == source_account,
        )
    ):
        if _link_tail(url or "") == tail:
            return {
                "id": job_id,
                "title": title,
                "location": location,
                "active": bool(active),
                "passes": status == "PASS",
            }

    return None


def _display_name(
    text: str,
) -> str:
    if not text.startswith(
        "http"
    ):
        return text

    return _name_from_url(
        text
    ).replace(
        "-",
        " ",
    ).title()


def _saved(
    session: Session,
    *,
    status: str,
    company: str,
    state: str,
    detail: str,
    now: datetime,
    candidate: BoardCandidate | None = None,
) -> AddResult:
    """Keep what the owner handed over, and say what is in the way."""

    row = remember_added(
        session,
        company=company,
        state=state,
        reason=detail,
        now=now,
        board=(
            {
                "source_type": candidate.source_type,
                "source_account": candidate.source_account,
                "source_host": candidate.source_host,
            }
            if candidate is not None
            else None
        ),
    )

    session.commit()

    return AddResult(
        status=status,
        company=company,
        source_type=candidate.source_type if candidate is not None else "",
        source_account=candidate.source_account if candidate is not None else "",
        job_count=candidate.job_count if candidate is not None else 0,
        detail=voice(detail),
        next_check_at=(
            row.next_check_at.isoformat()
            if row is not None
            else None
        ),
    )


def _saved_without_a_board(
    session: Session,
    *,
    text: str,
    reader: PoliteReader,
    now: datetime,
) -> AddResult:
    """A link that named no readable board: say what is in the way."""

    company = _display_name(
        text
    )

    if not reader.allows(
        text
    ) or reader.refuses(
        text
    ):
        return _saved(
            session,
            status="saved_refused",
            company=company,
            state=REFUSED,
            detail=(
                "Its rules ask automated readers to stay off "
                "this page. ace respects that and will not try "
                "another way. Check it by hand."
            ),
            now=now,
        )

    foreign = foreign_ats_in(
        text
    ) or foreign_ats_in(
        reader.fetch_text(
            text
        )
    )

    if foreign:
        return _saved(
            session,
            status="saved_no_reader",
            company=company,
            state=NOREADER,
            detail=(
                f"It hires through {foreign}, and ace has no "
                "reader for that site yet."
            ),
            now=now,
        )

    return _saved(
        session,
        status="saved_looking",
        company=company,
        state=DORMANT,
        detail=(
            "ace found no job board there yet. It may build "
            "itself in the browser."
        ),
        now=now,
    )


def add_source(
    session: Session,
    *,
    text: str,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
    post=_post_json,
    robots=_fetch_robots,
    refuses=refuses_automation,
    fetch_robots=read_robots,
    now: datetime | None = None,
) -> AddResult:
    """Do what the owner asked, and always say what happened.

    A board that belongs to the company starts polling at once, because the
    owner asked for it. Anything else is kept as a lead, so a name handed over
    is never forgotten, and the answer says what is in the way. Every read
    here asks robots first: pasting a link is no way around a refusal.
    """

    text = text.strip()

    moment = now or datetime.now(
        timezone.utc
    )

    reader = PoliteReader(
        refused_hosts(
            session
        ),
        fetch=fetch,
        fetch_text=fetch_text,
        post=post,
        robots=robots,
        refuses=refuses,
    )

    is_link = text.startswith(
        "http"
    )

    if is_link:
        candidate = resolve(
            text,
            fetch=reader.fetch,
            fetch_text=reader.fetch_text,
            post=reader.post,
        )

        if candidate is None:
            return _saved_without_a_board(
                session,
                text=text,
                reader=reader,
                now=moment,
            )
    else:
        diagnosis = diagnose(
            text,
            fetch=reader.fetch,
            fetch_text=reader.fetch_text,
            post=reader.post,
            refuses=reader.refuses,
        )

        candidate = diagnosis.candidate

        if candidate is None:
            status, state = {
                OTHER_ATS: ("saved_no_reader", NOREADER),
                BLOCKED: ("saved_refused", REFUSED),
            }.get(
                diagnosis.outcome,
                ("saved_looking", DORMANT),
            )

            return _saved(
                session,
                status=status,
                company=text,
                state=state,
                detail=diagnosis.detail,
                now=moment,
            )

    existing = existing_board(
        session,
        candidate.source_type,
        candidate.source_account,
    )

    if existing is not None and existing.enabled:
        return AddResult(
            status="already_known",
            company=existing.company_name,
            source_type=existing.source_type,
            source_account=existing.source_account,
            job_count=candidate.job_count,
            evidence=voice(
                candidate.evidence
            ),
            job=(
                job_from_link(
                    session,
                    text,
                    existing.source_type,
                    existing.source_account,
                )
                if is_link
                else None
            ),
            linked=is_link,
            last_read_at=_last_read(
                session,
                existing,
            ),
        )

    # A board switched off earlier stays a decision somebody made. An agency,
    # or a duplicate, is not turned back on by pasting a link.
    if existing is not None:
        return AddResult(
            status="known_off",
            company=existing.company_name,
            source_type=existing.source_type,
            source_account=existing.source_account,
            job_count=candidate.job_count,
            detail=_switched_off_reason(
                existing
            ),
        )

    for target in read_targets(
        candidate.source_type,
        candidate.source_account,
        candidate.source_host
        or SOURCE_HOSTS.get(
            candidate.source_type
        ),
    ):
        why = refusal_for(
            session,
            target,
            now=moment,
            fetch_robots=fetch_robots,
        )

        if why:
            return _saved(
                session,
                status="saved_refused",
                company=candidate.company,
                state=REFUSED,
                detail=why,
                now=moment,
                candidate=candidate,
            )

    source_host = (
        candidate.source_host
        or SOURCE_HOSTS.get(
            candidate.source_type
        )
    )

    session.add(
        JobSourceRecord(
            source_type=(
                candidate.source_type
            ),
            source_account=(
                candidate.source_account
            ),
            company_name=(
                candidate.company
            ),
            source_host=source_host,
            enabled=True,
            poll_interval_seconds=(
                registration_interval(
                    candidate.source_type
                )
            ),
            discovery_source="added_by_hand",
        )
    )

    remember_added(
        session,
        company=candidate.company,
        state=POLLING,
        reason="Added by you. ace reads it next.",
        now=moment,
        board={
            "source_type": candidate.source_type,
            "source_account": candidate.source_account,
            "source_host": source_host,
        },
    )

    session.commit()

    return AddResult(
        status="added",
        company=candidate.company,
        source_type=candidate.source_type,
        source_account=(
            candidate.source_account
        ),
        job_count=candidate.job_count,
        evidence=voice(
            candidate.evidence
        ),
        linked=is_link,
        first_read_seconds=registration_interval(
            candidate.source_type
        ),
    )


def _last_read(
    session: Session,
    source: JobSourceRecord,
) -> str | None:
    state = session.get(
        SourceState,
        (
            source.source_type,
            source.source_account,
        ),
    )

    return (
        state.last_success_at.isoformat()
        if state is not None and state.last_success_at
        else None
    )


def _switched_off_reason(
    source: JobSourceRecord,
) -> str:
    kind = (
        source.discovery_source or ""
    ).lower()

    if "staffing" in kind:
        return (
            "ace knows this board and left it out, because it "
            "looks like a staffing agency, not an employer."
        )

    if kind == UNDONE:
        return (
            "You took this board back earlier, so ace left it "
            "off. Ask me to turn it back on if that changed."
        )

    return (
        "ace knows this board and has it switched off."
    )


def undo_added(
    session: Session,
    *,
    source_type: str,
    source_account: str,
    now: datetime | None = None,
) -> bool:
    """Take back a board the owner just added.

    Only one they added by hand. The board stays on record, switched off, so it
    is never proposed again, and postings it brought in are closed. Marks and
    applications on them are untouched.
    """

    row = session.scalar(
        sa.select(
            JobSourceRecord
        ).where(
            JobSourceRecord.source_type == source_type,
            JobSourceRecord.source_account == source_account,
        )
    )

    if (
        row is None
        or not row.enabled
        or row.discovery_source != "added_by_hand"
    ):
        return False

    moment = now or datetime.now(
        timezone.utc
    )

    row.enabled = False

    row.discovery_source = UNDONE

    session.execute(
        sa.update(
            JobRecord
        )
        .where(
            JobRecord.source == source_type,
            JobRecord.source_account == source_account,
            JobRecord.is_active.is_(True),
        )
        .values(
            is_active=False,
            closed_at=moment,
        )
    )

    forget_added(
        session,
        company=row.company_name,
    )

    session.commit()

    return True


# An employer that will not sponsor is not a gap in what ACE can see;
# it is a gap in what the user can apply to, and until now it was
# invisible. The rule is per posting, so the same refusal was
# re-derived on every job of every poll and never once stated: 793
# Visa postings rejected one at a time, with nothing anywhere saying
# "Visa does not sponsor".
#
# Below this many readable postings the ratio is noise -- one refusal
# out of one posting says nothing about an employer.
MIN_POSTINGS_TO_JUDGE = 5


def sponsorship_refusals(
    session: Session,
) -> list[dict]:
    """Employers whose own postings say they will not sponsor.

    Counted only over postings whose requirement text ACE could
    actually read. A description it never saw cannot have stated
    anything, and including those would quietly deflate every ratio
    toward "mostly fine".
    """

    # PostgreSQL asks the stored list whether it holds the code. Turning
    # every reason list into text to search it took 797 ms over the
    # 659,000 readable active postings; containment took 558 ms and found
    # the same 189 employers. SQLite, which runs the tests and the demo,
    # keeps the text search.
    if session.get_bind().dialect.name == "postgresql":
        refuses = JobEvaluationRecord.reason_codes.contains(
            [
                "SPONSORSHIP_BLOCKER"
            ]
        )
    else:
        refuses = JobEvaluationRecord.reason_codes.cast(
            sa.Text
        ).like(
            "%SPONSORSHIP_BLOCKER%"
        )

    rows = session.execute(
        sa.select(
            # Grouped case-insensitively. Boards write the same
            # employer both ways -- "Esri" and "esri" both appear --
            # and split rows halve each ratio and read as two
            # companies.
            sa.func.min(
                JobRecord.company
            ).label(
                "company"
            ),
            sa.func.count().label(
                "readable"
            ),
            sa.func.count()
            .filter(
                refuses
            )
            .label(
                "refusing"
            ),
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .where(
            JobRecord.is_active.is_(
                True
            ),
            JobEvaluationRecord.requirements_verified.is_(
                True
            ),
        )
        .group_by(
            sa.func.lower(
                JobRecord.company
            )
        )
    ).all()

    refusals = [
        {
            "company": row.company,
            "readable": row.readable,
            "refusing": row.refusing,
            "share": round(
                row.refusing
                / row.readable,
                3,
            ),
        }
        for row in rows
        if row.refusing
        and row.readable
        >= MIN_POSTINGS_TO_JUDGE
    ]

    refusals.sort(
        key=lambda entry: (
            -entry["share"],
            -entry["refusing"],
            entry["company"],
        )
    )

    return refusals


def coverage(
    session: Session,
    *,
    sponsorship: list[dict] | None = None,
) -> dict:
    """Report which curated companies ACE can and cannot reach.

    Reachable means ACE polls a board for them or holds an active
    posting from them **taken directly** -- not one that arrived
    through a multi-employer feed. Anything else is a company on the
    list that ACE is currently blind to, which is the number worth
    watching.

    This is the same distinction reachable_keys() in probe_coverage.py
    makes, and it has to be made twice: this function renders the
    Coverage page a person reads, that one decides which companies get
    probed, and they drifted. Qualcomm was still shown as reached here
    after the probing fix already went in, because eight of its
    postings arrive through the curated feed and this function had
    never stopped counting that as reach. Its own board -- Eightfold,
    blocked at the API a probe confirmed -- was invisible on the one
    page that exists to show a gap like that.
    """

    reachable: set[str] = set()

    for name in session.scalars(
        sa.select(
            JobSourceRecord.company_name
        )
    ):
        reachable |= set(
            company_keys(
                name
            )
        )

    for name in session.scalars(
        sa.select(
            JobRecord.company
        )
        .where(
            JobRecord.is_active.is_(
                True
            ),
            JobRecord.source.not_in(
                MULTI_EMPLOYER_SOURCES
            ),
        )
        .distinct()
    ):
        reachable |= set(
            company_keys(
                name
            )
        )

    # What the last probe found in the way of each company. Without
    # it the gap is a list of names and nothing more: no way to tell a
    # company that has moved to an ATS ACE cannot read from one whose
    # careers page merely outgrew the buffer that read it. Both were
    # in this list, and both were found by hand.
    probes = {
        row.company_key: row
        for row in session.scalars(
            sa.select(
                SourceProbeRecord
            )
        )
    }

    unreached = []

    for name in sorted(
        TARGET_COMPANIES
    ):
        if set(
            company_keys(
                name
            )
        ) & reachable:
            continue

        probe = probes.get(
            normalise_company(
                name
            )
        )

        unreached.append(
            {
                "company": name,
                "outcome": (
                    probe.outcome
                    if probe
                    else "unprobed"
                ),
                "detail": (
                    probe.detail
                    if probe
                    else (
                        "Not looked at yet."
                    )
                ),
                "checked_at": (
                    probe.checked_at.isoformat()
                    if probe
                    and probe.checked_at
                    else None
                ),
            }
        )

    return {
        "total": len(
            TARGET_COMPANIES
        ),
        "reached": len(
            TARGET_COMPANIES
        )
        - len(
            unreached
        ),
        "unreached": unreached,
        "sources": session.scalar(
            sa.select(
                sa.func.count()
            ).select_from(
                JobSourceRecord
            )
        ),
        # The API passes a recent snapshot: this statistic covers every
        # readable posting and changes slowly. Computed here otherwise.
        "sponsorship": (
            sponsorship
            if sponsorship is not None
            else sponsorship_refusals(
                session
            )
        ),
        # ACE's own account of its misses: roles a feed listed before
        # ACE saw them at the source, and companies it reads only
        # through a feed.
        "caught_late": caught_late(
            session
        ),
        "feed_only": feed_only(
            session
        ),
        # Boards ACE polls that have stopped answering. Kept apart from
        # "unreached" because these are ACE's to fix, not the
        # company's -- and because their old postings still look
        # active, these companies would otherwise count as reached.
        "dark": [
            {
                "company": dark.company_name,
                "source_type": dark.source_type,
                "source_account": dark.source_account,
                "last_success_at": (
                    dark.last_success_at.isoformat()
                    if dark.last_success_at
                    else None
                ),
                "dark_since": (
                    dark.dark_since.isoformat()
                ),
            }
            for dark in dark_sources(
                session
            )
        ],
    }
