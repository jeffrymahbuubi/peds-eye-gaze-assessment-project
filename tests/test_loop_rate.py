"""SPEC-ui-setup-task-selection.md S25: ``app.target_fps: auto`` resolves the
loop rate from the device; an explicit number always wins."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.app as app_module
import src.engine.task_runner as task_runner_module
from src.app import AssessmentApp
from src.data.schema import SessionMetadata
from src.engine.loop_rate import resolve_target_fps, target_fps_is_invalid
from src.inputs.gazepoint_client import DeviceInfo, GazepointClient

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


# -- criterion 1: the pure resolver -----------------------------------------


@pytest.mark.parametrize("value", [150, 60, 75.0, "90", " 100 "])
def test_number_is_config_and_wins_over_device(value):
    fps, source = resolve_target_fps(value, 150, True)
    assert (fps, source) == (int(float(value)), "config")
    assert resolve_target_fps(value, None, False) == (int(float(value)), "config")


@pytest.mark.parametrize("value", ["auto", "AUTO", " Auto "])
@pytest.mark.parametrize("rate", [150, 60, 150.0])
def test_auto_live_with_rate_is_device(value, rate):
    assert resolve_target_fps(value, rate, True) == (int(rate), "device")


def test_missing_key_is_auto():
    from src.engine.loop_rate import config_target_fps

    assert resolve_target_fps(config_target_fps({}), 150, True) == (150, "device")
    assert resolve_target_fps(config_target_fps({"app": {}}), 60, True) == (60, "device")
    assert resolve_target_fps(config_target_fps({"app": {}}), None, True) == (60, "fallback")
    assert not target_fps_is_invalid(config_target_fps({"app": {}}))


@pytest.mark.parametrize("rate", [None, 0, -5])
def test_auto_live_with_unknown_rate_falls_back(rate):
    assert resolve_target_fps("auto", rate, True) == (60, "fallback")


def test_auto_not_live_falls_back():
    assert resolve_target_fps("auto", 150, False) == (60, "fallback")
    assert resolve_target_fps(None, 150, False) == (60, "fallback")


@pytest.mark.parametrize("bad", [0, -1, 0.5, "fast", "", float("nan"), float("inf"), True, [], {}])
def test_bad_values_fall_back_without_raising(bad):
    assert resolve_target_fps(bad, 150, True) == (60, "fallback")
    assert target_fps_is_invalid(bad)


def test_valid_values_are_not_flagged_invalid():
    for ok in (150, "auto", "AUTO", None, "90"):
        assert not target_fps_is_invalid(ok)


# -- criterion 3: metadata fields, v1.0.0 files still load -------------------


def test_metadata_defaults_and_old_file_loads():
    meta = SessionMetadata(subject_id="P", session_id="S", started_ns=0)
    assert meta.loop_fps is None and meta.loop_fps_source is None
    d = meta.to_dict()
    assert d["loop_fps"] is None and d["loop_fps_source"] is None

    # A v1.0.0 metadata.json lacks the keys; readers take named keys.
    old = {k: v for k, v in d.items() if k not in ("loop_fps", "loop_fps_source")}
    assert "loop_fps" not in old
    assert SessionMetadata(**{**old, "subject_id": "P"}).loop_fps is None


# -- criterion 4: headless replay -------------------------------------------


@pytest.fixture
def replay_with_fps(monkeypatch, tmp_path):
    real = task_runner_module.load_task_config

    def run(target_fps):
        def load(task_id, *a, **k):
            cfg = real(task_id, *a, **k)
            if target_fps is _DROP:
                cfg.setdefault("app", {}).pop("target_fps", None)
            else:
                cfg.setdefault("app", {})["target_fps"] = target_fps
            return cfg

        monkeypatch.setattr(task_runner_module, "load_task_config", load)
        result = task_runner_module.run_headless_replay(
            task_id="click_static",
            replay_path=FIXTURE,
            output_root=tmp_path,
            session_id=f"replay_{'drop' if target_fps is _DROP else target_fps}",
            max_seconds=2.0,
        )
        return (Path(result["session_dir"]) / "session.log").read_text(encoding="utf-8")

    return run


_DROP = object()


def test_replay_auto_runs_at_60(replay_with_fps):
    assert "fps=60" in replay_with_fps("auto")
    assert "fps=60" in replay_with_fps(_DROP)


def test_replay_number_runs_at_that_number(replay_with_fps):
    assert "fps=150" in replay_with_fps(150)
    assert "fps=75" in replay_with_fps(75)


# -- criteria 2 and 3: AssessmentApp ----------------------------------------


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _LiveFakeClient(GazepointClient):
    """A replay-backed client that presents as a live device with a known rate."""

    def __init__(self, rate_hz):
        super().__init__(replay_path=str(FIXTURE))
        self._fake_info = DeviceInfo(rate_hz=rate_hz)

    @property
    def device_info(self):
        return self._fake_info

    @property
    def is_live(self):
        return True


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch):
    real_load = app_module.load_task_config
    cfg_fps = {"value": "auto"}

    def load(task_id, *a, **k):
        cfg = real_load(task_id, *a, **k)
        cfg.setdefault("recording", {})["output_root"] = str(tmp_path / "sessions")
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        cfg.setdefault("app", {})["target_fps"] = cfg_fps["value"]
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    made = []

    def build(target_fps, client=None):
        cfg_fps["value"] = target_fps
        app = AssessmentApp(
            "click_static", str(FIXTURE), "P001", embedded=True, client=client
        )
        made.append(app)
        return app

    yield build
    for app in made:
        app.timer.stop()
        app.recorder.close()
        app.client.stop()


def _log_and_meta(app):
    app.recorder.close()
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    return log, meta


def test_app_auto_on_60hz_device_drives_timer_and_latency(make_app):
    client = _LiveFakeClient(60)
    client.connect()
    app = make_app("auto", client=client)
    assert app._loop_fps == 60
    assert app.timer.interval() == 16
    assert app._latency._window_size == 60
    log, meta = _log_and_meta(app)
    assert "Loop rate: 60 Hz (from device)." in log
    assert meta["loop_fps"] == 60 and meta["loop_fps_source"] == "device"


def test_app_auto_on_150hz_device(make_app):
    client = _LiveFakeClient(150)
    client.connect()
    app = make_app("auto", client=client)
    assert app._loop_fps == 150
    assert app.timer.interval() == 6
    log, meta = _log_and_meta(app)
    assert "Loop rate: 150 Hz (from device)." in log
    assert meta["loop_fps_source"] == "device"


def test_app_explicit_number_beats_device(make_app):
    client = _LiveFakeClient(60)
    client.connect()
    app = make_app(100, client=client)
    assert app._loop_fps == 100
    assert app.timer.interval() == 10
    log, meta = _log_and_meta(app)
    assert "Loop rate: 100 Hz (from config)." in log
    assert (meta["loop_fps"], meta["loop_fps_source"]) == (100, "config")


def test_app_auto_on_replay_falls_back_to_60(make_app):
    app = make_app("auto")
    assert app._loop_fps == 60
    log, meta = _log_and_meta(app)
    assert "Loop rate: 60 Hz (fallback)." in log
    assert (meta["loop_fps"], meta["loop_fps_source"]) == (60, "fallback")


def test_app_bad_value_warns_and_does_not_crash(make_app):
    app = make_app("fast")
    assert app._loop_fps == 60
    log, meta = _log_and_meta(app)
    assert "WARNING: app.target_fps='fast'" in log
    assert meta["loop_fps_source"] == "fallback"
