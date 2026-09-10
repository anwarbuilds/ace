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


def test_the_more_line_expands_its_group(
    page,
) -> None:
    """It counted what was hidden and did nothing when tapped, which
    is exactly how the user described it: like text, with no action
    on it."""

    _open_filters(
        page
    )

    shown = page.eval(
        "document.querySelectorAll("
        "'.pop-opt[data-addfilter="
        "\"company\"]').length"
    )

    total = page.eval(
        "state.facets.companies.length"
    )

    if total <= shown:
        pytest.skip(
            "no companies are held back"
        )

    page.click(
        '.pop-more[data-expand="company"]'
    )

    assert page.eval(
        "!!document.querySelector('.pop')"
    ), "expanding closed the menu"

    assert page.eval(
        "document.querySelectorAll("
        "'.pop-opt[data-addfilter="
        "\"company\"]').length"
    ) == total, "the group did not open"

    # One group at a time: opening the whole menu at once buries the
    # sources and families under 169 companies.
    assert page.eval(
        "document.querySelectorAll("
        "'.pop-opt[data-exclude]').length"
    ) == shown


def test_a_filter_offered_never_empties_the_queue(
    page,
) -> None:
    """Counts were taken over the whole corpus, so with a tier filter
    on, the menu offered companies that filter had already removed.
    Choosing one showed nothing, which reads as the tap doing nothing
    at all."""

    before = page.eval(
        "state.total"
    )

    page.click(
        '[data-tier="BIG_TECH"]'
    )

    # Waiting on `!state.loading` alone is a race: the flag is still
    # false from the previous load until loadJobs actually starts, so
    # the assertions below would read the numbers from before the tap.
    page.wait_for(
        "!state.loading && "
        "state.tiers[0]==='BIG_TECH' && "
        "state.total!==" + str(
            before
        )
    )

    total = page.eval(
        "state.total"
    )

    assert total > 0

    assert page.eval(
        "state.facets.companies"
        ".reduce(function(a,b){"
        "return a+b.count;},0)"
    ) == total, (
        "the menu counts more rows than the queue holds"
    )

    _open_filters(
        page
    )

    picked = page.eval(
        "(function(){var b=document"
        ".querySelectorAll('.pop-opt"
        "[data-addfilter=\"company\"]');"
        "if(!b.length) return '';"
        "b[b.length-1].click();"
        "return b[b.length-1]"
        ".dataset.value;})()"
    )

    assert picked, "no company was offered"

    page.wait_for(
        "!state.loading && "
        "state.total!==" + str(
            total
        )
    )

    assert page.eval(
        "state.total"
    ) > 0, f"choosing {picked} emptied the queue"

    page.click(
        '[data-tier="BIG_TECH"]'
    )


# --- pages load -------------------------------------------------------


@pytest.mark.parametrize(
    "page_name,marker",
    [
        ("pulls", ".pl-day"),
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


def test_every_check_is_logged_and_jobs_hide_behind_a_click(
    page,
) -> None:
    """A log that hides its quiet entries cannot answer "was ACE
    running at 3am", and one that expands every entry is a wall."""

    page.eval(
        'goTo("pulls")'
    )

    page.wait_for(
        "document.querySelectorAll"
        "('.pl-row').length>0"
    )

    rows = page.eval(
        "document.querySelectorAll"
        "('.pl-row').length"
    )

    assert rows == page.eval(
        "state.sessions.length"
    ), "checks that found nothing were dropped from the log"

    assert page.eval(
        "document.querySelectorAll"
        "('.pl-jobs').length"
    ) == 0, "jobs were shown before anything was clicked"

    if not page.eval(
        "document.querySelectorAll"
        "('.pl-row:not(:disabled)')"
        ".length"
    ):
        pytest.skip(
            "no check found a job to expand"
        )

    page.click(
        ".pl-row:not(:disabled)"
    )

    assert page.eval(
        "document.querySelectorAll"
        "('.pl-jobs .row').length"
    ) > 0, "expanding a check showed no jobs"

    page.click(
        ".pl-run.open .pl-row"
    )

    assert page.eval(
        "document.querySelectorAll"
        "('.pl-jobs').length"
    ) == 0, "clicking again did not collapse it"


def test_the_control_bar_separates_its_groups(
    page,
) -> None:
    """The labels ran straight into their chips, which is what made
    the bar unreadable. Measured rather than eyeballed, because the
    cause was CSS that never applied at all."""

    assert page.eval(
        "getComputedStyle(document"
        ".querySelector('.ctl-grp')).gap"
    ) == "6px"

    assert page.eval(
        "(function(){var l=document"
        ".querySelector('.ctl-label');"
        "var c=l.nextElementSibling;"
        "return Math.round("
        "c.getBoundingClientRect().left"
        "-l.getBoundingClientRect()"
        ".right);})()"
    ) >= 4, "the label is touching its first chip"


def test_the_queue_offers_one_way_back(
    page,
) -> None:
    """Clear all was only rendered when a chip happened to exist, so a
    tier filter left no single way back to the full queue."""

    before = page.eval(
        "state.total"
    )

    page.click(
        '[data-tier="BIG_TECH"]'
    )

    page.wait_for(
        "!state.loading && "
        "state.total!==" + str(
            before
        )
    )

    page.click(
        '[data-act="clearfilters"]'
    )

    page.wait_for(
        "!state.loading && "
        "state.tiers.length===0 && "
        "state.total===" + str(
            before
        )
    )


def test_a_company_that_reposts_one_role_collapses(
    page,
) -> None:
    """Sierra posts one role across nine industries and TikTok posts
    graduate roles across dozens of teams. Nine near-identical rows to
    realize they are one decision is the noise the user reported, and
    a company with an application limit needs one row to choose from,
    not nine separate ones."""

    group = page.eval(
        "(function(){"
        "var g=jobGroups();"
        "var k=Object.keys(g).filter("
        "function(x){return g[x].length"
        ">=GROUP_MIN;})[0];"
        "return k||null;})()"
    )

    if not group:
        pytest.skip(
            "no repeated-role group in "
            "the current queue"
        )

    assert page.eval(
        "!!document.querySelector"
        "('.grp-head')"
    ), "a group exists in state but no header row was rendered"

    expected_groups = page.eval(
        "Object.keys(jobGroups())"
        ".filter(function(k){"
        "return jobGroups()[k].length"
        ">=GROUP_MIN;}).length"
    )

    assert page.eval(
        "document.querySelectorAll"
        "('.grp-head').length"
    ) == expected_groups, (
        "a group was rendered more than "
        "once, which happens if a later "
        "member of the same group is not "
        "recognised as already shown"
    )

    before = page.eval(
        "document.querySelectorAll"
        "('.grp-member').length"
    )

    assert before == 0, (
        "a group started expanded"
    )

    page.click(
        ".grp-head"
    )

    after = page.eval(
        "document.querySelectorAll"
        "('.grp-member').length"
    )

    assert after >= 3, (
        "expanding a group showed "
        "fewer than the members it "
        "claimed"
    )

    assert page.eval(
        "(function(){var m=document"
        ".querySelector('.grp-member');"
        "return !!m.querySelector("
        "'[data-mark=\"applied\"]');"
        "})()"
    ), "an expanded member lost its own action buttons"

    page.click(
        ".grp-head"
    )

    assert page.eval(
        "document.querySelectorAll"
        "('.grp-member').length"
    ) == 0, "collapsing again left members visible"


def test_keyboard_navigation_skips_hidden_group_members(
    page,
) -> None:
    """Selecting a job hidden inside a collapsed group used to move
    the highlight to a row that was not on screen, which read as the
    key doing nothing. Walking "next" across the whole list is what
    actually exercises this: the old code, indexing raw item order,
    would eventually land on every id including the hidden ones."""

    all_ids = page.eval(
        "state.items.map("
        "function(j){return j.id;})"
    )

    visible_ids = page.eval(
        "visibleItemIds()"
    )

    hidden = [
        i
        for i in all_ids
        if i not in visible_ids
    ]

    if not hidden:
        pytest.skip(
            "nothing is currently "
            "collapsed"
        )

    page.eval(
        "state.selectedId=null"
    )

    visited = page.eval(
        "(function(){"
        "var seen=[];"
        f"for(var i=0;i<{len(all_ids)};i++){{"
        "step(1);"
        "seen.push(state.selectedId);"
        "}"
        "return seen;})()"
    )

    hit = set(
        visited
    ) & set(
        hidden
    )

    assert not hit, (
        "stepping through the queue "
        f"selected hidden id(s) {hit}"
    )


def test_activity_history_reaches_past_the_first_page(
    page,
) -> None:
    """The log was hard-capped at the newest 100 runs with nothing
    past that reachable, which on a busy day is barely more than a
    single day of the log the page claims to be."""

    page.eval(
        'goTo("pulls")'
    )

    page.wait_for(
        "document.querySelectorAll"
        "('.pl-row').length>0"
    )

    if page.eval(
        "state.sessionsExhausted"
    ):
        pytest.skip(
            "fewer than 30 sessions "
            "recorded, nothing to page"
        )

    before = page.eval(
        "state.sessions.length"
    )

    oldest_before = page.eval(
        "state.sessions"
        "[state.sessions.length-1]"
        ".started_at"
    )

    page.click(
        ".pl-loadmore"
    )

    page.wait_for(
        "state.sessions.length>"
        + str(
            before
        )
    )

    oldest_after = page.eval(
        "state.sessions"
        "[state.sessions.length-1]"
        ".started_at"
    )

    assert page.eval(
        "new Date(" + repr(
            oldest_after
        ).replace(
            "'",
            '"',
        )
        + ")<new Date(" + repr(
            oldest_before
        ).replace(
            "'",
            '"',
        )
        + ")"
    ), "loading older activity did not reach further back in time"


def test_the_activity_sidebar_shows_real_source_counts(
    page,
) -> None:
    """The log column left the rest of the page empty on anything
    past a laptop screen."""

    page.eval(
        'goTo("pulls")'
    )

    page.wait_for(
        "!!document.querySelector"
        "('.pl-side')"
    )

    rows = page.eval(
        "document.querySelectorAll"
        "('.pl-side-row').length"
    )

    assert rows == page.eval(
        "(state.facets.sources||[])"
        ".length"
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


# --- sheet sync -------------------------------------------------------


def _seed_import(
    page,
    status,
    candidates=2,
):
    """Put one row of the given status into the import dialog."""

    page.eval(
        """
        (function(){
          var cands=[];
          for(var i=0;i<"""
        + str(
            candidates
        )
        + """;i++){
            cands.push({job_id:100+i,company:'Stripe',
              title:'Software Engineer, New Grad',
              location:'City '+i});
          }
          state.importChoice={};
          state.keepExternal=false;
          state.importData={total:1,
            counts:{matched:0,recorded:0,ambiguous:0,
              unmatched:0,unusable:0},
            rows:[{row_number:1,status:'"""
        + status
        + """',
              method:'already kept as history',job_id:null,
              company:'Stripe',
              title:'Software Engineer, New Grad',
              applied_on:'2026-03-04',
              application_status:'applied',
              candidates:cands}]};
          state.importData.counts['"""
        + status
        + """']=1;
          renderImport();
          return 'ok';
        })()
        """
    )


def test_a_recorded_row_is_not_presented_as_a_question(
    page,
) -> None:
    """The whole point of the RECORDED status, seen from the page.

    ACE asked about the same 42 rows on every upload of one real sheet,
    every one of which it had already recorded. The dialog must say so
    rather than counting them as work.
    """

    _seed_import(
        page,
        "recorded",
    )

    body = page.eval(
        "document.querySelector"
        "('.sheet').innerText"
    )

    assert (
        "already yours"
        in body
    )

    assert (
        "Already in ACE as history"
        in body
    )

    # It is carried into the sync without being ticked, and it is not
    # counted among the rows that still need an answer.
    assert page.eval(
        "recordedRows().length"
    ) == 1

    assert page.eval(
        "unplaceableRows().length"
    ) == 0

    page.eval(
        "closeImport()"
    )


def test_a_genuinely_new_row_is_still_a_question(
    page,
) -> None:
    """Settling must be keyed on history, not applied to everything."""

    _seed_import(
        page,
        "ambiguous",
    )

    assert page.eval(
        "recordedRows().length"
    ) == 0

    assert page.eval(
        "unplaceableRows().length"
    ) == 1

    page.eval(
        "closeImport()"
    )


def test_a_recorded_row_can_still_be_attached_to_a_posting(
    page,
) -> None:
    """Settled is not closed: the option has to survive."""

    _seed_import(
        page,
        "recorded",
    )

    assert page.eval(
        "document.querySelectorAll"
        "('[data-improw]').length"
    ) == 1

    # Choosing a posting moves it out of the history bucket, so it is
    # attached to the job rather than refreshed as a placeholder.
    page.eval(
        "state.importChoice[1]=100;"
    )

    assert page.eval(
        "recordedRows().length"
    ) == 0

    page.eval(
        "closeImport()"
    )


# --- the answer bank ---------------------------------------------------


def _open_answers(
    page,
) -> None:
    """Show the answers editor."""

    page.eval(
        'goTo("answers")'
    )

    page.wait_for(
        "document.querySelectorAll"
        "('.ans-edit').length > 10"
    )


def test_a_yes_no_question_is_two_buttons(
    page,
) -> None:
    """The complaint that rewrote the bank.

    Every question used to be a text box, so answering "are you at
    least 18 years old" meant typing the word Yes, and answering "how
    did you hear about us" meant guessing which wording some future
    form would print.
    """

    _open_answers(
        page
    )

    assert page.eval(
        "document.querySelectorAll"
        "('.ans-yn').length"
    ) > 10

    assert page.eval(
        "document.querySelectorAll"
        "('select.ans-value').length"
    ) > 3


def test_a_name_is_still_a_text_box(
    page,
) -> None:
    """Only the questions with known answers became controls."""

    _open_answers(
        page
    )

    assert page.eval(
        """(function(){
          var rows=document.querySelectorAll('.ans-edit');
          for(var i=0;i<rows.length;i++){
            var n=rows[i].querySelector('.ans-name');
            if(n&&n.textContent.indexOf('Full name')===0){
              return !!rows[i].querySelector('textarea.ans-value');
            }
          }
          return false;
        })()"""
    )


def test_a_catalogue_question_cannot_be_renamed(
    page,
) -> None:
    """The label is the key the extension's rules resolve to.

    Letting it be edited would break the match that finds the question
    on a form, silently and only on the next application.
    """

    _open_answers(
        page
    )

    assert page.eval(
        "document.querySelectorAll"
        "('input.ans-label[type=text]').length"
    ) == 0


def test_pressing_a_toggle_is_what_gets_saved(
    page,
) -> None:
    """What the page shows and what a save reads must not drift."""

    _open_answers(
        page
    )

    assert page.eval(
        """(function(){
          var rows=document.querySelectorAll('.ans-edit');
          for(var i=0;i<rows.length;i++){
            var n=rows[i].querySelector('.ans-name');
            if(n&&n.textContent.indexOf('Criminal conviction')===0){
              rows[i].querySelector('button[data-val=No]').click();
              return rows[i].querySelector('.ans-value').value;
            }
          }
          return 'row not found';
        })()"""
    ) == "No"

    # Read back through the same function a save uses, rather than by
    # reading the button again: the hidden value is what is submitted.
    assert page.eval(
        """(function(){
          var all=collectAnswers();
          for(var i=0;i<all.length;i++){
            if(all[i].label==='Criminal conviction') return all[i].value;
          }
          return 'missing';
        })()"""
    ) == "No"
