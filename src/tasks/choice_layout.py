"""The Choice-making board, its eight objects and the trial order (Qt-free).

SPEC-scene-cause-effect-task.md 4.2 (layout and button-to-object mapping), 4.4 (effect
durations) and W5 (trial order). Kept apart from :mod:`.choice_making` so the maths can be
unit-tested without a task, and so the task file stays short.

The board is a 7 x 5 grid of equal cells over the whole canvas. The scene fills columns 1-5,
the eight buttons are columns 0 and 6, rows 1-4; cells (0, 0) and (6, 0) stay empty. A button
is drawn and hit-tested like a Grid Click cell (:func:`~src.engine.target_size.grid_cell_geometry`),
so the cell-gap presets apply to it unchanged.
"""

from __future__ import annotations

import random
import wave
from dataclasses import dataclass
from pathlib import Path

from ..engine.config import CONFIG_ROOT
from ..engine.target_size import CellGeometry, grid_cell_geometry

GRID_COLS = 7
GRID_ROWS = 5
N_BUTTONS = 8
SCENE_FIRST_COL = 1
SCENE_COLS = 5  # columns 1-5

SIDE_LEFT = "left"
SIDE_RIGHT = "right"

# How the prompt is given (SPEC section 3.7, P1): spoken, as text in a banner, or both.
PROMPT_VOICE, PROMPT_TEXT, PROMPT_VOICE_TEXT = "voice", "text", "voice_text"
PROMPT_MODES = (PROMPT_VOICE, PROMPT_TEXT, PROMPT_VOICE_TEXT)
DEFAULT_PROMPT_MODE = PROMPT_VOICE


def normalise_prompt_mode(value: object) -> str:
    """``value`` if it is one of :data:`PROMPT_MODES`, else the default (``voice``)."""
    return value if isinstance(value, str) and value in PROMPT_MODES else DEFAULT_PROMPT_MODE


def prompt_has_voice(mode: object) -> bool:
    """Whether the spoken prompt plays (and blocks selection until it ends, H4, A3)."""
    return normalise_prompt_mode(mode) != PROMPT_TEXT


def prompt_has_text(mode: object) -> bool:
    """Whether the text banner is shown (P2)."""
    return normalise_prompt_mode(mode) != PROMPT_VOICE

# The spoken prompt's length when its WAV is missing or unreadable (SPEC section 9, Q1 = B): the
# engine measures ``prompt_<object>.wav`` itself, and every object falls back to this.
DEFAULT_PROMPT_MS = 2000

# The assets folder (``configs/assets``); read only -- the engine never writes there.
ASSETS_ROOT = CONFIG_ROOT / "assets"


@dataclass(frozen=True, slots=True)
class SceneObject:
    """One object of the scene and the button that makes it happen."""

    id: str
    label: str  # the English label of the button and of the prompt
    slot: int  # button index 0-7: L1-L4 (column 0, rows 1-4), then R1-R4 (column 6, rows 1-4)
    effect_ms: int  # default effect duration (4.4); the scene manifest may override it later


# 4.2 / 4.4. Index in this tuple == ``slot``.
OBJECTS: tuple[SceneObject, ...] = (
    SceneObject("balloons", "Balloons", 0, 3500),
    SceneObject("rainbow", "Rainbow", 1, 2000),
    SceneObject("seesaw", "Seesaw", 2, 2000),
    SceneObject("apples", "Apples", 3, 4500),
    SceneObject("cloud", "Cloud", 4, 3500),
    SceneObject("bubbles", "Bubbles", 5, 4000),
    SceneObject("bike", "Bike", 6, 4000),
    SceneObject("swing", "Swing", 7, 2500),
)
OBJECT_BY_ID: dict[str, SceneObject] = {o.id: o for o in OBJECTS}

# slot -> (column, row) of its cell on the 7 x 5 board.
BUTTON_CELLS: tuple[tuple[int, int], ...] = tuple(
    [(0, row) for row in range(1, 5)] + [(GRID_COLS - 1, row) for row in range(1, 5)]
)


def side_of(slot: int) -> str:
    """Which side of the screen a button is on."""
    return SIDE_LEFT if slot < N_BUTTONS // 2 else SIDE_RIGHT


def button_centre_norm(slot: int) -> tuple[float, float]:
    """Canvas-normalized centre of a button's cell (independent of the canvas size)."""
    col, row = BUTTON_CELLS[slot]
    return (col + 0.5) / GRID_COLS, (row + 0.5) / GRID_ROWS


def board_geometry(w_px: float, h_px: float, gap_px: float | None) -> CellGeometry:
    """How a button is drawn and hit-tested on a canvas of the given size
    (:func:`~src.engine.target_size.grid_cell_geometry` of one cell's pitch)."""
    return grid_cell_geometry(w_px / GRID_COLS, h_px / GRID_ROWS, gap_px)


def button_rect(
    slot: int, w_px: float, h_px: float, geometry: CellGeometry
) -> tuple[float, float, float, float]:
    """The drawn button as ``(x, y, w, h)`` in canvas px."""
    col, row = BUTTON_CELLS[slot]
    return (
        col * w_px / GRID_COLS + geometry.inset,
        row * h_px / GRID_ROWS + geometry.inset,
        geometry.cell_w,
        geometry.cell_h,
    )


def scene_rect(w_px: float, h_px: float) -> tuple[float, float, float, float]:
    """The scene (columns 1-5, rows 0-4) as ``(x, y, w, h)`` in canvas px."""
    pitch_w = w_px / GRID_COLS
    return SCENE_FIRST_COL * pitch_w, 0.0, SCENE_COLS * pitch_w, float(h_px)


def button_at(px: float, py: float, w_px: float, h_px: float, geometry: CellGeometry) -> int:
    """The button whose hit area holds canvas point ``(px, py)``, else -1.

    The hit area is the geometry's own: the whole cell for the standard gap, the drawn button
    for a wider one, so the gap between two buttons selects neither (SPEC-grid-cell-gap.md H3).
    The scene, a gap and the two empty corner cells select nothing (H5)."""
    for slot, (col, row) in enumerate(BUTTON_CELLS):
        cx = (col + 0.5) * w_px / GRID_COLS
        cy = (row + 0.5) * h_px / GRID_ROWS
        if abs(px - cx) <= geometry.hit_w / 2 and abs(py - cy) <= geometry.hit_h / 2:
            return slot
    return -1


# -- the scene's audio files (4.7): read only -----------------------------------------------------


def scene_audio_dir(scene: str, root: Path | None = None) -> Path:
    """``<assets>/scenes/<scene>/audio``: the folder of a scene's prompts (``<language>/``) and
    effect sounds (``sfx/``)."""
    return (root if root is not None else ASSETS_ROOT) / "scenes" / scene / "audio"


def prompt_wav_path(scene: str, language: str, object_id: str, root: Path | None = None) -> Path:
    """The spoken prompt of an object: ``audio/<language>/prompt_<object>.wav``."""
    return scene_audio_dir(scene, root) / language / f"prompt_{object_id}.wav"


def effect_wav_path(scene: str, object_id: str, root: Path | None = None) -> Path:
    """The sound of an object's effect: ``audio/sfx/<object>.wav``."""
    return scene_audio_dir(scene, root) / "sfx" / f"{object_id}.wav"


def wav_duration_ms(path: Path) -> float | None:
    """Length of a WAV file in ms from its header (Python ``wave``, no Qt), or ``None`` when the
    file is missing, is not a PCM WAV, is empty or cannot be read."""
    try:
        with wave.open(str(path), "rb") as handle:
            frames, rate = handle.getnframes(), handle.getframerate()
    except (OSError, EOFError, wave.Error):
        return None
    if frames <= 0 or rate <= 0:
        return None
    return 1000.0 * frames / rate


# -- the trial order (W5) ---------------------------------------------------------------------


def _can_continue(counts: list[int], last: int) -> bool:
    """Whether what is left in ``counts`` can be laid out with no object next to itself and
    its first element not ``last`` (the object just placed)."""
    remaining = sum(counts)
    if remaining == 0:
        return True
    most = max(counts)
    if most > (remaining + 1) // 2:
        return False
    # An odd remainder with one object filling every other place must start with it.
    return not (remaining % 2 == 1 and most == (remaining + 1) // 2 and counts[last] == most)


def trial_order(n_trials: int, rng: random.Random) -> list[int]:
    """The object (== button slot) of each trial, for any trial count (W5).

    Balanced as far as the count allows: object counts differ by at most 1, left and right
    counts differ by at most 1, and no object comes twice in a row. 16 trials give each
    object twice and 8 on each side. Deterministic for a seeded ``rng``.
    """
    if n_trials <= 0:
        return []
    full, extra = divmod(n_trials, N_BUTTONS)
    counts = [full] * N_BUTTONS
    if extra:
        half = N_BUTTONS // 2
        # The extra objects split between the sides as evenly as possible; with an odd
        # number, a random side gets the odd one. Which objects get one more is random.
        more, fewer = (extra + 1) // 2, extra // 2
        left_n, right_n = (more, fewer) if rng.random() < 0.5 else (fewer, more)
        for slot in rng.sample(range(half), left_n):
            counts[slot] += 1
        for slot in rng.sample(range(half, N_BUTTONS), right_n):
            counts[slot] += 1

    order: list[int] = []
    last = -1
    for _ in range(n_trials):
        options = []
        for slot in range(N_BUTTONS):
            if counts[slot] == 0 or slot == last:
                continue
            counts[slot] -= 1
            if _can_continue(counts, slot):
                options.append(slot)
            counts[slot] += 1
        pick = rng.choices(options, weights=[counts[s] for s in options])[0]
        counts[pick] -= 1
        order.append(pick)
        last = pick
    return order
