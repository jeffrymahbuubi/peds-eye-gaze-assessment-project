"""The Test List's "Selected test" card: the seven buttons inside one card that names what
they act on (SPEC-test-list-visual-identity.md 4.3, direction B; wireframe
``docs/wireframes/test-list-alt-b.md``).

Look only. The buttons are the page's own, in today's order and tiers (Run Test is the only
primary; Delete Test carries the red square). The card adds a heading: the selected test's name
at the heading step with its Status badge under it, or "No test selected" in ``TEXT_SECONDARY``.
The heading never changes height, so the buttons do not move when the selection does, and a
long name is cut with an ellipsis rather than widening the card.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ..engine.subject_tests import SubjectTest
from .design_tokens import DANGER, TEXT_DISABLED
from .glyphs import GLYPH_SQUARE, glyph_icon
from .run_dialogs import PRIMARY
from .status_badge import StatusBadge
from .test_list_table import status_badge_state

NO_SELECTION_TEXT = "No test selected"
CARD_PADDING = 24
BUTTON_SPACING = 8
BUTTON_MIN_WIDTH = 170


class ElidedLabel(QLabel):
    """A one-line label that never asks for more width than it is given: the text is cut with an
    ellipsis, and ``full_text()`` (also the tooltip when cut) keeps all of it."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextFormat(Qt.TextFormat.PlainText)  # a test name is never markup
        self.setIndent(0)  # flush with the buttons (the sheet's box would indent the text)
        self.set_full_text(text)

    def full_text(self) -> str:
        return self._full

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, max(0, self.width()))
        self.setText(shown if self.width() > 0 else self._full)
        self.setToolTip(self._full if shown != self._full else "")

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._elide()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt naming)
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._elide()


class SelectedTestCard(QFrame):
    """The card: heading, then Add New Test, Configure Test, Run Test, View Report, Copy Test,
    Delete Test and Open Subject Folder. :meth:`show_test` sets the heading."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        column.setSpacing(BUTTON_SPACING)

        # One slot for both headings, as high as the taller: the buttons stay where they are.
        self.name_label = ElidedLabel()
        self.name_label.setObjectName("wtmhSectionTitle")
        self.name_label.setStyleSheet("margin-bottom: 0px;")  # the badge belongs right under the name
        self.none_label = ElidedLabel(NO_SELECTION_TEXT)
        self.none_label.setObjectName("cfgAdvancedTitle")  # the sheet's heading step in TEXT_SECONDARY
        heading = QStackedLayout()
        heading.addWidget(self.name_label)
        heading.addWidget(self.none_label)
        self._heading = heading
        column.addLayout(heading)
        self.badge = StatusBadge()
        keep = self.badge.sizePolicy()
        keep.setRetainSizeWhenHidden(True)  # a hidden badge still holds its row
        self.badge.setSizePolicy(keep)
        badge_row = QHBoxLayout()
        badge_row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignLeft)
        badge_row.addStretch(1)
        column.addLayout(badge_row)
        column.addSpacing(BUTTON_SPACING)

        self.add_button = self._button("Add New Test", "wtmhGhost", column)
        self.configure_button = self._button("Configure Test", "wtmhGhost", column)
        self.run_button = self._button("Run Test", PRIMARY, column)
        self.report_button = self._button("View Report", "wtmhGhost", column)
        self.copy_button = self._button("Copy Test", "wtmhGhost", column)
        self.delete_button = self._button("Delete Test", "wtmhGhost", column)
        self.delete_button.setIcon(glyph_icon(GLYPH_SQUARE, DANGER, TEXT_DISABLED))  # V2
        self.delete_button.setIconSize(QSize(12, 12))
        # Outside the row matrix: on whenever the subject has a folder (SPEC-subject-data-
        # layout.md H6, wireframe W2), whichever row is selected.
        self.open_folder_button = self._button("Open Subject Folder", "wtmhGhost", column)
        self.show_test(None)

    @property
    def buttons(self) -> tuple[QPushButton, ...]:
        """The seven buttons, top to bottom."""
        return (
            self.add_button,
            self.configure_button,
            self.run_button,
            self.report_button,
            self.copy_button,
            self.delete_button,
            self.open_folder_button,
        )

    @staticmethod
    def _button(text: str, tier: str, layout: QVBoxLayout) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)
        button.setAutoDefault(False)
        button.setMinimumWidth(BUTTON_MIN_WIDTH)
        layout.addWidget(button)
        return button

    def show_test(self, test: SubjectTest | None, data_missing: bool = False) -> None:
        """Name the selected test and its state, or say that none is selected."""
        if test is None:
            self._heading.setCurrentWidget(self.none_label)
            self.badge.hide()
            return
        self.name_label.set_full_text(test.name)
        self._heading.setCurrentWidget(self.name_label)
        self.badge.set_state(*status_badge_state(test, data_missing))
        self.badge.show()

    def heading_text(self) -> str:
        """The heading as the operator reads it: the test's name, or "No test selected"."""
        label = self._heading.currentWidget()
        return label.full_text() if isinstance(label, ElidedLabel) else ""
