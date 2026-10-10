"""Views hosting the subject canvas and the run bar.

:class:`TaskRunView` is the run screen as a plain ``QWidget`` -- the canvas, with the
thin :class:`~src.ui.run_bar.RunBar` under it (SPEC-compass-task-flow.md 4C.5): no
operator HUD. It is a widget so it can be embedded into another window (the
dashboard's ``QStackedWidget``) instead of only ever living inside its own top-level
window. :class:`MainWindow` is a thin wrapper around it for the standalone
``--task X --gui`` CLI launch (:mod:`src.app`).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from ..engine.run_mode import RECORD
from .canvas import TaskCanvas
from .run_bar import RunBar


class TaskRunView(QWidget):
    def __init__(
        self,
        theme: dict | None = None,
        run_mode: str = RECORD,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Qt's default inter-widget spacing would leave a gap between canvas and
        # bar where this unstyled widget's raw (black) background shows through
        # (SPEC-diki-design-audit.md S8.7).
        layout.setSpacing(0)

        self.canvas = TaskCanvas(theme=theme)
        self.run_bar = RunBar(run_mode)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.run_bar)

        # Alt-P and Alt-Q work with focus on the canvas or anywhere in this view:
        # shortcuts on the view, not mnemonics on the buttons (4C.5).
        self.pause_shortcut = self._shortcut("Alt+P", self.run_bar.pause_button)
        self.quit_shortcut = self._shortcut("Alt+Q", self.run_bar.quit_button)

        # After any bar click the canvas has the focus back, so Space (the switch)
        # and Esc keep working.
        for signal in (self.run_bar.pause_toggled, self.run_bar.skip_requested, self.run_bar.quit_requested):
            signal.connect(lambda *_args: self.canvas.setFocus())

    def _shortcut(self, keys: str, button) -> QShortcut:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(button.click)
        return shortcut


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme: dict | None = None,
        fullscreen: bool = True,
        run_mode: str = RECORD,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Pediatric Eye-Gaze Assessment")
        # Set by the run that owns this window (SPEC-audit-fixes.md H4): called by the close
        # event, returns whether the window may close now. None: always.
        self.close_guard: Callable[[], bool] | None = None

        self.view = TaskRunView(theme=theme, run_mode=run_mode)
        self.canvas = self.view.canvas
        self.setCentralWidget(self.view)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        """The X button and Alt+F4 during a run ask the quit question instead of closing: the
        run ends normally (every file written) and then the application quits."""
        if self.close_guard is not None and not self.close_guard():
            event.ignore()
            return
        super().closeEvent(event)
