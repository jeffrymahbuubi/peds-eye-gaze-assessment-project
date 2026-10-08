"""The cards of the configuration page, built from the layout spec
(SPEC-compass-task-flow.md 4B.1-4B.3).

:class:`ConfigForm` turns :func:`~src.ui.settings_registry.config_groups_for_task`
into widgets: one ``wtmhCard`` per group in a 3-column grid, one control per setting
(a one-of is radio buttons, on/off a check box, a number a slider row). It only
*builds*: it connects no signal and holds no state of its own, so
:class:`~src.ui.task_config_page.TaskConfigPage` wires the change handling and
owns the values. It also computes the amber shrink hint, from the same pure
functions the settings dialog uses; the hint is an alert box under its card, not inside it
(SPEC-design-system-phase2.md H3). Column C is titled "Advanced" (H6).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.settings_profile import STANDARD_CONFIG_NAME
from ..engine.target_size import ScaleInfo, gap_px_for, grid_fit_hint, icon_fit_hint, radius_px_for
from ..tasks.scanning import scanning_layout_slots
from .alert_box import AlertBox
from .config_widgets import CONFIG_TOOLTIPS, RadioChoice, choice_label, style_combo_popup
from .settings_registry import (
    HINT_GRID_FIT,
    HINT_ICON_FIT,
    ConfigControl,
    ConfigGroup,
    config_groups_for_task,
    get_nested,
)
from .slider_spin import SliderSpinRow
from .wheel_guard import WheelGuard, guard_wheel

COLUMNS = 3
CONTENT_MAX_WIDTH = 1500  # 4B.1: "content max width about 1500 px"
NOTES_HEIGHT = 84  # about three lines
ADVANCED_COLUMN = 2
ADVANCED_TITLE = "Advanced"
# The "Changed from ..." caption always takes this much height, text or not (C4), so the
# cards under it never move when it appears.
MODIFIED_LINE_HEIGHT = 20


def object_name(key: str) -> str:
    """``cfg_`` + the key with dots as underscores (4B.1): ``cfg_dwell_threshold_ms``."""
    return "cfg_" + key.replace(".", "_")


class ConfigForm:
    def __init__(
        self,
        task_id: str,
        standard: dict[str, dict[str, Any]],
        config: dict[str, Any],
        scale: ScaleInfo,
        distance_mm: float,
        canvas_px: tuple[float, float],
        dpr: float = 1.0,
    ) -> None:
        """``standard`` is the task's default ``{"live", "structural"}`` snapshot (what
        each control starts at); ``config`` the merged run config (the hint reads
        its grid margin and scanning layout); ``dpr`` the screen's device pixel ratio
        (the size and gap labels show physical px)."""
        self.task_id = task_id
        self._standard = standard
        self._scale = scale
        self._distance_mm = distance_mm
        self._canvas_px = canvas_px
        self._dpr = dpr
        task_cfg = config.get("task", {})
        self._grid_margin = float(task_cfg.get("grid", {}).get("margin_frac", 0.12))
        self._layout_cfg = task_cfg.get("layout", {})

        self.controls: dict[str, QWidget] = {}  # registry key -> its one control
        self.layers: dict[str, str] = {}  # registry key -> "live" | "structural"
        self.kinds: dict[str, str] = {}  # registry key -> bool | int | float | choice
        self.dependents: list[tuple[str, list[QWidget]]] = []  # (master key, widgets greyed)
        # (radio key, value, widgets): greyed while that radio group holds that value
        # (SPEC-input-selection-and-follow.md 4.1). A control may be in both lists (the
        # smoothing alpha, SPEC-preview-gaze-pointer.md H7): it is greyed if either says so.
        self.greyed_when: list[tuple[str, str, list[QWidget]]] = []
        self.cards: dict[str, QFrame] = {}
        self.fit_hint: AlertBox | None = None
        self.fit_hint_label: QLabel | None = None
        self._hint_kind: str | None = None
        self._wheel_guard = WheelGuard()  # shared by every slider row; lives as long as the form
        # The page's own fields (not options of a task, so not in ``controls``).
        self.test_name_edit = QLineEdit()
        self.config_combo = QComboBox()
        self.notes_edit = QPlainTextEdit()
        self.modified_label = QLabel("")
        self.reset_button = QPushButton("Reset to defaults")

    def build(self) -> QWidget:
        """The scrolling content: the cards in their three columns."""
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH)
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        columns = [QVBoxLayout() for _ in range(COLUMNS)]
        for column, layout in enumerate(columns):
            layout.setSpacing(16)
            grid.addLayout(layout, 0, column)
            grid.setColumnStretch(column, 1)
        groups = config_groups_for_task(self.task_id)
        if any(g.column == ADVANCED_COLUMN for g in groups):
            title = QLabel(ADVANCED_TITLE)
            title.setObjectName("cfgAdvancedTitle")
            columns[ADVANCED_COLUMN].addWidget(title)
        for group in groups:
            columns[group.column].addWidget(self._card(group))
            if group.hint:  # the alert sits under its card, never inside it
                columns[group.column].addWidget(self._hint_box(group.hint))
        for layout in columns:
            layout.addStretch(1)
        return content

    # -- cards and controls ---------------------------------------------------

    def _card(self, group: ConfigGroup) -> QFrame:
        card = QFrame()
        card.setObjectName("wtmhCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        title = QLabel(group.title)
        title.setObjectName("wtmhSectionTitle")
        layout.addWidget(title)
        for control in group.controls:
            self._add(layout, control, solo=len(group.controls) == 1)
        self.cards[group.id] = card
        return card

    def _add(self, layout: QVBoxLayout, control: ConfigControl, solo: bool) -> None:
        setting = control.setting
        tooltip = getattr(setting, "tooltip", None) or CONFIG_TOOLTIPS.get(control.key, "")
        widget = self._widget(control)
        widget.setToolTip(tooltip)
        label: QLabel | None = None
        # A check box carries its own label, and a lone radio group needs none: the
        # card title already says what it is ("Target").
        if control.widget != "check" and not (control.widget == "radio" and solo):
            label = QLabel(control.label)
            label.setToolTip(tooltip)
            layout.addWidget(label)
        layout.addWidget(widget)
        if control.widget == "combo_edit":
            self._add_config_extras(layout)
        if setting is not None:
            self.controls[control.key] = widget
            self.layers[control.key] = control.layer
            self.kinds[control.key] = setting.kind
        if control.depends_on:
            self.dependents.append((control.depends_on, [w for w in (label, widget) if w]))
        if control.greyed_by:
            master, value = control.greyed_by
            self.greyed_when.append((master, value, [w for w in (label, widget) if w]))

    def _widget(self, control: ConfigControl) -> QWidget:
        kind, key = control.widget, control.key
        if kind == "line_edit":
            self.test_name_edit.setObjectName("cfgTestName")
            return self.test_name_edit
        if kind == "combo_edit":
            combo = self.config_combo
            combo.setObjectName("cfgConfigName")
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.addItem(STANDARD_CONFIG_NAME)
            style_combo_popup(combo)
            # A wheel over it would change the selection and load a configuration.
            guard_wheel(combo, self._wheel_guard)
            return combo
        if kind == "notes":
            self.notes_edit.setObjectName("cfgNotes")
            self.notes_edit.setFixedHeight(NOTES_HEIGHT)
            self.notes_edit.setTabChangesFocus(True)  # Tab moves on, it does not type a tab (H13)
            return self.notes_edit
        setting = control.setting
        initial = (
            self._standard["live"].get(key)
            if control.layer == "live"
            else get_nested(self._standard["structural"], key)
        )
        if kind == "check":
            widget: QWidget = QCheckBox(control.label)
            widget.setChecked(bool(initial))
        elif kind == "radio":
            choices = [
                (
                    value,
                    choice_label(
                        key, value, label, self._scale.mm_per_px, self._distance_mm, self._dpr
                    ),
                )
                for value, label in setting.choices
            ]
            widget = RadioChoice(object_name(key), choices, str(initial))
        else:  # slider_int | slider_float
            widget = SliderSpinRow(
                setting.kind, setting.min, setting.max, setting.step, initial,
                display_divisor=setting.display_divisor,  # a time shown in seconds (V5)
            )
            # The page scrolls at 125 / 150 % scaling: a wheel over a slider must scroll it,
            # not change the value (a slider or spin box without focus ignores the wheel).
            guard_wheel(widget, self._wheel_guard)
        widget.setObjectName(object_name(key))
        return widget

    def _add_config_extras(self, layout: QVBoxLayout) -> None:
        """Under the Configuration Name: the "Changed from ..." line and [Reset to defaults]."""
        self.modified_label.setObjectName("wtmhCaption")
        self.modified_label.setFixedHeight(MODIFIED_LINE_HEIGHT)  # always there (C4)
        self.reset_button.setObjectName("cfgReset")
        self.reset_button.setAutoDefault(False)
        self.reset_button.setToolTip(
            "Back to the Standard configuration with every value at its default."
            " Test Name and Notes are kept. Nothing is saved yet."
        )
        row = QHBoxLayout()
        row.addWidget(self.reset_button)
        row.addStretch(1)
        layout.addWidget(self.modified_label)
        layout.addLayout(row)

    # -- the amber shrink hint (4B.3) -----------------------------------------------

    def _hint_box(self, kind: str) -> AlertBox:
        """The warning alert of a card with a hint (stacked: the column is narrow); hidden
        until :meth:`update_hint` has something to say."""
        self._hint_kind = kind
        self.fit_hint = AlertBox("warning", stacked=True)
        self.fit_hint_label = self.fit_hint.label
        self.fit_hint.hide()
        return self.fit_hint

    def update_hint(self, values: dict[str, Any]) -> None:
        """Show how far the chosen size will be shrunk to fit (the text of
        :func:`~src.engine.target_size.grid_fit_hint` / ``icon_fit_hint``, the one the
        settings dialog shows), or hide the box when the preset fits. ``values`` is
        the form's flat ``{key: value}``."""
        if self.fit_hint is None:
            return
        mm_per_px, distance = self._scale.mm_per_px, self._distance_mm
        text: str | None = None
        if self._hint_kind == HINT_GRID_FIT:
            gap = values.get("grid.gap")
            text = grid_fit_hint(
                values["grid.rows"],
                values["grid.cols"],
                *self._canvas_px,
                radius_px_for(values["target.size"], mm_per_px, distance),
                self._grid_margin,
                gap_px_for(gap, mm_per_px, distance) if gap is not None else None,
                self._dpr,  # the px shown are the panel's, like the labels' (FX4)
            )
        elif self._hint_kind == HINT_ICON_FIT:
            n_icons = values["layout.n_icons"]
            slots = scanning_layout_slots(
                n_icons,
                str(self._layout_cfg.get("arrangement", "grid")),
                float(self._layout_cfg.get("margin_frac", 0.14)),
            )
            wanted = radius_px_for(values["layout.size"], mm_per_px, distance)
            text = icon_fit_hint(n_icons, slots, *self._canvas_px, wanted, self._dpr)
        if text is None:
            self.fit_hint.hide()
        else:
            self.fit_hint_label.setText(text)
            self.fit_hint.show()
