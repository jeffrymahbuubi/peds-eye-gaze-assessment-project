"""SPEC-scene-cause-effect-task.md 4.8 / 4.9 / S8 / A1 (engine side): how Choice-making is
registered, configured and recorded. Pure logic, no Qt widgets."""

from __future__ import annotations

import csv

from src.data.schema import LOOKBACK_COLUMNS, SessionMetadata, TrialRecord
from src.engine.config import load_task_config
from src.engine.subject_tests import create_test, list_tests
from src.engine.task_info import TASK_INFO
from src.engine.task_runner import TASK_REGISTRY, build_task
from src.tasks.choice_making import ChoiceMakingTask
from src.ui.settings_registry import (
    config_groups_for_task,
    initial_live_values,
    initial_structural_values,
    live_settings_for_task,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import merged_config, run_settings
from tests.recorder_helpers import recorder_in

TASK = "choice_making"


# -- registration (A1, S8) ---------------------------------------------------------------------------


def test_the_task_is_registered_with_its_name_and_description():
    assert TASK_REGISTRY[TASK] is ChoiceMakingTask
    assert TASK_INFO[TASK] == (
        "Choice-making",
        "A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive."
        " Cause and effect, with look-back.",
    )


def test_it_is_added_on_request_only_a_new_subject_starts_with_no_tests(tmp_path):
    assert list_tests(tmp_path, "TESTING").tests == []
    test = create_test(tmp_path, "TESTING", TASK)
    assert (test.task_id, test.name) == (TASK, "Choice-making 1")
    assert [t.task_id for t in list_tests(tmp_path, "TESTING").tests] == [TASK]


# -- 4.8: the shipped configuration -------------------------------------------------------------------


def test_the_shipped_config_has_the_4_8_defaults():
    task = load_task_config(TASK)["task"]
    assert task["task_id"] == TASK
    assert (task["trials"], task["timeout_ms"], task["post_effect_ms"]) == (16, 10000, 1000)
    assert (task["scene"], task["language"], task["visual_cue"]) == ("park", "en", False)
    assert task["prompt_mode"] == "voice"  # P1: the default
    assert task["idle_animation"] == "blinks"  # N3: the default, as Grid 3
    assert task["grid"]["gap"] == "standard"
    assert task["feedback"]["miss_sound"] is True
    assert "target" not in task and "inter_trial_interval_ms" not in task  # no size, no ITI


def test_a_task_built_from_it_has_16_balanced_trials_and_a_post_effect_pause():
    task = build_task(TASK, load_task_config(TASK), seed=7)
    assert isinstance(task, ChoiceMakingTask)
    assert len(task.targets) == 16 and task.post_effect_ns == 1_000_000_000
    assert task.timeout_ns == 10_000_000_000
    assert task.visual_cue is False and task.gap_px is None and task.idle_animation == "blinks"


# -- the settings registry -------------------------------------------------------------------------------


def _keys(settings):
    return {s.key for s in settings}


def test_the_choice_making_settings_apply_to_this_task_only():
    for key in ("scene", "language", "prompt_mode", "visual_cue", "idle_animation"):
        assert key in _keys(structural_settings_for_task(TASK))
        for other in ("click_static", "click_grid", "follow_moving", "scanning"):
            assert key not in _keys(structural_settings_for_task(other))
    assert "task.post_effect_ms" in _keys(live_settings_for_task(TASK))
    for other in ("click_static", "click_grid", "follow_moving", "scanning"):
        assert "task.post_effect_ms" not in _keys(live_settings_for_task(other))


def test_the_cell_gap_applies_but_the_size_the_grid_and_the_itis_and_hit_sound_do_not():
    structural = _keys(structural_settings_for_task(TASK))
    assert "grid.gap" in structural
    for gone in ("target.size", "layout.size", "grid.rows", "grid.cols", "layout.n_icons",
                 "motion.path", "feedback.hit_sound"):
        assert gone not in structural, gone
    live = _keys(live_settings_for_task(TASK))
    assert "task.inter_trial_interval_ms" not in live and "task.timeout_ms" in live
    # ... and the input, glow and miss-sound controls are the other tests' (H5, W3).
    for kept in ("input.pointer", "input.selection", "feedback.target_glow", "feedback.miss_sound"):
        assert kept in structural


def test_the_timeout_reads_time_to_choose_and_the_pause_is_in_seconds_too():
    by_key = {s.key: s for s in live_settings_for_task(TASK)}
    timeout, pause = by_key["task.timeout_ms"], by_key["task.post_effect_ms"]
    assert timeout.label == "Time to choose (s)" and pause.label == "Pause after the animation (s)"
    assert timeout.display_divisor == pause.display_divisor == 1000.0
    # Every other task keeps its own label for the same key.
    other = {s.key: s for s in live_settings_for_task("click_static")}
    assert other["task.timeout_ms"].label == "Trial timeout (s)"


def test_the_settings_start_from_the_shipped_config():
    config = load_task_config(TASK)
    structural = initial_structural_values(TASK, config)
    assert structural["trials"] == 16 and structural["scene"] == "park"
    assert structural["language"] == "en" and structural["visual_cue"] is False
    assert structural["prompt_mode"] == "voice"
    assert structural["idle_animation"] == "blinks"
    assert structural["grid.gap"] == "standard"
    live = initial_live_values(config)
    assert live["task.timeout_ms"] == 10000 and live["task.post_effect_ms"] == 1000


def test_every_setting_has_exactly_one_control_on_the_page_and_none_is_hidden():
    controls = [c for g in config_groups_for_task(TASK) for c in g.controls]
    keys = [c.key for c in controls]
    expected = (
        _keys(live_settings_for_task(TASK)) | _keys(structural_settings_for_task(TASK))
        | {"test.name", "test.config_name", "test.notes"}
    )
    assert len(keys) == len(set(keys)) and set(keys) == expected


def test_the_page_has_a_scene_card_in_place_of_the_grid_layout_card():
    groups = {g.id: g for g in config_groups_for_task(TASK)}
    assert "grid" not in groups and "target" not in groups and "icons" not in groups
    scene = groups["scene"]
    assert (scene.title, scene.column, scene.hint) == ("Scene", 1, None)
    assert [c.key for c in scene.controls] == [
        "scene", "language", "prompt_mode", "visual_cue", "idle_animation", "grid.gap",
    ]
    assert [c.key for c in groups["timing"].controls] == ["task.timeout_ms", "task.post_effect_ms"]
    assert [g.id for g in config_groups_for_task(TASK) if g.column == 1] == [
        "scene", "timing", "feedback",
    ]
    # Grid Click keeps its own card, untouched.
    assert "grid" in {g.id for g in config_groups_for_task("click_grid")}
    assert "scene" not in {g.id for g in config_groups_for_task("click_grid")}


# -- 4.9: the trials.csv columns --------------------------------------------------------------------------------


def test_the_choice_making_columns_come_last_and_are_blank_for_other_tasks():
    # The four of step 3, then the nine look-back and waiting-phase ones (4.9).
    n = len(LOOKBACK_COLUMNS)
    header = TrialRecord.csv_header()
    assert header[-n - 4 : -n] == ["prompt_object", "button_side", "selected_object", "rt_ms"]
    assert header[-n:] == list(LOOKBACK_COLUMNS)
    other = TrialRecord(0, "click_grid", 0.5, 0.5, 90.0, 0).as_row()
    assert [other[c] for c in header[-n - 4 :]] == [""] * (n + 4)
    assert list(other) == header


def test_the_columns_are_written_to_trials_csv(tmp_path):
    hit = TrialRecord(
        0, TASK, 0.07, 0.3, 80.0, 0, is_hit=True, prompt_object="balloons", button_side="left",
        selected_object="balloons", rt_ms=812.345, slot_index=0,
    )
    timeout = TrialRecord(
        1, TASK, 0.93, 0.5, 80.0, 0, is_timeout=True, prompt_object="swing", button_side="right",
        slot_index=7,
    )
    meta = SessionMetadata(subject_id="P001", session_id="choice", started_ns=0)
    with recorder_in(tmp_path, meta) as recorder:
        path = recorder.write_trials([hit, timeout])
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["prompt_object"], r["button_side"], r["selected_object"], r["rt_ms"]) for r in rows] == [
        ("balloons", "left", "balloons", "812.35"),
        ("swing", "right", "", ""),
    ]
    assert rows[0]["slot_index"] == "0" and rows[1]["slot_index"] == "7"


# -- N3: the idle animation setting (step 4) --------------------------------------------------------------------


def test_idle_animation_is_a_three_way_choice_that_defaults_to_blinks():
    setting = next(s for s in structural_settings_for_task(TASK) if s.key == "idle_animation")
    assert setting.kind == "choice" and setting.default == "blinks"
    assert [value for value, _label in setting.choices] == ["off", "blinks", "blinks_bob"]
    for other in ("click_static", "click_grid", "follow_moving", "scanning"):
        assert "idle_animation" not in {s.key for s in structural_settings_for_task(other)}


def test_the_chosen_idle_animation_reaches_the_task_the_canvas_spec_and_metadata_json():
    config = load_task_config(TASK)
    for value in ("off", "blinks", "blinks_bob"):
        merged = merged_config(config, structural={"idle_animation": value})
        assert run_settings(TASK, merged, "x")["structural"]["idle_animation"] == value
        task = build_task(TASK, merged, seed=1)
        assert task.idle_animation == value and task.scene_spec()["idle_animation"] == value


def test_an_unknown_idle_animation_is_blinks_everywhere():
    merged = merged_config(load_task_config(TASK), structural={"idle_animation": "dancing"})
    assert initial_structural_values(TASK, merged)["idle_animation"] == "blinks"
    assert run_settings(TASK, merged, "x")["structural"]["idle_animation"] == "blinks"
    assert build_task(TASK, merged, seed=1).scene_spec()["idle_animation"] == "blinks"
