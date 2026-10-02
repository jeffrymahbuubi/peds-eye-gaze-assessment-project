"""Views hosting the subject canvas and the operator sidebar.

:class:`TaskRunView` is the actual canvas+sidebar content, as a plain
``QWidget`` -- extracted so it can be embedded into another window (the
Setup/Task-selection dashboard's ``QStackedWidget``, SPEC-ui-setup-
task-selection.md S3.1.7) instead of only ever living inside its own
top-level window. :class:`MainWindow` is now a thin wrapper around it for
the standalone ``--task X --gui`` CLI launch (:mod:`src.app`), unchanged in
behavior and public attributes (``.canvas``/``.operator_panel``) from
before this split.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from .canvas import TaskCanvas
from .operator_panel import OperatorPanel


class TaskRunView(QWidget):
    # Emitted only when the HUD's visibility actually changes (SPEC-hud-hide-
    # toggle.md S4.1), so listeners can count it as one operator toggle.
    hud_hidden_changed = Signal(bool)

    def __init__(
        self,
        theme: dict | None = None,
        task_id: str = "click_static",
        initial_settings: dict[str, Any] | None = None,
        settings_source: str = "defaults",
        settings_saved_at: str = "",
        settings_calibration: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Qt's default inter-widget spacing otherwise leaves a gap between
        # canvas and sidebar where this unstyled central widget's raw (black)
        # background shows through (SPEC-diki-design-audit.md S8.7).
        layout.setSpacing(0)

        self.canvas = TaskCanvas(theme=theme)
        self.operator_panel = OperatorPanel(
            task_id=task_id,
            initial_values=initial_settings,
            settings_source=settings_source,
            settings_saved_at=settings_saved_at,
            settings_calibration=settings_calibration,
        )
        self.operator_panel.setFixedWidth(280)

        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.operator_panel)

        # H toggles the HUD both ways (SPEC-hud-hide-toggle.md S4.2). A
        # shortcut on this view, not the canvas keyPressEvent patch, so it
        # works with focus on the canvas or on any panel control.
        self.hud_shortcut = QShortcut(QKeySequence(Qt.Key.Key_H), self)
        self.hud_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.hud_shortcut.activated.connect(self.toggle_hud)
        self.operator_panel.hide_requested.connect(lambda: self.set_hud_hidden(True))

    @property
    def hud_hidden(self) -> bool:
        return not self.operator_panel.isVisibleTo(self)

    def set_hud_hidden(self, hidden: bool) -> None:
        """Hide/show the operator column; the canvas takes (or gives back)
        its width through the layout. Focus returns to the canvas so Space
        and Esc keep working once the clicked button is gone."""
        changed = hidden != self.hud_hidden
        self.operator_panel.setVisible(not hidden)
        self.canvas.setFocus()
        if changed:
            self.hud_hidden_changed.emit(hidden)

    def toggle_hud(self) -> None:
        self.set_hud_hidden(not self.hud_hidden)


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme: dict | None = None,
        task_id: str = "click_static",
        initial_settings: dict[str, Any] | None = None,
        settings_source: str = "defaults",
        settings_saved_at: str = "",
        settings_calibration: dict | None = None,
        fullscreen: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Pediatric Eye-Gaze Assessment")

        self.view = TaskRunView(
            theme=theme,
            task_id=task_id,
            initial_settings=initial_settings,
            settings_source=settings_source,
            settings_saved_at=settings_saved_at,
            settings_calibration=settings_calibration,
        )
        self.canvas = self.view.canvas
        self.operator_panel = self.view.operator_panel
        self.setCentralWidget(self.view)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)
