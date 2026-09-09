"""Tests for ACE provider-neutral source dispatch."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.app.adapters.http_cache import (
    CacheValidators,
)
from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.scheduling.dispatcher import (
    AdzunaSourceFetcher,
    AshbySourceFetcher,
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


_NO_VALIDATORS = CacheValidators()


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
        validators=None,
    ) -> list[CanonicalJob]:
        observed[
            "board_token"
        ] = board_token

        observed[
            "company_name"
        ] = company_name

        return (
            [
                expected_job,
            ],
            False,
            _NO_VALIDATORS,
        )

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


def test_ashby_fetcher_uses_source_configuration() -> None:
    source = SourceDefinition(
        source_type=SourceType.ASHBY,
        source_account="ExampleAI",
        company_name="Example AI",
        source_host="jobs.ashbyhq.com",
    )

    expected_job = CanonicalJob(
        source="ashby",
        company="Example AI",
        external_id="ashby-1",
        requisition_id=None,
        title="Software Engineer",
        location="New York, NY",
        description="Build software.",
        official_url=(
            "https://jobs.ashbyhq.com/"
            "ExampleAI/ashby-1"
        ),
        posted_at=DETECTED_AT,
        updated_at=None,
    )

    observed: dict[
        str,
        str,
    ] = {}

    def fake_fetcher(
        board_name: str,
        company_name: str,
        validators=None,
    ) -> list[CanonicalJob]:
        observed[
            "board_name"
        ] = board_name

        observed[
            "company_name"
        ] = company_name

        return (
            [
                expected_job,
            ],
            False,
            _NO_VALIDATORS,
        )

    fetcher = AshbySourceFetcher(
        fetcher=fake_fetcher,
        clock=lambda: DETECTED_AT,
    )

    snapshot = fetcher(
        source
    )

    assert observed == {
        "board_name": "ExampleAI",
        "company_name": "Example AI",
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


def test_default_dispatcher_supports_all_implemented_sources() -> None:
    dispatcher = (
        build_default_source_dispatcher()
    )

    assert (
        dispatcher.supported_source_types
        == frozenset(
            {
                SourceType.ASHBY,
                SourceType.GREENHOUSE,
                SourceType.LEVER,
                SourceType.SMARTRECRUITERS,
                SourceType.WORKDAY,
                SourceType.AMAZON,
                SourceType.SIMPLIFY,
                SourceType.EIGHTFOLD,
                SourceType.EIGHTFOLD_PCSX,
                SourceType.ADZUNA,
            }
        )
    )

# --- AdzunaSourceFetcher ------------------------------------------------


def make_adzuna_source() -> SourceDefinition:
    return SourceDefinition(
        source_type=SourceType.ADZUNA,
        source_account="us-swe-entry-level",
        company_name="Adzuna",
    )


def adzuna_job(
    *,
    company: str,
    external_id: str = "1",
) -> CanonicalJob:
    return CanonicalJob(
        source="adzuna",
        company=company,
        external_id=external_id,
        requisition_id=None,
        title="Software Engineer",
        location="Austin, Texas",
        description="Build software.",
        official_url=(
            "https://www.adzuna.com"
            f"/details/{external_id}"
        ),
        posted_at=DETECTED_AT,
        updated_at=None,
    )


def test_adzuna_drops_a_company_ace_already_watches_directly() -> (
    None
):
    """A duplicate from the aggregator has a worse link than the
    listing ACE already has from the employer's own board, so it adds
    noise for no coverage gained."""

    fetcher = AdzunaSourceFetcher(
        fetcher=lambda **_: [
            adzuna_job(
                company="Stripe",
                external_id="1",
            ),
            adzuna_job(
                company="A New Employer",
                external_id="2",
            ),
        ],
        credentials=lambda: (
            "id",
            "key",
        ),
        excluded_companies=lambda: {
            "stripe",
        },
    )

    snapshot = fetcher(
        make_adzuna_source()
    )

    companies = {
        job.company
        for job in snapshot.jobs
    }

    assert companies == {
        "A New Employer",
    }


def test_adzuna_requires_configured_credentials() -> None:
    """Fails loudly rather than sending an empty key to Adzuna's API,
    which the user would only discover from a wall of 401s in the
    scheduler log."""

    fetcher = AdzunaSourceFetcher(
        fetcher=lambda **_: [],
        credentials=lambda: (
            None,
            None,
        ),
        excluded_companies=lambda: (
            frozenset()
        ),
    )

    with pytest.raises(
        ValueError,
        match="credentials",
    ):
        fetcher(
            make_adzuna_source()
        )


def test_adzuna_refuses_a_mismatched_source_definition() -> None:
    fetcher = AdzunaSourceFetcher(
        fetcher=lambda **_: [],
        credentials=lambda: (
            "id",
            "key",
        ),
        excluded_companies=lambda: (
            frozenset()
        ),
    )

    with pytest.raises(
        ValueError,
    ):
        fetcher(
            make_source()
        )


def test_adzuna_exclusion_matches_company_name_variants() -> None:
    """Company names differ in wording across sources: ACE registered
    Anduril as "Anduril", Adzuna might report "Anduril Industries".
    The same normalisation the coverage benchmark uses has to apply
    here or the exclusion silently misses real duplicates."""

    fetcher = AdzunaSourceFetcher(
        fetcher=lambda **_: [
            adzuna_job(
                company="Anduril Industries",
            ),
        ],
        credentials=lambda: (
            "id",
            "key",
        ),
        excluded_companies=lambda: {
            "anduril",
        },
    )

    snapshot = fetcher(
        make_adzuna_source()
    )

    assert snapshot.jobs == ()
