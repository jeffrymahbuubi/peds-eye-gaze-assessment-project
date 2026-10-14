"""SPEC-app-drawn-calibration.md 4.8 R3, acceptance A16: the Check accuracy view of the
calibration window (wireframe state 6) with a fake clock and a fake gaze.

Offscreen Qt. The view reads its time from an injected clock and the gaze from an injected
source (what the page hands it: the client's latest sample), so the 11 rings, the green trail of
the last second, the no-gaze hint and the buttons are all read without waiting and without a
device. The flow-level checks (Repeat, Results, Done, ``accuracy_checked`` in the saved record)
are in ``test_calibration_flow.py`` with the real thread against the fake Control.
"""

from __future__ import annotations

import gc
import math
import os
import weakref

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.calibration_settings import (
    BACKGROUNDS,
    BAND_GOOD,
    CalibrationSettings,
    EyeCounts,
    PointScore,
)
from src.ui.calibration_check import (
    CHECK_ACCURACY,
    DONE,
    FADE_S,
    NO_GAZE_S,
    NO_GAZE_TEXT,
    REPEAT,
    RESULTS,
    RING_POSITIONS,
    RING_RADIUS_DEG,
    TRAIL_S,
    CalibrationCheckView,
    GazeTrail,
    eye_lines,
    ring_radius_px,
)
from src.ui.calibration_window import (
    STATE_CHECK,
    STATE_MONITOR,
    STATE_RESULTS,
    STATE_WAITING,
    CalibrationWindow,
)
from tests.calibration_fixtures import FakeGaze, has_green

MM_PER_PX = 527.0 / 1920  # the lab rig, per logical px at 100 %
DISTANCE = 650.0


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_view(qapp, clock=None, gaze=None, size=(1280, 720), **settings):
    clock = clock or Clock()
    gaze = gaze if gaze is not None else FakeGaze()
    view = CalibrationCheckView(CalibrationSettings(**settings), MM_PER_PX, DISTANCE, gaze_source=gaze, clock=clock)
    view.resize(*size)
    view.show()
    QApplication.processEvents()
    return view, clock, gaze


def make_window(qapp, gaze=None, **settings):
    clock = Clock()
    window = CalibrationWindow(
        CalibrationSettings(**settings), MM_PER_PX, DISTANCE, gaze_source=gaze or FakeGaze(), clock=clock
    )
    window.resize(1280, 720)
    window.show()
    QApplication.processEvents()
    return window, clock


def score(point, x, y):
    return PointScore(point, x, y, 0.3, 90, BAND_GOOD)


# -- the rings ------------------------------------------------------------------------------------------


def test_there_are_eleven_rings_in_rows_of_4_3_4_at_the_positions_of_the_spec(qapp):
    assert len(RING_POSITIONS) == 11
    rows = {}
    for x, y in RING_POSITIONS:
        rows.setdefault(y, []).append(x)
    assert rows == {0.18: [0.18, 0.39, 0.61, 0.82], 0.50: [0.29, 0.50, 0.71], 0.82: [0.18, 0.39, 0.61, 0.82]}
    view, _clock, _gaze = make_view(qapp)
    centres = view.ring_centres()
    assert [(c.x(), c.y()) for c in centres] == pytest.approx(
        [(x * view.width(), y * view.height()) for x, y in RING_POSITIONS]
    )


def test_the_ring_radius_is_three_degrees_from_the_geometry(qapp):
    radius = ring_radius_px(MM_PER_PX, DISTANCE)
    assert RING_RADIUS_DEG == 3.0
    assert math.degrees(math.atan(radius * MM_PER_PX / DISTANCE)) == pytest.approx(3.0)
    assert 110 < radius < 140  # about 120 px on the 1920 x 1080 lab rig, as Control draws it
    # The same visual angle on a monitor with other pixels, and at another distance.
    assert ring_radius_px(0.5, DISTANCE) * 0.5 == pytest.approx(radius * MM_PER_PX)
    assert ring_radius_px(MM_PER_PX, 2 * DISTANCE) == pytest.approx(2 * radius)
    assert ring_radius_px(0, 0) > 0  # unknown geometry: the defaults, never a division by zero
    view, _clock, _gaze = make_view(qapp)
    assert view.ring_radius_px() == pytest.approx(radius)


@pytest.mark.parametrize("background", sorted(BACKGROUNDS))
def test_rings_and_plus_signs_use_the_contrast_colour_of_the_background(qapp, background):
    view, _clock, _gaze = make_view(qapp, background=background)
    image = view.grab().toImage()
    assert image.pixelColor(5, 400).name().upper() == BACKGROUNDS[background]  # the stage's colours
    centre = view.ring_centres()[0]
    plus = image.pixelColor(round(centre.x()), round(centre.y()))  # the "+" crosses at the centre
    edge_x = round(centre.x() + view.ring_radius_px())  # the ring at 3 o'clock
    edge = [image.pixelColor(edge_x + d, round(centre.y())) for d in (-2, -1, 0, 1, 2)]
    if background == "black":
        assert plus.lightness() > 200 and any(c.lightness() > 128 for c in edge)  # light ink on black
    else:
        assert plus.lightness() < 60 and any(c.lightness() < 128 for c in edge)  # dark ink on white and grey


# -- the trail: pure model ----------------------------------------------------------------------------------


def test_the_trail_keeps_the_last_second_of_valid_gaze_oldest_first():
    trail = GazeTrail()
    for step in range(8):  # a sample every quarter second (exact in binary: no float fuzz at the edge)
        trail.add(100.0 + step * 0.25, step / 10, 0.5)
    seen = trail.points(101.75)  # the last was seen just now
    assert TRAIL_S == 1.0 and seen[-1] == (0.7, 0.5)
    assert [round(x, 1) for x, _y in seen] == [0.3, 0.4, 0.5, 0.6, 0.7]  # 101.75 - 1.0 = 100.75: from step 3
    assert trail.points(103.0) == []  # long ago: nothing left


def test_no_gaze_for_half_a_second_fades_the_trail_out():
    trail = GazeTrail()
    trail.reset(100.0)
    assert not trail.no_gaze(100.2) and trail.opacity(100.2) == 1.0
    assert trail.no_gaze(100.0 + NO_GAZE_S)  # nothing since the start: the hint from half a second on
    trail.add(101.0, 0.5, 0.5)
    assert not trail.no_gaze(101.49) and trail.opacity(101.49) == 1.0
    assert trail.no_gaze(101.5) and trail.opacity(101.5) == 1.0  # the hint is up, the fade begins
    assert trail.opacity(101.5 + FADE_S / 2) == pytest.approx(0.5)
    assert trail.opacity(101.5 + FADE_S) == 0.0 and trail.opacity(110.0) == 0.0
    assert trail.silent_s(101.6) == pytest.approx(0.6)
    trail.add(102.0, 0.6, 0.5)  # gaze is back
    assert not trail.no_gaze(102.0) and trail.opacity(102.0) == 1.0
    trail.reset(103.0)
    assert trail.points(103.0) == []


# -- the trail: the view with a fake clock and a fake gaze -----------------------------------------------------


def test_a_valid_unsmoothed_sample_joins_the_trail_in_screen_fractions(qapp):
    view, clock, gaze = make_view(qapp)
    view.start()
    gaze.look(0.5, 0.35)
    clock.now += 0.02
    view.tick()
    gaze.look(0.52, 0.37)
    clock.now += 0.02
    view.tick()
    centres = view.trail_centres()
    assert [(c.x(), c.y()) for c in centres] == pytest.approx([(0.5 * 1280, 0.35 * 720), (0.52 * 1280, 0.37 * 720)])


def test_invalid_samples_and_a_sample_seen_twice_do_not_join_the_trail(qapp):
    view, clock, gaze = make_view(qapp)
    view.start()
    gaze.look(0.4, 0.4, valid=False)  # the tracker lost the eyes: not drawn
    clock.now += 0.02
    view.tick()
    assert view.trail_centres() == []
    gaze.look(0.4, 0.4)
    for _ in range(3):  # the same REC read on three frames
        clock.now += 0.016
        view.tick()
    assert len(view.trail_centres()) == 1


def test_the_gaze_already_waiting_when_the_view_opens_is_not_drawn(qapp):
    """The reader is stopped around the run: the client's newest sample is from before the
    calibration. Only a sample that arrives after the view opened counts."""
    gaze = FakeGaze()
    gaze.look(0.2, 0.2)  # stale
    view, clock, _ = make_view(qapp, gaze=gaze)
    view.start()
    clock.now += 0.02
    view.tick()
    assert view.trail_centres() == [] and view.trail.no_gaze(clock.now + 0.5)
    gaze.look(0.3, 0.3)
    clock.now += 0.02
    view.tick()
    assert len(view.trail_centres()) == 1


def test_the_trail_drops_samples_older_than_a_second(qapp):
    view, clock, gaze = make_view(qapp)
    view.start()
    for step in range(30):  # a sample every 60 ms for 1.8 s
        gaze.look(0.1 + 0.02 * step, 0.5)
        clock.now += 0.06
        view.tick()
    xs = [c.x() / view.width() for c in view.trail_centres()]
    # Seen at 100.06 + 0.06 k; the last at 101.8, so those from 100.8 on stay: k = 13 to 29.
    assert len(xs) == 17 and xs[-1] == pytest.approx(0.1 + 0.02 * 29) and xs[0] == pytest.approx(0.1 + 0.02 * 13)


def test_the_trail_is_painted_green_and_fades_when_the_gaze_is_lost(qapp):
    view, clock, gaze = make_view(qapp)
    view.start()
    for step in range(3):
        gaze.look(0.5 + 0.01 * step, 0.35)
        clock.now += 0.02
        view.tick()
    where = (0.51 * view.width() + 4, 0.35 * view.height())  # on the middle circle's edge
    assert has_green(view.grab().toImage(), *where)
    clock.now += 0.45  # lost, but not for half a second yet: still fully there
    assert has_green(view.grab().toImage(), *where)
    clock.now += 0.35  # 0.8 s without gaze: past the hint, in the middle of the fade
    assert 0.0 < view.trail.opacity(clock.now) < 1.0
    clock.now += FADE_S + 0.1  # faded out (and older than a second by now)
    assert not has_green(view.grab().toImage(), *where)


def test_the_trail_is_green_on_every_background(qapp):
    for background in sorted(BACKGROUNDS):
        view, clock, gaze = make_view(qapp, background=background)
        view.start()
        gaze.look(0.5, 0.35)
        clock.now += 0.02
        view.tick()
        assert has_green(view.grab().toImage(), 0.5 * view.width() + 4, 0.35 * view.height()), background


# -- the status lines -----------------------------------------------------------------------------------------


def test_the_eye_lines_come_from_the_calibration_and_the_hint_replaces_them_when_there_is_no_gaze(qapp):
    view, clock, gaze = make_view(qapp)
    view.set_result(EyeCounts(left=4, right=5, total=5))
    view.start()
    assert view.status_lines() == ["Left eye: 4 of 5 points valid", "Right eye: 5 of 5 points valid"]
    gaze.look(0.5, 0.5)
    clock.now += 0.2
    view.tick()
    assert view.status_lines()[0].startswith("Left eye:")  # gaze is there
    clock.now += NO_GAZE_S + 0.01  # half a second since the last valid sample
    view.tick()
    assert view.status_lines() == [NO_GAZE_TEXT] == ["No gaze. Check the head position."]
    gaze.look(0.5, 0.5)
    clock.now += 0.02
    view.tick()
    assert view.status_lines() == ["Left eye: 4 of 5 points valid", "Right eye: 5 of 5 points valid"]


def test_losing_the_link_or_the_eyes_gives_the_hint(qapp):
    view, clock, gaze = make_view(qapp)
    view.set_result(EyeCounts(5, 5, 5))
    view.start()
    gaze.look(0.5, 0.5)
    clock.now += 0.02
    view.tick()
    gaze.lose()  # the client forgets its last sample when the link is down
    clock.now += 0.6
    view.tick()
    assert view.status_lines() == [NO_GAZE_TEXT]
    gaze.look(0.5, 0.5, valid=False)  # eyes lost
    clock.now += 0.1
    view.tick()
    assert view.status_lines() == [NO_GAZE_TEXT]


def test_no_gaze_at_all_since_the_view_opened_gives_the_hint_after_half_a_second(qapp):
    view, clock, _gaze = make_view(qapp)
    view.set_result(EyeCounts(5, 5, 5))
    view.start()
    clock.now += 0.4
    view.tick()
    assert view.status_lines()[0].startswith("Left eye")
    clock.now += 0.2
    view.tick()
    assert view.status_lines() == [NO_GAZE_TEXT]


def test_without_calibration_data_there_are_no_eye_lines_and_the_text_is_the_wireframes():
    assert eye_lines(None) == ("", "")
    assert eye_lines(EyeCounts(2, 3, 5)) == ("Left eye: 2 of 5 points valid", "Right eye: 3 of 5 points valid")
    assert eye_lines(EyeCounts(9, 9, 9)) == ("Left eye: 9 of 9 points valid", "Right eye: 9 of 9 points valid")


def test_the_view_with_no_eye_counts_shows_nothing_until_the_hint(qapp):
    view, clock, gaze = make_view(qapp)
    view.start()
    assert view.status_lines() == []
    clock.now += 0.6
    view.tick()
    assert view.status_lines() == [NO_GAZE_TEXT]


# -- the buttons and the timer ----------------------------------------------------------------------------------


def test_the_three_buttons_say_what_the_wireframe_says_and_emit(qapp):
    view, _clock, _gaze = make_view(qapp)
    assert (view.repeat_button.text(), view.results_button.text(), view.done_button.text()) == (
        REPEAT, RESULTS, DONE,
    ) == ("Repeat calibration", "Results", "Done")
    seen = []
    view.repeatRequested.connect(lambda: seen.append("repeat"))
    view.resultsRequested.connect(lambda: seen.append("results"))
    view.doneRequested.connect(lambda: seen.append("done"))
    for button in (view.repeat_button, view.results_button, view.done_button):
        button.click()
    assert seen == ["repeat", "results", "done"]
    assert view.done_button.objectName() == "wtmhPrimary" and view.repeat_button.objectName() == "wtmhGhost"


def test_the_timer_runs_between_start_and_stop_and_stops_when_hidden(qapp):
    view, _clock, _gaze = make_view(qapp)
    assert not view._timer.isActive()
    view.start()
    assert view._timer.isActive()
    view.stop()
    assert not view._timer.isActive()
    view.start()
    view.hide()
    assert not view._timer.isActive()


def test_the_view_reads_the_source_it_was_given_and_holds_a_bound_method_weakly(qapp):
    class Page:
        def __init__(self) -> None:
            self.reads = 0

        def gaze_input(self):
            self.reads += 1
            return None

    page = Page()
    page_ref = weakref.ref(page)
    view = CalibrationCheckView(CalibrationSettings(), MM_PER_PX, DISTANCE, gaze_source=page.gaze_input, clock=Clock())
    view.tick()
    assert page.reads == 1  # the page's own reader is polled, not a copy
    del page
    gc.collect()
    view.tick()  # the page is gone: no gaze, no crash, and the view did not keep it alive
    assert page_ref() is None and view.status_lines() == [NO_GAZE_TEXT]
    view.set_source(None)
    view.tick()


# -- the window: the state and the buttons around it --------------------------------------------------------------


def test_the_map_has_a_check_accuracy_button_beside_show_monitor(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    QApplication.processEvents()
    assert window.check_button.text() == CHECK_ACCURACY == "Check accuracy"
    xs = [b.mapTo(window, b.rect().topLeft()).x() for b in (
        window.improve_button, window.monitor_button, window.check_button, window.back_button)]
    assert xs == sorted(xs) and len(set(xs)) == 4  # Improve, Show Monitor, Check accuracy ... Back
    ys = {b.mapTo(window, b.rect().topLeft()).y() for b in (window.monitor_button, window.check_button)}
    assert max(ys) - min(ys) <= 2  # one row, beside Show Monitor
    window.dismiss()


def test_check_accuracy_opens_the_view_and_results_goes_back_to_the_map(qapp):
    window, _clock = make_window(qapp)
    window.check_button.click()
    assert window.state() == STATE_WAITING and not window.accuracy_checked()  # nothing to check yet
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(4, 5, 5))
    assert window.state() == STATE_RESULTS and not window.accuracy_checked()
    window.check_button.click()
    assert window.state() == STATE_CHECK and window.checking() and window.check.isVisible()
    assert window.check._timer.isActive() and window.accuracy_checked()
    assert window.check.status_lines() == ["Left eye: 4 of 5 points valid", "Right eye: 5 of 5 points valid"]
    window.check.results_button.click()
    assert window.state() == STATE_RESULTS and not window.check.isVisible() and not window.check._timer.isActive()
    assert window.accuracy_checked()  # it was opened: that stays true
    window.check_button.click()  # and it can be opened again
    assert window.state() == STATE_CHECK
    window.dismiss()


def test_check_accuracy_from_show_monitor_takes_the_head_panel_away(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    window.monitor_button.click()
    assert window.state() == STATE_MONITOR and window.monitor_card.isVisible()
    window.check_button.click()
    assert window.state() == STATE_CHECK and not window.monitor_card.isVisible() and not window.map.dimmed()
    window.check.results_button.click()
    assert window.state() == STATE_RESULTS and window.monitor_button.text() == "Show Monitor"
    window.dismiss()


def test_repeat_is_improve_and_done_is_back_and_escape_and_the_x_ask_to_cancel(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    window.check_button.click()
    seen = []
    window.improveRequested.connect(lambda: seen.append("improve"))
    window.backRequested.connect(lambda: seen.append("back"))
    window.cancelRequested.connect(lambda: seen.append("cancel"))  # the flow turns it into Back here
    window.check.repeat_button.click()
    window.check.done_button.click()
    window._escape.activated.emit()
    window.close_button.click()
    assert seen == ["improve", "back", "cancel", "cancel"]
    window.dismiss()


def test_a_new_run_leaves_the_view_and_stops_its_timer(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    window.check_button.click()
    window.begin_run()  # Repeat calibration: all points again
    assert window.state() == STATE_WAITING and not window.check.isVisible() and not window.check._timer.isActive()
    assert not window.accuracy_checked()  # it described the old result: a new run starts false
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))  # the re-run's map
    assert not window.accuracy_checked()
    window.check_button.click()
    assert window.accuracy_checked()  # opened for this result
    window.dismiss()


def test_dismissing_the_window_stops_the_view(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    window.check_button.click()
    assert window.check._timer.isActive()
    window.dismiss()
    assert not window.check._timer.isActive()


def test_the_window_gives_the_view_its_gaze_source_and_its_clock(qapp):
    gaze = FakeGaze()
    window, clock = make_window(qapp, gaze=gaze, background="black")
    window.show_results([score(1, 0.5, 0.5)], eyes=EyeCounts(5, 5, 5))
    window.check_button.click()
    gaze.look(0.5, 0.35)
    clock.now += 0.02
    window.check.tick()
    assert len(window.check.trail_centres()) == 1
    assert has_green(window.check.grab().toImage(), 0.5 * window.check.width() + 4, 0.35 * window.check.height())
    window.dismiss()
