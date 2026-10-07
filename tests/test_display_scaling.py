"""SPEC-display-scaling-cursor-accuracy.md S8.4: cursor/hit-testing must be
exact at any Windows display scale, using Qt logical geometry throughout."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.app import AssessmentApp
from src.engine.config import load_task_config
from src.inputs.base import Pointer
from src.tasks.base_task import gaze_geometry_from_screen, screen_size_mismatch
from tests.test_task_pipeline import _SingleTargetTask

PHYSICAL = (1920, 1080)
COLUMN_LOGICAL = 280
HEADER_LOGICAL = 75
TARGETS = [(0.15, 0.15), (0.5, 0.5), (0.85, 0.5), (0.85, 0.85)]


def _layout(dpr: float, screen_origin_x: int = 0):
    """Logical screen + canvas, shaped like the S4.2 sessions (canvas at
    +0,+75, 280 px operator column) scaled to ``dpr``."""
    geo_w, geo_h = round(PHYSICAL[0] / dpr), round(PHYSICAL[1] / dpr)
    canvas_w, canvas_h = geo_w - COLUMN_LOGICAL, geo_h - HEADER_LOGICAL
    return geo_w, geo_h, canvas_w, canvas_h, (screen_origin_x, 0), (screen_origin_x, HEADER_LOGICAL)


def _cursor_error_px(dpr: float, tx: float, ty: float, screen_origin_x: int = 0) -> tuple[float, bool]:
    geo_w, geo_h, cw, ch, (sx, sy), (cx, cy) = _layout(dpr, screen_origin_x)
    task = _SingleTargetTask(load_task_config("click_static"), cw, ch, tx, ty, 90)
    task.set_screen_size(cw, ch)
    task.set_gaze_geometry(*gaze_geometry_from_screen(sx, sy, geo_w, geo_h, cx, cy))
    # Perfect gaze at the target: the tracker reports the fraction of the screen.
    gx = (cx - sx + tx * cw) / geo_w
    gy = (cy - sy + ty * ch) / geo_h
    px, py = task.pointer_to_canvas_px(Pointer(gx, gy, True, 0))
    err = ((px - tx * cw) ** 2 + (py - ty * ch) ** 2) ** 0.5
    return err, err <= 90


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5])
@pytest.mark.parametrize("tx,ty", TARGETS)
def test_perfect_gaze_hits_at_every_scale(dpr, tx, ty):
    err, hit = _cursor_error_px(dpr, tx, ty)
    assert err < 1.0 and hit


@pytest.mark.parametrize("dpr", [1.0, 1.5])
@pytest.mark.parametrize("tx,ty", TARGETS)
def test_secondary_monitor_with_nonzero_origin_is_identical(dpr, tx, ty):
    assert _cursor_error_px(dpr, tx, ty, screen_origin_x=1920)[0] < 1.0


def test_dpr_1_matches_previous_conversion():
    """At 100 % the logical geometry equals SCREEN_SIZE, so the helper's
    output is exactly what the old SCREEN_SIZE-based code fed the task."""
    assert gaze_geometry_from_screen(0, 0, 1920, 1080, 0, 75) == (1920, 1080, 0, 75)
    assert gaze_geometry_from_screen(1920, 0, 1920, 1080, 1920, 75) == (1920, 1080, 0, 75)


def test_screen_size_mismatch_tolerance():
    assert not screen_size_mismatch(1536, 864, 1.25, 1920, 1080)
    assert not screen_size_mismatch(1280, 720, 1.5, 1921, 1079)  # within +-2 px
    assert screen_size_mismatch(1920, 1080, 1.0, 2560, 1440)
    assert screen_size_mismatch(1280, 720, 1.5, 1920, 1090)


class _FakeScreen:
    def __init__(self, w, h, dpr):
        self._geo = SimpleNamespace(x=lambda: 0, y=lambda: 0, width=lambda: w, height=lambda: h)
        self._dpr = dpr

    def geometry(self):
        return self._geo

    def devicePixelRatio(self):
        return self._dpr


def _fake_app(info, screen):
    logs = []
    app = SimpleNamespace(
        client=SimpleNamespace(device_info=info),
        canvas=SimpleNamespace(
            screen=lambda: screen, mapToGlobal=lambda p: SimpleNamespace(x=lambda: 0, y=lambda: 75)
        ),
        task=SimpleNamespace(set_gaze_geometry=lambda *a: None),
        recorder=SimpleNamespace(log=logs.append),
        _pointer_is_mouse=False,  # a gaze run: the monitor geometry applies
    )
    return app, logs


def test_mismatch_logged_once_not_every_frame():
    info = SimpleNamespace(screen_width=2560, screen_height=1440, screen_x=0, screen_y=0)
    app, logs = _fake_app(info, _FakeScreen(1920, 1080, 1.0))
    for _ in range(5):
        AssessmentApp._sync_gaze_geometry(app)
    assert len(logs) == 1
    # A fresh device-info query (reconnect) logs again.
    app.client.device_info = SimpleNamespace(screen_width=2560, screen_height=1440, screen_x=0, screen_y=0)
    AssessmentApp._sync_gaze_geometry(app)
    assert len(logs) == 2


def test_matching_size_logs_nothing_and_missing_screen_size_is_noop():
    info = SimpleNamespace(screen_width=1920, screen_height=1080, screen_x=0, screen_y=0)
    app, logs = _fake_app(info, _FakeScreen(1280, 720, 1.5))
    AssessmentApp._sync_gaze_geometry(app)
    assert logs == []
    app.client.device_info = None
    AssessmentApp._sync_gaze_geometry(app)
    assert logs == []
