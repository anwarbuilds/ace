"""Ephemeral full-mailbox manifest. Imported evidence remains durable in SQL.

A restart discards the completeness claim and re-lists Gmail; already committed
messages need no second detail read. No schema or scheduler change is needed.
"""
from collections import deque
from dataclasses import dataclass, field


@dataclass
class FullMailboxScan:
    baseline: str
    phase: str = "listing"
    ids: set[str] = field(default_factory=set)
    pending: deque[str] = field(default_factory=deque)
    unavailable: set[str] = field(default_factory=set)
    page: str | None = None
    seen_pages: set[str] = field(default_factory=set)
    history_page: str | None = None
    seen_history_pages: set[str] = field(default_factory=set)
    snapshot_at: str | None = None
    snapshot: str | None = None
    live: bool = False
    live_ids: set[str] = field(default_factory=set)
    history_added: set[str] = field(default_factory=set)
    history_dirty: bool = False
