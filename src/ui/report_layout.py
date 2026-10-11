"""Which tables a per-test report shows (SPEC-input-selection-and-follow.md 4.5, A8;
SPEC-scene-cause-effect-task.md 4.9, W6). Qt-free.

One report has one of four layouts, and the page (:mod:`report_views`) and the PDF
(:mod:`report_pdf`) both ask this module, so the two can never disagree about a column:

* ``selection``: the Summary of Results table and the Trial-by-Trial table of a test with Dwell
  (and of an old Follow & Click folder, H10);
* ``switch``: the same, plus the **Clicks** and **Click errors** columns;
* ``follow``: Follow the Target's Metric / Value summary and its own Trial-by-Trial columns;
* ``choice``: Choice-making's summary (with its look-back columns), two more tables under it
  (by button side, while choosing) and its own Trial-by-Trial columns; the map is the Scene Map.

Every function takes the report dict and reads nothing but what :mod:`report_format`,
:mod:`report_format_follow` and :mod:`report_format_choice` already read.
"""

from __future__ import annotations

from typing import Any

from .report_format import (
    OUTCOME_LABELS,
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
from .report_format_choice import (
    CHOICE_DEFINITIONS,
    CHOICE_OUTCOME_LABELS,
    CHOICE_SUMMARY_ALIGNS,
    CHOICE_TRIAL_ALIGNS,
    ExtraTable,
    choice_block,
    choice_extra_tables,
    choice_footnote,
    choice_info,
    choice_summary_header,
    choice_summary_rows,
    choice_trial_cells,
    choice_trial_columns,
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

SELECTION, SWITCH, FOLLOW, CHOICE = "selection", "switch", "follow", "choice"


def layout_kind(report: dict[str, Any]) -> str:
    """``choice`` for a Choice-making report, ``follow`` for a Follow the Target report, ``switch``
    for a test selected by the switch, else ``selection``."""
    if choice_block(report) is not None:
        return CHOICE
    if follow_block(report) is not None:
        return FOLLOW
    return SWITCH if is_switch(report) else SELECTION


def summary_header(report: dict[str, Any]) -> tuple[str, ...]:
    kind = layout_kind(report)
    if kind == CHOICE:
        return choice_summary_header(report)
    return FOLLOW_SUMMARY_COLUMNS if kind == FOLLOW else summary_columns(report)


def summary_aligns(report: dict[str, Any]) -> list[str]:
    """``left`` / ``right`` / ``center`` per summary column."""
    header = summary_header(report)
    kind = layout_kind(report)
    if kind == FOLLOW:
        return ["left", "left"]
    if kind == CHOICE:
        return list(CHOICE_SUMMARY_ALIGNS)
    return ["left"] + ["right"] * (len(header) - 1)


def summary_cells(report: dict[str, Any]) -> list[list[str]]:
    kind = layout_kind(report)
    if kind == CHOICE:
        return choice_summary_rows(report)
    return follow_summary_rows(report) if kind == FOLLOW else summary_table(report)


def summary_bold_first(report: dict[str, Any]) -> bool:
    """The row labels of the Summary of Results are bold; a Metric / Value table's are not."""
    return layout_kind(report) != FOLLOW


def summary_note(report: dict[str, Any]) -> str:
    kind = layout_kind(report)
    if kind == CHOICE:
        return choice_footnote(report)
    return follow_footnote(report) if kind == FOLLOW else summary_footnote(report)


def summary_info(report: dict[str, Any]) -> str:
    """A line above the summary about how the test was made (Choice-making: the visual cue, a
    Mouse run); empty for every other layout."""
    return choice_info(report) if layout_kind(report) == CHOICE else ""


def summary_extra_tables(report: dict[str, Any]) -> list[ExtraTable]:
    """The tables under the Summary of Results (Choice-making: by button side, while choosing)."""
    return choice_extra_tables(report) if layout_kind(report) == CHOICE else []


def map_title(report: dict[str, Any]) -> str:
    """The heading of the Summary's map: the Scene Map replaces the Target Map (W6)."""
    return "Scene Map" if layout_kind(report) == CHOICE else "Target Map"


def targets_label(report: dict[str, Any]) -> str:
    """The first overlay switch of the map: the marks, or Choice-making's buttons and objects."""
    return "Buttons and objects" if layout_kind(report) == CHOICE else "Targets"


def outcome_label(report: dict[str, Any], outcome: str) -> str:
    """The word of an Outcome cell and badge: Choice-making's trials are Right or Modelled."""
    labels = CHOICE_OUTCOME_LABELS if layout_kind(report) == CHOICE else OUTCOME_LABELS
    return labels[outcome]


def trial_columns(report: dict[str, Any]) -> tuple[str, ...]:
    kind = layout_kind(report)
    if kind == CHOICE:
        return choice_trial_columns(report)
    if kind == FOLLOW:
        return FOLLOW_TRIAL_COLUMNS
    return SWITCH_TRIAL_COLUMNS if kind == SWITCH else TRIAL_COLUMNS


def trial_aligns(report: dict[str, Any]) -> list[str]:
    """``left`` / ``right`` / ``center`` per Trial-by-Trial column."""
    kind = layout_kind(report)
    if kind == CHOICE:
        return list(CHOICE_TRIAL_ALIGNS)
    if kind == FOLLOW:
        return follow_trial_aligns()
    return ["center", "right", "right", "left"] + ["right"] * (len(trial_columns(report)) - 4)


def trial_rows(report: dict[str, Any]) -> list[list[Cell]]:
    """The cells of every Trial-by-Trial row, in the report's trial order."""
    trials = report.get("trials", [])
    kind = layout_kind(report)
    if kind == CHOICE:
        return [choice_trial_cells(report, i) for i in range(len(trials))]
    if kind == FOLLOW:
        return [follow_trial_cells(report, i) for i in range(len(trials))]
    switch, gaze = kind == SWITCH, gaze_was_recorded(report)
    return [trial_cells(t, switch=switch, gaze_recorded=gaze) for t in trials]


def definition_lines(report: dict[str, Any]) -> tuple[str, ...]:
    """The PDF's footnotes: what each measure of this layout means."""
    kind = layout_kind(report)
    if kind == CHOICE:
        return CHOICE_DEFINITIONS
    return FOLLOW_DEFINITIONS if kind == FOLLOW else definitions(report)
