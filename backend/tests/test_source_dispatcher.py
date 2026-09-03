"""Tests for ACE provider-neutral source dispatch."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.scheduling.dispatcher import (
    GreenhouseSourceFetcher,
    SourceDispatcher,
    UnsupportedSourceTypeError,
    build_default_source_dispatcher,
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
    22,
    0,
    tzinfo=timezone.utc,
)


def make_source(
    *,
    source_account: str = "databricks",
    company_name: str = "Databricks",
) -> SourceDefinition:
    """Create one synthetic Greenhouse source definition."""

    return SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=source_account,
        company_name=company_name,
    )


def make_job(
    external_id: str = "1",
) -> CanonicalJob:
    """Create one normalized Greenhouse job."""

    return CanonicalJob(
        source="greenhouse",
        company="Databricks",
        external_id=external_id,
        requisition_id=(
            f"REQ-{external_id}"
        ),
        title="Software Engineer",
        location="Seattle, Washington",
        description=(
            "Build reliable distributed systems."
        ),
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
        posted_at=DETECTED_AT,
        updated_at=DETECTED_AT,
    )


def test_fetched_snapshot_exposes_provider_neutral_identity() -> None:
    source = make_source()

    job = make_job()

    snapshot = FetchedSourceSnapshot(
        source_definition=source,
        detected_at=DETECTED_AT,
        jobs=(
            job,
        ),
    )

    assert (
        snapshot.source_type
        == SourceType.GREENHOUSE
    )

    assert (
        snapshot.source
        == "greenhouse"
    )

    assert (
        snapshot.source_account
        == "databricks"
    )

    assert (
        snapshot.company_name
        == "Databricks"
    )

    assert (
        snapshot.detected_at
        == DETECTED_AT
    )

    assert snapshot.job_count == 1

    assert snapshot.jobs == (
        job,
    )


def test_fetched_snapshot_normalizes_detection_time_to_utc() -> None:
    source = make_source()

    offset = timezone(
        timedelta(
            hours=-7
        )
    )

    local_time = datetime(
        2026,
        9,
        2,
        15,
        0,
        tzinfo=offset,
    )

    snapshot = FetchedSourceSnapshot(
        source_definition=source,
        detected_at=local_time,
        jobs=(
            make_job(),
        ),
    )

    assert (
        snapshot.detected_at
        == DETECTED_AT
    )

    assert (
        snapshot.detected_at.tzinfo
        == timezone.utc
    )


def test_fetched_snapshot_rejects_naive_detection_time() -> None:
    source = make_source()

    naive_time = datetime(
        2026,
        9,
        2,
        22,
        0,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        FetchedSourceSnapshot(
            source_definition=source,
            detected_at=naive_time,
            jobs=(
                make_job(),
            ),
        )


def test_fetched_snapshot_rejects_mismatched_job_source() -> None:
    source = make_source()

    job = CanonicalJob(
        source="lever",
        company="Databricks",
        external_id="1",
        requisition_id="REQ-1",
        title="Software Engineer",
        location="Seattle, Washington",
        description="Build software.",
        official_url=(
            "https://example.com/jobs/1"
        ),
        posted_at=DETECTED_AT,
        updated_at=DETECTED_AT,
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        FetchedSourceSnapshot(
            source_definition=source,
            detected_at=DETECTED_AT,
            jobs=(
                job,
            ),
        )


def test_greenhouse_fetcher_uses_source_configuration() -> None:
    source = make_source(
        source_account="example-board",
        company_name="Example Company",
    )

    expected_job = make_job()

    observed: dict[
        str,
        str,
    ] = {}

    def fake_fetcher(
        board_token: str,
        company_name: str,
    ) -> list[CanonicalJob]:
        observed[
            "board_token"
        ] = board_token

        observed[
            "company_name"
        ] = company_name

        return [
            expected_job,
        ]

    fetcher = GreenhouseSourceFetcher(
        fetcher=fake_fetcher,
        clock=lambda: DETECTED_AT,
    )

    snapshot = fetcher(
        source
    )

    assert observed == {
        "board_token": "example-board",
        "company_name": "Example Company",
    }

    assert (
        snapshot.source_definition
        is source
    )

    assert (
        snapshot.detected_at
        == DETECTED_AT
    )

    assert snapshot.jobs == (
        expected_job,
    )


def test_dispatcher_routes_source_to_registered_handler() -> None:
    source = make_source()

    expected_snapshot = (
        FetchedSourceSnapshot(
            source_definition=source,
            detected_at=DETECTED_AT,
            jobs=(
                make_job(),
            ),
        )
    )

    calls: list[
        SourceDefinition
    ] = []

    def handler(
        configured_source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        calls.append(
            configured_source
        )

        return expected_snapshot

    dispatcher = SourceDispatcher(
        {
            SourceType.GREENHOUSE: handler,
        }
    )

    result = dispatcher.fetch(
        source
    )

    assert result is expected_snapshot

    assert calls == [
        source,
    ]


def test_dispatcher_rejects_missing_handler() -> None:
    source = make_source()

    dispatcher = SourceDispatcher(
        {}
    )

    with pytest.raises(
        UnsupportedSourceTypeError,
        match="greenhouse",
    ):
        dispatcher.fetch(
            source
        )


def test_dispatcher_rejects_handler_returning_wrong_source() -> None:
    requested_source = make_source(
        source_account="requested",
        company_name="Requested",
    )

    wrong_source = make_source(
        source_account="wrong",
        company_name="Wrong",
    )

    wrong_snapshot = (
        FetchedSourceSnapshot(
            source_definition=wrong_source,
            detected_at=DETECTED_AT,
            jobs=(
                make_job(),
            ),
        )
    )

    dispatcher = SourceDispatcher(
        {
            SourceType.GREENHOUSE: (
                lambda _source: (
                    wrong_snapshot
                )
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="different source definition",
    ):
        dispatcher.fetch(
            requested_source
        )


def test_default_dispatcher_supports_greenhouse_and_lever() -> None:
    dispatcher = (
        build_default_source_dispatcher()
    )

    assert (
        dispatcher.supported_source_types
        == frozenset(
            {
                SourceType.GREENHOUSE,
                SourceType.LEVER,
            }
        )
    )