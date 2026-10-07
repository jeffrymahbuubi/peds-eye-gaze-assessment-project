"""SPEC-compass-task-flow.md 7.1, V2: the Summary map's fixation scanpath and the Detailed
view's gaze path smoothed with the on-screen cursor's own filter. Qt-free; golden numbers
are from synthetic gaze with a known jitter."""

from __future__ import annotations

import json
import math
import random

import pytest

import src.data.report_visual as visual
from src.data.report_cache import (
    REPORT_FILENAME,
    REPORT_VERSION,
    build_report,
    load_or_build_report,
)
from src.data.report_eye import FrameIndex, GazeFrame, load_gaze_frames
from src.data.report_geometry import Geometry
from src.data.report_visual import (
    DEFAULT_SMOOTHING_ALPHA,
    SmoothParams,
    gaze_path,
    smooth_frames,
)
from src.inputs.eye_input import GazeSmoother, SmoothingConfig
from tests.report_fixtures import (
    OFFSET_NS,
    RIG_META,
    SEC,
    T0,
    deg_to_dx,
    monitor_xy,
    raw_samples,
    record,
    write_session,
)

GEO = Geometry.from_metadata(RIG_META)
STEP_NS = round(SEC / 150)
JITTER_DEG = 0.4  # fixational tremor of the synthetic gaze, uniform +-


def noisy_fixations(
    start_ns: int, centres: list[tuple[float, float]], *, seed: int = 5, each_s: float = 0.4
) -> list[GazeFrame]:
    """150 Hz frames resting ``each_s`` seconds at each canvas-normalized centre in turn (one
    FPOGID each, FPOGD cumulative), with a +-0.4 deg uniform jitter on both axes."""
    rng = random.Random(seed)
    jitter = deg_to_dx(JITTER_DEG)
    frames: list[GazeFrame] = []
    n = round(each_s * 150)
    t = start_ns
    for fid, centre in enumerate(centres, start=1):
        cx, cy = monitor_xy(*centre)
        for i in range(n):
            x = cx + rng.uniform(-1, 1) * jitter
            y = cy + rng.uniform(-1, 1) * jitter * 0.5
            frames.append(GazeFrame(t, x, y, True, fid, i / 150))
            t += STEP_NS
    return frames


CENTRES = [(0.25, 0.3), (0.5, 0.6), (0.75, 0.35)]


def noisy_folder(tmp_path, *, settings=None, centres=CENTRES):
    meta = dict(RIG_META, raw_clock_offset_ns=OFFSET_NS, planned_trials=2, completed_trials=2,
                outcome="completed")
    if settings is not None:
        meta["settings"] = settings
    records = [
        record(0, T0 + 1 * SEC, "hit", dur_s=1.5, entries=1, x=0.75, y=0.35, slot=0),
        record(1, T0 + 4 * SEC, "timeout", dur_s=1.5, first_gaze_s=None, entries=0, attempts=0,
               x=0.25, y=0.3, slot=1),
    ]
    lead = 100_000_000  # the first fixation starts a little after the onset, not on its edge
    frames = noisy_fixations(T0 + 1 * SEC + lead, centres, seed=5) + noisy_fixations(
        T0 + 4 * SEC + lead, centres[::-1], seed=6
    )
    return write_session(
        tmp_path / "run", records, meta=meta, frames=frames, samples=raw_samples(14.0)
    )


def settings_with(**live):
    base = {"dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.22}
    return {"config_name": "Standard", "live": {**base, **live}, "structural": {}}


def mean_step(points) -> float:
    steps = [math.dist(a, b) for a, b in zip(points, points[1:], strict=False)]
    return sum(steps) / len(steps)


def length(path) -> float:
    return sum(math.dist(a, b) for seg in path for a, b in zip(seg, seg[1:], strict=False))


# -- SmoothParams ---------------------------------------------------------------------------


def test_the_default_weight_is_the_cursors_0_22():
    assert DEFAULT_SMOOTHING_ALPHA == 0.22
    assert SmoothParams() == SmoothParams(True, 0.22)
    assert SmoothParams.from_values(None, None) == SmoothParams(True, 0.22)  # nothing recorded


def test_the_runs_own_settings_are_read():
    assert SmoothParams.from_values(True, 0.5) == SmoothParams(True, 0.5)
    assert SmoothParams.from_values(False, 0.5) == SmoothParams(False, 0.5)
    assert SmoothParams.from_values(0, 0.3).enabled is False
    assert SmoothParams.from_values(True, "0.4").alpha == 0.4


@pytest.mark.parametrize("alpha", [0, -0.1, 1.5, "x", True, float("nan"), [0.3]])
def test_a_value_that_is_not_a_weight_falls_back_to_the_default(alpha):
    assert SmoothParams.from_values(True, alpha).alpha == DEFAULT_SMOOTHING_ALPHA


def test_the_params_are_documented_as_a_plain_dict():
    assert SmoothParams(True, 0.22).as_dict() == {"enabled": True, "alpha": 0.22}


# -- smooth_frames: the cursor's own filter ------------------------------------------------------


def test_the_filter_is_the_cursors_not_a_second_one():
    assert visual.GazeSmoother is GazeSmoother
    frames = noisy_fixations(T0, [(0.5, 0.5)])
    smoother = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.22))
    expected = [smoother.update(f.x, f.y) for f in frames]
    got = smooth_frames(frames, SmoothParams(True, 0.22))
    assert [(f.x, f.y) for f in got] == expected  # identical, number for number


def test_smoothing_leaves_times_validity_and_fixation_fields_alone():
    frames = noisy_fixations(T0, [(0.5, 0.5)])
    out = smooth_frames(frames, SmoothParams())
    assert len(out) == len(frames)
    assert [(f.t_ns, f.valid, f.fid, f.dur_s) for f in out] == [
        (f.t_ns, f.valid, f.fid, f.dur_s) for f in frames
    ]


def test_smoothing_lowers_the_point_to_point_jitter_of_a_noisy_trace():
    frames = noisy_fixations(T0, [(0.5, 0.5)], each_s=2.0)
    raw = [(f.x, f.y) for f in frames]
    smooth = [(f.x, f.y) for f in smooth_frames(frames, SmoothParams(True, 0.22))]
    assert mean_step(smooth) < 0.5 * mean_step(raw)
    # a lower alpha is steadier still
    steadier = [(f.x, f.y) for f in smooth_frames(frames, SmoothParams(True, 0.1))]
    assert mean_step(steadier) < mean_step(smooth)


def test_an_alpha_of_one_is_the_raw_stream_and_off_leaves_it_untouched():
    frames = noisy_fixations(T0, [(0.5, 0.5)])
    assert smooth_frames(frames, SmoothParams(True, 1.0)) == frames
    assert smooth_frames(frames, SmoothParams(False, 0.22)) == frames


def test_an_invalid_frame_drops_the_running_average_as_the_cursor_does():
    frames = noisy_fixations(T0, [(0.5, 0.5)])
    frames[40] = frames[40]._replace(valid=False)
    out = smooth_frames(frames, SmoothParams(True, 0.22))
    assert out[40] == frames[40]  # the invalid frame itself is passed through
    assert (out[41].x, out[41].y) == (frames[41].x, frames[41].y)  # a fresh average: the raw point
    assert (out[42].x, out[42].y) != (frames[42].x, frames[42].y)  # then smoothing again


def test_smoothing_does_not_modify_its_input():
    frames = noisy_fixations(T0, [(0.5, 0.5)])
    before = list(frames)
    smooth_frames(frames, SmoothParams())
    assert frames == before


# -- the report: scanpath (Summary map) --------------------------------------------------------------


def test_the_scanpath_is_the_fixation_centroids_in_time_order(tmp_path):
    report = build_report(noisy_folder(tmp_path))
    first, second = report["trials"]
    for trial in (first, second):
        items = trial["fixations"]["items"]
        assert len(items) == 3
        assert trial["scanpath"] == [[x, y] for x, y, _dur in items]  # exactly the centroids
    # in time order: trial 1 visits the centres as listed, trial 2 in reverse
    for point, centre in zip(first["scanpath"], CENTRES, strict=True):
        assert point == pytest.approx(centre, abs=0.01)
    for point, centre in zip(second["scanpath"], CENTRES[::-1], strict=True):
        assert point == pytest.approx(centre, abs=0.01)


def test_the_scanpath_is_not_touched_by_smoothing(tmp_path):
    on = build_report(noisy_folder(tmp_path / "a", settings=settings_with()))
    off = build_report(
        noisy_folder(tmp_path / "b", settings=settings_with(**{"dwell.smoothing.enabled": False}))
    )
    assert [t["scanpath"] for t in on["trials"]] == [t["scanpath"] for t in off["trials"]]


def test_a_trial_without_fixations_has_an_empty_scanpath(tmp_path):
    report = build_report(noisy_folder(tmp_path, centres=[]))
    assert all(t["scanpath"] == [] for t in report["trials"])
    legacy = {k: v for k, v in RIG_META.items() if k != "settings"}
    folder = write_session(tmp_path / "bare", [record(0, T0 + SEC, "hit")], meta=legacy)
    assert build_report(folder)["trials"][0]["scanpath"] == []  # no gaze_stream.csv at all


def test_a_skipped_trial_has_no_scanpath(tmp_path):
    meta = dict(RIG_META, raw_clock_offset_ns=OFFSET_NS)
    folder = write_session(
        tmp_path / "run", [record(0, T0 + SEC, "skipped", dur_s=0.5)], meta=meta,
        frames=noisy_fixations(T0 + SEC, CENTRES),
    )
    assert build_report(folder)["trials"][0]["scanpath"] == []


# -- the report: the smoothed path (Detailed view) -----------------------------------------------------


def raw_path_of(folder, trial_index=0):
    """The path the report would have drawn before V2: the raw stream, same thinning."""
    report = build_report(folder)
    trial = report["trials"][trial_index]
    window = FrameIndex(load_gaze_frames(folder)).window(trial["onset_ns"], trial["end_ns"])
    return gaze_path(window, Geometry.from_metadata(json.loads((folder / "metadata.json").read_text())))


def test_the_detailed_path_is_smoother_than_the_raw_stream(tmp_path):
    folder = noisy_folder(tmp_path, settings=settings_with())
    smoothed = build_report(folder)["trials"][0]["path"]
    raw = raw_path_of(folder)
    assert smoothed and raw
    assert length(smoothed) < 0.5 * length(raw)  # the tremor no longer scribbles
    flat_smooth = [p for seg in smoothed for p in seg]
    flat_raw = [p for seg in raw for p in seg]
    assert len(flat_smooth) < len(flat_raw)  # and fewer points survive the thinning


def test_switching_smoothing_off_gives_the_raw_path(tmp_path):
    folder = noisy_folder(
        tmp_path, settings=settings_with(**{"dwell.smoothing.enabled": False})
    )
    assert build_report(folder)["trials"][0]["path"] == raw_path_of(folder)


def test_the_weight_is_the_runs_alpha_with_0_22_when_none_was_recorded(tmp_path):
    with_alpha = noisy_folder(tmp_path / "a", settings=settings_with())  # alpha 0.22 recorded
    none = noisy_folder(
        tmp_path / "b", settings={"config_name": "Standard", "live": {}, "structural": {}}
    )
    assert build_report(with_alpha)["trials"][0]["path"] == build_report(none)["trials"][0]["path"]
    steady = noisy_folder(tmp_path / "c", settings=settings_with(**{"dwell.smoothing.alpha": 0.08}))
    snappy = noisy_folder(tmp_path / "d", settings=settings_with(**{"dwell.smoothing.alpha": 0.9}))
    assert length(build_report(steady)["trials"][0]["path"]) < length(
        build_report(snappy)["trials"][0]["path"]
    )


def test_an_alpha_of_one_gives_the_raw_path(tmp_path):
    folder = noisy_folder(tmp_path, settings=settings_with(**{"dwell.smoothing.alpha": 1.0}))
    assert build_report(folder)["trials"][0]["path"] == raw_path_of(folder)


def test_the_path_params_stay_documented_and_name_the_filter(tmp_path):
    params = build_report(noisy_folder(tmp_path / "a", settings=settings_with()))["params"]["path"]
    assert {"min_step_deg", "min_step_ms", "split_gap_ms", "max_points"} <= set(params)  # the thinning
    assert params["smoothing"] == {"enabled": True, "alpha": 0.22}
    off = build_report(
        noisy_folder(tmp_path / "b", settings=settings_with(**{"dwell.smoothing.enabled": False}))
    )
    assert off["params"]["path"]["smoothing"]["enabled"] is False
    assert set(off["params"]) == {"ivt", "entries", "pupil", "heat", "path"}  # no new params block


def test_the_fixation_numbers_and_heat_still_use_the_raw_gaze(tmp_path):
    on = build_report(noisy_folder(tmp_path / "a", settings=settings_with()))
    off = build_report(
        noisy_folder(tmp_path / "b", settings=settings_with(**{"dwell.smoothing.enabled": False}))
    )
    assert [t["fixations"] for t in on["trials"]] == [t["fixations"] for t in off["trials"]]
    assert on["heat"] == off["heat"]


def test_the_report_is_still_deterministic(tmp_path):
    folder = noisy_folder(tmp_path, settings=settings_with())
    assert build_report(folder) == build_report(folder)


# -- the cache version ---------------------------------------------------------------------------------


def test_the_version_is_two_and_a_version_one_cache_is_rebuilt(tmp_path):
    assert REPORT_VERSION == 2  # the path is smoothed, trials carry a scanpath, texts are in seconds
    folder = noisy_folder(tmp_path, settings=settings_with())
    stale = build_report(folder)
    stale["report_version"] = 1
    for trial in stale["trials"]:
        del trial["scanpath"]
    (folder / REPORT_FILENAME).write_text(json.dumps(stale), encoding="utf-8")
    fresh = load_or_build_report(folder)
    assert fresh["report_version"] == 2
    assert all("scanpath" in t for t in fresh["trials"])
    assert json.loads((folder / REPORT_FILENAME).read_text(encoding="utf-8"))["report_version"] == 2
