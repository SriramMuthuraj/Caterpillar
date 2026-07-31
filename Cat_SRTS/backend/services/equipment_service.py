"""Equipment data operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from database.database import get_database


COLLECTION_NAME = "equipment"
REQUIRED_FIELDS = ("equipmentId", "equipmentName", "category", "ownershipStatus", "currentStatus")
ALLOWED_FIELDS = {
    "equipmentId",
    "equipmentName",
    "category",
    "manufacturer",
    "horsePower",
    "lastUsedDate",
    "expectedReturnDate",
    "ownershipStatus",
    "currentStatus",
}


class EquipmentValidationError(ValueError):
    """Raised when equipment input fails validation."""


class EquipmentDuplicateError(ValueError):
    """Raised when an equipmentId already exists."""


def _collection():
    return get_database()[COLLECTION_NAME]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a MongoDB document into JSON-safe data."""
    if document is None:
        return None
    return {key: _serialize_value(value) for key, value in document.items()}


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document = {key: value for key, value in payload.items() if key in ALLOWED_FIELDS}
    for field in ("lastUsedDate", "expectedReturnDate"):
        if field in document and isinstance(document[field], str):
            document[field] = datetime.fromisoformat(document[field].replace("Z", "+00:00"))
    return document


def validate_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for creating equipment."""
    missing_fields = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing_fields:
        raise EquipmentValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    document = _clean_payload(payload)
    now = datetime.utcnow()
    document["createdAt"] = now
    document["updatedAt"] = now
    return document


def validate_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for updating equipment."""
    update_data = _clean_payload(payload)
    update_data.pop("equipmentId", None)

    if not update_data:
        raise EquipmentValidationError("No valid equipment fields provided for update.")

    update_data["updatedAt"] = datetime.utcnow()
    return update_data


def get_all_equipment() -> list[dict[str, Any]]:
    """Return every equipment document."""
    documents = _collection().find().sort("equipmentId", 1)
    return [serialize_document(document) for document in documents]


def get_equipment_by_id(equipment_id: str) -> dict[str, Any] | None:
    """Return a single equipment document by equipmentId."""
    return serialize_document(_collection().find_one({"equipmentId": equipment_id}))


def create_equipment(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new equipment document."""
    document = validate_create_payload(payload)

    try:
        _collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise EquipmentDuplicateError("equipmentId already exists.") from exc

    return get_equipment_by_id(document["equipmentId"])


def update_equipment(equipment_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing equipment document."""
    update_data = validate_update_payload(payload)
    result = _collection().find_one_and_update(
        {"equipmentId": equipment_id},
        {"$set": update_data},
        return_document=True,
    )
    return serialize_document(result)


def delete_equipment(equipment_id: str) -> bool:
    """Delete an equipment document by equipmentId."""
    result = _collection().delete_one({"equipmentId": equipment_id})
    return result.deleted_count == 1
