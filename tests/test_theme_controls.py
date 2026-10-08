"""SPEC-compass-task-flow.md 7.1, P9b P1 and P2: a disabled button of the dashboard theme
looks "off", and an unchecked radio button or check box has an outline that shows on white.

Pinned two ways: the rules in ``STYLESHEET`` (the colours and their contrast), and what a
themed button or indicator really paints (offscreen Qt: colours are real, glyphs are not).
"""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QWidget,
)

from src.ui.design_tokens import (
    ACCENT,
    ACCENT_SUBTLE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    DISABLED_FILL,
    PAGE,
    PANEL,
    TEXT_DISABLED,
)
from src.ui.wtmh_theme import STYLESHEET
from tests.colour_helpers import contrast


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def rule(selector: str) -> str:
    """The declarations of the first block whose selector list names ``selector``."""
    match = re.search(re.escape(selector) + r"[^{}]*\{([^}]*)\}", STYLESHEET)
    assert match is not None, selector
    return match.group(1)


def themed_row(*widgets: QWidget) -> QWidget:
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    layout = QHBoxLayout(root)
    for widget in widgets:
        layout.addWidget(widget)
    root.resize(900, 90)
    root.show()
    QCoreApplication.processEvents()
    return root


def button(tier: str, enabled: bool, text: str = "Run Test") -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName(tier)
    widget.setEnabled(enabled)
    return widget


def fill(root: QWidget, widget: QWidget, image: QImage) -> QColor:
    """The colour just inside the left edge of ``widget``, away from its text."""
    spot = widget.mapTo(root, QPoint(8, widget.height() // 2))
    return image.pixelColor(spot.x(), spot.y())


# -- P1: a disabled button reads "off" ---------------------------------------------------------------------------


def test_the_disabled_colours_are_legible_and_the_old_faint_ones_were_not():
    assert contrast(QColor(TEXT_DISABLED), QColor(DISABLED_FILL)) >= 3.0  # muted, still legible
    assert QColor(DISABLED_FILL).saturation() == 0  # a flat grey, not a colour
    assert DISABLED_FILL not in (ACCENT_SUBTLE, PAGE)  # not the soft button, not the page


@pytest.mark.parametrize("selector", ["QPushButton#wtmhPrimary:disabled", "QPushButton#cfgSave:disabled"])
def test_the_disabled_primary_rule_is_neutral_grey_with_muted_text(selector):
    body = rule(selector)
    assert f"background: {DISABLED_FILL}" in body and f"color: {TEXT_DISABLED}" in body
    assert ACCENT_SUBTLE not in body  # the pale blue that read as an enabled soft button


@pytest.mark.parametrize(
    "selector",
    ["QPushButton#wtmhGhost:disabled", "QPushButton#cfgPreview:disabled", "QPushButton#cfgCancel:disabled",
     "QPushButton#cfgReset:disabled"],
)
def test_the_disabled_ghost_rule_is_neutral_grey_with_a_grey_border(selector):
    body = rule(selector)
    assert f"color: {TEXT_DISABLED}" in body
    assert f"background: {DISABLED_FILL}" in body and f"border-color: {DISABLED_FILL}" in body


def test_a_disabled_primary_and_ghost_button_paint_the_same_grey_unlike_any_enabled_state(qapp):
    primary_on, primary_off = button("wtmhPrimary", True), button("wtmhPrimary", False)
    ghost_on, ghost_off = button("wtmhGhost", True, "Add New Test"), button("wtmhGhost", False, "Delete Test")
    secondary_on = button("wtmhSecondary", True, "Other")
    root = themed_row(primary_on, primary_off, ghost_on, ghost_off, secondary_on)
    image = root.grab().toImage()
    off_primary, off_ghost = fill(root, primary_off, image), fill(root, ghost_off, image)
    assert off_primary == QColor(DISABLED_FILL) and off_ghost == QColor(DISABLED_FILL)
    enabled = [fill(root, w, image) for w in (primary_on, ghost_on, secondary_on)]
    assert enabled[0] == QColor(ACCENT)  # the primary is the accent fill
    assert enabled[1] == enabled[2] == QColor(PANEL)  # the secondary tier is white with an accent border
    for colour in (*enabled, QColor(PAGE), QColor(ACCENT_SUBTLE), QColor(ACCENT)):
        assert off_primary != colour


def test_a_disabled_button_keeps_muted_legible_text_and_its_size(qapp):
    on, off = button("wtmhPrimary", True), button("wtmhPrimary", False)
    root = themed_row(on, off)
    off.ensurePolished()
    text = off.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
    assert text == QColor(TEXT_DISABLED)
    assert on.sizeHint() == off.sizeHint()  # no border change: the button does not jump when it turns off
    assert root.isVisible()


@pytest.mark.parametrize("name", ["cfgSave", "cfgPreview", "cfgCancel", "cfgReset"])
def test_the_fixed_name_buttons_of_the_configuration_page_look_off_too(qapp, name):
    off = button(name, False, "Save && Continue")
    root = themed_row(off)
    assert fill(root, off, root.grab().toImage()) == QColor(DISABLED_FILL)


# -- P2: the unchecked indicators have a visible outline ----------------------------------------------------------


def test_the_indicator_outline_is_dark_enough_and_not_the_card_border():
    assert contrast(QColor(BORDER_STRONG), QColor(PANEL)) >= 3.0
    assert contrast(QColor(BORDER_SUBTLE), QColor(PANEL)) < 1.4  # the card edge: barely there
    for selector in ("QCheckBox::indicator {", "QRadioButton::indicator {"):
        body = rule("QWidget#wtmhDashboard " + selector.rstrip(" {"))
        assert f"border: 1px solid {BORDER_STRONG}" in body


@pytest.mark.parametrize("make", [lambda: QRadioButton(""), lambda: QCheckBox("")], ids=["radio", "check box"])
def test_an_unchecked_indicator_paints_a_dark_outline_on_white(qapp, make):
    box = make()
    root = themed_row(box)
    image = box.grab().toImage()
    darkest = min(image.pixelColor(x, y).lightness() for x in range(min(20, image.width()))
                  for y in range(image.height()))
    assert darkest < QColor(BORDER_SUBTLE).lightness() - 60  # clearly darker than the card edge
    assert darkest <= QColor(BORDER_STRONG).lightness() + 25
    assert root.isVisible()


def test_a_checked_indicator_still_fills_with_the_accent(qapp):
    box = QCheckBox("")
    box.setChecked(True)
    root = themed_row(box)
    image = box.grab().toImage()
    accent = QColor(ACCENT)
    assert any(image.pixelColor(x, y) == accent for x in range(min(20, image.width()))
               for y in range(image.height()))
    assert root.isVisible()
