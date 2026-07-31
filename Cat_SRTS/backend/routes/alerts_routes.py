"""Alerts API routes."""

from flask import Blueprint

from controllers.alerts_controller import list_alerts


alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")

alerts_bp.get("")(list_alerts)

