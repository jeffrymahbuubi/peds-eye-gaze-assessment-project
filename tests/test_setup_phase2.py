"""SPEC-design-system-phase2.md H3, H4, H12, H13 (Q6, Q7): the Setup page's status badges, the
"Needs: ..." caption under a disabled Continue to Tests, the field widths, the alerts that are
not inside cards, and the Notes box that lets Tab through. Widths are the values set in code
(offscreen Qt cannot measure a real window). Offscreen Qt."""

from __future__ import annotations

import itertools
import math
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.engine.calibration import CalibrationResult
from src.engine.display_check import check_display
from src.engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from src.ui import design_tokens as tokens
from src.ui.alert_box import AlertBox
from src.ui.page_layout import CONTENT_MAX_WIDTH, CONTINUE_WIDTH, SCROLLBAR_GUTTER
from src.ui.setup_page import SetupPage
from src.ui.setup_status import (
    DATE_BLOCKER,
    DISPLAY_BLOCKER,
    SEX_BLOCKER,
    SUBJECT_BLOCKER,
    calibration_badge,
    error_degrees,
    needs_caption,
    needs_names,
    tracker_badge,
)
from src.ui.status_badge import StatusBadge
from src.ui.wtmh_theme import STYLESHEET


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def page_with(*, connected=True, calibrated=True, subject="P001", sex=True, standard=True):
    page = SetupPage()
    page._client = SimpleNamespace(is_connected=lambda: connected) if connected is not None else None
    page._calibration_result = CalibrationResult(5, 12.0, True) if calibrated else None
    page.subject_id_edit.setText(subject)
    page.sex_combo.setCurrentIndex(1 if sex else 0)
    page._apply_display_check(check_display(1920, 1080, 1.0) if standard else check_display(1280, 720, 1.5))
    return page


# -- the caption under Continue to Tests (H4, Q7) ------------------------------------------------------


def test_the_short_names_of_the_blockers():
    assert needs_names([SUBJECT_BLOCKER, DATE_BLOCKER, SEX_BLOCKER, DISPLAY_BLOCKER]) == [
        "Subject ID", "Assessment Date", "Sex", "display acknowledgement",
    ]
    assert needs_names([TRACKER_BLOCKER, CALIBRATION_BLOCKER]) == ["tracker", "calibration"]
    assert needs_names(["a sentence nobody gave a name"]) == []
    assert needs_caption([]) == "" and needs_caption([SEX_BLOCKER, DISPLAY_BLOCKER]) == (
        "Needs: Sex, display acknowledgement"
    )


def test_a_disabled_continue_says_what_it_needs_in_the_order_of_the_blockers(qapp):
    page = page_with(subject="", sex=False, standard=False)
    assert not page.continue_button.isEnabled()
    assert not page.needs_label.isHidden()
    assert page.needs_label.text() == "Needs: Subject ID, Sex, display acknowledgement"
    # the caption is the continue_blockers() items, by their short names
    assert page.needs_label.text() == needs_caption(page.continue_blockers())
    page.subject_id_edit.setText("P001")
    assert page.needs_label.text() == "Needs: Sex, display acknowledgement"


def test_the_caption_never_lists_the_tracker_or_the_calibration(qapp):
    page = page_with(connected=None, calibrated=False, subject="", sex=False)
    assert page.run_blockers()[:2] == [TRACKER_BLOCKER, CALIBRATION_BLOCKER]  # a gaze test is held back
    text = page.needs_label.text()
    assert text == "Needs: Subject ID, Sex"
    assert "tracker" not in text and "calibration" not in text


@pytest.mark.parametrize("subject, sex, standard", list(itertools.product(("", "P001"), (False, True), (False, True))))
def test_the_caption_shows_exactly_when_continue_is_disabled(qapp, subject, sex, standard):
    page = page_with(subject=subject, sex=sex, standard=standard)
    assert page.needs_label.isHidden() == page.continue_button.isEnabled()
    assert bool(page.needs_label.text()) == (not page.can_continue())
    if not page.can_continue():
        assert page.needs_label.text().startswith("Needs: ")
    page.display_ack_checkbox.setChecked(True)  # the box only counts on a non-standard display
    assert page.needs_label.isHidden() == page.continue_button.isEnabled()


def test_the_caption_is_a_caption_not_body_text(qapp):
    """12 px, text-secondary: the generic label rule would make it ink (see wtmhCaption)."""
    page = page_with(subject="")
    assert page.needs_label.objectName() == "wtmhCaption"
    block = next(b for b in STYLESHEET.split("}") if "QLabel#wtmhCaption" in b)
    assert f"font-size: {tokens.TYPE_CAPTION}px" in block and f"color: {tokens.TEXT_SECONDARY}" in block


def test_the_tooltip_stays(qapp):
    page = page_with(subject="", sex=False)
    assert page.continue_button.toolTip() == "Still needed: enter a Subject ID; select Sex."


def test_the_footer_is_64_px_and_as_wide_as_the_column_and_holds_a_240_px_slot_for_continue(qapp):
    page = page_with()
    slot = page.continue_button.parentWidget()
    footer = slot.parentWidget()
    assert slot.minimumWidth() == slot.maximumWidth() == CONTINUE_WIDTH == 240
    assert footer.minimumHeight() == footer.maximumHeight() == 64
    assert footer.maximumWidth() == CONTENT_MAX_WIDTH == 1200
    assert page.needs_label.parentWidget() is footer  # the caption is under the slot, in the footer


def themed_page(page: SetupPage, width: int = 1920, height: int = 1000) -> QWidget:
    """``page`` under the dashboard's own style sheet, shown (what the live window has)."""
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    QVBoxLayout(root).addWidget(page)
    root.resize(width, height)
    root.show()
    QApplication.processEvents()
    return root


@pytest.mark.parametrize("label", ["Continue to Tests →", "Go"])
def test_continue_to_tests_is_240_px_wide_under_the_real_sheet_whatever_its_text(qapp, label):
    """Round 3, Q1 / H4: on screen it was 157 px, the width of its text, because the tiers' QSS
    ``min-width`` replaced the minimum a ``setFixedWidth`` on the button had set. The width is the
    slot's now; a short label (a narrower font than the offscreen one) must not change it."""
    page = page_with()
    page.continue_button.setText(label)
    root = themed_page(page)
    assert page.continue_button.width() == 240
    column_right = page.content_column_widget.x() + CONTENT_MAX_WIDTH  # the column's right edge
    right = page.continue_button.mapTo(page, QPoint(page.continue_button.width(), 0)).x()
    assert right == column_right  # right-aligned at the column's right edge
    root.close()


def test_the_needs_caption_sits_under_the_continue_button_at_its_right_edge(qapp):
    page = page_with(subject="", sex=False)
    root = themed_page(page)
    button, caption = page.continue_button, page.needs_label
    assert not caption.isHidden() and button.width() == 240
    button_bottom = button.mapTo(page, QPoint(0, button.height())).y()
    assert caption.mapTo(page, QPoint(0, 0)).y() >= button_bottom  # under it
    assert caption.mapTo(page, QPoint(caption.width(), 0)).x() == button.mapTo(page, QPoint(240, 0)).x()
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    page.display_ack_checkbox.setChecked(True)  # showing re-read the (offscreen, non-standard) display
    assert caption.isHidden() and button.isEnabled() and button.width() == 240  # enabled: still 240
    root.close()


# -- the badges (V3) -----------------------------------------------------------------------------------


def test_the_tracker_badge_says_disconnected_then_connected(qapp):
    page = page_with(connected=None)
    badge = page.tracker_badge
    assert isinstance(badge, StatusBadge) and (badge.kind(), badge.text()) == ("disconnected", "Disconnected")
    assert badge.accessibleName() == "Disconnected"
    page._client = SimpleNamespace(is_connected=lambda: True)
    page._on_state_changed()
    assert (badge.kind(), badge.text()) == ("connected", "Connected")
    page._client = SimpleNamespace(is_connected=lambda: False)  # it dropped
    page._on_state_changed()
    assert (badge.kind(), badge.text()) == ("disconnected", "Disconnected")
    assert not hasattr(page, "tracker_status_label")  # replaced by the badge


def test_what_the_last_connect_attempt_did_is_a_line_under_the_buttons(qapp):
    page = page_with(connected=None)
    assert page.tracker_message_label.isHidden()
    page._on_connect_failed("refused")
    assert page.tracker_message_label.text() == "Connection failed: refused"
    assert not page.tracker_message_label.isHidden()
    assert page.tracker_badge.kind() == "disconnected"  # a failed connect is still disconnected
    page._set_tracker_message("")
    assert page.tracker_message_label.isHidden()


def test_the_calibration_badge_says_not_calibrated_then_the_points_and_the_error(qapp):
    page = page_with(calibrated=False)
    badge = page.calibration_badge
    assert (badge.kind(), badge.text()) == ("not_calibrated", "Not calibrated")
    page._calibration_result = CalibrationResult(5, 12.0, True)
    page._on_state_changed()
    assert badge.kind() == "calibrated"
    assert badge.text().startswith("Calibrated, 5 points, ") and badge.text().endswith("°")
    page._calibration_result = None
    page._on_state_changed()
    assert badge.kind() == "not_calibrated"


def test_a_finished_calibration_updates_the_badge_and_the_alert(qapp):
    page = page_with(calibrated=False)
    page._on_calibration_finished(CalibrationResult(9, 20.0, True))
    assert page.calibration_badge.text().startswith("Calibrated, 9 points, ")
    assert page.calibration_alert.kind() == "success" and page.calibration_alert.word() == ""
    page._on_calibration_finished(CalibrationResult(9, None, False))  # an invalid one
    assert page.calibration_badge.kind() == "not_calibrated"
    assert page.calibration_alert.kind() == "danger"
    page._set_calibration_alert("info", "Calibrating…")
    assert page.calibration_alert.kind() == "note"


def test_error_degrees_is_the_visual_angle_of_the_error_on_the_screen():
    assert error_degrees(0, 0.25, 1.0, 650) == 0.0
    assert error_degrees(40, 0.25, 1.0, 650) == pytest.approx(math.degrees(2 * math.atan(10 / 1300)))
    # at 200 % the device's physical pixels are half as big on the (logical) scale
    assert error_degrees(40, 0.25, 2.0, 650) == pytest.approx(error_degrees(20, 0.25, 1.0, 650))
    assert error_degrees(-5, 0.25, 1.0, 650) == 0.0


def test_the_calibration_badge_words_without_a_screen():
    kind, word = calibration_badge(CalibrationResult(5, 10.0, True), None, {})
    assert kind == "calibrated" and word.startswith("Calibrated, 5 points, ") and word.endswith("°")
    assert calibration_badge(CalibrationResult(1, 10.0, True), None, {})[1].startswith("Calibrated, 1 point, ")
    assert calibration_badge(CalibrationResult(5, None, True), None, {}) == ("calibrated", "Calibrated, 5 points")
    assert calibration_badge(object(), None, {}) == ("calibrated", "Calibrated")
    assert calibration_badge(None, None, {}) == ("not_calibrated", "Not calibrated")
    assert tracker_badge(True) == ("connected", "Connected") and tracker_badge(False) == ("disconnected", "Disconnected")


# -- the widths (H4) -----------------------------------------------------------------------------------


def test_the_fields_have_their_widths_by_content(qapp):
    page = page_with()
    for field, width in (
        (page.subject_id_edit, 320), (page.date_edit, 200), (page.sex_combo, 240),
        (page.address_edit, 320), (page.port_spin, 120), (page.point_count_spin, 100),
    ):
        assert field.minimumWidth() == field.maximumWidth() == width, field.objectName() or type(field)
    assert page.notes_edit.minimumHeight() == page.notes_edit.maximumHeight() == 84  # three lines


def test_the_label_is_above_its_field_and_the_hint_under_subject_id(qapp):
    page = page_with()
    box = page.subject_id_edit.parentWidget()
    layout = box.layout()
    assert layout.itemAt(0).widget() is box.label and box.label.text() == "Subject ID"
    assert layout.itemAt(1).widget() is page.subject_id_edit
    assert layout.itemAt(2).widget() is page.subject_id_hint
    assert layout.spacing() == 4  # between a label and its field


def test_the_page_is_one_column_1200_px_wide_with_the_scroll_bar_beside_it(qapp):
    page = page_with()
    assert page.content_column_widget.maximumWidth() == CONTENT_MAX_WIDTH + SCROLLBAR_GUTTER
    scroll = page.findChild(QScrollArea, "wtmhSetupScroll")
    assert scroll.widget().maximumWidth() == CONTENT_MAX_WIDTH
    assert page.gaze_note.maximumWidth() == CONTENT_MAX_WIDTH
    page.resize(1856, 900)
    page.show()
    QApplication.processEvents()
    assert scroll.widget().width() == CONTENT_MAX_WIDTH  # room to spare: exactly the column
    assert page.content_column_widget.x() == 32  # left-aligned at the gutter
    page.close()


def test_the_page_title_has_no_number(qapp):
    page = page_with()
    titles = [label.text() for label in page.findChildren(QLabel) if label.objectName() == "wtmhPageTitle"]
    assert titles == ["Setup"]


# -- the alerts (H3, Q6) -----------------------------------------------------------------------------------


def ancestors(widget):
    while widget is not None:
        yield widget
        widget = widget.parentWidget()


def test_every_setup_alert_is_an_alert_box_and_none_sits_inside_a_card(qapp):
    page = page_with(standard=False)
    boxes = page.findChildren(AlertBox)
    assert {id(b) for b in boxes} == {
        id(page.display_ok_alert), id(page.display_warning_alert), id(page.rate_warning_alert),
        id(page.calibration_alert), id(page.gaze_note),
        id(next(b for b in boxes if b.text().startswith("Confirm in Gazepoint Control"))),
    }
    for box in boxes:
        assert not any(w.objectName() == "wtmhCard" for w in ancestors(box)), box.text()[:30]


def test_the_alert_kinds_and_the_aliases_tests_read(qapp):
    page = page_with()
    assert page.display_ok_alert.kind() == "success" and page.display_ok_label is page.display_ok_alert.label
    assert page.display_warning_alert.kind() == "warning"
    assert page.rate_warning_alert.kind() == "warning" and page.rate_warning_alert.isHidden()
    assert page.calibration_alert.kind() == "warning" and page.calibration_alert_label.text().startswith(
        "No calibration yet for this subject."
    )
    assert page.gaze_note.kind() == "note" and page.gaze_note_label is page.gaze_note.label


def test_the_alerts_sit_under_their_cards_at_the_page_level(qapp):
    page = page_with()
    for card_child, alert in ((page.connect_button, page.rate_warning_alert),
                              (page.do_calibration_button, page.calibration_alert)):
        card = next(w for w in ancestors(card_child) if w.objectName() == "wtmhCard")
        block = card.parentWidget()
        assert block is alert.parentWidget()
        layout = block.layout()
        assert layout.itemAt(0).widget() is card and layout.itemAt(1).widget() is alert


def test_the_display_alert_follows_the_display(qapp):
    page = page_with(standard=True)
    assert not page.display_ok_alert.isHidden() and page.display_warning_alert.isHidden()
    assert page.display_ack_checkbox.isHidden()
    page = page_with(standard=False)
    assert page.display_ok_alert.isHidden() and not page.display_warning_alert.isHidden()
    assert "1920×1080 at 100%" in page.display_warning_label.text()
    assert not page.display_ack_checkbox.isHidden()


# -- H13 (2): Tab in Notes -------------------------------------------------------------------------------------


def test_tab_in_notes_moves_on_and_types_nothing(qapp):
    page = page_with()
    assert page.notes_edit.tabChangesFocus()
    page.show()
    QApplication.processEvents()
    page.notes_edit.setFocus()
    QTest.keyClick(page.notes_edit, Qt.Key.Key_Tab)
    assert "\t" not in page.notes_edit.toPlainText()
    page.close()
