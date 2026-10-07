"""The Start page's read-aloud instructions (SPEC-compass-task-flow.md 4C.3, HC11).

Text is built from the test's own settings, so what the clinician reads out matches
what the child will see: the dwell time, the timeout, and whether the progress ring
and the gaze dot are shown. English only (U12): the Chinese ``instruction:`` keys in
the task YAML are untouched and unread here, kept for the future language feature.

Qt-free (it only imports the settings registry, which has no widgets), so it can be
unit-tested without a display. The wording is read to children and needs a
clinician's review before release (SPEC §9 (c)).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine.input_choice import resolve_input
from ..engine.task_info import TASK_INFO
from .settings_registry import get_nested, initial_live_values


@dataclass(frozen=True, slots=True)
class Instructions:
    """What the Start page shows.

    ``steps`` are plain sentences (the page numbers them); ``note`` carries its own
    ``NOTE:`` label. ``heading`` and ``steps`` and ``note`` are read to the child;
    ``clinician`` is for the operator only.
    """

    heading: str
    steps: tuple[str, ...]
    note: str
    clinician: tuple[str, ...]


_DOT = "The small dot on the screen shows where you are looking. "
_RING = " A ring will fill up around it."

# The wording of the two input choices (SPEC-input-selection-and-follow.md W1; read aloud,
# so it needs the same clinician review as the rest).
# Pointer = Mouse: the "small dot" sentence becomes this one (always: the child must be
# told to move the mouse), and "look at" becomes "point at" in every step.
_MOUSE_DOT = "Move the mouse to point at the screen. "
# Selection = Switch: the step that asks for a dwell ("keep looking at it for about 0.8
# seconds") becomes this one -- the task's own sentence and noun -- and, with the glow on,
# says the target glows while it is looked at.
_SWITCH_STEPS: dict[str, tuple[str, str]] = {
    "click_static": ("Look at the circle, then press the button.", "circle"),
    "click_grid": ("Look at the lit square, then press the button.", "square"),
    "scanning": ("Find the bright shape, look at it, then press the button.", "shape"),
}
_GLOW = " The {noun} glows while you are looking at it."


def _point_wording(text: str) -> str:
    """The Mouse version of a sentence: "look at" is "point at", "looking at" "pointing at"."""
    return (
        text.replace("Look at", "Point at")
        .replace("look at", "point at")
        .replace("looking at", "pointing at")
    )

# Per task: four step templates and the timeout NOTE. ``{dwell}`` / ``{timeout}``
# are seconds ("0.8 seconds"); ``{ring}`` is the optional ring sentence (with its
# leading space) and ``{dot}`` the optional first sentence (with its trailing one).
_TEMPLATES: dict[str, tuple[tuple[str, ...], str]] = {
    "click_static": (
        (
            "{dot}A circle will appear on the screen.",
            "Look at the circle and keep looking at it for about {dwell}.{ring}",
            "When it is selected, the next circle will appear.",
            "Continue until no more circles appear.",
        ),
        "NOTE: If the circle is not selected within {timeout}, it will disappear and the next one will appear.",
    ),
    "click_grid": (
        (
            "{dot}A board of squares will appear on the screen.",
            "One square will light up.",
            "Look at the lit square and keep looking at it for about {dwell}.{ring}",
            "When it is selected, another square will light up. Continue until no more squares light up.",
        ),
        "NOTE: If the square is not selected within {timeout}, the next square will light up.",
    ),
    "follow_moving": (
        (
            "{dot}A circle will appear and start to move across the screen.",
            "Follow the moving circle with your eyes.",
            "When the circle becomes bright with a white ring, keep looking at it for about {dwell} to select it.{ring}",
            "Then a new circle will appear. Continue until no more circles appear.",
        ),
        "NOTE: If the circle is not selected within {timeout}, it will disappear and the next one will appear.",
    ),
    "scanning": (
        (
            "{dot}Several shapes will appear on the screen.",
            "One shape will light up bright. The others stay dim.",
            "Find the bright shape and keep looking at it for about {dwell}.{ring}",
            "When it is selected, a different shape will light up. Continue until no more shapes light up.",
        ),
        "NOTE: If the shape is not selected within {timeout}, the next shape will light up.",
    ),
}

# The same for every task; ``{n}`` is the planned trial count.
_CLINICIAN: tuple[str, ...] = (
    'To pause the test: click the "Pause" button, or press ALT-P. '
    'To quit the test: click the "Quit" button, or press ALT-Q.',
    "Practice runs 3 targets with these settings. Nothing is recorded. Repeat it as often as needed.",
    'Start records {n} trials. Check that the bottom bar says "tracking OK" before you begin.',
)


def format_seconds(ms: float) -> str:
    """Milliseconds as spoken seconds: ``800`` -> "0.8 seconds", ``1000`` ->
    "1 second", ``12500`` -> "12.5 seconds"."""
    seconds = round(float(ms) / 1000.0, 2)
    return f"{seconds:g} {'second' if seconds == 1 else 'seconds'}"


def build_instructions(
    task_id: str, cfg: dict[str, Any], values: dict[str, Any] | None = None
) -> Instructions:
    """The instructions for one test.

    ``cfg`` is the run's merged config (``load_task_config`` with the test's
    structural overrides applied): it gives the planned trial count
    (``cfg["task"]["trials"]``). ``values`` are the test's live settings, keyed as
    in :func:`~src.ui.settings_registry.initial_live_values` (dwell threshold,
    timeout, progress ring, gaze cursor); it may be partial or omitted, and any key
    it lacks comes from ``cfg``. Neither argument is changed.
    """
    if task_id not in _TEMPLATES:
        raise KeyError(f"Unknown task '{task_id}'. Known: {sorted(_TEMPLATES)}")
    live = {**initial_live_values(cfg), **(values or {})}
    choice = resolve_input(cfg)
    if choice.is_mouse:
        dot = _MOUSE_DOT
    else:
        dot = _DOT if live["dwell.visual_cursor"] else ""
    fill = {
        "dot": dot,
        "ring": _RING if live["dwell.progress_ring"] else "",
        "dwell": format_seconds(live["dwell.threshold_ms"]),
        "timeout": format_seconds(live["task.timeout_ms"]),
    }
    steps, note = _TEMPLATES[task_id]
    if choice.is_switch and task_id in _SWITCH_STEPS:
        # The dwell step becomes a press (W1); the glow sentence only with the glow on.
        sentence, noun = _SWITCH_STEPS[task_id]
        glow = get_nested(cfg.get("task", {}), "feedback.target_glow", True)
        if glow is not False:
            sentence += _GLOW.format(noun=noun)
        steps = tuple(sentence if "{dwell}" in s else s for s in steps)
    trials = cfg.get("task", {}).get("trials")
    count = str(int(trials)) if trials is not None else "all"
    out = tuple(s.format(**fill) for s in steps)
    if choice.is_mouse:
        out = tuple(_point_wording(s) for s in out)
    return Instructions(
        heading=f"Instructions for the {TASK_INFO[task_id][0]} test:",
        steps=out,
        note=note.format(**fill),
        clinician=tuple(c.format(n=count) for c in _CLINICIAN),
    )
