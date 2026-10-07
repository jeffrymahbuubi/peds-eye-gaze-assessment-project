"""Shared slider + numeric-readout widget for int/float task settings
(SPEC-live-settings-panel.md section 8).

Both the configuration page's settings and TaskSettingsDialog's structural
settings need the same slider+exact-value pairing, kept in sync both ways.
This widget owns that sync so neither call site duplicates it.

A time setting is stored in milliseconds but shown in seconds (SPEC-compass-task-flow.md
7.1, V5): ``display_divisor=1000`` makes the readout ``value / 1000``. Only what the
operator sees changes; ``value()``, ``setValue()`` and ``valueChanged`` stay in the
stored unit, so profiles, snapshots and the data files keep their milliseconds.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSlider, QSpinBox, QWidget


def display_decimals(step: float, divisor: float) -> int:
    """Decimals a readout needs to show ``step / divisor`` exactly: 50 ms in seconds is
    ``0.05`` (2), 100 ms ``0.1`` (1), 1000 ms ``1`` (0); at most 4."""
    shown = step / divisor
    for digits in range(5):
        if abs(round(shown, digits) - shown) < 1e-9:
            return digits
    return 4


class SliderSpinRow(QWidget):
    """A QSlider paired with a QSpinBox/QDoubleSpinBox readout, kept in sync.

    ``kind`` selects the readout type (``"int"`` -> ``QSpinBox``, ``"float"``
    -> ``QDoubleSpinBox``). The slider always moves over integer *positions*
    (section 8.2's mapping: ``position = round((value - min) / step)``,
    ``value = min + position * step``), so one widget covers both kinds
    without a separate float-slider implementation.

    ``display_divisor`` (default 1: shown as stored) turns the readout into a
    ``QDoubleSpinBox`` of ``value / display_divisor`` (milliseconds shown as seconds).
    """

    valueChanged = Signal(object)  # emits int or float, matching `kind`

    def __init__(
        self,
        kind: str,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        parent: QWidget | None = None,
        *,
        display_divisor: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._min = minimum
        self._step = step
        self._divisor = float(display_divisor) if display_divisor else 1.0
        n_steps = round((maximum - minimum) / step)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setMinimum(0)
        self._slider.setMaximum(int(n_steps))

        self._spin: QSpinBox | QDoubleSpinBox
        if kind == "int" and self._divisor == 1.0:
            self._spin = QSpinBox(self)
            self._spin.setMinimum(int(minimum))
            self._spin.setMaximum(int(maximum))
            self._spin.setSingleStep(int(step))
        else:
            self._spin = QDoubleSpinBox(self)
            self._spin.setMinimum(self._shown(minimum))
            self._spin.setMaximum(self._shown(maximum))
            self._spin.setSingleStep(self._shown(step))
            self._spin.setDecimals(
                2 if self._divisor == 1.0 else display_decimals(step, self._divisor)
            )

        # Set initial values before wiring the sync signals below, so
        # construction never emits a spurious valueChanged.
        self._slider.setValue(self._position_for(value))
        self._spin.setValue(self._shown(value) if self._is_double() else int(value))

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._spin)

    def _is_double(self) -> bool:
        return isinstance(self._spin, QDoubleSpinBox)

    def _shown(self, value: float) -> float:
        """The stored value as the readout shows it."""
        return float(value) / self._divisor

    def _stored(self, shown: float) -> float:
        """What the readout shows, back in the stored unit (an int for ``kind="int"``)."""
        value = shown * self._divisor
        return value if self._kind == "float" else int(round(value))

    def _position_for(self, value: float) -> int:
        return round((value - self._min) / self._step)

    def _value_for(self, position: int) -> float:
        value = self._min + position * self._step
        return value if self._kind == "float" else int(round(value))

    def _on_slider_changed(self, position: int) -> None:
        value = self._value_for(position)
        self._spin.blockSignals(True)
        self._spin.setValue(self._shown(value) if self._is_double() else value)
        self._spin.blockSignals(False)
        self.valueChanged.emit(value)

    def _on_spin_changed(self, value: float) -> None:
        typed_value = self._stored(value) if self._is_double() else int(value)
        position = self._position_for(typed_value)
        self._slider.blockSignals(True)
        self._slider.setValue(position)
        self._slider.blockSignals(False)
        self.valueChanged.emit(typed_value)

    def value(self) -> float:
        return self._stored(self._spin.value()) if self._is_double() else int(self._spin.value())

    def setValue(self, value: float) -> None:  # noqa: N802 (Qt naming)
        self._spin.setValue(self._shown(value) if self._is_double() else int(value))

    def setToolTip(self, text: str) -> None:  # noqa: N802 (Qt naming)
        """Also apply to the slider/spin children, not just this container.

        A tooltip set only on the container never shows: the mouse is always
        over one of the two child widgets, which have no tooltip of their
        own by default (SPEC-diki-design-audit.md S8's ported tooltips).
        """
        super().setToolTip(text)
        self._slider.setToolTip(text)
        self._spin.setToolTip(text)
