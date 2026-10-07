"""Print Report: the per-test report as an A4 **portrait** PDF
(SPEC-compass-task-flow.md 4D.8, U9, HD13; portrait since 7.1, V3).

A :class:`QTextDocument` filled from HTML and printed by a :class:`QPdfWriter` (both
in QtGui): no printer dialog, no QtPrintSupport. One column, stacked: the header, the
Test Configuration table, the Summary of Results, then the Target Map (Targets only, as
one PNG, with its symbol legend) and the Eye Metrics on a page of their own, the
Trial-by-Trial table with its header row repeated on every page, and the definitions of
the measures. The text is the page's own (:mod:`report_format`), so the printout and the
screen cannot disagree.

Units: the document lays out in the writer's own pixels (300 dpi) and the layout
scales every length written in CSS ``px`` (padding, margins, an image's width) by the
writer's dpi itself, so a ``px`` here is the usual 1/96 inch: a length is **not**
converted again (doing so made rows three times too tall). Fonts are in pt.
"""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPdfWriter, QTextDocument

from .map_legend import legend_html, png_data_uri
from .report_format import (
    DASH,
    DEFINITIONS,
    SUMMARY_COLUMNS,
    TRIAL_COLUMNS,
    banner_lines,
    eye_rows,
    started_text,
    summary_footnote,
    summary_table,
    task_sentence,
    trial_cells,
)
from .wtmh_theme import BORDER, INK, MUTED, SOFT_ACCENT, SOFT_ACCENT_TEXT, WARNING_BG

PDF_RESOLUTION = 300  # dpi of the writer
MARGIN_MM = 10.0
MAP_WIDTH_MM = 186.0  # of the 190 mm between the margins of an A4 portrait page (190 spills over)
BODY_PT = 8.5
TRIAL_TABLE_PT = 7.5  # thirteen columns across 190 mm: a size down keeps each cell on few lines
CONFIG_LABEL_WIDTH = "30%"  # the Setting column of the configuration table


def mm_to_css_px(mm: float) -> int:
    """Millimetres as CSS px (1/96 inch), the unit of an ``<img>`` width."""
    return round(mm / 25.4 * 96)


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _table(
    header: list[str],
    rows: list[list[str]],
    aligns: list[str],
    *,
    bold_first: bool = False,
    grey_rows: frozenset[int] = frozenset(),
    first_width: str | None = None,
    font_pt: float | None = None,
) -> str:
    """A bordered table with ``aligns`` per column. The header is a ``<thead>`` row,
    which Qt repeats on every page the table spans. ``first_width`` is the first column's
    width (``"30%"``), ``font_pt`` a font size for the whole table."""
    head = "".join(
        f'<th bgcolor="{SOFT_ACCENT}" align="{align}"{width}>'
        f'<span style="color:{SOFT_ACCENT_TEXT}">{_e(h)}</span></th>'
        for h, align, width in zip(
            header,
            aligns,
            [f' width="{first_width}"' if first_width else ""] + [""] * (len(header) - 1),
            strict=True,
        )
    )
    body = []
    for n, cells in enumerate(rows):
        style = f' style="color:{MUTED}"' if n in grey_rows else ""
        tds = "".join(
            f'<td align="{align}"{style}>{"<b>" + _e(text) + "</b>" if bold_first and i == 0 else _e(text)}</td>'
            for i, (text, align) in enumerate(zip(cells, aligns, strict=True))
        )
        body.append(f"<tr>{tds}</tr>")
    size = f"; font-size:{font_pt}pt" if font_pt else ""
    return (
        f'<table border="1" cellspacing="0" cellpadding="3" width="100%" '
        f'style="border-collapse:collapse; border-color:{BORDER}{size}">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def build_report_html(
    report: dict[str, Any],
    *,
    test_name: str,
    evaluator: str,
    notes: str,
    map_image: QImage | None,
) -> str:
    """The report as the HTML :class:`QTextDocument` prints. ``test_name``,
    ``evaluator`` and ``notes`` are the page's (edited) values, not the stored ones."""
    session = report.get("session", {})
    config_name = session.get("config_name") or DASH

    header = (
        f'<h2 style="margin:0">Summary Results: {_e(test_name or DASH)}</h2>'
        f'<p style="margin-top:3px">Subject: <b>{_e(session.get("subject") or DASH)}</b>'
        f' &nbsp;·&nbsp; Test Date: <b>{_e(started_text(session.get("started_ns")))}</b>'
        f' &nbsp;·&nbsp; Evaluator: <b>{_e(evaluator or DASH)}</b></p>'
    )
    banner = "".join(
        f'<p style="background-color:{WARNING_BG}; margin-top:2px; margin-bottom:8px">{_e(line)}</p>'
        for line in banner_lines(report)
    )

    config = _table(
        ["Setting", "Value"],
        [[str(label), str(value)] for label, value in report.get("config", {}).get("rows", [])],
        ["left", "left"],
        first_width=CONFIG_LABEL_WIDTH,
    )
    notes_block = (
        f'<h3 style="margin-bottom:2px">Notes</h3><p style="margin-top:0">{_e(notes).replace(chr(10), "<br>") or DASH}</p>'
    )
    configuration = (
        f'<h3 style="margin-top:0; margin-bottom:2px">Test Configuration</h3>'
        f'<p style="margin-top:0">Configuration Name: <b>{_e(config_name)}</b></p>{config}{notes_block}'
    )

    summary = _table(list(SUMMARY_COLUMNS), summary_table(report), ["left"] + ["right"] * 4, bold_first=True)
    eye = _table(["Metric", "Value"], [[a, b] for a, b in eye_rows(report)], ["left", "left"], first_width=CONFIG_LABEL_WIDTH)
    summary_block = (
        f'<p style="margin-bottom:2px">{_e(task_sentence(report))}</p>'
        f'<h3 style="margin-bottom:2px">Summary of Results</h3>{summary}'
        f'<p style="font-size:{BODY_PT - 1}pt; color:{MUTED}">{_e(summary_footnote(report))}</p>'
    )
    eye_block = f'<h3 style="margin-bottom:2px">Eye Metrics</h3>{eye}'

    parts = [header, banner, configuration, summary_block]
    if map_image is not None:
        width = mm_to_css_px(MAP_WIDTH_MM)
        note = report.get("map", {}).get("note")
        parts.append(
            f'<h3 style="page-break-before:always; margin-top:0; margin-bottom:2px">Target Map</h3>'
            f'<p style="margin-top:0; margin-bottom:4px"><img src="{png_data_uri(map_image)}" width="{width}"></p>'
            f'{legend_html(width)}'
            + (f'<p style="font-size:{BODY_PT - 1}pt; color:{MUTED}">{_e(note)}</p>' if note else "")
        )
    parts.append(eye_block)

    trials = report.get("trials", [])
    rows = [[cell.text for cell in trial_cells(trial)] for trial in trials]
    skipped = frozenset(n for n, trial in enumerate(trials) if trial.get("outcome") == "skipped")
    aligns = ["left", "right", "right", "left"] + ["right"] * (len(TRIAL_COLUMNS) - 4)
    parts.append(
        '<h3 style="margin-bottom:2px">Trial-by-Trial Results</h3>'
        + _table(list(TRIAL_COLUMNS), rows, aligns, grey_rows=skipped, font_pt=TRIAL_TABLE_PT)
    )
    definitions = "".join(f"<li>{_e(text)}</li>" for text in DEFINITIONS)
    parts.append(
        f'<h3 style="margin-bottom:2px">Definitions</h3>'
        f'<ul style="font-size:{BODY_PT - 1}pt; color:{INK}">{definitions}</ul>'
    )
    return (
        f'<html><body style="font-family:\'Segoe UI\', sans-serif; font-size:{BODY_PT}pt; color:{INK}">'
        + "".join(parts)
        + "</body></html>"
    )


def _write(path: Path, html: str, title: str) -> None:
    writer = QPdfWriter(str(path))
    writer.setResolution(PDF_RESOLUTION)
    writer.setPageLayout(
        QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM),
            QPageLayout.Unit.Millimeter,
        )
    )
    writer.setTitle(title)
    writer.setCreator("Peds Eye Gaze Assessment")
    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(writer)  # lay out in the writer's own pixels
    doc.setHtml(html)
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
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
