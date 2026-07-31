"""Usage log request handlers."""

from __future__ import annotations

from flask import jsonify, request

from services.usage_service import (
    UsageReferenceError,
    UsageValidationError,
    create_usage_log,
    delete_usage_log,
    get_all_usage_logs,
    get_usage_logs_by_equipment,
    update_usage_log,
)


def list_usage_logs():
    """Handle GET /api/usage."""
    return jsonify(get_all_usage_logs())


def get_equipment_usage(equipment_id: str):
    """Handle GET /api/usage/<equipmentId>."""
    return jsonify(get_usage_logs_by_equipment(equipment_id))


def add_usage_log():
    """Handle POST /api/usage."""
    payload = request.get_json(silent=True) or {}

    try:
        usage_log = create_usage_log(payload)
    except UsageValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except UsageReferenceError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(usage_log), 201


def edit_usage_log(log_id: str):
    """Handle PUT /api/usage/<logId>."""
    payload = request.get_json(silent=True) or {}

    try:
        usage_log = update_usage_log(log_id, payload)
    except UsageValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except UsageReferenceError as exc:
        return jsonify({"error": str(exc)}), 400

    if usage_log is None:
        return jsonify({"error": "Usage log not found."}), 404

    return jsonify(usage_log)


def remove_usage_log(log_id: str):
    """Handle DELETE /api/usage/<logId>."""
    deleted = delete_usage_log(log_id)
    if not deleted:
        return jsonify({"error": "Usage log not found."}), 404

    return jsonify({"status": "success", "message": "Usage log deleted successfully."})

