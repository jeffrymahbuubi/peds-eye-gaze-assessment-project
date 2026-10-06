"""Scanning selection task (plan section 5.5).

Several icons are arranged on screen; one lights up as the target and the child
selects it. Distractor icons are visual only (rendered by the GUI); the metric
of interest is reaction time and wrong-selection count (tracked as attempts).

**Arrangement + shapes ported from ``resources/diki`` (SPEC-diki-design-audit.md
S3.4).** The original version here only ever laid icons out on a single
horizontal row -- not real visual search, since the child never has to look up
or down. ``layout.arrangement`` now supports ``row`` (kept for compatibility),
``ring``, and ``grid`` (new default): a genuine 2D field the child has to
actually scan. Icons are also now assigned one of 6 distinct *shapes*, not just
positions, rendered by ``TaskCanvas`` -- distinguishing by form (not just
brightness/colour) is what makes this a search task rather than a pop-out task.
"""

from __future__ import annotations

import math

from ..engine.target_size import ICON_DRAW_FRAC, fit_icon_radius_px
from ..inputs.base import circle_contains
from .base_task import BaseTask, TargetSpec


def scanning_layout_slots(n_icons: int, arrangement: str, margin: float) -> list[tuple[float, float]]:
    """Normalized canvas positions of the icon slots for an arrangement. Module
    level so the task and the Task settings dialog's shrink hint lay icons out by
    the one formula."""
    span = 1.0 - 2 * margin
    if arrangement == "row":
        return [(margin + span * (i + 0.5) / n_icons, 0.5) for i in range(n_icons)]
    if arrangement == "ring":
        cx, cy, r = 0.5, 0.5, 0.32
        return [
            (
                cx + r * math.cos(2 * math.pi * i / n_icons - math.pi / 2),
                cy + r * math.sin(2 * math.pi * i / n_icons - math.pi / 2),
            )
            for i in range(n_icons)
        ]
    # grid (default): favour more columns than rows, because the screen is
    # wider than it is tall -- round() here would give 6 icons a 2x3
    # layout, leaving large empty margins left and right.
    cols = max(1, math.ceil(n_icons ** 0.5))
    rows = max(1, -(-n_icons // cols))  # ceil division
    slots: list[tuple[float, float]] = []
    for i in range(n_icons):
        r, c = divmod(i, cols)
        slots.append(
            (
                margin + span * (c + 0.5) / cols,
                margin + span * (r + 0.5) / rows,
            )
        )
    return slots


class ScanningTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        layout = cfg.get("layout", {})
        n_icons = int(layout.get("n_icons", 4))
        radius = float(layout.get("radius_px", 80))
        arrangement = str(layout.get("arrangement", "grid"))
        margin = float(layout.get("margin_frac", 0.14))
        n_trials = int(cfg.get("trials", 16))

        self.arrangement = arrangement
        self.icon_slots = self._layout_slots(n_icons, arrangement, margin)
        self.icon_shapes = [i % 6 for i in range(len(self.icon_slots))]
        # Kept for the fixture-generation tool and the existing GUI
        # dim-outline fallback -- see BaseTask.layout_slots's own docstring.
        # scanning now draws real shapes instead (scene_spec's "icons" mode),
        # but this alias stays so nothing that reads task.layout_slots breaks.
        self.layout_slots = list(self.icon_slots)

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            slot = self.rng.randrange(len(self.icon_slots))
            x, y = self.icon_slots[slot]
            targets.append(
                TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius, slot_index=slot)
            )
        return targets

    def _layout_slots(
        self, n_icons: int, arrangement: str, margin: float
    ) -> list[tuple[float, float]]:
        return scanning_layout_slots(n_icons, arrangement, margin)

    # -- icon fit (SPEC-target-size-and-motion-paths.md S11.3) ----------------

    def effective_radius_px(self, target: TargetSpec) -> float:
        """The configured hit radius, capped so the *drawn* icons (at
        :data:`ICON_DRAW_FRAC` of it) neither overlap each other nor cross the
        canvas edge -- :func:`~src.engine.target_size.fit_icon_radius_px`.
        Returned as a hit radius so the canvas, which scales it by
        ``ICON_DRAW_FRAC``, draws the capped icon; every icon, distractors
        included, shrinks together. Per frame: the canvas resizes mid-run."""
        cap = fit_icon_radius_px(self.icon_slots, self.screen_w, self.screen_h)
        return min(target.radius_px, cap / ICON_DRAW_FRAC)

    def hit_test(
        self, target: TargetSpec, cx_px: float, cy_px: float, px: float, py: float
    ) -> bool:
        """The usual circle test (effective radius + jitter) AND the point is
        closer to the target's slot than to any other slot, so a look at a
        neighbouring icon never counts as the target in any arrangement."""
        if not circle_contains(
            cx_px, cy_px, self.effective_radius_px(target) + self.jitter_px, px, py
        ):
            return False
        own = math.hypot(px - cx_px, py - cy_px)
        for index, (x_norm, y_norm) in enumerate(self.icon_slots):
            if index == target.slot_index:
                continue
            if math.hypot(px - x_norm * self.screen_w, py - y_norm * self.screen_h) < own:
                return False
        return True

    def _shrink_details(self) -> dict:
        return {"n_icons": len(self.icon_slots), "arrangement": self.arrangement}

    def scene_spec(self) -> dict:
        return {
            "mode": "icons",
            "slots": list(self.icon_slots),
            "shapes": list(self.icon_shapes),
        }
