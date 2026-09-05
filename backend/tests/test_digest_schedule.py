"""Tests for ACE digest window scheduling.

Window identity is what bounds ACE to one or two emails per day, so the
boundaries are tested explicitly.
"""

from datetime import (
    datetime,
    time,
    timezone,
)
from zoneinfo import ZoneInfo

import pytest

from backend.app.notifications.schedule import (
    DigestWindowSchedule,
    parse_digest_times,
)


PACIFIC = ZoneInfo(
    "America/Los_Angeles"
)


def schedule(
    raw: str = "07:30,17:30",
    timezone_name: str = (
        "America/Los_Angeles"
    ),
) -> DigestWindowSchedule:
    """Build a schedule from configuration text."""

    return DigestWindowSchedule(
        timezone_name=timezone_name,
        times=parse_digest_times(
            raw
        ),
    )


def at_local(
    hour: int,
    minute: int = 0,
    *,
    day: int = 5,
) -> datetime:
    """Return a UTC instant for a Pacific wall-clock time."""

    return datetime(
        2026,
        9,
        day,
        hour,
        minute,
        tzinfo=PACIFIC,
    ).astimezone(
        timezone.utc
    )


# ----------------------------------------------------------------------
# Configuration parsing
# ----------------------------------------------------------------------


def test_single_window_is_valid() -> None:
    assert parse_digest_times(
        "08:00"
    ) == (
        time(
            8,
            0,
        ),
    )


def test_two_windows_are_sorted() -> None:
    assert parse_digest_times(
        "18:00, 06:45"
    ) == (
        time(
            6,
            45,
        ),
        time(
            18,
            0,
        ),
    )


def test_three_windows_are_rejected() -> None:
    """More than two windows would break the daily volume promise."""

    with pytest.raises(
        ValueError
    ):
        parse_digest_times(
            "06:00,12:00,18:00"
        )


def test_duplicate_windows_are_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        parse_digest_times(
            "08:00,08:00"
        )


def test_empty_configuration_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        parse_digest_times(
            "   "
        )


@pytest.mark.parametrize(
    "raw",
    [
        "8am",
        "25:00",
        "08:70",
        "08-00",
        "",
    ],
)
def test_malformed_times_are_rejected(
    raw: str,
) -> None:
    with pytest.raises(
        ValueError
    ):
        parse_digest_times(
            raw
        )


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        DigestWindowSchedule(
            timezone_name=(
                "Mars/Olympus_Mons"
            ),
            times=(
                time(
                    8,
                    0,
                ),
            ),
        )


# ----------------------------------------------------------------------
# Window resolution
# ----------------------------------------------------------------------


def test_no_window_before_first_configured_time() -> None:
    """Nothing is deliverable between midnight and the first window."""

    assert (
        schedule().resolve_active_window(
            now=at_local(
                5
            )
        )
        is None
    )


def test_morning_window_opens_on_time() -> None:
    window = (
        schedule().resolve_active_window(
            now=at_local(
                7,
                30,
            )
        )
    )

    assert window is not None

    assert window.window_label == "w0"

    assert (
        window.display_label
        == "Morning"
    )


def test_morning_window_stays_open_until_evening() -> None:
    window = (
        schedule().resolve_active_window(
            now=at_local(
                17,
                29,
            )
        )
    )

    assert window is not None

    assert window.window_label == "w0"


def test_evening_window_opens_at_its_time() -> None:
    window = (
        schedule().resolve_active_window(
            now=at_local(
                17,
                30,
            )
        )
    )

    assert window is not None

    assert window.window_label == "w1"

    assert (
        window.display_label
        == "Evening"
    )


def test_evening_window_stays_open_until_midnight() -> None:
    window = (
        schedule().resolve_active_window(
            now=at_local(
                23,
                59,
            )
        )
    )

    assert window is not None

    assert window.window_label == "w1"


def test_single_window_schedule_uses_daily_label() -> None:
    window = (
        schedule(
            "09:00"
        ).resolve_active_window(
            now=at_local(
                12
            )
        )
    )

    assert window is not None

    assert (
        window.display_label
        == "Daily"
    )

    assert window.window_label == "w0"


def test_exactly_two_windows_exist_per_day() -> None:
    """Across a whole day only two distinct windows are reachable."""

    sut = schedule()

    labels = set()

    for hour in range(
        24
    ):
        for minute in (
            0,
            30,
        ):
            window = (
                sut.resolve_active_window(
                    now=at_local(
                        hour,
                        minute,
                    )
                )
            )

            if window is not None:
                labels.add(
                    window.window_label
                )

    assert labels == {
        "w0",
        "w1",
    }


# ----------------------------------------------------------------------
# Digest identity
# ----------------------------------------------------------------------


def test_digest_key_is_stable_within_a_window() -> None:
    """Two instants inside one window share one durable identity."""

    sut = schedule()

    first = sut.resolve_active_window(
        now=at_local(
            8
        )
    )

    second = sut.resolve_active_window(
        now=at_local(
            16
        )
    )

    assert first is not None
    assert second is not None

    assert first.digest_key(
        recipient="a@b.com"
    ) == second.digest_key(
        recipient="a@b.com"
    )


def test_digest_key_differs_across_windows() -> None:
    sut = schedule()

    morning = sut.resolve_active_window(
        now=at_local(
            8
        )
    )

    evening = sut.resolve_active_window(
        now=at_local(
            18
        )
    )

    assert morning is not None
    assert evening is not None

    assert morning.digest_key(
        recipient="a@b.com"
    ) != evening.digest_key(
        recipient="a@b.com"
    )


def test_digest_key_differs_across_days() -> None:
    sut = schedule()

    today = sut.resolve_active_window(
        now=at_local(
            8,
            day=5,
        )
    )

    tomorrow = sut.resolve_active_window(
        now=at_local(
            8,
            day=6,
        )
    )

    assert today is not None
    assert tomorrow is not None

    assert today.digest_key(
        recipient="a@b.com"
    ) != tomorrow.digest_key(
        recipient="a@b.com"
    )


def test_digest_key_differs_across_recipients() -> None:
    """Two people must never share one digest identity."""

    window = (
        schedule().resolve_active_window(
            now=at_local(
                8
            )
        )
    )

    assert window is not None

    assert window.digest_key(
        recipient="a@b.com"
    ) != window.digest_key(
        recipient="c@d.com"
    )


def test_digest_key_normalizes_recipient_case() -> None:
    window = (
        schedule().resolve_active_window(
            now=at_local(
                8
            )
        )
    )

    assert window is not None

    assert window.digest_key(
        recipient="A@B.com"
    ) == window.digest_key(
        recipient="a@b.com"
    )


def test_window_label_survives_small_time_changes() -> None:
    """Nudging a window time must not create a second daily digest."""

    original = (
        schedule(
            "07:30,17:30"
        ).resolve_active_window(
            now=at_local(
                9
            )
        )
    )

    adjusted = (
        schedule(
            "08:00,17:30"
        ).resolve_active_window(
            now=at_local(
                9
            )
        )
    )

    assert original is not None
    assert adjusted is not None

    assert original.digest_key(
        recipient="a@b.com"
    ) == adjusted.digest_key(
        recipient="a@b.com"
    )


# ----------------------------------------------------------------------
# Timezone behavior
# ----------------------------------------------------------------------


def test_windows_follow_configured_timezone() -> None:
    """The same instant sits in different windows per timezone."""

    instant = datetime(
        2026,
        9,
        5,
        15,
        0,
        tzinfo=timezone.utc,
    )

    pacific = schedule(
        "07:30,17:30",
        "America/Los_Angeles",
    ).resolve_active_window(
        now=instant
    )

    # 15:00 UTC is 08:00 Pacific but 20:30 in Kolkata.
    kolkata = schedule(
        "07:30,17:30",
        "Asia/Kolkata",
    ).resolve_active_window(
        now=instant
    )

    assert pacific is not None
    assert kolkata is not None

    assert pacific.window_label == "w0"

    assert kolkata.window_label == "w1"


def test_next_window_opens_at_first_time_tomorrow() -> None:
    """After the last window closes, the next one is tomorrow."""

    sut = schedule()

    next_open = sut.next_window_opens_at(
        now=at_local(
            23
        )
    )

    assert (
        next_open.astimezone(
            PACIFIC
        ).hour
        == 7
    )

    assert (
        next_open.astimezone(
            PACIFIC
        ).day
        == 6
    )


def test_naive_now_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        schedule().resolve_active_window(
            now=datetime(
                2026,
                9,
                5,
                8,
            )
        )
