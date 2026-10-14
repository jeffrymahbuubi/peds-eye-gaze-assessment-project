"""SPEC-scanning-search-cues.md 4.6, acceptance C7: the per-trial fields and the new events of Scanning
Search reach ``trials.csv`` and ``events.jsonl`` through a real recorder, and ``docs/DATA_SCHEMA.md`` says
what they are."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.data.schema import LOOKBACK_COLUMNS, SCANNING_COLUMNS, SessionMetadata, TrialRecord
from src.inputs.base import Pointer
from src.tasks.base_task import Phase
from src.tasks.search_cues import SHAPE_NAMES
from tests.recorder_helpers import recorder_in
from tests.test_scanning_search import CENTRE, MS, at_slot, make, run

DOCS = Path(__file__).resolve().parent.parent / "docs" / "DATA_SCHEMA.md"
NEW_EVENTS = ("START_DOT_SHOWN", "START_DOT_DONE", "SAMPLE_START", "FIELD_SHOWN", "WRONG_SELECTION")


def run_recorded(tmp_path, **kwargs):
    """A whole run of a task on a real recorder: look at the target through every field."""
    kwargs.setdefault("trials", 2)
    meta = SessionMetadata(subject_id="P001", session_id="scan", started_ns=0)
    with recorder_in(tmp_path, meta) as recorder:
        task, _spy, _fb = make(recorder=recorder, **kwargs)
        for t in range(0, 20000, 10):
            slot = task.targets[task._trial_index].slot_index if task.phase is Phase.WAIT_INPUT else None
            task.update(t * MS, at_slot(task, slot) if slot is not None else CENTRE)
            if task.is_done:
                break
        assert task.is_done
    folder = tmp_path / "scan"
    with (folder / "trials.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return task, rows, events


# -- the columns --------------------------------------------------------------------------------------------


def test_the_scanning_columns_sit_between_follows_and_choice_makings_and_choice_making_stays_last():
    header = TrialRecord.csv_header()
    start = header.index("mean_dist_px") + 1
    assert header[start : start + len(SCANNING_COLUMNS)] == list(SCANNING_COLUMNS)
    assert header[start + len(SCANNING_COLUMNS)] == "prompt_object"
    assert header[-len(LOOKBACK_COLUMNS) :] == list(LOOKBACK_COLUMNS)
    assert list(SCANNING_COLUMNS) == [
        "search_mode", "target_shape", "field_shapes", "start_dot_ms", "start_dot_timeout",
        "first_icon_looked_at_slot", "first_icon_looked_at_shape", "wrong_selections", "wrong_selection_shapes",
    ]
    assert list(TrialRecord(0, "t", 0.5, 0.5, 90, 0).as_row()) == header


def test_the_columns_are_blank_for_every_other_task():
    row = TrialRecord(0, "click_grid", 0.5, 0.5, 90.0, 0).as_row()
    assert [row[c] for c in SCANNING_COLUMNS] == [""] * len(SCANNING_COLUMNS)


# -- a Match the sample run with the start dot, written ------------------------------------------------------


def test_match_the_sample_with_the_start_dot_writes_its_fields_and_events(tmp_path):
    task, rows, events = run_recorded(tmp_path, mode="match_sample", start_dot=True, seed=3)
    assert len(rows) == 2
    for i, row in enumerate(rows):
        shapes = row["field_shapes"].split("|")
        assert row["search_mode"] == "match_sample"
        assert shapes == [SHAPE_NAMES[s] for s in task.trial_field_shapes[i]]
        assert row["target_shape"] == shapes[int(row["slot_index"])] == SHAPE_NAMES[task.trial_target_shapes[i]]
        assert shapes.count(row["target_shape"]) == 1
        assert (row["start_dot_ms"], row["start_dot_timeout"]) == ("300.0", "0")
        assert row["first_icon_looked_at_slot"] == row["slot_index"]
        assert row["first_icon_looked_at_shape"] == row["target_shape"]
        assert (row["wrong_selections"], row["wrong_selection_shapes"]) == ("0", "")  # a Dwell test: 0, not blank
        assert row["is_hit"] == "1"
    assert [e["kind"] for e in events if e["kind"] in NEW_EVENTS or e["kind"] == "TARGET_SHOWN"][:5] == [
        "START_DOT_SHOWN", "START_DOT_DONE", "SAMPLE_START", "TARGET_SHOWN", "FIELD_SHOWN",
    ]
    by_kind = {k: [e for e in events if e["kind"] == k] for k in NEW_EVENTS}
    assert [len(by_kind[k]) for k in NEW_EVENTS] == [2, 2, 2, 2, 0]
    assert by_kind["START_DOT_DONE"][0]["result"] == "fixated" and by_kind["START_DOT_DONE"][0]["elapsed_ms"] == 300.0
    sample = by_kind["SAMPLE_START"][1]
    assert (sample["trial"], sample["shape"]) == (1, rows[1]["target_shape"])
    assert (sample["duration_ms"], sample["duration_source"]) == (1500.0, "default")
    assert by_kind["FIELD_SHOWN"][0]["trial"] == 0


def test_wrong_selections_reach_trials_csv_and_events_jsonl(tmp_path):
    meta = SessionMetadata(subject_id="P001", session_id="scan", started_ns=0)
    with recorder_in(tmp_path, meta) as recorder:
        task, _spy, _fb = make(trials=1, recorder=recorder, seed=3)
        run(task, CENTRE, 0, 1510)
        target = task.targets[0].slot_index
        first, second = (target + 1) % 4, (target + 2) % 4
        run(task, at_slot(task, first), 1520, 1740)
        run(task, CENTRE, 1740, 1900)
        run(task, at_slot(task, second), 1900, 2120)
        run(task, at_slot(task, target), 2120, 2400)
    row = list(csv.DictReader((tmp_path / "scan" / "trials.csv").open(encoding="utf-8")))[0]
    events = [json.loads(x) for x in (tmp_path / "scan" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    names = [SHAPE_NAMES[task.trial_field_shapes[0][s]] for s in (first, second)]
    assert row["is_hit"] == "1" and row["wrong_selections"] == "2" and row["wrong_selection_shapes"] == ";".join(names)
    wrong = [e for e in events if e["kind"] == "WRONG_SELECTION"]
    assert [(e["trial"], e["slot"], e["shape"]) for e in wrong] == [(0, first, names[0]), (0, second, names[1])]
    assert all(e["t_ns"] > 0 for e in wrong)


def test_a_timed_out_dot_is_a_blank_time_and_a_one(tmp_path):
    meta = SessionMetadata(subject_id="P001", session_id="scan", started_ns=0)
    with recorder_in(tmp_path, meta) as recorder:
        task, _spy, _fb = make(trials=1, mode="pop_out", start_dot=True, recorder=recorder)
        elsewhere = Pointer(x=0.1, y=0.1, valid=True, clicked=False)  # never near the centre dot
        for t in range(0, 5100, 10):
            task.update(t * MS, elsewhere)
        for t in range(5100, 5400, 10):  # then look at the target
            task.update(t * MS, at_slot(task, task.targets[0].slot_index))
    rows = list(csv.DictReader((tmp_path / "scan" / "trials.csv").open(encoding="utf-8")))
    events = [json.loads(x) for x in (tmp_path / "scan" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    done = [e for e in events if e["kind"] == "START_DOT_DONE"][0]
    assert done["result"] == "timeout" and done["elapsed_ms"] == 5000.0
    assert (rows[0]["start_dot_ms"], rows[0]["start_dot_timeout"]) == ("", "1")


def test_pop_out_writes_its_shapes_and_no_new_events(tmp_path):
    task, rows, events = run_recorded(tmp_path, mode="pop_out", start_dot=False)
    assert all(r["search_mode"] == "pop_out" for r in rows)
    assert all(r["field_shapes"] == "circle|square|triangle|diamond" for r in rows)
    assert all(r["start_dot_ms"] == "" and r["start_dot_timeout"] == "" for r in rows)
    assert all(r["first_icon_looked_at_slot"] == "" and r["first_icon_looked_at_shape"] == "" for r in rows)
    assert not {e["kind"] for e in events} & set(NEW_EVENTS)
    assert {e["kind"] for e in events} <= {"TARGET_SHOWN", "HIT", "TIMEOUT", "TARGET_INSET", "TARGET_SHRUNK"}


# -- DATA_SCHEMA.md -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", [*SCANNING_COLUMNS, *NEW_EVENTS, "start_dot"])
def test_data_schema_documents_every_new_column_event_and_setting(name):
    assert f"`{name}`" in DOCS.read_text(encoding="utf-8")


def test_data_schema_says_the_ignored_press_phases_of_the_new_stages():
    text = DOCS.read_text(encoding="utf-8")
    assert "`start_dot`" in text and "`sample`" in text
