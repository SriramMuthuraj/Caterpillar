"""One source of "now" for the Flask side.

Every date in the dataset is historical — the demo clock sits at 2025-08-18
while the wall clock is well past it. So ``datetime.utcnow()`` makes *every*
rental look expired: the alerts page fills with 296 identical RETURN_DUE rows
and the feature reads as broken.

The forecast package already owns the virtual clock, so this defers to it and
only falls back to the real one when that package is not importable (running
Cat_SRTS standalone from its own directory).
"""

from __future__ import annotations

from datetime import date, datetime, time


def today() -> date:
    try:
        from backend.forecast import clock_adapter
        return clock_adapter.now_date()
    except Exception:
        return datetime.utcnow().date()


def now() -> datetime:
    return datetime.combine(today(), time.min)


def end_of_today() -> datetime:
    return datetime.combine(today(), time.max)


def source() -> str:
    try:
        from backend.forecast import clock_adapter
        return clock_adapter.clock_source()
    except Exception:
        return "wall_clock"
