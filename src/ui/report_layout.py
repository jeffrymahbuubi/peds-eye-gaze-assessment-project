"""Which tables a per-test report shows (SPEC-input-selection-and-follow.md 4.5, A8). Qt-free.

One report has one of three layouts, and the page (:mod:`report_views`) and the PDF
(:mod:`report_pdf`) both ask this module, so the two can never disagree about a column:

* ``selection``: the Summary of Results table and the Trial-by-Trial table of a test with Dwell
  (and of an old Follow & Click folder, H10);
* ``switch``: the same, plus the **Clicks** and **Click errors** columns;
* ``follow``: Follow the Target's Metric / Value summary and its own Trial-by-Trial columns.

Every function takes the report dict and reads nothing but what :mod:`report_format` and
:mod:`report_format_follow` already read.
"""

from __future__ import annotations

from typing import Any

from .report_format import (
    SWITCH_TRIAL_COLUMNS,
    TRIAL_COLUMNS,
    Cell,
    definitions,
    gaze_was_recorded,
    is_switch,
    summary_columns,
    summary_footnote,
    summary_table,
    trial_cells,
)
from .report_format_follow import (
    FOLLOW_DEFINITIONS,
    FOLLOW_SUMMARY_COLUMNS,
    FOLLOW_TRIAL_COLUMNS,
    follow_block,
    follow_footnote,
    follow_summary_rows,
    follow_trial_aligns,
    follow_trial_cells,
)

SELECTION, SWITCH, FOLLOW = "selection", "switch", "follow"


def layout_kind(report: dict[str, Any]) -> str:
    """``follow`` for a Follow the Target report, ``switch`` for a test selected by the switch,
    else ``selection``."""
    if follow_block(report) is not None:
        return FOLLOW
    return SWITCH if is_switch(report) else SELECTION


def summary_header(report: dict[str, Any]) -> tuple[str, ...]:
    return FOLLOW_SUMMARY_COLUMNS if layout_kind(report) == FOLLOW else summary_columns(report)


def summary_aligns(report: dict[str, Any]) -> list[str]:
    """``left`` / ``right`` / ``center`` per summary column."""
    header = summary_header(report)
    if layout_kind(report) == FOLLOW:
        return ["left", "left"]
    return ["left"] + ["right"] * (len(header) - 1)


def summary_cells(report: dict[str, Any]) -> list[list[str]]:
    return follow_summary_rows(report) if layout_kind(report) == FOLLOW else summary_table(report)


def summary_bold_first(report: dict[str, Any]) -> bool:
    """The row labels of the Summary of Results are bold; a Metric / Value table's are not."""
    return layout_kind(report) != FOLLOW


def summary_note(report: dict[str, Any]) -> str:
    return follow_footnote(report) if layout_kind(report) == FOLLOW else summary_footnote(report)


def trial_columns(report: dict[str, Any]) -> tuple[str, ...]:
    kind = layout_kind(report)
    if kind == FOLLOW:
        return FOLLOW_TRIAL_COLUMNS
    return SWITCH_TRIAL_COLUMNS if kind == SWITCH else TRIAL_COLUMNS


def trial_aligns(report: dict[str, Any]) -> list[str]:
    """``left`` / ``right`` / ``center`` per Trial-by-Trial column."""
    if layout_kind(report) == FOLLOW:
        return follow_trial_aligns()
    return ["center", "right", "right", "left"] + ["right"] * (len(trial_columns(report)) - 4)


def trial_rows(report: dict[str, Any]) -> list[list[Cell]]:
    """The cells of every Trial-by-Trial row, in the report's trial order."""
    trials = report.get("trials", [])
    if layout_kind(report) == FOLLOW:
        return [follow_trial_cells(report, i) for i in range(len(trials))]
    switch, gaze = layout_kind(report) == SWITCH, gaze_was_recorded(report)
    return [trial_cells(t, switch=switch, gaze_recorded=gaze) for t in trials]


def definition_lines(report: dict[str, Any]) -> tuple[str, ...]:
    """The PDF's footnotes: what each measure of this layout means."""
    return FOLLOW_DEFINITIONS if layout_kind(report) == FOLLOW else definitions(report)

