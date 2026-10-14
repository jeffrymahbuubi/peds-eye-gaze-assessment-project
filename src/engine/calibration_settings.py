"""Settings of the app-drawn calibration and the maths around them (SPEC-app-drawn-calibration.md
2, 4.3, 4.3b, 4.4; decisions Q1, D1, D3, D5-D8).

Pure and Qt-free, like :mod:`src.engine.target_size`: every rule here (the speed pairs, the
degrees-to-pixels size, the Grid 3 point layout, the per-point score and its colour band) is
unit-testable headlessly. The Setup card's controls, the calibration window and the engine all
read the same names from here, so a preset, a layout or a score can never drift apart between
the screen the child sees and the numbers written to ``calibration.json``.

The settings are saved per PC in the local state (next to the Control address), never in
``configs/default.yaml``: :func:`load_settings` reads them back, :func:`settings_state` is what the
page hands to ``save_local_state``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple

from ..data.report_geometry import Geometry
from .calibration import CalibrationResult, per_point_errors_px
from .config import CONFIG_ROOT
from .target_size import DEFAULT_VIEWING_DISTANCE_MM, REFERENCE_MM_PER_PX

# -- the settings and their values --------------------------------------------------------------

SCREEN_APP = "app"
SCREEN_CONTROL = "control"
DEFAULT_SCREEN = SCREEN_APP
# (value stored, label shown): D6 replaced the "Show calibration window" tick box.
SCREEN_CHOICES: tuple[tuple[str, str], ...] = (
    (SCREEN_APP, "App (Grid 3 style)"),
    (SCREEN_CONTROL, "Gazepoint Control"),
)

POINT_CHOICES: tuple[int, ...] = (5, 9)  # Control rejects fewer than 4; Grid 3's 1-3 are not offered
DEFAULT_POINTS = 5


class Speed(NamedTuple):
    """One speed preset (D1): the glide is ``CALIBRATE_DELAY``, the hold ``CALIBRATE_TIMEOUT``."""

    glide_s: float
    hold_s: float


SPEEDS: dict[str, Speed] = {
    "slow": Speed(1.0, 1.5),
    "normal": Speed(0.8, 1.0),
    "fast": Speed(1.8, 0.4),  # the hold is confirmed or raised at probe P4 (SPEC 4.3b)
}
DEFAULT_SPEED = "normal"
SPEED_NAMES: dict[str, str] = {"slow": "Slow", "normal": "Normal", "fast": "Fast"}

# (gliding, holding) diameters in degrees of visual angle (4.3b).
SIZES_DEG: dict[str, tuple[float, float]] = {
    "small": (2.2, 0.6),
    "normal": (3.0, 0.8),
    "large": (4.0, 1.0),
}
DEFAULT_SIZE = "normal"
SIZE_NAMES: dict[str, str] = {"small": "Small", "normal": "Normal", "large": "Large"}

# The stimulus background (not UI chrome, so not a design token): white, black, mid grey.
BACKGROUNDS: dict[str, str] = {"white": "#FFFFFF", "black": "#000000", "grey": "#808080"}
DEFAULT_BACKGROUND = "white"
BACKGROUND_NAMES: dict[str, str] = {"white": "White", "black": "Black", "grey": "Grey"}

# D3: the built-in icons, in the order the picker lists them; the first is the default.
ICON_IDS: tuple[str, ...] = ("bee", "star", "ball", "fish", "flower", "car")
ICON_NAMES: dict[str, str] = {
    "bee": "Bee", "star": "Star", "ball": "Ball", "fish": "Fish", "flower": "Flower", "car": "Car",
}
DEFAULT_TARGET = ICON_IDS[0]
ICON_DIR = CONFIG_ROOT / "assets" / "calibration"


def icon_path(icon_id: str, root: Path | None = None) -> Path:
    """The PNG of a built-in icon (an unknown id gives the default's path)."""
    name = icon_id if icon_id in ICON_IDS else DEFAULT_TARGET
    return (root if root is not None else ICON_DIR) / f"{name}.png"


def _pick(value: Any, allowed: Any, default: str) -> str:
    key = str(value).strip().lower() if value is not None else ""
    return key if key in allowed else default


def _nearest_points(value: Any) -> int:
    """5 or 9, whichever is nearer (a tie is 5): an old ``calibration.points`` of 3 or 7 still
    lands on a layout the app offers."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULT_POINTS
    return min(POINT_CHOICES, key=lambda choice: (abs(choice - number), choice))


@dataclass(frozen=True)
class CalibrationSettings:
    screen: str = DEFAULT_SCREEN
    points: int = DEFAULT_POINTS
    speed: str = DEFAULT_SPEED
    target: str = DEFAULT_TARGET
    size: str = DEFAULT_SIZE
    background: str = DEFAULT_BACKGROUND

    @property
    def delay_s(self) -> float:
        """``CALIBRATE_DELAY`` (the glide) of the speed preset."""
        return SPEEDS[self.speed].glide_s

    @property
    def timeout_s(self) -> float:
        """``CALIBRATE_TIMEOUT`` (the hold, when Control samples) of the speed preset."""
        return SPEEDS[self.speed].hold_s

    @property
    def is_app(self) -> bool:
        return self.screen == SCREEN_APP

    def as_dict(self) -> dict[str, Any]:
        return {
            "screen": self.screen, "points": self.points, "speed": self.speed,
            "target": self.target, "size": self.size, "background": self.background,
        }

    @classmethod
    def from_dict(cls, raw: Any, base: CalibrationSettings | None = None) -> CalibrationSettings:
        """The settings in ``raw`` (a saved dict), every unknown or missing value taken from
        ``base`` (the defaults when ``None``)."""
        base = base if base is not None else cls()
        data = raw if isinstance(raw, dict) else {}
        return cls(
            screen=_pick(data.get("screen"), dict(SCREEN_CHOICES), base.screen),
            points=_nearest_points(data["points"]) if "points" in data else base.points,
            speed=_pick(data.get("speed"), SPEEDS, base.speed),
            target=_pick(data.get("target"), ICON_IDS, base.target),
            size=_pick(data.get("size"), SIZES_DEG, base.size),
            background=_pick(data.get("background"), BACKGROUNDS, base.background),
        )


def settings_from_config(config_calibration: Any) -> CalibrationSettings:
    """The defaults the shipped ``calibration:`` block of ``default.yaml`` gives (A12): its
    ``points`` (5 or 9), and the App screen for its ``show`` (``true`` is the App screen).
    ``show`` has no other mapping: "calibrate with no picture at all" is no longer offered
    (SPEC 4.2), so a ``false`` or missing value is the App default as well."""
    block = config_calibration if isinstance(config_calibration, dict) else {}
    return CalibrationSettings(
        screen=SCREEN_APP,
        points=_nearest_points(block.get("points", DEFAULT_POINTS)),
    )


def load_settings(local_state: dict[str, Any], config_calibration: Any = None) -> CalibrationSettings:
    """This PC's settings: the saved ``calibration`` block of the local state over the defaults
    of :func:`settings_from_config`."""
    return CalibrationSettings.from_dict(local_state.get("calibration"), settings_from_config(config_calibration))


def settings_state(settings: CalibrationSettings) -> dict[str, Any]:
    """The update to hand to ``save_local_state``."""
    return {"calibration": settings.as_dict()}


# -- the point layout (D5) ----------------------------------------------------------------------

# Centre first (D9, 4.8 R1), then Grid 3's corners in its order: top-left, bottom-right,
# top-right, bottom-left, at 10 / 90 %; the 9-point layout adds the edge midpoints (top, right,
# bottom, left) at 10 / 50 / 90 %.
_APP_LAYOUT: tuple[tuple[float, float], ...] = (
    (0.5, 0.5), (0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9),
    (0.5, 0.1), (0.9, 0.5), (0.5, 0.9), (0.1, 0.5),
)
LAYOUT_APP = "grid3"
LAYOUT_CONTROL = "vendor"


def app_layout(n_points: int) -> list[tuple[float, float]]:
    """The first ``n_points`` points of the app's layout (centre first), as (X, Y) fractions of
    the screen. Raises ``ValueError`` outside 4-9 (Control rejects fewer than 4)."""
    if not 4 <= n_points <= len(_APP_LAYOUT):
        raise ValueError(f"Unsupported calibration point count: {n_points} (must be 4-{len(_APP_LAYOUT)})")
    return list(_APP_LAYOUT[:n_points])


# -- the size on screen (4.3b) ------------------------------------------------------------------


def icon_diameter_px(
    size: str, holding: bool, mm_per_px: float, viewing_distance_mm: float | None = None
) -> float:
    """Diameter of the icon in the pixels ``mm_per_px`` is per: ``2 * D * tan(deg / 2) / mm_per_px``
    for the preset's gliding (large) or holding (small) angle. ``mm_per_px`` is per Qt logical px
    (:func:`src.engine.target_size.screen_scale`) for a widget that paints in logical px."""
    gliding, holding_deg = SIZES_DEG[_pick(size, SIZES_DEG, DEFAULT_SIZE)]
    degrees = holding_deg if holding else gliding
    distance = viewing_distance_mm if viewing_distance_mm and viewing_distance_mm > 0 else DEFAULT_VIEWING_DISTANCE_MM
    scale = mm_per_px if mm_per_px and mm_per_px > 0 else REFERENCE_MM_PER_PX
    return 2.0 * distance * math.tan(math.radians(degrees) / 2.0) / scale


# -- the per-point score (Q1, 4.4) --------------------------------------------------------------

SCORE_ZERO_DEG = 3.0  # the error that scores 0
GOOD_MAX_DEG = 1.0  # green up to and including this
FAIR_MAX_DEG = 2.0  # amber above that, up to and including this; red above

BAND_GOOD = "good"
BAND_FAIR = "fair"
BAND_POOR = "poor"
BAND_NONE = "none"  # no valid eye: a grey circle with "-"


def point_score(error_deg: float | None) -> int:
    """``round(100 * max(0, 1 - error / 3))``; 0 with no valid eye."""
    if error_deg is None:
        return 0
    return int(round(100.0 * max(0.0, 1.0 - error_deg / SCORE_ZERO_DEG)))


def point_band(error_deg: float | None) -> str:
    """Green 1 degree or less, amber up to 2 degrees, red above; ``none`` with no valid eye."""
    if error_deg is None:
        return BAND_NONE
    if error_deg <= GOOD_MAX_DEG:
        return BAND_GOOD
    return BAND_FAIR if error_deg <= FAIR_MAX_DEG else BAND_POOR


@dataclass(frozen=True)
class PointScore:
    point: int
    x: float  # the target, as fractions of the screen
    y: float
    error_deg: float | None  # mean over the valid eyes; None with no valid eye
    score: int
    band: str

    @property
    def weak(self) -> bool:
        """Needs attention: amber, red, or no valid eye (the map gives it a thicker ring)."""
        return self.band != BAND_GOOD


def _mean_valid_error_px(row: dict[str, Any]) -> float | None:
    errors = [
        row[f"{side}_error_px"]
        for side in ("left", "right")
        if row.get(side) is not None and row[side].get("valid") and row[f"{side}_error_px"] is not None
    ]
    return sum(errors) / len(errors) if errors else None


def score_points(per_point: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None, geometry: Geometry) -> list[PointScore]:
    """One :class:`PointScore` per point of a ``CALIB_RESULT``: the error of each valid eye as in
    ``per_point_errors_px`` (monitor px), turned into degrees by ``geometry.px_to_deg``, averaged
    over the valid eyes. An empty list for no per-point data."""
    if not per_point:
        return []
    width = geometry.screen_w_px or 0
    height = geometry.screen_h_px or 0
    scores: list[PointScore] = []
    for row in per_point_errors_px(tuple(per_point), int(width), int(height)):
        error_px = _mean_valid_error_px(row)
        error_deg = geometry.px_to_deg(error_px) if error_px is not None else None
        scores.append(
            PointScore(
                point=int(row["point"]), x=float(row["target_x"]), y=float(row["target_y"]),
                error_deg=error_deg, score=point_score(error_deg), band=point_band(error_deg),
            )
        )
    return scores


def annotate_per_point(
    per_point: tuple[dict[str, Any], ...] | None, scores: list[PointScore]
) -> tuple[dict[str, Any], ...] | None:
    """``per_point`` with each point's ``score`` and ``error_deg`` added (4.7), for
    ``calibration.json``; unchanged when there is nothing to add."""
    if not per_point or not scores:
        return per_point
    by_point = {s.point: s for s in scores}
    out = []
    for entry in per_point:
        found = by_point.get(entry.get("point"))
        extra = {} if found is None else {
            "score": found.score,
            "error_deg": None if found.error_deg is None else round(found.error_deg, 3),
        }
        out.append({**entry, **extra})
    return tuple(out)


def attention_text(scores: list[PointScore]) -> str:
    """The line under the results map (4.4)."""
    weak = sum(1 for s in scores if s.weak)
    if not weak:
        return "All points are good."
    subject = "1 point needs" if weak == 1 else f"{weak} points need"
    return f"{subject} attention. Check the head position, then Improve calibration."


def geometry_for_screen(
    screen_w_px: float, screen_h_px: float, mm_per_px: float, dpr: float, distance_mm: float
) -> Geometry:
    """The :class:`Geometry` the scores are measured in: the tracked monitor in *physical* px
    (``screen_w_px`` x ``screen_h_px``, the unit of ``CALIB_RESULT`` once scaled by the screen
    size), its physical size from ``mm_per_px`` (per Qt logical px, so divided by ``dpr``), and the
    viewing distance."""
    scale = dpr if dpr and dpr > 0 else 1.0
    mm_per_physical_px = mm_per_px / scale
    return Geometry(
        screen_w_px=float(screen_w_px),
        screen_h_px=float(screen_h_px),
        phys_w_mm=float(screen_w_px) * mm_per_physical_px,
        phys_h_mm=float(screen_h_px) * mm_per_physical_px,
        distance_mm=float(distance_mm),
    )


# -- what calibration.json keeps (4.7) ----------------------------------------------------------

MODE_APP = "app_drawn"  # the app's calibration window
MODE_CONTROL = "control"  # the operator chose Gazepoint Control's own window
MODE_FALLBACK = "control_fallback"  # the app's screen did not respond (4.2)


def record_for(settings: CalibrationSettings, mode: str, improve_runs: int = 0) -> dict[str, Any]:
    """The settings of a run as written into ``calibration.json``."""
    return {
        "mode": mode,
        "speed": settings.speed,
        "delay_s": settings.delay_s,
        "timeout_s": settings.timeout_s,
        "icon": settings.target,
        "size": settings.size,
        "background": settings.background,
        "layout": LAYOUT_APP if mode == MODE_APP else LAYOUT_CONTROL,
        "improve_runs": int(improve_runs),
        "accuracy_checked": False,
    }


def with_improve_runs(result: CalibrationResult, improve_runs: int) -> CalibrationResult:
    """``result`` with its record's ``improve_runs`` set (the re-runs before Back)."""
    record = dict(result.record or {})
    record["improve_runs"] = int(improve_runs)
    return replace(result, record=record)


def with_accuracy_checked(result: CalibrationResult, checked: bool) -> CalibrationResult:
    """``result`` with its record's ``accuracy_checked`` set: whether the Check accuracy view
    (4.8 R3) was opened before Back."""
    record = dict(result.record or {})
    record["accuracy_checked"] = bool(checked)
    return replace(result, record=record)


def any_eye_valid(per_point: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None) -> bool:
    """Whether any eye of any point of a ``CALIB_RESULT`` was valid (the run's ``valid``)."""
    return bool(per_point) and any(
        eye is not None and eye.get("valid") for point in per_point for eye in (point["left"], point["right"])
    )


class EyeCounts(NamedTuple):
    """How many points each eye was valid on, of ``total`` (the Check accuracy view's lines)."""

    left: int
    right: int
    total: int


def eye_counts(per_point: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None) -> EyeCounts | None:
    """The valid points per eye of a ``CALIB_RESULT``; None without per-point data."""
    if not per_point:
        return None

    def valid(point: dict[str, Any], side: str) -> bool:
        return point.get(side) is not None and bool(point[side].get("valid"))

    return EyeCounts(
        sum(valid(p, "left") for p in per_point), sum(valid(p, "right") for p in per_point), len(per_point)
    )


def mean_error_px(per_point: tuple[dict[str, Any], ...] | None, geometry: Geometry) -> float | None:
    """The mean distance in monitor px between each valid eye's estimate and its target, over
    every valid eye of every point of a ``CALIB_RESULT``; None with no valid eye."""
    if not per_point:
        return None
    errors = []
    for row in per_point_errors_px(tuple(per_point), int(geometry.screen_w_px or 0), int(geometry.screen_h_px or 0)):
        for side in ("left", "right"):
            if row.get(side) is not None and row[side].get("valid") and row[f"{side}_error_px"] is not None:
                errors.append(row[f"{side}_error_px"])
    return sum(errors) / len(errors) if errors else None


def annotate_result(
    result: CalibrationResult, settings: CalibrationSettings, mode: str, geometry: Geometry | None
) -> CalibrationResult:
    """``result`` with the settings record and each point's score and error added. Without a
    geometry only the record is added.

    One error measure for every mode (D11, 4.8 R2): when ``CALIB_RESULT`` gave per-point data,
    the badge's ``mean_error_px`` and ``valid`` are computed from it, whichever screen made the
    run, and Control's own ``AVE_ERROR`` (the summary, retained state that does not follow the
    per-point data) is left to the timing log. A result without per-point data (``CALIB_RESULT``
    never came) keeps what the run reported."""
    if geometry is not None and result.per_point:
        scored = annotate_per_point(result.per_point, score_points(result.per_point, geometry))
        result = replace(
            result,
            per_point=scored,
            mean_error_px=mean_error_px(result.per_point, geometry),
            valid=any_eye_valid(result.per_point),
        )
    return replace(result, record=record_for(settings, mode))
