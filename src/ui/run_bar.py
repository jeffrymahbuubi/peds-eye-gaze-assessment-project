"""The run screen's bottom bar (SPEC-compass-task-flow.md 4C.5, U5; SPEC-design-system-
phase1.md H9).

With the operator HUD gone, a thin bar under the canvas is all the operator sees of
the run: the status on the left, and Pause (Alt-P) / Skip trial / Quit
(Alt-Q) in the middle. No score, no counters, no sliders. The bar is the only thing
that tells a Practice or a Preview from a recorded run, so those turn it amber and
carry a PRACTICE / PREVIEW chip. The status is not one line of text but separate labels:
the chip, a pause marker, "Trial 4 of 18", the pointer, and the tracking state in
the colour of its level.

The bar only emits signals; :class:`~src.app.AssessmentApp` decides what they mean.
Its stylesheet is its own (scoped by object name), so it looks the same inside the
dashboard and in the standalone ``--task X --gui`` window, which never installs the
dashboard's.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from ..engine.run_mode import PRACTICE, PREVIEW, RECORD, validate_run_mode
from ..engine.tracking_status import LEVEL_ERROR, LEVEL_OK, LEVEL_WARN, RunStatus
from .design_tokens import (
    ACCENT,
    ACCENT_SUBTLE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    BORDER_WIDTH,
    DANGER_TEXT,
    DISABLED_FILL,
    INK,
    PAGE,
    PANEL,
    RADIUS,
    RUN_BAR_BUTTON_HEIGHT,
    RUN_BAR_HEIGHT,
    SUCCESS_TEXT,
    TEXT_DISABLED,
    TYPE_BODY,
    TYPE_BODY_LARGE,
    TYPE_CAPTION,
    WARNING,
    WARNING_CHIP,
    WARNING_SUBTLE,
    WARNING_TEXT,
)

BAR_HEIGHT = RUN_BAR_HEIGHT

# The tracking state is drawn in success-text / warning-text / danger-text, dark enough to
# read on both bar backgrounds (7.0 to 7.2:1).
_STYLESHEET = f"""
QFrame#wtmhRunBar {{ background: {PAGE}; border-top: 1px solid {BORDER_SUBTLE}; }}
QFrame#wtmhRunBar[practice="true"] {{ background: {WARNING_SUBTLE}; border-top: 1px solid {WARNING}; }}
QFrame#wtmhRunBar QLabel {{ color: {INK}; background: transparent; font-size: {TYPE_BODY_LARGE}px; }}
QFrame#wtmhRunBar QLabel#runBarChip {{
    background: {WARNING_CHIP}; color: {INK}; border-radius: 12px; padding: 0 12px;
    min-height: 24px; font-size: {TYPE_CAPTION}px; font-weight: 600;
}}
QFrame#wtmhRunBar QLabel#runBarTracking {{ font-weight: 600; }}
QFrame#wtmhRunBar QLabel#runBarTracking[level="{LEVEL_OK}"] {{ color: {SUCCESS_TEXT}; }}
QFrame#wtmhRunBar QLabel#runBarTracking[level="{LEVEL_WARN}"] {{ color: {WARNING_TEXT}; }}
QFrame#wtmhRunBar QLabel#runBarTracking[level="{LEVEL_ERROR}"] {{ color: {DANGER_TEXT}; }}
QFrame#wtmhRunBar QPushButton {{
    color: {INK}; background: {PANEL}; border: {BORDER_WIDTH}px solid {BORDER_STRONG};
    border-radius: {RADIUS}px; min-height: {RUN_BAR_BUTTON_HEIGHT - 2 * BORDER_WIDTH}px;
    padding: 0 15px; font-size: {TYPE_BODY}px; font-weight: 600;
}}
QFrame#wtmhRunBar QPushButton:hover {{ background: {ACCENT_SUBTLE}; border-color: {ACCENT}; }}
QFrame#wtmhRunBar QPushButton:disabled {{
    color: {TEXT_DISABLED}; background: {DISABLED_FILL}; border-color: {DISABLED_FILL};
}}
"""


class RunBar(QFrame):
    pause_toggled = Signal(bool)  # True = the operator asked to pause, False = to resume
    skip_requested = Signal()
    quit_requested = Signal()

    def __init__(self, run_mode: str = RECORD, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhRunBar")
        self.setStyleSheet(_STYLESHEET)
        self.setFixedHeight(BAR_HEIGHT)
        self._paused = False
        self._plain = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # The status at the left, a label per fact; the buttons sit in the middle because
        # both side columns stretch equally (the labels' own text width, which changes
        # every frame, must not decide their share: hence Ignored).
        self.status_box = QWidget()
        self.status_box.setObjectName("runBarStatus")
        self.status_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_box.setMinimumWidth(120)
        status_row = QHBoxLayout(self.status_box)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(16)
        self.chip_label = self._status_label("runBarChip", status_row)
        self.paused_label = self._status_label("runBarPaused", status_row)
        self.trial_label = self._status_label("runBarTrial", status_row)
        self.pointer_label = self._status_label("runBarPointer", status_row)
        self.tracking_label = self._status_label("runBarTracking", status_row)
        status_row.addStretch(1)
        layout.addWidget(self.status_box, stretch=1)

        self.pause_button = self._button("runBarPause", "Pause (Alt-P)")
        self.skip_button = self._button("runBarSkip", "Skip trial")
        self.quit_button = self._button("runBarQuit", "Quit (Alt-Q)")
        for button in (self.pause_button, self.skip_button, self.quit_button):
            layout.addWidget(button)
        layout.addStretch(1)

        self.pause_button.clicked.connect(self._on_pause_clicked)
        self.skip_button.clicked.connect(self.skip_requested.emit)
        self.quit_button.clicked.connect(self.quit_requested.emit)
        self.set_run_mode(run_mode)

    @staticmethod
    def _status_label(name: str, row: QHBoxLayout) -> QLabel:
        label = QLabel("")
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)  # a status is never read as markup
        label.hide()  # shown while it has something to say
        row.addWidget(label)
        return label

    @staticmethod
    def _button(name: str, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        # A click must not take the keyboard focus away from the canvas, where
        # Space (switch) and Esc are read.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    # -- state ----------------------------------------------------------------

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_run_mode(self, run_mode: str) -> None:
        """Amber for a Practice or a Preview (nothing is recorded), grey for a
        recorded run."""
        mode = validate_run_mode(run_mode)
        self.setProperty("practice", mode in (PRACTICE, PREVIEW))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_paused(self, paused: bool) -> None:
        """Show the paused state (Pause becomes Resume). Does not emit: the bar's own
        click does, and the app calls this when it pauses for another reason (the
        quit question)."""
        self._paused = bool(paused)
        self.pause_button.setText("Resume (Alt-P)" if self._paused else "Pause (Alt-P)")

    def set_skip_enabled(self, enabled: bool) -> None:
        self.skip_button.setEnabled(bool(enabled))

    def set_status(self, status: RunStatus) -> None:
        """Show ``status``: each fact in its own label, hidden when empty; the tracking state
        takes the colour of its level."""
        self._plain = status.line
        for label, text in (
            (self.chip_label, status.chip),
            (self.paused_label, "Paused" if status.paused else ""),
            (self.trial_label, status.trial),
            (self.pointer_label, status.pointer),
            (self.tracking_label, status.tracking),
        ):
            label.setText(text)
            label.setVisible(bool(text))
        if self.tracking_label.property("level") != status.level:
            self.tracking_label.setProperty("level", status.level)
            self.tracking_label.style().unpolish(self.tracking_label)
            self.tracking_label.style().polish(self.tracking_label)

    def status_text(self) -> str:
        """The status as plain text (the labels' texts, in order)."""
        return self._plain

    def _on_pause_clicked(self) -> None:
        self.set_paused(not self._paused)
        self.pause_toggled.emit(self._paused)
