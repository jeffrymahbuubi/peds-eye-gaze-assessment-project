"""Shape-following feedback rings (SPEC-scanning-search-cues.md 4.1, S1), split out of
:mod:`.canvas`.

Around a target the canvas draws three rings: the **selectable outline** (4 px, offset 4), the
**on-target ring** (5 px, offset 10) and the **dwell trace** (8 px, offset 16). They used to be
circles whatever the icon; here they follow the icon's own outline, grown outward by the offset
(:func:`shape_outline_path`), and the dwell progress runs along it, clockwise from the top-most
point (:func:`trace_fraction`), as Choice-making's border trace does round a button. For a circle
the outline is the same circle as before, so Static Click, Grid Click and Follow the Target look
unchanged. The hit area is untouched: it stays a circle.

Pure drawing and path maths; the caller says where, how big, which shape and how far along.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .canvas_shapes import SHAPE_SQUARE, SQUARE_CORNER_FRAC, shape_vertices

SELECTABLE_OFFSET_PX, INSTANT_OFFSET_PX, TRACE_OFFSET_PX = 4.0, 10.0, 16.0
SELECTABLE_PEN_PX, INSTANT_PEN_PX, TRACE_PEN_PX = 4.0, 5.0, 8.0
TRACE_STEP_PX = 5.0  # the dwell trace is a polyline with about this spacing (arcs are >= 16 px in radius)
_TOP_SCAN_STEPS = 720  # samples for finding the top-most point of a path that does not start there
_EPS = 1e-9


def shape_outline_path(cx: float, cy: float, r: float, shape: int, offset: float) -> QPainterPath:
    """The closed outline of glyph ``shape`` (radius ``r``, centred on ``cx``, ``cy``, as
    :func:`~.canvas_shapes.shape_path` draws it) grown outward by ``offset`` px: every point of
    it is ``offset`` from the glyph, round at the glyph's convex corners, mitred at its reflex
    ones (the star's inner corners). It runs clockwise on screen and starts at the top-most
    point (the middle of a flat top), so :func:`trace_fraction` needs no search. A circle gives
    the circle of radius ``r + offset``."""
    if shape == SHAPE_SQUARE:
        # A rounded square grown by d is its core square grown by (corner radius + d), round-cornered.
        core = r * (1.0 - SQUARE_CORNER_FRAC)
        pts = [(-core, -core), (core, -core), (core, core), (-core, core)]
        dist = r * SQUARE_CORNER_FRAC + offset
    else:
        pts = shape_vertices(r, shape)
        dist = offset
    if pts is None:  # the circle
        return _circle_outline(cx, cy, r + offset)
    return _offset_polygon([(cx + x, cy + y) for x, y in pts], dist)


def _circle_outline(cx: float, cy: float, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(cx, cy - radius)
    path.arcTo(QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius), 90.0, -360.0)
    path.closeSubpath()
    return path


def _qt_angle(nx: float, ny: float) -> float:
    """The angle Qt's ``arcTo`` uses (degrees, counter-clockwise, y up) of the screen direction (nx, ny)."""
    return math.degrees(math.atan2(-ny, nx))


def _offset_polygon(pts: list[tuple[float, float]], dist: float) -> QPainterPath:
    """The polygon ``pts`` (clockwise on screen) grown outward by ``dist``, as one closed path
    from its top-most point (see :func:`shape_outline_path`)."""
    n = len(pts)
    normals = []  # the unit outward normal of edge i, from pts[i] to pts[i + 1]
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        length = math.hypot(x1 - x0, y1 - y0)
        normals.append(((y1 - y0) / length, (x0 - x1) / length))

    def turn(i: int) -> float:
        """The clockwise turn (rad) at vertex i, from edge i - 1 to edge i: > 0 is a convex corner."""
        (ax, ay), (bx, by) = normals[i - 1], normals[i]
        return math.atan2(ax * by - ay * bx, ax * bx + ay * by)

    def edge_end(i: int) -> tuple[float, float]:
        """Where the grown edge i stops: the mitre point of the next corner when that is reflex."""
        j = (i + 1) % n
        (ax, ay), (bx, by) = normals[i], normals[j]
        if turn(j) < -_EPS and dist > 0:
            k = dist / (1.0 + ax * bx + ay * by)
            return pts[j][0] + k * (ax + bx), pts[j][1] + k * (ay + by)
        return pts[j][0] + dist * ax, pts[j][1] + dist * ay

    def join(path: QPainterPath, j: int) -> None:
        """The round join at convex corner j, from the end of edge j - 1 to the start of edge j."""
        t = turn(j)
        if t > _EPS and dist > 0:
            path.arcTo(_square(pts[j], dist), _qt_angle(*normals[j - 1]), -math.degrees(t))

    top_y = min(y for _x, y in pts)
    tops = [i for i, (_x, y) in enumerate(pts) if y - top_y < 1e-6]
    path = QPainterPath()
    if len(tops) == 1:  # an apex: start in the middle of its round join
        k = tops[0]
        half = math.degrees(turn(k)) / 2.0
        mid = _qt_angle(*normals[k - 1]) - half
        path.moveTo(
            pts[k][0] + dist * math.cos(math.radians(mid)), pts[k][1] - dist * math.sin(math.radians(mid))
        )
        if dist > 0:
            path.arcTo(_square(pts[k], dist), mid, -half)
        for step in range(n):
            i = (k + step) % n
            path.lineTo(*edge_end(i))
            if (i + 1) % n == k:
                break
            join(path, (i + 1) % n)
        if dist > 0:
            path.arcTo(_square(pts[k], dist), _qt_angle(*normals[k - 1]), -half)
    else:  # a flat top (two corners, the left one first): start in the middle of its grown edge
        a = min(tops, key=lambda i: pts[i][0])
        sx, sy = pts[a][0] + dist * normals[a][0], pts[a][1] + dist * normals[a][1]
        ex, ey = edge_end(a)
        mid_pt = ((sx + ex) / 2.0, (sy + ey) / 2.0)
        path.moveTo(*mid_pt)
        path.lineTo(ex, ey)
        for step in range(1, n + 1):
            i = (a + step) % n
            join(path, i)
            if i == a:
                path.lineTo(*mid_pt)
                break
            path.lineTo(*edge_end(i))
    path.closeSubpath()
    return path


def _square(centre: tuple[float, float], radius: float) -> QRectF:
    return QRectF(centre[0] - radius, centre[1] - radius, 2 * radius, 2 * radius)


def _point_at(path: QPainterPath, length: float):
    return path.pointAtPercent(path.percentAtLength(length))


def _top_length(path: QPainterPath, total: float) -> float:
    """The length along ``path`` at which its top-most point lies (on a flat top, the point
    nearest the middle). 0 for a path that starts there, as :func:`shape_outline_path`'s do."""
    bounds = path.boundingRect()
    start = path.pointAtPercent(0.0)
    middle = bounds.center().x()
    if abs(start.y() - bounds.top()) < 1e-3 and abs(start.x() - middle) < 1e-3:
        return 0.0
    best: tuple[tuple[float, float], float] | None = None
    for k in range(_TOP_SCAN_STEPS):
        length = total * k / _TOP_SCAN_STEPS
        p = _point_at(path, length)
        key = (round(p.y(), 2), abs(p.x() - middle))
        if best is None or key < best[0]:
            best = (key, length)
    assert best is not None
    return best[1]


def _sample_outline(path: QPainterPath) -> list[tuple[float, float]]:
    """``path`` sampled at equal steps of length (about :data:`TRACE_STEP_PX`), clockwise from its
    top-most point round to it again: the first and last points are the same. Slow
    (``percentAtLength`` is about 50 us a call on a circle), so the canvas keeps the result per
    shape and position (:func:`_cached_samples`)."""
    total = path.length()
    if total <= 0.0:
        return []
    start = _top_length(path, total)
    steps = max(8, math.ceil(total / TRACE_STEP_PX))
    points = []
    for k in range(steps + 1):
        point = _point_at(path, (start + total * k / steps) % total)
        points.append((point.x(), point.y()))
    return points


def _cut(points: list[tuple[float, float]], fraction: float) -> QPainterPath:
    """The first ``fraction`` of the length of the closed outline sampled in ``points``, as an open path."""
    out = QPainterPath()
    fraction = max(0.0, min(1.0, fraction))
    if fraction <= 0.0 or len(points) < 2:
        return out
    steps = len(points) - 1
    position = fraction * steps  # the samples are equally spaced, so this is the sample index
    whole = min(int(position), steps)
    out.moveTo(*points[0])
    for k in range(1, whole + 1):
        out.lineTo(*points[k])
    rest = position - whole
    if whole < steps and rest > 0.0:
        (x0, y0), (x1, y1) = points[whole], points[whole + 1]
        out.lineTo(x0 + (x1 - x0) * rest, y0 + (y1 - y0) * rest)
    return out


def trace_fraction(path: QPainterPath, fraction: float) -> QPainterPath:
    """The first ``fraction`` (0..1) of the closed ``path``, clockwise from its top-most point, as
    an open path whose length is ``fraction`` of the whole (so ``fraction`` 1 ends where it
    began). Sampled by length with ``percentAtLength`` / ``pointAtPercent`` -- the percent
    scale is not linear in length once a path has curves -- and, like
    :func:`~.scene_buttons.border_trace_path`, needs no newer Qt than the project's
    (``QPainterPath.trimmed`` is Qt 6.10). ``path`` must run clockwise on screen."""
    return _cut(_sample_outline(path), fraction)


@lru_cache(maxsize=32)
def _cached_samples(x: float, y: float, r: float, shape: int, offset: float) -> list[tuple[float, float]]:
    return _sample_outline(shape_outline_path(x, y, r, shape, offset))


def _ring_pen(colour: QColor | str, width: float) -> QPen:
    # A freshly constructed pen, never the painter's mutated in place: the painter's pen may be
    # NoPen from the fill just before, and changing a NoPen pen's colour or width leaves it
    # NoPen, so the ring would silently never draw (SPEC-2026-09-02.md item 1).
    return QPen(QColor(colour), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def draw_selectable_outline(painter: QPainter, x: float, y: float, r: float, shape: int) -> None:
    """The bright "catch me now" outline of a selectable target: white, 4 px, offset 4."""
    painter.setPen(_ring_pen("#ffffff", SELECTABLE_PEN_PX))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(shape_outline_path(x, y, r, shape, SELECTABLE_OFFSET_PX))


def draw_instant_ring(painter: QPainter, x: float, y: float, r: float, shape: int, colour: QColor | str) -> None:
    """The on-target ring, drawn the instant the pointer is on the target: 5 px, offset 10."""
    painter.setPen(_ring_pen(colour, INSTANT_PEN_PX))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(shape_outline_path(x, y, r, shape, INSTANT_OFFSET_PX))


def draw_dwell_trace(
    painter: QPainter, x: float, y: float, r: float, shape: int, colour: QColor | str, progress: float
) -> None:
    """The dwell progress: 8 px, offset 16, from the top clockwise, ``progress`` (0..1) of the way round."""
    painter.setPen(_ring_pen(colour, TRACE_PEN_PX))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    # Keyed by the position to a tenth of a px, so a target that stays put (every dwell) samples once.
    samples = _cached_samples(round(x, 1), round(y, 1), round(r, 1), shape, TRACE_OFFSET_PX)
    painter.drawPath(_cut(samples, progress))
