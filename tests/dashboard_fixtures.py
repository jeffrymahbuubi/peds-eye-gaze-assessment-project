"""Shared helpers of the dashboard flow tests (``test_config_flow.py``,
``test_config_preview.py``): a ``DashboardWindow`` on a scratch folder, tests created
through the store, and stand-ins for the two save questions."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import src.app as app_module
from src.engine.subject_tests import create_test, list_tests
from src.ui.config_save_dialogs import CANCEL
from src.ui.dashboard_flow import Flow
from src.ui.dashboard_window import DashboardWindow
from src.ui.task_config_page import TaskConfigPage

SUBJECT = "TESTING"


def make_window(tmp_path: Path, monkeypatch) -> DashboardWindow:
    """A dashboard whose ``sessions/`` is under ``tmp_path`` (the working directory), with
    the subject typed in Setup and the Tests tab open. A run of ``AssessmentApp`` reads the
    task config with the input mode ``eye`` and calibration off, whatever the local
    ``default.yaml`` says."""
    monkeypatch.chdir(tmp_path)
    real_load = app_module.load_task_config

    def load(task_id, *args, **kwargs):
        cfg = real_load(task_id, *args, **kwargs)
        cfg.setdefault("input", {})["mode"] = "eye"
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    window = DashboardWindow()
    window.setup_page.subject_id_edit.setText(SUBJECT)
    window.tests_nav_button.click()
    return window


def close_window(window: DashboardWindow) -> None:
    if window.config_flow.preview_app is not None:
        window.config_flow.preview_app.timer.stop()
    window.close()


def new_test(win, task="click_grid", **kwargs):
    return create_test(win.output_root, SUBJECT, task, **kwargs)


def open_page(win, test) -> TaskConfigPage:
    win.test_list_page.reload()
    win.test_list_page.select_test(test.test_id)
    win.test_list_page.configure_button.click()
    assert win.flow is Flow.CONFIGURE
    return win.config_flow.page


def stored(win, test_id):
    return next(t for t in list_tests(win.output_root, SUBJECT).tests if t.test_id == test_id)


def control(page, key):
    return page._form.controls[key]


def tree(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) if root.exists() else []


class Answers:
    """Stand-ins for the two save questions; record what they were asked."""

    def __init__(self, new_name=None, update=CANCEL):
        """``update`` is one answer, or a list used in order (the last one repeats)."""
        self.new_name = new_name
        self.updates = list(update) if isinstance(update, (list, tuple)) else [update]
        self.name_asked: list[tuple[str, str]] = []
        self.update_asked: list[str] = []

    def install(self, flow):
        flow.ask_new_name = self._ask_name
        flow.ask_update = self._ask_update

    def _ask_name(self, intro, default):
        self.name_asked.append((intro, default))
        return self.new_name

    def _ask_update(self, name):
        self.update_asked.append(name)
        return self.updates.pop(0) if len(self.updates) > 1 else self.updates[0]
