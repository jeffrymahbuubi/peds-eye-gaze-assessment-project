"""SPEC-audit-fixes.md H2 (F1, the client layer), H6 (F3, the client forgets a sample once
the link is gone) and H9 (F7, the reader stamps on the in-run clock).

A socketpair stands in for Gazepoint Control: the client reads one end, the test writes the
other. The client's reconnect interval is an hour, so a dropped link never dials anything.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from src.engine.clock import now_ns
from src.inputs import gazepoint_client as gc
from src.inputs.gazepoint_client import GazepointClient

REC = b'<REC FPOGX="0.5" FPOGY="0.5" FPOGV="1" BPOGX="0.5" BPOGY="0.5" BPOGV="1" />\r\n'
CALIB_RESULT = b'<CAL ID="CALIB_RESULT" CALX1="0.5" CALY1="0.5" />\r\n'


# Reader threads some earlier test left running (a daemon cannot be killed): not this test's.
_STRAYS: set[threading.Thread] = set()


def all_readers() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "gazepoint-reader" and t.is_alive()]


def readers() -> list[threading.Thread]:
    return [t for t in all_readers() if t not in _STRAYS]


def wait_until(predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def rig():
    _STRAYS.clear()
    _STRAYS.update(all_readers())
    ours, theirs = socket.socketpair()
    ours.settimeout(0.2)  # the reader's recv() wakes up quickly, as the real socket's does
    client = GazepointClient(reconnect_interval_s=3600.0)
    client._sock = ours
    client._connected = True
    yield client, theirs
    client.stop()
    theirs.close()
    assert wait_until(lambda: not readers())


# -- H2: the pause counter ---------------------------------------------------------------------


def test_start_streaming_inside_a_pause_never_starts_a_second_reader(rig):
    """The audit's repro: AssessmentApp.__init__ calls start_streaming() while a calibration
    holds the reader paused and polls the socket itself."""
    client, theirs = rig
    client.start_streaming()
    assert len(readers()) == 1
    with client.streaming_paused() as was_running:
        assert was_running is True
        assert readers() == [] and not client.is_streaming()
        client.start_streaming()  # recorded, not done
        assert readers() == [] and not client.is_streaming()
        theirs.sendall(CALIB_RESULT)
        assert b"CALIB_RESULT" in client._sock.recv(4096)  # the poller gets it, no reader eats it
    assert len(readers()) == 1 and client.is_streaming()
    assert not client._stop_event.is_set()
    theirs.sendall(REC)  # and the one reader delivers
    assert wait_until(lambda: client.latest() is not None)


def test_a_nested_pause_returns_paused_and_only_the_outermost_end_resumes(rig):
    client, _theirs = rig
    client.start_streaming()
    with client.streaming_paused() as outer:
        with client.streaming_paused() as inner:
            assert outer is True and inner is True
            assert readers() == []
        assert readers() == []  # the inner end must not restart the reader under the outer pause
    assert len(readers()) == 1


def test_a_pause_of_a_stopped_client_starts_a_reader_only_if_one_was_asked_for(rig):
    client, _theirs = rig
    with client.streaming_paused() as was_running:
        assert was_running is False
    assert readers() == []  # nobody asked: a non-streaming client stays that way
    with client.streaming_paused() as was_running:
        assert was_running is False
        client.start_streaming()
        assert readers() == []
    assert len(readers()) == 1 and client.is_streaming()  # asked for during the pause: once


def test_stop_inside_a_pause_means_the_pause_end_restarts_nothing(rig):
    client, _theirs = rig
    client.start_streaming()
    with client.streaming_paused():
        client.stop()
    assert readers() == []


def test_a_nested_pause_waits_until_the_first_has_stopped_the_reader(rig, monkeypatch):
    """The first pause is still joining the reader; a second caller must not get the socket
    before the reader has let go of it."""
    client, _theirs = rig
    release = threading.Event()
    stuck = threading.Thread(target=release.wait, name="gazepoint-reader", daemon=True)
    stuck.start()
    monkeypatch.setattr(gc, "_PAUSE_JOIN_TIMEOUT_S", 10.0)
    client._thread = stuck
    first_result: list[bool] = []
    second_result: list[bool] = []
    first = threading.Thread(target=lambda: first_result.append(client.pause_streaming()))
    first.start()
    assert wait_until(client._pause_join_lock.locked)  # the first pause is in its join
    second = threading.Thread(target=lambda: second_result.append(client.pause_streaming()))
    second.start()
    time.sleep(0.3)
    assert second_result == []  # still waiting
    release.set()  # the "reader" ends
    first.join(timeout=3)
    second.join(timeout=3)
    assert first_result == [True] and second_result == [True]
    client.resume_streaming()
    client.resume_streaming()
    assert len(readers()) == 1  # restarted once, by the last end


def test_refresh_device_info_during_a_calibration_pause_does_not_restart_the_reader(rig):
    """The Re-check/calibration overlap of F5 at the client level: the inner pause is nested."""
    client, theirs = rig
    client.start_streaming()
    with client.streaming_paused():
        with client.streaming_paused() as inner:
            assert inner is True
        assert readers() == []
        theirs.sendall(CALIB_RESULT)
        assert b"CALIB_RESULT" in client._sock.recv(4096)


# -- H6: the client forgets the last sample once the link is gone --------------------------------


def test_a_disconnect_clears_the_stale_sample(rig):
    client, theirs = rig
    client.start_streaming()
    theirs.sendall(REC)
    assert wait_until(lambda: client.latest() is not None and client.last_raw_pog() is not None)
    theirs.close()
    assert wait_until(lambda: client.is_connected() is False)
    assert client.latest() is None and client.last_raw_pog() is None


def test_stop_clears_the_last_sample(rig):
    client, theirs = rig
    client.start_streaming()
    theirs.sendall(REC)
    assert wait_until(lambda: client.latest() is not None)
    client.stop()
    assert client.latest() is None and client.last_raw_pog() is None


# -- H9: the reader stamps on the in-run clock ----------------------------------------------------


def test_the_readers_stamp_is_the_in_run_clock_and_ignores_a_wall_clock_step(rig, monkeypatch):
    client, theirs = rig
    client.start_streaming()
    wall = time.time_ns()
    monkeypatch.setattr(time, "time_ns", lambda: wall + 10 * 3600 * 10**9)  # the clock jumps 10 h
    before = now_ns()
    theirs.sendall(REC)
    assert wait_until(lambda: client.latest() is not None)
    stamp = client.latest().t_ns
    assert before <= stamp <= now_ns()
    assert abs(stamp - wall) < 60 * 10**9  # still the epoch-ns domain, not 10 h on
