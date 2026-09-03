"""Tests for ACE transactional single-source polling."""

from contextlib import (
    AbstractContextManager,
)
from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from typing import Any

import pytest

import backend.app.scheduling.service as service_module
from backend.app.notifications.outbox import (
    OutboxEnqueueResult,
)
from backend.app.scheduling.service import (
    poll_source_once,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
    SourceType,
)


DETECTED_AT = datetime(
    2026,
    9,
    2,
    23,
    45,
    tzinfo=timezone.utc,
)


def make_source() -> SourceDefinition:
    """Create one synthetic scheduled source."""

    return SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=(
            "databricks"
        ),
        company_name=(
            "Databricks"
        ),
    )


def make_snapshot(
    source: SourceDefinition,
) -> FetchedSourceSnapshot:
    """Create a provider-neutral empty fetched snapshot."""

    return FetchedSourceSnapshot(
        source_definition=source,
        detected_at=DETECTED_AT,
        jobs=(),
    )


def make_evaluation(
    *,
    alert_candidates: tuple[
        Any,
        ...,
    ] = (),
) -> SimpleNamespace:
    """Create the minimum evaluation shape required by the service."""

    return SimpleNamespace(
        alert_candidates=(
            alert_candidates
        ),
        evaluated_count=(
            len(
                alert_candidates
            )
        ),
        alert_candidate_count=(
            len(
                alert_candidates
            )
        ),
    )


def make_workflow_result(
    *,
    alert_candidates: tuple[
        Any,
        ...,
    ] = (),
) -> SimpleNamespace:
    """Create the minimum workflow result used by service tests."""

    return SimpleNamespace(
        evaluation=make_evaluation(
            alert_candidates=(
                alert_candidates
            )
        )
    )


class FakeFetcher:
    """Deterministic source fetcher recording execution order."""

    def __init__(
        self,
        *,
        snapshot: FetchedSourceSnapshot,
        events: list[str],
    ) -> None:
        self._snapshot = snapshot
        self._events = events

    def fetch(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        self._events.append(
            "fetch"
        )

        assert (
            source
            == self._snapshot
            .source_definition
        )

        return self._snapshot


class FakeTransaction(
    AbstractContextManager[
        object
    ]
):
    """Transaction context recording commit/rollback behavior."""

    def __init__(
        self,
        *,
        events: list[str],
    ) -> None:
        self._events = events
        self.session = object()

    def __enter__(
        self,
    ) -> object:
        self._events.append(
            "transaction_begin"
        )

        return self.session

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        if exc_type is None:
            self._events.append(
                "transaction_commit"
            )

        else:
            self._events.append(
                "transaction_rollback"
            )

        return False


class FakeTransactionFactory:
    """Factory returning deterministic transaction contexts."""

    def __init__(
        self,
        *,
        events: list[str],
    ) -> None:
        self._events = events

    def begin(
        self,
    ) -> FakeTransaction:
        return FakeTransaction(
            events=self._events
        )


def test_fetch_happens_before_database_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    fetcher = FakeFetcher(
        snapshot=snapshot,
        events=events,
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: events.append(
            "repository"
        )
        or object(),
    )

    def fake_workflow(
        repository,
        *,
        source,
        source_account,
        jobs,
        observed_at,
    ):
        del (
            repository,
            source,
            source_account,
            jobs,
            observed_at,
        )

        events.append(
            "workflow"
        )

        return make_workflow_result()

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        fake_workflow,
    )

    result = poll_source_once(
        source=source,
        fetcher=fetcher,
        transaction_factory=(
            FakeTransactionFactory(
                events=events
            )
        ),
        notification_recipient=None,
    )

    assert events == [
        "fetch",
        "transaction_begin",
        "repository",
        "workflow",
        "transaction_commit",
    ]

    assert (
        result.fetched_snapshot
        is snapshot
    )


def test_no_alert_candidates_do_not_require_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: object(),
    )

    workflow_result = (
        make_workflow_result()
    )

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        lambda *args, **kwargs: (
            workflow_result
        ),
    )

    def fail_if_outbox_created(
        _session,
    ):
        raise AssertionError(
            (
                "Outbox repository should "
                "not be created."
            )
        )

    monkeypatch.setattr(
        service_module,
        "SqlAlchemyNotificationOutboxRepository",
        fail_if_outbox_created,
    )

    result = poll_source_once(
        source=source,
        fetcher=FakeFetcher(
            snapshot=snapshot,
            events=events,
        ),
        transaction_factory=(
            FakeTransactionFactory(
                events=events
            )
        ),
        notification_recipient=None,
    )

    assert (
        result.outbox
        == OutboxEnqueueResult(
            candidate_count=0,
            queued_count=0,
            duplicate_count=0,
        )
    )


def test_alert_candidates_are_enqueued_inside_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    candidate = object()

    workflow_result = (
        make_workflow_result(
            alert_candidates=(
                candidate,
            )
        )
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: object(),
    )

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        lambda *args, **kwargs: (
            workflow_result
        ),
    )

    outbox_repository = object()

    monkeypatch.setattr(
        service_module,
        "SqlAlchemyNotificationOutboxRepository",
        lambda _session: (
            events.append(
                "outbox_repository"
            )
            or outbox_repository
        ),
    )

    observed: dict[
        str,
        Any,
    ] = {}

    def fake_enqueue(
        writer,
        *,
        candidates,
        source_account,
        recipient,
        detected_at,
    ) -> OutboxEnqueueResult:
        events.append(
            "enqueue"
        )

        observed.update(
            {
                "writer": writer,
                "candidates": candidates,
                "source_account": (
                    source_account
                ),
                "recipient": recipient,
                "detected_at": (
                    detected_at
                ),
            }
        )

        return OutboxEnqueueResult(
            candidate_count=1,
            queued_count=1,
            duplicate_count=0,
        )

    monkeypatch.setattr(
        service_module,
        "enqueue_alert_candidates",
        fake_enqueue,
    )

    result = poll_source_once(
        source=source,
        fetcher=FakeFetcher(
            snapshot=snapshot,
            events=events,
        ),
        transaction_factory=(
            FakeTransactionFactory(
                events=events
            )
        ),
        notification_recipient=(
            " alerts@example.com "
        ),
    )

    assert events == [
        "fetch",
        "transaction_begin",
        "outbox_repository",
        "enqueue",
        "transaction_commit",
    ]

    assert observed == {
        "writer": outbox_repository,
        "candidates": (
            candidate,
        ),
        "source_account": (
            "databricks"
        ),
        "recipient": (
            "alerts@example.com"
        ),
        "detected_at": DETECTED_AT,
    }

    assert (
        result.outbox.queued_count
        == 1
    )


@pytest.mark.parametrize(
    "recipient",
    [
        None,
        "",
        "   ",
    ],
)
def test_missing_recipient_rolls_back_when_alert_exists(
    monkeypatch: pytest.MonkeyPatch,
    recipient: str | None,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    workflow_result = (
        make_workflow_result(
            alert_candidates=(
                object(),
            )
        )
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: object(),
    )

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        lambda *args, **kwargs: (
            workflow_result
        ),
    )

    with pytest.raises(
        ValueError,
        match="notification_recipient",
    ):
        poll_source_once(
            source=source,
            fetcher=FakeFetcher(
                snapshot=snapshot,
                events=events,
            ),
            transaction_factory=(
                FakeTransactionFactory(
                    events=events
                )
            ),
            notification_recipient=(
                recipient
            ),
        )

    assert events == [
        "fetch",
        "transaction_begin",
        "transaction_rollback",
    ]


def test_workflow_receives_provider_neutral_snapshot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    repository = object()

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: repository,
    )

    observed: dict[
        str,
        Any,
    ] = {}

    def fake_workflow(
        passed_repository,
        *,
        source,
        source_account,
        jobs,
        observed_at,
    ):
        observed.update(
            {
                "repository": (
                    passed_repository
                ),
                "source": source,
                "source_account": (
                    source_account
                ),
                "jobs": jobs,
                "observed_at": (
                    observed_at
                ),
            }
        )

        return make_workflow_result()

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        fake_workflow,
    )

    poll_source_once(
        source=source,
        fetcher=FakeFetcher(
            snapshot=snapshot,
            events=events,
        ),
        transaction_factory=(
            FakeTransactionFactory(
                events=events
            )
        ),
        notification_recipient=None,
    )

    assert observed == {
        "repository": repository,
        "source": "greenhouse",
        "source_account": "databricks",
        "jobs": (),
        "observed_at": DETECTED_AT,
    }


def test_poll_result_exposes_summary_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    workflow_result = (
        SimpleNamespace(
            evaluation=(
                SimpleNamespace(
                    alert_candidates=(),
                    evaluated_count=3,
                    alert_candidate_count=2,
                )
            )
        )
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: object(),
    )

    monkeypatch.setattr(
        service_module,
        "run_source_snapshot_workflow",
        lambda *args, **kwargs: (
            workflow_result
        ),
    )

    result = poll_source_once(
        source=source,
        fetcher=FakeFetcher(
            snapshot=snapshot,
            events=events,
        ),
        transaction_factory=(
            FakeTransactionFactory(
                events=events
            )
        ),
        notification_recipient=None,
    )

    assert (
        result.source_definition
        is source
    )

    assert result.fetched_count == 0

    assert result.evaluated_count == 3

    assert (
        result.alert_candidate_count
        == 2
    )

    assert (
        result.queued_notification_count
        == 0
    )