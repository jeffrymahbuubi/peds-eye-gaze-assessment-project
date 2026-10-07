"""Shared helpers of the Run Test / View Report flow tests (``test_run_flow.py``,
``test_run_flow_end.py``, ``test_report_flow.py``, ``test_dashboard_e2e.py``): a
``DashboardWindow`` on a scratch folder whose Setup tracker is a mouse, tests created
through the store, and a driver that ticks a run by hand. Not a test module."""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint

import src.app as app_module
from src.engine.calibration import CalibrationResult
from src.engine.run_result import SAVE
from src.engine.subject_tests import list_tests, update_test
from src.inputs.mouse_gaze import MouseGazeSource
from src.ui.dashboard_flow import Flow
from tests.dashboard_fixtures import SUBJECT, make_window

# A hover of 300 ms selects; nothing waits between trials, so a run is quick.
FAST_LIVE = {
    "dwell.threshold_ms": 300,
    "dwell.refractory_ms": 0,
    "dwell.smoothing.enabled": False,
    "task.inter_trial_interval_ms": 0,
}


class Pointing:
    """A stand-in for the mouse position (a global QPoint)."""

    def __init__(self):
        self.pos = QPoint(0, 0)

    def __call__(self):
        return self.pos


class Answers:
    """Stand-ins for what the operator is asked at the end of a run; they record it."""

    def __init__(self, action=SAVE):
        self.action = action
        self.asked = []
        self.told = []

    def install(self, flow):
        flow.ask_end = self.ask_end
        flow.tell = lambda title, text: self.told.append((title, text))

    def ask_end(self, result):
        self.asked.append(result)
        return self.action


def make_run_window(tmp_path, monkeypatch):
    """``(window, mouse, pointing)``: the Tests tab open for ``SUBJECT``, a mouse as the
    Setup page's tracker with a valid calibration, no Setup blockers (``win.blockers`` is
    the list ``run_blockers`` returns: a test fills it), and no 500 ms pre-roll, so a run
    can be driven in a second or two."""
    win = make_window(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "preroll_ms", lambda mode: 0)
    pointing = Pointing()
    mouse = MouseGazeSource(cursor_pos=pointing)
    win.setup_page._client = mouse
    win.setup_page._calibration_result = CalibrationResult(n_points=5, mean_error_px=10.0, valid=True)
    win.blockers = []
    win.setup_page.run_blockers = lambda: list(win.blockers)
    return win, mouse, pointing


def close_run_window(win):
    for app in (win.run_flow.app, win.config_flow.preview_app):
        if app is not None:
            app.timer.stop()
    win.close()


def configure_fast(win, test, trials=1, name="Fast hover", **structural):
    """Give the not-yet-run ``test`` a stored configuration that selects after a 300 ms hover."""
    return update_test(
        win.output_root,
        SUBJECT,
        test.test_id,
        configuration={
            "name": name,
            "live": dict(FAST_LIVE),
            "structural": {"trials": trials, **structural},
        },
    )


def open_start(win, test):
    """Select ``test`` on the Test List and press Run Test; returns the Start page."""
    win.test_list_page.reload()
    assert win.test_list_page.select_test(test.test_id)
    win.test_list_page.run_button.click()
    assert win.flow is Flow.START, win.test_list_page.message_label.text()
    return win.run_flow.page


def start_run(win, mouse, button="start_button"):
    """Press Start (or ``practice_button``) on the open Start page; returns the app,
    its timer stopped (the tests tick by hand) and the mouse bound to its canvas."""
    getattr(win.run_flow.page, button).click()
    app = win.run_flow.app
    assert app is not None, win.test_list_page.message_label.text()
    app.timer.stop()
    mouse.bind_canvas(app.view.canvas)
    return app


def tick_until(app, condition, seconds=8.0):
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        time.sleep(0.004)


def hover_current(app, pointing):
    """Put the mouse on the target of the trial now showing."""
    task = app.task
    x_norm, y_norm = task.target_position(task.targets[task._trial_index], 0)
    pointing.pos = app.canvas.mapToGlobal(
        QPoint(round(x_norm * app.canvas.width()), round(y_norm * app.canvas.height()))
    )


def finish_trials(app, pointing, count=None, seconds=10.0):
    """Hover each target in turn: ``count`` more trials, or (``None``) until the run has
    ended and the flow has taken over."""
    wanted = None if count is None else len(app.task.trials) + count
    deadline = time.monotonic() + seconds
    while not app._shutdown_done:
        if wanted is not None and len(app.task.trials) >= wanted:
            return
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        if not app._shutdown_done and app.task.phase.name == "WAIT_INPUT":
            hover_current(app, pointing)
        time.sleep(0.004)


def run_dirs(win):
    """The recorded run folders under the window's output root."""
    root = Path(win.output_root)
    return sorted(p for p in root.glob("*_run*") if p.is_dir()) if root.exists() else []


def stored_tests(win):
    return list_tests(win.output_root, SUBJECT).tests

