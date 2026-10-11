"""SPEC-scene-cause-effect-task.md step 4, task side: the run bar's prompt line (W2), the effect
durations from the scene manifest (4.4, 4.7) and the idle-animation key of the scene description
(N3). Qt-free."""

from __future__ import annotations

import pytest

from src.engine.tracking_status import LEVEL_OK, RunStatus, run_status
from src.tasks.base_task import Phase
from src.tasks.choice_layout import OBJECTS
from tests.test_choice_making import DWELL_MS, MS, POST, PROMPT, SCENE, at, make, run, slot_of
from tests.test_choice_scene import write_scene

# -- W2: the prompt line of the run bar ------------------------------------------------------------------------------


def test_the_prompt_label_is_the_object_from_the_prompt_start_to_the_effect_end_and_empty_between():
    task, _spy, _fb = make()
    assert task.prompt_label == ""  # before the first trial
    slot = slot_of(task)
    label = OBJECTS[slot].label
    task.update(0, at(SCENE))
    assert task.prompt_label == label  # the prompt has started
    run(task, at(slot), 10, PROMPT + DWELL_MS + 10)
    assert task.phase is Phase.RESULT and task.prompt_label == label  # still, during the effect
    end_ms = PROMPT + DWELL_MS + OBJECTS[slot].effect_ms
    run(task, at(SCENE), PROMPT + DWELL_MS + 20, end_ms - 10)
    assert task.prompt_label == label
    run(task, at(SCENE), end_ms - 10, end_ms + 10)
    assert task.phase is Phase.ITI and task.prompt_label == ""  # between trials: empty
    run(task, at(SCENE), end_ms + 10, end_ms + POST + 20)
    assert task.prompt_label == OBJECTS[task.targets[1].slot_index].label  # the next trial's prompt


def test_a_timeout_keeps_the_prompt_line_through_the_modelled_effect_too():
    task, _spy, _fb = make(timeout_ms=1000)
    label = OBJECTS[slot_of(task)].label
    run(task, at(SCENE), 0, PROMPT + 1010)
    assert task.phase is Phase.RESULT and task.prompt_label == label


def test_a_skipped_trial_clears_the_prompt_line():
    task, _spy, _fb = make()
    task.update(0, at(SCENE))
    task.update(10 * MS, at(SCENE))
    task.skip_trial(20 * MS)
    assert task.prompt_label == ""


def test_the_run_status_names_the_prompt_after_the_trial_and_a_pause_drops_it():
    status = run_status(4, 16, "Tracking OK", prompt="Balloons")
    assert status.prompt == "Prompt: Balloons"
    assert status.line == "Trial 4 of 16, Prompt: Balloons, Tracking OK"
    assert run_status(4, 16, "Tracking OK", mouse=True, practice=True, prompt="Cloud").line == (
        "PRACTICE, Trial 4 of 16, Prompt: Cloud, Mouse pointer, Tracking OK"
    )
    assert run_status(1, 3, "", preview=True, mouse=True, prompt="Bike").line == (
        "PREVIEW, Trial 1 of 3, Prompt: Bike, Mouse pointer"
    )
    assert run_status(1, 3, "Tracking OK", preview=True, prompt="Bike").line == (
        "PREVIEW, Trial 1 of 3, Prompt: Bike, Gaze pointer, Tracking OK"
    )
    assert run_status(4, 16, "Tracking OK", paused=True, prompt="Balloons").line == "Paused, Trial 4 of 16"
    # Without a prompt nothing changes, for every other task.
    assert run_status(4, 16, "Tracking OK").prompt == "" and "Prompt" not in run_status(4, 16, "x").line
    assert RunStatus("", False, "Trial 1 of 2", "", "", LEVEL_OK).prompt == ""  # old positional use


# -- 4.4 / 4.7: durations come from the scene manifest -----------------------------------------------------------------


def test_with_no_scene_file_the_effects_last_their_4_4_durations():
    task, _spy, _fb = make()
    assert task.manifest.source == "default"
    assert [task.effect_ms(obj) for obj in OBJECTS] == [float(obj.effect_ms) for obj in OBJECTS]


def test_a_scene_file_can_change_an_effects_duration_and_the_engine_uses_it(tmp_path):
    slot_first = None
    task0, _s, _f = make()
    slot_first = slot_of(task0)
    object_id = OBJECTS[slot_first].id
    write_scene(tmp_path, f"objects:\n  {object_id}:\n    duration_ms: 1234\n")
    task, spy, _fb = make(assets_root=tmp_path)
    assert task.manifest.source == "file" and task.effect_ms(OBJECTS[slot_first]) == 1234.0
    run(task, at(slot_first), 0, PROMPT + DWELL_MS + 10)
    assert spy.of("EFFECT_START")[0][2]["duration_ms"] == 1234.0
    assert task.scene_spec()["effect"]["duration_ms"] == 1234.0
    run(task, at(SCENE), PROMPT + DWELL_MS + 20, PROMPT + DWELL_MS + 1234 + 10)
    assert [e[1] for e in spy.of("EFFECT_END")] == [(PROMPT + DWELL_MS + 1234) * MS]
    assert task.phase is Phase.ITI


def test_an_unusable_scene_file_is_logged_once_and_the_built_in_durations_are_used(tmp_path):
    write_scene(tmp_path, "objects: [1, 2]")
    task, _spy, _fb = make(assets_root=tmp_path)
    lines: list[str] = []
    task._log = lines.append  # the recorder double ignores log lines
    run(task, at(SCENE), 0, 200)
    task.effect_ms(OBJECTS[0])
    task.effect_ms(OBJECTS[1])
    assert len(lines) == 1 and "Scene manifest" in lines[0] and "scene.yaml" in lines[0]
    assert task.manifest.source == "default" and task.effect_ms(OBJECTS[0]) == float(OBJECTS[0].effect_ms)


# -- N3: what the canvas is told ----------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["off", "blinks", "blinks_bob"])
def test_the_scene_description_carries_the_idle_animation(value):
    task, _spy, _fb = make(extra={"idle_animation": value})
    assert task.scene_spec()["idle_animation"] == value


def test_the_idle_animation_defaults_to_blinks_and_an_unknown_value_is_blinks():
    assert make()[0].scene_spec()["idle_animation"] == "blinks"
    assert make(extra={"idle_animation": "dancing"})[0].scene_spec()["idle_animation"] == "blinks"
