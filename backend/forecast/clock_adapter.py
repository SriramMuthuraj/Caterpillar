"""Single entry point for "now" inside MOD-11.

INVARIANT: nothing in this package calls ``datetime.now()``. MOD-02 (Virtual
Clock) is the system's only source of ``now``. Until MOD-02 lands this falls
back to the fixed ``config.DEMO_NOW`` constant — still not a real clock, so the
generator stays deterministic and the forecast horizon stays reproducible.
"""

from __future__ import annotations

from datetime import date, timedelta

from . import config


def now_date() -> date:
    """Current date according to the virtual clock, never the wall clock."""
    try:
        # MOD-02's interface, per PRD section 8.1. Imported lazily and
        # defensively so M3 is never blocked on M1's landing.
        from backend.clock.service import now as clock_now  # type: ignore
    except Exception:
        return config.DEMO_NOW

    value = clock_now()
    return value.date() if hasattr(value, "date") else value


def clock_source() -> str:
    """Which clock answered — surfaced in the API so the demo can't lie."""
    try:
        from backend.clock.service import now as _  # type: ignore  # noqa: F401
    except Exception:
        return "demo_constant"
    return "virtual_clock"


def week_start(d: date) -> date:
    """Monday of the ISO week containing ``d``.

    Weeks are keyed by their Monday rather than by (iso_year, iso_week) to keep
    arithmetic simple and to sidestep the week-53 / year-boundary edge cases.
    """
    return d - timedelta(days=d.weekday())
