"""SPEC-gaze-stability-and-positioning.md 4.5-4.7, acceptance A8 (the offscreen paint test): the
head-position picture and its panel. Colours are read back from the painted pixels and must be
the design tokens' own; the face is found by its colour, so nothing here depends on a font.
Offscreen Qt."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.inputs import head_position as hp
from src.inputs.head_position import EyePosition, HeadReading, HeadState
from src.ui import design_tokens as tokens
from src.ui.head_position_panel import POLL_INTERVAL_MS, HeadPositionPanel
from src.ui.head_position_widget import WIDGET_WIDTH, HeadPositionWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def reading(state=HeadState.GREEN, *, u=0.5, v=0.5, scale=1.0, roll=0.0, z=65.0) -> HeadReading:
    return HeadReading(
        state, "x", z_cm=z, centre_x_cm=0.0, centre_y_cm=0.0,
        face_u=u, face_v=v, face_scale=scale, roll_deg=roll,
    )


def painted(qapp, read: HeadReading):
    """The widget showing ``read``, and its pixels."""
    widget = HeadPositionWidget()
    widget.set_reading(read)
    return widget, widget.grab().toImage()


def pixels(image, colour: str, *, region=None):
    """The ``(x, y)`` of every pixel exactly equal to ``colour`` (a token), within ``region``
    (a QRectF) when given."""
    rgb = QColor(colour).rgb() & 0xFFFFFF
    found = []
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixel(x, y) & 0xFFFFFF == rgb and (region is None or region.contains(x + 0.5, y + 0.5)):
                found.append((x, y))
    return found


def bar_region(widget):
    box = widget.box_rect()
    return QRectF(0, box.bottom(), widget.width(), widget.height() - box.bottom())


def centroid(points):
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


# -- colours are the tokens (4.6) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "state, token",
    [
        (HeadState.GREEN, tokens.SUCCESS),
        (HeadState.ORANGE, tokens.WARNING),
        (HeadState.RED, tokens.DANGER),
    ],
)
def test_the_face_is_drawn_in_the_state_token_and_no_other_state_colour(qapp, state, token):
    widget, image = painted(qapp, reading(state))
    box = widget.box_rect()
    face = pixels(image, token, region=box)
    assert len(face) > 500
    others = {tokens.SUCCESS, tokens.WARNING, tokens.DANGER} - {token}
    assert all(not pixels(image, other, region=box) for other in others)


@pytest.mark.parametrize("empty", [hp.NO_EYES, hp.NOT_CONNECTED])
def test_with_no_eyes_or_no_tracker_the_box_is_empty_and_has_no_dot(qapp, empty):
    widget, image = painted(qapp, empty)
    state_colours = (tokens.SUCCESS, tokens.WARNING, tokens.DANGER)
    assert all(not pixels(image, colour, region=widget.box_rect()) for colour in state_colours)
    # In the bar the green band is there, and no dot of any colour.
    assert not pixels(image, tokens.WARNING) and not pixels(image, tokens.DANGER)
    assert pixels(image, tokens.SUCCESS, region=bar_region(widget))  # the band, always


def test_the_box_is_a_grey_with_its_inner_zone_lighter(qapp):
    widget, image = painted(qapp, hp.NOT_CONNECTED)
    box = widget.box_rect()
    outer = image.pixelColor(int(box.left()) + 6, int(box.center().y()))
    inner = image.pixelColor(int(box.center().x()), int(box.center().y()))
    assert outer.rgb() == QColor(tokens.HEADER).rgb()
    assert inner.rgb() == QColor(tokens.PAGE).rgb()


def test_no_literal_colour_in_the_widget_or_panel_sources():
    root = Path(__file__).resolve().parents[1] / "src" / "ui"
    for name in ("head_position_widget.py", "head_position_panel.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert not re.findall(r"#[0-9A-Fa-f]{3,8}\b", text), name


# -- the face moves, grows and tilts (4.5) -------------------------------------------------------------


def test_the_face_is_drawn_where_the_reading_puts_it(qapp):
    for u, v in ((0.5, 0.5), (0.7, 0.4), (0.3, 0.62)):
        widget, image = painted(qapp, reading(u=u, v=v))
        found = pixels(image, tokens.SUCCESS, region=widget.box_rect())
        cx, cy = centroid(found)
        expected = widget.face_centre()
        assert (cx, cy) == pytest.approx((expected.x(), expected.y()), abs=2.0)


def test_moving_the_head_moves_the_face_the_same_way(qapp):
    _, centre = painted(qapp, reading(u=0.5, v=0.5))
    widget, right_low = painted(qapp, reading(u=0.65, v=0.6))
    box = widget.box_rect()
    cx0, cy0 = centroid(pixels(centre, tokens.SUCCESS, region=box))
    cx1, cy1 = centroid(pixels(right_low, tokens.SUCCESS, region=box))
    assert cx1 > cx0 + 10 and cy1 > cy0 + 5


def test_a_head_outside_the_box_is_cut_off_by_it(qapp):
    widget, image = painted(qapp, reading(HeadState.RED, u=0.5, v=1.05))
    box = widget.box_rect()
    assert pixels(image, tokens.DANGER, region=box)  # part of the face is inside
    # Nothing of it is painted in the gap between the box and the bar (the dot is further down).
    gap = QRectF(0, box.bottom() + 1.0, widget.width(), 6.0)
    assert not pixels(image, tokens.DANGER, region=gap)


def test_the_face_grows_with_the_scale(qapp):
    widget, small = painted(qapp, reading(scale=0.8))
    _, normal = painted(qapp, reading(scale=1.0))
    _, large = painted(qapp, reading(scale=1.4))
    count = [len(pixels(img, tokens.SUCCESS, region=widget.box_rect())) for img in (small, normal, large)]
    assert count[0] < count[1] < count[2]
    assert count[1] / count[0] == pytest.approx((1.0 / 0.8) ** 2, rel=0.1)


def extent(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def eye_pixel(widget, image, side: int, roll_deg: float) -> int:
    """The colour (rgb) of the pixel where the face's eye ``side`` (-1 left, +1 right) should
    be at ``roll_deg``: the eyes sit at (+-0.36, -0.2) face radii from the centre."""
    radius = widget.box_rect().height() * 0.25
    centre, theta = widget.face_centre(), math.radians(roll_deg)
    x, y = side * 0.36, -0.2
    px = centre.x() + radius * (x * math.cos(theta) - y * math.sin(theta))
    py = centre.y() + radius * (x * math.sin(theta) + y * math.cos(theta))
    return image.pixel(round(px), round(py)) & 0xFFFFFF


def test_the_face_tilts_with_the_roll(qapp):
    widget, upright = painted(qapp, reading(roll=0.0))
    _, sideways = painted(qapp, reading(roll=90.0))
    _, slanted = painted(qapp, reading(roll=30.0))
    box = widget.box_rect()
    width, height = extent(pixels(upright, tokens.SUCCESS, region=box))
    assert height > width  # an egg, taller than wide
    width90, height90 = extent(pixels(sideways, tokens.SUCCESS, region=box))
    assert width90 > height90  # a quarter turn lays it on its side
    assert (width90, height90) == pytest.approx((height, width), abs=3.0)
    # The eyes are where the roll puts them: a positive roll is clockwise on screen.
    white, face = QColor(tokens.PANEL).rgb() & 0xFFFFFF, QColor(tokens.SUCCESS).rgb() & 0xFFFFFF
    for side in (-1, 1):
        assert eye_pixel(widget, upright, side, 0.0) == white
        assert eye_pixel(widget, slanted, side, 30.0) == white
        assert eye_pixel(widget, slanted, side, 0.0) == face  # not where an upright face has it


def mouth_shape(widget, image) -> float:
    """How far the middle of the mouth sits below its ends, in px: + a smile, - a frown, 0 flat."""
    box, centre = widget.box_rect(), widget.face_centre()
    radius = box.height() * 0.25
    mouth = [
        p for p in pixels(image, tokens.PANEL, region=box)
        if p[1] > centre.y() + 0.25 * radius and abs(p[0] - centre.x()) < 0.5 * radius
    ]
    assert mouth
    middle = [p[1] for p in mouth if abs(p[0] - centre.x()) < 0.1 * radius]
    ends = [p[1] for p in mouth if abs(p[0] - centre.x()) > 0.3 * radius]
    return sum(middle) / len(middle) - sum(ends) / len(ends)


def test_green_smiles_orange_is_flat_and_red_frowns(qapp):
    shapes = {}
    for state in (HeadState.GREEN, HeadState.ORANGE, HeadState.RED):
        widget, image = painted(qapp, reading(state))
        shapes[state] = mouth_shape(widget, image)
    assert shapes[HeadState.GREEN] > 3.0
    assert abs(shapes[HeadState.ORANGE]) < 1.5
    assert shapes[HeadState.RED] < -3.0


# -- the Close-Far bar ----------------------------------------------------------------------------------


def dot_x(qapp, z_cm: float) -> float:
    widget, image = painted(qapp, reading(HeadState.ORANGE, z=z_cm))
    return centroid(pixels(image, tokens.WARNING, region=bar_region(widget)))[0]


def test_the_dot_sits_on_a_45_to_85_cm_scale(qapp):
    left, mid, right = dot_x(qapp, 45.0), dot_x(qapp, 65.0), dot_x(qapp, 85.0)
    assert left < mid < right
    assert mid == pytest.approx((left + right) / 2.0, abs=1.5)
    assert dot_x(qapp, 55.0) == pytest.approx(left + (right - left) * 0.25, abs=1.5)
    # Beyond the scale the dot stays at its end.
    assert dot_x(qapp, 30.0) == pytest.approx(left, abs=0.5)
    assert dot_x(qapp, 120.0) == pytest.approx(right, abs=0.5)


def test_the_55_to_75_cm_band_is_shaded_green_a_quarter_to_three_quarters_along(qapp):
    widget, image = painted(qapp, hp.NO_EYES)
    bar = bar_region(widget)
    groove = pixels(image, tokens.SLIDER_GROOVE, region=bar)
    band = pixels(image, tokens.SUCCESS, region=bar)
    left, right = min(p[0] for p in groove), max(p[0] for p in groove)
    assert (min(p[0] for p in band) - left) / (right - left) == pytest.approx(0.25, abs=0.03)
    assert (max(p[0] for p in band) - left) / (right - left) == pytest.approx(0.75, abs=0.03)


def test_a_dot_needs_a_face_and_a_distance(qapp):
    widget, image = painted(qapp, HeadReading(HeadState.ORANGE, "x"))  # no distance known
    assert not pixels(image, tokens.WARNING, region=bar_region(widget))


def test_the_widget_has_a_fixed_width_and_says_its_state_to_assistive_tools(qapp):
    widget = HeadPositionWidget()
    assert widget.width() == WIDGET_WIDTH == 240
    assert widget.accessibleName() == "Head position"
    assert widget.accessibleDescription() == "Tracker not connected"
    widget.set_reading(hp.assess(EyePosition((-0.03, 0.0, 0.52), (0.03, 0.0, 0.52), 0.0), 0.0))
    assert widget.accessibleDescription() == "Move back, 52 cm"


# -- the panel: the timer, the source and the status line (4.7) ------------------------------------


class Source:
    """A stand-in for ``SetupPage.head_position_input`` and the clock the panel reads."""

    def __init__(self):
        self.connected = True
        self.eyes: EyePosition | None = None
        self.now = 0.0
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.connected, self.eyes

    def clock(self) -> float:
        return self.now

    def see(self, dx_cm=0.0, z_cm=65.0, *, left=True, right=True):
        cx, z = (hp.CENTRED_X_CM + dx_cm) / 100.0, z_cm / 100.0
        y = hp.CENTRED_Y_CM / 100.0
        self.eyes = EyePosition(
            (cx - 0.03, y, z) if left else None, (cx + 0.03, y, z) if right else None, self.now
        )


def make_panel(source=None):
    source = source if source is not None else Source()
    return HeadPositionPanel(source=source, clock=source.clock), source


def test_a_panel_with_no_source_says_the_tracker_is_not_connected(qapp):
    panel = HeadPositionPanel()
    assert panel.reading() is hp.NOT_CONNECTED
    assert panel.status_badge.text() == "Tracker not connected"
    assert panel.picture.reading() is hp.NOT_CONNECTED
    assert panel.title_label.text() == "Head position"
    assert panel.width() == WIDGET_WIDTH


@pytest.mark.parametrize(
    "dx, z, left, right, kind, text",
    [
        (0.0, 65.0, True, True, "tracking_ok", "Good position, 65 cm"),
        (0.0, 52.0, True, True, "data_missing", "Move back, 52 cm"),
        (0.0, 47.0, True, True, "disconnected", "Move back, 47 cm"),
        (0.0, 65.0, True, False, "data_missing", "Only one eye seen, 65 cm"),
    ],
)
def test_the_status_line_is_a_glyph_the_hint_and_the_distance(qapp, dx, z, left, right, kind, text):
    panel, source = make_panel()
    source.see(dx, z, left=left, right=right)
    panel.poll()
    assert (panel.status_badge.kind(), panel.status_badge.text()) == (kind, text)
    assert panel.picture.reading() is panel.reading()


def test_connected_with_nothing_seen_says_no_eyes_and_a_dropped_tracker_says_not_connected(qapp):
    panel, source = make_panel()
    panel.poll()  # connected, no REC yet
    assert panel.status_badge.text() == "No eyes detected"
    source.connected = False
    panel.poll()
    assert panel.status_badge.text() == "Tracker not connected"
    assert panel.status_badge.kind() == "not_done"  # no colour: there is nothing to judge


def test_the_panel_holds_a_new_colour_for_0_3_s_through_the_tracker_rules(qapp):
    panel, source = make_panel()
    source.see(z_cm=65.0)
    panel.poll()
    source.now = 0.1
    source.see(z_cm=54.0)
    panel.poll()
    assert panel.status_badge.kind() == "tracking_ok"  # not yet
    assert panel.status_badge.text() == "Good position, 54 cm"  # but the distance is live
    source.now = 0.45
    source.see(z_cm=54.0)
    panel.poll()
    assert panel.status_badge.text() == "Move back, 54 cm"


def test_the_timer_runs_at_about_15_hz_only_while_the_panel_is_shown(qapp):
    panel, source = make_panel()
    assert not panel._timer.isActive()
    assert panel._timer.interval() == POLL_INTERVAL_MS and 60 <= POLL_INTERVAL_MS <= 70  # ~15 Hz
    panel.show()
    assert panel._timer.isActive()
    before = source.calls
    panel._timer.timeout.emit()
    assert source.calls == before + 1
    panel.hide()
    assert not panel._timer.isActive()


def test_the_snapshot_reads_afresh_and_is_the_metadata_form(qapp):
    panel, source = make_panel()
    source.see(dx_cm=2.0, z_cm=64.0)
    snap = panel.snapshot()
    assert snap == {"state": "green", "z_cm": 64.0, "centre_x_cm": 2.0, "centre_y_cm": 0.0}
    source.connected = False
    assert panel.snapshot()["state"] == "not_connected"


def test_a_bound_method_source_is_held_weakly_and_a_gone_owner_reads_as_not_connected(qapp):
    class Owner:
        def head_position_input(self):
            return True, EyePosition((-0.03, 0.0, 0.65), (0.03, 0.0, 0.65), 0.0)

    owner = Owner()
    panel = HeadPositionPanel(source=owner.head_position_input, clock=lambda: 0.0)
    assert panel.reading().state in (HeadState.GREEN, HeadState.ORANGE)  # it was read
    del owner
    panel.poll()
    assert panel.reading() is hp.NOT_CONNECTED


def test_changing_the_source_shows_it_at_once(qapp):
    panel, source = make_panel()
    source.see()
    panel.poll()
    other = Source()
    other.connected = False
    panel.set_source(other)
    assert panel.status_badge.text() == "Tracker not connected"
    panel.set_source(None)
    assert panel.reading() is hp.NOT_CONNECTED
