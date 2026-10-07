"""The report's whole-test Eye Metrics table and its data-quality block
(SPEC-compass-task-flow.md 4D.2, 4D.5). Pure and Qt-free; they read the per-trial dicts
that :func:`report_metrics.build_trials` returns, so a figure the trials lack stays
``None`` here too (4D.9)."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

from .report_eye import FrameIndex, GazeFrame
from .report_geometry import Geometry
from .report_metrics import SCORED_OUTCOMES
from .report_util import mean_or_none, round_or_none, to_float, to_int

VALID_SHARE_FLOOR = 0.8  # the floor the old Results page used (retired with it, HD17)


def eye_summary(
    trials: Sequence[dict[str, Any]],
    meta: dict[str, Any],
    geometry: Geometry,
    share: float | None,
) -> dict[str, Any]:
    """The Eye Metrics table (whole test). Every figure is over the scored trials
    that have the data; a count is the total over trials, a mean over saccades is pooled
    (weighted by each trial's saccade count)."""
    fix = [t["fixations"] for t in trials if t["fixations"]["count"] is not None]
    durations = [it[2] for f in fix for it in f["items"]]
    sacc = [t["saccades"] for t in trials if t["saccades"]["count"] is not None]
    pupils = [t["pupil"] for t in trials]
    error_px = to_float(meta.get("calibration_error_px"))
    error_deg = geometry.px_to_deg(error_px) if error_px is not None else None

    def pooled(key: str) -> float | None:
        weighted = [(s["count"], s[key]) for s in sacc if s["count"] and s[key] is not None]
        total = sum(n for n, _ in weighted)
        return round(sum(n * v for n, v in weighted) / total, 2) if total else None

    return {
        "fixations": {
            "count": sum(f["count"] for f in fix) if fix else None,
            "mean_per_trial": mean_or_none([f["count"] for f in fix], 2),
        },
        "fixation_duration_ms": {
            "mean": mean_or_none(durations, 1),
            "median": round(statistics.median(durations), 1) if durations else None,
        },
        "saccades": {
            "count": sum(s["count"] for s in sacc) if sacc else None,
            "mean_amplitude_deg": pooled("mean_amp_deg"),
            "mean_peak_velocity_deg_s": pooled("mean_peak"),
            "max_peak_velocity_deg_s": max(
                (s["max_peak"] for s in sacc if s["max_peak"] is not None), default=None
            ),
        },
        "scanpath_deg_per_trial": mean_or_none([s["scanpath_deg"] for s in sacc], 2),
        "pupil": {
            "mean_mm": mean_or_none([p["mean_mm"] for p in pupils], 3),
            "mean_change_mm": mean_or_none([p["change_mm"] for p in pupils], 3),
            "mean_change_pct": mean_or_none([p["change_pct"] for p in pupils], 2),
            "trials_with_baseline": sum(1 for p in pupils if p["change_mm"] is not None),
        },
        "valid_gaze_pct": None if share is None else round(100.0 * share, 1),
        "calibration": {
            "error_px": error_px,
            "error_deg": round_or_none(error_deg, 2),
            "points": to_int(meta.get("calibration_points")),
            "source": meta.get("calibration_source"),
        },
    }


def gaze_valid_share(index: FrameIndex, trials: Sequence[dict[str, Any]]) -> float | None:
    """Share of the gaze frames inside the scored trial windows that were valid;
    ``None`` when there are none (no ``gaze_stream.csv``)."""
    total = valid = 0
    for t in trials:
        if t["outcome"] not in SCORED_OUTCOMES:
            continue
        if t["onset_ns"] is None or t["end_ns"] is None:
            continue
        window = index.window(t["onset_ns"], t["end_ns"])
        total += len(window)
        valid += sum(1 for f in window if f.valid)
    return valid / total if total else None


def frames_by_window(
    index: FrameIndex, trials: Sequence[dict[str, Any]]
) -> list[tuple[list[GazeFrame], int]]:
    """``(frames, end_ns)`` of every scored trial, the heat map's input."""
    out = []
    for t in trials:
        if t["outcome"] in SCORED_OUTCOMES and t["onset_ns"] and t["end_ns"]:
            out.append((index.window(t["onset_ns"], t["end_ns"]), t["end_ns"]))
    return out


def quality_block(
    *,
    n_rows: int,
    planned: int | None,
    outcome: str | None,
    share: float | None,
    off_canvas_share: float | None,
    canvas_resized: bool,
) -> dict[str, Any]:
    """``{valid_share, off_canvas_share, warnings}``; each warning is
    ``{code, text}`` for the report's banner."""
    warnings: list[dict[str, str]] = []
    if outcome == "ended_early" or (planned is not None and planned > n_rows):
        total = f" of {planned}" if planned is not None else ""
        warnings.append(
            {"code": "ended_early", "text": f"Ended early — {n_rows}{total} trials"}
        )
    if share is not None and share < VALID_SHARE_FLOOR:
        warnings.append(
            {
                "code": "low_valid_gaze",
                "text": f"Valid gaze {share * 100:.0f}% is below the "
                f"{VALID_SHARE_FLOOR * 100:.0f}% floor",
            }
        )
    if canvas_resized:
        warnings.append(
            {
                "code": "canvas_resized",
                "text": "The window was resized during the test; gaze overlay is approximate",
            }
        )
    return {
        "valid_share": round_or_none(share, 4),
        "off_canvas_share": off_canvas_share,
        "warnings": warnings,
    }
