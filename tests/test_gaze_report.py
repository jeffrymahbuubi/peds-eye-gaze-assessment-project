"""The report and the fake tracker for the cursor signal (SPEC-gaze-stability-and-positioning.md
4.4, A6, A7): the Detailed view draws the recorded cursor path when the folder has it and replays
the running average otherwise; the Test Configuration shows the signal and the filter; the fake
Gazepoint server speaks APOG and AAC_FILTER."""

from __future__ import annotations

import csv
import importlib.util
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path

import pytest

from src.data.report_cache import build_report
from src.data.report_config import build_config_rows
from src.data.report_eye import load_cursor_frames
from src.data.report_geometry import Geometry
from src.data.report_util import NOT_RECORDED
from tests.report_fixtures import RIG_META, SEC, T0, frames_between, record, write_session

HEADER = [
    "t_ns", "x", "y", "valid", "fixation_id", "fix_duration_s", "pupil_left", "pupil_right",
    "pointer_x", "pointer_y", "pointer_valid",
]


def write_stream(path: Path, frames, cursor) -> None:
    """A gaze_stream.csv with the pointer columns: ``cursor(frame)`` is ``(x, y, valid)`` in
    canvas coordinates, or ``None`` for blank columns."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for f in frames:
            c = cursor(f)
            w.writerow([f.t_ns, f.x, f.y, int(f.valid), f.fid, f.dur_s, "", ""]
                       + (["", "", ""] if c is None else [c[0], c[1], int(c[2])]))


def folder(tmp_path, cursor=None):
    meta = dict(RIG_META, planned_trials=1, completed_trials=1, outcome="completed")
    # The raw gaze rests at canvas (0.4, 0.4) for the whole trial.
    frames = frames_between(T0, T0 + 3 * SEC, canvas_xy=(0.4, 0.4))
    out = write_session(tmp_path / "run", [record(0, T0 + 1 * SEC, "hit", dur_s=1.0)],
                        meta=meta, frames=None if cursor else frames)
    if cursor is not None:
        write_stream(out / "gaze_stream.csv", frames, cursor)
    return out


def path_points(report):
    return [p for line in report["trials"][0]["path"] for p in line]


# -- A7: the path ----------------------------------------------------------------------------


def test_a7_the_detailed_view_draws_the_recorded_cursor_not_the_replay(tmp_path):
    out = folder(tmp_path, cursor=lambda f: (0.6, 0.6, True))
    report = build_report(out)
    points = path_points(report)
    assert points and all(p == pytest.approx([0.6, 0.6], abs=1e-3) for p in points)
    # Nothing is replayed over a path that was already filtered when it was drawn.
    assert report["params"]["path"]["smoothing"]["enabled"] is False


def test_a7_an_older_session_keeps_the_replay_over_the_raw_gaze(tmp_path):
    out = folder(tmp_path)  # the 8-column gaze_stream.csv of every session before this feature
    report = build_report(out)
    points = path_points(report)
    assert points and all(p == pytest.approx([0.4, 0.4], abs=1e-3) for p in points)
    assert report["params"]["path"]["smoothing"]["enabled"] is True


def test_a7_blank_pointer_columns_fall_back_to_the_replay(tmp_path):
    report = build_report(folder(tmp_path, cursor=lambda f: None))  # e.g. a Mouse run's tracker file
    assert all(p == pytest.approx([0.4, 0.4], abs=1e-3) for p in path_points(report))
    assert report["params"]["path"]["smoothing"]["enabled"] is True


def test_a7_frames_where_the_cursor_was_frozen_are_not_drawn(tmp_path):
    # The cursor was driven for the second half only; before it, frozen far away (invalid).
    out = folder(tmp_path, cursor=lambda f: (0.6, 0.6, True) if f.t_ns >= T0 + 3 * SEC // 2
                 else (0.9, 0.9, False))
    points = path_points(build_report(out))
    assert points and all(p == pytest.approx([0.6, 0.6], abs=1e-3) for p in points)


def test_the_cursor_loader_converts_canvas_to_monitor_and_skips_blank_rows(tmp_path):
    out = folder(tmp_path, cursor=lambda f: None if f.t_ns % 2 else (0.5, 0.5, True))
    geometry = Geometry.from_metadata(RIG_META)
    frames = load_cursor_frames(out, geometry)
    assert frames and all(f.valid for f in frames)
    expected = geometry.canvas_to_monitor_norm(0.5, 0.5)
    assert all((f.x, f.y) == pytest.approx(expected) for f in frames)
    assert load_cursor_frames(tmp_path / "missing", geometry) == []


# -- the Test Configuration rows --------------------------------------------------------------


def rows(live, meta=RIG_META):
    settings = {**meta["settings"], "live": {**meta["settings"]["live"], **live}}
    return dict(build_config_rows(settings, meta, geometry=Geometry.from_metadata(meta)))


def test_the_rows_name_the_gaze_signal_and_the_filter():
    assert rows({"dwell.pointer_signal": "best"})["Gaze signal"] == "App smoothing (raw gaze)"
    assert rows({"dwell.pointer_signal": "assistive", "dwell.aac_filter_samples": 25})[
        "Gaze signal"
    ] == "Gazepoint Assistive (APOG), AAC filter 25 samples"
    # The default filter reads as before, with no mention of a type.
    assert rows({})["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"
    assert rows({"dwell.smoothing.type": "ema"})["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"
    assert rows({
        "dwell.smoothing.type": "one_euro", "dwell.smoothing.min_cutoff_hz": 0.5,
        "dwell.smoothing.beta": 4.0,
    })["Gaze smoothing"] == "On, adaptive (One Euro), steadiness 0.5 Hz, responsiveness 4, jitter tolerance 40 px"
    assert rows({"dwell.smoothing.enabled": False, "dwell.smoothing.type": "one_euro"})[
        "Gaze smoothing"
    ] == "Off, jitter tolerance 40 px"


ASSISTIVE = {"dwell.pointer_signal": "assistive", "dwell.aac_filter_samples": 15}
NOT_SMOOTHED = dict(RIG_META, smoothing_applied=False)  # a run recorded under 4.9, App smoothing off


def test_a14_a_new_assistive_run_reports_the_app_smoothing_as_off_whatever_was_saved():
    got = rows({**ASSISTIVE, "dwell.smoothing.enabled": True, "dwell.smoothing.type": "ema"}, NOT_SMOOTHED)
    assert got["Gaze signal"] == "Gazepoint Assistive (APOG), AAC filter 15 samples"
    assert got["Gaze smoothing"] == "Off (Gazepoint Assistive), jitter tolerance 40 px"
    for extra in ({"dwell.smoothing.type": "one_euro"}, {"dwell.smoothing.enabled": False}):
        assert rows({**ASSISTIVE, **extra}, NOT_SMOOTHED)["Gaze smoothing"] == (
            "Off (Gazepoint Assistive), jitter tolerance 40 px"
        )
    # An Assistive run that did not record its window still says what it was.
    assert rows({"dwell.pointer_signal": "assistive"}, NOT_SMOOTHED)["Gaze signal"] == (
        "Gazepoint Assistive (APOG)"
    )


def test_a14_an_old_assistive_session_that_was_smoothed_describes_the_smoothing():
    """Before 4.9 an Assistive run could have the app's average on top (the live-check finding): with
    no `smoothing_applied` in the folder the report describes the recorded settings, never "Off"."""
    assert "smoothing_applied" not in RIG_META
    on = rows({**ASSISTIVE, "dwell.smoothing.enabled": True, "dwell.smoothing.type": "ema"})
    assert on["Gaze signal"] == "Gazepoint Assistive (APOG), AAC filter 15 samples"
    assert on["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"
    adaptive = rows({**ASSISTIVE, "dwell.smoothing.enabled": True, "dwell.smoothing.type": "one_euro",
                     "dwell.smoothing.min_cutoff_hz": 0.5, "dwell.smoothing.beta": 4.0})
    assert adaptive["Gaze smoothing"] == (
        "On, adaptive (One Euro), steadiness 0.5 Hz, responsiveness 4, jitter tolerance 40 px"
    )
    assert rows({**ASSISTIVE, "dwell.smoothing.enabled": False})["Gaze smoothing"] == (
        "Off, jitter tolerance 40 px"
    )


def test_a14_a_run_that_says_its_smoothing_was_applied_is_described_not_called_off():
    applied = dict(RIG_META, smoothing_applied=True)
    assert rows(ASSISTIVE, applied)["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"


def test_a14_the_field_changes_nothing_for_app_smoothing_runs():
    for meta in (RIG_META, dict(RIG_META, smoothing_applied=True), NOT_SMOOTHED):  # e.g. a Mouse run
        assert rows({"dwell.pointer_signal": "best"}, meta)["Gaze smoothing"] == (
            "On, alpha 0.22, jitter tolerance 40 px"
        )


def test_a14_an_app_smoothing_run_keeps_the_smoothing_row_as_it_was():
    assert rows({"dwell.pointer_signal": "best"})["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"


def test_a14_an_old_session_with_fixation_reads_as_what_it_was():
    got = rows({"dwell.pointer_signal": "fixation"})
    assert got["Gaze signal"] == "Fixation (FPOG), no longer offered"
    assert got["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"  # it was smoothed by the app
    assert rows({"dwell.pointer_signal": "fixation", "dwell.smoothing.enabled": False})[
        "Gaze smoothing"
    ] == "Off, jitter tolerance 40 px"


def test_an_older_session_says_the_signal_was_not_recorded():
    old = {"live": {k: v for k, v in RIG_META["settings"]["live"].items() if k != "dwell.pointer_signal"},
           "structural": RIG_META["settings"]["structural"]}
    assert dict(build_config_rows(old, RIG_META))["Gaze signal"] == NOT_RECORDED


# -- the fake tracker ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake():
    path = Path(__file__).resolve().parents[1] / "tools" / "fake_gazepoint_server.py"
    spec = importlib.util.spec_from_file_location("_fake_gp_server_aac", path)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["fake_gazepoint_server.py"]  # the module reads its port from argv
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


def test_apog_is_the_moving_average_of_the_last_window(fake):
    history = deque([(0.0, 0.0), (0.3, 0.6), (0.6, 0.9)])
    assert fake.aac_attrs(history, 3) == 'APOGX="0.30000" APOGY="0.50000" APOGV="1" '
    assert fake.aac_attrs(history, 2) == 'APOGX="0.45000" APOGY="0.75000" APOGV="1" '
    assert fake.aac_attrs(history, 99) == fake.aac_attrs(history, 3)
    assert fake.aac_attrs(deque(), 15) == 'APOGX="0.00000" APOGY="0.00000" APOGV="0" '


def read_lines(conn: socket.socket, want: int, timeout_s: float = 3.0) -> list[str]:
    conn.settimeout(0.2)
    buffer, deadline = "", time.monotonic() + timeout_s
    while buffer.count("\n") < want and time.monotonic() < deadline:
        try:
            buffer += conn.recv(4096).decode("ascii")
        except TimeoutError:
            pass
    return buffer.splitlines()


def test_the_fake_server_acks_aac_filter_get_and_set_and_streams_apog(fake):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    server = threading.Thread(target=lambda: fake.handle_client(listener.accept()[0]), daemon=True)
    server.start()
    with socket.create_connection(listener.getsockname(), timeout=2.0) as conn:
        conn.sendall(b'<GET ID="AAC_FILTER" />\r\n')
        assert read_lines(conn, 1) == ['<ACK ID="AAC_FILTER" VALUE="15" />']
        conn.sendall(b'<SET ID="AAC_FILTER" VALUE="30" />\r\n')
        assert read_lines(conn, 1) == ['<ACK ID="AAC_FILTER" VALUE="30" />']
        conn.sendall(b'<SET ID="AAC_FILTER" VALUE="500" />\r\n')
        assert read_lines(conn, 1) == ['<ACK ID="AAC_FILTER" VALUE="60" />']  # the device's range
        conn.sendall(b'<SET ID="ENABLE_SEND_POG_AAC" STATE="1" />\r\n')
        conn.sendall(b'<SET ID="ENABLE_SEND_DATA" STATE="1" />\r\n')
        rec = read_lines(conn, 1)[0]
        assert rec.startswith("<REC ") and 'APOGX="' in rec and 'APOGV="1"' in rec
    listener.close()
