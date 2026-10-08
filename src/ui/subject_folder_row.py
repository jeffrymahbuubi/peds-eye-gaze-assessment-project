"""The Setup page's folder-name choice (SPEC-subject-data-layout.md H6, D4; wireframe
``docs/wireframes/setup.md``, W1).

Under the Subject ID field. While the typed ID is **new** (no ``subject.json`` on this PC
holds it, matched ignoring case) it shows ``Folder name: (*) Subject ID ( ) Anonymous code
(S-0004)``; the code shown is the one the next new subject would get. Once the subject has a
folder the choice is gone and one muted line says what was chosen, e.g. ``Folder: S-0003
(Anonymous code)``. Only one of the two is ever visible, and nothing at all for a blank ID.

The choice is fixed when the subject's folder is created (the first calibration, setting or
test saved for it); this widget only holds what the operator picked until then.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout, QWidget

from ..engine.subject_store import (
    FOLDER_MODE_CODE,
    FOLDER_MODE_ID,
    find_subject,
    next_subject_code,
)

CODE_TOOLTIP = (
    "The folder is named {code} instead of the Subject ID, so Explorer and zip file names "
    "do not show it. The files inside still contain the Subject ID."
)


class SubjectFolderRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.choice = QWidget()
        row = QHBoxLayout(self.choice)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(QLabel("Folder name"))
        self.id_radio = QRadioButton("Subject ID")
        self.code_radio = QRadioButton("Anonymous code")
        self.id_radio.setChecked(True)
        self._group = QButtonGroup(self)
        self._group.addButton(self.id_radio)
        self._group.addButton(self.code_radio)
        row.addWidget(self.id_radio)
        row.addWidget(self.code_radio)
        row.addStretch(1)
        layout.addWidget(self.choice)

        self.folder_label = QLabel("")
        self.folder_label.setObjectName("wtmhMuted")
        layout.addWidget(self.folder_label)
        self.update_for(Path("sessions"), "")

    def folder_mode(self) -> str:
        """What the operator picked for a new subject (the default is the Subject ID)."""
        return FOLDER_MODE_CODE if self.code_radio.isChecked() else FOLDER_MODE_ID

    def update_for(self, output_root: str | Path, subject_id: str) -> None:
        """Show the right state for the typed ``subject_id``, read from disk now."""
        subject_id = subject_id.strip()
        existing = find_subject(output_root, subject_id) if subject_id else None
        if existing is not None:
            self.choice.setVisible(False)
            self.folder_label.setText(existing.label())
            self.folder_label.setVisible(True)
            return
        self.folder_label.setVisible(False)
        self.choice.setVisible(bool(subject_id))
        if subject_id:
            code = next_subject_code(output_root)
            self.code_radio.setText(f"Anonymous code ({code})")
            self.code_radio.setToolTip(CODE_TOOLTIP.format(code=code))
