"""FastAPI router for MOD-11.

Mounted by M1's ``backend/main.py``::

    from backend.forecast.api import router as forecast_router
    app.include_router(forecast_router)

    @app.on_event("startup")
    async def _warm():
        from backend.forecast import service
        service.warm()          # NFR-2: no cold start

``GET /api/forecast`` returns the four keys frozen in PRD section 11 —
``points``, ``lower``, ``upper``, ``verdict``, ``mape`` — with additional keys
alongside them. The frozen keys keep their names and shapes; nothing in
``backend/schemas.py`` or ``openapi.yaml`` is touched from here, since those are
locked shared files.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from . import config, service

router = APIRouter(prefix="/api", tags=["forecast"])


@router.get("/forecast")
def get_forecast(
    type: str | None = Query(
        None, description="Equipment type, e.g. 'Excavator'. Omit for all."
    ),
    site: str | None = Query(
        None, description="Site id, e.g. 'S002'. Omit for all."
    ),
    horizon: int = Query(
        config.FORECAST_HORIZON_WEEKS, ge=1, le=26,
        description="Weeks ahead to forecast.",
    ),
) -> dict:
    """Weekly demand forecast: new rentals commencing per (type x site).

    A ``verdict`` of ``insufficient_data`` is a successful 200 response, not an
    error — the system declining to fabricate is the intended behaviour (FR-6).
    """
    try:
        return service.get_forecast(type=type, site=site, horizon=horizon)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/forecast/backtest")
def get_backtest() -> dict:
    """The rolling-origin backtest harness and its measured error.

    Presented as the deliverable rather than the accuracy figure (PRD 14.2).
    """
    return service.get_backtest()


@router.get("/phase/timeline")
def phase_timeline() -> dict:
    """Every site's phase state plus the observed phase windows.

    Declared before ``/phase/{site_id}`` because FastAPI matches routes in
    order, and a path parameter would otherwise swallow "timeline".
    """
    return service.get_phase_timeline()


@router.get("/phase/model")
def phase_model() -> dict:
    """How well the two phase models actually do.

    The evidence panel: held-out classifier accuracy, phase-end error in weeks
    against a schedule-only baseline, interval coverage, and which phases the
    duration model refuses to speak about.
    """
    return service.get_phase_model()


@router.get("/phase/{site_id}")
def get_phase(site_id: str) -> dict:
    """Current phase, predicted end with a range, and what comes next.

    A ``verdict`` of ``insufficient_data`` is a successful 200 response. Where
    too few phases of a kind have been observed to complete, refusing to name an
    end date is the intended behaviour, not an error.
    """
    try:
        return service.get_phase(site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/allocation")
def get_allocation() -> dict:
    """The decision board: shortfalls, spare machines, and what to do.

    Every recommendation carries both priced options — move a machine you are
    already paying for, or call off a new rental — so the choice can be checked
    rather than trusted.
    """
    return service.get_allocation()


@router.get("/forecast/cells")
def list_cells() -> dict:
    """Every (type x site) cell and whether it can be forecast at all."""
    result = service.get_forecast()
    return {
        "as_of": result["as_of"],
        "cells": [
            {
                "site_id": c["site_id"],
                "type": c["type"],
                "verdict": c["verdict"],
                "reason": c["reason"],
                "nonzero_weeks": c["nonzero_weeks"],
                "total_rentals_observed": c["total_rentals_observed"],
            }
            for c in result["cells"]
        ],
    }
