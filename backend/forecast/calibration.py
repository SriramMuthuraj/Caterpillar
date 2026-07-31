"""Fit the synthetic generator's distributions to the 7 supplied seed rows.

This is what separates generated history from invented history: durations, day
rates and engine/idle behaviour are drawn from distributions **fitted to the
real rows**, so the synthetic fleet is a larger version of the supplied data
rather than something unrelated to it.

``data/seed_assets.csv`` is not yet committed to this repo. Until it is, the
fallbacks below are used and ``Calibration.calibrated`` is False — which the API
reports and the parity test refuses to pass silently. Fallback values are
derived from the durations quoted in PRD section 3 (20, 24 and 30 days), not
invented.
"""

from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field

import pandas as pd

from . import paths

# Candidate header spellings, normalised to snake_case before matching.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "equipment_id": ("equipment_id", "equipmentid", "asset_id", "id"),
    "type": ("type", "equipment_type", "equipment_class", "category"),
    "site_id": ("site_id", "site", "siteid", "location_id"),
    "operator_id": ("operator_id", "operator", "operatorid"),
    "check_in": ("check_in", "check_in_date", "checkin", "check_out_date_from",
                 "rental_start", "start_date", "from_date"),
    "check_out": ("check_out", "check_out_date", "checkout", "rental_end",
                  "end_date", "to_date", "return_date"),
    "rental_days": ("rental_days", "rentaldays", "days", "rental_duration"),
    "engine_hours": ("engine_hours_day", "engine_hours_per_day", "engine_hours",
                     "engine_hrs_day", "engine_hours_day_"),
    "idle_hours": ("idle_hours_day", "idle_hours_per_day", "idle_hours",
                   "idle_hrs_day"),
}

# Durations quoted in PRD section 3 for the supplied rows.
_FALLBACK_DURATIONS = (20.0, 24.0, 30.0)

# Three observations produce an implausibly tight lognormal. Real rental
# durations vary far more, so sigma is floored. Declared assumption, not a fudge.
_SIGMA_FLOOR = 0.45


@dataclass
class Calibration:
    """Distribution parameters the generator draws from."""

    calibrated: bool
    source: str
    duration_log_mu: float
    duration_log_sigma: float
    duration_min: int
    duration_max: int
    engine_hours_mean: float
    engine_hours_sd: float
    idle_fraction_mean: float
    idle_fraction_sd: float
    observed_types: tuple[str, ...] = ()
    observed_sites: tuple[str, ...] = ()
    n_seed_rows: int = 0
    notes: tuple[str, ...] = ()

    @property
    def duration_mean_days(self) -> float:
        """Mean of the fitted lognormal, in days."""
        return math.exp(self.duration_log_mu + 0.5 * self.duration_log_sigma ** 2)


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical field names onto whatever the CSV actually calls them."""
    normalised = {_normalise(c): c for c in df.columns}
    resolved: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                resolved[canonical] = normalised[alias]
                break
    return resolved


def _fit_lognormal(values: list[float]) -> tuple[float, float]:
    positive = [v for v in values if v and v > 0]
    if not positive:
        positive = list(_FALLBACK_DURATIONS)
    logs = [math.log(v) for v in positive]
    mu = sum(logs) / len(logs)
    if len(logs) < 2:
        sigma = _SIGMA_FLOOR
    else:
        var = sum((x - mu) ** 2 for x in logs) / (len(logs) - 1)
        sigma = math.sqrt(var)
    return mu, max(sigma, _SIGMA_FLOOR)


def _fallback() -> Calibration:
    mu, sigma = _fit_lognormal(list(_FALLBACK_DURATIONS))
    return Calibration(
        calibrated=False,
        source="fallback (PRD section 3 durations; data/seed_assets.csv absent)",
        duration_log_mu=mu,
        duration_log_sigma=sigma,
        duration_min=5,
        duration_max=90,
        engine_hours_mean=6.5,
        engine_hours_sd=1.8,
        idle_fraction_mean=0.28,
        idle_fraction_sd=0.12,
        notes=(
            "data/seed_assets.csv is not present — synthetic history is NOT "
            "calibrated to the supplied rows. Commit the seed file and "
            "regenerate before treating any backtest number as meaningful.",
        ),
    )


def load_calibration() -> Calibration:
    """Fit from ``data/seed_assets.csv`` where present, else fall back loudly."""
    path = paths.seed_csv()
    if not path.exists():
        warnings.warn(
            f"{path} not found — MOD-11 is running on uncalibrated fallback "
            "distributions. See backend/forecast/README.md.",
            RuntimeWarning,
            stacklevel=2,
        )
        return _fallback()

    df = pd.read_csv(path)
    cols = _resolve_columns(df)
    notes: list[str] = []

    # --- durations -------------------------------------------------------
    durations: list[float] = []
    if "check_in" in cols and "check_out" in cols:
        start = pd.to_datetime(df[cols["check_in"]], errors="coerce")
        end = pd.to_datetime(df[cols["check_out"]], errors="coerce")
        spans = (end - start).dt.days.dropna()
        durations = [float(v) for v in spans if v > 0]
    if not durations and "rental_days" in cols:
        stated = pd.to_numeric(df[cols["rental_days"]], errors="coerce").dropna()
        durations = [float(v) for v in stated if v > 0]
        notes.append("durations taken from stated rental_days; date columns unusable")
    if not durations:
        durations = list(_FALLBACK_DURATIONS)
        notes.append("no usable duration column; fell back to PRD section 3 values")

    mu, sigma = _fit_lognormal(durations)

    # --- engine / idle ---------------------------------------------------
    # The supplied rows include physically impossible values on purpose
    # (EQX1001, EQX1002, EQX1007). Calibrating on those would propagate the
    # defect into every synthetic row, so implausible rows are excluded from the
    # fit. They remain in the dataset verbatim — this filter is fitting-only.
    engine_mean, engine_sd = 6.5, 1.8
    idle_mean, idle_sd = 0.28, 0.12
    if "engine_hours" in cols:
        engine = pd.to_numeric(df[cols["engine_hours"]], errors="coerce")
        plausible = engine[(engine > 0.5) & (engine <= 24)]
        if len(plausible) >= 2:
            engine_mean = float(plausible.mean())
            engine_sd = float(plausible.std(ddof=1)) or 1.8
        elif len(plausible) == 1:
            engine_mean = float(plausible.iloc[0])
            notes.append("only one plausible engine-hours row; sd left at default")

        if "idle_hours" in cols:
            idle = pd.to_numeric(df[cols["idle_hours"]], errors="coerce")
            mask = (engine > 0.5) & (engine <= 24) & (idle >= 0) & (idle <= engine)
            if mask.sum() >= 1:
                frac = (idle[mask] / engine[mask])
                idle_mean = float(frac.mean())
                if mask.sum() >= 2:
                    idle_sd = float(frac.std(ddof=1)) or 0.12
            else:
                notes.append(
                    "no seed row satisfies idle <= engine — idle fraction left "
                    "at default (this is INT-02 showing up in calibration)"
                )

    # --- vocabulary ------------------------------------------------------
    # Rental rates are deliberately not fitted here: pricing lives in
    # data/rates.yaml, which is M2's file. One source of truth for money.
    observed_types = tuple(
        sorted(df[cols["type"]].dropna().astype(str).unique())
    ) if "type" in cols else ()
    observed_sites = tuple(
        sorted(df[cols["site_id"]].dropna().astype(str).unique())
    ) if "site_id" in cols else ()

    return Calibration(
        calibrated=True,
        source=str(path),
        duration_log_mu=mu,
        duration_log_sigma=sigma,
        duration_min=max(3, int(min(durations) * 0.5)),
        duration_max=int(max(durations) * 3),
        engine_hours_mean=engine_mean,
        engine_hours_sd=abs(engine_sd),
        idle_fraction_mean=min(max(idle_mean, 0.05), 0.75),
        idle_fraction_sd=abs(idle_sd),
        observed_types=observed_types,
        observed_sites=observed_sites,
        n_seed_rows=int(len(df)),
        notes=tuple(notes),
    )
