"""Composition for Workday source fetching.

The detail-fetch predicate lives in the shared prefilter module, since
SmartRecruiters needs the same behaviour for the same reason.
"""

from datetime import (
    datetime,
    timezone,
)

from backend.app.runners.prefilter import (
    build_detail_predicate,
)


__all__ = [
    "build_detail_predicate",
    "utc_now",
]


def utc_now() -> datetime:
    """Return the current UTC instant."""

    return datetime.now(
        timezone.utc
    )
