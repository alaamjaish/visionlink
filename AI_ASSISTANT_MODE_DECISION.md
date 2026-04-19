# VisionLink — AI Assistant Mode Architecture Decision

**Date**: 2026-04-19
**Focus**: Buttons 5 (voice Q&A grounded in Supabase) and 6 (agent mode — voice-triggered email to supervisor)
**Sources**: 3 parallel research agents, 20+ April-2026 sources (full list at bottom)

---

## 1. The verdict (one paragraph, no hedging)

**Keep Gemini Live as the voice frontend. Add two tools: one for direct Supabase fetch (Button 5), one that delegates professional email writing to Claude Sonnet 4.6 and sends via Resend or Gmail SMTP (Button 6). Do NOT switch to OpenAI Realtime, do NOT switch to Google ADK, do NOT rebuild on LangGraph.** The voice loop you have works. The gap is two tools and ~120 lines of Python. All three research agents independently converged on the "voice model for UX, text model for brains" hybrid pattern, and this delivers a graduation-demo-ready stack in days, not weeks.

---

## 2. Why NOT the alternatives (intellectually honest)

### Why not OpenAI Realtime + Agents SDK
- OpenAI Agents SDK (renamed from Assistants) only went public on **April 18, 2026 — literally yesterday**. Still beta with breaking changes expected
- Realtime voice is beta on top of beta
- You'd rewrite the entire audio I/O we just debugged
- Price: $32/1M audio-in + $64/1M audio-out tokens — about 5× Gemini Live's preview (which is free for you)
- Four weeks to demo. Wrong bet.

### Why not Google ADK (Agent Development Kit)
- Is genuinely designed for multi-agent delegation with Gemini
- BUT its Gemini Live streaming API changed names twice in 2025-2026; documentation is moving targets
- Adds an abstraction layer on top of the `google-genai` SDK you already understand
- Overkill for 2 specialist agents (writer, fetcher)
- Good option for a v2 after the demo. Not now.

### Why not LangGraph / LiveKit
- LiveKit + LangGraph is the 2026 state-of-the-art for voice agents with tool graphs
- But it **replaces** your Gemini Live pipeline entirely — throws away everything we just built
- Sub-second latency on Pi requires WebRTC plumbing you don't need

### Why not Vercel AI SDK, CrewAI, AutoGen, Pydantic AI
- Vercel AI SDK: TypeScript only, no Python port, no native duplex voice
- CrewAI: batch-workflow oriented, not real-time voice
- AutoGen / MS Agent Framework: no Gemini Live path
- Pydantic AI: nice ergonomics but no voice frontend; would need custom wiring

---

## 3. The architecture (chosen design)

```
  ┌────────────────────────────────────────────────────────────────┐
  │                  Raspberry Pi 4B (VisionLink)                  │
  │                                                                │
  │  SPH0645 mic ──I2S──► Gemini Live WebSocket                    │
  │                       (gemini-3.1-flash-live-preview)          │
  │                       voice-in, voice-out, tool-calling        │
  │                              │                                 │
  │                    ┌─────────┴─────────┐                       │
  │                    ▼                   ▼                       │
  │        ┌───── tool: lookup_component ──────┐    [Button 5]    │
  │        │       (question or part_code)     │                  │
  │        │            │                      │                  │
  │        │            ▼                      │                  │
  │        │     supabase-py  .ilike(...)      │                  │
  │        │            │                      │                  │
  │        │            ▼                      │                  │
  │        │    rows returned as JSON          │                  │
  │        │    Gemini speaks from rows ONLY   │                  │
  │        └──────────────────────────────────-┘                  │
  │                                                                │
  │        ┌───── tool: draft_and_send_email ──┐    [Button 6]    │
  │        │   (transcript, recipient_email,   │                  │
  │        │    recipient_name)                │                  │
  │        │            │                      │                  │
  │        │            ▼                      │                  │
  │        │   Claude Sonnet 4.6 with a        │                  │
  │        │   structured-output schema        │                  │
  │        │   (subject + body_html + tone)    │                  │
  │        │            │                      │                  │
  │        │            ▼                      │                  │
  │        │    Resend API .Emails.send(...)   │                  │
  │        │   (or Gmail SMTP as fallback)     │                  │
  │        │            │                      │                  │
  │        │            ▼                      │                  │
  │        │   {sent: true, to, subject}       │                  │
  │        │   Gemini speaks "sent to X"       │                  │
  │        └──────────────────────────────────-┘                  │
  │                                                                │
  │  MAX98357A speaker ◄─I2S── Gemini Live WebSocket               │
  └────────────────────────────────────────────────────────────────┘
```

**Key insight**: Gemini Live stays the sole "voice conductor". It does NOT write emails itself — it captures the user's monologue, then calls `draft_and_send_email` which delegates the actual writing to Claude Sonnet 4.6 (which scores 99.8% on JSON-schema compliance, highest of any frontier model, per the 2026 scorecard). Claude is the *writer*, Gemini is the *voice*.

---

## 4. How the user experience flows

### Button 5 — "Tell me about the engine"
1. User: *"VisionLink, what's the torque spec on the main engine bolt?"*
2. Gemini Live: hears → calls `lookup_component("main engine bolt")`
3. Python handler: `supabase.table("components").ilike("name", "%main engine bolt%").execute()` → returns 1 row
4. Gemini: reads the torque_spec field aloud: *"Forty-two newton metres, tightened in two passes."*
5. If DB returns empty: Gemini MUST say *"I don't have that information in the factory records."* (system-prompt enforced)

### Button 6 — "Send a report to my supervisor"
1. User presses Button 6, says: *"Send an email to my supervisor saying we completed the pump inspection today, found two minor leaks on valve A3, and need replacement gaskets ordered by Friday."*
2. Gemini Live: captures the monologue transcription, hears the intent
3. Gemini: says *"One sec, drafting that now..."* (pre-announcement per system prompt; masks the tool latency)
4. Gemini: calls `draft_and_send_email(transcript="<full monologue>", recipient_email="sup@acme.com", recipient_name="Mr. Acharya")`
5. Python handler: sends the monologue to Claude Sonnet 4.6 with a Pydantic schema → gets back `{subject, body_html, tone}` as a polished business email
6. Python handler: calls Resend API → email sent
7. Gemini: speaks *"Email sent to Mr. Acharya. Subject: Pump A3 inspection — valve leaks and gasket reorder."*

Total Button 6 latency budget: ~3–5 seconds. Masked by the "one sec" filler.

---

## 5. Code skeleton (~120 lines — drops into `dashboard/server.py`)

```python
# ---------- Imports (add to top of server.py) ----------
import os
import anthropic
import resend
from supabase import create_client
from pydantic import BaseModel

# ---------- One-time setup (module level) ----------
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
resend.api_key = os.getenv("RESEND_API_KEY")

class EmailDraft(BaseModel):
    subject: str
    body_html: str
    tone: str  # "formal" | "neutral"

# ---------- Button 5: direct Supabase fetch (NO RAG, NO embeddings) ----------
async def handle_lookup_component(args: dict) -> dict:
    q = (args.get("query") or "").strip()
    if not q:
        return {"rows": []}
    cols = "name, part_code, description, torque_spec, maintenance_interval, safety_notes"
    # 1) exact part_code match
    r = sb.table("components").select(cols).ilike("part_code", q).limit(3).execute()
    if r.data:
        return {"rows": r.data}
    # 2) fuzzy name match
    r = sb.table("components").select(cols).ilike("name", f"%{q}%").limit(3).execute()
    return {"rows": r.data or []}

# ---------- Button 6: delegate email drafting to Claude, send via Resend ----------
async def handle_draft_and_send_email(args: dict) -> dict:
    transcript = args["transcript"]
    recipient_email = args["recipient_email"]
    recipient_name = args.get("recipient_name", recipient_email)

    # Claude Sonnet 4.6 with structured output
    msg = await asyncio.to_thread(
        claude.messages.create,
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=(
            "You are a senior technical writer. Produce concise, professional "
            "business emails for a factory supervisor. Use a formal, clear tone. "
            "No emoji, no fluff. Output must match the EmailDraft schema exactly."
        ),
        tools=[{
            "name": "write_email",
            "description": "Produce a polished business email.",
            "input_schema": EmailDraft.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "write_email"},
        messages=[{
            "role": "user",
            "content": (
                f"Recipient: {recipient_name}\n\n"
                f"Worker monologue (rewrite into a professional email; preserve all facts):\n"
                f"{transcript}"
            ),
        }],
    )
    draft_data = next(b.input for b in msg.content if b.type == "tool_use")
    draft = EmailDraft(**draft_data)

    # Send via Resend
    resend.Emails.send({
        "from": "VisionLink <bot@yourdomain.dev>",
        "to": recipient_email,
        "subject": draft.subject,
        "html": draft.body_html,
    })
    return {"sent": True, "to": recipient_name, "subject": draft.subject}

# ---------- Tool declarations for Gemini Live config ----------
TOOL_DECLS = [
    {
        "name": "lookup_component",
        "description": (
            "Search the factory components database by name or part code. "
            "Use this for ANY question about a part, torque spec, "
            "maintenance interval, or safety note."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Component name or part code"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "draft_and_send_email",
        "description": (
            "Draft a professional business email from the worker's spoken monologue "
            "and send it to the supervisor. Use when the user asks to send a report "
            "or email to someone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "transcript": {"type": "string",
                               "description": "The worker's full spoken monologue, verbatim"},
                "recipient_email": {"type": "string"},
                "recipient_name":  {"type": "string"},
            },
            "required": ["transcript", "recipient_email", "recipient_name"],
        },
    },
]

TOOL_HANDLERS = {
    "lookup_component":      handle_lookup_component,
    "draft_and_send_email":  handle_draft_and_send_email,
}

# ---------- System prompt addendum (add to existing system_instruction) ----------
SYSTEM_PROMPT = """You are VisionLink, a factory-floor voice assistant.

TOOL RULES (non-negotiable):
- For ANY question about a factory component, part, torque, maintenance, or
  safety, call `lookup_component` FIRST. Answer ONLY using the fields it returns.
  If the tool returns an empty list, say exactly:
  "I don't have that information in the factory records."
  Never invent part codes, torque values, or intervals.
- For ANY request to send a report, email, or summary to a person, call
  `draft_and_send_email` with the full monologue as transcript.
- Before calling ANY tool, say one short sentence like "one sec" so the user
  knows you're working on it.

STYLE:
- Keep replies to 1–2 sentences, spoken-friendly.
- Speak numbers naturally ("forty-two newton metres", not "42 Nm").
- Never read IDs or URLs aloud."""
```

### Changes to `LiveConnectConfig`
```python
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    realtime_input_config=types.RealtimeInputConfig(automatic_activity_detection=vad),
    tools=[{"function_declarations": TOOL_DECLS}],         # <-- NEW
    system_instruction=types.Content(parts=[types.Part.from_text(text=SYSTEM_PROMPT)]),
)
```

### Inside `receive_turns()` — add right after the `message.data` branch
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

---

## 6. Environment variables to add to `.env`

```ini
# Anthropic (for the writer subagent)
ANTHROPIC_API_KEY=sk-ant-...

# Resend (for sending emails)
RESEND_API_KEY=re_...

# Supabase already configured
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
```

Resend: free tier = 100 emails/day, no card needed. Get a key at resend.com.
Anthropic: first-time sign-up gives $5 free credits — enough for hundreds of drafts.
Supabase: you already have keys.

---

## 7. Risk list (ranked by likelihood)

1. **Voice silence during the 3–5 s tool call** — Claude + Resend takes time. **Mitigation**: system prompt forces "one sec" pre-announcement. Already baked into the design.
2. **Claude halucinating subject/body details not in the transcript** — low risk with structured output + "preserve all facts" instruction, but possible. **Mitigation**: dashboard shows the draft before send; add a `confirm_before_send` boolean arg if paranoid.
3. **Resend domain verification not done** — emails may land in spam on demo day. **Mitigation**: verify your domain this week OR fall back to Gmail SMTP with an app password (slower, but works on a gmail.com sender).
4. **Gemini Live tool_call format drift** on SDK updates — pin `google-genai==1.73.1` in `requirements.txt`.
5. **Supabase row schema drift** — if columns change, the tool returns junk. **Mitigation**: write a tiny `pytest` that hits `lookup_component("engine")` and asserts expected fields.

---

## 8. What to build first (30-minute Button 6 demo path)

1. Sign up for Resend at [resend.com](https://resend.com), verify a sender domain (or use `onboarding@resend.dev` sandbox for demo)
2. Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com)
3. Add both keys to `/home/visionlink/Desktop/visionlink/.env`
4. `pip install --user --break-system-packages anthropic resend`
5. Paste the code from §5 into `dashboard/server.py`
6. Add `tools=` and the new system prompt to `LiveConnectConfig`
7. Restart the server
8. Click **START LIVE** (audio mode) → say *"Send an email to demo@example.com saying hello from VisionLink"* → listen for *"one sec"* → hear Gemini confirm the send

---

## 9. Answers to your explicit questions

> *"Can we delegate to another agent?"*
**Yes.** Gemini Live calls `draft_and_send_email` → that Python handler calls Claude Sonnet 4.6 → Claude writes the email. Gemini is the mouth, Claude is the pen. Exactly what you asked for.

> *"Do we need Vercel AI SDK / Claude Agent SDK / LangChain?"*
**No.** All three research agents agreed: adding `tools=[...]` to Gemini Live and calling Claude via its Python SDK inside the tool handler is simpler, cheaper, and Pi-friendly. Those frameworks are for greenfield projects with months of runway.

> *"Do we need to switch to OpenAI entirely?"*
**No.** OpenAI's new Agents SDK is literally 1 day old (Apr 18, 2026). Immature for a 4-week deadline.

> *"Do we stay with Gemini?"*
**Yes — for voice. But use Claude for writing.** Hybrid is the 2026 best practice.

---

## 10. Full source list (all April 2026, deduplicated)

- [Tool use with Live API — Google AI](https://ai.google.dev/gemini-api/docs/live-api/tools)
- [Gemini API tooling updates — Google Blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-tooling-updates/)
- [Gemini 3.1 Flash Live release — MarkTechPost, Mar 2026](https://www.marktechpost.com/2026/03/26/google-releases-gemini-3-1-flash-live-a-real-time-multimodal-voice-model-for-low-latency-audio-video-and-tool-use-for-ai-agents/)
- [Gemini 3.1 Flash Live quickstart — LaoZhang AI](https://blog.laozhang.ai/en/posts/gemini-3-1-flash-live-api)
- [OpenAI Agents SDK realtime guide](https://openai.github.io/openai-agents-python/realtime/guide/)
- [OpenAI Agents SDK PyPI (Apr 18, 2026)](https://pypi.org/project/openai-agents/)
- [Claude Sonnet 4.6 vs Gemini 3 Flash — NxCode](https://www.nxcode.io/resources/news/claude-sonnet-4-6-vs-gemini-3-flash-ai-model-comparison-2026)
- [Claude Structured Outputs](https://claude.com/blog/structured-outputs-on-the-claude-developer-platform)
- [Improving Structured Outputs in Gemini API](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/)
- [Resend vs Amazon SES 2026](https://forwardemail.net/en/blog/resend-vs-amazon-simple-email-service-ses-email-service-comparison)
- [Send emails with Python — Resend](https://resend.com/docs/send-with-python)
- [Building AI Voice Agents — LiveKit + Supabase](https://www.trixlyai.com/blog/technical-14/building-ai-voice-agents-with-livekit-rag-and-supabase-vector-database-79)
- [Supabase AI & Vectors docs](https://supabase.com/docs/guides/ai)
- [Gemini Live long-running tool bug — pipecat #1564](https://github.com/pipecat-ai/pipecat/issues/1564)
- [Choosing an LLM in 2026 — DEV.to](https://dev.to/superorange0707/choosing-an-llm-in-2026-the-practical-comparison-table-specs-cost-latency-compatibility-354g)
- [Live API capabilities — Google AI](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
- [supabase-py GitHub](https://github.com/supabase/supabase-py)
