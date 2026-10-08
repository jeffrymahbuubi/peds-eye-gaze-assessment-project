"""SPEC-compass-task-flow.md 4D.6 / 4D.9 / 4D.10 G10: building and caching the report,
degrading on an old folder, and the dev CLI."""

from __future__ import annotations

import json
import logging

import pytest

import src.data.report_cache as cache
from src.data.report_cache import (
    REPORT_FILENAME,
    REPORT_VERSION,
    ReportError,
    build_report,
    load_or_build_report,
    main,
    report_json,
    summary_text,
    write_report,
    write_report_safely,
)
from tests.report_fixtures import (
    OFFSET_NS,
    RIG_META,
    SEC,
    T0,
    frames_between,
    raw_samples,
    record,
    write_session,
)

OLD_COLUMNS_ONLY = {
    "subject_id": "OLD", "session_id": "2026-09-11_OLD_click_grid_run1", "started_ns": T0,
    "tasks": ["click_grid"], "calibration_error_px": 20.0,
    "settings": {"live": {"task.inter_trial_interval_ms": 800}, "structural": {}},
}


def records3():
    return [
        record(0, T0 + 1 * SEC, "hit", dur_s=1.0, entries=1),
        record(1, T0 + 4 * SEC, "timeout", dur_s=2.0, first_gaze_s=None, entries=0, attempts=0),
        record(2, T0 + 8 * SEC, "hit", dur_s=1.5, entries=2),
    ]


def full_folder(tmp_path, **meta_extra):
    meta = dict(RIG_META, raw_clock_offset_ns=OFFSET_NS, planned_trials=3, completed_trials=3,
                outcome="completed", test_name="Grid 1", **meta_extra)
    frames = []
    for i in (1, 4, 8):
        frames += frames_between(T0 + i * SEC - 500_000_000, T0 + (i + 3) * SEC, canvas_xy=(0.4, 0.4))
    seen, unique = set(), []
    for f in frames:
        if f.t_ns not in seen:
            seen.add(f.t_ns)
            unique.append(f)
    return write_session(
        tmp_path / "run", records3(), meta=meta, frames=sorted(unique),
        samples=raw_samples(14.0, lambda t: 3.5),
    )


# -- the report of a full folder ---------------------------------------------------------


def test_a_full_folder_gives_every_block(tmp_path):
    report = build_report(full_folder(tmp_path))
    assert report["report_version"] == REPORT_VERSION
    assert set(report) == {
        "report_version", "params", "session", "geometry", "config", "trials", "follow",
        "summary", "map", "heat", "quality",
    }
    assert report["follow"] is None  # not a Follow the Target folder
    assert set(report["params"]) == {"ivt", "entries", "pupil", "heat", "path"}
    assert report["params"]["ivt"]["threshold_deg_s"] == 50.0
    assert report["params"]["entries"] == {"exit_hold_ms": 120.0}
    s = report["session"]
    assert (s["task_id"], s["subject"], s["test_name"], s["outcome"]) == (
        "click_grid", "P001", "Grid 1", "completed"
    )
    assert (s["planned_trials"], s["completed_trials"], s["n_rows"], s["n_scored"]) == (3, 3, 3, 3)
    assert (s["n_skipped"], s["n_not_presented"]) == (0, 0)
    assert all(s["sources"].values()) is False  # no target_track, no layout_slots, ...
    assert s["sources"]["raw_gaze"] and s["sources"]["entries"] and s["sources"]["saccades"]
    assert [t["outcome"] for t in report["trials"]] == ["hit", "timeout", "hit"]
    assert len(report["config"]["rows"]) == 17
    assert report["geometry"]["canvas_aspect"] == round(1640 / 957, 5)
    assert report["geometry"]["assumed_for_visuals"] is False
    assert report["map"]["aspect"] == round(1640 / 957, 5)
    assert len(report["map"]["marks"]) >= 1
    assert report["heat"]["empty"] is False and len(report["heat"]["data"]) == 96 * 54
    assert report["quality"]["warnings"] == []
    assert report["summary"]["rows"][1]["pct_n"] == "66.7% (2/3)"
    first = report["trials"][0]
    assert first["pupil"]["baseline_mm"] == pytest.approx(3.5)  # the pre-roll is on file
    assert first["fixations"]["count"] >= 1 and first["path"]


def test_the_map_carries_the_hit_tolerance_of_the_run(tmp_path):
    """P7c 9 (2): the Target Map's dashed ring uses the run's jitter tolerance, not a fixed 40 px."""
    settings = {"live": {"dwell.jitter_tolerance_px": 25}, "structural": {}}
    assert build_report(full_folder(tmp_path, settings=settings))["map"]["hit_tolerance_px"] == 25
    bare = {"live": {}, "structural": {}}
    assert build_report(full_folder(tmp_path / "b", settings=bare))["map"]["hit_tolerance_px"] is None


def test_g10_building_twice_gives_byte_identical_json(tmp_path):
    folder = full_folder(tmp_path)
    assert report_json(build_report(folder)) == report_json(build_report(folder))


def test_the_written_report_is_exactly_what_a_rebuild_gives(tmp_path):
    folder = full_folder(tmp_path)
    path = write_report(folder)
    assert path.name == REPORT_FILENAME
    assert path.read_text(encoding="utf-8") == report_json(build_report(folder))
    assert not list(folder.glob("*.tmp"))  # written whole, via a temp file that is gone


def test_the_json_is_compact_and_keeps_unicode(tmp_path):
    text = report_json(build_report(full_folder(tmp_path)))
    assert text == json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
    assert len(text.splitlines()) == 1
    assert "Gaze (GP3HD, 150 Hz), Dwell 0.8 s" in text and "5°" in text  # not \u escaped


# -- the cache -------------------------------------------------------------------------------


def test_a_current_cache_is_returned_without_rebuilding(tmp_path):
    folder = full_folder(tmp_path)
    write_report(folder)
    path = folder / REPORT_FILENAME
    tagged = json.loads(path.read_text(encoding="utf-8"))
    tagged["marker"] = "from the cache"
    path.write_text(json.dumps(tagged), encoding="utf-8")
    assert load_or_build_report(folder)["marker"] == "from the cache"


def test_a_missing_cache_is_built_and_written(tmp_path):
    folder = full_folder(tmp_path)
    report = load_or_build_report(folder)
    assert (folder / REPORT_FILENAME).read_text(encoding="utf-8") == report_json(report)


def test_g10_a_version_bump_triggers_a_rebuild(tmp_path, monkeypatch):
    folder = full_folder(tmp_path)
    write_report(folder)
    path = folder / REPORT_FILENAME
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["marker"] = "stale"
    path.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr(cache, "REPORT_VERSION", REPORT_VERSION + 1)
    fresh = load_or_build_report(folder)
    assert "marker" not in fresh and fresh["report_version"] == REPORT_VERSION + 1
    assert json.loads(path.read_text(encoding="utf-8"))["report_version"] == REPORT_VERSION + 1


@pytest.mark.parametrize("garbage", ["", "{not json", "[]", "null", "42", '{"report_version": 1'])
def test_an_unreadable_or_foreign_cache_is_rebuilt(tmp_path, garbage):
    folder = full_folder(tmp_path)
    (folder / REPORT_FILENAME).write_text(garbage, encoding="utf-8")
    assert load_or_build_report(folder)["report_version"] == REPORT_VERSION
    assert json.loads((folder / REPORT_FILENAME).read_text(encoding="utf-8"))["trials"]


def test_a_folder_that_cannot_be_written_still_gets_its_report(tmp_path, monkeypatch, caplog):
    folder = full_folder(tmp_path)

    def refuse(*a, **k):
        raise PermissionError("read-only")

    monkeypatch.setattr(cache, "write_report", refuse)
    with caplog.at_level(logging.WARNING):
        assert load_or_build_report(folder)["trials"]
    assert "not cached" in caplog.text


def test_closing_a_run_never_fails_because_the_report_could_not_be_built(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert write_report_safely(tmp_path / "no_such_folder") is None
    assert "report.json not written" in caplog.text
    assert write_report_safely(full_folder(tmp_path)) is not None


def test_a_folder_without_trials_csv_is_a_report_error(tmp_path):
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ReportError):
        build_report(tmp_path)
    assert issubclass(ReportError, ValueError)


# -- G10: an old folder, a partial run -------------------------------------------------------------


def test_g10_a_legacy_folder_degrades_to_none_without_an_exception(tmp_path):
    folder = write_session(tmp_path / "old", records3(), meta=OLD_COLUMNS_ONLY, legacy=True)
    report = build_report(folder)
    s = report["session"]
    assert s["sources"] == {
        "gaze_stream": False, "raw_gaze": False, "saccades": False, "geometry": False,
        "entries": False, "end_positions": False, "slot_index": False, "target_track": False,
        "layout_slots": False, "pointer_stream": False,
    }
    # An old folder has no input facts: nothing says gaze was not recorded.
    assert (s["pointer"], s["selection"], s["gaze_recorded"]) == (None, None, None)
    assert s["planned_trials"] is None and s["n_not_presented"] is None and s["outcome"] is None
    for t in report["trials"]:
        assert t["entries"] is None and t["error_free"] is None and t["size_deg"] is None
        assert t["distance_deg"] is None and t["fixations"]["count"] is None
        assert t["saccades"]["count"] is None and t["pupil"]["mean_mm"] is None
        assert t["path"] == []
    rows = {r["key"]: r for r in report["summary"]["rows"]}
    assert rows["error_free"]["pct_n"] == "—" and rows["all_selected"]["pct_n"] == "66.7% (2/3)"
    assert rows["all_selected"]["entries"] is None
    assert report["heat"]["empty"] and report["heat"]["off_canvas_share"] is None
    assert report["map"]["aspect"] is None and report["geometry"]["assumed_for_visuals"] is True
    assert report["quality"]["warnings"] == [] and report["quality"]["valid_share"] is None
    assert len(report["config"]["rows"]) == 17
    # The whole thing is still plain JSON.
    assert json.loads(report_json(report)) == report


def test_a_legacy_folder_with_gaze_stream_still_gets_fixations_path_and_heat(tmp_path):
    meta = dict(RIG_META, session_id="x")
    meta.pop("target_size")
    meta.pop("canvas_units")
    frames = frames_between(T0 + 1 * SEC, T0 + 10 * SEC, canvas_xy=(0.4, 0.4))
    folder = write_session(tmp_path / "old", records3(), meta=meta, frames=frames, legacy=True)
    report = build_report(folder)
    assert report["session"]["sources"]["gaze_stream"] and not report["session"]["sources"]["raw_gaze"]
    first = report["trials"][0]
    assert first["fixations"]["count"] >= 1 and first["path"] and first["size_deg"] is None
    assert first["saccades"]["count"] is None and first["pupil"]["mean_mm"] is None
    assert report["heat"]["empty"] is False


def test_g10_a_partial_run_carries_the_banner_flag(tmp_path):
    meta = dict(RIG_META, planned_trials=6, completed_trials=3, outcome="ended_early",
                skipped_trials=0)
    folder = write_session(tmp_path / "p", records3(), meta=meta)
    report = build_report(folder)
    assert report["quality"]["warnings"][0] == {
        "code": "ended_early", "text": "Ended early: 3 of 6 trials"
    }
    s = report["session"]
    assert (s["planned_trials"], s["n_rows"], s["n_not_presented"]) == (6, 3, 3)


def test_a_skipped_trial_is_counted_but_not_scored(tmp_path):
    recs = records3() + [record(3, T0 + 12 * SEC, "skipped", dur_s=1.0, entries=0)]
    report = build_report(write_session(tmp_path / "s", recs))
    s = report["session"]
    assert (s["n_rows"], s["n_scored"], s["n_skipped"]) == (4, 3, 1)
    assert all(r["N"] == 3 for r in report["summary"]["rows"])


def test_events_drive_the_resize_warning_and_the_capped_target_row(tmp_path):
    events = [
        {"t_ns": T0, "kind": "TARGET_SHRUNK", "requested_px": 165.6, "used_px": 53.3},
        {"t_ns": T0 + SEC, "kind": "CANVAS_RESIZED", "canvas_w": 1900, "canvas_h": 1000},
    ]
    folder = write_session(tmp_path / "e", records3(), events=events)
    (folder / "events.jsonl").write_text(
        (folder / "events.jsonl").read_text(encoding="utf-8") + "{truncated\n", encoding="utf-8"
    )  # a crash can cut the last line
    report = build_report(folder)
    assert [w["code"] for w in report["quality"]["warnings"]] == ["canvas_resized"]
    assert dict(report["config"]["rows"])["Target size"].endswith("capped to 53 px to fit")


def test_a_garbage_metadata_file_does_not_stop_the_report(tmp_path):
    folder = write_session(tmp_path / "g", records3())
    (folder / "metadata.json").write_text("{broken", encoding="utf-8")
    report = build_report(folder)
    assert report["session"]["subject"] is None and len(report["trials"]) == 3
    (folder / "metadata.json").write_text("[1, 2]", encoding="utf-8")
    assert len(build_report(folder)["trials"]) == 3


def test_an_empty_trials_table_gives_an_empty_report(tmp_path):
    report = build_report(write_session(tmp_path / "z", []))
    assert report["trials"] == [] and report["map"]["marks"] == []
    assert [r["pct_n"] for r in report["summary"]["rows"]] == ["0% (0/0)"] * 4
    assert report["session"]["n_rows"] == 0


def test_ad9_a_follow_moving_report_marks_the_end_position_and_carries_the_track(tmp_path):
    recs = [
        record(0, T0 + 1 * SEC, x=0.1, y=0.1, end_xy=(0.7, 0.4), task="follow_moving"),
        record(1, T0 + 5 * SEC, x=0.9, y=0.1, end_xy=(0.2, 0.8), task="follow_moving"),
    ]
    track = [(T0 + 1 * SEC + 50_000_000, 0, 0.1, 0.1), (T0 + 1 * SEC + 600_000_000, 0, 0.5, 0.3),
             (T0 + 5 * SEC + 50_000_000, 1, 0.9, 0.1)]
    meta = dict(RIG_META, tasks=["follow_moving"])
    folder = write_session(tmp_path / "f", recs, meta=meta, track=track)
    report = build_report(folder)
    assert report["session"]["sources"]["target_track"] is True
    marks = report["map"]["marks"]
    assert [(m["x"], m["y"]) for m in marks] == [(0.7, 0.4), (0.2, 0.8)]
    assert report["map"]["note"] is None
    assert report["trials"][0]["track"] == [[0.1, 0.1], [0.5, 0.3]]
    assert [t["distance_deg"] for t in report["trials"]] == [None, None]
    # The same task from a folder without end positions: start marks, with a note.
    old = build_report(write_session(tmp_path / "f2", recs, meta=meta, legacy=True))
    assert [(m["x"], m["y"]) for m in old["map"]["marks"]] == [(0.1, 0.1), (0.9, 0.1)]
    assert "start position" in old["map"]["note"]


def test_layout_slots_reach_the_map(tmp_path):
    meta = dict(RIG_META, layout_slots=[[0.2, 0.2], [0.5, 0.5]])
    report = build_report(write_session(tmp_path / "l", records3(), meta=meta))
    assert report["map"]["slots"] == [[0.2, 0.2], [0.5, 0.5]]
    assert report["session"]["sources"]["layout_slots"] is True


# -- the CLI ---------------------------------------------------------------------------------------


def test_the_cli_prints_the_json_and_writes_nothing_by_default(tmp_path, capsys):
    folder = full_folder(tmp_path)
    assert main([str(folder)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_version"] == REPORT_VERSION and len(printed["trials"]) == 3
    assert not (folder / REPORT_FILENAME).exists()  # read-only unless asked


def test_the_cli_can_write_summarize_and_pretty_print(tmp_path, capsys):
    folder = full_folder(tmp_path)
    assert main([str(folder), "--write", "--summary"]) == 0
    out = capsys.readouterr().out
    assert "summary of results:" in out and "All Targets Selected" in out and "66.7% (2/3)" in out
    assert (folder / REPORT_FILENAME).is_file()
    assert main([str(folder), "--indent"]) == 0
    assert capsys.readouterr().out.startswith("{\n  ")


def test_the_cli_reports_a_bad_folder_with_exit_code_2(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    assert "trials.csv" in capsys.readouterr().err


def test_the_summary_text_holds_the_headline_numbers(tmp_path):
    text = summary_text(build_report(full_folder(tmp_path)))
    assert "task=click_grid" in text and "sources:" in text and "heat:" in text
    assert text.count("hit") >= 2 and "timeout" in text
