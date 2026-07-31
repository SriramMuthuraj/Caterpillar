"""Tests for the forecaster, the backtest harness and the API surface."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.forecast import (
    backtest as backtest_mod,
    config,
    features,
    history,
    model as model_mod,
    service,
)

NOW = date(2025, 8, 18)
WEEKS = config.HISTORY_WEEKS


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    rentals = history.generate_history(
        seed=config.MASTER_SEED, now=NOW, weeks=WEEKS
    )
    return features.weekly_panel(rentals, now=NOW, weeks=WEEKS)


@pytest.fixture(scope="module")
def fitted(panel: pd.DataFrame) -> model_mod.DemandForecaster:
    return model_mod.DemandForecaster().fit(panel)


@pytest.fixture(scope="module")
def result(panel: pd.DataFrame) -> backtest_mod.BacktestResult:
    return backtest_mod.run_backtest(panel)


def _busy_cell(panel: pd.DataFrame) -> tuple[str, str]:
    for site in config.SITES:
        for etype in config.EQUIPMENT_TYPES:
            if model_mod.check_eligibility(
                panel, site.site_id, etype.name
            ).eligible:
                return site.site_id, etype.name
    raise AssertionError("no eligible cell")


# --------------------------------------------------------------------------
# No leakage
# --------------------------------------------------------------------------

def test_model_never_sees_the_generating_process(panel: pd.DataFrame):
    """The forecaster gets calendar and observed history — nothing else.

    Site phase, project progress and the monsoon multiplier itself are DGP
    internals. Handing any of them to the model would make the backtest a
    measurement of our own arithmetic rather than of forecasting skill.
    """
    design = features.encode(features.training_frame(panel))
    forbidden = (
        "progress", "phase", "lambda", "intensity", "monsoon_mult",
        "fiscal_mult", "scale", "share", "growth", "peak", "start_week",
    )
    leaked = [
        c for c in design.columns
        if any(token in c.lower() for token in forbidden)
    ]
    assert not leaked, f"generating-process features leaked into the model: {leaked}"


def test_features_do_not_use_the_current_week(panel: pd.DataFrame):
    """Lags must be strictly backward-looking.

    Constructed so that lag_1 for week t equals y at week t-1; any off-by-one
    here would let the model read the answer.
    """
    cell = features.cell_series(panel, config.SITES[0].site_id,
                               config.EQUIPMENT_TYPES[0].name)
    for i in range(1, len(cell)):
        assert cell["lag_1"].iloc[i] == cell["y"].iloc[i - 1]
    assert pd.isna(cell["lag_1"].iloc[0])


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

def test_model_is_deterministic(panel: pd.DataFrame):
    a = model_mod.DemandForecaster().fit(panel)
    b = model_mod.DemandForecaster().fit(panel)
    site, etype = _busy_cell(panel)
    pd.testing.assert_frame_equal(
        a.forecast_cell(panel, site, etype), b.forecast_cell(panel, site, etype)
    )


def test_forecast_is_non_negative_and_finite(panel: pd.DataFrame,
                                             fitted: model_mod.DemandForecaster):
    site, etype = _busy_cell(panel)
    path = fitted.forecast_cell(panel, site, etype, horizon=8)
    assert len(path) == 8
    assert (path["point"] >= 0).all()
    assert path["point"].notna().all()


def test_forecast_starts_the_week_after_history(
    panel: pd.DataFrame, fitted: model_mod.DemandForecaster
):
    site, etype = _busy_cell(panel)
    last_observed = panel["week_start"].max()
    path = fitted.forecast_cell(panel, site, etype, horizon=4)
    assert path["week_start"].iloc[0] == last_observed + pd.Timedelta(days=7)


# --------------------------------------------------------------------------
# Backtest
# --------------------------------------------------------------------------

def test_backtest_beats_the_seasonal_baseline(result: backtest_mod.BacktestResult):
    """The model must earn its place against a baseline anyone could write."""
    assert result.mae < result.baseline_mae, (
        f"model MAE {result.mae:.3f} does not beat seasonal baseline "
        f"{result.baseline_mae:.3f} — ship the baseline instead"
    )
    assert result.skill_vs_seasonal > 0


def test_backtest_error_grows_with_horizon(result: backtest_mod.BacktestResult):
    """Sanity check on the harness itself.

    Week 4 must be harder than week 1. If it is not, information is leaking
    across origins.
    """
    by_h = result.mae_by_horizon
    assert by_h[max(by_h)] >= by_h[min(by_h)] * 0.95


def test_intervals_are_ordered_and_calibrated(result: backtest_mod.BacktestResult):
    lo, hi = result.interval(3.0, horizon=1)
    assert 0.0 <= lo <= 3.0 <= hi

    # Bands are derived from these residuals, so this checks the arithmetic
    # rather than validating coverage out of sample.
    assert abs(result.coverage - result.interval_level) < 0.12


def test_interval_width_scales_with_level(result: backtest_mod.BacktestResult):
    """Poisson variance grows with the mean; a flat band would be wrong."""
    quiet_lo, quiet_hi = result.interval(0.5, horizon=1)
    busy_lo, busy_hi = result.interval(8.0, horizon=1)
    assert (busy_hi - busy_lo) > (quiet_hi - quiet_lo)


def test_far_horizon_reuses_the_widest_measured_band(
    result: backtest_mod.BacktestResult
):
    """Never invent a tighter interval than was actually measured."""
    measured = result.interval(3.0, horizon=max(result.residual_quantiles))
    beyond = result.interval(3.0, horizon=99)
    assert beyond == measured


# --------------------------------------------------------------------------
# The refusal — FR-6
# --------------------------------------------------------------------------

def test_insufficient_data_is_returned_not_raised():
    """`insufficient_data` is a 200 response, not an error (PRD 14.3)."""
    service.reset()
    starved = next(iter(config.SPARSE_CELLS))
    payload = service.get_forecast(site=starved[0], type=starved[1])

    if payload["verdict"] == "insufficient_data":
        assert payload["points"] == []
        assert payload["reason"]
    else:
        pytest.skip(f"{starved} became eligible; covered by test_history")


def test_at_least_one_cell_refuses():
    service.reset()
    payload = service.get_forecast()
    verdicts = {c["verdict"] for c in payload["cells"]}
    assert "insufficient_data" in verdicts
    assert "ok" in verdicts


# --------------------------------------------------------------------------
# API contract — PRD section 11
# --------------------------------------------------------------------------

def test_response_carries_the_frozen_keys():
    service.reset()
    payload = service.get_forecast(type="Excavator", site="S002")
    for key in ("points", "lower", "upper", "verdict", "mape"):
        assert key in payload

    assert len(payload["points"]) == len(payload["lower"]) == len(payload["upper"])
    assert len(payload["points"]) == len(payload["weeks"])
    assert payload["verdict"] in ("ok", "insufficient_data")


def test_bands_bracket_the_point_forecast():
    service.reset()
    payload = service.get_forecast(type="Excavator", site="S002")
    if payload["verdict"] != "ok":
        pytest.skip("cell refused")
    for lo, point, hi in zip(payload["lower"], payload["points"],
                             payload["upper"]):
        assert lo <= point <= hi


def test_unknown_filters_are_rejected():
    service.reset()
    with pytest.raises(KeyError):
        service.get_forecast(site="S999")
    with pytest.raises(KeyError):
        service.get_forecast(type="Hovercraft")


def test_aggregate_rolls_up_eligible_cells():
    service.reset()
    fleet = service.get_forecast()
    one = service.get_forecast(type="Excavator", site="S002")
    if one["verdict"] == "ok":
        assert fleet["points"][0] >= one["points"][0]


def test_no_wall_clock_anywhere_in_the_package():
    """MOD-02 is the only source of `now` (project invariant).

    Parsed rather than grepped: the invariant is about executed calls, and the
    strings ``datetime.now()`` and ``date.today()`` appear legitimately in the
    docstrings that explain why they are forbidden.
    """
    import ast
    from pathlib import Path

    banned = {"now", "today", "utcnow", "now_utc"}
    package = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in banned:
                continue
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id in {"datetime", "date",
                                                            "time", "pd"}:
                offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, f"wall-clock call at {offenders}"


def test_service_is_deterministic_across_rebuilds():
    """NFR-3 end to end: same seed, same clock, same numbers."""
    service.reset()
    first = service.get_forecast(type="Excavator", site="S002")
    service.reset()
    second = service.get_forecast(type="Excavator", site="S002")
    assert first["points"] == second["points"]
    assert first["lower"] == second["lower"]
    assert first["backtest"]["mae"] == second["backtest"]["mae"]
