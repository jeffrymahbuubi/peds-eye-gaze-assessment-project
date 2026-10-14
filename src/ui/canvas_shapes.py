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

# The square's corners are rounded by this fraction of its radius (see :func:`shape_path`).
SQUARE_CORNER_FRAC = 0.2


def shape_vertices(r: float, shape: int) -> list[tuple[float, float]] | None:
    """The corners of a polygon glyph of radius ``r`` about the origin, clockwise on screen
    (y down); ``None`` for the circle and the (rounded) square, which have none. The one source
    of the polygons' geometry, shared by :func:`shape_path` and the shape-following rings of
    :mod:`.canvas_trace`."""
    if shape == SHAPE_TRIANGLE:
        return [(0, -r), (r * 0.92, r * 0.7), (-r * 0.92, r * 0.7)]
    if shape == SHAPE_DIAMOND:
        return [(0, -r), (r, 0), (0, r), (-r, 0)]
    if shape == SHAPE_HEX:
        return [
            (r * math.cos(math.tau * k / 6), r * math.sin(math.tau * k / 6))
            for k in range(6)
        ]
    if shape == SHAPE_STAR:
        pts = []
        for k in range(10):
            rad = r if k % 2 == 0 else r * 0.45
            ang = math.tau * k / 10 - math.pi / 2
            pts.append((rad * math.cos(ang), rad * math.sin(ang)))
        return pts
    return None


def shape_path(cx: float, cy: float, r: float, shape: int) -> QPainterPath:
    """The outline of glyph ``shape`` centred on (``cx``, ``cy``) with radius ``r``."""
    path = QPainterPath()
    if shape == SHAPE_SQUARE:
        corner = r * SQUARE_CORNER_FRAC
        path.addRoundedRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), corner, corner)
        return path
    pts = shape_vertices(r, shape)
    if pts is None:  # circle
        path.addEllipse(QPointF(cx, cy), r, r)
        return path

    path.moveTo(cx + pts[0][0], cy + pts[0][1])
    for dx, dy in pts[1:]:
        path.lineTo(cx + dx, cy + dy)
    path.closeSubpath()
    return path
