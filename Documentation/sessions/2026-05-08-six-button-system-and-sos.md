# Session Log — 2026-05-08 (6-button system + SOS panic mode)

**Branch:** `openai-sdk`
**Theme:** Build the *full* 6-button wearable experience as on-screen
simulator buttons in the voice command center, controlled remotely via
configuration in the ops dashboard, with a brand-new **SOS panic mode**
on B6 (double-click).

---

## TL;DR

- The voice dashboard's controls panel is now a **6-button simulator** —
  single/double-click + hold gestures all wired. Same handler functions
  GPIO callbacks will eventually call.
- Provider/mode radios are **hidden behind a 🔧 Debug override** toggle —
  workers don't pick the brain, supervisors do.
- The ops dashboard is now the **remote configuration source**: a new
  *Wearable Settings* panel sets which provider B4/B5 use, vision mode
  for B5, SOS tunables.
- **SOS panic mode** on B6 double-click:
  - Inserts an `sos_events` row + emails the safety officer
  - Starts an OpenAI Realtime session with a calm-emergency system prompt
  - Auto-snaps a fresh camera frame every 4 s, uploads to storage,
    streams transcript to `sos_events.live_transcript`
  - 10-minute hard timeout
  - **REMOTE SHUTOFF** from the ops dashboard's SOS panel (supervisor
    flips `resolved=true`; the wearable polls every 2 s and stops)
- 4 new Supabase tables (`wearable_settings`, `sessions`, `session_assets`,
  `sos_events`) + a `session-assets` storage bucket.

---

## What we built

### Ops dashboard side — supervisor config + SOS oversight

**`ops/src/components/sections/WearableSettingsPanel.tsx`** — singleton
config form, realtime-synced. Edits in the form update Supabase; the
voice command center reads these on every button press. ~200 ms
propagation.

Fields:
- B4 voice provider (Gemini | OpenAI)
- B5 voice+vision provider (Gemini | OpenAI)
- B5 vision mode (`snap_on_press` | `gemini_video` | `auto_snap_4s`)
- SOS photo interval (s)
- SOS max duration (s) — hard timeout
- SOS alert recipient role
- Worker identity

**`ops/src/components/sections/SosPanel.tsx`** — alarm panel:
- Border + glow turn red when an SOS is active
- Each row shows worker, time-since, frames sent, email-sent badge
- Live transcript streams in below the row
- Big red **🛑 SHUT OFF** button → modal → confirms (with supervisor name
  + reason) → flips `resolved=true` in Supabase → wearable detects via
  poll within ~2 s and stops everything.

Both panels are in the new "Wearable" section of the ops command center,
above the existing Operations + Communications sections.

### Voice command center side — 6-button simulator

**`dashboard/static/index.html`** — Controls panel rebuilt as a 6-cell
grid. Each cell shows the button number, GPIO pin, label, and gesture
hint. Click events translate to:

| Gesture | Detection | Backend |
|---|---|---|
| `single` | Plain click (with 350 ms wait if double also valid) | `POST /api/button/N/single` |
| `double` | Two clicks within 350 ms | `POST /api/button/N/double` |
| `hold` | mousedown → mouseup/touchend | `POST /api/button/N/hold_start` then `/hold_end` |

Visual state:
- B1 lights green when a doc session is open
- B3 glows yellow while recording a voice note
- B6 glows accent when SOS is armed
- A toast notification surfaces warnings ("double-click required") and
  errors ("session already running") at the top of the screen.

The old Provider + Mode radios + START/STOP/SNAP buttons are now under a
**🔧 Debug override** checkbox — hidden by default, kept around because
they're useful during development. Workers in the demo never see them.

### Backend side — single source of truth handlers

**`src/subsystems/button_handlers.py`** — eight async coroutines, one per
(button, event) pair, plus a SOS controller:

- `b1_doc_session_toggle` — open/close `sessions` row
- `b2_take_photo` — picamera2 → upload to `session-assets` → row in
  `session_assets`
- `b2_record_video` — shells out to `scripts/capture_av_mp4.sh` for a
  ~5 s clip, uploads MP4
- `b3_voice_note_start` / `b3_voice_note_end` — drains mic blocks from
  `AudioBridge` while held, wraps in WAV header on release, uploads
- `b4_ai_voice_only` — reads `wearable_settings.b4_provider`, starts the
  matching AI session
- `b5_ai_voice_vision` — reads `b5_provider` + `b5_vision_mode`, starts
  the matching session with the camera open
- `b6_warn_single` — refuses to arm SOS, prompts for double-click
- `b6_sos_trigger` — full SOS controller (described below)

All handlers take callable deps (`log`, `broadcast`, `bridge`,
`grab_jpeg`, `ai_starter`) so they don't import from `dashboard.server`
— no circular imports. The dashboard injects these.

**`dashboard/server.py`** — one new endpoint replaces all six:

```python
@app.post("/api/button/{n}/{event}")
async def button_dispatch(n: int, event: str): ...
```

Plus a `_button_ai_starter(provider, mode, camera)` helper that gates
session start (refuses if any session is already running) and a
`_grab_jpeg_for_buttons()` helper that reuses the open SessionCamera if
present, falls back to a transient picamera2 lock otherwise.

### SOS panic controller

`b6_sos_trigger` orchestrates four concurrent tasks:

1. **OpenAI Realtime session** with a calm emergency system prompt:
   *"Stay calm, ask short questions, describe what you see, tell them
   help is on the way. Do NOT call any tools right now."*
2. **Auto-snap loop** — every `sos_photo_interval_s` seconds: capture
   JPEG → upload to `sos/<sos_id>/frame_<ts>.jpg` → inject into the
   OpenAI session via `send_image()` → bump `sos_events.frames_sent`
3. **Resolution watcher** — polls `sos_events.resolved` every 2 s. When
   the supervisor flips it via the ops dashboard, returns and triggers
   teardown.
4. **Hard timeout** — `asyncio.wait_for(watcher, timeout=max_duration_s)`
   auto-resolves if no one acks within 10 min.

Side effect at trigger time: `_sos_send_alert_email()` calls the
existing `handle_send_report()` tool with the safety officer role and
a custom message, so the supervisor's inbox lights up immediately.

Live transcript: every `transcript` event with `role="openai"` is
appended to `sos_events.live_transcript` so the supervisor sees what
the wearable is saying *as it speaks*, not just after.

---

## Database schema (new — needs to be applied)

`scripts/schema_buttons_and_sos.sql`:

| Table | Purpose |
|---|---|
| `wearable_settings` (1 row, id='current') | Remote config — providers, vision mode, SOS tunables, worker identity |
| `sessions` | B1 doc sessions (worker, label, started_at, ended_at, status) |
| `session_assets` | B2 photos / B2 videos / B3 voice notes (kind, storage_path, duration_s) |
| `sos_events` | One row per SOS — frames_sent, live_transcript, resolved, resolved_by, reason |

All 4 added to `supabase_realtime` publication; RLS disabled (matches
demo). Storage bucket `session-assets` is created via
`scripts/setup_buttons_schema.py` (since storage DDL can't be done in
SQL).

---

## What the user must do BEFORE testing

Three steps, ~3 minutes total:

1. Open the Supabase SQL editor → paste
   `scripts/schema_buttons_and_sos.sql` → run.
2. From the project root: `python3 scripts/setup_buttons_schema.py`
   - Verifies tables exist
   - Inserts the singleton `wearable_settings` row if missing
   - Creates the `session-assets` storage bucket (private)
3. Restart the dashboard so it picks up the latest code.

Then click any button and watch the ops dashboard light up.

---

## Architecture decisions (locked in 2026-05-08)

1. **Dual surface, not dual control.** The voice command center has
   buttons. The ops dashboard has settings. Workers press buttons.
   Supervisors edit settings. Two surfaces, two roles.
2. **B5 vision = snap on press (default), not continuous video.** OpenAI
   doesn't do video; Gemini's video stream is bandwidth-heavy. Snap-on-
   press works on both providers and matches the user's mental model
   ("press to show me something"). `gemini_video` and `auto_snap_4s`
   are still selectable in the settings panel.
3. **B6 single-click is intentionally a no-op.** Pocket-dial protection.
   Double-click within 350 ms (browser side; same window will be used
   for GPIO once we wire it).
4. **SOS uses OpenAI specifically** (not Gemini) regardless of B4/B5
   provider settings. Reason: gpt-realtime-2's instruction-following is
   more reliable for the calm-emergency persona and OpenAI's image
   model is purpose-built for "describe this snapshot." Gemini fallback
   could be added later if API is unreachable.
5. **Hard 10-minute timeout** is non-negotiable. Even if the supervisor
   never sees the alert, the wearable stops itself to bound storage cost
   and audio session length.
6. **Provider/mode radios kept but hidden behind 🔧 Debug override.**
   Useful for dev iteration; invisible by default for the demo.

---

## Files changed

### New
- `scripts/schema_buttons_and_sos.sql`
- `scripts/setup_buttons_schema.py`
- `src/subsystems/button_handlers.py` (~620 lines — 6 button handlers + SOS controller)
- `ops/src/components/sections/SosPanel.tsx`
- `ops/src/components/sections/WearableSettingsPanel.tsx`
- `Documentation/sessions/2026-05-08-six-button-system-and-sos.md` (this log)

### Modified
- `dashboard/server.py` — import `button_handlers`, add `_grab_jpeg_for_buttons`,
  `_button_ai_starter`, single dispatching `/api/button/{n}/{event}` endpoint
- `dashboard/static/index.html` — Controls panel rebuilt as a 6-button
  simulator grid; old Provider/Mode radios moved behind 🔧 Debug override;
  new toast notification system; new websocket events handled
- `ops/src/app/page.tsx` — Wearable section added with SOS + Settings panels
- `ops/src/lib/types.ts` — types for `WearableSettings`, `Session`,
  `SessionAsset`, `SosEvent`

### Untouched on purpose (your safety net)
- All existing Gemini Live + OpenAI Realtime session code
- `src/ai/tools.py` — same 6 tools, both providers, both buttons
- `dashboard/audio_worker.py` + `audio_bridge.py` — shared by everything
- All previous Supabase tables (`incidents`, `tasks`, `parts`,
  `components`, `managers`, `report_templates`, `sent_reports`)
- `~/.asoundrc`

---

## What's next

Once the schema is applied:
1. Smoke each of the 6 buttons on-screen
2. Trigger SOS, watch the ops dashboard light up red, supervisor clicks
   SHUT OFF, wearable stops within ~2 s
3. Then physical GPIO wiring: the same handler functions get called
   from `ButtonHandler.register(pin, on_single=b1_doc_session_toggle, ...)`
   in `main.py` — no new logic required.

End of session.
