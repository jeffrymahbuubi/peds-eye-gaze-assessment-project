"""The ``(value, label)`` lists behind the configuration page's radio groups and the
settings dialog's combos (split out of :mod:`src.ui.settings_registry`, which re-exports
them). Qt-free, so the registry and its tests stay headless.
"""

from __future__ import annotations

from ..engine.input_choice import (
    POINTER_GAZE,
    POINTER_MOUSE,
    SELECTION_DWELL,
    SELECTION_SWITCH,
)
from ..engine.target_size import SIZE_NAMES, SIZE_PRESETS_DEG
from ..tasks.follow_moving import MOTION_PATH_LABELS, PATHS

# Target size presets (SPEC-target-size-and-motion-paths.md S4.1/S4.5): (value
# stored in target.size, label). The dialog appends the diameter in px on the
# operator's own monitor, which only it can know.
TARGET_SIZE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (name, f"{SIZE_NAMES[name]} ({degrees:g}°)")
    for name, degrees in SIZE_PRESETS_DEG.items()
)

# follow_moving's movement paths (SPEC-target-size-and-motion-paths.md S4.4):
# (value stored in motion.path, label shown in the dialog).
MOTION_PATH_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (path, MOTION_PATH_LABELS[path]) for path in PATHS
)

# The two input choices of a test (SPEC-input-selection-and-follow.md H1, 4.1): what moves
# the pointer, and how a target is selected. Stored as ``input.pointer`` /
# ``input.selection`` in the test's structural configuration; ``input_mode`` is derived
# from them (:func:`~src.engine.input_choice.derive_input_mode`).
INPUT_POINTER_CHOICES: tuple[tuple[str, str], ...] = (
    (POINTER_GAZE, "Gaze"),
    (POINTER_MOUSE, "Mouse"),
)
INPUT_SELECTION_CHOICES: tuple[tuple[str, str], ...] = (
    (SELECTION_DWELL, "Dwell: keep looking at the target"),
    (SELECTION_SWITCH, "Switch: look at the target, then press the switch"),
)
