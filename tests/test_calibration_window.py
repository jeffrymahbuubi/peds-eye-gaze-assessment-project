"""The calibration window (SPEC-app-drawn-calibration.md 4.1, 4.3b, 4.4, 4.5, 4.6, 4.9; A1, A5, A10,
A10b, A19).

Offscreen Qt with a fake clock: the icon's pose is a function of the clock, so the glide, the
settle, the hold and the sizes are read without waiting. Nothing here touches a device.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.engine.calibration_motion import (
    PHASE_GLIDE,
    PHASE_HOLD,
    PHASE_IDLE,
    PHASE_SETTLE,
    WOBBLE_DEG,
)
from src.engine.calibration_run import (
    EVENT_FALLBACK,
    EVENT_PROCESSING,
    EVENT_RESULT_POINT,
    EVENT_START_POINT,
    CalibrationEvent,
)
from src.engine.calibration_settings import (
    BACKGROUNDS,
    BAND_FAIR,
    BAND_GOOD,
    BAND_NONE,
    BAND_POOR,
    ICON_IDS,
    SIZES_DEG,
    CalibrationSettings,
    PointScore,
    app_layout,
    icon_diameter_px,
    icon_path,
)
from src.ui import design_tokens as tokens
from src.ui.calibration_map import NO_SCORE, RING_PX, WEAK_RING_PX, ResultsMap, circle_look
from src.ui.calibration_window import (
    BACK,
    HIDE_MONITOR,
    IMPROVE,
    SHOW_MONITOR,
    STATE_MONITOR,
    STATE_PROCESSING,
    STATE_RESULTS,
    STATE_RUNNING,
    STATE_WAITING,
    CalibrationWindow,
)

MM_PER_PX = 527.0 / 1920  # the lab rig, per logical px at 100 %
DISTANCE = 650.0
DELAY = 0.8


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_window(qapp, clock=None, **settings) -> tuple[CalibrationWindow, Clock]:
    clock = clock or Clock()
    window = CalibrationWindow(CalibrationSettings(**settings), MM_PER_PX, DISTANCE, clock=clock)
    window.resize(1280, 720)
    window.show()
    QApplication.processEvents()
    return window, clock


def start(window, clock, point, delay=DELAY):
    x, y = app_layout(5)[point - 1]
    window.handle_event(CalibrationEvent(EVENT_START_POINT, point, x, y, clock.now, delay, 5))
    return x, y


def score(point, band, error=None, value=0, x=0.5, y=0.5):
    return PointScore(point, x, y, error, value, band)


# -- A1: the glide and the hold ------------------------------------------------------------------


def test_the_icon_enters_from_the_corner_glides_to_each_point_and_holds_by_delay(qapp):
    window, clock = make_window(qapp)
    assert window.state() == STATE_WAITING and window.stage.sample().phase == PHASE_IDLE
    previous = (0.0, 0.0)  # the first point: the icon enters from the top-left corner
    for number in range(1, 6):
        t0 = clock.now
        x, y = start(window, clock, number)
        assert window.state() == STATE_RUNNING
        first = window.stage.sample()
        assert (first.x, first.y) == previous and first.phase == PHASE_GLIDE  # leaves where it was
        clock.now = t0 + 0.2
        mid = window.stage.sample()
        assert mid.phase == PHASE_GLIDE
        large = icon_diameter_px("normal", MM_PER_PX, DISTANCE)  # the preset's one size, also while moving
        assert window.stage.diameter_px() == pytest.approx(large)
        assert min(previous[0], x) <= mid.x <= max(previous[0], x)
        assert min(previous[1], y) <= mid.y <= max(previous[1], y) and (mid.x, mid.y) != (x, y)  # on its way
        clock.now = t0 + DELAY
        hold = window.stage.sample()
        assert (hold.phase, hold.x, hold.y, hold.angle_deg) == (PHASE_HOLD, x, y, 0.0)  # still
        assert window.stage.diameter_px() == pytest.approx(large)  # and as large as in the glide (4.9 R5)
        clock.now = t0 + DELAY + 1.0  # the rest of the point: it does not move
        assert window.stage.sample() == hold
        previous = (x, y)
        clock.now += 0.001


def test_the_icon_settles_before_the_hold_keeps_its_size_and_is_still_in_the_hold(qapp):
    window, clock = make_window(qapp)
    t0 = clock.now
    start(window, clock, 1)
    large = icon_diameter_px("normal", MM_PER_PX, DISTANCE)
    phases = []
    for step in range(0, 81):
        clock.now = t0 + step * 0.01
        sample = window.stage.sample()
        phases.append(sample.phase)
        assert window.stage.diameter_px() == pytest.approx(large)  # never smaller (4.9 R5)
        if sample.phase == PHASE_HOLD:
            assert sample.angle_deg == 0
        if sample.phase == PHASE_SETTLE:
            assert abs(sample.angle_deg) <= WOBBLE_DEG  # the wobble only fades
    assert phases[0] == PHASE_GLIDE and PHASE_SETTLE in phases and phases[-1] == PHASE_HOLD
    assert phases == sorted(phases, key=[PHASE_GLIDE, PHASE_SETTLE, PHASE_HOLD].index)  # never back to moving


def test_the_first_paint_in_the_hold_is_no_later_than_delay_after_the_record(qapp):
    window, clock = make_window(qapp)
    t0 = clock.now
    start(window, clock, 1)
    clock.now = t0 + 0.3
    window.stage.grab()  # paints while it is still gliding
    clock.now = t0 + DELAY - 0.01  # the window is a frame late, still inside DELAY
    window.stage.grab()
    (entry,) = window.hold_report()
    assert entry["point"] == 1 and entry["start"] == t0
    assert entry["hold_scheduled"] <= t0 + DELAY
    assert entry["hold_painted"] is not None and entry["hold_painted"] - t0 <= DELAY


def test_a_late_event_does_not_move_the_hold(qapp):
    """The window gets the record 100 ms late; the clock time of the record still rules."""
    window, clock = make_window(qapp)
    t_record = clock.now
    clock.now = t_record + 0.1
    window.handle_event(CalibrationEvent(EVENT_START_POINT, 1, 0.1, 0.1, t_record, DELAY, 5))
    clock.now = t_record + DELAY
    assert window.stage.sample().phase == PHASE_HOLD


def test_result_points_processing_and_the_fallback_event(qapp):
    window, clock = make_window(qapp)
    start(window, clock, 1)
    window.handle_event(CalibrationEvent(EVENT_RESULT_POINT, 1, 0.1, 0.1, clock.now, DELAY, 5))
    assert window.state() == STATE_RUNNING  # the icon stays where it is until the next point
    assert window.hold_report()[0]["result"] == clock.now
    window.handle_event(CalibrationEvent(EVENT_PROCESSING, 5, 0.5, 0.5, clock.now, DELAY, 5))
    assert window.state() == STATE_PROCESSING
    window.handle_event(CalibrationEvent(EVENT_FALLBACK, reason="no CALIB_START_PT after CALIBRATE_START"))
    assert not window.isVisible()  # Control's own window takes over (4.2)


# -- A10b: the size, from the geometry ------------------------------------------------------------


@pytest.mark.parametrize("size", sorted(SIZES_DEG))
def test_the_icon_is_drawn_at_the_degrees_of_its_size_preset(qapp, size):
    """A19: one diameter in the glide, the settle and the hold, equal to the preset's degrees."""
    window, clock = make_window(qapp, size=size)
    t0 = clock.now
    start(window, clock, 1)
    expected = icon_diameter_px(size, MM_PER_PX, DISTANCE)
    seen = set()
    for step in range(0, 101):  # the whole point, past the hold's start
        clock.now = t0 + step * 0.01
        seen.add(window.stage.sample().phase)
        assert window.stage.diameter_px() == pytest.approx(expected)
    assert seen == {PHASE_GLIDE, PHASE_SETTLE, PHASE_HOLD}
    # ... and those pixels are the preset's visual angle at the viewing distance.
    import math

    assert 2 * math.degrees(math.atan(expected * MM_PER_PX / 2 / DISTANCE)) == pytest.approx(SIZES_DEG[size])


def test_a_larger_preset_draws_a_larger_icon(qapp):
    diameters = []
    for size in ("small", "normal", "large"):
        window, clock = make_window(qapp, size=size)
        start(window, clock, 1)
        diameters.append(window.stage.diameter_px())
    assert diameters == sorted(diameters) and len(set(diameters)) == 3


def test_the_centre_is_a_fraction_of_the_screen_in_logical_and_physical_px(qapp):
    """A10 (offscreen): the point lands on CALX x width whatever the display scale, because the
    window covers the screen; physical px are the logical ones times the device pixel ratio."""
    window, clock = make_window(qapp)
    t0 = clock.now
    x, y = start(window, clock, 2)
    clock.now = t0 + DELAY
    sample = window.stage.sample()
    centre = window.stage.center_px(sample)
    assert (centre.x(), centre.y()) == pytest.approx((x * window.stage.width(), y * window.stage.height()))
    ratio = window.stage.devicePixelRatioF()
    assert window.stage.center_physical_px(sample) == pytest.approx((centre.x() * ratio, centre.y() * ratio))
    # At 150 %: a 1280 x 720 logical screen is 1920 x 1080 physical, and 0.9 is 1728 either way.
    assert 0.9 * 1280 * 1.5 == pytest.approx(0.9 * 1920)


# -- the background and the icon art --------------------------------------------------------------


@pytest.mark.parametrize("background", sorted(BACKGROUNDS))
def test_the_stage_is_painted_in_the_chosen_background(qapp, background):
    window, _clock = make_window(qapp, background=background)
    image = window.stage.grab().toImage()
    assert QColor(image.pixelColor(5, 400)).name().upper() == BACKGROUNDS[background]


@pytest.mark.parametrize("icon", ICON_IDS)
def test_every_built_in_icon_is_there_and_is_drawn(qapp, icon):
    assert icon_path(icon).is_file()
    window, clock = make_window(qapp, target=icon)
    t0 = clock.now
    start(window, clock, 1)  # the centre (it comes first, 4.8 R1)
    clock.now = t0 + DELAY
    assert not window.stage._pixmap.isNull()
    image = window.stage.grab().toImage()
    middle = image.pixelColor(window.stage.width() // 2, window.stage.height() // 2)
    assert middle.name().upper() != BACKGROUNDS["white"]  # the icon's own pixels, not the background


# -- states, Esc and the x ---------------------------------------------------------------------------


def test_escape_the_x_and_closing_the_window_all_cancel(qapp):
    window, clock = make_window(qapp)
    seen = []
    window.cancelRequested.connect(lambda: seen.append("cancel"))
    window._escape.activated.emit()
    window.close_button.click()
    assert seen == ["cancel", "cancel"]
    window.close()  # Alt+F4, or the taskbar
    assert seen == ["cancel"] * 3


def test_the_flow_closing_the_window_is_not_a_cancel(qapp):
    window, _clock = make_window(qapp)
    seen = []
    window.cancelRequested.connect(lambda: seen.append("cancel"))
    window.dismiss()
    assert seen == [] and not window.isVisible()


def test_the_x_is_at_the_top_right_and_the_cursor_stays_visible(qapp):
    window, _clock = make_window(qapp)
    button = window.close_button
    assert button.x() > window.width() - 80 and button.y() < 40
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.cursor().shape() != Qt.CursorShape.BlankCursor and not window.stage.testAttribute(Qt.WidgetAttribute.WA_SetCursor)


def test_the_window_covers_a_screen_corner_to_corner(qapp):
    window, _clock = make_window(qapp)
    screen = qapp.primaryScreen()
    window.present_on(screen)
    QApplication.processEvents()
    assert window.isFullScreen() and window.geometry() == screen.geometry()
    window.dismiss()


def test_processing_shows_its_text_and_dots(qapp):
    window, clock = make_window(qapp)
    start(window, clock, 5)
    window.handle_event(CalibrationEvent(EVENT_PROCESSING, 5, 0.5, 0.5, clock.now, DELAY, 5))
    image = window.stage.grab().toImage()
    assert image.pixelColor(window.stage.width() // 2, window.stage.height() // 2 + 16).name().upper() != BACKGROUNDS["white"]


# -- A5: the results map ------------------------------------------------------------------------------


def test_each_band_has_its_token_colours_and_a_weak_point_a_thicker_ring():
    good = circle_look(score(1, BAND_GOOD, 0.5, 83))
    fair = circle_look(score(2, BAND_FAIR, 1.5, 50))
    poor = circle_look(score(3, BAND_POOR, 2.5, 17))
    none = circle_look(score(4, BAND_NONE))
    assert (good.fill, good.ring, good.text, good.ring_px) == (tokens.SUCCESS_SUBTLE, tokens.SUCCESS, "83", RING_PX)
    assert (fair.fill, fair.ring, fair.text, fair.ring_px) == (tokens.WARNING_SUBTLE, tokens.WARNING, "50", WEAK_RING_PX)
    assert (poor.fill, poor.ring, poor.text, poor.ring_px) == (tokens.DANGER_SUBTLE, tokens.DANGER, "17", WEAK_RING_PX)
    assert (none.fill, none.ring, none.text, none.ring_px) == (tokens.DISABLED_FILL, tokens.BORDER_STRONG, NO_SCORE, WEAK_RING_PX)
    assert NO_SCORE == "-" and WEAK_RING_PX > RING_PX


def test_the_map_puts_a_circle_at_each_point_and_paints_its_colour(qapp):
    results = ResultsMap()
    results.resize(960, 600)
    scores = [
        score(1, BAND_GOOD, 0.5, 83, 0.1, 0.1),
        score(2, BAND_FAIR, 1.5, 50, 0.9, 0.9),
        score(3, BAND_POOR, 2.5, 17, 0.9, 0.1),
        score(4, BAND_NONE, None, 0, 0.1, 0.9),
        score(5, BAND_GOOD, 0.2, 93, 0.5, 0.5),
    ]
    results.set_scores(scores, 16 / 9)
    rect = results.monitor_rect()
    assert rect.width() / rect.height() == pytest.approx(16 / 9)
    for one in scores:
        centre = results.circle_center(one)
        assert centre.x() == pytest.approx(rect.left() + one.x * rect.width())
        assert centre.y() == pytest.approx(rect.top() + one.y * rect.height())
    assert [look.text for look in results.looks()] == ["83", "50", "17", "-", "93"]
    image = results.grab().toImage()

    def fill_at(one):
        centre = results.circle_center(one)
        return image.pixelColor(int(centre.x()), int(centre.y() - results.circle_diameter() * 0.38)).name().upper()

    assert fill_at(scores[0]) == tokens.SUCCESS_SUBTLE.upper()
    assert fill_at(scores[1]) == tokens.WARNING_SUBTLE.upper()
    assert fill_at(scores[2]) == tokens.DANGER_SUBTLE.upper()
    assert fill_at(scores[3]) == tokens.DISABLED_FILL.upper()


def test_the_results_screen_has_the_three_buttons_and_the_attention_line(qapp):
    window, clock = make_window(qapp)
    window.show_results([score(1, BAND_FAIR, 1.5, 50, 0.1, 0.1), score(2, BAND_GOOD, 0.3, 90, 0.9, 0.9)])
    assert window.state() == STATE_RESULTS
    assert window.attention_label.text() == "1 point needs attention. Check the head position, then Improve calibration."
    assert (window.improve_button.text(), window.monitor_button.text(), window.back_button.text()) == (
        IMPROVE, SHOW_MONITOR, BACK,
    ) == ("Improve calibration", "Show Monitor", "Back")
    seen = []
    window.improveRequested.connect(lambda: seen.append("improve"))
    window.backRequested.connect(lambda: seen.append("back"))
    window.improve_button.click()
    window.back_button.click()
    assert seen == ["improve", "back"]
    window.show_results([score(1, BAND_GOOD, 0.3, 90)])
    assert window.attention_label.text() == "All points are good."
    window.show_results([], "Per-point details were not received.")
    assert window.attention_label.text() == "Per-point details were not received."


def test_show_monitor_toggles_the_head_position_widget_over_the_dimmed_map(qapp):
    window, _clock = make_window(qapp)
    window.show_results([score(1, BAND_GOOD, 0.3, 90)])
    assert not window.monitor_card.isVisible() and not window.map.dimmed()
    window.monitor_button.click()
    assert window.state() == STATE_MONITOR and window.monitor_card.isVisible() and window.map.dimmed()
    assert window.monitor_button.text() == HIDE_MONITOR == "Hide Monitor"
    assert window.head_panel.isVisible()  # the existing widget, live
    window.monitor_button.click()
    assert window.state() == STATE_RESULTS and not window.monitor_card.isVisible() and not window.map.dimmed()
    assert window.monitor_button.text() == SHOW_MONITOR


def test_show_monitor_is_off_before_there_are_results_and_begin_run_resets_the_screen(qapp):
    window, clock = make_window(qapp)
    window.monitor_button.click()
    assert window.state() == STATE_WAITING  # nothing to dim yet
    window.show_results([score(1, BAND_GOOD, 0.3, 90)])
    window.monitor_button.click()
    window.begin_run()  # Improve calibration: all points again
    assert window.state() == STATE_WAITING and not window.monitor_card.isVisible()
    assert window.stage.sample().phase == PHASE_IDLE and window.monitor_button.text() == SHOW_MONITOR
    assert window.hold_report() == []


def test_the_head_panel_reads_the_page_source_not_a_copy(qapp):
    seen = []

    def source():
        seen.append(1)
        return False, None

    window = CalibrationWindow(CalibrationSettings(), MM_PER_PX, DISTANCE, head_source=source)
    window.resize(1280, 720)
    window.show_results([score(1, BAND_GOOD, 0.3, 90)])
    window.monitor_button.click()
    QTest.qWait(200)
    assert seen  # polled while the card is up
    assert window.head_panel.reading().state.name == "NOT_CONNECTED"
    window.dismiss()
