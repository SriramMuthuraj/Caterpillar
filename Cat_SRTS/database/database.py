"""Reusable MongoDB connection helpers, with an offline fallback.

Atlas is used when it is reachable. When it is not — no network, no password,
sleeping cluster — the seed files are loaded into an in-memory store with the
same interface (``memory_store.py``) and the API comes up regardless.

Without this, a missing ``MONGODB_PASSWORD`` makes every ``/api/*`` route return
500 while the app itself reports healthy, which is the worst way to discover a
problem five minutes before a demo. Writes against the fallback work for the
life of the process; only durability is lost.

Set ``FORCE_MEMORY_DB=true`` to skip Atlas entirely.
"""

from __future__ import annotations

import logging
import os

from pymongo import MongoClient

from .config import DATABASE_NAME, get_mongodb_uri
from . import memory_store

log = logging.getLogger(__name__)

# Atlas gets two seconds to answer. The default is thirty, which turns "no
# network" into a half-minute stall on every request.
SERVER_SELECTION_TIMEOUT_MS = 2_000

_client: MongoClient | None = None
_memory_db: "memory_store.MemoryDatabase | None" = None
_backend: str | None = None          # "mongodb" | "memory", decided once


def _force_memory() -> bool:
    return os.getenv("FORCE_MEMORY_DB", "").lower() in ("1", "true", "yes")


def get_client() -> MongoClient:
    """Return a shared MongoDB client. Raises if Atlas is unavailable."""
    global _client
    if _client is None:
        _client = MongoClient(
            get_mongodb_uri(),
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        )
        # MongoClient constructs lazily, so force a round trip now: the point
        # of the short timeout is to find out immediately, not on first query.
        _client.admin.command("ping")
    return _client


def get_database():
    """Return the project database — Atlas if reachable, else the seed files."""
    global _memory_db, _backend

    if _force_memory():
        if _memory_db is None:
            _memory_db = memory_store.load()
            _backend = "memory"
            log.warning("FORCE_MEMORY_DB set — using the in-memory seed store")
        return _memory_db

    if _backend != "memory":
        try:
            database = get_client()[DATABASE_NAME]
            if _backend != "mongodb":
                _backend = "mongodb"
                log.info("connected to MongoDB Atlas (%s)", DATABASE_NAME)
            return database
        except Exception as exc:
            log.warning(
                "MongoDB unavailable (%s: %s) — falling back to the in-memory "
                "seed store. Data is read-write but not durable.",
                type(exc).__name__, exc,
            )

    if _memory_db is None:
        _memory_db = memory_store.load()
    _backend = "memory"
    return _memory_db


def active_backend() -> str:
    """Which store is live: "mongodb", "memory", or "undetermined"."""
    if _backend is None:
        get_database()
    return _backend or "undetermined"


def close_client() -> None:
    """Close the shared MongoDB client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def reset() -> None:
    """Drop all cached state. Used by tests."""
    global _memory_db, _backend
    close_client()
    _memory_db = None
    _backend = None
