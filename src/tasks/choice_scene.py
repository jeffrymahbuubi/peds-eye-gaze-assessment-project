"""The Choice-making scene: layers, effects and the AOI under an effect (Qt-free).

SPEC-scene-cause-effect-task.md 4.4 (effects), 4.5 (rendering), 4.7 (the scene manifest) and the
animation decisions N1-N4. This module is the single source of truth for what the canvas draws and
what the look-back AOI follows: both call the same functions, so the AOI of a moving object is exactly
the box the canvas drew (N2).

* **Scene fractions.** Every position here is a fraction of the scene rectangle (x of its width, y of
  its height; origin top-left), so the same numbers serve any canvas size. ``aspect`` (scene width /
  height, 4:3 by default) only matters for rotation, where the scene is not square.
* **Layers** (H14) are the art: a layer is a picture (a file, or a placeholder shape until the art
  exists) at a box, with a z order, a pivot and a rest alpha. Objects own layers; ``decor`` layers
  belong to no object (the bush the bike rides behind).
* **Effects** (N1) are lists of steps on a 0..1 timeline: ``transform`` (move / rotate about the pivot
  / scale / fade one layer), ``swap`` (show another state image), ``particles`` (bubbles, pop bursts)
  and ``sequence`` (a frame set, unused in v1). Of the transforms on one layer the latest to have
  started wins and holds its end value until a later one starts, so a layer can leave the scene and
  come back from the other side. A step sets only the properties it names; the rest are at rest.
  **Every effect ends on rest** (A5): at ``elapsed >= duration`` every layer is at rest and there
  are no particles, and the last step's end values are the rest values too (no jump).
* **The AOI under an effect.** :func:`object_box_at` is the object's look-back box in scene fractions
  at an elapsed time: the idle box, moved by the transform of the layer named in ``follows`` (Bike,
  Cloud; N2). It is pure and deterministic. The box is NOT clamped to the scene: while the object is
  off the picture it lies partly or wholly outside 0..1.
* **The manifest** is ``configs/assets/scenes/<scene>/scene.yaml`` (:func:`load_manifest`); when it
  is absent the built-in placeholder scene (``choice_scene_defaults``) is used, so everything works
  before any art exists. The file format is documented in :mod:`.choice_scene_io`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from .choice_layout import ASSETS_ROOT

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in scene fractions
Point = tuple[float, float]

SCENE_ASPECT = 4 / 3  # W1: the scene is about 4:3

IDLE_OFF, IDLE_BLINKS, IDLE_BLINKS_BOB = "off", "blinks", "blinks_bob"
IDLE_MODES = (IDLE_OFF, IDLE_BLINKS, IDLE_BLINKS_BOB)
DEFAULT_IDLE = IDLE_BLINKS  # N3

EASES = ("linear", "in", "out", "in_out")
PROPS = ("dx", "dy", "rot", "scale", "alpha")  # what a transform track can drive
PARTICLE_STYLES = ("bubble", "burst")

SOURCE_DEFAULT, SOURCE_FILE = "default", "file"


class SceneManifestError(ValueError):
    """A scene manifest (or a part of one) is not valid."""


def normalise_idle(value: object) -> str:
    """``value`` if it is one of :data:`IDLE_MODES`, else the default (``blinks``)."""
    return value if isinstance(value, str) and value in IDLE_MODES else DEFAULT_IDLE


# -- the model ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Layer:
    """One picture of the scene at rest. ``image`` is a file relative to the scene folder, or ``None``
    for a placeholder drawn in code (``shape`` and ``colour``). ``pivot`` (scene fractions) defaults to
    the centre of ``box``. ``idle_alpha`` 0 is a layer shown only by an effect (the rainbow's tinted
    copies, N4). ``states`` maps a state name (``blowing``) to its image file (``None`` = placeholder).
    ``label`` asks the placeholder to write the object's name on this layer."""

    id: str
    box: Box
    z: int = 0
    shape: str = "rect"
    colour: str = "#9e9e9e"
    image: str | None = None
    pivot: Point | None = None
    idle_alpha: float = 1.0
    states: Mapping[str, str | None] = field(default_factory=dict)
    label: bool = False

    @property
    def pivot_point(self) -> Point:
        if self.pivot is not None:
            return self.pivot
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2


@dataclass(frozen=True, slots=True)
class BlinkSpot:
    """The eyes of one character (N3): ``layer`` is the layer they belong to, ``(x, y)`` their centre
    and ``r`` half their width (x: fraction of the scene width). ``image`` is the eyes-closed patch
    file placed at ``box`` (N6), or ``None`` to draw the eyelids in code."""

    id: str
    layer: str
    x: float
    y: float
    r: float
    image: str | None = None
    box: Box | None = None


@dataclass(frozen=True, slots=True)
class Track:
    """One property over a step: ``keys`` are ``(p, value)`` pairs with ``p`` the step's eased
    progress 0..1 (linear between keys; none = the rest value), plus an optional damped oscillation
    ``(amplitude, cycles, damping)`` of the step's linear progress added on top. A whole number of
    cycles returns to 0, so a swing or a seesaw ends at rest."""

    keys: tuple[Point, ...] = ()
    osc: tuple[float, float, float] | None = None


def _check_window(t0: float, t1: float, what: str) -> None:
    if not (0.0 <= t0 <= t1 <= 1.0):
        raise SceneManifestError(f"{what}: need 0 <= t0 <= t1 <= 1, got {t0}, {t1}")


@dataclass(frozen=True, slots=True)
class Transform:
    kind: ClassVar[str] = "transform"
    layer: str
    t0: float
    t1: float
    tracks: Mapping[str, Track]
    ease: str = "in_out"

    def __post_init__(self) -> None:
        _check_window(self.t0, self.t1, f"transform of {self.layer}")
        if self.ease not in EASES:
            raise SceneManifestError(f"unknown ease {self.ease!r}")
        for prop in self.tracks:
            if prop not in PROPS:
                raise SceneManifestError(f"unknown transform property {prop!r}")


@dataclass(frozen=True, slots=True)
class Swap:
    kind: ClassVar[str] = "swap"
    layer: str
    t0: float
    t1: float
    state: str

    def __post_init__(self) -> None:
        _check_window(self.t0, self.t1, f"swap of {self.layer}")


@dataclass(frozen=True, slots=True)
class Sequence:
    """A short frame set played on the effect clock (N1: unused in v1)."""

    kind: ClassVar[str] = "sequence"
    layer: str
    t0: float
    t1: float
    frames: tuple[str, ...]
    fps: float = 24.0

    def __post_init__(self) -> None:
        _check_window(self.t0, self.t1, f"sequence of {self.layer}")
        if not self.frames or self.fps <= 0:
            raise SceneManifestError(f"sequence of {self.layer} needs frames and a positive fps")


@dataclass(frozen=True, slots=True)
class Particles:
    """``count`` particles of one ``style`` between ``t0`` and ``t1`` (every one is gone by ``t1``).
    ``bubble``: spawned evenly through the window at ``origin``, rising by ``drift`` over a life of
    ``life`` x the window, fading. ``burst``: all at once from ``origin``, flying out radially to
    ``drift[0]`` (scene height) while fading. ``size`` is a diameter in scene height."""

    kind: ClassVar[str] = "particles"
    t0: float
    t1: float
    style: str
    origin: Point
    count: int
    drift: Point
    size: float
    life: float = 0.5

    def __post_init__(self) -> None:
        _check_window(self.t0, self.t1, "particles")
        if self.style not in PARTICLE_STYLES:
            raise SceneManifestError(f"unknown particle style {self.style!r}")
        if self.count < 1 or not (0.0 < self.life <= 1.0) or self.size <= 0:
            raise SceneManifestError("particles need count >= 1, 0 < life <= 1 and size > 0")


Step = Transform | Swap | Sequence | Particles


@dataclass(frozen=True, slots=True)
class Effect:
    duration_ms: float
    steps: tuple[Step, ...] = ()

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise SceneManifestError("an effect needs a positive duration")


@dataclass(frozen=True, slots=True)
class ObjectSpec:
    """One of the eight objects: its look-back box (the AOI source, scene fractions), its layers, its
    effect and, for idle life, its blinking characters and its bob ``(amplitude, period_s)``.
    ``follows`` names the layer whose transform moves the box (N2); ``None`` = the box stays put."""

    id: str
    label: str
    slot: int
    box: Box
    colour: str
    layers: tuple[Layer, ...]
    effect: Effect
    follows: str | None = None
    prompt: str = ""
    blink: tuple[BlinkSpot, ...] = ()
    bob: tuple[float, float] | None = None
    button_image: str | None = None


@dataclass(frozen=True, slots=True)
class SceneManifest:
    scene: str
    objects: tuple[ObjectSpec, ...]
    decor: tuple[Layer, ...] = ()
    background: str | None = None  # image file, or None for the placeholder backdrop
    aspect: float = SCENE_ASPECT
    folder: Path | None = None  # where the image files live; None for the built-in scene
    source: str = SOURCE_DEFAULT
    warning: str | None = None  # why the built-in scene was used although a file exists

    def object(self, object_id: str) -> ObjectSpec:
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        raise KeyError(object_id)

    def all_layers(self) -> list[Layer]:
        """Every layer, lowest z first (ties keep their order)."""
        layers = list(self.decor) + [layer for obj in self.objects for layer in obj.layers]
        return sorted(layers, key=lambda layer: layer.z)

    def characters(self) -> list[BlinkSpot]:
        return [spot for obj in self.objects for spot in obj.blink]


@dataclass(frozen=True, slots=True)
class LayerState:
    """A layer's transform at one moment: ``dx`` / ``dy`` in scene fractions, ``rot`` in degrees
    clockwise about the pivot, ``scale`` about the pivot, ``alpha``; ``state`` the swapped-in state
    name (``None`` = the resting picture), ``frame`` the sequence frame."""

    dx: float = 0.0
    dy: float = 0.0
    rot: float = 0.0
    scale: float = 1.0
    alpha: float = 1.0
    state: str | None = None
    frame: int | None = None

    @property
    def moves(self) -> bool:
        """Whether the geometry differs from rest (alpha and state do not count)."""
        return bool(self.dx or self.dy or self.rot or self.scale != 1.0)


@dataclass(frozen=True, slots=True)
class ParticleState:
    """One particle to draw: ``(x, y)`` its centre in scene fractions, ``size`` its diameter in scene
    height, ``alpha`` 0..1."""

    style: str
    x: float
    y: float
    size: float
    alpha: float


# -- evaluation (pure, deterministic) ----------------------------------------------------------------


def ease(name: str, p: float) -> float:
    """``p`` (0..1) through the easing ``name``: ``in`` accelerates (gravity), ``out`` decelerates,
    ``in_out`` is a cosine ease."""
    p = min(max(p, 0.0), 1.0)
    if name == "in":
        return p * p
    if name == "out":
        return 1.0 - (1.0 - p) * (1.0 - p)
    if name == "in_out":
        return 0.5 - 0.5 * math.cos(math.pi * p)
    return p


def _interp(keys: tuple[Point, ...], p: float) -> float:
    """Piecewise-linear value of ``keys`` at ``p``, held at the first and last key outside them."""
    if p <= keys[0][0]:
        return keys[0][1]
    for (p0, v0), (p1, v1) in zip(keys, keys[1:], strict=False):
        if p <= p1:
            return v1 if p1 <= p0 else v0 + (v1 - v0) * (p - p0) / (p1 - p0)
    return keys[-1][1]


def effect_progress(effect: Effect, elapsed_ms: float) -> float | None:
    """How far into ``effect`` it is, 0..1 (exclusive of 1), or ``None`` outside it: before the start,
    at or after the end, or not a number. Outside the effect everything is at rest."""
    if not elapsed_ms >= 0.0 or elapsed_ms >= effect.duration_ms:  # also false for NaN
        return None
    return elapsed_ms / effect.duration_ms


def _latest(steps: tuple[Step, ...], kind: type, layer_id: str, u: float) -> Step | None:
    """The step of ``kind`` on ``layer_id`` that started last at or before ``u``."""
    best: Step | None = None
    for step in steps:
        if isinstance(step, kind) and step.layer == layer_id and step.t0 <= u:
            if best is None or step.t0 >= best.t0:
                best = step
    return best


def layer_state(effect: Effect, layer: Layer, elapsed_ms: float) -> LayerState:
    """The state of ``layer`` ``elapsed_ms`` into ``effect`` (rest outside it)."""
    rest = LayerState(alpha=layer.idle_alpha)
    u = effect_progress(effect, elapsed_ms)
    if u is None:
        return rest
    values = {"dx": 0.0, "dy": 0.0, "rot": 0.0, "scale": 1.0, "alpha": layer.idle_alpha}
    step = _latest(effect.steps, Transform, layer.id, u)
    if step is not None:
        linear = 1.0 if step.t1 <= step.t0 else min(max((u - step.t0) / (step.t1 - step.t0), 0.0), 1.0)
        eased = ease(step.ease, linear)
        for prop, track in step.tracks.items():
            value = _interp(track.keys, eased) if track.keys else values[prop]
            if track.osc is not None:
                amplitude, cycles, damping = track.osc
                value += amplitude * math.sin(math.tau * cycles * linear) * math.exp(-damping * linear)
            values[prop] = value
    state = None
    swap = _latest(effect.steps, Swap, layer.id, u)
    if swap is not None and u < swap.t1:
        state = swap.state
    frame = None
    seq = _latest(effect.steps, Sequence, layer.id, u)
    if seq is not None and u <= seq.t1:
        n_frames = len(seq.frames)
        frame = min(n_frames - 1, int((u - seq.t0) * effect.duration_ms / 1000.0 * seq.fps))
    return LayerState(**values, state=state, frame=frame)


def object_layer_states(obj: ObjectSpec, elapsed_ms: float) -> dict[str, LayerState]:
    """The state of each of ``obj``'s layers (by id) ``elapsed_ms`` into its effect."""
    return {layer.id: layer_state(obj.effect, layer, elapsed_ms) for layer in obj.layers}


def _hash01(index: int, salt: float) -> float:
    """A deterministic pseudo-random number in 0..1 from an index (no RNG state)."""
    x = math.sin(index * 12.9898 + salt * 78.233) * 43758.5453
    return x - math.floor(x)


def particles_at(effect: Effect, elapsed_ms: float) -> list[ParticleState]:
    """Every particle alive ``elapsed_ms`` into ``effect``. Deterministic; empty outside the effect."""
    u = effect_progress(effect, elapsed_ms)
    if u is None:
        return []
    out: list[ParticleState] = []
    for step_no, step in enumerate(effect.steps):
        if not isinstance(step, Particles) or not step.t0 <= u <= step.t1:
            continue
        span = step.t1 - step.t0
        life = max(step.life * span, 1e-9)
        for i in range(step.count):
            spawn = step.t0
            if step.style == "bubble" and step.count > 1:
                spawn += (span - life) * i / (step.count - 1)
            age = (u - spawn) / life
            if not 0.0 <= age <= 1.0:
                continue
            jitter = _hash01(i, step_no)
            if step.style == "bubble":
                wobble = 0.012 * math.sin(math.tau * (age * 1.5 + jitter))
                x = step.origin[0] + (jitter - 0.5) * 0.03 + step.drift[0] * age + wobble
                y = step.origin[1] + step.drift[1] * age
                size = step.size * (0.6 + 0.8 * _hash01(i, step_no + 0.5)) * (1.0 + 0.3 * age)
                alpha = 0.9 * (1.0 - age) ** 0.7
            else:  # burst
                angle = math.tau * (i + 0.3 * jitter) / step.count
                x = step.origin[0] + math.cos(angle) * step.drift[0] * age * 0.75
                y = step.origin[1] + math.sin(angle) * step.drift[0] * age
                size = step.size * (1.0 - 0.6 * age)
                alpha = 1.0 - age
            out.append(ParticleState(step.style, x, y, size, alpha))
    return out


def transform_box(box: Box, state: LayerState, pivot: Point, aspect: float = SCENE_ASPECT) -> Box:
    """``box`` (scene fractions) under ``state``: scaled and rotated about ``pivot`` (rotation is done
    in a square space, x scaled by ``aspect``), then shifted by ``dx`` / ``dy``; the bounding box."""
    x0, y0, x1, y1 = box
    px, py = pivot
    angle = math.radians(state.rot)
    cos, sin = math.cos(angle), math.sin(angle)
    xs: list[float] = []
    ys: list[float] = []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        sx = (x - px) * aspect * state.scale
        sy = (y - py) * state.scale
        xs.append(px + (sx * cos - sy * sin) / aspect + state.dx)
        ys.append(py + (sx * sin + sy * cos) + state.dy)
    return min(xs), min(ys), max(xs), max(ys)


def object_box_at(
    manifest: SceneManifest, object_id: str, elapsed_ms: float, *, aspect: float | None = None
) -> Box:
    """The look-back box ``(x0, y0, x1, y1)`` of ``object_id`` in scene fractions ``elapsed_ms`` after
    its effect started (N2, 4.6): the idle box under the transform of the layer the object ``follows``
    (Bike, Cloud), and exactly the idle box outside the effect or for an object whose box stays put.
    Pure and deterministic. Not clamped to the scene. ``aspect`` (scene width / height) defaults to
    the manifest's; pass the recorded scene rectangle's for exact rotation maths."""
    obj = manifest.object(object_id)
    if obj.follows is None:
        return obj.box
    layer = next((layer for layer in obj.layers if layer.id == obj.follows), None)
    if layer is None:
        return obj.box
    state = layer_state(obj.effect, layer, elapsed_ms)
    if not state.moves:
        return obj.box
    return transform_box(obj.box, state, layer.pivot_point, aspect or manifest.aspect)


# -- loading -----------------------------------------------------------------------------------------


def scene_folder(scene: str, root: Path | None = None) -> Path:
    """``<assets>/scenes/<scene>``: the folder of a scene's manifest, pictures and audio."""
    return (root if root is not None else ASSETS_ROOT) / "scenes" / scene


def load_manifest(scene: str = "park", root: Path | None = None) -> SceneManifest:
    """The manifest of ``scene``: ``scene.yaml`` in its folder when that file exists, else the built-in
    placeholder scene (so the test runs before any art exists). A file that cannot be read or is not
    valid also gives the built-in scene, with ``warning`` saying why; nothing is raised, because a
    broken file must not stop a run. Read only."""
    from .choice_scene_defaults import default_manifest
    from .choice_scene_io import read_manifest

    if not scene or Path(scene).name != scene:  # a name, never a path
        return default_manifest(scene or "park")
    path = scene_folder(scene, root) / "scene.yaml"
    if not path.is_file():
        return default_manifest(scene)
    try:
        return read_manifest(path, scene)
    except (OSError, ValueError) as error:  # read_manifest turns YAML errors into SceneManifestError
        fallback = default_manifest(scene)
        return SceneManifest(
            fallback.scene, fallback.objects, fallback.decor, fallback.background, fallback.aspect,
            warning=f"{path.name} not used ({error}); the built-in placeholder scene is shown",
        )
