"""SPEC-audit-fixes.md through ``AssessmentApp``: H5/F2 (what a run that dies leaves, and the
files of a normal run), H6/F3 (no stale gaze rows), H7/F4 and H8/F6 (the calibration file and
the CLI's fresh calibration), H9/F7 (a stepped wall clock moves nothing) and H11/F9 (a failed
start leaves no orphan folder). Offscreen Qt, a scratch folder, a replay fixture or a stand-in
tracker; nothing touches a device or a port.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp
from src.data.exporter import load_gaze_rows, load_trials_rows
from src.data.schema import GazeSample, TrialRecord
from src.engine.calibration import CalibrationFileError, CalibrationResult, save_calibration_result
from src.engine.clock import now_ns
from src.inputs.mouse_gaze import MouseGazeSource
from src.tasks.base_task import Phase

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
TIMED_OUT = CalibrationResult(n_points=5, mean_error_px=None, valid=False)
FAST = {"dwell.smoothing.enabled": False, "dwell.refractory_ms": 0}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch):
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

    def build(task_id="click_static", replay=True, embedded=True, **kw):
        kw.setdefault("preset_calibration_result", VALID)
        app = AssessmentApp(task_id, str(FIXTURE) if replay else None, "P001", embedded=embedded, **kw)
        app.timer.stop()  # the tests tick by hand
        made.append(app)
        return app

    build.root = root
    yield build
    for app in made:
        app.timer.stop()
        if not app._shutdown_done:
            app.recorder.close()
            app._shutdown_done = True  # the teardown ends the run: a window close must not ask
        app.client.stop()
        if app.window is not None:
            app.window.close()


class FakeTracker:
    """A live-looking tracker whose last sample and link the test controls."""

    is_live = True
    device_info = None

    def __init__(self) -> None:
        self.sample: GazeSample | None = None
        self.connected = True

    def latest(self):
        return self.sample

    def is_connected(self) -> bool:
        return self.connected

    def connect(self, *a, **k) -> None: ...
    def start_streaming(self) -> None: ...
    def stop(self) -> None: ...
    def clear_raw(self) -> None: ...

    def drain_raw(self):
        return []


class Pointing:
    def __init__(self) -> None:
        self.pos = QPoint(0, 0)

    def __call__(self) -> QPoint:
        return self.pos


def gaze_sample(t_ns: int | None = None) -> GazeSample:
    return GazeSample(t_ns=now_ns() if t_ns is None else t_ns, x=0.5, y=0.5, valid=True)


def legacy_trials_csv(trials: list[TrialRecord]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=TrialRecord.csv_header())
    writer.writeheader()
    for trial in trials:
        writer.writerow(trial.as_row())
    return buffer.getvalue().encode("utf-8")


def to_wait_input(app: AssessmentApp) -> None:
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT


def finish_one_trial(app: AssessmentApp) -> None:
    to_wait_input(app)
    app._skip_trial()
    app._tick()


def run_folders(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("*/runs/*/*") if p.is_dir()) if root.exists() else []


# -- H5/F2: what a run that dies leaves ---------------------------------------------------------------------


def test_a_run_that_dies_after_a_trial_leaves_its_metadata_and_the_finished_trial(make_app):
    app = make_app(structural_overrides={"trials": 4}, live_overrides={"task.inter_trial_interval_ms": 0})
    folder = app.recorder.session_dir
    finish_one_trial(app)
    # No _shutdown, no close(): what a killed process or a closed window used to lose.
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["complete"] is False and meta["subject_id"] == "P001"
    assert meta["tasks"] == ["click_static"] and meta["settings"]["structural"]["trials"] == 4
    (row,) = load_trials_rows(folder)
    assert row["is_skipped"] == "1" and row["trial_id"] == "0"


def test_a_normal_runs_trial_table_is_the_legacy_one_and_its_metadata_is_complete(make_app):
    app = make_app(structural_overrides={"trials": 3}, live_overrides={"task.inter_trial_interval_ms": 0})
    folder = app.recorder.session_dir
    for _ in range(2):
        finish_one_trial(app)
    app._shutdown()
    assert len(app.task.trials) >= 2
    assert (folder / "trials.csv").read_bytes() == legacy_trials_csv(app.task.trials)
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True and meta["outcome"] == "ended_early"


def test_the_standalone_window_asks_before_closing_a_run(make_app):
    """The CLI path: the X button and Alt+F4 go through the same quit question as Alt-Q."""
    app = make_app(embedded=False)
    app.window.show()  # run_gui does this after building the app
    assert app.window.close_guard is not None
    asked = []

    def keep_going(parent, completed, planned):
        asked.append((completed, planned))
        return False

    app.confirm_quit = keep_going
    app.window.close()
    assert asked and not app.is_finished and app.window.isVisible()  # asked, and the run goes on
    assert not app._paused  # Keep going resumes

    app.confirm_quit = lambda parent, completed, planned: True
    app.window.close()
    assert app.is_finished
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True and meta["ended_by"] == "operator_quit"
    app.window.close()  # once the run is over the window simply closes
    assert not app.window.isVisible()


# -- H6/F3: no stale gaze rows --------------------------------------------------------------------------------


def test_a_disconnect_records_no_gaze_rows_and_a_repeated_sample_once(make_app):
    tracker = FakeTracker()
    app = make_app(client=tracker, replay=False)
    folder = app.recorder.session_dir
    for _ in range(3):
        tracker.sample = gaze_sample()
        app._tick()
    app._tick()  # the loop ran faster than the device: the same stamp again, not written again
    app._tick()
    tracker.connected = False  # Control was closed; this stand-in still hands back the old sample
    for _ in range(10):
        app._tick()
    app._shutdown()
    assert len(load_gaze_rows(folder)) == 3
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert not [e for e in events if e["kind"] == "LATENCY_SAMPLE" and e["n_samples"] > 3]


def test_recording_resumes_with_the_reconnect(make_app):
    tracker = FakeTracker()
    app = make_app(client=tracker, replay=False)
    tracker.sample = gaze_sample()
    app._tick()
    tracker.connected = False
    app._tick()
    tracker.connected = True
    tracker.sample = gaze_sample()
    app._tick()
    app._shutdown()
    assert len(load_gaze_rows(app.recorder.session_dir)) == 2


# -- H7/F4 and H8/F6: the calibration file on the CLI path -----------------------------------------------------


def test_a_calibration_file_marked_not_valid_fails_fast_before_anything_is_made(make_app, tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", TIMED_OUT)
    with pytest.raises(CalibrationFileError, match="not valid"):
        make_app(calibration_file=str(path), preset_calibration_result=None)
    assert not make_app.root.exists()


def test_the_calibration_file_subject_matches_ignoring_case(make_app, tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "p001", VALID)  # saved as typed another day
    app = make_app(calibration_file=str(path), preset_calibration_result=None)
    assert app.metadata.calibration_source == "loaded"
    other = tmp_path / "other.json"
    save_calibration_result(other, "P002", VALID)
    with pytest.raises(CalibrationFileError, match="does not match"):
        make_app(calibration_file=str(other), preset_calibration_result=None)


class FreshCalibration:
    """Stands in for ``Calibration`` on the CLI path: a real (not stub) fresh calibration."""

    result = VALID
    is_stub = False

    def __init__(self, client, **kwargs) -> None: ...

    def run(self) -> CalibrationResult:
        return FreshCalibration.result


@pytest.mark.parametrize(("result", "saved"), [(VALID, True), (TIMED_OUT, False)])
def test_the_cli_saves_a_fresh_calibration_only_when_it_is_valid(make_app, monkeypatch, result, saved):
    monkeypatch.setattr(app_module, "Calibration", FreshCalibration)
    FreshCalibration.result = result
    app = make_app(client=FakeTracker(), replay=False, preset_calibration_result=None)
    assert (app.recorder.session_dir / "calibration.json").is_file() is saved


# -- H9/F7: the in-run clock --------------------------------------------------------------------------------------


def test_a_stepped_wall_clock_does_not_complete_a_dwell(make_app, monkeypatch):
    pointing = Pointing()
    mouse = MouseGazeSource(cursor_pos=pointing)
    app = make_app(
        run_mode="preview",
        client=mouse,
        replay=False,
        structural_overrides={"trials": 1},
        live_overrides={**FAST, "dwell.threshold_ms": 5000},
    )
    mouse.bind_canvas(app.canvas)
    app._tick()  # trial 1 is shown
    x_norm, y_norm = app.task.target_position(app.task.targets[0], 0)
    pointing.pos = app.canvas.mapToGlobal(
        QPoint(round(x_norm * app.canvas.width()), round(y_norm * app.canvas.height()))
    )
    app._tick()
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT and not app.task.trials
    wall = time.time_ns()
    monkeypatch.setattr(time, "time_ns", lambda: wall + 3600 * 10**9)  # the clock is set an hour ahead
    app._tick()
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT and not app.task.trials  # a few ms passed, not an hour


def test_a_run_is_stamped_in_the_epoch_ns_domain(make_app):
    app = make_app(structural_overrides={"trials": 2})
    to_wait_input(app)
    app._skip_trial()
    app._shutdown()
    (row,) = [r for r in load_trials_rows(app.recorder.session_dir)][:1]
    assert abs(int(row["t_target_shown_ns"]) - time.time_ns()) < 3600 * 10**9
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    assert abs(meta["started_ns"] - time.time_ns()) < 3600 * 10**9  # the real wall clock, as before


# -- H11/F9: a failed start leaves no orphan folder --------------------------------------------------------------------


def test_a_start_that_fails_after_the_calibration_was_saved_leaves_no_folder(make_app, monkeypatch):
    class Refusing:
        def __init__(self, *args, **kwargs) -> None:
            raise OSError("disk full")

    monkeypatch.setattr(app_module, "SessionRecorder", Refusing)
    with pytest.raises(OSError, match="disk full"):
        # The preset calibration is written into the new run folder first.
        make_app(client=FakeTracker(), replay=False)
    assert run_folders(make_app.root) == []
    assert (make_app.root / "P001" / "subject.json").is_file()  # the subject's own folder stays


def test_a_start_that_fails_after_the_recorder_opened_keeps_what_was_written(make_app, monkeypatch):
    """Pins H11 as written: only a folder holding nothing but calibration.json is removed. The
    recorder's own files are data, however the run ended (see the SPEC's section 9)."""

    def refusing(*args, **kwargs):
        raise ValueError("a stored value this task rejects")

    monkeypatch.setattr(app_module, "build_task", refusing)
    with pytest.raises(ValueError):
        make_app(client=FakeTracker(), replay=False)
    (folder,) = run_folders(make_app.root)
    assert (folder / "calibration.json").is_file() and (folder / "events.jsonl").is_file()
