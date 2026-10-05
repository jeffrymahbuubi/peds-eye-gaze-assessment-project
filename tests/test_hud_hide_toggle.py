"""SPEC-hud-hide-toggle.md S6: hide/show the operator HUD, sitting memory and
the HUD_TOGGLED / CANVAS_RESIZED / metadata recording."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app import AssessmentApp
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.ui.dashboard_window import DashboardWindow
from src.ui.main_window import TaskRunView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp):
    v = TaskRunView()
    v.resize(1280, 800)
    v.show()
    qapp.processEvents()
    yield v
    v.close()


# -- S6.1 / S6.2: hide, show, focus, width -----------------------------------


def test_button_hides_and_h_shows_with_focus_on_canvas(view, qapp):
    assert view.hud_hidden is False
    view.operator_panel.hide_hud_button.click()
    qapp.processEvents()
    assert view.hud_hidden is True
    assert not view.operator_panel.isVisible()
    assert view.canvas.hasFocus()
    view.hud_shortcut.activated.emit()
    qapp.processEvents()
    assert view.hud_hidden is False
    assert view.operator_panel.isVisible()
    assert view.canvas.hasFocus()


def test_shortcut_is_h_with_widget_with_children_context(view):
    sc = view.hud_shortcut
    assert sc.key().toString() == "H"
    assert sc.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert sc.parent() is view


def test_canvas_width_grows_by_panel_width_and_returns(view, qapp):
    before = view.canvas.width()
    panel_w = view.operator_panel.width()
    assert panel_w == 280
    view.set_hud_hidden(True)
    qapp.processEvents()
    assert view.canvas.width() == before + panel_w
    view.set_hud_hidden(False)
    qapp.processEvents()
    assert view.canvas.width() == before


def test_signal_emitted_only_on_real_change(view):
    seen: list[bool] = []
    view.hud_hidden_changed.connect(seen.append)
    view.set_hud_hidden(False)  # already shown: no change
    view.set_hud_hidden(True)
    view.set_hud_hidden(True)
    view.toggle_hud()
    assert seen == [True, False]


# -- S6.3: sitting memory ------------------------------------------------------


def test_dashboard_memory_is_in_memory_and_defaults_shown(qapp):
    win = DashboardWindow()
    assert win._hud_hidden is False
    DashboardWindow._on_hud_hidden_changed(win, True)
    assert win._hud_hidden is True
    DashboardWindow._on_hud_hidden_changed(win, False)
    assert win._hud_hidden is False
    # a fresh window always starts shown
    assert DashboardWindow()._hud_hidden is False


def test_view_starts_hidden_when_applied_before_connecting(qapp):
    v = TaskRunView()
    seen: list[bool] = []
    v.set_hud_hidden(True)
    v.hud_hidden_changed.connect(seen.append)
    assert v.hud_hidden is True
    assert seen == []
    v.toggle_hud()
    assert seen == [False]


# -- S6.4: recording ----------------------------------------------------------


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


def test_each_toggle_records_one_event_and_one_log_line():
    app = _fake_app(trial_index=3)
    AssessmentApp._on_hud_hidden_changed(app, True)
    AssessmentApp._on_hud_hidden_changed(app, False)
    kinds = [(k, p) for k, _t, p in app.recorder.events]
    assert kinds == [
        ("HUD_TOGGLED", {"hidden": True, "trial": 3}),
        ("HUD_TOGGLED", {"hidden": False, "trial": 3}),
    ]
    assert app.recorder.lines == ["HUD hidden by operator (trial 4).", "HUD shown by operator (trial 4)."]
    assert app.metadata.hud_toggle_count == 2


def test_toggle_before_first_trial_has_no_trial():
    app = _fake_app(trial_index=-1)
    AssessmentApp._on_hud_hidden_changed(app, True)
    assert app.recorder.events[0][2] == {"hidden": True, "trial": None}
    assert app.recorder.lines == ["HUD hidden by operator."]


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


def test_metadata_json_has_hud_fields(tmp_path):
    meta = SessionMetadata(subject_id="P001", session_id="s", started_ns=0, hud_hidden_at_start=False)
    meta.hud_toggle_count += 1
    with SessionRecorder(meta, output_root=tmp_path):
        pass
    data = json.loads((tmp_path / "s" / "metadata.json").read_text(encoding="utf-8"))
    assert data["hud_hidden_at_start"] is False
    assert data["hud_toggle_count"] == 1
    default = SessionMetadata(subject_id="x", session_id="y", started_ns=0)
    assert default.hud_hidden_at_start is None
    assert default.hud_toggle_count == 0
    assert default.schema_version == SessionMetadata(subject_id="x", session_id="y", started_ns=0).schema_version
