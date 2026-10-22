"""The look of the Test List's table rows and right-side buttons (SPEC-test-list-visual-
identity.md, direction C "Signal"; wireframe ``docs/wireframes/test-list-alt-c.md``).

The grid, the header band, the widths and the selected row stay as they were; what this adds is a
glyph on every button (in a 24 px slot, the label left-aligned after it), a glyph before every task
name, the row hover, and a right-aligned Date. Every colour is a token; the sheets are applied to
the Test List's own widgets only, so the other dashboard tables and buttons keep the global rules of
:mod:`~src.ui.wtmh_theme` and :mod:`~src.ui.wtmh_controls`.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from .design_tokens import ACCENT, ACCENT_DISABLED_TEXT, PANEL, TEXT_DISABLED
from .glyphs import (
    GLYPH_TASK_CHOICE,
    GLYPH_TASK_FOLLOW,
    GLYPH_TASK_GRID,
    GLYPH_TASK_SEARCH,
    GLYPH_TASK_STATIC,
    glyph_icon,
)

GLYPH_PX = 12  # a glyph, on a button and in the Task column
BUTTON_SLOT_PX = 24  # the square slot a button's glyph is centred in, so the labels line up
# The right padding of the Date header: the 8 px of every header section plus the 3 px an item's text
# keeps from its cell's edge, so the label ends over the right edge of the dates; and while the list is
# sorted by Date, the room the sort arrow takes at the right end of the section.
DATE_HEADER_PAD_PX = 11
SORT_ARROW_PAD_PX = 27

# The theme pads every header section by 6 px 8 px, the hidden vertical header included, which
# makes each row about 13 px taller than its text. The Date column is the last one: its header label is
# right-aligned (``test_list_table``) and padded to end over the dates.
TABLE_STYLE = f"""
QHeaderView::section:vertical {{ padding: 0px; border: none; }}
QHeaderView::section:last {{ padding-right: {DATE_HEADER_PAD_PX}px; }}
QHeaderView[sortedByDate="true"]::section:last {{ padding-right: {SORT_ARROW_PAD_PX}px; }}
"""

# The label sits left, after the glyph, instead of centred.
BUTTON_STYLE = "QPushButton { text-align: left; }"

# Task id to the glyph before its name in the Task column; a task with no entry has no glyph.
TASK_GLYPH = {
    "click_static": GLYPH_TASK_STATIC,
    "click_grid": GLYPH_TASK_GRID,
    "follow_moving": GLYPH_TASK_FOLLOW,
    "scanning": GLYPH_TASK_SEARCH,
    "choice_making": GLYPH_TASK_CHOICE,
}


def style_action_button(button: QPushButton, shape: str, *, primary: bool = False, colour: str | None = None) -> None:
    """Give a right-side button its glyph and the left-aligned label. The glyph takes the tier's
    text colour (``colour`` overrides it: Delete Test's red square), and the greyed one the tier's
    disabled text colour, so glyph and label always agree."""
    off = ACCENT_DISABLED_TEXT if primary else TEXT_DISABLED
    button.setIcon(glyph_icon(shape, colour or (PANEL if primary else ACCENT), off, GLYPH_PX, BUTTON_SLOT_PX))
    button.setIconSize(QSize(BUTTON_SLOT_PX, BUTTON_SLOT_PX))
    button.setStyleSheet(BUTTON_STYLE)


def task_icon(task_id: str) -> QIcon | None:
    """The glyph icon of a task (ACCENT, also while the row is selected), or ``None``."""
    shape = TASK_GLYPH.get(task_id)
    return glyph_icon(shape, ACCENT, ACCENT, GLYPH_PX) if shape else None
