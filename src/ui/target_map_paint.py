"""Painting of the report's Target Map (SPEC-compass-task-flow.md 4D.7).

Pure drawing: given a :class:`MapModel` (read once from ``report.json``) and the
rectangle of the canvas, :func:`paint_map` draws the whole test (target marks, the
faint layout, each trial's fixation scanpath, the heat map) or one trial (target and
hitbox rings, the smoothed gaze path dark to light, numbered fixations). Everything is in **canvas-normalized**
coordinates, so a mark sits where the target was and a circle stays a circle (the
rectangle has the canvas's own aspect). Used by :class:`TargetMapWidget` for the
screen and its ``render_to_image`` for the PDF, so both draw the same.

Nothing here computes analysis: the scanpaths, paths, fixations, heat values and marks are
the report's. :func:`paint_symbol` draws the four marks of the map's legend with the same code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QPolygonF

from .report_format import hit_tolerance_px
from .wtmh_theme import ACCENT, BORDER, DANGER, INK, MUTED, PANEL_BG, SUCCESS

DEFAULT_ASPECT = 16 / 9
MIN_RADIUS = 0.02  # canvas-x units, for a mark whose radius the folder lacks
HEAT_FLOOR = 0.05  # heat values below this are transparent (4D.5)
PATH_COLOURS = ("#1F77B4", "#E08A00", "#7B52AB", "#8C564B", "#D6479A", "#17A2B8")
# The path of one trial runs from the first colour to the second with time. The second is still a
# strong teal (3:1 against white), so the newest end of the path does not wash out on the canvas.
TRIAL_PATH_DARK, TRIAL_PATH_LIGHT = QColor("#0F3D52"), QColor("#2B8CB0")
BADGE_PAD = 0.25  # a number badge reaches this fraction of the font's pixel size past its digits


@dataclass
class MapModel:
    """What the map draws, read from a report once (see :func:`build_model`)."""

    aspect: float = DEFAULT_ASPECT
    slots: list[tuple[float, float]] = field(default_factory=list)
    slot_radius: float = 0.0
    marks: list[dict[str, Any]] = field(default_factory=list)
    trials: list[dict[str, Any]] = field(default_factory=list)
    heat_image: QImage | None = None
    heat_empty: bool = True
    note: str | None = None
    tolerance_norm: float | None = None  # hitbox margin in canvas-x units, None if unknown
    moving: bool = False


def canvas_logical_width(geometry: dict[str, Any]) -> float | None:
    """The canvas width in logical px from the report's ``geometry`` block (physical px
    are divided by the display scale, as in ``Geometry.canvas_logical_size``)."""
    canvas = geometry.get("canvas_px") or [None, None]
    width = canvas[0]
    if not isinstance(width, (int, float)) or width <= 0:
        return None
    scale = geometry.get("display_scale_percent")
    if geometry.get("canvas_units") == "physical" and isinstance(scale, (int, float)) and scale > 0:
        return float(width) * 100.0 / scale
    return float(width)


def heat_colour(value: float) -> QColor:
    """Blue (cool) to red (hot), more opaque as it heats; transparent below the floor."""
    if value < HEAT_FLOOR:
        return QColor(0, 0, 0, 0)
    value = min(1.0, value)
    colour = QColor.fromHsvF((1.0 - value) * 0.66, 0.9, 1.0)
    colour.setAlphaF(0.15 + 0.65 * value)
    return colour


def heat_image(heat: dict[str, Any]) -> QImage | None:
    """The report's ``heat`` block as a small ARGB image (one pixel per bin), or
    ``None`` for an empty map or data that does not match its size."""
    width, height, data = heat.get("w"), heat.get("h"), heat.get("data")
    if heat.get("empty") or not data or not isinstance(width, int) or not isinstance(height, int):
        return None
    if width * height != len(data):
        return None
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for i, value in enumerate(data):
        if isinstance(value, (int, float)) and value >= HEAT_FLOOR:
            image.setPixelColor(i % width, i // width, heat_colour(float(value)))
    return image


def build_model(report: dict[str, Any] | None) -> MapModel:
    """Read the map's inputs from ``report`` (``None`` gives an empty map)."""
    if not report:
        return MapModel()
    geometry, mapping = report.get("geometry", {}), report.get("map", {})
    aspect = mapping.get("aspect") or geometry.get("canvas_aspect")
    if not isinstance(aspect, (int, float)) or aspect <= 0:
        aspect = DEFAULT_ASPECT
    marks = [m for m in mapping.get("marks", []) if m.get("x") is not None and m.get("y") is not None]
    trials = list(report.get("trials", []))
    radii = sorted(
        t.get("target", {}).get("radius_norm_x") or 0.0 for t in trials
    )
    radii = [r for r in radii if r > 0]
    slot_radius = radii[len(radii) // 2] if radii else MIN_RADIUS
    slots = [
        (float(s[0]), float(s[1]))
        for s in (mapping.get("slots") or [])
        if isinstance(s, (list, tuple)) and len(s) == 2
    ]
    logical_w = canvas_logical_width(geometry)
    tolerance = hit_tolerance_px(report) if logical_w else None
    heat = report.get("heat", {})
    return MapModel(
        aspect=float(aspect),
        slots=slots,
        slot_radius=slot_radius,
        marks=marks,
        trials=trials,
        heat_image=heat_image(heat),
        heat_empty=bool(heat.get("empty", True)),
        note=mapping.get("note"),
        tolerance_norm=None if not logical_w else tolerance / logical_w,
        moving=report.get("session", {}).get("task_id") == "follow_moving",
    )


# -- drawing -------------------------------------------------------------------------


def _point(rect: QRectF, x: float, y: float) -> QPointF:
    return QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height())


def _pen(colour: QColor | str, width: float, style: Qt.PenStyle = Qt.PenStyle.SolidLine) -> QPen:
    pen = QPen(QColor(colour), max(1.0, width))
    pen.setStyle(style)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _alpha(colour: str, alpha: int) -> QColor:
    out = QColor(colour)
    out.setAlpha(alpha)
    return out


def fit_font(base: QFont, text: str, size: float, max_width: float) -> tuple[QFont, QFontMetricsF, float]:
    """The bold font a label of ``text`` is drawn in: ``size`` px, shrunk to fit ``max_width``
    (no smaller than 7 px). Returns ``(font, its metrics, the text's width)``."""
    font = QFont(base)
    font.setBold(True)
    font.setPixelSize(max(7, round(size)))
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(text)
    if width > max_width > 0:
        font.setPixelSize(max(7, round(font.pixelSize() * max_width / width)))
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text)
    return font, metrics, width


def digits_height(font: QFont, metrics: QFontMetricsF) -> float:
    """The height the digits of ``font`` occupy (the label is centred on it)."""
    return max(metrics.ascent() - metrics.descent(), 0.6 * font.pixelSize())


def badge_pill(centre: QPointF, font: QFont, metrics: QFontMetricsF, width: float) -> QRectF:
    """The pill behind a label's digits: the text's width and the digits' height plus
    :data:`BADGE_PAD` of the font's pixel size on every side."""
    pad = BADGE_PAD * font.pixelSize()
    height = digits_height(font, metrics)
    return QRectF(centre.x() - width / 2 - pad, centre.y() - height / 2 - pad, width + 2 * pad, height + 2 * pad)


def _label(
    p: QPainter,
    centre: QPointF,
    text: str,
    colour: str,
    max_width: float,
    size: float,
    badge: tuple[QColor | str, QColor | str] | None = None,
) -> None:
    """``text`` centred on ``centre``, shrunk to fit ``max_width`` (no smaller than 7 px).

    ``badge`` is ``(fill, outline)`` of a small pill drawn behind the digits, so the number
    stays readable over whatever is under it (the X of a missed target, the gaze path)."""
    if not text:
        return
    font, metrics, width = fit_font(p.font(), text, size, max_width)
    p.setFont(font)
    if badge is not None:
        pill = badge_pill(centre, font, metrics, width)
        p.setPen(_pen(badge[1], 1))
        p.setBrush(QColor(badge[0]))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(colour, 1))
    p.drawText(QPointF(centre.x() - width / 2, centre.y() + digits_height(font, metrics) / 2), text)


def _circle(p: QPainter, centre: QPointF, radius: float) -> None:
    p.drawEllipse(centre, radius, radius)


def _paint_mark(p: QPainter, rect: QRectF, mark: dict[str, Any], unit: float) -> None:
    centre = _point(rect, mark["x"], mark["y"])
    radius = max(mark.get("r") or 0.0, MIN_RADIUS) * rect.width()
    outcome = mark.get("outcome")
    badge = None
    p.setBrush(Qt.BrushStyle.NoBrush)
    if outcome == "hit":
        p.setPen(_pen(SUCCESS, 2 * unit))
        p.setBrush(_alpha(SUCCESS, 150))
        _circle(p, centre, radius)
        text_colour = "#FFFFFF"
    elif outcome == "timeout":
        p.setPen(_pen(_alpha(DANGER, 110), unit))
        _circle(p, centre, radius)
        p.setPen(_pen(DANGER, 3 * unit))
        d = radius * 0.7
        p.drawLine(QPointF(centre.x() - d, centre.y() - d), QPointF(centre.x() + d, centre.y() + d))
        p.drawLine(QPointF(centre.x() - d, centre.y() + d), QPointF(centre.x() + d, centre.y() - d))
        text_colour = INK
        badge = (PANEL_BG, _alpha(DANGER, 170))  # drawn after the X: the number stays readable
    else:  # skipped (or an outcome the report could not tell): a dashed grey ring
        p.setPen(_pen(MUTED, 2 * unit, Qt.PenStyle.DashLine))
        _circle(p, centre, radius)
        text_colour = INK
    p.setBrush(Qt.BrushStyle.NoBrush)
    size = min(26 * unit, max(9.0, radius * 0.75))
    _label(p, centre, str(mark.get("label", "")), text_colour, 1.7 * radius, size, badge)


def _paint_slots(p: QPainter, rect: QRectF, model: MapModel, unit: float) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(_alpha(MUTED, 90), unit, Qt.PenStyle.DashLine))
    for x, y in model.slots:
        _circle(p, _point(rect, x, y), model.slot_radius * rect.width())


def _paint_track(p: QPainter, rect: QRectF, track: list[list[float]], unit: float) -> None:
    if len(track) < 2:
        return
    p.setPen(_pen(_alpha(MUTED, 120), 2 * unit))
    p.drawPolyline(QPolygonF([_point(rect, x, y) for x, y in track]))


def _paint_scanpaths(p: QPainter, rect: QRectF, model: MapModel, unit: float) -> None:
    """The whole test's fixation scanpaths (V2): per trial, one dot at each fixation's
    centroid, joined by straight lines in time order, in the trial's own colour. It is not
    the raw gaze, so fixational tremor does not scribble the map."""
    for trial in model.trials:
        colour = PATH_COLOURS[(int(trial.get("trial") or 1) - 1) % len(PATH_COLOURS)]
        points = [
            _point(rect, pt[0], pt[1])
            for pt in trial.get("scanpath") or []
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(points) >= 2:
            p.setPen(_pen(_alpha(colour, 190), 1.5 * unit))
            p.drawPolyline(QPolygonF(points))
        p.setPen(_pen("#FFFFFF", unit))
        p.setBrush(QColor(colour))
        for point in points:
            _circle(p, point, max(4.5 * unit, 3.0))
        p.setBrush(Qt.BrushStyle.NoBrush)


def _blend(t: float) -> QColor:
    a, b = TRIAL_PATH_DARK, TRIAL_PATH_LIGHT
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def _star(centre: QPointF, radius: float) -> QPolygonF:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = radius if i % 2 == 0 else radius * 0.45
        points.append(QPointF(centre.x() + r * math.cos(angle), centre.y() + r * math.sin(angle)))
    return QPolygonF(points)


def _paint_trial(p: QPainter, rect: QRectF, model: MapModel, trial: dict[str, Any], unit: float) -> None:
    """One trial: the target with its dashed hitbox ring, the gaze path dark to light by
    time, fixation circles (radius grows with duration) numbered in order, the onset
    (S) and, for a hit, the selection (star) at the path's two ends."""
    target = trial.get("target", {})
    outcome = trial.get("outcome")
    if model.moving:
        _paint_track(p, rect, trial.get("track") or [], unit)
    x, y = target.get("x"), target.get("y")
    if model.moving and target.get("end_x") is not None and target.get("end_y") is not None:
        x, y = target["end_x"], target["end_y"]
    if x is not None and y is not None:
        centre = _point(rect, x, y)
        radius = max(target.get("radius_norm_x") or 0.0, MIN_RADIUS) * rect.width()
        colour = SUCCESS if outcome == "hit" else DANGER if outcome == "timeout" else MUTED
        p.setBrush(_alpha(colour, 60) if outcome == "hit" else Qt.BrushStyle.NoBrush)
        p.setPen(_pen(colour, 2.5 * unit))
        _circle(p, centre, radius)
        if model.tolerance_norm is not None:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(_pen(MUTED, 1.5 * unit, Qt.PenStyle.DashLine))
            _circle(p, centre, radius + model.tolerance_norm * rect.width())

    points = [pt for segment in trial.get("path", []) for pt in segment]
    total = max(1, len(points) - 1)
    index = 0
    for segment in trial.get("path", []):
        for a, b in zip(segment, segment[1:], strict=False):
            p.setPen(_pen(_blend(index / total), 2.5 * unit))
            p.drawLine(_point(rect, *a), _point(rect, *b))
            index += 1
        index += 1  # the jump to the next polyline is not drawn

    for number, (fx, fy, dur_ms) in enumerate(trial.get("fixations", {}).get("items", []), start=1):
        radius = rect.width() * min(0.03, max(0.006, float(dur_ms) * 0.00004))
        centre = _point(rect, fx, fy)
        # Opaque white under the tint, so the gaze path (drawn before) never shows through
        # a fixation, and a badge behind the number, so the number never sits on the path.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(PANEL_BG))
        _circle(p, centre, radius)
        p.setPen(_pen(ACCENT, 1.5 * unit))
        p.setBrush(_alpha(ACCENT, 70))
        _circle(p, centre, radius)
        # The badge may be wider than a short fixation's circle, so its number is not shrunk to it.
        _label(p, centre, str(number), INK, max(1.8 * radius, 12.0), max(9.0, radius), (PANEL_BG, ACCENT))

    if points:
        start = _point(rect, *points[0])
        s_radius = max(13 * unit, 10.0)  # big enough for a legible letter (it was 8 design px)
        p.setPen(_pen(INK, 2 * unit))
        p.setBrush(QColor(PANEL_BG))
        _circle(p, start, s_radius)
        _label(p, start, "S", INK, 1.7 * s_radius, max(17 * unit, 13.0))
        if outcome == "hit" and len(points) > 1:
            p.setPen(_pen(INK, unit))
            p.setBrush(QColor("#F2B705"))
            p.drawPolygon(_star(_point(rect, *points[-1]), 11 * unit))
    p.setBrush(Qt.BrushStyle.NoBrush)


LEGEND_KINDS = ("hit", "timeout", "skipped", "slot")


def paint_symbol(p: QPainter, rect: QRectF, kind: str) -> None:
    """One of the map's four marks, centred in ``rect`` (the legend's icon): ``hit`` (green
    circle), ``timeout`` (red X), ``skipped`` (dashed ring) or ``slot`` (a faint layout
    circle). The first three are the map's own drawing (:func:`_paint_mark`, no number); the
    layout circle is the map's too, a little stronger because it is alone on the box."""
    unit = max(0.5, min(rect.width(), rect.height()) / 40.0)  # a map is 900 px wide for unit 1
    side = min(rect.width(), rect.height())
    centre = rect.center()
    square = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if kind == "slot":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(_alpha(MUTED, 150), 1.4 * unit, Qt.PenStyle.DashLine))
        _circle(p, centre, 0.42 * side)
    else:
        _paint_mark(p, square, {"x": 0.5, "y": 0.5, "r": 0.42, "outcome": kind, "label": ""}, unit)
    p.restore()


def paint_map(
    p: QPainter,
    rect: QRectF,
    model: MapModel,
    *,
    targets: bool = True,
    path: bool = False,
    heat: bool = False,
    trial: int | None = None,
) -> None:
    """Draw the map inside ``rect`` (the canvas's rectangle, already at its aspect).

    ``trial`` is an index into ``model.trials`` for the single-trial view (which
    ignores the three overlay flags); otherwise the whole test is drawn with the
    overlays asked for.
    """
    unit = max(0.5, rect.width() / 900.0)  # one design px at 900 px wide
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.fillRect(rect, QColor(PANEL_BG))
    p.setClipRect(rect)
    one = model.trials[trial] if trial is not None and 0 <= trial < len(model.trials) else None
    if one is not None:
        _paint_slots(p, rect, model, unit)
        _paint_trial(p, rect, model, one, unit)
    else:
        if heat and model.heat_image is not None:
            p.drawImage(rect, model.heat_image)
        if targets:
            _paint_slots(p, rect, model, unit)
            if model.moving:
                for t in model.trials:
                    _paint_track(p, rect, t.get("track") or [], unit)
        if path:
            _paint_scanpaths(p, rect, model, unit)
        if targets:
            for mark in model.marks:
                _paint_mark(p, rect, mark, unit)
        if heat and model.heat_image is None:
            _label(p, rect.center(), "No gaze on the canvas for the heat map", MUTED, rect.width() * 0.8, 14 * unit)
    p.setClipping(False)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(BORDER, 1))
    p.drawRect(rect)
    p.restore()

