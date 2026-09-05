"""Tests for ACE digest delivery semantics.

These tests use an in-memory store so window, retry, and dead-letter
behavior can be exercised without a database.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.app.notifications.digest_delivery import (
    DigestAttemptResult,
    DigestCandidateRow,
    DigestOutcome,
    LockedDigest,
    build_digest_items,
    deliver_digest_once,
)
from backend.app.notifications.schedule import (
    DigestWindowSchedule,
    parse_digest_times,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


RECIPIENT = "user@example.com"


SCHEDULE = DigestWindowSchedule(
    timezone_name="UTC",
    times=parse_digest_times(
        "08:00,18:00"
    ),
)


MORNING = datetime(
    2026,
    9,
    5,
    9,
    0,
    tzinfo=timezone.utc,
)


EVENING = datetime(
    2026,
    9,
    5,
    19,
    0,
    tzinfo=timezone.utc,
)


BEFORE_FIRST_WINDOW = datetime(
    2026,
    9,
    5,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_row(
    row_id: int,
    *,
    title: str = "Software Engineer",
    company: str = "Example Co",
    url: str | None = None,
) -> DigestCandidateRow:
    """Build one assigned outbox row with a structured payload."""

    return DigestCandidateRow(
        id=row_id,
        subject=(
            f"[ACE] NEW | PRIMARY | "
            f"{title} | {company}"
        ),
        observation_status="NEW",
        source_account="example",
        external_id=str(
            row_id
        ),
        payload={
            "version": 1,
            "title": title,
            "company": company,
            "location": "Seattle, WA",
            "official_url": (
                url
                if url is not None
                else (
                    "https://boards.example.com"
                    f"/jobs/{row_id}"
                )
            ),
            "observation_status": "NEW",
            "eligibility_status": "PASS",
            "role_family": (
                "SOFTWARE_ENGINEERING"
            ),
            "role_priority": "PRIMARY",
            "reasons": [
                "No hard eligibility "
                "blocker detected.",
            ],
            "posted_at": "2026-09-04T12:00:00+00:00",
            "posting_age_days": 1,
        },
    )


class FakeStore:
    """In-memory digest store."""

    def __init__(
        self,
        *,
        unassigned: list[
            DigestCandidateRow
        ] | None = None,
    ) -> None:
        self.unassigned = list(
            unassigned or []
        )

        self.digests: dict[
            str,
            dict,
        ] = {}

        self.assigned: dict[
            int,
            list[
                DigestCandidateRow
            ],
        ] = {}

        self.next_id = 1

        self.lock_returns_none = False

        self.sent_calls: list[dict] = []

        self.failed_calls: list[dict] = []

        self.discarded: list[int] = []

    def get_or_create_digest(
        self,
        *,
        window,
        recipient: str,
    ) -> int:
        key = window.digest_key(
            recipient=recipient
        )

        if key not in self.digests:
            self.digests[key] = {
                "id": self.next_id,
                "status": "PENDING",
                "item_count": 0,
                "attempt_count": 0,
                "next_attempt_at": (
                    window.opens_at
                ),
            }

            self.assigned[
                self.next_id
            ] = []

            self.next_id += 1

        return self.digests[key][
            "id"
        ]

    def _record(
        self,
        digest_id: int,
    ) -> dict:
        for entry in (
            self.digests.values()
        ):
            if entry["id"] == digest_id:
                return entry

        raise AssertionError(
            "unknown digest id"
        )

    def lock_digest(
        self,
        *,
        digest_id: int,
    ) -> LockedDigest | None:
        if self.lock_returns_none:
            return None

        entry = self._record(
            digest_id
        )

        return LockedDigest(
            id=digest_id,
            status=entry["status"],
            item_count=entry[
                "item_count"
            ],
            attempt_count=entry[
                "attempt_count"
            ],
            next_attempt_at=entry[
                "next_attempt_at"
            ],
        )

    def assign_pending_candidates(
        self,
        *,
        digest_id: int,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> int:
        taken = self.unassigned[
            :limit
        ]

        self.unassigned = (
            self.unassigned[
                limit:
            ]
        )

        self.assigned[
            digest_id
        ].extend(
            taken
        )

        self._record(
            digest_id
        )["item_count"] = len(
            self.assigned[
                digest_id
            ]
        )

        return len(
            taken
        )

    def count_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
    ) -> int:
        return len(
            self.unassigned
        )

    def load_digest_candidates(
        self,
        *,
        digest_id: int,
    ) -> list[
        DigestCandidateRow
    ]:
        return list(
            self.assigned[
                digest_id
            ]
        )

    def load_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> list[
        DigestCandidateRow
    ]:
        return self.unassigned[
            :limit
        ]

    def discard_empty_digest(
        self,
        *,
        digest_id: int,
    ) -> None:
        self.discarded.append(
            digest_id
        )

        for key, entry in list(
            self.digests.items()
        ):
            if entry["id"] == digest_id:
                del self.digests[key]

    def mark_digest_sent(
        self,
        *,
        digest_id: int,
        subject: str,
        item_count: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        entry = self._record(
            digest_id
        )

        entry["status"] = "SENT"

        entry["attempt_count"] = (
            attempt_count
        )

        self.sent_calls.append(
            {
                "digest_id": digest_id,
                "subject": subject,
                "item_count": item_count,
                "attempt_count": (
                    attempt_count
                ),
            }
        )

    def mark_digest_failed(
        self,
        *,
        digest_id: int,
        attempt_count: int,
        attempted_at: datetime,
        next_attempt_at: datetime,
        error: str,
        dead: bool,
    ) -> None:
        entry = self._record(
            digest_id
        )

        entry["status"] = (
            "DEAD"
            if dead
            else "PENDING"
        )

        entry["attempt_count"] = (
            attempt_count
        )

        entry["next_attempt_at"] = (
            next_attempt_at
        )

        self.failed_calls.append(
            {
                "digest_id": digest_id,
                "attempt_count": (
                    attempt_count
                ),
                "next_attempt_at": (
                    next_attempt_at
                ),
                "error": error,
                "dead": dead,
            }
        )


class FakeTransport:
    """Controllable digest transport."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error

        self.messages: list[
            tuple[
                NotificationMessage,
                str,
            ]
        ] = []

    def send(
        self,
        message: NotificationMessage,
        *,
        recipient: str,
    ) -> None:
        self.messages.append(
            (
                message,
                recipient,
            )
        )

        if self.error is not None:
            raise self.error


def run(
    store: FakeStore,
    transport: FakeTransport,
    *,
    now: datetime = MORNING,
    max_jobs: int = 100,
    max_attempts: int = 5,
) -> DigestAttemptResult:
    """Attempt one digest delivery."""

    return deliver_digest_once(
        store,
        transport,
        now=now,
        schedule=SCHEDULE,
        recipient=RECIPIENT,
        max_jobs=max_jobs,
        max_attempts=max_attempts,
    )


# ----------------------------------------------------------------------
# Grouping: many candidates become one email
# ----------------------------------------------------------------------


def test_many_candidates_become_one_message() -> None:
    """Seven qualifying jobs must produce exactly one SMTP send."""

    store = FakeStore(
        unassigned=[
            make_row(
                index,
                title=(
                    f"Engineer {index}"
                ),
            )
            for index in range(
                1,
                8,
            )
        ]
    )

    transport = FakeTransport()

    result = run(
        store,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.SENT
    )

    assert len(
        transport.messages
    ) == 1

    assert result.item_count == 7

    message, recipient = (
        transport.messages[0]
    )

    assert recipient == RECIPIENT

    assert (
        "7 new matches"
        in message.subject
    )

    for index in range(
        1,
        8,
    ):
        assert (
            f"Engineer {index}"
            in message.text_body
        )


def test_single_candidate_becomes_one_digest() -> None:
    """One job still uses the digest path, with singular wording."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport()

    result = run(
        store,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.SENT
    )

    assert result.item_count == 1

    assert (
        "1 new match"
        in transport.messages[0][
            0
        ].subject
    )


def test_zero_candidates_sends_nothing() -> None:
    """No qualifying jobs must mean no email at all."""

    store = FakeStore(
        unassigned=[]
    )

    transport = FakeTransport()

    result = run(
        store,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.NOTHING_TO_SEND
    )

    assert transport.messages == []

    # The empty window is released so a later job can still use it.
    assert store.discarded


def test_digest_links_point_to_official_urls() -> None:
    """The apply link must be the employer's own posting."""

    store = FakeStore(
        unassigned=[
            make_row(
                1,
                url=(
                    "https://jobs.acme.com"
                    "/careers/42"
                ),
            ),
        ]
    )

    transport = FakeTransport()

    run(
        store,
        transport,
    )

    assert (
        "https://jobs.acme.com/careers/42"
        in transport.messages[0][
            0
        ].text_body
    )


# ----------------------------------------------------------------------
# Window discipline
# ----------------------------------------------------------------------


def test_no_send_outside_a_window() -> None:
    """Before the first configured window nothing is deliverable."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport()

    result = run(
        store,
        transport,
        now=BEFORE_FIRST_WINDOW,
    )

    assert (
        result.outcome
        is DigestOutcome.NO_OPEN_WINDOW
    )

    assert transport.messages == []


def test_second_attempt_in_same_window_sends_nothing() -> None:
    """A restart must not resend an already-delivered window."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport()

    first = run(
        store,
        transport,
    )

    assert (
        first.outcome
        is DigestOutcome.SENT
    )

    # Simulate a worker restart later in the same window.
    second = run(
        store,
        transport,
        now=MORNING
        + timedelta(
            hours=3
        ),
    )

    assert (
        second.outcome
        is DigestOutcome.ALREADY_DELIVERED
    )

    assert len(
        transport.messages
    ) == 1


def test_two_windows_produce_at_most_two_sends_per_day() -> None:
    """Morning and evening each deliver once; repeats are refused."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport()

    assert (
        run(
            store,
            transport,
            now=MORNING,
        ).outcome
        is DigestOutcome.SENT
    )

    store.unassigned.append(
        make_row(
            2
        )
    )

    assert (
        run(
            store,
            transport,
            now=EVENING,
        ).outcome
        is DigestOutcome.SENT
    )

    # Any further attempt inside either window sends nothing.
    for instant in (
        MORNING
        + timedelta(
            hours=1
        ),
        EVENING
        + timedelta(
            hours=1
        ),
    ):
        assert (
            run(
                store,
                transport,
                now=instant,
            ).outcome
            is DigestOutcome
            .ALREADY_DELIVERED
        )

    assert len(
        transport.messages
    ) == 2


def test_rows_created_after_morning_go_to_evening() -> None:
    """Candidates arriving post-digest wait for the next window."""

    store = FakeStore(
        unassigned=[
            make_row(
                1,
                title="Morning Role",
            ),
        ]
    )

    transport = FakeTransport()

    run(
        store,
        transport,
        now=MORNING,
    )

    store.unassigned.append(
        make_row(
            2,
            title="Afternoon Role",
        )
    )

    run(
        store,
        transport,
        now=EVENING,
    )

    morning_body = (
        transport.messages[0][
            0
        ].text_body
    )

    evening_body = (
        transport.messages[1][
            0
        ].text_body
    )

    assert (
        "Morning Role"
        in morning_body
    )

    assert (
        "Afternoon Role"
        not in morning_body
    )

    assert (
        "Afternoon Role"
        in evening_body
    )

    assert (
        "Morning Role"
        not in evening_body
    )


def test_no_duplicate_inclusion_across_windows() -> None:
    """A delivered candidate never appears in a second digest."""

    store = FakeStore(
        unassigned=[
            make_row(
                1,
                title="Only Once",
            ),
        ]
    )

    transport = FakeTransport()

    run(
        store,
        transport,
        now=MORNING,
    )

    store.unassigned.append(
        make_row(
            2,
            title="Second Role",
        )
    )

    run(
        store,
        transport,
        now=EVENING,
    )

    assert (
        transport.messages[1][
            0
        ].text_body.count(
            "Only Once"
        )
        == 0
    )


# ----------------------------------------------------------------------
# Failure handling
# ----------------------------------------------------------------------


def test_failed_digest_schedules_a_retry() -> None:
    """A transport error leaves the window retryable, not lost."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport(
        error=RuntimeError(
            "smtp unavailable"
        )
    )

    result = run(
        store,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.RETRY_SCHEDULED
    )

    assert (
        store.failed_calls[0]["dead"]
        is False
    )

    assert (
        store.failed_calls[0][
            "next_attempt_at"
        ]
        > MORNING
    )

    assert store.sent_calls == []


def test_retry_before_backoff_elapses_is_skipped() -> None:
    """Backoff is honored rather than hammering a broken transport."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport(
        error=RuntimeError(
            "smtp down"
        )
    )

    run(
        store,
        transport,
    )

    result = run(
        store,
        transport,
        now=MORNING
        + timedelta(
            seconds=5
        ),
    )

    assert (
        result.outcome
        is DigestOutcome.RETRY_NOT_DUE
    )

    assert len(
        transport.messages
    ) == 1


def test_retry_resends_the_same_frozen_candidates() -> None:
    """A retry must not absorb rows that arrived meanwhile."""

    store = FakeStore(
        unassigned=[
            make_row(
                1,
                title="Original",
            ),
        ]
    )

    failing = FakeTransport(
        error=RuntimeError(
            "smtp down"
        )
    )

    run(
        store,
        failing,
    )

    store.unassigned.append(
        make_row(
            2,
            title="Arrived Later",
        )
    )

    working = FakeTransport()

    result = run(
        store,
        working,
        now=MORNING
        + timedelta(
            hours=1
        ),
    )

    assert (
        result.outcome
        is DigestOutcome.SENT
    )

    body = working.messages[0][
        0
    ].text_body

    assert "Original" in body

    assert (
        "Arrived Later"
        not in body
    )


def test_repeated_failure_becomes_dead() -> None:
    """Exhausted attempts land in a visible terminal state."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport(
        error=RuntimeError(
            "smtp broken"
        )
    )

    result = run(
        store,
        transport,
        max_attempts=1,
    )

    assert (
        result.outcome
        is DigestOutcome.DEAD
    )

    assert (
        store.failed_calls[0]["dead"]
        is True
    )


def test_dead_window_is_not_retried() -> None:
    """An abandoned window stops consuming attempts."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    transport = FakeTransport(
        error=RuntimeError(
            "smtp broken"
        )
    )

    run(
        store,
        transport,
        max_attempts=1,
    )

    result = run(
        store,
        transport,
        now=MORNING
        + timedelta(
            hours=2
        ),
    )

    assert (
        result.outcome
        is DigestOutcome.WINDOW_ABANDONED
    )

    assert len(
        transport.messages
    ) == 1


def test_concurrent_worker_does_not_double_send() -> None:
    """A locked digest is skipped rather than delivered twice."""

    store = FakeStore(
        unassigned=[
            make_row(
                1
            ),
        ]
    )

    store.lock_returns_none = True

    transport = FakeTransport()

    result = run(
        store,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.CONCURRENT_WORKER
    )

    assert transport.messages == []


# ----------------------------------------------------------------------
# Size limits
# ----------------------------------------------------------------------


def test_digest_size_limit_defers_the_remainder() -> None:
    """An oversized backlog is split rather than clipped by Gmail."""

    store = FakeStore(
        unassigned=[
            make_row(
                index,
                title=f"Role {index}",
            )
            for index in range(
                1,
                11,
            )
        ]
    )

    transport = FakeTransport()

    result = run(
        store,
        transport,
        max_jobs=4,
    )

    assert result.item_count == 4

    assert result.deferred_count == 6

    assert (
        "6 additional matches"
        in transport.messages[0][
            0
        ].text_body
    )


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_empty_recipient_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        deliver_digest_once(
            FakeStore(),
            FakeTransport(),
            now=MORNING,
            schedule=SCHEDULE,
            recipient="   ",
        )


def test_non_positive_max_jobs_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        deliver_digest_once(
            FakeStore(),
            FakeTransport(),
            now=MORNING,
            schedule=SCHEDULE,
            recipient=RECIPIENT,
            max_jobs=0,
        )


def test_naive_now_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        deliver_digest_once(
            FakeStore(),
            FakeTransport(),
            now=datetime(
                2026,
                9,
                5,
                9,
            ),
            schedule=SCHEDULE,
            recipient=RECIPIENT,
        )


# ----------------------------------------------------------------------
# Legacy rows
# ----------------------------------------------------------------------


def test_legacy_rows_without_payload_still_render() -> None:
    """Pre-digest outbox rows must not be silently undeliverable."""

    legacy = DigestCandidateRow(
        id=99,
        subject=(
            "[ACE] NEW | PRIMARY | "
            "Backend Engineer | Acme"
        ),
        observation_status="NEW",
        source_account="acme",
        external_id="7",
        payload=None,
    )

    items = build_digest_items(
        [
            legacy,
        ]
    )

    assert len(items) == 1

    assert (
        items[0].title
        == "Backend Engineer"
    )

    assert items[0].company == "Acme"
