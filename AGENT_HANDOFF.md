# VisionLink - Agent Handoff Document

**Purpose:** This file tells any future AI agent exactly where we are, what's been done, what's next, and where to find everything.

---

## Critical Update (2026-02-24): Audio Debug Completed

- Read this first: `AUDIO_DEBUG_HANDOFF_2026-02-24.md`
- I2S speaker + mic are now both working on `googlevoicehat-soundcard`
- App recorder was updated to auto-use ALSA/`arecord` backend
- New one-command audio checks are in `Makefile` (`make audio-capture`, etc.)

---

## What Is This Project?

VisionLink is a **wearable industrial assistant** running on a Raspberry Pi 4B. It has two modes:

1. **Documentation Mode** (Buttons 1-3): Workers start a session, capture photos/videos, record voice notes. Everything uploads to Supabase.
2. **AI Assistant Mode** (Buttons 4-6): Workers scan QR codes, ask voice questions, and give agent commands (reports, notifications, parts requests). AI responds via speaker.

**This is a graduation project** for a team of 4 (Alaa, Ali Salih, F-Alaa, Defne). **Due mid-May 2026.** We are building an MVP - keep it simple, make it work end-to-end.

---

## Where We Are (Phase Status)

### Phase 1: Project Setup - COMPLETE
- Project structure created
- Config system (config.py + .env)
- Logging framework (rotating file handler)
- requirements.txt, .gitignore, systemd service file
- Git repo initialized

### Phase 2: Hardware Foundation - SKELETON COMPLETE, NOT TESTED
- buttons.py: GPIO handler with debounce, double-press, hold detection
- camera.py: picamera2 wrapper for photo/video/frames
- audio.py: Recording + playback (NEEDS UPDATE for I2S - see below)
- **Hardware is NOT connected yet** - see `HARDWARE_CONNECTION.md`

### Phase 3: Cloud Integration - SKELETON COMPLETE, NOT CONNECTED
- supabase_client.py: Session CRUD + background file upload
- **Supabase project not created yet** - need URL + service key

### Phase 4: AI Pipeline - SKELETON COMPLETE, NOT TESTED
- gemini.py: Multimodal queries with 30-min history window
- tts.py: Gemini TTS (PCM 16-bit 24kHz → WAV)
- stt.py: **STUB ONLY** - Soniox SDK needs research
- qr_reader.py: pyzbar QR scanner

### Phase 5: Subsystem Assembly - SKELETON COMPLETE
- documentation.py: Buttons 1-3 logic wired up
- assistant.py: Buttons 4-6 logic wired up
- session_manager.py: Session state machine

### Phase 6: Polish & Demo Prep - NOT STARTED

---

## What Needs To Happen Next (In Order)

### Immediate (Before any code works)

1. **Connect the hardware** - Follow `HARDWARE_CONNECTION.md`
   - Camera (CSI ribbon)
   - MAX98357A amplifier + speaker (I2S)
   - SPH0645LM4H microphone (I2S)
   - 6 buttons (GPIO)

2. **Configure I2S audio on the Pi**
   - Edit `/boot/firmware/config.txt` for I2S overlays
   - Create `~/.asoundrc` for ALSA routing
   - Test mic: `arecord` → test speaker: `aplay`

3. **Update audio.py for I2S**
   - Current code uses PyAudio which assumes USB/analog audio
   - I2S needs ALSA-based approach: `sounddevice` or `alsaaudio` library
   - Update requirements.txt accordingly

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up .env file**
   ```bash
   cp .env.example .env
   nano .env
   # Fill in: GEMINI_API_KEY, SONIOX_API_KEY
   ```

### Short-term (Get each module working)

6. **Test camera module** - take a photo, record video
7. **Test buttons** - press each one, verify log output + beeps
8. **Test Gemini AI** - send a text query, get response
9. **Test Gemini TTS** - synthesize speech, play through speaker
10. **Research & implement Soniox STT** - this is the biggest unknown
11. **Create Supabase project** - tables + storage bucket
12. **Test Supabase uploads** - create session, upload a file

### Medium-term (End-to-end flows)

13. **Documentation flow**: Button 1 → session starts → Button 2 → photo taken → Button 1 → session ends → files upload
14. **AI flow**: Button 5 → record question → transcribe → AI responds → speak answer
15. **Agent flow**: Button 6 → record command → parse → send email

### Final (Demo prep)

16. Startup voice announcement
17. Error handling & retry logic
18. Prepare QR codes and demo scenario
19. systemd auto-start for production
20. Full end-to-end demo walkthrough

---

## Key Files Reference

| File | What It Does |
|------|-------------|
| `main.py` | Entry point - initializes everything, wires buttons to actions |
| `config.py` | All settings (GPIO pins, intervals, model names, paths) |
| `.env` | Secrets (API keys, Supabase credentials, email password) |
| `PLAN.md` | Implementation plan with architecture overview |
| `UNANSWERED_QUESTIONS.md` | Open questions that need answers |
| `AFTER_MVP.md` | Features to add after MVP works |
| `HARDWARE_CONNECTION.md` | Physical wiring guide for all components |
| `SPECS.md` | Original project specification (Turkish) |
| `visionlink.service` | systemd unit file for auto-start |

---

## Known Issues & Blockers

### audio.py needs I2S rewrite
The current audio module uses PyAudio which expects USB/analog audio. Our hardware uses **I2S** (SPH0645LM4H mic + MAX98357A amp). The recording code needs to be updated to use `sounddevice` or `alsaaudio` instead. Playback via pygame should still work if ALSA is configured correctly.

### Soniox STT is a stub
`src/ai/stt.py` has the structure but NO actual API calls. The Soniox Python SDK needs research:
- What's the correct import?
- How do you send audio and get text back?
- Does it support Turkish?
- What audio format does it expect?

### Supabase not created
No Supabase project exists yet. Need to:
1. Create project at supabase.com
2. Create `sessions` table (see schema in PLAN.md)
3. Create `sessions` storage bucket
4. Get URL + service key → put in .env

### I2S overlay uncertainty
Both mic and amp are I2S and share clock pins. The right device tree overlay needs testing. Options:
- `googlevoicehat-soundcard` (designed for similar setups)
- `hifiberry-dac` + `i2s-mmap` (separate overlays)
- Custom overlay

---

## Architecture Quick Reference

```
main.py
  ├── Logging (logger.py)
  ├── Hardware
  │     ├── AudioPlayer (audio.py) → pygame/ALSA → MAX98357A → Speaker
  │     ├── AudioRecorder (audio.py) → ALSA → SPH0645LM4H mic
  │     ├── Camera (camera.py) → picamera2 → Pi Camera Module 3
  │     └── ButtonHandler (buttons.py) → RPi.GPIO → 6 physical buttons
  ├── Cloud
  │     └── SupabaseClient (supabase_client.py) → Supabase API
  ├── AI
  │     ├── GeminiAI (gemini.py) → Google Gemini API
  │     ├── TextToSpeech (tts.py) → Gemini TTS API
  │     ├── SpeechToText (stt.py) → Soniox API
  │     └── QRReader (qr_reader.py) → pyzbar
  ├── Subsystems
  │     ├── SessionManager → state machine (idle/active)
  │     ├── DocumentationMode → Buttons 1-3
  │     └── AssistantMode → Buttons 4-6
  └── Utils
        └── EmailSender (email_sender.py) → Gmail SMTP
```

---

## Rules For Future Development

1. **LOG EVERYTHING** - No monitor on this device. Logs at `~/visionlink/logs/`
2. **MVP first** - Don't over-engineer. Make it work, then make it better.
3. **Test each piece alone** before combining
4. **Graceful degradation** - Every hardware module checks if its library exists
5. **Background uploads** - Never block the main thread for cloud operations
6. **Retry silently** - 3 attempts, then speak a calm error message
7. **One session at a time** - No concurrent sessions
8. **Keep config.py updated** - All settings in one place
