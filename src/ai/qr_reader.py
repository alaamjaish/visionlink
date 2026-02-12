"""
QR Code Reader

Reads QR codes from camera frames using pyzbar.
Falls back to sending image to AI if no QR found.
"""

import time

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except ImportError:
    HAS_PYZBAR = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

from src.utils.logger import get_logger

logger = get_logger("qr")


class QRReader:
    """QR code scanner from camera frames or image files."""

    def __init__(self):
        pass

    def scan_frame(self, frame) -> list:
        """Scan a numpy frame for QR codes. Returns list of decoded strings."""
        if not HAS_PYZBAR:
            logger.warning("pyzbar not available")
            return []

        try:
            start = time.time()
            decoded = pyzbar.decode(frame)
            results = [obj.data.decode("utf-8") for obj in decoded]
            elapsed = time.time() - start

            if results:
                logger.info(f"QR found ({elapsed:.2f}s): {results}")
            else:
                logger.debug(f"No QR found in frame ({elapsed:.2f}s)")
            return results
        except Exception as e:
            logger.error(f"QR scan failed: {e}", exc_info=True)
            return []

    def scan_image(self, image_path: str) -> list:
        """Scan an image file for QR codes."""
        if not HAS_CV2:
            logger.warning("OpenCV not available")
            return []

        try:
            frame = cv2.imread(image_path)
            if frame is None:
                logger.error(f"Could not read image: {image_path}")
                return []
            return self.scan_frame(frame)
        except Exception as e:
            logger.error(f"QR scan from file failed: {e}", exc_info=True)
            return []
