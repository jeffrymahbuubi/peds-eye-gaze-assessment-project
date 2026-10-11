"""SPEC-scene-cause-effect-task.md N3 (idle life), Qt-free: blinks of about 150 ms at random 2-6 s
intervals per character, the bob of the balloons and the cloud, and the three ``idle_animation``
modes. The clock is fed by the renderer (it stops when the test is paused), so it is driven here by
hand."""

from __future__ import annotations

import random

import pytest

from src.tasks.choice_idle import BLINK_GAP_S, BLINK_MS, IdleLife
from src.tasks.choice_scene_defaults import default_manifest

MANIFEST = default_manifest()
STEP = 0.01


def life(mode="blinks", seed=3, characters=("a", "b", "c")):
    return IdleLife(mode, characters, {"balloons": (0.006, 3.2), "cloud": (0.004, 5.0)}, random.Random(seed))


def blink_spans(idle, character, seconds):
    """(start, end) of each blink of ``character`` seen while stepping ``seconds`` of idle time."""
    spans, start, t = [], None, 0.0
    while t < seconds:
        idle.advance(STEP)
        t += STEP
        closed = idle.is_blinking(character)
        if closed and start is None:
            start = t
        if not closed and start is not None:
            spans.append((start, t))
            start = None
    return spans


def test_nobody_blinks_at_the_start_and_off_never_blinks_or_bobs():
    idle = life()
    assert idle.blinking() == [] and idle.bob_offset("balloons") == 0.0
    off = life("off")
    for _ in range(3000):
        off.advance(STEP)
        assert off.blinking() == [] and off.bob_offset("balloons") == 0.0 and off.bobbing() == []


def test_a_blink_lasts_about_150_ms_and_the_gaps_are_2_to_6_seconds():
    spans = blink_spans(life(), "a", 120.0)
    assert len(spans) >= 15
    for start, end in spans:
        assert end - start == pytest.approx(BLINK_MS / 1000, abs=2 * STEP)
    assert 2.0 - 2 * STEP <= spans[0][0] <= 6.0 + 2 * STEP  # the first one is also 2-6 s in
    gaps = [b[0] - a[1] for a, b in zip(spans, spans[1:], strict=False)]
    assert min(gaps) >= BLINK_GAP_S[0] - 2 * STEP and max(gaps) <= BLINK_GAP_S[1] + 2 * STEP


def test_each_character_blinks_on_its_own_timer():
    idle = life(seed=11)
    a, b = blink_spans(idle, "a", 60.0), blink_spans(life(seed=11), "b", 60.0)
    assert a and b and a != b


def test_it_is_deterministic_for_a_seed():
    assert blink_spans(life(seed=5), "a", 30.0) == blink_spans(life(seed=5), "a", 30.0)
    assert blink_spans(life(seed=5), "a", 30.0) != blink_spans(life(seed=6), "a", 30.0)


def test_time_only_moves_forward_and_a_zero_step_changes_nothing():
    idle = life()
    idle.advance(1.0)
    idle.advance(0.0)
    idle.advance(-5.0)
    assert idle.t == 1.0


def test_blinks_mode_does_not_bob_and_blinks_bob_bobs_within_the_amplitude():
    plain = life("blinks")
    bob = life("blinks_bob")
    seen = []
    for _ in range(1000):
        plain.advance(STEP)
        bob.advance(STEP)
        assert plain.bob_offset("balloons") == 0.0
        seen.append(bob.bob_offset("balloons"))
        assert abs(bob.bob_offset("cloud")) <= 0.004 + 1e-12
    assert max(seen) > 0.0055 and min(seen) < -0.0055 and max(abs(v) for v in seen) <= 0.006 + 1e-12
    assert bob.bob_offset("rainbow") == 0.0  # only the balloons and the cloud
    assert bob.bobbing() == ["balloons", "cloud"] and plain.bobbing() == []
    assert bob.blinking() is not None  # blinks_bob keeps the blinks too


def test_the_balloons_and_the_cloud_do_not_bob_in_step():
    idle = life("blinks_bob", seed=2)
    pairs = []
    for _ in range(500):
        idle.advance(STEP)
        pairs.append((idle.bob_offset("balloons") / 0.006, idle.bob_offset("cloud") / 0.004))
    assert any(abs(a - b) > 0.2 for a, b in pairs)


def test_for_manifest_takes_the_characters_and_the_bobbing_objects_of_the_scene():
    idle = IdleLife.for_manifest(MANIFEST, "blinks_bob", random.Random(1))
    for _ in range(4000):
        idle.advance(STEP)
    assert set(idle._blink) == {s.id for s in MANIFEST.characters()} and len(idle._blink) == 5
    assert idle.bobbing() == ["balloons", "cloud"]
    assert IdleLife.for_manifest(MANIFEST, "off").bobbing() == []
