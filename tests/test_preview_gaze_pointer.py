"""SPEC-preview-gaze-pointer.md H1-H9: Preview follows the test's Pointer (the real gaze when
the tracker is connected and calibrated, else the mouse), the run bar says which, a Mouse
pointer is never smoothed, and the Gaze Smoothing card is greyed for it. Offscreen Qt, a
scratch folder, stand-in trackers; nothing touches a device or a port."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QThread, Signal
from PySide6.QtWidgets import QApplication

import src.app as app_module
from src.app import AssessmentApp
from src.data.recorder import NullRecorder
from src.data.schema import GazeSample
from src.engine.calibration import CalibrationResult
from src.engine.clock import now_ns
from src.engine.config import load_task_config
from src.inputs.mouse_gaze import MouseGazeSource
from src.ui import setup_page as setup_page_module
from src.ui.dashboard_flow import Flow
from src.ui.task_config_page import TaskConfigPage
from tests.dashboard_fixtures import close_window, control, make_window, new_test, open_page, stored, tree

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
VALID = CalibrationResult(n_points=5, mean_error_px=12.3, valid=True)
MOUSE_TEST = {"input": {"pointer": "mouse", "selection": "dwell"}}
GAZE_SWITCH = {"input": {"pointer": "gaze", "selection": "switch"}}
SMOOTH = {"dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.35}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Tracker:
    """A live-looking connected tracker whose last sample and link the test controls; every
    call that would change the device or its queues is recorded."""

    is_live = True
    device_info = None

    def __init__(self) -> None:
        self.sample: GazeSample | None = None
        self.connected = True
        self.calls: list[str] = []

    def latest(self):
        return self.sample

    def is_connected(self) -> bool:
        return self.connected

    def connect(self, *a, **k) -> None:
        self.calls.append("connect")

    def start_streaming(self) -> None:
        self.calls.append("start_streaming")  # idempotent on the real client

    def stop(self) -> None:
        self.calls.append("stop")

    def clear_raw(self) -> None:
        self.calls.append("clear_raw")

    def drain_raw(self):
        return []


def gaze_at(x: float, y: float) -> GazeSample:
    return GazeSample(t_ns=now_ns(), x=x, y=y, valid=True)


class Pointing:
    def __init__(self) -> None:
        self.pos = QPoint(0, 0)

    def __call__(self) -> QPoint:
        return self.pos


# -- the run bar's wording, through the app (H4) ------------------------------------------------


@pytest.fixture
def make_app(qapp, tmp_path, monkeypatch):
    real_load = app_module.load_task_config
    root = tmp_path / "sessions"

    def load(task_id, *a, **k):
        cfg = real_load(task_id, *a, **k)
        cfg.setdefault("recording", {})["output_root"] = str(root)
        cfg["calibration"] = {**cfg.get("calibration", {}), "enabled": False}
        cfg.setdefault("input", {})["mode"] = "eye"
        return cfg

    monkeypatch.setattr(app_module, "load_task_config", load)
    monkeypatch.setattr(app_module, "preroll_ms", lambda mode: 0)
    made: list[AssessmentApp] = []

    def build(task_id="click_static", replay_path=None, **kw):
        app = AssessmentApp(task_id, replay_path, "P001", embedded=True, **kw)
        app.timer.stop()  # the tests tick by hand
        made.append(app)
        return app

    build.root = root
    yield build
    for app in made:
        app.timer.stop()
        if not app._shutdown_done:
            app.recorder.close()
            app._shutdown_done = True  # the teardown ends the run: a window close must not ask
        if app._owns_client:
            app.client.stop()
        if app.window is not None:
            app.window.close()


def gaze_preview(make_app, tracker=None, **kw):
    tracker = tracker or Tracker()
    kw.setdefault("structural_overrides", {"trials": 3})
    app = make_app(
        run_mode="preview", client=tracker, preset_calibration_result=VALID, preview_pointer="gaze", **kw
    )
    return app, tracker


def mouse_preview(make_app, structural=None, **kw):
    mouse = MouseGazeSource(cursor_pos=kw.pop("cursor_pos", None))
    app = make_app(
        run_mode="preview",
        client=mouse,
        preview_pointer="mouse",
        structural_overrides={"trials": 3, **(structural or {})},
        **kw,
    )
    mouse.bind_canvas(app.canvas)
    return app, mouse


def test_a_gaze_preview_names_the_gaze_and_keeps_the_trackers_state(make_app):
    app, tracker = gaze_preview(make_app)
    app._tick()  # no sample yet
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Gaze pointer, Waiting for gaze"
    tracker.sample = gaze_at(0.5, 0.5)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Gaze pointer, Tracking OK"
    tracker.connected = False  # the link drops mid-run: the pointer does not change (H1)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Gaze pointer, Tracker disconnected"
    assert app._pointer_is_mouse is False and app.pointer_source is tracker
    app.view.run_bar.pause_button.click()
    assert app.view.run_bar.status_text() == "PREVIEW, Paused"


def test_a_gaze_test_on_the_mouse_fallback_says_the_tracker_was_not_ready(make_app):
    app, _mouse = mouse_preview(make_app)  # the test's Pointer is Gaze (the default)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer (tracker not ready)"
    app.view.run_bar.pause_button.click()
    assert app.view.run_bar.status_text() == "PREVIEW, Paused"


def test_a_mouse_test_previews_on_the_mouse_without_a_reason(make_app):
    app, _mouse = mouse_preview(make_app, MOUSE_TEST)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer"


def test_a_preview_without_a_stated_pointer_is_a_mouse_preview(make_app):
    """The default of ``preview_pointer`` keeps the mouse path every earlier caller used."""
    mouse = MouseGazeSource()
    app = make_app(run_mode="preview", client=mouse, structural_overrides={"trials": 3})
    assert app._pointer_is_mouse is True and app.pointer_source is mouse


# -- the pointer rule (H2, H3) ---------------------------------------------------------------------


def test_a_gaze_preview_reads_the_tracker_and_never_calibrates_or_dials(make_app, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a gaze preview must never calibrate or dial the device")

    monkeypatch.setattr(app_module, "Calibration", boom)
    monkeypatch.setattr(app_module, "GazepointClient", boom)
    before = tree(make_app.root)
    app, tracker = gaze_preview(make_app)
    assert app.client is tracker and app.pointer_source is tracker and app._owns_client is False
    assert app._pointer_is_mouse is False
    assert isinstance(app.recorder, NullRecorder)
    assert app._gaze_recorded is False and app.metadata.gaze_recorded is False
    tracker.sample = gaze_at(0.5, 0.5)
    app._tick()
    app._shutdown()
    assert tracker.calls == ["start_streaming"]  # no connect, no clear_raw, no stop
    assert tree(make_app.root) == before  # nothing is written


def test_a_gaze_preview_moves_the_pointer_with_the_trackers_gaze(make_app):
    app, tracker = gaze_preview(make_app, live_overrides={**SMOOTH, "dwell.smoothing.enabled": False})
    tracker.sample = gaze_at(0.25, 0.75)
    app._tick()
    pointer = app.eye.poll(now_ns())
    assert pointer.valid and pointer.x == pytest.approx(0.25) and pointer.y == pytest.approx(0.75)


@pytest.mark.parametrize("missing", ["client", "calibration"])
def test_a_gaze_preview_without_the_setup_tracker_or_calibration_is_refused(make_app, monkeypatch, missing):
    def boom(*a, **k):
        raise AssertionError("must be refused before anything is dialled or calibrated")

    monkeypatch.setattr(app_module, "Calibration", boom)
    monkeypatch.setattr(app_module, "GazepointClient", boom)
    kw = {"client": Tracker() if missing == "calibration" else None}
    kw["preset_calibration_result"] = VALID if missing == "client" else None
    with pytest.raises(ValueError, match="gaze Preview"):
        make_app(run_mode="preview", preview_pointer="gaze", **kw)
    assert not make_app.root.exists()


def test_an_unknown_preview_pointer_is_refused(make_app):
    with pytest.raises(ValueError, match="preview pointer"):
        make_app(run_mode="preview", client=MouseGazeSource(), preview_pointer="eyes")


def test_the_preview_pointer_means_nothing_outside_a_preview(make_app):
    """A recorded or practice run takes its pointer from the test, whatever is stated."""
    for mode in ("record", "practice"):
        app = make_app(
            replay_path=str(FIXTURE), run_mode=mode, preset_calibration_result=VALID, preview_pointer="mouse"
        )
        assert app._pointer_is_mouse is False, mode


def test_a_gaze_switch_preview_on_the_real_gaze_hides_the_cursor_and_the_mouse_fallback_does_not(make_app):
    """H5: Space / Enter / click select, with the OS cursor parked as in a recorded run."""
    real, _tracker = gaze_preview(make_app, structural_overrides={"trials": 3, **GAZE_SWITCH})
    assert real._is_switch and real._hide_cursor is True
    fallback, _mouse = mouse_preview(make_app, GAZE_SWITCH)
    assert fallback._is_switch and fallback._hide_cursor is False


# -- no smoothing on a Mouse pointer (H6) ---------------------------------------------------------


def smoothing(app):
    return app.eye.smoother.config


def test_a_mouse_test_is_never_smoothed_in_record_practice_or_preview(make_app):
    record = make_app(structural_overrides=MOUSE_TEST, live_overrides=SMOOTH)
    practice = make_app(run_mode="practice", structural_overrides=MOUSE_TEST, live_overrides=SMOOTH)
    preview, _mouse = mouse_preview(make_app, MOUSE_TEST, live_overrides=SMOOTH)
    for mode, app in (("record", record), ("practice", practice), ("preview", preview)):
        assert smoothing(app).enabled is False, mode
        # The configuration says what the test was set to; only the pointer is raw.
        assert app.metadata.settings["live"]["dwell.smoothing.enabled"] is True, mode
        assert app.metadata.settings["live"]["dwell.smoothing.alpha"] == 0.35, mode


def test_a_gaze_test_keeps_its_smoothing_in_every_run_mode_and_on_the_mouse_fallback(make_app):
    record = make_app(replay_path=str(FIXTURE), preset_calibration_result=VALID, live_overrides=SMOOTH)
    practice = make_app(
        replay_path=str(FIXTURE), run_mode="practice", preset_calibration_result=VALID, live_overrides=SMOOTH
    )
    real, _tracker = gaze_preview(make_app, live_overrides=SMOOTH)
    fallback, _mouse = mouse_preview(make_app, live_overrides=SMOOTH)  # Gaze test, tracker not ready
    for name, app in (("record", record), ("practice", practice), ("gaze preview", real), ("fallback", fallback)):
        assert smoothing(app).enabled is True and smoothing(app).alpha == 0.35, name


def test_a_gaze_test_with_smoothing_turned_off_stays_unsmoothed(make_app):
    app, _mouse = mouse_preview(make_app, live_overrides={**SMOOTH, "dwell.smoothing.enabled": False})
    assert smoothing(app).enabled is False


def test_the_mouse_pointer_is_raw_and_the_fallbacks_is_smoothed(make_app):
    """A jump of the mouse reaches the pointer whole for a Mouse test, in part on the fallback."""

    def pointer_after_a_jump(structural):
        pointing = Pointing()
        app, _mouse = mouse_preview(make_app, structural, live_overrides=SMOOTH, cursor_pos=pointing)

        def at(fx, fy):
            pointing.pos = app.canvas.mapToGlobal(
                QPoint(round(fx * app.canvas.width()), round(fy * app.canvas.height()))
            )

        at(0.5, 0.5)
        app._tick()  # the smoother starts at the first sample
        at(0.9, 0.9)
        return app.eye.poll(now_ns())

    raw = pointer_after_a_jump(MOUSE_TEST)
    smoothed = pointer_after_a_jump(None)
    assert raw.x == pytest.approx(0.9, abs=0.02)
    assert 0.5 < smoothed.x < raw.x - 0.1  # pulled toward the jump, not onto it


def mouse_log(app) -> list[str]:
    """The session.log of a recorded run, once it is written."""
    app.recorder.close()
    return (app.recorder.session_dir / "session.log").read_text(encoding="utf-8").splitlines()


def test_a_recorded_mouse_run_logs_that_smoothing_is_off(make_app):
    app = make_app(structural_overrides=MOUSE_TEST, live_overrides=SMOOTH)
    log = mouse_log(app)
    assert sum("Gaze smoothing: off (mouse pointer)." in line for line in log) == 1


def test_a_recorded_gaze_run_does_not_log_it(make_app):
    app = make_app(replay_path=str(FIXTURE), preset_calibration_result=VALID, live_overrides=SMOOTH)
    assert not any("Gaze smoothing" in line for line in mouse_log(app))


def test_a_practice_or_preview_of_a_mouse_test_gets_the_line_too_and_a_gaze_test_does_not(make_app, monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(NullRecorder, "log", lambda self, message: lines.append(message))
    make_app(run_mode="practice", structural_overrides=MOUSE_TEST)
    mouse_preview(make_app, MOUSE_TEST)
    assert lines.count("Gaze smoothing: off (mouse pointer).") == 2
    lines.clear()
    make_app(run_mode="practice", replay_path=str(FIXTURE), preset_calibration_result=VALID)
    mouse_preview(make_app)  # a Gaze test on the fallback: its smoothing is on
    assert not any("Gaze smoothing" in line for line in lines)


# -- the configuration page (H7) --------------------------------------------------------------------


def _rect(w, h):
    return SimpleNamespace(width=lambda: w, height=lambda: h, x=lambda: 0, y=lambda: 0)


SCREEN = SimpleNamespace(
    geometry=lambda: _rect(1920, 1080),
    availableGeometry=lambda: _rect(1920.0, 1000.0),
    devicePixelRatio=lambda: 1.0,
    physicalSize=lambda: _rect(531.4, 298.9),
)


def page_for(task_id="click_grid", *, live=None, **structural):
    page = TaskConfigPage(task_id, load_task_config(task_id), screen=SCREEN)
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name=f"{task_id} 1", live=live, structural=structural or None)
    return page


def active(page, key):
    return control(page, key).isEnabled()


@pytest.mark.parametrize("task_id", ["click_static", "click_grid", "follow_moving", "scanning"])
def test_a_mouse_pointer_greys_the_smoothing_card_in_place_and_gaze_wakes_it(qapp, task_id):
    page = page_for(task_id)
    assert active(page, "dwell.smoothing.enabled")
    pointer = control(page, "input.pointer")
    pointer.setValue("mouse")
    assert not active(page, "dwell.smoothing.enabled") and not active(page, "dwell.smoothing.alpha")
    assert not control(page, "dwell.smoothing.enabled").isHidden()  # greyed in place, never hidden
    pointer.setValue("gaze")
    assert active(page, "dwell.smoothing.enabled")
    assert active(page, "dwell.smoothing.alpha") == control(page, "dwell.smoothing.enabled").isChecked()


@pytest.mark.parametrize("pointer", ["gaze", "mouse"])
@pytest.mark.parametrize("checked", [True, False])
def test_the_alpha_is_greyed_if_either_rule_says_so(qapp, pointer, checked):
    page = page_for()
    control(page, "dwell.smoothing.enabled").setChecked(checked)
    control(page, "input.pointer").setValue(pointer)
    expected = checked and pointer == "gaze"
    assert active(page, "dwell.smoothing.alpha") is expected
    # The label greys with its slider, whichever rule did it.
    for _master, widgets in page._form.dependents:
        assert all(w.isEnabled() is expected for w in widgets)
    assert active(page, "dwell.smoothing.enabled") is (pointer == "gaze")


def test_ticking_smoothing_cannot_wake_the_alpha_under_a_mouse_pointer(qapp):
    page = page_for()
    control(page, "dwell.smoothing.enabled").setChecked(False)
    control(page, "input.pointer").setValue("mouse")
    control(page, "dwell.smoothing.enabled").setChecked(True)  # the second rule still holds
    assert not active(page, "dwell.smoothing.alpha")
    control(page, "input.pointer").setValue("gaze")
    assert active(page, "dwell.smoothing.alpha")  # and now neither does
    control(page, "dwell.smoothing.enabled").setChecked(False)
    assert not active(page, "dwell.smoothing.alpha")  # the first rule alone still greys it


def test_a_saved_mouse_test_opens_with_the_card_greyed_and_its_values_kept(qapp):
    page = page_for(live={"dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.5}, **MOUSE_TEST)
    assert not active(page, "dwell.smoothing.enabled") and not active(page, "dwell.smoothing.alpha")
    live = page.collect_values()["live"]
    assert live["dwell.smoothing.enabled"] is True and live["dwell.smoothing.alpha"] == 0.5
    control(page, "input.pointer").setValue("gaze")
    live = page.collect_values()["live"]
    assert live["dwell.smoothing.enabled"] is True and live["dwell.smoothing.alpha"] == 0.5


def test_the_selection_greying_still_works_beside_the_pointers(qapp):
    page = page_for(**{"input": {"pointer": "mouse", "selection": "switch"}})
    assert not active(page, "dwell.threshold_ms") and not active(page, "dwell.progress_ring")
    assert active(page, "feedback.target_glow") and active(page, "dwell.refractory_ms")
    assert not active(page, "dwell.smoothing.enabled")


# -- Preview Test from the configuration page (H1, H2, A1-A4) ------------------------------------------


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    yield window
    close_window(window)


def setup_tracker(win, *, connected=True, calibrated=True) -> Tracker:
    tracker = Tracker()
    tracker.connected = connected
    win.setup_page._client = tracker
    win.setup_page._calibration_result = VALID if calibrated else None
    return tracker


def start_preview(win, page):
    page.preview_button.click()
    app = win.config_flow.preview_app
    assert app is not None
    app.timer.stop()  # the tests tick by hand
    return app


def smoothing_on(page):
    control(page, "dwell.smoothing.enabled").setChecked(True)


def test_a_gaze_test_previews_on_the_real_gaze_when_the_tracker_is_ready(win, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a gaze preview must never start a calibration")

    monkeypatch.setattr(app_module, "Calibration", boom)
    tracker = setup_tracker(win)
    root = Path(win.output_root)
    test = new_test(win)
    page = open_page(win, test)
    smoothing_on(page)
    before = tree(root)
    app = start_preview(win, page)
    assert win.flow is Flow.PREVIEW
    assert app.client is tracker and app._pointer_is_mouse is False
    assert app.metadata.run_mode == "preview" and app._gaze_recorded is False
    assert smoothing(app).enabled is True  # A1: Gaze Smoothing applies
    tracker.sample = gaze_at(0.5, 0.5)
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Gaze pointer, Tracking OK"
    # A4: the Setup tab's connection and calibration are exactly as they were.
    assert win.setup_page.client is tracker and win.setup_page.calibration_result is VALID
    app.view.run_bar.quit_requested.emit()
    assert win.flow is Flow.CONFIGURE and win.setup_page.client is tracker
    assert set(tracker.calls) <= {"start_streaming"}  # never connected, cleared or stopped
    assert tree(root) == before  # A1: nothing under sessions/
    assert stored(win, test.test_id).status == "not_done"


@pytest.mark.parametrize(
    ("connected", "calibrated"), [(False, False), (False, True), (True, False)], ids=["neither", "no link", "uncalibrated"]
)
def test_a_gaze_test_falls_back_to_the_mouse_when_the_tracker_is_not_ready(win, monkeypatch, connected, calibrated):
    def boom(*a, **k):
        raise AssertionError("no calibration may start")

    monkeypatch.setattr(app_module, "Calibration", boom)
    tracker = setup_tracker(win, connected=connected, calibrated=calibrated)
    page = open_page(win, new_test(win))
    smoothing_on(page)
    app = start_preview(win, page)
    assert isinstance(app.client, MouseGazeSource) and app._pointer_is_mouse is True
    assert smoothing(app).enabled is True  # A2: the gaze settings still apply
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer (tracker not ready)"
    assert tracker.calls == []  # the tracker is not touched


def test_a_gaze_test_with_no_tracker_at_all_previews_on_the_mouse(win):
    assert win.setup_page.client is None
    app = start_preview(win, open_page(win, new_test(win)))
    assert isinstance(app.client, MouseGazeSource)
    app._tick()
    assert app.view.run_bar.status_text().endswith("Mouse pointer (tracker not ready)")


def test_a_mouse_test_previews_on_the_mouse_raw_even_with_a_ready_tracker(win):
    tracker = setup_tracker(win)
    page = open_page(win, new_test(win))
    smoothing_on(page)
    control(page, "input.pointer").setValue("mouse")
    app = start_preview(win, page)
    assert isinstance(app.client, MouseGazeSource) and app._pointer_is_mouse is True
    assert smoothing(app).enabled is False  # A3
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer"
    assert tracker.calls == []


def test_the_unsaved_pointer_decides_not_the_stored_one(win):
    setup_tracker(win)
    test = new_test(win)
    page = open_page(win, test)
    control(page, "input.pointer").setValue("mouse")
    app = start_preview(win, page)
    assert app._pointer_is_mouse and isinstance(app.client, MouseGazeSource)
    app.view.run_bar.quit_requested.emit()
    control(page, "input.pointer").setValue("gaze")
    app = start_preview(win, page)
    assert not app._pointer_is_mouse
    app.view.run_bar.quit_requested.emit()
    assert stored(win, test.test_id).configuration["structural"] == {}  # nothing was saved


def test_a_gaze_switch_test_previews_with_the_cursor_hidden_only_on_the_real_gaze(win):
    setup_tracker(win)
    page = open_page(win, new_test(win))
    control(page, "input.selection").setValue("switch")
    app = start_preview(win, page)
    assert app._is_switch and app._hide_cursor is True
    app.view.run_bar.quit_requested.emit()
    win.setup_page._calibration_result = None  # the tracker is no longer ready
    app = start_preview(win, page)
    assert app._is_switch and app._hide_cursor is False


def test_a_gaze_preview_that_cannot_start_says_so_and_changes_nothing(win, monkeypatch):
    tracker = setup_tracker(win)
    page = open_page(win, new_test(win))

    def broken(**kwargs):
        raise RuntimeError("no canvas")

    monkeypatch.setattr("src.ui.config_flow.AssessmentApp", broken)
    page.preview_button.click()
    assert page.footer_message.text() == "Preview could not start: no canvas"
    assert win.flow is Flow.CONFIGURE and win.config_flow.preview_app is None
    assert tracker.calls == [] and win.setup_page.client is tracker


# -- a busy Setup page: its thread owns the device socket (H1) -----------------------------------------


class BlockingCalibration:
    """Stands in for ``Calibration`` on the Setup page: ``run`` blocks where the real one polls
    the socket, until the test lets it go."""

    started = threading.Event()
    release = threading.Event()

    def __init__(self, client, **kwargs) -> None:
        self.client = client

    def run(self) -> CalibrationResult:
        BlockingCalibration.started.set()
        BlockingCalibration.release.wait(10)
        return VALID


class HeldConnectThread(QThread):
    """Stands in for ``_ConnectThread``: waits for the test, then reports a new tracker."""

    succeeded = Signal(object)
    failed = Signal(str)
    made: list[HeldConnectThread] = []

    def __init__(self, host, port, keep, enable=None, parent=None) -> None:
        super().__init__(parent)
        self.client = Tracker()
        self.release = threading.Event()
        HeldConnectThread.made.append(self)

    def run(self) -> None:
        self.release.wait(10)
        self.succeeded.emit(self.client)


def pump(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def setup_threads(monkeypatch):
    """The Setup page's calibration and connect threads replaced by ones the test releases;
    ``save_local_state`` is replaced so ``configs/local_state.json`` is never written."""
    BlockingCalibration.started = threading.Event()
    BlockingCalibration.release = threading.Event()
    HeldConnectThread.made = []
    monkeypatch.setattr(setup_page_module, "save_local_state", lambda *a, **k: None)
    monkeypatch.setattr(setup_page_module, "Calibration", BlockingCalibration)
    monkeypatch.setattr(setup_page_module, "_ConnectThread", HeldConnectThread)
    yield SimpleNamespace(calibration=BlockingCalibration, connects=HeldConnectThread.made)
    BlockingCalibration.release.set()
    for thread in HeldConnectThread.made:
        thread.release.set()
        try:
            thread.wait(2000)
        except RuntimeError:  # it finished and the page deleted it
            pass


def test_the_setup_page_says_when_a_thread_is_using_the_device(win):
    setup = win.setup_page
    assert setup.device_busy() is False
    for name in ("_connect_thread", "_recheck_thread", "_calibration_thread"):
        setattr(setup, name, SimpleNamespace(isRunning=lambda: False))  # any thread object
        try:
            assert setup.device_busy() is True, name
        finally:
            setattr(setup, name, None)
        assert setup.device_busy() is False, name


def test_a_gaze_test_previewed_during_a_calibration_gets_the_mouse(win, monkeypatch, setup_threads):
    def boom(*a, **k):
        raise AssertionError("a preview must never calibrate")

    monkeypatch.setattr(app_module, "Calibration", boom)
    tracker = setup_tracker(win)  # connected, calibrated by an earlier calibration
    win.setup_page._on_state_changed()
    page = open_page(win, new_test(win))
    smoothing_on(page)
    win.setup_page._on_do_calibration_clicked()
    assert setup_threads.calibration.started.wait(5) and win.setup_page.device_busy()
    assert win.setup_page.tracker_ready() == (True, True)  # what the old rule would have trusted

    app = start_preview(win, page)
    assert isinstance(app.client, MouseGazeSource) and app._pointer_is_mouse is True
    assert smoothing(app).enabled is True  # a Gaze test on the fallback keeps the gaze settings
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer (tracker not ready)"
    assert tracker.calls == []  # not started, cleared, stopped or connected under the calibration
    app.view.run_bar.quit_requested.emit()
    assert win.flow is Flow.CONFIGURE and win.setup_page.client is tracker

    # Once the calibration is over the same test previews on the real gaze again.
    setup_threads.calibration.release.set()
    pump(lambda: win.setup_page._calibration_thread is None)
    app = start_preview(win, page)
    assert app.client is tracker and app._pointer_is_mouse is False


def test_a_gaze_test_previewed_during_a_connect_gets_the_mouse(win, setup_threads):
    tracker = setup_tracker(win)
    win.setup_page._on_state_changed()
    page = open_page(win, new_test(win))
    win.setup_page._on_connect_clicked()
    (thread,) = setup_threads.connects
    assert win.setup_page.device_busy() and win.setup_page.tracker_ready() == (True, True)

    app = start_preview(win, page)
    assert isinstance(app.client, MouseGazeSource) and app._pointer_is_mouse is True
    app._tick()
    assert app.view.run_bar.status_text() == "PREVIEW, Trial 1 of 3, Mouse pointer (tracker not ready)"
    assert tracker.calls == []
    app.view.run_bar.quit_requested.emit()

    # The new client is in once the connect has finished, and the preview uses it.
    thread.release.set()
    pump(lambda: win.setup_page._connect_thread is None)
    assert win.setup_page.client is thread.client
    app = start_preview(win, page)
    assert app.client is thread.client and app._pointer_is_mouse is False


@pytest.mark.parametrize("name", ["_connect_thread", "_recheck_thread", "_calibration_thread"])
def test_any_busy_setup_thread_sends_a_gaze_preview_to_the_mouse(win, name):
    """Test Connection and Re-check use the same locks as the two above."""
    tracker = setup_tracker(win)
    page = open_page(win, new_test(win))
    setattr(win.setup_page, name, SimpleNamespace(isRunning=lambda: False))
    try:
        app = start_preview(win, page)
        assert isinstance(app.client, MouseGazeSource)
        assert tracker.calls == []
        app.view.run_bar.quit_requested.emit()
    finally:
        setattr(win.setup_page, name, None)
