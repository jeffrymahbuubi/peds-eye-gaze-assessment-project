"""SPEC-compass-task-flow.md 4D.4-1 / 4D.10 G1: ``EntryTracker``, the debounced
count of entries into the active target. Frames are scripted as a string, one
character per 10 ms: ``O`` valid and on target, ``.`` valid and off target,
``x`` invalid (a dropout)."""

from __future__ import annotations

import pytest

from src.inputs.eye_input import DwellConfig
from src.tasks.entry_tracker import DEFAULT_EXIT_HOLD_MS, ENTER, EXIT, EntryTracker

DT_NS = 10_000_000


def feed(pattern: str, exit_hold_ms: float = 120.0) -> tuple[EntryTracker, list[str | None]]:
    tracker = EntryTracker(exit_hold_ms)
    transitions = [
        tracker.update(i * DT_NS, valid=ch != "x", on_target=ch == "O")
        for i, ch in enumerate(pattern)
    ]
    return tracker, transitions


def test_a_single_clean_visit_is_one_entry():
    tracker, _ = feed("......OOOOOOOO......")
    assert tracker.entries == 1
    assert tracker.first_entry_ns == 6 * DT_NS


def test_a_first_frame_on_target_is_one_entry_at_onset():
    tracker, transitions = feed("OOOO")
    assert tracker.entries == 1
    assert tracker.first_entry_ns == 0
    assert transitions == [ENTER, None, None, None]


def test_never_on_target_is_zero_entries_and_no_first_entry():
    tracker, transitions = feed("." * 50)
    assert tracker.entries == 0
    assert tracker.first_entry_ns is None
    assert tracker.inside is False
    assert transitions == [None] * 50


def test_only_invalid_frames_is_zero_entries():
    tracker, _ = feed("x" * 50)
    assert (tracker.entries, tracker.first_entry_ns) == (0, None)


# The exit commits at the first valid off-target frame >= 120 ms after the first
# one, i.e. the 13th consecutive off frame at 10 ms. Shorter excursions are one visit.
@pytest.mark.parametrize(
    ("off_frames", "entries"),
    [(1, 1), (5, 1), (11, 1), (12, 1), (13, 2), (20, 2), (100, 2)],
)
def test_an_excursion_shorter_than_the_hold_is_flicker_and_longer_is_a_new_entry(off_frames, entries):
    tracker, _ = feed("OOO" + "." * off_frames + "OOO")
    assert tracker.entries == entries


def test_off_target_for_200_ms_and_back_is_two_entries():
    tracker, transitions = feed("OOO" + "." * 20 + "OOO")
    assert tracker.entries == 2
    assert [t for t in transitions if t] == [ENTER, EXIT, ENTER]


def test_flicker_under_120_ms_is_one_entry_however_often_it_repeats():
    tracker, _ = feed("OO" + ("..O" * 30))
    assert tracker.entries == 1


def test_invalid_frames_in_the_middle_of_a_visit_do_not_split_it():
    tracker, _ = feed("OOO" + "x" * 30 + "OOO")
    assert tracker.entries == 1


def test_invalid_for_two_seconds_while_off_target_then_on_is_one_entry():
    tracker, _ = feed("..." + "x" * 200 + "OOO")
    assert tracker.entries == 1
    assert tracker.first_entry_ns == 203 * DT_NS


def test_invalid_for_two_seconds_after_leaving_does_not_commit_the_exit():
    # The gaze left, then tracking was lost: nothing says it did not come back.
    tracker, _ = feed("OOO." + "x" * 200 + "OOO")
    assert tracker.entries == 1


def test_an_invalid_gap_does_not_advance_the_exit_timer_but_a_valid_off_frame_after_it_commits():
    # Off at 40 ms, lost, off again at 250 ms (210 ms after the first): committed.
    tracker, _ = feed("OOO." + "x" * 20 + "." + "OOO")
    assert tracker.entries == 2
    # The second off frame only 60 ms after the first: still one visit.
    tracker, _ = feed("OOO." + "x" * 5 + "." + "OOO")
    assert tracker.entries == 1


def test_an_invalid_frame_is_ignored_even_when_it_says_on_target():
    tracker = EntryTracker()
    assert tracker.update(0, valid=False, on_target=True) is None
    assert (tracker.entries, tracker.first_entry_ns, tracker.inside) == (0, None, False)


def test_first_entry_stays_at_the_first_visit_after_a_second_one():
    tracker, _ = feed("..OO" + "." * 20 + "OO")
    assert tracker.entries == 2
    assert tracker.first_entry_ns == 2 * DT_NS


def test_a_zero_hold_commits_the_exit_at_the_first_off_frame():
    tracker, _ = feed("O.O", exit_hold_ms=0)
    assert tracker.entries == 2


def test_reset_starts_a_new_target_from_scratch():
    tracker, _ = feed("OO" + "." * 20 + "OO")
    tracker.reset()
    assert (tracker.entries, tracker.first_entry_ns, tracker.inside) == (0, None, False)
    assert tracker.update(0, valid=True, on_target=True) == ENTER
    assert tracker.entries == 1


def test_a_trial_that_ends_inside_the_target_keeps_its_count():
    tracker, _ = feed("..OOOOOO")
    assert tracker.inside is True
    assert tracker.entries == 1


def test_the_default_hold_is_the_dwells_own_hold_grace():
    assert DEFAULT_EXIT_HOLD_MS == DwellConfig().hold_grace_ms == 120.0
    assert EntryTracker().exit_hold_ns == 120_000_000
