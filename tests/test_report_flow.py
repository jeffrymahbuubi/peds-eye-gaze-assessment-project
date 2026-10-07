"""SPEC-compass-task-flow.md 4D.2, 4D.8, 4A.7, R11, AA11 and AD11 on the dashboard side (P8b):
View Report opens the per-test report page with the nav locked; Save & Continue writes the
name, evaluator and notes to the test record and returns to the Test List; Cancel writes
nothing; a report that cannot be built is said so on the list. Offscreen Qt, a scratch folder;
the run folder is a synthetic one written through the real report pipeline."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.ui.report_flow as report_flow_module
from src.data.report_cache import REPORT_FILENAME, ReportError
from src.engine import subject_tests as store
from src.ui.dashboard_flow import TESTS_INDEX, Flow
from tests.dashboard_fixtures import new_test
from tests.report_ui_fixtures import folder_report
from tests.run_flow_fixtures import SUBJECT, close_run_window, make_run_window, stored_tests


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    yield win
    close_run_window(win)


def done_test(win, **edits):
    """A Done click_grid test whose run folder is a synthetic one under the output root.
    Returns ``(test, folder)``."""
    test = new_test(win)
    root = Path(win.output_root)
    folder_report(root)  # writes <root>/run through the real pipeline
    folder = root / "run"
    store.record_result(
        win.output_root, SUBJECT, test.test_id, session_dir=folder, planned_trials=6, completed_trials=6
    )
    if edits:
        store.update_test(win.output_root, SUBJECT, test.test_id, **edits)
    return next(t for t in stored_tests(win) if t.test_id == test.test_id), folder


def view_report(win, test):
    win.test_list_page.reload()
    assert win.test_list_page.select_test(test.test_id)
    win.test_list_page.report_button.click()
    return win.report_flow.page


def current(win, test_id):
    return next(t for t in stored_tests(win) if t.test_id == test_id)


def nav_locked(win):
    return not any(b.isEnabled() for b in win.title_bar.buttons)


# -- opening the report ------------------------------------------------------------------------------------


def test_view_report_opens_the_page_for_the_test_with_the_nav_locked(rig):
    win = rig
    test, _folder = done_test(win, notes="shy at first", evaluator="Dr. Lin")
    page = view_report(win, test)
    assert win.flow is Flow.REPORT and win.stack.currentWidget() is page and win.stack.count() == 3
    assert nav_locked(win) and not win.title_bar.isHidden()
    assert page.name_edit.text() == "Grid Click 1"
    assert page.evaluator_edit.text() == "Dr. Lin" and page.notes_edit.toPlainText() == "shy at first"
    assert page.view_mode == "summary" and not page.is_dirty()


def test_the_report_is_labelled_with_the_tests_subject_not_the_one_typed_in_setup(rig):
    win = rig
    test, _folder = done_test(win)
    win.setup_page.subject_id_edit.setText("testing")  # the same list, typed another way
    win.report_flow.open(test.test_id)
    label = win.report_flow.page.subject_label.text()
    assert "TESTING" in label and "P001" not in label  # not the report's own "P001" either


def test_print_report_starts_in_the_runs_own_folder(rig):
    win = rig
    test, folder = done_test(win)
    page = view_report(win, test)
    asked = []
    page.choose_pdf_path = lambda default: asked.append(default) or ""
    page.print_button.click()
    (default,) = asked
    assert Path(default).parent == folder and default.endswith(".pdf")
    assert "_Grid Click 1_" in Path(default).name  # <subject>_<test name>_<date>.pdf


def test_the_existing_names_of_the_subject_are_given_for_the_name_check(rig):
    win = rig
    test, _folder = done_test(win)
    store.create_test(win.output_root, SUBJECT, "scanning", name="Scanning Search 1")
    page = view_report(win, test)
    page.name_edit.setText("scanning search 1")  # taken, whatever the case
    assert not page.save_button.isEnabled()
    page.name_edit.setText("Grid Click 1")  # its own name is fine
    assert page.save_button.isEnabled()


def test_the_report_is_loaded_from_the_runs_folder_and_cached_there(rig):
    win = rig
    test, folder = done_test(win)
    assert not (folder / REPORT_FILENAME).exists()
    view_report(win, test)
    assert (folder / REPORT_FILENAME).is_file()  # load_or_build_report cached it


def test_a_report_already_in_hand_is_used_without_reading_the_folder(rig, monkeypatch):
    win = rig
    test, folder = done_test(win)
    report = folder_report(Path(win.output_root) / "elsewhere")
    monkeypatch.setattr(report_flow_module, "load_or_build_report", lambda f: pytest.fail("read the folder"))
    win.report_flow.open(test.test_id, report=report)
    assert win.flow is Flow.REPORT


def test_a_garbage_record_in_the_subjects_folder_does_not_stop_the_report(rig):
    win = rig
    test, _folder = done_test(win)
    (Path(win.output_root) / "_tests" / SUBJECT / "t_deadbeef00.json").write_text("[1, 2", encoding="utf-8")
    page = view_report(win, test)
    assert win.flow is Flow.REPORT and page is not None


def test_a_second_view_report_is_ignored_while_a_page_is_open(rig):
    win = rig
    test, _folder = done_test(win)
    page = view_report(win, test)
    win.report_flow.open(test.test_id)
    assert win.report_flow.page is page and win.stack.count() == 3


# -- Save & Continue and Cancel (AD11) ------------------------------------------------------------------------


def test_save_writes_name_evaluator_and_notes_and_returns_to_the_list(rig):
    win = rig
    test, folder = done_test(win)
    page = view_report(win, test)
    page.name_edit.setText("Renamed test")
    page.evaluator_edit.setText("Dr. Chen")
    page.notes_edit.setPlainText("Good attention")
    page.save_button.click()
    saved = current(win, test.test_id)
    assert (saved.name, saved.evaluator, saved.notes) == ("Renamed test", "Dr. Chen", "Good attention")
    assert saved.status == "done" and saved.session_dir == folder.name  # still locked, same run
    assert win.flow is Flow.IDLE and win.stack.currentIndex() == TESTS_INDEX and win.stack.count() == 2
    assert win.report_flow.page is None and win.test_list_page.selected_test().test_id == test.test_id
    assert "Renamed test" in [row[0] for row in win.test_list_page.row_texts()]
    assert not nav_locked(win)


def test_cancel_writes_nothing_and_returns_to_the_list(rig):
    win = rig
    test, _folder = done_test(win, notes="before")
    page = view_report(win, test)
    page.name_edit.setText("Edited")
    page.notes_edit.setPlainText("edited too")
    before = current(win, test.test_id)
    page.cancel_button.click()
    assert current(win, test.test_id) == before and before.notes == "before" and before.name == "Grid Click 1"
    assert win.flow is Flow.IDLE and win.stack.count() == 2
    assert win.test_list_page.selected_test().test_id == test.test_id


def test_save_with_nothing_changed_writes_nothing(rig, monkeypatch):
    win = rig
    test, _folder = done_test(win)
    page = view_report(win, test)
    monkeypatch.setattr(report_flow_module, "rename_test", lambda *a, **k: pytest.fail("renamed"))
    monkeypatch.setattr(report_flow_module, "update_test", lambda *a, **k: pytest.fail("updated"))
    page.save_button.click()
    assert win.flow is Flow.IDLE


def test_a_failed_write_says_so_on_the_page_and_stays(rig, monkeypatch):
    win = rig
    test, _folder = done_test(win)
    page = view_report(win, test)
    page.notes_edit.setPlainText("will not stick")

    def fail(*args, **kwargs):
        raise store.TestStoreError("disk full")

    monkeypatch.setattr(report_flow_module, "update_test", fail)
    page.save_button.click()
    assert page.footer_message.text() == "Could not save: disk full"
    assert win.flow is Flow.REPORT and win.report_flow.page is page
    assert current(win, test.test_id).notes == ""


def test_a_name_taken_meanwhile_is_reported_not_raised(rig):
    win = rig
    test, _folder = done_test(win)
    page = view_report(win, test)
    page.name_edit.setText("Fresh name")
    store.create_test(win.output_root, SUBJECT, "scanning", name="Fresh name")  # another process
    page.save_button.click()
    assert page.footer_message.text().startswith("Could not save:")
    assert win.flow is Flow.REPORT and current(win, test.test_id).name == "Grid Click 1"


def test_a_test_removed_meanwhile_is_reported_on_the_page(rig):
    win = rig
    test, _folder = done_test(win)
    page = view_report(win, test)
    store.delete_test(win.output_root, SUBJECT, test.test_id)
    page.notes_edit.setPlainText("x")
    page.save_button.click()
    assert page.footer_message.text() == "Could not save: this test could not be found."
    assert win.flow is Flow.REPORT


# -- a report that cannot be shown (AA11) ---------------------------------------------------------------------------


def test_a_run_folder_no_report_can_be_built_from_is_said_on_the_list(rig):
    win = rig
    test, folder = done_test(win)
    (folder / "trials.csv").unlink()
    (folder / REPORT_FILENAME).unlink(missing_ok=True)
    win.test_list_page.reload()
    win.report_flow.open(test.test_id)
    text = win.test_list_page.message_label.text()
    assert text.startswith("Could not open the report for Grid Click 1: ") and "trials.csv" in text
    assert win.flow is Flow.IDLE and win.stack.count() == 2 and win.report_flow.page is None
    assert not nav_locked(win)


def test_a_report_error_from_the_cache_is_shown_too(rig, monkeypatch):
    win = rig
    test, _folder = done_test(win)

    def broken(folder):
        raise ReportError("unreadable")

    monkeypatch.setattr(report_flow_module, "load_or_build_report", broken)
    win.report_flow.open(test.test_id)
    assert win.test_list_page.message_label.text() == "Could not open the report for Grid Click 1: unreadable"


def test_a_missing_data_folder_is_said_on_the_list(rig):
    win = rig
    test, folder = done_test(win)
    shutil.rmtree(folder)
    win.test_list_page.reload()
    win.test_list_page.select_test(test.test_id)
    assert not win.test_list_page.report_button.isEnabled()  # the list already says "data missing"
    win.report_flow.open(test.test_id)
    assert win.test_list_page.message_label.text() == (
        "The recorded data for Grid Click 1 is missing from the sessions folder."
    )
    assert win.flow is Flow.IDLE


def test_a_test_that_has_not_run_has_no_report(rig):
    win = rig
    test = new_test(win)
    win.report_flow.open(test.test_id)
    assert win.test_list_page.message_label.text() == "Grid Click 1 has not been run, so it has no report."
    assert win.flow is Flow.IDLE


def test_an_unknown_test_reloads_the_list(rig):
    win = rig
    win.report_flow.open("t_0000000000")
    assert win.test_list_page.message_label.text() == "That test could not be found. The list was reloaded."
