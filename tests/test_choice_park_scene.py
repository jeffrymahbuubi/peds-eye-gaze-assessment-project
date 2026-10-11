"""SPEC-scene-cause-effect-task.md step 6: the real park scene (configs/assets/scenes/park/scene.yaml and
its pictures, built by tools/build_park_scene.py). Marked ``real_scene`` so conftest does not pin these
tests to the placeholder scene. Checks: the file loads cleanly with every picture present, every effect
ends at rest (A5), only Bike and Cloud move their look-back box (N2), each eyes-closed patch changes only
pixels near the eyes (N6), and the canvas draws the real scene and is exactly idle again after each
effect (A5)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage

from src.tasks.choice_layout import OBJECTS
from src.tasks.choice_scene import (
    layer_state,
    load_manifest,
    object_box_at,
    particles_at,
    scene_folder,
)
from tests.test_choice_scene_canvas import (  # noqa: F401 (qapp: fixture)
    make_canvas,
    qapp,
    raw,
    scene_for,
    show,
)

pytestmark = pytest.mark.real_scene

IDS = [o.id for o in OBJECTS]


@pytest.fixture(scope="module")
def manifest():
    return load_manifest("park")


def test_the_park_scene_file_loads_without_warning_and_every_picture_exists(manifest):
    assert manifest.warning is None
    assert manifest.source != "default"
    assert sorted(o.id for o in manifest.objects) == sorted(IDS)
    root = scene_folder("park")
    pictures = [manifest.background] + [d.image for d in manifest.decor]
    for obj in manifest.objects:
        for layer in obj.layers:
            pictures += [layer.image, *(layer.states or {}).values()]
        pictures += [spot.image for spot in obj.blink]
    missing = [p for p in pictures if p and not (root / p).is_file()]
    assert not missing


@pytest.mark.parametrize("object_id", IDS)
def test_every_park_effect_ends_with_every_layer_at_rest(manifest, object_id):
    obj = manifest.object(object_id)
    end = obj.effect.duration_ms
    assert [layer.id for layer in obj.layers if layer_state(obj.effect, layer, end).moves] == []
    assert particles_at(obj.effect, end) == []


@pytest.mark.parametrize("object_id", IDS)
def test_only_bike_and_cloud_move_their_box_and_it_comes_back(manifest, object_id):
    obj = manifest.object(object_id)
    end = obj.effect.duration_ms
    middle = object_box_at(manifest, object_id, end / 2)
    if object_id in ("bike", "cloud"):
        assert middle != pytest.approx(obj.box)  # off the picture half way
    else:
        assert middle == pytest.approx(obj.box)
    assert object_box_at(manifest, object_id, end) == pytest.approx(obj.box)


def test_each_blink_patch_changes_only_pixels_near_the_eyes(manifest):
    root = scene_folder("park")
    anchor = QImage(str(root / "reference" / "style_anchor.png")).convertToFormat(QImage.Format.Format_RGB32)
    spots = [spot for obj in manifest.objects for spot in obj.blink]
    assert len(spots) == 5
    for spot in spots:
        patch = QImage(str(root / spot.image)).convertToFormat(QImage.Format.Format_RGB32)
        x0, y0 = round(spot.box[0] * anchor.width()), round(spot.box[1] * anchor.height())
        changed, border_changed = 0, 0
        for y in range(patch.height()):
            for x in range(patch.width()):
                a, b = patch.pixelColor(x, y), anchor.pixelColor(x0 + x, y0 + y)
                if max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())) > 3:
                    changed += 1
                    if x < 2 or y < 2 or x >= patch.width() - 2 or y >= patch.height() - 2:
                        border_changed += 1
        assert changed > 20, spot.id  # the eyes are closed
        assert border_changed == 0, spot.id  # the patch blends into the face it covers
        assert changed < 0.4 * patch.width() * patch.height(), spot.id


@pytest.mark.parametrize("object_id", IDS)
def test_the_real_scene_draws_and_is_exactly_idle_again_after_each_effect(qapp, manifest, object_id):  # noqa: F811
    canvas = make_canvas()
    idle = show(canvas, scene_for())
    duration = manifest.object(object_id).effect.duration_ms
    effect = {"object": object_id, "t_start": 0, "duration_ms": duration, "modelled": False}
    during = show(canvas, scene_for(effect={**effect, "elapsed_ms": duration * 0.3}))
    after = show(canvas, scene_for())
    assert raw(during) != raw(idle)
    assert raw(after) == raw(idle)
