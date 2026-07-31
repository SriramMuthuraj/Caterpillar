"""Create the full MongoDB database structure and seed it from local JSON files."""

from __future__ import annotations

import os

try:
    from .config import COLLECTIONS
    from .create_indexes import create_indexes
    from .database import get_database
    from .seed import seed_database
except ImportError:
    from config import COLLECTIONS
    from create_indexes import create_indexes
    from database import get_database
    from seed import seed_database


def create_collections() -> None:
    """Create required collections if they do not already exist."""
    db = get_database()
    existing_collections = set(db.list_collection_names())

    for collection_name in COLLECTIONS.values():
        if collection_name not in existing_collections:
            db.create_collection(collection_name)


def recreate_database() -> None:
    """
    Recreate the database from local project files.

    This intentionally does not drop data unless CONFIRM_RECREATE=true is set.
    """
    db = get_database()

    if os.getenv("CONFIRM_RECREATE", "").lower() == "true":
        db.client.drop_database(db.name)

    create_collections()
    create_indexes()
    seed_database()


if __name__ == "__main__":
    recreate_database()
    print("Database structure is ready and seed data has been applied.")

