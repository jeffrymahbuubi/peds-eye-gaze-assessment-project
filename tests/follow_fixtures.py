"""Synthetic Follow the Target data for the analysis and report tests
(SPEC-input-selection-and-follow.md H7, H8, A7): a target on a known path, a child's gaze that
follows it at a chosen pursuit gain with catch-up saccades and noise, and run folders on disk.
Not a test module."""

from __future__ import annotations

import copy
import csv
import json
import math
import random
from pathlib import Path
from typing import Any

from src.data.recorder import (
    POINTER_STREAM_COLUMNS,
    POINTER_STREAM_FILENAME,
    TARGET_TRACK_COLUMNS,
    TARGET_TRACK_FILENAME,
)
from src.data.report_eye import GazeFrame, RawSample
from src.data.report_geometry import Geometry
from src.data.schema import TrialRecord
from tests.report_fixtures import write_session

SEC = 1_000_000_000
T0 = 1_791_000_000 * SEC  # a host-clock origin; everything is relative to it
OFFSET_NS = T0 - 3 * SEC  # all_gaze TIME=0 is 3 s before T0 on the host clock
RATE_HZ = 150.0
TRACK_HZ = 20.0

# The reference rig with the task canvas filling the screen (canvas == monitor, so canvas-normalized
# and monitor-normalized coordinates are one thing and the tests can read them either way).
FULL_CANVAS_META: dict[str, Any] = {
    "subject_id": "P001",
    "session_id": "2026-10-08_P001_follow_moving_run1",
    "started_ns": T0,
    "gazepoint_model": "GP3HD",
    "input_mode": "eye",
    "input_pointer": "gaze",
    "input_selection": None,
    "gaze_recorded": True,
    "calibration_error_px": 21.0,
    "calibration_points": 5,
    "calibration_source": "measured",
    "tasks": ["follow_moving"],
    "screen_width_px": 1920,
    "screen_height_px": 1080,
    "screen_physical_width_mm": 527.0,
    "screen_physical_height_mm": 296.0,
    "viewing_distance_mm": 650.0,
    "canvas_width_px": 1920,
    "canvas_height_px": 1080,
    "canvas_offset_x_px": 0,
    "canvas_offset_y_px": 0,
    "canvas_units": "physical",
    "display_width_px": 1920,
    "display_height_px": 1080,
    "display_scale_percent": 100,
    "display_standard": True,
    "gazepoint_rate_hz": 150,
    "hitbox_margin_px": 40.0,
    "raw_clock_offset_ns": OFFSET_NS,
    "target_size": {
        "preset": "medium", "diameter_deg": 5.0, "radius_px": 103.4, "mm_per_px": 0.2745,
        "mm_per_px_source": "edid", "viewing_distance_mm": 650.0,
    },
    "planned_trials": 3,
    "settings": {
        "config_name": "Standard",
        "live": {
            "dwell.visual_cursor": True, "dwell.smoothing.enabled": True,
            "dwell.smoothing.alpha": 0.22, "task.timeout_ms": 10000,
            "task.inter_trial_interval_ms": 1000, "motion.speed_frac_per_s": 0.2,
        },
        "structural": {
            "trials": 3, "motion": {"path": "horizontal"}, "target": {"size": "medium"},
            "input": {"pointer": "gaze"}, "theme": "forest",
            "feedback": {"hit_sound": True, "target_glow": True, "particles": True},
        },
    },
}

MM_PER_DEG = 650.0 * math.tan(math.radians(1.0))  # the rig's mm on the screen per degree


def geometry(meta: dict[str, Any] | None = None) -> Geometry:
    return Geometry.from_metadata(FULL_CANVAS_META if meta is None else meta)


# -- the target ------------------------------------------------------------------------------


def horizontal(speed_frac: float = 0.2):
    """A bouncing sweep between x = 0.1 and 0.9 at ``speed_frac`` of the width per second."""

    def position(t_s: float) -> tuple[float, float]:
        span = 0.8
        raw = (speed_frac * t_s) % (2 * span)
        return 0.1 + (raw if raw <= span else 2 * span - raw), 0.5

    return position


def circular(speed_frac: float = 0.2):
    """The orbit of the task: radius 0.3 round the centre, ``speed_frac`` rotations per second."""

    def position(t_s: float) -> tuple[float, float]:
        angle = 2 * math.pi * speed_frac * t_s
        return 0.5 + 0.3 * math.cos(angle), 0.5 + 0.3 * math.sin(angle)

    return position


def vertical(speed_frac: float = 0.2):
    """A bouncing sweep between y = 0.1 and 0.9 at the same px/s as the horizontal one."""
    norm_speed = speed_frac * 1920 / 1080

    def position(t_s: float) -> tuple[float, float]:
        span = 0.8
        raw = (norm_speed * t_s) % (2 * span)
        return 0.5, 0.1 + (raw if raw <= span else 2 * span - raw)

    return position


def target_track_rows(position, seconds: float, *, trial: int = 0, origin_ns: int = T0):
    """``target_track.csv`` rows ``(t_ns, trial, x, y)`` at 20 Hz."""
    n = int(seconds * TRACK_HZ) + 1
    return [
        (origin_ns + round(k / TRACK_HZ * SEC), trial, round(position(k / TRACK_HZ)[0], 5),
         round(position(k / TRACK_HZ)[1], 5))
        for k in range(n)
    ]


# -- the child -------------------------------------------------------------------------------


def _err_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 527.0, (a[1] - b[1]) * 296.0) / MM_PER_DEG


def simulate_gaze(
    position,
    seconds: float,
    *,
    gain: float = 0.8,
    noise_deg: float = 0.1,
    catch_up_deg: float | None = 2.8,
    seed: int = 1,
    invalid=lambda t_s: False,
    start_s: float = 0.0,
) -> tuple[list[RawSample], list[float]]:
    """Device-rate samples (TIME 0 at ``start_s`` before the trial's first sample is NOT added: the
    samples run from TIME 0 to ``start_s + seconds``, the target's clock being the sample time minus
    ``start_s``) of a gaze that follows ``position`` with smooth pursuit at ``gain`` and, when its
    error reaches ``catch_up_deg``, a one-sample jump back onto the target (a catch-up saccade).
    Returns ``(samples, the times of the injected catch-up saccades in seconds)``."""
    rng = random.Random(seed)
    dt = 1.0 / RATE_HZ
    sigma_x, sigma_y = noise_deg * MM_PER_DEG / 527.0, noise_deg * MM_PER_DEG / 296.0
    total = int((start_s + seconds) * RATE_HZ)
    samples: list[RawSample] = []
    jumps: list[float] = []
    gx, gy = position(0.0)
    for i in range(total):
        t = i * dt
        t_target = max(t - start_s, 0.0)
        tx, ty = position(t_target)
        if i:
            px, py = position(max(t - dt - start_s, 0.0))
            gx, gy = gx + gain * (tx - px), gy + gain * (ty - py)
        if catch_up_deg is not None and _err_deg((gx, gy), (tx, ty)) >= catch_up_deg:
            gx, gy = tx, ty
            jumps.append(t)
        bad = invalid(t)
        samples.append(
            RawSample(
                t, gx + rng.gauss(0, sigma_x), gy + rng.gauss(0, sigma_y), not bad,
                3.5, not bad, 3.5, not bad,
            )
        )
    return samples, jumps


# -- folders -----------------------------------------------------------------------------------------


def follow_record(
    trial_id: int,
    onset_ns: int,
    *,
    duration_s: float = 10.0,
    valid_ms: float | None = None,
    on_target_ms: float = 7000.0,
    mean_dist_px: float | None = 40.0,
    first_gaze_s: float | None = 0.4,
    followed: bool | None = None,
    skipped: bool = False,
    radius_px: float = 100.0,
    start_xy: tuple[float, float] = (0.1, 0.5),
    end_xy: tuple[float, float] = (0.5, 0.5),
) -> TrialRecord:
    """A Follow the Target row: ``is_hit`` is *followed*, ``valid_ms`` defaults to the whole
    duration."""
    valid = duration_s * 1000.0 if valid_ms is None else valid_ms
    pct = 100.0 * on_target_ms / valid if valid else 0.0
    rec = TrialRecord(
        trial_id=trial_id,
        task_id="follow_moving",
        target_x=start_xy[0],
        target_y=start_xy[1],
        target_radius_px=radius_px,
        t_target_shown_ns=onset_ns,
        t_first_gaze_on_target_ns=(
            None if first_gaze_s is None else onset_ns + round(first_gaze_s * SEC)
        ),
        t_end_ns=onset_ns + round(duration_s * SEC),
        is_hit=(pct >= 50.0) if followed is None else followed,
        is_skipped=skipped,
        entries=1,
        end_x=end_xy[0],
        end_y=end_xy[1],
        valid_ms=valid,
        on_target_ms=on_target_ms,
        dist_sum_px=0.0 if mean_dist_px is None else mean_dist_px * 100,
        dist_n=0 if mean_dist_px is None else 100,
    )
    return rec


def write_track(folder: Path, rows) -> None:
    with (folder / TARGET_TRACK_FILENAME).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(TARGET_TRACK_COLUMNS)
        writer.writerows(rows)


# -- whole run folders (a Gaze run, a Mouse run with no tracker, an old Follow & Click one) -----------

TRIAL_S = 10.0
PERIOD_S = 12.0  # a trial and its pause
MM_PER_PX = 0.2745
FORTY_PX_DEG = 0.969  # 40 px * 0.2745 mm/px at 650 mm, as a visual angle


def onset(k: int) -> int:
    return OFFSET_NS + round(k * PERIOD_S * SEC)


def records():
    return [
        follow_record(0, onset(0), on_target_ms=7000.0, first_gaze_s=0.4),
        follow_record(1, onset(1), on_target_ms=8000.0, first_gaze_s=0.2),
        follow_record(2, onset(2), on_target_ms=3000.0, first_gaze_s=1.2, mean_dist_px=80.0),
    ]


def run_samples(gain=0.8):
    """One continuous gaze over three trials, the target restarting each time."""
    base = horizontal()

    def position(t):
        k = int(t // PERIOD_S)
        return base(min(t - k * PERIOD_S, TRIAL_S))

    samples, jumps = simulate_gaze(position, 2 * PERIOD_S + TRIAL_S, gain=gain, noise_deg=0.1)
    return samples, jumps


def path_frames(off_after_s=None, off_trial=2):
    """60 Hz gaze-stream frames on the target; in trial ``off_trial`` far from it after
    ``off_after_s``."""
    base = horizontal()
    frames = []
    for k in range(3):
        # A blink in the pause before each trial: the cursor's smoothing starts afresh.
        frames.append(GazeFrame(onset(k) - SEC, 0.5, 0.5, False, None, None))
        for i in range(int(TRIAL_S * 60) + 1):
            t = i / 60.0
            x, y = base(t)
            if off_after_s is not None and k == off_trial and t >= off_after_s:
                x += 0.3
            frames.append(GazeFrame(onset(k) + round(t * SEC), x, y, True, None, None))
    return frames


def folder(tmp_path, *, meta=None, recs=None, samples=True, frames=True, name="run"):
    base = horizontal()
    track = []
    for k in range(3):
        track.extend(target_track_rows(base, TRIAL_S, trial=k, origin_ns=onset(k)))
    meta = copy.deepcopy(FULL_CANVAS_META) if meta is None else meta
    out = write_session(
        tmp_path / name,
        recs or records(),
        meta=meta,
        frames=path_frames(off_after_s=5.0) if frames else None,
        samples=run_samples()[0] if samples else None,
        track=track,
    )
    return out


def mouse_folder(tmp_path):
    meta = copy.deepcopy(FULL_CANVAS_META)
    meta.update(
        input_mode="mouse_follow", input_pointer="mouse", gaze_recorded=False,
        calibration_source="not run", calibration_points=0, calibration_error_px=None,
    )
    meta["settings"]["structural"]["input"] = {"pointer": "mouse"}
    meta.pop("raw_clock_offset_ns")
    out = folder(tmp_path, meta=meta, samples=False, frames=False, name="mouse")
    base = horizontal()
    with (out / POINTER_STREAM_FILENAME).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(POINTER_STREAM_COLUMNS)
        for k in range(3):
            writer.writerow([onset(k) - SEC, 1.4, 0.5, 0])  # the mouse is off the canvas in the pause
            for i in range(int(TRIAL_S * 60) + 1):
                t = i / 60.0
                x, y = base(t)
                writer.writerow([onset(k) + round(t * SEC), round(x, 5), round(y, 5), 1])
    return out


def legacy_folder(tmp_path):
    recs = [
        follow_record(0, onset(0), followed=True),
        follow_record(1, onset(1), followed=False),
        follow_record(2, onset(2), followed=True),
    ]
    recs[0].t_click_ns = recs[0].t_end_ns - 3 * SEC
    recs[1].is_timeout = True
    out = folder(tmp_path, recs=recs, name="old")
    old = ("valid_ms", "on_target_ms", "time_on_target_pct", "mean_dist_px", "clicks", "click_errors")
    with (out / "trials.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    keep = [c for c in rows[0] if c not in old]
    with (out / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keep)
        writer.writeheader()
        writer.writerows([{k: r[k] for k in keep} for r in rows])
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    meta["settings"]["structural"]["motion"]["select_window_ms"] = 2500
    for key in ("input_pointer", "input_selection", "gaze_recorded", "hitbox_margin_px"):
        meta.pop(key)
    (out / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return out
