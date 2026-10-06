"""Drawing data for the report's Target Map (SPEC-compass-task-flow.md 4D.5, 4D.7):
gaze paths, the heat map and the map marks, all in **canvas-normalized** coordinates
so the widget paints them over the target positions without conversion. Gaze comes in
monitor-normalized and goes through :meth:`Geometry.monitor_to_canvas_norm`; a point
may land outside [0, 1] (the child looked off the canvas), and is kept, to be clipped
at draw time. Pure and Qt-free.
"""

from __future__ import annotations

import csv
import math
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .recorder import TARGET_TRACK_FILENAME
from .report_eye import GazeFrame
from .report_geometry import Geometry


@dataclass(frozen=True)
class PathParams:
    min_step_deg: float = 0.15  # keep a point this far from the last kept ...
    min_step_ms: float = 100.0  # ... or this long after it
    split_gap_ms: float = 150.0  # a longer gap, or an invalid frame, starts a new polyline
    max_points: int = 400  # per trial, thinned by a uniform stride beyond this

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeatParams:
    width: int = 96
    height: int = 54
    sigma_deg: float = 1.0  # ~ the device's accuracy plus fixation dispersion; one knob to retune
    weight_cap_ms: float = 100.0  # a sample counts for the time to the next one, at most this

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_PATH = PathParams()
DEFAULT_HEAT = HeatParams()
TRACK_MAX_POINTS = 100  # a moving target's drawn track, per trial


# -- gaze path -------------------------------------------------------------------


def _uniform_indices(n: int, cap: int) -> list[int]:
    """``cap`` indices spread evenly over ``range(n)``, first and last included."""
    if n <= cap:
        return list(range(n))
    return sorted({round(i * (n - 1) / (cap - 1)) for i in range(cap)})


def _thin(segment: Sequence[GazeFrame], geometry: Geometry, params: PathParams) -> list[GazeFrame]:
    """Radial decimation of one polyline: keep a frame when it is at least
    ``min_step_deg`` from the last kept one or ``min_step_ms`` after it; always keep
    the first and the last."""
    kept = [segment[0]]
    min_ns = round(params.min_step_ms * 1e6)
    for f in segment[1:-1]:
        last = kept[-1]
        step = geometry.angle_deg((last.x, last.y), (f.x, f.y)) or 0.0
        if step >= params.min_step_deg or f.t_ns - last.t_ns >= min_ns:
            kept.append(f)
    if len(segment) > 1:
        kept.append(segment[-1])
    return kept


def gaze_path(
    window: Sequence[GazeFrame], geometry: Geometry, params: PathParams = DEFAULT_PATH
) -> list[list[list[float]]]:
    """One trial's gaze as polylines ``[[ [x, y], ... ], ...]`` in canvas-normalized
    coordinates. Valid frames only; a new polyline starts at an invalid frame or a
    gap over ``split_gap_ms``. Thinned as in :func:`_thin`, then capped to
    ``max_points`` in total by a uniform stride. Frames are expected de-duplicated."""
    visual = geometry.for_visuals()
    gap_ns = round(params.split_gap_ms * 1e6)
    segments: list[list[GazeFrame]] = []
    current: list[GazeFrame] = []
    for f in window:
        if not f.valid:
            if current:
                segments.append(current)
                current = []
            continue
        if current and f.t_ns - current[-1].t_ns > gap_ns:
            segments.append(current)
            current = []
        current.append(f)
    if current:
        segments.append(current)
    thinned = [_thin(seg, visual, params) for seg in segments]
    flat = [(si, f) for si, seg in enumerate(thinned) for f in seg]
    keep = _uniform_indices(len(flat), params.max_points)
    out: list[list[list[float]]] = []
    last_seg = -1
    for i in keep:
        si, f = flat[i]
        if si != last_seg:
            out.append([])
            last_seg = si
        cx, cy = geometry.monitor_to_canvas_norm(f.x, f.y)
        out[-1].append([round(cx, 4), round(cy, 4)])
    return out


# -- heat map --------------------------------------------------------------------


def heat_sigma_bins(geometry: Geometry, params: HeatParams = DEFAULT_HEAT) -> tuple[float, float]:
    """The blur's sigma in bins along x and y: ``sigma_deg`` in mm on the screen,
    over the canvas size in mm, times the bin count. The two differ with the canvas
    aspect ratio and the bin grid (96x54 over any canvas)."""
    visual = geometry.for_visuals()
    size = visual.canvas_mm() or (visual.phys_w_mm, visual.phys_h_mm)
    mm = params.sigma_deg * visual.mm_per_deg
    return mm / size[0] * params.width, mm / size[1] * params.height


def _blur_axis(line: list[float], kernel: list[float]) -> list[float]:
    r = len(kernel) // 2
    n = len(line)
    out = [0.0] * n
    for i, v in enumerate(line):
        if v == 0.0:
            continue
        for j, w in enumerate(kernel):
            k = i + j - r
            if 0 <= k < n:
                out[k] += v * w
    return out


def _kernel(sigma_bins: float) -> list[float]:
    if sigma_bins <= 0:
        return [1.0]
    r = max(1, math.ceil(3 * sigma_bins))
    weights = [math.exp(-(d * d) / (2 * sigma_bins**2)) for d in range(-r, r + 1)]
    total = sum(weights)
    return [w / total for w in weights]


def blur_grid(grid: list[list[float]], sigma_x: float, sigma_y: float) -> list[list[float]]:
    """Separable Gaussian blur of ``grid[row][col]``, radius 3 sigma, the kernel
    normalized: mass is preserved except what the grid's edge cuts off."""
    kx, ky = _kernel(sigma_x), _kernel(sigma_y)
    rows = [_blur_axis(row, kx) for row in grid]
    height, width = len(rows), len(rows[0]) if rows else 0
    columns = [_blur_axis([rows[y][x] for y in range(height)], ky) for x in range(width)]
    return [[columns[x][y] for x in range(width)] for y in range(height)]


def heat_grid(
    windows: Sequence[tuple[Sequence[GazeFrame], int]],
    geometry: Geometry,
    params: HeatParams = DEFAULT_HEAT,
) -> tuple[list[list[float]], float, float]:
    """``(blurred grid, on_canvas_s, off_canvas_s)``, the grid not yet normalized.

    ``windows`` is one ``(frames, end_ns)`` per trial: only gaze inside a trial window
    counts (not the blank between trials). Each valid frame weighs the time to the next
    frame of its window (the window end for the last), at most ``weight_cap_ms``. A frame
    off the canvas adds to ``off_canvas_s`` and to no bin.
    """
    grid = [[0.0] * params.width for _ in range(params.height)]
    cap_s = params.weight_cap_ms / 1000.0
    on_s = off_s = 0.0
    for frames, end_ns in windows:
        for i, f in enumerate(frames):
            if not f.valid:
                continue
            nxt = frames[i + 1].t_ns if i + 1 < len(frames) else end_ns
            weight = min(max(nxt - f.t_ns, 0) / 1e9, cap_s)
            cx, cy = geometry.monitor_to_canvas_norm(f.x, f.y)
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                off_s += weight
                continue
            col = min(int(cx * params.width), params.width - 1)
            row = min(int(cy * params.height), params.height - 1)
            grid[row][col] += weight
            on_s += weight
    if on_s > 0:
        grid = blur_grid(grid, *heat_sigma_bins(geometry, params))
    return grid, on_s, off_s


def heat_map(
    windows: Sequence[tuple[Sequence[GazeFrame], int]],
    geometry: Geometry,
    params: HeatParams = DEFAULT_HEAT,
) -> dict[str, Any]:
    """The report's heat map: the blurred, time-weighted gaze density over canvas-
    normalized [0, 1]^2, scaled so the maximum is 1 and rounded to 3 decimals.

    ``data`` is row-major ``width * height`` values, or ``[]`` (with ``empty``) when no
    gaze fell on the canvas. ``off_canvas_share`` is the share of the valid gaze *time*
    that fell outside it; None when there was no valid gaze at all.
    """
    grid, on_s, off_s = heat_grid(windows, geometry, params)
    total = on_s + off_s
    sigma_x, sigma_y = heat_sigma_bins(geometry, params)
    out: dict[str, Any] = {
        "w": params.width,
        "h": params.height,
        "sigma_deg": params.sigma_deg,
        "sigma_bins": [round(sigma_x, 3), round(sigma_y, 3)],
        "total_s": round(on_s, 3),
        "off_canvas_share": round(off_s / total, 4) if total > 0 else None,
        "empty": on_s <= 0,
        "data": [],
    }
    if on_s > 0:
        peak = max(max(row) for row in grid)
        out["data"] = [round(v / peak, 3) for row in grid for v in row]
    return out


# -- map marks and the moving target's track ----------------------------------------


def map_marks(
    trials: Sequence[dict[str, Any]], geometry: Geometry, *, moving: bool = False
) -> dict[str, Any]:
    """The Target Map's marks: one per trial position and outcome.

    A trial's mark sits at its ``target`` ``x, y`` -- or, when ``moving``, at ``end_x,
    end_y`` (where the target was when the trial ended; the start position, with a note,
    for a folder that lacks it). Trials whose positions lie within half a radius of each
    other share a spot (a 3x3 grid with 18 trials reuses its cells): each distinct outcome
    there is drawn once, side by side, labelled with its trial numbers (``"3, 9"``).
    Returns ``{"marks": [...], "note": str | None}``; a mark is ``{x, y, r, outcome,
    trials, label}`` with ``r`` the radius in canvas-x units.
    """
    aspect = geometry.aspect or 1.0
    note = None
    spots: list[dict[str, Any]] = []
    for t in trials:
        target = t["target"]
        x, y = target["x"], target["y"]
        if moving:
            if target.get("end_x") is not None and target.get("end_y") is not None:
                x, y = target["end_x"], target["end_y"]
            else:
                note = "End positions were not recorded; marks are at the start position."
        r = target.get("radius_norm_x") or 0.0
        for spot in spots:
            dist = math.hypot(x - spot["x"], (y - spot["y"]) / aspect)
            if dist <= 0.5 * max(r, spot["r"]):
                spot["members"].append((t["trial"], t["outcome"]))
                break
        else:
            spots.append({"x": x, "y": y, "r": r, "members": [(t["trial"], t["outcome"])]})
    marks: list[dict[str, Any]] = []
    for spot in spots:
        outcomes = list(dict.fromkeys(o for _, o in spot["members"]))
        for i, outcome in enumerate(outcomes):
            numbers = sorted(n for n, o in spot["members"] if o == outcome)
            shift = (i - (len(outcomes) - 1) / 2) * 0.6 * spot["r"]
            marks.append(
                {
                    "x": round(spot["x"] + shift, 5),
                    "y": round(spot["y"], 5),
                    "r": round(spot["r"], 5),
                    "outcome": outcome,
                    "trials": numbers,
                    "label": ", ".join(str(n) for n in numbers),
                }
            )
    return {"marks": marks, "note": note}


def load_target_track(session_dir: str | Path) -> list[tuple[int, int, float, float]] | None:
    """``target_track.csv`` as ``(t_ns, trial, x, y)`` sorted by time; ``None`` when
    there is none (every task but follow_moving, and older folders)."""
    path = Path(session_dir) / TARGET_TRACK_FILENAME
    if not path.exists():
        return None
    rows: list[tuple[int, int, float, float]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append(
                    (int(row["t_ns"]), int(row["trial"]), float(row["x"]), float(row["y"]))
                )
            except (KeyError, TypeError, ValueError):
                continue
    rows.sort(key=lambda r: r[0])
    return rows


def trial_track(
    track: Sequence[tuple[int, int, float, float]],
    trial_id: int,
    onset_ns: int,
    end_ns: int,
    cap: int = TRACK_MAX_POINTS,
) -> list[list[float]]:
    """The moving target's ``[[x, y], ...]`` during one trial. A trial re-presented
    after a pause repeats its id, so the rows are windowed on the trial's own
    ``[onset, end]``, not just matched by id; thinned to ``cap`` points."""
    times = [r[0] for r in track]
    rows = [
        r
        for r in track[bisect_left(times, onset_ns) : bisect_right(times, end_ns)]
        if r[1] == trial_id
    ]
    return [[round(rows[i][2], 4), round(rows[i][3], 4)] for i in _uniform_indices(len(rows), cap)]
