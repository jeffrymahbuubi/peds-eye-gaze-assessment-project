"""Scanning selection task (plan section 5.5).

Several icons are arranged on screen; one lights up as the target and the child
selects it. Distractor icons are visual only (rendered by the GUI); the metric
of interest is reaction time and wrong-selection count (tracked as attempts).

**Arrangement + shapes ported from ``resources/diki`` (SPEC-diki-design-audit.md
S3.4).** The original version here only ever laid icons out on a single
horizontal row -- not real visual search, since the child never has to look up
or down. ``layout.arrangement`` now supports ``row`` (kept for compatibility),
``ring``, and ``grid`` (new default): a genuine 2D field the child has to
actually scan. Icons are also now assigned one of 6 distinct *shapes*, not just
positions, rendered by ``TaskCanvas`` -- distinguishing by form (not just
brightness/colour) is what makes this a search task rather than a pop-out task.

**Search modes and the start dot (SPEC-scanning-search-cues.md 4.2-4.4).** ``search_mode`` is
``pop_out`` (above, the default) or ``match_sample``: the target's shape is shown and spoken alone
at the centre, then the field appears with every icon bright in the target colour and a fresh
shuffle of the shapes. ``start_dot`` puts a small dot at the centre before each trial's field. Both
are *pre-trial phases*: the trial (its record, its clock, its timeout) starts when the field
appears, so reaction time is measured from there; the phases before it are reported through
``scene_spec`` and the ``START_DOT_*`` / ``SAMPLE_START`` events.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..engine.prompt_text import extent_px_for
from ..engine.target_size import (
    DEFAULT_VIEWING_DISTANCE_MM,
    ICON_DRAW_FRAC,
    REFERENCE_MM_PER_PX,
    fit_icon_radius_px,
)
from ..inputs.base import Pointer, circle_contains
from ..inputs.eye_input import DwellConfig, DwellSelector
from .base_task import BaseTask, FrameResult, Phase, TargetSpec
from .choice_layout import ASSETS_ROOT, wav_duration_ms
from .search_cues import (
    MATCH_SAMPLE,
    POP_OUT,
    SAMPLE_MS,
    SAMPLE_TEXT,
    SAMPLE_TEXT_DEG,
    SHAPE_NAMES,
    START_DOT_CAPTURE_DEG,
    START_DOT_DEG,
    START_DOT_HOLD_MS,
    START_DOT_TIMEOUT_MS,
    WrongIconDwell,
    draw_field,
    normalise_search_mode,
    prompt_wav_path,
    reminder_placement,
)

# The pre-trial stages, in the order they run; also the ``stage`` of ``scene_spec`` and the ``phase``
# a switch press made during one is logged under (``SWITCH_IGNORED``).
STAGE_START_DOT, STAGE_SAMPLE, STAGE_FIELD, STAGE_BLANK = "start_dot", "sample", "field", "blank"


def scanning_layout_slots(n_icons: int, arrangement: str, margin: float) -> list[tuple[float, float]]:
    """Normalized canvas positions of the icon slots for an arrangement. Module
    level so the task and the Task settings dialog's shrink hint lay icons out by
    the one formula."""
    span = 1.0 - 2 * margin
    if arrangement == "row":
        return [(margin + span * (i + 0.5) / n_icons, 0.5) for i in range(n_icons)]
    if arrangement == "ring":
        cx, cy, r = 0.5, 0.5, 0.32
        return [
            (
                cx + r * math.cos(2 * math.pi * i / n_icons - math.pi / 2),
                cy + r * math.sin(2 * math.pi * i / n_icons - math.pi / 2),
            )
            for i in range(n_icons)
        ]
    # grid (default): favour more columns than rows, because the screen is
    # wider than it is tall -- round() here would give 6 icons a 2x3
    # layout, leaving large empty margins left and right.
    cols = max(1, math.ceil(n_icons ** 0.5))
    rows = max(1, -(-n_icons // cols))  # ceil division
    slots: list[tuple[float, float]] = []
    for i in range(n_icons):
        r, c = divmod(i, cols)
        slots.append(
            (
                margin + span * (c + 0.5) / cols,
                margin + span * (r + 0.5) / rows,
            )
        )
    return slots


@dataclass(slots=True)
class _Pre:
    """The phases before trial ``trial``'s field appears, in ``stages`` order (4.3, 4.4)."""

    trial: int
    stages: list[str]
    index: int = 0
    stage_ns: int = 0  # when the current stage began
    end_ns: int = 0  # the sample stage's end
    hold: DwellSelector | None = None  # the start dot's 300 ms of gaze within 2 deg

    @property
    def stage(self) -> str:
        return self.stages[self.index]


class ScanningTask(BaseTask):
    # Where the spoken prompts live (``<assets>/scanning/audio/<language>/``); read only. A test
    # points it at a temp folder.
    assets_root: Path = ASSETS_ROOT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # State the frame loop and ``scene_spec`` read, set before ``BaseTask`` builds the targets.
        self._pre: _Pre | None = None
        self._dot_result: tuple[float | None, bool] | None = None  # (ms to fixate or None, timed out)
        self._sample_lengths: dict[str, tuple[float, str]] = {}
        self._frame_pointer: Pointer | None = None  # this frame's pointer, for a trial that starts in it
        self._wrong: WrongIconDwell | None = None  # Match the sample with Dwell: the wrong-icon dwell
        super().__init__(*args, **kwargs)

    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        layout = cfg.get("layout", {})
        n_icons = int(layout.get("n_icons", 4))
        radius = float(layout.get("radius_px", 80))
        arrangement = str(layout.get("arrangement", "grid"))
        margin = float(layout.get("margin_frac", 0.14))
        n_trials = int(cfg.get("trials", 16))

        self.arrangement = arrangement
        self.icon_slots = self._layout_slots(n_icons, arrangement, margin)
        self.icon_shapes = [i % 6 for i in range(len(self.icon_slots))]
        # Kept for the fixture-generation tool and the existing GUI
        # dim-outline fallback -- see BaseTask.layout_slots's own docstring.
        # scanning now draws real shapes instead (scene_spec's "icons" mode),
        # but this alias stays so nothing that reads task.layout_slots breaks.
        self.layout_slots = list(self.icon_slots)

        # The search mode and the start dot (SPEC-scanning-search-cues.md 4.2-4.4). The cues' sizes
        # are by visual angle, resolved into the config by ``apply_search_cues``; the reference
        # monitor's when nothing did (tests, headless replay).
        self.search_mode = normalise_search_mode(cfg.get("search_mode"))
        self.start_dot = cfg.get("start_dot") is True
        self.sample_reminder = cfg.get("sample_reminder") is True  # off by default (4.3, revision 2)
        self.sample_ms = float(cfg.get("sample_ms", SAMPLE_MS))
        self.language = str(cfg.get("language", "en"))
        self.start_dot_px = self._deg_px("start_dot_px", START_DOT_DEG)
        self.start_dot_capture_px = self._deg_px("start_dot_capture_px", START_DOT_CAPTURE_DEG)
        self.sample_text_px = self._deg_px("sample_text_px", SAMPLE_TEXT_DEG)

        targets: list[TargetSpec] = []
        # Per trial: the target's shape and the shape in every slot. Pop-out's field is the fixed
        # one above; Match the sample draws a fresh field after each target slot (S6), from the run's
        # RNG, so a seed gives the same run -- and Pop-out draws nothing more than it always did.
        self.trial_target_shapes: list[int] = []
        self.trial_field_shapes: list[list[int]] = []
        for i in range(n_trials):
            slot = self.rng.randrange(len(self.icon_slots))
            x, y = self.icon_slots[slot]
            targets.append(
                TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius, slot_index=slot)
            )
            if self.search_mode == MATCH_SAMPLE:
                target_shape, shapes = draw_field(self.rng, len(self.icon_slots), slot)
            else:
                target_shape, shapes = self.icon_shapes[slot], self.icon_shapes
            self.trial_target_shapes.append(target_shape)
            self.trial_field_shapes.append(list(shapes))
        return targets

    def _deg_px(self, key: str, degrees: float) -> float:
        return float(
            self.task_cfg.get(key)
            or extent_px_for(degrees, REFERENCE_MM_PER_PX, DEFAULT_VIEWING_DISTANCE_MM)
        )

    def _layout_slots(
        self, n_icons: int, arrangement: str, margin: float
    ) -> list[tuple[float, float]]:
        return scanning_layout_slots(n_icons, arrangement, margin)

    # -- icon fit (SPEC-target-size-and-motion-paths.md S11.3) ----------------

    def effective_radius_px(self, target: TargetSpec) -> float:
        """The configured hit radius, capped so the *drawn* icons (at
        :data:`ICON_DRAW_FRAC` of it) neither overlap each other nor cross the
        canvas edge -- :func:`~src.engine.target_size.fit_icon_radius_px`.
        Returned as a hit radius so the canvas, which scales it by
        ``ICON_DRAW_FRAC``, draws the capped icon; every icon, distractors
        included, shrinks together. Per frame: the canvas resizes mid-run."""
        cap = fit_icon_radius_px(self.icon_slots, self.screen_w, self.screen_h)
        return min(target.radius_px, cap / ICON_DRAW_FRAC)

    def hit_test(
        self, target: TargetSpec, cx_px: float, cy_px: float, px: float, py: float
    ) -> bool:
        """The usual circle test (effective radius + jitter) AND the point is
        closer to the target's slot than to any other slot, so a look at a
        neighbouring icon never counts as the target in any arrangement."""
        if not circle_contains(
            cx_px, cy_px, self.effective_radius_px(target) + self.jitter_px, px, py
        ):
            return False
        own = math.hypot(px - cx_px, py - cy_px)
        for index, (x_norm, y_norm) in enumerate(self.icon_slots):
            if index == target.slot_index:
                continue
            if math.hypot(px - x_norm * self.screen_w, py - y_norm * self.screen_h) < own:
                return False
        return True

    def _shrink_details(self) -> dict:
        return {"n_icons": len(self.icon_slots), "arrangement": self.arrangement}

    def _icon_at(self, px: float, py: float) -> int:
        """The icon the canvas point is on, else -1: the nearest slot, when the point lies within
        the hit radius plus the jitter margin of it -- :meth:`hit_test`'s rule, for any slot."""
        best, best_d = -1, math.inf
        for index, (x_norm, y_norm) in enumerate(self.icon_slots):
            d = math.hypot(px - x_norm * self.screen_w, py - y_norm * self.screen_h)
            if d < best_d:
                best, best_d = index, d
        reach = self.effective_radius_px(self.targets[0]) + self.jitter_px
        return best if best_d <= reach else -1

    def _icon_radius_px(self) -> float:
        """The radius an icon is drawn at right now (the hit radius scaled by ``ICON_DRAW_FRAC``)."""
        return self.effective_radius_px(self.targets[0]) * ICON_DRAW_FRAC if self.targets else 0.0

    # -- one frame ----------------------------------------------------------------------------

    def update(self, t_ns: int, pointer: Pointer) -> FrameResult:
        if self._paused_at_ns is not None:
            return self._paused_frame(pointer)
        if self._pre is None and self._pre_due(t_ns):
            self._begin_pre(t_ns)
        if self._pre is not None:
            stage = self._pre.stage
            if not self._advance_pre(t_ns, pointer):
                if pointer.clicked and self._switch_rules:
                    self.ignore_press(t_ns, stage, pointer)  # a press counts for nothing before the field
                return self._pre_frame(pointer)
            # The phases are over: the field appears this frame, and the trial starts below.
        self._frame_pointer = pointer
        self._note_icons(t_ns, pointer)
        return super().update(t_ns, pointer)

    def _note_icons(self, t_ns: int, pointer: Pointer) -> None:
        """Match the sample, on this frame's pointer and before the frame's selection may end the
        trial and write its row: the first icon the pointer enters after the field appears (4.6), and
        a completed dwell on an icon that is not the target, a wrong selection (4.3, 4.6). A wrong
        selection changes nothing on screen and plays nothing; the trial goes on."""
        trial = self._current
        if self.search_mode != MATCH_SAMPLE or self._phase is not Phase.WAIT_INPUT or trial is None:
            return
        slot = self._icon_at(*self.pointer_to_canvas_px(pointer)) if pointer.valid else -1
        index = self._trial_index
        if slot >= 0 and trial.first_icon_looked_at_slot is None:
            trial.first_icon_looked_at_slot = slot
            trial.first_icon_looked_at_shape = SHAPE_NAMES[self.trial_field_shapes[index][slot]]
        if self._wrong is None:
            return
        wrong = self._wrong.update(t_ns, pointer.valid, slot, self.targets[index].slot_index)
        if wrong is not None:
            self._count_wrong(t_ns, wrong)

    def _count_wrong(self, t_ns: int, slot: int) -> None:
        """A wrong selection: the icon in ``slot`` (not the target) was selected, by a completed dwell
        or a switch press. Counted in the trial's row and announced; nothing else happens."""
        trial, index = self._current, self._trial_index
        assert trial is not None
        shape = SHAPE_NAMES[self.trial_field_shapes[index][slot]]
        trial.wrong_selections = (trial.wrong_selections or 0) + 1
        trial.wrong_selection_shapes = ";".join(filter(None, (trial.wrong_selection_shapes, shape)))
        self._record_event("WRONG_SELECTION", t_ns, trial=index, slot=slot, shape=shape)

    def _switch_press(
        self, t_ns: int, pointer: Pointer, px: float, py: float, target: TargetSpec,
        cx_px: float, cy_px: float, selectable: bool,
    ) -> tuple[bool, dict[str, Any]]:
        """A counted press, judged as ever (a miss is a ``MISS_CLICK`` and a click error). In Match the
        sample one made where the pointer is on an icon that is not the target is also a wrong
        selection (4.6): judged at the same point as the press, so a blink's fallback counts alike."""
        result = super()._switch_press(t_ns, pointer, px, py, target, cx_px, cy_px, selectable)
        if self.search_mode == MATCH_SAMPLE:
            point = self._trace.at_press(t_ns, pointer.valid, px, py, pointer.x, pointer.y)
            slot = self._icon_at(point.px, point.py) if point is not None else -1
            if slot >= 0 and slot != target.slot_index:
                self._count_wrong(t_ns, slot)
        return result

    @property
    def trial_number(self) -> int:
        """1-based number of the trial the run is on; while its start dot or sample shows, the
        trial that comes next (the run bar names the trial being prepared)."""
        return super().trial_number + (1 if self._pre is not None else 0)

    # -- the phases before the field (4.3, 4.4) -------------------------------------------------

    def _pre_due(self, t_ns: int) -> bool:
        """Whether the next trial's start dot / sample begins now: the pre-roll is over, or the
        pause after the last trial (and there is a next one)."""
        if not (self.start_dot or self.search_mode == MATCH_SAMPLE):
            return False
        if self._phase is Phase.READY:
            return bool(self.targets) and self._preroll_over(t_ns)
        return (
            self._phase is Phase.ITI
            and t_ns >= self._phase_deadline_ns
            and self._trial_index + 1 < len(self.targets)
        )

    def _begin_pre(self, t_ns: int) -> None:
        stages = ([STAGE_START_DOT] if self.start_dot else []) + (
            [STAGE_SAMPLE] if self.search_mode == MATCH_SAMPLE else []
        )
        self._pre = _Pre(trial=self._trial_index + 1, stages=stages)
        self._dot_result = None
        self._phase = Phase.SHOW_TARGET  # no trial is running: nothing to select, nothing to skip
        self._enter_stage(t_ns)

    def _enter_stage(self, t_ns: int) -> None:
        pre = self._pre
        assert pre is not None
        pre.stage_ns = t_ns
        if pre.stage == STAGE_START_DOT:
            pre.hold = DwellSelector(DwellConfig(threshold_ms=START_DOT_HOLD_MS, refractory_ms=0.0))
            self._record_event("START_DOT_SHOWN", t_ns, trial=pre.trial)
            return
        shape = SHAPE_NAMES[self.trial_target_shapes[pre.trial]]
        duration_ms, source = self.sample_length(shape)
        pre.end_ns = t_ns + int(duration_ms * 1e6)
        self._record_event(
            "SAMPLE_START", t_ns, trial=pre.trial, shape=shape, duration_ms=round(duration_ms, 1),
            duration_source=source,
        )
        self._audio("on_prompt", shape)

    def sample_length(self, shape: str) -> tuple[float, str]:
        """``(ms, source)`` of the sample phase of ``shape``: the longer of ``sample_ms`` and its
        spoken prompt, measured from ``prompt_<shape>.wav`` (``source`` ``"wav"``); ``sample_ms``
        alone (``"default"``, said once in the session log) when the file is missing or unreadable.
        Measured once per shape and run."""
        if shape not in self._sample_lengths:
            path = prompt_wav_path(self.language, shape, self.assets_root)
            measured = wav_duration_ms(path)
            if measured is None:
                self._log(
                    f"Scanning prompt {path.name} is missing or unreadable: "
                    f"the sample lasts {self.sample_ms:.0f} ms, no voice."
                )
                self._sample_lengths[shape] = (self.sample_ms, "default")
            else:
                self._sample_lengths[shape] = (max(self.sample_ms, measured), "wav")
        return self._sample_lengths[shape]

    def _advance_pre(self, t_ns: int, pointer: Pointer) -> bool:
        """Run the current stage one frame; ``True`` once the last one is over (the phase is then
        ``READY``, so the base frame starts the trial: the field appears)."""
        pre = self._pre
        assert pre is not None
        px, py = self.pointer_to_canvas_px(pointer)
        self._trace.observe(t_ns, pointer.valid, px, py, pointer.x, pointer.y)
        if pre.stage == STAGE_START_DOT:
            assert pre.hold is not None
            near = pointer.valid and math.hypot(
                px - self.screen_w / 2.0, py - self.screen_h / 2.0
            ) <= self.start_dot_capture_px
            waited_ms = (t_ns - pre.stage_ns) / 1e6
            if pre.hold.update(t_ns, near).triggered:
                self._end_dot(t_ns, "fixated", waited_ms)
            elif waited_ms >= START_DOT_TIMEOUT_MS:
                self._end_dot(t_ns, "timeout", None)
            else:
                return False
        elif t_ns < pre.end_ns:
            return False
        pre.index += 1
        if pre.index < len(pre.stages):
            self._enter_stage(t_ns)
            return False
        self._pre = None
        self._phase = Phase.READY
        return True

    def _end_dot(self, t_ns: int, result: str, waited_ms: float | None) -> None:
        assert self._pre is not None
        self._dot_result = (waited_ms, result == "timeout")
        self._record_event(
            "START_DOT_DONE", t_ns, trial=self._pre.trial, result=result,
            elapsed_ms=round((t_ns - self._pre.stage_ns) / 1e6, 1),
        )

    def _pre_frame(self, pointer: Pointer) -> FrameResult:
        """What ``update`` reports during the start dot or the sample: no target, nothing selectable."""
        return FrameResult(
            phase=self._phase,
            trial_index=self._trial_index,
            target=None,
            target_xy_norm=None,
            dwell_progress=0.0,
            pointer=pointer,
            just_finished_trial=False,
            cursor_xy_norm=self.pointer_to_canvas_norm(pointer),
            selectable=False,
        )

    def _start_trial(self, t_ns: int) -> None:
        """The field appears: the trial starts (its clock, its timeout, ``t_selectable_start_ns``)."""
        super()._start_trial(t_ns)
        trial, index = self._current, self._trial_index
        assert trial is not None
        trial.search_mode = self.search_mode
        trial.target_shape = SHAPE_NAMES[self.trial_target_shapes[index]]
        trial.field_shapes = "|".join(SHAPE_NAMES[s] for s in self.trial_field_shapes[index])
        if self._dot_result is not None:
            trial.start_dot_ms, trial.start_dot_timeout = self._dot_result
            self._dot_result = None
        if self.search_mode == MATCH_SAMPLE:
            self._record_event("FIELD_SHOWN", t_ns, trial=index)
            # Wrong selections: a completed dwell on a wrong icon (Dwell), or a press while on one
            # (Switch, ``_switch_press``); 0 from the start, so a trial without one reads 0, not blank.
            self._wrong = WrongIconDwell(self.dwell.config) if self.dwell is not None else None
            trial.wrong_selections = 0
            if self._frame_pointer is not None:
                self._note_icons(t_ns, self._frame_pointer)  # the pointer may be on an icon at once

    def _audio(self, hook: str, *args: Any) -> None:
        """Ask the feedback bus to play or stop a sound (``on_prompt``, ``on_stop_audio``). A bus
        without the hook (a test double) is simply silent."""
        method = getattr(self.feedback, hook, None)
        if method is not None:
            method(*args)

    def pause(self, t_ns: int) -> bool:
        interrupted = super().pause(t_ns)
        if self._pre is not None:
            # The start dot or sample in progress is dropped, and its voice cut: the trial's phases
            # start over on resume, like a trial dropped by a pause.
            self._pre = None
            self._dot_result = None
            self._phase = Phase.READY
            self._audio("on_stop_audio")
        return interrupted

    # -- what the renderer needs ---------------------------------------------------------------

    def _stage(self) -> str:
        if self._pre is not None:
            return self._pre.stage
        if self.search_mode == MATCH_SAMPLE and self._phase is Phase.READY:
            return STAGE_BLANK  # before the first trial (and after a pause): nothing to show yet
        return STAGE_FIELD

    def scene_spec(self) -> dict[str, Any]:
        """The scene for the renderer, from the live canvas size; re-read every tick.

        Pop-out is ``{"mode": "icons", "slots", "shapes"}`` as it always was. Anything else adds
        ``search_mode``, the ``stage`` (``start_dot`` / ``sample`` / ``field`` / ``blank``) and
        ``icon_radius_px`` (the drawn radius of an icon), and per stage: the centre ``dot``; the
        ``sample_shape`` with its text; or, in Match the sample's field with ``sample_reminder`` on, the
        ``reminder`` (a place and a radius) while the child searches. ``shapes`` is the current trial's field."""
        index = self._pre.trial if self._pre is not None else max(0, self._trial_index)
        index = min(index, len(self.trial_field_shapes) - 1)
        spec: dict[str, Any] = {
            "mode": "icons",
            "slots": list(self.icon_slots),
            "shapes": list(
                self.trial_field_shapes[index] if self.search_mode == MATCH_SAMPLE else self.icon_shapes
            ),
        }
        stage = self._stage()
        if self.search_mode == POP_OUT and stage == STAGE_FIELD:
            return spec  # exactly the Pop-out scene of before
        icon_r = self._icon_radius_px()
        spec.update(search_mode=self.search_mode, stage=stage, icon_radius_px=icon_r)
        if stage == STAGE_START_DOT:
            spec["dot"] = {"x_norm": 0.5, "y_norm": 0.5, "diameter_px": self.start_dot_px}
        elif stage == STAGE_SAMPLE:
            spec.update(
                sample_shape=self.trial_target_shapes[index], sample_text=SAMPLE_TEXT,
                sample_text_px=self.sample_text_px,
            )
        elif stage == STAGE_FIELD and self._phase is Phase.WAIT_INPUT and self.sample_reminder:
            x, y, radius = reminder_placement(self.icon_slots, self.screen_w, self.screen_h, icon_r)
            spec.update(
                sample_shape=self.trial_target_shapes[index],
                reminder={"x_norm": x, "y_norm": y, "radius_px": radius},
            )
        return spec
