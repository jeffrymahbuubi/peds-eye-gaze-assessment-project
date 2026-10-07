"""The Target Map's symbol legend (SPEC-compass-task-flow.md 7.1, V1).

A light tinted box under the map: each mark the map uses drawn as a small icon next to a
short label, then what its numbers mean. Body text size, dark text, so it reads without
effort (the first version was one line of small grey text). The same four entries are in
the PDF (:func:`legend_html`); the icons are drawn by the map's own code
(:func:`~src.ui.target_map_paint.paint_symbol`), so a legend icon is the mark it names.
"""

from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from .target_map_paint import paint_symbol
from .wtmh_theme import BORDER, INK, SOFT_ACCENT

# (kind of mark, label). The kinds are those of :func:`paint_symbol`.
LEGEND_ENTRIES: tuple[tuple[str, str], ...] = (
    ("hit", "Target selected (hit)"),
    ("timeout", "Target not selected"),
    ("skipped", "Trial skipped"),
    ("slot", "Layout position (cell or icon)"),
)
NUMBERS_NOTE = "Numbers = trials shown at that place"

ICON_PX = 28  # the on-screen icon's side, logical px
COLUMNS = 2  # entries per row

LEGEND_STYLE = f"""
QFrame#mapLegend {{
    background: {SOFT_ACCENT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#mapLegend QLabel {{ color: {INK}; background: transparent; }}
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
    """The legend box: four icon + label entries in a grid, then the numbers note."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapLegend")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEGEND_STYLE)
        grid = QGridLayout(self)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.icons: list[LegendIcon] = []
        self.labels: list[QLabel] = []
        for n, (kind, text) in enumerate(LEGEND_ENTRIES):
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
        rows = -(-len(LEGEND_ENTRIES) // COLUMNS)
        self.numbers_label = QLabel(NUMBERS_NOTE)
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


def legend_html(width_css_px: int | None = None, icon_css_px: int = 20) -> str:
    """The legend as HTML for the PDF: the same tinted, outlined box, the same four icons and
    labels, the same numbers note. ``width_css_px`` is the box's width in CSS px (1/96 inch;
    the map's width, so the two line up), the full text width when ``None``; ``icon_css_px``
    is the icon's side.

    One outlined cell holds an unbordered table: Qt draws a border around every cell of a
    bordered table, which would make a grid of the entries."""
    cells = []
    for kind, text in LEGEND_ENTRIES:
        src = png_data_uri(symbol_image(kind))
        cells.append(
            f'<td width="{icon_css_px + 8}" bgcolor="{SOFT_ACCENT}">'
            f'<img src="{src}" width="{icon_css_px}" height="{icon_css_px}"></td>'
            f'<td bgcolor="{SOFT_ACCENT}">{text}</td>'
        )
    rows = "".join(
        f"<tr>{''.join(cells[i:i + COLUMNS])}</tr>" for i in range(0, len(cells), COLUMNS)
    )
    inner = (
        f'<table width="100%" border="0" cellspacing="0" cellpadding="3">{rows}'
        f'<tr><td colspan="{COLUMNS * 2}" bgcolor="{SOFT_ACCENT}">{NUMBERS_NOTE}</td></tr></table>'
    )
    width = f'"{width_css_px}"' if width_css_px else '"100%"'
    return (
        f'<table width={width} border="1" cellspacing="0" cellpadding="6" '
        f'style="border-collapse:collapse; border-color:{BORDER}">'
        f'<tr><td bgcolor="{SOFT_ACCENT}">{inner}</td></tr></table>'
    )
