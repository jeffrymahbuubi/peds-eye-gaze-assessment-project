"""The OS mouse cursor during a Gaze + Switch run (SPEC-input-selection-and-follow.md
4.2, I6).

The switch hardware sends a left click **at wherever the OS cursor is**. With the
pointer on gaze there is no reason for the child to see the cursor, and every reason
for it to sit on the canvas: parked on the run bar, the next press would hit Pause or
Quit. So at the start of such a run the cursor is moved to the middle of the canvas and
hidden over it (``Qt.BlankCursor``). While the run is paused the cursor is shown, so
the operator can use the bar; when it resumes it is hidden and parked again, because
the operator's last click left it on the bar.

Qt-light on purpose: the real move is :func:`_os_set_pos`, replaceable (``set_pos``)
so tests never move the machine's cursor.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor


def canvas_centre_global(canvas: Any) -> QPoint:
    """The middle of ``canvas`` in global (logical) coordinates."""
    return canvas.mapToGlobal(QPoint(canvas.width() // 2, canvas.height() // 2))


def _os_set_pos(canvas: Any) -> None:
    """Move the OS cursor to the middle of ``canvas``, on the screen it is shown on."""
    centre = canvas_centre_global(canvas)
    screen = canvas.screen()
    if screen is not None:
        QCursor.setPos(screen, centre)
    else:
        QCursor.setPos(centre)


class RunCursor:
    """Hides and parks the OS cursor over ``canvas``, and gives it back."""

    def __init__(self, canvas: Any, set_pos: Callable[[Any], None] | None = None) -> None:
        self._canvas = canvas
        self._set_pos = set_pos
        self.hidden = False
        self.park_count = 0

    def hide_and_park(self) -> None:
        """Hide the cursor over the canvas and move it to the canvas centre."""
        self._canvas.setCursor(Qt.CursorShape.BlankCursor)
        (self._set_pos or _os_set_pos)(self._canvas)
        self.hidden = True
        self.park_count += 1

    def show(self) -> None:
        """Give the cursor back (a pause, the end of the run, a quit)."""
        self._canvas.unsetCursor()
        self.hidden = False
