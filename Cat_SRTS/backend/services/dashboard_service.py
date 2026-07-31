"""Dashboard data aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from database.database import get_database


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in document.items()}


def get_dashboard_summary() -> dict[str, Any]:
    """Compute dashboard metrics from MongoDB collections."""
    db = get_database()
    equipment = db["equipment"]
    assignments = db["assignments"]
    usage_logs = db["usage_logs"]

    equipment_by_category = {
        item["_id"]: item["count"]
        for item in equipment.aggregate(
            [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        )
    }

    recent_assignments = [
        _serialize_document(document)
        for document in assignments.find().sort("checkOutTime", -1).limit(5)
    ]
    recent_usage_logs = [
        _serialize_document(document)
        for document in usage_logs.find().sort("usageDate", -1).limit(5)
    ]

    return {
        "totalEquipment": equipment.count_documents({}),
        "availableEquipment": equipment.count_documents({"currentStatus": "Available"}),
        "assignedEquipment": equipment.count_documents({"currentStatus": "Assigned"}),
        "activeEquipment": equipment.count_documents({"currentStatus": {"$in": ["Assigned", "Working"]}}),
        "inactiveEquipment": equipment.count_documents({"currentStatus": {"$in": ["Available", "Idle", "Returned"]}}),
        "ownedEquipment": equipment.count_documents({"ownershipStatus": "Owned"}),
        "rentedEquipment": equipment.count_documents({"ownershipStatus": "Rented"}),
        "equipmentByCategory": equipment_by_category,
        "recentAssignments": recent_assignments,
        "recentUsageLogs": recent_usage_logs,
    }

