"""SPEC-compass-task-flow.md 4B.4 (complete structural, task-filtered live), R7, HB12 and the
P4 carry-forward: what ``settings_snapshot`` produces is what ``report_config`` reads."""

from __future__ import annotations

import copy

import pytest

from src.data.report_config import build_config_rows
from src.data.report_util import NOT_RECORDED
from src.engine.config import deep_merge, load_task_config
from src.engine.settings_profile import list_named_configurations, save_settings_profile
from src.ui.settings_registry import (
    apply_live_values_to_config,
    get_nested,
    initial_live_values,
    initial_structural_values,
    live_settings_for_task,
    structural_settings_for_task,
)
from src.ui.settings_snapshot import (
    complete_settings,
    merged_config,
    run_settings,
    settings_snapshot,
)

TASKS = ("click_static", "click_grid", "follow_moving", "scanning")


def _flat_structural(task_id, structural):
    """Every structural registry key read back out of a nested block."""
    return {s.key: get_nested(structural, s.key) for s in structural_settings_for_task(task_id)}


# -- settings_snapshot: complete, task-applicable, YAML defaults --------------------------


@pytest.mark.parametrize("task_id", TASKS)
def test_the_snapshot_has_exactly_the_keys_of_the_task(task_id):
    config = load_task_config(task_id)
    snap = settings_snapshot(task_id, config)
    assert set(snap) == {"live", "structural"}
    assert set(snap["live"]) == {s.key for s in live_settings_for_task(task_id)}
    flat = _flat_structural(task_id, snap["structural"])
    assert set(flat) == {s.key for s in structural_settings_for_task(task_id)}
    assert None not in flat.values()  # every structural control has a value


@pytest.mark.parametrize("task_id", TASKS)
def test_the_snapshot_equals_the_defaults_of_the_merged_yaml(task_id):
    """AB3: defaults come from the merged YAML, never a registry fallback."""
    config = load_task_config(task_id)
    snap = settings_snapshot(task_id, config)
    expected_live = initial_live_values(config)
    for key, value in snap["live"].items():
        assert value == expected_live[key]
    assert _flat_structural(task_id, snap["structural"]) == initial_structural_values(task_id, config)
    assert snap["live"]["dwell.smoothing.alpha"] == config["dwell"]["smoothing"]["alpha"]


def test_the_live_block_is_task_filtered():
    static = settings_snapshot("click_static", load_task_config("click_static"))["live"]
    follow = settings_snapshot("follow_moving", load_task_config("follow_moving"))["live"]
    assert "motion.speed_frac_per_s" not in static
    assert follow["motion.speed_frac_per_s"] == load_task_config("follow_moving")["task"]["motion"][
        "speed_frac_per_s"
    ]


def test_the_structural_block_is_nested_like_the_dialog_overrides_and_includes_the_sounds():
    snap = settings_snapshot("click_grid", load_task_config("click_grid"))["structural"]
    assert snap["feedback"] == {"hit_sound": True, "miss_sound": True, "target_glow": True}
    assert snap["input"] == {"pointer": "gaze", "selection": "dwell"}
    assert set(snap["grid"]) == {"rows", "cols", "gap"}
    assert snap["target"] == {"size": "medium"}
    assert isinstance(snap["trials"], int)
    # Ready to be merged straight over the task block.
    merged = deep_merge(load_task_config("click_grid")["task"], snap)
    assert merged["feedback"]["hit_sound"] is True and merged["feedback"]["particles"] is True


# -- complete_settings: values over defaults, nothing mutated ------------------------------


def test_partial_values_are_completed_from_the_defaults():
    config = load_task_config("click_grid")
    out = complete_settings(
        "click_grid", config, live={"dwell.threshold_ms": 1200}, structural={"grid": {"rows": 5}}
    )
    defaults = settings_snapshot("click_grid", config)
    assert out["live"]["dwell.threshold_ms"] == 1200
    assert out["structural"]["grid"] == {**defaults["structural"]["grid"], "rows": 5}
    assert {k: v for k, v in out["live"].items() if k != "dwell.threshold_ms"} == {
        k: v for k, v in defaults["live"].items() if k != "dwell.threshold_ms"
    }
    assert set(out["live"]) == set(defaults["live"])


def test_nothing_is_changed_in_the_callers_values_or_config():
    config = load_task_config("click_grid")
    before = copy.deepcopy(config)
    live, structural = {"dwell.threshold_ms": 1200}, {"grid": {"rows": 5}}
    complete_settings("click_grid", config, live, structural)
    assert config == before
    assert live == {"dwell.threshold_ms": 1200} and structural == {"grid": {"rows": 5}}


def test_no_values_gives_the_plain_snapshot_and_unknown_keys_are_ignored():
    config = load_task_config("scanning")
    plain = settings_snapshot("scanning", config)
    assert complete_settings("scanning", config) == plain
    noisy = complete_settings(
        "scanning", config,
        live={"totally.made.up": 1, "motion.speed_frac_per_s": 0.9},  # not a scanning key
        structural={"layout": {"radius_px": 77}, "target": {"color": "#fff"}},
    )
    assert noisy["live"] == plain["live"]  # speed is follow_moving only
    assert noisy["structural"] == plain["structural"]


def test_an_invalid_choice_falls_back_to_the_default_like_everywhere_else():
    config = load_task_config("click_grid")
    out = complete_settings(
        "click_grid", config,
        structural={"target": {"size": "gigantic"}, "feedback": {"hit_sound": "maybe"}},
    )
    assert out["structural"]["target"]["size"] == "medium"
    assert out["structural"]["feedback"]["hit_sound"] is True


def test_the_sounds_can_be_switched_off_and_stay_switched_off():
    config = load_task_config("follow_moving")
    out = complete_settings(
        "follow_moving", config, structural={"feedback": {"hit_sound": False}}
    )
    # (Follow the Target plays no miss sound, so it has no such setting.)
    assert out["structural"]["feedback"] == {"hit_sound": False, "target_glow": True}
    scanning = complete_settings(
        "scanning", load_task_config("scanning"), structural={"feedback": {"hit_sound": False}}
    )
    assert scanning["structural"]["feedback"] == {
        "hit_sound": False, "miss_sound": True, "target_glow": True,
    }


@pytest.mark.parametrize("task_id", TASKS)
def test_completing_is_idempotent(task_id):
    config = load_task_config(task_id)
    once = complete_settings(task_id, config, {"dwell.threshold_ms": 1100}, {"trials": 7})
    assert complete_settings(task_id, config, once["live"], once["structural"]) == once


def test_a_stored_configuration_round_trips_through_a_profile_and_back(tmp_path):
    """AB7 data part: selecting a name loads all values; a key the file lacks is its default."""
    config = load_task_config("click_grid")
    full = complete_settings(
        "click_grid", config, {"dwell.smoothing.alpha": 0.4}, {"grid": {"rows": 4, "cols": 4}}
    )
    save_settings_profile(
        tmp_path, "S1", "click_grid", full["live"], full["structural"], name="Wide grid"
    )
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert (entry.live, entry.structural) == (full["live"], full["structural"])
    # An older file with only one key still resolves to a complete set.
    save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.threshold_ms": 1500}, name="Old")
    old = next(c for c in list_named_configurations(tmp_path, "S1", "click_grid") if c.name == "Old")
    loaded = complete_settings("click_grid", config, old.live, old.structural)
    assert loaded["live"]["dwell.threshold_ms"] == 1500
    assert loaded["structural"] == settings_snapshot("click_grid", config)["structural"]


# -- run_settings: the R7 block, in the shape report_config reads --------------------------


def test_the_run_block_is_the_r7_shape():
    config = load_task_config("click_grid")
    block = run_settings("click_grid", config, "Calm room")
    assert list(block) == ["config_name", "live", "structural"]
    assert block["config_name"] == "Calm room"
    assert run_settings("click_grid", config)["config_name"] == ""
    assert set(block["live"]) == {s.key for s in live_settings_for_task("click_grid")}


def test_the_run_block_carries_what_the_report_reads_for_theme_feedback_and_cursor():
    """The P4 carry-forward: ``structural.theme``, ``structural.feedback.{hit_sound,
    miss_sound, particles}`` and ``live["dwell.visual_cursor"]``."""
    config = load_task_config("click_grid")
    block = run_settings("click_grid", config)
    assert block["structural"]["theme"] == config["task"]["theme"] == "forest"
    assert block["structural"]["feedback"] == {
        "hit_sound": True, "miss_sound": True, "target_glow": True,
        "particles": config["task"]["feedback"]["particles"],
    }
    assert block["live"]["dwell.visual_cursor"] is True


def test_the_theme_is_resolved_as_the_app_resolves_it():
    # The task block wins; else the top-level theme block; else "forest" (app.py).
    assert run_settings("click_grid", {"task": {"theme": "space"}})["structural"]["theme"] == "space"
    assert run_settings("click_grid", {"theme": {"name": "ocean"}})["structural"]["theme"] == "ocean"
    assert run_settings("click_grid", {})["structural"]["theme"] == "forest"


def test_particles_is_recorded_only_when_the_config_has_it():
    assert "particles" not in run_settings("click_grid", {})["structural"]["feedback"]
    bare = {"task": {"feedback": {"particles": "yes"}}}  # not a bool: not recorded
    assert "particles" not in run_settings("click_grid", bare)["structural"]["feedback"]


def _meta(block):
    return {"settings": block, "tasks": ["click_grid"]}


def test_report_config_reads_the_run_block_without_dashes_for_the_snapshot_rows():
    config = load_task_config("click_grid")
    block = run_settings("click_grid", config, "Standard")
    rows = dict(build_config_rows(block, _meta(block), task_id="click_grid"))
    assert rows["Configuration name"] == "Standard"
    assert rows["Theme"] == "Forest"
    assert rows["Gaze cursor"] == "Shown"
    assert rows["Feedback"] == "Hit sound on, miss sound on, glow on"
    for label in ("Selection", "Trial timeout", "Inter-trial interval", "Gaze smoothing",
                  "Layout", "Number of trials"):
        assert rows[label] != NOT_RECORDED, label
    assert rows["Layout"].startswith("3×3 grid")


def test_report_config_follows_a_changed_run_block():
    config = load_task_config("click_grid")
    config["task"] = deep_merge(
        config["task"], {"feedback": {"hit_sound": False}, "theme": "space"}
    )
    apply_live_values_to_config(config, {"dwell.visual_cursor": False})
    block = run_settings("click_grid", config, "Quiet")
    rows = dict(build_config_rows(block, _meta(block), task_id="click_grid"))
    assert rows["Configuration name"] == "Quiet"
    assert rows["Theme"] == "Space"
    assert rows["Gaze cursor"] == "Hidden"
    assert rows["Feedback"] == "Hit sound off, miss sound on, glow on"


def test_the_controls_only_snapshot_has_no_theme():
    """Why ``run_settings`` exists: the test entry's snapshot is the page's controls, which
    do not include the theme or the dead ``feedback.particles`` key."""
    snap = settings_snapshot("click_grid", load_task_config("click_grid"))
    assert "theme" not in snap["structural"]
    assert "particles" not in snap["structural"]["feedback"]


# -- merged_config: what a run built from a test's stored configuration starts with ---------


def test_merged_config_lays_structural_and_live_over_the_task_config():
    config = load_task_config("click_grid")
    out = merged_config(config, {"dwell.threshold_ms": 1234}, {"trials": 7, "grid": {"rows": 4}})
    assert out["task"]["trials"] == 7 and out["task"]["grid"]["rows"] == 4
    assert initial_live_values(out)["dwell.threshold_ms"] == 1234


def test_merged_config_leaves_the_base_config_alone():
    config = load_task_config("click_grid")
    before = copy.deepcopy(config)
    merged_config(config, {"dwell.threshold_ms": 1234}, {"trials": 7})
    assert config == before


def test_merged_config_with_nothing_to_lay_over_is_a_copy():
    config = load_task_config("click_static")
    out = merged_config(config)
    assert out == config and out is not config and out["task"] is not config["task"]


@pytest.mark.parametrize("task_id", TASKS)
def test_complete_settings_is_the_snapshot_of_the_merged_config(task_id):
    config = load_task_config(task_id)
    live, structural = {"dwell.threshold_ms": 999}, {"trials": 5}
    assert complete_settings(task_id, config, live, structural) == settings_snapshot(
        task_id, merged_config(config, live, structural)
    )


def test_run_settings_keeps_a_missing_config_name_as_none():
    block = run_settings("click_grid", load_task_config("click_grid"), None)
    assert block["config_name"] is None
