"""SPEC-scene-cause-effect-task.md 3.7, P6: the text prompt's lettering is about 1.5 degrees tall,
computed from the same visual-angle maths as the target sizes and the cell gap (650 mm viewing
distance), never a fixed number of px. Pure maths; the drawing is in ``test_scene_banner.py``."""

from __future__ import annotations

import math

import pytest

from src.engine.config import load_task_config
from src.engine.prompt_text import (
    PROMPT_TEXT_DEG,
    apply_prompt_text,
    extent_px_for,
    prompt_text_log_line,
    prompt_text_px_for,
)
from src.engine.target_size import (
    DEFAULT_VIEWING_DISTANCE_MM,
    REFERENCE_MM_PER_PX,
    ScaleInfo,
    gap_px_for,
    radius_px_for,
    screen_scale,
)
from src.engine.task_runner import build_task

REF = REFERENCE_MM_PER_PX  # 531.4 mm over 1920 px: the lab's 24" 1920 x 1080 monitor at 100 %
D = DEFAULT_VIEWING_DISTANCE_MM  # 650 mm


def test_the_lettering_is_one_and_a_half_degrees():
    assert PROMPT_TEXT_DEG == 1.5
    assert prompt_text_px_for(REF, D) == pytest.approx(2 * D * math.tan(math.radians(0.75)) / REF)


def test_it_is_about_60_px_on_the_standard_display():
    assert 58.0 <= prompt_text_px_for(REF, D) <= 64.0  # 61.5
    assert prompt_text_px_for(REF, D) == pytest.approx(61.49, abs=0.05)


def test_it_agrees_with_the_other_visual_angle_sizes():
    """The new helper cannot drift from the target-size and cell-gap maths."""
    for mm, distance in ((REF, 650.0), (0.3, 650.0), (0.25, 800.0), (0.39, 500.0)):
        assert extent_px_for(1.0, mm, distance) == pytest.approx(gap_px_for("wide", mm, distance))
        assert extent_px_for(2.0, mm, distance) == pytest.approx(gap_px_for("extra_wide", mm, distance))
        # A target preset is a diameter in degrees: its radius is half the extent.
        assert extent_px_for(5.0, mm, distance) / 2 == pytest.approx(radius_px_for("medium", mm, distance))
        assert extent_px_for(8.0, mm, distance) / 2 == pytest.approx(radius_px_for("large", mm, distance))


def test_it_follows_the_screen_and_the_viewing_distance_and_is_never_a_fixed_px():
    base = prompt_text_px_for(REF, D)
    assert prompt_text_px_for(REF / 2, D) == pytest.approx(2 * base)  # a finer screen: more px
    assert prompt_text_px_for(REF * 2, D) == pytest.approx(base / 2)
    assert prompt_text_px_for(REF, 2 * D) == pytest.approx(2 * base)  # further away: bigger
    assert prompt_text_px_for(REF, D / 2) == pytest.approx(base / 2)
    sizes = {round(prompt_text_px_for(mm, d), 1) for mm in (0.2, 0.28, 0.4) for d in (500.0, 650.0, 900.0)}
    assert len(sizes) == 9


@pytest.mark.parametrize("bad", [0, 0.0, -1.0, None])
def test_a_missing_scale_or_distance_falls_back_to_the_reference_monitor_and_650_mm(bad):
    standard = prompt_text_px_for(REF, D)
    assert prompt_text_px_for(bad, D) == pytest.approx(standard)
    assert prompt_text_px_for(REF, bad) == pytest.approx(standard)


def test_apply_resolves_the_size_into_the_task_config_against_the_screen_scale():
    cfg = {"task_id": "choice_making"}
    info = apply_prompt_text(cfg, ScaleInfo(0.3, "config"), 650.0)
    expected = round(prompt_text_px_for(0.3, 650.0), 1)
    assert cfg["prompt_text_px"] == expected and info == {"text_deg": 1.5, "text_px": expected}
    # A 1366-px-wide laptop (same 24" panel width assumed) needs fewer px for the same angle.
    laptop = screen_scale(None, {"screen_width_px": 1366})
    cfg = {"task_id": "choice_making"}
    assert apply_prompt_text(cfg, laptop, 650.0)["text_px"] < expected
    assert cfg["prompt_text_px"] == pytest.approx(43.7, abs=0.1)


def test_other_tasks_are_left_alone():
    for task_id in ("click_static", "click_grid", "follow_moving", "scanning", None):
        cfg = {"task_id": task_id}
        assert apply_prompt_text(cfg, ScaleInfo(REF, "fallback"), D) is None
        assert cfg == {"task_id": task_id}


def test_the_log_line_names_the_angle_and_the_px():
    assert prompt_text_log_line({"text_deg": 1.5, "text_px": 61.5}) == "Prompt text: 1.5° (≈62 px)"


def test_the_task_reads_the_resolved_size_and_passes_it_to_the_canvas():
    config = load_task_config("choice_making")
    config["task"]["prompt_text_px"] = 70.0
    task = build_task("choice_making", config, seed=1)
    assert task.prompt_text_px == 70.0 and task.scene_spec()["prompt_text_px"] == 70.0


def test_without_a_resolved_size_the_task_uses_the_reference_monitor():
    task = build_task("choice_making", load_task_config("choice_making"), seed=1)
    assert task.prompt_text_px == pytest.approx(prompt_text_px_for(REF, D))
    assert task.scene_spec()["prompt_text_px"] == pytest.approx(61.49, abs=0.05)
