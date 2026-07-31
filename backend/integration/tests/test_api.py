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


# --------------------------------------------------------------------------
# Idle ratio by peer group
# --------------------------------------------------------------------------

@pytest.mark.parametrize("group", ["type", "site", "operator"])
def test_idle_ratio_matches_a_direct_average_of_the_findings(client, group):
    """The endpoint is an aggregation, so it must equal the aggregate.

    Computed here the long way round from the raw findings, because the whole
    value of serving this server-side is that nobody re-derives it by hand.
    """
    field = {"type": "type", "site": "site_id", "operator": "operator_id"}[group]
    findings = client.get(
        "/api/anomalies", params={"flagged_only": False, "limit": 5000}
    ).json()["findings"]

    expected: dict[str, list[float]] = {}
    for row in findings:
        if not row["is_valid_row"] or row["utilisation"] is None:
            continue
        if not row[field]:
            continue
        expected.setdefault(row[field], []).append(1.0 - row["utilisation"])

    served = {
        entry["group"]: entry
        for entry in client.get(
            "/api/anomalies/idle-ratio", params={"group": group}
        ).json()["groups"]
    }

    # The page caps at 5,000 rows, so only assert over what we could fetch.
    for key, values in expected.items():
        assert key in served, f"{group} {key} missing from the response"
        if len(values) == served[key]["n"]:
            assert served[key]["idle_ratio"] == pytest.approx(
                sum(values) / len(values), abs=1e-4
            )


def test_idle_ratio_marks_small_groups_rather_than_dropping_them(client):
    """A group too small for the imbalance rules is shown, flagged, not hidden."""
    payload = client.get(
        "/api/anomalies/idle-ratio", params={"group": "operator"}
    ).json()
    floor = payload["min_group_members"]

    assert payload["total_groups"] == len(payload["groups"])
    for entry in payload["groups"]:
        assert entry["compared_by_rules"] == (entry["n"] >= floor)

    assert any(not e["compared_by_rules"] for e in payload["groups"]), (
        "expected at least one operator below the comparison floor"
    )


def test_idle_ratio_is_sorted_worst_first_and_honours_limit(client):
    payload = client.get(
        "/api/anomalies/idle-ratio", params={"group": "operator", "limit": 15}
    ).json()
    ratios = [e["idle_ratio"] for e in payload["groups"]]

    assert len(ratios) == 15
    assert payload["total_groups"] > 15, "the truncation is not being exercised"
    assert ratios == sorted(ratios, reverse=True)


def test_idle_ratio_rejects_an_unknown_grouping(client):
    assert client.get(
        "/api/anomalies/idle-ratio", params={"group": "colour"}
    ).status_code == 422


def test_idle_ratio_excludes_rows_the_integrity_rules_rejected(client):
    """Invalid hours are exactly what must not set the baseline."""
    findings = client.get(
        "/api/anomalies", params={"flagged_only": False, "limit": 5000}
    ).json()["findings"]
    assert any(not row["is_valid_row"] for row in findings), (
        "fixture has no invalid rows, so this test proves nothing"
    )

    counted = client.get(
        "/api/anomalies/idle-ratio", params={"group": "type"}
    ).json()["rows_counted"]
    valid = sum(
        1 for row in findings
        if row["is_valid_row"] and row["utilisation"] is not None and row["type"]
    )
    assert counted >= valid  # findings above are capped at 5,000; served is not


def test_facets_offer_only_values_that_filter_to_something(client):
    facets = client.get("/api/anomalies/facets").json()
    assert facets["sites"] and facets["types"]

    for site in facets["sites"][:3]:
        page = client.get("/api/anomalies", params={
            "site_id": site, "flagged_only": False, "limit": 1,
        }).json()
        assert page["total"] > 0, f"site {site} is offered but matches nothing"


# --------------------------------------------------------------------------
# Equipment search
# --------------------------------------------------------------------------

def test_equipment_search_matches_on_a_substring(client):
    """The search box narrows as you type, so a partial id has to work."""
    exact = client.get("/api/anomalies", params={
        "equipment_id": "EQX2001", "flagged_only": False, "limit": 500,
    }).json()
    assert exact["total"] > 0
    assert {r["equipment_id"] for r in exact["findings"]} == {"EQX2001"}

    partial = client.get("/api/anomalies", params={
        "equipment_id": "eqx200", "flagged_only": False, "limit": 1,
    }).json()
    assert partial["total"] >= exact["total"]


def test_equipment_search_that_matches_nothing_is_empty_not_an_error(client):
    page = client.get("/api/anomalies", params={"equipment_id": "NOPE"}).json()
    assert page["total"] == 0
    assert page["findings"] == []


# --------------------------------------------------------------------------
# Allocation summary
# --------------------------------------------------------------------------

def test_headline_saving_equals_the_sum_of_the_rows_beneath_it(client):
    """Mixed rows save money too.

    Summing only the wholly-redeployed rows made the headline card smaller than
    the column it was summarising — a number a judge can disprove by adding up
    what is on screen.
    """
    payload = client.get("/api/allocation").json()
    rows = payload["recommendations"]

    assert payload["summary"]["saving_inr"] == round(
        sum(r["saving_inr"] for r in rows)
    )
    assert any(r["decision"] == "mixed" and r["saving_inr"] > 0 for r in rows), (
        "no mixed row with a saving, so this test proves nothing"
    )


def test_summary_counts_partition_the_recommendations(client):
    summary = client.get("/api/allocation").json()["summary"]
    assert (
        summary["redeploy"] + summary["mixed"] + summary["rent"]
        == summary["recommendations"]
    )
