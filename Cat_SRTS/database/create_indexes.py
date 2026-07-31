"""Create indexes for all CAT_SRTS MongoDB collections."""

from __future__ import annotations

from pymongo import ASCENDING

try:
    from .config import COLLECTIONS
    from .database import get_database
except ImportError:
    from config import COLLECTIONS
    from database import get_database


INDEX_DEFINITIONS = {
    COLLECTIONS["equipment"]: [
        ([("equipmentId", ASCENDING)], {"name": "equipmentId_unique", "unique": True}),
        ([("currentStatus", ASCENDING)], {"name": "currentStatus_idx"}),
        ([("ownershipStatus", ASCENDING)], {"name": "ownershipStatus_idx"}),
    ],
    COLLECTIONS["operators"]: [
        ([("operatorId", ASCENDING)], {"name": "operatorId_unique", "unique": True}),
        ([("assignedEquipmentId", ASCENDING)], {"name": "assignedEquipmentId_idx"}),
    ],
    COLLECTIONS["assignments"]: [
        ([("assignmentId", ASCENDING)], {"name": "assignmentId_unique", "unique": True}),
        ([("equipmentId", ASCENDING)], {"name": "assignment_equipmentId_idx"}),
        ([("operatorId", ASCENDING)], {"name": "assignment_operatorId_idx"}),
        ([("status", ASCENDING)], {"name": "assignment_status_idx"}),
    ],
    COLLECTIONS["usage_logs"]: [
        ([("equipmentId", ASCENDING)], {"name": "usage_equipmentId_idx"}),
        ([("operatorId", ASCENDING)], {"name": "usage_operatorId_idx"}),
        ([("usageDate", ASCENDING)], {"name": "usageDate_idx"}),
    ],
}


def create_indexes() -> None:
    """Create all required indexes if they do not already exist."""
    db = get_database()
    for collection_name, definitions in INDEX_DEFINITIONS.items():
        collection = db[collection_name]
        for keys, options in definitions:
            collection.create_index(keys, **options)


if __name__ == "__main__":
    create_indexes()
    print("MongoDB indexes created successfully.")

