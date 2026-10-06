"""Deleting a recorded session's folder (SPEC-compass-task-flow.md 4C.8, HC6, U14).

"Discard Results" removes the run's folder for good, so the one function that does
it is deliberately paranoid: it refuses anything that is not a plain session folder
directly inside the output root. Qt-free.
"""

from __future__ import annotations

import re
from pathlib import Path

# ``<date>_<subject>_<task>_run<N>``, as :func:`~src.engine.session_naming.next_session_id` makes it.
_SESSION_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_.+_run\d+$")


class SessionDiscardError(ValueError):
    """The folder is not one ``discard_session`` is willing to delete. Nothing was deleted."""


def _is_link(path: Path) -> bool:
    """A symlink, or a Windows junction (``Path.is_junction`` needs Python 3.12)."""
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def discard_session(session_dir: str | Path, output_root: str | Path) -> int:
    """Delete one recorded session folder; return how many files it held.

    Refuses (``SessionDiscardError``, nothing deleted) unless **all** hold:

    * ``session_dir`` exists and is a directory, not a symlink or junction;
    * its parent is exactly ``output_root`` (both resolved, so ``..`` and nested
      paths are no way round it);
    * its name looks like a session (``<date>_<subject>_<task>_run<N>``) and does
      not start with ``_`` (``_settings``, ``_tests``, ``_diagnostics`` ...);
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
    if resolved.parent != root:
        raise SessionDiscardError(f"{resolved} is not directly inside {root}")
    name = resolved.name
    if name.startswith("_") or not _SESSION_NAME.match(name):
        raise SessionDiscardError(f"{name!r} is not a session folder name")
    entries = list(resolved.iterdir())
    for entry in entries:
        if _is_link(entry) or not entry.is_file():
            raise SessionDiscardError(f"{entry.name!r} in {name} is not a plain file; nothing deleted")
    for entry in entries:
        entry.unlink()
    resolved.rmdir()
    return len(entries)
