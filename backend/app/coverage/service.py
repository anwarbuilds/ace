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
from urllib.parse import urlsplit

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import (
    company_keys,
    normalise_company,
)
from backend.app.coverage.companies import (
    CURATED_POLL_INTERVAL_SECONDS,
    MULTI_EMPLOYER_SOURCES,
    TARGET_COMPANIES,
)
from backend.app.coverage.probing import (
    BoardCandidate,
    BoardRef,
    board_belongs_to,
    board_jobs,
    careers_page_token,
    find_board,
    find_board_via_careers_page,
    workday_belongs_to,
    _fetch_json,
    _fetch_text,
    _post_json,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    SourceProbeRecord,
)


SOURCE_HOSTS = {
    "greenhouse": "job-boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "smartrecruiters": "jobs.smartrecruiters.com",
}


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


def add_source(
    session: Session,
    *,
    text: str,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
    post=_post_json,
) -> AddResult:
    """Register the board a URL or name refers to."""

    candidate = resolve(
        text,
        fetch=fetch,
        fetch_text=fetch_text,
        post=post,
    )

    if candidate is None:
        return AddResult(
            status="not_found",
            detail=(
                "No board ACE can read was found "
                "there. It may be self-hosted, on "
                "Workday, or behind a page that "
                "builds itself in the browser."
            ),
        )

    existing = session.scalar(
        sa.select(
            JobSourceRecord
        ).where(
            JobSourceRecord.source_type
            == candidate.source_type,
            JobSourceRecord.source_account
            == candidate.source_account,
        )
    )

    if existing is not None:
        return AddResult(
            status="already_known",
            company=existing.company_name,
            source_type=candidate.source_type,
            source_account=(
                candidate.source_account
            ),
            job_count=candidate.job_count,
            evidence=candidate.evidence,
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
            source_host=(
                candidate.source_host
                or SOURCE_HOSTS.get(
                    candidate.source_type
                )
            ),
            enabled=True,
            poll_interval_seconds=(
                CURATED_POLL_INTERVAL_SECONDS
            ),
            discovery_source="added_by_hand",
        )
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
        evidence=candidate.evidence,
    )


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
                JobEvaluationRecord.reason_codes.cast(
                    sa.Text
                ).like(
                    "%SPONSORSHIP_BLOCKER%"
                )
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
        "sponsorship": sponsorship_refusals(
            session
        ),
    }
