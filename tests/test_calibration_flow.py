"""The App-screen calibration from the Setup page and the Start page (SPEC-app-drawn-calibration.md
A3, A4, A6, A7, A10b, A12, A13): the real calibration thread against a fake Gazepoint Control that
answers a calibration with ``CAL`` records, with the calibration window on the offscreen platform.

No device. ``SPEEDS`` is shortened for the run so a point is 0.22 s; ``configs/local_state.json``
is never written (``save_local_state`` is replaced).
"""

from __future__ import annotations

import math
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine import calibration_run
from src.engine import calibration_settings as cs
from src.engine.calibration import CalibrationResult
from src.engine.config import load_task_config
from src.engine.display_check import check_display
from src.engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from src.ui import setup_page as setup_page_module
from src.ui.calibration_window import (
    STATE_MONITOR,
    STATE_PROCESSING,
    STATE_RESULTS,
    STATE_RUNNING,
    STATE_WAITING,
)
from src.ui.dashboard_flow import Flow
from src.ui.setup_page import SetupPage
from src.ui.setup_status import CALIBRATING_BLOCKER
from src.ui.start_test_page import StartTestPage
from tests.calibration_fixtures import FakeControl
from tests.dashboard_fixtures import close_window, make_window, new_test
from tests.run_flow_fixtures import open_start

QUICK = cs.Speed(0.1, 0.1)  # a point is DELAY + TIMEOUT + 20 ms = 0.22 s on the fake


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def control():
    fake = FakeControl()
    yield fake
    fake.close()


@pytest.fixture
def quick(monkeypatch):
    """Every speed preset is QUICK, and the waits of 4.2 are short."""
    for name in cs.SPEEDS:
        monkeypatch.setitem(cs.SPEEDS, name, QUICK)
    monkeypatch.setattr(calibration_run, "FALLBACK_GRACE_S", 0.3)
    monkeypatch.setattr(calibration_run, "RESULT_WAIT_S", 3.0)


@pytest.fixture
def saved(monkeypatch):
    """The updates the page hands to ``save_local_state`` (nothing reaches the real file)."""
    updates: list[dict] = []
    monkeypatch.setattr(setup_page_module, "save_local_state", lambda update, *a, **k: updates.append(update))
    return updates


def pump(condition, seconds: float = 10.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)


def connected(page: SetupPage, control: FakeControl):
    """Give the page a tracker that is a socket to the fake Control."""
    client = control.client()
    client.is_connected = lambda: True
    client.stop = lambda: None
    client.latest_eye_position = lambda: None
    page._client = client
    page._on_state_changed()
    return client


@pytest.fixture
def page(qapp, tmp_path, monkeypatch, saved, control, quick):
    monkeypatch.chdir(tmp_path)  # sessions/ and the timing log land under tmp
    page = SetupPage()
    page._apply_display_check(check_display(1920, 1080, 1.0))
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    connected(page, control)
    yield page
    page.stop_threads()


def window_of(page: SetupPage):
    flow = page._calibration_flow
    assert flow is not None and flow.window is not None
    return flow.window


def run_to_results(page: SetupPage):
    pump(lambda: page._calibration_flow is not None and page._calibration_flow.window is not None
         and page._calibration_flow.window.state() == STATE_RESULTS)
    return window_of(page)


# -- the App screen, end to end (A1, A6, A7) ------------------------------------------------------------


def test_do_calibration_opens_the_window_runs_the_points_and_shows_the_map(page, control):
    page.do_calibration_button.click()
    window = window_of(page)
    assert window.isVisible() and page._busy() and page.run_blockers()[0] == CALIBRATING_BLOCKER
    assert not any(b.isEnabled() for b in (page.do_calibration_button, page.load_calibration_button, page.continue_button))
    pump(lambda: window.state() in (STATE_RUNNING, STATE_PROCESSING, STATE_RESULTS))
    run_to_results(page)

    looks = window.map.looks()
    assert [look.point for look in looks] == [1, 2, 3, 4, 5]
    assert all(look.band == cs.BAND_GOOD for look in looks)  # the fake gaze is 0.1 degree off
    assert window.attention_label.text() == "All points are good."
    assert page._calibration_result is None  # nothing is taken in until Back
    # (the icon's positions, in the order sent, are checked in test_calibration_run.py and test_calibration_window.py)
    assert control.state.show == 0  # Control's own window stayed hidden

    window.back_button.click()
    pump(lambda: page._calibration_flow is None and page._calibration_thread is None)
    assert not window.isVisible() and not page._busy()
    result = page.calibration_result
    assert result.valid and result.n_points == 5 and page.calibration_source == "measured"
    assert page.calibration_badge.kind() == "calibrated" and "5 points" in page.calibration_badge.text()
    assert page.calibration_alert.kind() == "success" and "Calibration measured: 5 points" in page.calibration_alert_label.text()
    assert page.view_details_button.isEnabled() and page.do_calibration_button.isEnabled()
    assert result.record["mode"] == "app_drawn" and result.record["improve_runs"] == 0
    assert all("score" in point and "error_deg" in point for point in result.per_point)
    assert (control.state.delay, control.state.timeout) == (0.5, 1.5)  # Control's own, restored


def test_improve_calibration_runs_all_points_again_and_counts_the_runs(page, control):
    page.do_calibration_button.click()
    window = run_to_results(page)
    first_error = page._calibration_flow._last_run.result.mean_error_px  # from CALIB_RESULT
    runs_before = control.state.runs
    control.state.eye_offset = (0.002, 0.001)  # the child sits better on the second run
    window.improve_button.click()
    assert window.state() == STATE_WAITING and page._busy()  # back to the empty stage
    run_to_results(page)
    assert control.state.runs == runs_before + 1
    assert len(window.map.looks()) == 5  # all points again, not just the weak ones
    window.improve_button.click()
    run_to_results(page)
    window.back_button.click()
    pump(lambda: page._calibration_flow is None and page._calibration_thread is None)
    assert page.calibration_result.record["improve_runs"] == 2  # the re-runs before Back
    # The last run's, from its CALIB_RESULT: (0.002, 0.001) of this 800 px offscreen screen is 1.8 px.
    assert page.calibration_result.mean_error_px == pytest.approx(math.hypot(0.002 * 800, 0.001 * 800), abs=0.05)
    assert page.calibration_result.mean_error_px < first_error  # replaced, not kept from the first
    assert control.commands("CALIBRATE_START") == ['<SET ID="CALIBRATE_START" STATE="1" />'] * 3  # three runs, no stop


def test_a_weak_point_is_marked_on_the_map_and_counted_under_it(page, control):
    control.state.eye_offset = (0.10, 0.0)  # about 1.8 degrees off on this 800 px offscreen screen: amber
    page.do_calibration_button.click()
    window = run_to_results(page)
    looks = window.map.looks()
    assert {look.band for look in looks} == {cs.BAND_FAIR} and all(look.ring_px > 3 for look in looks)
    assert window.attention_label.text().startswith("5 points need attention.")
    window.back_button.click()
    pump(lambda: page._calibration_flow is None)


def test_show_monitor_works_during_the_results(page, control):
    page.do_calibration_button.click()
    window = run_to_results(page)
    window.monitor_button.click()
    assert window.state() == STATE_MONITOR and window.head_panel.isVisible()
    assert window.head_panel.reading().state.name == "NO_EYES"  # connected tracker, no eye data
    window.back_button.click()
    pump(lambda: page._calibration_flow is None)


# -- A4: Esc and the x ---------------------------------------------------------------------------------


def test_escape_during_a_point_stops_control_and_keeps_the_old_calibration(page, control):
    old = CalibrationResult(9, 20.0, True)
    page._calibration_result, page._calibration_source = old, "measured"
    page._on_state_changed()
    badge, alert = page.calibration_badge.text(), (page.calibration_alert.kind(), page.calibration_alert_label.text())

    page.do_calibration_button.click()
    window = window_of(page)
    pump(lambda: window.state() == STATE_RUNNING)
    window._escape.activated.emit()  # Esc
    pump(lambda: page._calibration_flow is None and page._calibration_thread is None)

    control.sync(page._client)
    commands = control.state.commands
    stop = commands.index('<SET ID="CALIBRATE_START" STATE="0" />')
    assert commands[stop + 1] == '<SET ID="CALIBRATE_SHOW" STATE="0" />'
    assert not window.isVisible() and not page._busy()
    assert page.calibration_result is old  # untouched
    assert page.calibration_badge.text() == badge
    assert (page.calibration_alert.kind(), page.calibration_alert_label.text()) == alert
    assert (control.state.delay, control.state.timeout) == (0.5, 1.5)


def test_the_x_during_processing_cancels_too_and_the_run_never_reports(page, control):
    page.do_calibration_button.click()
    window = window_of(page)
    pump(lambda: window.state() == STATE_PROCESSING or window.state() == STATE_RESULTS)
    window.close_button.click()
    pump(lambda: page._calibration_flow is None and page._calibration_thread is None)
    assert page.calibration_result is None and page.calibration_badge.kind() == "not_calibrated"
    assert CALIBRATION_BLOCKER in page.run_blockers()


@pytest.mark.parametrize("how", ["escape", "x", "close"])
def test_escape_or_x_on_the_results_map_is_back_and_keeps_the_new_result(page, control, how):
    """The run is over and Control already holds the new calibration, so Esc / x on the map is
    Back (hub answer 2026-10-13): nothing is discarded and no stop is sent."""
    page.do_calibration_button.click()
    window = run_to_results(page)
    starts_before = len(control.commands("CALIBRATE_START"))
    {"escape": window._escape.activated.emit, "x": window.close_button.click, "close": window.close}[how]()
    pump(lambda: page._calibration_flow is None)
    control.sync(page._client)
    assert page.calibration_result is not None and page.calibration_result.valid
    assert page.calibration_result.record["mode"] == "app_drawn" and page.calibration_badge.kind() == "calibrated"
    assert page.calibration_alert.kind() == "success"
    assert len(control.commands("CALIBRATE_START")) == starts_before  # no CALIBRATE_START STATE="0"
    assert not page._busy()


def test_escape_during_show_monitor_is_back_too(page, control):
    page.do_calibration_button.click()
    window = run_to_results(page)
    window.monitor_button.click()
    assert window.state() == STATE_MONITOR
    window._escape.activated.emit()
    pump(lambda: page._calibration_flow is None)
    assert page.calibration_result is not None and page.calibration_result.valid


def test_a_calibration_with_no_valid_eye_shows_grey_points_and_back_reports_it(page, control):
    control.state.valid_eyes = False  # no camera
    page.do_calibration_button.click()
    window = run_to_results(page)
    assert [look.band for look in window.map.looks()] == [cs.BAND_NONE] * 5
    assert [look.text for look in window.map.looks()] == ["-"] * 5
    assert window.attention_label.text().startswith("5 points need attention.")
    window.back_button.click()
    pump(lambda: page._calibration_flow is None)
    assert page.calibration_result is None and page.calibration_alert.kind() == "danger"
    assert CALIBRATION_BLOCKER in page.run_blockers()


def test_closing_the_application_during_the_window_ends_everything(page, control):
    page.do_calibration_button.click()
    window = window_of(page)
    pump(lambda: window.state() == STATE_RUNNING)
    assert page.stop_threads() is True
    assert not window.isVisible() and page._calibration_flow is None


# -- A3: the fallback to Control's window -----------------------------------------------------------------


def test_a_silent_control_falls_back_to_its_own_window_with_the_alert(page, control):
    control.state.silent_runs = 1
    page.do_calibration_button.click()
    window = window_of(page)
    pump(lambda: page._calibration_flow is None and page._calibration_thread is None, seconds=20)
    assert not window.isVisible()  # the app's window closed when the fallback began
    result = page.calibration_result
    assert result is not None and result.valid and result.record["mode"] == "control_fallback"
    assert result.record["layout"] == "vendor"
    assert page.calibration_alert.kind() == "warning"
    assert page.calibration_alert_label.text().startswith(calibration_run.FALLBACK_ALERT)
    assert "Calibration measured" in page.calibration_alert_label.text()
    assert control.commands("CALIBRATE_SHOW")[-1].endswith('STATE="1" />')  # Control's own window


# -- A12 and A10b: the Control screen and the greyed controls ------------------------------------------------


def test_the_control_screen_runs_todays_path_without_the_window(page, control):
    page.calibration_settings_panel.set_settings(cs.CalibrationSettings(screen=cs.SCREEN_CONTROL, speed="slow"))
    page.do_calibration_button.click()
    assert page._calibration_flow is None  # no window, no map
    pump(lambda: page._calibration_thread is None, seconds=20)
    result = page.calibration_result
    assert result.valid and result.record["mode"] == "control" and result.record["speed"] == "slow"
    assert control.commands("CALIBRATE_SHOW")[-1].endswith('STATE="1" />')  # CALIBRATE_SHOW STATE="1"
    assert f'<SET ID="CALIBRATE_DELAY" VALUE="{QUICK.glide_s}" />' in control.commands("CALIBRATE_DELAY")
    assert page.calibration_alert.kind() == "success"


def test_the_app_screen_is_the_default_and_background_target_and_size_grey_out_for_control(page):
    panel = page.calibration_settings_panel
    assert page.calibration_settings().screen == cs.SCREEN_APP
    assert all(widget.isEnabled() for widget in panel.drawn_by_app())
    panel.screen_choice.setValue(cs.SCREEN_CONTROL)
    assert not any(widget.isEnabled() for widget in panel.drawn_by_app())
    assert panel.points_combo.isEnabled() and panel.speed_combo.isEnabled()  # sent through the API (4.3b)
    panel.screen_choice.setValue(cs.SCREEN_APP)
    assert all(widget.isEnabled() for widget in panel.drawn_by_app())


def test_the_old_tick_box_and_point_spin_are_gone_and_the_card_has_the_new_controls(page):
    assert not hasattr(page, "show_calibration_checkbox") and not hasattr(page, "point_count_spin")
    panel = page.calibration_settings_panel
    assert [panel.points_combo.itemText(i) for i in range(panel.points_combo.count())] == ["5 points", "9 points"]
    assert [panel.target_combo.itemText(i) for i in range(6)] == ["Bee", "Star", "Ball", "Fish", "Flower", "Car"]
    assert not panel.target_combo.itemIcon(0).isNull()  # a thumbnail of each built-in icon
    assert [panel.size_combo.itemText(i) for i in range(3)] == ["Small", "Normal", "Large"]
    assert [panel.background_combo.itemText(i) for i in range(3)] == ["White", "Black", "Grey"]
    assert [b.text() for b in panel.screen_choice.buttons().values()] == ["App (Grid 3 style)", "Gazepoint Control"]


# -- A7: the settings persist per PC ----------------------------------------------------------------------------


def test_every_change_is_saved_per_pc_and_read_back_by_the_next_page(page, saved, monkeypatch):
    panel = page.calibration_settings_panel
    panel.speed_combo.setCurrentIndex(panel.speed_combo.findData("fast"))
    panel.target_combo.setCurrentIndex(panel.target_combo.findData("fish"))
    panel.size_combo.setCurrentIndex(panel.size_combo.findData("large"))
    panel.background_combo.setCurrentIndex(panel.background_combo.findData("black"))
    panel.points_combo.setCurrentIndex(panel.points_combo.findData("9"))
    panel.screen_choice.setValue(cs.SCREEN_CONTROL)
    wanted = cs.CalibrationSettings("control", 9, "fast", "fish", "large", "black")
    assert saved[-1] == cs.settings_state(wanted) and len(saved) == 6  # one save per change
    monkeypatch.setattr(setup_page_module, "load_local_state", lambda *a, **k: saved[-1])
    assert SetupPage().calibration_settings() == wanted


def test_the_settings_land_in_calibration_json(page, control, tmp_path):
    from src.engine.calibration import load_calibration_result, save_calibration_result

    panel = page.calibration_settings_panel
    panel.set_settings(cs.CalibrationSettings("app", 5, "fast", "car", "small", "grey"))
    page.do_calibration_button.click()
    window = run_to_results(page)
    window.back_button.click()
    pump(lambda: page._calibration_flow is None)
    path = tmp_path / "calibration.json"
    save_calibration_result(path, "P001", page.calibration_result)
    record = load_calibration_result(path).result.record
    assert (record["mode"], record["speed"], record["icon"], record["size"], record["background"], record["layout"]) == (
        "app_drawn", "fast", "car", "small", "grey", "grid3",
    )
    assert (record["delay_s"], record["timeout_s"]) == (QUICK.glide_s, QUICK.hold_s)


def test_the_timing_log_gets_the_mode_the_points_and_the_windows_hold_times(page, control):
    page.do_calibration_button.click()
    window = run_to_results(page)
    window.back_button.click()
    pump(lambda: page._calibration_flow is None)
    import json

    from src.engine.calibration import calibration_timing_log_path

    records = [json.loads(line) for line in calibration_timing_log_path(page.output_root).read_text(encoding="utf-8").splitlines()]
    app_record = next(r for r in records if r.get("mode") == "app_drawn")
    assert app_record["outcome"] == "calib_result" and len(app_record["points"]) == 5
    first = app_record["points"][0]
    assert first["t_hold_start_s"] - first["t_start_s"] <= QUICK.glide_s  # the hold rule, as scheduled
    window_record = next(r for r in records if r.get("kind") == "app_window")
    runs = window_record["runs"]
    assert len(runs) == 1 and len(runs[0]) == 5 and runs[0][0]["hold_scheduled_s"] <= QUICK.glide_s


# -- A13: Calibrate on the Start page ------------------------------------------------------------------------------


@pytest.fixture
def start_win(qapp, tmp_path, monkeypatch, saved, control, quick):
    win = make_window(tmp_path, monkeypatch)
    setup = win.setup_page
    setup.sex_combo.setCurrentIndex(1)
    setup._apply_display_check(check_display(1920, 1080, 1.0))
    connected(setup, control)
    yield win
    setup.stop_threads()
    close_window(win)


def test_calibrate_on_the_start_page_runs_the_window_back_returns_here_and_the_blocker_clears(start_win, control):
    win = start_win
    page = open_start(win, new_test(win, "click_grid"))
    assert page.blockers() == [CALIBRATION_BLOCKER] and not page.start_button.isEnabled()
    assert page.calibrate_button.text() == "Calibrate" and page.calibrate_button.isEnabled()
    assert page.calibrate_button.objectName() == "wtmhGhost"  # secondary tier, next to Practice

    page.calibrate_button.click()
    window = window_of(win.setup_page)
    assert not page.start_button.isEnabled() and not page.calibrate_button.isEnabled()  # busy: nothing starts under it
    pump(lambda: window.state() == STATE_RESULTS)
    assert win.flow is Flow.START
    window.back_button.click()
    pump(lambda: win.setup_page._calibration_flow is None)

    assert win.flow is Flow.START and win.stack.currentWidget() is page  # back here, not on Setup
    assert win.setup_page.calibration_result.valid and win.setup_page.calibration_badge.kind() == "calibrated"
    page.refresh_blockers()
    assert page.blockers() == [] and page.start_button.isEnabled() and page.calibrate_button.isEnabled()
    assert not page.calibration_alert.isVisibleTo(page)


def test_calibrate_after_a_fallback_shows_the_alert_on_the_start_page(start_win, control):
    control.state.silent_runs = 1
    page = open_start(start_win, new_test(start_win, "click_grid"))
    page.calibrate_button.click()
    pump(lambda: start_win.setup_page._calibration_flow is None and start_win.setup_page._calibration_thread is None, seconds=20)
    assert page.calibration_alert.isVisibleTo(page)
    assert page.calibration_alert_label.text() == calibration_run.FALLBACK_ALERT
    page.calibrate_button.click()  # the next Calibrate clears it
    assert not page.calibration_alert.isVisibleTo(page)
    pump(lambda: start_win.setup_page._calibration_flow is not None)
    start_win.setup_page._calibration_flow.window._escape.activated.emit()
    pump(lambda: start_win.setup_page._calibration_flow is None and start_win.setup_page._calibration_thread is None)


def test_esc_on_the_calibration_window_returns_to_the_start_page_with_nothing_changed(start_win, control):
    page = open_start(start_win, new_test(start_win, "click_grid"))
    page.calibrate_button.click()
    window = window_of(start_win.setup_page)
    pump(lambda: window.state() == STATE_RUNNING)
    window._escape.activated.emit()
    pump(lambda: start_win.setup_page._calibration_flow is None and start_win.setup_page._calibration_thread is None)
    assert start_win.flow is Flow.START and start_win.setup_page.calibration_result is None
    assert page.blockers() == [CALIBRATION_BLOCKER]


def test_calibrate_is_off_without_a_tracker_and_hidden_for_a_mouse_test(qapp):
    page = StartTestPage()
    cfg = load_task_config("click_grid")
    cfg["task"]["input"] = {"pointer": "gaze", "selection": "dwell"}
    page.set_blockers_provider(lambda: [TRACKER_BLOCKER])
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    assert page.calibrate_button.isVisibleTo(page) and not page.calibrate_button.isEnabled()
    page.set_blockers_provider(lambda: [CALIBRATING_BLOCKER])
    assert not page.calibrate_button.isEnabled()
    page.set_blockers_provider(lambda: [CALIBRATION_BLOCKER])  # only "No calibration yet": that is what Calibrate fixes
    assert page.calibrate_button.isEnabled()
    emitted = []
    page.calibrateRequested.connect(lambda: emitted.append(1))
    page.calibrate_button.click()
    assert emitted == [1]

    cfg["task"]["input"] = {"pointer": "mouse", "selection": "dwell"}
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    assert not page.calibrate_button.isVisibleTo(page)  # gaze tests only
    page.set_blockers_provider(lambda: [])
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    assert not page.calibrate_button.isVisibleTo(page)


def test_the_calibrate_button_sits_between_practice_and_cancel(qapp):
    page = StartTestPage()
    names = [page.start_button, page.practice_button, page.calibrate_button, page.cancel_button]
    page.resize(1200, 800)
    page.show()
    QApplication.processEvents()
    xs = [button.mapTo(page, button.rect().topLeft()).x() for button in names]
    assert xs == sorted(xs) and page.practice_button.objectName() == page.calibrate_button.objectName() == "wtmhGhost"
    page.close()
