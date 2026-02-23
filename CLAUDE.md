# CLAUDE.md — VisionLink Master Context

This file tells any AI agent EVERYTHING about this project, the developer, the hardware, and the current status. Read this FIRST. Then you can help immediately without asking 50 questions.

---

## WHO IS THE DEVELOPER

- A small team of students: **Alaa, Ali Salih, F-Alaa, Defne**
- This is a **graduation project** due **mid-May 2026**
- The main developer (you're talking to) is **not deeply technical** — explain things simply, avoid jargon, be patient and chatty
- They are learning as they go — treat them like a smart beginner
- They work on a **Raspberry Pi 4B** physically in front of them (headless — no monitor most of the time)
- They also connect to the Pi remotely from **Windows** via VS Code Remote SSH
- They have **Claude Code** running on the Pi terminal
- Current date context: **February 2026**

## COMMUNICATION STYLE

- Be chatty, encouraging, and clear
- Use simple language — no unnecessary technical jargon
- When giving hardware instructions, be VERY specific (pin numbers, wire colors, step-by-step)
- When something can break the hardware, WARN LOUDLY
- The developer prefers checklists and step-by-step instructions over long paragraphs
- They want to feel confident, not overwhelmed

---

## WHAT IS VISIONLINK

VisionLink is a **wearable industrial assistant** running on a **Raspberry Pi 4B (8GB RAM)**. Think of it as smart glasses (or a helmet attachment) for factory workers. It has two modes:

### Documentation Mode (Buttons 1-3)
Workers document their shifts hands-free:
- **Button 1** — Start/Stop a work session (creates a timestamped folder, syncs to cloud)
- **Button 2** — Take photo (single press) or record video (double press)
- **Button 3** — Record voice note (hold to record, release to stop)
- Everything uploads to **Supabase** (PostgreSQL + file storage) in background threads

### AI Assistant Mode (Buttons 4-6)
Workers get AI help hands-free:
- **Button 4** — Point camera at something (or QR code) + ask a question → AI sees the image and answers via speaker
- **Button 5** — Voice Q&A (ask anything, AI answers through speaker)
- **Button 6** — Agent commands ("send a report to supervisor", "request spare part X") → AI parses and executes via email

### The Big Picture Data Flow
```
Button press → GPIO interrupt → Python callback (background thread)
  → Camera/Mic captures input
  → Cloud API processes it (Gemini AI / Soniox STT / Supabase)
  → Speaker outputs the result (via Gemini TTS → I2S amp)
```

---

## HARDWARE — WHAT WE HAVE

| Component | Model | Interface | Status |
|-----------|-------|-----------|--------|
| Computer | Raspberry Pi 4B, 8GB RAM | — | Working |
| Camera | Pi Camera Module 3 | CSI ribbon cable | Connected |
| Microphone | SPH0645LM4H (GY-SPH0645 board) | I2S digital (GPIO wires) | Wired, not software-tested |
| Amplifier | MAX98357A | I2S digital (GPIO wires) | Wired, not software-tested |
| Speaker | 8 Ohm 1W mini oval (Adafruit-style) | Screw terminals on amp | Connected to amp |
| Buttons | 2x tactile 4-leg push buttons | GPIO pins | Wired (only 2 of 6 — see below) |
| Power | USB-C power supply / powerbank | USB-C | Working |

### CRITICAL: Only 2 Buttons Connected Right Now
We only have 2 physical buttons at the moment (not 6). They are wired as:
- **Button 1** (Session Start/Stop) → GPIO 17 (Pin 11)
- **Button 2** (Photo/Video) → GPIO 27 (Pin 13)
- Both buttons share **GND on Pin 20**

Buttons 3-6 are NOT connected. The code references all 6 — when those buttons are missing, the app should still work (graceful degradation). The remaining 4 buttons will be added later when hardware is purchased.

### GPIO Pin Map — What's Currently Wired

```
Pi GPIO Header (USB ports at bottom-right, Pin 1 = top-left corner)

LEFT SIDE (odd)              RIGHT SIDE (even)
═══════════════              ════════════════
Pin 1  ← Mic 3V (3.3V)      Pin 2  ← Amp Vin (5V)
Pin 3                        Pin 4
Pin 5                        Pin 6  ← Mic GND
Pin 7                        Pin 8
Pin 9  ← Amp GND            Pin 10
Pin 11 ← BUTTON 1 (GPIO17)  Pin 12 ← Amp BCLK + Mic BCLK (GPIO18)
Pin 13 ← BUTTON 2 (GPIO27)  Pin 14
Pin 15   (future BTN3)      Pin 16
Pin 17                       Pin 18
Pin 19                       Pin 20 ← Buttons GND (shared)
...
Pin 29   (future BTN4)      Pin 30
Pin 31   (future BTN5)      Pin 32
Pin 33   (future BTN6)      Pin 34
Pin 35 ← Amp LRC + Mic LRCLK (GPIO19)  Pin 36
Pin 37                       Pin 38 ← Mic DOUT (GPIO20)
Pin 39 ← Mic SEL (GND)      Pin 40 ← Amp DIN (GPIO21)
```

### I2S Audio — Important Detail
Both the microphone and amplifier are **I2S** (digital audio over GPIO), NOT USB audio. They **share clock lines** (BCLK on GPIO 18, LRCLK on GPIO 19) but have separate data lines (Mic DOUT = GPIO 20, Amp DIN = GPIO 21). This means:
- `audio.py` needs to use `sounddevice` or `alsaaudio` (NOT PyAudio)
- ALSA must be configured (`~/.asoundrc`) with the correct device tree overlay
- The correct overlay is still uncertain: `googlevoicehat-soundcard` vs `hifiberry-dac`

### Speaker Wiring
Speaker red wire → amp **+** screw terminal, black wire → amp **-** screw terminal. Already done.

---

## SOFTWARE — CURRENT STATE

### Project Location
```
~/Desktop/visionlink/
```

### Architecture
```
main.py              ← Single entry point, wires everything together
config.py            ← ALL settings (GPIO pins, intervals, model names, paths)
.env                 ← Secrets (API keys) — NOT committed to git
.env.example         ← Template for .env
requirements.txt     ← Python dependencies
visionlink.service   ← systemd unit for auto-start on boot

src/
  hardware/
    buttons.py       ← GPIO 6-button handler (debounce, double-press, hold)
    camera.py        ← Pi Camera v3 via picamera2 (photo, video, frames)
    audio.py         ← Recording + playback (NEEDS I2S REWRITE)
  cloud/
    supabase_client.py ← Session CRUD + background file uploads
  ai/
    gemini.py        ← Google Gemini AI (text + image, 30-min memory window)
    tts.py           ← Gemini TTS (text → PCM 16-bit 24kHz)
    stt.py           ← Soniox STT (STUB — not implemented yet)
    qr_reader.py     ← QR code scanner via pyzbar
  subsystems/
    documentation.py ← Documentation mode logic (Buttons 1-3)
    assistant.py     ← AI assistant mode logic (Buttons 4-6)
    session_manager.py ← Session state machine (idle ↔ active)
  utils/
    logger.py        ← Rotating file logger (10MB x 5 files)
    email_sender.py  ← Gmail SMTP for agent commands
```

### How main.py Works
1. Sets up logging (to `~/visionlink/logs/visionlink.log`)
2. Initializes all hardware modules (camera, audio, buttons)
3. Initializes cloud services (Supabase, email)
4. Initializes AI services (Gemini, TTS, STT, QR reader)
5. Creates subsystems (DocumentationMode, AssistantMode) with dependency injection
6. Registers button callbacks (e.g., Button 1 single-press → `doc_mode.toggle_session`)
7. Plays startup announcement via TTS
8. Enters infinite loop waiting for GPIO interrupts

### Running the App
```bash
cd ~/Desktop/visionlink
python3 main.py

# Or via systemd (production):
sudo cp visionlink.service /etc/systemd/system/
sudo systemctl enable --now visionlink
```

### Key Runtime Paths
- Logs: `~/visionlink/logs/visionlink.log`
- Sessions: `~/visionlink/sessions/{uuid}/`
- Sounds: `~/Desktop/visionlink/sounds/`

---

## API KEYS & SERVICES

| Service | Purpose | Status | Config Key |
|---------|---------|--------|------------|
| Google Gemini | AI (vision + text) | API key obtained | `GEMINI_API_KEY` |
| Gemini TTS | Text-to-speech | Same key as Gemini | (uses `GEMINI_API_KEY`) |
| Soniox | Speech-to-text | API key obtained | `SONIOX_API_KEY` |
| Supabase | Database + file storage | Project created, keys obtained | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |
| Gmail SMTP | Email for agent commands | Needs app password | `SMTP_EMAIL`, `SMTP_APP_PASSWORD` |

The developer says all API keys are ready and obtained. They should be in `.env`.

---

## BUILD PHASES & PROGRESS

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project Setup (structure, config, logging) | DONE |
| 2 | Hardware Foundation (buttons, camera, audio) | SKELETON DONE — hardware now physically wired |
| 3 | Cloud Integration (Supabase) | SKELETON DONE — Supabase project created |
| 4 | AI Pipeline (STT, Gemini, TTS, QR) | SKELETON DONE — API keys obtained |
| 5 | Subsystem Assembly (Doc mode, AI mode) | SKELETON DONE |
| 6 | Polish & Demo Prep | NOT STARTED |

### What "Skeleton Done" Means
All Python files exist with the right class structure, method signatures, imports, and logging. But most have NOT been tested with real hardware or real API calls yet. They use graceful degradation (`HAS_PICAMERA`, `HAS_GPIO`, etc.) so the code doesn't crash when hardware libraries are missing.

---

## WHAT NEEDS TO HAPPEN NEXT (in order)

### Immediate — Hardware Verification
1. Configure I2S audio on the Pi (`/boot/firmware/config.txt` overlay + `~/.asoundrc`)
2. Test camera: `libcamera-hello --timeout 5000`
3. Test speaker: `speaker-test -t wav -c 1`
4. Test microphone: `arecord -D plughw:1,0 -f S32_LE -r 16000 -c 1 -d 5 test.wav`
5. Test 2 buttons with a simple GPIO script

### Short-term — Get Each Module Working
6. Rewrite `audio.py` for I2S (replace PyAudio with sounddevice/alsaaudio)
7. Test Gemini AI with real API key (text query)
8. Test Gemini TTS (synthesize → play through speaker)
9. Research & implement Soniox STT (`stt.py` is currently a stub)
10. Test Supabase: create session, upload file

### Medium-term — End-to-End Flows
11. Documentation flow: Button 1 → session starts → Button 2 → photo → Button 1 → session ends → upload
12. AI flow: Button 5 → record question → transcribe → AI → TTS → speaker
13. Agent flow: Button 6 → record command → parse → send email

### Final — Demo Prep
14. Buy remaining 4 buttons and wire them
15. Startup voice announcement
16. Error handling & retry
17. QR codes for demo
18. systemd auto-start
19. Full demo walkthrough

---

## KNOWN BLOCKERS & ISSUES

| Issue | Severity | Details |
|-------|----------|---------|
| `audio.py` uses PyAudio | HIGH | Must be rewritten for I2S. Need `sounddevice` or `alsaaudio` |
| `stt.py` is a stub | HIGH | Soniox SDK API calls not implemented. Need to research the Python SDK |
| I2S overlay unknown | MEDIUM | Need to test which overlay works: `googlevoicehat-soundcard` vs `hifiberry-dac` |
| Only 2 buttons | LOW | 4 more buttons need to be purchased. Code handles missing buttons gracefully |
| ALSA config needed | MEDIUM | `~/.asoundrc` must be created for I2S mic/speaker routing |

---

## KEY DESIGN PATTERNS

- **Graceful degradation:** Every hardware module wraps imports in try/except, sets `HAS_*` flags. Methods check flags and log warnings instead of crashing. This lets code run partially on non-Pi machines.
- **Background uploads:** Supabase file uploads run in daemon threads via `upload_file_background()`. Never blocks button responsiveness.
- **Button callbacks:** `ButtonHandler.register()` supports `on_single`, `on_double` (500ms window), `on_hold_start`/`on_hold_end`. All fire in daemon threads.
- **AI memory:** `GeminiAI` keeps conversation history pruned to a 30-minute sliding window.
- **Dependency injection:** `main.py` creates all objects and passes them to subsystems via constructor args. No globals, no singletons.
- **One session at a time:** `SessionManager` enforces single active session.
- **Retry pattern:** 3 silent retries → speak error message → log everything.

## LOGGING POLICY

This device is **headless** (no monitor). Logs are the ONLY debugging tool.
- Location: `~/visionlink/logs/visionlink.log` (rotating, 10MB x 5 files)
- Every button press, API call (with timing), error (with traceback), session state change, and file operation MUST be logged
- Use `get_logger("module_name")` — all loggers prefixed with `vl.`

## CODING STANDARDS

- Python 3, PEP 8, 4-space indent
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for config constants
- Type hints encouraged, docstrings for public methods
- Keep it simple — this is an MVP. Don't over-engineer.
- All settings in `config.py`, all secrets in `.env`
- Tests go in `tests/test_*.py`, mock hardware/network calls

---

## KEY TECHNICAL DECISIONS

| Decision | Choice | Why |
|----------|--------|-----|
| AI Model | Google Gemini (gemini-2.5-flash) | Multimodal (text + image), fast, affordable |
| TTS | Gemini TTS (gemini-2.5-flash-tts) | Same ecosystem, PCM output, voice "Kore" |
| STT | Soniox | Accurate, supports streaming (future) |
| Database | Supabase | PostgreSQL + file storage + free tier |
| Language | English (configurable to Turkish) | `config.LANGUAGE = "en"` or `"tr"` |
| Audio I/O | I2S (not USB) | Better quality, lower latency, more compact for wearable |
| Email | Gmail SMTP with app password | Simple, reliable for MVP |

---

## OTHER IMPORTANT FILES

| File | What It Contains |
|------|-----------------|
| `PLAN.md` | Implementation plan with phases and architecture diagram |
| `AGENT_HANDOFF.md` | Detailed phase status, next steps, and rules for development |
| `HARDWARE_CONNECTION.md` | Full wiring guide with pin diagrams for every component |
| `SPECS.md` | Original project specification (bilingual Turkish/English) |
| `AFTER_MVP.md` | Feature wishlist for after MVP works |
| `UNANSWERED_QUESTIONS.md` | Open questions about Soniox, TTS, hardware, demo |
| `AGENTS.md` | Repository guidelines, coding style, commit conventions |

---

## QUICK START FOR A NEW AI SESSION

If you're a new AI agent reading this for the first time:

1. The project is at `~/Desktop/visionlink/`
2. The developer has hardware physically connected (camera, mic, amp+speaker, 2 buttons)
3. API keys are obtained (Gemini, Soniox, Supabase)
4. The code skeleton is complete but mostly untested on real hardware
5. Next step is: configure I2S audio on the Pi, then test each hardware piece
6. Be patient, be clear, give step-by-step instructions
7. This is an MVP — keep things simple and working
8. When in doubt, read `AGENT_HANDOFF.md` for the detailed status
