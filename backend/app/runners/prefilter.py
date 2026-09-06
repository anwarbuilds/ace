"""Shared detail-fetch prefilter for ACE adapters.

Several providers return a cheap list of postings and require a separate
request per posting for the description. On a large employer that is the
dominant cost: one SmartRecruiters source spent 949 seconds fetching
1,631 descriptions one at a time.

Most of those descriptions are never needed, because the posting is
rejected on its title alone. This module supplies the predicate that
decides, and it asks the *real* eligibility gate rather than
reimplementing a second heuristic that could drift away from it.

Only title rules can be applied at list time: providers commonly report
list-level location vaguely ("2 Locations") or not at all. The probe
therefore uses a deliberately permissive location so geography never
causes a skip.
"""

from collections.abc import Callable

from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob


# A location that always passes the geography rule, so the probe tests
# title rules alone.
PROBE_LOCATION = "United States"


def build_detail_predicate(
    *,
    source: str,
    company_name: str,
) -> Callable[[str], bool]:
    """Return a predicate deciding whether a posting's detail is worth fetching.

    A posting is skipped only when the gate already rejects it on its
    title, so skipping cannot change an outcome: the shallow record is
    rejected downstream for exactly the same reason.
    """

    def should_fetch_detail(
        title: str,
    ) -> bool:
        if not title.strip():
            return False

        probe = CanonicalJob(
            source=source,
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
