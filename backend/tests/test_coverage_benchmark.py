"""Tests for the coverage benchmark.

The benchmark exists to stop coverage being an opinion, so its own
arithmetic has to be trustworthy. Every parsing case here comes from
the real held-out lists, which write the employer three different ways
in the same column.
"""

from __future__ import annotations

from backend.app.coverage.benchmark import (
    companies_in_markdown,
    measure_list,
    normalise_company,
    overall_recall,
)


def test_a_company_is_read_however_the_row_writes_it() -> None:
    """Bare, bold, and linked all name the same first column."""

    markdown = (
        "| Company | Role | Location |\n"
        "| --- | --- | --- |\n"
        "| Stripe | SWE | NY |\n"
        "| **Ramp** | SWE | NY |\n"
        "| [Plaid](https://x) | SWE | SF |\n"
        "| **[Vanta](https://y)** | SWE | SF |\n"
    )

    assert companies_in_markdown(
        markdown
    ) == {
        "stripe",
        "ramp",
        "plaid",
        "vanta",
    }


def test_table_furniture_is_not_a_company() -> None:
    """Header and separator rows would otherwise count as employers
    and quietly inflate the denominator."""

    markdown = (
        "| Company | Role |\n"
        "| --- | --- |\n"
        "| Figma | SWE |\n"
    )

    assert companies_in_markdown(
        markdown
    ) == {
        "figma"
    }


def test_a_suffix_is_not_a_different_company() -> None:
    """Both sides of the comparison are normalised the same way, so a
    legal suffix cannot read as a coverage gap."""

    assert normalise_company(
        "Stripe, Inc."
    ) == normalise_company(
        "stripe"
    )

    assert normalise_company(
        "Applied Intuition Technologies"
    ) == "applied intuition"


def test_recall_counts_polled_and_held_alike(
) -> None:
    """Either means ACE had a path to the job. Which of the two it was
    is a question for discovery, not for coverage."""

    markdown = (
        "| Company | Role |\n"
        "| --- | --- |\n"
        "| Stripe | SWE |\n"
        "| Ramp | SWE |\n"
        "| Nowhere | SWE |\n"
    )

    result = measure_list(
        name="test",
        markdown=markdown,
        corpus={"stripe"},
        watched={"ramp"},
    )

    assert result.listed == 3

    assert result.reached == 2

    assert result.missing == (
        "nowhere",
    )

    assert (
        abs(
            result.recall
            - 2 / 3
        )
        < 1e-9
    )


def test_overall_recall_weights_by_companies_listed(
) -> None:
    """Averaging the percentages instead would let a ten-company list
    count as much as a four-hundred-company one."""

    small = measure_list(
        name="small",
        markdown=(
            "| Company | Role |\n"
            "| --- | --- |\n"
            "| Stripe | SWE |\n"
        ),
        corpus={"stripe"},
        watched=set(),
    )

    large = measure_list(
        name="large",
        markdown=(
            "| Company | Role |\n"
            "| --- | --- |\n"
            + "".join(
                f"| Co{index} | SWE |\n"
                for index in range(9)
            )
        ),
        corpus=set(),
        watched=set(),
    )

    assert small.recall == 1.0

    assert large.recall == 0.0

    # One reached of ten listed, not the 50% a naive average gives.
    assert (
        abs(
            overall_recall(
                [small, large]
            )
            - 0.1
        )
        < 1e-9
    )
