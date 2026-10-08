"""SPEC-input-selection-and-follow.md 4.5, A8 (Switch half): a test selected by the switch shows
the Clicks and Click errors columns in the Summary of Results, the Trial-by-Trial table (page
and PDF) and the report.json rows; a Dwell test does not. Offscreen Qt; nothing measures a size."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QTextDocument, QTextTable
from PySide6.QtWidgets import QApplication

from src.ui.report_format import (
    CLICK_COLUMNS,
    DASH,
    SUMMARY_COLUMNS,
    SWITCH_SUMMARY_COLUMNS,
    SWITCH_TRIAL_COLUMNS,
    TRIAL_COLUMNS,
    summary_footnote,
    summary_table,
)
from src.ui.report_layout import (
    SELECTION,
    SWITCH,
    definition_lines,
    layout_kind,
    trial_columns,
    trial_rows,
)
from src.ui.report_page import ReportPage
from src.ui.report_pdf import build_report_html
from tests.report_ui_fixtures import SWITCH_META, SWITCH_PRESSES, folder_report

CLICKS, ERRORS = 7, 8  # the columns right after Entries


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def switch_report(tmp_path, **kw):
    return folder_report(tmp_path, presses=SWITCH_PRESSES, **SWITCH_META, **kw)


def make_page(report) -> ReportPage:
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    page.show()
    QCoreApplication.processEvents()
    return page


def html_table(html: str, columns: int) -> tuple[QTextDocument, QTextTable]:
    doc = QTextDocument()
    doc.setHtml(html)
    found: list[QTextTable] = []

    def walk(frame):
        for child in frame.childFrames():
            if isinstance(child, QTextTable):
                found.append(child)
            walk(child)

    walk(doc.rootFrame())
    return doc, next(t for t in found if t.columns() == columns)


# -- report.json ----------------------------------------------------------------------------------


def test_the_report_rows_carry_the_presses_of_every_trial_and_their_means(tmp_path):
    report = switch_report(tmp_path)
    assert [t["clicks"] for t in report["trials"]] == [1, 4, 3, None, 1, 1]
    assert [t["click_errors"] for t in report["trials"]] == [0, 3, 2, None, 0, 0]  # skipped: none
    rows = {r["key"]: r for r in report["summary"]["rows"]}
    assert (rows["error_free"]["clicks"], rows["error_free"]["click_errors"]) == (1.0, 0.0)
    assert (rows["all_selected"]["clicks"], rows["all_selected"]["click_errors"]) == (1.5, 0.5)
    assert (rows["not_selected"]["clicks"], rows["not_selected"]["click_errors"]) == (4.0, 3.0)
    assert (rows["all_trials"]["clicks"], rows["all_trials"]["click_errors"]) == (2.0, 1.0)
    assert report["session"]["selection"] == "switch"


def test_an_old_folder_without_the_columns_has_no_presses_not_zeros(tmp_path):
    report = folder_report(tmp_path, legacy=True)
    assert all(t["clicks"] is None and t["click_errors"] is None for t in report["trials"])
    assert all(r["clicks"] is None and r["click_errors"] is None for r in report["summary"]["rows"])


def test_the_configuration_rows_name_the_switch(tmp_path):
    rows = dict(switch_report(tmp_path)["config"]["rows"])
    assert rows["Input"] == "Gaze (GP3HD, 150 Hz), Switch"
    assert rows["Selection"] == "Switch press (mouse/switch button), refractory 0.5 s"


# -- the layout -----------------------------------------------------------------------------------------


def test_only_a_switch_test_has_the_click_columns(tmp_path):
    switch, dwell = switch_report(tmp_path / "a"), folder_report(tmp_path / "b")
    assert (layout_kind(switch), layout_kind(dwell)) == (SWITCH, SELECTION)
    assert trial_columns(switch) == SWITCH_TRIAL_COLUMNS and len(SWITCH_TRIAL_COLUMNS) == 15
    assert trial_columns(dwell) == TRIAL_COLUMNS and len(TRIAL_COLUMNS) == 13
    assert SWITCH_TRIAL_COLUMNS[CLICKS : ERRORS + 1] == CLICK_COLUMNS == ("Clicks", "Click errors")
    assert SWITCH_TRIAL_COLUMNS[CLICKS - 1] == "Entries"  # right after Entries
    assert SWITCH_SUMMARY_COLUMNS == (*SUMMARY_COLUMNS, *CLICK_COLUMNS)
    assert not any(c in trial_columns(dwell) for c in CLICK_COLUMNS)


def test_the_summary_rows_show_the_means_of_the_presses(tmp_path):
    rows = summary_table(switch_report(tmp_path))
    assert all(len(row) == len(SWITCH_SUMMARY_COLUMNS) == 7 for row in rows)
    assert [row[5:] for row in rows] == [["1.0", "0.0"], ["1.5", "0.5"], ["4.0", "3.0"], ["2.0", "1.0"]]
    assert all(len(row) == 5 for row in summary_table(folder_report(tmp_path / "dwell")))


def test_the_trial_cells_have_the_presses_in_place_and_a_skipped_trial_has_dashes(tmp_path):
    report = switch_report(tmp_path)
    rows = trial_rows(report)
    assert all(len(cells) == 15 for cells in rows)
    assert [(cells[CLICKS].text, cells[ERRORS].text) for cells in rows] == [
        ("1", "0"), ("4", "3"), ("3", "2"), (DASH, DASH), ("1", "0"), ("1", "0"),
    ]
    assert rows[1][CLICKS].key == 4.0 and rows[3][CLICKS].key is None  # sorts by the number, dashes last
    assert rows[1][6].text == "0"  # Entries is where it was: the timeout never entered
    assert rows[0][ERRORS + 1].text == str(report["trials"][0]["fixations"]["count"])  # Fixations follow


def test_the_footnote_explains_the_presses_in_seconds_and_a_dwell_test_has_none(tmp_path):
    note = summary_footnote(switch_report(tmp_path / "a"))
    assert "Clicks = switch presses counted in the trial (presses between trials are ignored)" in note
    assert "Click errors = presses with the gaze off the target, or with no valid gaze in the last 0.15 s" in note
    assert "ms" not in note.replace("Reaction Time = onset to the first gaze entry", "")
    assert "Clicks" not in summary_footnote(folder_report(tmp_path / "b"))


def test_the_definitions_of_a_switch_report_name_both_columns(tmp_path):
    lines = definition_lines(switch_report(tmp_path / "a"))
    assert any(line.startswith("Clicks:") for line in lines)
    assert any(line.startswith("Click errors:") and "0.15 s" in line for line in lines)
    assert not any(line.startswith("Click") for line in definition_lines(folder_report(tmp_path / "b")))


# -- the page -----------------------------------------------------------------------------------------------


def test_the_page_shows_the_click_columns_in_both_views(qapp, tmp_path):
    page = make_page(switch_report(tmp_path))
    summary = page.summary.table
    assert [summary.horizontalHeaderItem(c).text() for c in range(summary.columnCount())] == list(
        SWITCH_SUMMARY_COLUMNS
    )
    assert summary.texts()[0][5:] == ["1.0", "0.0"] and summary.texts()[3][5:] == ["2.0", "1.0"]
    assert "Clicks = switch presses" in page.summary.note.text()
    detailed = page.detailed.table
    assert [detailed.horizontalHeaderItem(c).text() for c in range(detailed.columnCount())] == list(
        SWITCH_TRIAL_COLUMNS
    )
    assert [detailed.item(r, CLICKS).text() for r in range(detailed.rowCount())] == [
        "1", "4", "3", DASH, "1", "1",
    ]
    assert [detailed.item(r, ERRORS).text() for r in range(detailed.rowCount())] == [
        "0", "3", "2", DASH, "0", "0",
    ]


def test_the_click_columns_sort_and_keep_the_selected_trial(qapp, tmp_path):
    page = make_page(switch_report(tmp_path))
    table = page.detailed.table
    table.sortRequested.emit(CLICKS)  # ascending, the skipped trial's dash last
    assert [table.item(r, CLICKS).text() for r in range(table.rowCount())] == ["1", "1", "1", "3", "4", DASH]
    table.sortRequested.emit(CLICKS)  # descending, the dash still last
    assert [table.item(r, CLICKS).text() for r in range(table.rowCount())] == ["4", "3", "1", "1", "1", DASH]
    assert page.selected_trial() == 0  # the first trial stayed selected wherever it moved


def test_a_page_that_shows_a_switch_report_then_a_dwell_one_drops_the_columns(qapp, tmp_path):
    page = make_page(switch_report(tmp_path / "a"))
    assert page.detailed.table.columnCount() == 15 and page.summary.table.columnCount() == 7
    page.set_report(folder_report(tmp_path / "b"), test_name="Grid Click 2")
    assert page.detailed.table.columnCount() == 13 and page.summary.table.columnCount() == 5
    assert page.detailed.table.horizontalHeaderItem(6).text() == "Entries"
    assert page.detailed.table.horizontalHeaderItem(7).text() == "Fixations"
    hidden = [page.detailed.table.frozen_view.isColumnHidden(c) for c in range(13)]
    assert hidden == [False] + [True] * 12  # only the first column is frozen
    assert "Clicks" not in page.summary.note.text()
    page.set_report(switch_report(tmp_path / "c"), test_name="Grid Click 3")
    hidden = [page.detailed.table.frozen_view.isColumnHidden(c) for c in range(15)]
    assert hidden == [False] + [True] * 14


# -- the PDF -------------------------------------------------------------------------------------------------


def test_the_pdf_prints_the_click_columns_and_their_definitions(qapp, tmp_path):
    report = switch_report(tmp_path)
    html = build_report_html(report, test_name="Grid Click 1", evaluator="", notes="", map_image=None)
    doc, table = html_table(html, 15)
    header = [table.cellAt(0, c).firstCursorPosition().block().text() for c in range(15)]
    assert header == list(SWITCH_TRIAL_COLUMNS)
    for r, cells in enumerate(trial_rows(report), start=1):
        printed = [table.cellAt(r, c).firstCursorPosition().block().text() for c in range(15)]
        assert printed == [cell.text for cell in cells]
    _doc, summary = html_table(html, 7)
    assert summary.cellAt(0, 5).firstCursorPosition().block().text() == "Clicks"
    assert summary.cellAt(4, 6).firstCursorPosition().block().text() == "1.0"  # All Trials, Click errors
    assert "Click errors:" in html and "Clicks = switch presses" in html


def test_a_dwell_pdf_has_no_click_text(qapp, tmp_path):
    html = build_report_html(folder_report(tmp_path), test_name="T", evaluator="", notes="", map_image=None)
    assert "Clicks" not in html and "Click errors" not in html
    html_table(html, 13)  # the usual trial table is the one printed
