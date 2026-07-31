"""Alerts request handlers."""

from __future__ import annotations

from flask import jsonify

from services.alerts_service import get_alerts


def list_alerts():
    """Handle GET /api/alerts."""
    return jsonify(get_alerts())

