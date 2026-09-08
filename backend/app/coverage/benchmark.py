"""How much of the market ACE actually reaches.

Coverage was quoted at 64% once and the number was worthless: it was
measured against companies the user had applied to, and they applied to
those companies largely because ACE had shown them. Selection bias
dressed as evidence.

The honest measure is recall against a source ACE has never seen. ACE
seeds its board list from SimplifyJobs; these held-out lists are
maintained by other people, overlap only by coincidence, and are never
used for seeding. Whatever fraction of their companies ACE reaches is
a fraction it earned.

Read the number as directional, not absolute. These lists are
themselves incomplete, they skew toward companies that hire new
graduates publicly, and a company counts as reached even if the one
role the list names is not in ACE. What the number is good for is
movement: run it, change discovery, run it again.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


# Held-out on purpose. Adding any of these to the seed feeds destroys
# the measurement, because ACE would then be tested on its own inputs.
HELD_OUT_LISTS = (
    (
        "speedyapply/2026-SWE-College-Jobs",
        "https://raw.githubusercontent.com/"
        "speedyapply/2026-SWE-College-Jobs/"
        "main/README.md",
    ),
    (
        "vanshb03/New-Grad-2026",
        "https://raw.githubusercontent.com/"
        "vanshb03/New-Grad-2026/"
        "main/README.md",
    ),
    (
        "jobright-ai/2025-SWE-New-Grad",
        "https://raw.githubusercontent.com/"
        "jobright-ai/"
        "2025-Software-Engineer-New-Grad/"
        "master/README.md",
    ),
)


_PUNCTUATION = re.compile(
    r"[^a-z0-9 ]"
)

_SUFFIXES = re.compile(
    r"\b(?:inc|llc|ltd|corp|corporation|"
    r"technologies|technology|labs|"
    r"group|co|the)\b"
)

_SPACES = re.compile(
    r"\s+"
)

# Cells that are table furniture rather than an employer.
_NOT_A_COMPANY = frozenset(
    {
        "company",
        "name",
        "company name",
        "role",
        "position",
        "location",
    }
)


def normalise_company(
    name: str | None,
) -> str:
    """Reduce a company name to a comparable key.

    Both sides of the comparison are normalised the same way, so
    "Stripe, Inc." and "stripe" are one company and a spelling
    difference does not read as a coverage gap.
    """

    lowered = (
        name or ""
    ).lower()

    stripped = _PUNCTUATION.sub(
        " ",
        lowered,
    )

    without_suffix = _SUFFIXES.sub(
        " ",
        stripped,
    )

    return _SPACES.sub(
        " ",
        without_suffix,
    ).strip()


def companies_in_markdown(
    text: str,
) -> set[str]:
    """Pull employer names out of a markdown job table.

    These lists are all tables whose first column is the employer,
    written variously as a bare name, a bold name, or a link. Rows that
    carry no employer are skipped rather than guessed at.
    """

    names: set[str] = set()

    for line in text.splitlines():
        if not line.startswith(
            "|"
        ):
            continue

        cells = [
            cell.strip()
            for cell in line.strip(
                "|"
            ).split(
                "|"
            )
        ]

        if len(cells) < 2:
            continue

        first = cells[0]

        match = (
            re.search(
                r"\*\*\[([^\]]+)\]",
                first,
            )
            or re.search(
                r"\[([^\]]+)\]",
                first,
            )
            or re.search(
                r"\*\*([^*]+)\*\*",
                first,
            )
        )

        raw = re.sub(
            r"<[^>]+>",
            "",
            match.group(1)
            if match
            else first,
        ).strip()

        key = normalise_company(
            raw
        )

        if (
            not key
            or len(key) < 2
            or key in _NOT_A_COMPANY
            or "arrow" in key
        ):
            continue

        names.add(
            key
        )

    return names


@dataclass(
    frozen=True,
    slots=True,
)
class ListResult:
    """ACE's recall against one held-out list."""

    name: str

    listed: int

    in_corpus: int

    watched: int

    missing: tuple[str, ...]

    @property
    def reached(self) -> int:
        """Return companies ACE either polls or already holds jobs for."""

        return (
            self.listed
            - len(
                self.missing
            )
        )

    @property
    def recall(self) -> float:
        """Return the reached fraction, 0 when the list is empty."""

        if not self.listed:
            return 0.0

        return (
            self.reached
            / self.listed
        )


def measure_list(
    *,
    name: str,
    markdown: str,
    corpus: set[str],
    watched: set[str],
) -> ListResult:
    """Score one held-out list against what ACE reaches.

    A company counts as reached if ACE polls its board or already holds
    a posting from it. Either means ACE had a path to the job; which of
    the two it was is a question for discovery, not coverage.
    """

    listed = companies_in_markdown(
        markdown
    )

    reachable = corpus | watched

    return ListResult(
        name=name,
        listed=len(
            listed
        ),
        in_corpus=len(
            listed & corpus
        ),
        watched=len(
            listed & watched
        ),
        missing=tuple(
            sorted(
                listed - reachable
            )
        ),
    )


def overall_recall(
    results: list[ListResult],
) -> float:
    """Return recall across every list, weighted by companies listed."""

    listed = sum(
        result.listed
        for result in results
    )

    if not listed:
        return 0.0

    return (
        sum(
            result.reached
            for result in results
        )
        / listed
    )
