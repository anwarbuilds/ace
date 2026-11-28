"""Descriptions for boards that list first and describe each posting on its own (DIS-09).

BambooHR and Rippling, like Workable, answer a list of a board's postings in
one request and each posting's description in another. A description is
asked for only when the gate could pass the title, and kept in the shared
reading store, so each is fetched about once a week, not every poll.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import concurrent.futures
from datetime import datetime

from backend.app.verification.employer_page import READ, Reading, ReadingStore, is_stale

FRESH_DETAILS_PER_POLL = 150

CONCURRENCY = 4


def descriptions(
    postings: Sequence[tuple[str, str]],
    fetch_detail: Callable[[str], Reading],
    *,
    should_fetch_detail: Callable[[str], bool] | None,
    store: ReadingStore,
    now: datetime,
    fresh_details: int = FRESH_DETAILS_PER_POLL,
) -> dict[str, str]:
    """Each wanted posting's description by its address.

    ``postings`` is (address, title) pairs; ``fetch_detail`` reads one address.
    """

    wanted = [url for url, title in postings if should_fetch_detail is None or should_fetch_detail(title)]
    stored = store.load(wanted)
    found = {
        url: reading.description
        for url, (reading, _checked) in stored.items()
        if reading.status == READ and reading.description
    }
    due = [url for url in wanted if url not in stored or is_stale(*stored[url], now)][:fresh_details]
    if due:
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            fresh = dict(zip(due, pool.map(fetch_detail, due)))
        store.save(fresh, moment=now)
        found.update({url: reading.description for url, reading in fresh.items() if reading.status == READ and reading.description})
    return found


__all__ = ["descriptions"]
