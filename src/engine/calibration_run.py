"""One calibration run, for either screen (SPEC-app-drawn-calibration.md 4.1-4.3b, 4.7).

:func:`run_calibration` is what the Setup thread calls. For the **App** screen it sends
``CALIBRATE_SHOW STATE="0"``, the speed's ``CALIBRATE_DELAY`` / ``CALIBRATE_TIMEOUT``, the Grid 3
point layout and ``CALIBRATE_START``, then reads Control's ``CAL`` records itself and hands each
one to ``on_event`` so the calibration window can draw the target. For the **Gazepoint Control**
screen it runs today's path (:class:`~src.engine.calibration.Calibration`) with the same speed.
Either way Control's own DELAY and TIMEOUT are read first and restored afterwards, so other
software on the PC keeps its settings (4.3b).

Records that matter (probes P1-P3, feasibility 6.1): a ``CALIB_RESULT_PT`` above the point count
is ignored; ``CALIB_RESULT`` is the only end marker and the only source of the result;
``CALIBRATE_RESULT_SUMMARY`` is retained state and is never asked for. If Control sends nothing when it should
(4.2) the run falls back to Control's own window; Esc/X (``cancel``) stops it with
``CALIBRATE_START STATE="0"``.

Qt-free and socket-level, like :mod:`src.engine.calibration`; the reader thread is paused around
all socket use for the same reason (SPEC-calibration-result-timeout.md S4.1).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from ..data.report_geometry import Geometry
from ..inputs.gazepoint_client import parse_attrs
from .calibration import (
    CalibrationResult,
    _append_timing_record,
    _drain_socket,
    _parse_calib_result,
)
from .calibration_motion import schedule
from .calibration_settings import (
    MODE_APP,
    MODE_CONTROL,
    MODE_FALLBACK,
    CalibrationSettings,
    annotate_result,
    app_layout,
)

EVENT_START_POINT = "start_point"
EVENT_RESULT_POINT = "result_point"
EVENT_PROCESSING = "processing"
EVENT_FALLBACK = "fallback"

FALLBACK_GRACE_S = 1.0  # 4.2: DELAY (+ TIMEOUT) plus this
RESULT_WAIT_S = 5.0  # how long CALIB_RESULT may take after the last point's DELAY + TIMEOUT
QUERY_WAIT_S = 1.0  # for the ACK of a GET of Control's DELAY / TIMEOUT
_RECV_TIMEOUT_S = 0.1

FALLBACK_ALERT = (
    "The app's calibration screen did not respond; Gazepoint Control's own calibration was used."
)


@dataclass(frozen=True)
class CalibrationEvent:
    """One thing the calibration window reacts to; ``t`` is the clock time the record was read."""

    kind: str
    point: int = 0
    x: float = 0.0  # CALX / CALY, fractions of the screen
    y: float = 0.0
    t: float = 0.0
    delay_s: float = 0.0
    n_points: int = 0
    reason: str = ""


@dataclass(frozen=True)
class CalibrationRun:
    """What one :func:`run_calibration` call came to."""

    result: CalibrationResult
    mode: str
    cancelled: bool = False
    fallback_reason: str | None = None
    outcome: str = ""  # the diagnostics word: calib_result, cancelled, fallback, ...
    layout: list[tuple[float, float]] = field(default_factory=list)  # where the app drew the points


class DeviceTiming(NamedTuple):
    """Control's own ``CALIBRATE_DELAY`` and ``CALIBRATE_TIMEOUT`` (None: it did not answer)."""

    delay_s: float | None
    timeout_s: float | None


def _socket_of(client: Any) -> Any:
    return getattr(client, "_sock", None) if client is not None else None


def _send(sock: Any, text: str) -> None:
    sock.sendall(f"{text}\r\n".encode("ascii"))


def _lines(sock: Any, buffer: list[str]) -> list[str]:
    """Complete lines read from ``sock`` in at most one receive; ``buffer`` holds the partial one
    (a one-item list, so the caller keeps it between calls). ``[]`` on a timeout; raises
    ``OSError`` when the socket is closed."""
    try:
        chunk = sock.recv(4096)
    except TimeoutError:
        return []
    if not chunk:
        raise OSError("socket closed")
    buffer[0] += chunk.decode("ascii", errors="ignore")
    out: list[str] = []
    while "\n" in buffer[0]:
        line, buffer[0] = buffer[0].split("\n", 1)
        out.append(line)
    return out


def _wait_for_ack(sock: Any, ack_id: str, wait_s: float, clock: Callable[[], float]) -> dict[str, str] | None:
    """The attributes of the first ``<ACK ID=ack_id>`` within ``wait_s``, else None. Everything
    else on the socket (REC lines, other ACKs) is read and dropped."""
    buffer = [""]
    deadline = clock() + wait_s
    while clock() < deadline:
        try:
            lines = _lines(sock, buffer)
        except OSError:
            return None
        for line in lines:
            parsed = parse_attrs(line)
            if parsed is not None and parsed[0] == "ACK" and parsed[1].get("ID", "").strip() == ack_id:
                return parsed[1]
    return None


def _query_float(sock: Any, ack_id: str, clock: Callable[[], float]) -> float | None:
    try:
        _send(sock, f'<GET ID="{ack_id}" />')
    except OSError:
        return None
    attrs = _wait_for_ack(sock, ack_id, QUERY_WAIT_S, clock)
    try:
        return float(attrs["VALUE"]) if attrs is not None else None
    except (KeyError, ValueError):
        return None


def read_device_timing(sock: Any, clock: Callable[[], float] = time.monotonic) -> DeviceTiming | None:
    """Control's current ``CALIBRATE_DELAY`` and ``CALIBRATE_TIMEOUT`` (4.3b), for
    :func:`restore_device_timing`; None without a socket or when neither was answered."""
    if sock is None:
        return None
    original = sock.gettimeout()
    sock.settimeout(_RECV_TIMEOUT_S)
    try:
        timing = DeviceTiming(
            _query_float(sock, "CALIBRATE_DELAY", clock), _query_float(sock, "CALIBRATE_TIMEOUT", clock)
        )
    finally:
        sock.settimeout(original)
    return timing if timing != (None, None) else None


def restore_device_timing(sock: Any, saved: DeviceTiming | None) -> None:
    """Give Control its own DELAY and TIMEOUT back; never raises (the socket may be gone)."""
    if sock is None or saved is None:
        return
    try:
        if saved.delay_s is not None:
            _send(sock, f'<SET ID="CALIBRATE_DELAY" VALUE="{saved.delay_s}" />')
        if saved.timeout_s is not None:
            _send(sock, f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{saved.timeout_s}" />')
    except OSError:
        pass


def _stop_on_socket(sock: Any) -> None:
    """Esc/x during a run (4.1): stop the calibration and put ``CALIBRATE_SHOW`` back to 0."""
    try:
        _send(sock, '<SET ID="CALIBRATE_START" STATE="0" />')
        _send(sock, '<SET ID="CALIBRATE_SHOW" STATE="0" />')
    except OSError:
        pass


def annotate(
    run: CalibrationRun, settings: CalibrationSettings, geometry: Geometry | None
) -> CalibrationRun:
    """``run`` with the settings record and each point's score and error added to its result
    (4.7). Without a geometry only the record is added."""
    return replace(run, result=annotate_result(run.result, settings, run.mode, geometry))


def _unmeasured(n_points: int) -> CalibrationResult:
    return CalibrationResult(n_points=n_points, mean_error_px=None, valid=False)


def run_calibration(
    client: Any,
    settings: CalibrationSettings,
    *,
    make_control: Callable[..., Any],
    on_event: Callable[[CalibrationEvent], None] | None = None,
    cancel: threading.Event | None = None,
    timing_log_path: str | Path | None = None,
    geometry: Geometry | None = None,
    timing: tuple[float, float] | None = None,
    clock: Callable[[], float] = time.monotonic,
    grace_s: float | None = None,
    result_wait_s: float | None = None,
) -> CalibrationRun:
    """Run one calibration with ``settings`` and return how it went.

    ``make_control(**kwargs)`` builds the object whose ``run()`` is today's Control-window
    calibration (``point_delay_s``, ``point_timeout_s``, ``mode``, ``timing_extra`` as keywords);
    the Setup page passes a factory around :class:`~src.engine.calibration.Calibration`.
    ``timing`` overrides the speed's ``(DELAY, TIMEOUT)`` and ``grace_s`` / ``result_wait_s`` the
    waits of 4.2 (tests). Needs the reader thread quiet: it is paused here, as
    :meth:`Calibration.run` does.
    """
    delay_s, timeout_s = timing if timing is not None else (settings.delay_s, settings.timeout_s)
    grace_s = FALLBACK_GRACE_S if grace_s is None else grace_s
    result_wait_s = RESULT_WAIT_S if result_wait_s is None else result_wait_s
    sock = _socket_of(client)

    def control(mode: str, extra: dict[str, Any] | None = None) -> CalibrationRun:
        runner = make_control(point_delay_s=delay_s, point_timeout_s=timeout_s, mode=mode, timing_extra=extra)
        return CalibrationRun(result=runner.run(), mode=mode, outcome="control")

    if sock is None or not settings.is_app:
        # Control's own window (today's path), or no hardware at all (the stub answers).
        paused = getattr(client, "streaming_paused", None) if sock is not None else None
        with paused() if paused is not None else nullcontext():
            saved = read_device_timing(_socket_of(client) or sock, clock)
            try:
                run = control(MODE_APP if settings.is_app and sock is None else MODE_CONTROL)
            finally:
                restore_device_timing(_socket_of(client) or sock, saved)
        return annotate(run, settings, geometry)

    paused = getattr(client, "streaming_paused", None)
    with paused() if paused is not None else nullcontext():
        sock = _socket_of(client) or sock
        saved = read_device_timing(sock, clock)
        try:
            run = _run_app(
                sock, settings, delay_s, timeout_s, control, on_event, cancel, timing_log_path,
                clock, grace_s, result_wait_s,
            )
        finally:
            restore_device_timing(sock, saved)
    return annotate(run, settings, geometry)


def _run_app(
    sock: Any,
    settings: CalibrationSettings,
    delay_s: float,
    timeout_s: float,
    control: Callable[..., CalibrationRun],
    on_event: Callable[[CalibrationEvent], None] | None,
    cancel: threading.Event | None,
    timing_log_path: str | Path | None,
    clock: Callable[[], float],
    grace_s: float,
    result_wait_s: float,
) -> CalibrationRun:
    layout = app_layout(settings.points)
    n = len(layout)
    emit = on_event if on_event is not None else (lambda _event: None)
    points: dict[int, dict[str, float]] = {}  # point -> start / result times (clock)
    log = _TimingLog(timing_log_path, settings, delay_s, timeout_s, points, clock)

    _drain_socket(sock)
    try:
        _send(sock, '<SET ID="CALIBRATE_SHOW" STATE="0" />')
        _send(sock, f'<SET ID="CALIBRATE_DELAY" VALUE="{delay_s}" />')
        _send(sock, f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{timeout_s}" />')
        _send(sock, '<SET ID="CALIBRATE_CLEAR" />')
        for x, y in layout:
            _send(sock, f'<SET ID="CALIBRATE_ADDPOINT" X="{x}" Y="{y}" />')
        _send(sock, '<SET ID="CALIBRATE_START" STATE="1" />')
    except OSError:
        log.write("socket_error")
        return CalibrationRun(_unmeasured(n), MODE_APP, outcome="socket_error", layout=layout)
    t_start = clock()
    log.t_start = t_start

    original = sock.gettimeout()
    sock.settimeout(_RECV_TIMEOUT_S)
    buffer = [""]
    started = 0
    deadline = t_start + delay_s + grace_s  # for the next CALIB_START_PT, then CALIB_RESULT
    per_point: list[dict[str, Any]] | None = None
    outcome = "calib_result"
    reason = ""
    try:
        while True:
            if cancel is not None and cancel.is_set():
                _stop_on_socket(sock)
                log.write("cancelled")
                return CalibrationRun(_unmeasured(n), MODE_APP, cancelled=True, outcome="cancelled", layout=layout)
            if clock() > deadline:
                if started < n:
                    reason = (
                        "no CALIB_START_PT after CALIBRATE_START" if started == 0
                        else f"CALIB_START_PT {started + 1} was late"
                    )
                    outcome = "fallback"
                else:
                    outcome = "calib_result_never"
                break
            try:
                lines = _lines(sock, buffer)
            except OSError:
                log.write("socket_error")
                return CalibrationRun(_unmeasured(n), MODE_APP, outcome="socket_error", layout=layout)
            for line in lines:
                parsed = parse_attrs(line)
                if parsed is None or parsed[0] != "CAL":
                    continue
                attrs = parsed[1]
                kind = attrs.get("ID", "").strip()
                if kind == "CALIB_RESULT":
                    per_point = _parse_calib_result(attrs)
                    break
                point = _point_number(attrs, n)
                if point is None:
                    continue  # no PT, or one above the point count (A2): ignored
                x, y = _position(attrs, layout, point)
                now = clock()
                if kind == "CALIB_START_PT":
                    started = max(started, point)
                    points.setdefault(point, {})["start"] = now
                    deadline = now + delay_s + timeout_s + (grace_s if started < n else result_wait_s)
                    emit(CalibrationEvent(EVENT_START_POINT, point, x, y, now, delay_s, n))
                elif kind == "CALIB_RESULT_PT":
                    points.setdefault(point, {})["result"] = now
                    emit(CalibrationEvent(EVENT_RESULT_POINT, point, x, y, now, delay_s, n))
                    if point == n:
                        emit(CalibrationEvent(EVENT_PROCESSING, point, x, y, now, delay_s, n))
            if per_point is not None:
                break
    finally:
        sock.settimeout(original)

    if outcome == "fallback":
        _stop_on_socket(sock)
        emit(CalibrationEvent(EVENT_FALLBACK, t=clock(), n_points=n, reason=reason))
        log.write("fallback", reason=reason)
        run = control(MODE_FALLBACK, {"mode": MODE_FALLBACK, "fallback_reason": reason})
        return replace(run, fallback_reason=reason, outcome="fallback")

    result = _result_from_calib_result(n, per_point)
    log.write(outcome, result=result)
    return CalibrationRun(result, MODE_APP, outcome=outcome, layout=layout)


def _point_number(attrs: dict[str, str], n: int) -> int | None:
    try:
        point = int(attrs["PT"])
    except (KeyError, ValueError):
        return None
    return point if 1 <= point <= n else None


def _position(attrs: dict[str, str], layout: list[tuple[float, float]], point: int) -> tuple[float, float]:
    """CALX / CALY of the record (what Control says it is showing), else the sent layout's."""
    try:
        return float(attrs["CALX"]), float(attrs["CALY"])
    except (KeyError, ValueError):
        return layout[point - 1]


def _result_from_calib_result(n: int, per_point: list[dict[str, Any]] | None) -> CalibrationResult:
    """The run's result, from ``CALIB_RESULT`` alone: ``CALIBRATE_RESULT_SUMMARY`` is retained
    state (feasibility 6.1) and is never asked for. Valid when any eye of any point was valid; the
    mean error in px needs the monitor's size, so :func:`annotate` adds it. Without
    ``CALIB_RESULT`` there is no result at all."""
    breakdown = tuple(per_point) if per_point else None
    valid = bool(breakdown) and any(
        eye is not None and eye["valid"] for point in breakdown for eye in (point["left"], point["right"])
    )
    return CalibrationResult(n_points=n, mean_error_px=None, valid=valid, per_point=breakdown)


class _TimingLog:
    """The run's record in ``_diagnostics/calibration_timing.jsonl`` (4.2, 4.7): the mode, and
    per point when it started, when its result came and when the glide ended and the hold began
    (the times the window is held to, :func:`~src.engine.calibration_motion.schedule`)."""

    def __init__(
        self, path: str | Path | None, settings: CalibrationSettings, delay_s: float, timeout_s: float,
        points: dict[int, dict[str, float]], clock: Callable[[], float],
    ) -> None:
        self._path = path
        self._settings = settings
        self._delay_s = delay_s
        self._timeout_s = timeout_s
        self._points = points
        self._clock = clock
        self.t_start = clock()

    def write(self, outcome: str, *, result: CalibrationResult | None = None, reason: str = "") -> None:
        if self._path is None:
            return
        glide, shrink = schedule(self._delay_s)
        rows = []
        for point in sorted(self._points):
            times = self._points[point]
            start, done = times.get("start"), times.get("result")
            rows.append(
                {
                    "point": point,
                    "t_start_s": None if start is None else round(start - self.t_start, 4),
                    "t_result_s": None if done is None else round(done - self.t_start, 4),
                    "t_glide_end_s": None if start is None else round(start + glide - self.t_start, 4),
                    "t_hold_start_s": None if start is None else round(start + glide + shrink - self.t_start, 4),
                }
            )
        _append_timing_record(
            self._path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": MODE_APP,  # a fallback's own Control run writes its record as control_fallback
                "n_points": self._settings.points,
                "outcome": outcome,
                "fallback_reason": reason or None,
                "delay_s": self._delay_s,
                "timeout_s": self._timeout_s,
                "elapsed_s": round(self._clock() - self.t_start, 4),
                "points": rows,
                "valid": None if result is None else result.valid,
                "mean_error_px": None if result is None else result.mean_error_px,
            },
        )
