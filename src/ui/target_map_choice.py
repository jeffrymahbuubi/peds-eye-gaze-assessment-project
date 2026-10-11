"""What the Scene Map draws for Choice-making (SPEC-scene-cause-effect-task.md W6, 4.9; the drawing
code is :mod:`target_map_paint`, which calls this).

The Summary's map is the canvas at its own aspect with the idle scene faint (each object's idle box as
a labelled placeholder shape: the art is not in the report), each object's look-back area (its box plus
1 deg) as a dashed box, and the eight buttons with their marks: the green circle with the number of
right choices on it and the red X with the number of trials that were not chosen in time. The Scanpath
and Heat map overlays are drawn by the map as for any test. The selected trial of the Detailed view
shows the scene, the target button (coloured by the outcome), the animating object's area and, drawn
darker and thicker than the choosing path, the gaze during the animation and the 0.5 s after it.

Pure drawing and reading of the report's own ``choice`` block (buttons, areas, per-trial paths);
nothing is computed. Every colour is a map token.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from .design_tokens import (
    BORDER_SUBTLE,
    INK,
    MAP_FIXATION,
    MAP_HIT_FILL,
    MAP_HIT_OUTLINE,
    MAP_MISS,
    MAP_SKIPPED,
    MAP_SLOT,
    PANEL,
    TEXT_SECONDARY,
)
from .report_format_choice import choice_block

SYMBOL_KINDS = ("aoi",)  # the legend icon this module draws
MARK_RADIUS = 0.02  # of the canvas width: the right-choice and not-in-time marks on a button
ANIMATION_PATH = INK  # the gaze during the animation: darker than the choosing path
BUTTON_OUTCOME = {"hit": (MAP_HIT_OUTLINE, MAP_HIT_FILL), "timeout": (MAP_MISS, PANEL), "skipped": (MAP_SKIPPED, PANEL)}


class Tools(NamedTuple):
    """The map painter's own helpers, handed in so this module need not import it."""

    pen: Callable[..., QPen]
    label: Callable[..., None]
    mark: Callable[..., None]


def choice_for_map(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """The ``choice`` block when it can be drawn (eight buttons), else ``None``."""
    block = choice_block(report or {})
    if block is None or len(block.get("buttons") or []) != 8 or not block.get("scene_box"):
        return None
    return block


def _box(rect: QRectF, norm: list[float]) -> QRectF:
    """A canvas-normalized ``[x0, y0, x1, y1]`` as a rectangle inside the map's canvas ``rect``."""
    return QRectF(
        rect.left() + norm[0] * rect.width(),
        rect.top() + norm[1] * rect.height(),
        (norm[2] - norm[0]) * rect.width(),
        (norm[3] - norm[1]) * rect.height(),
    )


def _alpha(colour: str, alpha: int) -> QColor:
    out = QColor(colour)
    out.setAlpha(alpha)
    return out


def _paint_scene(
    p: QPainter, rect: QRectF, choice: dict[str, Any], unit: float, tools: Tools, strong: int | None = None
) -> None:
    """The idle scene, faint: its area and each object's idle box with the object's name. ``strong``
    is the slot of the one object drawn less faintly (the selected trial's)."""
    p.setPen(tools.pen(BORDER_SUBTLE, unit))
    p.setBrush(_alpha(BORDER_SUBTLE, 35))
    p.drawRect(_box(rect, choice["scene_box"]))
    for button in choice["buttons"]:
        box = _box(rect, button["box"])
        chosen = strong is not None and button["slot"] == strong
        p.setPen(tools.pen(MAP_SLOT, (1.5 if chosen else 1.0) * unit))
        p.setBrush(_alpha(BORDER_SUBTLE, 150 if chosen else 80))
        p.drawRoundedRect(box, 6 * unit, 6 * unit)
        tools.label(p, box.center(), str(button["label"]), TEXT_SECONDARY, 0.9 * box.width(), 13 * unit)


def _paint_areas(
    p: QPainter, rect: QRectF, choice: dict[str, Any], unit: float, tools: Tools, only: int | None = None
) -> None:
    """The look-back areas as dashed boxes (every object's, or ``only`` the one slot's)."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    for button in choice["buttons"]:
        if button.get("aoi") is None or (only is not None and button["slot"] != only):
            continue
        p.setPen(tools.pen(MAP_FIXATION, (2.5 if only is not None else 1.5) * unit, Qt.PenStyle.DashLine))
        p.drawRoundedRect(_box(rect, button["aoi"]), 4 * unit, 4 * unit)


def _paint_buttons(
    p: QPainter, rect: QRectF, choice: dict[str, Any], unit: float, tools: Tools,
    *, counts: bool, target: tuple[int | None, str | None] = (None, None),
) -> None:
    """The eight buttons with their names; with ``counts`` the marks of what happened on each, else the
    prompted one (``target``: its slot and the trial's outcome) coloured by the outcome."""
    for button in choice["buttons"]:
        cell = _box(rect, button["rect"])
        edge, fill = (MAP_SLOT, PANEL)
        width = unit
        if button["slot"] == target[0] and target[1] in BUTTON_OUTCOME:
            (edge, fill), width = BUTTON_OUTCOME[target[1]], 2.5 * unit
        p.setPen(tools.pen(edge, width, Qt.PenStyle.DashLine if edge == MAP_SKIPPED else Qt.PenStyle.SolidLine))
        # The whole test's buttons let the heat map show through; a trial's are solid.
        p.setBrush(_alpha(fill, 150) if counts else QColor(fill))
        p.drawRoundedRect(cell, 8 * unit, 8 * unit)
        top = QPointF(cell.center().x(), cell.top() + 0.24 * cell.height())
        tools.label(p, top, str(button["label"]), INK, 0.9 * cell.width(), 15 * unit)
        if not counts:
            continue
        marks = [(kind, n) for kind, n in (("hit", button.get("right")), ("timeout", button.get("timeouts"))) if n]
        x0, y0, x1, y1 = button["rect"]
        for i, (kind, n) in enumerate(marks):
            share = 0.5 if len(marks) == 1 else (0.28, 0.72)[i]
            tools.mark(
                p, rect,
                {"x": x0 + share * (x1 - x0), "y": y0 + 0.66 * (y1 - y0), "r": MARK_RADIUS, "outcome": kind, "label": str(n)},
                unit,
            )
    p.setBrush(Qt.BrushStyle.NoBrush)


def paint_choice_scene(p: QPainter, rect: QRectF, choice: dict[str, Any], unit: float, tools: Tools) -> None:
    """The whole test: the faint scene, every look-back area, the buttons with their counts."""
    _paint_scene(p, rect, choice, unit, tools)
    _paint_areas(p, rect, choice, unit, tools)
    _paint_buttons(p, rect, choice, unit, tools, counts=True)


def paint_choice_trial(
    p: QPainter, rect: QRectF, choice: dict[str, Any], index: int, unit: float, tools: Tools
) -> None:
    """One trial, under its gaze path: the scene, the buttons with the prompted one coloured by the
    trial's outcome, the animating object's area and the gaze during the animation (darker)."""
    items = choice.get("trials") or []
    item = items[index] if 0 <= index < len(items) else {}
    slot = item.get("slot")
    _paint_scene(p, rect, choice, unit, tools, strong=slot)
    _paint_areas(p, rect, choice, unit, tools, only=slot)
    _paint_buttons(p, rect, choice, unit, tools, counts=False, target=(slot, item.get("outcome")))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for segment in item.get("lookback_path") or []:
        points = [QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height()) for x, y in segment]
        if len(points) >= 2:
            p.setPen(tools.pen(ANIMATION_PATH, 3.5 * unit))
            p.drawPolyline(QPolygonF(points))


def paint_choice_symbol(p: QPainter, square: QRectF, unit: float, tools_pen: Callable[..., QPen]) -> None:
    """The legend icon of a look-back area: a dashed rounded box."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(tools_pen(MAP_FIXATION, 2.5 * unit, Qt.PenStyle.DashLine))
    p.drawRoundedRect(square.adjusted(square.width() * 0.08, square.height() * 0.2, -square.width() * 0.08, -square.height() * 0.2), 4 * unit, 4 * unit)
