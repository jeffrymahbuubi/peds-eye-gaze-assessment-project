"""View Report inside the dashboard (SPEC-compass-task-flow.md 4D.2, 4D.8, 4A.7, R11, HD1).

:class:`ReportFlow` is what the Tests tab's View Report button and the Test complete
dialog's "Save and View Report" hand a test to. It builds a
:class:`~src.ui.report_page.ReportPage` for that test from its ``report.json``
(:func:`~src.data.report_cache.load_or_build_report`, which rebuilds it when it is
missing), puts it on top of the dashboard's stack with the navigation locked, and
answers the page's two signals:

* **Save & Continue** -- writes the Test Name, Evaluator and Notes to the test record
  (they live there, not in the run folder: one source of truth, X5) and returns to the
  Test List with the test selected.
* **Cancel** -- the edits are dropped; returns to the Test List.

The report is of the test's own run folder; ``Print Report`` starts in the subject's
``reports/`` folder (SPEC-subject-data-layout.md H7). It carries the **test's** Subject ID, never whatever is typed in Setup now. A test that has
no run, a run folder that is gone, or a folder no report can be built from is said so on
the Test List, and no page is opened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..data.report_cache import load_or_build_report
from ..engine.subject_store import find_subject
from ..engine.subject_tests import (
    STATUS_NOT_DONE,
    SubjectTest,
    TestStoreError,
    list_tests,
    rename_test,
    run_folder_of,
    update_test,
)
from .dashboard_flow import Flow, find_test
from .report_page import ReportPage

if TYPE_CHECKING:  # pragma: no cover
    from .dashboard_window import DashboardWindow


class ReportFlow:
    def __init__(self, window: DashboardWindow) -> None:
        self._window = window
        self.page: ReportPage | None = None
        self.test: SubjectTest | None = None

    def open(self, test_id: str, report: dict[str, Any] | None = None) -> None:
        """View Report: open the page for ``test_id`` of the subject typed in Setup.
        ``report`` is a report already built (Save and View Report); without one it is
        loaded from the run folder."""
        window = self._window
        if window.flow is not Flow.IDLE:
            return
        listing = window.test_list_page
        test = find_test(window, test_id)
        if test is None:
            listing.reload()
            listing.show_message("That test could not be found. The list was reloaded.")
            return
        if test.status == STATUS_NOT_DONE or not test.run_dir:
            listing.show_message(f"{test.name} has not been run, so it has no report.")
            return
        folder = run_folder_of(window.output_root, test)
        if folder is None or not folder.is_dir():
            listing.show_message(
                f"The recorded data for {test.name} is missing from the subject folder."
            )
            return
        subject = find_subject(window.output_root, test.subject_id)  # exists: the run is in it
        if report is None:
            try:
                report = load_or_build_report(folder)
            except Exception as exc:  # noqa: BLE001 - ReportError or any build bug: say so, never crash
                listing.show_message(f"Could not open the report for {test.name}: {exc}")
                return

        page = ReportPage()
        page.set_report(
            report,
            test_name=test.name,
            evaluator=test.evaluator,
            notes=test.notes,
            subject=test.subject_id,  # the test's own, not the Setup field's (4A.7)
        )
        page.set_context(
            existing_test_names=[t.name for t in list_tests(window.output_root, test.subject_id).tests],
            pdf_dir=subject.reports if subject is not None else None,  # Print Report starts here (H7)
        )
        page.saved.connect(self._on_saved)
        page.cancelRequested.connect(self._close_page)
        self.page, self.test = page, test
        window.stack.addWidget(page)
        window.stack.setCurrentWidget(page)
        window.set_flow(Flow.REPORT)

    def _close_page(self) -> None:
        page, self.page = self.page, None
        test_id = self.test.test_id if self.test is not None else None
        self.test = None
        if page is not None:
            self._window.stack.removeWidget(page)
            page.deleteLater()
        self._window.show_tests(select=test_id)

    def _on_saved(self, name: str, evaluator: str, notes: str) -> None:
        page, window = self.page, self._window
        if page is None or self.test is None:
            return
        fresh = find_test(window, self.test.test_id)
        if fresh is None:
            page.show_note("Could not save: this test could not be found.")
            return
        root = window.output_root
        try:
            if name != fresh.name:
                rename_test(root, fresh.subject_id, fresh.test_id, name)
            if notes != fresh.notes or evaluator != fresh.evaluator:
                update_test(root, fresh.subject_id, fresh.test_id, notes=notes, evaluator=evaluator)
        except (OSError, ValueError, TestStoreError) as exc:
            page.show_note(f"Could not save: {exc}")
            return
        self._close_page()
