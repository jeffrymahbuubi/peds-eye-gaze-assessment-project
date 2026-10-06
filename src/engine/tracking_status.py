"""The run bar's one-line operator status (SPEC-compass-task-flow.md 4C.5).

Pure functions, so the rule is unit-testable apart from the widget (``RunBar``,
P7) that shows it. Qt-free.
"""

from __future__ import annotations

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
        return "tracker DISCONNECTED", LEVEL_ERROR
    if seconds_since_valid is None:
        return "waiting for gaze", LEVEL_WARN
    if seconds_since_valid >= GAZE_LOST_AFTER_S:
        return f"no gaze for {int(seconds_since_valid)} s", LEVEL_WARN
    return "tracking OK", LEVEL_OK


def run_status_line(
    trial_number: int,
    planned: int,
    tracking_text: str,
    *,
    practice: bool = False,
    paused: bool = False,
) -> str:
    """The bar's status text: ``[PRACTICE (not recorded) · ]Trial i/N · tracking``.

    ``trial_number`` is 1-based; before the first trial (the pre-roll) the task
    reports 0 or less, shown as trial 1. While paused the tracking text is
    dropped: ``Paused · Trial i/N``.
    """
    trial = f"Trial {max(trial_number, 1)}/{planned}"
    parts = ["PRACTICE (not recorded)"] if practice else []
    parts += ["Paused", trial] if paused else [trial, tracking_text]
    return " · ".join(parts)
