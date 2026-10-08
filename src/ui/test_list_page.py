"""The Tests tab: one subject's Test List (SPEC-compass-task-flow.md 4A.4-4A.6, U2, U3;
wireframe ``docs/wireframes/test-list.md``, Compass ``05-test-list.png``).

Replaces the four fixed task cards of ``tasks_page.py``. The list is the tests of the
Subject ID typed in Setup, read from disk every time :meth:`SubjectTestListPage.set_subject`
is called, so it is the same after an app restart and nothing about a subject lives in
memory (4A.8). Every action writes first (``src.engine.subject_tests``) and then reloads
the table from disk; a failed write shows a message and leaves the list as the disk has it.

The page owns Add New Test, Copy Test, Delete Test and the in-place rename, which need
no tracker and no other page. Configure, Run and View Report only emit a signal with the
test id (``configureRequested`` / ``runRequested`` / ``reportRequested``): the dashboard
opens the page that does the work. Run Test is never disabled by the Setup gate (R2): the
Start page lists what is missing.

The table is a ``QTableWidget`` that is not sortable by Qt itself: a header click sorts
it (Test Name by a natural key, so "Grid Click 2" comes before "Grid Click 10"; Date
Complete with "—" first) and the order and the selection are kept across a reload.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine.run_paths import resolve_run_dir
from ..engine.subject_store import find_subject
from ..engine.subject_tests import (
    ACTION_ADD,
    ACTION_CONFIGURE,
    ACTION_COPY,
    ACTION_DELETE,
    ACTION_REPORT,
    ACTION_RUN,
    STATUS_NOT_DONE,
    SubjectTest,
    TestStoreError,
    allowed_actions,
    copy_test,
    create_test,
    delete_test,
    list_tests,
    rename_test,
    subject_tests_dir,
)
from .add_test_dialog import AddTestDialog
from .folder_opener import open_folder
from .rename_editor import RenameEditor
from .run_dialogs import DANGER_TIER, PRIMARY, ask_choice
from .test_list_table import (
    COL_NAME,
    HEADERS,
    SubjectTestTable,
)

NO_SUBJECT_TEXT = "Enter a Subject ID in Setup."
NO_TESTS_TEXT = "No tests yet. Choose Add New Test."
SAVED_TEXT = "Changes are saved automatically."

# Local sheet for the table: the theme pads every header section by 6 px 8 px, the hidden
# vertical header included, which makes each row about 13 px taller than its text.
_TABLE_STYLE = "QHeaderView::section:vertical { padding: 0px; border: none; }"


class SubjectTestListPage(QWidget):
    configureRequested = Signal(str)  # test id
    runRequested = Signal(str)
    reportRequested = Signal(str)
    backToSetupRequested = Signal()
    testsChanged = Signal()  # a test was added, copied, renamed or deleted

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._subject_id = ""
        self._output_root = Path("sessions")
        self._folder_mode = "id"  # how a new subject's folder is named (Setup's choice, H6)
        self._subject_path: Path | None = None  # the typed subject's folder, as of the last reload
        self._tests: dict[str, SubjectTest] = {}
        self._sort: tuple[int, Qt.SortOrder] | None = None  # None = creation order
        self._editor: RenameEditor | None = None
        # The page's modal questions, replaceable so a test answers without a modal loop.
        self._choose_new_tests: Callable[[], tuple[str, int] | None] = lambda: AddTestDialog.ask(self)
        # Opens a folder in Explorer; replaceable so a test opens nothing.
        self._open_folder: Callable[[Path], bool] = open_folder
        self._confirm_delete: Callable[[SubjectTest], bool] = self._ask_delete
        self._build_ui()
        self.reload()

    # -- public API ---------------------------------------------------------------

    def set_subject(self, subject_id: str, output_root: str | Path, folder_mode: str = "id") -> None:
        """Show ``subject_id``'s tests, read from ``output_root`` now. A blank ID is the
        "Enter a Subject ID in Setup." state: nothing is read, created or enabled.
        ``folder_mode`` is how Setup chose to name a **new** subject's folder; the first
        test added creates it (SPEC-subject-data-layout.md H6)."""
        self._subject_id = subject_id.strip()
        self._output_root = Path(output_root)
        self._folder_mode = folder_mode
        self.reload()

    def reload(self, select: str | None = None) -> None:
        """Re-read the list from disk. The selection (``select``, else the one before)
        and the sort order are kept; a test that is gone is simply unselected."""
        keep = select or self._selected_id()
        self._close_editor()
        subject = find_subject(self._output_root, self._subject_id) if self._subject_id else None
        self._subject_path = subject.path if subject is not None else None
        unreadable: list[Path] = []
        tests: list[SubjectTest] = []
        if self._subject_id:
            loaded = list_tests(self._output_root, self._subject_id)
            tests, unreadable = loaded.tests, loaded.unreadable
        self._tests = {t.test_id: t for t in tests}
        self.table.populate(tests, self._data_missing)
        if self._sort is not None:
            self.table.sortItems(*self._sort)
        self.title_label.setText(
            f"Test List for {self._subject_id}" if self._subject_id else "Test List"
        )
        if not self._subject_id:
            self.empty_label.setText(NO_SUBJECT_TEXT)
        elif not tests:
            self.empty_label.setText(NO_TESTS_TEXT)
        self.center.setCurrentIndex(0 if tests else 1)
        self.unreadable_label.setText(
            f"{len(unreadable)} test file(s) could not be read and are hidden: "
            f"{subject_tests_dir(self._output_root, self._subject_id)}"
            if unreadable
            else ""
        )
        self.unreadable_label.setVisible(bool(unreadable))
        # The selection matches the focus the table shows (FX3): the test used last if it is
        # still listed, else the first row; nothing when the list is empty.
        first = self.table.item(0, COL_NAME) if tests else None
        if not (keep and self.select_test(keep)) and first is not None:
            self.select_test(first.data(Qt.ItemDataRole.UserRole))
        self._update_buttons()

    def selected_test(self) -> SubjectTest | None:
        return self._tests.get(self._selected_id() or "")

    def select_test(self, test_id: str) -> bool:
        row = self._row_of(test_id)
        if row < 0:
            return False
        self.table.selectRow(row)
        self.table.setCurrentCell(row, COL_NAME)
        self.table.scrollToItem(self.table.item(row, COL_NAME))
        return True

    def show_message(self, text: str) -> None:
        """A muted line under the table (a failed action, or a note from the dashboard);
        cleared by the next action."""
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))

    def row_texts(self) -> list[list[str]]:
        """The cell texts as shown, top to bottom."""
        return [
            [self.table.item(r, c).text() for c in range(len(HEADERS))]
            for r in range(self.table.rowCount())
        ]

    def start_rename(self) -> RenameEditor | None:
        """Open the in-place editor over the selected test's name (F2, double-click)."""
        test = self.selected_test()
        row = self._row_of(test.test_id) if test is not None else -1
        if test is None or row < 0:
            return None
        self._close_editor()
        self.show_message("")
        editor = RenameEditor(test.name, [t.name for t in self._tests.values()], parent=self)
        editor.committed.connect(lambda name, test_id=test.test_id: self._on_renamed(test_id, name))
        editor.cancelled.connect(self._close_editor)
        self._editor = editor
        rect = self.table.visualItemRect(self.table.item(row, COL_NAME))
        editor.open_at(self.table.viewport().mapToGlobal(rect.topLeft()), rect.width())
        return editor

    # -- building -------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        self.title_label = QLabel("Test List")
        self.title_label.setObjectName("wtmhPageTitle")
        outer.addWidget(self.title_label)

        body = QHBoxLayout()
        body.setSpacing(16)
        outer.addLayout(body, stretch=1)

        left = QVBoxLayout()
        left.setSpacing(8)
        body.addLayout(left, stretch=1)

        self.table = SubjectTestTable(0, len(HEADERS))
        self.table.setObjectName("wtmhTestTable")
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.setHorizontalHeaderLabels(list(HEADERS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setSortIndicatorShown(False)
        for column in range(len(HEADERS)):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch
                if column == COL_NAME
                else QHeaderView.ResizeMode.ResizeToContents,
            )

        # Page 0 is the table; page 1 is the empty-state line that stands in for it.
        self.center = QStackedWidget()
        self.center.addWidget(self.table)
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_label = QLabel(NO_SUBJECT_TEXT)
        self.empty_label.setObjectName("wtmhMuted")
        self.empty_label.setWordWrap(True)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch(1)
        self.center.addWidget(empty_page)
        left.addWidget(self.center, stretch=1)

        self.unreadable_label = QLabel("")
        self.unreadable_label.setObjectName("wtmhMuted")
        self.unreadable_label.setWordWrap(True)
        self.unreadable_label.hide()
        self.message_label = QLabel("")
        self.message_label.setObjectName("wtmhMuted")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        left.addWidget(self.unreadable_label)
        left.addWidget(self.message_label)

        # The button column, vertically centred; disabled buttons stay visible and grey.
        column = QVBoxLayout()
        column.setSpacing(10)
        column.addStretch(1)
        self.add_button = self._button("Add New Test", "wtmhGhost", column)
        self.configure_button = self._button("Configure Test", "wtmhGhost", column)
        self.run_button = self._button("Run Test", PRIMARY, column)
        self.report_button = self._button("View Report", "wtmhGhost", column)
        self.copy_button = self._button("Copy Test", "wtmhGhost", column)
        self.delete_button = self._button("Delete Test", "wtmhGhost", column)
        # Outside the row matrix: on whenever the subject has a folder (SPEC-subject-data-
        # layout.md H6, wireframe W2), whichever row is selected.
        self.open_folder_button = self._button("Open Subject Folder", "wtmhGhost", column)
        column.addStretch(1)
        body.addLayout(column)

        footer = QHBoxLayout()
        footer.setSpacing(16)
        self.back_button = QPushButton("← Back to Setup / recalibrate")
        self.back_button.setObjectName("wtmhGhost")
        self.back_button.setAutoDefault(False)
        footer.addWidget(self.back_button)
        saved = QLabel(SAVED_TEXT)
        saved.setObjectName("wtmhMuted")
        footer.addWidget(saved)
        footer.addStretch(1)
        outer.addLayout(footer)

        self.add_button.clicked.connect(self._on_add)
        self.configure_button.clicked.connect(lambda: self._emit_for_selected(self.configureRequested))
        self.run_button.clicked.connect(lambda: self._emit_for_selected(self.runRequested))
        self.report_button.clicked.connect(lambda: self._emit_for_selected(self.reportRequested))
        self.copy_button.clicked.connect(self._on_copy)
        self.delete_button.clicked.connect(self._on_delete)
        self.open_folder_button.clicked.connect(self._on_open_folder)
        self.back_button.clicked.connect(self.backToSetupRequested)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_double_clicked)
        self.table.deleteRequested.connect(self._on_delete)
        self.table.renameRequested.connect(self.start_rename)
        self.table.activateRequested.connect(self._activate)
        header.sectionClicked.connect(self._on_header_clicked)

    @staticmethod
    def _button(text: str, tier: str, layout: QVBoxLayout) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)
        button.setAutoDefault(False)
        button.setMinimumWidth(170)
        layout.addWidget(button)
        return button

    # -- table contents ----------------------------------------------------------------

    def _data_missing(self, test: SubjectTest) -> bool:
        """A run whose folder is no longer on disk (4A.4)."""
        if test.status == STATUS_NOT_DONE:
            return False
        folder = resolve_run_dir(self._subject_path, test.run_dir) if self._subject_path else None
        return folder is None or not folder.is_dir()

    def _selected_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), COL_NAME)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _row_of(self, test_id: str) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_NAME)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == test_id:
                return row
        return -1

    def _on_header_clicked(self, column: int) -> None:
        keep = self._selected_id()
        if self._sort is not None and self._sort[0] == column:
            order = (
                Qt.SortOrder.DescendingOrder
                if self._sort[1] == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.AscendingOrder
        self._sort = (column, order)
        self.table.sortItems(column, order)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().setSortIndicator(column, order)
        if keep is not None:
            self.select_test(keep)

    # -- buttons ---------------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        self.show_message("")
        self._update_buttons()

    def _update_buttons(self) -> None:
        test = self.selected_test()
        # No Subject ID: nothing is on, not even Add (4A.4 empty state, AA15).
        actions = allowed_actions(test) if self._subject_id else frozenset()
        missing = test is not None and self._data_missing(test)
        self.add_button.setEnabled(ACTION_ADD in actions)
        self.configure_button.setEnabled(ACTION_CONFIGURE in actions)
        self.run_button.setEnabled(ACTION_RUN in actions)
        self.report_button.setEnabled(ACTION_REPORT in actions and not missing)
        self.copy_button.setEnabled(ACTION_COPY in actions)
        self.delete_button.setEnabled(ACTION_DELETE in actions)
        self.open_folder_button.setEnabled(self._subject_path is not None)
        self.report_button.setToolTip(
            "The recorded data for this test is missing from the subject folder." if missing else ""
        )

    def _on_open_folder(self) -> None:
        folder = self._subject_path
        if folder is None:
            return
        if not self._open_folder(folder):
            self.show_message(f"Could not open the folder {folder}.")

    def _emit_for_selected(self, signal) -> None:
        test = self.selected_test()
        if test is not None:
            self.show_message("")
            signal.emit(test.test_id)

    def _activate(self) -> None:
        """Enter, or a double-click off the name: Run Test for a Not Done test, else View
        Report. Run leads to the Start page, so a stray double-click records nothing."""
        test = self.selected_test()
        if test is None:
            return
        if test.status == STATUS_NOT_DONE:
            if self.run_button.isEnabled():
                self._emit_for_selected(self.runRequested)
        elif self.report_button.isEnabled():
            self._emit_for_selected(self.reportRequested)

    def _on_double_clicked(self, _row: int, column: int) -> None:
        if column == COL_NAME:
            self.start_rename()
        else:
            self._activate()

    # -- actions that need no other page -------------------------------------------------------

    def _failed(self, what: str, exc: Exception) -> None:
        """A write failed: say so, and show the list as the disk really has it."""
        self.reload()
        self.show_message(f"Could not {what}: {str(exc).rstrip('.')}. Nothing was changed.")

    def _on_add(self) -> None:
        choice = self._choose_new_tests()
        if choice is None or not self._subject_id:
            return
        task_id, count = choice
        created: list[SubjectTest] = []
        try:
            for _ in range(count):
                created.append(
                    create_test(self._output_root, self._subject_id, task_id, folder_mode=self._folder_mode)
                )
        except (TestStoreError, ValueError) as exc:
            if not created:
                self._failed("add the test", exc)
                return
            # Some were written before the failure: the disk has them, so show them.
            self.reload(select=created[-1].test_id)
            self.show_message(
                f"Added {len(created)} of {count} tests; could not add the rest: "
                f"{str(exc).rstrip('.')}."
            )
            self.testsChanged.emit()
            return
        self.reload(select=created[-1].test_id)
        self.show_message("")
        self.testsChanged.emit()

    def _on_copy(self) -> None:
        test = self.selected_test()
        if test is None:
            return
        try:
            copy = copy_test(self._output_root, test.subject_id, test.test_id)
        except (TestStoreError, ValueError) as exc:
            self._failed(f"copy '{test.name}'", exc)
            return
        self.reload(select=copy.test_id)
        self.show_message("")
        self.testsChanged.emit()

    def _ask_delete(self, test: SubjectTest) -> bool:
        text = f"Delete '{test.name}' from this list?"
        if test.run_dir:
            text += " Its recorded data in the subject folder is kept."
        buttons = [("delete", "Delete", DANGER_TIER), ("keep", "Keep", PRIMARY)]
        return ask_choice(self, "Delete Test", text, buttons, "keep", "keep") == "delete"

    def _on_delete(self) -> None:
        test = self.selected_test()
        if test is None or not self._subject_id or not self._confirm_delete(test):
            return
        try:
            delete_test(self._output_root, test.subject_id, test.test_id)
        except (TestStoreError, ValueError) as exc:
            self._failed(f"delete '{test.name}'", exc)
            return
        self.reload()
        self.show_message("")
        self.testsChanged.emit()

    def _on_renamed(self, test_id: str, new_name: str) -> None:
        test = self._tests.get(test_id)
        self._close_editor()
        if test is None:
            return
        try:
            rename_test(self._output_root, test.subject_id, test_id, new_name)
        except (TestStoreError, ValueError) as exc:
            self._failed(f"rename '{test.name}'", exc)
            return
        self.reload(select=test_id)
        self.testsChanged.emit()

    def _close_editor(self) -> None:
        editor, self._editor = self._editor, None
        if editor is not None:
            editor.hide()
            editor.deleteLater()
