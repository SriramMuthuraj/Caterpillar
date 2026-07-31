"""Seed MongoDB collections from exported local JSON files without duplicates."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

try:
    from .config import COLLECTIONS
    from .database import get_database
except ImportError:
    from config import COLLECTIONS
    from database import get_database


BASE_DIR = Path(__file__).resolve().parent

SEED_FILES = {
    COLLECTIONS["equipment"]: ("equipment_seed.json", "equipmentId"),
    COLLECTIONS["operators"]: ("operators_seed.json", "operatorId"),
    COLLECTIONS["assignments"]: ("assignments_seed.json", "assignmentId"),
    COLLECTIONS["usage_logs"]: ("usage_logs_seed.json", "usageId"),
}


def _from_extended_json(value: Any) -> Any:
    if isinstance(value, list):
        return [_from_extended_json(item) for item in value]
    if isinstance(value, dict):
        if set(value.keys()) == {"$oid"}:
            return ObjectId(value["$oid"])
        if set(value.keys()) == {"$date"}:
            raw_date = value["$date"]
            if isinstance(raw_date, dict) and "$numberLong" in raw_date:
                return datetime.fromtimestamp(int(raw_date["$numberLong"]) / 1000)
            return datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        return {key: _from_extended_json(item) for key, item in value.items()}
    return value


def load_seed_documents(file_name: str) -> list[dict[str, Any]]:
    """Load a seed file and convert MongoDB Extended JSON values."""
    file_path = BASE_DIR / file_name
    with file_path.open("r", encoding="utf-8") as handle:
        return _from_extended_json(json.load(handle))


def seed_database() -> dict[str, int]:
    """Insert seed documents, skipping records whose primary identifier exists."""
    db = get_database()
    inserted_counts: dict[str, int] = {}

    for collection_name, (file_name, primary_field) in SEED_FILES.items():
        collection = db[collection_name]
        inserted = 0

        for document in load_seed_documents(file_name):
            if collection.count_documents({primary_field: document[primary_field]}, limit=1):
                continue
            collection.insert_one(document)
            inserted += 1

        inserted_counts[collection_name] = inserted

    return inserted_counts


if __name__ == "__main__":
    result = seed_database()
    print(f"Seed complete. Inserted counts: {result}")

