"""Static single-target click task (plan section 5.5).

A single target appears at one of a set of candidate positions; the child
selects it by dwell (or switch). Reaction time and hit rate are the primary
metrics.

The size is the one the run chose and never changes: a position that would put
the target (with its dwell ring) past the canvas edge is moved inward instead,
from the live canvas size (SPEC-target-size-and-motion-paths.md S11.3).
"""

from __future__ import annotations

from typing import Any

from ..engine.target_size import clamp_to_inset, edge_inset_norm
from .base_task import BaseTask, TargetSpec


class ClickStaticTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        n_trials = int(cfg.get("trials", 32))
        target_cfg = cfg.get("target", {})
        radius = float(target_cfg.get("radius_px", 90))
        positions = target_cfg.get("positions") or [[0.5, 0.5]]

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            pos = self.rng.choice(positions)
            targets.append(
                TargetSpec(index=i, x_norm=float(pos[0]), y_norm=float(pos[1]), radius_px=radius)
            )
        return targets

    def target_position(self, target: TargetSpec, elapsed_ns: int) -> tuple[float, float]:
        """The configured position, pulled inward just far enough that the
        circle and its outer ring stay on the canvas. Per frame, because the
        canvas resizes mid-run (HUD hide/show); a position already inside is
        returned untouched."""
        margin_x, margin_y = edge_inset_norm(target.radius_px, self.screen_w, self.screen_h)
        return clamp_to_inset(target.x_norm, margin_x), clamp_to_inset(target.y_norm, margin_y)

    def inset_details(self, target: TargetSpec) -> dict[str, Any] | None:
        if self.target_position(target, 0) == (target.x_norm, target.y_norm):
            return None
        margin_x, margin_y = edge_inset_norm(target.radius_px, self.screen_w, self.screen_h)
        return self._edge_inset_payload(target.radius_px, margin_x, margin_y)
