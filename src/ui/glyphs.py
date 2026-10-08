"""The painted glyphs of the operator UI (SPEC-design-system-phase2.md H1-H3;
``docs/design/fable-proposal.md`` 2.5).

A status badge and an alert's glyph tile show their state as a shape *and* a word, so a
state is never carried by colour alone. The shapes are drawn with ``QPainter`` into a small
pixmap, not typed as font characters, so they cannot fall back to a missing glyph (the
proposal's rule). Colours are passed in by the caller from :mod:`~src.ui.design_tokens`;
nothing here is a literal colour.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

GLYPH_CIRCLE = "circle"  # filled circle: done, connected, calibrated, tracking OK, success
GLYPH_RING = "ring"  # hollow circle: not done
GLYPH_HALF = "half"  # half-filled circle: ended early
GLYPH_TRIANGLE = "triangle"  # warning: data missing, not calibrated, no gaze
GLYPH_SQUARE = "square"  # danger: disconnected, blocked
GLYPH_DASHED = "dashed"  # dashed hollow circle: skipped
GLYPH_INFO = "info"  # an "i" in a circle: a note
GLYPHS = (
    GLYPH_CIRCLE,
    GLYPH_RING,
    GLYPH_HALF,
    GLYPH_TRIANGLE,
    GLYPH_SQUARE,
    GLYPH_DASHED,
    GLYPH_INFO,
)


DASHES = 6  # the dashed ring is this many dashes round


def _pen(color: QColor, width: float, *, ring_diameter: float = 0.0) -> QPen:
    """A ``width`` px pen; with a ``ring_diameter`` it is dashed into :data:`DASHES` dashes
    that close the ring evenly (a dash pattern counts in pen widths)."""
    pen = QPen(color, width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if ring_diameter:
        period = math.pi * ring_diameter / DASHES / width
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setDashPattern([period * 0.6, period * 0.4])
    return pen


def draw_glyph(painter: QPainter, shape: str, rect: QRectF, color: QColor | str) -> None:
    """Draw ``shape`` filling ``rect`` (a square) in ``color``. The painter keeps its state."""
    if shape not in GLYPHS:
        raise ValueError(f"Unknown glyph '{shape}'. Known: {list(GLYPHS)}")
    color = QColor(color)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = min(rect.width(), rect.height())
    line = max(1.0, size / 8.0)  # 1.5 px at 12 px
    inset = line / 2.0 + size / 12.0
    ring = rect.adjusted(inset, inset, -inset, -inset)
    cx = rect.center().x()

    if shape == GLYPH_CIRCLE:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(rect.adjusted(size / 12.0, size / 12.0, -size / 12.0, -size / 12.0))
    elif shape in (GLYPH_RING, GLYPH_DASHED):
        painter.setPen(_pen(color, line, ring_diameter=ring.width() if shape == GLYPH_DASHED else 0.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
    elif shape == GLYPH_HALF:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPie(ring, 90 * 16, 180 * 16)  # the left half, counter-clockwise from the top
        painter.setPen(_pen(color, line))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
    elif shape == GLYPH_TRIANGLE:
        top, bottom = rect.top() + size * 0.08, rect.bottom() - size * 0.12
        left, right = rect.left() + size * 0.04, rect.right() - size * 0.04
        painter.setPen(_pen(color, 1.0))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(cx, top), QPointF(right, bottom), QPointF(left, bottom)]))
    elif shape == GLYPH_SQUARE:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        margin = max(1, round(size * 0.15))  # whole pixels, so the square's edges are crisp
        painter.drawRect(rect.adjusted(margin, margin, -margin, -margin))
    else:  # GLYPH_INFO: a ring with a dot over a stem
        painter.setPen(_pen(color, line))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        dot = max(1.0, size * 0.09)
        painter.drawEllipse(QPointF(cx, rect.top() + size * 0.32), dot, dot)
        stem = max(1.0, size * 0.07)
        painter.drawRect(QRectF(cx - stem, rect.top() + size * 0.45, 2 * stem, size * 0.28))
    painter.restore()


def glyph_pixmap(shape: str, color: QColor | str, size: int = 12, dpr: float = 1.0) -> QPixmap:
    """A transparent ``size`` x ``size`` (logical px) pixmap with ``shape`` drawn in ``color``;
    ``dpr`` makes it sharp on a scaled display."""
    scale = dpr if dpr and dpr > 0 else 1.0
    pixmap = QPixmap(round(size * scale), round(size * scale))
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_glyph(painter, shape, QRectF(0, 0, size, size), color)
    painter.end()
    return pixmap


def glyph_icon(shape: str, color: QColor | str, disabled_color: QColor | str, size: int = 12) -> QIcon:
    """A button icon of ``shape``: ``color`` normally, ``disabled_color`` while the button is
    off (the theme greys the text, so the glyph is greyed with it)."""
    icon = QIcon()
    icon.addPixmap(glyph_pixmap(shape, color, size), QIcon.Mode.Normal)
    icon.addPixmap(glyph_pixmap(shape, disabled_color, size), QIcon.Mode.Disabled)
    return icon
