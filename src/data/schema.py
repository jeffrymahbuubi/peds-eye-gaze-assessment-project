"""Structured data records for the eye-gaze assessment.

All records are plain dataclasses so they can be serialised to CSV/JSON without
any GUI dependency. Coordinates are stored in **normalized** screen space
(0.0-1.0, origin top-left) unless a field name explicitly ends in ``_px``.

The ``SCHEMA_VERSION`` constant is written into every ``metadata.json`` so that
downstream loaders can tolerate future schema changes (see risk table in the
project plan, section 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

SCHEMA_VERSION = 1


@dataclass(slots=True)
class GazeSample:
    """One normalized gaze sample.

    Attributes
    ----------
    t_ns:
        Monotonic-ish capture timestamp in nanoseconds (``time.time_ns``).
    x, y:
        Normalized best point-of-gaze, 0-1. May be outside [0, 1] briefly.
    valid:
        Whether the tracker reported this sample as valid (FPOGV/BPOGV).
    fixation_id:
        Fixation identifier (FPOGID); ``None`` if not fixating.
    fix_duration_s:
        Fixation duration so far, seconds (FPOGD).
    pupil_left, pupil_right:
        Pupil diameters if available (v2 analysis); ``None`` otherwise.
    """

    t_ns: int
    x: float
    y: float
    valid: bool
    fixation_id: int | None = None
    fix_duration_s: float | None = None
    pupil_left: float | None = None
    pupil_right: float | None = None

    def as_row(self) -> dict[str, Any]:
        return {
            "t_ns": self.t_ns,
            "x": self.x,
            "y": self.y,
            "valid": int(self.valid),
            "fixation_id": self.fixation_id if self.fixation_id is not None else "",
            "fix_duration_s": self.fix_duration_s if self.fix_duration_s is not None else "",
            "pupil_left": self.pupil_left if self.pupil_left is not None else "",
            "pupil_right": self.pupil_right if self.pupil_right is not None else "",
        }


@dataclass(slots=True)
class TrialRecord:
    """One completed trial (one row of ``trials.csv``)."""

    trial_id: int
    task_id: str
    target_x: float
    target_y: float
    target_radius_px: float
    t_target_shown_ns: int
    t_first_gaze_on_target_ns: int | None = None
    t_click_ns: int | None = None
    t_end_ns: int | None = None
    is_hit: bool = False
    is_timeout: bool = False
    attempts: int = 0
    # First moment this trial's target could actually be selected. Equal to
    # t_target_shown_ns for every task except follow_moving, the only one that
    # overrides BaseTask.is_selectable(); None if the window never opened.
    t_selectable_start_ns: int | None = None
    # The operator skipped this trial (SPEC-compass-task-flow.md 4C.6, R6): a
    # skip is neither a hit nor a timeout, so both stay False and ``t_click_ns``
    # blank; ``t_end_ns`` is when the skip happened.
    is_skipped: bool = False
    # Debounced entries into the target's hitbox (SPEC-compass-task-flow.md 4D.4-1,
    # ``EntryTracker``): 0 when the gaze never reached it. ``time_to_first_
    # fixation_ms`` is the time of the first of them.
    entries: int = 0
    # Where the target was at ``t_end`` (canvas-normalized, 4D.4-2): equals
    # ``target_x/y`` for a static task, the live position for follow_moving,
    # which stores only the start otherwise. None until the trial ends.
    end_x: float | None = None
    end_y: float | None = None
    # Which grid cell / scanning icon the target was (4D.4-3); -1 for a task
    # with no fixed multi-item layout (``TargetSpec.slot_index``).
    slot_index: int = -1

    @property
    def reaction_time_ms(self) -> float | None:
        """Time from the target appearing to the selection.

        Kept unchanged, and comparable across tasks. Note for follow_moving
        specifically: its selection window opens at a random offset, so this
        figure is dominated by that offset rather than by the child --
        :attr:`reaction_time_from_selectable_ms` is the meaningful one there
        (SPEC-follow-moving-selection.md S4.2).
        """
        if self.t_click_ns is None:
            return None
        return (self.t_click_ns - self.t_target_shown_ns) / 1e6

    @property
    def reaction_time_from_selectable_ms(self) -> float | None:
        """Time from the target becoming selectable to the selection.

        For a task with no selection window this equals
        :attr:`reaction_time_ms`. For follow_moving it is the reaction time
        with the random window offset removed. Can be ~0 by design: a child
        already tracking has their held dwell fire the instant the window
        opens (S5.2).
        """
        if self.t_click_ns is None or self.t_selectable_start_ns is None:
            return None
        return (self.t_click_ns - self.t_selectable_start_ns) / 1e6

    @property
    def time_to_first_fixation_ms(self) -> float | None:
        if self.t_first_gaze_on_target_ns is None:
            return None
        return (self.t_first_gaze_on_target_ns - self.t_target_shown_ns) / 1e6

    def as_row(self) -> dict[str, Any]:
        row = {
            "trial_id": self.trial_id,
            "task_id": self.task_id,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_radius_px": self.target_radius_px,
            "t_target_shown_ns": self.t_target_shown_ns,
            "t_first_gaze_on_target_ns": _blank(self.t_first_gaze_on_target_ns),
            "t_click_ns": _blank(self.t_click_ns),
            "t_end_ns": _blank(self.t_end_ns),
            "is_hit": int(self.is_hit),
            "is_timeout": int(self.is_timeout),
            "attempts": self.attempts,
            "t_selectable_start_ns": _blank(self.t_selectable_start_ns),
            "reaction_time_ms": _blank(_round(self.reaction_time_ms)),
            "reaction_time_from_selectable_ms": _blank(
                _round(self.reaction_time_from_selectable_ms)
            ),
            "time_to_first_fixation_ms": _blank(_round(self.time_to_first_fixation_ms)),
            "is_skipped": int(self.is_skipped),
            "entries": self.entries,
            "end_x": _blank(self.end_x),
            "end_y": _blank(self.end_y),
            "slot_index": self.slot_index,
        }
        return row

    @staticmethod
    def csv_header() -> list[str]:
        return [
            "trial_id",
            "task_id",
            "target_x",
            "target_y",
            "target_radius_px",
            "t_target_shown_ns",
            "t_first_gaze_on_target_ns",
            "t_click_ns",
            "t_end_ns",
            "is_hit",
            "is_timeout",
            "attempts",
            "t_selectable_start_ns",
            "reaction_time_ms",
            "reaction_time_from_selectable_ms",
            "time_to_first_fixation_ms",
            "is_skipped",
            "entries",
            "end_x",
            "end_y",
            "slot_index",
        ]


@dataclass(slots=True)
class SessionMetadata:
    """Session-level metadata written to ``metadata.json``."""

    subject_id: str
    session_id: str
    started_ns: int
    schema_version: int = SCHEMA_VERSION
    gazepoint_model: str = "GP3HD"
    input_mode: str = "eye"
    calibration_error_px: float | None = None
    calibration_points: int | None = None
    # "measured" / "loaded" / "not run" (SPEC-result-logic.md S12.2). Additive;
    # older sessions lack it, and ``schema_version`` is deliberately NOT bumped.
    calibration_source: str | None = None
    tasks: list[str] = field(default_factory=list)
    notes: str = ""
    assessment_date: str = ""
    sex: str = ""
    # The settings this run actually used, and where they came from
    # (SPEC-live-settings-panel.md S10.4). Additive, so `schema_version` is
    # deliberately NOT bumped: every existing reader takes named keys and is
    # unaffected, and older sessions simply lack the block.
    settings: dict[str, Any] | None = None
    # Geometry the normalized gaze maps onto (SPEC-gazepoint-analysis-
    # export-parity.md S4.2). ``screen_*_px`` is the tracked monitor Gazepoint
    # Control reports via SCREEN_SIZE -- the only correct scale for any pixel
    # metric derived from the stream; the canvas fields describe where the
    # task scene sat on it (targets are authored normalized-to-canvas). The
    # physical size and viewing distance make degrees of visual angle
    # computable later. All additive; ``schema_version`` deliberately not
    # bumped, same reasoning as ``settings`` above.
    screen_width_px: int | None = None
    screen_height_px: int | None = None
    canvas_width_px: int | None = None
    canvas_height_px: int | None = None
    canvas_offset_x_px: int | None = None
    canvas_offset_y_px: int | None = None
    # "physical" when the canvas fields above are in physical px, the same
    # unit as ``screen_*_px`` (SPEC-display-scaling-cursor-accuracy.md S8.8).
    # None on older sessions, whose canvas fields were Qt logical px (the
    # same numbers at 100 % scale). Additive; ``schema_version`` not bumped.
    canvas_units: str | None = None
    screen_physical_width_mm: float | None = None
    screen_physical_height_mm: float | None = None
    viewing_distance_mm: float | None = None
    # The display the task ran on (SPEC-display-standard-check.md S4.5):
    # physical resolution, Windows scale, whether it is the recommended
    # 1920x1080 at 100 %, and whether the operator acknowledged a
    # non-standard one (None when not launched from the dashboard). Additive;
    # ``schema_version`` deliberately not bumped, same reasoning as above.
    display_width_px: int | None = None
    display_height_px: int | None = None
    display_scale_percent: int | None = None
    display_standard: bool | None = None
    display_nonstandard_acknowledged: bool | None = None
    # ``canvas_*_px`` above is the size at the FIRST TICK only; a later size
    # change is a CANVAS_RESIZED event. (The HUD-hiding fields that used to sit
    # here went with the HUD, SPEC-compass-task-flow.md 4C.7 / HC13; an older
    # session's metadata.json may still carry them, which nothing reads.)
    # Device facts and measured quality (SPEC-gazepoint-analysis-export-
    # parity.md S10.6.3). Rate/bus/serial come from the connect-time device
    # query (placeholders already filtered to None); the refresh rate is the
    # canvas's QScreen; the measured rate and eye distance are filled at
    # session end. All None when unknown (replay, older sessions). Additive;
    # ``schema_version`` deliberately not bumped, same reasoning as above.
    gazepoint_rate_hz: int | None = None
    gazepoint_bus: str | None = None
    gazepoint_serial: str | None = None
    display_refresh_hz: float | None = None
    measured_sample_rate_hz: float | None = None
    measured_eye_distance_mm_median: float | None = None
    # The poll/render loop rate the app actually ran at and where it came from:
    # "config" (explicit app.target_fps), "device" (target_fps auto, live
    # tracker's own rate) or "fallback" (60). SPEC-ui-setup-task-selection.md
    # S25. None on older sessions. Additive; ``schema_version`` not bumped.
    loop_fps: int | None = None
    loop_fps_source: str | None = None
    # The target size preset this run resolved (SPEC-target-size-and-motion-
    # paths.md S4.2): ``{"preset", "diameter_deg", "radius_px", "mm_per_px",
    # "mm_per_px_source", "viewing_distance_mm"}`` (scanning adds
    # ``"radius_of": "icon"``: its radius is the drawn icon's, SPEC S11.3).
    # None when the task config carries no ``target.size`` / ``layout.size``
    # (the explicit ``radius_px`` was used) or on older sessions. Additive;
    # ``schema_version`` deliberately not bumped, same reasoning as the
    # geometry fields above.
    target_size: dict[str, Any] | None = None
    # Grid Click's cell gap preset this run resolved (SPEC-grid-cell-gap.md
    # S4.2): ``{"preset", "gap_deg", "gap_px"}`` -- both None for ``standard``
    # -- plus ``"gap_px_used"`` when the live canvas capped the wanted gap
    # (H4). None when the task has no ``grid.gap`` (every other task, an old
    # config) or on older sessions. Additive; ``schema_version`` deliberately
    # not bumped, same reasoning as the fields above.
    grid_gap: dict[str, Any] | None = None
    # The Test List entry this run belongs to, and the random seed that drew
    # its target order (SPEC-compass-task-flow.md 4A.7, R3). None for a run not
    # started from a test (standalone ``--task X --gui``, older sessions);
    # ``seed`` is then None on older sessions and 0 on a standalone run.
    # Additive; ``schema_version`` deliberately not bumped, same reasoning as
    # the fields above.
    test_id: str | None = None
    test_name: str | None = None
    seed: int | None = None
    # What kind of run wrote this folder (SPEC-compass-task-flow.md 4C.4): only
    # ``"record"`` runs reach disk, so a folder carries it as ``"record"`` (None
    # on older sessions). ``config_name`` is the Test List configuration the run
    # used (R7; also in ``settings``). Additive; ``schema_version`` not bumped.
    run_mode: str | None = None
    config_name: str | None = None
    # How the run ended (4C.9, R1): planned = ``len(task.targets)``; completed =
    # rows written to ``trials.csv`` (skipped ones included); ``outcome`` is
    # ``"completed"`` / ``"ended_early"`` and ``ended_by`` ``"finished"`` /
    # ``"operator_quit"``. There is no ``"discarded"``: a discard deletes the
    # folder. All None on older sessions. Additive; ``schema_version`` not bumped.
    planned_trials: int | None = None
    completed_trials: int | None = None
    skipped_trials: int | None = None
    interrupted_trials: int | None = None
    pause_count: int | None = None
    outcome: str | None = None
    ended_by: str | None = None
    ended_ns: int | None = None
    # Canvas-normalized centres of the task's fixed layout (grid cells, scanning
    # icons) as ``[[x, y], ...]``, so the report can outline the empty slots
    # without re-reading the task config (SPEC 4D.4-4); None for a task with no
    # fixed layout (click_static, follow_moving) and on older sessions.
    layout_slots: list[list[float]] | None = None
    # Host-clock time (ns, ``time.time_ns`` domain) of ``all_gaze.csv`` ``TIME=0``
    # (4D.4-5): the smallest ``host receive time - device TIME`` seen, within ~5 ms
    # of the median. Aligns device-rate rows with trial windows:
    # ``t_ns = raw_clock_offset_ns + TIME * 1e9``. None when no raw file was
    # written and on older sessions. Additive; ``schema_version`` not bumped.
    raw_clock_offset_ns: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _round(value: float | None, ndigits: int = 2) -> float | None:
    return None if value is None else round(value, ndigits)


def _blank(value: Any) -> Any:
    return "" if value is None else value
