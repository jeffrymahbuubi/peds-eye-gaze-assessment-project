"""SPEC-compass-task-flow.md 4B.6, acceptance AB13-AB16: Preview Test inside
``DashboardWindow`` (offscreen Qt, a scratch folder, no tracker, nothing launched)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import src.ui.config_flow as flow_module
from src.engine.calibration import CalibrationResult
from src.engine.run_mode import PREVIEW_SEED
from src.ui.config_flow import PREVIEW_DONE_NOTE
from src.ui.dashboard_flow import Flow
from src.ui.task_config_page import TaskConfigPage
from tests.dashboard_fixtures import (
    close_window,
    control,
    make_window,
    new_test,
    open_page,
    stored,
    tree,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    yield window
    close_window(window)


# -- Preview Test: AB13-AB16 ---------------------------------------------------------------------------------------------------------------------------


class Pointing:
    def __init__(self):
        self.pos = QPoint(0, 0)

    def __call__(self):
        return self.pos


def start_preview(win, page):
    page.preview_button.click()
    app = win.config_flow.preview_app
    assert app is not None
    app.timer.stop()  # the tests tick by hand
    return app


def hover_target(app, pointing):
    x_norm, y_norm = app.task.target_position(app.task.targets[0], 0)
    pointing.pos = app.canvas.mapToGlobal(
        QPoint(round(x_norm * app.canvas.width()), round(y_norm * app.canvas.height()))
    )


def tick_until(app, condition, seconds=8.0):
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        time.sleep(0.004)


def fast_page(win, task="click_grid", trials=1):
    """A configuration page set up so a hover scores quickly."""
    test = new_test(win, task)
    page = open_page(win, test)
    control(page, "trials").setValue(trials)
    control(page, "dwell.threshold_ms").setValue(300)
    control(page, "dwell.refractory_ms").setValue(0)
    control(page, "dwell.smoothing.enabled").setChecked(False)
    return test, page


def test_preview_uses_the_unsaved_values_for_at_most_three_trials(win):
    test = new_test(win)
    page = open_page(win, test)
    control(page, "target.size").setValue("large")  # changed, not saved
    control(page, "dwell.threshold_ms").setValue(450)
    control(page, "trials").setValue(18)
    app = start_preview(win, page)
    assert app.config["task"]["target"]["size"] == "large"
    assert app._live_values["dwell.threshold_ms"] == 450
    assert len(app.task.targets) == 3  # min(3, 18)
    assert stored(win, test.test_id).configuration["structural"] == {}  # nothing was saved
    assert page.is_dirty()  # the edits are still the page's, unsaved


def test_a_test_configured_for_fewer_than_three_trials_previews_that_many(win):
    page = open_page(win, new_test(win))
    control(page, "trials").setValue(2)
    assert len(start_preview(win, page).task.targets) == 2


def test_preview_has_its_own_seed_never_the_tests(win):
    test = new_test(win)
    app = start_preview(win, open_page(win, test))
    assert app.metadata.seed == PREVIEW_SEED and app.metadata.seed != test.seed
    assert app.metadata.run_mode == "preview"


def test_preview_covers_the_window_and_locks_the_nav(win):
    page = open_page(win, new_test(win))
    app = start_preview(win, page)
    assert win.flow is Flow.PREVIEW and win.stack.currentWidget() is app.view
    assert win.title_bar.isHidden()
    assert not any(b.isEnabled() for b in win.title_bar.buttons)
    assert win.stack.indexOf(page) >= 0  # the page is still alive underneath
    app._tick()
    assert app.view.run_bar.status_text().startswith("PREVIEW")


def test_a_second_preview_press_is_ignored_while_one_runs(win):
    page = open_page(win, new_test(win))
    app = start_preview(win, page)
    win.config_flow._on_preview(page.collect_values())
    assert win.config_flow.preview_app is app and win.stack.count() == 4


def test_a_hover_of_dwell_length_on_the_target_scores_a_hit(win):
    _test, page = fast_page(win)
    app = start_preview(win, page)
    pointing = Pointing()
    app.client._cursor_pos = pointing
    app._tick()
    hover_target(app, pointing)
    tick_until(app, lambda: bool(app.task.trials))
    assert app.task.trials[0].is_hit is True


def test_a_natural_finish_returns_to_the_page_with_the_note(win):
    _test, page = fast_page(win)
    before = page.collect_values()
    scroll_before = page.scroll_area.verticalScrollBar().value()
    app = start_preview(win, page)
    pointing = Pointing()
    app.client._cursor_pos = pointing
    app._tick()
    hover_target(app, pointing)
    tick_until(app, lambda: win.flow is Flow.CONFIGURE)
    assert win.stack.currentWidget() is page and win.stack.count() == 3  # the view is gone
    assert win.config_flow.preview_app is None
    assert page.footer_message.text() == PREVIEW_DONE_NOTE == "Preview finished. Nothing was recorded."
    assert page.collect_values() == before and page.scroll_area.verticalScrollBar().value() == scroll_before
    assert not any(b.isEnabled() for b in win.title_bar.buttons)  # still locked: a page is open
    assert not win.title_bar.isHidden()


def test_quit_returns_to_the_page_exactly_as_it_was_without_the_note(win):
    _test, page = fast_page(win, trials=3)
    before = page.collect_values()
    entry_before = page.collect_entry()
    app = start_preview(win, page)
    app.view.run_bar.quit_requested.emit()  # nothing to save, so no question
    assert win.flow is Flow.CONFIGURE and win.stack.currentWidget() is page
    assert page.collect_values() == before and page.collect_entry() == entry_before
    assert page.footer_message.text() == ""  # only a natural finish says it finished


def test_escape_returns_to_the_page(win):
    _test, page = fast_page(win)
    before = page.collect_values()
    app = start_preview(win, page)
    app._tick()
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    app.canvas.keyPressEvent(event)
    assert win.flow is Flow.CONFIGURE and win.stack.currentWidget() is page
    assert page.collect_values() == before and page.footer_message.text() == ""


def test_the_page_is_not_reloaded_when_the_preview_ends(win, monkeypatch):
    _test, page = fast_page(win)
    loads = []
    real = TaskConfigPage.load_values
    monkeypatch.setattr(TaskConfigPage, "load_values", lambda self, **kw: loads.append(kw) or real(self, **kw))
    app = start_preview(win, page)
    app.view.run_bar.quit_requested.emit()
    assert loads == []  # HB9: Preview returns to the form exactly as it was


def test_the_typed_configuration_name_and_edits_survive_a_preview(win):
    page = open_page(win, new_test(win))
    page._form.config_combo.setEditText("Work in progress")
    page._form.notes_edit.setPlainText("keep me")
    control(page, "target.size").setValue("small")
    app = start_preview(win, page)
    app.view.run_bar.quit_requested.emit()
    assert page._form.config_combo.currentText() == "Work in progress"
    assert page._form.notes_edit.toPlainText() == "keep me"
    assert control(page, "target.size").value() == "small"


# -- AB14 / AB15: nothing is created, the tracker is never touched ---------------------------------------------------------------------------------


class FakeClient:
    """The Setup page's client: any call that reaches it is recorded."""

    is_live = True
    device_info = None

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return [] if name == "drain_raw" else None

        return call

    def is_connected(self):
        self.calls.append("is_connected")
        return True


def test_preview_creates_nothing_under_sessions(win):
    test, page = fast_page(win)
    root = Path(win.output_root)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    listing_before = tree(root)
    app = start_preview(win, page)
    pointing = Pointing()
    app.client._cursor_pos = pointing
    app._tick()
    hover_target(app, pointing)
    tick_until(app, lambda: win.flow is Flow.CONFIGURE)
    assert tree(root) == listing_before  # no run folder, no calibration.json, no diagnostics, no settings
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not (root / "_system").exists() and not (root / "TESTING" / "settings").exists()
    assert stored(win, test.test_id).status == "not_done"  # no card or test status change
    assert not any(root.glob("*/runs/*/*"))  # no run folder, so no run name is taken


def test_preview_works_with_no_tracker_and_no_calibration(win):
    assert win.setup_page.client is None and win.setup_page.calibration_result is None
    page = open_page(win, new_test(win))
    app = start_preview(win, page)
    app._tick()
    assert win.flow is Flow.PREVIEW


def test_preview_never_touches_the_setup_pages_client(win):
    # A Mouse test's preview leaves even a connected, calibrated tracker alone (H1); a Gaze
    # test's preview on it is in test_preview_gaze_pointer.py.
    fake = FakeClient()
    win.setup_page._client = fake
    win.setup_page._calibration_result = CalibrationResult(n_points=5, mean_error_px=10.0, valid=True)
    _test, page = fast_page(win)
    control(page, "input.pointer").setValue("mouse")
    app = start_preview(win, page)
    assert app.client is not fake
    pointing = Pointing()
    app.client._cursor_pos = pointing
    app._tick()
    hover_target(app, pointing)
    tick_until(app, lambda: win.flow is Flow.CONFIGURE)
    assert fake.calls == []  # no clear_raw, stop, drain_raw -- nothing at all


def test_preview_works_while_a_tracker_fault_is_showing(win):
    fake = FakeClient()
    fake.is_connected = lambda: False
    win.setup_page._client = fake
    page = open_page(win, new_test(win))
    app = start_preview(win, page)
    app._tick()
    assert win.flow is Flow.PREVIEW and fake.calls == []


def test_a_preview_that_cannot_start_says_so_on_the_page(win, monkeypatch):
    page = open_page(win, new_test(win))

    def broken(**kwargs):
        raise FileNotFoundError("No task config")

    monkeypatch.setattr(flow_module, "AssessmentApp", broken)
    page.preview_button.click()
    assert page.footer_message.text() == "Preview could not start: No task config"
    assert win.flow is Flow.CONFIGURE and win.stack.count() == 3 and win.config_flow.preview_app is None
