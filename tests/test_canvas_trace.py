"""SPEC-scanning-search-cues.md 4.1, S1, acceptance C1: the selectable outline, the on-target ring
and the dwell trace follow the icon's own shape, at offsets 4 / 10 / 16 and pens 4 / 5 / 8 px.

The path maths (``shape_outline_path``, ``trace_fraction``) is checked against the glyph's own
geometry; the painting is checked on a rendered offscreen canvas, pixel by pixel. A circle target must
look as it did before (Static Click, Grid Click, Follow the Target)."""

from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPainterPath
from PySide6.QtWidgets import QApplication

from src.engine.config import load_task_config
from src.engine.task_runner import build_task
from src.ui.canvas import TaskCanvas
from src.ui.canvas_shapes import (
    SHAPE_CIRCLE,
    SHAPE_HEX,
    SHAPE_SQUARE,
    SHAPE_STAR,
    SHAPE_TRIANGLE,
    SQUARE_CORNER_FRAC,
    shape_path,
    shape_vertices,
)
from src.ui.canvas_trace import (
    INSTANT_OFFSET_PX,
    INSTANT_PEN_PX,
    SELECTABLE_OFFSET_PX,
    SELECTABLE_PEN_PX,
    TRACE_OFFSET_PX,
    TRACE_PEN_PX,
    shape_outline_path,
    trace_fraction,
)

SHAPES = range(6)
OFFSETS = (SELECTABLE_OFFSET_PX, INSTANT_OFFSET_PX, TRACE_OFFSET_PX)
CX, CY, R = 300.0, 250.0, 100.0


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _distance_outside(point, shape, r=R):
    """How far ``point`` (canvas px, glyph centred on CX, CY) lies from the glyph's own outline."""
    px, py = point[0] - CX, point[1] - CY
    if shape == SHAPE_CIRCLE:
        return abs(math.hypot(px, py) - r)
    if shape == SHAPE_SQUARE:  # the signed distance of a rounded square
        core, corner = r * (1 - SQUARE_CORNER_FRAC), r * SQUARE_CORNER_FRAC
        qx, qy = abs(px) - core, abs(py) - core
        return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - corner
    pts = shape_vertices(r, shape)
    return min(_seg_dist((px, py), pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


def _points(path: QPainterPath, n=360):
    total = path.length()
    out = []
    for k in range(n):
        p = path.pointAtPercent(path.percentAtLength(total * k / n))
        out.append((p.x(), p.y()))
    return out


# -- the outline: every point is `offset` from the glyph ----------------------------------------------


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("offset", OFFSETS)
def test_the_outline_is_the_glyph_grown_by_the_offset(shape, offset):
    path = shape_outline_path(CX, CY, R, shape, offset)
    for point in _points(path):
        assert abs(_distance_outside(point, shape)) == pytest.approx(offset, abs=0.5)


@pytest.mark.parametrize("shape", SHAPES)
def test_the_outline_starts_at_the_top_most_point_and_runs_clockwise(shape):
    path = shape_outline_path(CX, CY, R, shape, TRACE_OFFSET_PX)
    top = path.boundingRect().top()
    start = path.pointAtPercent(0.0)
    assert start.y() == pytest.approx(top, abs=0.01) and start.x() == pytest.approx(CX, abs=0.01)
    # Clockwise on screen (y down): a quarter of the way round is to the right of the top.
    quarter = path.pointAtPercent(path.percentAtLength(path.length() * 0.2))
    assert quarter.x() > CX + 10
    # ... and the shoelace sum says so too (positive for clockwise with y down).
    pts = _points(path, 720)
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1], strict=True))
    assert area > 0


def test_a_circle_outline_is_the_circle_of_radius_plus_offset():
    for offset in OFFSETS:
        path = shape_outline_path(CX, CY, R, SHAPE_CIRCLE, offset)
        assert path.boundingRect().width() == pytest.approx(2 * (R + offset), abs=0.05)
        for x, y in _points(path):
            assert math.hypot(x - CX, y - CY) == pytest.approx(R + offset, abs=0.3)
        assert path.length() == pytest.approx(2 * math.pi * (R + offset), rel=0.002)


def test_the_stars_reflex_corners_are_mitred_not_looped():
    """A star's inner corners must give a simple outline: the grown edges meet at a point, they do not
    cross and leave a loop (which would draw as a stray spur on the ring)."""
    path = shape_outline_path(CX, CY, R, SHAPE_STAR, TRACE_OFFSET_PX)
    for point in _points(path, 720):
        assert _distance_outside(point, SHAPE_STAR) >= TRACE_OFFSET_PX - 0.5  # never inside the grown glyph


def test_a_zero_offset_outline_is_the_glyph():
    for shape in SHAPES:
        grown = shape_outline_path(CX, CY, R, shape, 0.0)
        plain = shape_path(CX, CY, R, shape)
        assert grown.boundingRect().top() == pytest.approx(plain.boundingRect().top(), abs=0.01)
        assert grown.length() == pytest.approx(plain.length(), rel=0.01)


# -- the trace ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("fraction", (0.1, 0.25, 0.5, 0.75, 1.0))
def test_the_trace_has_the_length_of_the_progress(shape, fraction):
    outline = shape_outline_path(CX, CY, R, shape, TRACE_OFFSET_PX)
    trace = trace_fraction(outline, fraction)
    assert trace.length() / outline.length() == pytest.approx(fraction, abs=0.01)


@pytest.mark.parametrize("shape", SHAPES)
def test_the_trace_starts_at_the_top_and_closes_at_full_progress(shape):
    outline = shape_outline_path(CX, CY, R, shape, TRACE_OFFSET_PX)
    start = trace_fraction(outline, 0.4).pointAtPercent(0.0)
    assert (start.x(), start.y()) == pytest.approx((CX, outline.boundingRect().top()), abs=0.5)
    full = trace_fraction(outline, 1.0)
    end = full.pointAtPercent(1.0)
    assert (end.x(), end.y()) == pytest.approx((start.x(), start.y()), abs=0.5)


def test_the_trace_runs_clockwise_from_twelve_round_a_circle():
    outline = shape_outline_path(CX, CY, R, SHAPE_CIRCLE, TRACE_OFFSET_PX)
    quarter = trace_fraction(outline, 0.25)
    end = quarter.pointAtPercent(1.0)  # three o'clock
    assert (end.x(), end.y()) == pytest.approx((CX + R + TRACE_OFFSET_PX, CY), abs=1.0)
    half = trace_fraction(outline, 0.5).pointAtPercent(1.0)  # six o'clock
    assert (half.x(), half.y()) == pytest.approx((CX, CY + R + TRACE_OFFSET_PX), abs=1.0)


def test_nothing_is_traced_at_no_progress_and_progress_is_clamped():
    outline = shape_outline_path(CX, CY, R, SHAPE_TRIANGLE, TRACE_OFFSET_PX)
    assert trace_fraction(outline, 0.0).isEmpty()
    assert trace_fraction(outline, -1.0).isEmpty()
    assert trace_fraction(outline, 7.0).length() == pytest.approx(trace_fraction(outline, 1.0).length())


def test_a_path_that_does_not_start_at_the_top_is_traced_from_its_top():
    """``shape_path``'s circle starts at three o'clock: the trace still starts at twelve."""
    plain = shape_path(CX, CY, R, SHAPE_CIRCLE)
    assert plain.pointAtPercent(0.0).x() > CX + R - 1
    start = trace_fraction(plain, 0.3).pointAtPercent(0.0)
    assert (start.x(), start.y()) == pytest.approx((CX, CY - R), abs=1.0)


def test_a_flat_topped_shape_is_traced_from_the_middle_of_its_top():
    """A hexagon's top is flat: starts at its middle, not at one of its corners."""
    outline = shape_outline_path(CX, CY, R, SHAPE_HEX, TRACE_OFFSET_PX)
    start = trace_fraction(outline, 0.3).pointAtPercent(0.0)
    assert start.x() == pytest.approx(CX, abs=0.5)
    # The same for a copy of the outline that starts elsewhere.
    elsewhere = QPainterPath()
    elsewhere.addPath(shape_path(CX, CY, R, SHAPE_HEX))
    start = trace_fraction(elsewhere, 0.3).pointAtPercent(0.0)
    assert start.y() == pytest.approx(elsewhere.boundingRect().top(), abs=0.5)
    assert start.x() == pytest.approx(CX, abs=1.5)


# -- painted: pixels on a rendered canvas --------------------------------------------------------------

_BG, _RING, _TARGET = "#000000", "#00ff00", "#ff0000"
_THEME = {"background": _BG, "cursor_color": _RING, "target_default": _TARGET}
_W, _H = 700, 600
_ICON_R = R * 0.78  # the icon is drawn at ICON_DRAW_FRAC of the hit radius


def _render(shape: int, *, progress=1.0, on_target=True):
    canvas = TaskCanvas(theme=_THEME)
    canvas.resize(_W, _H)
    canvas.show_cursor = False
    canvas.set_frame(
        (0.5, 0.5), R, (0.1, 0.1), True, progress, selectable=True, on_target=on_target,
        scene={"mode": "icons", "slots": [(0.5, 0.5)], "shapes": [shape]}, active_slot=0,
    )
    return canvas.grab().toImage()


def _colour_at(image, dx: float, dy: float) -> QColor:
    return image.pixelColor(round(_W / 2 + dx), round(_H / 2 + dy))


def _is(colour: QColor, hex_colour: str, tol=60) -> bool:
    want = QColor(hex_colour)
    return all(abs(a - b) <= tol for a, b in ((colour.red(), want.red()), (colour.green(), want.green()), (colour.blue(), want.blue())))


def test_the_rings_hug_a_triangle_instead_of_a_circle_round_it(qapp):
    """The triangle's bottom edge is at y = 0.7 r_icon; the dwell trace runs 16 px below it. The old
    circle ring (r_icon + 16 from the centre) would be 0.3 r_icon + 16 lower, so the pixel there is bare."""
    image = _render(SHAPE_TRIANGLE)
    bottom = 0.7 * _ICON_R
    assert _is(_colour_at(image, 0, bottom + TRACE_OFFSET_PX), _RING)
    assert _is(_colour_at(image, 0, bottom + INSTANT_OFFSET_PX), _RING)
    assert _is(_colour_at(image, 0, bottom + SELECTABLE_OFFSET_PX), "#ffffff")
    circle_ring_y = _ICON_R + TRACE_OFFSET_PX
    assert _is(_colour_at(image, 0, circle_ring_y), _BG, tol=20)


def test_the_dwell_trace_has_the_progress_of_the_ring_round_a_triangle(qapp):
    """Half progress: the trace covers the right edge (clockwise from the top) and not the left. Looked
    for 18 px out from each edge (normal to it), past the on-target ring, which is the same colour and
    all the way round."""
    image = _render(SHAPE_TRIANGLE, progress=0.5)
    edge_x = 0.92 * _ICON_R / 1.7  # where the triangle's sloping edges cross the middle row
    slope = 1.7 / math.hypot(0.92, 1.7)  # horizontal share of the edge's normal
    x = edge_x + (TRACE_OFFSET_PX + 2.0) / slope
    assert _is(_colour_at(image, x, 0.0), _RING)
    assert not _is(_colour_at(image, -x, 0.0), _RING, tol=20)


def test_a_circle_target_is_ringed_by_circles_as_before(qapp):
    image = _render(SHAPE_CIRCLE)
    for angle in (10, 80, 170, 200, 300):  # the dwell ring is full: all the way round
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        for offset, expected in (
            (SELECTABLE_OFFSET_PX, "#ffffff"), (INSTANT_OFFSET_PX, _RING), (TRACE_OFFSET_PX, _RING),
        ):
            assert _is(_colour_at(image, (_ICON_R + offset) * dx, (_ICON_R + offset) * dy), expected), (angle, offset)
        # ... and nothing beyond the dwell ring's outer edge (offset + half its pen).
        beyond = _ICON_R + TRACE_OFFSET_PX + TRACE_PEN_PX / 2 + 3
        assert _is(_colour_at(image, beyond * dx, beyond * dy), _BG, tol=20)


def test_the_pen_widths_are_4_5_and_8():
    assert (SELECTABLE_PEN_PX, INSTANT_PEN_PX, TRACE_PEN_PX) == (4.0, 5.0, 8.0)
    assert OFFSETS == (4.0, 10.0, 16.0)


@pytest.mark.parametrize("shape", [SHAPE_STAR, SHAPE_SQUARE])
def test_every_shape_is_ringed_along_its_own_outline(qapp, shape):
    image = _render(shape)
    outline = shape_outline_path(_W / 2, _H / 2, _ICON_R, shape, TRACE_OFFSET_PX)
    for x, y in _points(outline, 60):
        assert _is(image.pixelColor(round(x), round(y)), _RING), (x, y)
    assert not _is(image.pixelColor(round(_W / 2 + _ICON_R + TRACE_OFFSET_PX + TRACE_PEN_PX), round(_H / 2)), _RING)


def test_the_hit_area_is_still_a_circle():
    """Only the drawing follows the shape: scanning's hit test is untouched."""
    task = build_task("scanning", load_task_config("scanning"))
    target = task.targets[0]
    cx, cy = target.x_norm * task.screen_w, target.y_norm * task.screen_h
    reach = task.effective_radius_px(target) + task.jitter_px
    assert task.hit_test(target, cx, cy, cx + reach - 1, cy)
    assert not task.hit_test(target, cx, cy, cx + reach + 1, cy)
