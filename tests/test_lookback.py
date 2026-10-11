"""SPEC-scene-cause-effect-task.md 4.6 (look-back, H10, H11, S7, W4, N2), acceptance A6: the look-back
measures and the waiting-phase distribution on synthetic gaze, against values worked out by hand.
Pure maths (``src/data/lookback.py``): no run folder, no Qt.

The rig is the report's reference one (527 x 296 mm screen at 650 mm, the canvas filling it), so a
degree is ``650 * tan(1 deg) = 11.3454 mm`` and the 1 deg padding is that over the canvas's size in
millimetres: 0.021529 of its width and 0.038330 of its height. Samples come every 10 ms and a
sample counts for the 10 ms up to the next one.
"""

from __future__ import annotations

import math

import pytest

from src.data.lookback import (
    IDLE_BOXES,
    EffectWindow,
    LookbackParams,
    Pauses,
    Sample,
    SampleSeries,
    aoi_at,
    board_regions,
    inside,
    measure_lookback,
    measure_wait,
    pad_norm,
    padded,
    samples_from_frames,
    samples_from_raw,
    scene_box_to_canvas,
    static_box_provider,
)
from src.data.report_eye import GazeFrame, RawSample
from src.data.report_geometry import Geometry

T = 1_791_000_000_000_000_000  # a host-clock origin
MS = 1_000_000
RIG = Geometry(
    screen_w_px=1920, screen_h_px=1080, phys_w_mm=527.0, phys_h_mm=296.0, distance_mm=650.0,
    canvas_w_px=1920, canvas_h_px=1080, canvas_units="physical", display_scale_percent=100,
)
MM_PER_DEG = 650.0 * math.tan(math.radians(1.0))
PAD = (MM_PER_DEG / 527.0, MM_PER_DEG / 296.0)

# Positions (canvas fractions). The rainbow's idle box is (0.45, 0.12, 0.77, 0.36) of the scene,
# i.e. x 0.46429-0.69286, y 0.12-0.36 of the canvas; padded x 0.44276-0.71438, y 0.08167-0.39833.
ON_RAINBOW = (0.58, 0.24)
ON_A_BUTTON = (0.5 / 7, 1.5 / 5)  # the middle of the left button column's first button
IN_THE_CORNER = (0.5 / 7, 0.1)  # cell (0, 0), which is empty
ON_THE_SCENE = (0.5, 0.5)
STATIC = static_box_provider(IDLE_BOXES)


def stream(spans, *, end_ms=2500):
    """Samples every 10 ms from 0 to ``end_ms`` inclusive. ``spans`` are ``(from_ms, to_ms, where)``
    (``from <= t < to``), ``where`` an ``(x, y)`` or ``(x, y, False)`` for an invalid sample at that
    place; the later span wins, and a sample in none is invalid and off the canvas."""
    out = []
    for t in range(0, end_ms + 1, 10):
        sample = Sample(T + t * MS, -1.0, -1.0, False)
        for lo, hi, where in spans:
            if lo <= t < hi:
                sample = Sample(T + t * MS, where[0], where[1], len(where) == 2 or where[2])
        out.append(sample)
    return SampleSeries(out)


def rainbow(duration_ms=2000):
    return EffectWindow("rainbow", T, T + duration_ms * MS, duration_ms)


# -- the AOI -------------------------------------------------------------------------------------


def test_one_degree_is_the_distance_times_the_tangent_over_the_canvas_size():
    pad = pad_norm(RIG, 1.0)
    assert pad == pytest.approx(PAD)
    assert PAD == pytest.approx((0.021529, 0.038330), abs=1e-6)
    assert pad_norm(RIG, 2.0)[0] == pytest.approx(650 * math.tan(math.radians(2)) / 527)


def test_a_degree_is_never_guessed_without_the_physical_size():
    assert pad_norm(Geometry(canvas_w_px=1920, canvas_h_px=1080), 1.0) is None
    assert pad_norm(Geometry(), 1.0) is None


def test_the_scene_is_columns_one_to_five_of_the_board():
    assert scene_box_to_canvas((0.0, 0.0, 1.0, 1.0)) == pytest.approx((1 / 7, 0.0, 6 / 7, 1.0))
    # The rainbow: x = 1/7 + 0.45 * 5/7 = 0.464286 ... 1/7 + 0.77 * 5/7 = 0.692857.
    assert scene_box_to_canvas(IDLE_BOXES["rainbow"]) == pytest.approx(
        (0.464286, 0.12, 0.692857, 0.36), abs=1e-6
    )


def test_the_aoi_is_the_box_grown_by_the_pad_on_every_side():
    box = aoi_at(STATIC, "rainbow", 0.0, PAD)
    assert box == pytest.approx(
        (0.464286 - 0.021529, 0.12 - 0.038330, 0.692857 + 0.021529, 0.36 + 0.038330), abs=1e-6
    )
    assert inside(box, *ON_RAINBOW) and not inside(box, *ON_A_BUTTON)
    assert padded((0.2, 0.2, 0.4, 0.4), (0.01, 0.02)) == pytest.approx((0.19, 0.18, 0.41, 0.42))


# -- A6: the measures against hand-computed values ----------------------------------------------------


def test_look_back_with_a_gaze_loss_in_the_window():
    # W = 0 .. 2500 ms (the 2000 ms effect and 500 ms). The gaze is on a button until 300 ms, on
    # the rainbow from 300 to 1300 ms, lost from 1300 to 1500 ms (the tracker reports the old
    # place with valid = 0), then on the button again.
    series = stream([
        (0, 300, ON_A_BUTTON),
        (300, 1300, ON_RAINBOW),
        (1300, 1500, (*ON_RAINBOW, False)),
        (1500, 2501, ON_A_BUTTON),
    ])
    result = measure_lookback(series, rainbow(), STATIC, PAD)
    assert result.n_samples == 251  # 0, 10, ... 2500
    # Latency: the first valid sample inside is the one at 300 ms.
    assert result.latency_ms == 300.0
    # Dwell: the samples 300 .. 1290 = 100 samples of 10 ms. The 20 lost samples are inside the
    # box but do not count.
    assert result.dwell_ms == 1000.0
    assert result.lookback is True
    assert result.fraction == pytest.approx(1000.0 / 2500.0)  # 0.4
    # Valid: 251 samples less the 20 lost = 231.
    assert result.valid_fraction == pytest.approx(231 / 251)


def test_a_look_of_90_ms_is_no_and_one_of_100_ms_is_yes():
    def look(n_samples):
        series = stream([(0, 1000, ON_A_BUTTON), (1000, 1000 + 10 * n_samples, ON_RAINBOW),
                         (1000 + 10 * n_samples, 2501, ON_A_BUTTON)])
        return measure_lookback(series, rainbow(), STATIC, PAD)

    nine, ten = look(9), look(10)
    assert (nine.dwell_ms, nine.lookback, nine.latency_ms) == (90.0, False, 1000.0)
    assert (ten.dwell_ms, ten.lookback, ten.latency_ms) == (100.0, True, 1000.0)
    assert ten.fraction == pytest.approx(100.0 / 2500.0)


def test_a_window_with_no_valid_sample_is_no_with_nothing_valid():
    series = stream([(0, 2501, (*ON_RAINBOW, False))])
    result = measure_lookback(series, rainbow(), STATIC, PAD)
    assert (result.lookback, result.dwell_ms, result.fraction) == (False, 0.0, 0.0)
    assert result.latency_ms is None and result.valid_fraction == 0.0


def test_a_trial_with_mostly_lost_gaze_reports_how_much_was_valid():
    # Only the first 750 ms were valid, with the gaze on a button: "No", and 76 of the 251
    # samples valid (0 .. 750 ms), so the page can show that this "No" rests on 30 % of the window.
    series = stream([(0, 760, ON_A_BUTTON), (760, 2501, (*ON_RAINBOW, False))])
    result = measure_lookback(series, rainbow(), STATIC, PAD)
    assert result.lookback is False and result.dwell_ms == 0.0 and result.latency_ms is None
    assert result.valid_fraction == pytest.approx(76 / 251)


def test_no_sample_in_the_window_gives_no_figure_at_all():
    empty = SampleSeries([Sample(T - 5000 * MS, *ON_RAINBOW, True)])
    result = measure_lookback(empty, rainbow(), STATIC, PAD)
    assert result.lookback is None and result.dwell_ms is None and result.valid_fraction is None
    assert result.n_samples == 0
    assert measure_lookback(SampleSeries([]), rainbow(), STATIC, PAD).lookback is None


def test_a_gap_in_the_records_counts_for_100_ms_at_most():
    # Samples at 0 and 10 ms, then nothing until 1 s: the gaze at 10 ms is held for 100 ms, not 990.
    series = SampleSeries([
        Sample(T, *ON_RAINBOW, True), Sample(T + 10 * MS, *ON_RAINBOW, True),
        Sample(T + 1000 * MS, *ON_A_BUTTON, True),
    ])
    result = measure_lookback(series, rainbow(), STATIC, PAD)
    assert result.dwell_ms == 10.0 + 100.0
    assert result.latency_ms == 0.0


def test_the_window_closes_500_ms_after_the_effect_ends():
    # A look from 2400 ms on: the samples 2400 .. 2490 (100 ms) are in the window, the one at
    # 2500 ms ends it (it counts for nothing) and those after are out.
    series = stream([(0, 2400, ON_A_BUTTON), (2400, 2601, ON_RAINBOW)], end_ms=2600)
    result = measure_lookback(series, rainbow(), STATIC, PAD)
    assert (result.dwell_ms, result.latency_ms, result.n_samples) == (100.0, 2400.0, 251)
    assert measure_lookback(series, rainbow(), STATIC, PAD, LookbackParams(after_ms=0.0)).lookback is False


def test_the_effect_clock_stops_during_a_pause():
    # The window is 2500 ms, 1000 of them paused (500 .. 1500 ms): 1500 ms count and the 100
    # samples inside the pause are not in it. A look from 1500 to 2000 ms is 500 ms of dwell, a third
    # of the active window, and starts 500 ms into the effect on its own clock.
    series = stream([(0, 1500, ON_A_BUTTON), (1500, 2000, ON_RAINBOW), (2000, 2501, ON_A_BUTTON)])
    result = measure_lookback(series, rainbow(), STATIC, PAD, pauses=Pauses([(T + 500 * MS, T + 1500 * MS)]))
    assert result.n_samples == 151
    assert result.dwell_ms == 500.0
    assert result.fraction == pytest.approx(500.0 / 1500.0)
    assert result.latency_ms == 500.0


# -- N2: the AOI moves with the object ------------------------------------------------------------------


def moving(object_id, elapsed_ms):
    """A box of the scene (0.1 wide, 0.1 high) travelling right at 0.2 of the scene width per second."""
    shift = 0.2 * elapsed_ms / 1000.0
    return (0.1 + shift, 0.4, 0.2 + shift, 0.5)


def test_a_moving_aoi_follows_the_object_a_static_one_misses_it():
    # The gaze rests at 0.505 of the scene width (y = 0.45) and the box passes over it: its right
    # edge reaches it when 0.2 + 0.2 s >= 0.505, i.e. at 1.525 s (the first sample is the one at
    # 1530 ms), and its left edge leaves it when 0.1 + 0.2 s > 0.505, i.e. after 2.025 s (the last
    # is 2020 ms): 1530 .. 2020 = 50 samples, 500 ms. The padding is left out (0).
    where = (1 / 7 + 0.505 * 5 / 7, 0.45)
    series = stream([(0, 4501, where)], end_ms=4500)
    effect = EffectWindow("bike", T, T + 4000 * MS, 4000.0)
    result = measure_lookback(series, effect, moving, (0.0, 0.0))
    assert (result.latency_ms, result.dwell_ms, result.lookback) == (1530.0, 500.0, True)
    # The box where it started (scene 0.1-0.2) never holds that place.
    at_rest = static_box_provider({"bike": (0.1, 0.4, 0.2, 0.5)})
    assert measure_lookback(series, effect, at_rest, (0.0, 0.0)).lookback is False


def test_after_the_effect_the_object_is_back_at_rest():
    # The effect lasts 1 s, so from then on the box stays where it was at 1 s (0.3-0.4 of the
    # scene) instead of travelling on. The gaze rests at 0.31 of the scene width from 1200 ms:
    # inside the box at rest, outside the one that travelled on (0.34-0.44 at 1200 ms).
    where = (1 / 7 + 0.31 * 5 / 7, 0.45)
    series = stream([(0, 1200, (0.9, 0.9)), (1200, 1501, where)], end_ms=1500)
    effect = EffectWindow("bike", T, T + 1000 * MS, 1000.0)
    result = measure_lookback(series, effect, moving, (0.0, 0.0))
    assert (result.latency_ms, result.dwell_ms, result.n_samples) == (1200.0, 300.0, 151)
    # Without the effect's length the box would be taken to travel on.
    unbounded = EffectWindow("bike", T, T + 1000 * MS, None)
    assert measure_lookback(series, unbounded, moving, (0.0, 0.0)).lookback is False


# -- the waiting phase (S7) ------------------------------------------------------------------------------


def test_the_board_regions_are_the_scene_and_eight_drawn_buttons():
    regions = board_regions(RIG, None)
    assert regions.scene == pytest.approx((1 / 7, 0.0, 6 / 7, 1.0))
    # The standard board insets a cell by 6 % of its smaller side (216 px of the 1080): 12.96 px.
    inset = 0.06 * 216
    x0, y0, x1, y1 = regions.buttons[0]  # column 0, row 1
    assert (x0, y0) == pytest.approx((inset / 1920, (216 + inset) / 1080))
    assert (x1, y1) == pytest.approx(((1920 / 7 - inset) / 1920, (432 - inset) / 1080))
    assert len(regions.buttons) == 8
    assert board_regions(Geometry(), None) is None


def test_waiting_time_is_split_between_scene_buttons_and_elsewhere():
    # Prompt end at 0, the choice at 1000 ms: 30 samples on the scene, 50 on a button, 10 in the
    # empty corner and 11 lost (900 .. 1000 ms); the sample at 1000 ms ends the window.
    series = stream([
        (0, 300, ON_THE_SCENE), (300, 800, ON_A_BUTTON), (800, 900, IN_THE_CORNER),
        (900, 1001, (*ON_THE_SCENE, False)),
    ], end_ms=1000)
    result = measure_wait(series, T, T + 1000 * MS, board_regions(RIG, None))
    assert (result.scene_ms, result.buttons_ms, result.other_ms) == (300.0, 500.0, 100.0)
    assert (result.n_samples, result.n_valid) == (101, 90)
    assert result.valid_fraction == pytest.approx(90 / 101)


def test_gaze_off_the_canvas_is_elsewhere_and_so_is_the_gap_between_two_buttons():
    regions = board_regions(RIG, None)
    series = stream([(0, 100, (1.2, 0.5)), (100, 201, (-0.1, 0.5))], end_ms=200)
    result = measure_wait(series, T, T + 200 * MS, regions)
    assert (result.scene_ms, result.buttons_ms, result.other_ms) == (0.0, 0.0, 200.0)
    # A wide gap (80 px) leaves a wider band between the buttons of rows 1 and 2 (the first ends at
    # 392 px, the second starts at 472) than the standard board (419 and 445): 402 px is in the first.
    wide = board_regions(RIG, 80.0)
    assert wide.where(0.5 / 7, 402 / 1080) == "other"
    assert regions.where(0.5 / 7, 402 / 1080) == "buttons"
    assert wide.scene == regions.scene


def test_an_empty_waiting_window_gives_nothing():
    result = measure_wait(SampleSeries([]), T, T + 500 * MS, board_regions(RIG, None))
    assert result.valid_fraction is None and result.scene_ms is None


# -- the sources ---------------------------------------------------------------------------------------------


def test_raw_samples_go_onto_the_host_clock_and_the_canvas():
    canvas = Geometry(
        screen_w_px=1920, screen_h_px=1080, canvas_w_px=1640, canvas_h_px=957,
        offset_y_px=75, canvas_units="physical",
    )
    raw = [RawSample(2.5, 0.5, 0.5, True, 3.5, True, 3.5, True)]
    (sample,) = samples_from_raw(raw, T - 3_000 * MS, canvas)
    assert sample.t_ns == T - 500 * MS  # TIME 2.5 s from a TIME=0 that was 3 s before T
    assert sample.x == pytest.approx((0.5 * 1920) / 1640)
    assert sample.y == pytest.approx((0.5 * 1080 - 75) / 957)
    assert sample.valid is True


def test_gaze_frames_go_onto_the_canvas():
    frames = [GazeFrame(T, 0.5, 0.5, False, None, None)]
    (sample,) = samples_from_frames(frames, RIG)
    assert (sample.t_ns, sample.x, sample.y, sample.valid) == (T, 0.5, 0.5, False)
