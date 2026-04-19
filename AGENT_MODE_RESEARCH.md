# Agent Mode Research — VisionLink

**Date**: 2026-04-19
**Question**: Can we give our voice-first Gemini Live agent tool-calling / agentic abilities (send emails, fetch from database, write reports) WITHOUT abandoning the real-time voice experience we just built?

**Short answer**: **YES — stay with Gemini Live. It already supports native tool calling.** No need for Vercel AI SDK, OpenAI Assistants, Claude Agent SDK, or any "voice → text → agent → text → voice" sandwich. Gemini will call your Python functions mid-voice-conversation.

---

## 1. Bottom-line recommendation

Keep the entire pipeline you have today. Add tools by passing a `tools=[...]` field to `LiveConnectConfig` and handling `message.tool_call` in the same receive loop we already wrote. Total code change: ~40 lines in `dashboard/server.py`.

Do NOT switch to:
- OpenAI Realtime — better latency, 5× more expensive, requires rewriting audio I/O
- Vercel AI SDK — TypeScript, no native duplex voice, wrong language for our Pi
- Claude Agent SDK alone — no real-time voice API from Anthropic in 2026 (still push-to-talk)
- LangGraph + LiveKit — throws away our working Gemini Live pipeline

---

## 2. How Gemini Live tool calling actually works

### 2.1 Register tools in the session config

```python
send_email_decl = {
    "name": "send_email",
    "description": "Send an email to a recipient.",
    "parameters": {
        "type": "object",
        "properties": {
            "to":      {"type": "string"},
            "subject": {"type": "string"},
            "body":    {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
}

config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    tools=[{"function_declarations": [send_email_decl]}],   # <-- the new line
    # ... rest of our existing config
)
```

### 2.2 Tool call message shape

During `async for message in session.receive():` the tool call arrives on **`message.tool_call`** (top-level, NOT inside `server_content`):

```json
{
  "toolCall": {
    "functionCalls": [
      {
        "id": "function-call-14506904501175989829",
        "name": "send_email",
        "args": {"to": "boss@acme.com", "subject": "Shift report", "body": "All clean."}
      }
    ]
  }
}
```

### 2.3 Handle it + reply

```python
tc = getattr(message, "tool_call", None)
if tc and tc.function_calls:
    responses = []
    for fc in tc.function_calls:
        result = await TOOL_HANDLERS[fc.name](dict(fc.args or {}))
        responses.append(types.FunctionResponse(
            id=fc.id,           # REQUIRED — server matches on id, not name
            name=fc.name,
            response={"result": result},  # must be a dict
        ))
    await session.send_tool_response(function_responses=responses)
    continue
```

### 2.4 Behaviour during a tool call

- `tool_call` arrives **mid-turn** (NOT accompanied by `turn_complete`)
- Voice **goes silent** while our Python handler runs (Gemini 3.1 Flash Live is sync-only — `NON_BLOCKING` is reserved for 2.5 Flash Live)
- After `send_tool_response`, Gemini speaks the follow-up then fires `turn_complete`

### 2.5 The "silent gap" UX fix

For a 3-second SMTP call, the user will hear 3 seconds of silence. Fix it with ONE line in the system prompt:

> *"Before calling any tool, say one short sentence like 'one sec, sending that now'."*

Gemini reliably pre-announces when instructed — no client-side filler audio needed.

### 2.6 Safety pattern for destructive tools

The official Google 2026 examples do NOT build confirmation in. For `send_email`, `delete_row`, etc., use a **two-tool split**:

- `draft_email(to, subject, body)` — pure, returns draft back so Gemini reads it aloud
- `send_email_confirmed(draft_id)` — actually sends; system prompt forbids calling it without a spoken "yes"

Simpler alternative: one tool with a `confirmed: bool` arg and a strict system-prompt rule.

---

## 3. Architecture comparison (latency + cost, April 2026)

| Option | Round-trip latency | ~Cost/min | Verdict |
|---|---|---|---|
| **(a) Gemini Live + native tools** | 0.6–1.0 s | $0.03–0.08 (free during preview!) | **CHOSEN** |
| (b) OpenAI `gpt-realtime` + tools | 0.5–0.9 s | $0.18–0.30 | Requires rewrite, 5× pricier |
| (c) Hybrid Gemini Live + Claude Agent SDK | 1.2–3.5 s | $0.10–0.25 | Adds a second SDK, dual billing |
| (d) Vercel AI SDK (STT→LLM→TTS sandwich) | 1.5–2.5 s | $0.05–0.15 | TypeScript only — wrong stack |
| (e) LangGraph + LiveKit + Realtime | 0.7–1.2 s | $0.20–0.35 | Replaces our whole pipeline |

---

## 4. Tools we can build for the graduation demo

All of these are ~30 lines of Python each, registered as function declarations. None require leaving Gemini Live.

| Tool | What it does | Underlying service |
|---|---|---|
| `send_email(to, subject, body)` | SMTP via Gmail app-password | `smtplib` (existing `.env` has creds) |
| `draft_email(to, subject, body)` | Safe paired draft (voice confirmation) | in-memory draft store |
| `fetch_part(code)` | Look up a part in Supabase inventory | `httpx` → Supabase REST |
| `log_shift_note(text)` | Append a note to the current work session | Supabase insert |
| `take_photo_to_session()` | Capture + upload to current session | already-wired Picamera2 + Supabase |
| `write_shift_report()` | Summarise session → PDF → email | Gemini text API + `reportlab` + SMTP |
| `set_language(lang)` | Switch between English and Turkish mid-session | updates config |

For the demo (grad-teacher email stunt), start with `draft_email` + `send_email_confirmed`. That alone is the wow moment.

---

## 5. Exact code changes for `dashboard/server.py`

Three localised edits — no refactor needed.

### Edit A — declare tools + handlers (top of `run_live_session`, before `LiveConnectConfig`)

```python
send_email_decl = {
    "name": "send_email",
    "description": "Send an email. Ask the user to confirm out loud first.",
    "parameters": {
        "type": "object",
        "properties": {
            "to":      {"type": "string"},
            "subject": {"type": "string"},
            "body":    {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
}

async def handle_send_email(args: dict) -> dict:
    await log(f"[tool] send_email(to={args.get('to')!r}, subject={args.get('subject')!r})")
    await asyncio.sleep(0.2)  # dummy; wire up real SMTP later
    return {"status": "sent", "to": args.get("to")}

TOOL_HANDLERS = {"send_email": handle_send_email}
```

### Edit B — add `tools=[...]` and tweak system prompt in `LiveConnectConfig`

```python
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=vad
        ),
        tools=[{"function_declarations": [send_email_decl]}],   # NEW
        system_instruction=types.Content(parts=[types.Part.from_text(
            text=(
                "You are VisionLink, a friendly wearable assistant for a factory worker. "
                "Keep replies short and spoken-friendly. "
                "Before calling any tool, say one short sentence like 'one sec, sending that now'. "
                "Never send an email without first reading the draft aloud and getting a spoken 'yes'."
            )
        )]),
    )
```

### Edit C — handle `tool_call` inside `receive_turns`

Insert right after the `message.data` audio-queue push, before the `server_content` block:

```python
tc = getattr(message, "tool_call", None)
if tc and tc.function_calls:
    responses = []
    for fc in tc.function_calls:
        handler = TOOL_HANDLERS.get(fc.name)
        if handler is None:
            result = {"error": f"unknown tool {fc.name}"}
        else:
            try:
                result = await handler(dict(fc.args or {}))
            except Exception as e:
                result = {"error": str(e)}
        responses.append(types.FunctionResponse(
            id=fc.id, name=fc.name, response={"result": result}
        ))
    await session.send_tool_response(function_responses=responses)
    await broadcast({"type": "tool_call", "name": tc.function_calls[0].name})
    continue
```

That's it. To add another tool: append a decl to the `tools` list, add an entry to `TOOL_HANDLERS`.

---

## 6. Gotchas

- `fc.args` is a proto-dict — cast with `dict(fc.args)` before passing to `httpx`/`smtplib`.
- `FunctionResponse.id` must match `FunctionCall.id`; missing `id` silently stalls the server.
- `response` on `FunctionResponse` must be a **dict** (not a string).
- Sync-only on 3.1-flash-live — the voice pauses while your handler runs. Keep handlers under ~5 s or use the pre-announcement trick.
- `send_tool_response` must be awaited.

---

## 7. Sources (all April 2026)

- [Tool use with Live API — ai.google.dev/gemini-api/docs/live-api/tools](https://ai.google.dev/gemini-api/docs/live-api/tools)
- [Live API capabilities — ai.google.dev/gemini-api/docs/live-api/capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
- [Live API WebSockets reference — ai.google.dev/api/live](https://ai.google.dev/api/live)
- [google-gemini/cookbook Live-API tools notebook (DeepWiki)](https://deepwiki.com/google-gemini/cookbook/6.2-liveapi-tools-and-function-calling)
- [gemini-live-api-examples: Tool Use & Function Calling (DeepWiki)](https://deepwiki.com/google-gemini/gemini-live-api-examples/6-tool-use-and-function-calling)
- [Vertex AI Live API reference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/multimodal-live)
- [NON_BLOCKING hallucination bug — googleapis/python-genai #1894](https://github.com/googleapis/python-genai/issues/1894)
- [OpenAI Realtime / gpt-realtime docs](https://platform.openai.com/docs/guides/realtime)
- [Claude voice feature roadmap (2026)](https://www.datastudios.org/post/claude-voice-features-explained-current-status-and-upcoming-real-time-updates)
- [LangChain voice-agent guide (2026)](https://docs.langchain.com/oss/python/langchain/voice-agent)
- [Vercel AI Voice Elements changelog (2026)](https://vercel.com/changelog/ai-voice-elements)
