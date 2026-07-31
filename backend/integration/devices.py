"""QR and email endpoints.

Both wrap modules that were written as desktop scripts: ``qr`` opened an OpenCV
window and read from a local webcam, ``alert`` opened an SMTP socket on import.
Neither is usable from a request handler as written, so this exposes only their
headless entry points:

* ``qr.generate_qr.qr_png_bytes``  — renders to memory, no file, no window
* ``qr.scan_qr.decode_image``      — decodes an upload, no camera
* ``alert.EmailClient.send_email`` — dry-runs unless ALERTS_ENABLED is set

The browser does the camera work and posts a frame here, which is the only
arrangement that works over HTTP anyway.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["devices"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024


# --------------------------------------------------------------------------
# QR
# --------------------------------------------------------------------------

@router.get("/equipment/{equipment_id}/qr", responses={
    200: {"content": {"image/png": {}}, "description": "PNG QR code"},
})
def equipment_qr(equipment_id: str) -> Response:
    """A QR code encoding the equipment id, as a PNG.

    The payload is the bare id (``EQX2001``) — the same string the rest of the
    system keys on, so a scan resolves without a lookup table.
    """
    from qr.generate_qr import qr_png_bytes

    if not equipment_id.strip():
        raise HTTPException(status_code=400, detail="equipment_id is required")

    return Response(
        content=qr_png_bytes(equipment_id.strip()),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/scan")
async def scan(image: UploadFile = File(...)) -> dict:
    """Decode a QR code from an uploaded image.

    Replaces ``scan_qr()``, which hardcodes ``cv2.VideoCapture(0)`` and can only
    ever read the machine the server runs on.
    """
    from qr.scan_qr import decode_image

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    decoded = decode_image(payload)
    if not decoded:
        return {"found": False, "equipment_id": None,
                "message": "No QR code found in the image."}

    return {"found": True, "equipment_id": decoded}


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------

class AlertEmail(BaseModel):
    to: str = Field(..., description="Recipient address")
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1, description="Plain text or HTML")
    html: bool = Field(True, description="Send the body as HTML")


@router.post("/alerts/send")
def send_alert(payload: AlertEmail) -> dict:
    """Email one alert.

    Dry-run by default — the response says ``"reason": "dry_run"`` and no socket
    is opened. Set ``ALERTS_ENABLED=true`` (and the SMTP_* variables in
    ``alert/.env``) to actually deliver. The demo is expected to run offline, so
    off is the safe default rather than an oversight.
    """
    from alert.email_client import EmailClient

    client = EmailClient()
    result = client.send_email(
        receiver=payload.to,
        subject=payload.subject,
        html=payload.body if payload.html else None,
        text=None if payload.html else payload.body,
    )

    if result["reason"].startswith(("SMTP", "OSError", "socket", "TimeoutError")):
        log.warning("alert delivery failed: %s", result["reason"])

    return result
