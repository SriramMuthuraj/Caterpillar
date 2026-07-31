"""Weekly demand panel and model features (MOD-11, step 3).

Target (locked): **number of rentals commencing** in a week for one
(equipment_type x site) cell. A dealer pre-positions stock against new starts;
"assets currently on rent" is a utilisation figure that mostly predicts itself.

Two rules govern this file.

**The panel must be complete.** Cells with no rental in a week are explicit
zeros, not missing rows. Under a "new starts" target, zeros carry most of the
signal — dropping them would turn a demand series into a rentals-only series and
silently bias every level upward.

**No leakage.** Features are derived from the calendar and from the observed
history only. Nothing from the data-generating process — site phase, project
progress, the monsoon multiplier itself — is ever handed to the model. It has to
recover seasonality from observations, which is the entire point of the
exercise. ``test_forecast.py`` asserts this.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import clock_adapter, config
from . import history as history_mod

LAG_COLUMNS = ["lag_1", "lag_2", "lag_3", "lag_4", "roll_4", "roll_8", "roll_13"]

# Design-matrix calendar features. Raw ``woy`` (1-53) is deliberately excluded:
# it is redundant with the harmonics and the month one-hots, and its scale is an
# order of magnitude larger than everything else, which stalls the lbfgs solver.
# It stays in the panel because the seasonal baseline indexes on it.
CALENDAR_COLUMNS = [
    "t", "sin1", "cos1", "sin2", "cos2",
    "is_monsoon", "is_fy_q4", "is_april",
]
# Interaction terms, not plain site/type/month one-hots.
#
# ``cell`` is site x type. Entered separately they are additive in log space,
# which cannot express "S002 is excavator-heavy right now" — and that is exactly
# the structure a phase-driven fleet has. Without it the model under-predicts
# busy cells by roughly half.
#
# ``type_month`` is type x month, because monsoon sensitivity differs by machine
# class: earthmoving stops on wet ground, lifting barely notices.
CATEGORICAL_COLUMNS = ["cell", "type_month"]

# Rows before this many weeks of history have undefined long lags.
WARMUP_WEEKS = 13


def week_grid(now: date, weeks: int) -> list[date]:
    """The Mondays covered by the history, oldest first."""
    last_full_week = clock_adapter.week_start(now) - timedelta(days=7)
    first = last_full_week - timedelta(days=7 * (weeks - 1))
    return [first + timedelta(days=7 * i) for i in range(weeks)]


def lag_dict(history: list[float]) -> dict[str, float]:
    """Lag and rolling features from the values observed *before* this week.

    Deliberately shared by the panel builder and the recursive forecaster so the
    two can never drift apart — a mismatch between training features and
    prediction features is the classic silent forecasting bug.
    """
    out: dict[str, float] = {}
    n = len(history)

    for k in (1, 2, 3, 4):
        out[f"lag_{k}"] = history[-k] if n >= k else math.nan

    for window in (4, 8, 13):
        if n >= window:
            out[f"roll_{window}"] = float(np.mean(history[-window:]))
        else:
            out[f"roll_{window}"] = math.nan

    return out


def calendar_dict(week_start: date, t: int) -> dict[str, float]:
    """Calendar features. Observable to anyone with a wall calendar."""
    woy = week_start.isocalendar()[1]
    angle = 2.0 * math.pi * woy / 52.18
    month = week_start.month
    return {
        "t": t / 52.0,
        "month": month,
        "woy": woy,
        "sin1": math.sin(angle),
        "cos1": math.cos(angle),
        "sin2": math.sin(2 * angle),
        "cos2": math.cos(2 * angle),
        "is_monsoon": 1.0 if month in config.MONSOON_MONTHS else 0.0,
        "is_fy_q4": 1.0 if month in config.FISCAL_Q4_MONTHS else 0.0,
        "is_april": 1.0 if month == 4 else 0.0,
    }


def weekly_panel(rentals: pd.DataFrame, now: date, weeks: int) -> pd.DataFrame:
    """Complete (site x type x week) panel of new-rental counts.

    Only synthetic rows drive the demand series. The 7 ground-truth rows are
    preserved verbatim elsewhere but cannot contribute a weekly series — seven
    rentals across two years is not a time series, and pretending otherwise is
    the claim PRD section 3 warns collapses under questioning.
    """
    grid = week_grid(now, weeks)
    week_index = {w: i for i, w in enumerate(grid)}

    counts: dict[tuple[str, str, date], int] = {}
    # Rows with no site recorded (config.RATE_UNASSIGNED_SITE) belong to no
    # site-week series and would otherwise accumulate under a NaN key.
    rentals = rentals.dropna(subset=["site_id"])
    if len(rentals):
        starts = pd.to_datetime(rentals["check_in"]).dt.date
        for site_id, type_name, start in zip(
            rentals["site_id"], rentals["type"], starts
        ):
            w = clock_adapter.week_start(start)
            if w in week_index:
                counts[(site_id, type_name, w)] = counts.get(
                    (site_id, type_name, w), 0
                ) + 1

    # A site that has not broken ground yet is not a cell with zero demand — it
    # is not a cell at all. Emitting those weeks as explicit zeros (which this
    # builder did before sites gained schedules) pads every young site with tens
    # of weeks of fabricated silence, drags its level toward zero and makes the
    # panel claim observations nobody made.
    schedules = history_mod.build_schedules(weeks=weeks)

    rows: list[dict] = []
    for site in config.SITES:
        schedule = schedules[site.site_id]
        for etype in config.EQUIPMENT_TYPES:
            history: list[float] = []
            for t, w in enumerate(grid):
                if not schedule.is_active_at(t):
                    continue
                y = float(counts.get((site.site_id, etype.name, w), 0))
                row = {
                    "site_id": site.site_id,
                    "type": etype.name,
                    "cell": f"{site.site_id}|{etype.name}",
                    "type_month": f"{etype.name}|{w.month}",
                    "week_start": pd.Timestamp(w),
                    "y": y,
                }
                row.update(calendar_dict(w, t))
                row.update(lag_dict(history))
                rows.append(row)
                history.append(y)

    return pd.DataFrame(rows)


def future_row(site_id: str, type_name: str, week_start: date, t: int,
               history: list[float]) -> pd.DataFrame:
    """A single unobserved week, built with the same primitives as the panel."""
    row = {"site_id": site_id, "type": type_name,
           "cell": f"{site_id}|{type_name}",
           "type_month": f"{type_name}|{week_start.month}",
           "week_start": pd.Timestamp(week_start), "y": math.nan}
    row.update(calendar_dict(week_start, t))
    row.update(lag_dict(history))
    return pd.DataFrame([row])


def encode(frame: pd.DataFrame,
           columns: list[str] | None = None) -> pd.DataFrame:
    """One-hot the categoricals and return the numeric design matrix.

    Lag features enter as ``log1p``. The model has a log link, so a raw lag would
    make the effect exponential in recent demand; ``log1p`` makes it a power law,
    which is the right shape for carrying a level.

    ``columns`` pins the layout learned at fit time, so a prediction frame
    containing a single cell still scores against the full design.
    """
    work = frame.copy()

    design = pd.get_dummies(
        work[CATEGORICAL_COLUMNS + CALENDAR_COLUMNS + LAG_COLUMNS],
        columns=CATEGORICAL_COLUMNS,
        dtype=float,
    )

    for column in LAG_COLUMNS:
        design[column] = np.log1p(design[column].clip(lower=0.0))

    if columns is not None:
        design = design.reindex(columns=columns, fill_value=0.0)

    return design.astype(float)


def training_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """Rows usable for fitting: warm-up dropped, no undefined lags."""
    usable = panel.dropna(subset=LAG_COLUMNS)
    return usable.reset_index(drop=True)


def cell_series(panel: pd.DataFrame, site_id: str,
                type_name: str) -> pd.DataFrame:
    """One cell's history, oldest first."""
    mask = (panel["site_id"] == site_id) & (panel["type"] == type_name)
    return panel.loc[mask].sort_values("week_start").reset_index(drop=True)
