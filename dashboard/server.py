"""
VisionLink Command Center — web dashboard.

Run:
    cd ~/Desktop/visionlink
    python3 -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8000

Then open http://<pi-ip>:8000 from any browser on the same Wi-Fi.

What it gives you:
  - Start / Stop a Gemini Live voice session (talk through the I2S mic, hear
    the reply through the I2S speaker) with transcripts streaming into the UI
  - Take a photo with the Pi Camera v3 and view it inline
  - Live status lights, rolling log
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

from dashboard.audio_bridge import AudioBridge
from dashboard.audio_worker import BLOCK, MIC_RATE, SPEAKER_RATE
from src.ai.tools import TOOL_HANDLERS, WORKER_NAME, build_tools


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "static"
CAPTURES_DIR = STATIC_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.1-flash-live-preview"
# MIC_RATE / SPEAKER_RATE / BLOCK come from dashboard.audio_worker
# so the parent and worker can never disagree on format.


# ---------- Agent settings (live-tunable from the UI) ----------

AGENT_SETTINGS_PATH = PROJECT_ROOT / "dashboard" / "agent_settings.json"

DEFAULT_SYSTEM_PROMPT = (
    f"You are VisionLink, a wearable assistant talking to {WORKER_NAME} "
    f"on the factory floor.\n\n"
    "==================================================================\n"
    "ABSOLUTE RULE 1 — NEVER LIE ABOUT COMPLETING ACTIONS:\n"
    "If you say 'I logged it', 'I marked it done', 'I submitted the request', "
    "'I've added it', or any similar past-tense completion phrase, you MUST "
    "have actually called the matching tool first. Saying you did something "
    "without calling the tool is the WORST POSSIBLE FAILURE. If you can't "
    "call a tool for any reason, say literally: 'Sorry, I couldn't log that — "
    "let me try again' and stop. NEVER fake completion.\n"
    "==================================================================\n\n"
    "ABSOLUTE RULE 2 — VERB TRIGGERS:\n"
    "These exact spoken verbs from the worker REQUIRE you to call the matching "
    "tool. The topic does NOT matter (factory part, personal item, anything "
    "the worker mentions — call the tool):\n\n"
    "  'log' / 'log this' / 'log an incident' / 'add an incident' / 'record this'\n"
    "       → log_incident\n"
    "  'mark X done' / 'mark X complete' / 'I finished X' / 'X is done'\n"
    "       → mark_task_complete\n"
    "  'what's on my list' / 'what do I have' / 'my tasks' / 'my assignments'\n"
    "       → get_my_assignments\n"
    "  'request X' / 'order X' / 'I need X' / 'send me X' / 'get me X'\n"
    "       → request_part\n"
    "  'tell me about X' / 'what's the torque' / 'specs on X' / any part question\n"
    "       → lookup_component\n"
    "  'send report' / 'email X to Y' / 'send the X report to the CEO'\n"
    "       → send_report\n\n"
    "If you hear ANY of these triggers, you MUST emit the tool call. "
    "Do not chat instead. Do not pretend. Do not collect more info first "
    "unless the tool is missing a required parameter — and even then, only "
    "ask ONE clarifying question, then call the tool.\n\n"
    "ABSOLUTE RULE 3 — THE INFO-COLLECTION TRAP:\n"
    "If you ask the worker for clarifying info (location, severity, etc.) "
    "and they answer, your VERY NEXT action MUST be the tool call. Do not "
    "summarize, do not say 'got it' without then calling. The pattern is:\n"
    "  Worker: 'Log incident — broken phone'\n"
    "  You: 'On it, where are you?'\n"
    "  Worker: 'Main office'\n"
    "  You: [CALL log_incident immediately] then say 'Done — broken phone "
    "logged in main office.'\n\n"
    "==================================================================\n\n"
    "TOOLS AVAILABLE (signatures):\n\n"
    "1. lookup_component(query: str) → factory parts catalog (read-only)\n"
    "   Examples: 'pump A3', 'main engine bolt', 'PMP-A3-IMP'\n\n"
    "2. log_incident(description: str, category?: str, severity?: str, location?: str) → write\n"
    "   Categories: safety | equipment | leak | damage | other (default: other)\n"
    "   Severities: low | medium | high | critical (default: medium)\n"
    "   Examples that MUST trigger this tool:\n"
    "     - 'Log a leak on conveyor 4'\n"
    "     - 'I broke my phone' (description='broken phone', category='damage')\n"
    "     - 'There's a slip hazard near valve B7'\n"
    "     - 'Add an incident: motor smells burnt'\n\n"
    "3. mark_task_complete(task_query: str) → write\n"
    "   Examples: 'pump A3 inspection', 'bearing service', 'valve B7 seal'\n"
    "   If response has ambiguous=true, READ THE TASK TITLES BACK and "
    "ask which one — never guess.\n\n"
    "4. get_my_assignments(include_complete?: bool) → read-only\n"
    "   Default: returns only pending tasks. Set include_complete=true if "
    "the worker says 'including done' or 'everything'.\n\n"
    "5. request_part(part_query: str, quantity?: int, urgency?: str, reason?: str) → write\n"
    "   Urgencies: normal | urgent | critical (default: normal)\n\n"
    "6. send_report(report_name: str, recipient_role?: str, recipient_name?: str, recipient_email?: str, custom_message?: str) → write (sends email)\n"
    "   Recipients are found from the managers DB by role (preferred) or name.\n"
    "   Templates are found by name (e.g. 'daily operations report', 'incident report', 'quick note').\n"
    "   Examples that MUST trigger this tool:\n"
    "     - 'Send the daily operations report to the CEO'\n"
    "       → send_report(report_name='daily operations report', recipient_role='CEO')\n"
    "     - 'Email the incident report to the supervisor'\n"
    "       → send_report(report_name='incident report', recipient_role='supervisor')\n"
    "     - 'Send a quick note to the accountant: budget approval needed'\n"
    "       → send_report(report_name='quick note', recipient_role='accountant', custom_message='budget approval needed')\n\n"
    "==================================================================\n\n"
    "WHEN NOT TO CALL ANY TOOL:\n"
    "- Pure greetings: 'hi', 'hello', 'how are you', 'thanks', 'goodbye'\n"
    "- The worker is acknowledging your reply ('ok', 'thanks', 'cool')\n"
    "- Questions about you, the system: 'are you there', 'can you hear me'\n"
    "When in doubt, CALL THE TOOL. False positive is fine — false negative is a lie.\n\n"
    "BEFORE CALLING A TOOL:\n"
    "Say a short filler ('on it', 'one sec', 'logging that now') so the "
    "worker knows you heard them. Then call the tool. Then confirm.\n\n"
    "AFTER A TOOL RETURNS:\n"
    "- Use ONLY the data in the response. Never invent fields.\n"
    "- If a tool returns an error or empty result, say so plainly.\n"
    "- For writes, confirm explicitly: 'Done, broken phone logged in the "
    "main office.' / 'Pump A3 inspection marked complete.' / "
    "'Submitted, urgent gasket request.'\n\n"
    "STYLE:\n"
    "- 1-2 sentences, spoken-friendly.\n"
    "- Numbers as words ('forty-two newton metres', not '42 Nm').\n"
    "- Don't read part codes, IDs, or UUIDs aloud unless asked."
)

DEFAULT_AGENT_SETTINGS: dict[str, Any] = {
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "vad": {
        "start_sensitivity": "HIGH",   # HIGH | MEDIUM | LOW
        "end_sensitivity":   "HIGH",
        "prefix_padding_ms": 200,
        "silence_duration_ms": 500,
    },
    "audio": {
        "mic_gain": 6.0,  # software gain applied to mic blocks before sending
        # speaker_gain lives in the worker subprocess (audio_worker.py) and
        # is NOT live-tunable from here — we surface its value for visibility.
    },
}

agent_settings: dict[str, Any] = json.loads(json.dumps(DEFAULT_AGENT_SETTINGS))


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_agent_settings() -> None:
    global agent_settings
    if not AGENT_SETTINGS_PATH.exists():
        agent_settings = json.loads(json.dumps(DEFAULT_AGENT_SETTINGS))
        return
    try:
        loaded = json.loads(AGENT_SETTINGS_PATH.read_text())
        agent_settings = _deep_merge(DEFAULT_AGENT_SETTINGS, loaded)
        print(f"[agent_settings] loaded from {AGENT_SETTINGS_PATH}", flush=True)
    except Exception as e:
        print(f"[agent_settings] load failed: {e!r} — using defaults", flush=True)
        agent_settings = json.loads(json.dumps(DEFAULT_AGENT_SETTINGS))


def _save_agent_settings() -> None:
    AGENT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_SETTINGS_PATH.write_text(json.dumps(agent_settings, indent=2))


def _describe_tools() -> list[dict[str, Any]]:
    """Read-only schema view of every tool the agent has access to."""
    out = []
    for tool in build_tools():
        for fd in tool.function_declarations or []:
            out.append({
                "name": fd.name,
                "description": fd.description,
                "parameters": fd.parameters.model_dump(exclude_none=True)
                              if fd.parameters else None,
            })
    return out


_VAD_START_MAP = {
    "HIGH":   types.StartSensitivity.START_SENSITIVITY_HIGH,
    "LOW":    types.StartSensitivity.START_SENSITIVITY_LOW,
}
_VAD_END_MAP = {
    "HIGH":   types.EndSensitivity.END_SENSITIVITY_HIGH,
    "LOW":    types.EndSensitivity.END_SENSITIVITY_LOW,
}


_load_agent_settings()


app = FastAPI(title="VisionLink Command Center")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


ws_clients: set[WebSocket] = set()
live_task: Optional[asyncio.Task] = None
# Reference to the currently-open Gemini Live session (for snap/video frame injection)
current_session = None  # type: ignore
current_camera = None   # type: ignore  # SessionCamera instance during snap/video modes
live_mode: str = "audio"   # "audio" | "snap" | "video"
last_frame_jpeg: Optional[bytes] = None

# Audio I/O lives in a subprocess so an ALSA `plug` device assertion
# (the C-level pcm_plugin.c crash) only kills the child, not the FastAPI
# server. The bridge auto-restarts the worker on death.
_audio_bridge: Optional[AudioBridge] = None


def get_bridge() -> AudioBridge:
    global _audio_bridge
    if _audio_bridge is None:
        _audio_bridge = AudioBridge()
    return _audio_bridge


@app.on_event("startup")
async def _startup_audio():
    # Spawn the audio worker eagerly so the first START LIVE click is fast
    get_bridge()
    print("[startup] audio bridge online", flush=True)


@app.on_event("shutdown")
async def _shutdown_audio():
    global _audio_bridge
    if _audio_bridge is not None:
        _audio_bridge.shutdown()
        _audio_bridge = None
state = {
    "live_connected": False,
    "latest_photo": None,
    "model": MODEL,
    "mode": "audio",
}


async def broadcast(event: dict) -> None:
    dead = []
    for ws in list(ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)


async def log(msg: str, level: str = "info") -> None:
    print(f"[{level}] {msg}", flush=True)
    await broadcast({"type": "log", "level": level, "msg": msg, "ts": time.time()})


def dlog(msg: str, level: str = "debug") -> None:
    """Sync-friendly debug log: prints AND fires a broadcast task in the background.

    Use from inside hot paths (mic loop, receive loop) where awaiting broadcast
    would be noisy. The dashboard renders it in the Log panel like normal.
    """
    print(f"[{level}] {msg}", flush=True)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(broadcast(
        {"type": "log", "level": level, "msg": msg, "ts": time.time()}
    ))


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    ws_clients.add(ws)
    await ws.send_json({"type": "state", **state})
    try:
        while True:
            # We only push; keep connection alive.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)


class SessionCamera:
    """Owns a long-running Picamera2 instance for fast JPEG grabs during a session."""

    def __init__(self) -> None:
        self._cam = None

    def open(self) -> None:
        from picamera2 import Picamera2
        cam = Picamera2()
        cfg = cam.create_still_configuration(main={"size": (1024, 576)})
        cam.configure(cfg)
        cam.start()
        time.sleep(0.4)  # exposure settle
        self._cam = cam

    def close(self) -> None:
        if self._cam is not None:
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None

    def grab_jpeg(self) -> bytes:
        if self._cam is None:
            raise RuntimeError("camera not open")
        import io
        buf = io.BytesIO()
        self._cam.capture_file(buf, format="jpeg")
        return buf.getvalue()


async def run_live_session(mode: str = "audio") -> None:
    if not API_KEY:
        await log("GEMINI_API_KEY missing in .env — cannot start", "error")
        return

    global current_session, live_mode, last_frame_jpeg
    live_mode = mode if mode in ("audio", "snap", "video") else "audio"
    state["mode"] = live_mode
    last_frame_jpeg = None
    await log(f"Starting Live session — mode={live_mode}")

    client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
    # Read latest tunable values from agent_settings (mutated via /api/agent/settings)
    vad_cfg = agent_settings["vad"]
    vad = types.AutomaticActivityDetection(
        disabled=False,
        start_of_speech_sensitivity=_VAD_START_MAP.get(
            vad_cfg["start_sensitivity"],
            types.StartSensitivity.START_SENSITIVITY_HIGH,
        ),
        end_of_speech_sensitivity=_VAD_END_MAP.get(
            vad_cfg["end_sensitivity"],
            types.EndSensitivity.END_SENSITIVITY_HIGH,
        ),
        prefix_padding_ms=int(vad_cfg["prefix_padding_ms"]),
        silence_duration_ms=int(vad_cfg["silence_duration_ms"]),
    )
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=vad
        ),
        tools=build_tools(),
        # tool_config is rejected by LiveConnectConfig in google-genai 1.73
        # (extra_forbidden). Live API uses tools=[...] only — no separate
        # function_calling mode knob. Tool-calling reliability is driven by
        # the system prompt and example density.
        system_instruction=types.Content(parts=[types.Part.from_text(
            text=agent_settings["system_prompt"]
        )]),
    )

    # Audio I/O is in a subprocess (see dashboard/audio_worker.py). Drain the
    # mic queue so this session starts with a clean buffer (no stale audio).
    bridge = get_bridge()
    if not bridge.is_alive():
        bridge.restart()
        await log("Audio worker was dead, restarted")
    dropped_stale = bridge.drain_mic()
    await log(
        f"Audio worker ready (drained {dropped_stale} stale mic blocks)"
    )

    # Half-duplex + interruptable speaker playback:
    # - Gemini's audio chunks go into a queue
    # - A dedicated player task drains the queue to the speaker
    # - While the queue has audio, mic sending is MUTED (prevents echo feedback)
    # - On 'interrupted' event we drain the queue directly from the receive loop
    speaker_queue: asyncio.Queue[bytes] = asyncio.Queue()
    gemini_speaking = asyncio.Event()     # set while there is pending Gemini audio

    def flush_speaker_queue() -> int:
        """Drop everything still queued for the speaker (asyncio + bridge)."""
        dropped = 0
        while not speaker_queue.empty():
            try:
                speaker_queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
        dropped += bridge.flush_speaker()
        return dropped

    # Open the session camera if the mode needs it
    global current_camera
    session_cam: Optional[SessionCamera] = None
    if live_mode in ("snap", "video"):
        try:
            session_cam = SessionCamera()
            await asyncio.to_thread(session_cam.open)
            current_camera = session_cam
            await log(f"Session camera opened ({live_mode} mode)")
        except Exception as exc:
            await log(f"Could not open camera: {exc} — falling back to audio", "error")
            session_cam = None
            current_camera = None
            live_mode = "audio"
            state["mode"] = "audio"

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            current_session = session
            state["live_connected"] = True
            await broadcast({"type": "live_state", "connected": True, "mode": live_mode})
            await log(f"Connected to Gemini Live ({live_mode}) — speak now")

            loop = asyncio.get_running_loop()

            async def video_stream() -> None:
                """Capture a JPEG once a second and send it to Gemini as a video frame."""
                global last_frame_jpeg
                if session_cam is None:
                    return
                frame_num = 0
                while True:
                    await asyncio.sleep(1.0)
                    try:
                        jpeg = await asyncio.to_thread(session_cam.grab_jpeg)
                        last_frame_jpeg = jpeg
                        await session.send_realtime_input(
                            video=types.Blob(data=jpeg, mime_type="image/jpeg")
                        )
                        frame_num += 1
                        if frame_num % 5 == 0:
                            print(f"[video ] sent frame #{frame_num} ({len(jpeg)} bytes)", flush=True)
                        await broadcast({"type": "frame_sent", "n": frame_num})
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"[video ] error: {e}", flush=True)

            async def send_mic() -> None:
                """Read mic from the audio worker and send to Gemini, mute while Gemini talks.

                The SPH0645 I2S mic delivers a steady DC offset (~2000 in int16)
                even when silent, which buries the voice signal and confuses
                Gemini's VAD. We remove the DC offset (subtract block mean)
                and apply a fixed gain so voice reaches ~50% full scale.
                """
                import numpy as np
                MIC_GAIN = float(agent_settings["audio"]["mic_gain"])
                sent = 0
                muted = 0
                raw_peak = 0
                clean_peak = 0
                rolling_n = 0
                while True:
                    try:
                        data = await bridge.read_mic_block()
                    except Exception as e:
                        dlog(f"mic read error: {e} — restarting audio worker")
                        bridge.restart()
                        await asyncio.sleep(0.4)
                        continue
                    if gemini_speaking.is_set():
                        muted += 1
                        if muted % 20 == 0:
                            dlog(f"mic muted ({muted} blocks, half-duplex while Gemini talks)")
                        continue
                    raw = bytes(data)
                    arr = np.frombuffer(raw, dtype=np.int16).astype(np.int32)
                    if arr.size:
                        raw_peak = max(raw_peak, int(np.abs(arr).max()))
                        arr = arr - int(arr.mean())
                        arr = np.clip(arr * MIC_GAIN, -32768, 32767).astype(np.int16)
                        clean_peak = max(clean_peak, int(np.abs(arr).max()))
                        rolling_n += 1
                    out = arr.tobytes()
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=out,
                            mime_type=f"audio/pcm;rate={MIC_RATE}",
                        )
                    )
                    sent += 1
                    if sent % 10 == 0:
                        raw_pct = (raw_peak / 32767.0) * 100.0
                        clean_pct = (clean_peak / 32767.0) * 100.0
                        dlog(
                            f"mic sent {sent} ({sent*BLOCK/MIC_RATE:.1f}s) "
                            f"raw_peak={raw_peak} ({raw_pct:.1f}%) "
                            f"clean_peak={clean_peak} ({clean_pct:.1f}%)"
                        )
                        raw_peak = 0
                        clean_peak = 0
                        rolling_n = 0

            async def play_speaker() -> None:
                """Forward Gemini audio chunks to the audio-worker subprocess."""
                while True:
                    try:
                        chunk = await asyncio.wait_for(speaker_queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        # Idle: if queue is empty AND the bridge has nothing
                        # left to play, un-mute the mic.
                        if (gemini_speaking.is_set()
                                and speaker_queue.empty()
                                and not bridge.speaker_pending()):
                            await asyncio.sleep(0.25)
                            gemini_speaking.clear()
                            dlog("speaker queue drained, mic un-muted")
                        continue
                    # write_speaker can block up to 500 ms when the worker queue
                    # is full — run it off the event loop so the mic/receive
                    # tasks aren't paused.
                    await asyncio.to_thread(bridge.write_speaker, chunk)

            async def receive_turns() -> None:
                """Outer loop: session.receive() returns per-turn, so keep re-entering it."""
                turn_num = 0
                while True:
                    turn_num += 1
                    dlog(f"turn #{turn_num} waiting for Gemini...")
                    msg_count = 0
                    async for message in session.receive():
                        msg_count += 1

                        if msg_count <= 30 or msg_count % 50 == 0:
                            populated = []
                            for a in dir(message):
                                if a.startswith("_"):
                                    continue
                                try:
                                    v = getattr(message, a)
                                except Exception:
                                    continue
                                if v is None or callable(v):
                                    continue
                                populated.append(a)
                            dlog(f"recv #{msg_count} attrs={populated}")

                        tc = getattr(message, "tool_call", None)
                        if tc and getattr(tc, "function_calls", None):
                            responses = []
                            for fc in tc.function_calls:
                                args_dict = dict(fc.args or {})
                                handler = TOOL_HANDLERS.get(fc.name)
                                if handler is None:
                                    result = {"error": f"unknown tool {fc.name}"}
                                    dlog(f"TOOL unknown: {fc.name}", "warning")
                                else:
                                    try:
                                        result = await handler(args_dict)
                                        dlog(
                                            f"TOOL {fc.name}({args_dict}) -> "
                                            f"{str(result)[:200]}"
                                        )
                                    except Exception as e:
                                        result = {"error": str(e)}
                                        dlog(f"TOOL {fc.name} ERROR: {e}", "error")
                                responses.append(types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": result},
                                ))
                            await session.send_tool_response(
                                function_responses=responses
                            )
                            await broadcast({
                                "type": "tool_call",
                                "name": tc.function_calls[0].name,
                                "args": dict(tc.function_calls[0].args or {}),
                            })
                            continue

                        if getattr(message, "data", None):
                            gemini_speaking.set()
                            await speaker_queue.put(message.data)
                        sc = getattr(message, "server_content", None)
                        if sc is None:
                            continue
                        it = getattr(sc, "input_transcription", None)
                        ot = getattr(sc, "output_transcription", None)
                        if it and it.text:
                            dlog(f"USER said: {it.text!r}")
                            await broadcast(
                                {"type": "transcript", "role": "user", "text": it.text}
                            )
                        if ot and ot.text:
                            dlog(f"GEMINI said: {ot.text!r}")
                            await broadcast(
                                {"type": "transcript", "role": "gemini", "text": ot.text}
                            )
                        if getattr(sc, "interrupted", False):
                            dropped = flush_speaker_queue()
                            gemini_speaking.clear()
                            dlog(f"INTERRUPTED — dropped {dropped} queued speaker chunks")
                            await broadcast({"type": "interrupted"})
                        if getattr(sc, "turn_complete", False):
                            dlog(f"turn_complete (turn #{turn_num}, {msg_count} msgs received)")
                            await broadcast({"type": "turn_complete"})
                    dlog(f"turn #{turn_num} ended — looping for next turn")

            tasks = [send_mic(), play_speaker(), receive_turns()]
            if live_mode == "video" and session_cam is not None:
                tasks.append(video_stream())
            await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await log("Live session cancelled")
    except Exception as exc:
        await log(f"Live session error: {exc}", "error")
        traceback.print_exc()
    finally:
        current_session = None
        current_camera = None
        # Audio streams live in the worker subprocess. The session ends here
        # but the worker keeps running; next session reuses it (after drain_mic).
        if session_cam is not None:
            try:
                await asyncio.to_thread(session_cam.close)
            except Exception:
                pass
        state["live_connected"] = False
        state["mode"] = "audio"
        await broadcast({"type": "live_state", "connected": False})
        await log("Live session closed")


@app.post("/api/live/start")
async def live_start(mode: str = "audio") -> JSONResponse:
    global live_task
    if live_task and not live_task.done():
        return JSONResponse({"status": "already_running"})
    if mode not in ("audio", "snap", "video"):
        mode = "audio"
    live_task = asyncio.create_task(run_live_session(mode=mode))
    return JSONResponse({"status": "starting", "mode": mode})


@app.post("/api/live/snap")
async def live_snap() -> JSONResponse:
    """Grab a frame from the session camera and send it to the live Gemini session."""
    global last_frame_jpeg
    sess = current_session
    if sess is None:
        return JSONResponse({"error": "no active live session"}, status_code=400)
    if live_mode == "audio":
        return JSONResponse(
            {"error": "session started in audio-only mode — restart with Snap or Video"},
            status_code=400,
        )
    try:
        if current_camera is None:
            return JSONResponse({"error": "session camera not open"}, status_code=400)
        jpeg = await asyncio.to_thread(current_camera.grab_jpeg)
        await sess.send_realtime_input(
            video=types.Blob(data=jpeg, mime_type="image/jpeg")
        )
        last_frame_jpeg = jpeg
        await log(f"Snap sent to Gemini ({len(jpeg)} bytes)")
        await broadcast({"type": "frame_sent", "n": -1})
        return JSONResponse({"ok": True, "bytes": len(jpeg)})
    except Exception as exc:
        traceback.print_exc()
        await log(f"Snap failed: {exc}", "error")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/live/frame")
async def live_frame():
    """Return the latest frame sent to Gemini (used by the dashboard preview)."""
    if last_frame_jpeg is None:
        return JSONResponse({"error": "no frame"}, status_code=404)
    from fastapi.responses import Response
    return Response(content=last_frame_jpeg, media_type="image/jpeg")


@app.post("/api/live/stop")
async def live_stop() -> JSONResponse:
    global live_task
    if live_task and not live_task.done():
        live_task.cancel()
        return JSONResponse({"status": "stopping"})
    return JSONResponse({"status": "not_running"})


@app.post("/api/photo")
async def photo() -> JSONResponse:
    try:
        from picamera2 import Picamera2
    except ImportError:
        await log("picamera2 not installed", "error")
        return JSONResponse({"error": "picamera2 unavailable"}, status_code=500)

    loop = asyncio.get_running_loop()

    def _capture_transient() -> str:
        cam = Picamera2()
        cfg = cam.create_still_configuration(main={"size": (1280, 720)})
        cam.configure(cfg)
        cam.start()
        time.sleep(0.6)  # let exposure settle
        fname = f"photo_{int(time.time())}.jpg"
        cam.capture_file(str(CAPTURES_DIR / fname))
        cam.close()
        return fname

    def _capture_session() -> str:
        # Re-use the session camera (open in snap/video mode)
        fname = f"photo_{int(time.time())}.jpg"
        current_camera._cam.capture_file(str(CAPTURES_DIR / fname))  # type: ignore[attr-defined]
        return fname

    try:
        if current_camera is not None:
            filename = await loop.run_in_executor(None, _capture_session)
        else:
            filename = await loop.run_in_executor(None, _capture_transient)
        state["latest_photo"] = f"/static/captures/{filename}"
        await log(f"Photo captured: {filename}")
        await broadcast({"type": "photo", "url": state["latest_photo"]})
        return JSONResponse({"url": state["latest_photo"]})
    except Exception as exc:
        traceback.print_exc()
        await log(f"Photo failed: {exc}", "error")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/test_tone")
async def test_tone() -> JSONResponse:
    """Push a calibration tone through the same path Gemini audio uses."""
    bridge = get_bridge()
    bytes_sent = await asyncio.to_thread(bridge.play_test_tone, 880, 0.6, 0.5)
    await log(f"Test tone sent ({bytes_sent} bytes via bridge to speaker)")
    return JSONResponse({"ok": True, "bytes": bytes_sent})


@app.get("/api/agent/settings")
async def agent_settings_get() -> JSONResponse:
    """Snapshot of every tunable + read-only piece of the agent."""
    return JSONResponse({
        "model": MODEL,
        "system_prompt": agent_settings["system_prompt"],
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "vad": agent_settings["vad"],
        "audio": agent_settings["audio"],
        "tools": _describe_tools(),
        "live_active": state["live_connected"],
        "settings_path": str(AGENT_SETTINGS_PATH),
    })


@app.post("/api/agent/settings")
async def agent_settings_set(payload: dict) -> JSONResponse:
    """Update tunable settings. Applied to the NEXT live session.

    Accepts a partial dict — only the keys present are updated.
    """
    try:
        if "system_prompt" in payload:
            sp = str(payload["system_prompt"]).strip()
            if not sp:
                return JSONResponse(
                    {"error": "system_prompt cannot be empty"}, status_code=400
                )
            agent_settings["system_prompt"] = sp
        if "vad" in payload and isinstance(payload["vad"], dict):
            v = agent_settings["vad"]
            for key in ("start_sensitivity", "end_sensitivity"):
                if key in payload["vad"]:
                    val = str(payload["vad"][key]).upper()
                    if val not in ("HIGH", "LOW"):
                        return JSONResponse(
                            {"error": f"vad.{key} must be HIGH or LOW"},
                            status_code=400,
                        )
                    v[key] = val
            for key in ("prefix_padding_ms", "silence_duration_ms"):
                if key in payload["vad"]:
                    n = int(payload["vad"][key])
                    if not (0 <= n <= 5000):
                        return JSONResponse(
                            {"error": f"vad.{key} must be 0..5000"},
                            status_code=400,
                        )
                    v[key] = n
        if "audio" in payload and isinstance(payload["audio"], dict):
            if "mic_gain" in payload["audio"]:
                g = float(payload["audio"]["mic_gain"])
                if not (0.1 <= g <= 20.0):
                    return JSONResponse(
                        {"error": "audio.mic_gain must be 0.1..20.0"},
                        status_code=400,
                    )
                agent_settings["audio"]["mic_gain"] = g
        if payload.get("reset"):
            globals()["agent_settings"] = json.loads(json.dumps(DEFAULT_AGENT_SETTINGS))
        _save_agent_settings()
        await log("Agent settings updated (takes effect on next live session)")
        await broadcast({"type": "agent_settings_updated"})
        return JSONResponse({
            "ok": True,
            "system_prompt": agent_settings["system_prompt"],
            "vad": agent_settings["vad"],
            "audio": agent_settings["audio"],
            "applies": "next live session — current session keeps its config",
        })
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": f"bad payload: {e}"}, status_code=400)


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "has_api_key": bool(API_KEY),
        "model": MODEL,
        "live_connected": state["live_connected"],
        "clients": len(ws_clients),
    })
