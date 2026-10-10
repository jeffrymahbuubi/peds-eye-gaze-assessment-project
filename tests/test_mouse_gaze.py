"""SPEC-compass-task-flow.md 4B.6 / plan step B6: ``MouseGazeSource``, the gaze
source that lets Preview Test run on the mouse alone."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from src.data.schema import GazeSample
from src.engine.clock import now_ns
from src.inputs.eye_input import EyeInput, SmoothingConfig
from src.inputs.mouse_gaze import MouseGazeSource


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Pointing:
    """A stand-in for ``QCursor.pos``: the global position the test says the mouse is at."""

    def __init__(self) -> None:
        self.pos = QPoint(0, 0)

    def __call__(self) -> QPoint:
        return self.pos

    def at_canvas(self, canvas: QWidget, x: int, y: int) -> None:
        self.pos = canvas.mapToGlobal(QPoint(x, y))


@pytest.fixture
def canvas(qapp):
    widget = QWidget()
    widget.resize(400, 200)
    widget.move(30, 40)
    yield widget
    widget.deleteLater()


@pytest.fixture
def mouse():
    return Pointing()


@pytest.fixture
def source(canvas, mouse):
    src = MouseGazeSource(cursor_pos=mouse)
    src.bind_canvas(canvas)
    return src


# -- before binding ----------------------------------------------------------


def test_latest_is_none_until_a_canvas_is_bound(mouse):
    src = MouseGazeSource(cursor_pos=mouse)
    assert src.latest() is None


def test_bind_canvas_makes_samples_appear(canvas, mouse):
    src = MouseGazeSource(cursor_pos=mouse)
    mouse.at_canvas(canvas, 100, 50)
    assert src.latest() is None
    src.bind_canvas(canvas)
    assert isinstance(src.latest(), GazeSample)


def test_binding_another_canvas_moves_the_source(qapp, canvas, mouse, source):
    other = QWidget()
    other.resize(100, 100)
    other.move(900, 900)
    mouse.at_canvas(other, 50, 25)
    assert source.latest().valid is False  # the mouse is on the other widget
    source.bind_canvas(other)
    sample = source.latest()
    assert sample.valid is True and (sample.x, sample.y) == (0.5, 0.25)
    other.deleteLater()


# -- the contract (valid inside, invalid outside, normalisation) --------------


def test_inside_the_canvas_is_valid_and_normalised_to_it(canvas, mouse, source):
    mouse.at_canvas(canvas, 100, 50)
    sample = source.latest()
    assert sample.valid is True
    assert (sample.x, sample.y) == (0.25, 0.25)  # 100/400, 50/200
    assert sample.fixation_id is None and sample.fix_duration_s is None
    assert sample.pupil_left is None and sample.pupil_right is None


@pytest.mark.parametrize(
    "x,y,expected",
    [(0, 0, (0.0, 0.0)), (200, 100, (0.5, 0.5)), (399, 199, (399 / 400, 199 / 200)), (40, 160, (0.1, 0.8))],
)
def test_normalisation_over_the_whole_canvas(canvas, mouse, source, x, y, expected):
    mouse.at_canvas(canvas, x, y)
    sample = source.latest()
    assert sample.valid is True
    assert (sample.x, sample.y) == pytest.approx(expected)


@pytest.mark.parametrize(
    "x,y",
    [(-1, 50), (400, 50), (100, -1), (100, 200), (-50, -50), (900, 900)],
)
def test_outside_the_canvas_is_invalid(canvas, mouse, source, x, y):
    mouse.at_canvas(canvas, x, y)
    sample = source.latest()
    assert sample.valid is False
    # Still reports where the mouse is, relative to the canvas.
    assert (sample.x, sample.y) == pytest.approx((x / 400, y / 200))


def test_normalisation_follows_the_canvas_size(canvas, mouse, source):
    mouse.at_canvas(canvas, 100, 50)
    assert source.latest().x == 0.25
    canvas.resize(800, 400)
    mouse.at_canvas(canvas, 100, 50)
    assert (source.latest().x, source.latest().y) == (0.125, 0.125)


def test_a_canvas_with_no_size_gives_no_sample(mouse):
    src = MouseGazeSource(cursor_pos=mouse)
    src.bind_canvas(SimpleNamespace(width=lambda: 0, height=lambda: 0, mapFromGlobal=lambda p: p))
    assert src.latest() is None


def test_the_sample_is_stamped_with_the_in_run_clock(canvas, mouse, source):
    # The clock every run duration is measured on (SPEC-audit-fixes.md H9), not the wall clock.
    mouse.at_canvas(canvas, 10, 10)
    before = now_ns()
    t_ns = source.latest().t_ns
    assert before <= t_ns <= now_ns()


def test_the_default_cursor_is_the_real_one(canvas, qapp):
    """No injected position: it reads QCursor.pos(), which never raises and gives a
    sample for a bound canvas (valid or not depending on where the pointer is)."""
    src = MouseGazeSource()
    src.bind_canvas(canvas)
    assert isinstance(src.latest(), GazeSample)


# -- the rest of the gaze-source surface -------------------------------------


def test_it_looks_like_a_connected_non_live_device():
    src = MouseGazeSource()
    assert src.is_connected() is True
    assert src.device_info is None
    assert src.is_live is False


def test_the_device_calls_are_no_ops():
    src = MouseGazeSource()
    assert src.connect() is None
    assert src.connect(host="10.0.0.1", port=4250) is None
    assert src.start_streaming() is None
    assert src.clear_raw() is None
    assert src.stop() is None
    assert src.drain_raw() == []
    assert src.is_connected() is True  # still, after stop


# -- with EyeInput -----------------------------------------------------------


def test_eye_input_follows_the_mouse_and_freezes_when_it_leaves(canvas, mouse, source):
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=False))
    mouse.at_canvas(canvas, 100, 50)
    pointer = eye.poll(0)
    assert pointer.valid is True and (pointer.x, pointer.y) == (0.25, 0.25)

    mouse.at_canvas(canvas, 120, 100)
    pointer = eye.poll(1)
    assert pointer.valid is True and (pointer.x, pointer.y) == (0.3, 0.5)

    mouse.at_canvas(canvas, 900, 900)  # off the canvas: dropout behaviour
    pointer = eye.poll(2)
    assert pointer.valid is False and (pointer.x, pointer.y) == (0.3, 0.5)  # frozen in place

    mouse.at_canvas(canvas, 300, 150)
    pointer = eye.poll(3)
    assert pointer.valid is True and (pointer.x, pointer.y) == (0.75, 0.75)


def test_eye_input_before_binding_is_the_neutral_invalid_centre(mouse):
    eye = EyeInput(MouseGazeSource(cursor_pos=mouse))
    pointer = eye.poll(0)
    assert pointer.valid is False and (pointer.x, pointer.y) == (0.5, 0.5)
