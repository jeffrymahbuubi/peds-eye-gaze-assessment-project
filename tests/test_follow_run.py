# The fixtures are imported from input_run_fixtures and then used by name.
# ruff: noqa: F811
"""SPEC-input-selection-and-follow.md 4.4, I8, I10, A6 through ``AssessmentApp``: a Follow the
Target run on the canvas with the mouse for the gaze (and as the Mouse pointer): no dwell ring or
instant ring, the glow while on the target, the trial duration, the live counts in ``trials.csv``,
the ``FOLLOWED`` event, and the report built from the folder the run left. Offscreen Qt."""

from __future__ import annotations

import csv
import json
import time

import pytest

from src.data.report_cache import build_report
from src.engine.run_result import RunResult, practice_result_text
from tests.input_run_fixtures import (  # noqa: F401  (fixtures)
    events_of,
    kinds,
    look_at_target,
    look_away,
    make_app,
    parked,
    qapp,
    tick,
)

DURATION_MS = 3000
LIVE = {"task.timeout_ms": DURATION_MS}


def follow_app(make_app, *, pointer="gaze", client="mouse", trials=1, **kw):
    return make_app("follow_moving", choice={"pointer": pointer}, client=client, trials=trials,
                    live=LIVE, **kw)


def follow_it(app):
    """Put the pointer on the target where it is NOW (the target of Follow moves: the shared
    ``look_at_target`` reads it at elapsed 0, where the trial starts)."""
    task = app.task
    elapsed = time.time_ns() - task._trial_start_ns
    app.pointing.at_norm(app.canvas, *task.target_position(task.targets[task._trial_index], elapsed))


def run_to_the_end(app, pointer_for, seconds=15.0):
    deadline = time.monotonic() + seconds
    while not app._shutdown_done:
        assert time.monotonic() < deadline, "timed out"
        app._tick()
        if app.task.phase.name == "WAIT_INPUT":
            pointer_for(app)
        time.sleep(0.004)


# -- the run is set up as a follow run -----------------------------------------------------------


def test_a_follow_run_has_the_glow_and_no_dwell_rings_and_no_switch(make_app):
    app = follow_app(make_app)
    assert app.canvas.show_glow is True
    assert app.canvas.show_progress_ring is False and app.canvas.show_instant_feedback is False
    assert app.canvas.switch_press_enabled is False and not app.run_cursor.hidden
    meta = app.metadata
    assert (meta.input_mode, meta.input_pointer, meta.input_selection) == ("eye", "gaze", None)
    assert meta.hitbox_margin_px == 40.0 and app.task.has_selection is False
    assert app.task.timeout_ns == DURATION_MS * 1_000_000


def test_the_glow_can_be_turned_off_for_follow_too(make_app):
    app = follow_app(make_app, structural={"feedback": {"target_glow": False}})
    assert app.canvas.show_glow is False


def test_a_selection_run_keeps_its_rings(make_app):
    app = make_app(choice={"pointer": "gaze", "selection": "dwell"})
    assert app.canvas.show_progress_ring is True and app.canvas.show_instant_feedback is True


def test_the_canvas_is_told_the_pointer_is_on_the_target_while_it_is(make_app):
    app = follow_app(make_app)
    tick(app, 2)
    look_at_target(app)
    tick(app)
    assert app.canvas.on_target is True
    look_away(app)
    tick(app)
    assert app.canvas.on_target is False


# -- a whole run ------------------------------------------------------------------------------------


def test_a_followed_trial_lasts_its_duration_and_leaves_the_counts(make_app):
    app = follow_app(make_app, trials=1)
    run_to_the_end(app, follow_it)
    folder = app.recorder.session_dir
    with (folder / "trials.csv").open(encoding="utf-8") as fh:
        (row,) = list(csv.DictReader(fh))
    length_ms = (int(row["t_end_ns"]) - int(row["t_target_shown_ns"])) / 1e6
    assert DURATION_MS <= length_ms <= DURATION_MS + 200  # a frame or two of a slow test loop
    assert (row["is_hit"], row["is_timeout"], row["t_click_ns"], row["attempts"]) == ("1", "0", "", "0")
    assert float(row["time_on_target_pct"]) > 95.0
    assert float(row["valid_ms"]) > 0.9 * DURATION_MS and float(row["mean_dist_px"]) < 30.0
    (followed,) = kinds(app, "FOLLOWED")
    assert followed["trial"] == 0 and followed["time_on_target_pct"] > 95.0
    assert kinds(app, "NOT_FOLLOWED") == [] and kinds(app, "HIT") == [] and kinds(app, "TIMEOUT") == []


def test_a_trial_the_child_did_not_follow_is_not_followed_and_silent(make_app):
    app = follow_app(make_app, trials=1)
    run_to_the_end(app, look_away)
    with (app.recorder.session_dir / "trials.csv").open(encoding="utf-8") as fh:
        (row,) = list(csv.DictReader(fh))
    assert (row["is_hit"], row["is_timeout"]) == ("0", "0")
    assert float(row["time_on_target_pct"]) < 5.0 and float(row["mean_dist_px"]) > 100.0
    assert [e["kind"] for e in events_of(app) if e["kind"] in ("FOLLOWED", "NOT_FOLLOWED")] == [
        "NOT_FOLLOWED"
    ]


def test_the_report_of_the_folder_the_run_left_has_the_follow_block(make_app):
    app = follow_app(make_app, trials=1)
    run_to_the_end(app, follow_it)
    report = build_report(app.recorder.session_dir)
    follow = report["follow"]
    assert follow["legacy"] is False
    (trial,) = follow["trials"]
    assert trial["outcome"] == "followed" and trial["time_on_target_pct"] > 95.0
    assert trial["duration_s"] == pytest.approx(DURATION_MS / 1000, abs=0.2)
    assert follow["summary"]["followed"] == 1 and follow["summary"]["n_trials"] == 1
    assert follow["trial_duration_s"] == pytest.approx(DURATION_MS / 1000, abs=0.2)
    rows = dict(report["config"]["rows"])
    assert rows["Trial duration"] == "3 s" and "Selection" not in rows
    assert report["trials"][0]["outcome"] == "followed"
    # The mouse stood in for the tracker (a client, not a pointer), so the track is the task's.
    assert report["session"]["sources"]["target_track"] is True


def test_the_settings_recorded_hold_the_trial_duration_and_no_dwell_values(make_app):
    app = follow_app(make_app, trials=1)
    run_to_the_end(app, follow_it)
    meta = json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))
    live = meta["settings"]["live"]
    assert live["task.timeout_ms"] == DURATION_MS
    assert not any(key.startswith("dwell.") and key not in ("dwell.visual_cursor",) and
                   not key.startswith("dwell.smoothing") for key in live)
    assert "select_window_ms" not in json.dumps(meta["settings"])
    assert meta["settings"]["structural"]["input"] == {"pointer": "gaze"}


# -- Mouse Follow with no tracker ------------------------------------------------------------------------


def test_a_mouse_follow_with_no_tracker_records_the_pointer_and_measures_it(make_app):
    app = follow_app(make_app, pointer="mouse", client=None, trials=1)
    assert app.input_mode == "mouse_follow" and app._gaze_recorded is False
    run_to_the_end(app, follow_it)
    folder = app.recorder.session_dir
    assert (folder / "pointer_stream.csv").exists() and not (folder / "gaze_stream.csv").exists()
    report = build_report(folder)
    follow = report["follow"]
    assert follow["gaze_available"] is False
    (trial,) = follow["trials"]
    assert trial["followed"] is True and trial["pursuit_gain"] is None
    assert trial["pointer_path"]  # the mouse's path, from pointer_stream.csv
    assert report["session"]["gaze_recorded"] is False


# -- the practice line ------------------------------------------------------------------------------------


def finished(task_id, hits=2):
    return RunResult("practice", "completed", "finished", 3, 3, 0, hits, None, "2026-10-08T10:00:00",
                     task_id=task_id)


def test_a_follow_practice_says_followed_not_selected():
    assert practice_result_text(finished("follow_moving")) == (
        "Practice finished: 2 of 3 followed. You can practice again or press Start."
    )
    assert practice_result_text(finished("click_grid")) == (
        "Practice finished: 2 of 3 selected. You can practice again or press Start."
    )
    assert "selected" in practice_result_text(finished(""))  # a result with no task id: as before
