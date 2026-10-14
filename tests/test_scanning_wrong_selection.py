"""SPEC-scanning-search-cues.md 4.3 step 4 and 4.6, acceptance C7 (user decisions of 2026-10-14): in Match the
sample a completed dwell on an icon that is not the target (Dwell), or a switch press while the pointer is on
one (Switch), is a wrong selection.

It is counted per trial (``wrong_selections``, ``wrong_selection_shapes``) and announced by a
``WRONG_SELECTION`` event, and nothing else happens: no feedback, nothing drawn, the trial goes on until the
target or the timeout. After a dwell's the icon has to be left before it can count again; a press counts
each time. A press stays a ``MISS_CLICK`` and a click error. Pop-out has none. The helpers are those of
``test_scanning_search.py``; the prompts are never read from the repository's assets."""

from __future__ import annotations

import pytest

from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig
from src.tasks.base_task import Phase
from src.tasks.search_cues import SHAPE_NAMES, WrongIconDwell
from tests.test_scanning_search import CENTRE, DWELL_MS, MS, at_slot, make, run

FIELD = 1500  # when the first field appears (the end of the sample)


def _field_task(**kwargs):
    """A Match the sample task whose first field is up, and the slots of its target and two wrong icons."""
    task, spy, feedback = make(**kwargs)
    run(task, CENTRE, 0, FIELD + 10)
    target = task.targets[0].slot_index
    return task, spy, feedback, target, (target + 1) % 4, (target + 2) % 4


def _wrong_events(spy):
    return [(e[1] // MS, e[2]) for e in spy.of("WRONG_SELECTION")]


# -- the rule: a completed dwell, then leave it ------------------------------------------------------------


def test_a_completed_dwell_on_a_wrong_icon_is_counted_with_its_slot_shape_and_time():
    task, spy, _fb, _target, wrong, _other = _field_task(trials=2)
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS + 40)
    shape = SHAPE_NAMES[task.trial_field_shapes[0][wrong]]
    assert _wrong_events(spy) == [(1520 + DWELL_MS, {"trial": 0, "slot": wrong, "shape": shape})]
    assert task._current.wrong_selections == 1 and task._current.wrong_selection_shapes == shape


def test_it_needs_the_target_dwells_threshold_not_less():
    task, spy, _fb, _target, wrong, _other = _field_task()
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS - 10)  # 190 ms of a 200 ms dwell
    assert not spy.of("WRONG_SELECTION") and task._current.wrong_selections == 0
    task.update((1520 + DWELL_MS) * MS, at_slot(task, wrong))
    assert len(spy.of("WRONG_SELECTION")) == 1


def test_nothing_changes_on_screen_and_nothing_plays_and_the_trial_goes_on():
    task, spy, feedback, target, wrong, _other = _field_task(trials=2)
    scene_before = task.scene_spec()
    heard = len(feedback.events)
    frames = run(task, at_slot(task, wrong), 1520, 1520 + 3 * DWELL_MS)
    assert len(spy.of("WRONG_SELECTION")) == 1
    assert all(f.phase is Phase.WAIT_INPUT and f.selectable and not f.on_target for f in frames)
    assert all(f.dwell_progress == 0.0 for f in frames)  # no ring and no trace on the wrong icon
    assert task.scene_spec() == scene_before
    assert feedback.events[heard:] == []  # no hit, no miss, no progress, no burst
    assert task.trials == [] and spy.of("TARGET_SHOWN") and not spy.of("MISS_CLICK")
    # It carries on to the target: a hit, with the wrong selection kept in the row.
    run(task, at_slot(task, target), 1520 + 3 * DWELL_MS, 1520 + 3 * DWELL_MS + DWELL_MS + 40)
    trial = task.trials[0]
    assert trial.is_hit and trial.wrong_selections == 1 and trial.attempts == 1 and trial.click_errors == 0
    assert trial.as_row()["wrong_selections"] == 1


def test_the_trial_goes_on_to_the_timeout_too():
    task, spy, _fb, _target, wrong, _other = _field_task()
    run(task, at_slot(task, wrong), 1520, FIELD + 3000 + 40)
    assert spy.of("TIMEOUT") and len(spy.of("WRONG_SELECTION")) >= 1
    assert task.trials[0].is_timeout and task.trials[0].wrong_selections >= 1


def test_one_long_look_is_one_wrong_selection_not_one_per_dwell():
    task, spy, _fb, _target, wrong, _other = _field_task()
    run(task, at_slot(task, wrong), 1520, 1520 + 6 * DWELL_MS)
    assert len(spy.of("WRONG_SELECTION")) == 1


def test_a_glance_away_inside_the_hold_grace_does_not_free_the_icon():
    task, spy, _fb, _target, wrong, _other = _field_task()
    t = 1520
    run(task, at_slot(task, wrong), t, t + DWELL_MS + 10)
    run(task, CENTRE, t + DWELL_MS + 10, t + DWELL_MS + 70)  # 60 ms away, grace is 120
    run(task, at_slot(task, wrong), t + DWELL_MS + 70, t + 6 * DWELL_MS)
    assert len(spy.of("WRONG_SELECTION")) == 1


def test_leaving_the_icon_frees_it_and_a_second_full_dwell_counts_again():
    task, spy, _fb, _target, wrong, _other = _field_task()
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS + 10)
    assert len(spy.of("WRONG_SELECTION")) == 1
    run(task, CENTRE, 1740, 1900)  # away for 160 ms: past the grace
    run(task, at_slot(task, wrong), 1900, 1900 + DWELL_MS - 10)
    assert len(spy.of("WRONG_SELECTION")) == 1  # not yet a full dwell
    task.update((1900 + DWELL_MS) * MS, at_slot(task, wrong))
    events = _wrong_events(spy)
    assert [t for t, _p in events] == [1520 + DWELL_MS, 1900 + DWELL_MS]
    assert task._current.wrong_selections == 2


def test_the_shapes_are_listed_in_the_order_they_happened():
    task, spy, _fb, _target, a, b = _field_task()
    run(task, at_slot(task, a), 1520, 1520 + DWELL_MS + 10)
    run(task, CENTRE, 1740, 1900)
    run(task, at_slot(task, b), 1900, 1900 + DWELL_MS + 10)
    run(task, CENTRE, 2120, 2300)
    run(task, at_slot(task, a), 2300, 2300 + DWELL_MS + 10)
    names = [SHAPE_NAMES[task.trial_field_shapes[0][s]] for s in (a, b, a)]
    assert task._current.wrong_selection_shapes == ";".join(names)
    assert [p["shape"] for _t, p in _wrong_events(spy)] == names


def test_moving_from_one_wrong_icon_to_another_starts_the_dwell_over():
    task, spy, _fb, _target, a, b = _field_task()
    run(task, at_slot(task, a), 1520, 1520 + 150)
    run(task, at_slot(task, b), 1670, 1670 + 150)  # 150 ms on b: not a dwell
    run(task, at_slot(task, a), 1820, 1820 + 150)
    assert not spy.of("WRONG_SELECTION")
    run(task, at_slot(task, b), 1970, 1970 + DWELL_MS + 10)
    assert [p["slot"] for _t, p in _wrong_events(spy)] == [b]


def test_looking_at_the_target_or_nowhere_counts_nothing():
    task, spy, _fb, _target, _a, _b = _field_task()
    run(task, CENTRE, 1520, 1520 + 3000 - 100)
    assert not spy.of("WRONG_SELECTION") and task._current.wrong_selections == 0
    assert task._current.wrong_selection_shapes == ""


def test_a_blink_neither_counts_nor_frees_the_icon():
    task, spy, _fb, _target, wrong, _other = _field_task()
    blink = Pointer(x=0.5, y=0.5, valid=False, clicked=False)
    run(task, at_slot(task, wrong), 1520, 1520 + 100)
    run(task, blink, 1620, 1620 + 100)  # inside the grace: the dwell holds
    run(task, at_slot(task, wrong), 1720, 1720 + 120)
    assert len(spy.of("WRONG_SELECTION")) == 1  # 100 + 100 + 120 ms of one look
    run(task, blink, 1840, 2400)  # a long blink is not a look away
    run(task, at_slot(task, wrong), 2400, 3000)
    assert len(spy.of("WRONG_SELECTION")) == 1  # still the same, unfreed, look


def test_the_dwells_refractory_applies_after_a_wrong_selection():
    task, spy, _fb, _target, a, b = _field_task(refractory_ms=500)
    run(task, at_slot(task, a), 1520, 1520 + DWELL_MS + 10)  # counted at 1720
    run(task, at_slot(task, b), 1730, 2210)  # b at once: nothing accumulates before 1720 + 500 ms
    assert len(spy.of("WRONG_SELECTION")) == 1
    run(task, at_slot(task, b), 2210, 2700)
    assert [(t, p["slot"]) for t, p in _wrong_events(spy)] == [(1720, a), (2420, b)]


def test_each_trial_counts_for_itself():
    task, spy, _fb, target, wrong, _other = _field_task(trials=2)
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS + 10)
    run(task, at_slot(task, target), 1740, 1740 + DWELL_MS + 40)
    first = task.trials[0]
    assert first.is_hit and first.wrong_selections == 1
    end = first.t_end_ns // MS
    run(task, CENTRE, end + 10, end + 500 + 1500 + 20)  # the second trial's sample, then its field
    assert task._current.trial_id == 1 and task._current.wrong_selections == 0
    second_wrong = (task.targets[1].slot_index + 1) % 4
    start = end + 500 + 1500 + 20
    run(task, at_slot(task, second_wrong), start, start + DWELL_MS + 10)
    assert task._current.wrong_selections == 1
    assert [p["trial"] for _t, p in _wrong_events(spy)] == [0, 1]


def test_a_dwell_already_running_on_a_wrong_icon_when_the_field_appears_counts_from_that_frame():
    task, spy, _fb = make(trials=1)
    run(task, CENTRE, 0, FIELD)
    wrong = (task.targets[0].slot_index + 1) % 4
    run(task, at_slot(task, wrong), FIELD, FIELD + DWELL_MS + 10)  # the field's first frame is on the icon
    assert [t for t, _p in _wrong_events(spy)] == [FIELD + DWELL_MS]


# -- where it does not apply --------------------------------------------------------------------------------


def test_pop_out_has_no_wrong_selections_at_all():
    task, spy, _fb = make(trials=1, mode="pop_out")
    run(task, CENTRE, 0, 20)
    wrong = (task.targets[0].slot_index + 1) % 4
    run(task, at_slot(task, wrong), 20, 20 + 6 * DWELL_MS)
    assert not spy.of("WRONG_SELECTION")
    assert task._current.wrong_selections is None and task._current.wrong_selection_shapes == ""
    row = task._current.as_row()
    assert row["wrong_selections"] == "" and row["wrong_selection_shapes"] == ""


def _switch_field_task(**kwargs):
    """A Match the sample task with a Switch whose first field is up, and the slots of its target and two wrong icons."""
    task, spy, feedback = make(input_mode="gaze_switch", **kwargs)
    run(task, CENTRE, 0, FIELD + 10)
    target = task.targets[0].slot_index
    return task, spy, feedback, target, (target + 1) % 4, (target + 2) % 4


def test_a_switch_selection_counts_from_zero_not_blank_and_a_long_look_alone_counts_nothing():
    task, spy, _fb, _target, wrong, _other = _switch_field_task()
    assert task._current.wrong_selections == 0 and task._current.as_row()["wrong_selections"] == 0
    run(task, at_slot(task, wrong), 1520, 1520 + 6 * DWELL_MS)  # a long look, no press
    assert not spy.of("WRONG_SELECTION") and task._current.wrong_selections == 0
    assert task._current.wrong_selection_shapes == ""


def test_a_press_on_a_wrong_icon_is_a_wrong_selection_and_still_a_click_error():
    task, spy, feedback, _target, wrong, _other = _switch_field_task(trials=2)
    run(task, at_slot(task, wrong), 1520, 1700)
    heard = len(feedback.events)
    task.update(1700 * MS, at_slot(task, wrong, clicked=True))
    shape = SHAPE_NAMES[task.trial_field_shapes[0][wrong]]
    assert _wrong_events(spy) == [(1700, {"trial": 0, "slot": wrong, "shape": shape})]
    trial = task._current
    assert (trial.wrong_selections, trial.wrong_selection_shapes) == (1, shape)
    # As ever: a miss, a click error, an attempt; and nothing else, the trial goes on.
    assert spy.of("MISS_CLICK") and (trial.clicks, trial.click_errors, trial.attempts) == (1, 1, 1)
    assert task.trials == [] and task.phase is Phase.WAIT_INPUT
    assert feedback.events[heard:] == []  # no cue: a press that misses plays nothing, as today


def test_a_press_on_no_icon_is_a_click_error_but_not_a_wrong_selection():
    task, spy, _fb, _target, _a, _b = _switch_field_task()
    task.update(1700 * MS, Pointer(x=0.5, y=0.5, valid=True, clicked=True))  # the middle of the field
    assert spy.of("MISS_CLICK") and task._current.click_errors == 1
    assert not spy.of("WRONG_SELECTION") and task._current.wrong_selections == 0


def test_a_press_on_the_target_is_a_hit_with_no_wrong_selection():
    task, spy, _fb, target, _a, _b = _switch_field_task()
    task.update(1700 * MS, at_slot(task, target, clicked=True))
    assert task.trials[0].is_hit and task.trials[0].wrong_selections == 0
    assert not spy.of("WRONG_SELECTION")


def test_every_wrong_press_counts_and_the_shapes_are_in_order():
    task, spy, _fb, target, a, b = _switch_field_task()
    for t, slot in ((1700, a), (1800, b), (1900, a)):
        task.update(t * MS, at_slot(task, slot, clicked=True))
    names = [SHAPE_NAMES[task.trial_field_shapes[0][s]] for s in (a, b, a)]
    assert task._current.wrong_selections == 3 and task._current.wrong_selection_shapes == ";".join(names)
    assert [p["shape"] for _t, p in _wrong_events(spy)] == names
    task.update(2000 * MS, at_slot(task, target, clicked=True))  # then the target
    assert task.trials[0].is_hit and task.trials[0].wrong_selections == 3 and task.trials[0].click_errors == 3


def test_a_press_the_refractory_ignores_is_not_counted():
    task, spy, _fb, _target, wrong, _other = _switch_field_task(refractory_ms=500)
    task.update(1700 * MS, at_slot(task, wrong, clicked=True))
    task.update(1800 * MS, at_slot(task, wrong, clicked=True))  # too soon after the last counted one
    assert len(spy.of("WRONG_SELECTION")) == 1 and spy.of("SWITCH_IGNORED")
    task.update(2300 * MS, at_slot(task, wrong, clicked=True))  # past it
    assert len(spy.of("WRONG_SELECTION")) == 2


def test_a_press_in_a_blink_is_judged_where_the_pointer_last_was():
    task, spy, _fb, _target, wrong, _other = _switch_field_task()
    run(task, at_slot(task, wrong), 1520, 1700)
    task.update(1780 * MS, Pointer(x=0.5, y=0.5, valid=False, clicked=True))  # 80 ms after the last valid look
    assert [p["slot"] for _t, p in _wrong_events(spy)] == [wrong]


def test_a_press_with_no_gaze_to_judge_it_by_is_not_a_wrong_selection():
    task, spy, _fb, _target, wrong, _other = _switch_field_task()
    run(task, at_slot(task, wrong), 1520, 1700)
    task.update(2200 * MS, Pointer(x=0.5, y=0.5, valid=False, clicked=True))  # the last valid look is 500 ms old
    assert spy.of("MISS_CLICK") and not spy.of("WRONG_SELECTION") and task._current.wrong_selections == 0


def test_a_press_before_the_field_is_ignored_not_counted():
    task, spy, _fb = make(input_mode="gaze_switch", trials=1)
    task.update(0, at_slot(task, 0, clicked=True))  # in the sample
    assert spy.of("SWITCH_IGNORED") and not spy.of("WRONG_SELECTION")


def test_pop_out_with_a_switch_has_no_wrong_selections():
    task, spy, _fb = make(trials=1, mode="pop_out", input_mode="gaze_switch")
    run(task, CENTRE, 0, 20)
    wrong = (task.targets[0].slot_index + 1) % 4
    task.update(30 * MS, at_slot(task, wrong, clicked=True))
    assert spy.of("MISS_CLICK") and not spy.of("WRONG_SELECTION")
    assert task._current.wrong_selections is None and task._current.as_row()["wrong_selections"] == ""


def test_a_mouse_pointer_with_dwell_counts_like_gaze():
    task, spy, _fb, _target, wrong, _other = _field_task(input_mode="mouse_dwell")
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS + 10)
    assert len(spy.of("WRONG_SELECTION")) == 1


def test_a_trial_dropped_by_a_pause_starts_its_count_over():
    task, spy, _fb, target, wrong, _other = _field_task()
    run(task, at_slot(task, wrong), 1520, 1520 + DWELL_MS + 10)
    assert task._current.wrong_selections == 1
    task.pause(1800 * MS)
    task.resume(2000 * MS)
    run(task, CENTRE, 2010, 2010 + 1500 + 20)  # the sample again, then the field
    assert task._current.wrong_selections == 0 and task._current.wrong_selection_shapes == ""
    run(task, at_slot(task, target), 3540, 3540 + DWELL_MS + 40)
    assert task.trials[0].is_hit and task.trials[0].wrong_selections == 0


# -- the helper on its own ----------------------------------------------------------------------------------


def _helper() -> WrongIconDwell:
    return WrongIconDwell(DwellConfig(threshold_ms=100.0, refractory_ms=0.0, hold_grace_ms=50.0))


def test_the_helper_reports_the_slot_once_and_not_for_the_target():
    dwell = _helper()
    found = [dwell.update(t * MS, True, 2, target_slot=1) for t in range(0, 300, 10)]
    assert [f for f in found if f is not None] == [2] and found[10] == 2
    other = _helper()
    assert all(other.update(t * MS, True, 1, target_slot=1) is None for t in range(0, 400, 10))  # the target
    assert all(other.update(t * MS, True, -1, target_slot=1) is None for t in range(400, 800, 10))  # nowhere
    assert all(other.update(t * MS, False, 2, target_slot=1) is None for t in range(800, 1200, 10))  # no gaze


@pytest.mark.parametrize("ms_away, counts_again", [(40, False), (60, True)])
def test_the_hold_grace_is_how_long_the_icon_must_be_left(ms_away, counts_again):
    dwell = _helper()
    for t in range(0, 110, 10):
        dwell.update(t * MS, True, 2, target_slot=1)  # counted at 100 ms
    t = 110
    for _ in range(ms_away // 10):
        dwell.update(t * MS, True, -1, target_slot=1)
        t += 10
    again = [dwell.update((t + k) * MS, True, 2, target_slot=1) for k in range(0, 300, 10)]
    assert (2 in again) is counts_again
