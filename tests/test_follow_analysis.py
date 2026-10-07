"""SPEC-input-selection-and-follow.md H8, A7: smooth-pursuit gain and catch-up saccades from the
device-rate gaze against the target's logged track. Synthetic traces with a known gain, injected
catch-up saccades and noise; nothing here touches the disk or Qt."""

from __future__ import annotations

import pytest

from src.data.report_eye import RawSample
from src.data.report_follow import (
    DEFAULT_FOLLOW,
    FollowParams,
    GazeSeries,
    TargetTrack,
    catch_up,
    pursuit_gain,
)
from src.data.saccades import Saccade, detect_saccades
from tests.follow_fixtures import (
    OFFSET_NS,
    RATE_HZ,
    SEC,
    circular,
    geometry,
    horizontal,
    simulate_gaze,
    target_track_rows,
    vertical,
)

GEOM = geometry()


def to_mm(x, y):
    mx, my = GEOM.canvas_to_monitor_norm(x, y)
    return mx * GEOM.phys_w_mm, my * GEOM.phys_h_mm


def analyse(position, *, seconds=10.0, params=DEFAULT_FOLLOW, **sim):
    """Everything the report does for one trial: ``(gain, usable_s, catch-up count, valid s,
    injected jump times)``."""
    samples, jumps = simulate_gaze(position, seconds, **sim)
    saccades = detect_saccades([(s.t_s, s.x, s.y, s.valid) for s in samples], GEOM)
    series = GazeSeries(samples, OFFSET_NS, saccades, GEOM, params)
    onset, end = OFFSET_NS, OFFSET_NS + round(seconds * SEC)
    track = TargetTrack.from_log(target_track_rows(position, seconds, origin_ns=OFFSET_NS), 0, onset, end)
    gain, usable = pursuit_gain(series, track.mapped(to_mm), onset, end, GEOM, params)
    count, valid_s = catch_up(series, saccades, OFFSET_NS, onset, end)
    return gain, usable, count, valid_s, jumps


# -- A7: the gain --------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_gaze_at_0_8_times_the_targets_speed_with_noise_has_a_gain_of_0_8(seed):
    gain, usable, _count, _valid, jumps = analyse(horizontal(), gain=0.8, noise_deg=0.1, seed=seed)
    assert jumps  # the child needed catch-up saccades to stay near the target
    assert gain == pytest.approx(0.8, abs=0.05)
    assert usable > 3.0  # plenty of clean pursuit left after the saccades and the bounces


@pytest.mark.parametrize("gain_in", [0.55, 0.8, 0.95, 1.0])
def test_the_gain_follows_the_gain_put_in(gain_in):
    gain, *_ = analyse(horizontal(), gain=gain_in, noise_deg=0.1, catch_up_deg=2.8)
    assert gain == pytest.approx(gain_in, abs=0.05)


@pytest.mark.parametrize("make", [vertical, circular])
def test_it_works_along_the_other_paths_too_the_tangent_for_the_circle(make):
    gain, usable, *_ = analyse(make(), gain=0.8, noise_deg=0.1)
    assert gain == pytest.approx(0.8, abs=0.05)
    assert usable > 3.0


def test_a_slower_target_gives_the_same_gain():
    gain, *_ = analyse(horizontal(0.1), gain=0.8, noise_deg=0.05)
    assert gain == pytest.approx(0.8, abs=0.06)


def test_a_gaze_that_does_not_follow_leaves_the_3_degree_zone_and_has_no_gain():
    # Standing still, the gaze is within 3 deg of a 9 deg/s target for the first 0.3 s only.
    gain, usable, *_ = analyse(horizontal(), gain=0.0, noise_deg=0.05, catch_up_deg=None, seconds=3.0)
    assert gain is None and usable < 0.5


def test_samples_further_than_3_degrees_from_the_target_are_not_used():
    # Perfectly smooth pursuit (gain 1) but 5 degrees behind: never within max_err, so no gain.
    position = horizontal()
    offset = 5.0 * 11.34 / 527.0  # 5 deg in x, canvas-normalized

    def behind(t):
        x, y = position(t)
        return x - offset, y

    samples, _ = simulate_gaze(behind, 10.0, gain=1.0, noise_deg=0.05, catch_up_deg=None)
    saccades = detect_saccades([(s.t_s, s.x, s.y, s.valid) for s in samples], GEOM)
    series = GazeSeries(samples, OFFSET_NS, saccades, GEOM)
    track = TargetTrack.from_log(
        target_track_rows(position, 10.0, origin_ns=OFFSET_NS), 0, OFFSET_NS, OFFSET_NS + 10 * SEC
    )
    gain, usable = pursuit_gain(series, track.mapped(to_mm), OFFSET_NS, OFFSET_NS + 10 * SEC, GEOM)
    assert gain is None and usable == 0.0
    # ... and the same gaze within the limit is used.
    wide = FollowParams(max_err_deg=6.0)
    gain, usable = pursuit_gain(
        GazeSeries(samples, OFFSET_NS, saccades, GEOM, wide),
        track.mapped(to_mm), OFFSET_NS, OFFSET_NS + 10 * SEC, GEOM, wide,
    )
    assert gain == pytest.approx(1.0, abs=0.05) and usable > 3.0


# -- A7: fewer than 0.5 s usable gives None ------------------------------------------------------------


def test_a_trial_with_under_half_a_second_of_usable_gaze_has_no_gain():
    gain, usable, *_ = analyse(horizontal(), seconds=0.45, gain=1.0, noise_deg=0.05, catch_up_deg=None)
    assert gain is None and usable < 0.5


def test_a_trial_that_is_mostly_blinks_has_no_gain():
    def blinking(t_s):  # eyes open for 0.3 s out of every 2.0 s
        return (t_s % 2.0) >= 0.3

    gain, usable, *_ = analyse(horizontal(), seconds=4.0, gain=1.0, noise_deg=0.05,
                               catch_up_deg=None, invalid=blinking)
    assert gain is None and usable < 0.5


def test_the_threshold_is_the_parameter_not_a_constant():
    samples, _ = simulate_gaze(horizontal(), 1.5, gain=1.0, noise_deg=0.05, catch_up_deg=None)
    saccades = detect_saccades([(s.t_s, s.x, s.y, s.valid) for s in samples], GEOM)
    track = TargetTrack.from_log(
        target_track_rows(horizontal(), 1.5, origin_ns=OFFSET_NS), 0, OFFSET_NS, OFFSET_NS + round(1.5 * SEC)
    ).mapped(to_mm)
    args = (OFFSET_NS, OFFSET_NS + round(1.5 * SEC), GEOM)
    strict = FollowParams(min_usable_s=2.0)
    assert pursuit_gain(GazeSeries(samples, OFFSET_NS, saccades, GEOM, strict), track, *args, strict)[0] is None
    lax = FollowParams(min_usable_s=0.5)
    assert pursuit_gain(GazeSeries(samples, OFFSET_NS, saccades, GEOM, lax), track, *args, lax)[0] == pytest.approx(
        1.0, abs=0.05
    )


def test_the_defaults_are_the_specs_numbers():
    assert DEFAULT_FOLLOW.as_dict() == {
        "max_err_deg": 3.0, "bounce_excl_ms": 100.0, "min_usable_s": 0.5, "followed_pct": 50.0,
        "window_ms": 100.0, "saccade_pad_samples": 1,
    }


# -- A7: catch-up saccades ------------------------------------------------------------------------------------


def test_the_injected_catch_up_saccades_are_counted():
    _gain, _usable, count, valid_s, jumps = analyse(horizontal(), gain=0.8, noise_deg=0.1)
    assert len(jumps) >= 4
    assert count == len(jumps)
    assert valid_s == pytest.approx(10.0, abs=0.1)
    # per second of valid gaze, as the report states it
    assert count / valid_s == pytest.approx(len(jumps) / 10.0, abs=0.1)


def test_no_saccades_no_catch_up():
    _gain, _usable, count, _valid, jumps = analyse(horizontal(), gain=1.0, noise_deg=0.05, catch_up_deg=None)
    assert jumps == [] and count == 0


def test_invalid_time_is_not_valid_seconds():
    _gain, _usable, _count, valid_s, _jumps = analyse(
        horizontal(), gain=1.0, noise_deg=0.05, catch_up_deg=None, seconds=4.0,
        invalid=lambda t: 1.0 <= t < 2.0,
    )
    assert valid_s == pytest.approx(3.0, abs=0.05)


# -- the saccade samples are dropped, one sample each side ---------------------------------------------------


def test_saccade_samples_and_one_each_side_are_dropped():
    samples = [RawSample(i / RATE_HZ, 0.5, 0.5, True, 3.5, True, 3.5, True) for i in range(300)]
    sac = Saccade(onset_s=1.0, offset_s=1.02, amplitude_deg=3.0, peak_velocity_deg_s=80.0,
                  mean_velocity_deg_s=60.0)
    series = GazeSeries(samples, OFFSET_NS, [sac], GEOM)
    first, last = round(1.0 * RATE_HZ), round(1.02 * RATE_HZ)
    dropped = [i for i, d in enumerate(series.dropped) if d]
    assert dropped == list(range(first - 1, last + 2))
    assert FollowParams().saccade_pad_samples == 1
    wide = GazeSeries(samples, OFFSET_NS, [sac], GEOM, FollowParams(saccade_pad_samples=3))
    assert [i for i, d in enumerate(wide.dropped) if d] == list(range(first - 3, last + 4))


def test_a_blink_inside_the_window_costs_that_sample_its_place():
    samples, _ = simulate_gaze(horizontal(), 4.0, gain=1.0, noise_deg=0.05, catch_up_deg=None,
                               invalid=lambda t: 2.0 <= t < 2.05)
    series = GazeSeries(samples, OFFSET_NS, [], GEOM)
    track = TargetTrack.from_log(
        target_track_rows(horizontal(), 4.0, origin_ns=OFFSET_NS), 0, OFFSET_NS, OFFSET_NS + 4 * SEC
    ).mapped(to_mm)
    with_blink, usable_blink = pursuit_gain(series, track, OFFSET_NS, OFFSET_NS + 4 * SEC, GEOM)
    clean_samples, _ = simulate_gaze(horizontal(), 4.0, gain=1.0, noise_deg=0.05, catch_up_deg=None)
    _clean, usable_clean = pursuit_gain(
        GazeSeries(clean_samples, OFFSET_NS, [], GEOM), track, OFFSET_NS, OFFSET_NS + 4 * SEC, GEOM
    )
    assert usable_blink < usable_clean  # the windows touching the blink are gone
    assert with_blink == pytest.approx(1.0, abs=0.06)  # ... and the rest is not disturbed


# -- bounces ------------------------------------------------------------------------------------------------


def track_of(position, seconds):
    return TargetTrack.from_log(
        target_track_rows(position, seconds, origin_ns=OFFSET_NS), 0, OFFSET_NS, OFFSET_NS + round(seconds * SEC)
    )


def test_a_straight_path_bounces_at_its_ends_and_a_circle_never_does():
    bounces = track_of(horizontal(), 10.0).bounces()
    # 0.8 wide at 0.2 per second: the ends are at 4 s and 8 s (each good to one 50 ms log step).
    assert len(bounces) == 2
    for found, expected in zip(bounces, (4.0, 8.0), strict=True):
        assert abs((found - OFFSET_NS) / SEC - expected) <= 0.06
    assert track_of(circular(), 10.0).bounces() == []
    # The vertical sweep is shorter in px for the same px/s: a bounce every 2.25 s.
    assert len(track_of(vertical(), 10.0).bounces()) == 4


def test_samples_within_100_ms_of_a_bounce_are_excluded():
    samples, _ = simulate_gaze(horizontal(), 10.0, gain=1.0, noise_deg=0.05, catch_up_deg=None)
    series = GazeSeries(samples, OFFSET_NS, [], GEOM)
    track = track_of(horizontal(), 10.0).mapped(to_mm)
    args = (OFFSET_NS, OFFSET_NS + 10 * SEC, GEOM)
    _g, with_exclusion = pursuit_gain(series, track, *args, FollowParams(bounce_excl_ms=100.0))
    _g, without = pursuit_gain(series, track, *args, FollowParams(bounce_excl_ms=0.0))
    assert without - with_exclusion >= 2 * 0.2 * 0.8  # two bounces, 0.2 s each, less the windows' overlap


# -- the track -----------------------------------------------------------------------------------------------------


def test_the_track_interpolates_linearly_and_says_none_outside_its_span():
    track = TargetTrack([(0, 0.0, 0.0), (1_000, 1.0, 2.0), (3_000, 3.0, 2.0)])
    assert track.at(0) == (0.0, 0.0) and track.at(3_000) == (3.0, 2.0)
    assert track.at(500) == pytest.approx((0.5, 1.0))
    assert track.at(2_000) == pytest.approx((2.0, 2.0))
    assert track.at(-1) is None and track.at(3_001) is None
    assert track.at(-1, clamp=True) == (0.0, 0.0) and track.at(9_999, clamp=True) == (3.0, 2.0)
    assert TargetTrack([]).at(0) is None and len(track) == 3


def test_a_trial_re_presented_after_a_pause_is_windowed_on_its_own_times():
    rows = [(100, 0, 0.1, 0.5), (200, 0, 0.2, 0.5), (1_000, 0, 0.9, 0.5), (1_100, 1, 0.3, 0.5)]
    first = TargetTrack.from_log(rows, 0, 50, 250)  # the first presentation of trial 0
    again = TargetTrack.from_log(rows, 0, 900, 1_050)  # the same id, presented again
    assert first.t == [100, 200] and again.t == [1_000]
    assert TargetTrack.from_log(None, 0, 0, 1).t == []
