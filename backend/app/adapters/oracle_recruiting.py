"""Oracle Recruiting Cloud: employer boards on Oracle's HCM cloud.

Found by the 2026-10-04 audit of where passing roles came from. Fifteen
employers whose roles reached ACE only through the Simplify feed hire
through Oracle Recruiting -- American Express, JPMorgan Chase, Oracle,
BNY, Dell, Honeywell, Fortinet, Cummins, Emerson among them -- and their
posting pages render in the browser, so not even the employer-page
check could read them.

Every Oracle tenant's candidate site calls the same public REST API:

    GET /hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?finder=findReqs;siteNumber={site},limit=200,offset={n}
    GET /hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
        ?finder=ById;Id="{id}",siteNumber={site}

The source account is ``{host}/{site}``: the tenant's host and the
career site's number, both visible in any posting URL.

The listing gives titles and locations; the description needs one
request per posting. Like the Workday adapter, descriptions are fetched
only for titles the gate could pass, and -- unlike it -- kept between
polls in the shared reading store, so a posting's description is
fetched once a week rather than on every poll.

A snapshot is authoritative, so a tenant that does not finish inside
its page budget raises rather than return part of itself.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from datetime import (
    datetime,
    timezone,
)
from typing import Any

import httpx

from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import (
    READ,
    UNREACHABLE,
    Reading,
    ReadingStore,
    _flatten,
    is_stale,
)


SOURCE = "oracle_recruiting"

PAGE_SIZE = 200

# 100 pages is 20,000 postings; JPMorgan Chase, the largest seen, had
# 7,353.
MAX_PAGES = 100

# New descriptions fetched per poll. The rest come on later polls.
FRESH_DETAILS_PER_POLL = 150

CONCURRENCY = 4

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

API = "/hcmRestApi/resources/latest"


class IncompleteOracleRead(RuntimeError):
    """A tenant did not finish inside its page budget."""


def parse_source_account(
    source_account: str,
) -> tuple[str, str]:
    """``{host}/{site}`` as its two parts."""

    host, _, site = source_account.strip().strip(
        "/"
    ).partition(
        "/"
    )

    if not host or not site or "/" in site:
        raise ValueError(
            (
                "An Oracle Recruiting source account is "
                f"'host/siteNumber'; got {source_account!r}."
            )
        )

    return host, site


def posting_url(
    host: str,
    site: str,
    requisition_id: str,
) -> str:
    return (
        f"https://{host}/hcmUI/CandidateExperience/en/sites/"
        f"{site}/job/{requisition_id}"
    )


def build_location(
    requisition: dict[str, Any],
) -> str:
    """The primary location, then any others, separated by "; "."""

    places: list[str] = []

    primary = str(
        requisition.get(
            "PrimaryLocation"
        )
        or ""
    ).strip()

    if primary:
        places.append(
            primary
        )

    for other in requisition.get(
        "secondaryLocations"
    ) or []:
        if not isinstance(
            other,
            dict,
        ):
            continue

        name = str(
            other.get("Name")
            or ""
        ).strip()

        if name and name not in places:
            places.append(
                name
            )

    return "; ".join(
        places
    )


def build_description(
    detail: dict[str, Any],
) -> str:
    """Description, responsibilities and qualifications, as text.

    Oracle splits a posting across three fields, and the minimum
    qualifications -- years, degree, clearance, citizenship -- are
    usually in the last.
    """

    return "\n\n".join(
        text
        for text in (
            _flatten(
                str(
                    detail.get(field)
                    or ""
                )
            )
            for field in (
                "ExternalDescriptionStr",
                "ExternalResponsibilitiesStr",
                "ExternalQualificationsStr",
            )
        )
        if text
    )


def _posted_at(
    value: Any,
) -> datetime | None:
    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def fetch_oracle_recruiting_jobs(
    *,
    source_account: str,
    company_name: str,
    should_fetch_detail: (
        Callable[[str], bool] | None
    ) = None,
    store: ReadingStore | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(
        timezone.utc
    ),
    max_pages: int = MAX_PAGES,
    fresh_details: int = FRESH_DETAILS_PER_POLL,
) -> list[CanonicalJob]:
    """Read every posting on one Oracle Recruiting career site."""

    host, site = parse_source_account(
        source_account
    )

    store = store or ReadingStore()

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

    try:
        requisitions = _list_all(
            http,
            host=host,
            site=site,
            max_pages=max_pages,
            source_account=source_account,
        )

        urls = {
            str(requisition["Id"]): posting_url(
                host,
                site,
                str(requisition["Id"]),
            )
            for requisition in requisitions
        }

        wanted = [
            requisition_id
            for requisition_id, requisition in (
                (str(item["Id"]), item)
                for item in requisitions
            )
            if should_fetch_detail is None
            or should_fetch_detail(
                str(
                    requisition.get("Title")
                    or ""
                )
            )
        ]

        moment = now()

        stored = store.load(
            [
                urls[requisition_id]
                for requisition_id in wanted
            ]
        )

        descriptions: dict[str, str] = {
            url: reading.description
            for url, (reading, _checked) in stored.items()
            if reading.status == READ and reading.description
        }

        due = [
            requisition_id
            for requisition_id in wanted
            if urls[requisition_id] not in stored
            or is_stale(
                *stored[urls[requisition_id]],
                moment,
            )
        ][
            :fresh_details
        ]

        if due:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=CONCURRENCY,
            ) as pool:
                fresh = dict(
                    zip(
                        due,
                        pool.map(
                            lambda requisition_id: _detail(
                                http,
                                host=host,
                                site=site,
                                requisition_id=requisition_id,
                            ),
                            due,
                        ),
                    )
                )

            readings = {
                urls[requisition_id]: reading
                for requisition_id, reading in fresh.items()
            }

            store.save(
                readings,
                moment=moment,
            )

            for url, reading in readings.items():
                if reading.status == READ and reading.description:
                    descriptions[url] = reading.description

    finally:
        if owns_client:
            http.close()

    jobs: list[CanonicalJob] = []

    for requisition in requisitions:
        requisition_id = str(
            requisition["Id"]
        )

        title = str(
            requisition.get("Title")
            or ""
        ).strip()

        if not title:
            continue

        url = urls[requisition_id]

        jobs.append(
            CanonicalJob(
                source=SOURCE,
                company=company_name,
                external_id=requisition_id,
                requisition_id=requisition_id,
                title=title,
                location=build_location(
                    requisition
                ),
                description=descriptions.get(
                    url,
                    "",
                ),
                official_url=url,
                posted_at=_posted_at(
                    requisition.get(
                        "PostedDate"
                    )
                ),
            )
        )

    return jobs


def _list_all(
    http: httpx.Client,
    *,
    host: str,
    site: str,
    max_pages: int,
    source_account: str,
) -> list[dict[str, Any]]:
    requisitions: list[dict[str, Any]] = []

    seen: set[str] = set()

    offset = 0

    for _ in range(
        max_pages
    ):
        response = request_with_retry(
            lambda offset=offset: http.get(
                f"https://{host}{API}/recruitingCEJobRequisitions",
                params={
                    "onlyData": "true",
                    "expand": (
                        "requisitionList.secondaryLocations"
                    ),
                    "finder": (
                        f"findReqs;siteNumber={site},"
                        f"limit={PAGE_SIZE},offset={offset},"
                        "sortBy=POSTING_DATES_DESC"
                    ),
                },
            )
        )

        response.raise_for_status()

        items = response.json().get(
            "items"
        ) or []

        if not items:
            break

        search = items[0]

        page = search.get(
            "requisitionList"
        ) or []

        for requisition in page:
            if not isinstance(
                requisition,
                dict,
            ) or not requisition.get("Id"):
                continue

            requisition_id = str(
                requisition["Id"]
            )

            if requisition_id in seen:
                continue

            seen.add(
                requisition_id
            )

            requisitions.append(
                requisition
            )

        offset += len(
            page
        )

        total = search.get(
            "TotalJobsCount"
        )

        if len(
            page
        ) < PAGE_SIZE or (
            isinstance(
                total,
                int,
            )
            and offset >= total
        ):
            return requisitions

    raise IncompleteOracleRead(
        (
            f"{source_account} did not finish in {max_pages} "
            "pages; refusing to treat part of it as the whole."
        )
    )


def _detail(
    http: httpx.Client,
    *,
    host: str,
    site: str,
    requisition_id: str,
) -> Reading:
    try:
        response = request_with_retry(
            lambda: http.get(
                f"https://{host}{API}"
                "/recruitingCEJobRequisitionDetails",
                params={
                    "expand": "all",
                    "onlyData": "true",
                    "finder": (
                        f'ById;Id="{requisition_id}",'
                        f"siteNumber={site}"
                    ),
                },
            )
        )
    except httpx.HTTPError:
        return Reading(
            UNREACHABLE,
        )

    if response.status_code != 200:
        return Reading(
            UNREACHABLE,
        )

    items = response.json().get(
        "items"
    ) or []

    if not items or not isinstance(
        items[0],
        dict,
    ):
        return Reading(
            UNREACHABLE,
        )

    description = build_description(
        items[0]
    )

    if not description:
        return Reading(
            UNREACHABLE,
        )

    return Reading(
        READ,
        description,
    )
