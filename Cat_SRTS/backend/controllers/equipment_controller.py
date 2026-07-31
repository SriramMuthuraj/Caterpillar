"""Equipment request handlers."""

from __future__ import annotations

from flask import jsonify, request

from services.equipment_service import (
    EquipmentDuplicateError,
    EquipmentValidationError,
    create_equipment,
    delete_equipment,
    get_all_equipment,
    get_equipment_by_id,
    update_equipment,
)


def list_equipment():
    """Handle GET /api/equipment."""
    return jsonify(get_all_equipment())


def get_equipment(equipment_id: str):
    """Handle GET /api/equipment/<equipmentId>."""
    equipment = get_equipment_by_id(equipment_id)
    if equipment is None:
        return jsonify({"error": "Equipment not found."}), 404
    return jsonify(equipment)


def add_equipment():
    """Handle POST /api/equipment."""
    payload = request.get_json(silent=True) or {}

    try:
        equipment = create_equipment(payload)
    except EquipmentValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except EquipmentDuplicateError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify(equipment), 201


def edit_equipment(equipment_id: str):
    """Handle PUT /api/equipment/<equipmentId>."""
    payload = request.get_json(silent=True) or {}

    try:
        equipment = update_equipment(equipment_id, payload)
    except EquipmentValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    if equipment is None:
        return jsonify({"error": "Equipment not found."}), 404

    return jsonify(equipment)


def remove_equipment(equipment_id: str):
    """Handle DELETE /api/equipment/<equipmentId>."""
    deleted = delete_equipment(equipment_id)
    if not deleted:
        return jsonify({"error": "Equipment not found."}), 404

    return jsonify({"status": "success", "message": "Equipment deleted successfully."})

