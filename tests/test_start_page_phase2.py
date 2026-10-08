"""SPEC-design-system-phase2.md H7, H12 (Q3, Q4, Q6): the Start page's "Blocked:" alert with one
item per line and Go to Setup inside it, the separate path alert, the button tiers and their
row, the Mouse note, "Practice runs 3 targets" said once, and the two surfaces. Widths are the
values set in code. Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel

from src.engine.config import load_task_config
from src.engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from src.ui.alert_box import AlertBox
from src.ui.page_layout import CONTENT_MAX_WIDTH, SCROLLBAR_GUTTER
from src.ui.setup_status import SEX_BLOCKER
from src.ui.start_test_page import (
    MOUSE_NOTE_NO_EYE_DATA,
    MOUSE_NOTE_NO_TRACKER,
    StartTestPage,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_page(blockers=(), pointer="gaze", task_id="click_grid"):
    page = StartTestPage()
    items = list(blockers)
    page.set_blockers_provider(lambda: list(items))
    cfg = load_task_config(task_id)
    cfg["task"]["trials"] = 18
    cfg["task"]["input"] = {"pointer": pointer, "selection": "dwell"}
    page.set_test(test_name="Grid Click 1", task_id=task_id, cfg=cfg)
    return page


def ancestors(widget):
    while widget is not None:
        yield widget
        widget = widget.parentWidget()


# -- the Blocked alert (P1, Q3) ---------------------------------------------------------------------------


def test_the_blocker_is_a_danger_alert_with_the_word_blocked_over_one_item_per_line(qapp):
    page = make_page([TRACKER_BLOCKER, CALIBRATION_BLOCKER, SEX_BLOCKER])
    banner = page.banner
    assert isinstance(banner, AlertBox) and banner.kind() == "danger" and banner.word() == "Blocked:"
    assert not banner.isHidden()
    assert page.banner_label.text().split("\n") == [
        "The tracker is not connected (Setup page).",
        "No calibration yet (Setup page).",
        "Sex is not selected (Setup page).",
    ]
    # stacked: the word is on its own line above the items
    page.resize(1300, 900)
    page.show()
    QApplication.processEvents()
    assert banner.word_label.y() < banner.label.y()
    page.close()


def test_go_to_setup_is_a_secondary_button_inside_the_alert_at_its_right_edge(qapp):
    page = make_page([TRACKER_BLOCKER])
    button = page.go_to_setup_button
    assert page.banner.action_widget is button and page.banner in list(ancestors(button))
    assert button.objectName() == "wtmhGhost"  # the secondary tier
    page.resize(1300, 900)
    page.show()
    QApplication.processEvents()
    gap = page.banner.width() - (button.mapTo(page.banner, QPoint(0, 0)).x() + button.width())
    assert 0 <= gap <= 24  # at the right edge: only the alert's own padding
    assert button.mapTo(page.banner, QPoint(0, 0)).x() > page.banner.width() // 2
    page.close()


def test_the_alert_is_hidden_with_nothing_missing_and_follows_the_blockers(qapp):
    items = [TRACKER_BLOCKER]
    page = StartTestPage()
    page.set_blockers_provider(lambda: list(items))
    page.set_test(test_name="T", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert not page.banner.isHidden()
    items[:] = []
    page.refresh_blockers()
    assert page.banner.isHidden()
    items[:] = [CALIBRATION_BLOCKER, SEX_BLOCKER]
    page.refresh_blockers()
    assert page.banner_label.text() == f"{CALIBRATION_BLOCKER}\n{SEX_BLOCKER}"


def test_the_path_blocker_is_a_second_danger_alert_and_practice_stays_on_under_it(qapp):
    page = make_page([])
    page.set_path_error("The data folder path is too long. Move the program folder closer to the drive root.")
    assert isinstance(page.path_alert, AlertBox) and page.path_alert.kind() == "danger"
    assert page.path_alert is not page.banner and page.path_alert.action_widget is None
    assert not page.path_alert.isHidden() and page.banner.isHidden()
    assert not page.start_button.isEnabled() and page.practice_button.isEnabled()  # Q3: Practice stays on
    page.set_blockers_provider(lambda: [TRACKER_BLOCKER])
    assert not page.practice_button.isEnabled()  # only the banner's blockers switch it off


# -- the buttons (P2, Q4) --------------------------------------------------------------------------------


def test_start_keeps_the_primary_tier_when_disabled_practice_is_secondary_cancel_tertiary(qapp):
    free = make_page([])
    blocked = make_page([TRACKER_BLOCKER])
    for page, enabled in ((free, True), (blocked, False)):
        assert page.start_button.objectName() == "wtmhPrimary"  # never changes tier with its state
        assert page.start_button.isEnabled() is enabled
        assert page.practice_button.objectName() == "wtmhGhost"  # secondary
        assert page.cancel_button.objectName() == "wtmhTertiary"
        assert page.cancel_button.isEnabled()


def test_the_three_buttons_are_one_row_at_the_left_in_that_order(qapp):
    page = make_page([])
    page.resize(1500, 900)
    page.show()
    QApplication.processEvents()
    positions = [b.mapTo(page, QPoint(0, 0)) for b in (page.start_button, page.practice_button, page.cancel_button)]
    assert positions[0].x() < positions[1].x() < positions[2].x()
    assert len({p.y() for p in positions}) == 1  # one row
    assert positions[0].x() == page.content_column_widget.x()  # at the content edge, not centred
    page.close()


# -- the card and the surfaces (P3, P5) --------------------------------------------------------------------------


def test_the_column_is_1200_px_with_room_for_the_scroll_bar_beside_it(qapp):
    page = make_page([TRACKER_BLOCKER])
    assert page.content_column_widget.maximumWidth() == CONTENT_MAX_WIDTH + SCROLLBAR_GUTTER
    for alert in (page.banner, page.path_alert, page.mouse_note, page.help_bar):
        assert alert.maximumWidth() == CONTENT_MAX_WIDTH
    page.resize(1856, 900)
    page.show()
    QApplication.processEvents()
    assert page.card.width() == page.banner.width() == CONTENT_MAX_WIDTH
    assert page.card.mapTo(page, QPoint(0, 0)).x() == page.banner.mapTo(page, QPoint(0, 0)).x() == 32
    page.close()


def test_the_read_aloud_text_is_a_white_card_and_the_clinicians_text_is_on_the_page(qapp):
    page = make_page([])
    card_labels = {label.text() for label in page.card.findChildren(QLabel)}
    clinician_labels = {label.text() for label in page.clinician_box.findChildren(QLabel)}
    assert "Read aloud to the child" in card_labels and "For the clinician (not read aloud)" in clinician_labels
    assert page.card not in list(ancestors(page.clinician_box)) and page.card.objectName() == "wtmhCard"
    assert page.clinician_box.objectName() != "wtmhCard"
    # the read aloud steps at body-large (16 px), the clinician's lines at body (14 px)
    steps = [label for label in page.card.findChildren(QLabel) if label.text().startswith("1. ")]
    assert steps and "font-size: 16px" in steps[0].styleSheet()
    clinician = [label for label in page.clinician_box.findChildren(QLabel) if label.text().startswith("Practice runs")]
    assert clinician and "font-size: 14px" in clinician[0].styleSheet()


def test_practice_runs_3_targets_is_said_once(qapp):
    page = make_page([])
    everything = [label.text() for label in page.findChildren(QLabel)]
    assert sum("practice" in t.lower() and "3 targets" in t for t in everything) == 1
    assert sum(t.startswith("Practice runs 3 targets") for t in everything) == 1
    assert "practice" not in page.help_label.text().lower()


def test_the_help_alert_is_a_note_with_its_own_sentence(qapp):
    page = make_page([])
    assert isinstance(page.help_bar, AlertBox) and page.help_bar.kind() == "note"
    assert page.help_bar.word() == "Note:"
    assert page.help_label.text() == "From this screen you can begin the test. Read the instructions aloud to the child."


# -- the Mouse note (P4) -------------------------------------------------------------------------------------------


def test_the_mouse_note_is_a_note_alert(qapp):
    page = make_page([TRACKER_BLOCKER, CALIBRATION_BLOCKER], pointer="mouse")
    assert isinstance(page.mouse_note, AlertBox) and page.mouse_note.kind() == "note"
    assert page.mouse_note.word() == "Note:" and not page.mouse_note.isHidden()
    assert page.mouse_note_label.text() == MOUSE_NOTE_NO_TRACKER
    assert page.banner.isHidden()  # a Mouse test is not blocked by the tracker


def test_the_mouse_notes_no_eye_data_sentence_is_a_label_of_its_own_at_weight_600(qapp):
    """Section 9 answer of 2026-10-09: two sentences, the second bold, both inside the note."""
    page = make_page([TRACKER_BLOCKER, CALIBRATION_BLOCKER], pointer="mouse")
    note = page.mouse_note
    emphasis = note.emphasis_label
    assert emphasis.text() == MOUSE_NOTE_NO_EYE_DATA == "No eye data will be recorded."
    assert note.label.text() == "Mouse test. The tracker is not connected."  # the plain label has only the first
    assert emphasis in note.findChildren(QLabel) and emphasis.parentWidget() is note
    assert emphasis.textFormat().name == "PlainText"
    page.resize(1300, 900)
    page.show()
    QApplication.processEvents()
    assert emphasis.font().weight() == QFont.Weight.DemiBold  # 600 (the alert's body label is Normal)
    assert note.label.font().weight() != emphasis.font().weight()
    assert emphasis.mapTo(note, QPoint(0, 0)).y() > note.label.mapTo(note, QPoint(0, 0)).y()  # under it
    assert emphasis.mapTo(note, QPoint(0, 0)).x() == note.label.mapTo(note, QPoint(0, 0)).x()
    page.close()


def test_with_a_ready_tracker_the_note_has_no_second_sentence(qapp):
    page = make_page([], pointer="mouse")
    assert page.mouse_note.emphasis() == "" and page.mouse_note.emphasis_label.isHidden()


# -- Q6 ----------------------------------------------------------------------------------------------------------------


def test_no_alert_on_the_start_page_sits_inside_a_card(qapp):
    page = make_page([TRACKER_BLOCKER], pointer="gaze")
    boxes = page.findChildren(AlertBox)
    assert {id(b) for b in boxes} == {id(page.banner), id(page.path_alert), id(page.mouse_note), id(page.help_bar)}
    for box in boxes:
        assert not any(w.objectName() == "wtmhCard" for w in ancestors(box))
