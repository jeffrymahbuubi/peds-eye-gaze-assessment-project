"""Subject-ID to folder-name rule (SPEC-compass-task-flow.md 4A.9).

Run folders are no longer named here: they live under the subject's own folder
(:mod:`src.engine.run_paths`, SPEC-subject-data-layout.md H2). What remains is
the one rule that turns a free-hand Subject ID into a safe folder name. Kept
Qt-free so it can be unit tested without importing PySide6.
"""

from __future__ import annotations

import hashlib
import unicodedata

# Characters Windows refuses in a file or folder name (this includes the path separators).
_ILLEGAL_DIRNAME_CHARS = frozenset('<>:"/\\|?*')
_MAX_DIRNAME_LEN = 80
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
)


def safe_subject_dirname(subject_id: str, max_len: int = _MAX_DIRNAME_LEN) -> str:
    """Turn a Subject ID into one safe folder name (SPEC-compass-task-flow.md 4A.9).

    The ID is typed free-hand in Setup and used to be joined straight into
    paths, so an ID such as ``..\\x`` or ``A/B`` became a real path. Steps:
    NFC-normalise; replace each of ``<>:"/\\|?*`` and every control character
    with ``_``; strip trailing dots and spaces; cut at ``max_len`` characters
    (80 by default; a subject's folder uses 40, SPEC-subject-data-layout.md
    H5); prefix ``_`` if the result is empty or a Windows device name (CON,
    NUL, COM1, ..., with or without an extension). If anything changed, ``~``
    and the first 6 hex of the original's SHA-1 are appended, so "A/B" and
    "A_B" never share a folder.

    Ordinary IDs (letters, digits, space, ``_ - .``) come back **unchanged**.
    The verbatim ID stays in ``subject.json``, ``metadata.json`` and the test
    record; only the folder name is sanitised.
    """
    name = unicodedata.normalize("NFC", subject_id)
    name = "".join(
        "_" if ch in _ILLEGAL_DIRNAME_CHARS or unicodedata.category(ch) == "Cc" else ch
        for ch in name
    )
    name = name.rstrip(". ")[:max_len].rstrip(". ")
    if not name or name.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_DEVICE_NAMES:
        name = "_" + name
    if name != subject_id:
        digest = hashlib.sha1(
            subject_id.encode("utf-8", errors="surrogatepass"), usedforsecurity=False
        ).hexdigest()[:6]
        name = f"{name}~{digest}"
    return name
