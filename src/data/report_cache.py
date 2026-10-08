"""Build and cache the per-test report (SPEC-compass-task-flow.md 4D.6, HD1).

``build_report(session_dir)`` reads one finished run's raw files and returns the
report as a plain dict; ``report.json`` next to them is only a cache of it. It is
written at the end of a recorded run (so "Save and View Report" opens instantly) and
rebuilt on open when missing, unreadable or from another ``REPORT_VERSION``. The raw
files stay the source of truth; the version pins the algorithms so the clinical
numbers are reproducible. Same folder in, byte-identical JSON out.

A pure folder reader: it never needs the app, so any old folder can be opened for QA
(degrading as 4D.9 says: a figure its files cannot give is ``None``, not 0).

Dev CLI (read-only unless ``--write``)::

    python -m src.data.report_cache <session_dir> [--summary] [--indent] [--write]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from ..tasks.entry_tracker import DEFAULT_EXIT_HOLD_MS
from .exporter import load_metadata, load_trials_rows
from .recorder import POINTER_STREAM_FILENAME
from .report_config import build_config_rows, setting
from .report_eye import (
    DEFAULT_PUPIL,
    FrameIndex,
    load_gaze_frames,
    load_pointer_frames,
    load_raw_samples,
)
from .report_follow import build_follow
from .report_geometry import Geometry
from .report_metrics import (
    OUTCOME_SKIPPED,
    SCORED_OUTCOMES,
    analyse_raw,
    build_trials,
    summary_rows,
)
from .report_quality import eye_summary, frames_by_window, gaze_valid_share, quality_block
from .report_util import DASH
from .report_visual import (
    DEFAULT_HEAT,
    DEFAULT_PATH,
    SmoothParams,
    heat_map,
    load_target_track,
    map_marks,
    smooth_frames,
)
from .saccades import DEFAULT_IVT

# 2: ``path`` is the gaze stream smoothed as the on-screen cursor was (it was the raw
# stream), trials gain ``scanpath`` (fixation centroids), the config rows show seconds.
# 3: the ``follow`` block (Follow the Target, SPEC-input-selection-and-follow.md: ``None`` for
# every other task, ``{"legacy": true}`` for an old Follow & Click folder), the trial outcomes
# ``followed`` / ``not_followed``, a Mouse run's ``path`` from ``pointer_stream.csv``.
# 4: ``clicks`` / ``click_errors`` in every trial and Summary of Results row (a Switch test's
# Clicks columns, SPEC-input-selection-and-follow.md 4.5).
REPORT_VERSION = 4
REPORT_FILENAME = "report.json"

_log = logging.getLogger(__name__)


class ReportError(ValueError):
    """The folder holds nothing a report can be built from (no ``trials.csv``)."""


def _events(session_dir: Path) -> list[dict[str, Any]]:
    """``events.jsonl`` rows, skipping any unreadable line (a crash can truncate it)."""
    path = session_dir / "events.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            out.append(event)
    return out


def _number(value: Any) -> float | None:
    try:
        return None if isinstance(value, bool) else float(value)
    except (TypeError, ValueError):
        return None


def build_report(session_dir: str | Path) -> dict[str, Any]:
    """The full report of one run folder. Raises :class:`ReportError` when there is
    no readable ``trials.csv``; anything else a folder lacks degrades to ``None``."""
    session_dir = Path(session_dir)
    try:
        meta = load_metadata(session_dir)
    except (OSError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    try:
        trial_rows = load_trials_rows(session_dir)
    except OSError as exc:
        raise ReportError(f"{session_dir}: no readable trials.csv ({exc})") from exc

    tasks = meta.get("tasks")
    task_id = (trial_rows[0].get("task_id") if trial_rows else None) or (
        tasks[0] if isinstance(tasks, list) and tasks else None
    )
    settings = meta.get("settings") if isinstance(meta.get("settings"), dict) else {}
    geometry = Geometry.from_metadata(meta)
    index = FrameIndex(load_gaze_frames(session_dir))
    smoothing = SmoothParams.from_values(
        setting(settings, "dwell.smoothing.enabled", "dwell", "smoothing", "enabled"),
        setting(settings, "dwell.smoothing.alpha", "dwell", "smoothing", "alpha"),
    )
    # The path drawn is the *pointer's*: the gaze, or -- a Mouse run -- the mouse
    # (SPEC-input-selection-and-follow.md 4.5), through the same cursor filter.
    pointer_frames = (
        load_pointer_frames(session_dir, geometry) if meta.get("input_pointer") == "mouse" else []
    )
    path_index = FrameIndex(smooth_frames(pointer_frames or index.frames, smoothing))
    raw_samples = load_raw_samples(session_dir)
    raw = analyse_raw(raw_samples, meta, geometry)
    track = load_target_track(session_dir)
    events = _events(session_dir)
    shrunk = next((e for e in events if e.get("kind") == "TARGET_SHRUNK"), None)
    resized = any(e.get("kind") == "CANVAS_RESIZED" for e in events)
    iti_ms = _number(setting(settings, "task.inter_trial_interval_ms", "inter_trial_interval_ms"))

    trials = build_trials(
        trial_rows, geometry, index, raw, track, iti_ms=iti_ms, task_id=task_id,
        path_index=path_index,
    )
    heat = heat_map(frames_by_window(index, trials), geometry)
    share = gaze_valid_share(index, trials)
    n_rows = len(trial_rows)
    planned = meta.get("planned_trials") if isinstance(meta.get("planned_trials"), int) else None
    header = trial_rows[0].keys() if trial_rows else ()
    n_skipped = sum(1 for t in trials if t["outcome"] == OUTCOME_SKIPPED)
    # What "on target" meant: the radius plus this. The setting (a selection task), else what the
    # run recorded (Follow the Target has no such control on its page).
    margin_px = _number(
        setting(settings, "dwell.jitter_tolerance_px", "dwell", "jitter_tolerance_px")
    )
    if margin_px is None:
        margin_px = _number(meta.get("hitbox_margin_px"))
    follow = None
    if task_id == "follow_moving":
        follow = build_follow(
            trial_rows, trials, geometry=geometry, raw=raw, raw_samples=raw_samples,
            track=track, path_index=path_index, margin_px=margin_px,
            motion_path=setting(settings, None, "motion", "path"),
            speed_frac_per_s=_number(
                setting(settings, "motion.speed_frac_per_s", "motion", "speed_frac_per_s")
            ),
        )

    return {
        "report_version": REPORT_VERSION,
        "params": {
            "ivt": DEFAULT_IVT.as_dict(),
            "entries": {"exit_hold_ms": DEFAULT_EXIT_HOLD_MS},
            "pupil": DEFAULT_PUPIL.as_dict(),
            "heat": DEFAULT_HEAT.as_dict(),
            # The gaze path's thinning (raw-path parameters, unchanged) and the cursor filter
            # it is drawn through (``enabled`` off: the raw stream).
            "path": {**DEFAULT_PATH.as_dict(), "smoothing": smoothing.as_dict()},
        },
        "session": {
            "session_id": meta.get("session_id") or session_dir.name,
            "task_id": task_id,
            "subject": meta.get("subject_id"),
            "test_name": meta.get("test_name"),
            "config_name": settings.get("config_name") or meta.get("config_name"),
            "started_ns": meta.get("started_ns"),
            "planned_trials": planned,
            "completed_trials": meta.get("completed_trials")
            if isinstance(meta.get("completed_trials"), int)
            else n_rows,
            "outcome": meta.get("outcome"),
            "n_rows": n_rows,
            "n_scored": sum(1 for t in trials if t["outcome"] in SCORED_OUTCOMES),
            "n_skipped": n_skipped,
            "n_not_presented": max(0, planned - n_rows) if planned is not None else None,
            # The test's input (SPEC-input-selection-and-follow.md H1, 4.6): None on an
            # older folder. ``gaze_recorded`` False (a Mouse run with no tracker) is what
            # makes the eye sections say "not recorded" instead of a dash.
            "pointer": meta.get("input_pointer"),
            "selection": meta.get("input_selection"),
            "gaze_recorded": meta.get("gaze_recorded")
            if isinstance(meta.get("gaze_recorded"), bool)
            else None,
            # Which inputs the folder had, so the UI can say why a column is a dash.
            "sources": {
                "pointer_stream": (session_dir / POINTER_STREAM_FILENAME).exists(),
                "gaze_stream": bool(index.frames),
                "raw_gaze": raw is not None,
                "saccades": raw is not None and raw.saccades is not None,
                "geometry": geometry.has_angles,
                "entries": "entries" in header,
                "end_positions": "end_x" in header,
                "slot_index": "slot_index" in header,
                "target_track": track is not None,
                "layout_slots": meta.get("layout_slots") is not None,
            },
        },
        "geometry": {**geometry.as_dict(), "assumed_for_visuals": not geometry.has_angles},
        "config": {
            "rows": [
                list(r)
                for r in build_config_rows(
                    settings, meta, task_id=task_id, shrunk=shrunk, geometry=geometry,
                    follow_layout=follow is not None and not follow.get("legacy"),
                )
            ]
        },
        "trials": trials,
        # Follow the Target's figures (SPEC-input-selection-and-follow.md 4.5/4.6); None for
        # every other task, ``{"legacy": true}`` for an old Follow & Click folder.
        "follow": follow,
        "summary": {
            "rows": summary_rows(trials),
            "eye": eye_summary(trials, meta, geometry, share),
        },
        "map": {
            "aspect": None if geometry.aspect is None else round(geometry.aspect, 5),
            "slots": meta.get("layout_slots"),
            "hit_tolerance_px": margin_px,
            **map_marks(trials, geometry, moving=task_id == "follow_moving"),
        },
        "heat": heat,
        "quality": quality_block(
            n_rows=n_rows,
            planned=planned,
            outcome=meta.get("outcome"),
            share=share,
            off_canvas_share=heat["off_canvas_share"],
            canvas_resized=resized,
        ),
    }


# -- the cache ---------------------------------------------------------------------


def report_json(report: dict[str, Any]) -> str:
    """The exact text written to ``report.json``: compact and deterministic."""
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"))


def write_report(session_dir: str | Path, report: dict[str, Any] | None = None) -> Path:
    """Write ``report.json`` (building the report first when none is given); the
    file appears whole or not at all."""
    session_dir = Path(session_dir)
    text = report_json(report if report is not None else build_report(session_dir))
    path = session_dir / REPORT_FILENAME
    tmp = path.with_name(REPORT_FILENAME + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def write_report_safely(session_dir: str | Path) -> Path | None:
    """:func:`write_report` for the end of a recorded run: a failure is logged, never
    raised, so the run's own files are not put at risk by an analysis bug. The report
    is rebuilt on open if it is missing, so nothing is lost."""
    try:
        return write_report(session_dir)
    except Exception as exc:  # noqa: BLE001 - analysis must never break closing a run
        _log.warning("report.json not written for %s: %s", session_dir, exc)
        return None


def load_or_build_report(session_dir: str | Path) -> dict[str, Any]:
    """The cached report, or a fresh build (re-cached) when ``report.json`` is
    missing, unreadable or not :data:`REPORT_VERSION`. A folder that cannot be
    written to still gets its report, just uncached."""
    session_dir = Path(session_dir)
    try:
        cached = json.loads((session_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
        if isinstance(cached, dict) and cached.get("report_version") == REPORT_VERSION:
            return cached
    except (OSError, ValueError):
        pass
    report = build_report(session_dir)
    try:
        write_report(session_dir, report)
    except OSError as exc:
        _log.warning("report.json not cached for %s: %s", session_dir, exc)
    return report


# -- dev CLI -----------------------------------------------------------------------


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return DASH
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def summary_text(report: dict[str, Any]) -> str:
    """A short human digest of a report, for the CLI's ``--summary``."""
    s, q = report["session"], report["quality"]
    lines = [
        f"{s['session_id']}  task={s['task_id']}  rows={s['n_rows']} scored={s['n_scored']} "
        f"skipped={s['n_skipped']} planned={_fmt(s['planned_trials'])} outcome={_fmt(s['outcome'])}",
        "sources: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in s["sources"].items()),
        "summary of results:",
    ]
    for r in report["summary"]["rows"]:
        lines.append(
            f"  {r['label']:<30} {r['pct_n']:<14} trial={_fmt(r['trial_time_s'], 3)} s  "
            f"reaction={_fmt(r['reaction_time_s'], 3)} s  entries={_fmt(r['entries'])}"
        )
    eye = report["summary"]["eye"]
    lines.append("eye metrics:")
    for key, value in eye.items():
        lines.append(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
    heat = report["heat"]
    lines.append(
        f"heat: empty={heat['empty']} total_s={heat['total_s']} off_canvas={_fmt(heat['off_canvas_share'], 4)}"
    )
    lines.append(
        f"quality: valid_share={_fmt(q['valid_share'], 4)} warnings="
        + json.dumps([w["code"] for w in q["warnings"]])
    )
    lines.append("trials:")
    for t in report["trials"]:
        f, sc, p = t["fixations"], t["saccades"], t["pupil"]
        lines.append(
            f"  {t['trial']:>3} {t['outcome']:<8} size={_fmt(t['size_deg'], 1)}deg "
            f"dist={_fmt(t['distance_deg'], 1)} time={_fmt(t['trial_time_s'], 2)} "
            f"rt={_fmt(t['reaction_time_s'], 2)} ent={_fmt(t['entries'])} "
            f"fix={_fmt(f['count'])}/{_fmt(f['mean_dur_ms'], 0)}ms sacc={_fmt(sc['count'])}/"
            f"{_fmt(sc['mean_peak'], 0)}deg/s pupil={_fmt(p['mean_mm'], 2)}mm "
            f"d={_fmt(p['change_mm'], 3)} path_pts={sum(len(seg) for seg in t['path'])}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.data.report_cache",
        description="Build one run folder's report and print it (read-only unless --write).",
    )
    parser.add_argument("session_dir", help="a session folder (trials.csv, metadata.json, ...)")
    parser.add_argument("--summary", action="store_true", help="print a short digest, not the JSON")
    parser.add_argument("--indent", action="store_true", help="pretty-print the JSON")
    parser.add_argument("--write", action="store_true", help="also write report.json into the folder")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        report = build_report(args.session_dir)
        if args.write:
            write_report(args.session_dir, report)
    except ReportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.summary:
        print(summary_text(report))
    elif args.indent:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(report_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
