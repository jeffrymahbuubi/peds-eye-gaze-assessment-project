"""SPEC-scene-cause-effect-task.md 3.7, P4 and P5 (offscreen Qt): the dwell progress of a scene button
is an 8 px ACCENT line along the button's own rounded border, clockwise from top-centre, in
proportion to the progress (P4); the instant on-target outline moves inside the button the same way
(P5). Nothing drawn for the looked-at button may leave the button's rectangle.

Pixels are read back from a ``QImage`` the button is drawn on. The glow halo is not part of this
(it is drawn outside on purpose, W3), so every look here has ``show_glow`` off. The button's own
border is a 3 px line centred on its edge, so a baseline (the same button, not looked at) is what
"outside" is compared with."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.ui.design_tokens import ACCENT
from src.ui.scene_buttons import (
    INSTANT_PEN_PX,
    TRACE_PEN_PX,
    ButtonLook,
    border_trace_path,
    draw_button,
    inset_border,
)

BACKGROUND = "#e8f5e9"
CURSOR = "#1b5e20"  # the theme's cursor colour: the instant outline's
THEME = {"background": BACKGROUND, "cursor_color": CURSOR, "particle_color": "#66bb6a"}
SIZES = [(250.0, 182.0), (274.0, 206.0), (180.0, 120.0)]  # Standard gap, a bigger and a small button
PAD = 40


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def rect_of(size, dx=0.0, dy=0.0) -> QRectF:
    return QRectF(PAD + dx, PAD + dy, size[0], size[1])


def look(**kw) -> ButtonLook:
    kw.setdefault("hover_slot", 0)
    kw.setdefault("show_glow", False)
    return ButtonLook(THEME, **kw)


def render(rect: QRectF, button_look: ButtonLook) -> QImage:
    image = QImage(int(rect.width() + 2 * PAD + 2), int(rect.height() + 2 * PAD + 2), QImage.Format.Format_ARGB32)
    image.fill(QColor(BACKGROUND))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_button(painter, 0, rect, "Cloud", "#bbdefb", None, button_look)
    painter.end()
    return image


def not_looked_at(rect: QRectF) -> QImage:
    return render(rect, look(hover_slot=-1))


def close(pixel: QColor, hex_colour: str, tol: int = 12) -> bool:
    want = QColor(hex_colour)
    return all(abs(a - b) <= tol for a, b in (
        (pixel.red(), want.red()), (pixel.green(), want.green()), (pixel.blue(), want.blue())))


def count(image: QImage, hex_colour: str, region: QRectF | None = None) -> int:
    n = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if region is not None and not region.contains(x + 0.5, y + 0.5):
                continue
            if close(image.pixelColor(x, y), hex_colour):
                n += 1
    return n


def differing_outside(a: QImage, b: QImage, rect: QRectF) -> list[tuple[int, int]]:
    """Pixels that differ between ``a`` and ``b`` and lie outside ``rect`` (any pixel the rectangle
    touches counts as inside, so a fractional edge is not held against the drawing)."""
    inside = rect.toAlignedRect()
    return [
        (x, y)
        for y in range(a.height())
        for x in range(a.width())
        if not inside.contains(x, y) and a.pixel(x, y) != b.pixel(x, y)
    ]


# -- the path: clockwise from top-centre, in proportion ------------------------------------------------------------


def perimeter(rect: QRectF, radius: float) -> float:
    return 2 * (rect.width() - 2 * radius) + 2 * (rect.height() - 2 * radius) + 2 * 3.141592653589793 * radius


def test_no_progress_is_an_empty_path(qapp):
    rect = QRectF(0, 0, 200, 150)
    assert border_trace_path(rect, 15, 0.0).isEmpty()
    assert border_trace_path(rect, 15, -0.3).isEmpty()
    assert border_trace_path(QRectF(0, 0, 0, 10), 5, 0.5).isEmpty()


def test_the_path_starts_at_top_centre_and_runs_clockwise(qapp):
    rect = QRectF(20, 30, 242, 174)
    cx = rect.center().x()
    r = 17.0
    for fraction in (0.02, 0.05, 0.1):  # (the top edge is about 13 % of the border)
        path = border_trace_path(rect, r, fraction)
        assert path.elementAt(0).x == pytest.approx(cx) and path.elementAt(0).y == pytest.approx(rect.top())
        end = path.currentPosition()  # clockwise: first to the right along the top edge
        assert end.x() > cx and end.y() == pytest.approx(rect.top())
    # Past the right side and the bottom the path comes back along the top from the left ...
    for fraction in (0.9, 0.95, 0.98):
        end = border_trace_path(rect, r, fraction).currentPosition()
        assert end.x() < cx and end.y() == pytest.approx(rect.top())
    # ... a quarter of the way it is on the right edge, three quarters on the left edge.
    quarter = border_trace_path(rect, r, 0.3).currentPosition()
    assert quarter.x() == pytest.approx(rect.right()) and rect.top() < quarter.y() < rect.bottom()
    three = border_trace_path(rect, r, 0.7).currentPosition()
    assert three.x() == pytest.approx(rect.left()) and rect.top() < three.y() < rect.bottom()


def test_the_full_trace_is_back_at_top_centre(qapp):
    rect = QRectF(5, 5, 250, 182)
    end = border_trace_path(rect, 18, 1.0).currentPosition()
    assert end.x() == pytest.approx(rect.center().x(), abs=1e-6) and end.y() == pytest.approx(rect.top())
    assert border_trace_path(rect, 18, 7.0).currentPosition() == end  # capped at the full border


@pytest.mark.parametrize("radius", [0.0, 6.0, 18.0, 60.0])
def test_the_length_grows_in_proportion_to_the_progress(qapp, radius):
    rect = QRectF(0, 0, 250, 182)
    total = perimeter(rect, min(radius, 91.0))
    lengths = [border_trace_path(rect, radius, p).length() for p in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert lengths[0] == 0.0 and lengths == sorted(lengths) and len(set(lengths)) == 5
    for fraction, length in zip((0.25, 0.5, 0.75, 1.0), lengths[1:], strict=True):
        assert length == pytest.approx(fraction * total, rel=0.01)


def test_the_path_never_leaves_its_rectangle(qapp):
    rect = QRectF(10.3, 12.7, 250.4, 182.2)
    for step in range(1, 41):
        bounds = border_trace_path(rect, 18.2, step / 40).boundingRect()
        assert bounds.left() >= rect.left() - 1e-6 and bounds.right() <= rect.right() + 1e-6
        assert bounds.top() >= rect.top() - 1e-6 and bounds.bottom() <= rect.bottom() + 1e-6


def test_the_inset_is_half_the_pen_with_concentric_corners():
    rect = QRectF(10, 20, 250, 182)
    inner, radius = inset_border(rect, 18.2, 8.0)
    assert (inner.left(), inner.top(), inner.right(), inner.bottom()) == (14.0, 24.0, 256.0, 198.0)
    assert radius == pytest.approx(14.2)
    inner, radius = inset_border(rect, 3.0, 8.0)
    assert radius == 0.0  # never negative
    assert TRACE_PEN_PX == 8.0 and INSTANT_PEN_PX == 5.0


# -- the drawing: the trace stays inside the button -----------------------------------------------------------------


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (0.37, 0.61)])  # whole and fractional edges
def test_the_dwell_trace_never_leaves_the_button(qapp, size, dx, dy):
    rect = rect_of(size, dx, dy)
    plain = not_looked_at(rect)
    for progress in (0.05, 0.25, 0.5, 0.75, 1.0):
        image = render(rect, look(show_ring=True, progress=progress))
        assert image != plain  # something is drawn ...
        assert differing_outside(image, plain, rect) == []  # ... and none of it outside the button


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (0.37, 0.61)])
def test_the_instant_outline_never_leaves_the_button(qapp, size, dx, dy):
    rect = rect_of(size, dx, dy)
    plain = not_looked_at(rect)
    image = render(rect, look(show_instant=True))
    assert image != plain and count(image, CURSOR) > 100
    assert differing_outside(image, plain, rect) == []
    # The outline itself is cursor-coloured and no cursor-coloured pixel is outside the button.
    outside = QRectF(0, 0, image.width(), image.height())
    assert count(image, CURSOR, outside) == count(image, CURSOR, rect.adjusted(-1, -1, 1, 1))


def test_the_instant_outline_and_the_trace_together_stay_inside(qapp):
    rect = rect_of(SIZES[0])
    plain = not_looked_at(rect)
    image = render(rect, look(show_instant=True, show_ring=True, progress=0.6))
    assert differing_outside(image, plain, rect) == []


def test_the_instant_outline_replaces_the_old_ring_five_px_outside_the_button(qapp):
    rect = rect_of(SIZES[0])
    cx = rect.center().x()
    plain, instant = not_looked_at(rect), render(rect, look(show_instant=True))
    just_outside = QPointF(cx, rect.top() - 3.0)  # where the old outline (grown by 5 px) was drawn
    just_inside = QPointF(cx, rect.top() + 2.5)
    assert instant.pixelColor(int(just_outside.x()), int(just_outside.y())) == plain.pixelColor(
        int(just_outside.x()), int(just_outside.y())
    )
    assert close(instant.pixelColor(int(just_inside.x()), int(just_inside.y())), CURSOR)


def test_the_trace_is_accent_and_runs_clockwise_on_the_real_pixels(qapp):
    rect = rect_of(SIZES[0])
    cx, top = rect.center().x(), rect.top()
    early = render(rect, look(show_ring=True, progress=0.1))
    sample_right, sample_left = (int(cx + 40), int(top + 4)), (int(cx - 40), int(top + 4))
    assert close(early.pixelColor(*sample_right), ACCENT)  # right of top-centre first
    assert not close(early.pixelColor(*sample_left), ACCENT)
    late = render(rect, look(show_ring=True, progress=0.95))
    assert close(late.pixelColor(*sample_right), ACCENT) and close(late.pixelColor(*sample_left), ACCENT)
    # Early on it is not on the bottom or the left edge yet.
    assert not close(early.pixelColor(int(rect.left() + 4), int(rect.center().y())), ACCENT)
    assert not close(early.pixelColor(int(cx), int(rect.bottom() - 4)), ACCENT)


def test_more_progress_draws_a_longer_line(qapp):
    rect = rect_of(SIZES[0])
    counts = {p: count(render(rect, look(show_ring=True, progress=p)), ACCENT) for p in (0.0, 0.25, 0.5, 0.75, 1.0)}
    assert counts[0.0] == 0
    assert 0 < counts[0.25] < counts[0.5] < counts[0.75] < counts[1.0]
    for p in (0.25, 0.5, 0.75):  # in proportion (the round caps add a little at both ends)
        assert counts[p] / counts[1.0] == pytest.approx(p, abs=0.06)


def test_the_trace_is_eight_px_thick_and_keeps_the_picture_and_label_clear(qapp):
    rect = rect_of(SIZES[0])
    image = render(rect, look(show_ring=True, progress=1.0))
    cx = int(rect.center().x())
    # Straight down from the top edge at top-centre: accent for the 8 px of the pen, then not.
    column = [close(image.pixelColor(cx, int(rect.top()) + dy), ACCENT) for dy in range(0, 14)]
    assert column[:8] == [True] * 8 and not any(column[10:])
    # Nothing over the picture (the art area of draw_button) or over the label's text.
    picture = rect.adjusted(0.15 * rect.width(), 0.08 * rect.height(), -0.15 * rect.width(), -0.30 * rect.height())
    label = QRectF(rect.left() + 0.1 * rect.width(), rect.top() + 0.72 * rect.height(), 0.8 * rect.width(), 0.22 * rect.height())
    assert count(image, ACCENT, picture) == 0 and count(image, ACCENT, label) == 0


def test_the_ring_follows_the_same_inputs_as_before(qapp):
    rect = rect_of(SIZES[0])
    plain = not_looked_at(rect)
    assert render(rect, look(show_ring=True, progress=0.0)) == render(rect, look())  # no progress, no line
    assert render(rect, look(show_ring=False, progress=0.8)) == render(rect, look())  # ring setting off
    assert render(rect, look(show_ring=True, progress=0.8, hover_slot=3)) == plain  # another button's
    assert render(rect, look(show_ring=True, progress=0.8, selectable=False)) == plain  # prompt blocks
    assert render(rect, look(show_ring=True, progress=2.5)) == render(rect, look(show_ring=True, progress=1.0))


def test_the_glow_is_left_as_it_was_and_still_reaches_outside(qapp):
    rect = rect_of(SIZES[0])
    plain = not_looked_at(rect)
    glowing = render(rect, look(show_glow=True))
    assert differing_outside(glowing, plain, rect) != []  # the halo is drawn outside, on purpose (W3)
