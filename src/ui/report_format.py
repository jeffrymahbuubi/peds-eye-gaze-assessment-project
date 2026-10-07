"""Text of the per-test report: what the page and the PDF show for each figure
(SPEC-compass-task-flow.md 4D.2, 4D.8; wireframes ``report-summary.md`` /
``report-detailed.md``). Qt-free.

The numbers are read from ``report.json`` (:mod:`src.data.report_cache`) exactly as
built; nothing is computed here beyond rounding for display. A figure the report
could not give (``None``) is "—", never 0 (4D.9). Shared by :class:`ReportPage` and
the PDF so the two can never disagree about a label or a rounding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, NamedTuple

from ..data.report_util import ms_to_seconds, seconds_text
from ..engine.session_naming import safe_subject_dirname

DASH = "—"
NOT_RECORDED = "not recorded"  # what the eye sections say of a Mouse test with no tracker
DEFAULT_HIT_TOLERANCE_PX = 40.0  # dwell.jitter_tolerance_px's default: the hitbox margin

OUTCOME_LABELS = {
    "hit": "Hit",
    "timeout": "Not selected",
    "skipped": "Skipped",
    # Follow the Target (SPEC-input-selection-and-follow.md H6): on target for at least half
    # of the trial or not.
    "followed": "Followed",
    "not_followed": "Not followed",
}

# One English sentence per task, under the Summary's heading (4D.2).
TASK_SENTENCES = {
    "click_static": "A single target appears on an empty field; the child selects it by looking at it.",
    "click_grid": "One cell of a visible board lights up; the child selects it by looking at it.",
    "follow_moving": "A target travels across the screen; the child follows it and nothing is selected.",
    "scanning": "The child finds the cued shape among other shapes and selects it by looking at it.",
}
# An old Follow & Click session (selection window, a click or dwell; SPEC H10) keeps its sentence.
LEGACY_FOLLOW_SENTENCE = (
    "A target travels across the screen; the child follows it and selects it by looking at it."
)


def task_sentence(report: dict[str, Any]) -> str:
    """The one sentence under the Summary's heading for this report's task."""
    session = report.get("session") or {}
    task_id = session.get("task_id")
    follow = report.get("follow")
    if task_id == "follow_moving" and isinstance(follow, dict) and follow.get("legacy"):
        return LEGACY_FOLLOW_SENTENCE
    return TASK_SENTENCES.get(task_id, "")

SUMMARY_COLUMNS = ("", "% (N)", "Trial Time (s)", "Reaction Time (s)", "Entries")
TRIAL_COLUMNS = (
    "Trial", "Size (deg)", "Distance (deg)", "Outcome", "Trial Time (s)", "Reaction Time (s)",
    "Entries", "Fixations", "Mean fix. dur. (s)", "Saccades", "Mean peak vel. (deg/s)",
    "Pupil (mm)", "Pupil change (mm)",
)

EYE_NOTE = (
    "Peak saccade velocity is a smoothed value. Compare it only between children measured on "
    "the same device and sample rate. Old sessions without the new fields show \"—\"."
)

# The PDF's footnotes (4D.8): what each measure means, so a printed page stands alone.
DEFINITIONS = (
    "Trial Time: from the target appearing to its selection (Hit) or to the end of the trial (Not selected).",
    "Reaction Time: from the target appearing to the first time the gaze entered the target area; "
    "about 0 if the gaze already rested on the new target's place.",
    "Entries: how many separate times the gaze entered the target area (leaving for less than "
    f"{seconds_text(120)} does not count as a new entry).",
    "Error-free Target Selection: a Hit selected on the first gaze entry, with no earlier attempt.",
    "Fixations follow the Gazepoint definition and count for the trial in which they start.",
    "Saccades are found by velocity threshold (50 deg/s) on the device-rate gaze; peak velocity is a "
    "smoothed value, comparable only between children measured on the same device and sample rate.",
    f"Pupil change: the mean diameter during the trial minus the mean of the {seconds_text(300)} before "
    f"the target appeared; blinks ({seconds_text(100)} either side of any invalid sample) are excluded.",
    "Skipped trials are excluded from every percentage.",
)


def num(value: Any, digits: int = 1, *, signed: bool = False) -> str:
    """A number to ``digits`` decimals ("—" for ``None`` or anything not a number)."""
    if value is None or isinstance(value, bool):
        return DASH
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DASH
    return f"{number:+.{digits}f}" if signed else f"{number:.{digits}f}"


def whole(value: Any) -> str:
    """A whole-number figure (a count, a rounded rate)."""
    return num(value, 0)


def seconds_figure(ms: Any, digits: int = 2) -> str:
    """A stored millisecond figure as seconds to ``digits`` decimals, no unit ("0.23"): for
    table cells whose column says "(s)". "—" for ``None`` or anything not a number. The data
    files keep milliseconds; every text a person reads shows seconds (V5)."""
    return num(ms_to_seconds(ms), digits)


def percent_text(row: dict[str, Any]) -> str:
    """``61% (11/18)``: the share rounded to a whole percent (the wireframe's form),
    "—" when the row's count is unknown, ``0% (0/N)`` for an empty row."""
    n, total = row.get("n"), row.get("N") or 0
    if n is None:
        return DASH
    share = int(100.0 * n / total + 0.5) if total else 0
    return f"{share}% ({n}/{total})"


def summary_table(report: dict[str, Any]) -> list[list[str]]:
    """The four Summary of Results rows as display text (the columns are
    :data:`SUMMARY_COLUMNS`)."""
    return [
        [
            str(row.get("label", "")),
            percent_text(row),
            num(row.get("trial_time_s"), 2),
            num(row.get("reaction_time_s"), 2),
            num(row.get("entries"), 1),
        ]
        for row in report.get("summary", {}).get("rows", [])
    ]


def _part(text: str, value: Any) -> str:
    return DASH if value is None else text


def eye_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    """The whole-test Eye Metrics as ``(label, value)`` text (wireframe order)."""
    eye = report.get("summary", {}).get("eye", {})
    fix = eye.get("fixations", {})
    dur = eye.get("fixation_duration_ms", {})
    sac = eye.get("saccades", {})
    pup = eye.get("pupil", {})
    cal = eye.get("calibration", {})

    fixations = DASH
    if fix.get("count") is not None:
        fixations = f"{fix['count']}"
        if fix.get("mean_per_trial") is not None:
            fixations += f" ({num(fix['mean_per_trial'], 1)} per trial)"
    duration = DASH
    if dur.get("mean") is not None:
        duration = f"{seconds_figure(dur['mean'])} s"
        if dur.get("median") is not None:
            duration += f" (median {seconds_figure(dur['median'])} s)"
    velocity = DASH
    if sac.get("mean_peak_velocity_deg_s") is not None:
        velocity = f"{whole(sac['mean_peak_velocity_deg_s'])} deg/s"
        if sac.get("max_peak_velocity_deg_s") is not None:
            velocity += f" (max {whole(sac['max_peak_velocity_deg_s'])})"
    change = DASH
    if pup.get("mean_change_mm") is not None:
        change = f"{num(pup['mean_change_mm'], 2, signed=True)} mm"
        if pup.get("mean_change_pct") is not None:
            change += f" ({num(pup['mean_change_pct'], 1, signed=True)} %)"
    calibration_parts = []
    if cal.get("error_deg") is not None:
        calibration_parts.append(f"{num(cal['error_deg'], 1)}°")
    if cal.get("error_px") is not None:
        calibration_parts.append(f"({whole(cal['error_px'])} px)")
    calibration = " ".join(calibration_parts) or DASH
    if calibration_parts and cal.get("source"):
        calibration += f", {cal['source']}"

    rows = [
        ("Fixations", fixations),
        ("Mean fixation duration", duration),
        ("Saccades", DASH if sac.get("count") is None else str(sac["count"])),
        ("Mean saccade amplitude", _part(f"{num(sac.get('mean_amplitude_deg'), 1)}°", sac.get("mean_amplitude_deg"))),
        ("Mean peak saccade velocity", velocity),
        (
            "Scan-path length per trial",
            _part(f"{num(eye.get('scanpath_deg_per_trial'), 1)}°", eye.get("scanpath_deg_per_trial")),
        ),
        ("Mean pupil diameter", _part(f"{num(pup.get('mean_mm'), 2)} mm", pup.get("mean_mm"))),
        ("Mean pupil change from baseline", change),
        ("Valid gaze during trials", _part(f"{whole(eye.get('valid_gaze_pct'))} %", eye.get("valid_gaze_pct"))),
        ("Calibration error", calibration),
    ]
    if report.get("session", {}).get("gaze_recorded") is False:
        # A Mouse test with no tracker (SPEC-input-selection-and-follow.md A5): there was
        # no eye data to give, which is not the same as a figure that could not be built.
        return [(label, NOT_RECORDED) for label, _value in rows]
    return rows


class Cell(NamedTuple):
    """One table cell: the text shown and the value the column sorts by (``None``
    sorts last, in either direction)."""

    text: str
    key: float | str | None


def trial_cells(trial: dict[str, Any]) -> list[Cell]:
    """The 13 cells of one Trial-by-Trial row (the columns are :data:`TRIAL_COLUMNS`)."""
    fix, sac, pup = trial.get("fixations", {}), trial.get("saccades", {}), trial.get("pupil", {})
    outcome = OUTCOME_LABELS.get(str(trial.get("outcome")), DASH)

    def number(value: Any, digits: int, *, signed: bool = False) -> Cell:
        return Cell(num(value, digits, signed=signed), None if value is None else float(value))

    return [
        Cell(str(trial.get("trial", "")), float(trial.get("trial") or 0)),
        number(trial.get("size_deg"), 1),
        number(trial.get("distance_deg"), 1),
        Cell(outcome, None if outcome == DASH else outcome),
        number(trial.get("trial_time_s"), 2),
        number(trial.get("reaction_time_s"), 2),
        number(trial.get("entries"), 0),
        number(fix.get("count"), 0),
        Cell(seconds_figure(fix.get("mean_dur_ms")), ms_to_seconds(fix.get("mean_dur_ms"))),
        number(sac.get("count"), 0),
        number(sac.get("mean_peak"), 0),
        number(pup.get("mean_mm"), 2),
        number(pup.get("change_mm"), 2, signed=True),
    ]


def _count(value: Any, noun: str) -> str:
    if value is None:
        return f"{DASH} {noun}s"
    return f"{value} {noun}" if value == 1 else f"{value} {noun}s"


def trial_line(trial: dict[str, Any]) -> str:
    """The line under the selected-trial map: scan path, fixations, saccades."""
    sac, fix = trial.get("saccades", {}), trial.get("fixations", {})
    path = sac.get("scanpath_deg")
    path_text = f"Scan path {num(path, 1)} deg" if path is not None else f"Scan path {DASH}"
    return " · ".join([path_text, _count(fix.get("count"), "fixation"), _count(sac.get("count"), "saccade")])


def banner_lines(report: dict[str, Any]) -> list[str]:
    """The warnings of the banner under the header: an early end, low valid gaze, a
    resized canvas (4D.2, 4D.1 X6). The report's own text for any other code."""
    quality = report.get("quality", {})
    lines = []
    for warning in quality.get("warnings", []):
        code, text = warning.get("code"), str(warning.get("text", ""))
        share = quality.get("valid_share")
        if code == "low_valid_gaze" and share is not None:
            text = f"Gaze data is low quality: {whole(100.0 * share)} % valid"
        lines.append(text)
    return lines


def hit_tolerance_px(report: dict[str, Any]) -> float:
    """The hitbox margin of the "Target area" footnote and the map's dashed ring:
    ``map.hit_tolerance_px`` when a report carries it, else the 40 px default."""
    value = report.get("map", {}).get("hit_tolerance_px")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return DEFAULT_HIT_TOLERANCE_PX


def summary_footnote(report: dict[str, Any]) -> str:
    """The note under the Summary table (4D.2)."""
    session = report.get("session", {})
    parts = []
    skipped, not_presented = session.get("n_skipped"), session.get("n_not_presented")
    if skipped:
        parts.append(f"{skipped} skipped trial(s) excluded.")
    if not_presented:
        parts.append(f"{not_presented} planned trial(s) not presented.")
    parts.append(f"Target area = drawn target + {hit_tolerance_px(report):g} px tolerance ring.")
    parts.append(
        "Reaction Time = onset to the first gaze entry; about 0 if the gaze already rested on the "
        "new target's place."
    )
    return " ".join(parts)


def started_text(started_ns: Any) -> str:
    """``Oct 6, 2026 2:06 PM`` in local time ("—" when the run has no start time)."""
    if not isinstance(started_ns, int) or isinstance(started_ns, bool):
        return DASH
    try:
        moment = datetime.fromtimestamp(started_ns / 1e9)
    except (OverflowError, OSError, ValueError):
        return DASH
    hour = moment.hour % 12 or 12
    return f"{moment:%b} {moment.day}, {moment.year} {hour}:{moment:%M} {'AM' if moment.hour < 12 else 'PM'}"


def pdf_default_name(subject: str, test_name: str, started_ns: Any) -> str:
    """``<Subject>_<Test name>_<YYYY-MM-DD>.pdf`` (4D.8); the date is the test's own."""
    try:
        day = f"{datetime.fromtimestamp(started_ns / 1e9):%Y-%m-%d}"
    except (TypeError, OverflowError, OSError, ValueError):
        day = "undated"
    return f"{safe_subject_dirname(subject or 'subject')}_{safe_subject_dirname(test_name or 'report')}_{day}.pdf"
