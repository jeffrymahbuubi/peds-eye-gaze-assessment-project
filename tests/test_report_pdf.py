"""Print Report: the per-test report as a PDF (SPEC-compass-task-flow.md 4D.8; G12, AD12).
Offscreen Qt writing to ``tmp_path``; the page is read back with QtPdf where the
claim is about the document (page size, page count), and the HTML is checked where
the claim is about what it contains (offscreen has no fonts, so no text is extracted).
The phase-4 layout (title and heading sizes, the page order, the header words) is in
``test_report_pdf_phase4.py``."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QTextDocument, QTextTable
from PySide6.QtWidgets import QApplication

import src.ui.report_pdf as report_pdf
from src.ui.design_tokens import BORDER_SUBTLE
from src.ui.map_legend import LEGEND_ENTRIES, NUMBERS_NOTE
from src.ui.report_format import DEFINITIONS, TRIAL_COLUMNS, eye_rows, summary_table, trial_cells
from src.ui.report_pdf import build_report_html, export_report_pdf
from src.ui.target_map import TargetMapWidget
from tests.report_ui_fixtures import folder_report

QtPdf = pytest.importorskip("PySide6.QtPdf")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def map_image(report):
    widget = TargetMapWidget()
    widget.set_report(report)
    return widget.render_to_image(QSize(1800, round(1800 / widget.aspect)), {"targets": True})


def read_back(path: Path):
    doc = QtPdf.QPdfDocument()
    assert doc.load(str(path)) == QtPdf.QPdfDocument.Error.None_
    return doc


def many_trials(report, n):
    out = copy.deepcopy(report)
    base = out["trials"][0]
    out["trials"] = [dict(copy.deepcopy(base), trial=i + 1) for i in range(n)]
    return out


def html_tables(html: str) -> tuple[QTextDocument, list[QTextTable]]:
    """The document (keep it alive: the tables belong to it) and its tables."""
    doc = QTextDocument()
    doc.setHtml(html)
    found: list[QTextTable] = []

    def walk(frame):
        for child in frame.childFrames():
            if isinstance(child, QTextTable):
                found.append(child)
            walk(child)

    walk(doc.rootFrame())
    return doc, found


# -- G12 / AD12: a valid PDF with everything in it -----------------------------------------------


def test_the_pdf_is_a_valid_file_of_a_reasonable_size(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    path = export_report_pdf(
        tmp_path / "report.pdf", report, test_name="Grid Click 1", evaluator="Dr. Lin",
        notes="Good attention", map_image=map_image(report),
    )
    data = path.read_bytes()
    assert path == tmp_path / "report.pdf"
    assert data.startswith(b"%PDF") and len(data) > 10_000
    assert data.rstrip().endswith(b"%%EOF")


def test_the_pdf_is_a4_portrait_with_the_map_on_its_own_page_after_the_summary(qapp, tmp_path):
    """V3: portrait (it was landscape). Every page is 595 x 842 pt, taller than wide."""
    report = folder_report(tmp_path / "data")
    path = export_report_pdf(tmp_path / "r.pdf", report, test_name="T", map_image=map_image(report))
    doc = read_back(path)
    assert doc.pageCount() >= 2  # the configuration and summary page, then the map and the rest
    for page in range(doc.pageCount()):
        size = doc.pagePointSize(page)
        assert size.width() == pytest.approx(595.3, abs=1.0)
        assert size.height() == pytest.approx(841.9, abs=1.0)
        assert size.height() > size.width()


def test_the_page_layout_the_writer_is_given_is_a4_portrait(qapp, tmp_path, monkeypatch):
    """The orientation is what the writer is told, not just what comes back."""
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

    seen = {}
    real = QPdfWriter.setPageLayout

    def spy(self, layout):
        seen["orientation"] = layout.orientation()
        seen["size"] = layout.pageSize().id()
        return real(self, layout)

    monkeypatch.setattr(QPdfWriter, "setPageLayout", spy)
    export_report_pdf(tmp_path / "r.pdf", folder_report(tmp_path / "data"), test_name="T")
    assert seen == {"orientation": QPageLayout.Orientation.Portrait, "size": QPageSize.PageSizeId.A4}


def test_a_long_trial_table_continues_on_more_pages(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    short = export_report_pdf(tmp_path / "s.pdf", report, map_image=map_image(report))
    long = export_report_pdf(tmp_path / "l.pdf", many_trials(report, 150), map_image=map_image(report))
    assert read_back(long).pageCount() >= read_back(short).pageCount() + 2


def test_the_html_holds_header_configuration_both_tables_the_map_and_every_trial(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(
        report, test_name="Grid Click 1", evaluator="Dr. Lin", notes="Good attention", map_image=map_image(report)
    )
    assert "Summary Results, Grid Click 1" in html
    assert "Dr. Lin" in html and "Good attention" in html and "P001" in html
    for label, value in report["config"]["rows"]:
        assert label in html and value.replace("&", "&amp;") in html
    for row in summary_table(report):
        assert row[0] in html and row[1] in html
    for label, _value in eye_rows(report):
        assert label in html
    # the Target Map, as one PNG, and the legend's four icons
    assert html.count("data:image/png;base64,") == 1 + len(LEGEND_ENTRIES)
    assert "Trial-by-Trial Results" in html and "Target Map" in html and "Definitions" in html
    for text in DEFINITIONS:
        assert text.split(":")[0] in html
    assert html.count("<td align") >= 6 * len(TRIAL_COLUMNS)  # a cell for every trial row


def test_the_trial_table_has_its_header_row_marked_so_every_page_repeats_it(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    doc, tables = html_tables(html)
    trial_tables = [t for t in tables if t.columns() == len(TRIAL_COLUMNS)]
    assert len(trial_tables) == 1
    table = trial_tables[0]
    assert table.rows() == 1 + len(report["trials"])
    assert table.format().headerRowCount() == 1  # Qt repeats header rows on each printed page


def test_the_html_has_the_same_text_as_the_page_for_every_trial_cell(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=None)
    doc, tables = html_tables(html)
    table = next(t for t in tables if t.columns() == len(TRIAL_COLUMNS))
    for r, trial in enumerate(report["trials"], start=1):
        printed = [table.cellAt(r, c).firstCursorPosition().block().text() for c in range(table.columns())]
        assert printed == [cell.text for cell in trial_cells(trial)]


def test_the_banner_of_a_partial_run_is_in_the_pdf(qapp, tmp_path):
    report = folder_report(tmp_path / "data", planned=18)
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=None)
    assert "Ended early: 6 of 18 trials" in html


def test_without_a_map_image_there_is_no_target_map_section(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=None)
    assert "Target Map" not in html and "data:image" not in html
    export_report_pdf(tmp_path / "r.pdf", report)  # and it still writes


def test_text_from_the_operator_is_escaped_and_notes_keep_their_line_breaks(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(
        report, test_name="<b>x</b> & y", evaluator="<i>E</i>", notes="line 1\nline <2>", map_image=None
    )
    assert "<b>x</b> & y" not in html and "&lt;b&gt;x&lt;/b&gt; &amp; y" in html
    assert "&lt;i&gt;E&lt;/i&gt;" in html
    assert "line 1<br>line &lt;2&gt;" in html


def test_an_empty_evaluator_and_notes_print_as_not_recorded(qapp, tmp_path):
    html = build_report_html(folder_report(tmp_path / "data"), test_name="T", evaluator="", notes="", map_image=None)
    assert "Evaluator: <b>not recorded</b>" in html
    assert re.search(r'>Notes</p><p style="[^"]*">not recorded</p>', html)


def test_a_legacy_folder_exports_without_error(qapp, tmp_path):
    report = folder_report(tmp_path / "data", legacy=True)
    path = export_report_pdf(tmp_path / "old.pdf", report, test_name="Old", map_image=map_image(report))
    assert path.read_bytes().startswith(b"%PDF")


def test_a_report_with_no_trials_still_exports(qapp, tmp_path):
    path = export_report_pdf(tmp_path / "empty.pdf", {"session": {}, "trials": []})
    assert path.read_bytes().startswith(b"%PDF")


# -- writing safely ----------------------------------------------------------------------------------


def test_the_file_is_written_whole_with_no_partial_file_left(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    export_report_pdf(tmp_path / "r.pdf", report)
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["r.pdf"]


def test_exporting_again_replaces_the_file(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    target = tmp_path / "r.pdf"
    target.write_bytes(b"old content")
    export_report_pdf(target, report, test_name="Second")
    assert target.read_bytes().startswith(b"%PDF")


def test_a_missing_folder_raises_oserror_and_leaves_nothing_behind(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    with pytest.raises(OSError):
        export_report_pdf(tmp_path / "no" / "such" / "folder" / "r.pdf", report)
    assert not (tmp_path / "no").exists()


def test_a_failed_write_keeps_the_earlier_file_and_cleans_up(qapp, tmp_path, monkeypatch):
    report = folder_report(tmp_path / "data")
    target = tmp_path / "r.pdf"
    target.write_bytes(b"the earlier report")

    def broken(path, html, title):
        path.write_bytes(b"half a pdf")
        raise OSError("disk full")

    monkeypatch.setattr(report_pdf, "_write", broken)
    with pytest.raises(OSError, match="disk full"):
        export_report_pdf(target, report)
    assert target.read_bytes() == b"the earlier report"
    assert not list(tmp_path.glob("*.part"))


def test_a_target_that_is_a_folder_raises_oserror(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    (tmp_path / "taken.pdf").mkdir()
    with pytest.raises(OSError):
        export_report_pdf(tmp_path / "taken.pdf", report)
    assert not list(tmp_path.glob("*.part"))


def test_the_map_width_is_given_in_css_px_which_the_layout_scales_itself():
    assert report_pdf.mm_to_css_px(25.4) == 96  # an inch is 96 CSS px, whatever the writer's dpi
    assert report_pdf.mm_to_css_px(report_pdf.MAP_WIDTH_MM) == round(report_pdf.MAP_WIDTH_MM / 25.4 * 96)


def test_the_map_fits_between_the_margins_of_a_portrait_page():
    """No clipping (V3): the picture is no wider than the 190 mm between the 10 mm margins
    (the first portrait version used 190 and spilled 2 mm over the right edge when rendered)."""
    assert report_pdf.MAP_WIDTH_MM < 210.0 - 2 * report_pdf.MARGIN_MM


# -- V3: one stacked column; V1: the legend; V5: seconds ---------------------------------------------


def test_the_sections_are_stacked_in_the_order_configuration_summary_eye_metrics_map(qapp, tmp_path):
    """Phase 4 H8: Eye Metrics moved up in front of the map, so page 1 is not 40 % blank."""
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    order = [html.index(h) for h in (
        ">Test Configuration</p>", ">Summary of Results</p>", ">Eye Metrics</p>", ">Target Map</p>",
        ">Trial-by-Trial Results</p>", ">Definitions</p>",
    )]
    assert order == sorted(order)
    # one column: the old side-by-side layout table (a 38 % first cell) is gone
    assert 'width="38%"' not in html


def test_the_map_starts_a_new_page_so_it_is_never_split_from_its_legend(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    assert re.search(r'page-break-before:always;[^"]*">Target Map</p>', html)
    assert html.count("page-break-before") == 1  # and nothing else breaks the page
    assert html.index(">Eye Metrics</p>") < html.index("page-break-before")  # H10: page 1 ends with them


def test_the_legend_is_under_the_map_with_its_four_entries_and_the_numbers_note(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    assert html.index("data:image/png;base64,") < html.index(LEGEND_ENTRIES[0][1]) < html.index(">Trial-by-Trial Results</p>")
    for _kind, label in LEGEND_ENTRIES:
        assert label in html
    assert NUMBERS_NOTE in html
    assert BORDER_SUBTLE in html and "bgcolor" not in html.split("Target Map")[1].split("Trial-by-Trial")[0]
    assert f'width="{report_pdf.mm_to_css_px(report_pdf.MAP_WIDTH_MM)}"' in html  # as wide as the map


def test_no_legend_without_a_map(qapp, tmp_path):
    html = build_report_html(folder_report(tmp_path / "data"), test_name="T", evaluator="", notes="", map_image=None)
    assert NUMBERS_NOTE not in html and "data:image" not in html


def test_the_old_one_line_legend_is_gone(qapp, tmp_path):
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    assert "hit = green circle" not in html


def test_the_pdf_shows_seconds_never_milliseconds(qapp, tmp_path):
    """V5: configuration rows, the tables and the definitions all read in seconds."""
    report = folder_report(tmp_path / "data")
    html = build_report_html(report, test_name="T", evaluator="", notes="", map_image=map_image(report))
    visible = re.sub(r"<[^>]*>", " ", re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", html))
    assert not re.search(r"\bms\b", visible), re.findall(r".{20}\bms\b.{10}", visible)
    assert "Dwell, threshold 0.8 s, refractory 0.5 s" in visible
    assert "Mean fix. dur. (s)" in visible and "0.12 s" in visible
