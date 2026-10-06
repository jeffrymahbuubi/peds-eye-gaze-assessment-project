"""SPEC-target-size-and-motion-paths.md S4.5 / acceptance criterion 6.8: the
Task settings dialog's new ``choice`` kind -- Target size for click_grid and
Movement path for follow_moving -- and saving/restoring them in a settings
profile."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from src.app import AssessmentApp
from src.engine.config import deep_merge, load_task_config
from src.engine.settings_profile import (
    load_settings_profile,
    resolve_settings_precedence,
    save_settings_profile,
)
from src.engine.target_size import ScaleInfo, apply_target_size
from src.ui.settings_registry import (
    MOTION_PATH_CHOICES,
    TARGET_SIZE_CHOICES,
    get_nested,
    initial_structural_values,
    structural_settings_for_task,
)
from src.ui.slider_spin import SliderSpinRow
from src.ui.task_settings_dialog import TaskSettingsDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _keys(task_id):
    return [s.key for s in structural_settings_for_task(task_id)]


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


def _lab_screen(avail=(1920, 1000)):
    """A 24 inch 1920x1080 monitor at 100 % with ~1000 px of usable height."""
    return SimpleNamespace(
        geometry=lambda: _Rect(1920, 1080),
        availableGeometry=lambda: _Rect(*avail),
        devicePixelRatio=lambda: 1.0,
        physicalSize=lambda: _Rect(531.4, 298.9),
    )


@pytest.fixture
def lab_screen(monkeypatch):
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: _lab_screen())


def _dialog(task_id, qapp, **grid):
    config = load_task_config(task_id)
    if grid:
        config["task"]["grid"] = {**config["task"]["grid"], **grid}
    return TaskSettingsDialog(task_id, config)


# -- registry ---------------------------------------------------------------------------


def test_click_grid_has_a_size_choice_and_no_px_radius():
    keys = _keys("click_grid")
    assert "target.size" in keys
    assert "target.radius_px" not in keys


def test_every_target_task_has_a_size_choice_and_no_px_radius_row():
    # Phase B (SPEC S11.3): no px radius control remains anywhere.
    for task_id in ("click_grid", "click_static", "follow_moving"):
        assert "target.size" in _keys(task_id)
    assert "layout.size" in _keys("scanning")
    assert "layout.size" not in _keys("click_static")
    for task_id in ("click_grid", "click_static", "follow_moving", "scanning"):
        assert not any(key.endswith("radius_px") for key in _keys(task_id))


def test_follow_moving_has_a_movement_path_choice_and_only_it():
    assert "motion.path" in _keys("follow_moving")
    for task_id in ("click_static", "click_grid", "scanning"):
        assert "motion.path" not in _keys(task_id)


def test_choice_values_match_the_spec():
    assert [v for v, _label in TARGET_SIZE_CHOICES] == ["small", "medium", "large"]
    assert [label for _v, label in TARGET_SIZE_CHOICES] == [
        "Small — 3°", "Medium — 5°", "Large — 8°",
    ]
    assert [v for v, _label in MOTION_PATH_CHOICES] == [
        "circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl",
    ]


def test_initial_values_come_from_the_task_yaml():
    assert initial_structural_values("click_grid", load_task_config("click_grid"))["target.size"] == "medium"
    assert initial_structural_values("follow_moving", load_task_config("follow_moving"))["motion.path"] == "circular"


def test_initial_value_falls_back_to_the_setting_default_for_a_missing_or_invalid_value():
    cfg = load_task_config("click_grid")
    cfg["task"]["target"]["size"] = "gigantic"
    assert initial_structural_values("click_grid", cfg)["target.size"] == "medium"
    cfg = load_task_config("follow_moving")
    del cfg["task"]["motion"]["path"]
    assert initial_structural_values("follow_moving", cfg)["motion.path"] == "horizontal"


# -- dialog: click_grid ------------------------------------------------------------------


def test_grid_click_dialog_shows_a_size_combo_and_no_px_slider(qapp):
    d = _dialog("click_grid", qapp)
    assert isinstance(d._controls["target.size"], QComboBox)
    assert "target.radius_px" not in d._controls
    # Only the numeric rows are sliders: trials, rows, cols.
    assert len(d.findChildren(SliderSpinRow)) == 3
    assert d._controls["target.size"].currentData() == "medium"


def test_size_items_show_degrees_and_the_diameter_on_this_monitor(qapp, lab_screen):
    dialog = _dialog("click_grid", qapp)
    combo = dialog._controls["target.size"]
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels == [
        "Small — 3° (≈123 px)",
        "Medium — 5° (≈205 px)",
        "Large — 8° (≈328 px)",
    ]
    assert [combo.itemData(i) for i in range(combo.count())] == ["small", "medium", "large"]


def test_overrides_return_the_chosen_preset_as_a_string(qapp):
    d = _dialog("click_grid", qapp)
    combo = d._controls["target.size"]
    combo.setCurrentIndex(combo.findData("large"))
    result = d.overrides()
    assert result["target"] == {"size": "large"}  # no radius_px for click_grid
    assert isinstance(result["target"]["size"], str)
    assert result["grid"] == {"rows": 3, "cols": 3, "gap": "standard"}  # the Cell gap row's value


def test_dialog_restores_the_size_from_the_config(qapp):
    cfg = load_task_config("click_grid")
    cfg["task"]["target"]["size"] = "small"
    d = TaskSettingsDialog("click_grid", cfg)
    assert d._controls["target.size"].currentData() == "small"
    assert d.overrides()["target"]["size"] == "small"


# -- dialog: shrink hint ------------------------------------------------------------------


def test_no_hint_when_the_preset_fits(qapp, lab_screen):
    d = _dialog("click_grid", qapp)  # 3x3 Medium on a 1000 px tall canvas
    assert d.fit_hint.isHidden()


def test_hint_appears_when_the_size_will_be_shrunk_and_tracks_rows_and_cols(qapp, lab_screen):
    d = _dialog("click_grid", qapp)
    d._controls["grid.rows"].setValue(6)  # the row count alone makes the cells short
    assert not d.fit_hint.isHidden()
    assert "6 x 3 grid" in d.fit_hint_label.text()
    d._controls["grid.cols"].setValue(6)
    assert not d.fit_hint.isHidden()
    assert d.fit_hint_label.text() == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )
    d._controls["grid.rows"].setValue(3)
    d._controls["grid.cols"].setValue(3)
    assert d.fit_hint.isHidden()


def test_hint_follows_the_size_combo(qapp, lab_screen):
    d = _dialog("click_grid", qapp, rows=4, cols=4)
    # 4x4 on ~1000 px: a cell fits ~167 px across -- Medium (205) is shrunk, Small (123) is not.
    combo = d._controls["target.size"]
    assert not d.fit_hint.isHidden()
    assert "167 px" in d.fit_hint_label.text()
    combo.setCurrentIndex(combo.findData("small"))
    assert d.fit_hint.isHidden()
    combo.setCurrentIndex(combo.findData("large"))
    assert not d.fit_hint.isHidden()


def test_hint_is_already_showing_for_a_grid_that_starts_too_small(qapp, lab_screen):
    d = _dialog("click_grid", qapp, rows=6, cols=6)
    assert not d.fit_hint.isHidden()


def test_follow_moving_dialog_never_shows_a_hint(qapp, lab_screen):
    assert _dialog("follow_moving", qapp).fit_hint.isHidden()


# -- dialog: follow_moving ------------------------------------------------------------------


def test_follow_moving_dialog_shows_a_path_combo_and_a_size_combo_not_a_px_slider(qapp):
    d = _dialog("follow_moving", qapp)
    combo = d._controls["motion.path"]
    assert isinstance(combo, QComboBox)
    assert [combo.itemData(i) for i in range(combo.count())] == [v for v, _l in MOTION_PATH_CHOICES]
    assert combo.itemText(0) == "Circular"
    assert combo.itemText(4) == "Diagonal ↙ (top-right ↔ bottom-left)"
    assert combo.currentData() == "circular"
    assert isinstance(d._controls["target.size"], QComboBox)
    assert "target.radius_px" not in d._controls


@pytest.mark.parametrize("path", [v for v, _l in MOTION_PATH_CHOICES])
def test_path_choice_is_returned_in_overrides(qapp, path):
    d = _dialog("follow_moving", qapp)
    combo = d._controls["motion.path"]
    combo.setCurrentIndex(combo.findData(path))
    result = d.overrides()
    assert result["motion"]["path"] == path
    assert isinstance(result["motion"]["path"], str)
    assert "select_window_ms" in result["motion"]  # the other motion row still there


# -- 6.8: saved to and restored from a settings profile --------------------------------------

LIVE = {"dwell.threshold_ms": 900}


def test_string_choices_round_trip_through_a_settings_profile(tmp_path):
    structural = {"trials": 12, "target": {"size": "large"}, "grid": {"rows": 6, "cols": 6}}
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, structural)
    assert load_settings_profile(tmp_path, "S1", "click_grid")["structural"] == structural

    structural = {"motion": {"path": "diagonal_trbl", "select_window_ms": 2000}}
    save_settings_profile(tmp_path, "S1", "follow_moving", LIVE, structural)
    assert load_settings_profile(tmp_path, "S1", "follow_moving")["structural"] == structural


@pytest.mark.parametrize(
    "task_id, structural, key, expected",
    [
        ("click_grid", {"target": {"size": "large"}, "grid": {"rows": 5, "cols": 5}}, "target.size", "large"),
        ("follow_moving", {"motion": {"path": "vertical"}}, "motion.path", "vertical"),
        ("follow_moving", {"motion": {"path": "diagonal_tlbr"}}, "motion.path", "diagonal_tlbr"),
    ],
)
def test_saved_choice_is_restored_into_the_dialog(qapp, tmp_path, task_id, structural, key, expected):
    # The same route the dashboard takes: profile -> resolved structural
    # overrides -> merged over the task YAML -> the dialog's initial values.
    save_settings_profile(tmp_path, "S1", task_id, LIVE, structural)
    resolved = resolve_settings_precedence(None, load_settings_profile(tmp_path, "S1", task_id))
    assert resolved["source"] == "profile"
    config = load_task_config(task_id)
    config["task"] = deep_merge(config["task"], resolved["structural_overrides"])

    dialog = TaskSettingsDialog(task_id, config)
    assert dialog._controls[key].currentData() == expected
    assert get_nested(dialog.overrides(), key) == expected  # and it round-trips back out


def test_a_dialog_choice_is_what_gets_saved_and_applied_to_the_run(qapp, tmp_path):
    d = _dialog("click_grid", qapp)
    combo = d._controls["target.size"]
    combo.setCurrentIndex(combo.findData("large"))
    overrides = d.overrides()

    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, overrides)
    stored = load_settings_profile(tmp_path, "S1", "click_grid")["structural"]
    config = load_task_config("click_grid")
    config["task"] = deep_merge(config["task"], stored)  # as AssessmentApp.__init__ does
    app = SimpleNamespace(
        config=config,
        canvas=SimpleNamespace(screen=lambda: None),
        metadata=SimpleNamespace(target_size=None),
        recorder=SimpleNamespace(log=lambda _m: None),
    )
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.target_size["preset"] == "large"
    expected = apply_target_size({"target": {"size": "large"}}, ScaleInfo(0.2768, "fallback"), 650.0)
    assert app.config["task"]["target"]["radius_px"] == pytest.approx(expected["radius_px"], abs=0.5)


def test_an_older_profile_with_a_px_radius_still_loads_into_the_new_dialog(qapp, tmp_path):
    # Written before click_grid had a size preset: a px radius, no `size`.
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, {"target": {"radius_px": 120}})
    resolved = resolve_settings_precedence(None, load_settings_profile(tmp_path, "S1", "click_grid"))
    config = load_task_config("click_grid")
    config["task"] = deep_merge(config["task"], resolved["structural_overrides"])
    dialog = TaskSettingsDialog("click_grid", config)
    assert dialog._controls["target.size"].currentData() == "medium"
    assert "target.radius_px" not in dialog.overrides().get("target", {})
