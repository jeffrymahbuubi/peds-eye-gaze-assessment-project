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

from PySide6.QtCore import Qt
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..engine.settings_profile import STANDARD_CONFIG_NAME
from ..engine.target_size import ScaleInfo, gap_px_for, grid_fit_hint, icon_fit_hint, radius_px_for
from ..tasks.scanning import scanning_layout_slots
from .alert_box import AlertBox
from .config_widgets import (
    CONFIG_TOOLTIPS,
    ElidedLabel,
    RadioChoice,
    choice_label,
    style_combo_popup,
)
from .page_layout import LABEL_GAP
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
NOTES_HEIGHT = 56  # two lines
ADVANCED_COLUMN = 2
ADVANCED_TITLE = "Advanced"
# The "Changed from ..." caption sits at the right of the Configuration Name label's row and
# always takes this much height, text or not (C4), so nothing moves when it appears.
MODIFIED_LINE_HEIGHT = 20
# Vertical rhythm of a card, all on the spacing scale (design_tokens.SPACING_SCALE): the page has
# to fit a maximized 1920x1080 window without a scroll bar (SPEC-design-system-phase2.md section
# 9, 2026-10-09). A label sits LABEL_GAP above its control, rows are ROW_GAP apart, the title's
# own 6 px margin (wtmh_theme.py) is the gap under it.
CARD_PAD_H = 16
CARD_PAD_V = 12
ROW_GAP = 8
CARD_GAP = 12  # between two cards of a column
COLUMN_GAP = 16  # between the columns


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
        # (SPEC-input-selection-and-follow.md 4.1). Disjoint from ``dependents``.
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
        self.modified_label = ElidedLabel("")
        self.reset_button = QPushButton("Reset to defaults")

    def build(self) -> QWidget:
        """The scrolling content: the cards in their three columns."""
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH)
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(COLUMN_GAP)
        columns = [QVBoxLayout() for _ in range(COLUMNS)]
        for column, layout in enumerate(columns):
            layout.setSpacing(CARD_GAP)
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
        layout.setContentsMargins(CARD_PAD_H, CARD_PAD_V, CARD_PAD_H, CARD_PAD_V)
        layout.setSpacing(0)
        title = QLabel(group.title)
        title.setObjectName("wtmhSectionTitle")
        layout.addWidget(title)  # the sheet's margin under it is the gap to the first row
        rows = QVBoxLayout()
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(ROW_GAP)
        layout.addLayout(rows)
        for control in group.controls:
            self._add(rows, control, solo=len(group.controls) == 1)
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
        if control.widget == "combo_edit":
            layout.addLayout(self._name_field(label, widget))
        elif label is not None:
            field = QVBoxLayout()  # the label LABEL_GAP above its control
            field.setContentsMargins(0, 0, 0, 0)
            field.setSpacing(LABEL_GAP)
            field.addWidget(label)
            field.addWidget(widget)
            layout.addLayout(field)
        else:
            layout.addWidget(widget)
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

    def _name_field(self, label: QLabel, combo: QComboBox) -> QVBoxLayout:
        """The Configuration Name: its label with the "Changed from ..." line at the right of
        the same row, then the box with [Reset to defaults] beside it (one row less than a
        line and a button of their own, so the card fits the window)."""
        self.modified_label.setObjectName("wtmhCaption")
        self.modified_label.setFixedHeight(MODIFIED_LINE_HEIGHT)  # always there (C4)
        self.modified_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.reset_button.setObjectName("cfgReset")
        self.reset_button.setAutoDefault(False)
        self.reset_button.setToolTip(
            "Back to the Standard configuration with every value at its default."
            " Test Name and Notes are kept. Nothing is saved yet."
        )
        caption_row = QHBoxLayout()
        caption_row.setContentsMargins(0, 0, 0, 0)
        caption_row.setSpacing(ROW_GAP)
        caption_row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        caption_row.addWidget(self.modified_label, 1)
        # The row's stretch decides the box's width, not its longest saved name (a 40-character
        # name must not squeeze the button), and the button keeps its own width.
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.reset_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        box_row = QHBoxLayout()
        box_row.setContentsMargins(0, 0, 0, 0)
        box_row.setSpacing(ROW_GAP)
        box_row.addWidget(combo, 1, Qt.AlignmentFlag.AlignVCenter)  # the box takes the width
        box_row.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignVCenter)
        field = QVBoxLayout()
        field.setContentsMargins(0, 0, 0, 0)
        field.setSpacing(LABEL_GAP)
        field.addLayout(caption_row)
        field.addLayout(box_row)
        return field

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
