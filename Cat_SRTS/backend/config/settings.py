"""Application settings for the CAT_SRTS Flask backend."""

from __future__ import annotations

import os


class Config:
    """Base Flask configuration."""

    APP_NAME = "CAT_SRTS Backend"
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    HOST = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_RUN_PORT", "5000"))
    JSON_SORT_KEYS = False

