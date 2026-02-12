"""
Documentation Subsystem

Buttons 1-3: Session management, photo/video capture, voice notes.
"""

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

from src.utils.logger import get_logger

logger = get_logger("doc_mode")


class DocumentationMode:
    """Documentation subsystem controller (Buttons 1-3)."""

    def __init__(self, session_manager, camera, audio_recorder, audio_player, supabase_client=None):
        self._session = session_manager
        self._camera = camera
        self._recorder = audio_recorder
        self._player = audio_player
        self._supabase = supabase_client

    # === Button 1: Session Start/Stop ===

    def toggle_session(self):
        """Button 1: Start or stop a documentation session."""
        if self._session.is_active:
            self._stop_session()
        else:
            self._start_session()

    def _start_session(self):
        """Start a new documentation session."""
        logger.info("Starting documentation session...")
        if self._session.start_session():
            # Start auto-capture
            self._camera.start_auto_capture(
                self._session.session_dir + "/photos",
                callback=self._on_auto_capture
            )
            self._player.speak("Session started.")
            logger.info("Documentation session started successfully")
        else:
            self._player.speak("Could not start session.")
            logger.error("Failed to start documentation session")

    def _stop_session(self):
        """Stop the current documentation session."""
        logger.info("Stopping documentation session...")
        self._camera.stop_auto_capture()
        if self._camera.is_recording():
            self._camera.stop_video()
        if self._session.end_session():
            self._player.speak("Session ended. Files uploading.")
            logger.info("Documentation session stopped successfully")
        else:
            self._player.speak("Error ending session.")
            logger.error("Failed to stop documentation session")

    def _on_auto_capture(self, photo_path: str):
        """Callback when auto-capture takes a photo."""
        if self._supabase and self._session.session_id:
            self._supabase.upload_file_background(
                self._session.session_id, photo_path, "photos"
            )

    # === Button 2: Photo / Video ===

    def take_photo(self):
        """Button 2 single press: Take a photo."""
        if not self._session.is_active:
            self._player.speak("Start a session first.")
            logger.warning("Photo attempted without active session")
            return

        path = self._session.get_photo_path()
        if self._camera.take_photo(path):
            logger.info(f"Photo taken: {path}")
            if self._supabase and self._session.session_id:
                self._supabase.upload_file_background(
                    self._session.session_id, path, "photos"
                )
        else:
            self._player.speak("Photo failed.")

    def toggle_video(self):
        """Button 2 double press: Start/stop video recording."""
        if not self._session.is_active:
            self._player.speak("Start a session first.")
            return

        if self._camera.is_recording():
            self._camera.stop_video()
            self._player.speak("Video saved.")
            logger.info("Video recording stopped")
        else:
            path = self._session.get_video_path()
            if self._camera.start_video(path):
                self._player.speak("Recording.")
                logger.info(f"Video recording started: {path}")
            else:
                self._player.speak("Video failed.")

    # === Button 3: Voice Note ===

    def start_voice_note(self):
        """Button 3 hold start: Begin recording voice note."""
        if not self._session.is_active:
            self._player.speak("Start a session first.")
            return

        self._recorder.start_recording()
        logger.info("Voice note recording started")

    def stop_voice_note(self):
        """Button 3 hold end: Stop recording and save voice note."""
        path = self._session.get_audio_path()
        if path and self._recorder.save_recording(path):
            logger.info(f"Voice note saved: {path}")
            if self._supabase and self._session.session_id:
                self._supabase.upload_file_background(
                    self._session.session_id, path, "audio"
                )
        else:
            logger.error("Voice note save failed")
