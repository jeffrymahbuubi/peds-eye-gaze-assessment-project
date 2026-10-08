"""Follow the Target's analysis for the report (SPEC-input-selection-and-follow.md 4.5, 4.6,
H6-H8, H10). Pure and Qt-free, like the rest of ``src/data``.

What comes from where:

* **Time on target, mean distance, valid time** are counted live, per frame, by the task from the
  same smoothed pointer and hitbox that draw the glow (H7); they are columns of ``trials.csv``
  (``valid_ms``, ``on_target_ms``, ``time_on_target_pct``, ``mean_dist_px``) and are only read
  here. A trial is *followed* when the task said so (``is_hit``, at least 50 % of its valid time
  on target, H6).
* **Smooth-pursuit gain** and **catch-up saccades** come from the device-rate gaze of
  ``all_gaze.csv`` (H8), so a Mouse run with no tracker has neither (``None``, a dash).
* The **pointer path** coloured on / off target is the smoothed pointer (gaze, or the mouse from
  ``pointer_stream.csv``) against the target's track.

Pursuit gain (H8). Over one trial's device-rate samples, drop the invalid ones and the
saccades found by I-VT (plus one sample each side), and keep a sample only while the gaze is
within ``max_err_deg`` of the target and the target is further than ``bounce_excl_ms`` from a
bounce (a direction reversal of its track). At each kept sample the gaze velocity is the
least-squares slope of the gaze position along the target's direction over a ``window_ms``
window centred on it (a difference of two noisy samples would drown a 10 deg/s target in the
device's noise); a window with a dropped or invalid sample in it is not used, because the jump
across the gap would be read as velocity. The target's velocity is the chord of its interpolated track over the same
window (the 20 Hz log, linear interpolation: exact between bounces for the straight paths, and
the circle's chord over 100 ms is within 0.1 % of its arc), and the gain is their ratio -- the
tangent for a circle, since the direction is taken from the chord. The trial's value is the
median; fewer than ``min_usable_s`` of usable samples gives ``None``.

A folder with ``trials.csv`` but no ``on_target_ms`` column is an old Follow & Click session
and gets ``{"legacy": True}``: its report keeps the old layout (H10).
"""

from __future__ import annotations

import math
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .report_eye import FrameIndex, GazeFrame, RawSample
from .report_geometry import Geometry
from .report_metrics import OUTCOME_FOLLOWED, OUTCOME_SKIPPED, RawAnalysis
from .report_util import mean_or_none, round_or_none, to_float, to_int
from .report_visual import DEFAULT_PATH, PathParams, thin_segment, uniform_indices
from .saccades import Saccade, window_saccades

MIN_TARGET_SPEED_MM_S = 1.0  # a target slower than this has no direction worth a gain
DEFAULT_HITBOX_MARGIN_PX = 40.0  # ``dwell.jitter_tolerance_px``'s default, for a folder lacking it


@dataclass(frozen=True)
class FollowParams:
    max_err_deg: float = 3.0  # H8: the gaze must be this close to the target to count
    bounce_excl_ms: float = 100.0  # H8: ... and this far (in time) from a bounce
    min_usable_s: float = 0.5  # H8: fewer usable seconds than this gives no gain
    followed_pct: float = 50.0  # H6: the share of valid time that makes a trial "followed"
    window_ms: float = 100.0  # the velocity window (see the module docstring)
    saccade_pad_samples: int = 1  # H8: samples dropped each side of a saccade

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_FOLLOW = FollowParams()


# -- the target's track ------------------------------------------------------------


class TargetTrack:
    """One trial's moving target as logged (``target_track.csv``, about 20 Hz): times and
    positions, sorted by time, with linear interpolation between them."""

    def __init__(self, rows: Sequence[tuple[int, float, float]]) -> None:
        ordered = sorted(rows, key=lambda r: r[0])
        self.t = [r[0] for r in ordered]
        self.x = [r[1] for r in ordered]
        self.y = [r[2] for r in ordered]

    @classmethod
    def from_log(
        cls,
        track: Sequence[tuple[int, int, float, float]] | None,
        trial_id: int,
        onset_ns: int,
        end_ns: int,
    ) -> TargetTrack:
        """The rows of trial ``trial_id`` inside ``[onset_ns, end_ns]`` (a trial re-presented
        after a pause repeats its id, so the window is the trial's own)."""
        rows = [
            (t, x, y)
            for t, trial, x, y in (track or ())
            if trial == trial_id and onset_ns <= t <= end_ns
        ]
        return cls(rows)

    def __len__(self) -> int:
        return len(self.t)

    def mapped(self, fn) -> TargetTrack:
        """The same track with every ``(x, y)`` passed through ``fn`` (a frame change)."""
        return TargetTrack([(t, *fn(x, y)) for t, x, y in zip(self.t, self.x, self.y, strict=True)])

    def at(self, t_ns: int, *, clamp: bool = False) -> tuple[float, float] | None:
        """The interpolated position at ``t_ns``; outside the logged span ``None``, or the
        nearest end with ``clamp``."""
        if not self.t:
            return None
        if t_ns <= self.t[0]:
            return (self.x[0], self.y[0]) if clamp or t_ns == self.t[0] else None
        if t_ns >= self.t[-1]:
            return (self.x[-1], self.y[-1]) if clamp or t_ns == self.t[-1] else None
        k = bisect_right(self.t, t_ns)
        t0, t1 = self.t[k - 1], self.t[k]
        f = (t_ns - t0) / (t1 - t0)
        return self.x[k - 1] + f * (self.x[k] - self.x[k - 1]), self.y[k - 1] + f * (self.y[k] - self.y[k - 1])

    def bounces(self) -> list[int]:
        """Times of the direction reversals: the logged points where the step into them and
        the step out of them point against each other (the straight paths bounce at their
        ends; a circle never does). Each is good to one log step (the bounce lies between
        the neighbouring points)."""
        found = []
        for k in range(1, len(self.t) - 1):
            ax, ay = self.x[k] - self.x[k - 1], self.y[k] - self.y[k - 1]
            bx, by = self.x[k + 1] - self.x[k], self.y[k + 1] - self.y[k]
            if math.hypot(ax, ay) < 1e-9 or math.hypot(bx, by) < 1e-9:
                continue
            if ax * bx + ay * by < 0:
                found.append(self.t[k])
        return found


# -- the device-rate gaze --------------------------------------------------------------


class GazeSeries:
    """The ``all_gaze.csv`` samples of a run on the host clock, in millimetres on the screen,
    with the saccade samples (and one each side) flagged as dropped."""

    def __init__(
        self,
        samples: Sequence[RawSample],
        offset_ns: int,
        saccades: Sequence[Saccade],
        geometry: Geometry,
        params: FollowParams = DEFAULT_FOLLOW,
        sample_dt_s: float | None = None,
    ) -> None:
        n = len(samples)
        self.t_ns = [offset_ns + round(s.t_s * 1e9) for s in samples]
        self.valid = [s.valid for s in samples]
        self.x_mm = [s.x * geometry.phys_w_mm for s in samples]
        self.y_mm = [s.y * geometry.phys_h_mm for s in samples]
        times_s = [s.t_s for s in samples]
        self.dropped = [False] * n
        eps = 1e-9
        for sac in saccades:
            first = bisect_left(times_s, sac.onset_s - eps)
            last = bisect_right(times_s, sac.offset_s + eps) - 1
            for i in range(max(0, first - params.saccade_pad_samples),
                           min(n - 1, last + params.saccade_pad_samples) + 1):
                self.dropped[i] = True
        if sample_dt_s is None:
            gaps = [b - a for a, b in zip(times_s, times_s[1:], strict=False) if b > a]
            sample_dt_s = statistics.median(gaps) if gaps else None
        self.dt_s = sample_dt_s

    def usable(self, i: int) -> bool:
        return self.valid[i] and not self.dropped[i]

    def span(self, start_ns: int, end_ns: int) -> tuple[int, int]:
        """Indices ``[lo, hi)`` of the samples with ``start_ns <= t <= end_ns``."""
        return bisect_left(self.t_ns, start_ns), bisect_right(self.t_ns, end_ns)


def _mm_to_deg(chord_mm: float, distance_mm: float) -> float:
    return math.degrees(2.0 * math.atan(chord_mm / (2.0 * distance_mm)))


def pursuit_gain(
    series: GazeSeries,
    track_mm: TargetTrack,
    onset_ns: int,
    end_ns: int,
    geometry: Geometry,
    params: FollowParams = DEFAULT_FOLLOW,
) -> tuple[float | None, float]:
    """``(gain, usable seconds)`` of one trial (see the module docstring). ``track_mm`` is the
    trial's target track in millimetres on the screen (:meth:`TargetTrack.mapped`). The gain is
    ``None`` with fewer than ``params.min_usable_s`` of usable samples, or no geometry."""
    if not geometry.has_angles or series.dt_s is None or len(track_mm) < 2:
        return None, 0.0
    half_ns = round(params.window_ms * 1e6 / 2)
    half_s = half_ns / 1e9
    exclude_ns = round(params.bounce_excl_ms * 1e6)
    bounces = track_mm.bounces()
    need = max(4, int(0.6 * params.window_ms / 1000.0 / series.dt_s))
    lo, hi = series.span(onset_ns, end_ns)
    gains: list[float] = []
    for i in range(lo, hi):
        if not series.usable(i):
            continue
        t = series.t_ns[i]
        if any(abs(t - b) <= exclude_ns for b in bounces):
            continue
        before, after, centre = track_mm.at(t - half_ns), track_mm.at(t + half_ns), track_mm.at(t)
        if before is None or after is None or centre is None:
            continue
        vx, vy = (after[0] - before[0]) / (2 * half_s), (after[1] - before[1]) / (2 * half_s)
        speed = math.hypot(vx, vy)
        if speed < MIN_TARGET_SPEED_MM_S:
            continue
        err = _mm_to_deg(
            math.hypot(series.x_mm[i] - centre[0], series.y_mm[i] - centre[1]), geometry.distance_mm
        )
        if err > params.max_err_deg:
            continue
        ex, ey = vx / speed, vy / speed
        first = bisect_left(series.t_ns, t - half_ns)
        last = bisect_right(series.t_ns, t + half_ns)
        window = list(range(first, last))
        # The whole window must be clean: a saccade (or a blink) inside it leaves a gap with a
        # jump across it, and a slope through that jump is no pursuit. So a sample within half a
        # window of a dropped one is not used either, and a gap in the records (too few samples)
        # costs the window too.
        if len(window) < need or not all(series.usable(j) for j in window):
            continue
        ts = [(series.t_ns[j] - t) / 1e9 for j in window]
        ss = [series.x_mm[j] * ex + series.y_mm[j] * ey for j in window]
        t_mean, s_mean = sum(ts) / len(ts), sum(ss) / len(ss)
        denom = sum((a - t_mean) ** 2 for a in ts)
        if denom <= 0:
            continue
        slope = sum((a - t_mean) * (b - s_mean) for a, b in zip(ts, ss, strict=True)) / denom
        gains.append(slope / speed)
    usable_s = len(gains) * series.dt_s
    if usable_s < params.min_usable_s:
        return None, usable_s
    return statistics.median(gains), usable_s


def catch_up(
    series: GazeSeries,
    saccades: Sequence[Saccade],
    offset_ns: int,
    onset_ns: int,
    end_ns: int,
) -> tuple[int, float]:
    """``(saccades in the trial window, seconds of valid gaze in it)``: the catch-up rate is
    their ratio. The saccades are the I-VT ones the rest of the report uses (50 deg/s)."""
    lo, hi = series.span(onset_ns, end_ns)
    valid_s = sum(1 for i in range(lo, hi) if series.valid[i]) * (series.dt_s or 0.0)
    return len(window_saccades(saccades, offset_ns, onset_ns, end_ns)), valid_s


# -- the pointer path, on and off the target --------------------------------------------------


def pointer_path(
    frames: Sequence[GazeFrame],
    track: TargetTrack,
    geometry: Geometry,
    *,
    radius_px: float | None,
    margin_px: float,
    path_params: PathParams = DEFAULT_PATH,
) -> list[dict[str, Any]]:
    """One trial's pointer as ``[{"on": bool | None, "pts": [[x, y], ...]}, ...]``, canvas-
    normalized: polylines split wherever the pointer crosses the hitbox (radius + margin) of
    the target at that moment, so a map can draw the off-target stretches lighter. ``on`` is
    ``None`` when the folder cannot say (no canvas size or radius). Valid frames only, a gap or
    an invalid frame ends a polyline, each run is thinned like :func:`~.report_visual.gaze_path`
    and the whole is capped to ``path_params.max_points``. A run opens with the last point of the
    one before it, so the line stays joined."""
    canvas = geometry.canvas_logical_size()
    known = bool(canvas and radius_px and len(track) >= 2)
    visual = geometry.for_visuals()
    gap_ns = round(path_params.split_gap_ms * 1e6)
    reach = (radius_px or 0.0) + margin_px
    runs: list[tuple[bool | None, list[GazeFrame]]] = []
    current: list[GazeFrame] = []
    current_on: bool | None = None
    for f in frames:
        if not f.valid:
            if current:
                runs.append((current_on, current))
                current = []
            continue
        on: bool | None = None
        if known:
            cx, cy = geometry.monitor_to_canvas_norm(f.x, f.y)
            target = track.at(f.t_ns, clamp=True)
            on = math.hypot((cx - target[0]) * canvas[0], (cy - target[1]) * canvas[1]) <= reach
        if current and (f.t_ns - current[-1].t_ns > gap_ns):
            runs.append((current_on, current))
            current = []
        if current and on != current_on:
            runs.append((current_on, current))
            current = [current[-1]]
            current_on = on
        elif not current:
            current_on = on
        current.append(f)
    if current:
        runs.append((current_on, current))
    thinned = [(on, thin_segment(run, visual, path_params)) for on, run in runs if run]
    flat = [(si, f) for si, (_on, run) in enumerate(thinned) for f in run]
    # A uniform stride over the whole, plus both ends of every run, so a run still opens where
    # the one before it ended.
    edges: set[int] = set()
    start = 0
    for _on, run in thinned:
        edges.update((start, start + len(run) - 1))
        start += len(run)
    keep = sorted(set(uniform_indices(len(flat), path_params.max_points)) | edges)
    out: list[dict[str, Any]] = []
    last = -1
    for i in keep:
        si, f = flat[i]
        if si != last:
            out.append({"on": thinned[si][0], "pts": []})
            last = si
        cx, cy = geometry.monitor_to_canvas_norm(f.x, f.y)
        out[-1]["pts"].append([round(cx, 4), round(cy, 4)])
    return out


# -- the report.json block ---------------------------------------------------------------------


def is_follow_layout(trial_rows: Sequence[dict[str, str]]) -> bool:
    """Does this ``trials.csv`` carry Follow the Target's columns (``on_target_ms``)? An older
    Follow & Click folder does not, and keeps its old report layout (H10)."""
    return bool(trial_rows) and "on_target_ms" in trial_rows[0]


def build_follow(
    trial_rows: Sequence[dict[str, str]],
    trials: Sequence[dict[str, Any]],
    *,
    geometry: Geometry,
    raw: RawAnalysis | None,
    raw_samples: Sequence[RawSample] | None,
    track: Sequence[tuple[int, int, float, float]] | None,
    path_index: FrameIndex,
    margin_px: float | None,
    motion_path: str | None,
    speed_frac_per_s: float | None,
    params: FollowParams = DEFAULT_FOLLOW,
) -> dict[str, Any]:
    """The ``follow`` block of ``report.json``: per-trial and whole-test Follow the Target
    figures (the rows of the Summary and the Trial-by-Trial tables of the wireframes), and
    each trial's pointer path split on / off target. ``{"legacy": True}`` for an old folder.

    ``trials`` are the dicts of :func:`~.report_metrics.build_trials` (same order as
    ``trial_rows``): their ``outcome``, window and time-to-find are reused, so the two blocks
    cannot disagree. Gain and catch-up need the device-rate gaze (``raw``, ``raw_samples``,
    degrees from the geometry); without it they are ``None``.
    """
    if not is_follow_layout(trial_rows):
        return {"legacy": True}
    series = None
    if raw is not None and raw.saccades is not None and raw_samples and geometry.has_angles:
        series = GazeSeries(raw_samples, raw.offset_ns, raw.saccades, geometry, params, raw.sample_dt_s)
    margin = DEFAULT_HITBOX_MARGIN_PX if margin_px is None else margin_px

    def to_mm(x: float, y: float) -> tuple[float, float]:
        mx, my = geometry.canvas_to_monitor_norm(x, y)
        return mx * (geometry.phys_w_mm or 0.0), my * (geometry.phys_h_mm or 0.0)

    items: list[dict[str, Any]] = []
    total_catch = 0
    total_valid_s = 0.0
    total_valid_ms = total_ms = 0.0
    for row, trial in zip(trial_rows, trials, strict=True):
        outcome = trial["outcome"]
        onset, end = trial["onset_ns"], trial["end_ns"]
        item: dict[str, Any] = {
            "trial": trial["trial"],
            "outcome": outcome,
            "followed": None if outcome == OUTCOME_SKIPPED else outcome == OUTCOME_FOLLOWED,
            "duration_s": None,
            "valid_ms": None,
            "on_target_ms": None,
            "time_on_target_pct": None,
            "mean_distance_px": None,
            "mean_distance_deg": None,
            "time_to_find_s": None,
            "valid_pct": None,
            "pursuit_gain": None,
            "gain_usable_s": None,
            "catch_up_count": None,
            "catch_up_per_s": None,
            "pointer_path": [],
        }
        items.append(item)
        if outcome == OUTCOME_SKIPPED or onset is None or end is None:
            continue
        duration_ms = (end - onset) / 1e6
        valid_ms, on_ms = to_float(row.get("valid_ms")), to_float(row.get("on_target_ms"))
        mean_px = to_float(row.get("mean_dist_px"))
        item["duration_s"] = round(duration_ms / 1000.0, 3)
        item["valid_ms"], item["on_target_ms"] = valid_ms, on_ms
        if valid_ms is not None and on_ms is not None and valid_ms > 0:
            item["time_on_target_pct"] = round(100.0 * on_ms / valid_ms, 1)
        item["mean_distance_px"] = mean_px
        item["mean_distance_deg"] = (
            None if mean_px is None else round_or_none(geometry.logical_px_to_deg(mean_px), 2)
        )
        item["time_to_find_s"] = trial.get("reaction_time_s")
        if valid_ms is not None and duration_ms > 0:
            item["valid_pct"] = round(min(100.0, 100.0 * valid_ms / duration_ms), 1)
            total_valid_ms += valid_ms
            total_ms += duration_ms
        trial_id = (to_int(row.get("trial_id")) or 0)
        target_track = TargetTrack.from_log(track, trial_id, onset, end)
        if series is not None and len(target_track) >= 2:
            gain, usable_s = pursuit_gain(
                series, target_track.mapped(to_mm), onset, end, geometry, params
            )
            item["pursuit_gain"] = round_or_none(gain, 3)
            item["gain_usable_s"] = round(usable_s, 3)
            count, valid_s = catch_up(series, raw.saccades, raw.offset_ns, onset, end)
            item["catch_up_count"] = count
            if valid_s > 0:
                item["catch_up_per_s"] = round(count / valid_s, 2)
                total_catch += count
                total_valid_s += valid_s
        frames = path_index.window(onset, end)
        if frames:
            item["pointer_path"] = pointer_path(
                frames, target_track, geometry,
                radius_px=to_float(row.get("target_radius_px")), margin_px=margin,
            )

    scored = [it for it in items if it["followed"] is not None]
    pcts = [it["time_on_target_pct"] for it in scored if it["time_on_target_pct"] is not None]
    gains = [it["pursuit_gain"] for it in scored if it["pursuit_gain"] is not None]
    summary = {
        "n_trials": len(scored),
        "followed": sum(1 for it in scored if it["followed"]),
        "time_on_target_pct": {
            "mean": mean_or_none(pcts, 1),
            "min": min(pcts) if pcts else None,
            "max": max(pcts) if pcts else None,
        },
        "mean_distance_deg": mean_or_none([it["mean_distance_deg"] for it in scored], 2),
        "time_to_find_s": mean_or_none([it["time_to_find_s"] for it in scored], 2),
        "pursuit_gain": round(statistics.median(gains), 3) if gains else None,
        "pursuit_gain_trials": len(gains),
        "catch_up_per_s": round(total_catch / total_valid_s, 2) if total_valid_s > 0 else None,
        "valid_pct": round(100.0 * total_valid_ms / total_ms, 1) if total_ms > 0 else None,
    }
    durations = [it["duration_s"] for it in scored if it["duration_s"] is not None]
    return {
        "legacy": False,
        "params": params.as_dict(),
        "path": motion_path,
        "speed_frac_per_s": speed_frac_per_s,
        "trial_duration_s": round(statistics.median(durations), 1) if durations else None,
        "gaze_available": series is not None,
        "hitbox_margin_px": margin,
        "trials": items,
        "summary": summary,
    }
