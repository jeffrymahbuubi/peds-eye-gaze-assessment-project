"""The eight buttons of the Choice-making board (SPEC-scene-cause-effect-task.md 4.5, W3, S3).

Rounded rectangles in the operator design system's colours with the object's picture (a coloured
swatch until the art exists) and its English label. On top of a button, when the canvas asks:

* the **glow** on the button being looked at (Switch only: ``canvas.show_glow``; greyed with Dwell,
  W3), a soft halo in the theme's particle colour;
* the **instant ring** and the **dwell ring** of the other tests, around the button being looked at;
* the **visual-cue pulse** on the prompted button (S3): its border thickens and fades back about once
  a second;
* the **selected highlight** of the chosen button at the start of its effect.

Pure drawing: the caller says which state each button is in.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF

from .design_tokens import ACCENT, ACCENT_SUBTLE, BORDER_STRONG, FONT_FAMILY, INK, PANEL

PULSE_PERIOD_S = 1.0
SELECTED_MS = 1200.0  # how long the chosen button keeps its highlight at the start of the effect


@dataclass(slots=True)
class ButtonLook:
    """What the buttons look like this frame."""

    theme: dict
    hover_slot: int = -1  # the button the pointer is on; only a selectable moment counts
    selectable: bool = True
    show_glow: bool = False
    show_instant: bool = False
    show_ring: bool = False
    progress: float = 0.0
    cue_slot: int = -1
    pulse: float = 0.0  # 0..1 phase of the visual cue (1 = thickest border)
    selected_slot: int = -1
    selected_strength: float = 0.0  # 1 = just chosen, fading to 0


def pulse_phase(t_s: float) -> float:
    """0..1..0 once per :data:`PULSE_PERIOD_S` (a half sine), for the visual cue."""
    return sin(pi * ((t_s / PULSE_PERIOD_S) % 1.0))


def selected_strength(elapsed_ms: float) -> float:
    return max(0.0, 1.0 - elapsed_ms / SELECTED_MS)


def _glow(painter: QPainter, rect: QRectF, colour: QColor, radius: float) -> None:
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(7):
        halo = QColor(colour)
        halo.setAlpha(int(110 * (1 - i / 7)))
        painter.setPen(QPen(halo, 5.0))
        grown = rect.adjusted(-i * 4.0, -i * 4.0, i * 4.0, i * 4.0)
        painter.drawRoundedRect(grown, radius + i * 4.0, radius + i * 4.0)


def _check(painter: QPainter, rect: QRectF, strength: float) -> None:
    painter.setPen(QPen(QColor(ACCENT), max(3.0, rect.height() * 0.035), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    x, y, s = rect.right() - rect.width() * 0.18, rect.top() + rect.height() * 0.16, rect.height() * 0.09
    painter.setOpacity(strength)
    painter.drawPolyline(
        QPolygonF([QPointF(x - s, y), QPointF(x - s * 0.3, y + s * 0.7), QPointF(x + s, y - s * 0.7)])
    )
    painter.setOpacity(1.0)


def draw_button(
    painter: QPainter, slot: int, rect: QRectF, label: str, swatch: str, picture: QPixmap | None, look: ButtonLook
) -> None:
    """One button in its current state."""
    radius = min(rect.width(), rect.height()) * 0.1
    looked_at = slot == look.hover_slot and look.selectable
    theme = look.theme
    if looked_at and look.show_glow:
        _glow(painter, rect, QColor(theme.get("particle_color", "#ffd54f")), radius)
    chosen = slot == look.selected_slot and look.selected_strength > 0
    painter.setBrush(QColor(ACCENT_SUBTLE) if chosen else QColor(PANEL))
    painter.setPen(QPen(QColor(ACCENT if chosen else BORDER_STRONG), 5.0 if chosen else 3.0))
    painter.drawRoundedRect(rect, radius, radius)

    # The picture in the upper part, the label under it.
    label_px = max(12, int(rect.height() * 0.13))
    art = QRectF(rect.left() + rect.width() * 0.15, rect.top() + rect.height() * 0.08, rect.width() * 0.7, rect.height() * 0.62)
    if picture is not None and not picture.isNull():
        fitted = QRectF(0, 0, picture.width() / picture.devicePixelRatio(), picture.height() / picture.devicePixelRatio())
        fitted.moveCenter(art.center())
        painter.drawPixmap(fitted.topLeft(), picture)
    else:
        painter.setPen(QPen(QColor(0, 0, 0, 80), 2.0))
        painter.setBrush(QColor(swatch))
        side = min(art.width(), art.height())
        painter.drawEllipse(QRectF(art.center().x() - side / 2, art.center().y() - side / 2, side, side))
    font = QFont(FONT_FAMILY)
    font.setPixelSize(label_px)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(INK))
    painter.drawText(
        QRectF(rect.left(), rect.top() + rect.height() * 0.72, rect.width(), rect.height() * 0.24),
        Qt.AlignmentFlag.AlignCenter, label,
    )

    if chosen:
        _check(painter, rect, look.selected_strength)
    if slot == look.cue_slot:  # the visual cue (S3): the border thickens and fades back
        cue = QColor(ACCENT)
        cue.setAlpha(int(255 * (0.35 + 0.65 * look.pulse)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(cue, 3.0 + 7.0 * look.pulse))
        painter.drawRoundedRect(rect, radius, radius)
    if looked_at:
        ring = QColor(theme.get("cursor_color", "#ffffff"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if look.show_instant:
            painter.setPen(QPen(ring, 5.0))
            painter.drawRoundedRect(rect.adjusted(-5, -5, 5, 5), radius + 5, radius + 5)
        if look.show_ring and look.progress > 0:
            r = min(rect.width(), rect.height()) / 2 + 12
            painter.setPen(QPen(ring, 8.0))
            span = int(-360 * 16 * max(0.0, min(1.0, look.progress)))
            c = rect.center()
            painter.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 90 * 16, span)
