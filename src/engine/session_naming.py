"""Session-directory naming with a collision-proof run index.

SPEC-ui-setup-task-selection.md S3.1.8: the dashboard's embed-in-place task
hosting explicitly wants to support re-running the same task for the same
subject on the same day (diki's own "run in any order, re-run freely"
model). The pre-existing ``<date>_<subject_id>_<task_id>`` naming
(:mod:`src.app`) has no run/time component, so a same-day re-run would
silently reuse -- and overwrite -- the prior run's session directory
(``SessionRecorder`` creates its directory with ``exist_ok=True``). Kept
Qt-free so it can be unit tested without importing PySide6.
"""

from __future__ import annotations

import hashlib
import time
import unicodedata
from pathlib import Path

# Characters Windows refuses in a file or folder name (this includes the path separators).
_ILLEGAL_DIRNAME_CHARS = frozenset('<>:"/\\|?*')
_MAX_DIRNAME_LEN = 80
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
)


def safe_subject_dirname(subject_id: str) -> str:
    """Turn a Subject ID into one safe folder name (SPEC-compass-task-flow.md 4A.9).

    The ID is typed free-hand in Setup and used to be joined straight into
    paths, so an ID such as ``..\\x`` or ``A/B`` became a real path. Steps:
    NFC-normalise; replace each of ``<>:"/\\|?*`` and every control character
    with ``_``; strip trailing dots and spaces; cut at 80 characters; prefix
    ``_`` if the result is empty or a Windows device name (CON, NUL, COM1, ...,
    with or without an extension). If anything changed, ``~`` and the first 6
    hex of the original's SHA-1 are appended, so "A/B" and "A_B" never share a
    folder.

    Ordinary IDs (letters, digits, space, ``_ - .``) come back **unchanged**,
    so the ``_settings`` and ``_calibrations`` folders written before this
    function existed still match. The verbatim ID stays in ``metadata.json``
    and in the test record; only the folder name is sanitised.
    """
    name = unicodedata.normalize("NFC", subject_id)
    name = "".join(
        "_" if ch in _ILLEGAL_DIRNAME_CHARS or unicodedata.category(ch) == "Cc" else ch
        for ch in name
    )
    name = name.rstrip(". ")[:_MAX_DIRNAME_LEN].rstrip(". ")
    if not name or name.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_DEVICE_NAMES:
        name = "_" + name
    if name != subject_id:
        digest = hashlib.sha1(
            subject_id.encode("utf-8", errors="surrogatepass"), usedforsecurity=False
        ).hexdigest()[:6]
        name = f"{name}~{digest}"
    return name


def next_run_number(
    output_root: str | Path, subject_id: str, task_id: str, date_str: str | None = None
) -> int:
    """Return the next free run index ``N`` for this subject/task/day.

    Extracted out of :func:`next_session_id` (SPEC-ui-setup-task-selection.md
    S11.5) so the dashboard UI can show "this will be run N" the moment Run
    is clicked, without duplicating the directory-scan logic or waiting for
    ``AssessmentApp``/``SessionRecorder`` to create the directory first.
    """
    date_str = date_str or time.strftime("%Y-%m-%d")
    base = f"{date_str}_{safe_subject_dirname(subject_id)}_{task_id}"
    root = Path(output_root)
    n = 1
    while (root / f"{base}_run{n}").exists():
        n += 1
    return n


def next_session_id(
    output_root: str | Path, subject_id: str, task_id: str, date_str: str | None = None
) -> str:
    """Return ``<date>_<subject_id>_<task_id>_run<N>`` for the next free ``N``.

    ``<subject_id>`` here is :func:`safe_subject_dirname` of the ID (unchanged
    for an ordinary one).

    ``N`` starts at 1 and is chosen by checking which ``_run<N>`` directories
    already exist under ``output_root`` -- so a re-run never overwrites a
    prior attempt, and a from-scratch subject/task/day always gets ``_run1``.
    """
    date_str = date_str or time.strftime("%Y-%m-%d")
    n = next_run_number(output_root, subject_id, task_id, date_str=date_str)
    return f"{date_str}_{safe_subject_dirname(subject_id)}_{task_id}_run{n}"
