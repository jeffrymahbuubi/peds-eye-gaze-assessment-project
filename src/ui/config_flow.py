"""Configure Test and Preview Test inside the dashboard (SPEC-compass-task-flow.md 4B.4-4B.6,
plan step 7, AB8, AB9, AB13-AB16, AB19).

:class:`ConfigFlow` is what the dashboard's Tests tab hands a test to when Configure Test
is pressed. It builds a :class:`~src.ui.task_config_page.TaskConfigPage` for that test
(on Configure, not at start-up, so the px figures match the monitor the window is on),
puts it on top of the dashboard's stack with the navigation locked, and from then on
answers the page's three signals:

* **Save & Continue** -- re-reads the test and refuses if it has run since (AB19), applies
  the 4B.4 rules (:func:`~src.ui.config_save.decide_save`: Standard stays untouched, an
  edited Standard needs a new name, an existing name asks Update / new name / Cancel),
  writes a profile file when a name is new or updated, stores the **complete** snapshot
  (:func:`~src.ui.settings_snapshot.complete_settings`) in the test, applies the name and
  notes, and returns to the Test List.
* **Cancel** -- the page has already asked about unsaved edits; returns to the Test List.
* **Preview Test** -- runs the *unsaved* form values with the mouse for at most 3 trials
  (``run_mode="preview"``: no tracker, no calibration, nothing recorded) in an embedded
  run view on top of the page. The page is never rebuilt, so every control, the scroll
  position and the unsaved edits are exactly as they were when the preview ends.

Nothing here touches ``setup_page.client``.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from ..app import AssessmentApp
from ..engine.config import load_task_config
from ..engine.run_result import RunResult
from ..engine.settings_profile import list_named_configurations, save_settings_profile
from ..engine.subject_tests import (
    STATUS_NOT_DONE,
    SubjectTest,
    TestLockedError,
    TestStoreError,
    list_tests,
    rename_test,
    update_test,
    validate_test_name,
)
from ..inputs.mouse_gaze import MouseGazeSource
from .config_save import (
    ASK_NEW_NAME,
    NEW_CONFIGURATION,
    STORE_STANDARD,
    UNCHANGED,
    decide_save,
    next_custom_name,
)
from .config_save_dialogs import (
    NEW_NAME,
    NEW_NAME_INTRO,
    STANDARD_INTRO,
    UPDATE,
    ask_config_name,
    ask_update_choice,
)
from .dashboard_flow import Flow, find_test
from .settings_snapshot import complete_settings
from .task_config_page import TaskConfigPage

if TYPE_CHECKING:  # pragma: no cover
    from .dashboard_window import DashboardWindow

PREVIEW_TRIALS = 3  # 4B.6: abbreviated, timings unchanged
LOCKED_NOTE = "This test has already been run and can't be changed."
PREVIEW_DONE_NOTE = "Preview finished. Nothing was recorded."


class ConfigFlow:
    def __init__(self, window: DashboardWindow) -> None:
        self._window = window
        self.page: TaskConfigPage | None = None
        self.test: SubjectTest | None = None
        self.preview_app: AssessmentApp | None = None
        self._config: dict[str, Any] = {}
        # The two save questions, replaceable so a test answers without a modal loop.
        self.ask_new_name = lambda intro, default: ask_config_name(self.page, intro, default)
        self.ask_update = lambda name: ask_update_choice(self.page, name)

    # -- opening and closing the page ---------------------------------------------------

    def open(self, test_id: str) -> None:
        """Configure Test: open the page for ``test_id`` of the subject typed in Setup."""
        window = self._window
        if window.flow is not Flow.IDLE:
            return
        listing = window.test_list_page
        test = self._find(test_id)
        if test is None:
            listing.reload()
            listing.show_message("That test could not be found. The list was reloaded.")
            return
        if test.status != STATUS_NOT_DONE:  # the Configure button is off for these (HB7)
            listing.show_message(LOCKED_NOTE)
            return

        root = window.output_root
        config = load_task_config(test.task_id)
        page = TaskConfigPage(test.task_id, config, screen=window.screen())
        page.set_context(
            subject_id=test.subject_id,
            existing_test_names=[t.name for t in list_tests(root, test.subject_id).tests],
            named_configs=list_named_configurations(root, test.subject_id, test.task_id),
        )
        saved = test.configuration
        page.load_values(
            test_name=test.name,
            notes=test.notes,
            config_name=saved.get("name"),
            live=saved.get("live") or None,
            structural=saved.get("structural") or None,
        )
        page.saveRequested.connect(self._on_save)
        page.cancelRequested.connect(self._on_cancel)
        page.previewRequested.connect(self._on_preview)
        self.page, self.test, self._config = page, test, config
        window.stack.addWidget(page)
        window.stack.setCurrentWidget(page)
        window.set_flow(Flow.CONFIGURE)

    def _close_page(self) -> None:
        page, self.page = self.page, None
        test_id = self.test.test_id if self.test is not None else None
        self.test = None
        if page is not None:
            self._window.stack.removeWidget(page)
            page.deleteLater()
        self._window.show_tests(select=test_id)

    def _find(self, test_id: str) -> SubjectTest | None:
        """The test as the disk has it now, for the subject typed in Setup."""
        return find_test(self._window, test_id)

    # -- Save & Continue (4B.4) -------------------------------------------------------------

    def _on_save(self, entry: dict[str, Any]) -> None:
        page, window = self.page, self._window
        if page is None or self.test is None:
            return
        root = window.output_root
        fresh = self._find(self.test.test_id)
        if fresh is None or fresh.status != STATUS_NOT_DONE:
            page.show_note(LOCKED_NOTE)  # AB19: writes nothing
            return
        names = [t.name for t in list_tests(root, fresh.subject_id).tests]
        problem = validate_test_name(entry["test_name"], names, exclude=fresh.name)
        if problem is not None:
            page.show_note(problem)
            return
        resolved = self._resolve_name(entry)
        if resolved is None:  # the operator cancelled a question: stay on the page
            return
        name, write_profile = resolved
        values = complete_settings(fresh.task_id, self._config, entry["live"], entry["structural"])
        try:
            if write_profile:
                save_settings_profile(
                    root,
                    fresh.subject_id,
                    fresh.task_id,
                    values["live"],
                    values["structural"],
                    self._calibration(),
                    name,
                )
            update_test(
                root,
                fresh.subject_id,
                fresh.test_id,
                configuration={"name": name, **values},
                notes=entry["notes"],
            )
            if entry["test_name"] != fresh.name:
                rename_test(root, fresh.subject_id, fresh.test_id, entry["test_name"])
        except TestLockedError:
            page.show_note(LOCKED_NOTE)
            return
        except (OSError, ValueError, TestStoreError) as exc:
            page.show_note(f"Could not save: {exc}")
            return
        if write_profile:
            window.setup_page.refresh_subject_completer()  # a subject typed today is offered
        self._close_page()

    def _resolve_name(self, entry: dict[str, Any]) -> tuple[str, bool] | None:
        """The configuration name to store and whether a profile file is written for it,
        asking the operator where 4B.4 says to; ``None`` when they cancel."""
        page, test, window = self.page, self.test, self._window
        named = {
            c.name.casefold(): c
            for c in list_named_configurations(window.output_root, test.subject_id, test.task_id)
        }
        name = entry["config_name"]
        while True:
            decision = decide_save(
                test.task_id,
                self._config,
                name,
                entry["live"],
                entry["structural"],
                page.standard_values(),
                named,
            )
            if decision.kind in (STORE_STANDARD, UNCHANGED):
                return decision.name, False
            if decision.kind == NEW_CONFIGURATION:
                return decision.name, True
            default = next_custom_name(c.name for c in named.values())
            if decision.kind == ASK_NEW_NAME:
                asked = self.ask_new_name(STANDARD_INTRO, default)
            else:  # ASK_UPDATE
                answer = self.ask_update(decision.name)
                if answer == UPDATE:
                    return decision.name, True
                asked = self.ask_new_name(NEW_NAME_INTRO, default) if answer == NEW_NAME else None
            if asked is None:
                return None
            name = asked  # decided again: the new name may itself exist

    def _calibration(self) -> dict[str, Any] | None:
        """The calibration these settings were tuned under, for the profile (descriptive
        only, S10.5.5): from the Setup page, since there is no run to ask."""
        result = self._window.setup_page.calibration_result
        if result is None:
            return None
        return {"error_px": result.mean_error_px, "points": result.n_points}

    def _on_cancel(self) -> None:
        self._close_page()

    # -- Preview Test (4B.6) ----------------------------------------------------------------------

    def _on_preview(self, values: dict[str, Any]) -> None:
        """Run the unsaved form for at most 3 trials with the mouse; record nothing."""
        page, test, window = self.page, self.test, self._window
        if page is None or test is None or window.flow is not Flow.CONFIGURE:
            return
        structural = copy.deepcopy(values["structural"])
        structural["trials"] = min(PREVIEW_TRIALS, int(structural.get("trials", PREVIEW_TRIALS)))
        mouse = MouseGazeSource()
        try:
            app = AssessmentApp(
                task_id=test.task_id,
                replay_path=None,
                subject_id=test.subject_id,
                structural_overrides=structural,
                live_overrides=values["live"],
                client=mouse,
                embedded=True,
                on_finished=self._on_preview_finished,
                run_mode="preview",
                screen=window.screen(),
            )
        except Exception as exc:  # noqa: BLE001 - say so on the page rather than lose it
            page.show_note(f"Preview could not start: {exc}")
            return
        # The canvas exists only now; until it is bound the source reports "no gaze".
        mouse.bind_canvas(app.view.canvas)
        self.preview_app = app
        window.stack.addWidget(app.view)
        window.stack.setCurrentWidget(app.view)
        window.set_flow(Flow.PREVIEW)
        app.view.canvas.setFocus()

    def _on_preview_finished(self, result: RunResult) -> None:
        """Quit, Alt-Q, Esc or the last trial: back to the page exactly as it was (HB9).
        Only a natural finish says so in the footer; ``load_values()`` is never called."""
        window = self._window
        app, self.preview_app = self.preview_app, None
        if app is not None:
            window.stack.removeWidget(app.view)
            app.view.deleteLater()
        page = self.page
        if page is not None:
            window.stack.setCurrentWidget(page)
        window.set_flow(Flow.CONFIGURE)
        if page is not None and result.is_complete:
            page.show_note(PREVIEW_DONE_NOTE)
