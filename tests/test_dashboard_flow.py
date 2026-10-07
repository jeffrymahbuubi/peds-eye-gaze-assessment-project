"""SPEC-compass-task-flow.md 4A.6-4A.8, 4C.1 (flow state), R11 (nav lock), acceptance AA10
and AA16 (dashboard part), AA15: the dashboard window around the Tests tab (offscreen Qt,
a scratch folder, no tracker).

The configuration page and Preview are in ``test_config_flow.py``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.engine.subject_tests import create_test, list_tests, record_result
from src.ui.dashboard_flow import (
    NAV_LABELS,
    SETUP_INDEX,
    TESTS_INDEX,
    Flow,
    TitleBar,
    output_root_from_config,
)
from src.ui.dashboard_window import DashboardWindow
from src.ui.test_list_page import SubjectTestListPage
from src.ui.wtmh_theme import TITLEBAR_BG, TITLEBAR_TEXT


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # sessions/ is relative to the working directory
    window = DashboardWindow()
    window.setup_page.subject_id_edit.setText("TESTING")
    yield window
    window.close()


def names(win) -> list[str]:
    return [row[0] for row in win.test_list_page.row_texts()]


def active(win) -> list[bool]:
    return [bool(b.property("active")) for b in win.title_bar.buttons]


# -- the nav (R11) ------------------------------------------------------------------------------


def test_the_nav_reads_setup_and_tests_only(win):
    # R11: the per-test report replaced the old "3 · Results" tab.
    assert [b.text() for b in win.title_bar.buttons] == ["1 · Setup", "2 · Tests"]
    assert NAV_LABELS == ("1 · Setup", "2 · Tests")
    assert win.setup_nav_button is win.title_bar.setup_button
    assert win.tests_nav_button is win.title_bar.tests_button
    assert not hasattr(win, "results_nav_button") and not hasattr(win.title_bar, "results_button")


def test_the_window_opens_on_setup_with_every_button_on(win):
    assert win.stack.currentIndex() == SETUP_INDEX and win.flow is Flow.IDLE
    assert active(win) == [True, False]
    assert all(b.isEnabled() for b in win.title_bar.buttons)
    assert not win.title_bar.isHidden()


def test_the_nav_moves_between_tabs(win):
    win.tests_nav_button.click()
    assert win.stack.currentIndex() == TESTS_INDEX and active(win) == [False, True]
    win.setup_nav_button.click()
    assert win.stack.currentIndex() == SETUP_INDEX and active(win) == [True, False]


def test_the_stack_holds_setup_and_the_test_list(win):
    assert win.stack.widget(SETUP_INDEX) is win.setup_page
    assert isinstance(win.stack.widget(TESTS_INDEX), SubjectTestListPage)
    assert win.stack.count() == 2


@pytest.mark.parametrize(
    ("flow", "locks", "hides"),
    [
        (Flow.IDLE, False, False),
        (Flow.CONFIGURE, True, False),
        (Flow.PREVIEW, True, True),
        (Flow.START, True, False),
        (Flow.PRACTICE, True, True),
        (Flow.RUN, True, True),
        (Flow.FINISHING, True, True),
        (Flow.REPORT, True, False),
    ],
)
def test_each_flow_state_locks_the_nav_and_a_canvas_hides_the_title_bar(win, flow, locks, hides):
    assert flow.locks_nav is locks and flow.hides_title_bar is hides
    win.set_flow(flow)
    assert win.flow is flow
    assert all(b.isEnabled() is (not locks) for b in win.title_bar.buttons)
    assert win.title_bar.isHidden() is hides
    win.set_flow(Flow.IDLE)  # and back
    assert all(b.isEnabled() for b in win.title_bar.buttons) and not win.title_bar.isHidden()


def test_a_locked_nav_goes_nowhere(win):
    win.set_flow(Flow.CONFIGURE)
    for button in win.title_bar.buttons:
        button.click()  # disabled: Qt ignores the click
    win._go_to_tab(TESTS_INDEX)  # and the window refuses a direct request as well
    assert win.stack.currentIndex() == SETUP_INDEX


def test_set_nav_locked_is_the_one_lock(win):
    win._set_nav_locked(True)
    assert not any(b.isEnabled() for b in win.title_bar.buttons)
    win._set_nav_locked(False)
    assert all(b.isEnabled() for b in win.title_bar.buttons)


def test_the_title_bar_alone(qapp):
    bar = TitleBar()
    seen = []
    bar.navRequested.connect(seen.append)
    bar.tests_button.click()
    bar.setup_button.click()
    assert seen == [TESTS_INDEX, SETUP_INDEX]
    bar.set_active(TESTS_INDEX)
    assert [bool(b.property("active")) for b in bar.buttons] == [False, True]


def test_the_title_bar_paints_its_navy_background_so_the_light_text_is_readable(win):
    # FX5: a QWidget subclass paints a style-sheet background only with WA_StyledBackground;
    # without it the bar took the page colour and the light brand and nav text vanished.
    assert win.title_bar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    win.resize(900, 500)
    win.show()
    QApplication.processEvents()
    image = win.title_bar.grab().toImage()
    assert image.pixelColor(image.width() // 2, 2) == QColor(TITLEBAR_BG)
    assert image.pixelColor(2, image.height() // 2) == QColor(TITLEBAR_BG)
    assert QColor(TITLEBAR_TEXT).lightness() > QColor(TITLEBAR_BG).lightness() + 100  # light on navy


def test_the_title_bar_alone_has_the_styled_background_attribute(qapp):
    assert TitleBar().testAttribute(Qt.WidgetAttribute.WA_StyledBackground)


def test_the_output_root_is_the_default_configs(qapp):
    assert output_root_from_config() == "sessions"


# -- AA10: nothing about a subject or a task lives in the window -------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["_task_overrides", "_task_live_overrides", "_task_selected_profile", "_task_session_dirs",
     "tasks_page", "_active_assessment", "_active_task_id", "_hud_hidden", "results_page",
     "results_nav_button"],
)
def test_the_window_has_none_of_the_old_per_task_state(win, name):
    assert not hasattr(win, name)


def test_switching_the_subject_id_a_b_a_shows_each_subjects_own_tests(win):
    create_test(win.output_root, "A", "click_grid", name="A one")
    create_test(win.output_root, "B", "click_static", name="B one")
    create_test(win.output_root, "B", "scanning", name="B two")
    edit = win.setup_page.subject_id_edit
    edit.setText("A")
    win._go_to_tab(TESTS_INDEX)
    assert names(win) == ["A one"]
    win._go_to_tab(SETUP_INDEX)
    edit.setText("B")
    win._go_to_tab(TESTS_INDEX)
    assert names(win) == ["B one", "B two"]
    assert win.test_list_page.title_label.text() == "Test List for B"
    win._go_to_tab(SETUP_INDEX)
    edit.setText("A")
    win._go_to_tab(TESTS_INDEX)
    assert names(win) == ["A one"]


def test_typing_a_subject_id_changes_nothing_until_the_tab_is_opened(win):
    create_test(win.output_root, "A", "click_grid", name="A one")
    win.setup_page.subject_id_edit.setText("A")
    win._go_to_tab(TESTS_INDEX)
    win._go_to_tab(SETUP_INDEX)
    win.setup_page.subject_id_edit.setText("B")  # per keystroke, as typing does
    assert names(win) == ["A one"]  # the hidden list is not re-bound live (4A.8)


def test_a_flow_started_for_another_subjects_test_is_refused_at_the_source(win):
    # A test of another subject is simply not found for the subject typed in Setup: no
    # flow (Configure, Run or Report) can reach it.
    other = create_test(win.output_root, "B", "click_grid")
    win.setup_page.subject_id_edit.setText("TESTING")
    for open_flow in (win.config_flow.open, win.run_flow.open, win.report_flow.open):
        win.test_list_page.show_message("")
        open_flow(other.test_id)
        assert win.flow is Flow.IDLE and win.stack.count() == 2
        assert "could not be found" in win.test_list_page.message_label.text()
    assert win.config_flow.page is None and win.run_flow.page is None and win.report_flow.page is None


# -- Setup -> Tests ------------------------------------------------------------------------------------------


def test_continue_goes_to_the_test_list_only_when_setup_allows_it(win):
    create_test(win.output_root, "TESTING", "click_grid")
    win.setup_page.can_continue = lambda: False
    win.setup_page.continueRequested.emit()
    assert win.stack.currentIndex() == SETUP_INDEX
    win.setup_page.can_continue = lambda: True
    win.setup_page.continueRequested.emit()
    assert win.stack.currentIndex() == TESTS_INDEX
    assert names(win) == ["Grid Click 1"] and active(win) == [False, True]


def test_the_tests_tab_is_reachable_without_the_continue_gate(win):
    # No tracker, no calibration: AA15 / AA16.
    assert win.setup_page.client is None and win.setup_page.calibration_result is None
    win.tests_nav_button.click()
    assert win.stack.currentIndex() == TESTS_INDEX
    assert names(win) == []
    assert win.test_list_page.add_button.isEnabled()


def test_with_no_subject_id_the_tab_shows_the_empty_state(win):
    win.setup_page.subject_id_edit.setText("")
    win.tests_nav_button.click()
    page = win.test_list_page
    assert page.empty_label.text() == "Enter a Subject ID in Setup."
    assert not any(
        b.isEnabled()
        for b in (page.add_button, page.configure_button, page.run_button, page.report_button,
                  page.copy_button, page.delete_button)
    )
    assert not os.path.exists(win.output_root)  # nothing created on disk


def test_back_to_setup_returns_and_unlocks(win):
    win.tests_nav_button.click()
    win.test_list_page.back_button.click()
    assert win.stack.currentIndex() == SETUP_INDEX and active(win) == [True, False]


def test_the_tab_is_read_from_disk_every_time_it_opens(win):
    win._go_to_tab(TESTS_INDEX)
    assert names(win) == []
    create_test(win.output_root, "TESTING", "click_grid")  # as if another process wrote it
    win._go_to_tab(SETUP_INDEX)
    win._go_to_tab(TESTS_INDEX)
    assert names(win) == ["Grid Click 1"]


# -- AA16: no tracker connected ---------------------------------------------------------------------------------------


def test_without_a_tracker_add_configure_copy_delete_and_report_work(win, monkeypatch):
    assert win.setup_page.client is None
    page = win.test_list_page
    win._go_to_tab(TESTS_INDEX)
    page._choose_new_tests = lambda: ("click_grid", 2)
    page.add_button.click()
    assert names(win) == ["Grid Click 1", "Grid Click 2"]
    page.copy_button.click()
    assert names(win) == ["Grid Click 1", "Grid Click 2", "Grid Click 3"]
    page._confirm_delete = lambda test: True
    page.delete_button.click()
    assert names(win) == ["Grid Click 1", "Grid Click 2"]
    done = create_test(win.output_root, "TESTING", "scanning")
    folder = os.path.join(win.output_root, "2026-10-06_TESTING_scanning_run1")
    os.makedirs(folder)
    record_result(win.output_root, "TESTING", done.test_id, session_dir=folder,
                  planned_trials=6, completed_trials=6)
    page.reload()
    page.select_test(done.test_id)
    assert page.report_button.isEnabled()
    page.select_test(list_tests(win.output_root, "TESTING").tests[0].test_id)
    assert page.configure_button.isEnabled()
    page.configure_button.click()
    assert win.flow is Flow.CONFIGURE  # Configure works with no tracker


def test_run_test_is_on_for_a_not_done_test_whatever_the_tracker_says(win):
    test = create_test(win.output_root, "TESTING", "click_grid")
    win._go_to_tab(TESTS_INDEX)
    win.test_list_page.select_test(test.test_id)
    assert win.test_list_page.run_button.isEnabled()  # R2: the Start page shows the blockers


# -- the completer ----------------------------------------------------------------------------------------------------------------------


def test_a_subject_typed_today_is_offered_once_it_has_a_test(win):
    win.setup_page.subject_id_edit.setText("NEWKID")
    win._go_to_tab(TESTS_INDEX)
    page = win.test_list_page
    page._choose_new_tests = lambda: ("click_grid", 1)
    page.add_button.click()
    assert "NEWKID" in win.setup_page._subject_completer_model.stringList()


# -- AX3 (part): nothing of the retired pages or the per-task state is left in src/ -----------------------------


SRC = Path(__file__).resolve().parents[1] / "src"
RETIRED = (
    "OperatorPanel",
    "TasksPage",
    "ResultsPage",
    "_task_overrides",
    "_task_live_overrides",
    "_task_selected_profile",
    "_task_session_dirs",
)


def test_src_has_no_trace_of_the_retired_pages_or_the_per_task_dicts():
    found = [
        f"{path.relative_to(SRC)}: {name}"
        for path in SRC.rglob("*.py")
        for name in RETIRED
        if name in path.read_text(encoding="utf-8")
    ]
    assert found == []


def test_the_retired_page_modules_are_gone():
    assert not (SRC / "ui" / "tasks_page.py").exists()
    assert not (SRC / "ui" / "results_page.py").exists()


def test_the_start_pages_go_to_setup_returns_to_a_usable_setup_tab(win):
    # The window-level half of "Go to Setup": show_setup frees the nav and shows Setup.
    win.set_flow(Flow.START)
    win.show_setup()
    assert win.flow is Flow.IDLE and win.stack.currentIndex() == SETUP_INDEX
    assert all(b.isEnabled() for b in win.title_bar.buttons) and active(win) == [True, False]
