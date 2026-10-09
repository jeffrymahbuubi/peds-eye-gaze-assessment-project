"""What the Target Map draws for Follow the Target (SPEC-input-selection-and-follow.md 4.5; the
drawing code is :mod:`target_map_paint`, which calls this).

The Summary map shows the target's path as a faint line with a mark where each trial ended, and
the Scanpath overlay's fixation dots, like any moving-target map. The selected trial of the
Detailed view shows the target's path plus the **pointer path** (gaze, or the mouse), split by the
report where the pointer entered or left the target's area: the stretches on the target in the
map's dark path blue, the stretches off it in its skipped grey, thinner and **dashed** (SPEC-
design-system-phase4.md H4: the same tokens as the selection tasks' map; the dashes, so that on and
off read without colour, are the user's answer of 2026-10-09). The legend's icons for these three
lines are drawn here too.

Pure drawing and reading of the report's own ``follow.trials[*].pointer_path``; nothing is computed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPolygonF

from .design_tokens import MAP_PATH_DARK, MAP_SKIPPED, MAP_SLOT
from .report_format_follow import follow_block

FOLLOW_ON = MAP_PATH_DARK  # the pointer on the target (the dark end of the selection tasks' path)
FOLLOW_OFF = MAP_SKIPPED  # the pointer off the target
TRACK = MAP_SLOT  # the path of the target itself
ON_WIDTH, OFF_WIDTH = 3.0, 2.0  # design px: the off-target stretches are thinner too
OFF_DASHES = (4.0, 3.0)  # an off-target stretch: dash and gap, in pen widths
LINE_KINDS = ("track", "on", "off")  # the legend icons of the three lines

PenFactory = Callable[..., QPen]


def off_pen(pen: PenFactory, width: float) -> QPen:
    """The pen of an off-target stretch (and of its legend icon): the skipped grey, dashed. The
    caps are flat, so the gaps stay open (a round cap would grow every dash by half a pen width
    at both ends and close a gap this narrow)."""
    out = pen(FOLLOW_OFF, width, Qt.PenStyle.DashLine)
    out.setCapStyle(Qt.PenCapStyle.FlatCap)
    out.setDashPattern(list(OFF_DASHES))
    return out


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
    """The pointer path of one trial: the off-target stretches first (grey, thinner, dashed), the
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
            p.setPen(off_pen(pen, OFF_WIDTH * unit) if off else pen(FOLLOW_ON, ON_WIDTH * unit))
            p.drawPolyline(QPolygonF(points))


def paint_line_symbol(p: QPainter, rect: QRectF, kind: str, pen: PenFactory) -> None:
    """A legend icon for one of the map's lines (``track`` / ``on`` / ``off``): a short stroke
    across the middle of ``rect``, in the colour, width and dashes the map draws it."""
    unit = max(0.5, min(rect.width(), rect.height()) / 40.0)
    y = rect.center().y()
    start, end = QPointF(rect.left() + 0.1 * rect.width(), y), QPointF(rect.right() - 0.1 * rect.width(), y)
    p.save()
    if kind == "track":
        p.setPen(pen(TRACK, 2 * unit))
    elif kind == "off":
        p.setPen(off_pen(pen, OFF_WIDTH * unit * 1.5))
    else:
        p.setPen(pen(FOLLOW_ON, ON_WIDTH * unit * 1.5))
    p.drawLine(start, end)
    p.restore()
