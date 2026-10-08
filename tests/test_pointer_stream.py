"""SPEC-input-selection-and-follow.md H4, 4.6: ``pointer_stream.csv`` and the Mouse run's
recorder (no gaze file without a tracker), the new ``trials.csv`` / ``metadata.json`` fields,
the run bar's wording for a Mouse run, and the no-tracker stand-in. No Qt."""

from __future__ import annotations

import csv
import json

import pytest

from src.data.recorder import (
    POINTER_STREAM_COLUMNS,
    POINTER_STREAM_FILENAME,
    NullRecorder,
)
from src.data.schema import GazeSample, SessionMetadata, TrialRecord
from src.engine.tracking_status import run_status
from src.inputs.no_tracker import NoTracker
from tests.recorder_helpers import recorder_in


def meta(session_id="mouse_run"):
    return SessionMetadata(subject_id="P001", session_id=session_id, started_ns=0)


def sample(t_ns, x=0.25, y=0.5, valid=True):
    return GazeSample(t_ns=t_ns, x=x, y=y, valid=valid)


def rows(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# -- pointer_stream.csv ------------------------------------------------------------------------


def test_the_stream_has_the_agreed_name_and_columns():
    assert POINTER_STREAM_FILENAME == "pointer_stream.csv"
    assert POINTER_STREAM_COLUMNS == ["t_ns", "x", "y", "valid"]


def test_the_header_is_written_at_once_and_each_sample_is_a_row(tmp_path):
    with recorder_in(tmp_path, meta()) as recorder:
        recorder.open_pointer_stream()
        path = recorder.session_dir / POINTER_STREAM_FILENAME
        assert path.exists()  # even if no frame is ever recorded
        recorder.record_pointer(sample(10, 0.123456789, 0.5))
        recorder.record_pointer(sample(20, -0.2, 1.1, valid=False))  # the mouse left the canvas
    got = rows(path)
    assert [(r["t_ns"], r["x"], r["y"], r["valid"]) for r in got] == [
        ("10", "0.12346", "0.5", "1"),
        ("20", "-0.2", "1.1", "0"),
    ]


def test_a_long_stream_is_flushed_as_it_goes(tmp_path):
    recorder = recorder_in(tmp_path, meta())
    recorder.open()
    recorder.open_pointer_stream()
    for i in range(130):
        recorder.record_pointer(sample(i))
    # Two flushes of 60 happened before the run ended: a crash would leave at least that.
    on_disk = (recorder.session_dir / POINTER_STREAM_FILENAME).read_text(encoding="utf-8")
    assert len(on_disk.splitlines()) >= 1 + 120
    recorder.close()
    assert len(rows(recorder.session_dir / POINTER_STREAM_FILENAME)) == 130


def test_without_the_stream_opened_recording_a_pointer_does_nothing(tmp_path):
    with recorder_in(tmp_path, meta()) as recorder:
        recorder.record_pointer(sample(1))
    assert not (tmp_path / "mouse_run" / POINTER_STREAM_FILENAME).exists()


def test_opening_the_stream_twice_keeps_one_file(tmp_path):
    with recorder_in(tmp_path, meta()) as recorder:
        recorder.open_pointer_stream()
        recorder.record_pointer(sample(1))
        recorder.open_pointer_stream()  # not reopened (which would empty it)
        recorder.record_pointer(sample(2))
    assert [r["t_ns"] for r in rows(tmp_path / "mouse_run" / POINTER_STREAM_FILENAME)] == ["1", "2"]


# -- no gaze file without a tracker ---------------------------------------------------------------------


def test_the_gaze_stream_is_still_opened_by_default(tmp_path):
    with recorder_in(tmp_path, meta()) as recorder:
        recorder.record_gaze(sample(1))
    assert len(rows(tmp_path / "mouse_run" / "gaze_stream.csv")) == 1


def test_a_run_with_no_tracker_creates_no_gaze_stream(tmp_path):
    recorder = recorder_in(tmp_path, meta("none"))
    recorder.open(gaze_stream=False)
    recorder.open_pointer_stream()
    recorder.record_pointer(sample(1))
    with pytest.raises(RuntimeError):
        recorder.record_gaze(sample(1))
    recorder.close()
    names = {p.name for p in (tmp_path / "none").iterdir()}
    assert "gaze_stream.csv" not in names
    assert {"pointer_stream.csv", "events.jsonl", "session.log", "metadata.json"} <= names


def test_the_null_recorder_has_the_new_surface():
    null = NullRecorder()
    null.open(gaze_stream=False)
    null.open_pointer_stream()
    assert null.record_pointer(sample(1)) is None


# -- the new fields ---------------------------------------------------------------------------------------


def test_the_new_metadata_fields_default_to_none_and_are_written(tmp_path):
    m = meta()
    assert (m.input_pointer, m.input_selection, m.gaze_recorded) == (None, None, None)
    m.input_pointer, m.input_selection, m.gaze_recorded, m.input_mode = "mouse", None, False, "mouse_follow"
    with recorder_in(tmp_path, m):
        pass
    written = json.loads((tmp_path / "mouse_run" / "metadata.json").read_text(encoding="utf-8"))
    assert (written["input_pointer"], written["input_selection"], written["gaze_recorded"]) == (
        "mouse", None, False,
    )
    assert written["input_mode"] == "mouse_follow"
    assert written["schema_version"] == 1  # additive: the version is not bumped


def test_a_trial_has_no_clicks_unless_it_counted_some():
    trial = TrialRecord(0, "click_grid", 0.5, 0.5, 90.0, 0)
    assert (trial.clicks, trial.click_errors) == (0, 0)
    assert trial.as_row()["clicks"] == 0 and trial.as_row()["click_errors"] == 0
    trial.clicks, trial.click_errors = 3, 2
    assert (trial.as_row()["clicks"], trial.as_row()["click_errors"]) == (3, 2)
    assert list(trial.as_row()) == TrialRecord.csv_header()


# -- the bar and the stand-in -------------------------------------------------------------------------------


def test_a_mouse_run_names_its_pointer_in_the_status():
    assert run_status(2, 18, "Tracking OK").line == "Trial 2 of 18, Tracking OK"
    assert run_status(2, 18, "Tracking OK", mouse=True).line == "Trial 2 of 18, Mouse pointer, Tracking OK"
    assert run_status(2, 18, "", mouse=True).line == "Trial 2 of 18, Mouse pointer"  # no tracker
    assert run_status(2, 18, "", mouse=True, practice=True).line == "PRACTICE, Trial 2 of 18, Mouse pointer"
    assert run_status(2, 18, "x", mouse=True, paused=True).line == "Paused, Trial 2 of 18"
    # A preview always names the mouse; its chip says nothing is recorded.
    assert run_status(1, 3, "", preview=True, mouse=True).line == "PREVIEW, Trial 1 of 3, Mouse pointer"


def test_no_tracker_reports_nothing():
    none = NoTracker()
    assert none.latest() is None and none.is_connected() is False
    assert none.device_info is None and none.is_live is False
    assert none.drain_raw() == []
    for call in (none.start_streaming, none.stop, none.clear_raw, none.connect):
        assert call() is None
