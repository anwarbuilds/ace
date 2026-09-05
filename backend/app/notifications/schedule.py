"""Digest window scheduling for ACE notifications.

This module owns *when* a digest is allowed to be delivered.

It is deliberately pure:

    - no database access
    - no SMTP access
    - no reads of the current clock

Every function receives the reference instant explicitly so digest
scheduling stays deterministic and unit-testable.

Window semantics
----------------

Digest windows are expressed as local wall-clock times in a configured
IANA timezone.

Window ``i`` is open from its own configured time until the next
configured time on the same local day. The final window of a day closes
at local midnight.

Therefore:

    - at most one window is open at any instant
    - at most ``len(times)`` windows exist per local calendar day
    - no window is open between local midnight and the first configured
      time

That last property is what bounds ACE to at most one or two digest
emails per local calendar day, even across process restarts.
"""

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)


MAX_DIGEST_WINDOWS_PER_DAY = 2


DISPLAY_LABELS_BY_COUNT: dict[
    int,
    tuple[str, ...],
] = {
    1: (
        "Daily",
    ),
    2: (
        "Morning",
        "Evening",
    ),
}


def parse_digest_times(
    raw_value: str,
) -> tuple[time, ...]:
    """Parse a comma-separated HH:MM digest window configuration.

    Returns:
        Sorted, unique window times.

    Raises:
        ValueError: when the configuration is empty, malformed, or
            declares more windows than ACE permits per day.
    """

    normalized = raw_value.strip()

    if not normalized:
        raise ValueError(
            (
                "NOTIFICATION_DIGEST_TIMES "
                "must declare at least one "
                "HH:MM window."
            )
        )

    parsed_times: list[time] = []

    for token in normalized.split(
        ","
    ):
        candidate = token.strip()

        if not candidate:
            raise ValueError(
                (
                    "NOTIFICATION_DIGEST_TIMES "
                    "contains an empty window "
                    "entry."
                )
            )

        try:
            parsed = datetime.strptime(
                candidate,
                "%H:%M",
            ).time()

        except ValueError as exc:
            raise ValueError(
                (
                    "NOTIFICATION_DIGEST_TIMES "
                    "entries must use 24-hour "
                    f"HH:MM format: "
                    f"{candidate!r}."
                )
            ) from exc

        parsed_times.append(
            parsed
        )

    unique_times = sorted(
        set(
            parsed_times
        )
    )

    if len(unique_times) != len(
        parsed_times
    ):
        raise ValueError(
            (
                "NOTIFICATION_DIGEST_TIMES "
                "must not repeat the same "
                "window time."
            )
        )

    if (
        len(unique_times)
        > MAX_DIGEST_WINDOWS_PER_DAY
    ):
        raise ValueError(
            (
                "NOTIFICATION_DIGEST_TIMES "
                "must declare at most "
                f"{MAX_DIGEST_WINDOWS_PER_DAY} "
                "windows per day."
            )
        )

    return tuple(
        unique_times
    )


@dataclass(
    frozen=True,
    slots=True,
)
class DigestWindow:
    """One concrete digest delivery window on one local calendar day."""

    local_date: date

    window_index: int

    display_label: str

    opens_at: datetime

    closes_at: datetime

    @property
    def window_label(
        self,
    ) -> str:
        """Return the durable index-based window identifier.

        The label is index-based rather than time-based so that adjusting
        a configured window time by a few minutes does not create a
        second deliverable window on the same day.
        """

        return f"w{self.window_index}"

    def digest_key(
        self,
        *,
        recipient: str,
    ) -> str:
        """Return the globally unique identity of this digest.

        This value is protected by a UNIQUE database constraint and is
        what makes digest delivery restart-safe.
        """

        normalized_recipient = (
            recipient.strip().casefold()
        )

        if not normalized_recipient:
            raise ValueError(
                (
                    "recipient must not be "
                    "empty."
                )
            )

        return (
            f"{self.local_date.isoformat()}"
            f":{self.window_label}"
            f":{normalized_recipient}"
        )


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    """Require an aware datetime and normalize it to UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            (
                f"{field_name} must be "
                "timezone-aware."
            )
        )

    return value.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class DigestWindowSchedule:
    """Configured digest delivery windows for one ACE deployment."""

    timezone_name: str

    times: tuple[time, ...]

    def __post_init__(self) -> None:
        """Validate the configured schedule."""

        if not self.times:
            raise ValueError(
                (
                    "A digest schedule must "
                    "declare at least one "
                    "window."
                )
            )

        if len(self.times) > (
            MAX_DIGEST_WINDOWS_PER_DAY
        ):
            raise ValueError(
                (
                    "A digest schedule must "
                    "declare at most "
                    f"{MAX_DIGEST_WINDOWS_PER_DAY} "
                    "windows per day."
                )
            )

        if list(self.times) != sorted(
            set(
                self.times
            )
        ):
            raise ValueError(
                (
                    "Digest window times must "
                    "be unique and sorted."
                )
            )

        try:
            ZoneInfo(
                self.timezone_name
            )

        except (
            ZoneInfoNotFoundError,
            ValueError,
        ) as exc:
            raise ValueError(
                (
                    "Digest timezone is not a "
                    "known IANA timezone: "
                    f"{self.timezone_name!r}."
                )
            ) from exc

    @property
    def zone(
        self,
    ) -> ZoneInfo:
        """Return the configured timezone."""

        return ZoneInfo(
            self.timezone_name
        )

    @property
    def window_count(
        self,
    ) -> int:
        """Return the number of windows configured per local day."""

        return len(
            self.times
        )

    def _display_label(
        self,
        window_index: int,
    ) -> str:
        """Return a human-readable label for one window index."""

        labels = (
            DISPLAY_LABELS_BY_COUNT.get(
                self.window_count
            )
        )

        if (
            labels is not None
            and window_index
            < len(labels)
        ):
            return labels[
                window_index
            ]

        return (
            "Digest "
            f"{window_index + 1}"
        )

    def _to_utc(
        self,
        local_date: date,
        local_time: time,
    ) -> datetime:
        """Convert a local wall-clock time into a UTC instant."""

        local_datetime = datetime.combine(
            local_date,
            local_time,
            tzinfo=self.zone,
        )

        return local_datetime.astimezone(
            timezone.utc
        )

    def _build_window(
        self,
        *,
        local_date: date,
        window_index: int,
    ) -> DigestWindow:
        """Build one concrete window for a local calendar day."""

        opens_at = self._to_utc(
            local_date,
            self.times[
                window_index
            ],
        )

        is_last_window = (
            window_index
            == self.window_count - 1
        )

        if is_last_window:
            closes_at = self._to_utc(
                local_date
                + timedelta(
                    days=1
                ),
                time(
                    0,
                    0,
                ),
            )

        else:
            closes_at = self._to_utc(
                local_date,
                self.times[
                    window_index + 1
                ],
            )

        return DigestWindow(
            local_date=local_date,
            window_index=window_index,
            display_label=(
                self._display_label(
                    window_index
                )
            ),
            opens_at=opens_at,
            closes_at=closes_at,
        )

    def resolve_active_window(
        self,
        *,
        now: datetime,
    ) -> DigestWindow | None:
        """Return the digest window open at ``now``, if any.

        Returns None between local midnight and the first configured
        window time. During that period ACE deliberately has no
        deliverable window, which is what caps daily digest volume.
        """

        normalized_now = (
            _require_aware_datetime(
                now,
                field_name="now",
            )
        )

        local_now = (
            normalized_now.astimezone(
                self.zone
            )
        )

        local_time = local_now.time()

        active_index: int | None = None

        for index, window_time in enumerate(
            self.times
        ):
            if local_time >= window_time:
                active_index = index

            else:
                break

        if active_index is None:
            return None

        return self._build_window(
            local_date=local_now.date(),
            window_index=active_index,
        )

    def next_window_opens_at(
        self,
        *,
        now: datetime,
    ) -> datetime:
        """Return when the next digest window opens after ``now``."""

        normalized_now = (
            _require_aware_datetime(
                now,
                field_name="now",
            )
        )

        local_now = (
            normalized_now.astimezone(
                self.zone
            )
        )

        for window_index in range(
            self.window_count
        ):
            candidate = self._to_utc(
                local_now.date(),
                self.times[
                    window_index
                ],
            )

            if candidate > normalized_now:
                return candidate

        return self._to_utc(
            local_now.date()
            + timedelta(
                days=1
            ),
            self.times[0],
        )
