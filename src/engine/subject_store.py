"""One folder per subject under the output root (SPEC-subject-data-layout.md H1, H5, H6, H8).

::

    sessions/
      _system/diagnostics/, _system/replay/     machine-wide, no subject (D2, H11)
      <subject folder>/
        subject.json
        calibrations/  settings/  tests/  runs/<task_id>/<YYYY-MM-DD_HHMM>/  reports/

A folder is a subject folder only if it holds ``subject.json``
(``{"subject_id": <as first typed>, "folder_mode": "id" | "code", "created_at"}``).
The app finds a subject by reading those files and matching ``subject_id``
case-insensitively (casefold) -- it never recomputes the folder name from the ID,
so "Ana" and "ANA" are one subject and an Anonymous-code subject (``S-0003``) is
found by the ID it was typed with. The folder name is chosen once, when the folder
is created: ``safe_subject_dirname(id)`` capped at 40 characters (mode ``id``), or
the next free ``S-000N`` that is never reused (mode ``code``, D4).

:func:`output_root` is the one place the output root is read (H8). Qt-free.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
CODE_COUNTER_FILENAME = "subject_codes.json"  # in _system: the highest code ever issued

CALIBRATIONS_DIRNAME = "calibrations"
SETTINGS_DIRNAME = "settings"
TESTS_DIRNAME = "tests"
RUNS_DIRNAME = "runs"
REPORTS_DIRNAME = "reports"

FOLDER_MODE_ID = "id"
FOLDER_MODE_CODE = "code"
FOLDER_MODES = (FOLDER_MODE_ID, FOLDER_MODE_CODE)
MODE_LABELS = {FOLDER_MODE_ID: "Subject ID", FOLDER_MODE_CODE: "Anonymous code"}

MAX_FOLDER_ID_LEN = 40  # H5: the Subject ID part of a folder name (+ "~hash" when changed)

_CODE_NAME = re.compile(r"S-(\d{4,})")

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
    mode: str
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

    def label(self) -> str:
        """``Folder: S-0003 (Anonymous code)`` (the Setup page's read-only line)."""
        return f"Folder: {self.name} ({MODE_LABELS[self.mode]})"


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
    mode = data.get("folder_mode")
    created = data.get("created_at")
    return SubjectFolder(
        path=folder,
        subject_id=subject_id.strip(),
        mode=mode if mode in FOLDER_MODES else FOLDER_MODE_ID,
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
    """The folder name of a subject in mode ``id`` (H5): ``safe_subject_dirname`` of the
    stripped ID, cut at 40 characters. ``_system`` is reserved, so a subject typed that
    gets a prefixed name."""
    sid = subject_id.strip()
    name = safe_subject_dirname(sid, MAX_FOLDER_ID_LEN)
    if name.casefold() == SYSTEM_DIRNAME:
        digest = hashlib.sha1(sid.encode("utf-8", errors="surrogatepass"), usedforsecurity=False)
        name = f"_{name}~{digest.hexdigest()[:6]}"
    return name


def _code_name(number: int) -> str:
    return f"S-{number:04d}"


def _counter_path(root: Path) -> Path:
    return system_dir(root) / CODE_COUNTER_FILENAME


def _highest_code(root: Path) -> int:
    """The highest code number seen: in a folder name, or in the counter file that
    remembers codes whose folder was later deleted (so a code is never reused)."""
    best = 0
    try:
        names = [p.name for p in root.iterdir()]
    except OSError:
        names = []
    for name in names:
        match = _CODE_NAME.fullmatch(name)
        if match:
            best = max(best, int(match.group(1)))
    try:
        data = json.loads(_counter_path(root).read_text(encoding="utf-8"))
        last = data.get("last") if isinstance(data, dict) else None
        if isinstance(last, int) and not isinstance(last, bool):
            best = max(best, last)
    except (OSError, ValueError):
        pass
    return best


def next_subject_code(root: str | Path) -> str:
    """The code a new Anonymous-code subject would get: ``S-0001``, ``S-0002`` ..."""
    return _code_name(_highest_code(Path(root)) + 1)


def preview_folder_name(root: str | Path, subject_id: str, folder_mode: str) -> str:
    """The folder name a new subject would get in ``folder_mode`` (for the Setup choice)."""
    return next_subject_code(root) if folder_mode == FOLDER_MODE_CODE else id_folder_name(subject_id)


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


def ensure_subject(
    root: str | Path, subject_id: str, folder_mode: str | None = None
) -> SubjectFolder:
    """The folder of ``subject_id``, created (with its ``subject.json``) if it is new.

    An existing subject keeps the mode it was created with, whatever ``folder_mode``
    says: the choice is fixed when the folder is created (H6). ``None`` means mode
    ``id``. Raises ``ValueError`` for a blank ID or an unknown mode, ``OSError`` if the
    folder cannot be written.
    """
    sid = subject_id.strip()
    if not sid:
        raise ValueError("A Subject ID is required.")
    found = find_subject(root, sid)
    if found is not None:
        return found
    mode = folder_mode or FOLDER_MODE_ID
    if mode not in FOLDER_MODES:
        raise ValueError(f"folder_mode must be one of {FOLDER_MODES}, not {mode!r}")
    base_root = Path(root)
    base_root.mkdir(parents=True, exist_ok=True)
    number = _highest_code(base_root) + 1 if mode == FOLDER_MODE_CODE else 0
    base = _code_name(number) if mode == FOLDER_MODE_CODE else id_folder_name(sid)
    path = _claim_folder(base_root, base)
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        _write_json(
            path / SUBJECT_FILENAME,
            {"subject_id": sid, "folder_mode": mode, "created_at": created},
        )
        if number:
            _store_code(base_root, number)
    except OSError:
        try:
            (path / SUBJECT_FILENAME).unlink(missing_ok=True)
            path.rmdir()
        except OSError:
            pass
        raise
    return SubjectFolder(path=path, subject_id=sid, mode=mode, created_at=created)


def _store_code(root: Path, number: int) -> None:
    """Remember the highest code issued, so deleting its folder never frees it."""
    directory = system_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(_counter_path(root), {"last": number})
