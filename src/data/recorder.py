"""Per-session data recorder.

Writes one directory per recorded run, under the subject's own folder
(SPEC-subject-data-layout.md H1, H2)::

    sessions/
      P001/                                # the subject's folder (subject.json inside)
        runs/click_grid/2026-07-15_1432/   # runs/<task_id>/<YYYY-MM-DD_HHMM>[_2]
          metadata.json      # subject, calibration error, schema version
          session.log        # human-readable timeline
          gaze_stream.csv    # per-frame gaze samples
          all_gaze.csv       # every raw <REC>, Gazepoint Analysis export layout (optional)
          eye_geometry.csv   # 3D eye position + per-eye POG per raw <REC> (optional)
          trials.csv         # one row per trial
          target_track.csv   # moving target's position at ~20 Hz (follow_moving only)
          pointer_stream.csv # the mouse pointer per frame (a Mouse run only)
          events.jsonl       # discrete events (DWELL_START, TARGET_SHOWN, ...)

The recorder is deliberately GUI-free and streams to disk incrementally so a
crash mid-session still leaves usable partial data (SPEC-audit-fixes.md H5): ``metadata.json``
is written at :meth:`SessionRecorder.open` (``"complete": false``) and again at ``close()``
(``"complete": true``), ``trials.csv`` gets its header at ``open`` and one row at the end of
each trial, and the other CSVs are flushed at every trial end.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from ..engine.run_paths import new_run_dir
from .analysis_export import (
    ALL_GAZE_FILENAME,
    EYE_GEOMETRY_COLUMNS,
    EYE_GEOMETRY_FILENAME,
    all_gaze_header,
    rec_to_all_gaze_row,
    rec_to_eye_geometry_row,
)
from .null_recorder import NullRecorder  # noqa: F401  (re-exported: it used to live here)
from .schema import GazeSample, SessionMetadata, TrialRecord

_GAZE_HEADER = [
    "t_ns",
    "x",
    "y",
    "valid",
    "fixation_id",
    "fix_duration_s",
    "pupil_left",
    "pupil_right",
]

# The moving target's path (SPEC-compass-task-flow.md 4D.4-2): ``t_ns`` is the
# host clock, like ``trials.csv``; ``x``/``y`` are canvas-normalized. A trial
# re-presented after a pause repeats its ``trial`` id, so a reader windows on
# the trial's own ``[t_target_shown_ns, t_end_ns]``.
TARGET_TRACK_FILENAME = "target_track.csv"
TARGET_TRACK_COLUMNS = ["t_ns", "trial", "x", "y"]

# The mouse pointer of a Mouse run, one row per frame (SPEC-input-selection-and-follow.md
# H4): host clock and canvas-normalized x/y like ``gaze_stream.csv``, ``valid`` 1 while the
# pointer is inside the canvas. Lets the report draw the mouse path.
POINTER_STREAM_FILENAME = "pointer_stream.csv"
POINTER_STREAM_COLUMNS = ["t_ns", "x", "y", "valid"]

METADATA_FILENAME = "metadata.json"
SESSION_LOG_FILENAME = "session.log"
GAZE_STREAM_FILENAME = "gaze_stream.csv"
EVENTS_FILENAME = "events.jsonl"
TRIALS_FILENAME = "trials.csv"

# Every file name a SessionRecorder can create in its folder (the same constants its
# ``open`` calls use). A run that fails to start removes its folder only if it holds nothing
# but these and its calibration.json (SPEC-audit-fixes.md H11).
RECORDER_FILENAMES = frozenset(
    {
        METADATA_FILENAME,
        SESSION_LOG_FILENAME,
        GAZE_STREAM_FILENAME,
        EVENTS_FILENAME,
        TRIALS_FILENAME,
        ALL_GAZE_FILENAME,
        EYE_GEOMETRY_FILENAME,
        TARGET_TRACK_FILENAME,
        POINTER_STREAM_FILENAME,
    }
)


class SessionRecorder:
    """Streams gaze samples, trials and events to a session directory."""

    def __init__(
        self,
        metadata: SessionMetadata,
        output_root: str | Path = "sessions",
        session_dir: str | Path | None = None,
    ) -> None:
        """``session_dir`` is the run folder, already made by :func:`~src.engine.run_paths.
        new_run_dir` (``AssessmentApp`` needs it before the recorder exists) or any folder
        the caller owns (a headless replay). Without one, this makes the run folder
        itself, ``<output_root>/<subject folder>/runs/<task_id>/<YYYY-MM-DD_HHMM>``."""
        self.metadata = metadata
        if session_dir is None:
            task_id = metadata.tasks[0] if metadata.tasks else "session"
            session_dir = new_run_dir(output_root, metadata.subject_id, task_id)
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self._gaze_file: TextIO | None = None
        self._gaze_writer: csv.DictWriter | None = None
        self._events_file: TextIO | None = None
        self._log_file: TextIO | None = None
        # trials.csv, appended one row per finished trial (record_trial); write_trials()
        # replaces it with the whole table at the end of the run.
        self._trials_file: TextIO | None = None
        self._trials_writer: csv.DictWriter | None = None
        self._trials_recorded = 0
        self._closed = False
        # Flush the gaze CSV at least this often so a hard crash (SIGKILL, power
        # loss) leaves at most ~this many buffered samples on the floor.
        self._gaze_flush_every = 60
        self._gaze_since_flush = 0

        # Optional second per-sample file in Gazepoint Analysis's own export
        # layout (SPEC-gazepoint-analysis-export-parity.md S5): one row per
        # raw <REC> received, not per GUI frame -- opened by open_all_gaze().
        self._all_gaze_file: TextIO | None = None
        self._all_gaze_writer: Any = None  # csv.writer instance
        self._all_gaze_media_name = ""
        self._all_gaze_time_origin_s: float | None = None
        self._all_gaze_since_flush = 0

        # Optional third per-sample file, device rate like all_gaze.csv and
        # sharing its TIME origin (SPEC S10.6.2) -- opened by open_eye_geometry().
        self._eye_file: TextIO | None = None
        self._eye_writer: Any = None
        self._eye_since_flush = 0

        # target_track.csv is opened by the first record_target_track() call,
        # so only a task that moves its target leaves one.
        self._track_file: TextIO | None = None
        self._track_writer: Any = None
        self._track_since_flush = 0

        # pointer_stream.csv exists only for a Mouse run: opened by open_pointer_stream().
        self._pointer_file: TextIO | None = None
        self._pointer_writer: Any = None
        self._pointer_since_flush = 0

        # Smallest (host receive time - device TIME) seen in record_raw, in ns:
        # the host-clock time of all_gaze.csv's TIME=0 (SPEC 4D.4-5).
        self._raw_clock_offset_ns: int | None = None

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> SessionRecorder:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def open(self, *, gaze_stream: bool = True) -> None:
        """Open the session files. ``gaze_stream=False`` is a Mouse run with no
        tracker (SPEC-input-selection-and-follow.md H4): there is no gaze, so no
        ``gaze_stream.csv`` is created and :meth:`record_gaze` must not be called."""
        if gaze_stream:
            self._gaze_file = (self.session_dir / GAZE_STREAM_FILENAME).open(
                "w", newline="", encoding="utf-8"
            )
            self._gaze_writer = csv.DictWriter(self._gaze_file, fieldnames=_GAZE_HEADER)
            self._gaze_writer.writeheader()

        self._events_file = (self.session_dir / EVENTS_FILENAME).open(
            "w", encoding="utf-8"
        )
        self._log_file = (self.session_dir / SESSION_LOG_FILENAME).open("w", encoding="utf-8")

        # Crash safety (H5): the metadata known now, marked incomplete until close(), and
        # the trial table's header, so a run that dies leaves both beside the finished trials.
        self.write_metadata(complete=False)
        self._trials_file = (self.session_dir / TRIALS_FILENAME).open("w", newline="", encoding="utf-8")
        self._trials_writer = csv.DictWriter(self._trials_file, fieldnames=TrialRecord.csv_header())
        self._trials_writer.writeheader()
        self._trials_file.flush()

    def open_all_gaze(self, media_name: str, tick_frequency: int | None) -> None:
        """Start ``all_gaze.csv`` (Gazepoint Analysis layout). Call after
        :meth:`open`. ``media_name`` fills the ``MEDIA_NAME`` column (the
        task id -- our analogue of Analysis's stimulus name); ``tick_frequency``
        is the device's ``TIME_TICK_FREQUENCY`` for the ``TIMETICK(f=..)``
        header, 0 when unknown."""
        if self._all_gaze_file is not None:
            return
        self._all_gaze_media_name = media_name
        self._all_gaze_file = (self.session_dir / ALL_GAZE_FILENAME).open(
            "w", newline="", encoding="utf-8"
        )
        self._all_gaze_writer = csv.writer(self._all_gaze_file)
        self._all_gaze_writer.writerow(all_gaze_header(datetime.now(), tick_frequency))

    def open_eye_geometry(self) -> None:
        """Start ``eye_geometry.csv`` (SPEC S10.6.2). Call after :meth:`open`;
        rows come from :meth:`record_raw`, like ``all_gaze.csv``."""
        if self._eye_file is not None:
            return
        self._eye_file = (self.session_dir / EYE_GEOMETRY_FILENAME).open(
            "w", newline="", encoding="utf-8"
        )
        self._eye_writer = csv.writer(self._eye_file)
        self._eye_writer.writerow(EYE_GEOMETRY_COLUMNS)

    def open_pointer_stream(self) -> None:
        """Start ``pointer_stream.csv`` (a Mouse run): the header is written at once,
        so the file exists even if no frame is ever recorded. Call after :meth:`open`."""
        if self._pointer_file is not None:
            return
        self._pointer_file = (self.session_dir / POINTER_STREAM_FILENAME).open(
            "w", newline="", encoding="utf-8"
        )
        self._pointer_writer = csv.writer(self._pointer_file)
        self._pointer_writer.writerow(POINTER_STREAM_COLUMNS)

    def flush_eye_geometry(self) -> None:
        """Push buffered ``eye_geometry.csv`` rows to disk (so it can be read
        back before :meth:`close`)."""
        if self._eye_file is not None:
            self._eye_file.flush()

    def flush_all_gaze(self) -> None:
        """Same for ``all_gaze.csv``."""
        if self._all_gaze_file is not None:
            self._all_gaze_file.flush()

    # -- writers -----------------------------------------------------------

    def record_raw(self, t_ns: int, attrs: dict[str, str]) -> None:
        """Append one raw ``<REC>`` to ``all_gaze.csv`` and/or
        ``eye_geometry.csv``; a no-op unless :meth:`open_all_gaze` /
        :meth:`open_eye_geometry` was called, so callers need not branch.

        ``TIME`` is rewritten relative to the first record (the export's
        convention), from the device's own ``TIME`` when present, else from
        ``t_ns`` -- the two are never mixed within one file.
        """
        if self._all_gaze_writer is None and self._eye_writer is None:
            return
        device_time = _parse_float(attrs.get("TIME"))
        now_s = device_time if device_time is not None else t_ns / 1e9
        if self._all_gaze_time_origin_s is None:
            self._all_gaze_time_origin_s = now_s
        time_s = now_s - self._all_gaze_time_origin_s
        # ``t_ns`` is the host receive time of a record whose device time is
        # ``time_s``: the delay is never negative, so the minimum is the best
        # estimate of where TIME=0 sits on the host clock. Without a device TIME
        # ``time_s`` is host-relative and this is the constant first t_ns.
        offset_ns = t_ns - round(time_s * 1e9)
        if self._raw_clock_offset_ns is None or offset_ns < self._raw_clock_offset_ns:
            self._raw_clock_offset_ns = offset_ns
        if self._all_gaze_writer is not None:
            row = rec_to_all_gaze_row(
                attrs,
                time_s=time_s,
                media_name=self._all_gaze_media_name,
            )
            self._all_gaze_writer.writerow(list(row.values()))
            self._all_gaze_since_flush += 1
            if self._all_gaze_since_flush >= self._gaze_flush_every:
                self._all_gaze_file.flush()
                self._all_gaze_since_flush = 0
        if self._eye_writer is not None:
            self._eye_writer.writerow(rec_to_eye_geometry_row(attrs, time_s=time_s))
            self._eye_since_flush += 1
            if self._eye_since_flush >= self._gaze_flush_every:
                self._eye_file.flush()
                self._eye_since_flush = 0

    @property
    def raw_clock_offset_ns(self) -> int | None:
        """Host-clock time (ns) of ``all_gaze.csv`` ``TIME=0``; None until a raw
        record was written (SPEC 4D.4-5)."""
        return self._raw_clock_offset_ns

    def record_target_track(self, t_ns: int, trial: int, x: float, y: float) -> None:
        """Append one moving-target position to ``target_track.csv`` (created,
        with its header, by the first call)."""
        if self._track_writer is None:
            if self._events_file is None:
                raise RuntimeError("Recorder is not open.")
            self._track_file = (self.session_dir / TARGET_TRACK_FILENAME).open(
                "w", newline="", encoding="utf-8"
            )
            self._track_writer = csv.writer(self._track_file)
            self._track_writer.writerow(TARGET_TRACK_COLUMNS)
        self._track_writer.writerow([t_ns, trial, round(x, 5), round(y, 5)])
        self._track_since_flush += 1
        if self._track_since_flush >= self._gaze_flush_every:
            self._track_file.flush()
            self._track_since_flush = 0

    def record_pointer(self, sample: GazeSample) -> None:
        """Append one mouse-pointer sample to ``pointer_stream.csv``; a no-op unless
        :meth:`open_pointer_stream` was called."""
        if self._pointer_writer is None:
            return
        self._pointer_writer.writerow(
            [sample.t_ns, round(sample.x, 5), round(sample.y, 5), int(sample.valid)]
        )
        self._pointer_since_flush += 1
        if self._pointer_since_flush >= self._gaze_flush_every:
            self._pointer_file.flush()
            self._pointer_since_flush = 0

    def record_gaze(self, sample: GazeSample) -> None:
        if self._gaze_writer is None:
            raise RuntimeError("Recorder is not open; call open() or use as context manager.")
        self._gaze_writer.writerow(sample.as_row())
        self._gaze_since_flush += 1
        if self._gaze_since_flush >= self._gaze_flush_every:
            self._gaze_file.flush()
            self._gaze_since_flush = 0

    def record_event(self, kind: str, t_ns: int, **payload: Any) -> None:
        if self._events_file is None:
            raise RuntimeError("Recorder is not open.")
        event = {"t_ns": t_ns, "kind": kind, **payload}
        self._events_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        # Events are low-frequency and high-value; flush each one so the trial
        # timeline survives a crash.
        self._events_file.flush()

    def log(self, message: str) -> None:
        if self._log_file is None:
            raise RuntimeError("Recorder is not open.")
        self._log_file.write(message.rstrip("\n") + "\n")
        self._log_file.flush()

    def record_trial(self, trial: TrialRecord) -> None:
        """Append one finished trial to ``trials.csv`` and push every open CSV to disk, so
        a run that dies between trials keeps everything up to the last one (H5). A no-op
        once :meth:`write_trials` has written the final table."""
        if self._events_file is None:
            raise RuntimeError("Recorder is not open.")
        if self._trials_writer is None or self._trials_file is None:
            return
        self._trials_writer.writerow(trial.as_row())
        self._trials_recorded += 1
        for fh in (
            self._trials_file,
            self._gaze_file,
            self._all_gaze_file,
            self._eye_file,
            self._track_file,
            self._pointer_file,
        ):
            if fh is not None:
                fh.flush()

    def _close_trials(self) -> None:
        if self._trials_file is not None:
            self._trials_file.flush()
            self._trials_file.close()
        self._trials_file = None
        self._trials_writer = None

    def write_trials(self, trials: list[TrialRecord]) -> Path:
        """Write the whole trial table, replacing the rows :meth:`record_trial` appended, so
        the final file is the one a run has always ended with."""
        path = self.session_dir / TRIALS_FILENAME
        self._close_trials()
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=TrialRecord.csv_header())
            writer.writeheader()
            for trial in trials:
                writer.writerow(trial.as_row())
        return path

    def write_metadata(self, complete: bool | None = None) -> Path:
        """Write ``metadata.json``. ``complete`` adds the ``"complete"`` key: False while the
        run is open, True once :meth:`close` has written the final file; left out (the file
        every older run has) when None."""
        path = self.session_dir / METADATA_FILENAME
        payload = self.metadata.to_dict()
        if complete is not None:
            payload["complete"] = complete
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    @property
    def trials_recorded(self) -> int:
        """How many finished trials :meth:`record_trial` has appended to ``trials.csv``."""
        return self._trials_recorded

    # -- teardown ----------------------------------------------------------

    def _open_files(self) -> tuple[TextIO | None, ...]:
        return (
            self._gaze_file,
            self._all_gaze_file,
            self._eye_file,
            self._track_file,
            self._pointer_file,
            self._events_file,
            self._log_file,
        )

    def close(self) -> None:
        if self._closed:
            return
        # metadata is (re)written on close so late fields (calibration error,
        # task list) are captured.
        self.write_metadata(complete=True)
        self._close_trials()
        for fh in self._open_files():
            if fh is not None:
                fh.flush()
                fh.close()
        self._closed = True

    def abort(self) -> None:
        """Release every open file without writing anything more (SPEC-audit-fixes.md H11):
        for a run that failed to start, whose folder may now be removed (Windows cannot
        delete an open file). ``metadata.json`` keeps ``"complete": false``. Best effort: a
        file that will not flush or close does not stop the others being closed."""
        if self._closed:
            return
        for fh in (self._trials_file, *self._open_files()):
            if fh is not None:
                try:
                    fh.close()  # flushes first
                except OSError:
                    pass
        self._trials_file = None
        self._trials_writer = None
        self._closed = True


def _parse_float(raw: str | None) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None
