"""The Test List's rows as record cards (SPEC-test-list-visual-identity.md 4.3, direction B;
wireframe ``docs/wireframes/test-list-alt-b.md``).

Look only: the table is still the ``QTableWidget`` of :mod:`~src.ui.test_list_table` (sorting,
selection, the rename editor and the keys are Qt's and the page's). What changes is how it is
painted. The table has no frame, no grid and a PAGE background; each row section is
``TABLE_ROW_HEIGHT`` plus ``CARD_GAP`` high, and :class:`CardRowDelegate` paints one white card
(``RADIUS`` corners, a 1 px ``BORDER_SUBTLE`` edge) across the row, centred in its section, so
the cards sit ``CARD_GAP`` apart and a cell widget (the Status badge) stays centred on the card.
Selected: ``ROW_SELECTED`` with a 1 px ``ACCENT`` edge; under the mouse: ``ACCENT_SUBTLE``;
keyboard focus: the selected card's edge becomes the 2 px ``ACCENT_FOCUS`` border of every
focusable control, drawn inside the card so nothing moves.

:class:`CardHeader` paints the column labels as floating captions on PAGE (12 px / 600
``TEXT_SECONDARY``, ``ACCENT_SUBTLE`` under the mouse) with an ``ACCENT`` sort arrow; they are
still the clickable sort headers. Numeric columns (the Date) are right-aligned, label and cells.

The sheets are set on the Test List's own table and empty-state frame, so the other dashboard
tables keep the global rule of ``wtmh_controls.py``. Colours, sizes and radii are tokens.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QEvent, QModelIndex, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from .design_tokens import (
    ACCENT,
    ACCENT_FOCUS,
    ACCENT_SUBTLE,
    BORDER_SUBTLE,
    BORDER_WIDTH,
    FOCUS_BORDER_WIDTH,
    INK,
    PAGE,
    PANEL,
    RADIUS,
    ROW_SELECTED,
    TABLE_ROW_HEIGHT,
    TEXT_SECONDARY,
    TYPE_BODY,
    TYPE_CAPTION,
)

CARD_GAP = 8  # PAGE between two cards
ROW_SECTION = TABLE_ROW_HEIGHT + CARD_GAP  # a row's section: the card, centred, with half the gap each side
HEADER_HEIGHT = 32  # the floating labels' row
PAD_FIRST = 16  # the card's left padding, and the first label's
PAD_LAST = 16  # ... and the right padding of the last column
PAD = 8  # every other column's side padding
ARROW_W, ARROW_H, ARROW_GAP = 8, 5, 6  # the sort arrow and its gap to the label

TABLE_STYLE = f"""
QTableWidget#wtmhTestTable {{ background: {PAGE}; border: none; border-radius: 0px; outline: 0; }}
QTableWidget#wtmhTestTable:focus {{ border: none; }}
QTableWidget#wtmhTestTable QHeaderView {{ background: {PAGE}; border: none; }}
QHeaderView::section:vertical {{ padding: 0px; border: none; }}
"""

# The empty state is one card in the list area, not a framed sheet (square corners are a table's).
EMPTY_STYLE = f"""
QFrame#wtmhEmptyTable {{
    background: {PANEL};
    border: {BORDER_WIDTH}px solid {BORDER_SUBTLE};
    border-radius: {RADIUS}px;
}}
"""


def _padding(column: int, last: int) -> tuple[int, int]:
    """The ``(left, right)`` padding of ``column`` inside the card."""
    return (PAD_FIRST if column == 0 else PAD, PAD_LAST if column == last else PAD)


def card_colours(*, selected: bool, hover: bool, focused: bool) -> tuple[str, str, int]:
    """``(fill, edge, edge width)`` of a row card. A selected card keeps its fill under the
    mouse; the keyboard focus only changes the selected card's edge."""
    if selected:
        return ROW_SELECTED, (ACCENT_FOCUS if focused else ACCENT), (FOCUS_BORDER_WIDTH if focused else BORDER_WIDTH)
    return (ACCENT_SUBTLE if hover else PANEL), BORDER_SUBTLE, BORDER_WIDTH


def _rounded(rect: QRectF) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, RADIUS, RADIUS)
    return path


class CardRowDelegate(QStyledItemDelegate):
    """Paints one cell of a row card: the card's piece under it (the whole card is clipped to
    the cell, so the cells join without a seam), then the cell's text in ``INK`` at the body step.
    ``text=False`` leaves the text out (the Status cell: a badge widget sits over it);
    ``semibold`` is the Test Name (a name, not a state); ``tabular`` gives the digits one width.
    It holds no reference to the table; the view comes with the option."""

    def __init__(
        self, parent: QWidget | None = None, *, text: bool = True, semibold: bool = False, tabular: bool = False
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._semibold = semibold
        self._tabular = tabular

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        view = option.widget
        cell = option.rect
        last = index.model().columnCount() - 1
        left = view.columnViewportPosition(0) if view is not None else cell.left()
        right = (view.columnViewportPosition(last) + view.columnWidth(last)) if view is not None else cell.right()
        top = cell.top() + (cell.height() - TABLE_ROW_HEIGHT) // 2
        card = QRectF(left, top, right - left, TABLE_ROW_HEIGHT)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = view is not None and getattr(view, "hover_row", -1) == index.row()
        focused = selected and view is not None and view.hasFocus()
        fill, edge, width = card_colours(selected=selected, hover=hover, focused=focused)

        painter.save()
        painter.setClipRect(cell)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The view has already filled a selected cell with its own row colour (the style's
        # row background); the gap between two cards is PAGE, so wipe the cell first.
        painter.fillRect(cell, QColor(PAGE))
        painter.fillPath(_rounded(card), QColor(fill))
        half = width / 2.0
        painter.setPen(QPen(QColor(edge), width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card.adjusted(half, half, -half, -half), RADIUS - half, RADIUS - half)
        if self._text:
            self._paint_text(painter, option, index, last)
        painter.restore()

    def _paint_text(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex, last: int) -> None:
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        font = QFont(item.font)
        font.setPixelSize(TYPE_BODY)
        if self._semibold:
            font.setWeight(QFont.Weight.DemiBold)
        if self._tabular and hasattr(QFont, "Tag"):  # QFont.setFeature is Qt 6.7+
            font.setFeature(QFont.Tag("tnum"), 1)
        pad_left, pad_right = _padding(index.column(), last)
        rect = option.rect.adjusted(pad_left, 0, -pad_right, 0)
        raw = index.data(Qt.ItemDataRole.TextAlignmentRole)
        align = int(raw) if raw is not None else int(Qt.AlignmentFlag.AlignLeft)
        painter.setFont(font)
        painter.setPen(QColor(INK))
        painter.drawText(
            rect,
            align | int(Qt.AlignmentFlag.AlignVCenter),
            QFontMetrics(font).elidedText(item.text, Qt.TextElideMode.ElideRight, rect.width()),
        )


class CardHeader(QHeaderView):
    """The column labels as floating captions (no band, no rule), still clickable to sort.
    ``right_columns`` are right-aligned like their cells. The sort arrow is an ``ACCENT``
    triangle after the label, or before it in a right-aligned column, so the label keeps
    its edge."""

    def __init__(self, parent: QWidget | None = None, right_columns: Iterable[int] = ()) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._right = frozenset(right_columns)
        self._hover = -1
        self.setMouseTracking(True)

    def hover_section(self) -> int:
        """The section under the mouse, ``-1`` for none."""
        return self._hover

    def sectionSizeFromContents(self, logicalIndex: int) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(super().sectionSizeFromContents(logicalIndex).width(), HEADER_HEIGHT)

    def _hover_at(self, section: int) -> None:
        if section != self._hover:
            self._hover = section
            self.viewport().update()

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802 (Qt naming)
        if event.type() == QEvent.Type.MouseMove:
            self._hover_at(self.logicalIndexAt(event.position().toPoint()))
        elif event.type() == QEvent.Type.Leave:
            self._hover_at(-1)
        return super().viewportEvent(event)

    def paintSection(self, painter: QPainter, rect, logicalIndex: int) -> None:  # noqa: N802 (Qt naming)
        painter.save()
        painter.setClipRect(rect)  # a label wider than its section is cut, never spilled into the next
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT_SUBTLE if logicalIndex == self._hover else PAGE))
        painter.drawRoundedRect(QRectF(rect), RADIUS, RADIUS)
        font = QFont(self.font())
        font.setPixelSize(TYPE_CAPTION)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        label = str(self.model().headerData(logicalIndex, Qt.Orientation.Horizontal) or "")
        metrics = QFontMetrics(font)
        pad_left, pad_right = _padding(logicalIndex, self.count() - 1)
        inner = rect.adjusted(pad_left, 0, -pad_right, 0)
        right = logicalIndex in self._right
        align = Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft
        painter.setPen(QColor(TEXT_SECONDARY))
        painter.drawText(inner, int(align | Qt.AlignmentFlag.AlignVCenter), label)
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logicalIndex:
            text_w = min(metrics.horizontalAdvance(label), inner.width())
            x = inner.right() + 1 - text_w - ARROW_GAP - ARROW_W if right else inner.left() + text_w + ARROW_GAP
            top = rect.top() + (rect.height() - ARROW_H) // 2  # whole pixels, so the edges are crisp
            self._paint_arrow(painter, max(float(rect.left()), x), top, self.sortIndicatorOrder())
        painter.restore()

    @staticmethod
    def _paint_arrow(painter: QPainter, x: float, top: float, order: Qt.SortOrder) -> None:
        up = order == Qt.SortOrder.AscendingOrder
        bottom = top + ARROW_H
        tip, base = (top, bottom) if up else (bottom, top)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT))
        painter.drawPolygon(
            QPolygonF([QPointF(x + ARROW_W / 2.0, tip), QPointF(x + ARROW_W, base), QPointF(x, base)])
        )
