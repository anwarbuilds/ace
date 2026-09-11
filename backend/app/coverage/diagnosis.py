"""Why ACE cannot reach a company, in words a person can act on.

Coverage could say that 154 companies were out of reach and could not
say why any of them were. That difference matters more than it sounds.
A list of names is a wall: nothing on it suggests what to do, and
nothing distinguishes the company that has moved to an ATS ACE cannot
read from the company whose careers page merely grew past the buffer
that read it.

Both of those were in that list. So were a dozen companies sitting on
Workday and SmartRecruiters, which ACE has been able to read for
months and had simply never thought to look for. Every one of them was
found by hand, one at a time, by reading pages and comparing them to
what the code did. This module exists so that the next round of it is
a query.

The outcomes are deliberately few. Free text cannot be grouped and an
enumeration would need a migration every time a new ATS appears, so
what is stored is a coarse outcome plus a sentence.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from backend.app.coverage.probing import (
    MAX_PAGES_PER_COMPANY,
    BoardCandidate,
    _fetch_json,
    _fetch_text,
    _pages_to_read,
    _post_json,
    board_belongs_to,
    board_jobs,
    candidate_for_token,
    careers_page_token,
    domain_candidates,
    find_board,
    linked_board_belongs_to,
    page_claims_another_company,
    looks_like_a_parked_domain,
    page_names_company,
    workday_belongs_to,
)


# ACE reads a board or it does not. These are the ones it does not,
# and naming them is the point: "Rivian is on iCIMS" is a decision
# waiting to be made, where "Rivian is unreachable" is a shrug.
#
# Each is a real employer's real destination, found by reading the
# careers pages of companies the coverage report had written off.
FOREIGN_ATS = (
    (
        "iCIMS",
        r"[a-z0-9.-]+\.icims\.com",
    ),
    (
        "Phenom",
        r"phenompeople\.com|\.phenom\.com",
    ),
    (
        "SAP SuccessFactors",
        r"[a-z0-9-]+\.(?:successfactors|sapsf)"
        r"\.(?:com|eu)",
    ),
    (
        "Oracle Recruiting",
        r"[a-z0-9-]+\.oraclecloud\.com",
    ),
    (
        "Taleo",
        r"[a-z0-9-]+\.taleo\.net",
    ),
    (
        "Rippling",
        r"ats\.rippling\.com/[A-Za-z0-9_-]+",
    ),
    (
        "BambooHR",
        r"[a-z0-9-]+\.bamboohr\.com",
    ),
    (
        "Workable",
        r"apply\.workable\.com/[A-Za-z0-9_-]+",
    ),
    (
        "Jobvite",
        r"jobs\.jobvite\.com/[A-Za-z0-9_-]+",
    ),
    (
        "Paylocity",
        r"recruiting\.paylocity\.com/",
    ),
    (
        "Teamtailor",
        r"[a-z0-9-]+\.teamtailor\.com",
    ),
)


REACHED = "reached"

OTHER_ATS = "other_ats"

NO_POSTINGS = "no_postings"

REFUSED = "refused"

NO_BOARD_FOUND = "no_board_found"

SITE_UNREACHABLE = "site_unreachable"


@dataclass(
    frozen=True,
    slots=True,
)
class Diagnosis:
    """What stood between ACE and one company's jobs."""

    company: str

    outcome: str

    detail: str

    candidate: BoardCandidate | None = None


def foreign_ats_in(
    html: str,
) -> str | None:
    """Return the name of an ATS ACE cannot read, if the page uses one."""

    for name, pattern in FOREIGN_ATS:
        if re.search(
            pattern,
            html,
            re.IGNORECASE,
        ):
            return name

    return None


def diagnose(
    company: str,
    *,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
    post=_post_json,
) -> Diagnosis:
    """Find this company's board, or say what stopped it.

    Walks the same route as discovery and keeps what it learns on the
    way, rather than collapsing every failure into None. The order of
    the outcomes is the order of usefulness: a board is best, a named
    ATS is a decision, and "nothing found" is the only one that leaves
    a person with nowhere to start.
    """

    direct = find_board(
        company,
        fetch=fetch,
        fetch_text=fetch_text,
    )

    if direct is not None:
        return Diagnosis(
            company=company,
            outcome=REACHED,
            detail=direct.evidence,
            candidate=direct,
        )

    # Everything learned while walking the site, kept so that a
    # failure can say which kind of failure it was.
    saw_site = False

    saw_empty_board = ""

    saw_unverified = ""

    saw_foreign = ""

    budget = MAX_PAGES_PER_COMPANY

    for host in domain_candidates(
        company
    ):
        if budget <= 0:
            break

        root = f"https://{host}"

        budget -= 1

        landing = fetch_text(
            root
        )

        if landing and (
            page_claims_another_company(
                company,
                landing,
            )
            or looks_like_a_parked_domain(
                landing
            )
        ):
            continue

        if landing:
            saw_site = True

        # Whether this site positively said it is this company, as
        # opposed to merely not saying it is somebody else.
        identified = bool(
            landing
        ) and page_names_company(
            company,
            landing,
        )

        for url in _pages_to_read(
            root,
            host,
            landing,
        ):
            if url != root:
                if budget <= 0:
                    break

                budget -= 1

            html = (
                landing
                if url == root
                else fetch_text(
                    url
                )
            )

            if not html:
                continue

            if page_claims_another_company(
                company,
                html,
            ):
                continue

            saw_site = True

            identified = (
                identified
                or page_names_company(
                    company,
                    html,
                )
            )

            ref = careers_page_token(
                html
            )

            if ref is None:
                if not saw_foreign:
                    saw_foreign = (
                        foreign_ats_in(
                            html
                        )
                        or ""
                    )

                continue

            jobs = board_jobs(
                ref,
                fetch=fetch,
                post=post,
            )

            if not jobs:
                saw_empty_board = (
                    f"{ref.source_type}"
                    f"/{ref.token}"
                )

                continue

            if ref.source_type == "workday":
                evidence = workday_belongs_to(
                    company=company,
                    token=ref.token,
                )
            else:
                evidence = board_belongs_to(
                    company=company,
                    source_type=(
                        ref.source_type
                    ),
                    token=ref.token,
                    jobs=jobs,
                    fetch=fetch,
                    fetch_text=fetch_text,
                ) or linked_board_belongs_to(
                    company=company,
                    source_type=(
                        ref.source_type
                    ),
                    token=ref.token,
                    fetch=fetch,
                    fetch_text=fetch_text,
                )

            if evidence is None:
                saw_unverified = (
                    f"{ref.source_type}"
                    f"/{ref.token}"
                )

                continue

            return Diagnosis(
                company=company,
                outcome=REACHED,
                detail=(
                    evidence
                    + ", found on "
                    + url
                ),
                candidate=BoardCandidate(
                    company=company,
                    source_type=(
                        ref.source_type
                    ),
                    source_account=ref.token,
                    job_count=len(
                        jobs
                    ),
                    evidence=(
                        evidence
                        + ", found on "
                        + url
                    ),
                    source_host=(
                        ref.source_host
                    ),
                ),
            )

        if landing:
            by_domain = candidate_for_token(
                company,
                host,
                fetch=fetch,
                fetch_text=fetch_text,
            )

            if by_domain is not None:
                return Diagnosis(
                    company=company,
                    outcome=REACHED,
                    detail=by_domain.evidence,
                    candidate=by_domain,
                )

        if identified:
            # Their own site has been read. Further guesses are other
            # spellings of the same name, and at this point a match is
            # more likely to be a lookalike than a second site.
            break

    if saw_foreign:
        return Diagnosis(
            company=company,
            outcome=OTHER_ATS,
            detail=(
                f"Hires through {saw_foreign}, "
                "which ACE has no adapter for "
                "yet."
            ),
        )

    if saw_unverified:
        return Diagnosis(
            company=company,
            outcome=REFUSED,
            detail=(
                "Their careers page links "
                f"{saw_unverified}, which names "
                "a different company. Not "
                "subscribed: a board under the "
                "wrong name is harder to notice "
                "than a gap."
            ),
        )

    if saw_empty_board:
        return Diagnosis(
            company=company,
            outcome=NO_POSTINGS,
            detail=(
                f"Board {saw_empty_board} is "
                "readable and currently has no "
                "public postings."
            ),
        )

    if saw_site:
        return Diagnosis(
            company=company,
            outcome=NO_BOARD_FOUND,
            detail=(
                "Their site was read and points "
                "at no job board ACE recognises. "
                "Usually a careers page that "
                "builds itself in the browser, "
                "or a board hosted in-house."
            ),
        )

    return Diagnosis(
        company=company,
        outcome=SITE_UNREACHABLE,
        detail=(
            "No website answered for this name. "
            "The company may trade under another "
            "one, or publish on a domain nothing "
            "in the name suggests."
        ),
    )
