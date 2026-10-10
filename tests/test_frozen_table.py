"""The Trial-by-Trial table's frozen first column (SPEC-compass-task-flow.md 4D.2:
"first column frozen; horizontal scroll below ~1500 px"). Offscreen Qt: the overlay's
wiring is checked (shared model, hidden columns, scroll sync), never its pixel size."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from src.ui.frozen_table import FrozenColumnTable

COLUMNS = ["Trial", "Size (deg)", "Distance (deg)", "Outcome", "Trial Time (s)", "Reaction Time (s)"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_table(rows: int = 40, width: int = 420, height: int = 240) -> FrozenColumnTable:
    table = FrozenColumnTable(COLUMNS)
    table.setRowCount(rows)
    for r in range(rows):
        for c in range(len(COLUMNS)):
            table.setItem(r, c, QTableWidgetItem(f"{r + 1}" if c == 0 else f"cell {r},{c} with some width"))
    table.resizeColumnsToContents()
    table.resize(width, height)
    table.show()
    QCoreApplication.processEvents()
    return table


def test_the_overlay_shares_the_model_and_selection_and_shows_only_the_first_column(qapp):
    table = make_table()
    frozen = table.frozen_view
    assert frozen.model() is table.model()
    assert frozen.selectionModel() is table.selectionModel()
    assert not frozen.isColumnHidden(0)
    assert all(frozen.isColumnHidden(c) for c in range(1, len(COLUMNS)))
    assert frozen.columnWidth(0) == table.columnWidth(0)
    assert frozen.parent() is table


def test_the_overlay_covers_the_first_column_and_follows_a_resize(qapp):
    table = make_table()
    frozen = table.frozen_view
    assert frozen.geometry().width() == table.columnWidth(0)
    assert frozen.geometry().height() >= table.viewport().height()
    before = table.columnWidth(0)
    table.item(0, 0).setText("a much longer first-column text than before")  # sections fit their contents
    table.resizeColumnToContents(0)
    QCoreApplication.processEvents()
    assert table.columnWidth(0) > before
    assert frozen.columnWidth(0) == table.columnWidth(0)
    assert frozen.geometry().width() == table.columnWidth(0)
    table.resize(420, 300)
    QCoreApplication.processEvents()
    assert frozen.geometry().height() >= table.viewport().height()


def test_the_vertical_scroll_is_shared_both_ways(qapp):
    table = make_table(rows=60)
    frozen = table.frozen_view
    assert table.verticalScrollBar().maximum() > 0
    table.verticalScrollBar().setValue(90)
    assert frozen.verticalScrollBar().value() == 90
    frozen.verticalScrollBar().setValue(30)
    assert table.verticalScrollBar().value() == 30


def test_the_other_columns_scroll_sideways_and_the_first_stays(qapp):
    table = make_table(width=300)
    bar = table.horizontalScrollBar()
    assert bar.maximum() > 0  # more columns than room
    bar.setValue(bar.maximum())
    QCoreApplication.processEvents()
    assert not table.frozen_view.isHidden()
    assert table.frozen_view.geometry().x() == table.frameWidth()  # did not move with the scroll


def test_selecting_the_first_column_scrolls_its_row_into_view_but_never_sideways(qapp):
    table = make_table(rows=60, width=300)
    table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
    before = table.horizontalScrollBar().value()
    table.setCurrentCell(59, 0)
    QCoreApplication.processEvents()
    assert table.verticalScrollBar().value() > 0  # the last row is now in view
    assert table.horizontalScrollBar().value() == before  # and the sideways scroll was not undone
    table.setCurrentCell(0, 0)
    QCoreApplication.processEvents()
    assert table.verticalScrollBar().value() == 0


def test_a_row_is_selected_as_a_whole_one_at_a_time_and_cells_are_read_only(qapp):
    table = make_table(rows=5)
    assert table.selectionBehavior() == table.SelectionBehavior.SelectRows
    assert table.selectionMode() == table.SelectionMode.SingleSelection
    assert table.editTriggers() == table.EditTrigger.NoEditTriggers
    table.selectRow(2)
    table.selectRow(3)
    assert [i.row() for i in table.selectionModel().selectedRows()] == [3]
    assert table.frozen_view.selectionModel().isRowSelected(3)  # the overlay shows the same row


def test_a_click_on_either_header_asks_for_a_sort_of_that_column(qapp):
    table = make_table()
    asked: list[int] = []
    table.sortRequested.connect(asked.append)
    table.horizontalHeader().sectionClicked.emit(3)
    table.frozen_view.horizontalHeader().sectionClicked.emit(0)
    assert asked == [3, 0]


def test_the_sort_arrow_is_mirrored_on_both_headers_and_can_be_cleared(qapp):
    table = make_table()
    table.set_sort_indicator(0, Qt.SortOrder.DescendingOrder)
    for header in (table.horizontalHeader(), table.frozen_view.horizontalHeader()):
        assert header.sortIndicatorSection() == 0
        assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    table.set_sort_indicator(-1, Qt.SortOrder.AscendingOrder)
    assert table.horizontalHeader().sortIndicatorSection() == -1


def test_the_table_does_not_sort_by_itself(qapp):
    table = make_table(rows=3)
    assert not table.isSortingEnabled()
    table.horizontalHeader().sectionClicked.emit(1)
    assert [table.item(r, 0).text() for r in range(3)] == ["1", "2", "3"]  # the caller refills


def test_the_two_views_have_the_same_row_height_so_rows_line_up(qapp):
    table = make_table()
    assert table.frozen_view.verticalHeader().defaultSectionSize() == table.verticalHeader().defaultSectionSize()


def test_the_columns_can_be_replaced_and_only_the_first_stays_frozen(qapp):
    table = make_table(rows=3)
    wider = [*COLUMNS, "Clicks", "Click errors", "Fixations"]
    table.set_columns(wider)
    assert table.columnCount() == len(wider)
    assert [table.horizontalHeaderItem(c).text() for c in range(len(wider))] == wider
    frozen = table.frozen_view
    assert not frozen.isColumnHidden(0) and all(frozen.isColumnHidden(c) for c in range(1, len(wider)))
    table.set_columns(COLUMNS[:4])
    assert table.columnCount() == 4 and not table.frozen_view.isColumnHidden(0)
    assert all(table.frozen_view.isColumnHidden(c) for c in range(1, 4))
    assert table.frozen_view.columnWidth(0) == table.columnWidth(0)  # the overlay still covers column 0


# -- phase 4 (SPEC-design-system-phase4.md H7): widths from the text, two-line headers, badges ---------------


def test_fit_columns_sets_each_width_from_the_widest_cell_or_header_line_plus_room(qapp):
    from PySide6.QtGui import QFontMetrics

    from src.ui.frozen_table import MIN_COLUMN_PX, PADDING_PX, SORT_ARROW_PX

    table = FrozenColumnTable(["Trial", "Reaction\nTime (s)", "Outcome"])
    table.setRowCount(2)
    for r, texts in enumerate((["1", "0.31", "Not selected"], ["12", "0.5", "Hit"])):
        for c, text in enumerate(texts):
            table.setItem(r, c, QTableWidgetItem(text))
    table.fit_columns()
    body, head = (QFontMetrics(font) for font in table.table_fonts())
    longer_line = max(head.horizontalAdvance(line) for line in ("Reaction", "Time (s)"))
    cells = max(body.horizontalAdvance(text) for text in ("0.31", "0.5")) + PADDING_PX
    assert table.columnWidth(1) == max(MIN_COLUMN_PX, longer_line + PADDING_PX + SORT_ARROW_PX, cells)
    assert table.columnWidth(2) == max(
        head.horizontalAdvance("Outcome") + PADDING_PX + SORT_ARROW_PX, body.horizontalAdvance("Not selected") + PADDING_PX
    )
    assert table.columnWidth(0) >= MIN_COLUMN_PX and table.columns_width() == sum(table.columnWidth(c) for c in range(3))
    assert table.frozen_view.columnWidth(0) == table.columnWidth(0)  # the overlay follows
    first = table.columnWidth(1)
    table.fit_columns()
    assert table.columnWidth(1) == first  # and it is stable


def test_a_two_line_header_is_as_wide_as_its_longer_line_not_its_whole_label(qapp):
    from PySide6.QtGui import QFontMetrics

    from src.ui.frozen_table import PADDING_PX, SORT_ARROW_PX

    one = FrozenColumnTable(["Trial", "Reaction Time (s)"])
    two = FrozenColumnTable(["Trial", "Reaction\nTime (s)"])
    for table in (one, two):
        table.fit_columns()
    head = QFontMetrics(two.table_fonts()[1])
    assert two.columnWidth(1) == max(head.horizontalAdvance(line) for line in ("Reaction", "Time (s)")) + PADDING_PX + SORT_ARROW_PX
    assert two.columnWidth(1) < one.columnWidth(1)


def test_the_header_of_the_frozen_column_is_as_high_as_a_two_line_header_beside_it(qapp):
    table = FrozenColumnTable(["Trial", "Reaction\nTime (s)"])
    table.setRowCount(1)
    table.fit_columns()
    table.show()
    QCoreApplication.processEvents()
    assert table.horizontalHeader().sizeHint().height() > table.frozen_view.horizontalHeader().sizeHint().height()
    assert table.frozen_view.horizontalHeader().height() >= table.horizontalHeader().sizeHint().height()


def test_a_badge_column_shows_a_status_badge_over_the_cell_text(qapp):
    table = FrozenColumnTable(["Trial", "Outcome"])
    table.setRowCount(2)
    for r in range(2):
        table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
        table.setItem(r, 1, QTableWidgetItem("Hit" if r == 0 else "Skipped"))
    assert table.badge_column is None and table.badge_at(0) is None
    table.set_badge(0, "done", "Hit")  # no badge column yet: nothing happens
    assert table.badge_at(0) is None
    table.set_badge_column(1)
    table.set_badge(0, "done", "Hit", "tip")
    table.set_badge(1, "skipped", "Skipped")
    assert (table.badge_at(0).kind(), table.badge_at(0).text(), table.item(0, 1).toolTip()) == ("done", "Hit", "tip")
    assert table.badge_at(1).kind() == "skipped"
    assert table.item(0, 1).text() == "Hit"  # the item keeps the text, for the sort and for reading
    assert table.cellWidget(0, 1) is None  # painted by the delegate: no widget in the cell
    table.fit_columns()
    assert table.columnWidth(1) >= table.badge_at(0).width()  # a badge counts as its width
    table.clear_badges()
    assert table.badge_at(0) is None and table.badge_at(1) is None
    table.set_badge(0, "done", "Hit")
    table.set_badge_column(None)  # a new column choice clears the old badges
    assert table.badge_at(0) is None and table.badge_column is None


def test_a_badge_of_a_kind_that_does_not_exist_is_refused_when_it_is_set(qapp):
    table = FrozenColumnTable(["Trial", "Outcome"])
    table.setRowCount(1)
    table.setItem(0, 1, QTableWidgetItem("Hit"))
    table.set_badge_column(1)
    with pytest.raises(ValueError, match="Unknown badge kind"):
        table.set_badge(0, "no_such_kind", "Hit")
    assert table.badge_at(0) is None  # nothing was left on the cell for a paint to trip over


def test_the_badge_is_painted_over_the_cell_in_its_own_colours_and_the_row_fill_shows_round_it(qapp):
    from PySide6.QtGui import QColor

    from src.ui.design_tokens import PANEL

    table = FrozenColumnTable(["Trial", "Outcome", "Other"])
    table.setRowCount(2)
    for r in range(2):
        for c, text in enumerate((str(r + 1), "Hit", "x")):
            table.setItem(r, c, QTableWidgetItem(text))
    table.set_badge_column(1)
    table.set_badge(0, "done", "Hit")
    table.fit_columns()
    table.resize(table.columns_width() + 40, 200)
    table.show()
    QCoreApplication.processEvents()
    look = table.badge_at(0).look()
    image = table.viewport().grab().toImage()
    cell = table.visualRect(table.model().index(0, 1))
    middle = cell.center().y()
    between_glyph_and_word = cell.left() + 8 + 8 + 12 + 3  # indent, pill padding, glyph, 3 px of the gap
    assert QColor(image.pixelColor(between_glyph_and_word, middle)).name().lower() == look.fill.lower()
    assert QColor(image.pixelColor(cell.left() + 2, middle)).name().lower() == PANEL.lower()  # left of the pill
    other = table.visualRect(table.model().index(1, 1))  # a cell with no badge has none painted
    assert QColor(image.pixelColor(between_glyph_and_word, other.center().y())).name().lower() == PANEL.lower()
    table.close()


def test_the_cells_are_14_px_with_tabular_figures_and_the_header_is_semibold(qapp):
    from PySide6.QtGui import QFont

    table = FrozenColumnTable(["Trial", "Size (deg)"])
    body, header = table.table_fonts()
    assert body.pixelSize() == 14 and header.pixelSize() == 14
    assert header.weight() == QFont.Weight.DemiBold and body.weight() != header.weight()
    assert table.font().pixelSize() == 14 and table.frozen_view.font().pixelSize() == 14
    if hasattr(QFont, "Tag"):
        assert body.featureValue(QFont.Tag("tnum")) == 1


# -- room for a number of rows (the Detailed table below the map keeps eight) ---------------------------------------


def test_height_for_rows_is_the_header_the_rows_and_the_frame(qapp):
    table = FrozenColumnTable(COLUMNS)
    header = table.horizontalHeader().sizeHint().height()
    row = table.verticalHeader().defaultSectionSize()
    assert table.height_for_rows(0) == header + 2 * table.frameWidth()
    assert table.height_for_rows(8) - table.height_for_rows(0) == 8 * row
    assert table.height_for_rows(8) - table.height_for_rows(7) == row


def test_set_minimum_rows_keeps_the_table_that_tall_and_zero_takes_it_off(qapp):
    table = FrozenColumnTable(COLUMNS)
    assert table.minimumHeight() == 0  # none unless asked for
    table.set_minimum_rows(8)
    assert table.minimumHeight() == table.height_for_rows(8)
    table.setRowCount(3)  # the minimum does not follow the number of rows
    table.fit_columns()
    assert table.minimumHeight() == table.height_for_rows(8)
    table.set_minimum_rows(0)
    assert table.minimumHeight() == 0


def test_a_table_with_a_minimum_shows_that_many_whole_rows_when_given_that_height(qapp):
    table = make_table(rows=20, width=900, height=100)
    table.set_minimum_rows(8)
    table.resize(900, 100)  # asked to be shorter: it cannot be
    QCoreApplication.processEvents()
    assert table.height() >= table.height_for_rows(8)
    assert table.viewport().height() // table.verticalHeader().defaultSectionSize() >= 7  # the bar of a sideways scroll may take a row's part
    table.close()
