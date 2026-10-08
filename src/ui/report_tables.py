"""Small read-only tables of the report page (SPEC-compass-task-flow.md 4D.2).

:class:`FitTable` is a plain table sized to its rows, so the page scrolls as a whole
and no table has a scrollbar of its own: the Test Configuration, Summary of Results
and Eye Metrics tables. The Trial-by-Trial table, which does scroll, is
:class:`~src.ui.frozen_table.FrozenColumnTable`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, Qt
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

from .design_tokens import TABLE_ROW_HEIGHT

# What changes the size a row or the header needs: the style sheet it ends up under (a table
# is filled before the page is put in the dashboard, so the theme's cell padding arrives
# later), the font, the screen's scale.
_REFIT_EVENTS = frozenset(
    {
        QEvent.Type.Polish,
        QEvent.Type.StyleChange,
        QEvent.Type.FontChange,
        QEvent.Type.ParentChange,
        QEvent.Type.Show,
        QEvent.Type.DevicePixelRatioChange,
    }
)


class FitTable(QTableWidget):
    """A table with a header row and no editing, as tall as its rows.

    ``stretch_column`` takes the spare width; the other columns fit their contents.
    With ``wrap`` the long cells of that column wrap, and the height follows the
    width; ``compact`` halves the cell padding. The theme's ``QTableWidget`` rule gives it its look inside the dashboard.

    The height is the header plus every row's real height plus the frame, measured when
    the rows are set and again whenever the style sheet, font or screen scale changes,
    so no row is ever cut and the table never needs a scroll bar of its own.
    """

    _ready = False  # events during construction have nothing to fit yet

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
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWordWrap(wrap)
        self.setShowGrid(True)
        self.verticalHeader().hide()
        if not compact:  # a compact table keeps its short rows (it is the long one)
            self.verticalHeader().setMinimumSectionSize(TABLE_ROW_HEIGHT)
            self.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        head = self.horizontalHeader()
        head.setSectionsClickable(False)
        head.setHighlightSections(False)
        self._apply_header(header, stretch_column)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._ready = True

    def _apply_header(self, header: Sequence[str], stretch_column: int) -> None:
        self.setColumnCount(len(header))
        self.setHorizontalHeaderLabels(list(header))
        head = self.horizontalHeader()
        for column in range(len(header)):
            head.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch
                if column == stretch_column
                else QHeaderView.ResizeMode.ResizeToContents,
            )

    def set_header(self, header: Sequence[str], *, stretch_column: int = 0) -> None:
        """Change the columns (their labels, and which one takes the spare width). The rows
        are the caller's next :meth:`set_rows`; it is what refits the height."""
        self._apply_header(header, stretch_column)

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
        """Make the table exactly tall enough for its header and rows, as they are now."""
        # Polish the headers first: a header not yet polished has not got the style sheet's
        # padding and font, and its size hint (and every row's) would come out too small.
        head = self.horizontalHeader()
        for part in (self, head, self.verticalHeader()):
            part.ensurePolished()
        self.resizeRowsToContents()
        # QTableView lays the header out at its size hint (or its minimum height), not at
        # whatever height() it had before the first layout.
        header_height = 0 if head.isHidden() else max(head.minimumHeight(), head.sizeHint().height())
        rows_height = sum(self.rowHeight(r) for r in range(self.rowCount()))
        height = header_height + rows_height + 2 * self.frameWidth()
        if self.maximumHeight() != height or self.minimumHeight() != height:
            self.setFixedHeight(height)

    def event(self, event) -> bool:
        handled = super().event(event)
        if self._ready and event.type() in _REFIT_EVENTS:
            self.fit_height()
        return handled

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if self._wrap:  # a new width wraps the long cells differently
            self.fit_height()
