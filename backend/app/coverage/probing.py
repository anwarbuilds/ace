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
from backend.app.coverage.companies import is_namesake


USER_AGENT = "ACE-source-discovery/1.0"

TIMEOUT_SECONDS = 8.0


# Enough of the board to tell whose it is without pulling every job.
VERIFY_SAMPLE = 25

# How much of a careers page to read.
#
# This was 200KB, and Zendesk's careers page is bigger than that: the
# Workday link sat past the cut, so the page was fetched, parsed, found
# to contain no board, and written off. The company looked unreachable
# and the reason was a buffer size. Marketing pages carrying inlined
# CSS and JSON-LD run large, so the limit has to clear them rather than
# a hand-written page.
PAGE_READ_BYTES = 800_000


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

    # Where to poll, for the boards whose account does not say. A
    # Greenhouse token implies its own host; a Workday account is a
    # tenant and a site path, and which of Workday's several dozen
    # hosts serves that tenant is a separate fact. Polling cannot
    # start without it, so discovery has to carry it.
    source_host: str = ""


@dataclass(
    frozen=True,
    slots=True,
)
class BoardRef:
    """A board some page points at, before anyone has checked whose.

    Deliberately not a BoardCandidate. A candidate has been verified
    and carries the reason; this is only "a link on a page said this",
    which is the input to verification and never a substitute for it.
    """

    source_type: str

    token: str

    source_host: str = ""


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
        # Last because it is the only one that answers 200 for a
        # company that does not exist, with an empty page of results.
        # That costs nothing here -- no jobs means no candidate -- but
        # it means a SmartRecruiters 200 is not evidence of anything.
        (
            "smartrecruiters",
            "https://api.smartrecruiters.com"
            f"/v1/companies/{token}/postings?limit=100",
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
        for key in (
            "jobs",
            # SmartRecruiters pages its postings under "content".
            "content",
            # Workday's careers API, which answers a POST.
            "jobPostings",
        ):
            jobs = payload.get(
                key
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
                PAGE_READ_BYTES
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


# A company that writes its own name with its domain attached. Calm's
# Greenhouse board declares itself "Calm.com", and comparing that to
# "Calm" for exact equality rejected a board that really is theirs --
# then returned early, because a board that names *somebody else* must
# not be rescued by weaker evidence. The refusal was right and the
# comparison was wrong.
_TLD_TAIL = re.compile(
    r"\.(?:com|ai|io|co|dev|org|net|app|tech|xyz)$",
    re.IGNORECASE,
)


_PUNCT = re.compile(
    r"[^a-z0-9]+"
)


def _unstripped(
    name: str,
) -> str:
    """Lowercase a name without dropping any of its words.

    normalise_company exists to make two spellings of one company
    compare equal, and does it by deleting the words companies vary on
    -- Inc, Labs, Technologies. That is right for asking "have we
    reached this company" and wrong for asking "is this posting about
    this company", where the deleted word is often the only thing
    separating two employers.
    """

    return _PUNCT.sub(
        " ",
        (
            name or ""
        ).lower(),
    ).strip()


def _comparable(
    name: str,
) -> set[str]:
    """Return the keys a name could reasonably be written as.

    Trimming is deliberately narrow: a trailing domain suffix, and
    nothing else. In particular this is not company_keys, which also
    drops generic trailing words so that one list writing "Anduril"
    and another writing "Anduril Industries" count as one company.
    That is the right rule for measuring coverage and the wrong rule
    for deciding whose board this is -- under it "Ramp Networks"
    accepts a board belonging to Ramp, and "Aurora Innovation" accepts
    Aurora Labs, which is the subscription ACE actually made once and
    had to unpick.
    """

    text = (
        name or ""
    ).strip()

    keys = {
        key
        for key in (
            normalise_company(
                text
            ),
        )
        if key
    }

    trimmed = _TLD_TAIL.sub(
        "",
        text,
    )

    if trimmed and trimmed != text:
        key = normalise_company(
            trimmed
        )

        if key:
            keys.add(
                key
            )

    return keys


def posting_company_name(
    jobs: list[dict],
) -> str | None:
    """Return the employer a SmartRecruiters posting names.

    Every posting carries ``company.name`` written by the employer, so
    this is the same quality of evidence as Greenhouse's board
    metadata rather than the weaker read of posting prose.
    """

    for job in jobs[
        :VERIFY_SAMPLE
    ]:
        company = job.get(
            "company"
        )

        if not isinstance(
            company,
            dict,
        ):
            continue

        name = company.get(
            "name"
        )

        if isinstance(
            name,
            str,
        ) and name.strip():
            return name.strip()

    return None


# Titles that are somebody trying the software out, not a job.
#
# Written to need more than the word "test", because "Test
# Infrastructure Engineer" and "SDET - Test Automation" are real roles
# and refusing those would be worse than the problem. What these match
# is test data: "Test UAT", "Rene's Test Job", "Test Job 2".
_PLACEHOLDER_TITLE = re.compile(
    r"\b(?:uat|sandbox|dummy|placeholder|"
    r"do not apply)\b"
    r"|\btest\s+job\b"
    r"|\btest\s*\d*\s*$",
    re.IGNORECASE,
)


def looks_like_a_sandbox(
    jobs: list[dict],
) -> bool:
    """Is every posting on this board somebody testing the software?

    SmartRecruiters' ``uber`` board holds one posting, "Test UAT", and
    its ``bigcommerce`` board holds "Rene's Test Job" and "Test Job 2".
    Both declare the right employer, so every name check passes them,
    and subscribing to either would make the coverage page report a
    company as reached while ACE saw nothing real from them -- the
    number lying, which is the one thing that page exists to stop.

    All of them, not any of them: a real board with a test posting
    left on it is still a real board.
    """

    titles = [
        title
        for job in jobs
        for title in (
            job.get(
                "title"
            )
            or job.get(
                "name"
            )
            or "",
        )
        if title
    ]

    if not titles:
        return False

    return all(
        _PLACEHOLDER_TITLE.search(
            title
        )
        for title in titles
    )


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

    if looks_like_a_sandbox(
        jobs
    ):
        return None

    # Checked by hand once and found to be a different company of the
    # same name. Nothing readable distinguishes them, so the finding
    # is recorded rather than re-derived.
    if is_namesake(
        source_type,
        token,
    ):
        return None

    keys = _comparable(
        company
    )

    declared = board_metadata_name(
        source_type=source_type,
        token=token,
        fetch=fetch,
    ) or (
        posting_company_name(
            jobs
        )
        if source_type == "smartrecruiters"
        else None
    )

    if declared and (
        keys
        & _comparable(
            declared
        )
    ):
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

    if titled and (
        keys
        & _comparable(
            titled
        )
    ):
        return (
            "board page titled "
            f"{titled!r}"
        )

    # No metadata endpoint. Fall back to the employer's own words in a
    # posting, which is the weakest evidence here and is held to the
    # strictest form of the name because of it.
    #
    # normalise_company drops "Labs", "Technologies" and the like, so
    # "Astera Labs" reduces to "astera" -- and the Astera Institute, a
    # private research foundation, writes "ABOUT ASTERA" at the top of
    # every posting. That board passed this check and was proposed as
    # Astera Labs, the semiconductor company. It is the same failure
    # as Aurora Labs against Aurora Innovation, one tier down.
    #
    # So prose is matched against the whole name, suffixes and all. A
    # board belonging to Astera Labs says "Astera Labs" somewhere; a
    # foundation called Astera does not.
    full = _unstripped(
        company
    )

    if not full:
        return None

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

            if full in _unstripped(
                value
            ):
                return (
                    "company named in "
                    f"posting {field}"
                )

    return None


# Where a careers page can point, ordered strongest first. The last
# entry matches any "for=" parameter at all, which is how a Greenhouse
# embed script is written, and is also the only one loose enough to
# match something that is not a board -- so it goes last, after every
# pattern that names its host.
_BOARD_PATTERNS = (
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
        "lever",
        r"jobs\.lever\.co/([A-Za-z0-9_-]+)",
    ),
    (
        "ashby",
        r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)",
    ),
    (
        "smartrecruiters",
        r"(?:careers|jobs)\.smartrecruiters\.com/"
        r"(?:[A-Za-z0-9_-]+/)?([A-Za-z0-9_-]+)",
    ),
    (
        "greenhouse",
        r"for=([A-Za-z0-9_-]+)",
    ),
)


# Workday is matched apart from the rest because its URL carries three
# separate facts -- tenant, data centre, site -- where the others carry
# one, and none of them can be derived from the others.
_WORKDAY = re.compile(
    r"([a-z0-9][a-z0-9-]*)\.(wd\d+)"
    r"\.myworkdayjobs\.com/([A-Za-z0-9_%./-]*)",
    re.IGNORECASE,
)

# A locale Workday puts in front of the site name on some tenants:
# ".../en-US/Boston_Dynamics/..." is the Boston_Dynamics site, not a
# site called "en-US".
_LOCALE = re.compile(
    r"^[a-z]{2}([-_][A-Za-z]{2})?$",
)

_NOT_A_TOKEN = frozenset(
    {
        "embed",
        "job_board",
        "jobs",
        "careers",
        "wday",
    }
)


def _workday_ref(
    html: str,
) -> "BoardRef | None":
    """Read a Workday board out of a page.

    Workday cannot be guessed at all. The data-centre number is not
    derivable from anything -- Zendesk is on wd1, BigCommerce on wd12,
    NVIDIA on wd5 -- so a Workday board is reachable only if the
    employer published the URL somewhere ACE can read it.
    """

    match = _WORKDAY.search(
        html
    )

    if match is None:
        return None

    tenant = match.group(
        1
    ).lower()

    host = (
        f"{tenant}."
        f"{match.group(2).lower()}"
        ".myworkdayjobs.com"
    )

    segments = [
        segment
        for segment in match.group(
            3
        ).split(
            "/"
        )
        if segment
    ]

    while segments and _LOCALE.match(
        segments[0]
    ):
        segments = segments[1:]

    if not segments:
        return None

    return BoardRef(
        source_type="workday",
        token=(
            f"{tenant}/{segments[0]}"
        ),
        source_host=host,
    )


def careers_page_token(
    html: str,
) -> "BoardRef | None":
    """Read the board a page points at.

    This is how a token nothing like the company name is found.
    Current's page embeds "current81" while "current" is a different
    employer's live board, so guessing cannot reach it and reading can.

    What comes back is only what the page said. Whose board it is, is
    a separate question, and every caller has to ask it.
    """

    for source_type, pattern in _BOARD_PATTERNS:
        match = re.search(
            pattern,
            html,
        )

        if match is None:
            continue

        token = match.group(
            1
        )

        if token.lower() in _NOT_A_TOKEN:
            continue

        return BoardRef(
            source_type=source_type,
            token=token,
        )

    return _workday_ref(
        html
    )


def _post_json(
    url: str,
    payload: dict,
):
    """POST JSON and return the decoded reply, or None.

    Workday's careers API is the one board ACE reads that will not
    answer a GET.
    """

    request = urllib.request.Request(
        url,
        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": (
                "application/json"
            ),
            "Accept": (
                "application/json"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
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


def board_jobs(
    ref: "BoardRef",
    *,
    fetch=_fetch_json,
    post=_post_json,
) -> list[dict]:
    """Return a sample of a board's postings, whatever ATS it is on."""

    if ref.source_type == "workday":
        tenant, _, site = ref.token.partition(
            "/"
        )

        if not (
            tenant
            and site
            and ref.source_host
        ):
            return []

        return _jobs_from(
            post(
                f"https://{ref.source_host}"
                f"/wday/cxs/{tenant}/{site}/jobs",
                {
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": 0,
                    "searchText": "",
                },
            )
        )

    endpoint = dict(
        board_endpoints(
            ref.token
        )
    ).get(
        ref.source_type
    )

    if endpoint is None:
        return []

    return _jobs_from(
        fetch(
            endpoint
        )
    )


def workday_belongs_to(
    *,
    company: str,
    token: str,
) -> str | None:
    """Return why a Workday board is this company's, or None.

    Workday publishes no employer name anywhere ACE can read: no board
    metadata, no title worth trusting, and postings that never name the
    company. The only fact available is the tenant, which the employer
    chose and which sits in a hostname they control.

    So the rule is narrow on purpose: the tenant has to be the
    company's own name. That refuses boards that really are theirs --
    a tenant abbreviated past recognition is unreachable by this route
    -- and it also refuses the failure that made the rule necessary.
    Sana Labs' careers page links Workday's own tenant, because they
    run their hiring on Workday the product; a route that believed the
    link would have subscribed ACE to Workday Inc's vacancies under the
    name "Sana Labs".
    """

    if is_namesake(
        "workday",
        token,
    ):
        return None

    tenant = token.partition(
        "/"
    )[0].replace(
        "-",
        ""
    ).lower()

    if len(
        tenant
    ) < 3:
        return None

    for key in _comparable(
        company
    ):
        flattened = key.replace(
            " ",
            ""
        )

        if not flattened:
            continue

        if tenant == flattened:
            return (
                "Workday tenant "
                f"{tenant!r} is the "
                "company's own"
            )

        # "devoted" for Devoted Health, "bolt" for Bolt Financial.
        # A prefix only, and only a substantial one: a two- or
        # three-letter head matches half the internet.
        if len(
            tenant
        ) >= 4 and flattened.startswith(
            tenant
        ):
            return (
                "Workday tenant "
                f"{tenant!r} is the "
                "company's own"
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

# Words that describe what a company does rather than name it, and so
# are worth dropping when guessing at a domain: Clay Labs is clay.com,
# Bolt Financial is bolt.com. Only ever used to make an extra guess --
# never to decide that two names are the same company.
_DOMAIN_FILLER = frozenset(
    {
        "labs",
        "technologies",
        "technology",
        "systems",
        "industries",
        "aviation",
        "aerospace",
        "robotics",
        "financial",
        "trading",
        "capital",
        "analytics",
        "innovation",
        "health",
        "space",
        "defense",
        "bank",
        "trust",
        "internet",
        "associates",
        "group",
        "inc",
        "the",
    }
)


# Finding the company's own site, before reading anything off it.
#
# The old route guessed "<name>.com/careers" and read whatever
# answered. What answered was often somebody else: "Adept" landed on
# Omron's robotics division, "Beta Technologies" on an unrelated
# software firm, "Chime" on a squatted .ai. Every one of those pages
# was then searched for a board to subscribe the user to.
#
# Nothing bad reached the database, because the board is verified
# afterwards against the employer's own name. But searching the wrong
# company's website for the right company's board is not a search, and
# the one failure it cannot catch is the one where the wrong page
# happens to link a board that passes -- which is how ACE came to poll
# Aurora Labs for a user who wanted Aurora Innovation.
#
# So the site is established first, and only a site that says it is
# this company is read.
CAREERS_DOMAIN_SUFFIXES = (
    ".com",
    ".ai",
    ".io",
    ".co",
    ".dev",
    ".tech",
    ".net",
    ".org",
)

CAREERS_PATHS = (
    "/careers",
    "/jobs",
    "/careers/",
    "/company/careers",
    "/about/careers",
    "/careers/open-roles",
    "/en/careers",
)

def domain_candidates(
    company: str,
) -> list[str]:
    """Return hostnames this company might publish under."""

    lowered = (
        company or ""
    ).strip().lower()

    if not lowered:
        return []

    hosts: list[str] = []

    # "Bill.com", "Copy.ai", "Monday.com" carry their own domain, and
    # flattening them to "billcom.com" reaches a different site.
    if "." in lowered and " " not in lowered:
        hosts.append(
            lowered
        )

    words = [
        word
        for word in re.split(
            r"[^a-z0-9]+",
            lowered,
        )
        if word
    ]

    if not words:
        return hosts

    bases = [
        "".join(
            words
        )
    ]

    kept = [
        word
        for word in words
        if word not in _DOMAIN_FILLER
    ]

    if kept and kept != words:
        bases.append(
            "".join(
                kept
            )
        )

    if len(
        kept
    ) > 1 and len(
        kept[0]
    ) >= 4:
        bases.append(
            kept[0]
        )

    for base in bases:
        if len(
            base
        ) < 3:
            continue

        for suffix in CAREERS_DOMAIN_SUFFIXES:
            hosts.append(
                base + suffix
            )

    seen: set[str] = set()

    return [
        host
        for host in hosts
        if not (
            host in seen
            or seen.add(
                host
            )
        )
    ]


_OG_SITE_NAME = (
    re.compile(
        r"og:site_name[^>]*content="
        r"[\"\']([^\"\']{1,80})",
        re.IGNORECASE,
    ),
    re.compile(
        r"content=[\"\']([^\"\']{1,80})"
        r"[\"\'][^>]*og:site_name",
        re.IGNORECASE,
    ),
)


def leading_word(
    company: str,
) -> str:
    """Return the word this company is actually known by.

    "Column" out of "Column Bank", "Chainalysis" out of "Chainalysis".
    Short words and words that describe an industry rather than name a
    company are skipped, because those are what make a name match the
    wrong employer.
    """

    return next(
        (
            word
            for word in normalise_company(
                company
            ).split()
            if len(
                word
            ) >= 4
            and word not in _DOMAIN_FILLER
        ),
        "",
    )


def _claimed_names(
    html: str,
) -> list[str]:
    """Return the names a page publishes for itself."""

    claims: list[str] = []

    for pattern in _OG_SITE_NAME:
        match = pattern.search(
            html
        )

        if match:
            claims.append(
                match.group(
                    1
                )
            )

    title = _TITLE.search(
        html
    )

    if title:
        claims.append(
            title.group(
                1
            )
        )

    return claims


def page_names_company(
    company: str,
    html: str,
) -> bool:
    """Does this page say it belongs to this company?

    Deliberately a containment test rather than the equality used on a
    board. A careers page is titled "Life at Canva" or "Careers |
    Chainalysis", and demanding the exact name would reject almost all
    of them. It is not evidence about whose board was found: whatever
    is read here is still verified afterwards against a name the
    employer wrote.

    The hostname is not consulted, and that is the point. Discovery
    guesses the hostname from the company name, so a host that
    contains the name proves only that the guess was consistent with
    itself -- the same circularity that makes a Greenhouse job's own
    URL useless as evidence about the board.
    """

    key = normalise_company(
        company
    ).replace(
        " ",
        "",
    )

    if len(
        key
    ) < 3:
        return False

    # Column Bank publishes at column.com under the name "Column", and
    # demanding the whole name there rejected the right site.
    lead = leading_word(
        company
    )

    for claim in _claimed_names(
        html
    ):
        claimed = normalise_company(
            claim
        )

        if key in claimed.replace(
            " ",
            "",
        ):
            return True

        if lead and lead in claimed.split():
            return True

    return False


# A domain someone is selling, rather than a company using it.
#
# These defeat the site check in the one way it cannot see coming:
# the page's title is the domain itself, so it contains the company's
# name and reads as a positive identification. worldlabs.com is titled
# "WORLDLABS.COM | Strategic-Grade domain names for established
# businesses and funds", which counted as finding World Labs -- and
# because finding their site ends the search, it cost the real one at
# worldlabs.ai, whose careers page links an Ashby board in plain HTML.
#
# Written to need selling language, not the word "domain", so that a
# registrar or a hosting company describing its own product is not
# mistaken for a parking page.
_PARKED_DOMAIN = re.compile(
    r"\bdomain(?:\s+name)?s?\b[^.]{0,40}\bfor sale\b"
    r"|\bbuy this domain\b"
    r"|\bthis domain (?:is|may be) for sale\b"
    r"|\bpremium domains?\b"
    r"|\bdomain (?:broker|marketplace|names for)\b"
    r"|\bmake an offer\b[^.]{0,40}\bdomain\b"
    r"|\bparked (?:free )?(?:at|by)\b",
    re.IGNORECASE,
)


def looks_like_a_parked_domain(
    html: str,
) -> bool:
    """Is this a domain for sale rather than a company's website?"""

    return bool(
        _PARKED_DOMAIN.search(
            html[
                :40_000
            ]
        )
    )


def page_claims_another_company(
    company: str,
    html: str,
) -> bool:
    """Does this page say, in the employer's own words, that it is
    somebody else's?

    This is the gate, rather than page_names_company, because the two
    questions are not opposites. A page with no title and no
    og:site_name names nobody; it is not evidence that the site is the
    wrong one, and rejecting it would lose careers pages that are a
    bare list of links.

    What is worth rejecting is a page that positively names another
    employer. Guessing "<name>.com" put "Adept" on Omron's robotics
    division and "Beta Technologies" on an unrelated software firm,
    and both of those pages were then searched for a board to
    subscribe the user to.
    """

    claims = _claimed_names(
        html
    )

    if not claims:
        return False

    return not page_names_company(
        company,
        html,
    )


# How many pages of one site to read before giving up on it. A cap,
# not a target: most sites answer on the landing page or the first
# careers link, and the rest are not worth crawling.
MAX_PAGES_PER_SITE = 10

# And how many across every domain guessed for one company.
#
# Without this the worst case is the product of two caps -- eight
# candidate domains times ten pages each, every one of them allowed a
# full timeout -- which is several minutes spent on a single company
# that has no findable board, while the ones that do wait behind it.
# A sweep of the curated list has to finish in an afternoon to be run
# at all, so the budget is per company rather than per site.
MAX_PAGES_PER_COMPANY = 24

_CAREERS_LINK = re.compile(
    r"""href=["\']([^"\']{1,200})["\']""",
    re.IGNORECASE,
)

_CAREERS_WORD = re.compile(
    r"career|/jobs|join-us|joinus|"
    r"work-with-us|open-roles|hiring",
    re.IGNORECASE,
)


def _pages_to_read(
    root: str,
    host: str,
    landing: str,
) -> list[str]:
    """Return the pages of a verified site worth reading, in order.

    Guessing paths finds a careers page only when it sits where the
    guess expects. Zendesk publishes at /company/careers, Canva at a
    separate domain, Cadence under a locale prefix. The site's own
    navigation already says where it is, so that is read first and the
    guesses are the fallback.
    """

    urls = [
        root
    ]

    for match in _CAREERS_LINK.finditer(
        landing
    ):
        href = match.group(
            1
        )

        if not _CAREERS_WORD.search(
            href
        ):
            continue

        if href.startswith(
            "http"
        ):
            urls.append(
                href
            )
        elif href.startswith(
            "/"
        ):
            urls.append(
                root + href
            )

    urls.extend(
        root + path
        for path in CAREERS_PATHS
    )

    urls.extend(
        (
            f"https://careers.{host}",
            f"https://jobs.{host}",
        )
    )

    seen: set[str] = set()

    return [
        url
        for url in urls
        if not (
            url in seen
            or seen.add(
                url
            )
        )
    ][
        :MAX_PAGES_PER_SITE
    ]


def linked_board_belongs_to(
    *,
    company: str,
    source_type: str,
    token: str,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
) -> str | None:
    """Return why a board linked from the company's own site is theirs.

    Weaker than board_belongs_to on purpose, and only ever reachable
    from a page already confirmed to belong to this company. Column
    Bank's careers page links an Ashby board that titles itself
    "Column"; that is not their full name, so the strict check refuses
    it, and refusing was costing a real board on the strength of a
    word the employer simply does not print.

    What is not relaxed is the part that matters. The board still has
    to name a company, and that name still has to be recognisably this
    one. A page linking somebody else's board -- Sana Labs link
    Workday's, because they are a Workday customer -- names a company
    that shares nothing with the employer, and is still refused.
    """

    if is_namesake(
        source_type,
        token,
    ):
        return None

    lead = leading_word(
        company
    )

    if not lead:
        return None

    declared = board_metadata_name(
        source_type=source_type,
        token=token,
        fetch=fetch,
    ) or board_page_name(
        source_type=source_type,
        token=token,
        fetch_text=fetch_text,
    )

    if not declared:
        return None

    if lead not in normalise_company(
        declared
    ).split():
        return None

    return (
        "linked from the company's own "
        "careers page, and the board "
        f"declares itself {declared!r}"
    )


def candidate_for_token(
    company: str,
    token: str,
    *,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
) -> BoardCandidate | None:
    """Return a verified board for one exact token, or None."""

    for source_type, url in board_endpoints(
        token
    ):
        jobs = _jobs_from(
            fetch(
                url
            )
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


def find_board_via_careers_page(
    company: str,
    *,
    fetch=_fetch_json,
    fetch_text=_fetch_text,
    post=_post_json,
) -> BoardCandidate | None:
    """Find a board by reading the token off the company's own page.

    This is the route for a token nothing like the company name.
    Sourcegraph's board is ``sourcegraph91`` and no guess derived from
    "Sourcegraph" reaches it; their careers page says so plainly. It is
    also the only route to a Workday board at all, because a Workday
    URL carries a data-centre number that is not derivable from
    anything: Zendesk is on wd1, BigCommerce on wd12, NVIDIA on wd5.

    The token is read, never trusted. Mistral's careers page links a
    ``jobs.ashbyhq.com/mistral`` board that returns 404, so a route
    that registered what it read would have subscribed ACE to nothing.
    Everything found here goes through the same verification as a
    guessed token: the board must answer, and it must identify itself
    as this employer.
    """

    budget = MAX_PAGES_PER_COMPANY

    for host in domain_candidates(
        company
    ):
        if budget <= 0:
            return None

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
            # Somebody else's site, or nobody's. Reading either for a
            # board would be searching the wrong company's website,
            # which is not a search.
            continue

        # Whether this site said, in so many words, that it is this
        # company. Not the same as having got past the check above:
        # a page that names nobody clears that check without
        # identifying anyone, and plenty of real careers pages are
        # exactly that. Only a positive identification means the
        # search is over.
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

            # Checked per page, not once per site. Plenty of companies
            # serve a bot-hostile landing page and a plain careers
            # page, so a root that does not answer must not cost the
            # site; and a careers page that turns out to be a
            # recruiter's or a partner's must not be read just because
            # the root was fine.
            if page_claims_another_company(
                company,
                html,
            ):
                continue

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
                continue

            jobs = board_jobs(
                ref,
                fetch=fetch,
                post=post,
            )

            if not jobs:
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
                continue

            return BoardCandidate(
                company=company,
                source_type=ref.source_type,
                source_account=ref.token,
                job_count=len(
                    jobs
                ),
                evidence=(
                    evidence
                    + ", found on "
                    + url
                ),
                source_host=ref.source_host,
            )

        # Some boards are named after the employer's domain rather
        # than their name. Kraken's live Ashby board is "kraken.com";
        # the one their careers page links is "kraken", a restricted
        # board with nothing public on it. Worth one request, and only
        # for a domain already confirmed to be this company's.
        if not landing:
            continue

        by_domain = candidate_for_token(
            company,
            host,
            fetch=fetch,
            fetch_text=fetch_text,
        )

        if by_domain is not None:
            return by_domain

        if identified:
            # Their site has been found and read, and it points at no
            # board ACE can verify. The remaining guesses are other
            # spellings of the same name, which at this point are more
            # likely to be a lookalike than a second site of theirs --
            # and reading a lookalike is how a wrong board gets found.
            return None

    return None
