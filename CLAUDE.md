# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VisionLink is a wearable industrial assistant running on a **Raspberry Pi 4B (8GB)**. Two modes operated by 6 physical GPIO buttons:
- **Documentation Mode** (Buttons 1-3): Session management, photo/video capture, voice notes → uploaded to Supabase
- **AI Assistant Mode** (Buttons 4-6): QR scan + AI vision, voice Q&A, agent commands (email reports/notifications/parts requests)

This is an **MVP graduation project** (due mid-May 2026). Keep things simple and working end-to-end. See `AGENT_HANDOFF.md` for detailed phase status and next steps. See `UNANSWERED_QUESTIONS.md` for open items.

## Running

```bash
# Run the application
python3 main.py

# Production (systemd)
sudo cp visionlink.service /etc/systemd/system/
sudo systemctl enable --now visionlink

# Install dependencies
pip install -r requirements.txt

# Set up secrets
cp .env.example .env  # then fill in API keys
```

## Architecture

`main.py` is the single entry point. It instantiates all modules, injects dependencies via constructor, and wires button callbacks to subsystem methods. There is no framework — just a main loop that sleeps while GPIO interrupts fire callbacks on background threads.

**Data flow for AI query:** Button press → GPIO interrupt → `AssistantMode` method → `AudioRecorder` captures voice → `SpeechToText` (Soniox) → `GeminiAI` query → `TextToSpeech` (Gemini TTS, outputs PCM 16-bit 24kHz) → `AudioPlayer` converts to WAV and plays through I2S amp.

**Data flow for documentation:** Button press → `DocumentationMode` → `SessionManager` creates local dirs under `~/visionlink/sessions/{uuid}/` → `Camera` captures media → `SupabaseClient.upload_file_background()` uploads in daemon thread.

All settings in `config.py`. All secrets in `.env` (loaded via python-dotenv). Every module uses `from src.utils.logger import get_logger` — this is critical since the device is headless.

## Hardware

- **Camera:** Pi Camera Module 3 (CSI ribbon, uses `picamera2`)
- **Microphone:** SPH0645LM4H I2S MEMS (GPIO 18/19/20)
- **Amplifier:** MAX98357A I2S mono (GPIO 18/19/21, shares clock with mic)
- **Speaker:** 8 Ohm 1W mini oval, wired to amplifier
- **Buttons:** 6x tactile on GPIO 17, 27, 22, 5, 6, 13

See `HARDWARE_CONNECTION.md` for full wiring and pin map.

**Important:** Both mic and amp are I2S (not USB). `audio.py` currently uses PyAudio and needs rewriting to use `sounddevice` or `alsaaudio`. ALSA configuration (`~/.asoundrc`) is required.

## Key Patterns

- **Graceful degradation:** Every hardware module wraps its import in try/except and sets a `HAS_*` flag. Methods check the flag and log a warning instead of crashing. This lets the code run (partially) on non-Pi machines for development.
- **Background uploads:** All Supabase file uploads run in daemon threads via `upload_file_background()` so button responsiveness is never blocked.
- **Button callbacks:** `ButtonHandler.register()` supports `on_single`, `on_double` (500ms window), `on_hold_start`/`on_hold_end`. All callbacks fire in separate daemon threads.
- **AI memory:** `GeminiAI` maintains a conversation history list pruned to a 30-minute sliding window (`config.AI_MEMORY_WINDOW`).

## Logging Policy

This device has **no monitor**. Logs are the only debugging method. Log location: `~/visionlink/logs/visionlink.log` (rotating, 10MB x 5 files). Every button press, API call (with timing), error (with traceback), session state change, and file operation must be logged. Use `get_logger("module_name")` — loggers are prefixed with `vl.`.

## Known Blockers

- `src/ai/stt.py` is a **stub** — Soniox SDK API calls not implemented yet
- Supabase project not created — no URL/keys in `.env`
- I2S device tree overlay not yet determined (candidates: `googlevoicehat-soundcard`, `hifiberry-dac`)
