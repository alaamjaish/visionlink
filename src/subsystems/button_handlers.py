"""Six button handlers — the SINGLE source of truth for what each
physical (or on-screen) button does on the VisionLink wearable.

Both the FastAPI dashboard endpoints (/api/button/{n}/{event}) and the
future GPIO callbacks in main.py invoke these functions. New behavior
goes here, not in the GPIO or dashboard layers.

Button map (matches 7TH_MAY_UPDATE.md, with B5/B6 updated 2026-05-08):
  B1 single  → toggle documentation session (start or close)
  B2 single  → take photo (added to open session if any)
  B2 double  → record a short video clip (~5s)
  B3 hold    → record voice note (start on press, upload on release)
  B4 single  → start AI session (audio-only, provider from wearable_settings)
  B5 single  → start AI session with vision (provider+vision_mode from settings)
  B6 single  → no-op (warn — SOS requires double-click)
  B6 double  → trigger SOS panic mode

State lives at module scope and is accessed via thread-safe asyncio
primitives. The handlers are async; callers create_task them.
"""
from __future__ import annotations

import asyncio
import io
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from supabase import Client, create_client


# ---------- module-level state (single-process, single-wearable) ----------

@dataclass
class _ButtonState:
    """Tracks what the wearable is currently doing across button presses."""
    open_session_id: Optional[str] = None
    open_session_label: Optional[str] = None
    voice_note_recording: bool = False
    voice_note_buffer: bytearray = field(default_factory=bytearray)
    voice_note_started_at: float = 0.0
    voice_note_task: Optional[asyncio.Task] = None
    last_b6_single_at: float = 0.0       # for double-click detection
    last_b1_toggle_at: float = 0.0       # cooldown to absorb button bounce
    last_b3_toggle_at: float = 0.0       # cooldown for press-to-toggle voice note
    video_recording: bool = False        # in-progress guard for B2 double (rpicam-vid)
    sos_active_id: Optional[str] = None  # set while a SOS session is running
    sos_task: Optional[asyncio.Task] = None


_state = _ButtonState()
_state_lock = asyncio.Lock()


# ---------- Supabase client ----------

_sb: Optional[Client] = None


def _sb_client() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY missing in .env")
        _sb = create_client(url, key)
    return _sb


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- shared helpers ----------

async def load_wearable_settings() -> dict[str, Any]:
    """Fetch the singleton wearable_settings row. Falls back to defaults
    if the row is missing or Supabase is unreachable."""
    defaults = {
        "id": "current",
        # Default to Gemini — cheap, well-tested, won't burn OpenAI tokens by accident
        "b4_provider": "gemini",
        "b5_provider": "gemini",
        "b5_vision_mode": "snap_on_press",
        "sos_photo_interval_s": 10,
        "sos_max_duration_s": 600,
        "sos_alert_recipient_role": "safety officer",
        "sos_provider": "gemini",
        "worker_id": os.getenv("WORKER_ID", "demo_worker_001"),
        "worker_name": os.getenv("WORKER_NAME", "Alaa"),
    }
    try:
        sb = _sb_client()
        def _q():
            return (sb.table("wearable_settings")
                      .select("*")
                      .eq("id", "current")
                      .limit(1)
                      .execute())
        r = await asyncio.to_thread(_q)
        if r.data:
            return {**defaults, **r.data[0]}
    except Exception as e:
        print(f"[buttons] settings load failed: {e!r} — using defaults", flush=True)
    return defaults


async def _upload_to_storage(
    path: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    """Upload bytes to the session-assets bucket. Returns the storage path."""
    sb = _sb_client()
    def _up():
        sb.storage.from_("session-assets").upload(
            path,
            data,
            {"content-type": content_type, "upsert": "true"},
        )
    await asyncio.to_thread(_up)
    return path


# ============================================================
# B1 — toggle documentation session
# ============================================================

async def b1_doc_session_toggle(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
) -> dict[str, Any]:
    # Cooldown: physical button bounce can fire two falling edges within
    # a few ms, which would open-then-immediately-close (or vice versa).
    # Hardware debounce alone (50 ms) wasn't catching all of it on this
    # board, so we add a soft cooldown — the second toggle within 800 ms
    # is silently ignored.
    B1_COOLDOWN_S = 0.8
    now = time.time()
    if now - _state.last_b1_toggle_at < B1_COOLDOWN_S:
        return {"action": "ignored", "reason": "cooldown — too soon after last toggle"}
    _state.last_b1_toggle_at = now

    settings = await load_wearable_settings()
    sb = _sb_client()
    async with _state_lock:
        if _state.open_session_id:
            sid = _state.open_session_id
            def _close():
                sb.table("sessions").update({
                    "ended_at": _now_iso(),
                    "status": "closed",
                }).eq("id", sid).execute()
            await asyncio.to_thread(_close)
            _state.open_session_id = None
            _state.open_session_label = None
            await log(f"📁 Documentation session closed", "info")
            await broadcast({"type": "session_closed", "session_id": sid})
            return {"action": "closed", "session_id": sid}
        else:
            label = datetime.now().strftime("Session %Y-%m-%d %H:%M")
            def _open():
                return sb.table("sessions").insert({
                    "worker_id":   settings["worker_id"],
                    "worker_name": settings["worker_name"],
                    "label":       label,
                    "status":      "open",
                }).execute()
            r = await asyncio.to_thread(_open)
            sid = r.data[0]["id"] if r.data else None
            _state.open_session_id = sid
            _state.open_session_label = label
            await log(f"📁 Documentation session opened — {label}", "info")
            await broadcast({"type": "session_opened", "session_id": sid, "label": label})
            return {"action": "opened", "session_id": sid, "label": label}


# ============================================================
# B2 single — take photo
# ============================================================

async def b2_take_photo(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    grab_jpeg: Callable[[], bytes],
) -> dict[str, Any]:
    """Capture one JPEG and store it. If a doc session is open, attach;
    else file under '_orphan/'.

    `grab_jpeg` is provided by the dashboard so we can re-use the open
    SessionCamera (if any) instead of taking a fresh picamera2 lock.
    """
    settings = await load_wearable_settings()
    jpeg = await asyncio.to_thread(grab_jpeg)
    ts = int(time.time() * 1000)
    sid = _state.open_session_id
    folder = sid or "_orphan"
    path = f"{folder}/photo_{ts}.jpg"
    await _upload_to_storage(path, jpeg, "image/jpeg")
    sb = _sb_client()
    def _ins():
        sb.table("session_assets").insert({
            "session_id":   sid,
            "worker_id":    settings["worker_id"],
            "kind":         "photo",
            "storage_path": path,
            "duration_s":   None,
        }).execute()
    await asyncio.to_thread(_ins)
    await log(f"📷 photo saved → {path} ({len(jpeg)} bytes)", "info")
    await broadcast({"type": "photo_saved", "path": path, "session_id": sid})
    return {"ok": True, "path": path, "bytes": len(jpeg), "session_id": sid}


# ============================================================
# B2 double — short video clip
# ============================================================

async def b2_record_video(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    duration_s: float = 5.0,
) -> dict[str, Any]:
    """Record a short MP4 via rpicam-vid, then upload. Synchronous-ish —
    the simulator click waits ~duration_s.

    Refuses to start a second capture while the first is still running:
    rpicam-vid takes an exclusive camera lock, so two concurrent runs
    error out with 'imx708: Unable to set controls: Device or resource busy'.
    """
    async with _state_lock:
        if _state.video_recording:
            await log("🎥 video already in flight — ignoring this press", "info")
            return {"error": "video capture already in progress — wait a moment"}
        _state.video_recording = True

    try:
        settings = await load_wearable_settings()
        sid = _state.open_session_id
        folder = sid or "_orphan"
        ts = int(time.time() * 1000)
        out_path = f"/tmp/vl_video_{ts}.mp4"
        duration_ms = int(duration_s * 1000)

        # Video-only capture via rpicam-vid + libav -> MP4 in one shot.
        # The legacy capture_av_mp4.sh muxed audio via arecord, but the I2S
        # mic is held exclusively by audio_worker for B3 voice notes + AI
        # sessions, so a parallel arecord always fails with EBUSY. Audio
        # commentary on videos is a TODO that needs to route through the
        # AudioBridge instead of opening ALSA directly.
        cmd = [
            "rpicam-vid",
            "-o", out_path,
            "--width", "1280", "--height", "720", "--framerate", "30",
            "--codec", "libav", "--libav-format", "mp4",
            "-t", str(duration_ms),
            "-n",   # no preview window
        ]
        await log(f"🎥 recording {duration_s}s video (no audio)...", "info")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            msg = err.decode(errors='replace')[:300] or "(no stderr)"
            await log(f"video capture failed: {msg}", "error")
            return {"error": "video capture failed", "detail": msg}

        try:
            with open(out_path, "rb") as f:
                data = f.read()
        finally:
            try: os.unlink(out_path)
            except OSError: pass

        storage_path = f"{folder}/video_{ts}.mp4"
        await _upload_to_storage(storage_path, data, "video/mp4")
        sb = _sb_client()
        def _ins():
            sb.table("session_assets").insert({
                "session_id":   sid,
                "worker_id":    settings["worker_id"],
                "kind":         "video",
                "storage_path": storage_path,
                "duration_s":   duration_s,
            }).execute()
        await asyncio.to_thread(_ins)
        await log(f"🎥 video saved → {storage_path} ({len(data)} bytes)", "info")
        await broadcast({"type": "video_saved", "path": storage_path, "session_id": sid})
        return {"ok": True, "path": storage_path, "bytes": len(data), "duration_s": duration_s}
    finally:
        async with _state_lock:
            _state.video_recording = False


# ============================================================
# B3 — voice note (hold to record, release to upload)
# ============================================================

async def b3_voice_note_start(
    log: Callable[[str, str], Awaitable[None]],
    bridge: Any,   # AudioBridge — duck-typed to avoid circular import
    is_ai_session_running: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    # GUARD: voice notes share the AudioBridge mic with B4/B5/B6 AI sessions.
    # If both consume the mic concurrently, blocks get split between them and
    # neither stream is intelligible. Refuse instead of silently corrupting.
    if is_ai_session_running and is_ai_session_running():
        await log(
            "🎙 voice note BLOCKED — AI session is using the mic. "
            "Double-click B4/B5 to stop the session, then try again.",
            "warning",
        )
        return {"error": "AI session active — cannot record voice note"}

    # Drain any stale mic blocks the worker has been buffering since the last
    # consumer (AI session or prior voice note) ended. AudioBridge mic_q is
    # capped at 2000 blocks × 100 ms = 200 s (~3 min 20 s) — without this
    # drain, a fresh voice note replays whatever was sitting in the queue
    # ahead of the press, producing 3-minute "recordings" of unrelated audio.
    try:
        dropped = bridge.drain_mic()
        if dropped:
            await log(
                f"🎙 dropped {dropped} stale mic blocks "
                f"(~{dropped * 0.1:.1f}s of buffered audio) before recording",
                "info",
            )
    except Exception as e:
        # drain_mic should never throw, but if the bridge isn't ready, don't
        # block the user from starting their note — just log and continue.
        print(f"[b3] drain_mic failed: {e!r}", flush=True)

    async with _state_lock:
        if _state.voice_note_recording:
            return {"already_recording": True}
        _state.voice_note_recording = True
        _state.voice_note_buffer = bytearray()
        _state.voice_note_started_at = time.time()

    await log("🎙 voice note recording... (press B3 again to stop)", "info")

    async def _capture_loop():
        try:
            while _state.voice_note_recording:
                try:
                    block = await bridge.read_mic_block()
                    _state.voice_note_buffer.extend(block)
                except Exception as e:
                    print(f"[b3] mic read err: {e}", flush=True)
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    _state.voice_note_task = asyncio.create_task(_capture_loop())
    return {"recording": True}


async def b3_voice_note_end(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
) -> dict[str, Any]:
    async with _state_lock:
        if not _state.voice_note_recording:
            return {"not_recording": True}
        _state.voice_note_recording = False
        task = _state.voice_note_task
        _state.voice_note_task = None
        buf = bytes(_state.voice_note_buffer)
        _state.voice_note_buffer = bytearray()
        started = _state.voice_note_started_at

    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    duration_s = time.time() - started
    if len(buf) < 1600:  # less than 50 ms — ignore
        if len(buf) == 0:
            # Empty buffer means the mic stream produced no data at all —
            # usually audio_worker can't open the I2S device (missing/broken
            # ~/.asoundrc, busy hw:3,0, etc). Surface that, not "too short".
            await log(
                "🎙 voice note received NO audio — mic not flowing. "
                "Check audio_worker / ~/.asoundrc.",
                "warning",
            )
        else:
            await log("🎙 voice note too short — discarded", "info")
        return {"too_short": True, "duration_s": duration_s, "bytes": len(buf)}

    # Wrap raw 16k S16 mono PCM in a WAV header
    wav = _pcm_to_wav(buf, sample_rate=16000, channels=1)
    settings = await load_wearable_settings()
    sid = _state.open_session_id
    folder = sid or "_orphan"
    ts = int(time.time() * 1000)
    path = f"{folder}/voice_{ts}.wav"
    await _upload_to_storage(path, wav, "audio/wav")
    sb = _sb_client()
    def _ins():
        sb.table("session_assets").insert({
            "session_id":   sid,
            "worker_id":    settings["worker_id"],
            "kind":         "voice_note",
            "storage_path": path,
            "duration_s":   round(duration_s, 2),
        }).execute()
    await asyncio.to_thread(_ins)
    await log(f"🎙 voice note saved → {path} ({duration_s:.1f}s, {len(wav)} bytes)", "info")
    await broadcast({"type": "voice_note_saved", "path": path, "duration_s": duration_s})
    return {"ok": True, "path": path, "duration_s": duration_s}


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw int16 PCM in a WAV header so the file plays in browsers."""
    import struct
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)
    riff_size = 36 + data_size
    header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH",
        16, 1, channels, sample_rate, byte_rate, block_align, bits,
    )
    header += b"data" + struct.pack("<I", data_size)
    return header + pcm


# ============================================================
# B3 — single-press toggle (alternative to hold-to-record)
# ============================================================
#
# Calling convention: every B3 press fires this. The handler decides
# whether to START or STOP based on _state.voice_note_recording.
# Press 1 → start. Press 2 → stop & upload. Plus an 800 ms cooldown
# so physical button bounce can't accidentally double-toggle.

async def b3_voice_note_toggle(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    bridge: Any,
    is_ai_session_running: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    B3_COOLDOWN_S = 0.8
    now = time.time()
    if now - _state.last_b3_toggle_at < B3_COOLDOWN_S:
        return {"action": "ignored", "reason": "cooldown — too soon after last toggle"}
    _state.last_b3_toggle_at = now

    if _state.voice_note_recording:
        # Currently recording → stop and upload
        return await b3_voice_note_end(log, broadcast)
    else:
        # Not recording → start
        return await b3_voice_note_start(log, bridge, is_ai_session_running=is_ai_session_running)


# ============================================================
# B4 / B5 — start AI session (audio / audio+vision)
# ============================================================
#
# These are thin wrappers — actual session start is done by the
# dashboard via the `ai_starter` callable, because the session
# lifecycle (task, current_session refs, camera) lives there.

async def b4_ai_voice_only(
    log: Callable[[str, str], Awaitable[None]],
    ai_starter: Callable[[str, str, bool], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Start the audio-only AI session using the provider configured
    in wearable_settings.b4_provider.

    Logs reflect what actually happened — if ai_starter rejects (e.g. a
    session is already running), the user sees the rejection reason rather
    than a misleading "starting" message.
    """
    settings = await load_wearable_settings()
    provider = settings["b4_provider"]
    result = await ai_starter(provider, "audio", False)
    if result.get("error"):
        await log(f"🤖 B4 → {result['error']}", "info")
    else:
        await log(f"🤖 B4 → AI ({provider}) audio session started", "info")
    return result


async def b5_ai_voice_vision(
    log: Callable[[str, str], Awaitable[None]],
    ai_starter: Callable[[str, str, bool], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Start an AI session with vision per wearable_settings.b5_*."""
    settings = await load_wearable_settings()
    provider = settings["b5_provider"]
    vision_mode = settings["b5_vision_mode"]   # snap_on_press | gemini_video | auto_snap_4s
    # Map vision_mode + provider into the existing session 'mode' arg
    if provider == "gemini" and vision_mode == "gemini_video":
        gemini_mode = "video"
    elif provider == "gemini":
        gemini_mode = "snap"   # gemini supports snap-on-press in 'snap' mode
    else:
        gemini_mode = "audio"  # OpenAI uses audio mode + image injection
    result = await ai_starter(provider, gemini_mode, True)
    if result.get("error"):
        await log(f"👁 B5 → {result['error']}", "info")
    else:
        await log(
            f"👁 B5 → AI ({provider}, vision={vision_mode}) started", "info"
        )
    return result


async def b_ai_stop_any(
    log: Callable[[str, str], Awaitable[None]],
    ai_stopper: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Hard-stop whichever AI session is running (Gemini or OpenAI).

    Wired to B4 double-click + B5 double-click — same gesture, same effect.
    Independent of which provider was chosen; the dashboard knows what
    task is alive and cancels it.
    """
    await log("🛑 Stop AI session (double-click)", "info")
    return await ai_stopper()


# ============================================================
# B6 — single = warn, double = SOS panic mode
# ============================================================

DOUBLE_CLICK_WINDOW_S = 0.8

async def b6_warn_single(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
) -> dict[str, Any]:
    """Single click on B6 — refuses to trigger SOS, asks for double-click."""
    _state.last_b6_single_at = time.time()
    await log("⚠ B6 single click — DOUBLE-click to trigger SOS panic mode", "info")
    await broadcast({
        "type": "b6_warn",
        "msg": "Double-click required to arm SOS panic mode",
    })
    return {"warning": "double-click required for SOS"}


async def b6_sos_trigger(
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    bridge: Any,
    grab_jpeg: Callable[[], bytes],
    ai_starter: Optional[Callable[[str, str, bool], Awaitable[dict[str, Any]]]] = None,
    ai_stopper: Optional[Callable[[], Awaitable[dict[str, Any]]]] = None,
    snap_into_current: Optional[Callable[[], Awaitable[dict[str, Any]]]] = None,
) -> dict[str, Any]:
    """B6 double-click — TOGGLE SOS panic mode.

    If no SOS is active: arm it (insert row, email, start streaming task).
    If a SOS is already active: resolve it (the watcher in the running
    task will see resolved=true within 2s and tear everything down).

    What arming does:
      1. Insert sos_events row, store id in _state.sos_active_id
      2. Send alert email to wearable_settings.sos_alert_recipient_role
      3. Spawn the SOS task: starts an OpenAI Realtime session, auto-snaps
         photos every N seconds, streams transcript to sos_events.live_transcript
      4. Watcher polls sos_events.resolved every 2 s — flips true → shut down
      5. Hard timeout from settings.sos_max_duration_s
    """
    sb = _sb_client()

    async with _state_lock:
        active_id = _state.sos_active_id

    if active_id:
        # SOS is currently armed — worker double-clicks B6 again to cancel.
        # Flip the row; the running task's watcher polls every 2s and exits.
        await log(f"🛑 SOS cancel-by-worker (id={active_id})", "info")
        def _flip():
            sb.table("sos_events").update({
                "resolved": True,
                "resolved_at": _now_iso(),
                "resolved_by": "worker_cancel",
                "reason": "Cancelled by worker via B6 double-click",
            }).eq("id", active_id).execute()
        await asyncio.to_thread(_flip)
        await broadcast({"type": "sos_cancelling", "id": active_id})
        return {"action": "cancelling", "id": active_id}

    settings = await load_wearable_settings()

    def _insert_sos():
        return sb.table("sos_events").insert({
            "worker_id":   settings["worker_id"],
            "worker_name": settings["worker_name"],
            "notes":       "Triggered by double-click on B6",
        }).execute()
    r = await asyncio.to_thread(_insert_sos)
    sos_id = r.data[0]["id"] if r.data else str(uuid.uuid4())
    async with _state_lock:
        _state.sos_active_id = sos_id

    await log(f"🆘 SOS PANIC MODE ARMED — id={sos_id}", "error")
    await broadcast({"type": "sos_armed", "id": sos_id})

    # Auto-close any open doc session — worker is in an emergency, not a
    # paperwork moment. Fire-and-forget so we don't block SOS startup.
    asyncio.create_task(_sos_auto_close_open_session(sos_id, log, broadcast))

    # Fire-and-forget alert email (don't block on it)
    asyncio.create_task(_sos_send_alert_email(sos_id, settings, sb))

    # Pick the brain — Gemini by default (matches B4/B5 default), OpenAI if explicitly set
    sos_provider = settings.get("sos_provider", "gemini")

    if sos_provider == "gemini" and ai_starter and ai_stopper:
        task = asyncio.create_task(_sos_run_session_gemini(
            sos_id=sos_id,
            settings=settings,
            log=log,
            broadcast=broadcast,
            grab_jpeg=grab_jpeg,
            ai_starter=ai_starter,
            ai_stopper=ai_stopper,
            snap_into_current=snap_into_current,
        ))
    else:
        # OpenAI path (or Gemini path with missing deps — falls back to OpenAI)
        task = asyncio.create_task(_sos_run_session(
            sos_id=sos_id,
            settings=settings,
            log=log,
            broadcast=broadcast,
            bridge=bridge,
            grab_jpeg=grab_jpeg,
        ))
    async with _state_lock:
        _state.sos_task = task

    return {"ok": True, "sos_id": sos_id}


async def _sos_auto_close_open_session(
    sos_id: str,
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """If a doc session was open when SOS triggered, close it automatically.
    Worker is dealing with an emergency, not paperwork. Captures already
    written into the session keep their reference; future captures during
    the SOS go to _orphan/."""
    async with _state_lock:
        open_sid = _state.open_session_id

    if not open_sid:
        return

    sb = _sb_client()
    def _close():
        sb.table("sessions").update({
            "ended_at": _now_iso(),
            "status":   "closed",
        }).eq("id", open_sid).execute()
    try:
        await asyncio.to_thread(_close)
    except Exception as e:
        await log(f"⚠ SOS auto-close failed for session {open_sid}: {e}", "warning")
        return

    async with _state_lock:
        _state.open_session_id = None
        _state.open_session_label = None

    await log(
        f"📁 Auto-closed open doc session {open_sid[:8]} due to SOS {sos_id[:8]}",
        "info",
    )
    await broadcast({
        "type":       "session_auto_closed",
        "session_id": open_sid,
        "reason":     "sos",
        "sos_id":     sos_id,
    })


async def _sos_send_alert_email(
    sos_id: str, settings: dict[str, Any], sb: Client
) -> None:
    """Use the existing send_report tool to email the safety officer."""
    try:
        from src.ai.tools import handle_send_report
        result = await handle_send_report({
            "recipient_role": settings["sos_alert_recipient_role"],
            "report_name":    "incident report",
            "custom_message": (
                f"🆘 SOS PANIC MODE TRIGGERED by {settings['worker_name']} "
                f"(worker_id={settings['worker_id']}). Live frames + "
                f"transcript streaming to ops dashboard. SOS ID: {sos_id}."
            ),
        })
        ok = bool(result.get("ok"))
        def _mark():
            sb.table("sos_events").update({
                "email_sent": ok,
                "notes": f"alert email: {result}",
            }).eq("id", sos_id).execute()
        await asyncio.to_thread(_mark)
    except Exception as e:
        print(f"[sos] email alert failed: {e!r}", flush=True)


async def _sos_run_session(
    sos_id: str,
    settings: dict[str, Any],
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    bridge: Any,
    grab_jpeg: Callable[[], bytes],
) -> None:
    """The actual SOS loop. Concurrently:
      - runs an OpenAI Realtime session so the agent speaks calmly to the worker
      - injects a fresh camera frame every photo_interval_s
      - watches sos_events.resolved (poll every 2s) and shuts down when true
      - enforces a hard timeout

    Cleans up state when the loop exits.
    """
    from src.ai.openai_realtime import OpenAISession, DEFAULT_OPENAI_SETTINGS

    sb = _sb_client()
    photo_interval = max(1, int(settings.get("sos_photo_interval_s", 4)))
    max_duration   = max(30, int(settings.get("sos_max_duration_s", 600)))

    # SOS-specific system prompt: calm, reassuring, situationally aware
    sos_settings = dict(DEFAULT_OPENAI_SETTINGS)
    sos_settings["system_prompt"] = (
        f"You are VisionLink in EMERGENCY mode. {settings['worker_name']} just "
        f"triggered an SOS. Your job: reassure them out loud, ask short "
        f"questions ('Are you injured? Where are you? What happened?'), "
        f"describe whatever you can see in their camera frames, and tell them "
        f"help is on the way. Speak calmly, slowly, in 1-2 short sentences at "
        f"a time. Do NOT call any tools right now — focus on reassurance. "
        f"The supervisor will arrive shortly."
    )
    sos_settings["voice"] = "marin"  # warm voice for emergency

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        await log("🆘 OPENAI_API_KEY missing — SOS will run photo-only", "error")

    # Build an OpenAISession with our SOS settings if key is present
    session: Optional[OpenAISession] = None

    async def _on_transcript_update(text_delta: str) -> None:
        """Append agent transcript to sos_events.live_transcript so the
        supervisor sees what the wearable is saying."""
        try:
            def _update():
                # Read-modify-write — race is fine for streaming text
                row = (sb.table("sos_events")
                         .select("live_transcript")
                         .eq("id", sos_id)
                         .limit(1)
                         .execute())
                cur = row.data[0]["live_transcript"] if row.data else ""
                sb.table("sos_events").update({
                    "live_transcript": cur + text_delta,
                }).eq("id", sos_id).execute()
            await asyncio.to_thread(_update)
        except Exception as e:
            print(f"[sos] transcript update fail: {e!r}", flush=True)

    # Wrap the dashboard's broadcast so we also forward agent transcripts
    async def _wrapped_broadcast(event: dict[str, Any]) -> None:
        await broadcast(event)
        if event.get("type") == "transcript" and event.get("role") == "openai":
            await _on_transcript_update(event.get("text", ""))

    if api_key:
        session = OpenAISession(
            api_key=api_key,
            bridge=bridge,
            settings=sos_settings,
            broadcast=_wrapped_broadcast,
            log=log,
            dlog=lambda *a, **kw: None,
        )

    async def session_runner() -> None:
        if session is None:
            return
        try:
            await session.run()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await log(f"🆘 SOS OpenAI session ended: {e}", "error")

    async def auto_snap_loop() -> None:
        await asyncio.sleep(2.0)  # let the session connect first
        frame_n = 0
        while True:
            try:
                jpeg = await asyncio.to_thread(grab_jpeg)
                frame_n += 1
                # Upload to storage and wait so the ops dashboard's
                # last_frame_path always points to a real file
                ts = int(time.time() * 1000)
                path = f"sos/{sos_id}/frame_{ts}.jpg"
                await _upload_to_storage(path, jpeg, "image/jpeg")
                # Inject into OpenAI session if alive
                if session and session.connection is not None:
                    try:
                        await session.send_image(
                            jpeg,
                            prompt=("Live SOS frame. Describe briefly if you "
                                    "see anything noteworthy."),
                        )
                    except Exception as e:
                        print(f"[sos] send_image fail: {e!r}", flush=True)
                # Update frames_sent counter + last frame path for live display
                def _bump():
                    try:
                        sb.table("sos_events").update({
                            "frames_sent": frame_n,
                            "last_frame_path": path,
                        }).eq("id", sos_id).execute()
                    except Exception:
                        # column may not exist (migration pending)
                        sb.table("sos_events").update({
                            "frames_sent": frame_n,
                        }).eq("id", sos_id).execute()
                await asyncio.to_thread(_bump)
                await broadcast({
                    "type": "sos_frame",
                    "sos_id": sos_id,
                    "n": frame_n,
                    "path": path,
                })
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[sos] auto-snap loop err: {e!r}", flush=True)
            await asyncio.sleep(photo_interval)

    async def resolution_watcher() -> None:
        """Poll sos_events.resolved every 2 s. Returns when supervisor flips it."""
        while True:
            await asyncio.sleep(2.0)
            try:
                def _check():
                    return (sb.table("sos_events")
                              .select("resolved,resolved_by,reason")
                              .eq("id", sos_id)
                              .limit(1)
                              .execute())
                r = await asyncio.to_thread(_check)
                if r.data and r.data[0].get("resolved"):
                    await log(
                        f"🛑 SOS resolved by {r.data[0].get('resolved_by') or '?'}"
                        f" ({r.data[0].get('reason') or '—'})",
                        "info",
                    )
                    return
            except Exception as e:
                print(f"[sos] watcher err: {e!r}", flush=True)

    try:
        # Race the watcher against the hard timeout
        watcher_task = asyncio.create_task(resolution_watcher())
        snap_task    = asyncio.create_task(auto_snap_loop())
        session_task = asyncio.create_task(session_runner())

        try:
            await asyncio.wait_for(watcher_task, timeout=max_duration)
        except asyncio.TimeoutError:
            await log(f"🆘 SOS hit max duration ({max_duration}s) — auto-stopping", "warning")
            def _auto_resolve():
                sb.table("sos_events").update({
                    "resolved": True,
                    "resolved_at": _now_iso(),
                    "resolved_by": "auto_timeout",
                    "reason": f"max duration {max_duration}s reached",
                }).eq("id", sos_id).execute()
            await asyncio.to_thread(_auto_resolve)

        # Tear down side tasks
        for t in (snap_task, session_task, watcher_task):
            t.cancel()
        for t in (snap_task, session_task, watcher_task):
            try: await t
            except asyncio.CancelledError: pass
            except Exception: pass

    finally:
        # Mark resolved_at if the supervisor's update didn't include it
        def _final():
            cur = (sb.table("sos_events")
                     .select("resolved_at")
                     .eq("id", sos_id)
                     .limit(1)
                     .execute())
            if cur.data and not cur.data[0].get("resolved_at"):
                sb.table("sos_events").update({
                    "resolved_at": _now_iso(),
                }).eq("id", sos_id).execute()
        try:
            await asyncio.to_thread(_final)
        except Exception:
            pass

        async with _state_lock:
            _state.sos_active_id = None
            _state.sos_task = None
        await broadcast({"type": "sos_ended", "sos_id": sos_id})
        await log("🆘 SOS panic mode ended", "info")


# ============================================================
# SOS — Gemini code path (uses dashboard's existing Live machinery)
# ============================================================

def _build_sos_gemini_prompt(worker_name: str) -> str:
    """Brutal Gemini SOS system prompt. Mirrors the 'ABSOLUTE RULES' style
    we use for the regular agent prompt because Gemini Live needs strong
    instructions to avoid drifting into its default helpful-assistant mode."""
    return (
        f"🆘 EMERGENCY MODE — ABSOLUTE RULES. READ EVERY LINE.\n\n"
        f"Worker {worker_name} just triggered an SOS panic alarm on their "
        f"VisionLink wearable. They may be hurt, trapped, in danger, "
        f"scared, or unable to think clearly. Your supervisor was emailed. "
        f"You are the voice in their ear until help arrives.\n\n"
        f"==================================================================\n"
        f"RULE 1 — OPEN THE CALL IMMEDIATELY. The very FIRST thing you say:\n"
        f"  '{worker_name}, I'm here with you. Help is on the way. "
        f"Are you hurt? Where are you?'\n"
        f"Do not wait for them to speak first. Speak first. Be the voice "
        f"that arrives.\n"
        f"==================================================================\n\n"
        f"RULE 2 — STAY CALM, BE SHORT.\n"
        f"  - 1 to 2 short sentences per turn. No paragraphs.\n"
        f"  - Calm, low-stakes tone. No urgency in the voice — they have "
        f"enough urgency already.\n"
        f"  - Pause for them to answer. Do not fill silence with chatter.\n\n"
        f"RULE 3 — FOLLOW THIS PROTOCOL:\n"
        f"  Step 1: Confirm injury status — 'Are you hurt? Can you move?'\n"
        f"  Step 2: Confirm location — 'Where are you in the building?'\n"
        f"  Step 3: Confirm what happened — 'What happened? What do you see?'\n"
        f"  Step 4: Reassure — 'Help is coming. Stay where you are if it's safe.'\n"
        f"  Step 5: Keep them talking — 'I'm staying with you. Tell me what "
        f"you can hear.'\n\n"
        f"RULE 4 — TOOLS:\n"
        f"  - Use ONLY `log_incident` during this emergency. NEVER call "
        f"`send_report`, `mark_task_complete`, `request_part`, "
        f"`get_my_assignments`, or `lookup_component`.\n"
        f"  - Whenever the worker tells you ANYTHING factual (injury, "
        f"hazard, location, pain level, what they see), IMMEDIATELY call "
        f"log_incident with severity='critical' and a vivid description "
        f"capturing their words. This is a permanent record for the "
        f"medics arriving.\n\n"
        f"RULE 5 — IF YOU SEE A CAMERA FRAME:\n"
        f"  Briefly describe what's there. ONLY facts, no interpretation.\n"
        f"  Example: 'I see a dark room and what looks like spilled liquid "
        f"on the floor.' NOT: 'It looks dangerous.'\n\n"
        f"RULE 6 — DO NOT MENTION:\n"
        f"  - Tasks, parts, reports, components, torque specs, maintenance.\n"
        f"  - Anything about your normal helpful-assistant mode.\n"
        f"  - 'How can I help you with your tasks today' — NEVER. We are "
        f"not in normal mode.\n\n"
        f"RULE 7 — LANGUAGE: Match the worker. If they speak Turkish, "
        f"Arabic, English — follow them. Do not translate, just speak "
        f"their language back.\n\n"
        f"==================================================================\n"
        f"YOU ARE NOT A HELPFUL ASSISTANT RIGHT NOW. YOU ARE A 911 OPERATOR\n"
        f"WITH EYES. ACT LIKE ONE.\n"
        f"=================================================================="
    )


async def _sos_run_session_gemini(
    sos_id: str,
    settings: dict[str, Any],
    log: Callable[[str, str], Awaitable[None]],
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    grab_jpeg: Callable[[], bytes],
    ai_starter: Callable[..., Awaitable[dict[str, Any]]],
    ai_stopper: Callable[[], Awaitable[dict[str, Any]]],
    snap_into_current: Optional[Callable[[], Awaitable[dict[str, Any]]]],
) -> None:
    """SOS panic mode using the existing dashboard Gemini Live machinery
    BUT with a brutal SOS-specific system prompt overriding the default.

    Strategy: kick off a Gemini snap-mode session via ai_starter, passing
    the SOS prompt as system_prompt_override so Gemini boots into 911-
    operator persona instead of helpful-assistant persona. Then run side
    tasks for periodic snap injection and resolution polling on top.
    """
    sb = _sb_client()
    photo_interval = max(1, int(settings.get("sos_photo_interval_s", 10)))
    max_duration   = max(30, int(settings.get("sos_max_duration_s", 600)))

    # Build the SOS prompt and pass it through ai_starter — this is the
    # critical fix for "Gemini SOS just acts like a normal agent"
    sos_prompt = _build_sos_gemini_prompt(settings.get("worker_name", "the worker"))
    await log(f"🆘 Starting Gemini SOS with emergency prompt", "info")
    start_result = await ai_starter(
        "gemini", "snap", True,
        system_prompt_override=sos_prompt,
    )
    if start_result.get("error"):
        await log(f"🆘 SOS could not start Gemini: {start_result['error']}", "error")
        # Even though we couldn't start, keep the row open so the supervisor
        # sees it. They can still resolve to acknowledge.
        await _sos_idle_watch(sos_id, max_duration, broadcast, log)
        return
    await log(f"🆘 SOS Gemini session starting (interval={photo_interval}s)", "info")

    async def auto_snap_loop() -> None:
        # Give the session a moment to connect before injecting frames
        await asyncio.sleep(2.0)
        frame_n = 0
        while True:
            try:
                if snap_into_current is not None:
                    res = await snap_into_current()
                    if res and not res.get("error"):
                        frame_n += 1
                # Also persist the frame to storage for the audit trail
                jpeg = await asyncio.to_thread(grab_jpeg)
                ts = int(time.time() * 1000)
                path = f"sos/{sos_id}/frame_{ts}.jpg"
                # Wait for upload so last_frame_path points to a real file
                await _upload_to_storage(path, jpeg, "image/jpeg")
                # Bump frames_sent counter + the latest frame path so the
                # ops dashboard shows the new image live
                def _bump():
                    try:
                        sb.table("sos_events").update({
                            "frames_sent": frame_n,
                            "last_frame_path": path,
                        }).eq("id", sos_id).execute()
                    except Exception:
                        # last_frame_path column may not exist yet (migration
                        # not applied) — fall back to just bumping the counter
                        sb.table("sos_events").update({
                            "frames_sent": frame_n,
                        }).eq("id", sos_id).execute()
                await asyncio.to_thread(_bump)
                await broadcast({
                    "type": "sos_frame",
                    "sos_id": sos_id,
                    "n": frame_n,
                    "path": path,
                })
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[sos-gemini] snap loop err: {e!r}", flush=True)
            await asyncio.sleep(photo_interval)

    async def resolution_watcher() -> None:
        while True:
            await asyncio.sleep(2.0)
            try:
                def _check():
                    return (sb.table("sos_events")
                              .select("resolved,resolved_by,reason")
                              .eq("id", sos_id)
                              .limit(1)
                              .execute())
                r = await asyncio.to_thread(_check)
                if r.data and r.data[0].get("resolved"):
                    await log(
                        f"🛑 SOS resolved by {r.data[0].get('resolved_by') or '?'}"
                        f" ({r.data[0].get('reason') or '—'})",
                        "info",
                    )
                    return
            except Exception as e:
                print(f"[sos-gemini] watcher err: {e!r}", flush=True)

    snap_task    = asyncio.create_task(auto_snap_loop())
    watcher_task = asyncio.create_task(resolution_watcher())

    try:
        await asyncio.wait_for(watcher_task, timeout=max_duration)
    except asyncio.TimeoutError:
        await log(f"🆘 SOS hit {max_duration}s timeout — auto-stop", "warning")
        def _auto_resolve():
            sb.table("sos_events").update({
                "resolved": True,
                "resolved_at": _now_iso(),
                "resolved_by": "auto_timeout",
                "reason": f"max duration {max_duration}s reached",
            }).eq("id", sos_id).execute()
        await asyncio.to_thread(_auto_resolve)
    finally:
        for t in (snap_task, watcher_task):
            t.cancel()
        for t in (snap_task, watcher_task):
            try: await t
            except (asyncio.CancelledError, Exception): pass

        # Stop the Gemini session
        try:
            await ai_stopper()
        except Exception as e:
            print(f"[sos-gemini] ai_stopper err: {e!r}", flush=True)

        # Mark resolved_at if not already set
        try:
            def _final():
                cur = (sb.table("sos_events")
                         .select("resolved_at")
                         .eq("id", sos_id)
                         .limit(1)
                         .execute())
                if cur.data and not cur.data[0].get("resolved_at"):
                    sb.table("sos_events").update({
                        "resolved_at": _now_iso(),
                    }).eq("id", sos_id).execute()
            await asyncio.to_thread(_final)
        except Exception:
            pass

        async with _state_lock:
            _state.sos_active_id = None
            _state.sos_task = None
        await broadcast({"type": "sos_ended", "sos_id": sos_id})
        await log("🆘 SOS panic mode ended (Gemini)", "info")


async def _sos_idle_watch(
    sos_id: str,
    max_duration: int,
    broadcast: Callable[[dict[str, Any]], Awaitable[None]],
    log: Callable[[str, str], Awaitable[None]],
) -> None:
    """Fallback watcher when Gemini failed to start. Just polls for
    resolved=true so the row gets cleaned up properly."""
    sb = _sb_client()
    deadline = time.time() + max_duration
    while time.time() < deadline:
        await asyncio.sleep(2.0)
        def _check():
            return (sb.table("sos_events")
                      .select("resolved")
                      .eq("id", sos_id)
                      .limit(1)
                      .execute())
        try:
            r = await asyncio.to_thread(_check)
            if r.data and r.data[0].get("resolved"):
                break
        except Exception:
            pass
    async with _state_lock:
        _state.sos_active_id = None
        _state.sos_task = None
    await broadcast({"type": "sos_ended", "sos_id": sos_id})
    await log("🆘 SOS panic mode ended (no AI session)", "info")
