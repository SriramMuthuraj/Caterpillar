"""Tests for the phase engine and the allocation board.

The two that matter most are ``test_no_generator_parameter_reaches_the_models``
and ``test_pace_feature_only_uses_already_finished_phases``. Everything else
here checks that the pipeline runs; those two check that its scores mean
anything at all.
"""

from __future__ import annotations

import ast
import inspect
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.forecast import (
    allocate,
    clock_adapter,
    config,
    history,
    phase,
    service,
)

WEEKS = config.HISTORY_WEEKS


@pytest.fixture(scope="module")
def rentals() -> pd.DataFrame:
    return history.cached_history(weeks=WEEKS)


@pytest.fixture(scope="module")
def site_phases() -> pd.DataFrame:
    return history.site_phase_windows(weeks=WEEKS)


@pytest.fixture(scope="module")
def panel(rentals: pd.DataFrame, site_phases: pd.DataFrame) -> pd.DataFrame:
    return phase.build_panel(rentals, site_phases)


@pytest.fixture(scope="module")
def classifier(panel: pd.DataFrame) -> phase.PhaseClassifier:
    return phase.PhaseClassifier().fit(panel)


@pytest.fixture(scope="module")
def end_model(panel: pd.DataFrame,
              site_phases: pd.DataFrame) -> phase.PhaseEndModel:
    return phase.PhaseEndModel().fit(panel, site_phases)


# --------------------------------------------------------------------------
# Phase windows — the ground truth everything else is scored against
# --------------------------------------------------------------------------

def test_every_site_has_exactly_one_phase_in_progress(site_phases: pd.DataFrame):
    """A live site is in exactly one phase. Two would be a schedule bug."""
    current = site_phases[~site_phases["is_complete"]]
    assert len(current) == len(config.SITES)
    assert current["site_id"].nunique() == len(config.SITES)


def test_phases_run_in_order_without_gaps(site_phases: pd.DataFrame):
    """Phases follow one another; a project cannot skip foundation."""
    for site_id, group in site_phases.groupby("site_id"):
        group = group.sort_values("start_date")
        orders = list(group["phase_order"])
        assert orders == sorted(orders), f"{site_id} phases out of order"
        assert len(set(orders)) == len(orders), f"{site_id} repeats a phase"


def test_in_progress_phases_have_no_end_date(site_phases: pd.DataFrame):
    """An unfinished phase must not carry an end date.

    If it did, the duration model would train on the answer to the question it
    is asked at serving time, and every score in the report would be a fiction.
    """
    current = site_phases[~site_phases["is_complete"]]
    assert current["end_date"].isna().all()
    assert current["duration_weeks"].isna().all()


def test_phase_durations_actually_vary(site_phases: pd.DataFrame):
    """There must be something to predict.

    If every site ran a phase for the same number of weeks, the phase-end model
    would be a lookup of a constant, would score perfectly, and would mean
    nothing. Slip is the whole prediction problem.
    """
    completed = site_phases[
        site_phases["is_complete"] & ~site_phases["start_censored"]
    ]
    for name, group in completed.groupby("phase"):
        if len(group) < 4:
            continue
        spread = group["duration_weeks"].std()
        assert spread > 1.0, (
            f"{name} durations barely vary (sd={spread:.2f} weeks) — the "
            f"phase-end model would be predicting a constant"
        )


def test_sites_span_every_phase_right_now(site_phases: pd.DataFrame):
    """The demo has nothing to say if every site is at the same stage."""
    current = set(site_phases[~site_phases["is_complete"]]["phase"])
    assert current == set(config.PHASE_NAMES), (
        f"phases missing from the live fleet: "
        f"{set(config.PHASE_NAMES) - current}"
    )


# --------------------------------------------------------------------------
# Leakage — the tests that make every other number meaningful
# --------------------------------------------------------------------------

def test_no_generator_parameter_reaches_the_models():
    """Neither model may see anything only the simulator knows.

    ``Site.pace`` and the drawn phase durations determine the answer outright.
    A model handed either would score beautifully and be worthless on real data,
    where no such column exists. The features are checked by name because that
    is the boundary a future edit is most likely to cross by accident.
    """
    forbidden = {
        "pace", "site_pace", "phase_frac_now", "progress_now",
        "true_phase", "duration_weeks", "phase_total_weeks",
        "weeks_remaining", "end_week", "start_week", "slip",
    }
    for name in phase.CLASSIFIER_FEATURES + phase.DURATION_FEATURES:
        assert name not in forbidden, f"'{name}' is a generator parameter"

    # `site_pace_observed` is legitimate and deliberately near-miss named: it is
    # measured from finished phases, not read off the config.
    assert "site_pace_observed" in phase.DURATION_FEATURES


def test_the_target_is_not_among_the_features():
    """A model must not be handed the thing it is asked to predict."""
    assert "phase_total_weeks" not in phase.DURATION_FEATURES
    assert "weeks_remaining" not in phase.DURATION_FEATURES
    assert "phase" not in phase.CLASSIFIER_FEATURES


def test_pace_feature_only_uses_already_finished_phases(panel: pd.DataFrame,
                                                        site_phases: pd.DataFrame):
    """A site's track record must exclude the phase being predicted.

    ``site_pace_observed`` is the feature that lets the model beat a flat
    average, so it is also the one most able to cheat. Built from phases that
    end after the row's own week — including the row's own phase — it would be
    reading the label. This asserts the value equals what a strict
    already-finished recomputation gives.
    """
    planned = {p.name: float(p.base_weeks) for p in config.PHASES}
    finished = site_phases[
        site_phases["is_complete"] & ~site_phases["start_censored"]
    ]

    checked = 0
    for row in panel.sample(n=min(120, len(panel)), random_state=0).itertuples():
        prior = finished[
            (finished["site_id"] == row.site_id)
            & (finished["end_date"] < row.week_start)
        ]
        expected = (
            (prior["duration_weeks"] / prior["phase"].map(planned)).mean()
            if len(prior) else 1.0
        )
        assert row.site_pace_observed == pytest.approx(expected, abs=1e-9), (
            f"{row.site_id} at {row.week_start.date()} used a phase that had "
            f"not finished yet"
        )
        checked += 1

    assert checked > 0


def test_splits_hold_out_whole_windows_not_weeks(panel: pd.DataFrame):
    """Adjacent weeks of one phase must never straddle a split.

    They are near-duplicates — same site, same machines, a mix that moved a
    little. Split them at random and the model recognises the site instead of
    the pattern, and the held-out score is meaningless.
    """
    folds = phase.window_folds(panel)
    assert folds, "expected at least one fold"

    for train, test in folds:
        overlap = set(train["window_id"]) & set(test["window_id"])
        assert not overlap, f"windows on both sides of a split: {overlap}"

    # Every window is held out exactly once across the folds.
    held_out = [w for _, test in folds for w in test["window_id"].unique()]
    assert len(held_out) == len(set(held_out))
    assert set(held_out) == set(panel["window_id"].unique())


def test_no_wall_clock_call_anywhere_in_the_package():
    """``datetime.now()`` would break the demo's time travel silently.

    Every date in this project is historical, so a real clock makes nothing
    active and the allocation board empties out. Checked by AST rather than by
    grep so a comment mentioning it does not fail the build.
    """
    package = Path(phase.__file__).parent
    offenders: list[str] = []

    for source in package.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute)
                    and func.attr in {"now", "today", "utcnow"}
                    and isinstance(func.value, ast.Name)
                    and func.value.id in {"datetime", "date"}):
                offenders.append(f"{source.name}:{node.lineno}")

    assert not offenders, f"wall-clock call: {offenders}"


# --------------------------------------------------------------------------
# The classifier
# --------------------------------------------------------------------------

def test_classifier_beats_guessing_by_a_wide_margin(
        classifier: phase.PhaseClassifier):
    """Recovering the phase from equipment alone has to actually work.

    Six classes, so chance is 0.167. Anything near that and "we can tell what
    phase your site is in" is not a claim we can make.
    """
    report = classifier.report
    assert report is not None

    chance = 1.0 / len(config.PHASE_NAMES)
    assert report.accuracy > 3 * chance, (
        f"accuracy {report.accuracy:.3f} is not meaningfully above the "
        f"{chance:.3f} you would get by guessing"
    )
    # Confusing erection with grading is a near miss; confusing it with
    # clearing is not. The ordering has to be recovered even when the exact
    # phase is not.
    assert report.within_one_phase > 0.90


def test_classifier_scores_every_phase(classifier: phase.PhaseClassifier):
    """A headline accuracy hides which phases the model cannot see."""
    report = classifier.report
    assert report is not None
    assert set(report.per_phase_accuracy) == set(config.PHASE_NAMES)


def test_classifier_returns_a_calibrated_looking_probability(
        classifier: phase.PhaseClassifier, panel: pd.DataFrame):
    row = panel.iloc[len(panel) // 2].to_dict()
    label, confidence = classifier.predict(row)
    assert label in config.PHASE_NAMES
    assert 0.0 <= confidence <= 1.0


# --------------------------------------------------------------------------
# The phase-end model
# --------------------------------------------------------------------------

def test_phase_end_model_beats_a_schedule_only_baseline(
        end_model: phase.PhaseEndModel):
    """The bar: "this phase usually takes N weeks, minus what has elapsed".

    That baseline needs no model at all. If XGBoost cannot beat it, the honest
    thing is to ship the baseline and say so — so this test failing is a real
    signal, not a flake to be relaxed.
    """
    report = end_model.report
    assert report is not None
    assert report.mae_weeks < report.baseline_mae_weeks, (
        f"model MAE {report.mae_weeks:.2f} weeks does not beat the "
        f"schedule-only baseline {report.baseline_mae_weeks:.2f} — ship the "
        f"baseline instead"
    )


def test_prediction_intervals_cover_what_they_claim(
        end_model: phase.PhaseEndModel):
    """An 80% band that covers 40% is worse than no band at all.

    The allocator sizes its slack on this width, so a band that lies produces
    confidently wrong recommendations.
    """
    report = end_model.report
    assert report is not None
    assert 0.72 <= report.coverage <= 0.90, (
        f"nominal 80% interval covers {report.coverage:.1%}"
    )


def test_refuses_where_too_few_phases_have_completed(
        end_model: phase.PhaseEndModel, panel: pd.DataFrame):
    """Refusing is a supported answer, not an error path.

    Demobilisation is the last phase, so no site has been observed finishing
    one. A number there would be invented, and the allocator would act on it.
    """
    unseen = set(config.PHASE_NAMES) - end_model.trainable_phases
    assert unseen, "expected at least one phase with too little history"

    row = panel.iloc[0].to_dict()
    result = end_model.predict(row, sorted(unseen)[0])
    assert result["verdict"] == "insufficient_data"
    assert result["weeks_remaining"] is None
    assert result["reason"]


def test_predictions_are_ordered_and_non_negative(
        end_model: phase.PhaseEndModel, panel: pd.DataFrame):
    """low <= point <= high, and no phase ends in a negative number of weeks."""
    trainable = sorted(end_model.trainable_phases)
    assert trainable

    for row in panel.sample(n=min(40, len(panel)), random_state=1).to_dict("records"):
        result = end_model.predict(row, trainable[0])
        assert result["verdict"] == "ok"
        assert 0 <= result["weeks_remaining_low"] <= result["weeks_remaining"]
        assert result["weeks_remaining"] <= result["weeks_remaining_high"]


# --------------------------------------------------------------------------
# The lookup
# --------------------------------------------------------------------------

def test_equipment_mix_shifts_across_the_phase_sequence(rentals: pd.DataFrame):
    """The signal the classifier lives on has to exist in the data.

    Excavators front-load a project and compactors finish it. If that ordering
    is not in the rentals, the phase model is fitting noise and the product's
    central claim is unsupported.
    """
    mix = phase.equipment_mix_by_phase(rentals)
    assert mix.loc["clearing", "Excavator"] > mix.loc["grading", "Excavator"] * 2
    assert mix.loc["grading", "Compactor"] > mix.loc["clearing", "Compactor"] * 2


def test_requirements_scale_with_site_size(rentals: pd.DataFrame,
                                           site_phases: pd.DataFrame):
    typical = phase.typical_machines_per_phase(rentals, site_phases)
    small = allocate.requirements_for("foundation", typical, site_scale=0.5)
    large = allocate.requirements_for("foundation", typical, site_scale=2.0)
    assert sum(large.values()) > sum(small.values())


# --------------------------------------------------------------------------
# Allocation
# --------------------------------------------------------------------------

def test_a_machine_comes_free_at_the_earlier_of_the_two_clocks(
        rentals: pd.DataFrame):
    """freed_at = min(phase end, contract expiry), and it says which bit."""
    now = clock_adapter.now_date()
    phase_end = {config.SITES[0].site_id: now + timedelta(days=5)}
    ledger = allocate.build_ledger(rentals, phase_end, now)
    assert ledger

    for machine in ledger:
        end = phase_end.get(machine.site_id)
        expected = min(end, machine.check_out) if end else machine.check_out
        assert machine.freed_at == expected
        if end and end < machine.check_out:
            assert machine.freed_because == "phase_ends"
        else:
            assert machine.freed_because == "contract_expires"


def test_only_machines_on_rent_today_are_in_the_ledger(rentals: pd.DataFrame):
    now = clock_adapter.now_date()
    for machine in allocate.build_ledger(rentals, {}, now):
        assert machine.check_in <= now <= machine.check_out


def test_no_machine_is_promised_to_two_sites():
    """Double-booking a donor is the failure mode that discredits the board."""
    result = service.get_allocation()
    assigned = [
        move["equipment_id"]
        for rec in result["recommendations"]
        for move in rec["redeployments"]
    ]
    assert len(assigned) == len(set(assigned)), "a machine was moved twice"


def test_every_recommendation_prices_both_options():
    """The decision has to be checkable, not merely trusted."""
    result = service.get_allocation()
    assert result["recommendations"]

    for rec in result["recommendations"]:
        assert rec["decision"] in {"redeploy", "rent", "mixed"}
        assert rec["redeploy_count"] + rec["rent_count"] == rec["quantity"]
        assert rec["all_rented_inr"] > 0
        # Saving is measured against renting the whole shortfall.
        assert rec["saving_inr"] == pytest.approx(
            rec["all_rented_inr"] - rec["total_inr"], abs=2
        )
        for move in rec["redeployments"]:
            assert move["from_site"] != rec["site_id"]
            assert move["distance_km"] > 0


def test_a_redeployment_is_only_chosen_when_it_is_cheaper():
    """The rule is arithmetic, not a tuned threshold."""
    result = service.get_allocation()
    for rec in result["recommendations"]:
        unit_rent = rec["all_rented_inr"] / rec["quantity"]
        for move in rec["redeployments"]:
            assert move["total_inr"] < unit_rent


def test_surplus_machines_are_paid_for_past_their_need():
    """The cheaper half of the story, and it needs no prediction of demand."""
    result = service.get_allocation()
    for row in result["surplus"]:
        assert row["surplus_days"] > 0
        assert row["idle_cost_inr"] > 0


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_the_whole_pipeline_is_deterministic():
    """Same seed, same clock, same board. A demo that moves is a demo that
    cannot be rehearsed."""
    service.reset()
    first = service.get_allocation()
    service.reset()
    second = service.get_allocation()

    assert first["summary"] == second["summary"]
    assert (
        [r["rationale"] for r in first["recommendations"]]
        == [r["rationale"] for r in second["recommendations"]]
    )
