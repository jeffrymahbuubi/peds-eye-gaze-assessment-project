"""The table of the Tests tab and what its cells say (SPEC-compass-task-flow.md 4A.4;
SPEC-design-system-phase2.md H5).

Split out of :mod:`src.ui.test_list_page` to keep both under 500 lines: the column
layout, the pure text and sort-key helpers (:func:`natural_key`, :func:`status_text`,
:func:`date_cells`, :func:`status_badge_state`), the cell that sorts by a key rather than
by its text, and the table that turns Delete / F2 / Enter into signals.

The Status column shows a :class:`~src.ui.status_badge.StatusBadge` (glyph and word) in a
cell widget over its item. The item keeps the status text and the sort key, so sorting by
Status and the cell texts are as they were; the badge is only a view of them. Qt moves a
cell widget with its item when the table sorts.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..engine.subject_tests import STATUS_ENDED_EARLY, STATUS_NOT_DONE, SubjectTest
from ..engine.task_info import TASK_INFO
from .status_badge import StatusBadge

COL_NAME, COL_TASK, COL_CONFIG, COL_STATUS, COL_DATE = range(5)
HEADERS = ("Test Name", "Task", "Configuration", "Status", "Date Complete")
# Test Name 420, Task 180, Configuration 200, Status 180, Date 140 (H5); the table is at most
# 1200 px, so the columns' 1120 px and its frame always fit.
COLUMN_WIDTHS = (420, 180, 200, 180, 140)
TABLE_MAX_WIDTH = 1200
NO_DATE = "—"
DATA_MISSING = " · data missing"


def natural_key(text: str) -> list[Any]:
    """Case-insensitive, digits as numbers: ``"Grid Click 2" < "Grid Click 10"``. The
    split alternates text and digits, so two keys always compare like with like."""
    return [int(part) if i % 2 else part.casefold() for i, part in enumerate(re.split(r"(\d+)", text))]


def status_text(test: SubjectTest, data_missing: bool = False) -> str:
    """``Not Done`` / ``Done`` / ``Ended early (7/12)``, plus ``· data missing`` when a
    run's folder is gone (4A.4)."""
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


def status_badge_state(test: SubjectTest, data_missing: bool = False) -> tuple[str, str]:
    """``(kind, word)`` of the Status badge: ``Not done``, ``Done``, ``Ended early 7/12``
    (the counts when the record has them), or ``Data missing`` when the run's folder is
    gone, whatever the status was."""
    if data_missing:
        return "data_missing", "Data missing"
    if test.status == STATUS_NOT_DONE:
        return "not_done", "Not done"
    if test.status == STATUS_ENDED_EARLY:
        if test.completed_trials is not None and test.planned_trials is not None:
            return "ended_early", f"Ended early {test.completed_trials}/{test.planned_trials}"
        return "ended_early", "Ended early"
    return "done", "Done"


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


class _BadgeCell(QWidget):
    """The cell widget of the Status column: the badge, indented, centred vertically. It lets
    every mouse event through, so a click on the badge selects the row like any other cell."""

    def __init__(self, badge: StatusBadge) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.badge = badge


class _StatusDelegate(QStyledItemDelegate):
    """Paints the Status cell without its text: the item holds the status text for the sort
    and for ``row_texts``, but the badge over it says the state."""

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802 (Qt naming)
        super().initStyleOption(option, index)
        option.text = ""


class SubjectTestTable(QTableWidget):
    """The table, with the three keys of 4A.4 turned into signals."""

    deleteRequested = Signal()
    renameRequested = Signal()
    activateRequested = Signal()

    def __init__(self, rows: int, columns: int, parent: QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self.setItemDelegateForColumn(COL_STATUS, _StatusDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = self.horizontalHeader()
        for column, width in enumerate(COLUMN_WIDTHS):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, width)
        self.setFixedWidth(self.fitted_width())
        # A vertical scroll bar takes room from the viewport: widen the table by what it took,
        # so the five columns always show in full.
        self.verticalScrollBar().rangeChanged.connect(lambda *_: QTimer.singleShot(0, self._fit_width))

    def fitted_width(self) -> int:
        """The width the five columns and the frame need (without a scroll bar)."""
        return sum(COLUMN_WIDTHS) + 2 * self.frameWidth()

    def _fit_width(self) -> None:
        deficit = sum(COLUMN_WIDTHS) - self.viewport().width()
        if deficit:
            self.setFixedWidth(min(max(self.width() + deficit, self.fitted_width()), TABLE_MAX_WIDTH))

    def badge_at(self, row: int) -> StatusBadge | None:
        """The Status badge of ``row``."""
        cell = self.cellWidget(row, COL_STATUS)
        return cell.badge if isinstance(cell, _BadgeCell) else None

    def populate(self, tests: list[SubjectTest], data_missing: Callable[[SubjectTest], bool]) -> None:
        """Fill the rows from ``tests`` (signals blocked, selection cleared). Every cell
        carries the test id; the Status cell also holds the badge (nothing is bold any more:
        the badge, not the weight, says a test is not done)."""
        self.blockSignals(True)
        try:
            for row in range(self.rowCount()):
                self.removeCellWidget(row, COL_STATUS)
            self.clearContents()
            self.setRowCount(len(tests))
            for row, test in enumerate(tests):
                date_text, date_tip = date_cells(test.completed_at)
                task_name = TASK_INFO.get(test.task_id, (test.task_id, ""))[0]
                missing = data_missing(test)
                status = status_text(test, missing)
                cells = (
                    (test.name, natural_key(test.name), ""),
                    (task_name, task_name.casefold(), ""),
                    (test.configuration["name"], test.configuration["name"].casefold(), ""),
                    (status, status.casefold(), ""),
                    (date_text, date_tip, date_tip),  # "" for no date sorts first
                )
                for column, (text, key, tip) in enumerate(cells):
                    item = SortKeyItem(text, key)
                    item.setData(Qt.ItemDataRole.UserRole, test.test_id)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setToolTip(tip)
                    self.setItem(row, column, item)
                badge = StatusBadge(*status_badge_state(test, missing))
                # the full status as a sentence (the item's own text keeps the "· data missing"
                # the sort key and row_texts() know, hidden under the badge)
                badge.setToolTip(status.replace(DATA_MISSING, ", data missing"))
                self.setCellWidget(row, COL_STATUS, _BadgeCell(badge))
            self.clearSelection()
        finally:
            self.blockSignals(False)

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
