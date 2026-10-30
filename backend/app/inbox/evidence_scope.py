"""The owner's current job-search email window; storage and app history stay intact.

July 1 is a calendar date in the owner's Los Angeles timezone. Keep its absolute
instant fixed when Analytics changes display timezone, so Inbox and Analytics
never disagree about whether a message belongs to the current search.
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from backend.app.db.models import GmailMessageRecord


START = date(2026, 7, 1)
TIMEZONE = 'America/Los_Angeles'
START_AT = datetime.combine(START, time.min, ZoneInfo(TIMEZONE)).astimezone(timezone.utc)


def mail_clause():
    return GmailMessageRecord.received_at >= START_AT


def includes(stamp: datetime) -> bool:
    aware = stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=timezone.utc)
    return aware >= START_AT


def calendar_start(zone: ZoneInfo) -> date:
    return START_AT.astimezone(zone).date()


def effective_calendar_start(requested: date, zone: ZoneInfo, *, all_dates: bool) -> date:
    floor = calendar_start(zone)
    return floor if all_dates else max(requested, floor)


def metadata() -> dict:
    return {'start': START.isoformat(), 'timezone': TIMEZONE,
            'start_at': START_AT.isoformat().replace('+00:00', 'Z'),
            'application_cohort_unchanged': True}
