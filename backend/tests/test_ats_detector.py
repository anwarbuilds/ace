"""Tests for generic ATS URL detection."""

from backend.app.discovery.detector import (
    DetectedSourceIdentity,
    detect_source_from_url,
)
from backend.app.scheduling.types import (
    SourceType,
)


def test_detects_modern_greenhouse_job_url() -> None:
    result = detect_source_from_url(
        (
            "https://job-boards.greenhouse.io/"
            "kikoff/jobs/4393822009"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account="kikoff",
        source_host=(
            "job-boards.greenhouse.io"
        ),
    )


def test_detects_legacy_greenhouse_board_url() -> None:
    result = detect_source_from_url(
        (
            "https://boards.greenhouse.io/"
            "ExampleCompany/jobs/123"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=(
            "examplecompany"
        ),
        source_host=(
            "boards.greenhouse.io"
        ),
    )


def test_detects_lever_job_url() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.lever.co/"
            "examplecompany/"
            "12345678-abcd"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.LEVER
        ),
        source_account=(
            "examplecompany"
        ),
        source_host=(
            "jobs.lever.co"
        ),
    )


def test_detects_lever_eu_job_url() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.eu.lever.co/"
            "example-eu/"
            "12345678-abcd"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.LEVER
        ),
        source_account=(
            "example-eu"
        ),
        source_host=(
            "jobs.eu.lever.co"
        ),
    )


def test_detects_ashby_job_url_and_preserves_account_case() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.ashbyhq.com/"
            "ExampleAI/"
            "12345678-abcd"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.ASHBY
        ),
        source_account=(
            "ExampleAI"
        ),
        source_host=(
            "jobs.ashbyhq.com"
        ),
    )


def test_detects_smartrecruiters_classic_job_url() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.smartrecruiters.com/"
            "ExampleCompany/"
            "123456789-software-engineer"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.SMARTRECRUITERS
        ),
        source_account=(
            "ExampleCompany"
        ),
        source_host=(
            "jobs.smartrecruiters.com"
        ),
    )


def test_detects_smartrecruiters_oneclick_url() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.smartrecruiters.com/"
            "oneclick-ui/"
            "company/"
            "ExampleCompany/"
            "publication/"
            "12345678-abcd"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.SMARTRECRUITERS
        ),
        source_account=(
            "ExampleCompany"
        ),
        source_host=(
            "jobs.smartrecruiters.com"
        ),
    )


def test_detects_smartrecruiters_career_board_url() -> None:
    result = detect_source_from_url(
        (
            "https://careers.smartrecruiters.com/"
            "ExampleCompany"
        )
    )

    assert result == DetectedSourceIdentity(
        source_type=(
            SourceType.SMARTRECRUITERS
        ),
        source_account=(
            "ExampleCompany"
        ),
        source_host=(
            "careers.smartrecruiters.com"
        ),
    )


def test_query_string_and_fragment_do_not_change_identity() -> None:
    result = detect_source_from_url(
        (
            "https://jobs.ashbyhq.com/"
            "ExampleAI/"
            "123"
            "?utm_source=test"
            "#apply"
        )
    )

    assert result is not None

    assert (
        result.source_type
        == SourceType.ASHBY
    )

    assert (
        result.source_account
        == "ExampleAI"
    )


def test_scheme_less_known_url_is_supported() -> None:
    result = detect_source_from_url(
        (
            "jobs.lever.co/"
            "examplecompany/"
            "123"
        )
    )

    assert result is not None

    assert (
        result.source_type
        == SourceType.LEVER
    )

    assert (
        result.source_account
        == "examplecompany"
    )


def test_unknown_job_site_returns_none() -> None:
    result = detect_source_from_url(
        (
            "https://careers.example.com/"
            "jobs/123"
        )
    )

    assert result is None


def test_known_host_without_account_returns_none() -> None:
    assert (
        detect_source_from_url(
            "https://jobs.lever.co/"
        )
        is None
    )

    assert (
        detect_source_from_url(
            "https://jobs.ashbyhq.com/"
        )
        is None
    )

    assert (
        detect_source_from_url(
            "https://job-boards.greenhouse.io/"
        )
        is None
    )