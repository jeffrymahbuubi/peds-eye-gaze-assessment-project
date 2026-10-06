"""CANVAS_RESIZED: the one run event the HUD removal leaves behind (SPEC-compass-task-
flow.md 4C.7: "move its ``_check_canvas_resized`` tests here"). The canvas can still
change size mid-run (the window is resized), so the event, in physical px, stays.
Moved unchanged from the deleted ``tests/test_hud_hide_toggle.py``."""

from __future__ import annotations

from types import SimpleNamespace

from src.app import AssessmentApp
from src.data.schema import SessionMetadata


class _FakeRecorder:
    def __init__(self):
        self.events = []
        self.lines = []

    def record_event(self, kind, t_ns, **payload):
        self.events.append((kind, t_ns, payload))

    def log(self, message):
        self.lines.append(message)


def _fake_app(trial_index=3, dpr=1.0):
    app = SimpleNamespace(
        recorder=_FakeRecorder(),
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        task=SimpleNamespace(_trial_index=trial_index),
        _last_canvas_size=None,
    )
    app.canvas = SimpleNamespace(size=(1640, 1003))
    app.canvas.width = lambda: app.canvas.size[0]
    app.canvas.height = lambda: app.canvas.size[1]
    geo = SimpleNamespace(topLeft=lambda: SimpleNamespace(x=lambda: 0, y=lambda: 0))
    screen = SimpleNamespace(geometry=lambda: geo, devicePixelRatio=lambda: dpr)
    app.canvas.screen = lambda: screen
    app.canvas.mapToGlobal = lambda _p: SimpleNamespace(x=lambda: 0, y=lambda: 75)
    return app


def test_canvas_resized_baseline_then_only_on_change():
    app = _fake_app()
    AssessmentApp._check_canvas_resized(app, 1)  # baseline: no event
    AssessmentApp._check_canvas_resized(app, 2)  # unchanged: no event
    assert app.recorder.events == []
    app.canvas.size = (1920, 1003)
    AssessmentApp._check_canvas_resized(app, 3)
    AssessmentApp._check_canvas_resized(app, 4)  # unchanged again
    assert app.recorder.events == [("CANVAS_RESIZED", 3, {"canvas_w": 1920, "canvas_h": 1003})]
    assert app.recorder.lines == ["Canvas resized to 1920x1003."]


def test_canvas_resized_carries_physical_px_at_150_percent():
    app = _fake_app(dpr=1.5)
    AssessmentApp._check_canvas_resized(app, 1)
    assert app._last_canvas_size == (2460, 1504)  # 1640x1003 logical x 1.5
    app.canvas.size = (1920, 1003)
    AssessmentApp._check_canvas_resized(app, 2)
    assert app.recorder.events == [("CANVAS_RESIZED", 2, {"canvas_w": 2880, "canvas_h": 1504})]


def test_canvas_resized_ignores_zero_size_before_layout():
    app = _fake_app()
    app.canvas.size = (0, 0)
    AssessmentApp._check_canvas_resized(app, 1)
    assert app._last_canvas_size is None
    assert app.recorder.events == []


def test_the_run_events_of_the_hud_are_no_longer_emitted():
    """4C.7 / AC14: nothing in ``AssessmentApp`` toggles a HUD, changes a setting mid-run or saves
    a profile any more."""
    for name in (
        "_on_hud_hidden_changed",
        "_apply_setting",
        "_save_settings_profile",
        "_reset_settings_to_defaults",
        "calibration_snapshot",
        "_update_fps",
    ):
        assert not hasattr(AssessmentApp, name), name
