"""The Choice-making settings (SPEC-scene-cause-effect-task.md 4.8; page layout in
``docs/wireframes/choice-making.md`` part A).

Split out of :mod:`.settings_registry` to keep it under the project's 500-line limit; the
registry adds these to its own lists. Every entry applies to ``choice_making`` only. No PySide6
import, like the registry.
"""

from __future__ import annotations

from .setting_types import MS_PER_S, LiveSetting, StructuralSetting

TASK_ID = "choice_making"
_ONLY = (TASK_ID,)

# "Time to choose": the same key as every task's timeout, counted here from the END of the
# spoken prompt (H9); the registry swaps it in for this task (``_TASK_VARIANTS``).
CHOICE_TIMEOUT = LiveSetting(
    "task.timeout_ms",
    "Time to choose (s)",
    "pacing",
    "int",
    1000,
    20000,
    500,
    tooltip="How long the child has to choose, counted from the end of the spoken prompt."
    " After that the trial counts as a timeout and the animation plays once as a model.",
    display_divisor=MS_PER_S,
)

# This task has no inter-trial interval: the pause after the animation takes its place (4.1).
CHOICE_LIVE: list[LiveSetting] = [
    LiveSetting(
        "task.post_effect_ms",
        "Pause after the animation (s)",
        "pacing",
        "int",
        0,
        5000,
        100,
        applies_to=_ONLY,
        tooltip="The next prompt starts only after the animation and this pause.",
        display_divisor=MS_PER_S,
    ),
]

CHOICE_STRUCTURAL: list[StructuralSetting] = [
    StructuralSetting(
        "scene", "Scene", "choice", applies_to=_ONLY, choices=(("park", "Park"),), default="park"
    ),
    StructuralSetting(
        "language",
        "Prompt language",
        "choice",
        applies_to=_ONLY,
        choices=(("en", "English"),),
        default="en",
    ),
    StructuralSetting(
        "visual_cue",
        "Visual cue: the target button gently pulses",
        "bool",
        applies_to=_ONLY,
        default=False,
    ),
    # The picture's idle life between trials (N3): a registry entry, so it is stored with the test,
    # recorded in ``metadata.json`` (``settings.structural.idle_animation``) and shown in the report.
    StructuralSetting(
        "idle_animation",
        "Idle animation between trials",
        "choice",
        applies_to=_ONLY,
        choices=(("off", "Off"), ("blinks", "Blinks"), ("blinks_bob", "Blinks and a gentle bob")),
        default="blinks",
    ),
]

# The Scene card (column B) takes the place of Grid Click's Grid Layout card: this test has a
# fixed 7 x 5 board, so no rows or columns, but the Cell gap (``grid.gap``) lives here.
SCENE_CARD = (
    "scene", "Scene", 1, None, ("scene", "language", "visual_cue", "idle_animation", "grid.gap")
)


def choice_cards(task_id: str, cards: tuple) -> tuple:
    """The configuration cards of ``task_id``: ``cards`` (the registry's table) as they are,
    except for Choice-making, whose Grid Layout card is replaced by :data:`SCENE_CARD`."""
    if task_id != TASK_ID:
        return cards
    return tuple(SCENE_CARD if card[0] == "grid" else card for card in cards)
