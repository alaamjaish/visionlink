"""
Supabase Client Module

Handles session CRUD and file uploads to Supabase (PostgreSQL + Storage).
All uploads are non-blocking (background threads).
"""

import time
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("supabase")


class SupabaseClient:
    """Manages Supabase connection, session records, and file uploads."""

    def __init__(self):
        self._client: Client = None
        self._upload_queue = []

    def setup(self) -> bool:
        """Initialize Supabase client."""
        if not HAS_SUPABASE:
            logger.warning("supabase package not available")
            return False

        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
            logger.warning("Supabase credentials not configured")
            return False

        try:
            start = time.time()
            self._client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
            elapsed = time.time() - start
            logger.info(f"Supabase client initialized ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"Supabase setup failed: {e}", exc_info=True)
            return False

    def create_session(self, task_description: str = None) -> str:
        """Create a new session record. Returns session_id (uuid)."""
        if not self._client:
            logger.error("Supabase not initialized")
            return None

        session_id = str(uuid.uuid4())
        try:
            start = time.time()
            data = {
                "id": session_id,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "status": "active",
                "task_description": task_description,
            }
            result = self._client.table("sessions").insert(data).execute()
            elapsed = time.time() - start
            logger.info(f"Session created: {session_id} ({elapsed:.2f}s)")
            return session_id
        except Exception as e:
            logger.error(f"Create session failed: {e}", exc_info=True)
            return None

    def end_session(self, session_id: str, notes: str = None) -> bool:
        """Mark a session as completed."""
        if not self._client:
            logger.error("Supabase not initialized")
            return False

        try:
            start = time.time()
            data = {
                "end_time": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            }
            if notes:
                data["notes"] = notes
            self._client.table("sessions").update(data).eq("id", session_id).execute()
            elapsed = time.time() - start
            logger.info(f"Session ended: {session_id} ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"End session failed: {e}", exc_info=True)
            return False

    def upload_file(self, session_id: str, local_path: str,
                    file_type: str = "photos") -> bool:
        """Upload a file to Supabase storage. file_type: photos/videos/audio"""
        if not self._client:
            logger.error("Supabase not initialized")
            return False

        filename = Path(local_path).name
        remote_path = f"sessions/{session_id}/{file_type}/{filename}"

        try:
            start = time.time()
            with open(local_path, "rb") as f:
                self._client.storage.from_(config.SUPABASE_BUCKET).upload(
                    remote_path, f.read()
                )
            elapsed = time.time() - start
            logger.info(f"File uploaded: {remote_path} ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"Upload failed ({remote_path}): {e}", exc_info=True)
            return False

    def upload_file_background(self, session_id: str, local_path: str,
                               file_type: str = "photos"):
        """Non-blocking file upload in background thread."""
        def _do_upload():
            for attempt in range(config.MAX_RETRIES):
                if self.upload_file(session_id, local_path, file_type):
                    return
                logger.warning(f"Upload retry {attempt + 1}/{config.MAX_RETRIES} for {local_path}")
                time.sleep(config.RETRY_DELAY)
            logger.error(f"Upload permanently failed after {config.MAX_RETRIES} retries: {local_path}")

        thread = threading.Thread(target=_do_upload, daemon=True)
        thread.start()
        logger.debug(f"Background upload queued: {local_path}")

    def upload_session_files(self, session_id: str, session_dir: str):
        """Upload all files from a session directory (background)."""
        session_path = Path(session_dir)
        if not session_path.exists():
            logger.warning(f"Session directory not found: {session_dir}")
            return

        for subdir, file_type in [("photos", "photos"), ("videos", "videos"), ("audio", "audio")]:
            type_dir = session_path / subdir
            if not type_dir.exists():
                continue
            for file_path in type_dir.iterdir():
                if file_path.is_file():
                    self.upload_file_background(session_id, str(file_path), file_type)
