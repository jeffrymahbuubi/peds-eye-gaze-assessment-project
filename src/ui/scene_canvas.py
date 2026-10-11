"""The "scene" mode of the subject-facing canvas (SPEC-scene-cause-effect-task.md 4.4, 4.5, N1, N3, N5).

:class:`SceneView` is not a widget: :class:`~src.ui.canvas.TaskCanvas` hands it the painter and the
scene description of ``ChoiceMakingTask.scene_spec()`` and it draws the background, every object
layer at its idle or animated transform, the particles of an effect, the idle blinks and the eight
buttons (:mod:`.scene_buttons`). What moves, and where, comes from the Qt-free
:mod:`~src.tasks.choice_scene`, the same functions the look-back AOI uses.

* **Cached scene (N5).** Layers that are not animating are drawn once into pixmaps, split at the
  animating layers so z order is kept (the bike rides behind the bush); each frame blits those and
  draws only the animating layers over them. The cache is keyed by the set of animating layers and
  the scene size, kept for a few keys, and warmed when a prompt starts, so the first frame of an
  effect does not pay for it. :meth:`SceneView.repaint_due` caps scene repaints at about 60 Hz
  while the gaze loop keeps its own rate.
* **Idle life (N3).** Blinks and bob run on a clock the view advances from the canvas tick, so they
  stop with the test (a pause stops the ticks) and are frozen during an effect.
* **Placeholders.** A layer without a picture file is drawn by :mod:`.scene_placeholders`; one with
  a picture file in the scene folder is drawn from it.
"""

from __future__ import annotations

import random
import time
from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QPainter, QPixmap

from ..tasks.choice_idle import IdleLife
from ..tasks.choice_scene import (
    Layer,
    LayerState,
    ObjectSpec,
    SceneManifest,
    load_manifest,
    normalise_idle,
    object_layer_states,
    particles_at,
)
from .scene_buttons import ButtonLook, draw_button, pulse_phase, selected_strength
from .scene_placeholders import (
    draw_backdrop,
    draw_eyelids,
    draw_face,
    draw_label,
    draw_particle,
    draw_shape,
)

MIN_PAINT_S = 0.014  # scene repaints at most about every 14 ms (about 60 Hz, N5)
MAX_DT_S = 0.1  # a longer gap between ticks (a pause) does not jump the idle clock
CACHE_LIMIT = 4  # idle, bob, the effect in flight and the one before it

Segment = QPixmap | Layer


class SceneView:
    def __init__(
        self,
        theme: dict,
        clock: Callable[[], float] = time.perf_counter,
        rng: random.Random | None = None,
    ) -> None:
        self.theme = theme
        self._clock = clock
        self._rng = rng
        self.manifest: SceneManifest | None = None
        self.idle: IdleLife | None = None
        self.t = 0.0  # running seconds, for the visual-cue pulse
        self.cache_builds = 0  # how many scene pixmaps were rendered (tests, A9)
        self._name: str | None = None
        self._idle_mode: str | None = None
        self._last_tick: float | None = None
        self._last_request: float | None = None
        self._prompt: str | None = None
        self._cache: OrderedDict[tuple, list[Segment]] = OrderedDict()
        self._images: dict[tuple, QPixmap | None] = {}
        self._label_of: dict[str, str] = {}  # layer id -> the owner's label (placeholders)
        self._spots: dict[str, list] = {}  # layer id -> its characters' blink spots
        self._label_px = 16

    # -- per tick -------------------------------------------------------------------------------

    def sync(self, scene: dict, dpr: float = 1.0) -> None:
        """Take the frame's scene description: load the manifest on first sight, advance the idle
        clock (not during an effect) and warm the cache for the prompted object."""
        name = str(scene.get("theme") or "park")
        if name != self._name:
            self._load(name)
        mode = normalise_idle(scene.get("idle_animation"))
        if self.idle is None or mode != self._idle_mode:
            assert self.manifest is not None
            self.idle = IdleLife.for_manifest(self.manifest, mode, self._rng)
            self._idle_mode = mode
        now = self._clock()
        dt = 0.0 if self._last_tick is None else min(max(now - self._last_tick, 0.0), MAX_DT_S)
        self._last_tick = now
        self.t += dt
        if scene.get("effect") is None:
            self.idle.advance(dt)
        prompt = scene.get("prompt_object")
        if prompt and prompt != self._prompt:
            self._warm(prompt, scene, dpr)
        self._prompt = prompt

    def reset_clock(self) -> None:
        """Forget the last tick (the canvas was paused): the next one does not count the pause."""
        self._last_tick = None

    def repaint_due(self) -> bool:
        """Whether a repaint may be requested now: at most about every :data:`MIN_PAINT_S`."""
        now = self._clock()
        if self._last_request is not None and now - self._last_request < MIN_PAINT_S:
            return False
        self._last_request = now
        return True

    def _load(self, name: str) -> None:
        self.manifest = load_manifest(name)
        self._name = name
        self.idle = None
        self._cache.clear()
        self._images.clear()
        self._label_of = {layer.id: obj.label for obj in self.manifest.objects for layer in obj.layers}
        self._spots = {}
        for spot in self.manifest.characters():
            self._spots.setdefault(spot.layer, []).append(spot)

    # -- the cache of unmoving layers ---------------------------------------------------------------

    def _warm(self, object_id: str, scene: dict, dpr: float) -> None:
        assert self.manifest is not None
        try:
            obj = self.manifest.object(object_id)
        except KeyError:
            return
        rect = self._scene_rect(scene, dpr)
        if rect is not None:
            self._segments(frozenset(layer.id for layer in obj.layers), rect.size(), dpr)

    @staticmethod
    def _scene_rect(scene: dict, dpr: float) -> QRectF | None:
        """The scene's rectangle on whole device pixels (so the cached pixmaps land exactly where
        the layers drawn live do: with a fractional origin a moving layer's antialiased edges
        differ from the cached picture's), or ``None`` when there is no scene to draw."""
        x, y, w, h = scene.get("scene_rect", (0.0, 0.0, 0.0, 0.0))
        if not (w > 0 and h > 0 and dpr > 0):
            return None
        return QRectF(*(round(v * dpr) / dpr for v in (x, y, w, h)))

    def _segments(self, dynamic: frozenset[str], size: QSizeF, dpr: float) -> list[Segment]:
        """The scene as pixmaps of the layers that do not move, with each of ``dynamic`` (layer ids)
        between them in z order."""
        key = (dynamic, round(size.width()), round(size.height()), round(dpr * 100))
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        assert self.manifest is not None
        built: list[Segment] = []
        group: list[Layer] = []
        for layer in self.manifest.all_layers():
            if layer.id in dynamic:
                if not built or group:
                    built.append(self._render_group(group, not built, size, dpr))
                    group = []
                built.append(layer)
            elif layer.idle_alpha > 0:
                group.append(layer)
        if not built or group:
            built.append(self._render_group(group, not built, size, dpr))
        self.cache_builds += 1
        self._cache[key] = built
        while len(self._cache) > CACHE_LIMIT:
            self._cache.popitem(last=False)
        return built

    def _render_group(self, layers: list[Layer], first: bool, size: QSizeF, dpr: float) -> QPixmap:
        pixmap = QPixmap(max(1, round(size.width() * dpr)), max(1, round(size.height() * dpr)))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._label_px = max(11, int(size.height() * 0.018))
        if first:
            self._paint_background(painter, size, dpr)
        for layer in layers:
            self._draw_layer(painter, layer, LayerState(alpha=layer.idle_alpha), size, dpr)
        painter.end()
        return pixmap

    # -- pictures --------------------------------------------------------------------------------

    def _image(self, file: str | None, w: float, h: float, dpr: float, keep_aspect: bool = False) -> QPixmap | None:
        """The picture ``file`` of the scene folder scaled to ``w`` x ``h`` logical px, or ``None``
        when there is none (the built-in scene, a missing or unreadable file)."""
        if not file or self.manifest is None or self.manifest.folder is None:
            return None
        key = (file, round(w * dpr), round(h * dpr), keep_aspect)
        if key not in self._images:
            pixmap = QPixmap(str(self.manifest.folder / file))
            if pixmap.isNull():
                self._images[key] = None
            else:
                mode = Qt.AspectRatioMode.KeepAspectRatio if keep_aspect else Qt.AspectRatioMode.IgnoreAspectRatio
                scaled = pixmap.scaled(
                    max(1, round(w * dpr)), max(1, round(h * dpr)), mode, Qt.TransformationMode.SmoothTransformation
                )
                scaled.setDevicePixelRatio(dpr)
                self._images[key] = scaled
        return self._images[key]

    def _paint_background(self, painter: QPainter, size: QSizeF, dpr: float) -> None:
        assert self.manifest is not None
        picture = self._image(self.manifest.background, size.width(), size.height(), dpr)
        if picture is not None:
            painter.drawPixmap(QPointF(0, 0), picture)
        else:
            draw_backdrop(painter, QRectF(0, 0, size.width(), size.height()), self._label_px)

    def _draw_layer(self, painter: QPainter, layer: Layer, state: LayerState, size: QSizeF, dpr: float) -> None:
        """``layer`` under ``state``: the transform of the effect, then the picture or placeholder."""
        w, h = size.width(), size.height()
        if state.alpha <= 0.001:
            return
        rect = QRectF(layer.box[0] * w, layer.box[1] * h, (layer.box[2] - layer.box[0]) * w, (layer.box[3] - layer.box[1]) * h)
        painter.save()
        if state.moves:  # the same transform choice_scene.transform_box maps the AOI with
            px, py = layer.pivot_point[0] * w, layer.pivot_point[1] * h
            painter.translate(px + state.dx * w, py + state.dy * h)
            painter.rotate(state.rot)
            painter.scale(state.scale, state.scale)
            painter.translate(-px, -py)
        painter.setOpacity(state.alpha)
        file = (layer.states.get(state.state) if state.state else None) or layer.image
        picture = self._image(file, rect.width(), rect.height(), dpr)
        if picture is not None:
            painter.drawPixmap(rect.topLeft(), picture)
        else:
            draw_shape(painter, layer.shape, rect, layer.colour, state.state)
            for spot in self._spots.get(layer.id, ()):
                draw_face(painter, spot.x * w, spot.y * h, spot.r * w)
            if layer.label and layer.id in self._label_of:
                draw_label(painter, rect, self._label_of[layer.id], self._label_px)
        painter.restore()

    # -- painting ------------------------------------------------------------------------------

    def paint(self, painter: QPainter, canvas) -> None:
        """Draw the whole scene mode: the scene, then the buttons. ``canvas`` is the
        :class:`~src.ui.canvas.TaskCanvas` (its scene description and look flags)."""
        scene = canvas.scene
        dpr = canvas.devicePixelRatioF()
        if self.manifest is None or self.idle is None:
            self.sync(scene, dpr)
        assert self.manifest is not None and self.idle is not None
        effect = scene.get("effect")
        obj: ObjectSpec | None = None
        if effect:
            try:
                obj = self.manifest.object(effect["object"])
            except KeyError:
                obj = None
        rect = self._scene_rect(scene, dpr)
        if rect is not None:
            self._paint_scene(painter, rect, obj, float((effect or {}).get("elapsed_ms", 0.0)), dpr)
        self._paint_buttons(painter, canvas, scene, effect, dpr)

    def _paint_scene(self, painter: QPainter, rect: QRectF, obj: ObjectSpec | None, elapsed_ms: float, dpr: float) -> None:
        assert self.manifest is not None and self.idle is not None
        size = rect.size()
        w, h = size.width(), size.height()
        states: dict[str, LayerState] = {}
        if obj is not None:
            states = object_layer_states(obj, elapsed_ms)
        else:  # idle bob: the bobbing objects' layers move a little
            for bob in self.manifest.objects:
                if bob.id in self.idle.bobbing():
                    dy = self.idle.bob_offset(bob.id)
                    states.update({layer.id: LayerState(dy=dy, alpha=layer.idle_alpha) for layer in bob.layers})
        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.topLeft())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for segment in self._segments(frozenset(states), size, dpr):
            if isinstance(segment, Layer):
                self._draw_layer(painter, segment, states[segment.id], size, dpr)
            else:
                painter.drawPixmap(QPointF(0, 0), segment)
        if obj is not None:
            for p in particles_at(obj.effect, elapsed_ms):
                draw_particle(painter, p.style, p.x * w, p.y * h, p.size * h, p.alpha)
        else:
            for spot in self.manifest.characters():
                if not self.idle.is_blinking(spot.id):
                    continue
                b = spot.box
                target = QRectF(b[0] * w, b[1] * h, (b[2] - b[0]) * w, (b[3] - b[1]) * h) if b else None
                patch = self._image(spot.image, target.width(), target.height(), dpr) if target else None
                if patch is not None and target is not None:  # the eyes-closed picture (N6)
                    painter.drawPixmap(target.topLeft(), patch)
                else:  # eyelids drawn in code
                    draw_eyelids(painter, spot.x * w, spot.y * h, spot.r * w)
        painter.restore()

    def _paint_buttons(self, painter: QPainter, canvas, scene: dict, effect: dict | None, dpr: float) -> None:
        assert self.manifest is not None
        selected, strength = -1, 0.0
        if effect and not effect.get("modelled"):
            selected = next((b["slot"] for b in scene.get("buttons", ()) if b["object"] == effect["object"]), -1)
            strength = selected_strength(float(effect.get("elapsed_ms", 0.0)))
        look = ButtonLook(
            self.theme, int(scene.get("hover_slot", -1)), bool(canvas.selectable), bool(canvas.show_glow),
            bool(canvas.show_instant_feedback), bool(canvas.show_progress_ring), float(canvas.dwell_progress),
            int(scene.get("cue_slot", -1)), pulse_phase(self.t), selected, strength,
        )
        for button in scene.get("buttons", ()):
            rect = QRectF(*button["rect"])
            spec = self.manifest.object(button["object"])
            picture = self._image(spec.button_image, rect.width() * 0.7, rect.height() * 0.62, dpr, keep_aspect=True)
            draw_button(painter, button["slot"], rect, button["label"], spec.colour, picture, look)
