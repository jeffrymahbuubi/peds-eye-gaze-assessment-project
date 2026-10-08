"""SPEC-display-scaling-cursor-accuracy.md S8.8: metadata canvas fields in
physical px, relative to the canvas's own QScreen origin."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.app import AssessmentApp
from src.data.schema import SessionMetadata
from src.tasks.base_task import canvas_geometry_physical
from tests.recorder_helpers import recorder_in


def test_helper_dpr_1_is_identity():
    assert canvas_geometry_physical(0, 0, 0, 75, 1640, 1005, 1.0) == (1640, 1005, 0, 75)


def test_helper_dpr_1_5_spec_example():
    assert canvas_geometry_physical(0, 0, 0, 75, 1640, 957, 1.5) == (2460, 1436, 0, 112)


def test_helper_dpr_1_25():
    assert canvas_geometry_physical(0, 0, 0, 60, 1000, 600, 1.25) == (1250, 750, 0, 75)


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
def test_helper_second_monitor_uses_screen_origin(dpr):
    primary = canvas_geometry_physical(0, 0, 0, 75, 1000, 600, dpr)
    second = canvas_geometry_physical(1920, 0, 1920, 75, 1000, 600, dpr)
    assert second == primary


class _FakeRecorder:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        self.lines.append(message)


def _fake_app(dpr: float, device_info=None):
    geo = SimpleNamespace(
        width=lambda: round(1920 / dpr),
        height=lambda: round(1080 / dpr),
        topLeft=lambda: SimpleNamespace(x=lambda: 0, y=lambda: 0),
    )
    screen = SimpleNamespace(
        geometry=lambda: geo,
        devicePixelRatio=lambda: dpr,
        refreshRate=lambda: 60.0,
        physicalSize=lambda: SimpleNamespace(width=lambda: 527.0, height=lambda: 296.0),
    )
    canvas = SimpleNamespace(
        width=lambda: 1640,
        height=lambda: 957,
        screen=lambda: screen,
        mapToGlobal=lambda _p: SimpleNamespace(x=lambda: 0, y=lambda: 75),
    )
    app = SimpleNamespace(
        canvas=canvas,
        client=SimpleNamespace(device_info=device_info),
        config={"app": {}},
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        recorder=_FakeRecorder(),
        _geometry_recorded=False,
        _pointer_is_mouse=False,  # a gaze run (a Mouse run with no tracker is in test_mouse_run.py)
        _gaze_recorded=True,
    )
    app._record_display = lambda: AssessmentApp._record_display(app)
    return app


def _info():
    return SimpleNamespace(
        screen_width=1920, screen_height=1080, screen_x=0, screen_y=0, rate_hz=60, bus="USB3", serial="1"
    )


def test_record_geometry_dpr_1_matches_todays_values():
    app = _fake_app(1.0, _info())
    AssessmentApp._record_geometry(app)
    m = app.metadata
    assert (m.canvas_width_px, m.canvas_height_px) == (1640, 957)
    assert (m.canvas_offset_x_px, m.canvas_offset_y_px) == (0, 75)
    geometry = [ln for ln in app.recorder.lines if ln.startswith("Geometry:")]
    assert len(geometry) == 1
    assert "canvas 1640x957px at +0,+75," in geometry[0]
    assert "Windows scale" not in geometry[0]


def test_record_geometry_dpr_1_5_is_physical_and_names_scale():
    app = _fake_app(1.5, _info())
    AssessmentApp._record_geometry(app)
    m = app.metadata
    assert (m.canvas_width_px, m.canvas_height_px) == (2460, 1436)
    assert (m.canvas_offset_x_px, m.canvas_offset_y_px) == (0, 112)
    assert m.canvas_units == "physical"
    geometry = [ln for ln in app.recorder.lines if ln.startswith("Geometry:")][0]
    assert "canvas 2460x1436px at +0,+112 (physical px; Windows scale 150 %)" in geometry


def test_record_geometry_replay_still_fills_canvas_fields():
    app = _fake_app(1.5, None)
    AssessmentApp._record_geometry(app)
    m = app.metadata
    assert m.screen_width_px is None
    assert (m.canvas_width_px, m.canvas_offset_y_px) == (2460, 112)
    assert m.canvas_units == "physical"


def test_metadata_json_canvas_units_and_old_metadata_still_loads(tmp_path):
    app = _fake_app(1.5, _info())
    AssessmentApp._record_geometry(app)
    with recorder_in(tmp_path, app.metadata):
        pass
    data = json.loads((tmp_path / "s" / "metadata.json").read_text(encoding="utf-8"))
    assert data["canvas_units"] == "physical"
    assert data["canvas_width_px"] == 2460
    # A v1.0.0 metadata.json has no canvas_units key: default is None.
    assert SessionMetadata(subject_id="x", session_id="y", started_ns=0).canvas_units is None
    old = {k: v for k, v in data.items() if k != "canvas_units"}
    fields = SessionMetadata.__dataclass_fields__
    restored = SessionMetadata(**{k: v for k, v in old.items() if k in fields})
    assert restored.canvas_units is None
