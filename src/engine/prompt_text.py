"""The size of Choice-making's text prompt, by visual angle (SPEC-scene-cause-effect-task.md P6).

The banner's lettering is about 1.5 degrees tall at the viewing distance, so it reads the same on
any monitor. The px figure comes from the same visual-angle maths as the target sizes and the cell
gap (:func:`~src.engine.target_size.radius_px_for`, :func:`~src.engine.target_size.gap_px_for`:
``extent_mm = 2 * D * tan(deg / 2)``, over the monitor's mm per px), never a fixed number of px.
No PySide6 import. The shared maths could not live in ``target_size`` (it is at the 500-line limit);
``tests/test_prompt_text.py`` pins that the two agree.
"""

from __future__ import annotations

import math
from typing import Any

from .target_size import DEFAULT_VIEWING_DISTANCE_MM, REFERENCE_MM_PER_PX, ScaleInfo

PROMPT_TEXT_DEG = 1.5  # the lettering's height (P6)
TASK_ID = "choice_making"


def extent_px_for(degrees: float, mm_per_px: float, viewing_distance_mm: float) -> float:
    """The length in logical px that spans ``degrees`` of visual angle at ``viewing_distance_mm``
    on a monitor of ``mm_per_px``. A missing or non-positive scale or distance falls back to the
    reference monitor and the default 650 mm, as the target-size helpers do."""
    distance = viewing_distance_mm if viewing_distance_mm and viewing_distance_mm > 0 else (
        DEFAULT_VIEWING_DISTANCE_MM
    )
    scale = mm_per_px if mm_per_px and mm_per_px > 0 else REFERENCE_MM_PER_PX
    return 2.0 * distance * math.tan(math.radians(degrees) / 2.0) / scale


def prompt_text_px_for(mm_per_px: float, viewing_distance_mm: float) -> float:
    """The banner lettering's height (its pixel size) in logical px: :data:`PROMPT_TEXT_DEG`."""
    return extent_px_for(PROMPT_TEXT_DEG, mm_per_px, viewing_distance_mm)


def apply_prompt_text(
    task_cfg: dict[str, Any], scale: ScaleInfo, viewing_distance: float
) -> dict[str, Any] | None:
    """Resolve the banner's lettering size into ``prompt_text_px`` in ``task_cfg``, in place,
    against the same screen scale as :func:`~src.engine.target_size.apply_target_size`. Only
    Choice-making has a text prompt: any other task is left alone and ``None`` is returned.
    Returns ``{"text_deg", "text_px"}`` for the Session Log."""
    if task_cfg.get("task_id") != TASK_ID:
        return None
    px = round(prompt_text_px_for(scale.mm_per_px, viewing_distance), 1)
    task_cfg["prompt_text_px"] = px
    return {"text_deg": PROMPT_TEXT_DEG, "text_px": px}


def prompt_text_log_line(info: dict[str, Any]) -> str:
    """The Session Log line, e.g. ``Prompt text: 1.5° (≈62 px)``."""
    return f"Prompt text: {info['text_deg']:g}° (≈{info['text_px']:.0f} px)"
