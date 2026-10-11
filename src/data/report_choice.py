"""The ``choice`` block of ``report.json``: Choice-making's figures for the per-test report
(SPEC-scene-cause-effect-task.md 4.6, 4.9, W4, W6, S7, N2). Pure and Qt-free, like the rest of
``src/data``; the maths is in :mod:`lookback`.

What comes from where:

* **Who was prompted, what was chosen, the reaction time** are columns of ``trials.csv`` written by
  the task (``prompt_object``, ``button_side``, ``selected_object``, ``rt_ms``; step 3). The
  windows of the prompt and of the effect are the ``PROMPT_START`` / ``PROMPT_END`` /
  ``EFFECT_START`` / ``EFFECT_END`` events of ``events.jsonl`` (a trial re-presented after a pause
  repeats its id, so an event belongs to a trial by its time and its id), the wrong buttons its
  ``MISS_CLICK`` events, and the pauses its ``PAUSED`` / ``RESUMED`` events.
* **Look-back and the waiting-phase distribution** are worked out here from the device-rate gaze
  (``all_gaze.csv``; ``gaze_stream.csv`` without it) or, for a Mouse run, the pointer
  (``pointer_stream.csv``, marked "pointer, not gaze"). A trial that timed out and got the effect as
  a model is kept apart from the hit trials in the figures (H7).

A figure the folder cannot give is ``None``, never 0 (4D.9): no stream, no canvas or physical size
(the 1 deg padding is a degree, never guessed), no effect events.
"""

from __future__ import annotations

import csv
import os
import statistics
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..tasks.choice_layout import GRID_COLS, GRID_ROWS, OBJECT_BY_ID, OBJECTS, side_of
from ..tasks.choice_scene import load_manifest, object_box_at
from .lookback import (
    DEFAULT_LOOKBACK,
    NO_PAUSES,
    Box,
    BoxAt,
    EffectWindow,
    LookbackParams,
    Pauses,
    Regions,
    SampleSeries,
    aoi_at,
    board_regions,
    measure_lookback,
    measure_wait,
    pad_norm,
    samples_from_frames,
    samples_from_raw,
    scene_box_to_canvas,
)
from .report_config import setting
from .report_eye import FrameIndex, GazeFrame, RawSample
from .report_geometry import Geometry
from .report_util import round_or_none, to_float, to_int
from .report_visual import DEFAULT_PATH, gaze_path
from .schema import LOOKBACK_COLUMNS

SOURCE_GAZE, SOURCE_POINTER = "gaze", "pointer"
SIDES = ("left", "right")
NOMINAL_CANVAS = Geometry(canvas_w_px=1920, canvas_h_px=1080)  # the board's shape when a folder lacks one


def default_box_at(scene: str = "park") -> BoxAt:
    """The AOI box provider the report uses, ``(object_id, elapsed_ms) -> (x0, y0, x1, y1)`` in
    scene fractions: the canvas step's ``object_box_at`` on the run's scene manifest (N2), so the AOI
    of Bike and Cloud moves with the object and the others stay at their idle box. The manifest is
    read now, so a report rebuilt after the art changed uses the new boxes."""
    manifest = load_manifest(scene or "park")

    def box_at(object_id: str, elapsed_ms: float) -> Box:
        return object_box_at(manifest, object_id, elapsed_ms)

    return box_at


def run_extras(meta: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """The run's own settings the page and the PDF name, read as the run recorded them: the scene
    and prompt language, whether the visual cue was on (S3), the idle animation (N3: ``None`` until
    the canvas step writes it to ``metadata.json``), the time to choose, the pause after the
    animation and the cell gap."""
    cue = setting(settings, None, "visual_cue")
    idle = meta.get("idle_animation") or setting(settings, None, "idle_animation")
    cell_gap = meta.get("grid_gap")
    return {
        "scene": setting(settings, None, "scene"),
        "language": setting(settings, None, "language"),
        "visual_cue": cue if isinstance(cue, bool) else None,
        "idle_animation": str(idle) if idle else None,
        "timeout_ms": to_float(setting(settings, "task.timeout_ms", "timeout_ms")),
        "post_effect_ms": to_float(setting(settings, "task.post_effect_ms", "post_effect_ms")),
        "gap": cell_gap.get("preset") if isinstance(cell_gap, dict) else setting(settings, None, "grid", "gap"),
    }


def choose_series(
    *,
    mouse: bool,
    geometry: Geometry,
    pointer_frames: Sequence[GazeFrame] = (),
    raw_samples: Sequence[RawSample] | None = None,
    raw_offset_ns: int | None = None,
    gaze_frames: Sequence[GazeFrame] = (),
) -> tuple[SampleSeries | None, str | None]:
    """The samples look-back is measured on, and which kind they are: the pointer of a Mouse run,
    else the device-rate gaze when it can be put on the host clock, else the gaze stream; ``None``
    when the folder has none of them."""
    if mouse:
        if pointer_frames:
            return SampleSeries(samples_from_frames(pointer_frames, geometry)), SOURCE_POINTER
        return None, None
    if raw_samples and raw_offset_ns is not None:
        return SampleSeries(samples_from_raw(raw_samples, raw_offset_ns, geometry)), SOURCE_GAZE
    if gaze_frames:
        return SampleSeries(samples_from_frames(gaze_frames, geometry)), SOURCE_GAZE
    return None, None


# -- the events ----------------------------------------------------------------------------------


def pause_spans(events: Sequence[dict[str, Any]]) -> Pauses:
    """The paused spans: each ``PAUSED`` to the next ``RESUMED`` (a run that ended paused stays
    paused to the end)."""
    spans: list[tuple[int, int]] = []
    since: int | None = None
    for event in events:
        t_ns = to_int(event.get("t_ns"))
        if t_ns is None:
            continue
        if event.get("kind") == "PAUSED" and since is None:
            since = t_ns
        elif event.get("kind") == "RESUMED" and since is not None:
            spans.append((since, t_ns))
            since = None
    if since is not None:
        spans.append((since, 1 << 62))
    return Pauses(spans)


def _trial_events(
    trial_rows: Sequence[dict[str, str]], events: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """For each ``trials.csv`` row its prompt / effect events (the first of each kind with the
    row's id between its start and the next row's) and its ``MISS_CLICK``s (between its start and
    its end)."""
    ordered = sorted(
        (e for e in events if to_int(e.get("t_ns")) is not None), key=lambda e: to_int(e["t_ns"])
    )
    onsets = [to_int(r.get("t_target_shown_ns")) for r in trial_rows]
    out: list[dict[str, Any]] = []
    for i, row in enumerate(trial_rows):
        onset, end = onsets[i], to_int(row.get("t_end_ns"))
        later = next((o for o in onsets[i + 1 :] if o is not None), None)
        trial_id = to_int(row.get("trial_id"))
        found: dict[str, Any] = {"misses": []}
        if onset is not None:
            for e in ordered:
                t = to_int(e["t_ns"])
                if t < onset:
                    continue
                kind = e.get("kind")
                if kind == "MISS_CLICK":
                    if end is not None and t <= end:
                        found["misses"].append(e)
                elif kind in ("PROMPT_START", "PROMPT_END", "EFFECT_START", "EFFECT_END"):
                    if (later is None or t < later) and e.get("trial") == trial_id:
                        found.setdefault(kind, e)
        out.append(found)
    return out


# -- one trial -----------------------------------------------------------------------------------


def _ms(value: float | None, digits: int = 1) -> float | None:
    return round_or_none(value, digits)


def _on_a_button(miss: dict[str, Any]) -> bool:
    slot = to_int(miss.get("selected_slot"))
    return slot is not None and slot >= 0


def _trial_item(
    row: dict[str, str],
    trial: dict[str, Any],
    found: dict[str, Any],
    *,
    series: SampleSeries | None,
    regions: Regions | None,
    pad: tuple[float, float] | None,
    box_at: BoxAt,
    params: LookbackParams,
    pauses: Pauses,
    geometry: Geometry,
    path_index: FrameIndex | None,
) -> dict[str, Any]:
    outcome = trial["outcome"]
    start_event = found.get("PROMPT_START") or {}
    object_id = row.get("prompt_object") or start_event.get("object") or None
    obj = OBJECT_BY_ID.get(object_id) if object_id else None
    slot = obj.slot if obj else None
    # A wrong choice is a completed selection on another button; a switch press off every button
    # (``selected_slot`` -1) is an attempt, not a choice.
    wrong = [e for e in found["misses"] if _on_a_button(e)]
    item: dict[str, Any] = {
        "trial": trial["trial"],
        "outcome": outcome,
        "object": object_id,
        "label": obj.label if obj else None,
        "slot": slot,
        "side": row.get("button_side") or (side_of(slot) if slot is not None else None),
        "selected_object": row.get("selected_object") or None,
        "attempts": trial.get("attempts"),
        "wrong_choices": len(wrong) if found["misses"] or "PROMPT_START" in found else None,
        "wrong_objects": [e.get("selected_object") for e in wrong],
        "modelled": None,
        "reaction_time_s": None,
        "lookback": None, "lookback_latency_ms": None, "lookback_dwell_ms": None,
        "lookback_fraction": None, "lookback_valid_fraction": None,
        "wait_scene_ms": None, "wait_buttons_ms": None, "wait_other_ms": None,
        "wait_valid_fraction": None, "wait_samples": 0, "wait_valid_samples": 0,
        "aoi": None, "lookback_path": [],
    }
    if outcome not in ("hit", "timeout") or obj is None:
        # A skipped trial is the operator's act: nothing to measure, and no wrong choices to count (HD5).
        return {**item, "wrong_choices": None, "wrong_objects": []} if outcome == "skipped" else item
    item["modelled"] = outcome == "timeout"
    ready = to_int(row.get("t_selectable_start_ns"))
    if ready is None and "PROMPT_END" in found:
        ready = to_int(found["PROMPT_END"].get("t_ns"))
    chosen = to_int(row.get("t_click_ns")) if outcome == "hit" else trial.get("end_ns")
    rt_ms = to_float(row.get("rt_ms"))
    if outcome == "hit" and rt_ms is not None:
        item["reaction_time_s"] = round(rt_ms / 1000.0, 3)
    elif ready is not None and chosen is not None:
        item["reaction_time_s"] = round((chosen - ready) / 1e9, 3)
    if pad is not None:
        item["aoi"] = [round(v, 5) for v in aoi_at(box_at, obj.id, 0.0, pad)]
    if series is None:
        return item

    effect_start, effect_end = found.get("EFFECT_START"), found.get("EFFECT_END")
    if pad is not None and effect_start and effect_end:
        start, end = to_int(effect_start.get("t_ns")), to_int(effect_end.get("t_ns"))
        if start is not None and end is not None and end >= start:
            duration = to_float(effect_start.get("duration_ms"))
            result = measure_lookback(series, EffectWindow(obj.id, start, end, duration), box_at, pad, params, pauses)
            item["modelled"] = bool(effect_start.get("modelled", outcome == "timeout"))
            item.update(
                lookback=result.lookback,
                lookback_latency_ms=_ms(result.latency_ms),
                lookback_dwell_ms=_ms(result.dwell_ms),
                lookback_fraction=round_or_none(result.fraction, 4),
                lookback_valid_fraction=round_or_none(result.valid_fraction, 4),
            )
            if path_index is not None:
                after = round(params.after_ms * 1e6)
                item["lookback_path"] = gaze_path(path_index.window(start, end + after), geometry, DEFAULT_PATH)
    if regions is not None and ready is not None and chosen is not None and chosen > ready:
        waited = measure_wait(series, ready, chosen, regions, params, pauses)
        item.update(
            wait_scene_ms=_ms(waited.scene_ms), wait_buttons_ms=_ms(waited.buttons_ms),
            wait_other_ms=_ms(waited.other_ms),
            wait_valid_fraction=round_or_none(waited.valid_fraction, 4),
            wait_samples=waited.n_samples, wait_valid_samples=waited.n_valid,
        )
    return item


# -- the whole test --------------------------------------------------------------------------------


def _median(values: Sequence[float | None], digits: int = 2) -> float | None:
    present = [v for v in values if v is not None]
    return round(statistics.median(present), digits) if present else None


def _group(label_key: str, label: str, members: list[dict[str, Any]] | None, total: int) -> dict[str, Any]:
    """One row of a table: the trials in it and their medians and look-back count."""
    group = members or []
    known = [t for t in group if t["lookback"] is not None]
    wrong = [t["wrong_choices"] for t in group if t["wrong_choices"] is not None]
    return {
        "key": label_key,
        "label": label,
        "n": None if members is None else len(group),
        "N": total,
        "reaction_time_s": _median([t["reaction_time_s"] for t in group]),
        "wrong_choices": round(sum(wrong) / len(wrong), 2) if wrong else None,
        "lookback_yes": sum(1 for t in known if t["lookback"]),
        "lookback_n": len(known),
        "latency_s": _median(
            [None if t["lookback_latency_ms"] is None else t["lookback_latency_ms"] / 1000.0 for t in group]
        ),
    }


def _summary(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    scored = [t for t in items if t["outcome"] in ("hit", "timeout")]
    hits = [t for t in scored if t["outcome"] == "hit"]
    modelled = [t for t in scored if t["outcome"] == "timeout"]
    first_known = all(t["attempts"] is not None for t in hits)
    first = [t for t in hits if t["attempts"] == 1] if first_known else None
    total = len(scored)
    rows = [
        _group("first", "Right on the first choice", first, total),
        _group("right", "All right choices", hits, total),
        _group("modelled", "Not chosen in time (modelled)", modelled, total),
        _group("all", "All trials", scored, total),
    ]
    sides = []
    for side in SIDES:
        on_side = [t for t in scored if t["side"] == side]
        right = [t for t in on_side if t["outcome"] == "hit"]
        row = _group(side, f"{side.capitalize()} buttons", right, len(on_side))
        sides.append(row)
    waited = [t for t in scored if t["wait_valid_fraction"] is not None]
    spent = {k: sum(t[f"wait_{k}_ms"] for t in waited) for k in ("scene", "buttons", "other")}
    total_ms = sum(spent.values())
    n_samples = sum(t["wait_samples"] for t in waited)
    wait = {
        "n": len(waited),
        "total_ms": round(total_ms, 1),
        "scene_pct": round(100.0 * spent["scene"] / total_ms, 1) if total_ms else None,
        "buttons_pct": round(100.0 * spent["buttons"] / total_ms, 1) if total_ms else None,
        "other_pct": round(100.0 * spent["other"] / total_ms, 1) if total_ms else None,
        "valid_pct": round(100.0 * sum(t["wait_valid_samples"] for t in waited) / n_samples, 1)
        if n_samples
        else None,
    }
    return {"n_scored": total, "rows": rows, "sides": sides, "wait": wait}


def _buttons(
    items: Sequence[dict[str, Any]], regions: Regions, box_at: BoxAt, pad: tuple[float, float] | None
) -> list[dict[str, Any]]:
    """The eight buttons for the Scene Map: their rectangle, the object's idle box and look-back
    area (canvas fractions) and what happened on them (W6)."""
    out = []
    for obj in OBJECTS:
        idle = scene_box_to_canvas(box_at(obj.id, 0.0))
        mine = [t for t in items if t["slot"] == obj.slot]
        out.append(
            {
                "slot": obj.slot, "object": obj.id, "label": obj.label, "side": side_of(obj.slot),
                "rect": [round(v, 5) for v in regions.buttons[obj.slot]],
                "box": [round(v, 5) for v in idle],
                "aoi": None if pad is None else [round(v, 5) for v in aoi_at(box_at, obj.id, 0.0, pad)],
                "right": sum(1 for t in mine if t["outcome"] == "hit"),
                "timeouts": sum(1 for t in mine if t["outcome"] == "timeout"),
            }
        )
    return out


def _button_deg(geometry: Geometry) -> list[float] | None:
    """The size of one cell of the 7 x 5 board in degrees (width, height); ``None`` without the
    canvas's physical size and the viewing distance."""
    cell = geometry.canvas_cell_deg(GRID_COLS, GRID_ROWS)
    return None if cell is None else [round(cell[0], 1), round(cell[1], 1)]


def build_choice(
    trial_rows: Sequence[dict[str, str]],
    trials: Sequence[dict[str, Any]],
    *,
    events: Sequence[dict[str, Any]],
    geometry: Geometry,
    series: SampleSeries | None,
    source: str | None,
    gap_px: float | None = None,
    path_index: FrameIndex | None = None,
    box_at: BoxAt | None = None,
    params: LookbackParams = DEFAULT_LOOKBACK,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``choice`` block of ``report.json``.

    ``trials`` are the dicts of :func:`~.report_metrics.build_trials` (same order as ``trial_rows``);
    their outcome and window are reused so the blocks cannot disagree. ``series`` / ``source`` are
    :func:`choose_series`'s. ``extras`` (scene, language, visual_cue, idle_animation, ...) are the
    run's settings the page shows; they are copied in as they are. ``box_at`` is the AOI provider
    (:func:`default_box_at`)."""
    box_at = box_at or default_box_at(str((extras or {}).get("scene") or "park"))
    pad = pad_norm(geometry, params.pad_deg)
    regions = board_regions(geometry, gap_px)
    drawn = regions or board_regions(NOMINAL_CANVAS, gap_px)
    pauses = pause_spans(events) if events else NO_PAUSES
    per_trial = _trial_events(trial_rows, events)
    items = [
        _trial_item(
            row, trial, found, series=series, regions=regions, pad=pad, box_at=box_at,
            params=params, pauses=pauses, geometry=geometry, path_index=path_index,
        )
        for row, trial, found in zip(trial_rows, trials, per_trial, strict=True)
    ]
    return {
        **(extras or {}),
        "source": source,
        "pointer_not_gaze": source == SOURCE_POINTER,
        "params": params.as_dict(),
        "padded": pad is not None,
        "button_deg": _button_deg(geometry),
        "scene_box": [round(v, 5) for v in drawn.scene],
        "buttons": _buttons(items, drawn, box_at, pad),
        "trials": items,
        "summary": _summary(items),
    }


# -- the trials.csv columns --------------------------------------------------------------------------


def _csv_value(item: dict[str, Any], column: str) -> str:
    value = item.get(column)
    if value is None:
        return ""
    return str(int(value)) if column == "lookback" else str(value)


def fill_trials_lookback(session_dir: str | Path, choice: dict[str, Any]) -> bool:
    """Write the look-back and waiting-phase figures of ``choice`` into the last columns of the
    run's ``trials.csv`` (one row per trial, in order; blank where a figure is ``None``). The file
    is rewritten whole beside itself and moved into place. Returns False, touching nothing, when
    the file is missing or has another number of rows than the block."""
    path = Path(session_dir) / "trials.csv"
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            header = list(reader.fieldnames or [])
    except OSError:
        return False
    items = choice.get("trials") or []
    if not rows or len(rows) != len(items):
        return False
    header += [c for c in LOOKBACK_COLUMNS if c not in header]
    for row, item in zip(rows, items, strict=True):
        for column in LOOKBACK_COLUMNS:
            row[column] = _csv_value(item, column)
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(part, path)
    return True
