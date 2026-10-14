"""The Scanning Search settings of the search cues (SPEC-scanning-search-cues.md 4.5; page layout in
``docs/wireframes/task-config.md``, the Icons card).

Split out of :mod:`.settings_registry` to keep it under the project's 500-line limit; the registry
adds these to its own list and places them in the Icons card, under Number of icons. All apply to
``scanning`` only and are structural: stored with the test, written to ``metadata.json``
(``settings.structural.search_mode`` / ``start_dot`` / ``sample_reminder``) and shown in the report's Test Configuration.
No PySide6 import, like the registry.
"""

from __future__ import annotations

from ..tasks.search_cues import MATCH_SAMPLE, POP_OUT, TASK_ID
from .setting_types import StructuralSetting

_ONLY = (TASK_ID,)

SCANNING_STRUCTURAL: list[StructuralSetting] = [
    StructuralSetting(
        "search_mode",
        "Search mode",
        "choice",
        applies_to=_ONLY,
        choices=(
            (POP_OUT, "Pop-out: the target is the coloured icon"),
            (MATCH_SAMPLE, "Match the sample: find the shape shown first"),
        ),
        default=POP_OUT,
    ),
    StructuralSetting(
        "start_dot",
        "Start each trial from the centre",
        "bool",
        applies_to=_ONLY,
        default=False,
    ),
    StructuralSetting(
        "sample_reminder",
        "Show the shape while searching",
        "bool",
        applies_to=_ONLY,
        default=False,
    ),
]

# Greyed in place while the search mode is Pop-out: the reminder is Match the sample's only.
SCANNING_GREYED_BY: dict[str, tuple[tuple[str, str], ...]] = {
    "sample_reminder": (("search_mode", POP_OUT),),
}
