"""SPEC-scanning-search-cues.md 4.2-4.4, 4.6: Scanning Search's search modes and its centre start dot,
through the task, one frame at a time on a fake clock (acceptance C2, C3, C4's scene half, C5, C7's
trial fields). No Qt except where a test says so.

The spoken prompts are not in the repository when these run, so every task here reads its prompt
files from a folder of the test's own (``NO_ASSETS``, or a temp dir with fake WAVs): the real
``configs/assets/scanning/audio`` can never change a result."""

from __future__ import annotations

import random
import wave
from pathlib import Path

import pytest

from src.engine.config import load_task_config
from src.engine.feedback import NullFeedback
from src.engine.task_runner import build_task
from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig, DwellSelector
from src.tasks.base_task import Phase
from src.tasks.scanning import ScanningTask
from src.tasks.search_cues import (
    N_SHAPES,
    SAMPLE_MS,
    SHAPE_NAMES,
    draw_field,
    normalise_search_mode,
    prompt_wav_path,
)

MS = 1_000_000
DWELL_MS = 200
TIMEOUT_MS = 3000
ITI_MS = 500
NO_ASSETS = Path(__file__).parent / "_no_such_scanning_assets"
CENTRE = Pointer(x=0.5, y=0.5, valid=True, clicked=False)  # on no icon of a 4-icon grid


class AudioFeedback(NullFeedback):
    """A bus that also records the audio hooks."""

    def __init__(self) -> None:
        super().__init__()
        self.audio: list[tuple] = []

    def on_prompt(self, object_id):
        self.audio.append(("prompt", object_id))

    def on_stop_audio(self):
        self.audio.append(("stop",))


class Spy:
    """Recorder double: the events and log lines a task emits."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []
        self.logs: list[str] = []

    def record_event(self, kind, t_ns, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message) -> None:
        self.logs.append(message)

    def of(self, *kinds):
        return [e for e in self.events if e[0] in kinds]

    def kinds(self):
        return [e[0] for e in self.events]


def make(
    *, trials=3, mode="match_sample", start_dot=False, input_mode="eye", n_icons=4, seed=0,
    assets_root=NO_ASSETS, arrangement="grid", extra=None, preroll_ms=0.0, config_keys=True,
    recorder=None, refractory_ms=0,
):
    spy, feedback = (Spy() if recorder is None else recorder), AudioFeedback()
    task_cfg = {
        "task_id": "scanning", "trials": trials, "timeout_ms": TIMEOUT_MS,
        "inter_trial_interval_ms": ITI_MS,
        "layout": {"n_icons": n_icons, "radius_px": 80, "arrangement": arrangement, "margin_frac": 0.14},
        **({"search_mode": mode, "start_dot": start_dot} if config_keys else {}),
        **(extra or {}),
    }
    cfg = {"task": task_cfg, "dwell": {"refractory_ms": refractory_ms}}
    switch = input_mode in ("gaze_switch", "switch")
    dwell = None if switch else DwellSelector(DwellConfig(threshold_ms=DWELL_MS, refractory_ms=refractory_ms))
    task = ScanningTask(
        cfg, 1920, 1080, recorder=spy, feedback=feedback, dwell=dwell, input_mode=input_mode,
        seed=seed, preroll_ms=preroll_ms,
    )
    task.assets_root = assets_root
    return task, spy, feedback


def write_wav(path: Path, duration_ms: float, rate=8000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * duration_ms / 1000))
    return path


def at_slot(task, slot, *, clicked=False):
    x, y = task.icon_slots[slot]
    return Pointer(x=x, y=y, valid=True, clicked=clicked)


def run(task, pointer, start_ms, end_ms, step_ms=10):
    """Update from ``start_ms`` up to (not including) ``end_ms``; every FrameResult."""
    return [task.update(t * MS, pointer) for t in range(start_ms, end_ms, step_ms)]


def shape_name_of(task, slot, trial=0):
    return SHAPE_NAMES[task.trial_field_shapes[trial][slot]]


# -- the setting -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("junk", ["shout", "", "POP_OUT", None, 3, ["match_sample"]])
def test_an_unknown_search_mode_is_pop_out(junk):
    assert normalise_search_mode(junk) == "pop_out"


def test_the_shipped_config_is_pop_out_with_no_start_dot():
    task = build_task("scanning", load_task_config("scanning"))
    assert (task.search_mode, task.start_dot, task.sample_ms) == ("pop_out", False, SAMPLE_MS)


def test_the_shape_names_follow_the_glyph_constants():
    from src.ui import canvas_shapes as cs

    for name, constant in zip(
        ("circle", "square", "triangle", "diamond", "hexagon", "star"),
        (cs.SHAPE_CIRCLE, cs.SHAPE_SQUARE, cs.SHAPE_TRIANGLE, cs.SHAPE_DIAMOND, cs.SHAPE_HEX, cs.SHAPE_STAR),
        strict=True,
    ):
        assert SHAPE_NAMES[constant] == name
    assert N_SHAPES == len(SHAPE_NAMES) == 6


# -- S6: the field's shuffle ---------------------------------------------------------------------------------


@pytest.mark.parametrize("n_icons", [2, 4, 6, 8])
def test_a_field_has_the_target_shape_exactly_once_in_the_target_slot(n_icons):
    rng = random.Random(5)
    for _ in range(60):
        slot = rng.randrange(n_icons)
        target, shapes = draw_field(rng, n_icons, slot)
        assert len(shapes) == n_icons and shapes.count(target) == 1 and shapes[slot] == target
        assert all(0 <= s < N_SHAPES for s in shapes)


@pytest.mark.parametrize("n_icons", [2, 4, 6])
def test_distractors_are_distinct_shapes_up_to_five(n_icons):
    rng = random.Random(1)
    for _ in range(40):
        _target, shapes = draw_field(rng, n_icons, rng.randrange(n_icons))
        assert len(set(shapes)) == n_icons  # up to 6 icons: every shape at most once


def test_with_more_than_six_icons_a_distractor_repeats_but_never_the_targets():
    rng = random.Random(2)
    repeats = 0
    for _ in range(60):
        slot = rng.randrange(8)
        target, shapes = draw_field(rng, 8, slot)
        assert shapes.count(target) == 1
        others = [s for i, s in enumerate(shapes) if i != slot]
        assert len(others) == 7 and set(others) <= set(range(N_SHAPES)) - {target}
        repeats += len(others) - len(set(others))
    assert repeats > 0  # 7 distractors cannot be 5 distinct shapes


def test_the_task_draws_a_fresh_seeded_field_per_trial():
    a, _, _ = make(trials=12, seed=3)
    b, _, _ = make(trials=12, seed=3)
    c, _, _ = make(trials=12, seed=4)
    assert a.trial_field_shapes == b.trial_field_shapes and a.trial_target_shapes == b.trial_target_shapes
    assert a.trial_field_shapes != c.trial_field_shapes
    assert len({tuple(f) for f in a.trial_field_shapes}) > 4  # not one arrangement repeated
    for t, shapes, target in zip(a.targets, a.trial_field_shapes, a.trial_target_shapes, strict=True):
        assert shapes[t.slot_index] == target and shapes.count(target) == 1


# -- C2: pop-out is exactly what it was -------------------------------------------------------------------


@pytest.mark.parametrize("seed, n_icons", [(0, 4), (7, 4), (3, 6), (11, 8)])
def test_pop_out_draws_the_target_slots_it_always_drew(seed, n_icons):
    task, _, _ = make(trials=10, mode="pop_out", seed=seed, n_icons=n_icons)
    rng = random.Random(seed)
    assert [t.slot_index for t in task.targets] == [rng.randrange(n_icons) for _ in range(10)]
    assert task.icon_shapes == [i % 6 for i in range(n_icons)]


def test_the_pop_out_scene_is_the_three_key_scene_of_before():
    task, _, _ = make(mode="pop_out")
    expected = {"mode": "icons", "slots": list(task.icon_slots), "shapes": [0, 1, 2, 3]}
    assert task.scene_spec() == expected
    run(task, CENTRE, 0, 500)
    assert task.phase is Phase.WAIT_INPUT and task.scene_spec() == expected


def _script(task):
    """Look at the target for the whole of every trial and at nothing in between: every frame."""
    frames = []
    for t in range(0, 8000, 10):
        index = task._trial_index
        target = task.targets[index] if task.phase is Phase.WAIT_INPUT else None
        pointer = at_slot(task, target.slot_index) if target is not None else CENTRE
        frames.append(task.update(t * MS, pointer))
        if task.is_done:
            break
    return frames


def test_pop_out_without_the_new_keys_and_with_them_behaves_identically():
    """An old config (no search keys) and an explicit Pop-out with the start dot off give the same
    frames, the same events and the same trial rows -- the whole trial sequence for a seed."""
    old, old_spy, _ = make(trials=4, config_keys=False, seed=9)
    new, new_spy, _ = make(trials=4, mode="pop_out", start_dot=False, seed=9)
    old_frames, new_frames = _script(old), _script(new)
    fields = ("phase", "trial_index", "target", "target_xy_norm", "dwell_progress", "selectable", "on_target")
    assert [[getattr(f, n) for n in fields] for f in old_frames] == [
        [getattr(f, n) for n in fields] for f in new_frames
    ]
    assert old_spy.events == new_spy.events
    assert [r.as_row() for r in old.trials] == [r.as_row() for r in new.trials]
    # What it did record is what it always did: no new events at all.
    assert set(old_spy.kinds()) <= {"TARGET_SHOWN", "HIT", "TIMEOUT", "TARGET_INSET", "TARGET_SHRUNK"}
    assert len(old.trials) == 4 and all(r.is_hit for r in old.trials)


def test_pop_out_trials_record_their_shapes_and_no_start_dot_fields():
    task, _, _ = make(trials=2, mode="pop_out")
    _script(task)
    for trial in task.trials:
        assert trial.search_mode == "pop_out"
        assert trial.target_shape == SHAPE_NAMES[trial.slot_index % 6]
        assert trial.field_shapes == "|".join(SHAPE_NAMES[i % 6] for i in range(4))
        assert trial.start_dot_ms is None and trial.start_dot_timeout is None
        assert trial.first_icon_looked_at_slot is None and trial.first_icon_looked_at_shape == ""
        row = trial.as_row()
        assert row["start_dot_ms"] == "" and row["start_dot_timeout"] == ""


# -- C3: Match the sample -----------------------------------------------------------------------------------


def test_the_sample_shows_the_target_shape_alone_and_selection_is_closed():
    task, spy, feedback = make(trials=2)
    shape = SHAPE_NAMES[task.trial_target_shapes[0]]
    on_future_target = at_slot(task, task.targets[0].slot_index)  # looking right where the target will be
    frames = run(task, on_future_target, 0, 1500)
    assert all(f.phase is Phase.SHOW_TARGET and f.target is None and f.target_xy_norm is None for f in frames)
    assert all(not f.selectable and not f.on_target and f.dwell_progress == 0.0 for f in frames)
    assert task.trials == [] and spy.kinds() == ["SAMPLE_START"]
    spec = task.scene_spec()
    assert spec["stage"] == "sample" and spec["search_mode"] == "match_sample"
    assert spec["sample_shape"] == task.trial_target_shapes[0]
    assert spec["sample_text"] == "Find this!" and spec["sample_text_px"] > 0 and spec["icon_radius_px"] > 0
    assert "reminder" not in spec
    event = spy.events[0]
    assert event[1:] == (0, {
        "trial": 0, "shape": shape, "duration_ms": 1500.0, "duration_source": "default",
    })
    assert feedback.audio == [("prompt", shape)]


def test_the_field_appears_when_the_sample_ends_and_the_clock_starts_there():
    task, spy, _ = make(trials=2)
    run(task, CENTRE, 0, 1500)
    assert task.update(1500 * MS, CENTRE).phase is Phase.WAIT_INPUT
    assert spy.kinds() == ["SAMPLE_START", "TARGET_SHOWN", "FIELD_SHOWN"]
    assert [e[1] for e in spy.events] == [0, 1500 * MS, 1500 * MS]
    assert spy.of("FIELD_SHOWN")[0][2] == {"trial": 0}
    run(task, CENTRE, 1510, 1520)
    trial = task._current
    assert trial.t_target_shown_ns == trial.t_selectable_start_ns == 1500 * MS


def test_the_field_shows_the_targets_shape_once_in_the_target_slot_and_no_reminder_by_default():
    task, _, _ = make(trials=2)
    run(task, CENTRE, 0, 1600)
    spec = task.scene_spec()
    slot, shapes = task.targets[0].slot_index, spec["shapes"]
    assert task.sample_reminder is False and spec["stage"] == "field" and "reminder" not in spec
    assert shapes == task.trial_field_shapes[0]
    assert shapes[slot] == task.trial_target_shapes[0] and shapes.count(shapes[slot]) == 1


def test_with_sample_reminder_on_the_field_keeps_the_sample_small_as_a_reminder():
    task, _, _ = make(trials=2, extra={"sample_reminder": True})
    run(task, CENTRE, 0, 1600)
    spec = task.scene_spec()
    slot, shapes = task.targets[0].slot_index, spec["shapes"]
    assert spec["stage"] == "field" and spec["sample_shape"] == task.trial_target_shapes[0]
    assert shapes == task.trial_field_shapes[0]
    assert shapes[slot] == spec["sample_shape"] and shapes.count(spec["sample_shape"]) == 1
    assert set(spec["reminder"]) == {"x_norm", "y_norm", "radius_px"}
    assert spec["reminder"]["radius_px"] == pytest.approx(0.5 * spec["icon_radius_px"])


def test_reaction_time_and_the_timeout_count_from_the_field():
    task, spy, _ = make(trials=2)
    run(task, CENTRE, 0, 1500)
    slot = task.targets[0].slot_index
    run(task, at_slot(task, slot), 1500, 1500 + DWELL_MS + 30)
    trial = task.trials[0]
    assert trial.is_hit and trial.t_target_shown_ns == 1500 * MS
    assert trial.reaction_time_ms == pytest.approx(DWELL_MS, abs=20)  # not 1700: the sample is not in it
    assert trial.reaction_time_from_selectable_ms == pytest.approx(trial.reaction_time_ms)
    # The second trial: nothing is selected, the timeout runs from its field, not from its sample.
    t_hit = trial.t_end_ns // MS
    field_2 = t_hit + ITI_MS + 1500
    run(task, CENTRE, t_hit + 10, field_2 + TIMEOUT_MS + 20)
    timeout = spy.of("TIMEOUT")[0]
    assert timeout[1] // MS == pytest.approx(field_2 + TIMEOUT_MS, abs=10)
    assert task.trials[1].is_timeout and task.trials[1].reaction_time_ms is None


def test_the_sample_lasts_as_long_as_a_longer_spoken_prompt(tmp_path):
    task, spy, _ = make(assets_root=tmp_path)
    shape = SHAPE_NAMES[task.trial_target_shapes[0]]
    write_wav(prompt_wav_path("en", shape, tmp_path), 2400)
    run(task, CENTRE, 0, 2390)
    assert task.phase is Phase.SHOW_TARGET
    task.update(2400 * MS, CENTRE)
    assert task.phase is Phase.WAIT_INPUT
    start = spy.of("SAMPLE_START")[0][2]
    assert (start["duration_ms"], start["duration_source"]) == (2400.0, "wav")
    assert spy.of("TARGET_SHOWN")[0][1] == 2400 * MS
    assert not spy.logs  # a file that was found says nothing


def test_a_shorter_spoken_prompt_still_gets_the_minimum_sample_time(tmp_path):
    task, spy, _ = make(assets_root=tmp_path)
    write_wav(prompt_wav_path("en", SHAPE_NAMES[task.trial_target_shapes[0]], tmp_path), 800)
    run(task, CENTRE, 0, 1490)
    assert task.phase is Phase.SHOW_TARGET
    start = spy.of("SAMPLE_START")[0][2]
    assert (start["duration_ms"], start["duration_source"]) == (1500.0, "wav")


def test_a_missing_prompt_falls_back_to_the_sample_time_with_one_log_line():
    task, spy, _ = make(trials=4)
    run(task, CENTRE, 0, 1500)
    start = spy.of("SAMPLE_START")[0][2]
    assert (start["duration_ms"], start["duration_source"]) == (1500.0, "default")
    first = task.trial_target_shapes[0]
    prompt_log = [m for m in spy.logs if f"prompt_{SHAPE_NAMES[first]}.wav" in m]
    assert len(prompt_log) == 1 and "1500 ms" in prompt_log[0]
    # Asked again (the same shape, a later trial) it does not repeat itself.
    task.sample_length(SHAPE_NAMES[first])
    assert len([m for m in spy.logs if f"prompt_{SHAPE_NAMES[first]}.wav" in m]) == 1


def test_an_unreadable_prompt_file_falls_back_too(tmp_path):
    task, spy, _ = make(assets_root=tmp_path)
    path = prompt_wav_path("en", SHAPE_NAMES[task.trial_target_shapes[0]], tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a wav")
    assert task.sample_length(SHAPE_NAMES[task.trial_target_shapes[0]]) == (1500.0, "default")
    assert spy.logs


def test_before_the_first_trial_the_scene_is_blank_and_the_sample_starts_after_the_preroll():
    task, spy, _ = make(preroll_ms=400.0)
    run(task, CENTRE, 0, 400)
    assert task.phase is Phase.READY and task.scene_spec()["stage"] == "blank" and not spy.events
    task.update(400 * MS, CENTRE)
    assert task.scene_spec()["stage"] == "sample" and spy.of("SAMPLE_START")[0][1] == 400 * MS


def test_between_trials_the_field_stays_without_its_reminder_until_the_next_sample():
    task, _, _ = make(trials=2, extra={"sample_reminder": True})
    run(task, CENTRE, 0, 1500)
    run(task, at_slot(task, task.targets[0].slot_index), 1500, 1760)
    assert task.phase is Phase.ITI
    spec = task.scene_spec()
    assert spec["stage"] == "field" and "reminder" not in spec and spec["shapes"] == task.trial_field_shapes[0]
    run(task, CENTRE, 1760, 1760 + ITI_MS)
    assert task.scene_spec()["stage"] == "sample" and task.scene_spec()["shapes"] == task.trial_field_shapes[1]


def test_every_trial_has_its_own_sample_and_prompt():
    task, spy, feedback = make(trials=3)
    for t in range(0, 12000, 10):
        slot = task.targets[task._trial_index].slot_index if task.phase is Phase.WAIT_INPUT else None
        task.update(t * MS, at_slot(task, slot) if slot is not None else CENTRE)
        if task.is_done:
            break
    samples = spy.of("SAMPLE_START")
    assert [e[2]["trial"] for e in samples] == [0, 1, 2]
    assert [e[2]["shape"] for e in samples] == [SHAPE_NAMES[s] for s in task.trial_target_shapes]
    assert feedback.audio == [("prompt", e[2]["shape"]) for e in samples]
    assert len(spy.of("FIELD_SHOWN")) == 3 and all(r.is_hit for r in task.trials)


def test_the_run_bar_names_the_trial_being_prepared():
    task, _, _ = make(trials=2)
    assert task.trial_number == 0
    run(task, CENTRE, 0, 100)
    assert task.trial_number == 1  # the sample of trial 1
    run(task, CENTRE, 100, 1600)
    assert task.trial_number == 1  # and its field


def test_a_trial_in_the_sample_cannot_be_skipped():
    task, _, _ = make()
    run(task, CENTRE, 0, 100)
    assert task.skip_trial(100 * MS) is False


# -- trial fields (4.6) ---------------------------------------------------------------------------------


def test_a_match_the_sample_trial_records_its_mode_target_and_field():
    task, _, _ = make(trials=1)
    run(task, CENTRE, 0, 1500)
    run(task, at_slot(task, task.targets[0].slot_index), 1500, 1800)
    trial = task.trials[0]
    assert trial.search_mode == "match_sample"
    assert trial.target_shape == SHAPE_NAMES[task.trial_target_shapes[0]]
    assert trial.field_shapes.split("|") == [SHAPE_NAMES[s] for s in task.trial_field_shapes[0]]
    assert trial.field_shapes.split("|")[trial.slot_index] == trial.target_shape
    row = trial.as_row()
    assert row["search_mode"] == "match_sample" and row["target_shape"] == trial.target_shape
    assert row["field_shapes"] == trial.field_shapes


def test_first_icon_looked_at_is_the_first_icon_the_pointer_enters_after_the_field_appears():
    task, _, _ = make(trials=1, seed=2)
    target = task.targets[0].slot_index
    wrong = (target + 1) % 4
    run(task, at_slot(task, wrong), 0, 1500)  # the sample: looking at an icon-to-be counts for nothing
    assert task._current is None
    run(task, CENTRE, 1500, 1600)
    run(task, at_slot(task, wrong), 1600, 1700)  # the first icon entered is a wrong one
    run(task, at_slot(task, target), 1700, 1700 + DWELL_MS + 40)
    trial = task.trials[0]
    assert trial.is_hit
    assert trial.first_icon_looked_at_slot == wrong
    assert trial.first_icon_looked_at_shape == shape_name_of(task, wrong)
    assert trial.as_row()["first_icon_looked_at_slot"] == wrong


def test_looking_straight_at_the_target_records_it_and_looking_nowhere_records_nothing():
    task, _, _ = make(trials=2, seed=4)
    run(task, CENTRE, 0, 1500)
    run(task, at_slot(task, task.targets[0].slot_index), 1500, 1500 + DWELL_MS + 40)
    first = task.trials[0]
    assert first.first_icon_looked_at_slot == first.slot_index
    assert first.first_icon_looked_at_shape == first.target_shape
    t = first.t_end_ns // MS + ITI_MS + 1500
    run(task, CENTRE, first.t_end_ns // MS + 10, t + TIMEOUT_MS + 30)
    second = task.trials[1]
    assert second.is_timeout and second.first_icon_looked_at_slot is None
    assert second.as_row()["first_icon_looked_at_slot"] == ""


def test_a_look_on_the_frame_a_press_ends_the_trial_is_still_recorded():
    """The trial's row is written when it ends: the first icon is noted before the frame's selection."""
    task, _, _ = make(trials=1, input_mode="gaze_switch", seed=6)
    target = task.targets[0].slot_index
    run(task, CENTRE, 0, 1510)  # the field is up from 1500
    task.update(1510 * MS, at_slot(task, target, clicked=True))
    assert task.trials[0].is_hit and task.trials[0].first_icon_looked_at_slot == target


def test_a_look_at_an_icon_on_the_very_frame_the_field_appears_is_recorded():
    task, _, _ = make(trials=1, seed=6)
    target = task.targets[0].slot_index
    run(task, CENTRE, 0, 1500)
    task.update(1500 * MS, at_slot(task, target))  # the first frame of the field
    assert task._current.first_icon_looked_at_slot == target
