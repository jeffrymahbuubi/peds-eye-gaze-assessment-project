"""SPEC-scene-cause-effect-task.md 4.6, 4.9, W4, W6, S7, acceptance A6 and the data side of A7: the
``choice`` block of ``report.json`` built from a Choice-making run folder -- who was prompted and
what was chosen, the look-back figures, the waiting-phase distribution, the Scene Map's buttons --
for a Gaze run, a Mouse run, a run without the device-rate file and a run with no gaze at all, and the
look-back columns written back into ``trials.csv``.

The run is ``tests.choice_report_fixtures.main_trials``: a scripted gaze at 100 Hz, so every figure
below is a count of samples times 10 ms (the script is in that module). Values are worked out by hand
in the comments.
"""

from __future__ import annotations

import copy
import csv
import json

import pytest

from src.data.report_cache import (
    REPORT_FILENAME,
    REPORT_VERSION,
    build_report,
    load_or_build_report,
    write_report_safely,
)
from src.data.schema import LOOKBACK_COLUMNS, TrialRecord
from tests.choice_report_fixtures import (
    Trial,
    choice_folder,
    choice_meta,
    main_trials,
    records_and_events,
)


def block(tmp_path, trials=None, **kwargs):
    return build_report(choice_folder(tmp_path, trials or main_trials(), **kwargs))["choice"]


@pytest.fixture
def choice(tmp_path):
    return block(tmp_path)


# -- the block ---------------------------------------------------------------------------------------


def test_a_choice_making_folder_has_a_choice_block(tmp_path):
    assert build_report(choice_folder(tmp_path, main_trials()))["choice"] is not None
    assert REPORT_VERSION == 5


def test_the_block_says_where_the_samples_came_from_and_what_the_run_used(choice):
    assert choice["source"] == "gaze" and choice["pointer_not_gaze"] is False
    assert choice["padded"] is True
    assert choice["params"] == {"pad_deg": 1.0, "after_ms": 500.0, "min_dwell_ms": 100.0, "max_interval_ms": 100.0}
    assert (choice["scene"], choice["language"], choice["visual_cue"]) == ("park", "en", False)
    assert (choice["timeout_ms"], choice["post_effect_ms"], choice["gap"]) == (10000.0, 1000.0, "standard")
    assert choice["idle_animation"] is None  # step 4 writes it; an older folder has none
    # A cell of the 7 x 5 board on the 527 x 296 mm canvas at 650 mm: 75.3 x 59.2 mm.
    assert choice["button_deg"] == [6.6, 5.2]


def test_the_idle_animation_is_read_from_the_metadata_when_the_canvas_step_wrote_it(tmp_path):
    meta = choice_meta(main_trials(), idle_animation="blinks_bob")
    assert block(tmp_path, meta=meta)["idle_animation"] == "blinks_bob"


def test_each_trial_carries_what_the_prompt_and_the_choice_were(choice):
    t0, t1, t2, t3, t4 = choice["trials"]
    assert [t["trial"] for t in choice["trials"]] == [1, 2, 3, 4, 5]
    assert [t["outcome"] for t in choice["trials"]] == ["hit", "hit", "timeout", "skipped", "hit"]
    assert [t["object"] for t in choice["trials"]] == ["rainbow", "bike", "balloons", "seesaw", "swing"]
    assert [t["side"] for t in choice["trials"]] == ["left", "right", "left", "left", "right"]
    assert [t["selected_object"] for t in choice["trials"]] == ["rainbow", "bike", None, None, "swing"]
    assert [t["attempts"] for t in choice["trials"]] == [1, 2, 0, 0, 1]
    assert (t1["wrong_choices"], t1["wrong_objects"]) == (1, ["apples"])
    assert [t["wrong_choices"] for t in (t0, t2, t4)] == [0, 0, 0]
    assert [t["modelled"] for t in choice["trials"]] == [False, False, True, None, False]
    assert t3["label"] == "Seesaw" and t3["wrong_choices"] is None  # a skipped trial counts none


def test_reaction_time_is_from_the_prompt_end_to_the_choice_or_the_timeout(choice):
    assert [t["reaction_time_s"] for t in choice["trials"]] == [1.0, 3.0, 10.0, None, 2.0]


# -- A6: look-back on a scripted gaze ---------------------------------------------------------------------


def test_look_back_of_a_hit_trial_matches_the_hand_computed_values(choice):
    t0 = choice["trials"][0]
    # Rainbow, effect 8.0 .. 10.0 s, W = 8.0 .. 10.5 s = 251 samples, all valid. The gaze is on the
    # button until 8.5 s, on the rainbow for 100 samples (8.5 .. 9.49 s), then the button again.
    assert t0["lookback"] is True
    assert t0["lookback_latency_ms"] == 500.0
    assert t0["lookback_dwell_ms"] == 1000.0
    assert t0["lookback_fraction"] == pytest.approx(1000.0 / 2500.0)
    assert t0["lookback_valid_fraction"] == 1.0


def test_a_hit_trial_where_the_child_never_looked_back_is_no_with_the_valid_share_beside_it(choice):
    t1 = choice["trials"][1]
    # Bike, effect 30.0 .. 34.0 s, W = 4.5 s: on the button all along.
    assert t1["lookback"] is False
    assert (t1["lookback_dwell_ms"], t1["lookback_fraction"], t1["lookback_latency_ms"]) == (0.0, 0.0, None)
    assert t1["lookback_valid_fraction"] == 1.0


def test_a_modelled_trial_is_measured_and_marked_apart(choice):
    t2 = choice["trials"][2]
    # Balloons, the effect as a model 57.0 .. 60.5 s, W = 4.0 s: 1.0 s on the button, then 150 samples
    # on the balloons.
    assert t2["modelled"] is True
    assert (t2["lookback"], t2["lookback_latency_ms"], t2["lookback_dwell_ms"]) == (True, 1000.0, 1500.0)
    assert t2["lookback_fraction"] == pytest.approx(1500.0 / 4000.0)  # 0.375


def test_a_gaze_loss_inside_the_window_is_excluded_and_shown_in_the_valid_share(choice):
    t4 = choice["trials"][4]
    # Swing, effect 89.0 .. 91.5 s, W = 3.0 s = 301 samples; 0.5 s of them (50) lost, then 1.0 s on
    # the swing from 90.0 s.
    assert t4["lookback"] is True
    assert (t4["lookback_latency_ms"], t4["lookback_dwell_ms"]) == (1000.0, 1000.0)
    assert t4["lookback_fraction"] == pytest.approx(1000.0 / 3000.0, abs=1e-4)
    assert t4["lookback_valid_fraction"] == pytest.approx(251 / 301, abs=1e-4)


def test_a_skipped_trial_has_nothing_measured(choice):
    t3 = choice["trials"][3]
    assert t3["lookback"] is None and t3["lookback_valid_fraction"] is None
    assert t3["wait_valid_fraction"] is None and t3["reaction_time_s"] is None


# -- S7: where the gaze was while the child chose ---------------------------------------------------------


def test_the_waiting_phase_is_split_over_the_scene_the_buttons_and_elsewhere(choice):
    def wait(t):
        return (t["wait_scene_ms"], t["wait_buttons_ms"], t["wait_other_ms"], t["wait_valid_fraction"])

    t0, t1, t2, _t3, t4 = choice["trials"]
    assert wait(t0) == (400.0, 600.0, 0.0, 1.0)  # 7.0 .. 8.0 s: 0.4 s scene, 0.6 s button
    assert wait(t1) == (1000.0, 2000.0, 0.0, 1.0)
    assert wait(t2) == (2000.0, 6000.0, 2000.0, 1.0)  # the timeout: 10 s from the prompt end
    assert wait(t4) == (1000.0, 1000.0, 0.0, 1.0)
    assert (t0["wait_samples"], t2["wait_samples"]) == (101, 1001)


# -- the summary ------------------------------------------------------------------------------------------


def rows(choice):
    return {r["key"]: r for r in choice["summary"]["rows"]}


def test_the_summary_rows_split_first_choices_right_choices_modelled_and_all(choice):
    first, right, modelled, everything = (rows(choice)[k] for k in ("first", "right", "modelled", "all"))
    assert [(r["n"], r["N"]) for r in (first, right, modelled, everything)] == [(2, 4), (3, 4), (1, 4), (4, 4)]
    # Reaction time (median): first choices 1.0 and 2.0; right choices 1.0, 3.0, 2.0; the timeout 10.0;
    # all four 1.0, 3.0, 10.0, 2.0 -> (2.0 + 3.0) / 2.
    assert [r["reaction_time_s"] for r in (first, right, modelled, everything)] == [1.5, 2.0, 10.0, 2.5]
    # Wrong choices (mean): the bike trial has one.
    assert [r["wrong_choices"] for r in (first, right, modelled, everything)] == [0.0, 0.33, 0.0, 0.25]
    assert [(r["lookback_yes"], r["lookback_n"]) for r in (first, right, modelled, everything)] == [
        (2, 2), (2, 3), (1, 1), (3, 4),
    ]
    # Latency (median, s): first 0.5 and 1.0; right the same (the bike has none); modelled 1.0; all
    # 0.5, 1.0, 1.0.
    assert [r["latency_s"] for r in (first, right, modelled, everything)] == [0.75, 0.75, 1.0, 1.0]


def test_the_sides_count_right_choices_per_button_side(choice):
    left, right = choice["summary"]["sides"]
    # Left: rainbow (hit) and balloons (timeout); right: bike and swing (both hit).
    assert (left["key"], left["n"], left["N"], left["reaction_time_s"]) == ("left", 1, 2, 1.0)
    assert (left["lookback_yes"], left["lookback_n"]) == (1, 1)
    assert (right["key"], right["n"], right["N"], right["reaction_time_s"]) == ("right", 2, 2, 2.5)
    assert (right["lookback_yes"], right["lookback_n"]) == (1, 2)


def test_the_waiting_shares_pool_the_time_of_the_scored_trials(choice):
    wait = choice["summary"]["wait"]
    # Scene 400 + 1000 + 2000 + 1000 = 4400, buttons 600 + 2000 + 6000 + 1000 = 9600, elsewhere 2000.
    assert wait["total_ms"] == 16000.0
    assert (wait["scene_pct"], wait["buttons_pct"], wait["other_pct"]) == (27.5, 60.0, 12.5)
    assert wait["valid_pct"] == 100.0 and wait["n"] == 4


# -- the Scene Map's buttons --------------------------------------------------------------------------------


def test_the_buttons_carry_their_rectangle_look_back_area_and_counts(choice):
    buttons = choice["buttons"]
    assert [b["object"] for b in buttons] == [
        "balloons", "rainbow", "seesaw", "apples", "cloud", "bubbles", "bike", "swing",
    ]
    assert [(b["right"], b["timeouts"]) for b in buttons] == [
        (0, 1), (1, 0), (0, 0), (0, 0), (0, 0), (0, 0), (1, 0), (1, 0),
    ]
    rainbow = buttons[1]
    assert rainbow["side"] == "left" and rainbow["rect"][0] < 1 / 7
    # The look-back area is the idle box plus 1 deg: 0.021529 across and 0.038330 down.
    x0, y0, x1, y1 = rainbow["box"]
    assert rainbow["aoi"] == pytest.approx([x0 - 0.021529, y0 - 0.038330, x1 + 0.021529, y1 + 0.038330], abs=1e-4)
    assert choice["scene_box"] == pytest.approx([1 / 7, 0.0, 6 / 7, 1.0], abs=1e-5)
    assert choice["trials"][0]["aoi"] == rainbow["aoi"]


def test_the_box_provider_is_where_the_canvas_steps_moving_boxes_are_wired_in(tmp_path, monkeypatch):
    # ``default_box_at`` is choice_scene's ``object_box_at`` on the run's manifest. A provider that puts the object's box somewhere else (here the
    # bottom left corner, where the child never looked) changes the figures and the map's areas.
    from src.data import report_choice

    monkeypatch.setattr(report_choice, "default_box_at", lambda scene="park": (lambda object_id, elapsed_ms: (0.0, 0.9, 0.05, 0.99)))
    moved = block(tmp_path)
    assert moved["trials"][0]["lookback"] is False and moved["trials"][0]["lookback_dwell_ms"] == 0.0
    assert moved["buttons"][1]["box"][1] == pytest.approx(0.9)
    # Called with the object and the time since the effect started, in scene fractions.
    seen = []
    monkeypatch.setattr(report_choice, "default_box_at", lambda scene="park": (lambda o, ms: seen.append((o, ms)) or (0.4, 0.2, 0.6, 0.3)))
    block(tmp_path / "again")
    assert ("rainbow", 0.0) in seen and any(ms == 2000.0 and o == "rainbow" for o, ms in seen)  # clamped to its length
    assert max(ms for o, ms in seen if o == "rainbow") == 2000.0


def test_each_trial_carries_its_gaze_path_during_the_window(choice):
    path = choice["trials"][0]["lookback_path"]
    assert path and all(len(point) == 2 for segment in path for point in segment)
    assert choice["trials"][3]["lookback_path"] == []


# -- the other sources ----------------------------------------------------------------------------------------


def test_a_mouse_run_is_measured_on_the_pointer_and_marked_not_gaze(tmp_path):
    mouse = block(tmp_path, pointer=True)
    assert (mouse["source"], mouse["pointer_not_gaze"]) == ("pointer", True)
    t0 = mouse["trials"][0]
    assert (t0["lookback"], t0["lookback_latency_ms"], t0["lookback_dwell_ms"]) == (True, 500.0, 1000.0)
    assert (t0["wait_scene_ms"], t0["wait_buttons_ms"]) == (400.0, 600.0)


def test_without_the_device_rate_file_the_gaze_stream_is_used(tmp_path):
    stream = block(tmp_path, with_raw=False)
    assert stream["source"] == "gaze"
    t0, _t1, t2, _t3, t4 = stream["trials"]
    assert (t0["lookback_latency_ms"], t0["lookback_dwell_ms"]) == (500.0, 1000.0)
    assert (t2["lookback_latency_ms"], t2["lookback_dwell_ms"]) == (1000.0, 1500.0)
    assert (t4["lookback_latency_ms"], t4["lookback_dwell_ms"]) == (1000.0, 1000.0)
    assert t4["lookback_valid_fraction"] == pytest.approx(126 / 151, abs=1e-4)  # 3.0 s at 50 Hz; 25 lost


def test_a_run_with_no_gaze_at_all_has_no_look_back_but_keeps_the_rest(tmp_path):
    none = block(tmp_path, with_raw=False, with_frames=False)
    assert none["source"] is None
    assert all(t["lookback"] is None and t["wait_scene_ms"] is None for t in none["trials"])
    assert [t["reaction_time_s"] for t in none["trials"]] == [1.0, 3.0, 10.0, None, 2.0]
    assert none["buttons"][1]["aoi"] is not None  # the areas are known without any gaze
    assert none["summary"]["wait"]["scene_pct"] is None
    assert rows(none)["all"]["lookback_n"] == 0


def test_a_degree_is_never_guessed_so_without_the_screen_size_there_is_no_look_back(tmp_path):
    meta = choice_meta(main_trials())
    for key in ("screen_physical_width_mm", "screen_physical_height_mm", "viewing_distance_mm"):
        meta.pop(key)
    short = block(tmp_path, meta=meta)
    assert short["padded"] is False and short["button_deg"] is None
    assert all(t["lookback"] is None and t["aoi"] is None for t in short["trials"])
    assert short["trials"][0]["wait_scene_ms"] == 400.0  # where the gaze was needs no angle


def test_the_pauses_of_the_run_are_not_part_of_a_window(tmp_path):
    # Paused from 8.5 to 9.0 s, half of the first trial's look at the rainbow (8.5 .. 9.5 s): the
    # 50 samples inside the pause are out of the window (201 of 251 left), the look is 9.0 .. 9.5 s
    # = 500 ms and starts 500 ms into the effect on its own clock, out of 2000 ms of active window.
    t0 = block(tmp_path, pauses=[(8.5, 9.0)])["trials"][0]
    assert (t0["lookback_latency_ms"], t0["lookback_dwell_ms"]) == (500.0, 500.0)
    assert t0["lookback_fraction"] == pytest.approx(0.25)


# -- events that are not the trial's ------------------------------------------------------------------------------


def test_the_attempt_a_pause_interrupted_is_not_the_trial(tmp_path):
    # Trial 2 (the bike) was first presented at 14.0 s and interrupted; its row is the re-presentation
    # at 25.0 s. The earlier PROMPT_START (a different object) and a stray MISS_CLICK must not count.
    trials = main_trials()
    folder = choice_folder(tmp_path, trials)
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    events += [
        {"t_ns": events[0]["t_ns"] + 9 * 10**9, "kind": "PROMPT_START", "trial": 1, "object": "swing", "slot": 7},
        {"t_ns": events[0]["t_ns"] + 9_500_000_000, "kind": "MISS_CLICK", "selected_slot": 5, "selected_object": "bubbles"},
        {"t_ns": events[0]["t_ns"] + 10 * 10**9, "kind": "TRIAL_INTERRUPTED", "trial": 1},
    ]
    (folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in sorted(events, key=lambda e: e["t_ns"])), encoding="utf-8")
    again = build_report(folder)["choice"]
    reference = block(tmp_path / "other")
    assert again["trials"] == reference["trials"]


def test_a_switch_press_off_every_button_is_an_attempt_not_a_wrong_choice(tmp_path):
    folder = choice_folder(tmp_path, main_trials())
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    stray = dict(next(e for e in events if e["kind"] == "MISS_CLICK"), selected_slot=-1, selected_object=None)
    stray["t_ns"] += 50_000_000
    (folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in [*events, stray]), encoding="utf-8")
    assert build_report(folder)["choice"]["trials"][1]["wrong_choices"] == 1


# -- the cache and trials.csv -------------------------------------------------------------------------------------


def test_the_block_is_deterministic_and_survives_the_cache(tmp_path):
    folder = choice_folder(tmp_path, main_trials())
    first, second = build_report(folder), build_report(folder)
    assert first == second and json.loads(json.dumps(first)) == first
    assert load_or_build_report(folder)["choice"] == first["choice"]
    assert (folder / REPORT_FILENAME).exists()


def read_rows(folder):
    with (folder / "trials.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_the_look_back_columns_are_written_into_trials_csv_when_the_report_is_written(tmp_path):
    folder = choice_folder(tmp_path, main_trials())
    assert all(row[c] == "" for row in read_rows(folder) for c in LOOKBACK_COLUMNS)  # blank until then
    assert write_report_safely(folder) == folder / REPORT_FILENAME
    t0, t1, _t2, t3, t4 = (read_rows(folder)[i] for i in (0, 1, 2, 3, 4))
    assert [t0[c] for c in LOOKBACK_COLUMNS] == [
        "1", "500.0", "1000.0", "0.4", "1.0", "400.0", "600.0", "0.0", "1.0",
    ]
    assert [t1[c] for c in LOOKBACK_COLUMNS[:5]] == ["0", "", "0.0", "0.0", "1.0"]
    assert all(t3[c] == "" for c in LOOKBACK_COLUMNS)  # the skipped trial
    assert t4["lookback"] == "1" and t4["lookback_fraction"] == "0.3333"
    # The report does not depend on those columns: rebuilding from the filled file is the same report.
    assert build_report(folder)["choice"] == json.loads((folder / REPORT_FILENAME).read_text(encoding="utf-8"))["choice"]
    assert list(read_rows(folder)[0])[-len(LOOKBACK_COLUMNS):] == list(LOOKBACK_COLUMNS)


def test_an_older_trials_csv_without_the_columns_gets_them_appended(tmp_path):
    folder = choice_folder(tmp_path, main_trials())
    rows_before = read_rows(folder)
    keep = [c for c in rows_before[0] if c not in LOOKBACK_COLUMNS]
    with (folder / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keep)
        writer.writeheader()
        writer.writerows([{k: r[k] for k in keep} for r in rows_before])
    write_report_safely(folder)
    filled = read_rows(folder)
    assert list(filled[0])[-len(LOOKBACK_COLUMNS):] == list(LOOKBACK_COLUMNS)
    assert filled[0]["lookback_latency_ms"] == "500.0"


def test_another_task_is_left_alone_and_the_columns_are_blank(tmp_path):
    record = TrialRecord(0, "click_grid", 0.5, 0.5, 90.0, 0).as_row()
    assert all(record[c] == "" for c in LOOKBACK_COLUMNS)
    assert copy.deepcopy(LOOKBACK_COLUMNS) == (
        "lookback", "lookback_latency_ms", "lookback_dwell_ms", "lookback_fraction",
        "lookback_valid_fraction", "wait_scene_ms", "wait_buttons_ms", "wait_other_ms",
        "wait_valid_fraction",
    )


def test_a_trial_object_unknown_to_the_scene_is_left_unmeasured(tmp_path):
    rows_, events = records_and_events([Trial("rainbow")])
    assert rows_[0].prompt_object == "rainbow" and events[0]["kind"] == "PROMPT_START"
    folder = choice_folder(tmp_path, [Trial("rainbow")])
    with (folder / "trials.csv").open(encoding="utf-8", newline="") as fh:
        content = fh.read().replace("rainbow", "unicorn")
    (folder / "trials.csv").write_text(content, encoding="utf-8")
    events_text = (folder / "events.jsonl").read_text(encoding="utf-8").replace("rainbow", "unicorn")
    (folder / "events.jsonl").write_text(events_text, encoding="utf-8")
    item = build_report(folder)["choice"]["trials"][0]
    assert item["object"] == "unicorn" and item["lookback"] is None and item["label"] is None


def test_the_default_box_provider_moves_bike_and_cloud_and_keeps_the_others(monkeypatch):
    # N2: the report's boxes come from choice_scene.object_box_at on the run's manifest.
    from src.data import report_choice
    from src.data.lookback import IDLE_BOXES

    box_at = report_choice.default_box_at("park")
    for object_id, idle in IDLE_BOXES.items():
        assert box_at(object_id, 0.0) == pytest.approx(idle)
    for object_id in ("bike", "cloud"):
        assert box_at(object_id, 1000.0) != pytest.approx(IDLE_BOXES[object_id])
    for object_id in ("balloons", "rainbow", "seesaw", "apples", "bubbles", "swing"):
        assert box_at(object_id, 1000.0) == pytest.approx(IDLE_BOXES[object_id])
