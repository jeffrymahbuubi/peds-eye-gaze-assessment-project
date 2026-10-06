"""Follow-and-click task (plan section 5.5).

The target travels along a path; the child tracks it and selects it. Reaction
time and gaze-to-target distance are the metrics of interest. The target's live
position is computed per frame via :meth:`target_position`.

Paths (``motion.path``, SPEC-target-size-and-motion-paths.md S4.4): ``circular``,
and four straight bouncing paths -- ``horizontal``, ``vertical``,
``diagonal_tlbr`` (top-left to bottom-right) and ``diagonal_trbl`` (top-right
to bottom-left). Every straight path moves at the same on-screen speed in
px/s, so one ``speed_frac_per_s`` setting is comparable between them.

The path is kept inside the canvas for the chosen target size (SPEC-target-size-
and-motion-paths.md S11.3, B1 a): the nominal 0.1-0.9 ends are pulled inward by
the target's radius plus its dwell ring when that is more than 10 % of the
canvas, from the live canvas size. The size never changes; the speed in px/s
along the (then shorter) segment does not either.
"""

from __future__ import annotations

import math
from typing import Any

from ..engine.target_size import clamp_to_inset, edge_inset_norm
from .base_task import BaseTask, TargetSpec

PATHS = ("circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl")
DEFAULT_PATH = "horizontal"  # today's fallback for an unknown/missing value

# Nominal ends of a straight path along one axis, in normalized canvas coords.
_LO, _HI = 0.1, 0.9

# Straight paths run between these normalized-canvas points: (start, end) as
# ((x0, y0), (x1, y1)), starting at the first end. Nominal; the live segment is
# these pulled inward (:func:`_axis_bounds`).
_DIAGONALS = {
    "diagonal_tlbr": ((0.1, 0.1), (0.9, 0.9)),
    "diagonal_trbl": ((0.9, 0.1), (0.1, 0.9)),
}


def _axis_bounds(margin: float) -> tuple[float, float]:
    """The ends of a straight path along one axis: the nominal 0.1 / 0.9, pulled
    inward when the target's edge margin is larger. Degenerates to the centre
    on a canvas too small to hold the target."""
    lo, hi = max(_LO, margin), min(_HI, 1.0 - margin)
    return (lo, hi) if lo <= hi else (0.5, 0.5)


class FollowMovingTask(BaseTask):
    # The target's path goes to target_track.csv (SPEC-compass-task-flow.md 4D.4-2).
    records_target_track = True

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

    def _margins(self, target: TargetSpec) -> tuple[float, float]:
        """Edge margin (fraction of canvas width, height) the target needs."""
        return edge_inset_norm(target.radius_px, self.screen_w, self.screen_h)

    def start_position(self, target: TargetSpec) -> tuple[float, float]:
        # Circular keeps today's recorded value (S4.4 -- its TargetSpec start is
        # not where the orbit begins); every other path records where the target
        # actually is at elapsed 0, inset included.
        if self.path == "circular":
            return target.x_norm, target.y_norm
        return super().start_position(target)

    def inset_details(self, target: TargetSpec) -> dict[str, Any] | None:
        margin_x, margin_y = self._margins(target)
        if self.path == "circular":
            inset = margin_x > 0.5 - 0.3 or margin_y > 0.5 - 0.3  # orbit radius 0.3
        else:
            # An axis is inset when its ends moved off the nominal 0.1-0.9 or,
            # for the lane the path does not travel along, the random position
            # had to be pulled in.
            moves_x = self.path in ("horizontal", "diagonal_tlbr", "diagonal_trbl")
            moves_y = self.path in ("vertical", "diagonal_tlbr", "diagonal_trbl")
            inset = (
                (moves_x and _axis_bounds(margin_x) != (_LO, _HI))
                or (moves_y and _axis_bounds(margin_y) != (_LO, _HI))
                or (not moves_y and clamp_to_inset(target.y_norm, margin_y) != target.y_norm)
                or (not moves_x and clamp_to_inset(target.x_norm, margin_x) != target.x_norm)
            )
        return self._edge_inset_payload(target.radius_px, margin_x, margin_y) if inset else None

    def target_position(self, target: TargetSpec, elapsed_ns: int) -> tuple[float, float]:
        elapsed_s = elapsed_ns / 1e9
        margin_x, margin_y = self._margins(target)
        if self.path == "circular":
            cx, cy, r = 0.5, 0.5, 0.3
            omega = 2 * math.pi * self.speed
            # Per-axis clamp: on a canvas shorter than ~910 px the orbit is
            # flattened rather than leaving the canvas (S11.3).
            return (
                clamp_to_inset(cx + r * math.cos(omega * elapsed_s), margin_x),
                clamp_to_inset(cy + r * math.sin(omega * elapsed_s), margin_y),
            )
        # ``speed`` is a fraction of canvas WIDTH per second, so the on-screen
        # speed in px/s is speed * screen_w for every straight path (S4.4).
        if self.path == "vertical":
            y_lo, y_hi = _axis_bounds(margin_y)
            x = clamp_to_inset(target.x_norm, margin_x)
            span = y_hi - y_lo
            if span <= 0:
                return x, y_lo
            # speed * screen_w px/s, expressed in canvas heights per second.
            norm_speed = self.speed * self.screen_w / self.screen_h
            raw = y_lo + (norm_speed * elapsed_s) % (2 * span)
            y = raw if raw <= y_hi else (2 * y_hi - raw)  # triangle wave
            return x, y
        if self.path in _DIAGONALS:
            x_lo, x_hi = _axis_bounds(margin_x)
            y_lo, y_hi = _axis_bounds(margin_y)
            (sx, _sy), (ex, _ey) = _DIAGONALS[self.path]
            x0, x1 = (x_lo, x_hi) if sx < ex else (x_hi, x_lo)
            length_px = math.hypot((x1 - x0) * self.screen_w, (y_hi - y_lo) * self.screen_h)
            if length_px <= 0:
                return x0, y_lo
            travelled = (self.speed * self.screen_w * elapsed_s) % (2 * length_px)
            u = travelled / length_px
            if u > 1.0:
                u = 2.0 - u  # triangle wave: bounce back along the segment
            return x0 + (x1 - x0) * u, y_lo + (y_hi - y_lo) * u
        # horizontal: bounce between the (inset) ends, nominally 0.1 and 0.9
        x_lo, x_hi = _axis_bounds(margin_x)
        y = clamp_to_inset(target.y_norm, margin_y)
        span = x_hi - x_lo
        if span <= 0:
            return x_lo, y
        raw = x_lo + (self.speed * elapsed_s) % (2 * span)
        x = raw if raw <= x_hi else (2 * x_hi - raw)  # triangle wave
        return x, y
