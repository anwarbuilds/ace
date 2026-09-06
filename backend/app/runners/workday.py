"""Composition for Workday source fetching.

The detail-fetch predicate lives in the shared prefilter module, since
SmartRecruiters needs the same behaviour for the same reason.
"""

from backend.app.runners.clock import (
    Clock,
    utc_now,
)
from backend.app.runners.prefilter import (
    build_detail_predicate,
)


__all__ = [
    "Clock",
    "build_detail_predicate",
    "utc_now",
]
