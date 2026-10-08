"""The run-end dialogs (SPEC-compass-task-flow.md 4C.6, 4C.8, U8, U14, HC7; AC11, AC12 dialog
side; wireframe ``run-end.md``): the safe answer is the default and what Esc gives."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from src.engine.run_result import DISCARD, SAVE, SAVE_AND_VIEW, RunResult
from src.ui.run_dialogs import (
    SavePartialDialog,
    TestCompleteDialog,
    ask_run_end,
    ask_save_partial,
    ask_test_complete,
    confirm_discard,
    confirm_quit,
    show_nothing_saved,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def answer(key: str | None) -> None:
    """Answer the next modal dialog from inside its event loop: click the button named
    ``key``, or (``None``) close it the way Esc does."""

    def respond():
        dialog = QApplication.activeModalWidget()
        if dialog is None:  # not open yet: look again shortly
            QTimer.singleShot(5, respond)
        elif key is None:
            dialog.reject()
        else:
            dialog.buttons[key].click()

    QTimer.singleShot(0, respond)


def labels(dialog) -> dict[str, str]:
    return {key: button.text() for key, button in dialog.buttons.items()}


def run_result(completed: int, planned: int = 18, outcome: str | None = None) -> RunResult:
    outcome = outcome or ("completed" if completed >= planned else "ended_early")
    return RunResult(
        "record", outcome, "finished" if outcome == "completed" else "operator_quit",
        planned, completed, 0, completed, Path("2026-10-06_P001_click_grid_run1"), "2026-10-06T16:00:00+08:00",
    )


# -- Test complete ------------------------------------------------------------


def test_test_complete_offers_save_save_and_view_and_discard(qapp):
    dialog = TestCompleteDialog()
    assert dialog.windowTitle() == "Test complete" and dialog.text_label.text() == "Test complete"
    assert labels(dialog) == {
        SAVE: "Save",
        SAVE_AND_VIEW: "Save and View Report",
        DISCARD: "Discard Results",
    }
    assert dialog.isModal()


def test_test_complete_close_or_esc_is_save_never_discard(qapp):
    dialog = TestCompleteDialog()
    assert dialog.choice == SAVE  # even before anything is chosen
    dialog.reject()
    assert dialog.choice == SAVE


@pytest.mark.parametrize("key", [SAVE, SAVE_AND_VIEW, DISCARD])
def test_test_complete_reports_the_button_pressed(qapp, key):
    dialog = TestCompleteDialog()
    dialog.buttons[key].click()
    assert dialog.choice == key


def test_the_enter_key_is_save_and_view_report_not_discard(qapp):
    dialog = TestCompleteDialog()
    defaults = [k for k, b in dialog.buttons.items() if b.isDefault()]
    assert defaults == [SAVE_AND_VIEW]


def test_test_complete_runs_as_a_real_modal_loop(qapp):
    answer(DISCARD)
    assert ask_test_complete() == DISCARD
    answer(None)
    assert ask_test_complete() == SAVE


# -- the other dialogs ---------------------------------------------------------


@pytest.mark.parametrize(("completed", "text"), [(7, "Save the 7 completed trials?"), (1, "Save the 1 completed trial?")])
def test_save_partial_names_how_many_trials(qapp, completed, text):
    dialog = SavePartialDialog(completed)
    assert dialog.text_label.text() == text
    assert labels(dialog) == {SAVE: "Save partial results", DISCARD: "Discard results"}
    assert dialog.windowTitle() == "Save partial results"


def test_save_partial_defaults_to_save_and_esc_saves(qapp):
    dialog = SavePartialDialog(7)
    assert [k for k, b in dialog.buttons.items() if b.isDefault()] == [SAVE]
    dialog.reject()
    assert dialog.choice == SAVE
    answer(DISCARD)
    assert ask_save_partial(None, 7) == DISCARD
    answer(None)
    assert ask_save_partial(None, 7) == SAVE


def test_confirm_quit_names_the_trials_and_keep_going_is_the_default(qapp):
    seen: dict[str, object] = {}

    def respond():
        dialog = QApplication.activeModalWidget()
        seen["text"] = dialog.text_label.text()
        seen["title"] = dialog.windowTitle()
        seen["labels"] = labels(dialog)
        seen["default"] = [k for k, b in dialog.buttons.items() if b.isDefault()]
        dialog.reject()

    QTimer.singleShot(0, respond)
    assert confirm_quit(None, 7, 18) is False  # Esc = Keep going
    assert seen == {
        "text": "Quit the test? 7 of 18 trials are done.",
        "title": "Quit the test?",
        "labels": {"quit": "Quit test", "keep": "Keep going"},
        "default": ["keep"],
    }
    answer("quit")
    assert confirm_quit(None, 7, 18) is True
    answer("keep")
    assert confirm_quit(None, 7, 18) is False


def test_confirm_discard_keep_is_the_default_and_esc_keeps(qapp):
    seen: dict[str, object] = {}

    def respond():
        dialog = QApplication.activeModalWidget()
        seen["text"] = dialog.text_label.text()
        seen["default"] = [k for k, b in dialog.buttons.items() if b.isDefault()]
        dialog.reject()

    QTimer.singleShot(0, respond)
    assert confirm_discard(None) is False
    assert seen == {"text": "Discard these results? This cannot be undone.", "default": ["keep"]}
    answer("discard")
    assert confirm_discard(None) is True
    answer("keep")
    assert confirm_discard(None) is False


def test_nothing_saved_is_a_plain_ok(qapp):
    seen: dict[str, object] = {}

    def respond():
        dialog = QApplication.activeModalWidget()
        seen["text"] = dialog.text_label.text()
        seen["labels"] = labels(dialog)
        dialog.buttons["ok"].click()

    QTimer.singleShot(0, respond)
    show_nothing_saved(None)
    assert seen == {
        "text": "No trials were completed, so nothing was saved.",
        "labels": {"ok": "OK"},
    }


# -- ask_run_end: the order the dialogs come in ----------------------------------


class Script:
    """Stands in for the dialogs and remembers which were shown, in order."""

    def __init__(self, complete=(), partial=(), confirm=()):
        self.shown: list[str] = []
        self._complete, self._partial, self._confirm = list(complete), list(partial), list(confirm)

    def complete(self, _parent):
        self.shown.append("complete")
        return self._complete.pop(0)

    def partial(self, _parent, completed):
        self.shown.append(f"partial({completed})")
        return self._partial.pop(0)

    def confirm(self, _parent):
        self.shown.append("confirm")
        return self._confirm.pop(0)

    def nothing(self, _parent):
        self.shown.append("nothing")

    def ask(self, result):
        return ask_run_end(
            result, None, complete=self.complete, partial=self.partial, confirm=self.confirm, nothing=self.nothing
        )


@pytest.mark.parametrize("choice", [SAVE, SAVE_AND_VIEW])
def test_a_completed_run_saves_without_any_confirmation(choice):
    script = Script(complete=[choice])
    assert script.ask(run_result(18)) == choice
    assert script.shown == ["complete"]


def test_discard_results_asks_once_more_and_discards_on_yes():
    script = Script(complete=[DISCARD], confirm=[True])
    assert script.ask(run_result(18)) == DISCARD
    assert script.shown == ["complete", "confirm"]


def test_keep_brings_test_complete_back():
    script = Script(complete=[DISCARD, SAVE_AND_VIEW], confirm=[False])
    assert script.ask(run_result(18)) == SAVE_AND_VIEW
    assert script.shown == ["complete", "confirm", "complete"]


def test_an_early_end_offers_save_partial_or_discard_with_no_extra_confirmation():
    save = Script(partial=[SAVE])
    assert save.ask(run_result(7)) == SAVE and save.shown == ["partial(7)"]
    discard = Script(partial=[DISCARD])
    assert discard.ask(run_result(7)) == DISCARD
    assert discard.shown == ["partial(7)"]  # it is already the second step of a confirmed quit


def test_no_finished_trial_means_no_choice_and_an_automatic_discard():
    script = Script()
    assert script.ask(run_result(0, outcome="ended_early")) == DISCARD
    assert script.shown == ["nothing"]


def test_the_real_dialogs_walk_a_completed_run_through_keep_then_save(qapp):
    keys = [DISCARD, "keep", SAVE]  # Test complete: Discard Results, then Keep, then back: Save
    asked: list[str] = []

    def respond():
        dialog = QApplication.activeModalWidget()
        if dialog is None:  # the next dialog is not open yet
            QTimer.singleShot(5, respond)
            return
        asked.append(dialog.windowTitle())
        dialog.buttons[keys.pop(0)].click()
        if keys:
            QTimer.singleShot(5, respond)

    QTimer.singleShot(0, respond)
    assert ask_run_end(run_result(18)) == SAVE
    assert asked == ["Test complete", "Discard results", "Test complete"]
