"""Choice-making: a spoken prompt names one of eight buttons, the chosen object comes alive.

SPEC-scene-cause-effect-task.md 4.1-4.3 and 4.9 (engine side). One trial::

    prompt plays (selection blocked) -> the child selects a button -> the effect plays -> pause

* The prompt names an object; the response clock (``t_selectable_start_ns``, reaction time,
  the timeout) starts at the END of the prompt (H4, H9).
* **Any** of the eight buttons can be selected, with the test's own selection method (H5): a
  completed dwell or a switch press on a wrong button is a ``MISS_CLICK`` and the trial goes
  on; looking at the scene or a gap selects nothing. The base task hit-tests the target only,
  so this task has its own ``update``; ``BaseTask`` is untouched and the four other tasks
  behave exactly as before.
* A hit plays the target object's effect (no generic hit cue); a timeout plays it once as a
  model (``modelled``, H7); a wrong button plays the generic miss cue and no effect (H6).
  The effect is the ``RESULT`` phase, the pause after it (``post_effect_ms``) the ``ITI``.

The canvas draws the scene from :meth:`ChoiceMakingTask.scene_spec` (step 4); this module has
no rendering and plays no audio itself: it asks the feedback bus to (``on_prompt``,
``on_effect``, ``on_stop_audio``) and reads the prompt WAVs' lengths, read only, to time the
prompt. Layout, objects and trial order: :mod:`.choice_layout`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engine.target_size import CellGeometry
from ..inputs.base import Pointer, norm_to_px
from .base_task import BaseTask, FrameResult, Phase, TargetSpec
from .choice_layout import (
    ASSETS_ROOT,
    DEFAULT_PROMPT_MS,
    OBJECTS,
    SceneObject,
    board_geometry,
    button_at,
    button_centre_norm,
    button_rect,
    prompt_wav_path,
    scene_rect,
    side_of,
    trial_order,
    wav_duration_ms,
)
from .choice_scene import SceneManifest, load_manifest, normalise_idle

DEFAULT_POST_EFFECT_MS = 1000


class ChoiceMakingTask(BaseTask):
    # Where the scene's audio lives (``<assets>/scenes/<scene>/audio/...``); read only. A test
    # points it at a temp folder.
    assets_root: Path = ASSETS_ROOT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # State the frame loop and ``scene_spec`` read, set before ``BaseTask`` builds the targets.
        self._last_t_ns = 0
        self._prompt_object: SceneObject | None = None  # from the prompt start to the effect's end
        self._prompt_end_ns = 0
        self._prompt_over = True
        self._effect: dict[str, Any] | None = None
        self._prompt_lengths: dict[str, tuple[float, str]] = {}
        self._scene_manifest: SceneManifest | None = None
        self._hover_slot = -1  # the button the pointer is on right now
        self._dwell_slot = -1  # the button the running dwell is on
        super().__init__(*args, **kwargs)

    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        # The gap wanted between neighbouring buttons, in px, resolved from ``grid.gap`` by
        # ``apply_grid_gap`` exactly as for Grid Click; None is the standard board.
        gap_px = (cfg.get("grid") or {}).get("gap_px")
        self.gap_px: float | None = float(gap_px) if gap_px else None
        self._gap_reported = False
        self.gap_capped_px: float | None = None
        self.post_effect_ns = int(float(cfg.get("post_effect_ms", DEFAULT_POST_EFFECT_MS)) * 1e6)
        self.visual_cue = bool(cfg.get("visual_cue", False))
        # The picture's idle life between trials (N3): off / blinks / blinks_bob; the canvas reads it.
        self.idle_animation = normalise_idle(cfg.get("idle_animation"))
        self.scene_name = str(cfg.get("scene", "park"))
        self.language = str(cfg.get("language", "en"))
        # The button centres, for the report's map outlines and the canvas's stand-in outlines.
        self.layout_slots = [button_centre_norm(s) for s in range(len(OBJECTS))]
        n_trials = max(1, int(cfg.get("trials", 16)))
        targets = []
        for i, slot in enumerate(trial_order(n_trials, self.rng)):
            x, y = button_centre_norm(slot)
            # No configured radius: the button is sized by the 7 x 5 grid (H12).
            targets.append(TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=0.0, slot_index=slot))
        return targets

    # -- the prompt's length ---------------------------------------------------------------------

    def prompt_length(self, obj: SceneObject) -> tuple[float, str]:
        """``(ms, source)`` of ``obj``'s spoken prompt (SPEC section 9, Q1 = B): measured from
        ``audio/<language>/prompt_<object>.wav`` of the configured scene (``source`` ``"wav"``),
        else :data:`DEFAULT_PROMPT_MS` (``"default"``) when the file is missing or unreadable.
        Measured once per object and run."""
        if obj.id not in self._prompt_lengths:
            path = prompt_wav_path(self.scene_name, self.language, obj.id, self.assets_root)
            measured = wav_duration_ms(path)
            self._prompt_lengths[obj.id] = (
                (measured, "wav") if measured is not None else (float(DEFAULT_PROMPT_MS), "default")
            )
        return self._prompt_lengths[obj.id]

    def prompt_ms(self, obj: SceneObject) -> float:
        """How long the spoken prompt of ``obj`` lasts, in ms."""
        return self.prompt_length(obj)[0]

    @property
    def manifest(self) -> SceneManifest:
        """The scene manifest (4.7): ``scene.yaml`` of the configured scene under ``assets_root``,
        else the built-in placeholder scene. Loaded once per run, read only; a file that could not
        be used is said so once in the session log."""
        if self._scene_manifest is None:
            self._scene_manifest = load_manifest(self.scene_name, self.assets_root)
            if self._scene_manifest.warning:
                self._log(f"Scene manifest: {self._scene_manifest.warning}.")
        return self._scene_manifest

    def effect_ms(self, obj: SceneObject) -> float:
        """How long ``obj``'s effect plays: its duration in the scene manifest (4.4, per object),
        which is the 4.4 default until a scene file says otherwise."""
        return float(self.manifest.object(obj.id).effect.duration_ms)

    @property
    def prompt_label(self) -> str:
        """The English label of the prompted object from the prompt's start to the effect's end,
        else empty: the run bar's "Prompt: ..." line (W2)."""
        return self._prompt_object.label if self._prompt_object is not None else ""

    # -- geometry -----------------------------------------------------------------------------

    def _geometry(self) -> CellGeometry:
        """How a button is drawn and hit-tested right now, from the live canvas size (it
        resizes mid-run, so never baked in at build time)."""
        return board_geometry(self.screen_w, self.screen_h, self.gap_px)

    def _button_at(self, px: float, py: float) -> int:
        return button_at(px, py, self.screen_w, self.screen_h, self._geometry())

    def effective_radius_px(self, target: TargetSpec) -> float:
        """The largest circle that fits a button (what ``trials.csv`` records as the target's
        radius, and the ring the canvas can size from)."""
        return self._geometry().fit_radius_px

    def hit_test(
        self, target: TargetSpec, cx_px: float, cy_px: float, px: float, py: float
    ) -> bool:
        """On the target BUTTON (its hit area, not a circle). Used by the switch path."""
        return self._button_at(px, py) == target.slot_index

    def is_selectable(self, target: TargetSpec, elapsed_ns: int) -> bool:
        """False while the prompt plays (4.1); ``elapsed_ns`` is from the trial start."""
        return elapsed_ns >= self._prompt_end_ns - self._trial_start_ns

    # -- one frame ----------------------------------------------------------------------------

    def update(self, t_ns: int, pointer: Pointer) -> FrameResult:
        if self._paused_at_ns is not None:
            # Nothing advances while paused: not the prompt, not the effect (A8).
            return self._paused_frame(pointer)
        self._last_t_ns = t_ns
        just_finished = False

        if self._phase is Phase.READY and self._preroll_over(t_ns):
            self._start_trial(t_ns)

        target = self.targets[self._trial_index] if 0 <= self._trial_index < len(self.targets) else None
        px, py = self.pointer_to_canvas_px(pointer)
        self._trace.observe(t_ns, pointer.valid, px, py, pointer.x, pointer.y)
        slot = self._button_at(px, py) if pointer.valid else -1
        self._hover_slot = slot
        phase_in = self._phase
        press_where = phase_in.name.lower()
        press_judged = False
        dwell_progress = 0.0
        selectable = False
        on_target = False

        if self._phase is Phase.WAIT_INPUT and target is not None and self._current is not None:
            prompting = self._prompt_playing(t_ns)
            selectable = not prompting
            on_target = slot == target.slot_index
            self._entries.update(t_ns, pointer.valid, on_target)
            if on_target and self._current.t_first_gaze_on_target_ns is None:
                self._current.t_first_gaze_on_target_ns = t_ns

            clicked = hit = False
            chosen = -1
            miss_extra: dict[str, Any] = {}
            if prompting:
                # Selection is blocked while the prompt plays (A3): no dwell builds up, and a
                # press is logged and counts for nothing.
                press_where = "prompt"
                if self.dwell is not None:
                    self.dwell.reset()
                self._dwell_slot = -1
            elif not self._switch_rules:
                dwell_progress, clicked, chosen = self._dwell_frame(t_ns, slot)
                hit = clicked and chosen == target.slot_index
            elif pointer.clicked:
                press_judged = True
                if self._debounced(t_ns):
                    self.ignore_press(t_ns, "target", pointer, reason="refractory")
                else:
                    self._last_press_ns = t_ns
                    clicked = True
                    cx_px, cy_px = norm_to_px(target.x_norm, target.y_norm, self.screen_w, self.screen_h)
                    hit, miss_extra = self._switch_press(t_ns, pointer, px, py, target, cx_px, cy_px, True)
                    point = self._trace.at_press(t_ns, pointer.valid, px, py, pointer.x, pointer.y)
                    chosen = self._button_at(point.px, point.py) if point is not None else -1

            if clicked and not hit:
                self._current.attempts += 1
                self._record_event(
                    "MISS_CLICK", t_ns, x=pointer.x, y=pointer.y, selectable=True,
                    selected_slot=chosen,
                    selected_object=OBJECTS[chosen].id if chosen >= 0 else None,
                    **miss_extra,
                )
                if self.feedback is not None:
                    self.feedback.on_miss(*self.pointer_to_canvas_norm(pointer))
            elif hit:
                self._current.attempts += 1
                self._current.t_click_ns = t_ns
                self._current.is_hit = True
                self._finish_trial(t_ns, timed_out=False)
                just_finished = True
            elif selectable and t_ns - self._prompt_end_ns >= self.timeout_ns:
                self._end_by_time(t_ns)
                just_finished = True

        elif self._phase is Phase.RESULT:
            if t_ns >= self._phase_deadline_ns:
                self._end_effect()

        elif self._phase is Phase.ITI:
            if t_ns >= self._phase_deadline_ns:
                if self._trial_index + 1 >= len(self.targets):
                    self._phase = Phase.DONE
                else:
                    self._start_trial(t_ns)

        if pointer.clicked and self._switch_rules and not press_judged:
            # A press with no button choice open (prompt, effect, pause, pre-roll, the end).
            self.ignore_press(t_ns, press_where, pointer)

        target = self.targets[self._trial_index] if 0 <= self._trial_index < len(self.targets) else None
        return FrameResult(
            phase=self._phase,
            trial_index=self._trial_index,
            target=target,
            # None on purpose: the prompted button must not be marked (H4), and the dwell ring
            # and glow belong to the button the pointer is on, not to the target; the canvas
            # takes both from scene_spec (``hover_slot``, ``cue_slot``).
            target_xy_norm=None,
            dwell_progress=dwell_progress,
            pointer=pointer,
            just_finished_trial=just_finished,
            cursor_xy_norm=self.pointer_to_canvas_norm(pointer),
            selectable=selectable,
            on_target=on_target,
            target_radius_px=self.effective_radius_px(target) if target is not None else 0.0,
        )

    def _dwell_frame(self, t_ns: int, slot: int) -> tuple[float, bool, int]:
        """One dwell machine on whichever button the pointer is in; moving to another button
        starts it over (H5). ``(progress, completed, button)``."""
        if slot >= 0 and slot != self._dwell_slot:
            self.dwell.reset()
            self._dwell_slot = slot
        state = self.dwell.update(t_ns, slot >= 0)
        if self.feedback is not None and state.progress > 0 and self._dwell_slot >= 0:
            self.feedback.on_progress(*button_centre_norm(self._dwell_slot), state.progress)
        return state.progress, state.triggered, self._dwell_slot

    # -- the prompt ---------------------------------------------------------------------------

    def _start_trial(self, t_ns: int) -> None:
        geometry = self._geometry()
        if geometry.capped and not self._gap_reported:
            self._gap_reported = True
            self.gap_capped_px = geometry.gap_px
            self._record_event(
                "GAP_CAPPED", t_ns, requested_px=round(geometry.wanted_px, 1),
                used_px=round(geometry.gap_px, 1), rows=5, cols=7,
            )
            self._log(
                f"Cell gap limited to ≈{geometry.gap_px:.0f} px (wanted "
                f"≈{geometry.wanted_px:.0f} px) to fit the 7 x 5 board."
            )
        super()._start_trial(t_ns)
        assert self._current is not None
        _ = self.manifest  # read the scene file now, not in the middle of an effect
        obj = OBJECTS[self.targets[self._trial_index].slot_index]
        prompt_ms, source = self.prompt_length(obj)
        self._prompt_object = obj
        self._prompt_end_ns = t_ns + int(prompt_ms * 1e6)
        self._prompt_over = False
        self._dwell_slot = -1
        self._current.prompt_object = obj.id
        self._current.button_side = side_of(obj.slot)
        self._record_event(
            "PROMPT_START", t_ns, trial=self._trial_index, object=obj.id, slot=obj.slot,
            side=side_of(obj.slot), duration_ms=round(prompt_ms, 1), duration_source=source,
        )
        self._audio("on_prompt", obj.id)

    def _prompt_playing(self, t_ns: int) -> bool:
        """Whether the prompt is still playing at ``t_ns``. On the first frame it is over, the
        response clock starts at the prompt's end, not at this frame (H4)."""
        if self._prompt_over:
            return False
        if t_ns < self._prompt_end_ns:
            return True
        assert self._current is not None and self._prompt_object is not None
        self._prompt_over = True
        self._current.t_selectable_start_ns = self._prompt_end_ns
        self._record_event(
            "PROMPT_END", self._prompt_end_ns, trial=self._trial_index, object=self._prompt_object.id
        )
        return False

    # -- the end of a trial and the effect -----------------------------------------------------

    def _trial_cue(self) -> None:
        """No generic hit or miss cue at a trial's end: a hit is rewarded by the object's own
        effect and sound (H6), and a timeout by the modelled effect (H7)."""

    def _finish_trial(self, t_ns: int, timed_out: bool, skipped: bool = False) -> None:
        trial = self._current
        assert trial is not None and self._prompt_object is not None
        obj = self._prompt_object
        if trial.is_hit:
            trial.selected_object = obj.id
            assert trial.t_click_ns is not None
            trial.rt_ms = (trial.t_click_ns - self._prompt_end_ns) / 1e6
        super()._finish_trial(t_ns, timed_out, skipped)
        if skipped:
            # Nothing to show for a skip: only the pause before the next prompt. The prompt
            # that may still be playing is cut.
            self._prompt_object = None
            self._phase_deadline_ns = t_ns + self.post_effect_ns
            self._audio("on_stop_audio")
            return
        self._start_effect(t_ns, obj, modelled=timed_out)

    def _start_effect(self, t_ns: int, obj: SceneObject, modelled: bool) -> None:
        duration_ms = self.effect_ms(obj)
        self._effect = {
            "object": obj.id, "t_start": t_ns, "duration_ms": duration_ms, "modelled": modelled,
        }
        self._phase = Phase.RESULT
        self._phase_deadline_ns = t_ns + int(duration_ms * 1e6)
        self._record_event(
            "EFFECT_START", t_ns, trial=self._trial_index, object=obj.id, modelled=modelled,
            duration_ms=duration_ms,
        )
        self._audio("on_effect", obj.id, modelled)

    def _end_effect(self) -> None:
        """The effect is over: the scene is back to its idle picture, then the pause (A5)."""
        assert self._effect is not None
        end_ns = self._phase_deadline_ns
        self._record_event(
            "EFFECT_END", end_ns, trial=self._trial_index, object=self._effect["object"],
            modelled=self._effect["modelled"],
        )
        self._effect = None
        self._prompt_object = None
        self._phase = Phase.ITI
        self._phase_deadline_ns = end_ns + self.post_effect_ns

    def _audio(self, hook: str, *args: Any) -> None:
        """Ask the feedback bus to play or stop a sound (``on_prompt``, ``on_effect``,
        ``on_stop_audio``). A bus without the hook (a test double) is simply silent."""
        method = getattr(self.feedback, hook, None)
        if method is not None:
            method(*args)

    def pause(self, t_ns: int) -> bool:
        interrupted = super().pause(t_ns)
        if interrupted:  # the trial in flight was dropped; its prompt goes with it
            self._prompt_object = None
            self._dwell_slot = -1
        # A sound cannot be held and resumed: whatever plays (prompt or effect) is cut. A
        # prompt starts again with its trial; an effect's animation continues without its sound.
        self._audio("on_stop_audio")
        return interrupted

    def resume(self, t_ns: int) -> None:
        """End a pause. A running effect continues where it stopped (A8); the prompt of an
        interrupted trial starts over with the trial (``BaseTask.pause``)."""
        paused_at = self._paused_at_ns
        super().resume(t_ns)
        if paused_at is not None and self._phase is Phase.RESULT and self._effect is not None:
            paused_ns = max(0, t_ns - paused_at)
            self._effect["t_start"] += paused_ns
            self._phase_deadline_ns += paused_ns

    # -- what the renderer needs ---------------------------------------------------------------

    def scene_spec(self) -> dict[str, Any]:
        """The scene for the renderer (4.1), from the live canvas size; re-read every tick.

        ``buttons`` and ``scene_rect`` are ``(x, y, w, h)`` in canvas px. ``effect`` is ``None``
        or the effect in flight, with ``elapsed_ms`` as of the last frame (so a pause freezes
        it). ``prompt_object`` is the prompted object's id from the prompt's start to the
        effect's end (the run bar's "Prompt: ..." line, W2); ``cue_slot`` is the button to pulse
        when the visual cue is on (S3); ``hover_slot`` the button the pointer is on (the glow
        of W3 and the dwell ring belong to it); ``idle_animation`` the picture's idle life (N3)."""
        w, h = self.screen_w, self.screen_h
        geometry = self._geometry()
        effect = None
        if self._effect is not None:
            elapsed = (self._last_t_ns - self._effect["t_start"]) / 1e6
            effect = {**self._effect, "elapsed_ms": min(max(elapsed, 0.0), self._effect["duration_ms"])}
        cue_slot = -1
        if self.visual_cue and self._phase is Phase.WAIT_INPUT and self._prompt_object is not None:
            cue_slot = self._prompt_object.slot
        return {
            "mode": "scene",
            "theme": self.scene_name,
            "buttons": [
                {
                    "slot": o.slot, "object": o.id, "label": o.label, "side": side_of(o.slot),
                    "rect": button_rect(o.slot, w, h, geometry),
                }
                for o in OBJECTS
            ],
            "scene_rect": scene_rect(w, h),
            "effect": effect,
            "prompt_object": self._prompt_object.id if self._prompt_object is not None else None,
            "cue_slot": cue_slot,
            "hover_slot": self._hover_slot,
            "idle_animation": self.idle_animation,
        }

    def _shrink_details(self) -> dict[str, Any]:
        return {"rows": 5, "cols": 7}
