"""Usage log data operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from database.database import get_database


COLLECTION_NAME = "usage_logs"
REQUIRED_FIELDS = (
    "equipmentId",
    "operatorId",
    "runtimeHours",
    "fuelUsage",
    "idleHours",
    "location",
    "usageDate",
)
NUMERIC_FIELDS = ("runtimeHours", "fuelUsage", "idleHours")
ALLOWED_FIELDS = {
    "usageId",
    "equipmentId",
    "operatorId",
    "runtimeHours",
    "fuelUsage",
    "idleHours",
    "location",
    "usageDate",
}


class UsageValidationError(ValueError):
    """Raised when usage log input fails validation."""


class UsageReferenceError(ValueError):
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


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise UsageValidationError(f"{field_name} must be a valid ISO datetime.") from exc
    raise UsageValidationError(f"{field_name} must be a valid ISO datetime.")


def _parse_non_negative_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise UsageValidationError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise UsageValidationError(f"{field_name} must be numeric.") from exc
    if number < 0:
        raise UsageValidationError(f"{field_name} must be greater than or equal to 0.")
    return number


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document = {key: value for key, value in payload.items() if key in ALLOWED_FIELDS}
    for field in NUMERIC_FIELDS:
        if field in document:
            document[field] = _parse_non_negative_number(document[field], field)
    if "usageDate" in document:
        document["usageDate"] = _parse_datetime(document["usageDate"], "usageDate")
    return document


def _validate_references(equipment_id: str | None, operator_id: str | None) -> None:
    db = _database()
    if equipment_id and db["equipment"].count_documents({"equipmentId": equipment_id}, limit=1) == 0:
        raise UsageReferenceError("Invalid equipmentId.")
    if operator_id and db["operators"].count_documents({"operatorId": operator_id}, limit=1) == 0:
        raise UsageReferenceError("Invalid operatorId.")


def _log_filter(log_id: str) -> dict[str, Any]:
    try:
        object_id = ObjectId(log_id)
    except InvalidId:
        return {"usageId": log_id}
    return {"$or": [{"_id": object_id}, {"usageId": log_id}]}


def validate_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for creating a usage log."""
    missing_fields = [field for field in REQUIRED_FIELDS if field not in payload or payload[field] in ("", None)]
    if missing_fields:
        raise UsageValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    document = _clean_payload(payload)
    _validate_references(document.get("equipmentId"), document.get("operatorId"))
    document.setdefault("usageId", f"USE-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")
    document["createdAt"] = datetime.utcnow()
    return document


def validate_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize data for updating a usage log."""
    update_data = _clean_payload(payload)
    update_data.pop("usageId", None)

    if not update_data:
        raise UsageValidationError("No valid usage log fields provided for update.")

    _validate_references(update_data.get("equipmentId"), update_data.get("operatorId"))
    return update_data


def get_all_usage_logs() -> list[dict[str, Any]]:
    """Return every usage log document."""
    documents = _collection().find().sort("usageDate", -1)
    return [serialize_document(document) for document in documents]


def get_usage_logs_by_equipment(equipment_id: str) -> list[dict[str, Any]]:
    """Return usage logs for one equipmentId."""
    documents = _collection().find({"equipmentId": equipment_id}).sort("usageDate", -1)
    return [serialize_document(document) for document in documents]


def create_usage_log(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new usage log."""
    document = validate_create_payload(payload)
    result = _collection().insert_one(document)
    return serialize_document(_collection().find_one({"_id": result.inserted_id}))


def update_usage_log(log_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing usage log by usageId or MongoDB _id."""
    update_data = validate_update_payload(payload)
    result = _collection().find_one_and_update(
        _log_filter(log_id),
        {"$set": update_data},
        return_document=True,
    )
    return serialize_document(result)


def delete_usage_log(log_id: str) -> bool:
    """Delete a usage log by usageId or MongoDB _id."""
    result = _collection().delete_one(_log_filter(log_id))
    return result.deleted_count == 1

