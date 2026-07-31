import io

import qrcode


def qr_png_bytes(machine_id: str) -> bytes:
    """Render a QR code for ``machine_id`` and return the PNG as bytes.

    The headless path. Touches no filesystem and opens no window, so it is safe
    to call from a request handler — unlike :func:`generate_qr`, which saves to
    the current working directory and blocks on ``cv2.waitKey``.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(machine_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr(machine_id: str, show: bool = False, out_dir: str = "."):
    """Generate a QR code, save it to ``out_dir``, and return the path.

    ``show`` opens an OpenCV preview window that blocks until a key is pressed.
    It defaults to False: it used to be unconditional, which meant any caller
    without a display — a web worker, a test runner — hung forever.
    """
    import os

    os.makedirs(out_dir, exist_ok=True)
    filename = os.path.join(out_dir, f"{machine_id}.png")

    with open(filename, "wb") as handle:
        handle.write(qr_png_bytes(machine_id))

    if show:
        import cv2

        cv2.imshow("Generated QR Code", cv2.imread(filename))
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return filename
