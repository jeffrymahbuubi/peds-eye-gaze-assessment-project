"""SPEC-input-selection-and-follow.md A5, A8: a test with no gaze recorded (a Mouse test with no
tracker) says "not recorded" in every eye cell of the trial table, on the page and in the PDF, on
the Scanpath and Heat map switches and under the selected trial's map; an older folder that says
nothing keeps its dashes. Offscreen Qt."""

from __future__ import annotations

import copy
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from src.ui.report_format import (
    DASH,
    NOT_RECORDED,
    SWITCH_TRIAL_COLUMNS,
    TRIAL_COLUMNS,
    gaze_was_recorded,
    trial_cells,
    trial_line,
)
from src.ui.report_layout import trial_rows
from src.ui.report_page import ReportPage
from src.ui.report_pdf import build_report_html
from tests.report_ui_fixtures import SWITCH_META, SWITCH_PRESSES, folder_report

EYE_COLUMNS = ("Fixations", "Mean fix. dur. (s)", "Saccades", "Mean peak vel. (deg/s)", "Pupil (mm)", "Pupil change (mm)")
SKIPPED = 3  # the fourth trial of the fixture is skipped


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def no_gaze(report):
    report = copy.deepcopy(report)
    report["session"]["gaze_recorded"] = False
    return report


def eye_indexes(columns) -> list[int]:
    return [i for i, name in enumerate(columns) if name in EYE_COLUMNS]


# -- the cells ----------------------------------------------------------------------------------------------


def test_only_an_explicit_false_means_no_gaze_was_recorded():
    assert [gaze_was_recorded({"session": {"gaze_recorded": v}}) for v in (False, True, None)] == [False, True, True]
    assert gaze_was_recorded({}) is True


def test_every_eye_cell_of_a_presented_trial_says_not_recorded(tmp_path):
    report = no_gaze(folder_report(tmp_path))
    eye = eye_indexes(TRIAL_COLUMNS)
    assert len(eye) == 6
    for number, cells in enumerate(trial_rows(report)):
        if number == SKIPPED:
            continue
        assert [cells[i].text for i in eye] == [NOT_RECORDED] * 6
        assert all(cells[i].key is None for i in eye)  # not recorded sorts last, like a dash
        others = [c.text for i, c in enumerate(cells) if i not in eye]
        assert NOT_RECORDED not in others  # the trial's own figures are still there


def test_a_skipped_trial_keeps_its_dashes_nothing_was_presented(tmp_path):
    cells = trial_rows(no_gaze(folder_report(tmp_path)))[SKIPPED]
    assert [cells[i].text for i in eye_indexes(TRIAL_COLUMNS)] == [DASH] * 6
    assert cells[3].text == "Skipped"


def test_a_switch_test_shifts_the_eye_cells_right_by_the_two_click_columns(tmp_path):
    report = no_gaze(folder_report(tmp_path, presses=SWITCH_PRESSES, **SWITCH_META))
    eye = eye_indexes(SWITCH_TRIAL_COLUMNS)
    assert eye == list(range(9, 15))
    cells = trial_rows(report)[1]
    assert [cells[i].text for i in eye] == [NOT_RECORDED] * 6
    assert [cells[7].text, cells[8].text] == ["4", "3"]  # the presses are not an eye figure


def test_a_report_that_says_nothing_keeps_its_dashes(tmp_path):
    report = folder_report(tmp_path, legacy=True)
    assert report["session"]["gaze_recorded"] is None
    cells = trial_rows(report)[0]
    assert [c.text for c in cells[9:]] == [DASH] * 4  # saccades and pupil: no all_gaze.csv in that folder
    assert NOT_RECORDED not in [c.text for c in cells]


def test_a_run_with_gaze_is_unchanged(tmp_path):
    report = folder_report(tmp_path)
    assert [c.text for c in trial_rows(report)[0]] == [c.text for c in trial_cells(report["trials"][0])]
    assert NOT_RECORDED not in [c.text for cells in trial_rows(report) for c in cells]


def test_the_line_under_the_map_says_the_eye_data_was_not_recorded(tmp_path):
    report = folder_report(tmp_path)
    assert trial_line(report["trials"][0], gaze_recorded=False) == "Eye data not recorded."
    assert trial_line(report["trials"][0]).startswith("Scan path")


# -- the page ----------------------------------------------------------------------------------------------------


def make_page(report) -> ReportPage:
    page = ReportPage()
    page.set_report(report, test_name="Mouse 1")
    page.show()
    QCoreApplication.processEvents()
    return page


def test_the_page_shows_not_recorded_in_the_table_the_line_and_the_switches(tmp_path):
    page = make_page(no_gaze(folder_report(tmp_path)))
    table = page.detailed.table
    eye = eye_indexes(TRIAL_COLUMNS)
    assert [table.item(0, i).text() for i in eye] == [NOT_RECORDED] * 6
    assert [table.item(SKIPPED, i).text() for i in eye] == [DASH] * 6
    assert page.detailed.line_label.text() == "Eye data not recorded."
    summary = page.summary
    assert summary.targets_check.isEnabled()
    for check, label in ((summary.path_check, "Scanpath"), (summary.heat_check, "Heat map")):
        assert not check.isEnabled() and not check.isChecked() and check.text() == f"{label} (not recorded)"
    summary.targets_check.setChecked(False)  # the other switch still works
    assert summary.map.overlays() == {"targets": False, "path": False, "heat": False}


def test_a_page_goes_back_to_normal_for_the_next_report_with_gaze(tmp_path):
    page = make_page(no_gaze(folder_report(tmp_path / "a")))
    page.set_report(folder_report(tmp_path / "b"), test_name="Grid Click 2")
    assert page.summary.path_check.isEnabled() and page.summary.path_check.text() == "Scanpath"
    assert page.summary.heat_check.isEnabled() and page.summary.heat_check.text() == "Heat map"
    assert NOT_RECORDED not in [page.detailed.table.item(0, c).text() for c in range(13)]
    assert page.detailed.line_label.text().startswith("Scan path")


# -- the PDF -------------------------------------------------------------------------------------------------------


def test_the_pdf_prints_not_recorded_in_the_same_cells(tmp_path):
    report = no_gaze(folder_report(tmp_path))
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=None)
    presented = len(report["trials"]) - 1
    assert html.count(f">{NOT_RECORDED}<") >= 6 * presented + 10  # six per trial and the ten Eye Metrics
    with_gaze = build_report_html(folder_report(tmp_path / "gaze"), test_name="T", evaluator="", notes="", map_image=None)
    assert NOT_RECORDED not in with_gaze
