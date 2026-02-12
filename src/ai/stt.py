"""
Soniox Speech-to-Text Integration

Converts recorded audio (WAV) to text using Soniox API.
"""

import time

try:
    from soniox.speech_service import SpeechClient
    from soniox.transcribe_live import transcribe_file
    HAS_SONIOX = True
except ImportError:
    HAS_SONIOX = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("stt")


class SpeechToText:
    """Soniox STT client for voice transcription."""

    def __init__(self):
        self._client = None

    def setup(self) -> bool:
        """Initialize Soniox client."""
        if not HAS_SONIOX:
            logger.warning("soniox package not available")
            return False

        if not config.SONIOX_API_KEY:
            logger.warning("Soniox API key not configured")
            return False

        try:
            # Soniox SDK initialization may vary - needs verification
            self._client = True  # Placeholder - actual init depends on SDK
            logger.info("Soniox STT initialized")
            return True
        except Exception as e:
            logger.error(f"Soniox setup failed: {e}", exc_info=True)
            return False

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe a WAV file to text."""
        if not self._client:
            logger.error("STT not initialized")
            return ""

        try:
            start = time.time()
            # TODO: Implement actual Soniox transcription
            # The exact API depends on the Soniox Python SDK version
            # result = transcribe_file(audio_path, api_key=config.SONIOX_API_KEY)
            logger.warning("STT transcribe_file not yet implemented - needs Soniox SDK research")
            elapsed = time.time() - start
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            return ""

    def transcribe_bytes(self, wav_data: bytes) -> str:
        """Transcribe WAV bytes to text."""
        if not self._client:
            logger.error("STT not initialized")
            return ""

        try:
            start = time.time()
            # TODO: Implement actual Soniox transcription from bytes
            logger.warning("STT transcribe_bytes not yet implemented")
            elapsed = time.time() - start
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            return ""
