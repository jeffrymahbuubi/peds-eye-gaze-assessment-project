"""SPEC-compass-task-flow.md 4C.5 / AC8: the run bar's one-line operator status."""

from __future__ import annotations

import pytest

from src.engine.tracking_status import (
    GAZE_LOST_AFTER_S,
    LEVEL_ERROR,
    LEVEL_OK,
    LEVEL_WARN,
    run_status_line,
    tracking_status,
)


def test_the_threshold_is_one_second():
    assert GAZE_LOST_AFTER_S == 1.0


@pytest.mark.parametrize("since", [0.0, 0.016, 0.4, 0.999])
def test_valid_gaze_is_tracking_ok(since):
    assert tracking_status(True, since) == ("tracking OK", LEVEL_OK)


def test_single_invalid_frames_never_show():
    """FPOGV drops during saccades and blinks: anything under the threshold is OK."""
    assert tracking_status(True, 0.5)[1] == LEVEL_OK


@pytest.mark.parametrize(
    "since,text",
    [(1.0, "no gaze for 1 s"), (1.9, "no gaze for 1 s"), (3.2, "no gaze for 3 s"), (61.0, "no gaze for 61 s")],
)
def test_gaze_lost_for_a_while_is_amber(since, text):
    assert tracking_status(True, since) == (text, LEVEL_WARN)


def test_connected_but_no_valid_sample_yet_is_waiting():
    assert tracking_status(True, None) == ("waiting for gaze", LEVEL_WARN)


@pytest.mark.parametrize("since", [None, 0.0, 5.0])
def test_a_dropped_tracker_is_red_whatever_the_gaze_says(since):
    assert tracking_status(False, since) == ("tracker DISCONNECTED", LEVEL_ERROR)


def test_levels_are_distinct():
    assert len({LEVEL_OK, LEVEL_WARN, LEVEL_ERROR}) == 3


# -- the whole line ----------------------------------------------------------


def test_the_full_line_of_a_recorded_run():
    text, _level = tracking_status(True, 0.1)
    assert run_status_line(4, 12, text) == "Trial 4/12 · tracking OK"


def test_the_practice_prefix():
    line = run_status_line(2, 3, "tracking OK", practice=True)
    assert line == "PRACTICE (not recorded) · Trial 2/3 · tracking OK"


def test_a_lost_tracker_goes_into_the_line():
    assert run_status_line(1, 6, "tracker DISCONNECTED") == "Trial 1/6 · tracker DISCONNECTED"


def test_the_paused_line_drops_the_tracking_text():
    assert run_status_line(4, 12, "tracking OK", paused=True) == "Paused · Trial 4/12"
    assert run_status_line(2, 3, "tracking OK", practice=True, paused=True) == (
        "PRACTICE (not recorded) · Paused · Trial 2/3"
    )


def test_before_the_first_trial_it_still_reads_trial_one():
    """During the pre-roll the task has no trial yet (index -1): never "Trial 0/N"."""
    assert run_status_line(0, 12, "tracking OK") == "Trial 1/12 · tracking OK"
