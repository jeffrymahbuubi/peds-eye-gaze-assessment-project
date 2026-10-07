"""SPEC-input-selection-and-follow.md I5 (acceptance A2, A3) on the engine side: how a
switch press is judged -- on button down, hit or Click error, the 150 ms blink fallback,
presses between trials ignored -- and the ``clicks`` / ``click_errors`` it leaves in
``trials.csv``. No Qt: ``BaseTask`` is driven one frame at a time."""

from __future__ import annotations

import csv

import pytest

from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.engine.feedback import NullFeedback
from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig, DwellSelector
from src.inputs.switch_input import SwitchInput
from src.tasks.base_task import BaseTask, Phase, TargetSpec
from src.tasks.switch_select import SWITCH_FALLBACK_MS, PointerTrace

MS = 1_000_000


class Spy:
    """Recorder double: the events a task emits."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []

    def record_event(self, kind, t_ns, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message) -> None: ...

    def of(self, kind):
        return [e for e in self.events if e[0] == kind]


class Fixed(BaseTask):
    """Targets at x = 0.3, 0.5, 0.7 on a 1000 x 1000 canvas (radius 50 px)."""

    def build_targets(self):
        return [TargetSpec(index=i, x_norm=0.3 + 0.2 * i, y_norm=0.5, radius_px=50.0) for i in range(3)]


def make(
    mode="gaze_switch", *, timeout_ms=1000, iti_ms=200, preroll_ms=0.0, dwell=None, refractory_ms=0
):
    """``refractory_ms`` (the switch's debounce) is 0 unless a test asks for one."""
    spy = Spy()
    cfg = {
        "task": {"task_id": "fixed", "timeout_ms": timeout_ms, "inter_trial_interval_ms": iti_ms},
        "dwell": {"refractory_ms": refractory_ms},
    }
    task = Fixed(
        cfg, 1000, 1000, recorder=spy, feedback=NullFeedback(), dwell=dwell,
        input_mode=mode, preroll_ms=preroll_ms,
    )
    return task, spy


def at(x, *, valid=True, clicked=False, y=0.5):
    return Pointer(x=x, y=y, valid=valid, clicked=clicked)


ON, OFF = 0.3, 0.9  # trial 0's target is at x = 0.3


# -- the fallback rule on its own (A3) -------------------------------------------------


def test_the_fallback_window_is_150_ms():
    assert SWITCH_FALLBACK_MS == 150


def test_a_valid_pointer_is_used_as_it_is():
    trace = PointerTrace()
    trace.observe(0, True, 10.0, 20.0, 0.1, 0.2)
    point = trace.at_press(500 * MS, True, 300.0, 400.0, 0.3, 0.4)
    assert (point.px, point.py, point.used_fallback) == (300.0, 400.0, False)


@pytest.mark.parametrize("age_ms, used", [(0, True), (100, True), (150, True), (151, False), (200, False)])
def test_an_invalid_pointer_falls_back_to_the_last_valid_one_within_150_ms(age_ms, used):
    trace = PointerTrace()
    trace.observe(1000 * MS, True, 10.0, 20.0, 0.1, 0.2)
    trace.observe(1000 * MS + 20 * MS, False, 999.0, 999.0, 0.9, 0.9)  # an invalid frame is not kept
    point = trace.at_press(1000 * MS + age_ms * MS, False, 999.0, 999.0, 0.9, 0.9)
    if used:
        assert (point.px, point.py, point.x_norm, point.used_fallback) == (10.0, 20.0, 0.1, True)
    else:
        assert point is None


def test_with_no_valid_pointer_yet_there_is_no_gaze():
    assert PointerTrace().at_press(0, False, 0.0, 0.0, 0.5, 0.5) is None


def test_reset_forgets_the_last_pointer():
    trace = PointerTrace()
    trace.observe(0, True, 1.0, 1.0, 0.1, 0.1)
    trace.reset()
    assert trace.at_press(10 * MS, False, 0.0, 0.0, 0.5, 0.5) is None


# -- the switch latch (I5a: on button down) ---------------------------------------------


def test_a_press_counts_once_on_button_down_and_re_arms_on_release():
    switch = SwitchInput()
    assert switch.consume_click() is False
    switch.press()
    assert switch.consume_click() is True and switch.consume_click() is False
    switch.press()  # still held: auto-repeat, or a held button, is not another press
    assert switch.consume_click() is False
    switch.release()
    switch.press()
    assert switch.consume_click() is True


def test_reset_clears_a_waiting_and_a_held_press():
    switch = SwitchInput()
    switch.press()
    switch.reset()
    assert switch.consume_click() is False and not switch.is_held
    switch.press()
    assert switch.consume_click() is True


# -- A2: a press on the target selects, a press off it is a Click error -------------------


def test_a_press_with_the_gaze_on_the_target_is_a_hit():
    task, spy = make()
    task.update(0, at(ON))  # trial 0 is up
    task.update(40 * MS, at(ON, clicked=True))
    row = task.trials[0]
    assert (row.is_hit, row.is_timeout) == (True, False)
    assert (row.clicks, row.click_errors, row.attempts) == (1, 0, 1)
    assert row.t_click_ns == 40 * MS
    ((_k, _t, press),) = spy.of("SWITCH_PRESS")
    assert press["on_target"] is True and press["used_fallback"] is False and press["trial"] == 0
    assert spy.of("MISS_CLICK") == [] and task.phase is Phase.ITI


def test_a_press_off_the_target_is_a_click_error_and_the_trial_goes_on():
    task, spy = make()
    task.update(0, at(OFF))
    task.update(40 * MS, at(OFF, clicked=True))
    assert task.trials == [] and task.phase is Phase.WAIT_INPUT  # no end, no hit
    (_k, _t, press), = spy.of("SWITCH_PRESS")
    assert press["on_target"] is False
    ((_k, _t, miss),) = spy.of("MISS_CLICK")
    assert miss["selectable"] is True
    # The child then looks at the target and presses again: that one is the hit.
    task.update(80 * MS, at(ON))
    task.update(120 * MS, at(ON, clicked=True))
    row = task.trials[0]
    assert (row.is_hit, row.clicks, row.click_errors, row.attempts) == (True, 2, 1, 2)


def test_every_press_is_counted_even_a_run_of_errors():
    task, _spy = make()
    task.update(0, at(OFF))
    for i in range(1, 4):
        task.update(i * 20 * MS, at(OFF, clicked=True))
    task.update(200 * MS, at(ON, clicked=True))
    row = task.trials[0]
    assert (row.clicks, row.click_errors, row.is_hit) == (4, 3, True)


def test_a_press_after_the_timeout_clock_runs_out_still_ends_by_timeout():
    task, _spy = make(timeout_ms=100)
    task.update(0, at(OFF))
    task.update(50 * MS, at(OFF, clicked=True))
    task.update(150 * MS, at(OFF))
    row = task.trials[0]
    assert (row.is_timeout, row.is_hit, row.clicks, row.click_errors) == (True, False, 1, 1)


def test_dwell_selection_leaves_the_click_counts_at_zero():
    dwell = DwellSelector(DwellConfig(threshold_ms=100, refractory_ms=0))
    task, spy = make("eye", dwell=dwell)
    for t in range(0, 400, 20):
        task.update(t * MS, at(ON))
        if task.trials:
            break
    row = task.trials[0]
    assert row.is_hit and (row.clicks, row.click_errors) == (0, 0)
    assert spy.of("SWITCH_PRESS") == [] and spy.of("SWITCH_IGNORED") == []


def test_a_click_means_nothing_under_dwell():
    dwell = DwellSelector(DwellConfig(threshold_ms=10_000))
    task, spy = make("eye", dwell=dwell)
    task.update(0, at(ON))
    task.update(40 * MS, at(ON, clicked=True))
    assert task.trials == [] and spy.events[-1][0] != "SWITCH_PRESS"


@pytest.mark.parametrize(
    "mode, selection",
    [("eye", "dwell"), ("mouse_dwell", "dwell"), ("mouse_follow", "dwell"),
     ("gaze_switch", "switch"), ("switch", "switch")],
)
def test_the_selection_follows_the_input_mode(mode, selection):
    dwell = DwellSelector(DwellConfig(threshold_ms=100))
    task, _spy = make(mode, dwell=dwell)
    assert task.input_selection == selection


def test_a_mouse_dwell_run_selects_by_dwell():
    dwell = DwellSelector(DwellConfig(threshold_ms=100, refractory_ms=0))
    task, _spy = make("mouse_dwell", dwell=dwell)
    for t in range(0, 400, 20):
        task.update(t * MS, at(ON))
        if task.trials:
            break
    assert task.trials and task.trials[0].is_hit


# -- A3: a press in a blink ------------------------------------------------------------------


def test_a_press_in_a_blink_uses_the_last_valid_pointer_and_says_so():
    task, spy = make()
    task.update(0, at(ON))
    task.update(40 * MS, at(ON))
    task.update(100 * MS, at(ON, valid=False, clicked=True))  # 60 ms after the last valid frame
    row = task.trials[0]
    assert (row.is_hit, row.clicks, row.click_errors) == (True, 1, 0)
    ((_k, _t, press),) = spy.of("SWITCH_PRESS")
    assert press["used_fallback"] is True and press["on_target"] is True


def test_a_press_100_ms_after_the_last_valid_on_target_frame_is_a_hit():
    task, _spy = make()
    task.update(0, at(ON))
    task.update(20 * MS, at(ON))  # the last valid frame
    task.update(20 * MS + 100 * MS, at(ON, valid=False, clicked=True))
    assert task.trials[0].is_hit


def test_a_press_200_ms_after_the_last_valid_frame_is_a_click_error_with_no_gaze():
    task, spy = make()
    task.update(0, at(ON))
    task.update(20 * MS, at(ON))
    task.update(20 * MS + 200 * MS, at(ON, valid=False, clicked=True))
    assert task.trials == []  # the trial goes on
    ((_k, _t, press),) = spy.of("SWITCH_PRESS")
    assert press["on_target"] is False and press["used_fallback"] is False
    assert press["reason"] == "no_gaze"
    ((_k, _t, miss),) = spy.of("MISS_CLICK")
    assert miss["reason"] == "no_gaze"
    task.update(300 * MS, at(ON))
    task.update(340 * MS, at(ON, clicked=True))
    row = task.trials[0]
    assert (row.is_hit, row.clicks, row.click_errors) == (True, 2, 1)


def test_a_fallback_press_that_was_off_target_is_a_click_error():
    task, spy = make()
    task.update(0, at(OFF))
    task.update(50 * MS, at(OFF, valid=False, clicked=True))
    assert task.trials == []
    ((_k, _t, press),) = spy.of("SWITCH_PRESS")
    assert press["used_fallback"] is True and press["on_target"] is False
    assert "reason" not in press
    assert spy.of("MISS_CLICK")[0][2]["used_fallback"] is True


def test_a_press_with_an_invalid_pointer_and_no_history_has_no_gaze():
    task, spy = make()
    task.update(0, at(0.5, valid=False))
    task.update(30 * MS, at(0.5, valid=False, clicked=True))
    assert task.trials == []
    assert spy.of("SWITCH_PRESS")[0][2]["reason"] == "no_gaze"


# -- I5d: presses between trials are ignored -------------------------------------------------


def test_a_press_during_the_pause_between_trials_is_ignored_and_logged():
    task, spy = make(iti_ms=500)
    task.update(0, at(ON))
    task.update(40 * MS, at(ON, clicked=True))  # trial 0 hit; the ITI begins
    assert task.phase is Phase.ITI and len(spy.of("SWITCH_PRESS")) == 1
    task.update(100 * MS, at(0.5, clicked=True))
    task.update(300 * MS, at(0.5, clicked=True))
    ignored = spy.of("SWITCH_IGNORED")
    assert [p["phase"] for _k, _t, p in ignored] == ["iti", "iti"]
    assert len(spy.of("SWITCH_PRESS")) == 1 and task.trials[0].clicks == 1  # nothing was counted
    assert task.phase is Phase.ITI


def test_a_press_in_the_frame_the_pause_ends_still_belongs_to_the_pause():
    task, spy = make(iti_ms=100)
    task.update(0, at(ON))
    task.update(10 * MS, at(ON, clicked=True))  # hit; ITI until 110 ms
    task.update(120 * MS, at(0.5, clicked=True))  # the next trial starts in this frame
    assert task.phase is Phase.WAIT_INPUT
    assert [p["phase"] for _k, _t, p in spy.of("SWITCH_IGNORED")] == ["iti"]
    assert len(spy.of("SWITCH_PRESS")) == 1  # the new trial has none yet


def test_a_press_before_the_first_trial_is_ignored():
    task, spy = make(preroll_ms=500)
    task.update(0, at(ON, clicked=True))  # during the pre-roll
    task.update(200 * MS, at(ON, clicked=True))
    assert task.phase is Phase.READY
    assert [p["phase"] for _k, _t, p in spy.of("SWITCH_IGNORED")] == ["ready", "ready"]
    task.update(600 * MS, at(ON))  # the pre-roll is over: trial 0 is up
    assert task.phase is Phase.WAIT_INPUT and task.trials == []
    task.update(640 * MS, at(ON, clicked=True))
    assert task.trials[0].is_hit and task.trials[0].clicks == 1


def test_a_press_after_the_last_trial_is_ignored():
    task, spy = make(iti_ms=0)
    for i in range(3):
        task.update((i * 100) * MS, at(0.3 + 0.2 * i))
        task.update((i * 100 + 10) * MS, at(0.3 + 0.2 * i, clicked=True))
    task.update(400 * MS, at(0.5))
    assert task.is_done
    task.update(500 * MS, at(0.5, clicked=True))
    assert [p["phase"] for _k, _t, p in spy.of("SWITCH_IGNORED")][-1] == "done"


def test_ignore_press_logs_where_and_why():
    task, spy = make()
    task.ignore_press(5 * MS, "paused")
    task.ignore_press(6 * MS, "iti", at(0.4, clicked=True))
    (_k, t, first), (_k2, _t2, second) = spy.of("SWITCH_IGNORED")
    assert t == 5 * MS and first == {"phase": "paused"}
    assert second == {"phase": "iti", "x": 0.4, "y": 0.5}


# -- the refractory period is the switch's debounce (user decision of 2026-10-07) ----------------


def ignored(spy):
    return [(t, p) for _k, t, p in spy.of("SWITCH_IGNORED")]


def test_a_press_within_the_refractory_period_is_ignored_and_one_after_it_counts():
    task, spy = make(refractory_ms=500)
    task.update(0, at(ON))
    task.update(40 * MS, at(OFF, clicked=True))  # a Click error: counted
    task.update(340 * MS, at(ON, clicked=True))  # +0.3 s: a correct press, but too soon
    assert task.trials == [] and task.phase is Phase.WAIT_INPUT  # not a hit
    ((t, payload),) = ignored(spy)
    assert t == 340 * MS and payload["phase"] == "target" and payload["reason"] == "refractory"
    assert len(spy.of("SWITCH_PRESS")) == 1 and len(spy.of("MISS_CLICK")) == 1  # it was no press
    task.update(640 * MS, at(ON, clicked=True))  # +0.6 s: counted
    row = task.trials[0]
    assert (row.is_hit, row.clicks, row.click_errors, row.attempts) == (True, 2, 1, 2)
    assert len(ignored(spy)) == 1


def test_the_ignored_press_is_neither_a_click_nor_a_click_error():
    task, spy = make(refractory_ms=500)
    task.update(0, at(ON))
    task.update(10 * MS, at(OFF, clicked=True))  # counted, an error
    for t in (100, 200, 300):  # three hasty presses, all off target
        task.update(t * MS, at(OFF, clicked=True))
    task.update(1000 * MS - 1, at(ON))  # the trial times out with nothing else counted
    task.update(1010 * MS, at(ON))
    row = task.trials[0]
    assert row.is_timeout
    assert (row.clicks, row.click_errors, row.attempts) == (1, 1, 1)
    assert [p["reason"] for _t, p in ignored(spy)] == ["refractory"] * 3


def test_a_correct_press_0_3_s_after_a_click_error_is_ignored():
    task, spy = make(refractory_ms=500)
    task.update(0, at(OFF))
    task.update(100 * MS, at(OFF, clicked=True))  # the Click error
    task.update(400 * MS, at(ON, clicked=True))  # looks at the target and presses: too soon
    assert task.trials == []
    assert [p["reason"] for _t, p in ignored(spy)] == ["refractory"]
    task.update(700 * MS, at(ON, clicked=True))  # 0.6 s after the error: counts
    assert task.trials[0].is_hit and (task.trials[0].clicks, task.trials[0].click_errors) == (2, 1)


def test_a_press_exactly_one_refractory_period_after_the_last_counts():
    task, _spy = make(refractory_ms=500)
    task.update(0, at(OFF))
    task.update(100 * MS, at(OFF, clicked=True))
    task.update(600 * MS, at(ON, clicked=True))  # +500 ms exactly
    assert task.trials[0].is_hit and task.trials[0].clicks == 2


def test_an_ignored_press_does_not_extend_the_refractory_period():
    task, spy = make(refractory_ms=500)
    task.update(0, at(OFF))
    task.update(100 * MS, at(OFF, clicked=True))  # counted; the window ends at 600 ms
    task.update(500 * MS, at(OFF, clicked=True))  # ignored
    task.update(650 * MS, at(ON, clicked=True))  # 550 ms after the counted one, 150 after the ignored
    assert task.trials[0].is_hit and task.trials[0].clicks == 2
    assert len(ignored(spy)) == 1


def test_the_refractory_period_restarts_with_each_trial():
    task, spy = make(refractory_ms=500, iti_ms=100)
    task.update(0, at(ON))
    task.update(40 * MS, at(ON, clicked=True))  # trial 0: a hit
    task.update(140 * MS, at(0.5))  # the pause is over: trial 1 is up
    task.update(160 * MS, at(0.5, clicked=True))  # 120 ms after the last press, but a new trial
    assert task.trials[1].is_hit and task.trials[1].clicks == 1
    assert ignored(spy) == []


def test_the_refractory_period_comes_from_the_dwell_selector_when_there_is_one():
    dwell = DwellSelector(DwellConfig(refractory_ms=400))
    task, spy = make("gaze_switch", dwell=dwell, refractory_ms=0)  # the config says 0; the selector wins
    task.update(0, at(OFF))
    task.update(50 * MS, at(OFF, clicked=True))
    task.update(300 * MS, at(ON, clicked=True))  # +250 ms < 400
    assert task.trials == [] and len(ignored(spy)) == 1
    task.update(460 * MS, at(ON, clicked=True))  # +410 ms
    assert task.trials[0].is_hit


def test_a_refractory_period_of_zero_debounces_nothing():
    task, spy = make(refractory_ms=0)
    task.update(0, at(OFF))
    for t in (10, 11, 12):
        task.update(t * MS, at(OFF, clicked=True))
    assert len(spy.of("SWITCH_PRESS")) == 3 and ignored(spy) == []


def test_a_bare_task_with_no_dwell_settings_is_not_debounced():
    spy = Spy()
    cfg = {"task": {"task_id": "fixed", "timeout_ms": 1000, "inter_trial_interval_ms": 200}}
    task = Fixed(cfg, 1000, 1000, recorder=spy, feedback=NullFeedback(), input_mode="gaze_switch")
    assert task.refractory_ns == 0
    task.update(0, at(OFF))
    task.update(10 * MS, at(OFF, clicked=True))
    task.update(20 * MS, at(ON, clicked=True))
    assert task.trials[0].is_hit


def test_the_refractory_period_does_not_touch_a_dwell_run():
    dwell = DwellSelector(DwellConfig(threshold_ms=100, refractory_ms=500))
    task, spy = make("eye", dwell=dwell, refractory_ms=500)
    for t in range(0, 400, 20):
        task.update(t * MS, at(ON))
        if task.trials:
            break
    assert task.trials[0].is_hit and ignored(spy) == []


# -- trials.csv -----------------------------------------------------------------------------


def test_the_click_counts_reach_trials_csv(tmp_path):
    task, _spy = make()
    task.update(0, at(OFF))
    task.update(20 * MS, at(OFF, clicked=True))
    task.update(40 * MS, at(ON, clicked=True))
    meta = SessionMetadata(subject_id="P001", session_id="switch_rows", started_ns=0)
    with SessionRecorder(meta, output_root=tmp_path) as recorder:
        path = recorder.write_trials(task.trials)
    with path.open(encoding="utf-8") as fh:
        (row,) = list(csv.DictReader(fh))
    assert (row["clicks"], row["click_errors"], row["attempts"], row["is_hit"]) == ("2", "1", "2", "1")
