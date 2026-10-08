"""SPEC-input-selection-and-follow.md 4.4, I8-I10, H6, H7, H9 (acceptance A6): Follow the Target
has no selection -- no click, no dwell, no selection window -- every trial lasts exactly its
duration, the task counts the pointer per frame (valid time, time on target, distance), a trial is
*followed* with at least half of its valid time on the target, the hit sound plays only for a
followed trial and a miss sound never. No Qt: ``BaseTask`` is driven one frame at a time."""

from __future__ import annotations

import csv

import pytest

from src.data.schema import SessionMetadata, TrialRecord
from src.engine.config import load_task_config
from src.engine.feedback import NullFeedback
from src.engine.task_runner import build_task
from src.inputs.base import Pointer
from src.tasks.base_task import BaseTask, Phase
from src.tasks.follow_moving import FOLLOWED_PCT, MAX_FRAME_MS, FollowMovingTask
from tests.recorder_helpers import recorder_in

FRAME_NS = 16_666_667  # 60 Hz
MS = 1_000_000
DURATION_MS = 2000


class Spy:
    """Recorder double: the events a task emits."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []

    def record_event(self, kind, t_ns, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message) -> None: ...

    def of(self, kind):
        return [e for e in self.events if e[0] == kind]


def make(trials=2, duration_ms=DURATION_MS, path="horizontal", mode="eye", extra_motion=None):
    cfg = load_task_config("follow_moving")
    cfg["input"] = {"mode": mode}
    cfg["task"].update(trials=trials, timeout_ms=duration_ms, inter_trial_interval_ms=100)
    cfg["task"]["motion"] = {"path": path, "speed_frac_per_s": 0.2, **(extra_motion or {})}
    spy, fb = Spy(), NullFeedback()
    return build_task("follow_moving", cfg, recorder=spy, feedback=fb, seed=3), spy, fb


def where_is_the_target(task, t_ns):
    """The canvas-normalized position of the target the pointer should be following at ``t_ns``."""
    index = max(task._trial_index, 0)
    elapsed = max(t_ns - task._trial_start_ns, 0) if task._trial_index >= 0 else 0
    return task.target_position(task.targets[index], elapsed)


def run(task, pointer_for, *, seconds=30.0):
    """Frame by frame at 60 Hz until the task is done. ``pointer_for(task, t_ns, since_start_ms)``
    returns a ``Pointer``."""
    t = 0
    frames = int(seconds * 60)
    for _ in range(frames):
        since = (t - task._trial_start_ns) / 1e6 if task._trial_index >= 0 else 0.0
        task.update(t, pointer_for(task, t, since))
        if task.is_done:
            return
        t += FRAME_NS
    raise AssertionError("the run did not finish")


def on_target(task, t, since_ms):
    x, y = where_is_the_target(task, t)
    return Pointer(x=x, y=y, valid=True, clicked=False)


def off_target(task, t, since_ms):
    x, y = where_is_the_target(task, t)
    return Pointer(x=min(x + 0.4, 0.99) if x < 0.5 else x - 0.4, y=y, valid=True, clicked=False)


def on_then_off(share_on):
    """On the target for ``share_on`` of the trial, then far from it."""

    def pointer_for(task, t, since_ms):
        return on_target(task, t, since_ms) if since_ms < share_on * DURATION_MS else off_target(
            task, t, since_ms
        )

    return pointer_for


# -- no selection (I9) --------------------------------------------------------------------


def test_follow_has_no_selection_and_no_selection_window():
    task, _spy, _fb = make()
    assert FollowMovingTask.has_selection is False and BaseTask.has_selection is True
    assert not hasattr(task, "select_windows") and not hasattr(task, "select_window_ns")
    assert FollowMovingTask.is_selectable is BaseTask.is_selectable  # no override: always selectable
    assert task.targets and all(task.is_selectable(t, 0) for t in task.targets)


def test_an_old_test_that_still_carries_a_selection_window_runs_and_ignores_it():
    task, _spy, _fb = make(extra_motion={"select_window_ms": 100})
    run(task, on_target)
    assert [r.is_hit for r in task.trials] == [True, True]  # a 0.1 s window would have shut it


def test_a_click_is_not_a_selection_and_leaves_no_trace():
    task, spy, fb = make(trials=1)
    t = 0
    for _ in range(200):
        x, y = where_is_the_target(task, t)
        task.update(t, Pointer(x=x, y=y, valid=True, clicked=True))  # on target, "pressing"
        t += FRAME_NS
        if task.is_done:
            break
    row = task.trials[0]
    assert (row.attempts, row.clicks, row.click_errors) == (0, 0, 0)
    assert row.t_click_ns is None and row.is_timeout is False
    for kind in ("MISS_CLICK", "SWITCH_PRESS", "SWITCH_IGNORED", "HIT", "TIMEOUT"):
        assert spy.of(kind) == [], kind


def test_dwell_never_completes_here():
    task, _spy, fb = make(trials=1)
    run(task, on_target)
    assert not any(kind == "progress" for kind, _x, _y in fb.events)  # no dwell ring to feed
    assert task.trials[0].t_click_ns is None


# -- every trial lasts its duration (H9, A6) -------------------------------------------------


@pytest.mark.parametrize("pointer_for", [on_target, off_target])
def test_every_trial_lasts_exactly_the_trial_duration_whatever_the_child_does(pointer_for):
    task, _spy, _fb = make()
    run(task, pointer_for)
    assert len(task.trials) == 2
    for row in task.trials:
        length_ms = (row.t_end_ns - row.t_target_shown_ns) / 1e6
        assert DURATION_MS <= length_ms <= DURATION_MS + FRAME_NS / 1e6  # to the frame
        assert row.is_timeout is False and row.is_skipped is False


def test_the_trial_duration_is_the_tasks_timeout():
    task, _spy, _fb = make(duration_ms=3500)
    assert task.timeout_ns == 3500 * MS
    run(task, off_target)
    assert (task.trials[0].t_end_ns - task.trials[0].t_target_shown_ns) / 1e6 == pytest.approx(
        3500, abs=17
    )


def test_the_shipped_default_is_ten_seconds():
    cfg = load_task_config("follow_moving")
    assert cfg["task"]["timeout_ms"] == 10000
    assert "select_window_ms" not in cfg["task"]["motion"]
    assert cfg["task"]["title"].endswith("Follow the Target")


# -- the pointer, counted per frame (H7, A6) -----------------------------------------------------


def test_a_pointer_glued_to_the_target_is_on_it_the_whole_time_and_followed():
    task, spy, _fb = make()
    run(task, on_target)
    for row in task.trials:
        assert row.is_hit is True
        assert row.time_on_target_pct == pytest.approx(100.0)
        assert row.on_target_ms == pytest.approx(row.valid_ms)
        assert row.valid_ms == pytest.approx(DURATION_MS, abs=40)
        assert row.mean_dist_px == pytest.approx(0.0, abs=1e-6)
    kinds = [(k, p["time_on_target_pct"]) for k, _t, p in spy.events if k in ("FOLLOWED", "NOT_FOLLOWED")]
    assert kinds == [("FOLLOWED", 100.0)] * 2


def test_a_pointer_on_the_target_half_the_time_is_on_target_50_percent_a6():
    task, _spy, _fb = make()
    run(task, on_then_off(0.5))
    for row in task.trials:
        assert row.time_on_target_pct == pytest.approx(50.0, abs=1.0)
        assert row.valid_ms == pytest.approx(DURATION_MS, abs=40)


@pytest.mark.parametrize("share, followed", [(0.6, True), (0.5, True), (0.4, False), (0.0, False)])
def test_followed_means_at_least_half_of_the_valid_time_on_target(share, followed):
    assert FOLLOWED_PCT == 50.0
    task, spy, _fb = make(trials=1)
    run(task, on_then_off(share if share != 0.5 else 0.52))  # 0.52: clear of a frame's rounding
    row = task.trials[0]
    assert row.is_hit is followed
    assert [k for k, *_ in spy.events if k in ("FOLLOWED", "NOT_FOLLOWED")] == [
        "FOLLOWED" if followed else "NOT_FOLLOWED"
    ]


def test_invalid_frames_count_for_nothing_and_are_not_on_target():
    """A blink or a lost eye: no valid time, no on-target time, no distance."""

    def pointer_for(task, t, since_ms):
        pointer = on_target(task, t, since_ms)
        if since_ms < DURATION_MS / 2:
            return Pointer(x=pointer.x, y=pointer.y, valid=False, clicked=False)
        return pointer

    task, _spy, _fb = make(trials=1)
    run(task, pointer_for)
    row = task.trials[0]
    assert row.valid_ms == pytest.approx(DURATION_MS / 2, abs=40)  # only the valid half
    assert row.time_on_target_pct == pytest.approx(100.0)  # of the valid time
    assert row.dist_n == pytest.approx(60, abs=3)  # a distance per valid frame, 60 of them


def test_a_trial_with_no_valid_pointer_at_all_is_not_followed_and_has_no_percentage():
    task, _spy, _fb = make(trials=1)
    run(task, lambda task, t, since: Pointer(x=0.5, y=0.5, valid=False, clicked=False))
    row = task.trials[0]
    assert row.is_hit is False and row.valid_ms == 0.0 and row.time_on_target_pct is None
    assert row.mean_dist_px is None
    assert row.as_row()["time_on_target_pct"] == "" and row.as_row()["mean_dist_px"] == ""


def test_the_mean_distance_is_the_pointers_distance_from_the_targets_centre_in_px():
    def pointer_for(task, t, since_ms):
        x, y = where_is_the_target(task, t)
        return Pointer(x=x + 100 / task.screen_w, y=y, valid=True, clicked=False)  # 100 px right

    task, _spy, _fb = make(trials=1)
    run(task, pointer_for)
    assert task.trials[0].mean_dist_px == pytest.approx(100.0, abs=0.01)
    assert task.trials[0].time_on_target_pct == pytest.approx(100.0)  # 100 px < radius + 40


def test_the_frame_time_is_capped_so_a_stalled_loop_cannot_credit_a_second():
    task, _spy, _fb = make(trials=1)
    t = 0
    x, y = where_is_the_target(task, t)
    task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))  # the trial starts
    t += 5_000 * MS  # the loop stalls for 5 s
    x, y = where_is_the_target(task, t)
    task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
    assert MAX_FRAME_MS == 250.0
    assert task._current is None  # (the trial is over by duration now)
    assert task.trials[0].valid_ms == pytest.approx(MAX_FRAME_MS)


def test_the_first_time_the_pointer_found_the_target_is_still_recorded():
    task, _spy, _fb = make(trials=1)
    run(task, on_target)
    row = task.trials[0]
    assert row.t_first_gaze_on_target_ns is not None
    assert row.time_to_first_fixation_ms == pytest.approx(0.0, abs=40)  # glued from the start
    assert row.entries == 1


# -- feedback (I10) ---------------------------------------------------------------------------------


def test_the_hit_sound_plays_at_the_end_of_a_followed_trial_only():
    task, _spy, fb = make(trials=2)

    def pointer_for(task, t, since_ms):  # trial 1 followed, trial 2 not
        return (on_target if task._trial_index == 0 else off_target)(task, t, since_ms)

    run(task, pointer_for)
    cues = [e for e in fb.events if e[0] in ("hit", "miss")]
    assert [k for k, *_ in cues] == ["hit"]  # one cue, the hit; the lost trial is silent
    assert [r.is_hit for r in task.trials] == [True, False]


def test_a_miss_cue_is_never_played():
    task, _spy, fb = make(trials=3)
    run(task, off_target)
    assert [e for e in fb.events if e[0] in ("hit", "miss")] == []


def test_the_hit_cue_is_where_the_target_ended():
    task, _spy, fb = make(trials=1)
    run(task, on_target)
    (hit,) = [e for e in fb.events if e[0] == "hit"]
    row = task.trials[0]
    assert (hit[1], hit[2]) == (row.end_x, row.end_y) and row.end_x != row.target_x


def test_the_glow_has_what_it_needs_each_frame():
    """The canvas draws the glow from ``on_target`` and ``selectable``."""
    task, _spy, _fb = make(trials=1)
    t = 0
    seen = []
    for _ in range(20):
        x, y = where_is_the_target(task, t)
        result = task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
        seen.append((result.on_target, result.selectable))
        t += FRAME_NS
    assert all(on and selectable for on, selectable in seen)
    result = task.update(t, off_target(task, t, 0))
    assert (result.on_target, result.selectable) == (False, True)


# -- skip and pause (4C.6) ---------------------------------------------------------------------------


def test_a_skipped_trial_is_skipped_and_silent():
    task, spy, fb = make(trials=2)
    t = 0
    x, y = where_is_the_target(task, t)
    task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
    assert task.skip_trial(t + 300 * MS) is True
    row = task.trials[0]
    assert row.is_skipped and not row.is_hit and not row.is_timeout
    assert [k for k, *_ in spy.events if k in ("SKIPPED", "FOLLOWED", "NOT_FOLLOWED")] == ["SKIPPED"]
    assert [e for e in fb.events if e[0] in ("hit", "miss")] == []


def test_a_pause_drops_the_trial_and_the_counts_start_again():
    task, _spy, _fb = make(trials=1)
    t = 0
    for _ in range(40):  # 0.67 s on the target
        x, y = where_is_the_target(task, t)
        task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
        t += FRAME_NS
    assert task.pause(t) is True
    t += 60_000 * MS  # a minute's pause
    task.resume(t)
    x, y = where_is_the_target(task, t)
    task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
    assert task._current is not None and task._current.valid_ms == 0.0  # a fresh record
    run_rest = True
    while run_rest and not task.is_done:
        t += FRAME_NS
        x, y = where_is_the_target(task, t)
        task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
    assert len(task.trials) == 1
    assert task.trials[0].valid_ms == pytest.approx(DURATION_MS, abs=40)  # not 2.67 s


# -- the path, the lanes ------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl"])
def test_every_path_runs_without_selection(path):
    task, _spy, _fb = make(trials=1, path=path)
    run(task, on_target)
    assert task.trials[0].is_hit and task.trials[0].end_x is not None


def test_the_same_seed_gives_the_same_lanes_and_trials_differ():
    a, _s, _f = make(trials=6, path="horizontal")
    b, _s2, _f2 = make(trials=6, path="horizontal")
    assert [(t.x_norm, t.y_norm) for t in a.targets] == [(t.x_norm, t.y_norm) for t in b.targets]
    assert len({t.y_norm for t in a.targets}) > 1
    assert all(0.25 <= t.y_norm <= 0.75 for t in a.targets)


# -- trials.csv ----------------------------------------------------------------------------------------------


def test_the_four_columns_follow_the_click_columns_and_are_blank_for_other_tasks():
    header = TrialRecord.csv_header()
    assert header[header.index("click_errors") :] == [
        "click_errors", "valid_ms", "on_target_ms", "time_on_target_pct", "mean_dist_px",
    ]
    other = TrialRecord(0, "click_grid", 0.5, 0.5, 90.0, 0).as_row()
    assert [other[c] for c in ("valid_ms", "on_target_ms", "time_on_target_pct", "mean_dist_px")] == [""] * 4


def test_the_follow_columns_reach_trials_csv(tmp_path):
    task, _spy, _fb = make(trials=2)
    run(task, on_then_off(0.75))
    meta = SessionMetadata(subject_id="P001", session_id="follow", started_ns=0)
    with recorder_in(tmp_path, meta) as recorder:
        path = recorder.write_trials(task.trials)
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    for row in rows:
        assert row["is_hit"] == "1" and row["is_timeout"] == "0" and row["t_click_ns"] == ""
        assert float(row["valid_ms"]) == pytest.approx(DURATION_MS, abs=40)
        assert float(row["on_target_ms"]) == pytest.approx(0.75 * DURATION_MS, abs=40)
        assert float(row["time_on_target_pct"]) == pytest.approx(75.0, abs=1.5)
        assert float(row["mean_dist_px"]) > 100  # the off-target quarter is far away
        assert (row["clicks"], row["click_errors"], row["attempts"]) == ("0", "0", "0")


def test_the_phase_machine_still_runs_iti_between_trials():
    task, _spy, _fb = make(trials=2)
    t = 0
    phases = set()
    for _ in range(400):
        x, y = where_is_the_target(task, t)
        task.update(t, Pointer(x=x, y=y, valid=True, clicked=False))
        phases.add(task.phase)
        t += FRAME_NS
        if task.is_done:
            break
    assert {Phase.WAIT_INPUT, Phase.ITI, Phase.DONE} <= phases
