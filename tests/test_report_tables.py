"""SPEC-compass-task-flow.md 7.1, FX2: a ``FitTable`` is as tall as its header plus every row's
real height plus the frame, so no row is cut and the table never needs a scroll bar.

The live bug: a table is filled while it still has no parent (``ReportFlow.open`` builds the
page, fills it, and only then puts it in the dashboard), so its height was measured without
the theme's cell padding and never measured again. Offscreen Qt has no fonts, so the tests
do not change a font's size; what they change is the style sheet the table ends up under
(the padding is font-independent) and they send the events a font or screen-scale change
raises, to see that each one measures again.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.ui.report_page import ReportPage
from src.ui.report_tables import FitTable
from src.ui.wtmh_theme import STYLESHEET
from tests.report_ui_fixtures import folder_report

ROWS = [["All Trials", "6", "1.2"], ["Hits", "3", "0.4"], ["Misses", "2", "0.9"], ["Skipped", "1", "-"]]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def themed_root() -> QWidget:
    """What the dashboard is to a page: a parent that carries the theme's sheet."""
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    QVBoxLayout(root)
    return root


def show(root: QWidget) -> None:
    root.resize(900, 700)
    root.show()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()


def assert_fits(table: FitTable) -> None:
    """Every row lies inside the viewport, and the table is exactly as tall as it needs."""
    head = table.horizontalHeader()
    header = 0 if head.isHidden() else max(head.minimumHeight(), head.sizeHint().height())
    rows = sum(table.rowHeight(r) for r in range(table.rowCount()))
    assert table.height() == header + rows + 2 * table.frameWidth()
    assert table.viewport().height() >= rows
    for r in range(table.rowCount()):
        rect = table.visualRect(table.model().index(r, 0))
        assert rect.top() >= 0 and rect.bottom() < table.viewport().height(), f"row {r} is cut"
    assert not table.verticalScrollBar().isVisible()


# -- the measure ------------------------------------------------------------------------------------


def test_the_height_is_the_header_plus_every_real_row_plus_the_frame(qapp):
    root = themed_root()
    table = FitTable(["Metric", "N", "Time"], stretch_column=0)
    root.layout().addWidget(table)
    table.set_rows(ROWS)
    show(root)
    assert_fits(table)


def test_a_table_filled_before_it_joins_the_styled_page_is_measured_again(qapp):
    """The live bug: filled parentless (no theme padding), shown under the dashboard."""
    table = FitTable(["Metric", "N", "Time"], stretch_column=0)
    table.set_rows(ROWS)
    before = table.height()
    root = themed_root()
    root.layout().addWidget(table)  # the theme's cell padding arrives now
    show(root)
    assert_fits(table)
    assert table.height() > before  # the rows really are taller under the theme


def test_a_style_change_after_filling_measures_again(qapp):
    root = themed_root()
    table = FitTable(["Metric", "N", "Time"], stretch_column=0)
    root.layout().addWidget(table)
    table.set_rows(ROWS)
    show(root)
    before = table.height()
    table.setStyleSheet(table.styleSheet() + " QTableWidget::item { padding: 14px 8px; }")
    QCoreApplication.processEvents()
    assert_fits(table)
    assert table.height() > before


def test_new_content_is_fitted_when_it_grows_and_when_it_shrinks(qapp):
    root = themed_root()
    table = FitTable(["Metric", "Value"], stretch_column=1)
    root.layout().addWidget(table)
    table.set_rows([[f"row {i}", "x"] for i in range(10)])
    show(root)
    assert_fits(table)
    tall = table.height()
    table.set_rows([["only", "x"], ["two", "y"]])
    QCoreApplication.processEvents()
    assert_fits(table)
    assert table.height() < tall
    table.set_rows([])
    assert table.height() == max(table.horizontalHeader().minimumHeight(),
                                 table.horizontalHeader().sizeHint().height()) + 2 * table.frameWidth()


@pytest.mark.parametrize(
    "kind",
    [QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.DevicePixelRatioChange,
     QEvent.Type.ParentChange, QEvent.Type.Polish, QEvent.Type.Show],
    ids=lambda kind: kind.name,
)
def test_every_event_that_changes_a_size_makes_it_measure_again(qapp, monkeypatch, kind):
    table = FitTable(["Metric", "N"], stretch_column=0)
    table.set_rows(ROWS)
    measured = []
    monkeypatch.setattr(table, "fit_height", lambda: measured.append(kind))
    QCoreApplication.sendEvent(table, QEvent(kind))
    assert measured == [kind]


def test_a_larger_font_still_fits_every_row(qapp):
    """A non-default font set on the page (offscreen the metrics do not follow it, so this
    pins that nothing in the measure assumes the default font, not the size of the font)."""
    root = themed_root()
    font = QFont(root.font())
    font.setPointSize(20)
    root.setFont(font)
    table = FitTable(["Metric", "N", "Time"], stretch_column=0, compact=True)
    root.layout().addWidget(table)
    table.set_rows(ROWS)
    show(root)
    assert_fits(table)
    table.setFont(QFont(font.family(), 30))
    QCoreApplication.processEvents()
    assert_fits(table)


# -- the real tables of the report page --------------------------------------------------------------------


def report_tables(page: ReportPage) -> dict[str, FitTable]:
    return {"config": page.config_table, "summary": page.summary.table, "eye": page.summary.eye_table}


def test_every_table_of_the_report_page_fits_when_the_page_is_built_before_the_dashboard(qapp, tmp_path):
    """Exactly what ``ReportFlow.open`` does: build, fill, then put it in the styled window."""
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    root = themed_root()
    root.layout().setContentsMargins(0, 0, 0, 0)
    root.layout().addWidget(page)
    root.resize(1900, 1000)
    root.show()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    tables = report_tables(page)
    assert tables["config"].rowCount() == 17 and tables["summary"].rowCount() >= 3
    assert tables["eye"].rowCount() == 10
    for table in tables.values():
        assert_fits(table)


def test_the_report_tables_fit_after_the_detailed_view_and_back(qapp, tmp_path):
    page = ReportPage()
    root = themed_root()
    root.layout().addWidget(page)
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    show(root)
    page.toggle_button.click()  # View Details
    page.toggle_button.click()  # View Summary
    QCoreApplication.processEvents()
    for table in report_tables(page).values():
        assert_fits(table)


# -- the columns may change (the report's layouts differ, SPEC-input-selection-and-follow.md 4.5) ----------


def test_set_header_swaps_the_columns_and_the_table_still_fits(qapp):
    root = themed_root()
    table = FitTable(["", "% (N)", "Time"], stretch_column=0)
    root.layout().addWidget(table)
    table.set_rows(ROWS)
    show(root)
    table.set_header(["Metric", "Value"], stretch_column=1)
    table.set_rows([["Time on target", "60 %"], ["Followed", "2 of 3"], ["Valid pointer", "100 %"]])
    show(root)
    assert table.columnCount() == 2
    assert [table.horizontalHeaderItem(c).text() for c in range(2)] == ["Metric", "Value"]
    head = table.horizontalHeader()
    assert head.sectionResizeMode(1) == head.ResizeMode.Stretch and head.sectionResizeMode(0) != head.ResizeMode.Stretch
    assert table.texts()[0] == ["Time on target", "60 %"] and table.rowCount() == 3
    assert_fits(table)
    table.set_header(["", "a", "b", "c", "d"], stretch_column=0)  # and back to more columns
    table.set_rows([["x", "1", "2", "3", "4"]])
    show(root)
    assert table.columnCount() == 5 and head.sectionResizeMode(0) == head.ResizeMode.Stretch
    assert_fits(table)


def test_a_follow_reports_summary_table_fits_on_the_page(qapp, tmp_path):
    from src.data.report_cache import build_report
    from tests.follow_fixtures import folder

    page = ReportPage()
    root = themed_root()
    root.layout().addWidget(page)
    page.set_report(build_report(folder(tmp_path)), test_name="Follow 1")
    show(root)
    assert page.summary.table.rowCount() == 7
    assert_fits(page.summary.table)
    for table in report_tables(page).values():
        assert_fits(table)
