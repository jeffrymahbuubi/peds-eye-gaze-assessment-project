"""The Start screen (SPEC-compass-task-flow.md 4C.2-4C.4, U7, R2; AC1, AC2, AC3, AC5;
wireframe ``start-test.md``)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.engine.config import load_task_config
from src.engine.run_result import RunResult
from src.engine.task_info import TASK_INFO
from src.ui.start_test_page import BLOCKER_REFRESH_MS, HELP_TEXT, StartTestPage

TASKS = list(TASK_INFO)
NOT_CONNECTED = "The tracker is not connected. Connect it on the Setup page."
NO_CALIBRATION = "No calibration yet. Calibrate on the Setup page."


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Blockers:
    """A stand-in for ``SetupPage.run_blockers`` the test can change."""

    def __init__(self, *items: str):
        self.items = list(items)
        self.calls = 0

    def __call__(self) -> list[str]:
        self.calls += 1
        return list(self.items)


def make_page(task_id="click_grid", blockers=None, name="Grid Click 1", **values):
    page = StartTestPage()
    page.set_blockers_provider(blockers)
    cfg = load_task_config(task_id)
    cfg["task"]["trials"] = 18
    page.set_test(test_name=name, task_id=task_id, cfg=cfg, values=values or None)
    return page


def texts(page: StartTestPage) -> list[str]:
    return [label.text() for label in page.card.findChildren(QLabel)]


# -- AC1: what the page shows ----------------------------------------------------


def test_the_title_names_the_test(qapp):
    assert make_page().title_label.text() == "Start Grid Click 1"
    assert make_page(name="My own test").title_label.text() == "Start My own test"


@pytest.mark.parametrize("task_id", TASKS)
def test_every_task_shows_numbered_steps_a_note_and_the_clinician_block(qapp, task_id):
    page = make_page(task_id, **{"dwell.threshold_ms": 800, "task.timeout_ms": 8000})
    shown = texts(page)
    assert "Read aloud to the child" in shown and "For the clinician (not read aloud)" in shown
    assert page.heading_label.text() == f"Instructions for the {TASK_INFO[task_id][0]} test:"
    steps = [t for t in shown if t[:3] in ("1. ", "2. ", "3. ", "4. ")]
    assert len(steps) == 4 and [s[:2] for s in steps] == ["1.", "2.", "3.", "4."]
    assert page.note_label.text().startswith("NOTE: ") and "8 seconds" in page.note_label.text()
    assert any("0.8 seconds" in t for t in steps)
    assert all("{" not in t and "}" not in t for t in shown)
    clinician = shown[-3:]
    assert 'press ALT-P' in clinician[0] and 'press ALT-Q' in clinician[0]
    assert clinician[1].startswith("Practice runs 3 targets")
    assert clinician[2] == 'Start records 18 trials. Check that the bottom bar says "tracking OK" before you begin.'


def test_the_ring_and_dot_sentences_follow_the_tests_own_settings(qapp):
    both = " ".join(texts(make_page(**{"dwell.progress_ring": True, "dwell.visual_cursor": True})))
    neither = " ".join(texts(make_page(**{"dwell.progress_ring": False, "dwell.visual_cursor": False})))
    assert "A ring will fill up around it." in both and "small dot" in both
    assert "ring will fill" not in neither and "small dot" not in neither


def test_a_new_test_replaces_the_instructions_and_does_not_pile_them_up(qapp):
    page = make_page("click_grid")
    cfg = load_task_config("scanning")
    page.set_test(test_name="Scanning 1", task_id="scanning", cfg=cfg)
    assert page.title_label.text() == "Start Scanning 1"
    assert page.heading_label.text() == "Instructions for the Scanning Search test:"
    assert sum(1 for t in texts(page) if t.startswith("1. ")) == 1
    assert page.instructions.heading == page.heading_label.text()


def test_the_buttons_and_help_line(qapp):
    page = make_page()
    assert [b.text() for b in (page.start_button, page.practice_button, page.cancel_button)] == [
        "Start",
        "Practice",
        "Cancel",
    ]
    assert page.help_label.text() == HELP_TEXT == (
        "Help: From this screen you can begin the test. You may also practice 3 targets "
        "first; practice is not recorded. Read the instructions aloud to the child."
    )
    assert page.practice_label.isHidden()  # no practice yet


def test_no_button_is_the_default_so_enter_starts_nothing(qapp):
    page = make_page()
    for button in (page.start_button, page.practice_button, page.cancel_button, page.go_to_setup_button):
        assert not button.isDefault() and not button.autoDefault()


# -- AC2: the blockers -----------------------------------------------------------


def test_with_nothing_missing_the_banner_is_hidden_and_the_buttons_are_on(qapp):
    page = make_page(blockers=Blockers())
    assert page.banner.isHidden() and page.blockers() == []
    assert page.start_button.isEnabled() and page.practice_button.isEnabled()
    assert page.cancel_button.isEnabled()


def test_missing_things_are_listed_and_start_and_practice_go_off(qapp):
    page = make_page(blockers=Blockers(NOT_CONNECTED, NO_CALIBRATION))
    assert not page.banner.isHidden()
    assert page.banner_label.text() == (
        f"Still needed before you can start: {NOT_CONNECTED} · {NO_CALIBRATION}"
    )
    assert not page.start_button.isEnabled() and not page.practice_button.isEnabled()
    assert page.cancel_button.isEnabled()  # you can always go back
    assert page.go_to_setup_button.text() == "Go to Setup"


def test_the_banner_follows_the_blockers_when_they_change(qapp):
    blockers = Blockers(NOT_CONNECTED)
    page = make_page(blockers=blockers)
    assert not page.start_button.isEnabled()
    blockers.items = []
    assert page.refresh_blockers() == []
    assert page.banner.isHidden() and page.start_button.isEnabled()
    blockers.items = [NO_CALIBRATION]  # the tracker can drop at any moment
    page.refresh_blockers()
    assert page.banner_label.text().endswith(NO_CALIBRATION) and not page.practice_button.isEnabled()


def test_with_no_provider_nothing_blocks(qapp):
    page = make_page(blockers=None)
    assert page.blockers() == [] and page.start_button.isEnabled()


def test_a_stale_enabled_button_still_cannot_launch(qapp):
    """The handlers read the blockers again: the page may not have refreshed since the tracker dropped."""
    blockers = Blockers()
    page = make_page(blockers=blockers)
    started, practised = [], []
    page.startRequested.connect(lambda: started.append(1))
    page.practiceRequested.connect(practised.append)
    blockers.items = [NOT_CONNECTED]  # no timer tick yet: the buttons still look enabled
    assert page.start_button.isEnabled()
    page.start_button.click()
    page.practice_button.click()
    assert started == [] and practised == []
    assert not page.start_button.isEnabled()  # ... and now they look disabled too


def test_the_blockers_are_read_when_the_page_is_shown_and_every_second_while_visible(qapp):
    blockers = Blockers()
    page = make_page(blockers=blockers)
    page.show()
    assert page._timer.isActive() and page._timer.interval() == BLOCKER_REFRESH_MS == 1000
    calls = blockers.calls
    blockers.items = [NOT_CONNECTED]
    page._timer.timeout.emit()
    assert blockers.calls == calls + 1 and not page.start_button.isEnabled()
    page.hide()
    assert not page._timer.isActive()  # not polling while another page is showing
    page.close()


def test_go_to_setup_and_cancel_are_signals(qapp):
    page = make_page(blockers=Blockers(NOT_CONNECTED))
    seen: list[str] = []
    page.goToSetupRequested.connect(lambda: seen.append("setup"))
    page.cancelRequested.connect(lambda: seen.append("cancel"))
    page.go_to_setup_button.click()
    page.cancel_button.click()
    assert seen == ["setup", "cancel"]


def test_esc_is_cancel(qapp):
    page = make_page()
    seen: list[str] = []
    page.cancelRequested.connect(lambda: seen.append("cancel"))
    assert page._cancel_shortcut.key().toString() == "Esc"
    assert page._cancel_shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    page._cancel_shortcut.activated.emit()
    assert seen == ["cancel"]


# -- Start / Practice --------------------------------------------------------------


def test_start_emits_once_per_press(qapp):
    page = make_page(blockers=Blockers())
    seen: list[int] = []
    page.startRequested.connect(lambda: seen.append(1))
    page.start_button.click()
    assert seen == [1]


def test_each_practice_press_carries_its_own_number_so_the_seeds_differ(qapp):
    page = make_page(blockers=Blockers())
    numbers: list[int] = []
    page.practiceRequested.connect(numbers.append)
    for _ in range(3):
        page.practice_button.click()
    assert numbers == [0, 1, 2] and page.practice_count == 3  # AC5: repeatable, a new seed each time


def test_a_new_test_starts_the_practice_count_again(qapp):
    page = make_page(blockers=Blockers())
    page.practice_button.click()
    page.practice_button.click()
    page.set_test(test_name="Grid Click 2", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert page.practice_count == 0


def practice_result(hits: int, outcome="completed") -> RunResult:
    return RunResult("practice", outcome, "finished" if outcome == "completed" else "operator_quit", 3, 3, 0, hits, None, "2026-10-06T16:00:00+08:00")


def test_the_practice_line_appears_after_a_finished_practice(qapp):
    page = make_page()
    page.show()
    page.set_practice_result(practice_result(3))
    assert page.practice_label.isVisible()
    assert page.practice_label.text() == "Practice finished: 3 of 3 selected. You can practice again or press Start."
    page.set_practice_result(practice_result(2))
    assert page.practice_label.text().startswith("Practice finished: 2 of 3 selected.")
    page.close()


def test_a_quit_practice_says_nothing_and_a_new_test_clears_the_line(qapp):
    page = make_page()
    page.set_practice_result(practice_result(3))
    page.set_practice_result(practice_result(1, outcome="ended_early"))
    assert page.practice_label.isHidden() and page.practice_label.text() == ""
    page.set_practice_result(practice_result(3))
    page.set_test(test_name="Grid Click 2", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert page.practice_label.isHidden()
    page.set_practice_result(practice_result(3))
    page.set_practice_result(None)
    assert page.practice_label.isHidden()


def test_a_scrolling_card_keeps_the_buttons_outside_it(qapp):
    """The card scrolls above the buttons, so a small or scaled window never clips Start."""
    page = make_page()
    assert page.card.parent() is not page and page.start_button.parent() is page


# -- show_note: a line from the host when a run could not start ------------------------------


def test_the_host_can_say_why_a_run_could_not_start_and_the_buttons_stay_usable(qapp):
    page = make_page()
    assert page.message_label.isHidden()
    page.show_note("Could not start Grid Click 1: disk is read-only")
    assert not page.message_label.isHidden()
    assert page.message_label.text() == "Could not start Grid Click 1: disk is read-only"
    assert page.start_button.isEnabled() and page.practice_button.isEnabled() and page.cancel_button.isEnabled()
    page.show_note("")
    assert page.message_label.isHidden() and page.message_label.text() == ""


@pytest.mark.parametrize("button", ["start_button", "practice_button"])
def test_the_next_start_or_practice_press_clears_the_note(qapp, button):
    page = make_page()
    page.show_note("Could not start Grid Click 1: no")
    getattr(page, button).click()
    assert page.message_label.isHidden()


def test_a_practice_result_or_a_new_test_clears_the_note(qapp):
    page = make_page()
    page.show_note("Could not start Grid Click 1: no")
    page.set_practice_result(practice_result(3))
    assert page.message_label.isHidden()
    page.show_note("Could not start Grid Click 1: no")
    page.set_test(test_name="Grid Click 2", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert page.message_label.isHidden()
