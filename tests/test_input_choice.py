"""SPEC-input-selection-and-follow.md H1, H2, H3, H5 (acceptance A9): the Pointer /
Selection pair, the ``input_mode`` derived from it, the glow rule and the Mouse test's
blocker filter. Pure logic, no Qt."""

from __future__ import annotations

import pytest

from src.engine.config import load_task_config
from src.engine.input_choice import (
    CALIBRATION_BLOCKER,
    GAZE_ONLY_BLOCKERS,
    INPUT_MODES,
    TRACKER_BLOCKER,
    InputChoice,
    derive_input_mode,
    drop_gaze_only_blockers,
    glow_active,
    pointer_of_mode,
    resolve_input,
    selection_of_mode,
)
from src.engine.task_runner import TASK_REGISTRY, build_task

TASKS = tuple(TASK_REGISTRY)


# -- H1: the derived input_mode ----------------------------------------------------


@pytest.mark.parametrize(
    "pointer, selection, mode",
    [
        ("gaze", "dwell", "eye"),
        ("gaze", "switch", "gaze_switch"),
        ("mouse", "switch", "switch"),
        ("mouse", "dwell", "mouse_dwell"),  # new in this SPEC
        ("gaze", None, "eye"),  # Follow the Target: no selection
        ("mouse", None, "mouse_follow"),
    ],
)
def test_the_input_mode_is_derived_as_h1_says(pointer, selection, mode):
    assert derive_input_mode(pointer, selection) == mode
    assert InputChoice(pointer, selection).mode == mode
    assert mode in INPUT_MODES


def test_an_unknown_value_takes_the_default():
    assert derive_input_mode("eyes", "dwell") == "eye"
    assert derive_input_mode("mouse", "click") == "mouse_dwell"
    assert derive_input_mode("", "switch") == "gaze_switch"


@pytest.mark.parametrize("mode", INPUT_MODES)
def test_a_mode_names_its_pointer_and_selection(mode):
    # The two helpers invert the derivation, so ``BaseTask`` can read the mode alone.
    pointer, selection = pointer_of_mode(mode), selection_of_mode(mode)
    if mode == "mouse_follow":  # no selection of its own: dwell is the engine's stand-in
        assert (pointer, selection) == ("mouse", "dwell")
    else:
        assert derive_input_mode(pointer, selection) == mode


# -- where the choice comes from -----------------------------------------------------


def cfg(task_id="click_grid", *, block=None, legacy=None):
    config = {"task": {"task_id": task_id}}
    if block is not None:
        config["task"]["input"] = block
    if legacy is not None:
        config["input"] = {"mode": legacy}
    return config


def test_the_tests_own_choice_wins_over_the_global_mode():
    config = cfg(block={"pointer": "mouse", "selection": "switch"}, legacy="eye")
    choice = resolve_input(config)
    assert (choice.pointer, choice.selection, choice.mode) == ("mouse", "switch", "switch")
    assert choice.is_mouse and choice.is_switch


@pytest.mark.parametrize(
    "legacy, expected",
    [
        ("eye", ("gaze", "dwell")),
        ("gaze_switch", ("gaze", "switch")),
        ("switch", ("mouse", "switch")),
        ("mouse_dwell", ("mouse", "dwell")),
        (None, ("gaze", "dwell")),  # no input block anywhere: today's behaviour
    ],
)
def test_a_config_without_the_choice_falls_back_to_the_global_mode(legacy, expected):
    choice = resolve_input(cfg(legacy=legacy))
    assert (choice.pointer, choice.selection) == expected


def test_a_half_stored_choice_takes_the_rest_from_the_global_mode():
    # Only the Pointer is stored (a Follow test): the Selection is not needed there.
    assert resolve_input(cfg(block={"pointer": "mouse"}, legacy="eye")).pointer == "mouse"
    assert resolve_input(cfg(block={"selection": "switch"}, legacy="eye")).mode == "gaze_switch"
    # A value no longer valid (a hand-edited file) is ignored the same way.
    assert resolve_input(cfg(block={"pointer": "touch", "selection": "x"}, legacy="switch")).mode == "switch"


@pytest.mark.parametrize("pointer, mode", [("gaze", "eye"), ("mouse", "mouse_follow")])
def test_follow_the_target_has_no_selection(pointer, mode):
    config = cfg("follow_moving", block={"pointer": pointer, "selection": "switch"}, legacy="switch")
    choice = resolve_input(config)
    assert choice.selection is None and choice.mode == mode and not choice.is_switch


def test_a_missing_config_is_the_default():
    assert resolve_input({}).mode == "eye"
    assert resolve_input({"task": None}).mode == "eye"


@pytest.mark.parametrize("task_id", TASKS)
def test_build_task_reads_the_per_test_choice(task_id):
    config = load_task_config(task_id)
    config["task"]["input"] = {"pointer": "mouse", "selection": "dwell"}
    task = build_task(task_id, config)
    expected = "mouse_follow" if task_id == "follow_moving" else "mouse_dwell"
    assert task.input_mode == expected
    # Dwell is the engine's selection for both (Follow's own rewrite is a later step).
    assert task.input_selection == "dwell"


def test_build_task_without_the_choice_keeps_the_global_mode():
    config = load_task_config("click_static")
    config["input"] = {"mode": "gaze_switch"}
    task = build_task("click_static", config)
    assert (task.input_mode, task.input_selection) == ("gaze_switch", "switch")


# -- H3: the glow ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id, selection, enabled, shown",
    [
        ("click_grid", "switch", True, True),
        ("click_grid", "switch", False, False),
        ("click_grid", "dwell", True, False),  # greyed: the dwell ring takes its place
        ("click_static", "dwell", True, False),
        ("scanning", "switch", True, True),
        ("follow_moving", None, True, True),  # Follow has no dwell ring either
        ("follow_moving", None, False, False),
    ],
)
def test_the_glow_shows_for_switch_and_follow_only(task_id, selection, enabled, shown):
    assert glow_active(task_id, selection, enabled) is shown


# -- H5: the Mouse test's blockers -------------------------------------------------------


def test_the_two_gaze_only_blockers_are_the_setup_pages_own_sentences():
    assert GAZE_ONLY_BLOCKERS == (TRACKER_BLOCKER, CALIBRATION_BLOCKER)
    assert TRACKER_BLOCKER == "The tracker is not connected (Setup page)."
    assert CALIBRATION_BLOCKER == "No calibration yet (Setup page)."


@pytest.mark.parametrize(
    "blockers, remaining, tracker_ok, calibrated",
    [
        ([], [], True, True),
        ([TRACKER_BLOCKER, CALIBRATION_BLOCKER], [], False, False),
        ([CALIBRATION_BLOCKER], [], True, False),
        ([TRACKER_BLOCKER, "Subject ID is empty."], ["Subject ID is empty."], False, True),
        (["Sex is not selected."], ["Sex is not selected."], True, True),
    ],
)
def test_a_mouse_test_drops_only_the_tracker_and_calibration_blockers(
    blockers, remaining, tracker_ok, calibrated
):
    assert drop_gaze_only_blockers(blockers) == (remaining, tracker_ok, calibrated)
