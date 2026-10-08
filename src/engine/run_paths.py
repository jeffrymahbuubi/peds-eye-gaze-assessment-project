"""Where a run's folder is made, named and found (SPEC-subject-data-layout.md H2-H4, H9).

A recorded run lives at ``<root>/<subject folder>/runs/<task_id>/<YYYY-MM-DD_HHMM>/``
(``_2``, ``_3`` on a same-minute collision). The folder name carries no subject and no
test name: a rename would make it stale, and a child's name must not travel in it (D3).
:func:`new_run_dir` is the one function that makes it, used by :class:`~src.app.
AssessmentApp` (which needs the folder before the recorder exists, for
``calibration.json``) and by :class:`~src.data.recorder.SessionRecorder`.

A test record points at its run by a path **relative to the subject folder**
(``runs/click_grid/2026-10-07_1432``): :func:`relative_run_dir` makes it,
:func:`resolve_run_dir` reads it back and refuses anything that is not that shape.
:func:`path_budget_error` is the H9 check that a run's longest path stays under 240
characters. Qt-free.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

from .subject_store import (
    REPORTS_DIRNAME,
    RUNS_DIRNAME,
    SubjectFolder,
    ensure_subject,
    find_subject,
    id_folder_name,
)

RUN_NAME_FORMAT = "%Y-%m-%d_%H%M"
# ``2026-10-07_1432`` and ``2026-10-07_1432_2``: the H2 pattern the Discard guard demands.
RUN_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{4}(?:_\d+)?")
TASK_DIR_RE = re.compile(r"[a-z][a-z0-9_]*")

# H9: the longest path a run may write (Explorer, zip and OneDrive fail near 260).
MAX_PATH_BUDGET = 240
PATH_TOO_LONG_TEXT = (
    "The data folder path is too long. Move the program folder closer to the drive root."
)
# The longest file a run folder holds (``session_metrics.json``); a test pins it against
# every name the recorder, the report cache and the exporter write.
LONGEST_RUN_FILE_NAME = "session_metrics.json"
_WORST_RUN_NAME = "2026-10-07_1432_9"  # a same-minute collision suffix
PDF_NAME_MAX = 50  # H7: the test-name part of ``<YYYY-MM-DD>_<test name>.pdf``
_PDF_EXTRA = len("2026-10-07_") + len(".pdf")


def new_run_dir(
    output_root: str | Path,
    subject_id: str,
    task_id: str,
    *,
    folder_mode: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Create and return the folder of a new recorded run (H2).

    Makes the subject's folder first if it is new (``folder_mode`` applies then and
    only then), then ``runs/<task_id>/<YYYY-MM-DD_HHMM>``; on a collision ``_2``,
    ``_3`` ... The ``mkdir`` has no ``exist_ok``, so two runs can never share a folder.
    """
    if not TASK_DIR_RE.fullmatch(task_id):
        raise ValueError(f"Not a task id: {task_id!r}")
    folder = ensure_subject(output_root, subject_id, folder_mode)
    parent = folder.runs / task_id
    parent.mkdir(parents=True, exist_ok=True)
    stem = (now or datetime.now()).strftime(RUN_NAME_FORMAT)
    n = 1
    while True:
        path = parent / (stem if n == 1 else f"{stem}_{n}")
        try:
            path.mkdir()
        except FileExistsError:
            n += 1
            continue
        return path


def make_session_id(task_id: str, run_dir: Path, test_id: str | None) -> str:
    """``<task_id>_<YYYY-MM-DD_HHMM>_<test_id>`` (H3): unique across subjects, no subject
    in it. A run with no test (standalone launch) has none of the last part."""
    base = f"{task_id}_{run_dir.name}"
    return f"{base}_{test_id}" if test_id else base


def relative_run_dir(subject_path: str | Path, run_dir: str | Path) -> str:
    """``runs/<task_id>/<name>`` of ``run_dir``, relative to the subject folder (H4).

    Raises ``ValueError`` unless the run lies exactly there (a folder somewhere else, a
    deeper one, one whose name is not the H2 pattern).
    """
    try:
        relative = Path(run_dir).resolve().relative_to(Path(subject_path).resolve())
    except (OSError, ValueError) as exc:
        raise ValueError(f"The run folder {run_dir} is not inside {subject_path}") from exc
    parts = relative.parts
    if not _is_run_path(parts):
        raise ValueError(
            f"The run folder must be {RUNS_DIRNAME}/<task>/<date_time> under {subject_path}: {run_dir}"
        )
    return "/".join(parts)


def _is_run_path(parts: tuple[str, ...]) -> bool:
    return (
        len(parts) == 3
        and parts[0] == RUNS_DIRNAME
        and TASK_DIR_RE.fullmatch(parts[1]) is not None
        and RUN_NAME_RE.fullmatch(parts[2]) is not None
    )


def resolve_run_dir(subject_path: str | Path, run_dir: str | None) -> Path | None:
    """The folder a record's ``run_dir`` names, or ``None`` if it names none (empty, or not
    the ``runs/<task>/<name>`` shape: no ``..``, no drive, no deeper path)."""
    if not run_dir or not isinstance(run_dir, str):
        return None
    parts = PurePosixPath(run_dir).parts
    if not _is_run_path(parts):
        return None
    return Path(subject_path).joinpath(*parts)


# -- the path budget (H9) -------------------------------------------------------------


def longest_run_path(output_root: str | Path, subject_folder_name: str, task_id: str) -> int:
    """The length of the longest path a recorded run of ``task_id`` will write: the biggest
    of the run's longest file and the PDF Print Report proposes."""
    root = len(os.path.abspath(output_root))
    subject = root + 1 + len(subject_folder_name)
    run_file = subject + 1 + len(RUNS_DIRNAME) + 1 + len(task_id) + 1 + len(_WORST_RUN_NAME)
    run_file += 1 + len(LONGEST_RUN_FILE_NAME)
    pdf = subject + 1 + len(REPORTS_DIRNAME) + 1 + PDF_NAME_MAX + _PDF_EXTRA
    return max(run_file, pdf)


def path_budget_error(output_root: str | Path, subject_id: str, task_id: str) -> str | None:
    """:data:`PATH_TOO_LONG_TEXT` if a recorded run of this subject would write a path over
    :data:`MAX_PATH_BUDGET` characters, else ``None``. The subject's own folder name counts
    when it exists; a new subject is measured by the name its ID would get."""
    sid = subject_id.strip()
    existing: SubjectFolder | None = find_subject(output_root, sid) if sid else None
    name = existing.name if existing is not None else id_folder_name(sid or "subject")
    if longest_run_path(output_root, name, task_id) > MAX_PATH_BUDGET:
        return PATH_TOO_LONG_TEXT
    return None
