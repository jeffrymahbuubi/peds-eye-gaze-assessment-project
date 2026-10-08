"""SPEC-compass-task-flow.md 4A.5, 4A.6 and acceptance AA6 / AA7 (page part): what
``SubjectTestListPage`` does -- Add New Test, Copy Test, Delete Test, the in-place rename,
the keyboard and the signals (offscreen Qt, a scratch folder)."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import src.ui.test_list_page as list_module
from src.engine.subject_tests import (
    STATUS_DONE,
    STATUS_NOT_DONE,
    TestStoreError,
    create_test,
    list_tests,
    run_folder_of,
    subject_tests_dir,
)
from src.ui.test_list_page import NO_TESTS_TEXT
from src.ui.test_list_table import (
    COL_DATE,
    COL_NAME,
    COL_STATUS,
)
from tests.list_page_fixtures import (
    SUBJECT,
    Recorder,
    done_test,
    names,
    page_for,
    select,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sessions"


# -- Add New Test -------------------------------------------------------------------------------------------------------


def test_add_creates_tests_with_default_names_and_selects_the_last(qapp, root):
    page = page_for(root)
    changed = Recorder(page.testsChanged)
    page._choose_new_tests = lambda: ("click_grid", 3)
    page.add_button.click()
    assert names(page) == ["Grid Click 1", "Grid Click 2", "Grid Click 3"]
    assert page.selected_test().name == "Grid Click 3"
    assert len(changed.items) == 1
    stored = list_tests(root, SUBJECT).tests
    assert [t.status for t in stored] == [STATUS_NOT_DONE] * 3
    assert all(t.configuration == {"name": "Standard", "structural": {}, "live": {}} for t in stored)
    assert page.center.currentIndex() == 0  # the table replaced the "No tests yet" line


def test_add_continues_the_numbering_of_a_task(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    page._choose_new_tests = lambda: ("click_grid", 1)
    page.add_button.click()
    page._choose_new_tests = lambda: ("scanning", 2)
    page.add_button.click()
    assert names(page) == ["Grid Click 1", "Grid Click 2", "Scanning Search 1", "Scanning Search 2"]


def test_cancelling_the_add_dialog_changes_nothing(qapp, root):
    page = page_for(root)
    changed = Recorder(page.testsChanged)
    page._choose_new_tests = lambda: None
    page.add_button.click()
    assert names(page) == [] and not changed.items and not root.exists()


def test_a_failed_add_says_so_and_shows_the_disk(qapp, root, monkeypatch):
    page = page_for(root)

    def broken(*args, **kwargs):
        raise TestStoreError("Could not save t_x.json: Permission denied")

    monkeypatch.setattr(list_module, "create_test", broken)
    page._choose_new_tests = lambda: ("click_grid", 2)
    page.add_button.click()
    assert page.message_label.text() == (
        "Could not add the test: Could not save t_x.json: Permission denied. Nothing was changed."
    )
    assert names(page) == []


def test_a_partly_failed_add_shows_what_was_written(qapp, root, monkeypatch):
    page = page_for(root)
    real = list_module.create_test
    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise TestStoreError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(list_module, "create_test", flaky)
    page._choose_new_tests = lambda: ("click_grid", 3)
    changed = Recorder(page.testsChanged)
    page.add_button.click()
    assert names(page) == ["Grid Click 1"]
    assert page.message_label.text() == "Added 1 of 3 tests; could not add the rest: disk full."
    assert len(changed.items) == 1


# -- Copy Test -----------------------------------------------------------------------------------------------------------


def test_copy_appends_an_unrun_copy_and_selects_it(qapp, root):
    done = done_test(root, "click_grid")
    page = page_for(root)
    select(page, done.test_id)
    changed = Recorder(page.testsChanged)
    page.copy_button.click()
    assert names(page) == ["Grid Click 1", "Grid Click 2"]
    assert page.selected_test().name == "Grid Click 2"
    assert page.selected_test().status == STATUS_NOT_DONE
    assert page.row_texts()[1][COL_STATUS] == "Not Done" and page.row_texts()[1][COL_DATE] == "—"
    assert len(changed.items) == 1
    assert page.run_button.isEnabled()  # the copy can be run


def test_a_failed_copy_leaves_the_list_as_it_was(qapp, root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)

    def broken(*args, **kwargs):
        raise TestStoreError("disk full")

    monkeypatch.setattr(list_module, "copy_test", broken)
    page.copy_button.click()
    assert names(page) == [test.name]
    assert page.message_label.text() == "Could not copy 'Grid Click 1': disk full. Nothing was changed."


# -- Delete Test ------------------------------------------------------------------------------------------------------------


def stub_dialog(monkeypatch, answer):
    """Replace ``ask_choice`` in the page module; returns the calls it saw."""
    calls = []

    def ask(parent, title, text, buttons, default, on_close):
        calls.append(dict(title=title, text=text, buttons=buttons, default=default, on_close=on_close))
        return answer

    monkeypatch.setattr(list_module, "ask_choice", ask)
    return calls


def test_delete_asks_first_and_keep_is_the_default(qapp, root, monkeypatch):
    test = done_test(root)
    page = page_for(root)
    select(page, test.test_id)
    calls = stub_dialog(monkeypatch, "keep")
    page.delete_button.click()
    assert names(page) == [test.name]  # kept
    (call,) = calls
    assert call["title"] == "Delete Test"
    assert call["text"] == (
        f"Delete '{test.name}' from this list? Its recorded data in the subject folder is kept."
    )
    assert [label for _key, label, _tier in call["buttons"]] == ["Delete", "Keep"]
    assert call["default"] == "keep" and call["on_close"] == "keep"


def test_a_not_done_test_is_asked_about_without_the_data_sentence(qapp, root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    calls = stub_dialog(monkeypatch, "keep")
    page.delete_button.click()
    assert calls[0]["text"] == f"Delete '{test.name}' from this list?"


def test_delete_moves_the_record_and_never_touches_the_session_folder(qapp, root, monkeypatch):
    test = done_test(root)
    folder = run_folder_of(root, test)
    marker = folder / "trials.csv"
    marker.write_text("a,b\n1,2\n", encoding="utf-8")
    page = page_for(root)
    select(page, test.test_id)
    stub_dialog(monkeypatch, "delete")
    changed = Recorder(page.testsChanged)
    page.delete_button.click()
    assert names(page) == [] and page.empty_label.text() == NO_TESTS_TEXT
    assert (subject_tests_dir(root, SUBJECT) / "_deleted" / f"{test.test_id}.json").is_file()
    assert marker.read_text(encoding="utf-8") == "a,b\n1,2\n"
    assert len(changed.items) == 1


def test_a_failed_delete_leaves_the_test(qapp, root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    stub_dialog(monkeypatch, "delete")

    def broken(*args, **kwargs):
        raise TestStoreError("Could not delete Grid Click 1: Access is denied")

    monkeypatch.setattr(list_module, "delete_test", broken)
    page.delete_button.click()
    assert names(page) == [test.name]
    assert "Nothing was changed." in page.message_label.text()


# -- rename in place ------------------------------------------------------------------------------------------------------------


def test_f2_opens_the_editor_over_the_name_with_the_name_selected(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    QTest.keyClick(page.table, Qt.Key.Key_F2)
    editor = page._editor
    assert editor is not None and editor.line_edit.text() == test.name
    assert editor.error_label.isHidden()  # the name is valid as it is
    editor.cancel()


def test_a_double_click_on_the_name_renames_and_elsewhere_acts(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    runs = Recorder(page.runRequested)
    page.table.cellDoubleClicked.emit(0, COL_NAME)
    assert page._editor is not None and not runs.items
    page._editor.cancel()
    page.table.cellDoubleClicked.emit(0, COL_STATUS)
    assert runs.items == [test.test_id]


def test_the_editor_refuses_a_name_another_test_uses_and_shows_why(qapp, root):
    first = create_test(root, SUBJECT, "click_grid")
    second = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, second.test_id)
    editor = page.start_rename()
    editor.line_edit.setText("  grid CLICK 1 ")  # the other test's name, in another case
    assert not editor.error_label.isHidden()
    assert editor.error_label.text() == "A test named 'grid CLICK 1' already exists for this subject."
    assert editor.commit() is False  # Enter keeps the editor open
    assert page._editor is editor
    editor.line_edit.setText("")
    assert editor.error_label.text() == "Enter a test name."
    editor.line_edit.setText("x" * 61)
    assert "at most 60" in editor.error_label.text()
    editor.cancel()
    assert [t.name for t in list_tests(root, SUBJECT).tests] == [first.name, second.name]


def test_a_valid_name_is_saved_to_disk_and_the_row_stays_selected(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    changed = Recorder(page.testsChanged)
    editor = page.start_rename()
    editor.line_edit.setText("  Baseline  ")
    assert editor.commit() is True
    assert names(page) == ["Baseline"]
    assert page.selected_test().test_id == test.test_id
    assert list_tests(root, SUBJECT).tests[0].name == "Baseline"
    assert len(changed.items) == 1 and page._editor is None


def test_a_done_test_can_be_renamed(qapp, root):
    test = done_test(root)
    page = page_for(root)
    select(page, test.test_id)
    editor = page.start_rename()
    editor.line_edit.setText("Renamed after the run")
    assert editor.commit()
    stored = list_tests(root, SUBJECT).tests[0]
    assert stored.name == "Renamed after the run" and stored.status == STATUS_DONE
    assert stored.run_dir == test.run_dir


def test_keeping_the_name_or_changing_only_its_case_is_allowed(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    editor = page.start_rename()
    assert editor.problem() is None
    editor.line_edit.setText(test.name.upper())
    assert editor.problem() is None


def test_escape_cancels_the_rename(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    editor = page.start_rename()
    editor.line_edit.setText("Something else")
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert page._editor is None
    assert list_tests(root, SUBJECT).tests[0].name == test.name
    assert names(page) == [test.name]


def test_a_rename_that_fails_on_disk_says_so(qapp, root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)

    def broken(*args, **kwargs):
        raise TestStoreError("disk full")

    monkeypatch.setattr(list_module, "rename_test", broken)
    editor = page.start_rename()
    editor.line_edit.setText("New name")
    editor.commit()
    assert names(page) == [test.name]
    assert page.message_label.text() == "Could not rename 'Grid Click 1': disk full. Nothing was changed."


def test_rename_with_nothing_selected_does_nothing(qapp, root):
    assert page_for(root).start_rename() is None


# -- keyboard and signals ------------------------------------------------------------------------------------------------------------


def test_the_buttons_emit_the_selected_tests_id(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    done = done_test(root, "click_static")
    page = page_for(root)
    configure, run, report = (
        Recorder(page.configureRequested),
        Recorder(page.runRequested),
        Recorder(page.reportRequested),
    )
    select(page, test.test_id)
    page.configure_button.click()
    page.run_button.click()
    select(page, done.test_id)
    page.report_button.click()
    assert configure.items == [test.test_id] and run.items == [test.test_id]
    assert report.items == [done.test_id]


def test_enter_runs_a_not_done_test_and_reports_a_done_one(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    done = done_test(root, "click_static")
    page = page_for(root)
    run, report = Recorder(page.runRequested), Recorder(page.reportRequested)
    select(page, test.test_id)
    QTest.keyClick(page.table, Qt.Key.Key_Return)
    select(page, done.test_id)
    QTest.keyClick(page.table, Qt.Key.Key_Enter)
    assert run.items == [test.test_id] and report.items == [done.test_id]


def test_enter_on_a_done_test_with_missing_data_does_nothing(qapp, root):
    done = done_test(root)
    run_folder_of(root, done).rmdir()
    page = page_for(root)
    select(page, done.test_id)
    report = Recorder(page.reportRequested)
    QTest.keyClick(page.table, Qt.Key.Key_Return)
    assert not report.items


def test_the_delete_key_deletes_after_asking(qapp, root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    calls = stub_dialog(monkeypatch, "delete")
    QTest.keyClick(page.table, Qt.Key.Key_Delete)
    assert len(calls) == 1 and names(page) == []


def test_the_delete_key_with_nothing_selected_asks_nothing(qapp, root, monkeypatch):
    create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    page.table.clearSelection()  # the page opens with the first row selected (FX3)
    calls = stub_dialog(monkeypatch, "delete")
    QTest.keyClick(page.table, Qt.Key.Key_Delete)
    assert not calls


def test_run_is_never_disabled_by_setup_state(qapp, root):
    # R2: the page knows nothing about the tracker; Run Test is on for a Not Done test and
    # the Start page shows what is missing.
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    assert page.run_button.isEnabled() and page.run_button.toolTip() == ""


def test_back_to_setup_and_the_saved_line(qapp, root):
    page = page_for(root)
    back = Recorder(page.backToSetupRequested)
    page.back_button.click()
    assert len(back.items) == 1
    assert page.back_button.text() == "Back to Setup"


def test_a_message_is_cleared_by_the_next_selection(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    other = create_test(root, SUBJECT, "click_static")  # the first row is the one selected at open
    page = page_for(root)
    page.show_message("Run Test is not connected yet.")
    assert not page.message_label.isHidden()
    select(page, other.test_id)
    assert page.message_label.isHidden() and page.message_label.text() == ""


def test_reload_picks_up_a_change_made_on_disk(qapp, root):
    page = page_for(root)
    assert names(page) == []
    create_test(root, SUBJECT, "click_grid")
    page.reload()
    assert names(page) == ["Grid Click 1"]


def test_the_page_writes_nothing_on_its_own(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    page = page_for(root)
    page.table.horizontalHeader().sectionClicked.emit(COL_NAME)
    page.reload()
    page.select_test(list_tests(root, SUBJECT).tests[0].test_id)
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    assert before == after


def test_a_saved_record_is_json_the_page_never_rewrites(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    path = subject_tests_dir(root, SUBJECT) / f"{test.test_id}.json"
    before = path.read_bytes()
    page = page_for(root)
    page.reload()
    assert path.read_bytes() == before and json.loads(before)["name"] == test.name
