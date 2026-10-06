"""SPEC-compass-task-flow.md 4D.5 geometry and 4D.10 G3: the one place gaze (monitor
frame), targets (canvas frame) and the target radius (logical px) are converted."""

from __future__ import annotations

import math

import pytest

from src.data.report_geometry import Geometry
from src.engine.target_size import SIZE_PRESETS_DEG, radius_px_for

# The reference rig: 1920x1080 at 100 %, 527x296 mm, 650 mm away; the canvas is the
# window under a 75 px strip, offset (0, 75), 1640x957 -- the EYEGEOM sessions.
RIG = {
    "screen_width_px": 1920,
    "screen_height_px": 1080,
    "screen_physical_width_mm": 527.0,
    "screen_physical_height_mm": 296.0,
    "viewing_distance_mm": 650.0,
    "canvas_width_px": 1640,
    "canvas_height_px": 957,
    "canvas_offset_x_px": 0,
    "canvas_offset_y_px": 75,
    "canvas_units": "physical",
    "display_scale_percent": 100,
    "target_size": {"mm_per_px": 527.0 / 1920},
}


def test_monitor_to_canvas_applies_the_canvas_offset_and_size():
    g = Geometry.from_metadata(RIG)
    x, y = g.monitor_to_canvas_norm(0.5, 0.5)
    assert x == pytest.approx(960 / 1640)
    assert y == pytest.approx((540 - 75) / 957)
    # The canvas's own corners map to 0 and 1.
    assert g.monitor_to_canvas_norm(0.0, 75 / 1080) == pytest.approx((0.0, 0.0))
    assert g.monitor_to_canvas_norm(1640 / 1920, 1032 / 1080) == pytest.approx((1.0, 1.0))


def test_a_point_off_the_canvas_keeps_its_out_of_range_value():
    g = Geometry.from_metadata(RIG)
    x, y = g.monitor_to_canvas_norm(0.99, 0.02)
    assert x > 1.0 and y < 0.0


def test_monitor_canvas_round_trip():
    g = Geometry.from_metadata(RIG)
    for point in [(0.1, 0.9), (0.5, 0.5), (1.1, -0.05)]:
        back = g.canvas_to_monitor_norm(*g.monitor_to_canvas_norm(*point))
        assert back == pytest.approx(point)


def test_physical_and_logical_units_give_the_same_norm():
    # A 150 % display: every length is 1.5x smaller in logical px, the ratio is not.
    logical = dict(RIG)
    logical.update(
        screen_width_px=1280,
        screen_height_px=720,
        canvas_width_px=1640 / 1.5,
        canvas_height_px=957 / 1.5,
        canvas_offset_y_px=50,
        canvas_units=None,
    )
    a = Geometry.from_metadata(RIG).monitor_to_canvas_norm(0.3, 0.7)
    b = Geometry.from_metadata(logical).monitor_to_canvas_norm(0.3, 0.7)
    assert a == pytest.approx(b)


def test_px_per_deg_on_the_reference_rig():
    assert Geometry.from_metadata(RIG).px_per_deg == pytest.approx(41.34, abs=0.01)


def test_angle_between_two_points_is_per_axis_in_mm():
    g = Geometry.from_metadata(RIG)
    # A 5 degree chord along x: 2 * D * tan(2.5 deg) mm over the screen width.
    chord_mm = 2 * 650 * math.tan(math.radians(2.5))
    assert g.angle_deg((0.2, 0.5), (0.2 + chord_mm / 527.0, 0.5)) == pytest.approx(5.0)
    assert g.angle_deg((0.3, 0.3), (0.3, 0.3)) == 0.0
    # Canvas-normalized points go through the frame conversion first.
    c = g.canvas_angle_deg((0.0, 0.5), (1640 / 1920 * 0 + 0.0, 0.5))
    assert c == 0.0
    full = g.canvas_angle_deg((0.0, 0.5), (1.0, 0.5))
    assert full == pytest.approx(g.angle_deg((0.0, 0.5), (1640 / 1920, 0.5)))


@pytest.mark.parametrize("preset", sorted(SIZE_PRESETS_DEG))
def test_radius_to_diameter_is_the_inverse_of_radius_px_for(preset):
    g = Geometry.from_metadata(RIG)
    radius = radius_px_for(preset, 527.0 / 1920, 650.0)
    assert g.radius_to_diameter_deg(radius) == pytest.approx(SIZE_PRESETS_DEG[preset])


def test_the_five_degree_preset_round_trips_at_150_percent_scale():
    # mm per *logical* px is 1.5x larger at 150 %; the radius in logical px is smaller.
    meta = dict(RIG, display_scale_percent=150, target_size={"mm_per_px": 527.0 / 1280})
    radius = radius_px_for("medium", 527.0 / 1280, 650.0)
    assert Geometry.from_metadata(meta).radius_to_diameter_deg(radius) == pytest.approx(5.0)


def test_canvas_logical_size_undoes_the_display_scale_only_for_physical_units():
    physical = Geometry.from_metadata(dict(RIG, display_scale_percent=150))
    w, h = physical.canvas_logical_size()
    assert (w, h) == pytest.approx((1640 / 1.5, 957 / 1.5))
    legacy = Geometry.from_metadata(dict(RIG, canvas_units=None, display_scale_percent=150))
    assert legacy.canvas_logical_size() == (1640, 957)


def test_aspect_is_the_canvas_aspect():
    assert Geometry.from_metadata(RIG).aspect == pytest.approx(1640 / 957)


def test_a_folder_without_geometry_gives_none_not_a_guess():
    g = Geometry.from_metadata({"screen_width_px": 1920, "screen_height_px": 1080})
    assert not g.has_angles
    assert g.angle_deg((0, 0), (1, 1)) is None
    assert g.px_per_deg is None and g.px_to_deg(21.0) is None
    assert g.radius_to_diameter_deg(100.0) is None  # no target_size block either
    assert g.canvas_logical_size() is None and g.aspect is None
    # No canvas: the canvas is taken to be the monitor.
    assert g.monitor_to_canvas_norm(0.25, 0.75) == (0.25, 0.75)


def test_for_visuals_borrows_the_reference_rig_and_says_so():
    g = Geometry.from_metadata({"screen_width_px": 1920})
    v = g.for_visuals()
    assert v.assumed and v.has_angles
    assert v.px_per_deg == pytest.approx(41.34, abs=0.01)
    full = Geometry.from_metadata(RIG)
    assert full.for_visuals() is full and not full.assumed


def test_calibration_error_px_to_degrees():
    g = Geometry.from_metadata(RIG)
    # 21 px is 0.5 deg on this rig (SPEC 4D.5 heat-map note).
    assert g.px_to_deg(21.31) == pytest.approx(0.52, abs=0.01)


def test_garbage_metadata_values_do_not_raise():
    g = Geometry.from_metadata(
        {"screen_width_px": "x", "canvas_offset_x_px": "y", "canvas_width_px": -3,
         "target_size": {"mm_per_px": "n/a"}}
    )
    assert g.screen_w_px is None and g.canvas_w_px is None and g.mm_per_px is None
    assert g.offset_x_px == 0.0
    assert g.as_dict()["px_per_deg"] is None
