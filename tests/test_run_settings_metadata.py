"""SPEC-compass-task-flow.md R7 and the P5 carry-forward (P8b): ``metadata.json`` ``settings`` is
``run_settings`` of the **final** merged config of the run -- complete live and structural
values, the theme and the feedback toggles the report reads -- with the old provenance keys
beside them. Offscreen Qt, ``AssessmentApp`` on a replay fixture in a scratch folder."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp
from src.data.report_config import build_config_rows
from src.engine.calibration import CalibrationResult
from src.engine.config import load_task_config
from src.ui.settings_registry import (
    get_nested,
    live_settings_for_task,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import run_settings, settings_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
TASKS = ("click_static", "click_grid", "follow_moving", "scanning")


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
    made = []

    def build(task_id="click_grid", **kw):
        app = AssessmentApp(
            task_id,
            str(FIXTURE),
            "P001",
            embedded=True,
            preset_calibration_result=VALID,
            **kw,
        )
        app.timer.stop()
        made.append(app)
        return app

    yield build
    for app in made:
        app.timer.stop()
        app.recorder.close()
        app.client.stop()


def written_metadata(app):
    app.recorder.close()  # metadata.json is written at close
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("task_id", TASKS)
def test_settings_is_run_settings_of_the_final_merged_config(make_app, task_id):
    app = make_app(task_id, config_name="Quick look")
    block = written_metadata(app)["settings"]
    expected = run_settings(task_id, app.config, "Quick look")
    assert block == json.loads(json.dumps(expected))  # exactly that block, nothing beside it


@pytest.mark.parametrize("task_id", TASKS)
def test_settings_holds_one_value_for_every_setting_of_the_task(make_app, task_id):
    block = written_metadata(make_app(task_id))["settings"]
    assert set(block["live"]) == {s.key for s in live_settings_for_task(task_id)}
    for setting in structural_settings_for_task(task_id):
        assert get_nested(block["structural"], setting.key) is not None, setting.key


def test_a_run_with_no_overrides_records_the_task_defaults_in_full(make_app):
    block = written_metadata(make_app("click_grid"))["settings"]
    default = settings_snapshot("click_grid", load_task_config("click_grid"))
    assert block["live"] == default["live"]
    assert block["structural"]["trials"] == 18 and block["structural"]["grid"]["rows"] == 3


def test_the_tests_stored_values_are_what_the_run_records(make_app):
    app = make_app(
        "click_grid",
        structural_overrides={"trials": 5, "target": {"size": "large"}},
        live_overrides={"dwell.threshold_ms": 1234},
        config_name="Large and slow",
    )
    block = written_metadata(app)["settings"]
    assert block["config_name"] == "Large and slow"
    assert block["structural"]["trials"] == 5 and block["structural"]["target"]["size"] == "large"
    assert block["live"]["dwell.threshold_ms"] == 1234
    assert block["structural"]["grid"]["rows"] == 3  # what it did not override is the default, in full


def test_the_theme_and_feedback_the_report_reads_are_recorded(make_app):
    block = written_metadata(make_app("click_grid"))["settings"]
    assert block["structural"]["theme"] == "forest"
    assert block["structural"]["feedback"]["hit_sound"] is True
    assert block["structural"]["feedback"]["miss_sound"] is True
    assert block["live"]["dwell.visual_cursor"] is True


def test_the_old_provenance_keys_are_gone(make_app):
    # settings.source / profile_saved_at / profile_file described the retired "newest saved
    # profile applies" rule (S10.3, S10.12); the configuration's own name is what is recorded.
    block = written_metadata(make_app("click_static", config_name="Quick look"))["settings"]
    assert set(block) == {"config_name", "live", "structural"}


@pytest.mark.parametrize("argument", ["settings_source", "settings_saved_at", "settings_profile_file"])
def test_assessment_app_no_longer_takes_the_provenance_arguments(make_app, argument):
    with pytest.raises(TypeError):
        make_app("click_static", **{argument: "x"})


def test_a_standalone_run_has_no_config_name_but_a_complete_block(make_app):
    block = written_metadata(make_app("click_static"))["settings"]
    assert block["config_name"] is None
    assert block["live"]["dwell.threshold_ms"] and block["structural"]["trials"]


def test_the_report_configuration_table_reads_the_written_block(make_app):
    app = make_app("click_grid", config_name="Quick look", live_overrides={"dwell.visual_cursor": False})
    meta = written_metadata(app)
    rows = dict(build_config_rows(meta["settings"], meta))
    assert rows["Configuration name"] == "Quick look"
    assert rows["Theme"] == "Forest"
    assert rows["Gaze cursor"] == "Hidden"
    assert rows["Feedback"] == "Hit sound on, miss sound on, glow on"
    assert rows["Number of trials"] != "not recorded"
