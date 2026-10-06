"""SPEC-compass-task-flow.md 4D.4 / 4D.10 (P3, recording additions): the new
``trials.csv`` columns (``entries``, ``end_x``, ``end_y``, ``slot_index``, R6),
the ``target_track.csv`` writer, the raw clock offset (G9), and the ``BaseTask``
wiring of the entry tracker. G1 is in ``test_entry_tracker.py``; G11 is in
``test_task_pipeline.py``; the app-level metadata fields are in
``test_run_modes_app.py``."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.data.exporter import load_trials_rows
from src.data.recorder import (
    TARGET_TRACK_COLUMNS,
    TARGET_TRACK_FILENAME,
    NullRecorder,
    SessionRecorder,
)
from src.data.schema import SessionMetadata, TrialRecord
from src.engine.config import load_task_config
from src.engine.feedback import NullFeedback
from src.engine.task_runner import build_task, run_headless_replay
from src.inputs.base import Pointer
from src.inputs.eye_input import DwellConfig, DwellSelector
from src.tasks.base_task import BaseTask, TargetSpec
from src.tasks.entry_tracker import DEFAULT_EXIT_HOLD_MS
from src.tasks.target_track import TRACK_INTERVAL_NS, TrackThrottle

MS = 1_000_000
FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


def metadata(session_id: str = "S") -> SessionMetadata:
    return SessionMetadata(subject_id="P001", session_id=session_id, started_ns=0)


# -- the trials.csv columns (R6) ---------------------------------------------


def test_the_new_columns_follow_is_skipped_in_the_agreed_order():
    header = TrialRecord.csv_header()
    assert header[header.index("is_skipped") :] == ["is_skipped", "entries", "end_x", "end_y", "slot_index"]
    assert "outcome" not in header
    assert list(TrialRecord(0, "t", 0.5, 0.5, 90, 0).as_row()) == header


def test_the_new_fields_default_to_none_recorded():
    row = TrialRecord(0, "t", 0.5, 0.5, 90, 0).as_row()
    assert (row["entries"], row["end_x"], row["end_y"], row["slot_index"]) == (0, "", "", -1)


def test_the_new_fields_are_written_as_given():
    trial = TrialRecord(0, "t", 0.5, 0.5, 90, 0, entries=3, end_x=0.25, end_y=0.75, slot_index=4)
    row = trial.as_row()
    assert (row["entries"], row["end_x"], row["end_y"], row["slot_index"]) == (3, 0.25, 0.75, 4)


def test_an_older_trials_csv_without_the_columns_still_loads(tmp_path: Path):
    session = tmp_path / "old"
    session.mkdir()
    old = [c for c in TrialRecord.csv_header() if c not in ("entries", "end_x", "end_y", "slot_index")]
    with (session / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=old)
        writer.writeheader()
        row = TrialRecord(0, "t", 0.5, 0.5, 90, 0).as_row()
        writer.writerow({k: row[k] for k in old})
    rows = load_trials_rows(session)
    assert len(rows) == 1 and "entries" not in rows[0]


# -- target_track.csv writer -------------------------------------------------


def test_target_track_has_a_header_and_one_row_per_call(tmp_path: Path):
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.record_target_track(10 * MS, 0, 0.12345678, 0.5)
        rec.record_target_track(60 * MS, 0, 0.2, 0.5)
        rec.record_target_track(900 * MS, 1, 0.9, 0.25)
    path = tmp_path / "S" / TARGET_TRACK_FILENAME
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == TARGET_TRACK_COLUMNS == ["t_ns", "trial", "x", "y"]
    assert rows[1:] == [
        ["10000000", "0", "0.12346", "0.5"],
        ["60000000", "0", "0.2", "0.5"],
        ["900000000", "1", "0.9", "0.25"],
    ]


def test_a_run_that_never_moves_a_target_leaves_no_target_track(tmp_path: Path):
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.write_trials([])
    assert not (tmp_path / "S" / TARGET_TRACK_FILENAME).exists()


def test_target_track_is_flushed_to_disk_as_it_goes(tmp_path: Path):
    rec = SessionRecorder(metadata(), output_root=tmp_path)
    rec.open()
    try:
        for i in range(61):  # past the 60-row flush interval
            rec.record_target_track(i * MS, 0, 0.5, 0.5)
        lines = (tmp_path / "S" / TARGET_TRACK_FILENAME).read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 1 + 60
    finally:
        rec.close()


def test_target_track_before_open_is_refused(tmp_path: Path):
    rec = SessionRecorder(metadata(), output_root=tmp_path)
    with pytest.raises(RuntimeError):
        rec.record_target_track(0, 0, 0.5, 0.5)
    rec.close()


def test_null_recorder_takes_the_new_calls_and_writes_nothing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rec = NullRecorder(metadata())
    rec.record_target_track(1, 0, 0.5, 0.5)
    assert rec.raw_clock_offset_ns is None
    assert list(tmp_path.iterdir()) == []


def test_track_throttle_is_due_on_the_first_frame_then_every_interval():
    throttle = TrackThrottle()
    assert TRACK_INTERVAL_NS == 50 * MS  # 20 Hz
    due = [t for t in range(0, 210, 10) if throttle.due(t * MS)]
    assert due == [0, 50, 100, 150, 200]
    throttle.reset()
    assert throttle.due(205 * MS)  # a new trial starts with a sample again


# -- raw clock offset (G9) ---------------------------------------------------


def raw_attrs(i: int, time_s: float | None) -> dict[str, str]:
    attrs = {"CNT": str(i), "FPOGX": "0.5", "FPOGY": "0.5", "FPOGV": "1"}
    if time_s is not None:
        attrs["TIME"] = str(time_s)
    return attrs


def test_the_raw_clock_offset_is_the_smallest_host_minus_device_delay(tmp_path: Path):
    base = 5_000_000_000_000  # host clock at the first record's device TIME
    delays_ms = [7, 3, 12, 4, 9, 3.5, 20]  # how late each record reached the host
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.open_all_gaze("click_static", 0)
        assert rec.raw_clock_offset_ns is None  # nothing recorded yet
        for i, delay in enumerate(delays_ms):
            device_s = 200.0 + i * 0.0625  # exact in binary: no float noise in the check
            rec.record_raw(base + round(i * 0.0625 * 1e9) + round(delay * 1e6), raw_attrs(i, device_s))
        assert rec.raw_clock_offset_ns == base + 3_000_000


def test_the_raw_clock_offset_gives_back_host_time_from_device_time(tmp_path: Path):
    base = 7_000_000_000_000
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.open_all_gaze("click_static", 0)
        for i in range(5):
            rec.record_raw(base + i * 8 * MS + (2 * MS if i else 0), raw_attrs(i, 50.0 + i * 0.008))
        offset = rec.raw_clock_offset_ns
    # TIME is rewritten to start at 0, so t_ns(record) = offset + TIME * 1e9.
    assert offset == base
    assert offset + 0.008 * 1e9 == pytest.approx(base + 8 * MS)


def test_a_replay_without_device_time_has_one_consistent_offset(tmp_path: Path):
    base = 3_000_000_000_000
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.open_all_gaze("click_static", 0)
        for i in range(20):
            rec.record_raw(base + i * 8 * MS, raw_attrs(i, None))
        # TIME comes from the host clock here, so every record has the same
        # offset (the first t_ns), up to float rounding of t_ns / 1e9.
        assert rec.raw_clock_offset_ns == pytest.approx(base, abs=5)


def test_the_raw_clock_offset_also_tracks_with_only_eye_geometry_open(tmp_path: Path):
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.open_eye_geometry()
        rec.record_raw(4_000_000_000, raw_attrs(0, 10.0))
        assert rec.raw_clock_offset_ns == 4_000_000_000


def test_no_raw_file_open_means_no_offset(tmp_path: Path):
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        rec.record_raw(1, raw_attrs(0, 1.0))
        assert rec.raw_clock_offset_ns is None


# -- BaseTask wiring ---------------------------------------------------------


class Spy:
    """Recorder double that also takes target-track rows."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []
        self.track: list[tuple[int, int, float, float]] = []

    def record_event(self, kind, t_ns, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message) -> None: ...

    def record_target_track(self, t_ns, trial, x, y) -> None:
        self.track.append((t_ns, trial, x, y))


class Fixed(BaseTask):
    """Targets at fixed positions, each in its own numbered slot."""

    def build_targets(self):
        return [TargetSpec(index=i, x_norm=0.3, y_norm=0.5, radius_px=50.0, slot_index=i % 3) for i in range(4)]


class FixedMoving(Fixed):
    records_target_track = True

    def target_position(self, target, elapsed_ns):
        return 0.1 + elapsed_ns / 1e10, 0.5  # 0.1 per second to the right


def make(cls=Fixed, mode="eye", recorder=None, dwell=None, **cfg):
    task_cfg = {"task_id": "fixed", "timeout_ms": 1000, "inter_trial_interval_ms": 0, **cfg}
    return cls({"task": task_cfg}, 1000, 1000, recorder=recorder, feedback=NullFeedback(), dwell=dwell, input_mode=mode)


ON = Pointer(x=0.3, y=0.5, valid=True, clicked=False)
OFF = Pointer(x=0.9, y=0.9, valid=True, clicked=False)
LOST = Pointer(x=0.5, y=0.5, valid=False, clicked=False)


def test_the_entry_hold_is_the_dwells_hold_grace_or_its_default():
    assert make()._entries.exit_hold_ns == int(DEFAULT_EXIT_HOLD_MS * 1e6)
    dwell = DwellSelector(DwellConfig(hold_grace_ms=300))
    assert make(dwell=dwell)._entries.exit_hold_ns == 300 * MS


def test_a_hit_records_entries_end_position_and_slot():
    task = make(mode="switch", recorder=Spy())
    task.update(0, OFF)  # trial 0 shown, gaze elsewhere
    task.update(10 * MS, ON)
    task.update(20 * MS, Pointer(x=0.3, y=0.5, valid=True, clicked=True))
    row = task.trials[0]
    assert (row.is_hit, row.entries) == (True, 1)
    assert (row.end_x, row.end_y) == (0.3, 0.5)  # a static target ends where it started
    assert row.slot_index == 0
    assert row.time_to_first_fixation_ms == 10.0


def test_every_hit_has_at_least_one_entry():
    task = make(mode="switch", recorder=Spy())
    t = 0
    while not task.is_done and t < 60_000:
        index = min(len(task.trials), len(task.targets) - 1)
        target = task.targets[index]
        task.update(t * MS, Pointer(x=target.x_norm, y=target.y_norm, valid=True, clicked=True))
        t += 10
    assert task.is_done
    assert [r.slot_index for r in task.trials] == [0, 1, 2, 0]
    assert all(r.is_hit and r.entries >= 1 for r in task.trials)


def test_a_timeout_that_never_saw_the_gaze_has_zero_entries():
    task = make(mode="switch", recorder=Spy())
    t = 0
    while not task.trials and t < 5_000:
        task.update(t * MS, OFF)
        t += 10
    row = task.trials[0]
    assert (row.is_timeout, row.entries, row.t_first_gaze_on_target_ns) == (True, 0, None)


def test_a_skipped_trial_keeps_the_entries_it_had_and_its_end_position():
    task = make(mode="switch", recorder=Spy())
    task.update(0, ON)
    task.update(10 * MS, ON)
    assert task.skip_trial(20 * MS)
    row = task.trials[0]
    assert (row.is_skipped, row.entries) == (True, 1)
    assert (row.end_x, row.end_y) == (0.3, 0.5)


def test_each_trial_counts_its_own_entries():
    task = make(mode="switch", recorder=Spy())
    task.update(0, ON)  # trial 0: on target at once
    task.skip_trial(10 * MS)
    task.update(20 * MS, OFF)  # ITI is 0: trial 1 starts on the next frame
    task.update(30 * MS, OFF)
    task.skip_trial(40 * MS)
    assert [r.entries for r in task.trials] == [1, 0]


def test_a_dropout_does_not_split_a_visit_or_start_one():
    task = make(mode="switch", recorder=Spy())
    task.update(0, ON)
    for i in range(1, 40):
        task.update(i * 10 * MS, LOST)  # 400 ms of lost tracking
    task.update(400 * MS, ON)
    task.skip_trial(410 * MS)
    assert task.trials[0].entries == 1


def test_a_pause_that_drops_a_trial_starts_the_re_presented_one_from_zero():
    task = make(mode="switch", recorder=Spy())
    task.update(0, ON)
    assert task.pause(10 * MS) is True
    task.resume(500 * MS)
    task.update(510 * MS, OFF)  # the same target again, as a fresh trial
    task.skip_trial(520 * MS)
    assert task.trials[0].entries == 0


def test_a_moving_target_ends_where_it_is_at_the_end_not_where_it_began():
    task = make(FixedMoving, mode="switch", recorder=Spy())
    t = 0
    while not task.trials and t < 5_000:
        task.update(t * MS, OFF)
        t += 10
    row = task.trials[0]
    assert row.is_timeout
    assert (row.target_x, row.target_y) == (0.1, 0.5)
    assert row.end_x == pytest.approx(0.2)  # 1 s at 0.1 per second
    assert row.end_y == 0.5


# -- target_track.csv through the task ---------------------------------------


def run_moving(spy, trials: int = 2) -> BaseTask:
    task = make(FixedMoving, mode="switch", recorder=spy)
    t = 0
    while len(task.trials) < trials and t < 10_000:
        task.update(t * MS, OFF)
        t += 10
    return task


def test_a_moving_task_logs_its_path_at_20_hz_with_the_trial_number():
    spy = Spy()
    run_moving(spy, trials=2)
    trial0 = [r for r in spy.track if r[1] == 0]
    trial1 = [r for r in spy.track if r[1] == 1]
    assert [r[0] // MS for r in trial0] == list(range(0, 1001, 50))  # shown at 0, timed out at 1000
    # Trial 1 starts on the ITI frame (1010) and is first sampled on the next one.
    assert trial1 and trial1[0][0] == 1020 * MS
    assert all(b[0] - a[0] == 50 * MS for a, b in zip(trial0, trial0[1:], strict=False))
    # The logged position is the live one at that moment.
    for t_ns, _trial, x, y in trial0:
        assert x == pytest.approx(0.1 + (t_ns - trial0[0][0]) / 1e10, abs=1e-5)
        assert y == 0.5


def test_a_static_task_logs_no_path():
    spy = Spy()
    task = make(mode="switch", recorder=spy)
    for i in range(50):
        task.update(i * 10 * MS, OFF)
    assert spy.track == []


def test_a_moving_task_with_a_recorder_double_that_has_no_track_writer_still_runs():
    class EventsOnly:
        def record_event(self, *a, **k) -> None: ...
        def log(self, *a) -> None: ...

    task = make(FixedMoving, mode="switch", recorder=EventsOnly())
    for i in range(20):
        task.update(i * 10 * MS, OFF)  # must not raise
    task = make(FixedMoving, mode="switch", recorder=None)
    task.update(0, OFF)


def test_a_moving_task_writes_target_track_csv_through_a_real_recorder(tmp_path: Path):
    with SessionRecorder(metadata(), output_root=tmp_path) as rec:
        task = make(FixedMoving, mode="switch", recorder=rec)
        for i in range(101):
            task.update(i * 10 * MS, OFF)
        rec.write_trials(task.trials)
    rows = list(csv.DictReader((tmp_path / "S" / TARGET_TRACK_FILENAME).open(encoding="utf-8")))
    assert [r["trial"] for r in rows][:3] == ["0", "0", "0"]
    assert len(rows) == 21
    trials = load_trials_rows(tmp_path / "S")
    assert trials[0]["end_x"] != "" and float(trials[0]["end_x"]) == pytest.approx(0.2)


# -- the real tasks ----------------------------------------------------------


def switch_cfg(task_id: str) -> dict:
    cfg = load_task_config(task_id)
    cfg["input"] = {"mode": "switch"}
    cfg["task"]["inter_trial_interval_ms"] = 0
    return cfg


@pytest.mark.parametrize("task_id", ["click_grid", "scanning"])
def test_a_layout_task_records_the_slot_each_trial_used(task_id: str):
    task = build_task(task_id, switch_cfg(task_id), recorder=Spy(), feedback=NullFeedback())
    t = 0
    while not task.is_done and t < 600_000:
        target = task.targets[min(len(task.trials), len(task.targets) - 1)]
        task.update(t * MS, Pointer(x=target.x_norm, y=target.y_norm, valid=True, clicked=True))
        t += 20
    assert task.is_done
    assert [r.slot_index for r in task.trials] == [t_.slot_index for t_ in task.targets]
    assert all(0 <= r.slot_index < len(task.layout_slots) for r in task.trials)
    assert all((r.end_x, r.end_y) == (r.target_x, r.target_y) for r in task.trials)
    assert all(r.is_hit and r.entries >= 1 for r in task.trials)


def test_click_static_has_no_slot():
    task = build_task("click_static", switch_cfg("click_static"), recorder=Spy(), feedback=NullFeedback())
    task.update(0, OFF)
    task.skip_trial(10 * MS)
    assert task.trials[0].slot_index == -1


def test_follow_moving_is_the_task_that_records_a_path():
    assert build_task("follow_moving", load_task_config("follow_moving")).records_target_track is True
    for task_id in ("click_static", "click_grid", "scanning"):
        assert build_task(task_id, load_task_config(task_id)).records_target_track is False


# -- headless replay ---------------------------------------------------------


@pytest.mark.parametrize("task_id", ["click_static", "follow_moving"])
def test_a_headless_replay_writes_the_new_columns(task_id: str, tmp_path: Path):
    result = run_headless_replay(task_id=task_id, replay_path=FIXTURE, output_root=tmp_path, max_seconds=60.0)
    session = Path(result["session_dir"])
    rows = load_trials_rows(session)
    assert rows
    assert list(rows[0]) == TrialRecord.csv_header()
    assert all(r["end_x"] != "" and r["end_y"] != "" for r in rows)
    assert all(int(r["entries"]) >= 1 for r in rows if r["is_hit"] == "1")
    assert (session / TARGET_TRACK_FILENAME).exists() is (task_id == "follow_moving")
