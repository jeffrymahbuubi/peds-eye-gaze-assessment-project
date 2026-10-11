"""SPEC-scene-cause-effect-task.md step 4, Qt-free side: the scene manifest, the effect steps and the
moving AOI (4.4, 4.7, N1, N2), acceptance A5 (every effect ends on the idle picture).

``object_box_at`` is the function the look-back module (step 5) will call for the moving AOI of the
Bike and the Cloud, so its contract is pinned here: pure, deterministic, the idle box outside the
effect, the transformed box inside it."""

from __future__ import annotations

import math

import pytest

from src.tasks.choice_layout import OBJECTS
from src.tasks.choice_scene import (
    Effect,
    Layer,
    LayerState,
    Particles,
    SceneManifestError,
    Sequence,
    Swap,
    Track,
    Transform,
    ease,
    effect_progress,
    layer_state,
    load_manifest,
    normalise_idle,
    object_box_at,
    object_layer_states,
    particles_at,
    transform_box,
)
from src.tasks.choice_scene_defaults import BOXES, default_manifest

MANIFEST = default_manifest()
IDS = [o.id for o in OBJECTS]
EPS = 1e-6


def rest_of(layer: Layer) -> LayerState:
    return LayerState(alpha=layer.idle_alpha)


def close(a: LayerState, b: LayerState, tol: float = 1e-6) -> bool:
    return (
        abs(a.dx - b.dx) < tol and abs(a.dy - b.dy) < tol and abs(a.rot - b.rot) < tol
        and abs(a.scale - b.scale) < tol and abs(a.alpha - b.alpha) < tol
        and a.state == b.state and a.frame == b.frame
    )


# -- the built-in placeholder scene ----------------------------------------------------------------------------


def test_the_default_scene_has_the_eight_objects_with_the_4_2_boxes_and_4_4_durations():
    assert [o.id for o in MANIFEST.objects] == IDS and MANIFEST.source == "default"
    assert MANIFEST.folder is None and MANIFEST.warning is None
    for obj, spec in zip(MANIFEST.objects, OBJECTS, strict=True):
        assert (obj.slot, obj.label) == (spec.slot, spec.label)
        assert obj.box == BOXES[obj.id] and obj.effect.duration_ms == spec.effect_ms
        x0, y0, x1, y1 = obj.box
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    # The 4.2 table, spot checks.
    assert MANIFEST.object("bike").box == (0.36, 0.42, 0.47, 0.63)
    assert MANIFEST.object("balloons").box == (0.79, 0.03, 0.99, 0.28)


def test_layer_ids_are_unique_and_every_step_and_character_names_a_layer_of_its_object():
    all_ids = [layer.id for layer in MANIFEST.all_layers()]
    assert len(all_ids) == len(set(all_ids))
    for obj in MANIFEST.objects:
        ids = {layer.id for layer in obj.layers}
        assert ids and obj.prompt
        for step in obj.effect.steps:
            if hasattr(step, "layer"):
                assert step.layer in ids, (obj.id, step)
        assert all(spot.layer in ids for spot in obj.blink)
        if obj.follows:
            assert obj.follows in ids


def test_all_layers_are_sorted_by_z_and_the_bush_is_in_front_of_the_bike():
    layers = MANIFEST.all_layers()
    assert [layer.z for layer in layers] == sorted(layer.z for layer in layers)
    z = {layer.id: layer.z for layer in layers}
    assert z["bush_front"] > z["bike"] and z["rainbow_tint_1"] > z["rainbow"]
    assert next(layer for layer in layers if layer.id == "rainbow_tint_1").idle_alpha == 0.0


def test_only_the_bike_and_the_cloud_have_a_box_that_follows_a_layer_n2():
    assert {o.id: o.follows for o in MANIFEST.objects if o.follows} == {"bike": "bike", "cloud": "cloud"}


def test_four_characters_with_five_blink_spots_and_two_bobbing_objects():
    spots = MANIFEST.characters()
    assert len({s.id for s in spots}) == len(spots) == 5
    assert {o.id for o in MANIFEST.objects if o.bob} == {"balloons", "cloud"}


# -- A5: every effect ends on the idle picture -------------------------------------------------------------------


@pytest.mark.parametrize("object_id", IDS)
def test_every_layer_is_at_rest_before_the_effect_at_and_after_its_end_and_without_a_jump(object_id):
    obj = MANIFEST.object(object_id)
    end = obj.effect.duration_ms
    for layer in obj.layers:
        for elapsed in (-1.0, end, end + 500.0, float("nan")):
            assert close(layer_state(obj.effect, layer, elapsed), rest_of(layer)), (layer.id, elapsed)
        # ... and the last moment inside the effect already is the rest state: no jump at the end.
        assert close(layer_state(obj.effect, layer, end - 1e-6), rest_of(layer), 1e-5), layer.id
    assert particles_at(obj.effect, end) == [] and particles_at(obj.effect, end - 1e-6) == []
    assert particles_at(obj.effect, -5.0) == []


@pytest.mark.parametrize("object_id", IDS)
def test_every_effect_moves_something_between_its_start_and_its_end(object_id):
    obj = MANIFEST.object(object_id)
    moved = False
    for k in range(1, 40):
        elapsed = obj.effect.duration_ms * k / 40
        states = object_layer_states(obj, elapsed)
        moved |= any(not close(state, rest_of(layer)) for layer, state in zip(obj.layers, states.values(), strict=True))
        moved |= bool(particles_at(obj.effect, elapsed))
    assert moved, f"{object_id}: the effect never changes the picture"


def test_the_seesaw_and_the_swing_turn_about_their_pivots_and_return():
    seesaw = MANIFEST.object("seesaw")
    plank = next(layer for layer in seesaw.layers if layer.id == "seesaw_plank")
    peak = max(abs(layer_state(seesaw.effect, plank, seesaw.effect.duration_ms * k / 600).rot) for k in range(600))
    assert peak == pytest.approx(12.0, abs=0.2)  # about plus/minus 12 deg
    swing = MANIFEST.object("swing")
    seat = next(layer for layer in swing.layers if layer.id == "swing_seat")
    angles = [layer_state(swing.effect, seat, swing.effect.duration_ms * k / 600).rot for k in range(600)]
    assert max(abs(a) for a in angles[:100]) > max(abs(a) for a in angles[400:])  # damped
    assert seat.pivot is not None and seat.pivot[1] < seat.box[1]  # the pivot is the bar above the seat


def test_the_bike_and_the_cloud_leave_the_scene_and_come_back_from_the_other_side():
    for object_id, direction in (("bike", +1), ("cloud", -1)):
        obj = MANIFEST.object(object_id)
        x0, _y0, x1, _y1 = obj.box
        boxes = [object_box_at(MANIFEST, object_id, obj.effect.duration_ms * k / 200) for k in range(200)]
        assert any(b[0] >= 1.0 for b in boxes) if direction > 0 else any(b[2] <= 0.0 for b in boxes)
        # Then it re-enters from the opposite edge and ends on its idle box.
        assert boxes[-1][0] == pytest.approx(x0, abs=0.01) and boxes[-1][2] == pytest.approx(x1, abs=0.01)


def test_balloons_pop_one_after_another_leave_bare_strings_and_fade_back():
    obj = MANIFEST.object("balloons")
    duration = obj.effect.duration_ms
    alpha = {layer.id: layer for layer in obj.layers}

    def a(layer_id, u):
        return layer_state(obj.effect, alpha[layer_id], duration * u).alpha

    assert a("balloon_1", 0.05) == 1.0 and a("balloon_1", 0.2) == 0.0  # popped
    assert a("balloon_2", 0.2) == 1.0 and a("balloon_2", 0.4) == 0.0  # the next one, later
    assert a("balloon_3", 0.5) == 0.0
    assert all(a(f"balloon_{i}", 0.7) == 0.0 for i in (1, 2, 3)) and a("balloons_strings", 0.7) == 1.0
    assert all(a(f"balloon_{i}", 0.999) > 0.9 for i in (1, 2, 3))  # fading back in
    assert particles_at(obj.effect, duration * 0.12)  # a burst while the first one pops


def test_apples_fall_to_the_ground_then_new_ones_fade_in():
    obj = MANIFEST.object("apples")
    apple = next(layer for layer in obj.layers if layer.id == "apple_1")
    states = [layer_state(obj.effect, apple, obj.effect.duration_ms * k / 400) for k in range(400)]
    fall = max(s.dy for s in states)
    assert fall > 0.3 and obj.box[1] + 0.2 < apple.box[1] + fall <= obj.box[3]  # lands on the ground
    assert any(s.alpha == 0.0 for s in states) and states[-1].alpha > 0.9 and states[-1].dy < 0.01
    falling = [s.dy for s in states if 0 < s.dy < fall]
    assert all(b >= a for a, b in zip(falling, falling[1:], strict=False))  # accelerates down, never up


def test_the_rainbow_cross_fades_tinted_copies_in_place():
    obj = MANIFEST.object("rainbow")
    base, tint = obj.layers[0], obj.layers[1]
    assert layer_state(obj.effect, tint, 0.0).alpha == 0.0
    assert layer_state(obj.effect, tint, obj.effect.duration_ms * 0.35).alpha == pytest.approx(1.0, abs=0.01)
    assert layer_state(obj.effect, base, obj.effect.duration_ms * 0.35) == rest_of(base)  # the art stays
    for layer in obj.layers:  # in place: nothing moves
        assert all(not layer_state(obj.effect, layer, k * 20.0).moves for k in range(100))


def test_the_bubbles_child_swaps_to_blowing_and_bubbles_rise_up_and_left():
    obj = MANIFEST.object("bubbles")
    child = obj.layers[0]
    assert layer_state(obj.effect, child, 100.0).state == "blowing"
    assert layer_state(obj.effect, child, obj.effect.duration_ms * 0.95).state is None
    early = particles_at(obj.effect, obj.effect.duration_ms * 0.3)
    late = particles_at(obj.effect, obj.effect.duration_ms * 0.5)
    assert early and all(p.style == "bubble" for p in early + late)
    assert min(p.y for p in late) < min(p.y for p in early)  # rising
    assert max(p.alpha for p in late) <= 0.9 and all(0 <= p.alpha <= 1 for p in early + late)
    assert max(len(particles_at(obj.effect, obj.effect.duration_ms * k / 100)) for k in range(100)) <= 8


# -- the step model -------------------------------------------------------------------------------------------------


def test_easing_curves():
    assert [ease(n, 0.0) for n in ("linear", "in", "out", "in_out")] == [0.0] * 4
    assert [ease(n, 1.0) for n in ("linear", "in", "out", "in_out")] == [1.0] * 4
    assert ease("linear", 0.5) == 0.5 and ease("in", 0.5) == 0.25 and ease("out", 0.5) == 0.75
    assert ease("in_out", 0.5) == pytest.approx(0.5) and ease("in_out", 0.25) < 0.25
    assert ease("in", -3.0) == 0.0 and ease("out", 9.0) == 1.0  # clamped


def test_effect_progress_is_none_outside_the_effect():
    effect = Effect(1000.0)
    assert effect_progress(effect, 0.0) == 0.0 and effect_progress(effect, 500.0) == 0.5
    for outside in (-0.001, 1000.0, 2000.0, float("nan"), float("inf")):
        assert effect_progress(effect, outside) is None


def test_the_latest_started_transform_wins_and_holds_its_end_value_until_the_next_one():
    layer = Layer("x", (0.4, 0.4, 0.5, 0.5))
    out = Transform("x", 0.0, 0.4, {"dx": Track(((0.0, 0.0), (1.0, 1.0)))}, "linear")
    back = Transform("x", 0.6, 1.0, {"dx": Track(((0.0, -1.0), (1.0, 0.0)))}, "linear")
    effect = Effect(1000.0, (out, back))
    dx = lambda ms: layer_state(effect, layer, ms).dx  # noqa: E731
    assert dx(200) == pytest.approx(0.5) and dx(400) == pytest.approx(1.0)
    assert dx(500) == pytest.approx(1.0)  # between the two: held
    assert dx(600) == pytest.approx(-1.0) and dx(800) == pytest.approx(-0.5)  # a cut, not a glide
    assert dx(999.9999) == pytest.approx(0.0, abs=1e-6) and dx(1000) == 0.0


def test_a_step_sets_only_the_properties_it_names_and_a_track_without_keys_starts_at_rest():
    layer = Layer("x", (0.4, 0.4, 0.5, 0.5), idle_alpha=0.5)
    effect = Effect(1000.0, (Transform("x", 0.0, 1.0, {"rot": Track(osc=(10.0, 1.0, 0.0))}, "linear"),))
    state = layer_state(effect, layer, 250.0)
    assert state.rot == pytest.approx(10.0) and (state.dx, state.dy, state.scale, state.alpha) == (0, 0, 1, 0.5)
    assert layer_state(effect, layer, 500.0).rot == pytest.approx(0.0, abs=1e-9)  # a whole cycle back


def test_swap_shows_its_state_only_inside_its_window_and_sequence_picks_a_frame():
    layer = Layer("x", (0.4, 0.4, 0.5, 0.5))
    effect = Effect(1000.0, (Swap("x", 0.2, 0.6, "blowing"), Sequence("x", 0.5, 1.0, ("a", "b", "c"), 6.0)))
    assert layer_state(effect, layer, 100).state is None and layer_state(effect, layer, 300).state == "blowing"
    assert layer_state(effect, layer, 600).state is None
    assert layer_state(effect, layer, 400).frame is None
    assert [layer_state(effect, layer, ms).frame for ms in (500, 700, 900, 990)] == [0, 1, 2, 2]


def test_steps_and_effects_reject_nonsense():
    with pytest.raises(SceneManifestError):
        Transform("x", 0.5, 0.2, {})
    with pytest.raises(SceneManifestError):
        Transform("x", 0.0, 1.0, {}, ease="bounce")
    with pytest.raises(SceneManifestError):
        Transform("x", 0.0, 1.0, {"colour": Track()})
    with pytest.raises(SceneManifestError):
        Particles(0.0, 1.0, "confetti", (0.5, 0.5), 3, (0, 0), 0.02)
    with pytest.raises(SceneManifestError):
        Particles(0.0, 1.0, "burst", (0.5, 0.5), 0, (0, 0), 0.02)
    with pytest.raises(SceneManifestError):
        Sequence("x", 0.0, 1.0, (), 24.0)
    with pytest.raises(SceneManifestError):
        Effect(0.0)


def test_particles_are_deterministic_alive_only_in_their_window_and_all_gone_by_its_end():
    effect = Effect(2000.0, (Particles(0.2, 0.8, "bubble", (0.5, 0.8), 6, (-0.1, -0.3), 0.03, 0.5),))
    samples = [effect.duration_ms * k / 250 for k in range(250)]
    assert [particles_at(effect, ms) for ms in samples] == [particles_at(effect, ms) for ms in samples]
    assert not particles_at(effect, 0.19 * 2000) and not particles_at(effect, 0.81 * 2000)
    assert any(particles_at(effect, ms) for ms in samples)
    assert particles_at(effect, 0.8 * 2000) == [] or all(p.alpha < 1e-6 for p in particles_at(effect, 0.8 * 2000))
    burst = Effect(1000.0, (Particles(0.0, 0.5, "burst", (0.5, 0.5), 8, (0.1, 0.0), 0.02, 1.0),))
    assert len(particles_at(burst, 100.0)) == 8
    first = particles_at(burst, 50.0)
    assert all(math.hypot(p.x - 0.5, p.y - 0.5) < 0.1 for p in first)


# -- the moving AOI: object_box_at (N2) ------------------------------------------------------------------------------


@pytest.mark.parametrize("object_id", IDS)
def test_the_box_is_the_idle_box_outside_the_effect(object_id):
    box = MANIFEST.object(object_id).box
    duration = MANIFEST.object(object_id).effect.duration_ms
    for elapsed in (-100.0, 0.0, duration, duration + 1000.0, float("nan")):
        assert object_box_at(MANIFEST, object_id, elapsed) == box


@pytest.mark.parametrize("object_id", [i for i in IDS if i not in ("bike", "cloud")])
def test_every_other_objects_box_stays_put_during_its_effect(object_id):
    box = MANIFEST.object(object_id).box
    duration = MANIFEST.object(object_id).effect.duration_ms
    assert all(object_box_at(MANIFEST, object_id, duration * k / 50) == box for k in range(50))


def test_the_bike_box_is_the_idle_box_shifted_by_the_transform_the_canvas_draws():
    x0, y0, x1, y1 = MANIFEST.object("bike").box
    dx = 0.66 * 0.25  # 4.0 s effect: at 1.0 s the first leg (ease in, to 1.02 - 0.36) is a quarter eased
    assert object_box_at(MANIFEST, "bike", 1000.0) == pytest.approx((x0 + dx, y0, x1 + dx, y1))
    # the second leg starts just left of the scene
    assert object_box_at(MANIFEST, "bike", 2000.0) == pytest.approx((-0.02 - (x1 - x0), y0, -0.02, y1))
    # and the same box as the layer state says (one source of truth)
    obj = MANIFEST.object("bike")
    state = layer_state(obj.effect, obj.layers[0], 1000.0)
    assert (state.dx, state.dy, state.rot, state.scale) == pytest.approx((dx, 0, 0, 1))


def test_object_box_at_is_pure_and_deterministic():
    runs = [[object_box_at(MANIFEST, "cloud", ms) for ms in range(0, 3600, 100)] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    before = MANIFEST.object("cloud")
    object_box_at(MANIFEST, "cloud", 1234.0)
    assert MANIFEST.object("cloud") == before
    with pytest.raises(KeyError):
        object_box_at(MANIFEST, "tractor", 0.0)


def test_transform_box_rotates_in_a_square_space_and_shifts():
    box = (0.4, 0.4, 0.6, 0.5)  # 0.2 x 0.1 of the scene; at 4:3 that is 0.2667 x 0.1 square units
    centre = (0.5, 0.45)
    turned = transform_box(box, LayerState(rot=90.0), centre, aspect=4 / 3)
    assert turned == pytest.approx((0.5 - 0.05 / (4 / 3), 0.45 - 0.2667 / 2 * 1.0, 0.5 + 0.05 / (4 / 3), 0.45 + 0.2667 / 2), abs=1e-3)
    assert transform_box(box, LayerState(), centre) == pytest.approx(box)
    assert transform_box(box, LayerState(dx=0.1, dy=-0.2), centre) == pytest.approx((0.5, 0.2, 0.7, 0.3))
    grown = transform_box(box, LayerState(scale=2.0), centre)
    assert grown == pytest.approx((0.3, 0.35, 0.7, 0.55))


# -- loading the manifest (4.7) -----------------------------------------------------------------------------------


def write_scene(root, yaml_text, scene="park"):
    folder = root / "scenes" / scene
    folder.mkdir(parents=True)
    (folder / "scene.yaml").write_text(yaml_text, encoding="utf-8")
    return folder


def test_an_absent_file_gives_the_built_in_scene(tmp_path):
    manifest = load_manifest("park", tmp_path)
    assert manifest.source == "default" and manifest.warning is None and manifest.folder is None
    assert [o.id for o in manifest.objects] == IDS


def test_without_scene_assets_the_built_in_scene_is_used():
    # conftest points the loader at an empty folder (the real park scene: test_choice_park_scene.py)
    assert load_manifest("park").source == "default"


FULL_YAML = """
scene: park
aspect: 1.25
background: background.png
decor:
  - {id: bush, box: [0.3, 0.5, 0.4, 0.6], z: 30, image: layers/bush.png}
objects:
  bike:
    label: Bicycle
    prompt: Ride!
    box: [0.30, 0.40, 0.50, 0.66]
    follows: bike
    duration_ms: 3000
    button_image: buttons/bike.png
    layers:
      - {id: bike, box: [0.30, 0.40, 0.50, 0.66], z: 7, image: objects/bike.png, pivot: [0.4, 0.5],
         states: {pedalling: objects/bike_p.png}}
    blink:
      - {id: rider, layer: bike, x: 0.4, y: 0.45, r: 0.01, image: blink/rider.png, box: [0.39, 0.44, 0.41, 0.46]}
    bob: {amp: 0.01, period_s: 2}
    effect:
      - {kind: transform, layer: bike, t: [0, 0.5], ease: in, tracks: {dx: [[0, 0], [1, 0.7]]}}
      - {kind: transform, layer: bike, t: [0.5, 1], ease: out, tracks: {dx: [[0, -0.6], [1, 0]]}}
      - {kind: swap, layer: bike, t: [0, 0.4], state: pedalling}
      - {kind: particles, t: [0.1, 0.9], style: burst, origin: [0.4, 0.5], count: 4, drift: [0.05, 0], size: 0.02, life: 1}
      - {kind: sequence, layer: bike, t: [0.2, 0.3], frames: [a.png, b.png], fps: 10}
  seesaw:
    effect:
      - {kind: transform, layer: seesaw_plank, t: [0, 1], ease: linear, osc: {rot: [10, 2, 0]}}
"""


def test_a_scene_file_is_read_and_objects_it_does_not_list_keep_the_built_in_placeholders(tmp_path):
    folder = write_scene(tmp_path, FULL_YAML)
    manifest = load_manifest("park", tmp_path)
    assert manifest.source == "file" and manifest.warning is None and manifest.folder == folder
    assert manifest.background == "background.png" and manifest.aspect == 1.25
    assert [layer.id for layer in manifest.decor] == ["bush"]
    bike = manifest.object("bike")
    assert (bike.label, bike.prompt, bike.follows, bike.slot) == ("Bicycle", "Ride!", "bike", 6)
    assert bike.box == (0.30, 0.40, 0.50, 0.66) and bike.effect.duration_ms == 3000.0
    assert bike.layers[0].image == "objects/bike.png" and bike.layers[0].pivot == (0.4, 0.5)
    assert bike.layers[0].states == {"pedalling": "objects/bike_p.png"}
    assert bike.button_image == "buttons/bike.png" and bike.bob == (0.01, 2.0)
    assert bike.blink[0].image == "blink/rider.png" and bike.blink[0].box == (0.39, 0.44, 0.41, 0.46)
    kinds = [step.kind for step in bike.effect.steps]
    assert kinds == ["transform", "transform", "swap", "particles", "sequence"]
    seesaw = manifest.object("seesaw")  # only its effect is overridden; layers, box, duration stay
    assert seesaw.layers == default_manifest().object("seesaw").layers
    assert seesaw.effect.duration_ms == 2000.0 and seesaw.effect.steps[0].tracks["rot"].osc == (10.0, 2.0, 0.0)
    assert manifest.object("swing") == default_manifest().object("swing")  # not listed at all


def test_the_file_drives_the_same_functions_the_moving_aoi_uses(tmp_path):
    write_scene(tmp_path, FULL_YAML)
    manifest = load_manifest("park", tmp_path)
    assert object_box_at(manifest, "bike", 0.0) == (0.30, 0.40, 0.50, 0.66)
    moved = object_box_at(manifest, "bike", 750.0)  # 3.0 s: u = 0.25, ease in -> 0.25 of 0.7
    assert moved == pytest.approx((0.30 + 0.175, 0.40, 0.50 + 0.175, 0.66))
    assert object_box_at(manifest, "bike", 3000.0) == (0.30, 0.40, 0.50, 0.66)


@pytest.mark.parametrize(
    "text",
    [
        "objects: [1, 2]",
        "just text",
        "objects:\n  tractor: {}",
        "objects:\n  bike: {box: [0.5, 0.5, 0.4, 0.4]}",
        "objects:\n  bike: {layers: [{id: a}]}",
        "objects:\n  bike: {follows: wheel}",
        "objects:\n  bike: {effect: [{kind: transform, layer: nope, t: [0, 1]}]}",
        "objects:\n  bike: {effect: [{kind: dance, t: [0, 1]}]}",
        "objects:\n  bike: {effect: [{kind: transform, layer: bike, t: [0.8, 0.2]}]}",
        "objects:\n  bike: {blink: [{id: a, layer: nope, x: 0.1, y: 0.1}]}",
        "aspect: -1",
        "key: [unclosed",
    ],
)
def test_a_broken_file_gives_the_built_in_scene_with_a_warning_and_never_raises(tmp_path, text):
    write_scene(tmp_path, text)
    manifest = load_manifest("park", tmp_path)
    assert manifest.source == "default" and manifest.warning and "scene.yaml" in manifest.warning
    assert manifest.object("bike") == default_manifest().object("bike")


def test_a_scene_name_is_never_a_path(tmp_path):
    write_scene(tmp_path, FULL_YAML)
    for bad in ("../park", "a/b", "", ".."):
        assert load_manifest(bad, tmp_path).source == "default"


def test_the_idle_mode_is_off_blinks_or_blinks_bob_and_anything_else_is_blinks():
    assert [normalise_idle(v) for v in ("off", "blinks", "blinks_bob")] == ["off", "blinks", "blinks_bob"]
    assert [normalise_idle(v) for v in (None, "", "Blinks", 3, "bob")] == ["blinks"] * 5
