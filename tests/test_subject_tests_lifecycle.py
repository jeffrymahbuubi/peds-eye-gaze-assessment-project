"""SPEC-compass-task-flow.md 4A: the per-subject Test List store, part 2 (AA4-AA8,
AA14: subjects, locks, copy, delete, action matrix, tolerant reader).

Names starting with ``Test`` are reached through the module (``store.``) so
pytest never sees them in this file's namespace.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from src.engine import subject_store
from src.engine import subject_tests as store
from src.engine.run_paths import new_run_dir
from src.engine.subject_tests import (
    ACTION_ADD,
    ACTION_CONFIGURE,
    ACTION_COPY,
    ACTION_DELETE,
    ACTION_REPORT,
    ACTION_RUN,
    allowed_actions,
    copy_test,
    create_test,
    delete_test,
    list_tests,
    record_result,
    rename_test,
    subject_tests_dir,
    update_test,
)

SUBJECT = "TESTING"
RECORD_KEYS = {
    "schema_version", "test_id", "subject_id", "name", "task_id", "created_at", "origin",
    "configuration", "notes", "evaluator", "seed", "status", "completed_at", "planned_trials",
    "completed_trials", "outcome", "run_dir",
}  # fmt: skip


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(subject_store.time, "sleep", lambda _s: None)


@pytest.fixture
def root(tmp_path) -> Path:
    return tmp_path / "sessions"


def _session_folder(root: Path) -> Path:
    """A new run folder of ``SUBJECT`` (``<subject>/runs/click_grid/<date_time>``) with a file in it."""
    folder = new_run_dir(root, SUBJECT, "click_grid")
    (folder / "trials.csv").write_text("trial_id\n0\n", encoding="utf-8")
    return folder


def _done_test(root: Path, *, planned: int = 6, completed: int = 6, name: str | None = None):
    test = create_test(root, SUBJECT, "click_grid", name=name, configuration={
        "name": "Wide", "structural": {"grid": {"rows": 3}}, "live": {"dwell.threshold_ms": 900},
    })  # fmt: skip
    return record_result(
        root, SUBJECT, test.test_id, session_dir=_session_folder(root),
        planned_trials=planned, completed_trials=completed,
    )  # fmt: skip


def _files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*"))


# -- AA4 subjects ------------------------------------------------------------


def test_tests_of_one_subject_never_appear_for_another(root):
    create_test(root, "A", "click_grid")
    create_test(root, "B", "scanning")
    assert [t.subject_id for t in list_tests(root, "A").tests] == ["A"]
    assert [t.task_id for t in list_tests(root, "B").tests] == ["scanning"]
    assert list_tests(root, "C").tests == []


def test_ids_differing_only_in_case_share_one_list(root):
    create_test(root, "jeffry", "click_grid")
    create_test(root, "JEFFRY", "click_grid")
    names = [t.name for t in list_tests(root, "Jeffry").tests]
    assert names == ["Grid Click 1", "Grid Click 2"]
    assert {t.subject_id for t in list_tests(root, "jeffry").tests} == {"jeffry", "JEFFRY"}


def test_a_record_for_a_different_subject_in_the_folder_is_skipped_silently(root):
    test = create_test(root, "A/B", "click_grid")
    # Two IDs that sanitise to the same folder must never mix: forge the clash by hand.
    path = subject_tests_dir(root, "A/B") / f"{test.test_id}.json"
    data = json.loads(path.read_text("utf-8"))
    data["subject_id"] = "someone else"
    path.write_text(json.dumps(data), encoding="utf-8")
    load = list_tests(root, "A/B")
    assert load.tests == [] and load.unreadable == []


# -- AA5 locks ---------------------------------------------------------------


@pytest.mark.parametrize("planned, completed", [(6, 6), (6, 2)])
def test_a_run_test_is_locked_but_name_notes_evaluator_stay_editable(root, planned, completed):
    test = _done_test(root, planned=planned, completed=completed)
    assert test.status == ("done" if completed >= planned else "ended_early")
    with pytest.raises(store.TestLockedError):
        update_test(root, SUBJECT, test.test_id, configuration={"name": "X", "structural": {}, "live": {}})
    with pytest.raises(store.TestLockedError):
        record_result(
            root, SUBJECT, test.test_id, session_dir=_session_folder(root),
            planned_trials=3, completed_trials=3,
        )  # fmt: skip
    assert rename_test(root, SUBJECT, test.test_id, "Renamed").name == "Renamed"
    assert update_test(root, SUBJECT, test.test_id, notes="n", evaluator="e").notes == "n"
    locked = list_tests(root, SUBJECT).tests[0]
    assert locked.configuration["name"] == "Wide"  # unchanged by the refused update
    assert (locked.name, locked.notes, locked.evaluator) == ("Renamed", "n", "e")
    assert locked.run_dir == test.run_dir  # unchanged by the refused result


def test_a_not_done_test_can_be_reconfigured(root):
    test = create_test(root, SUBJECT, "click_grid")
    new = {"name": "Big", "structural": {"trials": 9}, "live": {"dwell.threshold_ms": 1000}}
    updated = update_test(root, SUBJECT, test.test_id, configuration=new)
    assert updated.configuration == new
    assert list_tests(root, SUBJECT).tests[0].configuration == new
    assert update_test(root, SUBJECT, test.test_id).configuration == new  # no change requested


def test_record_result_sets_status_outcome_counts_date_and_run_link(root):
    test = create_test(root, SUBJECT, "click_grid")
    folder = _session_folder(root)
    done = record_result(
        root, SUBJECT, test.test_id, session_dir=folder, planned_trials=6, completed_trials=6
    )
    assert (done.status, done.outcome) == ("done", "completed")
    assert (done.planned_trials, done.completed_trials) == (6, 6)
    assert done.run_dir == f"runs/click_grid/{folder.name}"  # relative to the subject folder, never absolute
    assert done.completed_at and done.completed_at[:4].isdigit()
    assert list_tests(root, SUBJECT).tests == [done]

    early = create_test(root, SUBJECT, "click_grid")
    ended = record_result(
        root, SUBJECT, early.test_id, session_dir=folder, planned_trials=18, completed_trials=7,
        completed_at="2026-10-06T15:40:12+08:00",
    )  # fmt: skip
    assert (ended.status, ended.outcome, ended.completed_at) == (
        "ended_early", "ended_early", "2026-10-06T15:40:12+08:00",
    )  # fmt: skip


def test_record_result_refuses_a_folder_that_is_not_one_of_the_subjects_runs(root, tmp_path):
    test = create_test(root, SUBJECT, "click_grid")
    outside = tmp_path / "elsewhere" / "run1"
    outside.mkdir(parents=True)
    with pytest.raises(ValueError):
        record_result(root, SUBJECT, test.test_id, session_dir=outside, planned_trials=1, completed_trials=1)
    with pytest.raises(ValueError):
        record_result(root, SUBJECT, test.test_id, session_dir=root / "a" / "b", planned_trials=1, completed_trials=1)
    with pytest.raises(ValueError):
        record_result(root, SUBJECT, test.test_id, session_dir=root / "ok", planned_trials=-1, completed_trials=0)
    assert list_tests(root, SUBJECT).tests[0].status == "not_done"


def test_unknown_or_malformed_test_id_is_a_store_error(root):
    create_test(root, SUBJECT, "click_grid")
    for bad in ("t_0000000000", "../../x", "", "t_ZZ"):
        with pytest.raises(store.TestStoreError):
            rename_test(root, SUBJECT, bad, "X")
    other = create_test(root, "other", "click_grid")
    with pytest.raises(store.TestStoreError):  # a test of another subject is not found
        rename_test(root, SUBJECT, other.test_id, "X")


# -- AA6 copy ----------------------------------------------------------------


def test_copy_of_a_done_test_is_an_unrun_copy(root):
    original = _done_test(root)
    original = update_test(root, SUBJECT, original.test_id, notes="subject was tired", evaluator="Dr. Lin")
    copied = copy_test(root, SUBJECT, original.test_id)
    assert copied.test_id != original.test_id
    assert copied.name == "Grid Click 2" and copied.origin == "copied"
    assert copied.status == "not_done" and copied.outcome is None
    assert copied.run_dir is None and copied.completed_at is None
    assert copied.planned_trials is None and copied.completed_trials is None
    assert copied.notes == ""
    assert copied.evaluator == "Dr. Lin"  # 4A.6 lists notes, not the evaluator, among the cleared
    assert copied.configuration == original.configuration
    assert copied.seed != original.seed and 0 <= copied.seed <= 999_999
    assert copied.created_at > original.created_at

    # Mutating the copy's configuration (in memory or via update_test) never reaches the original.
    copied.configuration["structural"]["grid"]["rows"] = 5
    assert original.configuration["structural"] == {"grid": {"rows": 3}}
    new = {"name": "Other", "structural": {"grid": {"rows": 4}}, "live": {}}
    update_test(root, SUBJECT, copied.test_id, configuration=new)
    reread = {t.test_id: t for t in list_tests(root, SUBJECT).tests}
    assert reread[original.test_id].configuration["structural"] == {"grid": {"rows": 3}}
    assert reread[copied.test_id].configuration == new


def test_copy_names(root):
    assert copy_test(root, SUBJECT, create_test(root, SUBJECT, "click_grid").test_id).name == "Grid Click 2"
    custom = create_test(root, SUBJECT, "scanning", name="Warm-up")
    assert copy_test(root, SUBJECT, custom.test_id).name == "Warm-up (copy)"
    assert copy_test(root, SUBJECT, custom.test_id).name == "Warm-up (copy 2)"
    assert copy_test(root, SUBJECT, custom.test_id).name == "Warm-up (copy 3)"
    long = create_test(root, SUBJECT, "scanning", name="L" * 60)
    long_copy = copy_test(root, SUBJECT, long.test_id)
    assert long_copy.name.endswith(" (copy)") and len(long_copy.name) == 60


# -- AA7 delete --------------------------------------------------------------


def test_delete_moves_the_record_and_never_touches_session_data(root):
    test = _done_test(root)
    folder = store.run_folder_of(root, test)
    folder_before = {p.name: p.read_bytes() for p in folder.iterdir()}
    keep = create_test(root, SUBJECT, "scanning")

    delete_test(root, SUBJECT, test.test_id)

    directory = subject_tests_dir(root, SUBJECT)
    assert not (directory / f"{test.test_id}.json").exists()
    moved = directory / "_deleted" / f"{test.test_id}.json"
    assert json.loads(moved.read_text("utf-8"))["test_id"] == test.test_id
    assert list_tests(root, SUBJECT).tests == [keep]
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == folder_before
    with pytest.raises(store.TestStoreError):
        delete_test(root, SUBJECT, test.test_id)  # already gone


def test_delete_works_for_a_not_done_test_too(root):
    test = create_test(root, SUBJECT, "click_grid")
    delete_test(root, SUBJECT, test.test_id)
    assert list_tests(root, SUBJECT).tests == []
    assert (subject_tests_dir(root, SUBJECT) / "_deleted" / f"{test.test_id}.json").is_file()


# -- AA8 action matrix -------------------------------------------------------

_NOT_DONE = {ACTION_ADD, ACTION_CONFIGURE, ACTION_RUN, ACTION_COPY, ACTION_DELETE}
_RAN = {ACTION_ADD, ACTION_REPORT, ACTION_COPY, ACTION_DELETE}


@pytest.mark.parametrize(
    "status, expected",
    [(None, {ACTION_ADD}), ("not_done", _NOT_DONE), ("done", _RAN), ("ended_early", _RAN)],
)
def test_allowed_actions_matches_the_matrix(root, status, expected):
    if status is None:
        test = None
    else:
        test = create_test(root, SUBJECT, "click_grid")
        if status != "not_done":
            completed = 6 if status == "done" else 4
            test = record_result(
                root, SUBJECT, test.test_id, session_dir=_session_folder(root),
                planned_trials=6, completed_trials=completed,
            )  # fmt: skip
            assert test.status == status
    assert allowed_actions(test) == frozenset(expected)


def test_run_test_is_on_for_every_not_done_test_whatever_the_setup_gate_says(root):
    # R2: the gate is shown on the Start page; the store has no run_blocked input at all.
    assert ACTION_RUN in allowed_actions(create_test(root, SUBJECT, "click_grid"))
    assert list(inspect.signature(allowed_actions).parameters) == ["test"]


# -- AA14 tolerant reader ----------------------------------------------------


def test_garbage_files_are_skipped_counted_and_never_raise(root):
    good = [create_test(root, SUBJECT, "click_grid"), create_test(root, SUBJECT, "scanning")]
    directory = subject_tests_dir(root, SUBJECT)
    ok = json.loads((directory / f"{good[0].test_id}.json").read_text("utf-8"))

    bad = {
        "t_aaaaaaaaaa.json": "{not json at all",
        "t_bbbbbbbbbb.json": "",
        "t_cccccccccc.json": "[1, 2, 3]",
        "t_dddddddddd.json": json.dumps({**ok, "test_id": ""}),  # missing id
        "t_eeeeeeeeee.json": json.dumps({**ok, "test_id": "t_eeeeeeeeee", "task_id": "teleport"}),
        "t_ffffffffff.json": json.dumps({**ok, "test_id": "t_0123456789"}),  # id differs from file
        "t_1111111111.json": json.dumps({**ok, "test_id": "t_1111111111", "name": "  "}),
    }
    for filename, text in bad.items():
        (directory / filename).write_text(text, encoding="utf-8")
    (directory / "t_2222222222.json").write_bytes(b"\xff\xfe\x00bad utf8")

    load = list_tests(root, SUBJECT)
    assert load.tests == good
    assert sorted(p.name for p in load.unreadable) == sorted([*bad, "t_2222222222.json"])


def test_unknown_status_reads_as_done_with_a_run_else_not_done(root):
    test = create_test(root, SUBJECT, "click_grid")
    path = subject_tests_dir(root, SUBJECT) / f"{test.test_id}.json"
    data = json.loads(path.read_text("utf-8"))
    path.write_text(json.dumps({**data, "status": "mystery"}), encoding="utf-8")
    assert list_tests(root, SUBJECT).tests[0].status == "not_done"
    link = "runs/click_grid/2026-10-06_1200"
    path.write_text(json.dumps({**data, "status": "mystery", "run_dir": link}), encoding="utf-8")
    reread = list_tests(root, SUBJECT).tests[0]
    assert (reread.status, reread.outcome, reread.run_dir) == ("done", "completed", link)


def test_missing_optional_fields_read_with_defaults(root):
    test = create_test(root, SUBJECT, "click_grid")
    path = subject_tests_dir(root, SUBJECT) / f"{test.test_id}.json"
    minimal = {k: json.loads(path.read_text("utf-8"))[k] for k in ("test_id", "subject_id", "name", "task_id")}
    path.write_text(json.dumps(minimal), encoding="utf-8")
    read = list_tests(root, SUBJECT).tests[0]
    assert read.configuration == {"name": "Standard", "structural": {}, "live": {}}
    assert (read.notes, read.evaluator, read.seed, read.status) == ("", "", 0, "not_done")
    assert read.origin == "created"


def test_missing_folder_is_simply_no_tests(root):
    load = list_tests(root, "NEVER_SEEN")
    assert load.tests == [] and load.unreadable == []
    assert not root.exists()  # listing must not create anything
