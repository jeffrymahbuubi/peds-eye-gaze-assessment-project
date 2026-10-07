"""SPEC-input-selection-and-follow.md 4.5, 4.6, H6-H8, H10, W2 (acceptance A6 on the data side,
A7 end to end, A8 for old sessions): the ``follow`` block of ``report.json`` built from a run
folder -- per-trial and whole-test figures, the pointer path split on / off target -- for a Gaze
run, a Mouse run with no tracker, a skipped trial and an old Follow & Click folder."""

from __future__ import annotations

import copy
import csv
import json

import pytest

from src.data.recorder import POINTER_STREAM_COLUMNS, POINTER_STREAM_FILENAME
from src.data.report_cache import REPORT_VERSION, build_report, load_or_build_report
from src.data.report_eye import GazeFrame
from src.ui.report_format import NOT_RECORDED, OUTCOME_LABELS, eye_rows, task_sentence
from tests.follow_fixtures import (
    FULL_CANVAS_META,
    OFFSET_NS,
    SEC,
    follow_record,
    horizontal,
    simulate_gaze,
    target_track_rows,
    write_track,
)
from tests.report_fixtures import write_session

TRIAL_S = 10.0
PERIOD_S = 12.0  # a trial and its pause
MM_PER_PX = 0.2745
FORTY_PX_DEG = 0.969  # 40 px * 0.2745 mm/px at 650 mm, as a visual angle


def onset(k: int) -> int:
    return OFFSET_NS + round(k * PERIOD_S * SEC)


def records():
    return [
        follow_record(0, onset(0), on_target_ms=7000.0, first_gaze_s=0.4),
        follow_record(1, onset(1), on_target_ms=8000.0, first_gaze_s=0.2),
        follow_record(2, onset(2), on_target_ms=3000.0, first_gaze_s=1.2, mean_dist_px=80.0),
    ]


def run_samples(gain=0.8):
    """One continuous gaze over three trials, the target restarting each time."""
    base = horizontal()

    def position(t):
        k = int(t // PERIOD_S)
        return base(min(t - k * PERIOD_S, TRIAL_S))

    samples, jumps = simulate_gaze(position, 2 * PERIOD_S + TRIAL_S, gain=gain, noise_deg=0.1)
    return samples, jumps


def path_frames(off_after_s=None, off_trial=2):
    """60 Hz gaze-stream frames on the target; in trial ``off_trial`` far from it after
    ``off_after_s``."""
    base = horizontal()
    frames = []
    for k in range(3):
        # A blink in the pause before each trial: the cursor's smoothing starts afresh.
        frames.append(GazeFrame(onset(k) - SEC, 0.5, 0.5, False, None, None))
        for i in range(int(TRIAL_S * 60) + 1):
            t = i / 60.0
            x, y = base(t)
            if off_after_s is not None and k == off_trial and t >= off_after_s:
                x += 0.3
            frames.append(GazeFrame(onset(k) + round(t * SEC), x, y, True, None, None))
    return frames


def folder(tmp_path, *, meta=None, recs=None, samples=True, frames=True, name="run"):
    base = horizontal()
    track = []
    for k in range(3):
        track.extend(target_track_rows(base, TRIAL_S, trial=k, origin_ns=onset(k)))
    meta = copy.deepcopy(FULL_CANVAS_META) if meta is None else meta
    out = write_session(
        tmp_path / name,
        recs or records(),
        meta=meta,
        frames=path_frames(off_after_s=5.0) if frames else None,
        samples=run_samples()[0] if samples else None,
        track=track,
    )
    return out


def follow_block(tmp_path, **kwargs):
    return build_report(folder(tmp_path, **kwargs))["follow"]


# -- the block --------------------------------------------------------------------------------------


def test_a_follow_folder_gives_the_follow_block_the_wireframes_need(tmp_path):
    report = build_report(folder(tmp_path))
    follow = report["follow"]
    assert follow["legacy"] is False and follow["gaze_available"] is True
    assert follow["params"] == {
        "max_err_deg": 3.0, "bounce_excl_ms": 100.0, "min_usable_s": 0.5, "followed_pct": 50.0,
        "window_ms": 100.0, "saccade_pad_samples": 1,
    }
    assert (follow["path"], follow["trial_duration_s"], follow["hitbox_margin_px"]) == (
        "horizontal", 10.0, 40.0,
    )
    assert [t["trial"] for t in follow["trials"]] == [1, 2, 3]


def test_each_trial_carries_the_columns_of_the_per_trial_table(tmp_path):
    follow = follow_block(tmp_path)
    t1, t2, t3 = follow["trials"]
    assert (t1["outcome"], t2["outcome"], t3["outcome"]) == ("followed", "followed", "not_followed")
    assert (t1["followed"], t3["followed"]) == (True, False)
    assert [t["duration_s"] for t in follow["trials"]] == [10.0, 10.0, 10.0]
    assert [t["time_on_target_pct"] for t in follow["trials"]] == [70.0, 80.0, 30.0]
    assert [t["valid_pct"] for t in follow["trials"]] == [100.0, 100.0, 100.0]
    assert [t["time_to_find_s"] for t in follow["trials"]] == [0.4, 0.2, 1.2]
    assert t1["mean_distance_px"] == 40.0
    assert t1["mean_distance_deg"] == pytest.approx(FORTY_PX_DEG, abs=0.005)
    assert t3["mean_distance_deg"] == pytest.approx(2 * FORTY_PX_DEG, abs=0.01)
    for t in follow["trials"]:
        assert t["pursuit_gain"] == pytest.approx(0.8, abs=0.06)
        assert t["gain_usable_s"] > 2.0
        assert t["catch_up_count"] > 0 and t["catch_up_per_s"] > 0


def test_the_whole_test_row_values_of_the_summary_table(tmp_path):
    summary = follow_block(tmp_path)["summary"]
    assert (summary["n_trials"], summary["followed"]) == (3, 2)
    assert summary["time_on_target_pct"] == {"mean": 60.0, "min": 30.0, "max": 80.0}
    assert summary["mean_distance_deg"] == pytest.approx((0.969 + 0.969 + 1.938) / 3, abs=0.01)
    assert summary["time_to_find_s"] == pytest.approx(0.6, abs=0.01)
    assert summary["pursuit_gain"] == pytest.approx(0.8, abs=0.06)  # the median
    assert summary["pursuit_gain_trials"] == 3
    assert summary["catch_up_per_s"] > 0.3
    assert summary["valid_pct"] == 100.0


def test_the_outcomes_of_the_trial_table_agree_with_the_follow_block(tmp_path):
    report = build_report(folder(tmp_path))
    assert [t["outcome"] for t in report["trials"]] == ["followed", "followed", "not_followed"]
    assert [t["outcome"] for t in report["follow"]["trials"]] == [t["outcome"] for t in report["trials"]]
    assert report["session"]["n_scored"] == 3 and report["session"]["n_skipped"] == 0
    assert {"followed", "not_followed"} <= set(OUTCOME_LABELS)
    # The eye figures are taken over the followed / not followed trials too (they were taken
    # only over hit / timeout ones before): the trial windows are read for these outcomes.
    assert all(t["path"] for t in report["trials"])
    assert report["quality"]["valid_share"] is not None


def test_the_configuration_rows_say_trial_duration_and_have_no_selection_row(tmp_path):
    rows = dict(build_report(folder(tmp_path))["config"]["rows"])
    assert "Trial duration" in rows and rows["Trial duration"] == "10 s"
    assert "Maximum time per trial" not in rows and "Selection" not in rows
    assert rows["Input"].startswith("Eye gaze, GP3HD") and "dwell" not in rows["Input"]
    assert rows["Task"] == "Follow the Target" and len(rows) == 16


def test_the_pointer_path_is_split_on_and_off_target(tmp_path):
    follow = follow_block(tmp_path)
    for trial in follow["trials"][:2]:  # followed all the way
        assert trial["pointer_path"] and all(seg["on"] is True for seg in trial["pointer_path"])
    third = follow["trials"][2]["pointer_path"]
    assert {seg["on"] for seg in third} == {True, False}  # on target, then 0.3 of the canvas away
    assert all(len(seg["pts"]) >= 2 for seg in third)
    assert all(0.0 <= x <= 1.3 and 0.0 <= y <= 1.0 for seg in third for x, y in seg["pts"])
    # The first stretch is on target, the last is off it.
    assert third[0]["on"] is True and third[-1]["on"] is False
    # A run opens with the last point of the one before it, so the line stays joined.
    for before, after in zip(third, third[1:], strict=False):
        if before["on"] != after["on"]:
            assert after["pts"][0] == before["pts"][-1]


def test_the_report_is_deterministic_and_round_trips_as_json(tmp_path):
    path = folder(tmp_path)
    first, second = build_report(path), build_report(path)
    assert first == second
    assert json.loads(json.dumps(first)) == first
    assert load_or_build_report(path)["report_version"] == REPORT_VERSION == 3


# -- a skipped trial ------------------------------------------------------------------------------------------


def test_a_skipped_trial_is_skipped_and_left_out_of_every_figure(tmp_path):
    recs = records()
    recs[1] = follow_record(1, onset(1), duration_s=3.0, on_target_ms=100.0, skipped=True, followed=False)
    follow = follow_block(tmp_path, recs=recs)
    skipped = follow["trials"][1]
    assert skipped["outcome"] == "skipped" and skipped["followed"] is None
    assert skipped["time_on_target_pct"] is None and skipped["pursuit_gain"] is None
    assert skipped["pointer_path"] == []
    assert follow["summary"]["n_trials"] == 2 and follow["summary"]["followed"] == 1
    assert follow["summary"]["time_on_target_pct"]["mean"] == 50.0


# -- no valid pointer, no distance -------------------------------------------------------------------------------


def test_a_trial_with_no_valid_pointer_has_dashes_not_zeros(tmp_path):
    recs = records()
    recs[0] = follow_record(0, onset(0), valid_ms=0.0, on_target_ms=0.0, mean_dist_px=None, followed=False)
    first = follow_block(tmp_path, recs=recs)["trials"][0]
    assert first["outcome"] == "not_followed"
    assert first["time_on_target_pct"] is None and first["mean_distance_deg"] is None
    assert first["valid_pct"] == 0.0


# -- a Mouse run with no tracker ------------------------------------------------------------------------------------


def mouse_folder(tmp_path):
    meta = copy.deepcopy(FULL_CANVAS_META)
    meta.update(
        input_mode="mouse_follow", input_pointer="mouse", gaze_recorded=False,
        calibration_source="not run", calibration_points=0, calibration_error_px=None,
    )
    meta["settings"]["structural"]["input"] = {"pointer": "mouse"}
    meta.pop("raw_clock_offset_ns")
    out = folder(tmp_path, meta=meta, samples=False, frames=False, name="mouse")
    base = horizontal()
    with (out / POINTER_STREAM_FILENAME).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(POINTER_STREAM_COLUMNS)
        for k in range(3):
            writer.writerow([onset(k) - SEC, 1.4, 0.5, 0])  # the mouse is off the canvas in the pause
            for i in range(int(TRIAL_S * 60) + 1):
                t = i / 60.0
                x, y = base(t)
                writer.writerow([onset(k) + round(t * SEC), round(x, 5), round(y, 5), 1])
    return out


def test_a_mouse_run_with_no_tracker_has_no_gain_and_no_catch_up_but_a_pointer_path(tmp_path):
    report = build_report(mouse_folder(tmp_path))
    follow = report["follow"]
    assert follow["gaze_available"] is False
    for trial in follow["trials"]:
        assert trial["pursuit_gain"] is None and trial["catch_up_per_s"] is None
        assert trial["catch_up_count"] is None
        assert trial["pointer_path"] and all(seg["on"] is True for seg in trial["pointer_path"])
    assert follow["summary"]["pursuit_gain"] is None and follow["summary"]["catch_up_per_s"] is None
    # The live figures are still there: they come from the task, not from the tracker.
    assert follow["summary"]["followed"] == 2 and follow["summary"]["valid_pct"] == 100.0
    assert report["session"]["gaze_recorded"] is False
    assert report["session"]["sources"]["pointer_stream"] is True
    assert report["session"]["sources"]["gaze_stream"] is False
    assert all(value == NOT_RECORDED for _label, value in eye_rows(report))


def test_a_mouse_runs_generic_path_is_the_mouses_too(tmp_path):
    report = build_report(mouse_folder(tmp_path))
    assert all(t["path"] for t in report["trials"])  # drawn although there is no gaze at all
    assert all(t["fixations"]["count"] is None for t in report["trials"])
    assert report["heat"]["empty"] is True
    assert dict(report["config"]["rows"])["Input"] == "Mouse pointer"


# -- an old Follow & Click folder (H10) ----------------------------------------------------------------------------------


def legacy_folder(tmp_path):
    recs = [
        follow_record(0, onset(0), followed=True),
        follow_record(1, onset(1), followed=False),
        follow_record(2, onset(2), followed=True),
    ]
    recs[0].t_click_ns = recs[0].t_end_ns - 3 * SEC
    recs[1].is_timeout = True
    out = folder(tmp_path, recs=recs, name="old")
    old = ("valid_ms", "on_target_ms", "time_on_target_pct", "mean_dist_px", "clicks", "click_errors")
    with (out / "trials.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    keep = [c for c in rows[0] if c not in old]
    with (out / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keep)
        writer.writeheader()
        writer.writerows([{k: r[k] for k in keep} for r in rows])
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    meta["settings"]["structural"]["motion"]["select_window_ms"] = 2500
    for key in ("input_pointer", "input_selection", "gaze_recorded", "hitbox_margin_px"):
        meta.pop(key)
    (out / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return out


def test_an_old_follow_and_click_folder_still_builds_in_its_old_layout(tmp_path):
    report = build_report(legacy_folder(tmp_path))
    assert report["follow"] == {"legacy": True}
    assert [t["outcome"] for t in report["trials"]] == ["hit", "timeout", "hit"]
    rows = {r["key"]: r for r in report["summary"]["rows"]}
    assert (rows["all_selected"]["n"], rows["not_selected"]["n"], rows["all_trials"]["N"]) == (2, 1, 3)
    config = dict(report["config"]["rows"])
    assert "Selection" in config and "Maximum time per trial" in config
    assert "selection window 2.5 s" in config["Layout"]
    assert len(config) == 17
    assert report["session"]["pointer"] is None and report["session"]["gaze_recorded"] is None


def test_the_old_sessions_sentence_still_says_it_was_selected(tmp_path):
    old, new = build_report(legacy_folder(tmp_path)), build_report(folder(tmp_path))
    assert "selects it by looking at it" in task_sentence(old)
    assert "nothing is selected" in task_sentence(new)
    assert task_sentence({"session": {"task_id": "click_grid"}}).startswith("One cell")


# -- other tasks are untouched ------------------------------------------------------------------------------------------


def test_another_task_has_no_follow_block(tmp_path):
    meta = copy.deepcopy(FULL_CANVAS_META)
    meta["tasks"] = ["click_grid"]
    recs = [follow_record(0, onset(0), followed=True)]
    recs[0].task_id = "click_grid"
    out = write_session(tmp_path / "grid", recs, meta=meta)
    write_track(out, [])
    assert build_report(out)["follow"] is None
