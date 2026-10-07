"""Distractor glyph outlines for the scanning field, split out of :mod:`.canvas`.

Ported from resources/diki (see SPEC-diki-design-audit.md S3.4/S4). Distinct
shapes -- not just distinct colours -- mean the child discriminates form, which
is what a scanning/visual-search assessment is for.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath

SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_TRIANGLE, SHAPE_DIAMOND, SHAPE_HEX, SHAPE_STAR = range(6)


def shape_path(cx: float, cy: float, r: float, shape: int) -> QPainterPath:
    """The outline of glyph ``shape`` centred on (``cx``, ``cy``) with radius ``r``."""
    path = QPainterPath()
    if shape == SHAPE_SQUARE:
        path.addRoundedRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), r * 0.2, r * 0.2)
        return path
    if shape == SHAPE_TRIANGLE:
        pts = [(0, -r), (r * 0.92, r * 0.7), (-r * 0.92, r * 0.7)]
    elif shape == SHAPE_DIAMOND:
        pts = [(0, -r), (r, 0), (0, r), (-r, 0)]
    elif shape == SHAPE_HEX:
        pts = [
            (r * math.cos(math.tau * k / 6), r * math.sin(math.tau * k / 6))
            for k in range(6)
        ]
    elif shape == SHAPE_STAR:
        pts = []
        for k in range(10):
            rad = r if k % 2 == 0 else r * 0.45
            ang = math.tau * k / 10 - math.pi / 2
            pts.append((rad * math.cos(ang), rad * math.sin(ang)))
    else:  # circle
        path.addEllipse(QPointF(cx, cy), r, r)
        return path

    path.moveTo(cx + pts[0][0], cy + pts[0][1])
    for dx, dy in pts[1:]:
        path.lineTo(cx + dx, cy + dy)
    path.closeSubpath()
    return path
