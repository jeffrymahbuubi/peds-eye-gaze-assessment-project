"""SPEC-compass-task-flow.md 4B.3 / HB11: the two shrink hints extracted into
``src/engine/target_size.py`` (``grid_fit_hint``, ``icon_fit_hint``), the
settings dialog calling them, and the dialog's new bool branch (the sound toggles)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox

from src.engine.config import load_task_config
from src.engine.target_size import (
    gap_px_for,
    grid_fit_hint,
    icon_fit_hint,
    radius_px_for,
)
from src.tasks.scanning import scanning_layout_slots
from src.ui import task_settings_dialog
from src.ui.settings_registry import structural_settings_for_task
from src.ui.settings_snapshot import settings_snapshot
from src.ui.slider_spin import SliderSpinRow
from src.ui.task_settings_dialog import TaskSettingsDialog

MM_PER_PX = 531.4 / 1920  # the lab's 24 inch 1920x1080 monitor
DISTANCE = 650.0
CANVAS = (1920.0, 1000.0)  # what the dialog sees on that monitor (see _lab_screen)
MEDIUM = radius_px_for("medium", MM_PER_PX, DISTANCE)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


@pytest.fixture
def lab_screen(monkeypatch):
    screen = SimpleNamespace(
        geometry=lambda: _Rect(1920, 1080),
        availableGeometry=lambda: _Rect(*CANVAS),
        devicePixelRatio=lambda: 1.0,
        physicalSize=lambda: _Rect(531.4, 298.9),
    )
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: screen)


def _dialog(task_id, **grid):
    config = load_task_config(task_id)
    if grid:
        config["task"]["grid"] = {**config["task"]["grid"], **grid}
    return TaskSettingsDialog(task_id, config)


# -- grid_fit_hint (pure) -----------------------------------------------------------------


def test_no_grid_hint_when_the_preset_fits():
    assert grid_fit_hint(3, 3, *CANVAS, MEDIUM) is None


def test_the_grid_hint_says_how_far_the_size_is_shrunk():
    assert grid_fit_hint(6, 6, *CANVAS, MEDIUM) == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )
    assert "6 x 3 grid" in grid_fit_hint(6, 3, *CANVAS, MEDIUM)


def test_a_capped_gap_is_reported_alone_or_with_the_shrunk_size():
    wide = gap_px_for("extra_wide", MM_PER_PX, DISTANCE)
    # 6 x 6 with a 2 degree gap: the gap is cut to half the pitch AND the target shrunk.
    both = grid_fit_hint(6, 6, *CANVAS, MEDIUM, 0.12, wide)
    assert both.startswith("Gap limited to ≈ ")
    assert " and targets shrunk to ≈ " in both
    assert both.endswith("to fit a 6 x 6 grid (approximate)")
    # A 5 x 5 grid with a target far smaller than any preset: the gap is limited, the
    # target is not.
    only = grid_fit_hint(5, 5, *CANVAS, 10.0, 0.12, wide)
    assert only.startswith("Gap limited to ≈ ")
    assert "shrunk" not in only
    assert only.endswith("to fit a 5 x 5 grid (approximate)")


def test_a_gap_that_fits_and_a_fitting_size_give_no_hint():
    wide = gap_px_for("wide", MM_PER_PX, DISTANCE)
    small = radius_px_for("small", MM_PER_PX, DISTANCE)
    assert grid_fit_hint(3, 3, *CANVAS, small, 0.12, wide) is None


def test_the_grid_hint_uses_the_given_margin():
    assert grid_fit_hint(3, 3, *CANVAS, MEDIUM, 0.40) is not None  # almost no room left


# -- icon_fit_hint (pure) -----------------------------------------------------------------


def test_the_icon_hint_matches_the_text_of_the_dialog_before_the_extraction():
    slots = scanning_layout_slots(8, "grid", 0.14)
    large = radius_px_for("large", MM_PER_PX, DISTANCE)
    assert icon_fit_hint(8, slots, *CANVAS, large) == (
        "Icons will be shrunk to ≈ 211 px to fit 8 icons (approximate)"
    )


def test_no_icon_hint_when_the_icons_fit():
    slots = scanning_layout_slots(4, "grid", 0.14)
    assert icon_fit_hint(4, slots, *CANVAS, MEDIUM) is None
    assert icon_fit_hint(8, scanning_layout_slots(8, "grid", 0.14), *CANVAS,
                         radius_px_for("small", MM_PER_PX, DISTANCE)) is None


# -- the dialog calls them ----------------------------------------------------------------


def test_the_dialog_shows_exactly_what_grid_fit_hint_returns(qapp, lab_screen, monkeypatch):
    seen = []

    def stub(*args):
        seen.append(args)
        return "STUB HINT"

    monkeypatch.setattr(task_settings_dialog, "grid_fit_hint", stub)
    d = _dialog("click_grid")
    assert not d.fit_hint.isHidden()
    assert d.fit_hint_label.text() == "STUB HINT"
    rows, cols, canvas_w, canvas_h, wanted, margin, gap = seen[-1]
    assert (rows, cols, canvas_w, canvas_h) == (3, 3, *CANVAS)
    assert wanted == pytest.approx(MEDIUM)
    assert margin == 0.12 and gap is None  # YAML margin, the Standard gap
    monkeypatch.setattr(task_settings_dialog, "grid_fit_hint", lambda *a: None)
    d._controls["grid.rows"].setValue(4)
    assert d.fit_hint.isHidden()


def test_the_dialog_shows_exactly_what_icon_fit_hint_returns(qapp, lab_screen, monkeypatch):
    seen = []

    def stub(*args):
        seen.append(args)
        return "ICON STUB"

    monkeypatch.setattr(task_settings_dialog, "icon_fit_hint", stub)
    d = _dialog("scanning")
    assert d.fit_hint_label.text() == "ICON STUB"
    n_icons, slots, canvas_w, canvas_h, wanted = seen[-1]
    assert n_icons == 4 and len(slots) == 4
    assert (canvas_w, canvas_h) == CANVAS
    assert wanted == pytest.approx(MEDIUM)


def test_the_dialog_and_the_shared_function_agree_on_every_grid_state(qapp, lab_screen):
    for rows, cols, size, gap in ((3, 3, "medium", "standard"), (6, 6, "medium", "standard"),
                                  (4, 4, "large", "wide"), (6, 6, "large", "extra_wide")):
        d = _dialog("click_grid")
        d._controls["grid.rows"].setValue(rows)
        d._controls["grid.cols"].setValue(cols)
        d._controls["target.size"].setCurrentIndex(d._controls["target.size"].findData(size))
        d._controls["grid.gap"].setCurrentIndex(d._controls["grid.gap"].findData(gap))
        expected = grid_fit_hint(
            rows, cols, *CANVAS, radius_px_for(size, MM_PER_PX, DISTANCE), 0.12,
            gap_px_for(gap, MM_PER_PX, DISTANCE),
        )
        assert (None if d.fit_hint.isHidden() else d.fit_hint_label.text()) == expected


# -- the bool branch (HB11) ----------------------------------------------------------------


@pytest.mark.parametrize("task_id", ["click_static", "click_grid", "follow_moving", "scanning"])
def test_the_sound_toggles_are_check_boxes_not_sliders(qapp, task_id):
    d = _dialog(task_id)
    for key in ("feedback.hit_sound", "feedback.miss_sound"):
        assert isinstance(d._controls[key], QCheckBox)
        assert d._controls[key].isChecked()  # the task YAMLs have both on
    n_sliders = sum(1 for s in structural_settings_for_task(task_id) if s.kind in ("int", "float"))
    assert len(d.findChildren(SliderSpinRow)) == n_sliders
    assert not any(
        isinstance(d._controls[s.key], QComboBox)
        for s in structural_settings_for_task(task_id) if s.kind == "bool"
    )


def test_unticking_a_sound_is_returned_in_the_overrides(qapp):
    d = _dialog("click_grid")
    assert d.overrides()["feedback"] == {"hit_sound": True, "miss_sound": True}
    d._controls["feedback.hit_sound"].setChecked(False)
    out = d.overrides()["feedback"]
    assert out == {"hit_sound": False, "miss_sound": True}
    assert all(isinstance(v, bool) for v in out.values())


def test_the_dialog_starts_from_the_configs_sound_values(qapp):
    config = load_task_config("click_grid")
    config["task"]["feedback"]["miss_sound"] = False
    d = TaskSettingsDialog("click_grid", config)
    assert d._controls["feedback.hit_sound"].isChecked()
    assert not d._controls["feedback.miss_sound"].isChecked()
    assert d.overrides()["feedback"] == {"hit_sound": True, "miss_sound": False}


def test_the_dialogs_overrides_are_the_snapshots_structural_block(qapp):
    """AB4, data part: on an untouched dialog, ``overrides()`` is the complete
    ``structural`` of the snapshot -- the sound toggles included."""
    for task_id in ("click_static", "click_grid", "follow_moving", "scanning"):
        config = load_task_config(task_id)
        assert TaskSettingsDialog(task_id, config).overrides() == settings_snapshot(
            task_id, config
        )["structural"], task_id
