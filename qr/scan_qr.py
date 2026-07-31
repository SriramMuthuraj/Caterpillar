import cv2
import numpy as np


def decode_image(image_bytes: bytes):
    """Decode a QR code from an in-memory image. Returns the payload or None.

    The headless counterpart to :func:`scan_qr`, which hardcodes
    ``cv2.VideoCapture(0)`` and therefore only works next to a physical webcam.
    This one accepts an upload, so the browser can do the capturing and the
    server just decodes — which is the only arrangement that works over HTTP.
    """
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    if frame is None:
        return None

    data, _bbox, _straight = cv2.QRCodeDetector().detectAndDecode(frame)
    return data or None


def scan_qr():
    """
    Opens the webcam and scans a QR code.

    Returns:
        Machine ID (str) if found
        None if user quits
    """

    detector = cv2.QRCodeDetector()

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Unable to open camera.")
        return None

    print("Scanning... Show the QR code to the camera.")
    print("Press 'q' to quit.\n")

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        data, bbox, _ = detector.detectAndDecode(frame)

        # QR detected
        if bbox is not None:

            # Draw green rectangle around QR
            bbox = bbox.astype(int)

            n = len(bbox)

            for i in range(n):
                pt1 = tuple(bbox[i][0])
                pt2 = tuple(bbox[(i + 1) % n][0])

                cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

            # If successfully decoded
            if data:
                cv2.putText(
                    frame,
                    data,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

                cv2.imshow("QR Scanner", frame)
                cv2.waitKey(1000)

                cap.release()
                cv2.destroyAllWindows()

                return data

        cv2.imshow("QR Scanner", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    return None