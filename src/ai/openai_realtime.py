"""OpenAI Realtime API session manager — the second brain for VisionLink.

Mirrors the structure of dashboard.server.run_live_session (the Gemini
Live path) but talks to OpenAI's Realtime WebSocket API instead. Reuses:

  - dashboard.audio_bridge.AudioBridge for I2S mic + speaker I/O
  - src.ai.tools.TOOL_HANDLERS for the SAME six tools Gemini uses
  - The dashboard's broadcast() / log() pipes for transcript + log UI

What we add ourselves:
  - 16 kHz mic block ──linear resample──> 24 kHz PCM (OpenAI mandate)
  - Event-driven receive loop for connection.recv()
  - Tool-call dispatch via response.function_call_arguments.done event
  - Single-shot image input via conversation.item.create + response.create
  - Half-duplex echo suppression (mute mic while assistant audio is queued)

Connection lifecycle:
  client.realtime.connect(model="gpt-realtime-2") opens a WebSocket. We
  send a session.update event to configure modalities, voice, VAD,
  tools, instructions, then start mic streaming. The server emits
  audio.delta + transcript events; we relay them to the speaker queue
  and the dashboard. On response.function_call_arguments.done we run
  the tool, send a function_call_output item, and call response.create
  to let the model speak the result.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import numpy as np
from openai import AsyncOpenAI

from dashboard.audio_bridge import AudioBridge
from dashboard.audio_worker import BLOCK, MIC_RATE, SPEAKER_RATE
from src.ai.openai_tools import build_openai_tools
from src.ai.tools import TOOL_HANDLERS, WORKER_NAME


OPENAI_MODEL = "gpt-realtime-2"

DEFAULT_VOICE = "marin"

# OpenAI Realtime PCM audio is locked to 24 kHz, but our I2S mic delivers
# 16 kHz. We resample the mic stream linearly (16 -> 24 == ratio 3/2).
MIC_RESAMPLE_FACTOR = SPEAKER_RATE / MIC_RATE  # 1.5

# Single source of truth for the OpenAI default system prompt. Plays
# the same role as dashboard.server.DEFAULT_SYSTEM_PROMPT for Gemini —
# but written for a model that already follows tool instructions well,
# so it's much shorter.
DEFAULT_OPENAI_SYSTEM_PROMPT = (
    f"You are VisionLink, a wearable assistant talking to {WORKER_NAME} "
    f"on the factory floor. Help with parts, tasks, incidents, and "
    f"reports.\n\n"
    "Tools you have:\n"
    "  - lookup_component(query) — search the parts catalog\n"
    "  - log_incident(description, category?, severity?, location?)\n"
    "  - mark_task_complete(task_query)\n"
    "  - get_my_assignments(include_complete?)\n"
    "  - request_part(part_query, quantity?, urgency?, reason?)\n"
    "  - send_report(report_name, recipient_role?, recipient_name?, "
    "recipient_email?, custom_message?)\n\n"
    "Rules:\n"
    "  1. Whenever the worker reports something wrong (broken, leaking, "
    "damaged, even a personal item like a phone), call log_incident.\n"
    "  2. Whenever the worker asks 'tell me about X' or 'what's the "
    "torque on X', call lookup_component before answering.\n"
    "  3. Never say you logged/marked/sent something without first "
    "calling the matching tool. Never invent data. If a tool returns "
    "an error, say so plainly.\n"
    "  4. If the worker shows you an image (camera snap), describe what "
    "you see and use lookup_component if a recognizable part is "
    "visible.\n"
    "  5. Speak concisely (1-2 sentences). Numbers as words. Don't read "
    "UUIDs or part codes aloud unless asked.\n"
)

DEFAULT_OPENAI_SETTINGS: dict[str, Any] = {
    "system_prompt": DEFAULT_OPENAI_SYSTEM_PROMPT,
    "voice": DEFAULT_VOICE,
    "reasoning_effort": "low",   # minimal | low | medium | high
    # Output playback speed multiplier (0.25 ≤ speed ≤ 1.5). Default 1.2
    # because gpt-realtime-2's voices speak deliberately at 1.0 — fine for
    # casual chat, sounds slow word-by-word in an industrial demo. 1.2 is
    # noticeably snappier without sounding chipmunky. Crank to 1.3 / 1.4
    # for even faster delivery via the AGENT settings panel.
    "speed": 1.2,
    "vad": {
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
    },
    "audio": {
        "mic_gain": 6.0,
    },
}


def resample_16k_to_24k(samples_int16: np.ndarray) -> np.ndarray:
    """Linear-interpolate 16 kHz mono int16 PCM up to 24 kHz mono int16.

    Input length N -> output length round(N * 1.5). Voice quality is
    plenty for an Realtime VAD; the model does its own ASR anyway.
    """
    if samples_int16.size == 0:
        return samples_int16
    n_in = samples_int16.size
    n_out = int(round(n_in * MIC_RESAMPLE_FACTOR))
    x_in = np.arange(n_in, dtype=np.float32)
    x_out = np.linspace(0.0, n_in - 1, n_out, dtype=np.float32)
    interp = np.interp(x_out, x_in, samples_int16.astype(np.float32))
    return np.clip(interp, -32768, 32767).astype(np.int16)


# ----------------------------------------------------------------------
# OpenAI session settings (lives at PROJECT_ROOT/dashboard/openai_settings.json)
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OPENAI_SETTINGS_PATH = PROJECT_ROOT / "dashboard" / "openai_settings.json"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_openai_settings() -> dict[str, Any]:
    if not OPENAI_SETTINGS_PATH.exists():
        return json.loads(json.dumps(DEFAULT_OPENAI_SETTINGS))
    try:
        loaded = json.loads(OPENAI_SETTINGS_PATH.read_text())
        return _deep_merge(DEFAULT_OPENAI_SETTINGS, loaded)
    except Exception as e:
        print(f"[openai_settings] load failed: {e!r} — using defaults", flush=True)
        return json.loads(json.dumps(DEFAULT_OPENAI_SETTINGS))


def save_openai_settings(settings: dict[str, Any]) -> None:
    OPENAI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAI_SETTINGS_PATH.write_text(json.dumps(settings, indent=2))


# ----------------------------------------------------------------------
# Session manager
# ----------------------------------------------------------------------

class OpenAISession:
    """A single live OpenAI Realtime session. Created per START LIVE click.

    The dashboard owns at most one of these at a time (parallel to the
    single Gemini session) — they don't coexist; the user picks ONE
    provider per session.

    All async coroutines exposed here can be awaited from the FastAPI
    event loop; nothing blocks the parent thread.
    """

    def __init__(
        self,
        api_key: str,
        bridge: AudioBridge,
        settings: dict[str, Any],
        broadcast: Callable[[dict[str, Any]], Awaitable[None]],
        log: Callable[[str, str], Awaitable[None]],
        dlog: Callable[..., None],
        start_button: int = 4,
    ) -> None:
        self.api_key = api_key
        self.bridge = bridge
        self.settings = settings
        self.broadcast = broadcast
        self.log = log
        self.dlog = dlog
        # 4 = audio agent (B4), 5 = vision agent (B5). Echoed back in the
        # live_state events so the simulator highlights only the originating
        # button.
        self.start_button = start_button

        # Set during run()
        self.connection: Any = None
        self.assistant_speaking = asyncio.Event()
        self.speaker_queue: asyncio.Queue[bytes] = asyncio.Queue()

        # Per-tool-call buffers keyed by call_id (for streaming arg deltas)
        self._tool_call_args: dict[str, str] = {}
        self._tool_call_names: dict[str, str] = {}

        # Counters for diagnostics
        self._mic_blocks_sent = 0
        self._audio_chunks_received = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _flush_speaker(self) -> int:
        dropped = 0
        while not self.speaker_queue.empty():
            try:
                self.speaker_queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
        dropped += self.bridge.flush_speaker()
        return dropped

    def _build_session_update_event(self) -> dict[str, Any]:
        """Construct the session.update event from current settings."""
        vad_cfg = self.settings.get("vad", {})
        threshold = float(vad_cfg.get("threshold", 0.5))
        prefix_pad = int(vad_cfg.get("prefix_padding_ms", 300))
        silence_ms = int(vad_cfg.get("silence_duration_ms", 500))

        voice = self.settings.get("voice", DEFAULT_VOICE)
        reasoning_effort = self.settings.get("reasoning_effort", "low")
        # Clamp speed to OpenAI's accepted range (0.25..1.5)
        speed = max(0.25, min(1.5, float(self.settings.get("speed", 1.2))))
        instructions = self.settings.get(
            "system_prompt", DEFAULT_OPENAI_SYSTEM_PROMPT
        )

        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": OPENAI_MODEL,
                "instructions": instructions,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": threshold,
                            "prefix_padding_ms": prefix_pad,
                            "silence_duration_ms": silence_ms,
                            "create_response": True,
                            "interrupt_response": True,
                        },
                        "transcription": {
                            "model": "gpt-realtime-whisper",
                        },
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "voice": voice,
                        "speed": speed,
                    },
                },
                "tools": build_openai_tools(),
                "tool_choice": "auto",
                "reasoning": {"effort": reasoning_effort},
            },
        }

    # ------------------------------------------------------------------
    # Public API: send an image into the live session
    # ------------------------------------------------------------------

    async def send_image(self, jpeg_bytes: bytes,
                         prompt: str | None = None) -> None:
        """Inject a single image into the conversation and ask the model
        to react. Suitable for SNAP & ASK button flows.

        OpenAI Realtime treats images as discrete content items, NOT a
        video stream — so each call is a one-shot snapshot.
        """
        if self.connection is None:
            raise RuntimeError("OpenAI session not connected")
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        content: list[dict[str, Any]] = [
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64}",
            }
        ]
        if prompt:
            content.insert(0, {"type": "input_text", "text": prompt})

        await self.connection.send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": content,
            },
        })
        # Trigger an immediate response so the model speaks back about
        # the image without the user having to say something else first.
        await self.connection.send({"type": "response.create"})
        await self.broadcast({
            "type": "frame_sent",
            "n": -1,
            "provider": "openai",
        })
        await self.log(f"📷 image sent to OpenAI ({len(jpeg_bytes)} bytes)", "info")

    # ------------------------------------------------------------------
    # Run the full session
    # ------------------------------------------------------------------

    async def run(self) -> None:
        if not self.api_key:
            await self.log(
                "OPENAI_API_KEY missing in .env — cannot start", "error"
            )
            return

        client = AsyncOpenAI(api_key=self.api_key)
        await self.log(f"Connecting to OpenAI Realtime ({OPENAI_MODEL})...", "info")

        # Make sure the audio worker is alive and start with a clean mic queue
        if not self.bridge.is_alive():
            self.bridge.restart()
            await self.log("Audio worker was dead, restarted", "info")
        dropped = self.bridge.drain_mic()
        await self.log(f"Audio worker ready (drained {dropped} stale mic blocks)", "info")

        try:
            async with client.realtime.connect(model=OPENAI_MODEL) as connection:
                self.connection = connection
                # Configure session
                await connection.send(self._build_session_update_event())
                await self.broadcast({
                    "type": "live_state",
                    "connected": True,
                    "mode": "openai",
                    "provider": "openai",
                    "start_button": self.start_button,
                })
                await self.log("Connected to OpenAI Realtime — speak now", "info")

                # Concurrent tasks
                tasks = [
                    asyncio.create_task(self._send_mic()),
                    asyncio.create_task(self._play_speaker()),
                    asyncio.create_task(self._receive_events()),
                ]
                try:
                    await asyncio.gather(*tasks)
                except asyncio.CancelledError:
                    for t in tasks:
                        t.cancel()
                    raise

        except asyncio.CancelledError:
            await self.log("OpenAI session cancelled", "info")
            raise
        except Exception as exc:
            await self.log(f"OpenAI session error: {exc}", "error")
            traceback.print_exc()
        finally:
            self.connection = None
            await self.broadcast({
                "type": "live_state",
                "connected": False,
                "provider": "openai",
                "start_button": self.start_button,
            })
            await self.log("OpenAI session closed", "info")

    # ------------------------------------------------------------------
    # Mic -> OpenAI
    # ------------------------------------------------------------------

    async def _send_mic(self) -> None:
        mic_gain = float(self.settings.get("audio", {}).get("mic_gain", 6.0))
        muted = 0
        raw_peak = 0
        clean_peak = 0
        while True:
            try:
                data = await self.bridge.read_mic_block()
            except Exception as e:
                self.dlog(f"[oai mic] read error: {e} — restarting worker", "warning")
                self.bridge.restart()
                await asyncio.sleep(0.3)
                continue

            if self.assistant_speaking.is_set():
                muted += 1
                if muted % 20 == 0:
                    self.dlog(f"[oai mic] muted ({muted} blocks, half-duplex)")
                continue

            arr = np.frombuffer(bytes(data), dtype=np.int16).astype(np.int32)
            if arr.size == 0:
                continue

            raw_peak = max(raw_peak, int(np.abs(arr).max()))
            arr = arr - int(arr.mean())          # DC offset removal
            arr = np.clip(arr * mic_gain, -32768, 32767).astype(np.int16)
            clean_peak = max(clean_peak, int(np.abs(arr).max()))

            # Resample 16 kHz -> 24 kHz (OpenAI Realtime requirement)
            up = resample_16k_to_24k(arr)

            b64 = base64.b64encode(up.tobytes()).decode("ascii")
            try:
                await self.connection.send({
                    "type": "input_audio_buffer.append",
                    "audio": b64,
                })
                self._mic_blocks_sent += 1
            except Exception as e:
                self.dlog(f"[oai mic] send failed: {e}", "warning")
                await asyncio.sleep(0.1)
                continue

            if self._mic_blocks_sent % 10 == 0:
                raw_pct = (raw_peak / 32767.0) * 100.0
                clean_pct = (clean_peak / 32767.0) * 100.0
                self.dlog(
                    f"[oai mic] sent {self._mic_blocks_sent} blocks "
                    f"({self._mic_blocks_sent * BLOCK / MIC_RATE:.1f}s) "
                    f"raw_peak={raw_peak} ({raw_pct:.1f}%) "
                    f"clean_peak={clean_peak} ({clean_pct:.1f}%) "
                    f"upsample 16k->24k"
                )
                raw_peak = 0
                clean_peak = 0

    # ------------------------------------------------------------------
    # OpenAI audio -> speaker
    # ------------------------------------------------------------------

    async def _play_speaker(self) -> None:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self.speaker_queue.get(), timeout=0.2
                )
            except asyncio.TimeoutError:
                if (
                    self.assistant_speaking.is_set()
                    and self.speaker_queue.empty()
                    and not self.bridge.speaker_pending()
                ):
                    await asyncio.sleep(0.25)
                    self.assistant_speaking.clear()
                    self.dlog("[oai] speaker drained, mic un-muted")
                continue
            await asyncio.to_thread(self.bridge.write_speaker, chunk)

    # ------------------------------------------------------------------
    # OpenAI -> us  (event dispatch)
    # ------------------------------------------------------------------

    async def _receive_events(self) -> None:
        async for event in self.connection:
            ev_type = getattr(event, "type", None) or (
                event.get("type") if isinstance(event, dict) else None
            )
            if ev_type is None:
                continue
            try:
                await self._handle_event(ev_type, event)
            except Exception as exc:
                self.dlog(f"[oai] handler error on {ev_type}: {exc}", "error")
                traceback.print_exc()

    def _ev_attr(self, event: Any, name: str, default: Any = None) -> Any:
        """Read an attribute or dict key off a Realtime event."""
        v = getattr(event, name, None)
        if v is None and isinstance(event, dict):
            v = event.get(name)
        return default if v is None else v

    async def _handle_event(self, ev_type: str, event: Any) -> None:
        # ---- session lifecycle ----
        if ev_type in ("session.created", "session.updated"):
            self.dlog(f"[oai] {ev_type}")
            return

        if ev_type == "error":
            err = self._ev_attr(event, "error", {})
            await self.log(f"[oai error] {err}", "error")
            return

        # ---- assistant audio out ----
        if ev_type in ("response.audio.delta", "response.output_audio.delta"):
            audio_b64 = self._ev_attr(event, "delta", "")
            if audio_b64:
                try:
                    pcm = base64.b64decode(audio_b64)
                except Exception:
                    return
                self.assistant_speaking.set()
                await self.speaker_queue.put(pcm)
                self._audio_chunks_received += 1
            return

        # ---- assistant transcript out (streaming) ----
        if ev_type in (
            "response.audio_transcript.delta",
            "response.output_audio.transcript.delta",
            "response.output_audio_transcript.delta",
        ):
            text = self._ev_attr(event, "delta", "")
            if text:
                await self.broadcast({
                    "type": "transcript",
                    "role": "openai",
                    "text": text,
                })
            return

        # ---- user transcript (server VAD + Whisper) ----
        if ev_type == "conversation.item.input_audio_transcription.delta":
            text = self._ev_attr(event, "delta", "")
            if text:
                await self.broadcast({
                    "type": "transcript",
                    "role": "user",
                    "text": text,
                })
            return

        if ev_type == "conversation.item.input_audio_transcription.completed":
            text = self._ev_attr(event, "transcript", "")
            self.dlog(f"[oai] USER said: {text!r}")
            return

        # ---- VAD speech boundaries ----
        if ev_type == "input_audio_buffer.speech_started":
            # User is talking: drop any pending assistant audio (barge-in)
            dropped = self._flush_speaker()
            if dropped:
                self.dlog(f"[oai] user spoke — dropped {dropped} queued chunks")
                self.assistant_speaking.clear()
                await self.broadcast({"type": "interrupted"})
            return

        if ev_type == "input_audio_buffer.speech_stopped":
            return

        # ---- response.created / response.done ----
        if ev_type == "response.created":
            return

        if ev_type == "response.done":
            await self.broadcast({"type": "turn_complete"})
            return

        # ---- function call (streaming args, then done) ----
        if ev_type == "response.function_call_arguments.delta":
            call_id = self._ev_attr(event, "call_id", "")
            delta = self._ev_attr(event, "delta", "")
            if call_id and delta:
                self._tool_call_args[call_id] = (
                    self._tool_call_args.get(call_id, "") + delta
                )
            # name comes through on the conversation.item.created for the
            # function call — capture below
            return

        if ev_type == "response.function_call_arguments.done":
            call_id = self._ev_attr(event, "call_id", "")
            args_str = self._ev_attr(event, "arguments", "") or \
                       self._tool_call_args.pop(call_id, "")
            name = self._ev_attr(event, "name", "") or \
                   self._tool_call_names.pop(call_id, "")
            await self._dispatch_tool_call(call_id, name, args_str)
            return

        # ---- conversation.item.created : capture function-call name ----
        if ev_type == "conversation.item.created":
            item = self._ev_attr(event, "item", {})
            # `item` may be a pydantic model — coerce to dict if needed
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if isinstance(item, dict) and item.get("type") == "function_call":
                cid = item.get("call_id") or item.get("id") or ""
                nm = item.get("name") or ""
                if cid and nm:
                    self._tool_call_names[cid] = nm
            return

        # ---- everything else, just log at debug volume ----
        self.dlog(f"[oai evt] {ev_type}")

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tool_call(
        self, call_id: str, name: str, args_str: str
    ) -> None:
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            args = {}

        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            result: dict[str, Any] = {"error": f"unknown tool {name!r}"}
            self.dlog(f"[oai TOOL] unknown: {name}", "warning")
        else:
            try:
                result = await handler(args)
                self.dlog(f"[oai TOOL] {name}({args}) -> {str(result)[:200]}")
            except Exception as e:
                result = {"error": str(e)}
                self.dlog(f"[oai TOOL] {name} ERROR: {e}", "error")

        # Surface to the dashboard transcript (same shape as Gemini)
        await self.broadcast({
            "type": "tool_call",
            "name": name,
            "args": args,
            "provider": "openai",
        })

        # Send the result back to OpenAI as a function_call_output item,
        # then trigger a fresh response so it speaks the result.
        if call_id:
            await self.connection.send({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                },
            })
            await self.connection.send({"type": "response.create"})


# ----------------------------------------------------------------------
# Convenience entry-point that wires settings, key, and shared deps
# ----------------------------------------------------------------------

async def run_openai_session(
    bridge: AudioBridge,
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    log: Callable[[str, str], Awaitable[None]],
    dlog: Callable[..., None],
    settings: Optional[dict[str, Any]] = None,
) -> "OpenAISession":
    """Build and run a single OpenAI Realtime session.

    Returns the OpenAISession instance once `connect()` has succeeded
    so callers can inject images via `session.send_image(jpeg)`.

    Note: this coroutine *runs* the session — it only returns when the
    session ends (CancelledError, network failure, etc.). Use
    `asyncio.create_task(...)` to run it in the background and keep a
    reference to the session via the `session_holder` pattern (see
    dashboard.server).
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    settings = settings or load_openai_settings()
    sess = OpenAISession(
        api_key=api_key,
        bridge=bridge,
        settings=settings,
        broadcast=broadcast,
        log=log,
        dlog=dlog,
    )
    await sess.run()
    return sess
