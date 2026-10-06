"""The HUD-less run screen (SPEC-compass-task-flow.md 4C.5, U5; AC7): ``RunBar``, the new
``TaskRunView`` and ``TaskCanvas.set_paused``."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from src.ui.canvas import TaskCanvas
from src.ui.main_window import MainWindow, TaskRunView
from src.ui.run_bar import BAR_HEIGHT, RunBar

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


def test_the_bar_holds_pause_skip_quit_and_one_status_label(qapp):
    bar = RunBar()
    assert [b.text() for b in bar.findChildren(QPushButton)] == [
        "Pause (Alt-P)",
        "Skip trial",
        "Quit (Alt-Q)",
    ]
    assert bar.height() == BAR_HEIGHT == 44
    assert bar.status_text() == ""


def test_the_buttons_stay_centred_whatever_the_status_says(qapp):
    bar = RunBar()
    bar.resize(1400, BAR_HEIGHT)
    bar.show()
    centres = []
    for line in ("Trial 1/3", "PRACTICE (not recorded) · Trial 12/18 · no gaze for 12 s"):
        bar.set_status(line)
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


def test_status_text_is_plain_and_the_tracking_part_is_coloured(qapp):
    bar = RunBar()
    bar.set_status("Trial 4/18 · tracking OK", "tracking OK", "ok")
    assert bar.status_text() == "Trial 4/18 · tracking OK"
    html = bar.status_label.text()
    assert "Trial 4/18 · " in html and "tracking OK" in html and "color:#1e7a53" in html
    bar.set_status("Trial 4/18 · no gaze for 3 s", "no gaze for 3 s", "warn")
    assert "color:#8a5a00" in bar.status_label.text()
    bar.set_status("Trial 4/18 · tracker DISCONNECTED", "tracker DISCONNECTED", "error")
    assert "color:#c0392b" in bar.status_label.text()


def test_a_status_with_no_tracking_part_is_plain_and_escaped(qapp):
    bar = RunBar()
    bar.set_status("Paused · Trial 4/18")
    assert bar.status_label.text() == "Paused · Trial 4/18" and "<span" not in bar.status_label.text()
    bar.set_status("a <b> & c")
    assert "&lt;b&gt;" in bar.status_label.text()  # never read as markup


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
