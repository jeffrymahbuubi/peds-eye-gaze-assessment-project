"""SPEC-scene-cause-effect-task.md section 9, user answers of 2026-10-11.

Q1 = B: the engine measures each ``audio/<language>/prompt_<object>.wav`` itself (Python ``wave``,
read only) and falls back to ``DEFAULT_PROMPT_MS`` when the file is missing or unreadable; the
length goes into ``PROMPT_START``. Q2 = A: the task asks the feedback bus to play the prompt and
the effect sound and to cut them on a pause or a skip (``on_prompt``, ``on_effect``,
``on_stop_audio``); the bus's hooks are no-ops by default. No Qt here (the GUI side is in
``test_choice_making_canvas.py``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.config import load_task_config
from src.engine.feedback import FeedbackBus, NullFeedback
from src.engine.task_runner import build_task, run_headless_replay
from src.tasks.choice_layout import DEFAULT_PROMPT_MS, OBJECTS, prompt_wav_path
from tests.test_choice_layout import write_wav
from tests.test_choice_making import MS, SCENE, AudioFeedback, at, make, run, slot_of

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


def wav_for(root, task, ms, scene="park", language="en", trial=0):
    """Write the prompt WAV of ``task``'s trial ``trial`` object under ``root``."""
    obj = OBJECTS[slot_of(task, trial)]
    return write_wav(prompt_wav_path(scene, language, obj.id, root), ms)


# -- Q1 = B: the prompt's length -------------------------------------------------------------------


def test_the_prompt_is_as_long_as_its_wav(tmp_path):
    task, spy, _fb = make(assets_root=tmp_path)
    wav_for(tmp_path, task, 500)
    on = at(slot_of(task))
    run(task, on, 0, 490)
    start = spy.of("PROMPT_START")[0]
    assert start[2]["duration_ms"] == 500.0 and start[2]["duration_source"] == "wav"
    assert not spy.of("PROMPT_END") and not task.update(490 * MS, on).selectable
    run(task, on, 490, 710)
    assert [e[1] for e in spy.of("PROMPT_END")] == [500 * MS]  # not the 2000 ms default
    trial = task.trials[0]
    assert trial.is_hit and trial.t_selectable_start_ns == 500 * MS
    assert trial.rt_ms == pytest.approx(200)


def test_each_object_has_its_own_length(tmp_path):
    task, spy, _fb = make(trials=2, assets_root=tmp_path)
    wav_for(tmp_path, task, 400, trial=0)
    wav_for(tmp_path, task, 900, trial=1)
    run(task, at(SCENE), 0, 10)
    first = task.prompt_length(OBJECTS[slot_of(task, 0)])
    second = task.prompt_length(OBJECTS[slot_of(task, 1)])
    assert first == (pytest.approx(400.0, abs=0.1), "wav")
    assert second == (pytest.approx(900.0, abs=0.1), "wav")
    assert spy.of("PROMPT_START")[0][2]["duration_ms"] == pytest.approx(400.0, abs=0.1)


def test_a_missing_wav_falls_back_to_the_default(tmp_path):
    task, spy, _fb = make(assets_root=tmp_path)  # nothing under tmp_path
    run(task, at(SCENE), 0, 20)
    start = spy.of("PROMPT_START")[0][2]
    assert start["duration_ms"] == float(DEFAULT_PROMPT_MS) == 2000.0
    assert start["duration_source"] == "default"
    run(task, at(SCENE), 20, DEFAULT_PROMPT_MS + 10)
    assert [e[1] for e in spy.of("PROMPT_END")] == [DEFAULT_PROMPT_MS * MS]
    assert list(tmp_path.iterdir()) == []  # read only: nothing was created


def test_an_unreadable_or_empty_wav_falls_back_too(tmp_path):
    task, spy, _fb = make(trials=2, assets_root=tmp_path)
    prompt_wav_path("park", "en", OBJECTS[slot_of(task, 0)].id, tmp_path).parent.mkdir(parents=True)
    prompt_wav_path("park", "en", OBJECTS[slot_of(task, 0)].id, tmp_path).write_bytes(b"RIFFnope")
    wav_for(tmp_path, task, 0, trial=1)  # a WAV with no samples
    run(task, at(SCENE), 0, 10)
    assert task.prompt_length(OBJECTS[slot_of(task, 0)]) == (float(DEFAULT_PROMPT_MS), "default")
    assert task.prompt_length(OBJECTS[slot_of(task, 1)]) == (float(DEFAULT_PROMPT_MS), "default")


def test_the_path_follows_the_configured_scene_and_language(tmp_path):
    task, spy, _fb = make(assets_root=tmp_path, extra={"scene": "zoo", "language": "zh-TW"})
    wav_for(tmp_path, task, 300, scene="park", language="zh-TW")  # wrong scene
    wav_for(tmp_path, task, 300, scene="zoo", language="en")  # wrong language
    run(task, at(SCENE), 0, 10)
    assert spy.of("PROMPT_START")[0][2]["duration_source"] == "default"
    wav_for(tmp_path, task, 300, scene="zoo", language="zh-TW")
    task2, spy2, _fb2 = make(assets_root=tmp_path, extra={"scene": "zoo", "language": "zh-TW"})
    run(task2, at(SCENE), 0, 10)
    assert spy2.of("PROMPT_START")[0][2]["duration_ms"] == 300.0


def test_a_length_is_measured_once_per_object_and_run(tmp_path):
    task, _spy, _fb = make(assets_root=tmp_path)
    path = wav_for(tmp_path, task, 500)
    run(task, at(SCENE), 0, 10)
    path.unlink()  # gone after the first prompt: the run keeps its measure
    assert task.prompt_ms(OBJECTS[slot_of(task)]) == pytest.approx(500.0, abs=0.1)


def test_the_shipped_config_names_the_park_and_english():
    task = build_task("choice_making", load_task_config("choice_making"))
    assert (task.scene_name, task.language) == ("park", "en")


# -- Q2 = A: the audio hooks on the feedback bus ---------------------------------------------------------


def test_the_hooks_are_no_ops_on_the_bus_and_nullfeedback_records_nothing_for_them():
    fb = NullFeedback()
    assert fb.on_prompt("balloons") is None and fb.on_effect("balloons", True) is None
    assert fb.on_stop_audio() is None
    assert fb.events == []
    assert issubclass(NullFeedback, FeedbackBus)


def test_the_prompt_is_played_at_prompt_start_and_only_then():
    fb = AudioFeedback()
    task, spy, _fb = make(feedback=fb)
    obj = OBJECTS[slot_of(task)]
    task.update(0, at(SCENE))
    assert fb.audio == [("prompt", obj.id)]
    run(task, at(SCENE), 10, 1500)
    assert fb.audio == [("prompt", obj.id)]  # nothing again until the next trial
    assert spy.of("PROMPT_START")[0][2]["object"] == obj.id


def test_a_hit_plays_the_effect_sound_and_a_timeout_the_modelled_one():
    fb = AudioFeedback()
    task, _spy, _fb = make(trials=2, timeout_ms=1000, feedback=fb)
    first, second = OBJECTS[slot_of(task, 0)], OBJECTS[slot_of(task, 1)]
    run(task, at(first.slot), 0, DEFAULT_PROMPT_MS + 300)  # a hit
    assert fb.audio == [("prompt", first.id), ("effect", first.id, False)]
    # ... the next trial begins after the effect and the pause; nobody looks at a button.
    end_ms = DEFAULT_PROMPT_MS + 200 + first.effect_ms + 1000
    run(task, at(SCENE), DEFAULT_PROMPT_MS + 300, end_ms + DEFAULT_PROMPT_MS + 1100)
    assert fb.audio[2:] == [("prompt", second.id), ("effect", second.id, True)]


def test_a_wrong_button_plays_no_effect_sound():
    fb = AudioFeedback()
    task, _spy, _fb = make(feedback=fb)
    wrong = (slot_of(task) + 1) % 8
    run(task, at(wrong), 0, DEFAULT_PROMPT_MS + 300)  # a wrong completed dwell
    assert fb.audio == [("prompt", OBJECTS[slot_of(task)].id)]


def test_a_pause_cuts_the_sound_and_the_interrupted_prompt_plays_again():
    fb = AudioFeedback()
    task, _spy, _fb = make(feedback=fb)
    obj = OBJECTS[slot_of(task)]
    run(task, at(SCENE), 0, 1000)
    task.pause(1000 * MS)
    assert fb.audio == [("prompt", obj.id), ("stop",)]
    task.resume(5000 * MS)
    task.update(5000 * MS, at(SCENE))
    assert fb.audio == [("prompt", obj.id), ("stop",), ("prompt", obj.id)]


def test_a_pause_during_an_effect_cuts_its_sound_too():
    fb = AudioFeedback()
    task, _spy, _fb = make(feedback=fb)
    obj = OBJECTS[slot_of(task)]
    run(task, at(obj.slot), 0, DEFAULT_PROMPT_MS + 210)
    assert fb.audio[-1] == ("effect", obj.id, False)
    assert task.pause((DEFAULT_PROMPT_MS + 500) * MS) is False
    assert fb.audio[-1] == ("stop",)


def test_a_skip_cuts_the_prompt():
    fb = AudioFeedback()
    task, _spy, _fb = make(feedback=fb)
    task.update(0, at(SCENE))
    assert task.skip_trial(300 * MS)
    assert fb.audio[-1] == ("stop",) and all(a[0] != "effect" for a in fb.audio)


def test_a_bus_without_the_hooks_is_simply_silent():
    class Bare:  # a test double that knows only the four original cues
        def on_target_shown(self, x, y): ...
        def on_hit(self, x, y): ...
        def on_miss(self, x, y): ...
        def on_progress(self, x, y, progress): ...

    task, spy, _fb = make(feedback=Bare())
    run(task, at(slot_of(task)), 0, DEFAULT_PROMPT_MS + 300)
    assert task.trials[0].is_hit and spy.of("EFFECT_START")
    task.pause((DEFAULT_PROMPT_MS + 400) * MS)


def test_no_other_task_calls_the_hooks(tmp_path):
    fb = AudioFeedback()
    result = run_headless_replay(
        task_id="click_static", replay_path=FIXTURE, output_root=tmp_path, feedback=fb,
        max_seconds=30.0,
    )
    assert result["n_trials"] > 0 and fb.events  # the usual cues came through
    assert fb.audio == []
