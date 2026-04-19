# Next Session Plan — After 2026-04-19

**Theme**: Move from "it works via a browser button" to "**it works when I press the physical button on my wearable**", and wire Buttons 5 + 6 to real external services (Supabase for lookup, Claude + Resend for email).

---

## The big goals

1. **Hardware-activated, not mouse-activated.** The dashboard is for debugging only from now on. The real product is triggered by the 6 GPIO buttons on the wearable.
2. **Button 5 connects to Supabase.** User presses Button 5 → speaks a question → Gemini calls `lookup_component()` → Supabase returns rows → Gemini speaks the answer. All from the real DB, not mocked.
3. **Button 6 sends real emails.** User presses Button 6 → speaks a monologue → Gemini calls `draft_and_send_email()` → Claude Sonnet 4.6 writes a polished email → Resend sends it → Gemini confirms.
4. **The 6 buttons (17, 27, 22, 5, 6, 13) are validated physically** — debounce works, no phantom triggers, no stuck GPIO.

---

## Concrete task list (in dependency order)

### Phase A — Physical-button validation (30 min)
- [ ] Write a tiny standalone GPIO probe script (`scripts/test_buttons.py`) that prints `"Button N pressed"` when any of the 6 fires, with debounce
- [ ] Press each of the 6 physical buttons, confirm correct GPIO detection + no bounce noise
- [ ] Fix wiring if any button reports wrong pin or stays stuck

### Phase B — Wire the 6 buttons into the app (1 hr)
- [ ] Use the existing `src/hardware/buttons.py` `ButtonHandler` (single, double, hold callbacks)
- [ ] In `main.py` (or a new `runner.py`), register:
  - Button 1 (GPIO 17) → start/stop documentation session
  - Button 2 (GPIO 27) → single = photo, double = video (reuse `capture_av_mp4.sh` path)
  - Button 3 (GPIO 22) → hold-to-record voice note
  - **Button 4 (GPIO 5) → start Gemini Live in "audio + snap" mode (point-and-ask)**
  - **Button 5 (GPIO 6) → start Gemini Live in "audio" mode with the `lookup_component` tool active**
  - **Button 6 (GPIO 13) → start Gemini Live in "audio" mode with the `draft_and_send_email` tool active**
- [ ] Each button press triggers the same async machinery the dashboard already uses — we refactor `run_live_session` to be callable from both code paths

### Phase C — Supabase `components` table (30 min)
- [ ] Create table:
  ```sql
  create table components (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    part_code text unique,
    description text,
    torque_spec text,
    maintenance_interval text,
    safety_notes text,
    image_url text,
    created_at timestamptz default now()
  );
  create index components_name_idx  on components using gin (to_tsvector('english', name));
  create index components_code_idx  on components (part_code);
  ```
- [ ] Seed with ~7–8 real-looking factory parts (engine, pump A3, valve B7, bearing C12, ...)
- [ ] Install `supabase` Python client: `pip install --user --break-system-packages supabase`
- [ ] Copy `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` into `.env`

### Phase D — Implement Button 5 tool (45 min)
- [ ] Add `handle_lookup_component()` from [AI_ASSISTANT_MODE_DECISION.md](../AI_ASSISTANT_MODE_DECISION.md) §5 into `dashboard/server.py` (or a new `src/ai/tools.py`)
- [ ] Register the tool in `LiveConnectConfig(tools=[...])`
- [ ] Update `system_instruction` with the grounding rules from the decision doc
- [ ] Test end-to-end: press Button 5 → ask "what's the torque spec on pump A3?" → Gemini calls the tool → speaks the real row data
- [ ] Test refusal path: ask "what's the torque spec on the imaginary widget?" → expect *"I don't have that information in the factory records."*

### Phase E — Implement Button 6 tool (1 hr)
- [ ] Sign up at [resend.com](https://resend.com), verify domain OR use `onboarding@resend.dev` for demo
- [ ] Sign up at [console.anthropic.com](https://console.anthropic.com), grab $5 free credit
- [ ] `pip install --user --break-system-packages anthropic resend`
- [ ] Add `ANTHROPIC_API_KEY` and `RESEND_API_KEY` to `.env`
- [ ] Add `handle_draft_and_send_email()` from the decision doc
- [ ] Register the tool in `LiveConnectConfig(tools=[...])`
- [ ] Test end-to-end: press Button 6 → speak "Send an email to demo@example.com saying we finished pump A3 today" → hear *"one sec..."* → hear *"Email sent to demo@example.com, subject ..."* → verify in the inbox

### Phase F — Polish (30 min)
- [ ] Startup TTS greeting when the systemd service boots ("VisionLink ready")
- [ ] Visual feedback in the dashboard when a physical button fires (WebSocket event)
- [ ] Write a one-page **demo script** for the grad panel

---

## What we don't do next session
- Live video streaming beyond testing (stays at 1 fps)
- True full-duplex echo cancellation (half-duplex is fine for demo)
- Soniox STT (we're using Gemini Live's built-in transcription instead)
- RAG / embeddings (table is small, direct SQL is faster and more reliable)
- Switching stacks — Gemini Live stays

---

## Required before we start next session

1. Keys in `.env`:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (already exist)
   - `ANTHROPIC_API_KEY` — get at console.anthropic.com
   - `RESEND_API_KEY` — get at resend.com
2. Supabase `components` table created (SQL in Phase C above)
3. Pi powered, on Wi-Fi, dashboard reachable at http://192.168.0.31:8000
4. All 6 buttons physically pressable (not stuck)

---

## Risk watchlist

- **Resend domain verification**: if not verified, emails land in spam. Use the sandbox address for demo if domain setup is a blocker.
- **Claude 4.6 latency**: budget 3–5 s for the draft+send round-trip. System prompt forces Gemini to say "one sec" so user knows we're working.
- **Button debounce on Pi OS Bookworm**: verify in Phase A. If phantom triggers, raise `BUTTON_DEBOUNCE_MS` in `config.py`.
- **Session length cap**: audio-only = 15 min, audio+video = 2 min. For a demo we'll be well under.
- **Tool-call voice silence**: handled by the "one sec" pre-announcement rule in the system prompt.

---

## Demo narrative (the story we're building toward)

> Worker in a factory wears VisionLink. Presses **Button 5**: *"What's the torque spec on pump A3?"* VisionLink replies *"Forty-two newton metres, tightened in two passes."*
>
> Later, worker presses **Button 6** and says: *"Send an email to the supervisor saying we completed the pump A3 inspection today, found two minor leaks on valve B7, and need replacement gaskets by Friday."*
>
> VisionLink says *"One sec, drafting that now..."* Pause of ~4 seconds. Then: *"Email sent to Mr. Acharya. Subject: Pump A3 inspection — valve B7 leaks and gasket reorder for Friday."*
>
> Supervisor's phone pings. They open an actual well-written professional email. **The demo is won.**
