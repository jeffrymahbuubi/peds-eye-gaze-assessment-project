"""SPEC-compass-task-flow.md 4C.8, U8, U14, HD1 (P7b): what a finished run hands back
(``RunResult``) and what the operator's choice does (``finish_run``). The carry-forward
from P4: ``report.json`` is built only after a Save, never for a discarded run."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.engine.run_result as run_result
from src.data.report_cache import REPORT_FILENAME, REPORT_VERSION
from src.data.schema import TrialRecord
from src.engine.run_result import (
    DISCARD,
    SAVE,
    SAVE_AND_VIEW,
    RunResult,
    finish_run,
    practice_result_text,
    run_result_from_task,
)
from src.engine.session_files import SessionDiscardError
from src.engine.subject_tests import (
    STATUS_DONE,
    STATUS_ENDED_EARLY,
    STATUS_NOT_DONE,
    TestLockedError,
    create_test,
    list_tests,
)
from tests.report_fixtures import RIG_META, SEC, T0, record, write_session

SUBJECT = "P001"
FINISHED_AT = "2026-10-06T16:30:00+08:00"


def records3():
    return [
        record(0, T0 + 1 * SEC, "hit", dur_s=1.0, entries=1),
        record(1, T0 + 4 * SEC, "timeout", dur_s=2.0, first_gaze_s=None, entries=0, attempts=0),
        record(2, T0 + 8 * SEC, "hit", dur_s=1.5, entries=2),
    ]


@pytest.fixture
def world(tmp_path):
    """An output root with one Not Done test and a recorded run folder for it."""
    root = tmp_path / "sessions"
    root.mkdir()
    test = create_test(root, SUBJECT, "click_grid")
    folder = write_session(root / "2026-10-06_P001_click_grid_run1", records3(), meta=dict(RIG_META))
    return SimpleNamespace(root=root, test=test, folder=folder)


def result_for(world, *, completed=3, planned=3, outcome="completed", folder=True, **kw):
    return RunResult(
        run_mode=kw.pop("run_mode", "record"),
        outcome=outcome,
        ended_by="finished" if outcome == "completed" else "operator_quit",
        planned=planned,
        completed=completed,
        skipped=0,
        hits=2,
        session_dir=world.folder if folder else None,
        finished_at=FINISHED_AT,
        **kw,
    )


def stored(world):
    return list_tests(world.root, SUBJECT).tests[0]


# -- RunResult -----------------------------------------------------------------


def test_run_result_says_whether_it_completed_or_is_empty():
    done = RunResult("record", "completed", "finished", 3, 3, 0, 2, Path("x"), FINISHED_AT)
    assert done.is_complete and not done.is_empty
    quit_ = RunResult("record", "ended_early", "operator_quit", 3, 0, 0, 0, Path("x"), FINISHED_AT)
    assert not quit_.is_complete and quit_.is_empty


class FakeTask:
    def __init__(self, trials, planned, done):
        self.trials, self.targets, self.is_done = trials, [0] * planned, done


def trial(**kw):
    return TrialRecord(
        trial_id=0, task_id="click_grid", target_x=0.5, target_y=0.5, target_radius_px=60.0,
        t_target_shown_ns=0, **kw,
    )


def test_run_result_from_task_counts_the_trials_like_the_metadata():
    trials = [trial(is_hit=True), trial(is_timeout=True), trial(is_skipped=True), trial(is_hit=True)]
    got = run_result_from_task("record", FakeTask(trials, 6, False), Path("run"), FINISHED_AT)
    assert (got.planned, got.completed, got.skipped, got.hits) == (6, 4, 1, 2)
    assert (got.outcome, got.ended_by) == ("ended_early", "operator_quit")
    assert got.session_dir == Path("run") and got.finished_at == FINISHED_AT
    finished = run_result_from_task("practice", FakeTask(trials, 4, True), None, FINISHED_AT)
    assert (finished.outcome, finished.ended_by, finished.session_dir) == ("completed", "finished", None)
    forced = run_result_from_task("record", FakeTask(trials, 4, True), Path("r"), FINISHED_AT, ended_by="operator_quit")
    assert forced.ended_by == "operator_quit"


def test_the_practice_line_only_after_a_finished_practice():
    done = RunResult("practice", "completed", "finished", 3, 3, 0, 3, None, FINISHED_AT)
    assert practice_result_text(done) == (
        "Practice finished: 3 of 3 selected. You can practice again or press Start."
    )
    two = RunResult("practice", "completed", "finished", 3, 3, 0, 2, None, FINISHED_AT)
    assert practice_result_text(two).startswith("Practice finished: 2 of 3 selected.")
    quit_ = RunResult("practice", "ended_early", "operator_quit", 3, 1, 0, 1, None, FINISHED_AT)
    assert practice_result_text(quit_) is None  # Quit returns at once and says nothing
    record_run = RunResult("record", "completed", "finished", 3, 3, 0, 3, Path("x"), FINISHED_AT)
    assert practice_result_text(record_run) is None


# -- Save ------------------------------------------------------------------------


def test_save_locks_the_test_and_caches_the_report(world):
    out = finish_run(
        result_for(world), SAVE, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert out.action == SAVE and out.report is None
    test = stored(world)
    assert test.status == STATUS_DONE and out.test == test
    assert (test.session_dir, test.planned_trials, test.completed_trials) == (world.folder.name, 3, 3)
    assert test.completed_at == FINISHED_AT
    report = json.loads((world.folder / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert report["report_version"] == REPORT_VERSION and len(report["trials"]) == 3


def test_the_cached_report_is_exactly_a_rebuild(world):
    """AD1: the cache is the same text a fresh build gives (it moved here from the run's end)."""
    from src.data.report_cache import build_report, report_json

    finish_run(
        result_for(world), SAVE, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    text = (world.folder / REPORT_FILENAME).read_text(encoding="utf-8")
    assert text == report_json(build_report(world.folder))


def test_a_saved_partial_run_gets_a_report_with_the_partial_banner(world, tmp_path):
    partial = write_session(
        world.root / "2026-10-06_P001_click_grid_run2",
        records3()[:1],
        meta=dict(RIG_META, planned_trials=3, completed_trials=1, outcome="ended_early"),
    )
    result = RunResult("record", "ended_early", "operator_quit", 3, 1, 0, 1, partial, FINISHED_AT)
    finish_run(result, SAVE, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id)
    report = json.loads((partial / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert report["quality"]["warnings"][0]["text"] == "Ended early — 1 of 3 trials"
    assert report["session"]["outcome"] == "ended_early"


def test_save_partial_marks_the_test_ended_early(world):
    out = finish_run(
        result_for(world, completed=1, planned=3, outcome="ended_early"),
        SAVE,
        output_root=world.root,
        subject_id=SUBJECT,
        test_id=world.test.test_id,
    )
    assert out.test.status == STATUS_ENDED_EARLY == stored(world).status
    assert (stored(world).completed_trials, stored(world).planned_trials) == (1, 3)
    assert (world.folder / REPORT_FILENAME).is_file()  # a saved partial run gets its report too


def test_save_and_view_hands_back_the_report_and_caches_it(world):
    out = finish_run(
        result_for(world), SAVE_AND_VIEW, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert out.action == SAVE_AND_VIEW and stored(world).status == STATUS_DONE
    assert out.report is not None and len(out.report["trials"]) == 3
    assert (world.folder / REPORT_FILENAME).is_file()  # built through load_or_build_report, cached


def test_save_and_view_uses_the_report_that_is_already_there(world, monkeypatch):
    first = finish_run(
        result_for(world), SAVE, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert first.report is None
    # a second test for a second view of the same folder: the cache is read, not rebuilt
    other = create_test(world.root, SUBJECT, "click_grid")
    monkeypatch.setattr(
        "src.data.report_cache.build_report", lambda _d: pytest.fail("rebuilt a cached report")
    )
    out = finish_run(
        result_for(world), SAVE_AND_VIEW, output_root=world.root, subject_id=SUBJECT, test_id=other.test_id
    )
    assert out.report is not None


def test_a_report_bug_never_undoes_a_save(world, monkeypatch):
    def boom(_folder):
        raise RuntimeError("analysis bug")

    monkeypatch.setattr("src.data.report_cache.build_report", boom)
    save = finish_run(
        result_for(world), SAVE, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert save.test.status == STATUS_DONE and not (world.folder / REPORT_FILENAME).exists()
    other = create_test(world.root, SUBJECT, "click_grid")
    view = finish_run(
        result_for(world), SAVE_AND_VIEW, output_root=world.root, subject_id=SUBJECT, test_id=other.test_id
    )
    assert view.test.status == STATUS_DONE and view.report is None  # saved; the page says why


def test_saving_twice_is_refused_and_nothing_changes(world):
    args = dict(output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id)
    finish_run(result_for(world), SAVE, **args)
    before = stored(world)
    with pytest.raises(TestLockedError):
        finish_run(result_for(world, completed=1, outcome="ended_early"), SAVE, **args)
    assert stored(world) == before


# -- Discard ---------------------------------------------------------------------


def test_discard_deletes_the_folder_and_leaves_the_test_not_done(world):
    before = stored(world)
    out = finish_run(
        result_for(world), DISCARD, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert out.action == DISCARD and out.test is None and out.report is None
    assert not world.folder.exists()  # U14: permanently deleted
    assert stored(world) == before and stored(world).status == STATUS_NOT_DONE  # re-runnable
    assert world.root.is_dir()


def test_a_discarded_run_never_builds_a_report(world, monkeypatch):
    """HD1 / the P4 carry-forward: no ``report.json`` is ever built for a run that is thrown away."""
    calls: list[object] = []
    monkeypatch.setattr(run_result, "write_report_safely", lambda d: calls.append(d))
    monkeypatch.setattr(run_result, "load_or_build_report", lambda d: calls.append(d))
    finish_run(
        result_for(world), DISCARD, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
    )
    assert calls == []
    assert not (world.folder / REPORT_FILENAME).exists()


def test_discard_only_touches_a_session_folder_inside_the_root(world, tmp_path):
    outside = write_session(tmp_path / "2026-10-06_P001_click_grid_run9", records3(), meta=dict(RIG_META))
    bad = RunResult("record", "completed", "finished", 3, 3, 0, 2, outside, FINISHED_AT)
    with pytest.raises(SessionDiscardError):
        finish_run(bad, DISCARD, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id)
    assert outside.is_dir() and world.folder.is_dir()


def test_a_practice_result_cannot_be_saved_or_discarded(world):
    practice = result_for(world, run_mode="practice", folder=False)
    for action in (SAVE, SAVE_AND_VIEW, DISCARD):
        with pytest.raises(ValueError):
            finish_run(practice, action, output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id)


def test_an_unknown_action_is_refused_before_anything_happens(world):
    with pytest.raises(ValueError):
        finish_run(
            result_for(world), "keep", output_root=world.root, subject_id=SUBJECT, test_id=world.test.test_id
        )
    assert world.folder.is_dir() and stored(world).status == STATUS_NOT_DONE
