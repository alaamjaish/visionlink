"""
VisionLink Configuration
All non-secret settings live here. Secrets go in .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Paths ===
PROJECT_DIR = Path(__file__).parent
SESSIONS_DIR = Path.home() / "visionlink" / "sessions"
LOGS_DIR = Path.home() / "visionlink" / "logs"
SOUNDS_DIR = PROJECT_DIR / "sounds"

# Create dirs on import
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# === API Keys (from .env) ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# === Email ===
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")
SUPERVISOR_EMAIL = os.getenv("SUPERVISOR_EMAIL", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# === Camera ===
PHOTO_RESOLUTION = (1280, 720)  # 720p
VIDEO_RESOLUTION = (1280, 720)
VIDEO_MAX_DURATION = 30  # seconds
VIDEO_FPS = 30
PHOTO_FORMAT = "jpeg"
PHOTO_QUALITY = 85
AUTO_CAPTURE_INTERVAL = 30  # seconds, 0 to disable

# === Audio ===
AUDIO_SAMPLE_RATE = 16000  # For STT recording
AUDIO_CHANNELS = 1
AUDIO_CHUNK_SIZE = 1024
TTS_SAMPLE_RATE = 24000  # Gemini TTS outputs 24kHz PCM
# Recorder backend:
# - "auto": prefer ALSA arecord, fallback to PyAudio
# - "alsa": force arecord backend
# - "pyaudio": force PyAudio backend
AUDIO_BACKEND = os.getenv("AUDIO_BACKEND", "auto")
# ALSA device name from ~/.asoundrc; keep as "default" for stable routing.
AUDIO_INPUT_DEVICE = os.getenv("AUDIO_INPUT_DEVICE", "default")
# arecord format for ALSA backend.
AUDIO_ARECORD_FORMAT = os.getenv("AUDIO_ARECORD_FORMAT", "S16_LE")

# === Buttons (BCM GPIO pin numbers) ===
# Documentation mode
BTN_SESSION = 17       # Button 1: Start/Stop session
BTN_PHOTO_VIDEO = 27   # Button 2: Photo (single) / Video (double)
BTN_VOICE_NOTE = 22    # Button 3: Voice note (hold)

# AI Assistant mode
BTN_AI_CAMERA = 5      # Button 4: Camera QR + AI
BTN_AI_VOICE = 6       # Button 5: Voice Q&A
BTN_AI_AGENT = 13      # Button 6: Agent commands

ALL_BUTTONS = [BTN_SESSION, BTN_PHOTO_VIDEO, BTN_VOICE_NOTE,
               BTN_AI_CAMERA, BTN_AI_VOICE, BTN_AI_AGENT]

BUTTON_DEBOUNCE_MS = 300    # Software debounce
DOUBLE_PRESS_WINDOW = 0.5  # seconds

# === AI ===
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash-tts"
GEMINI_TTS_VOICE = "Kore"
AI_MEMORY_WINDOW = 30 * 60  # 30 minutes in seconds

# === Language ===
LANGUAGE = "en"  # "en" or "tr"

# === Error Handling ===
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

# === Supabase ===
SUPABASE_BUCKET = "sessions"

# === Logging ===
LOG_LEVEL = "DEBUG"  # DEBUG for dev, INFO for production
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per log file
LOG_BACKUP_COUNT = 5
