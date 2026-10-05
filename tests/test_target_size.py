"""SPEC-target-size-and-motion-paths.md Phase A: target size presets (visual
angle), the size-to-radius resolution, the grid fit (target AND hitbox kept
inside the cell), and what gets recorded. Acceptance criteria 6.1-6.6."""

from __future__ import annotations

import csv
import json
import logging
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.app import AssessmentApp
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.engine.config import deep_merge, load_task_config
from src.engine.target_size import (
    CELL_PAD_FRAC,
    DEFAULT_SIZE,
    REFERENCE_MM_PER_PX,
    ScaleInfo,
    apply_target_size,
    estimate_grid_fit_radius_px,
    mm_per_logical_px,
    radius_px_for,
    resolve_mm_per_px,
    screen_scale,
    target_size_log_line,
    viewing_distance_mm,
)
from src.engine.task_runner import build_task, run_headless_replay
from src.inputs.base import Pointer, circle_contains

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay_click_static.jsonl"
LAB = ScaleInfo(REFERENCE_MM_PER_PX, "edid", 531.4, 298.9)  # 24" 1080p, EDID


class _FakeRecorder:
    def __init__(self):
        self.events = []
        self.lines = []

    def record_event(self, kind, t_ns, **payload):
        self.events.append((kind, t_ns, payload))

    def log(self, message):
        self.lines.append(message)


def _grid_task(rows, cols, size, canvas=(1500, 1000), recorder=None, mode="switch", scale=LAB):
    """A click_grid task with the size preset resolved the way the app does."""
    cfg = load_task_config("click_grid")
    cfg["input"] = {"mode": mode}
    cfg["task"]["grid"] = {**cfg["task"]["grid"], "rows": rows, "cols": cols}
    cfg["task"]["target"]["size"] = size
    apply_target_size(cfg["task"], scale, 650.0)
    task = build_task("click_grid", cfg, recorder=recorder)
    task.set_screen_size(*canvas)
    task.jitter_px = 40.0
    return task


def _pointer_at(task, target, dx_px=0.0, dy_px=0.0, clicked=False):
    cx = target.x_norm * task.screen_w
    cy = target.y_norm * task.screen_h
    return Pointer(
        x=(cx + dx_px) / task.screen_w, y=(cy + dy_px) / task.screen_h, valid=True, clicked=clicked
    )


# -- 6.1 radius_px_for / mm_per_logical_px -------------------------------------


@pytest.mark.parametrize(
    "size, expected", [("small", 61.5), ("medium", 102.5), ("large", 164.2)]
)
def test_preset_radius_on_the_lab_monitor(size, expected):
    # 24" 1920x1080 at 650 mm: S ~61, M ~102, L ~164 px radius (+-1).
    assert radius_px_for(size, REFERENCE_MM_PER_PX, 650.0) == pytest.approx(expected, abs=1.0)


def test_diameter_follows_the_visual_angle_formula():
    mm_per_px = 0.3
    for size, degrees in (("small", 3.0), ("medium", 5.0), ("large", 8.0)):
        diameter_mm = 2 * 650.0 * math.tan(math.radians(degrees) / 2)
        assert radius_px_for(size, mm_per_px, 650.0) == pytest.approx(diameter_mm / 2 / mm_per_px)


def test_150_percent_scale_keeps_the_same_millimetres_on_screen():
    # 1920x1080 physical at 150 % is 1280 logical px wide.
    per_logical, source = mm_per_logical_px(531.4, 1280, dpr=1.5)
    assert source == "config"
    medium = radius_px_for("medium", per_logical, 650.0)
    assert medium == pytest.approx(68.4, abs=1.0)
    # Same millimetres on the glass as at 100 % scale.
    reference = radius_px_for("medium", REFERENCE_MM_PER_PX, 650.0) * REFERENCE_MM_PER_PX
    assert medium * per_logical == pytest.approx(reference)


@pytest.mark.parametrize("bad_width_mm", [0, -5, None, 5000.0, 50.0, "n/a"])
def test_implausible_physical_width_falls_back(bad_width_mm):
    value, source = mm_per_logical_px(bad_width_mm, 1920)
    assert source == "fallback"
    assert value == pytest.approx(REFERENCE_MM_PER_PX)


def test_plausibility_is_judged_per_physical_px():
    # 531.4 mm over 1920 physical px = 0.277 mm/px -- plausible at any scale,
    # including when the caller only knows the 1280 logical px.
    assert mm_per_logical_px(531.4, 1280, dpr=1.5)[1] == "config"
    # 100 mm over 1920 px = 0.052 mm/px: implausible.
    assert mm_per_logical_px(100.0, 1920)[1] == "fallback"


def test_fallback_assumes_the_reference_panel_width_at_any_scale():
    value, source = mm_per_logical_px(None, 1280, dpr=1.5)
    assert source == "fallback"
    assert value == pytest.approx(531.4 / 1280)


def test_physical_width_source_order_is_config_then_edid_then_fallback():
    assert resolve_mm_per_px(1920, 1.0, 600.0, 531.4)[1] == "config"
    assert resolve_mm_per_px(1920, 1.0, None, 531.4)[1] == "edid"
    # An implausible config value yields to a good EDID one, and vice versa.
    assert resolve_mm_per_px(1920, 1.0, 5000.0, 531.4)[1] == "edid"
    assert resolve_mm_per_px(1920, 1.0, None, 0)[1] == "fallback"


def _fake_screen(logical_w, dpr, width_mm, height_mm):
    return SimpleNamespace(
        geometry=lambda: SimpleNamespace(width=lambda: logical_w),
        devicePixelRatio=lambda: dpr,
        physicalSize=lambda: SimpleNamespace(width=lambda: width_mm, height=lambda: height_mm),
    )


def test_screen_scale_reads_edid_then_config_override():
    screen = _fake_screen(1920, 1.0, 531.0, 299.0)
    scale = screen_scale(screen, {})
    assert (scale.source, scale.width_mm, scale.height_mm) == ("edid", 531.0, 299.0)
    assert scale.mm_per_px == pytest.approx(531.0 / 1920)
    assert screen_scale(screen, {"screen_physical_width_mm": 600.0}).source == "config"


def test_screen_scale_with_no_screen_is_the_fallback_headless_case():
    scale = screen_scale(None, {"screen_width_px": 1920})
    assert scale.source == "fallback"
    assert scale.mm_per_px == pytest.approx(REFERENCE_MM_PER_PX)


def test_unknown_size_name_uses_the_default_and_is_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="src.engine.target_size"):
        radius = radius_px_for("huge", REFERENCE_MM_PER_PX, 650.0)
    assert radius == pytest.approx(radius_px_for(DEFAULT_SIZE, REFERENCE_MM_PER_PX, 650.0))
    assert "huge" in caplog.text


def test_viewing_distance_defaults_to_650():
    assert viewing_distance_mm({}) == 650.0
    assert viewing_distance_mm({"viewing_distance_mm": None}) == 650.0
    assert viewing_distance_mm({"viewing_distance_mm": 700}) == 700.0


# -- 6.5 size vs the legacy radius_px -------------------------------------------


def test_config_with_only_radius_px_is_left_alone():
    task_cfg = {"target": {"radius_px": 150}}
    assert apply_target_size(task_cfg, LAB, 650.0) is None
    assert task_cfg["target"]["radius_px"] == 150


def test_size_wins_when_both_are_present():
    task_cfg = {"target": {"radius_px": 10, "size": "large"}}
    info = apply_target_size(task_cfg, LAB, 650.0)
    assert task_cfg["target"]["radius_px"] == pytest.approx(164.2, abs=0.1)
    assert info["preset"] == "large"


def test_old_profile_radius_is_overridden_by_the_yaml_size_after_the_merge():
    # A pre-change profile's structural block holds only target.radius_px; merged
    # over the new click_grid.yaml (which carries target.size) both are present,
    # so size wins -- the SPEC S4.2 rule, and why the YAML default is `medium`.
    cfg = load_task_config("click_grid")
    cfg["task"] = deep_merge(cfg["task"], {"target": {"radius_px": 120}})
    info = apply_target_size(cfg["task"], LAB, 650.0)
    assert info["preset"] == "medium"
    assert cfg["task"]["target"]["radius_px"] == pytest.approx(102.5, abs=1.0)


def test_legacy_config_without_size_builds_with_its_radius():
    cfg = load_task_config("click_static")  # still px: Phase B has not touched it
    assert "size" not in cfg["task"]["target"]
    assert apply_target_size(cfg["task"], LAB, 650.0) is None
    assert build_task("click_static", cfg).targets[0].radius_px == cfg["task"]["target"]["radius_px"]


# -- 6.2 grid fit: effective radius -----------------------------------------------


def test_6x6_large_is_capped_inside_its_cell():
    task = _grid_task(6, 6, "large", canvas=(1500, 1000))
    target = task.targets[0]
    assert target.radius_px == pytest.approx(164.2, abs=0.1)
    radius = task.effective_radius_px(target)

    cell_w, cell_h = 0.76 / 6 * 1500, 0.76 / 6 * 1000
    pad = CELL_PAD_FRAC * min(cell_w, cell_h)  # the canvas's own cell padding
    assert radius < target.radius_px
    assert radius <= 0.5 * min(cell_w, cell_h) - pad + 1e-9

    # The drawn circle sits inside the drawn cell rectangle.
    cx, cy = target.x_norm * 1500, target.y_norm * 1000
    left, right = cx - cell_w / 2 + pad, cx + cell_w / 2 - pad
    top, bottom = cy - cell_h / 2 + pad, cy + cell_h / 2 - pad
    assert cx - radius >= left - 1e-9 and cx + radius <= right + 1e-9
    assert cy - radius >= top - 1e-9 and cy + radius <= bottom + 1e-9


def test_frame_result_carries_the_effective_radius():
    task = _grid_task(6, 6, "large")
    result = task.update(0, _pointer_at(task, task.targets[0]))
    assert result.target_radius_px == pytest.approx(task.effective_radius_px(task.targets[0]))
    assert result.target_radius_px < result.target.radius_px


def test_cap_follows_the_live_canvas_size():
    # The canvas resizes mid-run (HUD hide/show), so the cap is per frame.
    task = _grid_task(6, 6, "large", canvas=(1500, 1000))
    before = task.effective_radius_px(task.targets[0])
    task.set_screen_size(1900, 1000)  # wider canvas, same height: height binds
    assert task.effective_radius_px(task.targets[0]) == pytest.approx(before)
    task.set_screen_size(1500, 800)
    assert task.effective_radius_px(task.targets[0]) < before


def test_estimate_matches_the_task_cap_on_the_same_canvas():
    task = _grid_task(6, 6, "large", canvas=(1500, 1000))
    assert estimate_grid_fit_radius_px(6, 6, 1500, 1000) == pytest.approx(
        task.effective_radius_px(task.targets[0])
    )


# -- 6.3 grid fit: hit-testing ----------------------------------------------------


def test_pointer_in_a_neighbour_cell_is_not_on_target_even_inside_the_circle():
    task = _grid_task(6, 6, "large", canvas=(1500, 1000))
    target = task.targets[0]
    cell_h = 0.76 / 6 * 1000
    reach = task.effective_radius_px(target) + task.jitter_px
    dy = cell_h / 2 + 3.0  # just across the cell boundary...
    assert dy < reach  # ...yet inside radius + jitter
    cx, cy = target.x_norm * 1500, target.y_norm * 1000
    assert circle_contains(cx, cy, reach, cx, cy + dy)  # the plain circle would say "on"

    result = task.update(0, _pointer_at(task, target, dy_px=dy))
    assert result.on_target is False


def test_pointer_in_the_cell_corner_within_radius_plus_jitter_is_on_target():
    task = _grid_task(6, 6, "large", canvas=(1500, 1000))
    target = task.targets[0]
    cell_w, cell_h = 0.76 / 6 * 1500, 0.76 / 6 * 1000
    reach = task.effective_radius_px(target) + task.jitter_px
    d = min(cell_w, cell_h) / 2 - 3.0  # inside the cell on both axes
    assert math.hypot(d, d) < reach
    assert task.update(0, _pointer_at(task, target, dx_px=d, dy_px=d)).on_target is True


def test_pointer_outside_radius_plus_jitter_is_not_on_target():
    task = _grid_task(3, 3, "medium", canvas=(1920, 1080))
    target = task.targets[0]
    reach = task.effective_radius_px(target) + task.jitter_px
    assert task.update(0, _pointer_at(task, target, dx_px=reach + 5)).on_target is False


# -- 6.4 no cap when it fits --------------------------------------------------------


def test_3x3_medium_on_1080p_is_not_capped_and_matches_todays_default():
    recorder = _FakeRecorder()
    task = _grid_task(3, 3, "medium", canvas=(1920, 1080), recorder=recorder)
    target = task.targets[0]
    assert task.effective_radius_px(target) == target.radius_px
    assert target.radius_px == pytest.approx(100.0, abs=3.0)  # today's default radius
    task.update(0, _pointer_at(task, target))
    assert [e for e in recorder.events if e[0] == "TARGET_SHRUNK"] == []


def test_3x3_medium_with_the_hud_shown_is_still_not_capped():
    task = _grid_task(3, 3, "medium", canvas=(1640, 1003))
    assert task.effective_radius_px(task.targets[0]) == task.targets[0].radius_px


# -- 6.6 recording ----------------------------------------------------------------


def _play(task, n_trials, t0=0, step_ns=50_000_000, between=None):
    """Hit n_trials in switch mode (pointer on target, clicked)."""
    t = t0
    while len(task.trials) < n_trials:
        index = max(task._trial_index, 0)
        task.update(t, _pointer_at(task, task.targets[index], clicked=True))
        t += step_ns
        if between is not None:
            between(task)
    return t


def test_one_target_shrunk_event_per_run_with_requested_and_used_px():
    recorder = _FakeRecorder()
    task = _grid_task(6, 6, "large", recorder=recorder)
    _play(task, 3)
    shrunk = [(kind, payload) for kind, _t, payload in recorder.events if kind == "TARGET_SHRUNK"]
    assert len(shrunk) == 1  # one per run, not per trial
    payload = shrunk[0][1]
    assert payload["requested_px"] == pytest.approx(164.2, abs=0.1)
    assert payload["used_px"] == pytest.approx(55.7, abs=0.1)
    assert (payload["rows"], payload["cols"]) == (6, 6)


def test_trials_record_the_effective_radius_at_trial_start():
    task = _grid_task(6, 6, "large")

    def _hud_toggle_after_first_trial(t):
        if len(t.trials) == 1:
            t.set_screen_size(1900, 760)  # shorter canvas: a smaller cap

    _play(task, 3, between=_hud_toggle_after_first_trial)
    first, second = task.trials[0], task.trials[1]
    assert first.target_radius_px == pytest.approx(55.7, abs=0.1)
    assert second.target_radius_px < first.target_radius_px
    assert first.as_row()["target_radius_px"] == first.target_radius_px


def test_resized_canvas_does_not_repeat_the_shrunk_event():
    recorder = _FakeRecorder()
    task = _grid_task(6, 6, "large", recorder=recorder)

    def _shrink_further(t):
        if len(t.trials) == 1:
            t.set_screen_size(1500, 700)

    _play(task, 3, between=_shrink_further)
    assert sum(1 for kind, _t, _p in recorder.events if kind == "TARGET_SHRUNK") == 1


def test_metadata_json_and_trials_csv_and_events_for_a_real_session(tmp_path):
    info = apply_target_size({"target": {"size": "large"}}, LAB, 650.0)
    meta = SessionMetadata(subject_id="P001", session_id="s", started_ns=0, target_size=info)
    with SessionRecorder(meta, output_root=tmp_path) as recorder:
        task = _grid_task(6, 6, "large", recorder=recorder)
        _play(task, 2)
        recorder.write_trials(task.trials)

    session = tmp_path / "s"
    data = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    assert set(data["target_size"]) == {
        "preset", "diameter_deg", "radius_px", "mm_per_px", "mm_per_px_source", "viewing_distance_mm",
    }
    assert data["target_size"]["preset"] == "large"
    assert data["target_size"]["diameter_deg"] == 8.0
    assert data["target_size"]["mm_per_px_source"] == "edid"
    assert data["target_size"]["viewing_distance_mm"] == 650.0

    with (session / "trials.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [float(r["target_radius_px"]) for r in rows] == [
        pytest.approx(55.7, abs=0.1), pytest.approx(55.7, abs=0.1)
    ]

    events = [json.loads(line) for line in (session / "events.jsonl").read_text("utf-8").splitlines()]
    assert sum(1 for e in events if e["kind"] == "TARGET_SHRUNK") == 1


def test_metadata_target_size_defaults_to_none_when_no_size_was_used():
    assert SessionMetadata(subject_id="x", session_id="y", started_ns=0).target_size is None


def _fake_app(task_cfg, screen):
    return SimpleNamespace(
        config={"app": {"viewing_distance_mm": 650}, "task": task_cfg},
        canvas=SimpleNamespace(screen=lambda: screen),
        metadata=SessionMetadata(subject_id="P001", session_id="s", started_ns=0),
        recorder=_FakeRecorder(),
    )


def test_app_resolves_size_into_radius_px_metadata_and_session_log():
    app = _fake_app({"target": {"size": "medium", "radius_px": 7}}, _fake_screen(1920, 1.0, 531.4, 298.9))
    AssessmentApp._resolve_target_size(app)
    radius = app.config["task"]["target"]["radius_px"]
    assert radius == pytest.approx(102.5, abs=1.0)  # size won over the stale radius_px
    info = app.metadata.target_size
    assert info["radius_px"] == radius
    assert info["preset"] == "medium" and info["mm_per_px_source"] == "edid"
    assert app.recorder.lines == ["Target size: Medium (5.0°) = 102 px radius (EDID 531x299 mm, 650 mm)."]


def test_app_resolves_in_logical_px_at_150_percent_scale():
    app = _fake_app({"target": {"size": "medium"}}, _fake_screen(1280, 1.5, 531.4, 298.9))
    AssessmentApp._resolve_target_size(app)
    assert app.config["task"]["target"]["radius_px"] == pytest.approx(68.4, abs=1.0)


def test_app_leaves_a_legacy_radius_px_config_alone():
    app = _fake_app({"target": {"radius_px": 120}}, _fake_screen(1920, 1.0, 531.4, 298.9))
    AssessmentApp._resolve_target_size(app)
    assert app.config["task"]["target"]["radius_px"] == 120
    assert app.metadata.target_size is None
    assert app.recorder.lines == []


def test_app_logs_an_unknown_size_name_and_uses_the_default():
    app = _fake_app({"target": {"size": "huge"}}, _fake_screen(1920, 1.0, 531.4, 298.9))
    AssessmentApp._resolve_target_size(app)
    assert app.metadata.target_size["preset"] == DEFAULT_SIZE
    assert "Unknown target size 'huge'" in app.recorder.lines[0]


def test_log_line_names_the_physical_source():
    info = {"preset": "small", "diameter_deg": 3.0, "radius_px": 61.5, "viewing_distance_mm": 650.0}
    assert "EDID 531x299 mm" in target_size_log_line(info, ScaleInfo(0.2767, "edid", 531.0, 299.0))
    assert "configured 600 mm" in target_size_log_line(info, ScaleInfo(0.3, "config", 600.0, None))
    assert "fallback" in target_size_log_line(info, ScaleInfo(0.2767, "fallback"))


def test_headless_replay_resolves_the_preset_on_the_reference_monitor(tmp_path):
    result = run_headless_replay("click_grid", FIXTURE, output_root=tmp_path, max_seconds=30.0)
    session = Path(result["session_dir"])
    data = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    info = data["target_size"]
    assert info["preset"] == "medium"
    assert info["radius_px"] == pytest.approx(102.5, abs=1.0)
    with (session / "trials.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # 3x3 at the configured 1920x1080: no cap, so the preset radius is recorded.
    assert all(float(r["target_radius_px"]) == info["radius_px"] for r in rows)
