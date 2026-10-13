"""The head-position picture (SPEC-gaze-stability-and-positioning.md 4.5-4.6, wireframes
``setup.md`` / ``start-test.md``; the Grid 3 track-status look of ``docs/calibration-video/
frames/16_*.png`` and ``34_*.png``).

A grey head box (the GP3 HD's 35 x 22 cm, its inner 70 % lighter: the green zone) with a
stylised face drawn in ``QPainter``. The face **moves** with the eye midpoint, **grows and
shrinks** with the distance and **tilts** with the line between the eyes; it is green with a
smile, orange with a flat mouth, red with a frown. Under the box is the **Close-Far bar**: a dot
on a 45-85 cm scale with the 55-75 cm band shaded green. With no eyes, or no tracker, the box is
empty.

The widget only draws a :class:`~src.inputs.head_position.HeadReading`; the model that makes it
is :mod:`src.inputs.head_position` and the timer that feeds it is
:class:`~src.ui.head_position_panel.HeadPositionPanel`. Every colour is a design token, never a
hex value of its own; the state is also in words under the picture, never in colour alone.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..inputs.head_position import (
    BAR_MAX_CM,
    BAR_MIN_CM,
    CENTRE_INNER_FRACTION,
    HEAD_BOX_HEIGHT_CM,
    HEAD_BOX_WIDTH_CM,
    NOT_CONNECTED,
    Z_GREEN_MAX_CM,
    Z_GREEN_MIN_CM,
    HeadReading,
    HeadState,
)
from .design_tokens import (
    BORDER_STRONG,
    DANGER,
    FONT_FAMILY,
    HEADER,
    PAGE,
    PANEL,
    RADIUS,
    SLIDER_GROOVE,
    SUCCESS,
    TEXT_SECONDARY,
    TYPE_CAPTION,
    WARNING,
)

WIDGET_WIDTH = 240  # "about 240 x 200 px" with the status line under it
BAR_GAP = 8  # between the box and the Close-Far bar
BAR_HEIGHT = 34  # the bar, its dot and the tick words under it
TRACK_HEIGHT = 6
DOT_RADIUS = 7

# The face is drawn in units of its own radius R, so the three mouths and the eyes are
# one set of numbers; R is this fraction of the box height at FACE_REFERENCE_CM.
FACE_RADIUS_FRACTION = 0.25

STATE_COLOURS = {
    HeadState.GREEN: SUCCESS,
    HeadState.ORANGE: WARNING,
    HeadState.RED: DANGER,
}


def _caption_font() -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPixelSize(TYPE_CAPTION)
    return font


class HeadPositionWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhHeadPosition")
        self.setAccessibleName("Head position")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._reading: HeadReading = NOT_CONNECTED
        self._font = _caption_font()
        self.setFixedSize(self.sizeHint())
        self.setAccessibleDescription(NOT_CONNECTED.status_text())

    # -- state ------------------------------------------------------------------

    def set_reading(self, reading: HeadReading) -> None:
        if reading == self._reading:
            return
        self._reading = reading
        self.setAccessibleDescription(reading.status_text())
        self.update()

    def reading(self) -> HeadReading:
        return self._reading

    # -- geometry -----------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        box_height = round(WIDGET_WIDTH * HEAD_BOX_HEIGHT_CM / HEAD_BOX_WIDTH_CM)
        return QSize(WIDGET_WIDTH, box_height + BAR_GAP + BAR_HEIGHT)

    def box_rect(self) -> QRectF:
        """The head box: the 35 : 22 shape, as large as the widget allows above the bar."""
        available_height = self.height() - BAR_GAP - BAR_HEIGHT
        width = min(float(self.width()), available_height * HEAD_BOX_WIDTH_CM / HEAD_BOX_HEIGHT_CM)
        height = width * HEAD_BOX_HEIGHT_CM / HEAD_BOX_WIDTH_CM
        return QRectF((self.width() - width) / 2.0, 0.0, width, height)

    def face_centre(self) -> QPointF:
        """Where the face's centre is drawn (may lie outside the box: the head is outside it)."""
        box, reading = self.box_rect(), self._reading
        return QPointF(box.left() + reading.face_u * box.width(), box.top() + reading.face_v * box.height())

    def _bar_x(self, cm: float, left: float, right: float) -> float:
        fraction = (min(max(cm, BAR_MIN_CM), BAR_MAX_CM) - BAR_MIN_CM) / (BAR_MAX_CM - BAR_MIN_CM)
        return left + fraction * (right - left)

    # -- painting -----------------------------------------------------------------

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = self.box_rect()
        self._paint_box(painter, box)
        if self._reading.has_face:
            self._paint_face(painter, box)
        self._paint_bar(painter, box)
        painter.end()

    def _paint_box(self, painter: QPainter, box: QRectF) -> None:
        painter.setPen(QPen(QColor(BORDER_STRONG), 1))
        painter.setBrush(QColor(HEADER))
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        zone = QRectF(0.0, 0.0, box.width() * CENTRE_INNER_FRACTION, box.height() * CENTRE_INNER_FRACTION)
        zone.moveCenter(box.center())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PAGE))
        painter.drawRect(zone)

    def _paint_face(self, painter: QPainter, box: QRectF) -> None:
        reading = self._reading
        radius = box.height() * FACE_RADIUS_FRACTION * reading.face_scale
        painter.save()
        painter.setClipRect(box.adjusted(1, 1, -1, -1))  # a head outside the box is cut off by it
        painter.translate(self.face_centre())
        painter.rotate(reading.roll_deg)
        painter.scale(radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(STATE_COLOURS[reading.state]))
        painter.drawEllipse(QRectF(-0.88, -1.0, 1.76, 2.0))  # an egg, a little taller than wide
        painter.setBrush(QColor(PANEL))
        for x in (-0.36, 0.36):
            painter.drawEllipse(QPointF(x, -0.2), 0.11, 0.11)
        mouth = QPainterPath()
        if reading.state is HeadState.GREEN:  # a smile
            mouth.moveTo(-0.38, 0.38)
            mouth.quadTo(0.0, 0.78, 0.38, 0.38)
        elif reading.state is HeadState.RED:  # a frown
            mouth.moveTo(-0.38, 0.62)
            mouth.quadTo(0.0, 0.22, 0.38, 0.62)
        else:  # flat
            mouth.moveTo(-0.34, 0.5)
            mouth.lineTo(0.34, 0.5)
        pen = QPen(QColor(PANEL), 0.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(mouth)
        painter.restore()

    def _paint_bar(self, painter: QPainter, box: QRectF) -> None:
        """Close |----[green band]----| Far, a dot at the distance, the band's ends in cm."""
        painter.setFont(self._font)
        metrics = QFontMetricsF(self._font)
        top = box.bottom() + BAR_GAP
        mid_y = top + DOT_RADIUS + 1
        close_width, far_width = metrics.horizontalAdvance("Close"), metrics.horizontalAdvance("Far")
        gap = 6.0
        left, right = box.left() + close_width + gap, box.right() - far_width - gap
        painter.setPen(QColor(TEXT_SECONDARY))
        text_top = mid_y - metrics.height() / 2.0
        painter.drawText(QPointF(box.left(), text_top + metrics.ascent()), "Close")
        painter.drawText(QPointF(box.right() - far_width, text_top + metrics.ascent()), "Far")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(SLIDER_GROOVE))
        track = QRectF(left, mid_y - TRACK_HEIGHT / 2.0, right - left, TRACK_HEIGHT)
        painter.drawRoundedRect(track, TRACK_HEIGHT / 2.0, TRACK_HEIGHT / 2.0)
        band_left, band_right = self._bar_x(Z_GREEN_MIN_CM, left, right), self._bar_x(Z_GREEN_MAX_CM, left, right)
        painter.setBrush(QColor(SUCCESS))
        painter.drawRect(QRectF(band_left, track.top(), band_right - band_left, TRACK_HEIGHT))

        painter.setPen(QColor(TEXT_SECONDARY))
        tick_y = mid_y + DOT_RADIUS + metrics.ascent() + 2.0
        for cm, x in ((Z_GREEN_MIN_CM, band_left), (Z_GREEN_MAX_CM, band_right)):
            label = f"{cm:.0f}"
            painter.drawText(QPointF(x - metrics.horizontalAdvance(label) / 2.0, tick_y), label)

        reading = self._reading
        if reading.has_face and reading.z_cm is not None:
            painter.setPen(QPen(QColor(PANEL), 2))
            painter.setBrush(QColor(STATE_COLOURS[reading.state]))
            painter.drawEllipse(QPointF(self._bar_x(reading.z_cm, left, right), mid_y), DOT_RADIUS, DOT_RADIUS)
