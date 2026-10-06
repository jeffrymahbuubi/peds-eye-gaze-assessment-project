"""Target size presets by visual angle (SPEC-target-size-and-motion-paths.md S4.1-S4.3).

A preset is a fixed target *diameter* in degrees of visual angle, converted to
pixels from the monitor's physical width and the configured eye-to-screen
distance (``app.viewing_distance_mm``) -- never from anything measured on the
child, so every subject on one monitor gets the identical pixel size, and the
*apparent* size stays the same across monitors.

Pure and Qt-free, like :mod:`src.engine.settings_profile`, so every rule here
is unit-testable headlessly. A QScreen is only ever touched through duck typing
in :func:`screen_scale`.

Pixels here are Qt *logical* px, because the canvas paints and hit-tests in
logical px: at 150 % Windows scale one logical px is 1.5 physical px, so the
millimetres-per-px used must be per logical px or the apparent size comes out
wrong (SPEC S4.1).
"""

from __future__ import annotations

import logging
import math
from typing import Any, NamedTuple

_log = logging.getLogger(__name__)

SIZE_PRESETS_DEG: dict[str, float] = {"small": 3.0, "medium": 5.0, "large": 8.0}  # diameter
DEFAULT_SIZE = "medium"
SIZE_NAMES: dict[str, str] = {"small": "Small", "medium": "Medium", "large": "Large"}

# Grid Click's gap between neighbouring cells, as a preset by visual angle
# (SPEC-grid-cell-gap.md S4.1). ``standard`` (None) is today's board -- cells
# inset by CELL_PAD_FRAC -- and stays the default (H1); the others are the
# space in degrees between two drawn cells, converted to px like a target size.
GAP_PRESETS_DEG: dict[str, float | None] = {"standard": None, "wide": 1.0, "extra_wide": 2.0}
DEFAULT_GAP = "standard"
GAP_NAMES: dict[str, str] = {"standard": "Standard", "wide": "Wide", "extra_wide": "Extra wide"}
# (value stored in grid.gap, label). The dialog appends the px on the
# operator's own monitor to the two angle presets.
GAP_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (name, GAP_NAMES[name] if degrees is None else f"{GAP_NAMES[name]} — {degrees:g}°")
    for name, degrees in GAP_PRESETS_DEG.items()
)
# A non-standard gap never takes more than this fraction of the pitch's smaller
# side (H4), so a drawn cell stays at least half its pitch.
GAP_MAX_PITCH_FRAC = 0.5

# The lab standard monitor: 24" 16:9 at 1920x1080 (531.4 mm wide).
REFERENCE_WIDTH_MM = 531.4
REFERENCE_MM_PER_PX = REFERENCE_WIDTH_MM / 1920
DEFAULT_VIEWING_DISTANCE_MM = 650.0

# A physical-width source is rejected as implausible when mm per *physical* px
# falls outside this band (EDID is sometimes 0 or bogus on projectors/TVs).
PLAUSIBLE_MM_PER_PX = (0.10, 0.60)

# Fraction of min(cell w, cell h) the canvas insets a grid cell by on each side
# (TaskCanvas._draw_grid_scene). Shared so the drawn cell, the shrink cap and
# the dialog's estimate can never drift apart.
CELL_PAD_FRAC = 0.06

# Scanning draws every icon at this fraction of the radius it is given
# (TaskCanvas, "icons" scene). A scanning size preset is the *visible* icon, so
# ``layout.radius_px`` -- the hit radius the canvas scales -- is the preset
# radius divided by this (SPEC-target-size-and-motion-paths.md S11.3, B2 a).
# Shared so drawing and sizing cannot drift apart.
ICON_DRAW_FRAC = 0.78

# How far beyond a target's circle its outermost drawn ring reaches: the dwell
# ring sits at r + 16 with an 8 px stroke, so r + 20. A target (or icon) must
# keep this much room to the canvas edge (SPEC S11.3).
EDGE_RING_PX = 20.0

# The task config block each task's size preset lives in; everything else has
# ``target``.
_SIZE_BLOCK_BY_TASK = {"scanning": "layout"}


class ScaleInfo(NamedTuple):
    """Millimetres per logical px, where it came from, and the panel size if known."""

    mm_per_px: float
    source: str  # "config" | "edid" | "fallback"
    width_mm: float | None = None
    height_mm: float | None = None


def normalize_size(size: Any) -> str:
    """A known preset name, lower-cased; an unknown one becomes
    :data:`DEFAULT_SIZE`, logged."""
    key = str(size).strip().lower() if size is not None else ""
    if key in SIZE_PRESETS_DEG:
        return key
    _log.warning("Unknown target size %r; using %r.", size, DEFAULT_SIZE)
    return DEFAULT_SIZE


def normalize_gap(gap: Any) -> str:
    """A known gap preset name, lower-cased; a missing one is quietly
    :data:`DEFAULT_GAP` and an unknown one becomes it too, logged."""
    if gap is None:
        return DEFAULT_GAP
    key = str(gap).strip().lower()
    if key in GAP_PRESETS_DEG:
        return key
    _log.warning("Unknown cell gap %r; using %r.", gap, DEFAULT_GAP)
    return DEFAULT_GAP


def mm_per_logical_px(
    physical_width_mm: float | None,
    logical_screen_width_px: float,
    dpr: float = 1.0,
    source: str = "config",
) -> tuple[float, str]:
    """``(mm per logical px, source)`` for one candidate physical width.

    ``source`` labels where the candidate came from and is returned as-is when
    the candidate is plausible. An implausible one (missing, <= 0, or giving
    mm per *physical* px outside :data:`PLAUSIBLE_MM_PER_PX`) falls back to the
    reference monitor: the display is assumed to be
    :data:`REFERENCE_WIDTH_MM` wide, which keeps the apparent size right at any
    Windows scale. ``dpr`` converts logical to physical px for the check only.
    """
    try:
        width = float(physical_width_mm) if physical_width_mm is not None else 0.0
    except (TypeError, ValueError):
        width = 0.0
    logical = float(logical_screen_width_px or 0.0)
    if width > 0 and logical > 0:
        scale = float(dpr) if dpr and dpr > 0 else 1.0
        lo, hi = PLAUSIBLE_MM_PER_PX
        if lo <= width / (logical * scale) <= hi:
            return width / logical, source
    fallback = REFERENCE_WIDTH_MM / logical if logical > 0 else REFERENCE_MM_PER_PX
    return fallback, "fallback"


def resolve_mm_per_px(
    logical_screen_width_px: float,
    dpr: float = 1.0,
    config_width_mm: float | None = None,
    edid_width_mm: float | None = None,
) -> tuple[float, str]:
    """Physical-width source order of SPEC S4.1: config, then EDID, then the
    reference monitor. The first plausible candidate wins."""
    for candidate, source in ((config_width_mm, "config"), (edid_width_mm, "edid")):
        value, used = mm_per_logical_px(candidate, logical_screen_width_px, dpr, source)
        if used != "fallback":
            return value, used
    return mm_per_logical_px(None, logical_screen_width_px, dpr)


def viewing_distance_mm(app_cfg: dict[str, Any]) -> float:
    """``app.viewing_distance_mm``, else the 650 mm default."""
    try:
        value = float(app_cfg.get("viewing_distance_mm") or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    return value if value > 0 else DEFAULT_VIEWING_DISTANCE_MM


def screen_scale(screen: Any, app_cfg: dict[str, Any]) -> ScaleInfo:
    """Resolve mm per logical px for ``screen`` (a QScreen, duck-typed) or, with
    ``screen`` None (headless replay has no screen), for the configured
    ``app.screen_width_px`` on the reference monitor."""
    config_w = app_cfg.get("screen_physical_width_mm")
    config_h = app_cfg.get("screen_physical_height_mm")
    if screen is None:
        logical_w = float(app_cfg.get("screen_width_px", 1920) or 1920)
        value, source = resolve_mm_per_px(logical_w, 1.0, config_w, None)
        return ScaleInfo(value, source, _positive(config_w), _positive(config_h))
    logical_w = float(screen.geometry().width())
    dpr = float(screen.devicePixelRatio())
    size_mm = screen.physicalSize()
    value, source = resolve_mm_per_px(logical_w, dpr, config_w, size_mm.width())
    if source == "config":
        return ScaleInfo(value, source, _positive(config_w), _positive(config_h))
    if source == "edid":
        return ScaleInfo(value, source, _positive(size_mm.width()), _positive(size_mm.height()))
    return ScaleInfo(value, source)


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def radius_px_for(size: str, mm_per_px: float, viewing_distance_mm: float) -> float:
    """Radius in logical px of the preset ``size``:
    ``diameter_mm = 2 * D * tan(deg / 2)``, ``radius_px = diameter_mm / 2 / mm_per_px``."""
    degrees = SIZE_PRESETS_DEG[normalize_size(size)]
    distance = viewing_distance_mm if viewing_distance_mm and viewing_distance_mm > 0 else (
        DEFAULT_VIEWING_DISTANCE_MM
    )
    scale = mm_per_px if mm_per_px and mm_per_px > 0 else REFERENCE_MM_PER_PX
    diameter_mm = 2.0 * distance * math.tan(math.radians(degrees) / 2.0)
    return diameter_mm / 2.0 / scale


def gap_px_for(gap: str, mm_per_px: float, viewing_distance_mm: float) -> float | None:
    """Width in logical px of the gap preset ``gap``, the same visual-angle
    maths as :func:`radius_px_for` (``extent_mm = 2 * D * tan(deg / 2)``, here
    the whole extent rather than half of it). ``None`` for ``standard``: that
    gap is a fraction of the cell, not an angle."""
    degrees = GAP_PRESETS_DEG[normalize_gap(gap)]
    if degrees is None:
        return None
    distance = viewing_distance_mm if viewing_distance_mm and viewing_distance_mm > 0 else (
        DEFAULT_VIEWING_DISTANCE_MM
    )
    scale = mm_per_px if mm_per_px and mm_per_px > 0 else REFERENCE_MM_PER_PX
    return 2.0 * distance * math.tan(math.radians(degrees) / 2.0) / scale


def size_block(task_cfg: dict[str, Any]) -> str:
    """The key path (a block of the task config) a task's ``size`` preset and
    ``radius_px`` live under: ``layout`` for scanning, ``target`` for the rest."""
    return _SIZE_BLOCK_BY_TASK.get(str(task_cfg.get("task_id")), "target")


def apply_target_size(
    task_cfg: dict[str, Any],
    scale: ScaleInfo,
    viewing_distance: float,
    block: str = "target",
) -> dict[str, Any] | None:
    """Resolve ``<block>.size`` into ``<block>.radius_px`` in ``task_cfg``, in place.

    ``block`` is the key path (:func:`size_block`): ``target`` for the three
    target tasks, ``layout`` for scanning. Tasks keep reading ``radius_px``
    exactly as before. With no ``size`` key (an old YAML or profile) nothing is
    touched and ``None`` is returned, so the explicit ``radius_px`` stands; with
    both, ``size`` wins (SPEC S4.2). Returns the ``metadata.target_size`` block.

    Scanning (``layout``) is sized by the *visible* icon (SPEC S11.3, B2 a): the
    preset radius is the drawn icon's, so the ``radius_px`` written for the
    canvas to scale is that divided by :data:`ICON_DRAW_FRAC`, and the returned
    block says ``"radius_of": "icon"``.
    """
    section = task_cfg.get(block)
    if not isinstance(section, dict) or section.get("size") is None:
        return None
    preset = normalize_size(section["size"])
    radius = round(radius_px_for(preset, scale.mm_per_px, viewing_distance), 1)
    info = {
        "preset": preset,
        "diameter_deg": SIZE_PRESETS_DEG[preset],
        "radius_px": radius,
        "mm_per_px": round(scale.mm_per_px, 4),
        "mm_per_px_source": scale.source,
        "viewing_distance_mm": viewing_distance,
    }
    if block == "layout":
        section["radius_px"] = radius / ICON_DRAW_FRAC
        info["radius_of"] = "icon"
    else:
        section["radius_px"] = radius
    return info


def target_size_log_line(info: dict[str, Any], scale: ScaleInfo) -> str:
    """The Session Log line, e.g.
    ``Target size: Medium (5.0°) = 102 px radius (EDID 531x299 mm, 650 mm).``
    (scanning's says ``Icon size:``)."""
    if scale.source == "edid" and scale.width_mm and scale.height_mm:
        where = f"EDID {scale.width_mm:.0f}x{scale.height_mm:.0f} mm"
    elif scale.source == "edid":
        where = f"EDID {scale.width_mm or 0:.0f} mm wide"
    elif scale.source == "config":
        where = f"configured {scale.width_mm or 0:.0f} mm wide"
    else:
        where = f"fallback, assumed {REFERENCE_WIDTH_MM:.0f} mm wide"
    name = SIZE_NAMES[info["preset"]]
    label = "Icon size" if info.get("radius_of") == "icon" else "Target size"
    return (
        f"{label}: {name} ({info['diameter_deg']:.1f}°) = {info['radius_px']:.0f} px "
        f"radius ({where}, {info['viewing_distance_mm']:g} mm)."
    )


def apply_grid_gap(
    task_cfg: dict[str, Any], scale: ScaleInfo, viewing_distance: float
) -> dict[str, Any] | None:
    """Resolve ``grid.gap`` into ``grid.gap_px`` in ``task_cfg``, in place
    (SPEC-grid-cell-gap.md S4.2) -- against the same screen scale as
    :func:`apply_target_size`.

    ``gap_px`` is the *wanted* gap in logical px, ``None`` for ``standard``
    (today's board: the task then draws, fits and hit-tests exactly as before).
    With no ``gap`` key (an old YAML or profile) nothing is touched and ``None``
    is returned, which is the same standard board. Returns the
    ``metadata.grid_gap`` block.
    """
    section = task_cfg.get("grid")
    if not isinstance(section, dict) or section.get("gap") is None:
        return None
    preset = normalize_gap(section["gap"])
    gap_px = gap_px_for(preset, scale.mm_per_px, viewing_distance)
    section["gap_px"] = None if gap_px is None else round(gap_px, 1)
    return {"preset": preset, "gap_deg": GAP_PRESETS_DEG[preset], "gap_px": section["gap_px"]}


def grid_gap_log_line(info: dict[str, Any]) -> str:
    """The Session Log line, e.g. ``Cell gap: Wide — 1° (≈41 px)`` (Standard
    says just ``Cell gap: Standard``)."""
    name = GAP_NAMES[info["preset"]]
    if info.get("gap_px") is None:
        return f"Cell gap: {name}"
    return f"Cell gap: {name} — {info['gap_deg']:g}° (≈{info['gap_px']:.0f} px)"


class CellGeometry(NamedTuple):
    """One grid cell as it is drawn, fitted and hit-tested (px). Everything that
    needs the cell's shape reads it from here -- see :func:`grid_cell_geometry`."""

    cell_w: float  # the drawn cell's width and height
    cell_h: float
    inset: float  # per side, pitch to drawn cell
    gap_px: float  # space between two neighbouring drawn cells, as used
    wanted_px: float | None  # the gap asked for; None for standard
    capped: bool  # the wanted gap was above the H4 cap
    fit_radius_px: float  # largest target radius that fits the drawn cell
    hit_w: float  # the cell-shaped hit area (the circle test is clipped to it)
    hit_h: float


def grid_cell_geometry(
    pitch_w_px: float, pitch_h_px: float, gap_px: float | None = None
) -> CellGeometry:
    """The single source for how a grid cell of the given pitch is drawn,
    fitted and hit-tested (SPEC-grid-cell-gap.md S4.1), so the canvas, the
    task's target cap and hit test and the dialog's hint cannot drift apart --
    the :data:`CELL_PAD_FRAC` sharing pattern.

    ``gap_px`` ``None`` is *standard* (H1): the cell is the pitch inset by
    :data:`CELL_PAD_FRAC` of its smaller side per edge, and the hit area is the
    whole, unpadded pitch -- exactly the board as it was before the setting
    existed. A number is a wanted gap between two drawn cells (H2): never
    below the standard gap of this pitch, and capped at
    :data:`GAP_MAX_PITCH_FRAC` of the pitch's smaller side (H4, ``capped``
    says so); the drawn cell is the pitch less that gap and the hit area is
    that drawn cell (H3), so the gap belongs to no cell.
    """
    smaller = min(pitch_w_px, pitch_h_px)
    if gap_px is None:
        inset = CELL_PAD_FRAC * smaller
        return CellGeometry(
            cell_w=pitch_w_px - 2.0 * inset,
            cell_h=pitch_h_px - 2.0 * inset,
            inset=inset,
            gap_px=2.0 * inset,
            wanted_px=None,
            capped=False,
            fit_radius_px=0.5 * smaller * (1.0 - 2.0 * CELL_PAD_FRAC),
            hit_w=pitch_w_px,
            hit_h=pitch_h_px,
        )
    wanted = max(float(gap_px), 0.0)
    used = max(wanted, 2.0 * CELL_PAD_FRAC * smaller)
    cap = GAP_MAX_PITCH_FRAC * smaller
    capped = used > cap
    if capped:
        used = cap
    width, height = pitch_w_px - used, pitch_h_px - used
    return CellGeometry(
        cell_w=width,
        cell_h=height,
        inset=used / 2.0,
        gap_px=used,
        wanted_px=wanted,
        capped=capped,
        fit_radius_px=0.5 * min(width, height),
        hit_w=width,
        hit_h=height,
    )


def fit_radius_px(cell_w_px: float, cell_h_px: float, gap_px: float | None = None) -> float:
    """Largest circle radius that sits fully inside a grid cell as the canvas
    draws it (:func:`grid_cell_geometry`; by default the cell rectangle inset by
    :data:`CELL_PAD_FRAC` of its smaller side on every edge)."""
    return grid_cell_geometry(cell_w_px, cell_h_px, gap_px).fit_radius_px


def estimate_grid_geometry(
    rows: int,
    cols: int,
    canvas_w_px: float,
    canvas_h_px: float,
    margin_frac: float = 0.12,
    gap_px: float | None = None,
) -> CellGeometry:
    """:func:`grid_cell_geometry` for an R x C grid on a canvas of the given
    size -- the same layout maths as ``ClickGridTask.build_targets``. Used by
    the settings dialog's hint, where the real canvas does not exist yet."""
    span = 1.0 - 2.0 * margin_frac
    return grid_cell_geometry(
        span / max(cols, 1) * canvas_w_px, span / max(rows, 1) * canvas_h_px, gap_px
    )


def estimate_grid_fit_radius_px(
    rows: int,
    cols: int,
    canvas_w_px: float,
    canvas_h_px: float,
    margin_frac: float = 0.12,
    gap_px: float | None = None,
) -> float:
    """:func:`fit_radius_px` for an R x C grid on a canvas of the given size
    (``gap_px`` ``None`` = the standard gap)."""
    return estimate_grid_geometry(
        rows, cols, canvas_w_px, canvas_h_px, margin_frac, gap_px
    ).fit_radius_px


def grid_fit_hint(
    rows: int, cols: int, canvas_w_px: float, canvas_h_px: float, wanted_radius_px: float,
    margin_frac: float = 0.12, gap_px: float | None = None,
) -> str | None:
    """The shrink hint of an R x C grid (SPEC-compass-task-flow.md 4B.3), or ``None``
    when ``wanted_radius_px`` fits and the wanted gap is not capped (H4). An
    estimate from the screen's available area, hence "approximate"; the run
    applies the real fit through :func:`grid_cell_geometry`. Shared by the
    settings dialog and the configuration page."""
    geometry = estimate_grid_geometry(rows, cols, canvas_w_px, canvas_h_px, margin_frac, gap_px)
    fits = geometry.fit_radius_px
    shrunk = fits < wanted_radius_px - 0.5
    tail = f"to fit a {rows} x {cols} grid (approximate)"
    if geometry.capped:
        limited = f"Gap limited to ≈ {round(geometry.gap_px)} px"
        if shrunk:
            return f"{limited} and targets shrunk to ≈ {round(2 * fits)} px {tail}"
        return f"{limited} {tail}"
    return f"Will be shrunk to ≈ {round(2 * fits)} px {tail}" if shrunk else None


def edge_inset_norm(radius_px: float, canvas_w_px: float, canvas_h_px: float) -> tuple[float, float]:
    """How far from the canvas edge a target of ``radius_px`` must stay, as
    ``(margin_x, margin_y)`` fractions of the canvas width and height: the
    circle plus its outermost drawn ring (:data:`EDGE_RING_PX`). click_static
    and follow_moving pull positions inward by this much (SPEC S11.3, B1 a); the
    size itself never changes."""
    reach = max(float(radius_px), 0.0) + EDGE_RING_PX
    return (
        reach / canvas_w_px if canvas_w_px > 0 else 0.0,
        reach / canvas_h_px if canvas_h_px > 0 else 0.0,
    )


def clamp_to_inset(value: float, margin: float) -> float:
    """``value`` limited to ``[margin, 1 - margin]``; a canvas too small to hold
    the target at all (``margin`` past one half) centres it instead. A value
    already inside comes back unchanged."""
    lo, hi = margin, 1.0 - margin
    if lo > hi:
        return 0.5
    return min(max(value, lo), hi)


def fit_icon_radius_px(
    slots: list[tuple[float, float]], canvas_w_px: float, canvas_h_px: float
) -> float:
    """Largest *drawn* scanning-icon radius that keeps every icon clear of its
    neighbours and of the canvas edge (SPEC S11.3): half the smallest pixel
    distance between two slot centres less the grid's own padding
    (:data:`CELL_PAD_FRAC`), and the smallest slot-centre-to-edge distance less
    :data:`EDGE_RING_PX`. ``slots`` are normalized canvas coordinates; the
    result is in canvas px. ``ScanningTask.effective_radius_px`` and the
    settings dialog's shrink hint share it, so they cannot drift."""
    points = [(x * canvas_w_px, y * canvas_h_px) for x, y in slots]
    cap = math.inf
    for i, (xi, yi) in enumerate(points):
        edge = min(xi, canvas_w_px - xi, yi, canvas_h_px - yi)
        cap = min(cap, edge - EDGE_RING_PX)
        for xj, yj in points[i + 1 :]:
            cap = min(cap, 0.5 * math.hypot(xi - xj, yi - yj) * (1.0 - 2.0 * CELL_PAD_FRAC))
    return max(cap, 0.0)


def icon_fit_hint(
    n_icons: int, slots: list[tuple[float, float]], canvas_w_px: float, canvas_h_px: float,
    wanted_radius_px: float,
) -> str | None:
    """The shrink hint of ``n_icons`` scanning icons at ``slots`` (4B.3), or ``None``
    when the wanted *drawn* radius fits. The caller lays the slots out with
    ``scanning_layout_slots`` (the task imports this module, so it cannot be
    imported here). Shared by the settings dialog and the page."""
    fits = fit_icon_radius_px(slots, canvas_w_px, canvas_h_px)
    if fits < wanted_radius_px - 0.5:
        return f"Icons will be shrunk to ≈ {round(2 * fits)} px to fit {n_icons} icons (approximate)"
    return None
