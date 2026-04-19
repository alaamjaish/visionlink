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
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

import sounddevice as sd
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "static"
CAPTURES_DIR = STATIC_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.1-flash-live-preview"
MIC_RATE = 16000
SPEAKER_RATE = 24000
BLOCK = 1600  # 100 ms at 16 kHz


app = FastAPI(title="VisionLink Command Center")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


ws_clients: set[WebSocket] = set()
live_task: Optional[asyncio.Task] = None
# Reference to the currently-open Gemini Live session (for snap/video frame injection)
current_session = None  # type: ignore
current_camera = None   # type: ignore  # SessionCamera instance during snap/video modes
live_mode: str = "audio"   # "audio" | "snap" | "video"
last_frame_jpeg: Optional[bytes] = None
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
    # Tuned VAD: low sensitivity + 800ms silence before Gemini decides the user is done.
    # Less-sensitive detection avoids false triggers from I2S mic noise / speaker bleed.
    vad = types.AutomaticActivityDetection(
        disabled=False,
        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
        prefix_padding_ms=200,
        silence_duration_ms=800,
    )
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=vad
        ),
        system_instruction=types.Content(parts=[types.Part.from_text(
            text=(
                "You are VisionLink, a friendly wearable assistant for a factory "
                "worker. Keep replies short and spoken-friendly."
            )
        )]),
    )

    mic_stream = sd.RawInputStream(
        samplerate=MIC_RATE, channels=1, dtype="int16", blocksize=BLOCK
    )
    spk_stream = sd.RawOutputStream(
        samplerate=SPEAKER_RATE, channels=1, dtype="int16"
    )
    mic_stream.start()
    spk_stream.start()
    await log("Mic + speaker streams open")

    # Half-duplex + interruptable speaker playback:
    # - Gemini's audio chunks go into a queue
    # - A dedicated player task drains the queue to the speaker
    # - While the queue has audio, mic sending is MUTED (prevents echo feedback)
    # - On 'interrupted' event we drain the queue directly from the receive loop
    speaker_queue: asyncio.Queue[bytes] = asyncio.Queue()
    gemini_speaking = asyncio.Event()     # set while there is pending Gemini audio

    def flush_speaker_queue() -> int:
        dropped = 0
        while not speaker_queue.empty():
            try:
                speaker_queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
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
                """Read mic and send to Gemini, but stay silent while Gemini is talking."""
                sent = 0
                muted = 0
                while True:
                    data, _ = await loop.run_in_executor(None, mic_stream.read, BLOCK)
                    if gemini_speaking.is_set():
                        muted += 1
                        if muted % 20 == 0:
                            print(f"[mic   ] muted ({muted} blocks, half-duplex)", flush=True)
                        continue
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=bytes(data),
                            mime_type=f"audio/pcm;rate={MIC_RATE}",
                        )
                    )
                    sent += 1
                    if sent % 100 == 0:
                        print(f"[mic   ] sent {sent} blocks to Gemini", flush=True)

            async def play_speaker() -> None:
                """Drain speaker queue to the output stream; un-mute mic when idle."""
                while True:
                    try:
                        chunk = await asyncio.wait_for(speaker_queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        if gemini_speaking.is_set() and speaker_queue.empty():
                            # Queue drained: let pending ALSA buffer finish, then un-mute mic
                            await asyncio.sleep(0.25)
                            gemini_speaking.clear()
                            print("[spk   ] queue drained, mic un-muted", flush=True)
                        continue
                    await asyncio.to_thread(spk_stream.write, chunk)

            async def receive_turns() -> None:
                """Outer loop: session.receive() returns per-turn, so keep re-entering it."""
                turn_num = 0
                while True:
                    turn_num += 1
                    print(f"[turn  ] #{turn_num} waiting for Gemini...", flush=True)
                    msg_count = 0
                    async for message in session.receive():
                        msg_count += 1
                        if getattr(message, "data", None):
                            gemini_speaking.set()
                            await speaker_queue.put(message.data)
                        sc = getattr(message, "server_content", None)
                        if sc is None:
                            continue
                        it = getattr(sc, "input_transcription", None)
                        ot = getattr(sc, "output_transcription", None)
                        if it and it.text:
                            print(f"[user  ] {it.text!r}", flush=True)
                            await broadcast(
                                {"type": "transcript", "role": "user", "text": it.text}
                            )
                        if ot and ot.text:
                            print(f"[gemini] {ot.text!r}", flush=True)
                            await broadcast(
                                {"type": "transcript", "role": "gemini", "text": ot.text}
                            )
                        if getattr(sc, "interrupted", False):
                            dropped = flush_speaker_queue()
                            gemini_speaking.clear()
                            print(f"[event ] INTERRUPTED - dropped {dropped} queued chunks", flush=True)
                            await broadcast({"type": "interrupted"})
                        if getattr(sc, "turn_complete", False):
                            print(f"[event ] turn_complete (turn #{turn_num}, {msg_count} msgs)", flush=True)
                            await broadcast({"type": "turn_complete"})
                    # session.receive() exited for this turn; outer while True starts the next one
                    print(f"[turn  ] #{turn_num} ended, looping for next turn", flush=True)

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
        try:
            mic_stream.stop(); mic_stream.close()
        except Exception:
            pass
        try:
            spk_stream.stop(); spk_stream.close()
        except Exception:
            pass
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


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "has_api_key": bool(API_KEY),
        "model": MODEL,
        "live_connected": state["live_connected"],
        "clients": len(ws_clients),
    })
