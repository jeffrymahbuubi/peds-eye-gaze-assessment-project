"""Look-back to the effect and the waiting-phase distribution of Choice-making
(SPEC-scene-cause-effect-task.md 4.6, H10, H11, S7, W4, N2). Pure and Qt-free, like the rest of
``src/data``; the run folder is read by :mod:`report_choice`, which feeds this module.

**Look-back.** After a selection (or a timeout) the chosen object's effect plays in the scene,
and the child's gaze, which was on a button at the screen edge, can come back to it. Per trial,
over the window ``W = [EFFECT_START, EFFECT_END + 500 ms]``:

* the AOI is the object's box (scene fractions, from ``box_at``) mapped to the canvas and padded by
  1 deg on each side. For an effect that carries the object out of its idle box (Bike, Cloud) the
  box is the object's *at each sample's time* (N2), so ``box_at(object_id, elapsed_ms)`` takes the
  time since the effect started on the canvas clock (a pause is not counted);
* ``dwell`` is the sum of the valid samples' intervals inside the AOI; ``lookback`` is yes when it
  is at least 100 ms (always yes / no, W4); ``latency`` is the time from the effect start to the
  first valid sample inside; ``fraction`` is the dwell over the length of W;
* ``valid_fraction`` is the share of the window's samples that were valid, so a trial with gaze
  loss is not read as "did not look". A window with no sample at all gives ``None`` everywhere
  (nothing was recorded: a dash, never a 0).

**Waiting phase** (S7). Over ``[PROMPT_END, selection or timeout]`` the valid time on the scene,
on the buttons and elsewhere (the rest of the canvas, and off it, so the three always add up to the
valid time).

A sample's *interval* is the time to the next sample of the stream, at most ``max_interval_ms``
(a gap in the records is not gaze), cut at the end of the window and at the start of a pause. The
samples are canvas-normalized; :func:`samples_from_raw` / :func:`samples_from_frames` turn the
device-rate ``all_gaze.csv`` and the host-rate streams into them.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, NamedTuple

from ..tasks.choice_layout import (
    GRID_COLS,
    N_BUTTONS,
    SCENE_COLS,
    SCENE_FIRST_COL,
    board_geometry,
    button_rect,
)
from .report_geometry import Geometry

Box = tuple[float, float, float, float]  # x0, y0, x1, y1
BoxAt = Callable[[str, float], Box]  # (object_id, elapsed_ms) -> box in scene fractions

# The scene is columns 1-5 of the 7 x 5 board, the full canvas height (4.2).
SCENE_X0 = SCENE_FIRST_COL / GRID_COLS
SCENE_W = SCENE_COLS / GRID_COLS
SCENE_BOX: Box = (SCENE_X0, 0.0, SCENE_X0 + SCENE_W, 1.0)  # in canvas fractions

# The idle object regions of the table in SPEC 4.2 (scene fractions), equal to the placeholder
# scene's boxes in ``choice_scene``. The report takes its boxes from the scene manifest
# (:func:`report_choice.default_box_at`); these remain for tests and as a fixed reference.
IDLE_BOXES: dict[str, Box] = {
    "balloons": (0.79, 0.03, 0.99, 0.28),
    "rainbow": (0.45, 0.12, 0.77, 0.36),
    "seesaw": (0.51, 0.33, 0.74, 0.52),
    "apples": (0.05, 0.08, 0.45, 0.72),
    "cloud": (0.43, 0.00, 0.83, 0.14),
    "bubbles": (0.47, 0.65, 0.59, 0.95),
    "bike": (0.36, 0.42, 0.47, 0.63),
    "swing": (0.00, 0.51, 0.29, 0.97),
}


def static_box_provider(boxes: Mapping[str, Box]) -> BoxAt:
    """A ``box_at`` for objects that stay where they are: each object's one box, at any time."""

    def box_at(object_id: str, _elapsed_ms: float) -> Box:
        return boxes[object_id]

    return box_at


class Sample(NamedTuple):
    """One gaze (or pointer) sample, canvas-normalized."""

    t_ns: int
    x: float
    y: float
    valid: bool


class SampleSeries:
    """Samples sorted by time, with their times for bisecting."""

    def __init__(self, samples: Sequence[Sample]) -> None:
        self.samples = sorted(samples, key=lambda s: s.t_ns)
        self.times = [s.t_ns for s in self.samples]

    def __len__(self) -> int:
        return len(self.samples)


def samples_from_frames(frames: Sequence[Any], geometry: Geometry) -> list[Sample]:
    """``gaze_stream.csv`` frames (host clock, monitor-normalized) or a Mouse run's
    ``pointer_stream.csv`` frames as canvas-normalized samples."""
    return [Sample(f.t_ns, *geometry.monitor_to_canvas_norm(f.x, f.y), f.valid) for f in frames]


def samples_from_raw(raw: Sequence[Any], offset_ns: int, geometry: Geometry) -> list[Sample]:
    """The device-rate ``all_gaze.csv`` samples (device ``TIME`` in seconds) on the host clock."""
    return [
        Sample(offset_ns + round(s.t_s * 1e9), *geometry.monitor_to_canvas_norm(s.x, s.y), s.valid)
        for s in raw
    ]


@dataclass(frozen=True)
class LookbackParams:
    pad_deg: float = 1.0  # H10: the AOI is the object's box plus this on each side
    after_ms: float = 500.0  # H10: W closes this long after the effect ends
    min_dwell_ms: float = 100.0  # H11: the dwell that makes a look-back "yes"
    max_interval_ms: float = 100.0  # a sample counts for the time to the next one, at most this

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_LOOKBACK = LookbackParams()


class Pauses:
    """The spans of time the run was paused (host clock, ns); they are not part of any window."""

    def __init__(self, spans: Sequence[tuple[int, int]] = ()) -> None:
        self.spans = sorted(spans)
        self._starts = [s for s, _ in self.spans]

    def overlap(self, start_ns: int, end_ns: int) -> int:
        """Paused time inside ``[start_ns, end_ns]``."""
        return sum(max(0, min(end_ns, e) - max(start_ns, s)) for s, e in self.spans)

    def contains(self, t_ns: int) -> bool:
        return any(s <= t_ns < e for s, e in self.spans)

    def next_start(self, t_ns: int) -> int | None:
        """The start of the first pause after ``t_ns``."""
        k = bisect_right(self._starts, t_ns)
        return self._starts[k] if k < len(self._starts) else None


NO_PAUSES = Pauses()


# -- geometry ------------------------------------------------------------------------------------


def scene_box_to_canvas(box: Box) -> Box:
    """A box in scene fractions as canvas fractions (the scene is columns 1-5, full height)."""
    x0, y0, x1, y1 = box
    return (SCENE_X0 + x0 * SCENE_W, y0, SCENE_X0 + x1 * SCENE_W, y1)


def pad_norm(geometry: Geometry, pad_deg: float) -> tuple[float, float] | None:
    """``pad_deg`` of visual angle as canvas fractions ``(along x, along y)``: the millimetres
    that angle spans at the viewing distance over the canvas's size in millimetres. ``None``
    unless the run recorded the monitor's physical size, the distance and the canvas (a degree is
    never guessed)."""
    size_mm = geometry.canvas_mm()
    if size_mm is None or not geometry.distance_mm:
        return None
    mm = geometry.distance_mm * math.tan(math.radians(pad_deg))
    return mm / size_mm[0], mm / size_mm[1]


def padded(box: Box, pad: tuple[float, float]) -> Box:
    return (box[0] - pad[0], box[1] - pad[1], box[2] + pad[0], box[3] + pad[1])


def aoi_at(box_at: BoxAt, object_id: str, elapsed_ms: float, pad: tuple[float, float]) -> Box:
    """The padded AOI, in canvas fractions, of ``object_id`` ``elapsed_ms`` into its effect."""
    return padded(scene_box_to_canvas(box_at(object_id, elapsed_ms)), pad)


def inside(box: Box, x: float, y: float) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


@dataclass(frozen=True)
class Regions:
    """The scene and the eight drawn buttons, as canvas fractions."""

    scene: Box
    buttons: tuple[Box, ...]

    def where(self, x: float, y: float) -> str:
        """``scene``, ``buttons`` or ``other`` (the empty cells, the gaps, off the canvas)."""
        if inside(self.scene, x, y):
            return "scene"
        return "buttons" if any(inside(b, x, y) for b in self.buttons) else "other"


def board_regions(geometry: Geometry, gap_px: float | None) -> Regions | None:
    """The scene and the buttons as the canvas drew them: the 7 x 5 board on the canvas's logical
    size with the run's cell gap (:func:`~src.tasks.choice_layout.board_geometry`, which also applies
    the cap, so a wide gap is the one the run used). ``None`` without the canvas size."""
    logical = geometry.canvas_logical_size()
    if logical is None:
        return None
    w, h = logical
    cells = board_geometry(w, h, gap_px)
    rects = []
    for slot in range(N_BUTTONS):
        x, y, bw, bh = button_rect(slot, w, h, cells)
        rects.append((x / w, y / h, (x + bw) / w, (y + bh) / h))
    return Regions(SCENE_BOX, tuple(rects))


# -- the measures --------------------------------------------------------------------------------


def _weighted(
    series: SampleSeries, start_ns: int, end_ns: int, params: LookbackParams, pauses: Pauses
) -> list[tuple[Sample, int]]:
    """The samples with ``start_ns <= t <= end_ns`` (none inside a pause) and each one's
    interval in ns (see the module docstring)."""
    cap = round(params.max_interval_ms * 1e6)
    lo, hi = bisect_left(series.times, start_ns), bisect_right(series.times, end_ns)
    out = []
    for i in range(lo, hi):
        sample = series.samples[i]
        if pauses.contains(sample.t_ns):
            continue
        following = series.times[i + 1] if i + 1 < len(series.times) else sample.t_ns
        limit = min(following - sample.t_ns, cap, end_ns - sample.t_ns)
        stop = pauses.next_start(sample.t_ns)
        if stop is not None:
            limit = min(limit, stop - sample.t_ns)
        out.append((sample, max(0, limit)))
    return out


@dataclass(frozen=True)
class EffectWindow:
    """One trial's effect, on the host clock."""

    object_id: str
    start_ns: int  # EFFECT_START
    end_ns: int  # EFFECT_END
    duration_ms: float | None = None  # the effect's own length; after it the object is back at rest


@dataclass(frozen=True)
class LookbackResult:
    lookback: bool | None = None
    latency_ms: float | None = None
    dwell_ms: float | None = None
    fraction: float | None = None
    valid_fraction: float | None = None
    n_samples: int = 0


def measure_lookback(
    series: SampleSeries,
    effect: EffectWindow,
    box_at: BoxAt,
    pad: tuple[float, float],
    params: LookbackParams = DEFAULT_LOOKBACK,
    pauses: Pauses = NO_PAUSES,
) -> LookbackResult:
    """The look-back measures of one trial (see the module docstring). ``pad`` is the AOI padding
    in canvas fractions (:func:`pad_norm`)."""
    end_ns = effect.end_ns + round(params.after_ms * 1e6)
    items = _weighted(series, effect.start_ns, end_ns, params, pauses)
    if not items:
        return LookbackResult()
    length_ms = (end_ns - effect.start_ns - pauses.overlap(effect.start_ns, end_ns)) / 1e6
    dwell_ns = 0
    n_valid = 0
    latency_ms = None
    for sample, interval in items:
        if not sample.valid:
            continue
        n_valid += 1
        # The effect's own clock: a pause does not run it.
        elapsed_ms = (sample.t_ns - effect.start_ns - pauses.overlap(effect.start_ns, sample.t_ns)) / 1e6
        at_ms = elapsed_ms if effect.duration_ms is None else min(elapsed_ms, effect.duration_ms)
        if inside(aoi_at(box_at, effect.object_id, at_ms, pad), sample.x, sample.y):
            dwell_ns += interval
            if latency_ms is None:
                latency_ms = elapsed_ms
    dwell_ms = dwell_ns / 1e6
    return LookbackResult(
        lookback=dwell_ms >= params.min_dwell_ms,
        latency_ms=latency_ms,
        dwell_ms=dwell_ms,
        fraction=min(1.0, dwell_ms / length_ms) if length_ms > 0 else None,
        valid_fraction=n_valid / len(items),
        n_samples=len(items),
    )


@dataclass(frozen=True)
class WaitResult:
    scene_ms: float | None = None
    buttons_ms: float | None = None
    other_ms: float | None = None
    valid_fraction: float | None = None
    n_samples: int = 0
    n_valid: int = 0


def measure_wait(
    series: SampleSeries,
    start_ns: int,
    end_ns: int,
    regions: Regions,
    params: LookbackParams = DEFAULT_LOOKBACK,
    pauses: Pauses = NO_PAUSES,
) -> WaitResult:
    """Where the valid gaze was between the prompt's end and the selection (or the timeout)."""
    items = _weighted(series, start_ns, end_ns, params, pauses)
    if not items:
        return WaitResult()
    spent = {"scene": 0, "buttons": 0, "other": 0}
    n_valid = 0
    for sample, interval in items:
        if sample.valid:
            n_valid += 1
            spent[regions.where(sample.x, sample.y)] += interval
    return WaitResult(
        scene_ms=spent["scene"] / 1e6,
        buttons_ms=spent["buttons"] / 1e6,
        other_ms=spent["other"] / 1e6,
        valid_fraction=n_valid / len(items),
        n_samples=len(items),
        n_valid=n_valid,
    )
