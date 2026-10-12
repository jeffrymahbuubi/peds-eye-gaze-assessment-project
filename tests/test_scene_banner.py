"""SPEC-scene-cause-effect-task.md 3.7, P2 (the banner is drawn across the top of the scene, only
while ``scene["prompt_text"]`` is set) and P6 (the lettering is about 1.5 degrees tall, on one line,
shrunk to fit only when a sentence would overflow). Offscreen Qt.

Offscreen Qt has no font database, so what depends on real glyph widths and heights registers the
Windows Segoe UI for the module (``tests/real_fonts.py``) and is skipped where it is missing; the
panel itself (colours, geometry) needs no font."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFontMetricsF, QImage
from PySide6.QtWidgets import QApplication

from src.engine.prompt_text import prompt_text_px_for
from src.engine.target_size import DEFAULT_VIEWING_DISTANCE_MM, REFERENCE_MM_PER_PX
from src.tasks.choice_layout import scene_rect
from src.tasks.choice_scene import load_manifest
from src.tasks.choice_scene_defaults import default_manifest
from src.ui.design_tokens import PANEL
from src.ui.scene_banner import (
    HEIGHT_FRAC,
    MARGIN_FRAC,
    MIN_TEXT_PX,
    PAD_X_FRAC,
    banner_font,
    banner_rect,
    fit_text_px,
)
from tests import real_fonts
from tests.test_choice_scene_canvas import make_canvas, scene_for, show

TEXT_PX = prompt_text_px_for(REFERENCE_MM_PER_PX, DEFAULT_VIEWING_DISTANCE_MM)  # 61.5 at 1920 x 1080


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def fonts(qapp):
    yield from real_fonts.segoe_ui(qapp)


def sentences(manifest) -> list[str]:
    return [obj.prompt for obj in manifest.objects]


def width_of(text: str):
    return lambda px: QFontMetricsF(banner_font(px)).horizontalAdvance(text)


# -- the strip -----------------------------------------------------------------------------------------------


def test_the_strip_lies_across_the_top_of_the_scene_inside_it():
    scene = QRectF(274.0, 0.0, 1371.0, 1032.0)
    strip = banner_rect(scene, 60.0)
    assert strip.top() == pytest.approx(60.0 * MARGIN_FRAC) and strip.height() == pytest.approx(60.0 * HEIGHT_FRAC)
    assert strip.left() == pytest.approx(scene.left() + 60.0 * MARGIN_FRAC)
    assert strip.right() == pytest.approx(scene.right() - 60.0 * MARGIN_FRAC)  # across the whole width
    assert scene.contains(strip)
    assert strip.height() < scene.height() * 0.15  # a caption, not a cover over the scene


def test_the_strip_grows_with_the_lettering():
    scene = QRectF(0.0, 0.0, 1000.0, 800.0)
    assert banner_rect(scene, 30.0).height() == pytest.approx(banner_rect(scene, 60.0).height() / 2)


# -- P6: shrink to fit only on overflow --------------------------------------------------------------------------


def test_a_sentence_that_fits_keeps_the_full_size():
    assert fit_text_px(61.49, 1000.0, lambda px: px * 12.0) == 61  # 732 px wide
    assert fit_text_px(61.49, 61 * 12.0, lambda px: px * 12.0) == 61  # exactly full


def test_a_sentence_that_would_overflow_shrinks_just_enough():
    px = fit_text_px(61.49, 500.0, lambda px: px * 12.0)  # 12 px per px of size: 41 fits
    assert px == 41 and px * 12.0 <= 500.0 < (px + 1) * 12.0
    assert fit_text_px(61.49, 100.0, lambda px: px * 12.0) == MIN_TEXT_PX  # never below the floor
    assert fit_text_px(61.49, 0.0, lambda px: px * 12.0) == 61  # no room to measure: unchanged


def test_the_fit_follows_a_width_that_is_not_proportional():
    def wobbly(px: int) -> float:  # hinting makes a width jump
        return px * 12.0 + (7.0 if px % 2 else 0.0)

    px = fit_text_px(61.49, 500.0, wobbly)
    assert wobbly(px) <= 500.0


@pytest.mark.real_scene  # the sentences of the shipped scene.yaml, as well as the built-in ones
def test_every_park_prompt_is_one_line_at_full_size_on_the_standard_display(qapp, fonts):
    """1920 x 1080 at 100 %: a 1371 px wide scene and 1.5 degrees (61 px) of lettering."""
    x, _y, w, h = scene_rect(1920, 1032)
    strip = banner_rect(QRectF(x, 0.0, w, h), TEXT_PX)
    room = strip.width() - 2 * TEXT_PX * PAD_X_FRAC
    for manifest in (default_manifest(), load_manifest("park")):
        for text in sentences(manifest):
            assert text and fit_text_px(TEXT_PX, room, width_of(text)) == round(TEXT_PX), text
            assert width_of(text)(round(TEXT_PX)) < room * 0.9  # with room to spare, not a near miss


def test_every_park_prompt_fits_at_full_size_on_a_smaller_display_too(qapp, fonts):
    """A 1366 x 768 laptop: the scene is narrower but the same angle is fewer px."""
    mm = 531.4 / 1366
    text_px = prompt_text_px_for(mm, DEFAULT_VIEWING_DISTANCE_MM)
    x, _y, w, h = scene_rect(1366, 720)
    strip = banner_rect(QRectF(x, 0.0, w, h), text_px)
    room = strip.width() - 2 * text_px * PAD_X_FRAC
    for text in sentences(default_manifest()):
        assert fit_text_px(text_px, room, width_of(text)) == round(text_px), text


def test_a_longer_sentence_shrinks_to_fit_instead_of_wrapping(qapp, fonts):
    text = "Make the seesaw go up and down and the bubbles fly and the rainbow shine!"
    x, _y, w, h = scene_rect(1920, 1032)
    strip = banner_rect(QRectF(x, 0.0, w, h), TEXT_PX)
    room = strip.width() - 2 * TEXT_PX * PAD_X_FRAC
    px = fit_text_px(TEXT_PX, room, width_of(text))
    assert MIN_TEXT_PX < px < round(TEXT_PX) and width_of(text)(px) <= room


# -- the drawing ------------------------------------------------------------------------------------------------


def differing(a: QImage, b: QImage) -> list[tuple[int, int]]:
    return [(x, y) for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y)]


def test_the_banner_is_drawn_in_the_strip_over_the_scene_and_nowhere_else(qapp):
    canvas = make_canvas()
    spec = scene_for(prompt_text=None, prompt_text_px=40.0)
    plain = show(canvas, spec)
    spec["prompt_text"] = "Make the bubbles fly!"
    banner = show(canvas, spec)
    strip = banner_rect(QRectF(*spec["scene_rect"]), 40.0)
    changed = differing(plain, banner)
    assert changed  # something was drawn ...
    area = strip.adjusted(-2, -2, 2, 2)
    assert all(area.contains(x + 0.5, y + 0.5) for x, y in changed)  # ... only in the strip
    scene = QRectF(*spec["scene_rect"])
    assert scene.contains(strip)  # and so inside the scene: the buttons are untouched
    # The panel is the design system's light panel; without text there is none.
    probe = (int(strip.left()) + 8, int(strip.center().y()))
    assert banner.pixelColor(*probe) == QColor(PANEL)
    assert plain.pixelColor(*probe) != QColor(PANEL)


def test_no_text_no_banner_whatever_the_size(qapp):
    canvas = make_canvas()
    spec = scene_for(prompt_text=None, prompt_text_px=61.5)
    plain = show(canvas, spec)
    assert show(canvas, dict(spec, prompt_text="")) == plain
    assert show(canvas, dict(spec, prompt_text=None, prompt_text_px=10.0)) == plain


def test_without_a_size_the_banner_uses_the_reference_monitors(qapp):
    canvas = make_canvas()
    spec = scene_for(prompt_text="Make the bubbles fly!", prompt_text_px=0.0)
    with_zero = show(canvas, spec)
    reference = show(canvas, dict(spec, prompt_text_px=TEXT_PX))
    assert with_zero == reference


def test_the_banner_is_hidden_during_an_effect_and_in_a_pause(qapp):
    canvas = make_canvas()
    spec = scene_for(prompt_text=None)  # the task says None from the hit on
    effect = {"object": "balloons", "t_start": 0, "duration_ms": 3500, "modelled": False, "elapsed_ms": 800.0}
    spec["effect"] = effect
    image = show(canvas, spec)
    strip = banner_rect(QRectF(*spec["scene_rect"]), spec["prompt_text_px"])
    probe = (int(strip.left()) + 8, int(strip.center().y()))
    assert image.pixelColor(*probe) != QColor(PANEL)


def ink_rows(image: QImage, region: QRectF) -> list[int]:
    """The pixel rows of ``region`` holding dark (text) pixels."""
    rows = []
    for y in range(int(region.top()), int(region.bottom())):
        if any(
            (c := image.pixelColor(x, y)).red() < 70 and c.green() < 70 and c.blue() < 70
            for x in range(int(region.left()), int(region.right()), 2)
        ):
            rows.append(y)
    return rows


@pytest.mark.parametrize("text_px", [30.0, 61.5])
def test_the_lettering_is_as_tall_as_it_is_told_and_on_one_line(qapp, fonts, text_px):
    canvas = make_canvas(1920, 1032)
    spec = scene_for(1920, 1032, prompt_text="Make the bubbles fly!", prompt_text_px=text_px)
    image = show(canvas, spec)
    strip = banner_rect(QRectF(*spec["scene_rect"]), text_px)
    rows = ink_rows(image, strip.adjusted(4, 4, -4, -4))
    assert rows and rows == list(range(rows[0], rows[-1] + 1))  # one connected block of lines: one line
    ink = rows[-1] - rows[0] + 1  # the tall M to the descender of the y
    assert 0.75 * text_px <= ink <= 1.05 * text_px
    assert strip.top() < rows[0] and rows[-1] < strip.bottom()  # inside the strip


def test_the_banner_text_is_dark_on_the_light_panel(qapp, fonts):
    canvas = make_canvas(1920, 1032)
    spec = scene_for(1920, 1032, prompt_text="Make the bubbles fly!", prompt_text_px=TEXT_PX)
    image = show(canvas, spec)
    strip = banner_rect(QRectF(*spec["scene_rect"]), TEXT_PX)
    assert image.pixelColor(int(strip.left()) + 8, int(strip.center().y())) == QColor(PANEL)
    assert ink_rows(image, strip.adjusted(4, 4, -4, -4))  # dark pixels on it
