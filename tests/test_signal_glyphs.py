"""SPEC-test-list-visual-identity.md, direction C "Signal": the six action glyphs of the Test List's
right-side buttons and the five task glyphs of its Task column, painted like the state glyphs
(1.5 px stroke at 12 px, token colours passed in, sharp at any pixel ratio). Each shape is sampled
from its painted pixmap, at the pixels where the 12 x 12 drawing is solid and where it is empty.
Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.ui import design_tokens as tokens
from src.ui.glyphs import (
    ACTION_GLYPHS,
    GLYPH_CIRCLE,
    GLYPH_COPY,
    GLYPH_DOCUMENT,
    GLYPH_FOLDER,
    GLYPH_PLAY,
    GLYPH_PLUS,
    GLYPH_SLIDERS,
    GLYPH_SQUARE,
    GLYPH_TASK_CHOICE,
    GLYPH_TASK_FOLLOW,
    GLYPH_TASK_GRID,
    GLYPH_TASK_SEARCH,
    GLYPH_TASK_STATIC,
    GLYPHS,
    ICON_DPRS,
    STATE_GLYPHS,
    TASK_GLYPHS,
    draw_glyph,
    glyph_icon,
    glyph_pixmap,
)

NEW_SHAPES = ACTION_GLYPHS + TASK_GLYPHS


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def alpha(pixmap, x: int, y: int) -> int:
    return pixmap.toImage().pixelColor(x, y).alpha()


def pixmap_of(shape: str, size: int = 12, dpr: float = 1.0):
    return glyph_pixmap(shape, "#000000", size, dpr)


def solid(pixmap, *points: tuple[int, int], at_least: int = 250) -> bool:
    return all(alpha(pixmap, x, y) >= at_least for x, y in points)


def empty(pixmap, *points: tuple[int, int], at_most: int = 8) -> bool:
    return all(alpha(pixmap, x, y) <= at_most for x, y in points)


# -- the set ----------------------------------------------------------------------------------------


def test_there_are_six_action_shapes_and_five_task_shapes_besides_the_seven_state_shapes():
    assert len(STATE_GLYPHS) == 7 and len(ACTION_GLYPHS) == 6 and len(TASK_GLYPHS) == 5
    assert GLYPHS == STATE_GLYPHS + ACTION_GLYPHS + TASK_GLYPHS
    assert len(set(GLYPHS)) == 18  # no two shapes share a name
    # Delete Test reuses the danger square, so 6 + 1 action glyphs and 5 task glyphs are the 12
    assert GLYPH_SQUARE in STATE_GLYPHS


@pytest.mark.parametrize("shape", NEW_SHAPES)
def test_a_new_shape_draws_inside_its_square_and_leaves_the_corners_empty(qapp, shape):
    pixmap = pixmap_of(shape)
    assert (pixmap.width(), pixmap.height()) == (12, 12)
    image = pixmap.toImage()
    assert sum(image.pixelColor(x, y).alpha() for x in range(12) for y in range(12)) > 300  # something is drawn
    assert empty(pixmap, (0, 0), (11, 0), (0, 11), (11, 11), at_most=20)


@pytest.mark.parametrize("shape", NEW_SHAPES)
def test_a_new_shape_is_drawn_in_the_colour_it_is_given(qapp, shape):
    colour = tokens.ACCENT
    image = glyph_pixmap(shape, colour, 12).toImage()
    opaque = [image.pixelColor(x, y) for x in range(12) for y in range(12) if image.pixelColor(x, y).alpha() == 255]
    assert opaque, shape
    assert {pixel.name().lower() for pixel in opaque} == {colour.lower()}


def test_an_unknown_shape_is_refused(qapp):
    image = QImage(12, 12, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        with pytest.raises(ValueError, match="Unknown glyph"):
            draw_glyph(painter, "sparkle", QRectF(0, 0, 12, 12), "#000000")
    finally:
        painter.end()


# -- the action shapes, sampled --------------------------------------------------------------------------


def test_the_plus_is_two_crossing_strokes(qapp):
    pixmap = pixmap_of(GLYPH_PLUS)
    assert solid(pixmap, (5, 5), (5, 2), (5, 9), (2, 5), (9, 5))  # the centre and the four arm ends
    assert max(alpha(pixmap, 6, y) for y in (2, 3, 4, 7, 8, 9)) < 200  # a 1.5 px stroke: the second pixel is half
    assert empty(pixmap, (2, 2), (9, 2), (2, 9), (9, 9), (3, 3), (8, 8))  # nothing on the diagonals
    assert empty(pixmap, (1, 5), (10, 5), (5, 1), (5, 10))  # the arms stop short of the edge


def test_the_sliders_are_three_tracks_with_a_knob_on_each_at_a_different_place(qapp):
    pixmap = pixmap_of(GLYPH_SLIDERS)
    assert solid(pixmap, (1, 2), (10, 2), (1, 6), (10, 6), (1, 9), (10, 9))  # the three tracks, edge to edge
    assert empty(pixmap, (1, 4), (10, 4), (1, 8), (0, 6), (11, 6))  # the room between them
    # a knob stands out of its track by about 2 px: above the top one, below the middle and the bottom one
    assert alpha(pixmap, 7, 1) > 200 and alpha(pixmap, 2, 1) == 0  # top knob, to the right
    assert alpha(pixmap, 3, 7) > 200 and alpha(pixmap, 9, 7) == 0  # middle knob, to the left
    assert alpha(pixmap, 6, 8) > 200 and alpha(pixmap, 1, 8) == 0  # bottom knob, in between


def test_the_play_glyph_is_a_triangle_pointing_right(qapp):
    pixmap = pixmap_of(GLYPH_PLAY)
    assert solid(pixmap, (4, 6), (6, 6), (8, 6), (4, 3), (4, 8))  # wide at the left, solid inside
    assert alpha(pixmap, 9, 6) > 200 and empty(pixmap, (11, 6))  # the tip reaches the right
    assert empty(pixmap, (8, 2), (8, 10), (10, 3), (10, 9), (0, 6))  # and the corners beside the tip are empty


def test_the_document_is_a_page_with_a_cut_corner_and_two_lines_of_text(qapp):
    pixmap = pixmap_of(GLYPH_DOCUMENT)
    assert solid(pixmap, (2, 4), (2, 8), (9, 6), (9, 9), (4, 1), (4, 10))  # the left, right, top and bottom edges
    assert empty(pixmap, (9, 1), (10, 1), (10, 3))  # the top right corner is cut off
    assert empty(pixmap, (4, 3), (6, 3), at_most=20)  # hollow above the text
    assert solid(pixmap, (5, 5), (6, 5))  # the first line of text
    assert alpha(pixmap, 5, 8) > 150 and alpha(pixmap, 6, 8) > 150  # the second, a row of half coverage under it
    assert alpha(pixmap, 5, 6) < 120  # a gap between the lines


def test_the_copy_glyph_is_two_squares_and_the_back_one_hides_behind_the_front(qapp):
    pixmap = pixmap_of(GLYPH_COPY)
    assert solid(pixmap, (1, 4), (4, 1), (7, 2))  # the back square: left and top edges, top right corner
    assert solid(pixmap, (5, 9), (10, 6), (10, 9), (4, 8))  # the front square: bottom, right and left edges
    assert empty(pixmap, (4, 3), (7, 6), (7, 7), (6, 7))  # hollow inside both; no back edge through the front
    assert alpha(pixmap, 2, 7) > 200  # the back square's bottom edge ends where the front one begins
    assert empty(pixmap, (9, 1), (1, 10), (0, 5))


def test_the_folder_is_an_outline_with_a_tab_on_the_left(qapp):
    pixmap = pixmap_of(GLYPH_FOLDER)
    assert solid(pixmap, (1, 6), (10, 6), (5, 10), (3, 2), (8, 4))  # left, right and bottom edges, the tab, the lid
    assert empty(pixmap, (8, 2), (10, 2), (5, 7), (6, 6))  # no tab on the right; hollow inside
    assert empty(pixmap, (0, 6), (11, 6), (5, 11))


# -- the task shapes, sampled ---------------------------------------------------------------------------------


def test_static_click_is_a_dot_in_a_ring(qapp):
    pixmap = pixmap_of(GLYPH_TASK_STATIC)
    assert solid(pixmap, (5, 5), (6, 6))  # the dot
    assert empty(pixmap, (3, 5), (8, 6), (5, 3), (6, 8))  # the gap between dot and ring
    assert alpha(pixmap, 1, 5) > 200 and alpha(pixmap, 10, 6) > 200  # the ring's left and right edges
    assert alpha(pixmap, 5, 1) > 200 and alpha(pixmap, 6, 10) > 200
    assert empty(pixmap, (1, 1), (10, 1), (1, 10), (10, 10))


def test_grid_click_is_a_three_by_three_block_of_two_pixel_squares(qapp):
    pixmap = pixmap_of(GLYPH_TASK_GRID)
    image = pixmap.toImage()
    for row in (1, 5, 9):
        for column in (1, 5, 9):
            assert solid(pixmap, (column, row), (column + 1, row), (column, row + 1), (column + 1, row + 1))
    assert empty(pixmap, (3, 3), (4, 1), (1, 3), (7, 7), (11, 11), (0, 0))  # two clear pixels between squares
    full = sum(1 for x in range(12) for y in range(12) if image.pixelColor(x, y).alpha() == 255)
    partial = sum(1 for x in range(12) for y in range(12) if 0 < image.pixelColor(x, y).alpha() < 255)
    assert (full, partial) == (36, 0)  # whole pixels only, so every edge is crisp


def test_follow_the_target_is_a_path_ending_in_an_arrow_head(qapp):
    pixmap = pixmap_of(GLYPH_TASK_FOLLOW)
    assert solid(pixmap, (9, 2), (6, 5), (2, 9))  # the head's corner, the shaft, the tail
    assert solid(pixmap, (5, 2), (9, 6))  # the head's two arms
    assert empty(pixmap, (2, 2), (9, 9), (0, 5), (5, 9))  # the other two corners are empty


def test_scanning_search_is_a_magnifier(qapp):
    pixmap = pixmap_of(GLYPH_TASK_SEARCH)
    assert solid(pixmap, (4, 1), (1, 4), (8, 4), (4, 8))  # the lens's top, left, right and bottom
    assert empty(pixmap, (4, 4), (5, 5), (3, 4))  # hollow lens
    assert solid(pixmap, (9, 9))  # the handle
    assert empty(pixmap, (10, 1), (1, 10), (11, 5))


def test_choice_making_is_a_filled_square_beside_an_outlined_one(qapp):
    pixmap = pixmap_of(GLYPH_TASK_CHOICE)
    assert solid(pixmap, (1, 4), (4, 4), (1, 7), (4, 7), (2, 5), (3, 6))  # the square that was picked: filled
    assert solid(pixmap, (7, 4), (10, 4), (7, 7), (10, 7), (8, 4), (9, 7), (7, 5), (10, 6))  # the other: its outline
    assert empty(pixmap, (8, 5), (9, 5), (8, 6), (9, 6))  # hollow inside
    assert alpha(pixmap, 5, 5) < 200 and alpha(pixmap, 6, 5) < 200  # a clear gap between the two
    assert empty(pixmap, (3, 2), (8, 2), (3, 9), (8, 9), (0, 0), (11, 11))  # centred vertically, nothing above or below


# -- sharp on a scaled display -----------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", NEW_SHAPES)
@pytest.mark.parametrize(("dpr", "physical"), [(1.25, 15), (1.5, 18), (2.0, 24)])
def test_a_new_shape_is_sharp_on_a_scaled_display(qapp, shape, dpr, physical):
    pixmap = pixmap_of(shape, dpr=dpr)
    assert pixmap.devicePixelRatio() == dpr
    assert (pixmap.width(), pixmap.height()) == (physical, physical)  # one painted pixel per device pixel
    assert max(alpha(pixmap, x, y) for x in range(physical) for y in range(physical)) == 255
    assert empty(pixmap, (0, 0), (physical - 1, 0), (0, physical - 1), at_most=40)


def test_a_larger_glyph_keeps_its_proportions(qapp):
    big = pixmap_of(GLYPH_TASK_GRID, size=24)
    assert solid(big, (2, 2), (3, 3), (10, 10), (18, 18)) and empty(big, (6, 6), (14, 14))  # 4 px squares, 4 px apart


# -- the slot and the icon ----------------------------------------------------------------------------------------


def test_a_slot_centres_the_glyph_in_a_larger_transparent_square(qapp):
    plain = glyph_pixmap(GLYPH_SQUARE, "#000000", 12)
    slotted = glyph_pixmap(GLYPH_SQUARE, "#000000", 12, slot=24)
    assert (plain.width(), slotted.width(), slotted.height()) == (12, 24, 24)
    # the 12 px square sits at 6..18: its own solid middle (2..10) lands on 8..16
    assert solid(slotted, (8, 12), (15, 12), (12, 8), (12, 15))
    assert empty(slotted, (7, 12), (16, 12), (12, 7), (12, 16), (0, 0), (23, 23))
    assert glyph_pixmap(GLYPH_CIRCLE, "#000000", 12, slot=0).width() == 12  # no slot, no change
    assert glyph_pixmap(GLYPH_CIRCLE, "#000000", 12, slot=8).width() == 12  # a slot never shrinks the glyph


def test_an_icon_is_one_colour_while_on_and_another_while_disabled_and_is_never_tinted(qapp):
    icon = glyph_icon(GLYPH_PLUS, tokens.ACCENT, tokens.TEXT_DISABLED)
    size = QSize(12, 12)

    def colour(mode: QIcon.Mode) -> str:
        return icon.pixmap(size, 1.0, mode).toImage().pixelColor(5, 5).name().lower()

    assert colour(QIcon.Mode.Normal) == tokens.ACCENT.lower()
    # the hovered / focused look, and the look in a selected row, are the same colour: Qt tints an
    # icon that has no pixmap for a mode, and a task glyph on a selected row must stay the accent
    assert colour(QIcon.Mode.Active) == colour(QIcon.Mode.Selected) == tokens.ACCENT.lower()
    assert colour(QIcon.Mode.Disabled) == tokens.TEXT_DISABLED.lower()


@pytest.mark.parametrize("dpr", ICON_DPRS)
def test_an_icon_holds_a_pixmap_for_every_pixel_ratio_so_it_is_sharp_on_a_scaled_display(qapp, dpr):
    icon = glyph_icon(GLYPH_PLUS, tokens.ACCENT, tokens.TEXT_DISABLED, 12, 24)
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Disabled):
        pixmap = icon.pixmap(QSize(24, 24), dpr, mode)
        assert pixmap.devicePixelRatio() == dpr
        assert pixmap.width() == round(24 * dpr)  # drawn at that size, not scaled up from 24 px
    # drawn at that size, not stretched: at 2.0 the plus's vertical arm starts at 16 px of the 48 px pixmap
    arm = icon.pixmap(QSize(24, 24), 2.0, QIcon.Mode.Normal).toImage()
    assert QColor(arm.pixelColor(24, 18)).alpha() == 255 and QColor(arm.pixelColor(24, 15)).alpha() == 0
