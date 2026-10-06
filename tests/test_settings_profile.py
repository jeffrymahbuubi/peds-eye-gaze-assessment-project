"""Tests for saved per-subject, per-task settings profiles.

SPEC-live-settings-panel.md S10. Pure logic, no Qt and no device -- the
profile store is deliberately Qt-free for exactly this reason, matching
src/engine/local_state.py.
"""

from __future__ import annotations

import json
import re

import pytest

from src.engine.settings_profile import (
    CONFIG_NAME_MAX_LEN,
    PROFILE_SCHEMA_VERSION,
    NamedConfig,
    effective_config_name,
    known_subject_ids,
    list_named_configurations,
    list_settings_profiles,
    load_settings_profile,
    load_settings_profile_file,
    parse_saved_at,
    resolve_settings_precedence,
    save_settings_profile,
    settings_profile_dir,
    settings_profile_path,
    task_live_values,
    validate_config_name,
)
from src.ui.settings_registry import (
    apply_live_values_to_config,
    format_calibration,
    format_saved_at,
    initial_live_values,
)

LIVE = {"dwell.smoothing.alpha": 0.05, "dwell.jitter_tolerance_px": 100, "task.timeout_ms": 9000}


def test_round_trip(tmp_path):
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, {"target.radius_px": 120})
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got is not None
    assert got["live"] == LIVE
    assert got["structural"] == {"target.radius_px": 120}
    assert got["saved_at"]


def test_profiles_are_isolated_per_subject_and_per_task(tmp_path):
    """The clinical safety property: one child's tuning must never become
    another child's starting point, and one task's must not leak to another."""
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE)
    assert load_settings_profile(tmp_path, "S2", "click_grid") is None
    assert load_settings_profile(tmp_path, "S1", "scanning") is None


def test_missing_profile_returns_none(tmp_path):
    assert load_settings_profile(tmp_path, "nobody", "click_grid") is None


def test_malformed_profile_degrades_to_none_instead_of_raising(tmp_path):
    """A corrupt profile must not be able to block a session."""
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all", encoding="utf-8")
    assert load_settings_profile(tmp_path, "S1", "click_grid") is None


def test_profile_of_the_wrong_shape_degrades_to_none(tmp_path):
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_settings_profile(tmp_path, "S1", "click_grid") is None


def test_newest_save_wins_on_load_and_earlier_saves_are_kept(tmp_path):
    """S10.12: every save is its own file; the automatic path takes the newest."""
    first = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.5})
    second = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.1})
    assert first != second
    assert first.is_file() and second.is_file()
    assert first.parent == second.parent == settings_profile_dir(tmp_path, "S1", "click_grid")
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["live"] == {"dwell.smoothing.alpha": 0.1}
    assert got["path"] == str(second)


# -- S10.12: a dated history of versions -------------------------------------


def _write_version(directory, name, saved_at, alpha, subject="S1", task="click_grid"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        json.dumps(
            {
                "subject_id": subject,
                "task_id": task,
                "saved_at": saved_at,
                "live": {"dwell.smoothing.alpha": alpha},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_versions_are_ordered_by_saved_at_not_filename(tmp_path):
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    older = _write_version(d, "zzz.json", "2026-09-17T10:00:00+08:00", 0.1)
    newer = _write_version(d, "aaa.json", "2026-09-18T10:00:00+08:00", 0.3)
    assert list_settings_profiles(tmp_path, "S1", "click_grid") == [newer, older]
    assert load_settings_profile(tmp_path, "S1", "click_grid")["live"]["dwell.smoothing.alpha"] == 0.3


def test_legacy_flat_file_is_one_more_version_and_never_rewritten(tmp_path):
    """Profiles saved before S10.12 live at <subject>/<task>.json; they must
    stay loadable, sort by their own timestamp, and stop being the write target."""
    legacy = settings_profile_path(tmp_path, "S1", "click_grid")
    _write_version(legacy.parent, legacy.name, "2026-09-11T10:00:00+00:00", 0.7)
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    older = _write_version(d, "2026-09-10_10-00-00.json", "2026-09-10T10:00:00+08:00", 0.1)
    assert list_settings_profiles(tmp_path, "S1", "click_grid") == [legacy, older]
    before = legacy.read_text(encoding="utf-8")
    new = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.9})
    assert new.parent == d
    assert legacy.read_text(encoding="utf-8") == before
    assert list_settings_profiles(tmp_path, "S1", "click_grid")[0] == new


def test_unreadable_versions_are_skipped_not_fatal(tmp_path):
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    good = _write_version(d, "2026-09-17_10-00-00.json", "2026-09-17T10:00:00+08:00", 0.1)
    d.joinpath("broken.json").write_text("{not json", encoding="utf-8")
    d.joinpath("notes.txt").write_text("ignored", encoding="utf-8")
    assert list_settings_profiles(tmp_path, "S1", "click_grid") == [good]


def test_no_versions_means_none(tmp_path):
    assert list_settings_profiles(tmp_path, "S1", "click_grid") == []
    assert load_settings_profile(tmp_path, "S1", "click_grid") is None


def test_same_second_saves_never_overwrite(tmp_path, monkeypatch):
    import src.engine.settings_profile as mod

    class _Frozen(mod.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 18, 14, 32, 5).astimezone()

    monkeypatch.setattr(mod, "datetime", _Frozen)
    a = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.1})
    b = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.2})
    assert a.name == "2026-09-18_14-32-05.json"
    assert b.name == "2026-09-18_14-32-05_2.json"
    assert load_settings_profile_file(a)["live"]["dwell.smoothing.alpha"] == 0.1


def test_saved_at_is_local_time_with_offset(tmp_path):
    path = save_settings_profile(tmp_path, "S1", "click_grid", LIVE)
    saved_at = load_settings_profile_file(path)["saved_at"]
    parsed = parse_saved_at(saved_at)
    assert parsed is not None and parsed.utcoffset() is not None
    # The filename is the picker's label (S10.12 decision 2): it must show
    # the same local wall-clock time the timestamp does.
    assert path.stem.startswith(parsed.strftime("%Y-%m-%d_%H-%M-%S"))


def test_loaded_file_carries_identity_for_refusal_checks(tmp_path):
    d = settings_profile_dir(tmp_path, "OTHER", "scanning")
    path = _write_version(d, "v.json", "2026-09-17T10:00:00+08:00", 0.1, subject="OTHER", task="scanning")
    got = load_settings_profile_file(path)
    assert got["subject_id"] == "OTHER"
    assert got["task_id"] == "scanning"
    assert got["path"] == str(path)
    assert load_settings_profile_file(tmp_path / "missing.json") is None


def test_parse_saved_at_handles_legacy_utc_naive_and_garbage():
    assert parse_saved_at("").__class__.__name__ == "NoneType"
    assert parse_saved_at("not a date") is None
    naive = parse_saved_at("2026-09-10")
    assert naive is not None and naive.utcoffset() is not None  # treated as UTC
    utc = parse_saved_at("2026-09-16T20:40:01+00:00")
    local = parse_saved_at("2026-09-17T04:40:01+08:00")
    assert utc == local  # same instant


def test_format_saved_at_renders_the_local_date_not_the_utc_one():
    """S10.12.2: the same instant, written by a legacy (UTC) and a new (local)
    profile, must display identically -- the bug was slicing the UTC string."""
    utc = "2026-09-16T20:40:01+00:00"
    local = "2026-09-17T04:40:01+08:00"
    assert format_saved_at(utc) == format_saved_at(local)
    assert format_saved_at(utc, with_time=False) == format_saved_at(local, with_time=False)
    assert format_saved_at("") == ""
    assert format_saved_at("garbage") == ""
    assert len(format_saved_at(local, with_time=False)) == 5  # "MM/DD"


# -- applying a profile back onto a config ------------------------------------


def test_apply_round_trips_through_initial_live_values():
    """apply_live_values_to_config must be the exact inverse of
    initial_live_values, or a restored setting is silently dropped."""
    config = {
        "dwell": {"threshold_ms": 800, "smoothing": {"alpha": 0.22}},
        "task": {"timeout_ms": 8000, "motion": {"speed_frac_per_s": 0.20}},
    }
    values = initial_live_values(config)
    values["dwell.smoothing.alpha"] = 0.05
    values["task.timeout_ms"] = 9000
    values["motion.speed_frac_per_s"] = 0.44
    apply_live_values_to_config(config, values)
    assert initial_live_values(config)["dwell.smoothing.alpha"] == 0.05
    assert initial_live_values(config)["task.timeout_ms"] == 9000
    assert initial_live_values(config)["motion.speed_frac_per_s"] == 0.44


def test_motion_keys_land_under_task_not_at_top_level():
    """The specific trap apply_live_values_to_config exists to avoid: the key
    says `motion.` but the value is read from config['task']['motion']."""
    config = {"task": {"motion": {"speed_frac_per_s": 0.20}}}
    apply_live_values_to_config(config, {"motion.speed_frac_per_s": 0.9})
    assert config["task"]["motion"]["speed_frac_per_s"] == 0.9
    assert "motion" not in config


def test_unknown_keys_are_ignored():
    """A profile written by a different build must not break the run."""
    config = {"dwell": {"smoothing": {"alpha": 0.22}}}
    apply_live_values_to_config(config, {"dwell.no_such_setting": 1, "totally.made.up": 2})
    assert config == {"dwell": {"smoothing": {"alpha": 0.22}}}


# -- calibration recorded with a profile (S10.5.5) ----------------------------
# Descriptive only: nothing reads it back to change behaviour. The point is
# that settings tuned under a poor calibration may be compensating for bad
# tracking rather than suiting the child, and re-applying them under a good
# calibration would be wrong.


def test_calibration_is_stored_and_returned(tmp_path):
    save_settings_profile(
        tmp_path, "S1", "click_grid", LIVE, calibration={"error_px": 34.9, "points": 5}
    )
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["calibration"] == {"error_px": 34.9, "points": 5}


def test_profile_without_calibration_loads_with_an_empty_block(tmp_path):
    """A profile written before S10.5.5 must still load cleanly."""
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"live": LIVE, "saved_at": "2026-09-10"}), encoding="utf-8")
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["calibration"] == {}
    assert got["live"] == LIVE


def test_format_calibration_renders_both_parts():
    assert format_calibration({"error_px": 34.94, "points": 5}) == "35px error, 5pt"


def test_format_calibration_is_empty_when_unknown():
    """Must render nothing rather than "None px" for an older/partial profile."""
    assert format_calibration(None) == ""
    assert format_calibration({}) == ""
    assert format_calibration({"error_px": None, "points": None}) == ""


def test_format_calibration_handles_a_partial_block():
    assert format_calibration({"points": 9}) == "9pt"
    assert format_calibration({"error_px": 8.0}) == "8px error"


# -- known subject IDs, for the Subject-ID completer (S10.7.3 B) --------------


def test_known_subject_ids_unions_settings_and_calibrations(tmp_path):
    """A subject usually has a saved calibration before a settings profile, so
    reading only _settings would miss the first chance to mistype the ID."""
    save_settings_profile(tmp_path, "TUNED", "click_grid", LIVE)
    (tmp_path / "_calibrations" / "CALIBRATED_ONLY").mkdir(parents=True)
    (tmp_path / "_calibrations" / "TUNED").mkdir(parents=True)
    assert known_subject_ids(tmp_path) == ["CALIBRATED_ONLY", "TUNED"]


def test_known_subject_ids_is_empty_when_nothing_is_saved(tmp_path):
    assert known_subject_ids(tmp_path) == []
    assert known_subject_ids(tmp_path / "does" / "not" / "exist") == []


def _profile(live=None, structural=None, calibration=None, saved_at="2026-09-11T10:00:00+00:00"):
    return {
        "live": live or {},
        "structural": structural or {},
        "calibration": calibration or {},
        "saved_at": saved_at,
    }


def test_carried_values_beat_a_saved_profile(tmp_path):
    """The rule the Tasks-page badge exists to report honestly (S10.7.3 A):
    with both present, the run applies the carried values, so a badge naming
    the profile would be a promise the run does not keep."""
    carried = {"dwell.smoothing.alpha": 0.4}
    resolved = resolve_settings_precedence(carried, _profile(live=LIVE))
    assert resolved["source"] == "carried"
    assert resolved["live_overrides"] == carried


def test_profile_applies_when_nothing_was_carried():
    resolved = resolve_settings_precedence(None, _profile(live=LIVE, calibration={"points": 5}))
    assert resolved["source"] == "profile"
    assert resolved["live_overrides"] == LIVE
    assert resolved["calibration"] == {"points": 5}
    assert resolved["saved_at"]


def test_no_carried_values_and_no_profile_is_defaults():
    resolved = resolve_settings_precedence(None, None)
    assert resolved["source"] == "defaults"
    assert resolved["live_overrides"] is None


def test_an_empty_profile_is_defaults_not_profile():
    """``source`` must name what the run really uses. A profile file that holds
    nothing changes nothing, so reporting "profile" would overstate it."""
    assert resolve_settings_precedence(None, _profile())["source"] == "defaults"


def test_a_structural_only_profile_still_counts_as_a_profile():
    resolved = resolve_settings_precedence(None, _profile(structural={"target.radius_px": 120}))
    assert resolved["source"] == "profile"
    assert resolved["structural_overrides"] == {"target.radius_px": 120}


def test_an_explicit_settings_dialog_choice_outranks_the_profiles_structural_block():
    resolved = resolve_settings_precedence(
        None,
        _profile(live=LIVE, structural={"target.radius_px": 120}),
        {"target.radius_px": 200},
    )
    assert resolved["structural_overrides"] == {"target.radius_px": 200}


def test_structural_overrides_survive_the_carried_branch():
    """Carrying live values must not drop a structural choice made this sitting."""
    resolved = resolve_settings_precedence(
        {"dwell.smoothing.alpha": 0.4}, None, {"target.radius_px": 200}
    )
    assert resolved["structural_overrides"] == {"target.radius_px": 200}


def test_known_subject_ids_ignores_loose_files(tmp_path):
    """Only directories are subjects; a stray file next to them is not one."""
    (tmp_path / "_settings").mkdir()
    (tmp_path / "_settings" / "S1").mkdir()
    (tmp_path / "_settings" / "notes.txt").write_text("x", encoding="utf-8")
    assert known_subject_ids(tmp_path) == ["S1"]


# -- named configurations, schema v2 (SPEC-compass-task-flow.md 4B.4, AB8-AB10 data) ----------

ALL_LIVE = {
    "dwell.threshold_ms": 900, "dwell.visual_cursor": True, "dwell.progress_ring": True,
    "dwell.instant_feedback": True, "dwell.refractory_ms": 500, "dwell.jitter_tolerance_px": 40,
    "dwell.smoothing.enabled": True, "dwell.smoothing.alpha": 0.22, "task.timeout_ms": 8000,
    "task.inter_trial_interval_ms": 800, "motion.speed_frac_per_s": 0.2,
}


def _write_named(directory, filename, saved_at, name, alpha=0.1, schema=2, structural=None):
    """A version file as a v1 (no ``name`` key) or v2 save would leave it."""
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": schema,
        "subject_id": "S1",
        "task_id": "click_grid",
        "saved_at": saved_at,
        "live": {"dwell.smoothing.alpha": alpha},
        "structural": structural or {},
    }
    if name is not None:
        data["name"] = name
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_named_save_writes_the_name_and_schema_v2(tmp_path):
    """AB8, data part: a profile file with ``name`` and ``schema_version == 2``."""
    path = save_settings_profile(
        tmp_path, "S1", "click_grid", LIVE, {"trials": 6}, name="  Calm room  "
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == "Calm room"  # trimmed
    assert data["schema_version"] == 2 == PROFILE_SCHEMA_VERSION
    assert load_settings_profile_file(path)["name"] == "Calm room"


def test_a_save_without_a_name_has_an_empty_one(tmp_path):
    path = save_settings_profile(tmp_path, "S1", "click_grid", LIVE)
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == ""
    assert load_settings_profile_file(path)["name"] == ""


def test_a_schema_v1_file_has_no_name_and_still_loads(tmp_path):
    """AB10, data part: ``name == ""`` for v1, the name for v2."""
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    v1 = _write_named(d, "old.json", "2026-09-17T10:00:00+08:00", None, schema=1)
    v2 = _write_named(d, "new.json", "2026-09-18T10:00:00+08:00", "Window seat")
    got = load_settings_profile_file(v1)
    assert got["name"] == ""
    assert got["schema_version"] == 1
    assert got["live"] == {"dwell.smoothing.alpha": 0.1}
    assert load_settings_profile_file(v2)["name"] == "Window seat"
    assert load_settings_profile(tmp_path, "S1", "click_grid")["name"] == "Window seat"


def test_a_non_string_name_in_a_file_reads_as_no_name(tmp_path):
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    path = _write_named(d, "odd.json", "2026-09-17T10:00:00+08:00", None)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = ["not", "a", "string"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_settings_profile_file(path)["name"] == ""


@pytest.mark.parametrize(
    "bad",
    ["Standard", "standard", "  STANDARD ", "x" * (CONFIG_NAME_MAX_LEN + 1), "two\nlines", "a\x00b"],
)
def test_a_name_that_cannot_be_stored_is_refused_and_nothing_is_written(tmp_path, bad):
    with pytest.raises(ValueError):
        save_settings_profile(tmp_path, "S1", "click_grid", LIVE, name=bad)
    assert not settings_profile_dir(tmp_path, "S1", "click_grid").exists()


def test_validate_config_name_rules():
    assert validate_config_name("Calm") is None
    assert validate_config_name("x" * CONFIG_NAME_MAX_LEN) is None  # exactly the limit
    assert validate_config_name("  Calm  ") is None  # trimmed first
    assert validate_config_name("Standard 2") is None  # only the whole word is reserved
    assert "name" in validate_config_name("")
    assert "name" in validate_config_name("   ")
    assert validate_config_name(None) is not None
    assert "at most 40" in validate_config_name("x" * 41)
    assert "reserved" in validate_config_name("sTaNdArD")
    assert CONFIG_NAME_MAX_LEN == 40  # R10


def test_the_live_block_holds_only_keys_that_apply_to_the_task(tmp_path):
    """4B.4: a static task's file no longer carries ``motion.speed_frac_per_s``."""
    dirty = {**ALL_LIVE, "target.color": "#fff", "totally.made.up": 1}
    static = save_settings_profile(tmp_path, "S1", "click_static", dirty)
    follow = save_settings_profile(tmp_path, "S1", "follow_moving", dirty)
    live_static = load_settings_profile_file(static)["live"]
    live_follow = load_settings_profile_file(follow)["live"]
    assert "motion.speed_frac_per_s" not in live_static
    assert live_follow["motion.speed_frac_per_s"] == 0.2
    assert set(live_follow) == set(ALL_LIVE)
    assert set(live_static) == set(ALL_LIVE) - {"motion.speed_frac_per_s"}
    for live in (live_static, live_follow):
        assert "target.color" not in live and "totally.made.up" not in live


def test_task_live_values_does_not_touch_the_callers_dict():
    live = dict(ALL_LIVE)
    assert task_live_values("scanning", live) == {
        k: v for k, v in ALL_LIVE.items() if k != "motion.speed_frac_per_s"
    }
    assert live == ALL_LIVE


def test_the_structural_block_is_stored_exactly_as_given(tmp_path):
    """The caller passes the complete block (every control); the writer adds nothing."""
    block = {"trials": 6, "feedback": {"hit_sound": False, "miss_sound": True}}
    path = save_settings_profile(tmp_path, "S1", "click_grid", LIVE, block)
    assert load_settings_profile_file(path)["structural"] == block


def test_listing_gives_one_entry_per_name_newest_first_and_the_newest_values(tmp_path):
    """AB9, data part: Update adds a version, the old file stays, the list shows
    one entry for the name with the newest values."""
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    old_calm = _write_named(d, "a.json", "2026-09-15T10:00:00+08:00", "Calm", alpha=0.1)
    seat = _write_named(d, "b.json", "2026-09-16T10:00:00+08:00", "Window seat", alpha=0.2)
    new_calm = _write_named(d, "c.json", "2026-09-17T10:00:00+08:00", "Calm", alpha=0.3)

    found = list_named_configurations(tmp_path, "S1", "click_grid")
    assert [c.name for c in found] == ["Calm", "Window seat"]  # by each name's newest version
    assert all(isinstance(c, NamedConfig) for c in found)
    assert found[0].path == new_calm
    assert found[0].live == {"dwell.smoothing.alpha": 0.3}
    assert found[1].path == seat
    assert old_calm.is_file()  # history, not deleted
    assert found[0].saved_at == "2026-09-17T10:00:00+08:00"


def test_updating_a_name_through_the_writer_keeps_the_old_file(tmp_path):
    first = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.1},
                                  {"trials": 6}, name="Calm")
    second = save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.5},
                                   {"trials": 9}, name="Calm")
    assert first != second and first.is_file() and second.is_file()
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == "Calm"
    assert entry.path == second
    assert entry.live == {"dwell.smoothing.alpha": 0.5}
    assert entry.structural == {"trials": 9}


def test_names_compare_case_insensitively_and_keep_the_newest_spelling(tmp_path):
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    _write_named(d, "a.json", "2026-09-15T10:00:00+08:00", "Calm")
    _write_named(d, "b.json", "2026-09-16T10:00:00+08:00", "calm")
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == "calm"


def test_a_v1_profile_is_listed_as_saved_mm_dd_hh_mm_and_loads(tmp_path):
    """AB10: ``Saved MM/DD HH:MM`` in local time, so every old profile stays reachable."""
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    saved_at = "2026-09-17T10:00:00+08:00"
    v1 = _write_named(d, "2026-09-17_10-00-00.json", saved_at, None, schema=1,
                      structural={"trials": 12})
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == f"Saved {format_saved_at(saved_at)}"
    assert re.fullmatch(r"Saved \d\d/\d\d \d\d:\d\d", entry.name)
    assert entry.path == v1
    assert entry.live == {"dwell.smoothing.alpha": 0.1}
    assert entry.structural == {"trials": 12}


def test_the_pre_s10_12_flat_file_is_listed_too(tmp_path):
    legacy = settings_profile_path(tmp_path, "S1", "click_grid")
    _write_named(legacy.parent, legacy.name, "2026-09-11T10:00:00+00:00", None, schema=1)
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == f"Saved {format_saved_at('2026-09-11T10:00:00+00:00')}"
    assert entry.path == legacy


def test_an_unnamed_v2_save_is_listed_like_a_v1_file(tmp_path):
    path = save_settings_profile(tmp_path, "S1", "click_grid", LIVE)
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == f"Saved {format_saved_at(load_settings_profile_file(path)['saved_at'])}"


def test_a_stored_name_that_could_not_be_chosen_today_falls_back_to_the_label(tmp_path):
    """"Standard" is the computed defaults and never stored; a hand-edited file
    must not shadow it in the combo, yet must stay reachable."""
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    _write_named(d, "x.json", "2026-09-17T10:00:00+08:00", "Standard")
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name.startswith("Saved ")


def test_an_unparseable_timestamp_is_labelled_with_the_file_name(tmp_path):
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    _write_named(d, "mystery.json", "not a date", None, schema=1)
    (entry,) = list_named_configurations(tmp_path, "S1", "click_grid")
    assert entry.name == "Saved mystery"


def test_effective_config_name_prefers_a_valid_name():
    assert effective_config_name({"name": "Calm", "saved_at": ""}) == "Calm"
    assert effective_config_name({"name": "", "saved_at": "2026-09-17T10:00:00+08:00"}).startswith(
        "Saved "
    )
    assert effective_config_name({}, "folder/old.json") == "Saved old"


def test_the_listing_is_per_subject_and_per_task_and_skips_unreadable_files(tmp_path):
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, name="Calm")
    assert list_named_configurations(tmp_path, "S2", "click_grid") == []
    assert list_named_configurations(tmp_path, "S1", "scanning") == []
    d = settings_profile_dir(tmp_path, "S1", "click_grid")
    d.joinpath("broken.json").write_text("{not json", encoding="utf-8")
    assert [c.name for c in list_named_configurations(tmp_path, "S1", "click_grid")] == ["Calm"]
    assert list_named_configurations(tmp_path / "nowhere", "S1", "click_grid") == []


def test_a_named_save_does_not_change_the_automatic_newest_rule(tmp_path):
    """The listing does not replace S10.3's ``load_settings_profile`` (still the newest file)."""
    save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.1}, name="A")
    save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.2}, name="B")
    assert load_settings_profile(tmp_path, "S1", "click_grid")["name"] == "B"
    assert [c.name for c in list_named_configurations(tmp_path, "S1", "click_grid")] == ["B", "A"]
