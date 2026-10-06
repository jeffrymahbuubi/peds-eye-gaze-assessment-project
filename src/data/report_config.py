"""The report's Test Configuration table (SPEC-compass-task-flow.md 4D.3, R7).

``build_config_rows(snapshot, metadata)`` turns what a run used into 17 label/value
rows like Compass's. ``snapshot`` is ``metadata["settings"]``
(``{config_name, live, structural}``, R7): what was *requested*. The resolved facts
(target size in px, the capped cell gap, the display, the calibration) come from the
rest of ``metadata.json``. A value its source lacks is "—", never a guess, so an old
folder with a partial snapshot still gives all 17 rows.

Pure and Qt-free. ``live`` is a flat dict keyed like ``dwell.threshold_ms``;
``structural`` mirrors the task YAML (``{"trials": 6, "target": {"size": ...}}``).
"""

from __future__ import annotations

from typing import Any

from ..engine.target_size import GAP_NAMES, SIZE_NAMES
from ..engine.task_info import TASK_INFO

DASH = "—"

_INPUT_LABELS = {
    "eye": "Eye gaze (dwell)",
    "gaze_switch": "Gaze pointer + switch",
    "switch": "Switch (mouse pointer)",
}
_MOTION_PATHS = {
    "circular": "Circular",
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "diagonal_tlbr": "Diagonal (top-left to bottom-right)",
    "diagonal_trbl": "Diagonal (top-right to bottom-left)",
}


def setting(snapshot: dict[str, Any] | None, live_key: str | None, *path: str) -> Any:
    """A value from the run's settings: ``live[live_key]`` when present, else the
    ``structural`` dict walked along ``path``; None when neither has it."""
    snapshot = snapshot or {}
    live = snapshot.get("live")
    if live_key and isinstance(live, dict) and live.get(live_key) is not None:
        return live[live_key]
    node: Any = snapshot.get("structural")
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _seconds(ms: Any) -> str:
    n = _num(ms)
    return DASH if n is None else f"{n / 1000.0:g} s"


def _yes_no(value: Any) -> str:
    return DASH if value is None else ("Yes" if value else "No")


def _first_task(meta: dict[str, Any], task_id: str | None) -> str | None:
    if task_id:
        return task_id
    tasks = meta.get("tasks")
    return str(tasks[0]) if isinstance(tasks, list) and tasks else None


def _input_row(meta: dict[str, Any]) -> str:
    mode = meta.get("input_mode")
    if mode is None:
        return DASH
    label = _INPUT_LABELS.get(str(mode), str(mode))
    if mode == "switch":  # the mouse drives the pointer: no tracker involved
        return label
    rate = _num(meta.get("gazepoint_rate_hz")) or _num(meta.get("measured_sample_rate_hz"))
    model = meta.get("gazepoint_model") or ""
    tracker = ", ".join(p for p in (str(model), f"{rate:g} Hz" if rate else "") if p)
    return f"{label}, {tracker}" if tracker else label


def _selection_row(snapshot: dict[str, Any], meta: dict[str, Any]) -> str:
    refractory = _num(setting(snapshot, "dwell.refractory_ms", "dwell", "refractory_ms"))
    tail = f", refractory {refractory:g} ms" if refractory is not None else ""
    if meta.get("input_mode") in ("gaze_switch", "switch"):
        return f"Switch press{tail}"
    threshold = _num(setting(snapshot, "dwell.threshold_ms", "dwell", "threshold_ms"))
    return DASH if threshold is None else f"Dwell {threshold:g} ms{tail}"


def _size_row(snapshot: dict[str, Any], meta: dict[str, Any], task: str | None, shrunk: Any) -> str:
    info = meta.get("target_size")
    if isinstance(info, dict) and info.get("preset") in SIZE_NAMES:
        text = f"{SIZE_NAMES[info['preset']]} ({_num(info.get('diameter_deg')) or 0:g}°)"
        radius = _num(info.get("radius_px"))
        if radius:
            text += f", {radius:.0f} px radius"
    else:
        block = "layout" if task == "scanning" else "target"
        radius = _num(setting(snapshot, None, block, "radius_px"))
        if radius is None:
            return DASH
        text = f"{radius:g} px radius"
    if isinstance(shrunk, dict) and _num(shrunk.get("used_px")):
        text += f", capped to {_num(shrunk['used_px']):.0f} px to fit"
    return text


def _layout_row(snapshot: dict[str, Any], meta: dict[str, Any], task: str | None) -> str:
    slots = meta.get("layout_slots")
    n_slots = len(slots) if isinstance(slots, list) else None
    if task == "click_grid":
        rows, cols = (_num(setting(snapshot, None, "grid", k)) for k in ("rows", "cols"))
        text = f"{rows:g}×{cols:g} grid" if rows and cols else (
            f"{n_slots} cells" if n_slots else DASH
        )
        gap = meta.get("grid_gap")
        preset = gap.get("preset") if isinstance(gap, dict) else setting(snapshot, None, "grid", "gap")
        if text != DASH and preset in GAP_NAMES:
            text += f", gap {GAP_NAMES[preset]}"
        return text
    if task == "scanning":
        n = _num(setting(snapshot, None, "layout", "n_icons")) or n_slots
        arrangement = setting(snapshot, None, "layout", "arrangement")
        if not n:
            return DASH
        return f"{n:g} icons" + (f", {arrangement}" if arrangement else "")
    if task == "follow_moving":
        path = setting(snapshot, None, "motion", "path")
        if path is None:
            return DASH
        text = f"{_MOTION_PATHS.get(str(path), str(path))} path"
        speed = _num(setting(snapshot, "motion.speed_frac_per_s", "motion", "speed_frac_per_s"))
        if speed is not None:
            text += f", {speed * 100:g}% of the width per second"
        window = _num(setting(snapshot, None, "motion", "select_window_ms"))
        if window is not None:
            text += f", selection window {window / 1000.0:g} s"
        return text
    if task == "click_static":
        positions = setting(snapshot, None, "target", "positions")
        return f"{len(positions)} positions" if isinstance(positions, list) and positions else DASH
    return DASH


def _theme_row(snapshot: dict[str, Any]) -> str:
    theme = setting(snapshot, None, "theme")
    if isinstance(theme, dict):
        theme = theme.get("name")
    return str(theme).capitalize() if theme else DASH


def _feedback_row(snapshot: dict[str, Any]) -> str:
    hit, miss, sparkle = (
        setting(snapshot, None, "feedback", k) for k in ("hit_sound", "miss_sound", "particles")
    )
    if hit is None and miss is None and sparkle is None:
        return DASH
    if hit and miss:
        sound = "on"
    elif hit or miss:
        sound = "hit only" if hit else "miss only"
    else:
        sound = "off"
    return f"Sound {sound}, sparkle {'on' if sparkle else 'off'}"


def _smoothing_row(snapshot: dict[str, Any]) -> str:
    enabled = setting(snapshot, "dwell.smoothing.enabled", "dwell", "smoothing", "enabled")
    alpha = _num(setting(snapshot, "dwell.smoothing.alpha", "dwell", "smoothing", "alpha"))
    jitter = _num(setting(snapshot, "dwell.jitter_tolerance_px", "dwell", "jitter_tolerance_px"))
    if enabled is None and jitter is None:
        return DASH
    head = DASH if enabled is None else (f"Smoothing α {alpha:g}" if enabled and alpha is not None
                                         else ("Smoothing on" if enabled else "Smoothing off"))
    return head if jitter is None else f"{head}, jitter tolerance {jitter:g} px"


def _display_row(meta: dict[str, Any]) -> str:
    w, h = _num(meta.get("display_width_px")), _num(meta.get("display_height_px"))
    if not (w and h):
        return DASH
    text = f"{w:.0f}×{h:.0f}"
    scale = _num(meta.get("display_scale_percent"))
    if scale:
        text += f" @ {scale:g}%"
    standard = meta.get("display_standard")
    if standard is not None:
        text += " (standard)" if standard else " (not standard)"
    return text


def _calibration_row(meta: dict[str, Any], geometry: Any) -> str:
    source = meta.get("calibration_source")
    if source == "not run":
        return "Not run"
    points = _num(meta.get("calibration_points"))
    error = _num(meta.get("calibration_error_px"))
    parts = []
    if points:
        parts.append(f"{points:.0f} points")
    if error is not None:
        deg = geometry.px_to_deg(error) if geometry is not None else None
        parts.append(f"mean error {error:.1f} px" + (f" ({deg:.2f}°)" if deg is not None else ""))
    if source:
        parts.append(str(source))
    return ", ".join(parts) if parts else DASH


def _canvas_row(meta: dict[str, Any]) -> str:
    w, h = _num(meta.get("canvas_width_px")), _num(meta.get("canvas_height_px"))
    if not (w and h):
        return DASH
    unit = "physical px" if meta.get("canvas_units") == "physical" else "px"
    return f"{w:.0f}×{h:.0f} {unit}"


def build_config_rows(
    snapshot: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    *,
    task_id: str | None = None,
    shrunk: dict[str, Any] | None = None,
    geometry: Any = None,
) -> list[tuple[str, str]]:
    """The 17 ``(label, value)`` rows of the Test Configuration table.

    ``task_id`` falls back to ``metadata["tasks"][0]``; ``shrunk`` is the run's
    ``TARGET_SHRUNK`` event payload (the preset did not fit its cell); ``geometry``
    (a :class:`~.report_geometry.Geometry`) adds the calibration error in degrees.
    """
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    meta = metadata or {}
    task = _first_task(meta, task_id)
    config_name = snapshot.get("config_name") or meta.get("config_name") or DASH
    planned = _num(meta.get("planned_trials")) or _num(setting(snapshot, None, "trials"))
    cursor = setting(snapshot, "dwell.visual_cursor", "dwell", "visual_cursor")
    distance = _num(meta.get("viewing_distance_mm"))
    size_label = "Icon size" if task == "scanning" else "Target size"
    return [
        ("Configuration name", str(config_name)),
        ("Task", TASK_INFO[task][0] if task in TASK_INFO else (task or DASH)),
        ("Input", _input_row(meta)),
        ("Trials (planned)", f"{planned:.0f}" if planned else DASH),
        ("Selection", _selection_row(snapshot, meta)),
        (size_label, _size_row(snapshot, meta, task, shrunk)),
        ("Layout", _layout_row(snapshot, meta, task)),
        ("Maximum time per trial", _seconds(setting(snapshot, "task.timeout_ms", "timeout_ms"))),
        (
            "Pause between trials",
            _seconds(setting(snapshot, "task.inter_trial_interval_ms", "inter_trial_interval_ms")),
        ),
        ("Theme", _theme_row(snapshot)),
        ("Gaze cursor shown", _yes_no(cursor)),
        ("Feedback", _feedback_row(snapshot)),
        ("Gaze smoothing", _smoothing_row(snapshot)),
        ("Display", _display_row(meta)),
        ("Viewing distance", f"{distance:g} mm" if distance else DASH),
        ("Calibration", _calibration_row(meta, geometry)),
        ("Canvas", _canvas_row(meta)),
    ]
