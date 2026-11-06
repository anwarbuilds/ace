"""A person's dated reading of each hiring platform's terms.

No program can judge terms, so this is written by hand. It is a note for the
owner, not legal advice. A platform with no entry shows as "Not read", never
as allowed. Only robots.txt ever stops a read: terms are for the owner to weigh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PlatformTerms:
    # "allowed": the platform publishes this route for public use.
    # "restricted": its terms limit automated reading; the owner decides.
    # "unclear": the terms do not settle it.
    verdict: str

    note: str

    url: str

    reviewed_on: date

    recheck_on: date


_REVIEWED = date(2026, 11, 5)

_RECHECK = date(2027, 5, 5)


def _reading(verdict: str, note: str, url: str) -> PlatformTerms:
    return PlatformTerms(verdict, note, url, _REVIEWED, _RECHECK)


# Only what was actually read. Greenhouse, Oracle, Eightfold, employers' own
# sites and their posting pages have no entry, so they say "Not read".
TERMS: dict[str, PlatformTerms] = {
    "lever": _reading(
        "allowed",
        'Its developer docs say published postings are public and "may be scraped by third parties". '
        "Its terms page could not be found.",
        "https://github.com/lever/postings-api",
    ),
    "ashby": _reading(
        "unclear",
        "Publishes this API for job boards. Its terms govern customers and say nothing about reading public boards.",
        "https://developers.ashbyhq.com/docs/public-job-posting-api",
    ),
    "smartrecruiters": _reading(
        "unclear",
        "Its docs describe the posting API with a key, and ACE reads it without one. Its terms could not be read.",
        "https://developers.smartrecruiters.com/docs/posting-api",
    ),
    "workable": _reading(
        "unclear",
        "Its terms govern customers and forbid harvesting candidates. They say nothing about reading public listings.",
        "https://www.workable.com/terms",
    ),
    "workday": _reading(
        "restricted",
        "Its site terms bar scraping Workday's own sites and APIs, and ignoring robots. "
        "They do not mention customers' career sites, which is where ACE reads.",
        "https://www.workday.com/en-us/legal/site-terms.html",
    ),
    "gem": _reading(
        "unclear",
        "Its terms govern customers and say nothing about reading public boards.",
        "https://www.gem.com/terms",
    ),
    "avature": _reading(
        "unclear",
        "Its terms bar mirroring avature.net's own content. They do not mention employers' career sites.",
        "https://www.avature.net/terms-of-use/",
    ),
    "jibe": _reading(
        "unclear",
        "iCIMS's terms bar robots on icims.com and its subdomains. "
        "They do not mention employers' own career sites, which is where ACE reads.",
        "https://www.icims.com/legal/terms-of-use/",
    ),
    "feed": _reading(
        "unclear",
        "GitHub's policy limits scraping, and ACE reads one public file there. "
        "RippleMatch's terms could not be found.",
        "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies",
    ),
}
