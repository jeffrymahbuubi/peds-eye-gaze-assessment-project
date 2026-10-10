"""SPEC-design-system-phase4.md H8-H10, M-5, M-6, M-6b: the printed report's sizes, page order,
header fill, labels and header words.

The claims are about text widths and fonts, which offscreen Qt cannot measure (no font database:
every glyph is one em wide), so the module registers the Windows Segoe UI files for its length and
sets the pixel-sized application font the real app has (the default font that made a heading
tag print at about 5 pt); it skips where the files are missing. The document is laid out exactly
as the writer prints it (:func:`report_pdf.laid_out_document`), and its lines are read back.
"""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QTextBlock, QTextDocument, QTextTable
from PySide6.QtWidgets import QApplication

import src.ui.report_page as report_page_module
import src.ui.report_pdf as report_pdf
from src.data.report_cache import build_report
from src.data.report_config import build_config_rows
from src.ui.design_tokens import CONTRAST_PAIRS, HEADER, INK, MAP_OVERLAY_ON_PANEL, WARNING_SUBTLE
from src.ui.map_legend import NUMBERS_NOTE, SCANPATH_NOTE
from src.ui.report_format import gaze_was_recorded
from src.ui.report_page import ReportPage
from src.ui.report_pdf import build_report_html, export_report_pdf
from src.ui.target_map import TargetMapWidget
from tests import real_fonts
from tests.follow_fixtures import folder as follow_folder
from tests.report_fixtures import RIG_META
from tests.report_ui_fixtures import SWITCH_META, SWITCH_PRESSES, folder_report

QtPdf = pytest.importorskip("PySide6.QtPdf")

SECTION_HEADINGS = (
    "Test Configuration", "Notes", "Summary of Results", "Eye Metrics", "Target Map",
    "Trial-by-Trial Results", "Definitions",
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def segoe(qapp):
    yield from real_fonts.segoe_ui(qapp)


# -- the reports of every layout --------------------------------------------------------------------


def selection(tmp_path):
    return folder_report(tmp_path / "selection")


def switch(tmp_path):
    return folder_report(tmp_path / "switch", presses=SWITCH_PRESSES, **SWITCH_META)


def follow(tmp_path):
    return build_report(follow_folder(tmp_path / "follow"))


def no_gaze(tmp_path):
    report = folder_report(tmp_path / "nogaze")
    report["session"]["gaze_recorded"] = False  # every eye cell says "not recorded"
    return report


def many_trials(tmp_path, n=40):
    report = folder_report(tmp_path / "many")
    base = report["trials"][0]
    report["trials"] = [dict(base, trial=i + 1) for i in range(n)]
    return report


LAYOUTS = {"selection": selection, "switch": switch, "follow": follow, "no gaze": no_gaze, "many trials": many_trials}


def map_image(report):
    """The page's map for the PDF (:meth:`ReportPage.export_pdf`): the targets, and the scanpath when
    gaze was recorded."""
    widget = TargetMapWidget()
    widget.set_report(report)
    overlays = {"targets": True, "path": gaze_was_recorded(report)}
    return widget.render_to_image(QSize(1800, round(1800 / widget.aspect)), overlays)


def html_of(report, *, with_map=True, **kw) -> str:
    kw = {"test_name": "Grid Click 1", "evaluator": "Dr. Lin", "notes": "Good attention", **kw}
    return build_report_html(report, map_image=map_image(report) if with_map else None, **kw)


class Laid:
    """A laid-out document and the writer it was laid out in (the writer must outlive it)."""

    def __init__(self, html: str) -> None:
        self.buffer = QBuffer()
        self.buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        self.writer = report_pdf.page_writer(self.buffer)
        self.doc: QTextDocument = report_pdf.laid_out_document(html, self.writer)
        self.doc.documentLayout().pageCount()  # lays everything out

    def blocks(self):
        block = self.doc.begin()
        while block.isValid():
            yield block
            block = block.next()

    def block(self, text: str) -> QTextBlock:
        return next(b for b in self.blocks() if b.text() == text)

    def page_of(self, block: QTextBlock) -> int:
        rect: QRectF = self.doc.documentLayout().blockBoundingRect(block)
        return int(rect.top() // self.doc.pageSize().height())

    def tables(self) -> list[QTextTable]:
        found: list[QTextTable] = []

        def walk(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    found.append(child)
                walk(child)

        walk(self.doc.rootFrame())
        return found

    def header_cells(self):
        """``(text, block)`` of every non-empty header cell of every table of five columns or more."""
        for table in self.tables():
            if table.columns() >= report_pdf.WIDTH_FROM_COLUMNS:
                for c in range(table.columns()):
                    block = table.cellAt(0, c).firstCursorPosition().block()
                    if block.text().strip():
                        yield block.text(), block


def font_of(block: QTextBlock) -> QFont:
    return block.begin().fragment().charFormat().font()


def broken_inside_a_word(laid: Laid) -> list[str]:
    """The header cells with a line that ends anywhere but after a space."""
    bad = []
    for text, block in laid.header_cells():
        layout = block.layout()
        for i in range(layout.lineCount() - 1):
            line = layout.lineAt(i)
            end = line.textStart() + line.textLength()
            if end < len(text) and not text[end - 1].isspace():
                bad.append(f"{text}: {text[:end]!r} | {text[end:]!r}")
    return bad


# -- H8 / M-6b: the title and the headings ------------------------------------------------------------


def test_the_title_is_12_pt_and_every_section_heading_11_pt_all_at_weight_600(qapp, segoe, tmp_path):
    assert qapp.font().pixelSize() == 14  # the conditions of the app: the pixel-sized default font
    laid = Laid(html_of(selection(tmp_path)))
    title = next(b for b in laid.blocks() if b.text().startswith("Summary Results, "))
    assert font_of(title).pointSizeF() == 12.0 and int(font_of(title).weight()) == 600
    for heading in SECTION_HEADINGS:
        font = font_of(laid.block(heading))
        assert font.pointSizeF() == 11.0 and int(font.weight()) == 600, heading


def test_the_heading_tags_that_printed_at_five_points_are_gone(qapp, tmp_path):
    """A heading tag is sized relative to the pixel-sized default font and ignores the pt size
    written on it; the title and headings are paragraphs with an explicit size and weight."""
    html = html_of(selection(tmp_path))
    assert not re.search(r"<h[1-6]\b", html)
    assert html.count("font-size:12.0pt; font-weight:600") == 1
    assert html.count("font-size:11.0pt; font-weight:600") == len(SECTION_HEADINGS)


def test_the_body_is_9_point_5_the_trial_table_8_and_the_definitions_8_point_5(qapp, segoe, tmp_path):
    html = html_of(selection(tmp_path))
    assert "sans-serif; font-size:9.5pt" in html and report_pdf.BODY_PT == 9.5
    trial_table = html.split(">Trial-by-Trial Results</p>")[1].split("</table>")[0]
    assert "font-size:8.0pt" in trial_table and report_pdf.TRIAL_TABLE_PT == 8.0
    definitions = html.split(">Definitions</p>")[1]
    assert definitions.startswith('<ul style="font-size:8.5pt') and report_pdf.DEFINITIONS_PT == 8.5


@pytest.mark.parametrize("layout", ["selection", "no gaze", "many trials"])
def test_a_thirteen_column_trial_table_stays_at_8_pt(qapp, segoe, tmp_path, layout):
    html = html_of(LAYOUTS[layout](tmp_path))
    assert "font-size:8.0pt" in html.split(">Trial-by-Trial Results</p>")[1].split("</table>")[0]


# -- H8 / M-5: the page order -----------------------------------------------------------------------------


@pytest.mark.parametrize("layout", ["selection", "switch", "follow"])
def test_page_1_holds_the_header_configuration_summary_and_eye_metrics_and_the_map_starts_page_2(
    qapp, segoe, tmp_path, layout
):
    laid = Laid(html_of(LAYOUTS[layout](tmp_path)))
    title = next(b for b in laid.blocks() if b.text().startswith("Summary Results, "))
    pages = {heading: laid.page_of(laid.block(heading)) for heading in SECTION_HEADINGS}
    assert laid.page_of(title) == 0
    for heading in ("Test Configuration", "Notes", "Summary of Results", "Eye Metrics"):
        assert pages[heading] == 0, heading
    assert pages["Target Map"] == 1  # the forced break: the map and its legend start page 2
    assert pages["Trial-by-Trial Results"] >= 1
    # every table of page 1 is whole on it, down to the last row of the Eye Metrics
    eye = next(t for t in laid.tables() if t.columns() == 2 and t.cellAt(0, 0).firstCursorPosition().block().text() == "Metric")
    assert laid.page_of(eye.cellAt(eye.rows() - 1, 1).firstCursorPosition().block()) == 0


# -- the PDF's map has the Summary's scanpath, and its legend says so (the user's answer of 2026-10-09) ----------------


def with_scanpath(report):
    """A scanpath along the bottom edge of the canvas, clear of every target mark."""
    report["trials"][0]["scanpath"] = [[0.06, 0.95], [0.5, 0.95], [0.94, 0.95]]
    return report


def overlay_pixels(image: QImage) -> int:
    """How many pixels are the scanpath's blue (the overlay colour at alpha 200 over white)."""
    want = QColor(MAP_OVERLAY_ON_PANEL)
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if all(abs(a - b) <= 3 for a, b in zip(image.pixelColor(x, y).getRgb()[:3], want.getRgb()[:3], strict=True))
    )


def capture_export(monkeypatch) -> dict:
    """Make :meth:`ReportPage.export_pdf` hand what it passes to the writer to the test."""
    seen: dict = {}
    monkeypatch.setattr(report_page_module, "export_report_pdf", lambda path, report, **kw: seen.update(kw) or path)
    return seen


def test_the_page_gives_the_pdf_the_map_with_the_scanpath_drawn_by_the_screens_own_code(qapp, tmp_path, monkeypatch):
    seen = capture_export(monkeypatch)
    page = ReportPage()
    page.set_report(with_scanpath(selection(tmp_path)), test_name="Grid Click 1")
    page.export_pdf(tmp_path / "a.pdf")
    image = seen["map_image"]
    assert overlay_pixels(image) > 200  # the line along the bottom edge and its three dots
    screen = page.summary.map.render_to_image(image.size(), {"targets": True, "path": True})
    assert image == screen  # pixel for pixel what the Summary's map draws with Targets and Scanpath on


def test_the_pdf_map_has_the_scanpath_whatever_the_summarys_switches_say(qapp, tmp_path, monkeypatch):
    seen = capture_export(monkeypatch)
    page = ReportPage()
    page.set_report(with_scanpath(selection(tmp_path)), test_name="Grid Click 1")
    assert not page.summary.path_check.isChecked()  # off on the screen
    page.summary.targets_check.setChecked(False)
    page.export_pdf(tmp_path / "a.pdf")
    assert overlay_pixels(seen["map_image"]) > 200
    assert page.summary.map.overlays() == {"targets": False, "path": False, "heat": False}  # untouched


def test_a_test_with_no_gaze_has_no_scanpath_in_the_pdf_map_and_no_line_in_its_legend(qapp, segoe, tmp_path, monkeypatch):
    seen = capture_export(monkeypatch)
    report = with_scanpath(no_gaze(tmp_path))
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    page.export_pdf(tmp_path / "a.pdf")
    assert overlay_pixels(seen["map_image"]) == 0
    assert SCANPATH_NOTE not in html_of(report) and NUMBERS_NOTE in html_of(report)


@pytest.mark.parametrize("layout", ["selection", "switch", "follow"])
def test_the_pdf_legend_names_the_scanpath_on_page_2_with_the_map(qapp, segoe, tmp_path, layout):
    report = LAYOUTS[layout](tmp_path)
    html = html_of(report)
    assert html.count(SCANPATH_NOTE) == 1 and html.index(SCANPATH_NOTE) < html.index(NUMBERS_NOTE)
    laid = Laid(html)
    note, numbers = laid.block(SCANPATH_NOTE), laid.block(NUMBERS_NOTE)
    assert laid.page_of(laid.block("Target Map")) == laid.page_of(note) == laid.page_of(numbers) == 1


def test_no_legend_line_without_a_map(qapp, tmp_path):
    assert SCANPATH_NOTE not in html_of(selection(tmp_path), with_map=False)


def test_the_written_pdf_shows_the_scanpath_on_page_2_when_gaze_was_recorded(qapp, segoe, tmp_path, monkeypatch):
    """End to end, read back from the file: the blue of the scanpath is on page 2 with gaze and not
    without it (nothing else on the page is blue)."""

    def blue_on_page_2(report) -> int:
        path = export_report_pdf(tmp_path / "r.pdf", report, test_name="Grid Click 1", map_image=map_image(report))
        document = QtPdf.QPdfDocument()
        assert document.load(str(path)) == QtPdf.QPdfDocument.Error.None_
        page = document.render(1, QSize(1240, 1754))
        document.close()
        return sum(
            1
            for y in range(0, page.height(), 2)
            for x in range(0, page.width(), 2)
            if (c := page.pixelColor(x, y)).blue() - c.red() > 60 and c.blue() - c.green() > 20
        )

    assert blue_on_page_2(with_scanpath(selection(tmp_path))) > 50
    assert blue_on_page_2(with_scanpath(no_gaze(tmp_path))) == 0


def test_the_written_file_is_two_pages_for_a_short_test(qapp, segoe, tmp_path):
    report = selection(tmp_path)
    path = export_report_pdf(tmp_path / "r.pdf", report, test_name="Grid Click 1", map_image=map_image(report))
    document = QtPdf.QPdfDocument()
    assert document.load(str(path)) == QtPdf.QPdfDocument.Error.None_
    assert document.pageCount() == 2  # page 1: the text; page 2: the map, the trials, the definitions


# -- H8 / F2: the table header fill --------------------------------------------------------------------------


def test_every_table_header_is_the_header_grey_with_ink_text(qapp, tmp_path):
    html = html_of(selection(tmp_path))
    heads = re.findall(r"<th ([^>]*)>", html)
    assert heads and all(f'bgcolor="{HEADER}"' in h for h in heads)
    assert 'span style="color' not in html  # the text is the body's ink, not a tinted span
    assert (INK, HEADER, 13.71) in CONTRAST_PAIRS
    assert not re.search(r'bgcolor="#(?!E0E0E0)', html)  # and no other tint anywhere (the legend's is gone)


def test_the_warning_banner_of_a_partial_run_is_the_warning_subtle_paragraph(qapp, tmp_path):
    html = html_of(folder_report(tmp_path, planned=18))
    assert f"background-color:{WARNING_SUBTLE}" in html and "Ended early: 6 of 18 trials" in html


# -- H9 / M-6: the labels and the text fields ---------------------------------------------------------------------


def config_table(laid: Laid) -> QTextTable:
    return next(
        t for t in laid.tables() if t.columns() == 2 and t.cellAt(0, 0).firstCursorPosition().block().text() == "Setting"
    )


def test_the_pdfs_configuration_labels_are_the_configuration_pages_and_build_config_rows(qapp, segoe, tmp_path):
    report = selection(tmp_path)
    expected = [label for label, _value in build_config_rows(RIG_META["settings"], RIG_META)]
    assert len(expected) == 17
    laid = Laid(html_of(report))  # the tables belong to the document: keep it
    table = config_table(laid)
    printed = [table.cellAt(r, 0).firstCursorPosition().block().text() for r in range(1, table.rows())]
    assert printed == expected
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    assert [page.config_table.cell_text(r, 0) for r in range(page.config_table.rowCount())] == printed
    values = [table.cellAt(r, 1).firstCursorPosition().block().text() for r in range(1, table.rows())]
    assert values == [page.config_table.cell_text(r, 1) for r in range(page.config_table.rowCount())]


def test_no_text_field_of_the_pdf_is_a_lone_em_dash(qapp, segoe, tmp_path):
    """Phase 1 U5: a missing text prints "not recorded"; the dash stays in the figure cells."""
    report = selection(tmp_path)
    report["session"]["config_name"] = None
    laid = Laid(html_of(report, evaluator="", notes=""))
    texts = [b.text() for b in laid.blocks()]
    header_line = next(t for t in texts if t.startswith("Subject: "))
    assert "Evaluator: not recorded" in header_line and "—" not in header_line
    assert "Configuration Name: not recorded" in texts
    assert texts[texts.index("Notes") + 1] == "not recorded"
    config = config_table(laid)
    for r in range(1, config.rows()):
        assert config.cellAt(r, 1).firstCursorPosition().block().text() != "—"


# -- M-6b: no header word is split --------------------------------------------------------------------------------


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_no_table_header_word_is_split_across_lines(qapp, segoe, tmp_path, layout):
    laid = Laid(html_of(LAYOUTS[layout](tmp_path)))
    assert len(list(laid.header_cells())) >= 13  # the trial table at least
    assert broken_inside_a_word(laid) == []


def test_every_header_word_has_room_to_spare_not_just_a_fit(qapp, segoe, tmp_path):
    """The old squeeze left each of these columns exactly as wide as its longest word (the cell
    was 0.1 px wider), and one more pixel of rounding broke "Entries" into "Entrie" and "s"."""
    for layout in ("selection", "switch", "follow"):
        laid = Laid(html_of(LAYOUTS[layout](tmp_path)))
        for text, block in laid.header_cells():
            metrics = QFontMetricsF(font_of(block), laid.writer)
            longest = max(metrics.horizontalAdvance(word) for word in text.replace(report_pdf.WORD_JOINER, "").split())
            room = laid.doc.documentLayout().blockBoundingRect(block).width() - longest
            assert room >= 6.0, (layout, text, room)  # 6 px at 300 dpi is 1.5 CSS px


def test_a_header_breaks_after_a_slash_only_without_the_word_joiner(qapp, segoe):
    """Qt also breaks after "/" and "-": at a width between "Mean peak vel. (deg/" and the whole
    label it cut "(deg/" from "s)". The joiner keeps the word whole, so the header wraps at a space."""
    label = "Mean peak vel. (deg/s)"
    font = QFont("Segoe UI")
    font.setPointSizeF(8.0)
    font.setBold(True)
    probe = Laid("<html></html>")
    metrics = QFontMetricsF(font, probe.writer)
    middle = (metrics.horizontalAdvance("Mean peak vel. (deg/") + metrics.horizontalAdvance(label)) / 2
    css_width = round(middle * 96 / report_pdf.PDF_RESOLUTION + 3)

    def lines(text: str) -> list[str]:
        html = (
            "<html><body style=\"font-family:'Segoe UI'; font-size:8pt\">"
            f'<table border="1" cellspacing="0" cellpadding="0" width="{css_width}"><tr><th>{text}</th></tr></table></body></html>'
        )
        laid = Laid(html)
        block = laid.tables()[0].cellAt(0, 0).firstCursorPosition().block()
        layout = block.layout()
        shown = block.text()
        return [shown[layout.lineAt(i).textStart():][: layout.lineAt(i).textLength()] for i in range(layout.lineCount())]

    assert lines(label)[0].endswith("(deg/")  # the bug
    assert [part.replace(report_pdf.WORD_JOINER, "") for part in lines(report_pdf._unbreakable(label))] == [
        "Mean peak vel. ", "(deg/s)",
    ]
    assert report_pdf._unbreakable("Catch-up sacc. (/s)").count(report_pdf.WORD_JOINER) == 2


def test_the_printed_pdf_reads_entries_whole(qapp, segoe, tmp_path):
    """End to end: the text of the written file, not the layout's lines."""
    report = selection(tmp_path)
    path = export_report_pdf(tmp_path / "r.pdf", report, test_name="Grid Click 1", map_image=map_image(report))
    document = QtPdf.QPdfDocument()
    assert document.load(str(path)) == QtPdf.QPdfDocument.Error.None_
    text = "\n".join(document.getAllText(page).text() for page in range(document.pageCount()))
    if not text.strip():
        pytest.skip("this QtPdf cannot extract text")
    assert "Entries" in text and "Fixations" in text and "Saccades" in text
    assert not re.search(r"Entrie\s+s\b", text)


def test_a_table_that_cannot_give_every_word_its_room_steps_the_font_down_not_the_word(qapp, segoe):
    meter = report_pdf._Meter()
    columns = [f"Extraordinarily{n}" for n in range(15)]
    rows = [["1.00"] * len(columns)]
    assert report_pdf._column_widths(columns, rows, meter, 8.0) is None  # 15 long words do not fit at 8
    html = report_pdf._measured_table(columns, rows, ["left"] * 15, meter, 8.0, steps_down=True)
    size = float(re.search(r"font-size:([\d.]+)pt", html).group(1))
    assert report_pdf.TRIAL_TABLE_MIN_PT <= size < 8.0
    fits = report_pdf._column_widths(columns, rows, meter, size)
    assert fits is None or sum(fits) == pytest.approx(100.0, abs=0.01)


def test_the_measured_widths_fill_the_table_and_no_column_is_narrower_than_its_word(qapp, segoe):
    meter = report_pdf._Meter()
    columns = ["Trial", "Outcome", "Entries", "Fixations", "Saccades"]
    rows = [["1", "Not selected", "1", "3", "3"]]
    widths = report_pdf._column_widths(columns, rows, meter, 8.0)
    assert widths is not None and sum(widths) == pytest.approx(100.0, abs=0.01)
    px = [w / 100.0 * meter.text_width for w in widths]
    for label, width in zip(columns, px, strict=True):
        assert width > meter.width(label, 8.0, bold=True) + 6 * meter.px_per_css_px, label
