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


def apply_target_size(
    task_cfg: dict[str, Any], scale: ScaleInfo, viewing_distance: float
) -> dict[str, Any] | None:
    """Resolve ``target.size`` into ``target.radius_px`` in ``task_cfg``, in place.

    Tasks keep reading ``radius_px`` exactly as before. With no ``size`` key
    (an old YAML or profile) nothing is touched and ``None`` is returned, so
    the explicit ``radius_px`` stands; with both, ``size`` wins (SPEC S4.2).
    Returns the ``metadata.target_size`` block.
    """
    target = task_cfg.get("target")
    if not isinstance(target, dict) or target.get("size") is None:
        return None
    preset = normalize_size(target["size"])
    radius = round(radius_px_for(preset, scale.mm_per_px, viewing_distance), 1)
    target["radius_px"] = radius
    return {
        "preset": preset,
        "diameter_deg": SIZE_PRESETS_DEG[preset],
        "radius_px": radius,
        "mm_per_px": round(scale.mm_per_px, 4),
        "mm_per_px_source": scale.source,
        "viewing_distance_mm": viewing_distance,
    }


def target_size_log_line(info: dict[str, Any], scale: ScaleInfo) -> str:
    """The Session Log line, e.g.
    ``Target size: Medium (5.0°) = 102 px radius (EDID 531x299 mm, 650 mm).``"""
    if scale.source == "edid" and scale.width_mm and scale.height_mm:
        where = f"EDID {scale.width_mm:.0f}x{scale.height_mm:.0f} mm"
    elif scale.source == "edid":
        where = f"EDID {scale.width_mm or 0:.0f} mm wide"
    elif scale.source == "config":
        where = f"configured {scale.width_mm or 0:.0f} mm wide"
    else:
        where = f"fallback, assumed {REFERENCE_WIDTH_MM:.0f} mm wide"
    name = SIZE_NAMES[info["preset"]]
    return (
        f"Target size: {name} ({info['diameter_deg']:.1f}°) = {info['radius_px']:.0f} px "
        f"radius ({where}, {info['viewing_distance_mm']:g} mm)."
    )


def fit_radius_px(cell_w_px: float, cell_h_px: float) -> float:
    """Largest circle radius that sits fully inside a grid cell as the canvas
    draws it (the cell rectangle inset by :data:`CELL_PAD_FRAC` of its smaller
    side on every edge)."""
    return 0.5 * min(cell_w_px, cell_h_px) * (1.0 - 2.0 * CELL_PAD_FRAC)


def estimate_grid_fit_radius_px(
    rows: int, cols: int, canvas_w_px: float, canvas_h_px: float, margin_frac: float = 0.12
) -> float:
    """:func:`fit_radius_px` for an R x C grid on a canvas of the given size --
    the same layout maths as ``ClickGridTask.build_targets``. Used by the
    settings dialog's shrink hint, where the real canvas does not exist yet."""
    span = 1.0 - 2.0 * margin_frac
    return fit_radius_px(span / max(cols, 1) * canvas_w_px, span / max(rows, 1) * canvas_h_px)
