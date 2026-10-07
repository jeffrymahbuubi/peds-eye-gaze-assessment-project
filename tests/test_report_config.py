"""SPEC-compass-task-flow.md 4D.3: the 17-row Test Configuration table (R7)."""

from __future__ import annotations

import copy

from src.data.report_config import DASH, build_config_rows, setting
from src.data.report_geometry import Geometry
from tests.report_fixtures import RIG_META

LABELS = [
    "Configuration name", "Task", "Input", "Trials (planned)", "Selection", "Target size",
    "Layout", "Maximum time per trial", "Pause between trials", "Theme", "Gaze cursor shown",
    "Feedback", "Gaze smoothing", "Display", "Viewing distance", "Calibration", "Canvas",
]


def rows(meta=None, **kw):
    meta = RIG_META if meta is None else meta
    return dict(build_config_rows(meta.get("settings"), meta, **kw))


def test_a_full_run_gives_the_17_rows_in_order_with_the_values_it_used():
    out = build_config_rows(RIG_META["settings"], RIG_META, geometry=Geometry.from_metadata(RIG_META))
    assert [label for label, _ in out] == LABELS
    assert dict(out) == {
        "Configuration name": "Standard",
        "Task": "Grid Click",
        "Input": "Eye gaze (dwell), GP3HD, 150 Hz",
        "Trials (planned)": "6",
        "Selection": "Dwell 0.8 s, refractory 0.5 s",
        "Target size": "Medium (5°), 103 px radius",
        "Layout": "3×3 grid, gap Standard",
        "Maximum time per trial": "8 s",
        "Pause between trials": "0.8 s",
        "Theme": "Forest",
        "Gaze cursor shown": "Yes",
        "Feedback": "Sound on, sparkle on",
        "Gaze smoothing": "Smoothing α 0.22, jitter tolerance 40 px",
        "Display": "1920×1080 @ 100% (standard)",
        "Viewing distance": "650 mm",
        "Calibration": "5 points, mean error 21.3 px (0.52°), measured",
        "Canvas": "1640×957 physical px",
    }


def test_nothing_known_is_17_dashes_not_17_guesses():
    out = build_config_rows(None, None)
    assert [label for label, _ in out] == LABELS
    assert {v for _, v in out} == {DASH}
    assert dict(build_config_rows({}, {}))["Task"] == DASH


def test_the_task_comes_from_the_argument_or_metadata_tasks():
    meta = {"tasks": ["scanning"]}
    assert rows(meta)["Task"] == "Scanning Search"
    assert rows(meta, task_id="follow_moving")["Task"] == "Follow the Target"
    assert rows({"tasks": ["mystery"]})["Task"] == "mystery"


def test_the_resolved_planned_count_wins_over_the_requested_one():
    meta = dict(RIG_META, planned_trials=18)
    assert rows(meta)["Trials (planned)"] == "18"


def test_a_capped_target_says_so():
    out = rows(shrunk={"requested_px": 165.6, "used_px": 53.3, "rows": 6, "cols": 6})
    assert out["Target size"] == "Medium (5°), 103 px radius, capped to 53 px to fit"


def test_a_legacy_folder_with_an_explicit_radius_shows_it():
    meta = {"settings": {"live": {}, "structural": {"target": {"radius_px": 100}}}}
    assert rows(meta, task_id="click_grid")["Target size"] == "100 px radius"
    scan = {"settings": {"structural": {"layout": {"radius_px": 90}}}}
    assert rows(scan, task_id="scanning")["Icon size"] == "90 px radius"
    assert "Target size" not in rows(scan, task_id="scanning")


def test_layout_per_task():
    grid = copy.deepcopy(RIG_META)
    grid["grid_gap"] = {"preset": "wide", "gap_deg": 1.0, "gap_px": 41.0}
    grid["settings"]["structural"]["grid"] = {"rows": 6, "cols": 6, "gap": "wide"}
    assert rows(grid)["Layout"] == "6×6 grid, gap Wide"
    cells = {"layout_slots": [[0, 0]] * 9, "tasks": ["click_grid"]}
    assert rows(cells)["Layout"] == "9 cells"
    scan = {"settings": {"structural": {"layout": {"n_icons": 8, "arrangement": "ring"}}}}
    assert rows(scan, task_id="scanning")["Layout"] == "8 icons, ring"
    assert rows({"layout_slots": [[0, 0]] * 4}, task_id="scanning")["Layout"] == "4 icons"
    move = {"settings": {"live": {"motion.speed_frac_per_s": 0.2},
                         "structural": {"motion": {"path": "diagonal_tlbr", "select_window_ms": 2500}}}}
    assert rows(move, task_id="follow_moving")["Layout"] == (
        "Diagonal (top-left to bottom-right) path, 20% of the width per second, "
        "selection window 2.5 s"
    )
    static = {"settings": {"structural": {"target": {"positions": [[0.1, 0.1]] * 8}}}}
    assert rows(static, task_id="click_static")["Layout"] == "8 positions"


def test_input_and_selection_for_the_switch_modes():
    switch = dict(RIG_META, input_mode="switch")
    assert rows(switch)["Input"] == "Switch (mouse pointer)"
    assert rows(switch)["Selection"] == "Switch press, refractory 0.5 s"
    both = dict(RIG_META, input_mode="gaze_switch")
    assert rows(both)["Input"] == "Gaze pointer + switch, GP3HD, 150 Hz"
    assert rows(both)["Selection"] == "Switch press, refractory 0.5 s"


def test_the_device_rate_falls_back_to_the_measured_one():
    meta = dict(RIG_META, gazepoint_rate_hz=None, measured_sample_rate_hz=148.5)
    assert rows(meta)["Input"] == "Eye gaze (dwell), GP3HD, 148.5 Hz"


def test_feedback_and_smoothing_variants():
    meta = copy.deepcopy(RIG_META)
    meta["settings"]["structural"]["feedback"] = {"hit_sound": True, "miss_sound": False,
                                                  "particles": False}
    meta["settings"]["live"]["dwell.smoothing.enabled"] = False
    out = rows(meta)
    assert out["Feedback"] == "Sound hit only, sparkle off"
    assert out["Gaze smoothing"] == "Smoothing off, jitter tolerance 40 px"
    meta["settings"]["structural"]["feedback"] = {"hit_sound": False, "miss_sound": False}
    assert rows(meta)["Feedback"] == "Sound off, sparkle off"


def test_theme_may_be_a_name_or_a_block():
    meta = {"settings": {"structural": {"theme": {"name": "space"}}}}
    assert rows(meta)["Theme"] == "Space"


def test_display_and_calibration_variants():
    meta = dict(RIG_META, display_scale_percent=150, display_standard=False,
                calibration_source="not run")
    out = rows(meta)
    assert out["Display"] == "1920×1080 @ 150% (not standard)"
    assert out["Calibration"] == "Not run"
    no_geo = rows(dict(RIG_META), geometry=None)
    assert no_geo["Calibration"] == "5 points, mean error 21.3 px, measured"
    legacy_canvas = rows(dict(RIG_META, canvas_units=None))
    assert legacy_canvas["Canvas"] == "1640×957 px"


def test_the_config_name_falls_back_to_the_metadata_one():
    meta = {"config_name": "Custom 1", "settings": {"live": {}, "structural": {}}}
    assert rows(meta)["Configuration name"] == "Custom 1"


def test_setting_prefers_the_live_key_and_walks_the_structural_path():
    snap = {"live": {"a.b": 5}, "structural": {"a": {"b": 1, "c": 2}}}
    assert setting(snap, "a.b", "a", "b") == 5
    assert setting(snap, "x", "a", "c") == 2
    assert setting(snap, None, "a", "zzz") is None
    assert setting(snap, None, "a", "b", "deeper") is None
    assert setting(None, "a.b", "a") is None
