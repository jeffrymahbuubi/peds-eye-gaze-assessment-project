"""Gaze, fixation and pupil readers for the per-test report
(SPEC-compass-task-flow.md 4D.5). Pure and Qt-free.

Two clocks, one rule: ``gaze_stream.csv`` is stamped with the host clock, the same
one as ``trials.csv`` (fixations, the gaze path and the heat map use it directly);
``all_gaze.csv`` has only device time, which ``metadata.raw_clock_offset_ns`` maps
onto the host clock (saccades and pupil).
"""

from __future__ import annotations

import csv
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, NamedTuple

from .analysis_export import ALL_GAZE_FILENAME, base_column
from .recorder import POINTER_STREAM_FILENAME
from .report_geometry import Geometry
from .report_util import to_float, to_int

# -- gaze_stream.csv ----------------------------------------------------------


class GazeFrame(NamedTuple):
    t_ns: int
    x: float  # monitor-normalized
    y: float
    valid: bool
    fid: int | None  # fixation id (FPOGID)
    dur_s: float | None  # cumulative fixation duration so far (FPOGD)


def load_gaze_frames(session_dir: str | Path) -> list[GazeFrame]:
    """Every ``gaze_stream.csv`` row as a :class:`GazeFrame`, sorted by time and
    de-duplicated on ``t_ns`` (the first of equal stamps wins): at a loop rate above
    the device rate the same sample is written again, and counting it twice would
    double its weight. ``[]`` when the file is missing."""
    path = Path(session_dir) / "gaze_stream.csv"
    if not path.exists():
        return []
    frames: list[GazeFrame] = []
    seen: set[int] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            t_ns = to_int(row.get("t_ns"))
            x, y = to_float(row.get("x")), to_float(row.get("y"))
            if t_ns is None or x is None or y is None or t_ns in seen:
                continue
            seen.add(t_ns)
            frames.append(
                GazeFrame(
                    t_ns, x, y, row.get("valid") == "1",
                    to_int(row.get("fixation_id")), to_float(row.get("fix_duration_s")),
                )
            )
    frames.sort(key=lambda f: f.t_ns)
    return frames


def load_pointer_frames(session_dir: str | Path, geometry: Geometry) -> list[GazeFrame]:
    """A Mouse run's ``pointer_stream.csv`` as :class:`GazeFrame` objects, so the gaze-path code
    (smoothing, thinning, the trial window) serves the mouse path unchanged
    (SPEC-input-selection-and-follow.md 4.5). The file is canvas-normalized and the frames
    are **monitor**-normalized like gaze, so a pointer position outside the canvas stays
    outside it through :meth:`Geometry.monitor_to_canvas_norm`. Sorted by time and
    de-duplicated on ``t_ns``; ``[]`` when the file is missing."""
    path = Path(session_dir) / POINTER_STREAM_FILENAME
    if not path.exists():
        return []
    frames: list[GazeFrame] = []
    seen: set[int] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            t_ns = to_int(row.get("t_ns"))
            x, y = to_float(row.get("x")), to_float(row.get("y"))
            if t_ns is None or x is None or y is None or t_ns in seen:
                continue
            seen.add(t_ns)
            mx, my = geometry.canvas_to_monitor_norm(x, y)
            frames.append(GazeFrame(t_ns, mx, my, row.get("valid") == "1", None, None))
    frames.sort(key=lambda f: f.t_ns)
    return frames


class FrameIndex:
    """Frames plus their times, so a trial window is a bisect, not a scan."""

    def __init__(self, frames: Sequence[GazeFrame]) -> None:
        self.frames = list(frames)
        self._times = [f.t_ns for f in self.frames]

    def window(self, start_ns: int, end_ns: int) -> list[GazeFrame]:
        """Frames with ``start_ns <= t_ns <= end_ns``."""
        return self.frames[bisect_left(self._times, start_ns) : bisect_right(self._times, end_ns)]


# -- fixations (the vendor FPOGID definition) ---------------------------------


class Fixation(NamedTuple):
    start_ns: int
    x: float  # canvas-normalized mean position
    y: float
    dur_ms: float


def trial_fixations(
    window: Sequence[GazeFrame], onset_ns: int, end_ns: int, geometry: Geometry
) -> list[Fixation]:
    """Fixations of one trial, assigned by where they *start*.

    For each fixation id seen on a valid frame of the window: its last frame in the
    window gives ``dur = FPOGD`` there (cumulative, so a fixation still running at
    the trial end is clipped to it for free) and ``start = t - dur``. It belongs to
    the trial when ``onset <= start < end``: one that began before the onset is the
    previous trial's. Position is the mean of its frames, canvas-normalized.
    Sorted by start. Frames are expected de-duplicated (:func:`load_gaze_frames`).
    """
    by_id: dict[int, list[GazeFrame]] = {}
    for f in window:
        if f.valid and f.fid is not None:
            by_id.setdefault(f.fid, []).append(f)
    found: list[Fixation] = []
    for frames in by_id.values():
        last = frames[-1]
        if last.dur_s is None:
            continue
        start_ns = last.t_ns - round(last.dur_s * 1e9)
        if not onset_ns <= start_ns < end_ns:
            continue
        points = [geometry.monitor_to_canvas_norm(f.x, f.y) for f in frames]
        found.append(
            Fixation(
                start_ns,
                sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points),
                last.dur_s * 1000.0,
            )
        )
    found.sort(key=lambda fx: fx.start_ns)
    return found


# -- all_gaze.csv (device rate) -----------------------------------------------


class RawSample(NamedTuple):
    t_s: float  # device TIME, seconds from the first record
    x: float  # BPOGX, monitor-normalized
    y: float
    valid: bool  # BPOGV
    pupil_l: float  # LPMM, mm
    pupil_l_ok: bool  # LPMMV
    pupil_r: float
    pupil_r_ok: bool


_RAW_COLUMNS = ("TIME", "BPOGX", "BPOGY", "BPOGV", "LPMM", "LPMMV", "RPMM", "RPMMV")


def load_raw_samples(session_dir: str | Path) -> list[RawSample] | None:
    """The device-rate samples of ``all_gaze.csv``, only the columns the report
    reads. ``None`` when the file is missing or lacks the gaze columns."""
    path = Path(session_dir) / ALL_GAZE_FILENAME
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return None
        index = {}
        for i, name in enumerate(header):
            index.setdefault(base_column(name), i)
        if not all(c in index for c in _RAW_COLUMNS[:4]):
            return None
        cols = [index.get(c, -1) for c in _RAW_COLUMNS]
        need = max(cols[:4]) + 1
        out: list[RawSample] = []
        for row in reader:
            if len(row) < need:
                continue
            vals = [to_float(row[c]) if 0 <= c < len(row) else None for c in cols]
            if vals[0] is None or vals[1] is None or vals[2] is None:
                continue
            out.append(
                RawSample(
                    vals[0], vals[1], vals[2], vals[3] == 1.0,
                    vals[4] or 0.0, vals[5] == 1.0, vals[6] or 0.0, vals[7] == 1.0,
                )
            )
    return out


def sample_period_s(samples: Sequence[RawSample], max_gap_s: float = 0.075) -> float | None:
    """Median gap between neighbouring samples, ignoring gaps over ``max_gap_s``
    (a pause or dropout is not the sample period)."""
    diffs = [
        b.t_s - a.t_s
        for a, b in zip(samples, samples[1:], strict=False)
        if 0 < b.t_s - a.t_s <= max_gap_s
    ]
    return statistics.median(diffs) if diffs else None


# -- pupil ----------------------------------------------------------------------


@dataclass(frozen=True)
class PupilParams:
    min_mm: float = 1.5
    max_mm: float = 9.0
    blink_mask_ms: float = 100.0  # drop valid samples this close to an invalid one
    baseline_ms: float = 300.0  # pre-onset window; the shorter of this and the ITI
    min_baseline_coverage: float = 0.5  # of the expected sample count

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_PUPIL = PupilParams()


def pupil_series(
    samples: Sequence[RawSample], clock_offset_ns: int, params: PupilParams = DEFAULT_PUPIL
) -> tuple[list[int], list[float]]:
    """``(times_ns, mm)`` of the usable pupil samples, host-clock aligned.

    Usable = both eyes valid and each within ``[min_mm, max_mm]``; the value is the
    mean of the two (L and R differ by ~0.2 mm on this device, and mixing one-eye and
    two-eye samples would make steps). A usable sample within ``blink_mask_ms`` of any
    unusable one is dropped too: the pupil is unreliable around a blink.
    """
    lo, hi = params.min_mm, params.max_mm
    times: list[int] = []
    values: list[float] = []
    bad: list[int] = []
    for s in samples:
        t_ns = clock_offset_ns + round(s.t_s * 1e9)
        if s.pupil_l_ok and s.pupil_r_ok and lo <= s.pupil_l <= hi and lo <= s.pupil_r <= hi:
            times.append(t_ns)
            values.append((s.pupil_l + s.pupil_r) / 2.0)
        else:
            bad.append(t_ns)
    if not bad:
        return times, values
    mask_ns = round(params.blink_mask_ms * 1e6)
    kept_t: list[int] = []
    kept_v: list[float] = []
    for t_ns, v in zip(times, values, strict=True):
        j = bisect_left(bad, t_ns)
        near = (j < len(bad) and bad[j] - t_ns <= mask_ns) or (
            j > 0 and t_ns - bad[j - 1] <= mask_ns
        )
        if not near:
            kept_t.append(t_ns)
            kept_v.append(v)
    return kept_t, kept_v


def trial_pupil(
    times: Sequence[int],
    values: Sequence[float],
    onset_ns: int,
    end_ns: int,
    *,
    sample_dt_s: float | None,
    iti_ms: float | None,
    params: PupilParams = DEFAULT_PUPIL,
) -> dict[str, float | None]:
    """``{mean_mm, baseline_mm, change_mm, change_pct}`` for one trial window.

    ``mean`` is over ``[onset, end]``; the baseline is the mean over the
    ``[onset - w, onset)`` window, ``w = min(baseline_ms, ITI)`` (the blank between
    trials; ``baseline_ms`` when the ITI is unknown, no baseline when it is 0), and is None unless at least ``min_baseline_coverage`` of the samples that
    window should hold survive (so a first trial with no pre-roll has none). The change
    is None when either is, never a made-up 0.
    """
    out: dict[str, float | None] = {
        "mean_mm": None, "baseline_mm": None, "change_mm": None, "change_pct": None
    }
    lo, hi = bisect_left(times, onset_ns), bisect_right(times, end_ns)
    if hi > lo:
        out["mean_mm"] = sum(values[lo:hi]) / (hi - lo)
    window_ms = params.baseline_ms if iti_ms is None else min(params.baseline_ms, iti_ms)
    if window_ms > 0 and sample_dt_s:
        b_lo = bisect_left(times, onset_ns - round(window_ms * 1e6))
        b_hi = bisect_left(times, onset_ns)
        expected = window_ms / 1000.0 / sample_dt_s
        n = b_hi - b_lo
        if n > 0 and n >= params.min_baseline_coverage * expected:
            out["baseline_mm"] = sum(values[b_lo:b_hi]) / n
    if out["mean_mm"] is not None and out["baseline_mm"] is not None:
        out["change_mm"] = out["mean_mm"] - out["baseline_mm"]
        out["change_pct"] = out["change_mm"] / out["baseline_mm"] * 100.0
    return out
