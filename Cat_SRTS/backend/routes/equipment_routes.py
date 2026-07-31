"""Equipment API routes."""

from flask import Blueprint

from controllers.equipment_controller import (
    add_equipment,
    edit_equipment,
    get_equipment,
    list_equipment,
    remove_equipment,
)


equipment_bp = Blueprint("equipment", __name__, url_prefix="/api/equipment")

equipment_bp.get("")(list_equipment)
equipment_bp.get("/<equipment_id>")(get_equipment)
equipment_bp.post("")(add_equipment)
equipment_bp.put("/<equipment_id>")(edit_equipment)
equipment_bp.delete("/<equipment_id>")(remove_equipment)
