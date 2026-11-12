"""AIRAC cycle identifiers. AIRAC cycles are 28 days long; cycle 2501 became effective on 2025-01-23."""
from __future__ import annotations

from datetime import date, timedelta

ANCHOR = date(2025, 1, 23)  # effective date of AIRAC 2501
CYCLE_DAYS = 28


def effective_date(day: date) -> date:
    """Effective date of the AIRAC cycle that is in force on `day`."""
    return ANCHOR + timedelta(days=((day - ANCHOR).days // CYCLE_DAYS) * CYCLE_DAYS)


def cycle_id(day: date) -> str:
    """AIRAC identifier such as '2513': two-digit year of the effective date plus the cycle number in that year."""
    eff = effective_date(day)
    first = eff
    while (first - timedelta(days=CYCLE_DAYS)).year == eff.year:
        first -= timedelta(days=CYCLE_DAYS)
    number = (eff - first).days // CYCLE_DAYS + 1
    return f"{eff.year % 100:02d}{number:02d}"
