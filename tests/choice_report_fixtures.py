"""Synthetic Choice-making run folders for the look-back and report tests
(SPEC-scene-cause-effect-task.md 4.6, 4.9, A6, A7): a scripted gaze (where the child looked, second
by second), the trial rows and events the task writes, and the folder on disk. Not a test module.

Everything is on the reference rig with the canvas filling the screen (canvas-normalized and
monitor-normalized coordinates are one thing) and the device sampling at 100 Hz, so every time of
the script is a sample instant and a hand-computed dwell is a count of samples times 10 ms.
"""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.data.lookback import IDLE_BOXES, scene_box_to_canvas
from src.data.recorder import POINTER_STREAM_COLUMNS, POINTER_STREAM_FILENAME
from src.data.report_eye import GazeFrame, RawSample
from src.data.schema import TrialRecord
from src.tasks.choice_layout import OBJECT_BY_ID, button_centre_norm, side_of
from tests.follow_fixtures import FULL_CANVAS_META
from tests.report_fixtures import OFFSET_NS, SEC, write_session

RATE_HZ = 100.0
TIMEOUT_S = 10.0
FIRST_ONSET_S = 5.0
PERIOD_S = 20.0

SCENE_SPOT = (0.5, 0.5)  # on the scene, on none of the objects
CORNER = (0.5 / 7, 0.1)  # the empty cell (0, 0)


def object_spot(object_id: str) -> tuple[float, float]:
    """The middle of the object's idle box on the canvas."""
    x0, y0, x1, y1 = scene_box_to_canvas(IDLE_BOXES[object_id])
    return (x0 + x1) / 2, (y0 + y1) / 2


@dataclass
class Trial:
    """One scripted trial. ``waiting`` and ``after`` are lists of ``(seconds, where)``: the gaze from
    the prompt's end on, and from the effect's start on (what is left of either is on the target's
    own button). ``where`` is ``scene``, ``button`` (the prompted object's), ``corner``, ``object``
    (the middle of the prompted object), ``lost`` (invalid) or an ``(x, y)``."""

    object: str
    outcome: str = "hit"  # hit | timeout | skipped
    wait_s: float = 1.0  # prompt end to the choice (a hit) or the skip
    wrong: tuple[str, ...] = ()  # objects of the wrong buttons chosen first (their time is inside wait_s)
    prompt_s: float = 2.0
    waiting: list[tuple[float, Any]] = field(default_factory=list)
    after: list[tuple[float, Any]] = field(default_factory=list)


def where_xy(trial: Trial, where: Any) -> tuple[float, float, bool]:
    if isinstance(where, tuple):
        return where[0], where[1], True
    if where == "scene":
        return (*SCENE_SPOT, True)
    if where == "button":
        return (*button_centre_norm(OBJECT_BY_ID[trial.object].slot), True)
    if where == "corner":
        return (*CORNER, True)
    if where == "object":
        return (*object_spot(trial.object), True)
    if where == "lost":
        return (*CORNER, False)
    raise ValueError(where)


def timeline(trials: list[Trial]) -> list[dict[str, Any]]:
    """The seconds (from the first sample) of every trial: onset, prompt end, choice, effect."""
    out = []
    for k, trial in enumerate(trials):
        onset = FIRST_ONSET_S + k * PERIOD_S
        ready = onset + trial.prompt_s
        choice = ready + (TIMEOUT_S if trial.outcome == "timeout" else trial.wait_s)
        effect_s = OBJECT_BY_ID[trial.object].effect_ms / 1000.0
        out.append(
            {"onset": onset, "ready": ready, "choice": choice, "effect_s": effect_s,
             "effect_end": choice + effect_s}
        )
    return out


def gaze_script(trials: list[Trial]) -> list[tuple[float, float, tuple[float, float], bool]]:
    """``(from_s, to_s, (x, y), valid)`` over the whole run, later entries winning; the gaze is in the
    corner where the script says nothing."""
    spans = []
    for trial, times in zip(trials, timeline(trials), strict=True):
        for start, parts, rest_until in (
            (times["ready"], trial.waiting, times["choice"]),
            (times["choice"], trial.after, times["effect_end"] + 0.5),
        ):
            cursor = start
            for seconds, where in parts:
                x, y, valid = where_xy(trial, where)
                spans.append((cursor, cursor + seconds, (x, y), valid))
                cursor += seconds
            if cursor < rest_until:
                x, y, valid = where_xy(trial, "button")
                spans.append((cursor, rest_until, (x, y), valid))
    return spans


def position_at(spans, t_s: float) -> tuple[float, float, bool]:
    found = (*CORNER, True)
    for lo, hi, xy, valid in spans:
        if lo - 1e-9 <= t_s < hi - 1e-9:
            found = (xy[0], xy[1], valid)
    return found


def raw_stream(trials: list[Trial], seconds: float) -> list[RawSample]:
    spans = gaze_script(trials)
    out = []
    for i in range(round(seconds * RATE_HZ)):
        t = i / RATE_HZ
        x, y, valid = position_at(spans, t)
        out.append(RawSample(t, x, y, valid, 3.5, valid, 3.5, valid))
    return out


def frames(trials: list[Trial], seconds: float, rate_hz: float = 50.0) -> list[GazeFrame]:
    spans = gaze_script(trials)
    out = []
    for i in range(round(seconds * rate_hz)):
        t = i / rate_hz
        x, y, valid = position_at(spans, t)
        fid = int(t / 0.4) + 1
        out.append(GazeFrame(OFFSET_NS + round(t * SEC), x, y, valid, fid, t % 0.4))
    return out


def at(seconds: float) -> int:
    return OFFSET_NS + round(seconds * SEC)


def records_and_events(trials: list[Trial], pauses=()) -> tuple[list[TrialRecord], list[dict[str, Any]]]:
    """The ``trials.csv`` rows and ``events.jsonl`` events the task writes for ``trials``."""
    rows: list[TrialRecord] = []
    events: list[dict[str, Any]] = []
    for k, (trial, times) in enumerate(zip(trials, timeline(trials), strict=True)):
        obj = OBJECT_BY_ID[trial.object]
        x, y = button_centre_norm(obj.slot)
        hit, timeout, skipped = (trial.outcome == c for c in ("hit", "timeout", "skipped"))
        end = times["choice"] if not skipped else times["ready"] + trial.wait_s
        record = TrialRecord(
            trial_id=k, task_id="choice_making", target_x=x, target_y=y, target_radius_px=80.0,
            t_target_shown_ns=at(times["onset"]),
            t_first_gaze_on_target_ns=at(times["ready"] + 0.4),
            t_click_ns=at(end) if hit else None,
            t_end_ns=at(end),
            is_hit=hit, is_timeout=timeout, is_skipped=skipped,
            attempts=len(trial.wrong) + (1 if hit else 0),
            t_selectable_start_ns=at(times["ready"]),
            entries=1, end_x=x, end_y=y, slot_index=obj.slot,
            prompt_object=obj.id, button_side=side_of(obj.slot),
            selected_object=obj.id if hit else "",
            rt_ms=round(trial.wait_s * 1000.0, 2) if hit else None,
        )
        rows.append(record)
        events.append({"t_ns": at(times["onset"]), "kind": "PROMPT_START", "trial": k, "object": obj.id,
                       "slot": obj.slot, "side": side_of(obj.slot), "duration_ms": trial.prompt_s * 1000.0,
                       "duration_source": "default"})
        events.append({"t_ns": at(times["ready"]), "kind": "PROMPT_END", "trial": k, "object": obj.id})
        for j, wrong in enumerate(trial.wrong):
            events.append({"t_ns": at(times["ready"] + 0.2 * (j + 1)), "kind": "MISS_CLICK",
                           "x": 0.1, "y": 0.2, "selectable": True,
                           "selected_slot": OBJECT_BY_ID[wrong].slot, "selected_object": wrong})
        if not skipped:
            events.append({"t_ns": at(times["choice"]), "kind": "HIT" if hit else "TIMEOUT", "trial": k})
            events.append({"t_ns": at(times["choice"]), "kind": "EFFECT_START", "trial": k, "object": obj.id,
                           "modelled": timeout, "duration_ms": times["effect_s"] * 1000.0})
            events.append({"t_ns": at(times["effect_end"]), "kind": "EFFECT_END", "trial": k, "object": obj.id,
                           "modelled": timeout})
    for start_s, end_s in pauses:
        events.append({"t_ns": at(start_s), "kind": "PAUSED", "trial": None, "interrupted": False})
        events.append({"t_ns": at(end_s), "kind": "RESUMED"})
    events.sort(key=lambda e: e["t_ns"])
    return rows, events


def choice_meta(trials: list[Trial], **extra: Any) -> dict[str, Any]:
    meta = copy.deepcopy(FULL_CANVAS_META)
    meta.update(
        session_id="2026-10-11_P001_choice_making_run1", tasks=["choice_making"],
        planned_trials=len(trials), completed_trials=len(trials), outcome="completed",
        raw_clock_offset_ns=OFFSET_NS, test_name="Choice-making 1",
        grid_gap={"preset": "standard", "gap_deg": None, "gap_px": None},
        layout_slots=[list(button_centre_norm(s)) for s in range(8)],
    )
    meta.pop("target_size", None)
    meta["settings"]["live"].update({"task.timeout_ms": 10000, "task.post_effect_ms": 1000})
    meta["settings"]["live"].pop("motion.speed_frac_per_s", None)
    meta["settings"]["structural"] = {
        "trials": len(trials), "scene": "park", "language": "en", "visual_cue": False,
        "grid": {"gap": "standard"}, "theme": "forest",
        "feedback": {"hit_sound": False, "miss_sound": True, "target_glow": True},
    }
    meta.update(extra)
    return meta


def choice_folder(
    tmp_path: Path,
    trials: list[Trial],
    *,
    name: str = "run",
    meta: dict[str, Any] | None = None,
    with_raw: bool = True,
    with_frames: bool = True,
    pointer: bool = False,
    pauses=(),
) -> Path:
    """A Choice-making run folder. ``pointer``: a Mouse run (the script is the mouse's, written to
    ``pointer_stream.csv``, and no gaze files)."""
    seconds = timeline(trials)[-1]["effect_end"] + 5.0
    rows, events = records_and_events(trials, pauses)
    meta = choice_meta(trials) if meta is None else meta
    if pointer:
        meta.update(input_mode="mouse_dwell", input_pointer="mouse", input_selection="dwell", gaze_recorded=False)
        meta.pop("raw_clock_offset_ns", None)
    out = write_session(
        tmp_path / name, rows, meta=meta,
        frames=frames(trials, seconds) if with_frames and not pointer else None,
        samples=raw_stream(trials, seconds) if with_raw and not pointer else None,
        events=events,
    )
    if pointer:
        with (out / POINTER_STREAM_FILENAME).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(POINTER_STREAM_COLUMNS)
            for f in frames(trials, seconds):
                writer.writerow([f.t_ns, round(f.x, 5), round(f.y, 5), int(f.valid)])
    return out


# The script of the run most tests read (times are seconds from the prompt end / the effect start):
#   0 rainbow, hit after 1.0 s: 0.4 s on the scene then on its button; the effect (2.0 s): 0.5 s on the
#     button, 1.0 s on the rainbow, then on the button.
#   1 bike, hit after 3.0 s with one wrong choice (apples): 1.0 s on the scene, then on the buttons;
#     the effect (4.0 s): on the button throughout.
#   2 balloons, timeout (10 s): 2.0 s on the scene, 6.0 on the button, 2.0 in the corner; the modelled
#     effect (3.5 s): 1.0 s on the button, 1.5 s on the balloons.
#   3 seesaw, skipped.
#   4 swing, hit after 2.0 s: 1.0 s on the scene; the effect (2.5 s): 0.5 s on the button, 0.5 s lost,
#     1.0 s on the swing, then the button.
def main_trials() -> list[Trial]:
    return [
        Trial("rainbow", wait_s=1.0, waiting=[(0.4, "scene")], after=[(0.5, "button"), (1.0, "object")]),
        Trial("bike", wait_s=3.0, wrong=("apples",), waiting=[(1.0, "scene")]),
        Trial("balloons", "timeout", waiting=[(2.0, "scene"), (6.0, "button"), (2.0, "corner")],
              after=[(1.0, "button"), (1.5, "object")]),
        Trial("seesaw", "skipped", wait_s=0.5),
        Trial("swing", wait_s=2.0, waiting=[(1.0, "scene")],
              after=[(0.5, "button"), (0.5, "lost"), (1.0, "object")]),
    ]
