"""Tests for the synthetic history generator (MOD-11, step 2).

The gate that matters is ``test_seasonal_signal_is_recoverable``. Everything
downstream — the model, the intervals, the MAPE on screen — is worthless if the
generated history is noise with a squiggle drawn through it. That test asserts a
seasonal predictor beats a flat mean on held-out weeks. If it fails, the fix is
to strengthen the generating signals in ``config.py``, not to weaken the test.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.forecast import (
    calibration,
    clock_adapter,
    config,
    features,
    history,
    model as model_mod,
)

NOW = date(2025, 8, 18)          # Monday, ISO week 34 of 2025
WEEKS = config.HISTORY_WEEKS


@pytest.fixture(scope="module")
def rentals() -> pd.DataFrame:
    return history.generate_history(seed=config.MASTER_SEED, now=NOW, weeks=WEEKS)


@pytest.fixture(scope="module")
def panel(rentals: pd.DataFrame) -> pd.DataFrame:
    return features.weekly_panel(rentals, now=NOW, weeks=WEEKS)


# --------------------------------------------------------------------------
# Determinism — NFR-3
# --------------------------------------------------------------------------

def test_generation_is_deterministic():
    a = history.generate_history(seed=config.MASTER_SEED, now=NOW, weeks=WEEKS)
    b = history.generate_history(seed=config.MASTER_SEED, now=NOW, weeks=WEEKS)
    pd.testing.assert_frame_equal(a, b)


def test_different_seed_gives_different_history():
    a = history.generate_history(seed=config.MASTER_SEED, now=NOW, weeks=WEEKS)
    b = history.generate_history(seed=config.MASTER_SEED + 1, now=NOW, weeks=WEEKS)
    assert len(a) != len(b) or not a["check_in"].equals(b["check_in"])


def test_cell_seeding_is_independent():
    """Reordering or adding a cell must not perturb another cell's draws.

    This is why rngs are spawned per (site, type) rather than drawn from one
    global stream — it keeps backtest numbers stable while the config evolves.
    """
    rng_a = history._cell_rng(config.MASTER_SEED, 0, 0)
    rng_b = history._cell_rng(config.MASTER_SEED, 0, 0)
    rng_c = history._cell_rng(config.MASTER_SEED, 1, 0)

    assert rng_a.random(5).tolist() == rng_b.random(5).tolist()
    assert rng_a.random(5).tolist() != rng_c.random(5).tolist()


# --------------------------------------------------------------------------
# Structural sanity
# --------------------------------------------------------------------------

def test_history_covers_the_requested_window(rentals: pd.DataFrame):
    last_full_week = clock_adapter.week_start(NOW) - timedelta(days=7)
    first_week = last_full_week - timedelta(days=7 * (WEEKS - 1))

    starts = pd.to_datetime(rentals["check_in"]).dt.date
    assert starts.min() >= first_week
    # Arrivals fall anywhere in their week, so the last start can be up to six
    # days past the final Monday.
    assert starts.max() <= last_full_week + timedelta(days=6)


def test_no_machine_is_double_booked(rentals: pd.DataFrame):
    """Fleet allocation must be physically consistent, or MOD-03 inherits a lie."""
    frame = rentals.sort_values(["equipment_id", "check_in"])
    for _, group in frame.groupby("equipment_id"):
        ends = group["check_out"].values[:-1]
        starts = group["check_in"].values[1:]
        assert (starts >= ends).all()


def test_panel_is_complete_over_each_site_s_life(panel: pd.DataFrame):
    """Zero weeks are rows, but only for weeks the site actually existed.

    Two failure modes sit either side of this, and the panel must avoid both.

    Dropping quiet weeks would bias every level upward — under a new-starts
    target the zeros carry most of the signal, so every week a site was live
    must appear whether or not it rented anything.

    Padding a site's pre-groundbreaking weeks with zeros is the opposite error:
    it invents observations nobody made and drags a young site's level toward
    zero. A plot of land is not a cell with no demand; it is not a cell.
    """
    schedules = history.build_schedules(weeks=WEEKS)
    expected = sum(
        len([w for w in range(WEEKS) if schedules[site.site_id].is_active_at(w)])
        for site in config.SITES
    ) * len(config.EQUIPMENT_TYPES)

    assert len(panel) == expected
    assert panel["y"].isna().sum() == 0
    assert (panel["y"] == 0).sum() > 0

    # Every cell's weeks are contiguous — no holes punched in the middle.
    for (_, _), group in panel.groupby(["site_id", "type"]):
        weeks = sorted(group["week_start"])
        gaps = {(b - a).days for a, b in zip(weeks, weeks[1:])}
        assert gaps <= {7}, "panel has a hole in the middle of a site's life"


def test_panel_counts_match_the_rentals(rentals: pd.DataFrame,
                                        panel: pd.DataFrame):
    """Every rental with a site lands in exactly one (site, type, week) cell.

    Rentals whose site was never recorded (config.RATE_UNASSIGNED_SITE) are
    excluded on both sides: they belong to no site-week series, and counting
    them under a NaN key is how a phantom site appears in the panel.
    """
    placed = rentals["site_id"].notna().sum()

    assert placed < len(rentals), (
        "no site-less rentals were generated — the anomaly detector's "
        "unassigned_equipment rule would have nothing to find"
    )
    assert panel["y"].sum() == pytest.approx(placed)


def test_fleet_size_is_plausible_for_the_number_of_sites(rentals: pd.DataFrame):
    """Machines per site has to look like a contractor, not an arithmetic
    accident.

    Bounded per-site rather than absolutely, because the fleet is an *output* of
    demand here: the generator adds a machine whenever nothing is free, so
    doubling the sites doubles the fleet. An absolute bound would just have to
    be rewritten every time a site is added, which is how a test stops meaning
    anything.
    """
    fleet = rentals["equipment_id"].nunique()
    per_site = fleet / len(config.SITES)
    assert 10 <= per_site <= 60, (
        f"fleet of {fleet} over {len(config.SITES)} sites is "
        f"{per_site:.0f} machines per site"
    )


# --------------------------------------------------------------------------
# THE GATE — is there anything here to learn?
# --------------------------------------------------------------------------

def _split(panel: pd.DataFrame, train_weeks: int = 78):
    weeks = sorted(panel["week_start"].unique())
    cutoff = weeks[train_weeks - 1]
    train = features.training_frame(panel[panel["week_start"] <= cutoff])
    test = panel[panel["week_start"] > cutoff]
    return train, test


def test_seasonal_signal_is_recoverable(panel: pd.DataFrame):
    """A seasonal predictor must beat a flat mean on held-out weeks.

    Run on the fleet-aggregate weekly series, where per-cell Poisson noise
    averages out and the seasonal structure is unambiguous. If this fails the
    generated history has no learnable signal and no forecast built on it means
    anything.
    """
    train, test = _split(panel)

    flat = model_mod.FlatMeanBaseline().fit(train)
    seasonal = model_mod.SeasonalIndexBaseline().fit(train)

    scored = test.copy()
    scored["flat"] = flat.predict(test)
    scored["seasonal"] = seasonal.predict(test)

    weekly = scored.groupby("week_start")[["y", "flat", "seasonal"]].sum()
    mae_flat = float(np.mean(np.abs(weekly["y"] - weekly["flat"])))
    mae_seasonal = float(np.mean(np.abs(weekly["y"] - weekly["seasonal"])))

    assert mae_seasonal < mae_flat * 0.80, (
        "no recoverable seasonality in the generated history: "
        f"seasonal MAE {mae_seasonal:.2f} vs flat MAE {mae_flat:.2f}. "
        "Strengthen the signals in config.py rather than relaxing this bound."
    )


def test_seasonal_signal_survives_at_cell_level(panel: pd.DataFrame):
    """Weaker claim, per cell, where Poisson noise is not averaged away.

    The margin is deliberately small: single-cell counts really are noisy, and
    that is precisely why prediction intervals and `insufficient_data` exist.
    """
    train, test = _split(panel)

    flat = model_mod.FlatMeanBaseline().fit(train)
    seasonal = model_mod.SeasonalIndexBaseline().fit(train)

    mae_flat = float(np.mean(np.abs(test["y"].values - flat.predict(test))))
    mae_seasonal = float(np.mean(np.abs(test["y"].values - seasonal.predict(test))))

    assert mae_seasonal < mae_flat


def test_monsoon_dip_is_actually_present(panel: pd.DataFrame):
    """The headline domain claim must be visible in the data we generated."""
    monsoon = panel[panel["month"].isin([7, 8])]["y"].mean()
    catch_up = panel[panel["month"].isin([10, 11])]["y"].mean()
    assert monsoon < catch_up * 0.65, (
        f"monsoon mean {monsoon:.2f} vs catch-up {catch_up:.2f} — the monsoon "
        "signal we claim on the slide is not in the data"
    )


def test_sparse_cells_are_actually_sparse(panel: pd.DataFrame):
    """Starved cells must trip the refusal path, not merely be quiet."""
    refused = 0
    for (site_id, type_name) in config.SPARSE_CELLS:
        if not model_mod.check_eligibility(panel, site_id, type_name).eligible:
            refused += 1
    assert refused >= 3, (
        f"only {refused} sparse cells return insufficient_data — FR-6's "
        "refusal path is barely exercised"
    )


def test_healthy_cells_are_forecastable(panel: pd.DataFrame):
    """The refusal must not be so aggressive that nothing is forecastable."""
    eligible = sum(
        model_mod.check_eligibility(panel, s.site_id, t.name).eligible
        for s in config.SITES
        for t in config.EQUIPMENT_TYPES
    )
    total = len(config.SITES) * len(config.EQUIPMENT_TYPES)
    assert eligible >= total * 0.6, f"only {eligible}/{total} cells forecastable"


# --------------------------------------------------------------------------
# Parity with the supplied rows
# --------------------------------------------------------------------------

def test_durations_match_the_seed_rows(rentals: pd.DataFrame):
    """Synthetic rentals must look like a bigger sample of the real ones.

    Skips loudly rather than passing vacuously when the seed file is absent —
    an uncalibrated generator that reports green is the failure mode this test
    exists to prevent.
    """
    calib = calibration.load_calibration()
    if not calib.calibrated:
        pytest.skip(
            "data/seed_assets.csv is not committed — the generator is running "
            "on fallback distributions and parity cannot be checked. This is a "
            "real gap, not a passing test."
        )

    # Computed from the dates, not read from a stored column — the span is
    # derived and derived values are never persisted.
    span = (rentals["check_out"] - rentals["check_in"]).dt.days
    generated_mean = float(span.mean())
    expected = calib.duration_mean_days
    assert generated_mean == pytest.approx(expected, rel=0.25), (
        f"generated mean duration {generated_mean:.1f}d does not match the "
        f"seed rows' fitted mean {expected:.1f}d"
    )


def test_declared_defects_are_present(rentals: pd.DataFrame):
    """Synthetic history carries something for the anomaly detector to find.

    Spotless data would leave the detector with nothing to say about 99% of the
    fleet and make it look like a toy.
    """
    engine = rentals["engine_hours_per_day"]
    idle = rentals["idle_hours_per_day"]

    idle_exceeds = (idle > engine).sum()
    over_budget = (engine + idle > 24).sum()
    span = (rentals["check_out"] - rentals["check_in"]).dt.days
    stated_mismatch = (rentals["rental_days"] != span).sum()

    assert idle_exceeds > 0, "no severely under-utilised machines to detect"
    assert over_budget > 0, "no blown-day-budget records to detect"
    assert stated_mismatch > 0, "no stated-vs-actual duration mismatches"

    # Declared rates, not an accident. Loose bounds so ordinary sampling
    # variation does not fail the build.
    n = len(rentals)
    assert idle_exceeds / n < config.RATE_IDLE_EXCEEDS_ENGINE * 2.5
    assert over_budget / n < config.DEFECT_RATE_DAY_BUDGET * 3.0


def test_no_row_claims_more_hours_than_a_day_has(rentals: pd.DataFrame):
    """The day budget may be blown, but only arguably.

    ``engine + idle`` above 24 is a bad record and the detector should say so.
    ``idle`` alone above 24 is not a finding — it is a bug in the generator, and
    the one claim in this dataset that an engineer in the room could refute on
    the spot. Injected rows are capped rather than left unbounded.
    """
    engine = rentals["engine_hours_per_day"]
    idle = rentals["idle_hours_per_day"]

    assert (engine >= 0).all() and (idle >= 0).all()
    assert idle.max() <= 24, f"a row claims {idle.max():.1f} idle hours in a day"
    assert engine.max() <= 24, f"a row claims {engine.max():.1f} engine hours"
    assert (engine + idle).max() <= config.MAX_DAY_HOURS_DEFECT


# --------------------------------------------------------------------------
# Simulated fields the brief requires and the schema omits (PRD section 3, A4)
# --------------------------------------------------------------------------

def test_fuel_is_derived_from_engine_hours_not_invented(rentals: pd.DataFrame):
    """Fuel must be a function of engine-on time, not an independent draw.

    The first thing anyone does with a fuel column is plot it against hours. An
    independently generated column shows no relationship and the simulation is
    exposed on the spot.

    Checked *within* machine class. Pooled across classes the correlation is
    diluted to ~0.6 by the burn rates themselves — a telehandler running ten
    hours genuinely burns less than an excavator running ten hours — so the
    pooled figure would understate how tightly the columns are coupled.
    """
    engine_on = (
        rentals["engine_hours_per_day"] + rentals["idle_hours_per_day"]
    )

    for etype in config.EQUIPMENT_TYPES:
        mask = rentals["type"] == etype.name
        correlation = float(rentals.loc[mask, "fuel_l_per_day"].corr(
            engine_on[mask]
        ))
        assert correlation > 0.85, (
            f"{etype.name}: fuel/engine-on correlation is only "
            f"{correlation:.2f} — fuel reads as an invented column rather than "
            "a derived one"
        )


def test_fuel_burn_rate_is_plausible_per_machine_class(rentals: pd.DataFrame):
    """Implied litres/hour must land near the configured class burn rate."""
    engine_on = (
        rentals["engine_hours_per_day"] + rentals["idle_hours_per_day"]
    )
    implied = rentals["fuel_l_per_day"] / engine_on.replace(0, np.nan)

    for etype in config.EQUIPMENT_TYPES:
        rate = float(implied[rentals["type"] == etype.name].mean())
        # Idle burns at a fraction of the working rate, so the blended figure
        # sits below the working rate but must stay the right side of it.
        assert 0.4 * etype.fuel_burn_l_per_h < rate <= etype.fuel_burn_l_per_h, (
            f"{etype.name}: implied {rate:.1f} L/h against a working rate of "
            f"{etype.fuel_burn_l_per_h} L/h"
        )


def test_idle_burns_fuel_but_less_than_working(rentals: pd.DataFrame):
    """Idle fuel burn is what makes idle hours cost money rather than only time."""
    assert 0.0 < config.IDLE_FUEL_FRACTION < 1.0
    assert (rentals["fuel_l_per_day"] > 0).all()


def test_geo_falls_inside_its_own_site(rentals: pd.DataFrame):
    tolerance = config.GEO_JITTER_DEG + 1e-9   # coordinates are rounded to 5dp
    for site in config.SITES:
        rows = rentals[rentals["site_id"] == site.site_id]
        assert (rows["lat"] - site.lat).abs().max() <= tolerance
        assert (rows["lon"] - site.lon).abs().max() <= tolerance


def test_simulated_rows_are_labelled_as_simulated(rentals: pd.DataFrame):
    """Assumption A4: simulated values must say so.

    The label is the point. Volunteering it earns more credibility with engineer
    judges than quietly presenting simulated values as measured ones.

    Every row here is synthetic, so the single `source` column carries it. Once
    MOD-01 loads the 7 supplied rows — measured hours beside simulated fuel and
    geo in one record — per-field flags will be needed. Not yet.
    """
    assert (rentals["source"] == "sim").all()


def test_column_order_matches_the_declared_schema(rentals: pd.DataFrame):
    assert list(rentals.columns) == history.RENTAL_COLUMNS


def test_ground_truth_rows_are_not_fabricated(rentals: pd.DataFrame):
    """MOD-11 generates simulated history only.

    The 7 supplied rows are MOD-01's to load verbatim. Nothing here may claim
    ground-truth provenance (PRD A2).
    """
    assert not rentals["is_ground_truth"].any()
    assert (rentals["source"] == "sim").all()
