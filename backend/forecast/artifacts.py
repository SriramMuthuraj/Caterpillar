"""Persisted model artifacts.

Two models, therefore two files:

===========================  ===========================================
``models/phase_classifier.pkl``  "which phase is this site in?"
``models/phase_end.pkl``         "when does that phase end?"
===========================  ===========================================

Four fitted estimators in total — the phase-end model is three quantile
regressors (P10/P50/P90), which are one *model* because a single interval
prediction needs all three plus the conformal pad. Splitting those apart would
produce a file that cannot answer anything on its own.

**Why a fingerprint.** A checked-in ``.pkl`` invites one specific failure: the
dataset is regenerated, nobody retrains, and the app serves a model fitted to
data that no longer exists. Nothing looks broken — the numbers are just wrong.
So each bundle records ``dgp_fingerprint()`` of the history it was trained on,
and a mismatch is treated as *no artifact at all*: the model is refitted (about
two seconds) and the file rewritten. Loud, cheap, and impossible to miss.

The same reasoning covers ``feature_columns``: a bundle trained before a feature
was added would otherwise be fed a differently-shaped matrix and either crash or
silently misalign columns.

Training is fast enough that none of this is an optimisation — it exists so the
models are inspectable and hand-offable, not to save time.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import joblib

from . import config, paths

log = logging.getLogger(__name__)

# Bumped when the bundle layout changes in a way older files cannot satisfy.
SCHEMA_VERSION = 1


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def classifier_path() -> Path:
    return paths.models_dir() / config.CLASSIFIER_ARTIFACT


def phase_end_path() -> Path:
    return paths.models_dir() / config.PHASE_END_ARTIFACT


# --------------------------------------------------------------------------
# Save
# --------------------------------------------------------------------------

def save_classifier(clf, fingerprint: str, path: Path | None = None) -> Path:
    """Write the fitted phase classifier."""
    path = path or classifier_path()
    joblib.dump(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "phase_classifier",
            "fingerprint": fingerprint,
            "feature_columns": list(clf.feature_columns),
            # Label ordering is not cosmetic: the model predicts integer class
            # indices, so a reordering here silently permutes every prediction.
            "classes_": list(clf.labels),
            "model": clf.model,
            "scores": asdict(clf.report) if clf.report is not None else None,
        },
        path,
    )
    log.info("wrote %s (fingerprint %s)", path.name, fingerprint)
    return path


def save_phase_end(model, fingerprint: str, path: Path | None = None) -> Path:
    """Write the fitted phase-end quantile model."""
    path = path or phase_end_path()
    joblib.dump(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "phase_end",
            "fingerprint": fingerprint,
            "feature_columns": list(model.feature_columns),
            "models": dict(model.models),          # keyed by quantile
            # Without this the P10-P90 band is the raw fitted quantiles, which
            # measured 0.40 coverage at a nominal 0.80. Not optional.
            "interval_pad": float(model.interval_pad),
            "mean_duration": dict(model.mean_duration),
            "trainable_phases": sorted(model.trainable_phases),
            "scores": asdict(model.report) if model.report is not None else None,
        },
        path,
    )
    log.info("wrote %s (fingerprint %s)", path.name, fingerprint)
    return path


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------

def _read(path: Path, kind: str, fingerprint: str,
          feature_columns: list[str], required: tuple[str, ...]) -> dict | None:
    """Load and validate a bundle. Returns None — never raises — on any doubt.

    Every rejection path logs at WARNING and falls through to a refit. A model
    that cannot be trusted is worth strictly less than two seconds of training.
    """
    if not path.exists():
        log.info("%s not found — training from scratch", path.name)
        return None

    try:
        bundle = joblib.load(path)
    except Exception as exc:
        log.warning("%s is unreadable (%s) — retraining", path.name, exc)
        return None

    if not isinstance(bundle, dict):
        log.warning("%s is not a model bundle — retraining", path.name)
        return None

    if bundle.get("schema_version") != SCHEMA_VERSION:
        log.warning("%s has schema v%s, expected v%s — retraining",
                    path.name, bundle.get("schema_version"), SCHEMA_VERSION)
        return None

    if bundle.get("kind") != kind:
        log.warning("%s holds a '%s' model, expected '%s' — retraining",
                    path.name, bundle.get("kind"), kind)
        return None

    if bundle.get("fingerprint") != fingerprint:
        log.warning(
            "%s was trained on dataset %s but the current dataset is %s — "
            "retraining. (The data changed and the model did not.)",
            path.name, bundle.get("fingerprint"), fingerprint,
        )
        return None

    if list(bundle.get("feature_columns") or []) != list(feature_columns):
        log.warning("%s was trained on a different feature set — retraining",
                    path.name)
        return None

    missing = [key for key in required if bundle.get(key) is None]
    if missing:
        log.warning("%s is incomplete, missing %s — retraining",
                    path.name, ", ".join(missing))
        return None

    log.info("loaded %s (fingerprint %s)", path.name, fingerprint)
    return bundle


def load_classifier(fingerprint: str, feature_columns: list[str],
                    path: Path | None = None) -> dict | None:
    return _read(
        path or classifier_path(), "phase_classifier", fingerprint,
        feature_columns, required=("model", "classes_"),
    )


def load_phase_end(fingerprint: str, feature_columns: list[str],
                   path: Path | None = None) -> dict | None:
    return _read(
        path or phase_end_path(), "phase_end", fingerprint, feature_columns,
        # interval_pad is required: a bundle without it would serve
        # uncalibrated intervals that look fine and cover 0.40 instead of 0.80.
        required=("models", "interval_pad", "trainable_phases"),
    )


def describe() -> dict:
    """What is on disk right now — for /api/phase/model and the CLI."""
    out = {}
    for name, path in (("phase_classifier", classifier_path()),
                       ("phase_end", phase_end_path())):
        if not path.exists():
            out[name] = {"present": False, "path": str(path)}
            continue
        try:
            bundle = joblib.load(path)
            out[name] = {
                "present": True,
                "path": str(path),
                "fingerprint": bundle.get("fingerprint"),
                "schema_version": bundle.get("schema_version"),
                "size_bytes": path.stat().st_size,
            }
        except Exception as exc:
            out[name] = {"present": True, "path": str(path),
                         "error": f"{type(exc).__name__}: {exc}"}
    return out
