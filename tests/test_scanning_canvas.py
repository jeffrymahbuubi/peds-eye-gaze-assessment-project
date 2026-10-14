"""SPEC-scanning-search-cues.md 4.3, 4.4, S4, S7, acceptance C4 (the render half): what the canvas draws
for Scanning Search's start dot, sample and Match the sample's bright field, on a rendered offscreen
canvas, and the spoken sample's sound bank (``SearchAudio``)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.app import GuiFeedback
from src.engine.config import load_task_config
from src.engine.target_size import ICON_DRAW_FRAC
from src.tasks.base_task import Phase
from src.tasks.search_cues import SHAPE_NAMES, prompt_wav_path
from src.ui.canvas import TaskCanvas
from src.ui.canvas_trace import INSTANT_OFFSET_PX, SELECTABLE_OFFSET_PX
from src.ui.scene_audio import VOLUME, SearchAudio
from tests.test_scanning_search import CENTRE, MS, at_slot, make, run, write_wav

_BG, _RING, _TARGET = "#000000", "#00ff00", "#ff0000"
_THEME = {"background": _BG, "cursor_color": _RING, "target_default": _TARGET}
_W, _H = 1000, 600


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _frame(task, canvas, t_ms, pointer):
    """Advance the task to ``t_ms`` and give the canvas that frame, as ``AssessmentApp._tick`` does."""
    task.set_screen_size(_W, _H)
    result = task.update(t_ms * MS, pointer)
    canvas.set_frame(
        target_xy_norm=result.target_xy_norm,
        target_radius_px=(result.target_radius_px if result.target else 90.0),
        cursor_xy_norm=result.cursor_xy_norm, cursor_valid=pointer.valid,
        dwell_progress=result.dwell_progress, selectable=result.selectable,
        layout_slots=task.layout_slots, on_target=result.on_target, scene=task.scene_spec(),
        active_slot=(result.target.slot_index if result.target else -1),
    )
    return canvas.grab().toImage()


def _canvas():
    canvas = TaskCanvas(theme=_THEME)
    canvas.resize(_W, _H)
    canvas.show_cursor = False
    return canvas


def _px(image, x, y) -> QColor:
    return image.pixelColor(round(x), round(y))


def _near(colour: QColor, hex_colour: str, tol=70) -> bool:
    want = QColor(hex_colour)
    return all(abs(a - b) <= tol for a, b in ((colour.red(), want.red()), (colour.green(), want.green()), (colour.blue(), want.blue())))


def _centre_of(task, slot):
    x, y = task.icon_slots[slot]
    return x * _W, y * _H


def _task(**kwargs):
    task, spy, feedback = make(**kwargs)
    task.set_screen_size(_W, _H)
    return task, spy, feedback


# -- the start dot ----------------------------------------------------------------------------------------


def test_the_start_dot_is_the_only_thing_drawn_and_is_a_degree_wide(qapp):
    task, _spy, _fb = _task(mode="pop_out", start_dot=True)
    canvas = _canvas()
    image = _frame(task, canvas, 0, at_slot(task, 0))
    r = task.start_dot_px / 2
    assert _near(_px(image, _W / 2, _H / 2), _RING)
    assert _near(_px(image, _W / 2 + r - 2, _H / 2), _RING)
    assert not _near(_px(image, _W / 2 + r + 3, _H / 2), _RING, tol=30)
    for slot in range(4):  # no field, faint or bright, while the dot is up
        assert _near(_px(image, *_centre_of(task, slot)), _BG, tol=20)


def test_pop_out_shows_its_faint_field_between_the_dot_and_the_target(qapp):
    task, _spy, _fb = _task(mode="pop_out", start_dot=True)
    canvas = _canvas()
    _frame(task, canvas, 0, CENTRE)
    image = _frame(task, canvas, 300, CENTRE)  # the dot went: the trial is up
    assert task.phase is Phase.WAIT_INPUT
    target = task.targets[0].slot_index
    other = (target + 1) % 4
    assert not _near(_px(image, *_centre_of(task, other)), _BG, tol=20)  # a faint distractor
    assert not _near(_px(image, *_centre_of(task, other)), _TARGET, tol=60)
    assert _near(_px(image, *_centre_of(task, target)), _TARGET, tol=110)


# -- the sample -------------------------------------------------------------------------------------------


def test_the_sample_is_the_target_shape_alone_at_the_centre_with_find_this_under_it(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    image = _frame(task, canvas, 0, CENTRE)
    spec = task.scene_spec()
    assert _near(_px(image, _W / 2, _H / 2), _TARGET, tol=110)  # the shape, at the centre, in the target colour
    for slot in (0, 1):  # the field is not there (the lower slots are under the text on this small canvas)
        assert _near(_px(image, *_centre_of(task, slot)), _BG, tol=20)
    # The text strip (the Choice-making banner's light panel) sits just under the sample, centred.
    text_px = spec["sample_text_px"]
    below = _H / 2 + spec["icon_radius_px"] + text_px * 0.6 + text_px * 0.2
    assert _px(image, _W / 2 - text_px * 0.2, below).lightness() > 180  # the strip's panel, not the black field
    assert _near(_px(image, _W / 2, below + text_px * 3), _BG, tol=20)  # and nothing further down


def test_the_sample_is_drawn_at_the_icon_size(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    image = _frame(task, canvas, 0, CENTRE)
    r = task.scene_spec()["icon_radius_px"]
    assert r == pytest.approx(task.effective_radius_px(task.targets[0]) * ICON_DRAW_FRAC)
    # Every shape's top is at most r above its centre (a hexagon's is 0.87 r) and its middle is solid.
    assert _near(_px(image, _W / 2, _H / 2 - 0.3 * r), _TARGET, tol=110)
    assert _near(_px(image, _W / 2, _H / 2 - r - 6), _BG, tol=20)


# -- the field --------------------------------------------------------------------------------------------


def _field_image(task, canvas, pointer):
    run(task, CENTRE, 0, 1500)  # the sample (a run() frame does not render; this one does)
    return _frame(task, canvas, 1500, pointer)


def test_every_icon_is_bright_in_the_target_colour_so_only_the_shape_differs(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    image = _field_image(task, canvas, CENTRE)
    assert task.phase is Phase.WAIT_INPUT
    centres = [_px(image, *_centre_of(task, slot)) for slot in range(4)]
    assert all(_near(c, _TARGET, tol=110) for c in centres)
    # The same gradient everywhere: the target's centre pixel is the distractors' centre pixel.
    assert len({(c.red(), c.green(), c.blue()) for c in centres}) == 1


def test_no_outline_marks_the_target_until_the_pointer_is_on_it(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    image = _field_image(task, canvas, CENTRE)
    slot = task.targets[0].slot_index
    x, y = _centre_of(task, slot)
    r = task.scene_spec()["icon_radius_px"]
    shape = SHAPE_NAMES[task.trial_target_shapes[0]]
    # Straight above the icon, past its top, where an outline round it would be (the top of every shape is at r).
    top = y - r - SELECTABLE_OFFSET_PX
    if shape == "hexagon":
        top = y - 0.866 * r - SELECTABLE_OFFSET_PX
    assert _near(_px(image, x, top), _BG, tol=20)  # no white outline
    assert _near(_px(image, x, y - r - INSTANT_OFFSET_PX), _BG, tol=20)  # no on-target ring either


def test_the_outline_and_the_ring_appear_when_the_pointer_is_on_the_target(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    run(task, CENTRE, 0, 1500)
    slot = task.targets[0].slot_index
    image = _frame(task, canvas, 1500, at_slot(task, slot))  # the field's first frame, already on it
    x, y = _centre_of(task, slot)
    r = task.scene_spec()["icon_radius_px"]
    top = (0.866 * r) if SHAPE_NAMES[task.trial_target_shapes[0]] == "hexagon" else r
    assert _near(_px(image, x, y - top - SELECTABLE_OFFSET_PX), "#ffffff")
    assert _near(_px(image, x, y - top - INSTANT_OFFSET_PX), _RING)


def test_by_default_nothing_is_drawn_above_the_field(qapp):
    task, _spy, _fb = _task(mode="match_sample")
    canvas = _canvas()
    with_none = _field_image(task, canvas, CENTRE)
    on, _s, _f = _task(mode="match_sample", extra={"sample_reminder": True})
    spec_on = (_field_image(on, _canvas(), CENTRE), on.scene_spec())
    rx, ry = spec_on[1]["reminder"]["x_norm"] * _W, spec_on[1]["reminder"]["y_norm"] * _H
    assert _near(_px(spec_on[0], rx, ry), _TARGET, tol=110)
    assert not _near(_px(with_none, rx, ry), _TARGET, tol=110)


def test_the_reminder_is_the_sample_at_half_size_at_the_top_and_clear_of_every_icon(qapp):
    task, _spy, _fb = _task(mode="match_sample", extra={"sample_reminder": True})
    canvas = _canvas()
    image = _field_image(task, canvas, CENTRE)
    spec = task.scene_spec()
    rx, ry, radius = spec["reminder"]["x_norm"] * _W, spec["reminder"]["y_norm"] * _H, spec["reminder"]["radius_px"]
    assert radius == pytest.approx(spec["icon_radius_px"] / 2) and ry - radius >= 0
    assert _near(_px(image, rx, ry), _TARGET, tol=110)
    assert not _near(_px(image, rx, ry + radius + 4), _TARGET, tol=60)
    for slot in range(4):
        cx, cy = _centre_of(task, slot)
        assert ((rx - cx) ** 2 + (ry - cy) ** 2) ** 0.5 >= radius + spec["icon_radius_px"]


def test_pop_out_is_drawn_as_before_faint_distractors_and_an_outlined_target(qapp):
    task, _spy, _fb = _task(mode="pop_out")
    canvas = _canvas()
    image = _frame(task, canvas, 0, CENTRE)
    target = task.targets[0].slot_index
    x, y = _centre_of(task, target)
    r = task.effective_radius_px(task.targets[0]) * ICON_DRAW_FRAC
    shape = SHAPE_NAMES[task.icon_shapes[target]]
    top = (0.866 * r) if shape == "hexagon" else r
    assert _near(_px(image, x, y - top - SELECTABLE_OFFSET_PX), "#ffffff")  # the outline waits for no one
    assert not _near(_px(image, *_centre_of(task, (target + 1) % 4)), _TARGET, tol=60)


def test_before_the_first_trial_match_the_sample_draws_nothing(qapp):
    task, _spy, _fb = _task(mode="match_sample", preroll_ms=400.0)
    canvas = _canvas()
    image = _frame(task, canvas, 0, CENTRE)
    assert task.phase is Phase.READY
    for slot in range(4):
        assert _near(_px(image, *_centre_of(task, slot)), _BG, tol=20)
    assert _near(_px(image, _W / 2, _H / 2), _BG, tol=20)


# -- the spoken sample's sounds --------------------------------------------------------------------------------


def test_search_audio_loads_only_the_files_that_exist_and_is_silent_for_the_rest(qapp, tmp_path):
    write_wav(prompt_wav_path("en", "star", tmp_path), 300)
    write_wav(prompt_wav_path("en", "circle", tmp_path), 300)
    write_wav(prompt_wav_path("zh-TW", "square", tmp_path), 300)  # another language
    audio = SearchAudio("en", tmp_path)
    assert set(audio._prompts) == {"star", "circle"}
    effect = audio._prompts["star"]
    assert effect.volume() == pytest.approx(VOLUME) and VOLUME < 1.0
    assert effect.source().toLocalFile().replace("\\", "/") == str(
        prompt_wav_path("en", "star", tmp_path)
    ).replace("\\", "/")
    for shape in ("hexagon", "no-such-shape"):  # not there: quiet no-ops
        audio.on_prompt(shape)
    audio.on_prompt("star")
    audio.on_effect("star", False)
    audio.stop()


def test_search_audio_with_no_files_at_all_is_silent_and_reads_only(qapp, tmp_path):
    audio = SearchAudio("en", tmp_path / "missing")
    assert not audio._prompts
    audio.on_prompt("triangle")
    audio.stop()
    assert not (tmp_path / "missing").exists()


def test_only_a_match_the_sample_run_gets_the_spoken_sample(qapp):
    scanning = load_task_config("scanning")["task"]
    assert SearchAudio.from_task_config(scanning) is None  # Pop-out speaks nothing
    assert SearchAudio.from_task_config({**scanning, "search_mode": "match_sample"}) is not None
    assert SearchAudio.from_task_config({**scanning, "search_mode": "shout"}) is None
    for other in ("click_grid", "click_static", "follow_moving", "choice_making"):
        assert SearchAudio.from_task_config({**load_task_config(other)["task"], "search_mode": "match_sample"}) is None


def test_gui_feedback_forwards_the_sample_prompt_to_the_search_audio(qapp):
    class Spy:
        def __init__(self):
            self.calls = []

        def on_prompt(self, object_id):
            self.calls.append(("prompt", object_id))

        def stop(self):
            self.calls.append(("stop",))

    spy = Spy()
    feedback = GuiFeedback(TaskCanvas(theme=_THEME), _THEME, {}, scene_audio=spy)
    feedback.on_prompt("star")
    feedback.on_stop_audio()
    assert spy.calls == [("prompt", "star"), ("stop",)]
