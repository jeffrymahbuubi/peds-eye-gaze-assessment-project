"""SPEC-compass-task-flow.md 4B.1-4B.5, acceptance AB1-AB7, AB11 and AB12: the
``TaskConfigPage`` widget (offscreen Qt, no tracker, nothing written).

The page is a renderer of ``config_groups_for_task``, so the controls are held
against the registries; its values are held against ``settings_snapshot`` and
``TaskSettingsDialog.overrides()``; its shrink hints against the dialog's.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
)

from src.engine.config import load_task_config
from src.engine.settings_profile import NamedConfig
from src.engine.subject_test_record import validate_test_name
from src.engine.target_size import gap_px_for, grid_fit_hint, icon_fit_hint, radius_px_for
from src.tasks.scanning import scanning_layout_slots
from src.ui import wtmh_theme
from src.ui.config_widgets import RadioChoice, choice_label, screen_dpr
from src.ui.settings_registry import (
    config_groups_for_task,
    live_settings_for_task,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import complete_settings, settings_snapshot
from src.ui.slider_spin import SliderSpinRow
from src.ui.task_config_page import TaskConfigPage
from src.ui.task_settings_dialog import TaskSettingsDialog

TASKS = ("click_static", "click_grid", "follow_moving", "scanning")
DISPLAY = {"click_static": "Static Click", "click_grid": "Grid Click",
           "follow_moving": "Follow & Click", "scanning": "Scanning Search"}
MM_PER_PX = 531.4 / 1920  # the lab's 24 inch 1920x1080 monitor
DISTANCE = 650.0
CANVAS = (1920.0, 1000.0)


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


LAB_SCREEN = SimpleNamespace(
    geometry=lambda: _Rect(1920, 1080),
    availableGeometry=lambda: _Rect(*CANVAS),
    devicePixelRatio=lambda: 1.0,
    physicalSize=lambda: _Rect(531.4, 298.9),
)


@pytest.fixture
def lab_screen(monkeypatch):
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: LAB_SCREEN)


@pytest.fixture
def answers(monkeypatch):
    """Replace the page's modal question: ``answers.reply`` is the answer, ``answers.asked``
    the questions put to it as ``(title, text)``."""
    box = SimpleNamespace(reply=True, asked=[])

    def fake_ask(self, title, text, accept, reject, *, default_accept=True):
        box.asked.append((title, text))
        return box.reply

    monkeypatch.setattr(TaskConfigPage, "_ask", fake_ask)
    return box


def _page(task_id, **load):
    config = load_task_config(task_id)
    page = TaskConfigPage(task_id, config, screen=LAB_SCREEN)
    page.set_context(subject_id="TESTING", existing_test_names=["Other test"])
    page.load_values(test_name=f"{DISPLAY[task_id]} 1", **load)
    return page, config


def _named(name, live=None, structural=None, saved_at="2026-10-05T14:12:00+08:00"):
    return NamedConfig(name, saved_at, Path(f"{name}.json"), live or {}, structural or {})


def _select(page, name):
    """What the operator does: pick ``name`` from the Configuration Name list."""
    combo = page._form.config_combo
    index = combo.findText(name)
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def _widgets_of_column(page, column):
    """The cards of a column, top to bottom (not the "Advanced" title or an alert box)."""
    layout = page.scroll_area.widget().layout().itemAtPosition(0, column).layout()
    widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
    return [w for w in widgets if w.objectName() == "wtmhCard"]


# -- AB1 / AB2: one control per setting, none hidden ---------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_page_has_exactly_the_controls_of_the_task(qapp, task_id):
    page, _ = _page(task_id)
    keys = {s.key for s in live_settings_for_task(task_id)} | {
        s.key for s in structural_settings_for_task(task_id)
    }
    assert set(page._form.controls) == keys  # AB2: every key, exactly once (a dict)
    assert not any("radius" in key for key in keys)  # AB1: no px target-radius control
    for name, cls in (("cfgTestName", QLineEdit), ("cfgConfigName", QComboBox),
                      ("cfgNotes", QPlainTextEdit), ("cfgPreview", QPushButton),
                      ("cfgSave", QPushButton), ("cfgCancel", QPushButton),
                      ("cfgReset", QPushButton)):
        assert len(page.findChildren(cls, name)) == 1, name
    # AB2: none hidden (greying is the only thing a control ever does).
    assert not any(widget.isHidden() for widget in page._form.controls.values())


@pytest.mark.parametrize("task_id", TASKS)
def test_the_cards_and_their_columns_follow_the_layout_spec(qapp, task_id):
    page, _ = _page(task_id)
    groups = config_groups_for_task(task_id)
    assert list(page.cards) == [g.id for g in groups]
    for column in range(3):
        expected = [page.cards[g.id] for g in groups if g.column == column]
        assert _widgets_of_column(page, column) == expected


@pytest.mark.parametrize("task_id", TASKS)
def test_each_control_is_the_widget_its_kind_calls_for(qapp, task_id):
    page, _ = _page(task_id)
    expected = {"check": QCheckBox, "slider_int": SliderSpinRow, "slider_float": SliderSpinRow,
                "radio": RadioChoice}
    for group in config_groups_for_task(task_id):
        for control in group.controls:
            if control.setting is None:
                continue
            widget = page._form.controls[control.key]
            assert isinstance(widget, expected[control.widget]), control.key
            assert widget.objectName() == "cfg_" + control.key.replace(".", "_")


def test_size_and_gap_and_path_are_radio_groups_with_named_buttons(qapp):
    page, _ = _page("click_grid")
    for name in ("cfg_target_size_small", "cfg_target_size_medium", "cfg_target_size_large",
                 "cfg_grid_gap_standard", "cfg_grid_gap_wide", "cfg_grid_gap_extra_wide"):
        assert len(page.findChildren(QRadioButton, name)) == 1, name
    follow, _ = _page("follow_moving")
    for path in ("circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl"):
        assert follow.findChild(QRadioButton, f"cfg_motion_path_{path}") is not None
    scanning, _ = _page("scanning")
    assert scanning.findChild(QRadioButton, "cfg_layout_size_large") is not None
    assert scanning.findChild(QRadioButton, "cfg_target_size_large") is None


def test_the_size_labels_carry_the_px_of_this_monitor(qapp):
    page, _ = _page("click_grid")
    medium = page.findChild(QRadioButton, "cfg_target_size_medium")
    diameter = round(2 * radius_px_for("medium", MM_PER_PX, DISTANCE))
    assert medium.text() == f"Medium (5°, about {diameter} px)"
    wide = page.findChild(QRadioButton, "cfg_grid_gap_wide")
    assert wide.text() == f"Wide (1°, about {round(gap_px_for('wide', MM_PER_PX, DISTANCE))} px)"
    assert page.findChild(QRadioButton, "cfg_grid_gap_standard").text() == "Standard"


# -- FX4: the px in a size or gap label are the panel's, whatever the Windows scaling ---------------

# The same 24 inch monitor at 150 % Windows scaling: Qt's logical screen is 1280 x 720 and one
# logical px is 1.5 physical px (mm per logical px is 1.5 times the 100 % value).
SCALED_SCREEN = SimpleNamespace(
    geometry=lambda: _Rect(1280, 720),
    availableGeometry=lambda: _Rect(CANVAS[0] / 1.5, CANVAS[1] / 1.5),  # the lab canvas, in logical px
    devicePixelRatio=lambda: 1.5,
    physicalSize=lambda: _Rect(531.4, 298.9),
)


def _px_labels(page):
    names = ("cfg_target_size_small", "cfg_target_size_medium", "cfg_target_size_large",
             "cfg_grid_gap_standard", "cfg_grid_gap_wide", "cfg_grid_gap_extra_wide")
    return {name: page.findChild(QRadioButton, name).text() for name in names}


def test_choice_label_shows_physical_px_when_given_a_device_pixel_ratio():
    mm_per_logical_px = MM_PER_PX * 1.5  # the 150 % screen
    logical = 2 * radius_px_for("small", mm_per_logical_px, DISTANCE)
    assert choice_label("target.size", "small", "Small (3°)", mm_per_logical_px, DISTANCE) == (
        f"Small (3°, about {round(logical)} px)"  # no ratio: the logical px, as before (82)
    )
    assert choice_label("target.size", "small", "Small (3°)", mm_per_logical_px, DISTANCE, 1.5) == (
        f"Small (3°, about {round(logical * 1.5)} px)"  # the panel's px (123)
    )
    gap = gap_px_for("extra_wide", mm_per_logical_px, DISTANCE)
    assert choice_label("grid.gap", "extra_wide", "Extra wide (2°)", mm_per_logical_px, DISTANCE, 1.5) == (
        f"Extra wide (2°, about {round(gap * 1.5)} px)"
    )
    assert choice_label("layout.size", "large", "Large (8°)", mm_per_logical_px, DISTANCE, 1.5).endswith(
        f"about {round(2 * radius_px_for('large', mm_per_logical_px, DISTANCE) * 1.5)} px)"
    )
    # A standard gap has no angle, and any other key is returned as it is.
    assert choice_label("grid.gap", "standard", "Standard", mm_per_logical_px, DISTANCE, 1.5) == "Standard"
    assert choice_label("motion.path", "circular", "Circular", mm_per_logical_px, DISTANCE, 1.5) == "Circular"


def test_screen_dpr_reads_the_ratio_and_never_returns_zero():
    assert screen_dpr(SCALED_SCREEN) == 1.5 and screen_dpr(LAB_SCREEN) == 1.0
    assert screen_dpr(None) == 1.0
    assert screen_dpr(SimpleNamespace(devicePixelRatio=lambda: 0.0)) == 1.0


def test_the_labels_show_physical_px_at_a_scaled_display(qapp):
    config = load_task_config("click_grid")
    scaled = TaskConfigPage("click_grid", config, screen=SCALED_SCREEN)
    unscaled = TaskConfigPage("click_grid", config, screen=LAB_SCREEN)
    # The same monitor: a 3 degree target is the same number of the panel's px at 100 % and
    # at 150 %, and that number is the physical one (not the 82 logical px of the 150 % screen).
    assert _px_labels(scaled) == _px_labels(unscaled)
    small = scaled.findChild(QRadioButton, "cfg_target_size_small").text()
    assert small == f"Small (3°, about {round(2 * radius_px_for('small', MM_PER_PX, DISTANCE))} px)"
    logical = round(2 * radius_px_for("small", MM_PER_PX * 1.5, DISTANCE))
    assert f"about {logical} px" not in small and logical < round(logical * 1.5)
    scanning = TaskConfigPage("scanning", load_task_config("scanning"), screen=SCALED_SCREEN)
    large = scanning.findChild(QRadioButton, "cfg_layout_size_large").text()
    assert large == f"Large (8°, about {round(2 * radius_px_for('large', MM_PER_PX, DISTANCE))} px)"


def test_the_cards_scroll_above_a_pinned_footer(qapp):
    page, _ = _page("click_grid")
    scroll = page.scroll_area
    assert isinstance(scroll, QScrollArea) and scroll.objectName() == "wtmhConfigScroll"
    assert not scroll.viewport().autoFillBackground()
    assert not scroll.widget().autoFillBackground()
    for button in (page.preview_button, page.save_button, page.cancel_button):
        assert not scroll.isAncestorOf(button)
        assert not button.autoDefault()  # Enter never saves (4B.5)
    assert scroll.widget().maximumWidth() == 1500
    assert "wtmhConfigScroll" in wtmh_theme.STYLESHEET
    assert "QRadioButton" in wtmh_theme.STYLESHEET


@pytest.mark.parametrize("task_id", TASKS)
def test_every_control_has_a_tooltip(qapp, task_id):
    page, _ = _page(task_id)
    for key, widget in page._form.controls.items():
        assert widget.toolTip(), key
    form = page._form
    for widget in (form.test_name_edit, form.config_combo, form.notes_edit, form.reset_button):
        assert widget.toolTip()


# -- AB3: a new test opens with Standard ----------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_a_new_test_opens_with_standard_and_the_defaults(qapp, task_id):
    page, config = _page(task_id)
    assert page.collect_values() == settings_snapshot(task_id, config)
    assert page._form.config_combo.currentText() == "Standard"
    assert page.loaded_config_name() == "Standard"
    assert page.collect_values()["live"]["dwell.smoothing.alpha"] == 0.22  # the YAML, not 0.35
    assert page._form.modified_label.text() == ""
    assert not page.is_dirty() and not page.is_modified()
    assert page.save_problem() is None and page.save_button.isEnabled()
    assert page.standard_values() == settings_snapshot(task_id, config)


def test_the_header_names_the_test_and_the_subject(qapp):
    page, _ = _page("click_grid")
    assert page.title_label.text() == "Grid Click 1 Configuration"
    assert page.subtitle_label.text() == "Grid Click, subject TESTING"


# -- AB4: the values are what a run and the dialog use -----------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_collect_values_equals_the_dialogs_overrides_and_the_snapshots_live(qapp, task_id):
    page, config = _page(task_id)
    values = page.collect_values()
    assert values["structural"] == TaskSettingsDialog(task_id, config).overrides()
    assert values["live"] == settings_snapshot(task_id, config)["live"]
    assert set(values) == {"live", "structural"}
    assert ("motion.speed_frac_per_s" in values["live"]) == (task_id == "follow_moving")


def test_edits_show_up_in_collect_values_with_the_right_types(qapp):
    page, _ = _page("click_grid")
    c = page._form.controls
    c["target.size"].setValue("large")
    c["grid.rows"].setValue(4)
    c["grid.gap"].setValue("wide")
    c["dwell.smoothing.alpha"].setValue(0.5)
    c["dwell.visual_cursor"].setChecked(False)
    c["feedback.miss_sound"].setChecked(False)
    values = page.collect_values()
    assert values["structural"]["target"] == {"size": "large"}
    assert values["structural"]["grid"] == {"rows": 4, "cols": 3, "gap": "wide"}
    assert values["structural"]["feedback"] == {
        "hit_sound": True, "miss_sound": False, "target_glow": True,
    }
    assert values["live"]["dwell.smoothing.alpha"] == 0.5
    assert values["live"]["dwell.visual_cursor"] is False
    assert isinstance(values["structural"]["grid"]["rows"], int)


# -- AB5: the one dependent control ------------------------------------------------------------------


def test_unticking_smoothing_greys_the_alpha_and_reticking_restores_it(qapp):
    page, _ = _page("click_static")
    enabled = page._form.controls["dwell.smoothing.enabled"]
    alpha = page._form.controls["dwell.smoothing.alpha"]
    (_master, widgets), = page._form.dependents
    assert alpha in widgets and len(widgets) == 2  # the control and its label
    enabled.setChecked(False)
    assert all(not w.isEnabled() for w in widgets)
    assert not alpha.isHidden()  # greyed in place, never hidden
    enabled.setChecked(True)
    assert all(w.isEnabled() for w in widgets)


def test_a_loaded_configuration_with_smoothing_off_opens_greyed(qapp):
    page, _ = _page("click_static", live={"dwell.smoothing.enabled": False})
    assert not page._form.controls["dwell.smoothing.alpha"].isEnabled()


# -- AB6: the hints are the dialog's --------------------------------------------------------------------


def _hint_text(widget_or_page):
    hint = widget_or_page.fit_hint
    return None if hint.isHidden() else widget_or_page.fit_hint_label.text()


@pytest.mark.parametrize("rows, cols, size, gap", [
    (3, 3, "medium", "standard"), (6, 6, "medium", "standard"), (4, 4, "large", "wide"),
    (6, 6, "large", "extra_wide"), (3, 3, "small", "wide"),
])
def test_the_grid_hint_is_what_the_dialog_shows_and_hides_when_it_fits(
    qapp, lab_screen, rows, cols, size, gap
):
    page, config = _page("click_grid")
    page._form.controls["grid.rows"].setValue(rows)
    page._form.controls["grid.cols"].setValue(cols)
    page._form.controls["target.size"].setValue(size)
    page._form.controls["grid.gap"].setValue(gap)
    dialog = TaskSettingsDialog("click_grid", config)
    dialog._controls["grid.rows"].setValue(rows)
    dialog._controls["grid.cols"].setValue(cols)
    dialog._controls["target.size"].setCurrentIndex(dialog._controls["target.size"].findData(size))
    dialog._controls["grid.gap"].setCurrentIndex(dialog._controls["grid.gap"].findData(gap))
    assert _hint_text(page) == _hint_text(dialog)
    fits = (rows, cols, size, gap) in {(3, 3, "medium", "standard"), (3, 3, "small", "wide")}
    assert (_hint_text(page) is None) == fits


def test_the_grid_hint_is_shown_for_a_crowded_grid_and_hidden_again(qapp):
    page, _ = _page("click_grid")
    assert page.fit_hint.isHidden()
    page._form.controls["grid.rows"].setValue(6)
    page._form.controls["grid.cols"].setValue(6)
    assert not page.fit_hint.isHidden()
    assert page.fit_hint_label.text().startswith("Will be shrunk to ≈ ")
    page._form.controls["grid.rows"].setValue(3)
    page._form.controls["grid.cols"].setValue(3)
    assert page.fit_hint.isHidden()


@pytest.mark.parametrize("n_icons, size", [(4, "medium"), (8, "large"), (8, "small"), (5, "large")])
def test_the_scanning_hint_is_what_the_dialog_shows(qapp, lab_screen, n_icons, size):
    page, config = _page("scanning")
    page._form.controls["layout.n_icons"].setValue(n_icons)
    page._form.controls["layout.size"].setValue(size)
    dialog = TaskSettingsDialog("scanning", config)
    dialog._controls["layout.n_icons"].setValue(n_icons)
    dialog._controls["layout.size"].setCurrentIndex(dialog._controls["layout.size"].findData(size))
    assert _hint_text(page) == _hint_text(dialog)


def test_only_the_grid_and_scanning_pages_have_a_hint(qapp):
    assert _page("click_static")[0].fit_hint is None
    assert _page("follow_moving")[0].fit_hint is None
    assert _page("click_grid")[0].fit_hint is not None
    assert _page("scanning")[0].fit_hint is not None


# -- FX4 follow-up: the amber hint shows the panel's px too -----------------------------------------------------


def _figures(text):
    return [int(n) for n in re.findall(r"≈ (\d+) px", text)]


def _set_grid(page, rows, cols, size, gap):
    for key, value in (("grid.rows", rows), ("grid.cols", cols), ("target.size", size), ("grid.gap", gap)):
        page._form.controls[key].setValue(value)


@pytest.mark.parametrize("rows, cols, size, gap", [
    (6, 6, "medium", "standard"), (6, 6, "large", "extra_wide"), (4, 4, "large", "wide"),
])
def test_the_grid_hint_shows_physical_px_at_a_scaled_display(qapp, rows, cols, size, gap):
    config = load_task_config("click_grid")
    scaled = TaskConfigPage("click_grid", config, screen=SCALED_SCREEN)
    plain = TaskConfigPage("click_grid", config, screen=LAB_SCREEN)
    for page in (scaled, plain):
        _set_grid(page, rows, cols, size, gap)
    # The same monitor and layout give the same figures, in the panel's px, at 100 % and 150 %.
    assert _hint_text(plain) is not None and _hint_text(scaled) is not None
    assert len(_figures(_hint_text(scaled))) == len(_figures(_hint_text(plain)))
    for shown, expected in zip(_figures(_hint_text(scaled)), _figures(_hint_text(plain)), strict=True):
        assert abs(shown - expected) <= 1
    # The page asks the engine for logical px worked out on the logical canvas, with the ratio.
    mm_per_logical_px = MM_PER_PX * 1.5
    margin = float(config["task"]["grid"].get("margin_frac", 0.12))
    args = (rows, cols, CANVAS[0] / 1.5, CANVAS[1] / 1.5,
            radius_px_for(size, mm_per_logical_px, DISTANCE), margin,
            gap_px_for(gap, mm_per_logical_px, DISTANCE))
    assert _hint_text(scaled) == grid_fit_hint(*args, 1.5)
    assert _hint_text(scaled) != grid_fit_hint(*args)  # not the logical figures (the live bug)


@pytest.mark.parametrize("n_icons, size", [(8, "large"), (5, "large")])
def test_the_scanning_hint_shows_physical_px_at_a_scaled_display(qapp, n_icons, size):
    config = load_task_config("scanning")
    scaled = TaskConfigPage("scanning", config, screen=SCALED_SCREEN)
    scaled._form.controls["layout.n_icons"].setValue(n_icons)
    scaled._form.controls["layout.size"].setValue(size)
    layout = config["task"].get("layout", {})
    slots = scanning_layout_slots(
        n_icons, str(layout.get("arrangement", "grid")), float(layout.get("margin_frac", 0.14))
    )
    args = (n_icons, slots, CANVAS[0] / 1.5, CANVAS[1] / 1.5,
            radius_px_for(size, MM_PER_PX * 1.5, DISTANCE))
    assert _hint_text(scaled) is not None
    assert _hint_text(scaled) == icon_fit_hint(*args, 1.5)
    assert _hint_text(scaled) != icon_fit_hint(*args)


def test_a_hint_that_fits_stays_hidden_at_a_scaled_display(qapp):
    scaled = TaskConfigPage("click_grid", load_task_config("click_grid"), screen=SCALED_SCREEN)
    assert scaled.fit_hint.isHidden()  # 3 x 3 medium fits: the ratio changes figures, not the verdict
    _set_grid(scaled, 6, 6, "medium", "standard")
    assert not scaled.fit_hint.isHidden()
    _set_grid(scaled, 3, 3, "medium", "standard")
    assert scaled.fit_hint.isHidden()


# -- AB7: saved names ---------------------------------------------------------------------------------------


def test_the_name_list_is_standard_then_the_saved_names(qapp):
    page, _ = _page("click_grid")
    page.set_context(named_configs=[_named("Large targets"), _named("Saved 10/01 09:00")])
    combo = page._form.config_combo
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Standard", "Large targets", "Saved 10/01 09:00"]
    assert combo.currentText() == "Standard"


def test_picking_a_saved_name_loads_all_its_values_and_defaults_the_missing_ones(qapp, answers):
    page, config = _page("click_grid")
    saved = _named(
        "Large targets",
        live={"dwell.threshold_ms": 1200, "dwell.smoothing.enabled": False, "bogus.key": 1},
        structural={"target": {"size": "large"}, "grid": {"rows": 4}},  # no cols, no gap
    )
    page.set_context(named_configs=[saved])
    _select(page, "Large targets")
    expected = complete_settings("click_grid", config, saved.live, saved.structural)
    assert page.collect_values() == expected
    values = page.collect_values()
    assert values["structural"]["grid"] == {"rows": 4, "cols": 3, "gap": "standard"}  # defaults
    assert values["live"]["dwell.threshold_ms"] == 1200
    assert page._form.config_combo.currentText() == "Large targets"
    assert page.loaded_config_name() == "Large targets"
    assert page._form.modified_label.text() == ""
    assert answers.asked == []  # nothing to replace: not asked
    _select(page, "Standard")
    assert page.collect_values() == settings_snapshot("click_grid", config)


def test_picking_a_name_never_touches_the_test_name_or_notes(qapp, answers):
    page, _ = _page("click_grid")
    page._form.notes_edit.setPlainText("tired")
    page.set_context(named_configs=[_named("Large targets", structural={"target": {"size": "large"}})])
    _select(page, "Large targets")
    assert page._form.test_name_edit.text() == "Grid Click 1"
    assert page._form.notes_edit.toPlainText() == "tired"


def test_a_dirty_form_asks_before_a_saved_name_replaces_it(qapp, answers):
    page, _ = _page("click_grid")
    page.set_context(named_configs=[_named("Large targets", structural={"target": {"size": "large"}})])
    page._form.controls["dwell.threshold_ms"].setValue(1500)
    assert page.is_modified()
    answers.reply = False  # Keep my edits
    _select(page, "Large targets")
    assert answers.asked == [("Load configuration", "Replace your edits with configuration 'Large targets'?")]
    assert page.collect_values()["live"]["dwell.threshold_ms"] == 1500  # kept
    assert page.collect_values()["structural"]["target"] == {"size": "medium"}
    assert page._form.config_combo.currentText() == "Standard"  # the box is back as it was
    assert page.loaded_config_name() == "Standard"
    answers.reply = True  # Replace
    _select(page, "Large targets")
    assert page.collect_values()["live"]["dwell.threshold_ms"] == 800
    assert page.collect_values()["structural"]["target"] == {"size": "large"}
    assert page._form.config_combo.currentText() == "Large targets"
    assert not page.is_modified()


def test_keeping_the_edits_puts_back_the_name_that_was_typed(qapp, answers):
    page, _ = _page("click_grid")
    page.set_context(named_configs=[_named("Large targets")])
    page._form.config_combo.setEditText("My own name")  # typing: a new name, no load
    page._form.controls["trials"].setValue(10)
    answers.reply = False
    _select(page, "Large targets")
    assert page._form.config_combo.currentText() == "My own name"
    assert page.collect_values()["structural"]["trials"] == 10


def test_enter_after_typing_an_existing_name_has_nothing_to_undo(qapp, answers):
    page, _ = _page("click_grid")
    page.set_context(named_configs=[_named("Large targets")])
    combo = page._form.config_combo
    combo.setEditText("Large targets")
    qapp.processEvents()  # the typing is over: the Enter that follows is its own event
    page._form.controls["trials"].setValue(10)
    answers.reply = False
    combo.activated.emit(combo.findText("Large targets"))
    assert len(answers.asked) == 1
    assert combo.currentText() == "Large targets"
    assert page.collect_values()["structural"]["trials"] == 10


def test_typing_a_new_name_loads_nothing_and_asks_nothing(qapp, answers):
    page, _ = _page("click_grid")
    page.set_context(named_configs=[_named("Large targets", structural={"trials": 40})])
    page._form.config_combo.setEditText("Large")
    page._form.config_combo.setEditText("Large t")
    assert page.collect_values()["structural"]["trials"] == 18
    assert answers.asked == []
    assert page.loaded_config_name() == "Standard"


def test_loading_a_tests_own_snapshot_fills_the_form_and_is_clean(qapp):
    page, config = _page(
        "follow_moving",
        notes="n1",
        config_name="Slow circle",
        live={"motion.speed_frac_per_s": 0.1},
        structural={"motion": {"path": "vertical"}},
    )
    assert page.collect_values()["live"]["motion.speed_frac_per_s"] == 0.1
    assert page.collect_values()["structural"]["motion"]["path"] == "vertical"
    assert page._form.config_combo.currentText() == "Slow circle"
    assert page._form.notes_edit.toPlainText() == "n1"
    assert not page.is_dirty() and not page.is_modified()
    assert page.standard_values() == settings_snapshot("follow_moving", config)


def test_a_stored_name_of_standard_in_any_case_loads_as_standard(qapp):
    page, config = _page("click_grid", config_name=" standard ")
    assert page.loaded_config_name() == "Standard"
    assert page._form.config_combo.currentText() == "Standard"
    assert page.collect_values() == settings_snapshot("click_grid", config)


def test_values_a_hand_edited_file_cannot_give_fall_back_to_the_defaults(qapp):
    page, config = _page(
        "click_grid",
        live={"dwell.threshold_ms": "fast", "dwell.visual_cursor": 1, "dwell.refractory_ms": True},
        structural={"trials": "abc", "target": {"size": "huge"}, "feedback": {"hit_sound": "no"}},
    )
    assert page.collect_values() == settings_snapshot("click_grid", config)


# -- the "Changed from" line, dirty tracking -------------------------------------------------------------------------


def test_the_changed_from_line_names_the_loaded_configuration(qapp):
    page, _ = _page("click_grid")
    modified = page._form.modified_label
    assert modified.text() == ""  # always there (C4), empty while nothing changed
    page._form.controls["trials"].setValue(7)
    assert modified.text() == "Changed from Standard"
    page._form.controls["trials"].setValue(18)
    assert modified.text() == ""
    page.load_values(config_name="Large targets", structural={"trials": 9})
    page._form.controls["trials"].setValue(10)
    assert modified.text() == "Changed from Large targets"


def test_dirty_follows_every_kind_of_edit_and_clears_on_load_or_mark_clean(qapp):
    page, _ = _page("click_grid")
    assert not page.is_dirty()
    page._form.test_name_edit.setText("Renamed")
    assert page.is_dirty()
    page._form.test_name_edit.setText("Grid Click 1")
    assert not page.is_dirty()
    page._form.notes_edit.setPlainText("x")
    assert page.is_dirty()
    page.mark_clean()
    assert not page.is_dirty()
    page._form.controls["grid.gap"].setValue("wide")
    assert page.is_dirty()
    page._form.controls["grid.gap"].setValue("standard")
    assert not page.is_dirty()
    page._form.config_combo.setEditText("Typed name")
    assert page.is_dirty()
    page.load_values(test_name="Grid Click 1")
    assert not page.is_dirty()


def test_showing_the_page_does_not_reload_the_form(qapp):
    page, _ = _page("click_grid")
    page._form.controls["trials"].setValue(25)
    page.show()
    qapp.processEvents()
    page.hide()
    assert page.collect_values()["structural"]["trials"] == 25
    assert page.is_dirty()


# -- AB11: validation -------------------------------------------------------------------------------------------


def _blocked(page):
    return not page.save_button.isEnabled(), page.footer_message.text()


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, "other TEST", "Other Test"])
def test_a_bad_test_name_disables_save_and_says_why(qapp, name):
    page, _ = _page("click_grid")
    page._form.test_name_edit.setText(name)
    expected = validate_test_name(name, ["Other test"], exclude="Grid Click 1")
    assert expected
    assert _blocked(page) == (True, expected)


def test_the_tests_own_name_and_a_new_one_are_fine(qapp):
    page, _ = _page("click_grid")
    page._form.test_name_edit.setText("GRID CLICK 1")  # its own name, other case
    assert page.save_button.isEnabled() and page.footer_message.text() == ""
    page._form.test_name_edit.setText("A new name")
    assert page.save_button.isEnabled()
    page._form.test_name_edit.setText("x" * 60)
    assert page.save_button.isEnabled()


def test_a_bad_configuration_name_disables_save_and_says_why(qapp):
    page, _ = _page("click_grid")
    combo = page._form.config_combo
    combo.setEditText("")
    assert _blocked(page) == (True, "Enter a configuration name.")
    combo.setEditText("y" * 41)
    blocked, message = _blocked(page)
    assert blocked and "at most 40 characters" in message
    combo.setEditText("y" * 40)
    assert page.save_button.isEnabled() and page.footer_message.text() == ""


def test_standard_with_changed_values_leaves_save_on_for_the_forced_rename(qapp):
    """AB8: Save & Continue on Standard + changed values opens the forced-rename dialog,
    so the page must let it through (the dashboard shows the dialog)."""
    page, _ = _page("click_grid")
    page._form.controls["trials"].setValue(7)
    assert page.is_modified() and page._form.config_combo.currentText() == "Standard"
    assert page.save_button.isEnabled()
    page._form.config_combo.setEditText("standard")
    assert page.save_button.isEnabled()


def test_the_first_problem_is_the_one_shown_and_a_fixed_form_clears_it(qapp):
    page, _ = _page("click_grid")
    page._form.test_name_edit.setText("")
    page._form.config_combo.setEditText("")
    assert page.footer_message.text() == "Enter a test name."
    page._form.test_name_edit.setText("ok")
    assert page.footer_message.text() == "Enter a configuration name."
    page._form.config_combo.setEditText("Standard")
    assert page.footer_message.text() == "" and page.save_button.isEnabled()


# -- signals, footer, AB12 ---------------------------------------------------------------------------------------


def test_save_emits_the_entry_and_a_disabled_save_emits_nothing(qapp):
    page, _ = _page("click_grid")
    saved = []
    page.saveRequested.connect(saved.append)
    page._form.notes_edit.setPlainText("note")
    page._form.controls["trials"].setValue(7)
    page._form.config_combo.setEditText("  Short  ")
    page.save_button.click()
    assert len(saved) == 1
    entry = saved[0]
    assert (entry["test_name"], entry["config_name"], entry["notes"]) == ("Grid Click 1", "Short", "note")
    assert entry["structural"]["trials"] == 7
    assert {"live", "structural"} <= set(entry)
    page._form.test_name_edit.setText("")
    assert not page.save_button.isEnabled()
    page.save_button.click()
    assert len(saved) == 1


def test_preview_hands_over_the_unsaved_values_and_is_always_enabled(qapp):
    page, _ = _page("click_grid")
    previews = []
    page.previewRequested.connect(previews.append)
    page._form.controls["target.size"].setValue("large")  # not saved
    page._form.test_name_edit.setText("")  # invalid: Save is off, Preview is not
    assert not page.save_button.isEnabled() and page.preview_button.isEnabled()
    page.preview_button.click()
    assert previews == [page.collect_values()]
    assert previews[0]["structural"]["target"] == {"size": "large"}
    assert set(previews[0]) == {"live", "structural"}  # no names, no notes


def test_cancel_without_edits_returns_at_once_and_writes_nothing(qapp, answers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page, _ = _page("click_grid")
    cancelled = []
    page.cancelRequested.connect(lambda: cancelled.append(True))
    page.cancel_button.click()
    assert cancelled == [True] and answers.asked == []
    assert list(tmp_path.iterdir()) == []


def test_cancel_with_edits_asks_first_and_writes_nothing(qapp, answers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page, _ = _page("click_grid")
    cancelled = []
    page.cancelRequested.connect(lambda: cancelled.append(True))
    page._form.controls["trials"].setValue(7)
    answers.reply = False  # Keep editing
    page.cancel_button.click()
    assert cancelled == [] and answers.asked == [("Discard changes", "Discard your changes?")]
    assert page.collect_values()["structural"]["trials"] == 7
    answers.reply = True  # Discard
    page.cancel_button.click()
    assert cancelled == [True]
    assert list(tmp_path.iterdir()) == []


def test_reset_restores_standard_and_the_defaults_but_keeps_name_and_notes(qapp, answers):
    page, config = _page("click_grid", notes="kept", config_name="Large targets",
                         structural={"target": {"size": "large"}})
    page._form.test_name_edit.setText("My test")
    page._form.controls["trials"].setValue(7)
    page._form.controls["dwell.smoothing.enabled"].setChecked(False)
    page._form.reset_button.click()
    assert page.collect_values() == settings_snapshot("click_grid", config)
    assert page._form.config_combo.currentText() == "Standard"
    assert page.loaded_config_name() == "Standard"
    assert page._form.test_name_edit.text() == "My test"
    assert page._form.notes_edit.toPlainText() == "kept"
    assert page._form.modified_label.text() == ""
    assert page._form.controls["dwell.smoothing.alpha"].isEnabled()  # dependents follow
    assert page.is_dirty()  # unsaved until Save & Continue
    assert answers.asked == []  # reset itself never asks


def test_a_note_shows_until_the_next_edit_and_a_problem_outranks_it(qapp):
    page, _ = _page("click_grid")
    page.show_note("Preview finished. Nothing was recorded.")
    assert page.footer_message.text() == "Preview finished. Nothing was recorded."
    page._form.controls["trials"].setValue(9)
    assert page.footer_message.text() == ""
    page.show_note("again")
    page._form.test_name_edit.setText("")
    assert page.footer_message.text() == "Enter a test name."


# -- the real question box -----------------------------------------------------------------------------------------


def _click_later(button_text, seen):
    """Press the button labelled ``button_text`` of the next modal question from inside its
    event loop, noting what it was in ``seen``."""

    def press():
        box = QApplication.activeModalWidget()
        if box is None:  # not open yet: look again shortly
            QTimer.singleShot(5, press)
            return
        seen.append(box)
        next(b for b in box.buttons.values() if b.text() == button_text).click()

    QTimer.singleShot(0, press)


def test_cancel_with_edits_really_asks_in_a_themed_box(qapp):
    page, _ = _page("click_grid")
    cancelled, seen = [], []
    page.cancelRequested.connect(lambda: cancelled.append(True))
    page._form.controls["trials"].setValue(7)
    _click_later("Keep editing", seen)
    page.cancel_button.click()
    assert cancelled == []
    _click_later("Discard", seen)
    page.cancel_button.click()
    assert cancelled == [True]
    # FX1: the dashboard's own themed dialog (light palette and sheet), not a QMessageBox,
    # whose body and buttons stayed dark in the live check.
    assert [type(box).__name__ for box in seen] == ["_ChoiceDialog"] * 2
    assert not any(isinstance(box, QMessageBox) for box in seen)
    assert seen[0].windowTitle() == "Discard changes"
    assert seen[0].text_label.text() == "Discard your changes?"
