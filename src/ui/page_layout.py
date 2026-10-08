"""The page frame of the operator pages (SPEC-design-system-phase2.md H4-H7; ``docs/design/
fable-proposal.md`` 2.3).

Form pages keep their content in a column at most 1200 px wide, left-aligned, with a 32 px
gutter: :func:`content_column` gives a page that column. :func:`labeled` is one form field
(the label 4 px above its control, the control a fixed width by content); the gap constants
are the proposal's. The widths are set in code, so they hold on any screen; nothing here
depends on a measured size.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

CONTENT_MAX_WIDTH = 1200  # a form page's column
# The dashboard sheet's scroll bar is 10 px wide (wtmh_theme.py). A page whose cards scroll
# makes its column this much wider than CONTENT_MAX_WIDTH and limits the content to
# CONTENT_MAX_WIDTH, so the cards are 1200 px wide with the bar beside them, not under it.
SCROLLBAR_GUTTER = 10
PAGE_GUTTER = 32  # left and right
PAGE_MARGIN_V = 24  # top and bottom
CARD_GAP = 24  # between two cards
CARD_PADDING = 24
LABEL_GAP = 4  # between a label and its control
FIELD_GAP = 16  # between two fields

# Field widths by content (2.3)
SUBJECT_ID_WIDTH = 320
DATE_WIDTH = 200
SEX_WIDTH = 240
ADDRESS_WIDTH = 320
PORT_WIDTH = 120
POINT_COUNT_WIDTH = 100
NOTES_HEIGHT = 84  # three lines
CONTINUE_WIDTH = 240  # Setup's Continue to Tests button


def content_column(
    page: QWidget,
    max_width: int = CONTENT_MAX_WIDTH,
    *,
    margins: tuple[int, int, int, int] = (PAGE_GUTTER, PAGE_MARGIN_V, PAGE_GUTTER, PAGE_MARGIN_V),
) -> QVBoxLayout:
    """Give ``page`` one column at most ``max_width`` px wide, left-aligned, and return the
    column's layout (zero margins) for the page's own widgets. Any room the page has beyond
    ``max_width`` stays empty at the right."""
    root = QHBoxLayout(page)
    root.setContentsMargins(*margins)
    root.setSpacing(0)
    column = QWidget()
    column.setObjectName("wtmhPageColumn")
    column.setMaximumWidth(max_width)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(CARD_GAP)
    root.addWidget(column, 1000)
    root.addStretch(1)
    page.content_column_widget = column  # type: ignore[attr-defined]  # for tests and the hub
    return layout


def labeled(
    text: str, field: QWidget, *, width: int | None = None, hint: QWidget | None = None
) -> QWidget:
    """One form field: ``text`` 4 px above ``field``, the field ``width`` px wide and at the
    left of its container, and an optional ``hint`` line 4 px under it. The container's
    ``.label`` is the label."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(LABEL_GAP)
    label = QLabel(text)
    box.label = label  # type: ignore[attr-defined]
    layout.addWidget(label)
    if width is not None:
        field.setFixedWidth(width)
        layout.addWidget(field, 0, Qt.AlignmentFlag.AlignLeft)
    else:
        layout.addWidget(field)
    if hint is not None:
        layout.addWidget(hint)
    return box
