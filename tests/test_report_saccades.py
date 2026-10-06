"""SPEC-compass-task-flow.md 4D.5 / 4D.10 G4: I-VT saccades on the device-rate samples."""

from __future__ import annotations

import math
import random

import pytest

from src.data.report_geometry import Geometry
from src.data.saccades import (
    IvtParams,
    detect_saccades,
    filter_widths,
    split_segments,
    window_saccades,
)

RIG = Geometry(
    screen_w_px=1920, screen_h_px=1080, phys_w_mm=527.0, phys_h_mm=296.0, distance_mm=650.0
)


def x_at(deg: float, origin: float = 0.2) -> float:
    """Monitor-normalized x that is ``deg`` of visual angle right of ``origin``."""
    return origin + 2 * 650 * math.tan(math.radians(deg / 2)) / 527.0


def stream(rate_hz, plan):
    """``(t_s, x, y, valid)`` from ``plan``: a list of ``(n, x_deg_start, x_deg_end, valid)``
    segments, each a linear move over ``n`` samples (start == end is a fixation)."""
    out, i = [], 0
    for n, a, b, valid in plan:
        for j in range(n):
            frac = j / (n - 1) if n > 1 else 0.0
            deg = a + (b - a) * frac
            out.append((i / rate_hz, x_at(deg), 0.5, valid))
            i += 1
    return out


# -- the filter widths follow the rate --------------------------------------------


def test_filter_widths_at_150_and_60_hz():
    assert filter_widths(1 / 150) == (5, 3)
    assert filter_widths(1 / 60) == (3, 1)


def test_segments_split_at_invalid_samples_and_gaps_over_75_ms():
    s = [(0.0, 0, 0, True), (0.01, 0, 0, True), (0.02, 0, 0, False), (0.03, 0, 0, True),
         (0.04, 0, 0, True), (0.20, 0, 0, True), (0.21, 0, 0, True)]
    sizes = [len(seg) for seg in split_segments(s, 0.075)]
    assert sizes == [2, 2, 2]


# -- one clean saccade -------------------------------------------------------------


def one_saccade(rate_hz, ramp_ms=40):
    n_ramp = round(ramp_ms / 1000 * rate_hz) + 1
    return stream(rate_hz, [(30, 0, 0, True), (n_ramp, 0, 5, True), (30, 5, 5, True)])


def test_a_five_degree_ramp_at_150_hz_is_one_saccade_with_the_analytic_peak():
    found = detect_saccades(one_saccade(150), RIG)
    assert len(found) == 1
    s = found[0]
    assert s.amplitude_deg == pytest.approx(5.0, abs=0.3)
    m, k = filter_widths(1 / 150)
    analytic_peak = 5.0 / (2 * k / 150)  # the 40 ms difference window sees the whole ramp
    assert analytic_peak == pytest.approx(125.0)
    assert s.peak_velocity_deg_s == pytest.approx(analytic_peak, rel=0.15)
    assert 0.0 < s.mean_velocity_deg_s <= s.peak_velocity_deg_s * 1.01


def test_the_same_scenario_at_60_hz_is_one_saccade():
    found = detect_saccades(one_saccade(60, ramp_ms=33), RIG)
    assert len(found) == 1
    assert found[0].amplitude_deg == pytest.approx(5.0, abs=0.3)
    analytic_peak = 5.0 / (2 * 1 / 60)  # m=3, k=1
    assert found[0].peak_velocity_deg_s == pytest.approx(analytic_peak, rel=0.15)


def test_the_onset_is_the_first_sample_above_threshold():
    found = detect_saccades(one_saccade(150), RIG)
    # The ramp starts at sample 29 (t = 29 / 150); the first velocity above the
    # threshold comes a little after it, never before it.
    assert found[0].onset_s >= 29 / 150
    assert found[0].offset_s > found[0].onset_s


# -- what must not be a saccade ----------------------------------------------------


@pytest.mark.parametrize("rate_hz", [150, 60])
def test_deterministic_jitter_alone_is_no_saccade(rate_hz):
    rng = random.Random(7)
    s = [
        (i / rate_hz, x_at(rng.uniform(-0.3, 0.3)), 0.5 + rng.uniform(-0.3, 0.3) / 30, True)
        for i in range(400)
    ]
    assert detect_saccades(s, RIG) == []


def test_alternating_jitter_is_no_saccade():
    s = [(i / 150, x_at(0.3 if i % 2 else -0.3), 0.5, True) for i in range(300)]
    assert detect_saccades(s, RIG) == []


def test_a_blink_inside_a_fixation_gives_no_saccade():
    s = stream(150, [(40, 0, 0, True), (15, 0, 0, False), (40, 0, 0, True)])
    assert detect_saccades(s, RIG) == []


def test_a_move_that_happens_across_a_blink_is_not_a_saccade():
    # Fixation, 100 ms of lost tracking, a different fixation 5 deg away: the
    # displacement is inside the gap, and a velocity is never taken across it.
    s = stream(150, [(40, 0, 0, True), (15, 0, 0, False), (40, 5, 5, True)])
    assert detect_saccades(s, RIG) == []


def test_a_pause_gap_in_the_time_axis_is_a_break():
    first = stream(150, [(40, 0, 0, True)])
    second = [(t + 10.0, x, y, v) for t, x, y, v in stream(150, [(40, 5, 5, True)])]
    assert detect_saccades(first + second, RIG) == []


def test_a_small_step_is_rejected_by_the_amplitude_floor():
    step = stream(150, [(30, 0, 0, True), (30, 0.4, 0.4, True)])
    low_bar = IvtParams(threshold_deg_s=5.0)
    assert detect_saccades(step, RIG, low_bar) == []  # 0.4 deg < the 0.5 deg floor
    assert len(detect_saccades(step, RIG, IvtParams(threshold_deg_s=5.0, min_amplitude_deg=0.3))) == 1


def test_a_single_fast_sample_is_not_enough():
    s = stream(150, [(40, 0, 0, True), (1, 3, 3, True), (40, 0, 0, True)])
    assert detect_saccades(s, RIG, IvtParams(min_samples=4)) == []


def test_without_the_physical_geometry_there_is_nothing_to_measure():
    blind = Geometry(screen_w_px=1920, screen_h_px=1080)
    assert detect_saccades(one_saccade(150), blind) == []


def test_too_few_samples_do_not_raise():
    assert detect_saccades([], RIG) == []
    assert detect_saccades([(0.0, 0.5, 0.5, True)], RIG) == []
    assert detect_saccades([(0.0, 0.5, 0.5, False)] * 5, RIG) == []


# -- which trial a saccade belongs to ----------------------------------------------


def test_the_clock_offset_puts_the_saccade_in_the_right_trial_window():
    found = detect_saccades(one_saccade(150), RIG)
    onset_s = found[0].onset_s
    offset_ns = 5_000_000_000_000
    on_ns = offset_ns + round(onset_s * 1e9)
    # Window A holds the onset, window B starts after it.
    a = (on_ns - 100_000_000, on_ns + 100_000_000)
    b = (on_ns + 100_000_000, on_ns + 900_000_000)
    assert len(window_saccades(found, offset_ns, *a)) == 1
    assert window_saccades(found, offset_ns, *b) == []
    # Shifting the clock offset by 300 ms moves the same saccade out of A and into B.
    shifted = offset_ns + 300_000_000
    assert window_saccades(found, shifted, *a) == []
    assert len(window_saccades(found, shifted, *b)) == 1


def test_a_window_is_half_open_at_the_end():
    found = detect_saccades(one_saccade(150), RIG)
    on_ns = round(found[0].onset_s * 1e9)
    assert window_saccades(found, 0, on_ns, on_ns + 1) == found
    assert window_saccades(found, 0, on_ns - 5, on_ns) == []
