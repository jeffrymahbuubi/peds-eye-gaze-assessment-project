"""A gaze source driven by the mouse (SPEC-compass-task-flow.md 4B.6, B6).

Preview Test lets a clinician see and feel a configuration before the child sits
down, with no tracker and no calibration: the mouse pointer takes the place of the
gaze. :class:`MouseGazeSource` is handed to :class:`~src.app.AssessmentApp` as
``client`` and is duck-typed to the parts of
:class:`~src.inputs.gazepoint_client.GazepointClient` the app uses, so dwell by
hover, the rings, smoothing and sounds work exactly as with gaze.

The sample's x/y are the mouse position normalised to the canvas, and it is
``valid`` only while the pointer is inside the canvas; outside, the app's usual
dropout path freezes the gaze dot where it was. Nothing here is recorded: a preview
run uses a ``NullRecorder``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..data.schema import GazeSample


def _cursor_pos() -> Any:
    """The mouse position in global (logical) coordinates. Imported on use so the
    module itself needs no Qt until a real cursor is read."""
    from PySide6.QtGui import QCursor

    return QCursor.pos()


class MouseGazeSource:
    """Mouse position, shaped like a connected gaze client.

    ``cursor_pos`` replaces ``QCursor.pos`` (a callable returning a global
    ``QPoint``); tests inject it. :meth:`bind_canvas` must be called with the
    ``TaskCanvas`` the pointer is read against: the dashboard does it right after
    constructing the app. Before that :meth:`latest` returns ``None``, which
    ``EyeInput.poll`` already treats as an invalid, centred pointer.
    """

    # A mouse is not a tracker: no device facts, and not "live", so the app skips
    # the latency meter and the dropout diagnostic that only make sense for one.
    device_info = None
    is_live = False

    def __init__(self, cursor_pos: Callable[[], Any] | None = None) -> None:
        self._cursor_pos = cursor_pos or _cursor_pos
        self._canvas: Any = None

    def bind_canvas(self, canvas: Any) -> None:
        """Read the pointer relative to ``canvas`` from now on."""
        self._canvas = canvas

    def latest(self) -> GazeSample | None:
        """The pointer as a gaze sample, or ``None`` before a canvas is bound (or
        while it has no size). ``x``/``y`` are canvas-normalised and may lie outside
        [0, 1]; ``valid`` is True only for a position inside the canvas."""
        canvas = self._canvas
        if canvas is None:
            return None
        width, height = canvas.width(), canvas.height()
        if width <= 0 or height <= 0:
            return None
        local = canvas.mapFromGlobal(self._cursor_pos())
        px, py = local.x(), local.y()
        inside = 0 <= px < width and 0 <= py < height
        return GazeSample(t_ns=time.time_ns(), x=px / width, y=py / height, valid=inside)

    def is_connected(self) -> bool:
        return True

    # The rest of the client surface: nothing to connect to, stream or record.

    def connect(self, host: str = "127.0.0.1", port: int = 4242) -> None:
        return None

    def start_streaming(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def clear_raw(self) -> None:
        return None

    def drain_raw(self) -> list[tuple[int, dict[str, str]]]:
        return []
