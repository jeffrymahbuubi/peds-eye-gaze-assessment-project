"""SPEC-target-size-and-motion-paths.md S9 answer: the target size preset is
resolved against the screen the run will actually appear on.

``AssessmentApp`` takes an optional ``screen`` (default None, then the canvas's
own screen); ``DashboardWindow`` passes its window's screen; and
``TaskSettingsDialog`` describes its parent's screen when it has a parent, so
the dropdown labels and the shrink hint speak about the same monitor the run is
sized for."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from src.app import AssessmentApp
from src.data.schema import SessionMetadata
from src.engine.calibration import CalibrationFileError
from src.engine.config import load_task_config
from src.engine.subject_tests import create_test
from src.engine.target_size import radius_px_for, screen_scale
from src.ui import config_flow
from src.ui.dashboard_window import DashboardWindow
from src.ui.task_settings_dialog import TaskSettingsDialog

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


def _screen(logical, dpr, physical_mm, available):
    """The attributes ``screen_scale`` and the dialog read from a QScreen."""
    return SimpleNamespace(
        geometry=lambda: _Rect(*logical),
        availableGeometry=lambda: _Rect(*available),
        devicePixelRatio=lambda: dpr,
        physicalSize=lambda: _Rect(*physical_mm),
    )


# The lab's 24 inch 1920x1080 monitor at 100 %.
LAB = _screen((1920, 1080), 1.0, (531.4, 298.9), (1920, 1000))
# A different monitor: 1280 logical px wide (150 % scale), 400 mm wide panel.
OTHER = _screen((1280, 720), 1.5, (400.0, 225.0), (1280, 680))


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeRecorder:
    def __init__(self):
        self.lines = []

    def log(self, message):
        self.lines.append(message)


def _fake_app(canvas_screen):
    def _canvas_screen():
        if isinstance(canvas_screen, Exception):
            raise canvas_screen
        return canvas_screen

    return SimpleNamespace(
        config={"app": {"viewing_distance_mm": 650}, "task": {"target": {"size": "medium"}}},
        canvas=SimpleNamespace(screen=_canvas_screen),
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        recorder=_FakeRecorder(),
    )


# -- AssessmentApp._resolve_target_size ---------------------------------------------------


def test_a_passed_in_screen_is_the_one_used():
    # The canvas would answer with OTHER (or, un-shown, a default); the caller's
    # screen must win and the canvas must not even be asked.
    app = _fake_app(AssertionError("canvas.screen() must not be consulted"))
    AssessmentApp._resolve_target_size(app, LAB)
    info = app.metadata.target_size
    assert info["mm_per_px_source"] == "edid"
    assert info["mm_per_px"] == pytest.approx(531.4 / 1920, abs=1e-4)
    assert app.config["task"]["target"]["radius_px"] == pytest.approx(102.5, abs=1.0)
    assert "EDID 531x299 mm" in app.recorder.lines[0]


def test_a_passed_in_screen_beats_a_different_canvas_screen():
    app = _fake_app(OTHER)
    AssessmentApp._resolve_target_size(app, LAB)
    assert app.config["task"]["target"]["radius_px"] == pytest.approx(102.5, abs=1.0)


def test_without_a_screen_the_canvas_screen_is_used_as_before():
    for args in ((), (None,)):
        app = _fake_app(OTHER)
        AssessmentApp._resolve_target_size(app, *args)
        expected = radius_px_for("medium", 400.0 / 1280, 650.0)
        assert app.config["task"]["target"]["radius_px"] == pytest.approx(expected, abs=0.1)
        assert "EDID 400x225 mm" in app.recorder.lines[0]


def test_screen_is_an_optional_keyword_defaulting_to_none():
    param = inspect.signature(AssessmentApp.__init__).parameters["screen"]
    assert param.default is None
    assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def _construct(**kwargs):
    app = AssessmentApp(
        task_id="click_grid", replay_path=str(FIXTURE), subject_id="T", embedded=True, **kwargs
    )
    app.timer.stop()
    return app


@pytest.fixture
def scratch_cwd(tmp_path, monkeypatch):
    # AssessmentApp writes ./sessions/ relative to the cwd.
    monkeypatch.chdir(tmp_path)


def test_init_hands_the_screen_through_to_the_resolution(qapp, scratch_cwd):
    app = _construct(screen=LAB)
    try:
        info = app.metadata.target_size
        assert info["mm_per_px_source"] == "edid"
        assert info["radius_px"] == pytest.approx(102.5, abs=1.0)
        assert app.task.targets[0].radius_px == info["radius_px"]
    finally:
        app._shutdown()


def test_init_without_a_screen_resolves_against_the_canvas_screen(qapp, scratch_cwd):
    app = _construct()
    try:
        expected = screen_scale(app.canvas.screen(), app.config.get("app", {}))
        assert app.metadata.target_size["mm_per_px"] == pytest.approx(expected.mm_per_px, abs=1e-4)
        assert app.metadata.target_size["mm_per_px_source"] == expected.source
    finally:
        app._shutdown()


# -- DashboardWindow --------------------------------------------------------------------------


def test_dashboard_passes_its_own_screen_to_the_run(qapp, scratch_cwd, monkeypatch):
    # The run the dashboard starts today is Preview Test on a test's configuration page
    # (the recorded run joins it in the next step); it builds its app the same way.
    captured = {}

    class _RecordingApp:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            raise CalibrationFileError("stop here: the arguments are what is under test")

    monkeypatch.setattr(config_flow, "AssessmentApp", _RecordingApp)
    win = DashboardWindow()
    win.screen = lambda: LAB  # the shown window's screen
    win.setup_page.subject_id_edit.setText("T")
    test = create_test(win.output_root, "T", "click_grid")
    win.config_flow.open(test.test_id)
    win.config_flow.page.preview_button.click()
    assert captured["screen"] is LAB
    assert captured["embedded"] is True


# -- TaskSettingsDialog -------------------------------------------------------------------------

LAB_LABELS = [
    "Small — 3° (≈123 px)",
    "Medium — 5° (≈205 px)",
    "Large — 8° (≈328 px)",
]


def _labels(dialog):
    combo = dialog._controls["target.size"]
    return [combo.itemText(i) for i in range(combo.count())]


class _ParentOnLab(QWidget):
    def screen(self):
        return LAB


@pytest.fixture
def dialog_own_screen_is_other(monkeypatch):
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: OTHER)


def test_dialog_describes_its_parents_screen_not_its_own(qapp, dialog_own_screen_is_other):
    parent = _ParentOnLab()
    dialog = TaskSettingsDialog("click_grid", load_task_config("click_grid"), parent=parent)
    assert _labels(dialog) == LAB_LABELS


def test_dialog_without_a_parent_uses_its_own_screen(qapp, dialog_own_screen_is_other):
    dialog = TaskSettingsDialog("click_grid", load_task_config("click_grid"))
    expected = [
        f"{label} (≈{round(2 * radius_px_for(value, 400.0 / 1280, 650.0))} px)"
        for value, label in (
            ("small", "Small — 3°"),
            ("medium", "Medium — 5°"),
            ("large", "Large — 8°"),
        )
    ]
    assert _labels(dialog) == expected
    assert _labels(dialog) != LAB_LABELS


def test_the_shrink_hint_follows_the_parents_screen_too(qapp, dialog_own_screen_is_other):
    config = load_task_config("click_grid")
    config["task"]["grid"] = {**config["task"]["grid"], "rows": 6, "cols": 6}
    parent = _ParentOnLab()
    dialog = TaskSettingsDialog("click_grid", config, parent=parent)
    # The lab screen's ~1000 px tall canvas: a 6x6 cell fits ~111 px across.
    assert dialog.fit_hint_label.text() == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )
