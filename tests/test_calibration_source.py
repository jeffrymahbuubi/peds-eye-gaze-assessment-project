"""SPEC-result-logic.md S12: the Session Log / metadata record where a run's
calibration came from (measured / loaded / not run)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp, calibration_log_line, resolve_calibration_source
from src.data.schema import SessionMetadata
from src.engine.calibration import CalibrationResult, save_calibration_result
from src.ui import setup_page as setup_page_module
from src.ui.setup_page import SetupPage

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.34, valid=True)
INVALID = CalibrationResult(n_points=5, mean_error_px=None, valid=False)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- S12.2 helpers ----------------------------------------------------------


def test_log_line_measured_is_unchanged():
    assert calibration_log_line(VALID, "measured", None) == (
        "Calibration measured — 5 points, mean error 12.3px, valid."
    )


def test_log_line_loaded_names_the_file():
    line = calibration_log_line(VALID, "loaded", "/x/y/calibration_5pt.json")
    assert line == "Calibration loaded from calibration_5pt.json — 5 points, mean error 12.3px, valid."


def test_log_line_loaded_without_file():
    assert calibration_log_line(VALID, "loaded", None).startswith("Calibration loaded — 5 points")


def test_log_line_invalid_and_not_run():
    assert calibration_log_line(INVALID, "measured", None) == (
        "Calibration measured — 5 points, invalid or unmeasured."
    )
    assert calibration_log_line(INVALID, "not run", None) == (
        "Calibration not run — 5 points, invalid or unmeasured."
    )


def _resolve(**kw):
    base = dict(
        calibration_file=None,
        preset_present=False,
        preset_source=None,
        preset_file=None,
        ran_fresh=False,
        is_stub=False,
    )
    base.update(kw)
    return resolve_calibration_source(**base)


def test_resolve_rules():
    assert _resolve(calibration_file="a.json", preset_present=True, preset_source="measured") == (
        "loaded",
        "a.json",
    )
    assert _resolve(preset_present=True, preset_source="measured") == ("measured", None)
    assert _resolve(preset_present=True, preset_source="loaded", preset_file="b.json") == ("loaded", "b.json")
    assert _resolve(preset_present=True) == ("loaded", None)
    assert _resolve(ran_fresh=True) == ("measured", None)
    assert _resolve(ran_fresh=True, is_stub=True) == ("not run", None)


def test_metadata_field_is_optional_and_serialised():
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    assert meta.calibration_source is None
    meta.calibration_source = "loaded"
    assert meta.to_dict()["calibration_source"] == "loaded"


# -- S12.2 SetupPage tracking -----------------------------------------------


def test_setup_page_source_tracking(qapp, tmp_path, monkeypatch):
    page = SetupPage()
    assert page.calibration_source is None and page.calibration_file is None

    page._on_calibration_finished(VALID)
    assert (page.calibration_source, page.calibration_file) == ("measured", None)

    cal_path = tmp_path / "calibration_5pt.json"
    save_calibration_result(cal_path, "P001", VALID)
    page.subject_id_edit.setText("P001")
    monkeypatch.setattr(
        setup_page_module.QFileDialog, "getOpenFileName", lambda *a, **k: (str(cal_path), "")
    )
    page._on_load_calibration_clicked()
    assert page.calibration_source == "loaded"
    assert page.calibration_file == str(cal_path)

    # A failed load (subject mismatch) clears the source with the result.
    page.subject_id_edit.setText("OTHER")
    page._on_load_calibration_clicked()
    assert page.calibration_result is None
    assert page.calibration_source is None and page.calibration_file is None

    # An invalid run clears it too.
    page._on_calibration_finished(INVALID)
    assert page.calibration_result is None
    assert page.calibration_source is None and page.calibration_file is None


# -- S12.5 end to end through AssessmentApp ---------------------------------


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch):
    real_load = app_module.load_task_config

    def load(task_id, *a, **k):
        cfg = real_load(task_id, *a, **k)
        cfg.setdefault("recording", {})["output_root"] = str(tmp_path / "sessions")
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    made = []

    def build(**kw):
        app = AssessmentApp("click_static", str(FIXTURE), "P001", embedded=True, **kw)
        made.append(app)
        return app

    yield build
    for app in made:
        app.recorder.close()
        app.client.stop()


def _log_and_meta(app):
    app.recorder.close()
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    return log, meta


def test_app_preset_loaded_logs_file_and_metadata(make_app):
    app = make_app(
        preset_calibration_result=VALID,
        preset_calibration_source="loaded",
        preset_calibration_file="/some/dir/calibration_5pt.json",
    )
    log, meta = _log_and_meta(app)
    assert "Calibration loaded from calibration_5pt.json — 5 points" in log
    assert meta["calibration_source"] == "loaded"


def test_app_preset_measured_logs_measured(make_app):
    app = make_app(preset_calibration_result=VALID, preset_calibration_source="measured")
    log, meta = _log_and_meta(app)
    assert "Calibration measured — 5 points, mean error 12.3px, valid." in log
    assert meta["calibration_source"] == "measured"


def test_app_calibration_file_is_loaded(make_app, tmp_path):
    cal_path = tmp_path / "calibration_5pt.json"
    save_calibration_result(cal_path, "P001", VALID)
    app = make_app(calibration_file=str(cal_path))
    log, meta = _log_and_meta(app)
    assert "Calibration loaded from calibration_5pt.json" in log
    assert meta["calibration_source"] == "loaded"


def test_app_stub_is_not_run(make_app):
    app = make_app()
    log, meta = _log_and_meta(app)
    assert "Calibration not run — " in log
    assert meta["calibration_source"] == "not run"
