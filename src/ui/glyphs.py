"""The painted glyphs of the operator UI (SPEC-design-system-phase2.md H1-H3;
``docs/design/fable-proposal.md`` 2.5).

A status badge and an alert's glyph tile show their state as a shape *and* a word, so a
state is never carried by colour alone. The shapes are drawn with ``QPainter`` into a small
pixmap, not typed as font characters, so they cannot fall back to a missing glyph (the
proposal's rule). Colours are passed in by the caller from :mod:`~src.ui.design_tokens`;
nothing here is a literal colour.

Besides the seven state shapes there are six action shapes (the Test List's right-side buttons;
Delete Test reuses the square) and five task shapes (its Task column), drawn the same way: a
1.5 px stroke at 12 px, sharp at any device pixel ratio.
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
STATE_GLYPHS = (
    GLYPH_CIRCLE,
    GLYPH_RING,
    GLYPH_HALF,
    GLYPH_TRIANGLE,
    GLYPH_SQUARE,
    GLYPH_DASHED,
    GLYPH_INFO,
)

GLYPH_PLUS = "plus"  # Add New Test
GLYPH_SLIDERS = "sliders"  # Configure Test
GLYPH_PLAY = "play"  # Run Test
GLYPH_DOCUMENT = "document"  # View Report
GLYPH_COPY = "copy"  # Copy Test: two squares
GLYPH_FOLDER = "folder"  # Open Subject Folder
ACTION_GLYPHS = (GLYPH_PLUS, GLYPH_SLIDERS, GLYPH_PLAY, GLYPH_DOCUMENT, GLYPH_COPY, GLYPH_FOLDER)

GLYPH_TASK_STATIC = "task_static"  # Static Click: a dot in a ring
GLYPH_TASK_GRID = "task_grid"  # Grid Click: a 3 x 3 block
GLYPH_TASK_FOLLOW = "task_follow"  # Follow the Target: a path with an arrow head
GLYPH_TASK_SEARCH = "task_search"  # Scanning Search: a magnifier
GLYPH_TASK_CHOICE = "task_choice"  # Choice-making: two squares, one picked
TASK_GLYPHS = (GLYPH_TASK_STATIC, GLYPH_TASK_GRID, GLYPH_TASK_FOLLOW, GLYPH_TASK_SEARCH, GLYPH_TASK_CHOICE)

GLYPHS = STATE_GLYPHS + ACTION_GLYPHS + TASK_GLYPHS


DASHES = 6  # the dashed ring is this many dashes round
ICON_DPRS = (1.0, 1.25, 1.5, 2.0)  # the pixel ratios an icon holds a pixmap for; Qt takes the fit


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


def _draw_signal(painter: QPainter, shape: str, rect: QRectF, color: QColor, line: float) -> None:
    """The action and task shapes, laid out on a 12 x 12 grid that scales with ``rect``; strokes
    are ``line`` wide (1.5 px at 12 px), solid parts are whole-pixel squares or filled polygons."""
    u = min(rect.width(), rect.height()) / 12.0

    def at(x: float, y: float) -> QPointF:
        return QPointF(rect.left() + x * u, rect.top() + y * u)

    def stroke(cap: Qt.PenCapStyle = Qt.PenCapStyle.FlatCap) -> None:
        pen = _pen(color, line)
        pen.setCapStyle(cap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def fill() -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

    # A 1.5 px stroke centred 0.25 px off a pixel boundary covers one pixel row fully and the next
    # by half, so the strokes below sit on x.75 / x.25 centres instead of blurring over two rows.
    if shape == GLYPH_PLUS:
        stroke()
        painter.drawLine(at(2, 5.75), at(10, 5.75))
        painter.drawLine(at(5.75, 2), at(5.75, 10))
    elif shape == GLYPH_SLIDERS:  # three tracks, a knob on each at a different place
        for y, knob in ((2.75, 8.0), (6.25, 4.0), (9.75, 7.0)):
            stroke()
            painter.drawLine(at(1, y), at(11, y))
            fill()
            painter.drawEllipse(at(knob, y), 1.75 * u, 1.75 * u)
    elif shape == GLYPH_PLAY:
        painter.setPen(_pen(color, 1.0))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([at(3.2, 1.5), at(10.2, 6), at(3.2, 10.5)]))
    elif shape == GLYPH_DOCUMENT:  # a page with a cut corner and two lines of text
        stroke()
        painter.drawPolygon(QPolygonF([at(2.75, 1.75), at(6.5, 1.75), at(9.25, 4.5), at(9.25, 10.25), at(2.75, 10.25)]))
        painter.drawLine(at(4.75, 5.5), at(7.25, 5.5))
        painter.drawLine(at(4.75, 8.0), at(7.25, 8.0))
    elif shape == GLYPH_COPY:  # the back square shows only where the front one does not cover it
        stroke()
        painter.drawPolyline(QPolygonF([at(7.25, 4.0), at(7.25, 1.75), at(1.75, 1.75), at(1.75, 7.25), at(4.0, 7.25)]))
        painter.drawRect(QRectF(at(4.75, 4.75), at(10.25, 10.25)))
    elif shape == GLYPH_FOLDER:
        stroke()
        painter.drawPolygon(
            QPolygonF([at(1.75, 10.25), at(1.75, 2.75), at(4.75, 2.75), at(6.25, 4.5), at(10.25, 4.5), at(10.25, 10.25)])
        )
    elif shape == GLYPH_TASK_STATIC:  # a dot in a ring
        stroke()
        painter.drawEllipse(at(6, 6), 4.25 * u, 4.25 * u)
        fill()
        painter.drawEllipse(at(6, 6), 1.75 * u, 1.75 * u)
    elif shape == GLYPH_TASK_GRID:  # nine 2 px squares, 2 px apart
        fill()
        for row in range(3):
            for col in range(3):
                painter.drawRect(QRectF(at(1 + 4 * col, 1 + 4 * row), at(3 + 4 * col, 3 + 4 * row)))
    elif shape == GLYPH_TASK_FOLLOW:  # a path that ends in an arrow head
        stroke(Qt.PenCapStyle.RoundCap)
        painter.drawLine(at(2.5, 9.5), at(9.5, 2.5))
        painter.drawPolyline(QPolygonF([at(4.5, 2.5), at(9.5, 2.5), at(9.5, 7.5)]))
    elif shape == GLYPH_TASK_CHOICE:  # a filled square, the one picked, beside an outlined one
        fill()
        painter.drawRect(QRectF(at(0.5, 3.5), at(5.5, 8.5)))
        stroke()
        painter.drawRect(QRectF(at(7.25, 4.25), at(10.75, 7.75)))
    else:  # GLYPH_TASK_SEARCH: a magnifier
        stroke(Qt.PenCapStyle.RoundCap)
        painter.drawEllipse(at(5, 5), 3.5 * u, 3.5 * u)
        painter.drawLine(at(7.75, 7.75), at(10.5, 10.5))


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
    elif shape == GLYPH_INFO:  # a ring with a dot over a stem
        painter.setPen(_pen(color, line))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        dot = max(1.0, size * 0.09)
        painter.drawEllipse(QPointF(cx, rect.top() + size * 0.32), dot, dot)
        stem = max(1.0, size * 0.07)
        painter.drawRect(QRectF(cx - stem, rect.top() + size * 0.45, 2 * stem, size * 0.28))
    else:
        _draw_signal(painter, shape, rect, color, line)
    painter.restore()


def glyph_pixmap(shape: str, color: QColor | str, size: int = 12, dpr: float = 1.0, slot: int = 0) -> QPixmap:
    """A transparent ``size`` x ``size`` (logical px) pixmap with ``shape`` drawn in ``color``;
    ``dpr`` makes it sharp on a scaled display. A ``slot`` larger than ``size`` makes the pixmap a
    ``slot`` x ``slot`` square with the glyph centred in it, so a label that follows starts at the
    same x on every button whatever the shape."""
    scale = dpr if dpr and dpr > 0 else 1.0
    extent = max(size, slot)
    pixmap = QPixmap(round(extent * scale), round(extent * scale))
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    offset = (extent - size) / 2.0
    draw_glyph(painter, shape, QRectF(offset, offset, size, size), color)
    painter.end()
    return pixmap


def glyph_icon(
    shape: str, color: QColor | str, disabled_color: QColor | str, size: int = 12, slot: int = 0
) -> QIcon:
    """A button or item icon of ``shape``: ``color`` normally, ``disabled_color`` while the button
    is off (the theme greys the text, so the glyph is greyed with it). The hovered / focused
    (active) and the selected-row looks are ``color`` too, so Qt does not tint them, and the
    pixmaps come at every :data:`ICON_DPRS` so the glyph is sharp on a scaled display."""
    icon = QIcon()
    for dpr in ICON_DPRS:
        normal = glyph_pixmap(shape, color, size, dpr, slot)
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected):
            icon.addPixmap(normal, mode)
        icon.addPixmap(glyph_pixmap(shape, disabled_color, size, dpr, slot), QIcon.Mode.Disabled)
    return icon
