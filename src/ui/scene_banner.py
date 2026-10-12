"""The text prompt banner of the Choice-making scene (SPEC-scene-cause-effect-task.md 3.7, P2, P6).

A rounded caption strip across the top of the scene rectangle: large dark text on a light panel,
the object's prompt sentence (``scene.yaml`` ``prompt:``), on ONE line. The lettering is about
1.5 degrees tall (``scene["prompt_text_px"]``, from :mod:`~src.engine.prompt_text`, never a fixed
px); it shrinks to fit only when a sentence would overflow the strip. Pure drawing: the task says
whether and what to show (``scene["prompt_text"]``, ``None`` when hidden).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

from ..engine.prompt_text import prompt_text_px_for
from ..engine.target_size import DEFAULT_VIEWING_DISTANCE_MM, REFERENCE_MM_PER_PX
from .design_tokens import BORDER_STRONG, FONT_FAMILY, INK, PANEL

MARGIN_FRAC = 0.4  # the gap between the strip and the scene's top, left and right edges
PAD_X_FRAC = 0.5  # the space between the strip's ends and the text
HEIGHT_FRAC = 1.6  # the strip's height
MIN_TEXT_PX = 8  # the smallest the lettering shrinks to


def banner_font(text_px: float) -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(1, round(text_px)))
    font.setBold(True)
    return font


def banner_rect(scene_rect: QRectF, text_px: float) -> QRectF:
    """The strip: across the top of ``scene_rect``, ``text_px`` x :data:`MARGIN_FRAC` in from its
    top, left and right edges."""
    margin = text_px * MARGIN_FRAC
    return QRectF(
        scene_rect.left() + margin, scene_rect.top() + margin,
        max(0.0, scene_rect.width() - 2 * margin), text_px * HEIGHT_FRAC,
    )


def fit_text_px(text_px: float, max_width: float, width_at: Callable[[int], float]) -> int:
    """The pixel size to draw a sentence at: ``text_px`` rounded, or smaller only when the sentence
    (``width_at(px)`` is its width at ``px``) would be wider than ``max_width``."""
    px = max(1, round(text_px))
    if max_width <= 0 or width_at(px) <= max_width:
        return px
    width = width_at(px)
    px = max(MIN_TEXT_PX, int(px * max_width / width))  # first guess, then step down to fit
    while px > MIN_TEXT_PX and width_at(px) > max_width:
        px -= 1
    return px


def draw_banner(painter: QPainter, scene_rect: QRectF, text: str, text_px: float = 0.0) -> None:
    """Draw ``text`` in the strip across the top of ``scene_rect``. ``text_px`` is the lettering's
    height (1.5 deg); 0 means the reference monitor's."""
    if not text:
        return
    if text_px <= 0:
        text_px = prompt_text_px_for(REFERENCE_MM_PER_PX, DEFAULT_VIEWING_DISTANCE_MM)
    strip = banner_rect(scene_rect, text_px)
    if strip.width() <= 0:
        return
    painter.save()
    painter.setBrush(QColor(PANEL))
    painter.setPen(QPen(QColor(BORDER_STRONG), 2.0))
    radius = strip.height() * 0.25
    painter.drawRoundedRect(strip, radius, radius)
    room = strip.width() - 2 * text_px * PAD_X_FRAC
    px = fit_text_px(text_px, room, lambda size: QFontMetricsF(banner_font(size)).horizontalAdvance(text))
    painter.setFont(banner_font(px))
    painter.setPen(QColor(INK))
    painter.drawText(strip, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, text)
    painter.restore()
