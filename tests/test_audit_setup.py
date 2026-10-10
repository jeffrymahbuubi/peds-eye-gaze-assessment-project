"""SPEC-audit-fixes.md H1, H3, H7, H8, H10 on the Setup page (F1, F5, F4, F6, F8): the device
actions are locked while a Setup thread runs, a second Connect stops the first client, a
calibration file marked not valid is refused, subject ids match ignoring case, and the
``gazepoint.enable.*`` switches reach the client.

Offscreen Qt. The threads are real ``QThread`` objects; what they would do on a socket is a
stand-in that blocks until the test lets it go. Nothing here touches a device or a port, and
``save_local_state`` is replaced so ``configs/local_state.json`` is never written.
"""

from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from src.engine.calibration import CalibrationResult, save_calibration_result
from src.engine.display_check import check_display
from src.engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from src.inputs.gazepoint_client import DeviceInfo
from src.ui import setup_page as setup_page_module
from src.ui.setup_page import INVALID_CALIBRATION_FILE_ALERT, SetupPage
from src.ui.setup_status import CALIBRATING_BLOCKER, CONNECTING_BLOCKER, needs_caption

VALID = CalibrationResult(n_points=5, mean_error_px=12.0, valid=True)
TIMED_OUT = CalibrationResult(n_points=5, mean_error_px=None, valid=False)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeClient:
    """A connected client that does nothing; counts the calls the page makes."""

    def __init__(self) -> None:
        self.stopped = False
        self.device_info = DeviceInfo(model="GP3HD", rate_hz=150)
        self.recheck_release = threading.Event()

    def is_connected(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True

    def refresh_device_info(self) -> DeviceInfo:
        self.recheck_release.wait(10)
        return self.device_info


@pytest.fixture
def page(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # sessions/ and the calibration timing log land under tmp
    monkeypatch.setattr(setup_page_module, "save_local_state", lambda *a, **k: None)
    page = SetupPage()
    page._apply_display_check(check_display(1920, 1080, 1.0))
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    yield page
    page.stop_threads()


def connected(page: SetupPage) -> FakeClient:
    """Give the page a connected client, as a finished Connect does."""
    page._client = FakeClient()
    page._on_state_changed()
    return page._client


def pump(condition, seconds: float = 5.0) -> None:
    """Deliver the threads' queued signals until ``condition`` holds."""
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)


def device_actions(page: SetupPage):
    return [
        page.connect_button,
        page.test_connection_button,
        page.recheck_device_info_button,
        page.do_calibration_button,
        page.load_calibration_button,
        page.continue_button,
    ]


class BlockingCalibration:
    """Stands in for ``Calibration``: ``run`` blocks where the real one polls the socket."""

    started = threading.Event()
    release = threading.Event()

    def __init__(self, client, **kwargs) -> None:
        self.client = client

    def run(self) -> CalibrationResult:
        BlockingCalibration.started.set()
        while not BlockingCalibration.release.is_set() and not getattr(self.client, "stopped", False):
            time.sleep(0.01)
        return VALID


@pytest.fixture
def blocking_calibration(monkeypatch):
    BlockingCalibration.started = threading.Event()
    BlockingCalibration.release = threading.Event()
    monkeypatch.setattr(setup_page_module, "Calibration", BlockingCalibration)
    yield BlockingCalibration
    BlockingCalibration.release.set()


# -- H1: Do Calibration locks the device actions (F1, F5) -----------------------------------------


def test_do_calibration_locks_the_page_and_blocks_start_and_continue(page, blocking_calibration):
    connected(page)
    page._calibration_result = VALID  # an earlier calibration: the old behaviour let a run start under it
    page._calibration_source = "measured"
    page._on_state_changed()
    assert page.run_blockers() == [] and page.can_continue()

    page.do_calibration_button.click()
    assert blocking_calibration.started.wait(5)
    assert page._calibration_thread is not None
    assert page.run_blockers() == [CALIBRATING_BLOCKER]
    assert page.continue_blockers() == [CALIBRATING_BLOCKER]
    assert not page.can_continue()
    assert not any(button.isEnabled() for button in device_actions(page))
    assert page.needs_label.text() == needs_caption([CALIBRATING_BLOCKER]) == "Needs: calibration to finish"
    assert not page.needs_label.isHidden()
    assert "wait for the calibration to finish" in page.continue_button.toolTip()

    page._on_do_calibration_clicked()  # a stray second press starts nothing
    page._on_load_calibration_clicked()
    page._on_recheck_device_info_clicked()
    assert page._recheck_thread is None

    blocking_calibration.release.set()
    pump(lambda: page._calibration_thread is None)
    assert page.run_blockers() == [] and page.can_continue()
    assert page.connect_button.isEnabled() and page.test_connection_button.isEnabled()
    assert page.do_calibration_button.isEnabled() and page.load_calibration_button.isEnabled()
    assert page.continue_button.isEnabled()
    assert page.needs_label.isHidden()


def test_the_calibration_blocker_comes_before_the_ones_it_explains(page, blocking_calibration):
    connected(page)
    page.do_calibration_button.click()
    assert blocking_calibration.started.wait(5)
    assert page.run_blockers() == [CALIBRATING_BLOCKER, CALIBRATION_BLOCKER]
    assert page.continue_blockers() == [CALIBRATING_BLOCKER]  # no calibration is never a Continue blocker


# -- H1/H3: Connect (F5) --------------------------------------------------------------------------


class FakeConnectThread(QThread):
    """Stands in for ``_ConnectThread``: waits for the test, then reports a client."""

    succeeded = Signal(object)
    failed = Signal(str)
    made: list[FakeConnectThread] = []

    def __init__(self, host, port, keep, enable=None, parent=None) -> None:
        super().__init__(parent)
        self.enable = enable
        self.client = FakeClient()
        self.release = threading.Event()
        FakeConnectThread.made.append(self)

    def run(self) -> None:
        self.release.wait(10)
        self.succeeded.emit(self.client)


@pytest.fixture
def connect_threads(monkeypatch):
    FakeConnectThread.made = []
    monkeypatch.setattr(setup_page_module, "_ConnectThread", FakeConnectThread)
    yield FakeConnectThread.made
    for thread in FakeConnectThread.made:
        thread.release.set()
        try:
            thread.wait(2000)
        except RuntimeError:  # it finished and the page deleted it
            pass


def test_connect_locks_the_page_and_a_second_connect_is_ignored(page, connect_threads):
    page.connect_button.click()
    (thread,) = connect_threads
    assert page.run_blockers()[0] == CONNECTING_BLOCKER
    assert page.continue_blockers() == [CONNECTING_BLOCKER]
    assert page.needs_label.text() == "Needs: connection to finish"
    assert not any(button.isEnabled() for button in device_actions(page))
    page._on_connect_clicked()  # programmatic: the button is off, the page ignores it too
    page._on_test_connection_clicked()
    assert len(connect_threads) == 1

    thread.release.set()
    pump(lambda: page._connect_thread is None)
    assert page.client is thread.client and CONNECTING_BLOCKER not in page.run_blockers()
    assert page.connect_button.isEnabled() and page.do_calibration_button.isEnabled()
    assert page.recheck_device_info_button.isEnabled()


def test_a_second_connect_stops_the_first_client(page, connect_threads):
    page.connect_button.click()
    connect_threads[0].release.set()
    pump(lambda: page._connect_thread is None)
    first = page.client
    assert first is connect_threads[0].client and not first.stopped

    page.connect_button.click()
    connect_threads[1].release.set()
    pump(lambda: page._connect_thread is None)
    assert page.client is connect_threads[1].client
    assert first.stopped  # no orphan socket, no second reconnect loop (H3)


def test_the_connect_thread_gets_the_enable_switches_of_default_yaml(page, connect_threads):
    """H10: the dashboard's Connect passes gazepoint.enable.* like the standalone launch does."""
    page.connect_button.click()
    assert connect_threads[0].enable == page._defaults["gazepoint"]["enable"]
    assert connect_threads[0].enable  # the shipped file lists the switches


def test_the_real_connect_thread_builds_its_client_with_the_enable_switches(qapp, monkeypatch):
    """H10 at the client: ``_ConnectThread.run`` hands ``enable`` to ``GazepointClient``."""
    seen = {}

    class SpyClient:
        def __init__(self, enable=None, **kwargs) -> None:
            seen["enable"] = enable

        def connect(self, host, port) -> None:
            raise OSError("nobody home")

    monkeypatch.setattr(setup_page_module, "GazepointClient", SpyClient)
    switches = {"time": True, "pupil_left": False}
    failures = []
    thread = setup_page_module._ConnectThread("127.0.0.1", 9, keep=True, enable=switches)
    thread.failed.connect(failures.append)
    thread.run()  # synchronously, as the client tests do
    assert seen["enable"] == switches and failures == ["nobody home"]


def test_a_thread_that_fails_unexpectedly_still_releases_the_lock(page, monkeypatch, qapp):
    """The page stays locked until the thread reports, so a bug in it must still report."""

    class Exploding:
        def __init__(self, *args, **kwargs) -> None: ...

        def run(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(setup_page_module, "Calibration", Exploding)
    connected(page)
    page.do_calibration_button.click()
    pump(lambda: page._calibration_thread is None)
    assert page.calibration_result is None and not page._busy()
    assert page.do_calibration_button.isEnabled()


# -- H1: Re-check ---------------------------------------------------------------------------------


def test_a_recheck_locks_the_same_controls(page):
    client = connected(page)
    page.recheck_device_info_button.setVisible(True)
    page._on_recheck_device_info_clicked()
    assert page._recheck_thread is not None
    assert not any(button.isEnabled() for button in device_actions(page))
    assert not page.can_continue()  # the button and can_continue() agree
    assert page.run_blockers() == [CALIBRATION_BLOCKER]  # no new sentence for it
    page._on_connect_clicked()
    assert page._connect_thread is None
    client.recheck_release.set()
    pump(lambda: page._recheck_thread is None)
    assert page.recheck_device_info_button.isEnabled() and page.continue_button.isEnabled()
    assert page.can_continue()


# -- H4: the window close waits for the threads ---------------------------------------------------


def test_stop_threads_ends_a_running_calibration_and_waits_for_it(page, blocking_calibration):
    client = connected(page)
    page.do_calibration_button.click()
    assert blocking_calibration.started.wait(5)
    assert page.stop_threads() is True  # the client is stopped under it, its poll returns
    assert client.stopped
    assert not page._calibration_thread.isRunning()


def test_stop_threads_with_nothing_running_is_a_no_op(page):
    assert page.stop_threads() is True


# -- H7/H8: Load Calibration File (F4, F6) --------------------------------------------------------


def load_file(page, monkeypatch, path):
    monkeypatch.setattr(setup_page_module.QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    page._on_load_calibration_clicked()


def test_a_calibration_file_marked_not_valid_is_refused_and_the_blocker_stays(page, monkeypatch, tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", TIMED_OUT)
    connected(page)
    load_file(page, monkeypatch, path)
    assert page.calibration_result is None and page.calibration_source is None
    assert page.calibration_alert_label.text() == INVALID_CALIBRATION_FILE_ALERT
    assert INVALID_CALIBRATION_FILE_ALERT == "This calibration file is not valid. Run Do Calibration."
    assert CALIBRATION_BLOCKER in page.run_blockers()
    assert page.calibration_badge.kind() == "not_calibrated"


def test_a_valid_file_still_loads_and_the_alert_says_valid(page, monkeypatch, tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", VALID)
    connected(page)
    load_file(page, monkeypatch, path)
    assert page.calibration_result == VALID and page.calibration_source == "loaded"
    assert page.calibration_alert_label.text() == "Calibration loaded: 5 points, mean error 12px, valid."
    assert CALIBRATION_BLOCKER not in page.run_blockers()


def test_the_subject_of_a_calibration_file_matches_ignoring_case(page, monkeypatch, tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", VALID)  # saved for P001
    page.subject_id_edit.setText("p001")  # typed in another case the next day
    load_file(page, monkeypatch, path)
    assert page.calibration_result == VALID and page.calibration_source == "loaded"

    page.subject_id_edit.setText("P002")  # a different child is still refused
    load_file(page, monkeypatch, path)
    assert page.calibration_result is None
    assert "does not match" in page.calibration_alert_label.text()
    assert TRACKER_BLOCKER in page.run_blockers()  # (no client here: unchanged rules)


# -- A1: the Start page under a running calibration -------------------------------------------------------------


@pytest.mark.parametrize("pointer", ["gaze", "mouse"])
def test_start_and_practice_are_blocked_while_a_calibration_runs(page, blocking_calibration, pointer):
    """The audit's repro: Start was enabled mid-calibration. A Mouse test records the same
    tracker alongside, so it is held back too."""
    from src.engine.config import load_task_config
    from src.ui.start_test_page import StartTestPage

    connected(page)
    page._calibration_result = VALID
    page._on_state_changed()
    start = StartTestPage()
    start.set_blockers_provider(page.run_blockers)
    cfg = load_task_config("click_grid")
    cfg["task"]["input"] = {"pointer": pointer, "selection": "dwell"}
    start.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    assert start.start_button.isEnabled() and start.practice_button.isEnabled()

    page.do_calibration_button.click()
    assert blocking_calibration.started.wait(5)
    start.refresh_blockers()
    assert not start.start_button.isEnabled() and not start.practice_button.isEnabled()
    assert start.banner_label.text() == CALIBRATING_BLOCKER == "Calibration in progress (Setup page)."

    blocking_calibration.release.set()
    pump(lambda: page._calibration_thread is None)
    start.refresh_blockers()
    assert start.start_button.isEnabled() and start.practice_button.isEnabled()
