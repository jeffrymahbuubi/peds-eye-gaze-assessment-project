"""What the Setup page says about itself, as pure functions (SPEC-design-system-phase2.md H4,
V3): the short names of what still blocks Continue to Tests, and the two status badges.

Split out of :mod:`~src.ui.setup_page` (already over the size limit). The sentences of the
Setup blockers live here and in :mod:`~src.engine.input_choice` (the tracker and calibration
ones, which the Start page also reads); each has a short name, and the caption under a
disabled Continue to Tests lists those names for exactly the blockers
:meth:`~src.ui.setup_page.SetupPage.continue_blockers` returns. The tracker and the
calibration are never among them: Continue does not wait for either (user decision of
2026-10-07).
"""

from __future__ import annotations

import math
from typing import Any

from ..engine.input_choice import CALIBRATION_BLOCKER, TRACKER_BLOCKER
from ..engine.target_size import screen_scale, viewing_distance_mm

# The Start page lists these one per line after "Blocked:", each pointing at the page that
# fixes it (proposal 4: "Sex is not selected (Setup page).").
SUBJECT_BLOCKER = "Subject ID is empty (Setup page)."
DATE_BLOCKER = "Assessment date is empty (Setup page)."
SEX_BLOCKER = "Sex is not selected (Setup page)."
DISPLAY_BLOCKER = "The display is not 1920x1080 at 100 %. Tick the acknowledgement on the Setup page."

SHORT_NAMES: dict[str, str] = {
    TRACKER_BLOCKER: "tracker",
    CALIBRATION_BLOCKER: "calibration",
    SUBJECT_BLOCKER: "Subject ID",
    DATE_BLOCKER: "Assessment Date",
    SEX_BLOCKER: "Sex",
    DISPLAY_BLOCKER: "display acknowledgement",
}
NEEDS_PREFIX = "Needs: "


def needs_names(blockers: list[str]) -> list[str]:
    """The short name of each blocker, in order (a sentence without one is skipped)."""
    return [SHORT_NAMES[b] for b in blockers if b in SHORT_NAMES]


def needs_caption(blockers: list[str]) -> str:
    """``"Needs: Sex, display acknowledgement"`` for the blockers, or ``""`` for none."""
    names = needs_names(blockers)
    return NEEDS_PREFIX + ", ".join(names) if names else ""


def tracker_badge(connected: bool) -> tuple[str, str]:
    """``(kind, word)`` of the badge beside Connect."""
    return ("connected", "Connected") if connected else ("disconnected", "Disconnected")


def error_degrees(error_px: float, mm_per_logical_px: float, dpr: float, distance_mm: float) -> float:
    """A calibration error of ``error_px`` physical px as visual angle at ``distance_mm``:
    ``2 * atan(mm / 2D)``. The device reports pixels of the screen it drew on (physical), and
    ``mm_per_logical_px`` is per Qt logical px, so it is divided by the device pixel ratio."""
    scale = dpr if dpr and dpr > 0 else 1.0
    chord = max(float(error_px), 0.0) * mm_per_logical_px / scale
    return math.degrees(2.0 * math.atan(chord / (2.0 * distance_mm)))


def calibration_badge(result: Any | None, screen: Any, app_cfg: dict[str, Any]) -> tuple[str, str]:
    """``(kind, word)`` of the badge beside Do Calibration: ``Not calibrated`` without a
    result, else ``Calibrated, 5 points, 1.8°`` (the measured mean error as visual angle, left
    out when the device gave none). ``screen`` is a QScreen (duck-typed, ``None`` allowed)."""
    if result is None:
        return "not_calibrated", "Not calibrated"
    parts = ["Calibrated"]
    n_points = getattr(result, "n_points", None)
    if isinstance(n_points, int) and n_points > 0:
        parts.append(f"{n_points} point" + ("" if n_points == 1 else "s"))
    error_px = getattr(result, "mean_error_px", None)
    if isinstance(error_px, (int, float)):
        dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
        scale = screen_scale(screen, app_cfg)
        parts.append(f"{error_degrees(error_px, scale.mm_per_px, dpr, viewing_distance_mm(app_cfg)):.1f}°")
    return "calibrated", ", ".join(parts)
