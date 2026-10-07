"""SPEC-input-selection-and-follow.md, user decision of 2026-10-07 (the Setup gate of §9):
"Continue to Tests" is allowed with no tracker connected and/or no calibration, and the Setup
page says only Mouse tests can run. Gaze tests stay held back on their own Start page by
``run_blockers``; every other Setup requirement (Subject ID, Sex, the display
acknowledgement) is as it was. Offscreen Qt."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.display_check import check_display
from src.engine.input_choice import (
    CALIBRATION_BLOCKER,
    NO_TRACKER_NOTE,
    NOT_CALIBRATED_NOTE,
    TRACKER_BLOCKER,
    gaze_only_note,
)
from src.ui.dashboard_flow import SETUP_INDEX, TESTS_INDEX
from src.ui.setup_page import SetupPage
from tests.dashboard_fixtures import close_window, make_window


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def page_with(*, connected=True, calibrated=True, subject="P001", sex=True, standard=True):
    page = SetupPage()
    page._client = SimpleNamespace(is_connected=lambda: connected) if connected is not None else None
    page._calibration_result = object() if calibrated else None
    page.subject_id_edit.setText(subject)
    page.sex_combo.setCurrentIndex(1 if sex else 0)
    page._apply_display_check(
        check_display(1920, 1080, 1.0) if standard else check_display(1280, 720, 1.5)
    )
    return page


def note(page):
    return None if page.gaze_note.isHidden() else page.gaze_note_label.text()


# -- the two notes ---------------------------------------------------------------------------


def test_the_two_notes_say_what_the_user_decided():
    assert NO_TRACKER_NOTE == "No tracker connected: only Mouse tests can run."
    assert NOT_CALIBRATED_NOTE == "Not calibrated: only Mouse tests can run."


@pytest.mark.parametrize(
    "tracker_ok, calibrated, expected",
    [
        (True, True, None),
        (False, True, NO_TRACKER_NOTE),
        (False, False, NO_TRACKER_NOTE),  # a missing tracker is named first
        (True, False, NOT_CALIBRATED_NOTE),
    ],
)
def test_the_note_names_the_tracker_first_and_nothing_when_a_gaze_test_could_run(
    tracker_ok, calibrated, expected
):
    assert gaze_only_note(tracker_ok, calibrated) == expected


# -- the button and the note ---------------------------------------------------------------------


def test_a_ready_tracker_needs_no_note(qapp):
    page = page_with()
    assert note(page) is None and page.continue_button.isEnabled() and page.can_continue()
    assert page.run_blockers() == []


def test_continue_is_enabled_with_no_tracker_and_the_page_says_only_mouse_tests_can_run(qapp):
    page = page_with(connected=None, calibrated=False)  # no client at all, no calibration
    assert page.run_blockers() == [TRACKER_BLOCKER, CALIBRATION_BLOCKER]  # a gaze test is held back
    assert page.continue_blockers() == [] and page.can_continue() is True
    assert page.continue_button.isEnabled() and page.continue_button.toolTip() == ""
    assert note(page) == "No tracker connected: only Mouse tests can run."


def test_a_tracker_that_dropped_is_the_same_as_none(qapp):
    page = page_with(connected=False)
    assert page.run_blockers() == [TRACKER_BLOCKER]
    assert page.can_continue() and page.continue_button.isEnabled()
    assert note(page) == NO_TRACKER_NOTE


def test_connected_but_uncalibrated_says_not_calibrated(qapp):
    page = page_with(connected=True, calibrated=False)
    assert page.run_blockers() == [CALIBRATION_BLOCKER]
    assert page.can_continue() and page.continue_button.isEnabled()
    assert note(page) == "Not calibrated: only Mouse tests can run."


def test_the_note_follows_the_tracker_and_the_calibration(qapp):
    page = page_with(connected=False, calibrated=False)
    assert note(page) == NO_TRACKER_NOTE
    page._client = SimpleNamespace(is_connected=lambda: True)
    page._on_state_changed()
    assert note(page) == NOT_CALIBRATED_NOTE
    page._calibration_result = object()
    page._on_state_changed()
    assert note(page) is None


@pytest.mark.parametrize("connected", [None, False])
def test_the_other_setup_requirements_still_hold_without_a_tracker(qapp, connected):
    page = page_with(connected=connected, subject="")
    assert not page.can_continue() and not page.continue_button.isEnabled()
    assert page.continue_button.toolTip() == "Still needed: enter a Subject ID."
    assert note(page) == NO_TRACKER_NOTE  # the note is about the tracker, not the gate

    page = page_with(connected=connected, sex=False)
    assert not page.can_continue()
    assert page.continue_button.toolTip() == "Still needed: select Sex."


def test_the_display_acknowledgement_gate_stays(qapp):
    page = page_with(connected=None, calibrated=False, standard=False)
    assert not page.can_continue() and not page.continue_button.isEnabled()
    assert "acknowledge the non-standard display" in page.continue_button.toolTip()
    page.display_ack_checkbox.setChecked(True)
    assert page.can_continue() and page.continue_button.isEnabled()
    assert note(page) == NO_TRACKER_NOTE


def test_the_tooltip_no_longer_asks_for_the_tracker_or_a_calibration(qapp):
    page = page_with(connected=None, calibrated=False, subject="", sex=False)
    tip = page.continue_button.toolTip()
    assert "tracker" not in tip and "calibration" not in tip
    assert tip == "Still needed: enter a Subject ID; select Sex."


def test_tracker_ready_reports_what_a_gaze_test_needs(qapp):
    assert page_with().tracker_ready() == (True, True)
    assert page_with(connected=False).tracker_ready() == (False, True)
    assert page_with(connected=None, calibrated=False).tracker_ready() == (False, False)
    assert page_with(calibrated=False).tracker_ready() == (True, False)


# -- the dashboard -------------------------------------------------------------------------------------


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    window._go_to_tab(SETUP_INDEX)
    window.setup_page.sex_combo.setCurrentIndex(1)
    window.setup_page._apply_display_check(check_display(1920, 1080, 1.0))
    yield window
    close_window(window)


def test_the_dashboard_goes_to_the_test_list_with_no_tracker(win):
    setup = win.setup_page
    assert setup.client is None and setup.calibration_result is None
    assert setup.continue_button.isEnabled() and setup.can_continue()
    assert note(setup) == NO_TRACKER_NOTE
    setup.continue_button.click()
    assert win.stack.currentIndex() == TESTS_INDEX


def test_the_dashboard_still_holds_continue_back_for_a_missing_subject(win):
    win.setup_page.subject_id_edit.setText("")
    win.setup_page.continueRequested.emit()
    assert win.stack.currentIndex() == SETUP_INDEX
