"""The built-in placeholder scene of Choice-making (SPEC-scene-cause-effect-task.md 4.2, 4.4, 4.5).

Used whenever ``configs/assets/scenes/<scene>/scene.yaml`` is absent, so the canvas, the effects, the
idle life and the look-back AOI can be built and tested before any art exists. Every object is a few
labelled, coloured placeholder shapes (the renderer draws them in code); the boxes are the object
regions of the 4.2 table, the durations those of 4.4 (``choice_layout.OBJECTS``), the pivots are
guesses. When the art arrives its ``scene.yaml`` replaces the numbers here object by object.
"""

from __future__ import annotations

from collections.abc import Iterable

from .choice_layout import OBJECTS
from .choice_scene import (
    BlinkSpot,
    Box,
    Effect,
    Layer,
    ObjectSpec,
    Particles,
    Point,
    SceneManifest,
    Step,
    Swap,
    Track,
    Transform,
)

# Object region of the 4.2 table (x0, y0, x1, y1 in scene fractions): the look-back AOI source.
BOXES: dict[str, Box] = {
    "balloons": (0.79, 0.03, 0.99, 0.28),
    "rainbow": (0.45, 0.12, 0.77, 0.36),
    "seesaw": (0.51, 0.33, 0.74, 0.52),
    "apples": (0.05, 0.08, 0.45, 0.72),
    "cloud": (0.43, 0.00, 0.83, 0.14),
    "bubbles": (0.47, 0.65, 0.59, 0.95),
    "bike": (0.36, 0.42, 0.47, 0.63),
    "swing": (0.00, 0.51, 0.29, 0.97),
}
COLOURS = {  # the placeholder (and button swatch) colour of each object
    "balloons": "#e53935", "rainbow": "#8e24aa", "seesaw": "#fb8c00", "apples": "#43a047",
    "cloud": "#78909c", "bubbles": "#29b6f6", "bike": "#3949ab", "swing": "#f9a825",
}
PROMPTS = {
    "balloons": "Make the balloons pop!", "rainbow": "Make the rainbow sparkle!",
    "seesaw": "Make the seesaw go up and down!", "apples": "Make the apples fall!",
    "cloud": "Make the cloud float away!", "bubbles": "Make the bubbles fly!",
    "bike": "Make the bike ride away!", "swing": "Make the swing go!",
}
# Idle bob (blinks_bob, N3): amplitude as a fraction of the scene height, period in seconds.
BOBS = {"balloons": (0.006, 3.2), "cloud": (0.004, 5.0)}


def _sub(box: Box, fx0: float, fy0: float, fx1: float, fy1: float) -> Box:
    """The part of ``box`` between the given fractions of its own width / height."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    return x0 + fx0 * w, y0 + fy0 * h, x0 + fx1 * w, y0 + fy1 * h


def _at(box: Box, fx: float, fy: float) -> Point:
    x0, y0, x1, y1 = box
    return x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)


def _move(
    layer: str, t0: float, t1: float, ease: str = "in_out", **tracks: Iterable[Point] | Track
) -> Transform:
    """A transform step; each track is a list of ``(p, value)`` keys or a ready :class:`Track`."""
    built = {
        prop: spec if isinstance(spec, Track) else Track(tuple(spec)) for prop, spec in tracks.items()
    }
    return Transform(layer, t0, t1, built, ease)


def _ramp(a: float, b: float) -> list[Point]:
    return [(0.0, a), (1.0, b)]


def _balloons(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    layers = [Layer("balloons_strings", _sub(box, 0.08, 0.45, 0.92, 1.0), 10, "strings", "#616161", label=True)]
    steps: list[Step] = []
    spans = ((0.0, 0.0, 0.36, 0.55), (0.32, 0.0, 0.68, 0.5), (0.64, 0.0, 1.0, 0.55))
    for i, span in enumerate(spans, start=1):
        layer = Layer(f"balloon_{i}", _sub(box, *span), 10 + i, "ellipse", ("#e53935", "#fdd835", "#1e88e5")[i - 1])
        layers.append(layer)
        t0 = 0.10 + 0.18 * (i - 1)  # popped one after another, bare strings remain, then back
        cx, cy = _at(layer.box, 0.5, 0.5)
        steps += [
            _move(layer.id, t0, t0 + 0.02, "linear", alpha=_ramp(1.0, 0.0)),
            Particles(t0, t0 + 0.18, "burst", (cx, cy), 8, (0.06, 0.0), 0.02, 1.0),
            _move(layer.id, 0.78, 1.0, "in_out", alpha=_ramp(0.0, 1.0)),
        ]
    return layers, steps, []


def _rainbow(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    layers = [
        Layer("rainbow", box, 3, "rainbow", "#8e24aa", label=True),
        Layer("rainbow_tint_1", box, 4, "rainbow", "#26c6da", idle_alpha=0.0),  # N4: tinted copies
        Layer("rainbow_tint_2", box, 5, "rainbow", "#ffca28", idle_alpha=0.0),
    ]
    steps: list[Step] = [
        _move("rainbow_tint_1", 0.0, 0.7, "linear", alpha=[(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]),
        _move("rainbow_tint_2", 0.3, 1.0, "linear", alpha=[(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]),
    ]
    return layers, steps, []


def _seesaw(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    plank = Layer("seesaw_plank", _sub(box, 0.0, 0.25, 1.0, 0.5), 6, "plank", "#fb8c00", pivot=_at(box, 0.5, 0.55))
    layers = [Layer("seesaw_base", _sub(box, 0.38, 0.5, 0.62, 1.0), 5, "triangle", "#8d6e63", label=True), plank]
    steps: list[Step] = [  # about plus/minus 12 deg, 3 cycles
        _move("seesaw_plank", 0.0, 1.0, "linear", rot=Track(osc=(12.0, 3.0, 0.0))),
    ]
    spots = [
        BlinkSpot("seesaw_a", "seesaw_plank", *_at(plank.box, 0.12, 0.0), 0.012),
        BlinkSpot("seesaw_b", "seesaw_plank", *_at(plank.box, 0.88, 0.0), 0.012),
    ]
    return layers, steps, spots


def _apples(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    layers = [Layer("apples_tree", box, 1, "tree", "#43a047", label=True)]
    steps: list[Step] = []
    spans = ((0.15, 0.20, 0.27, 0.32), (0.45, 0.12, 0.57, 0.24), (0.70, 0.25, 0.82, 0.37))
    for i, span in enumerate(spans, start=1):
        layer = Layer(f"apple_{i}", _sub(box, *span), 2, "ellipse", "#d32f2f")
        layers.append(layer)
        t0 = 0.08 + 0.1 * (i - 1)
        fall = box[3] - layer.box[3] - 0.01  # to the ground
        steps += [
            _move(layer.id, t0, t0 + 0.4, "in", dy=_ramp(0.0, fall), alpha=[(0.0, 1.0), (0.8, 1.0), (1.0, 0.0)]),
            _move(layer.id, 0.78, 1.0, "in_out", dy=_ramp(0.0, 0.0), alpha=_ramp(0.0, 1.0)),  # new apples
        ]
    return layers, steps, []


def _cloud(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    layers = [Layer("cloud", box, 20, "cloud", "#78909c", label=True)]
    steps: list[Step] = [  # out to the left, back in from the right, to rest
        _move("cloud", 0.0, 0.5, "in_out", dx=_ramp(0.0, -(box[2] + 0.02))),
        _move("cloud", 0.5, 1.0, "in_out", dx=_ramp(1.0 - box[0] + 0.02, 0.0)),
    ]
    return layers, steps, []


def _bubbles(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    child = Layer(
        "bubbles_child", _sub(box, 0.0, 0.25, 1.0, 1.0), 8, "child", "#29b6f6", states={"blowing": None}, label=True
    )
    steps: list[Step] = [
        Swap("bubbles_child", 0.0, 0.85, "blowing"),
        Particles(0.08, 0.95, "bubble", _at(box, 0.8, 0.45), 8, (-0.16, -0.38), 0.03, 0.5),
    ]
    return [child], steps, [BlinkSpot("bubbles_girl", "bubbles_child", *_at(child.box, 0.5, 0.2), 0.008)]


def _bike(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    layer = Layer("bike", box, 7, "bike", "#3949ab", label=True)
    steps: list[Step] = [  # rides right out of the scene, comes back in from the left, stops at its start
        _move("bike", 0.0, 0.5, "in", dx=_ramp(0.0, 1.0 - box[0] + 0.02)),
        _move("bike", 0.5, 1.0, "out", dx=_ramp(-(box[2] + 0.02), 0.0)),
    ]
    return [layer], steps, [BlinkSpot("bike_rider", "bike", *_at(box, 0.5, 0.18), 0.007)]


def _swing(box: Box) -> tuple[list[Layer], list[Step], list[BlinkSpot]]:
    seat = Layer("swing_seat", _sub(box, 0.25, 0.12, 0.75, 1.0), 6, "swing", "#f9a825", pivot=_at(box, 0.5, 0.04))
    layers = [Layer("swing_frame", box, 5, "frame", "#8d6e63", label=True), seat]
    steps: list[Step] = [  # damped, 2 cycles
        _move("swing_seat", 0.0, 1.0, "linear", rot=Track(osc=(16.0, 2.0, 1.5))),
    ]
    return layers, steps, [BlinkSpot("swing_child", "swing_seat", *_at(seat.box, 0.5, 0.22), 0.008)]


_BUILDERS = {
    "balloons": _balloons, "rainbow": _rainbow, "seesaw": _seesaw, "apples": _apples,
    "cloud": _cloud, "bubbles": _bubbles, "bike": _bike, "swing": _swing,
}
# Objects whose look-back box moves with a layer (N2): they leave their idle box.
_FOLLOWS = {"bike": "bike", "cloud": "cloud"}


def default_manifest(scene: str = "park") -> SceneManifest:
    """The built-in placeholder scene: the eight objects of ``choice_layout.OBJECTS``."""
    objects = []
    for spec in OBJECTS:
        box = BOXES[spec.id]
        layers, steps, spots = _BUILDERS[spec.id](box)
        objects.append(
            ObjectSpec(
                spec.id, spec.label, spec.slot, box, COLOURS[spec.id], tuple(layers),
                Effect(float(spec.effect_ms), tuple(steps)), _FOLLOWS.get(spec.id), PROMPTS[spec.id],
                tuple(spots), BOBS.get(spec.id),
            )
        )
    bush = Layer("bush_front", (0.33, 0.58, 0.42, 0.68), 30, "bush", "#2e7d32")  # the bike rides behind it
    return SceneManifest(scene, tuple(objects), (bush,))
