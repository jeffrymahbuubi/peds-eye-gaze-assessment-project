"""Per-subject Test List store (SPEC-compass-task-flow.md 4A).

A *test* is one planned instance of a task for one subject: a name, the task,
a configuration snapshot, a random seed, and -- once it has run -- a link to
its session folder. The Tests tab lists them like Compass's Test List and
they survive across days and restarts.

One JSON file per test (``<output_root>/_tests/<subject_dirname>/<test_id>.json``)
so one bad file loses one test, and there is no read-modify-write race on a
shared list. Disk is the source of truth: every action writes first. The
reader is tolerant in the :mod:`src.engine.settings_profile` way -- a bad file
is skipped and counted, never an error -- and the lock rules live here, not
only in the UI. Kept Qt-free so it can be unit tested headlessly.

The record dataclass, its parser and the name rules are in
:mod:`src.engine.subject_test_record` and re-exported here. Class names that
start with ``Test`` carry ``__test__ = False`` so pytest does not try to
collect them when a test module imports them.
"""

from __future__ import annotations

import copy
import json
import os
import random
import re
import secrets
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .session_naming import safe_subject_dirname
from .settings_profile import TESTS_DIRNAME
from .subject_test_record import (  # noqa: F401  (re-exported)
    MAX_NAME_LEN,
    MAX_SEED,
    ORIGIN_COPIED,
    ORIGIN_CREATED,
    OUTCOME_COMPLETED,
    OUTCOME_ENDED_EARLY,
    SCHEMA_VERSION,
    STANDARD_CONFIGURATION_NAME,
    STATUS_DONE,
    STATUS_ENDED_EARLY,
    STATUS_NOT_DONE,
    SubjectTest,
    copy_name,
    next_default_name,
    normalise_configuration,
    parse_record,
    standard_configuration,
    validate_test_name,
)
from .task_runner import TASK_REGISTRY

DELETED_DIRNAME = "_deleted"

# Action ids of the Test List's button column (4A.4); ``allowed_actions`` returns a subset.
ACTION_ADD = "add"
ACTION_CONFIGURE = "configure"
ACTION_RUN = "run"
ACTION_REPORT = "report"
ACTION_COPY = "copy"
ACTION_DELETE = "delete"

# Antivirus / OneDrive can hold a freshly written file for a moment on Windows.
_REPLACE_RETRIES = 5
_REPLACE_DELAY_S = 0.04

_TEST_ID_RE = re.compile(r"t_[0-9a-f]{10}")


class TestStoreError(Exception):
    """A test could not be read, written or found. The message says why."""

    __test__ = False


class TestLockedError(TestStoreError):
    """The test has already run, so its configuration (or result) is locked."""

    __test__ = False


@dataclass
class TestListLoad:
    """What ``list_tests`` found: the readable tests, and the files it had to skip."""

    __test__ = False

    tests: list[SubjectTest]
    unreadable: list[Path]


# -- paths and disk ----------------------------------------------------------


def subject_tests_dir(output_root: str | Path, subject_id: str) -> Path:
    return Path(output_root) / TESTS_DIRNAME / safe_subject_dirname(subject_id.strip())


def _discard(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _replace_with_retry(src: Path, dst: Path) -> None:
    """``os.replace`` with a few short retries on ``PermissionError`` (4A.2)."""
    attempts = 1 + _REPLACE_RETRIES
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(_REPLACE_DELAY_S)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write ``<name>.tmp`` beside the target, flush + fsync, then replace.

    The previous file is untouched unless the replace succeeds; any failure
    removes the temp file and raises :class:`TestStoreError`. The reader only
    reads ``t_*.json``, so a stray ``.tmp`` is never listed.
    """
    try:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TestStoreError(f"Could not save {path.name}: {exc}") from exc
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(tmp, path)
    except OSError as exc:
        _discard(tmp)
        raise TestStoreError(f"Could not save {path.name}: {exc.strerror or exc}") from exc


_last_created: datetime | None = None


def _now_created() -> datetime:
    """Local now, strictly increasing within the process.

    ``list_tests`` sorts by ``created_at``; the Add dialog can create several
    tests in one second, and the clock tick can be coarser than a microsecond,
    so ties would fall back to the random id and break creation order.
    """
    global _last_created
    now = datetime.now().astimezone()
    if _last_created is not None and now <= _last_created:
        now = _last_created + timedelta(microseconds=1)
    _last_created = now
    return now


def _new_seed(avoid: int | None = None) -> int:
    """A random seed in [0, MAX_SEED] (R3); never ``avoid`` (Copy Test)."""
    rng = random.SystemRandom()
    seed = rng.randint(0, MAX_SEED)
    while seed == avoid:
        seed = rng.randint(0, MAX_SEED)
    return seed


def _new_test_id(directory: Path) -> str:
    while True:
        test_id = "t_" + secrets.token_hex(5)
        taken = (directory / f"{test_id}.json").exists()
        taken = taken or (directory / DELETED_DIRNAME / f"{test_id}.json").exists()
        if not taken:
            return test_id


# -- reading -----------------------------------------------------------------


def _same_subject(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def list_tests(output_root: str | Path, subject_id: str) -> TestListLoad:
    """Every readable test of this subject, sorted by ``(created_at, test_id)``.

    Skipped **and counted** in ``unreadable``: a file that is not JSON or not a
    dict, a missing ``test_id`` / ``subject_id`` / ``name`` / ``task_id``, a
    ``test_id`` that differs from the file name, or a ``task_id`` not in
    ``TASK_REGISTRY``. Skipped silently: a record whose subject differs
    (casefold) from ``subject_id``, so two folders that sanitise to the same
    name can never mix. A missing folder is simply "no tests".
    """
    directory = subject_tests_dir(output_root, subject_id)
    tests: list[SubjectTest] = []
    unreadable: list[Path] = []
    try:
        paths = sorted(p for p in directory.glob("t_*.json") if p.is_file())
    except OSError:
        return TestListLoad([], [])
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            unreadable.append(path)
            continue
        test = parse_record(data, path.stem)
        if test is None:
            unreadable.append(path)
        elif _same_subject(test.subject_id, subject_id):
            tests.append(test)
    tests.sort(key=lambda t: (t.created_at, t.test_id))
    return TestListLoad(tests, unreadable)


def _load(output_root: str | Path, subject_id: str, test_id: str) -> SubjectTest:
    if not isinstance(test_id, str) or not _TEST_ID_RE.fullmatch(test_id):
        raise TestStoreError(f"Unknown test id {test_id!r}.")
    path = subject_tests_dir(output_root, subject_id) / f"{test_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TestStoreError(f"Test {test_id} was not found for this subject.") from exc
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise TestStoreError(f"Test {test_id} could not be read: {exc}") from exc
    test = parse_record(data, test_id)
    if test is None or not _same_subject(test.subject_id, subject_id):
        raise TestStoreError(f"Test {test_id} was not found for this subject.")
    return test


def _save(output_root: str | Path, test: SubjectTest) -> None:
    path = subject_tests_dir(output_root, test.subject_id) / f"{test.test_id}.json"
    _atomic_write_json(path, test.to_record())


def _names(output_root: str | Path, subject_id: str) -> list[str]:
    return [t.name for t in list_tests(output_root, subject_id).tests]


def _configuration_arg(value: Any) -> dict[str, Any]:
    """Validate a caller-supplied configuration: a dict (copied), or ``None`` for Standard."""
    if value is not None and not isinstance(value, dict):
        raise ValueError("A configuration must be a dict with name / structural / live.")
    return normalise_configuration(value)


# -- actions -----------------------------------------------------------------


def create_test(
    output_root: str | Path,
    subject_id: str,
    task_id: str,
    *,
    name: str | None = None,
    configuration: dict[str, Any] | None = None,
) -> SubjectTest:
    """Add a Not Done test: default name, Standard configuration, a fresh seed."""
    subject_id = subject_id.strip()
    if not subject_id:
        raise ValueError("A Subject ID is required to add a test.")
    if task_id not in TASK_REGISTRY:
        raise ValueError(f"Unknown task '{task_id}'. Known: {sorted(TASK_REGISTRY)}")
    names = _names(output_root, subject_id)
    if name is None:
        name = next_default_name(task_id, names)
    else:
        name = name.strip()
        error = validate_test_name(name, names)
        if error:
            raise ValueError(error)
    test = SubjectTest(
        test_id=_new_test_id(subject_tests_dir(output_root, subject_id)),
        subject_id=subject_id,
        name=name,
        task_id=task_id,
        created_at=_now_created().isoformat(timespec="microseconds"),
        configuration=_configuration_arg(configuration),
        seed=_new_seed(),
    )
    _save(output_root, test)
    return test


def copy_test(output_root: str | Path, subject_id: str, test_id: str) -> SubjectTest:
    """An unrun copy of any test: same task and configuration, new id, new seed (R3).

    Status, session link, date, counts and notes are cleared (4A.6); the
    evaluator is carried over because 4A.6 does not list it among the cleared.
    """
    source = _load(output_root, subject_id, test_id)
    test = SubjectTest(
        test_id=_new_test_id(subject_tests_dir(output_root, source.subject_id)),
        subject_id=source.subject_id,
        name=copy_name(source, _names(output_root, source.subject_id)),
        task_id=source.task_id,
        created_at=_now_created().isoformat(timespec="microseconds"),
        origin=ORIGIN_COPIED,
        configuration=copy.deepcopy(source.configuration),
        evaluator=source.evaluator,
        seed=_new_seed(avoid=source.seed),
    )
    _save(output_root, test)
    return test


def rename_test(output_root: str | Path, subject_id: str, test_id: str, new_name: str) -> SubjectTest:
    """Rename in any state, Done included (it is the only way to rename a locked test)."""
    test = _load(output_root, subject_id, test_id)
    new_name = new_name.strip() if isinstance(new_name, str) else ""
    error = validate_test_name(new_name, _names(output_root, test.subject_id), exclude=test.name)
    if error:
        raise ValueError(error)
    test = replace(test, name=new_name)
    _save(output_root, test)
    return test


def update_test(
    output_root: str | Path,
    subject_id: str,
    test_id: str,
    *,
    configuration: dict[str, Any] | None = None,
    notes: str | None = None,
    evaluator: str | None = None,
) -> SubjectTest:
    """Change the configuration (Not Done only) and/or notes / evaluator (any state)."""
    test = _load(output_root, subject_id, test_id)
    changes: dict[str, Any] = {}
    if configuration is not None:
        if test.status != STATUS_NOT_DONE:
            raise TestLockedError(f"'{test.name}' has already run; its configuration is locked.")
        changes["configuration"] = _configuration_arg(configuration)
    if notes is not None:
        changes["notes"] = notes
    if evaluator is not None:
        changes["evaluator"] = evaluator.strip()
    if not changes:
        return test
    test = replace(test, **changes)
    _save(output_root, test)
    return test


def delete_test(output_root: str | Path, subject_id: str, test_id: str) -> None:
    """Soft delete: move the record to ``_deleted/``. Session folders are never touched."""
    test = _load(output_root, subject_id, test_id)
    directory = subject_tests_dir(output_root, test.subject_id)
    target = directory / DELETED_DIRNAME / f"{test_id}.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _replace_with_retry(directory / f"{test_id}.json", target)
    except OSError as exc:
        raise TestStoreError(f"Could not delete {test.name}: {exc.strerror or exc}") from exc


def record_result(
    output_root: str | Path,
    subject_id: str,
    test_id: str,
    *,
    session_dir: str | Path,
    planned_trials: int,
    completed_trials: int,
    completed_at: str | None = None,
) -> SubjectTest:
    """Link a saved run to its test and lock it. Called by the run-end Save.

    ``status`` / ``outcome`` become ``done`` / ``completed`` when
    ``completed_trials >= planned_trials``, else ``ended_early``. A second call
    raises :class:`TestLockedError`. ``session_dir`` must be a folder directly
    inside ``output_root`` and is stored by name only.
    """
    test = _load(output_root, subject_id, test_id)
    if test.status != STATUS_NOT_DONE:
        raise TestLockedError(f"'{test.name}' already has a result.")
    for label, count in (("planned_trials", planned_trials), ("completed_trials", completed_trials)):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"{label} must be a non-negative integer, got {count!r}.")
    folder = Path(session_dir)
    if not folder.name or folder.parent.resolve() != Path(output_root).resolve():
        raise ValueError(f"The session folder must be directly inside {output_root}: {session_dir}")
    finished = completed_trials >= planned_trials
    test = replace(
        test,
        status=STATUS_DONE if finished else STATUS_ENDED_EARLY,
        outcome=OUTCOME_COMPLETED if finished else OUTCOME_ENDED_EARLY,
        completed_at=completed_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        planned_trials=planned_trials,
        completed_trials=completed_trials,
        session_dir=folder.name,
    )
    _save(output_root, test)
    return test


def allowed_actions(test: SubjectTest | None) -> frozenset[str]:
    """The buttons that are on for the selected row (4A.4's matrix; ``None`` = nothing selected).

    Run Test is on for every Not Done test: the Setup gate is shown on the
    Start page, not by disabling the button (R2). View Report additionally
    needs the data folder, which the UI checks.
    """
    if test is None:
        return frozenset({ACTION_ADD})
    if test.status == STATUS_NOT_DONE:
        return frozenset({ACTION_ADD, ACTION_CONFIGURE, ACTION_RUN, ACTION_COPY, ACTION_DELETE})
    return frozenset({ACTION_ADD, ACTION_REPORT, ACTION_COPY, ACTION_DELETE})
