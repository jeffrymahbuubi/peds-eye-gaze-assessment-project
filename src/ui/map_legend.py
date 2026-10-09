"""The Target Map's symbol legend (SPEC-compass-task-flow.md 7.1, V1).

A white box with a light grey edge under the map (no tint, SPEC-design-system-phase4.md H5):
each mark the map uses drawn as a small icon next to a short label, then what the Scanpath
overlay draws (the Summary's, in its one colour) and what the numbers mean. Body size, ink
text (the user's answer of 2026-10-09: it must read without effort). The same entries are in the
PDF (:func:`legend_html`), with the Scanpath line when the PDF's map draws the scanpath; the icons
are drawn by the map's own code (:func:`~src.ui.target_map_paint.paint_symbol`), so a legend icon
is the mark it names.
"""

from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from .design_tokens import BORDER_SUBTLE, INK, PANEL, RADIUS, TYPE_BODY
from .target_map_paint import paint_symbol

# (kind of mark, label). The kinds are those of :func:`paint_symbol`.
LEGEND_ENTRIES: tuple[tuple[str, str], ...] = (
    ("hit", "Target selected (hit)"),
    ("timeout", "Target not selected"),
    ("skipped", "Trial skipped"),
    ("slot", "Layout position (cell or icon)"),
)
NUMBERS_NOTE = "Numbers = trials shown at that place"
# What the Summary's Scanpath overlay draws: one colour for every trial (X1). The on-screen Summary
# legend and the PDF's (which draws the same scanpath when gaze was recorded) have this line.
SCANPATH_NOTE = "Scanpath: fixations joined in time order, all trials"
# Follow the Target (SPEC-input-selection-and-follow.md 4.5): its marks say followed or not, it
# has no layout positions, and its map draws the target's path. The selected trial's pointer path
# is drawn solid dark where the pointer was on the target and grey and dashed where it was off it,
# so the Detailed view's own legend names those two lines (the Summary map and the PDF do not draw them).
FOLLOW_LEGEND_ENTRIES: tuple[tuple[str, str], ...] = (
    ("hit", "Trial followed"),
    ("timeout", "Trial not followed"),
    ("skipped", "Trial skipped"),
    ("track", "Path of the target"),
)
POINTER_LEGEND_ENTRIES: tuple[tuple[str, str], ...] = (
    ("on", "Pointer on target"),
    ("off", "Pointer off target"),
    ("track", "Path of the target"),
)
POINTER_NUMBERS_NOTE = "Numbers = fixations, in the order they happened"

ICON_PX = 28  # the on-screen icon's side, logical px
COLUMNS = 2  # entries per row

LEGEND_STYLE = f"""
QFrame#mapLegend {{
    background: {PANEL};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {RADIUS}px;
}}
QFrame#mapLegend QLabel {{ color: {INK}; background: transparent; font-size: {TYPE_BODY}px; }}
"""


class LegendIcon(QWidget):
    """One mark of the map, drawn small."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName(f"legendIcon_{kind}")
        self.setFixedSize(ICON_PX, ICON_PX)

    def paintEvent(self, _event: object) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        paint_symbol(painter, QRectF(self.rect()), self.kind)
        painter.end()


class MapLegend(QFrame):
    """The legend box: icon + label entries in a grid, then the overlay line (if any) and the
    numbers note. It shows the selection tasks' four marks until :meth:`set_entries` gives it
    another set."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapLegend")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEGEND_STYLE)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(14, 10, 14, 10)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(6)
        self.icons: list[LegendIcon] = []
        self.labels: list[QLabel] = []
        self.overlay_label = QLabel("")
        self.numbers_label = QLabel(NUMBERS_NOTE)
        self.set_entries(LEGEND_ENTRIES)

    def set_entries(
        self,
        entries: tuple[tuple[str, str], ...],
        numbers_note: str = NUMBERS_NOTE,
        overlay_note: str = "",
    ) -> None:
        """Show ``entries`` (``(kind, label)``, kinds as :func:`paint_symbol` draws them),
        ``overlay_note`` (what the Scanpath overlay draws; none when empty) and ``numbers_note``
        under them."""
        grid = self._grid
        for widget in (*self.icons, *self.labels, self.overlay_label, self.numbers_label):
            grid.removeWidget(widget)
            widget.hide()  # deleteLater() waits for the event loop; it must not show meanwhile
            widget.setParent(None)
            widget.deleteLater()
        for column in range(COLUMNS * 3):
            grid.setColumnMinimumWidth(column, 0)
            grid.setColumnStretch(column, 0)
        self.icons, self.labels = [], []
        for n, (kind, text) in enumerate(entries):
            row, column = divmod(n, COLUMNS)
            icon = LegendIcon(kind)
            label = QLabel(text)
            label.setObjectName(f"legendLabel_{kind}")
            self.icons.append(icon)
            self.labels.append(label)
            grid.addWidget(icon, row, column * 3)
            grid.addWidget(label, row, column * 3 + 1)
            if column < COLUMNS - 1:
                grid.setColumnMinimumWidth(column * 3 + 2, 18)  # a gap between the two columns
        rows = -(-len(entries) // COLUMNS)
        self.overlay_label = QLabel(overlay_note)
        self.overlay_label.setObjectName("legendOverlay")
        self.overlay_label.setVisible(bool(overlay_note))
        if overlay_note:
            grid.addWidget(self.overlay_label, rows, 0, 1, COLUMNS * 3 - 1)
            rows += 1
        self.numbers_label = QLabel(numbers_note)
        self.numbers_label.setObjectName("legendNumbers")
        grid.addWidget(self.numbers_label, rows, 0, 1, COLUMNS * 3 - 1)
        grid.setColumnStretch(COLUMNS * 3 - 1, 1)

    def entries(self) -> list[tuple[str, str]]:
        """``(kind, label)`` of every entry, in the order shown."""
        return [(icon.kind, label.text()) for icon, label in zip(self.icons, self.labels, strict=True)]


# -- the PDF's legend ------------------------------------------------------------------


def symbol_image(kind: str, px: int = 96) -> QImage:
    """A mark as a transparent square image (the PDF's icon; drawn large and shown small, so
    it stays sharp)."""
    image = QImage(QSize(px, px), QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    paint_symbol(painter, QRectF(image.rect()), kind)
    painter.end()
    return image


def png_data_uri(image: QImage) -> str:
    """``image`` as a ``data:`` URI of a PNG, for an ``<img>`` of the PDF's HTML."""
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return "data:image/png;base64," + base64.b64encode(bytes(data)).decode("ascii")


def legend_html(
    width_css_px: int | None = None,
    icon_css_px: int = 20,
    entries: tuple[tuple[str, str], ...] = LEGEND_ENTRIES,
    overlay_note: str = "",
) -> str:
    """The legend as HTML for the PDF: the same white, outlined box, the same icons and
    labels (``entries``: the four marks unless a Follow the Target report gives its own), the
    ``overlay_note`` line (what the scanpath on the map draws; none when empty) and the
    same numbers note. ``width_css_px`` is the box's width in CSS px (1/96 inch;
    the map's width, so the two line up), the full text width when ``None``; ``icon_css_px``
    is the icon's side.

    One outlined cell holds an unbordered table: Qt draws a border around every cell of a
    bordered table, which would make a grid of the entries."""
    cells = []
    for kind, text in entries:
        src = png_data_uri(symbol_image(kind))
        cells.append(
            f'<td width="{icon_css_px + 8}">'
            f'<img src="{src}" width="{icon_css_px}" height="{icon_css_px}"></td>'
            f"<td>{text}</td>"
        )
    rows = "".join(
        f"<tr>{''.join(cells[i:i + COLUMNS])}</tr>" for i in range(0, len(cells), COLUMNS)
    )
    overlay = f'<tr><td colspan="{COLUMNS * 2}">{overlay_note}</td></tr>' if overlay_note else ""
    inner = (
        f'<table width="100%" border="0" cellspacing="0" cellpadding="3">{rows}{overlay}'
        f'<tr><td colspan="{COLUMNS * 2}">{NUMBERS_NOTE}</td></tr></table>'
    )
    width = f'"{width_css_px}"' if width_css_px else '"100%"'
    return (
        f'<table width={width} border="1" cellspacing="0" cellpadding="6" '
        f'style="border-collapse:collapse; border-color:{BORDER_SUBTLE}">'
        f"<tr><td>{inner}</td></tr></table>"
    )
