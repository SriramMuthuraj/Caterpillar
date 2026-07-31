"""Dashboard API routes."""

from flask import Blueprint

from controllers.dashboard_controller import get_dashboard


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

dashboard_bp.get("")(get_dashboard)

