"""SPEC-compass-task-flow.md 4D.5 / 4D.7 / 4D.10 G7 (path decimation) and G8 (heat map),
and the map marks and the moving target's track."""

from __future__ import annotations

import math
import random

import pytest

from src.data.report_eye import GazeFrame, load_gaze_frames
from src.data.report_geometry import Geometry
from src.data.report_visual import (
    HeatParams,
    PathParams,
    blur_grid,
    gaze_path,
    heat_grid,
    heat_map,
    heat_sigma_bins,
    map_marks,
    trial_track,
)
from tests.report_fixtures import RIG_META, SEC, T0, deg_to_dx, monitor_xy

GEO = Geometry.from_metadata(RIG_META)
STEP_NS = round(SEC / 150)


def line(n, *, deg=10.0, jitter_deg=0.05, start_ns=T0, seed=3, y=0.5):
    """``n`` valid frames at 150 Hz drifting ``deg`` of visual angle along x, with a
    small deterministic jitter."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        x = 0.3 + deg_to_dx(deg * i / (n - 1)) + rng.uniform(-1, 1) * deg_to_dx(jitter_deg)
        out.append(GazeFrame(start_ns + i * STEP_NS, x, y, True, None, None))
    return out


def canvas_of(frame):
    return tuple(round(v, 4) for v in GEO.monitor_to_canvas_norm(frame.x, frame.y))


# -- G7: path decimation ------------------------------------------------------------------------


def test_a_straight_jittered_line_thins_to_few_points_with_both_ends_kept():
    frames = line(300)
    (segment,) = gaze_path(frames, GEO)
    assert 10 <= len(segment) < 150 and len(segment) <= 400
    assert tuple(segment[0]) == canvas_of(frames[0])
    assert tuple(segment[-1]) == canvas_of(frames[-1])


def test_kept_points_are_at_least_0_15_degrees_or_100_ms_apart():
    frames = line(300, jitter_deg=0.0)
    (segment,) = gaze_path(frames, GEO)
    # Without jitter the 10 deg line is walked at 0.15 deg steps (~67 points + the end).
    assert 60 <= len(segment) <= 75
    steps = [
        GEO.canvas_angle_deg(tuple(a), tuple(b)) for a, b in zip(segment, segment[1:], strict=False)
    ]
    assert all(s >= 0.14 for s in steps[:-1])


def test_a_stationary_gaze_still_leaves_a_point_every_100_ms():
    still = [GazeFrame(T0 + i * STEP_NS, 0.4, 0.5, True, None, None) for i in range(300)]  # 2 s
    (segment,) = gaze_path(still, GEO)
    assert 18 <= len(segment) <= 22


def test_a_gap_over_150_ms_starts_a_new_polyline():
    first = line(60, deg=2.0)
    second = line(60, deg=2.0, start_ns=T0 + 60 * STEP_NS + 200_000_000)
    assert len(gaze_path(first + second, GEO)) == 2
    close = line(60, deg=2.0, start_ns=T0 + 60 * STEP_NS + 100_000_000)  # a 100 ms gap
    assert len(gaze_path(first + close, GEO)) == 1


def test_an_invalid_frame_ends_the_polyline_and_is_never_drawn():
    frames = line(60, deg=2.0)
    frames[30] = frames[30]._replace(valid=False)
    segments = gaze_path(frames, GEO)
    assert len(segments) == 2
    assert sum(len(s) for s in segments) <= 59


def test_points_off_the_canvas_are_kept_unclipped():
    frames = [GazeFrame(T0 + i * STEP_NS, 0.99, 0.02, True, None, None) for i in range(20)]
    (segment,) = gaze_path(frames, GEO)
    x, y = segment[0]
    assert x > 1.0 and y < 0.0  # monitor (0.99, 0.02) is right of and above the canvas


def test_the_total_is_capped_at_400_points_by_a_uniform_stride_keeping_both_ends():
    frames = line(1500, deg=20.0, jitter_deg=0.0)
    out = gaze_path(frames, GEO, PathParams(min_step_deg=0.0))  # nothing thinned away first
    flat = [p for seg in out for p in seg]
    assert len(flat) == 400
    assert tuple(flat[0]) == canvas_of(frames[0]) and tuple(flat[-1]) == canvas_of(frames[-1])
    xs = [p[0] for p in flat]
    assert xs == sorted(xs)  # still in order


def test_the_cap_applies_across_polylines_and_keeps_their_structure():
    a = line(900, deg=5.0, jitter_deg=0.0)
    b = line(900, deg=5.0, jitter_deg=0.0, start_ns=T0 + 900 * STEP_NS + SEC)
    out = gaze_path(a + b, GEO, PathParams(min_step_deg=0.0))
    assert len(out) == 2 and sum(len(s) for s in out) == 400


def test_nothing_valid_gives_no_path_and_one_frame_gives_a_dot():
    assert gaze_path([], GEO) == []
    assert gaze_path([GazeFrame(T0, 0.5, 0.5, False, None, None)], GEO) == []
    assert len(gaze_path([GazeFrame(T0, 0.5, 0.5, True, None, None)], GEO)[0]) == 1


def test_a_path_in_a_folder_with_no_geometry_still_draws_on_the_reference_rig():
    blind = Geometry()
    assert gaze_path(line(300), blind)  # decimates against the assumed rig, no exception


# -- G8: heat map -----------------------------------------------------------------------------------


def one_sample(canvas_xy=(0.5, 0.5), *, valid=True, t=T0):
    x, y = monitor_xy(*canvas_xy)
    return GazeFrame(t, x, y, valid, None, None)


def heat_of(frames, end_ns, params=None):
    return heat_map([(frames, end_ns)], GEO, params or HeatParams())


def test_one_stationary_sample_peaks_in_the_bin_it_sits_in():
    heat = heat_of([one_sample()], T0 + 100_000_000)
    data = heat["data"]
    assert len(data) == heat["w"] * heat["h"] == 96 * 54
    assert data.index(max(data)) == 27 * 96 + 48  # canvas (0.5, 0.5) -> col 48, row 27
    assert max(data) == 1.0 and heat["empty"] is False
    assert heat["total_s"] == pytest.approx(0.1)
    assert heat["off_canvas_share"] == 0.0


def test_a_sample_near_a_corner_peaks_in_that_corner_bin():
    heat = heat_of([one_sample((0.05, 0.9))], T0 + 100_000_000)
    data = heat["data"]
    peak = data.index(max(data))
    assert (peak % 96, peak // 96) == (int(0.05 * 96), int(0.9 * 54))


def test_the_blur_preserves_mass_away_from_the_edges():
    grid, on_s, off_s = heat_grid([([one_sample()], T0 + 100_000_000)], GEO)
    mass = sum(sum(row) for row in grid)
    assert off_s == 0.0 and on_s == pytest.approx(0.1)
    assert mass == pytest.approx(on_s, rel=0.01)


def test_the_blur_loses_only_what_the_edge_cuts_off():
    grid = [[0.0] * 96 for _ in range(54)]
    grid[0][0] = 1.0  # in the corner: roughly a quarter of the kernel is outside
    blurred = blur_grid(grid, 2.4, 2.3)
    assert 0.2 < sum(sum(r) for r in blurred) < 0.35
    assert blur_grid(grid, 0.0, 0.0) == grid  # no sigma, no blur


def test_each_sample_weighs_the_time_to_the_next_one_capped_at_100_ms():
    a, b = one_sample(t=T0), one_sample((0.2, 0.2), t=T0 + SEC)  # 1 s later: the cap applies
    _, on_s, _ = heat_grid([([a, b], T0 + SEC + 50_000_000)], GEO)
    assert on_s == pytest.approx(0.1 + 0.05)  # a: capped 0.1; b: 50 ms to the window end


def test_duplicate_t_ns_rows_are_not_double_weighted(tmp_path):
    x, y = monitor_xy(0.5, 0.5)
    rows = "".join(f"{T0},{x},{y},1,,,,\n" for _ in range(3))
    (tmp_path / "gaze_stream.csv").write_text(
        "t_ns,x,y,valid,fixation_id,fix_duration_s,pupil_left,pupil_right\n" + rows,
        encoding="utf-8",
    )
    frames = load_gaze_frames(tmp_path)
    assert len(frames) == 1
    assert heat_of(frames, T0 + 100_000_000)["total_s"] == pytest.approx(0.1)


def test_only_frames_inside_trial_windows_are_given_to_the_heat_map():
    # The heat map takes (frames, end) per trial; whatever is not passed (the blank
    # between trials) cannot count. Two windows add up.
    w = [([one_sample()], T0 + 100_000_000), ([one_sample((0.3, 0.3), t=T0 + SEC)], T0 + SEC + 100_000_000)]
    assert heat_map(w, GEO)["total_s"] == pytest.approx(0.2)
    assert heat_map([], GEO)["empty"] is True


def test_sigma_in_bins_follows_the_canvas_aspect_ratio():
    sx, sy = heat_sigma_bins(GEO)
    # 1 deg = px_per_deg monitor px; the canvas is 1640 x 957 px, split into 96 x 54 bins.
    assert sx == pytest.approx(GEO.px_per_deg / (1640 / 96), rel=0.01)
    assert sy == pytest.approx(GEO.px_per_deg / (957 / 54), rel=0.01)
    square = Geometry.from_metadata(dict(RIG_META, canvas_width_px=900, canvas_height_px=900))
    qx, qy = heat_sigma_bins(square)
    assert qx == pytest.approx(GEO.px_per_deg / (900 / 96), rel=0.01)
    assert qy == pytest.approx(GEO.px_per_deg / (900 / 54), rel=0.01)
    assert qx > sx and qy > sy  # a smaller canvas covers fewer degrees per bin
    assert heat_sigma_bins(GEO, HeatParams(sigma_deg=2.0))[0] == pytest.approx(2 * sx)


def test_all_samples_off_the_canvas_give_an_empty_map_and_a_share_of_one():
    off = [one_sample((1.5, 0.5), t=T0 + i * STEP_NS) for i in range(10)]
    heat = heat_of(off, T0 + 20 * STEP_NS)
    assert heat["data"] == [] and heat["empty"] is True and heat["total_s"] == 0.0
    assert heat["off_canvas_share"] == 1.0


def test_off_canvas_gaze_is_excluded_from_the_map_but_counted_in_the_share():
    frames = [one_sample(t=T0), one_sample((1.5, 0.5), t=T0 + 100_000_000)]
    heat = heat_of(frames, T0 + 200_000_000)
    assert heat["off_canvas_share"] == pytest.approx(0.5)
    assert heat["total_s"] == pytest.approx(0.1)


def test_no_valid_gaze_has_no_share_at_all():
    heat = heat_of([one_sample(valid=False)], T0 + 100_000_000)
    assert heat["empty"] and heat["off_canvas_share"] is None


def test_the_map_is_deterministic_and_rounded_to_three_decimals():
    a = heat_of(line(150), T0 + SEC)
    b = heat_of(line(150), T0 + SEC)
    assert a == b
    assert all(v == round(v, 3) and 0.0 <= v <= 1.0 for v in a["data"])


# -- map marks -----------------------------------------------------------------------------------


def trial(n, outcome, x, y, r=0.06, end=None):
    return {"trial": n, "outcome": outcome,
            "target": {"x": x, "y": y, "end_x": end[0] if end else None,
                       "end_y": end[1] if end else None, "radius_norm_x": r, "slot": None}}


def test_trials_on_one_spot_share_a_mark_labelled_with_every_number():
    marks = map_marks(
        [trial(3, "hit", 0.5, 0.5), trial(9, "hit", 0.5, 0.5), trial(4, "hit", 0.8, 0.5)], GEO
    )["marks"]
    assert [(m["label"], m["trials"]) for m in marks] == [("3, 9", [3, 9]), ("4", [4])]
    assert marks[0]["x"] == 0.5 and marks[0]["r"] == 0.06


def test_each_distinct_outcome_on_a_spot_is_drawn_once_side_by_side():
    marks = map_marks([trial(3, "hit", 0.5, 0.5), trial(9, "timeout", 0.5, 0.5)], GEO)["marks"]
    assert [(m["outcome"], m["label"]) for m in marks] == [("hit", "3"), ("timeout", "9")]
    assert marks[0]["x"] < 0.5 < marks[1]["x"] and marks[0]["y"] == marks[1]["y"] == 0.5


def test_a_skipped_trial_gets_its_own_grey_mark():
    marks = map_marks([trial(1, "hit", 0.2, 0.2), trial(2, "skipped", 0.7, 0.7)], GEO)["marks"]
    assert [m["outcome"] for m in marks] == ["hit", "skipped"]


def test_nearby_but_not_overlapping_positions_are_separate_marks():
    marks = map_marks([trial(1, "hit", 0.5, 0.5), trial(2, "hit", 0.5 + 0.06, 0.5)], GEO)["marks"]
    assert len(marks) == 2  # 0.06 apart is a whole radius, more than half a radius


def test_the_vertical_distance_uses_the_canvas_aspect_for_grouping():
    # 0.02 apart in y is 0.02 / aspect = 0.0117 in x units: within half a 0.06 radius.
    marks = map_marks([trial(1, "hit", 0.5, 0.5), trial(2, "hit", 0.5, 0.52)], GEO)["marks"]
    assert len(marks) == 1


def test_a_moving_target_is_marked_where_it_ended():
    t = [trial(1, "hit", 0.1, 0.1, end=(0.6, 0.4))]
    out = map_marks(t, GEO, moving=True)
    assert (out["marks"][0]["x"], out["marks"][0]["y"]) == (0.6, 0.4) and out["note"] is None
    assert map_marks(t, GEO)["marks"][0]["x"] == 0.1  # a static task uses the start


def test_a_moving_target_without_end_positions_is_marked_at_the_start_with_a_note():
    out = map_marks([trial(1, "hit", 0.1, 0.1)], GEO, moving=True)
    assert (out["marks"][0]["x"], out["marks"][0]["y"]) == (0.1, 0.1)
    assert "start position" in out["note"]


def test_no_trials_no_marks():
    assert map_marks([], GEO) == {"marks": [], "note": None}


# -- the moving target's track ---------------------------------------------------------------------


def test_the_track_is_windowed_on_the_trial_not_just_matched_by_id():
    # Trial 2 was interrupted by a pause and re-presented: the id repeats, the rows do not.
    track = [
        (T0 + 10 * SEC, 2, 0.1, 0.1), (T0 + 10 * SEC + 50_000_000, 2, 0.2, 0.2),  # 1st attempt
        (T0 + 30 * SEC, 2, 0.5, 0.5), (T0 + 30 * SEC + 50_000_000, 2, 0.6, 0.6),  # re-presented
        (T0 + 30 * SEC + 60_000_000, 3, 0.9, 0.9),  # another trial's row inside the window
    ]
    assert trial_track(track, 2, T0 + 30 * SEC, T0 + 31 * SEC) == [[0.5, 0.5], [0.6, 0.6]]
    assert trial_track(track, 2, T0 + 10 * SEC, T0 + 11 * SEC) == [[0.1, 0.1], [0.2, 0.2]]
    assert trial_track([], 2, 0, 10) == []


def test_a_long_track_is_thinned_keeping_both_ends():
    track = [(T0 + i * 50_000_000, 0, i / 1000, 0.5) for i in range(500)]
    out = trial_track(track, 0, T0, T0 + 30 * SEC, cap=100)
    assert len(out) == 100 and out[0] == [0.0, 0.5] and out[-1] == [0.499, 0.5]


def test_heat_params_are_the_spec_ones():
    p = HeatParams()
    assert (p.width, p.height, p.sigma_deg, p.weight_cap_ms) == (96, 54, 1.0, 100.0)
    assert math.isclose(PathParams().min_step_deg, 0.15) and PathParams().max_points == 400
