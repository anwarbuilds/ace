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
from backend.app.scheduling.service import (
    poll_source_once,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
    SourceType,
)


class _StubRepository:
    """Minimal repository stand-in for transaction-boundary tests.

    These tests care about ordering and rollback, not persistence, so
    the repository only has to absorb the calls the service makes.
    """

    def record_http_validators(
        self,
        **_kwargs,
    ) -> None:
        return None

    def record_source_unchanged(
        self,
        **_kwargs,
    ) -> None:
        return None


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
        # These service tests cover transaction boundaries and outbox
        # wiring. Evaluation materialization is covered separately in
        # test_job_evaluations.py against a real database.
        evaluated_jobs=(),
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
        stale_suppressed_count=0,
    )


def make_workflow_result(
    *,
    alert_candidates: tuple[
        Any,
        ...,
    ] = (),
) -> SimpleNamespace:
    """Create the minimum workflow result used by service tests."""

    evaluation = make_evaluation(
        alert_candidates=(
            alert_candidates
        )
    )

    return SimpleNamespace(
        evaluation=evaluation,
        stale_suppressed_count=(
            evaluation
            .stale_suppressed_count
        ),
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
        or _StubRepository(),
    )

    def fake_workflow(
        repository,
        *,
        source,
        source_account,
        jobs,
        observed_at,
        freshness_policy=None,
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





def test_workflow_receives_provider_neutral_snapshot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    source = make_source()

    snapshot = make_snapshot(
        source
    )

    repository = _StubRepository()

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
        freshness_policy=None,
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
                    evaluated_jobs=(),
                    evaluated_count=3,
                    alert_candidate_count=2,
                    stale_suppressed_count=1,
                )
            ),
            stale_suppressed_count=1,
        )
    )

    monkeypatch.setattr(
        service_module,
        "JobRepository",
        lambda _session: _StubRepository(),
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
