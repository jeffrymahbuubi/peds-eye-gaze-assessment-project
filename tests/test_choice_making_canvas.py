"""SPEC-scene-cause-effect-task.md step 3 scope, offscreen Qt.

* The task's frames and scene go to a real ``TaskCanvas`` and each phase of a trial is painted
  (the scene mode itself is step 4: ``test_choice_scene_canvas.py``).
* Section 9 Q2 = A, the GUI side: ``SceneAudio`` keeps one ``QSoundEffect`` per audio file that
  exists and is silent for one that does not; ``GuiFeedback`` forwards the audio hooks to it."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.app import GuiFeedback
from src.engine.config import load_task_config
from src.tasks.choice_layout import OBJECTS, effect_wav_path, prompt_wav_path
from src.ui.canvas import TaskCanvas
from src.ui.scene_audio import VOLUME, SceneAudio
from tests.test_choice_layout import write_wav
from tests.test_choice_making import MS, SCENE, at, make

THEME = {"background": "#e8f5e9", "cursor_color": "#1b5e20", "target_default": "#ff5252"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_canvas_paints_every_phase_of_a_choice_making_trial(qapp):
    task, _spy, _fb = make(trials=2, timeout_ms=1000)
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(960, 540)
    task.set_screen_size(960, 540)
    seen, slot = set(), -1
    for t in range(0, 40_000, 100):
        # Look at the right button on the first trial, the scene on the second (a timeout).
        pointer = at(slot) if slot >= 0 and task.trial_number == 1 else at(SCENE)
        result = task.update(t * MS, pointer)
        slot = result.target.slot_index if result.target else -1
        canvas.set_frame(
            target_xy_norm=result.target_xy_norm,
            target_radius_px=result.target_radius_px if result.target else 90.0,
            cursor_xy_norm=result.cursor_xy_norm,
            cursor_valid=True,
            dwell_progress=result.dwell_progress,
            selectable=result.selectable,
            layout_slots=task.layout_slots,
            on_target=result.on_target,
            scene=task.scene_spec(),
            active_slot=slot,
        )
        image = canvas.grab()
        assert not image.isNull()
        seen.add(result.phase.name)
        if task.is_done:
            break
    assert {"WAIT_INPUT", "RESULT", "ITI", "DONE"} <= seen
    assert canvas.scene["mode"] == "scene" and len(canvas.scene["buttons"]) == len(OBJECTS)


# -- Q2 = A: the sounds ------------------------------------------------------------------------------------


def test_scene_audio_loads_only_the_files_that_exist_and_is_silent_for_the_rest(qapp, tmp_path):
    write_wav(prompt_wav_path("park", "en", "balloons", tmp_path), 300)
    write_wav(prompt_wav_path("park", "en", "bike", tmp_path), 300)
    write_wav(effect_wav_path("park", "bike", tmp_path), 300)
    write_wav(prompt_wav_path("park", "zh-TW", "swing", tmp_path), 300)  # another language
    audio = SceneAudio("park", "en", tmp_path)
    assert set(audio._prompts) == {"balloons", "bike"} and set(audio._effects) == {"bike"}
    effect = audio._prompts["bike"]
    assert effect.volume() == pytest.approx(VOLUME) and VOLUME < 1.0
    assert effect.source().toLocalFile().replace("\\", "/") == str(
        prompt_wav_path("park", "en", "bike", tmp_path)
    ).replace("\\", "/")
    # Playing a file that is not there (most objects, today) and stopping are quiet no-ops.
    for object_id in ("rainbow", "swing"):
        audio.on_prompt(object_id)
        audio.on_effect(object_id, False)
    audio.on_prompt("bike")
    audio.on_effect("bike", True)
    audio.stop()


def test_scene_audio_with_no_files_at_all_is_silent(qapp, tmp_path):
    audio = SceneAudio("park", "en", tmp_path / "missing")
    assert not audio._prompts and not audio._effects
    audio.on_prompt("balloons")
    audio.on_effect("balloons", False)
    audio.stop()
    assert not (tmp_path / "missing").exists()  # read only


def test_only_a_task_with_a_scene_gets_audio(qapp):
    assert SceneAudio.from_task_config(load_task_config("click_grid")["task"]) is None
    audio = SceneAudio.from_task_config(load_task_config("choice_making")["task"])
    assert isinstance(audio, SceneAudio)


def test_gui_feedback_forwards_the_audio_hooks_and_stays_quiet_without_audio(qapp):
    class Spy:
        def __init__(self):
            self.calls = []

        def on_prompt(self, object_id):
            self.calls.append(("prompt", object_id))

        def on_effect(self, object_id, modelled):
            self.calls.append(("effect", object_id, modelled))

        def stop(self):
            self.calls.append(("stop",))

    canvas = TaskCanvas(theme=THEME)
    spy = Spy()
    feedback = GuiFeedback(canvas, THEME, {}, scene_audio=spy)
    feedback.on_prompt("cloud")
    feedback.on_effect("cloud", True)
    feedback.on_stop_audio()
    assert spy.calls == [("prompt", "cloud"), ("effect", "cloud", True), ("stop",)]
    plain = GuiFeedback(canvas, THEME, {})  # every other task
    plain.on_prompt("cloud")
    plain.on_effect("cloud", False)
    plain.on_stop_audio()
