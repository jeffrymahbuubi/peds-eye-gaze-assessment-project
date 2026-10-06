"""Grid click task (Compass-style comparison, plan section 5.5).

Cells of an R x C grid light up one at a time in randomized order; the child
selects the lit cell.

**Real grid rendering ported from ``resources/diki``** (SPEC-diki-design-audit.md
S3.3/S4). Previously the GUI only ever drew every cell as a dim, generic
outline circle (the same fallback ``TaskCanvas._draw_layout_slots`` uses for
any multi-item task); the board is the whole point of this task -- it mimics
a communication board -- so cells are now drawn as real rounded-rect grid
cells via ``scene_spec()``'s new ``"grid"`` mode.
"""

from __future__ import annotations

from ..engine.target_size import CellGeometry, grid_cell_geometry
from ..inputs.base import circle_contains
from .base_task import BaseTask, TargetSpec


class ClickGridTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        grid = cfg.get("grid", {})
        rows = int(grid.get("rows", 3))
        cols = int(grid.get("cols", 3))
        margin = float(grid.get("margin_frac", 0.12))
        # The gap wanted between neighbouring cells, in px, resolved from
        # ``grid.gap`` by apply_grid_gap (SPEC-grid-cell-gap.md S4.2). None --
        # the standard gap, also when the config has no ``gap`` at all -- keeps
        # the board exactly as it was (H1).
        gap_px = grid.get("gap_px")
        self.gap_px: float | None = float(gap_px) if gap_px else None
        # GAP_CAPPED is reported once per run, at the first trial start where the
        # live canvas makes grid_cell_geometry cap the gap (like TARGET_SHRUNK);
        # ``gap_capped_px`` is then the gap actually used, for metadata.
        self._gap_reported = False
        self.gap_capped_px: float | None = None
        radius = float(cfg.get("target", {}).get("radius_px", 80))
        n_trials = int(cfg.get("trials", rows * cols))

        cells: list[tuple[float, float]] = []
        span = 1.0 - 2 * margin
        for r in range(rows):
            for c in range(cols):
                x = margin + (span * (c + 0.5) / cols)
                y = margin + (span * (r + 0.5) / rows)
                cells.append((x, y))

        # Kept so the canvas can draw the whole grid (scene_spec's "grid"
        # mode) and for tools/make_replay_fixture.py + the existing
        # layout_slots pytest coverage.
        self.rows = rows
        self.cols = cols
        self.cells = cells
        self.cell_w = span / cols
        self.cell_h = span / rows
        self.layout_slots = cells

        # Randomized order, cycling through all cells if n_trials > len(cells).
        order: list[int] = []
        while len(order) < n_trials:
            shuffled = list(range(len(cells)))
            self.rng.shuffle(shuffled)
            order.extend(shuffled)
        order = order[:n_trials]

        return [
            TargetSpec(
                index=i,
                x_norm=cells[slot][0],
                y_norm=cells[slot][1],
                radius_px=radius,
                slot_index=slot,
            )
            for i, slot in enumerate(order)
        ]

    # -- target fit (SPEC-target-size-and-motion-paths.md S4.3) ---------------

    def _cell_px(self) -> tuple[float, float]:
        """One grid cell's pitch in canvas px, from the live canvas size."""
        return self.cell_w * self.screen_w, self.cell_h * self.screen_h

    def _geometry(self) -> CellGeometry:
        """How a cell is drawn, fitted and hit-tested right now
        (:func:`~src.engine.target_size.grid_cell_geometry`, SPEC-grid-cell-
        gap.md S4.3). Evaluated per frame: the canvas resizes mid-run (HUD
        hide/show), and the gap in px does not follow the canvas."""
        return grid_cell_geometry(*self._cell_px(), self.gap_px)

    def effective_radius_px(self, target: TargetSpec) -> float:
        """The configured radius, capped so the circle sits fully inside its
        cell as the canvas draws it (the drawn cell of ``_geometry``). Evaluated
        per frame: the canvas resizes mid-run (HUD hide/show)."""
        return min(target.radius_px, self._geometry().fit_radius_px)

    def hit_test(
        self, target: TargetSpec, cx_px: float, cy_px: float, px: float, py: float
    ) -> bool:
        """The usual circle test (effective radius + jitter) AND the point lies
        inside the target's own cell: the hitbox never reaches a neighbouring
        cell, yet keeps its full jitter tolerance in the cell's corners. The
        standard gap clips to the whole, unpadded pitch (as always); a wider
        gap clips to the *drawn* cell, so the gap between two cells is a dead
        zone that belongs to neither (SPEC-grid-cell-gap.md H3)."""
        geometry = self._geometry()
        in_cell = abs(px - cx_px) <= geometry.hit_w / 2 and abs(py - cy_px) <= geometry.hit_h / 2
        return in_cell and circle_contains(
            cx_px, cy_px, self.effective_radius_px(target) + self.jitter_px, px, py
        )

    def _shrink_details(self) -> dict:
        return {"rows": self.rows, "cols": self.cols}

    def _start_trial(self, t_ns: int) -> None:
        geometry = self._geometry()
        if geometry.capped and not self._gap_reported:
            self._gap_reported = True
            self.gap_capped_px = geometry.gap_px
            self._record_event(
                "GAP_CAPPED",
                t_ns,
                requested_px=round(geometry.wanted_px, 1),
                used_px=round(geometry.gap_px, 1),
                **self._shrink_details(),
            )
            self._log(
                f"Cell gap limited to ≈{geometry.gap_px:.0f} px (wanted "
                f"≈{geometry.wanted_px:.0f} px) to fit a {self.rows} x {self.cols} grid."
            )
        super()._start_trial(t_ns)

    def scene_spec(self) -> dict:
        # ``cell_inset_px`` is the live inset per side (it depends on the canvas
        # size when the gap is standard or capped), so the canvas draws the very
        # cell the target is fitted and hit-tested against; the app re-reads this
        # every frame.
        return {
            "mode": "grid",
            "rows": self.rows,
            "cols": self.cols,
            "cells": list(self.cells),
            "cell_w": self.cell_w,
            "cell_h": self.cell_h,
            "cell_inset_px": self._geometry().inset,
        }
