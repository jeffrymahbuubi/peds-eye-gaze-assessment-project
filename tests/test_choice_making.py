"""SPEC-scene-cause-effect-task.md step 3, engine side: the Choice-making task's trial flow
(4.3), multi-button selection (4.1, H5), prompt and effect phases, events and trial fields (4.9).

Acceptance covered here: A2 (the order, through the task), A3 (selection blocked while the
prompt plays, RT from its end), A4 (a wrong button is a MISS_CLICK, a hit plays the right effect,
a timeout plays the modelled one), A5 (the scene is idle again before the next prompt), A8
(pause stops prompt timing and effects; resume continues them). No Qt: the task is driven one
frame at a time. The prompt audio does not exist in the repository yet, so unless a test points
``assets_root`` at a temp folder of its own, every prompt falls back to ``DEFAULT_PROMPT_MS``."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.feedback import NullFeedback
from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig, DwellSelector
from src.tasks.base_task import Phase
from src.tasks.choice_layout import DEFAULT_PROMPT_MS, OBJECTS, button_centre_norm, side_of
from src.tasks.choice_making import ChoiceMakingTask

MS = 1_000_000
PROMPT = DEFAULT_PROMPT_MS
DWELL_MS = 200
POST = 1000
SCENE = (0.5, 0.5)  # the middle of the scene: no button
# A folder that never exists: whatever assets the repository gains later must not change these tests.
NO_ASSETS = Path(__file__).parent / "_no_such_assets"


class AudioFeedback(NullFeedback):
    """A bus that also records the audio hooks (``NullFeedback`` itself ignores them)."""

    def __init__(self) -> None:
        super().__init__()
        self.audio: list[tuple] = []

    def on_prompt(self, object_id):
        self.audio.append(("prompt", object_id))

    def on_effect(self, object_id, modelled):
        self.audio.append(("effect", object_id, modelled))

    def on_stop_audio(self):
        self.audio.append(("stop",))


class Spy:
    """Recorder double: the events a task emits."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []

    def record_event(self, kind, t_ns, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message) -> None: ...

    def of(self, kind):
        return [e for e in self.events if e[0] == kind]


def make(
    *, trials=3, timeout_ms=3000, mode="eye", dwell_ms=DWELL_MS, visual_cue=False, gap_px=None,
    post_effect_ms=POST, seed=0, extra=None, assets_root=NO_ASSETS, feedback=None,
):
    spy = Spy()
    feedback = NullFeedback() if feedback is None else feedback
    task_cfg = {
        "task_id": "choice_making", "trials": trials, "timeout_ms": timeout_ms,
        "post_effect_ms": post_effect_ms, "visual_cue": visual_cue, "grid": {"gap_px": gap_px},
        **(extra or {}),
    }
    cfg = {"task": task_cfg, "dwell": {"refractory_ms": 0}}
    switch = mode in ("gaze_switch", "switch")
    dwell = None if switch else DwellSelector(DwellConfig(threshold_ms=dwell_ms, refractory_ms=0))
    task = ChoiceMakingTask(
        cfg, 1920, 1080, recorder=spy, feedback=feedback, dwell=dwell, input_mode=mode, seed=seed
    )
    task.assets_root = assets_root  # read lazily, at the first prompt
    return task, spy, feedback


def at(slot_or_xy, *, valid=True, clicked=False):
    x, y = button_centre_norm(slot_or_xy) if isinstance(slot_or_xy, int) else slot_or_xy
    return Pointer(x=x, y=y, valid=valid, clicked=clicked)


def run(task, pointer, start_ms, end_ms, step_ms=10):
    """Update from ``start_ms`` up to (not including) ``end_ms``; the last FrameResult."""
    result = None
    for t in range(start_ms, end_ms, step_ms):
        result = task.update(t * MS, pointer)
    return result


def slot_of(task, trial=0):
    return task.targets[trial].slot_index


def other_slot(task, trial=0):
    return (slot_of(task, trial) + 1) % 8


# -- the order, through the task (A2) -------------------------------------------------------------


def test_16_trials_are_buttons_with_each_object_twice_and_never_twice_in_a_row():
    task, _spy, _fb = make(trials=16)
    slots = [t.slot_index for t in task.targets]
    assert sorted(slots) == sorted(list(range(8)) * 2)
    assert all(a != b for a, b in zip(slots, slots[1:], strict=False))
    assert sum(1 for s in slots if s < 4) == 8
    for target in task.targets:  # a target is its button: centre of the cell, no configured radius
        assert (target.x_norm, target.y_norm) == button_centre_norm(target.slot_index)
        assert target.radius_px == 0.0


def test_the_order_follows_the_seed():
    a = [t.slot_index for t in make(trials=16, seed=3)[0].targets]
    b = [t.slot_index for t in make(trials=16, seed=3)[0].targets]
    c = [t.slot_index for t in make(trials=16, seed=4)[0].targets]
    assert a == b and a != c


@pytest.mark.parametrize("trials", [1, 5, 9, 23])
def test_any_trial_count_is_built(trials):
    task, _spy, _fb = make(trials=trials)
    assert len(task.targets) == trials


# -- A3: selection is blocked while the prompt plays; RT counts from its end ------------------------


def test_nothing_can_be_selected_while_the_prompt_plays():
    task, spy, _fb = make()
    on = at(slot_of(task))
    frames = [task.update(t * MS, on) for t in range(0, PROMPT, 10)]
    assert all(f.phase is Phase.WAIT_INPUT and not f.selectable for f in frames)
    assert not spy.of("HIT") and not spy.of("MISS_CLICK") and not spy.of("PROMPT_END")
    assert [e[1] for e in spy.of("PROMPT_START")] == [0]
    assert spy.of("PROMPT_START")[0][2]["object"] == OBJECTS[slot_of(task)].id


def test_is_selectable_is_false_until_the_prompt_has_ended():
    task, _spy, _fb = make()
    task.update(0, at(SCENE))
    target = task.targets[0]
    assert not task.is_selectable(target, 0) and not task.is_selectable(target, (PROMPT - 1) * MS)
    assert task.is_selectable(target, PROMPT * MS) and task.is_selectable(target, 10 * PROMPT * MS)


def test_the_response_clock_starts_at_the_end_of_the_prompt():
    task, spy, _fb = make()
    on = at(slot_of(task))
    # Looked at from the start of the trial: the dwell only starts once the prompt is over.
    run(task, on, 0, PROMPT + DWELL_MS + 10)
    assert [e[1] for e in spy.of("PROMPT_END")] == [PROMPT * MS]
    assert spy.of("PROMPT_END")[0][2]["object"] == OBJECTS[slot_of(task)].id
    trial = task.trials[0]
    assert trial.is_hit and trial.t_click_ns == (PROMPT + DWELL_MS) * MS
    assert trial.t_selectable_start_ns == PROMPT * MS
    assert trial.rt_ms == pytest.approx(DWELL_MS)
    assert trial.reaction_time_from_selectable_ms == pytest.approx(DWELL_MS)
    assert trial.reaction_time_ms == pytest.approx(PROMPT + DWELL_MS)  # from the trial start


def test_the_timeout_counts_from_the_end_of_the_prompt():
    task, spy, _fb = make(timeout_ms=1000)
    run(task, at(SCENE), 0, PROMPT + 990)
    assert not spy.of("TIMEOUT")  # a timeout from the trial start would have fired at 1000 ms
    run(task, at(SCENE), PROMPT + 990, PROMPT + 1010)
    assert [e[1] for e in spy.of("TIMEOUT")] == [(PROMPT + 1000) * MS]
    trial = task.trials[0]
    assert trial.is_timeout and not trial.is_hit and trial.rt_ms is None
    assert trial.selected_object == ""


def test_a_press_during_the_prompt_is_logged_and_counts_for_nothing():
    task, spy, _fb = make(mode="gaze_switch")
    on = at(slot_of(task))
    task.update(0, on)
    task.update(500 * MS, at(slot_of(task), clicked=True))
    ignored = spy.of("SWITCH_IGNORED")
    assert [e[2]["phase"] for e in ignored] == ["prompt"]
    assert not spy.of("SWITCH_PRESS") and not spy.of("MISS_CLICK") and not spy.of("HIT")
    task.update(PROMPT * MS, on)
    task.update((PROMPT + 500) * MS, at(slot_of(task), clicked=True))
    trial = task.trials[0]
    assert trial.is_hit and trial.clicks == 1 and trial.click_errors == 0
    assert trial.rt_ms == pytest.approx(500)


# -- A4: any button can be selected (H5) ---------------------------------------------------------------


def test_a_completed_dwell_on_a_wrong_button_is_a_miss_click_and_the_trial_goes_on():
    task, spy, fb = make()
    wrong = other_slot(task)
    result = run(task, at(wrong), 0, PROMPT + DWELL_MS + 10)
    misses = spy.of("MISS_CLICK")
    assert len(misses) == 1 and misses[0][1] == (PROMPT + DWELL_MS) * MS
    payload = misses[0][2]
    assert payload["selected_slot"] == wrong and payload["selected_object"] == OBJECTS[wrong].id
    assert result.phase is Phase.WAIT_INPUT and not task.trials and not spy.of("HIT")
    assert not spy.of("EFFECT_START")  # H6: no effect for the wrong object
    assert task.scene_spec()["effect"] is None
    assert [e[0] for e in fb.events].count("miss") == 1  # the generic miss cue
    # ... and the trial still ends on the right button.
    run(task, at(slot_of(task)), PROMPT + DWELL_MS + 10, PROMPT + 2 * DWELL_MS + 40)
    trial = task.trials[0]
    assert trial.is_hit and trial.attempts == 2
    assert trial.selected_object == OBJECTS[slot_of(task)].id


def test_looking_at_the_scene_a_gap_or_nowhere_selects_nothing():
    task, spy, _fb = make(gap_px=82.0, timeout_ms=10_000)
    run(task, at(SCENE), 0, PROMPT + 1000)
    gap = (button_centre_norm(0)[0], 2 / 5)  # between buttons 0 and 1: the dead zone of a wide gap
    run(task, at(gap), PROMPT + 1000, PROMPT + 2000)
    run(task, at(slot_of(task), valid=False), PROMPT + 2000, PROMPT + 3000)  # blinking
    assert not spy.of("MISS_CLICK") and not spy.of("HIT") and not task.trials


def test_moving_to_another_button_starts_the_dwell_over():
    task, spy, _fb = make()
    wrong = other_slot(task)
    run(task, at(wrong), 0, PROMPT + 150)
    result = run(task, at(slot_of(task)), PROMPT + 150, PROMPT + 300)  # 150 ms on each
    assert not spy.of("HIT") and not spy.of("MISS_CLICK")
    assert 0 < result.dwell_progress < 1
    run(task, at(slot_of(task)), PROMPT + 300, PROMPT + 400)
    assert task.trials[0].is_hit


def test_a_wrong_switch_press_is_a_miss_click_with_the_selected_object():
    task, spy, fb = make(mode="gaze_switch")
    wrong = other_slot(task)
    task.update(0, at(wrong))
    task.update(PROMPT * MS, at(wrong))
    task.update((PROMPT + 100) * MS, at(wrong, clicked=True))
    miss = spy.of("MISS_CLICK")[0]
    assert miss[2]["selected_slot"] == wrong and miss[2]["selected_object"] == OBJECTS[wrong].id
    assert not task.trials and [e[0] for e in fb.events].count("miss") == 1
    task.update((PROMPT + 400) * MS, at(slot_of(task), clicked=True))
    trial = task.trials[0]
    assert trial.is_hit and trial.attempts == 2
    assert (trial.clicks, trial.click_errors) == (2, 1)


def test_a_switch_press_off_every_button_is_a_miss_click_with_no_object():
    task, spy, _fb = make(mode="gaze_switch")
    task.update(0, at(SCENE))
    task.update(PROMPT * MS, at(SCENE))
    task.update((PROMPT + 100) * MS, at(SCENE, clicked=True))
    payload = spy.of("MISS_CLICK")[0][2]
    assert payload["selected_slot"] == -1 and payload["selected_object"] is None
    assert not task.trials


def test_a_hit_plays_the_prompted_objects_effect_and_no_generic_hit_cue():
    task, spy, fb = make()
    slot = slot_of(task)
    obj = OBJECTS[slot]
    run(task, at(slot), 0, PROMPT + DWELL_MS + 10)
    hit_ns = (PROMPT + DWELL_MS) * MS
    assert [e[1] for e in spy.of("HIT")] == [hit_ns]
    start = spy.of("EFFECT_START")[0]
    assert start[1] == hit_ns
    assert start[2]["object"] == obj.id and start[2]["modelled"] is False
    assert start[2]["duration_ms"] == obj.effect_ms and start[2]["trial"] == 0
    assert task.phase is Phase.RESULT
    effect = task.scene_spec()["effect"]
    assert effect["object"] == obj.id and effect["modelled"] is False
    assert effect["t_start"] == hit_ns and effect["duration_ms"] == obj.effect_ms
    assert not {"hit", "miss"} & {e[0] for e in fb.events}  # the effect is the reward


def test_a_timeout_plays_the_effect_once_as_a_model():
    task, spy, fb = make(timeout_ms=1000)
    obj = OBJECTS[slot_of(task)]
    run(task, at(SCENE), 0, PROMPT + 1010)
    start = spy.of("EFFECT_START")[0]
    assert start[1] == (PROMPT + 1000) * MS
    assert start[2]["object"] == obj.id and start[2]["modelled"] is True
    assert task.phase is Phase.RESULT and task.scene_spec()["effect"]["modelled"] is True
    assert [e[0] for e in fb.events] == ["target_shown"]  # a model is not a miss


# -- A5: the scene is idle again before the next prompt ----------------------------------------------------


def test_the_effect_runs_its_duration_then_the_pause_then_the_next_prompt():
    task, spy, _fb = make()
    obj = OBJECTS[slot_of(task)]
    run(task, at(slot_of(task)), 0, PROMPT + DWELL_MS + 10)
    hit_ms = PROMPT + DWELL_MS
    end_ms = hit_ms + obj.effect_ms
    run(task, at(SCENE), hit_ms + 10, end_ms - 10)
    assert task.phase is Phase.RESULT and not spy.of("EFFECT_END")
    run(task, at(SCENE), end_ms - 10, end_ms + 10)
    assert [e[1] for e in spy.of("EFFECT_END")] == [end_ms * MS]
    assert spy.of("EFFECT_END")[0][2]["object"] == obj.id
    assert task.phase is Phase.ITI
    idle = task.scene_spec()
    assert idle["effect"] is None and idle["prompt_object"] is None
    run(task, at(SCENE), end_ms + 10, end_ms + POST - 10)
    assert len(spy.of("PROMPT_START")) == 1  # the next prompt waits for the pause
    run(task, at(SCENE), end_ms + POST - 10, end_ms + POST + 10)
    assert [e[1] for e in spy.of("PROMPT_START")][1] == (end_ms + POST) * MS


def test_a_whole_run_keeps_the_events_in_order_and_never_prompts_during_an_effect():
    task, spy, _fb = make(trials=4)
    result, frame_scenes = None, []
    for t in range(0, 120_000, 10):
        pointer = at(result.target.slot_index) if result is not None and result.target else at(SCENE)
        result = task.update(t * MS, pointer)
        if len(spy.of("PROMPT_START")) > len(frame_scenes):
            frame_scenes.append(task.scene_spec()["effect"])  # the scene at each prompt's start
        if task.is_done:
            break
    assert task.is_done and len(task.trials) == 4 and all(tr.is_hit for tr in task.trials)
    assert frame_scenes[1:] == [None] * 3  # A5: idle before every prompt after the first
    kinds = [e[0] for e in spy.events if e[0] in (
        "PROMPT_START", "PROMPT_END", "HIT", "EFFECT_START", "EFFECT_END")]
    assert kinds == ["PROMPT_START", "PROMPT_END", "HIT", "EFFECT_START", "EFFECT_END"] * 4
    starts, ends = spy.of("PROMPT_START"), spy.of("EFFECT_END")
    for effect_end, next_start in zip(ends, starts[1:], strict=False):
        assert next_start[1] - effect_end[1] == POST * MS
    # The run ends only after the last effect and its pause.
    assert spy.events[-1][0] == "EFFECT_END"
    for trial, effect in zip(task.trials, spy.of("EFFECT_START"), strict=True):
        assert effect[2]["object"] == trial.prompt_object


def test_the_trial_record_carries_the_prompt_the_side_and_the_selected_object():
    task, _spy, _fb = make(trials=2)
    run(task, at(slot_of(task)), 0, PROMPT + DWELL_MS + 10)
    trial = task.trials[0]
    obj = OBJECTS[slot_of(task)]
    assert (trial.prompt_object, trial.button_side) == (obj.id, side_of(obj.slot))
    assert trial.selected_object == obj.id and trial.slot_index == obj.slot
    assert (trial.target_x, trial.target_y) == button_centre_norm(obj.slot)
    row = trial.as_row()
    assert row["prompt_object"] == obj.id and row["button_side"] == side_of(obj.slot)
    assert row["selected_object"] == obj.id and row["rt_ms"] == pytest.approx(DWELL_MS)


# -- skipping ----------------------------------------------------------------------------------------------


def test_a_skipped_trial_plays_no_effect_and_waits_only_the_pause():
    task, spy, _fb = make()
    task.update(0, at(SCENE))
    assert task.skip_trial(500 * MS)
    assert spy.of("SKIPPED") and not spy.of("EFFECT_START")
    trial = task.trials[0]
    assert trial.is_skipped and trial.prompt_object and trial.selected_object == ""
    assert task.phase is Phase.ITI and task.scene_spec()["prompt_object"] is None
    run(task, at(SCENE), 510, 500 + POST + 10)
    assert [e[1] for e in spy.of("PROMPT_START")] == [0, (500 + POST) * MS]


# -- A8: pause stops prompt timing and effects; resume continues them ---------------------------------------


def test_pausing_during_the_prompt_stops_its_clock_and_resume_prompts_again():
    task, spy, _fb = make()
    slot = slot_of(task)
    run(task, at(SCENE), 0, 1000)
    assert task.pause(1000 * MS) is True
    assert spy.of("TRIAL_INTERRUPTED")
    for t in (2500, PROMPT + 500, 4500):  # past the prompt's end: nothing happens while paused
        assert task.update(t * MS, at(slot)).target is None
    assert not spy.of("PROMPT_END") and not spy.of("HIT") and len(spy.of("PROMPT_START")) == 1
    assert task.scene_spec()["prompt_object"] is None
    task.resume(5000 * MS)
    task.update(5000 * MS, at(SCENE))
    assert [e[1] for e in spy.of("PROMPT_START")] == [0, 5000 * MS]
    assert spy.of("PROMPT_START")[1][2]["object"] == OBJECTS[slot].id  # the same trial again
    run(task, at(SCENE), 5010, 5000 + PROMPT - 10)
    assert not spy.of("PROMPT_END")
    run(task, at(SCENE), 5000 + PROMPT - 10, 5000 + PROMPT + 10)
    assert [e[1] for e in spy.of("PROMPT_END")] == [(5000 + PROMPT) * MS]


def test_pausing_during_an_effect_freezes_it_and_resume_continues_it():
    task, spy, _fb = make()
    slot = slot_of(task)
    obj = OBJECTS[slot]
    run(task, at(slot), 0, PROMPT + DWELL_MS + 10)
    hit_ms = PROMPT + DWELL_MS
    run(task, at(SCENE), hit_ms + 10, hit_ms + 1000)
    assert task.pause((hit_ms + 1000) * MS) is False  # no trial in flight to interrupt
    assert task.scene_spec()["effect"]["elapsed_ms"] == pytest.approx(990, abs=10)
    task.update((hit_ms + 60_000) * MS, at(SCENE))  # a minute later, still paused
    assert not spy.of("EFFECT_END") and task.phase is Phase.RESULT
    resume_ms = hit_ms + 11_000  # paused for 10 s
    task.resume(resume_ms * MS)
    task.update(resume_ms * MS, at(SCENE))
    assert task.scene_spec()["effect"]["elapsed_ms"] == pytest.approx(1000, abs=10)
    new_end = hit_ms + obj.effect_ms + 10_000
    run(task, at(SCENE), resume_ms + 10, new_end - 10)
    assert not spy.of("EFFECT_END")
    run(task, at(SCENE), new_end - 10, new_end + 10)
    assert [e[1] for e in spy.of("EFFECT_END")] == [new_end * MS]
    run(task, at(SCENE), new_end + 10, new_end + POST + 10)
    assert [e[1] for e in spy.of("PROMPT_START")][1] == (new_end + POST) * MS


# -- what the renderer is given -----------------------------------------------------------------------------------


def test_scene_spec_describes_the_board_for_the_renderer():
    task, _spy, _fb = make()
    task.set_screen_size(1920, 1032)
    spec = task.scene_spec()
    assert spec["mode"] == "scene" and spec["theme"] == "park"
    assert [b["object"] for b in spec["buttons"]] == [o.id for o in OBJECTS]
    assert [b["slot"] for b in spec["buttons"]] == list(range(8))
    assert [b["label"] for b in spec["buttons"]][:2] == ["Balloons", "Rainbow"]
    x, y, w, h = spec["scene_rect"]
    assert (x, y, w, h) == pytest.approx((1920 / 7, 0.0, 1371.43, 1032), abs=0.01)
    for button in spec["buttons"]:  # no button overlaps the scene
        bx, by, bw, bh = button["rect"]
        assert bx + bw <= x or bx >= x + w
    assert spec["effect"] is None and spec["prompt_object"] is None
    assert spec["cue_slot"] == -1 and spec["hover_slot"] == -1
    assert task.layout_slots == [button_centre_norm(s) for s in range(8)]


def test_the_frame_marks_no_target_so_the_prompted_button_is_not_given_away():
    task, _spy, _fb = make()
    frame = task.update(0, at(slot_of(task)))
    assert frame.target is not None and frame.target.slot_index == slot_of(task)
    assert frame.target_xy_norm is None
    assert task.scene_spec()["prompt_object"] == OBJECTS[slot_of(task)].id


@pytest.mark.parametrize("cue", [False, True])
def test_the_visual_cue_pulses_the_target_button_from_the_prompt_to_the_selection(cue):
    task, _spy, _fb = make(visual_cue=cue)
    slot = slot_of(task)
    task.update(0, at(SCENE))
    assert task.scene_spec()["cue_slot"] == (slot if cue else -1)
    run(task, at(slot), 10, PROMPT + DWELL_MS + 10)
    assert task.scene_spec()["cue_slot"] == -1  # the trial has ended


def test_hover_slot_follows_the_pointer_for_the_glow():
    task, _spy, _fb = make()
    task.update(0, at(3))
    assert task.scene_spec()["hover_slot"] == 3
    task.update(10 * MS, at(SCENE))
    assert task.scene_spec()["hover_slot"] == -1
    task.update(20 * MS, at(5, valid=False))
    assert task.scene_spec()["hover_slot"] == -1


def test_the_board_follows_the_live_canvas_size():
    task, _spy, _fb = make()
    first = task.scene_spec()["buttons"][0]["rect"]
    task.set_screen_size(1280, 720)
    second = task.scene_spec()["buttons"][0]["rect"]
    assert second != first and second[2] < first[2]
    frame = task.update(PROMPT * MS, at(4))
    assert frame.target_radius_px == pytest.approx(task._geometry().fit_radius_px)


def test_a_gap_that_does_not_fit_is_capped_once_and_reported():
    task, spy, _fb = make(trials=2, gap_px=500.0)
    run(task, at(SCENE), 0, 50)
    capped = spy.of("GAP_CAPPED")
    assert len(capped) == 1 and capped[0][2]["requested_px"] == 500.0
    assert task.gap_capped_px == pytest.approx(0.5 * 1080 / 5)
    assert task.gap_px == 500.0
