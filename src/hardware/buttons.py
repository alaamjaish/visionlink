"""
GPIO Button Handler

6 buttons with software debounce, double-press detection, and beep feedback.
Buttons 1-3: Documentation mode
Buttons 4-6: AI Assistant mode
"""

import time
import threading
from typing import Callable

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("buttons")


class ButtonHandler:
    """Handles all 6 GPIO buttons with debounce and double-press detection."""

    def __init__(self, audio_player=None):
        self._callbacks = {}          # pin -> {"single": fn, "double": fn, "hold_start": fn, "hold_end": fn}
        self._last_press_time = {}    # pin -> timestamp
        self._pending_single = {}     # pin -> Timer (for double-press detection)
        self._press_active = {}       # pin -> bool; true until the physical press releases cleanly
        self._hold_active = {}        # pin -> bool
        self._audio_player = audio_player
        self._running = False
        self._lock = threading.RLock()

    def setup(self):
        """Initialize GPIO pins."""
        if not HAS_GPIO:
            logger.warning("RPi.GPIO not available - buttons will not work")
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for pin in config.ALL_BUTTONS:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._last_press_time[pin] = 0
            self._press_active[pin] = False
            self._hold_active[pin] = False
            logger.info(f"GPIO pin {pin} configured as input with pull-up")

        self._running = True
        logger.info("Button handler initialized")

    def register(self, pin: int, on_single: Callable = None,
                 on_double: Callable = None,
                 on_hold_start: Callable = None,
                 on_hold_end: Callable = None):
        """Register callbacks for a button pin."""
        self._callbacks[pin] = {
            "single": on_single,
            "double": on_double,
            "hold_start": on_hold_start,
            "hold_end": on_hold_end,
        }
        logger.debug(f"Callbacks registered for pin {pin}")

    def start_listening(self):
        """Start listening for button events on all registered pins."""
        if not HAS_GPIO:
            logger.warning("Cannot start listening - no GPIO")
            return

        for pin in self._callbacks:
            GPIO.add_event_detect(
                pin, GPIO.FALLING,
                callback=self._on_button_press,
                bouncetime=config.BUTTON_DEBOUNCE_MS
            )
            logger.info(f"Listening on pin {pin}")

        # Start hold detection thread
        self._hold_thread = threading.Thread(target=self._hold_monitor, daemon=True)
        self._hold_thread.start()
        logger.info("Button listener started")

    def _on_button_press(self, pin: int):
        """GPIO callback on a raw falling edge.

        RPi.GPIO bouncetime is intentionally short so it does not swallow the
        second click of a fast physical double-click. The real debounce happens
        in a worker thread: accept a click only after the pin is still LOW, and
        ignore all later falling edges until the same press releases HIGH.
        """
        edge_at = time.monotonic()
        logger.debug(f"Pin {pin}: raw falling edge at {edge_at:.6f}")
        threading.Thread(
            target=self._handle_validated_press,
            args=(pin, edge_at),
            daemon=True,
        ).start()

    def _handle_validated_press(self, pin: int, edge_at: float):
        """Validate a raw edge and route it into single/double/hold logic."""
        press_stable_s = getattr(config, "BUTTON_PRESS_STABLE_MS", 20) / 1000.0
        time.sleep(press_stable_s)
        if not self._running:
            return
        try:
            if GPIO.input(pin) != GPIO.LOW:
                logger.debug(f"Pin {pin}: ignored unstable edge")
                return
        except Exception as e:
            logger.error(f"Pin {pin}: GPIO read failed during press validation: {e}")
            return

        with self._lock:
            if self._press_active.get(pin):
                logger.debug(f"Pin {pin}: ignored bounce while press is active")
                return
            self._press_active[pin] = True
            self._last_press_time[pin] = edge_at

        # Play beep feedback only for a validated click, not every raw bounce.
        self._beep()
        callbacks = self._callbacks.get(pin, {})

        # If this button uses hold mode, track it
        if callbacks.get("hold_start"):
            with self._lock:
                self._hold_active[pin] = True
            logger.info(f"Pin {pin}: hold started")
            cb = callbacks["hold_start"]
            if cb:
                threading.Thread(target=cb, daemon=True).start()
            return

        threading.Thread(target=self._release_monitor, args=(pin,), daemon=True).start()

        # Double-press detection
        if callbacks.get("double"):
            with self._lock:
                pending = self._pending_single.get(pin)
                if pending is not None:
                    pending.cancel()
                    self._pending_single[pin] = None
                    is_double = True
                else:
                    timer = threading.Timer(
                        config.DOUBLE_PRESS_WINDOW,
                        self._fire_single, args=[pin]
                    )
                    self._pending_single[pin] = timer
                    is_double = False

            if is_double:
                logger.info(f"Pin {pin}: DOUBLE press")
                cb = callbacks["double"]
                if cb:
                    threading.Thread(target=cb, daemon=True).start()
            else:
                timer.start()
        else:
            # No double-press handler, fire single immediately
            logger.info(f"Pin {pin}: SINGLE press")
            cb = callbacks.get("single")
            if cb:
                threading.Thread(target=cb, daemon=True).start()

    def _fire_single(self, pin: int):
        """Fire single press after double-press window expires."""
        with self._lock:
            if self._pending_single.get(pin) is None:
                return
            self._pending_single[pin] = None
        logger.info(f"Pin {pin}: SINGLE press (after timeout)")
        cb = self._callbacks.get(pin, {}).get("single")
        if cb:
            threading.Thread(target=cb, daemon=True).start()

    def _release_monitor(self, pin: int):
        """Clear press_active only after the switch is stably released."""
        if not HAS_GPIO:
            return
        release_stable_s = getattr(config, "BUTTON_RELEASE_STABLE_MS", 40) / 1000.0
        high_since = None
        while self._running:
            try:
                is_high = GPIO.input(pin) == GPIO.HIGH
            except Exception as e:
                logger.error(f"Pin {pin}: GPIO read failed during release monitor: {e}")
                is_high = True
            now = time.monotonic()
            if is_high:
                if high_since is None:
                    high_since = now
                elif now - high_since >= release_stable_s:
                    with self._lock:
                        self._press_active[pin] = False
                    logger.debug(f"Pin {pin}: release stable")
                    return
            else:
                high_since = None
            time.sleep(0.01)

    def _hold_monitor(self):
        """Monitor for button release on hold-type buttons."""
        if not HAS_GPIO:
            return
        while self._running:
            for pin, active in list(self._hold_active.items()):
                if active and GPIO.input(pin) == GPIO.HIGH:
                    # Button released
                    with self._lock:
                        self._hold_active[pin] = False
                        self._press_active[pin] = False
                    logger.info(f"Pin {pin}: hold ended")
                    cb = self._callbacks.get(pin, {}).get("hold_end")
                    if cb:
                        threading.Thread(target=cb, daemon=True).start()
            time.sleep(0.05)  # 50ms polling

    def _beep(self):
        """Play beep feedback sound."""
        if self._audio_player:
            try:
                self._audio_player.play_beep()
            except Exception as e:
                logger.error(f"Beep failed: {e}")

    def cleanup(self):
        """Clean up GPIO resources."""
        self._running = False
        if HAS_GPIO:
            GPIO.cleanup()
        logger.info("Button handler cleaned up")
