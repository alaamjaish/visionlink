"""
AI Assistant Subsystem

Buttons 4-6: Camera QR + AI, Voice Q&A, Agent commands.
"""

import time
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("ai_mode")


class AssistantMode:
    """AI Assistant subsystem controller (Buttons 4-6)."""

    def __init__(self, camera, audio_recorder, audio_player,
                 gemini_ai, tts, stt, qr_reader, email_sender):
        self._camera = camera
        self._recorder = audio_recorder
        self._player = audio_player
        self._gemini = gemini_ai
        self._tts = tts
        self._stt = stt
        self._qr = qr_reader
        self._email = email_sender

    def _speak_response(self, text: str):
        """Convert text to speech and play it."""
        pcm_data = self._tts.synthesize(text)
        if pcm_data:
            self._player.play_pcm(pcm_data)
        else:
            logger.error("TTS synthesis returned empty, cannot speak response")

    # === Button 4: Camera QR + AI ===

    def camera_ai_query(self):
        """Button 4: Capture image, scan for QR, send to AI with voice question."""
        logger.info("Camera AI query started")

        # Capture image
        frame = self._camera.capture_frame()
        if frame is None:
            self._speak_response("Camera not available.")
            return

        # Save frame as temp image for AI
        tmp_path = tempfile.mktemp(suffix=".jpg")
        try:
            import cv2
            cv2.imwrite(tmp_path, frame)
        except ImportError:
            logger.error("OpenCV not available for saving frame")
            self._speak_response("Image processing not available.")
            return

        # Scan for QR codes
        qr_results = self._qr.scan_frame(frame)
        qr_context = ""
        if qr_results:
            qr_context = f"QR code(s) found: {', '.join(qr_results)}. "
            logger.info(f"QR context: {qr_context}")

        # Record voice question
        self._speak_response("What is your question?")
        self._recorder.start_recording()
        time.sleep(5)  # Record for 5 seconds (or until button release in real usage)
        wav_data = self._recorder.stop_recording()

        # Transcribe
        question = self._stt.transcribe_bytes(wav_data)
        if not question:
            question = "What do you see in this image? Describe any machines, parts, or labels."

        # Query AI with image + text
        full_query = f"{qr_context}{question}"
        response = self._gemini.query_with_image(full_query, tmp_path)

        # Speak response
        self._speak_response(response)

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)
        logger.info("Camera AI query completed")

    # === Button 5: Voice Q&A ===

    def voice_qa(self):
        """Button 5: Record question, send to AI, speak answer."""
        logger.info("Voice Q&A started")

        self._speak_response("Listening.")

        # Record question
        self._recorder.start_recording()
        time.sleep(5)  # TODO: Replace with hold-to-talk or silence detection
        wav_data = self._recorder.stop_recording()

        # Transcribe
        question = self._stt.transcribe_bytes(wav_data)
        if not question:
            self._speak_response("I didn't catch that. Please try again.")
            logger.warning("Voice Q&A: empty transcription")
            return

        logger.info(f"Voice Q&A question: {question}")

        # Query AI (text only)
        response = self._gemini.query(question)

        # Speak response
        self._speak_response(response)
        logger.info("Voice Q&A completed")

    # === Button 6: Agent Commands ===

    def agent_command(self):
        """Button 6: Record command, parse intent, execute agent function."""
        logger.info("Agent command started")

        self._speak_response("What would you like me to do?")

        # Record command
        self._recorder.start_recording()
        time.sleep(5)
        wav_data = self._recorder.stop_recording()

        # Transcribe
        command = self._stt.transcribe_bytes(wav_data)
        if not command:
            self._speak_response("I didn't catch that.")
            return

        logger.info(f"Agent command: {command}")

        # Use AI to parse the command and determine action
        parse_prompt = f"""The worker said: "{command}"

Determine which action they want:
1. "report" - Generate a maintenance report
2. "notify" - Send notification to supervisor
3. "parts" - Request parts/materials

Respond with ONLY the action word (report, notify, or parts) and the details.
Format: ACTION: details"""

        ai_response = self._gemini.query(parse_prompt)
        logger.info(f"Agent parse result: {ai_response}")

        # Execute the appropriate action
        response_lower = ai_response.lower()
        if "report" in response_lower:
            self._handle_report(command)
        elif "notify" in response_lower:
            self._handle_notify(command)
        elif "parts" in response_lower:
            self._handle_parts_request(command)
        else:
            self._speak_response("I'm not sure what action to take. Please try again.")

    def _handle_report(self, context: str):
        """Generate and send a maintenance report."""
        logger.info("Generating maintenance report...")

        report_prompt = f"""Generate a brief maintenance report based on this worker's input: "{context}"
Include: Date, Description, Status, Recommended Action.
Keep it concise and professional."""

        report = self._gemini.query(report_prompt)

        if self._email.send_maintenance_report(report):
            self._speak_response("Maintenance report sent to supervisor.")
        else:
            self._speak_response("Failed to send report. Will retry later.")
            logger.error("Maintenance report email failed")

    def _handle_notify(self, message: str):
        """Send notification to supervisor."""
        logger.info(f"Sending notification: {message}")

        if self._email.notify_supervisor(f"Worker notification:\n\n{message}"):
            self._speak_response("Supervisor has been notified.")
        else:
            self._speak_response("Failed to send notification.")
            logger.error("Supervisor notification email failed")

    def _handle_parts_request(self, context: str):
        """Send parts request."""
        logger.info(f"Parts request: {context}")

        parts_prompt = f"""Format this as a parts request based on the worker's input: "{context}"
Include: Part name/description, Quantity (if mentioned), Urgency level.
Keep it concise."""

        parts_info = self._gemini.query(parts_prompt)

        if self._email.send_parts_request(parts_info):
            self._speak_response("Parts request sent to supervisor.")
        else:
            self._speak_response("Failed to send parts request.")
            logger.error("Parts request email failed")
