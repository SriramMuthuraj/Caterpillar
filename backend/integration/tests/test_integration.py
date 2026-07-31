"""Tests for the seams between the four modules.

Each module has its own tests. These cover the joins — the places where two
people's assumptions meet and where a mistake is silent rather than loud.
"""

from __future__ import annotations

import ast
import json
import pathlib

import joblib
import pandas as pd
import pytest

from backend.forecast import (
    artifacts, clock_adapter, config, history as history_mod, phase as phase_mod,
)
from backend.integration import dataset


@pytest.fixture(scope="module")
def now():
    return clock_adapter.now_date()


@pytest.fixture(scope="module")
def rentals():
    return dataset.history()


@pytest.fixture(scope="module")
def snapshot(now):
    return dataset.live_snapshot(now)


# --------------------------------------------------------------------------
# One universe
# --------------------------------------------------------------------------

def test_every_machine_in_the_snapshot_exists_in_the_history(snapshot, rentals):
    """The dashboard must not know about machines the models have never seen.

    This is the whole reason the operational store is *derived*. Seed it by hand
    and the dashboard says "20 machines" while the forecast page says "296
    active" — two fleets, one screen apart.
    """
    known = set(rentals["equipment_id"])
    shown = {doc["equipmentId"] for doc in snapshot["equipment"]}
    assert shown <= known, f"invented machines: {sorted(shown - known)[:5]}"


def test_on_hire_count_equals_rentals_active_right_now(snapshot, rentals, now):
    active = dataset.active_rentals(now)
    on_hire = [d for d in snapshot["equipment"]
               if d["currentStatus"] in ("Working", "Idle")]
    assert len(on_hire) == len(active)


def test_assignments_and_operators_reference_real_equipment(snapshot):
    equipment_ids = {d["equipmentId"] for d in snapshot["equipment"]}

    for assignment in snapshot["assignments"]:
        assert assignment["equipmentId"] in equipment_ids

    for operator in snapshot["operators"]:
        assert operator["assignedEquipmentId"] in equipment_ids


def test_no_machine_is_on_hire_twice(snapshot):
    on_hire = [d["equipmentId"] for d in snapshot["equipment"]
               if d["currentStatus"] in ("Working", "Idle")]
    assert len(on_hire) == len(set(on_hire))


def test_sites_are_named_not_free_text(snapshot):
    """siteName must resolve to a real site, not an arbitrary string."""
    real = {site.name for site in config.SITES}
    for assignment in snapshot["assignments"]:
        assert assignment["siteName"] in real or \
            assignment["siteName"] == "Unassigned"


# --------------------------------------------------------------------------
# The naming inversion — the most likely silent bug in the whole integration
# --------------------------------------------------------------------------

def test_check_out_time_is_the_start_not_the_expiry(snapshot, rentals, now):
    """Cat_SRTS's ``checkOutTime`` is the machine leaving the yard.

    Ours is the contract expiring. Same word, opposite ends of the rental. Get
    this backwards and every assignment reads as having started on the day it
    was due to finish — plausible on screen, wrong in every downstream sum.
    """
    active = dataset.active_rentals(now).set_index("equipment_id")

    for assignment in snapshot["assignments"][:50]:
        rental = active.loc[assignment["equipmentId"]]
        started = pd.Timestamp(assignment["checkOutTime"]["$date"])

        assert started == pd.Timestamp(rental["check_in"]), (
            "checkOutTime must be the rental start (our check_in)"
        )
        assert started <= pd.Timestamp(now), "a live rental cannot start later"


def test_expected_return_date_is_the_contract_expiry(snapshot, rentals, now):
    active = dataset.active_rentals(now).set_index("equipment_id")

    for doc in snapshot["equipment"]:
        if doc["currentStatus"] not in ("Working", "Idle"):
            continue
        rental = active.loc[doc["equipmentId"]]
        assert pd.Timestamp(doc["expectedReturnDate"]["$date"]) == \
            pd.Timestamp(rental["check_out"])


def test_a_live_assignment_has_not_been_checked_back_in(snapshot):
    for assignment in snapshot["assignments"]:
        assert assignment["checkInTime"] is None


def test_returned_machines_have_no_expected_return_date(snapshot):
    """Otherwise the RETURN_DUE rule flags every machine already back."""
    for doc in snapshot["equipment"]:
        if doc["currentStatus"] == "Returned":
            assert doc["expectedReturnDate"] is None


# --------------------------------------------------------------------------
# The anomaly detector's view
# --------------------------------------------------------------------------

def test_anomaly_view_has_exactly_the_columns_the_detector_reads():
    view = dataset.anomaly_view()
    assert list(view.columns) == dataset.ANOMALY_COLUMNS


def test_anomaly_view_loses_no_rows(rentals):
    """A rename, not a filter. Cleaning rows here would hide real findings."""
    assert len(dataset.anomaly_view()) == len(rentals)


def test_dates_are_the_format_the_detector_can_parse():
    """``main.py`` parses with an unguarded strptime — any other format aborts."""
    view = dataset.anomaly_view()
    for column in ("Check_In_Date", "Check_Out_Date"):
        parsed = pd.to_datetime(view[column], format="%Y-%m-%d", errors="coerce")
        assert parsed.notna().all()


def test_missing_values_are_the_NULL_sentinel_not_nan():
    """NaN would be read as 0.0 and silently trip the zero_activity rule."""
    view = dataset.anomaly_view()
    assert not view.isna().any().any()
    assert (view["Site_ID"] == "NULL").sum() > 0
    assert (view["Last_Operator_ID"] == "NULL").sum() > 0


def test_the_two_paperwork_rules_have_something_to_find(rentals):
    """Without injected gaps, unassigned_equipment and no_accountability are dead."""
    assert rentals["site_id"].isna().sum() > 0
    assert rentals["operator_id"].isna().sum() > 0


def test_site_less_rows_never_reach_the_phase_panel(rentals, now):
    """A rental with no site cannot belong to a site-week."""
    site_phases = history_mod.site_phase_windows(now=now)
    panel = phase_mod.build_panel(rentals, site_phases, now=now)
    assert panel["site_id"].notna().all()


# --------------------------------------------------------------------------
# Model artifacts
# --------------------------------------------------------------------------

def test_artifacts_round_trip_to_identical_predictions(rentals, now):
    fingerprint = history_mod.dgp_fingerprint()
    bundle = artifacts.load_classifier(fingerprint, phase_mod.CLASSIFIER_FEATURES)
    if bundle is None:
        pytest.skip("no classifier artifact on disk; run scripts/train_models.py")

    site_phases = history_mod.site_phase_windows(now=now)
    panel = phase_mod.build_panel(rentals, site_phases, now=now)
    usable = panel.dropna(subset=phase_mod.CLASSIFIER_FEATURES)
    features = usable[phase_mod.CLASSIFIER_FEATURES].to_numpy(dtype=float)

    restored = phase_mod.PhaseClassifier.restore(bundle)
    fresh = phase_mod.PhaseClassifier().fit(panel)

    assert (restored.model.predict(features) == fresh.model.predict(features)).all()


def test_a_stale_fingerprint_is_rejected_rather_than_trusted():
    """The whole point: a model must never outlive the data it was fitted to."""
    assert artifacts.load_classifier(
        "0000000000", phase_mod.CLASSIFIER_FEATURES
    ) is None
    assert artifacts.load_phase_end(
        "0000000000", phase_mod.DURATION_FEATURES
    ) is None


def test_a_changed_feature_set_is_rejected():
    fingerprint = history_mod.dgp_fingerprint()
    assert artifacts.load_phase_end(
        fingerprint, phase_mod.DURATION_FEATURES + ["invented_feature"]
    ) is None


def test_phase_end_without_its_conformal_pad_is_rejected(tmp_path):
    """Three quantile regressors alone are not a complete interval model.

    Without ``interval_pad`` the P10-P90 band drops from 0.80 coverage to about
    0.40 and nothing visibly breaks, which is exactly why the loader has to
    refuse rather than shrug.
    """
    path = artifacts.phase_end_path()
    if not path.exists():
        pytest.skip("no phase_end artifact on disk")

    crippled = tmp_path / "crippled.pkl"
    bundle = joblib.load(path)
    bundle["interval_pad"] = None
    joblib.dump(bundle, crippled)

    assert artifacts.load_phase_end(
        history_mod.dgp_fingerprint(), phase_mod.DURATION_FEATURES, path=crippled
    ) is None


# --------------------------------------------------------------------------
# Invariants
# --------------------------------------------------------------------------

INTEGRATION_DIR = pathlib.Path(__file__).resolve().parents[1]


def test_no_wall_clock_call_anywhere_in_the_integration_package():
    """Every date in the dataset is historical.

    A stray ``datetime.now()`` makes nothing active: the snapshot empties, the
    allocation board goes blank, and the alerts page fills with false overdues.
    ``clock_adapter`` is the only source of "now".
    """
    offenders = []

    for path in INTEGRATION_DIR.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("now", "utcnow", "today"):
                owner = getattr(func.value, "id", None) or \
                    getattr(getattr(func.value, "attr", None), "__str__", lambda: "")()
                if owner in ("datetime", "date"):
                    offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, f"wall-clock calls: {offenders}"


def test_the_snapshot_is_deterministic(now):
    """Same clock, same seed, same documents — including the generated _ids."""
    first = json.dumps(dataset.live_snapshot(now), sort_keys=True, default=str)
    second = json.dumps(dataset.live_snapshot(now), sort_keys=True, default=str)
    assert first == second


def test_forecast_config_is_not_shadowed_by_cat_srts():
    """Cat_SRTS puts its own ``config`` package on sys.path at import time.

    ``backend.forecast`` uses relative imports so it is immune, but this asserts
    the property rather than assuming it — a future absolute import would
    silently pick up Flask settings instead of the phase model's constants.
    """
    from backend.forecast import config as forecast_config

    assert hasattr(forecast_config, "PHASE_NAMES")
    assert hasattr(forecast_config, "DEMO_NOW")
    assert forecast_config.__name__ == "backend.forecast.config"
