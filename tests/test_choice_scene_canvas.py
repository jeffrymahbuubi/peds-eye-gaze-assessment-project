"""SPEC-scene-cause-effect-task.md step 4, offscreen Qt: the canvas "scene" mode (4.5, N1, N3, N5),
acceptance A5 (every effect returns the picture to idle), A8 (the idle clock stops with a pause), A9
(the frame time stays fine during an effect) and the canvas side of A1.

The scene is described by ``ChoiceMakingTask.scene_spec()``; the tests take one from a real task and
override the parts they pin (the effect, the hover, the cue ...). Pixels are read back from
``canvas.grab()``. Offscreen Qt has no font database, so nothing here depends on text."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import random
import statistics
import time

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.tasks.choice_layout import OBJECTS
from src.tasks.choice_scene import object_box_at
from src.tasks.choice_scene_defaults import default_manifest
from src.ui.canvas import TaskCanvas
from src.ui.scene_canvas import CACHE_LIMIT, MIN_PAINT_S, SceneView
from tests.test_choice_making import make

THEME = {
    "background": "#e8f5e9", "cursor_color": "#1b5e20", "target_default": "#ff5252",
    "particle_color": "#66bb6a",
}
MANIFEST = default_manifest()
IDS = [o.id for o in OBJECTS]
W, H = 960, 540


class Clock:
    """A clock the test moves by hand (the scene view reads it for the idle clock and the repaint cap)."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def scene_for(w: int = W, h: int = H, **overrides) -> dict:
    task, _spy, _fb = make()
    task.set_screen_size(w, h)
    spec = task.scene_spec()
    spec["idle_animation"] = "off"  # no blinks unless a test asks for them
    spec.update(overrides)
    return spec


def effect_of(object_id: str, elapsed_ms: float, modelled: bool = False) -> dict:
    duration = MANIFEST.object(object_id).effect.duration_ms
    return {"object": object_id, "t_start": 0, "duration_ms": duration, "modelled": modelled, "elapsed_ms": elapsed_ms}


def make_canvas(w: int = W, h: int = H, clock: Clock | None = None) -> TaskCanvas:
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(w, h)
    canvas._scene_view._clock = clock or Clock()
    canvas._scene_view._rng = random.Random(4)
    return canvas


def show(canvas: TaskCanvas, spec: dict, **frame) -> QImage:
    """Give the canvas ``spec`` the way the app does (one ``set_frame``), then grab it."""
    canvas.set_frame(
        target_xy_norm=None, target_radius_px=90.0, cursor_xy_norm=(0.5, 0.5), cursor_valid=False,
        dwell_progress=frame.pop("dwell_progress", 0.0), selectable=frame.pop("selectable", True),
        scene=spec, **frame,
    )
    return canvas.grab().toImage()


def scene_px(spec: dict, fx: float, fy: float) -> tuple[int, int]:
    x, y, w, h = spec["scene_rect"]
    return round(x + fx * w), round(y + fy * h)


def near(colour: QColor, hex_colour: str, tol: int = 6) -> bool:
    want = QColor(hex_colour)
    return all(abs(a - b) <= tol for a, b in ((colour.red(), want.red()), (colour.green(), want.green()), (colour.blue(), want.blue())))


def raw(image: QImage) -> bytes:
    """The pixels of an image as bytes (a QImage is not hashable)."""
    return bytes(image.constBits())


def max_channel_diff(a: QImage, b: QImage, spec: dict, stride: int = 3) -> int:
    """The largest difference in any colour channel between two grabs, over the scene (every
    ``stride``-th pixel)."""
    x0, y0, w, h = (round(v) for v in spec["scene_rect"])
    worst = 0
    for y in range(y0, y0 + h, stride):
        for x in range(x0, x0 + w, stride):
            pa, pb = a.pixelColor(x, y), b.pixelColor(x, y)
            worst = max(worst, abs(pa.red() - pb.red()), abs(pa.green() - pb.green()), abs(pa.blue() - pb.blue()))
    return worst


def scene_region_differs(a: QImage, b: QImage, spec: dict) -> bool:
    x, y, w, h = (round(v) for v in spec["scene_rect"])
    return a.copy(x, y, w, h) != b.copy(x, y, w, h)


# -- the picture at rest -------------------------------------------------------------------------------------------


def test_the_scene_draws_the_backdrop_the_objects_and_the_eight_buttons(qapp):
    canvas = make_canvas()
    spec = scene_for()
    image = show(canvas, spec)
    assert not image.isNull() and (image.width(), image.height()) == (W, H)
    sky = image.pixelColor(*scene_px(spec, 0.05, 0.02))
    assert sky.blue() > sky.red() + 20  # the backdrop
    assert near(image.pixelColor(*scene_px(spec, 0.89, 0.0925)), "#fdd835")  # the yellow balloon
    assert near(image.pixelColor(*scene_px(spec, 0.25, 0.30)), "#43a047")  # the apple tree
    for button in spec["buttons"]:  # every button: white card, the object's swatch in it
        x, y, w, h = button["rect"]
        assert near(image.pixelColor(round(x + 12), round(y + h / 2)), "#ffffff", 3)
        swatch = image.pixelColor(round(x + w / 2), round(y + h * 0.37))
        assert near(swatch, MANIFEST.object(button["object"]).colour, 4), button["object"]
    left_edge = image.pixelColor(10, 10)
    assert near(left_edge, THEME["background"], 3)  # the empty corner cell is the canvas background


def test_the_bush_is_in_front_of_the_bike_at_rest_and_while_it_moves(qapp):
    canvas = make_canvas()
    spec = scene_for()
    at_rest = show(canvas, spec)
    bush = scene_px(spec, 0.375, 0.63)
    assert near(at_rest.pixelColor(*bush), "#2e7d32", 4)
    spec["effect"] = effect_of("bike", 400.0)  # a little way into the first leg: still overlapping the bush
    moving = show(canvas, spec)
    assert near(moving.pixelColor(*bush), "#2e7d32", 4)


def test_without_a_scene_rect_nothing_crashes_and_the_buttons_are_the_only_thing_drawn(qapp):
    canvas = make_canvas()
    spec = scene_for()
    spec["scene_rect"] = (0.0, 0.0, 0.0, 0.0)
    assert not show(canvas, spec).isNull()


# -- A5: every effect returns the picture to idle ----------------------------------------------------------------


@pytest.mark.parametrize("object_id", IDS)
def test_an_effect_changes_the_picture_and_the_picture_is_exactly_idle_again_afterwards(qapp, object_id):
    canvas = make_canvas()
    spec = scene_for()
    idle = show(canvas, spec)
    duration = MANIFEST.object(object_id).effect.duration_ms
    changed = False
    for k in range(1, 30):
        spec["effect"] = effect_of(object_id, duration * k / 30)
        changed |= scene_region_differs(idle, show(canvas, spec), spec)
    assert changed, f"{object_id}: the effect never changed the picture"
    # The last moment is (all but) the idle picture: a fade 99.98 % done, a swing still turned by
    # 0.05 degrees. Only antialiasing differs (a layer left displaced would differ by 100 or more).
    spec["effect"] = effect_of(object_id, duration - 0.5)
    assert max_channel_diff(idle, show(canvas, spec), spec) <= 30
    spec["effect"] = None
    assert show(canvas, spec).copy(*(round(v) for v in spec["scene_rect"])) == idle.copy(*(round(v) for v in spec["scene_rect"]))


def test_the_balloons_pop_one_after_another_and_come_back(qapp):
    canvas = make_canvas()
    spec = scene_for()
    yellow = scene_px(spec, 0.89, 0.0925)
    assert near(show(canvas, spec).pixelColor(*yellow), "#fdd835")
    spec["effect"] = effect_of("balloons", 0.45 * 3500)  # the yellow one has popped; strings remain
    popped = show(canvas, spec)
    assert not near(popped.pixelColor(*yellow), "#fdd835", 60)
    spec["effect"] = effect_of("balloons", 0.999 * 3500)  # fading back in
    assert near(show(canvas, spec).pixelColor(*yellow), "#fdd835", 40)


def test_a_timeout_model_looks_the_same_as_a_hit_except_for_the_selected_highlight(qapp):
    canvas = make_canvas()
    spec = scene_for()
    spec["effect"] = effect_of("swing", 1800.0, modelled=False)
    hit = show(canvas, spec)
    spec["effect"] = effect_of("swing", 1800.0, modelled=True)
    assert scene_region_differs(hit, show(canvas, spec), spec) is False  # same picture; the highlight
    spec["effect"] = effect_of("swing", 100.0, modelled=False)  # is on the button, early in the effect
    selected = show(canvas, spec)
    spec["effect"] = effect_of("swing", 100.0, modelled=True)
    modelled = show(canvas, spec)
    slot = OBJECTS[[o.id for o in OBJECTS].index("swing")].slot
    bx, by, bw, bh = (round(v) for v in spec["buttons"][slot]["rect"])
    assert selected.copy(bx, by, bw, bh) != modelled.copy(bx, by, bw, bh)
    assert selected.copy(0, 0, 10, 10) == modelled.copy(0, 0, 10, 10)


# -- N2: the AOI is the box the canvas draws ---------------------------------------------------------------------


def bbox_of(image: QImage, spec: dict, predicate) -> tuple[int, int, int, int] | None:
    x0, y0, w, h = (round(v) for v in spec["scene_rect"])
    xs, ys = [], []
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if predicate(image.pixelColor(x, y)):
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


@pytest.mark.parametrize(
    ("object_id", "colour", "elapsed"),
    [("bike", "#3949ab", 1000.0), ("bike", "#3949ab", 3000.0), ("cloud", QColor("#78909c").lighter(160).name(), 700.0),
     ("cloud", QColor("#78909c").lighter(160).name(), 2800.0)],
)
def test_what_the_canvas_draws_of_a_moving_object_is_inside_object_box_at(qapp, object_id, colour, elapsed):
    canvas = make_canvas()
    spec = scene_for()
    spec["effect"] = effect_of(object_id, elapsed)
    image = show(canvas, spec)
    drawn = bbox_of(image, spec, lambda c: near(c, colour, 3))
    assert drawn is not None
    sx, sy, sw, sh = spec["scene_rect"]
    box = object_box_at(MANIFEST, object_id, elapsed, aspect=sw / sh)
    px = (sx + box[0] * sw, sy + box[1] * sh, sx + box[2] * sw, sy + box[3] * sh)
    pad = 4
    visible_x0, visible_x1 = max(px[0], sx), min(px[2], sx + sw)  # the part of the box on the picture
    assert drawn[0] >= visible_x0 - pad and drawn[2] <= visible_x1 + pad
    assert drawn[1] >= px[1] - pad and drawn[3] <= px[3] + pad
    # ... and it fills a good part of the box (the AOI is where the object really is)
    assert (drawn[2] - drawn[0]) >= 0.4 * (visible_x1 - visible_x0)


# -- N5: the cache and the repaint cap ---------------------------------------------------------------------------


def test_the_idle_scene_is_rendered_once_and_reused_every_frame(qapp):
    canvas = make_canvas()
    view = canvas._scene_view
    spec = scene_for()
    for _ in range(10):
        show(canvas, spec)
        canvas._scene_view._clock.t += 0.02
    assert view.cache_builds == 1  # one cached pixmap of the whole idle scene


def test_the_first_frame_of_an_effect_does_not_render_the_cache_because_the_prompt_warmed_it(qapp):
    canvas = make_canvas()
    view = canvas._scene_view
    spec = scene_for()
    show(canvas, spec)
    spec["prompt_object"] = "bike"  # the prompt starts: the cache for the bike's effect is built now
    show(canvas, spec)
    built = view.cache_builds
    assert built == 2
    spec["effect"] = effect_of("bike", 0.0)
    for k in range(0, 4000, 100):
        spec["effect"] = effect_of("bike", float(k))
        show(canvas, spec)
    assert view.cache_builds == built  # the whole effect drew from the warmed cache
    spec["effect"] = effect_of("cloud", 0.0)  # an effect nobody prompted is built on the spot, once
    show(canvas, spec)
    show(canvas, spec)
    assert view.cache_builds == built + 1


def test_the_cached_pixmaps_follow_the_device_pixel_ratio_and_the_scene_sits_on_whole_device_pixels(qapp):
    view = SceneView(THEME)
    spec = scene_for()
    assert view._scene_rect({"scene_rect": (0.0, 0.0, 0.0, 10.0)}, 1.0) is None and view._scene_rect(spec, 0.0) is None
    assert view._scene_rect({}, 1.0) is None
    for dpr in (1.0, 1.25, 1.5, 2.0):
        rect = view._scene_rect(spec, dpr)
        assert rect is not None
        for value in (rect.x(), rect.y(), rect.width(), rect.height()):
            assert value * dpr == pytest.approx(round(value * dpr), abs=1e-9)
        view.sync(spec, dpr)
        first = view._segments(frozenset(), rect.size(), dpr)[0]
        assert first.devicePixelRatio() == dpr and first.width() == round(rect.width() * dpr)
        assert first.deviceIndependentSize().width() == pytest.approx(rect.width(), abs=1e-6)
    canvas = make_canvas()
    canvas.devicePixelRatioF = lambda: 1.5  # a laptop at 150 %: paints without trouble
    assert not show(canvas, scene_for(idle_animation="blinks_bob", effect=effect_of("bike", 1000.0))).isNull()


def test_the_cache_is_dropped_when_the_canvas_changes_size_and_stays_small(qapp):
    canvas = make_canvas()
    view = canvas._scene_view
    spec = scene_for()
    show(canvas, spec)
    canvas.resize(W + 100, H + 60)
    show(canvas, scene_for(W + 100, H + 60))
    assert view.cache_builds == 2
    spec = scene_for(W + 100, H + 60)
    for object_id in IDS:  # eight different animating sets
        spec["effect"] = effect_of(object_id, 10.0)
        show(canvas, spec)
    assert len(view._cache) <= CACHE_LIMIT


def test_scene_repaints_are_capped_at_about_60_hz_while_the_gaze_loop_keeps_its_rate(qapp):
    clock = Clock()
    canvas = make_canvas(clock=clock)
    spec = scene_for()
    requests: list[float] = []
    canvas.update = lambda *a: requests.append(clock.t)  # what set_frame asks Qt for
    ticks = 0
    for _ in range(300):  # a 150 Hz loop (6.67 ms per tick) for two seconds
        canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene=spec)
        clock.t += 1 / 150
        ticks += 1
    assert 90 <= len(requests) <= 150  # about 60 Hz (not 150)
    gaps = [b - a for a, b in zip(requests, requests[1:], strict=False)]
    assert min(gaps) >= MIN_PAINT_S - 1e-9 and max(gaps) <= MIN_PAINT_S + 1 / 150 + 1e-9
    # a loop at or below 60 Hz is never thinned
    requests.clear()
    for _ in range(120):
        canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene=spec)
        clock.t += 0.0167
    assert len(requests) == 120


def test_other_modes_are_not_throttled(qapp):
    canvas = make_canvas()
    requests: list[int] = []
    canvas.update = lambda *a: requests.append(1)
    for _ in range(50):
        canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene={"mode": "single"})
    assert len(requests) == 50


# -- N3: idle life ------------------------------------------------------------------------------------------------------


def spots_px(spec: dict) -> list[tuple[int, int]]:
    return [scene_px(spec, spot.x, spot.y) for spot in MANIFEST.characters()]


def idle_images(mode: str, seconds: float = 40.0, step: float = 0.05) -> list[QImage]:
    """The canvas grabbed every ``step`` seconds of canvas time with ``mode`` on."""
    clock = Clock()
    canvas = make_canvas(clock=clock)
    spec = scene_for(idle_animation=mode)
    images = []
    for _ in range(int(seconds / step)):
        clock.t += step
        images.append(show(canvas, spec))
    return images


def test_off_is_a_still_picture(qapp):
    images = idle_images("off", 30.0, 0.1)
    assert all(img == images[0] for img in images)


def test_blinks_close_the_eyes_for_a_moment_and_the_picture_is_otherwise_the_same(qapp):
    images = idle_images("blinks", 40.0, 0.05)
    base = images[0]
    odd = [i for i, img in enumerate(images) if img != base]
    assert odd, "nobody blinked in 40 s"
    assert len(odd) < len(images) * 0.4  # a blink is brief
    # a blink changes only the pixels around the eyes
    spec = scene_for()
    boxes = [(x - 40, y - 25, 80, 50) for x, y in spots_px(spec)]
    for i in odd[:5]:
        diff = [(x, y) for y in range(H) for x in range(W) if images[i].pixel(x, y) != base.pixel(x, y)]
        assert diff and all(any(bx <= x < bx + bw and by <= y < by + bh for bx, by, bw, bh in boxes) for x, y in diff)


def test_bob_moves_the_balloons_and_the_cloud_a_little_and_nothing_else(qapp):
    images = idle_images("blinks_bob", 10.0, 0.25)
    spec = scene_for()
    sx, sy, sw, sh = (round(v) for v in spec["scene_rect"])
    assert any(a != b for a, b in zip(images, images[1:], strict=False))  # the balloons and the cloud bob
    # Nothing else does: a patch of the apple tree (no character, no bob) is the same in every frame.
    tx, ty = scene_px(spec, 0.25, 0.30)
    patch = (tx - 20, ty - 20, 40, 40)
    assert len({raw(img.copy(*patch)) for img in images}) == 1
    # The balloons themselves move, by a few pixels at most (0.6 % of the scene height).
    strings_y = {raw(img.copy(*(round(v) for v in (sx + 0.84 * sw, sy + 0.10 * sh, 0.1 * sw, 0.12 * sh)))) for img in images}
    assert len(strings_y) > 1


def test_idle_life_is_frozen_during_an_effect_and_a_pause_does_not_advance_it(qapp):
    clock = Clock()
    canvas = make_canvas(clock=clock)
    view = canvas._scene_view
    spec = scene_for(idle_animation="blinks_bob")
    show(canvas, spec)
    clock.t += 0.05
    show(canvas, spec)
    idle_t = view.idle.t
    assert idle_t == pytest.approx(0.05)
    spec["effect"] = effect_of("rainbow", 500.0)
    for _ in range(20):
        clock.t += 0.05
        show(canvas, spec)
    assert view.idle.t == idle_t  # an effect: idle life does not run
    spec["effect"] = None
    canvas.set_paused(True)  # A8: a pause
    clock.t += 60.0  # a minute passes with no tick at all
    canvas.set_paused(False)
    clock.t += 0.02
    show(canvas, spec)
    assert view.idle.t == pytest.approx(idle_t, abs=1e-9)  # the first tick after a pause counts no time
    clock.t += 0.02
    show(canvas, spec)
    assert view.idle.t == pytest.approx(idle_t + 0.02)


def test_a_long_gap_between_ticks_advances_the_idle_clock_by_at_most_a_tenth_of_a_second(qapp):
    clock = Clock()
    canvas = make_canvas(clock=clock)
    spec = scene_for(idle_animation="blinks")
    show(canvas, spec)
    clock.t += 30.0
    show(canvas, spec)
    assert canvas._scene_view.idle.t == pytest.approx(0.1)


def test_changing_the_idle_mode_between_frames_is_picked_up(qapp):
    canvas = make_canvas()
    show(canvas, scene_for(idle_animation="off"))
    assert canvas._scene_view.idle.mode == "off"
    show(canvas, scene_for(idle_animation="blinks_bob"))
    assert canvas._scene_view.idle.mode == "blinks_bob"


# -- the buttons: glow, rings, cue, pause --------------------------------------------------------------------------


def button_region(image: QImage, spec: dict, slot: int, grow: int = 30) -> QImage:
    x, y, w, h = (round(v) for v in spec["buttons"][slot]["rect"])
    return image.copy(max(0, x - grow), max(0, y - grow), w + 2 * grow, h + 2 * grow)


def test_the_glow_follows_the_gaze_in_switch_mode_and_is_off_with_dwell(qapp):
    canvas = make_canvas()
    spec = scene_for(hover_slot=-1)
    plain = show(canvas, spec)
    spec["hover_slot"] = 3
    canvas.show_glow = False  # Dwell: the setting is stored but not shown (W3)
    canvas.show_instant_feedback = False
    canvas.show_progress_ring = False
    assert show(canvas, spec) == plain
    canvas.show_glow = True  # Switch: the looked-at button lights
    glowing = show(canvas, spec)
    assert button_region(glowing, spec, 3) != button_region(plain, spec, 3)
    for other in (0, 1, 4, 5, 6, 7):  # only that button (its neighbour above sits inside the halo)
        assert button_region(glowing, spec, other, 0) == button_region(plain, spec, other, 0)
    assert show(canvas, scene_for(hover_slot=-1)) == plain  # looking away: it goes out


def test_nothing_is_lit_while_selection_is_blocked_by_the_prompt(qapp):
    canvas = make_canvas()
    spec = scene_for(hover_slot=-1)
    plain = show(canvas, spec)
    canvas.show_glow = canvas.show_instant_feedback = canvas.show_progress_ring = True
    spec["hover_slot"] = 3
    assert show(canvas, spec, selectable=False, dwell_progress=0.5) == plain


def test_the_instant_ring_and_the_dwell_ring_are_drawn_round_the_looked_at_button(qapp):
    canvas = make_canvas()
    spec = scene_for(hover_slot=5)
    canvas.show_glow = False
    canvas.show_instant_feedback = False
    canvas.show_progress_ring = False
    plain = show(canvas, spec)
    canvas.show_instant_feedback = True
    instant = show(canvas, spec)
    assert instant != plain
    canvas.show_progress_ring = True
    half = show(canvas, spec, dwell_progress=0.5)
    full = show(canvas, spec, dwell_progress=1.0)
    assert half != instant and full != half
    assert show(canvas, spec, dwell_progress=0.0) == instant  # no progress, no arc


def test_the_visual_cue_pulses_the_target_button_about_once_a_second(qapp):
    clock = Clock()
    canvas = make_canvas(clock=clock)
    spec = scene_for(cue_slot=6)
    cued, uncued = [], []
    for _ in range(40):
        clock.t += 0.05  # two seconds
        cued.append(raw(button_region(show(canvas, spec), spec, 6, 6)))
        uncued.append(raw(button_region(show(canvas, scene_for(cue_slot=-1)), spec, 6, 6)))
    assert len(set(uncued)) == 1  # no cue: the button is still
    assert len(set(cued)) > 5  # the cue pulses (border width and alpha change)
    assert all(c != uncued[0] for c in cued)  # and the button never looks like an uncued one
    other = show(canvas, spec)  # only the cued button pulses
    assert button_region(other, spec, 2, 0) == button_region(show(canvas, scene_for(cue_slot=-1)), spec, 2, 0)


def test_a_paused_canvas_shows_paused_and_not_the_scene(qapp):
    canvas = make_canvas()
    spec = scene_for()
    show(canvas, spec)
    canvas.set_paused(True)
    image = canvas.grab().toImage()
    assert near(image.pixelColor(*scene_px(spec, 0.89, 0.0925)), THEME["background"], 3)
    canvas.set_paused(False)
    assert near(canvas.grab().toImage().pixelColor(*scene_px(spec, 0.89, 0.0925)), "#fdd835")


# -- pictures from a scene folder ----------------------------------------------------------------------------------


def test_pictures_named_in_a_scene_file_are_drawn_instead_of_the_placeholders(qapp, tmp_path, monkeypatch):
    folder = tmp_path / "scenes" / "park"
    folder.mkdir(parents=True)
    for name, colour, size in (("background.png", "#ff00ff", (40, 30)), ("bike.png", "#00ffff", (20, 20)), ("btn.png", "#ffff00", (30, 30))):
        image = QImage(*size, QImage.Format.Format_ARGB32)
        image.fill(QColor(colour))
        assert image.save(str(folder / name))
    (folder / "scene.yaml").write_text(
        "background: background.png\n"
        "objects:\n"
        "  bike:\n"
        "    button_image: btn.png\n"
        "    layers:\n"
        "      - {id: bike, box: [0.36, 0.42, 0.47, 0.63], z: 7, image: bike.png}\n"
        "    blink: []\n"
        "    effect:\n"
        "      - {kind: transform, layer: bike, t: [0, 1], ease: linear, tracks: {dx: [[0, 0], [1, 0.3]]}}\n"
        "    follows: bike\n",
        encoding="utf-8",
    )
    import src.ui.scene_canvas as scene_canvas

    real = scene_canvas.load_manifest
    monkeypatch.setattr(scene_canvas, "load_manifest", lambda name: real(name, tmp_path))
    canvas = make_canvas()
    spec = scene_for()
    image = show(canvas, spec)
    assert canvas._scene_view.manifest.source == "file"
    assert near(image.pixelColor(*scene_px(spec, 0.05, 0.02)), "#ff00ff", 3)  # the background picture
    assert near(image.pixelColor(*scene_px(spec, 0.415, 0.52)), "#00ffff", 3)  # the bike picture, not the shape
    x, y, w, h = spec["buttons"][6]["rect"]
    assert near(image.pixelColor(round(x + w / 2), round(y + h * 0.37)), "#ffff00", 3)  # the button picture
    spec["effect"] = effect_of("bike", 2000.0)  # the picture moves with the effect (dx 0.15 at half way)
    moved = show(canvas, spec)
    assert near(moved.pixelColor(*scene_px(spec, 0.415 + 0.15 * 0.5, 0.52)), "#00ffff", 3) or near(moved.pixelColor(*scene_px(spec, 0.415 + 0.15, 0.52)), "#00ffff", 3)
    assert not near(moved.pixelColor(*scene_px(spec, 0.415, 0.52)), "#00ffff", 3)


def test_a_missing_picture_file_falls_back_to_the_placeholder(qapp, tmp_path, monkeypatch):
    folder = tmp_path / "scenes" / "park"
    folder.mkdir(parents=True)
    (folder / "scene.yaml").write_text("background: nope.png\n", encoding="utf-8")
    import src.ui.scene_canvas as scene_canvas

    real = scene_canvas.load_manifest
    monkeypatch.setattr(scene_canvas, "load_manifest", lambda name: real(name, tmp_path))
    canvas = make_canvas()
    spec = scene_for()
    sky = show(canvas, spec).pixelColor(*scene_px(spec, 0.05, 0.02))
    assert sky.blue() > sky.red() + 20


# -- A9: the frame time during an effect ------------------------------------------------------------------------------


def frame_times(object_id: str, w: int, h: int, frames: int = 60, animate: bool = True) -> list[float]:
    """Milliseconds of ``set_frame`` + a full paint at ``frames`` points of ``object_id``'s effect (or of
    the idle picture, with ``animate`` off)."""
    canvas = make_canvas(w, h, clock=Clock())
    spec = scene_for(w, h, prompt_object=object_id)
    show(canvas, spec)  # idle + warm-up, as at the prompt
    duration = MANIFEST.object(object_id).effect.duration_ms
    times = []
    for k in range(frames):
        spec["effect"] = effect_of(object_id, duration * k / frames) if animate else None
        canvas._scene_view._clock.t += 0.0167
        start = time.perf_counter()
        canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene=spec)
        canvas.grab()
        times.append((time.perf_counter() - start) * 1000)
    return times


def test_a9_the_paint_time_stays_small_during_every_effect(qapp):
    """Indicative only (offscreen, this PC); the real measure is in the live check on the target
    laptop. The bounds are generous: the point is that an effect is not many times slower than the
    idle picture, and that nothing in it renders a pixmap per frame."""
    idle = statistics.median(frame_times("bike", 1920, 1032, animate=False))
    report = {}
    for object_id in IDS:
        times = frame_times(object_id, 1920, 1032)
        report[object_id] = (statistics.median(times), max(times))
    print(
        f"A9 paint ms at 1920x1032, idle picture median {idle:.1f}; effects (median, max):",
        {k: (round(a, 1), round(b, 1)) for k, (a, b) in report.items()},
    )
    for object_id, (median, worst) in report.items():
        assert median < 40.0, f"{object_id}: median frame {median:.1f} ms"
        assert worst < 250.0, f"{object_id}: slowest frame {worst:.1f} ms"
        assert median < 3 * idle + 5.0, f"{object_id}: an effect frame costs {median:.1f} ms against {idle:.1f} idle"


def test_a9_the_tick_interval_holds_during_an_effect_with_a_real_qtimer(qapp):
    """The app's loop in miniature: a 16 ms QTimer drives set_frame and a paint through a 1.2 s part of
    the bike's effect, and the interval between ticks is measured."""
    canvas = TaskCanvas(theme=THEME)
    canvas.resize(1920, 1032)
    canvas.show()
    spec = scene_for(1920, 1032, prompt_object="bike")
    canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene=spec)  # warm up
    stamps: list[float] = []
    started = time.perf_counter()
    timer = QTimer()

    def tick() -> None:
        now = time.perf_counter()
        stamps.append(now)
        spec["effect"] = effect_of("bike", min((now - started) * 1000, 3999.0))
        canvas.set_frame(None, 90.0, (0.5, 0.5), True, 0.0, scene=spec)
        canvas.repaint()

    timer.timeout.connect(tick)
    timer.start(16)
    while time.perf_counter() - started < 1.2:
        qapp.processEvents()
        time.sleep(0.001)
    timer.stop()
    intervals = [(b - a) * 1000 for a, b in zip(stamps, stamps[1:], strict=False)]
    assert len(intervals) > 15
    print(
        "A9 tick interval ms (median, p95, max), 16 ms QTimer, bike effect:",
        round(statistics.median(intervals), 1),
        round(sorted(intervals)[int(len(intervals) * 0.95)], 1),
        round(max(intervals), 1),
    )
    assert statistics.median(intervals) < 40.0
    assert max(intervals) < 300.0
