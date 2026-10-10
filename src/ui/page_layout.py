"""The page frame of the operator pages (SPEC-design-system-phase2.md H4-H7 and the section 9
answer of 2026-10-09 on empty space; ``docs/design/fable-proposal.md`` 2.3).

Form pages fill the window's width inside a 32 px gutter, there is no maximum width:
:func:`page_frame` gives a page that frame. :class:`CardGrid` lays cards in two columns of equal
width, and :class:`FlowLayout` lets a row of buttons wrap when its card is narrow. :func:`labeled`
is one form field (the label 4 px above its control, the control as wide as its card);
the gap constants are the proposal's. The widths are set in code, so they hold on any screen;
nothing here depends on a measured size.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QVBoxLayout,
    QWidget,
)

PAGE_GUTTER = 32  # left and right
PAGE_MARGIN_V = 24  # top and bottom
PAGE_SPACING = 16  # between the parts of a page
CARD_GAP = 24  # between two cards, across and down
CARD_PADDING = 24
LABEL_GAP = 4  # between a label and its control
FIELD_GAP = 16  # between two fields
CARD_COLUMNS = 2  # columns of a CardGrid

# Setup's fields fill their card's width, as on feature/compass-task-flow (user, 2026-10-10)
NOTES_HEIGHT = 84  # three lines
CONTINUE_WIDTH = 240  # Setup's Continue to Tests button


def page_frame(
    page: QWidget,
    spacing: int = PAGE_SPACING,
    *,
    margins: tuple[int, int, int, int] = (PAGE_GUTTER, PAGE_MARGIN_V, PAGE_GUTTER, PAGE_MARGIN_V),
) -> QVBoxLayout:
    """Give ``page`` one column as wide as the page less its gutters and return its layout
    for the page's own widgets. Nothing caps the width: a wider window means wider cards."""
    layout = QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


class CardGrid(QVBoxLayout):
    """Cards in ``columns`` (default two) independent columns of equal width, each card at the top of its column, the
    gap between two cards the same across and down (:data:`CARD_GAP`).

    With ``columns=1`` the cards stack one per row, each as wide as the page (Setup, user
    decision of 2026-10-10: the feature/compass-task-flow arrangement).

    :meth:`add_card` puts the next card at the foot of the next column, left then right, so the
    cards read, and Tab, in the order they were added (Subject, Tracker, Display, Calibration
    are left, right, left, right). The columns are not rows: a short card does not leave a hole
    under it for a tall one beside it, the next card of its column moves up under it.
    :meth:`add_wide` puts a one-line note (not a card) across both columns under them; a card
    added after it starts a new pair of columns. :meth:`finish` takes the room left over below,
    so the cards keep their height.
    """

    def __init__(self, parent: QWidget | None = None, *, columns: int = CARD_COLUMNS) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(CARD_GAP)
        self._column_count = columns
        self._columns: list[QVBoxLayout] | None = None
        self._next = 0

    def _start_columns(self) -> list[QVBoxLayout]:
        # The layouts are attached before any card is added, so a card is reparented to the
        # page's widget at once, in the order of the calls (that order is the Tab order).
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(CARD_GAP)
        self.addLayout(row)
        columns = []
        for _ in range(self._column_count):
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(CARD_GAP)
            row.addLayout(column, 1)  # equal stretch: equal widths
            column.addStretch(1)  # keeps the cards at the top of their column
            columns.append(column)
        self._next = 0
        return columns

    def add_card(self, widget: QWidget) -> None:
        if self._columns is None:
            self._columns = self._start_columns()
        column = self._columns[self._next % self._column_count]
        column.insertWidget(column.count() - 1, widget)
        self._next += 1

    def add_wide(self, widget: QWidget) -> None:
        self.addWidget(widget)
        self._columns = None

    def finish(self) -> None:
        self.addStretch(1)


class FlowLayout(QLayout):
    """Items left to right, wrapping to a new line when the width runs out; the items of a
    line are centred on it vertically. Its minimum width is the widest item, so a card that
    holds one can be as narrow as its widest button, and its height follows the width."""

    def __init__(self, *, h_spacing: int = 6, v_spacing: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(0, 0, 0, 0)

    # -- QLayout --------------------------------------------------------------------

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 (Qt naming)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 (Qt naming)
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 (Qt naming)
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 (Qt naming)
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 (Qt naming)
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 (Qt naming)
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 (Qt naming)
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 (Qt naming)
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    # -- the lines ------------------------------------------------------------------

    def _arrange(self, rect: QRect, *, apply: bool) -> int:
        """Break the items into lines for ``rect``'s width; put them there when ``apply``.
        Returns the height the lines need, margins included."""
        margins = self.contentsMargins()
        left, right = rect.x() + margins.left(), rect.right() + 1 - margins.right()
        top = rect.y() + margins.top()
        lines: list[list[tuple[QLayoutItem, QSize]]] = [[]]
        x = left
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if lines[-1] and x + hint.width() > right:
                lines.append([])
                x = left
            lines[-1].append((item, hint))
            x += hint.width() + self._h_spacing
        y = top
        for index, line in enumerate(lines):
            line_height = max((hint.height() for _item, hint in line), default=0)
            if apply:
                x = left
                for item, hint in line:
                    width = min(hint.width(), max(right - left, item.minimumSize().width()))
                    item.setGeometry(QRect(QPoint(x, y + (line_height - hint.height()) // 2), QSize(width, hint.height())))
                    x += hint.width() + self._h_spacing
            y += line_height + (self._v_spacing if index < len(lines) - 1 else 0)
        return y + margins.bottom() - rect.y()


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
