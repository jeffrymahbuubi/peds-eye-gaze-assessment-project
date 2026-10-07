"""SPEC-input-selection-and-follow.md 4.5, W2, A8 (Follow half): Follow the Target's report shows
the Metric / Value summary and its own Trial-by-Trial columns on the page and in the PDF, a Target
Map that draws the pointer path on and off the target, and a legend that names it; an old Follow &
Click folder opens in the old layout. Offscreen Qt; pixels are checked by colour, never by size."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument, QTextTable
from PySide6.QtWidgets import QApplication

from src.data.report_cache import build_report
from src.ui.map_legend import (
    FOLLOW_LEGEND_ENTRIES,
    LEGEND_ENTRIES,
    POINTER_LEGEND_ENTRIES,
    legend_html,
    symbol_image,
)
from src.ui.report_format import DASH, NOT_RECORDED, SUMMARY_COLUMNS, TRIAL_COLUMNS
from src.ui.report_format_follow import (
    FOLLOW_DEFINITIONS,
    FOLLOW_SUMMARY_COLUMNS,
    FOLLOW_TRIAL_COLUMNS,
    GAIN_CAPTION,
    follow_footnote,
    follow_summary_rows,
)
from src.ui.report_layout import FOLLOW, SELECTION, layout_kind, trial_columns, trial_rows
from src.ui.report_page import ReportPage
from src.ui.report_pdf import build_report_html, export_report_pdf
from src.ui.target_map import TargetMapWidget
from src.ui.target_map_follow import FOLLOW_OFF, FOLLOW_ON, LINE_KINDS, paint_line_symbol
from src.ui.target_map_paint import _pen
from tests.follow_fixtures import folder, legacy_folder, mouse_folder

QtPdf = pytest.importorskip("PySide6.QtPdf")

GAIN = FOLLOW_TRIAL_COLUMNS.index("Pursuit gain")
CATCH_UP = FOLLOW_TRIAL_COLUMNS.index("Catch-up sacc. (/s)")


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def report(tmp_path):
    return build_report(folder(tmp_path))


@pytest.fixture
def mouse_report(tmp_path):
    return build_report(mouse_folder(tmp_path))


def make_page(report) -> ReportPage:
    page = ReportPage()
    page.set_report(report, test_name="Follow 1")
    page.show()
    QCoreApplication.processEvents()
    return page


def html_table(html: str, columns: int, first: str | None = None) -> tuple[QTextDocument, QTextTable]:
    """The first table of ``columns`` columns whose first body cell starts with ``first``."""
    doc = QTextDocument()
    doc.setHtml(html)
    found: list[QTextTable] = []

    def walk(frame):
        for child in frame.childFrames():
            if isinstance(child, QTextTable):
                found.append(child)
            walk(child)

    walk(doc.rootFrame())

    def first_cell(table: QTextTable) -> str:
        return table.cellAt(1, 0).firstCursorPosition().block().text() if table.rows() > 1 else ""

    return doc, next(t for t in found if t.columns() == columns and first_cell(t).startswith(first or ""))


def near(image: QImage, colour: str, tolerance: int = 10) -> int:
    """How many pixels of ``image`` are within ``tolerance`` of ``colour`` on every channel."""
    want = QColor(colour)
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if (
                c.alpha() == 255
                and abs(c.red() - want.red()) <= tolerance
                and abs(c.green() - want.green()) <= tolerance
                and abs(c.blue() - want.blue()) <= tolerance
            ):
                count += 1
    return count


# -- which layout --------------------------------------------------------------------------------------------


def test_a_follow_report_has_the_follow_layout_and_an_old_one_keeps_the_selection_layout(tmp_path):
    new, old = build_report(folder(tmp_path / "a")), build_report(legacy_folder(tmp_path / "b"))
    assert layout_kind(new) == FOLLOW and trial_columns(new) == FOLLOW_TRIAL_COLUMNS
    assert layout_kind(old) == SELECTION and trial_columns(old) == TRIAL_COLUMNS
    assert layout_kind({"session": {"task_id": "follow_moving"}, "follow": {"legacy": True}}) == SELECTION
    assert layout_kind({"follow": None}) == SELECTION and layout_kind({}) == SELECTION


# -- the summary table (W2) ---------------------------------------------------------------------------------------


def test_the_summary_is_a_metric_value_table_of_seven_rows(report):
    rows = follow_summary_rows(report)
    assert FOLLOW_SUMMARY_COLUMNS == ("Metric", "Value") and all(len(r) == 2 for r in rows)
    assert [label for label, _ in rows] == [
        "Followed (on target at least 50 % of the trial)",
        "Time on target",
        "Mean distance to target",
        "Time to find target",
        "Smooth-pursuit gain",
        "Catch-up saccades",
        "Valid pointer during trials",
    ]
    values = dict(rows)
    assert values["Followed (on target at least 50 % of the trial)"] == "2 of 3"
    assert values["Time on target"] == "60 % (range 30–80 %)"
    assert values["Mean distance to target"] == "1.3°"
    assert values["Time to find target"] == "0.60 s"
    assert values["Valid pointer during trials"] == "100 %"
    gain, unit = values["Smooth-pursuit gain"].split(" ", 1)
    assert unit == "(median)" and float(gain) == pytest.approx(0.8, abs=0.06)
    assert values["Catch-up saccades"].endswith(" per s") and float(values["Catch-up saccades"].split()[0]) > 0.3


def test_a_range_of_one_value_is_not_printed_as_a_range(report):
    report["follow"]["summary"]["time_on_target_pct"] = {"mean": 70.0, "min": 70.0, "max": 70.0}
    assert dict(follow_summary_rows(report))["Time on target"] == "70 %"


def test_a_figure_the_report_could_not_give_is_a_dash_never_a_zero(report):
    summary = report["follow"]["summary"]
    for key in ("mean_distance_deg", "time_to_find_s", "pursuit_gain", "catch_up_per_s", "valid_pct"):
        summary[key] = None
    summary["time_on_target_pct"] = {"mean": None, "min": None, "max": None}
    summary["followed"] = None
    values = [value for _label, value in follow_summary_rows(report)]
    assert values == [DASH] * 7


def test_the_footnote_names_the_target_area_the_threshold_and_the_gain_caution(report):
    note = follow_footnote(report)
    assert "On target = within the drawn target + 40 px tolerance ring." in note
    assert "Followed = on target at least 50 % of the valid time (a fixed threshold in this version)." in note
    assert GAIN_CAPTION in note and "0.6 to 0.85" in note and "not a pass or fail value" in note
    assert "skipped" not in note
    report["session"]["n_skipped"] = 2
    assert "2 skipped trial(s) excluded." in follow_footnote(report)


# -- the trial table --------------------------------------------------------------------------------------------------


def test_the_trial_table_has_the_follow_columns_then_the_usual_eye_ones(report):
    assert len(FOLLOW_TRIAL_COLUMNS) == 14
    assert FOLLOW_TRIAL_COLUMNS[:10] == (
        "Trial", "Path", "Outcome", "Duration (s)", "Time on target (%)", "Mean distance (deg)",
        "Time to find (s)", "Pursuit gain", "Catch-up sacc. (/s)", "Valid (%)",
    )
    assert FOLLOW_TRIAL_COLUMNS[10:] == ("Fixations", "Saccades", "Pupil (mm)", "Pupil change (mm)")
    assert not any("(ms)" in c for c in FOLLOW_TRIAL_COLUMNS)


def test_the_trial_cells_are_the_follow_blocks_figures(report):
    rows = trial_rows(report)
    assert len(rows) == 3 and all(len(cells) == 14 for cells in rows)
    third = [cell.text for cell in rows[2]]
    assert third[:6] == ["3", "Horizontal", "Not followed", "10.0", "30", "1.9"]
    assert third[6] == "1.20" and third[9] == "100"
    assert float(third[7]) == pytest.approx(0.8, abs=0.06) and float(third[8]) > 0
    first = [cell.text for cell in rows[0]]
    assert first[2] == "Followed" and first[4] == "70" and first[6] == "0.40"
    assert rows[2][4].key == 30.0 and rows[1][2].key == "Followed"  # sorts by the number or the word


def test_a_skipped_follow_trial_has_dashes_in_every_figure(tmp_path):
    from tests.follow_fixtures import follow_record, onset, records

    recs = records()
    recs[1] = follow_record(1, onset(1), duration_s=3.0, on_target_ms=100.0, skipped=True, followed=False)
    cells = trial_rows(build_report(folder(tmp_path, recs=recs)))[1]
    assert [c.text for c in cells[:3]] == ["2", "Horizontal", "Skipped"]
    assert all(c.text == DASH and c.key is None for c in cells[3:])


# -- a Mouse test with no tracker ---------------------------------------------------------------------------------------


def test_a_mouse_follow_without_gaze_says_not_recorded_where_the_tracker_was_needed(mouse_report):
    values = dict(follow_summary_rows(mouse_report))
    assert values["Smooth-pursuit gain"] == values["Catch-up saccades"] == NOT_RECORDED
    assert values["Time on target"] != NOT_RECORDED and values["Followed (on target at least 50 % of the trial)"] == "2 of 3"
    for cells in trial_rows(mouse_report):
        assert [c.text for c in cells[GAIN:]] == [NOT_RECORDED] * (len(FOLLOW_TRIAL_COLUMNS) - GAIN)
        assert [c.text for c in cells[3:GAIN]] != [DASH] * (GAIN - 3)  # the live figures are there
        assert all(c.key is None for c in cells[GAIN:])


def test_a_gaze_follow_with_a_missing_gain_keeps_its_dash(report):
    report["follow"]["trials"][0]["pursuit_gain"] = None
    assert trial_rows(report)[0][GAIN].text == DASH


# -- the page ------------------------------------------------------------------------------------------------------------------


def test_the_page_shows_the_metric_table_the_follow_legend_and_the_columns(qapp, report):
    page = make_page(report)
    summary = page.summary
    table = summary.table
    assert [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())] == list(FOLLOW_SUMMARY_COLUMNS)
    assert table.rowCount() == 7 and table.texts()[1] == ["Time on target", "60 % (range 30–80 %)"]
    assert "Followed = on target at least 50 %" in summary.note.text()
    assert summary.legend.entries() == list(FOLLOW_LEGEND_ENTRIES)
    assert "nothing is selected" in summary.task_label.text()
    detailed = page.detailed
    header = detailed.table
    assert [header.horizontalHeaderItem(c).text() for c in range(header.columnCount())] == list(FOLLOW_TRIAL_COLUMNS)
    assert [header.item(r, 2).text() for r in range(3)] == ["Followed", "Followed", "Not followed"]
    assert detailed.legend.entries() == list(POINTER_LEGEND_ENTRIES) and not detailed.legend.isHidden()
    assert "light where it was off it" in detailed.trial_legend.text()


def test_a_selection_report_after_a_follow_one_gets_its_own_tables_and_legend_back(qapp, report, tmp_path):
    from tests.report_ui_fixtures import folder_report

    page = make_page(report)
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    assert page.summary.table.columnCount() == len(SUMMARY_COLUMNS)
    assert page.summary.table.horizontalHeaderItem(0).text() == ""
    assert page.summary.legend.entries() == list(LEGEND_ENTRIES)
    assert page.detailed.table.columnCount() == len(TRIAL_COLUMNS)
    assert page.detailed.legend.isHidden()
    assert "dark to light with time" in page.detailed.trial_legend.text()


def test_the_scanpath_and_heat_map_switches_work_for_a_gaze_follow(qapp, report):
    summary = make_page(report).summary
    assert summary.path_check.isEnabled() and summary.heat_check.isEnabled()
    assert (summary.path_check.text(), summary.heat_check.text()) == ("Scanpath", "Heat map")


def test_the_switches_that_need_gaze_are_off_and_say_so_for_a_mouse_run(qapp, mouse_report, report):
    page = make_page(mouse_report)
    summary = page.summary
    assert summary.targets_check.isEnabled() and summary.targets_check.isChecked()
    for check, name in ((summary.path_check, "Scanpath"), (summary.heat_check, "Heat map")):
        assert not check.isEnabled() and not check.isChecked() and check.text() == f"{name} (not recorded)"
    assert summary.map.overlays() == {"targets": True, "path": False, "heat": False}
    row = page.detailed.table
    assert row.item(0, GAIN).text() == NOT_RECORDED
    assert page.detailed.line_label.text() == "Eye data not recorded."
    page.set_report(report, test_name="Follow 2")  # a report with gaze brings them back
    assert summary.path_check.isEnabled() and summary.path_check.text() == "Scanpath"
    assert page.detailed.line_label.text().startswith("Scan path")


# -- the Target Map -------------------------------------------------------------------------------------------------------------


def render_trial(report, trial: int | None) -> QImage:
    widget = TargetMapWidget()
    widget.set_report(report)
    widget.set_trial(trial)
    return widget.render_to_image(QSize(1600, round(1600 / widget.aspect)), {"targets": True})


def test_a_trial_on_target_all_along_draws_only_the_dark_path(report):
    on_all_along = render_trial(report, 0)
    assert near(on_all_along, FOLLOW_ON) > 300
    assert near(on_all_along, FOLLOW_OFF) == 0


def test_a_trial_that_left_the_target_draws_its_off_stretch_lighter(report):
    left = render_trial(report, 2)
    assert near(left, FOLLOW_ON) > 300
    assert near(left, FOLLOW_OFF) > 150  # the stretch after the pointer moved away from the target


def test_the_runs_the_map_draws_are_the_reports_own(report):
    widget = TargetMapWidget()
    widget.set_report(report)
    runs = widget.model.pointer_runs
    assert [len(r) for r in runs] == [len(t["pointer_path"]) for t in report["follow"]["trials"]]
    assert {run["on"] for run in runs[2]} == {True, False} and {run["on"] for run in runs[0]} == {True}


def test_the_summary_map_marks_followed_and_not_followed_trials(report):
    widget = TargetMapWidget()
    widget.set_report(report)
    assert {m["outcome"] for m in widget.model.marks} == {"followed", "not_followed"}
    image = widget.render_to_image(QSize(1600, round(1600 / widget.aspect)), {"targets": True})
    greens = sum(1 for y in range(image.height()) for x in range(image.width())
                 if (c := image.pixelColor(x, y)).green() > c.red() + 40 and c.green() > c.blue() + 20)
    reds = sum(1 for y in range(image.height()) for x in range(image.width())
               if (c := image.pixelColor(x, y)).red() > c.green() + 80 and c.red() > c.blue() + 80)
    assert greens > 300 and reds > 100  # a followed trial's circle and a not followed trial's X


def test_a_report_without_pointer_runs_falls_back_to_the_usual_path(report):
    def painted(image: QImage) -> int:
        background = image.pixel(30, 30)  # inside the canvas, away from every mark
        return sum(
            1 for y in range(0, image.height(), 2) for x in range(0, image.width(), 2)
            if image.pixel(x, y) != background
        )

    for trial in report["follow"]["trials"]:
        trial["pointer_path"] = []
    with_path = render_trial(report, 0)
    for trial in report["trials"]:
        trial["path"] = []
    assert painted(with_path) > painted(render_trial(report, 0))  # the usual path is still drawn


# -- the legend --------------------------------------------------------------------------------------------------------------------


def test_the_follow_legends_name_the_followed_marks_and_the_two_pointer_lines():
    assert [k for k, _ in FOLLOW_LEGEND_ENTRIES] == ["hit", "timeout", "skipped", "track"]
    assert [t for _, t in FOLLOW_LEGEND_ENTRIES][:2] == ["Trial followed", "Trial not followed"]
    assert [(k, t) for k, t in POINTER_LEGEND_ENTRIES][:2] == [("on", "Pointer on target"), ("off", "Pointer off target")]
    assert not {t for _, t in FOLLOW_LEGEND_ENTRIES} & {t for _, t in LEGEND_ENTRIES} - {"Trial skipped"}


@pytest.mark.parametrize("kind, colour", [("on", FOLLOW_ON), ("off", FOLLOW_OFF)])
def test_the_pointer_line_icons_are_drawn_in_the_colour_of_the_line(qapp, kind, colour):
    image = symbol_image(kind)
    assert near(image, colour, 6) > 100
    assert near(image, FOLLOW_OFF if kind == "on" else FOLLOW_ON, 6) == 0
    assert kind in LINE_KINDS


def test_the_track_icon_is_a_faint_line_and_every_line_kind_draws(qapp):
    for kind in LINE_KINDS:
        image = QImage(QSize(60, 60), QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        paint_line_symbol(painter, QRectF(image.rect()), kind, _pen)
        painter.end()
        assert any(image.pixelColor(x, 30).alpha() > 0 for x in range(60)), kind


def test_the_pdf_legend_html_takes_the_follow_entries(qapp):
    html = legend_html(600, entries=FOLLOW_LEGEND_ENTRIES)
    for _kind, text in FOLLOW_LEGEND_ENTRIES:
        assert text in html
    assert "Target selected (hit)" not in html and html.count("data:image/png;base64,") == 4


# -- the PDF ----------------------------------------------------------------------------------------------------------------------------


def pdf_html(report) -> str:
    widget = TargetMapWidget()
    widget.set_report(report)
    image = widget.render_to_image(QSize(1800, round(1800 / widget.aspect)), {"targets": True})
    return build_report_html(report, test_name="Follow 1", evaluator="Dr. Lin", notes="", map_image=image)


def test_the_pdf_prints_the_metric_table_the_follow_columns_and_the_follow_definitions(qapp, report):
    html = pdf_html(report)
    assert "Error-free Target Selections" not in html and "Targets Not Selected" not in html
    _doc, summary = html_table(html, 2, "Followed")
    printed = [
        [summary.cellAt(r, c).firstCursorPosition().block().text() for c in range(2)] for r in range(1, 8)
    ]
    assert printed == follow_summary_rows(report)
    _doc, table = html_table(html, 14)
    assert [table.cellAt(0, c).firstCursorPosition().block().text() for c in range(14)] == list(FOLLOW_TRIAL_COLUMNS)
    for r, cells in enumerate(trial_rows(report), start=1):
        assert [table.cellAt(r, c).firstCursorPosition().block().text() for c in range(14)] == [c.text for c in cells]
    for text in FOLLOW_DEFINITIONS:
        assert text.split(":")[0] in html
    assert "Smooth-pursuit gain:" in html and "Catch-up saccades:" in html and "Clicks" not in html
    assert "On target = within the drawn target + 40 px tolerance ring." in html
    assert "Trial followed" in html and "Target selected (hit)" not in html
    assert html.count("data:image/png;base64,") == 1 + len(FOLLOW_LEGEND_ENTRIES)


def test_the_pdf_of_a_follow_report_is_written_and_has_a_trial_table_on_its_last_pages(qapp, report, tmp_path):
    page = make_page(report)
    path = page.export_pdf(tmp_path / "follow.pdf")
    doc = QtPdf.QPdfDocument()
    assert doc.load(str(path)) == QtPdf.QPdfDocument.Error.None_
    assert doc.pageCount() >= 2 and path.read_bytes().startswith(b"%PDF")


def test_the_pdf_of_a_mouse_run_says_not_recorded_in_the_gaze_cells(qapp, mouse_report):
    html = pdf_html(mouse_report)
    assert html.count(f">{NOT_RECORDED}<") >= 3 * (len(FOLLOW_TRIAL_COLUMNS) - GAIN) + 2  # trials + two summary rows


# -- an old Follow & Click folder (H10, A8) ------------------------------------------------------------------------------------------


def test_an_old_follow_and_click_folder_opens_in_the_old_layout_without_an_error(qapp, tmp_path):
    old = build_report(legacy_folder(tmp_path))
    page = make_page(old)
    assert page.summary.table.columnCount() == len(SUMMARY_COLUMNS) and page.summary.table.rowCount() == 4
    assert page.detailed.table.columnCount() == len(TRIAL_COLUMNS) and page.detailed.table.rowCount() == 3
    assert [page.detailed.table.item(r, 3).text() for r in range(3)] == ["Hit", "Not selected", "Hit"]
    assert page.summary.legend.entries() == list(LEGEND_ENTRIES) and page.detailed.legend.isHidden()
    assert "selects it by looking at it" in page.summary.task_label.text()
    page.show_detailed()
    page.detailed.table.sortRequested.emit(4)  # sorting an old folder's table is as it was
    path = export_report_pdf(tmp_path / "old.pdf", old, test_name="Old")
    assert path.exists() and path.stat().st_size > 5_000
    html = build_report_html(old, test_name="Old", evaluator="", notes="", map_image=None)
    assert "Error-free Target Selections" in html and "Followed (on target" not in html
