"""Scanning Search's search modes, sample cue and centre start dot (Qt-free).

SPEC-scanning-search-cues.md 4.2-4.4. Kept apart from :mod:`.scanning` so the maths (the shuffle,
the reminder's place, the sizes by visual angle) can be unit-tested without a task, and so the task
file stays short.

* ``pop_out`` (the default, today's task): the target is the one coloured icon of a fixed field.
* ``match_sample``: the target's shape is shown alone at the centre and spoken (``prompt_<shape>.wav``),
  then the field appears with every icon bright in the target colour, reshuffled every trial with
  the target's shape exactly once, so only the shape tells them apart.
* ``start_dot``: before each trial a small dot at the centre; the gaze rests on it, and the trial goes on.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

from ..engine.prompt_text import PROMPT_TEXT_DEG, extent_px_for
from ..engine.target_size import ScaleInfo
from ..inputs.eye_input import DwellConfig, DwellSelector
from .choice_layout import ASSETS_ROOT

TASK_ID = "scanning"

# Index == the SHAPE_* constants of ``src.ui.canvas_shapes`` (tests/test_scanning_search.py pins that
# they agree); the name is the spoken prompt's file name (``prompt_<name>.wav``) and the recorded one.
SHAPE_NAMES = ("circle", "square", "triangle", "diamond", "hexagon", "star")
N_SHAPES = len(SHAPE_NAMES)

POP_OUT, MATCH_SAMPLE = "pop_out", "match_sample"
SEARCH_MODES = (POP_OUT, MATCH_SAMPLE)
DEFAULT_SEARCH_MODE = POP_OUT
SEARCH_MODE_NAMES = {POP_OUT: "Pop-out", MATCH_SAMPLE: "Match the sample"}

# The sample phase (4.3): at least this long (or as long as the spoken prompt, if that is longer).
SAMPLE_MS = 1500.0
SAMPLE_TEXT = "Find this!"
SAMPLE_TEXT_DEG = PROMPT_TEXT_DEG  # 1.5 deg lettering, as Choice-making's banner
REMINDER_SCALE = 0.5  # the reminder is this fraction of the icon size
_REMINDER_PAD_FRAC = 0.02  # its distance from the canvas edge, in canvas heights
_REMINDER_PAD_MIN_PX = 8.0
_REMINDER_CLEARANCE_PX = 8.0  # the gap kept between the reminder and any icon

# The centre start dot (4.4): its size, how close the gaze must stay, for how long, and the give-up time.
START_DOT_DEG = 1.0
START_DOT_CAPTURE_DEG = 2.0  # radius
START_DOT_HOLD_MS = 300.0
START_DOT_TIMEOUT_MS = 5000.0

# Where the spoken prompts are read from, relative to the assets folder (``configs/assets``).
AUDIO_DIR = ("scanning", "audio")


def normalise_search_mode(value: object) -> str:
    """``value`` if it is one of :data:`SEARCH_MODES`, else the default (``pop_out``)."""
    return value if isinstance(value, str) and value in SEARCH_MODES else DEFAULT_SEARCH_MODE


def prompt_wav_path(language: str, shape_name: str, root: Path | None = None) -> Path:
    """The spoken prompt of a shape: ``scanning/audio/<language>/prompt_<shape>.wav``."""
    return (root if root is not None else ASSETS_ROOT).joinpath(*AUDIO_DIR, language, f"prompt_{shape_name}.wav")


def draw_field(rng: random.Random, n_icons: int, target_slot: int) -> tuple[int, list[int]]:
    """A trial's field in Match the sample (S6): ``(target shape, shape of every slot)``.

    The target's shape is drawn from the six, and it sits in ``target_slot`` and nowhere else. The
    other slots get distinct other shapes where possible; with more than five distractors a shape
    repeats, but never the target's."""
    target = rng.randrange(N_SHAPES)
    others = [s for s in range(N_SHAPES) if s != target]
    pool: list[int] = []
    shapes = [target] * n_icons
    for slot in range(n_icons):
        if slot == target_slot:
            continue
        if not pool:
            pool = list(others)
            rng.shuffle(pool)
        shapes[slot] = pool.pop()
    return target, shapes


class WrongIconDwell:
    """A dwell on an icon that is not the target, in Match the sample (SPEC 4.3, 4.6).

    The same rule as the target's dwell -- the dwell's threshold, refractory and hold grace -- run on
    whichever wrong icon the pointer is on; moving to another icon starts it over. A completed one is
    a wrong selection: this only reports it, it draws and plays nothing. After it the icon has to be
    left (a valid pointer off it for the hold grace) before it can count again, so one long look is
    one wrong selection, not one per dwell."""

    def __init__(self, config: DwellConfig) -> None:
        self._dwell = DwellSelector(config)
        self._grace_ns = int(config.hold_grace_ms * 1e6)
        self._slot: int | None = None  # the wrong icon the running dwell is on
        self._locked: int | None = None  # the icon of the last completed dwell, not yet left
        self._off_since_ns: int | None = None

    def update(self, t_ns: int, valid: bool, slot: int, target_slot: int) -> int | None:
        """One frame: ``slot`` is the icon the pointer is on (-1 none). Returns the slot of a wrong
        icon whose dwell completed this frame, else ``None``."""
        if self._locked is not None and valid:
            if slot == self._locked:
                self._off_since_ns = None
            else:
                if self._off_since_ns is None:
                    self._off_since_ns = t_ns
                if t_ns - self._off_since_ns >= self._grace_ns:
                    self._locked = self._off_since_ns = None
        on_wrong = valid and self._locked is None and slot >= 0 and slot != target_slot
        if on_wrong:
            if self._slot is not None and self._slot != slot:
                self._dwell.reset()
            self._slot = slot
        if self._dwell.update(t_ns, on_wrong).triggered:
            done, self._locked = self._slot, self._slot
            self._slot = None  # nothing is accumulating now: a move to another icon must not reset the refractory
            return done
        return None


def reminder_placement(
    slots: list[tuple[float, float]], w_px: float, h_px: float, icon_radius_px: float
) -> tuple[float, float, float]:
    """``(x_norm, y_norm, radius_px)`` of the reminder in the search phase (4.3): half the icon
    size, at the top centre, or in the top-left corner when it would touch an icon there."""
    radius = icon_radius_px * REMINDER_SCALE
    pad = max(_REMINDER_PAD_MIN_PX, _REMINDER_PAD_FRAC * h_px)
    y = pad + radius
    x = w_px / 2.0
    clear = icon_radius_px + radius + _REMINDER_CLEARANCE_PX
    if any(math.hypot(x - sx * w_px, y - sy * h_px) < clear for sx, sy in slots):
        x = pad + radius
    return x / w_px, y / h_px, radius


def apply_search_cues(
    task_cfg: dict[str, Any], scale: ScaleInfo, viewing_distance: float
) -> dict[str, Any] | None:
    """Resolve the cues' sizes by visual angle into ``task_cfg``, in place, against the same screen
    scale as :func:`~src.engine.target_size.apply_target_size`: ``start_dot_px`` (the dot's
    diameter), ``start_dot_capture_px`` (how near the gaze must stay, a radius) and
    ``sample_text_px`` (the lettering's height). Only a Scanning Search run with Match the sample
    or the start dot on has any: any other task, or the plain Pop-out, is left alone and ``None`` is
    returned. Returns the sizes for the Session Log."""
    if task_cfg.get("task_id") != TASK_ID:
        return None
    if normalise_search_mode(task_cfg.get("search_mode")) == POP_OUT and task_cfg.get("start_dot") is not True:
        return None
    sizes = {
        "start_dot_px": START_DOT_DEG,
        "start_dot_capture_px": START_DOT_CAPTURE_DEG,
        "sample_text_px": SAMPLE_TEXT_DEG,
    }
    info: dict[str, Any] = {}
    for key, degrees in sizes.items():
        px = round(extent_px_for(degrees, scale.mm_per_px, viewing_distance), 1)
        task_cfg[key] = px
        info[key] = px
    return info


def search_cues_log_line(info: dict[str, Any]) -> str:
    """The Session Log line, e.g. ``Search cues: start dot 1° (≈55 px), gaze within 2° (≈111 px),
    sample text 1.5° (≈83 px)``."""
    return (
        f"Search cues: start dot {START_DOT_DEG:g}° (≈{info['start_dot_px']:.0f} px), "
        f"gaze within {START_DOT_CAPTURE_DEG:g}° (≈{info['start_dot_capture_px']:.0f} px), "
        f"sample text {SAMPLE_TEXT_DEG:g}° (≈{info['sample_text_px']:.0f} px)"
    )
