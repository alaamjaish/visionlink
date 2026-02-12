"""
Session Manager

Manages documentation sessions - one at a time only.
Handles local file organization and Supabase sync.
"""

import time
import uuid
from pathlib import Path
from enum import Enum

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("session")


class SessionState(Enum):
    IDLE = "idle"
    ACTIVE = "active"


class SessionManager:
    """Manages documentation sessions with local storage and cloud sync."""

    def __init__(self, supabase_client=None):
        self._state = SessionState.IDLE
        self._session_id = None
        self._session_dir = None
        self._supabase = supabase_client
        self._photo_count = 0
        self._video_count = 0
        self._audio_count = 0

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_dir(self) -> str:
        return str(self._session_dir) if self._session_dir else None

    @property
    def is_active(self) -> bool:
        return self._state == SessionState.ACTIVE

    def start_session(self, task_description: str = None) -> bool:
        """Start a new documentation session."""
        if self._state == SessionState.ACTIVE:
            logger.warning("Session already active, end it first")
            return False

        self._session_id = str(uuid.uuid4())
        self._session_dir = config.SESSIONS_DIR / self._session_id

        # Create local directories
        (self._session_dir / "photos").mkdir(parents=True, exist_ok=True)
        (self._session_dir / "videos").mkdir(parents=True, exist_ok=True)
        (self._session_dir / "audio").mkdir(parents=True, exist_ok=True)

        # Create cloud session record
        if self._supabase:
            cloud_id = self._supabase.create_session(task_description)
            if cloud_id:
                # Use the cloud-generated ID if available
                pass  # We already set our own ID

        self._state = SessionState.ACTIVE
        self._photo_count = 0
        self._video_count = 0
        self._audio_count = 0

        logger.info(f"Session started: {self._session_id}")
        logger.info(f"Session directory: {self._session_dir}")
        return True

    def end_session(self) -> bool:
        """End the current session and trigger upload."""
        if self._state != SessionState.ACTIVE:
            logger.warning("No active session to end")
            return False

        # Upload all files to Supabase
        if self._supabase:
            self._supabase.end_session(self._session_id)
            self._supabase.upload_session_files(self._session_id, str(self._session_dir))

        old_id = self._session_id
        self._state = SessionState.IDLE
        self._session_id = None
        self._session_dir = None

        logger.info(f"Session ended: {old_id} (photos={self._photo_count}, videos={self._video_count}, audio={self._audio_count})")
        return True

    def get_photo_path(self) -> str:
        """Get the next photo file path for the current session."""
        if not self.is_active:
            return None
        self._photo_count += 1
        path = self._session_dir / "photos" / f"photo_{self._photo_count:04d}.jpg"
        logger.debug(f"Photo path: {path}")
        return str(path)

    def get_video_path(self) -> str:
        """Get the next video file path for the current session."""
        if not self.is_active:
            return None
        self._video_count += 1
        path = self._session_dir / "videos" / f"video_{self._video_count:04d}.mp4"
        logger.debug(f"Video path: {path}")
        return str(path)

    def get_audio_path(self) -> str:
        """Get the next audio file path for the current session."""
        if not self.is_active:
            return None
        self._audio_count += 1
        path = self._session_dir / "audio" / f"note_{self._audio_count:04d}.wav"
        logger.debug(f"Audio path: {path}")
        return str(path)
