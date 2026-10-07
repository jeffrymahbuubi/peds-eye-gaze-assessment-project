"""SPEC-compass-task-flow.md 4B.4, plan step 7, acceptance AB3, AB8, AB9, AB12 (via the
dashboard), AB19: Configure Test inside ``DashboardWindow`` -- opening the page, Save &
Continue and its questions, Cancel (offscreen Qt, a scratch folder, no tracker). Preview is
in ``test_config_preview.py``."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.ui.config_flow as flow_module
from src.engine.calibration import CalibrationResult
from src.engine.config import load_task_config
from src.engine.settings_profile import (
    PROFILE_SCHEMA_VERSION,
    list_named_configurations,
    list_settings_profiles,
    load_settings_profile_file,
    save_settings_profile,
)
from src.engine.subject_tests import TestStoreError, record_result, update_test
from src.ui.config_flow import LOCKED_NOTE
from src.ui.config_save_dialogs import CANCEL, NEW_NAME, NEW_NAME_INTRO, STANDARD_INTRO, UPDATE
from src.ui.dashboard_flow import TESTS_INDEX, Flow
from src.ui.settings_snapshot import complete_settings, settings_snapshot
from src.ui.task_config_page import TaskConfigPage
from tests.dashboard_fixtures import (
    SUBJECT,
    Answers,
    close_window,
    control,
    make_window,
    new_test,
    open_page,
    stored,
    tree,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    yield window
    close_window(window)


# -- opening the page ----------------------------------------------------------------------------------


def test_configure_puts_the_page_on_top_with_the_nav_locked(win):
    test = new_test(win)
    page = open_page(win, test)
    assert isinstance(page, TaskConfigPage) and win.stack.currentWidget() is page
    assert win.stack.count() == 3  # the two tabs and the page
    assert not any(b.isEnabled() for b in win.title_bar.buttons)
    assert not win.title_bar.isHidden()  # the title bar stays for a page; only a canvas hides it
    assert page.title_label.text() == "Grid Click 1 Configuration"
    assert page.subtitle_label.text() == "Grid Click · Subject TESTING"


def test_a_new_test_opens_at_standard_with_the_task_defaults(win):
    # AB3 through the dashboard: nothing carries over from anywhere (U13).
    page = open_page(win, new_test(win))
    config = load_task_config("click_grid")
    assert page.loaded_config_name() == "Standard"
    assert page.collect_values() == settings_snapshot("click_grid", config)
    assert not page.is_dirty() and not page.is_modified()
    assert control(page, "dwell.smoothing.alpha").value() == pytest.approx(0.22)


def test_the_page_shows_the_tests_own_snapshot_notes_and_name(win):
    test = new_test(win)
    config = load_task_config("click_grid")
    values = complete_settings("click_grid", config, {"dwell.threshold_ms": 1300}, {"target": {"size": "large"}})
    update_test(win.output_root, SUBJECT, test.test_id,
                configuration={"name": "Slow dwell", **values}, notes="tired after lunch")
    page = open_page(win, test)
    assert control(page, "dwell.threshold_ms").value() == 1300
    assert control(page, "target.size").value() == "large"
    assert page.loaded_config_name() == "Slow dwell"
    assert page._form.notes_edit.toPlainText() == "tired after lunch"
    assert page._form.test_name_edit.text() == "Grid Click 1"
    assert not page.is_dirty()


def test_the_configuration_name_list_is_this_subjects_saved_names_newest_first(win):
    test = new_test(win)
    page = open_page(win, test)
    combo = page._form.config_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["Standard"]
    page.cancelRequested.emit()
    other = settings_snapshot("click_grid", load_task_config("click_grid"))
    save_settings_profile(win.output_root, SUBJECT, "click_grid", other["live"], other["structural"], None, "Large targets")
    save_settings_profile(win.output_root, "OTHERKID", "click_grid", other["live"], other["structural"], None, "Not mine")
    page = open_page(win, test)
    combo = page._form.config_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["Standard", "Large targets"]


def test_another_subjects_configuration_is_never_offered(win):
    snap = settings_snapshot("click_grid", load_task_config("click_grid"))
    save_settings_profile(win.output_root, "OTHERKID", "click_grid", snap["live"], snap["structural"], None, "Theirs")
    combo = open_page(win, new_test(win))._form.config_combo
    assert "Theirs" not in [combo.itemText(i) for i in range(combo.count())]


def test_a_locked_test_cannot_be_configured(win):
    test = new_test(win)
    folder = Path(win.output_root) / "2026-10-06_TESTING_click_grid_run1"
    folder.mkdir(parents=True)
    record_result(win.output_root, SUBJECT, test.test_id, session_dir=folder, planned_trials=3, completed_trials=3)
    win.config_flow.open(test.test_id)
    assert win.flow is Flow.IDLE and win.config_flow.page is None
    assert win.test_list_page.message_label.text() == LOCKED_NOTE


def test_a_missing_test_is_reported_and_the_list_reloaded(win):
    win.config_flow.open("t_0123456789")
    assert win.flow is Flow.IDLE
    assert "could not be found" in win.test_list_page.message_label.text()


def test_configure_is_ignored_while_another_flow_is_active(win):
    test = new_test(win)
    open_page(win, test)
    first = win.config_flow.page
    win.config_flow.open(test.test_id)
    assert win.config_flow.page is first and win.stack.count() == 3


# -- Save & Continue: Standard, untouched ------------------------------------------------------------------------------------


def test_saving_standard_untouched_stores_the_complete_snapshot_and_writes_no_profile(win):
    test = new_test(win)
    page = open_page(win, test)
    page.save_button.click()
    assert win.flow is Flow.IDLE and win.config_flow.page is None
    assert win.stack.currentIndex() == TESTS_INDEX and win.stack.count() == 2
    assert all(b.isEnabled() for b in win.title_bar.buttons)
    config = load_task_config("click_grid")
    expected = complete_settings("click_grid", config)
    saved = stored(win, test.test_id)
    assert saved.configuration == {"name": "Standard", **expected}
    assert not (Path(win.output_root) / "_settings").exists()  # no file for Standard
    assert win.test_list_page.selected_test().test_id == test.test_id


def test_the_stored_snapshot_is_complete_and_has_no_theme_or_particles(win):
    # HB12 / the P5 carry-forward: complete_settings (task-applicable keys), never run_settings.
    test = new_test(win, "follow_moving")
    page = open_page(win, test)
    page.save_button.click()
    cfg = stored(win, test.test_id).configuration
    assert "motion.speed_frac_per_s" in cfg["live"]
    assert cfg["structural"]["motion"]["path"] == "circular"
    # The two sounds and the glow (SPEC-input-selection-and-follow.md H3); Follow has no Selection.
    assert cfg["structural"]["feedback"] == {"hit_sound": True, "miss_sound": True, "target_glow": True}
    assert cfg["structural"]["input"] == {"pointer": "gaze"}
    assert "theme" not in cfg["structural"] and "particles" not in cfg["structural"]["feedback"]


def test_saving_applies_the_name_and_the_notes(win):
    test = new_test(win)
    page = open_page(win, test)
    page._form.test_name_edit.setText("Baseline grid")
    page._form.notes_edit.setPlainText("first sitting")
    page.save_button.click()
    saved = stored(win, test.test_id)
    assert saved.name == "Baseline grid" and saved.notes == "first sitting"
    assert win.test_list_page.row_texts()[0][0] == "Baseline grid"


def test_saving_keeps_the_seed_and_the_status(win):
    test = new_test(win)
    page = open_page(win, test)
    page.save_button.click()
    saved = stored(win, test.test_id)
    assert saved.seed == test.seed and saved.status == "not_done" and saved.session_dir is None


# -- AB8: Standard + changed values ----------------------------------------------------------------------------------------------


def test_edited_standard_asks_for_a_new_name_and_writes_a_v2_profile(win):
    test = new_test(win)
    page = open_page(win, test)
    control(page, "dwell.threshold_ms").setValue(1200)
    answers = Answers(new_name="Custom 1")
    answers.install(win.config_flow)
    page.save_button.click()
    assert answers.name_asked == [(STANDARD_INTRO, "Custom 1")]
    assert STANDARD_INTRO == "Standard cannot be changed. Save these settings as:"
    (path,) = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    profile = load_settings_profile_file(path)
    assert profile["name"] == "Custom 1" and profile["schema_version"] == PROFILE_SCHEMA_VERSION == 2
    assert profile["live"]["dwell.threshold_ms"] == 1200
    assert profile["subject_id"] == SUBJECT and profile["task_id"] == "click_grid"
    saved = stored(win, test.test_id)
    assert saved.configuration["name"] == "Custom 1"
    assert saved.configuration["live"]["dwell.threshold_ms"] == 1200
    assert saved.configuration["live"] == profile["live"]
    assert saved.configuration["structural"] == profile["structural"]
    assert win.flow is Flow.IDLE


def test_the_default_for_the_new_name_skips_names_in_use(win):
    snap = settings_snapshot("click_grid", load_task_config("click_grid"))
    save_settings_profile(win.output_root, SUBJECT, "click_grid", snap["live"], snap["structural"], None, "Custom 1")
    page = open_page(win, new_test(win))
    control(page, "dwell.threshold_ms").setValue(1100)
    answers = Answers(new_name=None)
    answers.install(win.config_flow)
    page.save_button.click()
    assert answers.name_asked == [(STANDARD_INTRO, "Custom 2")]


def test_cancelling_the_new_name_stays_on_the_page_and_writes_nothing(win):
    test = new_test(win)
    page = open_page(win, test)
    control(page, "dwell.threshold_ms").setValue(1200)
    before = tree(Path(win.output_root))
    Answers(new_name=None).install(win.config_flow)
    page.save_button.click()
    assert win.flow is Flow.CONFIGURE and win.config_flow.page is page
    assert tree(Path(win.output_root)) == before
    assert stored(win, test.test_id).configuration == {"name": "Standard", "structural": {}, "live": {}}


def test_a_new_name_typed_in_the_box_writes_a_profile_without_asking(win):
    test = new_test(win)
    page = open_page(win, test)
    page._form.config_combo.setEditText("Large targets")
    control(page, "target.size").setValue("large")
    answers = Answers()
    answers.install(win.config_flow)
    page.save_button.click()
    assert not answers.name_asked and not answers.update_asked
    (named,) = list_named_configurations(win.output_root, SUBJECT, "click_grid")
    assert named.name == "Large targets" and named.structural["target"]["size"] == "large"
    assert stored(win, test.test_id).configuration["name"] == "Large targets"


def test_the_profile_records_the_calibration_it_was_tuned_under(win):
    win.setup_page._calibration_result = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
    page = open_page(win, new_test(win))
    page._form.config_combo.setEditText("With calibration")
    page.save_button.click()
    (path,) = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    assert load_settings_profile_file(path)["calibration"] == {"error_px": 12.3, "points": 5}


def test_without_a_calibration_the_profile_has_none(win):
    assert win.setup_page.calibration_result is None
    page = open_page(win, new_test(win))
    page._form.config_combo.setEditText("No calibration")
    page.save_button.click()
    (path,) = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    assert load_settings_profile_file(path)["calibration"] == {}


# -- AB9: a name that exists --------------------------------------------------------------------------------------------------------


def save_named(win, name, **live):
    """A saved configuration for TESTING / click_grid with some live values changed."""
    snap = settings_snapshot("click_grid", load_task_config("click_grid"))
    save_settings_profile(win.output_root, SUBJECT, "click_grid", {**snap["live"], **live}, snap["structural"], None, name)


def pick(page, name):
    combo = page._form.config_combo
    index = combo.findText(name)
    combo.setCurrentIndex(index)
    page._on_config_activated(index)


def test_an_existing_name_with_different_values_asks_and_update_adds_a_new_version(win):
    save_named(win, "Large targets", **{"dwell.threshold_ms": 1000})
    time.sleep(1.1)  # versions are told apart by saved_at, in whole seconds
    test = new_test(win)
    page = open_page(win, test)
    pick(page, "Large targets")
    control(page, "dwell.threshold_ms").setValue(1700)
    before = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    answers = Answers(update=UPDATE)
    answers.install(win.config_flow)
    page.save_button.click()
    assert answers.update_asked == ["Large targets"]
    after = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    assert len(after) == len(before) + 1 and set(before) <= set(after)  # the old file is still there
    (named,) = list_named_configurations(win.output_root, SUBJECT, "click_grid")  # one entry for the name
    assert named.name == "Large targets" and named.live["dwell.threshold_ms"] == 1700
    assert stored(win, test.test_id).configuration["live"]["dwell.threshold_ms"] == 1700


def test_an_existing_name_with_the_same_values_needs_no_question_or_file(win):
    save_named(win, "Large targets", **{"dwell.threshold_ms": 1000})
    page = open_page(win, new_test(win))
    pick(page, "Large targets")
    before = list_settings_profiles(win.output_root, SUBJECT, "click_grid")
    answers = Answers()
    answers.install(win.config_flow)
    page.save_button.click()
    assert not answers.update_asked and not answers.name_asked
    assert list_settings_profiles(win.output_root, SUBJECT, "click_grid") == before
    assert win.flow is Flow.IDLE


def test_save_under_a_new_name_asks_for_one_and_leaves_the_old_configuration(win):
    save_named(win, "Large targets", **{"dwell.threshold_ms": 1000})
    page = open_page(win, new_test(win))
    pick(page, "Large targets")
    control(page, "dwell.threshold_ms").setValue(1700)
    answers = Answers(new_name="Large and slow", update=NEW_NAME)
    answers.install(win.config_flow)
    page.save_button.click()
    assert answers.name_asked == [(NEW_NAME_INTRO, "Custom 1")]
    names = {c.name: c for c in list_named_configurations(win.output_root, SUBJECT, "click_grid")}
    assert names["Large targets"].live["dwell.threshold_ms"] == 1000  # untouched
    assert names["Large and slow"].live["dwell.threshold_ms"] == 1700


def test_a_new_name_that_already_exists_is_decided_again(win):
    save_named(win, "Large targets", **{"dwell.threshold_ms": 1000})
    save_named(win, "Other", **{"dwell.threshold_ms": 900})
    page = open_page(win, new_test(win))
    pick(page, "Large targets")
    control(page, "dwell.threshold_ms").setValue(1700)
    # "Save under a new name", typing the name of another saved configuration: it exists
    # with other values, so the update question comes back (for "Other"); Cancel ends it.
    answers = Answers(new_name="other", update=[NEW_NAME, CANCEL])
    answers.install(win.config_flow)
    page.save_button.click()
    assert answers.update_asked == ["Large targets", "Other"]  # the saved spelling is used
    assert win.flow is Flow.CONFIGURE
    names = {c.name: c for c in list_named_configurations(win.output_root, SUBJECT, "click_grid")}
    assert names["Other"].live["dwell.threshold_ms"] == 900  # nothing was written


def test_cancel_in_the_update_question_stays_on_the_page(win):
    save_named(win, "Large targets", **{"dwell.threshold_ms": 1000})
    test = new_test(win)
    page = open_page(win, test)
    pick(page, "Large targets")
    control(page, "dwell.threshold_ms").setValue(1700)
    before = tree(Path(win.output_root))
    Answers(update=CANCEL).install(win.config_flow)
    page.save_button.click()
    assert win.flow is Flow.CONFIGURE and tree(Path(win.output_root)) == before
    assert stored(win, test.test_id).configuration["name"] == "Standard"


# -- AB19 and failures -------------------------------------------------------------------------------------------------------------------


def test_saving_a_test_that_has_run_since_writes_nothing_and_says_so(win):
    test = new_test(win)
    page = open_page(win, test)
    folder = Path(win.output_root) / "2026-10-06_TESTING_click_grid_run1"
    folder.mkdir(parents=True)
    record_result(win.output_root, SUBJECT, test.test_id, session_dir=folder, planned_trials=3, completed_trials=3)
    control(page, "dwell.threshold_ms").setValue(1500)
    page._form.config_combo.setEditText("Late edit")
    before = tree(Path(win.output_root))
    page.save_button.click()
    assert page.footer_message.text() == LOCKED_NOTE == "This test has already been run and can't be changed."
    assert win.flow is Flow.CONFIGURE and tree(Path(win.output_root)) == before
    saved = stored(win, test.test_id)
    assert saved.status == "done" and saved.configuration["name"] == "Standard"


def test_a_test_name_used_by_another_test_is_refused_by_the_flow_too(win):
    new_test(win, name="Taken")
    test = new_test(win)
    page = open_page(win, test)
    page._form.test_name_edit.setText("taken")
    before = tree(Path(win.output_root))
    win.config_flow._on_save(page.collect_entry())  # the page itself disables Save for this
    assert "already exists" in page.footer_message.text()
    assert win.flow is Flow.CONFIGURE and tree(Path(win.output_root)) == before


def test_a_failed_write_says_so_and_keeps_the_page(win, monkeypatch):
    test = new_test(win)
    page = open_page(win, test)
    page._form.notes_edit.setPlainText("notes")

    def broken(*args, **kwargs):
        raise TestStoreError("Could not save t_x.json: Access is denied")

    monkeypatch.setattr(flow_module, "update_test", broken)
    page.save_button.click()
    assert page.footer_message.text() == "Could not save: Could not save t_x.json: Access is denied"
    assert win.flow is Flow.CONFIGURE and win.config_flow.page is page
    assert stored(win, test.test_id).notes == ""


def test_a_failed_profile_write_leaves_the_test_untouched(win, monkeypatch):
    test = new_test(win)
    page = open_page(win, test)
    page._form.config_combo.setEditText("Will fail")

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(flow_module, "save_settings_profile", broken)
    page.save_button.click()
    assert page.footer_message.text() == "Could not save: disk full"
    assert stored(win, test.test_id).configuration["name"] == "Standard"
    assert win.flow is Flow.CONFIGURE


# -- Cancel ------------------------------------------------------------------------------------------------------------------------------------


def test_cancel_without_edits_returns_at_once_and_writes_nothing(win):
    test = new_test(win)
    page = open_page(win, test)
    before = tree(Path(win.output_root))
    page.cancel_button.click()
    assert win.flow is Flow.IDLE and win.config_flow.page is None and win.stack.count() == 2
    assert win.stack.currentIndex() == TESTS_INDEX
    assert tree(Path(win.output_root)) == before
    assert win.test_list_page.selected_test().test_id == test.test_id


def test_cancel_with_edits_asks_and_discards(win):
    test = new_test(win)
    page = open_page(win, test)
    control(page, "dwell.threshold_ms").setValue(1900)
    asked = []
    page._ask = lambda *args, **kwargs: asked.append(args[0]) or True  # "Discard"
    page.cancel_button.click()
    assert asked == ["Discard changes"] and win.flow is Flow.IDLE
    assert stored(win, test.test_id).configuration == {"name": "Standard", "structural": {}, "live": {}}


def test_keep_editing_stays_on_the_page(win):
    page = open_page(win, new_test(win))
    control(page, "dwell.threshold_ms").setValue(1900)
    page._ask = lambda *args, **kwargs: False
    page.cancel_button.click()
    assert win.flow is Flow.CONFIGURE and control(page, "dwell.threshold_ms").value() == 1900


# -- the page builds on the monitor it is on ----------------------------------------------------------------------------------------------------------------


def test_the_page_is_built_with_the_windows_screen(win, monkeypatch):
    seen = {}
    real = flow_module.TaskConfigPage

    def spy(task_id, config, *, screen=None, parent=None):
        seen["screen"] = screen
        return real(task_id, config, screen=screen, parent=parent)

    monkeypatch.setattr(flow_module, "TaskConfigPage", spy)
    marker = win.screen()
    open_page(win, new_test(win))
    assert seen["screen"] is marker


def test_json_of_a_saved_test_has_the_name_and_the_complete_values(win):
    test = new_test(win)
    page = open_page(win, test)
    page._form.config_combo.setEditText("Check the file")
    control(page, "grid.rows").setValue(4)
    page.save_button.click()
    path = Path(win.output_root) / "_tests" / SUBJECT / f"{test.test_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["configuration"]["name"] == "Check the file"
    assert record["configuration"]["structural"]["grid"]["rows"] == 4
    assert record["configuration"]["live"]["dwell.threshold_ms"] == 800
