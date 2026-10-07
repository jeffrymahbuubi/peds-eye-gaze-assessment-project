"""The table of the Tests tab and what its cells say (SPEC-compass-task-flow.md 4A.4).

Split out of :mod:`src.ui.test_list_page` to keep both under 500 lines: the column
layout, the pure text and sort-key helpers (:func:`natural_key`, :func:`status_text`,
:func:`date_cells`), the cell that sorts by a key rather than by its text, and the table
that turns Delete / F2 / Enter into signals.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from ..engine.subject_tests import STATUS_ENDED_EARLY, STATUS_NOT_DONE, SubjectTest

COL_NAME, COL_TASK, COL_CONFIG, COL_STATUS, COL_DATE = range(5)
HEADERS = ("Test Name", "Task", "Configuration", "Status", "Date Complete")
NO_DATE = "—"
DATA_MISSING = " · data missing"


def natural_key(text: str) -> list[Any]:
    """Case-insensitive, digits as numbers: ``"Grid Click 2" < "Grid Click 10"``. The
    split alternates text and digits, so two keys always compare like with like."""
    return [int(part) if i % 2 else part.casefold() for i, part in enumerate(re.split(r"(\d+)", text))]


def status_text(test: SubjectTest, data_missing: bool = False) -> str:
    """``Not Done`` / ``Done`` / ``Ended early (7/12)``, plus ``· data missing`` when a
    run's session folder is gone (4A.4)."""
    if test.status == STATUS_NOT_DONE:
        return "Not Done"
    if test.status == STATUS_ENDED_EARLY:
        counts = (
            f" ({test.completed_trials}/{test.planned_trials})"
            if test.completed_trials is not None and test.planned_trials is not None
            else ""
        )
        text = f"Ended early{counts}"
    else:
        text = "Done"
    return text + (DATA_MISSING if data_missing else "")


def date_cells(completed_at: str | None) -> tuple[str, str]:
    """``(YYYY-MM-DD, tooltip with the full local time)`` of a completion time, or the
    dash and nothing. ``completed_at`` is local time with its offset; it is converted
    to local time again so a UTC-stamped record shows the local day."""
    if not completed_at:
        return NO_DATE, ""
    try:
        when = datetime.fromisoformat(completed_at)
    except ValueError:
        return NO_DATE, ""
    if when.tzinfo is not None:
        when = when.astimezone()
    return when.strftime("%Y-%m-%d"), when.strftime("%Y-%m-%d %H:%M:%S")


class SortKeyItem(QTableWidgetItem):
    """A cell that sorts by ``key`` rather than by its text."""

    def __init__(self, text: str, key: Any) -> None:
        super().__init__(text)
        self.key = key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        other_key = getattr(other, "key", None)
        if other_key is None:
            return super().__lt__(other)
        return self.key < other_key


class SubjectTestTable(QTableWidget):
    """The table, with the three keys of 4A.4 turned into signals."""

    deleteRequested = Signal()
    renameRequested = Signal()
    activateRequested = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self.deleteRequested.emit()
        elif key == Qt.Key.Key_F2:
            self.renameRequested.emit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activateRequested.emit()
        else:
            super().keyPressEvent(event)
