"""The drawing surface of the calibration window while a run is on (SPEC-app-drawn-calibration.md
4.1, 4.3b, 4.6; wireframe ``docs/wireframes/calibration-window.md`` states 1 to 3).

A plain background (Setup's White, Black or Grey), the icon, and nothing else: no text, no
progress, no sound. The icon's pose comes from :class:`~src.engine.calibration_motion.TargetMotion`
as a function of the clock, so a late event never delays the hold; the stage only repaints on a
timer while a point is on. After the last point the stage shows "Processing calibration results"
with three pulsing dots until the window swaps it for the results map.

Positions are fractions of the stage (the window covers the tracked monitor, so a fraction of
the stage is a fraction of Control's screen, whatever the display scale); sizes are degrees of
visual angle turned into logical px with ``mm_per_px`` (per logical px) and the viewing distance,
so the icon looks the same on any monitor (4.3b).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..engine.calibration_motion import PHASE_HOLD, PHASE_IDLE, MotionSample, TargetMotion
from ..engine.calibration_settings import (
    BACKGROUNDS,
    CalibrationSettings,
    icon_diameter_px,
    icon_path,
)
from .design_tokens import INK, PANEL, TITLE_BAR, TYPE_HEADING

FRAME_MS = 16  # about 60 frames a second while a point is on
PROCESSING_TEXT = "Processing calibration results"
_DOT_COUNT = 3
_DOT_PERIOD_S = 1.2


class CalibrationStage(QWidget):
    def __init__(
        self,
        settings: CalibrationSettings,
        mm_per_px: float,
        viewing_distance_mm: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clock = clock
        self._motion = TargetMotion()
        self._processing = False
        self._current_point = 0
        self._times: dict[int, dict[str, float | None]] = {}
        self._pixmap = QPixmap()
        self._background = QColor(BACKGROUNDS["white"])
        self.configure(settings, mm_per_px, viewing_distance_mm)
        self.setAutoFillBackground(False)
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.update)

    # -- setup -------------------------------------------------------------------------------

    def configure(self, settings: CalibrationSettings, mm_per_px: float, viewing_distance_mm: float) -> None:
        self._settings = settings
        self._mm_per_px = mm_per_px
        self._distance_mm = viewing_distance_mm
        self._background = QColor(BACKGROUNDS[settings.background])
        self._pixmap = QPixmap(str(icon_path(settings.target)))
        self.update()

    def reset(self) -> None:
        """Back to the start of a run: the icon waits off screen and enters from the corner."""
        self._timer.stop()
        self._motion = TargetMotion()
        self._processing = False
        self._current_point = 0
        self._times = {}
        self.update()

    # -- what the engine's records do ----------------------------------------------------------

    def begin_point(self, point: int, x: float, y: float, t0: float, delay_s: float) -> None:
        """``CALIB_START_PT``: glide to (x, y); the hold starts by ``t0 + delay_s``."""
        self._processing = False
        self._current_point = point
        self._motion.begin_point(x, y, t0, delay_s)
        self._times[point] = {"start": t0, "hold_scheduled": self._motion.hold_start(), "result": None, "hold_painted": None}
        self._timer.start()
        self.update()

    def note_result(self, point: int, t: float) -> None:
        """``CALIB_RESULT_PT``: the point is done (the icon stays where it is)."""
        if point in self._times:
            self._times[point]["result"] = t

    def show_processing(self) -> None:
        self._processing = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def hold_report(self) -> list[dict[str, float | int | None]]:
        """Per point, when the hold was scheduled and when it was first painted (clock time), for
        ``_diagnostics/calibration_timing.jsonl``: the hold rule of 4.1 as it happened."""
        return [{"point": point, **times} for point, times in sorted(self._times.items())]

    # -- the icon's pose -----------------------------------------------------------------------

    def sample(self) -> MotionSample:
        return self._motion.sample(self._clock())

    def diameter_px(self, sample: MotionSample) -> float:
        """The icon's diameter in logical px: the preset's large size while gliding, shrinking to
        its small one for the hold."""
        large = icon_diameter_px(self._settings.size, False, self._mm_per_px, self._distance_mm)
        small = icon_diameter_px(self._settings.size, True, self._mm_per_px, self._distance_mm)
        return small + (large - small) * sample.size

    def center_px(self, sample: MotionSample) -> QPointF:
        """The icon's centre in logical px of this widget (a fraction of its size)."""
        return QPointF(sample.x * self.width(), sample.y * self.height())

    def center_physical_px(self, sample: MotionSample) -> tuple[float, float]:
        """The same centre in physical px of the screen (the unit Control's points are in once
        scaled by the screen size): logical px times the device pixel ratio."""
        centre = self.center_px(sample)
        ratio = self.devicePixelRatioF()
        return centre.x() * ratio, centre.y() * ratio

    # -- painting ------------------------------------------------------------------------------

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self._background)
        if self._processing:
            self._paint_processing(painter)
        else:
            self._paint_icon(painter)
        painter.end()

    def _paint_icon(self, painter: QPainter) -> None:
        sample = self.sample()
        if sample.phase == PHASE_IDLE:
            return
        if sample.phase == PHASE_HOLD:
            times = self._times.get(self._current_point)
            if times is not None and times["hold_painted"] is None:
                times["hold_painted"] = self._clock()
        diameter = self.diameter_px(sample)
        centre = self.center_px(sample)
        painter.save()
        painter.translate(centre)
        painter.rotate(sample.angle_deg)
        target = QRectF(-diameter / 2.0, -diameter / 2.0, diameter, diameter)
        if self._pixmap.isNull():  # a missing asset still shows where to look
            painter.setBrush(QColor(PANEL))
            painter.setPen(QPen(QColor(TITLE_BAR), max(2.0, diameter / 12.0)))
            painter.drawEllipse(target)
        else:
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        painter.restore()

    def _paint_processing(self, painter: QPainter) -> None:
        ink = QColor(PANEL) if self._settings.background == "black" else QColor(INK)
        font = QFont(painter.font())
        font.setPixelSize(TYPE_HEADING)
        painter.setFont(font)
        painter.setPen(ink)
        middle = self.rect().center()
        text_box = QRectF(0, middle.y() - 40, self.width(), 32)
        painter.drawText(text_box, int(Qt.AlignmentFlag.AlignCenter), PROCESSING_TEXT)
        phase = (self._clock() % _DOT_PERIOD_S) / _DOT_PERIOD_S
        radius, gap = 6.0, 22.0
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(_DOT_COUNT):
            strength = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(2.0 * math.pi * (phase - i / _DOT_COUNT)))
            colour = QColor(ink)
            colour.setAlphaF(strength)
            painter.setBrush(colour)
            x = middle.x() + (i - (_DOT_COUNT - 1) / 2.0) * gap
            painter.drawEllipse(QPointF(x, middle.y() + 16), radius, radius)
