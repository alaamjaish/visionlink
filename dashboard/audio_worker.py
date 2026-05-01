"""
Audio worker subprocess for VisionLink.

Runs in its own process so an ALSA `plug` device assertion (the C-level
`pcm_plugin.c:572` crash) cannot kill the FastAPI server. The parent
restarts this worker on death.

Owns the I2S mic and speaker via sounddevice. Communicates over two
multiprocessing queues:
- mic_q : worker -> parent  (16 kHz S16 mono PCM, BLOCK frames at a time)
- spk_q : parent -> worker  (24 kHz S16 mono PCM, arbitrary chunk sizes,
                              special sentinels for shutdown / drain)
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

# Sentinels — special bytes values on spk_q
MSG_SHUTDOWN = b"__VL_SHUTDOWN__"

MIC_RATE = 16000
SPEAKER_RATE = 24000
BLOCK = 1600  # 100 ms at 16 kHz


def _err(msg: str) -> None:
    sys.stderr.write(f"[audio_worker] {msg}\n")
    sys.stderr.flush()


def run(mic_q: Any, spk_q: Any) -> None:
    """Worker entrypoint. Block until shutdown is requested or a stream errors out."""
    # sounddevice is imported here, NOT at module top, so the parent process
    # never loads PortAudio. Only this child process does.
    import sounddevice as sd

    # IMPORTANT — explicitly bind to our ~/.asoundrc PCMs by EXACT NAME.
    # PortAudio's default OUTPUT on this Pi is `bcm2835 Headphones` (hw:2,0),
    # the 3.5mm audio jack, NOT the I2S googlevoicehat-soundcard. If we let
    # sounddevice pick its default we get audio playing into the wrong card
    # (the user hears near-silence, only crosstalk).
    #
    # We can't pass device='mic_left' as a string because PortAudio does
    # substring matching and would pick `mic_left_raw` (a 2ch S32 device)
    # first, which fails to open at our 16k S16 mono config. Look up by
    # exact name → index instead.
    def _find_by_name(name: str) -> int:
        for idx, dev in enumerate(sd.query_devices()):
            if dev["name"] == name:
                return idx
        raise RuntimeError(f"audio device {name!r} not found in PortAudio enumeration")

    try:
        mic_idx = _find_by_name("mic_left")
        spk_idx = _find_by_name("speaker")
        _err(f"resolved devices: mic_left={mic_idx}, speaker={spk_idx}")
        mic_stream = sd.RawInputStream(
            samplerate=MIC_RATE, channels=1, dtype="int16", blocksize=BLOCK,
            device=mic_idx,
        )
        spk_stream = sd.RawOutputStream(
            samplerate=SPEAKER_RATE, channels=1, dtype="int16",
            device=spk_idx,
        )
        mic_stream.start()
        spk_stream.start()
        _err(f"streams started — mic device #{mic_stream.device}, spk device #{spk_stream.device}")

        # === DIAGNOSTIC: play a calibration tone at startup ===
        # Tells us if the speaker chain is at full volume independent of any
        # Gemini-data path. 0.4 s of 880 Hz at ~50% amplitude (peak ~16 384).
        try:
            import math
            import struct
            tone_samples = bytearray()
            for n in range(int(SPEAKER_RATE * 0.4)):
                v = int(16384 * math.sin(2 * math.pi * 880 * n / SPEAKER_RATE))
                tone_samples += struct.pack("<h", v)
            spk_stream.write(bytes(tone_samples))
            _err(f"calibration tone written ({len(tone_samples)} bytes, 880Hz, 0.4s)")
        except Exception as e:
            _err(f"calibration tone failed: {e!r}")
    except Exception as e:
        _err(f"primary device open failed: {e!r}")
        # Fallback: try the ALSA "default" PCM (still routes via asoundrc)
        try:
            default_idx = _find_by_name("default")
            mic_stream = sd.RawInputStream(
                samplerate=MIC_RATE, channels=1, dtype="int16",
                blocksize=BLOCK, device=default_idx,
            )
            spk_stream = sd.RawOutputStream(
                samplerate=SPEAKER_RATE, channels=1, dtype="int16",
                device=default_idx,
            )
            mic_stream.start()
            spk_stream.start()
            _err(f"fallback to 'default' device #{default_idx} succeeded")
        except Exception as e2:
            _err(f"fallback also failed: {e2!r}")
            return

    stop_flag = threading.Event()

    def mic_thread() -> None:
        """Continuously read mic blocks and forward to parent. Drop on backpressure."""
        while not stop_flag.is_set():
            try:
                data, _ = mic_stream.read(BLOCK)
            except Exception as e:
                _err(f"mic read error: {e}")
                stop_flag.set()
                break
            try:
                mic_q.put_nowait(bytes(data))
            except Exception:
                # Parent isn't draining (no active session). Drop the frame.
                pass

    t = threading.Thread(target=mic_thread, daemon=True)
    t.start()

    # Speaker loop (this thread blocks on spk_q.get).
    while not stop_flag.is_set():
        try:
            chunk = spk_q.get(timeout=0.5)
        except Exception:
            continue
        if chunk == MSG_SHUTDOWN:
            stop_flag.set()
            break
        if not chunk:
            continue
        try:
            spk_stream.write(chunk)
        except Exception as e:
            _err(f"spk write error: {e}")
            stop_flag.set()
            break

    # Clean shutdown — proper stop()+close() ONLY happens here, in the
    # subprocess. If ALSA's plug device kills us with its assertion, only
    # this child dies; the parent supervisor will spawn a fresh worker.
    _err("shutting down — closing streams")
    for s in (mic_stream, spk_stream):
        try:
            s.stop()
        except Exception as e:
            _err(f"stop: {e}")
        try:
            s.close()
        except Exception as e:
            _err(f"close: {e}")
    _err("shutdown complete")
