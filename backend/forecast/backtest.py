"""Rolling-origin backtest and prediction intervals (MOD-11, step 5).

PRD section 14 commits to presenting **the harness as the deliverable, not the
accuracy number**. This file is that harness.

Method: walk an origin forward one week at a time. At each origin, refit on
everything up to that week only, forecast h = 1..H, and score against what
actually happened. No future information reaches any fit. This is the only
honest way to measure a time-series model; a random train/test split would leak
the future and report a flattering fiction.

**Prediction intervals are earned, not assumed.** They come from the spread of
these measured errors, not from a distributional formula. Residuals are scaled
by ``sqrt(prediction)`` before quantiles are taken, because count variance
grows with the level — a flat +/- 2 band is far too wide on a quiet cell and far
too narrow on a busy one.

A note on MAPE. The frozen contract (PRD section 11) carries a ``mape`` field,
so it is populated — but the target is *new rental starts*, which is legitimately
zero in many weeks, and MAPE divides by the actual. It is therefore computed over
non-zero weeks only and labelled as such. **MAE is the headline metric** in the
UI: "we are off by 1.2 machines in a typical week" is both honest and immediately
legible to a judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config, features, model as model_mod

BACKTEST_ORIGINS = 16
BACKTEST_HORIZON = 4

# Floor inside the variance scaling, so a near-zero prediction cannot produce a
# degenerate zero-width interval.
_SCALE_FLOOR = 0.5


@dataclass
class BacktestResult:
    """Measured out-of-sample performance and the intervals derived from it."""

    n_predictions: int
    n_origins: int
    horizon: int
    mae: float
    rmse: float
    mape_nonzero: float | None
    n_mape_weeks: int
    baseline_mae: float
    skill_vs_seasonal: float
    coverage: float
    interval_level: float
    residual_quantiles: dict[int, tuple[float, float]] = field(default_factory=dict)
    mae_by_horizon: dict[int, float] = field(default_factory=dict)
    predictions: pd.DataFrame | None = None

    def summary(self) -> dict:
        """Compact, JSON-safe form for the API and the deck."""
        return {
            "n_predictions": self.n_predictions,
            "n_origins": self.n_origins,
            "horizon": self.horizon,
            "mae": round(self.mae, 3),
            "rmse": round(self.rmse, 3),
            "mape_nonzero_pct": (
                None if self.mape_nonzero is None else round(self.mape_nonzero, 1)
            ),
            "n_mape_weeks": self.n_mape_weeks,
            "baseline_mae": round(self.baseline_mae, 3),
            "skill_vs_seasonal_baseline": round(self.skill_vs_seasonal, 3),
            "interval_coverage": round(self.coverage, 3),
            "interval_level": self.interval_level,
            "mae_by_horizon": {
                int(h): round(v, 3) for h, v in sorted(self.mae_by_horizon.items())
            },
            "method": (
                f"rolling origin, {self.n_origins} origins, refit at each, "
                f"horizons 1-{self.horizon}"
            ),
        }

    def interval(self, point: float, horizon: int) -> tuple[float, float]:
        """Prediction interval around ``point`` for a given horizon.

        Beyond the measured horizon the widest measured band is reused rather
        than extrapolated. Wider-than-justified is the safe direction; inventing
        a narrower one is not.
        """
        if not self.residual_quantiles:
            return (point, point)

        available = sorted(self.residual_quantiles)
        h = horizon if horizon in self.residual_quantiles else available[-1]
        q_lo, q_hi = self.residual_quantiles[h]

        scale = np.sqrt(max(point, _SCALE_FLOOR))
        return (
            float(max(point + q_lo * scale, 0.0)),
            float(max(point + q_hi * scale, 0.0)),
        )


def _eligible_cells(panel: pd.DataFrame) -> list[tuple[str, str]]:
    cells = []
    for site in config.SITES:
        for etype in config.EQUIPMENT_TYPES:
            if model_mod.check_eligibility(
                panel, site.site_id, etype.name
            ).eligible:
                cells.append((site.site_id, etype.name))
    return cells


def run_backtest(
    panel: pd.DataFrame,
    n_origins: int = BACKTEST_ORIGINS,
    horizon: int = BACKTEST_HORIZON,
    interval_level: float = config.INTERVAL_LEVEL,
) -> BacktestResult:
    """Walk the origin forward, refitting at each step."""
    weeks = sorted(panel["week_start"].unique())
    n_weeks = len(weeks)

    last_origin = n_weeks - 1 - horizon
    first_origin = last_origin - n_origins + 1
    if first_origin <= features.WARMUP_WEEKS + 4:
        raise ValueError(
            "history too short to backtest: increase config.HISTORY_WEEKS or "
            "reduce BACKTEST_ORIGINS"
        )

    actual_lookup = {
        (s, t, w): float(y)
        for s, t, w, y in zip(
            panel["site_id"], panel["type"], panel["week_start"], panel["y"]
        )
    }

    records: list[dict] = []

    for origin_idx in range(first_origin, last_origin + 1):
        cutoff = weeks[origin_idx]
        train = panel[panel["week_start"] <= cutoff]

        fitted = model_mod.DemandForecaster().fit(train)
        baseline = model_mod.SeasonalIndexBaseline().fit(
            features.training_frame(train)
        )

        for site_id, type_name in _eligible_cells(train):
            path = fitted.forecast_cell(train, site_id, type_name, horizon)

            for _, row in path.iterrows():
                week = row["week_start"]
                key = (site_id, type_name, week)
                if key not in actual_lookup:
                    continue

                future = pd.DataFrame([{
                    "site_id": site_id,
                    "type": type_name,
                    "woy": int(pd.Timestamp(week).isocalendar()[1]),
                }])

                records.append({
                    "origin": cutoff,
                    "week_start": week,
                    "site_id": site_id,
                    "type": type_name,
                    "horizon": int(row["horizon"]),
                    "actual": actual_lookup[key],
                    "pred": float(row["point"]),
                    "baseline": float(baseline.predict(future)[0]),
                })

    if not records:
        raise ValueError("backtest produced no predictions")

    frame = pd.DataFrame(records)
    error = frame["actual"] - frame["pred"]

    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error ** 2)))
    baseline_mae = float(np.mean(np.abs(frame["actual"] - frame["baseline"])))
    skill = 1.0 - (mae / baseline_mae) if baseline_mae > 0 else 0.0

    nonzero = frame[frame["actual"] > 0]
    if len(nonzero):
        mape = float(
            np.mean(np.abs(
                (nonzero["actual"] - nonzero["pred"]) / nonzero["actual"]
            )) * 100.0
        )
    else:
        mape = None

    # Scaled-residual quantiles per horizon -> interval half-widths.
    tail = (1.0 - interval_level) / 2.0
    quantiles: dict[int, tuple[float, float]] = {}
    mae_by_h: dict[int, float] = {}
    for h, group in frame.groupby("horizon"):
        scale = np.sqrt(np.maximum(group["pred"].values, _SCALE_FLOOR))
        scaled = (group["actual"].values - group["pred"].values) / scale
        quantiles[int(h)] = (
            float(np.quantile(scaled, tail)),
            float(np.quantile(scaled, 1.0 - tail)),
        )
        mae_by_h[int(h)] = float(np.mean(np.abs(
            group["actual"].values - group["pred"].values
        )))

    # Empirical coverage, computed on the same residuals the bands came from.
    # In-sample for the interval calibration, so it is a sanity check that the
    # arithmetic is right rather than an independent validation — stated plainly
    # rather than presented as out-of-sample coverage.
    inside = 0
    for _, row in frame.iterrows():
        q_lo, q_hi = quantiles[int(row["horizon"])]
        scale = np.sqrt(max(row["pred"], _SCALE_FLOOR))
        lo = max(row["pred"] + q_lo * scale, 0.0)
        hi = max(row["pred"] + q_hi * scale, 0.0)
        if lo <= row["actual"] <= hi:
            inside += 1

    return BacktestResult(
        n_predictions=len(frame),
        n_origins=last_origin - first_origin + 1,
        horizon=horizon,
        mae=mae,
        rmse=rmse,
        mape_nonzero=mape,
        n_mape_weeks=len(nonzero),
        baseline_mae=baseline_mae,
        skill_vs_seasonal=skill,
        coverage=inside / len(frame),
        interval_level=interval_level,
        residual_quantiles=quantiles,
        mae_by_horizon=mae_by_h,
        predictions=frame,
    )
