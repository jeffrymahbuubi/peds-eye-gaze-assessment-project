"""What the Target Map draws for Follow the Target (SPEC-input-selection-and-follow.md 4.5; the
drawing code is :mod:`target_map_paint`, which calls this).

The Summary map shows the target's path as a faint line with a mark where each trial ended, and
the Scanpath overlay's fixation dots, like any moving-target map. The selected trial of the
Detailed view shows the target's path plus the **pointer path** (gaze, or the mouse), split by the
report where the pointer entered or left the target's area: the stretches on the target in a dark
colour, the stretches off it lighter and thinner (a difference of lightness and width, not of hue
alone, so it reads without colour). The legend's icons for these three lines are drawn here too.

Pure drawing and reading of the report's own ``follow.trials[*].pointer_path``; nothing is computed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from .design_tokens import LEGACY_REPORT_COLOURS
from .report_format_follow import follow_block

# Phase 4 gives the report map, its legend and the PDF the design tokens; until then they keep
# today's colours (SPEC-design-system-phase1.md H2).
MUTED = LEGACY_REPORT_COLOURS.muted
FOLLOW_ON = "#0F3D52"  # the pointer on the target (the darkest end of the selection tasks' path)
FOLLOW_OFF = "#6FA3BB"  # the pointer off the target: lighter, about 2.8:1 against the white canvas
ON_WIDTH, OFF_WIDTH = 3.0, 2.0  # design px: the off-target stretches are thinner too
LINE_KINDS = ("track", "on", "off")  # the legend icons of the three lines

PenFactory = Callable[..., QPen]


def pointer_runs(report: dict[str, Any] | None, n_trials: int) -> list[list[dict[str, Any]]]:
    """Each report trial's pointer runs (``{"on": bool | None, "pts": [[x, y], ...]}``), one
    list per trial; empty for a trial without them and for every report that is not a Follow
    the Target one."""
    block = follow_block(report or {})
    runs: list[list[dict[str, Any]]] = [[] for _ in range(n_trials)]
    if block is None:
        return runs
    for i, item in enumerate(block.get("trials") or []):
        if i < n_trials and isinstance(item, dict) and isinstance(item.get("pointer_path"), list):
            runs[i] = [r for r in item["pointer_path"] if isinstance(r, dict)]
    return runs


def run_points(runs: list[dict[str, Any]]) -> list[list[float]]:
    """Every point of ``runs`` in order (the S mark sits at the first)."""
    return [
        pt
        for run in runs
        for pt in (run.get("pts") or [])
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]


def paint_pointer_runs(
    p: QPainter, rect: QRectF, runs: list[dict[str, Any]], unit: float, pen: PenFactory
) -> None:
    """The pointer path of one trial: the off-target stretches first (lighter, thinner), the
    on-target ones over them. A run whose ``on`` the report could not tell (``None``) is drawn
    as on target."""
    for off in (True, False):
        for run in runs:
            if (run.get("on") is False) != off:
                continue
            points = [
                QPointF(rect.left() + pt[0] * rect.width(), rect.top() + pt[1] * rect.height())
                for pt in (run.get("pts") or [])
                if isinstance(pt, (list, tuple)) and len(pt) >= 2
            ]
            if len(points) < 2:
                continue
            p.setPen(pen(FOLLOW_OFF if off else FOLLOW_ON, (OFF_WIDTH if off else ON_WIDTH) * unit))
            p.drawPolyline(QPolygonF(points))


def paint_line_symbol(p: QPainter, rect: QRectF, kind: str, pen: PenFactory) -> None:
    """A legend icon for one of the map's lines (``track`` / ``on`` / ``off``): a short stroke
    across the middle of ``rect``, in the colour and width the map draws it."""
    unit = max(0.5, min(rect.width(), rect.height()) / 40.0)
    y = rect.center().y()
    start, end = QPointF(rect.left() + 0.1 * rect.width(), y), QPointF(rect.right() - 0.1 * rect.width(), y)
    p.save()
    if kind == "track":
        faint = QColor(MUTED)
        faint.setAlpha(120)
        p.setPen(pen(faint, 2 * unit))
    elif kind == "off":
        p.setPen(pen(FOLLOW_OFF, OFF_WIDTH * unit * 1.5))
    else:
        p.setPen(pen(FOLLOW_ON, ON_WIDTH * unit * 1.5))
    p.drawLine(start, end)
    p.restore()
