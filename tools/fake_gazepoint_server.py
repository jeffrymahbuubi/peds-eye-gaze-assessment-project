"""Minimal fake OpenGaze TCP server for testing against a live socket
connection without a real GP3HD attached.

Accepts a connection the same way Gazepoint Control does, and answers
``CALIBRATE_RESULT_SUMMARY`` queries with a fixed, immediately-valid result
-- enough for ``Calibration.run()`` to complete and for ``AssessmentApp`` to
auto-save ``calibration.json`` (SPEC-2026-09-02.md item 7, Goal 1). It also
runs a calibration the way Control does (SPEC-app-drawn-calibration.md):
``CALIBRATE_START`` sends ``CALIB_START_PT`` / ``CALIB_RESULT_PT`` for every point,
each lasting DELAY + TIMEOUT (+ ``CAL_JITTER_S``), then ``CALIB_RESULT``; it honours
``CALIBRATE_SHOW`` / ``CLEAR`` / ``RESET`` / ``ADDPOINT`` and answers GET / SET of
``CALIBRATE_DELAY`` and ``CALIBRATE_TIMEOUT``. A test drives it through ``CalibrationState``
(``silent_runs``, ``extra_result_pt``, ``valid_eyes``, ``eye_offset``). Once
``ENABLE_SEND_DATA`` is set, streams a ``REC`` at ``REC_RATE_HZ`` that steps
through ``WAYPOINTS`` (SPEC-ui-setup-task-selection.md S24.4's original
fixed-center point, extended for SPEC-result-logic.md's Results-tab demo
recording): it holds each waypoint for ``FIXATION_HOLD_S``, incrementing
``FPOGID``/resetting ``FPOGD`` on every waypoint change, so a downstream
task sees a real dwell-then-saccade gaze pattern -- enough to exercise hit/
miss scoring and the fixation/saccade aggregation in
``compute_fixation_saccade_metrics`` (real fixation clustering, real
saccade count), not just a live sample-rate number. Still not a real
recorded gaze trace (no noise/smooth pursuit/blinks; APOG, sent once
``ENABLE_SEND_POG_AAC`` is set, is the moving average of FPOG over the
``AAC_FILTER`` window, which the server also ACKs for GET and SET) -- use ``--replay``
with ``tools/make_replay_fixture.py`` output for that instead, though note
that path only wires into the old standalone ``--gui`` launch today, not
the ``DashboardWindow``'s embedded task-run flow.

Usage::

    python tools/fake_gazepoint_server.py [port]   # default 4242

Then point ``configs/default.yaml``'s ``gazepoint.host`` at ``127.0.0.1``
(it has ``git update-index --skip-worktree`` set, so this is a free local
edit -- see README.md's "Editing a config file locally without it showing
up in git status" section) and run the app *without* ``--replay``, e.g.::

    python -m src.main --task click_static --gui --subject DEMO01

The eyes drift slowly (X, Y, Z and tilt) and vanish for 3 s every 20 s, so the head-position
widget (Setup's Calibration card, the Start page) passes through green, orange, red and "No eyes
detected" without a subject; see ``head_pose``.

Ctrl+C to stop. Remember to point ``gazepoint.host`` back at the real
device's address afterward.
"""

from __future__ import annotations

import contextlib
import math
import socket
import sys
import threading
import time
from collections import deque
from typing import NamedTuple

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4242
N_POINTS = 5
AVE_ERROR = "8.42"
REC_RATE_HZ = 20.0

# Waypoints the streamed REC steps through, one "fixation" at a time -- the
# 8 outer positions exactly match configs/tasks/click_static.yaml's own
# candidate positions (guaranteed hits there); the center additionally lines
# up with click_static's own [0.5, 0.5] fallback and sits close to
# click_grid's own middle cell. Order is simple sequential cycling, not
# randomized, so a recording is reproducible run to run.
WAYPOINTS: list[tuple[float, float]] = [
    (0.15, 0.15), (0.50, 0.15), (0.85, 0.15),
    (0.15, 0.50), (0.50, 0.50), (0.85, 0.50),
    (0.15, 0.85), (0.50, 0.85), (0.85, 0.85),
]
FIXATION_HOLD_S = 1.8  # comfortably above dwell.threshold_ms's 800ms default
AAC_FILTER_DEFAULT = 15  # the device's own APOG window, in samples (API manual 3.22)
AAC_FILTER_MAX = 60

# Canned replies for the connect-time device-info GET queries
# (SPEC-ui-setup-task-selection.md S23). Deliberately reproduces the real
# GP3HD audit's exact reported values (S24) -- NONE/0 placeholders and a
# sub-150 rate -- so this fake server doubles as a QA fixture for S24.1's
# placeholder filter and S24.3's rate-warning banner, not just the happy
# path. Keyed by GET ID.
DEVICE_INFO_REPLIES = {
    "PRODUCT_ID": '<ACK ID="PRODUCT_ID" VALUE="NONE" BUS="USB2" RATE="60" />\r\n',
    "SERIAL_ID": '<ACK ID="SERIAL_ID" VALUE="0" />\r\n',
    "CAMERA_SIZE": '<ACK ID="CAMERA_SIZE" WIDTH="752" HEIGHT="480" />\r\n',
    "API_ID": '<ACK ID="API_ID" VALUE="2.8" />\r\n',
    # A plausible single-monitor tracked-screen region (SPEC-gui-audit-
    # 2026-09-10.md item 5) -- lets QA exercise BaseTask.set_gaze_geometry's
    # real wiring (app.py -> DeviceInfo -> task) end-to-end even though this
    # fake server's REC stream is already canvas-normalized (see WAYPOINTS),
    # not screen-normalized -- the fake server proves the plumbing, not the
    # undershoot math itself (that's covered by tests/test_task_pipeline.py's
    # direct unit tests instead).
    "SCREEN_SIZE": '<ACK ID="SCREEN_SIZE" X="0" Y="0" WIDTH="1920" HEIGHT="1080" />\r\n',
    # all_gaze.csv's TIMETICK(f=..) header (SPEC-gazepoint-analysis-export-
    # parity.md S5.1); the real GP3 HD reports 1e9 (OpenCV tick counter).
    "TIME_TICK_FREQUENCY": '<ACK ID="TIME_TICK_FREQUENCY" FREQ="1000000000" />\r\n',
}


# -- calibration (SPEC-app-drawn-calibration.md): what Control does on CALIBRATE_START ---------
CAL_DEFAULT_DELAY = 0.5  # the device's own CALIBRATE_DELAY / CALIBRATE_TIMEOUT
CAL_DEFAULT_TIMEOUT = 1.5
CAL_DEFAULT_POINTS = [(0.5, 0.5), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85), (0.15, 0.15)]
CAL_JITTER_S = 0.02  # probe P3: a point runs 10-70 ms longer than DELAY + TIMEOUT
CAL_EYE_OFFSET = (0.003, 0.002)  # the fake gaze's error at each point (left eye; right mirrored)
CAL_SCREEN_PX = (1920, 1080)
CAL_COMMANDS = {
    "CALIBRATE_SHOW", "CALIBRATE_DELAY", "CALIBRATE_TIMEOUT", "CALIBRATE_CLEAR",
    "CALIBRATE_RESET", "CALIBRATE_ADDPOINT", "CALIBRATE_START",
}


class CalibrationState:
    """The calibration side of one fake connection: Control's settings, the point list, what
    the connection received, and the knobs a test turns."""

    def __init__(self) -> None:
        self.delay = CAL_DEFAULT_DELAY
        self.timeout = CAL_DEFAULT_TIMEOUT
        self.show = 1
        self.points = list(CAL_DEFAULT_POINTS)
        self.running = False
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None
        self.commands: list[str] = []  # every calibration command line received
        self.runs = 0
        self.ave_error = AVE_ERROR  # retained state until a run finishes
        self.valid_points = N_POINTS
        self.silent_runs = 0  # the next this-many runs send no CAL records (the app-drawn fallback)
        self.extra_result_pt = False  # an extra CALIB_RESULT_PT above the count (probe P3)
        self.valid_eyes = True  # False: no camera, every eye invalid and zero
        self.eye_offset = CAL_EYE_OFFSET


def _attr(line: str, name: str) -> str | None:
    marker = f'{name}="'
    return line.split(marker, 1)[1].split('"', 1)[0] if marker in line else None


def calibration_result_attrs(points: list[tuple[float, float]], state: CalibrationState) -> str:
    """The ``CALIB_RESULT`` attributes: each point's target and both eyes' gaze estimate (the
    target plus ``eye_offset``, left and right mirrored), or zeros and invalid flags with no
    camera."""
    parts = []
    dx, dy = state.eye_offset
    for i, (x, y) in enumerate(points, 1):
        parts.append(f'CALX{i}="{x:.5f}" CALY{i}="{y:.5f}"')
        if state.valid_eyes:
            parts.append(
                f'LX{i}="{x - dx:.5f}" LY{i}="{y + dy:.5f}" LV{i}="1" '
                f'RX{i}="{x + dx:.5f}" RY{i}="{y - dy:.5f}" RV{i}="1"'
            )
        else:
            parts.append(f'LX{i}="0.00000" LY{i}="0.00000" LV{i}="0" RX{i}="0.00000" RY{i}="0.00000" RV{i}="0"')
    return " ".join(parts)


def run_calibration_records(state: CalibrationState, send) -> None:
    """The records of one calibration, each point lasting DELAY + TIMEOUT (+ jitter); a
    ``CALIBRATE_START STATE="0"`` (``state.cancel``) ends it with no ``CALIB_RESULT``."""
    points = list(state.points)
    state.runs += 1
    try:
        if state.silent_runs > 0:
            state.silent_runs -= 1
            return
        for i, (x, y) in enumerate(points, 1):
            send(f'<CAL ID="CALIB_START_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')
            if state.cancel.wait(state.delay + state.timeout + CAL_JITTER_S):
                return
            send(f'<CAL ID="CALIB_RESULT_PT" PT="{i}" CALX="{x:.5f}" CALY="{y:.5f}" />\r\n')
        if state.extra_result_pt and points:
            last_x, last_y = points[-1]
            send(f'<CAL ID="CALIB_RESULT_PT" PT="{len(points) + 1}" CALX="{last_x:.5f}" CALY="{last_y:.5f}" />\r\n')
        if state.valid_eyes and points:
            px = math.hypot(state.eye_offset[0] * CAL_SCREEN_PX[0], state.eye_offset[1] * CAL_SCREEN_PX[1])
            state.ave_error, state.valid_points = f"{px:.2f}", len(points)
        else:
            state.ave_error, state.valid_points = "1510.04", 0
        state.commands.append("<sent CALIB_RESULT>")  # so a test can order it against the queries
        send(f'<CAL ID="CALIB_RESULT" {calibration_result_attrs(points, state)} />\r\n')
    finally:
        state.running = False


def handle_calibration_command(line: str, state: CalibrationState, send) -> bool:
    """Answer the calibration commands in ``line``; True when it was one. ``send(text)`` writes
    to the client."""
    if "<GET" not in line and "<SET" not in line:
        return False
    command = _attr(line, "ID")
    if command not in CAL_COMMANDS:
        return False
    state.commands.append(line)
    is_set = "<SET" in line
    value = _attr(line, "VALUE")
    if command == "CALIBRATE_SHOW":
        if is_set and _attr(line, "STATE") is not None:
            state.show = int(_attr(line, "STATE"))
        reply = f'<ACK ID="CALIBRATE_SHOW" STATE="{state.show}" />'
    elif command in ("CALIBRATE_DELAY", "CALIBRATE_TIMEOUT"):
        name = "delay" if command == "CALIBRATE_DELAY" else "timeout"
        if is_set and value is not None:
            try:
                wanted = float(value)
            except ValueError:
                wanted = -1.0
            if wanted > 0 or (name == "delay" and wanted >= 0):  # TIMEOUT > 0, DELAY >= 0 (API 3.5, 3.6)
                setattr(state, name, wanted)
        shown = value if is_set and value is not None else f"{getattr(state, name):g}"
        reply = f'<ACK ID="{command}" VALUE="{shown}" />'
    elif command in ("CALIBRATE_CLEAR", "CALIBRATE_RESET", "CALIBRATE_ADDPOINT"):
        if is_set and command == "CALIBRATE_CLEAR":
            state.points = []
        elif is_set and command == "CALIBRATE_RESET":
            state.points = list(CAL_DEFAULT_POINTS)
        elif is_set and _attr(line, "X") is not None and _attr(line, "Y") is not None:
            state.points.append((float(_attr(line, "X")), float(_attr(line, "Y"))))
        reply = f'<ACK ID="{command}" PTS="{len(state.points)}" />'
    else:  # CALIBRATE_START
        wanted = _attr(line, "STATE")
        if is_set and wanted == "1" and not state.running:
            state.running = True
            state.cancel.clear()
            state.thread = threading.Thread(target=run_calibration_records, args=(state, send), daemon=True)
            state.thread.start()
        elif is_set and wanted == "0":
            state.cancel.set()
            state.running = False
        reply = f'<ACK ID="CALIBRATE_START" STATE="{1 if state.running else 0}" />'
    send(reply + "\r\n")
    return True


class HeadPose(NamedTuple):
    """Where the fake child's eyes are: ``(x, y, z)`` in metres from the camera focal point,
    and whether the tracker sees them (``LPUPILV`` / ``RPUPILV``)."""

    left: tuple[float, float, float]
    right: tuple[float, float, float]
    eyes_valid: bool


# A head that never moves: eyes at +-0.03 m on X and 0.65 m from the camera.
STILL_HEAD = HeadPose((-0.03, 0.01, 0.65), (0.03, 0.01, 0.65), True)

# The slow head drift of SPEC-gaze-stability-and-positioning.md 4.5, so the head-position widget
# can be tried without the device: X, Y and Z (and the head's tilt) swing on their own periods and
# pass through the widget's green, orange and red bands; every HEAD_GAP_PERIOD_S the tracker loses
# the eyes for HEAD_GAP_S (the pupil valid flags go to 0 and the positions to zeros, as a real
# device sends them). It starts at HEAD_CENTRE_M and 0.65 m, so the first seconds are green.
# HEAD_CENTRE_M is the eye midpoint's (X, Y) of a well-seated head: keep it equal to the widget's
# CENTRED_X_CM / CENTRED_Y_CM (src/inputs/head_position.py), which the live check sets.
HEAD_CENTRE_M = (0.0, 0.0)
HEAD_X_SWING_M, HEAD_X_PERIOD_S = 0.15, 47.0
HEAD_Y_SWING_M, HEAD_Y_PERIOD_S = 0.09, 61.0
HEAD_Z_SWING_M, HEAD_Z_PERIOD_S = 0.17, 83.0
HEAD_TILT_SWING_M, HEAD_TILT_PERIOD_S = 0.008, 29.0  # each eye's Y moves this far, opposite ways
HEAD_GAP_PERIOD_S = 20.0
HEAD_GAP_S = 3.0


def head_pose(elapsed_s: float) -> HeadPose:
    """The drifting head ``elapsed_s`` seconds after the stream started."""
    if elapsed_s % HEAD_GAP_PERIOD_S >= HEAD_GAP_PERIOD_S - HEAD_GAP_S:
        return HeadPose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), False)

    def swing(amplitude: float, period_s: float) -> float:
        return amplitude * math.sin(2.0 * math.pi * elapsed_s / period_s)

    x = HEAD_CENTRE_M[0] + swing(HEAD_X_SWING_M, HEAD_X_PERIOD_S)
    y = HEAD_CENTRE_M[1] + swing(HEAD_Y_SWING_M, HEAD_Y_PERIOD_S)
    z = 0.65 + swing(HEAD_Z_SWING_M, HEAD_Z_PERIOD_S)
    tilt = swing(HEAD_TILT_SWING_M, HEAD_TILT_PERIOD_S)
    return HeadPose((x - 0.03, y - tilt, z), (x + 0.03, y + tilt, z), True)


def eye_geometry_attrs(
    x: float, y: float, enabled: set[str], head: HeadPose = STILL_HEAD
) -> str:
    """REC attributes for the ENABLE_SEND_EYE_* / ENABLE_SEND_POG_* records the
    client asked for (SPEC-gazepoint-analysis-export-parity.md S10.6.4):
    eyes where ``head`` puts them (by default still, +-0.03 m on X and 0.65 m
    from the camera), per-eye POG = the fixation point plus a small fixed
    offset."""
    valid = "1" if head.eyes_valid else "0"
    out = ""
    if "ENABLE_SEND_EYE_LEFT" in enabled:
        out += (
            f'LEYEX="{head.left[0]:.5f}" LEYEY="{head.left[1]:.5f}" LEYEZ="{head.left[2]:.5f}" '
            f'LPUPILD="0.00300" LPUPILV="{valid}" '
        )
    if "ENABLE_SEND_EYE_RIGHT" in enabled:
        out += (
            f'REYEX="{head.right[0]:.5f}" REYEY="{head.right[1]:.5f}" REYEZ="{head.right[2]:.5f}" '
            f'RPUPILD="0.00300" RPUPILV="{valid}" '
        )
    if "ENABLE_SEND_POG_LEFT" in enabled:
        out += f'LPOGX="{x - 0.005:.5f}" LPOGY="{y:.5f}" LPOGV="1" '
    if "ENABLE_SEND_POG_RIGHT" in enabled:
        out += f'RPOGX="{x + 0.005:.5f}" RPOGY="{y:.5f}" RPOGV="1" '
    return out


def aac_attrs(history: deque[tuple[float, float]], samples: int) -> str:
    """REC attributes of the ENABLE_SEND_POG_AAC record (SPEC-gaze-stability-and-positioning.md
    4.1): APOG is a moving-window average of FPOG over the last ``samples`` points of
    ``history`` (newest last), as the real device does; always valid here."""
    window = list(history)[-max(1, samples):]
    if not window:
        return 'APOGX="0.00000" APOGY="0.00000" APOGV="0" '
    x = sum(p[0] for p in window) / len(window)
    y = sum(p[1] for p in window) / len(window)
    return f'APOGX="{x:.5f}" APOGY="{y:.5f}" APOGV="1" '


def send_rec_loop(
    conn: socket.socket,
    stop_event: threading.Event,
    enabled: set[str] | None = None,
    aac_state: dict[str, int] | None = None,
    send_lock: threading.Lock | None = None,
) -> None:
    """Streams an always-valid REC at REC_RATE_HZ, stepping through
    WAYPOINTS one fixation at a time, until the connection drops or
    stop_event is set (SPEC S24.4 / result-logic S9 QA support).

    FPOGID increments (and FPOGD resets to 0) the instant the waypoint
    changes -- the same signal ``compute_fixation_saccade_metrics`` already
    uses to segment real device output into fixations/saccades, so this
    produces genuine (if synthetic) fixation/saccade counts rather than the
    single perpetual fixation a truly fixed point would give.

    ``enabled`` is the live set of ``ENABLE_SEND_*`` ids the client has
    switched on (shared with the connection handler, read per record).
    ``aac_state["samples"]`` is the AAC_FILTER window the client set (default 15).
    """
    enabled = enabled if enabled is not None else set()
    aac_state = aac_state if aac_state is not None else {"samples": AAC_FILTER_DEFAULT}
    history: deque[tuple[float, float]] = deque(maxlen=AAC_FILTER_MAX)
    t0 = time.monotonic()
    interval_s = 1.0 / REC_RATE_HZ
    waypoint_index = -1
    fixation_id = 0
    fixation_start = 0.0
    counter = 0
    while not stop_event.wait(interval_s):
        elapsed = time.monotonic() - t0
        current_index = int(elapsed // FIXATION_HOLD_S) % len(WAYPOINTS)
        if current_index != waypoint_index:
            waypoint_index = current_index
            fixation_id += 1
            fixation_start = elapsed
        x, y = WAYPOINTS[waypoint_index]
        history.append((x, y))
        fix_duration = elapsed - fixation_start
        # Every attribute all_gaze.csv records (SPEC-gazepoint-analysis-
        # export-parity.md S5), with plausible constants for the ones this
        # fake does not model, so the live all_gaze path is exercisable
        # without a subject. Biometrics-kit fields are deliberately absent.
        line = (
            f'<REC CNT="{counter}" TIME="{elapsed:.5f}" TIME_TICK="{time.monotonic_ns()}" '
            f'FPOGX="{x:.5f}" FPOGY="{y:.5f}" FPOGS="{fixation_start:.5f}" '
            f'FPOGD="{fix_duration:.5f}" FPOGID="{fixation_id}" FPOGV="1" '
            f'BPOGX="{x:.5f}" BPOGY="{y:.5f}" BPOGV="1" '
            f'CX="0.50000" CY="0.50000" CS="0" KB=" " KBS="0" USER="" '
            f'LPCX="0.53492" LPCY="0.41770" LPD="14.56116" LPS="1.20453" LPV="1" '
            f'RPCX="0.82296" RPCY="0.37728" RPD="19.28113" RPS="1.20453" RPV="1" '
            f'BKID="0" BKDUR="0.00000" BKPMIN="19" '
            f'LPMM="3.00000" LPMMV="1" RPMM="3.00000" RPMMV="1" '
            f'PIXS="0.00000" PIXV="0" '
            f'{eye_geometry_attrs(x, y, enabled, head_pose(elapsed))}'
            f'{aac_attrs(history, aac_state["samples"]) if "ENABLE_SEND_POG_AAC" in enabled else ""}'
            f'/>\r\n'
        )
        counter += 1
        try:
            with send_lock if send_lock is not None else contextlib.nullcontext():
                conn.sendall(line.encode("ascii"))
        except OSError:
            return


def handle_client(conn: socket.socket, cal: CalibrationState | None = None) -> None:
    conn.settimeout(0.2)
    buffer = ""
    cal = cal if cal is not None else CalibrationState()
    send_lock = threading.Lock()  # the REC thread, the calibration thread and this one share the socket

    def send(text: str) -> None:
        try:
            with send_lock:
                conn.sendall(text.encode("ascii"))
        except OSError:
            cal.cancel.set()

    stop_rec = threading.Event()
    enabled: set[str] = set()  # ENABLE_SEND_* ids the client switched on
    aac_state = {"samples": AAC_FILTER_DEFAULT}  # the AAC_FILTER window: SET changes it, GET reads it
    rec_thread: threading.Thread | None = None
    print("[fake-server] client connected", flush=True)
    try:
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                print("[fake-server] client disconnected", flush=True)
                break
            buffer += chunk.decode("ascii", errors="ignore")
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                print(f"[fake-server] recv: {line}", flush=True)
                if handle_calibration_command(line, cal, send):
                    continue
                if 'ID="CALIBRATE_RESULT_SUMMARY"' in line and "<GET" in line:
                    cal.commands.append(line)
                    ack = (
                        f'<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="{cal.ave_error}" '
                        f'VALID_POINTS="{cal.valid_points}" />\r\n'
                    )
                    send(ack)
                    print(f"[fake-server] sent: {ack.strip()}", flush=True)
                    continue
                if 'ID="AAC_FILTER"' in line:
                    if "<SET" in line and 'VALUE="' in line:
                        try:
                            wanted = int(line.split('VALUE="', 1)[1].split('"', 1)[0])
                            aac_state["samples"] = max(1, min(AAC_FILTER_MAX, wanted))
                        except ValueError:
                            pass
                    ack = f'<ACK ID="AAC_FILTER" VALUE="{aac_state["samples"]}" />\r\n'
                    send(ack)
                    print(f"[fake-server] sent: {ack.strip()}", flush=True)
                    continue
                if "<SET" in line and 'ID="ENABLE_SEND_' in line:
                    record_id = line.split('ID="', 1)[1].split('"', 1)[0]
                    if 'STATE="1"' in line:
                        enabled.add(record_id)
                    else:
                        enabled.discard(record_id)
                if 'ID="ENABLE_SEND_DATA"' in line and 'STATE="1"' in line and rec_thread is None:
                    rec_thread = threading.Thread(
                        target=send_rec_loop, args=(conn, stop_rec, enabled, aac_state, send_lock), daemon=True
                    )
                    rec_thread.start()
                    print(f"[fake-server] streaming REC at {REC_RATE_HZ:.0f} Hz", flush=True)
                    continue
                if "<GET" in line:
                    for query_id, reply in DEVICE_INFO_REPLIES.items():
                        if f'ID="{query_id}"' in line:
                            send(reply)
                            print(f"[fake-server] sent: {reply.strip()}", flush=True)
                            break
    finally:
        cal.cancel.set()  # a calibration still running ends with its connection
        stop_rec.set()
        if rec_thread is not None:
            rec_thread.join(timeout=1.0)


def main() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(1)
    # A blocking accept() with no timeout can't be interrupted by Ctrl+C on
    # Windows -- CPython only checks for a pending KeyboardInterrupt between
    # bytecode instructions, and a C-level blocking socket call doesn't
    # return control to the interpreter until it has something to report.
    # With nothing ever connecting, accept() would simply never return and
    # Ctrl+C would appear to do nothing. Polling with a short timeout (same
    # pattern already used for the per-client socket in handle_client)
    # gives the interpreter a chance to service the signal every 0.5s.
    listener.settimeout(0.5)
    print(f"[fake-server] listening on 127.0.0.1:{PORT} (Ctrl+C to stop)", flush=True)
    try:
        while True:
            try:
                conn, _addr = listener.accept()
            except TimeoutError:
                continue
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("[fake-server] stopping", flush=True)
    finally:
        listener.close()


if __name__ == "__main__":
    main()
