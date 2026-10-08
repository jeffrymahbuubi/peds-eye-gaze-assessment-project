"""SPEC-compass-task-flow.md AX1 and AX2 (P8b), end to end through ``DashboardWindow`` with a
mouse in place of the tracker (no device, no fake server): add two Grid Click tests, configure
one with a new named configuration, preview it, Start it (Practice first), pause, skip once and
let it complete, Save and View Report; then restart the window and find everything as it was.
Offscreen Qt, a scratch folder; the clock is the real one, so the whole run takes a few seconds."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.run_result import SAVE_AND_VIEW
from src.ui.dashboard_flow import Flow
from src.ui.dashboard_window import DashboardWindow
from tests.dashboard_fixtures import control
from tests.run_flow_fixtures import (
    SUBJECT,
    Answers,
    close_run_window,
    finish_trials,
    make_run_window,
    open_start,
    run_dirs,
    start_run,
    stored_tests,
    tick_until,
)

NAMED = "Fast hover"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def summary_rows(page):
    return {row[0]: row for row in page.summary.table.texts()}


def test_ax1_ax2_add_configure_preview_practice_run_report_and_restart(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    restarted = None
    try:
        answers = Answers(SAVE_AND_VIEW)
        answers.install(win.run_flow)
        listing = win.test_list_page

        # 1. Add 2 Grid Click tests.
        listing._choose_new_tests = lambda: ("click_grid", 2)
        listing.add_button.click()
        first, second = stored_tests(win)
        assert (first.name, second.name) == ("Grid Click 1", "Grid Click 2")

        # 2. Configure test 1 with a new named configuration.
        listing.select_test(first.test_id)
        listing.configure_button.click()
        page = win.config_flow.page
        control(page, "trials").setValue(3)
        control(page, "dwell.threshold_ms").setValue(300)
        control(page, "dwell.refractory_ms").setValue(0)
        control(page, "dwell.smoothing.enabled").setChecked(False)
        control(page, "task.inter_trial_interval_ms").setValue(0)
        page._form.config_combo.setEditText(NAMED)

        # 3. Preview it with the mouse: back on the page, nothing recorded.
        page.preview_button.click()
        win.config_flow.preview_app.timer.stop()
        win.config_flow.preview_app.view.run_bar.quit_requested.emit()
        assert win.flow is Flow.CONFIGURE and run_dirs(win) == []
        page.save_button.click()
        first = stored_tests(win)[0]
        assert win.flow is Flow.IDLE and first.configuration["name"] == NAMED

        # 4. Start it: Practice (three targets, nothing recorded), then Start.
        open_start(win, first)
        practice = start_run(win, mouse, "practice_button")
        finish_trials(practice, pointing)
        assert win.flow is Flow.START and run_dirs(win) == []
        app = start_run(win, mouse, "start_button")
        assert win.flow is Flow.RUN and app.metadata.config_name == NAMED

        # 5. Pause (the trial in flight is dropped and comes back), Skip once, then complete.
        tick_until(app, lambda: app.task.phase.name == "WAIT_INPUT")
        bar = app.view.run_bar
        bar.pause_button.click()
        for _ in range(3):
            app._tick()
        assert app.task.trials == [] and bar.status_text().startswith("Paused")
        bar.pause_button.click()
        tick_until(app, lambda: app.task.phase.name == "WAIT_INPUT")
        assert bar.skip_button.isEnabled()
        bar.skip_button.click()
        assert len(app.task.trials) == 1 and app.task.trials[0].is_skipped
        finish_trials(app, pointing)  # the other two trials, selected by hovering

        # 6. Save and View Report: the report of this test, with the named configuration.
        report_page = win.report_flow.page
        assert win.flow is Flow.REPORT and report_page is not None
        assert "Fast hover" in report_page.config_name_label.text()
        rows = summary_rows(report_page)
        selected = rows["All Targets Selected"]
        assert selected[1] == "100% (2/2)"  # 2 scored trials: the skipped one is excluded
        assert selected[3] != "—" and selected[4] != "—"  # Reaction Time and Entries are filled
        assert "1 skipped trial(s) excluded." in report_page.summary.note.text()
        report_page.save_button.click()

        # The Test List row reads "Done <date>" and is locked.
        done = stored_tests(win)[0]
        assert done.status == "done" and (done.planned_trials, done.completed_trials) == (3, 3)
        assert win.test_list_page.selected_test().test_id == first.test_id
        row = win.test_list_page.row_texts()[0]
        assert row[0] == "Grid Click 1" and row[2] == NAMED
        assert row[3] == "Done" and row[4] == done.completed_at[:10]
        assert not listing.run_button.isEnabled() and not listing.configure_button.isEnabled()

        # Copy Test: an unrun copy with the same configuration and a different seed.
        listing.copy_button.click()
        copy = stored_tests(win)[-1]
        assert copy.test_id not in (first.test_id, second.test_id)
        assert copy.status == "not_done" and copy.run_dir is None
        assert copy.configuration == done.configuration and copy.configuration["name"] == NAMED
        assert copy.seed != done.seed

        # The subject's folder holds exactly one run: practice and preview left none.
        assert len(run_dirs(win)) == 1 and done.run_dir == f"runs/click_grid/{run_dirs(win)[0].name}"
        assert run_dirs(win)[0].parent.parent.parent.name == "TESTING"  # <subject>/runs/<task>/<run>

        # L3: the subject's folder holds everything; none of the old folders was made.
        root = Path(win.output_root)
        assert sorted(p.name for p in root.iterdir() if p.name != "_system") == ["TESTING"]
        for old in ("_tests", "_settings", "_calibrations", "_diagnostics"):
            assert not (root / old).exists()
        assert (root / "TESTING" / "subject.json").is_file() and (root / "TESTING" / "tests").is_dir()

        # AX2: restart the app and type the same Subject ID.
        before = win.test_list_page.row_texts()
        restarted = DashboardWindow()
        restarted.setup_page.subject_id_edit.setText(SUBJECT)
        restarted.tests_nav_button.click()
        assert restarted.test_list_page.row_texts() == before
        restarted.test_list_page.select_test(first.test_id)
        restarted.test_list_page.report_button.click()
        reopened = restarted.report_flow.page
        assert restarted.flow is Flow.REPORT and reopened is not None
        assert "Fast hover" in reopened.config_name_label.text()
        assert summary_rows(reopened) == rows
        assert Path(restarted.output_root).resolve() == Path(win.output_root).resolve()
    finally:
        if restarted is not None:
            restarted.close()
        close_run_window(win)
