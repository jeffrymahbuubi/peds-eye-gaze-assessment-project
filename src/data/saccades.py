"""Saccade detection by velocity threshold (I-VT) on the device-rate gaze samples
(SPEC-compass-task-flow.md 4D.5, HD7).

Why not amplitude over the gap between two vendor fixations: at the device rate
that gap is about one sample, so a velocity from it is degenerate. Why not the
textbook 30 deg/s on raw samples: the noise inside a fixation on this device is
too large for it (measured raw sample-to-sample velocity inside vendor fixations:
median 52, 95th percentile 203 deg/s). So the positions are median-filtered, the
velocity is a central difference over a short span, and the threshold is 50 deg/s.
Everything is defined in milliseconds, so the filter widths follow the measured
sample rate: 150 Hz gives a median of 5 samples and a +-3 sample difference, 60 Hz
gives 3 and +-1.

Consequence, to be stated wherever the number is shown: the peak velocity is a
*smoothed* peak. A ~40 ms difference window attenuates it (median 70 to 75 deg/s on
~3 deg saccades against 200+ physiological), so it is comparable across children
only on the same device and sample rate.

Pure and Qt-free: the caller supplies ``(t_s, x, y, valid)`` samples with ``x``/``y``
normalized to the tracked monitor, and a :class:`~.report_geometry.Geometry`.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .report_geometry import Geometry


@dataclass(frozen=True)
class IvtParams:
    threshold_deg_s: float = 50.0  # HD7; the textbook 30 fails on this device's noise
    min_samples: int = 2  # consecutive samples at or above the threshold
    min_amplitude_deg: float = 0.5
    median_ms: float = 33.0  # position pre-filter, a running median
    velocity_span_ms: float = 20.0  # central difference reaches this far each side
    max_gap_ms: float = 75.0  # a longer gap between samples (a pause, a dropout) is a break

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Saccade:
    onset_s: float  # device TIME of the first sample at or above the threshold
    offset_s: float  # device TIME of the last
    amplitude_deg: float
    peak_velocity_deg_s: float  # the smoothed peak (see the module docstring)
    mean_velocity_deg_s: float  # amplitude over the run's duration, one sample included


DEFAULT_IVT = IvtParams()


def filter_widths(dt_s: float, params: IvtParams = DEFAULT_IVT) -> tuple[int, int]:
    """``(m, k)``: the running-median width (odd, in samples) and the central
    difference reach (samples each side) for a sample period ``dt_s``."""
    dt_ms = dt_s * 1000.0
    m = max(1, round(params.median_ms / dt_ms))
    if m % 2 == 0:
        m += 1
    k = max(1, round(params.velocity_span_ms / dt_ms))
    return m, k


def split_segments(
    samples: Sequence[tuple[float, float, float, bool]], max_gap_s: float
) -> list[list[tuple[float, float, float]]]:
    """Runs of consecutive valid samples. An invalid sample, or a gap longer than
    ``max_gap_s`` between two samples, ends a run: a velocity is never computed
    across one (blinks, validity drops, a pause)."""
    segments: list[list[tuple[float, float, float]]] = []
    current: list[tuple[float, float, float]] = []
    for t, x, y, valid in samples:
        if not valid:
            if current:
                segments.append(current)
                current = []
            continue
        if current and t - current[-1][0] > max_gap_s:
            segments.append(current)
            current = []
        current.append((t, x, y))
    if current:
        segments.append(current)
    return segments


def median_period_s(segments: Sequence[Sequence[tuple[float, float, float]]]) -> float | None:
    """Median sample period over every pair of neighbours inside a segment."""
    diffs = [b[0] - a[0] for seg in segments for a, b in zip(seg, seg[1:], strict=False)]
    diffs = [d for d in diffs if d > 0]
    return statistics.median(diffs) if diffs else None


def _running_median(values: list[float], half: int) -> list[float]:
    """Median over ``2 * half + 1`` neighbours; the window shrinks symmetrically
    at both ends so it always has an odd count."""
    n = len(values)
    out = []
    for i in range(n):
        h = min(half, i, n - 1 - i)
        window = sorted(values[i - h : i + h + 1])
        out.append(window[h])
    return out


def detect_saccades(
    samples: Sequence[tuple[float, float, float, bool]],
    geometry: Geometry,
    params: IvtParams = DEFAULT_IVT,
) -> list[Saccade]:
    """I-VT saccades in ``samples`` (``(t_s, x, y, valid)``, x/y monitor-normalized).

    Returns ``[]`` for no saccade *and* for a geometry that cannot give degrees;
    the caller checks ``geometry.has_angles`` first when the two must differ.
    """
    if not geometry.has_angles:
        return []
    segments = split_segments(samples, params.max_gap_ms / 1000.0)
    dt = median_period_s(segments)
    if dt is None:
        return []
    m, k = filter_widths(dt, params)
    found: list[Saccade] = []
    for seg in segments:
        found.extend(_segment_saccades(seg, geometry, params, m, k, dt))
    return found


def _segment_saccades(
    seg: list[tuple[float, float, float]],
    geometry: Geometry,
    params: IvtParams,
    m: int,
    k: int,
    dt: float,
) -> list[Saccade]:
    n = len(seg)
    if n < 2:
        return []
    times = [s[0] for s in seg]
    xs = _running_median([s[1] for s in seg], m // 2)
    ys = _running_median([s[2] for s in seg], m // 2)

    velocity = [0.0] * n
    for i in range(n):
        a, b = max(0, i - k), min(n - 1, i + k)
        if b > a and times[b] > times[a]:
            angle = geometry.angle_deg((xs[a], ys[a]), (xs[b], ys[b])) or 0.0
            velocity[i] = angle / (times[b] - times[a])

    saccades: list[Saccade] = []
    i = 0
    while i < n:
        if velocity[i] < params.threshold_deg_s:
            i += 1
            continue
        first = i
        while i < n and velocity[i] >= params.threshold_deg_s:
            i += 1
        last = i - 1
        if last - first + 1 < params.min_samples:
            continue
        a, b = max(0, first - k), min(n - 1, last + k)
        amplitude = geometry.angle_deg((xs[a], ys[a]), (xs[b], ys[b])) or 0.0
        if amplitude < params.min_amplitude_deg:
            continue
        duration = times[last] - times[first] + dt
        saccades.append(
            Saccade(
                onset_s=times[first],
                offset_s=times[last],
                amplitude_deg=amplitude,
                peak_velocity_deg_s=max(velocity[first : last + 1]),
                mean_velocity_deg_s=amplitude / duration,
            )
        )
    return saccades


def window_saccades(
    saccades: Sequence[Saccade], clock_offset_ns: int, start_ns: int, end_ns: int
) -> list[Saccade]:
    """The saccades whose onset falls in ``[start_ns, end_ns)`` on the host clock.
    Device time becomes host time with ``metadata.raw_clock_offset_ns``:
    ``t_ns = clock_offset_ns + TIME * 1e9`` (4D.4-5)."""
    return [
        s
        for s in saccades
        if start_ns <= clock_offset_ns + round(s.onset_s * 1e9) < end_ns
    ]
