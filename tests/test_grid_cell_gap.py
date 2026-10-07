"""SPEC-grid-cell-gap.md: Grid Click's operator-set gap between cells -- the
gap presets by visual angle, the one cell-geometry function drawing / fit / hit
test / dialog hint share, the dead zone, the cap on dense grids, the recorded
metadata / Log line / GAP_CAPPED event, and the Task settings dialog row.
Acceptance criteria 6.1-6.7."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QComboBox

from src.app import AssessmentApp
from src.data.schema import SessionMetadata
from src.engine.config import CONFIG_ROOT, deep_merge, load_task_config
from src.engine.settings_profile import load_settings_profile, save_settings_profile
from src.engine.target_size import (
    CELL_PAD_FRAC,
    GAP_CHOICES,
    GAP_PRESETS_DEG,
    REFERENCE_MM_PER_PX,
    ScaleInfo,
    apply_grid_gap,
    apply_target_size,
    estimate_grid_fit_radius_px,
    estimate_grid_geometry,
    fit_radius_px,
    gap_px_for,
    grid_cell_geometry,
    grid_gap_log_line,
    normalize_gap,
)
from src.engine.task_runner import build_task, run_headless_replay
from src.inputs.base import Pointer, circle_contains, norm_to_px
from src.tasks.base_task import TargetSpec
from src.ui.canvas import TaskCanvas
from src.ui.settings_registry import initial_structural_values, structural_settings_for_task
from src.ui.task_settings_dialog import TaskSettingsDialog

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
LAB = ScaleInfo(REFERENCE_MM_PER_PX, "edid", 531.4, 298.9)  # 24" 1080p, EDID
# The SPEC's S3 effect table was measured on a monitor with 41.4 px per degree
# at 650 mm; this scale reproduces it.
TABLE_MM_PER_PX = 2 * 650.0 * math.tan(math.radians(0.5)) / 41.4
TABLE = ScaleInfo(TABLE_MM_PER_PX, "config", 531.4, None)
CANVAS = (1920, 957)  # the table's canvas (HUD hidden)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeRecorder:
    def __init__(self):
        self.events = []
        self.lines = []

    def record_event(self, kind, t_ns, **payload):
        self.events.append((kind, t_ns, payload))

    def log(self, message):
        self.lines.append(message)

    def of(self, kind):
        return [payload for k, _t, payload in self.events if k == kind]


def _task(rows, cols, size="medium", gap="standard", canvas=CANVAS, recorder=None, scale=TABLE):
    """A click_grid task with size and gap resolved the way the app does.
    ``gap=None`` removes the key altogether (an old config / profile)."""
    cfg = load_task_config("click_grid")
    cfg["input"] = {"mode": "switch"}
    cfg["task"]["grid"] = {**cfg["task"]["grid"], "rows": rows, "cols": cols}
    if gap is None:
        cfg["task"]["grid"].pop("gap", None)
    else:
        cfg["task"]["grid"]["gap"] = gap
    cfg["task"]["target"]["size"] = size
    apply_target_size(cfg["task"], scale, 650.0)
    apply_grid_gap(cfg["task"], scale, 650.0)
    task = build_task("click_grid", cfg, recorder=recorder)
    task.set_screen_size(*canvas)
    task.jitter_px = 40.0
    return task


def _spec(task, slot):
    """A TargetSpec centred on grid cell ``slot`` (any cell, not just a trial's)."""
    x_norm, y_norm = task.cells[slot]
    return TargetSpec(
        index=0, x_norm=x_norm, y_norm=y_norm, radius_px=task.targets[0].radius_px, slot_index=slot
    )


def _centre_px(task, spec):
    return norm_to_px(spec.x_norm, spec.y_norm, task.screen_w, task.screen_h)


def _play(task, n_trials, between=None, t0=0, step_ns=50_000_000):
    t = t0
    while len(task.trials) < n_trials:
        target = task.targets[max(task._trial_index, 0)]
        task.update(
            t, Pointer(x=target.x_norm, y=target.y_norm, valid=True, clicked=True)
        )
        t += step_ns
        if between is not None:
            between(task)
    return t


# -- 6.2 presets and gap_px_for ----------------------------------------------------


def test_presets_and_choices_match_the_spec():
    assert GAP_PRESETS_DEG == {"standard": None, "wide": 1.0, "extra_wide": 2.0}
    assert GAP_CHOICES == (
        ("standard", "Standard"),
        ("wide", "Wide — 1°"),
        ("extra_wide", "Extra wide — 2°"),
    )


def test_normalize_gap_unknown_or_missing_means_standard(caplog):
    assert normalize_gap(None) == "standard"
    assert normalize_gap(" Extra_Wide ") == "extra_wide"
    with caplog.at_level(logging.WARNING, logger="src.engine.target_size"):
        assert normalize_gap("huge") == "standard"
    assert "huge" in caplog.text


def test_gap_px_for_is_the_visual_angle_extent_on_the_monitor():
    # 24" 1080p at 650 mm: 1 deg = 11.345 mm = 41.0 px, 2 deg = 22.69 mm = 82.0 px.
    assert gap_px_for("wide", REFERENCE_MM_PER_PX, 650.0) == pytest.approx(41.0, abs=0.5)
    assert gap_px_for("extra_wide", REFERENCE_MM_PER_PX, 650.0) == pytest.approx(82.0, abs=0.5)
    # Exactly the formula, whatever the monitor (the same maths as radius_px_for).
    for mm_per_px, distance in ((0.3, 650.0), (0.2768, 700.0)):
        for name, degrees in (("wide", 1.0), ("extra_wide", 2.0)):
            extent_mm = 2 * distance * math.tan(math.radians(degrees) / 2)
            assert gap_px_for(name, mm_per_px, distance) == pytest.approx(extent_mm / mm_per_px)


def test_gap_px_for_standard_is_none_and_unknown_is_standard():
    assert gap_px_for("standard", REFERENCE_MM_PER_PX, 650.0) is None
    assert gap_px_for("nonsense", REFERENCE_MM_PER_PX, 650.0) is None


def test_gap_px_is_per_logical_px_so_a_scaled_display_gets_fewer_px():
    # 1920 physical px at 150 % is 1280 logical px over the same glass.
    assert gap_px_for("wide", 531.4 / 1280, 650.0) == pytest.approx(
        gap_px_for("wide", REFERENCE_MM_PER_PX, 650.0) / 1.5
    )


# -- 4.2 resolving the gap into the run config --------------------------------------


def test_apply_grid_gap_writes_gap_px_and_returns_the_metadata_block():
    task_cfg = {"grid": {"rows": 3, "cols": 3, "gap": "wide"}}
    info = apply_grid_gap(task_cfg, LAB, 650.0)
    assert task_cfg["grid"]["gap_px"] == pytest.approx(41.0, abs=0.1)
    assert info == {"preset": "wide", "gap_deg": 1.0, "gap_px": task_cfg["grid"]["gap_px"]}


def test_apply_grid_gap_standard_resolves_to_no_px():
    task_cfg = {"grid": {"gap": "standard", "gap_px": 99}}  # a stale value is cleared
    info = apply_grid_gap(task_cfg, LAB, 650.0)
    assert task_cfg["grid"]["gap_px"] is None
    assert info == {"preset": "standard", "gap_deg": None, "gap_px": None}


def test_apply_grid_gap_without_a_gap_key_touches_nothing():
    for task_cfg in ({"grid": {"rows": 3}}, {"target": {"size": "medium"}}, {}):
        before = json.dumps(task_cfg, sort_keys=True)
        assert apply_grid_gap(task_cfg, LAB, 650.0) is None
        assert json.dumps(task_cfg, sort_keys=True) == before


def test_apply_grid_gap_unknown_name_is_standard():
    task_cfg = {"grid": {"gap": "huge"}}
    assert apply_grid_gap(task_cfg, LAB, 650.0)["preset"] == "standard"
    assert task_cfg["grid"]["gap_px"] is None


def test_log_line_wording():
    wide = apply_grid_gap({"grid": {"gap": "wide"}}, LAB, 650.0)
    assert grid_gap_log_line(wide) == "Cell gap: Wide — 1° (≈41 px)"
    extra = apply_grid_gap({"grid": {"gap": "extra_wide"}}, LAB, 650.0)
    assert grid_gap_log_line(extra) == "Cell gap: Extra wide — 2° (≈82 px)"
    assert grid_gap_log_line({"preset": "standard", "gap_deg": None, "gap_px": None}) == (
        "Cell gap: Standard"
    )


# -- 6.1 standard is exactly today's board (H1) -------------------------------------


def test_standard_geometry_pins_todays_numbers():
    # 6x6 on 1500 x 1000 (margin 0.12): pitch 190 x 126.667.
    pitch_w, pitch_h = 0.76 / 6 * 1500, 0.76 / 6 * 1000
    geometry = grid_cell_geometry(pitch_w, pitch_h)
    assert geometry.inset == pytest.approx(7.6, abs=1e-9)  # 0.06 of the smaller side
    assert geometry.cell_w == pytest.approx(190.0 - 15.2)
    assert geometry.cell_h == pytest.approx(126.6667 - 15.2, abs=1e-3)
    assert geometry.gap_px == pytest.approx(15.2)
    assert geometry.fit_radius_px == pytest.approx(55.7333, abs=1e-3)
    assert (geometry.hit_w, geometry.hit_h) == (pitch_w, pitch_h)  # the unpadded pitch
    assert geometry.wanted_px is None and geometry.capped is False
    # ... and the very formula it replaced, bit for bit.
    assert geometry.fit_radius_px == 0.5 * min(pitch_w, pitch_h) * (1.0 - 2.0 * CELL_PAD_FRAC)
    assert fit_radius_px(pitch_w, pitch_h) == geometry.fit_radius_px
    assert estimate_grid_fit_radius_px(6, 6, 1500, 1000) == geometry.fit_radius_px


def test_standard_task_numbers_are_pinned_on_the_table_canvas():
    task = _task(3, 3, gap="standard")
    assert task.gap_px is None
    scene = task.scene_spec()
    assert scene["cell_inset_px"] == pytest.approx(0.06 * 0.76 / 3 * 957, abs=1e-9)  # 14.546
    assert scene["cell_inset_px"] == pytest.approx(14.55, abs=0.01)
    assert task.effective_radius_px(task.targets[0]) == pytest.approx(103.6, abs=0.2)  # not capped
    assert task.effective_radius_px(task.targets[0]) == task.targets[0].radius_px
    big =_task(6, 6, size="large", canvas=(1500, 1000), gap="standard")
    assert big.effective_radius_px(big.targets[0]) == pytest.approx(55.7, abs=0.1)


def _legacy_hit_test(task, target, cx, cy, px, py):
    """ClickGridTask.hit_test as it was before the gap setting (b6803a6)."""
    cell_w_px, cell_h_px = task.cell_w * task.screen_w, task.cell_h * task.screen_h
    radius = min(target.radius_px, 0.5 * min(cell_w_px, cell_h_px) * (1.0 - 2.0 * CELL_PAD_FRAC))
    in_cell = abs(px - cx) <= cell_w_px / 2 and abs(py - cy) <= cell_h_px / 2
    return in_cell and circle_contains(cx, cy, radius + task.jitter_px, px, py)


@pytest.mark.parametrize("gap", ["standard", None])  # explicit standard, and no gap key at all
@pytest.mark.parametrize("rows, cols, size", [(3, 3, "medium"), (6, 6, "large"), (4, 5, "small")])
def test_standard_and_a_config_without_a_gap_hit_test_exactly_as_before(rows, cols, size, gap):
    task = _task(rows, cols, size=size, gap=gap)
    target = task.targets[0]
    cx, cy = _centre_px(task, target)
    for dx in range(-300, 301, 15):
        for dy in range(-200, 201, 10):
            assert task.hit_test(target, cx, cy, cx + dx, cy + dy) == _legacy_hit_test(
                task, target, cx, cy, cx + dx, cy + dy
            ), (dx, dy)


def test_a_config_without_a_gap_records_nothing_new():
    recorder = _FakeRecorder()
    task = _task(6, 6, size="large", gap=None, recorder=recorder)
    _play(task, 2)
    assert task.gap_px is None and task.gap_capped_px is None
    assert recorder.of("GAP_CAPPED") == []
    assert not any("gap" in line.lower() for line in recorder.lines)


# -- 6.3 grid_cell_geometry: floor, cap, the SPEC's S3 table ------------------------


@pytest.mark.parametrize(
    "rows, cols, gap, used, cell_w, cell_h, radius",
    [
        (3, 3, "standard", 29, 457, 213, 106),
        (3, 3, "wide", 41, 445, 201, 100),
        (3, 3, "extra_wide", 83, 403, 159, 79),
        (6, 6, "standard", 15, 228, 106, 53),
        (6, 6, "wide", 41, 202, 80, 40),
        (6, 6, "extra_wide", 60, 183, 61, 30),
    ],
)
def test_the_spec_effect_table_is_reproduced(rows, cols, gap, used, cell_w, cell_h, radius):
    gap_px = gap_px_for(gap, TABLE_MM_PER_PX, 650.0)
    geometry = estimate_grid_geometry(rows, cols, *CANVAS, 0.12, gap_px)
    assert geometry.gap_px == pytest.approx(used, abs=1.0)
    assert geometry.cell_w == pytest.approx(cell_w, abs=1.0)
    assert geometry.cell_h == pytest.approx(cell_h, abs=1.0)
    assert geometry.fit_radius_px == pytest.approx(radius, abs=1.0)
    assert geometry.capped is (rows == 6 and gap == "extra_wide")


def test_a_wide_gap_is_never_narrower_than_standard():
    # 3x3: the standard gap is 29 px; a (hypothetical) 10 px gap is floored to it.
    standard = grid_cell_geometry(486.4, 242.44)
    floored = grid_cell_geometry(486.4, 242.44, 10.0)
    assert floored.gap_px == pytest.approx(standard.gap_px)
    assert floored.capped is False
    assert floored.wanted_px == 10.0
    # But it is a wide-style cell: the hit area is the drawn cell, not the pitch.
    assert floored.hit_w == pytest.approx(486.4 - standard.gap_px)


def test_a_wanted_gap_is_capped_at_half_the_smaller_pitch_and_reports_it():
    geometry = grid_cell_geometry(243.2, 121.2, 83.0)  # 6x6 Extra wide
    assert geometry.capped is True
    assert geometry.gap_px == pytest.approx(60.6)  # 50 % of 121.2
    assert geometry.wanted_px == 83.0
    assert geometry.cell_h == pytest.approx(60.6)  # a drawn cell stays half its pitch
    assert geometry.cell_w == pytest.approx(243.2 - 60.6)
    assert geometry.inset == pytest.approx(30.3)
    assert geometry.fit_radius_px == pytest.approx(30.3)


def test_the_drawn_cell_is_the_pitch_less_the_gap_and_the_hit_area_is_that_cell():
    geometry = grid_cell_geometry(486.4, 242.44, 41.0)
    assert geometry.capped is False
    assert geometry.gap_px == 41.0
    assert (geometry.cell_w, geometry.cell_h) == pytest.approx((445.4, 201.44))
    assert geometry.inset == 20.5
    assert (geometry.hit_w, geometry.hit_h) == pytest.approx((445.4, 201.44))
    assert geometry.fit_radius_px == pytest.approx(0.5 * 201.44)


def test_estimate_grid_fit_radius_takes_the_gap():
    standard = estimate_grid_fit_radius_px(6, 6, 1500, 1000)
    wide = estimate_grid_fit_radius_px(6, 6, 1500, 1000, gap_px=41.0)
    assert wide < standard
    assert wide == pytest.approx(0.5 * (0.76 / 6 * 1000 - 41.0))


# -- 6.4 hit test, Wide: the gap is a dead zone ------------------------------------


def test_a_point_in_the_gap_hits_neither_cell_even_within_jitter_of_both():
    task = _task(3, 3, gap="wide")  # 41 px gap, 3x3: vertical neighbours are cells 0 and 3
    above, below = _spec(task, 0), _spec(task, 3)
    (ax, ay), (bx, by) = _centre_px(task, above), _centre_px(task, below)
    px, py = (ax + bx) / 2, (ay + by) / 2  # the middle of the gap between the two rows

    reach = task.effective_radius_px(above) + task.jitter_px
    assert math.hypot(px - ax, py - ay) < reach  # inside radius + jitter of BOTH targets...
    assert math.hypot(px - bx, py - by) < reach
    assert circle_contains(ax, ay, reach, px, py) and circle_contains(bx, by, reach, px, py)

    for offset in (-2.0, 0.0, 2.0):  # the middle of the gap and a hair either side of it
        assert task.hit_test(above, ax, ay, px, py + offset) is False  # ... yet it selects neither
        assert task.hit_test(below, bx, by, px, py + offset) is False
    # On the standard board the two hit areas touch: a hair either side of the same
    # line is on the nearer cell, so there is no dead zone between them.
    standard = _task(3, 3, gap="standard")
    assert standard.hit_test(_spec(standard, 0), ax, ay, px, py - 2.0) is True
    assert standard.hit_test(_spec(standard, 3), bx, by, px, py + 2.0) is True


@pytest.mark.parametrize("gap, size", [("wide", "medium"), ("extra_wide", "small")])
def test_every_point_in_the_gap_between_two_cells_is_a_dead_zone(gap, size):
    task = _task(3, 3, size=size, gap=gap)
    geometry = grid_cell_geometry(*task._cell_px(), task.gap_px)
    left, right = _spec(task, 0), _spec(task, 1)
    (lx, ly), (rx, _ry) = _centre_px(task, left), _centre_px(task, right)
    x0, x1 = lx + geometry.cell_w / 2, rx - geometry.cell_w / 2  # the gap, edge to edge
    assert x1 - x0 == pytest.approx(geometry.gap_px)
    for i in range(1, 20):
        px = x0 + (x1 - x0) * i / 20
        assert task.hit_test(left, lx, ly, px, ly) is False
        assert task.hit_test(right, rx, ly, px, ly) is False


def test_a_point_inside_the_drawn_cell_within_radius_plus_jitter_still_hits():
    task = _task(3, 3, gap="wide")
    target = _spec(task, 4)
    cx, cy = _centre_px(task, target)
    geometry = grid_cell_geometry(*task._cell_px(), task.gap_px)
    reach = task.effective_radius_px(target) + task.jitter_px
    inside = geometry.cell_h / 2 - 2.0  # just inside the drawn cell's top edge
    assert task.hit_test(target, cx, cy, cx, cy - inside) is True
    d = geometry.cell_h / 2 - 2.0  # a corner of the drawn cell, still inside radius + jitter
    assert math.hypot(d, d) < reach
    assert task.hit_test(target, cx, cy, cx + d, cy + d) is True


def test_wide_clips_to_the_drawn_cell_where_standard_clips_to_the_pitch():
    wide, standard = _task(3, 3, gap="wide"), _task(3, 3, gap="standard")
    target_w, target_s = _spec(wide, 4), _spec(standard, 4)
    cx, cy = _centre_px(wide, target_w)
    geometry = grid_cell_geometry(*wide._cell_px(), wide.gap_px)
    dy = geometry.cell_h / 2 + 3.0  # just past the drawn cell's edge, still inside the pitch
    assert dy < wide._cell_px()[1] / 2
    assert dy < wide.effective_radius_px(target_w) + wide.jitter_px  # and inside radius + jitter
    assert wide.hit_test(target_w, cx, cy, cx, cy + dy) is False
    assert standard.hit_test(target_s, cx, cy, cx, cy + dy) is True


def test_update_reports_no_target_for_gaze_in_the_gap():
    task = _task(3, 3, gap="wide")
    target = task.targets[0]
    cx, cy = _centre_px(task, target)
    geometry = grid_cell_geometry(*task._cell_px(), task.gap_px)
    in_gap = Pointer(
        x=cx / task.screen_w,
        y=(cy + geometry.cell_h / 2 + geometry.gap_px / 2) / task.screen_h,
        valid=True,
        clicked=False,
    )
    assert task.update(0, in_gap).on_target is False
    on_cell = Pointer(x=cx / task.screen_w, y=cy / task.screen_h, valid=True, clicked=False)
    assert task.update(10_000_000, on_cell).on_target is True


# -- 4.3 effective radius and the scene follow the drawn cell ------------------------


def test_the_target_is_capped_to_the_drawn_cell():
    task = _task(3, 3, gap="wide")  # 3x3 Medium: radius 103.6 > half the drawn cell's 201 px
    target = task.targets[0]
    assert target.radius_px == pytest.approx(103.6, abs=0.2)
    assert task.effective_radius_px(target) == pytest.approx(100.5, abs=0.1)
    result = task.update(0, Pointer(x=target.x_norm, y=target.y_norm, valid=True, clicked=False))
    assert result.target_radius_px == pytest.approx(task.effective_radius_px(target))


def test_scene_spec_carries_the_inset_the_target_is_fitted_to():
    for gap in ("standard", "wide", "extra_wide"):
        task = _task(6, 6, size="large", gap=gap)
        scene = task.scene_spec()
        drawn_h = scene["cell_h"] * task.screen_h - 2 * scene["cell_inset_px"]
        assert task.effective_radius_px(task.targets[0]) <= drawn_h / 2 + 1e-9, gap
        assert task.effective_radius_px(task.targets[0]) == pytest.approx(drawn_h / 2), gap
    wide = _task(3, 3, gap="wide").scene_spec()["cell_inset_px"]
    assert wide == pytest.approx(gap_px_for("wide", TABLE_MM_PER_PX, 650.0) / 2, abs=0.1)


def test_hud_hide_mid_run_re_evaluates_the_gap_inset_and_radius():
    task = _task(6, 6, size="small", gap="wide", canvas=(1640, 1003))
    shown = task.scene_spec()["cell_inset_px"]
    radius_shown = task.effective_radius_px(task.targets[0])
    task.set_screen_size(1920, 957)  # the HUD hides: the canvas changes size
    hidden = task.scene_spec()["cell_inset_px"]
    # The gap in px does not follow the canvas (it is an angle), so the inset is the
    # same ... but a cap on a shorter canvas does, and the radius follows the cell.
    assert hidden == pytest.approx(shown, abs=0.01)
    assert hidden == pytest.approx(gap_px_for("wide", TABLE_MM_PER_PX, 650.0) / 2, abs=0.1)
    assert task.effective_radius_px(task.targets[0]) != pytest.approx(radius_shown, abs=0.01)
    task.set_screen_size(1920, 600)  # so short that even Wide is capped
    assert task.scene_spec()["cell_inset_px"] == pytest.approx(0.25 * 0.76 / 6 * 600)


# -- 6.7 GAP_CAPPED --------------------------------------------------------------------


def test_one_gap_capped_event_per_run_with_wanted_and_used_px():
    recorder = _FakeRecorder()
    task = _task(6, 6, size="large", gap="extra_wide", recorder=recorder)
    _play(task, 3)
    capped = recorder.of("GAP_CAPPED")
    assert len(capped) == 1  # once per run, not per trial
    assert capped[0]["requested_px"] == pytest.approx(82.8, abs=0.1)
    assert capped[0]["used_px"] == pytest.approx(60.6, abs=0.1)  # half the 121.2 px pitch
    assert (capped[0]["rows"], capped[0]["cols"]) == (6, 6)
    assert task.gap_capped_px == pytest.approx(60.61, abs=0.01)
    assert recorder.lines == [
        "Cell gap limited to ≈61 px (wanted ≈83 px) to fit a 6 x 6 grid."
    ]
    # Before TARGET_SHOWN, like TARGET_SHRUNK.
    kinds = [kind for kind, _t, _p in recorder.events]
    assert kinds.index("GAP_CAPPED") < kinds.index("TARGET_SHOWN")


def test_no_gap_capped_event_when_the_gap_fits():
    for rows, gap in ((3, "wide"), (3, "extra_wide"), (6, "wide"), (6, "standard")):
        recorder = _FakeRecorder()
        task = _task(rows, rows, size="large", gap=gap, recorder=recorder)
        _play(task, 2)
        assert recorder.of("GAP_CAPPED") == [], (rows, gap)
        assert task.gap_capped_px is None


def test_gap_capped_is_reported_at_the_first_trial_start_where_it_applies():
    recorder = _FakeRecorder()
    task = _task(6, 6, size="large", gap="extra_wide", canvas=(1920, 1400), recorder=recorder)

    def _hud_shown_after_first_trial(t):
        if len(t.trials) == 1:
            t.set_screen_size(1920, 957)  # a shorter canvas: now the gap is capped

    _play(task, 4, between=_hud_shown_after_first_trial)
    assert len(recorder.of("GAP_CAPPED")) == 1
    assert recorder.of("GAP_CAPPED")[0]["used_px"] == pytest.approx(60.6, abs=0.1)


def test_a_resize_does_not_repeat_gap_capped():
    recorder = _FakeRecorder()
    task = _task(6, 6, size="large", gap="extra_wide", recorder=recorder)

    def _shrink_further(t):
        if len(t.trials) == 1:
            t.set_screen_size(1920, 700)

    _play(task, 3, between=_shrink_further)
    assert len(recorder.of("GAP_CAPPED")) == 1


# -- 4.2 metadata, Log line, replay ---------------------------------------------------


def _fake_screen(logical_w, dpr, width_mm, height_mm):
    return SimpleNamespace(
        geometry=lambda: SimpleNamespace(width=lambda: logical_w),
        devicePixelRatio=lambda: dpr,
        physicalSize=lambda: SimpleNamespace(width=lambda: width_mm, height=lambda: height_mm),
    )


def _fake_app(task_cfg, screen):
    return SimpleNamespace(
        config={"app": {"viewing_distance_mm": 650}, "task": task_cfg},
        canvas=SimpleNamespace(screen=lambda: screen),
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        recorder=_FakeRecorder(),
    )


def test_app_resolves_the_gap_into_gap_px_metadata_and_session_log():
    app = _fake_app(
        {"target": {"size": "medium"}, "grid": {"gap": "wide"}}, _fake_screen(1920, 1.0, 531.4, 298.9)
    )
    AssessmentApp._resolve_target_size(app)
    assert app.config["task"]["grid"]["gap_px"] == pytest.approx(41.0, abs=0.1)
    assert app.metadata.grid_gap == {"preset": "wide", "gap_deg": 1.0, "gap_px": app.config["task"]["grid"]["gap_px"]}
    assert app.recorder.lines[-1] == "Cell gap: Wide — 1° (≈41 px)"
    assert app.metadata.target_size["preset"] == "medium"  # the size part is untouched


def test_app_logs_standard_without_a_px_value():
    app = _fake_app({"target": {"size": "medium"}, "grid": {"gap": "standard"}}, None)
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.grid_gap == {"preset": "standard", "gap_deg": None, "gap_px": None}
    assert app.recorder.lines[-1] == "Cell gap: Standard"


def test_app_resolves_the_gap_in_logical_px_at_150_percent_scale():
    app = _fake_app({"grid": {"gap": "wide"}}, _fake_screen(1280, 1.5, 531.4, 298.9))
    AssessmentApp._resolve_target_size(app)
    assert app.config["task"]["grid"]["gap_px"] == pytest.approx(41.0 / 1.5, abs=0.2)


def test_app_without_a_gap_key_changes_nothing():
    app = _fake_app({"target": {"size": "medium"}, "grid": {"rows": 3}}, None)
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.grid_gap is None
    assert "gap_px" not in app.config["task"]["grid"]
    assert not any("gap" in line for line in app.recorder.lines)


def test_session_end_copies_the_capped_gap_into_the_metadata_block():
    meta = SessionMetadata(
        subject_id="P001", session_id="s", started_ns=0,
        grid_gap={"preset": "extra_wide", "gap_deg": 2.0, "gap_px": 82.8},
    )
    app = SimpleNamespace(
        task=SimpleNamespace(gap_capped_px=60.66),
        metadata=meta,
        client=SimpleNamespace(is_live=False),
        _save_eye_geometry=False,
    )
    AssessmentApp._record_session_end_quality(app)
    assert meta.grid_gap["gap_px_used"] == 60.7
    # Not capped: no gap_px_used key; and a task with no gap at all is fine.
    meta2 = SessionMetadata(
        subject_id="P001", session_id="s", started_ns=0,
        grid_gap={"preset": "wide", "gap_deg": 1.0, "gap_px": 41.0},
    )
    app.task, app.metadata = SimpleNamespace(gap_capped_px=None), meta2
    AssessmentApp._record_session_end_quality(app)
    assert "gap_px_used" not in meta2.grid_gap
    app.task, app.metadata = SimpleNamespace(), SessionMetadata(subject_id="x", session_id="y", started_ns=0)
    AssessmentApp._record_session_end_quality(app)


def test_metadata_grid_gap_defaults_to_none():
    assert SessionMetadata(subject_id="x", session_id="y", started_ns=0).grid_gap is None


def test_headless_replay_records_the_standard_gap_and_todays_radius(tmp_path):
    result = run_headless_replay("click_grid", FIXTURE, output_root=tmp_path, max_seconds=30.0)
    session = Path(result["session_dir"])
    data = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    assert data["grid_gap"] == {"preset": "standard", "gap_deg": None, "gap_px": None}
    assert data["target_size"]["radius_px"] == pytest.approx(102.5, abs=1.0)
    assert "Cell gap: Standard" in (session / "session.log").read_text(encoding="utf-8")


def test_headless_replay_records_a_capped_extra_wide_gap(tmp_path):
    root = tmp_path / "configs"
    shutil.copytree(CONFIG_ROOT, root)
    yaml_path = root / "tasks" / "click_grid.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    text = text.replace("gap: standard", "gap: extra_wide").replace("rows: 3", "rows: 6").replace(
        "cols: 3", "cols: 6"
    )
    yaml_path.write_text(text, encoding="utf-8")
    result = run_headless_replay(
        "click_grid", FIXTURE, output_root=tmp_path / "out", config_root=root, max_seconds=3.0
    )
    session = Path(result["session_dir"])
    data = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    info = data["grid_gap"]
    assert (info["preset"], info["gap_deg"]) == ("extra_wide", 2.0)
    assert info["gap_px"] == pytest.approx(82.0, abs=1.0)
    assert info["gap_px_used"] < info["gap_px"]  # capped on the replay canvas
    log = (session / "session.log").read_text(encoding="utf-8")
    assert "Cell gap: Extra wide — 2° (≈82 px)" in log
    assert "Cell gap limited to" in log
    events = [
        json.loads(line) for line in (session / "events.jsonl").read_text("utf-8").splitlines()
    ]
    assert sum(1 for e in events if e["kind"] == "GAP_CAPPED") == 1


# -- 4.4 the canvas draws the cell from the scene's inset ------------------------------

_THEME = {"background": "#000000", "cursor_color": "#ffffff", "target_default": "#ff5252"}


def _grid_alpha(scene_extra: dict, probe_x: int) -> int:
    """Alpha of one pixel of the idle cells the canvas paints: a 2-column board on
    a 600x400 canvas (each pitch 300 wide), probed on the first cell's row centre."""
    canvas = TaskCanvas(theme=_THEME)
    canvas.active_slot = -1
    canvas.scene = {
        "mode": "grid",
        "cells": [(0.25, 0.5), (0.75, 0.5)],
        "cell_w": 0.5,
        "cell_h": 1.0,
        **scene_extra,
    }
    image = QImage(600, 400, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    canvas._draw_grid_scene(painter, 600, 400)
    painter.end()
    return image.pixelColor(probe_x, 200).alpha()


def test_the_canvas_draws_the_cell_from_the_scene_inset(qapp):
    # Inset 30: the first cell is drawn from x = 30 to 270, so x = 285 is the gap...
    assert _grid_alpha({"cell_inset_px": 30.0}, 150) > 0  # inside the cell
    assert _grid_alpha({"cell_inset_px": 30.0}, 285) == 0
    assert _grid_alpha({"cell_inset_px": 30.0}, 300) == 0  # the middle of the gap
    assert _grid_alpha({"cell_inset_px": 30.0}, 450) > 0  # the second cell
    # ... while inset 5 draws it to x = 295, covering that same pixel.
    assert _grid_alpha({"cell_inset_px": 5.0}, 285) > 0


def test_a_scene_without_an_inset_is_drawn_as_the_standard_board(qapp):
    # The standard inset is 6 % of the smaller side (300): the cell ends at x = 282.
    assert _grid_alpha({}, 278) > 0
    assert _grid_alpha({}, 285) == 0


def test_the_task_scene_drives_the_canvas_for_a_wide_gap(qapp):
    task = _task(3, 3, gap="wide", canvas=(600, 400))
    inset = task.scene_spec()["cell_inset_px"]
    assert inset == pytest.approx(gap_px_for("wide", TABLE_MM_PER_PX, 650.0) / 2, abs=0.1)
    # Probe the middle of the vertical gap between the top two rows of the first column.
    canvas = TaskCanvas(theme=_THEME)
    canvas.active_slot = -1
    canvas.scene = task.scene_spec()
    image = QImage(600, 400, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    canvas._draw_grid_scene(painter, 600, 400)
    painter.end()
    (cx, cy), (_bx, by) = norm_to_px(*task.cells[0], 600, 400), norm_to_px(*task.cells[3], 600, 400)
    assert image.pixelColor(int(cx), int(cy)).alpha() > 0  # inside the first cell
    assert image.pixelColor(int(cx), int((cy + by) / 2)).alpha() == 0  # the gap between the rows


# -- 6.6 the Task settings dialog ------------------------------------------------------


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


@pytest.fixture
def lab_screen(monkeypatch):
    screen = SimpleNamespace(
        geometry=lambda: _Rect(1920, 1080),
        availableGeometry=lambda: _Rect(1920, 1000),
        devicePixelRatio=lambda: 1.0,
        physicalSize=lambda: _Rect(531.4, 298.9),
    )
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: screen)


def _dialog(task_id="click_grid", **grid):
    config = load_task_config(task_id)
    if grid:
        config["task"]["grid"] = {**config["task"]["grid"], **grid}
    return TaskSettingsDialog(task_id, config)


def _keys(task_id):
    return [s.key for s in structural_settings_for_task(task_id)]


def test_cell_gap_row_is_on_click_grid_only_right_after_grid_cols():
    keys = _keys("click_grid")
    assert keys.index("grid.gap") == keys.index("grid.cols") + 1
    for task_id in ("click_static", "follow_moving", "scanning"):
        assert "grid.gap" not in _keys(task_id)
    setting = next(s for s in structural_settings_for_task("click_grid") if s.key == "grid.gap")
    assert (setting.label, setting.kind, setting.default) == ("Cell gap", "choice", "standard")
    assert setting.choices == GAP_CHOICES and setting.applies_to == ("click_grid",)


def test_dialog_shows_the_gap_combo_on_click_grid_only(qapp):
    dialog = _dialog()
    assert isinstance(dialog._controls["grid.gap"], QComboBox)
    assert dialog._controls["grid.gap"].currentData() == "standard"  # the default
    for task_id in ("click_static", "follow_moving", "scanning"):
        assert "grid.gap" not in _dialog(task_id)._controls


def test_gap_items_show_the_px_it_comes_to_on_this_monitor(qapp, lab_screen):
    dialog = _dialog()
    combo = dialog._controls["grid.gap"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Standard",
        "Wide — 1° (≈41 px)",
        "Extra wide — 2° (≈82 px)",
    ]
    assert [combo.itemData(i) for i in range(combo.count())] == ["standard", "wide", "extra_wide"]


def test_overrides_return_the_chosen_gap_as_a_string(qapp):
    dialog = _dialog()
    combo = dialog._controls["grid.gap"]
    combo.setCurrentIndex(combo.findData("wide"))
    gap = dialog.overrides()["grid"]["gap"]
    assert gap == "wide" and isinstance(gap, str)


def test_dialog_restores_the_gap_from_the_config(qapp):
    dialog = _dialog(gap="extra_wide")  # kept alive: its widgets die with it
    assert dialog._controls["grid.gap"].currentData() == "extra_wide"
    # A missing or no-longer-valid value falls back to Standard.
    assert initial_structural_values("click_grid", {"task": {"grid": {}}})["grid.gap"] == "standard"
    assert (
        initial_structural_values("click_grid", {"task": {"grid": {"gap": "huge"}}})["grid.gap"]
        == "standard"
    )


def test_hint_follows_the_gap_and_says_when_it_is_capped(qapp, lab_screen):
    dialog = _dialog()  # 3x3 Medium on a ~1000 px canvas: fits with the standard gap
    combo = dialog._controls["grid.gap"]
    assert dialog.fit_hint.isHidden()
    combo.setCurrentIndex(combo.findData("wide"))
    assert dialog.fit_hint.isHidden()  # 41 px still leaves the target its size
    combo.setCurrentIndex(combo.findData("extra_wide"))
    assert not dialog.fit_hint.isHidden()  # 82 px takes the cells below Medium
    assert dialog.fit_hint_label.text() == (
        "Will be shrunk to ≈ 171 px to fit a 3 x 3 grid (approximate)"
    )
    dialog._controls["grid.rows"].setValue(6)
    dialog._controls["grid.cols"].setValue(6)  # dense: 82 px is over half a cell
    assert dialog.fit_hint_label.text() == (
        "Gap limited to ≈ 63 px and targets shrunk to ≈ 63 px to fit a 6 x 6 grid (approximate)"
    )
    combo.setCurrentIndex(combo.findData("standard"))  # back to today's board
    assert dialog.fit_hint_label.text() == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )


def test_hint_follows_rows_cols_and_size_with_a_wide_gap(qapp, lab_screen):
    dialog = _dialog(gap="extra_wide", rows=6, cols=6)
    assert dialog.fit_hint_label.text().startswith("Gap limited to ≈ 63 px and targets shrunk")
    size = dialog._controls["target.size"]
    size.setCurrentIndex(size.findData("small"))  # the hint still recomputes
    assert dialog.fit_hint_label.text().startswith("Gap limited to ≈ 63 px and targets shrunk")
    dialog._controls["grid.rows"].setValue(3)
    dialog._controls["grid.cols"].setValue(3)
    assert dialog.fit_hint.isHidden()  # Small fits 3x3 even with the 82 px gap


def test_standard_hint_is_unchanged_from_before_the_gap_row(qapp, lab_screen):
    dialog = _dialog(rows=6, cols=6)
    assert dialog.fit_hint_label.text() == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )


def test_a_dialog_without_the_gap_row_still_hints_as_standard(qapp, lab_screen):
    # Defensive: the hint must not require the control.
    dialog = _dialog(rows=6, cols=6)
    del dialog._controls["grid.gap"]
    dialog._update_fit_hint()
    assert dialog.fit_hint_label.text() == (
        "Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)"
    )


# -- 6.6 saved in / restored from a settings profile -----------------------------------

LIVE = {"dwell.threshold_ms": 900}


def test_the_gap_round_trips_through_a_settings_profile(qapp, tmp_path):
    dialog = _dialog()
    combo = dialog._controls["grid.gap"]
    combo.setCurrentIndex(combo.findData("wide"))
    overrides = dialog.overrides()
    assert overrides["grid"]["gap"] == "wide"

    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, overrides)
    stored = load_settings_profile(tmp_path, "S1", "click_grid")["structural"]
    assert stored["grid"]["gap"] == "wide"
    config = load_task_config("click_grid")
    config["task"] = deep_merge(config["task"], stored)
    restored = TaskSettingsDialog("click_grid", config)  # kept alive: its widgets die with it
    assert restored._controls["grid.gap"].currentData() == "wide"

    # ... and it is what the run resolves.
    app = SimpleNamespace(
        config=config,
        canvas=SimpleNamespace(screen=lambda: None),
        metadata=SimpleNamespace(target_size=None, grid_gap=None),
        recorder=SimpleNamespace(log=lambda _m: None),
    )
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.grid_gap["preset"] == "wide"
    assert config["task"]["grid"]["gap_px"] > 0


def test_an_older_profile_without_a_gap_loads_as_standard(qapp, tmp_path):
    # Written before the Cell gap row: a grid block with no `gap`.
    save_settings_profile(
        tmp_path, "S1", "click_grid", LIVE, {"target": {"size": "large"}, "grid": {"rows": 5, "cols": 5}}
    )
    stored = load_settings_profile(tmp_path, "S1", "click_grid")["structural"]
    config = load_task_config("click_grid")
    config["task"] = deep_merge(config["task"], stored)
    restored = TaskSettingsDialog("click_grid", config)  # kept alive: its widgets die with it
    assert restored._controls["grid.gap"].currentData() == "standard"
    task = build_task("click_grid", config)
    assert task.gap_px is None  # the standard board
