"""Follow-and-click task (plan section 5.5).

The target travels along a path; the child tracks it and selects it. Reaction
time and gaze-to-target distance are the metrics of interest. The target's live
position is computed per frame via :meth:`target_position`.

Paths (``motion.path``, SPEC-target-size-and-motion-paths.md S4.4): ``circular``,
and four straight bouncing paths -- ``horizontal``, ``vertical``,
``diagonal_tlbr`` (top-left to bottom-right) and ``diagonal_trbl`` (top-right
to bottom-left). Every straight path moves at the same on-screen speed in
px/s, so one ``speed_frac_per_s`` setting is comparable between them.
"""

from __future__ import annotations

import math

from .base_task import BaseTask, TargetSpec

PATHS = ("circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl")
DEFAULT_PATH = "horizontal"  # today's fallback for an unknown/missing value

# Straight paths run between these normalized-canvas points: (start, end) as
# ((x0, y0), (x1, y1)), starting at the first end.
_DIAGONALS = {
    "diagonal_tlbr": ((0.1, 0.1), (0.9, 0.9)),
    "diagonal_trbl": ((0.9, 0.1), (0.1, 0.9)),
}


class FollowMovingTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        n_trials = int(cfg.get("trials", 12))
        radius = float(cfg.get("target", {}).get("radius_px", 80))
        motion = cfg.get("motion", {})
        requested = str(motion.get("path", DEFAULT_PATH))
        if requested in PATHS:
            self.path = requested
        else:
            self.path = DEFAULT_PATH
            self._log(f"Unknown motion.path {requested!r}; using {DEFAULT_PATH!r}.")
        self.speed = float(motion.get("speed_frac_per_s", 0.20))
        self.select_window_ns = int(float(motion.get("select_window_ms", 2500)) * 1e6)

        # Per-trial selection window: the target is only selectable (and
        # highlighted) for select_window_ms starting at a randomized offset, so
        # the child must actively track and catch it rather than park on it.
        latest_start = max(0, self.timeout_ns - self.select_window_ns)
        self.select_windows: list[tuple[int, int]] = []

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            # Drawn for every path, in this order, so a given seed keeps the
            # same selection windows whichever path is chosen.
            lane = self.rng.uniform(0.25, 0.75)
            start = self.rng.randint(int(0.15 * self.timeout_ns), latest_start) if latest_start > 0 else 0
            self.select_windows.append((start, start + self.select_window_ns))
            x, y = self._start_point(lane)
            targets.append(TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius))
        return targets

    def _start_point(self, lane: float) -> tuple[float, float]:
        """Where a trial's target starts, in normalized canvas coordinates.

        ``lane`` is the per-trial random 0.25-0.75 offset across the path --
        the y of a horizontal path, the x of a vertical one. Recorded as the
        trial's ``target_x/y`` in trials.csv. Circular keeps today's value.
        """
        if self.path == "vertical":
            return lane, 0.1
        if self.path in _DIAGONALS:
            return _DIAGONALS[self.path][0]
        return 0.1, lane  # horizontal, and circular as before

    def scene_spec(self) -> dict:
        # Lets the canvas draw a fading motion trail behind the live target
        # position (ported from resources/diki, SPEC-diki-design-audit.md
        # S3.5/S4) -- distinguishes "tracked it" from "waited where it would
        # arrive." path/speed aren't read by the canvas today but are
        # included for parity with diki and any future trail-shape tuning.
        return {"mode": "moving", "path": self.path, "speed": self.speed}

    def is_selectable(self, target: TargetSpec, elapsed_ns: int) -> bool:
        start, end = self.select_windows[target.index]
        return start <= elapsed_ns <= end

    def target_position(self, target: TargetSpec, elapsed_ns: int) -> tuple[float, float]:
        elapsed_s = elapsed_ns / 1e9
        if self.path == "circular":
            cx, cy, r = 0.5, 0.5, 0.3
            omega = 2 * math.pi * self.speed
            return (
                cx + r * math.cos(omega * elapsed_s),
                cy + r * math.sin(omega * elapsed_s),
            )
        # ``speed`` is a fraction of canvas WIDTH per second, so the on-screen
        # speed in px/s is speed * screen_w for every straight path (S4.4).
        if self.path == "vertical":
            span = 0.8
            # speed * screen_w px/s, expressed in canvas heights per second.
            norm_speed = self.speed * self.screen_w / self.screen_h
            raw = 0.1 + (norm_speed * elapsed_s) % (2 * span)
            y = raw if raw <= 0.9 else (1.8 - raw)  # triangle wave
            return target.x_norm, y
        if self.path in _DIAGONALS:
            (x0, y0), (x1, y1) = _DIAGONALS[self.path]
            length_px = math.hypot((x1 - x0) * self.screen_w, (y1 - y0) * self.screen_h)
            travelled = (self.speed * self.screen_w * elapsed_s) % (2 * length_px)
            u = travelled / length_px
            if u > 1.0:
                u = 2.0 - u  # triangle wave: bounce back along the segment
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        # horizontal: bounce between 0.1 and 0.9
        span = 0.8
        raw = 0.1 + (self.speed * elapsed_s) % (2 * span)
        x = raw if raw <= 0.9 else (1.8 - raw)  # triangle wave
        return x, target.y_norm
