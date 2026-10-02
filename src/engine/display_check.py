"""Display standard check (SPEC-display-standard-check.md S4.1).

Data collection is recommended on a 1920x1080 display at 100 % Windows scale,
so sessions are comparable and the task screens lay out as designed. Pure
arithmetic, no Qt: the caller passes a screen's logical size and device pixel
ratio. The constants live here, not in ``configs/default.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass

STANDARD_WIDTH_PX = 1920
STANDARD_HEIGHT_PX = 1080
STANDARD_SCALE_PERCENT = 100


@dataclass(frozen=True)
class DisplayCheck:
    width_px: int  # physical pixels
    height_px: int
    scale_percent: int  # round(devicePixelRatio * 100)
    standard: bool


def check_display(logical_w: float, logical_h: float, dpr: float) -> DisplayCheck:
    """Physical size = round(logical x dpr); standard needs both the exact
    resolution and exactly 100 % scale."""
    width = round(logical_w * dpr)
    height = round(logical_h * dpr)
    scale = round(dpr * 100)
    standard = (
        width == STANDARD_WIDTH_PX
        and height == STANDARD_HEIGHT_PX
        and scale == STANDARD_SCALE_PERCENT
    )
    return DisplayCheck(width_px=width, height_px=height, scale_percent=scale, standard=standard)
