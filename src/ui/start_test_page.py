"""The Start screen shown before a recorded run (SPEC-compass-task-flow.md 4C.2-4C.4,
U7, R2; wireframe ``docs/wireframes/start-test.md``, Compass ``07a``).

Run Test on the Test List always opens this page, so the instructions stay readable
and a missing tracker or calibration is visible rather than a silent no-op: an amber
banner lists what is missing (from :meth:`SetupPage.run_blockers`) and Start and
Practice are disabled while it shows. The blockers are read again on show, every
second while the page is visible (the tracker can drop), and inside the Start and
Practice handlers, so a stale enabled button still cannot launch.

The page only emits signals; the dashboard (P8) builds a new
:class:`~src.app.AssessmentApp` for Practice and for the real run. There is no
default button, so Enter starts nothing, and Esc is Cancel. The wording of the
instructions comes from :func:`~src.ui.task_instructions.build_instructions` and is
read aloud to children, so it needs a clinician's review before release.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..engine.run_result import RunResult, practice_result_text
from .task_instructions import Instructions, build_instructions

BLOCKER_REFRESH_MS = 1000

HELP_TEXT = (
    "Help: From this screen you can begin the test. You may also practice 3 targets "
    "first; practice is not recorded. Read the instructions aloud to the child."
)

_SCROLL_STYLE = (
    "QScrollArea#wtmhStartScroll, QScrollArea#wtmhStartScroll > QWidget "
    "{ background: transparent; border: none; }"
)


class StartTestPage(QWidget):
    startRequested = Signal()
    practiceRequested = Signal(int)  # the 0-based practice number since the page was set up
    cancelRequested = Signal()
    goToSetupRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._blockers_provider: Callable[[], list[str]] | None = None
        self._blockers: list[str] = []
        self._practice_count = 0
        self.instructions: Instructions | None = None
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(BLOCKER_REFRESH_MS)
        self._timer.timeout.connect(self.refresh_blockers)
        # Esc is Cancel (4C.3); there is no default button, so Enter does nothing.
        self._cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._cancel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._cancel_shortcut.activated.connect(self.cancelRequested.emit)
        self.refresh_blockers()

    # -- public API -----------------------------------------------------------

    def set_blockers_provider(self, provider: Callable[[], list[str]] | None) -> None:
        """Where the reasons a test cannot start come from (``SetupPage.run_blockers``);
        none means nothing blocks."""
        self._blockers_provider = provider
        self.refresh_blockers()

    def set_test(
        self,
        *,
        test_name: str,
        task_id: str,
        cfg: dict[str, Any],
        values: dict[str, Any] | None = None,
    ) -> None:
        """Show one test: its name and the instructions built from its own settings
        (``cfg`` is the run's merged config, ``values`` its live settings). A new test
        starts its practice count and its practice line afresh."""
        self.title_label.setText(f"Start {test_name}")
        self._practice_count = 0
        self.set_practice_result(None)
        self.instructions = build_instructions(task_id, cfg, values)
        self._show_instructions(self.instructions)
        self.refresh_blockers()

    def set_practice_result(self, result: RunResult | None) -> None:
        """The line after a practice ("Practice finished: 3 of 3 selected. ..."); a
        practice that was quit, or ``None``, clears it."""
        text = practice_result_text(result) if result is not None else None
        self.practice_label.setText(text or "")
        self.practice_label.setVisible(bool(text))

    def blockers(self) -> list[str]:
        """The reasons as of the last check."""
        return list(self._blockers)

    def refresh_blockers(self) -> list[str]:
        """Read the blockers now; show or hide the banner and enable or disable Start
        and Practice. Returns them."""
        provider = self._blockers_provider
        self._blockers = list(provider()) if provider is not None else []
        blocked = bool(self._blockers)
        self.banner.setVisible(blocked)
        if blocked:
            self.banner_label.setText(
                "Still needed before you can start: " + " · ".join(self._blockers)
            )
        self.start_button.setEnabled(not blocked)
        self.practice_button.setEnabled(not blocked)
        return self.blockers()

    @property
    def practice_count(self) -> int:
        """How many times Practice has been pressed since :meth:`set_test`."""
        return self._practice_count

    # -- UI -------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        self.title_label = QLabel("Start")
        self.title_label.setObjectName("wtmhPageTitle")
        outer.addWidget(self.title_label)

        self.banner = QFrame()
        self.banner.setObjectName("wtmhAlertWarning")
        banner_row = QHBoxLayout(self.banner)
        self.banner_label = QLabel("")
        self.banner_label.setWordWrap(True)
        banner_row.addWidget(self.banner_label, stretch=1)
        self.go_to_setup_button = QPushButton("Go to Setup")
        self.go_to_setup_button.setObjectName("wtmhGhost")
        self.go_to_setup_button.setAutoDefault(False)
        self.go_to_setup_button.clicked.connect(self.goToSetupRequested.emit)
        banner_row.addWidget(self.go_to_setup_button)
        self.banner.hide()
        outer.addWidget(self.banner)

        # The card scrolls above the buttons, so a small or scaled window never clips
        # Start (the same rule as the Setup and configuration pages).
        scroll = QScrollArea()
        scroll.setObjectName("wtmhStartScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(_SCROLL_STYLE)
        self.card = QFrame()
        self.card.setObjectName("wtmhCard")
        self._card_layout = QVBoxLayout(self.card)
        self._card_layout.setContentsMargins(28, 22, 28, 22)
        self._card_layout.setSpacing(10)
        scroll.setWidget(self.card)
        scroll.viewport().setAutoFillBackground(False)
        self.card.setAutoFillBackground(False)
        outer.addWidget(scroll, stretch=1)
        self._build_card()

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch(1)
        self.start_button = self._button("startTestStart", "Start", "wtmhPrimary", self._on_start)
        self.practice_button = self._button(
            "startTestPractice", "Practice", "wtmhGhost", self._on_practice
        )
        self.cancel_button = self._button(
            "startTestCancel", "Cancel", "wtmhGhost", self.cancelRequested.emit
        )
        for button in (self.start_button, self.practice_button, self.cancel_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.practice_label = QLabel("")
        self.practice_label.setObjectName("wtmhMuted")
        self.practice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.practice_label.setWordWrap(True)
        self.practice_label.hide()
        outer.addWidget(self.practice_label)

        self.help_bar = QFrame()
        self.help_bar.setObjectName("wtmhAlertInfo")
        help_row = QVBoxLayout(self.help_bar)
        self.help_label = QLabel(HELP_TEXT)
        self.help_label.setWordWrap(True)
        help_row.addWidget(self.help_label)
        outer.addWidget(self.help_bar)

    @staticmethod
    def _button(name: str, text: str, tier: str, slot: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(tier)  # the theme styles the tiers by object name
        button.setAccessibleName(name)
        # No default button: Enter must not start a test (4C.3).
        button.setAutoDefault(False)
        button.setDefault(False)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    def _build_card(self) -> None:
        layout = self._card_layout
        aloud_title = QLabel("Read aloud to the child")
        aloud_title.setObjectName("wtmhSectionTitle")
        layout.addWidget(aloud_title)
        self.heading_label = QLabel("")
        self.heading_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(self.heading_label)
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(6)
        layout.addLayout(self.steps_layout)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(self.note_label)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(rule)

        clinician_title = QLabel("For the clinician (not read aloud)")
        clinician_title.setObjectName("wtmhSectionTitle")
        layout.addWidget(clinician_title)
        self.clinician_layout = QVBoxLayout()
        self.clinician_layout.setSpacing(6)
        layout.addLayout(self.clinician_layout)
        layout.addStretch(1)

    def _show_instructions(self, text: Instructions) -> None:
        self.heading_label.setText(text.heading)
        self._fill(self.steps_layout, [f"{i}. {step}" for i, step in enumerate(text.steps, 1)], 15)
        self.note_label.setText(text.note)
        self._fill(self.clinician_layout, list(text.clinician), 13)

    @staticmethod
    def _fill(layout: QVBoxLayout, lines: list[str], pixel_size: int) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # gone from the card now, not at the next event loop
                widget.deleteLater()
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            label.setStyleSheet(f"font-size: {pixel_size}px;")
            layout.addWidget(label)

    # -- handlers -------------------------------------------------------------

    def _on_start(self) -> None:
        if self.refresh_blockers():
            return  # a stale enabled button still cannot launch
        self.startRequested.emit()

    def _on_practice(self) -> None:
        if self.refresh_blockers():
            return
        number = self._practice_count
        self._practice_count += 1
        self.practiceRequested.emit(number)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_blockers()
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._timer.stop()
        super().hideEvent(event)
