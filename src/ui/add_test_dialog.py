"""The Add New Test dialog (SPEC-compass-task-flow.md 4A.5, HA2; wireframe
``docs/wireframes/test-list.md``).

A small modal: the four tasks, each a bold name over a muted one-line description (from
:data:`~src.engine.task_info.TASK_INFO`), a "How many" box (1-10, default 1: the same
task can be added several times), and Add / Cancel. A double-click on a task adds one.
The dialog only *asks*: the Test List creates the tests, with default names and the
Standard configuration, and nothing opens by itself.

Each row is as tall as its label needs (F6): the item's size hint is the label's own size
hint, measured once the label sits in the list under the dashboard's sheet (a label measured
before that has other margins and fonts) and again whenever its font, style sheet or the
screen's scale changes.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..engine.task_info import TASK_INFO
from ..engine.task_runner import TASK_REGISTRY
from .dialog_theme import apply_dialog_theme
from .wtmh_theme import MUTED

MAX_COUNT = 10

# What changes the height a label needs.
_REMEASURE_EVENTS = frozenset(
    {
        QEvent.Type.Polish,
        QEvent.Type.StyleChange,
        QEvent.Type.FontChange,
        QEvent.Type.DevicePixelRatioChange,
    }
)


class _TaskRow(QLabel):
    """One task of the list (bold name over a muted description). It lets the mouse through,
    so a click or double-click still reaches the list item, and says when something that
    decides its height has changed."""

    remeasure = Signal()

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setContentsMargins(6, 4, 6, 4)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in _REMEASURE_EVENTS:
            self.remeasure.emit()
        return handled


class AddTestDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_theme(self)  # light list and text whatever the Windows colour mode (FX1)
        self.setWindowTitle("Add New Test")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Add New Test")
        title.setObjectName("wtmhSectionTitle")
        layout.addWidget(title)

        self.task_list = QListWidget()
        self.task_list.setObjectName("addTestList")
        self.task_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.task_list.setMinimumWidth(460)
        self._rows: list[tuple[QListWidgetItem, _TaskRow]] = []
        for task_id in TASK_REGISTRY:
            name, description = TASK_INFO.get(task_id, (task_id, ""))
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.task_list.addItem(item)
            label = _TaskRow(f"<b>{name}</b><br><span style='color:{MUTED}'>{description}</span>")
            self.task_list.setItemWidget(item, label)
            label.remeasure.connect(self.fit_items)
            self._rows.append((item, label))
        layout.addWidget(self.task_list)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("How many"))
        self.count_spin = QSpinBox()
        self.count_spin.setObjectName("addTestCount")
        self.count_spin.setRange(1, MAX_COUNT)
        self.count_spin.setValue(1)
        count_row.addWidget(self.count_spin)
        count_row.addStretch(1)
        layout.addLayout(count_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("wtmhPrimary")
        self.add_button.setAutoDefault(False)
        self.add_button.setEnabled(False)  # until a task is chosen
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("wtmhGhost")
        self.cancel_button.setAutoDefault(False)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.fit_items()
        self.task_list.itemSelectionChanged.connect(self._refresh)
        self.task_list.itemDoubleClicked.connect(self._add_one)
        self.add_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def fit_items(self) -> None:
        """Make every row as tall as its label needs, as the label is now."""
        for item, label in self._rows:
            label.ensurePolished()
            hint = label.sizeHint()
            if item.sizeHint() != hint:
                item.setSizeHint(hint)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.fit_items()  # the last word, once the list is on screen

    def selected_task_id(self) -> str | None:
        item = self.task_list.currentItem()
        if item is None or not item.isSelected():
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def count(self) -> int:
        return int(self.count_spin.value())

    def choice(self) -> tuple[str, int] | None:
        """``(task_id, how many)`` once a task is chosen, else ``None``."""
        task_id = self.selected_task_id()
        return None if task_id is None else (task_id, self.count())

    def select_task(self, task_id: str) -> None:
        for row in range(self.task_list.count()):
            item = self.task_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                self.task_list.setCurrentItem(item)
                item.setSelected(True)
                return

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> tuple[str, int] | None:
        """Run the dialog; ``(task_id, how many)`` if Add was pressed, else ``None``."""
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.choice()
        return None

    def _refresh(self) -> None:
        self.add_button.setEnabled(self.selected_task_id() is not None)

    def _add_one(self, item: QListWidgetItem) -> None:
        """A double-click adds one test of that task, whatever the count box says."""
        self.count_spin.setValue(1)
        self.task_list.setCurrentItem(item)
        item.setSelected(True)
        self.accept()
