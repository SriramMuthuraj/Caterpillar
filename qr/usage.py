"""Manual smoke test for the QR helpers.

This used to run at *import* time — writing a PNG and opening the webcam as a
side effect of importing the module. Now behind a __main__ guard::

    python -m qr.usage
"""

try:
    from .generate_qr import generate_qr
    from .scan_qr import scan_qr
except ImportError:
    from generate_qr import generate_qr
    from scan_qr import scan_qr


if __name__ == "__main__":
    # EQX-prefixed to match the equipment_id space the rest of the project uses;
    # the old "MCH001" payload did not correspond to any real machine.
    path = generate_qr("EQX2001", show=True)
    print(f"QR saved as {path}")
    print("Machine ID:", scan_qr())
