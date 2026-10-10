"""The status badge: a glyph and a word in a pill (SPEC-design-system-phase2.md H1, H2;
``docs/design/fable-proposal.md`` 2.5).

A state is never carried by colour, bold or tint alone: every badge pairs a painted glyph
shape with the state word, so it reads the same in grey scale and for a colour-blind
operator. The Test List's Status cells, the Setup tracker and calibration badges and the
run bar's tracking state all use this one widget; the report's Outcome cell reuses it in
phase 4.

The pill is 24 px high with a full radius, the glyph a 12 px pixmap painted with
``QPainter`` (:mod:`~src.ui.glyphs`), a 6 px gap, then the word at the caption step in
weight 600. Colours come from :mod:`~src.ui.design_tokens` only. The widget paints itself,
so it looks the same inside the dashboard and in the standalone window, and its
``accessibleName`` is the word, so a screen reader and qt-mcp read the state.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from .design_tokens import (
    DANGER_SUBTLE,
    DANGER_TEXT,
    FONT_FAMILY,
    HEADER,
    SUCCESS_SUBTLE,
    SUCCESS_TEXT,
    TEXT_SECONDARY,
    TYPE_CAPTION,
    WARNING_SUBTLE,
    WARNING_TEXT,
)
from .glyphs import (
    GLYPH_CIRCLE,
    GLYPH_DASHED,
    GLYPH_HALF,
    GLYPH_RING,
    GLYPH_SQUARE,
    GLYPH_TRIANGLE,
    glyph_pixmap,
)

BADGE_HEIGHT = 24
BADGE_RADIUS = BADGE_HEIGHT // 2  # a full pill
BADGE_PADDING = 8  # left and right
GLYPH_PX = 12
GLYPH_GAP = 6


class BadgeLook(NamedTuple):
    glyph: str
    fill: str
    text: str  # the word's colour, and the glyph's
    word: str  # the word used when a state is set without one


_SUCCESS = (GLYPH_CIRCLE, SUCCESS_SUBTLE, SUCCESS_TEXT)
_NEUTRAL = (GLYPH_RING, HEADER, TEXT_SECONDARY)
_WARNING = (GLYPH_TRIANGLE, WARNING_SUBTLE, WARNING_TEXT)
_DANGER = (GLYPH_SQUARE, DANGER_SUBTLE, DANGER_TEXT)

# Glyph and colours per kind (H2): the proposal's 2.5 plus the user's V1 (Not calibrated is
# the warning triangle like Data missing; Skipped a dashed hollow ring in neutral grey).
LOOKS: dict[str, BadgeLook] = {
    "done": BadgeLook(*_SUCCESS, "Done"),
    "connected": BadgeLook(*_SUCCESS, "Connected"),
    "calibrated": BadgeLook(*_SUCCESS, "Calibrated"),
    "tracking_ok": BadgeLook(*_SUCCESS, "Tracking OK"),
    "not_done": BadgeLook(*_NEUTRAL, "Not done"),
    "ended_early": BadgeLook(GLYPH_HALF, WARNING_SUBTLE, WARNING_TEXT, "Ended early"),
    "data_missing": BadgeLook(*_WARNING, "Data missing"),
    "not_calibrated": BadgeLook(*_WARNING, "Not calibrated"),
    "no_gaze": BadgeLook(*_WARNING, "No gaze"),
    "disconnected": BadgeLook(*_DANGER, "Disconnected"),
    "tracker_disconnected": BadgeLook(*_DANGER, "Tracker disconnected"),
    "skipped": BadgeLook(GLYPH_DASHED, HEADER, TEXT_SECONDARY, "Skipped"),
}
KINDS = tuple(LOOKS)


def badge_font() -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPixelSize(TYPE_CAPTION)
    font.setWeight(QFont.Weight.DemiBold)  # 600
    return font


class StatusBadge(QWidget):
    """A pill with a state glyph and the state word. ``set_state(kind, text)`` changes both;
    ``text`` defaults to the kind's own word ("Not done", "Tracking OK", ...)."""

    def __init__(self, kind: str = "not_done", text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhStatusBadge")
        self.setFixedHeight(BADGE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._font = badge_font()
        self._kind = ""
        self._text = ""
        self.set_state(kind, text)

    # -- state ------------------------------------------------------------------

    def set_state(self, kind: str, text: str = "") -> None:
        if kind not in LOOKS:
            raise ValueError(f"Unknown badge kind '{kind}'. Known: {list(KINDS)}")
        self._kind = kind
        self._text = text or LOOKS[kind].word
        self.setAccessibleName(self._text)
        self.setFixedWidth(self.sizeHint().width())
        self.update()

    def kind(self) -> str:
        return self._kind

    def text(self) -> str:
        return self._text

    def look(self) -> BadgeLook:
        return LOOKS[self._kind]

    # -- size and painting -------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        word = QFontMetrics(self._font).horizontalAdvance(self._text)
        return QSize(BADGE_PADDING + GLYPH_PX + GLYPH_GAP + word + BADGE_PADDING + 1, BADGE_HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self.sizeHint()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        look = self.look()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(look.fill))
        painter.drawRoundedRect(QRectF(self.rect()), BADGE_RADIUS, BADGE_RADIUS)
        pixmap = glyph_pixmap(look.glyph, look.text, GLYPH_PX, self.devicePixelRatioF())
        painter.drawPixmap(QPointF(BADGE_PADDING, (self.height() - GLYPH_PX) / 2.0), pixmap)
        painter.setFont(self._font)
        painter.setPen(QColor(look.text))
        left = BADGE_PADDING + GLYPH_PX + GLYPH_GAP
        painter.drawText(
            QRectF(left, 0, self.width() - left, self.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()
