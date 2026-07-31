"""Repo-relative path resolution.

The forecast package is imported both by the FastAPI app (cwd = repo root) and
by pytest (cwd = anywhere), so paths are resolved from this file's location
rather than from the working directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import config

# backend/forecast/paths.py -> backend/forecast -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]


def seed_csv() -> Path:
    return REPO_ROOT / config.SEED_CSV


def site_phases_csv() -> Path:
    path = REPO_ROOT / config.SITE_PHASES_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    d = REPO_ROOT / config.CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    """Where the trained model artifacts live.

    Overridable with FLEETTRUST_MODELS so a retrained bundle can be pointed at
    without moving files around.
    """
    override = os.environ.get("FLEETTRUST_MODELS")
    d = Path(override) if override else REPO_ROOT / config.MODELS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d
