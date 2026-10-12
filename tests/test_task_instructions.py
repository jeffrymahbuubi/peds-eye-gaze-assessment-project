"""SPEC-compass-task-flow.md 4C.3 / AC1: the read-aloud instructions on the Start
page match the test's own settings."""

from __future__ import annotations

import pytest

from src.engine.config import load_task_config
from src.engine.task_info import TASK_INFO
from src.ui.settings_registry import initial_live_values
from src.ui.task_instructions import Instructions, build_instructions, format_seconds

TASKS = list(TASK_INFO)
# The three that select a target; Follow the Target has its own wording (W1) and no NOTE line,
# tested at the end of this file.
SELECTING = [t for t in TASKS if t != "follow_moving"]


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
        assert text.strip() == text
        assert text or (task_id == "follow_moving" and text is ins.note)  # Follow has no NOTE


@pytest.mark.parametrize("task_id", SELECTING)
def test_the_tests_own_dwell_and_timeout_are_spoken(task_id):
    ins = build_instructions(task_id, cfg_for(task_id), values(dwell=800, timeout=8000))
    assert sum("0.8 seconds" in s for s in ins.steps) == 1
    assert "8 seconds" in ins.note

    ins = build_instructions(task_id, cfg_for(task_id), values(dwell=1000, timeout=12500))
    assert sum("1 second" in s and "1 seconds" not in s for s in ins.steps) == 1
    assert "12.5 seconds" in ins.note


@pytest.mark.parametrize("task_id", SELECTING)
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
    assert ins.note == "" if task_id == "follow_moving" else ins.note.startswith("NOTE: If the ")


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
        if task_id != "follow_moving":  # (Follow has no NOTE line)
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


# -- Follow the Target (SPEC-input-selection-and-follow.md W1) ------------------------------------


def follow_ins(*, glow=True, pointer="gaze", **live):
    cfg = cfg_for("follow_moving")
    cfg["input"] = {"mode": "eye"}
    cfg["task"]["input"] = {"pointer": pointer}
    cfg["task"].setdefault("feedback", {})["target_glow"] = glow
    return build_instructions("follow_moving", cfg, {**values(), **live})


def test_follow_reads_the_w1_wording_with_the_trial_duration():
    ins = follow_ins(**{"task.timeout_ms": 10000})
    assert ins.steps == (
        "The small dot on the screen shows where you are looking. "
        "A circle will appear and start to move across the screen.",
        "Follow the moving circle with your eyes and keep looking at it while it moves.",
        "The circle glows while you are looking at it.",
        "After about 10 seconds a new circle will appear. Continue until no more circles appear.",
    )
    assert ins.heading == "Instructions for the Follow the Target test:"
    assert ins.note == ""  # nothing to select, so no timeout NOTE


def test_follows_glow_step_is_read_only_with_the_glow_on():
    on, off = follow_ins(glow=True), follow_ins(glow=False)
    assert len(on.steps) == 4 and len(off.steps) == 3
    assert not any("glows" in s for s in off.steps)
    assert [s for s in on.steps if "glows" not in s] == list(off.steps)


def test_follow_speaks_the_tests_own_duration_and_no_selection_words():
    ins = follow_ins(**{"task.timeout_ms": 12500})
    assert "After about 12.5 seconds a new circle will appear." in ins.steps[-1]
    text = " ".join([*ins.steps, ins.note]).lower().replace("glows", "")
    for word in ("select", "ring", "dwell", "click", "press", "white"):
        assert word not in text, word


def test_follow_ignores_the_dwell_settings():
    a = follow_ins(**{"dwell.threshold_ms": 300, "dwell.progress_ring": True})
    b = follow_ins(**{"dwell.threshold_ms": 2000, "dwell.progress_ring": False})
    assert a.steps == b.steps


def test_follow_with_the_mouse_points_and_follows_with_the_mouse():
    ins = follow_ins(pointer="mouse")
    assert ins.steps[0] == (
        "Move the mouse to point at the screen. A circle will appear and start to move across the screen."
    )
    assert ins.steps[1] == "Follow the moving circle with the mouse and keep pointing at it while it moves."
    assert ins.steps[2] == "The circle glows while you are pointing at it."


# -- Choice-making: the wording follows the prompt mode (SPEC-scene-cause-effect-task.md 3.7, P7) -----------

PROMPT_STEP = {
    "voice": 'You will hear which button to choose, for example "Make the balloons pop!"',
    "text": 'You will see which button to choose at the top of the picture, for example "Make the balloons pop!"',
    "voice_text": 'You will hear and see which button to choose, for example "Make the balloons pop!"',
}
PROMPT_END = {"voice": "are spoken", "text": "appear", "voice_text": "are given"}
CHOICE_NOTE = (
    "NOTE: If the button is not selected within 8 seconds, the picture will show what that"
    " button does and the next prompt will follow."
)


def choice_cfg(mode="<absent>", *, pointer="gaze", selection="dwell"):
    cfg = cfg_for("choice_making")
    cfg["input"] = {"mode": "eye"}  # whatever the local default.yaml says
    cfg["task"]["input"] = {"pointer": pointer, "selection": selection}
    cfg["task"].setdefault("feedback", {})["target_glow"] = True
    cfg["task"].pop("prompt_mode", None)
    if mode != "<absent>":
        cfg["task"]["prompt_mode"] = mode
    return cfg


def choice_ins(mode="<absent>", *, pointer="gaze", selection="dwell", **live):
    return build_instructions("choice_making", choice_cfg(mode, pointer=pointer, selection=selection), {**values(), **live})


def choice_steps(mode, third, first="A picture will appear on the screen, with buttons on each side."):
    """The four read-aloud steps of Choice-making for ``mode``: ``third`` is the selection step."""
    return (
        first,
        PROMPT_STEP[mode],
        third,
        f"When it is selected, the picture will come alive. Continue until no more prompts {PROMPT_END[mode]}.",
    )


DOT = "The small dot on the screen shows where you are looking. "
MOUSE_DOT = "Move the mouse to point at the screen. "
DWELL_STEP = "Look at that button and keep looking at it for about 0.8 seconds. A ring will fill up around it."
POINT_STEP = "Point at that button and keep pointing at it for about 0.8 seconds. A ring will fill up around it."
SWITCH_STEP = "Look at that button, then press the switch. The button glows while you are looking at it."
POINT_SWITCH_STEP = "Point at that button, then press the switch. The button glows while you are pointing at it."


@pytest.mark.parametrize("mode", ["voice", "text", "voice_text"])
@pytest.mark.parametrize(
    "pointer,selection,third,dot",
    [
        ("gaze", "dwell", DWELL_STEP, DOT),
        ("gaze", "switch", SWITCH_STEP, DOT),
        ("mouse", "dwell", POINT_STEP, MOUSE_DOT),
        ("mouse", "switch", POINT_SWITCH_STEP, MOUSE_DOT),
    ],
)
def test_choice_making_wording_follows_the_prompt_mode_for_every_input(mode, pointer, selection, third, dot):
    ins = choice_ins(mode, pointer=pointer, selection=selection)
    first = choice_steps(mode, third)[0]
    assert ins.steps == choice_steps(mode, third, first=dot + first)
    assert ins.note == CHOICE_NOTE  # "the next prompt will follow" stays in every mode
    assert ins.heading == "Instructions for the Choice-making test:"


def test_choice_making_voice_is_the_wording_it_had_before_the_prompt_mode_existed():
    assert choice_ins("voice").steps == (
        DOT + "A picture will appear on the screen, with buttons on each side.",
        'You will hear which button to choose, for example "Make the balloons pop!"',
        DWELL_STEP,
        "When it is selected, the picture will come alive. Continue until no more prompts are spoken.",
    )


@pytest.mark.parametrize("unknown", ["banana", "", "VOICE", "voice text", None, 5, ["text"]])
def test_choice_making_with_an_unknown_prompt_mode_reads_the_voice_wording(unknown):
    assert choice_ins(unknown) == choice_ins("voice")


def test_choice_making_without_a_prompt_mode_reads_the_voice_wording():
    assert choice_ins() == choice_ins("voice")


@pytest.mark.parametrize("mode", ["voice", "text", "voice_text"])
def test_choice_making_only_the_prompt_step_and_the_ending_change_with_the_mode(mode):
    voice, other = choice_ins("voice"), choice_ins(mode)
    assert other.steps[0] == voice.steps[0] and other.steps[2] == voice.steps[2]
    assert other.note == voice.note and other.clinician == voice.clinician
    assert other.steps[1] == PROMPT_STEP[mode]
    assert other.steps[3].endswith(f"no more prompts {PROMPT_END[mode]}.")


def test_the_text_mode_reads_nothing_about_hearing():
    text = " ".join(choice_ins("text").steps).lower()
    assert "hear" not in text and "spoken" not in text
    both = " ".join(choice_ins("voice_text").steps)
    assert "hear and see" in both and "spoken" not in both


@pytest.mark.parametrize("mode", ["voice", "text", "voice_text", "banana"])
@pytest.mark.parametrize("ring", [True, False])
@pytest.mark.parametrize("dot", [True, False])
@pytest.mark.parametrize("pointer,selection", [("gaze", "dwell"), ("gaze", "switch"), ("mouse", "dwell")])
def test_choice_making_leaves_no_placeholder_in_any_mode(mode, ring, dot, pointer, selection):
    ins = choice_ins(mode, pointer=pointer, selection=selection, **{"dwell.progress_ring": ring, "dwell.visual_cursor": dot})
    assert len(ins.steps) == 4
    for text in every_text(ins):
        assert "{" not in text and "}" not in text and text.strip() == text


@pytest.mark.parametrize("task_id", [t for t in TASKS if t != "choice_making"])
def test_the_prompt_mode_does_not_change_the_other_tests(task_id):
    plain = build_instructions(task_id, cfg_for(task_id), values())
    cfg = cfg_for(task_id)
    cfg["task"]["prompt_mode"] = "text"
    assert build_instructions(task_id, cfg, values()) == plain


def test_a_tests_stored_prompt_mode_reaches_the_instructions_through_the_merged_config():
    from src.ui.settings_snapshot import merged_config

    base = choice_cfg("voice")
    cfg = merged_config(base, None, {"prompt_mode": "text"})
    assert cfg["task"]["prompt_mode"] == "text"
    assert build_instructions("choice_making", cfg, values()).steps[1] == PROMPT_STEP["text"]
    assert base["task"]["prompt_mode"] == "voice"  # the stored config is not touched


def test_choice_making_does_not_touch_its_inputs():
    import copy

    cfg, vals = choice_cfg("text"), values()
    before = (copy.deepcopy(cfg), copy.deepcopy(vals))
    build_instructions("choice_making", cfg, vals)
    assert (cfg, vals) == before
