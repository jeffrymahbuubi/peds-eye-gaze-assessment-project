"""SPEC-subject-data-layout.md H9, W3 (L7): the Start page's path-too-long line. It is an error
alert of its own, separate from the blocker banner; it disables **Start only**, and Practice
(which writes nothing) stays on. Offscreen Qt."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.config import load_task_config
from src.engine.run_paths import PATH_TOO_LONG_TEXT, longest_run_path
from src.ui.start_test_page import StartTestPage
from tests.run_flow_fixtures import SUBJECT, close_run_window, make_run_window, open_start


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_page(blockers=None) -> StartTestPage:
    page = StartTestPage()
    page.set_blockers_provider((lambda: list(blockers)) if blockers is not None else None)
    cfg = load_task_config("click_grid")
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    return page


def alert_shown(page) -> bool:
    return not page.path_alert.isHidden()


# -- the page ---------------------------------------------------------------------------------------


def test_the_text_is_the_wireframes(qapp):
    assert PATH_TOO_LONG_TEXT == (
        "The data folder path is too long. Move the program folder closer to the drive root."
    )


def test_no_path_error_no_alert_and_both_buttons_on(qapp):
    page = make_page()
    assert not alert_shown(page)
    assert page.start_button.isEnabled() and page.practice_button.isEnabled()


def test_a_path_error_shows_the_alert_and_disables_start_only(qapp):
    page = make_page()
    page.set_path_error(PATH_TOO_LONG_TEXT)
    assert alert_shown(page) and page.path_alert_label.text() == PATH_TOO_LONG_TEXT
    assert page.path_alert.objectName() == "wtmhAlertError"
    assert not page.start_button.isEnabled()
    assert page.practice_button.isEnabled()  # practice writes nothing


def test_the_alert_is_separate_from_the_blocker_banner(qapp):
    page = make_page(blockers=["The tracker is not connected."])
    page.set_path_error(PATH_TOO_LONG_TEXT)
    assert alert_shown(page) and not page.banner.isHidden()
    assert page.path_alert is not page.banner and page.path_alert_label is not page.banner_label
    assert PATH_TOO_LONG_TEXT not in page.banner_label.text()
    assert not page.start_button.isEnabled() and not page.practice_button.isEnabled()  # the banner's doing
    page.set_path_error(None)
    assert not alert_shown(page) and not page.banner.isHidden()


def test_clearing_the_error_brings_start_back(qapp):
    page = make_page()
    page.set_path_error(PATH_TOO_LONG_TEXT)
    page.set_path_error("")
    assert not alert_shown(page) and page.start_button.isEnabled()


def test_the_blocker_refresh_does_not_undo_the_path_error(qapp):
    page = make_page()
    page.set_path_error(PATH_TOO_LONG_TEXT)
    page.refresh_blockers()
    page.refresh_blockers()
    assert not page.start_button.isEnabled() and page.practice_button.isEnabled()


def test_start_emits_nothing_while_the_path_error_shows_even_if_the_button_is_forced(qapp):
    page = make_page()
    started, practiced = [], []
    page.startRequested.connect(lambda: started.append(1))
    page.practiceRequested.connect(practiced.append)
    page.set_path_error(PATH_TOO_LONG_TEXT)
    page._on_start()
    assert started == []
    page.practice_button.click()
    assert practiced == [0]


def test_a_new_test_keeps_the_hosts_path_error_until_the_host_sets_another(qapp):
    page = make_page()
    page.set_path_error(PATH_TOO_LONG_TEXT)
    page.set_test(test_name="Other", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert alert_shown(page)  # the host (RunFlow) sets it each time it opens the page


# -- through the Run Test flow -----------------------------------------------------------------------


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    yield win
    close_run_window(win)


def root_of_length(tmp_path: Path, length: int) -> str:
    pad = length - len(str(tmp_path)) - 1
    root = tmp_path / ("p" * pad)
    assert len(str(root)) == length
    return str(root)


def test_a_normal_root_opens_the_start_page_without_the_alert(rig):
    from tests.dashboard_fixtures import new_test

    win = rig
    page = open_start(win, new_test(win))
    assert not alert_shown(page) and page.start_button.isEnabled() and page.practice_button.isEnabled()


def test_a_root_deep_enough_blocks_start_but_not_practice(rig, tmp_path):
    from tests.dashboard_fixtures import new_test

    win = rig
    win.output_root = root_of_length(tmp_path, 170)
    win._reload_tests()  # the Test List reads from the window's output root
    assert longest_run_path(win.output_root, SUBJECT, "click_grid") > 240
    test = new_test(win)  # still writable: the test record is a short path
    page = open_start(win, test)
    assert alert_shown(page) and page.path_alert_label.text() == PATH_TOO_LONG_TEXT
    assert not page.start_button.isEnabled()
    assert page.practice_button.isEnabled()
    page.start_button.click()  # nothing happens: no run folder is made
    assert win.run_flow.app is None
    assert not list(Path(win.output_root).glob("*/runs/*/*"))


def test_practice_still_runs_under_a_too_deep_root(rig, tmp_path):
    from tests.dashboard_fixtures import new_test
    from tests.run_flow_fixtures import configure_fast, start_run

    win = rig
    mouse = win.setup_page._client
    win.output_root = root_of_length(tmp_path, 170)
    win._reload_tests()  # the Test List reads from the window's output root
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse, "practice_button")
    assert app.run_mode == "practice" and win.run_flow.app is app
    assert not list(Path(win.output_root).glob("*/runs/*/*"))
