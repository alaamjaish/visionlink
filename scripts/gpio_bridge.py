#!/usr/bin/env python3
"""GPIO bridge — translate physical button presses into the same HTTP
calls the on-screen 6-button simulator already makes.

Run alongside the dashboard, in a SECOND terminal:
    cd ~/Desktop/visionlink
    python3 scripts/gpio_bridge.py

Pre-flight:
- Dashboard must be running at http://localhost:8000.
- main.py must NOT be running (it would fight us for the same GPIO pins).
- User must be in the `gpio` group (already true for the visionlink user).

What it does:
- Reuses src.hardware.buttons.ButtonHandler for gesture detection
  (debounce, double-press window, hold polling — all the logic that
  already powers the design).
- For every gesture, POSTs to /api/button/{n}/{event}, which is the
  exact endpoint the browser simulator hits. Same handlers, same state.

Stop with Ctrl+C — GPIO is released cleanly.
"""

import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.hardware.buttons import ButtonHandler

DASHBOARD_URL = "http://localhost:8000"
HTTP_TIMEOUT = 5.0


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def post(n: int, event: str) -> None:
    """Fire one button event at the dashboard. Logs result to stdout."""
    url = f"{DASHBOARD_URL}/api/button/{n}/{event}"
    label = f"B{n} {event:11s}"
    try:
        r = requests.post(url, timeout=HTTP_TIMEOUT)
        tag = "OK " if r.ok else "ERR"
        body = r.text.replace("\n", " ")
        if len(body) > 120:
            body = body[:117] + "..."
        print(f"[{_ts()}] [{tag}] {label} -> {r.status_code} {body}", flush=True)
    except requests.exceptions.ConnectionError:
        print(
            f"[{_ts()}] [ERR] {label} -> dashboard not reachable at "
            f"{DASHBOARD_URL} (is uvicorn running?)",
            flush=True,
        )
    except Exception as e:
        print(f"[{_ts()}] [ERR] {label} -> {type(e).__name__}: {e}", flush=True)


def main() -> None:
    # Force line-buffered stdout so output is visible when piped to a log.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    print("=" * 64, flush=True)
    print(" VisionLink GPIO bridge - physical buttons -> dashboard", flush=True)
    print("=" * 64, flush=True)
    print(
        f" Pins: B1=GPIO{config.BTN_SESSION}  B2=GPIO{config.BTN_PHOTO_VIDEO}  "
        f"B3=GPIO{config.BTN_VOICE_NOTE}  "
        f"B4=GPIO{config.BTN_AI_CAMERA}  B5=GPIO{config.BTN_AI_VOICE}  "
        f"B6=GPIO{config.BTN_AI_AGENT}",
        flush=True,
    )
    print(f" Dashboard: {DASHBOARD_URL}", flush=True)
    print(
        f" Debounce: {config.BUTTON_DEBOUNCE_MS}ms   "
        f"double-press window: {config.DOUBLE_PRESS_WINDOW}s",
        flush=True,
    )
    print("=" * 64, flush=True)

    buttons = ButtonHandler()  # no audio_player -> no beep, no crash
    buttons.setup()

    # Gesture map — must match dashboard.server.button_dispatch:
    buttons.register(
        config.BTN_SESSION,
        on_single=lambda: post(1, "single"),
    )
    buttons.register(
        config.BTN_PHOTO_VIDEO,
        on_single=lambda: post(2, "single"),
        on_double=lambda: post(2, "double"),
    )
    buttons.register(
        config.BTN_VOICE_NOTE,
        on_hold_start=lambda: post(3, "hold_start"),
        on_hold_end=lambda: post(3, "hold_end"),
    )
    buttons.register(
        config.BTN_AI_CAMERA,
        on_single=lambda: post(4, "single"),
        on_double=lambda: post(4, "double"),
    )
    buttons.register(
        config.BTN_AI_VOICE,
        on_single=lambda: post(5, "single"),
        on_double=lambda: post(5, "double"),
    )
    buttons.register(
        config.BTN_AI_AGENT,
        on_single=lambda: post(6, "single"),
        on_double=lambda: post(6, "double"),
    )

    buttons.start_listening()

    print(" Listening. Press a button (Ctrl+C to stop).", flush=True)
    print(flush=True)

    def shutdown(signum, frame):
        print(f"\n[{_ts()}] Shutting down - releasing GPIO...", flush=True)
        buttons.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
