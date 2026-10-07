"""SPEC-input-selection-and-follow.md H1 / H3 / 4.1, acceptance A1 (data side): the
Pointer and Selection settings, the Input card, the card "Dwell", "Glow on target" and
the greying of the controls that Selection makes meaningless. The registry and the
layout are pure data; the page tests build the real ``TaskConfigPage`` offscreen."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from src.engine.config import load_task_config
from src.engine.input_choice import resolve_input
from src.engine.settings_profile import list_named_configurations, save_settings_profile
from src.ui.config_widgets import CONFIG_TOOLTIPS
from src.ui.settings_registry import (
    config_groups_for_task,
    get_nested,
    initial_structural_values,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import (
    complete_settings,
    merged_config,
    run_settings,
    settings_snapshot,
)
from src.ui.task_config_page import TaskConfigPage

TASKS = ("click_static", "click_grid", "follow_moving", "scanning")
SELECTION_TASKS = ("click_static", "click_grid", "scanning")


def controls(task_id):
    return {c.key: c for g in config_groups_for_task(task_id) for c in g.controls}


# -- the registry ---------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_pointer_is_a_choice_on_every_task(task_id):
    setting = next(s for s in structural_settings_for_task(task_id) if s.key == "input.pointer")
    assert setting.kind == "choice" and setting.default == "gaze"
    assert [v for v, _label in setting.choices] == ["gaze", "mouse"]
    assert [label for _v, label in setting.choices] == ["Gaze", "Mouse"]


@pytest.mark.parametrize("task_id", TASKS)
def test_selection_is_a_choice_on_the_three_selection_tasks_only(task_id):
    keys = {s.key for s in structural_settings_for_task(task_id)}
    assert ("input.selection" in keys) == (task_id in SELECTION_TASKS)
    if task_id in SELECTION_TASKS:
        setting = next(s for s in structural_settings_for_task(task_id) if s.key == "input.selection")
        assert setting.default == "dwell" and setting.kind == "choice"
        assert [v for v, _label in setting.choices] == ["dwell", "switch"]


@pytest.mark.parametrize("task_id", TASKS)
def test_glow_on_target_is_a_bool_on_by_default_on_every_task(task_id):
    setting = next(s for s in structural_settings_for_task(task_id) if s.key == "feedback.target_glow")
    assert (setting.kind, setting.default, setting.label) == ("bool", True, "Glow on target")
    assert initial_structural_values(task_id, load_task_config(task_id))["feedback.target_glow"] is True


def test_the_new_controls_have_tooltips():
    for key in ("input.pointer", "input.selection", "feedback.target_glow"):
        assert CONFIG_TOOLTIPS[key]


# -- the layout ------------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_input_card_is_first_in_the_third_column(task_id):
    third = [g for g in config_groups_for_task(task_id) if g.column == 2]
    # (Follow the Target has no Dwell card: nothing to select.)
    assert [g.id for g in third] == (
        ["input", "selection", "smoothing"] if task_id in SELECTION_TASKS else ["input", "smoothing"]
    )
    assert third[0].title == "Input"
    assert [c.key for c in third[0].controls] == (
        ["input.pointer", "input.selection"] if task_id in SELECTION_TASKS else ["input.pointer"]
    )
    assert all(c.widget == "radio" for c in third[0].controls)


@pytest.mark.parametrize("task_id", SELECTION_TASKS)
def test_the_selection_dwell_card_is_now_called_dwell(task_id):
    by_id = {g.id: g for g in config_groups_for_task(task_id)}
    assert by_id["selection"].title == "Dwell"
    assert [c.key for c in by_id["selection"].controls] == [
        "dwell.threshold_ms", "dwell.refractory_ms", "dwell.jitter_tolerance_px",
    ]
    assert not any(g.title == "Selection (Dwell)" for g in by_id.values())


def test_follow_the_target_has_no_dwell_card_at_all():
    by_id = {g.id: g for g in config_groups_for_task("follow_moving")}
    assert "selection" not in by_id and not any(g.title == "Dwell" for g in by_id.values())


@pytest.mark.parametrize("task_id", TASKS)
def test_glow_sits_in_feedback_after_the_rings_and_before_the_sounds(task_id):
    feedback = next(g for g in config_groups_for_task(task_id) if g.id == "feedback")
    keys = [c.key for c in feedback.controls]
    # Follow has no instant ring: the glow follows the gaze cursor there.
    before = "dwell.instant_feedback" if task_id in SELECTION_TASKS else "dwell.visual_cursor"
    assert keys.index(before) < keys.index("feedback.target_glow") < keys.index("feedback.hit_sound")
    assert next(c for c in feedback.controls if c.key == "feedback.target_glow").widget == "check"


@pytest.mark.parametrize("task_id", TASKS)
def test_the_greying_rules_of_4_1(task_id):
    greyed = {k: c.greyed_by for k, c in controls(task_id).items() if c.greyed_by}
    if task_id == "follow_moving":
        # No Selection to grey anything by, and no threshold or ring to grey: only the glow's
        # rule remains on the data, which names a control this page does not have, so it never
        # applies.
        assert greyed == {"feedback.target_glow": ("input.selection", "dwell")}
        assert "input.selection" not in controls(task_id)
        return
    assert greyed == {
        "dwell.threshold_ms": ("input.selection", "switch"),
        "dwell.progress_ring": ("input.selection", "switch"),
        "feedback.target_glow": ("input.selection", "dwell"),
    }
    # Refractory and jitter tolerance stay active under Switch: the debounce and the
    # hitbox apply to it too. And nothing is both greyed by a choice and by a check box.
    assert not any(c.greyed_by and c.depends_on for c in controls(task_id).values())
    for _key, (master, _value) in greyed.items():
        assert master in controls(task_id)


# -- the stored values ------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_a_new_test_starts_at_gaze_dwell_with_the_glow_on(task_id):
    block = settings_snapshot(task_id, load_task_config(task_id))["structural"]
    assert get_nested(block, "input.pointer") == "gaze"
    assert get_nested(block, "input.selection") == ("dwell" if task_id in SELECTION_TASKS else None)
    assert get_nested(block, "feedback.target_glow") is True


@pytest.mark.parametrize("task_id", SELECTION_TASKS)
def test_the_choice_round_trips_through_a_tests_stored_configuration(task_id):
    config = load_task_config(task_id)
    stored = complete_settings(
        task_id, config, None,
        {"input": {"pointer": "mouse", "selection": "switch"}, "feedback": {"target_glow": False}},
    )["structural"]
    assert stored["input"] == {"pointer": "mouse", "selection": "switch"}
    assert stored["feedback"]["target_glow"] is False
    # Run from the stored block, the config resolves to the derived mode (H1).
    choice = resolve_input(merged_config(config, None, stored))
    assert (choice.pointer, choice.selection, choice.mode) == ("mouse", "switch", "switch")
    # What a run records is the final merged config's block, input included (R7).
    block = run_settings(task_id, merged_config(config, None, stored))["structural"]
    assert block["input"] == {"pointer": "mouse", "selection": "switch"}


def test_an_unknown_choice_in_a_stored_configuration_is_the_default():
    block = complete_settings(
        "click_grid", load_task_config("click_grid"), None, {"input": {"pointer": "touch"}}
    )["structural"]
    assert block["input"]["pointer"] == "gaze"


def test_the_choice_persists_in_a_named_configuration(tmp_path):
    values = complete_settings(
        "click_grid", load_task_config("click_grid"), None,
        {"input": {"pointer": "gaze", "selection": "switch"}},
    )
    save_settings_profile(
        tmp_path, "P001", "click_grid", values["live"], values["structural"], None, "Switch child"
    )
    (named,) = list_named_configurations(tmp_path, "P001", "click_grid")
    assert named.name == "Switch child"
    assert named.structural["input"] == {"pointer": "gaze", "selection": "switch"}
    reloaded = complete_settings("click_grid", load_task_config("click_grid"), named.live, named.structural)
    assert json.loads(json.dumps(reloaded["structural"]["input"])) == {
        "pointer": "gaze", "selection": "switch",
    }


# -- the page ---------------------------------------------------------------------------


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


SCREEN = SimpleNamespace(
    geometry=lambda: _Rect(1920, 1080),
    availableGeometry=lambda: _Rect(1920.0, 1000.0),
    devicePixelRatio=lambda: 1.0,
    physicalSize=lambda: _Rect(531.4, 298.9),
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def page_for(task_id, **structural):
    config = load_task_config(task_id)
    page = TaskConfigPage(task_id, config, screen=SCREEN)
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name=f"{task_id} 1", structural=structural or None)
    return page


def enabled(page, key):
    return page._form.controls[key].isEnabled()


@pytest.mark.parametrize("task_id", SELECTION_TASKS)
def test_dwell_greys_the_glow_and_nothing_else(qapp, task_id):
    page = page_for(task_id)
    assert page._form.controls["input.selection"].value() == "dwell"
    assert not enabled(page, "feedback.target_glow")
    for key in ("dwell.threshold_ms", "dwell.progress_ring", "dwell.refractory_ms",
                "dwell.jitter_tolerance_px", "dwell.instant_feedback"):
        assert enabled(page, key), key


@pytest.mark.parametrize("task_id", SELECTION_TASKS)
def test_switch_greys_the_threshold_and_the_ring_and_wakes_the_glow(qapp, task_id):
    page = page_for(task_id, input={"pointer": "gaze", "selection": "switch"})
    assert enabled(page, "feedback.target_glow")
    assert not enabled(page, "dwell.threshold_ms") and not enabled(page, "dwell.progress_ring")
    # The debounce and the hitbox apply to the switch too.
    assert enabled(page, "dwell.refractory_ms") and enabled(page, "dwell.jitter_tolerance_px")
    assert enabled(page, "dwell.instant_feedback")


def test_picking_selection_on_the_page_greys_and_wakes_the_controls_at_once(qapp):
    page = page_for("click_grid")
    selection = page._form.controls["input.selection"]
    selection.setValue("switch")
    assert enabled(page, "feedback.target_glow") and not enabled(page, "dwell.threshold_ms")
    assert page.collect_values()["structural"]["input"]["selection"] == "switch"
    selection.setValue("dwell")
    assert not enabled(page, "feedback.target_glow") and enabled(page, "dwell.threshold_ms")


def test_greyed_controls_keep_their_values(qapp):
    page = page_for("click_grid", input={"pointer": "gaze", "selection": "switch"})
    ring = page._form.controls["dwell.progress_ring"]
    assert not ring.isEnabled() and ring.isChecked()  # greyed, not hidden, not unchecked
    assert page.collect_values()["live"]["dwell.progress_ring"] is True


def test_pointer_mouse_greys_nothing(qapp):
    plain = page_for("click_grid")
    mouse = page_for("click_grid", input={"pointer": "mouse", "selection": "dwell"})
    state = lambda page: {k: w.isEnabled() for k, w in page._form.controls.items()}  # noqa: E731
    assert state(mouse) == state(plain)


def test_follow_has_a_pointer_and_no_dwell_controls_and_its_glow_is_always_on_offer(qapp):
    page = page_for("follow_moving")
    assert "input.selection" not in page._form.controls
    assert page._form.controls["input.pointer"].value() == "gaze"
    for key in ("dwell.threshold_ms", "dwell.progress_ring", "dwell.refractory_ms",
                "dwell.jitter_tolerance_px", "dwell.instant_feedback", "feedback.miss_sound"):
        assert key not in page._form.controls, key
    # No Selection on this page: the glow's rule (greyed under Dwell) never applies.
    assert enabled(page, "feedback.target_glow")


def test_the_pointer_choice_is_collected_for_a_run_and_a_save(qapp):
    page = page_for("scanning")
    page._form.controls["input.pointer"].setValue("mouse")
    structural = page.collect_values()["structural"]
    assert structural["input"] == {"pointer": "mouse", "selection": "dwell"}
    assert page.collect_entry()["structural"]["input"]["pointer"] == "mouse"
    assert page.is_modified()


def test_the_cards_on_the_page_are_titled_input_and_dwell(qapp):
    page = page_for("click_grid")
    titles = {
        group_id: page.cards[group_id].findChild(QLabel, "wtmhSectionTitle").text()
        for group_id in ("input", "selection")
    }
    assert titles == {"input": "Input", "selection": "Dwell"}
