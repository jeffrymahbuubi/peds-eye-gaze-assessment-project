"""SPEC-compass-task-flow.md 4B.4 / AB8 / AB9: what Save & Continue has to do with a
configuration name, as a pure decision (no Qt, no files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.config import load_task_config
from src.engine.settings_profile import NamedConfig
from src.ui.config_save import (
    ASK_NEW_NAME,
    ASK_UPDATE,
    NEW_CONFIGURATION,
    STORE_STANDARD,
    UNCHANGED,
    decide_save,
    next_custom_name,
    same_values,
)
from src.ui.settings_snapshot import settings_snapshot

TASK = "click_grid"


@pytest.fixture(scope="module")
def config():
    return load_task_config(TASK)


@pytest.fixture(scope="module")
def standard(config):
    return settings_snapshot(TASK, config)


def changed(standard, *, dwell=1200, size="large"):
    """The standard values with a live and a structural option changed."""
    live = {**standard["live"], "dwell.threshold_ms": dwell}
    structural = {**standard["structural"], "target": {"size": size}}
    return live, structural


def named(name, live, structural, saved_at="2026-10-06T10:00:00+08:00") -> NamedConfig:
    return NamedConfig(name, saved_at, Path("x.json"), live, structural)


def decide(config, standard, name, live, structural, saved=()):
    return decide_save(
        TASK,
        config,
        name,
        live,
        structural,
        standard,
        {c.name.casefold(): c for c in saved},
    )


# -- Standard ------------------------------------------------------------------------------


def test_standard_with_untouched_values_stores_nothing_new(config, standard):
    decision = decide(config, standard, "Standard", standard["live"], standard["structural"])
    assert decision.kind == STORE_STANDARD and decision.name == "Standard"


@pytest.mark.parametrize("spelling", ["standard", "STANDARD", "  Standard  "])
def test_the_name_standard_is_matched_case_insensitively(config, standard, spelling):
    decision = decide(config, standard, spelling, standard["live"], standard["structural"])
    assert decision.kind == STORE_STANDARD and decision.name == "Standard"


def test_standard_with_changed_values_must_be_renamed(config, standard):
    live, structural = changed(standard)
    decision = decide(config, standard, "Standard", live, structural)
    assert decision.kind == ASK_NEW_NAME


def test_a_changed_live_value_alone_is_enough(config, standard):
    live = {**standard["live"], "dwell.smoothing.alpha": 0.5}
    assert decide(config, standard, "Standard", live, standard["structural"]).kind == ASK_NEW_NAME


def test_a_changed_structural_value_alone_is_enough(config, standard):
    structural = {**standard["structural"], "trials": 7}
    assert decide(config, standard, "Standard", standard["live"], structural).kind == ASK_NEW_NAME


# -- a name that is new -------------------------------------------------------------------------


def test_a_new_name_writes_a_profile(config, standard):
    live, structural = changed(standard)
    decision = decide(config, standard, "Large targets", live, structural)
    assert decision.kind == NEW_CONFIGURATION and decision.name == "Large targets"
    assert decision.existing is None


def test_a_new_name_with_untouched_values_still_writes_a_profile(config, standard):
    # The name is the thing being saved: the operator may want "Defaults for Ana".
    decision = decide(config, standard, "Ana", standard["live"], standard["structural"])
    assert decision.kind == NEW_CONFIGURATION


def test_the_name_is_trimmed(config, standard):
    live, structural = changed(standard)
    assert decide(config, standard, "  Large targets ", live, structural).name == "Large targets"


# -- a name that exists ----------------------------------------------------------------------------


def test_an_existing_name_with_the_same_values_needs_no_new_file(config, standard):
    live, structural = changed(standard)
    saved = [named("Large targets", live, structural)]
    decision = decide(config, standard, "Large targets", live, structural, saved)
    assert decision.kind == UNCHANGED
    assert decision.existing is saved[0]


def test_an_existing_name_with_different_values_asks(config, standard):
    live, structural = changed(standard)
    saved = [named("Large targets", live, structural)]
    other_live, other_structural = changed(standard, dwell=1500)
    decision = decide(config, standard, "Large targets", other_live, other_structural, saved)
    assert decision.kind == ASK_UPDATE and decision.name == "Large targets"


def test_an_existing_name_keeps_the_spelling_of_its_newest_version(config, standard):
    live, structural = changed(standard)
    saved = [named("Large targets", live, structural)]
    decision = decide(config, standard, "LARGE TARGETS", live, structural, saved)
    assert decision.kind == UNCHANGED and decision.name == "Large targets"


def test_a_saved_version_that_lacks_keys_compares_as_the_default_for_them(config, standard):
    # An older file holds only what was changed; the rest reads as the task default.
    saved = [named("Slow", {"dwell.threshold_ms": 1200}, {"target": {"size": "large"}})]
    live, structural = changed(standard)  # the same two changes, everything else default
    assert decide(config, standard, "Slow", live, structural, saved).kind == UNCHANGED


def test_an_unlisted_name_that_is_not_saved_yet_is_new(config, standard):
    live, structural = changed(standard)
    saved = [named("Other", live, structural)]
    assert decide(config, standard, "Large targets", live, structural, saved).kind == NEW_CONFIGURATION


# -- same_values and next_custom_name ---------------------------------------------------------------------


def test_same_values_ignores_keys_no_setting_knows(config, standard):
    a = {"live": {**standard["live"], "not.a.setting": 1}, "structural": standard["structural"]}
    assert same_values(TASK, config, a, standard)


def test_same_values_sees_a_difference(config, standard):
    live, structural = changed(standard)
    assert not same_values(TASK, config, {"live": live, "structural": structural}, standard)


def test_next_custom_name_starts_at_one_and_skips_taken_numbers():
    assert next_custom_name([]) == "Custom 1"
    assert next_custom_name(["Custom 1", "custom 2", "Large targets"]) == "Custom 3"
    assert next_custom_name(["Custom 2"]) == "Custom 1"
