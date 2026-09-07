"""Deciding which stored posting an application row refers to.

The asymmetry here drives every decision: a missed match costs one row
the user re-checks by hand, while a wrong match silently tells them they
already applied to something they did not. So this never guesses. When
two postings are equally good candidates the row is reported as
ambiguous and left for the user, rather than resolved by a tiebreak that
would be arbitrary.

Three strategies, strongest first:

1. The posting URL, which identifies a job exactly.
2. Company and title, both normalized.
3. Company plus a strong token overlap on the title, for rows typed by
   hand where the title was abbreviated.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit


# Below this share of shared title words, a same-company candidate is
# not proposed at all. Set high because "Software Engineer" overlaps
# almost everything a tech company posts.
TITLE_OVERLAP_THRESHOLD = 0.75


# Words that carry no distinguishing weight in a job title.
TITLE_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "for",
        "in",
        "of",
        "the",
        "to",
        "with",
        "new",
        "grad",
        "graduate",
        "entry",
        "level",
        "i",
        "ii",
        "1",
        "2",
    }
)


# Suffixes companies add to their own name but job trackers rarely do.
COMPANY_SUFFIXES = (
    "inc",
    "llc",
    "ltd",
    "corp",
    "corporation",
    "co",
    "gmbh",
    "plc",
    "technologies",
    "technology",
    "labs",
    "group",
    "holdings",
)


@dataclass(
    frozen=True,
    slots=True,
)
class Candidate:
    """One stored posting a row might refer to."""

    job_id: int

    company: str

    title: str

    official_url: str


@dataclass(
    frozen=True,
    slots=True,
)
class RowMatch:
    """The outcome of matching one application row."""

    row_number: int

    status: str

    method: str | None = None

    job_id: int | None = None

    candidates: tuple[Candidate, ...] = ()


MATCHED = "matched"

AMBIGUOUS = "ambiguous"

UNMATCHED = "unmatched"

UNUSABLE = "unusable"


def normalize_url(
    value: str | None,
) -> str | None:
    """Reduce a posting URL to a comparable identity.

    Query strings carry tracking parameters that differ between the copy
    a person saved and the copy ACE stored, so they are dropped. The
    path is kept, because that is what identifies the posting.
    """

    if not value:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    if "://" not in text:
        text = f"https://{text}"

    try:
        parts = urlsplit(
            text
        )
    except ValueError:
        return None

    host = (
        parts.netloc or ""
    ).lower()

    if host.startswith(
        "www."
    ):
        host = host[4:]

    path = (
        parts.path or ""
    ).rstrip(
        "/"
    ).lower()

    if not host:
        return None

    return f"{host}{path}"


def normalize_company(
    value: str | None,
) -> str:
    """Reduce a company name to a comparable form."""

    text = re.sub(
        r"[^a-z0-9 ]+",
        " ",
        str(
            value or ""
        ).lower(),
    )

    words = [
        word
        for word in text.split()
        if word not in COMPANY_SUFFIXES
    ]

    return " ".join(
        words
    )


def tighten_company(
    value: str | None,
) -> str:
    """Return a company name with its spacing removed entirely.

    "Open AI" and "OpenAI" are the same employer, and a tracker written
    by hand will not agree with an ATS about the space. Comparing the
    spaceless forms costs nothing and recovered several hundred stored
    postings that were reporting as not found.
    """

    return normalize_company(
        value
    ).replace(
        " ",
        "",
    )


# People write "SDE" in a tracker and "Software Development Engineer"
# is what the employer posted. Without expansion those share no words
# at all and the row reports as not found even though ACE holds the
# posting. Expansion happens on both sides, so it cannot matter which
# form is abbreviated.
TITLE_ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "sde": (
        "software",
        "development",
        "engineer",
    ),
    "swe": (
        "software",
        "engineer",
    ),
    "sre": (
        "site",
        "reliability",
        "engineer",
    ),
    "mts": (
        "member",
        "technical",
        "staff",
    ),
    "mle": (
        "machine",
        "learning",
        "engineer",
    ),
    "ds": (
        "data",
        "scientist",
    ),
    "de": (
        "data",
        "engineer",
    ),
    "pm": (
        "product",
        "manager",
    ),
    "tpm": (
        "technical",
        "program",
        "manager",
    ),
    "fde": (
        "forward",
        "deployed",
        "engineer",
    ),
    "ml": (
        "machine",
        "learning",
    ),
    "nlp": (
        "natural",
        "language",
        "processing",
    ),
    "cv": (
        "computer",
        "vision",
    ),
    "qa": (
        "quality",
        "assurance",
    ),
    "eng": (
        "engineer",
    ),
    "engg": (
        "engineer",
    ),
    "dev": (
        "developer",
    ),
    "sw": (
        "software",
    ),
    "infra": (
        "infrastructure",
    ),
    "ops": (
        "operations",
    ),
    "fullstack": (
        "full",
        "stack",
    ),
    "backend": (
        "back",
        "end",
    ),
    "frontend": (
        "front",
        "end",
    ),
}


def title_tokens(
    value: str | None,
) -> frozenset[str]:
    """Reduce a job title to its distinguishing words.

    Known abbreviations expand to the words they stand for, so a title
    typed short still overlaps the title as posted.
    """

    text = re.sub(
        r"[^a-z0-9 ]+",
        " ",
        str(
            value or ""
        ).lower(),
    )

    words: set[str] = set()

    for word in text.split():
        if word in TITLE_STOPWORDS:
            continue

        expansion = (
            TITLE_ABBREVIATIONS.get(
                word
            )
        )

        if expansion:
            words.update(
                expansion
            )
        else:
            words.add(
                word
            )

    return frozenset(
        words
    )


def title_overlap(
    left: str | None,
    right: str | None,
) -> float:
    """Return the share of the shorter title's words that both share."""

    a = title_tokens(
        left
    )

    b = title_tokens(
        right
    )

    if not a or not b:
        return 0.0

    return len(
        a & b
    ) / min(
        len(a),
        len(b),
    )


def _partial_company_pool(
    company: str,
    *,
    by_company: dict[str, list[Candidate]],
) -> list[Candidate]:
    """Return candidates whose name contains the row's name as words.

    Whole words only, so "chase" reaches "jp morgan chase" but "ai"
    does not reach every company with those two letters inside it.
    Every partial hit is pooled together rather than picked between:
    if more than one employer survives, the title checks will report
    the row as ambiguous and the user decides.
    """

    wanted = set(
        company.split()
    )

    if not wanted:
        return []

    pooled: list[Candidate] = []

    for stored, candidates in (
        by_company.items()
    ):
        words = set(
            stored.split()
        )

        if wanted < words or words < wanted:
            pooled.extend(
                candidates
            )

    return pooled


def match_row(
    row,
    *,
    by_url: dict[str, Candidate],
    by_company: dict[str, list[Candidate]],
    by_tight: dict[str, list[Candidate]] | None = None,
    already_applied: frozenset[int] | None = None,
) -> RowMatch:
    """Decide which stored posting one application row refers to.

    ``already_applied`` carries the jobs an application is recorded
    against. Re-uploading an updated sheet is the intended daily habit,
    and without this every ambiguous row would have to be resolved by
    hand again on every upload. A candidate the user has already
    applied to is the one they picked last time.
    """

    by_tight = (
        by_tight
        if by_tight is not None
        else {}
    )

    applied = (
        already_applied
        if already_applied is not None
        else frozenset()
    )

    def settle(
        candidates: list[Candidate],
        *,
        method: str,
    ) -> RowMatch:
        """Resolve a set of equally good candidates.

        One already carrying an application is the choice made on a
        previous upload, so it is honoured rather than asked again.
        Two would mean the user applied to both, which the sheet cannot
        disambiguate, so that stays a question for them.
        """

        chosen = [
            candidate
            for candidate in candidates
            if candidate.job_id in applied
        ]

        if len(chosen) == 1:
            return RowMatch(
                row_number=row.row_number,
                status=MATCHED,
                method=(
                    "your earlier choice"
                ),
                job_id=chosen[0].job_id,
            )

        return RowMatch(
            row_number=row.row_number,
            status=AMBIGUOUS,
            method=method,
            candidates=tuple(
                candidates[:8]
            ),
        )

    if not row.is_usable:
        return RowMatch(
            row_number=row.row_number,
            status=UNUSABLE,
        )

    key = normalize_url(
        row.url
    )

    if key and key in by_url:
        return RowMatch(
            row_number=row.row_number,
            status=MATCHED,
            method="url",
            job_id=by_url[key].job_id,
        )

    company = normalize_company(
        row.company
    )

    if not company:
        return RowMatch(
            row_number=row.row_number,
            status=UNMATCHED,
        )

    pool = by_company.get(
        company,
        [],
    )

    if not pool:
        # "Open AI" against a stored "OpenAI".
        pool = by_tight.get(
            tighten_company(
                row.company
            ),
            [],
        )

    if not pool:
        # "Chase" against a stored "JP Morgan Chase". Only accepted
        # when the shorter name is a whole word inside the longer one,
        # and the result still has to survive the title checks below,
        # so a loose company match cannot produce a match on its own.
        pool = _partial_company_pool(
            company,
            by_company=by_company,
        )

    if not pool:
        return RowMatch(
            row_number=row.row_number,
            status=UNMATCHED,
        )

    wanted = title_tokens(
        row.title
    )

    exact = [
        candidate
        for candidate in pool
        if title_tokens(
            candidate.title
        )
        == wanted
    ]

    if len(exact) == 1:
        return RowMatch(
            row_number=row.row_number,
            status=MATCHED,
            method="company and title",
            job_id=exact[0].job_id,
        )

    if len(exact) > 1:
        return settle(
            exact,
            method="company and title",
        )

    scored = sorted(
        (
            (
                title_overlap(
                    row.title,
                    candidate.title,
                ),
                candidate,
            )
            for candidate in pool
        ),
        key=lambda pair: -pair[0],
    )

    close = [
        candidate
        for score, candidate in scored
        if score
        >= TITLE_OVERLAP_THRESHOLD
    ]

    if len(close) == 1:
        return RowMatch(
            row_number=row.row_number,
            status=MATCHED,
            method="company and similar title",
            job_id=close[0].job_id,
        )

    if len(close) > 1:
        return settle(
            close,
            method=(
                "company and similar title"
            ),
        )

    return RowMatch(
        row_number=row.row_number,
        status=UNMATCHED,
    )
