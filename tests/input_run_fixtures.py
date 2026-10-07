"""Shared rig of the input-selection run tests (``test_switch_run.py``,
``test_mouse_run.py``): an :class:`~src.app.AssessmentApp` built offscreen on a scratch
folder, with the mouse standing in for the gaze (or for the pointer of a Mouse test) and
the OS cursor never touched. Not a test module."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

import src.app as app_module
import src.ui.run_cursor as run_cursor_module
from src.app import AssessmentApp
from src.engine.calibration import CalibrationResult
from src.inputs.mouse_gaze import MouseGazeSource

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
# A 300 ms hover selects; no smoothing lag, no refractory, nothing waits between trials.
FAST = {
    "dwell.threshold_ms": 300,
    "dwell.refractory_ms": 0,
    "dwell.smoothing.enabled": False,
    "task.inter_trial_interval_ms": 0,
}


class Pointing:
    """A stand-in for the mouse position (a global QPoint)."""

    def __init__(self) -> None:
        self.pos = QPoint(0, 0)

    def __call__(self) -> QPoint:
        return self.pos

    def at_norm(self, canvas, x: float, y: float) -> None:
        self.pos = canvas.mapToGlobal(QPoint(round(x * canvas.width()), round(y * canvas.height())))


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def parked(monkeypatch):
    """The canvases the OS cursor was asked to be parked on (the real cursor never moves)."""
    calls: list = []
    monkeypatch.setattr(run_cursor_module, "_os_set_pos", calls.append)
    return calls


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch, parked):
    """Build apps writing under ``tmp_path/sessions``: no 500 ms pre-roll, calibration off,
    the global input mode ``eye`` whatever the local ``default.yaml`` says."""
    real_load = app_module.load_task_config
    root = tmp_path / "sessions"

    def load(task_id, *a, **k):
        cfg = real_load(task_id, *a, **k)
        cfg.setdefault("recording", {})["output_root"] = str(root)
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        cfg.setdefault("input", {})["mode"] = "eye"
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    monkeypatch.setattr(app_module, "preroll_ms", lambda mode: 0)
    made: list[AssessmentApp] = []

    def build(task_id="click_static", *, choice=None, trials=2, live=None, **kw):
        """``choice`` is the test's ``{"pointer", "selection"}``; ``client`` defaults to a
        mouse bound to the canvas as the tracker, ``client=None`` to *no* tracker."""
        structural = {"trials": trials}
        if choice:
            structural["input"] = dict(choice)
        structural.update(kw.pop("structural", {}))
        pointing = kw.pop("pointing", None) or Pointing()
        tracker = kw.pop("client", "mouse")
        if tracker == "mouse":
            tracker = MouseGazeSource(cursor_pos=pointing)
        if "pointer_source" not in kw and (choice or {}).get("pointer") == "mouse":
            kw["pointer_source"] = MouseGazeSource(cursor_pos=pointing)
        app = AssessmentApp(
            task_id,
            None,
            "P001",
            structural_overrides=structural,
            live_overrides={**FAST, **(live or {})},
            client=tracker,
            preset_calibration_result=VALID if tracker is not None else None,
            embedded=True,
            **kw,
        )
        app.timer.stop()  # the tests tick by hand
        # A canvas of a real size, so "on the target" and "off it" mean something.
        app.view.resize(1600, 900)
        app.view.layout().activate()
        if isinstance(tracker, MouseGazeSource):
            tracker.bind_canvas(app.canvas)  # the tracker's samples are the mouse's
        app.pointing = pointing
        made.append(app)
        return app

    build.root = root
    yield build
    for app in made:
        app.timer.stop()
        app.recorder.close()
        app.client.stop()


def events_of(app: AssessmentApp) -> list[dict]:
    path = app.recorder.session_dir / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def kinds(app: AssessmentApp, kind: str) -> list[dict]:
    return [e for e in events_of(app) if e["kind"] == kind]


def target_norm(app: AssessmentApp) -> tuple[float, float]:
    """Where the target of the trial now showing is, canvas-normalized."""
    task = app.task
    return task.target_position(task.targets[task._trial_index], 0)


def look_at_target(app: AssessmentApp) -> None:
    app.pointing.at_norm(app.canvas, *target_norm(app))


def look_away(app: AssessmentApp) -> None:
    """On the canvas, far from the target of the trial now showing."""
    x, y = target_norm(app)
    app.pointing.at_norm(app.canvas, 0.97 if x < 0.5 else 0.03, 0.97 if y < 0.5 else 0.03)


def tick(app: AssessmentApp, n: int = 1) -> None:
    for _ in range(n):
        app._tick()
        time.sleep(0.004)


def tick_until(app: AssessmentApp, condition, seconds: float = 8.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        time.sleep(0.004)


def finish_run(app: AssessmentApp, seconds: float = 12.0) -> None:
    """Hover each target in turn until the run has ended (a dwell selection)."""
    deadline = time.monotonic() + seconds
    while not app._shutdown_done:
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        if not app._shutdown_done and app.task.phase.name == "WAIT_INPUT":
            look_at_target(app)
        time.sleep(0.004)
