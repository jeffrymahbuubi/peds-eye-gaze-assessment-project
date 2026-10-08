"""Coordinate frames and visual angle for the per-test report
(SPEC-compass-task-flow.md 4D.5).

Three frames meet in a report and must never be mixed without a conversion:

* **Gaze** (``gaze_stream.csv``, ``all_gaze.csv``) is normalized to the *tracked
  monitor* -- the screen Gazepoint Control reports via ``SCREEN_SIZE``.
* **Targets** (``trials.csv``, ``target_track.csv``) are normalized to the task
  *canvas*, the sub-rectangle of the monitor the scene was drawn in.
* ``target_radius_px`` is in Qt *logical* px; ``metadata.canvas_*_px`` are in
  *physical* px when ``canvas_units == "physical"`` and logical px on older runs
  (the same numbers at 100 % scale).

:class:`Geometry` reads the numbers from ``metadata.json`` and is the one place
the conversions live, with the same maths as ``BaseTask.pointer_to_canvas_px``.
The monitor-to-canvas ratio is unit-free (all four numbers physical, or all
logical), so mixed old and new folders both work.

Pure and Qt-free, like the rest of ``src/data``. Any value a folder lacks stays
``None`` and the angle helpers then return ``None`` -- a degree is never guessed
(the report shows a dash). :meth:`Geometry.for_visuals` is the one exception: the
gaze-path thinning and the heat-map blur need *some* scale, so they borrow the
reference rig's, flagged ``assumed``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

# The lab rig (24" 16:9, 650 mm): what an old folder with no geometry is drawn
# against, for display-only purposes (never for a reported number).
REFERENCE_SCREEN_PX = (1920.0, 1080.0)
REFERENCE_PHYSICAL_MM = (527.0, 296.0)
REFERENCE_DISTANCE_MM = 650.0


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 and math.isfinite(number) else None


@dataclass(frozen=True)
class Geometry:
    screen_w_px: float | None = None
    screen_h_px: float | None = None
    phys_w_mm: float | None = None
    phys_h_mm: float | None = None
    distance_mm: float | None = None
    canvas_w_px: float | None = None
    canvas_h_px: float | None = None
    offset_x_px: float = 0.0
    offset_y_px: float = 0.0
    canvas_units: str | None = None
    display_scale_percent: float | None = None
    # mm per Qt *logical* px (``metadata.target_size.mm_per_px``): the scale the
    # target radius is in. None when the run had no size preset.
    mm_per_px: float | None = None
    assumed: bool = False

    @classmethod
    def from_metadata(cls, meta: dict[str, Any] | None) -> Geometry:
        meta = meta or {}
        size = meta.get("target_size")
        mm_per_px = _positive(size.get("mm_per_px")) if isinstance(size, dict) else None
        try:
            off_x = float(meta.get("canvas_offset_x_px") or 0.0)
            off_y = float(meta.get("canvas_offset_y_px") or 0.0)
        except (TypeError, ValueError):
            off_x = off_y = 0.0
        return cls(
            screen_w_px=_positive(meta.get("screen_width_px")),
            screen_h_px=_positive(meta.get("screen_height_px")),
            phys_w_mm=_positive(meta.get("screen_physical_width_mm")),
            phys_h_mm=_positive(meta.get("screen_physical_height_mm")),
            distance_mm=_positive(meta.get("viewing_distance_mm")),
            canvas_w_px=_positive(meta.get("canvas_width_px")),
            canvas_h_px=_positive(meta.get("canvas_height_px")),
            offset_x_px=off_x,
            offset_y_px=off_y,
            canvas_units=meta.get("canvas_units"),
            display_scale_percent=_positive(meta.get("display_scale_percent")),
            mm_per_px=mm_per_px,
        )

    # -- what is known ------------------------------------------------------

    @property
    def has_canvas(self) -> bool:
        return all((self.screen_w_px, self.screen_h_px, self.canvas_w_px, self.canvas_h_px))

    @property
    def has_angles(self) -> bool:
        """True when monitor size in px and mm and the viewing distance are known,
        so a normalized distance can be turned into degrees."""
        return all(
            (self.screen_w_px, self.screen_h_px, self.phys_w_mm, self.phys_h_mm, self.distance_mm)
        )

    @property
    def aspect(self) -> float | None:
        """Canvas width over height (units cancel); None without canvas size."""
        if self.canvas_w_px and self.canvas_h_px:
            return self.canvas_w_px / self.canvas_h_px
        return None

    @property
    def mm_per_deg(self) -> float | None:
        """Millimetres on the screen per degree of visual angle at the viewing
        distance (small-angle, ``D * tan(1 deg)``)."""
        return self.distance_mm * math.tan(math.radians(1.0)) if self.distance_mm else None

    @property
    def px_per_deg(self) -> float | None:
        """Monitor px per degree (41.3 on the 1920 px / 527 mm / 650 mm rig)."""
        if not self.has_angles:
            return None
        mm_per_px = self.phys_w_mm / self.screen_w_px
        return self.mm_per_deg / mm_per_px

    # -- frames -------------------------------------------------------------

    def monitor_to_canvas_norm(self, x: float, y: float) -> tuple[float, float]:
        """Monitor-normalized gaze to canvas-normalized (``BaseTask`` maths).
        Not clamped: a value outside [0, 1] is real gaze off the canvas. With no
        canvas size known the canvas is taken to be the whole monitor."""
        if not self.has_canvas:
            return x, y
        return (
            (x * self.screen_w_px - self.offset_x_px) / self.canvas_w_px,
            (y * self.screen_h_px - self.offset_y_px) / self.canvas_h_px,
        )

    def canvas_to_monitor_norm(self, x: float, y: float) -> tuple[float, float]:
        """Inverse of :meth:`monitor_to_canvas_norm`."""
        if not self.has_canvas:
            return x, y
        return (
            (x * self.canvas_w_px + self.offset_x_px) / self.screen_w_px,
            (y * self.canvas_h_px + self.offset_y_px) / self.screen_h_px,
        )

    def canvas_logical_size(self) -> tuple[float, float] | None:
        """Canvas size in Qt logical px, the unit ``target_radius_px`` is in."""
        if not (self.canvas_w_px and self.canvas_h_px):
            return None
        if self.canvas_units == "physical" and self.display_scale_percent:
            factor = 100.0 / self.display_scale_percent
            return self.canvas_w_px * factor, self.canvas_h_px * factor
        return self.canvas_w_px, self.canvas_h_px

    def canvas_mm(self) -> tuple[float, float] | None:
        """Canvas width and height in mm; None unless :attr:`has_angles` and the
        canvas size is known."""
        if not (self.has_angles and self.canvas_w_px and self.canvas_h_px):
            return None
        return (
            self.canvas_w_px * self.phys_w_mm / self.screen_w_px,
            self.canvas_h_px * self.phys_h_mm / self.screen_h_px,
        )

    # -- visual angle -------------------------------------------------------

    def angle_deg(self, p: tuple[float, float], q: tuple[float, float]) -> float | None:
        """Visual angle between two *monitor*-normalized points: per-axis mm (so a
        non-square pixel is right), then ``2 * atan(chord / 2D)``. None when the
        geometry is incomplete."""
        if not self.has_angles:
            return None
        chord = math.hypot(
            (q[0] - p[0]) * self.phys_w_mm, (q[1] - p[1]) * self.phys_h_mm
        )
        return math.degrees(2.0 * math.atan(chord / (2.0 * self.distance_mm)))

    def canvas_angle_deg(self, p: tuple[float, float], q: tuple[float, float]) -> float | None:
        """Same for two *canvas*-normalized points."""
        return self.angle_deg(self.canvas_to_monitor_norm(*p), self.canvas_to_monitor_norm(*q))

    def px_to_deg(self, monitor_px: float) -> float | None:
        """A horizontal distance of ``monitor_px`` physical px as visual angle."""
        if not self.has_angles:
            return None
        chord = monitor_px * self.phys_w_mm / self.screen_w_px
        return math.degrees(2.0 * math.atan(chord / (2.0 * self.distance_mm)))

    def logical_px_to_deg(self, logical_px: float) -> float | None:
        """A distance of ``logical_px`` Qt logical px on the canvas (the unit of
        ``target_radius_px`` and of the task's pointer distances) as visual angle:
        ``2 * atan(mm / 2D)`` with ``mm = px * mm_per_px``. None without the run's
        ``target_size`` block (``mm_per_px``) or the viewing distance."""
        if not (self.mm_per_px and self.distance_mm) or logical_px < 0:
            return None
        return math.degrees(2.0 * math.atan(logical_px * self.mm_per_px / (2.0 * self.distance_mm)))

    def radius_to_diameter_deg(self, radius_px: float) -> float | None:
        """Diameter in degrees of a target of ``radius_px`` logical px:
        ``2 * atan(r_mm / D)``, the inverse of ``target_size.radius_px_for``.
        None without the run's ``target_size`` block or the viewing distance."""
        if not (self.mm_per_px and self.distance_mm) or radius_px <= 0:
            return None
        return math.degrees(2.0 * math.atan(radius_px * self.mm_per_px / self.distance_mm))

    # -- display-only fallback and serialization ----------------------------

    def for_visuals(self) -> Geometry:
        """This geometry with any missing monitor/physical/distance value taken
        from the reference rig, flagged ``assumed``. For thinning a drawn path and
        sizing the heat-map blur only; never for a number the report prints."""
        if self.has_angles:
            return self
        return replace(
            self,
            screen_w_px=self.screen_w_px or REFERENCE_SCREEN_PX[0],
            screen_h_px=self.screen_h_px or REFERENCE_SCREEN_PX[1],
            phys_w_mm=self.phys_w_mm or REFERENCE_PHYSICAL_MM[0],
            phys_h_mm=self.phys_h_mm or REFERENCE_PHYSICAL_MM[1],
            distance_mm=self.distance_mm or REFERENCE_DISTANCE_MM,
            assumed=True,
        )

    def as_dict(self) -> dict[str, Any]:
        """The ``report.json`` ``geometry`` block (rounded, None where unknown)."""
        px_per_deg = self.px_per_deg
        return {
            "screen_px": [self.screen_w_px, self.screen_h_px],
            "physical_mm": [self.phys_w_mm, self.phys_h_mm],
            "viewing_distance_mm": self.distance_mm,
            "canvas_px": [self.canvas_w_px, self.canvas_h_px],
            "canvas_offset_px": [self.offset_x_px, self.offset_y_px],
            "canvas_units": self.canvas_units,
            "display_scale_percent": self.display_scale_percent,
            "mm_per_px": self.mm_per_px,
            "px_per_deg": None if px_per_deg is None else round(px_per_deg, 3),
            "canvas_aspect": None if self.aspect is None else round(self.aspect, 5),
        }
