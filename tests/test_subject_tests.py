"""SPEC-compass-task-flow.md 4A: the per-subject Test List store, part 1 (AA1-AA3:
records, seeds, atomic writes, names). Lifecycle rules are in test_subject_tests_lifecycle.py.

Names starting with ``Test`` are reached through the module (``store.``) so
pytest never sees them in this file's namespace.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.engine import subject_tests as store
from src.engine.subject_tests import (
    copy_test,
    create_test,
    delete_test,
    list_tests,
    next_default_name,
    record_result,
    rename_test,
    subject_tests_dir,
    update_test,
    validate_test_name,
)

SUBJECT = "TESTING"
RECORD_KEYS = {
    "schema_version", "test_id", "subject_id", "name", "task_id", "created_at", "origin",
    "configuration", "notes", "evaluator", "seed", "status", "completed_at", "planned_trials",
    "completed_trials", "outcome", "session_dir",
}  # fmt: skip


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(store.time, "sleep", lambda _s: None)


@pytest.fixture
def root(tmp_path) -> Path:
    return tmp_path / "sessions"


def _session_folder(root: Path, name: str = "2026-10-06_TESTING_click_grid_run1") -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
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


# -- AA1 create + round trip -------------------------------------------------


def test_create_writes_one_record_with_every_field(root):
    test = create_test(root, SUBJECT, "click_grid")
    path = root / "_tests" / SUBJECT / f"{test.test_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == RECORD_KEYS
    assert data["schema_version"] == 1
    assert data["test_id"].startswith("t_") and len(data["test_id"]) == 12
    assert data["subject_id"] == SUBJECT
    assert data["name"] == "Grid Click 1"
    assert data["task_id"] == "click_grid"
    assert data["origin"] == "created"
    assert data["configuration"] == {"name": "Standard", "structural": {}, "live": {}}
    assert (data["notes"], data["evaluator"]) == ("", "")
    assert data["status"] == "not_done"
    assert data["completed_at"] is None and data["session_dir"] is None
    assert data["planned_trials"] is None and data["completed_trials"] is None
    assert data["outcome"] is None
    assert datetime.fromisoformat(data["created_at"]).utcoffset() is not None  # local time + offset


def test_list_returns_what_was_written(root):
    created = [create_test(root, SUBJECT, t) for t in ("click_grid", "scanning", "click_grid")]
    load = list_tests(root, SUBJECT)
    assert load.unreadable == []
    assert load.tests == created
    assert [t.name for t in load.tests] == ["Grid Click 1", "Scanning Search 1", "Grid Click 2"]


def test_list_keeps_creation_order_for_tests_made_in_one_instant(root):
    created = [create_test(root, SUBJECT, "click_static") for _ in range(12)]
    assert [t.test_id for t in list_tests(root, SUBJECT).tests] == [t.test_id for t in created]


def test_create_with_a_configuration_stores_a_deep_copy(root):
    config = {"name": "Wide", "structural": {"grid": {"rows": 3}}, "live": {}}
    test = create_test(root, SUBJECT, "click_grid", configuration=config)
    config["structural"]["grid"]["rows"] = 99
    assert list_tests(root, SUBJECT).tests[0].configuration["structural"] == {"grid": {"rows": 3}}
    assert test.configuration["structural"] == {"grid": {"rows": 3}}


def test_create_rejects_blank_subject_unknown_task_and_bad_name(root):
    with pytest.raises(ValueError):
        create_test(root, "  ", "click_grid")
    with pytest.raises(ValueError):
        create_test(root, SUBJECT, "no_such_task")
    with pytest.raises(ValueError):
        create_test(root, SUBJECT, "click_grid", name="   ")
    with pytest.raises(ValueError):
        create_test(root, SUBJECT, "click_grid", configuration=["not", "a", "dict"])
    assert not (root / "_tests").exists()  # nothing was written


def test_new_test_ids_never_collide(root):
    ids = {create_test(root, SUBJECT, "click_static").test_id for _ in range(30)}
    assert len(ids) == 30


# -- R3 seed, R9 evaluator, R1 names, R4 / R5 --------------------------------


def test_seed_is_drawn_per_test_in_range(root):
    seeds = [create_test(root, SUBJECT, "click_static").seed for _ in range(25)]
    assert all(0 <= s <= store.MAX_SEED == 999_999 for s in seeds)
    assert len(set(seeds)) > 1


def test_copy_draws_a_new_seed_even_if_the_draw_collides(root, monkeypatch):
    source = create_test(root, SUBJECT, "click_static")
    draws = iter([source.seed, source.seed, (source.seed + 1) % 1_000_000])

    class _Rng:
        def randint(self, lo, hi):
            assert (lo, hi) == (0, 999_999)
            return next(draws)

    monkeypatch.setattr(store.random, "SystemRandom", _Rng)
    assert copy_test(root, SUBJECT, source.test_id).seed == (source.seed + 1) % 1_000_000


def test_record_uses_the_r1_names_only(root):
    test = _done_test(root)
    data = json.loads((subject_tests_dir(root, SUBJECT) / f"{test.test_id}.json").read_text("utf-8"))
    assert (data["planned_trials"], data["completed_trials"], data["outcome"]) == (6, 6, "completed")
    assert "trials_planned" not in data and "trials_completed" not in data


def test_evaluator_defaults_empty_and_is_editable_in_every_state(root):
    todo = create_test(root, SUBJECT, "click_static")
    assert todo.evaluator == ""
    assert update_test(root, SUBJECT, todo.test_id, evaluator="  Dr. Lin ").evaluator == "Dr. Lin"
    done = _done_test(root)
    assert update_test(root, SUBJECT, done.test_id, evaluator="Dr. Wu").evaluator == "Dr. Wu"
    assert {t.evaluator for t in list_tests(root, SUBJECT).tests} == {"Dr. Lin", "Dr. Wu"}


def test_no_discard_marker_and_no_legacy_import_in_the_store():
    assert not hasattr(store, "mark_discarded")  # R4: a discard just leaves the test Not Done
    assert not hasattr(store, "import_legacy_sessions")  # R5


# -- AA2 atomic writes -------------------------------------------------------


def test_failed_replace_leaves_the_old_file_untouched(root, monkeypatch):
    test = create_test(root, SUBJECT, "click_grid")
    path = subject_tests_dir(root, SUBJECT) / f"{test.test_id}.json"
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk on fire")

    monkeypatch.setattr(store.os, "replace", boom)
    with pytest.raises(store.TestStoreError, match="disk on fire"):
        rename_test(root, SUBJECT, test.test_id, "Renamed")
    monkeypatch.undo()
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.tmp"))
    assert [t.name for t in list_tests(root, SUBJECT).tests] == ["Grid Click 1"]


def test_failed_first_write_creates_no_test_and_no_tmp(root, monkeypatch):
    monkeypatch.setattr(store.os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(store.TestStoreError):
        create_test(root, SUBJECT, "click_grid")
    monkeypatch.undo()
    directory = subject_tests_dir(root, SUBJECT)
    assert not list(directory.glob("*.tmp")) and not list(directory.glob("t_*.json"))
    assert list_tests(root, SUBJECT).tests == []


def test_permission_error_on_the_first_two_attempts_still_succeeds(root, monkeypatch):
    real_replace = store.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(1)
        if len(calls) <= 2:
            raise PermissionError("held by antivirus")
        real_replace(src, dst)

    monkeypatch.setattr(store.os, "replace", flaky)
    test = create_test(root, SUBJECT, "click_grid")
    monkeypatch.undo()
    assert len(calls) == 3
    assert list_tests(root, SUBJECT).tests == [test]


def test_permission_error_that_never_clears_raises_the_store_error(root, monkeypatch):
    calls = []

    def stuck(src, dst):
        calls.append(1)
        raise PermissionError("locked")

    monkeypatch.setattr(store.os, "replace", stuck)
    with pytest.raises(store.TestStoreError, match="locked"):
        create_test(root, SUBJECT, "click_grid")
    monkeypatch.undo()
    assert len(calls) == 1 + store._REPLACE_RETRIES
    assert not list(subject_tests_dir(root, SUBJECT).glob("*.tmp"))


def test_stray_tmp_file_is_never_listed(root):
    test = create_test(root, SUBJECT, "click_grid")
    directory = subject_tests_dir(root, SUBJECT)
    (directory / f"{test.test_id}.json.tmp").write_text("{half a record", encoding="utf-8")
    load = list_tests(root, SUBJECT)
    assert load.tests == [test] and load.unreadable == []


# -- AA3 / R10 names ---------------------------------------------------------


def test_default_names_count_up_and_reuse_a_freed_number(root):
    first, second = (create_test(root, SUBJECT, "click_grid") for _ in range(2))
    assert (first.name, second.name) == ("Grid Click 1", "Grid Click 2")
    delete_test(root, SUBJECT, first.test_id)
    assert create_test(root, SUBJECT, "click_grid").name == "Grid Click 1"
    assert create_test(root, SUBJECT, "click_grid").name == "Grid Click 3"
    assert create_test(root, SUBJECT, "scanning").name == "Scanning Search 1"


def test_next_default_name_is_the_smallest_free_number_case_insensitively():
    assert next_default_name("click_grid", []) == "Grid Click 1"
    assert next_default_name("click_grid", ["Grid Click 1", "grid click 3"]) == "Grid Click 2"
    assert next_default_name("follow_moving", ["Follow the Target 1"]) == "Follow the Target 2"


@pytest.mark.parametrize("bad", ["Grid Click 1", "grid click 1", "  GRID CLICK 1  "])
def test_rename_to_an_existing_name_is_rejected(root, bad):
    create_test(root, SUBJECT, "click_grid")
    other = create_test(root, SUBJECT, "click_grid")
    with pytest.raises(ValueError, match="already exists"):
        rename_test(root, SUBJECT, other.test_id, bad)
    assert [t.name for t in list_tests(root, SUBJECT).tests] == ["Grid Click 1", "Grid Click 2"]


def test_validate_test_name_rules():
    assert validate_test_name("A", []) is None
    assert validate_test_name("x" * 60, []) is None
    assert "at most 60" in validate_test_name("x" * 61, [])
    assert validate_test_name("   ", []) == "Enter a test name."
    assert validate_test_name("", []) == "Enter a test name."
    assert "control" in validate_test_name("bad\nname", [])
    assert "already exists" in validate_test_name(" Warm Up ", ["warm up"])
    # Excluding the test's own current name allows keeping it or changing only its case.
    assert validate_test_name("warm up", ["Warm Up"], exclude="Warm Up") is None
    assert "already exists" in validate_test_name("Other", ["Warm Up", "Other"], exclude="Warm Up")
    assert validate_test_name("été", []) is None


def test_rename_trims_and_persists_and_allows_own_name(root):
    test = create_test(root, SUBJECT, "click_grid")
    assert rename_test(root, SUBJECT, test.test_id, "  Warm-up  ").name == "Warm-up"
    assert rename_test(root, SUBJECT, test.test_id, "WARM-UP").name == "WARM-UP"
    assert list_tests(root, SUBJECT).tests[0].name == "WARM-UP"


def test_rename_blank_and_too_long_are_rejected(root):
    test = create_test(root, SUBJECT, "click_grid")
    for bad in ("", "   ", "x" * 61):
        with pytest.raises(ValueError):
            rename_test(root, SUBJECT, test.test_id, bad)
    assert list_tests(root, SUBJECT).tests[0].name == "Grid Click 1"
