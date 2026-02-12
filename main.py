#!/usr/bin/env python3
"""
VisionLink - Wearable Industrial Assistant
Main application entry point.

Initializes all modules, wires them together, and starts listening for button events.
"""

import signal
import sys
import time

# Ensure project root is on path
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

import config
from src.utils.logger import setup_logging, get_logger
from src.hardware.buttons import ButtonHandler
from src.hardware.camera import Camera
from src.hardware.audio import AudioPlayer, AudioRecorder
from src.cloud.supabase_client import SupabaseClient
from src.ai.gemini import GeminiAI
from src.ai.tts import TextToSpeech
from src.ai.stt import SpeechToText
from src.ai.qr_reader import QRReader
from src.utils.email_sender import EmailSender
from src.subsystems.session_manager import SessionManager
from src.subsystems.documentation import DocumentationMode
from src.subsystems.assistant import AssistantMode

logger = None


def main():
    global logger

    # === 1. Logging (FIRST - everything depends on this) ===
    setup_logging(log_dir=str(config.LOGS_DIR), level=config.LOG_LEVEL)
    logger = get_logger("main")
    logger.info("=" * 60)
    logger.info("VisionLink starting up...")
    logger.info("=" * 60)

    # === 2. Hardware ===
    logger.info("Initializing hardware...")

    audio_player = AudioPlayer()
    audio_player.setup()

    audio_recorder = AudioRecorder()
    audio_recorder.setup()

    camera = Camera()
    camera.setup()

    # === 3. Cloud ===
    logger.info("Initializing cloud services...")

    supabase = SupabaseClient()
    supabase.setup()

    email_sender = EmailSender()
    email_sender.setup()

    # === 4. AI ===
    logger.info("Initializing AI services...")

    gemini = GeminiAI()
    gemini.setup()

    tts = TextToSpeech()
    tts.setup()

    stt = SpeechToText()
    stt.setup()

    qr_reader = QRReader()

    # === 5. Subsystems ===
    logger.info("Initializing subsystems...")

    session_mgr = SessionManager(supabase_client=supabase)

    doc_mode = DocumentationMode(
        session_manager=session_mgr,
        camera=camera,
        audio_recorder=audio_recorder,
        audio_player=audio_player,
        supabase_client=supabase,
    )

    ai_mode = AssistantMode(
        camera=camera,
        audio_recorder=audio_recorder,
        audio_player=audio_player,
        gemini_ai=gemini,
        tts=tts,
        stt=stt,
        qr_reader=qr_reader,
        email_sender=email_sender,
    )

    # === 6. Buttons ===
    logger.info("Setting up buttons...")

    buttons = ButtonHandler(audio_player=audio_player)
    buttons.setup()

    # Documentation mode (Buttons 1-3)
    buttons.register(config.BTN_SESSION,
                     on_single=doc_mode.toggle_session)

    buttons.register(config.BTN_PHOTO_VIDEO,
                     on_single=doc_mode.take_photo,
                     on_double=doc_mode.toggle_video)

    buttons.register(config.BTN_VOICE_NOTE,
                     on_hold_start=doc_mode.start_voice_note,
                     on_hold_end=doc_mode.stop_voice_note)

    # AI Assistant mode (Buttons 4-6)
    buttons.register(config.BTN_AI_CAMERA,
                     on_single=ai_mode.camera_ai_query)

    buttons.register(config.BTN_AI_VOICE,
                     on_single=ai_mode.voice_qa)

    buttons.register(config.BTN_AI_AGENT,
                     on_single=ai_mode.agent_command)

    buttons.start_listening()

    # === 7. Startup announcement ===
    logger.info("VisionLink ready!")
    startup_msg = "VisionLink ready." if config.LANGUAGE == "en" else "VisionLink hazır."
    pcm = tts.synthesize(startup_msg)
    if pcm:
        audio_player.play_pcm(pcm)
    else:
        logger.warning("Startup TTS failed, trying beep instead")
        audio_player.play_beep()

    # === 8. Main loop (wait for signals) ===
    def shutdown(signum, frame):
        logger.info(f"Shutdown signal received ({signum})")
        buttons.cleanup()
        camera.cleanup()
        audio_player.cleanup()
        audio_recorder.cleanup()
        logger.info("VisionLink shut down cleanly")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Entering main loop - waiting for button events...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(signal.SIGINT, None)


if __name__ == "__main__":
    main()
