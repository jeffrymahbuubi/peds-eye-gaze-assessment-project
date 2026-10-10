"""The two questions Save & Continue can ask (SPEC-compass-task-flow.md 4B.4; wireframe
``docs/wireframes/task-config.md``, "Save as a new configuration" and "Configuration exists").

* :func:`ask_config_name` -- a name for the settings: "Standard cannot be changed. Save
  these settings as:" with a default of "Custom 1", also used for "Save under a new
  name...". The Save button stays off, with the reason shown, until the name is one that
  can be stored (:func:`~src.engine.settings_profile.validate_config_name`: 1-40
  characters, not "Standard").
* :func:`ask_update_choice` -- "'<name>' already exists with different settings": Update
  it, save under a new name, or cancel.

Both only ask; the flow in :mod:`src.ui.config_flow` acts on the answer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.settings_profile import validate_config_name
from .design_tokens import TYPE_HEADING
from .dialog_theme import apply_dialog_theme
from .run_dialogs import GHOST, PRIMARY, ask_choice

UPDATE, NEW_NAME, CANCEL = "update", "new", "cancel"
NAME_FIELD_WIDTH = 320  # the name field by content (SPEC-design-system-phase2.md C7)

STANDARD_INTRO = "Standard cannot be changed. Save these settings as:"
NEW_NAME_INTRO = "Save these settings as:"


class ConfigNameDialog(QDialog):
    def __init__(self, intro: str, default: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_theme(
            self, f"QLabel#cfgNameHeading {{ font-size: {TYPE_HEADING}px; font-weight: 600; }}"
        )
        self.setWindowTitle("Save as a new configuration")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.heading_label = QLabel("Save as a new configuration")  # the heading step, 20 px
        self.heading_label.setObjectName("cfgNameHeading")
        layout.addWidget(self.heading_label)
        self.intro_label = QLabel(intro)
        self.intro_label.setWordWrap(True)
        self.intro_label.setMinimumWidth(380)
        self.name_edit = QLineEdit(default)
        self.name_edit.setObjectName("cfgNewName")
        self.name_edit.setFixedWidth(NAME_FIELD_WIDTH)
        self.error_label = QLabel("")
        self.error_label.setObjectName("wtmhMuted")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.name_edit, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.error_label)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName(PRIMARY)
        self.save_button.setAutoDefault(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName(GHOST)
        self.cancel_button.setAutoDefault(False)
        row.addWidget(self.save_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

        self.name_edit.textChanged.connect(self._refresh)
        self.name_edit.returnPressed.connect(self._save)
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        self._refresh()
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def name(self) -> str:
        return self.name_edit.text().strip()

    def problem(self) -> str | None:
        return validate_config_name(self.name_edit.text())

    def _refresh(self) -> None:
        problem = self.problem()
        self.save_button.setEnabled(problem is None)
        self.error_label.setText(problem or "")
        self.error_label.setVisible(problem is not None)

    def _save(self) -> None:
        if self.problem() is None:
            self.accept()


def ask_config_name(parent: QWidget | None, intro: str, default: str) -> str | None:
    """The name typed, or ``None`` if the operator cancelled."""
    dialog = ConfigNameDialog(intro, default, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.name()
    return None


def ask_update_choice(parent: QWidget | None, name: str) -> str:
    """``update``, ``new`` (save under a new name) or ``cancel`` (Esc gives this)."""
    return ask_choice(
        parent,
        "Configuration exists",
        f"'{name}' already exists with different settings.",
        [
            (UPDATE, f"Update '{name}'", PRIMARY),
            (NEW_NAME, "Save under a new name...", GHOST),
            (CANCEL, "Cancel", GHOST),
        ],
        default=UPDATE,
        on_close=CANCEL,
    )
