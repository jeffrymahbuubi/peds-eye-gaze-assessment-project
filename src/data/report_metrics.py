"""The per-test report's trial table and Summary of Results rows
(SPEC-compass-task-flow.md 4D.2, 4D.5, 4D.9). Pure and Qt-free; the files are read by
:mod:`report_cache`, and the whole-test eye metrics and quality block built from these
rows are in :mod:`report_quality`.

Where a number cannot be computed from what the folder holds, it is ``None`` ("—" in
the UI), never 0 and never a guess (4D.9): no ``entries`` column means no Entries and
no Error-free row; no ``all_gaze.csv`` or ``raw_clock_offset_ns`` means no saccade or
pupil figures; no physical geometry means no degrees.

A trial's outcome is *derived* from ``is_skipped`` / ``is_hit`` / ``is_timeout`` (R6;
there is no outcome column). Skipped trials are the operator's act, not the child's
failure: they show no metrics and stay out of every percentage (HD5).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .report_eye import (
    DEFAULT_PUPIL,
    FrameIndex,
    PupilParams,
    RawSample,
    pupil_series,
    sample_period_s,
    trial_fixations,
    trial_pupil,
)
from .report_geometry import Geometry
from .report_util import mean_or_none, round_or_none, to_float, to_int
from .report_visual import (
    DEFAULT_PATH,
    PathParams,
    gaze_path,
    trial_track,
)
from .saccades import DEFAULT_IVT, IvtParams, Saccade, detect_saccades, window_saccades

OUTCOME_HIT, OUTCOME_TIMEOUT, OUTCOME_SKIPPED, OUTCOME_UNKNOWN = (
    "hit", "timeout", "skipped", "unknown"
)

SUMMARY_ROWS = (
    ("error_free", "Error-free Target Selections"),
    ("all_selected", "All Targets Selected"),
    ("not_selected", "Targets Not Selected"),
    ("all_trials", "All Trials"),
)


def trial_outcome(row: dict[str, str]) -> str:
    """``skipped`` / ``hit`` / ``timeout`` from the three flags (R6); ``unknown``
    when none is set (never a made-up one)."""
    if row.get("is_skipped") == "1":
        return OUTCOME_SKIPPED
    if row.get("is_hit") == "1":
        return OUTCOME_HIT
    if row.get("is_timeout") == "1":
        return OUTCOME_TIMEOUT
    return OUTCOME_UNKNOWN


def format_pct_n(n: int | None, total: int) -> str:
    """``42.9% (3/7)``; ``0% (0/7)`` for an empty row; ``—`` when ``n`` is unknown."""
    if n is None:
        return "—"
    pct = round(100.0 * n / total, 1) if total else 0.0
    return f"{pct:g}% ({n}/{total})"


# -- the device-rate (all_gaze.csv) analysis ----------------------------------------


@dataclass
class RawAnalysis:
    """Saccades and the pupil series of one run, on the host clock."""

    offset_ns: int
    sample_dt_s: float | None
    saccades: list[Saccade] | None  # None: the geometry cannot give degrees
    pupil_times: list[int]
    pupil_values: list[float]


def analyse_raw(
    samples: Sequence[RawSample] | None,
    meta: dict[str, Any],
    geometry: Geometry,
    ivt: IvtParams = DEFAULT_IVT,
    pupil: PupilParams = DEFAULT_PUPIL,
) -> RawAnalysis | None:
    """I-VT and the pupil series, or ``None`` without ``all_gaze.csv`` samples or the
    ``raw_clock_offset_ns`` that aligns them with the trials (4D.4-5, 4D.9)."""
    offset = to_int(meta.get("raw_clock_offset_ns"))
    if not samples or offset is None:
        return None
    saccades = None
    if geometry.has_angles:
        saccades = detect_saccades([(s.t_s, s.x, s.y, s.valid) for s in samples], geometry, ivt)
    times, values = pupil_series(samples, offset, pupil)
    return RawAnalysis(offset, sample_period_s(samples), saccades, times, values)


# -- the trial table -----------------------------------------------------------------


def _empty_fixations() -> dict[str, Any]:
    return {"count": None, "mean_dur_ms": None, "items": []}


def _empty_saccades() -> dict[str, Any]:
    return {
        "count": None, "mean_peak": None, "max_peak": None, "mean_amp_deg": None,
        "scanpath_deg": None,
    }


def _saccade_block(found: Sequence[Saccade]) -> dict[str, Any]:
    if not found:
        return {**_empty_saccades(), "count": 0, "scanpath_deg": 0.0}
    amps = [s.amplitude_deg for s in found]
    peaks = [s.peak_velocity_deg_s for s in found]
    return {
        "count": len(found),
        "mean_peak": round(sum(peaks) / len(peaks), 1),
        "max_peak": round(max(peaks), 1),
        "mean_amp_deg": round(sum(amps) / len(amps), 2),
        "scanpath_deg": round(sum(amps), 2),
    }


def build_trials(
    trial_rows: Sequence[dict[str, str]],
    geometry: Geometry,
    index: FrameIndex,
    raw: RawAnalysis | None,
    track: Sequence[tuple[int, int, float, float]] | None,
    *,
    iti_ms: float | None,
    task_id: str | None,
    path_params: PathParams = DEFAULT_PATH,
    pupil_params: PupilParams = DEFAULT_PUPIL,
    path_index: FrameIndex | None = None,
) -> list[dict[str, Any]]:
    """One dict per ``trials.csv`` row, in order (see 4D.6 for the shape).

    The trial window is ``[t_target_shown_ns, t_end_ns]``. A trial re-presented after
    a pause repeats its trial id but has its own row and window, so nothing here is
    keyed by the id alone.

    ``path`` (the Detailed view's full gaze path) is drawn from ``path_index``, the same
    stream passed through the on-screen cursor's filter (:func:`~.report_visual.smooth_frames`);
    without one it is the raw stream. ``scanpath`` (the Summary map's) is the trial's
    fixation centroids in time order, whatever the smoothing.
    """
    moving = task_id == "follow_moving"
    logical = geometry.canvas_logical_size()
    out: list[dict[str, Any]] = []
    prev_start: tuple[float, float] | None = None
    for row in trial_rows:
        trial_id = to_int(row.get("trial_id")) or 0
        outcome = trial_outcome(row)
        onset = to_int(row.get("t_target_shown_ns"))
        end = to_int(row.get("t_end_ns"))
        x, y = to_float(row.get("target_x")), to_float(row.get("target_y"))
        radius_px = to_float(row.get("target_radius_px"))
        end_x, end_y = to_float(row.get("end_x")), to_float(row.get("end_y"))
        slot = to_int(row.get("slot_index"))

        distance = None
        if prev_start is not None and x is not None and y is not None and not moving:
            distance = round_or_none(geometry.canvas_angle_deg(prev_start, (x, y)), 2)
        if x is not None and y is not None:
            prev_start = (x, y)

        entries = to_int(row.get("entries")) if outcome != OUTCOME_SKIPPED else None
        attempts = to_int(row.get("attempts"))
        t_click = to_int(row.get("t_click_ns"))
        t_first = to_int(row.get("t_first_gaze_on_target_ns"))
        scored = outcome in (OUTCOME_HIT, OUTCOME_TIMEOUT) and onset is not None
        trial_time = reaction = None
        if scored:
            done = t_click if outcome == OUTCOME_HIT and t_click is not None else end
            trial_time = None if done is None else round_or_none((done - onset) / 1e9, 3)
            reaction = None if t_first is None else round_or_none((t_first - onset) / 1e9, 3)
        error_free = None
        if outcome == OUTCOME_HIT and entries is not None and attempts is not None:
            error_free = entries == 1 and attempts == 1

        item: dict[str, Any] = {
            "trial": trial_id + 1,
            "outcome": outcome,
            "size_deg": round_or_none(
                geometry.radius_to_diameter_deg(radius_px) if radius_px else None, 2
            ),
            "distance_deg": distance,
            "target": {
                "x": x, "y": y, "end_x": end_x, "end_y": end_y,
                "radius_norm_x": (
                    round(radius_px / logical[0], 5) if radius_px and logical else None
                ),
                "slot": slot if slot is not None and slot >= 0 else None,
            },
            "onset_ns": onset,
            "end_ns": end,
            "attempts": attempts,
            "error_free": error_free,
            "trial_time_s": trial_time,
            "reaction_time_s": reaction,
            "entries": entries,
            "fixations": _empty_fixations(),
            "scanpath": [],
            "saccades": _empty_saccades(),
            "pupil": {k: None for k in ("mean_mm", "baseline_mm", "change_mm", "change_pct")},
            "path": [],
        }
        if track is not None and moving and onset is not None and end is not None:
            item["track"] = trial_track(track, trial_id, onset, end)
        if scored and end is not None:
            window = index.window(onset, end)
            if window:
                fixes = trial_fixations(window, onset, end, geometry)
                item["fixations"] = {
                    "count": len(fixes),
                    "mean_dur_ms": mean_or_none([f.dur_ms for f in fixes], 1),
                    "items": [[round(f.x, 4), round(f.y, 4), round(f.dur_ms, 1)] for f in fixes],
                }
                item["scanpath"] = [[round(f.x, 4), round(f.y, 4)] for f in fixes]
                item["path"] = gaze_path(
                    (path_index or index).window(onset, end), geometry, path_params
                )
            if raw is not None:
                if raw.saccades is not None:
                    item["saccades"] = _saccade_block(
                        window_saccades(raw.saccades, raw.offset_ns, onset, end)
                    )
                p = trial_pupil(
                    raw.pupil_times, raw.pupil_values, onset, end,
                    sample_dt_s=raw.sample_dt_s, iti_ms=iti_ms, params=pupil_params,
                )
                item["pupil"] = {
                    "mean_mm": round_or_none(p["mean_mm"], 3),
                    "baseline_mm": round_or_none(p["baseline_mm"], 3),
                    "change_mm": round_or_none(p["change_mm"], 3),
                    "change_pct": round_or_none(p["change_pct"], 2),
                }
        out.append(item)
    return out


# -- Summary of Results --------------------------------------------------------------


def summary_rows(trials: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The four Summary of Results rows (U10).

    ``N`` is the scored trials (hit + timeout; skipped are excluded). Each row has its
    membership count and ``pct_n`` text, and the means of Trial Time (onset to selection,
    or to the end for a timeout), Reaction Time (onset to the first gaze entry, over the
    trials where gaze ever entered) and Entries. Error-free = a hit with ``entries == 1``
    and ``attempts == 1``; when the folder has no ``entries`` the row is ``None`` / "—"
    (not guessed).
    """
    scored = [t for t in trials if t["outcome"] in (OUTCOME_HIT, OUTCOME_TIMEOUT)]
    hits = [t for t in scored if t["outcome"] == OUTCOME_HIT]
    timeouts = [t for t in scored if t["outcome"] == OUTCOME_TIMEOUT]
    known = all(t["error_free"] is not None for t in hits)
    members: dict[str, list[dict[str, Any]] | None] = {
        "error_free": [t for t in hits if t["error_free"]] if known else None,
        "all_selected": hits,
        "not_selected": timeouts,
        "all_trials": scored,
    }
    rows = []
    for key, label in SUMMARY_ROWS:
        group = members[key]
        n = None if group is None else len(group)
        rows.append(
            {
                "key": key,
                "label": label,
                "n": n,
                "N": len(scored),
                "pct": None if n is None else (round(100.0 * n / len(scored), 1) if scored else 0.0),
                "pct_n": format_pct_n(n, len(scored)),
                "trial_time_s": None if not group else mean_or_none([t["trial_time_s"] for t in group], 3),
                "reaction_time_s": (
                    None if not group else mean_or_none([t["reaction_time_s"] for t in group], 3)
                ),
                "entries": None if not group else mean_or_none([t["entries"] for t in group], 2),
            }
        )
    return rows
