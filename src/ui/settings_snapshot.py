"""A task's complete settings as plain data (SPEC-compass-task-flow.md 4B.4, R7, HB12).

Three pure functions, Qt-free like :mod:`.settings_registry` (which they read):

- :func:`settings_snapshot` -- every setting that applies to a task, with the value
  a merged run config holds: ``{"live": {...}, "structural": {...}}``. ``live`` is
  flat (``"dwell.threshold_ms"``), ``structural`` is nested the way
  ``TaskSettingsDialog.overrides()`` returns it (``{"target": {"size": "large"}}``),
  so the dict can be deep-merged straight over ``config["task"]``.
- :func:`complete_settings` -- the same, for values collected on the
  configuration page: what it was given laid over the task's defaults, so a
  stored configuration never depends on a later change to the YAML (HB12).
- :func:`run_settings` -- ``metadata.json``'s ``settings`` block (R7), which also
  carries the two facts the report's Theme and Feedback rows read.

The registry is the single list of what a task has to say, so "complete" means
one key per registry entry that applies to the task, no more and no less.
Nothing here writes a file: ``save_settings_profile`` stores what it is given, and
``AssessmentApp`` calls :func:`run_settings` for ``metadata.json``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..engine.config import deep_merge
from .settings_registry import (
    apply_live_values_to_config,
    get_nested,
    initial_live_values,
    initial_structural_values,
    live_settings_for_task,
    set_nested,
)


def settings_snapshot(task_id: str, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``{"live", "structural"}`` for ``task_id`` as the merged ``config`` holds them.

    Values come through the registries' own readers (``initial_live_values`` and
    ``initial_structural_values``), so a missing or no-longer-valid choice is
    already its default and the YAML's value wins over a registry fallback.
    """
    applicable = {s.key for s in live_settings_for_task(task_id)}
    structural: dict[str, Any] = {}
    for key, value in initial_structural_values(task_id, config).items():
        set_nested(structural, key, value)
    return {
        "live": {k: v for k, v in initial_live_values(config).items() if k in applicable},
        "structural": structural,
    }


def merged_config(
    config: dict[str, Any],
    live: dict[str, Any] | None = None,
    structural: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A copy of ``config`` with ``structural`` (nested) merged over its ``task`` block
    and ``live`` (flat) applied: the config a run built from a test's stored
    configuration starts with, the same merge ``AssessmentApp`` makes. ``config`` is
    not modified; keys no setting knows about are ignored."""
    merged = deepcopy(config)
    if structural:
        merged["task"] = deep_merge(merged.get("task", {}), structural)
    if live:
        apply_live_values_to_config(merged, live)
    return merged


def complete_settings(
    task_id: str,
    config: dict[str, Any],
    live: dict[str, Any] | None = None,
    structural: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """:func:`settings_snapshot` of ``config`` with ``live`` (flat) and
    ``structural`` (nested) laid over it. ``config`` is not modified; keys no
    setting knows about are ignored, like everywhere a profile is applied."""
    return settings_snapshot(task_id, merged_config(config, live, structural))


def run_settings(task_id: str, config: dict[str, Any], config_name: str | None = "") -> dict[str, Any]:
    """The ``settings`` block of a run's ``metadata.json`` (R7): ``config_name``
    (``None`` for a run that has none, the standalone launch) plus the complete
    ``live`` and ``structural`` values of the **final** merged run config.

    Two things in ``structural`` are not controls of the configuration page but
    are what the report's Theme and Feedback rows read (``report_config.py``): the
    theme name, resolved as ``AssessmentApp`` resolves it, and the YAML's
    ``feedback.particles``. They are recorded, never offered.
    """
    block = settings_snapshot(task_id, config)
    task_cfg = config.get("task", {})
    block["structural"]["theme"] = task_cfg.get("theme") or config.get("theme", {}).get(
        "name", "forest"
    )
    particles = get_nested(task_cfg, "feedback.particles")
    if isinstance(particles, bool):
        set_nested(block["structural"], "feedback.particles", particles)
    return {"config_name": config_name, **block}
