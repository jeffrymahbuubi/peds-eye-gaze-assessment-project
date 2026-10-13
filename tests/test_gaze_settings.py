"""The gaze-signal and smoothing settings (SPEC-gaze-stability-and-positioning.md 4.2, 4.3, 4.8;
acceptance A10): the registry entries and their order, what greys each one on the configuration
page, saved profiles (an old one loads as `best` + `ema`) and the metadata snapshot. Offscreen Qt
for the page; the rest is headless."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.config import load_task_config
from src.engine.settings_profile import load_settings_profile, save_settings_profile
from src.ui.settings_registry import (
    LIVE_SETTINGS,
    apply_live_values_to_config,
    config_groups_for_task,
    initial_live_values,
    live_settings_for_task,
)
from src.ui.settings_snapshot import complete_settings, run_settings, settings_snapshot
from src.ui.task_config_page import TaskConfigPage
from tests.dashboard_fixtures import control

TASKS = ["click_static", "click_grid", "follow_moving", "scanning", "choice_making"]
CARD = [
    "dwell.pointer_signal", "dwell.aac_filter_samples", "dwell.smoothing.enabled",
    "dwell.smoothing.type", "dwell.smoothing.alpha", "dwell.smoothing.min_cutoff_hz",
    "dwell.smoothing.beta",
]
NEW_DEFAULTS = {
    "dwell.pointer_signal": "best", "dwell.aac_filter_samples": 15, "dwell.smoothing.type": "ema",
    "dwell.smoothing.min_cutoff_hz": 0.3, "dwell.smoothing.beta": 5.0,
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- the registry (4.8) -------------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_gaze_smoothing_card_lists_the_seven_controls_in_the_wireframe_order(task_id):
    card = next(g for g in config_groups_for_task(task_id) if g.id == "smoothing")
    assert (card.title, card.column) == ("Gaze Smoothing", 2)
    assert [c.key for c in card.controls] == CARD
    widgets = {c.key: c.widget for c in card.controls}
    assert widgets["dwell.pointer_signal"] == widgets["dwell.smoothing.type"] == "radio"
    assert widgets["dwell.smoothing.enabled"] == "check"
    assert widgets["dwell.aac_filter_samples"] == "slider_int"
    assert all(widgets[k] == "slider_float" for k in CARD[4:])


def test_the_new_settings_have_the_specs_ranges_and_options():
    by_key = {s.key: s for s in LIVE_SETTINGS}
    aac = by_key["dwell.aac_filter_samples"]
    assert (aac.min, aac.max, aac.step) == (1, 60, 1)
    cutoff, beta = by_key["dwell.smoothing.min_cutoff_hz"], by_key["dwell.smoothing.beta"]
    assert (cutoff.min, cutoff.max) == (0.05, 5.0) and (beta.min, beta.max) == (0.0, 10.0)
    assert [v for v, _ in by_key["dwell.pointer_signal"].choices] == ["best", "fixation", "assistive"]
    assert [label for _, label in by_key["dwell.pointer_signal"].choices] == [
        "Raw gaze (BPOG)", "Fixation (FPOG)", "Assistive (APOG)"
    ]
    assert list(by_key["dwell.smoothing.type"].choices) == [
        ("ema", "Simple"), ("one_euro", "Adaptive (One Euro)")
    ]
    assert [s.label for s in (cutoff, beta)] == ["Steadiness (Hz)", "Responsiveness"]


@pytest.mark.parametrize("task_id", TASKS)
def test_every_page_has_the_card_and_every_setting_has_exactly_one_control(task_id):
    keys = [c.key for g in config_groups_for_task(task_id) for c in g.controls]
    assert len(keys) == len(set(keys))
    assert {s.key for s in live_settings_for_task(task_id)} <= set(keys)


@pytest.mark.parametrize("task_id", TASKS)
def test_the_greying_rules_of_4_8(task_id):
    card = next(g for g in config_groups_for_task(task_id) if g.id == "smoothing")
    by_key = {c.key: c for c in card.controls}
    mouse = ("input.pointer", "mouse")
    assert by_key["dwell.pointer_signal"].greyed_by == (mouse,)
    assert set(by_key["dwell.aac_filter_samples"].greyed_by) == {
        mouse, ("dwell.pointer_signal", "best"), ("dwell.pointer_signal", "fixation")
    }
    assert set(by_key["dwell.smoothing.alpha"].greyed_by) == {mouse, ("dwell.smoothing.type", "one_euro")}
    for key in ("dwell.smoothing.min_cutoff_hz", "dwell.smoothing.beta"):
        assert set(by_key[key].greyed_by) == {mouse, ("dwell.smoothing.type", "ema")}
    # The three numbers follow the check box; the type and the signal do not.
    assert {k: c.depends_on for k, c in by_key.items() if c.depends_on} == {
        "dwell.smoothing.alpha": "dwell.smoothing.enabled",
        "dwell.smoothing.min_cutoff_hz": "dwell.smoothing.enabled",
        "dwell.smoothing.beta": "dwell.smoothing.enabled",
    }


# -- the stored values (A10) -------------------------------------------------------------------


def test_the_defaults_stay_best_and_ema_whatever_the_config_says_or_lacks():
    values = initial_live_values({})
    assert {k: values[k] for k in NEW_DEFAULTS} == NEW_DEFAULTS
    assert values["dwell.smoothing.enabled"] is True and values["dwell.smoothing.alpha"] == 0.35


def test_a_config_value_is_read_and_a_bad_choice_is_the_default():
    dwell = {
        "pointer_signal": "assistive", "aac_filter_samples": 30,
        "smoothing": {"type": "one_euro", "min_cutoff_hz": 0.4, "beta": 6.0},
    }
    values = initial_live_values({"dwell": dwell})
    assert (values["dwell.pointer_signal"], values["dwell.aac_filter_samples"]) == ("assistive", 30)
    assert (values["dwell.smoothing.type"], values["dwell.smoothing.min_cutoff_hz"],
            values["dwell.smoothing.beta"]) == ("one_euro", 0.4, 6.0)
    bad = initial_live_values({"dwell": {"pointer_signal": "gaze", "smoothing": {"type": "kalman"}}})
    assert (bad["dwell.pointer_signal"], bad["dwell.smoothing.type"]) == ("best", "ema")


@pytest.mark.parametrize("task_id", TASKS)
def test_a10_an_old_profile_loads_as_best_and_ema(task_id):
    """A profile saved before these settings has none of the new keys: the test behaves as it did."""
    config = load_task_config(task_id)
    old = {"dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.1, "dwell.threshold_ms": 900}
    apply_live_values_to_config(config, old)
    values = initial_live_values(config)
    assert {k: values[k] for k in NEW_DEFAULTS} == NEW_DEFAULTS
    assert (values["dwell.smoothing.alpha"], values["dwell.threshold_ms"]) == (0.1, 900)
    live = complete_settings(task_id, load_task_config(task_id), old)["live"]
    assert {k: live[k] for k in NEW_DEFAULTS} == NEW_DEFAULTS and live["dwell.smoothing.alpha"] == 0.1


def test_the_new_keys_are_saved_in_a_profile_and_applied_from_it(tmp_path):
    new = {
        "dwell.pointer_signal": "fixation", "dwell.aac_filter_samples": 40,
        "dwell.smoothing.type": "one_euro", "dwell.smoothing.min_cutoff_hz": 0.5,
        "dwell.smoothing.beta": 3.0,
    }
    save_settings_profile(tmp_path, "S1", "click_grid", new, {})
    stored = load_settings_profile(tmp_path, "S1", "click_grid")["live"]
    assert stored == new
    config = load_task_config("click_grid")
    apply_live_values_to_config(config, stored)
    assert config["dwell"]["pointer_signal"] == "fixation"
    assert config["dwell"]["smoothing"]["type"] == "one_euro"
    assert {k: initial_live_values(config)[k] for k in new} == new


def test_a_profile_from_a_newer_build_with_a_bad_choice_does_not_break_a_run():
    config = load_task_config("click_static")
    apply_live_values_to_config(config, {"dwell.pointer_signal": "telepathy"})
    assert initial_live_values(config)["dwell.pointer_signal"] == "best"


# -- metadata.json (4.4) --------------------------------------------------------------------------


def test_the_run_snapshot_records_the_signal_and_filter_and_nulls_the_window_unless_assistive():
    config = load_task_config("click_grid")
    live = run_settings("click_grid", config)["live"]
    assert (live["dwell.pointer_signal"], live["dwell.aac_filter_samples"]) == ("best", None)
    assert (live["dwell.smoothing.type"], live["dwell.smoothing.min_cutoff_hz"],
            live["dwell.smoothing.beta"]) == ("ema", 0.3, 5.0)
    apply_live_values_to_config(config, {"dwell.pointer_signal": "assistive", "dwell.aac_filter_samples": 22})
    live = run_settings("click_grid", config)["live"]
    assert (live["dwell.pointer_signal"], live["dwell.aac_filter_samples"]) == ("assistive", 22)
    # The page's own snapshot keeps the number whatever the signal (it is a control's value).
    config["dwell"]["pointer_signal"] = "fixation"
    assert settings_snapshot("click_grid", config)["live"]["dwell.aac_filter_samples"] == 22


# -- the page (4.8) ---------------------------------------------------------------------------------


def _rect(w, h):
    return SimpleNamespace(width=lambda: w, height=lambda: h, x=lambda: 0, y=lambda: 0)


SCREEN = SimpleNamespace(
    geometry=lambda: _rect(1920, 1080),
    availableGeometry=lambda: _rect(1920.0, 1000.0),
    devicePixelRatio=lambda: 1.0,
    physicalSize=lambda: _rect(531.4, 298.9),
)


def page_for(task_id="click_grid", *, live=None, **structural):
    page = TaskConfigPage(task_id, load_task_config(task_id), screen=SCREEN)
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name=f"{task_id} 1", live=live, structural=structural or None)
    return page


def active(page, key):
    return control(page, key).isEnabled()


def states(page):
    return {key: active(page, key) for key in CARD}


@pytest.mark.parametrize("task_id", ["click_static", "follow_moving", "choice_making"])
def test_a_new_page_opens_at_best_and_simple_with_only_the_matching_rows_active(qapp, task_id):
    page = page_for(task_id)
    values = page.collect_values()["live"]
    assert {k: values[k] for k in NEW_DEFAULTS} == NEW_DEFAULTS
    assert states(page) == {
        "dwell.pointer_signal": True, "dwell.aac_filter_samples": False,
        "dwell.smoothing.enabled": True, "dwell.smoothing.type": True,
        "dwell.smoothing.alpha": True, "dwell.smoothing.min_cutoff_hz": False,
        "dwell.smoothing.beta": False,
    }


def test_choosing_assistive_wakes_the_aac_length_and_only_that(qapp):
    page = page_for()
    control(page, "dwell.pointer_signal").setValue("assistive")
    assert active(page, "dwell.aac_filter_samples") and not active(page, "dwell.smoothing.min_cutoff_hz")
    control(page, "dwell.pointer_signal").setValue("fixation")
    assert not active(page, "dwell.aac_filter_samples")


def test_choosing_adaptive_swaps_alpha_for_steadiness_and_responsiveness(qapp):
    page = page_for()
    control(page, "dwell.smoothing.type").setValue("one_euro")
    assert not active(page, "dwell.smoothing.alpha")
    assert active(page, "dwell.smoothing.min_cutoff_hz") and active(page, "dwell.smoothing.beta")
    control(page, "dwell.smoothing.type").setValue("ema")
    assert active(page, "dwell.smoothing.alpha") and not active(page, "dwell.smoothing.beta")


def test_unticking_smoothing_greys_all_three_numbers_but_not_the_type(qapp):
    page = page_for(live={"dwell.smoothing.type": "one_euro"})
    assert active(page, "dwell.smoothing.min_cutoff_hz")
    control(page, "dwell.smoothing.enabled").setChecked(False)
    assert not any(active(page, k) for k in CARD[4:])
    assert active(page, "dwell.smoothing.type") and active(page, "dwell.pointer_signal")
    control(page, "dwell.smoothing.enabled").setChecked(True)
    assert active(page, "dwell.smoothing.min_cutoff_hz") and not active(page, "dwell.smoothing.alpha")


def test_a_mouse_pointer_greys_the_whole_card_and_gaze_gives_back_exactly_the_matching_rows(qapp):
    page = page_for(live={"dwell.pointer_signal": "assistive", "dwell.smoothing.type": "one_euro"})
    before = states(page)
    assert before["dwell.aac_filter_samples"] and before["dwell.smoothing.beta"]
    control(page, "input.pointer").setValue("mouse")
    assert not any(states(page).values())
    assert not control(page, "dwell.smoothing.type").isHidden()  # greyed in place, never hidden
    control(page, "input.pointer").setValue("gaze")
    assert states(page) == before


def test_the_label_of_a_greyed_row_greys_with_its_slider(qapp):
    page = page_for()
    # The AAC length is greyed for `best`: its label is one of the widgets the rule names.
    widgets = [w for key, value, ws in page._form.greyed_when
               if key == "dwell.pointer_signal" and value == "best" for w in ws]
    assert control(page, "dwell.aac_filter_samples") in widgets and len(widgets) == 2
    assert all(not w.isEnabled() for w in widgets)


def test_the_page_round_trips_the_new_values(qapp):
    live = {
        "dwell.pointer_signal": "fixation", "dwell.aac_filter_samples": 40,
        "dwell.smoothing.type": "one_euro", "dwell.smoothing.min_cutoff_hz": 0.5,
        "dwell.smoothing.beta": 3.0,
    }
    page = page_for(live=live)
    got = page.collect_values()["live"]
    assert {k: got[k] for k in live} == live
    page.load_values(test_name="again", live={})  # a stored test without the keys
    assert {k: page.collect_values()["live"][k] for k in NEW_DEFAULTS} == NEW_DEFAULTS
