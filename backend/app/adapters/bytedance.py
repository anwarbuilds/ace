"""ByteDance and TikTok: their own careers sites, read directly.

Found by the 2026-10-04 audit of where passing roles came from. 139 of
them -- 106 TikTok, 33 ByteDance, nearly all new-graduate engineering --
reached ACE only through the Simplify feed, hours or days after they
opened. ACE had a "ByteDance" source, but it was a SmartRecruiters board
holding two postings; neither company's real board was read at all.

Both careers sites are front ends to one public job API, ByteDance's
"supplier" endpoint, which each site's own pages call:

    POST {api}/search/job/posts   {"keyword": "", "limit": 200, ...}

with a ``website-path`` header naming the portal. robots.txt on both
sites disallows only referral pages; the API host for TikTok publishes
no rules at all.

Every posting worldwide is read -- 4,291 for TikTok and 1,417 for
ByteDance on 2026-10-04, at 200 a page, so about thirty requests a poll.
The API's location filter does not take a country, and the eligibility
gate is where location is judged anyway. A portal that does not finish
inside its page budget raises rather than return part of itself, since
a snapshot is authoritative and whatever it lacks is closed.

The apply link is each company's own posting page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import CanonicalJob


SOURCE = "bytedance"

PAGE_SIZE = 200

# 200 pages is 40,000 postings, ten times TikTok's whole board.
MAX_PAGES = 200

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


@dataclass(
    frozen=True,
    slots=True,
)
class Portal:
    """One careers site on the supplier API."""

    api: str

    website_path: str

    job_url: str


# Keyed by source account.
PORTALS = {
    "tiktok": Portal(
        api=(
            "https://api.lifeattiktok.com"
            "/api/v1/public/supplier"
        ),
        website_path="tiktok",
        job_url="https://lifeattiktok.com/search/{id}",
    ),
    "bytedance": Portal(
        api=(
            "https://jobs.bytedance.com"
            "/api/v1/public/supplier"
        ),
        website_path="en",
        job_url=(
            "https://jobs.bytedance.com"
            "/en/position/{id}/detail"
        ),
    ),
}


class IncompleteByteDanceRead(RuntimeError):
    """A portal did not finish inside its page budget."""


def _name(
    node: Any,
) -> str:
    if not isinstance(
        node,
        dict,
    ):
        return ""

    return str(
        node.get("en_name")
        or node.get("i18n_name")
        or node.get("name")
        or ""
    ).strip()


def build_location(
    city_info: Any,
) -> str:
    """City, region and country, most specific first.

    The API nests them as a chain of parents -- city, then state, then
    country -- so the chain is walked rather than assumed to be three
    deep. "United States of America" is kept as written: the gate reads
    "United States" inside it.
    """

    parts: list[str] = []

    node = city_info

    seen = 0

    while isinstance(
        node,
        dict,
    ) and seen < 6:
        name = _name(
            node
        )

        if name and name not in parts:
            parts.append(
                name
            )

        node = node.get(
            "parent"
        )

        seen += 1

    return ", ".join(
        parts
    )


def build_description(
    posting: dict,
) -> str:
    """The role description and its stated requirements, together.

    The minimum qualifications -- years of experience, degree, work
    authorisation -- are in ``requirement``, which is what the gate's
    phrase rules have to read.
    """

    return "\n\n".join(
        part
        for part in (
            str(
                posting.get(
                    "description"
                )
                or ""
            ).strip(),
            str(
                posting.get(
                    "requirement"
                )
                or ""
            ).strip(),
        )
        if part
    )


def _employment_type(
    recruit_type: str,
) -> str | None:
    """The posting's recruit type, as the gate reads employment.

    A "third-party associate" is employed by a staffing vendor and
    placed at the company -- not a hire by the company, and so not one
    that can sponsor. It is written as a contract role, which the gate
    already rejects for exactly that reason.
    """

    kind = recruit_type.strip().lower()

    if not kind:
        return None

    if "third-party" in kind or "third party" in kind:
        return f"contract ({kind})"

    return kind


def parse_posting(
    posting: Any,
    *,
    portal: Portal,
    company_name: str,
) -> CanonicalJob | None:
    """One API posting as a canonical job, or None to skip it."""

    if not isinstance(
        posting,
        dict,
    ):
        return None

    job_id = str(
        posting.get(
            "id"
        )
        or ""
    ).strip()

    title = str(
        posting.get(
            "title"
        )
        or ""
    ).strip()

    if not job_id or not title:
        return None

    recruit_type = _name(
        posting.get(
            "recruit_type"
        )
    )

    return CanonicalJob(
        source=SOURCE,
        company=company_name,
        external_id=job_id,
        requisition_id=(
            str(
                posting.get(
                    "code"
                )
                or ""
            ).strip()
            or None
        ),
        title=title,
        location=build_location(
            posting.get(
                "city_info"
            )
        ),
        description=build_description(
            posting
        ),
        official_url=portal.job_url.format(
            id=job_id,
        ),
        employment_type=_employment_type(
            recruit_type
        ),
    )


def fetch_bytedance_jobs(
    *,
    source_account: str,
    company_name: str,
    client: httpx.Client | None = None,
    max_pages: int = MAX_PAGES,
) -> list[CanonicalJob]:
    """Read every posting on one supplier-API portal."""

    portal = PORTALS.get(
        source_account
    )

    if portal is None:
        raise ValueError(
            (
                f"Unknown ByteDance portal {source_account!r}; "
                f"known: {sorted(PORTALS)}."
            )
        )

    owns_client = client is None

    http = (
        client
        if client is not None
        else httpx.Client(
            timeout=TIMEOUT_SECONDS,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
    )

    jobs: list[CanonicalJob] = []

    seen: set[str] = set()

    offset = 0

    try:
        for _ in range(
            max_pages
        ):
            response = request_with_retry(
                lambda offset=offset: http.post(
                    f"{portal.api}/search/job/posts",
                    json={
                        "recruitment_id_list": [],
                        "job_category_id_list": [],
                        "subject_id_list": [],
                        "location_code_list": [],
                        "keyword": "",
                        "limit": PAGE_SIZE,
                        "offset": offset,
                    },
                    headers={
                        "website-path": (
                            portal.website_path
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                    },
                )
            )

            response.raise_for_status()

            body = response.json()

            if body.get(
                "code"
            ) not in (
                0,
                None,
            ):
                raise RuntimeError(
                    (
                        f"{source_account} job API answered "
                        f"code {body.get('code')!r}: "
                        f"{body.get('message')!r}"
                    )
                )

            data = body.get(
                "data"
            ) or {}

            postings = data.get(
                "job_post_list"
            ) or []

            if not isinstance(
                postings,
                list,
            ) or not postings:
                break

            for posting in postings:
                job = parse_posting(
                    posting,
                    portal=portal,
                    company_name=company_name,
                )

                if (
                    job is None
                    or job.external_id in seen
                ):
                    continue

                seen.add(
                    job.external_id
                )

                jobs.append(
                    job
                )

            offset += len(
                postings
            )

            total = data.get(
                "count"
            )

            if len(
                postings
            ) < PAGE_SIZE or (
                isinstance(
                    total,
                    int,
                )
                and offset >= total
            ):
                break

        else:
            raise IncompleteByteDanceRead(
                (
                    f"{source_account} did not finish in "
                    f"{max_pages} pages; refusing to treat "
                    "part of it as the whole."
                )
            )

    finally:
        if owns_client:
            http.close()

    return jobs
