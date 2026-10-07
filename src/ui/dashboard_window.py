"""Persistent Setup / Tests dashboard (SPEC-ui-setup-task-selection.md, then
SPEC-compass-task-flow.md).

The tracker connection and calibration made in the Setup tab persist across every test:
the Tests tab lists the typed Subject ID's tests (:class:`~src.ui.test_list_page.SubjectTestListPage`)
and each flow that follows -- configure and preview (:class:`~src.ui.config_flow.ConfigFlow`),
start, practice, run and its end (:class:`~src.ui.run_flow.RunFlow`), report
(:class:`~src.ui.report_flow.ReportFlow`) -- is a page or an embedded run view put on top
of this window's stack, in place, with no new window and no subprocess ("nothing gets
relaunched").

Nothing about a subject or a task is kept in this window (4A.8): the list is read from
disk every time the tab opens, and a flow takes everything from its own test record, so
typing another Subject ID can never carry the previous child's settings over. The window
holds only which flow is active (:class:`~src.ui.dashboard_flow.Flow`); while one is, the
navigation is locked (R11).

The standalone ``python -m src.main --task X --gui`` launch path
(:func:`src.app.run_gui`) is untouched and still creates its own
``GazepointClient``/``MainWindow`` per run -- this window is an additional,
opt-in entry point (``--dashboard``), not a replacement.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..engine.config import CONFIG_ROOT
from .config_flow import ConfigFlow
from .dashboard_flow import (
    SETUP_INDEX,
    TESTS_INDEX,
    Flow,
    TitleBar,
    output_root_from_config,
)
from .report_flow import ReportFlow
from .run_flow import RunFlow
from .setup_page import SetupPage
from .test_list_page import SubjectTestListPage
from .wtmh_theme import STYLESHEET

_LOGO_PATH = CONFIG_ROOT / "assets" / "branding" / "wtmh_logo.png"
_ICON_PATH = CONFIG_ROOT / "assets" / "branding" / "WTMH.ico"


class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Pediatric Eye-Gaze Assessment v{__version__}")
        if _ICON_PATH.exists():
            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(str(_ICON_PATH)))

        self.flow = Flow.IDLE
        # Where tests, sessions and saved settings live; the Test List and every flow
        # read it from here (a test can point it at a scratch folder).
        self.output_root = output_root_from_config()

        central = QWidget(self)
        central.setObjectName("wtmhDashboard")
        central.setStyleSheet(STYLESHEET)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(_LOGO_PATH)
        self.setup_nav_button = self.title_bar.setup_button
        self.tests_nav_button = self.title_bar.tests_button
        outer.addWidget(self.title_bar)

        self.stack = QStackedWidget()
        self.setup_page = SetupPage()
        self.test_list_page = SubjectTestListPage()
        self.stack.addWidget(self.setup_page)  # SETUP_INDEX
        self.stack.addWidget(self.test_list_page)  # TESTS_INDEX
        # A sub-page or an embedded run view is added after these, and removed again.
        outer.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)
        self.resize(1024, 800)

        self.config_flow = ConfigFlow(self)
        self.run_flow = RunFlow(self)
        self.report_flow = ReportFlow(self)

        self.title_bar.navRequested.connect(self._go_to_tab)
        self.setup_page.continueRequested.connect(self._on_continue_to_tests)
        self.test_list_page.configureRequested.connect(self.config_flow.open)
        self.test_list_page.runRequested.connect(self.run_flow.open)
        self.test_list_page.reportRequested.connect(self.report_flow.open)
        self.test_list_page.backToSetupRequested.connect(lambda: self._go_to_tab(SETUP_INDEX))
        # A subject entered today is offered by Setup's completer as soon as it has a test.
        self.test_list_page.testsChanged.connect(self.setup_page.refresh_subject_completer)

        self.title_bar.set_active(SETUP_INDEX)

    # -- flow state and navigation ---------------------------------------------------

    def set_flow(self, flow: Flow) -> None:
        """Enter ``flow``: lock the navigation while it owns the window (R11) and give a
        canvas the whole window by hiding the title bar (HC8)."""
        self.flow = flow
        self._set_nav_locked(flow.locks_nav)
        self.title_bar.setVisible(not flow.hides_title_bar)

    def _set_nav_locked(self, locked: bool) -> None:
        self.title_bar.set_locked(locked)

    def _go_to_tab(self, index: int) -> None:
        if self.flow is not Flow.IDLE:
            return  # a sub-page or a run is showing
        if index == TESTS_INDEX:
            self._reload_tests()
        self.stack.setCurrentIndex(index)
        self.title_bar.set_active(index)

    def _reload_tests(self) -> None:
        """Read the typed Subject ID's tests from disk (4A.8: never kept in memory)."""
        self.test_list_page.set_subject(self.setup_page.subject_id(), self.output_root)

    def show_tests(self, select: str | None = None) -> None:
        """Back to the Tests tab after a flow ends: flow ``IDLE``, the list reloaded
        from disk, and ``select`` (a test id) selected."""
        self.set_flow(Flow.IDLE)
        self._reload_tests()
        if select is not None:
            self.test_list_page.select_test(select)
        self.stack.setCurrentIndex(TESTS_INDEX)
        self.title_bar.set_active(TESTS_INDEX)

    def show_setup(self) -> None:
        """Back to the Setup tab after a flow ends (the Start page's Go to Setup)."""
        self.set_flow(Flow.IDLE)
        self._go_to_tab(SETUP_INDEX)

    def _on_continue_to_tests(self) -> None:
        if not self.setup_page.can_continue():
            return
        self._go_to_tab(TESTS_INDEX)


def run_dashboard() -> int:
    existing = QApplication.instance()
    app = existing or QApplication([])
    if existing is None:
        # Windows' native "windowsvista" QStyle (the platform default, and
        # this app never set one before) largely ignores QSS-declared
        # custom arrow/indicator subcontrols -- it paints its own tiny
        # native glyph inside whatever box our stylesheet reserves,
        # regardless of the border-triangle CSS we declare (confirmed via
        # a zoomed qt-mcp screenshot, SPEC-ui-setup-task-selection.md
        # S12). Fusion is the standard, reliable fix: it fully honors
        # custom subcontrol QSS, which this app leans on heavily
        # (wtmh_theme.py).
        style = QStyleFactory.create("Fusion")
        app.setStyle(style)
        # S13: switching style alone isn't enough -- on a machine with
        # Windows dark mode on, Qt6 auto-adopts a DARK default QPalette
        # (confirmed: Window #1e1e1e, Button #3c3c3c) regardless of which
        # QStyle is active. Anything our QSS doesn't explicitly cover
        # (e.g. QCalendarWidget's weekday header, which QSS itself can't
        # reach for this widget -- see setup_page.py's
        # _theme_calendar_popup) silently falls back to that dark palette
        # instead of a neutral light one, which is almost certainly the
        # real explanation behind most of this app's "looks
        # dark/unthemed" reports so far, not just the calendar header.
        # Fusion's own standardPalette() is a real light default,
        # independent of OS dark-mode inheritance -- applying it here
        # gives every not-yet-explicitly-styled corner a sane light
        # fallback instead of near-black.
        app.setPalette(style.standardPalette())
    window = DashboardWindow()
    # showMaximized(), not show() (SPEC-live-settings-panel.md S10.8). The
    # old HUD column (gone, SPEC-compass-task-flow.md 4C.7) could not shrink
    # and was clipped when the window opened at resize(1024, 800); maximizing
    # afterwards did not rebuild an already-clipped layout. The pages that
    # replaced it are laid out for the project's 1920x1080 standard, so the
    # dashboard still starts maximized rather than entering that path.
    # The resize() above stays as the restore-down geometry.
    window.showMaximized()
    return app.exec()
