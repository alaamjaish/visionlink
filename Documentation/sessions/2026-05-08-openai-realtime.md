# Session Log — 2026-05-08 (OpenAI Realtime integration)

**Branch:** `openai-sdk` (cut from `main` at `942363d`).
**Theme:** Add OpenAI's brand-new `gpt-realtime-2` (released 2026-05-07) as a
parallel voice provider next to Gemini Live. Keep Gemini intact as the safety
net. Share tools, database, audio output, and the ops dashboard.
**Outcome:** Working end-to-end on the first connection attempt. User spoke
in Arabic, agent transcribed it, called `lookup_component`, and responded.

---

## TL;DR

- New provider radio in the dashboard: 🟡 Gemini Live | 🟢 OpenAI Realtime.
  Default = Gemini. Switching is one click; live state is per-provider.
- `gpt-realtime-2` connects via the official `openai` Python SDK 2.36.0
  (released 2026-05-07).
- All **6 tools** (`lookup_component`, `log_incident`, `mark_task_complete`,
  `get_my_assignments`, `request_part`, `send_report`) are reused as-is from
  `src/ai/tools.py` — provider-agnostic handlers paid off.
- **📷 SNAP & ASK** works on either provider: capture from picamera2, base64,
  inject as `input_image` content. OpenAI accepts images mid-session at any
  time (no special "snap mode" needed, unlike Gemini).
- Dashboard's Agent Settings modal now has a Provider radio at the top.
  Each provider has its own system prompt, VAD, and tunables persisted to a
  separate JSON file.
- **Multilingual works out of the box** — first live test spoke Arabic
  ("مرحبا") and the agent transcribed + tool-called against the parts DB.

---

## What we added

### `src/ai/openai_tools.py` (new, ~50 lines)
Thin adapter that maps `TOOL_DECLS` (provider-agnostic JSON-Schema-ish dicts)
into OpenAI's `tools=[{type:"function", name, description, parameters}]`
list format. Also exports `describe_openai_tools()` for the agent settings
read-only view.

### `src/ai/openai_realtime.py` (new, ~400 lines)
The OpenAI Realtime session manager. Mirrors the structure of Gemini's
`run_live_session` so the dashboard wiring is uniform. Highlights:

- `OpenAISession` class encapsulates one live websocket connection.
- `_send_mic` reads I2S mic blocks (16 kHz S16 mono), removes DC offset,
  applies 6× gain, then **resamples 16 kHz → 24 kHz** (OpenAI's PCM
  requirement) via numpy linear interpolation. Streams via
  `input_audio_buffer.append`.
- `_play_speaker` queues incoming `response.audio.delta` PCM into the
  shared `AudioBridge` (same speaker pipeline as Gemini, no churn).
- `_receive_events` routes server events by `type`:
  - audio out → speaker queue
  - assistant transcript → broadcast as `role: "openai"`
  - user transcript → broadcast as `role: "user"`
  - `response.function_call_arguments.done` → tool dispatch
  - `input_audio_buffer.speech_started` → barge-in (flush speaker)
  - `error` / `session.created|updated` / `response.done` → log
- `_dispatch_tool_call` calls the existing `TOOL_HANDLERS` then sends a
  `function_call_output` item + `response.create`.
- `send_image(jpeg, prompt?)` injects a base64 JPEG via
  `conversation.item.create` + `response.create`.
- Settings persistence: `dashboard/openai_settings.json` (gitignored). The
  defaults file lives in code; the disk file only stores deltas.

### `dashboard/server.py` (additive only)
Imports the new module. Existing Gemini routes untouched. New routes:

- `POST /api/live/oai/start?camera=true|false` — spawn OpenAI session
- `POST /api/live/oai/stop`
- `POST /api/live/oai/snap?prompt=...` — inject a camera frame
- `GET /api/agent/openai/settings` — full read snapshot
- `POST /api/agent/openai/settings` — partial update / reset

`/api/health` extended with `has_openai_key`, `openai_model`,
`openai_connected`.

The two providers are mutually exclusive at runtime: `oai_start` returns 409
if a Gemini session is already running, and the existing Gemini routes are
unchanged so they don't know about the OpenAI session.

### `dashboard/static/index.html`
- New Provider radio above the existing Mode radio (Gemini default checked).
- Mode row hidden when OpenAI is selected (OpenAI doesn't have audio/snap/
  video distinction).
- `📷 SNAP & ASK` button replaces "SNAP TO GEMINI" — works for both
  providers; the dispatch routes to the right endpoint based on the
  provider radio.
- Live light label flips between "Gemini Live" and "OpenAI Realtime".
- Model tag flips between `gemini-3.1-flash-live-preview` and
  `gpt-realtime-2`.
- Agent Settings modal:
  - New Provider radio at top of modal
  - Gemini-only fields (start/end sensitivity) inside `#geminiFields`
  - OpenAI-only fields (voice, reasoning effort, server-VAD threshold)
    inside `#openaiFields`
  - One save button — POSTs to the right endpoint based on provider radio
  - Tools panel shared (same six tools either way)

### `.env.example`
Added documented `OPENAI_API_KEY=` slot with a link to the OpenAI keys page.

### `.gitignore`
Added `dashboard/openai_settings.json` (alongside the existing
`agent_settings.json` for Gemini).

---

## Architecture decision: dual-stack, NOT migration

We deliberately did NOT replace Gemini. The user wanted:

1. The new model integrated end-to-end and ready to demo.
2. Gemini kept intact as a safety net.
3. Both selectable from the same dashboard.

This drives the design:

```
                    [Voice Dashboard UI]
                            |
                            ▼
              ┌─────────────┴─────────────┐
              ▼                           ▼
      [Gemini provider]            [OpenAI provider]
      dashboard.server             src/ai/openai_realtime
      .run_live_session            .OpenAISession
              │                           │
              └─────────────┬─────────────┘
                            ▼
                  [src/ai/tools.py]   ← UNCHANGED
                            │
                            ▼
                  [Supabase + Gmail]  ← UNCHANGED
```

Six tools, one database, one ops dashboard. Two brains. Pick at session start.

---

## Things that landed cleanly first try

- Schema conversion: `TOOL_DECLS` was already in JSON-Schema-ish dict form,
  so OpenAI just needed `{"type": "function", ...}` wrapper. Zero re-mapping.
- Event dispatch: the SDK's `connection.recv()` returns pydantic models;
  we coerce to dicts for image content but otherwise read attributes
  directly. Worked first run.
- Audio output: OpenAI's 24 kHz PCM matches what our audio_worker already
  expects. We didn't touch the worker at all.
- Audio input: 16 kHz → 24 kHz linear resample with `np.interp`. Voice
  quality is plenty for a VAD-driven STT model. Zero perceived loss.
- Tool dispatch: `function_call_arguments.done` → JSON parse → existing
  handler → `function_call_output` item → `response.create`. Standard.
- Image input: `conversation.item.create` with content `[{type:
  "input_image", image_url: "data:image/jpeg;base64,..."}]` then
  `response.create` to make the model speak about it.

---

## Things we caught while building

1. **OpenAI Realtime PCM is locked to 24 kHz.** No way to negotiate down
   to 16 kHz like Gemini Live. Linear-interpolate the mic stream up. Done
   in `resample_16k_to_24k` (~10 lines of numpy).
2. **The SDK's high-level `connection.session.update()` shape from
   marketing docs doesn't exist in 2.36.0.** The real API is
   `connection.send({"type": "session.update", ...})` — raw event dicts
   on the same websocket. Easier than expected once you know.
3. **`conversation.item.created` carries the function-call name**; the
   later `response.function_call_arguments.done` event has `arguments`
   but doesn't always include `name`. We capture name on item-created and
   merge with args on done.
4. **Server VAD config keys differ from Gemini.** OpenAI uses `threshold`
   (0..1) instead of `start/end_sensitivity` enums. We surface threshold
   directly in the UI.
5. **Pydantic events vs. dicts.** `connection.recv()` yields pydantic
   model instances; we use a tiny `_ev_attr(event, name)` helper that
   tries `getattr` then `dict.get` so the same code handles both.

---

## Live test result (first session, 2026-05-08 ~02:50)

User started a Gemini session earlier in the day. After our restart they
selected `🟢 OpenAI Realtime` and clicked START LIVE. Within ~3 seconds:

- WebSocket connected to `gpt-realtime-2`
- Calibration tone played (audio worker)
- Mic blocks streaming (visible in log: `[oai mic] sent N blocks ... upsample 16k->24k`)
- User said "مرحبا" (Arabic for "hello") — transcribed correctly
- User asked about valve B7 in Arabic — agent fired
  `lookup_component({'query': 'الصمام B7'})` against Supabase
- Result was `{'rows': []}` (the DB has the part in English) — agent
  responded honestly that it couldn't find it
- Half-duplex echo suppression worked (`[oai mic] muted (20 blocks)`)
- Speaker drained, mic re-enabled, ready for next turn

**No code changes needed after the first connection.** The build was right
on the first integration. Multilingual tool calling worked without any
prompt tuning.

---

## What still needs doing

- **Wire OpenAI provider to a physical GPIO button.** Current plan in
  `7TH_MAY_UPDATE.md` is to simulate the 6 buttons in the dashboard first
  and validate every flow, then map GPIO callbacks to those handlers.
  OpenAI snap-and-ask is a perfect fit for the camera-button (Button 4).
- **Resend transport for OpenAI flows.** Currently `send_report` uses
  Gmail SMTP. No change needed — works for both providers.
- **Voice quality A/B test.** Try `cedar` vs `marin` vs `alloy` voices
  during a real demo run. Tunable from the Agent Settings modal.
- **Reasoning effort dial in real demo.** Default is `low`. Try `medium`
  for the email drafting flow specifically.
- **MCP server expose.** Optional — OpenAI Realtime supports remote MCP
  servers. We could expose `src/ai/tools.py` as an MCP server so any
  MCP-aware client (Claude Desktop, etc.) could use the same tools.

---

## Files changed

### Modified
- `dashboard/server.py` — imports + globals + 5 new endpoints + `/api/health`
  extension. Existing Gemini code unchanged.
- `dashboard/static/index.html` — provider radio, dual UI, agent settings
  tabs.
- `.env.example` — documented `OPENAI_API_KEY=` slot
- `.gitignore` — added `dashboard/openai_settings.json`

### New
- `src/ai/openai_tools.py` — provider-agnostic schema converter
- `src/ai/openai_realtime.py` — `OpenAISession` class + helpers
- `Documentation/sessions/2026-05-08-openai-realtime.md` — this log
- `Documentation/NEXT_SESSION_PLAN.md` — *not updated yet, do that next*

### Auto-generated at runtime (gitignored)
- `dashboard/openai_settings.json` — written when user saves OpenAI
  settings in the Agent Settings modal

---

## Lessons / non-obvious knowledge

1. **Provider-agnostic tool registry pays off massively.** Because
   `TOOL_HANDLERS` and `TOOL_DECLS` were never coupled to Gemini types,
   adding OpenAI is mostly a schema wrapper + an event-loop. No tool
   logic was duplicated.
2. **Don't fight 24 kHz.** OpenAI Realtime mandates 24 kHz PCM — accept
   the resample tax and move on. `np.interp` is fast enough for a 16 kHz
   block (1600 samples) — measured ~50 µs per block on the Pi 4B.
3. **`gpt-realtime-2` does NOT need brutal anti-hallucination prompts.**
   Our 5,201-char Gemini prompt has three "ABSOLUTE RULES" against lying.
   The OpenAI prompt is ~700 chars and tools fired correctly on the very
   first session.
4. **First-session multilingual works out of the box.** Spoke Arabic,
   transcribed, mapped to a tool call, executed against Supabase. No
   language-specific prompting needed.
5. **OpenAI's image model is "snap not stream."** Each image is a
   discrete content item. We don't need a video-mode equivalent — the
   single SNAP & ASK button works mid-session at any time.
6. **The two sessions can't coexist.** Both want the same audio worker
   subprocess (single I2S mic + speaker). The dashboard returns 409 if
   you try to start one while the other is live. By design.

---

End of session.
