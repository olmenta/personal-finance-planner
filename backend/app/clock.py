"""Today in Europe/Madrid — the one clock every month boundary reads.

FIXED_TODAY pins it for the e2e suite (deterministic months and paid/pending
splits). Honored only outside production, like other dev-only switches.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import get_settings

MADRID = ZoneInfo("Europe/Madrid")


def today_madrid() -> date:
    settings = get_settings()
    if settings.fixed_today and settings.sentry_environment != "production":
        return settings.fixed_today
    return datetime.now(MADRID).date()


def current_month() -> str:
    return today_madrid().strftime("%Y-%m")
