"""Fullscreen subject-facing canvas (PySide6).

Renders the active target, the gaze cursor, the dwell progress ring, and simple
hit particle feedback. Imports PySide6 at module load, so it is only imported by
the GUI path (:mod:`src.app`), never by the headless pipeline or tests.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..engine.target_size import ICON_DRAW_FRAC, grid_cell_geometry
from ..inputs.base import norm_to_px, outside_distance
from .canvas_cursor import (
    _CURSOR_ALPHA,
    _CURSOR_ALPHA_DIM,
    _CURSOR_CORE_COLOR,
    _CURSOR_HALO_COLOR,
    _CURSOR_HALO_STROKE_PX,
    _CURSOR_RADIUS_PX,
    _CURSOR_STROKE_PX,
    _clamp_to_canvas,
)
from .canvas_shapes import SHAPE_CIRCLE, shape_path

# The target glow (SPEC-input-selection-and-follow.md H3, I5e, I10): a soft halo that
# fades out over this fraction of the target's own radius (never less than the px
# floor), in the theme's particle colour. It stands in for the dwell ring, which a
# switch or a follow test does not have, so it must read at a glance: strong at the
# target's edge and fading to nothing.
_GLOW_EXTRA_FRAC = 0.6
_GLOW_EXTRA_MIN_PX = 28.0
_GLOW_ALPHA = 200


class TaskCanvas(QWidget):
    # The switch (SPEC-input-selection-and-follow.md 4.2): a left press on the canvas,
    # on button down. The app connects them to ``SwitchInput``; a press on the run
    # bar never reaches the canvas, so it stays an operator action (I6).
    switchPressed = Signal()
    switchReleased = Signal()

    def __init__(self, theme: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme or {}
        self.setMouseTracking(True)
        self._bg = QColor(self.theme.get("background", "#101418"))

        # Render state, updated by the app loop each frame.
        self.target_xy_norm: tuple[float, float] | None = None
        self.target_radius_px: float = 90.0
        self.target_color = QColor(self.theme.get("target_default", "#ff5252"))
        self.layout_slots: list[tuple[float, float]] = []
        self.cursor_xy_norm: tuple[float, float] = (0.5, 0.5)
        self.cursor_valid: bool = False
        # Last position gaze was actually inside the canvas, which off-canvas
        # gaze freezes at (see _cursor_draw_position).
        self._last_on_canvas_xy: tuple[float, float] | None = None
        self.dwell_progress: float = 0.0
        self.selectable: bool = True
        self.show_cursor: bool = True
        self.show_progress_ring: bool = True
        self.show_instant_feedback: bool = True
        # The glow around the target while the pointer is on it (set by the app: on only
        # for a Switch or a Follow test with "Glow on target" ticked).
        self.show_glow: bool = False
        # Whether a left press is the switch; set by the app (Selection = Switch).
        self.switch_press_enabled: bool = False
        self.on_target: bool = False
        self._particles: list[tuple[float, float, float]] = []  # x_norm, y_norm, age

        # Scene (task-level layout description, ported from resources/diki --
        # see SPEC-diki-design-audit.md S3.1). Set once per task run via
        # AssessmentApp; default "single" matches pre-existing rendering
        # (just the active target + any generic layout_slots outlines) so
        # tasks not yet ported to a dedicated mode are unaffected.
        self.scene: dict = {"mode": "single"}
        self.active_slot: int = -1
        self._trail: list[tuple[float, float]] = []  # "moving" mode only

        self.paused: bool = False  # only a calm "Paused" (4C.5): no target, no cursor

    # -- state updates from the app loop ----------------------------------

    def set_paused(self, paused: bool) -> None:
        """Show or leave the "Paused" screen (SPEC-compass-task-flow.md 4C.5). The
        fading trail is dropped: the trial after a pause starts from its first spot."""
        if bool(paused) == self.paused:
            return
        self.paused = bool(paused)
        if paused:
            self._trail.clear()
        self.update()

    def set_frame(
        self,
        target_xy_norm: tuple[float, float] | None,
        target_radius_px: float,
        cursor_xy_norm: tuple[float, float],
        cursor_valid: bool,
        dwell_progress: float,
        selectable: bool = True,
        layout_slots: list[tuple[float, float]] | None = None,
        on_target: bool = False,
        scene: dict | None = None,
        active_slot: int = -1,
    ) -> None:
        self.target_xy_norm = target_xy_norm
        self.target_radius_px = target_radius_px
        self.cursor_xy_norm = cursor_xy_norm
        self.cursor_valid = cursor_valid
        self.dwell_progress = dwell_progress
        self.selectable = selectable
        self.layout_slots = layout_slots or []
        self.on_target = on_target
        if scene is not None:
            self.scene = scene
        self.active_slot = active_slot

        # Fading motion-trail history for "moving" mode (ported from
        # resources/diki, SPEC-diki-design-audit.md S3.5/S4). Cleared
        # whenever the target isn't shown (e.g. between trials during ITI)
        # so the trail never bridges a teleport to the next trial's start.
        if self.scene.get("mode") == "moving" and target_xy_norm is not None:
            self._trail.append(target_xy_norm)
            # ~1.5s of history at 60Hz -- long enough to read as a path, short
            # enough not to overlap the target's own next lap on a small orbit.
            if len(self._trail) > 90:
                self._trail.pop(0)
        elif target_xy_norm is None and self._trail:
            self._trail.clear()

        self.update()

    def burst(self, x_norm: float, y_norm: float) -> None:
        """Trigger a hit particle burst at a normalized position."""
        self._particles.append((x_norm, y_norm, 0.0))

    # -- the switch --------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """A left press is the switch while ``switch_press_enabled``; any other button
        (and every press otherwise) is left to Qt's default."""
        if self.switch_press_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.switchPressed.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.switchReleased.emit()
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Losing the focus drops a held switch: its key-up goes elsewhere."""
        self.switchReleased.emit()
        super().focusOutEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._bg)

        if self.paused:
            self._draw_paused(painter, w, h)
            painter.end()
            return

        mode = self.scene.get("mode", "single")
        if mode == "icons":
            self._draw_icon_scene(painter, w, h)
        elif mode == "grid":
            self._draw_grid_scene(painter, w, h)
        elif mode == "moving":
            self._draw_trail(painter, w, h)
        elif self.layout_slots:
            self._draw_layout_slots(painter, w, h)

        if self.target_xy_norm is not None:
            tx, ty = norm_to_px(*self.target_xy_norm, w, h)
            # Behind the target, so the target itself stays crisp (gated on `selectable`
            # for the same reason as the instant ring below).
            if self.show_glow and self.on_target and self.selectable:
                self._draw_glow(painter, tx, ty)
            self._draw_target(painter, tx, ty)
            # Gated on `selectable` too (SPEC-follow-moving-selection.md S5.4):
            # without it this told the child "you're on it" on a target the
            # task had already decided could not be selected yet -- the same
            # contradictory-affordance family as the dwell ring filling
            # outside follow_moving's selection window. No other task has a
            # window, so `selectable` is always True for them and nothing
            # changes there.
            if self.show_instant_feedback and self.on_target and self.selectable:
                self._draw_instant_feedback(painter, tx, ty)
            if self.show_progress_ring and self.dwell_progress > 0:
                self._draw_progress_ring(painter, tx, ty)

        self._draw_particles(painter, w, h)

        if self.show_cursor:
            placed = self._cursor_draw_position()
            if placed is not None:
                (xn, yn), frozen = placed
                cx, cy = norm_to_px(xn, yn, w, h)
                ccx, ccy, _ = _clamp_to_canvas(cx, cy, w, h)
                self._draw_cursor(painter, ccx, ccy, dim=frozen or not self.cursor_valid)

        painter.end()

    def _draw_paused(self, painter: QPainter, w: int, h: int) -> None:
        """A centred "Paused" in the theme's contrasting (ring) colour."""
        font = painter.font()
        font.setPixelSize(max(24, min(w, h) // 14))
        painter.setFont(font)
        painter.setPen(QColor(self.theme.get("cursor_color", "#ffffff")))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Paused")

    def _draw_layout_slots(self, painter: QPainter, w: int, h: int) -> None:
        """Draw the unlit candidate positions of a multi-item task.

        click_grid's 3x3 cells and scanning's icon row are otherwise invisible
        between trials — only the single active target is ever painted — which
        made the two tasks (and click_static) look identical to an observer.
        This paints every other slot as a dim outline so the layout itself is
        visible, while the active target (painted afterwards) stays the only
        filled, bright shape.
        """
        r = self.target_radius_px
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(0.25)
        for xn, yn in self.layout_slots:
            if self.target_xy_norm is not None and math.isclose(xn, self.target_xy_norm[0], abs_tol=1e-6) and math.isclose(
                yn, self.target_xy_norm[1], abs_tol=1e-6
            ):
                continue  # the active slot is drawn as the real target instead
            sx, sy = norm_to_px(xn, yn, w, h)
            painter.drawEllipse(QPointF(sx, sy), r, r)
        painter.setOpacity(1.0)

    def _draw_grid_scene(self, painter: QPainter, w: int, h: int) -> None:
        """Draw every grid cell as a real rounded-rect, not a dim circle.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.3/S4) --
        click_grid mimics a communication board, so the whole board should be
        visible, not just the lit cell. The active cell is drawn afterwards
        by _draw_target on top; this only paints the (n-1) inactive cells.
        """
        cells = self.scene.get("cells") or []
        cw = float(self.scene.get("cell_w", 0.0)) * w
        ch = float(self.scene.get("cell_h", 0.0)) * h
        if not cells or cw <= 0 or ch <= 0:
            return

        # The inset the task fits the target circle and hit-tests against
        # (ClickGridTask._geometry; SPEC-target-size-and-motion-paths.md S4.3,
        # SPEC-grid-cell-gap.md S4.4). A scene without one is the standard board.
        pad = self.scene.get("cell_inset_px")
        if pad is None:
            pad = grid_cell_geometry(cw, ch).inset
        idle = QColor(self.theme.get("cursor_color", "#ffffff"))
        idle.setAlpha(38)
        for i, (xn, yn) in enumerate(cells):
            if i == self.active_slot:
                continue  # the active cell is drawn as the real target instead
            cx, cy = norm_to_px(xn, yn, w, h)
            rect = QRectF(cx - cw / 2 + pad, cy - ch / 2 + pad, cw - 2 * pad, ch - 2 * pad)
            painter.setPen(QPen(idle, 2))
            painter.setBrush(QColor(255, 255, 255, 16))
            painter.drawRoundedRect(rect, 14, 14)

    def _draw_trail(self, painter: QPainter, w: int, h: int) -> None:
        """Fading trail behind a moving target, so pursuit is visible.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.5/S4) --
        distinguishes "tracked it" from "waited where it would arrive."
        History is accumulated in set_frame, not here.
        """
        if len(self._trail) < 2:
            return
        color = QColor(self.target_color)
        n = len(self._trail)
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (xn, yn) in enumerate(self._trail[:-1]):
            frac = (i + 1) / n
            color.setAlpha(int(120 * frac))
            painter.setBrush(color)
            px, py = norm_to_px(xn, yn, w, h)
            radius = self.target_radius_px * 0.34 * frac
            painter.drawEllipse(QPointF(px, py), radius, radius)

    def _draw_icon_scene(self, painter: QPainter, w: int, h: int) -> None:
        """Draw the distractor field; the cued slot is drawn by _draw_target.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.4/S4).
        """
        slots = self.scene.get("slots") or []
        shapes = self.scene.get("shapes") or []
        if not slots:
            return

        r = self.target_radius_px * ICON_DRAW_FRAC
        distractor = QColor(self.theme.get("cursor_color", "#ffffff"))
        distractor.setAlpha(64)
        for i, (xn, yn) in enumerate(slots):
            if i == self.active_slot:
                continue  # the target itself is drawn on top, in colour
            cx, cy = norm_to_px(xn, yn, w, h)
            shape = shapes[i] if i < len(shapes) else SHAPE_CIRCLE
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(distractor)
            painter.drawPath(shape_path(cx, cy, r, shape))

    def _ring_base_radius(self) -> float:
        """Radius the selectable outline and the instant / dwell rings are drawn
        around -- the radius of what is actually painted (SPEC-target-visual-
        fixes.md F2 a). In the ``icons`` scene the cued icon is painted at
        ``ICON_DRAW_FRAC`` of the hit radius (see :meth:`_draw_target`), so the
        rings follow that, not the hit radius, and stay clear of neighbouring
        icons; every other scene paints the target at ``target_radius_px``."""
        if self.scene.get("mode", "single") == "icons" and self.active_slot >= 0:
            return self.target_radius_px * ICON_DRAW_FRAC
        return self.target_radius_px

    def _draw_target(self, painter: QPainter, x: float, y: float) -> None:
        r = self.target_radius_px
        color = self.target_color if self.selectable else self.target_color.darker(180)
        grad = QRadialGradient(QPointF(x, y), r)
        grad.setColorAt(0.0, color.lighter(130))
        grad.setColorAt(1.0, color)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)

        mode = self.scene.get("mode", "single")
        if mode == "icons" and self.active_slot >= 0:
            # Keep the target's silhouette so the child matches shape, not
            # just brightness/colour -- a plain circle would turn a search
            # task into pop-out. Ported from resources/diki.
            shapes = self.scene.get("shapes") or []
            shape = shapes[self.active_slot] if self.active_slot < len(shapes) else SHAPE_CIRCLE
            painter.drawPath(shape_path(x, y, r * ICON_DRAW_FRAC, shape))
        else:
            painter.drawEllipse(QPointF(x, y), r, r)

        if self.selectable:
            # bright "catch me now" outline during the selectable window.
            # Must be a freshly-constructed QPen, not painter.pen() mutated in
            # place -- the painter's current pen is NoPen (just used for the
            # gradient fill above), and changing a NoPen pen's color/width
            # does not change its style, so the outline silently never drew.
            painter.setPen(QPen(QColor("#ffffff"), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring = self._ring_base_radius() + 4
            painter.drawEllipse(QPointF(x, y), ring, ring)

    def _draw_glow(self, painter: QPainter, x: float, y: float) -> None:
        """A soft halo round the target while the pointer is on it (SPEC-input-
        selection-and-follow.md H3): opaque at the painted edge, fading to nothing
        over :data:`_GLOW_EXTRA_FRAC` of the radius. Drawn only while ``on_target``,
        so a child who looks away sees it go."""
        r = self._ring_base_radius()
        outer = r + max(_GLOW_EXTRA_MIN_PX, r * _GLOW_EXTRA_FRAC)
        color = QColor(self.theme.get("particle_color", "#ffd54f"))
        grad = QRadialGradient(QPointF(x, y), outer)
        color.setAlpha(_GLOW_ALPHA)
        grad.setColorAt(max(0.0, r / outer - 0.02), color)
        color.setAlpha(0)
        grad.setColorAt(1.0, color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(QPointF(x, y), outer, outer)

    def _draw_instant_feedback(self, painter: QPainter, x: float, y: float) -> None:
        """Immediate acknowledgment that gaze is on the target right now.

        SPEC-2026-09-02.md item 2: the only prior on-target feedback was the
        dwell progress ring, which needs threshold_ms (800ms default) of
        accumulated dwell before it's visibly obvious -- so "gaze lands on
        target" and "nothing happens for the better part of a second" looked
        identical. This is a full-brightness ring drawn the instant on_target
        is true, not gated by dwell progress at all.
        """
        r = self._ring_base_radius() + 10
        painter.setPen(QPen(QColor(self.theme.get("cursor_color", "#ffffff")), 5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), r, r)

    def _draw_progress_ring(self, painter: QPainter, x: float, y: float) -> None:
        r = self._ring_base_radius() + 16
        # Same NoPen-carryover fix as _draw_instant_feedback/_draw_target: a
        # fresh QPen, not painter.pen() mutated in place -- this arc was
        # silently never drawn before, which is very likely the real cause
        # behind SPEC-2026-09-02.md item 1's "toggling dwell.progress_ring
        # produced no visible change" observation.
        painter.setPen(QPen(QColor(self.theme.get("cursor_color", "#ffffff")), 8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span = int(-360 * 16 * max(0.0, min(1.0, self.dwell_progress)))
        painter.drawArc(int(x - r), int(y - r), int(2 * r), int(2 * r), 90 * 16, span)

    def _cursor_draw_position(self) -> tuple[tuple[float, float], bool] | None:
        """Where to draw the gaze marker, and whether that position is frozen.

        Returns ``None`` when there is nothing to draw at all -- only before
        the very first on-canvas reading of a run, when no position has ever
        been established to freeze at.

        **Off-canvas gaze freezes the cursor in place** rather than tracking it
        to the nearest edge (SPEC-gaze-cursor-redesign.md S10, revising S4.2).
        The earlier design clamped to the edge and faded by distance; the user
        asked for parity with Gazepoint Control instead, where looking away
        simply stops the marker. That makes "looking away" and "tracking lost"
        visually identical, which is a deliberate, accepted consequence --
        Gazepoint Control does not distinguish them either, and it removes the
        distance threshold this otherwise needed.

        Hit-testing is untouched by any of this. ``BaseTask`` still sees the
        true, unfrozen, possibly out-of-range position, so freezing can never
        cause a selection the child did not actually make -- freezing is the
        renderer's decision alone (the same separation S6 of
        SPEC-gui-audit-2026-09-10.md established for the clamp).
        """
        xy = self.cursor_xy_norm
        if outside_distance(*xy) > 0.0:
            if self._last_on_canvas_xy is None:
                return None
            return self._last_on_canvas_xy, True
        self._last_on_canvas_xy = xy
        return xy, False

    def _draw_cursor(self, painter: QPainter, x: float, y: float, dim: bool = False) -> None:
        """Draw the gaze marker: a small hollow ring with a contrasting fringe.

        Two states, deliberately only two (S10): a live on-canvas reading at
        full strength, and a *frozen* one -- dimmed -- covering both tracking
        loss and gaze that has left the canvas.

        Drawn as two concentric strokes at the same radius, wider first: the
        halo's extra width survives on both sides of the narrower core, so the
        marker carries its own contrast onto any backdrop instead of depending
        on the theme it happens to be drawn over.
        """
        alpha = _CURSOR_ALPHA_DIM if (dim or not self.cursor_valid) else _CURSOR_ALPHA
        centre = QPointF(x, y)
        # Hollow: stroke only, no fill, so the target underneath stays visible.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        halo = QColor(_CURSOR_HALO_COLOR)
        halo.setAlpha(alpha)
        painter.setPen(QPen(halo, _CURSOR_HALO_STROKE_PX))
        painter.drawEllipse(centre, _CURSOR_RADIUS_PX, _CURSOR_RADIUS_PX)
        core = QColor(_CURSOR_CORE_COLOR)
        core.setAlpha(alpha)
        painter.setPen(QPen(core, _CURSOR_STROKE_PX))
        painter.drawEllipse(centre, _CURSOR_RADIUS_PX, _CURSOR_RADIUS_PX)

    def _draw_particles(self, painter: QPainter, w: int, h: int) -> None:
        if not self._particles:
            return
        color = QColor(self.theme.get("particle_color", "#ffd54f"))
        alive: list[tuple[float, float, float]] = []
        for (xn, yn, age) in self._particles:
            age += 1.0
            if age > 20:
                continue
            cx, cy = norm_to_px(xn, yn, w, h)
            for k in range(8):
                ang = math.tau * k / 8
                rad = age * 6
                color.setAlpha(max(0, int(255 * (1 - age / 20))))
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang)), 6, 6
                )
            alive.append((xn, yn, age))
        self._particles = alive
