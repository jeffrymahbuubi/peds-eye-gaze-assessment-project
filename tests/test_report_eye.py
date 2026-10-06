"""SPEC-compass-task-flow.md 4D.5 pupil and fixations, 4D.10 G5 (pupil) and G6
(fixations), plus the readers they sit on."""

from __future__ import annotations

import pytest

from src.data.report_eye import (
    FrameIndex,
    GazeFrame,
    PupilParams,
    load_gaze_frames,
    load_raw_samples,
    pupil_series,
    sample_period_s,
    trial_fixations,
    trial_pupil,
)
from src.data.report_geometry import Geometry
from tests.report_fixtures import RIG_META, SEC, raw_samples, write_all_gaze

GEO = Geometry.from_metadata(RIG_META)
DT = 1 / 150
ONSET, END = 1 * SEC, 2 * SEC


def ramp(t: float) -> float:
    """3.5 mm until onset (1 s), then a ramp to 3.8 mm at the end of the trial (2 s)."""
    return 3.5 if t < 1.0 else 3.5 + 0.3 * min(t - 1.0, 1.0)


def pupil(samples, *, iti_ms=800.0, dt=DT, **kw):
    times, values = pupil_series(samples, 0)
    return trial_pupil(times, values, ONSET, END, sample_dt_s=dt, iti_ms=iti_ms, **kw)


# -- G5: pupil -------------------------------------------------------------------------


def test_change_is_the_trial_mean_minus_the_baseline():
    out = pupil(raw_samples(3.0, ramp))
    assert out["baseline_mm"] == pytest.approx(3.5)
    assert out["mean_mm"] == pytest.approx(3.65, abs=0.005)
    assert out["change_mm"] == pytest.approx(out["mean_mm"] - out["baseline_mm"])
    assert out["change_pct"] == pytest.approx(out["change_mm"] / 3.5 * 100)
    assert out["change_mm"] == pytest.approx(0.15, abs=0.005)


def test_a_sample_with_one_eye_invalid_is_excluded_not_averaged_in():
    # The left eye drops out for 200 ms while the right eye reads a wild (but in range)
    # 8 mm: the sample is unusable, so the mean must not move.
    samples = raw_samples(
        3.0,
        lambda t: 8.0 if 1.4 <= t <= 1.6 else 3.5,
        left_ok=lambda t: not 1.4 <= t <= 1.6,
    )
    times, _ = pupil_series(samples, 0)
    assert not any(1.3 * SEC < t < 1.7 * SEC for t in times)  # the gap plus its +-100 ms mask
    assert pupil(samples)["mean_mm"] == pytest.approx(3.5)


def test_the_blink_mask_removes_valid_samples_within_100_ms_of_an_invalid_one():
    samples = raw_samples(3.0, invalid=lambda t: t == 1.5)  # exactly one invalid sample
    times, _ = pupil_series(samples, 0)
    # 31 samples lie within 100 ms of it (itself included): 450 - 31 survive.
    assert len(times) == 450 - 31
    assert not any(abs(t - 1.5 * SEC) <= 0.1 * SEC for t in times)


def test_values_outside_1_5_to_9_mm_are_unusable():
    low = raw_samples(1.0, lambda t: 0.4)
    high = raw_samples(1.0, lambda t: 11.0)
    assert pupil_series(low, 0) == ([], [])
    assert pupil_series(high, 0) == ([], [])
    assert pupil_series(raw_samples(1.0, lambda t: 1.5), 0)[0]  # the bounds are inclusive


def test_a_baseline_with_less_than_half_its_samples_is_none_and_never_zero():
    # Lost tracking at 0.6-0.78 s, masked to 0.5-0.88 s, leaves 0.88-1.0 s of the
    # 0.7-1.0 s baseline window: 40 % of it.
    samples = raw_samples(3.0, ramp, invalid=lambda t: 0.6 <= t < 0.78)
    out = pupil(samples)
    assert out["baseline_mm"] is None
    assert out["change_mm"] is None and out["change_pct"] is None
    assert out["mean_mm"] is not None


def test_a_baseline_with_at_least_half_its_samples_is_kept():
    samples = raw_samples(3.0, ramp, invalid=lambda t: 0.6 <= t < 0.7)  # leaves 0.8-1.0: 67 %
    out = pupil(samples)
    assert out["baseline_mm"] == pytest.approx(3.5)
    assert out["change_mm"] is not None


def test_a_first_trial_with_no_pre_roll_has_no_baseline():
    samples = [s for s in raw_samples(3.0, ramp) if s.t_s >= 1.0]  # recording starts at onset
    out = pupil(samples)
    assert out["baseline_mm"] is None and out["change_mm"] is None
    assert out["mean_mm"] is not None


def test_the_baseline_window_is_the_shorter_of_300_ms_and_the_iti():
    def f(t):  # 4.0 before 0.9 s, 3.5 in the last 100 ms before onset
        return 4.0 if t < 0.9 else 3.5

    samples = raw_samples(3.0, f)
    assert pupil(samples, iti_ms=100.0)["baseline_mm"] == pytest.approx(3.5)
    assert pupil(samples, iti_ms=800.0)["baseline_mm"] == pytest.approx((4.0 * 2 + 3.5) / 3, abs=0.02)
    assert pupil(samples, iti_ms=None)["baseline_mm"] == pytest.approx((4.0 * 2 + 3.5) / 3, abs=0.02)
    # No blank between trials (ITI 0) leaves no clean baseline at all.
    assert pupil(samples, iti_ms=0.0)["baseline_mm"] is None


def test_without_a_sample_period_there_is_no_baseline():
    assert pupil(raw_samples(3.0, ramp), dt=None)["baseline_mm"] is None


def test_an_empty_trial_window_has_no_mean():
    out = trial_pupil([], [], ONSET, END, sample_dt_s=DT, iti_ms=800.0)
    assert out == {"mean_mm": None, "baseline_mm": None, "change_mm": None, "change_pct": None}


def test_the_host_clock_offset_moves_the_series_not_the_values():
    samples = raw_samples(1.0)
    shifted, values = pupil_series(samples, 5 * SEC)
    plain, values0 = pupil_series(samples, 0)
    assert [t - 5 * SEC for t in shifted] == plain and values == values0


def test_pupil_params_are_the_spec_ones():
    p = PupilParams()
    assert (p.min_mm, p.max_mm, p.blink_mask_ms, p.baseline_ms, p.min_baseline_coverage) == (
        1.5, 9.0, 100.0, 300.0, 0.5
    )


# -- G6: fixations (the vendor FPOGID definition) ----------------------------------------


def fr(t_s, fid, dur, *, valid=True, x=0.3, y=0.5):
    return GazeFrame(round(t_s * SEC), x, y, valid, fid, dur)


def window_of(frames):
    return FrameIndex(frames).window(ONSET, END)


def test_a_carry_in_fixation_belongs_to_the_previous_trial():
    frames = [fr(0.9, 1, 0.10), fr(1.05, 1, 0.25), fr(1.3, 2, 0.1), fr(1.4, 2, 0.2)]
    found = trial_fixations(window_of(frames), ONSET, END, GEO)
    assert [round(f.dur_ms) for f in found] == [200]  # fixation 1 started at 0.8 s: excluded


def test_a_fixation_still_running_at_the_trial_end_is_clipped_to_it():
    frames = [
        fr(1.25, 2, 0.05), fr(1.35, 2, 0.15), fr(1.45, 2, 0.25),
        fr(1.85, 3, 0.05), fr(1.95, 3, 0.15), fr(2.0, 3, 0.20),
        fr(2.1, 3, 0.30),  # after the trial: the cumulative duration here must not count
    ]
    found = trial_fixations(window_of(frames), ONSET, END, GEO)
    assert [round(f.dur_ms) for f in found] == [250, 200]
    assert [round(f.start_ns / SEC, 3) for f in found] == [1.2, 1.8]


def test_a_fixation_starting_exactly_at_the_onset_counts_and_at_the_end_does_not():
    at_onset = [fr(1.1, 5, 0.1)]  # start 1.0 = onset
    at_end = [fr(2.0, 6, 0.0)]  # start 2.0 = end
    assert len(trial_fixations(window_of(at_onset), ONSET, END, GEO)) == 1
    assert trial_fixations(window_of(at_end), ONSET, END, GEO) == []


def test_a_trial_with_no_fixation_has_none():
    frames = [fr(1.2, None, None), fr(1.3, 4, 0.1, valid=False), fr(1.4, 4, 0.2, valid=False)]
    assert trial_fixations(window_of(frames), ONSET, END, GEO) == []
    assert trial_fixations([], ONSET, END, GEO) == []


def test_a_fixation_without_a_duration_is_skipped():
    assert trial_fixations(window_of([fr(1.2, 7, None)]), ONSET, END, GEO) == []


def test_the_position_is_the_canvas_normalized_mean_of_the_fixation_frames():
    frames = [fr(1.2, 2, 0.1, x=0.3), fr(1.3, 2, 0.2, x=0.5)]
    (fix,) = trial_fixations(window_of(frames), ONSET, END, GEO)
    expected_x, expected_y = GEO.monitor_to_canvas_norm(0.4, 0.5)
    assert (fix.x, fix.y) == pytest.approx((expected_x, expected_y))


def test_duplicate_t_ns_rows_are_counted_once(tmp_path):
    path = tmp_path / "gaze_stream.csv"
    t = round(1.3 * SEC)
    path.write_text(
        "t_ns,x,y,valid,fixation_id,fix_duration_s,pupil_left,pupil_right\n"
        f"{round(1.2 * SEC)},0.3,0.5,1,2,0.1,,\n"
        f"{t},0.3,0.5,1,2,0.2,,\n"
        f"{t},0.9,0.5,1,2,0.2,,\n"  # the same stamp written again: the first one wins
        f"{t},0.9,0.5,1,2,0.2,,\n",
        encoding="utf-8",
    )
    frames = load_gaze_frames(tmp_path)
    assert len(frames) == 2
    (fix,) = trial_fixations(FrameIndex(frames).window(ONSET, END), ONSET, END, GEO)
    assert fix.x == pytest.approx(GEO.monitor_to_canvas_norm(0.3, 0.5)[0])


def test_the_loader_sorts_skips_bad_rows_and_tolerates_a_missing_file(tmp_path):
    assert load_gaze_frames(tmp_path) == []
    (tmp_path / "gaze_stream.csv").write_text(
        "t_ns,x,y,valid,fixation_id,fix_duration_s,pupil_left,pupil_right\n"
        "300,0.1,0.1,1,,,,\n"
        "100,0.2,0.2,0,,,,\n"
        "x,0.3,0.3,1,,,,\n"
        "200,oops,0.3,1,,,,\n",
        encoding="utf-8",
    )
    frames = load_gaze_frames(tmp_path)
    assert [f.t_ns for f in frames] == [100, 300]
    assert [f.valid for f in frames] == [False, True]


# -- the all_gaze reader ---------------------------------------------------------------------


def test_raw_samples_round_trip_through_all_gaze_csv(tmp_path):
    samples = raw_samples(0.2, lambda t: 3.25)
    write_all_gaze(tmp_path / "all_gaze.csv", samples)
    loaded = load_raw_samples(tmp_path)
    assert len(loaded) == len(samples)
    assert loaded[3].t_s == pytest.approx(samples[3].t_s, abs=1e-5)
    assert (loaded[3].x, loaded[3].valid, loaded[3].pupil_l_ok) == (0.4, True, True)
    assert loaded[3].pupil_l == pytest.approx(3.25)
    assert sample_period_s(loaded) == pytest.approx(DT, abs=1e-5)


def test_the_raw_reader_gives_none_without_the_file_or_the_gaze_columns(tmp_path):
    assert load_raw_samples(tmp_path) is None
    (tmp_path / "all_gaze.csv").write_text("A,B\n1,2\n", encoding="utf-8")
    assert load_raw_samples(tmp_path) is None


def test_the_sample_period_ignores_pause_gaps():
    samples = raw_samples(0.5) + [
        s._replace(t_s=s.t_s + 10.0) for s in raw_samples(0.5)
    ]
    assert sample_period_s(samples) == pytest.approx(DT)
    assert sample_period_s(samples[:1]) is None
