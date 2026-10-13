"""The settings at the top of the Setup page's Calibration card (SPEC-app-drawn-calibration.md 4.3,
4.3b; wireframe ``docs/wireframes/setup.md``, Calibration).

"Calibration screen" (App or Gazepoint Control, D6; it replaced the "Show calibration window" tick
box), then a row of Points, Speed and Background and a row of Target and Target size. Speed and
Points apply to both screens (Speed is sent through the Gazepoint API, 4.3b); Background, Target and
Target size are drawn by the app, so they are greyed for Gazepoint Control. The panel only holds
and reports the choices (:class:`~src.engine.calibration_settings.CalibrationSettings`); the page
saves them per PC.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ..engine.calibration_settings import (
    BACKGROUND_NAMES,
    ICON_IDS,
    ICON_NAMES,
    POINT_CHOICES,
    SCREEN_CHOICES,
    SIZE_NAMES,
    SIZES_DEG,
    SPEED_NAMES,
    SPEEDS,
    CalibrationSettings,
    icon_path,
)
from .config_widgets import RadioChoice
from .design_tokens import BORDER_STRONG, PANEL, RADIUS
from .page_layout import FIELD_GAP, labeled
from .wheel_guard import WheelGuard, guard_wheel

LABEL = "Calibration screen"
THUMB_PX = 28


def speed_label(speed: str) -> str:
    """``Normal (glide 0.8 s, hold 1.0 s)``: the preset with its pair (D1)."""
    glide, hold = SPEEDS[speed]
    return f"{SPEED_NAMES[speed]} (glide {glide:.1f} s, hold {hold:.1f} s)"


def _combo(items: list[tuple[str, str]]) -> QComboBox:
    """A combo box of (value, label) items, its popup framed like the Setup page's other
    drop-downs (one border, no focus rectangle)."""
    combo = QComboBox()
    for value, label in items:
        combo.addItem(label, value)
    # A row of three must fit a narrow card: the closed box is as narrow as it needs to be and
    # elides, the popup lists every item in full.
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(6)
    combo.view().setFrameShape(QFrame.Shape.NoFrame)
    combo.view().setFocusPolicy(Qt.FocusPolicy.NoFocus)
    container = combo.view().parentWidget()
    if container is not None:
        container.setStyleSheet(
            f"background: {PANEL}; border: 1px solid {BORDER_STRONG}; border-top: none; border-radius: {RADIUS}px;"
        )
    return combo


class CalibrationSettingsPanel(QWidget):
    changed = Signal(object)  # the new CalibrationSettings, on every change the operator makes

    def __init__(self, settings: CalibrationSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._wheel_guard = WheelGuard()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FIELD_GAP)

        self.screen_choice = RadioChoice("cal_screen", SCREEN_CHOICES, settings.screen)
        layout.addWidget(labeled(LABEL, self.screen_choice))

        self.points_combo = _combo([(str(n), f"{n} points") for n in POINT_CHOICES])
        self.speed_combo = _combo([(name, speed_label(name)) for name in SPEEDS])
        self.background_combo = _combo([(name, label) for name, label in BACKGROUND_NAMES.items()])
        self.target_combo = _combo([(icon, ICON_NAMES[icon]) for icon in ICON_IDS])
        self.target_combo.setIconSize(QSize(THUMB_PX, THUMB_PX))
        for index, icon in enumerate(ICON_IDS):  # a thumbnail of each built-in icon (D3)
            pixmap = QPixmap(str(icon_path(icon)))
            if not pixmap.isNull():
                thumb = pixmap.scaled(
                    THUMB_PX * 2, THUMB_PX * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.target_combo.setItemIcon(index, QIcon(thumb))
        self.size_combo = _combo([(name, SIZE_NAMES[name]) for name in SIZES_DEG])

        # Three across, then two across, every field filling its share of the card.
        for fields in (
            (("Points", self.points_combo), ("Speed", self.speed_combo), ("Background", self.background_combo)),
            (("Target", self.target_combo), ("Target size", self.size_combo)),
        ):
            row = QHBoxLayout()
            row.setSpacing(FIELD_GAP)
            for text, combo in fields:
                row.addWidget(labeled(text, combo), 1)
            layout.addLayout(row)
        guard_wheel(self, self._wheel_guard)  # the page scrolls: a wheel over a drop-down must not change it

        self.set_settings(settings)
        self.screen_choice.valueChanged.connect(self._on_changed)
        for combo in self._combos():
            combo.currentIndexChanged.connect(self._on_changed)

    def _combos(self) -> list[QComboBox]:
        return [self.points_combo, self.speed_combo, self.background_combo, self.target_combo, self.size_combo]

    # -- the settings ----------------------------------------------------------------------------

    def settings(self) -> CalibrationSettings:
        return CalibrationSettings(
            screen=self.screen_choice.value(),
            points=int(self.points_combo.currentData()),
            speed=self.speed_combo.currentData(),
            target=self.target_combo.currentData(),
            size=self.size_combo.currentData(),
            background=self.background_combo.currentData(),
        )

    def set_settings(self, settings: CalibrationSettings) -> None:
        """Show ``settings`` without announcing a change."""
        for widget in (self.screen_choice, *self._combos()):
            widget.blockSignals(True)
        try:
            self.screen_choice.setValue(settings.screen)
            for combo, value in (
                (self.points_combo, str(settings.points)),
                (self.speed_combo, settings.speed),
                (self.background_combo, settings.background),
                (self.target_combo, settings.target),
                (self.size_combo, settings.size),
            ):
                index = combo.findData(value)
                combo.setCurrentIndex(max(index, 0))
        finally:
            for widget in (self.screen_choice, *self._combos()):
                widget.blockSignals(False)
        self._apply_enabled()

    def drawn_by_app(self) -> list[QWidget]:
        """The controls that apply to the App screen only (the app draws them, 4.3b)."""
        return [self.background_combo, self.target_combo, self.size_combo]

    def _apply_enabled(self) -> None:
        app = self.settings().is_app
        for combo in self.drawn_by_app():
            combo.setEnabled(app)
            combo.parentWidget().label.setEnabled(app)  # the label from ``labeled``

    def _on_changed(self, *_args: object) -> None:
        self._apply_enabled()
        self.changed.emit(self.settings())
