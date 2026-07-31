"""Anomaly endpoints.

Mounted alongside the forecast router by ``backend/main.py``. The detector
itself lives in ``anomaly_detection/`` and is untouched; this exposes its
findings over HTTP with the phase joined on.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from . import anomaly_adapter

router = APIRouter(prefix="/api", tags=["anomalies"])


@router.get("/anomalies/summary")
def anomalies_summary() -> dict:
    """Counts by severity, rule, category and phase.

    Declared before ``/anomalies/{equipment_id}`` because FastAPI matches in
    order and a path parameter would otherwise swallow "summary".
    """
    result = anomaly_adapter.run()
    return {
        "as_of": result["as_of"],
        "clock_source": result["clock_source"],
        "dataset_fingerprint": result["dataset_fingerprint"],
        "runtime_seconds": result["runtime_seconds"],
        **result["summary"],
    }


@router.get("/anomalies")
def list_anomalies(
    severity: str | None = Query(
        None, description="Critical | Warning | Normal"),
    site_id: str | None = Query(None, description="e.g. 'S002'"),
    type: str | None = Query(None, description="e.g. 'Excavator'"),
    phase: str | None = Query(None, description="e.g. 'excavation'"),
    rule: str | None = Query(
        None, description="e.g. 'impossible_hours'. Matches any flag on the row."),
    flagged_only: bool = Query(
        True, description="Hide rows that scored zero."),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Findings, filtered and paginated.

    Every row the detector scored is available, but ``flagged_only`` defaults to
    True: 5,888 of 7,209 rows score zero and a table of them is not a finding
    list, it is the dataset.
    """
    result = anomaly_adapter.run()
    rows = result["findings"]

    if flagged_only:
        rows = [r for r in rows if r["score"] > 0]
    if severity:
        rows = [r for r in rows if r["severity"].lower() == severity.lower()]
    if site_id:
        rows = [r for r in rows if r["site_id"] == site_id]
    if type:
        rows = [r for r in rows if r["type"].lower() == type.lower()]
    if phase:
        rows = [r for r in rows if (r["phase"] or "").lower() == phase.lower()]
    if rule:
        rows = [r for r in rows
                if any(f["rule"] == rule for f in r["flags"])]

    # Worst first: this is a work queue, not a log.
    rows = sorted(rows, key=lambda r: r["score"], reverse=True)

    return {
        "as_of": result["as_of"],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "findings": rows[offset:offset + limit],
    }


@router.get("/anomalies/{equipment_id}")
def anomalies_for_equipment(equipment_id: str) -> dict:
    """Every finding for one machine, oldest first — its history of trouble."""
    result = anomaly_adapter.run()
    rows = [r for r in result["findings"]
            if r["equipment_id"].lower() == equipment_id.lower()]

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No rentals found for equipment {equipment_id!r}",
        )

    rows = sorted(rows, key=lambda r: r["check_in"])
    flagged = [r for r in rows if r["score"] > 0]

    return {
        "as_of": result["as_of"],
        "equipment_id": rows[0]["equipment_id"],
        "type": rows[0]["type"],
        "rentals_scored": len(rows),
        "rentals_flagged": len(flagged),
        "worst_severity": max(
            (r["severity"] for r in rows),
            key=lambda s: {"Critical": 2, "Warning": 1, "Normal": 0}.get(s, 0),
        ),
        "findings": rows,
    }
