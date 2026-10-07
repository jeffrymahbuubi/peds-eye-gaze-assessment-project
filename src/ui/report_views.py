"""The two right-hand views of the report page (SPEC-compass-task-flow.md 4D.2, 4D.7;
wireframes ``report-summary.md`` / ``report-detailed.md``).

:class:`SummaryView`: the task sentence, the Summary of Results table and its
footnote, the Target Map with its Targets / Scanpath / Heat map switches and its symbol
legend, and the whole-test Eye Metrics table. :class:`DetailedView`: the Trial-by-Trial table (first
column frozen, every column sortable) above the selected trial's map.

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

from .frozen_table import FrozenColumnTable
from .map_legend import MapLegend
from .report_format import (
    EYE_NOTE,
    SUMMARY_COLUMNS,
    TASK_SENTENCES,
    TRIAL_COLUMNS,
    eye_rows,
    summary_footnote,
    summary_table,
    trial_cells,
    trial_line,
)
from .report_tables import FitTable
from .target_map import TargetMapWidget
from .wtmh_theme import MUTED

MAP_MAX_WIDTH = 880  # the Summary's map, so a wide window does not make it enormous

# A run that did not record the monitor's physical size (an old folder): the path is thinned
# and the heat map blurred in degrees of an assumed monitor (4D.5; geometry.assumed_for_visuals).
ASSUMED_GEOMETRY_NOTE = (
    "This run did not record the monitor's size, so the gaze path and heat map assume a standard monitor."
)
TRIAL_LEGEND = (
    "S = gaze when the target appeared · star = gaze at the selection · numbered circles = "
    "fixations (bigger = longer) · the path (smoothed like the on-screen gaze cursor) runs dark "
    "to light with time · dashed ring = target area."
)

_RIGHT = Qt.AlignmentFlag.AlignRight
_LEFT = Qt.AlignmentFlag.AlignLeft
_CENTER = Qt.AlignmentFlag.AlignHCenter
_SUMMARY_ALIGNS = [_LEFT] + [_RIGHT] * 4
_TRIAL_ALIGNS = [_CENTER, _RIGHT, _RIGHT, _LEFT] + [_RIGHT] * (len(TRIAL_COLUMNS) - 4)

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
    """Summary of Results, Target Map and Eye Metrics of one report."""

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
        self.path_check = QCheckBox("Scanpath")  # a dot per fixation, joined in time order (V2)
        self.heat_check = QCheckBox("Heat map")
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
        self.eye_table = FitTable(["Metric", "Value"], stretch_column=1)
        layout.addWidget(self.eye_table)
        layout.addWidget(muted_label(EYE_NOTE))
        layout.addStretch(1)
        setup_scroll(self, content)

    def set_report(self, report: dict[str, Any]) -> None:
        self.task_label.setText(TASK_SENTENCES.get(report.get("session", {}).get("task_id"), ""))
        self.table.set_rows(summary_table(report), aligns=_SUMMARY_ALIGNS, bold_first=True)
        self.note.setText(summary_footnote(report))
        self.eye_table.set_rows([list(row) for row in eye_rows(report)])
        self.map.set_report(report)
        notes = [self.map.note] if self.map.note else []
        if report.get("geometry", {}).get("assumed_for_visuals"):
            notes.append(ASSUMED_GEOMETRY_NOTE)
        self.map_note.setText(" ".join(notes))
        self.map_note.setVisible(bool(notes))
        self._on_overlays()

    def _on_overlays(self, *_args: object) -> None:
        self.map.set_overlays(
            targets=self.targets_check.isChecked(),
            path=self.path_check.isChecked(),
            heat=self.heat_check.isChecked(),
        )


class DetailedView(QScrollArea):
    """The Trial-by-Trial table and the selected trial's map.

    Rows are selected one at a time (the first when a report is set); the map and the
    line under it follow. A click on a column header sorts by it (again to reverse), a
    column's "—" cells always last; the selected trial stays selected wherever it moves.
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
        layout.addWidget(section_title("Trial-by-Trial Results"))
        self.table = FrozenColumnTable(TRIAL_COLUMNS)
        self.table.setMinimumHeight(200)
        layout.addWidget(self.table, stretch=11)
        self.selected_title = section_title("Selected trial")
        layout.addWidget(self.selected_title)
        self.map = TargetMapWidget()
        self.map.setMinimumHeight(220)
        layout.addWidget(self.map, stretch=9)
        self.line_label = QLabel("")
        layout.addWidget(self.line_label)
        layout.addWidget(muted_label(TRIAL_LEGEND))
        setup_scroll(self, content)
        self.table.sortRequested.connect(self._on_sort)
        self.table.currentCellChanged.connect(self._on_current_changed)

    def set_report(self, report: dict[str, Any]) -> None:
        """Show ``report``'s trials unsorted with the first selected."""
        self._report = report
        self._sort = (-1, Qt.SortOrder.AscendingOrder)
        self.table.set_sort_indicator(-1, Qt.SortOrder.AscendingOrder)
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
        rows = [(i, trial_cells(t), t) for i, t in enumerate(trials)]
        column, order = self._sort
        if column >= 0:
            have = [r for r in rows if r[1][column].key is not None]
            missing = [r for r in rows if r[1][column].key is None]  # always last
            have.sort(key=lambda r: r[1][column].key, reverse=order == Qt.SortOrder.DescendingOrder)
            rows = have + missing
        table = self.table
        blocked = table.blockSignals(True)
        try:
            table.setRowCount(len(rows))
            self._indexes = [r[0] for r in rows]
            for r, (_, cells, trial) in enumerate(rows):
                skipped = trial.get("outcome") == "skipped"
                for c, cell in enumerate(cells):
                    item = QTableWidgetItem(cell.text)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setTextAlignment(_TRIAL_ALIGNS[c] | Qt.AlignmentFlag.AlignVCenter)
                    if skipped:
                        item.setForeground(QColor(MUTED))
                    table.setItem(r, c, item)
            table.resizeColumnsToContents()
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
        self.selected_title.setText(f"Selected trial — Trial {trial.get('trial', '')}")
        self.line_label.setText(trial_line(trial))

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
