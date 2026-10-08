"""SPEC-compass-task-flow.md 4C.6 / 4C.9 / R8 (engine side, P2): ``is_skipped``,
``BaseTask.pause`` / ``resume`` / ``skip_trial``, the recorded-run pre-roll, the
``summarize()`` skip handling and the new metadata fields. Acceptance AC9, AC10,
AC16."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.data.exporter import load_trials_rows, summarize
from src.data.schema import SessionMetadata, TrialRecord
from src.engine.feedback import NullFeedback
from src.inputs.base import Pointer
from src.tasks.base_task import BaseTask, Phase, TargetSpec
from tests.recorder_helpers import recorder_in

MS = 1_000_000


class _Spy:
    """Recorder double: keeps the events and log lines a task emits."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int, dict]] = []
        self.lines: list[str] = []

    def record_event(self, kind: str, t_ns: int, **payload) -> None:
        self.events.append((kind, t_ns, payload))

    def log(self, message: str) -> None:
        self.lines.append(message)

    def of(self, kind: str) -> list[tuple[str, int, dict]]:
        return [e for e in self.events if e[0] == kind]


class _FixedTask(BaseTask):
    """N fixed targets, each on a different cell, so a re-presented target is
    recognisable by its position."""

    def __init__(self, n_targets: int, *args, **kwargs) -> None:
        self._n_targets = n_targets
        super().__init__(*args, **kwargs)

    def build_targets(self) -> list[TargetSpec]:
        return [
            TargetSpec(index=i, x_norm=0.1 + 0.2 * i, y_norm=0.5, radius_px=50.0)
            for i in range(self._n_targets)
        ]


def make_task(n: int = 4, timeout_ms: int = 1000, iti_ms: int = 100, **kwargs):
    spy = _Spy()
    fb = NullFeedback()
    cfg = {"task": {"task_id": "fixed", "timeout_ms": timeout_ms, "inter_trial_interval_ms": iti_ms}}
    task = _FixedTask(
        n, cfg, 1000, 1000, recorder=spy, feedback=fb, input_mode="switch", **kwargs
    )
    return task, spy, fb


def on(task: BaseTask, i: int) -> Pointer:
    """A pointer sitting on target ``i`` (no click)."""
    return Pointer(x=task.targets[i].x_norm, y=0.5, valid=True, clicked=False)


def click(task: BaseTask, i: int) -> Pointer:
    return Pointer(x=task.targets[i].x_norm, y=0.5, valid=True, clicked=True)


NOWHERE = Pointer(x=0.99, y=0.99, valid=True, clicked=False)


# -- schema: is_skipped (R6) -------------------------------------------------


def test_is_skipped_defaults_false_and_is_followed_by_the_p3_columns():
    trial = TrialRecord(0, "t", 0.5, 0.5, 90, 0)
    assert trial.is_skipped is False
    header = TrialRecord.csv_header()
    # R6: is_skipped, then the 4D.4 columns, in one go (P3 adds the last four).
    assert header[header.index("is_skipped"):] == [
        "is_skipped", "entries", "end_x", "end_y", "slot_index", "clicks", "click_errors",
        "valid_ms", "on_target_ms", "time_on_target_pct", "mean_dist_px",
    ]
    assert "outcome" not in header  # R6: no outcome column, the report derives it
    assert list(trial.as_row()) == header
    assert trial.as_row()["is_skipped"] == 0
    trial.is_skipped = True
    assert trial.as_row()["is_skipped"] == 1


# -- AC10: skip --------------------------------------------------------------


def test_skip_records_a_skipped_row_and_no_feedback():
    task, spy, fb = make_task()
    task.update(0, NOWHERE)  # trial 0 is shown
    assert task.phase is Phase.WAIT_INPUT
    fb.events.clear()

    assert task.skip_trial(300 * MS) is True
    row = task.trials[0]
    assert (row.is_skipped, row.is_hit, row.is_timeout) == (True, False, False)
    assert row.t_end_ns == 300 * MS and row.t_click_ns is None
    flat = row.as_row()
    assert (flat["is_skipped"], flat["is_hit"], flat["is_timeout"]) == (1, 0, 0)
    assert flat["t_click_ns"] == "" and flat["t_end_ns"] == 300 * MS
    # No hit cue, no miss cue (U5: a skip is not a timeout).
    assert [e for e in fb.events if e[0] in ("hit", "miss")] == []
    assert [(k, p["trial"]) for k, _t, p in spy.of("SKIPPED")] == [("SKIPPED", 0)]
    assert spy.of("TIMEOUT") == [] and spy.of("HIT") == []
    assert task.phase is Phase.ITI


def test_a_skipped_run_still_runs_to_n_trials():
    task, _spy, _fb = make_task(n=3)
    t = 0
    task.update(t, NOWHERE)
    task.skip_trial(t + 10 * MS)  # trial 0 skipped
    t += 10 * MS + 100 * MS  # ITI over
    task.update(t, click(task, 1))  # trial 1 starts; no click yet on this frame
    task.update(t + 5 * MS, click(task, 1))  # trial 1 hit (switch input)
    t += 5 * MS + 100 * MS
    task.update(t, NOWHERE)  # trial 2 starts
    task.update(t + 1000 * MS, NOWHERE)  # trial 2 times out
    task.update(t + 1000 * MS + 100 * MS, NOWHERE)  # ITI over -> done
    assert task.is_done
    assert [(r.trial_id, r.is_skipped, r.is_hit, r.is_timeout) for r in task.trials] == [
        (0, True, False, False),
        (1, False, True, False),
        (2, False, False, True),
    ]


@pytest.mark.parametrize("when", ["ready", "iti", "done", "paused"])
def test_skip_does_nothing_outside_a_running_trial(when):
    task, spy, _fb = make_task(n=1)
    if when != "ready":
        task.update(0, NOWHERE)
    if when in ("iti", "done"):
        task.skip_trial(10 * MS)  # trial 0 skipped -> ITI
        spy.events.clear()
    if when == "done":
        task.update(10 * MS + 100 * MS, NOWHERE)
        assert task.is_done
    if when == "paused":
        task.pause(10 * MS)
        spy.events.clear()
    before = len(task.trials)
    assert task.skip_trial(500 * MS) is False
    assert len(task.trials) == before
    assert spy.of("SKIPPED") == []


# -- AC9: pause / resume -----------------------------------------------------


def test_pause_in_a_trial_drops_it_and_re_presents_the_same_target_fresh():
    task, spy, _fb = make_task(n=3, timeout_ms=1000)
    task.update(0, NOWHERE)  # trial 0 starts at t=0
    assert task.pause(400 * MS) is True  # in flight -> interrupted
    assert task.trials == []  # never recorded
    assert task.phase is Phase.READY

    task.resume(10_000 * MS)  # a pause far longer than timeout_ms
    result = task.update(10_000 * MS, NOWHERE)
    assert task.trials == []  # the long pause caused no timeout
    assert result.trial_index == 0 and result.target is task.targets[0]  # the same target
    assert task.phase is Phase.WAIT_INPUT
    assert task._trial_start_ns == 10_000 * MS  # fresh clock

    # The re-presented trial is scored like any other, still trial_id 0.
    task.update(10_000 * MS + 200 * MS, click(task, 0))
    assert [(r.trial_id, r.is_hit) for r in task.trials] == [(0, True)]
    assert task.trials[0].t_target_shown_ns == 10_000 * MS


def test_pause_events_and_counters():
    task, spy, _fb = make_task()
    task.update(0, NOWHERE)
    task.pause(400 * MS)
    task.resume(900 * MS)
    kinds = [k for k, _t, _p in spy.events]
    assert kinds.index("TRIAL_INTERRUPTED") < kinds.index("PAUSED") < kinds.index("RESUMED")
    _k, t_ns, payload = spy.of("TRIAL_INTERRUPTED")[0]
    assert t_ns == 400 * MS
    assert payload == {"trial": 0, "reason": "pause", "elapsed_ms": 400.0}
    _k, t_ns, payload = spy.of("PAUSED")[0]
    assert t_ns == 400 * MS and payload == {"trial": 0, "interrupted": True}
    assert spy.of("RESUMED")[0][1] == 900 * MS
    assert (task.pause_count, task.interrupted_trials) == (1, 1)


def test_a_full_run_with_pauses_keeps_n_contiguous_trials():
    task, _spy, _fb = make_task(n=3, timeout_ms=1000)
    t = 0
    task.update(t, NOWHERE)
    task.pause(t + 100 * MS)
    task.resume(t + 5_000 * MS)
    t += 5_000 * MS
    for i in range(3):
        task.update(t, NOWHERE)  # trial i starts (or is already running)
        task.update(t + 50 * MS, click(task, i))  # hit
        t += 50 * MS + 100 * MS
        if i == 1:  # a second pause, this time in the ITI of trial 1
            task.pause(t - 30 * MS)  # 30 ms of the ITI left
            task.resume(t + 9_000 * MS)
            t += 9_000 * MS + 30 * MS  # the rest of the ITI is served
    task.update(t, NOWHERE)
    assert task.is_done
    assert [r.trial_id for r in task.trials] == [0, 1, 2]
    assert all(r.is_hit for r in task.trials)
    assert task.pause_count == 2 and task.interrupted_trials == 1  # the ITI pause interrupted nothing


def test_pause_in_the_iti_keeps_the_remaining_iti():
    task, spy, _fb = make_task(n=2, iti_ms=100)
    task.update(0, NOWHERE)
    task.update(50 * MS, click(task, 0))  # trial 0 hit at 50 ms; ITI ends at 150 ms
    assert task.phase is Phase.ITI
    assert task.pause(110 * MS) is False  # nothing was in flight
    assert spy.of("PAUSED")[0][2] == {"trial": 0, "interrupted": False}
    assert spy.of("TRIAL_INTERRUPTED") == []
    task.resume(5_110 * MS)  # 40 ms of ITI were left
    task.update(5_149 * MS, NOWHERE)
    assert task.phase is Phase.ITI  # still waiting
    task.update(5_150 * MS, NOWHERE)
    assert task.phase is Phase.WAIT_INPUT and task._trial_index == 1
    assert len(task.trials) == 1  # trial 0 untouched


def test_update_while_paused_never_advances_the_task():
    task, _spy, _fb = make_task(n=1, timeout_ms=1000)
    task.update(0, NOWHERE)
    task.pause(100 * MS)
    for t in (2_000 * MS, 50_000 * MS):
        result = task.update(t, NOWHERE)
        assert result.target is None  # nothing to draw while paused
    assert task.trials == []
    task.resume(60_000 * MS)
    task.update(60_000 * MS, NOWHERE)
    assert task.phase is Phase.WAIT_INPUT and task.trials == []


def test_pause_resume_edge_cases_are_harmless():
    task, spy, _fb = make_task(n=1)
    task.resume(5)  # not paused: nothing
    assert spy.events == []
    task.update(0, NOWHERE)
    assert task.pause(10 * MS) is True
    assert task.pause(20 * MS) is False  # already paused: not counted twice
    assert task.pause_count == 1 and len(spy.of("PAUSED")) == 1
    task.resume(30 * MS)
    task.resume(40 * MS)
    assert len(spy.of("RESUMED")) == 1


def test_pause_after_the_run_is_over_is_ignored():
    task, spy, _fb = make_task(n=1)
    task.update(0, NOWHERE)
    task.skip_trial(10 * MS)
    task.update(10 * MS + 100 * MS, NOWHERE)
    assert task.is_done
    assert task.pause(500 * MS) is False
    assert task.pause_count == 0 and spy.of("PAUSED") == []


# -- R8: pre-roll ------------------------------------------------------------


def test_no_preroll_by_default_the_first_trial_starts_at_once():
    task, spy, _fb = make_task()
    task.update(7 * MS, NOWHERE)
    assert task.phase is Phase.WAIT_INPUT
    assert spy.of("TARGET_SHOWN")[0][1] == 7 * MS


def test_preroll_holds_trial_one_for_at_least_500_ms_from_the_first_frame():
    task, spy, _fb = make_task(preroll_ms=500)
    t0 = 1_000 * MS
    first = task.update(t0, NOWHERE)
    assert task.phase is Phase.READY and first.target is None and first.trial_index == -1
    for dt in (0, 100, 499):
        result = task.update(t0 + dt * MS, on(task, 0))
        assert result.target is None and task.trials == []
    assert spy.of("TARGET_SHOWN") == []
    task.update(t0 + 500 * MS, NOWHERE)
    assert task.phase is Phase.WAIT_INPUT
    assert spy.of("TARGET_SHOWN")[0][1] - t0 >= 500 * MS


def test_preroll_does_not_apply_between_trials_or_after_a_pause():
    task, spy, _fb = make_task(n=2, preroll_ms=500)
    t0 = 0
    task.update(t0, NOWHERE)
    task.update(t0 + 500 * MS, NOWHERE)  # trial 0 starts
    task.pause(t0 + 600 * MS)  # interrupts it
    task.resume(t0 + 700 * MS)
    task.update(t0 + 700 * MS, NOWHERE)  # re-presented at once, no 500 ms wait
    assert task.phase is Phase.WAIT_INPUT
    task.update(t0 + 750 * MS, click(task, 0))
    assert task.phase is Phase.ITI
    task.update(t0 + 750 * MS + 100 * MS, NOWHERE)  # next trial at the ITI, not 500 ms later
    assert task.phase is Phase.WAIT_INPUT and task._trial_index == 1


def test_a_pause_during_the_preroll_does_not_eat_it():
    task, spy, _fb = make_task(preroll_ms=500)
    task.update(0, NOWHERE)
    assert task.pause(200 * MS) is False  # nothing in flight
    task.resume(10_200 * MS)
    task.update(10_200 * MS, NOWHERE)
    assert task.phase is Phase.READY  # 300 ms of the pre-roll are still left
    task.update(10_499 * MS, NOWHERE)
    assert task.phase is Phase.READY
    task.update(10_500 * MS, NOWHERE)
    assert task.phase is Phase.WAIT_INPUT


# -- summarize(): skips (AC10 last clause, AC16) -----------------------------


def _write_trials(tmp_path: Path, trials: list[TrialRecord]) -> Path:
    meta = SessionMetadata(subject_id="P001", session_id="s_skip", started_ns=0)
    with recorder_in(tmp_path, meta) as rec:
        rec.write_trials(trials)
    return tmp_path / "s_skip"


def test_summarize_counts_skips_apart_from_timeouts_and_hit_rate(tmp_path):
    trials = [
        TrialRecord(0, "t", 0.5, 0.5, 90, 0, t_click_ns=800 * MS, is_hit=True, attempts=1),
        TrialRecord(1, "t", 0.5, 0.5, 90, 0, is_timeout=True),
        TrialRecord(2, "t", 0.5, 0.5, 90, 0, is_skipped=True, t_end_ns=5 * MS),
        TrialRecord(3, "t", 0.5, 0.5, 90, 0, is_skipped=True, t_end_ns=5 * MS),
    ]
    summary = summarize(_write_trials(tmp_path, trials))
    assert summary["n_trials"] == 4
    assert summary["n_skipped"] == 2
    assert summary["n_timeouts"] == 1  # the skips are not in it
    assert summary["n_hits"] == 1
    assert summary["hit_rate"] == 0.5  # 1 hit / (4 trials - 2 skipped)


def test_summarize_with_only_skips_has_no_hit_rate(tmp_path):
    trials = [TrialRecord(0, "t", 0.5, 0.5, 90, 0, is_skipped=True)]
    summary = summarize(_write_trials(tmp_path, trials))
    assert summary["n_skipped"] == 1 and summary["hit_rate"] is None


def test_summarize_reads_an_older_trials_csv_without_the_column(tmp_path):
    old_header = [c for c in TrialRecord.csv_header() if c != "is_skipped"]
    session = tmp_path / "old"
    session.mkdir()
    with (session / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=old_header)
        writer.writeheader()
        for i, hit in enumerate((True, False)):
            row = TrialRecord(i, "t", 0.5, 0.5, 90, 0, is_hit=hit, is_timeout=not hit).as_row()
            row.pop("is_skipped")
            writer.writerow(row)
    assert "is_skipped" not in load_trials_rows(session)[0]
    summary = summarize(session)
    assert summary["n_skipped"] == 0 and summary["hit_rate"] == 0.5 and summary["n_timeouts"] == 1


# -- AC16: new metadata fields -----------------------------------------------

_NEW_FIELDS = (
    "run_mode",
    "config_name",
    "planned_trials",
    "completed_trials",
    "skipped_trials",
    "interrupted_trials",
    "pause_count",
    "outcome",
    "ended_by",
    "ended_ns",
)


def test_new_metadata_fields_default_to_none_and_serialise():
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    assert all(getattr(meta, name) is None for name in _NEW_FIELDS)
    meta.run_mode, meta.config_name = "record", "Custom 1"
    meta.planned_trials, meta.completed_trials, meta.skipped_trials = 18, 17, 1
    meta.interrupted_trials, meta.pause_count = 2, 3
    meta.outcome, meta.ended_by, meta.ended_ns = "ended_early", "operator_quit", 123
    data = meta.to_dict()
    assert data["run_mode"] == "record" and data["config_name"] == "Custom 1"
    assert (data["planned_trials"], data["completed_trials"], data["skipped_trials"]) == (18, 17, 1)
    assert (data["interrupted_trials"], data["pause_count"]) == (2, 3)
    assert (data["outcome"], data["ended_by"], data["ended_ns"]) == ("ended_early", "operator_quit", 123)
    assert data["schema_version"] == 1  # additive: not bumped


def test_older_metadata_without_the_new_fields_still_loads():
    old = SessionMetadata(subject_id="S", session_id="x", started_ns=0).to_dict()
    for name in _NEW_FIELDS:
        old.pop(name)
    assert SessionMetadata(**old).outcome is None


def test_the_hud_fields_are_gone_with_the_hud():
    """4C.7 / HC13: the HUD-hiding fields left ``SessionMetadata`` with the HUD. An older
    ``metadata.json`` that still carries them is read by named key, so nothing breaks."""
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    assert not hasattr(meta, "hud_hidden_at_start") and not hasattr(meta, "hud_toggle_count")
    assert "hud_hidden_at_start" not in meta.to_dict() and "hud_toggle_count" not in meta.to_dict()
