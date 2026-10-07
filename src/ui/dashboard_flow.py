"""The dashboard's flow state, its top navigation and the nav lock
(SPEC-compass-task-flow.md 4C.1, 4A.7, R11, HC8).

:class:`Flow` says what the window is doing. ``IDLE`` is "a tab is showing"; every other
value is a sub-page or a run that owns the window until it ends, so the navigation is
locked (R11: configure, start, practice, run, finishing, report) and, while a canvas is
on screen (Preview, Practice, a recorded run and its end dialogs), the title bar is
hidden so the canvas fills the window above the run bar (HC8).

:class:`TitleBar` is the brand strip with the nav buttons ``1 · Setup`` / ``2 · Tests``
(R11: the per-test report replaced the old ``3 · Results`` tab). It has one lock,
:meth:`TitleBar.set_locked`, which :meth:`DashboardWindow._set_nav_locked` calls, and one
signal, ``navRequested(index)``; the window decides whether to honour it.

:func:`find_test` is how every flow (Configure, Run, Report) gets its test: re-read from
disk, and only ever one of the subject typed in Setup.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..engine.config import load_default
from ..engine.subject_tests import SubjectTest, list_tests

SETUP_INDEX = 0
TESTS_INDEX = 1

NAV_LABELS = ("1 · Setup", "2 · Tests")


class Flow(Enum):
    IDLE = "idle"  # a tab (Setup, Tests) is showing
    CONFIGURE = "configure"  # the configuration page of a test
    PREVIEW = "preview"  # Preview Test, on top of the configuration page
    START = "start"  # the Start page of a test
    PRACTICE = "practice"  # a practice run (3 targets, nothing recorded)
    RUN = "run"  # a recorded run
    FINISHING = "finishing"  # the run-end dialogs, over the frozen canvas
    REPORT = "report"  # a test's report

    @property
    def locks_nav(self) -> bool:
        """Every state but ``IDLE`` owns the window: no tab can be opened (R11)."""
        return self is not Flow.IDLE

    @property
    def hides_title_bar(self) -> bool:
        """A canvas is on screen: it gets the whole window (HC8, 4B.6)."""
        return self in (Flow.PREVIEW, Flow.PRACTICE, Flow.RUN, Flow.FINISHING)


def find_test(window, test_id: str) -> SubjectTest | None:
    """The test as the disk has it now, for the subject typed in Setup: ``None`` if there
    is no Subject ID or no such test among that subject's, so another subject's test
    can never be reached (4A.7)."""
    subject = window.setup_page.subject_id()
    if not subject:
        return None
    for test in list_tests(window.output_root, subject).tests:
        if test.test_id == test_id:
            return test
    return None


def output_root_from_config() -> str:
    """Where sessions, saved settings and the Test List live: ``recording.output_root``
    of the default config, the same place the Setup page and every run read."""
    return str(load_default().get("recording", {}).get("output_root", "sessions"))


class TitleBar(QWidget):
    navRequested = Signal(int)

    def __init__(self, logo_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wtmhTitleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        if logo_path is not None and logo_path.exists():
            logo_label = QLabel()
            logo_label.setPixmap(QPixmap(str(logo_path)).scaledToHeight(28))
            layout.addWidget(logo_label)

        title_label = QLabel("Pediatric Eye-Gaze Assessment")
        title_label.setObjectName("wtmhBrandTitle")
        layout.addWidget(title_label)
        layout.addStretch(1)

        self.buttons: list[QPushButton] = []
        for index, label in enumerate(NAV_LABELS):
            button = QPushButton(label)
            button.setObjectName("wtmhNavButton")
            button.clicked.connect(lambda _checked=False, i=index: self.navRequested.emit(i))
            layout.addWidget(button)
            self.buttons.append(button)
        self.setup_button, self.tests_button = self.buttons

    def set_active(self, index: int) -> None:
        """Underline the button of the tab that is showing."""
        for i, button in enumerate(self.buttons):
            button.setProperty("active", i == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def set_locked(self, locked: bool) -> None:
        for button in self.buttons:
            button.setEnabled(not locked)
