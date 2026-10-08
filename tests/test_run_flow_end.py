"""SPEC-compass-task-flow.md 4C.6, 4C.8, U8, U14, HD1, acceptance AC11-AC13 and AA11 on the
dashboard side (P8b): what happens when a recorded run ends -- Save, Save and View Report,
Discard, a quit with trials done or none, and a store that refuses (the data stays on disk and
the test stays Not Done). Offscreen Qt, a scratch folder, a mouse for the tracker."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.engine.run_result as run_result_module
import src.ui.report_flow as report_flow_module
import src.ui.run_flow as run_flow_module
from src.data.report_cache import REPORT_FILENAME, ReportError
from src.engine import subject_tests as store  # by module: pytest would try to collect Test* names
from src.engine.run_paths import new_run_dir
from src.engine.run_result import DISCARD, SAVE, SAVE_AND_VIEW
from src.engine.session_files import SessionDiscardError
from src.ui.dashboard_flow import Flow
from src.ui.run_dialogs import ask_run_end
from tests.dashboard_fixtures import new_test
from tests.run_flow_fixtures import (
    SUBJECT,
    Answers,
    close_run_window,
    configure_fast,
    finish_trials,
    make_run_window,
    open_start,
    run_dirs,
    start_run,
    stored_tests,
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


def begin(win, mouse, trials=1):
    """A configured test with its Start page open and the recorded run started."""
    test = new_test(win)
    configure_fast(win, test, trials=trials)
    open_start(win, test)
    return test, start_run(win, mouse)


def quit_run(app, answer=True):
    app.confirm_quit = lambda parent, completed, planned: answer
    app.view.run_bar.quit_requested.emit()


def selected_row(win):
    page = win.test_list_page
    return page.row_texts()[[t.test_id for t in stored_tests(win)].index(page.selected_test().test_id)]


# -- Save (AC12, AA11) ---------------------------------------------------------------------------------


def test_save_links_the_run_locks_the_test_and_returns_to_the_list(rig):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing)
    saved = only_test(win)
    assert saved.status == "done" and saved.outcome == "completed"
    assert saved.run_dir == f"runs/click_grid/{folder.name}" and saved.completed_trials == saved.planned_trials == 1
    assert win.flow is Flow.IDLE and win.stack.currentIndex() == 1 and win.stack.count() == 2
    assert win.run_flow.app is None and win.run_flow.page is None
    assert win.test_list_page.selected_test().test_id == test.test_id
    row = selected_row(win)
    assert row[3] == "Done" and row[4] == saved.completed_at[:10]
    page = win.test_list_page
    assert not page.run_button.isEnabled() and not page.configure_button.isEnabled()  # locked
    assert page.report_button.isEnabled()
    assert page.message_label.text() == ""
    (result,) = answers.asked
    assert result.run_mode == "record" and result.is_complete and result.session_dir == folder
    assert not win.title_bar.isHidden() and all(b.isEnabled() for b in win.title_bar.buttons)


def test_the_saved_runs_metadata_names_the_test_and_how_it_ended(rig):
    # AA11 / AC16: the run folder carries the link back to the test, and the outcome fields.
    win, mouse, pointing = rig
    Answers(SAVE).install(win.run_flow)
    test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing)
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    saved = only_test(win)
    assert (meta["test_id"], meta["test_name"], meta["seed"]) == (test.test_id, test.name, test.seed)
    assert meta["config_name"] == "Fast hover" and meta["settings"]["config_name"] == "Fast hover"
    assert meta["outcome"] == "completed" and meta["ended_by"] == "finished"
    assert meta["planned_trials"] == meta["completed_trials"] == 1 == saved.completed_trials
    assert saved.run_dir == f"runs/click_grid/{folder.name}"
    assert meta["session_id"] == f"click_grid_{folder.name}_{test.test_id}"  # H3: no subject in it


def test_save_caches_the_report_in_the_run_folder(rig):
    win, mouse, pointing = rig
    Answers(SAVE).install(win.run_flow)
    _test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    assert not (folder / REPORT_FILENAME).exists()  # not at the run's end (HD1)
    finish_trials(app, pointing)
    assert (folder / REPORT_FILENAME).is_file()


def test_the_end_dialogs_are_asked_with_the_title_bar_hidden_over_the_frozen_canvas(rig):
    win, mouse, pointing = rig
    seen = []

    def ask(result):
        seen.append((win.flow, win.title_bar.isHidden(), win.stack.currentWidget() is win.run_flow.app.view))
        return SAVE

    win.run_flow.ask_end = ask
    _test, app = begin(win, mouse)
    finish_trials(app, pointing)
    assert seen == [(Flow.FINISHING, True, True)]


# -- Save and View Report ------------------------------------------------------------------------------


def test_save_and_view_report_opens_the_report_of_the_saved_test(rig):
    win, mouse, pointing = rig
    Answers(SAVE_AND_VIEW).install(win.run_flow)
    test, app = begin(win, mouse)
    finish_trials(app, pointing)
    assert only_test(win).status == "done"
    page = win.report_flow.page
    assert page is not None and win.flow is Flow.REPORT and win.stack.currentWidget() is page
    assert win.stack.count() == 3  # the two tabs and the report: no Start page, no run view left
    assert page.name_edit.text() == test.name
    assert not win.title_bar.isHidden() and not any(b.isEnabled() for b in win.title_bar.buttons)


def test_a_report_that_cannot_be_opened_after_save_leaves_the_saved_test_on_the_list(rig, monkeypatch):
    win, mouse, pointing = rig
    Answers(SAVE_AND_VIEW).install(win.run_flow)
    # finish_run builds the report itself and swallows a failure; the flow then tries once more.
    monkeypatch.setattr(run_result_module, "load_or_build_report", lambda folder: (_ for _ in ()).throw(ReportError("no trials")))
    monkeypatch.setattr(report_flow_module, "load_or_build_report", lambda folder: (_ for _ in ()).throw(ReportError("no trials")))
    test, app = begin(win, mouse)
    finish_trials(app, pointing)
    assert only_test(win).status == "done"  # the run is saved whatever the report does
    assert win.flow is Flow.IDLE and win.stack.count() == 2
    assert win.test_list_page.message_label.text() == f"Could not open the report for {test.name}: no trials"


# -- Discard (U14, HD1) ---------------------------------------------------------------------------------------


def test_discard_deletes_the_folder_and_leaves_the_test_not_done_and_runnable(rig):
    win, mouse, pointing = rig
    Answers(DISCARD).install(win.run_flow)
    test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    assert folder.is_dir()
    finish_trials(app, pointing)
    assert not folder.exists() and run_dirs(win) == []
    after = only_test(win)
    assert after.status == "not_done" and after.run_dir is None and after.completed_at is None
    assert win.flow is Flow.IDLE and win.test_list_page.selected_test().test_id == test.test_id
    assert win.test_list_page.run_button.isEnabled() and win.test_list_page.configure_button.isEnabled()
    # The minute is free again: the next run does not need a collision suffix.
    open_start(win, after)
    assert not start_run(win, mouse).recorder.session_dir.name.endswith("_2")


def test_the_report_is_built_only_for_a_saved_run_never_for_a_discarded_one(rig, monkeypatch):
    win, mouse, pointing = rig
    built = []
    real = run_result_module.write_report_safely
    monkeypatch.setattr(run_result_module, "write_report_safely", lambda folder: built.append(folder) or real(folder))
    answers = Answers(DISCARD)
    answers.install(win.run_flow)
    _test, app = begin(win, mouse)
    finish_trials(app, pointing)
    assert built == []
    answers.action = SAVE
    open_start(win, only_test(win))
    app = start_run(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing)
    assert built == [folder]


# -- a quit (4C.6, AC11) --------------------------------------------------------------------------------------


def test_quit_with_trials_done_then_save_partial_gives_ended_early(rig):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    test, app = begin(win, mouse, trials=3)
    finish_trials(app, pointing, 1)
    quit_run(app)
    saved = only_test(win)
    assert saved.status == "ended_early" and saved.outcome == "ended_early"
    assert (saved.completed_trials, saved.planned_trials) == (1, 3)
    assert selected_row(win)[3] == "Ended early (1/3)"
    (result,) = answers.asked
    assert not result.is_complete and result.ended_by == "operator_quit" and result.completed == 1
    assert win.flow is Flow.IDLE and not win.test_list_page.run_button.isEnabled()


def test_quit_with_trials_done_then_discard_deletes_the_folder(rig):
    win, mouse, pointing = rig
    Answers(DISCARD).install(win.run_flow)
    _test, app = begin(win, mouse, trials=3)
    folder = app.recorder.session_dir
    finish_trials(app, pointing, 1)
    quit_run(app)
    assert not folder.exists() and only_test(win).status == "not_done"
    assert win.test_list_page.run_button.isEnabled()


def test_keep_going_after_the_quit_question_keeps_the_run_and_the_flow(rig):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    _test, app = begin(win, mouse, trials=2)
    finish_trials(app, pointing, 1)
    quit_run(app, answer=False)
    assert answers.asked == [] and win.flow is Flow.RUN and win.run_flow.app is app
    assert not app._shutdown_done and only_test(win).status == "not_done"


def test_a_quit_before_any_trial_is_discarded_with_a_message_and_nothing_is_kept(rig):
    win, mouse, _pointing = rig
    told = []
    win.run_flow.ask_end = lambda result: ask_run_end(result, win, nothing=lambda parent: told.append(parent))
    _test, app = begin(win, mouse, trials=3)
    folder = app.recorder.session_dir
    app._tick()
    quit_run(app)
    assert told == [win]  # "No trials were completed, so nothing was saved."
    assert not folder.exists() and only_test(win).status == "not_done"
    assert win.flow is Flow.IDLE


def test_the_real_end_dialogs_are_walked_by_ask_run_end(rig):
    win, mouse, pointing = rig
    asked = []

    def complete(parent):
        asked.append("complete")
        return SAVE

    win.run_flow.ask_end = lambda result: ask_run_end(result, win, complete=complete)
    _test, app = begin(win, mouse)
    finish_trials(app, pointing)
    assert asked == ["complete"] and only_test(win).status == "done"


# -- the store refuses: the data stays, the operator is told (AC12) ----------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        store.TestLockedError("'Grid Click 1' already has a result."),
        store.TestStoreError("Could not save Grid Click 1: disk full"),
        ValueError("The session folder must be directly inside sessions"),
        SessionDiscardError("not a session folder"),
        PermissionError("file is in use"),
    ],
    ids=["locked", "store", "value", "discard", "os"],
)
def test_a_store_error_leaves_the_data_and_the_test_not_done_and_says_so(rig, monkeypatch, error):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    monkeypatch.setattr(run_flow_module, "finish_run", lambda *a, **k: (_ for _ in ()).throw(error))
    test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing)
    assert folder.is_dir() and (folder / "trials.csv").is_file()  # nothing was lost
    assert only_test(win).status == "not_done"
    assert win.flow is Flow.IDLE and win.test_list_page.selected_test().test_id == test.test_id
    ((title, text),) = answers.told
    reason = str(error).rstrip(".")
    assert title == "Results not saved" and reason in text and folder.name in text
    assert "Grid Click 1 stays Not Done" in text
    assert win.test_list_page.message_label.text() == ""  # the dialog only: no extra line on the list


def test_a_real_locked_test_at_save_time_is_reported_not_raised(rig):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    other = new_run_dir(win.output_root, SUBJECT, "click_grid")
    store.record_result(win.output_root, SUBJECT, test.test_id, session_dir=other, planned_trials=1, completed_trials=1)
    finish_trials(app, pointing)  # the test was saved from elsewhere meanwhile
    assert folder.is_dir()
    assert only_test(win).run_dir == f"runs/click_grid/{other.name}"  # the earlier link is untouched
    ((title, text),) = answers.told
    assert title == "Results not saved" and "already has a result" in text


def test_a_discard_the_guard_refuses_says_so_and_deletes_nothing(rig, monkeypatch):
    win, mouse, pointing = rig
    answers = Answers(DISCARD)
    answers.install(win.run_flow)

    def refuse(session_dir, output_root):
        raise SessionDiscardError("refusing to delete this folder")

    monkeypatch.setattr(run_result_module, "discard_session", refuse)
    _test, app = begin(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing)
    assert folder.is_dir() and only_test(win).status == "not_done"
    ((title, text),) = answers.told
    assert title == "Results not discarded" and "refusing to delete this folder" in text
    assert folder.name in text and "stays Not Done" in text
