"""Switch input (plan section 5.3; SPEC-input-selection-and-follow.md 4.2).

The switch is whatever sends a **left mouse press on the canvas** (a USB switch
that acts as a mouse button, or the mouse's own) or **Space / Enter**
(:class:`~src.ui.canvas.TaskCanvas` and :meth:`AssessmentApp._install_key_handler`
feed :meth:`SwitchInput.press` / :meth:`~SwitchInput.release`). The pointer comes
from gaze (``gaze_switch``) or the mouse (``switch``); the switch only says *when*.
The click detection is a simple rising-edge latch so the same logic works whether
events arrive from PySide6, ``pynput``, or a test harness.

A press counts on **button down** (I5a), so :meth:`press` latches at once; the latch
re-arms only on :meth:`release`, so a held button or an auto-repeating key is one
press.
"""

from __future__ import annotations


class SwitchInput:
    """Rising-edge click latch fed by external press/release events."""

    def __init__(self) -> None:
        self._pressed = False
        self._click_latched = False

    def press(self) -> None:
        """Signal that the switch was activated (key down / button press)."""
        if not self._pressed:
            self._click_latched = True
        self._pressed = True

    def release(self) -> None:
        self._pressed = False

    def reset(self) -> None:
        """Forget a press that is waiting and the held state (focus lost, a pause):
        a release that never arrives must not leave the switch dead."""
        self._pressed = False
        self._click_latched = False

    @property
    def is_held(self) -> bool:
        return self._pressed

    def consume_click(self) -> bool:
        """Return True exactly once per press (one-frame rising edge)."""
        clicked = self._click_latched
        self._click_latched = False
        return clicked
