"""Keep the mouse wheel from changing a value while it is meant to scroll the page
(SPEC-compass-task-flow.md §9 P7a, resolved: wheel guard in P8).

At 125 / 150 % display scaling the configuration page scrolls, and a wheel turn that
happens to pass over a slider, a spin box or a combo box would change a setting without
anyone noticing. One of them that does not have the keyboard focus therefore ignores the
wheel, so the event travels on to the scroll area; click it (or Tab to it) and the wheel
works as usual.

Two parts make that work. The widget's focus policy is ``StrongFocus``: Qt's default
for a spin box is ``WheelFocus``, which hands the focus to the widget *before* the
event reaches any filter, so it would always look focused. And a :class:`WheelGuard`
event filter ignores the wheel for a widget without focus.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QSlider, QWidget


class WheelGuard(QObject):
    """An event filter shared by every guarded widget; keep a reference to it for as
    long as the widgets live."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt naming)
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(watched, QWidget)
            and not watched.hasFocus()
        ):
            # Ignored *and* filtered: the widget never sees it, and an ignored event
            # is offered to the parent, which is how the scroll area gets it.
            event.ignore()
            return True
        return False


def guard_wheel(widget: QWidget, guard: WheelGuard) -> int:
    """Guard ``widget`` and every slider, spin box or combo box inside it; returns how many.

    The slider row of the configuration page is a container, so its children are
    looked at too. Other widgets (a plain label, a text box that scrolls itself) are
    left alone.
    """
    guarded = 0
    for candidate in (widget, *widget.findChildren(QWidget)):
        if isinstance(candidate, (QSlider, QAbstractSpinBox, QComboBox)):
            candidate.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            candidate.installEventFilter(guard)
            guarded += 1
    return guarded
