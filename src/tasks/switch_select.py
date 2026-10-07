"""Where the pointer was when a switch was pressed (SPEC-input-selection-and-follow.md I5c).

A press is judged against where the child was looking *at that moment*. A blink (or a
saccade: ``FPOGV`` drops in both) can leave the pointer invalid at exactly that frame,
so the last valid pointer within :data:`SWITCH_FALLBACK_MS` stands in for it. With none
that recent, the press has no gaze and is a Click error.

Pure and Qt-free, so the rule is unit-tested on synthetic timelines.
"""

from __future__ import annotations

from dataclasses import dataclass

SWITCH_FALLBACK_MS = 150  # I5c: how old the last valid pointer may be and still count


@dataclass(frozen=True, slots=True)
class PressPoint:
    """The point a press is judged at: canvas px for the hit test, the normalized
    pointer for the event, and whether it is the last valid one rather than now's."""

    px: float
    py: float
    x_norm: float
    y_norm: float
    used_fallback: bool


class PointerTrace:
    """Remembers the last valid pointer, frame by frame."""

    def __init__(self, fallback_ms: float = SWITCH_FALLBACK_MS) -> None:
        self.fallback_ns = int(fallback_ms * 1e6)
        self._last: tuple[int, float, float, float, float] | None = None

    def reset(self) -> None:
        self._last = None

    def observe(
        self, t_ns: int, valid: bool, px: float, py: float, x_norm: float, y_norm: float
    ) -> None:
        """Note this frame's pointer; only a valid one is kept."""
        if valid:
            self._last = (t_ns, px, py, x_norm, y_norm)

    def at_press(
        self, t_ns: int, valid: bool, px: float, py: float, x_norm: float, y_norm: float
    ) -> PressPoint | None:
        """The point to judge a press at ``t_ns``: this frame's pointer when valid, else
        the last valid one if it is at most ``fallback_ms`` old, else ``None``
        (no gaze). A pointer *this* frame is never replaced by an older one."""
        if valid:
            return PressPoint(px, py, x_norm, y_norm, used_fallback=False)
        if self._last is None:
            return None
        last_t, lpx, lpy, lxn, lyn = self._last
        if t_ns - last_t > self.fallback_ns:
            return None
        return PressPoint(lpx, lpy, lxn, lyn, used_fallback=True)
