"""Runs the anomaly detector over the fleet history and serves its findings.

The detector was written against the original supplied schema — nine
PascalCase columns — and it is scored by a golden test that pins exact results
against its own 76-row sample. So nothing here edits its rules. The dataset is
renamed on the way in (``dataset.anomaly_view``) and the phase is joined back on
the way out. His module stays exactly as he wrote it.

**Why the phase is added afterwards.** His rules compare a machine against peers
grouped by type, site or operator. None of those know what stage the project is
at, and 20% utilisation is unremarkable during structural erection and alarming
during earthworks. Attaching the phase to each finding does not change any
score — it changes whether a reader can tell which of those two they are looking
at.

Results are cached against the dataset fingerprint, so a judge's first click
costs nothing and a regenerated dataset invalidates automatically.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from ..forecast import clock_adapter, history as history_mod, paths
from . import dataset

log = logging.getLogger(__name__)

_cache: dict | None = None


def _cache_path() -> Path:
    return paths.cache_dir() / f"anomalies_{history_mod.dgp_fingerprint()}.json"


# --------------------------------------------------------------------------
# Running the detector
# --------------------------------------------------------------------------

def _run_detector(now: date) -> list[dict]:
    """Invoke the teammate's pipeline on a temp copy of the renamed history."""
    # Imported here, not at module scope: the package appends its own directory
    # to sys.path on import, and there is no reason to do that unless a request
    # actually needs the detector.
    from anomaly_detection.main import run_pipeline

    with tempfile.TemporaryDirectory() as workspace:
        csv_path = Path(workspace) / "fleet_history.csv"
        dataset.write_anomaly_csv(csv_path, now=now)

        # write_outputs=False: his CLI writes flagged_anomalies.{json,csv} into
        # his own output/ directory, which is his artefact, not ours to churn.
        return run_pipeline(
            str(csv_path), enable_gemini=False, now=now, write_outputs=False
        )


def _enrich(results: list[dict], now: date) -> list[dict]:
    """Attach rental_id and phase to each scored row, and tidy the shape.

    The join is positional: his ``row_index`` is the CSV line number, so
    ``row_index - 2`` indexes the frame we handed him, and the anomaly view
    preserves the history's row order. Asserted rather than assumed, because a
    silent off-by-one here would label findings with the wrong site's phase.
    """
    source = dataset.history().reset_index(drop=True)
    if len(source) != len(results):
        raise RuntimeError(
            f"detector returned {len(results)} rows for {len(source)} rentals — "
            "row alignment cannot be trusted"
        )

    findings = []
    for result in results:
        index = result["row_index"] - 2
        row = source.iloc[index]

        phase = row["phase"]
        site_id = row["site_id"]

        findings.append({
            "row_id": result["row_index"],
            "rental_id": row["rental_id"],
            "equipment_id": result["Equipment_ID"],
            "type": result["Type"],
            "site_id": None if pd.isna(site_id) else site_id,
            # The context his rules cannot see: same-type-same-phase is a very
            # different comparison from same-type.
            "phase": None if pd.isna(phase) else phase,
            "operator_id": (None if result["Last_Operator_ID"] == "NULL"
                            else result["Last_Operator_ID"]),
            "check_in": result["Check_In_Date"],
            "check_out": result["Check_Out_Date"],
            "engine_hours_per_day": float(row["engine_hours_per_day"]),
            "idle_hours_per_day": float(row["idle_hours_per_day"]),
            "utilisation": _utilisation(row),
            "score": result["score"],
            "severity": result["level"],
            "is_valid_row": not any(
                f.get("category") == "integrity" for f in _flags(result)
            ),
            "flags": _flags(result),
        })

    return findings


def _utilisation(row) -> float | None:
    """engine / (engine + idle). Disjoint hours, so this is the real split."""
    engine = float(row["engine_hours_per_day"])
    idle = float(row["idle_hours_per_day"])
    total = engine + idle
    return round(engine / total, 4) if total > 0 else None


_CATEGORY = {
    "impossible_hours": "integrity",
    "bad_date_order": "integrity",
    "zero_activity": "integrity",
    "rental_days_mismatch": "integrity",
    "booking_conflict": "integrity",
    "unassigned_equipment": "asset_rule",
    "no_accountability": "asset_rule",
    "under_utilized": "asset_rule",
    "overdue": "asset_rule",
    "self_baseline_deviation": "self_baseline",
    "type_level_imbalance": "group",
    "site_id_level_imbalance": "group",
    "last_operator_id_level_imbalance": "group",
}


def _flags(result: dict) -> list[dict]:
    """Normalise his flag dicts: rule name out front, evidence kept intact."""
    flags = []
    for flag in result.get("flags", []):
        detail = {k: v for k, v in flag.items() if k != "rule"}
        rule = flag.get("rule", "unknown")
        flags.append({
            "rule": rule,
            "category": _CATEGORY.get(rule, "unknown"),
            "evidence": detail,
        })
    return flags


# --------------------------------------------------------------------------
# Public surface
# --------------------------------------------------------------------------

def run(now: date | None = None, refresh: bool = False) -> dict:
    """Findings for the whole history. Cached on the dataset fingerprint."""
    global _cache

    if _cache is not None and not refresh:
        return _cache

    path = _cache_path()
    if path.exists() and not refresh:
        try:
            _cache = json.loads(path.read_text(encoding="utf-8"))
            log.info("loaded %s (%d findings)", path.name,
                     len(_cache["findings"]))
            return _cache
        except Exception as exc:
            log.warning("%s unreadable (%s) — rerunning", path.name, exc)

    now = now or clock_adapter.now_date()
    started = time.perf_counter()
    findings = _enrich(_run_detector(now), now)
    elapsed = time.perf_counter() - started

    _cache = {
        "as_of": now.isoformat(),
        "clock_source": clock_adapter.clock_source(),
        "dataset_fingerprint": history_mod.dgp_fingerprint(),
        "rows_scored": len(findings),
        "runtime_seconds": round(elapsed, 2),
        "summary": summarise(findings),
        "findings": findings,
    }

    path.write_text(json.dumps(_cache), encoding="utf-8")
    log.info("scored %d rows in %.1fs -> %s", len(findings), elapsed, path.name)
    return _cache


def summarise(findings: list[dict]) -> dict:
    """Counts by severity, rule, category and phase — the page header numbers."""
    flagged = [f for f in findings if f["score"] > 0]

    by_rule = Counter(
        flag["rule"] for finding in findings for flag in finding["flags"]
    )
    by_category = Counter(
        flag["category"] for finding in findings for flag in finding["flags"]
    )
    by_phase = Counter(
        finding["phase"] or "unassigned" for finding in flagged
    )

    return {
        "rows_scored": len(findings),
        "rows_flagged": len(flagged),
        "by_severity": dict(Counter(f["severity"] for f in findings)),
        "by_rule": dict(by_rule.most_common()),
        "by_category": dict(by_category.most_common()),
        "by_phase": dict(by_phase.most_common()),
        "machines_flagged": len({f["equipment_id"] for f in flagged}),
    }


def reset() -> None:
    """Drop the in-process cache. Used by tests and clock scrubbing."""
    global _cache
    _cache = None
