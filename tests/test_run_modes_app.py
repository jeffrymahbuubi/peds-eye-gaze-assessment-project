"""SPEC-compass-task-flow.md 4C.4 / R3 / R8 / 4C.9 through ``AssessmentApp`` (P2,
data side of ``run_mode``): what a record, a practice and a preview run write, the
seed each uses, the pre-roll, the outcome fields, and the Preview mouse source.
Acceptance AC4, AC6, AC16; AB13/AB14 (data side)."""

from __future__ import annotations

import copy
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
from src.data.analysis_export import read_all_gaze
from src.data.recorder import NullRecorder, SessionRecorder
from src.engine.calibration import CalibrationResult
from src.engine.run_mode import PREVIEW_SEED
from src.inputs.gazepoint_client import DeviceInfo, GazepointClient
from src.inputs.mouse_gaze import MouseGazeSource
from src.tasks.base_task import Phase

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
FAST = {"dwell.smoothing.enabled": False, "dwell.refractory_ms": 0}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch):
    """Build apps writing under ``tmp_path/sessions``. The 500 ms pre-roll is
    switched off unless a test asks for the real one (``real_preroll=True``)."""
    real_load = app_module.load_task_config
    root = tmp_path / "sessions"

    def load(task_id, *a, **k):
        cfg = real_load(task_id, *a, **k)
        cfg.setdefault("recording", {})["output_root"] = str(root)
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        cfg.setdefault("input", {})["mode"] = "eye"
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    seeds: list[int] = []
    real_build = app_module.build_task

    def spy(task_id, config, **kw):
        seeds.append(kw.get("seed"))
        return real_build(task_id, config, **kw)

    monkeypatch.setattr(app_module, "build_task", spy)
    made: list[AssessmentApp] = []

    def build(task_id="click_static", replay=True, real_preroll=False, **kw):
        if not real_preroll:
            monkeypatch.setattr(app_module, "preroll_ms", lambda mode: 0)
        app = AssessmentApp(
            task_id, str(FIXTURE) if replay else None, "P001", embedded=True, **kw
        )
        app.timer.stop()  # the tests tick by hand
        made.append(app)
        return app

    build.root, build.seeds = root, seeds
    yield build
    for app in made:
        app.timer.stop()
        app.recorder.close()
        app.client.stop()


def snapshot(root: Path) -> dict[str, bytes | None]:
    if not root.exists():
        return {"<missing>": None}
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in root.rglob("*")
    }


def tick_until(app: AssessmentApp, condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        time.sleep(0.005)


def metadata_of(app: AssessmentApp) -> dict:
    app.recorder.close()
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def events_of(app: AssessmentApp) -> list[dict]:
    lines = (app.recorder.session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


# -- run_mode validation -----------------------------------------------------


def test_an_unknown_run_mode_is_refused_before_anything_is_created(make_app):
    with pytest.raises(ValueError):
        make_app(run_mode="recorded")
    assert not make_app.root.exists()


def test_the_default_run_mode_is_record(make_app):
    app = make_app()
    assert app.run_mode == "record"
    assert isinstance(app.recorder, SessionRecorder)


# -- a recorded run ----------------------------------------------------------


def test_a_record_run_writes_run_mode_and_config_name(make_app):
    app = make_app(config_name="Custom 1", seed=4242)
    meta = metadata_of(app)
    assert meta["run_mode"] == "record"
    assert meta["config_name"] == "Custom 1"
    assert meta["settings"]["config_name"] == "Custom 1"  # R7: the configuration block names it too
    assert meta["seed"] == 4242 and make_app.seeds == [4242]  # the test's own seed
    assert app.metadata.session_id.endswith("_run1") and app.recorder.session_dir.is_dir()


def test_a_standalone_record_run_has_no_config_name(make_app):
    meta = metadata_of(make_app())
    assert meta["config_name"] is None and meta["settings"]["config_name"] is None
    assert meta["run_mode"] == "record" and meta["seed"] == 0


def test_a_record_run_with_a_preset_calibration_saves_it(make_app):
    app = make_app(preset_calibration_result=VALID)
    assert (app.recorder.session_dir / "calibration.json").is_file()


def test_the_pre_roll_holds_trial_one_for_at_least_500_ms(make_app):
    app = make_app(real_preroll=True)
    t_first = time.time_ns()
    app._tick()
    assert app.task.phase is Phase.READY and app.task.trials == []
    tick_until(app, lambda: app.task.phase is Phase.WAIT_INPUT)
    waited_ns = time.time_ns() - t_first
    assert waited_ns >= 500_000_000
    app._shutdown()
    shown = [e for e in events_of(app) if e["kind"] == "TARGET_SHOWN"]
    assert shown[0]["t_ns"] - t_first >= 500_000_000


@pytest.mark.parametrize("mode", ["practice", "preview"])
def test_practice_and_preview_have_no_pre_roll(make_app, mode):
    kw = {"client": MouseGazeSource()} if mode == "preview" else {}
    app = make_app(run_mode=mode, real_preroll=True, replay=mode == "practice", **kw)
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT


def test_the_skip_button_now_records_a_skip_not_a_timeout(make_app):
    app = make_app()
    app._tick()
    assert app.task.phase is Phase.WAIT_INPUT
    app._skip_trial()
    row = app.task.trials[0]
    assert (row.is_skipped, row.is_timeout, row.is_hit) == (True, False, False)
    app._skip_trial()  # in the ITI now: harmlessly nothing
    assert len(app.task.trials) == 1


def test_an_ended_run_writes_how_it_ended(make_app):
    app = make_app(structural_overrides={"trials": 6})
    app._tick()
    app._skip_trial()  # one skipped trial, then the operator ends the run
    t_before = time.time_ns()
    app._shutdown()
    meta = metadata_of(app)
    assert meta["planned_trials"] == 6 == len(app.task.targets)
    assert (meta["completed_trials"], meta["skipped_trials"]) == (1, 1)
    assert (meta["interrupted_trials"], meta["pause_count"]) == (0, 0)
    assert (meta["outcome"], meta["ended_by"]) == ("ended_early", "operator_quit")
    assert meta["ended_ns"] >= t_before
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    assert "Run ended early by operator at trial 1 of 6 (1 recorded)." in log
    lines = (app.recorder.session_dir / "trials.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",")[-5] == "is_skipped"  # then entries, end_x, end_y, slot_index (R6)
    assert lines[1].split(",")[-5] == "1"
    # The HUD is gone (4C.7): its two metadata fields are no longer written.
    assert "hud_hidden_at_start" not in meta and "hud_toggle_count" not in meta


def test_a_run_that_runs_out_of_trials_is_completed(make_app):
    done: list[int] = []
    app = make_app(
        structural_overrides={"trials": 2},
        live_overrides={"task.timeout_ms": 30, "task.inter_trial_interval_ms": 0},
        on_finished=lambda _result: done.append(1),
    )
    tick_until(app, lambda: bool(done))
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["planned_trials"] == meta["completed_trials"] == 2
    assert (meta["outcome"], meta["ended_by"]) == ("completed", "finished")
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    assert "Run completed: 2 of 2 trials." in log


def test_the_dropout_diagnostic_is_for_recorded_runs_on_a_live_device(make_app):
    class LiveFake(GazepointClient):
        def __init__(self):
            super().__init__(replay_path=str(FIXTURE))
            self._info = DeviceInfo(rate_hz=60)

        @property
        def device_info(self):
            return self._info

        @property
        def is_live(self):
            return True

    assert make_app(client=LiveFake())._dropout_log is not None
    assert make_app(client=LiveFake(), run_mode="practice", preset_calibration_result=VALID)._dropout_log is None


# -- practice (AC4) ----------------------------------------------------------


def seeded_world(root: Path) -> None:
    """A sessions folder that already holds a finished run and the shared logs."""
    run = root / "2026-10-05_P001_click_static_run1"
    run.mkdir(parents=True)
    (run / "trials.csv").write_text("trial_id\n0\n", encoding="utf-8")
    (run / "calibration.json").write_text("{}", encoding="utf-8")
    (root / "_diagnostics").mkdir()
    (root / "_diagnostics" / "gaze_dropouts.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "_settings").mkdir()
    (root / "_settings" / "keep.json").write_text("{}", encoding="utf-8")


def test_practice_leaves_the_sessions_folder_byte_identical(make_app):
    seeded_world(make_app.root)
    before = snapshot(make_app.root)
    structural = {"trials": 3}
    live = {"task.timeout_ms": 30, "task.inter_trial_interval_ms": 0}
    structural_before, live_before = copy.deepcopy(structural), copy.deepcopy(live)
    done: list[int] = []
    app = make_app(
        run_mode="practice",
        practice_index=2,
        seed=777,  # the test's own seed: not used by a practice
        structural_overrides=structural,
        live_overrides=live,
        preset_calibration_result=VALID,
        preset_calibration_source="measured",
        on_finished=lambda _result: done.append(1),
    )
    assert isinstance(app.recorder, NullRecorder) and app.recorder.session_dir is None
    assert len(app.task.targets) == 3
    app._tick()
    app._skip_trial()
    tick_until(app, lambda: bool(done))  # the other two time out; the task finishes by itself
    assert snapshot(make_app.root) == before  # no folder, no file, no _diagnostics line
    assert list(make_app.root.glob("**/calibration.json")) == [
        make_app.root / "2026-10-05_P001_click_static_run1" / "calibration.json"
    ]
    assert (structural, live) == (structural_before, live_before)  # the test's dicts untouched
    assert app.metadata.run_mode == "practice" and app.metadata.session_id == "practice"
    assert make_app.seeds == [1_000_002]  # 1_000_000 + k, not 777


def test_practice_uses_a_new_seed_each_time_and_never_the_record_one(make_app):
    seeds = []
    for k in range(3):
        make_app(run_mode="practice", practice_index=k, preset_calibration_result=VALID)
        seeds.append(make_app.seeds[-1])
    assert seeds == [1_000_000, 1_000_001, 1_000_002]
    make_app(seed=0)
    assert make_app.seeds[-1] == 0


def test_a_practice_never_stops_the_shared_client(make_app):
    class Shared(GazepointClient):
        def __init__(self):
            super().__init__(replay_path=str(FIXTURE))
            self.stop_calls = 0

        def stop(self):
            self.stop_calls += 1
            super().stop()

    shared = Shared()
    app = make_app(run_mode="practice", client=shared, preset_calibration_result=VALID)
    app._tick()
    app._shutdown()
    assert shared.stop_calls == 0  # the Setup page's client is not the practice's to stop


def test_practice_with_no_preset_calibration_still_leaves_nothing(make_app):
    """No preset and a replay client: the stub calibration result, and nothing on disk."""
    before = snapshot(make_app.root)
    app = make_app(run_mode="practice")
    app._tick()
    app._shutdown()
    assert snapshot(make_app.root) == before


# -- AC6: raw records ---------------------------------------------------------


class RawQueueClient:
    """A gaze client with a raw queue we fill by hand."""

    is_live = False
    device_info = None

    def __init__(self) -> None:
        self._raw: list[tuple[int, dict[str, str]]] = []
        self.cleared = 0

    def queue(self, *x_values: str, t0: float) -> None:
        for i, x in enumerate(x_values):
            attrs = {"CNT": str(i), "TIME": f"{t0 + 0.05 * i:.5f}", "FPOGX": x, "FPOGY": "0.5", "FPOGV": "1"}
            self._raw.append((time.time_ns(), attrs))

    def latest(self):
        return None

    def is_connected(self) -> bool:
        return True

    def connect(self, *a, **k) -> None: ...
    def start_streaming(self) -> None: ...
    def stop(self) -> None: ...

    def clear_raw(self) -> None:
        self.cleared += 1
        self._raw.clear()

    def drain_raw(self):
        items, self._raw = self._raw, []
        return items


def test_a_practice_then_a_record_keeps_the_raw_file_to_the_record_run(make_app):
    client = RawQueueClient()
    client.queue("0.1", "0.1", "0.1", t0=1.0)  # Connect / Setup / calibration records

    practice = make_app(run_mode="practice", client=client, preset_calibration_result=VALID, replay=False)
    assert client.cleared == 1  # the practice starts from a clean queue too
    client.queue("0.2", "0.2", t0=2.0)  # arrive during the practice
    practice._tick()
    assert client.drain_raw() == []  # drained (and thrown away), not left queued
    practice._shutdown()
    client.queue("0.3", "0.3", t0=3.0)  # between the practice and the real run

    record = make_app(client=client, preset_calibration_result=VALID, replay=False)
    assert client.cleared == 2  # construction of the record run dropped the "0.3" records
    client.queue("0.7", "0.8", "0.9", t0=4.0)  # after construction: the run's own
    record._tick()
    record._shutdown()

    session = record.recorder.session_dir
    _header, rows = read_all_gaze(session / "all_gaze.csv")
    assert [r["FPOGX"] for r in rows] == ["0.7", "0.8", "0.9"]
    assert float(rows[0]["TIME"]) == 0.0  # TIME starts at the run's first record


# -- preview (AB13/AB14, data side) ------------------------------------------


class Pointing:
    def __init__(self) -> None:
        self.pos = QPoint(0, 0)

    def __call__(self) -> QPoint:
        return self.pos


def test_preview_writes_nothing_and_uses_its_own_seed(make_app):
    before = snapshot(make_app.root)
    mouse = MouseGazeSource(cursor_pos=Pointing())
    app = make_app(run_mode="preview", client=mouse, replay=False, seed=31)
    assert app.client is mouse and app._owns_client is False
    assert isinstance(app.recorder, NullRecorder)
    assert app.metadata.run_mode == "preview" and app.metadata.session_id == "preview"
    assert make_app.seeds == [PREVIEW_SEED]
    mouse.bind_canvas(app.canvas)
    app._tick()
    app._shutdown()
    assert snapshot(make_app.root) == before  # nothing: no folder, no calibration.json, no _diagnostics


def test_a_hover_of_dwell_length_on_the_target_scores_a_hit_in_preview(make_app):
    pointing = Pointing()
    mouse = MouseGazeSource(cursor_pos=pointing)
    app = make_app(
        run_mode="preview",
        client=mouse,
        replay=False,
        structural_overrides={"trials": 1},
        live_overrides={**FAST, "dwell.threshold_ms": 300},
    )
    mouse.bind_canvas(app.canvas)
    app._tick()  # trial 1 is shown
    target = app.task.targets[0]
    x_norm, y_norm = app.task.target_position(target, 0)
    pointing.pos = app.canvas.mapToGlobal(
        QPoint(round(x_norm * app.canvas.width()), round(y_norm * app.canvas.height()))
    )
    tick_until(app, lambda: bool(app.task.trials))
    assert app.task.trials[0].is_hit is True


def test_a_mouse_outside_the_canvas_never_scores(make_app):
    pointing = Pointing()
    mouse = MouseGazeSource(cursor_pos=pointing)
    app = make_app(
        run_mode="preview",
        client=mouse,
        replay=False,
        structural_overrides={"trials": 1},
        live_overrides={**FAST, "dwell.threshold_ms": 300, "task.timeout_ms": 400},
    )
    mouse.bind_canvas(app.canvas)
    pointing.pos = app.canvas.mapToGlobal(QPoint(-500, -500))
    tick_until(app, lambda: bool(app.task.trials))
    assert app.task.trials[0].is_timeout is True and app.task.trials[0].is_hit is False


# -- P3 recording additions through the app (SPEC 4D.4-4, 4D.4-5) -------------


def test_a_record_run_writes_the_raw_clock_offset(make_app):
    client = RawQueueClient()
    app = make_app(client=client, preset_calibration_result=VALID, replay=False)
    client.queue("0.7", "0.8", "0.9", t0=4.0)
    queued = list(client._raw)
    app._tick()
    app._shutdown()
    first = float(queued[0][1]["TIME"])
    # The host time of TIME=0: the smallest receive time minus device time.
    expected = min(t - round((float(a["TIME"]) - first) * 1e9) for t, a in queued)
    assert metadata_of(app)["raw_clock_offset_ns"] == expected


def test_no_raw_records_means_no_clock_offset(make_app):
    app = make_app(client=RawQueueClient(), preset_calibration_result=VALID, replay=False)
    app._tick()
    app._shutdown()
    assert metadata_of(app)["raw_clock_offset_ns"] is None


@pytest.mark.parametrize(("task_id", "n_slots"), [("click_grid", 9), ("scanning", None), ("click_static", 0)])
def test_the_metadata_carries_the_layout_slots_in_canvas_norm(make_app, task_id, n_slots):
    app = make_app(task_id)
    app._tick()
    slots = metadata_of(app)["layout_slots"]
    if n_slots == 0:
        assert slots is None and app.task.layout_slots is None  # no fixed layout
        return
    expected = [[round(x, 5), round(y, 5)] for x, y in app.task.layout_slots]
    assert slots == expected
    assert n_slots is None or len(slots) == n_slots
    assert all(0.0 < x < 1.0 and 0.0 < y < 1.0 for x, y in slots)


def test_a_follow_moving_run_writes_a_target_track_and_a_practice_does_not(make_app):
    record = make_app("follow_moving")
    for _ in range(5):
        record._tick()
        time.sleep(0.01)
    record._shutdown()
    track = record.recorder.session_dir / "target_track.csv"
    lines = track.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "t_ns,trial,x,y" and len(lines) >= 2

    before = snapshot(make_app.root)
    practice = make_app("follow_moving", run_mode="practice")
    for _ in range(5):
        practice._tick()  # runs against the NullRecorder: must not raise or write
        time.sleep(0.01)
    practice._shutdown()
    assert snapshot(make_app.root) == before


# -- the report is no longer built at the run's end (HD1, P7b) ------------------


def test_a_recorded_run_does_not_build_a_report_json(make_app):
    """Only a run the operator saves gets one (``finish_run``, tests/test_run_finish.py): a
    discarded run must never have built it, so the run's own end does not."""
    done: list[object] = []
    app = make_app(
        structural_overrides={"trials": 2},
        live_overrides={"task.timeout_ms": 30, "task.inter_trial_interval_ms": 0},
        on_finished=lambda result: done.append(result),
    )
    tick_until(app, lambda: bool(done))
    folder = app.recorder.session_dir
    assert (folder / "trials.csv").is_file() and (folder / "session_metrics.json").is_file()
    assert not (folder / "report.json").exists()
    assert done[0].session_dir == folder  # ... and hands the folder to the run-end flow


@pytest.mark.parametrize("mode", ["practice", "preview"])
def test_practice_and_preview_never_build_a_report(make_app, mode):
    kw = {"client": MouseGazeSource()} if mode == "preview" else {}
    app = make_app(run_mode=mode, replay=mode == "practice", **kw)
    app._tick()
    app._shutdown()
    assert list(make_app.root.glob("**/report.json")) == []
