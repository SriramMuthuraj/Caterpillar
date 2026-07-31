"""Dashboard request handlers."""

from __future__ import annotations

from flask import jsonify

from services.dashboard_service import get_dashboard_summary


def get_dashboard():
    """Handle GET /api/dashboard."""
    return jsonify(get_dashboard_summary())

