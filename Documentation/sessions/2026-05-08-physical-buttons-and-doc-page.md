# Session Log — 2026-05-08 (physical GPIO bridge + Documentation page + B1/B2/B3 wiring bug)

**Branch:** `openai-sdk`
**Hardware:** Raspberry Pi 4B (8GB RAM), Debian 13 (Trixie), kernel 6.12.47-rpt-rpi-v8 aarch64
**Theme:** Get the physical wearable buttons firing into the running system, build a supervisor "Documentation" page so B1/B2/B3 captures are actually visible, and root-cause why three of the six physical buttons refuse to fire.

---

## TL;DR

- **GPIO sidecar built** (`scripts/gpio_bridge.py`) — physical button presses now translate into the same `/api/button/{n}/{event}` HTTP calls the on-screen 6-button simulator uses. Reuses the existing `ButtonHandler` (debounce + double-press + hold polling).
- **Debounce tuned** in `config.py` from 300 ms → 50 ms. The old value ate two-thirds of the 500 ms double-click window — physical doubles were almost impossible. New value leaves a 450 ms valid zone (more forgiving than the browser simulator's 350 ms).
- **New ops page at `/documentation`** with Sessions panel + Captures panel. Photos open in a modal, videos play inline, voice notes get audio controls. Realtime via Supabase, no refresh.
- **Top-of-page nav** switches between **Agent** (existing Command Center at `/`) and **Documentation**, with active highlight via `usePathname`.
- **B3 vs AI guard** — voice notes refuse to start while a B4/B5 AI session is holding the mic. Avoids silent corruption from two consumers fighting over the I2S bridge.
- **SOS auto-close** — when B6 SOS arms, any open documentation session is automatically closed. Worker isn't doing paperwork in an emergency.
- **B2 video fixed** — rewrote `b2_record_video` to call `rpicam-vid --codec libav` directly, producing MP4 in one shot. The legacy `capture_av_mp4.sh` muxed audio via parallel `arecord`, which always failed with EBUSY because audio_worker holds the I2S mic exclusively. Video is silent for now; audio mux via AudioBridge is a TODO.
- **B4/B5/B6 (GPIO 5/6/13) physical buttons work end-to-end.** 28+ kernel-confirmed presses logged.
- **B1/B2/B3 (GPIO 17/27/22) physical buttons silent throughout the session.** `/proc/interrupts` shows zero edges on those pins after 48 minutes of bridge runtime. Three independent sub-agents (fresh contexts, different angles) converged on the same verdict: every layer of pi-side software is bit-for-bit identical between the working trio and the broken trio — the failure is downstream of the SoC pad (wiring / breadboard / button leg).
- **End-of-session breakthrough**: user audited the breadboard wires against the GPIO header and discovered **two wires plugged into power pins instead of GPIO pins** — Pin 17 (3.3 V) and Pin 4 (5 V). That fully explains the silence: pressing those buttons shorts the GPIO line to a power rail, not to GND, so the pin never goes LOW and the kernel never sees a falling edge. Fix is purely physical: rewire each of B1/B2/B3 with one leg on the correct GPIO pin and the diagonal leg on a GND pin.

---

## What we built today

### `scripts/gpio_bridge.py` — the sidecar
Pure additive — does not touch the dashboard process. Imports `RPi.GPIO`, sets pins 17/27/22/5/6/13 as `INPUT` with `PUD_UP`, registers `add_event_detect(GPIO.FALLING, bouncetime=50)` for each, and on every gesture (single / double / hold_start / hold_end) does a `requests.post` to `/api/button/{n}/{event}`. Logs to `/tmp/vl_bridge.log` line-by-line for live diagnosis.

Reuses `src/hardware/buttons.py::ButtonHandler` so debounce, 500 ms double-press window, and hold polling are exactly the original logic — no parallel implementation to maintain.

Run as a separate process in a second terminal:
```bash
cd ~/Desktop/visionlink
python3 scripts/gpio_bridge.py
```

If anything goes wrong the bridge is killable with Ctrl+C; the dashboard is unaffected. The `visionlink` user is already in the `gpio` group, so no sudo needed.

### `config.py` — debounce
`BUTTON_DEBOUNCE_MS = 300 → 50`. Math:
- `bouncetime` blocks any further interrupt on the same pin for that long after a press.
- `DOUBLE_PRESS_WINDOW = 0.5 s` is the total window for press 2 to land.
- Old: press 2 had to land between 300 ms and 500 ms = **200 ms valid window**.
- New: press 2 has to land between 50 ms and 500 ms = **450 ms valid window**.

Verified live: `B4 single` followed by `B4 double` 4 s later, both detected correctly. Bridge log line at 02:28:59 (this session).

### `ops/src/app/documentation/page.tsx` — the new supervisor page
Client-rendered. Subscribes to `sessions` and `session_assets` via the existing `useRealtimeRows` hook. Computes a stats row (sessions / open / photos / videos / voice notes / orphans) and hands the data down to two presentational panels.

### `ops/src/components/sections/SessionsPanel.tsx`
Newest sessions first. Open ones glow green. Each row: worker, started/ended time, duration, asset counts (📷 N, 🎬 N, 🎙 N). Click a row → expands inline to list the assets in that session.

### `ops/src/components/sections/CapturesPanel.tsx`
Tabbed grid (All / Photos / Videos / Voice notes / Orphans). Photos render as click-to-zoom thumbnails (modal preview). Videos use `<video controls>`. Voice notes use `<audio controls>`. URLs come from `supabase.storage.from('session-assets').getPublicUrl(...)` — the bucket is public, no signing required.

Each card shows the parent session label or an "orphan" pill if `session_id` is null.

### `ops/src/components/Nav.tsx`
Adds two pill-tabs in the top bar: **Agent** (`/`) and **Documentation** (`/documentation`). Active tab highlighted via `usePathname()`. Logo on the left, realtime indicator on the right — same layout, just two new pills in the middle.

### `src/subsystems/button_handlers.py` — three patches

**B3 guard** in `b3_voice_note_start`:
```python
if is_ai_session_running and is_ai_session_running():
    await log("voice note BLOCKED — AI session is using the mic", "warning")
    return {"error": "AI session active — cannot record voice note"}
```
Caller (in `dashboard/server.py`) injects a small `_ai_running()` lambda that returns true if `live_task` or `oai_task` are still running. Verified: pressing B3 while an OpenAI session is open returns the explicit error; after `B4 double` to stop the session, B3 records normally.

**SOS auto-close** in `b6_sos_trigger` — new helper `_sos_auto_close_open_session(sos_id, log, broadcast)`:
- Reads `_state.open_session_id` under the lock
- If set, updates the row to `status='closed', ended_at=now()` in Supabase
- Clears the in-memory state
- Broadcasts `{"type": "session_auto_closed", "session_id": ..., "reason": "sos", "sos_id": ...}` so the UI can react

Spawned as `asyncio.create_task` so SOS startup isn't blocked. Verified: opened session → triggered SOS → DB confirms session was auto-closed within ~1 s.

**B2 video** — rewrote to bypass `capture_av_mp4.sh` entirely:
```python
cmd = [
    "rpicam-vid",
    "-o", out_path,
    "--width", "1280", "--height", "720", "--framerate", "30",
    "--codec", "libav", "--libav-format", "mp4",
    "-t", str(duration_ms),
    "-n",
]
```
The legacy script's audio side (`arecord`) always failed because the I2S mic is held exclusively by audio_worker. `rpicam-vid --codec libav` produces an MP4 in one subprocess invocation, no audio. Verified: 5 s capture → 119 KB MP4 → uploaded to Supabase storage → row in `session_assets`.

### `dashboard/server.py` — wiring the B3 guard
The `(3, "hold_start")` dispatch now constructs an `_ai_running()` callable referencing the dashboard's `live_task` and `oai_task` globals and passes it to `bh.b3_voice_note_start`. Everything else in the dispatch is unchanged.

---

## The B1/B2/B3 mystery — how we caught it

When physical buttons started failing in pairs (B1/B2/B3 silent while B4/B5/B6 worked perfectly), the user asked for three independent investigation agents in parallel — fresh contexts, different angles, strict read-only rules.

**Agent 1 — Live kernel-edge verification.** Used `/proc/interrupts` (the kernel's authoritative count of every electrical edge per IRQ line) since `gpiomon` would conflict with the active bridge requests. Found:

```
60: pinctrl-bcm2835  17  Edge  lg   count=0
61: pinctrl-bcm2835  27  Edge  lg   count=0
62: pinctrl-bcm2835  22  Edge  lg   count=0
63: pinctrl-bcm2835   5  Edge  lg   count=37
64: pinctrl-bcm2835   6  Edge  lg   count=40
65: pinctrl-bcm2835  13  Edge  lg   count=50
```

Interrupts are correctly registered for all six pins. The "good" pins counted up. The "bad" pins stayed at zero. **The kernel never saw a falling edge on GPIO 17/22/27.** That puts the failure upstream of any software.

**Agent 2 — Pi software / driver / overlay forensics.** Compared `pinctrl get`, `gpioinfo`, `pinconf-pins`, `pinmux-pins`, `dmesg`, `vcgencmd get_config`, `lsmod`, the loaded device-tree, and the `googlevoicehat-soundcard` overlay. Result: every layer of pi-side configuration is bit-for-bit symmetric between the two trios. JTAG explicitly off (`enable_jtag_gpio=0`). Audio overlay only claims GPIO 16 + I2S pins 18-21 — does not touch 17/22/27. No driver consumer claim. Conclusion: "downstream of the SoC pad."

**Agent 3 — Project hardware history.** Read CLAUDE.md, HARDWARE_CONNECTION.md, every session log, git log on `config.py`. Found:
- B1/B2/B3 have **never** been confirmed working in any document, log, or commit.
- Pin map has not changed since the original commit.
- CLAUDE.md (lines 67–99, written 2026-02-23) reveals B1 + B2 were the **first two** buttons soldered, sharing GND on Pin 20. B3 was added later. B4/B5/B6 were added later still and almost certainly use a **different** GND pin (likely Pin 34 near GPIO 5/6/13).
- "Identical buttons" doesn't mean "identical wiring path" — and the docs strongly imply two separate breadboard areas with two separate GND returns.

All three agents converged on the same verdict: **wiring fault on the B1/B2/B3 side, not software.**

---

## The bug we caught (root cause)

After the three agents reported, the user audited the physical breadboard against the GPIO header pinout and counted positions in the OUTER (odd) column:

| Wire was at | What that pin actually is | Should have been at |
|---|---|---|
| 9th outer | **Pin 17 = 3.3 V power** | 7th outer (Pin 13 = GPIO 27) |
| Pin 4 | **5 V power** | one of Pin 11 / 13 / 15 |
| 8th outer | Pin 15 = GPIO 22 ✅ correct | (this one was right) |

A button can only fire if pressing it pulls the GPIO line **to GND**. If the "ground" leg of the button is plugged into a **power pin** (3.3 V or 5 V), pressing the button shorts the GPIO line to power — exactly what the internal pull-up is already doing — so nothing changes electrically and no falling edge fires. **Perfect explanation for total silence on B1/B2/B3.**

Power pins to NEVER plug a button into:
- Pin 1 (3.3 V)
- Pin 2 (5 V)
- Pin 4 (5 V)
- Pin 17 (3.3 V)

---

## What needs to happen next (carryover)

1. **Physically rewire B1/B2/B3.** Each tactile button has 4 legs in two internally-connected pairs. Wire **diagonally**:
   - **B1**: one leg → Pin 11 (GPIO 17) | diagonal leg → Pin 14 (GND)
   - **B2**: one leg → Pin 13 (GPIO 27) | diagonal leg → Pin 14 (GND, same row)
   - **B3**: one leg → Pin 15 (GPIO 22) | diagonal leg → Pin 20 (GND)
2. **Verify** by pressing each button and watching `cat /proc/interrupts | grep pinctrl` — IRQs 60, 61, 62 should start incrementing.
3. **End-to-end demo dry-run**: open a session via B1, snap photo via B2, record video via B2 double, voice note via B3 hold, close session via B1, switch to `/documentation` in the browser and confirm everything streamed in.
4. **(Optional)** Restore audio in B2 videos by routing through `AudioBridge` instead of opening ALSA directly. Today's video is silent because `arecord` can't open the I2S mic concurrently with `audio_worker`.
5. **(Optional)** Identify the unknown blue 6-pin component on the user's breadboard (markings: "L608", "L122S" — possibly an optocoupler or small breakout) and decide whether it's intentional in the signal path.

---

## Files changed

### New
- `scripts/gpio_bridge.py` — physical-button → HTTP sidecar
- `ops/src/app/documentation/page.tsx` — second supervisor page
- `ops/src/components/sections/SessionsPanel.tsx`
- `ops/src/components/sections/CapturesPanel.tsx`
- `Documentation/sessions/2026-05-08-physical-buttons-and-doc-page.md` — this log

### Modified
- `config.py` — `BUTTON_DEBOUNCE_MS` 300 → 50
- `ops/src/components/Nav.tsx` — Agent / Documentation tabs
- `src/subsystems/button_handlers.py` — B3 guard + SOS auto-close + B2 video rewrite
- `dashboard/server.py` — wires the B3 guard via `_ai_running` callable

### Untouched on purpose
- All Gemini Live + OpenAI Realtime session code
- `src/ai/tools.py` — same 6 tools
- `dashboard/audio_worker.py` + `audio_bridge.py`
- All Supabase tables (`sessions` + `session_assets` + `sos_events` + `wearable_settings` were already in place from the previous session — no schema changes needed today)
- `~/.asoundrc`
- `capture_av_mp4.sh` (left in tree but no longer referenced from b2_record_video)

---

## Commits pushed to `origin/openai-sdk`

- `fc6fce9` — GPIO bridge: physical buttons → dashboard via HTTP, plus debounce tune
- `f38c145` — ops: Documentation page + B3 guard + SOS auto-close + B2 video fix

---

## Hardware in use right now

- **Raspberry Pi 4B** (8 GB RAM)
- Debian 13 (Trixie), kernel 6.12.47-rpt-rpi-v8 aarch64
- 6 tactile push-buttons on a breadboard
- SPH0645LM4H I2S microphone on GPIO 18/19/20
- MAX98357A I2S amplifier + 8 Ω 1 W oval speaker on GPIO 18/19/21
- Pi Camera Module 3 via CSI ribbon
- USB-C power
- User's working orientation: USB-C charger at the bottom-right, USB-A + LAN at the top → GPIO header runs vertically along the user's left edge with Pin 1 at the bottom

---

## Diagnostic state at end of session

- Dashboard process: `uvicorn dashboard.server:app` on `:8000`
- Ops dev server: `next dev` on `:3000`
- GPIO bridge: `python3 -u scripts/gpio_bridge.py`, log at `/tmp/vl_bridge.log`
- Bridge banner shows: `Debounce: 50ms · double-press window: 0.5s`
- Baseline IRQ snapshot saved at `/tmp/gpio_probe/irq_baseline.txt`
- DB has 5 closed test sessions and 8 captures (1 photo, 1 video, 6 voice notes — most are `_orphan/` from earlier debugging)

End of session.
