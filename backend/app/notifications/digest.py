"""Digest rendering for ACE notifications.

One digest groups every alert candidate accumulated during one delivery
window into a single scannable email.

This module is pure. It receives already-selected items and a reference
instant, and returns a transport-neutral message. It performs no
database access, no SMTP access, and never reads the clock.

Ordering
--------

Items are ordered so the most actionable opportunity is first:

    1. role priority   -- primary target families before secondary
    2. eligibility     -- PASS before STRETCH
    3. posting age     -- freshest first, unknown age last
    4. company/title   -- stable alphabetical tie-break

A stable, fully specified ordering matters because the same digest may
be re-rendered on a delivery retry, and the retry should look identical.
"""

from collections.abc import Sequence
from datetime import (
    datetime,
    timezone,
)
from zoneinfo import ZoneInfo

from backend.app.notifications.payload import (
    DigestItem,
)
from backend.app.notifications.renderer import (
    format_relative_age,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


SEPARATOR_WIDTH = 68


ROLE_PRIORITY_ORDER: dict[str, int] = {
    "PRIMARY": 0,
    "SECONDARY": 1,
}


ELIGIBILITY_ORDER: dict[str, int] = {
    "PASS": 0,
    "STRETCH": 1,
}


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


def _sort_key(
    item: DigestItem,
) -> tuple[
    int,
    int,
    int,
    str,
    str,
]:
    """Return the deterministic digest ordering key for one item."""

    priority_rank = (
        ROLE_PRIORITY_ORDER.get(
            item.role_priority.upper(),
            len(ROLE_PRIORITY_ORDER),
        )
    )

    eligibility_rank = (
        ELIGIBILITY_ORDER.get(
            item.eligibility_status.upper(),
            len(ELIGIBILITY_ORDER),
        )
    )

    # Unknown posting age sorts last rather than pretending to be fresh.
    age_rank = (
        item.posting_age_days
        if item.posting_age_days
        is not None
        else 10**6
    )

    return (
        priority_rank,
        eligibility_rank,
        age_rank,
        item.company.casefold(),
        item.title.casefold(),
    )


def sort_digest_items(
    items: Sequence[DigestItem],
) -> tuple[DigestItem, ...]:
    """Order digest items most-actionable first."""

    return tuple(
        sorted(
            items,
            key=_sort_key,
        )
    )


def build_digest_subject(
    *,
    item_count: int,
    window_label: str,
    reference_time: datetime,
    timezone_name: str,
) -> str:
    """Build a scannable digest subject line.

    The subject leads with the count so the inbox itself communicates
    whether the digest is worth opening immediately.
    """

    if item_count < 1:
        raise ValueError(
            (
                "A digest subject requires at "
                "least one item."
            )
        )

    normalized_reference = (
        _require_aware_datetime(
            reference_time,
            field_name="reference_time",
        )
    )

    local_reference = (
        normalized_reference.astimezone(
            ZoneInfo(
                timezone_name
            )
        )
    )

    noun = (
        "match"
        if item_count == 1
        else "matches"
    )

    date_label = (
        local_reference.strftime(
            "%b %-d"
        )
    )

    return (
        f"[ACE] {item_count} new "
        f"{noun} — "
        f"{window_label} "
        f"{date_label}"
    )


def _render_item(
    item: DigestItem,
    *,
    position: int,
    reference_time: datetime,
) -> list[str]:
    """Render one digest entry as plain-text lines."""

    header = (
        f"{position}. "
        f"{item.title} — "
        f"{item.company}"
    )

    lines = [
        header,
    ]

    lines.append(
        f"   Eligibility: "
        f"{item.eligibility_status}"
        f"   Priority: "
        f"{item.role_priority}"
        f"   Change: "
        f"{item.observation_status}"
    )

    lines.append(
        f"   Role family: "
        f"{item.role_family}"
    )

    lines.append(
        f"   Location:    "
        f"{item.location}"
    )

    lines.append(
        f"   Posted:      "
        f"{format_relative_age(
            item.posted_at,
            reference_time=reference_time,
        )}"
    )

    if item.reasons:
        lines.append(
            f"   Why:         "
            f"{item.reasons[0]}"
        )

    if item.official_url:
        lines.append(
            f"   Apply:       "
            f"{item.official_url}"
        )

    else:
        lines.append(
            "   Apply:       "
            "(no verified official URL "
            "stored for this candidate)"
        )

    return lines


def render_digest(
    items: Sequence[DigestItem],
    *,
    window_label: str,
    reference_time: datetime,
    timezone_name: str,
    deferred_count: int = 0,
) -> NotificationMessage:
    """Render many alert candidates as one digest email.

    Raises:
        ValueError: when called with no items. A digest with nothing in
            it must never be delivered, and that is enforced here as
            well as by the delivery worker.
    """

    if not items:
        raise ValueError(
            (
                "Refusing to render an empty "
                "digest."
            )
        )

    if deferred_count < 0:
        raise ValueError(
            (
                "deferred_count must not be "
                "negative."
            )
        )

    normalized_reference = (
        _require_aware_datetime(
            reference_time,
            field_name="reference_time",
        )
    )

    ordered_items = sort_digest_items(
        items
    )

    subject = build_digest_subject(
        item_count=len(
            ordered_items
        ),
        window_label=window_label,
        reference_time=(
            normalized_reference
        ),
        timezone_name=timezone_name,
    )

    noun = (
        "opening"
        if len(ordered_items) == 1
        else "openings"
    )

    lines: list[str] = [
        "ACE JOB DIGEST",
        "=" * SEPARATOR_WIDTH,
        "",
        (
            f"{len(ordered_items)} new "
            f"matching {noun}"
        ),
        (
            f"{window_label} digest · "
            f"generated "
            f"{normalized_reference.strftime(
                '%Y-%m-%d %H:%M:%S UTC'
            )}"
        ),
        "",
        "-" * SEPARATOR_WIDTH,
        "",
    ]

    for position, item in enumerate(
        ordered_items,
        start=1,
    ):
        lines.extend(
            _render_item(
                item,
                position=position,
                reference_time=(
                    normalized_reference
                ),
            )
        )

        lines.append(
            ""
        )

    lines.append(
        "-" * SEPARATOR_WIDTH
    )

    if deferred_count:
        deferred_noun = (
            "match"
            if deferred_count == 1
            else "matches"
        )

        lines.extend(
            [
                "",
                (
                    f"{deferred_count} "
                    f"additional {deferred_noun} "
                    "exceeded this digest's size "
                    "limit and will appear in the "
                    "next digest."
                ),
            ]
        )

    lines.extend(
        [
            "",
            (
                "Every link above points to the "
                "employer's own posting."
            ),
            (
                "Jobs held back by the freshness "
                "policy are still stored by ACE "
                "and remain searchable."
            ),
        ]
    )

    return NotificationMessage(
        subject=subject,
        text_body="\n".join(
            lines
        ),
    )
