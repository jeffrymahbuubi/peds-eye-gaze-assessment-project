"""One folder per subject under the output root (SPEC-subject-data-layout.md H1, H5, H8).

::

    sessions/
      _system/diagnostics/, _system/replay/     machine-wide, no subject (D2, H11)
      <subject folder>/
        subject.json
        calibrations/  settings/  tests/  runs/<task_id>/<YYYY-MM-DD_HHMM>/  reports/

A folder is a subject folder only if it holds ``subject.json``
(``{"subject_id": <as first typed>, "folder_mode": "id", "created_at"}``).
The app finds a subject by reading those files and matching ``subject_id``
case-insensitively (casefold) -- it never recomputes the folder name from the ID,
so "Ana" and "ANA" are one subject. The folder name is chosen once, when the folder
is created: always ``safe_subject_dirname(id)`` capped at 40 characters (D4 revised
2026-10-08: no Anonymous code option). ``folder_mode`` stays in the file, always
``"id"``, so the schema does not change; the reader ignores its value.

:func:`output_root` is the one place the output root is read (H8). Qt-free.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_default
from .session_naming import safe_subject_dirname

DEFAULT_OUTPUT_ROOT = "sessions"
SYSTEM_DIRNAME = "_system"  # reserved: never a subject folder
DIAGNOSTICS_DIRNAME = "diagnostics"
REPLAY_DIRNAME = "replay"
SUBJECT_FILENAME = "subject.json"

CALIBRATIONS_DIRNAME = "calibrations"
SETTINGS_DIRNAME = "settings"
TESTS_DIRNAME = "tests"
RUNS_DIRNAME = "runs"
REPORTS_DIRNAME = "reports"

FOLDER_MODE_ID = "id"  # the only value written to subject.json's "folder_mode" key

MAX_FOLDER_ID_LEN = 40  # H5: the Subject ID part of a folder name (+ "~hash" when changed)

# Antivirus / OneDrive can hold a freshly written file for a moment on Windows.
REPLACE_RETRIES = 5
_REPLACE_DELAY_S = 0.04


def output_root(config: Mapping[str, Any] | None = None) -> str:
    """Where every subject folder lives: ``recording.output_root`` of ``config`` (a
    merged task config), or of the default config when none is given (H8)."""
    cfg = config if config is not None else load_default()
    recording = cfg.get("recording") or {}
    return str(recording.get("output_root", DEFAULT_OUTPUT_ROOT))


def system_dir(root: str | Path) -> Path:
    return Path(root) / SYSTEM_DIRNAME


def diagnostics_dir(root: str | Path) -> Path:
    return system_dir(root) / DIAGNOSTICS_DIRNAME


def replay_dir(root: str | Path) -> Path:
    return system_dir(root) / REPLAY_DIRNAME


@dataclass(frozen=True)
class SubjectFolder:
    """One subject's folder, as ``subject.json`` describes it."""

    path: Path
    subject_id: str
    created_at: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def calibrations(self) -> Path:
        return self.path / CALIBRATIONS_DIRNAME

    @property
    def settings(self) -> Path:
        return self.path / SETTINGS_DIRNAME

    @property
    def tests(self) -> Path:
        return self.path / TESTS_DIRNAME

    @property
    def runs(self) -> Path:
        return self.path / RUNS_DIRNAME

    @property
    def reports(self) -> Path:
        return self.path / REPORTS_DIRNAME


def same_subject(a: str, b: str) -> bool:
    """Subject IDs are one subject when they match ignoring case and outer spaces."""
    return a.strip().casefold() == b.strip().casefold()


def _read_subject_json(folder: Path) -> SubjectFolder | None:
    """The folder as a subject, or ``None`` if it has no readable ``subject.json``."""
    try:
        data = json.loads((folder / SUBJECT_FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):  # ValueError: bad JSON or bad UTF-8
        return None
    if not isinstance(data, dict):
        return None
    subject_id = data.get("subject_id")
    if not isinstance(subject_id, str) or not subject_id.strip():
        return None
    created = data.get("created_at")
    return SubjectFolder(
        path=folder,
        subject_id=subject_id.strip(),
        created_at=created if isinstance(created, str) else "",
    )


def list_subjects(root: str | Path) -> list[SubjectFolder]:
    """Every subject folder under ``root``, ordered by folder name. A missing or
    unreadable root is simply "no subjects"."""
    base = Path(root)
    try:
        entries = sorted(base.iterdir(), key=lambda p: p.name.casefold())
    except OSError:
        return []
    found: list[SubjectFolder] = []
    for entry in entries:
        if entry.name.casefold() == SYSTEM_DIRNAME or not entry.is_dir():
            continue
        subject = _read_subject_json(entry)
        if subject is not None:
            found.append(subject)
    return found


def find_subject(root: str | Path, subject_id: str) -> SubjectFolder | None:
    """The folder of ``subject_id`` (case-insensitive), or ``None`` for a new subject."""
    wanted = subject_id.strip()
    if not wanted:
        return None
    # Always a scan of the subject.json files (never a guess at the folder name from the ID): the
    # folder name on disk can differ from the ID in case, mode or sanitising, and on NTFS a
    # guessed path would hand back the guess, not the real name.
    for subject in list_subjects(root):
        if same_subject(subject.subject_id, wanted):
            return subject
    return None


def known_subject_ids(root: str | Path) -> list[str]:
    """The ``subject_id`` of every subject folder, verbatim as first typed, sorted
    (the Setup page's completer)."""
    return sorted({s.subject_id for s in list_subjects(root)}, key=lambda s: (s.casefold(), s))


# -- folder names ---------------------------------------------------------------------


def id_folder_name(subject_id: str) -> str:
    """The folder name of a new subject (H5): ``safe_subject_dirname`` of the stripped
    ID, cut at 40 characters. ``_system`` is reserved, so a subject typed that gets a
    prefixed name."""
    sid = subject_id.strip()
    name = safe_subject_dirname(sid, MAX_FOLDER_ID_LEN)
    if name.casefold() == SYSTEM_DIRNAME:
        digest = hashlib.sha1(sid.encode("utf-8", errors="surrogatepass"), usedforsecurity=False)
        name = f"_{name}~{digest.hexdigest()[:6]}"
    return name


# -- creating -------------------------------------------------------------------------


def replace_with_retry(src: Path, dst: Path) -> None:
    """``os.replace`` with a few short retries on ``PermissionError`` (SPEC-compass-task-flow.md 4A.2)."""
    attempts = 1 + REPLACE_RETRIES
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(_REPLACE_DELAY_S)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _claim_folder(root: Path, base: str) -> Path:
    """Create ``root/base`` (or ``base~2``, ``base~3`` ... if the name is taken by a folder
    that is not this subject's). ``mkdir`` without ``exist_ok`` is the atomic claim."""
    n = 1
    while True:
        path = root / (base if n == 1 else f"{base}~{n}")
        try:
            path.mkdir()
        except FileExistsError:
            n += 1
            continue
        return path


def ensure_subject(root: str | Path, subject_id: str) -> SubjectFolder:
    """The folder of ``subject_id``, created (with its ``subject.json``) if it is new.

    The folder is named after the Subject ID (:func:`id_folder_name`); an existing
    subject keeps whatever folder it has. Raises ``ValueError`` for a blank ID,
    ``OSError`` if the folder cannot be written.
    """
    sid = subject_id.strip()
    if not sid:
        raise ValueError("A Subject ID is required.")
    found = find_subject(root, sid)
    if found is not None:
        return found
    base_root = Path(root)
    base_root.mkdir(parents=True, exist_ok=True)
    path = _claim_folder(base_root, id_folder_name(sid))
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        _write_json(
            path / SUBJECT_FILENAME,
            {"subject_id": sid, "folder_mode": FOLDER_MODE_ID, "created_at": created},
        )
    except OSError:
        try:
            (path / SUBJECT_FILENAME).unlink(missing_ok=True)
            path.rmdir()
        except OSError:
            pass
        raise
    return SubjectFolder(path=path, subject_id=sid, created_at=created)
