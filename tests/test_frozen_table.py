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
