"""Usage log API routes."""

from flask import Blueprint

from controllers.usage_controller import (
    add_usage_log,
    edit_usage_log,
    get_equipment_usage,
    list_usage_logs,
    remove_usage_log,
)


usage_bp = Blueprint("usage", __name__, url_prefix="/api/usage")

usage_bp.get("")(list_usage_logs)
usage_bp.get("/<equipment_id>")(get_equipment_usage)
usage_bp.post("")(add_usage_log)
usage_bp.put("/<log_id>")(edit_usage_log)
usage_bp.delete("/<log_id>")(remove_usage_log)

