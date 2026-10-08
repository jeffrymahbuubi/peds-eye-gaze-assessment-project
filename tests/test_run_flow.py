"""SPEC-compass-task-flow.md 4C.1-4C.5, R2, R11, HC8, acceptance AC1-AC5 on the dashboard
side (P8b): Run Test opens the Start page, Practice, and the recorded run's launch, from
the test record. Offscreen Qt, a scratch folder, a mouse for the tracker; nothing is
launched and no device is touched. The end of a recorded run is in ``test_run_flow_end.py``."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.ui.run_flow as run_flow_module
from src.engine.run_mode import PRACTICE_SEED_BASE
from src.engine.run_paths import new_run_dir
from src.engine.subject_tests import STATUS_DONE, create_test, record_result
from src.ui.dashboard_flow import SETUP_INDEX, TESTS_INDEX, Flow
from tests.dashboard_fixtures import new_test, tree
from tests.run_flow_fixtures import (
    SUBJECT,
    close_run_window,
    configure_fast,
    finish_trials,
    make_run_window,
    open_start,
    run_dirs,
    start_run,
    stored_tests,
    tick_until,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    yield win, mouse, pointing
    close_run_window(win)


def only_test(win):
    (test,) = stored_tests(win)
    return test


def files_under(root):
    return {p: p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


def nav_locked(win):
    return not any(b.isEnabled() for b in win.title_bar.buttons)


# -- Run Test opens the Start page, always (R2, AC1-AC3) -------------------------------------------------


def test_run_test_opens_the_start_page_for_the_test(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    assert win.flow is Flow.START and win.stack.currentWidget() is page and win.stack.count() == 3
    assert page.title_label.text() == "Start Grid Click 1"
    assert page.instructions.heading == "Instructions for the Grid Click test:"
    assert nav_locked(win) and not win.title_bar.isHidden()
    assert page._blockers_provider is win.setup_page.run_blockers


def test_the_start_page_instructions_follow_the_tests_own_settings(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=12)
    page = open_start(win, test)
    assert any("0.3 seconds" in step for step in page.instructions.steps)
    assert any("12 trials" in line for line in page.instructions.clinician)


def test_blockers_are_listed_and_disable_start_and_practice_but_run_test_still_opens(rig):
    win, _mouse, _pointing = rig
    reasons = ["The tracker is not connected. Connect it on the Setup page.", "No calibration yet."]
    win.blockers[:] = reasons
    page = open_start(win, new_test(win))  # not a silent no-op (R2)
    assert not page.banner.isHidden()
    assert all(reason in page.banner_label.text() for reason in reasons)
    assert not page.start_button.isEnabled() and not page.practice_button.isEnabled()
    assert page.cancel_button.isEnabled()


def test_a_stale_enabled_start_button_still_cannot_launch(rig):
    win, _mouse, _pointing = rig
    page = open_start(win, new_test(win))
    win.blockers[:] = ["The tracker is not connected."]  # dropped since the page was shown
    page.start_button.setEnabled(True)
    page.practice_button.setEnabled(True)
    page.start_button.click()
    page.practice_button.click()
    assert win.run_flow.app is None and win.flow is Flow.START


def test_cancel_returns_to_the_list_and_changes_nothing(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    before, listing = files_under(win.output_root), tree(Path(win.output_root))
    page = open_start(win, test)
    page.cancel_button.click()
    assert win.flow is Flow.IDLE and win.stack.currentIndex() == TESTS_INDEX and win.stack.count() == 2
    assert win.run_flow.page is None and win.test_list_page.selected_test().test_id == test.test_id
    assert files_under(win.output_root) == before and tree(Path(win.output_root)) == listing
    assert not nav_locked(win) and not win.title_bar.isHidden()


def test_escape_is_cancel(rig):
    win, _mouse, _pointing = rig
    page = open_start(win, new_test(win))
    page._cancel_shortcut.activated.emit()
    assert win.flow is Flow.IDLE and win.stack.count() == 2


def test_go_to_setup_leaves_for_the_setup_tab(rig):
    win, _mouse, _pointing = rig
    page = open_start(win, new_test(win))
    page.go_to_setup_button.click()
    assert win.flow is Flow.IDLE and win.stack.currentIndex() == SETUP_INDEX and win.stack.count() == 2
    assert not nav_locked(win) and bool(win.title_bar.setup_button.property("active"))


def test_the_nav_is_locked_on_the_start_page_in_practice_and_in_a_run(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    open_start(win, test)
    win._go_to_tab(SETUP_INDEX)
    assert nav_locked(win) and win.stack.currentWidget() is win.run_flow.page  # AC3
    app = start_run(win, mouse, "practice_button")
    win._go_to_tab(SETUP_INDEX)
    assert nav_locked(win) and win.stack.currentWidget() is app.view
    app.view.run_bar.quit_requested.emit()
    win.run_flow.page.start_button.click()
    app = win.run_flow.app
    app.timer.stop()
    win._go_to_tab(SETUP_INDEX)
    assert win.flow is Flow.RUN and nav_locked(win) and win.stack.currentWidget() is app.view


def test_a_done_test_cannot_be_run(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    folder = new_run_dir(win.output_root, SUBJECT, "click_grid")
    record_result(win.output_root, SUBJECT, test.test_id, session_dir=folder, planned_trials=6, completed_trials=6)
    win.run_flow.open(test.test_id)
    assert win.flow is Flow.IDLE and "already been run" in win.test_list_page.message_label.text()


def test_an_unknown_test_reloads_the_list(rig):
    win, _mouse, _pointing = rig
    win.run_flow.open("t_0000000000")
    assert win.flow is Flow.IDLE
    assert win.test_list_page.message_label.text() == "That test could not be found. The list was reloaded."


def test_run_test_is_ignored_while_another_flow_is_open(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    win.run_flow.open(test.test_id)
    assert win.run_flow.page is page and win.stack.count() == 3


# -- Practice (AC4, AC5) ------------------------------------------------------------------------------------------


def test_practice_is_a_practice_run_of_the_tests_own_configuration_with_at_most_3_trials(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=18, target={"size": "large"})
    before = copy.deepcopy(only_test(win).configuration)
    open_start(win, test)
    app = start_run(win, mouse, "practice_button")
    assert app.run_mode == "practice" and len(app.task.targets) == 3  # min(3, 18)
    assert app.config["task"]["target"]["size"] == "large"
    assert app._live_values["dwell.threshold_ms"] == 300
    assert app.metadata.test_id is None and app.recorder.session_dir is None
    assert win.run_flow.test.configuration == before  # the test's own dicts are never mutated
    assert only_test(win).configuration == before


def test_practice_of_a_short_test_has_that_many_trials(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=2)
    open_start(win, test)
    assert len(start_run(win, mouse, "practice_button").task.targets) == 2


def test_practice_of_an_unconfigured_standard_test_has_3_trials(rig):
    win, mouse, _pointing = rig
    open_start(win, new_test(win))
    assert len(start_run(win, mouse, "practice_button").task.targets) == 3


def test_practice_hides_the_title_bar_and_locks_the_nav(rig):
    win, mouse, _pointing = rig
    open_start(win, new_test(win))
    app = start_run(win, mouse, "practice_button")
    assert win.flow is Flow.PRACTICE and win.stack.currentWidget() is app.view
    assert win.title_bar.isHidden() and nav_locked(win)
    app._tick()
    assert app.view.run_bar.status_text().startswith("PRACTICE")


def test_each_practice_press_gets_its_own_number_and_seed(rig):
    win, mouse, _pointing = rig
    open_start(win, new_test(win))
    seeds = []
    for _ in range(3):
        app = start_run(win, mouse, "practice_button")
        seeds.append(app.metadata.seed)
        app.view.run_bar.quit_requested.emit()  # no question in a practice (HC12)
        assert win.flow is Flow.START
    assert seeds == [PRACTICE_SEED_BASE, PRACTICE_SEED_BASE + 1, PRACTICE_SEED_BASE + 2]


def test_a_new_start_page_counts_its_practices_from_zero_again(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    open_start(win, test)
    start_run(win, mouse, "practice_button").view.run_bar.quit_requested.emit()
    win.run_flow.page.cancel_button.click()
    open_start(win, test)
    assert start_run(win, mouse, "practice_button").metadata.seed == PRACTICE_SEED_BASE


def test_a_finished_practice_returns_to_the_start_page_with_its_result_line(rig):
    win, mouse, pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=2)
    page = open_start(win, test)
    app = start_run(win, mouse, "practice_button")
    finish_trials(app, pointing)
    assert win.flow is Flow.START and win.stack.currentWidget() is page and win.stack.count() == 3
    assert win.run_flow.app is None  # the view is gone
    assert not page.practice_label.isHidden()
    assert page.practice_label.text() == "Practice finished: 2 of 2 selected. You can practice again or press Start."
    assert not win.title_bar.isHidden() and nav_locked(win)  # the bar is back; the Start page owns the window


def test_a_quit_practice_returns_at_once_with_no_line(rig):
    win, mouse, pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=3)
    page = open_start(win, test)
    app = start_run(win, mouse, "practice_button")
    finish_trials(app, pointing)  # a first practice, finished: the line shows
    assert not page.practice_label.isHidden()
    app = start_run(win, mouse, "practice_button")
    app._tick()
    app.view.run_bar.quit_requested.emit()
    assert win.flow is Flow.START and win.stack.currentWidget() is page
    assert page.practice_label.isHidden()  # a quit practice says nothing


def test_practice_writes_nothing_under_the_output_root(rig):
    win, mouse, pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=2)
    root = Path(win.output_root)
    before, listing = files_under(root), tree(root)
    open_start(win, test)
    app = start_run(win, mouse, "practice_button")
    finish_trials(app, pointing)
    assert files_under(root) == before and tree(root) == listing  # no run folder, calibration.json or diagnostics
    assert not (root / "_system").exists() and not run_dirs(win)
    assert only_test(win).status == "not_done"


def test_practice_uses_another_seed_so_its_targets_differ_from_the_recorded_run(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    record = Path(win.output_root) / SUBJECT / "tests" / f"{test.test_id}.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    data["seed"] = 7  # a fixed seed, so the comparison below cannot be a coincidence
    record.write_text(json.dumps(data), encoding="utf-8")
    open_start(win, test)
    practice = start_run(win, mouse, "practice_button")
    practiced = [t.slot_index for t in practice.task.targets]
    practice.view.run_bar.quit_requested.emit()
    recorded = start_run(win, mouse, "start_button")
    assert recorded.metadata.seed == 7 and practice.metadata.seed != 7
    assert [t.slot_index for t in recorded.task.targets][:3] != practiced


# -- the recorded run is built from the test record (4A.7, R3) ------------------------------------


def test_start_builds_a_recorded_run_from_the_test_record(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=5, name="Quick look", target={"size": "large"})
    test = only_test(win)
    open_start(win, test)
    app = start_run(win, mouse)
    meta = app.metadata
    assert app.run_mode == "record" and win.flow is Flow.RUN
    assert (meta.test_id, meta.test_name, meta.seed) == (test.test_id, test.name, test.seed)
    assert meta.subject_id == test.subject_id and meta.config_name == "Quick look"
    assert meta.settings["config_name"] == "Quick look"
    assert app.config["task"]["trials"] == 5 and app.config["task"]["target"]["size"] == "large"
    assert app._live_values["dwell.threshold_ms"] == 300
    assert app.client is mouse and app._owns_client is False  # the Setup tab's tracker, never stopped
    assert meta.calibration_points == 5 and meta.calibration_error_px == 10.0
    run = app.recorder.session_dir  # L1: <root>/<subject folder>/runs/<task_id>/<YYYY-MM-DD_HHMM>
    assert run.is_dir() and run.parent == Path(win.output_root) / SUBJECT / "runs" / "click_grid"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}(_\d+)?", run.name)
    assert meta.session_id == f"click_grid_{run.name}_{test.test_id}"  # H3: no subject in it


def test_the_recorded_run_hides_the_title_bar_and_locks_the_nav(rig):
    win, mouse, _pointing = rig
    open_start(win, new_test(win))
    app = start_run(win, mouse)
    assert win.stack.currentWidget() is app.view and win.stack.indexOf(win.run_flow.page) >= 0
    assert win.title_bar.isHidden() and nav_locked(win)
    app._tick()
    assert app.view.run_bar.status_text().startswith("Trial 1 of ")  # no practice marker


def test_an_unconfigured_standard_test_runs_with_the_task_defaults(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    open_start(win, test)
    app = start_run(win, mouse)
    assert test.configuration == {"name": "Standard", "structural": {}, "live": {}}
    assert app.metadata.config_name == "Standard" and len(app.task.targets) == 18


def test_the_run_takes_the_setup_pages_session_fields(rig):
    win, mouse, _pointing = rig
    win.setup_page.notes_edit.setPlainText("quiet room")
    open_start(win, new_test(win))
    app = start_run(win, mouse)
    assert app.metadata.notes == "quiet room"
    assert app.metadata.assessment_date == win.setup_page.assessment_date()


def assert_still_on_the_start_page(win, page, text):
    """A run that could not start leaves the operator where they were, nav locked, with the reason."""
    assert win.flow is Flow.START and win.stack.currentWidget() is page and win.stack.count() == 3
    assert win.run_flow.app is None and win.run_flow.page is page
    assert not page.message_label.isHidden() and page.message_label.text() == text
    assert nav_locked(win) and not win.title_bar.isHidden()
    assert win.test_list_page.message_label.text() == ""  # nothing was said on the list


def test_start_is_refused_when_the_subject_id_in_setup_changed(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    win.setup_page.subject_id_edit.setText("SOMEONE ELSE")
    page.start_button.click()
    assert_still_on_the_start_page(
        win, page, "Could not start Grid Click 1: the Subject ID in Setup is no longer TESTING."
    )
    assert only_test(win).status == "not_done" and run_dirs(win) == []
    page.practice_button.click()  # Practice is refused for the same reason
    assert win.run_flow.app is None and win.flow is Flow.START
    page.cancel_button.click()  # and the operator can still go back
    assert win.flow is Flow.IDLE and win.stack.count() == 2


def test_start_is_refused_when_the_test_has_run_since(rig):
    win, _mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    folder = new_run_dir(win.output_root, SUBJECT, "click_grid")
    record_result(win.output_root, SUBJECT, test.test_id, session_dir=folder, planned_trials=6, completed_trials=6)
    page.start_button.click()
    assert_still_on_the_start_page(win, page, "Could not start Grid Click 1: this test has already been run.")
    assert only_test(win).status == STATUS_DONE and len(run_dirs(win)) == 1


def test_a_run_that_cannot_start_says_so_on_the_start_page_and_can_be_retried(rig, monkeypatch):
    win, mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    real = run_flow_module.AssessmentApp

    def broken(**kwargs):
        raise OSError("disk is read-only")

    monkeypatch.setattr(run_flow_module, "AssessmentApp", broken)
    page.start_button.click()
    assert_still_on_the_start_page(win, page, "Could not start Grid Click 1: disk is read-only")
    # The operator fixes the cause and presses Start again: it runs, and the note is gone.
    monkeypatch.setattr(run_flow_module, "AssessmentApp", real)
    page.start_button.click()
    assert win.flow is Flow.RUN and page.message_label.isHidden()
    win.run_flow.app.timer.stop()


def test_a_practice_that_cannot_start_says_so_on_the_start_page_too(rig, monkeypatch):
    win, _mouse, _pointing = rig
    page = open_start(win, new_test(win))
    real = run_flow_module.AssessmentApp
    monkeypatch.setattr(run_flow_module, "AssessmentApp", lambda **kw: (_ for _ in ()).throw(ValueError("bad config")))
    page.practice_button.click()
    assert_still_on_the_start_page(win, page, "Could not start Grid Click 1: bad config")
    monkeypatch.setattr(run_flow_module, "AssessmentApp", real)
    page.practice_button.click()
    assert win.flow is Flow.PRACTICE and page.message_label.isHidden()
    win.run_flow.app.timer.stop()


def test_a_run_never_dials_the_device_when_the_setup_page_has_no_tracker(rig, monkeypatch):
    win, mouse, _pointing = rig
    page = open_start(win, new_test(win))
    win.setup_page._client = None  # the blockers are patched empty, so only the flow's own guard is left
    real = run_flow_module.AssessmentApp
    built = []
    monkeypatch.setattr(run_flow_module, "AssessmentApp", lambda **kw: built.append(kw))
    page.start_button.click()
    assert built == []
    assert_still_on_the_start_page(win, page, "Could not start Grid Click 1: the tracker is not connected.")
    win.setup_page._client = mouse  # connected again: nothing else is needed to try again
    monkeypatch.setattr(run_flow_module, "AssessmentApp", real)
    page.start_button.click()
    assert win.flow is Flow.RUN
    win.run_flow.app.timer.stop()


def test_cancel_after_a_failed_start_returns_to_the_list_with_the_test_selected(rig, monkeypatch):
    win, _mouse, _pointing = rig
    test = new_test(win)
    page = open_start(win, test)
    monkeypatch.setattr(run_flow_module, "AssessmentApp", lambda **kw: (_ for _ in ()).throw(OSError("no")))
    page.start_button.click()
    page.cancel_button.click()
    assert win.flow is Flow.IDLE and win.stack.count() == 2
    assert win.test_list_page.selected_test().test_id == test.test_id
    assert not nav_locked(win)


def test_the_launch_arguments_come_from_the_record_not_from_shared_dicts(rig, monkeypatch):
    win, mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=4)
    seen = []
    real = run_flow_module.AssessmentApp

    def spy(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(run_flow_module, "AssessmentApp", spy)
    open_start(win, test)
    start_run(win, mouse, "practice_button").view.run_bar.quit_requested.emit()
    start_run(win, mouse)
    practice, record = seen
    assert practice["run_mode"] == "practice" and practice["practice_index"] == 0
    assert record["run_mode"] == "record" and record["seed"] == only_test(win).seed
    assert record["test_id"] == test.test_id and record["test_name"] == test.name
    assert record["replay_path"] is None and record["embedded"] is True
    assert record["client"] is mouse and record["screen"] is win.screen()
    stored_config = only_test(win).configuration
    assert record["structural_overrides"] == stored_config["structural"]
    assert record["live_overrides"] == stored_config["live"]
    assert practice["structural_overrides"]["trials"] == 3 and stored_config["structural"]["trials"] == 4
    assert record["structural_overrides"] is not stored_config["structural"]  # a copy


def test_nothing_changes_on_disk_between_open_and_the_first_trial(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    before = files_under(Path(win.output_root) / SUBJECT / "tests")
    open_start(win, test)
    start_run(win, mouse)
    assert files_under(Path(win.output_root) / SUBJECT / "tests") == before  # only the run folder is new
    assert only_test(win).status == "not_done"


def test_an_unused_recorded_run_can_be_ticked_to_its_first_trial(rig):
    win, mouse, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse)
    tick_until(app, lambda: app.task.phase.name == "WAIT_INPUT")
    assert app.task.trial_number == 1


def test_a_garbage_record_in_the_subjects_folder_does_not_stop_a_run(rig):
    # AA14 through the flow: the unreadable file is skipped (the list says so), the rest works.
    win, mouse, _pointing = rig
    test = new_test(win)
    (Path(win.output_root) / SUBJECT / "tests" / "t_deadbeef00.json").write_text("{not json", encoding="utf-8")
    open_start(win, test)
    app = start_run(win, mouse)
    assert app.metadata.test_id == test.test_id and win.flow is Flow.RUN
    assert not win.test_list_page.unreadable_label.isHidden()


def test_other_subjects_tests_are_not_reachable_for_a_run(rig):
    win, _mouse, _pointing = rig
    other = create_test(win.output_root, "OTHER", "click_grid")
    win.run_flow.open(other.test_id)
    assert win.flow is Flow.IDLE and "could not be found" in win.test_list_page.message_label.text()
