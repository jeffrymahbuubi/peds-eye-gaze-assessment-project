"""The configuration page's footer row (SPEC-design-system-phase2.md H6, C5).

Preview Test / Save & Continue / Cancel are centred under the three columns, in a row as wide
as the card grid (:data:`~src.ui.config_form.CONTENT_MAX_WIDTH`) and, like the grid, at the
left of the page. The reason Save is off (or a note) sits right of the buttons; an equal
stretch each side keeps the buttons in the middle however long that text is.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


def centered_footer(
    buttons: Sequence[QPushButton], message: QLabel, max_width: int
) -> QHBoxLayout:
    """A layout to add to the page: a footer row at most ``max_width`` px wide, left-aligned,
    with ``buttons`` in its middle and ``message`` beside them."""
    footer = QWidget()
    footer.setObjectName("cfgFooter")
    footer.setMaximumWidth(max_width)
    row = QHBoxLayout(footer)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addStretch(1)
    for index, button in enumerate(buttons):
        if index:
            row.addSpacing(10)
        row.addWidget(button)
    # The message's own left margin is the gap to the buttons, so the stretch on the left and
    # the message's width on the right are equal and the buttons stay in the middle. Ignored:
    # the text's own width must not decide its share.
    message.setContentsMargins(16, 0, 0, 0)
    message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    row.addWidget(message, 1)

    holder = QHBoxLayout()
    holder.setContentsMargins(0, 0, 0, 0)
    holder.addWidget(footer, 1000)
    holder.addStretch(1)
    return holder
