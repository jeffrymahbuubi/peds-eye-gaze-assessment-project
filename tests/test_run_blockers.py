"""SPEC-compass-task-flow.md 4C.2 / AC2: ``SetupPage.run_blockers`` says why a test
cannot start, and agrees with ``can_continue`` exactly."""

from __future__ import annotations

import itertools
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.display_check import check_display
from src.ui.setup_page import SetupPage

TRACKER = "The tracker is not connected. Connect it on the Setup page."
CALIBRATION = "No calibration yet. Calibrate on the Setup page."
SUBJECT = "Subject ID is empty."
DATE = "Assessment date is empty."
SEX = "Sex is not selected."
DISPLAY = "The display is not 1920x1080 at 100 %. Tick the acknowledgement on the Setup page."


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def ready_page(qapp, connected=True) -> SetupPage:
    page = SetupPage()
    page._client = SimpleNamespace(is_connected=lambda: connected)
    page._calibration_result = object()
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    page._apply_display_check(check_display(1920, 1080, 1.0))
    return page


def test_a_ready_page_has_no_blockers(qapp):
    page = ready_page(qapp)
    assert page.run_blockers() == []
    assert page.can_continue() is True


def test_a_fresh_page_lists_everything_in_order(qapp):
    page = SetupPage()
    page._apply_display_check(check_display(1920, 1080, 1.0))
    # No client, no calibration, no subject, no sex; the date always has a value.
    assert page.run_blockers() == [TRACKER, CALIBRATION, SUBJECT, SEX]
    assert page.can_continue() is False


def test_each_blocker_alone(qapp):
    page = ready_page(qapp, connected=False)
    assert page.run_blockers() == [TRACKER]

    page = ready_page(qapp)
    page._client = None
    assert page.run_blockers() == [TRACKER]

    page = ready_page(qapp)
    page._calibration_result = None
    assert page.run_blockers() == [CALIBRATION]

    page = ready_page(qapp)
    page.subject_id_edit.setText("   ")
    assert page.run_blockers() == [SUBJECT]

    page = ready_page(qapp)
    page.assessment_date = lambda: ""
    assert page.run_blockers() == [DATE]

    page = ready_page(qapp)
    page.sex_combo.setCurrentIndex(0)
    assert page.run_blockers() == [SEX]


def test_the_display_blocker_follows_the_acknowledgement(qapp):
    page = ready_page(qapp)
    page._apply_display_check(check_display(1280, 720, 1.5))
    assert page.run_blockers() == [DISPLAY]
    assert page.can_continue() is False
    page.display_ack_checkbox.setChecked(True)
    assert page.run_blockers() == []
    assert page.can_continue() is True


def test_the_order_is_tracker_calibration_subject_date_sex_display(qapp):
    page = SetupPage()
    page.assessment_date = lambda: ""
    page._apply_display_check(check_display(1280, 720, 1.5))
    assert page.run_blockers() == [TRACKER, CALIBRATION, SUBJECT, DATE, SEX, DISPLAY]


def test_no_continue_blockers_exactly_when_can_continue_across_every_combination(qapp):
    """AC2, as amended 2026-10-07 (SPEC-input-selection-and-follow.md): ``can_continue()`` is
    "no blockers but the tracker and the calibration" -- a Mouse test needs neither -- while
    ``run_blockers() == []`` (a gaze test may start) implies it."""
    page = SetupPage()
    for connected, calibrated, subject, sex, standard, acked in itertools.product(
        (True, False), repeat=6
    ):
        page._client = SimpleNamespace(is_connected=lambda c=connected: c)
        page._calibration_result = object() if calibrated else None
        page.subject_id_edit.setText("P001" if subject else "")
        page.sex_combo.setCurrentIndex(1 if sex else 0)
        page._apply_display_check(
            check_display(1920, 1080, 1.0) if standard else check_display(1280, 720, 1.5)
        )
        page.display_ack_checkbox.setChecked(acked)
        assert (page.continue_blockers() == []) is page.can_continue()
        assert page.can_continue() is bool(subject and sex and (standard or acked))
        assert page.continue_button.isEnabled() is page.can_continue()
        if page.run_blockers() == []:
            assert page.can_continue() is True
        # The tracker and the calibration are the only difference between the two.
        assert [b for b in page.run_blockers() if b not in (TRACKER, CALIBRATION)] == (
            page.continue_blockers()
        )


def test_reading_the_blockers_changes_nothing(qapp):
    page = ready_page(qapp, connected=False)
    enabled = page.continue_button.isEnabled()
    first = page.run_blockers()
    assert page.run_blockers() == first
    assert page.continue_button.isEnabled() is enabled
