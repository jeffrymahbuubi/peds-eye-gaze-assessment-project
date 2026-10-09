"""SPEC-design-system-phase2.md H6, H12, V4 (Q5, Q6): the configuration page's column titles
and order, its shrink hints as alerts under their cards, the "Changed from ..." line that keeps
its height, the slider length caps, the centred footer and the name dialog. Sizes asserted are
the values set in code, and positions compared are relative (offscreen Qt has no fonts, so
nothing here measures a text width). The last section is the fit-1080 fix round (SPEC section 9,
2026-10-09): column A must fit a maximized 1920x1080 window without a scroll bar. Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QSlider,
    QWidget,
)

from src.engine.config import load_task_config
from src.engine.settings_profile import NamedConfig
from src.ui import design_tokens as tokens
from src.ui.alert_box import AlertBox
from src.ui.config_form import (
    ADVANCED_TITLE,
    CARD_GAP,
    CARD_PAD_H,
    CARD_PAD_V,
    COLUMN_GAP,
    MODIFIED_LINE_HEIGHT,
    NOTES_HEIGHT,
    ROW_GAP,
)
from src.ui.config_save_dialogs import NAME_FIELD_WIDTH, ConfigNameDialog
from src.ui.config_widgets import RADIO_GAP, ElidedLabel
from src.ui.page_layout import LABEL_GAP
from src.ui.settings_registry import config_groups_for_task
from src.ui.slider_spin import (
    LONG_SLIDER_PX,
    SHORT_RANGE_STEPS,
    SHORT_SLIDER_PX,
    SPIN_PX,
    SliderSpinRow,
)
from src.ui.task_config_page import TaskConfigPage
from src.ui.wtmh_theme import STYLESHEET

TASKS = ("click_static", "click_grid", "follow_moving", "scanning")
CARD_IDS = {
    "click_static": [["test", "input", "target"], ["timing", "feedback"], ["selection", "smoothing"]],
    "click_grid": [["test", "input", "target"], ["grid", "timing", "feedback"], ["selection", "smoothing"]],
    "follow_moving": [["test", "input", "target"], ["motion", "timing", "feedback"], ["smoothing"]],
    "scanning": [["test", "input", "icons"], ["timing", "feedback"], ["selection", "smoothing"]],
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_page(task_id="click_grid"):
    page = TaskConfigPage(task_id, load_task_config(task_id))
    page.set_context(subject_id="TESTING", existing_test_names=["Other test"])
    page.load_values(test_name="Test 1")
    return page


def column_layout(page, column):
    return page.scroll_area.widget().layout().itemAtPosition(0, column).layout()


def column_items(page, column):
    layout = column_layout(page, column)
    return [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]


def ancestors(widget):
    while widget is not None:
        yield widget
        widget = widget.parentWidget()


# -- the columns (V4, C1) --------------------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_columns_follow_h6_for_every_task(qapp, task_id):
    page = make_page(task_id)
    got = [
        [g.id for g in config_groups_for_task(task_id) if g.column == column] for column in range(3)
    ]
    assert got == CARD_IDS[task_id]
    for column in range(3):
        cards = [w for w in column_items(page, column) if w.objectName() == "wtmhCard"]
        assert cards == [page.cards[card_id] for card_id in CARD_IDS[task_id][column]]


@pytest.mark.parametrize("task_id", TASKS)
def test_column_c_is_titled_advanced_above_its_cards(qapp, task_id):
    page = make_page(task_id)
    items = column_items(page, 2)
    assert isinstance(items[0], QLabel) and items[0].text() == ADVANCED_TITLE == "Advanced"
    assert items[0].objectName() == "cfgAdvancedTitle"
    assert items[1] is page.cards[CARD_IDS[task_id][2][0]]
    for column in (0, 1):  # the other two have no title
        assert not any(isinstance(w, QLabel) for w in column_items(page, column))


def test_the_advanced_title_is_the_heading_step_in_text_secondary():
    block = next(
        b for b in STYLESHEET.split("}") if "QLabel#cfgAdvancedTitle" in b
    )
    assert f"font-size: {tokens.TYPE_HEADING}px" in block
    assert f"color: {tokens.TEXT_SECONDARY}" in block


def test_icons_stays_one_card_with_size_and_count_in_column_a(qapp):
    assert "icons" in make_page("scanning").cards
    icons = [g for g in config_groups_for_task("scanning") if g.id == "icons"]
    assert len(icons) == 1 and icons[0].column == 0
    assert [c.key for c in icons[0].controls] == ["layout.size", "layout.n_icons"]
    assert not any(g.id == "target" for g in config_groups_for_task("scanning"))


# -- alerts under their cards (H3, Q6) ---------------------------------------------------------------------


@pytest.mark.parametrize("task_id, card_id, column", [("click_grid", "grid", 1), ("scanning", "icons", 0)])
def test_the_shrink_hint_is_a_warning_alert_directly_under_its_card(qapp, task_id, card_id, column):
    page = make_page(task_id)
    hint = page.fit_hint
    assert isinstance(hint, AlertBox) and hint.kind() == "warning" and hint.word() == "Warning:"
    assert page.fit_hint_label is hint.label
    items = column_items(page, column)
    assert items.index(hint) == items.index(page.cards[card_id]) + 1
    assert not any(w.objectName() == "wtmhCard" for w in ancestors(hint))


def test_no_page_has_an_alert_inside_a_card(qapp):
    for task_id in TASKS:
        page = make_page(task_id)
        for box in page.findChildren(AlertBox):
            assert not any(w.objectName() == "wtmhCard" for w in ancestors(box))


def test_the_hint_still_shows_the_text_of_the_pure_function(qapp):
    page = make_page("click_grid")
    page._form.controls["grid.rows"].setValue(6)
    page._form.controls["grid.cols"].setValue(6)
    assert not page.fit_hint.isHidden() and page.fit_hint_label.text()


# -- the "Changed from" line (C4, Q5) -------------------------------------------------------------------------


def test_the_changed_from_line_is_a_caption(qapp):
    label = make_page("click_grid")._form.modified_label
    assert label.objectName() == "wtmhCaption"  # 12 px, text-secondary (2.1 caption)


def test_the_changed_from_line_is_always_there_with_a_fixed_height(qapp):
    page = make_page("click_grid")
    label = page._form.modified_label
    assert label.minimumHeight() == label.maximumHeight() == MODIFIED_LINE_HEIGHT
    assert label.text() == "" and not label.isHidden()
    page._form.controls["trials"].setValue(7)
    assert label.text() == "Changed from Standard" and not label.isHidden()
    assert label.minimumHeight() == label.maximumHeight() == MODIFIED_LINE_HEIGHT


@pytest.mark.parametrize("task_id", TASKS)
def test_nothing_moves_when_the_line_appears(qapp, task_id):
    page = make_page(task_id)
    page.resize(1700, 900)
    page.show()
    QApplication.processEvents()

    def positions():
        return {
            "cards": {name: card.mapTo(page, QPoint(0, 0)) for name, card in page.cards.items()},
            "sizes": {name: card.size() for name, card in page.cards.items()},
            "reset": page._form.reset_button.mapTo(page, QPoint(0, 0)),
            "name": page._form.config_combo.mapTo(page, QPoint(0, 0)),
        }

    before = positions()
    page._form.controls["trials"].setValue(7)
    QApplication.processEvents()
    assert page._form.modified_label.text() == "Changed from Standard"
    assert positions() == before  # the first card, and everything under the line, stays put
    page._form.controls["trials"].setValue(18)
    QApplication.processEvents()
    assert positions() == before
    page.close()


# -- the sliders (C3) ------------------------------------------------------------------------------------------


def test_a_slider_over_ten_steps_or_fewer_is_240_px_with_ticks_else_360(qapp):
    short = SliderSpinRow("int", 1, 6, 1, 3)  # 5 steps
    edge = SliderSpinRow("int", 0, 10, 1, 3)  # exactly 10 steps
    long = SliderSpinRow("int", 1, 100, 1, 18)  # 99 steps
    slider = lambda row: row.findChild(QSlider)  # noqa: E731
    for row in (short, edge):
        assert slider(row).maximumWidth() == SHORT_SLIDER_PX == 240
        assert slider(row).tickPosition() == QSlider.TickPosition.TicksBelow and slider(row).tickInterval() == 1
    assert slider(long).maximumWidth() == LONG_SLIDER_PX == 360
    assert slider(long).tickPosition() == QSlider.TickPosition.NoTicks
    assert SHORT_RANGE_STEPS == 10
    for row in (short, edge, long):
        assert row._spin.minimumWidth() == row._spin.maximumWidth() == SPIN_PX == 88


def test_a_float_range_counts_its_steps_too(qapp):
    coarse = SliderSpinRow("float", 0.0, 1.0, 0.1, 0.5)  # 10 steps: short
    fine = SliderSpinRow("float", 0.0, 1.0, 0.01, 0.22)  # 100 steps: long
    assert coarse.findChild(QSlider).maximumWidth() == 240
    assert fine.findChild(QSlider).maximumWidth() == 360
    assert fine.findChild(QSlider).tickPosition() == QSlider.TickPosition.NoTicks


def test_the_slider_rows_of_the_pages_follow_the_rule(qapp):
    page = make_page("click_grid")
    for key, control in page._form.controls.items():
        if not isinstance(control, SliderSpinRow):
            continue
        slider = control.findChild(QSlider)
        steps = slider.maximum() - slider.minimum()
        expected = SHORT_SLIDER_PX if steps <= SHORT_RANGE_STEPS else LONG_SLIDER_PX
        assert slider.maximumWidth() == expected, key
        assert (slider.tickPosition() == QSlider.TickPosition.TicksBelow) == (steps <= SHORT_RANGE_STEPS), key
    for key in ("grid.rows", "grid.cols"):
        assert page._form.controls[key].findChild(QSlider).maximumWidth() == 240


def test_the_slider_row_still_keeps_slider_and_spin_in_step(qapp):
    row = SliderSpinRow("int", 1, 6, 1, 3)
    seen = []
    row.valueChanged.connect(seen.append)
    row.findChild(QSlider).setValue(4)  # position 4 = value 5
    assert row.value() == 5 and seen == [5]
    row.setValue(2)
    assert row.findChild(QSlider).value() == 1


# -- the footer (C5) -------------------------------------------------------------------------------------------


def test_the_footer_row_is_as_wide_as_the_grid_and_the_buttons_sit_in_its_middle(qapp):
    page = make_page("click_grid")
    page.resize(1800, 900)
    page.show()
    QApplication.processEvents()
    footer = page.findChild(QWidget, "cfgFooter")
    assert footer.maximumWidth() == 1500 == page.scroll_area.widget().maximumWidth()
    assert footer.mapTo(page, QPoint(0, 0)).x() == page.scroll_area.mapTo(page, QPoint(0, 0)).x()  # left-aligned like the grid

    def middle() -> float:
        left = page.preview_button.mapTo(footer, QPoint(0, 0)).x()
        right = page.cancel_button.mapTo(footer, QPoint(page.cancel_button.width(), 0)).x()
        return (left + right) / 2

    assert abs(middle() - footer.width() / 2) <= 2
    page.footer_message.setText("Test Name is already used by another test of this subject. " * 3)
    QApplication.processEvents()
    assert abs(middle() - footer.width() / 2) <= 2  # a long reason does not push them aside
    page.close()


def test_the_footer_buttons_keep_their_names_and_the_save_rule(qapp):
    page = make_page("click_grid")
    assert [b.objectName() for b in (page.preview_button, page.save_button, page.cancel_button)] == [
        "cfgPreview", "cfgSave", "cfgCancel",
    ]
    assert [b.text() for b in (page.preview_button, page.save_button, page.cancel_button)] == [
        "Preview Test", "Save && Continue", "Cancel",  # (&& is a literal & on a button)
    ]
    page._form.test_name_edit.setText("Other test")  # taken by another test of the subject
    assert not page.save_button.isEnabled() and page.footer_message.text()


# -- the name dialog (C7) ---------------------------------------------------------------------------------------


def test_the_name_dialog_has_a_20_px_heading_and_a_320_px_field(qapp):
    dialog = ConfigNameDialog("Standard cannot be changed. Save these settings as:", "Custom 1")
    assert dialog.heading_label.text() == "Save as a new configuration"
    assert dialog.heading_label.objectName() == "cfgNameHeading"
    assert f"QLabel#cfgNameHeading {{ font-size: {tokens.TYPE_HEADING}px; font-weight: 600; }}" in dialog.styleSheet()
    assert NAME_FIELD_WIDTH == 320
    assert dialog.name_edit.minimumWidth() == dialog.name_edit.maximumWidth() == 320
    assert dialog.name_edit.objectName() == "cfgNewName" and dialog.name() == "Custom 1"
    assert dialog.save_button.isEnabled()
    dialog.name_edit.setText("Standard")
    assert not dialog.save_button.isEnabled()  # the rules of the name are unchanged


# -- H13 (2): Tab in Notes -------------------------------------------------------------------------------------------


def test_tab_in_the_notes_box_moves_on_and_types_nothing(qapp):
    page = make_page("click_grid")
    notes = page._form.notes_edit
    assert notes.tabChangesFocus()
    page.show()
    QApplication.processEvents()
    notes.setFocus()
    QTest.keyClick(notes, Qt.Key.Key_Tab)
    assert "\t" not in notes.toPlainText()
    page.close()


def test_no_card_frame_other_than_wtmhcard_was_added(qapp):
    page = make_page("click_grid")
    assert all(card.objectName() == "wtmhCard" and isinstance(card, QFrame) for card in page.cards.values())


# -- column A fits a maximized 1920x1080 window (fit-1080 fix round, SPEC section 9) ----------------------------------

# The sum of column A's card size hints plus the gaps between them, in offscreen px. Offscreen Qt
# has no fonts and understates a real window by about 10 % (labels 12 px high, not 19), so these
# are a proxy: the real figures, measured with Segoe UI loaded, are 871 px before this round for
# Test + Input + Target (click_static, click_grid) against a 784 px scroll viewport, and 696 / 696 /
# 598 / 786 px now (static, grid, follow, scanning) against 800 px. ``BEFORE`` is the offscreen sum
# before the round.
COLUMN_A_BEFORE = {"click_static": 808, "click_grid": 808, "follow_moving": 714, "scanning": 892}
# 690 is the budget of the three pages with a Target card. Scanning's third card is Icons (a size
# group of three and the count slider: 76 px taller than Target), so its proxy sits near 716; its
# real column is 786 px against the 800 px viewport, so it fits too, with less room.
COLUMN_A_BUDGET = {"click_static": 690, "click_grid": 690, "follow_moving": 690, "scanning": 720}
MIN_SAVING = 110


def card_stack_height(page, column) -> int:
    """The cards of ``column`` (not an alert or the Advanced title) and the gaps between them."""
    cards = [w for w in column_items(page, column) if w.objectName() == "wtmhCard"]
    return sum(card.sizeHint().height() for card in cards) + column_layout(page, column).spacing() * (len(cards) - 1)


@pytest.mark.parametrize("task_id", TASKS)
def test_column_a_stays_inside_its_height_budget(qapp, task_id):
    height = card_stack_height(make_page(task_id), 0)
    assert height <= COLUMN_A_BUDGET[task_id], (task_id, height)
    assert height <= COLUMN_A_BEFORE[task_id] - MIN_SAVING, (task_id, height)  # at least 110 px shorter


@pytest.mark.parametrize("task_id", ["click_static", "click_grid", "follow_moving"])
def test_the_pages_with_a_target_card_fit_the_690_px_budget_and_no_column_is_taller(qapp, task_id):
    page = make_page(task_id)
    assert card_stack_height(page, 0) <= 690
    for column in (1, 2):
        assert card_stack_height(page, column) <= 690, (column, card_stack_height(page, column))


def test_the_spacing_is_on_the_scale_and_the_cards_use_it(qapp):
    for value in (CARD_PAD_H, CARD_PAD_V, ROW_GAP, CARD_GAP, COLUMN_GAP, LABEL_GAP, RADIO_GAP):
        assert value in tokens.SPACING_SCALE, value
    page = make_page("click_grid")
    for card in page.cards.values():
        margins = card.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            CARD_PAD_H, CARD_PAD_V, CARD_PAD_H, CARD_PAD_V,
        )
    for column in range(3):
        assert column_layout(page, column).spacing() == CARD_GAP
    assert page.scroll_area.widget().layout().horizontalSpacing() == COLUMN_GAP


# -- the Test card: caption on the label row, Reset beside the box, a two-line Notes -------------------------


def labels_named(page, text):
    return [w for w in page.findChildren(QLabel) if w.text() == text]


def test_the_notes_box_is_two_lines_high(qapp):
    notes = make_page("click_grid")._form.notes_edit
    assert isinstance(notes, QPlainTextEdit) and NOTES_HEIGHT == 56
    assert notes.minimumHeight() == notes.maximumHeight() == NOTES_HEIGHT


def test_the_changed_from_line_sits_on_the_configuration_name_label_row_and_reset_beside_the_box(qapp):
    page = make_page("click_grid")
    page.resize(1700, 900)
    page.show()
    QApplication.processEvents()
    form = page._form
    name_label = labels_named(page, "Configuration Name")[0]
    caption, combo, reset, notes = form.modified_label, form.config_combo, form.reset_button, form.notes_edit

    def top(widget):
        return widget.mapTo(page, QPoint(0, 0))

    def centre(widget):
        return top(widget).y() + widget.height() / 2

    # the caption shares the label's row, at its right, above the box and the button
    assert abs(centre(caption) - centre(name_label)) <= 2
    assert top(caption).x() >= top(name_label).x() + name_label.width()
    assert top(caption).y() + caption.height() <= top(combo).y() + 1
    assert top(caption).y() + caption.height() <= top(reset).y() + 1
    # the box and [Reset to defaults] share a row: the box takes the width, the button its own
    assert abs(centre(combo) - centre(reset)) <= 2
    assert top(reset).x() >= top(combo).x() + combo.width()
    assert combo.width() > reset.width() >= reset.sizeHint().width()
    # nothing else sits between that row and Number of trials, and Notes follows below
    assert top(notes).y() > top(combo).y() + combo.height()
    page.close()


def test_a_long_configuration_name_neither_widens_the_card_nor_squeezes_reset(qapp):
    name = "N" * 40
    page = make_page("click_grid")
    page.set_context(named_configs=[NamedConfig(name, "2026-10-05T14:12:00+08:00", "n.json", {}, {})])
    page.resize(1700, 900)
    page.show()
    QApplication.processEvents()
    card, reset = page.cards["test"], page._form.reset_button
    before = (card.size(), reset.size())
    page.load_values(config_name=name)
    page._form.controls["trials"].setValue(9)
    QApplication.processEvents()
    caption = page._form.modified_label
    assert caption.text() == "Changed from " + name  # the whole text is kept ...
    assert caption.toolTip() == caption.text()  # ... and is the tooltip, since the line can be cut short
    assert (card.size(), reset.size()) == before
    assert reset.width() >= reset.sizeHint().width()
    page.close()


def test_the_elided_label_never_asks_for_width_and_keeps_its_text(qapp):
    label = ElidedLabel("")
    label.setText("Changed from a rather long configuration name")
    assert label.text() == "Changed from a rather long configuration name"
    assert label.minimumSizeHint().width() == 0
    assert label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert label.toolTip() == label.text()
    label.setText("")
    assert label.text() == "" and label.toolTip() == ""
