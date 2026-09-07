"""Browser tests for the ACE client.

Each of these covers a bug that actually shipped. The client is one HTML
file with no seam for unit tests, so every interface defect so far was
found by a person looking at the page: a primary button pushed off
screen, a list stuck on skeletons, a sort that silently did nothing, a
deletion that took unrelated functions with it and left the app blank.

They run against the app on ACE_BROWSER_TEST_URL, and skip rather than
fail when Chrome or the server is missing.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.browser


# --- the page renders at all ------------------------------------------


def test_the_queue_renders(
    page,
) -> None:
    """The regression that motivated all of this.

    Deleting a block of JavaScript once removed unrelated functions
    with it, render() threw, and the app drew nothing. Nothing caught
    it because nothing loaded the page.
    """

    assert page.eval(
        "document.getElementById('app')"
        ".innerHTML.length"
    ) > 1000

    assert page.count(
        ".row"
    ) > 0


def test_rendering_raises_nothing(
    page,
) -> None:
    """render() must be safe to call again at any moment."""

    assert page.eval(
        "(function(){try{render();return 'ok';}"
        "catch(e){return 'threw: '+e.message;}})()"
    ) == "ok"


def test_no_skeletons_remain_after_loading(
    page,
) -> None:
    """The list once stayed on skeletons forever.

    Every call site of loadJobs passed a promise result as its first
    argument, which was truthy, so it took the append branch and
    fetched nothing.
    """

    assert page.count(
        ".sk-row"
    ) == 0

    assert page.eval(
        "state.loading"
    ) is False


def test_the_headline_total_matches_the_rows(
    page,
) -> None:
    """A count disagreeing with the list reads as jobs being withheld."""

    total = page.eval(
        "state.total"
    )

    assert page.text(
        ".h1-count"
    ) == str(
        total
    )

    assert (
        page.eval(
            "state.stats"
            ".qualifying_active_jobs"
        )
        == total
    )


# --- the primary action is reachable ----------------------------------


def test_the_job_page_shows_its_primary_action(
    page,
) -> None:
    """"Open official posting" was once pushed below the fold.

    It was in the DOM the whole time, which is exactly why only looking
    at the page found it.
    """

    page.click(
        ".j-title"
    )

    page.wait_for(
        "state.page==='job'"
    )

    assert page.text(
        ".btn-primary"
    ).startswith(
        "Open official posting"
    )

    viewport = page.eval(
        "window.innerHeight || "
        "document.documentElement"
        ".clientHeight"
    )

    top = page.eval(
        "document.querySelector"
        "('.btn-primary')"
        ".getBoundingClientRect().top"
    )

    assert 0 <= top < viewport, (
        "the primary action is off screen"
    )


def test_a_job_link_survives_being_opened_cold(
    page,
) -> None:
    """Right-click, open in new tab used to land on the queue.

    The href looked like a link but nothing routed on it.
    """

    href = page.eval(
        "document.querySelector('.j-title')"
        ".getAttribute('href')"
    )

    assert href.startswith(
        "#job/"
    )

    job_id = int(
        href.split(
            "/"
        )[1]
    )

    page.open(
        "/" + href
    )

    page.wait_for(
        "state.page==='job' && !!state.detailJob"
    )

    assert page.eval(
        "state.jobId"
    ) == job_id

    assert page.text(
        ".jp-title"
    )


# --- sorting ----------------------------------------------------------


def test_enabling_a_sort_makes_it_primary(
    page,
) -> None:
    """Appending it left "Not applied first" third, breaking only ties,
    which reads as the sort doing nothing at all."""

    page.click(
        '[data-sort="unapplied_first"]'
    )

    page.wait_for(
        "state.sorts.indexOf"
        "('unapplied_first')<0"
    )

    page.click(
        '[data-sort="unapplied_first"]'
    )

    page.wait_for(
        "state.sorts[0]==='unapplied_first'"
    )


def test_applied_jobs_sink_under_the_default_sort(
    page,
) -> None:
    """The whole point of returning to a long queue."""

    assert page.eval(
        "state.sorts[0]"
    ) == "unapplied_first"

    assert page.eval(
        "(function(){var s=state.items.map("
        "function(j){return j.applied_at?1:0;});"
        "return !s.some(function(v,i){"
        "return v===0 && s.slice(0,i)"
        ".indexOf(1)>=0;});})()"
    ), "an unapplied job sorted below an applied one"


# --- filters ----------------------------------------------------------


def test_excluding_a_company_removes_it_and_keeps_the_rest(
    page,
) -> None:
    before = page.eval(
        "state.total"
    )

    company = page.eval(
        "state.items[0].company"
    )

    page.eval(
        "toggleExclude("
        + repr(
            company
        ).replace(
            "'",
            '"',
        )
        + ")"
    )

    page.wait_for(
        "!state.loading && state.total<"
        + str(
            before
        )
    )

    assert page.eval(
        "state.items.every(function(j){"
        "return j.company!=="
        + repr(
            company
        ).replace(
            "'",
            '"',
        )
        + ";})"
    )

    page.click(
        ".chip.excluded"
    )

    page.wait_for(
        "!state.loading && state.total==="
        + str(
            before
        )
    )


def test_the_age_filter_is_off_until_asked_for(
    page,
) -> None:
    """It once narrowed the queue on load without being asked."""

    assert page.eval(
        "state.recentOnly"
    ) is False

    assert page.eval(
        "params(viewParams())"
        ".has('max_detected_age_days')"
    ) is False


# --- pages load -------------------------------------------------------


@pytest.mark.parametrize(
    "page_name,marker",
    [
        ("pulls", ".gh"),
        ("resumes", ".wrap"),
        ("skills", ".wrap"),
        ("answers", ".ans-edit"),
        ("settings", ".wrap"),
        ("saved", ".h1"),
        ("applied", ".h1"),
        ("archive", ".h1"),
    ],
)
def test_every_page_renders_something(
    page,
    page_name,
    marker,
) -> None:
    """A page that throws leaves a blank frame and no other signal."""

    page.eval(
        f"goTo({page_name!r})".replace(
            "'",
            '"',
        )
    )

    page.wait_for(
        f"state.page==={page_name!r}".replace(
            "'",
            '"',
        )
    )

    page.wait_for(
        "document.querySelectorAll("
        + repr(
            marker
        ).replace(
            "'",
            '"',
        )
        + ").length>0",
        timeout=15,
    )


# --- content rules ----------------------------------------------------


def test_no_em_dash_reaches_the_screen(
    page,
) -> None:
    """A permanent content rule, and the one most easily broken by a
    stray string in a template."""

    assert page.eval(
        "document.body.innerText"
        ".indexOf('\\u2014')"
    ) == -1


def test_both_themes_paint_their_own_background(
    page,
) -> None:
    """A transparent body silently borrows the host's theme."""

    for theme, expected in (
        (
            "dark",
            "rgb(13, 8, 23)",
        ),
        (
            "light",
            "rgb(252, 250, 254)",
        ),
    ):
        page.eval(
            f'applyTheme("{theme}")'
        )

        assert page.eval(
            "getComputedStyle"
            "(document.body)"
            ".backgroundColor"
        ) == expected, theme

    page.eval(
        'applyTheme("dark")'
    )
