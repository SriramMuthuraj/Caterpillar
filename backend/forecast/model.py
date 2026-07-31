"""Demand forecaster and its baselines (MOD-11, step 4).

``PoissonRegressor`` is the model, for four reasons: the target is a count, the
log link keeps predictions non-negative without clipping, it is deterministic
(no random restarts, so NFR-3 holds by construction), and it fits in
milliseconds — which matters when the backtest refits it at every origin.

It is fitted on the **pooled panel**, all cells at once, with site and type as
one-hot features. Any single cell has ~104 weekly points, which is not enough to
estimate seasonality; pooled across 30 cells it comfortably is. Cell-specific
level is carried by the one-hots and the lag features.

Two baselines exist and both are reported, because a forecast with no baseline
is an unfalsifiable number:

* ``FlatMeanBaseline`` — predict the cell's historical mean. The bar the model
  must clear to be worth anything at all.
* ``SeasonalIndexBaseline`` — cell mean scaled by a pooled, smoothed
  week-of-year index. The bar that proves seasonality is *recoverable from the
  data* rather than merely present in it. This is what ``test_history.py`` uses
  as its signal-sufficiency gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

from . import config, features

# Ridge penalty on the Poisson GLM. Non-zero because the one-hot blocks and the
# harmonics are mildly collinear by construction.
ALPHA = 1e-3
MAX_ITER = 1000

# Half-width of the smoothing window applied to the week-of-year index.
SEASONAL_SMOOTH = 2


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------

@dataclass
class FlatMeanBaseline:
    """Predict each cell's own historical mean."""

    means: dict[tuple[str, str], float] = field(default_factory=dict)
    grand_mean: float = 0.0

    def fit(self, panel: pd.DataFrame) -> "FlatMeanBaseline":
        grouped = panel.groupby(["site_id", "type"])["y"].mean()
        self.means = {(s, t): float(v) for (s, t), v in grouped.items()}
        self.grand_mean = float(panel["y"].mean())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.array([
            self.means.get((s, t), self.grand_mean)
            for s, t in zip(frame["site_id"], frame["type"])
        ])


@dataclass
class SeasonalIndexBaseline:
    """Cell mean x pooled week-of-year index.

    The index is estimated by pooling every cell, which averages away the
    Poisson noise that makes any single cell's week-of-year look like static.
    """

    flat: FlatMeanBaseline = field(default_factory=FlatMeanBaseline)
    index: dict[int, float] = field(default_factory=dict)

    def fit(self, panel: pd.DataFrame) -> "SeasonalIndexBaseline":
        self.flat = FlatMeanBaseline().fit(panel)

        grand = float(panel["y"].mean()) or 1.0
        by_woy = panel.groupby("woy")["y"].mean()
        raw = {int(w): float(v) / grand for w, v in by_woy.items()}

        # Circular moving average over week-of-year.
        weeks = sorted(raw)
        smoothed: dict[int, float] = {}
        for w in weeks:
            window = [
                raw[weeks[(weeks.index(w) + d) % len(weeks)]]
                for d in range(-SEASONAL_SMOOTH, SEASONAL_SMOOTH + 1)
            ]
            smoothed[w] = float(np.mean(window))

        self.index = smoothed
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        base = self.flat.predict(frame)
        factors = np.array([
            self.index.get(int(w), 1.0) for w in frame["woy"]
        ])
        return np.clip(base * factors, 0.0, None)


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------

class DemandForecaster:
    """Poisson GLM over calendar + lag features, fitted on the pooled panel."""

    def __init__(self, alpha: float = ALPHA, max_iter: int = MAX_ITER) -> None:
        self.alpha = alpha
        self.max_iter = max_iter
        self.model: PoissonRegressor | None = None
        self.columns: list[str] = []

    def fit(self, panel: pd.DataFrame) -> "DemandForecaster":
        train = features.training_frame(panel)
        if train.empty:
            raise ValueError("no usable training rows — history too short")

        design = features.encode(train)
        self.columns = list(design.columns)

        self.model = PoissonRegressor(
            alpha=self.alpha, max_iter=self.max_iter, fit_intercept=True
        )
        self.model.fit(design.values, train["y"].values)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("DemandForecaster.predict called before fit")
        design = features.encode(frame, columns=self.columns)
        return np.clip(self.model.predict(design.values), 0.0, None)

    def forecast_cell(self, panel: pd.DataFrame, site_id: str, type_name: str,
                      horizon: int = config.FORECAST_HORIZON_WEEKS
                      ) -> pd.DataFrame:
        """Recursive multi-step forecast for one cell.

        Each predicted week is appended to the working history so the next step's
        lag features are defined. Recursion is why the lag primitives are shared
        with the panel builder rather than reimplemented here.
        """
        series = features.cell_series(panel, site_id, type_name)
        if series.empty:
            raise KeyError(f"unknown cell ({site_id}, {type_name})")

        history = [float(v) for v in series["y"]]
        last_week = series["week_start"].iloc[-1].date()
        last_t = int(round(float(series["t"].iloc[-1]) * 52.0))

        out: list[dict] = []
        for step in range(1, horizon + 1):
            week_start = last_week + pd.Timedelta(days=7 * step).to_pytimedelta()
            row = features.future_row(
                site_id, type_name, week_start, last_t + step, history
            )
            point = float(self.predict(row)[0])
            history.append(point)
            out.append({
                "week_start": pd.Timestamp(week_start),
                "horizon": step,
                "point": point,
            })

        return pd.DataFrame(out)


# --------------------------------------------------------------------------
# The refusal
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Eligibility:
    """Whether a cell has enough history to be forecast at all."""

    eligible: bool
    nonzero_weeks: int
    total_rentals: int
    reason: str | None = None


def check_eligibility(panel: pd.DataFrame, site_id: str,
                      type_name: str) -> Eligibility:
    """FR-6: refuse rather than fabricate where n is too small.

    Returning ``insufficient_data`` is a feature. Some cells are starved on
    purpose (``config.SPARSE_CELLS``) so this path runs against real generated
    data instead of being a branch nobody exercises.
    """
    series = features.cell_series(panel, site_id, type_name)
    nonzero = int((series["y"] > 0).sum())
    total = int(series["y"].sum())

    if nonzero < config.MIN_NONZERO_WEEKS:
        return Eligibility(
            False, nonzero, total,
            f"only {nonzero} weeks with any rental "
            f"(need {config.MIN_NONZERO_WEEKS})",
        )
    if total < config.MIN_TOTAL_RENTALS:
        return Eligibility(
            False, nonzero, total,
            f"only {total} rentals observed "
            f"(need {config.MIN_TOTAL_RENTALS})",
        )
    return Eligibility(True, nonzero, total)
