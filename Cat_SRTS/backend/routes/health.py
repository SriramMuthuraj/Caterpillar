"""Health check routes for the CAT_SRTS backend."""

from flask import Blueprint, jsonify

from database.config import DATABASE_NAME
from database.database import active_backend, get_database


health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def root_health():
    """Return backend service health."""
    return jsonify(
        {
            "status": "running",
            "service": "Smart Rental Tracking System Backend",
        }
    )


@health_bp.get("/api/health/database")
def database_health():
    """Report which store is live and that it answers.

    Two backends are possible: MongoDB Atlas, or the in-memory seed store used
    when Atlas is unreachable. Both are healthy states — the point of this
    endpoint is to say *which one you are looking at*, because "the dashboard
    works but my writes vanished on restart" is otherwise a mystery.
    """
    backend = active_backend()

    if backend == "memory":
        db = get_database()
        return jsonify({
            "status": "connected",
            "backend": "memory",
            "database": DATABASE_NAME,
            "message": "Serving the seed files from memory — MongoDB was not "
                       "reachable. Reads and writes work; writes are not "
                       "persisted across a restart.",
            "collections": {
                name: db[name].count_documents({})
                for name in db.list_collection_names()
            },
        })

    try:
        db = get_database()
        db.client.admin.command("ping")
        database_names = db.client.list_database_names()

        if DATABASE_NAME not in database_names:
            return (
                jsonify(
                    {
                        "status": "error",
                        "database": DATABASE_NAME,
                        "message": "Database does not exist.",
                    }
                ),
                500,
            )

        return jsonify(
            {
                "status": "connected",
                "backend": "mongodb",
                "database": DATABASE_NAME,
            }
        )
    except Exception as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "database": DATABASE_NAME,
                    "message": str(exc),
                }
            ),
            500,
        )
