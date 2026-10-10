"""SPEC-design-system-phase2.md H1, H2, H12: the status badge. Every kind has its glyph shape
(sampled from the painted pixmap, not typed as a font character), its fill and text colours
from the tokens, and its word as the widget's ``accessibleName``. Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.ui import design_tokens as tokens
from src.ui.glyphs import (
    GLYPH_CIRCLE,
    GLYPH_DASHED,
    GLYPH_HALF,
    GLYPH_INFO,
    GLYPH_RING,
    GLYPH_SQUARE,
    GLYPH_TRIANGLE,
    glyph_pixmap,
)
from src.ui.status_badge import (
    BADGE_HEIGHT,
    BADGE_PADDING,
    GLYPH_PX,
    KINDS,
    LOOKS,
    StatusBadge,
)
from tests.colour_helpers import contrast

EXPECTED = {
    "done": (GLYPH_CIRCLE, tokens.SUCCESS_SUBTLE, tokens.SUCCESS_TEXT, "Done"),
    "connected": (GLYPH_CIRCLE, tokens.SUCCESS_SUBTLE, tokens.SUCCESS_TEXT, "Connected"),
    "calibrated": (GLYPH_CIRCLE, tokens.SUCCESS_SUBTLE, tokens.SUCCESS_TEXT, "Calibrated"),
    "tracking_ok": (GLYPH_CIRCLE, tokens.SUCCESS_SUBTLE, tokens.SUCCESS_TEXT, "Tracking OK"),
    "not_done": (GLYPH_RING, tokens.HEADER, tokens.TEXT_SECONDARY, "Not done"),
    "ended_early": (GLYPH_HALF, tokens.WARNING_SUBTLE, tokens.WARNING_TEXT, "Ended early"),
    "data_missing": (GLYPH_TRIANGLE, tokens.WARNING_SUBTLE, tokens.WARNING_TEXT, "Data missing"),
    "not_calibrated": (GLYPH_TRIANGLE, tokens.WARNING_SUBTLE, tokens.WARNING_TEXT, "Not calibrated"),
    "no_gaze": (GLYPH_TRIANGLE, tokens.WARNING_SUBTLE, tokens.WARNING_TEXT, "No gaze"),
    "disconnected": (GLYPH_SQUARE, tokens.DANGER_SUBTLE, tokens.DANGER_TEXT, "Disconnected"),
    "tracker_disconnected": (GLYPH_SQUARE, tokens.DANGER_SUBTLE, tokens.DANGER_TEXT, "Tracker disconnected"),
    "skipped": (GLYPH_DASHED, tokens.HEADER, tokens.TEXT_SECONDARY, "Skipped"),
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def alpha(pixmap, x: int, y: int) -> int:
    return pixmap.toImage().pixelColor(x, y).alpha()


def total_alpha(pixmap) -> int:
    image = pixmap.toImage()
    return sum(image.pixelColor(x, y).alpha() for x in range(image.width()) for y in range(image.height()))


def near(a: QColor, b: str, tolerance: int = 12) -> bool:
    c = QColor(b)
    return max(abs(a.red() - c.red()), abs(a.green() - c.green()), abs(a.blue() - c.blue())) <= tolerance


# -- the kinds -----------------------------------------------------------------------------


def test_the_twelve_kinds_of_h1_are_all_there():
    assert set(KINDS) == set(EXPECTED) and len(KINDS) == 12


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_each_kind_has_the_glyph_fill_and_text_colour_of_h2(kind):
    glyph, fill, text, word = EXPECTED[kind]
    look = LOOKS[kind]
    assert (look.glyph, look.fill, look.text, look.word) == (glyph, fill, text, word)


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_a_badge_says_its_word_to_a_screen_reader(qapp, kind):
    badge = StatusBadge(kind)
    assert badge.text() == badge.accessibleName() == EXPECTED[kind][3]
    assert badge.kind() == kind and badge.objectName() == "wtmhStatusBadge"


def test_set_state_changes_the_word_and_the_accessible_name_together(qapp):
    badge = StatusBadge("ended_early", "Ended early 4/6")
    assert badge.text() == badge.accessibleName() == "Ended early 4/6"
    badge.set_state("done")
    assert badge.text() == badge.accessibleName() == "Done" and badge.kind() == "done"


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_the_word_and_the_glyph_are_readable_on_the_pill(kind):
    look = LOOKS[kind]
    assert contrast(QColor(look.text), QColor(look.fill)) >= 4.5, kind  # text, and a glyph (3:1), at once


def test_an_unknown_kind_is_refused(qapp):
    with pytest.raises(ValueError):
        StatusBadge("almost_done")
    badge = StatusBadge("done")
    with pytest.raises(ValueError):
        badge.set_state("nope")
    assert badge.kind() == "done"


# -- the pill ------------------------------------------------------------------------------


def test_the_pill_is_24_px_high_and_grows_with_its_word(qapp):
    short, long = StatusBadge("done"), StatusBadge("tracker_disconnected")
    assert short.height() == long.height() == BADGE_HEIGHT == 24
    assert short.minimumHeight() == short.maximumHeight() == 24
    assert long.width() > short.width() > BADGE_PADDING * 2 + GLYPH_PX  # a fixed width of its own
    longer = StatusBadge("ended_early", "Ended early 4/6")
    assert longer.width() > StatusBadge("ended_early").width()


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_the_pill_is_filled_with_the_kinds_subtle_colour_and_round_ended(qapp, kind):
    badge = StatusBadge(kind)
    image = badge.grab().toImage()
    fill = EXPECTED[kind][1]
    assert near(image.pixelColor(image.width() // 2, 2), fill, 2)  # above the word, inside the pill
    # the corners are outside the full-radius pill, so they show the widget's backdrop
    assert not near(image.pixelColor(0, 0), fill, 2)
    assert not near(image.pixelColor(image.width() - 1, image.height() - 1), fill, 2)
    assert near(image.pixelColor(image.width() // 2, 0), fill, 2)  # the top edge is flat


@pytest.mark.parametrize("kind", ["done", "connected", "calibrated", "tracking_ok"])
def test_a_success_badge_paints_a_filled_circle_in_the_success_text_colour(qapp, kind):
    image = StatusBadge(kind).grab().toImage()
    centre = image.pixelColor(BADGE_PADDING + GLYPH_PX // 2, BADGE_HEIGHT // 2)
    assert near(centre, tokens.SUCCESS_TEXT, 2)


@pytest.mark.parametrize("kind", ["disconnected", "tracker_disconnected"])
def test_a_disconnected_badge_paints_a_filled_square_in_the_danger_text_colour(qapp, kind):
    image = StatusBadge(kind).grab().toImage()
    centre = image.pixelColor(BADGE_PADDING + GLYPH_PX // 2, BADGE_HEIGHT // 2)
    assert near(centre, tokens.DANGER_TEXT, 2)


# -- the glyph shapes, sampled -----------------------------------------------------------------


def test_the_filled_circle_is_solid_in_the_middle_and_empty_in_the_corners(qapp):
    pixmap = glyph_pixmap(GLYPH_CIRCLE, "#000000", GLYPH_PX)
    assert alpha(pixmap, 6, 6) == 255 and alpha(pixmap, 2, 6) == 255 and alpha(pixmap, 0, 0) == 0
    assert alpha(pixmap, 11, 0) == 0 and alpha(pixmap, 0, 11) == 0 and alpha(pixmap, 11, 11) == 0


def test_the_hollow_circle_has_a_ring_and_an_empty_middle(qapp):
    pixmap = glyph_pixmap(GLYPH_RING, "#000000", GLYPH_PX)
    assert alpha(pixmap, 6, 6) == 0 and alpha(pixmap, 4, 6) == 0 and alpha(pixmap, 8, 6) == 0
    assert max(alpha(pixmap, x, 5) for x in (1, 2)) > 100  # the ring's left edge
    assert max(alpha(pixmap, x, 5) for x in (9, 10)) > 100  # and its right edge
    assert alpha(pixmap, 0, 0) == 0


def test_the_half_circle_is_filled_on_the_left_only(qapp):
    pixmap = glyph_pixmap(GLYPH_HALF, "#000000", GLYPH_PX)
    assert alpha(pixmap, 4, 6) == 255 and alpha(pixmap, 3, 4) == 255 and alpha(pixmap, 3, 8) == 255
    assert max(alpha(pixmap, 7, y) for y in (4, 6, 8)) < 20  # (anti-aliasing leaves a few percent)
    assert max(alpha(pixmap, x, 5) for x in (9, 10)) > 100  # the right half is only outlined


def test_the_triangle_is_wide_at_the_bottom_and_empty_at_the_top_corners(qapp):
    pixmap = glyph_pixmap(GLYPH_TRIANGLE, "#000000", GLYPH_PX)
    assert alpha(pixmap, 6, 6) == 255 and alpha(pixmap, 6, 9) == 255
    assert alpha(pixmap, 2, 9) == 255 and alpha(pixmap, 9, 9) == 255  # the wide base
    assert alpha(pixmap, 1, 2) == 0 and alpha(pixmap, 10, 2) == 0 and alpha(pixmap, 2, 3) == 0


def test_the_square_is_solid_with_a_margin(qapp):
    pixmap = glyph_pixmap(GLYPH_SQUARE, "#000000", GLYPH_PX)
    assert alpha(pixmap, 6, 6) == 255 and alpha(pixmap, 3, 3) == 255 and alpha(pixmap, 8, 8) == 255
    assert alpha(pixmap, 0, 0) == 0 and alpha(pixmap, 0, 6) == 0 and alpha(pixmap, 11, 6) == 0


def test_the_dashed_ring_has_gaps_the_solid_ring_does_not(qapp):
    solid = glyph_pixmap(GLYPH_RING, "#000000", GLYPH_PX)
    dashed = glyph_pixmap(GLYPH_DASHED, "#000000", GLYPH_PX)
    assert alpha(dashed, 6, 6) == 0  # hollow
    assert 0 < total_alpha(dashed) < total_alpha(solid) * 0.8
    # the ring is broken: a pixel the solid ring covers well is nearly empty in the dashed one
    image_solid, image_dashed = solid.toImage(), dashed.toImage()
    ring = [(x, y) for x in range(12) for y in range(12) if image_solid.pixelColor(x, y).alpha() > 200]
    assert ring and any(image_dashed.pixelColor(x, y).alpha() < 40 for x, y in ring)


def test_the_info_glyph_is_a_ring_with_a_dot_and_a_stem(qapp):
    pixmap = glyph_pixmap(GLYPH_INFO, "#000000", 20)
    assert alpha(pixmap, 10, 2) > 200  # the ring's top
    assert alpha(pixmap, 10, 6) > 200  # the dot
    assert alpha(pixmap, 10, 8) < 100  # the gap between the dot and the stem
    assert alpha(pixmap, 10, 11) > 200  # the stem
    assert alpha(pixmap, 6, 10) == 0  # empty beside the stem


def test_a_glyph_is_sharp_on_a_scaled_display(qapp):
    pixmap = glyph_pixmap(GLYPH_CIRCLE, "#000000", GLYPH_PX, dpr=2.0)
    assert pixmap.width() == 24 and pixmap.devicePixelRatio() == 2.0
    assert alpha(pixmap, 12, 12) == 255
