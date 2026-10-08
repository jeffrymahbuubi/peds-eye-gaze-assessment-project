"""SPEC-audit-fixes.md H5 (F2, a recorder that survives a crash), H6 (F3, the metrics count a
sample once) and H11 (F9, the orphan folder helper).

The headline claim of H5 is that a normal run's files do not change: ``trials.csv`` and the
other files of a run are the bytes they always were, and ``metadata.json`` only gains the
``"complete"`` key.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from src.data.exporter import compute_fixation_saccade_metrics
from src.data.recorder import NullRecorder, SessionRecorder
from src.data.schema import GazeSample, SessionMetadata, TrialRecord
from src.engine.run_paths import new_run_dir
from src.engine.session_files import remove_orphan_run_dir
from src.engine.subject_store import ensure_subject
from src.engine.task_runner import run_headless_replay
from tests.recorder_helpers import recorder_in

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"


def meta() -> SessionMetadata:
    return SessionMetadata(subject_id="P001", session_id="S", started_ns=1000, tasks=["click_static"])


def trial(i: int, hit: bool = True) -> TrialRecord:
    return TrialRecord(i, "click_static", 0.5, 0.5, 90, i * 10, t_click_ns=i * 10 + 5, is_hit=hit, attempts=1)


def legacy_trials_csv(trials: list[TrialRecord]) -> bytes:
    """``trials.csv`` as ``write_trials`` always wrote it: the header, then every row."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=TrialRecord.csv_header())
    writer.writeheader()
    for item in trials:
        writer.writerow(item.as_row())
    return buffer.getvalue().encode("utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# -- open() leaves what a dead run needs ------------------------------------------------------------


def test_open_writes_metadata_marked_incomplete_and_the_trial_table_header(tmp_path):
    rec = recorder_in(tmp_path, meta())
    rec.open()
    folder = tmp_path / "S"
    data = read_json(folder / "metadata.json")
    assert data["complete"] is False and data["subject_id"] == "P001"
    assert (folder / "trials.csv").read_bytes() == legacy_trials_csv([])  # the header, no rows
    rec.close()


def test_each_trial_end_appends_a_row_and_pushes_the_files_to_disk(tmp_path):
    rec = recorder_in(tmp_path, meta())
    rec.open()
    folder = tmp_path / "S"
    for i in range(5):  # fewer than the 60 rows after which gaze_stream.csv flushes by itself
        rec.record_gaze(GazeSample(t_ns=i, x=0.5, y=0.5, valid=True))
    assert len(list(csv.DictReader((folder / "gaze_stream.csv").open(encoding="utf-8")))) == 0
    rec.record_trial(trial(0))
    rec.record_trial(trial(1, hit=False))
    # Nothing was closed: this is what a process killed here leaves behind.
    assert (folder / "trials.csv").read_bytes() == legacy_trials_csv([trial(0), trial(1, hit=False)])
    assert len(list(csv.DictReader((folder / "gaze_stream.csv").open(encoding="utf-8")))) == 5
    assert read_json(folder / "metadata.json")["complete"] is False
    rec.close()


def test_a_recorder_that_was_never_opened_refuses_a_trial(tmp_path):
    with pytest.raises(RuntimeError):
        recorder_in(tmp_path, meta()).record_trial(trial(0))


# -- a normal run's files do not change ---------------------------------------------------------------


def test_close_marks_the_metadata_complete_and_the_final_trial_table_is_the_legacy_one(tmp_path):
    trials = [trial(0), trial(1, hit=False), trial(2)]
    with recorder_in(tmp_path, meta()) as rec:
        for item in trials:
            rec.record_trial(item)
        rec.write_trials(trials)
    folder = tmp_path / "S"
    assert (folder / "trials.csv").read_bytes() == legacy_trials_csv(trials)
    final = read_json(folder / "metadata.json")
    assert final.pop("complete") is True
    assert final == meta().to_dict()  # nothing else about the file moved


def test_the_final_trial_table_is_the_same_with_or_without_the_appended_rows(tmp_path):
    trials = [trial(0), trial(1)]
    with recorder_in(tmp_path / "a", meta()) as rec:
        for item in trials:
            rec.record_trial(item)
        rec.write_trials(trials)
    with recorder_in(tmp_path / "b", meta()) as rec:
        rec.write_trials(trials)  # the way it was before
    assert (tmp_path / "a" / "S" / "trials.csv").read_bytes() == (tmp_path / "b" / "S" / "trials.csv").read_bytes()


def test_a_metadata_write_without_complete_is_the_old_file(tmp_path):
    rec = recorder_in(tmp_path, meta())
    rec.open()
    path = rec.write_metadata()
    assert "complete" not in read_json(path)
    rec.close()


def test_a_headless_run_leaves_the_same_folder_as_before(tmp_path, monkeypatch):
    """The whole folder of a deterministic headless run, new recorder against the recorder as it
    was (no rows appended, no ``complete`` key): every file the same, byte for byte."""

    def run(root: Path) -> Path:
        result = run_headless_replay(
            "click_static", FIXTURE, output_root=root, session_id="same", max_seconds=30.0
        )
        return Path(result["session_dir"])

    new_dir = run(tmp_path / "new")

    original_write_metadata = SessionRecorder.write_metadata
    monkeypatch.setattr(SessionRecorder, "record_trial", lambda self, trial: None)
    monkeypatch.setattr(
        SessionRecorder, "write_metadata", lambda self, complete=None: original_write_metadata(self)
    )
    old_dir = run(tmp_path / "old")

    names = sorted(p.name for p in new_dir.iterdir())
    assert names == sorted(p.name for p in old_dir.iterdir())
    assert {"trials.csv", "gaze_stream.csv", "events.jsonl", "metadata.json"} <= set(names)
    for name in names:
        new_bytes = (new_dir / name).read_bytes().replace(str(new_dir).encode(), b"<dir>")
        old_bytes = (old_dir / name).read_bytes().replace(str(old_dir).encode(), b"<dir>")
        if name == "metadata.json":
            new_meta, old_meta = json.loads(new_bytes), json.loads(old_bytes)
            assert new_meta.pop("complete") is True and "complete" not in old_meta
            assert new_meta == old_meta
        else:
            assert new_bytes == old_bytes, name


# -- the null recorder keeps the surface ------------------------------------------------------------------


def test_the_null_recorder_takes_the_new_calls():
    rec = NullRecorder()
    assert rec.record_trial(trial(0)) is None
    assert rec.write_metadata(complete=True) is None and rec.write_metadata() is None


# -- H6: a sample counts once in the metrics -----------------------------------------------------------------


def gaze_run(tmp_path: Path, name: str, stamps: list[int]) -> Path:
    with recorder_in(tmp_path / name, meta()) as rec:
        for stamp in stamps:
            rec.record_gaze(GazeSample(t_ns=stamp * 10**7, x=0.5, y=0.5, valid=True, fixation_id=1, fix_duration_s=0.1))
    return tmp_path / name / "S"


def test_the_fixation_metrics_count_each_stamp_once(tmp_path):
    real = list(range(150))
    once = compute_fixation_saccade_metrics(gaze_run(tmp_path, "once", real))
    stale = compute_fixation_saccade_metrics(gaze_run(tmp_path, "stale", real + [real[-1]] * 1500))
    assert once["n_samples"] == 150
    assert stale == once  # the audit's 1650 rows with 1500 repeats: the same numbers


# -- H11: the orphan folder helper ------------------------------------------------------------------------


def make_run(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "sessions"
    return root, new_run_dir(root, "P001", "click_grid")


def test_a_run_folder_holding_only_its_calibration_is_removed(tmp_path):
    root, run = make_run(tmp_path)
    (run / "calibration.json").write_text("{}", encoding="utf-8")
    assert remove_orphan_run_dir(run, root) is True
    assert not run.exists()
    assert (root / "P001").is_dir()  # the subject's folder stays


def test_an_empty_run_folder_is_removed_too(tmp_path):
    root, run = make_run(tmp_path)
    assert remove_orphan_run_dir(run, root) is True and not run.exists()


def test_a_run_folder_with_anything_else_in_it_is_never_touched(tmp_path):
    root, run = make_run(tmp_path)
    (run / "calibration.json").write_text("{}", encoding="utf-8")
    (run / "events.jsonl").write_text("{}", encoding="utf-8")
    assert remove_orphan_run_dir(run, root) is False
    assert (run / "calibration.json").is_file() and (run / "events.jsonl").is_file()


def test_a_folder_that_is_not_a_run_folder_is_never_touched(tmp_path):
    root = tmp_path / "sessions"
    ensure_subject(root, "P001")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "calibration.json").write_text("{}", encoding="utf-8")
    assert remove_orphan_run_dir(elsewhere, root) is False and elsewhere.is_dir()
    assert remove_orphan_run_dir(root / "P001", root) is False and (root / "P001").is_dir()
    assert remove_orphan_run_dir(None, root) is False
    assert remove_orphan_run_dir(tmp_path / "missing", root) is False
