"""SPEC-test-list-visual-identity.md direction A "Ledger" (TA1-TA6, T3, T5, T6, T8): the Test List's
rows have no vertical lines but a 1 px rule under each, a tint on the hovered row, secondary text
in Task and Configuration and right-aligned dates; the seven buttons are the rows of one command
panel. Colours are read from what the themed page paints; the text itself is boxes offscreen, so
only fills, rules and the position of the first box are measured. Offscreen Qt."""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from src.engine.subject_tests import create_test
from src.ui import design_tokens as tokens
from src.ui.design_tokens import CONTRAST_PAIRS
from src.ui.test_list_panel import PANEL_PADDING
from src.ui.test_list_style import PANEL_STYLE, TABLE_STYLE
from src.ui.test_list_table import COL_CONFIG, COL_DATE, COL_NAME, COL_STATUS, COL_TASK, HEADERS
from src.ui.wtmh_theme import STYLESHEET
from tests.list_page_fixtures import SUBJECT, done_test, page_for

LABELS = ["Add New Test", "Configure Test", "Run Test", "View Report", "Copy Test", "Delete Test",
          "Open Subject Folder"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sessions"


def five_rows(root):
    """Grid Click 1 (not done), Static Click 1 (done), Follow the Target 1, Scanning Search 1, Grid Click 2."""
    create_test(root, SUBJECT, "click_grid", name="Grid Click 1")
    done_test(root, "click_static", name="Static Click 1")
    done_test(root, "follow_moving", name="Follow the Target 1", planned=6, completed=4)
    done_test(root, "scanning", name="Scanning Search 1")
    create_test(root, SUBJECT, "click_grid", name="Grid Click 2")


def themed(page, width=1500, height=520):
    """The page inside the dashboard's themed root, shown. The root owns the page: keep it alive."""
    shell = QWidget()
    shell.setObjectName("wtmhDashboard")
    shell.setStyleSheet(STYLESHEET)
    QHBoxLayout(shell).addWidget(page)
    shell.resize(width, height)
    shell.show()
    QCoreApplication.processEvents()
    return shell


def viewport_image(page):
    return page.table.viewport().grab().toImage()


def row_top(page, row):
    return page.table.rowViewportPosition(row)


def hover(page, row):
    """Move the mouse over ``row`` (a 'Test Name' cell, left of its text)."""
    table = page.table
    QTest.mouseMove(table.viewport(), QPoint(2, row_top(page, row) + 20))
    QCoreApplication.processEvents()
    assert table.hover_row == row


# -- the table: horizontal rules only ---------------------------------------------------------------------


def test_the_table_has_no_grid_and_forty_pixel_rows(qapp, root):
    five_rows(root)
    page = page_for(root)
    assert not page.table.showGrid()
    assert page.table.verticalHeader().defaultSectionSize() == tokens.TABLE_ROW_HEIGHT == 40


def test_a_rule_runs_under_every_row_and_no_line_between_the_columns(qapp, root):
    five_rows(root)
    page = page_for(root)
    shell = themed(page)
    page.table.clearSelection()
    QCoreApplication.processEvents()
    image = viewport_image(page)
    rule, white = QColor(tokens.BORDER_SUBTLE), QColor(tokens.PANEL)
    header = page.table.horizontalHeader()
    for row in range(page.table.rowCount()):
        top = row_top(page, row)
        for column in range(5):  # the rule crosses every column, across the badge cell too
            x = header.sectionViewportPosition(column) + 2
            assert image.pixelColor(x, top + 39) == rule, (row, column)
            assert image.pixelColor(x, top + 38) == white, (row, column)  # a 1 px line, nothing thicker
    for column in range(1, 5):  # no vertical line: both sides of a column edge are plain white
        edge = header.sectionViewportPosition(column)
        for dx in (-2, -1, 0, 1):
            assert image.pixelColor(edge + dx, row_top(page, 1) + 20) == white, (column, dx)
    shell.close()


def test_the_selected_row_is_the_chosen_blue_and_a_hovered_row_the_pale_tint(qapp, root):
    five_rows(root)
    page = page_for(root)
    shell = themed(page)
    page.select_test(next(t for t in page._tests.values() if t.name == "Static Click 1").test_id)
    row = page.table.currentRow()
    QCoreApplication.processEvents()
    hover(page, 3)
    image = viewport_image(page)
    for column in range(5):
        x = page.table.horizontalHeader().sectionViewportPosition(column) + 2
        assert image.pixelColor(x, row_top(page, row) + 20) == QColor(tokens.ROW_SELECTED), column
        assert image.pixelColor(x, row_top(page, 3) + 20) == QColor(tokens.ACCENT_SUBTLE), column
        assert image.pixelColor(x, row_top(page, 0) + 20) == QColor(tokens.PANEL), column
    hover(page, row)  # a hovered chosen row keeps the chosen fill
    image = viewport_image(page)
    assert image.pixelColor(2, row_top(page, row) + 20) == QColor(tokens.ROW_SELECTED)
    assert image.pixelColor(2, row_top(page, 3) + 20) == QColor(tokens.PANEL)  # and the tint moved away
    shell.close()


def test_the_tint_follows_the_mouse_and_goes_when_it_leaves_or_leaves_the_rows(qapp, root):
    five_rows(root)
    page = page_for(root)
    shell = themed(page)
    table = page.table
    assert table.hover_row == -1
    hover(page, 2)
    QTest.mouseMove(table.viewport(), QPoint(2, row_top(page, 4) + 60))  # below the last row
    QCoreApplication.processEvents()
    assert table.hover_row == -1
    hover(page, 1)
    QCoreApplication.sendEvent(table.viewport(), QEvent(QEvent.Type.Leave))
    assert table.hover_row == -1
    page.table.clearSelection()
    assert viewport_image(page).pixelColor(2, row_top(page, 1) + 20) == QColor(tokens.PANEL)
    shell.close()


def test_the_tint_survives_a_sort_and_a_reload_on_the_row_under_the_mouse(qapp, root):
    five_rows(root)
    page = page_for(root)
    shell = themed(page)
    hover(page, 2)
    page.table.horizontalHeader().sectionClicked.emit(COL_NAME)
    page.reload()
    QCoreApplication.processEvents()
    assert page.table.hover_row == 2  # a row position, as the mouse is
    page.table.clearSelection()
    assert viewport_image(page).pixelColor(2, row_top(page, 2) + 20) == QColor(tokens.ACCENT_SUBTLE)
    shell.close()


# -- the cells: secondary text, right-aligned tabular dates -----------------------------------------------


def test_task_and_configuration_are_secondary_text_and_the_rest_ink(qapp, root):
    five_rows(root)
    page = page_for(root)
    table = page.table
    for row in range(table.rowCount()):
        for column in (COL_TASK, COL_CONFIG):
            assert table.item(row, column).foreground().color() == QColor(tokens.TEXT_SECONDARY)
        for column in (COL_NAME, COL_STATUS, COL_DATE):  # no colour of their own: the sheet's ink
            assert table.item(row, column).foreground().style() == Qt.BrushStyle.NoBrush
    shell = themed(page)
    table.ensurePolished()
    assert table.palette().color(table.foregroundRole()) == QColor(tokens.INK)
    shell.close()


def test_the_dates_and_their_header_are_right_aligned_with_tabular_figures(qapp, root):
    five_rows(root)
    page = page_for(root)
    table = page.table
    right = Qt.AlignmentFlag.AlignRight
    assert HEADERS[COL_DATE] == "Date Complete"
    assert table.horizontalHeaderItem(COL_DATE).textAlignment() & right
    for row in range(table.rowCount()):
        item = table.item(row, COL_DATE)
        assert item.textAlignment() & right and item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
        assert not item.font().bold()
        if hasattr(QFont, "Tag"):  # QFont.setFeature is Qt 6.7+
            assert item.font().featureValue(QFont.Tag("tnum")) == 1
    for column in (COL_NAME, COL_TASK, COL_CONFIG):  # the other columns keep their left alignment
        assert not table.item(0, column).textAlignment() & right
        assert not table.horizontalHeaderItem(column).textAlignment() & right


def test_the_date_label_and_the_dates_share_the_right_edge_and_the_arrow_has_room(qapp, root):
    """Both have 16 px on their right (the sheet's header and item padding), so the sort arrow
    drawn at the edge of a sorted Date header sits beside the label, not on it."""
    assert re.search(r"QHeaderView::section:horizontal:last\s*\{\s*padding-right:\s*16px", TABLE_STYLE)
    assert re.search(r"::item\s*\{\s*padding:\s*4px 16px 4px 8px", TABLE_STYLE)


def test_other_dashboard_tables_keep_their_grid_and_header_band(qapp, root):
    five_rows(root)
    page = page_for(root)
    plain = QTableWidget(2, 3)
    for row in range(2):
        for column in range(3):
            plain.setItem(row, column, QTableWidgetItem("x"))
    shell = themed(page)
    shell.layout().addWidget(plain)
    shell.resize(1500, 800)
    QCoreApplication.processEvents()
    assert plain.showGrid() and not page.table.showGrid()
    plain.ensurePolished()
    assert "QTableWidget#wtmhTestTable" not in STYLESHEET.replace("QTableWidget#wtmhTestTable::item:selected", "")
    for table in (plain, page.table):  # the header band is the HEADER fill in both
        image = table.horizontalHeader().grab().toImage()
        assert image.pixelColor(3, 3) == QColor(tokens.HEADER)
    shell.close()


# -- the command panel -----------------------------------------------------------------------------------


def panel_children(page):
    """The panel's layout, top to bottom: a button's text, or ``"---"`` for a rule."""
    layout = page.actions.layout()
    out = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        out.append("---" if isinstance(widget, QFrame) and widget.objectName() == "wtmhTestRule" else widget.text())
    return out


def test_the_seven_buttons_are_the_rows_of_one_card_in_four_groups(qapp, root):
    five_rows(root)
    page = page_for(root)
    panel = page.actions
    assert isinstance(panel, QFrame) and panel.objectName() == "wtmhCard"
    assert panel.parentWidget() is page and panel.styleSheet() == PANEL_STYLE
    assert panel_children(page) == [
        "Add New Test", "---", "Configure Test", "Run Test", "View Report", "---",
        "Copy Test", "Delete Test", "---", "Open Subject Folder",
    ]
    assert [t for t in panel_children(page) if t != "---"] == LABELS
    margins = panel.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (PANEL_PADDING,) * 4 == (8,) * 4
    assert panel.layout().spacing() == 0
    assert panel.minimumWidth() == 200
    rules = [panel.layout().itemAt(i).widget() for i in range(panel.layout().count())
             if panel_children(page)[i] == "---"]
    assert len(rules) == 3 and {r.height() for r in rules} == {1} and {r.minimumHeight() for r in rules} == {1}


def test_the_rules_are_the_card_border_colour_and_scoped_to_the_panel(qapp, root):
    assert tokens.BORDER_SUBTLE in PANEL_STYLE and "text-align: left" in PANEL_STYLE
    assert "wtmhTestRule" not in STYLESHEET and "text-align" not in STYLESHEET


def test_the_rows_are_tertiary_with_a_left_label_and_run_test_the_one_primary(qapp, root):
    five_rows(root)
    page = page_for(root)
    shell = themed(page)
    names = {b.text(): b.objectName() for b in page.actions.findChildren(type(page.add_button))}
    assert names == {label: ("wtmhPrimary" if label == "Run Test" else "wtmhTertiary") for label in LABELS}
    # Add New Test is the shortest label in its row: left-aligned, its first box sits a padding in from the
    # edge; centred, it would sit half the spare width in.
    button = page.add_button
    image = page.actions.grab().toImage()
    accent = QColor(tokens.ACCENT)
    xs = [x for x in range(button.x(), button.x() + button.width())
          for y in range(button.y() + 12, button.y() + 28) if image.pixelColor(x, y) == accent]
    left_gap, right_gap = min(xs) - button.x(), button.x() + button.width() - 1 - max(xs)
    assert left_gap < right_gap and left_gap <= 20, (left_gap, right_gap)
    shell.close()


def test_the_hover_and_disabled_looks_of_the_rows_are_the_tertiary_tier_of_the_theme(qapp, root):
    hover_rule = re.search(r"QPushButton#wtmhTertiary:hover[^{]*\{([^}]*)\}", STYLESHEET).group(1)
    assert f"background: {tokens.ACCENT_SUBTLE}" in hover_rule and f"color: {tokens.ACCENT}" in hover_rule
    off_rule = re.search(r"QPushButton#wtmhTertiary:disabled\s*\{([^}]*)\}", STYLESHEET).group(1)
    assert f"color: {tokens.TEXT_DISABLED}" in off_rule and f"background: {tokens.DISABLED_FILL}" in off_rule
    assert f"border-radius: {tokens.RADIUS}px" in re.search(r"QPushButton#wtmhTertiary\s*\{([^}]*)\}", STYLESHEET).group(1)


def test_disabled_rows_stay_visible_and_grey_and_a_disabled_run_test_stays_pale_blue(qapp, root):
    page = page_for(root)  # a subject with no tests: only Add New Test (and the folder, if there is one) is on
    shell = themed(page)
    off = [b for b in (page.configure_button, page.report_button, page.copy_button, page.delete_button)]
    assert not any(b.isEnabled() for b in off) and not page.run_button.isEnabled()
    image = page.actions.grab().toImage()
    for button in off:
        assert button.isVisible()
        colour = image.pixelColor(button.x() + 8, button.y() + button.height() // 2)
        assert colour == QColor(tokens.DISABLED_FILL), button.text()
    run = page.run_button
    assert image.pixelColor(run.x() + 8, run.y() + run.height() // 2) == QColor(tokens.ACCENT_DISABLED_FILL)
    assert all(b.height() == tokens.BUTTON_HEIGHT for b in (*off, run))
    on = page.add_button  # the enabled row is the card's own white
    assert image.pixelColor(on.x() + 8, on.y() + on.height() // 2) == QColor(tokens.PANEL)
    shell.close()


# -- the contrast table (T5) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fg", "bg"),
    [
        (tokens.INK, tokens.ACCENT_SUBTLE),  # a hovered row
        (tokens.TEXT_SECONDARY, tokens.ACCENT_SUBTLE),  # its Task and Configuration
        (tokens.TEXT_SECONDARY, tokens.ROW_SELECTED),  # the chosen row's
        (tokens.DANGER, tokens.ACCENT_SUBTLE),  # the Delete glyph on a hovered button
    ],
)
def test_every_new_foreground_background_pair_is_a_contrast_row(fg, bg):
    assert any(f == fg and b == bg for f, b, _ in CONTRAST_PAIRS)
