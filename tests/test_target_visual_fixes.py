"""SPEC-target-visual-fixes.md acceptance criteria F2 a and F3 a (F1 a is no code).

F2 a: in the ``icons`` scene (scanning) the selectable outline and the instant
and dwell rings are drawn around the *drawn* icon, ``target_radius_px *
ICON_DRAW_FRAC``, not around the hit radius; every other scene is unchanged.
F3 a: the dead ``target.color`` / ``target.highlight_color`` task-YAML keys are
gone, and a saved settings profile that still carries them loads without error.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.engine.config import CONFIG_ROOT, deep_merge, load_task_config
from src.engine.settings_profile import load_settings_profile, save_settings_profile
from src.engine.target_size import ICON_DRAW_FRAC
from src.engine.task_runner import build_task
from src.ui.canvas import TaskCanvas
from src.ui.settings_registry import apply_live_values_to_config

TASK_IDS = ("click_grid", "click_static", "follow_moving", "scanning")
HIT_RADIUS = 100.0
_THEME = {"background": "#000000", "cursor_color": "#ffffff", "target_default": "#ff5252"}

# One cued slot, drawn as a circle, at the canvas centre of an 800x600 canvas.
_SCENES = {
    "icons": {"mode": "icons", "slots": [(0.5, 0.5)], "shapes": [0]},
    "single": {"mode": "single"},
    "grid": {"mode": "grid", "cells": [(0.5, 0.5)], "cell_w": 0.5, "cell_h": 0.5},
    "moving": {"mode": "moving"},
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _canvas(scene: dict, active_slot: int = 0) -> TaskCanvas:
    canvas = TaskCanvas(theme=_THEME)
    canvas.resize(800, 600)
    canvas.show_cursor = False
    canvas.set_frame(
        (0.5, 0.5), HIT_RADIUS, (0.5, 0.5), True, 1.0,  # dwell ring full
        selectable=True, on_target=True, scene=scene, active_slot=active_slot,
    )
    return canvas


# -- F2 a: ring base radius ---------------------------------------------------


def test_ring_base_radius_is_the_drawn_icon_only_in_the_icons_scene(qapp):
    assert _canvas(_SCENES["icons"])._ring_base_radius() == HIT_RADIUS * ICON_DRAW_FRAC
    for mode in ("single", "grid", "moving"):
        assert _canvas(_SCENES[mode])._ring_base_radius() == HIT_RADIUS, mode


def test_ring_base_radius_follows_what_target_draws_in_the_icons_scene(qapp):
    """_draw_target paints the silhouette at ICON_DRAW_FRAC only for a cued slot
    (active_slot >= 0); without one it paints a plain circle at the hit radius,
    and the rings follow that."""
    assert _canvas(_SCENES["icons"], active_slot=-1)._ring_base_radius() == HIT_RADIUS


@pytest.mark.parametrize("mode, base", [("icons", HIT_RADIUS * ICON_DRAW_FRAC), ("single", HIT_RADIUS),
                                        ("grid", HIT_RADIUS), ("moving", HIT_RADIUS)])
def test_the_painted_rings_reach_base_radius_plus_twenty(qapp, mode, base):
    """With the outline (+4), instant ring (+10, pen 5) and dwell ring (+16,
    pen 8) all on, the outermost lit pixel is the dwell ring's outer edge,
    base + 20 -- measured on the rendered canvas, so it proves paintEvent really
    uses the helper rather than just the helper returning the right number."""
    image: QImage = _canvas(_SCENES[mode]).grab().toImage()
    cx = image.width() // 2
    row = image.height() // 2
    lit = [
        x
        for x in range(image.width())
        if (c := QColor(image.pixel(x, row))).red() > 128 and c.green() > 128 and c.blue() > 128
    ]
    assert max(lit) - cx == pytest.approx(base + 20, abs=2.5), mode


def test_the_canvas_target_colour_still_comes_from_the_theme(qapp):
    assert TaskCanvas(theme=_THEME).target_color.name() == "#ff5252"


# -- F3 a: the dead colour keys ----------------------------------------------


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_task_yaml_has_no_target_colour_keys(task_id):
    raw = yaml.safe_load((CONFIG_ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    target = raw.get("target") or {}
    assert "color" not in target
    assert "highlight_color" not in target
    # Resolved through the loader too, so a default.yaml inheritance could not
    # smuggle them back in.
    resolved_target = load_task_config(task_id)["task"].get("target") or {}
    assert "color" not in resolved_target and "highlight_color" not in resolved_target


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_a_saved_profile_still_carrying_the_colour_keys_loads_and_runs(tmp_path, task_id):
    """Profiles written before F3 a (or by another build) may hold the keys.
    Structural overrides are deep-merged over the task block and live values
    are filtered to known keys -- exactly the steps AssessmentApp takes -- so
    the stale keys must be inert, never an error."""
    save_settings_profile(
        tmp_path,
        "S1",
        task_id,
        {"dwell.smoothing.alpha": 0.05, "target.color": "#4caf50", "target.highlight_color": "#ffeb3b"},
        {"target": {"size": "large", "color": "#4caf50", "highlight_color": "#ffeb3b"}},
    )
    profile = load_settings_profile(tmp_path, "S1", task_id)
    assert profile is not None

    config = load_task_config(task_id)
    config["task"] = deep_merge(config["task"], profile["structural"])
    apply_live_values_to_config(config, profile["live"])
    assert config["dwell"]["smoothing"]["alpha"] == 0.05  # the known key was applied
    task = build_task(task_id, config)
    assert task.targets  # the task builds and plays; the stale keys changed nothing


def test_nothing_in_configs_or_src_refers_to_the_dead_keys():
    root = Path(__file__).resolve().parent.parent
    hits = [
        str(path.relative_to(root))
        for folder in ("configs", "src")
        for path in (root / folder).rglob("*")
        if path.suffix in {".py", ".yaml", ".yml", ".json"}
        and "__pycache__" not in path.parts
        and path.name != "local_state.json"
        and "highlight_color" in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert hits == []
