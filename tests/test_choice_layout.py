"""SPEC-scene-cause-effect-task.md 4.2 / 4.4 / W5 (acceptance A2): the Choice-making board, its
eight objects and the trial order. Pure logic, no Qt, no task."""

from __future__ import annotations

import random
import wave
from collections import Counter
from pathlib import Path

import pytest

from src.engine.config import CONFIG_ROOT
from src.tasks.choice_layout import (
    ASSETS_ROOT,
    BUTTON_CELLS,
    DEFAULT_PROMPT_MS,
    GRID_COLS,
    GRID_ROWS,
    N_BUTTONS,
    OBJECT_BY_ID,
    OBJECTS,
    SIDE_LEFT,
    SIDE_RIGHT,
    board_geometry,
    button_at,
    button_centre_norm,
    button_rect,
    effect_wav_path,
    prompt_wav_path,
    scene_audio_dir,
    scene_rect,
    side_of,
    trial_order,
    wav_duration_ms,
)

W, H = 1920, 1080


def write_wav(path: Path, ms: float, rate: int = 8000) -> Path:
    """A tiny silent 16-bit mono PCM WAV of ``ms`` milliseconds (parents created)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * round(rate * ms / 1000.0))
    return path


# -- 4.2: the objects and where their buttons are --------------------------------------------


def test_the_eight_objects_sit_on_the_buttons_of_the_4_2_table():
    assert [o.id for o in OBJECTS] == [
        "balloons", "rainbow", "seesaw", "apples",  # L1-L4
        "cloud", "bubbles", "bike", "swing",  # R1-R4
    ]
    assert [o.slot for o in OBJECTS] == list(range(N_BUTTONS))
    assert {o.id: o for o in OBJECTS} == OBJECT_BY_ID
    assert [o.label for o in OBJECTS][0] == "Balloons"


def test_buttons_are_columns_0_and_6_rows_1_to_4_and_the_corners_stay_empty():
    assert BUTTON_CELLS[:4] == ((0, 1), (0, 2), (0, 3), (0, 4))
    assert BUTTON_CELLS[4:] == ((6, 1), (6, 2), (6, 3), (6, 4))
    assert (GRID_COLS, GRID_ROWS) == (7, 5)
    assert (0, 0) not in BUTTON_CELLS and (6, 0) not in BUTTON_CELLS


def test_the_first_four_buttons_are_on_the_left_and_the_rest_on_the_right():
    assert [side_of(s) for s in range(8)] == [SIDE_LEFT] * 4 + [SIDE_RIGHT] * 4


def test_the_button_centres_are_the_cell_centres_whatever_the_canvas_size():
    assert button_centre_norm(0) == pytest.approx((0.5 / 7, 1.5 / 5))
    assert button_centre_norm(7) == pytest.approx((6.5 / 7, 4.5 / 5))


def test_the_effect_durations_are_the_4_4_defaults():
    assert {o.id: o.effect_ms for o in OBJECTS} == {
        "bike": 4000, "seesaw": 2000, "bubbles": 4000, "swing": 2500,
        "rainbow": 2000, "cloud": 3500, "balloons": 3500, "apples": 4500,
    }
    assert DEFAULT_PROMPT_MS > 0


# -- the board on a canvas ----------------------------------------------------------------------


def test_the_scene_is_columns_1_to_5_at_full_height_about_4_to_3():
    x, y, w, h = scene_rect(1920, 1032)  # W1: about 1371 x 1032 at 1920 x 1080 less the run bar
    assert (x, y) == pytest.approx((1920 / 7, 0.0))
    assert (w, h) == pytest.approx((1371.43, 1032), abs=0.01)
    assert w / h == pytest.approx(4 / 3, rel=0.01)


def test_a_standard_button_is_its_cell_inset_like_a_grid_click_cell():
    geometry = board_geometry(W, H, None)
    x, y, w, h = button_rect(0, W, H, geometry)
    pitch_w, pitch_h = W / 7, H / 5
    inset = 0.06 * min(pitch_w, pitch_h)
    assert (x, y) == pytest.approx((inset, pitch_h + inset))
    assert (w, h) == pytest.approx((pitch_w - 2 * inset, pitch_h - 2 * inset))


def test_a_point_in_a_button_selects_it_and_the_centre_of_every_button_is_its_own():
    geometry = board_geometry(W, H, None)
    for slot in range(N_BUTTONS):
        cx, cy = button_centre_norm(slot)
        assert button_at(cx * W, cy * H, W, H, geometry) == slot


def test_the_scene_and_the_empty_corner_cells_select_nothing():
    geometry = board_geometry(W, H, None)
    assert button_at(0.5 * W, 0.5 * H, W, H, geometry) == -1  # the middle of the scene
    assert button_at(0.5 / 7 * W, 0.5 / 5 * H, W, H, geometry) == -1  # cell (0, 0)
    assert button_at(6.5 / 7 * W, 0.5 / 5 * H, W, H, geometry) == -1  # cell (6, 0)
    assert button_at(-5.0, -5.0, W, H, geometry) == -1  # off the canvas


def test_the_standard_gap_leaves_no_dead_zone_but_a_wide_gap_does():
    # Between slot 0 (row 1) and slot 1 (row 2) the cells meet at y = 2 * pitch_h.
    edge_y = 2 * H / 5
    x = 0.5 / 7 * W
    standard = board_geometry(W, H, None)
    assert button_at(x, edge_y - 1, W, H, standard) == 0
    assert button_at(x, edge_y + 1, W, H, standard) == 1
    wide = board_geometry(W, H, 82.0)  # 2 deg on the lab monitor
    assert wide.gap_px == pytest.approx(82.0)
    assert button_at(x, edge_y, W, H, wide) == -1  # the gap belongs to neither button
    assert button_at(x, edge_y - 41 - 1, W, H, wide) == 0  # just inside the drawn button
    assert button_at(x, edge_y + 41 + 1, W, H, wide) == 1


def test_a_wide_gap_is_capped_at_half_the_pitch():
    geometry = board_geometry(W, H, 500.0)
    assert geometry.capped and geometry.gap_px == pytest.approx(0.5 * min(W / 7, H / 5))


# -- W5 / A2: the trial order -----------------------------------------------------------------------


def _balanced(order: list[int], n: int) -> None:
    assert len(order) == n
    assert all(0 <= s < N_BUTTONS for s in order)
    counts = Counter(order)
    per_object = [counts.get(s, 0) for s in range(N_BUTTONS)]
    assert max(per_object) - min(per_object) <= 1, per_object
    left = sum(per_object[:4])
    right = sum(per_object[4:])
    assert abs(left - right) <= 1, (left, right)
    assert all(a != b for a, b in zip(order, order[1:], strict=False)), order  # never twice in a row


@pytest.mark.parametrize("seed", range(40))
def test_16_trials_prompt_each_object_twice_8_left_8_right_never_twice_in_a_row(seed):
    order = trial_order(16, random.Random(seed))
    assert Counter(order) == {s: 2 for s in range(N_BUTTONS)}
    assert sum(1 for s in order if side_of(s) == SIDE_LEFT) == 8
    _balanced(order, 16)


@pytest.mark.parametrize("n", range(1, 71))
def test_any_trial_count_is_balanced_as_far_as_the_count_allows(n):
    for seed in range(12):
        _balanced(trial_order(n, random.Random(seed)), n)


def test_the_order_is_deterministic_for_a_seed_and_varies_between_seeds():
    assert trial_order(16, random.Random(5)) == trial_order(16, random.Random(5))
    assert len({tuple(trial_order(16, random.Random(s))) for s in range(10)}) > 1


def test_no_trials_is_an_empty_order():
    assert trial_order(0, random.Random(0)) == [] and trial_order(-3, random.Random(0)) == []


# -- section 9 Q1 = B: the prompt WAVs, measured read only ----------------------------------------


def test_the_audio_paths_come_from_the_scene_and_the_language():
    root = Path("assets")
    assert scene_audio_dir("park", root) == root / "scenes" / "park" / "audio"
    assert prompt_wav_path("park", "en", "balloons", root) == (
        root / "scenes" / "park" / "audio" / "en" / "prompt_balloons.wav"
    )
    assert prompt_wav_path("zoo", "zh-TW", "bike", root) == (
        root / "scenes" / "zoo" / "audio" / "zh-TW" / "prompt_bike.wav"
    )
    assert effect_wav_path("park", "bike", root) == (
        root / "scenes" / "park" / "audio" / "sfx" / "bike.wav"
    )


def test_the_default_audio_root_is_the_configs_assets_folder():
    assert ASSETS_ROOT == CONFIG_ROOT / "assets"
    assert prompt_wav_path("park", "en", "swing") == (
        CONFIG_ROOT / "assets" / "scenes" / "park" / "audio" / "en" / "prompt_swing.wav"
    )


@pytest.mark.parametrize("ms", [250, 500, 1500, 2345])
def test_a_wav_is_measured_from_its_header(tmp_path, ms):
    path = write_wav(tmp_path / "a.wav", ms, rate=16000)
    assert wav_duration_ms(path) == pytest.approx(ms, abs=0.1)


def test_a_missing_empty_or_unreadable_wav_has_no_length(tmp_path):
    assert wav_duration_ms(tmp_path / "nowhere" / "x.wav") is None
    assert not (tmp_path / "nowhere").exists()  # measuring never creates anything
    assert wav_duration_ms(write_wav(tmp_path / "empty.wav", 0)) is None
    garbage = tmp_path / "garbage.wav"
    garbage.write_bytes(b"this is not a wav file at all")
    assert wav_duration_ms(garbage) is None
    assert wav_duration_ms(tmp_path) is None  # a folder
    truncated = tmp_path / "truncated.wav"
    truncated.write_bytes(write_wav(tmp_path / "t.wav", 100).read_bytes()[:20])
    assert wav_duration_ms(truncated) is None
