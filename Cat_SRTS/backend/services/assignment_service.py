"""Assignment data operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from database.database import get_database


COLLECTION_NAME = "assignments"
REQUIRED_FIELDS = ("assignmentId", "equipmentId", "operatorId", "siteName", "checkOutTime", "status")
ALLOWED_FIELDS = {
    "assignmentId",
    "equipmentId",
    "operatorId",
    "siteName",
    "checkOutTime",
    "checkInTime",
    "status",
}


class AssignmentValidationError(ValueError):
    """Raised when assignment input fails validation."""


class AssignmentDuplicateError(ValueError):
    """Raised when an assignmentId already exists."""


class AssignmentReferenceError(ValueError):
    """Raised when equipmentId or operatorId references are invalid."""


def _database():
    return get_database()


def _collection():
    return _database()[COLLECTION_NAME]


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


def _parse_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AssignmentValidationError(f"{field_name} must be a valid ISO datetime.") from exc
    raise AssignmentValidationError(f"{field_name} must be a valid ISO datetime.")


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document = {key: value for key, value in payload.items() if key in ALLOWED_FIELDS}
    if "checkOutTime" in document:
        document["checkOutTime"] = _parse_datetime(document["checkOutTime"], "checkOutTime")
    if "checkInTime" in document:
        document["checkInTime"] = _parse_datetime(document["checkInTime"], "checkInTime")
    return document


def _validate_references(equipment_id: str | None, operator_id: str | None) -> None:
    db = _database()
    if equipment_id and db["equipment"].count_documents({"equipmentId": equipment_id}, limit=1) == 0:
        raise AssignmentReferenceError("Invalid equipmentId.")
    if operator_id and db["operators"].count_documents({"operatorId": operator_id}, limit=1) == 0:
        raise AssignmentReferenceError("Invalid operatorId.")


def validate_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for creating an assignment."""
    missing_fields = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing_fields:
        raise AssignmentValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    document = _clean_payload(payload)
    _validate_references(document.get("equipmentId"), document.get("operatorId"))
    document.setdefault("checkInTime", None)

    now = datetime.utcnow()
    document["createdAt"] = now
    document["updatedAt"] = now
    return document


def validate_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for updating an assignment."""
    update_data = _clean_payload(payload)
    update_data.pop("assignmentId", None)

    if not update_data:
        raise AssignmentValidationError("No valid assignment fields provided for update.")

    _validate_references(update_data.get("equipmentId"), update_data.get("operatorId"))
    update_data["updatedAt"] = datetime.utcnow()
    return update_data


def get_all_assignments() -> list[dict[str, Any]]:
    """Return every assignment document."""
    documents = _collection().find().sort("assignmentId", 1)
    return [serialize_document(document) for document in documents]


def get_assignment_by_id(assignment_id: str) -> dict[str, Any] | None:
    """Return a single assignment document by assignmentId."""
    return serialize_document(_collection().find_one({"assignmentId": assignment_id}))


def create_assignment(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new assignment document."""
    document = validate_create_payload(payload)

    try:
        _collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise AssignmentDuplicateError("assignmentId already exists.") from exc

    return get_assignment_by_id(document["assignmentId"])


def update_assignment(assignment_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing assignment document."""
    update_data = validate_update_payload(payload)
    result = _collection().find_one_and_update(
        {"assignmentId": assignment_id},
        {"$set": update_data},
        return_document=True,
    )
    return serialize_document(result)


def delete_assignment(assignment_id: str) -> bool:
    """Delete an assignment document by assignmentId."""
    result = _collection().delete_one({"assignmentId": assignment_id})
    return result.deleted_count == 1
