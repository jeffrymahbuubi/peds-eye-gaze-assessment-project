"""The per-test report page (SPEC-compass-task-flow.md 4D.2, 4D.3, 4D.7; G12, AD10,
AD11, AD14; wireframes ``report-summary.md`` / ``report-detailed.md``). Offscreen Qt;
nothing measures a size (no fonts offscreen) and no modal dialog is opened (the PDF
path chooser is replaced)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.ui.design_tokens import TEXT_SECONDARY
from src.ui.report_format import DASH, TRIAL_COLUMNS
from src.ui.report_page import DETAILED, SUMMARY, ReportPage
from tests.report_ui_fixtures import folder_report

OUTCOME_COLUMN, REACTION_COLUMN, ENTRIES_COLUMN = 3, 5, 6


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_page(tmp_path, *, legacy=False, planned=6, events=None, **kw) -> ReportPage:
    page = ReportPage()
    report = folder_report(tmp_path, legacy=legacy, planned=planned, events=events)
    page.set_report(report, test_name=kw.pop("test_name", "Grid Click 1"), **kw)
    page.show()
    QCoreApplication.processEvents()
    return page


def column(page: ReportPage, c: int) -> list[str]:
    table = page.detailed.table
    return [table.item(r, c).text() for r in range(table.rowCount())]


def shown_trials(page: ReportPage) -> list[str]:
    return column(page, 0)


# -- G12: it populates from a report and toggles --------------------------------------------


def test_the_page_opens_on_the_summary_with_the_header_filled(qapp, tmp_path):
    page = make_page(tmp_path, evaluator="Dr. Lin", notes="Good attention")
    assert page.view_mode == SUMMARY
    assert page.title_label.text() == "Summary Results"
    assert page.name_edit.text() == "Grid Click 1"
    assert page.evaluator_edit.text() == "Dr. Lin"
    assert page.notes_edit.toPlainText() == "Good attention"
    assert "P001" in page.subject_label.text()
    assert page.date_label.text().startswith("Test Date: ") and DASH not in page.date_label.text()
    assert page._stack.currentIndex() == 0 and page.toggle_button.text() == "View Details"
    assert page.save_button.isEnabled() and not page.banner.isVisible()


def test_the_name_defaults_to_the_one_the_run_recorded(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path))
    assert page.name_edit.text() == "Grid Click 1"  # metadata.test_name
    page.set_report(folder_report(tmp_path / "b"), test_name="Renamed since")
    assert page.name_edit.text() == "Renamed since"


def test_the_subject_can_be_given_by_the_host(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), subject="TESTING")
    assert "TESTING" in page.subject_label.text() and "P001" not in page.subject_label.text()


def test_the_left_column_has_the_seventeen_configuration_rows_and_the_name(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.config_table.rowCount() == 17 and page.config_table.columnCount() == 2
    assert page.config_table.cell_text(0, 0) == "Configuration name"
    assert page.config_table.cell_text(1, 0) == "Task" and page.config_table.cell_text(1, 1) == "Grid Click"
    assert "Standard" in page.config_name_label.text()
    assert [page.config_table.horizontalHeaderItem(c).text() for c in range(2)] == ["Setting", "Value"]


def test_the_summary_has_the_description_the_four_rows_and_the_footnote(qapp, tmp_path):
    page = make_page(tmp_path)
    assert "One cell of a visible board" in page.summary.task_label.text()
    rows = page.summary.table.texts()
    assert [r[0] for r in rows] == [
        "Error-free Target Selections", "All Targets Selected", "Targets Not Selected", "All Trials",
    ]
    assert rows[0][1] == "60% (3/5)"
    assert "1 skipped trial(s) excluded." in page.summary.note.text()
    assert [page.summary.table.horizontalHeaderItem(c).text() for c in range(5)] == [
        "", "% (N)", "Trial Time (s)", "Reaction Time (s)", "Entries",
    ]


def test_the_summary_has_ten_eye_metric_rows(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.summary.eye_table.rowCount() == 10
    assert page.summary.eye_table.cell_text(0, 0) == "Fixations"
    assert page.summary.eye_table.cell_text(8, 0) == "Valid gaze during trials"
    assert page.summary.eye_table.cell_text(8, 1) == "100 %"


def test_view_details_and_view_summary_toggle_the_view(qapp, tmp_path):
    page = make_page(tmp_path)
    page.toggle_button.click()
    assert page.view_mode == DETAILED
    assert page.title_label.text() == "Detailed Results" and page.toggle_button.text() == "View Summary"
    assert page._stack.currentIndex() == 1
    page.toggle_button.click()
    assert page.view_mode == SUMMARY and page._stack.currentIndex() == 0
    assert page.title_label.text() == "Summary Results" and page.toggle_button.text() == "View Details"
    page.show_detailed()
    assert page.view_mode == DETAILED
    page.show_summary()
    assert page.view_mode == SUMMARY


def test_the_header_left_column_and_footer_are_the_same_in_both_views(qapp, tmp_path):
    page = make_page(tmp_path)
    page.show_detailed()
    for widget in (page.name_edit, page.evaluator_edit, page.config_table, page.notes_edit,
                   page.print_button, page.toggle_button, page.save_button, page.cancel_button):
        assert widget.isVisibleTo(page)
    assert [b.text() for b in (page.print_button, page.toggle_button, page.save_button, page.cancel_button)] == [
        "Print Report", "View Summary", "Save && Continue", "Cancel",  # "&&" shows as one "&"
    ]


# -- the Detailed table ---------------------------------------------------------------------------


def test_the_trial_table_has_the_wireframe_columns_and_a_row_per_trial(qapp, tmp_path):
    page = make_page(tmp_path)
    table = page.detailed.table
    shown = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    assert [label.replace("\n", " ") for label in shown] == list(TRIAL_COLUMNS)  # two-line headers (H7)
    assert table.rowCount() == 6 and shown_trials(page) == ["1", "2", "3", "4", "5", "6"]
    assert column(page, OUTCOME_COLUMN) == ["Hit", "Not selected", "Hit", "Skipped", "Hit", "Hit"]


def test_the_first_row_is_selected_when_the_page_opens_and_the_pane_shows_it(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.detailed.table.currentRow() == 0 and page.selected_trial() == 0
    assert page.detailed.map.trial() == 0
    assert page.detailed.selected_title.text() == "Selected trial: Trial 1"
    assert page.detailed.line_label.text().startswith("Scan path ")


def test_selecting_a_row_updates_the_selected_trial_pane(qapp, tmp_path):
    page = make_page(tmp_path)
    page.show_detailed()
    page.detailed.table.setCurrentCell(2, 0)
    assert page.selected_trial() == 2 and page.detailed.map.trial() == 2
    assert page.detailed.selected_title.text() == "Selected trial: Trial 3"
    assert "fixation" in page.detailed.line_label.text() and "saccade" in page.detailed.line_label.text()
    page.detailed.table.selectRow(1)
    assert page.detailed.map.trial() == 1 and page.detailed.selected_title.text().endswith("Trial 2")


def test_the_up_and_down_keys_move_the_selection_and_the_map_follows(qapp, tmp_path):
    page = make_page(tmp_path)
    page.show_detailed()
    table = page.detailed.table
    table.setFocus()
    QTest.keyClick(table, Qt.Key.Key_Down)
    assert page.selected_trial() == 1 and page.detailed.map.trial() == 1
    QTest.keyClick(table, Qt.Key.Key_Down)
    QTest.keyClick(table, Qt.Key.Key_Up)
    assert page.selected_trial() == 1
    QTest.keyClick(table, Qt.Key.Key_Up)
    QTest.keyClick(table, Qt.Key.Key_Up)  # at the top: stays
    assert page.selected_trial() == 0 and page.detailed.map.trial() == 0


def test_a_skipped_row_is_grey_with_dashes_and_is_still_selectable(qapp, tmp_path):
    page = make_page(tmp_path)
    table = page.detailed.table
    assert [table.item(3, c).text() for c in range(4, 13)] == [DASH] * 9
    assert table.item(3, 3).foreground().color().name().lower() == TEXT_SECONDARY.lower()
    assert table.item(0, 3).foreground().color().name().lower() != TEXT_SECONDARY.lower()
    table.setCurrentCell(3, 0)
    assert page.detailed.map.trial() == 3  # shows the skipped trial's target as a dashed ring


def test_clicking_a_header_sorts_by_that_column_and_a_second_click_reverses(qapp, tmp_path):
    page = make_page(tmp_path)
    table = page.detailed.table
    table.sortRequested.emit(REACTION_COLUMN)  # what a click on the header emits
    ascending = column(page, REACTION_COLUMN)
    assert ascending == ["0.20", "0.25", "0.30", "0.40", DASH, DASH]  # dashes last
    assert table.horizontalHeader().sortIndicatorSection() == REACTION_COLUMN
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
    table.sortRequested.emit(REACTION_COLUMN)
    assert column(page, REACTION_COLUMN) == ["0.40", "0.30", "0.25", "0.20", DASH, DASH]  # still last
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    table.sortRequested.emit(OUTCOME_COLUMN)  # a new column starts ascending
    assert column(page, OUTCOME_COLUMN) == ["Hit", "Hit", "Hit", "Hit", "Not selected", "Skipped"]
    table.sortRequested.emit(0)
    assert shown_trials(page) == ["1", "2", "3", "4", "5", "6"]


def test_sorting_keeps_the_selected_trial_and_its_pane(qapp, tmp_path):
    page = make_page(tmp_path)
    page.detailed.table.setCurrentCell(2, 0)  # trial 3
    page.detailed.table.sortRequested.emit(REACTION_COLUMN)
    assert page.selected_trial() == 2  # still trial 3 ...
    assert page.detailed.table.item(page.detailed.table.currentRow(), 0).text() == "3"  # ... wherever it moved
    assert page.detailed.map.trial() == 2 and page.detailed.selected_title.text().endswith("Trial 3")


def test_the_trial_cells_are_read_only(qapp, tmp_path):
    page = make_page(tmp_path)
    table = page.detailed.table
    assert table.editTriggers() == table.EditTrigger.NoEditTriggers
    for r in range(table.rowCount()):
        for c in range(table.columnCount()):
            assert not table.item(r, c).flags() & Qt.ItemFlag.ItemIsEditable
    for read_only in (page.config_table, page.summary.table, page.summary.eye_table):
        assert read_only.editTriggers() == read_only.EditTrigger.NoEditTriggers
        assert not read_only.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable


# -- overlays on the Summary's map ---------------------------------------------------------------------


def test_the_map_overlay_switches_start_targets_on_and_drive_the_map(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.summary.targets_check.isChecked() and not page.summary.path_check.isChecked() and not page.summary.heat_check.isChecked()
    assert page.summary.map.overlays() == {"targets": True, "path": False, "heat": False}
    page.summary.path_check.setChecked(True)
    page.summary.heat_check.setChecked(True)
    page.summary.targets_check.setChecked(False)
    assert page.summary.map.overlays() == {"targets": False, "path": True, "heat": True}


def test_the_summary_map_shows_the_whole_test_and_the_pane_map_one_trial(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.summary.map.trial() is None and page.detailed.map.trial() == 0
    for view in (page.summary, page.detailed):  # both fill their column by an explicit size (fit_within)
        assert not view.map.hasHeightForWidth()
        assert view.map.minimumSize() == view.map.maximumSize()
    assert page.summary.map.aspect == pytest.approx(1640 / 957, abs=1e-4)
    assert len(page.summary.map.model.marks) >= 1 and len(page.detailed.map.model.trials) == 6


# -- the banner (AD14) ----------------------------------------------------------------------------------


def test_a_partial_run_shows_ended_early_with_the_counts(qapp, tmp_path):
    page = make_page(tmp_path, planned=18)
    assert page.banner.isVisible()
    assert page.banner_label.text() == "Ended early: 6 of 18 trials"
    assert "12 planned trial(s) not presented." in page.summary.note.text()


def test_a_resized_canvas_shows_the_warning(qapp, tmp_path):
    page = make_page(tmp_path, events=[{"kind": "CANVAS_RESIZED"}])
    assert page.banner.isVisible() and "resized" in page.banner_label.text()


def test_a_complete_run_has_no_banner_and_a_new_report_hides_an_old_one(qapp, tmp_path):
    page = make_page(tmp_path / "a", planned=18)
    assert page.banner.isVisible()
    page.set_report(folder_report(tmp_path / "b"), test_name="Second")
    assert not page.banner.isVisible()


# -- old sessions (AD10) -----------------------------------------------------------------------------------


def test_a_legacy_folder_fills_the_page_with_dashes_and_no_error(qapp, tmp_path):
    page = make_page(tmp_path, legacy=True, test_name="Old test")
    assert page.detailed.table.rowCount() == 6
    # No entries column, no all_gaze.csv, no geometry: those columns are dashes on every row.
    for c, name in ((1, "Size"), (2, "Distance"), (ENTRIES_COLUMN, "Entries"), (9, "Saccades"),
                    (10, "Mean peak vel."), (11, "Pupil"), (12, "Pupil change")):
        assert set(column(page, c)) == {DASH}, name
    assert set(column(page, 7)) != {DASH}  # fixations only need gaze_stream.csv
    assert page.summary.eye_table.cell_text(2, 1) == DASH  # Saccades
    assert page.summary.eye_table.cell_text(6, 1) == DASH  # pupil
    page.show_detailed()
    assert page.selected_trial() == 0 and page.detailed.map.trial() == 0


def test_an_error_free_row_of_a_legacy_folder_is_a_dash_not_a_guess(qapp, tmp_path):
    page = make_page(tmp_path, legacy=True)
    assert page.summary.table.cell_text(0, 1) == DASH
    assert page.summary.table.cell_text(0, 4) == DASH


def test_the_save_button_shows_an_ampersand_not_a_mnemonic(qapp, tmp_path):
    page = make_page(tmp_path)
    assert page.save_button.text() == "Save && Continue"  # displayed as "Save & Continue"
    assert page.save_button.text().replace("&&", "&") == "Save & Continue"
    assert page.save_button.shortcut().isEmpty()


def test_a_run_without_monitor_geometry_says_the_overlays_assume_a_standard_monitor(qapp, tmp_path):
    page = make_page(tmp_path / "old", legacy=True)
    assert page.summary.map_note.isVisibleTo(page)
    assert "assume a standard monitor" in page.summary.map_note.text()
    page.set_report(folder_report(tmp_path / "new"), test_name="T")
    assert not page.summary.map_note.isVisibleTo(page)
