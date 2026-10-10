"""Print Report: the per-test report as an A4 **portrait** PDF
(SPEC-compass-task-flow.md 4D.8, U9, HD13; portrait since 7.1, V3; SPEC-design-system-phase4.md H8).

A :class:`QTextDocument` filled from HTML and printed by a :class:`QPdfWriter` (both
in QtGui): no printer dialog, no QtPrintSupport. One column, stacked. Page 1: the header, the
Test Configuration table and Notes, the Summary of Results and the Eye Metrics. The Target Map
(the targets and, when gaze was recorded, the Summary's one-colour Scanpath, as one PNG, with its
symbol legend) starts page 2, then the Trial-by-Trial table
with its header row repeated on every page, and the definitions of the measures. The text and the
choice of tables (Switch's Clicks columns, Follow the Target's Metric / Value summary) are the
page's own (:mod:`report_layout`), so the printout and the screen cannot disagree.

Units: the document lays out in the writer's own pixels (300 dpi) and the layout
scales every length written in CSS ``px`` (padding, margins, an image's width) by the
writer's dpi itself, so a ``px`` here is the usual 1/96 inch: a length is **not**
converted again (doing so made rows three times too tall). Fonts are in pt.

Two Qt facts shape the HTML. A heading tag (``h2``, ``h3``) gets a size *relative to the
document's default font*, which is a pixel-sized 14 px font, so it printed at about 5 pt whatever
size the style said: the title and the section headings are paragraphs with an explicit size and
weight. And a table squeezes its columns down to the width of their longest word, to no slack at
all, so a header word can lose its last letter ("Entrie" over "s"): every table of five columns or
more gets explicit column widths, measured in the writer's own pixels, that leave each word room.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

from PySide6.QtCore import QBuffer, QMarginsF, QSizeF
from PySide6.QtGui import (
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QTextDocument,
)

from .design_tokens import BORDER_SUBTLE, FONT_FAMILY, HEADER, INK, TEXT_SECONDARY, WARNING_SUBTLE
from .map_legend import FOLLOW_LEGEND_ENTRIES, LEGEND_ENTRIES, SCANPATH_NOTE, legend_html, png_data_uri
from .report_format import (
    NOT_RECORDED,
    banner_lines,
    eye_rows,
    gaze_was_recorded,
    started_text,
    task_sentence,
)
from .report_layout import (
    FOLLOW,
    definition_lines,
    layout_kind,
    summary_aligns,
    summary_bold_first,
    summary_cells,
    summary_header,
    summary_note,
    trial_aligns,
    trial_columns,
    trial_rows,
)

PDF_RESOLUTION = 300  # dpi of the writer
MARGIN_MM = 10.0
MAP_WIDTH_MM = 186.0  # of the 190 mm between the margins of an A4 portrait page (190 spills over)
TITLE_PT = 12.0  # the title and the section headings: 600 weight (H8)
HEADING_PT = 11.0
HEADING_WEIGHT = 600
BODY_PT = 9.5
NOTE_PT = BODY_PT - 1  # a footnote under a table or the map
DEFINITIONS_PT = 8.5
TRIAL_TABLE_PT = 8.0  # the Trial-by-Trial table; a layout whose header words do not fit steps down
TRIAL_TABLE_STEP_PT = 0.5
TRIAL_TABLE_MIN_PT = 6.5
CONFIG_LABEL_WIDTH = "30%"  # the Setting column of the configuration table
FOLLOW_LABEL_WIDTH = "50%"  # the Metric column of Follow the Target's summary: its labels are long
WIDTH_FROM_COLUMNS = 5  # a table of this many columns or more gets measured column widths
# Page 1 holds the header, the configuration, the summary and the Eye Metrics (H8): at 9.5 pt that
# takes table rows with 1 px above and below the text (the sides keep their 3 px) and small gaps
# between blocks, in CSS px.
CELL_PADDING_CSS_PX = 3
CELL_PADDING_V_CSS_PX = 1
HEADING_GAP_CSS_PX = 10  # above a section heading
BLOCK_GAP_CSS_PX = 4  # below a paragraph, before the table or heading that follows
# What a cell needs around its text, in CSS px: the table's cellpadding and border (1) on each
# side, and a little room beyond the longest word so that rounding can never push it over.
CELL_EXTRA_CSS_PX = 2 * CELL_PADDING_CSS_PX + 2 * 1
WORD_SLACK_CSS_PX = 3
DOCUMENT_MARGIN_PX = 4  # QTextDocument's default margin, in the writer's pixels
WORD_JOINER = "\u2060"


def mm_to_css_px(mm: float) -> int:
    """Millimetres as CSS px (1/96 inch), the unit of an ``<img>`` width."""
    return round(mm / 25.4 * 96)


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def page_writer(device: Any) -> QPdfWriter:
    """A writer on ``device`` (a file name or a QIODevice) with the report's page: A4
    portrait, 10 mm margins, 300 dpi."""
    writer = QPdfWriter(device)
    writer.setResolution(PDF_RESOLUTION)
    writer.setPageLayout(
        QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM),
            QPageLayout.Unit.Millimeter,
        )
    )
    return writer


class _Meter:
    """Text widths in the writer's own pixels, in the document's font, so that a column can be
    given the room its words need before the document is laid out."""

    def __init__(self) -> None:
        self._buffer = QBuffer()  # the writer's device; nothing is ever written to it
        self._buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        self._writer = page_writer(self._buffer)
        self.text_width = float(self._writer.width() - 2 * DOCUMENT_MARGIN_PX)
        self.px_per_css_px = PDF_RESOLUTION / 96
        self._metrics: dict[tuple[float, bool], QFontMetricsF] = {}
        self._widths: dict[tuple[str, float, bool], float] = {}

    def width(self, text: str, pt: float, *, bold: bool = False) -> float:
        key = (text, pt, bold)
        if key not in self._widths:
            if (pt, bold) not in self._metrics:
                font = QFont(FONT_FAMILY)
                font.setPointSizeF(pt)
                font.setBold(bold)
                self._metrics[(pt, bold)] = QFontMetricsF(font, self._writer)
            self._widths[key] = self._metrics[(pt, bold)].horizontalAdvance(text)
        return self._widths[key]


def _two_line_width(label: str, meter: _Meter, pt: float) -> float:
    """The width of ``label`` (bold) on the two lines that make the wider one narrowest."""
    words = label.split()
    splits = [
        max(meter.width(" ".join(words[:i]), pt, bold=True), meter.width(" ".join(words[i:]), pt, bold=True))
        for i in range(1, len(words))
    ]
    return min(splits, default=meter.width(label, pt, bold=True))


def _column_widths(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    meter: _Meter,
    pt: float,
    *,
    bold_first: bool = False,
) -> list[float] | None:
    """Each column's width as a percentage of the table, or ``None`` if the columns cannot all
    have room for their longest word at ``pt``.

    A column needs its longest word (a header word is bold, a bold-first column's cells too)
    plus the cell's padding and a little slack; it would like the whole of its widest cell on one
    line, and its header on two lines at most. The room left over after every need goes to the
    columns in proportion to what they would like beyond it, and if everything fits with room to
    spare the columns are scaled up to fill the table."""
    extra = (CELL_EXTRA_CSS_PX + WORD_SLACK_CSS_PX) * meter.px_per_css_px
    need: list[float] = []
    want: list[float] = []
    for c, label in enumerate(header):
        bold_cells = bold_first and c == 0
        longest_word = max((meter.width(w, pt, bold=True) for w in label.split()), default=0.0)
        widest_cell = _two_line_width(label, meter, pt)
        for row in rows:
            text = row[c]
            widest_cell = max(widest_cell, meter.width(text, pt, bold=bold_cells))
            longest_word = max(
                longest_word, max((meter.width(w, pt, bold=bold_cells) for w in text.split()), default=0.0)
            )
        need.append(longest_word + extra)
        want.append(max(longest_word, widest_cell) + extra)
    if sum(need) > meter.text_width:
        return None
    spare = meter.text_width - sum(need)
    beyond = [w - n for w, n in zip(want, need, strict=True)]
    if sum(beyond) > spare:  # the wishes do not all fit: share what is left by wish
        share = spare / sum(beyond)
        widths = [n + b * share for n, b in zip(need, beyond, strict=True)]
    else:  # everything fits: fill the table in proportion to the wishes
        widths = [w * meter.text_width / sum(want) for w in want]
    return [100.0 * w / meter.text_width for w in widths]


def _unbreakable(label: str) -> str:
    """``label`` with a word joiner after every "/" and "-": Qt also breaks a line there, so a
    header such as "Mean peak vel. (deg/s)" was cut as "(deg/" and "s)" when the column was a
    little too narrow for the whole of it. With the joiner a header wraps only at its spaces."""
    return label.replace("/", "/" + WORD_JOINER).replace("-", "-" + WORD_JOINER)


def _table(
    header: list[str],
    rows: list[list[str]],
    aligns: list[str],
    *,
    bold_first: bool = False,
    grey_rows: frozenset[int] = frozenset(),
    first_width: str | None = None,
    font_pt: float | None = None,
    widths: Sequence[float] | None = None,
) -> str:
    """A bordered table with ``aligns`` per column. The header is a ``<thead>`` row,
    which Qt repeats on every page the table spans. ``first_width`` is the first column's
    width (``"30%"``), ``widths`` every column's (percent), ``font_pt`` a font size for the
    whole table."""
    if widths is not None:
        column_widths = [f' width="{w:.2f}%"' for w in widths]
    else:
        column_widths = [f' width="{first_width}"' if first_width else ""] + [""] * (len(header) - 1)
    head = "".join(
        f'<th bgcolor="{HEADER}" align="{align}"{width}>{_e(_unbreakable(h))}</th>'
        for h, align, width in zip(header, aligns, column_widths, strict=True)
    )
    body = []
    for n, cells in enumerate(rows):
        style = f' style="color:{TEXT_SECONDARY}"' if n in grey_rows else ""
        tds = "".join(
            f'<td align="{align}"{style}>{"<b>" + _e(text) + "</b>" if bold_first and i == 0 else _e(text)}</td>'
            for i, (text, align) in enumerate(zip(cells, aligns, strict=True))
        )
        body.append(f"<tr>{tds}</tr>")
    size = f"; font-size:{font_pt}pt" if font_pt else ""
    return (
        f'<table border="1" cellspacing="0" cellpadding="{CELL_PADDING_CSS_PX}" width="100%" '
        f'style="border-collapse:collapse; border-color:{BORDER_SUBTLE}{size}">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def _measured_table(
    header: Sequence[str],
    rows: list[list[str]],
    aligns: list[str],
    meter: _Meter,
    pt: float,
    *,
    steps_down: bool = False,
    **kw: Any,
) -> str:
    """:func:`_table` at ``pt`` with measured column widths when the table is wide enough to
    need them. With ``steps_down`` the font goes down by half a point until every column has
    room for its longest word (down to :data:`TRIAL_TABLE_MIN_PT`)."""
    if len(header) < WIDTH_FROM_COLUMNS or kw.get("first_width"):
        return _table(list(header), rows, aligns, font_pt=pt, **kw)
    bold_first = bool(kw.get("bold_first"))
    widths = _column_widths(header, rows, meter, pt, bold_first=bold_first)
    while widths is None and steps_down and pt - TRIAL_TABLE_STEP_PT >= TRIAL_TABLE_MIN_PT:
        pt -= TRIAL_TABLE_STEP_PT
        widths = _column_widths(header, rows, meter, pt, bold_first=bold_first)
    return _table(list(header), rows, aligns, font_pt=pt, widths=widths, **kw)


def _heading(text: str, *, top: int = HEADING_GAP_CSS_PX, extra_style: str = "") -> str:
    """A section heading: a paragraph with an explicit size and weight (see the module doc)."""
    return (
        f'<p style="{extra_style}font-size:{HEADING_PT}pt; font-weight:{HEADING_WEIGHT}; '
        f'margin-top:{top}px; margin-bottom:2px">{_e(text)}</p>'
    )


def _paragraph(inner: str, *, top: int = 0, bottom: int = BLOCK_GAP_CSS_PX, style: str = "") -> str:
    """A paragraph with explicit gaps (Qt's default is 12 px above and below)."""
    return f'<p style="{style}margin-top:{top}px; margin-bottom:{bottom}px">{inner}</p>'


def build_report_html(
    report: dict[str, Any],
    *,
    test_name: str,
    evaluator: str,
    notes: str,
    map_image: QImage | None,
) -> str:
    """The report as the HTML :class:`QTextDocument` prints. ``test_name``,
    ``evaluator`` and ``notes`` are the page's (edited) values, not the stored ones. ``map_image``
    is the page's (:meth:`ReportPage.export_pdf`): it has the Scanpath whenever gaze was recorded,
    so the legend beside it says what the scanpath is then."""
    session = report.get("session", {})
    config_name = session.get("config_name") or NOT_RECORDED
    meter = _Meter()

    title = f"Summary Results, {test_name}" if test_name else "Summary Results"
    header = (
        f'<p style="font-size:{TITLE_PT}pt; font-weight:{HEADING_WEIGHT}; margin:0">{_e(title)}</p>'
        + _paragraph(
            f'Subject: <b>{_e(session.get("subject") or NOT_RECORDED)}</b>'
            f', Test Date: <b>{_e(started_text(session.get("started_ns")))}</b>'
            f', Evaluator: <b>{_e(evaluator or NOT_RECORDED)}</b>',
            top=3,
        )
    )
    banner = "".join(
        f'<p style="background-color:{WARNING_SUBTLE}; margin-top:2px; margin-bottom:8px">{_e(line)}</p>'
        for line in banner_lines(report)
    )

    config = _table(
        ["Setting", "Value"],
        [[str(label), str(value)] for label, value in report.get("config", {}).get("rows", [])],
        ["left", "left"],
        first_width=CONFIG_LABEL_WIDTH,
    )
    notes_block = _heading("Notes") + _paragraph(_e(notes).replace(chr(10), "<br>") or NOT_RECORDED)
    configuration = (
        _heading("Test Configuration", top=0)
        + _paragraph(f"Configuration Name: <b>{_e(config_name)}</b>")
        + config
        + notes_block
    )

    follow = layout_kind(report) == FOLLOW
    summary_rows = summary_cells(report)
    summary = _measured_table(
        summary_header(report),
        summary_rows,
        summary_aligns(report),
        meter,
        BODY_PT,
        bold_first=summary_bold_first(report),
        first_width=FOLLOW_LABEL_WIDTH if follow else None,
    )
    eye = _table(["Metric", "Value"], [[a, b] for a, b in eye_rows(report)], ["left", "left"], first_width=CONFIG_LABEL_WIDTH)
    summary_block = (
        _paragraph(_e(task_sentence(report)), top=HEADING_GAP_CSS_PX, bottom=0)
        + _heading("Summary of Results")
        + summary
        + _paragraph(
            _e(summary_note(report)), top=BLOCK_GAP_CSS_PX, bottom=0, style=f"font-size:{NOTE_PT}pt; color:{TEXT_SECONDARY}; "
        )
    )
    eye_block = _heading("Eye Metrics") + eye

    # Page 1 ends with the Eye Metrics; the Target Map starts page 2.
    parts = [header, banner, configuration, summary_block, eye_block]
    if map_image is not None:
        width = mm_to_css_px(MAP_WIDTH_MM)
        note = report.get("map", {}).get("note")
        parts.append(
            _heading("Target Map", top=0, extra_style="page-break-before:always; ")
            + _paragraph(f'<img src="{png_data_uri(map_image)}" width="{width}">')
            + legend_html(
                width,
                entries=FOLLOW_LEGEND_ENTRIES if follow else LEGEND_ENTRIES,
                overlay_note=SCANPATH_NOTE if gaze_was_recorded(report) else "",
            )
            + (
                _paragraph(_e(note), top=BLOCK_GAP_CSS_PX, style=f"font-size:{NOTE_PT}pt; color:{TEXT_SECONDARY}; ")
                if note
                else ""
            )
        )

    trials = report.get("trials", [])
    rows = [[cell.text for cell in cells] for cells in trial_rows(report)]
    skipped = frozenset(n for n, trial in enumerate(trials) if trial.get("outcome") == "skipped")
    columns = trial_columns(report)
    parts.append(
        _heading("Trial-by-Trial Results")
        + _measured_table(
            columns,
            rows,
            ["left"] + trial_aligns(report)[1:],
            meter,
            TRIAL_TABLE_PT,
            steps_down=True,
            grey_rows=skipped,
        )
    )
    definitions = "".join(f"<li>{_e(text)}</li>" for text in definition_lines(report))
    parts.append(
        _heading("Definitions") + f'<ul style="font-size:{DEFINITIONS_PT}pt; color:{INK}">{definitions}</ul>'
    )
    cell_style = f"td, th {{ padding-top: {CELL_PADDING_V_CSS_PX}px; padding-bottom: {CELL_PADDING_V_CSS_PX}px; }}"
    return (
        f"<html><head><style>{cell_style}</style></head>"
        f'<body style="font-family:\'{FONT_FAMILY}\', sans-serif; font-size:{BODY_PT}pt; color:{INK}">'
        + "".join(parts)
        + "</body></html>"
    )


def laid_out_document(html: str, writer: QPdfWriter) -> QTextDocument:
    """``html`` as a document laid out in ``writer``'s own pixels, page by page, ready to print."""
    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(writer)  # lay out in the writer's own pixels
    doc.setHtml(html)
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
    return doc


def _write(path: Path, html: str, title: str) -> None:
    writer = page_writer(str(path))
    writer.setTitle(title)
    writer.setCreator("Peds Eye Gaze Assessment")
    doc = laid_out_document(html, writer)
    doc.print_(writer)
    del doc
    del writer  # closes the file, so it can be moved into place


def export_report_pdf(
    path: str | Path,
    report: dict[str, Any],
    *,
    test_name: str = "",
    evaluator: str = "",
    notes: str = "",
    map_image: QImage | None = None,
) -> Path:
    """Write the report to ``path`` and return it. The file is written beside it first
    and moved into place, so a failure (no such folder, a locked file) raises
    :class:`OSError` and leaves any earlier file as it was."""
    path = Path(path)
    html = build_report_html(
        report, test_name=test_name, evaluator=evaluator, notes=notes, map_image=map_image
    )
    part = path.with_name(path.name + ".part")
    try:
        _write(part, html, f"Report: {test_name}" if test_name else "Report")
        if not part.exists() or part.stat().st_size == 0:
            raise OSError(f"could not write {path}")
        os.replace(part, path)
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
    return path
