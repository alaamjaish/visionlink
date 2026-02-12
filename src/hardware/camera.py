"""
Camera Module

Handles photo capture, video recording, and provides frames for QR scanning.
Uses Pi Camera Module v3 via picamera2.
"""

import time
import threading
from pathlib import Path

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
    HAS_CAMERA = True
except ImportError:
    HAS_CAMERA = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("camera")


class Camera:
    """Pi Camera v3 handler for photos, video, and QR scanning."""

    def __init__(self):
        self._camera = None
        self._recording = False
        self._auto_capture_timer = None
        self._auto_capture_running = False

    def setup(self):
        """Initialize the camera."""
        if not HAS_CAMERA:
            logger.warning("picamera2 not available - camera will not work")
            return False

        try:
            self._camera = Picamera2()
            # Configure for still capture by default
            cam_config = self._camera.create_still_configuration(
                main={"size": config.PHOTO_RESOLUTION}
            )
            self._camera.configure(cam_config)
            self._camera.start()
            time.sleep(1)  # Warm-up
            logger.info(f"Camera initialized at {config.PHOTO_RESOLUTION}")
            return True
        except Exception as e:
            logger.error(f"Camera setup failed: {e}", exc_info=True)
            return False

    def take_photo(self, output_path: str) -> bool:
        """Capture a photo and save to output_path."""
        if not self._camera:
            logger.error("Camera not initialized")
            return False

        try:
            start = time.time()
            self._camera.capture_file(output_path)
            elapsed = time.time() - start
            logger.info(f"Photo captured: {output_path} ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"Photo capture failed: {e}", exc_info=True)
            return False

    def start_video(self, output_path: str) -> bool:
        """Start recording video. Auto-stops at VIDEO_MAX_DURATION."""
        if not self._camera:
            logger.error("Camera not initialized")
            return False

        if self._recording:
            logger.warning("Already recording")
            return False

        try:
            encoder = H264Encoder(bitrate=5_000_000)
            output = FfmpegOutput(output_path)
            self._camera.start_recording(encoder, output)
            self._recording = True
            logger.info(f"Video recording started: {output_path}")

            # Auto-stop timer
            self._video_timer = threading.Timer(
                config.VIDEO_MAX_DURATION, self.stop_video
            )
            self._video_timer.start()
            return True
        except Exception as e:
            logger.error(f"Video start failed: {e}", exc_info=True)
            return False

    def stop_video(self) -> bool:
        """Stop recording video."""
        if not self._recording:
            return False

        try:
            if hasattr(self, '_video_timer'):
                self._video_timer.cancel()
            self._camera.stop_recording()
            self._recording = False
            logger.info("Video recording stopped")
            return True
        except Exception as e:
            logger.error(f"Video stop failed: {e}", exc_info=True)
            return False

    def is_recording(self) -> bool:
        return self._recording

    def capture_frame(self):
        """Capture a single frame as numpy array (for QR scanning / AI)."""
        if not self._camera:
            logger.error("Camera not initialized")
            return None

        try:
            frame = self._camera.capture_array()
            logger.debug("Frame captured for processing")
            return frame
        except Exception as e:
            logger.error(f"Frame capture failed: {e}", exc_info=True)
            return None

    def start_auto_capture(self, session_dir: str, callback=None):
        """Start periodic auto-capture of photos."""
        if config.AUTO_CAPTURE_INTERVAL <= 0:
            logger.info("Auto-capture disabled (interval=0)")
            return

        self._auto_capture_running = True
        self._auto_capture_count = 0

        def _auto_loop():
            while self._auto_capture_running:
                time.sleep(config.AUTO_CAPTURE_INTERVAL)
                if not self._auto_capture_running:
                    break
                self._auto_capture_count += 1
                path = str(Path(session_dir) / f"auto_{self._auto_capture_count:04d}.jpg")
                if self.take_photo(path) and callback:
                    callback(path)

        self._auto_thread = threading.Thread(target=_auto_loop, daemon=True)
        self._auto_thread.start()
        logger.info(f"Auto-capture started (every {config.AUTO_CAPTURE_INTERVAL}s)")

    def stop_auto_capture(self):
        """Stop periodic auto-capture."""
        self._auto_capture_running = False
        logger.info("Auto-capture stopped")

    def cleanup(self):
        """Release camera resources."""
        self.stop_auto_capture()
        if self._recording:
            self.stop_video()
        if self._camera:
            self._camera.close()
            self._camera = None
        logger.info("Camera cleaned up")
