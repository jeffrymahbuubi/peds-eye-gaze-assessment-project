"""SPEC-design-system-phase2.md H3, H12: the alert box. White fill, a 1 px border in the state
colour, a 20 px glyph tile, a bold state word (none for a success), the text, an optional
action at the right edge; no left stripe and no tint. Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QWidget

from src.ui import design_tokens as tokens
from src.ui.alert_box import ALERT_STYLESHEET, KINDS, LOOKS, TILE_PX, AlertBox
from src.ui.glyphs import GLYPH_CIRCLE, GLYPH_INFO, GLYPH_SQUARE, GLYPH_TRIANGLE


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def shown(box: AlertBox, width: int = 640) -> AlertBox:
    box.resize(width, box.heightForWidth(width) if box.hasHeightForWidth() else 60)
    box.show()
    QApplication.processEvents()
    return box


def near(a: QColor, b: str, tolerance: int = 2) -> bool:
    c = QColor(b)
    return max(abs(a.red() - c.red()), abs(a.green() - c.green()), abs(a.blue() - c.blue())) <= tolerance


def test_the_four_kinds_have_their_glyph_border_and_word():
    assert set(KINDS) == {"danger", "warning", "success", "note"}
    assert (LOOKS["danger"].shape, LOOKS["danger"].border, LOOKS["danger"].word) == (
        GLYPH_SQUARE, tokens.DANGER, "Blocked:")
    assert (LOOKS["warning"].shape, LOOKS["warning"].border, LOOKS["warning"].word) == (
        GLYPH_TRIANGLE, tokens.WARNING, "Warning:")
    assert (LOOKS["success"].shape, LOOKS["success"].border, LOOKS["success"].word) == (
        GLYPH_CIRCLE, tokens.SUCCESS, "")
    assert (LOOKS["note"].shape, LOOKS["note"].border, LOOKS["note"].word) == (
        GLYPH_INFO, tokens.BORDER_STRONG, "Note:")


def test_an_alert_has_the_object_name_the_pages_and_qt_mcp_find_it_by(qapp):
    box = AlertBox("warning", "Look out.")
    assert box.objectName() == "wtmhAlert" and box.kind() == "warning"
    assert box.property("kind") == "warning"
    assert isinstance(box, QFrame)


@pytest.mark.parametrize(("kind", "word"), [("danger", "Blocked:"), ("warning", "Warning:"), ("note", "Note:")])
def test_the_state_word_is_bold_and_in_front_of_the_text(qapp, kind, word):
    box = shown(AlertBox(kind, "Something to know."))
    assert box.word() == word and not box.word_label.isHidden()
    assert box.text() == box.label.text() == "Something to know."
    assert box.word_label.x() < box.label.x()  # the word comes first, on the same line
    assert abs(box.word_label.y() - box.label.y()) <= 2
    assert "font-weight: 700" in ALERT_STYLESHEET and "wtmhAlertWord" in ALERT_STYLESHEET
    box.close()


def test_a_success_has_no_state_word(qapp):
    box = shown(AlertBox("success", "Display 1920x1080 at 100 %: the recommended standard."))
    assert box.word() == "" and box.word_label.isHidden()
    box.close()


def test_the_word_can_be_overridden_or_dropped(qapp):
    assert AlertBox("danger", "x", word="").word_label.isHidden()
    assert AlertBox("note", "x", word="Tip:").word() == "Tip:"


def test_a_stacked_alert_puts_the_word_above_the_text(qapp):
    box = shown(AlertBox("danger", "First item.\nSecond item.", stacked=True))
    assert box.word_label.y() < box.label.y()
    assert box.word_label.x() == box.label.x()
    box.close()


def test_the_text_is_plain_never_markup(qapp):
    box = AlertBox("warning", "a <b>bold</b> & c")
    assert box.text() == "a <b>bold</b> & c"
    assert box.label.textFormat().name == "PlainText"


def test_the_glyph_tile_is_20_px_and_follows_the_kind(qapp):
    box = AlertBox("danger", "x")
    assert (box.tile.width(), box.tile.height()) == (TILE_PX, TILE_PX) == (20, 20)
    assert box.tile.look is LOOKS["danger"]
    box.set_kind("note")
    assert box.tile.look is LOOKS["note"] and box.kind() == "note" and box.property("kind") == "note"
    assert box.word() == "Note:"


def test_set_kind_keeps_a_word_override_and_unknown_kinds_are_refused(qapp):
    box = AlertBox("warning", "x", word="Heads up:")
    box.set_kind("danger")
    assert box.word() == "Heads up:"
    with pytest.raises(ValueError):
        box.set_kind("loud")
    with pytest.raises(ValueError):
        AlertBox("loud")


def test_an_action_sits_at_the_right_edge(qapp):
    button = QPushButton("Go to Setup")
    box = shown(AlertBox("danger", "No calibration yet (Setup page).", stacked=True, action=button), 900)
    assert box.action_widget is button
    assert button.x() > box.label.x() + 100
    assert box.width() - (button.x() + button.width()) <= 24  # the right padding only
    box.close()


def test_set_action_later_puts_the_widget_in_the_same_place(qapp):
    box = AlertBox("note", "x")
    button = QPushButton("Open")
    box.set_action(button)
    box.resize(700, 50)
    box.show()
    QApplication.processEvents()
    assert button.x() > 500
    box.close()


def test_the_box_is_white_with_a_one_px_border_in_the_state_colour_and_no_stripe(qapp):
    for kind, look in LOOKS.items():
        box = shown(AlertBox(kind, "Some text."), 400)
        image = box.grab().toImage()
        middle = image.height() // 2
        assert near(image.pixelColor(0, middle), look.border), kind  # the 1 px border
        assert near(image.pixelColor(1, middle), tokens.PANEL), kind  # then white: no stripe
        assert near(image.pixelColor(200, 1), tokens.PANEL) or near(image.pixelColor(200, 1), look.border)
        assert near(image.pixelColor(image.width() - 1, middle), look.border), kind
        box.close()


def test_the_tile_has_the_subtle_state_fill_behind_the_glyph(qapp):
    for kind, look in LOOKS.items():
        box = shown(AlertBox(kind, "Some text."), 400)
        image = box.grab().toImage()
        tile = box.tile
        # a pixel in a corner of the tile, outside the 12 px glyph
        assert near(image.pixelColor(tile.x() + 3, tile.y() + 3), look.tile), kind
        box.close()


def test_the_stylesheet_has_no_left_stripe_and_no_tint():
    assert "border-left" not in ALERT_STYLESHEET
    assert f"background: {tokens.PANEL}" in ALERT_STYLESHEET
    for look in LOOKS.values():
        assert look.tile != look.border  # the subtle fill is behind the tile only
    assert f"font-size: {tokens.TYPE_BODY_LARGE}px" in ALERT_STYLESHEET


def test_an_emphasis_sentence_is_a_label_of_its_own_at_weight_600_under_the_text(qapp):
    box = AlertBox("note", "Mouse test. The tracker is not connected.")
    assert box.emphasis() == "" and box.emphasis_label.isHidden()  # none until asked for
    box.set_emphasis("No eye data will be recorded.")
    box = shown(box)
    assert box.emphasis() == box.emphasis_label.text() == "No eye data will be recorded."
    assert box.text() == "Mouse test. The tracker is not connected."  # the text label keeps its own text
    assert not box.emphasis_label.isHidden()
    assert box.emphasis_label.objectName() == "wtmhAlertEmphasis"
    assert box.emphasis_label.font().weight() == QFont.Weight.DemiBold
    assert box.label.font().weight() == QFont.Weight.Normal
    assert box.emphasis_label.y() > box.label.y() and box.emphasis_label.x() == box.label.x()
    assert "wtmhAlertEmphasis" in ALERT_STYLESHEET and "font-weight: 600" in ALERT_STYLESHEET
    box.set_emphasis("")
    assert box.emphasis_label.isHidden()
    box.close()


def test_an_alert_hides_and_shows_like_any_widget(qapp):
    parent = QWidget()
    box = AlertBox("note", "x", parent=parent)
    box.hide()
    parent.show()
    assert box.isHidden()
    box.show()
    assert not box.isHidden()
    parent.close()
