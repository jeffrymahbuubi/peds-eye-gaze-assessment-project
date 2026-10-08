"""The run bar's operator status (SPEC-compass-task-flow.md 4C.5; SPEC-design-system-
phase1.md H9): what it says, as separate facts the bar shows in a label each.

Pure functions, so the rule is unit-testable apart from the widget (``RunBar``,
P7) that shows it. Qt-free.
"""

from __future__ import annotations

from typing import NamedTuple

# ``FPOGV`` drops during saccades and blinks, so a single invalid frame must
# never show; gaze counts as lost only after this long with no valid frame.
GAZE_LOST_AFTER_S = 1.0

LEVEL_OK = "ok"  # shown green
LEVEL_WARN = "warn"  # amber
LEVEL_ERROR = "error"  # red


def tracking_status(connected: bool, seconds_since_valid: float | None) -> tuple[str, str]:
    """``(text, level)`` for the tracker's state.

    ``seconds_since_valid`` is how long ago the last valid gaze frame was, or
    ``None`` if there has not been one yet. A dropped link beats everything else
    (a stale last sample would otherwise look like steady gaze); a disconnect only
    shows here, it never pauses the run (HC9).
    """
    if not connected:
        return "Tracker disconnected", LEVEL_ERROR
    if seconds_since_valid is None:
        return "Waiting for gaze", LEVEL_WARN
    if seconds_since_valid >= GAZE_LOST_AFTER_S:
        return f"No gaze for {int(seconds_since_valid)} s", LEVEL_WARN
    return "Tracking OK", LEVEL_OK


class RunStatus(NamedTuple):
    """What the run bar says, one fact per field (an empty one is not shown)."""

    chip: str = ""  # PRACTICE or PREVIEW; none in a recorded run
    paused: bool = False
    trial: str = ""  # "Trial 4 of 18"
    pointer: str = ""  # "Mouse pointer" when the pointer is the mouse
    tracking: str = ""  # the tracker's state, from :func:`tracking_status`
    level: str = LEVEL_OK  # how the tracking text is coloured

    @property
    def line(self) -> str:
        """The facts as plain text, in the order the bar shows them, comma separated."""
        facts = (self.chip, "Paused" if self.paused else "", self.trial, self.pointer, self.tracking)
        return ", ".join(fact for fact in facts if fact)


def run_status(
    trial_number: int,
    planned: int,
    tracking_text: str,
    level: str = LEVEL_OK,
    *,
    practice: bool = False,
    paused: bool = False,
    preview: bool = False,
    mouse: bool = False,
) -> RunStatus:
    """The bar's status: ``[PRACTICE|PREVIEW] Trial i of N [Mouse pointer] tracking``.

    ``trial_number`` is 1-based; before the first trial (the pre-roll) the task
    reports 0 or less, shown as trial 1. While paused the pointer and the tracking text
    are dropped: ``Paused, Trial i of N``. A ``preview`` (the mouse-driven look at a
    configuration, 4B.6) says so in its chip instead of naming the tracker (the chip means
    nothing is recorded): ``PREVIEW, Trial i of N, Mouse pointer``, and just
    ``PREVIEW, Paused`` while paused. A ``mouse`` run (Pointer = Mouse,
    SPEC-input-selection-and-follow.md) names its pointer after the trial, and
    ``tracking_text`` may be empty (no tracker: nothing to report).
    """
    trial = f"Trial {max(trial_number, 1)} of {planned}"
    chip = "PREVIEW" if preview else "PRACTICE" if practice else ""
    if preview:
        if paused:
            return RunStatus(chip, paused=True)
        return RunStatus(chip, trial=trial, pointer="Mouse pointer")
    if paused:
        return RunStatus(chip, paused=True, trial=trial)
    return RunStatus(
        chip,
        trial=trial,
        pointer="Mouse pointer" if mouse else "",
        tracking=tracking_text,
        level=level,
    )
