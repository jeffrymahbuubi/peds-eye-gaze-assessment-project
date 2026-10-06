"""SPEC-target-size-and-motion-paths.md Phase B (S11): a size preset instead of a
px radius for every task -- click_static and follow_moving move the target
inward at the canvas edge (size never changes), scanning shrinks its icons
together and keeps neighbouring icons from counting. Acceptance criteria
S11.4 items 1-7 (item 8 is the full suite, item 9 the hub's live check)."""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QComboBox

from src.app import AssessmentApp
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.engine.config import deep_merge, load_task_config
from src.engine.settings_profile import (
    load_settings_profile,
    resolve_settings_precedence,
    save_settings_profile,
)
from src.engine.target_size import (
    EDGE_RING_PX,
    ICON_DRAW_FRAC,
    ScaleInfo,
    apply_target_size,
    clamp_to_inset,
    edge_inset_norm,
    fit_icon_radius_px,
    radius_px_for,
    size_block,
    target_size_log_line,
)
from src.engine.task_runner import build_task, run_headless_replay
from src.inputs.base import Pointer
from src.tasks.scanning import scanning_layout_slots
from src.ui import canvas as canvas_module
from src.ui.canvas import TaskCanvas
from src.ui.settings_registry import (
    get_nested,
    initial_structural_values,
    structural_settings_for_task,
)
from src.ui.task_settings_dialog import TaskSettingsDialog

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
# The lab screen of SPEC S11.1: 0.2745 mm/px at 650 mm gives S 62.0, M 103.4, L 165.6 px.
LAB = ScaleInfo(0.2745, "edid", 527.0, 296.0)
HUD_SHOWN = (1640, 957)
HUD_HIDDEN = (1920, 957)
TASKS = ("click_grid", "click_static", "follow_moving", "scanning")


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


def _build(task_id, size="medium", canvas=HUD_SHOWN, recorder=None, mode="switch", seed=0, **overrides):
    """A task built the way the app builds it: the YAML, the size preset
    resolved into ``radius_px`` for the lab screen, then the canvas size set."""
    cfg = load_task_config(task_id)
    cfg["input"] = {"mode": mode}
    cfg["task"] = deep_merge(cfg["task"], overrides)
    block = size_block(cfg["task"])
    cfg["task"][block]["size"] = size
    apply_target_size(cfg["task"], LAB, 650.0, block=block)
    task = build_task(task_id, cfg, recorder=recorder, seed=seed)
    task.set_screen_size(*canvas)
    task.jitter_px = 40.0
    return task


def _pointer_on(task, target, dx_px=0.0, dy_px=0.0, clicked=False, elapsed_ns=0):
    """A pointer on the target's live position ``elapsed_ns`` into its trial."""
    cx_norm, cy_norm = task.target_position(target, elapsed_ns)
    cx, cy = cx_norm * task.screen_w, cy_norm * task.screen_h
    return Pointer(
        x=(cx + dx_px) / task.screen_w, y=(cy + dy_px) / task.screen_h, valid=True, clicked=clicked
    )


def _play(task, n_trials, step_ns=50_000_000, max_frames=40_000):
    """Finish n_trials in switch mode: the pointer follows the live target and
    clicks on every frame (a click outside the selection window is a miss, so a
    moving target is hit when its window opens)."""
    t = 0
    for _ in range(max_frames):
        if len(task.trials) >= n_trials:
            return t
        index = max(task._trial_index, 0)
        elapsed = max(t - task._trial_start_ns, 0) if task._trial_index >= 0 else 0
        task.update(t, _pointer_on(task, task.targets[index], clicked=True, elapsed_ns=elapsed))
        t += step_ns
    raise AssertionError(f"only {len(task.trials)} of {n_trials} trials finished")


# -- S11.4 item 1: dialog ----------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Rect:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


@pytest.fixture
def lab_screen(monkeypatch):
    """A 24 inch 1920x1080 monitor at 100 % with ~1000 px of usable height."""
    screen = SimpleNamespace(
        geometry=lambda: _Rect(1920, 1080),
        availableGeometry=lambda: _Rect(1920, 1000),
        devicePixelRatio=lambda: 1.0,
        physicalSize=lambda: _Rect(531.4, 298.9),
    )
    monkeypatch.setattr(TaskSettingsDialog, "screen", lambda self: screen)


def _dialog(task_id, **layout):
    config = load_task_config(task_id)
    if layout:
        config["task"]["layout"] = {**config["task"]["layout"], **layout}
    return TaskSettingsDialog(task_id, config)


@pytest.mark.parametrize("task_id", ["click_static", "follow_moving"])
def test_target_task_dialogs_show_a_size_combo_and_no_px_radius_row(qapp, task_id):
    d = _dialog(task_id)
    assert isinstance(d._controls["target.size"], QComboBox)
    assert d._controls["target.size"].currentData() == "medium"
    assert not any(key.endswith("radius_px") for key in d._controls)
    assert d.overrides()["target"] == {"size": "medium"}  # no radius_px in what the dialog returns


def test_scanning_dialog_shows_an_icon_size_combo_and_no_px_radius_row(qapp):
    d = _dialog("scanning")
    assert isinstance(d._controls["layout.size"], QComboBox)
    assert d._controls["layout.size"].currentData() == "medium"
    assert not any(key.endswith("radius_px") for key in d._controls)
    assert [s.label for s in structural_settings_for_task("scanning") if s.key == "layout.size"] == [
        "Icon size"
    ]
    assert d.overrides()["layout"] == {"size": "medium", "n_icons": 4}


def test_click_grid_dialog_is_unchanged(qapp):
    d = _dialog("click_grid")
    assert set(d._controls) == {"trials", "target.size", "grid.rows", "grid.cols"}


def test_size_items_of_every_task_show_degrees_and_the_diameter_on_this_monitor(qapp, lab_screen):
    for task_id, key in (("click_static", "target.size"), ("scanning", "layout.size")):
        dialog = _dialog(task_id)  # keep it alive: its widgets die with it
        combo = dialog._controls[key]
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "Small — 3° (≈123 px)",
            "Medium — 5° (≈205 px)",
            "Large — 8° (≈328 px)",
        ]


@pytest.mark.parametrize("task_id", ["click_static", "follow_moving"])
def test_click_static_and_follow_moving_never_show_a_shrink_hint(qapp, lab_screen, task_id):
    d = _dialog(task_id)
    combo = d._controls["target.size"]
    combo.setCurrentIndex(combo.findData("large"))
    assert d.fit_hint.isHidden()


def test_scanning_hint_appears_when_the_icons_will_be_shrunk_and_tracks_size_and_count(
    qapp, lab_screen
):
    d = _dialog("scanning")  # 4 icons, grid, Medium: fits
    assert d.fit_hint.isHidden()
    combo = d._controls["layout.size"]
    combo.setCurrentIndex(combo.findData("large"))
    assert not d.fit_hint.isHidden()  # Large 4-icon grid: cell 0.36 x 1000 px high
    d._controls["layout.n_icons"].setValue(8)
    assert d.fit_hint_label.text() == "Icons will be shrunk to ≈ 211 px to fit 8 icons (approximate)"
    combo.setCurrentIndex(combo.findData("small"))
    assert d.fit_hint.isHidden()  # Small fits everywhere
    combo.setCurrentIndex(combo.findData("medium"))
    assert d.fit_hint.isHidden()  # Medium (205 px) still fits 8 icons on ~1000 px (211)
    d._controls["layout.n_icons"].setValue(4)
    combo.setCurrentIndex(combo.findData("large"))
    d._controls["layout.n_icons"].setValue(2)
    assert d.fit_hint.isHidden()  # two icons: 0.5 x 0.36 x 1920 apart, room for Large


def test_scanning_hint_is_already_showing_for_a_starting_config_that_does_not_fit(qapp, lab_screen):
    config = load_task_config("scanning")
    config["task"]["layout"].update(size="large", n_icons=8)
    assert not TaskSettingsDialog("scanning", config).fit_hint.isHidden()


def test_scanning_hint_uses_the_yamls_arrangement(qapp, lab_screen):
    row = _dialog("scanning", arrangement="row", n_icons=8)
    assert not row.fit_hint.isHidden()  # row of 8: Medium does not fit
    assert "to fit 8 icons" in row.fit_hint_label.text()
    row_px = round(2 * fit_icon_radius_px(scanning_layout_slots(8, "row", 0.14), 1920, 1000))
    assert f"≈ {row_px} px" in row.fit_hint_label.text()  # the row's cap, not the grid's 211
    assert row_px < 211
    combo = row._controls["layout.size"]
    combo.setCurrentIndex(combo.findData("small"))
    assert row.fit_hint.isHidden()  # Small (123 px) fits a row of 8 (152 px)


LIVE = {"dwell.threshold_ms": 900}


@pytest.mark.parametrize(
    "task_id, key, choice",
    [
        ("click_static", "target.size", "large"),
        ("follow_moving", "target.size", "small"),
        ("scanning", "layout.size", "large"),
    ],
)
def test_size_choice_round_trips_through_a_settings_profile(qapp, tmp_path, task_id, key, choice):
    d = _dialog(task_id)
    combo = d._controls[key]
    combo.setCurrentIndex(combo.findData(choice))
    overrides = d.overrides()
    assert get_nested(overrides, key) == choice

    save_settings_profile(tmp_path, "S1", task_id, LIVE, overrides)
    resolved = resolve_settings_precedence(None, load_settings_profile(tmp_path, "S1", task_id))
    config = load_task_config(task_id)
    config["task"] = deep_merge(config["task"], resolved["structural_overrides"])
    assert initial_structural_values(task_id, config)[key] == choice
    dialog = TaskSettingsDialog(task_id, config)  # keep it alive: its widgets die with it
    assert dialog._controls[key].currentData() == choice


@pytest.mark.parametrize(
    "task_id, old_structural, key",
    [
        ("click_static", {"target": {"radius_px": 120}}, "target.size"),
        ("follow_moving", {"target": {"radius_px": 60}}, "target.size"),
        ("scanning", {"layout": {"radius_px": 120, "n_icons": 6}}, "layout.size"),
    ],
)
def test_an_older_profile_with_a_px_radius_still_loads_and_size_wins(
    qapp, tmp_path, task_id, old_structural, key
):
    save_settings_profile(tmp_path, "S1", task_id, LIVE, old_structural)
    resolved = resolve_settings_precedence(None, load_settings_profile(tmp_path, "S1", task_id))
    config = load_task_config(task_id)
    config["task"] = deep_merge(config["task"], resolved["structural_overrides"])
    dialog = TaskSettingsDialog(task_id, config)
    assert dialog._controls[key].currentData() == "medium"
    assert not any(k.endswith("radius_px") for k in dialog.overrides().get(key.split(".")[0], {}))
    # ...and the stale px value is overwritten by the size when the run resolves it.
    block = size_block(config["task"])
    apply_target_size(config["task"], LAB, 650.0, block=block)
    expected = radius_px_for("medium", LAB.mm_per_px, 650.0)
    if block == "layout":
        expected /= ICON_DRAW_FRAC
    assert config["task"][block]["radius_px"] == pytest.approx(expected, abs=0.1)


# -- S11.4 item 2: click_static ---------------------------------------------------------


def _inside_canvas(x_norm, y_norm, radius, canvas):
    w, h = canvas
    reach = radius + EDGE_RING_PX
    return (
        reach - 1e-6 <= x_norm * w <= w - reach + 1e-6
        and reach - 1e-6 <= y_norm * h <= h - reach + 1e-6
    )


def test_edge_inset_helpers():
    mx, my = edge_inset_norm(165.6, 1640, 957)
    assert mx == pytest.approx(185.6 / 1640)
    assert my == pytest.approx(185.6 / 957)
    assert clamp_to_inset(0.15, 0.1) == 0.15  # already inside: untouched
    assert clamp_to_inset(0.15, 0.2) == 0.2
    assert clamp_to_inset(0.9, 0.2) == pytest.approx(0.8)
    assert clamp_to_inset(0.3, 0.6) == 0.5  # canvas too small for the target: centred
    assert size_block({"task_id": "scanning"}) == "layout"
    assert size_block({"task_id": "click_static"}) == "target"
    assert size_block({}) == "target"


@pytest.mark.parametrize("canvas", [HUD_SHOWN, HUD_HIDDEN])
def test_click_static_large_keeps_every_target_and_ring_on_the_canvas(canvas):
    task = _build("click_static", "large", canvas=canvas)
    radius = task.targets[0].radius_px
    assert radius == pytest.approx(165.6, abs=0.1)
    for target in task.targets:
        x, y = task.target_position(target, 0)
        assert _inside_canvas(x, y, radius, canvas), (target.x_norm, target.y_norm, x, y)
        assert task.effective_radius_px(target) == radius  # the size is the same on every trial


def test_click_static_positions_that_already_fit_are_untouched():
    task = _build("click_static", "large", canvas=HUD_SHOWN)
    mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    for target in task.targets:
        x, y = task.target_position(target, 0)
        assert x == target.x_norm  # 0.15 / 0.5 / 0.85 all clear the 0.113 side margin
        if my <= target.y_norm <= 1 - my:
            assert y == target.y_norm
        else:  # the top / bottom rows move inward to ~0.19 / ~0.81 of the height
            assert y == pytest.approx(my if target.y_norm < 0.5 else 1 - my)
    # 0.15 -> ~0.194 of the height on the 957 px canvas (SPEC S11.2 B1 a)
    assert my == pytest.approx(0.194, abs=0.001)


def test_click_static_medium_is_identical_to_the_configured_positions():
    task = _build("click_static", "medium", canvas=HUD_SHOWN)
    assert task.targets[0].radius_px == pytest.approx(103.4, abs=0.1)
    for target in task.targets:
        assert task.target_position(target, 0) == (target.x_norm, target.y_norm)
        assert task.start_position(target) == (target.x_norm, target.y_norm)


def test_click_static_position_follows_the_live_canvas_size():
    task = _build("click_static", "large", canvas=HUD_SHOWN)
    top = next(t for t in task.targets if t.y_norm == 0.15)
    shown = task.target_position(top, 0)[1]
    task.set_screen_size(*HUD_HIDDEN)  # HUD toggle: same height, wider
    assert task.target_position(top, 0)[1] == pytest.approx(shown)
    task.set_screen_size(1640, 760)  # a shorter canvas pulls it further inward
    assert task.target_position(top, 0)[1] > shown
    assert _inside_canvas(*task.target_position(top, 0), top.radius_px, (1640, 760))


def test_click_static_hit_test_follows_the_moved_target():
    task = _build("click_static", "large", canvas=HUD_SHOWN)
    top = next(t for t in task.targets if t.y_norm == 0.15)
    task._trial_index = top.index - 1  # the next update starts exactly this trial
    result = task.update(0, _pointer_on(task, top))
    assert result.on_target is True  # gaze on the drawn (moved) target hits
    assert result.target_xy_norm == task.target_position(top, 0)
    # The hitbox is centred on the moved target: a point just inside its reach on the
    # far side from where the target was configured is on it (an unmoved hitbox would
    # miss it), and one just outside on the near side is not.
    reach = result.target_radius_px + task.jitter_px
    cx, cy = (v * s for v, s in zip(task.target_position(top, 0), HUD_SHOWN, strict=True))
    inside = Pointer(x=cx / 1640, y=(cy + reach - 5) / 957, valid=True, clicked=False)
    outside = Pointer(x=cx / 1640, y=(cy - reach - 5) / 957, valid=True, clicked=False)
    assert top.y_norm * 957 + reach < cy + reach - 5  # beyond the configured spot's reach
    assert task.update(10_000_000, inside).on_target is True
    assert task.update(20_000_000, outside).on_target is False


def test_click_static_trials_record_the_position_actually_used_and_one_inset_event():
    recorder = _FakeRecorder()
    task = _build("click_static", "large", canvas=HUD_SHOWN, recorder=recorder)
    _play(task, 8)
    mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    for trial, target in zip(task.trials, task.targets, strict=False):
        assert (trial.target_x, trial.target_y) == task.target_position(target, 0)
        assert _inside_canvas(trial.target_x, trial.target_y, trial.target_radius_px, HUD_SHOWN)
    assert any(t.target_y != target.y_norm for t, target in zip(task.trials, task.targets, strict=False))
    inset = recorder.of("TARGET_INSET")
    assert len(inset) == 1  # once per run, not per trial
    assert inset[0] == {
        "radius_px": pytest.approx(165.6, abs=0.1),
        "margin_x_norm": pytest.approx(mx, abs=1e-4),
        "margin_y_norm": pytest.approx(my, abs=1e-4),
        "canvas_w": 1640,
        "canvas_h": 957,
    }
    assert sum("moved inward" in line for line in recorder.lines) == 1
    assert recorder.of("TARGET_SHRUNK") == []  # click_static never shrinks


def test_no_inset_event_when_nothing_was_moved():
    recorder = _FakeRecorder()
    task = _build("click_static", "medium", canvas=HUD_SHOWN, recorder=recorder)
    _play(task, 8)
    assert recorder.of("TARGET_INSET") == []
    assert recorder.lines == []


def test_click_static_medium_run_is_identical_to_the_pre_phase_b_build_for_the_same_seed():
    # Same seed, same positions chosen; only the radius value differs (100 -> 103.4).
    old = load_task_config("click_static")
    old["task"]["target"].pop("size")
    old["task"]["target"]["radius_px"] = 100
    before = build_task("click_static", old, seed=3)
    now = _build("click_static", "medium", seed=3)
    assert [(t.x_norm, t.y_norm) for t in now.targets] == [(t.x_norm, t.y_norm) for t in before.targets]
    assert now.targets[0].radius_px == pytest.approx(103.4, abs=0.1)
    assert before.targets[0].radius_px == 100


# -- S11.4 item 3: follow_moving --------------------------------------------------------

PATHS = ("circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl")
STRAIGHT = PATHS[1:]


def _follow(path, size="large", canvas=HUD_SHOWN, speed=0.2, **kw):
    return _build(
        "follow_moving", size, canvas=canvas, motion={"path": path, "speed_frac_per_s": speed}, **kw
    )


@pytest.mark.parametrize("canvas", [HUD_SHOWN, HUD_HIDDEN])
@pytest.mark.parametrize("path", PATHS)
def test_follow_moving_large_stays_on_the_canvas_incl_ring(path, canvas):
    task = _follow(path, canvas=canvas)
    radius = task.targets[0].radius_px
    assert radius == pytest.approx(165.6, abs=0.1)
    for target in task.targets:
        for step in range(0, 4000):
            x, y = task.target_position(target, int(step * 0.005 * 1e9))
            assert _inside_canvas(x, y, radius, canvas), (path, step, x, y)


@pytest.mark.parametrize("canvas", [HUD_SHOWN, HUD_HIDDEN])
def test_follow_moving_straight_paths_keep_equal_px_per_second(canvas):
    expected = 0.2 * canvas[0]  # speed_frac_per_s is a fraction of canvas WIDTH
    for path in STRAIGHT:
        task = _follow(path, canvas=canvas)
        for t in (0.3, 1.0, 1.5):
            x0, y0 = task.target_position(task.targets[0], int(t * 1e9))
            x1, y1 = task.target_position(task.targets[0], int((t + 1e-3) * 1e9))
            speed = math.hypot((x1 - x0) * canvas[0], (y1 - y0) * canvas[1]) / 1e-3
            assert speed == pytest.approx(expected, rel=0.01), (path, t)


def test_follow_moving_vertical_bounces_at_the_inset_ends():
    task = _follow("vertical", canvas=HUD_SHOWN)
    _mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    leg = (1 - 2 * my) / (0.2 * HUD_SHOWN[0] / HUD_SHOWN[1])
    at = lambda s: task.target_position(task.targets[0], int(s * 1e9))  # noqa: E731
    assert at(0.0)[1] == pytest.approx(my)
    assert at(leg)[1] == pytest.approx(1 - my)
    assert at(2 * leg)[1] == pytest.approx(my)
    assert at(1.5 * leg)[1] == pytest.approx(0.5)  # on the way back up


def test_follow_moving_diagonals_run_between_the_inset_corners():
    task = _follow("diagonal_trbl", canvas=HUD_SHOWN)
    mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    leg = math.hypot((1 - 2 * mx) * HUD_SHOWN[0], (1 - 2 * my) * HUD_SHOWN[1]) / (0.2 * HUD_SHOWN[0])
    at = lambda s: task.target_position(task.targets[0], int(s * 1e9))  # noqa: E731
    assert at(0.0) == pytest.approx((1 - mx, my))
    assert at(leg) == pytest.approx((mx, 1 - my))
    assert at(2 * leg) == pytest.approx((1 - mx, my))


def test_follow_moving_circular_is_flattened_on_a_short_canvas_not_cut_off():
    task = _follow("circular", canvas=(1000, 700))
    ys = [task.target_position(task.targets[0], int(s * 0.01 * 1e9))[1] for s in range(0, 600)]
    my = edge_inset_norm(task.targets[0].radius_px, 1000, 700)[1]
    assert my > 0.2  # the 0.3-radius orbit would leave the canvas
    assert min(ys) == pytest.approx(my) and max(ys) == pytest.approx(1 - my)


def _old_horizontal_x(speed, elapsed_ns):
    """The pre-Phase-B code, verbatim."""
    elapsed_s = elapsed_ns / 1e9
    span = 0.8
    raw = 0.1 + (speed * elapsed_s) % (2 * span)
    return raw if raw <= 0.9 else (1.8 - raw)


def test_follow_moving_medium_horizontal_is_numerically_identical_to_today():
    task = _follow("horizontal", size="medium", canvas=HUD_SHOWN)
    assert task.targets[0].radius_px == pytest.approx(103.4, abs=0.1)
    for target in task.targets:
        for elapsed_ns in range(0, 20_000_000_000, 137_000_000):
            assert task.target_position(target, elapsed_ns) == (
                _old_horizontal_x(0.2, elapsed_ns),
                target.y_norm,
            )


def test_follow_moving_trials_record_the_start_position_actually_used():
    recorder = _FakeRecorder()
    task = _follow("vertical", recorder=recorder, canvas=HUD_SHOWN)
    _play(task, 3)
    _mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    for trial, target in zip(task.trials, task.targets, strict=False):
        assert trial.target_y == pytest.approx(my)  # the inset end, not the nominal 0.1
        assert trial.target_x == pytest.approx(target.x_norm)  # lane already inside
    assert len(recorder.of("TARGET_INSET")) == 1
    assert recorder.of("TARGET_INSET")[0]["canvas_h"] == 957
    assert sum("moved inward" in line for line in recorder.lines) == 1


@pytest.mark.parametrize("path", STRAIGHT)
def test_follow_moving_medium_only_reports_an_inset_where_the_path_actually_moved(path):
    # Medium on the 957 px canvas needs 0.128 of the height: the vertical ends and the
    # diagonals' y ends move in; horizontal (x needs 0.075, lane inside) does not.
    recorder = _FakeRecorder()
    task = _follow(path, size="medium", recorder=recorder, canvas=HUD_SHOWN)
    _play(task, 2)
    assert len(recorder.of("TARGET_INSET")) == (0 if path == "horizontal" else 1)


def test_follow_moving_circular_keeps_its_recorded_start_value():
    task = _follow("circular", size="medium")
    _play(task, 1)
    assert (task.trials[0].target_x, task.trials[0].target_y) == (
        task.targets[0].x_norm,
        task.targets[0].y_norm,
    )


# -- S11.4 item 4: scanning ---------------------------------------------------------------

TABLE = {  # SPEC S11.1: largest drawn icon radius (px), canvas 1640x957
    "grid": {2: 260, 4: 152, 6: 152, 8: 101},
    "row": {2: 260, 4: 130, 6: 87, 8: 65},
    "ring": {2: 152, 4: 152, 6: 135, 8: 117},
}
SCAN_CASES = [(a, n) for a in TABLE for n in TABLE[a]]


def _scan(n_icons, arrangement, size="large", canvas=HUD_SHOWN, recorder=None, mode="switch"):
    return _build(
        "scanning",
        size,
        canvas=canvas,
        recorder=recorder,
        mode=mode,
        layout={"n_icons": n_icons, "arrangement": arrangement},
    )


@pytest.mark.parametrize("arrangement, n_icons", SCAN_CASES)
def test_scanning_cap_matches_the_spec_table(arrangement, n_icons):
    task = _scan(n_icons, arrangement)
    icon = task.effective_radius_px(task.targets[0]) * ICON_DRAW_FRAC
    expected = TABLE[arrangement][n_icons]
    wanted = radius_px_for("large", LAB.mm_per_px, 650.0)
    assert icon == pytest.approx(min(expected, wanted), abs=1.0)


@pytest.mark.parametrize("size", ["small", "medium", "large"])
@pytest.mark.parametrize("canvas", [HUD_SHOWN, HUD_HIDDEN])
@pytest.mark.parametrize("arrangement, n_icons", SCAN_CASES)
def test_scanning_icons_never_overlap_or_cross_the_canvas_edge(arrangement, n_icons, canvas, size):
    task = _scan(n_icons, arrangement, size=size, canvas=canvas)
    drawn = task.effective_radius_px(task.targets[0]) * ICON_DRAW_FRAC  # what the canvas draws
    w, h = canvas
    pts = [(x * w, y * h) for x, y in task.icon_slots]
    for (x0, y0), (x1, y1) in itertools.combinations(pts, 2):
        assert math.hypot(x1 - x0, y1 - y0) >= 2 * drawn - 1e-6
    for x, y in pts:
        assert min(x, w - x, y, h - y) >= drawn + EDGE_RING_PX - 1e-6


def test_scanning_hit_test_ignores_a_look_at_a_neighbouring_icon():
    task = _scan(4, "grid", size="large")  # 2x2, slots 590 px apart across, 344 down
    target = task.targets[0]
    reach = task.effective_radius_px(target) + task.jitter_px
    cx, cy = target.x_norm * task.screen_w, target.y_norm * task.screen_h
    below = task.icon_slots[(target.slot_index + 2) % 4]  # the slot under / over it
    # a point between the two icons, nearer the neighbour yet still inside the target's circle
    dy = 175.0 if below[1] > target.y_norm else -175.0
    assert abs(dy) < reach
    px, py = cx, cy + dy
    assert math.hypot(px - below[0] * task.screen_w, py - below[1] * task.screen_h) < abs(dy)
    assert task.hit_test(target, cx, cy, px, py) is False
    # nearer its own slot: on target
    assert task.hit_test(target, cx, cy, cx, cy + dy / 4) is True
    # outside radius + jitter: not on target
    assert task.hit_test(target, cx, cy, cx + reach + 5, cy) is False


@pytest.mark.parametrize("arrangement", ["grid", "row", "ring"])
def test_scanning_nearest_slot_rule_holds_in_every_arrangement(arrangement):
    task = _scan(6, arrangement, size="large")
    w, h = task.screen_w, task.screen_h
    slots_px = [(x * w, y * h) for x, y in task.icon_slots]
    for target in task.targets[:3]:
        cx, cy = slots_px[target.slot_index]
        for k, (ox, oy) in enumerate(slots_px):
            if k == target.slot_index:
                continue
            # 60 % of the way to a neighbour: past the bisector, so not on target
            px, py = cx + 0.6 * (ox - cx), cy + 0.6 * (oy - cy)
            assert task.hit_test(target, cx, cy, px, py) is False
            # 30 % of the way: on target exactly when inside the hitbox and its own
            # slot is still the nearest one
            px, py = cx + 0.3 * (ox - cx), cy + 0.3 * (oy - cy)
            inside = math.hypot(px - cx, py - cy) <= task.effective_radius_px(target) + task.jitter_px
            nearest = min(range(len(slots_px)), key=lambda m: math.hypot(px - slots_px[m][0], py - slots_px[m][1]))
            assert task.hit_test(target, cx, cy, px, py) is (inside and nearest == target.slot_index)


def test_scanning_pointer_through_update_uses_the_nearest_slot_rule():
    task = _scan(4, "grid", size="large")
    target = task.targets[0]
    neighbour_y = task.icon_slots[(target.slot_index + 2) % 4][1]  # same column, other row
    dy = 175.0 if neighbour_y > target.y_norm else -175.0  # 175 px of the 344 px between them
    assert task.update(0, _pointer_on(task, target, dy_px=dy)).on_target is False
    assert task.update(10_000_000, _pointer_on(task, target)).on_target is True


def test_scanning_reports_one_shrink_event_when_capped_and_none_when_not():
    recorder = _FakeRecorder()
    task = _scan(8, "grid", size="large", recorder=recorder)
    _play(task, 3)
    shrunk = recorder.of("TARGET_SHRUNK")
    assert len(shrunk) == 1
    assert (shrunk[0]["n_icons"], shrunk[0]["arrangement"]) == (8, "grid")
    assert shrunk[0]["used_px"] < shrunk[0]["requested_px"]
    assert shrunk[0]["used_px"] == pytest.approx(task.trials[0].target_radius_px, abs=0.1)

    recorder = _FakeRecorder()
    task = _scan(4, "grid", size="medium", recorder=recorder)
    _play(task, 3)
    assert recorder.of("TARGET_SHRUNK") == []
    assert task.trials[0].target_radius_px == pytest.approx(task.targets[0].radius_px)


def test_scanning_cap_follows_the_live_canvas_size():
    task = _scan(8, "grid", size="large", canvas=HUD_HIDDEN)
    before = task.effective_radius_px(task.targets[0])
    task.set_screen_size(1640, 700)  # shorter canvas: smaller cells
    assert task.effective_radius_px(task.targets[0]) < before


# -- S11.4 item 5: scanning Medium is the visible icon ---------------------------------------


def test_scanning_medium_draws_the_icon_at_the_preset_radius():
    task = _build("scanning", "medium", layout={"n_icons": 4, "arrangement": "grid"})
    hit_radius = task.targets[0].radius_px
    assert hit_radius == pytest.approx(103.4 / ICON_DRAW_FRAC, abs=0.1)
    assert task.effective_radius_px(task.targets[0]) == hit_radius  # 4 icons: no cap
    assert hit_radius * ICON_DRAW_FRAC == pytest.approx(103.4, abs=0.1)


def test_scanning_metadata_block_and_log_line_say_icon():
    cfg = load_task_config("scanning")
    info = apply_target_size(cfg["task"], LAB, 650.0, block="layout")
    assert info["radius_px"] == pytest.approx(103.4, abs=0.1)  # the drawn icon's radius
    assert info["radius_of"] == "icon"
    assert set(info) == {
        "preset", "diameter_deg", "radius_px", "mm_per_px", "mm_per_px_source",
        "viewing_distance_mm", "radius_of",
    }
    assert cfg["task"]["layout"]["radius_px"] == pytest.approx(103.4 / ICON_DRAW_FRAC, abs=0.1)
    assert target_size_log_line(info, LAB).startswith("Icon size: Medium (5.0°) = 103 px radius")
    other = apply_target_size(load_task_config("click_static")["task"], LAB, 650.0)
    assert "radius_of" not in other
    assert target_size_log_line(other, LAB).startswith("Target size: ")


def test_the_canvas_draws_the_scanning_icon_at_the_shared_fraction_of_the_hit_radius(qapp):
    assert canvas_module.ICON_DRAW_FRAC is ICON_DRAW_FRAC
    assert "* 0.78" not in Path(canvas_module.__file__).read_text(encoding="utf-8")
    canvas = TaskCanvas(theme={"background": "#000000", "cursor_color": "#ffffff"})
    canvas.resize(800, 600)
    canvas.show_cursor = False
    hit_radius = 103.4 / ICON_DRAW_FRAC
    canvas.set_frame(
        None, hit_radius, (0.5, 0.5), True, 0.0,
        scene={"mode": "icons", "slots": [(0.5, 0.5)], "shapes": [0]},  # one circle icon
    )
    image: QImage = canvas.grab().toImage()
    lit = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if QColor(image.pixel(x, y)).red() > 20
    ]
    width = max(x for x, _y in lit) - min(x for x, _y in lit) + 1
    assert width == pytest.approx(2 * 103.4, abs=3.0)  # drawn radius 103.4, not the hit radius


# -- S11.4 item 6: old configs and the size-wins rule ---------------------------------------


@pytest.mark.parametrize("task_id", ["click_static", "follow_moving", "scanning"])
def test_a_config_with_only_a_px_radius_is_used_unchanged(task_id):
    block = "layout" if task_id == "scanning" else "target"
    cfg = load_task_config(task_id)
    del cfg["task"][block]["size"]
    cfg["task"][block]["radius_px"] = 70
    assert apply_target_size(cfg["task"], LAB, 650.0, block=size_block(cfg["task"])) is None
    assert cfg["task"][block]["radius_px"] == 70
    assert build_task(task_id, cfg).targets[0].radius_px == 70


def test_scanning_with_a_legacy_radius_is_still_capped_to_fit():
    cfg = load_task_config("scanning")
    del cfg["task"]["layout"]["size"]
    cfg["task"]["layout"].update(radius_px=200, n_icons=8)
    task = build_task("scanning", cfg)
    task.set_screen_size(*HUD_SHOWN)
    assert task.effective_radius_px(task.targets[0]) < 200  # hit radius 200 -> icon 156 > cap 101


@pytest.mark.parametrize(
    "task_id, block", [("click_static", "target"), ("follow_moving", "target"), ("scanning", "layout")]
)
def test_size_wins_over_a_stale_radius_when_both_are_present(task_id, block):
    cfg = load_task_config(task_id)
    cfg["task"][block].update(size="large", radius_px=10)
    info = apply_target_size(cfg["task"], LAB, 650.0, block=block)
    assert info["preset"] == "large"
    want = radius_px_for("large", LAB.mm_per_px, 650.0) / (ICON_DRAW_FRAC if block == "layout" else 1)
    assert cfg["task"][block]["radius_px"] == pytest.approx(want, abs=0.1)


def test_the_yamls_carry_a_size_and_no_px_radius():
    for task_id in ("click_static", "follow_moving", "click_grid"):
        target = load_task_config(task_id)["task"]["target"]
        assert target["size"] == "medium" and "radius_px" not in target
    layout = load_task_config("scanning")["task"]["layout"]
    assert layout["size"] == "medium" and "radius_px" not in layout


def _fake_app(task_cfg):
    screen = SimpleNamespace(
        geometry=lambda: SimpleNamespace(width=lambda: 1920),
        devicePixelRatio=lambda: 1.0,
        physicalSize=lambda: SimpleNamespace(width=lambda: 527.0, height=lambda: 296.0),
    )
    return SimpleNamespace(
        config={"app": {"viewing_distance_mm": 650}, "task": task_cfg},
        canvas=SimpleNamespace(screen=lambda: screen),
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        recorder=_FakeRecorder(),
    )


def test_app_resolves_a_scanning_icon_size_from_layout_size():
    app = _fake_app({"task_id": "scanning", "layout": {"size": "medium", "radius_px": 5}})
    AssessmentApp._resolve_target_size(app)
    assert app.config["task"]["layout"]["radius_px"] == pytest.approx(103.4 / ICON_DRAW_FRAC, abs=0.1)
    assert app.metadata.target_size["radius_of"] == "icon"
    assert app.recorder.lines[0].startswith("Icon size: Medium (5.0°) = 103 px radius (EDID 527x296 mm")


def test_app_logs_an_unknown_icon_size_by_that_name():
    app = _fake_app({"task_id": "scanning", "layout": {"size": "huge"}})
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.target_size["preset"] == "medium"
    assert "Unknown icon size 'huge'" in app.recorder.lines[0]


# -- S11.4 item 7: metadata + recorded positions, end to end ------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_headless_replay_records_target_size_metadata_for_all_four_tasks(tmp_path, task_id):
    result = run_headless_replay(task_id, FIXTURE, output_root=tmp_path, max_seconds=40.0)
    session = Path(result["session_dir"])
    info = json.loads((session / "metadata.json").read_text(encoding="utf-8"))["target_size"]
    assert info["preset"] == "medium" and info["diameter_deg"] == 5.0
    assert info["radius_px"] == pytest.approx(102.5, abs=1.0)  # reference monitor, headless
    assert ("radius_of" in info) == (task_id == "scanning")
    log = (session / "session.log").read_text(encoding="utf-8")
    assert ("Icon size: Medium" if task_id == "scanning" else "Target size: Medium") in log


def test_a_real_session_records_the_clamped_positions_and_one_inset_event(tmp_path):
    meta = SessionMetadata(subject_id="P001", session_id="s", started_ns=0)
    with SessionRecorder(meta, output_root=tmp_path) as recorder:
        task = _build("click_static", "large", canvas=HUD_SHOWN, recorder=recorder)
        _play(task, 10)
        recorder.write_trials(task.trials)

    session = tmp_path / "s"
    with (session / "trials.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    _mx, my = edge_inset_norm(task.targets[0].radius_px, *HUD_SHOWN)
    ys = {round(float(r["target_y"]), 4) for r in rows}
    assert ys <= {round(my, 4), 0.5, round(1 - my, 4)}  # 0.15 / 0.85 became the inset rows
    assert round(my, 4) in ys or round(1 - my, 4) in ys
    assert {float(r["target_radius_px"]) for r in rows} == {task.targets[0].radius_px}
    events = [json.loads(line) for line in (session / "events.jsonl").read_text("utf-8").splitlines()]
    assert [e["kind"] for e in events].count("TARGET_INSET") == 1
    log = (session / "session.log").read_text(encoding="utf-8")
    assert len(re.findall("moved inward", log)) == 1
