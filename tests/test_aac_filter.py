"""AAC_FILTER and the pointer columns of a run (SPEC-gaze-stability-and-positioning.md 4.1, 4.2,
4.4; acceptance A5, A6): the client reads the device's value on connect, sets the Assistive window
at a run start and gives the original back on stop; a gaze run records the cursor as drawn."""

# The fixtures are imported from input_run_fixtures and then used by name.
# ruff: noqa: F811
from __future__ import annotations

import csv
import json
import logging
import os
import time
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.data.schema import GazeSample
from src.inputs.gazepoint_client import GazepointClient
from src.inputs.mouse_gaze import MouseGazeSource
from src.ui.setup_page import SetupPage
from tests.input_run_fixtures import (  # noqa: F401  (fixtures)
    finish_run,
    make_app,
    parked,
    qapp,
    tick,
)
from tests.test_gazepoint_client import FakeGazepointServer


@pytest.fixture
def server():
    s = FakeGazepointServer()
    yield s
    s.close()


def wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def sets(server: FakeGazepointServer) -> list[str]:
    """The values of the AAC_FILTER SET commands the server has received, in order."""
    return [
        part.split('VALUE="', 1)[1].split('"', 1)[0]
        for part in server.received_text().split("<")
        if part.startswith("SET") and 'ID="AAC_FILTER"' in part
    ]


# -- the client (A5) -------------------------------------------------------------------------


def test_connect_reads_the_devices_filter_and_always_subscribes_to_apog(server):
    # Everything else switched off: the Assistive subscription is not a gazepoint.enable.* key.
    client = GazepointClient(enable={"pog_fix": False, "pog_best": False})
    client.connect(host="127.0.0.1", port=server.port)
    try:
        assert wait_until(lambda: "ENABLE_SEND_DATA" in server.received_text())
        assert 'ID="ENABLE_SEND_POG_AAC" STATE="1"' in server.received_text()
        assert 'GET ID="AAC_FILTER"' in server.received_text()
        assert client.device_info.aac_filter == 15
    finally:
        client.stop()


def test_a5_a_run_start_sets_the_window_and_stop_restores_the_original(server):
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=server.port)
    assert client.set_aac_filter(30) is True
    assert wait_until(lambda: sets(server) == ["30"])
    client.stop()  # a Disconnect, or the owner of the client closing
    assert wait_until(lambda: sets(server) == ["30", "15"])


def test_the_original_is_not_overwritten_by_a_second_set_and_is_restored_once(server):
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=server.port)
    client.set_aac_filter(30)
    client.set_aac_filter(45)  # a second run
    assert client.restore_aac_filter() is True
    assert client.restore_aac_filter() is False  # nothing left to give back
    client.stop()  # and stop() does not send it again
    assert wait_until(lambda: len(sets(server)) >= 3)
    time.sleep(0.2)
    assert sets(server) == ["30", "45", "15"]


def test_a_client_that_never_set_the_filter_never_touches_it(server):
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=server.port)
    assert client.restore_aac_filter() is False
    client.stop()
    time.sleep(0.2)
    assert sets(server) == []


def test_set_aac_filter_without_a_connection_is_not_sent():
    client = GazepointClient()
    assert client.set_aac_filter(30) is False
    assert client.restore_aac_filter() is False


def test_the_devices_ack_of_a_set_is_logged(server, caplog):
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=server.port)
    client.start_streaming()
    try:
        server.wait_for_connection()
        with caplog.at_level(logging.INFO, logger="src.inputs.gazepoint_client"):
            server._conn.sendall(b'<ACK ID="AAC_FILTER" VALUE="30" />\n')
            assert wait_until(lambda: "Gazepoint ACK AAC_FILTER VALUE=30" in caplog.text)
    finally:
        client.stop()


def test_the_reader_builds_each_sample_from_the_chosen_signal(server):
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=server.port)
    client.set_pointer_signal("assistive")
    client.start_streaming()
    try:
        server.wait_for_connection()
        server._conn.sendall(
            b'<REC BPOGX="0.1" BPOGY="0.2" BPOGV="1" FPOGX="0.3" FPOGY="0.4" FPOGV="1" '
            b'APOGX="0.5" APOGY="0.6" APOGV="1" />\n'
        )
        assert wait_until(lambda: client.latest() is not None)
        s = client.latest()
        assert (s.x, s.y) == (0.1, 0.2) and (s.pointer_x, s.pointer_y) == (0.5, 0.6)
    finally:
        client.stop()


def test_closing_the_window_gives_the_filter_back():
    calls: list[str] = []
    tracker = SimpleNamespace(restore_aac_filter=lambda: calls.append("restored"))
    SetupPage.release_tracker(SimpleNamespace(_client=tracker))
    SetupPage.release_tracker(SimpleNamespace(_client=None))  # no tracker connected: nothing to do
    assert calls == ["restored"]


# -- a run (A5, A6) ---------------------------------------------------------------------------


class SignalTracker(MouseGazeSource):
    """The default test tracker (the mouse) that also takes the gaze-signal commands."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[tuple] = []

    def set_pointer_signal(self, signal: str) -> None:
        self.calls.append(("signal", signal))

    def set_aac_filter(self, samples: int) -> bool:
        self.calls.append(("aac", samples))
        return True


def csv_rows(app) -> list[dict]:
    with (app.recorder.session_dir / "gaze_stream.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def session_log(app) -> str:
    return (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")


def metadata(app) -> dict:
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def test_a5_a_run_with_the_assistive_signal_sets_the_window_and_records_it(make_app):
    tracker = SignalTracker()
    app = make_app(trials=1, client=tracker, live={"dwell.pointer_signal": "assistive",
                                                   "dwell.aac_filter_samples": 25})
    assert tracker.calls == [("signal", "assistive"), ("aac", 25)]
    log = session_log(app)
    assert "Gaze signal: Assistive (APOG)." in log and "AAC filter set to 25 samples." in log
    app.recorder.write_metadata()
    live = metadata(app)["settings"]["live"]
    assert (live["dwell.pointer_signal"], live["dwell.aac_filter_samples"]) == ("assistive", 25)


@pytest.mark.parametrize("signal", ["best", "fixation"])
def test_a_run_with_another_signal_never_sends_the_filter_and_records_null(make_app, signal):
    tracker = SignalTracker()
    app = make_app(trials=1, client=tracker, live={"dwell.pointer_signal": signal})
    assert tracker.calls == [("signal", signal)]
    assert "AAC filter" not in session_log(app)
    app.recorder.write_metadata()
    live = metadata(app)["settings"]["live"]
    assert live["dwell.pointer_signal"] == signal and live["dwell.aac_filter_samples"] is None


def test_a_mouse_test_does_not_touch_the_trackers_signal(make_app):
    tracker = SignalTracker()
    make_app(trials=1, client=tracker, choice={"pointer": "mouse", "selection": "dwell"},
             live={"dwell.pointer_signal": "assistive"})
    assert tracker.calls == []


def test_a6_a_gaze_run_records_the_cursor_as_drawn_after_the_raw_columns(make_app):
    app = make_app(trials=1)
    finish_run(app)
    header = (app.recorder.session_dir / "gaze_stream.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.endswith(",pupil_left,pupil_right,pointer_x,pointer_y,pointer_valid")
    rows = csv_rows(app)
    assert rows and all(r["pointer_x"] != "" and r["pointer_valid"] in ("0", "1") for r in rows)
    valid = [r for r in rows if r["pointer_valid"] == "1"]
    assert valid
    # The cursor is canvas-normalized (the mouse source is canvas-normalized already, on a canvas
    # that fills the tracked screen here), so it sits where the raw gaze does: on the target.
    assert all(abs(float(r["pointer_x"]) - float(r["x"])) < 0.05 for r in valid if r["valid"] == "1")


def test_a_mouse_run_leaves_the_pointer_columns_of_the_tracker_alongside_blank(make_app):
    app = make_app(trials=1, choice={"pointer": "mouse", "selection": "dwell"})
    finish_run(app)
    rows = csv_rows(app)
    assert rows and all((r["pointer_x"], r["pointer_y"], r["pointer_valid"]) == ("", "", "") for r in rows)


def test_the_sample_row_has_blank_pointer_columns_when_it_has_no_cursor_signal():
    row = GazeSample(t_ns=1, x=0.5, y=0.5, valid=True).as_row()
    assert (row["pointer_x"], row["pointer_y"], row["pointer_valid"]) == ("", "", "")
    row = GazeSample(1, 0.5, 0.5, True, pointer_x=0.123456789, pointer_y=0.2, pointer_valid=False).as_row()
    assert (row["pointer_x"], row["pointer_y"], row["pointer_valid"]) == (0.12346, 0.2, 0)
