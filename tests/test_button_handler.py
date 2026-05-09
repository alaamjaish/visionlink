import threading
import time
import unittest

import config
from src.hardware import buttons as buttons_mod


class FakeGPIO:
    LOW = 0
    HIGH = 1
    BCM = "BCM"
    IN = "IN"
    PUD_UP = "PUD_UP"
    FALLING = "FALLING"

    def __init__(self):
        self.states = {}

    def input(self, pin):
        return self.states.get(pin, self.HIGH)

    def setup(self, pin, mode, pull_up_down=None):
        self.states[pin] = self.HIGH

    def setmode(self, mode):
        pass

    def setwarnings(self, enabled):
        pass

    def add_event_detect(self, *args, **kwargs):
        pass

    def cleanup(self):
        pass


class ButtonHandlerGestureTests(unittest.TestCase):
    def setUp(self):
        self._old_gpio = buttons_mod.GPIO
        self._old_has_gpio = buttons_mod.HAS_GPIO
        self._old_debounce = config.BUTTON_DEBOUNCE_MS
        self._old_press_stable = config.BUTTON_PRESS_STABLE_MS
        self._old_release_stable = config.BUTTON_RELEASE_STABLE_MS
        self._old_double_window = config.DOUBLE_PRESS_WINDOW

        self.gpio = FakeGPIO()
        buttons_mod.GPIO = self.gpio
        buttons_mod.HAS_GPIO = True
        config.BUTTON_DEBOUNCE_MS = 1
        config.BUTTON_PRESS_STABLE_MS = 1
        config.BUTTON_RELEASE_STABLE_MS = 2
        config.DOUBLE_PRESS_WINDOW = 0.05

    def tearDown(self):
        buttons_mod.GPIO = self._old_gpio
        buttons_mod.HAS_GPIO = self._old_has_gpio
        config.BUTTON_DEBOUNCE_MS = self._old_debounce
        config.BUTTON_PRESS_STABLE_MS = self._old_press_stable
        config.BUTTON_RELEASE_STABLE_MS = self._old_release_stable
        config.DOUBLE_PRESS_WINDOW = self._old_double_window

    def _handler(self, pin, events):
        handler = buttons_mod.ButtonHandler()
        handler.setup()
        handler.register(
            pin,
            on_single=lambda: events.append("single"),
            on_double=lambda: events.append("double"),
        )
        return handler

    def _press(self, handler, pin):
        self.gpio.states[pin] = self.gpio.LOW
        handler._on_button_press(pin)

    def _release(self, pin):
        self.gpio.states[pin] = self.gpio.HIGH

    def test_bounce_during_same_press_does_not_fire_double(self):
        pin = 6
        events = []
        handler = self._handler(pin, events)

        self._press(handler, pin)
        time.sleep(0.006)
        handler._on_button_press(pin)  # falling-edge bounce while still held
        time.sleep(0.006)
        self._release(pin)
        time.sleep(0.09)

        handler.cleanup()
        self.assertEqual(events, ["single"])

    def test_fast_press_release_press_fires_double(self):
        pin = 13
        events = []
        double_seen = threading.Event()
        handler = buttons_mod.ButtonHandler()
        handler.setup()
        handler.register(
            pin,
            on_single=lambda: events.append("single"),
            on_double=lambda: (events.append("double"), double_seen.set()),
        )

        self._press(handler, pin)
        time.sleep(0.006)
        self._release(pin)
        time.sleep(0.03)
        self._press(handler, pin)
        time.sleep(0.006)
        self._release(pin)

        self.assertTrue(double_seen.wait(0.1))
        time.sleep(0.07)

        handler.cleanup()
        self.assertEqual(events, ["double"])


if __name__ == "__main__":
    unittest.main()
