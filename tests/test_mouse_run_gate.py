"""SPEC-input-selection-and-follow.md H5, I7, W1 (acceptance A5, with A1 on the Start page):
a test with Pointer = Mouse may be started and practised with no tracker and no calibration;
the Start page says so in one line and keeps its other blockers; a Gaze test is gated exactly
as before. The read-aloud wording of Switch and Mouse (W1). Offscreen Qt, a scratch folder."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

import src.app as app_module
from src.engine.config import load_task_config
from src.engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from src.engine.subject_tests import STATUS_DONE
from src.inputs.mouse_gaze import MouseGazeSource
from src.inputs.no_tracker import NoTracker
from src.ui.dashboard_flow import Flow
from src.ui.settings_snapshot import merged_config
from src.ui.start_test_page import (
    MOUSE_NOTE_ALONGSIDE,
    MOUSE_NOTE_NO_TRACKER,
    MOUSE_NOTE_NOT_CALIBRATED,
    StartTestPage,
)
from src.ui.task_instructions import build_instructions
from tests.dashboard_fixtures import new_test
from tests.run_flow_fixtures import (
    Answers,
    close_run_window,
    configure_fast,
    finish_trials,
    make_run_window,
    open_start,
    run_dirs,
    stored_tests,
)

MOUSE = {"input": {"pointer": "mouse", "selection": "dwell"}}
OTHER = "Subject ID is empty."


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, tracker, pointing = make_run_window(tmp_path, monkeypatch)
    # The mouse a Mouse test points with: a source reading the test's own stand-in cursor.
    monkeypatch.setattr(app_module, "MouseGazeSource", lambda: MouseGazeSource(cursor_pos=pointing))
    yield win, tracker, pointing
    close_run_window(win)


class Blockers:
    def __init__(self, *items):
        self.items = list(items)

    def __call__(self):
        return list(self.items)


def page_for(task_id="click_grid", *, pointer="gaze", blockers=()):
    cfg = load_task_config(task_id)
    cfg["task"]["input"] = {"pointer": pointer, "selection": "dwell"}
    provider = Blockers(*blockers)
    page = StartTestPage()
    page.set_blockers_provider(provider)
    page.set_test(test_name="Test 1", task_id=task_id, cfg=cfg)
    return page, provider


# -- the Start page ----------------------------------------------------------------------------------


def test_a_gaze_test_is_gated_as_before_and_has_no_mouse_note(qapp):
    page, _ = page_for(pointer="gaze", blockers=[TRACKER_BLOCKER, CALIBRATION_BLOCKER])
    assert page.blockers() == [TRACKER_BLOCKER, CALIBRATION_BLOCKER]
    assert not page.start_button.isEnabled() and not page.practice_button.isEnabled()
    assert page.mouse_note.isHidden() and not page.banner.isHidden()


def test_a_mouse_test_with_no_tracker_can_start_and_practise_and_says_so(qapp):
    page, _ = page_for(pointer="mouse", blockers=[TRACKER_BLOCKER, CALIBRATION_BLOCKER])
    assert page.blockers() == [] and page.banner.isHidden()
    assert page.start_button.isEnabled() and page.practice_button.isEnabled()
    assert not page.mouse_note.isHidden()
    assert page.mouse_note_label.text() == MOUSE_NOTE_NO_TRACKER
    assert MOUSE_NOTE_NO_TRACKER == "Mouse test. The tracker is not connected, so no eye data will be recorded."


def test_a_mouse_test_with_a_ready_tracker_says_the_eye_data_is_recorded_alongside(qapp):
    page, _ = page_for(pointer="mouse", blockers=[])
    assert page.start_button.isEnabled() and not page.mouse_note.isHidden()
    assert page.mouse_note_label.text() == MOUSE_NOTE_ALONGSIDE == "Mouse test. Eye data will be recorded alongside."


def test_a_connected_but_uncalibrated_tracker_records_nothing_and_the_note_says_that(qapp):
    page, _ = page_for(pointer="mouse", blockers=[CALIBRATION_BLOCKER])
    assert page.start_button.isEnabled()
    assert page.mouse_note_label.text() == MOUSE_NOTE_NOT_CALIBRATED


def test_a_mouse_test_keeps_every_other_blocker(qapp):
    page, _ = page_for(pointer="mouse", blockers=[TRACKER_BLOCKER, OTHER])
    assert page.blockers() == [OTHER]
    assert not page.start_button.isEnabled() and not page.practice_button.isEnabled()
    assert OTHER in page.banner_label.text() and TRACKER_BLOCKER not in page.banner_label.text()
    assert not page.mouse_note.isHidden()  # the note and the banner can show together


def test_the_note_follows_the_tracker_when_it_drops_or_returns(qapp):
    page, provider = page_for(pointer="mouse", blockers=[])
    assert page.mouse_note_label.text() == MOUSE_NOTE_ALONGSIDE
    provider.items = [TRACKER_BLOCKER, CALIBRATION_BLOCKER]  # it dropped
    page.refresh_blockers()
    assert page.mouse_note_label.text() == MOUSE_NOTE_NO_TRACKER and page.start_button.isEnabled()


def test_a_new_test_resets_the_gate_to_its_own_pointer(qapp):
    page, _ = page_for(pointer="mouse", blockers=[TRACKER_BLOCKER])
    assert page.start_button.isEnabled()
    cfg = eye_config("scanning")  # no input block: the global mode, eye
    page.set_test(test_name="Scanning 1", task_id="scanning", cfg=cfg)
    assert page.mouse_note.isHidden() and not page.start_button.isEnabled()


def test_a_stale_enabled_button_of_a_gaze_test_still_cannot_launch(qapp):
    page, provider = page_for(pointer="gaze", blockers=[])
    started = []
    page.startRequested.connect(lambda: started.append(1))
    provider.items = [TRACKER_BLOCKER]
    page.start_button.click()
    assert started == []


# -- the run flow -------------------------------------------------------------------------------------------------


def unplug(win):
    """The Setup tab has no tracker and no calibration, and its gate says so."""
    win.setup_page._client = None
    win.setup_page._calibration_result = None
    win.blockers[:] = [TRACKER_BLOCKER, CALIBRATION_BLOCKER]


def only_test(win):
    (test,) = stored_tests(win)
    return test


def test_a_gaze_test_still_cannot_start_without_a_tracker(rig):
    win, _tracker, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=1, input={"pointer": "gaze", "selection": "dwell"})
    page = open_start(win, test)
    unplug(win)
    page.refresh_blockers()
    assert not page.start_button.isEnabled()
    page.start_button.setEnabled(True)  # even if the button looked enabled
    page.start_button.click()
    assert win.run_flow.app is None and win.flow is Flow.START


def test_a_mouse_test_starts_with_no_tracker_and_no_calibration(rig, monkeypatch):
    win, tracker, pointing = rig
    monkeypatch.setattr(
        app_module, "Calibration", lambda *a, **k: pytest.fail("a Mouse test started a calibration")
    )
    test = new_test(win)
    configure_fast(win, test, trials=1, **MOUSE)
    page = open_start(win, test)
    unplug(win)
    page.refresh_blockers()
    assert page.start_button.isEnabled() and page.mouse_note_label.text() == MOUSE_NOTE_NO_TRACKER
    page.start_button.click()
    app = win.run_flow.app
    assert app is not None and win.flow is Flow.RUN, page.message_label.text()
    app.timer.stop()
    assert isinstance(app.client, NoTracker) and app._gaze_recorded is False
    assert app.run_mode == "record" and app.metadata.test_id == test.test_id
    Answers().install(win.run_flow)
    finish_trials(app, pointing)
    (folder,) = run_dirs(win)
    names = {p.name for p in folder.iterdir()}
    assert "pointer_stream.csv" in names and not names & {"gaze_stream.csv", "all_gaze.csv"}
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert (meta["input_mode"], meta["gaze_recorded"], meta["calibration_source"]) == (
        "mouse_dwell", False, "not run",
    )
    assert only_test(win).status == STATUS_DONE  # saved like any run


def test_a_mouse_test_records_the_setup_trackers_gaze_alongside(rig):
    win, tracker, pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=1, **MOUSE)
    open_start(win, test)  # the rig's tracker is connected and calibrated, no blockers
    page = win.run_flow.page
    assert page.mouse_note_label.text() == MOUSE_NOTE_ALONGSIDE
    page.start_button.click()
    app = win.run_flow.app
    app.timer.stop()
    assert app.client is tracker and app._gaze_recorded is True
    assert app.pointer_source is not tracker and app.metadata.calibration_source in ("loaded", "measured")
    Answers().install(win.run_flow)
    finish_trials(app, pointing)
    (folder,) = run_dirs(win)
    names = {p.name for p in folder.iterdir()}
    assert {"pointer_stream.csv", "gaze_stream.csv", "all_gaze.csv"} <= names


def test_a_tracker_that_dropped_is_not_used_for_a_mouse_test(rig):
    win, tracker, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=1, **MOUSE)
    open_start(win, test)
    tracker.is_connected = lambda: False  # the Setup tab's tracker has dropped
    win.blockers[:] = [TRACKER_BLOCKER]
    win.run_flow.page.start_button.click()
    app = win.run_flow.app
    app.timer.stop()
    assert isinstance(app.client, NoTracker) and app._gaze_recorded is False


def test_a_mouse_practice_needs_no_tracker_and_leaves_no_trace(rig):
    win, tracker, _pointing = rig
    test = new_test(win)
    configure_fast(win, test, trials=2, **MOUSE)
    page = open_start(win, test)
    unplug(win)
    page.refresh_blockers()
    page.practice_button.click()
    app = win.run_flow.app
    assert app is not None and app.run_mode == "practice", page.message_label.text()
    app.timer.stop()
    assert isinstance(app.client, NoTracker) and app.recorder.session_dir is None
    assert run_dirs(win) == []


# -- W1: the read-aloud wording ------------------------------------------------------------------------------------------


def eye_config(task_id):
    """The task's config with the global input mode ``eye``, whatever the local file says."""
    cfg = load_task_config(task_id)
    cfg["input"] = {"mode": "eye"}
    return cfg


def instructions(task_id, *, pointer="gaze", selection="dwell", glow=True, **live):
    cfg = eye_config(task_id)
    cfg["task"]["input"] = {"pointer": pointer, "selection": selection}
    cfg["task"].setdefault("feedback", {})["target_glow"] = glow
    return build_instructions(task_id, cfg, live or None)


def test_dwell_wording_is_unchanged_by_the_new_settings():
    for task_id in ("click_static", "click_grid", "scanning", "follow_moving"):
        base = build_instructions(task_id, eye_config(task_id))
        assert instructions(task_id) == base


@pytest.mark.parametrize(
    "task_id, step, noun",
    [
        ("click_static", "Look at the circle, then press the button.", "circle"),
        ("click_grid", "Look at the lit square, then press the button.", "square"),
        ("scanning", "Find the bright shape, look at it, then press the button.", "shape"),
    ],
)
def test_switch_replaces_the_dwell_step_with_a_press(task_id, step, noun):
    ins = instructions(task_id, selection="switch")
    glow = f" The {noun} glows while you are looking at it."
    assert step + glow in ins.steps
    assert not any("keep looking" in s or "seconds" in s or "ring" in s for s in ins.steps)
    assert len(ins.steps) == 4 and ins.note.startswith("NOTE: If the ")  # the timeout still applies
    plain = instructions(task_id, selection="switch", glow=False)
    assert step in plain.steps and not any("glows" in s for s in plain.steps)
    # Only that one step changed.
    dwell = instructions(task_id)
    assert [a == b for a, b in zip(ins.steps, dwell.steps, strict=True)].count(False) == 1


def test_the_switch_wording_ignores_the_dwell_time_and_the_ring_setting():
    a = instructions("click_grid", selection="switch", **{"dwell.threshold_ms": 800, "dwell.progress_ring": True})
    b = instructions("click_grid", selection="switch", **{"dwell.threshold_ms": 2000, "dwell.progress_ring": False})
    assert a.steps == b.steps


@pytest.mark.parametrize("task_id", ["click_static", "click_grid", "scanning", "follow_moving"])
def test_mouse_replaces_the_dot_sentence_and_look_at_becomes_point_at(task_id):
    ins = instructions(task_id, pointer="mouse")
    assert ins.steps[0].startswith("Move the mouse to point at the screen. ")
    text = " ".join(ins.steps)
    assert "small dot" not in text and "Look at" not in text and "look at" not in text
    assert "looking at" not in text


def test_the_mouse_sentence_is_there_whether_or_not_the_gaze_dot_is_shown():
    with_dot = instructions("click_grid", pointer="mouse", **{"dwell.visual_cursor": True})
    without = instructions("click_grid", pointer="mouse", **{"dwell.visual_cursor": False})
    assert with_dot.steps == without.steps  # the child must be told to move the mouse either way


def test_mouse_with_dwell_says_point_at_and_keep_pointing():
    ins = instructions(
        "click_static", pointer="mouse", **{"dwell.threshold_ms": 800, "dwell.progress_ring": True}
    )
    assert ins.steps[1] == (
        "Point at the circle and keep pointing at it for about 0.8 seconds. A ring will fill up around it."
    )


def test_mouse_with_a_switch_points_then_presses_and_the_glow_is_pointed_at():
    ins = instructions("click_grid", pointer="mouse", selection="switch")
    assert ins.steps[0] == "Move the mouse to point at the screen. A board of squares will appear on the screen."
    assert ins.steps[2] == (
        "Point at the lit square, then press the button. The square glows while you are pointing at it."
    )


def test_no_placeholder_is_left_in_any_variant():
    for task_id in ("click_static", "click_grid", "scanning", "follow_moving"):
        for pointer in ("gaze", "mouse"):
            for selection in ("dwell", "switch"):
                for glow in (True, False):
                    ins = instructions(task_id, pointer=pointer, selection=selection, glow=glow)
                    for text in (ins.heading, *ins.steps, ins.note, *ins.clinician):
                        assert "{" not in text and "}" not in text and text.strip() == text


def test_the_start_page_shows_the_switch_and_mouse_wording(qapp):
    cfg = merged_config(
        load_task_config("click_grid"), None, {"input": {"pointer": "mouse", "selection": "switch"}}
    )
    page = StartTestPage()
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    shown = [label.text() for label in page.card.findChildren(QLabel)]
    assert any("Move the mouse to point at the screen." in t for t in shown)
    assert any("then press the button" in t for t in shown)


def test_the_clinician_line_before_start_fits_the_input_of_the_test():
    gaze = instructions("click_grid", pointer="gaze").clinician
    mouse = instructions("click_grid", pointer="mouse").clinician
    assert gaze[2] == 'Start records 18 trials. Check that the bottom bar says "tracking OK" before you begin.'
    assert mouse[2] == "Start records 18 trials. Check that the mouse moves the pointer on the screen before you begin."
    assert "tracking" not in mouse[2] and "bottom bar" not in mouse[2]
    assert gaze[:2] == mouse[:2] and len(gaze) == len(mouse) == 3  # the pause and practice lines are the same
    for task_id in ("click_static", "scanning", "follow_moving"):
        assert instructions(task_id, pointer="mouse").clinician[2].endswith("before you begin.")
        assert "bottom bar" not in instructions(task_id, pointer="mouse").clinician[2]
        assert "tracking OK" in instructions(task_id, pointer="gaze").clinician[2]


def test_the_start_page_shows_the_mouse_clinician_line(qapp):
    cfg = merged_config(load_task_config("click_grid"), None, {"input": {"pointer": "mouse", "selection": "dwell"}})
    page = StartTestPage()
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    shown = [label.text() for label in page.card.findChildren(QLabel)]
    assert any("Check that the mouse moves the pointer on the screen" in t for t in shown)
    assert not any("Check that the bottom bar says" in t for t in shown)
