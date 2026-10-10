"""A read-only table whose first column stays put while the rest scrolls sideways
(the Trial-by-Trial table, SPEC-compass-task-flow.md 4D.2; SPEC-design-system-phase4.md H7).

The standard Qt "frozen column" technique: a second :class:`QTableView` sharing this
table's model and selection model sits over the first column, showing only that
column, and follows the vertical scroll. Rows are selected as a whole, one at a time;
the selected row has the row-selected fill (bold is never a state cue). Sorting is the
caller's (it refills the rows): a click on either header emits :attr:`sortRequested` with
the column, and :meth:`set_sort_indicator` mirrors the arrow on both headers.

The cells are 14 px with tabular figures, and a header label may have two lines (a newline in
it: "Reaction\\nTime (s)"). The column widths are not left to the header: Qt adds the sort
arrow's room, as high as the header is, to every section, which two-line headers would double.
:meth:`fit_columns` sets each width from the text instead (the widest cell or header line plus
the sheet's padding and room for the arrow), so thirteen columns fit about 1,370 px.
:meth:`set_minimum_rows` keeps the table tall enough to show that many rows under the header.

One column may hold status badges (:meth:`set_badge_column`, :meth:`set_badge`): the item keeps
the text, for the sort and for reading, and the badge painted over it says the state. The delegate
paints it with the :class:`~src.ui.status_badge.StatusBadge` widget's own drawing
(:func:`~src.ui.status_badge.paint_badge`). It is not a cell widget: with a widget in every Outcome cell, long test
runs that built and dropped many tables died with an access violation, which stopped once the
cells held none.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QModelIndex, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
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
    TYPE_BODY,
)
from .status_badge import BADGE_HEIGHT, LOOKS, BadgeLook, badge_width, paint_badge

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
    font-size: {TYPE_BODY}px;
}}
QTableView#reportTrialTable:focus {{ border: {FOCUS_BORDER_WIDTH}px solid {ACCENT_FOCUS}; }}
QTableView#reportTrialFrozen {{ border: none; border-right: 2px solid {BORDER_SUBTLE}; }}
QTableView#reportTrialTable::item, QTableView#reportTrialFrozen::item {{ padding: 4px 8px; }}
QTableView#reportTrialTable::item:selected, QTableView#reportTrialFrozen::item:selected {{
    background: {ROW_SELECTED};
    color: {INK};
}}
QTableView#reportTrialTable QHeaderView, QTableView#reportTrialFrozen QHeaderView {{
    background: {HEADER};
    border: none;
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

# What a column needs besides its text: the sheet's 8 px of padding on each side and the grid
# line (cell and header alike), and the room kept for the sort arrow at the right of a header.
PADDING_PX = 18
SORT_ARROW_PX = 16
MIN_COLUMN_PX = 48
BADGE_KIND_ROLE = Qt.ItemDataRole.UserRole + 10  # cell data: the kind of the badge painted over it
BADGE_TEXT_ROLE = Qt.ItemDataRole.UserRole + 11  # ... and its word
BADGE_INDENT_PX = 8


def two_lines(label: str) -> str:
    """``label`` on two lines, split at the space that makes the longer line shortest ("Reaction
    Time (s)" becomes "Reaction" over "Time (s)"). A one-word label stays on one line and a word
    is never split."""
    words = label.split(" ")
    if len(words) < 2:
        return label
    at = min(
        range(1, len(words)),
        key=lambda i: (max(len(" ".join(words[:i])), len(" ".join(words[i:]))), i),
    )
    return " ".join(words[:at]) + "\n" + " ".join(words[at:])


class BadgeCell:
    """A badge painted over a cell: its ``kind()``, its word ``text()``, its ``look()`` (glyph and
    colours) and its ``width()``."""

    def __init__(self, kind: str, text: str) -> None:
        self._kind, self._text = kind, text

    def kind(self) -> str:
        return self._kind

    def text(self) -> str:
        return self._text

    def look(self) -> BadgeLook:
        return LOOKS[self._kind]

    def width(self) -> int:
        return badge_width(self._text)


class _CellDelegate(QStyledItemDelegate):
    """The standard cell; where a badge belongs it has no text of its own and the badge is painted
    over it (indented, centred vertically). It reads the cell's own data (:data:`BADGE_KIND_ROLE`)
    and holds no reference to the table: a reference back made a cycle through the C++ ownership,
    so the table was freed by the cyclic collector at a random moment (inside some other widget's
    event) rather than when its last reference went."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        if index.data(BADGE_KIND_ROLE):
            option.text = ""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().paint(painter, option, index)  # the background, the selection, no text
        kind = index.data(BADGE_KIND_ROLE)
        if not kind:
            return
        text = index.data(BADGE_TEXT_ROLE) or ""
        top = option.rect.top() + (option.rect.height() - BADGE_HEIGHT) // 2
        rect = QRectF(option.rect.left() + BADGE_INDENT_PX, top, badge_width(text), BADGE_HEIGHT)
        paint_badge(painter, rect, kind, text, painter.device().devicePixelRatioF())  # the row's fill shows round it


class FrozenColumnTable(QTableWidget):
    """``columns`` are the header labels; the first is the frozen one."""

    sortRequested = Signal(int)

    def __init__(self, columns: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(columns), parent)
        self.badge_column: int | None = None
        self._minimum_rows = 0
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
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)  # fit_columns() sets the widths
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicatorClearable(True)
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self.sortRequested)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._cells = _CellDelegate(self)
        self.setItemDelegate(self._cells)
        self.setStyleSheet(_STYLE)
        body_font, header_font = self.table_fonts()
        self.setFont(body_font)
        header.setFont(header_font)

        frozen = QTableView(self)
        frozen.setObjectName("reportTrialFrozen")
        frozen.setModel(self.model())
        frozen.setSelectionModel(self.selectionModel())
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        frozen.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        frozen.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        frozen.setItemDelegate(_CellDelegate(frozen))
        frozen.setFont(body_font)
        frozen.verticalHeader().hide()
        frozen.verticalHeader().setDefaultSectionSize(self.verticalHeader().defaultSectionSize())
        frozen.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen_header = frozen.horizontalHeader()
        frozen_header.setFont(header_font)
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

    def table_fonts(self) -> tuple[QFont, QFont]:
        """The cell font and the header font: the application's family at 14 px with tabular
        figures (so the digits of a column line up), the header at weight 600."""
        body = QFont(self.font())
        body.setPixelSize(TYPE_BODY)
        if hasattr(QFont, "Tag"):  # QFont.setFeature is Qt 6.7+
            body.setFeature(QFont.Tag("tnum"), 1)
        header = QFont(body)
        header.setWeight(QFont.Weight.DemiBold)
        return body, header

    def set_columns(self, columns: Sequence[str]) -> None:
        """Replace the columns (the report's layouts differ by task and by selection). The first
        stays the frozen one; the rows are the caller's next fill. A label may have two lines."""
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(list(columns))
        for column in range(1, self.columnCount()):
            self._frozen.setColumnHidden(column, True)
        self._update_frozen_geometry()

    def set_sort_indicator(self, column: int, order: Qt.SortOrder) -> None:
        for header in (self.horizontalHeader(), self._frozen.horizontalHeader()):
            header.setSortIndicator(column, order)

    # -- badges ----------------------------------------------------------------

    def set_badge_column(self, column: int | None) -> None:
        """The column whose cells show a badge over their (hidden) text, or ``None``."""
        self.clear_badges()
        self.badge_column = column
        self.viewport().update()

    def set_badge(self, row: int, kind: str, text: str, tooltip: str = "") -> None:
        """Paint a :class:`~src.ui.status_badge.StatusBadge` of ``kind`` and ``text`` over the
        badge column's cell of ``row`` (its item must be set; the item's text stays, unseen)."""
        item = self.item(row, self.badge_column) if self.badge_column is not None else None
        if item is None:
            return
        if kind not in LOOKS:  # refused here, not in a paint
            raise ValueError(f"Unknown badge kind '{kind}'. Known: {list(LOOKS)}")
        item.setData(BADGE_KIND_ROLE, kind)
        item.setData(BADGE_TEXT_ROLE, text)
        if tooltip:
            item.setToolTip(tooltip)

    def clear_badges(self) -> None:
        """Take every badge off (the rows are about to be refilled)."""
        if self.badge_column is None:
            return
        for row in range(self.rowCount()):
            item = self.item(row, self.badge_column)
            if item is not None:
                item.setData(BADGE_KIND_ROLE, None)
                item.setData(BADGE_TEXT_ROLE, None)

    def badge_at(self, row: int) -> BadgeCell | None:
        """What is painted over ``row``'s badge cell (its kind, word and width), if anything."""
        item = self.item(row, self.badge_column) if self.badge_column is not None else None
        kind = item.data(BADGE_KIND_ROLE) if item is not None else None
        return BadgeCell(kind, item.data(BADGE_TEXT_ROLE) or "") if kind else None

    # -- widths ------------------------------------------------------------------

    def fit_columns(self) -> None:
        """Set every column's width from its text: the widest cell (a badge counts as its
        width) or header line, plus the padding and room for the sort arrow, at least
        :data:`MIN_COLUMN_PX`. Call it after the rows are filled."""
        header = self.horizontalHeader()
        for part in (self, header):
            part.ensurePolished()
        body_font, header_font = self.table_fonts()
        body, head = QFontMetrics(body_font), QFontMetrics(header_font)
        for column in range(self.columnCount()):
            item = self.horizontalHeaderItem(column)
            lines = (item.text() if item else "").split("\n")
            width = max(head.horizontalAdvance(line) for line in lines) + PADDING_PX + SORT_ARROW_PX
            for row in range(self.rowCount()):
                width = max(width, self._cell_px(row, column, body))
            self.setColumnWidth(column, max(MIN_COLUMN_PX, width))
        self._sync_header_heights()
        self._apply_minimum_height()  # the header may have changed its height with the labels
        self._update_frozen_geometry()

    def set_minimum_rows(self, rows: int) -> None:
        """Keep the table at least tall enough to show ``rows`` rows under its header (the page
        around it scrolls instead of squeezing the table); 0 sets no minimum."""
        self._minimum_rows = max(0, rows)
        self._apply_minimum_height()

    def height_for_rows(self, rows: int) -> int:
        """The table height that shows ``rows`` rows under the header: the header, the rows
        and the frame (a sideways scroll bar, when one is needed, takes its own room)."""
        header = self.horizontalHeader()
        for part in (self, header):
            part.ensurePolished()
        return header.sizeHint().height() + rows * self.verticalHeader().defaultSectionSize() + 2 * self.frameWidth()

    def _apply_minimum_height(self) -> None:
        self.setMinimumHeight(self.height_for_rows(self._minimum_rows) if self._minimum_rows else 0)

    def columns_width(self) -> int:
        """The sum of the column widths (what the table needs, with the frame, to show every
        column without a sideways scroll)."""
        return sum(self.columnWidth(c) for c in range(self.columnCount()))

    def _cell_px(self, row: int, column: int, metrics: QFontMetrics) -> int:
        item = self.item(row, column)
        if item is None:
            return 0
        badge = self.badge_at(row) if column == self.badge_column else None
        if badge is not None:
            return badge.width() + PADDING_PX
        return metrics.horizontalAdvance(item.text()) + PADDING_PX

    def _sync_header_heights(self) -> None:
        """The overlay's header is as high as this one (two lines in a column that is not the
        first), so its rows line up with the rows beside it."""
        height = self.horizontalHeader().sizeHint().height()
        self._frozen.horizontalHeader().setMinimumHeight(height)

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
