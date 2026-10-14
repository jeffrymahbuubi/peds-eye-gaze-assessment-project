"""The sounds of Choice-making: a spoken prompt per object and an effect sound per object
(SPEC-scene-cause-effect-task.md 4.7, section 9 Q2 = A), and Scanning Search's spoken sample
(:class:`SearchAudio`, SPEC-scanning-search-cues.md 4.3).

Files, read only, under ``<assets>/scenes/<scene>/audio/``: ``<language>/prompt_<object>.wav`` and
``sfx/<object>.wav``. One cached :class:`QSoundEffect` per file that exists, loaded when the run
is built so the first prompt is not late; a file that is missing (the art and audio arrive in
step 6) is simply silent, never an error. :class:`~src.app.GuiFeedback` owns one and forwards the
feedback bus's ``on_prompt`` / ``on_effect`` / ``on_stop_audio`` to it.

Imports PySide6, so it is only imported by the GUI path, like :mod:`.canvas`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from ..tasks.choice_layout import OBJECTS, effect_wav_path, prompt_wav_path
from ..tasks.search_cues import MATCH_SAMPLE, SHAPE_NAMES, TASK_ID, normalise_search_mode
from ..tasks.search_cues import prompt_wav_path as shape_prompt_wav_path

# Below full volume, like the hit and miss cues (SPEC-2026-09-02.md item 4): nothing may startle.
VOLUME = 0.6


class SceneAudio:
    def __init__(self, scene: str, language: str, root: Path | None = None) -> None:
        self._prompts: dict[str, QSoundEffect] = {}
        self._effects: dict[str, QSoundEffect] = {}
        for obj in OBJECTS:
            self._load(self._prompts, obj.id, prompt_wav_path(scene, language, obj.id, root))
            self._load(self._effects, obj.id, effect_wav_path(scene, obj.id, root))

    @classmethod
    def from_task_config(cls, task_cfg: dict[str, Any], root: Path | None = None) -> SceneAudio | None:
        """The audio of a task whose config names a ``scene`` (Choice-making); ``None`` for
        every other task."""
        scene = task_cfg.get("scene")
        if not scene:
            return None
        return cls(str(scene), str(task_cfg.get("language", "en")), root)

    @staticmethod
    def _load(cache: dict[str, QSoundEffect], object_id: str, path: Path) -> None:
        if not path.is_file():
            return
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(VOLUME)
        cache[object_id] = effect

    def on_prompt(self, object_id: str) -> None:
        self.stop()  # one voice at a time: a prompt that restarts (after a pause) starts over
        self._play(self._prompts.get(object_id))

    def on_effect(self, object_id: str, modelled: bool) -> None:
        self._play(self._effects.get(object_id))

    def stop(self) -> None:
        for effect in (*self._prompts.values(), *self._effects.values()):
            if effect.isPlaying():
                effect.stop()

    @staticmethod
    def _play(effect: QSoundEffect | None) -> None:
        if effect is not None:
            effect.play()


class SearchAudio:
    """Scanning Search's spoken sample in Match the sample: ``scanning/audio/<language>/prompt_<shape>.wav``
    for each of the six shapes, one cached :class:`QSoundEffect` per file that exists, loaded when the
    run is built. A missing file is silent (the task then shows the sample for ``sample_ms`` alone).
    Offers the same hooks as :class:`SceneAudio`, so :class:`~src.app.GuiFeedback` forwards to either."""

    def __init__(self, language: str, root: Path | None = None) -> None:
        self._prompts: dict[str, QSoundEffect] = {}
        for shape in SHAPE_NAMES:
            SceneAudio._load(self._prompts, shape, shape_prompt_wav_path(language, shape, root))

    @classmethod
    def from_task_config(cls, task_cfg: dict[str, Any], root: Path | None = None) -> SearchAudio | None:
        """The audio of a Scanning Search run whose search mode is Match the sample; ``None`` for
        every other task and for Pop-out (it speaks nothing)."""
        mode = normalise_search_mode(task_cfg.get("search_mode"))
        if task_cfg.get("task_id") != TASK_ID or mode != MATCH_SAMPLE:
            return None
        return cls(str(task_cfg.get("language", "en")), root)

    def on_prompt(self, object_id: str) -> None:
        self.stop()  # one voice at a time
        SceneAudio._play(self._prompts.get(object_id))

    def on_effect(self, object_id: str, modelled: bool) -> None:
        """Scanning Search has no effect sounds."""

    def stop(self) -> None:
        for effect in self._prompts.values():
            if effect.isPlaying():
                effect.stop()
