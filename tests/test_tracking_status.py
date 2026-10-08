"""SPEC-compass-task-flow.md 4C.5 / AC8, SPEC-design-system-phase1.md H9: the run bar's operator status."""

from __future__ import annotations

import pytest

from src.engine.tracking_status import (
    GAZE_LOST_AFTER_S,
    LEVEL_ERROR,
    LEVEL_OK,
    LEVEL_WARN,
    RunStatus,
    run_status,
    tracking_status,
)


def test_the_threshold_is_one_second():
    assert GAZE_LOST_AFTER_S == 1.0


@pytest.mark.parametrize("since", [0.0, 0.016, 0.4, 0.999])
def test_valid_gaze_is_tracking_ok(since):
    assert tracking_status(True, since) == ("Tracking OK", LEVEL_OK)


def test_single_invalid_frames_never_show():
    """FPOGV drops during saccades and blinks: anything under the threshold is OK."""
    assert tracking_status(True, 0.5)[1] == LEVEL_OK


@pytest.mark.parametrize(
    "since,text",
    [(1.0, "No gaze for 1 s"), (1.9, "No gaze for 1 s"), (3.2, "No gaze for 3 s"), (61.0, "No gaze for 61 s")],
)
def test_gaze_lost_for_a_while_is_amber(since, text):
    assert tracking_status(True, since) == (text, LEVEL_WARN)


def test_connected_but_no_valid_sample_yet_is_waiting():
    assert tracking_status(True, None) == ("Waiting for gaze", LEVEL_WARN)


@pytest.mark.parametrize("since", [None, 0.0, 5.0])
def test_a_dropped_tracker_is_red_whatever_the_gaze_says(since):
    assert tracking_status(False, since) == ("Tracker disconnected", LEVEL_ERROR)


def test_levels_are_distinct():
    assert len({LEVEL_OK, LEVEL_WARN, LEVEL_ERROR}) == 3


# -- the whole status ---------------------------------------------------------


def test_the_status_of_a_recorded_run_is_the_trial_and_the_tracking_state():
    text, level = tracking_status(True, 0.1)
    status = run_status(4, 12, text, level)
    assert status == RunStatus(trial="Trial 4 of 12", tracking="Tracking OK", level=LEVEL_OK)
    assert status.line == "Trial 4 of 12, Tracking OK"
    assert status.chip == "" and status.pointer == "" and not status.paused


def test_the_practice_chip():
    status = run_status(2, 3, "Tracking OK", LEVEL_OK, practice=True)
    assert status.chip == "PRACTICE" and status.trial == "Trial 2 of 3"
    assert status.line == "PRACTICE, Trial 2 of 3, Tracking OK"
    assert "not recorded" not in status.line  # the chip itself means it


def test_a_lost_tracker_goes_into_the_status_with_its_level():
    text, level = tracking_status(False, None)
    status = run_status(1, 6, text, level)
    assert (status.tracking, status.level) == ("Tracker disconnected", LEVEL_ERROR)


def test_the_paused_status_drops_the_pointer_and_the_tracking_text():
    status = run_status(4, 12, "Tracking OK", LEVEL_OK, paused=True, mouse=True)
    assert status == RunStatus(paused=True, trial="Trial 4 of 12")
    assert status.line == "Paused, Trial 4 of 12"
    practice = run_status(2, 3, "Tracking OK", LEVEL_OK, practice=True, paused=True)
    assert practice.line == "PRACTICE, Paused, Trial 2 of 3"


def test_a_preview_says_so_in_its_chip_and_names_the_mouse():
    status = run_status(1, 3, "", preview=True, mouse=True)
    assert status == RunStatus("PREVIEW", trial="Trial 1 of 3", pointer="Mouse pointer")
    assert run_status(1, 3, "", preview=True, paused=True) == RunStatus("PREVIEW", paused=True)
    assert run_status(1, 3, "", preview=True, paused=True).line == "PREVIEW, Paused"


def test_a_preview_names_its_pointer_in_all_three_cases():
    """SPEC-preview-gaze-pointer.md H4: the real gaze keeps the tracker's state, the mouse
    fallback of a Gaze test says why, a Mouse test just names the mouse."""
    text, level = tracking_status(True, 0.1)
    gaze = run_status(2, 3, text, level, preview=True)
    assert gaze == RunStatus("PREVIEW", trial="Trial 2 of 3", pointer="Gaze pointer", tracking="Tracking OK")
    assert gaze.line == "PREVIEW, Trial 2 of 3, Gaze pointer, Tracking OK"
    lost = run_status(2, 3, *tracking_status(False, None), preview=True)
    assert (lost.pointer, lost.tracking, lost.level) == ("Gaze pointer", "Tracker disconnected", LEVEL_ERROR)
    fallback = run_status(2, 3, "", preview=True, mouse=True, tracker_not_ready=True)
    assert fallback.line == "PREVIEW, Trial 2 of 3, Mouse pointer (tracker not ready)"
    assert run_status(2, 3, "", preview=True, mouse=True).line == "PREVIEW, Trial 2 of 3, Mouse pointer"
    for kwargs in ({}, {"mouse": True}, {"mouse": True, "tracker_not_ready": True}):
        assert run_status(2, 3, "Tracking OK", preview=True, paused=True, **kwargs).line == "PREVIEW, Paused"


def test_the_not_ready_reason_belongs_to_a_preview_only():
    assert run_status(2, 3, "", mouse=True, tracker_not_ready=True).line == "Trial 2 of 3, Mouse pointer"
    assert run_status(2, 3, "", practice=True, mouse=True, tracker_not_ready=True).pointer == "Mouse pointer"


def test_a_mouse_run_names_its_pointer_after_the_trial_and_may_have_no_tracking_text():
    assert run_status(2, 18, "Tracking OK", mouse=True).line == "Trial 2 of 18, Mouse pointer, Tracking OK"
    assert run_status(2, 18, "", mouse=True).line == "Trial 2 of 18, Mouse pointer"  # no tracker


def test_before_the_first_trial_it_still_reads_trial_one():
    """During the pre-roll the task has no trial yet (index -1): never "Trial 0 of N"."""
    assert run_status(0, 12, "Tracking OK").trial == "Trial 1 of 12"


def test_no_part_of_the_status_has_an_interpunct():
    for flags in ({}, {"practice": True}, {"paused": True}, {"preview": True}, {"mouse": True}):
        status = run_status(3, 9, "No gaze for 3 s", LEVEL_WARN, **flags)
        assert "·" not in status.line
