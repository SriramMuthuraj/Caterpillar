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


#: Chart group -> the finding field it reads. Keeps the query string stable
#: even though the underlying field names are the detector's.
_GROUP_FIELDS = {
    "type": "type",
    "site": "site_id",
    "operator": "operator_id",
}

#: Below this, the detector's imbalance rules skip a group entirely
#: (``min_members`` in ``anomaly_detection/src/group_analysis.py``). Charted
#: groups under it are marked rather than dropped, so a viewer can see which
#: bars the rules actually judged.
MIN_GROUP_MEMBERS = 3


@router.get("/anomalies/idle-ratio")
def idle_ratio_by_group(
    group: str = Query("type", description="type | site | operator"),
    limit: int | None = Query(
        None, ge=1, description="Keep only the N worst groups. All, if unset."),
) -> dict:
    """Average idle ratio per equipment type, site or operator.

    Aggregated here rather than in the browser because the average is taken over
    every valid row — 7,209 of them — which ``GET /anomalies`` cannot serve in
    one page and should not have to.

    Mirrors the detector's own group charts: only rows that pass the integrity
    rules count, and the figure is the **unweighted mean of the per-row ratios**,
    not total idle over total hours. A machine that idles all day on one short
    rental should move the number as much as one that does it on a long rental.
    """
    field = _GROUP_FIELDS.get(group)
    if field is None:
        raise HTTPException(
            status_code=422,
            detail=f"group must be one of {sorted(_GROUP_FIELDS)}, not {group!r}",
        )

    result = anomaly_adapter.run()

    ratios: dict[str, list[float]] = {}
    for row in result["findings"]:
        # An invalid row's hours are exactly what the integrity rules rejected,
        # so averaging them in would let bad data set the baseline.
        if not row["is_valid_row"]:
            continue
        key = row.get(field)
        utilisation = row.get("utilisation")
        if not key or utilisation is None:
            continue
        ratios.setdefault(str(key), []).append(1.0 - utilisation)

    groups = sorted(
        (
            {
                "group": key,
                "idle_ratio": round(sum(values) / len(values), 4),
                "n": len(values),
                "compared_by_rules": len(values) >= MIN_GROUP_MEMBERS,
            }
            for key, values in ratios.items()
        ),
        key=lambda entry: entry["idle_ratio"],
        reverse=True,
    )

    return {
        "as_of": result["as_of"],
        "group": group,
        "min_group_members": MIN_GROUP_MEMBERS,
        "total_groups": len(groups),
        "rows_counted": sum(len(v) for v in ratios.values()),
        "groups": groups[:limit] if limit else groups,
    }


@router.get("/anomalies/facets")
def anomaly_facets() -> dict:
    """The distinct sites and types present, for the filter controls.

    Derived from the findings rather than the summary so it stays correct
    against caches written before this endpoint existed.
    """
    result = anomaly_adapter.run()
    sites = {r["site_id"] for r in result["findings"] if r["site_id"]}
    types = {r["type"] for r in result["findings"] if r["type"]}
    return {"sites": sorted(sites), "types": sorted(types)}


@router.get("/anomalies")
def list_anomalies(
    severity: str | None = Query(
        None, description="Critical | Warning | Normal"),
    site_id: str | None = Query(None, description="e.g. 'S002'"),
    type: str | None = Query(None, description="e.g. 'Excavator'"),
    phase: str | None = Query(None, description="e.g. 'excavation'"),
    rule: str | None = Query(
        None, description="e.g. 'impossible_hours'. Matches any flag on the row."),
    equipment_id: str | None = Query(
        None, description="Substring match on the machine id, e.g. 'EQX24'."),
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
    if equipment_id:
        # Substring, so a partial id typed into the search box narrows as you
        # go. Exact-match drill-down is /anomalies/{equipment_id}.
        needle = equipment_id.strip().lower()
        rows = [r for r in rows if needle in r["equipment_id"].lower()]

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
