"""SPEC-audit-fixes.md H4 (F2, U3): closing the dashboard window (X, Alt+F4) during a run asks
the quit question like Alt-Q, and once the run has ended normally (every file written) the
window closes; a Preview quits at once; a busy Setup thread is waited for. Offscreen Qt, a
scratch folder, a mouse for the tracker."""

from __future__ import annotations

import json
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.data.exporter import load_trials_rows
from src.engine.run_result import SAVE
from src.ui import setup_page as setup_page_module
from src.ui.dashboard_flow import Flow
from tests.dashboard_fixtures import new_test, open_page
from tests.run_flow_fixtures import (
    Answers,
    close_run_window,
    configure_fast,
    finish_trials,
    make_run_window,
    open_start,
    start_run,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    win.show()
    yield win, mouse, pointing
    close_run_window(win)


class Question:
    """A stand-in for the quit question: records that it was asked, answers as told."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[tuple[int, int]] = []

    def __call__(self, parent, completed: int, planned: int) -> bool:
        self.asked.append((completed, planned))
        return self.answer


def begin(win, mouse, trials=3, button="start_button"):
    test = new_test(win)
    configure_fast(win, test, trials=trials)
    open_start(win, test)
    return start_run(win, mouse, button)


def settle() -> None:
    QApplication.processEvents()


# -- a recorded run (U3) ----------------------------------------------------------------------------------------


def test_closing_during_a_recorded_run_asks_then_writes_every_file_and_closes(rig):
    win, mouse, pointing = rig
    answers = Answers(SAVE)
    answers.install(win.run_flow)
    app = begin(win, mouse)
    folder = app.recorder.session_dir
    finish_trials(app, pointing, count=1)
    question = app.confirm_quit = Question(True)

    win.close()  # the X button / Alt+F4

    assert len(question.asked) == 1 and question.asked[0][0] == 1  # one trial was done
    assert app.is_finished
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True and meta["outcome"] == "ended_early" and meta["ended_by"] == "operator_quit"
    assert len(load_trials_rows(folder)) == 1
    (result,) = answers.asked  # the run ended the normal way: the Save question was put
    assert result.session_dir == folder and result.completed == 1
    assert win.isVisible()  # not yet: the close is deferred out of the close event
    settle()
    assert not win.isVisible()  # now the window closes


def test_keep_going_leaves_the_window_open_and_forgets_the_close(rig):
    win, mouse, pointing = rig
    Answers(SAVE).install(win.run_flow)
    app = begin(win, mouse)
    question = app.confirm_quit = Question(False)

    win.close()

    assert len(question.asked) == 1 and not app.is_finished
    assert win.flow is Flow.RUN and win.isVisible()
    assert not app._paused  # Keep going resumes the run
    assert win._close_pending is False
    settle()
    assert win.isVisible()
    # The run later ends by itself: nothing remembered, so the window stays.
    finish_trials(app, pointing)
    settle()
    assert win.isVisible()


def test_a_close_while_the_run_end_dialogs_are_up_waits_for_them(rig):
    win, mouse, pointing = rig
    app = begin(win, mouse, trials=1)
    seen = []

    def ask_end(result):
        win.close()  # the window is asked to close while the Save question is showing
        seen.append((win.flow, win.isVisible()))
        return SAVE

    win.run_flow.ask_end = ask_end
    win.run_flow.tell = lambda title, text: None
    finish_trials(app, pointing)
    assert seen == [(Flow.FINISHING, True)]  # ignored, remembered
    settle()
    assert not win.isVisible()  # and honoured once the run was saved


def test_a_practice_ends_at_once_and_the_window_closes(rig):
    win, mouse, _pointing = rig
    app = begin(win, mouse, button="practice_button")
    question = app.confirm_quit = Question(True)
    win.close()
    assert question.asked == []  # nothing is recorded: no question
    assert app.is_finished and win.flow is Flow.START
    settle()
    assert not win.isVisible()


def test_a_preview_quits_at_once_and_the_window_closes(rig):
    win, _mouse, _pointing = rig
    page = open_page(win, new_test(win))
    page.preview_button.click()
    app = win.config_flow.preview_app
    assert app is not None and win.flow is Flow.PREVIEW
    app.timer.stop()
    win.close()
    assert app.is_finished and win.flow is Flow.CONFIGURE and win.config_flow.preview_app is None
    assert not win.isVisible()  # no deferral: nothing was recorded


def test_outside_a_run_the_window_just_closes(rig):
    win, _mouse, _pointing = rig
    assert win.flow is Flow.IDLE
    win.close()
    assert not win.isVisible()


# -- the Setup threads (H4) -----------------------------------------------------------------------------------------


class SlowCalibration:
    started = threading.Event()

    def __init__(self, client, **kwargs) -> None:
        self.client = client

    def run(self):
        SlowCalibration.started.set()
        deadline = time.monotonic() + 20
        while not self.client.stopped and time.monotonic() < deadline:
            time.sleep(0.01)
        return setup_page_module.CalibrationResult(n_points=5, mean_error_px=None, valid=False)


class Client:
    stopped = False

    def is_connected(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


def test_closing_during_a_calibration_waits_for_its_thread(rig, monkeypatch):
    win, _mouse, _pointing = rig
    SlowCalibration.started = threading.Event()
    monkeypatch.setattr(setup_page_module, "Calibration", SlowCalibration)
    setup = win.setup_page
    setup._client = Client()
    setup._on_state_changed()
    setup.do_calibration_button.click()
    assert SlowCalibration.started.wait(5)
    thread = setup._calibration_thread
    assert thread is not None and thread.isRunning()

    win.close()  # must not leave a running QThread to be destroyed

    assert not thread.isRunning()
    assert setup._client.stopped
    assert not win.isVisible()
