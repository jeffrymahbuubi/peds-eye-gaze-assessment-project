"""The Test List's command panel (SPEC-test-list-visual-identity.md, direction A "Ledger").

Split out of :mod:`src.ui.test_list_page` to keep both under 500 lines. The seven buttons of the
page's right-hand column become the rows of one card: the tertiary tier with a left-aligned label
(hover fill, 40 px, radius 4 inside 8 px of padding), Run Test the one primary row, and three
1 px rules that split the four groups: Add, then Configure / Run / View Report, then Copy /
Delete, then Open Subject Folder. Same labels, same order, same signals as the old column; the
page owns what they do and when they are enabled.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from .design_tokens import DANGER, TEXT_DISABLED
from .glyphs import GLYPH_SQUARE, glyph_icon
from .run_dialogs import PRIMARY
from .test_list_style import PANEL_STYLE

PANEL_WIDTH = 200
PANEL_PADDING = 8  # the spacing scale's 8; the rows inside it are 40 px high with radius 4
TERTIARY = "wtmhTertiary"


class ActionPanel(QFrame):
    """The seven buttons of the Test List, in one ``wtmhCard``. Disabled buttons stay visible."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhCard")
        self.setStyleSheet(PANEL_STYLE)
        self.setMinimumWidth(PANEL_WIDTH)
        column = QVBoxLayout(self)
        column.setContentsMargins(PANEL_PADDING, PANEL_PADDING, PANEL_PADDING, PANEL_PADDING)
        column.setSpacing(0)
        self.add_button = self._row("Add New Test", TERTIARY, column)
        self._rule(column)
        self.configure_button = self._row("Configure Test", TERTIARY, column)
        self.run_button = self._row("Run Test", PRIMARY, column)
        self.report_button = self._row("View Report", TERTIARY, column)
        self._rule(column)
        self.copy_button = self._row("Copy Test", TERTIARY, column)
        self.delete_button = self._row("Delete Test", TERTIARY, column)
        self.delete_button.setIcon(glyph_icon(GLYPH_SQUARE, DANGER, TEXT_DISABLED))  # V2
        self.delete_button.setIconSize(QSize(12, 12))
        self._rule(column)
        # Outside the row matrix: on whenever the subject has a folder (SPEC-subject-data-
        # layout.md H6, wireframe W2), whichever row is selected.
        self.open_folder_button = self._row("Open Subject Folder", TERTIARY, column)

    @staticmethod
    def _row(text: str, tier: str, layout: QVBoxLayout) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)
        button.setAutoDefault(False)
        layout.addWidget(button)
        return button

    @staticmethod
    def _rule(layout: QVBoxLayout) -> None:
        rule = QFrame()
        rule.setObjectName("wtmhTestRule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
