"""Export the existing MongoDB Atlas database collections to local JSON files."""

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

EXPORT_FILES = {
    COLLECTIONS["equipment"]: "equipment_seed.json",
    COLLECTIONS["operators"]: "operators_seed.json",
    COLLECTIONS["assignments"]: "assignments_seed.json",
    COLLECTIONS["usage_logs"]: "usage_logs_seed.json",
}


def _to_extended_json(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return {"$oid": str(value)}
    if isinstance(value, datetime):
        return {"$date": value.isoformat().replace("+00:00", "Z")}
    if isinstance(value, list):
        return [_to_extended_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_extended_json(item) for key, item in value.items()}
    return value


def export_data() -> dict[str, int]:
    """Export every configured collection to a seed JSON file."""
    db = get_database()
    counts: dict[str, int] = {}

    for collection_name, file_name in EXPORT_FILES.items():
        documents = list(db[collection_name].find().sort("_id", 1))
        serializable_documents = [_to_extended_json(document) for document in documents]

        output_path = BASE_DIR / file_name
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(serializable_documents, handle, indent=2)
            handle.write("\n")

        counts[collection_name] = len(documents)

    return counts


if __name__ == "__main__":
    result = export_data()
    print(f"Export complete. Document counts: {result}")

