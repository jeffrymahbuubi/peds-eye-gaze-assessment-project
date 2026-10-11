"""Placeholder art of the Choice-making scene, drawn in code (SPEC-scene-cause-effect-task.md 4.5).

Until the real art is approved (step 6) every layer is a labelled, coloured shape: the engine, the
effects, the idle life and the look-back can be built and tested without a picture. Each function
draws into a rectangle in the painter's current coordinates; the caller has already applied the
layer's effect transform. Characters get a simple face whose eyes are the blink spots (N3): the
face is drawn with open eyes with the layer, and a blink overlays closed eyelids
(:func:`draw_eyelids`) for about 150 ms.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF

from .design_tokens import FONT_FAMILY, INK

SKIN = QColor("#ffcc80")
_OUTLINE = QColor(0, 0, 0, 90)


def _pen(colour: QColor | str, width: float) -> QPen:
    return QPen(QColor(colour), width)


def draw_backdrop(painter: QPainter, rect: QRectF, label_px: int) -> None:
    """The placeholder sky and lawn, with a note that this is not the final art."""
    horizon = rect.top() + rect.height() * 0.62
    sky = QLinearGradient(rect.topLeft(), QPointF(rect.left(), horizon))
    sky.setColorAt(0.0, QColor("#a9d8f2"))
    sky.setColorAt(1.0, QColor("#e3f3fb"))
    painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), horizon - rect.top()), sky)
    grass = QLinearGradient(QPointF(rect.left(), horizon), rect.bottomLeft())
    grass.setColorAt(0.0, QColor("#a5d6a7"))
    grass.setColorAt(1.0, QColor("#7cb87f"))
    painter.fillRect(QRectF(rect.left(), horizon, rect.width(), rect.bottom() - horizon), grass)
    painter.setPen(_pen("#4a6b4c", 1))
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(10, label_px - 4))
    painter.setFont(font)
    painter.drawText(
        rect.adjusted(10, 0, 0, -6), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        "Park scene (placeholder art)",
    )


def draw_label(painter: QPainter, rect: QRectF, text: str, label_px: int) -> None:
    """The object's name on a white chip at the bottom edge of ``rect``."""
    font = QFont(FONT_FAMILY)
    font.setPixelSize(label_px)
    font.setBold(True)
    painter.setFont(font)
    width = painter.fontMetrics().horizontalAdvance(text) + label_px
    chip = QRectF(0, 0, width, label_px * 1.5)
    chip.moveCenter(QPointF(rect.center().x(), rect.bottom() - chip.height() / 2))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 215))
    painter.drawRoundedRect(chip, chip.height() / 2, chip.height() / 2)
    painter.setPen(_pen(INK, 1))
    painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, text)


def draw_face(painter: QPainter, x: float, y: float, r: float) -> None:
    """A small face for a character: ``(x, y)`` is the centre of its eyes, ``r`` half their width."""
    painter.setPen(_pen(_OUTLINE, 1.5))
    painter.setBrush(SKIN)
    painter.drawEllipse(QPointF(x, y + r * 0.9), r * 2.6, r * 2.6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(INK))
    for side in (-1, 1):
        painter.drawEllipse(QPointF(x + side * r * 0.55, y), r * 0.32, r * 0.42)
    painter.setPen(_pen(INK, max(1.5, r * 0.15)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(x - r * 0.9, y + r * 1.0, r * 1.8, r * 1.2), 200 * 16, 140 * 16)


def draw_eyelids(painter: QPainter, x: float, y: float, r: float) -> None:
    """Closed eyes over :func:`draw_face`: skin-coloured lids with a lash line each."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(SKIN)
    painter.drawRoundedRect(QRectF(x - r * 1.2, y - r * 0.6, r * 2.4, r * 1.2), r * 0.4, r * 0.4)
    painter.setPen(_pen(INK, max(1.5, r * 0.2)))
    for side in (-1, 1):
        cx = x + side * r * 0.55
        painter.drawLine(QPointF(cx - r * 0.4, y), QPointF(cx + r * 0.4, y))


def _shape_rainbow(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    base = colour.hue() if colour.hue() >= 0 else 0
    bands = 5
    width = rect.height() * 0.8 / bands
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(bands):
        arc = QColor.fromHsv((base + 28 * i) % 360, 190, 235)
        painter.setPen(QPen(arc, width * 0.95))
        inset = width * (i + 0.5)
        box = QRectF(rect.left() + inset, rect.top() + inset, rect.width() - 2 * inset, (rect.height() - inset) * 2)
        painter.drawArc(box, 0, 180 * 16)


def _shape_cloud(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    painter.setPen(_pen(_OUTLINE, 2))
    painter.setBrush(colour.lighter(160))
    w, h = rect.width(), rect.height()
    for fx, fy, fw, fh in ((0.0, 0.35, 0.45, 0.65), (0.25, 0.0, 0.5, 0.85), (0.55, 0.3, 0.45, 0.7), (0.2, 0.4, 0.6, 0.6)):
        painter.drawEllipse(QRectF(rect.left() + fx * w, rect.top() + fy * h, fw * w, fh * h))


def _shape_tree(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    w, h = rect.width(), rect.height()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#6d4c41"))
    painter.drawRect(QRectF(rect.left() + w * 0.44, rect.top() + h * 0.5, w * 0.12, h * 0.5))
    painter.setPen(_pen(_OUTLINE, 2))
    painter.setBrush(colour)
    painter.drawEllipse(QRectF(rect.left(), rect.top(), w, h * 0.72))


def _shape_bike(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    w, h = rect.width(), rect.height()
    radius = min(w * 0.22, h * 0.28)
    wheels = (QPointF(rect.left() + w * 0.2, rect.bottom() - radius), QPointF(rect.right() - w * 0.2, rect.bottom() - radius))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(_pen("#212121", max(3.0, radius * 0.18)))
    for wheel in wheels:
        painter.drawEllipse(wheel, radius, radius)
    painter.setPen(_pen(colour, max(4.0, radius * 0.22)))
    seat = QPointF(rect.left() + w * 0.42, rect.top() + h * 0.5)
    bars = QPointF(rect.right() - w * 0.25, rect.top() + h * 0.46)
    painter.drawPolyline(QPolygonF([wheels[0], seat, wheels[1], bars, seat]))
    painter.drawLine(seat, QPointF(seat.x(), rect.top() + h * 0.3))  # the rider's body


def _shape_frame(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    painter.setPen(QPen(colour, max(5.0, rect.width() * 0.03), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    top = rect.top() + rect.height() * 0.04
    left, right = rect.left() + rect.width() * 0.2, rect.right() - rect.width() * 0.2
    painter.drawLine(QPointF(left, top), QPointF(right, top))
    painter.drawLine(QPointF(left, top), QPointF(rect.left() + rect.width() * 0.05, rect.bottom()))
    painter.drawLine(QPointF(right, top), QPointF(rect.right() - rect.width() * 0.05, rect.bottom()))


def _shape_swing(painter: QPainter, rect: QRectF, colour: QColor) -> None:
    w, h = rect.width(), rect.height()
    top = rect.top() - h * 0.09  # the ropes hang from the top bar, just above the seat layer
    painter.setPen(_pen("#6d4c41", 2.5))
    seat_y = rect.top() + h * 0.82
    painter.drawLine(QPointF(rect.left() + w * 0.12, top), QPointF(rect.left() + w * 0.12, seat_y))
    painter.drawLine(QPointF(rect.right() - w * 0.12, top), QPointF(rect.right() - w * 0.12, seat_y))
    painter.setPen(_pen(_OUTLINE, 1.5))
    painter.setBrush(colour)
    painter.drawRoundedRect(QRectF(rect.left(), seat_y, w, h * 0.1), 4, 4)
    painter.drawRoundedRect(QRectF(rect.left() + w * 0.3, rect.top() + h * 0.4, w * 0.4, h * 0.42), 8, 8)


def _shape_child(painter: QPainter, rect: QRectF, colour: QColor, state: str | None) -> None:
    w, h = rect.width(), rect.height()
    painter.setPen(_pen(_OUTLINE, 1.5))
    painter.setBrush(colour)
    painter.drawRoundedRect(QRectF(rect.left() + w * 0.2, rect.top() + h * 0.36, w * 0.6, h * 0.64), 10, 10)
    if state == "blowing":  # the bubble wand raised to the mouth
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(_pen("#0277bd", 3))
        painter.drawEllipse(QPointF(rect.left() + w * 0.88, rect.top() + h * 0.2), w * 0.12, w * 0.12)


def _shape_plain(painter: QPainter, rect: QRectF, colour: QColor, shape: str) -> None:
    painter.setPen(_pen(_OUTLINE, 2))
    painter.setBrush(colour)
    if shape == "ellipse":
        painter.drawEllipse(rect)
    elif shape == "bush":
        for fx, fw in ((0.0, 0.55), (0.3, 0.7), (0.55, 0.45)):
            painter.drawEllipse(QRectF(rect.left() + fx * rect.width(), rect.top(), fw * rect.width(), rect.height()))
    elif shape == "triangle":
        painter.drawPolygon(QPolygonF([QPointF(rect.center().x(), rect.top()), rect.bottomRight(), rect.bottomLeft()]))
    elif shape == "strings":
        painter.setPen(_pen(colour, 2))
        centre = QPointF(rect.center().x(), rect.bottom())
        for fx in (0.15, 0.5, 0.85):
            painter.drawLine(QPointF(rect.left() + fx * rect.width(), rect.top()), centre)
    else:  # "rect", "plank" and any unknown shape
        painter.drawRoundedRect(rect, min(rect.width(), rect.height()) * 0.2, min(rect.width(), rect.height()) * 0.2)


def draw_shape(painter: QPainter, shape: str, rect: QRectF, colour: str, state: str | None = None) -> None:
    """Draw the placeholder ``shape`` of a layer in ``rect``."""
    fill = QColor(colour)
    if shape == "rainbow":
        _shape_rainbow(painter, rect, fill)
    elif shape == "cloud":
        _shape_cloud(painter, rect, fill)
    elif shape == "tree":
        _shape_tree(painter, rect, fill)
    elif shape == "bike":
        _shape_bike(painter, rect, fill)
    elif shape == "frame":
        _shape_frame(painter, rect, fill)
    elif shape == "swing":
        _shape_swing(painter, rect, fill)
    elif shape == "child":
        _shape_child(painter, rect, fill, state)
    else:
        _shape_plain(painter, rect, fill, shape)


def draw_particle(painter: QPainter, style: str, x: float, y: float, diameter: float, alpha: float) -> None:
    """One particle: a see-through bubble with a highlight, or a spark of a pop burst."""
    a = max(0.0, min(1.0, alpha))
    centre, r = QPointF(x, y), diameter / 2
    if style == "bubble":
        painter.setBrush(QColor(173, 224, 255, int(70 * a)))
        painter.setPen(_pen(QColor(2, 119, 189, int(200 * a)), max(1.5, r * 0.12)))
        painter.drawEllipse(centre, r, r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(190 * a)))
        painter.drawEllipse(QPointF(x - r * 0.35, y - r * 0.35), r * 0.25, r * 0.18)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 179, 0, int(255 * a)))
        painter.drawEllipse(centre, r * 0.6, r * 0.6)
        painter.setBrush(QColor(255, 255, 255, int(255 * a)))
        painter.drawEllipse(centre, r * 0.25, r * 0.25)

