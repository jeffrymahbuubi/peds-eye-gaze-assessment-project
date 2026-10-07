"""The per-test report page, Summary and Detailed (SPEC-compass-task-flow.md 4D.2,
4D.3, 4D.7, 4D.8; wireframes ``report-summary.md`` / ``report-detailed.md``).

One page for one finished test, built from its ``report.json``
(:func:`~src.data.report_cache.load_or_build_report`): nothing is recomputed here,
every figure is formatted by :mod:`report_format`. The header has the editable Test
Name and Evaluator, the left column the Test Configuration and the editable Notes
(both views), and the right column either :class:`~src.ui.report_views.SummaryView`
or :class:`~src.ui.report_views.DetailedView`. The run's own numbers are never
editable.

The page only **emits signals**: ``saved(name, evaluator, notes)`` (the host writes
them to the test record and returns to the Test List) and ``cancelRequested`` (the
edits are dropped). Print Report writes a PDF itself (:mod:`report_pdf`); the host
only tells it where to start (``set_context(pdf_dir=...)``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from html import escape
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine.subject_test_record import validate_test_name
from .report_format import DASH, banner_lines, pdf_default_name, started_text
from .report_pdf import export_report_pdf
from .report_tables import FitTable
from .report_views import (
    SCROLL_STYLE,
    DetailedView,
    SummaryView,
    muted_label,
    scroll_area,
    section_title,
)

_log = logging.getLogger(__name__)

SUMMARY, DETAILED = "summary", "detailed"
SIDEBAR_WIDTH = 460
PDF_MAP_WIDTH_PX = 1800


def _button(text: str, tier: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(tier)
    button.setAutoDefault(False)  # Enter never saves
    return button


class ReportPage(QWidget):
    """The report of one test. Fill it with :meth:`set_report`."""

    saved = Signal(str, str, str)  # Test Name, Evaluator, Notes: the host writes them
    cancelRequested = Signal()
    pdfExported = Signal(str)  # the path of the PDF Print Report wrote

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(SCROLL_STYLE)
        self._report: dict[str, Any] = {}
        self._view = SUMMARY
        self._existing_names: list[str] = []
        self._own_name = ""
        self._pdf_dir = ""
        self._baseline: tuple[str, str, str] = ("", "", "")
        self._note = ""
        self._loading = False
        # Where Print Report asks for the file; a test (or the host) may replace it.
        self.choose_pdf_path: Callable[[str], str] = self._ask_pdf_path
        self._build_ui()
        self._connect()
        self._refresh_footer()

    # -- public API -------------------------------------------------------------

    def set_report(
        self,
        report: dict[str, Any],
        *,
        test_name: str | None = None,
        evaluator: str = "",
        notes: str = "",
        subject: str | None = None,
    ) -> None:
        """Show ``report``. ``test_name``, ``evaluator`` and ``notes`` are the test record's
        current values (the report only knows the name at run time); ``subject`` defaults
        to the report's. Starts on the Summary with the first trial selected."""
        self._report = report
        session = report.get("session", {})
        name = test_name if test_name is not None else str(session.get("test_name") or "")
        self._loading = True
        try:
            self.name_edit.setText(name)
            self._own_name = name.strip()
            self.evaluator_edit.setText(evaluator)
            self.notes_edit.setPlainText(notes)
            who = subject if subject is not None else session.get("subject")
            self.subject_label.setText(f"Subject: <b>{escape(str(who or DASH))}</b>")
            self.date_label.setText(f"Test Date: <b>{started_text(session.get('started_ns'))}</b>")
            self._fill_banner()
            self._fill_left()
            self.summary.set_report(report)
            self.detailed.set_report(report)
        finally:
            self._loading = False
        self._note = ""
        self.show_summary()
        self.mark_clean()
        self._refresh_footer()

    def set_context(
        self, *, existing_test_names: Iterable[str] | None = None, pdf_dir: str | Path | None = None
    ) -> None:
        """What the page needs from the host (``None`` leaves a part as it was): this
        subject's test names (the Test Name must be unique among them, the test's own
        name aside) and the folder Print Report starts in."""
        if existing_test_names is not None:
            self._existing_names = list(existing_test_names)
        if pdf_dir is not None:
            self._pdf_dir = str(pdf_dir)
        self._refresh_footer()

    @property
    def view_mode(self) -> str:
        return self._view

    def show_summary(self) -> None:
        self._set_view(SUMMARY)

    def show_detailed(self) -> None:
        self._set_view(DETAILED)

    def collect_edits(self) -> dict[str, str]:
        """The three editable fields as they are now (the Test Name trimmed)."""
        return {
            "test_name": self.name_edit.text().strip(),
            "evaluator": self.evaluator_edit.text().strip(),
            "notes": self.notes_edit.toPlainText(),
        }

    def is_dirty(self) -> bool:
        return self._state() != self._baseline

    def mark_clean(self) -> None:
        self._baseline = self._state()

    def save_problem(self) -> str | None:
        """Why Save & Continue is disabled (the Test Name rules of R10), or ``None``."""
        return validate_test_name(
            self.name_edit.text(), self._existing_names, exclude=self._own_name or None
        )

    def show_note(self, text: str) -> None:
        """A line in the footer from the host (a failed save); a Test Name problem
        outranks it and the next edit clears it, like the page's own notes."""
        self._note = text
        self._refresh_footer()

    def selected_trial(self) -> int | None:
        """The report trial index of the selected Detailed row (``None`` if none)."""
        return self.detailed.selected_trial()

    def export_pdf(self, path: str | Path) -> Path:
        """Write the PDF of the report as it is on screen now (the edited name,
        evaluator and notes) to ``path``; raises :class:`OSError` if it cannot. The map in
        it is the whole test with Targets only, whatever the screen shows."""
        summary_map = self.summary.map
        width = PDF_MAP_WIDTH_PX
        previous = summary_map.trial()
        summary_map.set_trial(None)
        try:
            image = summary_map.render_to_image(
                QSize(width, round(width / summary_map.aspect)), {"targets": True}
            )
        finally:
            summary_map.set_trial(previous)
        edits = self.collect_edits()
        return export_report_pdf(
            path,
            self._report,
            test_name=edits["test_name"],
            evaluator=edits["evaluator"],
            notes=edits["notes"],
            map_image=image,
        )

    # -- building ---------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)

        self.title_label = QLabel("Summary Results:")
        self.title_label.setObjectName("wtmhPageTitle")
        outer.addWidget(self.title_label)

        header = QHBoxLayout()
        header.setSpacing(24)
        name_box = QVBoxLayout()
        name_box.setSpacing(4)
        name_box.addWidget(section_title("Test Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumWidth(360)
        name_box.addWidget(self.name_edit)
        header.addLayout(name_box, stretch=1)
        info = QVBoxLayout()
        info.setSpacing(4)
        facts = QHBoxLayout()
        self.subject_label = QLabel(f"Subject: <b>{DASH}</b>")
        self.date_label = QLabel(f"Test Date: <b>{DASH}</b>")
        facts.addWidget(self.subject_label)
        facts.addSpacing(16)
        facts.addWidget(self.date_label)
        facts.addStretch(1)
        info.addLayout(facts)
        evaluator_row = QHBoxLayout()
        evaluator_row.addWidget(QLabel("Evaluator"))
        self.evaluator_edit = QLineEdit()
        self.evaluator_edit.setMinimumWidth(240)
        evaluator_row.addWidget(self.evaluator_edit)
        info.addLayout(evaluator_row)
        header.addLayout(info)
        outer.addLayout(header)

        self.banner = QFrame()
        self.banner.setObjectName("wtmhAlertWarning")
        banner_layout = QVBoxLayout(self.banner)
        self.banner_label = QLabel("")
        self.banner_label.setTextFormat(Qt.TextFormat.PlainText)
        self.banner_label.setWordWrap(True)
        banner_layout.addWidget(self.banner_label)
        self.banner.setVisible(False)
        outer.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(self._build_left())
        self.summary = SummaryView()
        self.detailed = DetailedView()
        self._stack = QStackedWidget()
        self._stack.addWidget(self.summary)
        self._stack.addWidget(self.detailed)
        body.addWidget(self._stack, stretch=1)
        outer.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.print_button = _button("Print Report", "wtmhGhost")
        self.toggle_button = _button("View Details", "wtmhGhost")
        # "&&" is how a button shows one "&" (a single one makes the next letter a mnemonic).
        self.save_button = _button("Save && Continue", "wtmhPrimary")
        self.cancel_button = _button("Cancel", "wtmhGhost")
        for button in (self.print_button, self.toggle_button, self.save_button, self.cancel_button):
            footer.addWidget(button)
        footer.addSpacing(6)
        self.footer_message = muted_label()
        footer.addWidget(self.footer_message, stretch=1)
        outer.addLayout(footer)

    def _build_left(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)
        layout.addWidget(section_title("Test Configuration"))
        self.config_name_label = QLabel(f"Configuration Name: <b>{DASH}</b>")
        layout.addWidget(self.config_name_label)
        self.config_table = FitTable(["Setting", "Value"], stretch_column=1, wrap=True, compact=True)
        layout.addWidget(self.config_table)
        layout.addWidget(section_title("Notes"))
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes about this test")
        self.notes_edit.setMinimumHeight(110)
        layout.addWidget(self.notes_edit)
        layout.addStretch(1)
        area = scroll_area(content)
        area.setFixedWidth(SIDEBAR_WIDTH)
        return area

    def _connect(self) -> None:
        for edit in (self.name_edit, self.evaluator_edit):
            edit.textChanged.connect(self._on_edited)
        self.notes_edit.textChanged.connect(self._on_edited)
        self.print_button.clicked.connect(self._on_print)
        self.toggle_button.clicked.connect(self._on_toggle)
        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.cancelRequested)

    # -- filling and view -----------------------------------------------------------

    def _fill_banner(self) -> None:
        lines = banner_lines(self._report)
        self.banner_label.setText("\n".join(lines))
        self.banner.setVisible(bool(lines))

    def _fill_left(self) -> None:
        session = self._report.get("session", {})
        name = escape(str(session.get("config_name") or DASH))
        self.config_name_label.setText(f"Configuration Name: <b>{name}</b>")
        rows = [[str(a), str(b)] for a, b in self._report.get("config", {}).get("rows", [])]
        self.config_table.set_rows(rows)

    def _set_view(self, view: str) -> None:
        self._view = view
        detailed = view == DETAILED
        self._stack.setCurrentIndex(1 if detailed else 0)
        self.title_label.setText("Detailed Results:" if detailed else "Summary Results:")
        self.toggle_button.setText("View Summary" if detailed else "View Details")
        if detailed:
            self.detailed.table.setFocus()

    def _on_toggle(self) -> None:
        self._set_view(SUMMARY if self._view == DETAILED else DETAILED)

    # -- edits and footer -----------------------------------------------------------

    def _state(self) -> tuple[str, str, str]:
        return (self.name_edit.text(), self.evaluator_edit.text(), self.notes_edit.toPlainText())

    def _on_edited(self, *_args: object) -> None:
        if self._loading:
            return
        self._note = ""
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        problem = self.save_problem() if self._report else None
        self.save_button.setEnabled(bool(self._report) and problem is None)
        self.footer_message.setText(problem or self._note)

    def _on_save(self) -> None:
        if self.save_problem() is not None:
            return
        edits = self.collect_edits()
        self.saved.emit(edits["test_name"], edits["evaluator"], edits["notes"])

    def _ask_pdf_path(self, default: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Print Report", default, "PDF files (*.pdf)")
        if path and not path.lower().endswith(".pdf"):
            path += ".pdf"
        return path

    def _on_print(self) -> None:
        session = self._report.get("session", {})
        name = pdf_default_name(
            str(session.get("subject") or ""), self.name_edit.text().strip(), session.get("started_ns")
        )
        default = str(Path(self._pdf_dir) / name) if self._pdf_dir else name
        chosen = self.choose_pdf_path(default)
        if not chosen:
            return
        try:
            path = self.export_pdf(chosen)
        except Exception as exc:  # noqa: BLE001 - shown to the operator, never a crash
            _log.warning("Print Report failed for %s: %s", chosen, exc)
            self._note = f"The PDF could not be written: {exc}"
        else:
            self._note = f"PDF saved: {path}"
            self.pdfExported.emit(str(path))
        self._refresh_footer()
