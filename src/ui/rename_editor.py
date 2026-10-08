"""The in-place rename editor of the Test List (SPEC-compass-task-flow.md 4A.4, 4A.6;
wireframe ``docs/wireframes/test-list.md``, "Rename (in place, F2)").

A small popup that opens over the Test Name cell: a text box with the reason a name is
refused shown underneath it as the operator types. The rules are the store's own
(:func:`~src.engine.subject_test_record.validate_test_name`, R10), the same ones the
configuration page's Test Name field uses. Enter keeps the name (only while it is
valid), Esc or a click anywhere else leaves the test as it was. The editor changes
nothing itself; it emits ``committed(new_name)`` and the Test List does the rename.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..engine.subject_test_record import validate_test_name
from .design_tokens import BORDER_STRONG, PANEL, RADIUS

MIN_WIDTH = 320


class RenameEditor(QFrame):
    committed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        current_name: str,
        existing_names: Iterable[str],
        parent: QWidget | None = None,
    ) -> None:
        """``current_name`` is the test's own name (it may be kept, or changed in case
        only); ``existing_names`` are all of this subject's names."""
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("wtmhRenameEditor")
        self.setStyleSheet(
            f"QFrame#wtmhRenameEditor {{ background: {PANEL}; border: 1px solid {BORDER_STRONG};"
            f" border-radius: {RADIUS}px; }}"
        )
        self._current = current_name
        self._existing = list(existing_names)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self.line_edit = QLineEdit(current_name)
        self.line_edit.setObjectName("wtmhRenameEdit")
        self.error_label = QLabel("")
        self.error_label.setObjectName("wtmhMuted")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.error_label)
        self.setMinimumWidth(MIN_WIDTH)

        self.line_edit.textChanged.connect(self._refresh)
        self.line_edit.returnPressed.connect(self.commit)
        self._done = False
        self._refresh()

    def problem(self) -> str | None:
        """Why the name in the box cannot be kept, or ``None``."""
        return validate_test_name(self.line_edit.text(), self._existing, exclude=self._current)

    def name(self) -> str:
        return self.line_edit.text().strip()

    def commit(self) -> bool:
        """Keep the name if it is valid (Enter); otherwise the reason stays on show."""
        if self._done or self.problem() is not None:
            return False
        self._done = True
        self.hide()
        self.committed.emit(self.name())
        return True

    def cancel(self) -> None:
        if self._done:
            return
        self._done = True
        self.hide()
        self.cancelled.emit()

    def open_at(self, global_pos, width: int) -> None:
        """Show the editor with its top-left corner at ``global_pos``."""
        self.setMinimumWidth(max(MIN_WIDTH, width))
        self.adjustSize()
        self.move(global_pos)
        self.show()
        self.line_edit.setFocus()
        self.line_edit.selectAll()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # A click outside closes a popup without a word: that is a cancel.
        super().hideEvent(event)
        if not self._done:
            self.cancel()

    def _refresh(self) -> None:
        problem = self.problem()
        self.error_label.setText(problem or "")
        self.error_label.setVisible(problem is not None)
