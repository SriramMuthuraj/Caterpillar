"""Operator data operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from database.database import get_database


COLLECTION_NAME = "operators"
REQUIRED_FIELDS = ("operatorId", "operatorName")
ALLOWED_FIELDS = {
    "operatorId",
    "operatorName",
    "licenseNumber",
    "phoneNumber",
    "assignedEquipment",
    "assignedEquipmentId",
}


class OperatorValidationError(ValueError):
    """Raised when operator input fails validation."""


class OperatorDuplicateError(ValueError):
    """Raised when an operatorId already exists."""


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
    if "assignedEquipment" in document and "assignedEquipmentId" not in document:
        document["assignedEquipmentId"] = document.pop("assignedEquipment")
    else:
        document.pop("assignedEquipment", None)
    return document


def validate_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for creating an operator."""
    missing_fields = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing_fields:
        raise OperatorValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    document = _clean_payload(payload)
    document.setdefault("licenseNumber", f"LIC-{document['operatorId']}")
    document.setdefault("phoneNumber", "Not Provided")
    document.setdefault("assignedEquipmentId", None)

    now = datetime.utcnow()
    document["createdAt"] = now
    document["updatedAt"] = now
    return document


def validate_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for updating an operator."""
    update_data = _clean_payload(payload)
    update_data.pop("operatorId", None)

    if not update_data:
        raise OperatorValidationError("No valid operator fields provided for update.")

    update_data["updatedAt"] = datetime.utcnow()
    return update_data


def get_all_operators() -> list[dict[str, Any]]:
    """Return every operator document."""
    documents = _collection().find().sort("operatorId", 1)
    return [serialize_document(document) for document in documents]


def get_operator_by_id(operator_id: str) -> dict[str, Any] | None:
    """Return a single operator document by operatorId."""
    return serialize_document(_collection().find_one({"operatorId": operator_id}))


def create_operator(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new operator document."""
    document = validate_create_payload(payload)

    try:
        _collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise OperatorDuplicateError("operatorId already exists.") from exc

    return get_operator_by_id(document["operatorId"])


def update_operator(operator_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing operator document."""
    update_data = validate_update_payload(payload)
    result = _collection().find_one_and_update(
        {"operatorId": operator_id},
        {"$set": update_data},
        return_document=True,
    )
    return serialize_document(result)


def delete_operator(operator_id: str) -> bool:
    """Delete an operator document by operatorId."""
    result = _collection().delete_one({"operatorId": operator_id})
    return result.deleted_count == 1

