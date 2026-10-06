"""Display names and one-line descriptions of the four tasks.

Moved out of ``src/ui/tasks_page.py`` (SPEC-compass-task-flow.md 4A.1) so the
Qt-free test store (:mod:`src.engine.subject_tests`) can name default tests
without importing a widget module. The UI pages import it from here.
"""

from __future__ import annotations

# (display name, one-line description) -- text lifted from docs/wireframes/tasks.md
# so the real UI matches the reviewed mockup, not re-worded independently.
# The grid label has no "(3×3)": rows and columns are configurable.
TASK_INFO: dict[str, tuple[str, str]] = {
    "click_static": ("Static Click", "One still target on an empty field — baseline look-and-select."),
    "click_grid": ("Grid Click", "One cell of a visible 3x3 board lights up — selection among candidates."),
    "follow_moving": ("Follow & Click", "The target travels; select it while it moves — smooth pursuit."),
    "scanning": ("Scanning Search", "Find the cued shape in a 2D field of distractors — visual search."),
}
