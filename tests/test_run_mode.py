"""SPEC-compass-task-flow.md 4C.4 / R3 / R8 (data side of ``run_mode``, P2): which
runs are recorded, the seed each mode draws its target order from, the pre-roll,
``NullRecorder``, and the outcome fields a finished run writes."""

from __future__ import annotations

import inspect

import pytest

from src.data.recorder import NullRecorder, SessionRecorder
from src.data.schema import GazeSample, SessionMetadata, TrialRecord
from src.engine.config import load_task_config
from src.engine.run_mode import (
    PRACTICE,
    PRACTICE_SEED_BASE,
    PREROLL_MS,
    PREVIEW,
    PREVIEW_SEED,
    RECORD,
    RUN_MODES,
    is_recorded,
    outcome_fields,
    outcome_log_line,
    preroll_ms,
    run_seed,
    validate_run_mode,
)
from src.engine.task_runner import build_task

# -- run modes ---------------------------------------------------------------


def test_the_three_run_modes():
    assert RUN_MODES == ("record", "practice", "preview")
    assert (RECORD, PRACTICE, PREVIEW) == RUN_MODES


def test_only_a_record_run_is_recorded():
    assert is_recorded(RECORD) is True
    assert is_recorded(PRACTICE) is False
    assert is_recorded(PREVIEW) is False


@pytest.mark.parametrize("mode", RUN_MODES)
def test_validate_run_mode_passes_known_modes_through(mode):
    assert validate_run_mode(mode) == mode


@pytest.mark.parametrize("bad", ["recorded", "", "Record", None, 3])
def test_validate_run_mode_rejects_anything_else(bad):
    with pytest.raises(ValueError):
        validate_run_mode(bad)


# -- seeds (R3) --------------------------------------------------------------


def test_a_record_run_uses_the_tests_own_seed():
    assert run_seed(RECORD, 0) == 0
    assert run_seed(RECORD, 424_242) == 424_242


def test_practice_seeds_are_1_000_000_plus_k_whatever_the_test_seed():
    assert PRACTICE_SEED_BASE == 1_000_000
    assert run_seed(PRACTICE, 123, practice_index=0) == 1_000_000
    assert run_seed(PRACTICE, 123, practice_index=5) == 1_000_005
    assert run_seed(PRACTICE, 999_999, practice_index=5) == 1_000_005  # not a function of it


def test_preview_has_its_own_seed_that_is_not_zero_and_not_a_practice_seed():
    assert PREVIEW_SEED != 0
    assert run_seed(PREVIEW, 7, practice_index=3) == PREVIEW_SEED
    assert PREVIEW_SEED != run_seed(PRACTICE, 0, practice_index=0)
    assert PREVIEW_SEED > run_seed(PRACTICE, 0, practice_index=999_999)


def test_neither_practice_nor_preview_can_draw_a_recorded_order():
    """A test seed is drawn from [0, 999_999] (R3); both other modes sit above it."""
    assert min(run_seed(PRACTICE, 0, practice_index=0), PREVIEW_SEED) > 999_999


@pytest.mark.parametrize("task_id", ["click_static", "click_grid"])
def test_practice_target_order_differs_from_the_record_order_at_seed_zero(task_id):
    """AC4: with seed 0 the practice does not replay the real run's first targets."""
    def first_three(seed):
        task = build_task(task_id, load_task_config(task_id), seed=seed)
        return [(t.x_norm, t.y_norm) for t in task.targets[:3]]

    record = first_three(run_seed(RECORD, 0))
    assert first_three(run_seed(RECORD, 0)) == record  # a seed reproduces its order
    assert first_three(run_seed(PRACTICE, 0, practice_index=0)) != record
    assert first_three(PREVIEW_SEED) != record


# -- pre-roll (R8) -----------------------------------------------------------


def test_only_a_recorded_run_has_the_preroll():
    assert PREROLL_MS >= 500
    assert preroll_ms(RECORD) == PREROLL_MS
    assert preroll_ms(PRACTICE) == 0
    assert preroll_ms(PREVIEW) == 0


# -- NullRecorder ------------------------------------------------------------


def _public(cls):
    return {n for n, v in inspect.getmembers(cls) if not n.startswith("_") and callable(v)}


def test_null_recorder_has_the_surface_of_session_recorder():
    assert _public(NullRecorder) >= _public(SessionRecorder)


def test_null_recorder_accepts_every_call_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    meta = SessionMetadata(subject_id="P001", session_id="practice", started_ns=0)
    rec = NullRecorder(meta)
    assert rec.session_dir is None
    assert rec.metadata is meta
    rec.open()
    rec.open_all_gaze(media_name="click_static", tick_frequency=1)
    rec.open_eye_geometry()
    rec.record_raw(1, {"TIME": "0.1", "FPOGX": "0.5"})
    rec.record_gaze(GazeSample(t_ns=1, x=0.5, y=0.5, valid=True))
    rec.record_event("TARGET_SHOWN", 1, trial=0)
    rec.log("a line\n")
    assert rec.write_trials([TrialRecord(0, "t", 0.5, 0.5, 90, 0)]) is None
    assert rec.write_metadata() is None
    rec.flush_eye_geometry()
    rec.flush_all_gaze()
    rec.close()
    rec.close()  # idempotent, like the real one
    assert list(tmp_path.iterdir()) == []


def test_null_recorder_works_as_a_context_manager():
    with NullRecorder() as rec:
        rec.log("x")
    assert rec.session_dir is None


# -- outcome fields ----------------------------------------------------------


def _trials(spec: str) -> list[TrialRecord]:
    """h = hit, t = timeout, s = skipped."""
    out = []
    for i, ch in enumerate(spec):
        out.append(
            TrialRecord(
                i, "t", 0.5, 0.5, 90, 0, is_hit=ch == "h", is_timeout=ch == "t", is_skipped=ch == "s"
            )
        )
    return out


def test_outcome_of_a_finished_run():
    fields = outcome_fields(
        _trials("hhts"), planned=4, is_done=True, pause_count=2, interrupted_trials=1, ended_ns=99
    )
    assert fields == {
        "planned_trials": 4,
        "completed_trials": 4,  # rows in trials.csv, the skipped one included
        "skipped_trials": 1,
        "interrupted_trials": 1,
        "pause_count": 2,
        "outcome": "completed",
        "ended_by": "finished",
        "ended_ns": 99,
    }


def test_outcome_of_a_run_the_operator_ended():
    fields = outcome_fields(
        _trials("hh"), planned=6, is_done=False, pause_count=0, interrupted_trials=0, ended_ns=5
    )
    assert (fields["outcome"], fields["ended_by"]) == ("ended_early", "operator_quit")
    assert (fields["planned_trials"], fields["completed_trials"]) == (6, 2)


def test_every_outcome_field_is_a_metadata_field():
    fields = outcome_fields(_trials(""), 1, False, 0, 0, 0)
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    for name, value in fields.items():
        setattr(meta, name, value)  # slots: raises for a name the metadata lacks
        assert meta.to_dict()[name] == value


def test_apply_outcome_writes_the_metadata_and_returns_the_log_line():
    from types import SimpleNamespace

    from src.engine.run_mode import apply_outcome

    task = SimpleNamespace(
        trials=_trials("ht"),
        targets=[object()] * 5,
        is_done=False,
        pause_count=1,
        interrupted_trials=1,
        trial_number=3,
    )
    meta = SessionMetadata(subject_id="S", session_id="x", started_ns=0)
    line = apply_outcome(meta, task, 77)
    assert line == "Run ended early by operator at trial 3 of 5 (2 recorded)."
    assert (meta.planned_trials, meta.completed_trials, meta.skipped_trials) == (5, 2, 0)
    assert (meta.outcome, meta.ended_by, meta.ended_ns) == ("ended_early", "operator_quit", 77)
    assert (meta.pause_count, meta.interrupted_trials) == (1, 1)
    task.is_done, task.trial_number = True, 5
    task.trials = _trials("hhhhh")
    assert apply_outcome(meta, task, 78) == "Run completed: 5 of 5 trials."
    assert meta.outcome == "completed"


def test_the_task_reports_the_trial_it_is_on():
    from src.engine.config import load_task_config
    from src.engine.task_runner import build_task
    from src.inputs.base import Pointer

    task = build_task("click_static", load_task_config("click_static"))
    assert task.trial_number == 0  # before the first
    task.update(0, Pointer(x=0.5, y=0.5, valid=False, clicked=False))
    assert task.trial_number == 1


def test_outcome_log_lines():
    assert outcome_log_line("completed", completed=18, planned=18, trial_number=18) == (
        "Run completed: 18 of 18 trials."
    )
    assert outcome_log_line("ended_early", completed=3, planned=18, trial_number=4) == (
        "Run ended early by operator at trial 4 of 18 (3 recorded)."
    )
