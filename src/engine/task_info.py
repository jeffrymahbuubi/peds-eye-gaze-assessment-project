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
    "click_static": ("Static Click", "One still target on an empty field. Baseline look and select."),
    "click_grid": ("Grid Click", "One cell of a visible board lights up. Selection among candidates."),
    "follow_moving": (
        "Follow the Target",
        "The target travels across the screen. Follow it; nothing is selected. Smooth pursuit.",
    ),
    "scanning": ("Scanning Search", "Find the cued shape among other shapes. Visual search."),
    # Offered in Add test only, never in a new subject's default test list (SPEC-scene-cause-
    # effect-task.md S8).
    "choice_making": (
        "Choice-making",
        "A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive."
        " Cause and effect, with look-back.",
    ),
}
