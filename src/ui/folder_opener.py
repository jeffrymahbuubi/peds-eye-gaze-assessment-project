"""Open a folder in the system file browser (Explorer on Windows), for the Test List's
"Open Subject Folder" button (SPEC-subject-data-layout.md H6)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_folder(path: str | Path) -> bool:
    """``True`` if the desktop accepted the request (``QDesktopServices.openUrl``)."""
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
