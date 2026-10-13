"""The head-position block of the Setup page's Calibration card and the Start page's clinician
text (SPEC-gaze-stability-and-positioning.md 4.7, G1): a "Head position" heading, the picture
(:class:`~src.ui.head_position_widget.HeadPositionWidget`) and one status line, glyph + hint +
distance.

The panel polls its source about 15 times a second on the GUI thread while it is visible
(the timer stops when the page is hidden) and feeds it through the timing rules of
:class:`~src.inputs.head_position.HeadPositionTracker`. The source says whether a tracker is
connected and gives its latest eye position; both pages hand it ``SetupPage.head_position_input``.
It **gates nothing**: it is information for the operator.

:meth:`HeadPositionPanel.snapshot` is the reading at one moment, for the run's
``metadata.json`` (``head_position_at_start``, 4.7).
"""

from __future__ import annotations

import inspect
import time
import weakref
from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..inputs.head_position import EyePosition, HeadPositionTracker, HeadReading, HeadState
from .design_tokens import INK, TYPE_BODY
from .head_position_widget import WIDGET_WIDTH, HeadPositionWidget
from .status_badge import StatusBadge

POLL_INTERVAL_MS = 67  # about 15 Hz
TITLE = "Head position"

# (tracker connected, the latest eye position): what a page's ``head_position_input`` returns.
HeadPositionSource = Callable[[], tuple[bool, EyePosition | None]]

# The status line's glyph and colours are the existing badge looks: the circle for green, the
# triangle for orange, the square for red, the plain ring when there is nothing to judge.
_BADGE_KINDS = {
    HeadState.GREEN: "tracking_ok",
    HeadState.ORANGE: "data_missing",
    HeadState.RED: "disconnected",
    HeadState.NO_EYES: "not_done",
    HeadState.NOT_CONNECTED: "not_done",
}


class HeadPositionPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        source: HeadPositionSource | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhHeadPositionPanel")
        self._source_ref: Callable[[], HeadPositionSource | None] | None = None
        self.set_source(source, poll=False)
        self._clock = clock
        self._tracker = HeadPositionTracker()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.title_label = QLabel(TITLE)
        self.title_label.setStyleSheet(f"font-size: {TYPE_BODY}px; font-weight: 600; color: {INK};")
        layout.addWidget(self.title_label)
        self.picture = HeadPositionWidget()
        layout.addWidget(self.picture)
        self.status_badge = StatusBadge("not_done")
        layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.setFixedWidth(WIDGET_WIDTH)

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)
        self.poll()

    # -- public API -----------------------------------------------------------

    def set_source(self, source: HeadPositionSource | None, *, poll: bool = True) -> None:
        """Where the eye positions come from; none shows "Tracker not connected".

        A bound method is held weakly: ``SetupPage.head_position_input`` handed to the panel the
        page itself owns would be a reference cycle between two Qt widgets, which the garbage
        collector tears down in an order that crashes PySide (an access violation in a later
        test). A plain function or lambda is held as given."""
        if source is None:
            self._source_ref = None
        elif inspect.ismethod(source):
            self._source_ref = weakref.WeakMethod(source)
        else:
            self._source_ref = lambda: source
        if poll:
            self.poll()

    def poll(self) -> HeadReading:
        """Read the source once and show the result (what the timer does ~15 times a second)."""
        source = self._source_ref() if self._source_ref is not None else None
        connected, eyes = source() if source is not None else (False, None)
        reading = self._tracker.update(connected, eyes, self._clock())
        self.picture.set_reading(reading)
        kind = _BADGE_KINDS[reading.state]
        text = reading.status_text()
        if (self.status_badge.kind(), self.status_badge.text()) != (kind, text):
            self.status_badge.set_state(kind, text)
        return reading

    def reading(self) -> HeadReading | None:
        """The reading shown now."""
        return self._tracker.reading

    def snapshot(self) -> dict[str, object]:
        """The reading at this moment as ``head_position_at_start`` for ``metadata.json``:
        read afresh, so it is the one the operator sees as Start is pressed."""
        reading = self.poll()
        return reading.as_metadata()

    # -- the timer follows visibility --------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.poll()
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._timer.stop()
        super().hideEvent(event)
