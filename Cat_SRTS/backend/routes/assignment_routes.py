"""Assignment API routes."""

from flask import Blueprint

from controllers.assignment_controller import (
    add_assignment,
    edit_assignment,
    get_assignment,
    list_assignments,
    remove_assignment,
)


assignment_bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")

assignment_bp.get("")(list_assignments)
assignment_bp.get("/<assignment_id>")(get_assignment)
assignment_bp.post("")(add_assignment)
assignment_bp.put("/<assignment_id>")(edit_assignment)
assignment_bp.delete("/<assignment_id>")(remove_assignment)

