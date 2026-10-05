"""SPEC-target-size-and-motion-paths.md Phase C: follow_moving's straight paths
(horizontal, vertical, two corner diagonals) as bouncing triangle waves at one
shared on-screen speed. Acceptance criterion 6.7."""

from __future__ import annotations

import math
import random

import pytest

from src.engine.config import load_task_config
from src.engine.task_runner import build_task

PATHS = ("circular", "horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl")
STRAIGHT = ("horizontal", "vertical", "diagonal_tlbr", "diagonal_trbl")


class _FakeRecorder:
    def __init__(self):
        self.events = []
        self.lines = []

    def record_event(self, kind, t_ns, **payload):
        self.events.append((kind, t_ns, payload))

    def log(self, message):
        self.lines.append(message)


def _task(path, canvas=(1500, 1000), speed=0.2, recorder=None, seed=0):
    cfg = load_task_config("follow_moving")
    cfg["task"]["motion"]["path"] = path
    cfg["task"]["motion"]["speed_frac_per_s"] = speed
    task = build_task("follow_moving", cfg, recorder=recorder, seed=seed)
    task.set_screen_size(*canvas)
    return task


def _at(task, seconds, index=0):
    return task.target_position(task.targets[index], int(seconds * 1e9))


def _px_speed(task, t, dt=1e-3):
    """On-screen speed in px/s of the live target at second ``t``."""
    x0, y0 = _at(task, t)
    x1, y1 = _at(task, t + dt)
    return math.hypot((x1 - x0) * task.screen_w, (y1 - y0) * task.screen_h) / dt


# -- stays inside [0.1, 0.9] -----------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("canvas", [(1500, 1000), (1920, 1003), (1640, 1003)])
def test_every_path_stays_within_the_inner_80_percent(path, canvas):
    task = _task(path, canvas=canvas)
    for index in range(len(task.targets)):
        for step in range(0, 6000):
            x, y = _at(task, step * 0.005, index)
            assert 0.1 - 1e-9 <= x <= 0.9 + 1e-9, (path, step, x)
            assert 0.1 - 1e-9 <= y <= 0.9 + 1e-9, (path, step, y)


# -- start points -------------------------------------------------------------------


def test_start_points_are_recorded_as_the_trial_target_x_y():
    for index in range(6):
        horizontal = _task("horizontal").targets[index]
        assert horizontal.x_norm == 0.1 and 0.25 <= horizontal.y_norm <= 0.75
        vertical = _task("vertical").targets[index]
        assert vertical.y_norm == 0.1 and 0.25 <= vertical.x_norm <= 0.75
        tlbr = _task("diagonal_tlbr").targets[index]
        assert (tlbr.x_norm, tlbr.y_norm) == (0.1, 0.1)
        trbl = _task("diagonal_trbl").targets[index]
        assert (trbl.x_norm, trbl.y_norm) == (0.9, 0.1)


@pytest.mark.parametrize("path", STRAIGHT)
def test_motion_starts_at_the_recorded_start_point(path):
    task = _task(path)
    for index, target in enumerate(task.targets):
        x, y = _at(task, 0.0, index)
        assert (x, y) == pytest.approx((target.x_norm, target.y_norm))


# -- bounce ---------------------------------------------------------------------------


def test_vertical_travels_down_bounces_and_returns_to_the_top():
    task = _task("vertical", canvas=(1500, 1000), speed=0.2)
    norm_speed = 0.2 * 1500 / 1000  # canvas heights per second
    leg = 0.8 / norm_speed
    assert _at(task, leg)[1] == pytest.approx(0.9)
    assert _at(task, leg * 1.5)[1] == pytest.approx(0.5)  # on the way back up
    assert _at(task, 2 * leg)[1] == pytest.approx(0.1)
    assert _at(task, 3 * leg)[1] == pytest.approx(0.9)  # and down again
    x_values = {round(_at(task, leg * k / 7)[0], 12) for k in range(30)}
    assert x_values == {round(task.targets[0].x_norm, 12)}  # x never moves


@pytest.mark.parametrize(
    "path, start, end",
    [("diagonal_tlbr", (0.1, 0.1), (0.9, 0.9)), ("diagonal_trbl", (0.9, 0.1), (0.1, 0.9))],
)
def test_diagonals_run_corner_to_corner_and_bounce_back(path, start, end):
    task = _task(path, canvas=(1500, 1000), speed=0.2)
    length_px = 0.8 * math.hypot(1500, 1000)
    leg = length_px / (0.2 * 1500)
    assert _at(task, 0.0) == pytest.approx(start)
    assert _at(task, leg) == pytest.approx(end)
    assert _at(task, 2 * leg) == pytest.approx(start)
    midway = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    assert _at(task, leg / 2) == pytest.approx(midway)
    assert _at(task, leg * 1.5) == pytest.approx(midway)


def test_diagonal_angle_follows_the_canvas_aspect_ratio():
    task = _task("diagonal_tlbr", canvas=(1920, 1003))
    x, y = _at(task, 1.0)
    angle = math.degrees(math.atan2((y - 0.1) * 1003, (x - 0.1) * 1920))
    assert angle == pytest.approx(math.degrees(math.atan2(1003, 1920)), abs=0.01)
    assert 27 < angle < 29  # roughly 28 degrees from horizontal on a 16:9 canvas


# -- horizontal is unchanged ------------------------------------------------------------


def _old_targets(seed, n_trials, timeout_ns, window_ns):
    """The pre-change build_targets draw order: y, then the window start."""
    rng = random.Random(seed)
    latest_start = max(0, timeout_ns - window_ns)
    out = []
    for _ in range(n_trials):
        y = rng.uniform(0.25, 0.75)
        start = rng.randint(int(0.15 * timeout_ns), latest_start) if latest_start > 0 else 0
        out.append((y, (start, start + window_ns)))
    return out


def _old_horizontal_x(speed, elapsed_ns):
    elapsed_s = elapsed_ns / 1e9
    span = 0.8
    raw = 0.1 + (speed * elapsed_s) % (2 * span)
    return raw if raw <= 0.9 else (1.8 - raw)


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_horizontal_is_numerically_identical_to_the_old_code_for_the_same_seed(seed):
    task = _task("horizontal", seed=seed)
    old = _old_targets(seed, len(task.targets), task.timeout_ns, task.select_window_ns)
    for target, (y, window) in zip(task.targets, old, strict=True):
        assert (target.x_norm, target.y_norm) == (0.1, y)
        assert task.select_windows[target.index] == window
        for elapsed_ns in range(0, 20_000_000_000, 137_000_000):
            assert task.target_position(target, elapsed_ns) == (
                _old_horizontal_x(task.speed, elapsed_ns),
                y,
            )


@pytest.mark.parametrize("path", PATHS)
def test_every_path_draws_the_same_selection_windows_for_one_seed(path):
    task = _task(path, seed=7)
    old = _old_targets(7, len(task.targets), task.timeout_ns, task.select_window_ns)
    assert task.select_windows == [window for _y, window in old]


def test_circular_is_unchanged():
    task = _task("circular", speed=0.2)
    target = task.targets[0]
    for seconds in (0.0, 0.7, 2.3, 9.9):
        omega = 2 * math.pi * 0.2
        expected = (0.5 + 0.3 * math.cos(omega * seconds), 0.5 + 0.3 * math.sin(omega * seconds))
        assert task.target_position(target, int(seconds * 1e9)) == expected
    assert (target.x_norm, target.y_norm) == (0.1, _old_targets(0, 1, task.timeout_ns, task.select_window_ns)[0][0])


# -- equal on-screen speed ------------------------------------------------------------------


@pytest.mark.parametrize("canvas", [(1500, 1000), (1920, 1003), (1640, 1003)])
@pytest.mark.parametrize("speed", [0.1, 0.2])
def test_all_straight_paths_move_at_the_same_px_per_second(canvas, speed):
    expected = speed * canvas[0]  # speed_frac_per_s is a fraction of canvas WIDTH
    # Instants within the first leg of every path at the default speed, plus one
    # on a return leg of the vertical path.
    for path in STRAIGHT:
        task = _task(path, canvas=canvas, speed=speed)
        for t in (0.3, 1.0, 2.0 / (speed / 0.2)):
            assert _px_speed(task, t) == pytest.approx(expected, rel=0.01), (path, t)


def test_speed_is_independent_of_the_path_across_a_bounce():
    # Vertical bounces first (shortest leg); its speed on the way back is the same.
    task = _task("vertical", canvas=(1500, 1000), speed=0.2)
    leg = 0.8 / (0.2 * 1500 / 1000)
    assert _px_speed(task, leg + 0.4) == pytest.approx(0.2 * 1500, rel=0.01)


# -- unknown path ----------------------------------------------------------------------------


def test_unknown_path_falls_back_to_horizontal_and_is_logged():
    recorder = _FakeRecorder()
    task = _task("spiral", recorder=recorder)
    assert task.path == "horizontal"
    assert task.scene_spec()["path"] == "horizontal"
    assert any("spiral" in line for line in recorder.lines)
    y = task.targets[0].y_norm
    assert _at(task, 1.0)[1] == y  # behaves as horizontal


def test_missing_path_key_is_horizontal_without_a_warning():
    recorder = _FakeRecorder()
    cfg = load_task_config("follow_moving")
    del cfg["task"]["motion"]["path"]
    task = build_task("follow_moving", cfg, recorder=recorder)
    assert task.path == "horizontal"
    assert recorder.lines == []


@pytest.mark.parametrize("path", PATHS)
def test_known_paths_are_not_logged_as_unknown(path):
    recorder = _FakeRecorder()
    assert _task(path, recorder=recorder).path == path
    assert recorder.lines == []
