"""Gentler with Workday, and no board left behind (2026-11-17).

Workday began answering most of ACE's requests with 429 on 2026-11-16.
These tests hold the four safety steps: one shared pause for the platform,
no instant repeat of a refused page, fewer boards at once, big boards less
often; plus details reused instead of fetched on every read. Every board,
company and posting here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from backend.app.adapters import workday as workday_module
from backend.app.adapters.workday import StoredDetail, detail_refresh_due, fetch_workday_jobs
from backend.app.scheduling import runtime as runtime_module
from backend.app.scheduling.registry import SourceRegistry
from backend.app.scheduling.runtime import SchedulerRuntime
from backend.app.scheduling.types import SourceDefinition, SourceType


HOST = "fabrikam.wd5.myworkdayjobs.example"
ACCOUNT = "fabrikam/External"
REFERENCE = datetime(2026, 11, 17, 4, 30, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def workday(account: str, interval: int = 900) -> SourceDefinition:
    return SourceDefinition(
        source_type=SourceType.WORKDAY,
        source_account=f"{account}/External",
        source_host=f"{account}.wd5.myworkdayjobs.example",
        company_name=account.title(),
        enabled=True,
        poll_interval_seconds=interval,
    )


def greenhouse(account: str) -> SourceDefinition:
    return SourceDefinition(
        source_type=SourceType.GREENHOUSE,
        source_account=account,
        company_name=account.title(),
        enabled=True,
        poll_interval_seconds=900,
    )


def refusal(status: int = 429) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"https://{HOST}/wday/cxs/fabrikam/External/jobs")
    return httpx.HTTPStatusError(str(status), request=request, response=httpx.Response(status, request=request))


def result(fetched: int = 10):
    return SimpleNamespace(
        fetched_count=fetched,
        evaluated_count=0,
        alert_candidate_count=0,
        stale_suppressed_count=0,
        queued_notification_count=0,
    )


def runtime_for(sources, poller, clock) -> SchedulerRuntime:
    return SchedulerRuntime(
        registry=SourceRegistry(tuple(sources)),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
    )


def test_a_few_refusals_pause_all_of_workday_and_no_board_is_dropped() -> None:
    clock = Clock()
    names = ("alder", "birch", "cedar", "dogwood", "elder", "fir", "ginkgo", "hazel")
    boards = [workday(name) for name in names]
    polled: list[str] = []
    workday_answers = {"refuse": True}

    def poller(source):
        polled.append(source.source_account)
        if source.source_type == SourceType.WORKDAY and workday_answers["refuse"]:
            raise refusal()
        return result()

    runtime = runtime_for([*boards, greenhouse("elm")], poller, clock)

    # Workday boards refused: after three, all of Workday pauses.
    runtime.run_due_sources()
    assert runtime._lane_paused_until["workday"] == clock.now + runtime_module.LANE_PAUSE_FIRST_SECONDS
    assert "elm" in polled
    waiting = [board.source_account for board in boards if board.source_account not in polled]
    assert waiting, "the pause must stop the rest of Workday"

    # During the pause the other boards wait; none is dropped.
    polled.clear()
    clock.now += 60
    runtime.run_due_sources()
    assert polled == []
    assert all(board.identity in runtime._next_due_at for board in boards)
    # The loop sleeps until the pause ends instead of waking for it.
    assert runtime.seconds_until_next_poll() == runtime_module.LANE_PAUSE_FIRST_SECONDS - 60

    # Pause over: the boards that waited go first, and every one is read.
    workday_answers["refuse"] = False
    clock.now += runtime_module.LANE_PAUSE_FIRST_SECONDS
    runtime.run_due_sources()
    assert polled[: len(waiting)] == waiting
    assert set(waiting) <= set(polled)
    assert "workday" not in runtime._lane_pauses


def test_pauses_grow_while_workday_keeps_refusing_and_start_over_after_it_answers() -> None:
    clock = Clock()
    boards = [workday(name, interval=60) for name in ("alder", "birch", "cedar")]
    answers = {"refuse": True}

    def poller(source):
        if answers["refuse"]:
            raise refusal()
        return result()

    runtime = runtime_for(boards, poller, clock)

    runtime.run_due_sources()
    assert runtime._lane_paused_until["workday"] - clock.now == 600

    clock.now = runtime._lane_paused_until["workday"] + 3600
    runtime.run_due_sources()
    assert runtime._lane_paused_until["workday"] - clock.now == 1200

    # It answers again: the next pause starts short.
    answers["refuse"] = False
    clock.now = runtime._lane_paused_until["workday"] + 3600
    runtime.run_due_sources()
    answers["refuse"] = True
    clock.now += 3600
    runtime.run_due_sources()
    assert runtime._lane_paused_until["workday"] - clock.now == 600


def test_a_refused_workday_board_waits_at_most_an_hour_on_its_own() -> None:
    clock = Clock()
    board = workday("alder")

    def poller(_source):
        raise refusal()

    runtime = runtime_for([board], poller, clock)
    for _ in range(6):
        runtime.run_due_sources()
        clock.now = runtime._next_due_at[board.identity]
    runtime.run_due_sources()
    assert runtime._next_due_at[board.identity] - clock.now == runtime_module.LANE_BOARD_BACKOFF_CAP_SECONDS


def test_a_big_workday_board_is_read_hourly_and_a_small_one_keeps_its_plan() -> None:
    clock = Clock()
    big, small, other = workday("alder"), workday("birch"), greenhouse("elm")
    sizes = {big.identity: 1200, small.identity: 40, other.identity: 1200}

    runtime = runtime_for([big, small, other], lambda source: result(sizes[source.identity]), clock)
    runtime.run_due_sources()

    assert runtime._next_due_at[big.identity] - clock.now == 3600
    assert runtime._next_due_at[small.identity] - clock.now == 900
    assert runtime._next_due_at[other.identity] - clock.now == 900


def test_workday_reads_at_most_three_boards_at_once_by_default() -> None:
    assert runtime_module.PLATFORM_LIMITS["workday"] == 3
    assert workday_module.DEFAULT_CONCURRENCY == 2


# The reader.

def postings(count: int) -> list[dict]:
    return [
        {"title": "Software Engineer", "externalPath": f"/job/Remote/Software-Engineer_R{index:04d}", "postedOn": "Posted Today"}
        for index in range(count)
    ]


def serve(listing, *, list_status=200, detail_status=200, calls=None):
    calls = calls if calls is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            if list_status != 200:
                return httpx.Response(list_status)
            return httpx.Response(200, json={"total": len(listing), "jobPostings": listing})
        if detail_status != 200:
            return httpx.Response(detail_status)
        return httpx.Response(
            200,
            json={"jobPostingInfo": {"jobDescription": "<p>Fresh text</p>", "location": "Denver, CO", "jobReqId": "R1"}},
        )

    return httpx.MockTransport(handler), calls


def read(transport, **kwargs):
    with httpx.Client(transport=transport) as client:
        return fetch_workday_jobs(
            source_account=ACCOUNT,
            company_name="Fabrikam",
            source_host=HOST,
            client=client,
            now=REFERENCE,
            **kwargs,
        )


def test_a_refused_page_is_not_asked_again_at_once() -> None:
    transport, calls = serve(postings(3), list_status=429)
    try:
        read(transport)
    except httpx.HTTPStatusError as error:
        assert error.response.status_code == 429
    else:
        raise AssertionError("a refused page must fail the read")
    assert [method for method, _ in calls] == ["POST"]


def stored(paths):
    return {
        path: StoredDetail("Stored text", "Austin, TX", datetime(2026, 11, 1, tzinfo=timezone.utc), "R9", f"https://{HOST}{path}")
        for path in paths
    }


def test_stored_details_are_reused_and_refreshed_once_a_day() -> None:
    listing = postings(30)
    paths = [posting["externalPath"] for posting in listing]
    due = {path for path in paths if detail_refresh_due(path, REFERENCE)}
    transport, calls = serve(listing)

    jobs = read(transport, known_details=stored(paths))

    fetched = {path for method, path in calls if method == "GET"}
    assert {path.split("/External")[-1] for path in fetched} == due
    by_id = {job.external_id: job for job in jobs}
    for path in paths:
        expected = "Fresh text" if path in due else "Stored text"
        assert by_id[path].description == expected
    reused = next(path for path in paths if path not in due)
    assert by_id[reused].location == "Austin, TX"
    assert by_id[reused].requisition_id == "R9"


def test_every_posting_has_one_refresh_hour_a_day() -> None:
    path = "/job/Remote/Software-Engineer_R0001"
    hours = [
        detail_refresh_due(path, datetime(2026, 11, 17, hour, tzinfo=timezone.utc))
        for hour in range(24)
    ]
    assert hours.count(True) == 1


def test_a_refused_detail_keeps_the_stored_text_and_stops_asking(monkeypatch) -> None:
    # Every posting is due a fresh detail this hour.
    monkeypatch.setattr(workday_module, "DETAIL_REFRESH_HOURS", 1)
    listing = postings(30)
    paths = [posting["externalPath"] for posting in listing]
    transport, calls = serve(listing, detail_status=429)

    jobs = read(transport, known_details=stored(paths))

    gets = [path for method, path in calls if method == "GET"]
    assert 1 <= len(gets) <= 3
    assert all(job.description == "Stored text" for job in jobs)


def test_workday_keeps_being_read_while_it_still_answers_some_requests() -> None:
    """On 2026-11-17 Workday answered about half: refusals then pause boards, not the platform."""
    clock = Clock()
    boards = [workday(name, interval=60) for name in ("alder", "birch", "cedar", "dogwood", "elder", "fir")]
    answers = {"alder/External": True, "birch/External": False, "cedar/External": False,
               "dogwood/External": False, "elder/External": True, "fir/External": False}
    polled: list[str] = []

    def poller(source):
        polled.append(source.source_account)
        if not answers[source.source_account]:
            raise refusal()
        return result()

    runtime = runtime_for(boards, poller, clock)
    for _ in range(3):
        runtime.run_due_sources()
        clock.now += 61

    assert "workday" not in runtime._lane_paused_until
    assert {"alder/External", "elder/External"} <= set(polled)
    # Each refused board backs off on its own.
    assert runtime._refusals[boards[1].identity] >= 1


# The speed limit, quick reads and order (2026-11-17, second refinement).

from datetime import timedelta  # noqa: E402

from backend.app.adapters.workday import QUICK_READ_PAGES, WorkdayPace  # noqa: E402
from backend.app.scheduling.dispatcher import WORKDAY_FULL_READ_EVERY, WorkdaySourceFetcher  # noqa: E402


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_pace_spaces_requests_and_follows_workdays_answers() -> None:
    fake = FakeTime()
    pace = WorkdayPace(start=6.0, low=1.0, high=12.0, clock=fake.clock, sleep=fake.sleep)
    for _ in range(3):
        pace.wait()
    assert fake.slept == [10.0, 10.0]

    pace.refused()
    assert pace.per_minute == 3.0
    pace.refused(); pace.refused()
    assert pace.per_minute == 1.0  # never below the floor

    for _ in range(WorkdayPace.RAISE_AFTER):
        pace.answered()
    assert pace.per_minute == 1.25
    for _ in range(WorkdayPace.RAISE_AFTER * 30):
        pace.answered()
    assert pace.per_minute == 12.0  # never above the ceiling


def paged_board(total: int, calls: list):
    listing = postings(total)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            import json as _json
            body = _json.loads(request.content)
            page = listing[body["offset"]:body["offset"] + 20]
            return httpx.Response(200, json={"total": total, "jobPostings": page, "facets": []})
        return httpx.Response(200, json={"jobPostingInfo": {"jobDescription": "<p>Text</p>"}})

    return httpx.MockTransport(handler)


def test_a_quick_read_takes_the_newest_pages_and_closes_nothing() -> None:
    calls: list = []
    jobs = read(paged_board(200, calls), quick=True, should_fetch_detail=lambda title: False)
    assert len([c for c in calls if c[0] == "POST"]) == QUICK_READ_PAGES
    assert len(jobs) == QUICK_READ_PAGES * 20
    assert jobs.complete is False

    calls.clear()
    small = read(paged_board(35, calls), quick=True, should_fetch_detail=lambda title: False)
    assert len(small) == 35 and small.complete is True


def test_a_capped_board_is_not_sliced_on_a_quick_read() -> None:
    calls: list = []
    jobs = read(paged_board(2000, calls), quick=True, should_fetch_detail=lambda title: False)
    assert len([c for c in calls if c[0] == "POST"]) == QUICK_READ_PAGES
    assert jobs.complete is False


def test_every_request_waits_on_the_pace_it_is_given() -> None:
    class Recorder:
        def __init__(self) -> None:
            self.waits = 0
            self.statuses: list[int] = []

        def wait(self) -> None:
            self.waits += 1

        def note(self, status: int) -> None:
            self.statuses.append(status)

    pace = Recorder()
    calls: list = []
    read(paged_board(45, calls), pace=pace, should_fetch_detail=lambda title: True, max_detail_fetches=2)
    assert pace.waits == len(calls) == 3 + 2
    assert pace.statuses == [200] * 5


def test_each_board_is_read_in_full_once_a_day_and_quickly_in_between() -> None:
    moments = [REFERENCE]
    seen: list[bool] = []

    def fetcher(**kwargs):
        seen.append(kwargs["quick"])
        assert kwargs["pace"] is not None
        return []

    fetcher_ = WorkdaySourceFetcher(
        fetcher=fetcher,
        clock=lambda: moments[0],
        posted_lookup=lambda source: {},
        detail_lookup=lambda source: {},
    )
    board = workday("alder")
    fetcher_(board)
    moments[0] = REFERENCE + timedelta(hours=3)
    fetcher_(board)
    moments[0] = REFERENCE + WORKDAY_FULL_READ_EVERY
    fetcher_(board)
    moments[0] = REFERENCE + WORKDAY_FULL_READ_EVERY + timedelta(minutes=15)
    fetcher_(board)
    assert seen == [True, True, False, True]


def test_workday_boards_with_matching_roles_go_first_and_none_starve() -> None:
    clock = Clock()
    mine = workday("alder", interval=900)
    other = workday("birch", interval=3600)
    runtime = runtime_for([other, mine], lambda source: result(), clock)
    runtime._next_due_at[other.identity] = clock.now - 600
    runtime._next_due_at[mine.identity] = clock.now - 60
    assert [s.source_account for s in runtime._due_sources(clock.now)] == ["alder/External", "birch/External"]

    runtime._next_due_at[other.identity] = clock.now - 7 * 3600
    assert [s.source_account for s in runtime._due_sources(clock.now)] == ["birch/External", "alder/External"]


def test_the_top_pace_is_set_by_the_scheduler_and_never_passed() -> None:
    fake = FakeTime()
    pace = WorkdayPace(start=6.0, low=1.0, high=120.0, clock=fake.clock, sleep=fake.sleep)
    pace.set_top(150.0)
    for _ in range(WorkdayPace.RAISE_AFTER * 40):
        pace.answered()
    assert pace.per_minute == 150.0
    # Lowering the top lowers the pace at once; a top below the floor keeps the floor.
    pace.set_top(10.0)
    assert pace.per_minute == 10.0
    pace.set_top(0.2)
    assert pace.high == 1.0 and pace.per_minute == 1.0
    # A refusal still halves it, as before.
    pace.set_top(150.0)
    for _ in range(WorkdayPace.RAISE_AFTER * 40):
        pace.answered()
    pace.refused()
    assert pace.per_minute == 75.0
