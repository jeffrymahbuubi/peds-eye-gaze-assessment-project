"""The report's Target Map (SPEC-compass-task-flow.md 4D.7; AD8, AD9): marks sit at the
targets' canvas-normalized positions at the canvas's own aspect, the overlays switch
independently, a trial can be shown alone, and the PDF's image is the same drawing.
Offscreen Qt; pixels are checked by colour class, never by size (no fonts offscreen)."""

from __future__ import annotations

import copy
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.ui.target_map import TargetMapWidget
from src.ui.target_map_paint import (
    BADGE_PAD,
    DEFAULT_ASPECT,
    HEAT_FLOOR,
    TRIAL_PATH_DARK,
    TRIAL_PATH_LIGHT,
    _label,
    badge_pill,
    build_model,
    canvas_logical_width,
    digits_height,
    fit_font,
    heat_colour,
    heat_image,
)
from tests.colour_helpers import contrast, luminance
from tests.report_ui_fixtures import folder_report, synthetic_map_report

ASPECT = round(1640 / 957, 5)
WHITE = QColor("#FFFFFF")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def render(report, size=(1000, 584), *, trial=None, **overlays) -> tuple[QImage, QRectF]:
    widget = TargetMapWidget()
    widget.set_report(report)
    if trial is not None:
        widget.set_trial(trial)
    image = widget.render_to_image(QSize(*size), overlays or None)
    return image, widget.canvas_rect(QRectF(image.rect()))


def at(image: QImage, rect: QRectF, x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> QColor:
    """The pixel at canvas-normalized (x, y), nudged by (dx, dy) px."""
    return image.pixelColor(
        round(rect.left() + x * rect.width() + dx), round(rect.top() + y * rect.height() + dy)
    )


def is_white(colour: QColor) -> bool:
    return colour.red() > 245 and colour.green() > 245 and colour.blue() > 245


def greenish(colour: QColor) -> bool:
    return colour.green() > colour.red() + 30 and colour.green() > colour.blue() + 10


def reddish(colour: QColor) -> bool:
    return colour.red() > colour.green() + 60 and colour.red() > colour.blue() + 60


def ink_in(image: QImage, rect: QRectF, x: float, y: float, half: int = 6) -> bool:
    """Is anything but white within ``half`` px of canvas-normalized (x, y)?"""
    cx, cy = round(rect.left() + x * rect.width()), round(rect.top() + y * rect.height())
    return any(
        not is_white(image.pixelColor(px, py))
        for px in range(cx - half, cx + half + 1)
        for py in range(cy - half, cy + half + 1)
    )


# -- the model -----------------------------------------------------------------------------


def test_the_model_reads_aspect_marks_slots_and_trials():
    model = build_model(synthetic_map_report())
    assert model.aspect == pytest.approx(ASPECT)
    assert [m["outcome"] for m in model.marks] == ["hit", "timeout"]
    assert model.slots == [(0.65, 0.5), (0.3, 0.7)]
    assert len(model.trials) == 2 and model.slot_radius == pytest.approx(0.05)
    assert model.moving is False and model.heat_empty is False


def test_an_empty_or_missing_report_gives_an_empty_map_at_sixteen_by_nine(qapp):
    assert build_model(None).aspect == DEFAULT_ASPECT
    assert build_model({}).marks == [] and build_model({}).trials == []
    widget = TargetMapWidget()
    widget.set_report(None)
    image = widget.render_to_image(QSize(400, 250))
    assert image.size() == QSize(400, 250)


def test_the_aspect_falls_back_to_the_geometry_block_then_to_16_by_9():
    report = synthetic_map_report()
    report["map"]["aspect"] = None
    assert build_model(report).aspect == pytest.approx(ASPECT)
    report["geometry"]["canvas_aspect"] = None
    assert build_model(report).aspect == DEFAULT_ASPECT


def test_the_aspect_of_a_real_report_is_the_canvas_aspect(tmp_path):
    assert build_model(folder_report(tmp_path)).aspect == pytest.approx(1640 / 957, abs=1e-4)


@pytest.mark.parametrize(
    ("geometry", "expected"),
    [
        ({"canvas_px": [1640, 957], "canvas_units": "physical", "display_scale_percent": 100}, 1640.0),
        ({"canvas_px": [1640, 957], "canvas_units": "physical", "display_scale_percent": 150}, 1640 / 1.5),
        ({"canvas_px": [1093, 638], "canvas_units": "logical", "display_scale_percent": 150}, 1093.0),
        ({"canvas_px": [1093, 638], "display_scale_percent": 150}, 1093.0),
        ({"canvas_px": [None, None]}, None),
        ({}, None),
    ],
)
def test_the_logical_canvas_width(geometry, expected):
    assert canvas_logical_width(geometry) == (pytest.approx(expected) if expected else None)


def test_the_hitbox_margin_follows_the_report_and_is_unknown_without_a_canvas():
    report = synthetic_map_report()
    assert build_model(report).tolerance_norm == pytest.approx(40 / 1640)
    report["map"]["hit_tolerance_px"] = 60
    assert build_model(report).tolerance_norm == pytest.approx(60 / 1640)
    report["geometry"] = {}
    assert build_model(report).tolerance_norm is None  # no guess without a canvas size


# -- the widget's geometry --------------------------------------------------------------------


@pytest.mark.parametrize("size", [(800, 470), (500, 500), (300, 900), (1200, 200)])
def test_the_canvas_rectangle_keeps_the_canvas_aspect_and_is_centred(qapp, size):
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    widget.resize(*size)
    rect = widget.canvas_rect()
    assert rect.width() / rect.height() == pytest.approx(ASPECT, rel=1e-3)  # AD8
    assert rect.center().x() == pytest.approx(size[0] / 2)
    assert rect.center().y() == pytest.approx(size[1] / 2)
    assert rect.width() <= size[0] and rect.height() <= size[1]


def test_fit_to_width_makes_the_height_follow_the_width(qapp):
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    assert not widget.hasHeightForWidth()
    widget.set_fit_to_width(True)
    assert widget.hasHeightForWidth()
    assert widget.heightForWidth(804) == round(800 / ASPECT) + 4
    widget.setMaximumWidth(404)  # a layout asks with the width it has, not the one it will give
    assert widget.heightForWidth(2000) == round(400 / ASPECT) + 4
    widget.set_fit_to_width(False)
    assert not widget.hasHeightForWidth()


# -- marks (AD8) --------------------------------------------------------------------------------


def test_a_hit_is_a_green_circle_at_the_targets_position_with_its_real_radius(qapp):
    image, rect = render(synthetic_map_report())
    r_px = 0.05 * rect.width()
    assert greenish(at(image, rect, 0.65, 0.5, 0.6 * r_px, 0))  # inside, off the label
    assert greenish(at(image, rect, 0.65, 0.5, 0, -0.6 * r_px))
    assert is_white(at(image, rect, 0.65, 0.5, 1.5 * r_px, 0))  # outside the radius
    assert is_white(at(image, rect, 0.5, 0.25))  # nowhere near a target


def test_a_not_selected_trial_is_a_red_x_not_a_filled_circle(qapp):
    image, rect = render(synthetic_map_report())
    r_px = 0.05 * rect.width()
    d = 0.5 * r_px  # on the X's diagonal
    assert reddish(at(image, rect, 0.3, 0.7, d, d))
    assert reddish(at(image, rect, 0.3, 0.7, -d, d))
    assert is_white(at(image, rect, 0.3, 0.7, 0.6 * r_px, 0))  # between the arms: not filled


def test_a_skipped_trial_is_a_grey_dashed_ring(qapp):
    report = synthetic_map_report()
    report["map"]["marks"][1]["outcome"] = "skipped"
    image, rect = render(report)
    r_px = 0.05 * rect.width()
    on_ring = [at(image, rect, 0.3, 0.7, r_px, 0), at(image, rect, 0.3, 0.7, -r_px, 0),
               at(image, rect, 0.3, 0.7, 0, r_px), at(image, rect, 0.3, 0.7, 0, -r_px)]
    assert any(not is_white(c) for c in on_ring)
    assert not any(reddish(c) or greenish(c) for c in on_ring)
    assert is_white(at(image, rect, 0.3, 0.7, 0.5 * r_px, 0.5 * r_px))  # hollow


def test_the_targets_overlay_off_draws_no_marks_and_no_layout(qapp):
    image, rect = render(synthetic_map_report(), targets=False)
    assert is_white(at(image, rect, 0.65, 0.5, 20, 0))
    assert not ink_in(image, rect, 0.65, 0.5, half=2 * round(0.05 * rect.width()))
    assert not ink_in(image, rect, 0.3, 0.7, half=2 * round(0.05 * rect.width()))


def test_the_layout_slots_are_faint_rings_that_show_empty_places(qapp):
    report = synthetic_map_report()
    report["map"]["slots"].append([0.8, 0.2])  # an empty place: no mark
    image, rect = render(report)
    r_px = 0.05 * rect.width()
    ring = [at(image, rect, 0.8, 0.2, r_px, 0), at(image, rect, 0.8, 0.2, 0, r_px),
            at(image, rect, 0.8, 0.2, -r_px, 0), at(image, rect, 0.8, 0.2, 0, -r_px)]
    assert any(not is_white(c) for c in ring)
    assert is_white(at(image, rect, 0.8, 0.2))  # hollow, and faint
    report["map"]["slots"] = None
    plain, _ = render(report)
    assert is_white(at(plain, rect, 0.8, 0.2, r_px, 0))


def test_a_mark_without_a_radius_still_shows(qapp):
    report = synthetic_map_report()
    for mark in report["map"]["marks"]:
        mark["r"] = 0
    image, rect = render(report)
    assert greenish(at(image, rect, 0.65, 0.5, 0.01 * rect.width(), 0.01 * rect.width()))


def test_a_shared_place_draws_each_outcome_once_with_the_report_label(qapp):
    report = synthetic_map_report()
    report["map"]["marks"] = [
        {"x": 0.45, "y": 0.5, "r": 0.05, "outcome": "hit", "trials": [3], "label": "3"},
        {"x": 0.55, "y": 0.5, "r": 0.05, "outcome": "timeout", "trials": [9], "label": "9"},
    ]
    image, rect = render(report)
    r_px = 0.05 * rect.width()
    assert greenish(at(image, rect, 0.45, 0.5, 0, 0.6 * r_px))
    assert reddish(at(image, rect, 0.55, 0.5, 0.5 * r_px, 0.5 * r_px))


# -- scanpath and heat map overlays ------------------------------------------------------------------


def test_the_scanpath_overlay_is_off_by_default_and_draws_each_trial_in_its_colour(qapp):
    report = synthetic_map_report()
    report["trials"][0]["scanpath"] = [[0.1, 0.1], [0.5, 0.1], [0.9, 0.1]]
    report["trials"][1]["scanpath"] = [[0.1, 0.9], [0.5, 0.9], [0.9, 0.9]]
    off, rect = render(report)
    assert is_white(at(off, rect, 0.3, 0.1)) and is_white(at(off, rect, 0.3, 0.9))
    on, rect = render(report, targets=False, path=True)
    first, second = at(on, rect, 0.3, 0.1), at(on, rect, 0.3, 0.9)  # on the line between two dots
    assert not is_white(first) and not is_white(second)
    assert first.blue() > first.red()  # trial 1: the cycle's blue
    assert first.rgb() != second.rgb()  # trial 2 has another colour


def test_the_scanpath_is_a_dot_per_fixation_joined_by_straight_lines_in_time_order(qapp):
    """V2: dots at the centroids, straight lines between consecutive ones, nothing else."""
    report = synthetic_map_report()
    report["trials"][0]["scanpath"] = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]]  # right, then down
    report["trials"][1]["scanpath"] = []
    image, rect = render(report, targets=False, path=True)
    for x, y in ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8)):
        assert not is_white(at(image, rect, x, y))  # a dot at every fixation
    assert not is_white(at(image, rect, 0.5, 0.2))  # the line of the first leg
    assert not is_white(at(image, rect, 0.8, 0.5))  # the line of the second leg
    assert is_white(at(image, rect, 0.2, 0.5))  # no line from the last fixation back to the first
    assert is_white(at(image, rect, 0.5, 0.5))  # and none as a diagonal shortcut


def test_the_scanpath_does_not_draw_the_raw_or_smoothed_gaze_path(qapp):
    """The Summary map is the fixation scanpath only: the full path is the Detailed view's."""
    report = synthetic_map_report()
    report["trials"][0]["path"] = [[[0.1, 0.5], [0.9, 0.5]]]
    report["trials"][0]["scanpath"] = []
    image, rect = render(report, targets=False, path=True)
    assert is_white(at(image, rect, 0.5, 0.5))


def test_a_scanpath_of_one_fixation_is_one_dot_and_a_missing_one_draws_nothing(qapp):
    report = synthetic_map_report()
    report["trials"][0]["scanpath"] = [[0.4, 0.4]]
    image, rect = render(report, targets=False, path=True)
    assert not is_white(at(image, rect, 0.4, 0.4)) and is_white(at(image, rect, 0.6, 0.4))
    stripped = synthetic_map_report()  # a report from before the scanpath existed
    image, rect = render(stripped, targets=False, path=True)
    assert is_white(at(image, rect, 0.5, 0.5))


def test_a_scanpath_leaving_the_canvas_is_clipped_to_it(qapp):
    report = synthetic_map_report()
    report["trials"][0]["scanpath"] = [[-0.5, 0.5], [1.5, 0.5]]
    image, rect = render(report, size=(1200, 584), targets=False, path=True)  # room around the canvas
    assert not is_white(at(image, rect, 0.5, 0.5))
    assert is_white(at(image, rect, 1.0, 0.5, 8, 0))  # outside the canvas stays white
    assert is_white(at(image, rect, 0.0, 0.5, -8, 0))


def test_the_heat_map_is_an_alpha_ramp_over_the_canvas_and_off_by_default(qapp):
    report = synthetic_map_report()
    report["heat"] = {"w": 4, "h": 2, "empty": False, "data": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0]}
    off, rect = render(report)
    assert is_white(at(off, rect, 0.375, 0.75))
    on, rect = render(report, targets=False, heat=True)
    hot, warm, cold = at(on, rect, 0.375, 0.75), at(on, rect, 0.625, 0.75), at(on, rect, 0.125, 0.25)
    assert reddish(hot) and not is_white(warm)
    assert is_white(cold)  # below the floor: transparent
    assert hot.red() > hot.blue() and warm.red() < hot.red()


def test_an_empty_heat_map_draws_nothing_but_says_so(qapp):
    report = synthetic_map_report()
    report["heat"] = {"w": 96, "h": 54, "empty": True, "data": []}
    assert heat_image(report["heat"]) is None
    on, rect = render(report, targets=False, heat=True)
    assert is_white(at(on, rect, 0.02, 0.02))
    assert ink_in(on, rect, 0.5, 0.5, half=40)  # the note: "No gaze on the canvas ..."


def test_heat_colours_run_cool_to_hot_and_stay_transparent_below_the_floor():
    assert heat_colour(HEAT_FLOOR / 2).alpha() == 0
    cool, hot = heat_colour(0.1), heat_colour(1.0)
    assert cool.blue() > cool.red() and hot.red() > hot.blue()
    assert hot.alpha() > cool.alpha() > 0


def test_heat_data_that_does_not_match_its_size_is_ignored():
    assert heat_image({"w": 4, "h": 2, "empty": False, "data": [0.5] * 7}) is None
    assert heat_image({"w": 4, "h": 2, "empty": False, "data": []}) is None
    assert heat_image({}) is None


# -- follow & click (AD9) ----------------------------------------------------------------------------


def moving_report():
    report = synthetic_map_report()
    report["session"]["task_id"] = "follow_moving"
    # the report's marks sit at the END position; the start is on the left
    report["trials"][0]["target"].update({"x": 0.2, "y": 0.5, "end_x": 0.8, "end_y": 0.5})
    report["trials"][0]["track"] = [[0.2, 0.5], [0.5, 0.5], [0.8, 0.5]]
    report["trials"][1]["track"] = []
    report["map"]["marks"] = [
        {"x": 0.8, "y": 0.5, "r": 0.05, "outcome": "hit", "trials": [1], "label": "1"},
    ]
    report["map"]["slots"] = None
    return report


def test_a_follow_moving_map_shows_the_target_track_and_the_mark_at_its_end(qapp):
    image, rect = render(moving_report())
    r_px = 0.05 * rect.width()
    assert greenish(at(image, rect, 0.8, 0.5, 0, 0.6 * r_px))  # the mark at end_x / end_y
    assert is_white(at(image, rect, 0.2, 0.5, 0, 0.6 * r_px))  # not at the start
    assert not is_white(at(image, rect, 0.5, 0.5))  # the faint track in between
    assert build_model(moving_report()).moving is True


def test_a_static_task_draws_no_track_even_if_a_trial_carries_one(qapp):
    report = moving_report()
    report["session"]["task_id"] = "click_grid"
    image, rect = render(report)
    assert is_white(at(image, rect, 0.5, 0.5))


def test_the_trial_view_of_a_moving_target_draws_its_track_and_rings_the_end(qapp):
    image, rect = render(moving_report(), trial=0)
    r_px = 0.05 * rect.width()
    assert not is_white(at(image, rect, 0.5, 0.5))  # the track
    assert any(
        not is_white(c) for c in (at(image, rect, 0.8, 0.5, r_px, 0), at(image, rect, 0.8, 0.5, 0, r_px))
    )
    assert is_white(at(image, rect, 0.2, 0.5, 0, r_px))  # no ring at the start


# -- one trial ---------------------------------------------------------------------------------------


def test_set_trial_shows_one_trial_and_none_goes_back_to_the_whole_test(qapp):
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    assert widget.trial() is None
    widget.set_trial(1)
    assert widget.trial() == 1
    widget.set_trial(7)  # not there: the whole test
    assert widget.trial() is None
    widget.set_trial(-1)
    assert widget.trial() is None
    widget.set_trial(0)
    widget.set_report(synthetic_map_report())  # a new report starts on the whole test
    assert widget.trial() is None


def test_the_trial_view_draws_only_that_trials_target_and_a_dashed_hitbox_ring(qapp):
    image, rect = render(synthetic_map_report(), trial=0)
    r_px = 0.05 * rect.width()
    assert not is_white(at(image, rect, 0.65, 0.5, 0, 0.6 * r_px))  # the hit target's light fill
    assert is_white(at(image, rect, 0.3, 0.7, 0.5 * r_px, 0.5 * r_px))  # the other trial's target: absent
    margin = 0.05 + 40 / 1640
    ring = [at(image, rect, 0.65, 0.5, margin * rect.width(), 0), at(image, rect, 0.65, 0.5, 0, margin * rect.width()),
            at(image, rect, 0.65, 0.5, -margin * rect.width(), 0), at(image, rect, 0.65, 0.5, 0, -margin * rect.width())]
    assert any(not is_white(c) for c in ring)  # the hitbox: drawn target + the 40 px margin


def test_no_hitbox_ring_when_the_canvas_size_is_unknown(qapp):
    report = synthetic_map_report()
    report["geometry"] = {}
    image, rect = render(report, trial=0)
    margin = (0.05 + 40 / 1640) * rect.width()
    ring = [at(image, rect, 0.65, 0.5, margin, 0), at(image, rect, 0.65, 0.5, -margin, 0)]
    assert all(is_white(c) for c in ring)


def test_the_selection_star_is_drawn_for_a_hit_only(qapp):
    report = synthetic_map_report()
    image, rect = render(report, trial=0)
    star = at(image, rect, 0.64, 0.49)  # the path's last point
    assert star.red() > 200 and star.green() > 150 and star.blue() < 120  # gold
    report["trials"][0]["outcome"] = "timeout"
    other, rect = render(report, trial=0)
    star = at(other, rect, 0.64, 0.49)
    assert not (star.red() > 200 and star.green() > 150 and star.blue() < 120)


def test_fixation_circles_grow_with_duration_and_the_path_runs_dark_to_light(qapp):
    report = synthetic_map_report()
    report["trials"][0]["fixations"]["items"] = [[0.2, 0.2, 100], [0.5, 0.2, 700]]
    report["trials"][0]["path"] = [[[0.05 + 0.9 * i / 29, 0.8] for i in range(30)]]  # 29 segments
    image, rect = render(report, trial=0)

    def extent(x: float, y: float) -> int:
        """Width of the non-white span along the row through the centre (the number badge
        in the middle is white, so the ring and the tint are what is measured)."""
        cx, cy = round(rect.left() + x * rect.width()), round(rect.top() + y * rect.height())
        inked = [dx for dx in range(-80, 81) if not is_white(image.pixelColor(cx + dx, cy))]
        return inked[-1] - inked[0] if inked else 0

    assert extent(0.5, 0.2) > extent(0.2, 0.2)  # the 700 ms fixation is the bigger circle
    early, late = at(image, rect, 0.1, 0.8), at(image, rect, 0.9, 0.8)
    assert early.red() + early.green() + early.blue() < late.red() + late.green() + late.blue()


def test_the_trial_view_of_a_trial_with_no_gaze_still_shows_its_target(qapp):
    report = synthetic_map_report()
    report["trials"][0]["path"] = []
    report["trials"][0]["fixations"] = {"count": None, "mean_dur_ms": None, "items": []}
    image, rect = render(report, trial=0)
    assert not is_white(at(image, rect, 0.65, 0.5, 0, 0.6 * 0.05 * rect.width()))


# -- the image for the PDF -------------------------------------------------------------------------------


def test_render_to_image_uses_the_given_overlays_not_the_widgets_own(qapp):
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    widget.set_overlays(targets=False, path=True)
    assert widget.overlays() == {"targets": False, "path": True, "heat": False}
    image = widget.render_to_image(QSize(1000, 584), {"targets": True})
    rect = widget.canvas_rect(QRectF(image.rect()))
    assert greenish(at(image, rect, 0.65, 0.5, 0, 0.6 * 0.05 * rect.width()))
    assert is_white(at(image, rect, 0.5, 0.5))  # no path: only what was asked for
    assert widget.overlays() == {"targets": False, "path": True, "heat": False}  # untouched


def test_the_image_has_the_asked_size_a_white_surround_and_the_canvas_aspect(qapp):
    image, rect = render(synthetic_map_report(), size=(1800, 700))
    assert image.size() == QSize(1800, 700)
    assert rect.width() / rect.height() == pytest.approx(ASPECT, rel=1e-3)
    assert is_white(image.pixelColor(2, 2))  # outside the canvas rectangle's margin


def test_a_real_reports_map_marks_come_from_the_pipeline(qapp, tmp_path):
    report = folder_report(tmp_path)
    image, rect = render(report)
    first = report["map"]["marks"][0]
    r_px = first["r"] * rect.width()
    assert first["outcome"] == "hit"
    assert greenish(at(image, rect, first["x"], first["y"], 0, 0.6 * r_px))


def test_the_widget_does_not_modify_the_report_it_is_given(qapp):
    report = synthetic_map_report()
    before = copy.deepcopy(report)
    render(report, targets=True, path=True, heat=True)
    render(report, trial=1)
    assert report == before


# -- P9b: readable numbers, a legible start marker, a ramp that stays visible (P3, P4) ---------------------


def pill_of(text: str, size: float, max_width: float):
    """What the map draws behind ``text``: its pill and glyph box, centred on the origin."""
    font, metrics, width = fit_font(QFont(), text, size, max_width)
    return badge_pill(QPointF(0, 0), font, metrics, width), width, digits_height(font, metrics), font.pixelSize()


def one_fixation_report(duration_ms: float, outcome: str = "timeout") -> dict:
    """Trial 1 with one fixation at the middle of a straight path (y = 0.3), no target at
    the start, so only the path, the fixation and the markers are in the way."""
    report = synthetic_map_report()
    trial = report["trials"][0]
    trial["outcome"] = outcome
    trial["path"] = [[[0.1, 0.3], [0.9, 0.3]]]
    trial["fixations"]["items"] = [[0.5, 0.3, duration_ms]]
    return report


def test_the_number_of_a_missed_target_sits_on_a_white_badge_drawn_after_the_x(qapp):
    """P3: the red X used to run through the digits. The pill is drawn over the X, so no
    X-red pixel is left inside the digits' box, while the arms still show beyond the pill."""
    image, rect = render(synthetic_map_report())
    r_px = 0.05 * rect.width()
    unit = max(0.5, rect.width() / 900.0)
    pill, width, digits, _ = pill_of("2", min(26 * unit, max(9.0, r_px * 0.75)), 1.7 * r_px)
    cx, cy = rect.left() + 0.3 * rect.width(), rect.top() + 0.7 * rect.height()
    red_in_box = [
        (x, y)
        for x in range(round(cx - width / 2), round(cx + width / 2) + 1)
        for y in range(round(cy - digits / 2), round(cy + digits / 2) + 1)
        if reddish(image.pixelColor(x, y))
    ]
    assert red_in_box == []  # the X's arms cross exactly here (they met at the digits before)
    assert reddish(at(image, rect, 0.3, 0.7, 0.6 * r_px, 0.6 * r_px))  # the arms continue past the pill
    assert reddish(at(image, rect, 0.3, 0.7, -0.6 * r_px, 0.6 * r_px))
    assert pill.width() / 2 < 0.6 * r_px and pill.height() / 2 < 0.6 * r_px  # the badge is small


def test_a_hit_label_keeps_its_green_disc_with_no_badge(qapp):
    image, rect = render(synthetic_map_report())
    r_px = 0.05 * rect.width()
    assert greenish(at(image, rect, 0.65, 0.5, 0.25 * r_px, 0.25 * r_px))  # the number is white on green


def test_label_draws_its_badge_behind_the_text_and_only_when_asked(qapp):
    image = QImage(200, 100, QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    painter = QPainter(image)
    centre = QPointF(100, 50)
    _label(painter, centre, "12", "#FF0000", 400.0, 24, ("#FFFFFF", "#00FF00"))
    painter.end()
    pill, width, digits, pixel_size = pill_of("12", 24, 400.0)
    inside = round(100 + width / 2 + 0.5 * BADGE_PAD * pixel_size)
    outside = round(100 + pill.width() / 2 + 4)
    assert image.pixelColor(inside, 50) == QColor("#FFFFFF")  # on the badge, past the digits
    assert image.pixelColor(outside, 50) == QColor("#000000")  # the badge ends where it should
    bare = QImage(200, 100, QImage.Format.Format_ARGB32)
    bare.fill(QColor("#000000"))
    painter = QPainter(bare)
    _label(painter, centre, "12", "#FF0000", 400.0, 24)
    painter.end()
    assert bare.pixelColor(inside, 50) == QColor("#000000")  # no badge unless asked


def test_a_fixation_covers_the_path_and_its_number_sits_on_a_white_badge(qapp):
    """P4: a path line used to show through the translucent fixation circle and run under
    its number. The circle is opaque (tint over white) and the number has its own badge."""
    image, rect = render(one_fixation_report(500), trial=0)
    unit = rect.width() / 900.0
    radius = rect.width() * min(0.03, max(0.006, 500 * 0.00004))
    cx, cy = rect.left() + 0.5 * rect.width(), rect.top() + 0.3 * rect.height()
    path_on_row = image.pixelColor(round(cx + 1.6 * radius), round(cy))
    assert luminance(path_on_row) < 0.3  # the path is drawn, outside the circle
    inside = image.pixelColor(round(cx + 0.9 * radius), round(cy))  # on the path's row, inside the ring
    assert luminance(inside) > 0.6 and inside != path_on_row
    pill, width, digits, pixel_size = pill_of("1", max(9.0, radius), 1.8 * radius)
    badge = image.pixelColor(round(cx + width / 2 + 0.5 * BADGE_PAD * pixel_size), round(cy))
    assert badge == QColor("#FFFFFF")  # the badge is pure white, the circle's tint is not
    assert unit > 0


def test_the_start_marker_is_a_bigger_disc_than_the_old_eight_design_pixels(qapp):
    report = synthetic_map_report()
    trial = report["trials"][0]
    trial["fixations"]["items"] = []
    trial["path"] = [[[0.2, 0.2], [0.8, 0.2]]]
    trial["outcome"] = "timeout"
    image, rect = render(report, trial=0)
    unit = rect.width() / 900.0
    radius = max(13 * unit, 10.0)
    sx, sy = rect.left() + 0.2 * rect.width(), rect.top() + 0.2 * rect.height()
    ring = image.pixelColor(round(sx), round(sy - radius))
    assert luminance(ring) < 0.2  # the INK ring of the new, larger disc
    assert is_white(image.pixelColor(round(sx), round(sy - radius - 4 * unit)))  # nothing larger around it
    assert radius > 8 * unit  # it was 8 design px


def test_the_light_end_of_the_path_ramp_stays_visible_on_white(qapp):
    white = QColor("#FFFFFF")
    assert contrast(TRIAL_PATH_LIGHT, white) >= 3.0  # was a pale cyan, about 1.7
    assert luminance(TRIAL_PATH_DARK) < luminance(TRIAL_PATH_LIGHT)  # still dark to light
    report = synthetic_map_report()
    report["trials"][0]["fixations"]["items"] = []
    report["trials"][0]["path"] = [[[0.05 + 0.9 * i / 29, 0.8] for i in range(30)]]
    image, rect = render(report, trial=0)
    newest = at(image, rect, 0.93, 0.8)
    assert contrast(newest, white) >= 2.8  # the newest end of the drawn path, not just the constant
