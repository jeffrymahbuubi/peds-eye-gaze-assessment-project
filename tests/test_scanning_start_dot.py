"""SPEC-scanning-search-cues.md 4.4, acceptance C5: Scanning Search's centre start dot, a switch press and a
pause before the field, and the reminder's place -- through the task, one frame at a time on a fake clock.
The helpers (``make``, ``run``, ``at_slot``) are those of ``test_scanning_search.py``; the spoken prompts
are never read from the repository's own assets."""

from __future__ import annotations

import pytest

from src.engine.target_size import ICON_DRAW_FRAC
from src.inputs.base import Pointer
from src.tasks.base_task import Phase
from src.tasks.scanning import scanning_layout_slots
from src.tasks.search_cues import SHAPE_NAMES, START_DOT_TIMEOUT_MS, reminder_placement
from tests.test_scanning_search import CENTRE, DWELL_MS, MS, at_slot, make, run

# -- C5: the centre start dot ------------------------------------------------------------------------------


def _dot_task(**kwargs):
    kwargs.setdefault("mode", "pop_out")
    return make(start_dot=True, **kwargs)


def test_the_start_dot_comes_first_and_holds_the_trial_back():
    task, spy, _ = _dot_task(trials=2)
    frames = run(task, at_slot(task, 0), 0, 400)  # looking at an icon, not the dot
    assert all(f.phase is Phase.SHOW_TARGET and f.target is None and not f.selectable for f in frames)
    spec = task.scene_spec()
    assert spec["stage"] == "start_dot" and spec["dot"]["diameter_px"] > 0
    assert (spec["dot"]["x_norm"], spec["dot"]["y_norm"]) == (0.5, 0.5)
    assert spy.kinds() == ["START_DOT_SHOWN"] and spy.events[0][1:] == (0, {"trial": 0})


def test_the_dot_goes_after_300_ms_of_gaze_within_two_degrees_and_the_trial_starts_then():
    task, spy, _ = _dot_task(trials=1)
    near = Pointer(x=0.5 + 0.9 * task.start_dot_capture_px / 1920, y=0.5, valid=True, clicked=False)
    run(task, near, 0, 290)
    assert task.phase is Phase.SHOW_TARGET and "START_DOT_DONE" not in spy.kinds()
    frame = task.update(300 * MS, near)
    assert frame.phase is Phase.WAIT_INPUT and frame.target is not None
    assert spy.kinds() == ["START_DOT_SHOWN", "START_DOT_DONE", "TARGET_SHOWN"]
    done = spy.of("START_DOT_DONE")[0]
    assert done[1] == 300 * MS and done[2] == {"trial": 0, "result": "fixated", "elapsed_ms": 300.0}
    assert spy.of("TARGET_SHOWN")[0][1] == 300 * MS
    run(task, at_slot(task, task.targets[0].slot_index), 310, 310 + DWELL_MS + 40)
    trial = task.trials[0]
    assert (trial.start_dot_ms, trial.start_dot_timeout) == (300.0, False)
    # Reaction time is from the field, never from the dot.
    assert trial.t_target_shown_ns == 300 * MS and trial.reaction_time_ms == pytest.approx(DWELL_MS + 10, abs=20)


def test_gaze_beyond_two_degrees_does_not_count():
    task, spy, _ = _dot_task(trials=1)
    far = Pointer(x=0.5 + 1.1 * task.start_dot_capture_px / 1920, y=0.5, valid=True, clicked=False)
    run(task, far, 0, 1000)
    assert task.phase is Phase.SHOW_TARGET and "START_DOT_DONE" not in spy.kinds()


def test_a_blink_does_not_restart_the_hold():
    task, spy, _ = _dot_task(trials=1)
    run(task, CENTRE, 0, 200)
    run(task, Pointer(x=0.5, y=0.5, valid=False, clicked=False), 200, 300)  # 100 ms: inside the hold grace
    assert not spy.of("START_DOT_DONE")
    task.update(300 * MS, CENTRE)
    assert spy.of("START_DOT_DONE")[0][1] == 300 * MS  # 300 ms since the first look, the blink counted in


def test_a_look_away_restarts_the_hold():
    task, spy, _ = _dot_task(trials=1)
    run(task, CENTRE, 0, 200)
    run(task, at_slot(task, 0), 200, 500)  # away for 300 ms: past the grace, the hold starts over
    run(task, CENTRE, 500, 790)
    assert not spy.of("START_DOT_DONE")
    run(task, CENTRE, 790, 810)
    assert spy.of("START_DOT_DONE")[0][1] == 800 * MS


def test_after_five_seconds_without_it_the_trial_goes_on_and_the_timeout_is_recorded():
    task, spy, _ = _dot_task(trials=1)
    run(task, at_slot(task, 0), 0, int(START_DOT_TIMEOUT_MS) - 10)
    assert task.phase is Phase.SHOW_TARGET
    frame = task.update(int(START_DOT_TIMEOUT_MS) * MS, at_slot(task, 0))
    assert frame.phase is Phase.WAIT_INPUT
    done = spy.of("START_DOT_DONE")[0]
    assert done[2] == {"trial": 0, "result": "timeout", "elapsed_ms": 5000.0}
    run(task, at_slot(task, task.targets[0].slot_index), 5010, 5010 + DWELL_MS + 40)
    trial = task.trials[0]
    assert trial.start_dot_ms is None and trial.start_dot_timeout is True
    assert trial.t_target_shown_ns == 5000 * MS
    row = trial.as_row()
    assert row["start_dot_ms"] == "" and row["start_dot_timeout"] == 1


def test_every_trial_starts_from_the_dot_again():
    task, spy, _ = _dot_task(trials=3)
    for t in range(0, 6000, 10):
        slot = task.targets[task._trial_index].slot_index if task.phase is Phase.WAIT_INPUT else None
        task.update(t * MS, at_slot(task, slot) if slot is not None else CENTRE)
        if task.is_done:
            break
    assert [e[2]["trial"] for e in spy.of("START_DOT_SHOWN")] == [0, 1, 2]
    assert [r.start_dot_ms for r in task.trials] == [300.0, 300.0, 300.0]
    assert [r.start_dot_timeout for r in task.trials] == [False] * 3


def test_with_match_the_sample_the_dot_comes_before_the_sample():
    task, spy, _ = make(trials=1, start_dot=True)
    run(task, CENTRE, 0, 300)
    assert task.scene_spec()["stage"] == "start_dot"
    task.update(300 * MS, CENTRE)
    assert task.scene_spec()["stage"] == "sample" and task.phase is Phase.SHOW_TARGET
    run(task, CENTRE, 310, 1810)
    assert task.phase is Phase.WAIT_INPUT
    assert spy.kinds() == [
        "START_DOT_SHOWN", "START_DOT_DONE", "SAMPLE_START", "TARGET_SHOWN", "FIELD_SHOWN",
    ]
    assert spy.of("SAMPLE_START")[0][1] == 300 * MS and spy.of("TARGET_SHOWN")[0][1] == 1800 * MS
    run(task, at_slot(task, task.targets[0].slot_index), 1820, 1820 + DWELL_MS + 40)
    assert task.trials[0].start_dot_ms == 300.0 and task.trials[0].start_dot_timeout is False


def test_the_dot_works_with_a_mouse_pointer_too():
    task, spy, _ = _dot_task(trials=1, input_mode="mouse_dwell")
    run(task, CENTRE, 0, 320)
    assert spy.of("START_DOT_DONE") and task.phase is Phase.WAIT_INPUT


def test_the_dot_size_is_two_degrees_by_default_on_the_reference_monitor():
    task, _, _ = _dot_task()
    assert task.start_dot_px == pytest.approx(task.start_dot_capture_px / 2, rel=0.01)
    assert 20 < task.start_dot_px < 60  # 1 deg on the reference monitor at 650 mm


def test_a_resolved_size_in_the_config_wins():
    task, _, _ = _dot_task(extra={"start_dot_px": 41.5, "start_dot_capture_px": 99.0, "sample_text_px": 70.0})
    assert (task.start_dot_px, task.start_dot_capture_px, task.sample_text_px) == (41.5, 99.0, 70.0)


# -- a switch: presses before the field count for nothing -----------------------------------------------------


def test_a_switch_press_during_the_dot_or_the_sample_is_ignored_and_logged():
    task, spy, _ = make(trials=1, start_dot=True, input_mode="gaze_switch")
    task.update(0, CENTRE)
    task.update(50 * MS, Pointer(x=0.5, y=0.5, valid=True, clicked=True))
    run(task, CENTRE, 60, 310)  # the dot completes on gaze, not on the press
    assert task.scene_spec()["stage"] == "sample"
    task.update(400 * MS, Pointer(x=0.5, y=0.5, valid=True, clicked=True))
    ignored = spy.of("SWITCH_IGNORED")
    assert [e[2]["phase"] for e in ignored] == ["start_dot", "sample"]
    run(task, CENTRE, 410, 1810)
    assert task.phase is Phase.WAIT_INPUT and task._current.clicks == 0 and not task.trials


def test_a_switch_selects_the_target_in_match_the_sample_as_before():
    task, spy, _ = make(trials=1, input_mode="gaze_switch")
    run(task, CENTRE, 0, 1600)
    slot = task.targets[0].slot_index
    task.update(1700 * MS, at_slot(task, slot, clicked=True))
    assert task.trials[0].is_hit and task.trials[0].clicks == 1
    assert task.trials[0].first_icon_looked_at_slot == slot


# -- pause -------------------------------------------------------------------------------------------------


def test_a_pause_during_the_sample_drops_it_and_the_trial_starts_over_on_resume():
    task, spy, feedback = make(trials=2)
    run(task, CENTRE, 0, 800)
    assert task.pause(800 * MS) is False  # no trial was running
    assert ("stop",) in feedback.audio and task.phase is Phase.READY and task.scene_spec()["stage"] == "blank"
    frozen = task.update(5000 * MS, CENTRE)
    assert frozen.target is None and len(spy.of("SAMPLE_START")) == 1  # nothing advances while paused
    task.resume(5000 * MS)
    run(task, CENTRE, 5010, 6600)
    assert [e[2]["trial"] for e in spy.of("SAMPLE_START")] == [0, 0]  # the same trial, its sample again
    assert task.phase is Phase.WAIT_INPUT and spy.of("TARGET_SHOWN")[0][1] >= 6500 * MS
    assert feedback.audio.count(("prompt", SHAPE_NAMES[task.trial_target_shapes[0]])) == 2


def test_a_pause_during_the_start_dot_restarts_the_dot_on_resume():
    task, spy, _ = _dot_task(trials=1)
    run(task, CENTRE, 0, 200)
    task.pause(200 * MS)
    task.resume(900 * MS)
    run(task, CENTRE, 910, 1230)
    assert [e[2]["trial"] for e in spy.of("START_DOT_SHOWN")] == [0, 0]
    assert spy.of("START_DOT_DONE")[0][1] >= 1200 * MS  # a full 300 ms after the resume
    assert task.phase is Phase.WAIT_INPUT


def test_a_pause_in_the_field_re_presents_the_trial_with_its_sample():
    task, spy, _ = make(trials=2)
    run(task, CENTRE, 0, 1600)
    assert task.pause(1600 * MS) is True and spy.of("TRIAL_INTERRUPTED")
    task.resume(2000 * MS)
    run(task, CENTRE, 2010, 3600)
    assert [e[2]["trial"] for e in spy.of("SAMPLE_START")] == [0, 0]
    assert task.phase is Phase.WAIT_INPUT and task._trial_index == 0


# -- the reminder's place -----------------------------------------------------------------------------------


@pytest.mark.parametrize("arrangement", ["grid", "row", "ring"])
@pytest.mark.parametrize("n_icons", [2, 4, 6, 8])
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768)])
def test_the_reminder_never_overlaps_a_slot(arrangement, n_icons, size):
    w, h = size
    slots = scanning_layout_slots(n_icons, arrangement, 0.14)
    task, _, _ = make(n_icons=n_icons, arrangement=arrangement)
    task.set_screen_size(w, h)
    icon_r = task.effective_radius_px(task.targets[0]) * ICON_DRAW_FRAC
    x, y, radius = reminder_placement(slots, w, h, icon_r)
    assert radius == pytest.approx(icon_r / 2)
    for sx, sy in slots:
        gap = ((x * w - sx * w) ** 2 + (y * h - sy * h) ** 2) ** 0.5
        assert gap >= radius + icon_r, (arrangement, n_icons, size)
    assert y * h >= radius  # on the canvas


def test_the_reminder_is_at_the_top_centre_unless_a_slot_is_in_the_way():
    slots = scanning_layout_slots(4, "grid", 0.14)
    x, _y, radius = reminder_placement(slots, 1920, 1080, 90.0)
    assert x == pytest.approx(0.5) and radius == 45.0
    ring = scanning_layout_slots(6, "ring", 0.14)  # an icon sits at the top centre
    x, y, radius = reminder_placement(ring, 1920, 1080, 90.0)
    assert x * 1920 == pytest.approx(radius + max(8.0, 0.02 * 1080)) and x < 0.1  # the top-left corner
    assert y * 1080 == pytest.approx(radius + max(8.0, 0.02 * 1080))
