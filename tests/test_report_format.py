"""The text of the per-test report (SPEC-compass-task-flow.md 4D.2, 4D.8; AD4, AD10):
what the page and the PDF print for each figure. Qt-free."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.ui.report_format import (
    DASH,
    DEFAULT_HIT_TOLERANCE_PX,
    SUMMARY_COLUMNS,
    TRIAL_COLUMNS,
    banner_lines,
    eye_rows,
    hit_tolerance_px,
    num,
    pdf_default_name,
    percent_text,
    started_text,
    summary_footnote,
    summary_table,
    trial_cells,
    trial_line,
)
from tests.report_fixtures import T0
from tests.report_ui_fixtures import folder_report

# -- numbers ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "digits", "signed", "text"),
    [
        (1.234, 2, False, "1.23"),
        (0, 1, False, "0.0"),
        (0.04, 2, True, "+0.04"),
        (-0.034, 2, True, "-0.03"),
        (None, 1, False, DASH),
        (True, 1, False, DASH),
        ("x", 1, False, DASH),
    ],
)
def test_num_rounds_and_dashes(value, digits, signed, text):
    assert num(value, digits, signed=signed) == text


@pytest.mark.parametrize(
    ("n", "total", "text"),
    [(11, 18, "61% (11/18)"), (16, 18, "89% (16/18)"), (2, 18, "11% (2/18)"), (0, 7, "0% (0/7)"),
     (0, 0, "0% (0/0)"), (3, 6, "50% (3/6)"), (None, 5, DASH)],
)
def test_percent_text_is_a_whole_percent_with_the_counts(n, total, text):
    assert percent_text({"n": n, "N": total}) == text


# -- Summary of Results and Eye Metrics (the AD4 rows as shown) -------------------------


def test_the_summary_table_shows_the_four_u10_rows_in_order(tmp_path):
    report = folder_report(tmp_path)
    rows = summary_table(report)
    assert [r[0] for r in rows] == [
        "Error-free Target Selections", "All Targets Selected", "Targets Not Selected", "All Trials",
    ]
    assert len(SUMMARY_COLUMNS) == 5 and all(len(r) == 5 for r in rows)
    # 4 hits and 1 timeout scored (the skipped trial is excluded from N), 3 of the hits on the
    # first entry.
    assert rows[0][1] == "60% (3/5)"
    assert rows[1][1] == "80% (4/5)"
    assert rows[2][1] == "20% (1/5)"
    assert rows[3][1] == "100% (5/5)"
    assert rows[1][2] == "1.12" and rows[1][4] == "1.2"  # trial time (s), mean entries


def test_the_eye_metrics_table_has_the_ten_wireframe_rows(tmp_path):
    rows = eye_rows(folder_report(tmp_path))
    assert [label for label, _ in rows] == [
        "Fixations", "Mean fixation duration", "Saccades", "Mean saccade amplitude",
        "Mean peak saccade velocity", "Scan-path length per trial", "Mean pupil diameter",
        "Mean pupil change from baseline", "Valid gaze during trials", "Calibration error",
    ]
    values = dict(rows)
    assert values["Valid gaze during trials"] == "100 %"
    assert values["Mean pupil diameter"] == "3.50 mm"
    assert values["Mean pupil change from baseline"] == "+0.00 mm (+0.0 %)"
    assert values["Saccades"] == "0" and values["Mean saccade amplitude"] == DASH  # none found: no mean
    assert values["Calibration error"].endswith("(21 px), measured")
    assert "per trial" in values["Fixations"]


def test_eye_metrics_of_a_legacy_folder_are_dashes_not_zeros(tmp_path):
    values = dict(eye_rows(folder_report(tmp_path, legacy=True)))
    for label in ("Saccades", "Mean saccade amplitude", "Mean peak saccade velocity",
                  "Scan-path length per trial", "Mean pupil diameter",
                  "Mean pupil change from baseline"):
        assert values[label] == DASH, label
    assert values["Fixations"] != DASH  # gaze_stream.csv is all it needs


def test_a_report_with_no_summary_block_gives_empty_tables_not_an_error():
    assert summary_table({}) == []
    assert all(value == DASH for _, value in eye_rows({}))


# -- Trial-by-Trial rows -----------------------------------------------------------------


def test_a_trial_row_has_the_thirteen_columns_in_order(tmp_path):
    report = folder_report(tmp_path)
    cells = trial_cells(report["trials"][0])
    assert len(cells) == len(TRIAL_COLUMNS) == 13
    assert cells[0].text == "1" and cells[3].text == "Hit"
    assert cells[4].text == "1.00" and cells[5].text == "0.30" and cells[6].text == "1"
    assert cells[2].text == DASH  # no distance before the first trial


def test_outcomes_read_as_hit_not_selected_skipped(tmp_path):
    report = folder_report(tmp_path)
    assert [trial_cells(t)[3].text for t in report["trials"]] == [
        "Hit", "Not selected", "Hit", "Skipped", "Hit", "Hit",
    ]


def test_a_skipped_row_has_dashes_for_every_metric(tmp_path):
    cells = trial_cells(folder_report(tmp_path)["trials"][3])
    assert [c.text for c in cells[4:]] == [DASH] * 9
    assert all(c.key is None for c in cells[4:])  # nothing to sort by: always last


def test_the_sort_key_of_a_number_is_the_number_and_of_a_dash_is_none(tmp_path):
    cells = trial_cells(folder_report(tmp_path)["trials"][1])  # timeout, no reaction time
    assert cells[0].key == 2.0
    assert cells[5].text == DASH and cells[5].key is None
    assert cells[3].key == "Not selected"


def test_the_line_under_the_selected_trial_map(tmp_path):
    trial = {"saccades": {"scanpath_deg": 12.34, "count": 6}, "fixations": {"count": 7}}
    assert trial_line(trial) == "Scan path 12.3 deg · 7 fixations · 6 saccades"
    one = {"saccades": {"scanpath_deg": 0.0, "count": 1}, "fixations": {"count": 1}}
    assert trial_line(one) == "Scan path 0.0 deg · 1 fixation · 1 saccade"
    none = {"saccades": {"scanpath_deg": None, "count": None}, "fixations": {"count": None}}
    assert trial_line(none) == "Scan path — · — fixations · — saccades"


# -- banner, footnote, date, file name ---------------------------------------------------


def test_the_banner_says_ended_early_with_the_counts(tmp_path):
    lines = banner_lines(folder_report(tmp_path, planned=18))
    assert lines == ["Ended early — 6 of 18 trials"]


def test_the_banner_says_the_gaze_data_is_low_quality():
    report = {"quality": {"valid_share": 0.72,
                          "warnings": [{"code": "low_valid_gaze", "text": "Valid gaze 72% is below the 80% floor"}]}}
    assert banner_lines(report) == ["Gaze data is low quality: 72 % valid"]


def test_the_banner_warns_about_a_resized_canvas(tmp_path):
    lines = banner_lines(folder_report(tmp_path, events=[{"kind": "CANVAS_RESIZED"}]))
    assert len(lines) == 1 and "resized" in lines[0]


def test_a_complete_run_has_no_banner(tmp_path):
    assert banner_lines(folder_report(tmp_path)) == []


def test_the_footnote_counts_skipped_and_not_presented_trials(tmp_path):
    note = summary_footnote(folder_report(tmp_path, planned=18))
    assert "1 skipped trial(s) excluded." in note
    assert "12 planned trial(s) not presented." in note
    assert "Target area = drawn target + 40 px tolerance ring." in note
    assert "Reaction Time = onset to the first gaze entry" in note
    assert "planned" not in summary_footnote(folder_report(tmp_path / "b"))


def test_the_hit_tolerance_is_forty_pixels_unless_the_report_says_otherwise():
    assert hit_tolerance_px({}) == DEFAULT_HIT_TOLERANCE_PX == 40.0
    assert hit_tolerance_px({"map": {"hit_tolerance_px": 25}}) == 25.0
    assert hit_tolerance_px({"map": {"hit_tolerance_px": "x"}}) == 40.0
    assert hit_tolerance_px({"map": {"hit_tolerance_px": -3}}) == 40.0
    assert "60 px tolerance ring" in summary_footnote({"map": {"hit_tolerance_px": 60}})


def test_the_test_date_is_local_time_in_the_wireframes_form():
    ns = int(datetime(2026, 10, 6, 14, 6).timestamp() * 1e9)
    assert started_text(ns) == "Oct 6, 2026 2:06 PM"
    assert started_text(int(datetime(2026, 1, 2, 0, 5).timestamp() * 1e9)) == "Jan 2, 2026 12:05 AM"
    assert started_text(int(datetime(2026, 1, 2, 12, 0).timestamp() * 1e9)) == "Jan 2, 2026 12:00 PM"
    assert started_text(None) == DASH and started_text("x") == DASH


def test_the_pdf_file_name_is_the_tests_date_then_the_test_name_and_no_subject():
    ns = int(datetime(2026, 10, 6, 14, 6).timestamp() * 1e9)
    assert pdf_default_name("Grid Click 1", ns) == "2026-10-06_Grid Click 1.pdf"
    # Characters a file name cannot hold are replaced, so the path is always valid.
    name = pdf_default_name('a:b*c?"d', ns)
    assert name.startswith("2026-10-06_") and name.endswith(".pdf")
    assert not any(ch in name for ch in '/\\:*?"<>|')
    assert pdf_default_name("", None) == "undated_report.pdf"


def test_the_pdf_name_part_is_cut_at_50_characters_hash_included():
    ns = int(datetime(2026, 10, 6, 14, 6).timestamp() * 1e9)
    exact = "n" * 50
    assert pdf_default_name(exact, ns) == f"2026-10-06_{exact}.pdf"  # fits: untouched
    long = pdf_default_name("n" * 60, ns)  # a test name can have 60 characters
    part = long.removeprefix("2026-10-06_").removesuffix(".pdf")
    assert len(part) == 50 and part.startswith("n" * 43 + "~")
    assert pdf_default_name("n" * 60, ns) == long  # stable
    assert pdf_default_name("n" * 59 + "m", ns) != long  # and two long names stay apart
    illegal = pdf_default_name("x" * 46 + "/", ns).removeprefix("2026-10-06_").removesuffix(".pdf")
    assert len(illegal) <= 50


def test_the_date_of_a_run_uses_started_ns_not_today():
    assert pdf_default_name("T", T0).startswith(f"{datetime.fromtimestamp(T0 / 1e9):%Y-%m-%d}_")
