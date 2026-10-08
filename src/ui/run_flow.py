"""Run Test inside the dashboard: the Start page, Practice, the recorded run and what
happens when it ends (SPEC-compass-task-flow.md 4A.7, 4C.1-4C.8, R2, R11, HC8, plan
steps 6 and 7).

:class:`RunFlow` is what the Tests tab hands a test to when Run Test is pressed:

* **Start page** (:class:`~src.ui.start_test_page.StartTestPage`): always opens, with the
  Setup gate's reasons as its banner (R2: Start and Practice are off while any shows).
  Cancel, or Esc, goes back to the Test List; the nav is locked here as in a run.
* **Practice** -- a new ``AssessmentApp(run_mode="practice")`` with the same settings and
  at most 3 trials, driven by the gaze, recording nothing. Its end or its Quit returns to
  the Start page (with a one-line result after a finished practice); it can be repeated.
* **Start** -- a new ``AssessmentApp(run_mode="record")`` built from the test **record**
  (its own seed, ``test_id`` and name, its stored configuration), never from the Setup
  page's fields. The title bar is hidden while a practice or a recorded run is on screen.
  A run that cannot be started (an error from ``AssessmentApp``, a test that has run since,
  a changed Subject ID, no tracker) says why on the Start page and stays there, nav locked:
  the operator fixes the cause and presses Start or Practice again, or goes back.
* **Run end** -- every file is already on disk when ``on_finished`` fires. The operator
  chooses (``ask_run_end``: Test complete / Save partial / Discard), then
  :func:`~src.engine.run_result.finish_run` carries it out. Save returns to the Test List
  with the test selected, Save and View Report opens its report, Discard leaves the test
  Not Done. If the store refuses (a locked test, a write error, a path the discard guard
  rejects) the data stays on disk and the operator is told.

Nothing here touches ``setup_page.client`` beyond handing it to the run: the Setup tab
owns the connection, and a run never stops it.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..app import AssessmentApp
from ..engine.config import load_task_config
from ..engine.input_choice import resolve_input
from ..engine.run_mode import PRACTICE, RECORD
from ..engine.run_paths import path_budget_error
from ..engine.run_result import DISCARD, SAVE_AND_VIEW, RunResult, finish_run
from ..engine.session_files import SessionDiscardError
from ..engine.subject_tests import (
    STATUS_NOT_DONE,
    SubjectTest,
    TestLockedError,
    TestStoreError,
)
from .dashboard_flow import Flow, find_test
from .run_dialogs import PRIMARY, ask_choice, ask_run_end
from .settings_snapshot import merged_config
from .start_test_page import StartTestPage

if TYPE_CHECKING:  # pragma: no cover
    from .dashboard_window import DashboardWindow

PRACTICE_TRIALS = 3  # 4C.4
ALREADY_RUN_NOTE = "This test has already been run."


def _planned_trials(config: dict[str, Any]) -> int:
    """The test's configured trial count (``PRACTICE_TRIALS`` if the config has none)."""
    value = config.get("task", {}).get("trials")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else PRACTICE_TRIALS


class RunFlow:
    def __init__(self, window: DashboardWindow) -> None:
        self._window = window
        self.test: SubjectTest | None = None
        self.page: StartTestPage | None = None
        self.app: AssessmentApp | None = None  # the practice or recorded run on screen
        self._config: dict[str, Any] = {}  # the test's merged config: instructions, practice length
        # The run-end questions and the "could not save" notice, replaceable so a test
        # answers them without a modal loop.
        self.ask_end: Callable[[RunResult], str] = lambda result: ask_run_end(result, self._window)
        self.tell: Callable[[str, str], None] = self._tell

    # -- the Start page -----------------------------------------------------------------

    def open(self, test_id: str) -> None:
        """Run Test: open the Start page for ``test_id`` of the subject typed in Setup."""
        window = self._window
        if window.flow is not Flow.IDLE:
            return
        listing = window.test_list_page
        test = find_test(window, test_id)
        if test is None:
            listing.reload()
            listing.show_message("That test could not be found. The list was reloaded.")
            return
        if test.status != STATUS_NOT_DONE:  # the Run Test button is off for these (4A.4)
            listing.show_message(ALREADY_RUN_NOTE)
            return

        config = load_task_config(test.task_id)
        saved = test.configuration
        self._config = merged_config(config, saved.get("live"), saved.get("structural"))
        page = StartTestPage()
        page.set_blockers_provider(window.setup_page.run_blockers)
        page.set_test(test_name=test.name, task_id=test.task_id, cfg=self._config)
        # H9: a recorded run must not write a path over 240 characters. Checked once, as the
        # page opens; Start is off while it shows, Practice (which writes nothing) is not.
        page.set_path_error(path_budget_error(window.output_root, test.subject_id, test.task_id))
        page.startRequested.connect(self._on_start)
        page.practiceRequested.connect(self._on_practice)
        page.cancelRequested.connect(lambda: self._leave())
        page.goToSetupRequested.connect(lambda: self._leave(setup=True))
        self.page, self.test = page, test
        window.stack.addWidget(page)
        window.stack.setCurrentWidget(page)
        window.set_flow(Flow.START)
        page.setFocus()  # so Esc (Cancel) works without a click first

    def _leave(self, *, setup: bool = False) -> None:
        """End the flow: drop the Start page (and any run view still up) and return to
        the Test List with the test selected, or to Setup."""
        window = self._window
        test_id = self.test.test_id if self.test is not None else None
        self._remove_run_view()
        page, self.page = self.page, None
        if page is not None:
            window.stack.removeWidget(page)
            page.deleteLater()
        self.test = None
        if setup:
            window.show_setup()
            return
        window.show_tests(select=test_id)

    def _cannot_start(self, text: str) -> None:
        """Say why a run could not be started, on the Start page, which stays up."""
        if self.page is not None:
            self.page.show_note(text)

    def _remove_run_view(self) -> None:
        app, self.app = self.app, None
        if app is not None:
            self._window.stack.removeWidget(app.view)
            app.view.deleteLater()

    # -- launching ------------------------------------------------------------------------

    def _ready(self) -> SubjectTest | None:
        """The test as it is on disk now, if a run may start from this Start page: the
        Subject ID in Setup is still the test's (4A.7) and the test has not run since.
        Otherwise the reason is shown on the Start page, and this returns ``None``."""
        window, test = self._window, self.test
        if test is None or self.page is None or window.flow is not Flow.START:
            return None
        if test.subject_id.casefold() != window.setup_page.subject_id().casefold():
            self._cannot_start(
                f"Could not start {test.name}: the Subject ID in Setup is no longer {test.subject_id}."
            )
            return None
        fresh = find_test(window, test.test_id)
        if fresh is None or fresh.status != STATUS_NOT_DONE:
            self._cannot_start(f"Could not start {test.name}: {ALREADY_RUN_NOTE.lower()}")
            return None
        return fresh

    def _on_start(self) -> None:
        test = self._ready()
        if test is None:
            return
        app = self._build(
            test,
            RECORD,
            copy.deepcopy(test.configuration["structural"]),
            test_id=test.test_id,
            test_name=test.name,
            seed=test.seed,
            on_finished=self._on_run_finished,
        )
        if app is not None:
            self._show(app, Flow.RUN)

    def _on_practice(self, number: int) -> None:
        test = self._ready()
        if test is None:
            return
        # A copy: the test's own configuration is never touched (AC4).
        structural = copy.deepcopy(test.configuration["structural"])
        structural["trials"] = min(PRACTICE_TRIALS, _planned_trials(self._config))
        app = self._build(
            test,
            PRACTICE,
            structural,
            practice_index=number,
            on_finished=self._on_practice_finished,
        )
        if app is not None:
            self._show(app, Flow.PRACTICE)

    def _build(
        self, test: SubjectTest, mode: str, structural: dict[str, Any], **extra: Any
    ) -> AssessmentApp | None:
        """A new run of ``test``'s own configuration (never reuse one, 4C.1). On a failure
        the reason is shown on the Start page and this returns ``None``."""
        window, setup = self._window, self._window.setup_page
        tracker, calibration = setup.client, setup.calibration_result
        if resolve_input(self._config).is_mouse:
            # A Mouse test needs no tracker (H5): the Setup tab's one records alongside
            # when it is connected and calibrated, otherwise there is none (not even a
            # calibration is started for it).
            if tracker is not None and not (tracker.is_connected() and calibration is not None):
                tracker, calibration = None, None
        elif tracker is None:  # the Setup tab owns the device; a run must never dial it
            self._cannot_start(f"Could not start {test.name}: the tracker is not connected.")
            return None
        try:
            return AssessmentApp(
                task_id=test.task_id,
                replay_path=None,
                subject_id=test.subject_id,
                structural_overrides=structural or None,
                live_overrides=copy.deepcopy(test.configuration["live"]) or None,
                config_name=test.configuration["name"],
                client=tracker,
                preset_calibration_result=calibration,
                preset_calibration_source=setup.calibration_source if tracker is not None else None,
                preset_calibration_file=setup.calibration_file if tracker is not None else None,
                embedded=True,
                assessment_date=setup.assessment_date(),
                sex=setup.sex(),
                notes=setup.notes(),
                display_acknowledged=setup.display_acknowledged(),
                # This window is shown, so its screen is the monitor the run appears
                # on; the not-yet-embedded canvas cannot say.
                screen=window.screen(),
                run_mode=mode,
                **extra,
            )
        except Exception as exc:  # noqa: BLE001 - say so on the Test List rather than lose it
            self._cannot_start(f"Could not start {test.name}: {exc}")
            return None

    def _show(self, app: AssessmentApp, flow: Flow) -> None:
        window = self._window
        self.app = app
        window.stack.addWidget(app.view)
        window.stack.setCurrentWidget(app.view)
        window.set_flow(flow)  # nav locked, title bar hidden (HC8)
        app.view.canvas.setFocus()

    # -- a run ends ---------------------------------------------------------------------------

    def _on_practice_finished(self, result: RunResult) -> None:
        """Practice ended or was quit: back to the Start page, where the line says how it
        went (4C.4). Nothing was recorded."""
        window = self._window
        self._remove_run_view()
        page = self.page
        if page is None:  # cannot happen: the page lives until the flow ends
            window.show_tests()
            return
        page.set_practice_result(result)
        window.stack.setCurrentWidget(page)
        window.set_flow(Flow.START)
        page.setFocus()

    def _on_run_finished(self, result: RunResult) -> None:
        """The recorded run ended (finished, or quit with the question answered). The
        files are on disk already; the operator now says what becomes of them."""
        window, test = self._window, self.test
        if test is None:
            return
        # The title bar stays hidden: the end dialogs sit over the frozen canvas.
        window.set_flow(Flow.FINISHING)
        action = self.ask_end(result)
        try:
            done = finish_run(
                result,
                action,
                output_root=window.output_root,
                subject_id=test.subject_id,
                test_id=test.test_id,
            )
        except (TestLockedError, TestStoreError, ValueError, SessionDiscardError, OSError) as exc:
            # The data stays on disk and the test stays Not Done. (OSError: discard_session
            # unlinks files one by one, and Windows can refuse one that is open elsewhere.)
            self._leave()
            self.tell(*self._problem(action, test, result, exc))
            return
        self._leave()
        if done.action == SAVE_AND_VIEW:
            window.report_flow.open(test.test_id, report=done.report)

    @staticmethod
    def _problem(
        action: str, test: SubjectTest, result: RunResult, exc: Exception
    ) -> tuple[str, str]:
        # <subject folder>/runs/<task>/<name>: the run folder alone would not say where it is.
        folder = (
            "/".join(result.session_dir.parts[-4:])
            if result.session_dir is not None
            else "the subject folder"
        )
        reason = str(exc).rstrip(".")
        if action == DISCARD:
            return (
                "Results not discarded",
                f"The results could not be discarded: {reason}. The recorded data is still in "
                f"the folder {folder}. {test.name} stays Not Done.",
            )
        return (
            "Results not saved",
            f"The results were recorded but could not be saved to the test list: {reason}. "
            f"The data is in the folder {folder}. {test.name} stays Not Done.",
        )

    def _tell(self, title: str, text: str) -> None:
        ask_choice(self._window, title, text, [("ok", "OK", PRIMARY)], "ok", "ok")
