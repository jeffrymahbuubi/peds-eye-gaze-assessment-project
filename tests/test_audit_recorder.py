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
import os
from pathlib import Path

import pytest

from src.data.exporter import compute_fixation_saccade_metrics
from src.data.recorder import RECORDER_FILENAMES, NullRecorder, SessionRecorder
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
    """Without a list of names the start wrote, the calibration is the only file allowed."""
    root, run = make_run(tmp_path)
    (run / "calibration.json").write_text("{}", encoding="utf-8")
    (run / "events.jsonl").write_text("{}", encoding="utf-8")
    assert remove_orphan_run_dir(run, root) is False
    assert (run / "calibration.json").is_file() and (run / "events.jsonl").is_file()


def test_a_run_folder_holding_the_recorders_files_is_removed_when_they_are_named(tmp_path):
    root, run = make_run(tmp_path)
    (run / "calibration.json").write_text("{}", encoding="utf-8")
    for name in sorted(RECORDER_FILENAMES):
        (run / name).write_text("x", encoding="utf-8")
    assert remove_orphan_run_dir(run, root, RECORDER_FILENAMES) is True
    assert not run.exists() and (root / "P001").is_dir()


def test_one_foreign_file_keeps_the_whole_folder(tmp_path):
    root, run = make_run(tmp_path)
    for name in ("calibration.json", "events.jsonl", "trials.csv", "report.pdf"):
        (run / name).write_text("x", encoding="utf-8")
    assert remove_orphan_run_dir(run, root, RECORDER_FILENAMES) is False
    assert sorted(p.name for p in run.iterdir()) == ["calibration.json", "events.jsonl", "report.pdf", "trials.csv"]


def test_a_subfolder_with_a_known_name_keeps_the_folder(tmp_path):
    root, run = make_run(tmp_path)
    (run / "events.jsonl").write_text("x", encoding="utf-8")
    (run / "trials.csv").mkdir()  # a known name, but not a regular file
    (run / "trials.csv" / "inner.txt").write_text("x", encoding="utf-8")
    assert remove_orphan_run_dir(run, root, RECORDER_FILENAMES) is False
    assert (run / "events.jsonl").is_file() and (run / "trials.csv" / "inner.txt").is_file()


@pytest.mark.parametrize("linked", ["events.jsonl", "calibration.json"])
def test_a_link_with_a_known_name_keeps_the_folder(tmp_path, monkeypatch, linked):
    """The link check is simulated, so this also runs where symlinks need a privilege."""
    from src.engine import session_files

    root, run = make_run(tmp_path)
    for name in ("calibration.json", "events.jsonl"):
        (run / name).write_text("x", encoding="utf-8")
    real = session_files._is_link
    monkeypatch.setattr(session_files, "_is_link", lambda p: p.name == linked or real(p))
    assert remove_orphan_run_dir(run, root, RECORDER_FILENAMES) is False
    assert (run / "calibration.json").is_file() and (run / "events.jsonl").is_file()


def test_a_real_symlink_with_a_known_name_keeps_the_folder_and_its_target(tmp_path):
    root, run = make_run(tmp_path)
    target = tmp_path / "precious.txt"
    target.write_text("keep me", encoding="utf-8")
    try:
        os.symlink(target, run / "events.jsonl")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this machine")
    assert remove_orphan_run_dir(run, root, RECORDER_FILENAMES) is False
    assert target.read_text(encoding="utf-8") == "keep me"


def test_a_folder_that_is_not_a_run_folder_is_never_touched(tmp_path):
    root = tmp_path / "sessions"
    ensure_subject(root, "P001")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "calibration.json").write_text("{}", encoding="utf-8")
    assert remove_orphan_run_dir(elsewhere, root) is False and elsewhere.is_dir()
    assert remove_orphan_run_dir(root / "P001", root) is False and (root / "P001").is_dir()
    assert remove_orphan_run_dir(None, root, RECORDER_FILENAMES) is False
    assert remove_orphan_run_dir(tmp_path / "missing", root, RECORDER_FILENAMES) is False


# -- H11: the recorder's side of the orphan cleanup --------------------------------------------------------


def test_the_recorders_file_names_are_every_file_it_can_make(tmp_path):
    """RECORDER_FILENAMES is what the cleanup trusts: open every optional file and compare."""
    rec = recorder_in(tmp_path, meta())
    rec.open()
    rec.open_all_gaze("click_static", 120)
    rec.open_eye_geometry()
    rec.open_pointer_stream()
    rec.record_target_track(1, 0, 0.5, 0.5)
    rec.write_trials([trial(0)])
    rec.close()
    assert {p.name for p in (tmp_path / "S").iterdir()} == RECORDER_FILENAMES


def test_abort_releases_every_file_and_writes_nothing_more(tmp_path):
    rec = recorder_in(tmp_path, meta())
    rec.open()
    rec.open_all_gaze("click_static", 120)
    rec.open_eye_geometry()
    rec.open_pointer_stream()
    rec.record_target_track(1, 0, 0.5, 0.5)
    folder = tmp_path / "S"
    names = {p.name for p in folder.iterdir()}
    metadata = (folder / "metadata.json").read_bytes()
    rec.abort()  # closing flushes what was buffered; it creates and rewrites nothing
    assert {p.name for p in folder.iterdir()} == names
    assert (folder / "metadata.json").read_bytes() == metadata
    assert read_json(folder / "metadata.json")["complete"] is False  # never marked finished
    rec.close()  # nothing left to do once aborted
    assert read_json(folder / "metadata.json")["complete"] is False
    for entry in folder.iterdir():
        entry.unlink()  # no handle is held (Windows refuses to delete an open file)
    folder.rmdir()


def test_abort_copes_with_a_recorder_that_was_never_opened_or_died_in_open(tmp_path, monkeypatch):
    recorder_in(tmp_path / "never", meta()).abort()
    rec = recorder_in(tmp_path / "died", meta())
    monkeypatch.setattr(SessionRecorder, "write_metadata", lambda self, complete=None: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        rec.open()  # gaze_stream.csv, events.jsonl and session.log are open, trials.csv is not
    rec.abort()
    for entry in (tmp_path / "died" / "S").iterdir():
        entry.unlink()


def test_the_recorder_counts_the_trials_it_appended(tmp_path):
    rec = recorder_in(tmp_path, meta())
    assert rec.trials_recorded == 0
    rec.open()
    assert rec.trials_recorded == 0
    rec.record_trial(trial(0))
    rec.record_trial(trial(1))
    assert rec.trials_recorded == 2
    rec.close()


def test_the_null_recorder_has_the_abort_surface():
    rec = NullRecorder()
    assert rec.abort() is None and rec.trials_recorded == 0
