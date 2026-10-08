"""Saved per-subject, per-task settings profiles.

SPEC-live-settings-panel.md S10. A physician tunes a task to a child during a
throwaway first run; those values must survive into the data-collection runs
that follow, and be recoverable when the same child returns another day.

Keyed **per subject and per task** rather than globally, mirroring the
calibration precedent (``<subject folder>/calibrations/``): one child's
tuning silently becoming the next child's starting point is a protocol hazard,
not a convenience.

Every save is its own file (S10.12): ``<subject folder>/settings/<task_id>/<local
date>_<local time>.json`` (the folder is found through ``subject.json``,
:mod:`src.engine.subject_store`; SPEC-subject-data-layout.md H1). Nothing is ever
overwritten, so a profile saved on one day is
still there to choose after a different one is saved the next. The pre-S10.12
flat ``<subject>/<task_id>.json`` is read as one more version and never
rewritten. Timestamps are **local** time with their UTC offset -- the date is
the label an operator picks a version by, and a UTC date is the wrong day for
any save before 08:00 in this lab's timezone (S10.12.2).

A version may carry a ``name`` (schema v2, SPEC-compass-task-flow.md 4B.4): a
named configuration resolves to its newest version and the older ones stay as
history (:func:`list_named_configurations`).

Kept Qt-free so it can be unit tested headlessly, and deliberately tolerant in
the same way as :mod:`src.engine.local_state`: a missing, empty or malformed
profile is treated as "no profile", never as an error. A saved profile is a
convenience, so a corrupt one must degrade to config defaults rather than
block a session.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .subject_store import ensure_subject, find_subject

# Bumped only if the on-disk shape changes incompatibly. Readers ignore keys
# they do not know (see ``apply_live_values_to_config``), so adding a settings
# field does not need a bump. v2 (SPEC-compass-task-flow.md 4B.4) documents the
# optional ``name`` of a named configuration; a v1 file has none and still loads.
PROFILE_SCHEMA_VERSION = 2

# A named configuration (4B.4): "Standard" is the task's own defaults -- computed
# from the YAML, never stored, and reserved. Names are 1-40 characters (R10).
STANDARD_CONFIG_NAME = "Standard"
CONFIG_NAME_MAX_LEN = 40

_FILENAME_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


def subject_settings_dir(output_root: str | Path, subject_id: str) -> Path | None:
    """``<subject folder>/settings``, or ``None`` for a subject with no folder yet."""
    folder = find_subject(output_root, subject_id)
    return folder.settings if folder is not None else None


def settings_profile_path(output_root: str | Path, subject_id: str, task_id: str) -> Path | None:
    """The pre-S10.12 single-file location. Still read, no longer written."""
    directory = subject_settings_dir(output_root, subject_id)
    return directory / f"{task_id}.json" if directory is not None else None


def settings_profile_dir(output_root: str | Path, subject_id: str, task_id: str) -> Path | None:
    """Where this subject+task's saved versions live -- and where the Load
    Settings file dialog opens, so one folder holds exactly the choice."""
    directory = subject_settings_dir(output_root, subject_id)
    return directory / task_id if directory is not None else None


def parse_saved_at(value: str) -> datetime | None:
    """ISO ``saved_at`` -> aware datetime, or ``None`` if unparseable.

    Legacy profiles carry ``+00:00`` (UTC); S10.12 ones carry the local
    offset. Both parse; a naive string (no offset) is treated as UTC, which
    is what every legacy writer produced.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_saved_at(saved_at: str, with_time: bool = True) -> str:
    """Render a profile's ``saved_at`` in **local** time, e.g. ``09/18 14:32``.

    The date is the label an operator picks a version by (S10.12), so it has
    to be the local date: slicing the stored ISO string (``saved_at[:10]``,
    as the badge and panel did before S10.12) showed the UTC date, which is
    the previous day for any save before 08:00 in this lab's timezone.
    Legacy UTC-stamped profiles and S10.12 local-offset ones both convert
    correctly. Returns "" for an empty or unparseable value.

    Lives here (moved from ``settings_registry``, which still re-exports it) so
    the unnamed-configuration label below needs nothing from the UI layer.
    """
    when = parse_saved_at(saved_at)
    if when is None:
        return ""
    local = when.astimezone()
    return local.strftime("%m/%d %H:%M" if with_time else "%m/%d")


def validate_config_name(name: str) -> str | None:
    """Error text for a configuration name, or ``None`` if it can be stored
    (SPEC-compass-task-flow.md 4B.3, R10).

    1-40 characters after trimming, no control characters, and not "Standard"
    (case-insensitive): that name is the task's computed defaults.
    """
    value = name.strip() if isinstance(name, str) else ""
    if not value:
        return "Enter a configuration name."
    if len(value) > CONFIG_NAME_MAX_LEN:
        return (
            f"A configuration name can be at most {CONFIG_NAME_MAX_LEN} characters "
            f"({len(value)} entered)."
        )
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        return "A configuration name cannot contain control characters."
    if value.casefold() == STANDARD_CONFIG_NAME.casefold():
        return f"'{STANDARD_CONFIG_NAME}' is reserved for the task defaults; choose another name."
    return None


def load_settings_profile_file(path: str | Path) -> dict[str, Any] | None:
    """Parse one saved version, or ``None`` if it isn't a usable profile.

    Missing, empty, malformed, or structurally wrong all return ``None`` --
    the caller falls back to config defaults and the run proceeds. The
    returned dict carries ``subject_id``/``task_id`` as written (so a file
    picked from the wrong folder can be refused, S10.12.4) and ``path``.
    ``name`` is the named configuration's name (schema v2, 4B.4); "" for a
    schema v1 file or any save made without one.
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    live = data.get("live")
    structural = data.get("structural")
    calibration = data.get("calibration")
    name = data.get("name")
    return {
        "name": name.strip() if isinstance(name, str) else "",
        "live": live if isinstance(live, dict) else {},
        "structural": structural if isinstance(structural, dict) else {},
        "calibration": calibration if isinstance(calibration, dict) else {},
        "saved_at": str(data.get("saved_at", "")),
        "schema_version": data.get("schema_version"),
        "subject_id": str(data.get("subject_id", "")),
        "task_id": str(data.get("task_id", "")),
        "path": str(path),
    }


def list_settings_profiles(
    output_root: str | Path, subject_id: str, task_id: str
) -> list[Path]:
    """Every usable saved version for this subject+task, **newest first**.

    Ordered by each file's own ``saved_at``, not by filename, so the legacy
    flat file (whose name carries no date) and any hand-renamed file both
    sort where they belong. Unreadable files are simply left out, per this
    module's tolerance rule. A missing folder is "no versions".
    """
    candidates: list[Path] = []
    directory = settings_profile_dir(output_root, subject_id, task_id)
    if directory is None:
        return []
    try:
        candidates.extend(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError:
        pass
    legacy = settings_profile_path(output_root, subject_id, task_id)
    if legacy is not None and legacy.is_file():
        candidates.append(legacy)

    dated: list[tuple[datetime, Path]] = []
    for path in candidates:
        profile = load_settings_profile_file(path)
        if profile is None:
            continue
        when = parse_saved_at(profile["saved_at"])
        if when is None:
            # Unparseable timestamp: keep the file reachable, sorted last.
            when = datetime.min.replace(tzinfo=timezone.utc)
        dated.append((when, path))
    # Secondary key: filename, so two saves within one second (``<stem>.json``
    # then ``<stem>_2.json``, same ``saved_at``) still come back newest first.
    dated.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    return [path for _when, path in dated]


def load_settings_profile(
    output_root: str | Path, subject_id: str, task_id: str
) -> dict[str, Any] | None:
    """Return the **newest** saved profile, or ``None`` if there isn't one.

    This was the automatic path (S10.3): a fresh sitting started from the most
    recent save. The old Tasks page's Load Settings (S10.12) chose an older
    version through :func:`load_settings_profile_file` directly; named
    configurations (:func:`list_named_configurations`, SPEC-compass-task-
    flow.md 4B.4) replaced both, and no run calls this any more.
    """
    versions = list_settings_profiles(output_root, subject_id, task_id)
    if not versions:
        return None
    return load_settings_profile_file(versions[0])


@dataclass(frozen=True)
class NamedConfig:
    """One named configuration: the newest saved version under its name."""

    name: str
    saved_at: str
    path: Path
    live: dict[str, Any]
    structural: dict[str, Any]


def effective_config_name(profile: dict[str, Any], path: str | Path = "") -> str:
    """The name a saved version is listed under (SPEC-compass-task-flow.md 4B.4).

    Its own ``name``; for a schema v1 file, a save made without a name, or a
    stored name that could not be chosen today (hand-edited to "Standard", say),
    ``Saved MM/DD HH:MM`` from its local ``saved_at``, so every old profile
    stays reachable. A timestamp that will not parse falls back to the file name.
    """
    name = profile.get("name") or ""
    if name and validate_config_name(name) is None:
        return name
    when = format_saved_at(profile.get("saved_at", ""))
    return f"Saved {when or Path(path).stem}"


def list_named_configurations(
    output_root: str | Path, subject_id: str, task_id: str
) -> list[NamedConfig]:
    """One entry per distinct effective name for this subject+task, **newest
    first** (4B.4); the Configuration Name combo shows Standard, then these.

    A name resolves to its newest version by ``saved_at`` (the order
    :func:`list_settings_profiles` already gives); older versions stay on disk
    as history and are not listed. Names compare case-insensitively, like test
    names (R10); the entry keeps the spelling of its newest version.
    """
    seen: set[str] = set()
    found: list[NamedConfig] = []
    for path in list_settings_profiles(output_root, subject_id, task_id):
        profile = load_settings_profile_file(path)
        if profile is None:  # vanished or changed since the listing
            continue
        name = effective_config_name(profile, path)
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        found.append(
            NamedConfig(name, profile["saved_at"], path, profile["live"], profile["structural"])
        )
    return found


def task_live_values(task_id: str, live: dict[str, Any]) -> dict[str, Any]:
    """``live`` limited to the keys that apply to ``task_id`` (4B.4): a static
    task's file no longer carries ``motion.speed_frac_per_s``. Keys no setting
    knows are dropped."""
    # Imported here, not at the top: settings_registry imports this module.
    from ..ui.settings_registry import live_settings_for_task

    applicable = {s.key for s in live_settings_for_task(task_id)}
    return {key: value for key, value in live.items() if key in applicable}


def save_settings_profile(
    output_root: str | Path,
    subject_id: str,
    task_id: str,
    live: dict[str, Any],
    structural: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    name: str = "",
) -> Path:
    """Write a **new** version for this subject+task; earlier ones are kept.

    ``name`` (schema v2, SPEC-compass-task-flow.md 4B.4) makes it a named
    configuration; "" is an unnamed save (listed as ``Saved MM/DD HH:MM``). A
    name that :func:`validate_config_name` refuses -- "Standard" included, it
    is never stored -- raises ``ValueError``. ``live`` is cut to the keys that
    apply to ``task_id`` (:func:`task_live_values`). ``structural`` is stored
    as given: the caller passes the task's complete block (every control; the
    configuration page's values, or ``settings_snapshot.complete_settings``).

    Called only from an explicit user action -- never automatically at the end
    of a run (S10.5.2, decided with the user): an exploratory or abandoned run
    must not be able to overwrite a profile that was working. S10.12 extends
    that to every save: nothing overwrites anything, so a same-second
    collision gets a numeric suffix rather than replacing the earlier file.

    ``calibration`` records the calibration these settings were tuned under
    (S10.5.5). It is **descriptive only** -- nothing reads it back to change
    behaviour. The reason to keep it is that settings tuned under a poor
    calibration may be compensating for bad tracking rather than suiting the
    child, and re-applying them under a good calibration would be wrong;
    without this, nothing in the profile would say which case it was.

    A subject's first save of anything creates the subject's folder.
    """
    name = name.strip()
    if name and (error := validate_config_name(name)):
        raise ValueError(error)
    now = datetime.now().astimezone()
    directory = ensure_subject(output_root, subject_id).settings / task_id
    directory.mkdir(parents=True, exist_ok=True)
    stem = now.strftime(_FILENAME_TIME_FORMAT)
    path = directory / f"{stem}.json"
    suffix = 2
    while path.exists():
        path = directory / f"{stem}_{suffix}.json"
        suffix += 1
    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "subject_id": subject_id,
        "task_id": task_id,
        "name": name,
        "saved_at": now.isoformat(timespec="seconds"),
        "live": task_live_values(task_id, live),
        "structural": dict(structural or {}),
        "calibration": dict(calibration or {}),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
