"""The run screen's bottom bar (SPEC-compass-task-flow.md 4C.5, U5).

With the operator HUD gone, a thin bar under the canvas is all the operator sees of
the run: one line of status on the left, and Pause (Alt-P) / Skip trial / Quit
(Alt-Q) in the middle. No score, no counters, no sliders. The bar is the only thing
that tells a Practice or a Preview from a recorded run, so those turn it amber.

The bar only emits signals; :class:`~src.app.AssessmentApp` decides what they mean.
Its stylesheet is its own (scoped by object name), so it looks the same inside the
dashboard and in the standalone ``--task X --gui`` window, which never installs the
dashboard's.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from ..engine.run_mode import PRACTICE, PREVIEW, RECORD, validate_run_mode
from ..engine.tracking_status import LEVEL_ERROR, LEVEL_OK, LEVEL_WARN

BAR_HEIGHT = 44

# Text colours for the tracking state, dark enough to read on both bar backgrounds.
_LEVEL_COLORS = {LEVEL_OK: "#1e7a53", LEVEL_WARN: "#8a5a00", LEVEL_ERROR: "#c0392b"}

_STYLESHEET = """
QFrame#wtmhRunBar { background: #e9eef1; border-top: 1px solid #c9d5dc; }
QFrame#wtmhRunBar[practice="true"] { background: #fbe3b0; border-top: 1px solid #d9a441; }
QFrame#wtmhRunBar QLabel { color: #122b3a; background: transparent; font-size: 13px; }
QFrame#wtmhRunBar QPushButton {
    color: #122b3a; background: #ffffff; border: 1px solid #b8c7cf;
    border-radius: 6px; padding: 5px 16px; font-size: 13px; font-weight: 600;
}
QFrame#wtmhRunBar QPushButton:hover { background: #dcf0f5; border-color: #1f7a9c; }
QFrame#wtmhRunBar QPushButton:disabled { color: #7f939e; background: #f3f6f8; border-color: #d3dde2; }
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

        # One status line at the left; the buttons sit in the middle because both
        # side columns stretch equally (the label's own text width, which changes
        # every frame, must not decide its share: hence Ignored).
        self.status_label = QLabel("")
        self.status_label.setObjectName("runBarStatus")
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setMinimumWidth(120)
        layout.addWidget(self.status_label, stretch=1)

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

    def set_status(self, line: str, tracking: str | None = None, level: str | None = None) -> None:
        """Show ``line`` (the whole status, e.g. ``Trial 4/18 · tracking OK``). When
        ``tracking`` is the end of it, that part is drawn in the colour of ``level``."""
        self._plain = line
        if tracking and level in _LEVEL_COLORS and line.endswith(tracking):
            head = escape(line[: len(line) - len(tracking)])
            tail = f'<span style="color:{_LEVEL_COLORS[level]}; font-weight:600">{escape(tracking)}</span>'
            self.status_label.setText(head + tail)
        else:
            self.status_label.setText(escape(line))

    def status_text(self) -> str:
        """The status as plain text."""
        return self._plain

    def _on_pause_clicked(self) -> None:
        self.set_paused(not self._paused)
        self.pause_toggled.emit(self._paused)
