"""SPEC-scene-cause-effect-task.md 3.7, step 8: the text prompt (P1 the setting, P2 the banner's
text through ``scene_spec``, P3 the timing).

``prompt_mode`` is ``voice`` (the default: the spoken prompt blocks selection until it ends, H4, A3),
``text`` (no voice, selection open from the trial start, the time to choose counted from it) or
``voice_text`` (the voice as in ``voice``, plus the banner). No Qt: the task is driven one frame at
a time. What the canvas draws from ``scene_spec`` is in ``test_scene_banner.py``."""

from __future__ import annotations

import pytest

from src.engine.config import load_task_config
from src.engine.subject_tests import create_test, list_tests
from src.engine.task_runner import build_task
from src.tasks.base_task import Phase
from src.tasks.choice_layout import (
    DEFAULT_PROMPT_MODE,
    DEFAULT_PROMPT_MS,
    OBJECTS,
    PROMPT_MODES,
    normalise_prompt_mode,
    prompt_has_text,
    prompt_has_voice,
)
from src.tasks.choice_scene_defaults import default_manifest
from src.ui.settings_registry import initial_structural_values, structural_settings_for_task
from src.ui.settings_snapshot import complete_settings, merged_config, run_settings
from tests.test_choice_making import (
    DWELL_MS,
    MS,
    POST,
    PROMPT,
    SCENE,
    AudioFeedback,
    at,
    make,
    run,
    slot_of,
)

TASK = "choice_making"
MODES = ("voice", "text", "voice_text")
SENTENCES = {obj.id: default_manifest().object(obj.id).prompt for obj in OBJECTS}


def text_of(task) -> str | None:
    return task.scene_spec()["prompt_text"]


# -- P1: the setting ------------------------------------------------------------------------------------


def test_prompt_mode_is_a_three_way_choice_that_defaults_to_voice():
    setting = next(s for s in structural_settings_for_task(TASK) if s.key == "prompt_mode")
    assert setting.kind == "choice" and setting.default == "voice" == DEFAULT_PROMPT_MODE
    assert setting.label == "Prompt"
    assert setting.choices == (("voice", "Voice"), ("text", "Text"), ("voice_text", "Voice and text"))
    assert tuple(value for value, _label in setting.choices) == PROMPT_MODES
    for other in ("click_static", "click_grid", "follow_moving", "scanning"):
        assert "prompt_mode" not in {s.key for s in structural_settings_for_task(other)}


def test_a_task_built_from_the_shipped_config_gives_a_voice_prompt():
    task = build_task(TASK, load_task_config(TASK), seed=1)
    assert task.prompt_mode == "voice"


@pytest.mark.parametrize("mode", MODES)
def test_the_chosen_mode_reaches_the_task_and_the_run_metadata(mode):
    config = load_task_config(TASK)
    merged = merged_config(config, structural={"prompt_mode": mode})
    assert run_settings(TASK, merged, "x")["structural"]["prompt_mode"] == mode
    assert build_task(TASK, merged, seed=1).prompt_mode == mode


@pytest.mark.parametrize("junk", ["shout", "", "VOICE", None, 3])
def test_an_unknown_value_is_voice_everywhere(junk):
    assert normalise_prompt_mode(junk) == "voice"
    merged = merged_config(load_task_config(TASK), structural={"prompt_mode": junk})
    assert initial_structural_values(TASK, merged)["prompt_mode"] == "voice"
    assert run_settings(TASK, merged, "x")["structural"]["prompt_mode"] == "voice"
    task = build_task(TASK, merged, seed=1)
    assert task.prompt_mode == "voice"
    assert prompt_has_voice(junk) and not prompt_has_text(junk)


def test_which_mode_has_a_voice_and_which_a_banner():
    assert [(m, prompt_has_voice(m), prompt_has_text(m)) for m in MODES] == [
        ("voice", True, False), ("text", False, True), ("voice_text", True, True),
    ]


def test_the_mode_is_stored_with_the_test_and_a_run_built_from_it_uses_it(tmp_path):
    config = load_task_config(TASK)
    stored = complete_settings(TASK, config, structural={"prompt_mode": "text"})
    assert stored["structural"]["prompt_mode"] == "text"  # a stored configuration is complete
    create_test(
        tmp_path, "TESTING", TASK,
        configuration={"name": "Saved", "structural": stored["structural"], "live": stored["live"]},
    )
    test = list_tests(tmp_path, "TESTING").tests[0]
    assert test.configuration["structural"]["prompt_mode"] == "text"
    merged = merged_config(config, test.configuration["live"], test.configuration["structural"])
    assert build_task(TASK, merged, seed=test.seed).prompt_mode == "text"
    # A configuration saved with Voice stays Voice even if the shipped default were to change later.
    assert complete_settings(TASK, config)["structural"]["prompt_mode"] == "voice"


# -- P2: what scene_spec says to show -------------------------------------------------------------------


def test_the_scene_spec_has_no_text_in_voice_mode_at_any_time():
    task, _spy, _fb = make(trials=2, timeout_ms=1000, extra={"prompt_mode": "voice"})
    assert text_of(task) is None
    for t in range(0, 2 * (PROMPT + 1000 + 5000), 50):
        task.update(t * MS, at(SCENE))
        assert text_of(task) is None


@pytest.mark.parametrize("mode", ["text", "voice_text"])
def test_the_text_is_the_prompted_objects_sentence_from_the_trial_start_to_the_hit(mode):
    task, _spy, _fb = make(trials=2, extra={"prompt_mode": mode})
    assert text_of(task) is None  # before the first trial
    task.update(0, at(SCENE))
    obj = OBJECTS[slot_of(task)]
    assert text_of(task) == SENTENCES[obj.id] == task.manifest.object(obj.id).prompt
    assert text_of(task) and text_of(task).endswith("!")
    run(task, at(SCENE), 10, PROMPT + 500)  # through the voice prompt and after it
    assert text_of(task) == SENTENCES[obj.id]
    # A wrong choice does not take it away.
    wrong = at((slot_of(task) + 1) % 8)
    run(task, wrong, PROMPT + 500, PROMPT + 500 + DWELL_MS + 40)
    assert task.trials == [] and task._phase is Phase.WAIT_INPUT
    assert text_of(task) == SENTENCES[obj.id]


@pytest.mark.parametrize("mode", ["text", "voice_text"])
def test_the_text_is_hidden_during_the_effect_the_pause_and_between_trials(mode):
    task, spy, _fb = make(trials=2, extra={"prompt_mode": mode})
    first, second = (OBJECTS[slot_of(task, i)] for i in (0, 1))
    hit = at(first.slot)
    t = 0
    while not task.trials:  # the hit
        task.update(t * MS, hit)
        t += 10
    assert task._phase is Phase.RESULT and text_of(task) is None  # the effect plays
    effect_end = spy.of("EFFECT_START")[0][1] // MS + int(first.effect_ms)
    while t < effect_end - 10:
        task.update(t * MS, at(SCENE))
        t += 10
        assert text_of(task) is None
    while task._phase is not Phase.WAIT_INPUT:  # the pause after the effect (the ITI)
        assert text_of(task) is None
        task.update(t * MS, at(SCENE))
        t += 10
    assert t * MS > effect_end * MS + POST * MS - 20 * MS  # the next trial began after effect and pause
    assert text_of(task) == SENTENCES[second.id] != SENTENCES[first.id]


@pytest.mark.parametrize("mode", ["text", "voice_text"])
def test_the_text_is_hidden_during_the_modelled_effect_after_a_timeout(mode):
    task, spy, _fb = make(trials=2, timeout_ms=800, extra={"prompt_mode": mode})
    t, seen = 0, []
    while not spy.of("EFFECT_START") and t < 20_000:
        task.update(t * MS, at(SCENE))
        seen.append(text_of(task))
        t += 10
    assert spy.of("EFFECT_START")[0][2]["modelled"] is True
    assert seen[0] is not None and seen[-2] is not None and seen[-1] is None  # gone with the timeout
    assert text_of(task) is None


@pytest.mark.parametrize("mode", ["text", "voice_text"])
def test_the_text_is_hidden_after_a_skip_and_while_paused_and_at_the_end(mode):
    task, _spy, _fb = make(trials=2, extra={"prompt_mode": mode})
    task.update(0, at(SCENE))
    assert text_of(task) is not None
    assert task.skip_trial(100 * MS)
    assert text_of(task) is None  # the pause before the next prompt
    t = 100
    while task._phase is not Phase.WAIT_INPUT:
        task.update(t * MS, at(SCENE))
        t += 10
    assert text_of(task) is not None
    task.pause(t * MS)
    assert text_of(task) is None  # the trial in flight was dropped
    task.resume((t + 3000) * MS)
    task.update((t + 3000) * MS, at(SCENE))
    assert text_of(task) is not None  # re-presented from its start, with its text
    done, _spy2, _fb2 = make(trials=1, extra={"prompt_mode": mode})
    run(done, at(slot_of(done)), 0, PROMPT + 400)
    run(done, at(SCENE), PROMPT + 400, PROMPT + 400 + 4600 + POST + 500)
    assert done._phase is Phase.DONE and text_of(done) is None


def test_every_object_has_a_sentence_and_the_text_follows_each_trials_object():
    assert all(SENTENCES.values()) and len(set(SENTENCES.values())) == 8
    task, _spy, _fb = make(trials=16, extra={"prompt_mode": "text"})
    t = 0
    for index in range(16):
        while not (task._phase is Phase.WAIT_INPUT and task._trial_index == index):
            task.update(t * MS, at(SCENE))  # through the pause of the trial before
            t += 10
        obj = OBJECTS[slot_of(task, index)]
        assert text_of(task) == SENTENCES[obj.id]
        assert task.skip_trial(t * MS)  # on to the next
        assert text_of(task) is None


# -- P3: the timing -------------------------------------------------------------------------------------


def test_text_mode_plays_no_voice_but_the_effect_still_has_its_sound():
    fb = AudioFeedback()
    task, _spy, _fb = make(extra={"prompt_mode": "text"}, feedback=fb)
    obj = OBJECTS[slot_of(task)]
    run(task, at(obj.slot), 0, DWELL_MS + 100)
    assert task.trials[0].is_hit
    assert fb.audio == [("effect", obj.id, False)]  # no ("prompt", ...) at all


def test_text_mode_plays_no_voice_on_the_next_trials_either():
    fb = AudioFeedback()
    task, _spy, _fb = make(trials=3, timeout_ms=500, extra={"prompt_mode": "text"}, feedback=fb)
    run(task, at(SCENE), 0, 3 * (500 + 4600 + POST) + 200)
    assert len(task.trials) >= 2 and all(a[0] != "prompt" for a in fb.audio)
    assert any(a[0] == "effect" and a[2] is True for a in fb.audio)  # the modelled effects still sound


def test_text_mode_is_selectable_at_once_and_the_hit_comes_after_the_dwell_alone():
    task, spy, _fb = make(extra={"prompt_mode": "text"})
    on = at(slot_of(task))
    first = task.update(0, on)
    assert first.selectable and first.phase is Phase.WAIT_INPUT
    run(task, on, 10, DWELL_MS + 100)
    trial = task.trials[0]
    assert trial.is_hit and trial.t_click_ns <= (DWELL_MS + 20) * MS  # nowhere near the 2 s a voice takes
    assert trial.t_selectable_start_ns == 0
    assert trial.rt_ms == pytest.approx(DWELL_MS, abs=20)  # counted from the trial start


def test_text_mode_prompt_events_have_duration_zero_and_source_text():
    task, spy, _fb = make(trials=2, timeout_ms=500, extra={"prompt_mode": "text"})
    run(task, at(SCENE), 0, 500 + 4600 + POST + 300)
    starts, ends = spy.of("PROMPT_START"), spy.of("PROMPT_END")
    assert len(starts) == 2
    for _kind, _t_ns, payload in starts:
        assert payload["duration_ms"] == 0 and payload["duration_source"] == "text"
        assert payload["object"] in SENTENCES
    # The prompt has no length, so it "ends" when it starts and the time to choose begins there.
    assert [e[1] for e in ends] == [s[1] for s in starts]


def test_text_mode_timeout_is_counted_from_the_trial_start():
    voice, spy_v, _ = make(timeout_ms=1000)
    run(voice, at(SCENE), 0, PROMPT + 1200)
    text, spy_t, _ = make(timeout_ms=1000, extra={"prompt_mode": "text"})
    run(text, at(SCENE), 0, 1200)
    assert [e[1] for e in spy_v.of("TIMEOUT")] == [(PROMPT + 1000) * MS]  # from the end of the voice
    assert [e[1] for e in spy_t.of("TIMEOUT")] == [1000 * MS]  # from the start
    assert text.trials[0].is_timeout and spy_t.of("EFFECT_START")[0][2]["modelled"] is True


def test_text_mode_with_the_switch_selects_at_once_and_a_wrong_press_is_a_wrong_choice():
    task, spy, _fb = make(mode="gaze_switch", extra={"prompt_mode": "text"})
    wrong = (slot_of(task) + 1) % 8
    task.update(0, at(wrong))
    task.update(50 * MS, at(wrong, clicked=True))
    miss = spy.of("MISS_CLICK")
    assert len(miss) == 1 and miss[0][2]["selected_object"] == OBJECTS[wrong].id
    task.update(100 * MS, at(slot_of(task)))
    task.update(150 * MS, at(slot_of(task), clicked=True))
    assert task.trials[0].is_hit and task.trials[0].attempts == 2


@pytest.mark.parametrize("mode", ["voice", "voice_text"])
def test_voice_and_voice_text_play_the_voice_and_block_selection_until_it_ends(mode):
    fb = AudioFeedback()
    task, spy, _fb = make(extra={"prompt_mode": mode}, feedback=fb)
    obj = OBJECTS[slot_of(task)]
    on = at(obj.slot)
    frames = [task.update(t * MS, on) for t in range(0, PROMPT, 10)]
    assert not any(f.selectable for f in frames) and not task.trials  # blocked the whole prompt
    assert fb.audio == [("prompt", obj.id)]
    start = spy.of("PROMPT_START")[0][2]
    assert start["duration_ms"] == DEFAULT_PROMPT_MS and start["duration_source"] == "default"
    run(task, on, PROMPT, PROMPT + DWELL_MS + 100)
    trial = task.trials[0]
    assert trial.is_hit and [e[1] for e in spy.of("PROMPT_END")] == [PROMPT * MS]
    assert trial.t_selectable_start_ns == PROMPT * MS
    assert trial.rt_ms == pytest.approx(DWELL_MS, abs=20)  # counted from the voice's end
    assert fb.audio[-1] == ("effect", obj.id, False)


def test_voice_text_times_out_from_the_end_of_the_voice_like_voice():
    task, spy, _fb = make(timeout_ms=1000, extra={"prompt_mode": "voice_text"})
    run(task, at(SCENE), 0, PROMPT + 1200)
    assert [e[1] for e in spy.of("TIMEOUT")] == [(PROMPT + 1000) * MS]


def test_text_mode_survives_a_pause_and_re_presents_the_trial_with_its_banner_and_no_voice():
    fb = AudioFeedback()
    task, spy, _fb = make(extra={"prompt_mode": "text"}, feedback=fb)
    run(task, at(SCENE), 0, 400)
    assert task.pause(400 * MS) is True  # the trial in flight is dropped
    task.resume(5000 * MS)
    task.update(5000 * MS, at(SCENE))
    assert text_of(task) is not None and task.trials == []
    assert [e[2]["duration_source"] for e in spy.of("PROMPT_START")] == ["text", "text"]
    assert all(a[0] != "prompt" for a in fb.audio)
