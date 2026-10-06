"""SPEC-compass-task-flow.md 4C.3 / AC1: the read-aloud instructions on the Start
page match the test's own settings."""

from __future__ import annotations

import pytest

from src.engine.config import load_task_config
from src.engine.task_info import TASK_INFO
from src.ui.settings_registry import initial_live_values
from src.ui.task_instructions import Instructions, build_instructions, format_seconds

TASKS = list(TASK_INFO)


def values(dwell=800, timeout=8000, ring=True, dot=True) -> dict:
    return {
        "dwell.threshold_ms": dwell,
        "task.timeout_ms": timeout,
        "dwell.progress_ring": ring,
        "dwell.visual_cursor": dot,
    }


def cfg_for(task_id: str, trials: int | None = None) -> dict:
    cfg = load_task_config(task_id)
    if trials is not None:
        cfg["task"]["trials"] = trials
    return cfg


def every_text(ins: Instructions) -> list[str]:
    return [ins.heading, *ins.steps, ins.note, *ins.clinician]


# -- seconds -----------------------------------------------------------------


@pytest.mark.parametrize(
    "ms,text",
    [
        (800, "0.8 seconds"),
        (1000, "1 second"),
        (1500, "1.5 seconds"),
        (2000, "2 seconds"),
        (8000, "8 seconds"),
        (12000, "12 seconds"),
        (300, "0.3 seconds"),
        (850, "0.85 seconds"),
        (1000.0, "1 second"),
    ],
)
def test_format_seconds(ms, text):
    assert format_seconds(ms) == text


# -- AC1 ---------------------------------------------------------------------


@pytest.mark.parametrize("task_id", TASKS)
@pytest.mark.parametrize("ring", [True, False])
@pytest.mark.parametrize("dot", [True, False])
def test_no_placeholder_is_left_unreplaced(task_id, ring, dot):
    ins = build_instructions(task_id, cfg_for(task_id), values(ring=ring, dot=dot))
    for text in every_text(ins):
        assert "{" not in text and "}" not in text, text
        assert text.strip() == text and text


@pytest.mark.parametrize("task_id", TASKS)
def test_the_tests_own_dwell_and_timeout_are_spoken(task_id):
    ins = build_instructions(task_id, cfg_for(task_id), values(dwell=800, timeout=8000))
    assert sum("0.8 seconds" in s for s in ins.steps) == 1
    assert "8 seconds" in ins.note

    ins = build_instructions(task_id, cfg_for(task_id), values(dwell=1000, timeout=12500))
    assert sum("1 second" in s and "1 seconds" not in s for s in ins.steps) == 1
    assert "12.5 seconds" in ins.note


@pytest.mark.parametrize("task_id", TASKS)
def test_the_ring_sentence_only_when_the_progress_ring_is_on(task_id):
    on = build_instructions(task_id, cfg_for(task_id), values(ring=True))
    off = build_instructions(task_id, cfg_for(task_id), values(ring=False))
    ring = "A ring will fill up around it."
    assert sum(ring in s for s in on.steps) == 1
    assert not any("ring will fill" in s for s in off.steps)
    # Switching it off only removes that clause.
    assert [s.replace(" " + ring, "") for s in on.steps] == list(off.steps)


@pytest.mark.parametrize("task_id", TASKS)
def test_the_dot_sentence_only_when_the_gaze_cursor_is_on_and_leads_step_one(task_id):
    on = build_instructions(task_id, cfg_for(task_id), values(dot=True))
    off = build_instructions(task_id, cfg_for(task_id), values(dot=False))
    dot = "The small dot on the screen shows where you are looking."
    assert on.steps[0].startswith(dot + " ")
    assert not any("small dot" in s for s in off.steps)
    assert on.steps[0] == dot + " " + off.steps[0]
    assert on.steps[1:] == off.steps[1:]


@pytest.mark.parametrize("task_id", TASKS)
def test_steps_are_plain_sentences_the_page_numbers_them(task_id):
    ins = build_instructions(task_id, cfg_for(task_id), values(dot=False))
    assert len(ins.steps) == 4
    assert not any(s[:2] in ("1.", "2.", "3.", "4.") for s in ins.steps)
    assert ins.note.startswith("NOTE: If the ")


def test_the_heading_names_the_task():
    for task_id, (name, _desc) in TASK_INFO.items():
        ins = build_instructions(task_id, cfg_for(task_id), values())
        assert ins.heading == f"Instructions for the {name} test:"


def test_each_task_speaks_about_its_own_stimulus():
    nouns = {
        "click_static": "circle",
        "click_grid": "square",
        "follow_moving": "moving circle",
        "scanning": "shape",
    }
    for task_id, noun in nouns.items():
        ins = build_instructions(task_id, cfg_for(task_id), values())
        assert noun in " ".join(ins.steps)
        assert noun.split()[-1] in ins.note
    assert len({build_instructions(t, cfg_for(t), values()).steps for t in nouns}) == 4


def test_the_clinician_block_is_the_same_for_every_task_apart_from_the_trial_count():
    blocks = {
        task_id: build_instructions(task_id, cfg_for(task_id, trials=7), values()).clinician
        for task_id in TASKS
    }
    assert len(set(blocks.values())) == 1
    pause, practice, start = blocks["click_static"]
    assert 'click the "Pause" button, or press ALT-P' in pause
    assert 'click the "Quit" button, or press ALT-Q' in pause
    assert practice == (
        "Practice runs 3 targets with these settings. Nothing is recorded. "
        "Repeat it as often as needed."
    )
    assert start == 'Start records 7 trials. Check that the bottom bar says "tracking OK" before you begin.'


def test_the_trial_count_is_the_configured_one():
    ins = build_instructions("click_grid", cfg_for("click_grid", trials=18), values())
    assert "Start records 18 trials." in ins.clinician[2]


def test_values_may_be_partial_and_fall_back_to_the_configuration():
    cfg = cfg_for("click_static")
    base = initial_live_values(cfg)
    ins = build_instructions("click_static", cfg, {"dwell.threshold_ms": 1500})
    assert any("1.5 seconds" in s for s in ins.steps)
    assert format_seconds(base["task.timeout_ms"]) in ins.note
    # Omitted altogether: everything comes from the configuration.
    ins = build_instructions("click_static", cfg)
    assert any(format_seconds(base["dwell.threshold_ms"]) in s for s in ins.steps)


def test_an_unknown_task_is_an_error():
    with pytest.raises(KeyError):
        build_instructions("not_a_task", {"task": {}}, values())


def test_it_does_not_touch_its_inputs():
    cfg = cfg_for("scanning")
    vals = values()
    import copy

    before = (copy.deepcopy(cfg), copy.deepcopy(vals))
    build_instructions("scanning", cfg, vals)
    assert (cfg, vals) == before
