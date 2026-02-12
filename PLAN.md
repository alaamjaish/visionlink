# VisionLink - Implementation Plan

## Team
Alaa, Ali Salih, F-Alaa, Defne | Due: Mid-May 2026

## Build Strategy
Full skeleton first, then flesh out each part. MVP priority.

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project Setup (structure, config, logging) | DONE |
| 2 | Hardware Foundation (buttons, camera, audio) | SKELETON DONE |
| 3 | Cloud Integration (Supabase) | SKELETON DONE |
| 4 | AI Pipeline (STT, Gemini, TTS, QR) | SKELETON DONE |
| 5 | Subsystem Assembly (Doc mode, AI mode, Agent) | SKELETON DONE |
| 6 | Polish & Demo Prep | NOT STARTED |

## Current Focus
- Install dependencies and test hardware modules on Pi
- Set up Supabase project (tables + storage bucket)
- Research Soniox Python SDK (actual API calls)
- Test Gemini AI + TTS with real API key

## Architecture
```
main.py              # Entry point - wires everything together
config.py            # All settings (non-secret)
.env                 # Secrets (API keys, passwords)
src/
  hardware/
    buttons.py       # GPIO 6-button handler
    camera.py        # Pi Camera v3 (photo, video, frames)
    audio.py         # Microphone recording + speaker playback
  cloud/
    supabase_client.py  # Session CRUD + file upload
  ai/
    gemini.py        # Gemini AI (text + image queries)
    tts.py           # Gemini TTS (text -> speech)
    stt.py           # Soniox STT (speech -> text)
    qr_reader.py     # QR code scanner (pyzbar)
  subsystems/
    session_manager.py  # Session state machine
    documentation.py    # Doc mode (Buttons 1-3)
    assistant.py        # AI mode (Buttons 4-6)
  utils/
    logger.py        # Rotating file logger
    email_sender.py  # Gmail SMTP
```

## Key Decisions
- AI: Google Gemini (multimodal)
- TTS: gemini-2.5-flash-tts (PCM 16-bit 24kHz)
- STT: Soniox API
- DB: Supabase (PostgreSQL + Storage)
- Language: English & Turkish (configurable)
- Error: Retry 3x silently -> speak error -> LOG EVERYTHING
- Sessions: One at a time, stored at ~/visionlink/sessions/
- Upload: Background (non-blocking)
- Email: Gmail SMTP with app password
