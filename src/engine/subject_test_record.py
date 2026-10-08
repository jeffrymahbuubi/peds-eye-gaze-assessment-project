"""One Test List record: the dataclass, how it is read back, and the name rules.

Split out of :mod:`src.engine.subject_tests` (SPEC-compass-task-flow.md 4A) to
keep that module under the 500-line rule; callers import everything from
``subject_tests``, which re-exports the public names. Qt-free.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .task_info import TASK_INFO
from .task_runner import TASK_REGISTRY

SCHEMA_VERSION = 2  # 2: run_dir (relative to the subject folder) replaced session_dir
MAX_NAME_LEN = 60  # R10; the Configuration Name keeps its own 40-character limit (4B)
MAX_SEED = 999_999  # R3; practice (1_000_000 + k) and preview use seeds above this range
STANDARD_CONFIGURATION_NAME = "Standard"

STATUS_NOT_DONE = "not_done"
STATUS_DONE = "done"
STATUS_ENDED_EARLY = "ended_early"
_STATUSES = (STATUS_NOT_DONE, STATUS_DONE, STATUS_ENDED_EARLY)
OUTCOME_COMPLETED = "completed"
OUTCOME_ENDED_EARLY = "ended_early"
_OUTCOMES = (OUTCOME_COMPLETED, OUTCOME_ENDED_EARLY)
ORIGIN_CREATED = "created"
ORIGIN_COPIED = "copied"


def standard_configuration() -> dict[str, Any]:
    """'Standard' means the task defaults: a name and nothing to override."""
    return {"name": STANDARD_CONFIGURATION_NAME, "structural": {}, "live": {}}


@dataclass
class SubjectTest:
    test_id: str
    subject_id: str  # verbatim, stripped; authoritative (the folder name is only a locator)
    name: str
    task_id: str
    created_at: str  # local time + offset
    origin: str = ORIGIN_CREATED
    # A snapshot, never a reference: editing or deleting a saved configuration
    # later cannot change an existing test. Same shapes as a settings profile.
    configuration: dict[str, Any] = field(default_factory=standard_configuration)
    notes: str = ""
    evaluator: str = ""
    seed: int = 0
    status: str = STATUS_NOT_DONE
    completed_at: str | None = None
    planned_trials: int | None = None
    completed_trials: int | None = None
    outcome: str | None = None
    run_dir: str | None = None  # "runs/<task>/<name>", relative to the subject folder (H4)
    schema_version: int = SCHEMA_VERSION

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "test_id": self.test_id,
            "subject_id": self.subject_id,
            "name": self.name,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "origin": self.origin,
            "configuration": self.configuration,
            "notes": self.notes,
            "evaluator": self.evaluator,
            "seed": self.seed,
            "status": self.status,
            "completed_at": self.completed_at,
            "planned_trials": self.planned_trials,
            "completed_trials": self.completed_trials,
            "outcome": self.outcome,
            "run_dir": self.run_dir,
        }


# -- reading a record --------------------------------------------------------


def normalise_configuration(value: Any) -> dict[str, Any]:
    """A deep copy of ``value`` with ``name`` / ``structural`` / ``live`` guaranteed.

    Other keys are kept (4B owns them); a non-dict reads as Standard.
    """
    if not isinstance(value, dict):
        return standard_configuration()
    cfg = copy.deepcopy(value)
    name = cfg.get("name")
    cfg["name"] = name.strip() if isinstance(name, str) and name.strip() else STANDARD_CONFIGURATION_NAME
    for key in ("structural", "live"):
        if not isinstance(cfg.get(key), dict):
            cfg[key] = {}
    return cfg


def _opt_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _str_or(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def parse_record(data: Any, stem: str) -> SubjectTest | None:
    """One record dict -> ``SubjectTest``, or ``None`` if it is not a usable test.

    Required: string ``test_id`` (equal to the file name ``stem``), ``subject_id``,
    ``name`` and a ``task_id`` in ``TASK_REGISTRY``. Everything else is optional
    and falls back to a default; an unknown ``status`` reads as done if the
    record has a ``run_dir``, else not done (4A.2).
    """
    if not isinstance(data, dict):
        return None
    test_id, subject_id, name, task_id = (data.get(k) for k in ("test_id", "subject_id", "name", "task_id"))
    if not all(isinstance(v, str) and v.strip() for v in (test_id, subject_id, name, task_id)):
        return None
    if test_id != stem or task_id not in TASK_REGISTRY:
        return None
    run_dir = _opt_str(data.get("run_dir"))
    status = data.get("status")
    if status not in _STATUSES:
        status = STATUS_DONE if run_dir else STATUS_NOT_DONE
    outcome = data.get("outcome")
    if status == STATUS_NOT_DONE:
        outcome = None
    elif outcome not in _OUTCOMES:
        outcome = OUTCOME_COMPLETED if status == STATUS_DONE else OUTCOME_ENDED_EARLY
    seed = _opt_int(data.get("seed"))
    return SubjectTest(
        test_id=test_id,
        subject_id=subject_id.strip(),
        name=name.strip(),
        task_id=task_id,
        created_at=_str_or(data.get("created_at"), ""),
        origin=_str_or(data.get("origin"), ORIGIN_CREATED),
        configuration=normalise_configuration(data.get("configuration")),
        notes=_str_or(data.get("notes"), ""),
        evaluator=_str_or(data.get("evaluator"), ""),
        seed=seed if seed is not None and 0 <= seed <= MAX_SEED else 0,
        status=status,
        completed_at=_opt_str(data.get("completed_at")),
        planned_trials=_opt_int(data.get("planned_trials")),
        completed_trials=_opt_int(data.get("completed_trials")),
        outcome=outcome,
        run_dir=run_dir,
    )


# -- names -------------------------------------------------------------------


def validate_test_name(name: str, existing_names, *, exclude: str | None = None) -> str | None:
    """Error text for ``name``, or ``None`` if it is acceptable (R10).

    1-60 characters after trimming, no control characters, unique among
    ``existing_names`` case-insensitively on the trimmed value. ``exclude`` is
    the test's own current name, so renaming a test to itself (or changing
    only its case) is allowed.
    """
    value = name.strip() if isinstance(name, str) else ""
    if not value:
        return "Enter a test name."
    if len(value) > MAX_NAME_LEN:
        return f"A test name can be at most {MAX_NAME_LEN} characters ({len(value)} entered)."
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        return "A test name cannot contain control characters."
    own = exclude.strip().casefold() if isinstance(exclude, str) else None
    key = value.casefold()
    for existing in existing_names:
        other = existing.strip().casefold()
        if other == key and other != own:
            return f"A test named '{value}' already exists for this subject."
    return None


def task_display_name(task_id: str) -> str:
    return TASK_INFO.get(task_id, (task_id, ""))[0]


def next_default_name(task_id: str, existing_names) -> str:
    """``"<Task display name> <N>"`` with the smallest free ``N`` for that task."""
    taken = {n.strip().casefold() for n in existing_names}
    base = task_display_name(task_id)
    n = 1
    while f"{base} {n}".casefold() in taken:
        n += 1
    return f"{base} {n}"


def copy_name(source: SubjectTest, existing_names) -> str:
    """Next default number for an auto-named source, else ``"<name> (copy)"``, ``"(copy 2)"``."""
    base = task_display_name(source.task_id)
    if re.fullmatch(rf"{re.escape(base)} \d+", source.name.strip(), re.IGNORECASE):
        return next_default_name(source.task_id, existing_names)
    for k in range(1, 1000):
        suffix = " (copy)" if k == 1 else f" (copy {k})"
        candidate = source.name.strip()[: MAX_NAME_LEN - len(suffix)].rstrip() + suffix
        if validate_test_name(candidate, existing_names) is None:
            return candidate
    return next_default_name(source.task_id, existing_names)
