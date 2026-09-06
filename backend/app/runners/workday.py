"""Composition for Workday source fetching.

The adapter deliberately knows nothing about eligibility. This module
supplies the predicate that decides whether a posting's description is
worth fetching, and it does so by asking the real gate rather than by
reimplementing a second, drifting heuristic.

Only title-based rules can be applied at list time: Workday reports
list-level location as prose such as "2 Locations", which cannot be
evaluated. The probe therefore uses a deliberately permissive location
so that geography never causes a skip.
"""

from datetime import (
    datetime,
    timezone,
)

from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob


# A location that always passes the geography rule, so the probe tests
# title rules alone.
PROBE_LOCATION = "United States"


def utc_now() -> datetime:
    """Return the current UTC instant."""

    return datetime.now(
        timezone.utc
    )


def build_detail_predicate(
    *,
    company_name: str,
):
    """Return a predicate deciding whether to fetch a job's detail.

    A posting is skipped only when ACE's gate already rejects it on its
    title alone, so skipping can never change an outcome: the shallow
    record is rejected downstream for exactly the same reason.
    """

    def should_fetch_detail(
        title: str,
    ) -> bool:
        probe = CanonicalJob(
            source="workday",
            company=company_name,
            external_id="probe",
            title=title,
            location=PROBE_LOCATION,
            description="",
            official_url=(
                "https://example.invalid/probe"
            ),
        )

        return (
            evaluate_job(
                probe
            ).status
            is not EligibilityStatus.REJECT
        )

    return should_fetch_detail
