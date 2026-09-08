"""Finding a company's job board when nobody has told you the token.

Greenhouse, Lever and Ashby each publish a clean public API per board
and none of them publishes a list of boards. That single fact is what
caps ACE's coverage at 20%: it can read any board, and only knows 129
of them.

The token is usually the company name with the punctuation removed, so
guessing works often enough to be worth doing. It also fails in the
two ways that matter, and both are handled here rather than trusted.

**A guess can hit the wrong company.** "Applied Materials" reduces to
"applied", which is a live Ashby board belonging to Applied Intuition.
Subscribing to it would fill the queue with another employer's jobs
under a name the user recognises, which is worse than missing them.
Every candidate is therefore verified against the board's own content
before it is offered.

**A company's token can be nothing like its name.** Current's board is
"current81", and "current" is a different employer's live board. No
amount of guessing finds that, so the careers page is read for the
token it embeds.

Nothing here writes to the database. Discovery proposes; a human
confirms.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import urllib.error
import urllib.request

from backend.app.coverage.benchmark import normalise_company


USER_AGENT = "ACE-source-discovery/1.0"

TIMEOUT_SECONDS = 8.0


# Enough of the board to tell whose it is without pulling every job.
VERIFY_SAMPLE = 25


@dataclass(
    frozen=True,
    slots=True,
)
class BoardCandidate:
    """A board that might belong to a company."""

    company: str

    source_type: str

    source_account: str

    job_count: int

    # Why this is believed to be the right company's board. Recorded so
    # a human confirming it can see the reasoning rather than a score.
    evidence: str


def token_guesses(
    company: str,
) -> list[str]:
    """Return board tokens worth trying for a company name.

    Ordered most to least likely, and deliberately short. Every extra
    guess is another request against someone else's API and another
    chance to match an unrelated board.
    """

    key = normalise_company(
        company
    )

    if not key:
        return []

    words = key.split()

    joined = "".join(
        words
    )

    guesses = [
        joined,
        "-".join(
            words
        ),
    ]

    # "Ramp" from "Ramp Financial". Only when the first word is
    # substantial: "the" or "ai" alone matches anything.
    if len(words) > 1 and len(words[0]) >= 4:
        guesses.append(
            words[0]
        )

    seen: set[str] = set()

    return [
        guess
        for guess in guesses
        if len(guess) >= 3
        and not (
            guess in seen
            or seen.add(
                guess
            )
        )
    ]


def _fetch_json(
    url: str,
    *,
    opener=urllib.request.urlopen,
):
    """Return decoded JSON, or None when the board does not answer."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with opener(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            if response.status != 200:
                return None

            return json.loads(
                response.read().decode(
                    "utf-8",
                    "replace",
                )
            )
    except Exception:
        return None


def board_endpoints(
    token: str,
) -> list[tuple[str, str]]:
    """Return (source_type, url) for each ATS worth trying."""

    return [
        (
            "greenhouse",
            "https://boards-api.greenhouse.io"
            f"/v1/boards/{token}/jobs",
        ),
        (
            "ashby",
            "https://api.ashbyhq.com"
            f"/posting-api/job-board/{token}",
        ),
        (
            "lever",
            "https://api.lever.co"
            f"/v0/postings/{token}?mode=json",
        ),
    ]


def _jobs_from(
    payload,
) -> list[dict]:
    """Normalise the three response shapes into a list of jobs."""

    if isinstance(
        payload,
        list,
    ):
        return [
            item
            for item in payload
            if isinstance(
                item,
                dict,
            )
        ]

    if isinstance(
        payload,
        dict,
    ):
        jobs = payload.get(
            "jobs"
        )

        if isinstance(
            jobs,
            list,
        ):
            return [
                item
                for item in jobs
                if isinstance(
                    item,
                    dict,
                )
            ]

    return []


def board_metadata_name(
    *,
    source_type: str,
    token: str,
    fetch=_fetch_json,
) -> str | None:
    """Return the name the board declares for itself.

    This is the only non-circular evidence available. A Greenhouse job's
    ``absolute_url`` is ``boards.greenhouse.io/<token>/...``, so
    checking it for a token derived from the company name proves
    nothing except that the guess was consistent with itself. The board
    metadata is written by the employer.

    Only Greenhouse publishes it. Ashby and Lever are verified from
    posting text instead, which is weaker and is labelled as such.
    """

    if source_type != "greenhouse":
        return None

    payload = fetch(
        "https://boards-api.greenhouse.io"
        f"/v1/boards/{token}"
    )

    if not isinstance(
        payload,
        dict,
    ):
        return None

    name = payload.get(
        "name"
    )

    return (
        name
        if isinstance(
            name,
            str,
        )
        else None
    )


def _fetch_text(
    url: str,
) -> str:
    """Return a page's HTML, or empty when it does not answer."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            if response.status != 200:
                return ""

            return response.read(
                200_000
            ).decode(
                "utf-8",
                "replace",
            )
    except Exception:
        return ""


# Ashby and Lever publish no board metadata, but both put the employer
# in the board page's title: "Ramp Jobs", "Wealthfront". Written by the
# employer and not derived from the token, so it is real evidence.
BOARD_PAGE_URLS = {
    "ashby": "https://jobs.ashbyhq.com/{token}",
    "lever": "https://jobs.lever.co/{token}",
}

_TITLE = re.compile(
    r"<title[^>]*>([^<]{1,120})",
    re.IGNORECASE,
)

_TITLE_NOISE = re.compile(
    r"\b(jobs?|careers?|openings?|"
    r"job\s*board|hiring|open\s*roles?)\b",
    re.IGNORECASE,
)


def board_page_name(
    *,
    source_type: str,
    token: str,
    fetch_text=_fetch_text,
) -> str | None:
    """Return the employer named in a board page's title."""

    template = BOARD_PAGE_URLS.get(
        source_type
    )

    if template is None:
        return None

    match = _TITLE.search(
        fetch_text(
            template.format(
                token=token
            )
        )
    )

    if match is None:
        return None

    return _TITLE_NOISE.sub(
        " ",
        match.group(
            1
        ),
    ).strip() or None


def board_belongs_to(
    *,
    company: str,
    source_type: str,
    token: str,
    jobs: list[dict],
    fetch=_fetch_json,
    fetch_text=_fetch_text,
) -> str | None:
    """Return why this board is the company's, or None if unproven.

    A token matching is not evidence, and neither is a URL built from
    that token. The board has to name the company somewhere the
    employer wrote it.

    Returning None is the safe answer. An unverified board is dropped
    rather than guessed at, because a wrong subscription fills the
    queue with another employer's jobs under a name the user
    recognises, which is harder to notice than a gap.
    """

    key = normalise_company(
        company
    )

    if not key:
        return None

    declared = board_metadata_name(
        source_type=source_type,
        token=token,
        fetch=fetch,
    )

    if declared and normalise_company(
        declared
    ) == key:
        return (
            "board declares itself "
            f"{declared!r}"
        )

    if declared:
        # It answered, and with somebody else's name.
        return None

    titled = board_page_name(
        source_type=source_type,
        token=token,
        fetch_text=fetch_text,
    )

    if titled and normalise_company(
        titled
    ) == key:
        return (
            "board page titled "
            f"{titled!r}"
        )

    # No metadata endpoint. Fall back to the employer's own words in a
    # posting, which is weaker: plenty of postings never name the
    # company, so this finds fewer boards rather than wrong ones.
    for job in jobs[
        :VERIFY_SAMPLE
    ]:
        for field in (
            "descriptionPlain",
            "text",
            "title",
            "department",
        ):
            value = job.get(
                field
            )

            if not isinstance(
                value,
                str,
            ):
                continue

            if key in normalise_company(
                value
            ):
                return (
                    "company named in "
                    f"posting {field}"
                )

    return None


def careers_page_token(
    html: str,
) -> tuple[str, str] | None:
    """Read the board token a careers page embeds.

    This is how a token nothing like the company name is found.
    Current's page embeds "current81" while "current" is a different
    employer's live board, so guessing cannot reach it and reading can.
    """

    patterns = (
        (
            "greenhouse",
            r"boards\.greenhouse\.io/embed/"
            r"job_board\?for=([A-Za-z0-9_-]+)",
        ),
        (
            "greenhouse",
            r"(?:job-boards|boards)"
            r"\.greenhouse\.io/"
            r"([A-Za-z0-9_-]+)",
        ),
        (
            "greenhouse",
            r"for=([A-Za-z0-9_-]+)",
        ),
        (
            "lever",
            r"jobs\.lever\.co/([A-Za-z0-9_-]+)",
        ),
        (
            "ashby",
            r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)",
        ),
    )

    for source_type, pattern in patterns:
        match = re.search(
            pattern,
            html,
        )

        if match:
            token = match.group(
                1
            )

            if token.lower() not in {
                "embed",
                "job_board",
                "jobs",
            }:
                return (
                    source_type,
                    token,
                )

    return None


def find_board(
    company: str,
    *,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
) -> BoardCandidate | None:
    """Return a verified board for a company, or None.

    None means "not found by this method", never "no board exists".
    The careers-page route finds tokens this one cannot.
    """

    for token in token_guesses(
        company
    ):
        for source_type, url in board_endpoints(
            token
        ):
            payload = fetch(
                url
            )

            jobs = _jobs_from(
                payload
            )

            if not jobs:
                continue

            evidence = board_belongs_to(
                company=company,
                source_type=source_type,
                token=token,
                jobs=jobs,
                fetch=fetch,
                fetch_text=fetch_text,
            )

            if evidence is None:
                # The board is real and someone else's, or it is
                # theirs and says so nowhere ACE can check. Either way
                # it is not safe to subscribe to.
                continue

            return BoardCandidate(
                company=company,
                source_type=source_type,
                source_account=token,
                job_count=len(
                    jobs
                ),
                evidence=evidence,
            )

    return None
