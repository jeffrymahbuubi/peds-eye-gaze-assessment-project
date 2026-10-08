"""SPEC-compass-task-flow.md 4A.4 and acceptance AA9, AA12, AA14 (page part), AA15,
AA16 (page part): what ``SubjectTestListPage`` shows -- the table, the button matrix, the
empty states, sorting (offscreen Qt, a scratch folder; the store itself is tested in
``test_subject_tests*.py``). The actions are in ``test_test_list_actions.py``."""

from __future__ import annotations

import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.subject_tests import (
    STATUS_DONE,
    STATUS_ENDED_EARLY,
    create_test,
    delete_test,
    run_folder_of,
    subject_tests_dir,
)
from src.ui.test_list_page import NO_SUBJECT_TEXT, NO_TESTS_TEXT
from src.ui.test_list_table import (
    COL_DATE,
    COL_NAME,
    COL_STATUS,
    date_cells,
    natural_key,
    status_text,
)
from tests.list_page_fixtures import (
    SUBJECT,
    done_test,
    enabled,
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


# -- helpers -----------------------------------------------------------------------------------


def test_natural_key_orders_digits_as_numbers_and_ignores_case():
    ordered = sorted(["Grid Click 10", "grid click 2", "Grid Click 1", "Static Click 3"], key=natural_key)
    assert ordered == ["Grid Click 1", "grid click 2", "Grid Click 10", "Static Click 3"]


def test_natural_key_never_compares_text_with_a_number():
    # Mixed and unusual names must sort without a TypeError.
    sorted(["", "7", "a7b", "7a", "²", "Test ٣", "x" * 60], key=natural_key)


def test_status_text_per_state():
    from src.engine.subject_tests import SubjectTest

    base = SubjectTest("t_0123456789", "S", "n", "click_grid", "2026-10-06T10:00:00+08:00")
    assert status_text(base) == "Not Done"
    done = SubjectTest(**{**base.__dict__, "status": STATUS_DONE})
    assert status_text(done) == "Done"
    assert status_text(done, data_missing=True) == "Done · data missing"
    early = SubjectTest(
        **{**base.__dict__, "status": STATUS_ENDED_EARLY, "completed_trials": 7, "planned_trials": 12}
    )
    assert status_text(early) == "Ended early (7/12)"
    assert status_text(early, data_missing=True) == "Ended early (7/12) · data missing"
    bare = SubjectTest(**{**base.__dict__, "status": STATUS_ENDED_EARLY})
    assert status_text(bare) == "Ended early"


def test_date_cells():
    when = datetime.fromisoformat("2026-10-06T12:00:00+00:00").astimezone()
    assert date_cells("2026-10-06T12:00:00+00:00") == (
        when.strftime("%Y-%m-%d"),
        when.strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert date_cells(None) == ("—", "")
    assert date_cells("not a date") == ("—", "")


# -- AA9: the table after a reload -------------------------------------------------------------------


def test_the_table_after_recreating_the_page_is_identical(qapp, root):
    not_done = create_test(root, SUBJECT, "click_grid")
    done = done_test(root, "click_static")
    early = done_test(root, "follow_moving", planned=12, completed=7)
    first = page_for(root)
    second = page_for(root)  # a fresh page, as after a restart
    assert first.row_texts() == second.row_texts()
    rows = {row[COL_NAME]: row for row in second.row_texts()}
    assert rows[not_done.name][COL_STATUS] == "Not Done"
    assert rows[not_done.name][COL_DATE] == "—"
    assert rows[done.name][COL_STATUS] == "Done"
    expected_day = datetime.fromisoformat("2026-10-06T12:00:00+00:00").astimezone().strftime("%Y-%m-%d")
    assert rows[done.name][COL_DATE] == expected_day
    assert rows[early.name][COL_STATUS] == "Ended early (7/12)"
    # Compass: rows of tests not yet run are bold, and only those.
    for row in range(second.table.rowCount()):
        bold = {second.table.item(row, c).font().bold() for c in range(5)}
        assert bold == {second.row_texts()[row][COL_NAME] == not_done.name}


def test_the_date_cell_carries_the_full_time_as_its_tooltip(qapp, root):
    done_test(root)
    page = page_for(root)
    tip = page.table.item(0, COL_DATE).toolTip()
    assert tip.startswith(page.row_texts()[0][COL_DATE]) and len(tip) == len("2026-10-06 12:00:00")


def test_the_columns_and_the_default_order(qapp, root):
    for name in ("Grid Click 10", "Grid Click 2", "Grid Click 1"):
        create_test(root, SUBJECT, "click_grid", name=name)
    page = page_for(root)
    assert [page.table.horizontalHeaderItem(c).text() for c in range(5)] == [
        "Test Name", "Task", "Configuration", "Status", "Date Complete",
    ]
    assert names(page) == ["Grid Click 10", "Grid Click 2", "Grid Click 1"]  # creation order
    assert page.row_texts()[0][1:3] == ["Grid Click", "Standard"]


def test_a_done_test_whose_folder_is_gone_says_so_and_has_no_report(qapp, root):
    test = done_test(root)
    page = page_for(root)
    select(page, test.test_id)
    assert page.report_button.isEnabled()
    run_folder_of(root, test).rmdir()
    page.reload()
    assert page.row_texts()[0][COL_STATUS] == "Done · data missing"
    assert not page.report_button.isEnabled()
    assert "missing from the subject folder" in page.report_button.toolTip()
    assert page.copy_button.isEnabled() and page.delete_button.isEnabled()


# -- the button matrix (4A.4, R2) ---------------------------------------------------------------------------


def test_with_nothing_selected_only_add_is_on(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    page.table.clearSelection()  # the page opens with a row selected (FX3); the operator can clear it
    assert page.selected_test() is None
    assert enabled(page) == dict(add=True, configure=False, run=False, report=False, copy=False, delete=False)


# -- FX3: the selection matches the focus the table shows ----------------------------------------------------


def test_the_page_opens_with_the_first_row_selected_and_current(qapp, root):
    first = create_test(root, SUBJECT, "click_grid")
    create_test(root, SUBJECT, "click_static")
    page = page_for(root)
    assert page.selected_test().test_id == first.test_id
    assert page.table.currentRow() == 0 and page.table.currentColumn() == COL_NAME
    # The buttons follow the 4A.4 matrix for a Not Done row, not the "nothing selected" row.
    assert enabled(page) == dict(add=True, configure=True, run=True, report=False, copy=True, delete=True)


def test_a_done_first_row_opens_with_the_done_buttons(qapp, root):
    done = done_test(root)
    create_test(root, SUBJECT, "click_static")
    page = page_for(root)
    assert page.selected_test().test_id == done.test_id
    assert enabled(page) == dict(add=True, configure=False, run=False, report=True, copy=True, delete=True)


def test_the_test_used_last_stays_selected_through_a_reload(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    second = create_test(root, SUBJECT, "click_static")
    page = page_for(root)
    select(page, second.test_id)
    page.reload()
    assert page.selected_test().test_id == second.test_id
    page.set_subject(SUBJECT, root)  # the Tests tab is opened again
    assert page.selected_test().test_id == second.test_id
    page.reload(select=second.test_id)  # what the dashboard asks for after a flow
    assert page.selected_test().test_id == second.test_id


def test_a_test_that_is_gone_falls_back_to_the_first_row(qapp, root):
    first = create_test(root, SUBJECT, "click_grid")
    second = create_test(root, SUBJECT, "click_static")
    page = page_for(root)
    select(page, second.test_id)
    delete_test(root, SUBJECT, second.test_id)
    page.reload()
    assert page.selected_test().test_id == first.test_id
    assert page.table.currentRow() == 0


def test_the_first_row_is_the_first_one_shown_when_the_list_is_sorted(qapp, root):
    for name in ("Grid Click 2", "Grid Click 1", "Grid Click 3"):
        create_test(root, SUBJECT, "click_grid", name=name)
    page = page_for(root)
    click_header(page, COL_NAME)
    click_header(page, COL_NAME)  # descending
    page.table.clearSelection()
    page.reload()
    assert names(page)[0] == "Grid Click 3"
    assert page.selected_test().name == "Grid Click 3" and page.table.currentRow() == 0


def test_another_subject_opens_on_its_own_first_row(qapp, root):
    create_test(root, "A", "click_grid", name="A's test")
    b_first = create_test(root, "B", "click_static", name="B's first")
    create_test(root, "B", "click_grid", name="B's second")
    page = page_for(root, "A")
    assert page.selected_test().name == "A's test"
    page.set_subject("B", root)  # A's selected test is not B's: fall back to B's first row
    assert page.selected_test().test_id == b_first.test_id


def test_with_no_tests_nothing_is_selected(qapp, root):
    page = page_for(root)  # no tests yet
    assert page.selected_test() is None
    assert enabled(page) == dict(add=True, configure=False, run=False, report=False, copy=False, delete=False)
    page_for(root, subject="")  # no Subject ID: nothing, not even Add, and nothing raised


def test_a_not_done_test_can_be_configured_and_run_but_not_reported(qapp, root):
    test = create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    select(page, test.test_id)
    assert enabled(page) == dict(add=True, configure=True, run=True, report=False, copy=True, delete=True)


@pytest.mark.parametrize("planned,completed", [(18, 18), (12, 7)])
def test_a_run_test_can_be_reported_but_not_configured_or_run(qapp, root, planned, completed):
    test = done_test(root, planned=planned, completed=completed)
    page = page_for(root)
    select(page, test.test_id)
    assert enabled(page) == dict(add=True, configure=False, run=False, report=True, copy=True, delete=True)


def test_disabled_buttons_stay_visible(qapp, root):
    page = page_for(root)
    for button in (page.configure_button, page.run_button, page.report_button, page.copy_button, page.delete_button):
        assert not button.isEnabled() and not button.isHidden()


def test_the_buttons_follow_the_selection(qapp, root):
    not_done = create_test(root, SUBJECT, "click_grid")
    done = done_test(root, "click_static")
    page = page_for(root)
    select(page, not_done.test_id)
    assert page.run_button.isEnabled()
    select(page, done.test_id)
    assert not page.run_button.isEnabled() and page.report_button.isEnabled()
    page.table.clearSelection()
    assert not page.run_button.isEnabled()


# -- AA15: no Subject ID ----------------------------------------------------------------------------------------


def test_no_subject_id_shows_the_empty_state_and_creates_nothing(qapp, root):
    page = page_for(root, subject="")
    assert page.title_label.text() == "Test List"
    assert page.empty_label.text() == NO_SUBJECT_TEXT
    assert page.center.currentIndex() == 1  # the line stands in for the table
    assert not any(enabled(page).values())  # every button is off, Add included
    assert not root.exists()  # no folder, no file


def test_whitespace_is_no_subject_id(qapp, root):
    page = page_for(root, subject="   ")
    assert page.empty_label.text() == NO_SUBJECT_TEXT and not any(enabled(page).values())


def test_a_subject_with_no_tests_says_so_and_allows_add(qapp, root):
    page = page_for(root)
    assert page.empty_label.text() == NO_TESTS_TEXT
    assert page.center.currentIndex() == 1
    assert enabled(page)["add"] and not enabled(page)["run"]
    assert page.title_label.text() == f"Test List for {SUBJECT}"


# -- AA14 (page part): an unreadable file ------------------------------------------------------------------------


def test_an_unreadable_test_file_is_hidden_and_counted(qapp, root):
    good = create_test(root, SUBJECT, "click_grid")
    folder = subject_tests_dir(root, SUBJECT)
    (folder / "t_0123456789.json").write_text("{ not json", encoding="utf-8")
    page = page_for(root)
    assert names(page) == [good.name]
    assert not page.unreadable_label.isHidden()
    assert page.unreadable_label.text().startswith("1 test file(s) could not be read and are hidden:")
    assert str(folder) in page.unreadable_label.text()


def test_no_unreadable_files_no_line(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    assert page_for(root).unreadable_label.isHidden()


# -- subjects never mix (AA4 / AA10 at page level) --------------------------------------------------------------------


def test_another_subject_sees_none_of_the_first_subjects_tests(qapp, root):
    create_test(root, "A", "click_grid", name="A's test")
    create_test(root, "B", "click_static", name="B's test")
    page = page_for(root, "A")
    assert names(page) == ["A's test"]
    page.set_subject("B", root)
    assert names(page) == ["B's test"] and page.title_label.text() == "Test List for B"
    page.set_subject("A", root)
    assert names(page) == ["A's test"]


def test_subject_ids_that_differ_only_in_case_share_one_list(qapp, root):
    create_test(root, "jeffry", "click_grid")
    assert names(page_for(root, "JEFFRY")) == ["Grid Click 1"]


# -- AA12: sorting ------------------------------------------------------------------------------------------------------


def click_header(page, column):
    page.table.horizontalHeader().sectionClicked.emit(column)


def test_a_header_click_sorts_test_names_naturally_and_again_reverses(qapp, root):
    for name in ("Grid Click 10", "Grid Click 2", "Grid Click 1", "grid click 3"):
        create_test(root, SUBJECT, "click_grid", name=name)
    page = page_for(root)
    click_header(page, COL_NAME)
    assert names(page) == ["Grid Click 1", "Grid Click 2", "grid click 3", "Grid Click 10"]
    click_header(page, COL_NAME)
    assert names(page) == ["Grid Click 10", "grid click 3", "Grid Click 2", "Grid Click 1"]
    click_header(page, COL_NAME)  # a third click goes back to ascending
    assert names(page)[0] == "Grid Click 1"


def test_the_selection_survives_a_sort_and_a_reload(qapp, root):
    tests = [create_test(root, SUBJECT, "click_grid", name=f"Grid Click {n}") for n in (10, 2, 1)]
    page = page_for(root)
    select(page, tests[0].test_id)  # "Grid Click 10"
    click_header(page, COL_NAME)
    assert page.selected_test().name == "Grid Click 10"
    page.reload()
    assert page.selected_test().name == "Grid Click 10"
    assert names(page) == ["Grid Click 1", "Grid Click 2", "Grid Click 10"]  # the sort is kept too


def test_a_sort_keeps_the_rows_of_a_test_together(qapp, root):
    done = done_test(root, "click_static", name="Beta")
    create_test(root, SUBJECT, "click_grid", name="Alpha")
    page = page_for(root)
    click_header(page, COL_NAME)
    assert page.row_texts()[0][COL_NAME] == "Alpha" and page.row_texts()[0][COL_STATUS] == "Not Done"
    assert page.row_texts()[1][COL_NAME] == "Beta" and page.row_texts()[1][COL_STATUS] == "Done"
    select(page, done.test_id)
    assert page.selected_test().name == "Beta"


def test_date_complete_sorts_with_the_dash_first(qapp, root):
    later = done_test(root, "click_static", name="Later", when="2026-10-08T12:00:00+00:00")
    create_test(root, SUBJECT, "click_grid", name="Waiting")
    earlier = done_test(root, "scanning", name="Earlier", when="2026-10-05T12:00:00+00:00")
    page = page_for(root)
    click_header(page, COL_DATE)
    assert names(page) == ["Waiting", "Earlier", "Later"]
    click_header(page, COL_DATE)
    assert names(page) == ["Later", "Earlier", "Waiting"]
    assert {later.name, earlier.name} <= set(names(page))


# -- Open Subject Folder (SPEC-subject-data-layout.md H6, wireframe W2, L5) ---------------------------------------------


def test_open_subject_folder_is_off_until_the_subject_has_a_folder(qapp, root):
    page = page_for(root)  # TESTING has nothing saved yet
    assert not page.open_folder_button.isEnabled()
    assert page.open_folder_button.text() == "Open Subject Folder"
    create_test(root, SUBJECT, "click_grid")
    page.reload()
    assert page.open_folder_button.isEnabled()


def test_open_subject_folder_is_off_without_a_subject_id(qapp, root):
    assert not page_for(root, subject="").open_folder_button.isEnabled()


def test_open_subject_folder_is_on_whatever_row_is_selected_or_none(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    done = done_test(root, "click_static")
    page = page_for(root)
    for test_id in (None, done.test_id):
        if test_id is not None:
            select(page, test_id)
        else:
            page.table.clearSelection()
        assert page.open_folder_button.isEnabled()


def test_open_subject_folder_opens_the_subjects_own_folder(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    opened = []
    page._open_folder = lambda path: opened.append(path) or True
    page.open_folder_button.click()
    assert opened == [root / SUBJECT]


def test_open_subject_folder_opens_the_code_folder_for_an_anonymous_subject(qapp, root):
    create_test(root, "Maria Lopez", "click_grid", folder_mode="code")
    page = page_for(root, "maria lopez")
    opened = []
    page._open_folder = lambda path: opened.append(path) or True
    page.open_folder_button.click()
    assert opened == [root / "S-0001"]


def test_open_subject_folder_says_so_when_the_desktop_refuses(qapp, root):
    create_test(root, SUBJECT, "click_grid")
    page = page_for(root)
    page._open_folder = lambda path: False
    page.open_folder_button.click()
    assert "Could not open the folder" in page.message_label.text()


def test_the_first_test_added_in_the_page_makes_the_folder_in_the_chosen_mode(qapp, root):
    page = page_for(root, "Ana")
    page.set_subject("Ana", root, "code")
    page._choose_new_tests = lambda: ("click_grid", 1)
    page.add_button.click()
    assert [p.name for p in root.iterdir() if p.name != "_system"] == ["S-0001"]
    assert page.open_folder_button.isEnabled()
    assert names(page) == ["Grid Click 1"]
