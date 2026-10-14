"""Scanning Search's search-mode drawing (SPEC-scanning-search-cues.md 4.3, 4.4, S4, S7), split
out of :mod:`.canvas`.

``ScanningTask.scene_spec`` says what the icons scene shows through its ``stage``:

* ``start_dot``: only the small dot at the centre (4.4);
* ``sample``: the target's shape alone at the centre, in the target colour, with "Find this!"
  under it in the Choice-making banner style (4.3 step 2);
* ``blank``: nothing (Match the sample before its first trial);
* ``field``: the field. In Pop-out it is the canvas's own (faint distractors, the target in
  colour), which :func:`draw_search_scene` leaves to it. In Match the sample every icon is drawn
  bright in the target colour, the way today's target is, so only the shape tells them apart
  (S7), and, with ``sample_reminder`` on (off by default), the sample sits small at the top as a reminder.

Pure drawing: the task decides what to show, where and how big.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QRadialGradient

from ..engine.target_size import ICON_DRAW_FRAC
from ..inputs.base import norm_to_px
from ..tasks.search_cues import MATCH_SAMPLE
from .canvas_shapes import SHAPE_CIRCLE, shape_path
from .scene_banner import HEIGHT_FRAC, MARGIN_FRAC, PAD_X_FRAC, banner_font, draw_banner

_TEXT_GAP_FRAC = 0.6  # the gap between the sample and its text, in text heights
_TEXT_SLACK_PX = 2.0  # so the text always fits the strip it was measured for


def bright_gradient(x: float, y: float, hit_radius: float, colour: QColor) -> QRadialGradient:
    """The fill of a bright icon: a radial gradient over the icon's hit radius, lighter at the
    middle -- today's target look (S8)."""
    grad = QRadialGradient(QPointF(x, y), hit_radius)
    grad.setColorAt(0.0, colour.lighter(130))
    grad.setColorAt(1.0, colour)
    return grad


def draw_bright_icon(
    painter: QPainter, x: float, y: float, hit_radius: float, shape: int, colour: QColor
) -> None:
    """One icon drawn like today's target: its shape at :data:`ICON_DRAW_FRAC` of ``hit_radius``."""
    painter.setBrush(bright_gradient(x, y, hit_radius, colour))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(shape_path(x, y, hit_radius * ICON_DRAW_FRAC, shape))


def _shape_of(shapes: list[int], slot: int) -> int:
    return shapes[slot] if 0 <= slot < len(shapes) else SHAPE_CIRCLE


def _draw_start_dot(painter: QPainter, scene: dict, w: int, h: int, dot_colour: QColor) -> None:
    dot = scene.get("dot") or {}
    cx, cy = norm_to_px(dot.get("x_norm", 0.5), dot.get("y_norm", 0.5), w, h)
    radius = float(dot.get("diameter_px", 0.0)) / 2.0
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(dot_colour)
    painter.drawEllipse(QPointF(cx, cy), radius, radius)


def _draw_sample(painter: QPainter, scene: dict, w: int, h: int, colour: QColor) -> None:
    cx, cy = w / 2.0, h / 2.0
    icon_r = float(scene.get("icon_radius_px", 0.0))
    draw_bright_icon(painter, cx, cy, icon_r / ICON_DRAW_FRAC, scene.get("sample_shape", SHAPE_CIRCLE), colour)
    text = str(scene.get("sample_text") or "")
    text_px = float(scene.get("sample_text_px") or 0.0)
    if not text or text_px <= 0:
        return
    # draw_banner puts its strip across the top of a rectangle, MARGIN_FRAC of the lettering in
    # from the sides and the top: size a rectangle so that the strip is exactly as wide as the text.
    margin = text_px * MARGIN_FRAC
    strip_w = QFontMetricsF(banner_font(text_px)).horizontalAdvance(text) + 2 * text_px * PAD_X_FRAC + _TEXT_SLACK_PX
    strip_top = cy + icon_r + text_px * _TEXT_GAP_FRAC
    rect = QRectF(
        cx - strip_w / 2 - margin, strip_top - margin, strip_w + 2 * margin, text_px * HEIGHT_FRAC + 2 * margin
    )
    draw_banner(painter, rect, text, text_px)


def _draw_field(
    painter: QPainter, scene: dict, w: int, h: int, hit_radius: float, colour: QColor, active_slot: int
) -> None:
    slots = scene.get("slots") or []
    shapes = scene.get("shapes") or []
    for i, (xn, yn) in enumerate(slots):
        if i == active_slot:
            continue  # the target is drawn on top by the canvas, with its outlines
        x, y = norm_to_px(xn, yn, w, h)
        draw_bright_icon(painter, x, y, hit_radius, _shape_of(shapes, i), colour)
    reminder = scene.get("reminder")
    if reminder:
        x, y = norm_to_px(reminder["x_norm"], reminder["y_norm"], w, h)
        hit_radius = float(reminder["radius_px"]) / ICON_DRAW_FRAC
        draw_bright_icon(painter, x, y, hit_radius, scene.get("sample_shape", SHAPE_CIRCLE), colour)


def draw_search_scene(
    painter: QPainter,
    scene: dict,
    w: int,
    h: int,
    *,
    hit_radius: float,
    colour: QColor,
    dot_colour: QColor,
    active_slot: int,
) -> bool:
    """Draw the icons scene's stage when it is not the plain Pop-out field; ``False`` (nothing
    drawn) when the canvas should draw that field itself."""
    stage = scene.get("stage", "field")
    if stage == "blank":
        return True
    if stage == "start_dot":
        _draw_start_dot(painter, scene, w, h, dot_colour)
        return True
    if stage == "sample":
        _draw_sample(painter, scene, w, h, colour)
        return True
    if scene.get("search_mode") != MATCH_SAMPLE:
        return False
    _draw_field(painter, scene, w, h, hit_radius, colour, active_slot)
    return True
