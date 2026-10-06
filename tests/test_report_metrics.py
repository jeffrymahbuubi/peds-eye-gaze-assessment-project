"""SPEC-compass-task-flow.md 4D.2 / 4D.5 / 4D.9 / 4D.10 G2: the trial table, the Summary
of Results rows, the whole-test eye metrics and the quality block."""

from __future__ import annotations

import math

import pytest

from src.data.report_eye import FrameIndex, GazeFrame
from src.data.report_geometry import Geometry
from src.data.report_metrics import (
    analyse_raw,
    build_trials,
    format_pct_n,
    summary_rows,
    trial_outcome,
)
from src.data.report_quality import eye_summary, gaze_valid_share, quality_block
from tests.report_fixtures import (
    OFFSET_NS,
    RIG_META,
    SEC,
    T0,
    deg_to_dx,
    frames_between,
    raw_samples,
    record,
    row_strings,
)

GEO = Geometry.from_metadata(RIG_META)


def table(records, *, legacy=False, frames=(), raw=None, track=None, task_id="click_grid"):
    rows = [row_strings(r, legacy=legacy) for r in records]
    return build_trials(
        rows, GEO, FrameIndex(frames), raw, track, iti_ms=800.0, task_id=task_id
    )


def g2_records():
    """The G2 fixture: 8 trials, 7 scored, 1 skipped."""
    at = lambda i: T0 + (10 * i + 1) * SEC  # noqa: E731
    return [
        record(0, at(0), "hit", dur_s=1.0, first_gaze_s=0.2, entries=1, attempts=1),
        record(1, at(1), "hit", dur_s=2.0, first_gaze_s=0.4, entries=1, attempts=1),
        record(2, at(2), "hit", dur_s=3.0, first_gaze_s=0.6, entries=1, attempts=1),
        record(3, at(3), "hit", dur_s=4.0, first_gaze_s=0.5, entries=2, attempts=1),
        record(4, at(4), "hit", dur_s=5.0, first_gaze_s=0.3, entries=1, attempts=2),
        record(5, at(5), "timeout", dur_s=8.0, first_gaze_s=0.7, entries=1, attempts=0),
        record(6, at(6), "timeout", dur_s=8.0, first_gaze_s=None, entries=0, attempts=0),
        record(7, at(7), "skipped", dur_s=1.5, first_gaze_s=None, entries=0, attempts=0),
    ]


# -- G2: Summary rows -----------------------------------------------------------------------


def rows_by_key(trials):
    return {r["key"]: r for r in summary_rows(trials)}


def test_g2_counts_and_percentages_match_the_hand_computation():
    rows = rows_by_key(table(g2_records()))
    assert [(k, r["n"], r["N"]) for k, r in rows.items()] == [
        ("error_free", 3, 7), ("all_selected", 5, 7), ("not_selected", 2, 7), ("all_trials", 7, 7),
    ]
    assert rows["error_free"]["pct_n"] == "42.9% (3/7)"
    assert rows["all_selected"]["pct_n"] == "71.4% (5/7)"
    assert rows["not_selected"]["pct_n"] == "28.6% (2/7)"
    assert rows["all_trials"]["pct_n"] == "100% (7/7)"
    assert rows["error_free"]["pct"] == pytest.approx(42.9)
    assert [r["label"] for r in rows.values()] == [
        "Error-free Target Selections", "All Targets Selected", "Targets Not Selected", "All Trials",
    ]


def test_g2_means_of_trial_time_reaction_time_and_entries():
    rows = rows_by_key(table(g2_records()))
    ef, sel, no, allr = (rows[k] for k in ("error_free", "all_selected", "not_selected", "all_trials"))
    assert (ef["trial_time_s"], ef["reaction_time_s"], ef["entries"]) == (2.0, 0.4, 1.0)
    assert (sel["trial_time_s"], sel["reaction_time_s"], sel["entries"]) == (3.0, 0.4, 1.2)
    # A timeout's trial time is the time to its end; reaction time only where gaze ever entered.
    assert (no["trial_time_s"], no["reaction_time_s"], no["entries"]) == (8.0, 0.7, 0.5)
    assert allr["trial_time_s"] == pytest.approx(31 / 7, abs=1e-3)
    assert allr["reaction_time_s"] == pytest.approx(0.45)
    assert allr["entries"] == 1.0


def test_g2_error_free_never_exceeds_all_selected_never_exceeds_all_trials():
    rows = rows_by_key(table(g2_records()))
    assert rows["error_free"]["n"] <= rows["all_selected"]["n"] <= rows["all_trials"]["n"]
    assert rows["all_selected"]["n"] + rows["not_selected"]["n"] == rows["all_trials"]["n"]


def test_g2_the_skipped_trial_is_excluded_from_every_row():
    trials = table(g2_records())
    assert trials[7]["outcome"] == "skipped"
    assert all(r["N"] == 7 for r in summary_rows(trials))


def test_g2_an_empty_row_prints_zero_percent_of_n():
    only_hits = g2_records()[:5]
    rows = rows_by_key(table(only_hits))
    row = rows["not_selected"]
    assert row["pct_n"] == "0% (0/5)" and row["n"] == 0 and row["pct"] == 0.0
    assert (row["trial_time_s"], row["reaction_time_s"], row["entries"]) == (None, None, None)


def test_with_no_scored_trial_every_row_is_zero_of_zero():
    rows = summary_rows(table([g2_records()[7]]))  # only the skip
    assert [r["pct_n"] for r in rows] == ["0% (0/0)"] * 4
    assert summary_rows([]) == summary_rows(table([]))


def test_format_pct_n():
    assert format_pct_n(3, 7) == "42.9% (3/7)"
    assert format_pct_n(0, 0) == "0% (0/0)"
    assert format_pct_n(8, 8) == "100% (8/8)"
    assert format_pct_n(None, 8) == "—"


# -- 4D.9: an old folder without the new columns ---------------------------------------------


def test_a_legacy_trials_table_has_no_entries_and_no_error_free_row():
    trials = table(g2_records(), legacy=True)
    assert all(t["entries"] is None and t["error_free"] is None for t in trials)
    rows = rows_by_key(trials)
    assert rows["error_free"]["n"] is None and rows["error_free"]["pct_n"] == "—"
    assert rows["all_selected"]["n"] == 5 and rows["all_selected"]["entries"] is None
    # Outcome is derived from is_hit / is_timeout when the skipped column is absent; a
    # skip written by newer code but read without its column is "unknown", never scored.
    assert [t["outcome"] for t in trials] == ["hit"] * 5 + ["timeout"] * 2 + ["unknown"]
    assert rows["all_trials"]["N"] == 7


def test_trial_outcome_is_derived_from_the_three_flags():
    assert trial_outcome({"is_hit": "1", "is_timeout": "0", "is_skipped": "0"}) == "hit"
    assert trial_outcome({"is_hit": "0", "is_timeout": "1"}) == "timeout"
    assert trial_outcome({"is_hit": "0", "is_timeout": "0", "is_skipped": "1"}) == "skipped"
    assert trial_outcome({"is_hit": "0", "is_timeout": "0", "is_skipped": "0"}) == "unknown"
    assert trial_outcome({}) == "unknown"


def test_an_unknown_outcome_is_listed_but_never_scored():
    row = row_strings(record(0, T0, "hit"))
    row.update(is_hit="0", is_timeout="0", is_skipped="0")
    trials = build_trials([row], GEO, FrameIndex([]), None, None, iti_ms=None, task_id="click_grid")
    assert trials[0]["outcome"] == "unknown" and trials[0]["trial_time_s"] is None
    assert summary_rows(trials)[3]["N"] == 0


# -- the trial table --------------------------------------------------------------------------


def test_trial_numbers_are_one_based_and_a_skipped_row_has_no_metrics():
    trials = table(g2_records())
    assert [t["trial"] for t in trials] == list(range(1, 9))
    skipped = trials[7]
    assert (skipped["trial_time_s"], skipped["reaction_time_s"], skipped["entries"]) == (
        None, None, None
    )
    assert skipped["error_free"] is None


def test_size_is_the_target_diameter_in_degrees_and_distance_the_angle_between_starts():
    a = record(0, T0, x=0.2, y=0.3)
    b = record(1, T0 + 5 * SEC, x=0.8, y=0.6, radius_px=103.4)
    t0, t1 = table([a, b])
    # 100 px * 0.2745 mm/px = 27.45 mm radius at 650 mm: 2 * atan(27.45 / 650) = 4.84 deg.
    assert t0["size_deg"] == pytest.approx(math.degrees(2 * math.atan(27.45 / 650)), abs=0.01)
    assert t1["size_deg"] == pytest.approx(5.0, abs=0.01)  # the 5 deg preset's own radius
    assert t0["distance_deg"] is None  # nothing before trial 1
    assert t1["distance_deg"] == pytest.approx(GEO.canvas_angle_deg((0.2, 0.3), (0.8, 0.6)), abs=0.01)


def test_follow_moving_has_no_distance_and_carries_its_track():
    recs = [record(0, T0, x=0.2, y=0.3, task="follow_moving"),
            record(1, T0 + 5 * SEC, x=0.8, y=0.6, task="follow_moving")]
    track = [(T0 + 100_000_000, 0, 0.2, 0.3), (T0 + 600_000_000, 0, 0.3, 0.4),
             (T0 + 5 * SEC + 50_000_000, 1, 0.8, 0.6)]
    trials = table(recs, task_id="follow_moving", track=track)
    assert [t["distance_deg"] for t in trials] == [None, None]
    assert trials[0]["track"] == [[0.2, 0.3], [0.3, 0.4]] and trials[1]["track"] == [[0.8, 0.6]]
    assert "track" not in table(recs, task_id="follow_moving")[0]  # no target_track.csv


def test_the_target_block_holds_position_end_radius_and_slot():
    rec = record(0, T0, x=0.25, y=0.5, radius_px=100.0, slot=4, end_xy=(0.3, 0.55))
    (t,) = table([rec])
    assert t["target"] == {
        "x": 0.25, "y": 0.5, "end_x": 0.3, "end_y": 0.55,
        "radius_norm_x": round(100.0 / 1640, 5), "slot": 4,
    }
    (legacy,) = table([record(0, T0, slot=-1)])
    assert legacy["target"]["slot"] is None


def test_the_radius_is_in_logical_px_so_a_scaled_display_divides_the_canvas_by_the_scale():
    meta = dict(RIG_META, display_scale_percent=150)
    geo = Geometry.from_metadata(meta)
    rows = [row_strings(record(0, T0, radius_px=100.0))]
    (t,) = build_trials(rows, geo, FrameIndex([]), None, None, iti_ms=None, task_id="click_grid")
    assert t["target"]["radius_norm_x"] == pytest.approx(100.0 / (1640 / 1.5), abs=1e-5)


def test_without_gaze_or_raw_files_the_eye_columns_are_none_not_zero():
    (t,) = table([record(0, T0)])
    assert t["fixations"] == {"count": None, "mean_dur_ms": None, "items": []}
    assert t["saccades"]["count"] is None and t["pupil"]["mean_mm"] is None and t["path"] == []


def test_a_trial_re_presented_after_a_pause_is_two_rows_with_their_own_windows():
    # trial id 3 appears twice (the interrupted attempt is not recorded, but the
    # re-presented one repeats the id); each row windows its own gaze.
    first = record(2, T0 + 10 * SEC, dur_s=1.0)
    again = record(2, T0 + 30 * SEC, dur_s=1.0)
    frames = frames_between(T0 + 10 * SEC, T0 + 11 * SEC) + frames_between(
        T0 + 30 * SEC, T0 + 31 * SEC, canvas_xy=(0.2, 0.2)
    )
    a, b = table([first, again], frames=frames)
    assert a["trial"] == b["trial"] == 3
    assert a["fixations"]["items"][0][:2] != b["fixations"]["items"][0][:2]


# -- fixations, saccades, pupil through the trial windows ----------------------------------------


def saccade_raw():
    """150 Hz, TIME 0-10 s: still until TIME 4.0, a 5 deg move over 40 ms, still again.
    TIME 4.0 is host T0 + 1 s (OFFSET_NS = T0 - 3 s)."""
    x0 = 0.3

    def x_fn(t):
        if t < 4.0:
            return x0
        if t <= 4.04:
            return x0 + deg_to_dx(5.0) * (t - 4.0) / 0.04
        return x0 + deg_to_dx(5.0)

    return raw_samples(10.0, x_fn=x_fn)


def two_trials():
    # Trial A holds host T0 + 0.5 .. 1.5 s (the saccade at T0 + 1 s); B holds T0 + 2 .. 3 s.
    return [record(0, T0 + 500_000_000, dur_s=1.0), record(1, T0 + 2 * SEC, dur_s=1.0)]


def test_the_raw_clock_offset_puts_a_saccade_in_the_right_trial():
    meta = dict(RIG_META, raw_clock_offset_ns=OFFSET_NS)
    raw = analyse_raw(saccade_raw(), meta, GEO)
    a, b = table(two_trials(), raw=raw)
    assert (a["saccades"]["count"], b["saccades"]["count"]) == (1, 0)
    assert a["saccades"]["mean_amp_deg"] == pytest.approx(5.0, abs=0.3)
    assert a["saccades"]["scanpath_deg"] == a["saccades"]["mean_amp_deg"]
    assert b["saccades"]["mean_peak"] is None and b["saccades"]["scanpath_deg"] == 0.0
    # Shift the clock by 1.5 s and the same saccade belongs to trial B.
    later = analyse_raw(saccade_raw(), dict(meta, raw_clock_offset_ns=OFFSET_NS + 1_500_000_000), GEO)
    a2, b2 = table(two_trials(), raw=later)
    assert (a2["saccades"]["count"], b2["saccades"]["count"]) == (0, 1)


def test_no_offset_or_no_samples_means_no_raw_analysis():
    assert analyse_raw(saccade_raw(), RIG_META, GEO) is None  # old folder: no offset
    assert analyse_raw(None, dict(RIG_META, raw_clock_offset_ns=0), GEO) is None
    assert analyse_raw([], dict(RIG_META, raw_clock_offset_ns=0), GEO) is None


def test_without_physical_geometry_saccades_are_none_but_pupil_still_works():
    meta = {"raw_clock_offset_ns": OFFSET_NS, "screen_width_px": 1920, "screen_height_px": 1080}
    raw = analyse_raw(saccade_raw(), meta, Geometry.from_metadata(meta))
    assert raw.saccades is None and raw.pupil_times
    rows = [row_strings(r) for r in two_trials()]
    a, _ = build_trials(rows, Geometry.from_metadata(meta), FrameIndex([]), raw, None,
                        iti_ms=800.0, task_id="click_grid")
    assert a["saccades"]["count"] is None and a["pupil"]["mean_mm"] == pytest.approx(3.5)


def test_pupil_baseline_comes_from_the_blank_before_the_trial():
    meta = dict(RIG_META, raw_clock_offset_ns=OFFSET_NS)
    # Host T0 = TIME 3.0: trial B (TIME 5.0-6.0) follows an ITI of 0.5 s of 3.5 mm.
    raw = analyse_raw(raw_samples(10.0, lambda t: 4.0 if 5.0 <= t <= 6.0 else 3.5), meta, GEO)
    _, b = table(two_trials(), raw=raw)
    assert b["pupil"]["mean_mm"] == pytest.approx(4.0)
    assert b["pupil"]["baseline_mm"] == pytest.approx(3.5)
    assert b["pupil"]["change_mm"] == pytest.approx(0.5)
    assert b["pupil"]["change_pct"] == pytest.approx(0.5 / 3.5 * 100, abs=0.01)


def test_fixations_and_a_path_are_windowed_per_trial():
    frames = frames_between(T0, T0 + 4 * SEC, canvas_xy=(0.4, 0.4))
    a, b = table(two_trials(), frames=frames)
    for t in (a, b):
        assert t["fixations"]["count"] >= 2 and t["fixations"]["mean_dur_ms"] > 0
        assert t["path"] and sum(len(seg) for seg in t["path"]) >= 2


# -- whole-test eye metrics ----------------------------------------------------------------------


def trial_stub(fix_items, sacc, pupil):
    """``fix_items`` None = the trial had no gaze data at all (count None, not 0)."""
    return {
        "outcome": "hit", "onset_ns": 1, "end_ns": 2,
        "fixations": {
            "count": None if fix_items is None else len(fix_items),
            "mean_dur_ms": None, "items": fix_items or [],
        },
        "saccades": sacc, "pupil": pupil,
    }


def sacc(count, mean_peak, max_peak, mean_amp, scan):
    return {"count": count, "mean_peak": mean_peak, "max_peak": max_peak,
            "mean_amp_deg": mean_amp, "scanpath_deg": scan}


NO_PUPIL = {"mean_mm": None, "baseline_mm": None, "change_mm": None, "change_pct": None}


def test_eye_summary_pools_saccades_and_averages_trials():
    trials = [
        trial_stub([[0, 0, 200.0], [0, 0, 300.0]], sacc(2, 100.0, 150.0, 4.0, 8.0),
                   {"mean_mm": 3.5, "baseline_mm": 3.4, "change_mm": 0.1, "change_pct": 2.94}),
        trial_stub([[0, 0, 100.0]], sacc(1, 200.0, 200.0, 6.0, 6.0),
                   {"mean_mm": 3.7, "baseline_mm": None, "change_mm": None, "change_pct": None}),
        trial_stub(None, sacc(None, None, None, None, None), NO_PUPIL),  # no data: ignored
    ]
    eye = eye_summary(trials, RIG_META, GEO, 0.93)
    assert eye["fixations"] == {"count": 3, "mean_per_trial": 1.5}
    assert eye["fixation_duration_ms"] == {"mean": 200.0, "median": 200.0}
    assert eye["saccades"]["count"] == 3
    assert eye["saccades"]["mean_peak_velocity_deg_s"] == pytest.approx(133.33, abs=0.01)
    assert eye["saccades"]["mean_amplitude_deg"] == pytest.approx(4.67, abs=0.01)
    assert eye["saccades"]["max_peak_velocity_deg_s"] == 200.0
    assert eye["scanpath_deg_per_trial"] == 7.0
    assert eye["pupil"]["mean_mm"] == pytest.approx(3.6)
    assert (eye["pupil"]["mean_change_mm"], eye["pupil"]["trials_with_baseline"]) == (0.1, 1)
    assert eye["valid_gaze_pct"] == 93.0
    assert eye["calibration"] == {
        "error_px": 21.31, "error_deg": 0.52, "points": 5, "source": "measured"
    }


def test_eye_summary_of_nothing_is_all_none():
    eye = eye_summary([], {}, Geometry(), None)
    assert eye["fixations"] == {"count": None, "mean_per_trial": None}
    assert eye["saccades"]["count"] is None and eye["pupil"]["mean_mm"] is None
    assert eye["valid_gaze_pct"] is None and eye["calibration"]["error_deg"] is None


# -- quality ---------------------------------------------------------------------------------------


def test_valid_share_counts_scored_trial_windows_only():
    good = frames_between(T0, T0 + SEC)  # 61 valid
    bad = frames_between(T0 + SEC + 1, T0 + 2 * SEC, valid=False)  # all invalid, in the skip
    outside = frames_between(T0 + 5 * SEC, T0 + 6 * SEC, valid=False)
    recs = [record(0, T0, dur_s=1.0), record(1, T0 + SEC + 1, "skipped", dur_s=0.9)]
    trials = table(recs, frames=good + bad + outside)
    assert gaze_valid_share(FrameIndex(good + bad + outside), trials) == 1.0
    assert gaze_valid_share(FrameIndex([]), trials) is None


def test_valid_share_with_some_invalid_frames():
    frames = [GazeFrame(T0 + i, 0.5, 0.5, i % 4 != 0, None, None) for i in range(100)]
    trials = table([record(0, T0, dur_s=0.0)], frames=frames)
    trials[0]["end_ns"] = T0 + 99
    assert gaze_valid_share(FrameIndex(frames), trials) == pytest.approx(0.75)


def test_quality_warnings():
    q = quality_block(n_rows=3, planned=6, outcome="ended_early", share=0.7,
                      off_canvas_share=0.01, canvas_resized=True)
    assert [w["code"] for w in q["warnings"]] == ["ended_early", "low_valid_gaze", "canvas_resized"]
    assert q["warnings"][0]["text"] == "Ended early — 3 of 6 trials"
    assert "70%" in q["warnings"][1]["text"] and "80%" in q["warnings"][1]["text"]
    assert q["valid_share"] == 0.7 and q["off_canvas_share"] == 0.01


def test_a_complete_clean_run_has_no_warning():
    q = quality_block(n_rows=6, planned=6, outcome="completed", share=0.95,
                      off_canvas_share=None, canvas_resized=False)
    assert q["warnings"] == []


def test_a_partial_run_is_flagged_even_when_the_outcome_field_is_missing():
    q = quality_block(n_rows=3, planned=6, outcome=None, share=None,
                      off_canvas_share=None, canvas_resized=False)
    assert q["warnings"][0]["code"] == "ended_early"
    # No planned count (an old folder): no banner, unless the outcome says so.
    assert quality_block(n_rows=3, planned=None, outcome=None, share=None,
                         off_canvas_share=None, canvas_resized=False)["warnings"] == []
    assert quality_block(n_rows=3, planned=None, outcome="ended_early", share=None,
                         off_canvas_share=None, canvas_resized=False)["warnings"][0]["text"] == (
        "Ended early — 3 trials")
