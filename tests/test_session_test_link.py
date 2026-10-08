"""SPEC-compass-task-flow.md 4A.7 / AA11 (first half): a run started from a test
carries ``test_id``, ``test_name`` and ``seed`` in its ``metadata.json``."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp
from src.data.schema import SessionMetadata
from src.engine.subject_tests import create_test, list_tests

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


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
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    seeds_seen = []
    real_build = app_module.build_task

    def spy(task_id, config, **kw):
        seeds_seen.append(kw.get("seed"))
        return real_build(task_id, config, **kw)

    monkeypatch.setattr(app_module, "build_task", spy)
    made = []

    def build(**kw):
        app = AssessmentApp("click_static", str(FIXTURE), "P001", embedded=True, **kw)
        made.append(app)
        return app

    build.root, build.seeds_seen = root, seeds_seen
    yield build
    for app in made:
        app.timer.stop()
        app.recorder.close()
        app.client.stop()


def _metadata(app) -> dict:
    app.recorder.close()
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def test_run_started_from_a_test_records_its_id_name_and_seed(make_app):
    test = create_test(make_app.root, "P001", "click_static", name="Warm-up")
    app = make_app(test_id=test.test_id, test_name=test.name, seed=test.seed)
    meta = _metadata(app)
    assert meta["test_id"] == test.test_id
    assert meta["test_name"] == "Warm-up"
    assert meta["seed"] == test.seed
    assert make_app.seeds_seen == [test.seed]  # the task's target order is drawn from it
    # The run's folder is where the record will point at after Save (4A.7).
    assert app.recorder.session_dir.parent == make_app.root / "P001" / "runs" / "click_static"
    assert list_tests(make_app.root, "P001").tests[0].run_dir is None  # nothing links it yet


def test_standalone_run_has_no_test_and_seed_zero(make_app):
    app = make_app()
    meta = _metadata(app)
    assert meta["test_id"] is None and meta["test_name"] is None
    assert meta["seed"] == 0  # the standardized order every run had before tests existed
    assert make_app.seeds_seen == [0]


def test_metadata_fields_default_to_none_and_serialise():
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    assert (meta.test_id, meta.test_name, meta.seed) == (None, None, None)
    meta.test_id, meta.test_name, meta.seed = "t_0123456789", "Grid Click 1", 4242
    data = meta.to_dict()
    assert (data["test_id"], data["test_name"], data["seed"]) == ("t_0123456789", "Grid Click 1", 4242)
    assert data["schema_version"] == SessionMetadata(subject_id="x", session_id="y", started_ns=0).schema_version


def test_older_metadata_without_the_fields_still_loads():
    old = SessionMetadata(subject_id="S", session_id="x", started_ns=0).to_dict()
    for key in ("test_id", "test_name", "seed"):
        old.pop(key)
    assert SessionMetadata(**old).seed is None
