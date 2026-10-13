"""The One Euro filter (Casiez, Roussel and Vogel, CHI 2012) for the gaze cursor
(SPEC-gaze-stability-and-positioning.md 4.3).

Per axis, a first-order low-pass whose cutoff rises with the signal's speed::

    cutoff = min_cutoff + beta * |filtered speed|

so the cursor is steady while the eyes rest (low cutoff) and follows quickly when they
jump (high cutoff). The speed is the derivative of the raw signal, itself low-passed at
the fixed ``D_CUTOFF_HZ``. Unlike the running average it uses the real time between
samples, so its feel does not change with the loop rate. Qt-free.
"""

from __future__ import annotations

import math

from .gaze_signal import ONE_EURO_BETA_DEFAULT, ONE_EURO_MIN_CUTOFF_DEFAULT

D_CUTOFF_HZ = 1.0  # the paper's recommendation; not a setting


def _alpha(dt_s: float, cutoff_hz: float) -> float:
    """Weight of the new value for a low-pass of ``cutoff_hz`` sampled every ``dt_s``."""
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / dt_s)


class _Axis:
    """One axis of the filter."""

    def __init__(self) -> None:
        self.raw: float | None = None  # the previous raw value
        self.value = 0.0  # the filtered value
        self.speed = 0.0  # the filtered derivative, units per second

    def update(self, value: float, dt_s: float, min_cutoff_hz: float, beta: float) -> float:
        if self.raw is None:
            self.raw = self.value = value
            return value
        a_d = _alpha(dt_s, D_CUTOFF_HZ)
        self.speed = a_d * (value - self.raw) / dt_s + (1.0 - a_d) * self.speed
        a = _alpha(dt_s, min_cutoff_hz + beta * abs(self.speed))
        self.value = a * value + (1.0 - a) * self.value
        self.raw = value
        return self.value


class OneEuroFilter:
    """The One Euro filter over an (x, y) point, with the real time between calls."""

    def __init__(
        self,
        min_cutoff_hz: float = ONE_EURO_MIN_CUTOFF_DEFAULT,
        beta: float = ONE_EURO_BETA_DEFAULT,
    ) -> None:
        # A zero cutoff would never move; the setting's own range starts above it.
        self.min_cutoff_hz = max(min_cutoff_hz, 1e-3)
        self.beta = max(beta, 0.0)
        self._t_ns: int | None = None
        self._x = _Axis()
        self._y = _Axis()

    def reset(self) -> None:
        """Forget the history: the next point starts fresh (after a gaze drop-out)."""
        self._t_ns = None
        self._x = _Axis()
        self._y = _Axis()

    def update(self, x: float, y: float, t_ns: int) -> tuple[float, float]:
        """The filtered point for the raw ``(x, y)`` seen at ``t_ns``. The first point after
        construction or :meth:`reset` passes through; a call at or before the last time
        returns the last filtered point unchanged."""
        if self._t_ns is None:
            self._t_ns = t_ns
            return self._x.update(x, 0.0, 0.0, 0.0), self._y.update(y, 0.0, 0.0, 0.0)
        dt_s = (t_ns - self._t_ns) / 1e9
        if dt_s <= 0.0:
            return self._x.value, self._y.value
        self._t_ns = t_ns
        return (
            self._x.update(x, dt_s, self.min_cutoff_hz, self.beta),
            self._y.update(y, dt_s, self.min_cutoff_hz, self.beta),
        )
