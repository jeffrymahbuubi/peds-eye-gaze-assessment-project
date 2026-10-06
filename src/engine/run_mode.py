"""Run modes and what each one means for the data (SPEC-compass-task-flow.md 4C.4,
R3, R8). Qt-free, so :class:`~src.app.AssessmentApp` stays thin and the rules are
unit-testable.

A run is one of three kinds:

* ``record`` -- the real test. Files are written, the target order comes from the
  test's own seed, and a blank pre-roll precedes trial 1.
* ``practice`` -- 3 trials driven by gaze, nothing recorded, a seed of its own.
* ``preview`` -- the mouse-driven look at a configuration, nothing recorded.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..data.schema import TrialRecord

RECORD = "record"
PRACTICE = "practice"
PREVIEW = "preview"
RUN_MODES = (RECORD, PRACTICE, PREVIEW)

# A test's seed is drawn from [0, 999_999] (R3), so a practice seed
# (``PRACTICE_SEED_BASE + k``) and the preview seed, which both sit above that,
# can never reproduce a recorded order.
PRACTICE_SEED_BASE = 1_000_000
PREVIEW_SEED = 2_000_000

# A recorded run shows the canvas without a target for this long before trial 1,
# so the gaze and pupil recorded just before it are a baseline (R8).
PREROLL_MS = 500

# How a run ended (``metadata.ended_by``): the task ran out of trials, or the
# operator quit it (Quit, Alt-Q, Esc).
ENDED_FINISHED = "finished"
ENDED_QUIT = "operator_quit"


def validate_run_mode(run_mode: object) -> str:
    """``run_mode`` itself if it is one of :data:`RUN_MODES`, else ``ValueError``."""
    if run_mode not in RUN_MODES:  # also rejects None and non-strings
        raise ValueError(f"run_mode must be one of {RUN_MODES}, not {run_mode!r}")
    return run_mode  # type: ignore[return-value]


def is_recorded(run_mode: str) -> bool:
    """Whether a run of this mode reaches disk (only ``record`` does)."""
    return run_mode == RECORD


def run_seed(run_mode: str, seed: int = 0, practice_index: int = 0) -> int:
    """The seed a run's target order is drawn from.

    ``record`` uses the test's own ``seed``; ``practice`` uses
    ``PRACTICE_SEED_BASE + practice_index`` (the k-th practice press since the
    Start page opened, so every repeat differs) whatever ``seed`` is; ``preview``
    uses :data:`PREVIEW_SEED`.
    """
    validate_run_mode(run_mode)
    if run_mode == PRACTICE:
        return PRACTICE_SEED_BASE + int(practice_index)
    if run_mode == PREVIEW:
        return PREVIEW_SEED
    return int(seed)


def preroll_ms(run_mode: str) -> int:
    """The blank period before trial 1: :data:`PREROLL_MS` for a recorded run,
    none for practice and preview."""
    return PREROLL_MS if is_recorded(run_mode) else 0


def outcome_fields(
    trials: Sequence[TrialRecord],
    planned: int,
    is_done: bool,
    pause_count: int,
    interrupted_trials: int,
    ended_ns: int,
    ended_by: str | None = None,
) -> dict[str, Any]:
    """The ``metadata.json`` fields that say how a run ended (4C.9, R1).

    ``completed_trials`` is the rows written to ``trials.csv``, skipped ones
    included. ``outcome`` is ``completed`` only when the task ran out of trials
    on its own; anything else is the operator ending it. ``ended_by`` is derived
    from that unless the caller says (``_shutdown(ended_by=...)``): the quit flow
    that asks first does not change these values.
    """
    if ended_by not in (None, ENDED_FINISHED, ENDED_QUIT):
        raise ValueError(f"ended_by must be {ENDED_FINISHED!r} or {ENDED_QUIT!r}, not {ended_by!r}")
    return {
        "planned_trials": planned,
        "completed_trials": len(trials),
        "skipped_trials": sum(1 for t in trials if t.is_skipped),
        "interrupted_trials": interrupted_trials,
        "pause_count": pause_count,
        "outcome": "completed" if is_done else "ended_early",
        "ended_by": ended_by or (ENDED_FINISHED if is_done else ENDED_QUIT),
        "ended_ns": ended_ns,
    }


def apply_outcome(
    metadata: Any,
    task: Any,
    ended_ns: int,
    ended_by: str | None = None,
    trial_number: int | None = None,
) -> str:
    """Write how ``task``'s run ended into ``metadata`` (a ``SessionMetadata``) and
    return the ``session.log`` line for it. Call before the recorder closes, so
    ``metadata.json`` carries the fields.

    ``trial_number`` overrides ``task.trial_number`` in the log line: a quit
    confirmed while paused has already dropped the in-flight trial, so the task is
    one step behind the trial the operator was actually on."""
    fields = outcome_fields(
        task.trials,
        len(task.targets),
        task.is_done,
        task.pause_count,
        task.interrupted_trials,
        ended_ns,
        ended_by,
    )
    for name, value in fields.items():
        setattr(metadata, name, value)
    return outcome_log_line(
        fields["outcome"],
        fields["completed_trials"],
        fields["planned_trials"],
        task.trial_number if trial_number is None else trial_number,
    )


def outcome_log_line(outcome: str, completed: int, planned: int, trial_number: int) -> str:
    """The ``session.log`` line for the end of a run (4C.9). ``trial_number`` is
    the 1-based trial the operator ended it on."""
    if outcome == "completed":
        return f"Run completed: {completed} of {planned} trials."
    return (
        f"Run ended early by operator at trial {trial_number} of {planned} "
        f"({completed} recorded)."
    )
