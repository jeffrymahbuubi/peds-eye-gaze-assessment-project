"""A read-only table whose first column stays put while the rest scrolls sideways
(the Trial-by-Trial table, SPEC-compass-task-flow.md 4D.2).

The standard Qt "frozen column" technique: a second :class:`QTableView` sharing this
table's model and selection model sits over the first column, showing only that
column, and follows the vertical scroll. Rows are selected as a whole, one at a time;
the selected row is drawn in bold (the wireframe's marker) on top of the highlight.
Sorting is the caller's (it refills the rows): a click on either header emits
:attr:`sortRequested` with the column, and :meth:`set_sort_indicator` mirrors the
arrow on both headers.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QWidget,
)

from .design_tokens import (
    ACCENT_FOCUS,
    BORDER_SUBTLE,
    FOCUS_BORDER_WIDTH,
    HEADER,
    INK,
    PANEL,
    ROW_SELECTED,
    TABLE_ROW_HEIGHT,
)

# The theme styles QTableWidget under wtmhDashboard; the overlay is a plain QTableView,
# so both get the same rule here (by object name) and cannot look different.
_STYLE = f"""
QTableView#reportTrialTable, QTableView#reportTrialFrozen {{
    background: {PANEL};
    color: {INK};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 0px;
    gridline-color: {BORDER_SUBTLE};
    outline: 0;
}}
QTableView#reportTrialTable:focus {{ border: {FOCUS_BORDER_WIDTH}px solid {ACCENT_FOCUS}; }}
QTableView#reportTrialFrozen {{ border: none; border-right: 2px solid {BORDER_SUBTLE}; }}
QTableView#reportTrialTable::item, QTableView#reportTrialFrozen::item {{ padding: 4px 8px; }}
QTableView#reportTrialTable::item:selected, QTableView#reportTrialFrozen::item:selected {{
    background: {ROW_SELECTED};
    color: {INK};
}}
QTableView#reportTrialTable QHeaderView::section, QTableView#reportTrialFrozen QHeaderView::section {{
    background: {HEADER};
    color: {INK};
    border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 6px 8px;
    font-weight: 600;
}}
"""


class _BoldSelectedDelegate(QStyledItemDelegate):
    """Draws the cells of the selected row in bold."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        if option.state & QStyle.StateFlag.State_Selected:
            option.font.setBold(True)


class FrozenColumnTable(QTableWidget):
    """``columns`` are the header labels; the first is the frozen one."""

    sortRequested = Signal(int)

    def __init__(self, columns: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(columns), parent)
        self.setObjectName("reportTrialTable")
        self.setHorizontalHeaderLabels(list(columns))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setShowGrid(True)
        self.setWordWrap(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicatorClearable(True)
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self.sortRequested)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(_BoldSelectedDelegate(self))
        self.setStyleSheet(_STYLE)

        frozen = QTableView(self)
        frozen.setObjectName("reportTrialFrozen")
        frozen.setModel(self.model())
        frozen.setSelectionModel(self.selectionModel())
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        frozen.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        frozen.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        frozen.setItemDelegate(_BoldSelectedDelegate(frozen))
        frozen.verticalHeader().hide()
        frozen.verticalHeader().setDefaultSectionSize(self.verticalHeader().defaultSectionSize())
        frozen.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen_header = frozen.horizontalHeader()
        frozen_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen_header.setSectionsClickable(True)
        frozen_header.setSortIndicatorShown(True)
        frozen_header.setSortIndicatorClearable(True)
        frozen_header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        frozen_header.sectionClicked.connect(self.sortRequested)
        for column in range(1, self.columnCount()):
            frozen.setColumnHidden(column, True)
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setStyleSheet(_STYLE)
        self.viewport().stackUnder(frozen)
        self._frozen = frozen

        header.sectionResized.connect(self._on_section_resized)
        header.geometriesChanged.connect(self._update_frozen_geometry)
        self.verticalScrollBar().valueChanged.connect(frozen.verticalScrollBar().setValue)
        frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        frozen.show()
        self._update_frozen_geometry()

    @property
    def frozen_view(self) -> QTableView:
        """The overlay showing only the first column."""
        return self._frozen

    def set_columns(self, columns: Sequence[str]) -> None:
        """Replace the columns (the report's layouts differ by task and by selection). The first
        stays the frozen one; the rows are the caller's next fill."""
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(list(columns))
        for column in range(1, self.columnCount()):
            self._frozen.setColumnHidden(column, True)
        self._update_frozen_geometry()

    def set_sort_indicator(self, column: int, order: Qt.SortOrder) -> None:
        for header in (self.horizontalHeader(), self._frozen.horizontalHeader()):
            header.setSortIndicator(column, order)

    # -- keeping the overlay in step ------------------------------------------

    def _on_section_resized(self, column: int, _old: int, new: int) -> None:
        if column == 0:
            # ``new``, not columnWidth(0): the header can still report the old size while
            # it is emitting this signal (it fits its sections to their contents).
            self._place_frozen(new)

    def _update_frozen_geometry(self) -> None:
        self._place_frozen(self.columnWidth(0))

    def _place_frozen(self, width: int) -> None:
        frame = self.frameWidth()
        self._frozen.setColumnWidth(0, width)
        self._frozen.setGeometry(
            frame, frame, width, self.viewport().height() + self.horizontalHeader().height()
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._update_frozen_geometry()

    def scrollTo(self, index: QModelIndex, hint: QAbstractItemView.ScrollHint = QAbstractItemView.ScrollHint.EnsureVisible) -> None:  # noqa: N802
        """Never scroll sideways to reveal the frozen column (it is always shown); a
        selection in it only brings its row into view vertically."""
        if index.column() > 0:
            super().scrollTo(index, hint)
            return
        rect = self.visualRect(index)
        bar = self.verticalScrollBar()
        if rect.top() < 0:
            bar.setValue(bar.value() + rect.top())
        elif rect.bottom() > self.viewport().height():
            bar.setValue(bar.value() + rect.bottom() - self.viewport().height())
