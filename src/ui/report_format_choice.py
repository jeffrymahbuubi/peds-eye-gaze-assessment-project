"""Choice-making's text for the per-test report (SPEC-scene-cause-effect-task.md 4.9, W4, W6, S7;
wireframe ``docs/wireframes/choice-making.md`` part C). Qt-free, like :mod:`report_format`, whose
figure helpers it uses.

Read from the ``choice`` block of ``report.json`` (:mod:`src.data.report_choice`) exactly as built:
nothing is computed here beyond rounding. A figure the report could not give is a dash. Look-back is
always Yes / No (W4) with the share of valid samples beside it, and the trials that timed out and
got the effect as a model are counted apart (H7). A Mouse run's look-back is the pointer's, and the
words say so ("pointer, not gaze", 4.6).
"""

from __future__ import annotations

from typing import Any, NamedTuple

from ..tasks.choice_layout import OBJECT_BY_ID
from .report_format import (
    DASH,
    DEFINITIONS,
    NOT_RECORDED,
    Cell,
    gaze_was_recorded,
    num,
    percent_text,
    whole,
)

CHOICE_OUTCOME_LABELS = {"hit": "Right", "timeout": "Modelled", "skipped": "Skipped"}
IDLE_ANIMATION_LABELS = {"off": "Off", "blinks": "Blinks", "blinks_bob": "Blinks and bob"}

CHOICE_SUMMARY_ALIGNS = ["left", "right", "right", "right", "right", "right"]
SIDE_ALIGNS = ["left", "right", "right", "right"]
WAIT_ALIGNS = ["left", "right"]
# The Detailed table's columns (wireframe C2); the three look-back ones and "Gaze on" are named for
# the pointer of a Mouse run instead of the gaze.
CHOICE_TRIAL_ALIGNS = ["center", "left", "left", "left", "left"] + ["right"] * 11


class ExtraTable(NamedTuple):
    """A table under the Summary of Results: a heading, a header row, rows, alignments, a note."""

    title: str
    header: tuple[str, ...]
    rows: list[list[str]]
    aligns: list[str]
    note: str


def choice_block(report: dict[str, Any]) -> dict[str, Any] | None:
    """The ``choice`` block when the report is a Choice-making one, else ``None`` (another task, a
    report with no block, or one cached before the block existed)."""
    block = report.get("choice")
    if isinstance(block, dict) and isinstance(block.get("trials"), list):
        return block
    return None


def _pointer(block: dict[str, Any]) -> bool:
    return bool(block.get("pointer_not_gaze"))


def _words(block: dict[str, Any]) -> dict[str, str]:
    """The names of the look-back columns: the gaze's, or the pointer's for a Mouse run."""
    if _pointer(block):
        return {
            "back": "Pointer back (not gaze)", "latency": "Pointer-back latency (s)",
            "time": "Pointer-back time (s)", "on": "Pointer on", "valid": "pointer",
        }
    return {
        "back": "Looked back", "latency": "Look-back latency (s)", "time": "Look-back time (s)",
        "on": "Gaze on", "valid": "gaze",
    }


def choice_summary_header(report: dict[str, Any]) -> tuple[str, ...]:
    words = _words(choice_block(report) or {})
    return ("", "% (N)", "Reaction Time (s)", "Wrong choices", words["back"], words["latency"])


def _looked(row: dict[str, Any]) -> str:
    """``89% (8/9)``: the trials with a look-back over the ones that could tell."""
    known, yes = row.get("lookback_n"), row.get("lookback_yes")
    if not known:
        return DASH
    return f"{int(100.0 * yes / known + 0.5)}% ({yes}/{known})"


def choice_summary_rows(report: dict[str, Any]) -> list[list[str]]:
    """The four Summary of Results rows (wireframe C1)."""
    block = choice_block(report)
    if block is None:
        return []
    return [
        [
            str(row.get("label", "")),
            percent_text(row),
            num(row.get("reaction_time_s"), 2),
            num(row.get("wrong_choices"), 1),
            _looked(row),
            num(row.get("latency_s"), 2),
        ]
        for row in (block.get("summary") or {}).get("rows", [])
    ]


def choice_info(report: dict[str, Any]) -> str:
    """The line above the summary about how the test was made: the visual cue (S3), a Mouse run."""
    block = choice_block(report)
    if block is None:
        return ""
    parts = []
    if block.get("visual_cue"):
        parts.append("Visual cue was on: the target button pulsed.")
    if _pointer(block):
        parts.append("Mouse run: the look-back figures are the pointer's, not gaze.")
    return " ".join(parts)


def choice_footnote(report: dict[str, Any]) -> str:
    """The note under the Summary of Results table."""
    block = choice_block(report)
    if block is None:
        return ""
    session = report.get("session", {})
    pad = (block.get("params") or {}).get("pad_deg", 1.0)
    parts = []
    if session.get("n_skipped"):
        parts.append(f"{session['n_skipped']} skipped trial(s) excluded.")
    if session.get("n_not_presented"):
        parts.append(f"{session['n_not_presented']} planned trial(s) not presented.")
    parts.append(
        "Reaction Time = prompt end to the right choice (for a modelled trial, to the end of the time "
        "to choose); it and the latency are medians. Wrong choices = selections on another button, "
        f"the mean per trial. {_words(block)['back']} = at least 0.1 s on the animating object (its "
        f"area plus {whole(pad)}°) during the animation and 0.5 s after it. Latency = animation start "
        "to the first look. Modelled trials (the effect shown after a timeout) are counted apart."
    )
    if block.get("source") is None:
        parts.append("No gaze or pointer was recorded, so there are no look-back figures.")
    elif not block.get("padded"):
        parts.append("The run did not record the screen's size, so the look-back area could not be placed.")
    return " ".join(parts)


def _side_table(block: dict[str, Any]) -> ExtraTable:
    words = _words(block)
    rows = [
        [
            str(row.get("label", "")),
            percent_text(row),
            num(row.get("reaction_time_s"), 2),
            _looked(row),
        ]
        for row in (block.get("summary") or {}).get("sides", [])
    ]
    return ExtraTable(
        "By button side", ("Side", "Right choices", "Reaction Time (s)", words["back"]), rows,
        SIDE_ALIGNS, "",
    )


def _wait_table(block: dict[str, Any]) -> ExtraTable:
    words = _words(block)
    wait = (block.get("summary") or {}).get("wait") or {}

    def share(key: str) -> str:
        value = wait.get(key)
        return DASH if value is None else f"{whole(value)}%"

    valid = wait.get("valid_pct")
    note = (
        f"Measured from the prompt end to the choice or the timeout, valid {words['valid']} only. "
        f"Valid {words['valid']} while choosing: {DASH if valid is None else whole(valid) + ' %'}."
    )
    rows = [["Scene", share("scene_pct")], ["Buttons", share("buttons_pct")], ["Elsewhere", share("other_pct")]]
    return ExtraTable("While choosing", (words["on"], "Share of the time to choose"), rows, WAIT_ALIGNS, note)


def choice_extra_tables(report: dict[str, Any]) -> list[ExtraTable]:
    """The tables under the Summary of Results: by button side, and while choosing (S7)."""
    block = choice_block(report)
    return [] if block is None else [_side_table(block), _wait_table(block)]


# -- the Trial-by-Trial table -----------------------------------------------------------------------


def choice_trial_columns(report: dict[str, Any]) -> tuple[str, ...]:
    words = _words(choice_block(report) or {})
    return (
        "Trial", "Prompt", "Side", "Outcome", "Chosen", "Wrong choices", "Reaction Time (s)",
        words["back"], words["latency"], words["time"], "Valid (%)", "Scene / Buttons / Else (%)",
        "Fixations", "Saccades", "Pupil (mm)", "Pupil change (mm)",
    )


def _object_name(object_id: Any) -> str:
    obj = OBJECT_BY_ID.get(str(object_id))
    return obj.label if obj else DASH


def _shares(item: dict[str, Any]) -> Cell:
    """``30 / 62 / 8``: where the valid gaze was while choosing, in per cent of that time."""
    parts = [item.get(f"wait_{k}_ms") for k in ("scene", "buttons", "other")]
    total = sum(p for p in parts if p is not None)
    if any(p is None for p in parts) or total <= 0:
        return Cell(DASH, None)
    shares = [100.0 * p / total for p in parts]
    return Cell(" / ".join(whole(s) for s in shares), shares[0])


def choice_trial_cells(report: dict[str, Any], index: int) -> list[Cell]:
    """The 16 cells of one row (:func:`choice_trial_columns`) for the report trial ``index``: the
    choice and look-back figures of the ``choice`` block, then the usual eye columns."""
    block = choice_block(report) or {}
    trial = report.get("trials", [])[index]
    items = block.get("trials") or []
    item = items[index] if index < len(items) else {}
    fix, sac, pup = trial.get("fixations", {}), trial.get("saccades", {}), trial.get("pupil", {})
    outcome = CHOICE_OUTCOME_LABELS.get(str(trial.get("outcome")), NOT_RECORDED)

    def number(value: Any, digits: int, *, signed: bool = False, scale: float = 1.0) -> Cell:
        if value is None:
            return Cell(DASH, None)
        return Cell(num(value * scale, digits, signed=signed), float(value) * scale)

    back = item.get("lookback")
    looked = Cell(DASH, None) if back is None else Cell("Yes" if back else "No", float(back))
    wrong = item.get("wrong_objects") or []
    wrong_cell = number(item.get("wrong_choices"), 0)._replace(tip=", ".join(_object_name(o) for o in wrong))
    side = str(item.get("side") or "")
    chosen = _object_name(item["selected_object"]) if item.get("selected_object") else DASH
    valid = item.get("lookback_valid_fraction")
    cells = [
        Cell(str(trial.get("trial", "")), float(trial.get("trial") or 0)),
        Cell(item.get("label") or DASH, item.get("label")),
        Cell(side.capitalize() or DASH, side or None),
        Cell(outcome, None if outcome == NOT_RECORDED else outcome),
        Cell(chosen, None if chosen == DASH else chosen),
        wrong_cell,
        number(item.get("reaction_time_s"), 2),
        looked,
        number(item.get("lookback_latency_ms"), 2, scale=0.001),
        number(item.get("lookback_dwell_ms"), 2, scale=0.001),
        number(valid, 0, scale=100.0),
        _shares(item),
        number(fix.get("count"), 0),
        number(sac.get("count"), 0),
        number(pup.get("mean_mm"), 2),
        number(pup.get("change_mm"), 2, signed=True),
    ]
    if not gaze_was_recorded(report) and trial.get("outcome") != "skipped":
        cells[-4:] = [Cell(NOT_RECORDED, None) for _ in range(4)]
    return cells


CHOICE_DEFINITIONS = (
    "Right: the prompted button was selected within the time to choose. Modelled: it was not, so the "
    "object's effect was shown once as a model; these trials are counted apart.",
    "Reaction Time: from the end of the spoken prompt to the right choice (selection is blocked while "
    "the prompt plays).",
    "Wrong choices: completed selections (a dwell, or a switch press) on a button other than the prompted "
    "one; the trial goes on until the right choice or the timeout.",
    "Looked back: at least 0.1 s of valid gaze on the animating object, its area plus 1° of visual angle "
    "(following the object when its effect moves it), from the start of the animation to 0.5 s after it "
    "ends. The latency is the time to the first such sample; the look-back time is the time spent on it.",
    "Valid (%): the share of the look-back window's samples with valid gaze, so that a trial with lost "
    "gaze is not read as \"did not look\".",
    "Scene / Buttons / Else: the valid gaze between the end of the prompt and the choice (or the "
    "timeout), as a share of that time, on the scene, on a button and elsewhere.",
    *(d for d in DEFINITIONS if d.startswith(("Fixations", "Saccades", "Pupil change", "Skipped"))),
)
