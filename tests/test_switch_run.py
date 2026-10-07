"""SPEC-input-selection-and-follow.md 4.2, I5, I6, H2, H3 (acceptance A2, A3, A4) through
``AssessmentApp`` and ``TaskCanvas``: a left press on the canvas (or Space / Enter) is the
switch, judged against where the gaze is; presses between trials and while paused are ignored;
the OS cursor is parked on the canvas and hidden, and given back on a pause; the glow is drawn
while the pointer is on the target and the dwell ring is not. Offscreen Qt, a mouse for the
gaze, the OS cursor never moved."""

# The fixtures are imported from input_run_fixtures and then used by name.
# ruff: noqa: F811
from __future__ import annotations

import csv
import json
import time

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtTest import QTest

from src.ui.canvas import TaskCanvas
from tests.input_run_fixtures import (  # noqa: F401  (fixtures)
    events_of,
    kinds,
    look_at_target,
    look_away,
    make_app,
    parked,
    qapp,
    tick,
    tick_until,
)

SWITCH = {"pointer": "gaze", "selection": "switch"}
LEFT, RIGHT = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
OFF_CANVAS = QPoint(-5000, -5000)  # a global position no canvas is at


def click(app):
    QTest.mousePress(app.canvas, LEFT)
    QTest.mouseRelease(app.canvas, LEFT)


def key(app, which, *, repeat=False, release=False):
    kind = QEvent.Type.KeyRelease if release else QEvent.Type.KeyPress
    event = QKeyEvent(kind, which, Qt.KeyboardModifier.NoModifier, "", repeat)
    (app.canvas.keyReleaseEvent if release else app.canvas.keyPressEvent)(event)


def up(app):
    """Tick until a target is showing."""
    tick_until(app, lambda: app.task.phase.name == "WAIT_INPUT")


# -- the run is set up as a switch run ---------------------------------------------------


def test_a_switch_run_is_set_up_for_the_switch(make_app):
    app = make_app(choice=SWITCH)
    assert app.input_mode == "gaze_switch" and app.task.input_selection == "switch"
    assert app.canvas.switch_press_enabled is True
    assert app.canvas.show_progress_ring is False  # A4: no dwell ring with a switch
    assert app.canvas.show_glow is True
    meta = app.metadata
    assert (meta.input_mode, meta.input_pointer, meta.input_selection) == ("gaze_switch", "gaze", "switch")
    assert meta.gaze_recorded is True


def test_a_dwell_run_has_the_ring_no_glow_and_no_switch(make_app):
    app = make_app(choice={"pointer": "gaze", "selection": "dwell"})
    assert app.input_mode == "eye"
    assert app.canvas.switch_press_enabled is False
    assert app.canvas.show_progress_ring is True and app.canvas.show_glow is False


def test_the_glow_can_be_turned_off(make_app):
    app = make_app(choice=SWITCH, structural={"feedback": {"target_glow": False}})
    assert app.canvas.show_glow is False


def test_a_test_with_no_choice_runs_as_it_always_did(make_app):
    app = make_app()
    assert (app.input_mode, app.metadata.input_pointer, app.metadata.input_selection) == ("eye", "gaze", "dwell")
    assert app.canvas.switch_press_enabled is False


# -- A2: a left press selects ----------------------------------------------------------------


def test_a_left_press_with_the_gaze_on_the_target_selects(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    tick(app)
    assert app.task.trials == []  # looking is not selecting
    click(app)
    tick(app)
    row = app.task.trials[0]
    assert row.is_hit and (row.clicks, row.click_errors) == (1, 0)
    (press,) = kinds(app, "SWITCH_PRESS")
    assert press["on_target"] is True and press["trial"] == 0


def test_a_press_off_the_target_is_a_click_error_and_the_trial_goes_on(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_away(app)
    tick(app)
    click(app)
    tick(app)
    assert app.task.trials == [] and app.task.phase.name == "WAIT_INPUT"
    look_at_target(app)
    tick(app)
    click(app)
    tick(app)
    row = app.task.trials[0]
    assert row.is_hit and (row.clicks, row.click_errors, row.attempts) == (2, 1, 2)
    assert [p["on_target"] for p in kinds(app, "SWITCH_PRESS")] == [False, True]


def test_a_press_between_trials_is_ignored_and_logged(make_app):
    app = make_app(choice=SWITCH, live={"task.inter_trial_interval_ms": 3000})
    up(app)
    look_at_target(app)
    tick(app)
    click(app)
    tick(app)
    assert len(app.task.trials) == 1 and app.task.phase.name == "ITI"
    click(app)
    tick(app)
    assert len(kinds(app, "SWITCH_PRESS")) == 1  # nothing counted
    assert [e["phase"] for e in kinds(app, "SWITCH_IGNORED")] == ["iti"]
    assert app.task.trials[0].clicks == 1 and app.task.phase.name == "ITI"


def test_the_refractory_period_setting_debounces_the_switch(make_app):
    app = make_app(choice=SWITCH, live={"dwell.refractory_ms": 150})
    assert app.task.refractory_ns == 150 * 1_000_000
    up(app)
    look_away(app)
    tick(app)
    click(app)  # a Click error: counted
    tick(app)
    look_at_target(app)
    tick(app)
    click(app)  # the right look, but a few ms after the error: ignored
    tick(app)
    assert app.task.trials == [] and len(kinds(app, "SWITCH_PRESS")) == 1
    (ignored,) = kinds(app, "SWITCH_IGNORED")
    assert (ignored["phase"], ignored["reason"]) == ("target", "refractory")
    time.sleep(0.2)
    click(app)
    tick(app)
    row = app.task.trials[0]
    assert row.is_hit and (row.clicks, row.click_errors) == (2, 1)


def test_the_pointer_in_a_blink_uses_the_last_valid_one(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    tick(app)  # a valid pointer on the target
    app.pointing.pos = OFF_CANVAS  # the next sample is invalid: a blink
    click(app)
    tick(app)
    row = app.task.trials[0]
    assert row.is_hit and row.click_errors == 0
    (press,) = kinds(app, "SWITCH_PRESS")
    assert press["used_fallback"] is True and press["on_target"] is True


def test_a_press_with_no_gaze_at_all_is_a_click_error(make_app):
    app = make_app(choice=SWITCH)
    app.pointing.pos = OFF_CANVAS  # never on the canvas: there is no gaze at all
    up(app)
    tick(app)
    click(app)
    tick(app)
    assert app.task.trials == []
    (press,) = kinds(app, "SWITCH_PRESS")
    assert press["reason"] == "no_gaze" and press["on_target"] is False
    assert kinds(app, "MISS_CLICK")[0]["reason"] == "no_gaze"


# -- the other buttons, the run bar, and Space / Enter -------------------------------------------


def test_only_the_left_button_is_the_switch(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    QTest.mouseClick(app.canvas, RIGHT)
    QTest.mouseClick(app.canvas, Qt.MouseButton.MiddleButton)
    tick(app)
    assert app.task.trials == [] and kinds(app, "SWITCH_PRESS") == []


def test_a_press_on_the_run_bar_never_reaches_the_switch(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    QTest.mouseClick(app.view.run_bar, LEFT)  # the bar's own background
    tick(app)
    assert app.task.trials == [] and kinds(app, "SWITCH_PRESS") == []


def test_a_left_press_means_nothing_to_a_dwell_run(make_app):
    app = make_app(choice={"pointer": "gaze", "selection": "dwell"}, live={"dwell.threshold_ms": 60000})
    up(app)
    look_at_target(app)
    click(app)
    tick(app)
    assert app.task.trials == [] and kinds(app, "SWITCH_PRESS") == []


@pytest.mark.parametrize("which", [Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_space_and_enter_are_the_switch_too(make_app, which):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    key(app, which)
    tick(app)
    assert app.task.trials[0].is_hit and app.task.trials[0].clicks == 1


def test_a_held_key_is_one_press_and_its_repeat_is_not_another(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_away(app)
    key(app, Qt.Key.Key_Space)
    key(app, Qt.Key.Key_Space, repeat=True)
    key(app, Qt.Key.Key_Space, repeat=True, release=True)  # the repeat's own release: not a release
    key(app, Qt.Key.Key_Space, repeat=True)
    tick(app)
    assert len(kinds(app, "SWITCH_PRESS")) == 1
    key(app, Qt.Key.Key_Space, release=True)  # the real release re-arms it
    key(app, Qt.Key.Key_Space)
    tick(app)
    assert len(kinds(app, "SWITCH_PRESS")) == 2
    assert app.task.trials == []  # both were off target


def test_space_does_nothing_in_a_dwell_run(make_app):
    app = make_app(choice={"pointer": "gaze", "selection": "dwell"}, live={"dwell.threshold_ms": 60000})
    up(app)
    look_at_target(app)
    key(app, Qt.Key.Key_Space)
    tick(app)
    assert app.task.trials == []


def test_the_mouse_button_and_space_are_one_switch(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_away(app)
    QTest.mousePress(app.canvas, LEFT)
    key(app, Qt.Key.Key_Space)  # the button is still down: no second press
    tick(app)
    assert len(kinds(app, "SWITCH_PRESS")) == 1
    QTest.mouseRelease(app.canvas, LEFT)


# -- a pause --------------------------------------------------------------------------------------


def test_a_press_while_paused_is_ignored_and_does_not_select_on_resume(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    tick(app)
    app._set_paused(True)
    click(app)
    tick(app)  # a paused tick: the press is consumed and logged
    assert [e["phase"] for e in kinds(app, "SWITCH_IGNORED")] == ["paused"]
    app._set_paused(False)
    tick(app, 3)
    assert app.task.trials == [] and kinds(app, "SWITCH_PRESS") == []


def test_a_press_that_waits_across_a_resume_is_dropped(make_app):
    app = make_app(choice=SWITCH)
    up(app)
    look_at_target(app)
    app._set_paused(True)
    click(app)  # latched, but not yet seen by a tick
    app._set_paused(False)
    tick(app, 2)
    assert app.task.trials == []


# -- I6: the OS cursor ---------------------------------------------------------------------------


def test_the_cursor_is_parked_on_the_canvas_and_hidden_at_the_start(make_app, parked):
    app = make_app(choice=SWITCH)
    app.view.show()
    tick(app)
    assert app.run_cursor.hidden and app.canvas.cursor().shape() == Qt.CursorShape.BlankCursor
    assert parked == [app.canvas]
    tick(app, 3)
    assert parked == [app.canvas]  # parked once, not every frame


def test_the_cursor_waits_for_the_canvas_to_be_on_screen(make_app, parked):
    app = make_app(choice=SWITCH)
    tick(app)  # the view was never shown
    assert parked == [] and not app.run_cursor.hidden
    app.view.show()
    tick(app)
    assert parked == [app.canvas]


def test_a_pause_gives_the_cursor_back_and_a_resume_hides_and_parks_it_again(make_app, parked):
    app = make_app(choice=SWITCH)
    app.view.show()
    tick(app)
    app._set_paused(True)
    assert not app.run_cursor.hidden and app.canvas.cursor().shape() == Qt.CursorShape.ArrowCursor
    tick(app)
    assert parked == [app.canvas]  # nothing is parked while paused
    app._set_paused(False)
    tick(app)
    assert app.run_cursor.hidden and parked == [app.canvas, app.canvas]
    assert app.canvas.cursor().shape() == Qt.CursorShape.BlankCursor


def test_the_end_of_the_run_gives_the_cursor_back(make_app, parked):
    app = make_app(choice=SWITCH)
    app.view.show()
    tick(app)
    assert app.run_cursor.hidden
    app._shutdown()
    assert not app.run_cursor.hidden and app.canvas.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_a_quit_gives_the_cursor_back(make_app, parked):
    app = make_app(choice=SWITCH)
    app.view.show()
    tick(app)
    asked = []
    app.confirm_quit = lambda *a: asked.append(app.run_cursor.hidden) or True
    app._request_quit()
    assert asked == [False]  # shown while the question is up
    assert not app.run_cursor.hidden


@pytest.mark.parametrize(
    "choice",
    [
        {"pointer": "gaze", "selection": "dwell"},  # the cursor is not hidden for a dwell run
        {"pointer": "mouse", "selection": "switch"},  # the mouse is the pointer: it must be seen
        {"pointer": "mouse", "selection": "dwell"},
    ],
)
def test_the_cursor_is_left_alone_unless_it_is_gaze_with_a_switch(make_app, parked, choice):
    app = make_app(choice=choice)
    app.view.show()
    tick(app, 3)
    assert parked == [] and not app.run_cursor.hidden
    assert app.canvas.cursor().shape() == Qt.CursorShape.ArrowCursor


# -- a whole run, and what it leaves on disk ------------------------------------------------------


def test_a_whole_switch_run_leaves_the_click_counts_and_events(make_app):
    app = make_app(choice=SWITCH, trials=3)
    ticks_left = 4000
    while not app._shutdown_done and ticks_left:
        ticks_left -= 1
        tick(app)
        if app._shutdown_done or app.task.phase.name != "WAIT_INPUT":
            continue
        look_away(app)
        tick(app)
        click(app)  # one Click error first, then the hit
        tick(app)
        look_at_target(app)
        tick(app)
        click(app)
        tick(app)
    assert app._shutdown_done and len(app.task.trials) == 3
    folder = app.recorder.session_dir
    with (folder / "trials.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["clicks"], r["click_errors"], r["is_hit"]) for r in rows] == [("2", "1", "1")] * 3
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert (meta["input_mode"], meta["input_pointer"], meta["input_selection"]) == (
        "gaze_switch", "gaze", "switch",
    )
    assert meta["settings"]["structural"]["input"] == {"pointer": "gaze", "selection": "switch"}
    assert len(kinds(app, "SWITCH_PRESS")) == 6 and len(kinds(app, "SWITCH_IGNORED")) == 0
    assert "Input: pointer gaze, selection switch." in (folder / "session.log").read_text(encoding="utf-8")
    assert {e["kind"] for e in events_of(app)} >= {"SWITCH_PRESS", "MISS_CLICK", "HIT"}


# -- A4: what the canvas draws ---------------------------------------------------------------------

BLACK = (0, 0, 0)
THEME = {"background": "#000000", "particle_color": "#ffd54f", "cursor_color": "#ffffff"}
CX, CY, R = 200, 150, 40


def canvas_with(**state):
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(400, 300)
    canvas.show_cursor = False
    canvas.show_instant_feedback = False
    canvas.show_progress_ring = False
    for name in ("show_glow", "show_progress_ring"):
        if name in state:
            setattr(canvas, name, state.pop(name))
    canvas.set_frame(
        target_xy_norm=(0.5, 0.5),
        target_radius_px=float(R),
        cursor_xy_norm=(0.02, 0.02),
        cursor_valid=True,
        dwell_progress=state.pop("dwell_progress", 0.0),
        selectable=state.pop("selectable", True),
        on_target=state.pop("on_target", False),
    )
    return canvas


def rgb(canvas, x, y):
    c = canvas.grab().toImage().pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def test_the_glow_is_drawn_round_the_target_while_the_pointer_is_on_it(qapp):
    outside = (CX + R + 14, CY)  # past the target and its white outline, inside the glow
    lit = rgb(canvas_with(show_glow=True, on_target=True), *outside)
    assert lit != BLACK and lit[0] > 40 and lit[0] > lit[2]  # warm light, not the background


def test_no_glow_when_the_pointer_is_off_the_target(qapp):
    assert rgb(canvas_with(show_glow=True, on_target=False), CX + R + 14, CY) == BLACK


def test_no_glow_when_it_is_switched_off(qapp):
    assert rgb(canvas_with(show_glow=False, on_target=True), CX + R + 14, CY) == BLACK


def test_no_glow_while_the_target_cannot_be_selected(qapp):
    assert rgb(canvas_with(show_glow=True, on_target=True, selectable=False), CX + R + 14, CY) == BLACK


def test_the_glow_fades_out_with_distance(qapp):
    canvas = canvas_with(show_glow=True, on_target=True)
    near, far, beyond = (rgb(canvas, CX + R + d, CY)[0] for d in (8, 22, 60))
    assert near > far > beyond and beyond == 0


def test_the_dwell_ring_is_not_drawn_when_it_is_switched_off(qapp):
    top_of_ring = (CX, CY - (R + 16))
    on = canvas_with(show_progress_ring=True, dwell_progress=0.5)
    off = canvas_with(show_progress_ring=False, dwell_progress=0.5)
    assert rgb(on, *top_of_ring) != BLACK  # the arc starts at the top
    assert rgb(off, *top_of_ring) == BLACK


# -- the canvas's own switch signals ------------------------------------------------------------------


def test_the_canvas_emits_the_switch_only_when_enabled_and_for_the_left_button(qapp):
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(100, 100)
    got = []
    canvas.switchPressed.connect(lambda: got.append("down"))
    canvas.switchReleased.connect(lambda: got.append("up"))
    QTest.mouseClick(canvas, LEFT)
    assert got == ["up"]  # not enabled: no press (a release is harmless)
    got.clear()
    canvas.switch_press_enabled = True
    QTest.mouseClick(canvas, LEFT)
    QTest.mouseClick(canvas, RIGHT)
    assert got == ["down", "up"]


def test_losing_the_focus_releases_the_switch(qapp):
    canvas = TaskCanvas(theme=THEME)
    got = []
    canvas.switchReleased.connect(lambda: got.append("up"))
    canvas.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))
    assert got == ["up"]
