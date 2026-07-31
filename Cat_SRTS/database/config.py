"""Configuration for the CAT Smart Rental Tracking System database module."""

from __future__ import annotations

import os


DATABASE_NAME = os.getenv("MONGODB_DATABASE", "smart_rental_tracking_system")

COLLECTION_EQUIPMENT = "equipment"
COLLECTION_OPERATORS = "operators"
COLLECTION_ASSIGNMENTS = "assignments"
COLLECTION_USAGE_LOGS = "usage_logs"

COLLECTIONS = {
    "equipment": COLLECTION_EQUIPMENT,
    "operators": COLLECTION_OPERATORS,
    "assignments": COLLECTION_ASSIGNMENTS,
    "usage_logs": COLLECTION_USAGE_LOGS,
}

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_HOST = os.getenv("MONGODB_HOST", "cluster0.oqcnmna.mongodb.net")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "madhavan86776_db_user")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_APP_NAME = os.getenv("MONGODB_APP_NAME", "Cluster0")


def get_mongodb_uri() -> str:
    """Return the MongoDB connection URI from environment configuration."""
    if MONGODB_URI:
        return MONGODB_URI

    if not MONGODB_PASSWORD:
        raise RuntimeError(
            "Set MONGODB_URI or MONGODB_PASSWORD before connecting to MongoDB Atlas."
        )

    return (
        f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}/"
        f"{DATABASE_NAME}?retryWrites=true&w=majority&appName={MONGODB_APP_NAME}"
    )

