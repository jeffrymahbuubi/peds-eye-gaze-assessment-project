"""Declarative registries for the live settings panel and pre-launch task
settings dialog (SPEC-live-settings-panel.md section 5.1).

Kept dependency-light (no PySide6 import) so it can be unit-tested headlessly,
matching this project's existing convention of not testing Qt widgets
directly (see tests/test_theme_sounds.py).

Two registries, matching the SPEC's two buckets:

- ``LIVE_SETTINGS``: cheap, per-frame-read fields that are safe to change
  while a task is running (dwell/feedback toggles, smoothing, task timing).
- ``STRUCTURAL_SETTINGS``: fields baked once into a task's trial list at
  ``build_targets()`` time (grid size, radius, trial count, ...) -- these are
  only offered in the pre-launch dialog, never mid-task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine.input_choice import (
    POINTER_GAZE,
    SELECTION_DWELL,
    SELECTION_SWITCH,
    TASKS_WITHOUT_SELECTION,
)
from ..engine.target_size import DEFAULT_GAP, DEFAULT_SIZE, GAP_CHOICES
from .choice_lists import (  # re-exported: the dialog and the tests import them from here
    INPUT_POINTER_CHOICES,
    INPUT_SELECTION_CHOICES,
    MOTION_PATH_CHOICES,
    TARGET_SIZE_CHOICES,
)
from .setting_types import (  # re-exported: the two records live in setting_types.py
    MS_PER_S,
    LiveSetting,
    StructuralSetting,
)

# -- live, mid-task settings (SPEC section 5.1, regrouped per section 9) ----
#
# Grouped by field origin, not by relevance tier (SPEC section 9): "settings"
# is every dwell.* field (configs/default.yaml's global dwell: block);
# "pacing" is everything else (each task's own YAML config -- how fast/slow
# a trial moves along). Both groups are shown together on the configuration
# page (SPEC-compass-task-flow.md 4B).

LIVE_SETTINGS: list[LiveSetting] = [
    LiveSetting(
        "dwell.threshold_ms",
        "Dwell threshold (s)",
        "settings",
        "int",
        300,
        2000,
        50,
        tooltip="How long the gaze must rest on the target before it counts as a"
        " selection. Higher = fewer accidental selections, but slower to react.",
        display_divisor=MS_PER_S,
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    LiveSetting(
        "dwell.visual_cursor",
        "Show gaze cursor",
        "settings",
        "bool",
        tooltip="Show a dot at the child's current gaze position on screen.",
    ),
    LiveSetting(
        "dwell.progress_ring",
        "Show dwell progress ring",
        "settings",
        "bool",
        tooltip="Show a filling ring around the target while the dwell timer counts up.",
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    LiveSetting(
        "dwell.instant_feedback",
        "Show instant on-target ring",
        "settings",
        "bool",
        tooltip="Show an immediate ring the moment gaze lands on the target,"
        " before the dwell timer finishes.",
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    LiveSetting(
        "dwell.refractory_ms",
        "Refractory period (s)",
        "settings",
        "int",
        0,
        2000,
        50,
        tooltip="Minimum time after a selection before dwell can trigger again,"
        " to stop one long look from re-selecting the same target repeatedly.",
        display_divisor=MS_PER_S,
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    LiveSetting(
        "dwell.jitter_tolerance_px",
        "Jitter tolerance (px)",
        "settings",
        "int",
        0,
        100,
        5,
        tooltip="How far gaze can wander from the target and still count as"
        " on-target. Higher = steadier cursor, slightly less precise selection.",
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    LiveSetting(
        "dwell.smoothing.enabled",
        "Gaze smoothing enabled",
        "settings",
        "bool",
        tooltip="Smooth out small frame-to-frame jitter in the raw gaze signal.",
    ),
    LiveSetting(
        "dwell.smoothing.alpha",
        "Smoothing alpha",
        "settings",
        "float",
        0.05,
        1.0,
        0.05,
        tooltip="Lower = steadier cursor, slightly slower to follow a new look."
        " Higher = snappier cursor, more visible jitter.",
    ),
    LiveSetting(
        "task.timeout_ms",
        "Trial timeout (s)",
        "pacing",
        "int",
        1000,
        20000,
        500,
        tooltip="How long a trial waits for a selection before it counts as a timeout.",
        display_divisor=MS_PER_S,
    ),
    LiveSetting(
        "task.inter_trial_interval_ms",
        "Inter-trial interval (s)",
        "pacing",
        "int",
        0,
        3000,
        100,
        tooltip="Pause between one trial ending and the next one's target appearing.",
        display_divisor=MS_PER_S,
    ),
    LiveSetting(
        "motion.speed_frac_per_s",
        "Target speed (frac/s)",
        "pacing",
        "float",
        0.05,
        1.0,
        0.05,
        applies_to=("follow_moving",),
        tooltip="How fast the moving target travels across the screen."
        " Higher = harder to track.",
    ),
]

# A setting that reads differently on one task. Follow the Target has no timeout: its
# ``task.timeout_ms`` is how long every trial lasts (SPEC-input-selection-and-follow.md H9, I12),
# 3-30 s in half-second steps. Same key, so the stored value, the profiles and the data files
# are unchanged; only the label, range and tooltip differ.
_TASK_VARIANTS: dict[tuple[str, str], LiveSetting] = {
    ("task.timeout_ms", "follow_moving"): LiveSetting(
        "task.timeout_ms",
        "Trial duration (s)",
        "pacing",
        "int",
        3000,
        30000,
        500,
        tooltip="How long each trial lasts. The target moves for this long, whatever the child"
        " does, then the next one appears after the inter-trial interval.",
        display_divisor=MS_PER_S,
    ),
}


# -- structural, pre-launch-only settings (SPEC section 4) ------------------

STRUCTURAL_SETTINGS: list[StructuralSetting] = [
    StructuralSetting("trials", "Number of trials", "int", 1, 60, 1),
    # Every task takes its size as a preset (visual angle), never px: Target
    # size for the three target tasks, Icon size (the *visible* icon) for
    # scanning. SPEC-target-size-and-motion-paths.md S4.5 / S11.3.
    StructuralSetting(
        "target.size",
        "Target size",
        "choice",
        applies_to=("click_grid", "click_static", "follow_moving"),
        choices=TARGET_SIZE_CHOICES,
        default=DEFAULT_SIZE,
    ),
    StructuralSetting(
        "layout.size",
        "Icon size",
        "choice",
        applies_to=("scanning",),
        choices=TARGET_SIZE_CHOICES,
        default=DEFAULT_SIZE,
    ),
    StructuralSetting("grid.rows", "Grid rows", "int", 2, 6, 1, applies_to=("click_grid",)),
    StructuralSetting("grid.cols", "Grid cols", "int", 2, 6, 1, applies_to=("click_grid",)),
    # The space between two neighbouring cells, by visual angle like the sizes;
    # the dialog appends the px it comes to on this monitor. SPEC-grid-cell-gap.md
    # S4.5 -- Standard is today's board.
    StructuralSetting(
        "grid.gap",
        "Cell gap",
        "choice",
        applies_to=("click_grid",),
        choices=GAP_CHOICES,
        default=DEFAULT_GAP,
    ),
    StructuralSetting(
        "layout.n_icons", "Number of icons", "int", 2, 8, 1, applies_to=("scanning",)
    ),
    StructuralSetting(
        "motion.path",
        "Movement path",
        "choice",
        applies_to=("follow_moving",),
        choices=MOTION_PATH_CHOICES,
        default="horizontal",  # FollowMovingTask's own fallback when the YAML has no path
    ),
    # (No selection window any more: Follow the Target has nothing to select, I9/H9. An old
    # test that still carries ``motion.select_window_ms`` loads fine; nothing reads it.)
    # The two sound toggles (SPEC-compass-task-flow.md HB3): read once at
    # GuiFeedback construction, so structural. `feedback.particles` stays unexposed.
    # Follow plays the hit sound at the end of a followed trial and never a miss sound (I10).
    StructuralSetting("feedback.hit_sound", "Play hit sound", "bool", default=True),
    StructuralSetting(
        "feedback.miss_sound",
        "Play miss sound",
        "bool",
        default=True,
        excludes=TASKS_WITHOUT_SELECTION,
    ),
    # The input choices (SPEC-input-selection-and-follow.md H1): Pointer on every task,
    # Selection on the three tasks that select a target (Follow the Target has none, I9).
    StructuralSetting(
        "input.pointer",
        "Pointer (what moves the pointer)",
        "choice",
        choices=INPUT_POINTER_CHOICES,
        default=POINTER_GAZE,
    ),
    StructuralSetting(
        "input.selection",
        "Selection (how a target is selected)",
        "choice",
        excludes=TASKS_WITHOUT_SELECTION,
        choices=INPUT_SELECTION_CHOICES,
        default=SELECTION_DWELL,
    ),
    # The glow round the target while the pointer is on it (H3): drawn for a Switch
    # selection and for Follow the Target, where there is no dwell ring.
    StructuralSetting("feedback.target_glow", "Glow on target", "bool", default=True),
]


def live_settings_for_task(task_id: str) -> list[LiveSetting]:
    """The live settings that apply to ``task_id``, a task's own variant of one
    (:data:`_TASK_VARIANTS`) in place of the common entry."""
    return [_TASK_VARIANTS.get((s.key, task_id), s) for s in LIVE_SETTINGS if s.applies(task_id)]


def structural_settings_for_task(task_id: str) -> list[StructuralSetting]:
    return [s for s in STRUCTURAL_SETTINGS if s.applies(task_id)]


# -- nested dict helpers ------------------------------------------------------

_DWELL_DEFAULTS = {
    "threshold_ms": 800,
    "refractory_ms": 500,
    "jitter_tolerance_px": 40,
    "visual_cursor": True,
    "progress_ring": True,
    "instant_feedback": True,
}
_SMOOTHING_DEFAULTS = {"enabled": True, "alpha": 0.35}


def get_nested(d: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    node: Any = d
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = d
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def initial_live_values(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve each LIVE_SETTINGS default from the merged run config.

    ``dwell.*``/``dwell.smoothing.*`` come straight from the config's own
    ``dwell`` block; ``task.*`` come from the task's own YAML (already merged
    into ``config["task"]``); ``motion.*`` (follow_moving only) comes from the
    task config's ``motion`` block.
    """
    dwell_cfg = config.get("dwell", {})
    smoothing_cfg = dwell_cfg.get("smoothing", {})
    task_cfg = config.get("task", {})
    motion_cfg = task_cfg.get("motion", {})
    return {
        "dwell.threshold_ms": dwell_cfg.get("threshold_ms", _DWELL_DEFAULTS["threshold_ms"]),
        "dwell.visual_cursor": dwell_cfg.get("visual_cursor", _DWELL_DEFAULTS["visual_cursor"]),
        "dwell.progress_ring": dwell_cfg.get("progress_ring", _DWELL_DEFAULTS["progress_ring"]),
        "dwell.instant_feedback": dwell_cfg.get(
            "instant_feedback", _DWELL_DEFAULTS["instant_feedback"]
        ),
        "dwell.refractory_ms": dwell_cfg.get("refractory_ms", _DWELL_DEFAULTS["refractory_ms"]),
        "dwell.jitter_tolerance_px": dwell_cfg.get(
            "jitter_tolerance_px", _DWELL_DEFAULTS["jitter_tolerance_px"]
        ),
        "dwell.smoothing.enabled": smoothing_cfg.get("enabled", _SMOOTHING_DEFAULTS["enabled"]),
        "dwell.smoothing.alpha": smoothing_cfg.get("alpha", _SMOOTHING_DEFAULTS["alpha"]),
        "task.timeout_ms": task_cfg.get("timeout_ms", 8000),
        "task.inter_trial_interval_ms": task_cfg.get("inter_trial_interval_ms", 800),
        "motion.speed_frac_per_s": motion_cfg.get("speed_frac_per_s", 0.20),
    }


def apply_live_values_to_config(config: dict[str, Any], values: dict[str, Any]) -> None:
    """Write live values back into the merged config, in place.

    The exact inverse of :func:`initial_live_values`, and deliberately kept
    beside it: the ``motion.*`` keys are the reason a generic
    :func:`set_nested` cannot be used here, since they are read from
    ``config["task"]["motion"]`` while their key says only ``motion.``. A
    mismatch between the two functions would silently drop a restored setting.

    Used to seed a run from a carried-over or saved profile
    (SPEC-live-settings-panel.md S10.3) *before* ``initial_live_values`` runs,
    so the config stays the single source of truth and the task, the engine
    objects and the panel cannot disagree about what is in effect.

    **Unknown keys are ignored**, which is what lets a profile written by an
    older or newer build load without breaking the run (S10.5.3).
    """
    known = {s.key for s in LIVE_SETTINGS}
    for key, value in values.items():
        if key not in known:
            continue
        if key.startswith("motion."):
            set_nested(config.setdefault("task", {}), key, value)
        else:
            set_nested(config, key, value)


def initial_structural_values(task_id: str, config: dict[str, Any]) -> dict[str, Any]:
    task_cfg = config.get("task", {})
    return {
        s.key: _initial_structural_value(s, task_cfg)
        for s in structural_settings_for_task(task_id)
    }


def _initial_structural_value(setting: StructuralSetting, task_cfg: dict[str, Any]) -> Any:
    if setting.kind == "bool":
        # The task config's own switch (a profile merged over it), else the default.
        value = get_nested(task_cfg, setting.key, setting.default)
        return value if isinstance(value, bool) else setting.default
    if setting.kind != "choice":
        return get_nested(task_cfg, setting.key, setting.min)
    # A choice yields the task config's string (the YAML's default, or what a
    # saved profile merged over it), falling back to the setting's own default
    # for a missing or no-longer-valid value.
    value = get_nested(task_cfg, setting.key, setting.default)
    return value if value in {v for v, _label in setting.choices} else setting.default


# -- configuration page layout (SPEC-compass-task-flow.md 4B.1, 4B.2) ----------


@dataclass(frozen=True, slots=True)
class ConfigControl:
    key: str  # a registry key, or "test.name" / "test.config_name" / "test.notes"
    layer: str  # "live" | "structural" | "page"
    # line_edit | combo_edit | notes | check | slider_int | slider_float | radio
    widget: str
    label: str
    depends_on: str | None = None  # key of a check box that greys this one while it is off
    setting: LiveSetting | StructuralSetting | None = None  # None for a "page" control
    # ``(key of a radio group, value)``: greyed while that group holds that value
    # (SPEC-input-selection-and-follow.md 4.1). A page without the group (Follow has
    # no Selection) never greys it.
    greyed_by: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ConfigGroup:
    id: str  # the card's object-name stem ("test", "feedback", "target", ...)
    title: str
    column: int  # 0, 1 or 2: columns A, B, C of 4B.1
    controls: tuple[ConfigControl, ...]
    hint: str | None = None  # HINT_*: the amber fit hint shown under the controls


HINT_GRID_FIT, HINT_ICON_FIT = "grid_fit", "icon_fit"
# The page's own controls: not options of a task, so no registry entry.
_PAGE_CONTROLS = {
    "test.name": ("Test Name", "line_edit"),
    "test.config_name": ("Configuration Name", "combo_edit"),
    "test.notes": ("Notes", "notes"),
}
_WIDGET_BY_KIND = {"bool": "check", "int": "slider_int", "float": "slider_float", "choice": "radio"}
# 4B.3: greyed in place, never hidden, while the control it names is off.
_DEPENDS_ON = {"dwell.smoothing.alpha": "dwell.smoothing.enabled"}
# 4.1, greyed in place the same way, but by what Selection says: Switch has no dwell
# threshold and no dwell ring; Dwell has no glow. The refractory period and the jitter
# tolerance stay active under Switch -- the debounce and the hitbox apply to it too.
_GREYED_BY = {
    "dwell.threshold_ms": ("input.selection", SELECTION_SWITCH),
    "dwell.progress_ring": ("input.selection", SELECTION_SWITCH),
    "feedback.target_glow": ("input.selection", SELECTION_DWELL),
}
# The cards in order of clinical weight (SPEC-design-system-phase2.md H6, V4): (id, title,
# column, hint, control keys in order). Column 0 holds what the clinician sets first (the
# test, the input, the target or icons), column 1 the task's own card, the timing and the
# feedback, column 2 the advanced Dwell and Gaze Smoothing (under an "Advanced" title). A key
# the task has no setting for is skipped and a card left empty is dropped, so one table lays
# out all four pages (scanning has Icons where the others have Target; only click_grid has a
# grid; Icons stays one card, size and count together).
_CARDS = (
    ("test", "Test", 0, None, ("test.name", "test.config_name", "trials", "test.notes")),
    ("input", "Input", 0, None, ("input.pointer", "input.selection")),
    ("target", "Target", 0, None, ("target.size",)),
    ("icons", "Icons", 0, HINT_ICON_FIT, ("layout.size", "layout.n_icons")),
    ("grid", "Grid Layout", 1, HINT_GRID_FIT, ("grid.rows", "grid.cols", "grid.gap")),
    ("motion", "Motion", 1, None, ("motion.path", "motion.speed_frac_per_s")),
    ("timing", "Timing", 1, None, ("task.timeout_ms", "task.inter_trial_interval_ms")),
    ("feedback", "Feedback", 1, None, (
        "dwell.visual_cursor", "dwell.progress_ring", "dwell.instant_feedback",
        "feedback.target_glow", "feedback.hit_sound", "feedback.miss_sound")),
    ("selection", "Dwell", 2, None, (
        "dwell.threshold_ms", "dwell.refractory_ms", "dwell.jitter_tolerance_px")),
    ("smoothing", "Gaze Smoothing", 2, None, ("dwell.smoothing.enabled", "dwell.smoothing.alpha")),
)


def config_groups_for_task(task_id: str) -> list[ConfigGroup]:
    """The configuration page for ``task_id`` as data: its cards in order, each
    control with the widget kind that edits it (a one-of is ``radio``, a number
    a slider row, on/off a ``check``) and what greys it (4B.2, 4B.3).

    Pure, so a test can hold it against the registries: every setting that
    applies to the task has exactly one control, none hidden (AB1, AB2), and
    the page widget (``TaskConfigPage``) is just a renderer of this.
    """
    known: dict[str, ConfigControl] = {}
    for layer, settings in (
        ("live", live_settings_for_task(task_id)),
        ("structural", structural_settings_for_task(task_id)),
    ):
        for s in settings:
            known[s.key] = ConfigControl(
                s.key, layer, _WIDGET_BY_KIND[s.kind], s.label, _DEPENDS_ON.get(s.key), s,
                _GREYED_BY.get(s.key),
            )
    for key, (label, widget) in _PAGE_CONTROLS.items():
        known[key] = ConfigControl(key, "page", widget, label)
    groups = []
    for group_id, title, column, hint, keys in _CARDS:
        controls = tuple(known[key] for key in keys if key in known)
        if controls:
            groups.append(ConfigGroup(group_id, title, column, controls, hint))
    return groups
