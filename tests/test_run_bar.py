"""The HUD-less run screen (SPEC-compass-task-flow.md 4C.5, U5; AC7; SPEC-design-system-phase1.md H9):
``RunBar``, the new ``TaskRunView`` and ``TaskCanvas.set_paused``."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from src.engine.tracking_status import LEVEL_ERROR, LEVEL_OK, LEVEL_WARN, RunStatus, run_status
from src.ui.canvas import TaskCanvas
from src.ui.design_tokens import (
    DANGER_TEXT,
    SUCCESS_TEXT,
    WARNING_CHIP,
    WARNING_SUBTLE,
    WARNING_TEXT,
)
from src.ui.glyphs import GLYPH_CIRCLE, GLYPH_SQUARE, GLYPH_TRIANGLE
from src.ui.main_window import MainWindow, TaskRunView
from src.ui.run_bar import BAR_HEIGHT, RunBar
from src.ui.status_badge import StatusBadge

THEME = {"background": "#e8f5e9", "cursor_color": "#1b5e20", "target_default": "#ff5252"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp):
    v = TaskRunView(theme=THEME)
    v.resize(1280, 800)
    v.show()
    qapp.processEvents()
    yield v
    v.close()


# -- RunBar ------------------------------------------------------------------


def test_the_bar_holds_pause_skip_quit_and_its_status_labels(qapp):
    bar = RunBar()
    assert [b.text() for b in bar.findChildren(QPushButton)] == [
        "Pause (Alt-P)",
        "Skip trial",
        "Quit (Alt-Q)",
    ]
    assert bar.height() == BAR_HEIGHT == 48
    assert bar.status_text() == ""
    labels = (bar.chip_label, bar.paused_label, bar.trial_label, bar.pointer_label, bar.tracking_label)
    assert all(label.isHidden() for label in labels)  # nothing to say yet


def test_the_buttons_stay_centred_whatever_the_status_says(qapp):
    bar = RunBar()
    bar.resize(1400, BAR_HEIGHT)
    bar.show()
    centres = []
    for status in (
        run_status(1, 3, ""),
        run_status(12, 18, "No gaze for 12 s", LEVEL_WARN, practice=True, mouse=True),
    ):
        bar.set_status(status)
        qapp.processEvents()
        left = bar.pause_button.geometry().left()
        right = bar.quit_button.geometry().right()
        centres.append((left + right) / 2)
    assert centres[0] == centres[1]  # the text does not move them ...
    assert abs(centres[0] - 700) <= 8, centres  # ... and they are (near enough) in the middle
    bar.close()


def test_pause_toggles_its_label_and_signals_the_new_state(qapp):
    bar = RunBar()
    seen: list[bool] = []
    bar.pause_toggled.connect(seen.append)
    bar.pause_button.click()
    assert seen == [True] and bar.is_paused and bar.pause_button.text() == "Resume (Alt-P)"
    bar.pause_button.click()
    assert seen == [True, False] and not bar.is_paused and bar.pause_button.text() == "Pause (Alt-P)"


def test_set_paused_from_outside_changes_the_label_without_a_signal(qapp):
    bar = RunBar()
    seen: list[bool] = []
    bar.pause_toggled.connect(seen.append)
    bar.set_paused(True)
    assert bar.pause_button.text() == "Resume (Alt-P)" and seen == []


def test_skip_and_quit_emit_and_skip_can_be_disabled(qapp):
    bar = RunBar()
    skipped, quit_ = [], []
    bar.skip_requested.connect(lambda: skipped.append(1))
    bar.quit_requested.connect(lambda: quit_.append(1))
    bar.skip_button.click()
    bar.quit_button.click()
    assert (skipped, quit_) == ([1], [1])
    bar.set_skip_enabled(False)
    bar.skip_button.click()  # disabled: nothing
    assert skipped == [1] and not bar.skip_button.isEnabled()


def test_the_buttons_never_take_the_keyboard_focus(qapp):
    bar = RunBar()
    assert all(
        b.focusPolicy() == Qt.FocusPolicy.NoFocus for b in bar.findChildren(QPushButton)
    )


def test_each_fact_of_the_status_is_its_own_label_and_the_tracking_state_has_its_level(qapp):
    bar = RunBar()
    bar.set_status(run_status(4, 18, "Tracking OK", LEVEL_OK, practice=True, mouse=True))
    assert bar.status_text() == "PRACTICE, Trial 4 of 18, Mouse pointer, Tracking OK"
    shown = {
        label.objectName(): label.text()
        for label in (bar.chip_label, bar.paused_label, bar.trial_label, bar.pointer_label, bar.tracking_label)
        if not label.isHidden()
    }
    assert shown == {
        "runBarChip": "PRACTICE",
        "runBarTrial": "Trial 4 of 18",
        "runBarPointer": "Mouse pointer",
        "runBarTracking": "Tracking OK",
    }
    assert bar.tracking_label.property("level") == LEVEL_OK
    bar.set_status(run_status(4, 18, "No gaze for 3 s", LEVEL_WARN))
    assert bar.tracking_label.property("level") == LEVEL_WARN and bar.chip_label.isHidden()
    bar.set_status(run_status(4, 18, "Tracker disconnected", LEVEL_ERROR))
    assert bar.tracking_label.property("level") == LEVEL_ERROR
    assert bar.tracking_label.text() == "Tracker disconnected"


def test_the_tracking_state_is_a_status_badge_with_a_glyph_and_the_word(qapp):
    """SPEC-design-system-phase2.md H8, Q2: glyph + word in success / warning / danger text
    colours (7.0 to 7.2:1 on both bar fills), under the name the label had."""
    bar = RunBar()
    badge = bar.tracking_label
    assert isinstance(badge, StatusBadge) and badge.objectName() == "runBarTracking"
    expected = (
        (LEVEL_OK, "Tracking OK", "tracking_ok", SUCCESS_TEXT, GLYPH_CIRCLE),
        (LEVEL_WARN, "No gaze for 3 s", "no_gaze", WARNING_TEXT, GLYPH_TRIANGLE),
        (LEVEL_ERROR, "Tracker disconnected", "tracker_disconnected", DANGER_TEXT, GLYPH_SQUARE),
    )
    for level, word, kind, colour, glyph in expected:
        bar.set_status(run_status(4, 18, word, level))
        assert badge.kind() == kind and badge.text() == badge.accessibleName() == word
        assert (badge.look().text, badge.look().glyph) == (colour, glyph)
        assert not badge.isHidden() and badge.property("level") == level


def test_the_tracking_badge_is_hidden_while_there_is_nothing_to_report(qapp):
    bar = RunBar()
    bar.set_status(run_status(1, 3, "", practice=True, mouse=True))  # a Mouse test, no tracker
    assert bar.tracking_label.isHidden()
    bar.set_status(run_status(1, 3, "Tracking OK", paused=True))  # paused drops it
    assert bar.tracking_label.isHidden()


def test_the_chip_is_a_fixed_24_px_pill_centred_in_the_bar(qapp):
    """SPEC-design-system-phase2.md H13 (3): it used to stretch to the bar's height."""
    bar = RunBar("practice")
    bar.resize(1400, BAR_HEIGHT)
    bar.show()
    for status in (
        run_status(2, 3, "Tracking OK", practice=True),
        run_status(2, 3, "", preview=True),
        run_status(2, 3, "No gaze for 3 s", LEVEL_WARN, practice=True, mouse=True),
    ):
        bar.set_status(status)
        qapp.processEvents()
        chip = bar.chip_label
        assert chip.minimumHeight() == chip.maximumHeight() == 24
        assert chip.height() == 24
        top = chip.mapTo(bar, chip.rect().topLeft()).y()
        assert top + 12 == BAR_HEIGHT // 2  # the chip's middle is the bar's middle
        badge = bar.tracking_label
        if not badge.isHidden():
            assert badge.height() == 24
            assert badge.mapTo(bar, badge.rect().topLeft()).y() + 12 == BAR_HEIGHT // 2
    bar.close()


def test_the_chip_is_a_filled_warning_chip_and_the_practice_bar_is_warning_subtle(qapp):
    sheet = RunBar().styleSheet()
    assert f"background: {WARNING_CHIP}" in sheet and f'[practice="true"] {{ background: {WARNING_SUBTLE}' in sheet


def test_a_pause_shows_the_marker_and_drops_the_pointer_and_the_tracking_state(qapp):
    bar = RunBar("preview")
    bar.set_status(run_status(2, 3, "Tracking OK", paused=True, preview=True))
    assert bar.status_text() == "PREVIEW, Paused"
    assert not bar.paused_label.isHidden() and bar.trial_label.isHidden() and bar.tracking_label.isHidden()
    bar.set_status(run_status(2, 3, "Tracking OK", paused=True))
    assert bar.status_text() == "Paused, Trial 2 of 3" and bar.chip_label.isHidden()


def test_a_status_is_plain_text_never_markup(qapp):
    bar = RunBar()
    bar.set_status(RunStatus(trial="a <b> & c"))
    assert bar.trial_label.text() == "a <b> & c" and bar.trial_label.textFormat() == Qt.TextFormat.PlainText


def test_the_run_bar_buttons_are_36_px_high(qapp):
    bar = RunBar()
    bar.resize(1400, BAR_HEIGHT)
    bar.show()
    qapp.processEvents()
    assert {b.height() for b in bar.findChildren(QPushButton)} == {36}
    bar.close()


def test_practice_and_preview_turn_the_bar_amber_and_a_recorded_run_grey(qapp):
    bar = RunBar("practice")
    assert bar.property("practice") is True
    bar.set_run_mode("record")
    assert bar.property("practice") is False
    bar.set_run_mode("preview")
    assert bar.property("practice") is True
    with pytest.raises(ValueError):
        bar.set_run_mode("recorded")


# -- TaskRunView (AC7) ---------------------------------------------------------


def test_the_view_is_a_canvas_over_a_bar_and_has_no_operator_panel(view):
    assert not hasattr(view, "operator_panel") and not hasattr(view, "hud_hidden")
    assert isinstance(view.canvas, TaskCanvas) and isinstance(view.run_bar, RunBar)
    names = {type(w).__name__ for w in view.findChildren(object)}
    assert "OperatorPanel" not in names
    assert view.canvas.width() == view.width()  # the canvas fills the width (no side column)
    assert view.canvas.height() == view.height() - BAR_HEIGHT
    assert view.run_bar.y() == view.canvas.height()  # the bar sits right under it


def test_alt_p_and_alt_q_are_shortcuts_on_the_view(view):
    for shortcut, keys in ((view.pause_shortcut, "Alt+P"), (view.quit_shortcut, "Alt+Q")):
        assert shortcut.key().toString() == keys
        assert shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut
        assert shortcut.parent() is view


def test_the_shortcuts_press_the_bars_buttons(view):
    pauses, quits = [], []
    view.run_bar.pause_toggled.connect(pauses.append)
    view.run_bar.quit_requested.connect(lambda: quits.append(1))
    view.pause_shortcut.activated.emit()
    view.quit_shortcut.activated.emit()
    assert pauses == [True] and quits == [1]


def test_a_bar_click_gives_the_focus_back_to_the_canvas(view, qapp):
    view.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    for signal in (view.run_bar.skip_requested, view.run_bar.quit_requested):
        view.canvas.clearFocus()
        signal.emit()
        assert view.canvas.hasFocus()
    view.canvas.clearFocus()
    view.run_bar.pause_toggled.emit(True)
    assert view.canvas.hasFocus()


def test_the_main_window_wraps_the_same_view(qapp):
    window = MainWindow(theme=THEME, fullscreen=False, run_mode="preview")
    assert window.view.canvas is window.canvas
    assert window.view.run_bar.property("practice") is True
    window.close()


# -- TaskCanvas.set_paused -----------------------------------------------------


def _render(canvas: TaskCanvas):
    return canvas.grab().toImage()


def test_a_paused_canvas_draws_no_target_and_no_cursor(qapp):
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(400, 300)
    canvas.set_frame((0.5, 0.5), 60.0, (0.2, 0.2), True, 0.0)
    live = _render(canvas)
    assert live.pixelColor(200, 150) != QColor("#e8f5e9")  # the target is there
    canvas.set_paused(True)
    paused = _render(canvas)
    assert paused.pixelColor(10, 10) == QColor("#e8f5e9")
    assert paused.pixelColor(80, 60) == QColor("#e8f5e9")  # where the cursor was (0.2, 0.2)
    ink = {(x, y) for x in range(0, 400, 2) for y in range(0, 300, 2) if paused.pixelColor(x, y) != QColor("#e8f5e9")}
    assert ink, "the word Paused is drawn"
    xs = [x for x, _y in ink]
    assert 100 < min(xs) and max(xs) < 300  # centred, nothing at the edges


def test_leaving_the_pause_paints_the_scene_again(qapp):
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(400, 300)
    canvas.set_frame((0.5, 0.5), 60.0, (0.2, 0.2), True, 0.0)
    canvas.set_paused(True)
    canvas.set_paused(False)
    assert _render(canvas).pixelColor(200, 150) != QColor("#e8f5e9")


def test_pausing_drops_the_moving_trail(qapp):
    canvas = TaskCanvas(theme=THEME)
    canvas.scene = {"mode": "moving"}
    for i in range(5):
        canvas.set_frame((0.1 * i, 0.5), 40.0, (0.5, 0.5), True, 0.0)
    assert canvas._trail
    canvas.set_paused(True)
    assert canvas._trail == []
