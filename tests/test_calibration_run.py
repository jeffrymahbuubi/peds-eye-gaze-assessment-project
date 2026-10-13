"""SPEC-app-drawn-calibration.md acceptance A1-A4, A10a at the engine: ``run_calibration`` against a
fake Gazepoint Control that answers a calibration with ``CAL`` records.

No device. The fake (``tools/fake_gazepoint_server.py``) runs in-process on an ephemeral port; a
point lasts DELAY + TIMEOUT there, so the tests use short timings (``timing=``) and the speed
presets only where just the commands sent matter (the run is cancelled at its first point).
"""

from __future__ import annotations

import json
import math
import threading

import pytest

from src.engine import calibration_settings as settings_module
from src.engine.calibration import CalibrationResult
from src.engine.calibration_motion import PHASE_GLIDE, PHASE_HOLD, TargetMotion
from src.engine.calibration_run import (
    EVENT_FALLBACK,
    EVENT_PROCESSING,
    EVENT_RESULT_POINT,
    EVENT_START_POINT,
    FALLBACK_ALERT,
    MODE_APP,
    MODE_CONTROL,
    MODE_FALLBACK,
    read_device_timing,
    restore_device_timing,
    run_calibration,
)
from src.engine.calibration_settings import SPEEDS, CalibrationSettings, Speed, app_layout
from tests.calibration_fixtures import CapturingControl, FakeControl, control_factory

FAST = (0.1, 0.1)  # (DELAY, TIMEOUT) of the tests: a point is 0.22 s on the fake


@pytest.fixture
def control():
    fake = FakeControl()
    fake.state.delay, fake.state.timeout = 0.7, 1.3  # Control's own, to be given back
    yield fake
    fake.close()


def settings(**kwargs) -> CalibrationSettings:
    return CalibrationSettings(**kwargs)


# -- A1: the points, in the order sent, and the hold rule ------------------------------------------


def test_a_five_point_run_draws_each_point_in_the_layout_order(control):
    """The ``CALIB_START_PT`` records, in the order the Grid 3 layout sent them (D5)."""
    events = []
    client = control.client()
    run = run_calibration(
        client, settings(), make_control=CapturingControl(None), on_event=events.append, timing=FAST
    )
    starts = [e for e in events if e.kind == EVENT_START_POINT]
    assert [(e.point, e.x, e.y) for e in starts] == [(i + 1, x, y) for i, (x, y) in enumerate(app_layout(5))]
    assert [e.delay_s for e in starts] == [FAST[0]] * 5
    assert starts[0].n_points == 5
    # Each point's result follows its start, and the last result opens "Processing".
    order = [(e.kind, e.point) for e in events]
    for point in range(1, 6):
        assert order.index((EVENT_START_POINT, point)) < order.index((EVENT_RESULT_POINT, point))
    assert order[-1] == (EVENT_PROCESSING, 5)
    assert run.mode == MODE_APP and run.outcome == "calib_result" and not run.cancelled
    assert run.result.valid and run.result.n_points == 5 and len(run.result.per_point) == 5


def test_the_commands_sent_hide_control_and_set_the_pair_and_the_layout(control):
    client = control.client()
    run_calibration(
        client, settings(points=9), make_control=CapturingControl(None), timing=FAST, cancel=_cancel_at_once()
    )
    control.sync(client)
    sets = [line for line in control.state.commands if "<SET" in line]
    assert sets[0] == '<SET ID="CALIBRATE_SHOW" STATE="0" />'  # Control's own window stays hidden
    assert control.commands("CALIBRATE_DELAY")[-2:] == [
        '<SET ID="CALIBRATE_DELAY" VALUE="0.1" />', '<SET ID="CALIBRATE_DELAY" VALUE="0.7" />'
    ]  # the preset's, then Control's own given back
    ids = [line.split('ID="')[1].split('"')[0] for line in sets]
    assert ids.index("CALIBRATE_CLEAR") < ids.index("CALIBRATE_ADDPOINT") < ids.index("CALIBRATE_START")
    added = control.commands("CALIBRATE_ADDPOINT")
    assert added == [f'<SET ID="CALIBRATE_ADDPOINT" X="{x}" Y="{y}" />' for x, y in app_layout(9)]


def test_the_hold_starts_no_later_than_delay_after_each_record_with_a_fake_clock():
    """A1 with a fake clock: whenever the window gets a point (``t0``), the icon is still and
    small by ``t0 + DELAY``, and was moving before."""
    for delay in (0.1, 0.8, 1.0, 1.8):
        motion = TargetMotion()
        t0 = 100.0
        for x, y in app_layout(5):
            motion.begin_point(x, y, t0, delay)
            assert motion.hold_start() <= t0 + delay
            assert motion.sample(t0 + delay).phase == PHASE_HOLD
            assert motion.sample(motion.hold_start()).size == 0.0
            assert motion.sample(t0 + delay).x == x and motion.sample(t0 + delay).y == y
            if delay >= 0.5:
                assert motion.sample(t0 + 0.1).phase == PHASE_GLIDE
            t0 += delay + 1.0  # the next record, after the hold


# -- A2: only CALIB_RESULT ends the run ------------------------------------------------------------


def test_an_extra_result_point_above_the_count_is_ignored_and_calib_result_ends_the_run(control):
    control.state.extra_result_pt = True  # PT 6 right after point 5, as probe P3 saw
    events = []
    run = run_calibration(
        control.client(), settings(), make_control=CapturingControl(None), on_event=events.append, timing=FAST
    )
    assert max(e.point for e in events) == 5  # PT 6 produced no event
    assert [e.kind for e in events].count(EVENT_PROCESSING) == 1
    assert run.outcome == "calib_result" and len(run.result.per_point) == 5  # the run ended on CALIB_RESULT


def test_the_result_comes_from_calib_result_alone_the_retained_summary_is_never_asked_for(control):
    """Feasibility 6.1: CALIBRATE_RESULT_SUMMARY is retained state. The score, the map and the
    badge's number come from CALIB_RESULT, whatever the summary holds."""
    control.state.ave_error, control.state.valid_points = "999.00", 0  # a previous run's retained summary
    client = control.client()
    geometry = settings_module.geometry_for_screen(1920, 1080, 527.0 / 1920, 1.0, 650.0)
    run = run_calibration(
        client, settings(), make_control=CapturingControl(None), timing=FAST, geometry=geometry
    )
    control.sync(client)
    assert control.commands("CALIBRATE_RESULT_SUMMARY") == []  # never asked
    result = run.result
    assert result.valid and len(result.per_point) == 5 and all("score" in p for p in result.per_point)
    # The fake's gaze is (0.003, 0.002) of the screen off at every point, on both eyes.
    assert result.mean_error_px == pytest.approx(math.hypot(0.003 * 1920, 0.002 * 1080), abs=0.01)
    assert result.mean_error_px != pytest.approx(999.0)


def test_without_a_valid_eye_the_result_is_not_valid_and_still_has_its_points(control):
    control.state.valid_eyes = False  # no camera: every eye invalid and zero
    geometry = settings_module.geometry_for_screen(1920, 1080, 527.0 / 1920, 1.0, 650.0)
    run = run_calibration(
        control.client(), settings(), make_control=CapturingControl(None), timing=FAST, geometry=geometry
    )
    assert run.outcome == "calib_result" and not run.result.valid
    assert len(run.result.per_point) == 5 and run.result.mean_error_px is None
    assert {p["score"] for p in run.result.per_point} == {0}


def test_no_calib_result_means_no_result_and_no_fallback(control, monkeypatch):
    """The five points ran, CALIB_RESULT never came: there is nothing to keep (and the child has
    sat through the calibration, so Control's window is not run again)."""

    def points_then_quiet(state, send):
        for i, (x, y) in enumerate(state.points, 1):
            send(f'<CAL ID="CALIB_START_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')
            state.cancel.wait(state.delay + state.timeout)
            send(f'<CAL ID="CALIB_RESULT_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')

    monkeypatch.setattr(control.module, "run_calibration_records", points_then_quiet)
    capture = CapturingControl(CalibrationResult(5, None, False))
    run = run_calibration(
        control.client(), settings(), make_control=capture, timing=FAST, grace_s=0.3, result_wait_s=0.3
    )
    assert run.outcome == "calib_result_never" and run.mode == MODE_APP and capture.calls == []
    assert not run.result.valid and run.result.per_point is None and run.result.mean_error_px is None


# -- A3: the fallback to Control's window ----------------------------------------------------------


def test_no_record_within_delay_plus_a_grace_falls_back_to_controls_window(control, tmp_path):
    """4.2: a silent Control triggers the fallback: the run is stopped, an event closes the
    window, today's Control-window run is made, and the reason is logged."""
    control.state.silent_runs = 1
    log = tmp_path / "calibration_timing.jsonl"
    events = []
    client = control.client()
    run = run_calibration(
        client, settings(), make_control=control_factory(client, log), on_event=events.append,
        timing=FAST, grace_s=0.3, timing_log_path=log,
    )
    control.sync(client)
    assert run.mode == MODE_FALLBACK and run.fallback_reason == "no CALIB_START_PT after CALIBRATE_START"
    assert [e.kind for e in events] == [EVENT_FALLBACK] and events[0].reason == run.fallback_reason
    assert run.result.valid and run.result.per_point  # Control's own window produced the result
    starts = control.commands("CALIBRATE_START")
    assert starts[:2] == ['<SET ID="CALIBRATE_START" STATE="1" />', '<SET ID="CALIBRATE_START" STATE="0" />']
    shows = control.commands("CALIBRATE_SHOW")
    assert shows[0].endswith('STATE="0" />') and shows[-1].endswith('STATE="1" />')  # then Control's window
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [(r["mode"], r["outcome"]) for r in records][0] == (MODE_APP, "fallback")
    assert records[0]["fallback_reason"] == run.fallback_reason
    assert records[-1]["mode"] == MODE_FALLBACK and records[-1]["fallback_reason"] == run.fallback_reason
    assert "Gazepoint Control's own calibration was used" in FALLBACK_ALERT


def test_a_late_point_also_falls_back(control, monkeypatch):
    """A point more than DELAY + TIMEOUT + grace after the one before is late (4.2)."""

    def two_points_then_quiet(state, send):
        for i, (x, y) in enumerate(state.points[:2], 1):
            send(f'<CAL ID="CALIB_START_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')
            state.cancel.wait(state.delay + state.timeout)
            send(f'<CAL ID="CALIB_RESULT_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')

    monkeypatch.setattr(control.module, "run_calibration_records", two_points_then_quiet)
    capture = CapturingControl(CalibrationResult(5, None, False))
    events = []
    run = run_calibration(
        control.client(), settings(), make_control=capture, on_event=events.append, timing=FAST, grace_s=0.3,
    )
    assert run.mode == MODE_FALLBACK and run.fallback_reason == "CALIB_START_PT 3 was late"
    assert capture.calls[0]["mode"] == MODE_FALLBACK
    assert capture.calls[0]["timing_extra"] == {"mode": MODE_FALLBACK, "fallback_reason": run.fallback_reason}
    assert [e.kind for e in events].count(EVENT_START_POINT) == 2


# -- A4: Esc/X ---------------------------------------------------------------------------------------


def _cancel_at_once() -> threading.Event:
    event = threading.Event()
    event.set()
    return event


def test_cancel_stops_the_calibration_and_leaves_no_result(control):
    cancel = threading.Event()
    events = []

    def on_event(event):
        events.append(event)
        if event.kind == EVENT_START_POINT and event.point == 2:
            cancel.set()  # Esc during the second point

    client = control.client()
    run = run_calibration(
        client, settings(), make_control=CapturingControl(None), on_event=on_event, timing=FAST, cancel=cancel
    )
    control.sync(client)
    assert run.cancelled and run.outcome == "cancelled"
    assert not run.result.valid and run.result.per_point is None  # nothing to keep
    commands = control.state.commands
    stop = commands.index('<SET ID="CALIBRATE_START" STATE="0" />')
    assert commands[stop + 1] == '<SET ID="CALIBRATE_SHOW" STATE="0" />'
    assert max(e.point for e in events) == 2  # no third point after the cancel


# -- A10a: the speed pairs, read and restored --------------------------------------------------------


@pytest.mark.parametrize("speed", sorted(SPEEDS))
def test_each_speed_preset_sends_its_pair_on_the_app_screen_and_restores_controls_own(control, speed):
    cancel = threading.Event()

    def on_event(event):
        if event.kind == EVENT_START_POINT:
            cancel.set()

    client = control.client()
    run_calibration(
        client, settings(speed=speed), make_control=CapturingControl(None), on_event=on_event, cancel=cancel
    )
    control.sync(client)
    glide, hold = SPEEDS[speed]
    delays, timeouts = control.commands("CALIBRATE_DELAY"), control.commands("CALIBRATE_TIMEOUT")
    assert f'<SET ID="CALIBRATE_DELAY" VALUE="{glide}" />' in delays
    assert f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{hold}" />' in timeouts
    assert (control.state.delay, control.state.timeout) == (0.7, 1.3)  # Control's own, restored


def test_the_speed_presets_are_the_pairs_of_the_spec():
    assert SPEEDS == {"slow": Speed(1.0, 1.5), "normal": Speed(0.8, 1.0), "fast": Speed(1.8, 0.4)}


@pytest.mark.parametrize("speed", ["slow", "normal", "fast"])
def test_the_control_screen_gets_the_same_pair_and_gives_controls_own_back(control, speed, monkeypatch):
    """Speed stays active for Gazepoint Control's window too (4.3b): the pair reaches
    ``Calibration`` and Control's own DELAY and TIMEOUT are read before and restored after."""
    quick = {"slow": Speed(0.05, 0.05), "normal": Speed(0.06, 0.05), "fast": Speed(0.07, 0.05)}
    monkeypatch.setattr(settings_module, "SPEEDS", quick)
    client = control.client()
    run = run_calibration(client, settings(screen="control", speed=speed), make_control=control_factory(client))
    control.sync(client)
    assert run.mode == MODE_CONTROL and run.result.valid
    assert f'<SET ID="CALIBRATE_DELAY" VALUE="{quick[speed].glide_s}" />' in control.commands("CALIBRATE_DELAY")
    assert f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{quick[speed].hold_s}" />' in control.commands("CALIBRATE_TIMEOUT")
    assert control.commands("CALIBRATE_SHOW")[-1].endswith('STATE="1" />')  # Control's own window
    assert (control.state.delay, control.state.timeout) == (0.7, 1.3)
    assert run.result.record["mode"] == MODE_CONTROL and run.result.record["speed"] == speed


def test_controls_timing_is_read_and_restored_by_the_helpers(control):
    client = control.client()
    saved = read_device_timing(client._sock)
    assert tuple(saved) == (0.7, 1.3)
    control.state.delay, control.state.timeout = 9.0, 9.0
    restore_device_timing(client._sock, saved)
    assert read_device_timing(client._sock).delay_s == 0.7
    assert read_device_timing(None) is None
    restore_device_timing(None, saved)  # no socket: nothing, no error


def test_a_run_without_a_socket_is_the_stub_and_draws_nothing():
    events = []
    capture = CapturingControl(CalibrationResult(5, None, False))
    run = run_calibration(None, settings(), make_control=capture, on_event=events.append)
    assert events == [] and not run.result.valid and run.result.per_point is None
    assert capture.calls[0]["point_delay_s"] == SPEEDS["normal"].glide_s
