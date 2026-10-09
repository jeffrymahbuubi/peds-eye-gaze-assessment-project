"""Deleting a recorded session's folder (SPEC-compass-task-flow.md 4C.8, HC6, U14;
SPEC-subject-data-layout.md H10).

"Discard Results" removes the run's folder for good, so the one function that does
it is deliberately paranoid: it refuses anything that is not a plain run folder at
``<output root>/<subject folder>/runs/<task_id>/<YYYY-MM-DD_HHMM>``. Qt-free.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .run_paths import RUN_NAME_RE, TASK_DIR_RE
from .subject_store import RUNS_DIRNAME, SUBJECT_FILENAME, SYSTEM_DIRNAME


class SessionDiscardError(ValueError):
    """The folder is not one ``discard_session`` is willing to delete. Nothing was deleted."""


def _is_link(path: Path) -> bool:
    """A symlink, or a Windows junction (``Path.is_junction`` needs Python 3.12)."""
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def discard_session(session_dir: str | Path, output_root: str | Path) -> int:
    """Delete one recorded run folder; return how many files it held.

    Refuses (``SessionDiscardError``, nothing deleted) unless **all** hold:

    * ``session_dir`` exists and is a directory, not a symlink or junction;
    * it lies at ``<output_root>/<subject>/runs/<task_id>/<name>`` (both resolved, so
      ``..`` and nested paths are no way round it), where ``<subject>`` is a subject
      folder (it holds ``subject.json``; ``_system`` is not one) and ``<name>`` is the
      ``YYYY-MM-DD_HHMM`` pattern (``_2``, ``_3`` on a collision);
    * every entry in it is a regular file: any subdirectory or link aborts the
      whole thing before the first file is removed.

    The path should be the one from the run itself (``RunResult.session_dir``),
    never text a user typed.
    """
    folder = Path(session_dir)
    if _is_link(folder):
        raise SessionDiscardError(f"{folder} is a link; not deleting it")
    try:
        resolved = folder.resolve(strict=True)
        root = Path(output_root).resolve(strict=True)
    except OSError as exc:
        raise SessionDiscardError(f"{folder} or the output root does not exist: {exc}") from exc
    if not resolved.is_dir():
        raise SessionDiscardError(f"{resolved} is not a folder")
    try:
        parts = resolved.relative_to(root).parts
    except ValueError as exc:
        raise SessionDiscardError(f"{resolved} is not inside {root}") from exc
    name = resolved.name
    if (
        len(parts) != 4
        or parts[0].casefold() == SYSTEM_DIRNAME
        or parts[1] != RUNS_DIRNAME
        or not TASK_DIR_RE.fullmatch(parts[2])
        or not RUN_NAME_RE.fullmatch(name)
    ):
        raise SessionDiscardError(
            f"{name!r} is not a run folder (<subject>/{RUNS_DIRNAME}/<task>/<date_time>) of {root}"
        )
    if not (root / parts[0] / SUBJECT_FILENAME).is_file():
        raise SessionDiscardError(f"{parts[0]!r} is not a subject folder of {root}")
    entries = list(resolved.iterdir())
    for entry in entries:
        if _is_link(entry) or not entry.is_file():
            raise SessionDiscardError(f"{entry.name!r} in {name} is not a plain file; nothing deleted")
    for entry in entries:
        entry.unlink()
    resolved.rmdir()
    return len(entries)


def remove_orphan_run_dir(
    session_dir: str | Path | None,
    output_root: str | Path,
    written_names: Iterable[str] = (),
) -> bool:
    """Remove the folder of a run that failed to start, if every entry in it is a file the
    failed start wrote (SPEC-audit-fixes.md H11); return whether it was removed.

    ``AssessmentApp`` makes the folder when it first needs it (the preset calibration is
    saved there before the recorder exists), so a start that fails afterwards leaves a
    folder no report or discard could ever use. The files a start writes are its
    ``calibration.json`` and, if the recorder opened, the recorder's own: the caller names
    those in ``written_names``. A folder that holds any other entry is data, however it got
    there, and is never touched. The same checks as :func:`discard_session` apply to its
    place and shape (a link or a subfolder, even one with a known name, means "not removed").
    The caller closes any file it still holds open first (Windows cannot delete one).
    """
    if session_dir is None:
        return False
    folder = Path(session_dir)
    try:
        names = {entry.name for entry in folder.iterdir()}
    except OSError:
        return False
    if names - {"calibration.json", *written_names}:
        return False
    try:
        discard_session(folder, output_root)
    except (SessionDiscardError, OSError):
        return False
    return True
