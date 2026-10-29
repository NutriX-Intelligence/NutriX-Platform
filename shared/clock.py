"""
The one definition of "today" for the whole backend.

A diary day must be the user's calendar day, not the server's. Everything that decides a meal's `log_date`, a
dashboard's default day, a stream snapshot or an analytics window calls `clock.today()`, which uses APP_TIMEZONE
(an IANA name, default Asia/Kolkata). Using UTC instead would file meals logged between 00:00 and 05:30 India time
under the previous day, so the app would not show them on "today".

The app should still send `log_date` / `?date=` explicitly (the date it shows on screen) wherever the API accepts it.
"""
import logging
import os
from datetime import date, datetime, timezone as _utc
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("shared.clock")

DEFAULT_TIMEZONE = "Asia/Kolkata"


def tzinfo():
    """The configured timezone (re-read on every call so tests and restarts pick up changes)."""
    name = os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown APP_TIMEZONE %r: falling back to UTC", name)
        return _utc.utc


def now() -> datetime:
    """Timezone-aware current time in APP_TIMEZONE."""
    return datetime.now(tzinfo())


def today() -> date:
    return now().date()
