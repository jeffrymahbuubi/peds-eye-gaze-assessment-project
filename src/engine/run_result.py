"""What a finished run hands back, and what saving or discarding it does
(SPEC-compass-task-flow.md 4C.8, U8, U14, HD1).

:class:`RunResult` is what :class:`~src.app.AssessmentApp` gives its ``on_finished``
callback. The files of a recorded run are already on disk by then, so a crash at a
run-end dialog loses nothing; whether they **stay** is decided afterwards, by the
operator's choice at the dialog (``src/ui/run_dialogs.py``), and carried out here by
:func:`finish_run`:

* **Save** (and **Save partial results**): the test is linked to the run and locked
  (``record_result``), then ``report.json`` is cached from the files on disk.
* **Save and View Report**: the same, but the report is built on the spot
  (``load_or_build_report``) and handed back for the report page.
* **Discard**: the run folder is deleted (guarded, ``discard_session``) and the
  test is left Not Done, so it can be configured and run again.

``report.json`` is built only after a Save, never for a run that is discarded
(carry-forward from P4, 4D.6 / HD1). Qt-free.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data.report_cache import load_or_build_report, write_report_safely
from .run_mode import ENDED_FINISHED, ENDED_QUIT
from .session_files import discard_session
from .subject_tests import SubjectTest, record_result

_log = logging.getLogger(__name__)

SAVE = "save"
SAVE_AND_VIEW = "save_and_view"
DISCARD = "discard"
FINISH_ACTIONS = (SAVE, SAVE_AND_VIEW, DISCARD)

OUTCOME_COMPLETED = "completed"
OUTCOME_ENDED_EARLY = "ended_early"


@dataclass(frozen=True, slots=True)
class RunResult:
    """How one run ended.

    ``planned`` is the number of trials the task had, ``completed`` the rows in
    ``trials.csv`` (skipped ones included), ``skipped`` how many of those were
    skipped and ``hits`` how many were selected. ``outcome`` is ``completed`` only
    when the task ran out of trials on its own; ``ended_by`` says who ended it
    (``finished`` or ``operator_quit``). ``session_dir`` is the run's folder, or
    ``None`` for a practice or preview (nothing is written). ``finished_at`` is the
    local time with its offset, as an ISO string.
    """

    run_mode: str
    outcome: str
    ended_by: str
    planned: int
    completed: int
    skipped: int
    hits: int
    session_dir: Path | None
    finished_at: str
    # The task's id, so a line can say "followed" (Follow the Target) instead of "selected".
    task_id: str = ""

    @property
    def is_complete(self) -> bool:
        return self.outcome == OUTCOME_COMPLETED

    @property
    def is_empty(self) -> bool:
        """No trial was finished, so there is nothing worth saving."""
        return self.completed == 0


def run_result_from_task(
    run_mode: str,
    task: Any,
    session_dir: Path | None,
    finished_at: str,
    *,
    ended_by: str | None = None,
) -> RunResult:
    """The :class:`RunResult` of ``task`` as it stands now (a ``BaseTask``): the same
    outcome rule as ``metadata.json`` (:func:`~src.engine.run_mode.outcome_fields`)."""
    done = bool(task.is_done)
    return RunResult(
        run_mode=run_mode,
        outcome=OUTCOME_COMPLETED if done else OUTCOME_ENDED_EARLY,
        ended_by=ended_by or (ENDED_FINISHED if done else ENDED_QUIT),
        planned=len(task.targets),
        completed=len(task.trials),
        skipped=sum(1 for t in task.trials if t.is_skipped),
        hits=sum(1 for t in task.trials if t.is_hit),
        session_dir=session_dir,
        finished_at=finished_at,
        task_id=str(getattr(task, "task_id", "") or ""),
    )


def practice_result_text(result: RunResult) -> str | None:
    """The Start page's line after a practice (4C.4): ``None`` unless the practice
    ran to its end, because Quit / Esc in a practice returns at once and says
    nothing."""
    if result.run_mode != "practice" or not result.is_complete:
        return None
    # Follow the Target selects nothing: its "hits" are the trials that were followed.
    what = "followed" if result.task_id == "follow_moving" else "selected"
    return (
        f"Practice finished: {result.hits} of {result.planned} {what}. "
        "You can practice again or press Start."
    )


@dataclass(frozen=True, slots=True)
class FinishedRun:
    """What :func:`finish_run` did. ``test`` is the updated (now locked) test after a
    save, ``None`` after a discard. ``report`` is the report for "Save and View
    Report" (``None`` if it could not be built: the report page then says why)."""

    action: str
    test: SubjectTest | None = None
    report: dict[str, Any] | None = None


def finish_run(
    result: RunResult,
    action: str,
    *,
    output_root: str | Path,
    subject_id: str,
    test_id: str,
) -> FinishedRun:
    """Carry out the operator's choice for a finished, recorded run.

    May raise what ``record_result`` raises (``TestLockedError``, ``TestStoreError``,
    ``ValueError``): the data stays on disk and the test stays Not Done, so the
    caller shows the message and nothing is lost. A discard may raise
    ``SessionDiscardError`` (nothing deleted). Building the report never raises.
    """
    if action not in FINISH_ACTIONS:
        raise ValueError(f"action must be one of {FINISH_ACTIONS}, not {action!r}")
    if result.session_dir is None:
        raise ValueError("a practice or preview run has no run folder to save or discard")
    if action == DISCARD:
        discard_session(result.session_dir, output_root)
        return FinishedRun(DISCARD)
    test = record_result(
        output_root,
        subject_id,
        test_id,
        session_dir=result.session_dir,
        planned_trials=result.planned,
        completed_trials=result.completed,
        completed_at=result.finished_at,
    )
    if action == SAVE:
        write_report_safely(result.session_dir)
        return FinishedRun(SAVE, test)
    try:
        report = load_or_build_report(result.session_dir)
    except Exception as exc:  # noqa: BLE001 - the run is saved; a report bug must not undo that
        _log.warning("report not built for %s: %s", result.session_dir, exc)
        report = None
    return FinishedRun(SAVE_AND_VIEW, test, report)
