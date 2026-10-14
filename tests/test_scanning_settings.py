"""SPEC-scanning-search-cues.md 4.5, acceptance C6: the two settings of Scanning Search's search cues
(``search_mode``, ``start_dot``) are registry entries of the Icons card, stored with the test, written to
``metadata.json`` (``settings.structural``), shown in the report's Test Configuration and followed by the
Start page's instructions. The Standard configuration keeps today's behaviour. No Qt."""

from __future__ import annotations

import pytest

from src.data.report_config import build_config_rows, search_mode_text
from src.data.report_util import NOT_RECORDED
from src.engine.config import load_task_config
from src.engine.subject_tests import create_test, list_tests
from src.engine.task_runner import build_task
from src.tasks.search_cues import MATCH_SAMPLE, POP_OUT, SEARCH_MODE_NAMES
from src.ui.settings_registry import (
    config_groups_for_task,
    initial_structural_values,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import complete_settings, merged_config, run_settings
from src.ui.task_instructions import build_instructions

TASK = "scanning"
OTHERS = ("click_static", "click_grid", "follow_moving", "choice_making")
SAMPLE_SENTENCE = "You will see and hear which shape to find. Then look at the same shape among the others."


def _setting(key, task=TASK):
    return next(s for s in structural_settings_for_task(task) if s.key == key)


# -- the registry entries ------------------------------------------------------------------------------


def test_search_mode_is_a_two_way_choice_that_defaults_to_pop_out():
    setting = _setting("search_mode")
    assert setting.kind == "choice" and setting.default == POP_OUT and setting.label == "Search mode"
    assert setting.choices == (
        ("pop_out", "Pop-out: the target is the coloured icon"),
        ("match_sample", "Match the sample: find the shape shown first"),
    )
    assert setting.applies_to == ("scanning",)


def test_start_dot_is_a_tick_box_that_is_off_by_default():
    setting = _setting("start_dot")
    assert setting.kind == "bool" and setting.default is False
    assert setting.label == "Start each trial from the centre" and setting.applies_to == ("scanning",)


def test_sample_reminder_is_a_tick_box_that_is_off_by_default_and_greyed_for_pop_out():
    setting = _setting("sample_reminder")
    assert setting.kind == "bool" and setting.default is False and setting.applies_to == ("scanning",)
    icons = next(g for g in config_groups_for_task(TASK) if g.id == "icons")
    control = next(c for c in icons.controls if c.key == "sample_reminder")
    assert control.greyed_by == (("search_mode", "pop_out"),)


@pytest.mark.parametrize("other", OTHERS)
def test_no_other_task_has_any_of_the_settings(other):
    keys = {s.key for s in structural_settings_for_task(other)}
    assert not {"search_mode", "start_dot", "sample_reminder"} & keys


def test_they_are_in_the_icons_card_under_number_of_icons():
    icons = next(g for g in config_groups_for_task(TASK) if g.id == "icons")
    assert [c.key for c in icons.controls] == [
        "layout.size", "layout.n_icons", "search_mode", "sample_reminder", "start_dot",
    ]
    widgets = {c.key: c.widget for c in icons.controls}
    assert widgets["search_mode"] == "radio" and widgets["start_dot"] == widgets["sample_reminder"] == "check"
    assert {c.layer for c in icons.controls} == {"structural"}


def test_the_shipped_configuration_is_standard_and_keeps_todays_behaviour():
    config = load_task_config(TASK)
    values = initial_structural_values(TASK, config)
    assert values["search_mode"] == "pop_out" and values["start_dot"] is False
    assert values["sample_reminder"] is False
    task = build_task(TASK, config, seed=1)
    assert (task.search_mode, task.start_dot, task.sample_reminder) == ("pop_out", False, False)


def test_a_saved_sample_reminder_reaches_the_run_and_its_metadata():
    merged = merged_config(load_task_config(TASK), structural={"search_mode": "match_sample", "sample_reminder": True})
    assert run_settings(TASK, merged, "Saved")["structural"]["sample_reminder"] is True
    assert build_task(TASK, merged, seed=1).sample_reminder is True


@pytest.mark.parametrize("junk", ["shout", "", None, 3])
def test_an_unknown_search_mode_is_pop_out_everywhere(junk):
    merged = merged_config(load_task_config(TASK), structural={"search_mode": junk})
    assert initial_structural_values(TASK, merged)["search_mode"] == "pop_out"
    assert run_settings(TASK, merged, "x")["structural"]["search_mode"] == "pop_out"
    assert build_task(TASK, merged, seed=1).search_mode == "pop_out"


# -- stored with the test and written to the run's metadata ----------------------------------------------


def test_the_settings_are_stored_with_the_test_and_a_run_built_from_it_uses_them(tmp_path):
    config = load_task_config(TASK)
    stored = complete_settings(TASK, config, structural={"search_mode": "match_sample", "start_dot": True})
    assert stored["structural"]["search_mode"] == "match_sample" and stored["structural"]["start_dot"] is True
    create_test(
        tmp_path, "TESTING", TASK,
        configuration={"name": "Saved", "structural": stored["structural"], "live": stored["live"]},
    )
    test = list_tests(tmp_path, "TESTING").tests[0]
    assert test.configuration["structural"]["search_mode"] == "match_sample"
    assert test.configuration["structural"]["start_dot"] is True
    merged = merged_config(config, test.configuration["live"], test.configuration["structural"])
    task = build_task(TASK, merged, seed=test.seed)
    assert (task.search_mode, task.start_dot) == ("match_sample", True)
    # A configuration saved with the defaults stays so even if the shipped ones were to change later.
    standard = complete_settings(TASK, config)["structural"]
    assert (standard["search_mode"], standard["start_dot"]) == ("pop_out", False)


@pytest.mark.parametrize("mode, dot", [("pop_out", False), ("match_sample", True), ("pop_out", True)])
def test_the_run_metadata_records_them_in_settings_structural(mode, dot):
    merged = merged_config(load_task_config(TASK), structural={"search_mode": mode, "start_dot": dot})
    structural = run_settings(TASK, merged, "Saved")["structural"]
    assert (structural["search_mode"], structural["start_dot"]) == (mode, dot)


def test_other_tasks_metadata_has_neither_key():
    for other in OTHERS:
        structural = run_settings(other, load_task_config(other), "Standard")["structural"]
        assert "search_mode" not in structural and "start_dot" not in structural


# -- the report's Test Configuration ------------------------------------------------------------------------


def _rows(structural, task=TASK):
    snapshot = {"config_name": "Standard", "live": {}, "structural": structural}
    return dict(build_config_rows(snapshot, {"tasks": [task]}, task_id=task))


@pytest.mark.parametrize("mode, text", [("pop_out", "Pop-out"), ("match_sample", "Match the sample")])
def test_the_report_names_the_search_mode(mode, text):
    assert _rows({"search_mode": mode})["Search mode"] == text
    assert search_mode_text(mode) == text == SEARCH_MODE_NAMES[mode]


@pytest.mark.parametrize("dot, text", [(True, "On"), (False, "Off")])
def test_the_report_says_whether_each_trial_started_from_the_centre(dot, text):
    assert _rows({"start_dot": dot})["Centre start"] == text


@pytest.mark.parametrize("on, text", [(True, "On"), (False, "Off")])
def test_the_report_says_whether_the_sample_stayed_as_a_reminder(on, text):
    assert _rows({"sample_reminder": on})["Sample reminder"] == text


def test_a_run_made_before_the_settings_says_not_recorded_never_a_guess():
    rows = _rows({"layout": {"n_icons": 4}})
    assert rows["Search mode"] == NOT_RECORDED and rows["Centre start"] == NOT_RECORDED
    assert rows["Sample reminder"] == NOT_RECORDED
    assert search_mode_text("") == NOT_RECORDED and search_mode_text(None) == NOT_RECORDED
    assert search_mode_text("shout") == "Pop-out"


def test_scanning_has_three_more_rows_after_the_layout_and_no_other_task_does():
    snapshot = {"config_name": "Standard", "live": {}, "structural": {"search_mode": "pop_out", "start_dot": False}}
    scanning = [label for label, _v in build_config_rows(snapshot, {"tasks": [TASK]}, task_id=TASK)]
    assert len(scanning) == 21
    after = scanning[scanning.index("Layout") + 1 : scanning.index("Layout") + 4]
    assert after == ["Search mode", "Sample reminder", "Centre start"]
    for other in ("click_static", "click_grid", "follow_moving"):
        labels = [label for label, _v in build_config_rows(snapshot, {"tasks": [other]}, task_id=other)]
        assert len(labels) == 18 and "Search mode" not in labels and "Centre start" not in labels
        assert "Sample reminder" not in labels


# -- the Start page's instructions ------------------------------------------------------------------------


def _cfg(**structural):
    return merged_config(load_task_config(TASK), structural=structural)


def test_pop_out_keeps_todays_instructions():
    text = build_instructions(TASK, _cfg(search_mode="pop_out"))
    assert text == build_instructions(TASK, load_task_config(TASK))
    assert text.steps[1] == "One shape will light up bright. The others stay dim."
    assert text.note.startswith("NOTE: If the shape is not selected within")


def test_match_the_sample_says_to_find_the_shape_shown_and_heard():
    text = build_instructions(TASK, _cfg(search_mode="match_sample"))
    assert SAMPLE_SENTENCE in text.steps[0]
    assert len(text.steps) == 4 and not any("light up" in s or "bright" in s for s in text.steps)
    assert "{" not in "".join(text.steps) + text.note
    assert "0.8 seconds" in text.steps[1] and "10 seconds" in text.note


def test_match_the_sample_instructions_follow_switch_and_mouse():
    switch = build_instructions(TASK, _cfg(search_mode="match_sample", **{"input": {"selection": "switch"}}))
    assert any("press the button" in s and "same shape" in s for s in switch.steps)
    assert not any("bright" in s for s in switch.steps)
    mouse = build_instructions(TASK, _cfg(search_mode="match_sample", **{"input": {"pointer": "mouse"}}))
    assert "point at the same shape" in mouse.steps[0] and "Move the mouse" in mouse.steps[0]


def test_the_other_tasks_instructions_ignore_the_search_mode():
    for other in ("click_static", "click_grid", "follow_moving"):
        cfg = load_task_config(other)
        cfg["task"]["search_mode"] = MATCH_SAMPLE
        assert build_instructions(other, cfg) == build_instructions(other, load_task_config(other))


# -- the centre dot's sentence (user, 2026-10-14) ------------------------------------------------------------

DOT_SENTENCE = "Each time, first look at the small dot in the middle."
GAZE_DOT = "The small dot on the screen shows where you are looking. "


@pytest.mark.parametrize("mode", ["pop_out", "match_sample"])
def test_the_centre_dot_sentence_leads_the_instructions_when_the_start_dot_is_on(mode):
    off = build_instructions(TASK, _cfg(search_mode=mode, start_dot=False))
    on = build_instructions(TASK, _cfg(search_mode=mode, start_dot=True))
    assert on.steps[0] == GAZE_DOT + DOT_SENTENCE
    # Everything else is as it was: the gaze-dot sentence moved from the old first step to the new one.
    assert on.steps[1:] == (off.steps[0].removeprefix(GAZE_DOT), *off.steps[1:])
    assert (on.note, on.clinician, on.heading) == (off.note, off.clinician, off.heading)
    assert not any("{" in s for s in on.steps)


@pytest.mark.parametrize("mode", ["pop_out", "match_sample"])
def test_without_the_start_dot_the_instructions_have_no_such_sentence(mode):
    text = build_instructions(TASK, _cfg(search_mode=mode, start_dot=False))
    assert not any("small dot in the middle" in s for s in text.steps)
    assert text == build_instructions(TASK, _cfg(search_mode=mode))  # an unticked box is the default


def test_the_dot_sentence_stands_alone_when_the_gaze_cursor_is_hidden():
    values = {"dwell.visual_cursor": False}
    text = build_instructions(TASK, _cfg(search_mode="pop_out", start_dot=True), values)
    assert text.steps[0] == DOT_SENTENCE and "where you are looking" not in "".join(text.steps)


def test_the_dot_sentence_follows_the_mouse_and_a_switch():
    mouse = build_instructions(TASK, _cfg(start_dot=True, **{"input": {"pointer": "mouse"}}))
    assert mouse.steps[0] == "Move the mouse to point at the screen. Each time, first point at the small dot in the middle."
    switch = build_instructions(TASK, _cfg(search_mode="match_sample", start_dot=True, **{"input": {"selection": "switch"}}))
    assert switch.steps[0] == GAZE_DOT + DOT_SENTENCE
    assert any("press the button" in s for s in switch.steps)


def test_the_other_tests_instructions_ignore_the_start_dot():
    for other in ("click_static", "click_grid", "follow_moving"):
        cfg = load_task_config(other)
        cfg["task"]["start_dot"] = True
        assert build_instructions(other, cfg) == build_instructions(other, load_task_config(other))
