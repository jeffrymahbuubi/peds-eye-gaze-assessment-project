"""The results map of the calibration window (SPEC-app-drawn-calibration.md 4.4, Q1, D2; wireframe
``docs/wireframes/calibration-window.md`` state 4).

A rectangle for the monitor with one circle per point at its position. Each circle holds the
point's 0-100 score, coloured green, amber or red by the design tokens; a point with no valid eye
is a grey circle with "-". A weak point (amber, red or grey) has a thicker ring. There is no
overall score on the map, as in Grid 3.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from ..engine.calibration_settings import BAND_FAIR, BAND_GOOD, BAND_NONE, BAND_POOR, PointScore
from .design_tokens import (
    BORDER_STRONG,
    DANGER,
    DANGER_SUBTLE,
    DISABLED_FILL,
    INK,
    PAGE,
    PANEL,
    SUCCESS,
    SUCCESS_SUBTLE,
    TYPE_HEADING,
    WARNING,
    WARNING_SUBTLE,
)

NO_SCORE = "-"
RING_PX = 3
WEAK_RING_PX = 7  # the thicker ring of a point that needs attention
MAP_MARGIN_PX = 24
CIRCLE_FRACTION = 0.13  # circle diameter over the map's height
MIN_CIRCLE_PX = 44

# band -> (fill, ring), the tokens of the states: success, warning, danger and the disabled grey.
BAND_COLOURS: dict[str, tuple[str, str]] = {
    BAND_GOOD: (SUCCESS_SUBTLE, SUCCESS),
    BAND_FAIR: (WARNING_SUBTLE, WARNING),
    BAND_POOR: (DANGER_SUBTLE, DANGER),
    BAND_NONE: (DISABLED_FILL, BORDER_STRONG),
}


class CircleLook(NamedTuple):
    """What one circle shows (also what the tests read instead of pixels)."""

    point: int
    text: str  # the score, or "-"
    band: str
    ring_px: int
    fill: str
    ring: str


def circle_look(score: PointScore) -> CircleLook:
    fill, ring = BAND_COLOURS[score.band]
    text = NO_SCORE if score.band == BAND_NONE else str(score.score)
    return CircleLook(score.point, text, score.band, WEAK_RING_PX if score.weak else RING_PX, fill, ring)


class ResultsMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scores: list[PointScore] = []
        self._aspect = 16 / 9
        self._dimmed = False
        self.setMinimumSize(320, 200)

    def set_scores(self, scores: list[PointScore], aspect: float | None = None) -> None:
        """Show ``scores``; ``aspect`` is the monitor's width over its height."""
        self._scores = list(scores)
        if aspect and aspect > 0:
            self._aspect = aspect
        self.update()

    def set_dimmed(self, dimmed: bool) -> None:
        """Dimmed while the head-position panel is over it (state 5)."""
        self._dimmed = dimmed
        self.update()

    def dimmed(self) -> bool:
        return self._dimmed

    def looks(self) -> list[CircleLook]:
        return [circle_look(score) for score in self._scores]

    def monitor_rect(self) -> QRectF:
        """The rectangle standing for the monitor: the widget less its margins, fitted to the
        monitor's aspect."""
        room = QRectF(self.rect()).adjusted(MAP_MARGIN_PX, MAP_MARGIN_PX, -MAP_MARGIN_PX, -MAP_MARGIN_PX)
        width = min(room.width(), room.height() * self._aspect)
        height = width / self._aspect
        return QRectF(room.center().x() - width / 2.0, room.center().y() - height / 2.0, width, height)

    def circle_center(self, score: PointScore) -> QPointF:
        rect = self.monitor_rect()
        return QPointF(rect.left() + score.x * rect.width(), rect.top() + score.y * rect.height())

    def circle_diameter(self) -> float:
        return max(MIN_CIRCLE_PX, self.monitor_rect().height() * CIRCLE_FRACTION)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.monitor_rect()
        painter.setPen(QPen(QColor(BORDER_STRONG), 2))
        painter.setBrush(QColor(PANEL))
        painter.drawRect(rect)
        font = QFont(painter.font())
        font.setPixelSize(TYPE_HEADING)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        diameter = self.circle_diameter()
        for score, look in zip(self._scores, self.looks(), strict=True):
            centre = self.circle_center(score)
            # The ring is drawn inside the circle's edge, so a thick one does not grow it.
            painter.setPen(QPen(QColor(look.ring), look.ring_px))
            painter.setBrush(QColor(look.fill))
            inset = look.ring_px / 2.0
            circle = QRectF(centre.x() - diameter / 2.0 + inset, centre.y() - diameter / 2.0 + inset,
                            diameter - 2 * inset, diameter - 2 * inset)
            painter.drawEllipse(circle)
            painter.setPen(QColor(INK))
            painter.drawText(circle, int(Qt.AlignmentFlag.AlignCenter), look.text)
        if self._dimmed:
            veil = QColor(PAGE)
            veil.setAlpha(190)
            painter.fillRect(self.rect(), veil)
        painter.end()
