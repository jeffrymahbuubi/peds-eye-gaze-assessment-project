"""SPEC-compass-task-flow.md 4B.2 / 4B.3 / HB3, acceptance AB1 and AB2: the
registries and ``config_groups_for_task`` -- the configuration page as data.

Pure logic, no Qt: the layout spec is held against the registries, so a setting
added to a registry without a place on the page (or placed twice) fails here.
"""

from __future__ import annotations

import pytest

from src.engine.config import load_task_config
from src.ui.settings_registry import (
    HINT_GRID_FIT,
    HINT_ICON_FIT,
    LIVE_SETTINGS,
    STRUCTURAL_SETTINGS,
    LiveSetting,
    StructuralSetting,
    config_groups_for_task,
    get_nested,
    initial_structural_values,
    live_settings_for_task,
    set_nested,
    structural_settings_for_task,
)

TASKS = ("click_static", "click_grid", "follow_moving", "scanning")
PAGE_KEYS = {"test.name", "test.config_name", "test.notes"}

FEEDBACK = [
    "dwell.visual_cursor", "dwell.progress_ring", "dwell.instant_feedback",
    "feedback.target_glow", "feedback.hit_sound", "feedback.miss_sound",
]
FOLLOW_FEEDBACK = ["dwell.visual_cursor", "feedback.target_glow", "feedback.hit_sound"]
INPUT = ["input.pointer", "input.selection"]  # Follow the Target has no Selection (I9)
SELECTION = ["dwell.threshold_ms", "dwell.refractory_ms", "dwell.jitter_tolerance_px"]
SMOOTHING = ["dwell.smoothing.enabled", "dwell.smoothing.alpha"]
TEST_CARD = ["test.name", "test.config_name", "trials", "test.notes"]
TIMING = ["task.timeout_ms", "task.inter_trial_interval_ms"]

# (id, column, hint, controls) per card, in order -- 4B.1 and the 4B.2 tables, reordered by
# clinical weight in SPEC-design-system-phase2.md H6 (V4): column A = Test, Input, Target (or
# Icons); B = the task's own card, Timing, Feedback; C = Dwell, Gaze Smoothing ("Gaze Pointer Settings").
EXPECTED = {
    "click_static": [
        ("test", 0, None, TEST_CARD),
        ("input", 0, None, INPUT),
        ("target", 0, None, ["target.size"]),
        ("timing", 1, None, TIMING),
        ("feedback", 1, None, FEEDBACK),
        ("selection", 2, None, SELECTION),
        ("smoothing", 2, None, SMOOTHING),
    ],
    "click_grid": [
        ("test", 0, None, TEST_CARD),
        ("input", 0, None, INPUT),
        ("target", 0, None, ["target.size"]),
        ("grid", 1, HINT_GRID_FIT, ["grid.rows", "grid.cols", "grid.gap"]),
        ("timing", 1, None, TIMING),
        ("feedback", 1, None, FEEDBACK),
        ("selection", 2, None, SELECTION),
        ("smoothing", 2, None, SMOOTHING),
    ],
    # Follow the Target (SPEC-input-selection-and-follow.md 4.1): nothing to select, so no Dwell
    # card, no dwell ring or instant ring, no miss sound, no selection window; the Timing card
    # holds "Trial duration" (same key as the timeout) and the inter-trial interval.
    "follow_moving": [
        ("test", 0, None, TEST_CARD),
        ("input", 0, None, ["input.pointer"]),
        ("target", 0, None, ["target.size"]),
        ("motion", 1, None, ["motion.path", "motion.speed_frac_per_s"]),
        ("timing", 1, None, TIMING),
        ("feedback", 1, None, FOLLOW_FEEDBACK),
        ("smoothing", 2, None, SMOOTHING),
    ],
    "scanning": [
        ("test", 0, None, TEST_CARD),
        ("input", 0, None, INPUT),
        ("icons", 0, HINT_ICON_FIT, ["layout.size", "layout.n_icons"]),
        ("timing", 1, None, TIMING),
        ("feedback", 1, None, FEEDBACK),
        ("selection", 2, None, SELECTION),
        ("smoothing", 2, None, SMOOTHING),
    ],
}


def _controls(task_id):
    return [c for g in config_groups_for_task(task_id) for c in g.controls]


# -- AB1 / AB2 --------------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_every_setting_of_the_task_has_exactly_one_control_and_none_is_hidden(task_id):
    keys = [c.key for c in _controls(task_id)]
    expected = (
        {s.key for s in live_settings_for_task(task_id)}
        | {s.key for s in structural_settings_for_task(task_id)}
        | PAGE_KEYS
    )
    assert len(keys) == len(set(keys)), "a control is placed twice"
    assert set(keys) == expected


@pytest.mark.parametrize("task_id", TASKS)
def test_no_task_has_a_px_target_radius_control(task_id):
    assert not any(c.key.endswith("radius_px") for c in _controls(task_id))


@pytest.mark.parametrize("task_id", TASKS)
def test_cards_columns_and_order_follow_the_4b2_tables(task_id):
    got = [(g.id, g.column, g.hint, [c.key for c in g.controls])
           for g in config_groups_for_task(task_id)]
    assert got == EXPECTED[task_id]


def test_task_specific_controls_appear_only_on_their_task():
    for key, only in (
        ("grid.rows", "click_grid"), ("grid.cols", "click_grid"), ("grid.gap", "click_grid"),
        ("motion.path", "follow_moving"), ("motion.speed_frac_per_s", "follow_moving"),
        ("layout.size", "scanning"), ("layout.n_icons", "scanning"),
    ):
        assert [t for t in TASKS if key in {c.key for c in _controls(t)}] == [only], key
    # ... and what Follow the Target gave up is on the other three only.
    for key in ("dwell.threshold_ms", "dwell.refractory_ms", "dwell.jitter_tolerance_px",
                "dwell.progress_ring", "dwell.instant_feedback", "feedback.miss_sound",
                "input.selection"):
        assert [t for t in TASKS if key in {c.key for c in _controls(t)}] == [
            "click_static", "click_grid", "scanning",
        ], key
    assert not any("select_window" in c.key for t in TASKS for c in _controls(t))
    assert [t for t in TASKS if "target.size" in {c.key for c in _controls(t)}] == [
        "click_static", "click_grid", "follow_moving",
    ]


def test_an_unknown_task_still_gets_the_common_cards():
    ids = [g.id for g in config_groups_for_task("not_a_task")]
    # Pointer is on every task, so the Input card is too (Selection is only on three).
    assert ids == ["test", "input", "timing", "feedback", "selection", "smoothing"]


# -- widget kinds and dependencies ------------------------------------------------------


def test_widget_kinds_follow_the_compass_principle():
    kinds = {c.key: c.widget for c in _controls("follow_moving") + _controls("click_grid")
             + _controls("scanning")}
    assert kinds["test.name"] == "line_edit"
    assert kinds["test.config_name"] == "combo_edit"
    assert kinds["test.notes"] == "notes"
    for key in ("target.size", "layout.size", "grid.gap", "motion.path"):  # one-of: radio (HB1)
        assert kinds[key] == "radio", key
    for key in FEEDBACK + ["dwell.smoothing.enabled"]:  # on/off: check box
        assert kinds[key] == "check", key
    for key in ("trials", "grid.rows", "layout.n_icons", "dwell.threshold_ms", "task.timeout_ms"):
        assert kinds[key] == "slider_int", key
    for key in ("dwell.smoothing.alpha", "motion.speed_frac_per_s"):
        assert kinds[key] == "slider_float", key


@pytest.mark.parametrize("task_id", TASKS)
def test_only_smoothing_alpha_depends_on_something(task_id):
    controls = {c.key: c for c in _controls(task_id)}
    assert {k: c.depends_on for k, c in controls.items() if c.depends_on} == {
        "dwell.smoothing.alpha": "dwell.smoothing.enabled"
    }
    # The control it names exists on the same page and is a check box.
    assert controls["dwell.smoothing.enabled"].widget == "check"


def test_a_control_carries_its_registry_entry_and_label():
    for control in _controls("click_grid"):
        if control.layer == "page":
            assert control.setting is None
            continue
        assert isinstance(
            control.setting, LiveSetting if control.layer == "live" else StructuralSetting
        )
        assert control.setting.key == control.key
        assert control.setting.label == control.label
    layers = {c.key: c.layer for c in _controls("click_grid")}
    assert layers["dwell.threshold_ms"] == "live"
    assert layers["trials"] == layers["feedback.hit_sound"] == "structural"
    assert layers["test.name"] == "page"


# -- the new bool kind (HB3) -------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_sound_toggles_are_structural_bools_and_follow_has_no_miss_sound(task_id):
    by_key = {s.key: s for s in structural_settings_for_task(task_id)}
    sounds = [("feedback.hit_sound", "Play hit sound")]
    if task_id != "follow_moving":  # Follow plays a hit sound only (I10)
        sounds.append(("feedback.miss_sound", "Play miss sound"))
    for key, label in sounds:
        assert by_key[key].kind == "bool"
        assert by_key[key].default is True
        assert by_key[key].label == label
    assert ("feedback.miss_sound" in by_key) == (task_id != "follow_moving")
    assert "feedback.particles" not in by_key  # the dead key stays unexposed


@pytest.mark.parametrize("task_id", TASKS)
def test_a_bool_takes_the_task_yaml_value_and_nests_like_the_others(task_id):
    values = initial_structural_values(task_id, load_task_config(task_id))
    assert values["feedback.hit_sound"] is True
    assert values.get("feedback.miss_sound", True) is True  # (absent for Follow the Target)
    nested: dict = {}
    set_nested(nested, "feedback.hit_sound", values["feedback.hit_sound"])
    assert nested == {"feedback": {"hit_sound": True}}


def test_a_bool_reads_false_from_the_config_and_falls_back_for_anything_else():
    def value(feedback, key="feedback.hit_sound"):
        task = {} if feedback is None else {"feedback": feedback}
        return initial_structural_values("click_grid", {"task": task})[key]

    assert value({"hit_sound": False}) is False
    assert value({"hit_sound": True}) is True
    assert value(None) is True  # no feedback block
    assert value({}) is True  # no key
    assert value({"hit_sound": "no"}) is True  # not a bool: the setting's default
    assert value({"hit_sound": 0}) is True
    assert value({"hit_sound": False}, "feedback.miss_sound") is True  # keys are independent


def test_the_registries_still_hold_one_entry_per_key():
    for registry in (LIVE_SETTINGS, STRUCTURAL_SETTINGS):
        keys = [s.key for s in registry]
        assert len(keys) == len(set(keys))
    assert not {s.key for s in LIVE_SETTINGS} & {s.key for s in STRUCTURAL_SETTINGS}


def test_number_and_choice_lookups_are_unchanged_by_the_bool_branch():
    cfg = load_task_config("click_grid")
    values = initial_structural_values("click_grid", cfg)
    assert values["trials"] == get_nested(cfg["task"], "trials")
    assert values["target.size"] == "medium"
    assert values["grid.gap"] == "standard"

