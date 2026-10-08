"""The alert box: a glyph tile, a bold state word and the text (SPEC-design-system-phase2.md
H3; ``docs/design/fable-proposal.md`` 2.5).

White fill and a 1 px border in the state colour, no left stripe, no tint. At the left a 20 px
glyph tile (a square for a danger, a triangle for a warning, a filled circle for a success, an
"i" in a circle for a note), then the bold state word ("Blocked:", "Warning:", "Note:"; none
for a success), then the text at the body-large step, and at the right edge an optional
action widget (the Start page's Go to Setup). An alert sits between cards at the page level,
never inside a card (2.4).

The box styles itself (:data:`ALERT_STYLESHEET`), so it looks the same in the dashboard, in a
dialog and in the standalone window. :attr:`label` is the text label, kept under the old
``*_label`` names by the pages that hold an alert.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import (
    BORDER_STRONG,
    DANGER,
    DANGER_SUBTLE,
    DANGER_TEXT,
    HEADER,
    INK,
    PANEL,
    RADIUS,
    SUCCESS,
    SUCCESS_SUBTLE,
    SUCCESS_TEXT,
    TEXT_SECONDARY,
    TYPE_BODY_LARGE,
    WARNING,
    WARNING_SUBTLE,
    WARNING_TEXT,
)
from .glyphs import GLYPH_CIRCLE, GLYPH_INFO, GLYPH_SQUARE, GLYPH_TRIANGLE, draw_glyph

TILE_PX = 20
GLYPH_IN_TILE_PX = 12


class AlertLook(NamedTuple):
    border: str  # the box's 1 px border
    tile: str  # the fill behind the glyph (the subtle state fill)
    glyph: str  # the glyph's colour (the state's text colour: 7:1 on the tile)
    shape: str
    word: str  # the bold state word


LOOKS: dict[str, AlertLook] = {
    "danger": AlertLook(DANGER, DANGER_SUBTLE, DANGER_TEXT, GLYPH_SQUARE, "Blocked:"),
    "warning": AlertLook(WARNING, WARNING_SUBTLE, WARNING_TEXT, GLYPH_TRIANGLE, "Warning:"),
    "success": AlertLook(SUCCESS, SUCCESS_SUBTLE, SUCCESS_TEXT, GLYPH_CIRCLE, ""),
    "note": AlertLook(BORDER_STRONG, HEADER, TEXT_SECONDARY, GLYPH_INFO, "Note:"),
}
KINDS = tuple(LOOKS)

ALERT_STYLESHEET = (
    f"""
QFrame#wtmhAlert {{
    background: {PANEL};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS}px;
}}
"""
    + "".join(
        f'QFrame#wtmhAlert[kind="{kind}"] {{ border-color: {look.border}; }}\n' for kind, look in LOOKS.items()
    )
    + f"""
QFrame#wtmhAlert QLabel {{
    background: transparent;
    border: none;
    color: {INK};
    font-size: {TYPE_BODY_LARGE}px;
}}
QFrame#wtmhAlert QLabel#wtmhAlertWord {{ font-weight: 700; }}
QFrame#wtmhAlert QLabel#wtmhAlertEmphasis {{ font-weight: 600; }}
"""
)


class _GlyphTile(QWidget):
    """The 20 px tile: the subtle state fill, radius 4, the glyph centred in the state colour."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(TILE_PX, TILE_PX)
        self.look = LOOKS["note"]

    def set_kind(self, kind: str) -> None:
        self.look = LOOKS[kind]
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(TILE_PX, TILE_PX)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.look.tile))
        painter.drawRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        margin = (TILE_PX - GLYPH_IN_TILE_PX) / 2.0
        draw_glyph(
            painter, self.look.shape, QRectF(margin, margin, GLYPH_IN_TILE_PX, GLYPH_IN_TILE_PX), self.look.glyph
        )
        painter.end()


class AlertBox(QFrame):
    """An alert of one ``kind`` (``danger``, ``warning``, ``success`` or ``note``).

    ``word`` overrides the kind's state word (``""`` for none). ``stacked`` puts the word on a
    line of its own above the text (the Start page's "Blocked:" over its list of items)
    instead of in front of it. ``action`` is a widget at the right edge. :meth:`set_emphasis`
    puts a second sentence at weight 600 on a line under the text (the Mouse note's "No eye
    data will be recorded."), a label of its own so the text label keeps its plain text.
    """

    def __init__(
        self,
        kind: str = "note",
        text: str = "",
        *,
        word: str | None = None,
        stacked: bool = False,
        action: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhAlert")
        self.setStyleSheet(ALERT_STYLESHEET)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._kind = ""
        self._word_override = word

        root = self._root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 16, 10)
        root.setSpacing(12)
        self.tile = _GlyphTile()
        root.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignTop)

        self._text_layout: QBoxLayout = QVBoxLayout() if stacked else QHBoxLayout()
        self._text_layout.setSpacing(4 if stacked else 6)
        self.word_label = QLabel("")
        self.word_label.setObjectName("wtmhAlertWord")
        self.word_label.setTextFormat(Qt.TextFormat.PlainText)
        self.label = QLabel(text)
        self.label.setObjectName("wtmhAlertText")
        self.label.setTextFormat(Qt.TextFormat.PlainText)  # a message is never read as markup
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.emphasis_label = QLabel("")
        self.emphasis_label.setObjectName("wtmhAlertEmphasis")
        self.emphasis_label.setTextFormat(Qt.TextFormat.PlainText)
        self.emphasis_label.setWordWrap(True)
        self.emphasis_label.hide()
        body = QVBoxLayout()  # the text, and under it the emphasis line when there is one
        body.setSpacing(2)
        body.addWidget(self.label)
        body.addWidget(self.emphasis_label)
        self._text_layout.addWidget(self.word_label, 0, Qt.AlignmentFlag.AlignTop)
        self._text_layout.addLayout(body, 1)
        root.addLayout(self._text_layout, 1)

        self.action_widget: QWidget | None = None
        if action is not None:
            self.set_action(action)
        self.set_kind(kind)

    # -- state ------------------------------------------------------------------

    def kind(self) -> str:
        return self._kind

    def set_kind(self, kind: str, word: str | None = None) -> None:
        """Change the kind (and the state word: ``None`` keeps an override given before, else
        the kind's own)."""
        if kind not in LOOKS:
            raise ValueError(f"Unknown alert kind '{kind}'. Known: {list(KINDS)}")
        if word is not None:
            self._word_override = word
        self._kind = kind
        shown = LOOKS[kind].word if self._word_override is None else self._word_override
        self.word_label.setText(shown)
        self.word_label.setVisible(bool(shown))
        self.tile.set_kind(kind)
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)

    def word(self) -> str:
        return self.word_label.text()

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self.label.setText(text)

    def emphasis(self) -> str:
        return self.emphasis_label.text()

    def set_emphasis(self, text: str) -> None:
        """A sentence at weight 600 under the text; ``""`` hides the line."""
        self.emphasis_label.setText(text)
        self.emphasis_label.setVisible(bool(text))

    def set_action(self, widget: QWidget) -> None:
        """Put ``widget`` at the right edge, centred vertically."""
        self.action_widget = widget
        self._root.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
