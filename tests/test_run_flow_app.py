"""The run flow through ``AssessmentApp`` with no HUD (SPEC-compass-task-flow.md 4C.4-4C.8, P7b):
the run bar's status and buttons, Pause (the paused tick), Skip, the Quit question, the
``RunResult`` handed to ``on_finished``, and the standalone ``--task X --gui`` path (AC7-AC11,
AC15). Offscreen; the clock is the real one, so timeouts are a few hundred ms at most."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp
from src.data.analysis_export import read_all_gaze
from src.engine.calibration import CalibrationResult
from src.engine.clock import now_ns
from src.engine.run_result import RunResult
from src.inputs.mouse_gaze import MouseGazeSource
from src.tasks.base_task import Phase

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
FAST = {"dwell.smoothing.enabled": False, "dwell.refractory_ms": 0}
LONG_TRIAL = {**FAST, "task.timeout_ms": 600_000, "task.inter_trial_interval_ms": 0}


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
        cfg.setdefault("app", {})["fullscreen"] = False
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    monkeypatch.setattr(app_module, "preroll_ms", lambda mode: 0)
    made: list[AssessmentApp] = []
    results: list[RunResult] = []

    def build(task_id="click_static", replay=True, embedded=True, **kw):
        kw.setdefault("preset_calibration_result", VALID)
        app = AssessmentApp(
            task_id,
            str(FIXTURE) if replay else None,
            "P001",
            embedded=embedded,
            on_finished=results.append,
            **kw,
        )
        app.timer.stop()  # the tests tick by hand
        made.append(app)
        return app

    build.root, build.results = root, results
    yield build
    for app in made:
        app.timer.stop()
        if not app._shutdown_done:
            app.recorder.close()
            app._shutdown_done = True  # the teardown ends the run: the window close must not ask (H4)
        app.client.stop()
        if app.window is not None:
            app.window.close()


def tick_until(app: AssessmentApp, condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        time.sleep(0.005)


def to_wait_input(app: AssessmentApp) -> None:
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT


def metadata_of(app: AssessmentApp) -> dict:
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def events_of(app: AssessmentApp) -> list[dict]:
    path = app.recorder.session_dir / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def esc_event() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)


class Answer:
    """A ``confirm_quit`` replacement: answers, and remembers what the app looked like when asked."""

    def __init__(self, app: AssessmentApp, quit_it: bool):
        self.app, self.quit_it, self.calls = app, quit_it, []

    def __call__(self, parent, completed, planned) -> bool:
        self.calls.append(
            {
                "parent": parent,
                "completed": completed,
                "planned": planned,
                "paused": self.app._paused,
                "canvas_paused": self.app.canvas.paused,
            }
        )
        return self.quit_it


# -- the run view has no HUD (AC7, AC14) ------------------------------------------


def test_the_run_view_is_a_canvas_and_a_run_bar(make_app):
    app = make_app()
    assert not hasattr(app, "operator_panel") and not hasattr(app.view, "operator_panel")
    assert app.view.run_bar.pause_button.text() == "Pause (Alt-P)"
    assert [app.view.run_bar.skip_button.text(), app.view.run_bar.quit_button.text()] == [
        "Skip trial",
        "Quit (Alt-Q)",
    ]


def test_a_hud_hidden_argument_no_longer_exists(make_app):
    with pytest.raises(TypeError):
        make_app(hud_hidden=True)


# -- the status line (4C.5, AC8) -----------------------------------------------------


def test_the_status_reads_trial_i_of_n_and_tracking(make_app):
    app = make_app(structural_overrides={"trials": 12})
    now = time.time_ns()
    app._last_valid_ns = now
    app._update_run_bar(now)
    assert app.view.run_bar.status_text() == "Trial 1 of 12, Tracking OK"
    app._last_valid_ns = now - 3_200_000_000
    app._update_run_bar(now)
    assert app.view.run_bar.status_text() == "Trial 1 of 12, No gaze for 3 s"
    app._last_valid_ns = None
    app._update_run_bar(now)
    assert app.view.run_bar.status_text() == "Trial 1 of 12, Waiting for gaze"
    app.client.is_connected = lambda: False
    app._update_run_bar(now)
    assert app.view.run_bar.status_text() == "Trial 1 of 12, Tracker disconnected"


def test_the_status_counts_trials_as_the_run_goes_on(make_app):
    app = make_app(structural_overrides={"trials": 4}, live_overrides={**FAST, "task.timeout_ms": 600_000})
    to_wait_input(app)
    assert app.view.run_bar.status_text().startswith("Trial 1 of 4, ")
    app._skip_trial()
    tick_until(app, lambda: app.task.phase is Phase.WAIT_INPUT)
    assert app.view.run_bar.status_text().startswith("Trial 2 of 4, ")


def test_practice_marks_the_status_and_turns_the_bar_amber(make_app):
    app = make_app(run_mode="practice", structural_overrides={"trials": 3})
    app._tick()
    assert app.view.run_bar.status_text().startswith("PRACTICE, Trial 1 of 3, ")
    assert app.view.run_bar.property("practice") is True
    record = make_app(structural_overrides={"trials": 3})
    record._tick()
    assert not record.view.run_bar.status_text().startswith("PRACTICE")
    assert record.view.run_bar.property("practice") is False


def test_a_preview_names_the_mouse_and_its_chip_says_nothing_is_recorded(make_app):
    mouse = MouseGazeSource()
    app = make_app(run_mode="preview", client=mouse, replay=False, structural_overrides={"trials": 3})
    mouse.bind_canvas(app.canvas)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer"
    app.view.run_bar.pause_button.click()
    assert app.view.run_bar.status_text() == "PREVIEW, Paused"


# -- Pause (4C.6, AC9) -----------------------------------------------------------------


def test_pause_drops_the_trial_in_flight_and_shows_the_paused_screen(make_app):
    app = make_app(live_overrides=LONG_TRIAL)
    to_wait_input(app)
    first_target = app.task.target_position(app.task.targets[0], 0)
    app.view.run_bar.pause_button.click()
    assert app._paused and app.canvas.paused
    assert app.view.run_bar.pause_button.text() == "Resume (Alt-P)"
    assert app.view.run_bar.status_text() == f"Paused, Trial 1 of {len(app.task.targets)}"
    assert app.task.trials == []  # the interrupted attempt is not a row
    assert not app.view.run_bar.skip_button.isEnabled()
    app.view.run_bar.pause_button.click()
    assert not app._paused and not app.canvas.paused
    assert app.view.run_bar.pause_button.text() == "Pause (Alt-P)"
    app._tick()  # the same target comes back, as a fresh trial
    assert app.task.phase is Phase.WAIT_INPUT and app.task.trial_number == 1
    assert app.task.target_position(app.task.targets[0], 0) == first_target
    kinds = [e["kind"] for e in events_of(app) if e["kind"] in ("PAUSED", "TRIAL_INTERRUPTED", "RESUMED")]
    assert kinds == ["TRIAL_INTERRUPTED", "PAUSED", "RESUMED"]
    meta_events = {e["kind"]: e for e in events_of(app)}
    assert meta_events["PAUSED"]["interrupted"] is True and meta_events["TRIAL_INTERRUPTED"]["reason"] == "pause"


def test_a_pause_longer_than_the_timeout_creates_no_timeout(make_app):
    app = make_app(live_overrides={**FAST, "task.timeout_ms": 300, "task.inter_trial_interval_ms": 0})
    to_wait_input(app)
    app._set_paused(True)
    deadline = time.monotonic() + 0.5  # longer than the whole trial
    while time.monotonic() < deadline:
        app._tick()
        time.sleep(0.01)
    app._set_paused(False)
    app._tick()
    assert app.task.trials == [] and app.task.phase is Phase.WAIT_INPUT  # fresh clock, no timeout


def test_a_paused_tick_updates_nothing_and_records_no_gaze_but_drains_the_raw_queue(make_app, monkeypatch):
    app = make_app(live_overrides=LONG_TRIAL)
    to_wait_input(app)
    app._set_paused(True)
    updates, rows, drains = [], [], []
    monkeypatch.setattr(app.task, "update", lambda *a, **k: updates.append(1))
    monkeypatch.setattr(app.recorder, "record_gaze", lambda s: rows.append(s))
    real_drain = app.client.drain_raw
    monkeypatch.setattr(app.client, "drain_raw", lambda: drains.append(1) or real_drain())
    for _ in range(5):
        app._tick()
    assert updates == [] and rows == [] and len(drains) == 5
    app._set_paused(False)
    monkeypatch.undo()


def test_pausing_in_the_iti_interrupts_nothing(make_app):
    app = make_app(live_overrides={**FAST, "task.timeout_ms": 600_000, "task.inter_trial_interval_ms": 2000})
    to_wait_input(app)
    app._skip_trial()
    assert app.task.phase is Phase.ITI
    app._set_paused(True)
    assert app.task.interrupted_trials == 0 and not app._pause_interrupted
    assert app.view.run_bar.status_text() == f"Paused, Trial 1 of {len(app.task.targets)}"
    app._set_paused(False)
    assert app.task.phase is Phase.ITI


def test_pause_time_is_not_in_the_raw_file(make_app):
    from tests.test_run_modes_app import RawQueueClient

    client = RawQueueClient()
    app = make_app(client=client, replay=False, live_overrides=LONG_TRIAL)
    client.queue("0.7", t0=1.0)
    to_wait_input(app)
    app._set_paused(True)
    client.queue("0.8", t0=2.0)  # arrives while paused: drained by the paused tick, thrown away
    app._tick()
    client.queue("0.9", t0=3.0)  # arrives after the last paused tick: the final drain throws it away too
    app._shutdown()
    _header, rows = read_all_gaze(app.recorder.session_dir / "all_gaze.csv")
    assert [r["FPOGX"] for r in rows] == ["0.7"]


# -- Skip ------------------------------------------------------------------------------


def test_the_skip_button_is_on_only_while_a_target_waits(make_app):
    app = make_app(live_overrides={**FAST, "task.timeout_ms": 600_000, "task.inter_trial_interval_ms": 2000})
    bar = app.view.run_bar
    app._update_run_bar(time.time_ns())
    assert not bar.skip_button.isEnabled()  # nothing shown yet
    to_wait_input(app)
    assert bar.skip_button.isEnabled()
    bar.skip_button.click()  # skipped: a row, then the ITI
    assert app.task.trials[0].is_skipped and app.task.trials[0].is_timeout is False
    app._tick()
    assert app.task.phase is Phase.ITI and not bar.skip_button.isEnabled()
    assert len(app.task.trials) == 1
    bar.skip_button.click()  # disabled: nothing more is skipped
    assert len(app.task.trials) == 1


# -- Quit (4C.6, AC11) -------------------------------------------------------------------


@pytest.mark.parametrize("how", ["button", "alt_q", "esc"])
def test_quit_asks_first_pausing_the_clock_and_keep_going_resumes(make_app, how):
    app = make_app(live_overrides=LONG_TRIAL)
    answer = app.confirm_quit = Answer(app, quit_it=False)
    to_wait_input(app)
    if how == "button":
        app.view.run_bar.quit_button.click()
    elif how == "alt_q":
        app.view.quit_shortcut.activated.emit()
    else:
        app.canvas.keyPressEvent(esc_event())
    assert len(answer.calls) == 1
    call = answer.calls[0]
    assert call["parent"] is app.view and (call["completed"], call["planned"]) == (0, len(app.task.targets))
    assert call["paused"] and call["canvas_paused"]  # the clock was stopped while it was asked
    assert not app._shutdown_done and not app._paused and not app.canvas.paused  # Keep going
    assert app.view.run_bar.pause_button.text() == "Pause (Alt-P)"
    assert not (app._embedded and make_app.results)  # nothing finished
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT


def test_keep_going_leaves_an_operator_pause_in_place(make_app):
    app = make_app(live_overrides=LONG_TRIAL)
    answer = app.confirm_quit = Answer(app, quit_it=False)
    to_wait_input(app)
    app.view.run_bar.pause_button.click()
    app.view.run_bar.quit_button.click()
    assert len(answer.calls) == 1 and app._paused  # still paused: the operator had paused already
    assert app.view.run_bar.pause_button.text() == "Resume (Alt-P)"


@pytest.mark.parametrize("how", ["button", "alt_q", "esc"])
def test_a_confirmed_quit_writes_the_files_and_hands_back_an_ended_early_result(make_app, how):
    app = make_app(structural_overrides={"trials": 6}, live_overrides=LONG_TRIAL)
    answer = app.confirm_quit = Answer(app, quit_it=True)
    to_wait_input(app)
    app._skip_trial()  # one finished trial (a skip), then the next target shows
    app._tick()
    t_before = now_ns()
    if how == "button":
        app.view.run_bar.quit_button.click()
    elif how == "alt_q":
        app.view.quit_shortcut.activated.emit()
    else:
        app.canvas.keyPressEvent(esc_event())
    assert answer.calls[0]["completed"] == 1
    assert app._shutdown_done
    (result,) = make_app.results
    assert result.run_mode == "record" and (result.outcome, result.ended_by) == ("ended_early", "operator_quit")
    assert (result.planned, result.completed, result.skipped, result.hits) == (6, 1, 1, 0)
    assert result.session_dir == app.recorder.session_dir and result.session_dir.is_dir()
    assert result.finished_at
    meta = metadata_of(app)
    assert (meta["outcome"], meta["ended_by"]) == ("ended_early", "operator_quit")
    assert (meta["planned_trials"], meta["completed_trials"], meta["skipped_trials"]) == (6, 1, 1)
    assert meta["ended_ns"] >= t_before
    # The quit question paused the run, so the in-flight trial 2 was dropped (interrupted), not
    # recorded; the log still names the trial the operator was on.
    assert meta["interrupted_trials"] == 1
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    assert "Run ended early by operator at trial 2 of 6 (1 recorded)." in log
    lines = (app.recorder.session_dir / "trials.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # a header and the one skipped trial
    assert not (app.recorder.session_dir / "report.json").exists()  # built only after a Save (HD1)


def test_a_quit_before_any_trial_finished_is_an_empty_result(make_app):
    app = make_app(live_overrides=LONG_TRIAL)
    app.confirm_quit = Answer(app, quit_it=True)
    to_wait_input(app)
    app.view.run_bar.quit_button.click()
    (result,) = make_app.results
    assert result.is_empty and result.completed == 0 and not result.is_complete
    assert result.session_dir.is_dir()  # written; the run-end flow discards it (nothing is saved)


def test_a_second_quit_while_the_question_is_open_is_ignored(make_app):
    app = make_app(live_overrides=LONG_TRIAL)
    to_wait_input(app)
    asked: list[int] = []

    def confirm(parent, completed, planned):
        asked.append(1)
        app.canvas.keyPressEvent(esc_event())  # Esc pressed again behind the dialog
        app.view.run_bar.quit_button.click()
        return False

    app.confirm_quit = confirm
    app.view.run_bar.quit_button.click()
    assert asked == [1] and not app._shutdown_done and not app._paused


@pytest.mark.parametrize("mode", ["practice", "preview"])
def test_a_practice_or_preview_quits_at_once_with_no_question(make_app, mode):
    kw = {"client": MouseGazeSource(), "replay": False} if mode == "preview" else {}
    app = make_app(run_mode=mode, structural_overrides={"trials": 3}, live_overrides=LONG_TRIAL, **kw)
    if mode == "preview":
        kw["client"].bind_canvas(app.canvas)
    app.confirm_quit = lambda *a: pytest.fail("a practice must not ask")
    to_wait_input(app)
    app.canvas.keyPressEvent(esc_event())
    (result,) = make_app.results
    assert (result.run_mode, result.outcome, result.ended_by) == (mode, "ended_early", "operator_quit")
    assert result.session_dir is None and (result.planned, result.completed) == (3, 0)
    assert not (make_app.root.exists() and any(make_app.root.rglob("*")))


def test_alt_q_and_esc_do_nothing_after_the_run_has_ended(make_app):
    app = make_app(live_overrides=LONG_TRIAL, structural_overrides={"trials": 1})
    app.confirm_quit = lambda *a: pytest.fail("the run is over")
    app._shutdown()
    app._request_quit()
    app.canvas.keyPressEvent(esc_event())
    assert len(make_app.results) == 1


# -- normal completion -------------------------------------------------------------------------


def test_a_run_that_runs_out_of_trials_hands_back_a_completed_result(make_app):
    app = make_app(
        structural_overrides={"trials": 2},
        live_overrides={**FAST, "task.timeout_ms": 30, "task.inter_trial_interval_ms": 0},
    )
    app.confirm_quit = lambda *a: pytest.fail("a finished run never asks")
    tick_until(app, lambda: bool(make_app.results))
    (result,) = make_app.results
    assert (result.outcome, result.ended_by) == ("completed", "finished")
    assert (result.planned, result.completed, result.skipped, result.hits) == (2, 2, 0, 0)
    assert result.is_complete and result.session_dir == app.recorder.session_dir
    assert (result.session_dir / "trials.csv").is_file()
    assert not (result.session_dir / "report.json").exists()


# -- the standalone path (AC15) ---------------------------------------------------------------------


def test_the_standalone_window_runs_to_the_end_with_a_run_bar(make_app):
    app = make_app(
        embedded=False,
        structural_overrides={"trials": 2},
        live_overrides={**FAST, "task.timeout_ms": 30, "task.inter_trial_interval_ms": 0},
        preset_calibration_result=None,
    )
    assert app.window is not None and app.view is app.window.view
    assert app.view.run_bar.quit_button.text() == "Quit (Alt-Q)"
    assert not hasattr(app.window, "operator_panel")
    tick_until(app, lambda: app.task.is_done or app._shutdown_done)
    assert app._shutdown_done
    folder = app.recorder.session_dir
    assert (folder / "trials.csv").is_file() and (folder / "metadata.json").is_file()
    assert metadata_of(app)["outcome"] == "completed"
    assert make_app.results == []  # no embedding: the app quits instead of reporting
