"""The calibration target's motion during one point (SPEC-app-drawn-calibration.md 4.1, 4.6, 4.9).

On each ``CALIB_START_PT`` the icon glides from where it is to the point, with a slow wobble, then
settles (the wobble fades out) and **holds still**, at the same size all the way (4.9 R5: no
shrink). Gazepoint Control starts sampling gaze ``CALIBRATE_DELAY`` seconds after it sent
``CALIB_START_PT`` and no record marks that moment, so the app times the glide itself: the hold
(still) must have started no later than DELAY after the record (:func:`schedule`, A1). The pose is
a pure function of the time, so a window that is late to process the record simply jumps ahead
and the hold still starts on time.

Pure and Qt-free, so the schedule is unit-testable with a fake clock. Positions are fractions of
the screen (the same unit as ``CALX`` / ``CALY``); the window turns them into physical pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The icon enters from the top-left corner before the first point (the Grid 3 recording).
START_CORNER = (0.0, 0.0)

WOBBLE_DEG = 8.0  # +-8 degrees while gliding, fading out in the settle, still during the hold
WOBBLE_HZ = 1.0
SETTLE_S_MAX = 0.5  # the settle at the end of the DELAY, at most this long
SETTLE_FRACTION = 0.3  # ... and at most this share of the time to the hold
# The hold starts this long before DELAY is over, so the icon is still before Control's first
# sample even when the record was read a few milliseconds after it was sent.
SAFETY_S = 0.05
SAFETY_MAX_FRACTION = 0.25  # but never more than this share of a very short DELAY

PHASE_IDLE = "idle"  # no point has started: nothing is drawn
PHASE_GLIDE = "glide"
PHASE_SETTLE = "settle"
PHASE_HOLD = "hold"


def ease(u: float) -> float:
    """Ease in and out, 0 to 1 over ``u`` 0 to 1."""
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def schedule(delay_s: float) -> tuple[float, float]:
    """``(glide_s, settle_s)`` for a ``CALIBRATE_DELAY`` of ``delay_s``: the position eases over
    ``glide_s``, the icon then settles at the point over ``settle_s`` (its wobble fades out), and
    the hold starts at ``glide_s + settle_s``, which is never later than ``delay_s``."""
    delay = max(0.0, float(delay_s))
    total = delay - min(SAFETY_S, SAFETY_MAX_FRACTION * delay)
    settle = min(SETTLE_S_MAX, SETTLE_FRACTION * total)
    return total - settle, settle


@dataclass(frozen=True)
class MotionSample:
    phase: str
    x: float  # fractions of the screen
    y: float
    angle_deg: float


class TargetMotion:
    """The icon's pose over time; :meth:`begin_point` on each ``CALIB_START_PT``."""

    def __init__(self, start: tuple[float, float] = START_CORNER) -> None:
        self._from = start
        self._to = start
        self._t0 = 0.0
        self._delay = 0.0
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def begin_point(self, x: float, y: float, t0: float, delay_s: float) -> None:
        """A point starts at clock time ``t0`` (when the record was read): glide from the pose
        the icon has now to ``(x, y)``."""
        here = self.sample(t0)
        self._from = (here.x, here.y)
        self._to = (float(x), float(y))
        self._t0 = float(t0)
        self._delay = max(0.0, float(delay_s))
        self._active = True

    def glide_end(self) -> float:
        """Clock time the position reaches the point."""
        return self._t0 + schedule(self._delay)[0]

    def hold_start(self) -> float:
        """Clock time the hold (still) starts: at most ``t0 + DELAY`` (A1)."""
        glide, settle = schedule(self._delay)
        return self._t0 + glide + settle

    def sample(self, t: float) -> MotionSample:
        if not self._active:
            return MotionSample(PHASE_IDLE, self._to[0], self._to[1], 0.0)
        glide, settle = schedule(self._delay)
        elapsed = t - self._t0
        wobble = WOBBLE_DEG * math.sin(2.0 * math.pi * WOBBLE_HZ * max(0.0, elapsed))
        if elapsed < glide:
            u = ease(elapsed / glide) if glide > 0 else 1.0
            x = self._from[0] + (self._to[0] - self._from[0]) * u
            y = self._from[1] + (self._to[1] - self._from[1]) * u
            return MotionSample(PHASE_GLIDE, x, y, wobble)
        if elapsed < glide + settle:
            v = ease((elapsed - glide) / settle)
            return MotionSample(PHASE_SETTLE, self._to[0], self._to[1], wobble * (1.0 - v))
        return MotionSample(PHASE_HOLD, self._to[0], self._to[1], 0.0)
