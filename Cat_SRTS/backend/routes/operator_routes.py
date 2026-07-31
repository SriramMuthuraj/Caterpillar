"""Operator API routes."""

from flask import Blueprint

from controllers.operator_controller import (
    add_operator,
    edit_operator,
    get_operator,
    list_operators,
    remove_operator,
)


operator_bp = Blueprint("operators", __name__, url_prefix="/api/operators")

operator_bp.get("")(list_operators)
operator_bp.get("/<operator_id>")(get_operator)
operator_bp.post("")(add_operator)
operator_bp.put("/<operator_id>")(edit_operator)
operator_bp.delete("/<operator_id>")(remove_operator)

