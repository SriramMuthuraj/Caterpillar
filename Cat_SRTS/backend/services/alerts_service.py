"""Computed alert data for equipment operations."""

from __future__ import annotations

from typing import Any

from config import clock
from database.database import get_database


IDLE_HOURS_THRESHOLD = 1.5
MAINTENANCE_RUNTIME_THRESHOLD = 500


def _equipment_lookup() -> dict[str, dict[str, Any]]:
    equipment_documents = get_database()["equipment"].find(
        {},
        {"equipmentId": 1, "equipmentName": 1, "expectedReturnDate": 1},
    )
    return {document["equipmentId"]: document for document in equipment_documents}


def _return_due_alerts(equipment_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    # The demo clock, not the wall clock: every expiry date in the dataset is
    # historical, so utcnow() would flag the entire fleet as due back.
    today_end = clock.end_of_today()
    alerts = []

    for equipment in equipment_by_id.values():
        expected_return_date = equipment.get("expectedReturnDate")
        if expected_return_date and expected_return_date <= today_end:
            equipment_id = equipment["equipmentId"]
            equipment_name = equipment.get("equipmentName", "")
            alerts.append(
                {
                    "type": "RETURN_DUE",
                    "equipmentId": equipment_id,
                    "equipmentName": equipment_name,
                    "message": f"{equipment_name} is due for return or overdue.",
                }
            )

    return alerts


def _idle_alerts(equipment_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    usage_logs = get_database()["usage_logs"]
    latest_logs = usage_logs.aggregate(
        [
            {"$sort": {"usageDate": -1}},
            {"$group": {"_id": "$equipmentId", "latestLog": {"$first": "$$ROOT"}}},
        ]
    )

    alerts = []
    for item in latest_logs:
        log = item["latestLog"]
        idle_hours = log.get("idleHours", 0)
        if idle_hours > IDLE_HOURS_THRESHOLD:
            equipment = equipment_by_id.get(log["equipmentId"], {})
            equipment_name = equipment.get("equipmentName", "")
            alerts.append(
                {
                    "type": "EXCESSIVE_IDLE",
                    "equipmentId": log["equipmentId"],
                    "equipmentName": equipment_name,
                    "message": f"{equipment_name} has excessive idle time in the latest usage log.",
                }
            )

    return alerts


def _maintenance_alerts(equipment_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    usage_totals = get_database()["usage_logs"].aggregate(
        [
            {"$group": {"_id": "$equipmentId", "totalRuntimeHours": {"$sum": "$runtimeHours"}}},
            {"$match": {"totalRuntimeHours": {"$gt": MAINTENANCE_RUNTIME_THRESHOLD}}},
        ]
    )

    alerts = []
    for item in usage_totals:
        equipment_id = item["_id"]
        equipment = equipment_by_id.get(equipment_id, {})
        equipment_name = equipment.get("equipmentName", "")
        total_runtime = round(item["totalRuntimeHours"], 2)
        alerts.append(
            {
                "type": "MAINTENANCE_REQUIRED",
                "equipmentId": equipment_id,
                "equipmentName": equipment_name,
                "message": f"{equipment_name} has exceeded {MAINTENANCE_RUNTIME_THRESHOLD} runtime hours ({total_runtime}).",
            }
        )

    return alerts


def get_alerts() -> list[dict[str, str]]:
    """Return computed alerts without persisting alert records."""
    equipment_by_id = _equipment_lookup()
    return (
        _return_due_alerts(equipment_by_id)
        + _idle_alerts(equipment_by_id)
        + _maintenance_alerts(equipment_by_id)
    )

