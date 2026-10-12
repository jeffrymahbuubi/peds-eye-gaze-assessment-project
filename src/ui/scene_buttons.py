"""The eight buttons of the Choice-making board (SPEC-scene-cause-effect-task.md 4.5, W3, S3).

Rounded rectangles in the operator design system's colours with the object's picture (a coloured
swatch until the art exists) and its English label. On top of a button, when the canvas asks:

* the **glow** on the button being looked at (Switch only: ``canvas.show_glow``; greyed with Dwell,
  W3), a soft halo in the theme's particle colour;
* the **instant outline** and the **dwell progress** on the button being looked at. Both lie INSIDE the
  button's rectangle, on its own rounded border inset by half the pen, so nothing drawn for the looked-at
  button leaves it (SPEC 3.7, P4, P5): the instant outline is a thin line round the border, the dwell
  progress an 8 px accent line that runs clockwise along the border from top-centre back to top-centre,
  in proportion to the progress (it replaces the circle ring, which overflowed the button by 16 px);
* the **visual-cue pulse** on the prompted button (S3): its border thickens and fades back about once
  a second;
* the **selected highlight** of the chosen button at the start of its effect.

Pure drawing: the caller says which state each button is in.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from .design_tokens import ACCENT, ACCENT_SUBTLE, BORDER_STRONG, FONT_FAMILY, INK, PANEL

PULSE_PERIOD_S = 1.0
TRACE_PEN_PX = 8.0  # the dwell progress line (P4)
INSTANT_PEN_PX = 5.0  # the instant on-target outline (P5)
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


def inset_border(rect: QRectF, radius: float, pen_px: float) -> tuple[QRectF, float]:
    """The rectangle and corner radius to stroke a ``pen_px`` line on so that it lies entirely inside
    ``rect``: the border inset by half the pen, its corners concentric with the button's (P4, P5)."""
    half = pen_px / 2.0
    return rect.adjusted(half, half, -half, -half), max(0.0, radius - half)


def border_trace_path(rect: QRectF, radius: float, fraction: float) -> QPainterPath:
    """The first ``fraction`` (0..1) of the rounded rectangle ``rect`` (corner ``radius``) as a path
    that runs clockwise from top-centre, so ``fraction`` 1 ends back at top-centre (P4). Built from
    lines and arcs, each cut to length, so its length is in proportion to ``fraction`` and it needs
    no newer Qt than the project's (``QPainterPath.trimmed`` is Qt 6.10)."""
    path = QPainterPath()
    fraction = max(0.0, min(1.0, fraction))
    if fraction <= 0.0 or rect.width() <= 0 or rect.height() <= 0:
        return path
    r = max(0.0, min(radius, rect.width() / 2.0, rect.height() / 2.0))
    left, top, right, bottom, cx = rect.left(), rect.top(), rect.right(), rect.bottom(), rect.center().x()
    quarter = pi * r / 2.0
    top_mid = QPointF(cx, top)

    def line(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[QPointF, QPointF] | None, None, float]:
        return (QPointF(x0, y0), QPointF(x1, y1)), None, abs(x1 - x0) + abs(y1 - y0)

    def corner(x: float, y: float, start: float) -> tuple[None, tuple[QRectF, float], float]:
        return None, (QRectF(x, y, 2 * r, 2 * r), start), quarter

    # Clockwise from top-centre: (a line's two points | None, an arc's corner square and start
    # angle | None, the piece's length).
    pieces = [
        line(cx, top, right - r, top),
        corner(right - 2 * r, top, 90.0),
        line(right, top + r, right, bottom - r),
        corner(right - 2 * r, bottom - 2 * r, 0.0),
        line(right - r, bottom, left + r, bottom),
        corner(left, bottom - 2 * r, -90.0),
        line(left, bottom - r, left, top + r),
        corner(left, top, 180.0),
        line(left + r, top, cx, top),
    ]
    remaining = fraction * sum(length for _line, _arc, length in pieces)
    path.moveTo(top_mid)
    for ends, arc, length in pieces:
        if remaining <= 0.0:
            break
        if length > 0.0:
            part = min(1.0, remaining / length)
            if ends is not None:
                a, b = ends
                path.lineTo(QPointF(a.x() + (b.x() - a.x()) * part, a.y() + (b.y() - a.y()) * part))
            elif arc is not None:
                path.arcTo(arc[0], arc[1], -90.0 * part)  # clockwise = a negative sweep
        remaining -= length
    return path


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
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if look.show_instant:  # P5: inside the button, on its border inset by half the pen
            inner, inner_radius = inset_border(rect, radius, INSTANT_PEN_PX)
            painter.setPen(QPen(QColor(theme.get("cursor_color", "#ffffff")), INSTANT_PEN_PX))
            painter.drawRoundedRect(inner, inner_radius, inner_radius)
        if look.show_ring and look.progress > 0:  # P4: the border trace, clockwise from top-centre
            inner, inner_radius = inset_border(rect, radius, TRACE_PEN_PX)
            painter.setPen(
                QPen(QColor(ACCENT), TRACE_PEN_PX, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            )
            painter.drawPath(border_trace_path(inner, inner_radius, look.progress))
