"""Reading ``scene.yaml`` (SPEC-scene-cause-effect-task.md 4.7), Qt-free.

The file lives at ``configs/assets/scenes/<scene>/scene.yaml``; picture files are named relative to
that folder. Everything is optional except what a layer needs to exist. An object the file does not
list keeps its built-in placeholder, and an object that leaves out a part (``effect``, ``blink``,
``bob``, ``duration_ms`` ...) keeps that part, so art can arrive object by object. An object that
replaces its ``layers`` must also give its ``effect`` and ``blink``: the built-in ones name the
built-in layers, and a step or blink spot naming a layer the object does not have is an error::

    scene: park
    aspect: 1.3333                      # scene width / height (default 4:3)
    background: background.png          # omit for the placeholder backdrop
    decor:                              # layers that belong to no object
      - {id: bush_front, box: [0.33, 0.58, 0.42, 0.68], z: 30, image: layers/bush_front.png}
    objects:
      bike:
        label: Bike                     # default: the built-in label
        prompt: "Make the bike ride away!"
        box: [0.36, 0.42, 0.47, 0.63]   # the look-back AOI source (scene fractions)
        follows: bike                   # the layer whose transform moves the box (N2); omit = static
        duration_ms: 4000               # default: the 4.4 duration
        button_image: buttons/bike.png
        layers:                         # id, box, z, image, pivot, idle_alpha, states, shape, colour
          - {id: bike, box: [0.36, 0.42, 0.47, 0.63], z: 7, image: objects/bike.png,
             states: {blowing: objects/bike_blowing.png}}
        blink:                          # eyes of the characters (N3); image = the eyes-closed patch
          - {id: bike_rider, layer: bike, x: 0.41, y: 0.50, r: 0.007,
             image: blink/bike_rider.png, box: [0.40, 0.49, 0.42, 0.51]}
        bob: {amp: 0.006, period_s: 3.2}   # idle bob (blinks_bob)
        effect:                         # steps on a 0..1 timeline, t: [start, end]
          - {kind: transform, layer: bike, t: [0, 0.5], ease: in,
             tracks: {dx: [[0, 0], [1, 0.66]]}}           # keys: [progress 0..1, value]
          - {kind: transform, layer: seesaw_plank, t: [0, 1], ease: linear,
             osc: {rot: [12, 3, 0]}}                       # [amplitude, cycles, damping]
          - {kind: swap, layer: bubbles_child, t: [0, 0.85], state: blowing}
          - {kind: particles, t: [0.08, 0.95], style: bubble, origin: [0.56, 0.78], count: 8,
             drift: [-0.16, -0.38], size: 0.03, life: 0.5}
          - {kind: sequence, layer: x, t: [0, 1], frames: [a.png, b.png], fps: 24}

A malformed file raises :class:`~.choice_scene.SceneManifestError`; :func:`~.choice_scene.load_manifest`
turns that into the built-in scene plus a warning.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .choice_layout import OBJECT_BY_ID
from .choice_scene import (
    SCENE_ASPECT,
    SOURCE_FILE,
    BlinkSpot,
    Box,
    Effect,
    Layer,
    ObjectSpec,
    Particles,
    Point,
    SceneManifest,
    SceneManifestError,
    Sequence,
    Step,
    Swap,
    Track,
    Transform,
)
from .choice_scene_defaults import default_manifest


def _fail(where: str, message: str) -> SceneManifestError:
    return SceneManifestError(f"{where}: {message}")


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail(where, "expected a mapping")
    return value


def _list(value: Any, where: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _fail(where, "expected a list")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(where, f"expected a number, got {value!r}")
    return float(value)


def _pair(value: Any, where: str) -> Point:
    seq = _list(value, where)
    if len(seq) != 2:
        raise _fail(where, "expected [x, y]")
    return _number(seq[0], where), _number(seq[1], where)


def _box(value: Any, where: str) -> Box:
    seq = _list(value, where)
    if len(seq) != 4:
        raise _fail(where, "expected [x0, y0, x1, y1]")
    x0, y0, x1, y1 = (_number(v, where) for v in seq)
    if not (x0 < x1 and y0 < y1):
        raise _fail(where, "a box needs x0 < x1 and y0 < y1")
    return x0, y0, x1, y1


def _text(data: Mapping[str, Any], key: str, where: str, default: str | None = None) -> str | None:
    value = data.get(key, default)
    if value is not None and not isinstance(value, str):
        raise _fail(f"{where}.{key}", "expected text")
    return value


def _layer(data: Any, where: str) -> Layer:
    d = _mapping(data, where)
    layer_id = _text(d, "id", where)
    if not layer_id:
        raise _fail(where, "a layer needs an id")
    pivot = d.get("pivot")
    states = _mapping(d.get("states") or {}, f"{where}.states")
    return Layer(
        layer_id,
        _box(d.get("box"), f"{where}.box"),
        int(_number(d.get("z", 0), f"{where}.z")),
        _text(d, "shape", where, "rect") or "rect",
        _text(d, "colour", where, "#9e9e9e") or "#9e9e9e",
        _text(d, "image", where),
        _pair(pivot, f"{where}.pivot") if pivot is not None else None,
        _number(d.get("idle_alpha", 1.0), f"{where}.idle_alpha"),
        {str(k): (None if v is None else str(v)) for k, v in states.items()},
        bool(d.get("label", False)),
    )


def _track(data: Any, where: str) -> Track:
    if isinstance(data, Mapping):  # {keys: [[p, v], ...], osc: [amp, cycles, damping]}
        keys = tuple(_pair(k, where) for k in _list(data.get("keys"), where))
        osc = data.get("osc")
        return Track(keys, _triple(osc, where) if osc is not None else None)
    return Track(tuple(_pair(k, where) for k in _list(data, where)))


def _triple(value: Any, where: str) -> tuple[float, float, float]:
    seq = _list(value, where)
    if len(seq) != 3:
        raise _fail(where, "expected [amplitude, cycles, damping]")
    return _number(seq[0], where), _number(seq[1], where), _number(seq[2], where)


def _step(data: Any, where: str) -> Step:
    d = _mapping(data, where)
    kind = d.get("kind")
    t0, t1 = _pair(d.get("t"), f"{where}.t")
    layer = _text(d, "layer", where)
    if kind == "transform":
        tracks = {str(p): _track(v, f"{where}.tracks.{p}") for p, v in _mapping(d.get("tracks") or {}, where).items()}
        for prop, spec in _mapping(d.get("osc") or {}, f"{where}.osc").items():
            base = tracks.get(str(prop), Track())
            tracks[str(prop)] = Track(base.keys, _triple(spec, f"{where}.osc.{prop}"))
        return Transform(layer or "", t0, t1, tracks, _text(d, "ease", where, "in_out") or "in_out")
    if kind == "swap":
        return Swap(layer or "", t0, t1, _text(d, "state", where) or "")
    if kind == "sequence":
        frames = tuple(str(f) for f in _list(d.get("frames"), f"{where}.frames"))
        return Sequence(layer or "", t0, t1, frames, _number(d.get("fps", 24.0), f"{where}.fps"))
    if kind == "particles":
        return Particles(
            t0, t1, _text(d, "style", where, "bubble") or "bubble", _pair(d.get("origin"), f"{where}.origin"),
            int(_number(d.get("count", 1), f"{where}.count")), _pair(d.get("drift", [0, 0]), f"{where}.drift"),
            _number(d.get("size", 0.03), f"{where}.size"), _number(d.get("life", 0.5), f"{where}.life"),
        )
    raise _fail(where, f"unknown step kind {kind!r}")


def _blink(data: Any, where: str) -> BlinkSpot:
    d = _mapping(data, where)
    box = d.get("box")
    return BlinkSpot(
        _text(d, "id", where) or "", _text(d, "layer", where) or "",
        _number(d.get("x"), f"{where}.x"), _number(d.get("y"), f"{where}.y"),
        _number(d.get("r", 0.01), f"{where}.r"), _text(d, "image", where),
        _box(box, f"{where}.box") if box is not None else None,
    )


def _object(object_id: str, data: Any, builtin: ObjectSpec) -> ObjectSpec:
    """An object of the file; what it leaves out (layers, effect, blink, bob ...) keeps its
    built-in value, so a file can override one thing at a time."""
    where = f"objects.{object_id}"
    d = _mapping(data, where)
    layers = builtin.layers
    if "layers" in d:
        layers = tuple(_layer(item, f"{where}.layers[{i}]") for i, item in enumerate(_list(d["layers"], where)))
    steps = builtin.effect.steps
    if "effect" in d:
        steps = tuple(_step(item, f"{where}.effect[{i}]") for i, item in enumerate(_list(d["effect"], where)))
    blink = builtin.blink
    if "blink" in d:
        blink = tuple(_blink(item, f"{where}.blink[{i}]") for i, item in enumerate(_list(d["blink"], where)))
    bob = builtin.bob
    if "bob" in d:
        raw = d["bob"]
        if isinstance(raw, Mapping):
            bob = (_number(raw.get("amp"), f"{where}.bob.amp"), _number(raw.get("period_s"), f"{where}.bob.period_s"))
        else:
            bob = _pair(raw, f"{where}.bob") if raw is not None else None
    duration = _number(d.get("duration_ms", builtin.effect.duration_ms), f"{where}.duration_ms")
    follows = _text(d, "follows", where, builtin.follows)
    layer_ids = {layer.id for layer in layers}
    if follows is not None and follows not in layer_ids:
        raise _fail(f"{where}.follows", f"{follows!r} is not one of the object's layers")
    for step in steps:
        target = getattr(step, "layer", None)
        if target is not None and target not in layer_ids:
            raise _fail(where, f"an effect step names an unknown layer {target!r}")
    for spot in blink:
        if spot.layer not in layer_ids:
            raise _fail(where, f"a blink spot names an unknown layer {spot.layer!r}")
    return ObjectSpec(
        object_id, _text(d, "label", where, builtin.label) or builtin.label, builtin.slot,
        _box(d["box"], f"{where}.box") if "box" in d else builtin.box, _text(d, "colour", where, builtin.colour) or builtin.colour,
        layers, Effect(duration, steps), follows, _text(d, "prompt", where, builtin.prompt) or "", blink, bob,
        _text(d, "button_image", where, builtin.button_image),
    )


def parse_manifest(data: Any, folder: Path, scene: str) -> SceneManifest:
    """The manifest in ``data`` (a loaded YAML mapping) whose pictures are in ``folder``."""
    d = _mapping(data, "scene.yaml")
    builtin = default_manifest(scene)
    listed = _mapping(d.get("objects") or {}, "objects")
    for object_id in listed:
        if object_id not in OBJECT_BY_ID:
            raise _fail("objects", f"unknown object {object_id!r}")
    objects = tuple(
        _object(obj.id, listed[obj.id], obj) if obj.id in listed else obj for obj in builtin.objects
    )
    decor = tuple(_layer(item, f"decor[{i}]") for i, item in enumerate(_list(d.get("decor"), "decor")))
    aspect = _number(d.get("aspect", SCENE_ASPECT), "aspect")
    if aspect <= 0:
        raise _fail("aspect", "must be positive")
    return SceneManifest(
        scene, objects, decor, _text(d, "background", "scene.yaml"), aspect, folder, SOURCE_FILE
    )


def read_manifest(path: Path, scene: str) -> SceneManifest:
    """Read and validate ``path`` (a ``scene.yaml``); raises :class:`SceneManifestError`/``OSError``."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise SceneManifestError(f"not valid YAML ({error})") from error
    return parse_manifest(data, path.parent, scene)
