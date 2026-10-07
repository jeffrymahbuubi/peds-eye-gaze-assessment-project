"""The two setting records of ``settings_registry`` (SPEC-live-settings-panel.md section 5.1):
a live, mid-task field and a structural, pre-launch one. Split out of the registry to keep it
under the project's 500-line limit; ``settings_registry`` re-exports both, so every import
``from .settings_registry import LiveSetting`` keeps working. No PySide6 import."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MS_PER_S = 1000.0  # a stored millisecond figure is shown in seconds (``display_divisor``)


@dataclass(frozen=True, slots=True)
class LiveSetting:
    key: str  # dotted key identifying this field (matches AssessmentApp's dispatch table)
    label: str
    group: str  # "settings" (dwell.*) | "pacing" (everything else)
    kind: str  # "bool" | "int" | "float"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    applies_to: tuple[str, ...] = ()  # empty = every task
    # Plain-language explanation shown as a widget tooltip (SPEC-diki-design-
    # audit.md S8 -- ported from diki's per-slider tooltip pattern, e.g.
    # "Higher = steadier cursor, slightly slower to follow a new look").
    tooltip: str | None = None
    # A time is stored in milliseconds but shown in seconds (SPEC-compass-task-flow.md 7.1, V5):
    # 1000.0 makes the slider row's number ``value / 1000`` and its label say "(s)". Only the
    # display changes; the stored value, the profiles and the data files stay in ms.
    display_divisor: float = 1.0
    # Tasks it does not apply to even though ``applies_to`` is empty ("every task but ...").
    excludes: tuple[str, ...] = ()

    def applies(self, task_id: str) -> bool:
        return task_id not in self.excludes and (not self.applies_to or task_id in self.applies_to)


@dataclass(frozen=True, slots=True)
class StructuralSetting:
    key: str  # dotted path within the task config's "task" block, e.g. "target.radius_px"
    label: str
    kind: str  # "int" | "float" | "choice" | "bool"
    min: float = 0.0
    max: float = 0.0
    step: float = 0.0
    applies_to: tuple[str, ...] = ()
    # "choice" only (SPEC-target-size-and-motion-paths.md S4.5): (value, label)
    # pairs rendered as a combo box; the saved/overridden value is the string.
    choices: tuple[tuple[str, str], ...] = ()
    # "choice" (a string) and "bool" (a bool, SPEC-compass-task-flow.md HB3): used
    # when the task config has no value.
    default: Any = ""
    display_divisor: float = 1.0  # as on LiveSetting: 1000.0 shows a stored ms figure in seconds
    excludes: tuple[str, ...] = ()  # as on LiveSetting

    def applies(self, task_id: str) -> bool:
        return task_id not in self.excludes and (not self.applies_to or task_id in self.applies_to)
