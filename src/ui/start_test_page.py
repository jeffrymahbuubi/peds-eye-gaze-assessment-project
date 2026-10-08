"""The Start screen shown before a recorded run (SPEC-compass-task-flow.md 4C.2-4C.4,
U7, R2; SPEC-design-system-phase2.md H7; wireframe ``docs/wireframes/start-test.md``,
Compass ``07a``).

Run Test on the Test List always opens this page, so the instructions stay readable
and a missing tracker or calibration is visible rather than a silent no-op: a "Blocked:"
alert lists what is missing, one item per line, with Go to Setup inside it (from
:meth:`SetupPage.run_blockers`), and Start and Practice are disabled while it shows. The blockers are read again on show, every
second while the page is visible (the tracker can drop), and inside the Start and
Practice handlers, so a stale enabled button still cannot launch.

The page only emits signals; the dashboard (P8) builds a new
:class:`~src.app.AssessmentApp` for Practice and for the real run. There is no
default button, so Enter starts nothing, and Esc is Cancel. The wording of the
instructions comes from :func:`~src.ui.task_instructions.build_instructions` and is
read aloud to children, so it needs a clinician's review before release.

The page is one column 1200 px wide. The read-aloud text is a white card, the clinician's text
sits on the page under it; Start is always the primary button (a disabled primary while
blocked), Practice the secondary, Cancel the tertiary, in one row at the left.

A second, separate line is the path blocker (SPEC-subject-data-layout.md H9, wireframe
W3): :meth:`StartTestPage.set_path_error` shows a danger alert when the run would write a
path over 240 characters. It disables **Start only**; Practice writes nothing, so it stays
on. The host sets it when the page opens: a path cannot change while the page is up.
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

from ..engine.input_choice import drop_gaze_only_blockers, resolve_input
from ..engine.run_result import RunResult, practice_result_text
from .alert_box import AlertBox
from .design_tokens import TYPE_BODY, TYPE_BODY_LARGE, TYPE_HEADING
from .page_layout import CARD_PADDING, CONTENT_MAX_WIDTH, SCROLLBAR_GUTTER, content_column
from .task_instructions import Instructions, build_instructions

BLOCKER_REFRESH_MS = 1000

# The line of a test with Pointer = Mouse (SPEC-input-selection-and-follow.md H5, I7): it
# needs no tracker and no calibration, but says what happens to the eye data.
# The note is two sentences (SPEC-design-system-phase2.md H7, section 9 answer of 2026-10-09): the
# first says why, in the alert's text; the second, in a label of its own at weight 600, says
# what that means for the data.
MOUSE_NOTE_ALONGSIDE = "Mouse test. Eye data will be recorded alongside."
MOUSE_NOTE_NO_TRACKER = "Mouse test. The tracker is not connected."
MOUSE_NOTE_NOT_CALIBRATED = "Mouse test. The tracker is not calibrated."
MOUSE_NOTE_NO_EYE_DATA = "No eye data will be recorded."

# "Practice runs 3 targets" is said once, in the clinician's text (P5); the alert's "Note:" is
# its state word.
HELP_TEXT = "From this screen you can begin the test. Read the instructions aloud to the child."

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
        self._mouse_test = False  # Pointer = Mouse: no tracker or calibration needed (H5)
        self._path_error = ""  # the H9 text while a recorded run would write too long a path
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
        self._mouse_test = resolve_input(cfg).is_mouse
        self.set_practice_result(None)
        self.show_note("")
        self.instructions = build_instructions(task_id, cfg, values)
        self._show_instructions(self.instructions)
        self.refresh_blockers()

    def set_practice_result(self, result: RunResult | None) -> None:
        """The line after a practice ("Practice finished: 3 of 3 selected. ..."); a
        practice that was quit, or ``None``, clears it."""
        text = practice_result_text(result) if result is not None else None
        self.practice_label.setText(text or "")
        self.practice_label.setVisible(bool(text))
        if result is not None:
            self.show_note("")  # a practice ran, so an earlier "could not start" is outdated

    def show_note(self, text: str) -> None:
        """A muted line under the buttons from the host, e.g. "Could not start Grid
        Click 1: ..." when a run could not be built. The operator stays here, can fix
        the cause and press Start or Practice again; the next press, a practice result
        or a new test clears it."""
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))

    def blockers(self) -> list[str]:
        """The reasons as of the last check."""
        return list(self._blockers)

    def set_path_error(self, text: str | None) -> None:
        """Show (or, with ``None`` / "", hide) the path-too-long alert. While it shows,
        Start is off and Practice is untouched (W3)."""
        self._path_error = text or ""
        self.path_alert_label.setText(self._path_error)
        self.path_alert.setVisible(bool(self._path_error))
        self.refresh_blockers()

    def refresh_blockers(self) -> list[str]:
        """Read the blockers now; show or hide the banner and enable or disable Start
        and Practice. Returns them.

        A Mouse test (H5) drops the tracker and calibration blockers: it is not blocked
        by them, and a one-line note says whether eye data will be recorded alongside."""
        provider = self._blockers_provider
        blockers = list(provider()) if provider is not None else []
        if self._mouse_test:
            blockers, tracker_ok, calibrated = drop_gaze_only_blockers(blockers)
            if tracker_ok and calibrated:
                self.mouse_note_label.setText(MOUSE_NOTE_ALONGSIDE)
                self.mouse_note.set_emphasis("")
            else:
                self.mouse_note_label.setText(
                    MOUSE_NOTE_NO_TRACKER if not tracker_ok else MOUSE_NOTE_NOT_CALIBRATED
                )
                self.mouse_note.set_emphasis(MOUSE_NOTE_NO_EYE_DATA)
        self.mouse_note.setVisible(self._mouse_test)
        self._blockers = blockers
        blocked = bool(self._blockers)
        self.banner.setVisible(blocked)
        if blocked:
            self.banner_label.setText("\n".join(self._blockers))  # one item per line
        self.start_button.setEnabled(not blocked and not self._path_error)
        self.practice_button.setEnabled(not blocked)
        return self.blockers()

    @property
    def practice_count(self) -> int:
        """How many times Practice has been pressed since :meth:`set_test`."""
        return self._practice_count

    # -- UI -------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = content_column(self, CONTENT_MAX_WIDTH + SCROLLBAR_GUTTER)  # the bar sits beside
        outer.setSpacing(16)

        self.title_label = QLabel("Start")
        self.title_label.setObjectName("wtmhPageTitle")
        outer.addWidget(self.title_label)

        # "Blocked:" over one item per line, Go to Setup inside the alert at its right edge.
        self.go_to_setup_button = QPushButton("Go to Setup")
        self.go_to_setup_button.setObjectName("wtmhGhost")
        self.go_to_setup_button.setAutoDefault(False)
        self.go_to_setup_button.clicked.connect(self.goToSetupRequested.emit)
        self.banner = AlertBox("danger", stacked=True, action=self.go_to_setup_button)
        self.banner_label = self.banner.label
        self.banner.hide()
        outer.addWidget(self.banner)

        # The H9 path blocker: a danger alert of its own, not part of the one above (no Go to
        # Setup: the cause is where the program folder is, not a Setup field).
        self.path_alert = AlertBox("danger")
        self.path_alert_label = self.path_alert.label
        self.path_alert.hide()
        outer.addWidget(self.path_alert)

        # Only for a test with Pointer = Mouse (H5), in place of the tracker blockers.
        self.mouse_note = AlertBox("note")
        self.mouse_note_label = self.mouse_note.label
        self.mouse_note.hide()
        outer.addWidget(self.mouse_note)

        # The text scrolls above the buttons, so a small or scaled window never clips
        # Start (the same rule as the Setup and configuration pages). Two surfaces: the
        # read-aloud text on a white card, the clinician's on the page.
        scroll = QScrollArea()
        scroll.setObjectName("wtmhStartScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(_SCROLL_STYLE)
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)
        self.card = QFrame()
        self.card.setObjectName("wtmhCard")
        self._card_layout = QVBoxLayout(self.card)
        self._card_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        self._card_layout.setSpacing(10)
        content_layout.addWidget(self.card)
        self.clinician_box = QWidget()
        self._clinician_box_layout = QVBoxLayout(self.clinician_box)
        self._clinician_box_layout.setContentsMargins(0, 0, 0, 0)
        self._clinician_box_layout.setSpacing(10)
        content_layout.addWidget(self.clinician_box)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        scroll.viewport().setAutoFillBackground(False)
        content.setAutoFillBackground(False)
        outer.addWidget(scroll, stretch=1)
        self._build_card()

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.start_button = self._button("startTestStart", "Start", "wtmhPrimary", self._on_start)
        self.practice_button = self._button(
            "startTestPractice", "Practice", "wtmhGhost", self._on_practice
        )
        self.cancel_button = self._button(
            "startTestCancel", "Cancel", "wtmhTertiary", self.cancelRequested.emit
        )
        for button in (self.start_button, self.practice_button, self.cancel_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.practice_label = QLabel("")
        self.practice_label.setObjectName("wtmhMuted")
        self.practice_label.setWordWrap(True)
        self.practice_label.hide()
        outer.addWidget(self.practice_label)

        self.message_label = QLabel("")
        self.message_label.setObjectName("wtmhMuted")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        outer.addWidget(self.message_label)

        self.help_bar = AlertBox("note", HELP_TEXT)
        self.help_label = self.help_bar.label
        outer.addWidget(self.help_bar)
        # Every alert is as wide as the card under them, 1200 px, not as the column (which
        # leaves room for the scroll bar).
        for alert in (self.banner, self.path_alert, self.mouse_note, self.help_bar):
            alert.setMaximumWidth(CONTENT_MAX_WIDTH)

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
        self.heading_label.setStyleSheet(f"font-size: {TYPE_HEADING}px; font-weight: 600;")
        layout.addWidget(self.heading_label)
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(6)
        layout.addLayout(self.steps_layout)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"font-size: {TYPE_BODY_LARGE}px; font-weight: 600;")
        layout.addWidget(self.note_label)

        layout.addStretch(1)

        clinician_title = QLabel("For the clinician (not read aloud)")
        clinician_title.setObjectName("wtmhSectionTitle")
        self._clinician_box_layout.addWidget(clinician_title)
        self.clinician_layout = QVBoxLayout()
        self.clinician_layout.setSpacing(6)
        self._clinician_box_layout.addLayout(self.clinician_layout)

    def _show_instructions(self, text: Instructions) -> None:
        self.heading_label.setText(text.heading)
        self._fill(self.steps_layout, [f"{i}. {step}" for i, step in enumerate(text.steps, 1)], TYPE_BODY_LARGE)
        self.note_label.setText(text.note)
        self.note_label.setVisible(bool(text.note))  # Follow the Target has no NOTE line
        self._fill(self.clinician_layout, list(text.clinician), TYPE_BODY)

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
        self.show_note("")
        if self.refresh_blockers() or self._path_error:
            return  # a stale enabled button still cannot launch
        self.startRequested.emit()

    def _on_practice(self) -> None:
        self.show_note("")
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
