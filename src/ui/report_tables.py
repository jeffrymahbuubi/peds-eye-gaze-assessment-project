"""Small read-only tables of the report page (SPEC-compass-task-flow.md 4D.2).

:class:`FitTable` is a plain table sized to its rows, so the page scrolls as a whole
and no table has a scrollbar of its own: the Test Configuration, Summary of Results
and Eye Metrics tables. The Trial-by-Trial table, which does scroll, is
:class:`~src.ui.frozen_table.FrozenColumnTable`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


class FitTable(QTableWidget):
    """A table with a header row and no editing, as tall as its rows.

    ``stretch_column`` takes the spare width; the other columns fit their contents.
    With ``wrap`` the long cells of that column wrap, and the height follows the
    width; ``compact`` halves the cell padding. The theme's ``QTableWidget`` rule gives it its look inside the dashboard.
    """

    def __init__(
        self,
        header: Sequence[str],
        *,
        stretch_column: int = 0,
        wrap: bool = False,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(0, len(header), parent)
        self._wrap = wrap
        # The theme pads a header section by 6 px 8 px; the (hidden) vertical header takes the
        # same rule and would make every row 13 px taller than its text needs.
        style = "QHeaderView::section:vertical { padding: 0px; border: none; }"
        if compact:  # a long table that should not push what is under it off the screen
            style += " QTableWidget::item { padding: 2px 8px; }"
        self.setStyleSheet(style)
        self.setHorizontalHeaderLabels(list(header))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWordWrap(wrap)
        self.setShowGrid(True)
        self.verticalHeader().hide()
        head = self.horizontalHeader()
        head.setSectionsClickable(False)
        head.setHighlightSections(False)
        for column in range(len(header)):
            head.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch
                if column == stretch_column
                else QHeaderView.ResizeMode.ResizeToContents,
            )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rows(
        self,
        rows: Sequence[Sequence[str]],
        *,
        aligns: Sequence[Qt.AlignmentFlag] | None = None,
        bold_first: bool = False,
    ) -> None:
        """Replace the rows (each a list of display text). ``aligns`` is per column."""
        self.setRowCount(len(rows))
        for r, cells in enumerate(rows):
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                align = aligns[c] if aligns else Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                if bold_first and c == 0:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                self.setItem(r, c, item)
        self.fit_height()

    def cell_text(self, row: int, column: int) -> str:
        item = self.item(row, column)
        return item.text() if item is not None else ""

    def texts(self) -> list[list[str]]:
        return [
            [self.cell_text(r, c) for c in range(self.columnCount())] for r in range(self.rowCount())
        ]

    def fit_height(self) -> None:
        """Make the table exactly tall enough for its header and rows."""
        self.resizeRowsToContents()
        height = self.horizontalHeader().height() + 2 * self.frameWidth()
        height += sum(self.rowHeight(r) for r in range(self.rowCount()))
        if self.height() != height:
            self.setFixedHeight(height)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if self._wrap:  # a new width wraps the long cells differently
            self.fit_height()
