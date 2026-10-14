"""The App-screen calibration from Do Calibration (or the Start page's Calibrate) to Back
(SPEC-app-drawn-calibration.md 4.1, 4.2, 4.4, 4.7).

:class:`CalibrationFlow` owns the calibration window and, one at a time, the threads that run the
calibration behind it (:func:`~src.engine.calibration_run.run_calibration`). It opens the window,
forwards the engine's records to it, shows the results map when a run ends, runs everything again
on Improve calibration (Q2: a full re-run, counted), and ends with one
:class:`CalibrationOutcome` for the page that started it:

* **Back** (also the check view's Done): the last run's result, with ``improve_runs`` and
  ``accuracy_checked`` set;
* **Esc / x** during a run (glide, hold, processing): ``cancelled``; the page keeps what it had
  (4.1). On the results map (and Show Monitor, and the Check accuracy view) the run is over and
  Control already holds the new calibration, so Esc / x is Back and the result is kept;
* **fallback** (4.2): the window is gone and Control's own window made the result, with the alert.

The page supplies ``make_thread`` (its calibration thread, so a test can stand in for the device).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from ..data.report_geometry import Geometry
from ..engine.calibration import CalibrationResult, _append_timing_record
from ..engine.calibration_run import FALLBACK_ALERT, CalibrationRun
from ..engine.calibration_settings import (
    MODE_FALLBACK,
    CalibrationSettings,
    eye_counts,
    score_points,
    with_accuracy_checked,
    with_improve_runs,
)
from .calibration_check import GazeSource
from .calibration_window import CalibrationWindow
from .head_position_panel import HeadPositionSource


@dataclass(frozen=True)
class CalibrationOutcome:
    """How the flow ended: ``result`` is None when ``cancelled``."""

    result: CalibrationResult | None
    cancelled: bool = False
    alert: str = ""  # FALLBACK_ALERT when Control's own window made the result
    mode: str = ""
    improve_runs: int = 0


class CalibrationFlow(QObject):
    finished = Signal(object)  # a CalibrationOutcome

    def __init__(
        self,
        make_thread: Callable[[CalibrationSettings, Geometry, threading.Event], Any],
        settings: CalibrationSettings,
        screen: Any,
        geometry: Geometry,
        *,
        mm_per_px: float,
        viewing_distance_mm: float,
        head_source: HeadPositionSource | None = None,
        gaze_source: GazeSource | None = None,
        timing_log_path: str | Path | None = None,
        window_factory: Callable[..., CalibrationWindow] = CalibrationWindow,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._make_thread = make_thread
        self._settings = settings
        self._screen = screen
        self._geometry = geometry
        self._mm_per_px = mm_per_px
        self._distance_mm = viewing_distance_mm
        self._head_source = head_source
        self._gaze_source = gaze_source
        self._timing_log_path = timing_log_path
        self._window_factory = window_factory
        self._clock = clock
        self.window: CalibrationWindow | None = None
        self.improve_runs = 0
        self._cancel = threading.Event()
        self._running = False  # a thread is running the calibration
        self._cancelling = False
        self._closed = False
        self._last_run: CalibrationRun | None = None
        self._hold_reports: list[list[dict[str, Any]]] = []

    # -- starting and ending ------------------------------------------------------------------

    def start(self) -> None:
        """Open the window over the tracked monitor and start the first run."""
        parent = self.parent() if isinstance(self.parent(), QWidget) else None
        window = self.window = self._window_factory(
            self._settings, self._mm_per_px, self._distance_mm,
            head_source=self._head_source, gaze_source=self._gaze_source, clock=self._clock, parent=parent,
        )
        window.cancelRequested.connect(self._on_cancel)
        window.improveRequested.connect(self._on_improve)
        window.backRequested.connect(self._on_back)
        window.present_on(self._screen)
        self._start_run()

    def running(self) -> bool:
        """Whether a thread is running the calibration now."""
        return self._running

    def abort(self) -> None:
        """The application is closing: stop the run and the window, report nothing."""
        self._closed = True
        self._cancel.set()
        if self.window is not None:
            window, self.window = self.window, None
            window.dismiss()
            window.deleteLater()

    def _start_run(self) -> None:
        window = self.window
        if window is None:
            return
        window.begin_run()
        self._cancel = threading.Event()
        thread = self._make_thread(self._settings, self._geometry, self._cancel)
        thread.calibrationEvent.connect(self._on_event)
        self._running = True
        thread.start()

    def _finish(self, outcome: CalibrationOutcome) -> None:
        if self._closed:
            return
        self._closed = True
        window, self.window = self.window, None
        if window is not None:
            self._write_window_times()
            window.dismiss()
            window.deleteLater()
        self.finished.emit(outcome)

    # -- what the thread reports --------------------------------------------------------------

    def _on_event(self, event) -> None:
        if self.window is not None and not self._closed:
            self.window.handle_event(event)

    def run_done(self, run: CalibrationRun) -> None:
        """The thread's run ended (the page forwards its ``finished_ok``)."""
        self._running = False
        if self._closed:
            return
        if self.window is not None:
            self._hold_reports.append(self.window.hold_report())
        self._last_run = run
        if self._cancelling or run.cancelled:
            self._finish(CalibrationOutcome(None, cancelled=True, mode=run.mode))
            return
        if run.mode == MODE_FALLBACK:  # Control's own window made it; ours is already closed
            self._finish(self._outcome(run, alert=FALLBACK_ALERT))
            return
        if not run.result.per_point:  # no CALIB_RESULT, so no result and no map: the page reports it
            self._finish(self._outcome(run))
            return
        if self.window is not None:
            self.window.show_results(
                score_points(run.result.per_point, self._geometry), eyes=eye_counts(run.result.per_point)
            )

    def _outcome(self, run: CalibrationRun, alert: str = "") -> CalibrationOutcome:
        checked = self.window is not None and self.window.accuracy_checked()  # the Check accuracy view (4.8 R3)
        result = with_accuracy_checked(with_improve_runs(run.result, self.improve_runs), checked)
        return CalibrationOutcome(result=result, alert=alert, mode=run.mode, improve_runs=self.improve_runs)

    # -- what the window's buttons ask ---------------------------------------------------------

    def _on_improve(self) -> None:
        if self._running or self._closed or self._last_run is None:
            return
        self.improve_runs += 1
        self._last_run = None
        self._start_run()

    def _on_back(self) -> None:
        if self._running or self._closed or self._last_run is None:
            return
        self._finish(self._outcome(self._last_run))

    def _on_cancel(self) -> None:
        """Esc, the x, or the window closed. During a run (glide, hold, processing) it cancels
        (4.1): the thread stops Control (:func:`run_calibration` sends ``CALIBRATE_START
        STATE="0"``) and the page keeps what it had. On the results map and Show Monitor the run
        is over and Control already holds the new calibration, so it is Back: the result is kept
        (hub answer 2026-10-13)."""
        if self._cancelling or self._closed:
            return
        if not self._running:
            self._on_back()
            return
        self._cancelling = True
        self._cancel.set()  # run_done() finishes the flow

    # -- diagnostics ----------------------------------------------------------------------------

    def _write_window_times(self) -> None:
        """Per run and point, how long after ``CALIB_START_PT`` the hold was scheduled and when
        it was first painted: the hold rule of 4.1 as the window kept it (4.7)."""
        if self._timing_log_path is None or not any(self._hold_reports):
            return
        runs = []
        for report in self._hold_reports:
            runs.append(
                [
                    {
                        "point": entry["point"],
                        "hold_scheduled_s": _after(entry["hold_scheduled"], entry["start"]),
                        "hold_painted_s": _after(entry["hold_painted"], entry["start"]),
                    }
                    for entry in report
                ]
            )
        _append_timing_record(
            self._timing_log_path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "app_window",
                "n_points": self._settings.points,
                "delay_s": self._settings.delay_s,
                "improve_runs": self.improve_runs,
                "runs": runs,
            },
        )


def _after(moment: float | None, start: float | None) -> float | None:
    return None if moment is None or start is None else round(moment - start, 4)
