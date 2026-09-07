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


def _open_filters(
    page,
) -> None:
    """Open the Add a filter popover."""

    page.click(
        '[data-act="filters"]'
    )

    page.wait_for(
        "!!document.getElementById"
        "('filter-q')"
    )


def test_company_names_keep_their_capitals(
    page,
) -> None:
    """The list folded every value to lower case, which suits
    SOFTWARE_ENGINEERING and mangles ByteDance and IXL Learning."""

    _open_filters(
        page
    )

    top = page.eval(
        "state.facets.companies[0].value"
    )

    assert top != top.lower(), (
        "pick a corpus whose busiest company "
        "has capitals to test against"
    )

    assert page.eval(
        "Array.from(document"
        ".querySelectorAll('.pop-opt"
        "[data-addfilter=\"company\"]'))"
        ".some(function(b){return "
        "b.textContent.indexOf("
        + repr(
            top
        ).replace(
            "'",
            '"',
        )
        + ")>=0;})"
    ), f"{top} was not offered under its own name"


def test_a_company_outside_the_top_few_is_reachable(
    page,
) -> None:
    """Only the ten busiest companies were listed, so the other 159
    could not be filtered on at all."""

    _open_filters(
        page
    )

    target = page.eval(
        "(function(){var c=state.facets"
        ".companies;return c.length>20 ?"
        " c[c.length-1].value : '';})()"
    )

    if not target:
        pytest.skip(
            "corpus too small to have a tail"
        )

    assert not page.eval(
        "Array.from(document"
        ".querySelectorAll('.pop-opt'))"
        ".some(function(b){return "
        "b.textContent.indexOf("
        + repr(
            target
        ).replace(
            "'",
            '"',
        )
        + ")>=0;})"
    ), "the whole list is rendered, so search is not what makes it reachable"

    page.eval(
        "(function(){var i=document"
        ".getElementById('filter-q');"
        "i.value="
        + repr(
            target
        ).replace(
            "'",
            '"',
        )
        + ";i.dispatchEvent("
        "new Event('input'));})()"
    )

    assert page.wait_for(
        "Array.from(document"
        ".querySelectorAll('.pop-opt"
        "[data-addfilter=\"company\"]'))"
        ".some(function(b){return "
        "b.textContent.indexOf("
        + repr(
            target
        ).replace(
            "'",
            '"',
        )
        + ")>=0;})"
    )


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


# --- marking applied --------------------------------------------------


def _first_unapplied(
    page,
) -> int:
    """Return a queue row that is not already applied.

    Tests must never toggle a real application off, so they pick a row
    whose state they can restore exactly.
    """

    job_id = page.eval(
        "(function(){var j=state.items"
        ".filter(function(x){"
        "return !x.applied_at;})[0];"
        "return j ? j.id : 0;})()"
    )

    if not job_id:
        pytest.skip(
            "every queued job is already applied"
        )

    return job_id


def _applied_on_server(
    job_id: int,
    expected: str,
) -> str:
    """Return an expression that resolves true once the server agrees.

    The comparison sits inside the ``then`` because the browser hands
    back a promise: comparing the promise itself to a string is a
    perfectly valid expression that is simply always false.
    """

    return (
        f"fetch('/api/jobs/{job_id}')"
        ".then(function(r){"
        "return r.json();})"
        ".then(function(d){return "
        "String(d.application_status)"
        f"==={expected!r}".replace(
            "'",
            '"',
        )
        + ";})"
    )


def _mark_applied(
    page,
    job_id: int,
) -> None:
    """Click the row's Applied button and wait for the write to land.

    Waiting matters beyond the assertion: cleanup issues its own write,
    and a test that races ahead of the browser's request can have the
    two arrive out of order and leave a real job marked applied.
    """

    page.click(
        f'.row[data-id="{job_id}"] '
        '.iconbtn[data-mark="applied"]'
    )

    page.wait_for(
        _applied_on_server(
            job_id,
            "applied",
        )
    )


def _clear_applied(
    page,
    job_id: int,
) -> None:
    """Put the job back the way the test found it.

    This goes through the API rather than the button so cleanup still
    runs when the assertion about the button is what failed, and it
    waits for confirmation rather than trusting the write.
    """

    page.eval(
        f"putMark({job_id},"
        "{applied:false})"
    )

    page.wait_for(
        _applied_on_server(
            job_id,
            "null",
        )
    )


def test_a_queue_row_can_record_an_application(
    page,
) -> None:
    """Recording an application used to mean an undiscoverable
    keystroke or a round trip through a spreadsheet, which is why the
    spreadsheet existed at all."""

    job_id = _first_unapplied(
        page
    )

    try:
        _mark_applied(
            page,
            job_id,
        )
    finally:
        _clear_applied(
            page,
            job_id,
        )


def test_a_just_applied_row_survives_a_reload(
    page,
) -> None:
    """The default sort sinks applied jobs to the bottom of a queue
    thousands long, so the next load would drop the row off the page
    entirely and the click would read as the job vanishing."""

    job_id = _first_unapplied(
        page
    )

    try:
        _mark_applied(
            page,
            job_id,
        )

        page.eval(
            "loadJobs()"
        )

        page.wait_for(
            "!state.loading"
        )

        assert page.eval(
            "state.items.some(function(j){"
            f"return j.id==={job_id};}})"
        ), "the row left the screen when it was marked"

        assert "Applied" in page.text(
            f'.row[data-id="{job_id}"] '
            ".c-status"
        )
    finally:
        _clear_applied(
            page,
            job_id,
        )


def test_the_exported_sheet_keeps_its_columns(
    page,
) -> None:
    """The export exists to drop into a tracker the user already keeps.
    Renaming a column turns it into a file they have to fix first."""

    header = page.eval(
        "fetch('/api/applications"
        "/export.csv')"
        ".then(function(r){"
        "return r.text();})"
        ".then(function(t){"
        "return t.split('\\n')[0]"
        ".trim();})"
    )

    assert header == (
        "Company Name,Role Title,Type,"
        "Date Applied,Status,Link"
    )


def test_the_applied_page_offers_the_sheet(
    page,
) -> None:
    """Exporting is what makes marking in ACE a replacement for the
    spreadsheet rather than a second place to keep the same list."""

    page.eval(
        'goTo("applied")'
    )

    page.wait_for(
        "state.page==='applied' "
        "&& !state.loading"
    )

    assert page.eval(
        "(function(){var a=document"
        ".querySelector("
        "'a[href*=\"export.csv\"]');"
        "return a ? a.getAttribute"
        "('href') : '';})()"
    ).endswith(
        "/api/applications/export.csv"
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
