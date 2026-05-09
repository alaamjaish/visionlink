"""
Parent-side supervisor for the audio worker subprocess.

Spawns the worker, restarts it if it dies, and exposes a small async-friendly
API: read mic blocks, write speaker chunks, drain queues.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import time
from pathlib import Path
from typing import Optional

from dashboard.audio_worker import (
    BLOCK,
    MIC_RATE,
    MSG_SHUTDOWN,
    SPEAKER_RATE,
    run as audio_worker_run,
)

# ~/.asoundrc has gone missing mid-session more than once (cause unverified —
# possibly editor sync, SD-card glitch, stray reboot). Without it the audio
# worker can't resolve the named PCMs `mic_left` / `speaker` and falls into a
# tight restart loop. Source of truth lives in the repo; we make ~/.asoundrc a
# symlink to it and re-verify before every worker spawn.
_ASOUNDRC_REPO = (Path(__file__).resolve().parent.parent / "system" / "asoundrc")
_ASOUNDRC_USER = Path.home() / ".asoundrc"


def _ensure_asoundrc() -> None:
    """Restore ~/.asoundrc as a symlink to the canonical repo file if missing."""
    if not _ASOUNDRC_REPO.exists():
        print(
            f"[bridge] WARNING: canonical asoundrc missing at {_ASOUNDRC_REPO} "
            f"— audio worker will likely fail to find named PCMs",
            flush=True,
        )
        return

    # Path.exists() follows symlinks: True only if user file resolves to a real
    # target. False covers both "file gone" and "dangling symlink".
    if _ASOUNDRC_USER.exists():
        return

    # Clean any dangling symlink, then atomically install the canonical one.
    try:
        if _ASOUNDRC_USER.is_symlink():
            _ASOUNDRC_USER.unlink()
    except FileNotFoundError:
        pass
    tmp = _ASOUNDRC_USER.with_suffix(".asoundrc.tmp")
    try:
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
    except FileNotFoundError:
        pass
    os.symlink(_ASOUNDRC_REPO, tmp)
    os.replace(tmp, _ASOUNDRC_USER)
    print(
        f"[bridge] HEAL: restored {_ASOUNDRC_USER} -> {_ASOUNDRC_REPO} "
        f"(was missing — audio worker would have failed)",
        flush=True,
    )


class AudioBridge:
    """Owns one audio_worker subprocess. Auto-restarts it on death."""

    def __init__(self) -> None:
        self._ctx = multiprocessing.get_context("spawn")
        self._proc: Optional[multiprocessing.Process] = None
        self._mic_q = None
        self._spk_q = None
        self._lock = asyncio.Lock()
        self.start()

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Spawn a fresh audio worker."""
        if self._proc is not None and self._proc.is_alive():
            return
        _ensure_asoundrc()
        # Generous queues — Gemini emits speaker audio in MANY small chunks
        # (often >100/sec) and a queue that's too small silently drops most
        # of the voice. Memory is cheap; audio-quality regressions are not.
        self._mic_q = self._ctx.Queue(maxsize=2000)
        self._spk_q = self._ctx.Queue(maxsize=10000)
        self._proc = self._ctx.Process(
            target=audio_worker_run,
            args=(self._mic_q, self._spk_q),
            daemon=True,
        )
        self._proc.start()
        # Give the worker a moment to open streams before first use
        time.sleep(0.6)

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    def shutdown(self) -> None:
        """Polite shutdown — sends SHUTDOWN sentinel, then joins, then kills."""
        try:
            if self._spk_q is not None:
                self._spk_q.put(MSG_SHUTDOWN, timeout=0.5)
        except Exception:
            pass
        if self._proc is not None:
            self._proc.join(timeout=2.0)
            if self._proc.is_alive():
                self._proc.terminate()
                self._proc.join(timeout=1.0)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=1.0)

    def restart(self) -> None:
        """Kill the worker and spawn a fresh one (use after a crash)."""
        self.shutdown()
        time.sleep(0.3)
        self.start()

    def _ensure_alive(self) -> None:
        """Restart the worker if it's died (e.g. ALSA assertion)."""
        if not self.is_alive():
            self.restart()

    # ------------------------------------------------------------------ mic

    def drain_mic(self) -> int:
        """Discard any mic frames sitting in the queue (call at session start)."""
        dropped = 0
        if self._mic_q is None:
            return 0
        while True:
            try:
                self._mic_q.get_nowait()
                dropped += 1
            except Exception:
                break
        return dropped

    async def read_mic_block(self) -> bytes:
        """Read one mic block (~100 ms at 16 kHz). Auto-restarts on worker death."""
        self._ensure_alive()
        loop = asyncio.get_running_loop()
        # Use a timeout so we don't hang forever if the worker silently dies
        return await loop.run_in_executor(None, self._mic_q.get, True, 5.0)

    # ------------------------------------------------------------------ speaker

    _spk_dropped: int = 0

    def write_speaker(self, chunk: bytes) -> None:
        """Queue a speaker chunk. Block briefly if the queue is full so we don't
        silently lose audio (the cause of the 'very quiet' regression)."""
        self._ensure_alive()
        if self._spk_q is None:
            return
        try:
            # Short timeout: if the worker really can't keep up, eventually
            # drop one chunk rather than block the receive loop forever.
            self._spk_q.put(chunk, timeout=0.5)
        except Exception:
            self._spk_dropped += 1
            if self._spk_dropped % 10 == 1:
                print(f"[bridge] WARNING: dropped {self._spk_dropped} speaker chunks (queue full)", flush=True)

    def flush_speaker(self) -> int:
        """Drain pending speaker chunks (call on Gemini interruption)."""
        dropped = 0
        if self._spk_q is None:
            return 0
        while True:
            try:
                self._spk_q.get_nowait()
                dropped += 1
            except Exception:
                break
        return dropped

    def speaker_pending(self) -> bool:
        """True if there are speaker chunks queued for playback."""
        if self._spk_q is None:
            return False
        return not self._spk_q.empty()

    def play_test_tone(self, freq_hz: int = 880, duration_s: float = 0.5,
                        amplitude: float = 0.5) -> int:
        """Push a sine-wave PCM tone at SPEAKER_RATE through the same path as
        Gemini audio. Returns the number of bytes queued."""
        import math
        import struct
        from dashboard.audio_worker import SPEAKER_RATE

        n = int(SPEAKER_RATE * duration_s)
        peak = int(32767 * max(0.0, min(1.0, amplitude)))
        buf = bytearray()
        for i in range(n):
            v = int(peak * math.sin(2 * math.pi * freq_hz * i / SPEAKER_RATE))
            buf += struct.pack("<h", v)
        chunk = bytes(buf)
        self.write_speaker(chunk)
        return len(chunk)
