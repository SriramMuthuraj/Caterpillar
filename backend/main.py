"""FleetTrust — one application, one port.

    uvicorn backend.main:app --reload --port 8000

Three backends were built independently and are served together here so the
frontend has a single base URL and CORS stops being a question:

    /api/forecast, /api/phase/*, /api/allocation    FastAPI   backend/forecast
    /api/anomalies/*                                FastAPI   backend/integration
    /api/equipment|operators|assignments|usage|     Flask     Cat_SRTS/backend
    /api/dashboard|alerts|health/database                     (mounted via WSGI)

FastAPI is the host and its routes are matched first; everything else falls
through to the Flask app. The namespaces do not overlap.

**Why mount rather than port the Flask routes.** Porting ~30 CRUD endpoints to
FastAPI is mechanical work whose only prize is a single /docs page, and it would
leave the Flask app unrunnable on its own. Mounting keeps ``create_app()``
standalone — if this ever misbehaves, run the two processes separately and point
the frontend at both.

**The sys.path hazard.** ``Cat_SRTS/backend/app.py`` inserts ``Cat_SRTS/`` at the
front of ``sys.path``, which makes ``config``, ``routes``, ``services`` and
``database`` importable as top-level names. ``backend/forecast`` uses relative
imports throughout and is immune, but the Flask import still happens *after* the
forecast package is loaded and warmed, so there is no window in which a bare
``import config`` could resolve to the wrong module.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import clock_adapter, service  # noqa: E402
from backend.forecast.api import router as forecast_router  # noqa: E402
from backend.integration.api import router as anomaly_router  # noqa: E402
from backend.integration.devices import router as devices_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("fleettrust")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Build everything before the first request.

    The forecast bundle takes about forty seconds to assemble. Paying that on a
    judge's first click is the difference between a demo and an apology.
    """
    log.info("clock is %s (%s)",
             clock_adapter.now_date(), clock_adapter.clock_source())
    log.info("warming the forecast bundle...")
    service.warm()
    log.info("ready")

    # Warm the anomaly cache too, in the background of startup rather than on
    # a request. It is a no-op once the fingerprinted cache file exists.
    try:
        from backend.integration import anomaly_adapter
        result = anomaly_adapter.run()
        log.info("anomalies ready: %d rows scored, %d flagged",
                 result["summary"]["rows_scored"],
                 result["summary"]["rows_flagged"])
    except Exception as exc:                       # pragma: no cover
        # A broken detector must not stop the rest of the product from serving.
        log.warning("anomaly detector unavailable: %s: %s",
                    type(exc).__name__, exc)

    yield


app = FastAPI(
    title="FleetTrust",
    description="Phase-aware demand forecasting, allocation and anomaly "
                "detection for rented construction plant.",
    version="1.0.0",
    lifespan=lifespan,
)

# The Vite dev server runs on :3000 and the Flask app already sets its own
# permissive CORS; this covers the FastAPI half.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast_router)
app.include_router(anomaly_router)
# Declared before the Flask mount so /api/equipment/{id}/qr resolves here rather
# than falling through to Flask's /api/equipment/<id> handler.
app.include_router(devices_router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Is everything up, and which clock and dataset are we on?"""
    from backend.forecast import artifacts, history

    return {
        "status": "ok",
        "clock": {
            "now": clock_adapter.now_date().isoformat(),
            "source": clock_adapter.clock_source(),
        },
        "dataset_fingerprint": history.dgp_fingerprint(),
        "models": artifacts.describe(),
    }


def _mount_flask() -> None:
    """Mount the Cat_SRTS Flask app last, so it catches whatever is left."""
    sys.path.insert(0, str(REPO_ROOT / "Cat_SRTS"))
    sys.path.insert(0, str(REPO_ROOT / "Cat_SRTS" / "backend"))

    from app import create_app                     # Cat_SRTS/backend/app.py

    app.mount("/", WSGIMiddleware(create_app()))
    log.info("mounted Cat_SRTS Flask app at /")


_mount_flask()
