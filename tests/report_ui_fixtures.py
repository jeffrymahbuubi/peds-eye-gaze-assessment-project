"""Reports for the report page / Target Map / PDF tests
(SPEC-compass-task-flow.md 4D.2, 4D.7, 4D.8). Not a test module: helpers only.

``folder_report`` runs the real pipeline (a synthetic run folder through
``build_report``) so the page is tested against the true ``report.json`` shape;
``synthetic_map_report`` is a tiny hand-written report for the drawing tests, where
the exact coordinates matter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.data.report_cache import build_report
from tests.report_fixtures import (
    OFFSET_NS,
    RIG_META,
    SEC,
    T0,
    frames_between,
    raw_samples,
    record,
    write_session,
)

SLOTS = [[0.2, 0.25], [0.5, 0.25], [0.8, 0.25], [0.2, 0.6], [0.5, 0.6], [0.8, 0.6]]


def trial_records(task: str = "click_grid"):
    """Six trials: hit, timeout, hit (2 entries), skipped, hit, hit."""
    spots = [(0.2, 0.25), (0.5, 0.25), (0.8, 0.25), (0.2, 0.6), (0.5, 0.6), (0.2, 0.25)]
    plan = [
        (1, "hit", 1.0, 0.3, 1), (4, "timeout", 2.0, None, 0), (8, "hit", 1.5, 0.4, 2),
        (11, "skipped", 0.5, None, 0), (13, "hit", 1.0, 0.2, 1), (16, "hit", 1.0, 0.25, 1),
    ]
    return [
        record(
            n, T0 + at * SEC, outcome, dur_s=dur, first_gaze_s=first, entries=entries,
            attempts=0 if outcome == "timeout" else 1, x=spots[n][0], y=spots[n][1], slot=n,
            task=task,
        )
        for n, (at, outcome, dur, first, entries) in enumerate(plan)
    ]


def folder_report(
    tmp_path: Path, *, legacy: bool = False, planned: int | None = 6, events=None, **meta_extra: Any
) -> dict[str, Any]:
    """``build_report`` of a synthetic run folder (``legacy``: no new columns, no
    ``all_gaze.csv``, no geometry, as an old folder)."""
    if legacy:
        meta: dict[str, Any] = {
            "subject_id": "OLD", "session_id": "2026-09-11_OLD_click_grid_run1", "started_ns": T0,
            "tasks": ["click_grid"], "calibration_error_px": 20.0,
            "settings": {"live": {"task.inter_trial_interval_ms": 800}, "structural": {}},
        }
    else:
        meta = dict(
            RIG_META, raw_clock_offset_ns=OFFSET_NS, planned_trials=planned,
            completed_trials=6, outcome="completed" if planned in (None, 6) else "ended_early",
            test_name="Grid Click 1", layout_slots=SLOTS,
        )
    meta.update(meta_extra)
    frames, seen = [], set()
    for at in (1, 4, 8, 11, 13, 16):
        for f in frames_between(T0 + at * SEC - 500_000_000, T0 + (at + 2) * SEC, canvas_xy=(0.3, 0.3)):
            if f.t_ns not in seen:
                seen.add(f.t_ns)
                frames.append(f)
    folder = write_session(
        tmp_path / "run",
        trial_records(),
        meta=meta,
        frames=sorted(frames, key=lambda f: f.t_ns),
        samples=None if legacy else raw_samples(20.0),
        events=events,
        legacy=legacy,
    )
    return build_report(folder)


def synthetic_map_report(**overrides: Any) -> dict[str, Any]:
    """Two trials on a 1640x957 canvas: a hit at (0.65, 0.5) and a timeout at (0.3, 0.7),
    each radius 0.05 (canvas-x units), with paths, fixations and a heat map."""
    hit = {
        "trial": 1, "outcome": "hit",
        "target": {"x": 0.65, "y": 0.5, "end_x": 0.65, "end_y": 0.5, "radius_norm_x": 0.05, "slot": 0},
        "path": [[[0.15, 0.2], [0.4, 0.35]], [[0.45, 0.4], [0.64, 0.49]]],
        "fixations": {"count": 3, "mean_dur_ms": 350,
                      "items": [[0.16, 0.21, 300], [0.4, 0.35, 150], [0.64, 0.49, 600]]},
        "saccades": {"scanpath_deg": 12.3, "count": 2},
    }
    miss = {
        "trial": 2, "outcome": "timeout",
        "target": {"x": 0.3, "y": 0.7, "end_x": 0.3, "end_y": 0.7, "radius_norm_x": 0.05, "slot": 1},
        "path": [[[0.1, 0.7], [0.5, 0.8], [0.9, 0.2]]],
        "fixations": {"count": 0, "mean_dur_ms": None, "items": []},
        "saccades": {"scanpath_deg": None, "count": None},
    }
    report: dict[str, Any] = {
        "report_version": 1,
        "session": {"task_id": "click_grid", "subject": "P001", "test_name": "Grid Click 1"},
        "geometry": {"canvas_px": [1640, 957], "canvas_units": "physical", "display_scale_percent": 100,
                     "canvas_aspect": round(1640 / 957, 5)},
        "map": {
            "aspect": round(1640 / 957, 5),
            "slots": [[0.65, 0.5], [0.3, 0.7]],
            "marks": [
                {"x": 0.65, "y": 0.5, "r": 0.05, "outcome": "hit", "trials": [1], "label": "1"},
                {"x": 0.3, "y": 0.7, "r": 0.05, "outcome": "timeout", "trials": [2], "label": "2"},
            ],
            "note": None,
        },
        "trials": [hit, miss],
        "heat": {"w": 4, "h": 2, "empty": False, "data": [0.0] * 8},
    }
    report.update(overrides)
    return report
