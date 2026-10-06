"""Small time helpers so every part of the app agrees on what 'now' means."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings

_LOCAL = ZoneInfo(settings.timezone)


def now_local() -> datetime:
    """Wall-clock time in the app's time zone (IST by default), without tz info.
    Session times typed in the browser are local times, so they are compared with this."""
    return datetime.now(_LOCAL).replace(tzinfo=None)


def now_utc() -> datetime:
    """Current UTC time without tz info (SQLite stores no time zones). Used for test timers."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    """A naive UTC datetime as an ISO string ending in Z, e.g. 2026-10-06T10:29:00Z."""
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"
