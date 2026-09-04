"""Tests for public Greenhouse source discovery providers."""

import httpx
import pytest

from backend.app.discovery.providers import (
    DiscoveryFeed,
    PublicGreenhouseFeedProvider,
    PublicJobFeedProvider,
    extract_greenhouse_candidates,
    extract_source_candidates,
    greenhouse_account_from_url,
)
from backend.app.scheduling.types import (
    SourceType,
)


def test_greenhouse_account_from_modern_job_board_url() -> None:
    account = greenhouse_account_from_url(
        (
            "https://job-boards.greenhouse.io/"
            "kikoff/jobs/4393822009"
        )
    )

    assert account == "kikoff"


def test_greenhouse_account_from_legacy_board_url() -> None:
    account = greenhouse_account_from_url(
        (
            "https://boards.greenhouse.io/"
            "Example-Company/"
            "jobs/123"
        )
    )

    assert (
        account
        == "example-company"
    )


def test_non_greenhouse_url_is_ignored() -> None:
    account = greenhouse_account_from_url(
        (
            "https://example.com/"
            "jobs/123"
        )
    )

    assert account is None


def test_extract_candidates_preserves_company_name() -> None:
    document = """
    <table>
      <tbody>
        <tr>
          <td>
            <strong>
              <a href="https://example.com/company">
                Startup Alpha
              </a>
            </strong>
          </td>
          <td>Software Engineer New Grad</td>
          <td>San Francisco, CA</td>
          <td>
            <a href="https://job-boards.greenhouse.io/startupalpha/jobs/123">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    candidates = (
        extract_greenhouse_candidates(
            document,
            discovery_source=(
                "test-feed"
            ),
        )
    )

    assert len(
        candidates
    ) == 1

    candidate = (
        candidates[
            0
        ]
    )

    assert (
        candidate.source_type
        == SourceType.GREENHOUSE
    )

    assert (
        candidate.source_account
        == "startupalpha"
    )

    assert (
        candidate.company_name
        == "Startup Alpha"
    )

    assert (
        candidate.discovery_source
        == "test-feed"
    )


def test_arrow_row_reuses_previous_company_name() -> None:
    document = """
    <table>
      <tbody>
        <tr>
          <td>Startup Beta</td>
          <td>Software Engineer</td>
          <td>New York, NY</td>
          <td>
            <a href="https://example.com/job-one">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>↳</td>
          <td>Software Engineer I</td>
          <td>Remote</td>
          <td>
            <a href="https://job-boards.greenhouse.io/startupbeta/jobs/456">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    candidates = (
        extract_greenhouse_candidates(
            document,
            discovery_source=(
                "test-feed"
            ),
        )
    )

    assert len(
        candidates
    ) == 1

    assert (
        candidates[
            0
        ].company_name
        == "Startup Beta"
    )


def test_duplicate_greenhouse_account_is_returned_once() -> None:
    document = """
    <table>
      <tbody>
        <tr>
          <td>Startup Gamma</td>
          <td>Software Engineer</td>
          <td>Remote</td>
          <td>
            <a href="https://job-boards.greenhouse.io/startupgamma/jobs/1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Startup Gamma</td>
          <td>Backend Engineer</td>
          <td>Remote</td>
          <td>
            <a href="https://job-boards.greenhouse.io/startupgamma/jobs/2">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    candidates = (
        extract_greenhouse_candidates(
            document,
            discovery_source=(
                "test-feed"
            ),
        )
    )

    assert len(
        candidates
    ) == 1

    assert (
        candidates[
            0
        ].source_account
        == "startupgamma"
    )


def test_provider_deduplicates_accounts_across_feeds() -> None:
    feed_one = DiscoveryFeed(
        name="feed-one",
        url="https://example.com/one",
    )

    feed_two = DiscoveryFeed(
        name="feed-two",
        url="https://example.com/two",
    )

    documents = {
        feed_one.url: """
            <table>
              <tr>
                <td>Startup Delta</td>
                <td>Engineer</td>
                <td>Remote</td>
                <td>
                  <a href="https://job-boards.greenhouse.io/startupdelta/jobs/1">
                    Apply
                  </a>
                </td>
              </tr>
            </table>
        """,
        feed_two.url: """
            <table>
              <tr>
                <td>Startup Delta</td>
                <td>Engineer I</td>
                <td>New York</td>
                <td>
                  <a href="https://job-boards.greenhouse.io/startupdelta/jobs/2">
                    Apply
                  </a>
                </td>
              </tr>
            </table>
        """,
    }

    def fetch_text(
        url: str,
    ) -> str:
        return documents[
            url
        ]

    provider = (
        PublicGreenhouseFeedProvider(
            feeds=(
                feed_one,
                feed_two,
            ),
            fetch_text=(
                fetch_text
            ),
        )
    )

    candidates = (
        provider.discover()
    )

    assert len(
        candidates
    ) == 1

    assert (
        candidates[
            0
        ].source_account
        == "startupdelta"
    )


def test_provider_continues_when_one_feed_fails() -> None:
    broken_feed = DiscoveryFeed(
        name="broken",
        url="https://example.com/broken",
    )

    working_feed = DiscoveryFeed(
        name="working",
        url="https://example.com/working",
    )

    document = """
    <table>
      <tr>
        <td>Startup Echo</td>
        <td>Software Engineer</td>
        <td>Remote</td>
        <td>
          <a href="https://job-boards.greenhouse.io/startupecho/jobs/1">
            Apply
          </a>
        </td>
      </tr>
    </table>
    """

    def fetch_text(
        url: str,
    ) -> str:
        if (
            url
            == broken_feed.url
        ):
            raise httpx.ConnectError(
                "synthetic failure"
            )

        return document

    provider = (
        PublicGreenhouseFeedProvider(
            feeds=(
                broken_feed,
                working_feed,
            ),
            fetch_text=(
                fetch_text
            ),
        )
    )

    candidates = (
        provider.discover()
    )

    assert len(
        candidates
    ) == 1

    assert (
        candidates[
            0
        ].source_account
        == "startupecho"
    )


def test_provider_raises_when_every_feed_fails() -> None:
    feed = DiscoveryFeed(
        name="broken",
        url="https://example.com/broken",
    )

    def fetch_text(
        url: str,
    ) -> str:
        del url

        raise httpx.ConnectError(
            "synthetic failure"
        )

    provider = (
        PublicGreenhouseFeedProvider(
            feeds=(
                feed,
            ),
            fetch_text=(
                fetch_text
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "All configured source "
            "discovery feeds failed"
        ),
    ):
        provider.discover()


def test_provider_can_limit_candidate_count() -> None:
    feed = DiscoveryFeed(
        name="test",
        url="https://example.com/feed",
    )

    document = """
    <table>
      <tr>
        <td>Company One</td>
        <td>Engineer</td>
        <td>Remote</td>
        <td>
          <a href="https://job-boards.greenhouse.io/companyone/jobs/1">
            Apply
          </a>
        </td>
      </tr>

      <tr>
        <td>Company Two</td>
        <td>Engineer</td>
        <td>Remote</td>
        <td>
          <a href="https://job-boards.greenhouse.io/companytwo/jobs/2">
            Apply
          </a>
        </td>
      </tr>
    </table>
    """

    provider = (
        PublicGreenhouseFeedProvider(
            feeds=(
                feed,
            ),
            fetch_text=(
                lambda url: document
            ),
            max_candidates=1,
        )
    )

    candidates = (
        provider.discover()
    )

    assert len(
        candidates
    ) == 1

def test_generic_extractor_discovers_multiple_ats_families() -> None:
    document = """
    <table>
      <tbody>
        <tr>
          <td>Greenhouse Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://job-boards.greenhouse.io/greenhousecompany/jobs/1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Lever EU Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.eu.lever.co/example-eu/lever-job-1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Example AI</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.ashbyhq.com/ExampleAI/ashby-job-1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Smart Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.smartrecruiters.com/ExampleCompany/123-software-engineer">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    candidates = (
        extract_source_candidates(
            document,
            discovery_source=(
                "mixed-test-feed"
            ),
        )
    )

    assert len(candidates) == 4

    by_type = {
        candidate.source_type: candidate
        for candidate in candidates
    }

    assert set(by_type) == {
        SourceType.GREENHOUSE,
        SourceType.LEVER,
        SourceType.ASHBY,
        SourceType.SMARTRECRUITERS,
    }

    greenhouse = by_type[
        SourceType.GREENHOUSE
    ]

    assert (
        greenhouse.source_account
        == "greenhousecompany"
    )

    assert (
        greenhouse.company_name
        == "Greenhouse Company"
    )

    lever = by_type[
        SourceType.LEVER
    ]

    assert (
        lever.source_account
        == "example-eu"
    )

    assert (
        lever.source_host
        == "jobs.eu.lever.co"
    )

    assert (
        lever.company_name
        == "Lever EU Company"
    )

    ashby = by_type[
        SourceType.ASHBY
    ]

    assert (
        ashby.source_account
        == "ExampleAI"
    )

    assert (
        ashby.source_host
        == "jobs.ashbyhq.com"
    )

    smartrecruiters = by_type[
        SourceType.SMARTRECRUITERS
    ]

    assert (
        smartrecruiters.source_account
        == "ExampleCompany"
    )

    assert (
        smartrecruiters.source_host
        == "jobs.smartrecruiters.com"
    )

    assert (
        smartrecruiters.discovery_source
        == "mixed-test-feed"
    )


def test_generic_extractor_deduplicates_same_ats_identity() -> None:
    document = """
    <table>
      <tbody>
        <tr>
          <td>Example AI</td>
          <td>
            <a href="https://jobs.ashbyhq.com/ExampleAI/job-one">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Example AI</td>
          <td>
            <a href="https://jobs.ashbyhq.com/ExampleAI/job-two">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    candidates = (
        extract_source_candidates(
            document,
            discovery_source="test-feed",
        )
    )

    assert len(candidates) == 1

    assert (
        candidates[
            0
        ].source_type
        == SourceType.ASHBY
    )

    assert (
        candidates[
            0
        ].source_account
        == "ExampleAI"
    )

def test_public_job_feed_provider_discovers_multiple_ats_families() -> None:
    feed = DiscoveryFeed(
        name="mixed-feed",
        url="https://example.com/jobs",
    )

    document = """
    <table>
      <tbody>
        <tr>
          <td>Greenhouse Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://job-boards.greenhouse.io/greenhousecompany/jobs/1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Lever Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.lever.co/levercompany/job-1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>Ashby Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.ashbyhq.com/AshbyCompany/job-1">
              Apply
            </a>
          </td>
        </tr>

        <tr>
          <td>SmartRecruiters Company</td>
          <td>Software Engineer</td>
          <td>
            <a href="https://jobs.smartrecruiters.com/SmartCompany/123-engineer">
              Apply
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """

    provider = PublicJobFeedProvider(
        feeds=(
            feed,
        ),
        fetch_text=(
            lambda url: document
        ),
    )

    candidates = (
        provider.discover()
    )

    assert len(candidates) == 4

    assert {
        candidate.source_type
        for candidate in candidates
    } == {
        SourceType.GREENHOUSE,
        SourceType.LEVER,
        SourceType.ASHBY,
        SourceType.SMARTRECRUITERS,
    }


def test_old_greenhouse_provider_name_is_compatibility_alias() -> None:
    assert (
        PublicGreenhouseFeedProvider
        is PublicJobFeedProvider
    )
