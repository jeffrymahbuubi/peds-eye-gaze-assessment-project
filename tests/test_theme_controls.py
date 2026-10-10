"""SPEC-compass-task-flow.md 7.1, P9b P1 and P2: a disabled button of the dashboard theme
looks "off", and an unchecked radio button or check box has an outline that shows on white.
A disabled primary button (Start, Run Test, ...) is the pale accent blue, every other disabled
button the neutral grey (SPEC-design-system-phase2.md section 9, user decision 2026-10-09).

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

from src.engine.config import load_task_config
from src.engine.input_choice import TRACKER_BLOCKER
from src.ui.design_tokens import (
    ACCENT,
    ACCENT_DISABLED_FILL,
    ACCENT_DISABLED_TEXT,
    ACCENT_SUBTLE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    DISABLED_FILL,
    PAGE,
    PANEL,
    TEXT_DISABLED,
)
from src.ui.setup_page import SetupPage
from src.ui.start_test_page import StartTestPage
from src.ui.test_list_page import SubjectTestListPage
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
def test_the_disabled_primary_rule_is_the_pale_accent_blue_with_blue_grey_text(selector):
    body = rule(selector)
    assert f"background: {ACCENT_DISABLED_FILL}" in body and f"color: {ACCENT_DISABLED_TEXT}" in body
    assert f"border-color: {ACCENT_DISABLED_FILL}" in body  # the border takes the fill: nothing moves
    assert DISABLED_FILL not in body and TEXT_DISABLED not in body  # no longer the grey of the others
    assert ACCENT_SUBTLE not in body  # nor the near-white tint that read as an enabled soft button


def test_the_pale_blue_is_the_accent_at_reduced_strength_and_its_text_is_readable():
    fill, accent = QColor(ACCENT_DISABLED_FILL), QColor(ACCENT)
    assert abs(fill.hue() - accent.hue()) <= 3  # the same blue, not another colour
    assert fill.lightness() > accent.lightness() + 60 and fill.saturation() > 0  # paler, still blue
    assert fill.lightness() < QColor(ACCENT_SUBTLE).lightness()  # more than the hover tint
    assert contrast(QColor(ACCENT_DISABLED_TEXT), fill) >= 3.0  # the SPEC's floor (it is 4.6)
    assert contrast(QColor(ACCENT_DISABLED_TEXT), fill) >= 4.5  # and it is real text
    assert contrast(fill, QColor(PAGE)) > contrast(QColor(DISABLED_FILL), QColor(PAGE))  # not fainter than grey


@pytest.mark.parametrize(
    "selector",
    ["QPushButton#wtmhGhost:disabled", "QPushButton#cfgPreview:disabled", "QPushButton#cfgCancel:disabled",
     "QPushButton#cfgReset:disabled"],
)
def test_the_disabled_ghost_rule_is_neutral_grey_with_a_grey_border(selector):
    body = rule(selector)
    assert f"color: {TEXT_DISABLED}" in body
    assert f"background: {DISABLED_FILL}" in body and f"border-color: {DISABLED_FILL}" in body


def test_a_disabled_primary_paints_the_pale_blue_and_a_disabled_ghost_the_grey_unlike_any_enabled_state(qapp):
    primary_on, primary_off = button("wtmhPrimary", True), button("wtmhPrimary", False)
    ghost_on, ghost_off = button("wtmhGhost", True, "Add New Test"), button("wtmhGhost", False, "Delete Test")
    secondary_on = button("wtmhSecondary", True, "Other")
    tertiary_off = button("wtmhTertiary", False, "Back to Setup")
    root = themed_row(primary_on, primary_off, ghost_on, ghost_off, secondary_on, tertiary_off)
    image = root.grab().toImage()
    off_primary, off_ghost = fill(root, primary_off, image), fill(root, ghost_off, image)
    assert off_primary == QColor(ACCENT_DISABLED_FILL)  # the primary keeps the accent family
    assert off_ghost == QColor(DISABLED_FILL)  # every other tier keeps the phase-1 grey
    assert off_primary != off_ghost
    enabled = [fill(root, w, image) for w in (primary_on, ghost_on, secondary_on)]
    assert enabled[0] == QColor(ACCENT)  # the primary is the accent fill
    assert enabled[1] == enabled[2] == QColor(PANEL)  # the secondary tier is white with an accent border
    for colour in (*enabled, QColor(PAGE), QColor(ACCENT_SUBTLE), QColor(ACCENT)):
        assert off_primary != colour and off_ghost != colour


def test_a_disabled_button_keeps_muted_legible_text_and_its_size(qapp):
    on, off = button("wtmhPrimary", True), button("wtmhPrimary", False)
    ghost_off = button("wtmhGhost", False, "Delete Test")
    root = themed_row(on, off, ghost_off)
    for widget in (off, ghost_off):
        widget.ensurePolished()
    disabled = QPalette.ColorGroup.Disabled
    assert off.palette().color(disabled, QPalette.ColorRole.ButtonText) == QColor(ACCENT_DISABLED_TEXT)
    assert ghost_off.palette().color(disabled, QPalette.ColorRole.ButtonText) == QColor(TEXT_DISABLED)
    assert on.sizeHint() == off.sizeHint()  # no border change: the button does not jump when it turns off
    assert root.isVisible()


@pytest.mark.parametrize(
    ("name", "expected"),
    [("cfgSave", ACCENT_DISABLED_FILL), ("cfgPreview", DISABLED_FILL), ("cfgCancel", DISABLED_FILL),
     ("cfgReset", DISABLED_FILL)],
)
def test_the_fixed_name_buttons_of_the_configuration_page_look_off_too(qapp, name, expected):
    off = button(name, False, "Save && Continue")
    root = themed_row(off)
    assert fill(root, off, root.grab().toImage()) == QColor(expected)  # Save is the page's primary


def painted(widget: QWidget) -> QColor:
    """The fill of ``widget`` as the themed page paints it: just inside its left edge."""
    return widget.grab().toImage().pixelColor(8, widget.height() // 2)


def themed_page(page: QWidget) -> QWidget:
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    QHBoxLayout(root).addWidget(page)
    root.resize(1500, 1000)
    root.show()
    QCoreApplication.processEvents()
    return root


def test_the_real_primaries_of_the_pages_paint_the_pale_blue_when_disabled(qapp, tmp_path):
    """Start, Run Test, Continue to Tests and Do Calibration are all ``wtmhPrimary``: disabled,
    each is the pale accent blue; the disabled secondary buttons beside them stay grey."""
    start = StartTestPage()
    start.set_blockers_provider(lambda: [TRACKER_BLOCKER])
    cfg = load_task_config("click_grid")
    start.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    setup = SetupPage()  # no subject, no tracker: Continue and Do Calibration are off
    tests = SubjectTestListPage()
    tests.set_subject("TESTING", tmp_path)  # nothing selected: Run Test and Delete Test are off
    pages = [(start, [start.start_button], []), (setup, [setup.continue_button, setup.do_calibration_button], []),
             (tests, [tests.run_button], [tests.delete_button, tests.configure_button])]
    roots = []
    for page, primaries, others in pages:
        root = themed_page(page)
        roots.append(root)  # the root owns the page: keep it alive while its buttons are read
        for button_ in primaries:
            assert button_.objectName() == "wtmhPrimary" and not button_.isEnabled(), button_.text()
            assert painted(button_) == QColor(ACCENT_DISABLED_FILL), button_.text()
        for button_ in others:
            assert not button_.isEnabled(), button_.text()
            assert painted(button_) == QColor(DISABLED_FILL), button_.text()  # the grey stays
    # and an enabled Start is the accent again: the pale blue is only the off state
    ready = StartTestPage()
    ready.set_blockers_provider(lambda: [])
    ready.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    root = themed_page(ready)
    assert ready.start_button.isEnabled() and painted(ready.start_button) == QColor(ACCENT)
    for each in (*roots, root):
        each.close()


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
