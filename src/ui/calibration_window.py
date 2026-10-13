"""The calibration window (SPEC-app-drawn-calibration.md 4.1, 4.4, 4.5; wireframe
``docs/wireframes/calibration-window.md``).

A frameless full-screen window on the tracked monitor, over the taskbar, opened by Do Calibration
(Setup) or Calibrate (Start page) when "Calibration screen" is App. It has five states:

* **waiting / running** (:class:`~src.ui.calibration_stage.CalibrationStage`): a plain background and
  the icon, no text, no sound, only a faint close x top right; the mouse cursor stays visible;
* **processing**: "Processing calibration results" until ``CALIB_RESULT``;
* **results**: the map of per-point scores (:class:`~src.ui.calibration_map.ResultsMap`), the line
  under it, and Improve calibration, Show Monitor and Back;
* **monitor**: the head-position widget over the dimmed map.

Esc or the x asks to cancel (``cancelRequested``): during a run that cancels it, on the results map
it is Back (the flow decides, see :class:`~src.ui.calibration_flow.CalibrationFlow`). The window only
draws and reports what was pressed; :class:`~src.ui.calibration_flow.CalibrationFlow` runs the calibration behind it.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.calibration_run import (
    EVENT_FALLBACK,
    EVENT_PROCESSING,
    EVENT_RESULT_POINT,
    EVENT_START_POINT,
    CalibrationEvent,
)
from ..engine.calibration_settings import CalibrationSettings, PointScore, attention_text
from .calibration_map import MAP_MARGIN_PX, ResultsMap
from .calibration_stage import CalibrationStage
from .design_tokens import INK, TEXT_SECONDARY, TYPE_BODY_LARGE, TYPE_HEADING
from .dialog_theme import apply_dialog_theme
from .head_position_panel import HeadPositionPanel, HeadPositionSource

STATE_WAITING = "waiting"  # started, no point yet
STATE_RUNNING = "running"  # a point is on (glide, then hold)
STATE_PROCESSING = "processing"  # the last point is done, waiting for CALIB_RESULT
STATE_RESULTS = "results"
STATE_MONITOR = "monitor"  # results, with the head-position widget over the map

SHOW_MONITOR = "Show Monitor"
HIDE_MONITOR = "Hide Monitor"
IMPROVE = "Improve calibration"
BACK = "Back"
CLOSE_PX = 40
CLOSE_MARGIN_PX = 12


class CalibrationWindow(QWidget):
    cancelRequested = Signal()  # Esc, the x, or the window being closed from outside (Back on the map)
    improveRequested = Signal()  # Improve calibration: run all points again (Q2)
    backRequested = Signal()  # Back: keep the last result and return to the page that opened it

    def __init__(
        self,
        settings: CalibrationSettings,
        mm_per_px: float,
        viewing_distance_mm: float,
        *,
        head_source: HeadPositionSource | None = None,
        clock: Callable[[], float] = time.monotonic,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("calibrationWindow")
        self.setWindowTitle("Calibration")
        self._state = STATE_WAITING
        self._dismissed = False
        self._aspect = 16 / 9
        self._scores: list[PointScore] = []

        self._layout = QStackedLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.stage = CalibrationStage(settings, mm_per_px, viewing_distance_mm, clock=clock)
        self._layout.addWidget(self.stage)
        self._results = self._build_results(head_source)
        self._layout.addWidget(self._results)
        self._layout.setCurrentWidget(self.stage)

        # The faint x, always on top; Esc does the same.
        self.close_button = QToolButton(self)
        self.close_button.setObjectName("calibrationClose")
        self.close_button.setText("×")
        self.close_button.setAccessibleName("Cancel calibration")
        self.close_button.setFixedSize(CLOSE_PX, CLOSE_PX)
        self.close_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.close_button.setStyleSheet(
            f"QToolButton {{ color: {TEXT_SECONDARY}; background: transparent; border: none;"
            f" font-size: {TYPE_HEADING}px; }} QToolButton:hover {{ color: {INK}; }}"
        )
        self.close_button.clicked.connect(self.cancelRequested)
        self._escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape.setContext(Qt.ShortcutContext.WindowShortcut)
        self._escape.activated.connect(self.cancelRequested)

    # -- building ------------------------------------------------------------------------------

    def _build_results(self, head_source: HeadPositionSource | None) -> QWidget:
        page = QWidget()
        apply_dialog_theme(page)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(MAP_MARGIN_PX, 56, MAP_MARGIN_PX, MAP_MARGIN_PX)
        outer.setSpacing(16)
        self.map = ResultsMap()
        outer.addWidget(self.map, 1)
        self.attention_label = QLabel("")
        self.attention_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.attention_label.setWordWrap(True)
        self.attention_label.setStyleSheet(f"font-size: {TYPE_BODY_LARGE}px;")
        outer.addWidget(self.attention_label)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.improve_button = self._button("calibrationImprove", IMPROVE, "wtmhGhost", self.improveRequested.emit)
        self.monitor_button = self._button("calibrationMonitor", SHOW_MONITOR, "wtmhGhost", self._toggle_monitor)
        self.back_button = self._button("calibrationBack", BACK, "wtmhPrimary", self.backRequested.emit)
        row.addWidget(self.improve_button)
        row.addWidget(self.monitor_button)
        row.addStretch(1)
        row.addWidget(self.back_button)
        outer.addLayout(row)

        # The head-position widget as a card over the map (state 5): the existing panel, reused.
        self.monitor_card = QFrame(page)
        self.monitor_card.setObjectName("wtmhCard")
        card_layout = QVBoxLayout(self.monitor_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        self.head_panel = HeadPositionPanel(source=head_source)
        card_layout.addWidget(self.head_panel)
        self.monitor_card.hide()
        return page

    @staticmethod
    def _button(name: str, text: str, tier: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)  # the theme styles the tiers by object name
        button.setAccessibleName(name)
        button.setAutoDefault(False)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    # -- showing it ----------------------------------------------------------------------------

    def present_on(self, screen) -> None:
        """Cover ``screen`` (the tracked monitor) from corner to corner, taskbar included, and
        take the keyboard."""
        if screen is not None:
            self.setScreen(screen)
            geometry = screen.geometry()
            self.setGeometry(geometry)
            if geometry.height() > 0:
                self._aspect = geometry.width() / geometry.height()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def dismiss(self) -> None:
        """The flow is done with the window: stop drawing and close without a cancel."""
        self._dismissed = True
        self.stage.stop()
        self.monitor_card.hide()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        if not self._dismissed:
            self._dismissed = True  # e.g. Alt+F4: it is a cancel
            self.cancelRequested.emit()
        self.stage.stop()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self.close_button.move(self.width() - CLOSE_PX - CLOSE_MARGIN_PX, CLOSE_MARGIN_PX)
        self.close_button.raise_()
        self._place_monitor_card()

    def _place_monitor_card(self) -> None:
        map_rect = self.map.geometry()
        self.monitor_card.adjustSize()
        self.monitor_card.move(map_rect.left() + MAP_MARGIN_PX + 16, map_rect.top() + MAP_MARGIN_PX + 16)

    # -- state ---------------------------------------------------------------------------------

    def state(self) -> str:
        return self._state

    def begin_run(self) -> None:
        """A run (the first, or Improve calibration's) is about to start: back to the empty
        stage, the icon off screen."""
        self.monitor_card.hide()
        self.map.set_dimmed(False)
        self.monitor_button.setText(SHOW_MONITOR)
        self.stage.reset()
        self._layout.setCurrentWidget(self.stage)
        self.close_button.raise_()
        self._state = STATE_WAITING

    def handle_event(self, event: CalibrationEvent) -> None:
        """React to one of the engine's records."""
        if event.kind == EVENT_START_POINT:
            self._state = STATE_RUNNING
            self.stage.begin_point(event.point, event.x, event.y, event.t, event.delay_s)
        elif event.kind == EVENT_RESULT_POINT:
            self.stage.note_result(event.point, event.t)
        elif event.kind == EVENT_PROCESSING:
            self._state = STATE_PROCESSING
            self.stage.show_processing()
        elif event.kind == EVENT_FALLBACK:
            self.dismiss()  # Control's own window takes over (4.2)

    def show_results(self, scores: list[PointScore], note: str = "") -> None:
        """The run is over: draw the map of ``scores``. ``note`` replaces the line under it
        (e.g. when no per-point data came)."""
        self._scores = list(scores)
        self.stage.stop()
        self.map.set_scores(self._scores, self._aspect)
        self.attention_label.setText(note or attention_text(self._scores))
        self._layout.setCurrentWidget(self._results)
        self._state = STATE_RESULTS
        self.close_button.raise_()
        self._place_monitor_card()
        self.setFocus()

    def monitor_visible(self) -> bool:
        return self._state == STATE_MONITOR

    def _toggle_monitor(self) -> None:
        if self._state not in (STATE_RESULTS, STATE_MONITOR):
            return
        showing = self._state == STATE_RESULTS
        self._state = STATE_MONITOR if showing else STATE_RESULTS
        self.monitor_card.setVisible(showing)
        if showing:
            self._place_monitor_card()
            self.monitor_card.raise_()
        self.map.set_dimmed(showing)
        self.monitor_button.setText(HIDE_MONITOR if showing else SHOW_MONITOR)

    def hold_report(self) -> list[dict[str, float | int | None]]:
        return self.stage.hold_report()
