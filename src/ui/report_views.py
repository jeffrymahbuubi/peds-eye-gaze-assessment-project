"""The two right-hand views of the report page (SPEC-compass-task-flow.md 4D.2, 4D.7;
wireframes ``report-summary.md`` / ``report-detailed.md``).

:class:`SummaryView`: the task sentence, the Summary of Results table and its
footnote, the Target Map with its Targets / Scanpath / Heat map switches and its symbol
legend, and the whole-test Eye Metrics table (320 + 320 px, the whole view at most 1100 px wide).
:class:`DetailedView`: the selected trial's 720 x 405 px map, then the Trial-by-Trial table below it at
the full width (first column frozen, every column sortable, the Outcome column as status badges,
two-line headers so the 13 columns fit; the pane scrolls, the table keeps room for eight rows)
(SPEC-design-system-phase4.md H6, H7 and the user's answer of 2026-10-09).

Both are scroll areas that only **show** a report: every figure is formatted by
:mod:`report_format` and drawn by :class:`~src.ui.target_map.TargetMapWidget`; nothing is
recomputed and nothing here is editable.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import TEXT_SECONDARY
from .frozen_table import FrozenColumnTable, two_lines
from .map_legend import (
    FOLLOW_LEGEND_ENTRIES,
    LEGEND_ENTRIES,
    NUMBERS_NOTE,
    POINTER_LEGEND_ENTRIES,
    POINTER_NUMBERS_NOTE,
    SCANPATH_NOTE,
    MapLegend,
)
from .report_format import (
    EYE_NOTE,
    OUTCOME_LABELS,
    SUMMARY_COLUMNS,
    TRIAL_COLUMNS,
    eye_rows,
    gaze_was_recorded,
    task_sentence,
    trial_line,
)
from .report_layout import (
    FOLLOW,
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
from .report_tables import FitTable
from .target_map import TargetMapWidget

MAP_MAX_WIDTH = 880  # the Summary's map, so a wide window does not make it enormous
SUMMARY_MAX_WIDTH = 1100  # the Summary's whole main column (the sidebar keeps 460)
EYE_COLUMN_WIDTHS = (320, 320)  # the Eye Metrics table: Metric, Value
SELECTED_MAP_SIZE = (720, 405)  # the Detailed view's map of the selected trial
TABLE_MIN_ROWS = 8  # the Detailed table is never squeezed below this many rows (the pane scrolls)
# The badge of an Outcome cell (SPEC-design-system-phase4.md H7): the glyph and colour of a
# status badge kind, with the report's own word ("Hit", "Not selected", ...).
OUTCOME_KINDS = {
    "hit": "done",
    "followed": "done",
    "timeout": "disconnected",
    "not_followed": "disconnected",
    "skipped": "skipped",
}
OUTCOME_COLUMN = "Outcome"  # its header, in every layout

# A run that did not record the monitor's physical size (an old folder): the path is thinned
# and the heat map blurred in degrees of an assumed monitor (4D.5; geometry.assumed_for_visuals).
ASSUMED_GEOMETRY_NOTE = (
    "This run did not record the monitor's size, so the gaze path and heat map assume a standard monitor."
)
# The sentence under the selected trial's map, as two caption lines.
TRIAL_LEGEND = (
    "S = gaze when the target appeared, star = gaze at the selection, numbered circles = "
    "fixations (bigger = longer).\n"
    "The path (smoothed like the on-screen gaze cursor) runs dark to light with time, "
    "dashed ring = target area."
)
# Follow the Target: nothing is selected, and the pointer path is split by the target's area.
FOLLOW_TRIAL_LEGEND = (
    "S = pointer when the target appeared, numbered circles = fixations (bigger = longer), "
    "faint line = the path of the target, dashed ring = target area.\n"
    "The pointer path (smoothed like the on-screen cursor) is solid dark blue where the pointer was on the "
    "target and dashed grey where it was off it."
)
NOT_RECORDED_SUFFIX = "not recorded"  # on the Scanpath and Heat map switches of a test with no gaze

_ALIGN = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "right": Qt.AlignmentFlag.AlignRight,
    "center": Qt.AlignmentFlag.AlignHCenter,
}

# The scroll areas are transparent over the page's tint (the theme's rules cover its own
# scroll-area names only).
SCROLL_STYLE = """
QScrollArea#reportScroll, QScrollArea#reportScroll > QWidget { background: transparent; border: none; }
"""


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("wtmhSectionTitle")
    return label


def muted_label(text: str = "") -> QLabel:
    """A wrapped, muted, **plain-text** line (some of what it shows is typed by the operator)."""
    label = QLabel(text)
    label.setObjectName("wtmhMuted")
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def caption_label(text: str = "") -> QLabel:
    """A wrapped **plain-text** caption (the type scale's smallest step, in text-secondary)."""
    label = QLabel(text)
    label.setObjectName("wtmhCaption")
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def setup_scroll(area: QScrollArea, content: QWidget) -> None:
    """Make ``area`` a transparent, vertically scrolling frame around ``content`` (both
    autofills cleared, SPEC S22.5: setWidget() would otherwise paint black bands)."""
    area.setObjectName("reportScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(content)
    area.viewport().setAutoFillBackground(False)
    content.setAutoFillBackground(False)


def scroll_area(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    setup_scroll(area, content)
    return area


class SummaryView(QScrollArea):
    """Summary of Results, Target Map and Eye Metrics of one report.

    The table is the report's layout (:mod:`report_layout`): the four selection rows (with the
    Clicks columns for a Switch test) or Follow the Target's Metric / Value rows; the legend
    names the marks of that task. A test with no gaze recorded cannot draw the Scanpath or the
    Heat map: their switches are off and say so."""

    SCANPATH, HEAT = "Scanpath", "Heat map"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)
        self.task_label = QLabel("")
        self.task_label.setWordWrap(True)
        layout.addWidget(self.task_label)
        layout.addWidget(section_title("Summary of Results"))
        self.table = FitTable(SUMMARY_COLUMNS, stretch_column=0)
        layout.addWidget(self.table)
        self.note = muted_label()
        layout.addWidget(self.note)

        layout.addWidget(section_title("Target Map"))
        switches = QHBoxLayout()
        self.targets_check = QCheckBox("Targets")
        self.targets_check.setChecked(True)
        self.path_check = QCheckBox(self.SCANPATH)  # a dot per fixation, joined in time order (V2)
        self.heat_check = QCheckBox(self.HEAT)
        for check in (self.targets_check, self.path_check, self.heat_check):
            check.toggled.connect(self._on_overlays)
            switches.addWidget(check)
        switches.addStretch(1)
        layout.addLayout(switches)
        self.map = TargetMapWidget()
        self.map.set_fit_to_width(True)
        self.map.setMaximumWidth(MAP_MAX_WIDTH)
        layout.addWidget(self.map)  # no alignment: it takes up to its maximum width
        self.legend = MapLegend()
        self.legend.setMaximumWidth(MAP_MAX_WIDTH)  # as wide as the map above it, no wider
        layout.addWidget(self.legend)
        self.map_note = muted_label()
        layout.addWidget(self.map_note)

        layout.addWidget(section_title("Eye Metrics"))
        self.eye_table = FitTable(["Metric", "Value"], stretch_column=1, column_widths=EYE_COLUMN_WIDTHS)
        layout.addWidget(self.eye_table)
        layout.addWidget(muted_label(EYE_NOTE))
        layout.addStretch(1)
        setup_scroll(self, content)
        self.setMaximumWidth(SUMMARY_MAX_WIDTH)

    def set_report(self, report: dict[str, Any]) -> None:
        self.task_label.setText(task_sentence(report))
        follow = layout_kind(report) == FOLLOW
        self.table.set_header(summary_header(report), stretch_column=1 if follow else 0)
        self.table.set_rows(
            summary_cells(report),
            aligns=[_ALIGN[a] for a in summary_aligns(report)],
            bold_first=summary_bold_first(report),
        )
        self.note.setText(summary_note(report))
        recorded = gaze_was_recorded(report)
        self.legend.set_entries(
            FOLLOW_LEGEND_ENTRIES if follow else LEGEND_ENTRIES,
            NUMBERS_NOTE,
            SCANPATH_NOTE if recorded else "",  # no gaze, no Scanpath to explain
        )
        self._set_gaze_switches(recorded)
        self.eye_table.set_rows([list(row) for row in eye_rows(report)])
        self.map.set_report(report)
        notes = [self.map.note] if self.map.note else []
        if report.get("geometry", {}).get("assumed_for_visuals"):
            notes.append(ASSUMED_GEOMETRY_NOTE)
        self.map_note.setText(" ".join(notes))
        self.map_note.setVisible(bool(notes))
        self._on_overlays()

    def _set_gaze_switches(self, recorded: bool) -> None:
        """Scanpath and Heat map need gaze: without it they are off, disabled and say "not recorded"."""
        for check, label in ((self.path_check, self.SCANPATH), (self.heat_check, self.HEAT)):
            check.setEnabled(recorded)
            check.setText(label if recorded else f"{label} ({NOT_RECORDED_SUFFIX})")
            if not recorded:
                check.setChecked(False)

    def _on_overlays(self, *_args: object) -> None:
        self.map.set_overlays(
            targets=self.targets_check.isChecked(),
            path=self.path_check.isChecked(),
            heat=self.heat_check.isChecked(),
        )


class DetailedView(QScrollArea):
    """The selected trial's map and, below it, the Trial-by-Trial table.

    Rows are selected one at a time (the first when a report is set); the map and the
    line under it follow. A click on a column header sorts by it (again to reverse), a
    column's dash cells always last; the selected trial stays selected wherever it moves.
    The Outcome column shows a status badge over each cell's text (the text is what sorts).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report: dict[str, Any] = {}
        self._sort: tuple[int, Qt.SortOrder] = (-1, Qt.SortOrder.AscendingOrder)
        self._indexes: list[int] = []  # report trial index of each table row, as shown
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)
        self._cells: list[list[Any]] = []  # the cells of each report trial, in the report's order
        self._aligns: list[str] = []
        self.selected_title = section_title("Selected trial")
        layout.addWidget(self.selected_title)
        self.map = TargetMapWidget()
        self.map.setFixedSize(*SELECTED_MAP_SIZE)
        layout.addWidget(self.map, 0, Qt.AlignmentFlag.AlignLeft)
        self.line_label = QLabel("")
        layout.addWidget(self.line_label)
        # Follow the Target only: what the dark and the light stretches of the pointer path mean.
        self.legend = MapLegend()
        self.legend.set_entries(POINTER_LEGEND_ENTRIES, POINTER_NUMBERS_NOTE)
        self.legend.setMaximumWidth(MAP_MAX_WIDTH)
        self.legend.setVisible(False)
        layout.addWidget(self.legend)
        self.trial_legend = caption_label(TRIAL_LEGEND)
        layout.addWidget(self.trial_legend)
        layout.addWidget(section_title("Trial-by-Trial Results"))
        self.table = FrozenColumnTable([two_lines(c) for c in TRIAL_COLUMNS])
        self.table.set_minimum_rows(TABLE_MIN_ROWS)
        layout.addWidget(self.table, stretch=1)
        setup_scroll(self, content)
        self.table.sortRequested.connect(self._on_sort)
        self.table.currentCellChanged.connect(self._on_current_changed)

    def set_report(self, report: dict[str, Any]) -> None:
        """Show ``report``'s trials unsorted with the first selected."""
        self._report = report
        self._sort = (-1, Qt.SortOrder.AscendingOrder)
        self.table.set_sort_indicator(-1, Qt.SortOrder.AscendingOrder)
        columns = trial_columns(report)
        self.table.set_columns([two_lines(c) for c in columns])
        self.table.set_badge_column(columns.index(OUTCOME_COLUMN) if OUTCOME_COLUMN in columns else None)
        self._aligns = trial_aligns(report)
        self._cells = trial_rows(report)
        follow = layout_kind(report) == FOLLOW
        self.legend.setVisible(follow)
        self.trial_legend.setText(FOLLOW_TRIAL_LEGEND if follow else TRIAL_LEGEND)
        self.map.set_report(report)
        self._fill(select=0)

    def selected_trial(self) -> int | None:
        """The report trial index of the selected row (``None`` if none)."""
        row = self.table.currentRow()
        return self._indexes[row] if 0 <= row < len(self._indexes) else None

    def _fill(self, *, select: int | None) -> None:
        """Rebuild the rows in the current sort order and select the one for report trial
        ``select`` (an index into ``trials``), if any."""
        trials = self._report.get("trials", [])
        rows = [(i, self._cells[i], t) for i, t in enumerate(trials)]
        column, order = self._sort
        if column >= 0:
            have = [r for r in rows if r[1][column].key is not None]
            missing = [r for r in rows if r[1][column].key is None]  # always last
            have.sort(key=lambda r: r[1][column].key, reverse=order == Qt.SortOrder.DescendingOrder)
            rows = have + missing
        table = self.table
        blocked = table.blockSignals(True)
        try:
            table.clear_badges()
            table.setRowCount(len(rows))
            self._indexes = [r[0] for r in rows]
            for r, (_, cells, trial) in enumerate(rows):
                outcome = trial.get("outcome")
                skipped = outcome == "skipped"
                for c, cell in enumerate(cells):
                    item = QTableWidgetItem(cell.text)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setTextAlignment(_ALIGN[self._aligns[c]] | Qt.AlignmentFlag.AlignVCenter)
                    if skipped:
                        item.setForeground(QColor(TEXT_SECONDARY))
                    table.setItem(r, c, item)
                if outcome in OUTCOME_KINDS:
                    table.set_badge(r, OUTCOME_KINDS[outcome], OUTCOME_LABELS[outcome])
            table.fit_columns()
            target = self._indexes.index(select) if select in self._indexes else -1
            if target >= 0:
                table.setCurrentCell(target, 0)
                table.selectRow(target)
            else:
                table.clearSelection()
        finally:
            table.blockSignals(blocked)
        self._show(self.selected_trial())

    def _show(self, index: int | None) -> None:
        trials = self._report.get("trials", [])
        if index is None or not 0 <= index < len(trials):
            self.map.set_trial(None)
            self.selected_title.setText("Selected trial")
            self.line_label.setText("")
            return
        trial = trials[index]
        self.map.set_trial(index)
        self.selected_title.setText(f"Selected trial: Trial {trial.get('trial', '')}")
        self.line_label.setText(trial_line(trial, gaze_was_recorded(self._report)))

    def _on_sort(self, column: int) -> None:
        current, order = self._sort
        if column == current:
            order = (
                Qt.SortOrder.DescendingOrder
                if order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.AscendingOrder
        self._sort = (column, order)
        self.table.set_sort_indicator(column, order)
        self._fill(select=self.selected_trial())

    def _on_current_changed(self, row: int, _column: int, _prev_row: int, _prev_col: int) -> None:
        if 0 <= row < len(self._indexes):
            self._show(self._indexes[row])
