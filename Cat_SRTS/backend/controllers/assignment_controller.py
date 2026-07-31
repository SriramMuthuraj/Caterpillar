"""Assignment request handlers."""

from __future__ import annotations

from flask import jsonify, request

from services.assignment_service import (
    AssignmentDuplicateError,
    AssignmentReferenceError,
    AssignmentValidationError,
    create_assignment,
    delete_assignment,
    get_all_assignments,
    get_assignment_by_id,
    update_assignment,
)


def list_assignments():
    """Handle GET /api/assignments."""
    return jsonify(get_all_assignments())


def get_assignment(assignment_id: str):
    """Handle GET /api/assignments/<assignmentId>."""
    assignment = get_assignment_by_id(assignment_id)
    if assignment is None:
        return jsonify({"error": "Assignment not found."}), 404
    return jsonify(assignment)


def add_assignment():
    """Handle POST /api/assignments."""
    payload = request.get_json(silent=True) or {}

    try:
        assignment = create_assignment(payload)
    except AssignmentValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except AssignmentReferenceError as exc:
        return jsonify({"error": str(exc)}), 400
    except AssignmentDuplicateError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify(assignment), 201


def edit_assignment(assignment_id: str):
    """Handle PUT /api/assignments/<assignmentId>."""
    payload = request.get_json(silent=True) or {}

    try:
        assignment = update_assignment(assignment_id, payload)
    except AssignmentValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except AssignmentReferenceError as exc:
        return jsonify({"error": str(exc)}), 400

    if assignment is None:
        return jsonify({"error": "Assignment not found."}), 404

    return jsonify(assignment)


def remove_assignment(assignment_id: str):
    """Handle DELETE /api/assignments/<assignmentId>."""
    deleted = delete_assignment(assignment_id)
    if not deleted:
        return jsonify({"error": "Assignment not found."}), 404

    return jsonify({"status": "success", "message": "Assignment deleted successfully."})

