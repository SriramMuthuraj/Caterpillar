"""End-to-end checks against the assembled application.

Slow — building the app warms the whole forecast bundle — so this is one module
with one shared client rather than a fixture per test.
"""

from __future__ import annotations

import os

import pytest

# Force the offline store before anything imports the Flask app: the point of
# these tests is that the product works with no Atlas, no network, no password.
os.environ["FORCE_MEMORY_DB"] = "true"

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    from backend.main import app

    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Everything is served from one port
# --------------------------------------------------------------------------

FASTAPI_ROUTES = [
    "/api/health",
    "/api/phase/timeline",
    "/api/phase/model",
    "/api/phase/S006",
    "/api/allocation",
    "/api/forecast",
    "/api/anomalies/summary",
    "/api/anomalies?limit=5",
]

FLASK_ROUTES = [
    "/api/health/database",
    "/api/dashboard",
    "/api/equipment",
    "/api/operators",
    "/api/assignments",
    "/api/usage",
    "/api/alerts",
]


@pytest.mark.parametrize("route", FASTAPI_ROUTES)
def test_fastapi_routes_answer(client, route):
    assert client.get(route).status_code == 200


@pytest.mark.parametrize("route", FLASK_ROUTES)
def test_mounted_flask_routes_answer(client, route):
    """The Flask app is reachable through the FastAPI host, on the same port."""
    assert client.get(route).status_code == 200


def test_the_database_falls_back_instead_of_returning_500(client):
    """With no Atlas the API must still serve a full fleet, not error.

    A missing password used to make every /api route 500 while the app itself
    reported healthy — the worst way to find out, five minutes before a demo.
    """
    health = client.get("/api/health/database").json()
    assert health["status"] == "connected"
    assert health["backend"] == "memory"

    equipment = client.get("/api/equipment").json()
    assert len(equipment) > 100


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------

def test_the_dashboard_and_the_forecast_agree_on_the_fleet(client):
    """One universe: the same machines, counted two different ways."""
    dashboard = client.get("/api/dashboard").json()
    equipment = client.get("/api/equipment").json()

    on_hire = [e for e in equipment if e["currentStatus"] in ("Working", "Idle")]
    allocation = client.get("/api/allocation").json()

    assert dashboard["totalEquipment"] == len(equipment)
    assert dashboard["activeEquipment"] + dashboard["inactiveEquipment"] == \
        len(equipment)
    # Every surplus machine the allocator wants to move is a machine the
    # operational store knows is on hire.
    shown = {e["equipmentId"] for e in on_hire}
    for machine in allocation["surplus"]:
        assert machine["equipment_id"] in shown


def test_the_clock_is_the_demo_clock_everywhere(client):
    """Three modules, three clocks, one answer."""
    health = client.get("/api/health").json()
    timeline = client.get("/api/phase/timeline").json()
    anomalies = client.get("/api/anomalies/summary").json()

    assert health["clock"]["source"] == "demo_constant"
    assert timeline["as_of"] == health["clock"]["now"]
    assert anomalies["as_of"] == health["clock"]["now"]


def test_return_due_alerts_are_a_shortlist_not_the_whole_fleet(client):
    """With the wall clock every rental looks expired — 296 useless alerts."""
    alerts = client.get("/api/alerts").json()
    equipment = client.get("/api/equipment").json()

    return_due = [a for a in alerts if a["type"] == "RETURN_DUE"]
    assert 0 < len(return_due) < len(equipment) * 0.1


def test_findings_carry_the_phase_the_rules_cannot_see(client):
    """Peer groups are type/site/operator; none of them knows the project stage."""
    findings = client.get("/api/anomalies?limit=100").json()["findings"]
    assert findings

    with_phase = [f for f in findings if f["phase"]]
    assert len(with_phase) > len(findings) * 0.8

    valid = set(client.get("/api/phase/timeline").json()["phases"])
    assert {f["phase"] for f in with_phase} <= valid


def test_the_detector_finds_the_defects_that_were_planted(client):
    summary = client.get("/api/anomalies/summary").json()
    rules = summary["by_rule"]

    # Deliberately injected by the generator; see config.py's defect block.
    assert rules.get("impossible_hours", 0) > 100
    assert rules.get("rental_days_mismatch", 0) > 100
    assert rules.get("unassigned_equipment", 0) > 0
    assert rules.get("no_accountability", 0) > 0

    # And one it must NOT find: the generator never double-books a machine.
    assert rules.get("booking_conflict", 0) == 0


def test_a_refused_prediction_is_a_200_not_an_error(client):
    """Declining to predict is an answer, not a failure."""
    timeline = client.get("/api/phase/timeline").json()
    verdicts = {site["verdict"] for site in timeline["sites"]}
    assert verdicts <= {"ok", "insufficient_data"}

    model = client.get("/api/phase/model").json()
    assert "demobilisation" in model["phase_end"]["phases_refused"]


def test_every_recommendation_prices_both_options(client):
    """The choice has to be checkable, not merely assertable."""
    for rec in client.get("/api/allocation").json()["recommendations"]:
        assert rec["quantity"] == rec["redeploy_count"] + rec["rent_count"]
        assert len(rec["redeployments"]) == rec["redeploy_count"]
        assert rec["all_rented_inr"] > 0
        assert rec["total_inr"] <= rec["all_rented_inr"]
        assert rec["saving_inr"] == pytest.approx(
            rec["all_rented_inr"] - rec["total_inr"], abs=1
        )


def test_no_machine_is_promised_to_two_sites(client):
    """Donors are consumed as assigned, across the whole board."""
    assigned = [
        option["equipment_id"]
        for rec in client.get("/api/allocation").json()["recommendations"]
        for option in rec["redeployments"]
    ]
    assert len(assigned) == len(set(assigned))


# --------------------------------------------------------------------------
# Devices
# --------------------------------------------------------------------------

def test_qr_generates_and_decodes_without_a_camera_or_a_window(client):
    png = client.get("/api/equipment/EQX2001/qr")
    assert png.status_code == 200
    assert png.content[:4] == b"\x89PNG"

    scanned = client.post(
        "/api/scan", files={"image": ("qr.png", png.content, "image/png")}
    )
    assert scanned.json() == {"found": True, "equipment_id": "EQX2001"}


def test_the_qr_route_does_not_shadow_the_flask_equipment_route(client):
    """/api/equipment/{id}/qr is FastAPI's; /api/equipment/{id} is Flask's."""
    detail = client.get("/api/equipment/EQX2001")
    assert detail.status_code == 200
    assert detail.json()["equipmentId"] == "EQX2001"


def test_alerts_dry_run_by_default(client):
    """The demo runs offline; sending must be opt-in, not opt-out."""
    result = client.post("/api/alerts/send", json={
        "to": "ops@example.com", "subject": "test", "body": "<b>hi</b>",
    }).json()
    assert result["sent"] is False
    assert result["reason"] == "dry_run"
