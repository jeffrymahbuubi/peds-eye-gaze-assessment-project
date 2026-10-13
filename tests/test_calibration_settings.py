"""SPEC-app-drawn-calibration.md acceptance A5, A7 (the record), A10b (the size in degrees) and A12
(the old ``calibration.show`` value) as pure maths: the settings, the Grid 3 layout, the per-point
score and its colour band, and what ``calibration.json`` keeps.

No Qt and no device.
"""

from __future__ import annotations

import json
import math

import pytest

from src.data.report_geometry import Geometry
from src.engine import calibration_settings as cs
from src.engine.calibration import (
    CalibrationResult,
    load_calibration_result,
    save_calibration_result,
)
from src.engine.calibration_motion import ease, schedule
from src.engine.calibration_run import CalibrationRun, annotate
from src.engine.calibration_settings import MODE_APP, MODE_FALLBACK, record_for, with_improve_runs

# The lab rig: 24-inch 16:9 at 1920 x 1080, 650 mm away.
RIG = Geometry(screen_w_px=1920, screen_h_px=1080, phys_w_mm=527.0, phys_h_mm=296.0, distance_mm=650.0)


def px_for_degrees(degrees: float, geometry: Geometry = RIG) -> float:
    """The horizontal distance in monitor px that ``geometry.px_to_deg`` reads as ``degrees``."""
    chord_mm = 2.0 * geometry.distance_mm * math.tan(math.radians(degrees) / 2.0)
    return chord_mm * geometry.screen_w_px / geometry.phys_w_mm


def per_point(target, left_deg=None, right_deg=None, point=1, left_valid=True, right_valid=True):
    """A CALIB_RESULT point whose eyes are off the target horizontally by the given degrees."""
    x, y = target

    def eye(deg, valid):
        if deg is None:
            return None
        return {"x": x + px_for_degrees(deg) / RIG.screen_w_px, "y": y, "valid": valid}

    return {
        "point": point, "target_x": x, "target_y": y,
        "left": eye(left_deg, left_valid), "right": eye(right_deg, right_valid),
    }


# -- A5: the score and its band (Q1) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("error_deg", "score", "band"),
    [
        (0.0, 100, cs.BAND_GOOD),
        (0.5, 83, cs.BAND_GOOD),
        (1.0, 67, cs.BAND_GOOD),  # 1 deg or less is green
        (1.01, 66, cs.BAND_FAIR),
        (1.5, 50, cs.BAND_FAIR),
        (2.0, 33, cs.BAND_FAIR),  # up to 2 deg is amber
        (2.01, 33, cs.BAND_POOR),  # above 2 deg is red
        (3.0, 0, cs.BAND_POOR),
        (4.5, 0, cs.BAND_POOR),  # never below 0
        (None, 0, cs.BAND_NONE),  # no valid eye
    ],
)
def test_score_and_band_follow_q1(error_deg, score, band):
    assert cs.point_score(error_deg) == score
    assert cs.point_band(error_deg) == band


def test_known_per_eye_errors_give_the_expected_scores_and_colours():
    points = (
        per_point((0.1, 0.1), 0.4, 0.6, point=1),  # mean 0.5 deg: green
        per_point((0.9, 0.9), 1.4, 1.6, point=2),  # mean 1.5 deg: amber
        per_point((0.9, 0.1), 2.4, 2.6, point=3),  # mean 2.5 deg: red
        per_point((0.1, 0.9), 0.4, 3.6, point=4, right_valid=False),  # only the left eye counts: green
        per_point((0.5, 0.5), 0.2, 0.2, point=5, left_valid=False, right_valid=False),  # none valid
    )
    scores = cs.score_points(points, RIG)
    assert [s.point for s in scores] == [1, 2, 3, 4, 5]
    assert [s.band for s in scores] == [cs.BAND_GOOD, cs.BAND_FAIR, cs.BAND_POOR, cs.BAND_GOOD, cs.BAND_NONE]
    assert [s.score for s in scores] == [83, 50, 17, 87, 0]
    assert scores[0].error_deg == pytest.approx(0.5, abs=0.02)
    assert scores[3].error_deg == pytest.approx(0.4, abs=0.02)
    assert scores[4].error_deg is None
    assert [s.weak for s in scores] == [False, True, True, False, True]  # a thicker ring on these


def test_a_point_with_no_estimate_at_all_is_none_and_missing_data_gives_no_scores():
    scores = cs.score_points((per_point((0.5, 0.5)),), RIG)
    assert scores[0].band == cs.BAND_NONE and scores[0].error_deg is None
    assert cs.score_points(None, RIG) == [] and cs.score_points((), RIG) == []


def test_the_line_under_the_map_counts_the_points_that_need_attention():
    good = cs.score_points((per_point((0.5, 0.5), 0.2, 0.2),), RIG)
    assert cs.attention_text(good) == "All points are good."
    one = cs.score_points((per_point((0.5, 0.5), 0.2, 0.2), per_point((0.1, 0.1), 1.5, 1.5, point=2)), RIG)
    assert cs.attention_text(one) == "1 point needs attention. Check the head position, then Improve calibration."
    two = cs.score_points(
        (per_point((0.5, 0.5), 2.5, 2.5), per_point((0.1, 0.1), 1.5, 1.5, point=2), per_point((0.9, 0.9), 0.1, 0.1, point=3)),
        RIG,
    )
    assert cs.attention_text(two).startswith("2 points need attention.")


def test_the_scores_are_written_beside_each_point_for_calibration_json():
    points = (per_point((0.5, 0.5), 0.5, 0.5), per_point((0.1, 0.1), None, None, point=2))
    annotated = cs.annotate_per_point(points, cs.score_points(points, RIG))
    assert annotated[0]["score"] == 83 and annotated[0]["error_deg"] == pytest.approx(0.5, abs=0.01)
    assert annotated[1]["score"] == 0 and annotated[1]["error_deg"] is None
    assert annotated[0]["target_x"] == 0.5  # what was there stays
    assert cs.annotate_per_point(points, []) is points and cs.annotate_per_point(None, []) is None


# -- D5: the layout --------------------------------------------------------------------------------


def test_the_layout_is_grid3s_tl_br_tr_bl_c_at_10_and_90_percent():
    assert cs.app_layout(5) == [(0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9), (0.5, 0.5)]


def test_the_nine_point_layout_adds_the_edge_midpoints_after_the_five():
    nine = cs.app_layout(9)
    assert nine[:5] == cs.app_layout(5)
    assert set(nine[5:]) == {(0.5, 0.1), (0.9, 0.5), (0.5, 0.9), (0.1, 0.5)}
    assert len(set(nine)) == 9


def test_fewer_than_four_points_are_not_a_layout():
    for count in (0, 3, 10):
        with pytest.raises(ValueError):
            cs.app_layout(count)
    assert cs.POINT_CHOICES == (5, 9)


# -- A10b: the size in degrees ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "gliding", "holding"), [("small", 2.2, 0.6), ("normal", 3.0, 0.8), ("large", 4.0, 1.0)]
)
def test_the_size_presets_are_the_degrees_of_the_spec(size, gliding, holding):
    assert cs.SIZES_DEG[size] == (gliding, holding)
    mm_per_px = 527.0 / 1920
    for holding_now, degrees in ((False, gliding), (True, holding)):
        px = cs.icon_diameter_px(size, holding_now, mm_per_px, 650.0)
        assert px * mm_per_px == pytest.approx(2 * 650.0 * math.tan(math.radians(degrees) / 2), rel=1e-9)


def test_normal_is_about_6_percent_and_1_7_percent_of_the_width_on_the_lab_rig():
    """4.3b: close to Grid 3's measured ~5-6.5 % gliding and ~1.5-2 % holding."""
    mm_per_px = 527.0 / 1920
    gliding = cs.icon_diameter_px("normal", False, mm_per_px, 650.0) / 1920
    holding = cs.icon_diameter_px("normal", True, mm_per_px, 650.0) / 1920
    assert 0.055 <= gliding <= 0.07 and 0.015 <= holding <= 0.02


def test_the_apparent_size_is_the_same_on_a_monitor_with_other_pixels():
    big_pixels = cs.icon_diameter_px("normal", False, 0.5, 650.0)
    small_pixels = cs.icon_diameter_px("normal", False, 0.25, 650.0)
    assert big_pixels * 0.5 == pytest.approx(small_pixels * 0.25)


def test_the_geometry_for_a_scaled_screen_is_in_physical_px():
    geometry = cs.geometry_for_screen(1920, 1080, 0.375, 1.5, 650)  # 1280 x 720 logical px at 150 %
    assert (geometry.screen_w_px, geometry.screen_h_px) == (1920, 1080)
    assert geometry.phys_w_mm == pytest.approx(1920 * 0.375 / 1.5)  # mm per physical px is per logical / scale
    assert geometry.has_angles and geometry.px_to_deg(41.3) > 0


# -- A7: settings per PC, and the record -----------------------------------------------------------


def test_the_defaults_are_app_5_normal_the_first_icon_normal_size_white():
    s = cs.CalibrationSettings()
    assert s.as_dict() == {
        "screen": "app", "points": 5, "speed": "normal", "target": "bee", "size": "normal", "background": "white",
    }
    assert (s.delay_s, s.timeout_s) == (0.8, 1.0)
    assert cs.DEFAULT_TARGET == cs.ICON_IDS[0] == "bee"
    assert cs.ICON_IDS == ("bee", "star", "ball", "fish", "flower", "car")


def test_settings_round_trip_through_the_local_state():
    wanted = cs.CalibrationSettings("control", 9, "fast", "car", "large", "black")
    assert cs.load_settings(cs.settings_state(wanted)) == wanted


def test_an_unknown_or_missing_saved_value_falls_back_to_the_default():
    state = {"calibration": {"screen": "paper", "points": "x", "speed": 7, "target": "dog", "size": None}}
    assert cs.load_settings(state) == cs.CalibrationSettings()
    assert cs.load_settings({}) == cs.CalibrationSettings()
    assert cs.load_settings({"calibration": "nonsense"}) == cs.CalibrationSettings()


def test_points_outside_5_and_9_land_on_the_nearest_layout():
    assert [cs.CalibrationSettings.from_dict({"points": n}).points for n in (1, 5, 6, 7, 8, 9, 12)] == [5, 5, 5, 5, 9, 9, 9]


# -- A12: the old calibration.show value -----------------------------------------------------------


def test_the_shipped_show_true_is_the_app_screen_and_its_points_carry_over():
    assert cs.settings_from_config({"enabled": True, "points": 5, "show": True}).screen == "app"
    assert cs.settings_from_config({"points": 9, "show": True}).points == 9
    assert cs.settings_from_config(None) == cs.CalibrationSettings()


def test_show_false_is_the_app_default_too_because_no_picture_is_no_longer_offered():
    assert cs.settings_from_config({"show": False}).screen == "app"


def test_a_saved_choice_wins_over_the_config_default():
    saved = {"calibration": {"screen": "control"}}
    loaded = cs.load_settings(saved, {"points": 9, "show": True})
    assert loaded.screen == "control" and loaded.points == 9


# -- the record in calibration.json (4.7) ----------------------------------------------------------


def test_the_record_holds_the_mode_speed_timing_icon_size_background_layout_and_improve_runs():
    settings = cs.CalibrationSettings("app", 5, "slow", "fish", "small", "grey")
    assert record_for(settings, MODE_APP, 2) == {
        "mode": "app_drawn", "speed": "slow", "delay_s": 1.0, "timeout_s": 1.5, "icon": "fish",
        "size": "small", "background": "grey", "layout": "grid3", "improve_runs": 2,
    }
    assert record_for(settings, MODE_FALLBACK)["layout"] == "vendor"


def test_the_record_and_the_scores_reach_the_file_and_load_back(tmp_path):
    points = (per_point((0.1, 0.1), 0.5, 0.5), per_point((0.9, 0.9), 1.5, 1.5, point=2))
    settings = cs.CalibrationSettings("app", 5, "fast", "star", "large", "black")
    run = annotate(
        CalibrationRun(CalibrationResult(5, 12.0, True, per_point=points), MODE_APP), settings, RIG
    )
    result = with_improve_runs(run.result, 3)
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", result)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data["mode"], data["speed"], data["delay_s"], data["timeout_s"]) == ("app_drawn", "fast", 1.8, 0.4)
    assert (data["icon"], data["size"], data["background"], data["layout"], data["improve_runs"]) == (
        "star", "large", "black", "grid3", 3,
    )
    assert [p["score"] for p in data["per_point"]] == [83, 50]
    assert data["per_point"][0]["error_deg"] == pytest.approx(0.5, abs=0.01)

    loaded = load_calibration_result(path).result
    assert loaded.record == result.record and loaded.per_point == result.per_point
    assert loaded == result


def test_the_app_drawn_mean_error_is_computed_from_calib_result_and_control_keeps_its_own():
    points = (per_point((0.5, 0.5), 0.5, 0.5), per_point((0.1, 0.1), 1.5, None, point=2))
    expected = [px_for_degrees(0.5), px_for_degrees(0.5), px_for_degrees(1.5)]
    assert cs.mean_error_px(points, RIG) == pytest.approx(sum(expected) / 3, rel=1e-6)  # valid eyes only
    assert cs.mean_error_px((per_point((0.5, 0.5), 0.5, 0.5, left_valid=False, right_valid=False),), RIG) is None
    assert cs.mean_error_px(None, RIG) is None
    settings = cs.CalibrationSettings()
    got = {"app_drawn": None, "control": 42.0}
    for mode, device_value in got.items():
        result = cs.annotate_result(CalibrationResult(5, device_value, True, per_point=points), settings, mode, RIG)
        if mode == "app_drawn":
            assert result.mean_error_px == pytest.approx(sum(expected) / 3, rel=1e-6)
        else:
            assert result.mean_error_px == 42.0  # Control's own window: its own number, as today


def test_the_modes_are_app_drawn_control_and_control_fallback():
    assert (cs.MODE_APP, cs.MODE_CONTROL, cs.MODE_FALLBACK) == ("app_drawn", "control", "control_fallback")


def test_an_old_calibration_file_without_a_record_still_loads(tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", CalibrationResult(5, 12.0, True))
    assert "mode" not in json.loads(path.read_text(encoding="utf-8"))
    assert load_calibration_result(path).result.record is None


def test_improve_runs_is_set_on_a_copy():
    result = CalibrationResult(5, 1.0, True, record={"mode": "app_drawn", "improve_runs": 0})
    assert with_improve_runs(result, 2).record["improve_runs"] == 2 and result.record["improve_runs"] == 0


# -- the motion's helpers ---------------------------------------------------------------------------


def test_ease_runs_from_0_to_1_and_the_schedule_ends_before_delay():
    assert ease(0) == 0 and ease(1) == 1 and ease(0.5) == pytest.approx(0.5)
    assert ease(-1) == 0 and ease(2) == 1
    for delay in (0.0, 0.05, 0.8, 1.0, 1.8):
        glide, shrink = schedule(delay)
        assert glide >= 0 and shrink >= 0 and glide + shrink <= delay
