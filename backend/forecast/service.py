"""Assembly and caching for MOD-11.

Builds the pipeline once per process — history -> panel -> fit -> backtest — and
answers forecast queries from it. NFR-2 says the app opens on a pre-seeded,
interesting state with no cold start, so ``warm()`` is called at FastAPI startup
rather than lazily on the first judge's click.

Nothing here touches the network. NFR-1 holds by construction.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from . import (
    allocate as allocate_mod,
    artifacts,
    backtest as backtest_mod,
    calibration,
    clock_adapter,
    config,
    features,
    history,
    model as model_mod,
    paths,
    phase as phase_mod,
)

_lock = threading.Lock()
_bundle: "ForecastBundle | None" = None


@dataclass
class ForecastBundle:
    """Everything the endpoints need, built once."""

    now: date
    calib: calibration.Calibration
    rentals: pd.DataFrame
    panel: pd.DataFrame
    forecaster: model_mod.DemandForecaster
    result: backtest_mod.BacktestResult
    # --- phase engine ---------------------------------------------------
    site_phases: pd.DataFrame
    phase_panel: pd.DataFrame
    classifier: phase_mod.PhaseClassifier
    end_model: phase_mod.PhaseEndModel
    peaks: pd.DataFrame
    typical_site_size: float

    @property
    def fleet_size(self) -> int:
        return int(self.rentals["equipment_id"].nunique())


def build(seed: int = config.MASTER_SEED, now: date | None = None,
          weeks: int = config.HISTORY_WEEKS,
          refresh: bool = False) -> ForecastBundle:
    """Run the whole pipeline. Deterministic for a given seed and clock."""
    now = now or clock_adapter.now_date()
    calib = calibration.load_calibration()

    rentals = history.cached_history(seed=seed, now=now, weeks=weeks,
                                     refresh=refresh)
    panel = features.weekly_panel(rentals, now=now, weeks=weeks)

    forecaster = model_mod.DemandForecaster().fit(panel)
    result = backtest_mod.run_backtest(panel)

    # --- phase engine ----------------------------------------------------
    site_phases = history.site_phase_windows(now=now, weeks=weeks, seed=seed)
    phase_panel = phase_mod.build_panel(rentals, site_phases, now=now)
    classifier, end_model = _phase_models(
        phase_panel, site_phases, refresh=refresh
    )
    peaks = phase_mod.typical_machines_per_phase(rentals, site_phases)
    site_size = phase_mod.typical_site_size(rentals, site_phases)

    bundle = ForecastBundle(
        now=now, calib=calib, rentals=rentals, panel=panel,
        forecaster=forecaster, result=result,
        site_phases=site_phases, phase_panel=phase_panel,
        classifier=classifier, end_model=end_model, peaks=peaks,
        typical_site_size=site_size,
    )
    _write_backtest_card(bundle)
    return bundle


def _phase_models(phase_panel: pd.DataFrame, site_phases: pd.DataFrame,
                  refresh: bool = False):
    """Load both phase models from disk, refitting whichever cannot be trusted.

    Each file is checked independently against the fingerprint of the data
    currently in hand, so a stale classifier cannot ride along on a freshly
    trained duration model. Anything that fails validation is refitted and
    rewritten — see artifacts.py for what "fails" means.

    Refitting costs about two seconds per model, so this is not a speed
    optimisation. It exists so there is a file to inspect, hand over and
    retrain independently, and so that file can never quietly disagree with the
    data it claims to describe.
    """
    fingerprint = history.dgp_fingerprint()

    classifier = None
    if not refresh:
        bundle = artifacts.load_classifier(
            fingerprint, phase_mod.CLASSIFIER_FEATURES
        )
        if bundle is not None:
            classifier = phase_mod.PhaseClassifier.restore(bundle)
    if classifier is None:
        classifier = phase_mod.PhaseClassifier().fit(phase_panel)
        artifacts.save_classifier(classifier, fingerprint)

    end_model = None
    if not refresh:
        bundle = artifacts.load_phase_end(
            fingerprint, phase_mod.DURATION_FEATURES
        )
        if bundle is not None:
            end_model = phase_mod.PhaseEndModel.restore(bundle)
    if end_model is None:
        end_model = phase_mod.PhaseEndModel().fit(phase_panel, site_phases)
        artifacts.save_phase_end(end_model, fingerprint)

    return classifier, end_model


def warm(**kwargs) -> ForecastBundle:
    """Idempotent, thread-safe startup build."""
    global _bundle
    with _lock:
        if _bundle is None:
            _bundle = build(**kwargs)
        return _bundle


def reset() -> None:
    """Drop the cached bundle. Used by tests and by clock scrubbing."""
    global _bundle
    with _lock:
        _bundle = None


def _write_backtest_card(bundle: ForecastBundle) -> None:
    """Persist the backtest summary for the deck and for offline reads."""
    card = {
        "generated_for_now": bundle.now.isoformat(),
        "clock_source": clock_adapter.clock_source(),
        "seed": config.MASTER_SEED,
        "calibrated_to_seed_rows": bundle.calib.calibrated,
        "calibration_source": bundle.calib.source,
        "fleet_size": bundle.fleet_size,
        "n_rentals": int(len(bundle.rentals)),
        "backtest": bundle.result.summary(),
    }
    path = paths.cache_dir() / "backtest_card.json"
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

def _cell_forecast(bundle: ForecastBundle, site_id: str, type_name: str,
                   horizon: int) -> dict:
    """Forecast one (type x site) cell, or refuse."""
    eligibility = model_mod.check_eligibility(bundle.panel, site_id, type_name)
    series = features.cell_series(bundle.panel, site_id, type_name)

    base = {
        "site_id": site_id,
        "type": type_name,
        "observed_weeks": int(len(series)),
        "nonzero_weeks": eligibility.nonzero_weeks,
        "total_rentals_observed": eligibility.total_rentals,
    }

    if not eligibility.eligible:
        # FR-6: refuse rather than fabricate. This is a legitimate response,
        # not an error — see PRD section 14.3.
        return {
            **base,
            "verdict": "insufficient_data",
            "reason": eligibility.reason,
            "weeks": [],
            "points": [],
            "lower": [],
            "upper": [],
        }

    path = bundle.forecaster.forecast_cell(
        bundle.panel, site_id, type_name, horizon
    )

    weeks, points, lower, upper = [], [], [], []
    for _, row in path.iterrows():
        point = float(row["point"])
        lo, hi = bundle.result.interval(point, int(row["horizon"]))
        weeks.append(pd.Timestamp(row["week_start"]).date().isoformat())
        points.append(round(point, 2))
        lower.append(round(lo, 2))
        upper.append(round(hi, 2))

    return {
        **base,
        "verdict": "ok",
        "reason": None,
        "weeks": weeks,
        "points": points,
        "lower": lower,
        "upper": upper,
    }


def _aggregate(cells: list[dict]) -> dict:
    """Roll eligible cells into one series.

    Point forecasts add. Interval half-widths are combined in quadrature, which
    assumes the cells' errors are independent — they are not perfectly, since
    monsoon hits several types at once, so the aggregate band is if anything a
    little narrow. Stated here rather than buried.
    """
    usable = [c for c in cells if c["verdict"] == "ok"]
    if not usable:
        return {"weeks": [], "points": [], "lower": [], "upper": []}

    weeks = usable[0]["weeks"]
    n = len(weeks)
    points = [0.0] * n
    lo_sq = [0.0] * n
    hi_sq = [0.0] * n

    for cell in usable:
        for i in range(n):
            p = cell["points"][i]
            points[i] += p
            lo_sq[i] += (p - cell["lower"][i]) ** 2
            hi_sq[i] += (cell["upper"][i] - p) ** 2

    return {
        "weeks": weeks,
        "points": [round(p, 2) for p in points],
        "lower": [round(max(points[i] - math.sqrt(lo_sq[i]), 0.0), 2)
                  for i in range(n)],
        "upper": [round(points[i] + math.sqrt(hi_sq[i]), 2) for i in range(n)],
    }


def get_forecast(type: str | None = None, site: str | None = None,
                 horizon: int = config.FORECAST_HORIZON_WEEKS) -> dict:
    """Answer ``GET /api/forecast?type=&site=``.

    Both filters given -> that cell. Otherwise the matching cells are rolled up,
    and every individual cell is returned alongside so the UI can show which ones
    were refused.
    """
    bundle = warm()
    result = bundle.result

    sites = [s.site_id for s in config.SITES]
    types = [t.name for t in config.EQUIPMENT_TYPES]

    if site is not None and site not in sites:
        raise KeyError(f"unknown site '{site}'")
    if type is not None and type not in types:
        raise KeyError(f"unknown equipment type '{type}'")

    selected_sites = [site] if site else sites
    selected_types = [type] if type else types

    cells = [
        _cell_forecast(bundle, s, t, horizon)
        for s in selected_sites
        for t in selected_types
    ]

    if len(cells) == 1:
        headline = cells[0]
        verdict = headline["verdict"]
        reason = headline["reason"]
    else:
        headline = _aggregate(cells)
        n_ok = sum(1 for c in cells if c["verdict"] == "ok")
        verdict = "ok" if n_ok else "insufficient_data"
        reason = None if n_ok else "no cell in this selection has enough history"

    summary = result.summary()

    return {
        # --- frozen contract (PRD section 11) ---------------------------
        "points": headline["points"],
        "lower": headline["lower"],
        "upper": headline["upper"],
        "verdict": verdict,
        "mape": summary["mape_nonzero_pct"],
        # --- additive context; the four keys above keep their shape -----
        "weeks": headline["weeks"],
        "reason": reason,
        "target": "new_rentals_commencing_per_week",
        "unit": "machines",
        "horizon_weeks": horizon,
        "interval_level": result.interval_level,
        "headline_metric": {"name": "MAE", "value": summary["mae"],
                            "unit": "machines/week"},
        "mape_note": (
            "MAPE is computed over non-zero weeks only "
            f"({summary['n_mape_weeks']} of {summary['n_predictions']} "
            "backtest points). The target is new rental starts, which is "
            "legitimately zero in many weeks, so MAE is the headline metric."
        ),
        "backtest": summary,
        "cells": cells,
        "as_of": bundle.now.isoformat(),
        "clock_source": clock_adapter.clock_source(),
        "calibrated_to_seed_rows": bundle.calib.calibrated,
        "data_note": bundle.calib.source,
    }


def get_backtest() -> dict:
    """The harness itself — PRD section 14.2 presents this as the deliverable."""
    bundle = warm()
    return {
        "as_of": bundle.now.isoformat(),
        "seed": config.MASTER_SEED,
        "fleet_size": bundle.fleet_size,
        "n_rentals": int(len(bundle.rentals)),
        "history_weeks": int(bundle.panel["week_start"].nunique()),
        "cells": int(len(config.SITES) * len(config.EQUIPMENT_TYPES)),
        "calibrated_to_seed_rows": bundle.calib.calibrated,
        "calibration_source": bundle.calib.source,
        "calibration_notes": list(bundle.calib.notes),
        "model": "PoissonRegressor (log link) on calendar + lag features, "
                 "fitted on the pooled panel",
        "backtest": bundle.result.summary(),
        "generating_process": {
            "note": "published deliberately; the model never receives these "
                    "parameters and must recover seasonality from observations",
            "signals": [
                "site project phase (excavators early, compactors late)",
                "monsoon Jun-Sep collapse, Oct-Dec catch-up",
                "Indian fiscal year Q4 flush, April collapse",
            ],
        },
    }


# --------------------------------------------------------------------------
# Phase engine queries
# --------------------------------------------------------------------------

def _site_status(bundle: ForecastBundle, site_id: str) -> dict:
    """What phase a site is in, when it ends, and what comes next.

    The **true** phase comes from the generator and the **detected** phase from
    the classifier, and both are returned. That is deliberate: the pipeline runs
    on the label so nothing downstream is blocked, while the detected phase and
    its agreement rate are what make "we can tell what phase your site is in" a
    claim rather than an assertion. Hiding the comparison would be the tell that
    it does not hold up.
    """
    site = config.SITE_BY_ID[site_id]
    week = clock_adapter.week_start(bundle.now)

    current = bundle.site_phases[
        (bundle.site_phases["site_id"] == site_id)
        & (~bundle.site_phases["is_complete"])
    ]
    if current.empty:
        return {
            "site_id": site_id, "site_name": site.name,
            "verdict": "not_active",
            "reason": "site has no phase in progress at this date",
            "current_phase": None, "detected_phase": None,
            "phase_end_date": None, "next_phase": None,
        }

    row = current.iloc[0]
    true_phase = str(row["phase"])
    started = pd.Timestamp(row["start_date"]).date()

    # Features for the live week, built by the same function that built the
    # training rows — the only reliable defence against a train/serve skew.
    live = bundle.phase_panel[
        (bundle.phase_panel["site_id"] == site_id)
        & (bundle.phase_panel["week_start"] == pd.Timestamp(week))
    ]
    if live.empty:
        live = bundle.phase_panel[
            bundle.phase_panel["site_id"] == site_id
        ].tail(1)
    if live.empty:
        return {
            "site_id": site_id, "site_name": site.name,
            "verdict": "insufficient_data",
            "reason": "no observed weeks for this site",
            "current_phase": true_phase, "detected_phase": None,
            "phase_end_date": None, "next_phase": None,
        }

    feats = live.iloc[0].to_dict()
    detected, confidence = bundle.classifier.predict(feats)
    prediction = bundle.end_model.predict(feats, true_phase)

    weeks_elapsed = float(feats.get("weeks_elapsed_in_phase", 0.0))
    end_date = None
    if prediction["verdict"] == "ok":
        end_date = week + timedelta(
            days=7 * int(round(prediction["weeks_remaining"]))
        )

    following = config.next_phase(true_phase)
    typical = bundle.end_model.mean_duration.get(
        following.name if following else "", 12.0
    )

    return {
        "site_id": site_id,
        "site_name": site.name,
        "region": site.region,
        "verdict": prediction["verdict"],
        "reason": prediction["reason"],
        "current_phase": true_phase,
        "detected_phase": detected,
        "detection_confidence": round(confidence, 3),
        "detection_agrees": detected == true_phase,
        "phase_started_on": started.isoformat(),
        "weeks_elapsed": round(weeks_elapsed, 1),
        "weeks_remaining": prediction["weeks_remaining"],
        "weeks_remaining_low": prediction["weeks_remaining_low"],
        "weeks_remaining_high": prediction["weeks_remaining_high"],
        "phase_end_date": end_date,
        "next_phase": following.name if following else None,
        "next_phase_typical_weeks": round(float(typical), 1),
        "machines_on_site": int(feats.get("machines_on_site", 0)),
    }


def _serialise_status(status: dict) -> dict:
    """Dates to ISO strings, for the API surface."""
    out = dict(status)
    end = out.get("phase_end_date")
    out["phase_end_date"] = end.isoformat() if end else None
    return out


def all_site_status() -> dict[str, dict]:
    """Every site's phase state, keyed by site_id. Dates stay as dates."""
    bundle = warm()
    return {
        site.site_id: _site_status(bundle, site.site_id)
        for site in config.SITES
    }


def get_phase(site_id: str) -> dict:
    """Answer ``GET /api/phase/{site_id}``."""
    bundle = warm()
    if site_id not in config.SITE_BY_ID:
        raise KeyError(f"unknown site '{site_id}'")
    return _serialise_status(_site_status(bundle, site_id))


def get_phase_timeline() -> dict:
    """Every site's phase state plus the observed phase windows."""
    bundle = warm()
    windows = bundle.site_phases.copy()
    windows["start_date"] = windows["start_date"].dt.date.astype(str)
    windows["end_date"] = windows["end_date"].dt.date.astype(str).replace(
        "NaT", None
    )

    return {
        "as_of": bundle.now.isoformat(),
        "clock_source": clock_adapter.clock_source(),
        "phases": list(config.PHASE_NAMES),
        "sites": [
            _serialise_status(_site_status(bundle, site.site_id))
            for site in config.SITES
        ],
        "windows": windows.to_dict(orient="records"),
    }


def get_phase_model() -> dict:
    """The evidence panel — how well both phase models actually do."""
    bundle = warm()
    classifier = bundle.classifier.report
    duration = bundle.end_model.report

    return {
        "as_of": bundle.now.isoformat(),
        "seed": config.MASTER_SEED,
        "n_sites": len(config.SITES),
        "n_phase_windows": int(len(bundle.site_phases)),
        "n_trainable_windows": int(
            (bundle.site_phases["is_complete"]
             & ~bundle.site_phases["start_censored"]).sum()
        ),
        "n_panel_rows": int(len(bundle.phase_panel)),
        "classifier": {
            "model": "XGBClassifier, 6 classes",
            "question": "which phase is this site in?",
            "features": phase_mod.CLASSIFIER_FEATURES,
            **(classifier.summary() if classifier else
               {"verdict": "insufficient_data"}),
        },
        "phase_end": {
            "model": "XGBRegressor, quantile objectives at P10/P50/P90",
            "question": "how many weeks until this phase ends?",
            "features": phase_mod.DURATION_FEATURES,
            "target_note": (
                "the model predicts the phase's TOTAL length and the remaining "
                "weeks are obtained by subtracting the elapsed ones — asking a "
                "tree ensemble for the remainder directly makes it learn a "
                "subtraction it approximates with a staircase of splits"
            ),
            "phases_refused": sorted(
                set(config.PHASE_NAMES) - bundle.end_model.trainable_phases
            ),
            **(duration.summary() if duration else
               {"verdict": "insufficient_data"}),
        },
        "equipment_mix_by_phase": (
            phase_mod.equipment_mix_by_phase(bundle.rentals)
            .round(3).to_dict(orient="index")
        ),
    }


# --------------------------------------------------------------------------
# Allocation
# --------------------------------------------------------------------------

def get_allocation() -> dict:
    """Answer ``GET /api/allocation`` — the decision board."""
    bundle = warm()
    status = all_site_status()

    # Denominator for site scaling, taken from *today's* sites rather than the
    # all-season median. Rentals collapse through the monsoon, so measuring a
    # site's size in August against a year-round median makes every site look
    # 50% smaller than it is and quietly under-provisions the whole board.
    # Comparing sites to their peers on the same date cancels the season out.
    live_sizes = [
        s["machines_on_site"] for s in status.values()
        if s.get("machines_on_site")
    ]
    denominator = (float(sorted(live_sizes)[len(live_sizes) // 2])
                   if live_sizes else bundle.typical_site_size)

    recommendations = allocate_mod.recommend(
        bundle.rentals, status, bundle.peaks,
        typical_site_size=denominator, now=bundle.now,
    )
    surplus = allocate_mod.surplus_report(bundle.rentals, status, now=bundle.now)

    redeploys = [r for r in recommendations if r.decision == "redeploy"]
    total_saving = sum(r.saving_inr for r in redeploys)

    return {
        "as_of": bundle.now.isoformat(),
        "clock_source": clock_adapter.clock_source(),
        "horizon_weeks": allocate_mod.HORIZON_WEEKS,
        "summary": {
            "recommendations": len(recommendations),
            "redeploy": len(redeploys),
            "rent": sum(1 for r in recommendations if r.decision == "rent"),
            "saving_inr": round(total_saving),
            "machines_running_past_need": len(surplus),
            "idle_spend_inr": round(sum(s["idle_cost_inr"] for s in surplus)),
        },
        "recommendations": [r.to_dict() for r in recommendations],
        "surplus": surplus,
        "costing": {
            "day_rate_inr": config.DAY_RATE_INR,
            "mobilisation_inr": config.MOBILISATION_INR,
            "transport_inr_per_km": config.TRANSPORT_INR_PER_KM,
            "transport_handling_inr": config.TRANSPORT_HANDLING_INR,
            "blocked_day_inr": config.BLOCKED_DAY_INR,
            "note": (
                "every recommendation is the cheaper of two priced options, "
                "both returned. Redeployment does not pay hire — that contract "
                "is already running — so it pays haulage, any waiting, and any "
                "extension needed past the existing expiry."
            ),
        },
    }


def demand_table() -> pd.DataFrame:
    """The weekly panel, for MOD-12 redeployment and MOD-14 narration."""
    return warm().panel.copy()


def rental_history() -> pd.DataFrame:
    """The synthetic rental records, for MOD-03/MOD-07 if they want them."""
    return warm().rentals.copy()


__all__ = [
    "ForecastBundle", "build", "warm", "reset",
    "get_forecast", "get_backtest", "demand_table", "rental_history",
    "get_phase", "get_phase_timeline", "get_phase_model", "get_allocation",
    "all_site_status",
]
