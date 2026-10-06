"""Pre-launch dialog for structural/layout task parameters
(SPEC-live-settings-panel.md section 5.3).

Grid size, target/icon size, icon count, trial count, and follow_moving's
selection window are baked once into a task's trial list at
``build_targets()`` time -- they are not safe to change mid-task without a
trial-rebuild mechanism this design deliberately avoids (see the SPEC's
section 4 classification table). Instead, they're collected here, before
``AssessmentApp`` is constructed, and merged over the task's own config via
the same ``deep_merge`` an ``overrides:`` YAML block already goes through.

A setting is a slider+spin row (int/float) or, for ``kind="choice"``, a themed
combo box whose value is a string (the target / icon size preset of every task,
follow_moving's movement path -- SPEC-target-size-and-motion-paths.md S4.5,
S11.3 -- and click_grid's cell gap, SPEC-grid-cell-gap.md S4.5) or, for
``kind="bool"``, a check box (the two sound toggles, SPEC-compass-task-flow.md
HB3/HB11). The shrink-hint texts come from :mod:`src.engine.target_size`, shared
with the configuration page.

Shown modally by :func:`src.app.run_gui` and by ``DashboardWindow``'s Tasks
tab. "Start task" accepts current values (defaults if untouched); "Cancel"
aborts the launch.

Themed to match the WTMH dashboard (SPEC-ui-setup-task-selection.md S11.1
critique point 1 -- previously fell back entirely to native OS dialog
styling). Reuses ``wtmh_theme.STYLESHEET`` directly rather than duplicating
any button/form-control CSS: giving this dialog the same ``wtmhDashboard``
object name is enough for every ancestor-scoped rule in that stylesheet
(form controls, button tiers, sliders) to apply here too, exactly as it does
in ``DashboardWindow``. The dialog keeps its native OS title bar (this app
never goes frameless anywhere, not even ``DashboardWindow`` itself, which
only adds its own styled bar *below* the OS chrome) -- the in-card title
label below plays that same role here.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..engine.target_size import (
    gap_px_for,
    grid_fit_hint,
    icon_fit_hint,
    radius_px_for,
    screen_scale,
    viewing_distance_mm,
)
from ..tasks.scanning import scanning_layout_slots
from .settings_registry import (
    StructuralSetting,
    initial_structural_values,
    set_nested,
    structural_settings_for_task,
)
from .slider_spin import SliderSpinRow
from .wtmh_theme import BORDER, PANEL_BG, STYLESHEET


class TaskSettingsDialog(QDialog):
    def __init__(self, task_id: str, config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Task settings — {task_id}")
        self.setObjectName("wtmhDashboard")
        self.setStyleSheet(STYLESHEET)
        self._settings = structural_settings_for_task(task_id)
        values = initial_structural_values(task_id, config)

        # What the size labels and the grid-fit hint are computed from: the
        # parent window's screen when there is one (the dashboard -- the monitor
        # the run will be sized for), else this dialog's own.
        app_cfg = config.get("app", {})
        screen = parent.screen() if parent is not None else self.screen()
        self._scale = screen_scale(screen, app_cfg)
        self._distance_mm = viewing_distance_mm(app_cfg)
        self._canvas_px = self._estimated_canvas_px(screen, app_cfg)
        self._grid_margin = float(config.get("task", {}).get("grid", {}).get("margin_frac", 0.12))
        self._layout_cfg = config.get("task", {}).get("layout", {})

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        card = QFrame(self)
        card.setObjectName("wtmhCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Soft drop shadow to lift the card off the page-background dialog
        # behind it -- same QGraphicsDropShadowEffect pattern already used
        # for OperatorPanel's HUD cards (SPEC-diki-design-audit.md S8.10);
        # QSS has no box-shadow property, so this needs a real graphics
        # effect, not CSS.
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        title = QLabel(f"Task settings — {task_id}")
        title.setObjectName("wtmhSectionTitle")
        card_layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self._controls: dict[str, QWidget] = {}

        for setting in self._settings:
            control = self._build_control(setting, values.get(setting.key))
            self._controls[setting.key] = control
            form.addRow(setting.label, control)

        card_layout.addLayout(form)

        # Shrink hint (SPEC-target-size-and-motion-paths.md S4.5, S11.3): the two
        # tasks with several things on screen at once -- click_grid (cells too
        # small for a preset) and scanning (icons that would overlap or leave
        # the canvas). click_static and follow_moving move the target inward
        # instead, so their size never changes and they get no hint.
        self.fit_hint = QFrame()
        self.fit_hint.setObjectName("wtmhAlertWarning")
        hint_layout = QVBoxLayout(self.fit_hint)
        self.fit_hint_label = QLabel("")
        self.fit_hint_label.setWordWrap(True)
        hint_layout.addWidget(self.fit_hint_label)
        self.fit_hint.hide()
        card_layout.addWidget(self.fit_hint)
        if all(key in self._controls for key in ("target.size", "grid.rows", "grid.cols")):
            self._controls["target.size"].currentIndexChanged.connect(self._update_fit_hint)
            self._controls["grid.rows"].valueChanged.connect(self._update_fit_hint)
            self._controls["grid.cols"].valueChanged.connect(self._update_fit_hint)
            if "grid.gap" in self._controls:
                self._controls["grid.gap"].currentIndexChanged.connect(self._update_fit_hint)
            self._update_fit_hint()
        if all(key in self._controls for key in ("layout.size", "layout.n_icons")):
            self._controls["layout.size"].currentIndexChanged.connect(self._update_icon_hint)
            self._controls["layout.n_icons"].valueChanged.connect(self._update_icon_hint)
            self._update_icon_hint()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Start task")
        ok_button.setObjectName("wtmhPrimary")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("wtmhGhost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        outer.addWidget(card)

    @staticmethod
    def _estimated_canvas_px(screen, app_cfg: dict[str, Any]) -> tuple[float, float]:
        """Rough size of the run canvas, for the grid-fit hint: the screen's
        available area (the real canvas only exists once the run window is up,
        and is a little smaller -- hence the hint is labelled approximate)."""
        if screen is not None:
            area = screen.availableGeometry()
            return float(area.width()), float(area.height())
        return float(app_cfg.get("screen_width_px", 1920)), float(app_cfg.get("screen_height_px", 1080))

    def _build_control(self, setting: StructuralSetting, value: Any) -> QWidget:
        if setting.kind == "choice":
            return self._build_choice(setting, value)
        if setting.kind == "bool":
            check = QCheckBox()
            check.setChecked(bool(setting.default if value is None else value))
            return check
        initial = value if value is not None else setting.min
        return SliderSpinRow(setting.kind, setting.min, setting.max, setting.step, initial)

    def _build_choice(self, setting: StructuralSetting, value: Any) -> QComboBox:
        combo = QComboBox()
        for choice_value, label in setting.choices:
            if setting.key in ("target.size", "layout.size"):
                # The operator can't picture "5 degrees": show the diameter it
                # comes to on this monitor.
                diameter = 2 * radius_px_for(choice_value, self._scale.mm_per_px, self._distance_mm)
                label = f"{label} (≈{round(diameter)} px)"
            elif setting.key == "grid.gap":
                # Likewise the cell gap (Standard has no angle, so no px).
                gap = gap_px_for(choice_value, self._scale.mm_per_px, self._distance_mm)
                if gap is not None:
                    label = f"{label} (≈{round(gap)} px)"
            combo.addItem(label, choice_value)
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(setting.default))
        self._style_combo_popup(combo)
        return combo

    @staticmethod
    def _style_combo_popup(combo: QComboBox) -> None:
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

    def _update_fit_hint(self, *_args) -> None:
        """Show how far the chosen size will be shrunk to fit the chosen grid
        and cell gap, and whether the gap itself is limited.

        The text is :func:`~src.engine.target_size.grid_fit_hint`, the one the
        configuration page shows too: an estimate from the screen's available
        area (labelled approximate); the real fit is applied per frame during
        the run (``ClickGridTask.effective_radius_px`` / ``grid_cell_geometry``,
        which that reads too, so they cannot disagree). Hidden when the preset
        fits and the gap is not limited.
        """
        gap_control = self._controls.get("grid.gap")
        self._show_hint(
            grid_fit_hint(
                int(self._controls["grid.rows"].value()),
                int(self._controls["grid.cols"].value()),
                *self._canvas_px,
                radius_px_for(
                    self._controls["target.size"].currentData(),
                    self._scale.mm_per_px,
                    self._distance_mm,
                ),
                self._grid_margin,
                gap_px_for(gap_control.currentData(), self._scale.mm_per_px, self._distance_mm)
                if gap_control is not None
                else None,
            )
        )

    def _update_icon_hint(self, *_args) -> None:
        """Show how far the chosen icon size will be shrunk to fit the chosen
        number of icons (scanning), via :func:`~src.engine.target_size.icon_fit_hint`.

        An estimate from the screen's available area and the YAML's arrangement /
        margin (labelled approximate); the real fit is applied per frame during
        the run (``ScanningTask.effective_radius_px``). The size is the *visible*
        icon, so the figure is the icon's diameter. Hidden when the preset fits.
        """
        n_icons = int(self._controls["layout.n_icons"].value())
        slots = scanning_layout_slots(
            n_icons,
            str(self._layout_cfg.get("arrangement", "grid")),
            float(self._layout_cfg.get("margin_frac", 0.14)),
        )
        wanted = radius_px_for(
            self._controls["layout.size"].currentData(), self._scale.mm_per_px, self._distance_mm
        )
        self._show_hint(icon_fit_hint(n_icons, slots, *self._canvas_px, wanted))

    def _show_hint(self, text: str | None) -> None:
        if text is None:
            self.fit_hint.hide()
            return
        self.fit_hint_label.setText(text)
        self.fit_hint.show()

    def overrides(self) -> dict[str, Any]:
        """Return a nested dict (dotted keys expanded) suitable for
        ``deep_merge``-ing over ``config["task"]``."""
        result: dict[str, Any] = {}
        for setting in self._settings:
            control = self._controls[setting.key]
            if setting.kind == "choice":
                set_nested(result, setting.key, str(control.currentData()))
                continue
            if setting.kind == "bool":
                set_nested(result, setting.key, control.isChecked())
                continue
            value = control.value()
            set_nested(result, setting.key, int(value) if setting.kind == "int" else float(value))
        return result
