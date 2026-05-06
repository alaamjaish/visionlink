# 7th of May Update — Next Step Plan

**Date**: 2026-05-07
**Theme**: Simulate the whole 6-button experience in the dashboard FIRST, before touching any GPIO wiring. Validate end-to-end software, then make it physical.

---

## The intention (in one sentence)

Turn the existing testing dashboard into a **full hypothetical control panel** — six clickable on-screen buttons that fire the exact same code paths the physical buttons will fire — so we can prove every flow works from A to Z **without touching a single GPIO pin**.

Once every button is green and behaving perfectly on-screen, **then** we transition to reality: solder, GPIO, debounce, the works.

---

## Why do it this way

- **Faster iteration**: clicking is instant; rewiring is not.
- **Decouples bugs**: if a button's flow is broken, we know it's software (not a wire, not a debounce issue, not a pull-up/pull-down).
- **Demoable from anywhere**: any browser on the LAN can drive the device, even before the wearable is assembled.
- **Reusable forever**: even after physical buttons exist, these on-screen buttons stay as a debug surface.

---

## What the dashboard should grow into

Six clickable buttons in the UI, each labeled and color-coded by mode, each calling the **exact same async function** the physical button would trigger. No simulation layer, no fake events — the click goes through the same handler the GPIO callback will use.

| # | GPIO (later) | Mode | What clicking it should do |
|---|---|---|---|
| 1 | 17 | Documentation | Start/stop a documentation session (timestamped folder, Supabase row) |
| 2 | 27 | Photo / Video | Single-click = photo, double-click = video |
| 3 | 22 | **Voice note** (the one you were trying to remember) | Press & hold → record → release → upload |
| 4 | 5  | AI: Snap + Ask | Open Live session in `audio + snap` mode |
| 5 | 6  | AI: Component Q&A | Open Live session with `lookup_component` tool active |
| 6 | 13 | AI: Agent / Email | Open Live session with `draft_and_send_email` tool active |

The dashboard already has the audio bridge, the Live session loop, and the camera helpers — Buttons 4 / 5 / 6 are mostly wiring. Buttons 1 / 2 / 3 are the new pieces and they're the ones that pull Supabase in.

---

## Concrete steps (in order)

### Step 1 — Supabase schema for documentation
Create the tables Buttons 1, 2, 3 will write into:
- `sessions` — id, user, started_at, ended_at, label, status
- `session_assets` — session_id, kind (`photo` | `video` | `voice_note`), storage_path, captured_at, duration_s, notes
- A Supabase Storage bucket (e.g. `session-assets/`) for the actual files

### Step 2 — Six clickable buttons in the dashboard UI
- Add a "Hypothetical Buttons" panel to `dashboard/static/index.html`
- Six labeled buttons, with single / double / hold gestures wired to `onClick` / `onDblClick` / `onMouseDown`+`onMouseUp` so we can test all three GPIO event types
- Each click hits a corresponding `POST /api/button/{n}/{event}` endpoint

### Step 3 — Server endpoints that mirror the physical handler signatures
- `/api/button/1/single` → `documentation_mode.toggle_session()`
- `/api/button/2/single` → `documentation_mode.take_photo()`
- `/api/button/2/double` → `documentation_mode.toggle_video()`
- `/api/button/3/hold_start` + `/hold_end` → `documentation_mode.voice_note_start/stop()`
- `/api/button/4/single` → `run_live_session(mode="snap")`
- `/api/button/5/single` → `run_live_session(mode="audio", tools=["lookup_component"])`
- `/api/button/6/single` → `run_live_session(mode="audio", tools=["draft_and_send_email"])`

These are the exact same functions GPIO callbacks will eventually call.

### Step 4 — Simulate, watch, fix
- Click each button, watch the dashboard log + Supabase tables.
- Confirm: photos appear in storage, sessions open and close, voice notes upload, Live sessions start in the right mode with the right tools.
- Iterate until each one is dead reliable.

### Step 5 — Transition to physical (only after Step 4 is green)
- Wire `src/hardware/buttons.py` `ButtonHandler` callbacks to the **same handler functions** that the dashboard endpoints already call.
- No new logic. The physical button just becomes another way to reach the working code.
- Re-test from real hardware, confirm parity with the on-screen version.

---

## Done = …

A demo recording where someone clicks all 6 dashboard buttons in sequence, the right thing happens for each, Supabase shows the right rows and files, the speaker speaks the right replies — and we have not yet wired a single GPIO. **Then** and only then do we go physical.
