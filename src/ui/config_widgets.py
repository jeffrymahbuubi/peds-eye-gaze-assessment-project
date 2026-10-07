"""Building blocks shared by the configuration page and the settings dialog
(SPEC-compass-task-flow.md 4B.1, 4B.3, 4B.7).

Kept here so :class:`~src.ui.task_config_page.TaskConfigPage` and
:class:`~src.ui.task_settings_dialog.TaskSettingsDialog` cannot disagree about
the px figures in a size label, the canvas estimate behind the shrink hints or
the look of a combo popup:

- :func:`estimated_canvas_px`, :func:`choice_label`, :func:`style_combo_popup`:
  lifted unchanged from the dialog.
- :func:`ask_two_choice`: the themed yes/no question of the page's modals.
- :class:`RadioChoice`: a one-of group of radio buttons (4B.1: one-of = radio).
- :data:`CONFIG_TOOLTIPS`: the plain-language tooltips of the controls that have
  no ``LiveSetting.tooltip`` (the structural options and the page's own fields).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.target_size import gap_px_for, radius_px_for
from .run_dialogs import GHOST, PRIMARY, ask_choice
from .wtmh_theme import BORDER, PANEL_BG

# Plain-language tooltips (SPEC 4B.1: every structural control gets one, same
# convention as the live settings' ``LiveSetting.tooltip``), by registry key.
CONFIG_TOOLTIPS: dict[str, str] = {
    "test.name": "A name for this test. It must be different from the names of this"
    " subject's other tests.",
    "test.config_name": "A named set of settings for this subject and task. Pick a name from the"
    " list to load it, or type a new name to save the current values under it."
    " Standard is the task's default settings.",
    "test.notes": "Free-text notes about this test. They also appear on the test's report.",
    "trials": "How many trials the test runs.",
    "target.size": "How big the target is, as the angle it covers at the child's eye."
    " The pixel size shown is for this monitor; every child on the same monitor gets the"
    " same size.",
    "layout.size": "How big each icon is, as the angle it covers at the child's eye."
    " The pixel size shown is for this monitor.",
    "grid.rows": "How many rows the grid has. Each cell can light up as the target.",
    "grid.cols": "How many columns the grid has. Each cell can light up as the target.",
    "grid.gap": "The space between neighbouring cells. Looking at the gap selects nothing,"
    " so a wider gap makes it less likely that a look lands on the wrong cell.",
    "layout.n_icons": "How many icons are on screen at once. One of them is the one to find.",
    "motion.path": "The route the moving target follows across the screen.",
    "motion.select_window_ms": "How long, within each trial, the moving target can be selected."
    " A shorter window is harder: the child has to catch the target while it counts.",
    "input.pointer": "What moves the pointer on the screen: the child's gaze (needs the tracker), or"
    " the mouse. A Mouse test is recorded too, and records gaze alongside when the tracker is"
    " connected and calibrated.",
    "input.selection": "How a target is selected. Dwell: keep looking at it. Switch: look at it,"
    " then press the switch (a left click on the screen, or Space / Enter).",
    "feedback.target_glow": "Show a soft glow round the target while the pointer is on it. It"
    " takes the place of the dwell ring when the target is selected with a switch, and is greyed"
    " out for Dwell.",
    "feedback.hit_sound": "Play a short sound when a target is selected."
    " Turn it off for a child who is sensitive to sound.",
    "feedback.miss_sound": "Play a short sound when a trial ends without a selection."
    " Turn it off for a child who is sensitive to sound.",
}


def estimated_canvas_px(screen: Any, app_cfg: dict[str, Any]) -> tuple[float, float]:
    """Rough size of the run canvas, for the grid-fit hint: the screen's
    available area (the real canvas only exists once the run window is up,
    and is a little smaller -- hence the hint is labelled approximate)."""
    if screen is not None:
        area = screen.availableGeometry()
        return float(area.width()), float(area.height())
    return float(app_cfg.get("screen_width_px", 1920)), float(app_cfg.get("screen_height_px", 1080))


def screen_dpr(screen: Any) -> float:
    """The device pixel ratio of ``screen`` (a QScreen, duck-typed): 1.0 without one."""
    dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
    return dpr if dpr > 0 else 1.0


def choice_label(
    key: str, value: str, label: str, mm_per_px: float, distance_mm: float, dpr: float = 1.0
) -> str:
    """A choice's label with the px it comes to on this monitor: the operator
    can't picture "5 degrees". Standard cell gap has no angle, so no px.

    The size maths is in Qt's logical px; ``dpr`` (the screen's device pixel ratio) turns
    them into the physical px of the panel, the unit the run's metadata records (FX4: at
    150 % scaling the label said 83 px for a target that is 124 px on the panel)."""
    if key in ("target.size", "layout.size"):
        diameter = 2 * radius_px_for(value, mm_per_px, distance_mm)
        return f"{label} (≈{round(diameter * dpr)} px)"
    if key == "grid.gap":
        gap = gap_px_for(value, mm_per_px, distance_mm)
        if gap is not None:
            return f"{label} (≈{round(gap * dpr)} px)"
    return label


def style_combo_popup(combo: QComboBox) -> None:
    """Same popup treatment as the Setup page's combo (setup_page.py,
    S13-S16): no inner frame, no focus rectangle, and an opaque outer
    container -- the combo's own QSS cannot reach Qt's popup frame."""
    combo.view().setFrameShape(QFrame.Shape.NoFrame)
    combo.view().setFocusPolicy(Qt.FocusPolicy.NoFocus)
    container = combo.view().parentWidget()
    if container is not None:
        container.setStyleSheet(
            f"background: {PANEL_BG}; border: 1px solid {BORDER}; "
            f"border-top: none; border-radius: 8px;"
        )


def ask_two_choice(
    parent: QWidget, title: str, text: str, accept: str, reject: str, *, default_accept: bool = True
) -> bool:
    """A themed two-button question; True when ``accept`` is chosen. The wireframe's
    modals (``task-config.md``): the safe answer is the primary (default) button, and
    Esc is ``reject``.

    It is the dashboard's own choice dialog, not Qt's stock message box: that took none of
    the theme in the live check of FX1 (dark body, dark grey buttons)."""
    buttons = [
        ("accept", accept, PRIMARY if default_accept else GHOST),
        ("reject", reject, GHOST if default_accept else PRIMARY),
    ]
    default = "accept" if default_accept else "reject"
    return ask_choice(parent, title, text, buttons, default, "reject") == "accept"


class RadioChoice(QWidget):
    """A one-of choice shown as a column of radio buttons (SPEC 4B.1, HB1).

    ``choices`` are ``(value, label)`` pairs; the value is a string, as stored in
    the task config. Each button is named ``<name_stem>_<value>`` for qt-mcp and
    tests (``cfg_target_size_small``). One button is always checked once the
    widget is built; an unknown value passed to :meth:`setValue` is ignored.
    """

    valueChanged = Signal(object)  # emits the newly checked value (a str)

    def __init__(
        self,
        name_stem: str,
        choices: Sequence[tuple[str, str]],
        value: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QRadioButton] = {}
        for choice_value, label in choices:
            button = QRadioButton(label)
            button.setObjectName(f"{name_stem}_{choice_value}")
            self._group.addButton(button)
            self._buttons[choice_value] = button
            layout.addWidget(button)
        # Checked before the signals are wired, so construction never emits.
        self.setValue(value if value in self._buttons else next(iter(self._buttons), ""))
        for choice_value, button in self._buttons.items():
            button.toggled.connect(
                lambda checked, v=choice_value: self.valueChanged.emit(v) if checked else None
            )

    def buttons(self) -> dict[str, QRadioButton]:
        return dict(self._buttons)

    def value(self) -> str:
        for choice_value, button in self._buttons.items():
            if button.isChecked():
                return choice_value
        return ""

    def setValue(self, value: str) -> None:  # noqa: N802 (Qt naming)
        button = self._buttons.get(value)
        if button is not None:
            button.setChecked(True)

    def setToolTip(self, text: str) -> None:  # noqa: N802 (Qt naming)
        """Also on every button, which the mouse is over rather than this container
        (same reason as :class:`~src.ui.slider_spin.SliderSpinRow`)."""
        super().setToolTip(text)
        for button in self._buttons.values():
            button.setToolTip(text)
