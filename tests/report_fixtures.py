"""Synthetic run folders and rows for the per-test report tests
(SPEC-compass-task-flow.md 4D.10). Not a test module: helpers only."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from src.data.analysis_export import all_gaze_header, rec_to_all_gaze_row
from src.data.recorder import TARGET_TRACK_COLUMNS, TARGET_TRACK_FILENAME
from src.data.report_eye import GazeFrame, RawSample
from src.data.schema import TrialRecord

SEC = 1_000_000_000
T0 = 1_791_000_000 * SEC  # a host-clock origin; everything is relative to it
OFFSET_NS = T0 - 3 * SEC  # all_gaze TIME=0 is 3 s before T0 on the host clock

# The reference rig, the EYEGEOM canvas, a resolved 5 deg target size.
RIG_META: dict[str, Any] = {
    "subject_id": "P001",
    "session_id": "2026-10-06_P001_click_grid_run1",
    "started_ns": T0,
    "gazepoint_model": "GP3HD",
    "input_mode": "eye",
    "calibration_error_px": 21.31,
    "calibration_points": 5,
    "calibration_source": "measured",
    "tasks": ["click_grid"],
    "screen_width_px": 1920,
    "screen_height_px": 1080,
    "screen_physical_width_mm": 527.0,
    "screen_physical_height_mm": 296.0,
    "viewing_distance_mm": 650.0,
    "canvas_width_px": 1640,
    "canvas_height_px": 957,
    "canvas_offset_x_px": 0,
    "canvas_offset_y_px": 75,
    "canvas_units": "physical",
    "display_width_px": 1920,
    "display_height_px": 1080,
    "display_scale_percent": 100,
    "display_standard": True,
    "gazepoint_rate_hz": 150,
    "target_size": {
        "preset": "medium", "diameter_deg": 5.0, "radius_px": 103.4, "mm_per_px": 0.2745,
        "mm_per_px_source": "edid", "viewing_distance_mm": 650.0,
    },
    "settings": {
        "config_name": "Standard",
        "live": {
            "dwell.threshold_ms": 800, "dwell.refractory_ms": 500,
            "dwell.jitter_tolerance_px": 40, "dwell.visual_cursor": True,
            "dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.22,
            "task.timeout_ms": 8000, "task.inter_trial_interval_ms": 800,
        },
        "structural": {"trials": 6, "grid": {"rows": 3, "cols": 3, "gap": "standard"},
                       "theme": "forest",
                       "feedback": {"hit_sound": True, "miss_sound": True, "particles": True}},
    },
}

# The columns P2/P3 added to trials.csv; a legacy folder lacks all of them.
NEW_TRIAL_COLUMNS = ("is_skipped", "entries", "end_x", "end_y", "slot_index")


def record(
    trial_id: int,
    onset_ns: int,
    outcome: str = "hit",
    *,
    dur_s: float = 1.0,
    first_gaze_s: float | None = 0.2,
    entries: int = 1,
    attempts: int = 1,
    x: float = 0.5,
    y: float = 0.5,
    radius_px: float = 100.0,
    slot: int = -1,
    end_xy: tuple[float, float] | None = None,
    task: str = "click_grid",
) -> TrialRecord:
    """One finished trial. ``dur_s`` is onset to selection (hit), to the end (timeout)
    or to the skip."""
    end_ns = onset_ns + round(dur_s * SEC)
    rec = TrialRecord(
        trial_id=trial_id,
        task_id=task,
        target_x=x,
        target_y=y,
        target_radius_px=radius_px,
        t_target_shown_ns=onset_ns,
        t_first_gaze_on_target_ns=(
            None if first_gaze_s is None else onset_ns + round(first_gaze_s * SEC)
        ),
        t_click_ns=end_ns if outcome == "hit" else None,
        t_end_ns=end_ns,
        is_hit=outcome == "hit",
        is_timeout=outcome == "timeout",
        is_skipped=outcome == "skipped",
        attempts=attempts,
        entries=entries,
        end_x=(end_xy or (x, y))[0],
        end_y=(end_xy or (x, y))[1],
        slot_index=slot,
    )
    return rec


def row_strings(rec: TrialRecord, *, legacy: bool = False) -> dict[str, str]:
    """A ``trials.csv`` row as ``csv.DictReader`` returns it (all strings)."""
    row = {k: str(v) for k, v in rec.as_row().items()}
    if legacy:
        for col in NEW_TRIAL_COLUMNS:
            row.pop(col, None)
    return row


def monitor_xy(cx: float, cy: float, meta: dict[str, Any] = RIG_META) -> tuple[float, float]:
    """Monitor-normalized position of a canvas-normalized point (the rig's canvas)."""
    return (
        (cx * meta["canvas_width_px"] + meta["canvas_offset_x_px"]) / meta["screen_width_px"],
        (cy * meta["canvas_height_px"] + meta["canvas_offset_y_px"]) / meta["screen_height_px"],
    )


def frames_between(
    start_ns: int, end_ns: int, rate_hz: float = 60.0, *, canvas_xy=(0.5, 0.5), valid=True
) -> list[GazeFrame]:
    """Valid frames at ``rate_hz`` resting at a canvas position, FPOGID counting up
    every 0.4 s so each is a fixation."""
    step = round(SEC / rate_hz)
    x, y = monitor_xy(*canvas_xy)
    out = []
    t = start_ns
    while t <= end_ns:
        fid = (t - start_ns) // round(0.4 * SEC) + 1
        dur = ((t - start_ns) % round(0.4 * SEC)) / SEC
        out.append(GazeFrame(t, x, y, valid, fid, dur))
        t += step
    return out


def raw_samples(
    seconds: float,
    pupil_fn=lambda t: 3.5,
    *,
    rate_hz: float = 150.0,
    x_fn=lambda t: 0.4,
    invalid=lambda t: False,
    left_ok=lambda t: True,
) -> list[RawSample]:
    """Device-rate samples from TIME 0 for ``seconds`` seconds."""
    out = []
    for i in range(round(seconds * rate_hz)):
        t = i / rate_hz
        bad = invalid(t)
        p = pupil_fn(t)
        out.append(
            RawSample(t, x_fn(t), 0.5, not bad, p, left_ok(t) and not bad, p, not bad)
        )
    return out


def deg_to_dx(deg: float) -> float:
    """Monitor-normalized x distance that is ``deg`` of visual angle on the rig."""
    return 2 * 650.0 * math.tan(math.radians(deg / 2)) / 527.0


# -- folders on disk -----------------------------------------------------------------


def write_gaze_stream(path: Path, frames: list[GazeFrame]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_ns", "x", "y", "valid", "fixation_id", "fix_duration_s",
                    "pupil_left", "pupil_right"])
        for f in frames:
            w.writerow([f.t_ns, f.x, f.y, int(f.valid), "" if f.fid is None else f.fid,
                        "" if f.dur_s is None else f.dur_s, "", ""])


def write_all_gaze(path: Path, samples: list[RawSample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(all_gaze_header(datetime(2026, 10, 6, 12, 0, 0), 1_000_000_000))
        for s in samples:
            attrs = {
                "BPOGX": f"{s.x:.5f}", "BPOGY": f"{s.y:.5f}", "BPOGV": str(int(s.valid)),
                "LPMM": f"{s.pupil_l:.5f}", "LPMMV": str(int(s.pupil_l_ok)),
                "RPMM": f"{s.pupil_r:.5f}", "RPMMV": str(int(s.pupil_r_ok)),
            }
            w.writerow(list(rec_to_all_gaze_row(attrs, time_s=s.t_s, media_name="t").values()))


def write_session(
    folder: Path,
    records: list[TrialRecord],
    *,
    meta: dict[str, Any] | None = None,
    frames: list[GazeFrame] | None = None,
    samples: list[RawSample] | None = None,
    track: list[tuple[int, int, float, float]] | None = None,
    events: list[dict[str, Any]] | None = None,
    legacy: bool = False,
) -> Path:
    """A run folder on disk. ``legacy`` drops the P2/P3 trials columns."""
    folder.mkdir(parents=True, exist_ok=True)
    header = [c for c in TrialRecord.csv_header() if not (legacy and c in NEW_TRIAL_COLUMNS)]
    with (folder / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for rec in records:
            w.writerow(row_strings(rec, legacy=legacy))
    meta = dict(RIG_META if meta is None else meta)
    (folder / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    if frames is not None:
        write_gaze_stream(folder / "gaze_stream.csv", frames)
    if samples is not None:
        write_all_gaze(folder / "all_gaze.csv", samples)
    if track is not None:
        with (folder / TARGET_TRACK_FILENAME).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(TARGET_TRACK_COLUMNS)
            w.writerows(track)
    if events is not None:
        (folder / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
    return folder
