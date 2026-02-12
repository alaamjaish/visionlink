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
        self._hold_active = {}        # pin -> bool
        self._audio_player = audio_player
        self._running = False

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
        """Called on button press (falling edge). Handles debounce + double-press."""
        now = time.time()
        logger.debug(f"Button press detected on pin {pin}")

        # Play beep feedback
        self._beep()

        callbacks = self._callbacks.get(pin, {})

        # If this button uses hold mode, track it
        if callbacks.get("hold_start"):
            self._hold_active[pin] = True
            logger.info(f"Pin {pin}: hold started")
            cb = callbacks["hold_start"]
            if cb:
                threading.Thread(target=cb, daemon=True).start()
            return

        # Double-press detection
        if callbacks.get("double"):
            if pin in self._pending_single and self._pending_single[pin] is not None:
                # Second press within window -> double press
                self._pending_single[pin].cancel()
                self._pending_single[pin] = None
                logger.info(f"Pin {pin}: DOUBLE press")
                cb = callbacks["double"]
                if cb:
                    threading.Thread(target=cb, daemon=True).start()
            else:
                # First press -> wait for potential second
                timer = threading.Timer(
                    config.DOUBLE_PRESS_WINDOW,
                    self._fire_single, args=[pin]
                )
                self._pending_single[pin] = timer
                timer.start()
        else:
            # No double-press handler, fire single immediately
            logger.info(f"Pin {pin}: SINGLE press")
            cb = callbacks.get("single")
            if cb:
                threading.Thread(target=cb, daemon=True).start()

    def _fire_single(self, pin: int):
        """Fire single press after double-press window expires."""
        self._pending_single[pin] = None
        logger.info(f"Pin {pin}: SINGLE press (after timeout)")
        cb = self._callbacks.get(pin, {}).get("single")
        if cb:
            threading.Thread(target=cb, daemon=True).start()

    def _hold_monitor(self):
        """Monitor for button release on hold-type buttons."""
        if not HAS_GPIO:
            return
        while self._running:
            for pin, active in list(self._hold_active.items()):
                if active and GPIO.input(pin) == GPIO.HIGH:
                    # Button released
                    self._hold_active[pin] = False
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
