"""The Check accuracy view of the calibration window (SPEC-app-drawn-calibration.md 4.8 R3, D10;
wireframe ``docs/wireframes/calibration-window.md`` state 6).

A copy of Gazepoint Control's after-calibration window (``resources/images/window-after-
calibration.png``): eleven rings in rows of 4-3-4, each with a small "+" at its centre, and a live
green trail of where the tracker puts the gaze. The child or the operator looks at any ring and
sees whether the trail sits on it. Nothing here is recorded.

* **Rings:** centres at x 18 / 39 / 61 / 82 % (top and bottom rows) and 29 / 50 / 71 % (middle row),
  y 18 / 50 / 82 % of the window, which covers the tracked monitor. The radius is
  :data:`RING_RADIUS_DEG` of visual angle (the viewing distance and the screen's mm per px, like the
  icon sizes of 4.3b). Ring and "+" use the background's contrast colour.
* **Trail:** the last :data:`TRAIL_S` second of valid, **unsmoothed** gaze (the session's POG as
  recorded, not the cursor filter), as small circles joined by a thin line, read from the tracker
  client the page already has (no new socket). No gaze for :data:`NO_GAZE_S` fades the trail out
  and replaces the eye lines with :data:`NO_GAZE_TEXT`.
* **Eye lines:** "Left eye: n of N points valid" and "Right eye: ..." from ``CALIB_RESULT``.
* **Buttons:** Repeat calibration, Results and Done; Esc and the x are Done (the window's).

:class:`GazeTrail` is Qt-free and takes the time as an argument; the view reads the time from an
injected clock and the gaze from an injected source (a callable returning the newest
:class:`~src.data.schema.GazeSample` or None), so a test drives it with a fake clock and a fake gaze.
"""

from __future__ import annotations

import inspect
import math
import time
import weakref
from collections import deque
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..data.schema import GazeSample
from ..engine.calibration_settings import BACKGROUNDS, CalibrationSettings, EyeCounts
from ..engine.target_size import DEFAULT_VIEWING_DISTANCE_MM, REFERENCE_MM_PER_PX
from .design_tokens import INK, PANEL, SUCCESS_TEXT, TYPE_BODY_LARGE
from .wtmh_theme import STYLESHEET

# Where Gazepoint Control draws its eleven rings (fractions of the window): rows of 4, 3 and 4.
RING_ROWS: tuple[tuple[float, tuple[float, ...]], ...] = (
    (0.18, (0.18, 0.39, 0.61, 0.82)),
    (0.50, (0.29, 0.50, 0.71)),
    (0.82, (0.18, 0.39, 0.61, 0.82)),
)
RING_POSITIONS: tuple[tuple[float, float], ...] = tuple((x, y) for y, xs in RING_ROWS for x in xs)
RING_RADIUS_DEG = 3.0
RING_LINE_PX = 2
PLUS_ARM_PX = 9

TRAIL_S = 1.0  # the trail shows this much of the past
NO_GAZE_S = 0.5  # no valid gaze for this long: the trail fades and the hint appears
FADE_S = 0.4  # ... and is gone this much later
TRAIL_DOT_PX = 4.0
TRAIL_LINE_PX = 1.5
FRAME_MS = 16  # about 60 frames a second while the view is up

# Stimulus colours, not UI chrome (like the backgrounds): a dark green on the light backgrounds, a
# light one on black.
GREEN_ON_LIGHT = SUCCESS_TEXT
GREEN_ON_BLACK = "#4CE06A"

CHECK_ACCURACY = "Check accuracy"
REPEAT = "Repeat calibration"
RESULTS = "Results"
DONE = "Done"
NO_GAZE_TEXT = "No gaze. Check the head position."
MARGIN_PX = 24

GazeSource = Callable[[], GazeSample | None]


def ring_radius_px(mm_per_px: float, viewing_distance_mm: float | None = None) -> float:
    """The rings' radius in the pixels ``mm_per_px`` is per: ``D * tan(3 deg) / mm_per_px``, the
    distance on screen of a gaze error of :data:`RING_RADIUS_DEG` (per Qt logical px for a widget
    that paints in logical px, like :func:`~src.engine.calibration_settings.icon_diameter_px`)."""
    distance = viewing_distance_mm if viewing_distance_mm and viewing_distance_mm > 0 else DEFAULT_VIEWING_DISTANCE_MM
    scale = mm_per_px if mm_per_px and mm_per_px > 0 else REFERENCE_MM_PER_PX
    return distance * math.tan(math.radians(RING_RADIUS_DEG)) / scale


def eye_lines(counts: EyeCounts | None) -> tuple[str, str]:
    """The two status lines under the rings; empty without a ``CALIB_RESULT``."""
    if counts is None:
        return "", ""
    return (
        f"Left eye: {counts.left} of {counts.total} points valid",
        f"Right eye: {counts.right} of {counts.total} points valid",
    )


class GazeTrail:
    """The recent valid gaze, and how long it has been silent (Qt-free; the time is an argument).

    ``add`` records a valid sample seen at ``now``; ``points(now)`` are the ones of the last
    ``trail_s``; ``opacity(now)`` is 1 until ``no_gaze_s`` pass with no valid sample, then falls to
    0 over ``fade_s``. Before the first sample the silence is counted from ``reset``.
    """

    def __init__(self, trail_s: float = TRAIL_S, no_gaze_s: float = NO_GAZE_S, fade_s: float = FADE_S) -> None:
        self.trail_s = trail_s
        self.no_gaze_s = no_gaze_s
        self.fade_s = fade_s
        self._samples: deque[tuple[float, float, float]] = deque()  # (time seen, x, y)
        self._last_seen: float | None = None
        self._since = 0.0

    def reset(self, now: float) -> None:
        self._samples.clear()
        self._last_seen = None
        self._since = now

    def add(self, now: float, x: float, y: float) -> None:
        self._samples.append((now, x, y))
        self._last_seen = now
        self._drop_old(now)

    def _drop_old(self, now: float) -> None:
        while self._samples and now - self._samples[0][0] > self.trail_s:
            self._samples.popleft()

    def points(self, now: float) -> list[tuple[float, float]]:
        """The ``(x, y)`` of the valid samples of the last ``trail_s``, oldest first."""
        self._drop_old(now)
        return [(x, y) for _t, x, y in self._samples]

    def silent_s(self, now: float) -> float:
        """How long ago the last valid sample was seen (or the trail was reset)."""
        return now - (self._last_seen if self._last_seen is not None else self._since)

    def no_gaze(self, now: float) -> bool:
        return self.silent_s(now) >= self.no_gaze_s

    def opacity(self, now: float) -> float:
        over = self.silent_s(now) - self.no_gaze_s
        if over <= 0:
            return 1.0
        return max(0.0, 1.0 - over / self.fade_s) if self.fade_s > 0 else 0.0


class CalibrationCheckView(QWidget):
    repeatRequested = Signal()  # Repeat calibration: the window's Improve (a full re-run)
    resultsRequested = Signal()  # back to the results map
    doneRequested = Signal()  # Done: the window's Back (keeps the result)

    def __init__(
        self,
        settings: CalibrationSettings,
        mm_per_px: float,
        viewing_distance_mm: float,
        *,
        gaze_source: GazeSource | None = None,
        clock: Callable[[], float] = time.monotonic,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("calibrationCheck")
        self._clock = clock
        self._mm_per_px = mm_per_px
        self._distance_mm = viewing_distance_mm
        self._source_ref: Callable[[], GazeSource | None] | None = None
        self.set_source(gaze_source)
        self.trail = GazeTrail()
        self._last_stamp: int | None = None  # t_ns of the sample read last: only a new one is added
        self._counts: EyeCounts | None = None
        dark = settings.background == "black"
        self._background = QColor(BACKGROUNDS[settings.background])
        self._ink = QColor(PANEL) if dark else QColor(INK)
        self._green = QColor(GREEN_ON_BLACK if dark else GREEN_ON_LIGHT)

        self.setStyleSheet(STYLESHEET)  # the button tiers; the view paints its own background
        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN_PX, MARGIN_PX, MARGIN_PX, MARGIN_PX)
        outer.setSpacing(4)
        outer.addStretch(1)
        eye_style = f"color: {self._green.name()}; font-size: {TYPE_BODY_LARGE}px; background: transparent;"
        self.left_label = self._status_label("calibrationCheckLeft", eye_style)
        self.right_label = self._status_label("calibrationCheckRight", eye_style)
        self.hint_label = self._status_label(
            "calibrationCheckHint",
            f"color: {self._ink.name()}; font-size: {TYPE_BODY_LARGE}px; background: transparent;",
        )
        self.hint_label.setText(NO_GAZE_TEXT)
        for label in (self.left_label, self.right_label, self.hint_label):
            outer.addWidget(label)
        outer.addSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.repeat_button = self._button("calibrationRepeat", REPEAT, "wtmhGhost", self.repeatRequested)
        self.results_button = self._button("calibrationResults", RESULTS, "wtmhGhost", self.resultsRequested)
        self.done_button = self._button("calibrationDone", DONE, "wtmhPrimary", self.doneRequested)
        row.addWidget(self.repeat_button)
        row.addWidget(self.results_button)
        row.addStretch(1)
        row.addWidget(self.done_button)
        outer.addLayout(row)
        self.hint_label.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.tick)

    # -- building ------------------------------------------------------------------------------

    @staticmethod
    def _status_label(name: str, style: str) -> QLabel:
        label = QLabel("")
        label.setObjectName(name)
        label.setStyleSheet(style)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    @staticmethod
    def _button(name: str, text: str, tier: str, signal: Any) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)  # the theme styles the tiers by object name
        button.setAccessibleName(name)
        button.setAutoDefault(False)
        button.clicked.connect(lambda _checked=False: signal.emit())
        return button

    # -- the gaze source and the result -----------------------------------------------------------

    def set_source(self, source: GazeSource | None) -> None:
        """Where the newest gaze sample comes from. A bound method is held weakly, like the
        head-position panel's source: a page's method handed to a widget the page owns would be a
        reference cycle between two Qt objects, which the garbage collector tears down in an order
        that crashes PySide."""
        if source is None:
            self._source_ref = None
        elif inspect.ismethod(source):
            self._source_ref = weakref.WeakMethod(source)
        else:
            self._source_ref = lambda: source

    def _read(self) -> GazeSample | None:
        source = self._source_ref() if self._source_ref is not None else None
        return source() if source is not None else None

    def set_result(self, counts: EyeCounts | None) -> None:
        """The valid points per eye of the calibration being checked (``CALIB_RESULT``)."""
        self._counts = counts
        left, right = eye_lines(counts)
        self.left_label.setText(left)
        self.right_label.setText(right)
        self._refresh_status(self._clock())

    # -- running -------------------------------------------------------------------------------

    def start(self) -> None:
        """The view is up: an empty trail, the gaze already waiting not counted (only a sample that
        arrives from now on is), and the timer on."""
        now = self._clock()
        self.trail.reset(now)
        sample = self._read()
        self._last_stamp = sample.t_ns if sample is not None else None
        self._refresh_status(now)
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def tick(self) -> None:
        """Read the newest gaze sample once and repaint (what the timer does ~60 times a second):
        a sample not seen before and valid joins the trail."""
        now = self._clock()
        sample = self._read()
        if sample is not None and sample.t_ns != self._last_stamp:
            self._last_stamp = sample.t_ns
            if sample.valid:
                self.trail.add(now, sample.x, sample.y)
        self._refresh_status(now)
        self.update()

    def _refresh_status(self, now: float) -> None:
        """The eye lines, or the no-gaze hint in their place (wireframe state 6)."""
        silent = self.trail.no_gaze(now)
        self.hint_label.setVisible(silent)
        self.left_label.setVisible(not silent and bool(self.left_label.text()))
        self.right_label.setVisible(not silent and bool(self.right_label.text()))

    def status_lines(self) -> list[str]:
        """The status lines showing now, top to bottom."""
        return [
            label.text() for label in (self.left_label, self.right_label, self.hint_label)
            if label.isVisibleTo(self) and label.text()
        ]

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._timer.stop()
        super().hideEvent(event)

    # -- the picture ------------------------------------------------------------------------------

    def ring_radius_px(self) -> float:
        return ring_radius_px(self._mm_per_px, self._distance_mm)

    def ring_centres(self) -> list[QPointF]:
        """The eleven ring centres in this widget's px."""
        return [QPointF(x * self.width(), y * self.height()) for x, y in RING_POSITIONS]

    def trail_centres(self, now: float | None = None) -> list[QPointF]:
        """The trail's circles in this widget's px (gaze x and y are fractions of the screen)."""
        moment = self._clock() if now is None else now
        return [QPointF(x * self.width(), y * self.height()) for x, y in self.trail.points(moment)]

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._background)
        self._paint_rings(painter)
        self._paint_trail(painter, self._clock())
        painter.end()

    def _paint_rings(self, painter: QPainter) -> None:
        radius = self.ring_radius_px()
        painter.setPen(QPen(self._ink, RING_LINE_PX))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for centre in self.ring_centres():
            painter.drawEllipse(centre, radius, radius)
            painter.drawLine(QPointF(centre.x() - PLUS_ARM_PX, centre.y()), QPointF(centre.x() + PLUS_ARM_PX, centre.y()))
            painter.drawLine(QPointF(centre.x(), centre.y() - PLUS_ARM_PX), QPointF(centre.x(), centre.y() + PLUS_ARM_PX))

    def _paint_trail(self, painter: QPainter, now: float) -> None:
        opacity = self.trail.opacity(now)
        centres = self.trail_centres(now)
        if opacity <= 0 or not centres:
            return
        colour = QColor(self._green)
        colour.setAlphaF(opacity)
        painter.setPen(QPen(colour, TRAIL_LINE_PX))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for start, end in zip(centres, centres[1:], strict=False):
            painter.drawLine(start, end)
        for centre in centres:
            painter.drawEllipse(centre, TRAIL_DOT_PX, TRAIL_DOT_PX)
