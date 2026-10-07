"""The two input choices of a test and the one run mode they derive
(SPEC-input-selection-and-follow.md H1, H2, H3, H5; Qt-free).

A test carries **Pointer** (what moves the pointer: ``gaze`` or ``mouse``) and
**Selection** (how a target is selected: ``dwell`` or ``switch``) as the structural
settings ``input.pointer`` and ``input.selection``. Follow the Target has no
selection (I9), so for it the second one is ``None``.

``input_mode`` stays the one string the rest of the code (``BaseTask``, the report's
Input row) reads. It is derived here (H1)::

    gaze  + dwell   -> eye            mouse + dwell   -> mouse_dwell
    gaze  + switch  -> gaze_switch    mouse + switch  -> switch
    gaze  + (none)  -> eye            mouse + (none)  -> mouse_follow

A config with no per-test ``input`` block (a standalone launch, a headless replay, a
test stored before these settings existed) falls back to the old global
``input.mode`` of ``default.yaml``, so nothing that ran before changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POINTER_GAZE = "gaze"
POINTER_MOUSE = "mouse"
POINTERS = (POINTER_GAZE, POINTER_MOUSE)

SELECTION_DWELL = "dwell"
SELECTION_SWITCH = "switch"
SELECTIONS = (SELECTION_DWELL, SELECTION_SWITCH)

MODE_EYE = "eye"
MODE_GAZE_SWITCH = "gaze_switch"
MODE_SWITCH = "switch"
MODE_MOUSE_DWELL = "mouse_dwell"
MODE_MOUSE_FOLLOW = "mouse_follow"
INPUT_MODES = (MODE_EYE, MODE_GAZE_SWITCH, MODE_SWITCH, MODE_MOUSE_DWELL, MODE_MOUSE_FOLLOW)

# Tasks with nothing to select (I9): they have a Pointer but no Selection.
TASKS_WITHOUT_SELECTION = ("follow_moving",)
# Tasks whose target glows while the pointer is on it even with no switch (I10).
TASKS_WITH_GLOW = ("follow_moving",)

# The two Setup blockers a Mouse test does not need (H5): no tracker, no calibration.
# The one place their text lives, so ``SetupPage.run_blockers`` and the Start page agree.
TRACKER_BLOCKER = "The tracker is not connected. Connect it on the Setup page."
CALIBRATION_BLOCKER = "No calibration yet. Calibrate on the Setup page."
GAZE_ONLY_BLOCKERS = (TRACKER_BLOCKER, CALIBRATION_BLOCKER)

_MODE_OF = {
    (POINTER_GAZE, SELECTION_DWELL): MODE_EYE,
    (POINTER_GAZE, SELECTION_SWITCH): MODE_GAZE_SWITCH,
    (POINTER_MOUSE, SELECTION_SWITCH): MODE_SWITCH,
    (POINTER_MOUSE, SELECTION_DWELL): MODE_MOUSE_DWELL,
}


def derive_input_mode(pointer: str, selection: str | None) -> str:
    """The ``input_mode`` of a Pointer and Selection (H1); an unknown value takes the
    default (gaze, dwell). ``selection`` is ``None`` for a task with none."""
    pointer = pointer if pointer in POINTERS else POINTER_GAZE
    if selection is None:
        return MODE_MOUSE_FOLLOW if pointer == POINTER_MOUSE else MODE_EYE
    selection = selection if selection in SELECTIONS else SELECTION_DWELL
    return _MODE_OF[(pointer, selection)]


def selection_of_mode(mode: str) -> str:
    """How targets are selected in ``mode``: a switch press for ``gaze_switch`` and
    ``switch``, a dwell for everything else (including a task with no selection, which
    ``BaseTask`` still runs as a dwell until Follow's own rewrite)."""
    return SELECTION_SWITCH if mode in (MODE_GAZE_SWITCH, MODE_SWITCH) else SELECTION_DWELL


def pointer_of_mode(mode: str) -> str:
    """What moves the pointer in ``mode``."""
    return POINTER_MOUSE if mode in (MODE_SWITCH, MODE_MOUSE_DWELL, MODE_MOUSE_FOLLOW) else POINTER_GAZE


@dataclass(frozen=True, slots=True)
class InputChoice:
    """A test's Pointer and Selection (``selection`` is ``None`` for Follow the Target)."""

    pointer: str
    selection: str | None

    @property
    def mode(self) -> str:
        return derive_input_mode(self.pointer, self.selection)

    @property
    def is_mouse(self) -> bool:
        return self.pointer == POINTER_MOUSE

    @property
    def is_switch(self) -> bool:
        return self.selection == SELECTION_SWITCH


def resolve_input(config: dict[str, Any]) -> InputChoice:
    """The Pointer and Selection of a run from its merged config.

    ``config["task"]["input"]`` (the test's stored ``input.pointer`` / ``input.selection``)
    wins; whatever it lacks comes from the legacy global ``config["input"]["mode"]``
    (default ``eye``). The task id is ``config["task"]["task_id"]``: a task in
    :data:`TASKS_WITHOUT_SELECTION` has no selection.
    """
    task_cfg = config.get("task") or {}
    block = task_cfg.get("input")
    block = block if isinstance(block, dict) else {}
    legacy = str((config.get("input") or {}).get("mode", MODE_EYE))
    pointer = block.get("pointer")
    if pointer not in POINTERS:
        pointer = pointer_of_mode(legacy)
    if task_cfg.get("task_id") in TASKS_WITHOUT_SELECTION:
        return InputChoice(pointer, None)
    selection = block.get("selection")
    if selection not in SELECTIONS:
        selection = selection_of_mode(legacy)
    return InputChoice(pointer, selection)


def glow_active(task_id: str, selection: str | None, enabled: bool) -> bool:
    """Whether the target glow is drawn: the ``feedback.target_glow`` setting, and only
    where there is no dwell ring to take its place -- Switch selection, and Follow the
    Target (H3, A4). With Dwell the setting is stored but not shown."""
    return bool(enabled) and (selection == SELECTION_SWITCH or task_id in TASKS_WITH_GLOW)


# What the Setup page says under its Continue button when a gaze test could not run now
# (SPEC-input-selection-and-follow.md, user decision of 2026-10-07): Continue to Tests is
# allowed without a tracker, and the page says what that leaves.
NO_TRACKER_NOTE = "No tracker connected: only Mouse tests can run."
NOT_CALIBRATED_NOTE = "Not calibrated: only Mouse tests can run."


def gaze_only_note(tracker_ok: bool, calibrated: bool) -> str | None:
    """The Setup note for a tracker that is missing or not calibrated, or ``None`` when a
    gaze test could run. A missing tracker is named first, whatever the calibration."""
    if not tracker_ok:
        return NO_TRACKER_NOTE
    if not calibrated:
        return NOT_CALIBRATED_NOTE
    return None


def drop_gaze_only_blockers(blockers: list[str]) -> tuple[list[str], bool, bool]:
    """``(remaining, tracker_ok, calibrated)`` for a Mouse test (H5): the blockers
    without the tracker and calibration ones, and whether those two were absent (the
    gaze is then recorded alongside)."""
    remaining = [b for b in blockers if b not in GAZE_ONLY_BLOCKERS]
    return remaining, TRACKER_BLOCKER not in blockers, CALIBRATION_BLOCKER not in blockers
