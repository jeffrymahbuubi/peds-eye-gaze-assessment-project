"""Rate limiter for the moving target's position log (SPEC-compass-task-flow.md
4D.4-2, HD12).

The GUI ticks at the device or display rate (60-150 Hz); ``target_track.csv``
only needs the path at ~20 Hz, which draws a smooth polyline for about 1.5 kB a
trial. Qt-free, so the throttle is tested without a recorder.
"""

from __future__ import annotations

TRACK_HZ = 20
TRACK_INTERVAL_NS = int(1e9 / TRACK_HZ)


class TrackThrottle:
    """Says when a position is due: the first frame of a trial, then every
    :data:`TRACK_INTERVAL_NS` after the last one that was due."""

    def __init__(self, interval_ns: int = TRACK_INTERVAL_NS) -> None:
        self.interval_ns = interval_ns
        self._last_ns: int | None = None

    def reset(self) -> None:
        """A new trial: its first frame is due again."""
        self._last_ns = None

    def due(self, t_ns: int) -> bool:
        if self._last_ns is not None and t_ns - self._last_ns < self.interval_ns:
            return False
        self._last_ns = t_ns
        return True
