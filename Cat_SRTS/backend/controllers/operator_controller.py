"""Operator request handlers."""

from __future__ import annotations

from flask import jsonify, request

from services.operator_service import (
    OperatorDuplicateError,
    OperatorValidationError,
    create_operator,
    delete_operator,
    get_all_operators,
    get_operator_by_id,
    update_operator,
)


def list_operators():
    """Handle GET /api/operators."""
    return jsonify(get_all_operators())


def get_operator(operator_id: str):
    """Handle GET /api/operators/<operatorId>."""
    operator = get_operator_by_id(operator_id)
    if operator is None:
        return jsonify({"error": "Operator not found."}), 404
    return jsonify(operator)


def add_operator():
    """Handle POST /api/operators."""
    payload = request.get_json(silent=True) or {}

    try:
        operator = create_operator(payload)
    except OperatorValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except OperatorDuplicateError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify(operator), 201


def edit_operator(operator_id: str):
    """Handle PUT /api/operators/<operatorId>."""
    payload = request.get_json(silent=True) or {}

    try:
        operator = update_operator(operator_id, payload)
    except OperatorValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    if operator is None:
        return jsonify({"error": "Operator not found."}), 404

    return jsonify(operator)


def remove_operator(operator_id: str):
    """Handle DELETE /api/operators/<operatorId>."""
    deleted = delete_operator(operator_id)
    if not deleted:
        return jsonify({"error": "Operator not found."}), 404

    return jsonify({"status": "success", "message": "Operator deleted successfully."})

