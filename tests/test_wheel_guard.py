"""SPEC-compass-task-flow.md §9 P7a (resolved: wheel guard in P8): a slider or spin box
without focus ignores the wheel, so the wheel only scrolls the configuration page."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.engine.config import load_task_config
from src.engine.settings_profile import NamedConfig
from src.ui.slider_spin import SliderSpinRow
from src.ui.task_config_page import TaskConfigPage
from src.ui.wheel_guard import WheelGuard, guard_wheel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def wheel_event(widget: QWidget, delta: int = 120) -> QWheelEvent:
    pos = QPointF(widget.width() / 2, widget.height() / 2)
    return QWheelEvent(
        pos,
        QPointF(widget.mapToGlobal(pos.toPoint())),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def turn(widget: QWidget, delta: int = 120) -> QWheelEvent:
    event = wheel_event(widget, delta)
    QApplication.sendEvent(widget, event)
    return event


@pytest.fixture
def host(qapp):
    """A shown window whose keyboard focus sits on a text box, with one guarded slider
    row and one that is not guarded."""
    window = QWidget()
    layout = QVBoxLayout(window)
    anchor = QLineEdit()
    guarded = SliderSpinRow("int", 0, 100, 5, 50)
    plain = SliderSpinRow("int", 0, 100, 5, 50)
    guard = WheelGuard()
    guard_wheel(guarded, guard)
    for widget in (anchor, guarded, plain):
        layout.addWidget(widget)
    window.show()
    window.activateWindow()
    anchor.setFocus()
    qapp.processEvents()
    assert anchor.hasFocus()
    yield window, guarded, plain, guard
    window.close()


def test_a_spin_box_without_focus_ignores_the_wheel(host):
    _window, guarded, _plain, _guard = host
    event = turn(guarded._spin)
    assert guarded.value() == 50
    assert not event.isAccepted()  # offered on to the parent, so a scroll area scrolls


def test_a_slider_without_focus_ignores_the_wheel(host):
    _window, guarded, _plain, _guard = host
    event = turn(guarded._slider)
    assert guarded.value() == 50
    assert not event.isAccepted()


def test_with_focus_the_wheel_works_as_usual(host):
    _window, guarded, _plain, _guard = host
    guarded._spin.setFocus()
    QApplication.processEvents()
    assert guarded._spin.hasFocus()
    turn(guarded._spin)
    assert guarded.value() > 50
    guarded._slider.setFocus()
    QApplication.processEvents()
    before = guarded.value()
    turn(guarded._slider)
    assert guarded.value() != before


def test_an_unguarded_row_still_changes_with_the_wheel(host):
    # The control for the tests above: without the guard Qt changes the value.
    _window, _guarded, plain, _guard = host
    turn(plain._spin)
    assert plain.value() != 50


def test_the_wheel_does_not_give_a_guarded_widget_the_focus(host):
    # WheelFocus (Qt's default for a spin box) would hand it the focus before any filter
    # runs, so the guard would see a focused widget: the policy is StrongFocus instead.
    _window, guarded, _plain, _guard = host
    assert guarded._spin.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert guarded._slider.focusPolicy() == Qt.FocusPolicy.StrongFocus
    turn(guarded._spin)
    assert not guarded._spin.hasFocus()


def test_guard_wheel_returns_the_number_of_widgets_it_guarded(qapp):
    row = SliderSpinRow("float", 0.0, 1.0, 0.05, 0.5)
    assert guard_wheel(row, WheelGuard()) == 2  # the slider and the spin box
    assert guard_wheel(QLabel("x"), WheelGuard()) == 0


def test_a_wheel_over_a_guarded_slider_scrolls_the_scroll_area(qapp):
    # The whole point: the event reaches the scroll area instead of the control.
    content = QWidget()
    layout = QVBoxLayout(content)
    anchor = QLineEdit()
    layout.addWidget(anchor)
    row = SliderSpinRow("int", 0, 100, 5, 50)
    guard = WheelGuard()
    guard_wheel(row, guard)
    layout.addWidget(row)
    layout.addWidget(QLabel("tall\n" * 80))
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    area.resize(300, 200)
    area.show()
    area.activateWindow()
    anchor.setFocus()
    qapp.processEvents()
    bar = area.verticalScrollBar()
    assert bar.maximum() > 0 and bar.value() == 0
    spin = row._spin
    pos = QPointF(spin.width() / 2, spin.height() / 2)
    event = QWheelEvent(
        pos,
        QPointF(spin.mapToGlobal(pos.toPoint())),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(spin, event)
    # A real (spontaneous) wheel is offered to the parents when the widget ignores it;
    # sendEvent does not do that, so the test walks up the parents the way Qt does.
    parent = spin.parentWidget()
    while parent is not None and not event.isAccepted():
        QApplication.sendEvent(parent, event)
        parent = parent.parentWidget()
    assert row.value() == 50
    assert bar.value() > 0
    area.close()


# -- on the configuration page ------------------------------------------------------------------


def test_every_slider_and_spin_box_of_the_config_page_is_guarded(qapp):
    for task_id in ("click_static", "click_grid", "follow_moving", "scanning"):
        page = TaskConfigPage(task_id, load_task_config(task_id))
        rows = [c for c in page._form.controls.values() if isinstance(c, SliderSpinRow)]
        assert rows, f"{task_id} has slider rows"
        inner = [
            w
            for row in rows
            for w in row.findChildren(QWidget)
            if isinstance(w, (QSlider, QAbstractSpinBox))
        ]
        assert len(inner) == 2 * len(rows)  # a slider and a spin box in each
        assert all(w.focusPolicy() == Qt.FocusPolicy.StrongFocus for w in inner)


# -- the Configuration Name combo (a wheel over it would load a configuration) ----------------------


@pytest.fixture
def combo_host(qapp):
    """A shown window with focus on a text box, a guarded and an unguarded combo box."""
    window = QWidget()
    layout = QVBoxLayout(window)
    anchor = QLineEdit()
    guarded, plain = QComboBox(), QComboBox()
    for combo in (guarded, plain):
        combo.setEditable(True)
        combo.addItems(["Standard", "Large targets", "Slow"])
    guard = WheelGuard()
    guard_wheel(guarded, guard)
    for widget in (anchor, guarded, plain):
        layout.addWidget(widget)
    window.show()
    window.activateWindow()
    anchor.setFocus()
    qapp.processEvents()
    assert anchor.hasFocus()
    yield window, guarded, plain, guard
    window.close()


def test_a_combo_box_without_focus_ignores_the_wheel(combo_host):
    _window, guarded, _plain, _guard = combo_host
    activated = []
    guarded.activated.connect(activated.append)
    event = turn(guarded, -120)  # down: towards the next item
    assert guarded.currentIndex() == 0 and not activated
    assert not event.isAccepted()
    assert guarded.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert not guarded.hasFocus()  # the wheel did not hand it the focus either


def test_a_combo_box_with_focus_still_takes_the_wheel(combo_host):
    _window, guarded, _plain, _guard = combo_host
    guarded.setFocus()
    QApplication.processEvents()
    assert guarded.hasFocus()
    turn(guarded, -120)
    assert guarded.currentIndex() != 0


def test_an_unguarded_combo_box_changes_with_the_wheel(combo_host):
    # The control for the two tests above.
    _window, _guarded, plain, _guard = combo_host
    turn(plain, -120)
    assert plain.currentIndex() != 0


def test_guard_wheel_counts_a_combo_box(qapp):
    assert guard_wheel(QComboBox(), WheelGuard()) == 1


def test_a_wheel_over_the_configuration_name_does_not_load_a_configuration(qapp):
    page = TaskConfigPage("click_grid", load_task_config("click_grid"))
    saved = NamedConfig(
        "Large targets", "2026-10-06T10:00:00+08:00", Path("x.json"), {"dwell.threshold_ms": 1500}, {}
    )
    page.set_context(subject_id="TESTING", named_configs=[saved])
    page.show()
    page.activateWindow()
    page._form.test_name_edit.setFocus()
    QApplication.processEvents()
    assert page._form.test_name_edit.hasFocus()
    combo = page._form.config_combo
    assert combo.focusPolicy() == Qt.FocusPolicy.StrongFocus
    before = page.collect_values()
    turn(combo, -120)
    assert combo.currentText() == "Standard" and page.loaded_config_name() == "Standard"
    assert page.collect_values() == before  # nothing was loaded
    page.close()
