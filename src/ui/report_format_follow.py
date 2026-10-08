"""Follow the Target's text for the per-test report (SPEC-input-selection-and-follow.md 4.5,
W2, H6, H8; wireframes ``report-summary.md`` / ``report-detailed.md``). Qt-free, like
:mod:`report_format`, whose figure helpers it uses.

Read from the ``follow`` block of ``report.json`` (:mod:`src.data.report_follow`) exactly as
built: nothing is computed here beyond rounding. A figure the report could not give is a dash,
and a figure that needs the eye tracker says "not recorded" for a test with no gaze recorded
(a Mouse test with no tracker). An old Follow & Click folder (``follow.legacy``) is not a
Follow layout: it keeps the selection tables of :mod:`report_format`.
"""

from __future__ import annotations

from typing import Any

from .report_format import (
    DASH,
    DEFINITIONS,
    NOT_RECORDED,
    OUTCOME_LABELS,
    Cell,
    gaze_was_recorded,
    hit_tolerance_px,
    num,
    whole,
)

DEFAULT_FOLLOWED_PCT = 50.0  # H6, when a report does not carry its params

# The column labels are the wireframe's. Time columns say (s), the angle ones (deg) (V5).
FOLLOW_TRIAL_COLUMNS = (
    "Trial", "Path", "Outcome", "Duration (s)", "Time on target (%)", "Mean distance (deg)",
    "Time to find (s)", "Pursuit gain", "Catch-up sacc. (/s)", "Valid (%)", "Fixations",
    "Saccades", "Pupil (mm)", "Pupil change (mm)",
)
# The first of the eye columns after the follow ones (Pursuit gain and Catch-up are the tracker's too).
_EYE_FROM = FOLLOW_TRIAL_COLUMNS.index("Pursuit gain")
FOLLOW_SUMMARY_COLUMNS = ("Metric", "Value")

# What the Path column says: short, the test's own setting (the configuration table has the long form).
PATH_LABELS = {
    "circular": "Circular",
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "diagonal_tlbr": "Diagonal TL-BR",
    "diagonal_trbl": "Diagonal TR-BL",
}

GAIN_CAPTION = (
    "Smooth-pursuit gain = eye speed divided by target speed, saccades removed; children's typical "
    "range is about 0.6 to 0.85, lower for vertical movement. It is not a pass or fail value."
)

# The PDF's footnotes for a Follow report: what each figure means (the common ones are kept).
FOLLOW_DEFINITIONS = (
    "Trial duration: every trial lasts the same fixed time, whatever the child does.",
    "Followed: the pointer (gaze, or the mouse) was on the target for at least half of the time it "
    "was valid. The share is fixed in this version.",
    "Time on target: the share of the valid pointer time spent within the target area (the drawn "
    "target plus its tolerance ring).",
    "Mean distance to target: the mean distance from the pointer to the target's centre, in degrees "
    "of visual angle, over the valid pointer time.",
    "Time to find target: from the target appearing to the first time the pointer entered the "
    "target area.",
    "Smooth-pursuit gain: the gaze speed along the target's direction divided by the target's speed, "
    "with saccades removed and only the gaze within 3 degrees of the target; the median over the "
    "trial, then over the trials. It needs the eye tracker.",
    "Catch-up saccades: saccades (velocity threshold 50 deg/s) per second of valid gaze during the "
    "trial. It needs the eye tracker.",
    "Valid pointer: the share of the trial with a valid pointer; a blink or lost tracking is not valid.",
    *(d for d in DEFINITIONS if d.startswith(("Fixations", "Saccades", "Pupil change", "Skipped")))
)


def follow_block(report: dict[str, Any]) -> dict[str, Any] | None:
    """The ``follow`` block when the report is a Follow the Target one, else ``None``: a
    report of another task, one with no block, and an old Follow & Click folder (its block is
    only ``{"legacy": true}``) all give ``None`` and keep the selection layout (H10)."""
    block = report.get("follow")
    if isinstance(block, dict) and not block.get("legacy") and isinstance(block.get("trials"), list):
        return block
    return None


def followed_pct(block: dict[str, Any]) -> float:
    value = (block.get("params") or {}).get("followed_pct")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else DEFAULT_FOLLOWED_PCT


def _tracker(gaze_recorded: bool, value: Any, text: str) -> str:
    """``text`` for a figure only the eye tracker gives: a dash when it could not be built,
    "not recorded" when the test recorded no gaze at all."""
    if not gaze_recorded:
        return NOT_RECORDED
    return DASH if value is None else text


def follow_summary_rows(report: dict[str, Any]) -> list[list[str]]:
    """The Metric / Value rows that stand in for the Summary of Results table (W2)."""
    block = follow_block(report)
    if block is None:
        return []
    summary = block.get("summary") or {}
    gaze = gaze_was_recorded(report)
    share = summary.get("time_on_target_pct") or {}
    mean, low, high = share.get("mean"), share.get("min"), share.get("max")
    on_target = DASH
    if mean is not None:
        on_target = f"{whole(mean)} %"
        if low is not None and high is not None and round(low) != round(high):
            on_target += f" (range {whole(low)}–{whole(high)} %)"
    followed, total = summary.get("followed"), summary.get("n_trials")
    gain, catch = summary.get("pursuit_gain"), summary.get("catch_up_per_s")
    distance, find, valid = summary.get("mean_distance_deg"), summary.get("time_to_find_s"), summary.get("valid_pct")
    return [
        [
            f"Followed (on target at least {whole(followed_pct(block))} % of the trial)",
            DASH if followed is None or total is None else f"{followed} of {total}",
        ],
        ["Time on target", on_target],
        ["Mean distance to target", DASH if distance is None else f"{num(distance, 1)}°"],
        ["Time to find target", DASH if find is None else f"{num(find, 2)} s"],
        ["Smooth-pursuit gain", _tracker(gaze, gain, f"{num(gain, 2)} (median)")],
        ["Catch-up saccades", _tracker(gaze, catch, f"{num(catch, 1)} per s")],
        ["Valid pointer during trials", DASH if valid is None else f"{whole(valid)} %"],
    ]


def follow_footnote(report: dict[str, Any]) -> str:
    """The note under the Follow summary table: the skipped trials, what "on target" and
    "followed" mean, and the gain's caution."""
    block = follow_block(report)
    if block is None:
        return ""
    session = report.get("session", {})
    parts = []
    skipped, not_presented = session.get("n_skipped"), session.get("n_not_presented")
    if skipped:
        parts.append(f"{skipped} skipped trial(s) excluded.")
    if not_presented:
        parts.append(f"{not_presented} planned trial(s) not presented.")
    parts.append(f"On target = within the drawn target + {hit_tolerance_px(report):g} px tolerance ring.")
    parts.append(
        f"Followed = on target at least {whole(followed_pct(block))} % of the valid time (a fixed "
        "threshold in this version)."
    )
    parts.append(GAIN_CAPTION)
    return " ".join(parts)


def follow_trial_cells(report: dict[str, Any], index: int) -> list[Cell]:
    """The 14 cells of one Follow the Target row (:data:`FOLLOW_TRIAL_COLUMNS`) for the report
    trial ``index``: its follow figures, then the usual eye columns."""
    block = follow_block(report) or {}
    trial = report.get("trials", [])[index]
    rows = block.get("trials") or []
    figures = rows[index] if index < len(rows) else {}
    fix, sac, pup = trial.get("fixations", {}), trial.get("saccades", {}), trial.get("pupil", {})
    outcome = OUTCOME_LABELS.get(str(trial.get("outcome")), NOT_RECORDED)
    path = PATH_LABELS.get(str(block.get("path")), NOT_RECORDED)

    def number(value: Any, digits: int, *, signed: bool = False) -> Cell:
        return Cell(num(value, digits, signed=signed), None if value is None else float(value))

    cells = [
        Cell(str(trial.get("trial", "")), float(trial.get("trial") or 0)),
        Cell(path, None if path == NOT_RECORDED else path),
        Cell(outcome, None if outcome == NOT_RECORDED else outcome),
        number(figures.get("duration_s"), 1),
        number(figures.get("time_on_target_pct"), 0),
        number(figures.get("mean_distance_deg"), 1),
        number(figures.get("time_to_find_s"), 2),
        number(figures.get("pursuit_gain"), 2),
        number(figures.get("catch_up_per_s"), 1),
        number(figures.get("valid_pct"), 0),
        number(fix.get("count"), 0),
        number(sac.get("count"), 0),
        number(pup.get("mean_mm"), 2),
        number(pup.get("change_mm"), 2, signed=True),
    ]
    if not gaze_was_recorded(report) and trial.get("outcome") != "skipped":
        cells[_EYE_FROM:] = [Cell(NOT_RECORDED, None) for _ in cells[_EYE_FROM:]]
    return cells


def follow_trial_aligns() -> list[str]:
    """Alignment of each trial column: the number centred, the words left, the figures right."""
    return ["center", "left", "left"] + ["right"] * (len(FOLLOW_TRIAL_COLUMNS) - 3)

