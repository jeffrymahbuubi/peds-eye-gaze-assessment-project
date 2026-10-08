"""GUI application wiring (plan section 3.1 + Prompts 3/4).

Builds the QApplication, the gaze source (live Gazepoint or paced replay), the
task, the recorder, and a 60 Hz update loop that ties them together. Kept in its
own module so importing it (and thus PySide6) is opt-in — the headless pipeline
in :mod:`src.engine.task_runner` never touches this file.
"""

from __future__ import annotations

import functools
import sys
import time
from datetime import datetime
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer, QUrl
from PySide6.QtGui import QScreen
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication, QDialog

from .data.analysis_export import (
    ALL_GAZE_FILENAME,
    EYE_GEOMETRY_FILENAME,
    finalize_all_gaze,
    measured_sample_rate_hz,
    median_eye_distance_mm,
)
from .data.exporter import write_session_metrics
from .data.recorder import NullRecorder, SessionRecorder
from .data.schema import SessionMetadata
from .engine.calibration import (
    Calibration,
    CalibrationFileError,
    CalibrationResult,
    calibration_timing_log_path,
    load_calibration_result,
    save_calibration_result,
)
from .engine.clock import now_ns
from .engine.display_check import check_display
from .engine.config import CONFIG_ROOT, deep_merge, load_task_config, load_theme
from .engine.gaze_diagnostics import GazeDropoutLog, gaze_dropout_log_path
from .engine.feedback import FeedbackBus
from .engine.input_choice import (
    POINTER_GAZE,
    POINTER_MOUSE,
    TASKS_WITHOUT_SELECTION,
    glow_active,
    resolve_input,
)
from .engine.latency import LatencyTracker
from .engine.loop_rate import config_target_fps, resolve_target_fps, target_fps_is_invalid
from .engine.run_mode import (
    ENDED_QUIT,
    PRACTICE,
    PREVIEW,
    apply_outcome,
    is_recorded,
    preroll_ms,
    run_seed,
    validate_run_mode,
)
from .engine.run_paths import make_session_id, new_run_dir
from .engine.run_result import RunResult, run_result_from_task
from .engine.session_files import remove_orphan_run_dir
from .engine.subject_store import output_root as resolve_output_root
from .engine.subject_store import same_subject
from .engine.target_size import (
    DEFAULT_SIZE,
    apply_grid_gap,
    apply_target_size,
    grid_gap_log_line,
    screen_scale,
    size_block,
    target_size_log_line,
    viewing_distance_mm,
)
from .engine.task_runner import build_task
from .engine.tracking_status import run_status, tracking_status
from .inputs.base import Pointer
from .inputs.eye_input import DwellConfig, EyeInput, SmoothingConfig
from .inputs.gazepoint_client import GazepointClient
from .inputs.mouse_gaze import MouseGazeSource
from .inputs.no_tracker import NoTracker
from .inputs.switch_input import SwitchInput
from .tasks.base_task import (
    Phase,
    canvas_geometry_physical,
    gaze_geometry_from_screen,
    screen_size_mismatch,
)
from .ui.main_window import MainWindow, TaskRunView
from .ui.run_cursor import RunCursor
from .ui.run_dialogs import confirm_quit
from .ui.settings_registry import apply_live_values_to_config, get_nested, initial_live_values
from .ui.settings_snapshot import run_settings
from .ui.task_settings_dialog import TaskSettingsDialog


def _canvas_physical(canvas) -> tuple[int, int, int, int, float | None]:
    """``(width, height, offset_x, offset_y, dpr)`` of the canvas in physical
    px, the offset relative to its own QScreen's origin (SPEC-display-scaling-
    cursor-accuracy.md S8.8). With no QScreen (cannot happen for a shown
    canvas) returns the raw logical values and ``dpr`` None."""
    origin = canvas.mapToGlobal(QPoint(0, 0))
    screen = canvas.screen()
    if screen is None:
        return int(canvas.width()), int(canvas.height()), int(origin.x()), int(origin.y()), None
    top_left = screen.geometry().topLeft()
    dpr = float(screen.devicePixelRatio())
    w, h, off_x, off_y = canvas_geometry_physical(
        top_left.x(), top_left.y(), origin.x(), origin.y(), canvas.width(), canvas.height(), dpr
    )
    return w, h, off_x, off_y, dpr


class GuiFeedback(FeedbackBus):
    """Feedback that drives on-canvas particles and short hit/miss sound cues.

    Sound loading is best-effort: a missing asset or a task/theme with no
    `sounds` block just means silence, never a crash (matches the tolerant
    style used elsewhere on this startup path, e.g. Calibration's stub mode).
    """

    # Deliberately below full volume: these cues need to never add to
    # sensory overstimulation for a child with sensory sensitivity, which
    # weighed into how the sound assets themselves were designed/generated
    # (SPEC-2026-09-02.md item 4 — short, soft, non-startling cues).
    _VOLUME = 0.6

    def __init__(self, canvas, theme: dict | None = None, feedback_cfg: dict | None = None) -> None:
        self.canvas = canvas
        theme = theme or {}
        feedback_cfg = feedback_cfg or {}
        self._hit_sound = (
            self._load_sound(theme, "hit") if feedback_cfg.get("hit_sound", True) else None
        )
        self._miss_sound = (
            self._load_sound(theme, "miss") if feedback_cfg.get("miss_sound", True) else None
        )

    @staticmethod
    def _load_sound(theme: dict, key: str) -> QSoundEffect | None:
        rel_path = theme.get("sounds", {}).get(key)
        if not rel_path:
            return None
        path = CONFIG_ROOT / rel_path
        if not path.exists():
            return None
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(GuiFeedback._VOLUME)
        return effect

    def on_target_shown(self, x: float, y: float) -> None:
        pass

    def on_hit(self, x: float, y: float) -> None:
        self.canvas.burst(x, y)
        if self._hit_sound is not None:
            self._hit_sound.play()

    def on_miss(self, x: float, y: float) -> None:
        if self._miss_sound is not None:
            self._miss_sound.play()

    def on_progress(self, x: float, y: float, progress: float) -> None:
        pass


def resolve_calibration_source(
    *,
    calibration_file: str | None,
    preset_present: bool,
    preset_source: str | None,
    preset_file: str | None,
    ran_fresh: bool,
    is_stub: bool = False,
) -> tuple[str, str | None]:
    """Where a run's calibration came from: ``(source, file)``.

    ``source`` is ``"measured"``, ``"loaded"`` or ``"not run"``
    (SPEC-result-logic.md S12.2). A ``--calibration-file`` always wins; a
    preset with no stated source (any caller but the dashboard) counts as
    loaded; a fresh run is measured unless it was the stub.
    """
    if calibration_file is not None:
        return "loaded", calibration_file
    if preset_present:
        return (preset_source or "loaded"), preset_file
    if ran_fresh and is_stub:
        return "not run", None
    return "measured", None


def calibration_log_line(cal: CalibrationResult, source: str, file: str | None) -> str:
    """The Session Log's calibration line (SPEC-result-logic.md S12.2)."""
    if source == "loaded":
        label = f"loaded from {Path(file).name}" if file else "loaded"
    else:
        label = source
    if cal.valid:
        error_txt = f"{cal.mean_error_px:.1f}px" if cal.mean_error_px is not None else "n/a"
        line = f"Calibration {label} — {cal.n_points} points, mean error {error_txt}, valid."
        # Measured or loaded: an older/lossy record may lack the breakdown too.
        return line if cal.per_point else line + " Per-point details not available."
    return f"Calibration {label} — {cal.n_points} points, invalid or unmeasured."


def _removing_an_orphan_run_folder(init):
    """Wrap ``AssessmentApp.__init__`` (SPEC-audit-fixes.md H11): a start that fails after
    the run's folder was made, and before anything but its ``calibration.json`` was written
    into it, removes the folder again. A folder with anything else in it is left alone."""

    @functools.wraps(init)
    def wrapper(self, *args, **kwargs):
        try:
            init(self, *args, **kwargs)
        except BaseException:
            remove_orphan_run_dir(getattr(self, "_run_dir", None), getattr(self, "_output_root", ""))
            raise

    return wrapper


class AssessmentApp:
    @_removing_an_orphan_run_folder
    def __init__(
        self,
        task_id: str,
        replay_path: str | None,
        subject_id: str,
        calibration_file: str | None = None,
        structural_overrides: dict | None = None,
        live_overrides: dict | None = None,
        client: GazepointClient | None = None,
        preset_calibration_result: CalibrationResult | None = None,
        embedded: bool = False,
        on_finished: Callable[[RunResult], None] | None = None,
        assessment_date: str = "",
        sex: str = "",
        notes: str = "",
        display_acknowledged: bool | None = None,
        preset_calibration_source: str | None = None,
        preset_calibration_file: str | None = None,
        screen: QScreen | None = None,
        test_id: str | None = None,
        test_name: str | None = None,
        seed: int = 0,
        run_mode: str = "record",
        practice_index: int = 0,
        config_name: str | None = None,
        pointer_source: MouseGazeSource | None = None,
        preview_pointer: str | None = None,
    ) -> None:
        """Build one task run.

        ``client``/``preset_calibration_result`` let a caller that already
        owns a connected :class:`GazepointClient` and a completed
        calibration (the Setup tab's dashboard, SPEC-ui-setup-task-
        selection.md S3.1.7) hand both in directly instead of this class
        connecting/calibrating again on every task run -- "nothing gets
        relaunched" was the explicit design decision. ``embedded`` builds a
        plain :class:`~src.ui.main_window.TaskRunView` (for the dashboard's
        ``QStackedWidget``) instead of a fullscreen
        :class:`~src.ui.main_window.MainWindow`, and routes end-of-task to
        ``on_finished(RunResult)`` instead of quitting the whole application. All four
        default to the exact standalone-launch behavior this class always
        had (own client, own calibration, own top-level window, quit on
        end) when omitted, so ``python -m src.main --task X --gui`` is
        unaffected.

        ``screen`` is the monitor the run will be shown on, used to resolve a
        target size preset into px (SPEC-target-size-and-motion-paths.md S4.2).
        The dashboard passes its own window's screen: the embedded canvas is
        not yet in any window when this runs, so its own ``screen()`` would
        only be a default. Omitted, the canvas's own screen is used.

        ``test_id``/``test_name`` link the run to its Test List entry and are
        written to ``metadata.json`` (SPEC-compass-task-flow.md 4A.7);
        ``seed`` is the target-order seed (R3: the test's own seed), written
        there too. All three default to the standalone behaviour: no test, and
        seed 0, the order every run had before tests existed.

        ``run_mode`` (SPEC-compass-task-flow.md 4C.4, :mod:`src.engine.run_mode`)
        is ``"record"`` (default), ``"practice"`` or ``"preview"``. The last two
        write nothing (a :class:`NullRecorder`: no folder, calibration file or
        diagnostics), have no pre-roll, and ignore ``seed``: ``practice_index``
        picks a practice's own seed. ``config_name`` is recorded in the metadata.

        There is no operator HUD (4C.5, U5): the run view is the canvas and a
        :class:`~src.ui.run_bar.RunBar` (Pause, Skip trial, Quit, one status
        line). Every setting is fixed before the run starts; nothing changes
        during it, so ``metadata.settings`` is the complete configuration.
        Quit, Alt-Q and Esc ask first in a recorded run (``confirm_quit``,
        replaceable by a test), then ``_shutdown`` hands ``on_finished`` a
        :class:`~src.engine.run_result.RunResult`; a practice or preview quits
        at once.

        The test's **Pointer** (``input.pointer``: gaze or mouse) and **Selection**
        (``input.selection``: dwell or switch) come from the merged config
        (:func:`~src.engine.input_choice.resolve_input`; SPEC-input-selection-and-
        follow.md). A Mouse run takes its pointer from a
        :class:`~src.inputs.mouse_gaze.MouseGazeSource` bound to the canvas
        (``pointer_source`` replaces it, for a test) and writes ``pointer_stream.csv``;
        ``client`` is then only the tracker that records *alongside* (the Setup tab's,
        when connected and calibrated). With no ``client`` there is no tracker: a
        :class:`~src.inputs.no_tracker.NoTracker` stands in, nothing is calibrated and
        no gaze file is written. A Mouse pointer is never smoothed (SPEC-preview-gaze-
        pointer.md H6): ``dwell.smoothing.*`` stays in ``metadata.settings`` as configured.

        A Preview's pointer is its caller's decision (``preview_pointer``, H1, H3; ignored
        by every other run mode). ``"gaze"``: the tracker is the pointer, and ``client``
        and ``preset_calibration_result`` must be the Setup tab's connected, calibrated
        ones: a Preview never dials the device or calibrates, and records nothing.
        ``"mouse"`` (and ``None``): the pointer is the mouse, and ``client`` is the
        :class:`~src.inputs.mouse_gaze.MouseGazeSource` the caller binds to the canvas; for
        a Gaze test (the tracker was not ready) the gaze settings, smoothing included,
        still apply to it.
        """
        self.run_mode = validate_run_mode(run_mode)
        if preview_pointer not in (None, POINTER_GAZE, POINTER_MOUSE):
            raise ValueError(f"Unknown preview pointer {preview_pointer!r}; expected 'gaze' or 'mouse'.")
        recorded = is_recorded(self.run_mode)
        seed = run_seed(self.run_mode, seed, practice_index)
        self.config = load_task_config(task_id)
        self.task_id = task_id
        if structural_overrides:
            # Pre-launch-only structural params (grid size, radius, trial
            # count, ...) collected via TaskSettingsDialog -- SPEC-live-
            # settings-panel.md section 5.3. Reuses the exact merge a task
            # YAML's own `overrides:` block already goes through.
            self.config["task"] = deep_merge(self.config["task"], structural_overrides)
        if live_overrides:
            # The test's own live values (or, standalone, a saved profile's).
            # Applied to the *config* rather than only to self._live_values so
            # that build_task() and the engine objects all read the same thing
            # -- self._live_values is derived from the config a few lines down,
            # so they cannot disagree.
            apply_live_values_to_config(self.config, live_overrides)
        theme_name = self.config.get("task", {}).get("theme") or self.config.get("theme", {}).get("name", "forest")
        self.theme = load_theme(theme_name)
        # What moves the pointer and how a target is selected (SPEC-input-selection-and-
        # follow.md H1); ``input_mode`` is derived from the two. A Preview's pointer is its
        # caller's decision (SPEC-preview-gaze-pointer.md H1, H3): the tracker's gaze only
        # when told so, else the mouse -- whatever the test says, so a Gaze test whose
        # tracker was not ready previews on the mouse, and a Mouse test's smoothing (below)
        # follows the test's own pointer, not this one.
        self.input_choice = resolve_input(self.config)
        self.input_mode = self.input_choice.mode
        self._is_switch = self.input_choice.is_switch
        if self.run_mode == PREVIEW:
            self._pointer_is_mouse = preview_pointer != POINTER_GAZE
        else:
            self._pointer_is_mouse = self.input_choice.is_mouse

        # A recorded run's folder is ``<output root>/<subject folder>/runs/<task_id>/
        # <YYYY-MM-DD_HHMM>`` (SPEC-subject-data-layout.md H1, H2), made by
        # ``new_run_dir`` with an atomic mkdir, so a same-minute re-run gets its own
        # folder (``_2``) and never overwrites a prior run. ``run_dir()`` makes it at
        # the first thing that needs it -- an auto-saved calibration.json (which is
        # written before the recorder exists), else the recorder. A run that fails to
        # start before its recorder opens has the folder removed again (``__init__`` is
        # wrapped by ``_removing_an_orphan_run_folder``). A practice or preview run has
        # no folder: its "session id" is a sentinel and ``run_dir`` is never called.
        output_root = resolve_output_root(self.config)
        self._output_root = output_root
        self._run_dir: Path | None = None

        def run_dir() -> Path:
            if self._run_dir is None:
                self._run_dir = new_run_dir(output_root, subject_id, task_id)
            return self._run_dir

        # A --calibration-file is loaded and subject-checked before touching
        # the device at all, so a bad path or subject mismatch fails fast
        # without opening a socket or showing any calibration UI
        # (SPEC-2026-09-02.md item 7, Goal 1).
        preset_calibration = preset_calibration_result
        if calibration_file is not None:
            saved = load_calibration_result(calibration_file)
            if not same_subject(saved.subject_id, subject_id):
                raise CalibrationFileError(
                    f"Calibration file subject_id {saved.subject_id!r} does not match "
                    f"--subject {subject_id!r} ({calibration_file})"
                )
            if not saved.result.valid:
                # A timed-out calibration is a record, not a calibration (SPEC-audit-fixes.md H7).
                raise CalibrationFileError(
                    f"Calibration file is marked not valid; run a fresh calibration instead "
                    f"({calibration_file})"
                )
            preset_calibration = saved.result

        if self.run_mode == PREVIEW and not self._pointer_is_mouse and (
            client is None or preset_calibration is None
        ):
            # H2: a gaze Preview must never dial the device or start a calibration.
            raise ValueError(
                "A gaze Preview needs the Setup tab's tracker and its calibration; "
                "it never connects or calibrates."
            )

        gp_cfg = self.config.get("gazepoint", {})
        # An externally-provided client is already connected (and possibly
        # already streaming, from a prior task run in the same dashboard
        # session) -- connect()/start_streaming() must not be called again
        # on it: connect() unconditionally reopens the socket and re-sends
        # every ENABLE_SEND_* command, which would be wasteful at best and
        # disruptive to an in-progress stream at worst. This class never
        # owns (and must never .stop()) a client it didn't create itself.
        mouse_only = client is None and self._pointer_is_mouse and replay_path is None
        self._owns_client = client is None and not mouse_only
        if client is not None:
            self.client = client
        elif mouse_only:
            # A Mouse run with no tracker (H5): nothing to connect to or calibrate.
            self.client = NoTracker()
        else:
            # `enable` here is the gazepoint.enable.* block (default.yaml keys:
            # time/pog_fix/pog_best/pupil_left/pupil_right/cursor) -- wiring it
            # through lets a therapist disable a data field via YAML instead of
            # it silently doing nothing (GazepointClient defaults to all-True
            # when enable=None). The dashboard's Connect (setup_page._ConnectThread)
            # passes the same block from default.yaml to the client it hands in.
            self.client = GazepointClient(replay_path=replay_path, enable=gp_cfg.get("enable"))
            self.client.connect(host=gp_cfg.get("host", "127.0.0.1"), port=int(gp_cfg.get("port", 4242)))

        # Calibration must run before start_streaming(): it reads the socket
        # directly to poll CALIBRATE_RESULT_SUMMARY, and once the background
        # reader thread is consuming the same socket it will race for (and
        # can silently swallow) that response. A preset result (whether from
        # --calibration-file or handed in directly by the dashboard) skips
        # this device interaction entirely -- there's nothing to poll for.
        cal_cfg = self.config.get("calibration", {})
        fresh_is_stub = False
        # Whether a tracker records into this run (H4): any gaze run, and a Mouse run
        # that was given one. A Preview records nothing at all.
        self._gaze_recorded = self.run_mode != PREVIEW and not isinstance(self.client, NoTracker)
        if preset_calibration is None and self._pointer_is_mouse:
            # A Mouse run needs no calibration (H5): without the tracker's there is
            # nothing to measure, and a fresh one is never started for it.
            cal = CalibrationResult(n_points=0, mean_error_px=None, valid=False)
            fresh_is_stub = True
        elif preset_calibration is not None:
            cal = preset_calibration
            # Recorded into THIS run's own session dir too, even though it
            # wasn't measured this run -- every session directory carries its
            # own self-contained calibration record, matching the fresh-
            # calibration branch below, and lets --calibration-file work
            # against any individual run's folder later. (Not for a practice or
            # preview, which has no folder.)
            if recorded:
                save_calibration_result(run_dir() / "calibration.json", subject_id, cal)
        else:
            calibration = Calibration(
                self.client,
                n_points=int(cal_cfg.get("points", 5)),
                enabled=bool(cal_cfg.get("enabled", True)),
                show=bool(cal_cfg.get("show", True)),
                point_timeout_s=cal_cfg.get("timeout_s"),
                point_delay_s=cal_cfg.get("delay_s"),
                timing_log_path=calibration_timing_log_path(output_root) if recorded else None,
            )
            cal = calibration.run()
            fresh_is_stub = calibration.is_stub
            if recorded and not calibration.is_stub and cal.valid:
                # A real calibration just ran (not the no-hardware/disabled
                # stub) -- auto-save it so a later launch can reuse it via
                # --calibration-file. No separate save flag, per the user's
                # 2026-09-04 design decision. A timed-out (invalid) one is not
                # saved: it would only be refused when loaded (SPEC-audit-fixes.md H7).
                save_calibration_result(run_dir() / "calibration.json", subject_id, cal)

        self.client.start_streaming()  # idempotent (GazepointClient no-ops if already streaming)

        # Single source of truth for every live-setting field's value
        # (SPEC-live-settings-panel.md section 5.1) -- used to initialize the
        # live objects below and recorded in ``metadata.settings``. Nothing
        # changes it during the run (no HUD, 4C.7).
        self._live_values = initial_live_values(self.config)
        lv = self._live_values

        # What moves the pointer: the tracker's gaze, or the mouse over the canvas (a
        # Preview's ``client`` already is the pointer, bound by its caller: the mouse source
        # or the Setup tab's tracker).
        if self._pointer_is_mouse and self.run_mode != PREVIEW:
            self.pointer_source = pointer_source or MouseGazeSource()
        else:
            self.pointer_source = self.client
        # Gaze smoothing is for gaze: off whenever the *test's* pointer is the mouse, in every
        # run mode (P2, H6). A Gaze test previewed on the mouse fallback keeps it on (H1), so
        # this reads the test's pointer, not ``_pointer_is_mouse``.
        smoothing_on = bool(lv["dwell.smoothing.enabled"]) and not self.input_choice.is_mouse
        self.eye = EyeInput(
            self.pointer_source,
            DwellConfig(
                threshold_ms=float(lv["dwell.threshold_ms"]),
                refractory_ms=float(lv["dwell.refractory_ms"]),
            ),
            SmoothingConfig(enabled=smoothing_on, alpha=float(lv["dwell.smoothing.alpha"])),
        )
        self.switch = SwitchInput()

        self._embedded = embedded
        self._on_finished = on_finished
        if embedded:
            # No top-level window at all -- the caller (DashboardWindow)
            # inserts .view into its own QStackedWidget page.
            self.window = None
            self.view = TaskRunView(theme=self.theme, run_mode=self.run_mode)
        else:
            self.window = MainWindow(
                theme=self.theme,
                fullscreen=bool(self.config.get("app", {}).get("fullscreen", True)),
                run_mode=self.run_mode,
            )
            self.window.close_guard = self._may_close_window
            self.view = self.window.view
        self.canvas = self.view.canvas
        if self.pointer_source is not self.client and hasattr(self.pointer_source, "bind_canvas"):
            self.pointer_source.bind_canvas(self.canvas)
        self.canvas.show_cursor = bool(lv["dwell.visual_cursor"])
        # A switch run has no dwell ring (A4): its place is taken by the glow. Follow the
        # Target has nothing to dwell on at all: no ring and no instant ring, just the glow.
        has_dwell_ui = task_id not in TASKS_WITHOUT_SELECTION
        self.canvas.show_progress_ring = (
            bool(lv["dwell.progress_ring"]) and not self._is_switch and has_dwell_ui
        )
        self.canvas.show_instant_feedback = bool(lv["dwell.instant_feedback"]) and has_dwell_ui
        glow_on = get_nested(self.config.get("task", {}), "feedback.target_glow", True)
        self.canvas.show_glow = glow_active(
            task_id, self.input_choice.selection, glow_on if isinstance(glow_on, bool) else True
        )
        # The switch: a left press on the canvas, and Space / Enter (H2); only when the
        # test's Selection is Switch (4.2). A dwell run ignores both.
        self.canvas.switch_press_enabled = self._is_switch
        self.canvas.switchPressed.connect(self.switch.press)
        self.canvas.switchReleased.connect(self.switch.release)
        # Pointer = Gaze + Switch: the OS cursor is parked on the canvas and hidden (I6).
        self.run_cursor = RunCursor(self.canvas)
        self._hide_cursor = self._is_switch and not self._pointer_is_mouse
        self._cursor_pending = self._hide_cursor

        # H3: ``<task_id>_<YYYY-MM-DD_HHMM>_<test_id>`` -- no subject in it.
        session_id = make_session_id(task_id, run_dir(), test_id) if recorded else self.run_mode
        self.metadata = SessionMetadata(
            subject_id=subject_id,
            session_id=session_id,
            started_ns=time.time_ns(),
            input_mode=self.input_mode,
            input_pointer=self.input_choice.pointer,
            input_selection=self.input_choice.selection,
            gaze_recorded=self._gaze_recorded,
            # What "on target" meant: the radius plus this (Follow has no control for it).
            hitbox_margin_px=float(lv["dwell.jitter_tolerance_px"]),
            tasks=[task_id],
            assessment_date=assessment_date,
            sex=sex,
            notes=notes,
            display_nonstandard_acknowledged=display_acknowledged,
            test_id=test_id,
            test_name=test_name,
            seed=int(seed),
            run_mode=self.run_mode,
            config_name=config_name,
            # Provenance (SPEC-live-settings-panel.md S10.4). The settings
            # actually in effect are recorded with the data, or two runs of the
            # same task on the same child can differ with nothing to say how.
            # Nothing changes them during a run (the HUD's sliders are gone,
            # 4C.7), so ``run_settings`` of the **final** merged config (the
            # task YAML, the test's structural and live values laid over it) is
            # the complete configuration of the run (R7): the report's
            # Test Configuration table reads it.
            settings=run_settings(task_id, self.config, config_name),
        )
        self.recorder = (
            SessionRecorder(self.metadata, session_dir=run_dir())
            if recorded
            else NullRecorder(self.metadata)
        )
        # No tracker, no gaze files (H4): a Mouse run without one has only the pointer.
        self.recorder.open(gaze_stream=self._gaze_recorded)
        if self._pointer_is_mouse:
            self.recorder.open_pointer_stream()
        recording_cfg = self.config.get("recording", {})
        self._save_all_gaze = self._gaze_recorded and bool(recording_cfg.get("save_all_gaze", True))
        self._save_eye_geometry = self._gaze_recorded and bool(
            recording_cfg.get("save_eye_geometry", True)
        )
        if self._save_all_gaze or self._save_eye_geometry:
            # Raw records queued since Connect / Setup / calibration are not
            # part of this run: start both raw files, and their TIME origin,
            # at the run's first record (SPEC S10.6.9).
            self.client.clear_raw()
        if self._save_all_gaze:
            # Gazepoint Analysis export layout (SPEC-gazepoint-analysis-
            # export-parity.md S5): the task id stands in for Analysis's
            # media name; the tick frequency was read at connect.
            info = self.client.device_info
            self.recorder.open_all_gaze(
                media_name=task_id,
                tick_frequency=info.tick_frequency if info is not None else None,
            )
        # Device-rate 3D eye position + per-eye POG (SPEC-gazepoint-analysis-
        # export-parity.md S10.6.2); on unless explicitly disabled.
        if self._save_eye_geometry:
            self.recorder.open_eye_geometry()
        # Filled once the canvas has its real on-screen size (see
        # _record_geometry); not at construction, when a widget still
        # reports 0x0 or its pre-layout default.
        self._geometry_recorded = False
        # Last canvas size seen by _tick (None until the first tick sets the
        # baseline); a change after that is a CANVAS_RESIZED event.
        self._last_canvas_size: tuple[int, int] | None = None

        # Human-readable session narrative (SPEC-result-logic.md §8.3's
        # Session Log panel) -- connect()/calibrate() above both had to run
        # before the recorder existed (calibration polls the socket directly
        # and must not race the client's own reader thread against a log
        # write), so their lines are recorded here, right after open(), not
        # at the point each thing actually happened.
        self.recorder.log(f"Session started: {session_id}")
        if self._owns_client:
            self.recorder.log("Connected to Gazepoint Control.")
        cal_source, cal_file = resolve_calibration_source(
            calibration_file=calibration_file,
            preset_present=preset_calibration is not None,
            preset_source=preset_calibration_source,
            preset_file=preset_calibration_file,
            ran_fresh=preset_calibration is None,
            is_stub=fresh_is_stub,
        )
        self.recorder.log(calibration_log_line(cal, cal_source, cal_file))
        self.recorder.log(self._input_log_line())
        if self.input_choice.is_mouse:
            self.recorder.log("Gaze smoothing: off (mouse pointer).")  # H6; metadata keeps the setting

        self.metadata.calibration_source = cal_source
        self.metadata.calibration_points = cal.n_points
        self.metadata.calibration_error_px = cal.mean_error_px

        # Loop rate (SPEC-ui-setup-task-selection.md S25): resolved once, here,
        # because device_info is known by now (the dashboard connects at Setup;
        # the standalone path connected above). Drives the QTimer and the
        # latency window below.
        target_fps_cfg = config_target_fps(self.config)
        dev_info = self.client.device_info
        self._loop_fps, loop_fps_source = resolve_target_fps(
            target_fps_cfg,
            dev_info.rate_hz if dev_info is not None else None,
            self.client.is_live,
        )
        if target_fps_is_invalid(target_fps_cfg):
            self.recorder.log(
                f"WARNING: app.target_fps={target_fps_cfg!r} is not 'auto' or a "
                f"positive number; using {self._loop_fps} Hz."
            )
        self.metadata.loop_fps = self._loop_fps
        self.metadata.loop_fps_source = loop_fps_source
        source_text = {"config": "from config", "device": "from device"}.get(
            loop_fps_source, "fallback"
        )
        self.recorder.log(f"Loop rate: {self._loop_fps} Hz ({source_text}).")

        self.feedback = GuiFeedback(
            self.canvas, self.theme, self.config.get("task", {}).get("feedback", {})
        )
        # Before build_task: tasks read the resolved ``radius_px`` (``target``'s,
        # or ``layout``'s for scanning).
        self._resolve_target_size(screen)
        self.task = build_task(
            task_id,
            self.config,
            recorder=self.recorder,
            feedback=self.feedback,
            seed=int(seed),
            preroll_ms=preroll_ms(self.run_mode),
        )
        app_cfg = self.config.get("app", {})
        self.recorder.log(
            f"Running {task_id} ({len(self.task.targets)} trials) at "
            f"{int(app_cfg.get('screen_width_px', 1920))}x{int(app_cfg.get('screen_height_px', 1080))}."
        )
        if recorded:
            self.recorder.log(f"Pre-roll: {preroll_ms(self.run_mode)} ms blank before trial 1.")
        # The task's fixed slots (grid cells, scanning icons), canvas-normalized,
        # for the report's map outlines (SPEC-compass-task-flow.md 4D.4-4).
        slots = self.task.layout_slots
        self.metadata.layout_slots = [[round(x, 5), round(y, 5)] for x, y in slots] if slots else None
        # The task's persistent on-screen layout description (ported from
        # resources/diki, see SPEC-diki-design-audit.md S3.1). Default
        # {"mode": "single"} for tasks not yet ported to a dedicated scene.
        # Re-read every tick (see _tick): click_grid's cell inset follows the
        # live canvas size (SPEC-grid-cell-gap.md S4.3).
        self._scene = self.task.scene_spec()

        # Pause state. A pause that interrupts a trial in flight leaves the task one
        # trial behind (it is re-presented on resume), which ``_display_trial_number``
        # corrects for the bar. ``_last_valid_ns`` is the last valid gaze frame, for
        # the bar's tracking state.
        self._paused = False
        self._pause_interrupted = False
        self._quit_pending = False
        self._shutdown_done = False
        self._last_valid_ns: int | None = None
        # Stamp of the last tracker sample written to the gaze files (F3, SPEC-audit-fixes.md H6).
        self._last_gaze_t_ns: int | None = None
        # The quit question; replaceable (a test answers without a modal loop).
        self.confirm_quit: Callable[[object, int, int], bool] = confirm_quit
        self._wire_bar()
        self._install_key_handler()

        # Gaze-to-feedback latency (plan risk table / gap F): only meaningful
        # against a live tracker, never a replay fixture (see
        # GazepointClient.is_live) -- and never for a mouse pointer.
        self._latency = LatencyTracker(window_size=self._loop_fps)

        # Dropout / off-canvas diagnostic (SPEC-gaze-cursor-redesign.md S6).
        # Live device only: a replay fixture's dropouts are the fixture's, not
        # the tracker's, and would pollute the aggregate the fade threshold is
        # meant to be read from. Recorded runs only: a practice leaves no trace.
        self._dropout_log = (
            GazeDropoutLog(
                gaze_dropout_log_path(output_root),
                raw_probe=getattr(self.client, "last_raw_pog", None),
                task_id=task_id,
            )
            if recorded and self.client.is_live and not self._pointer_is_mouse
            else None
        )

        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000 / self._loop_fps))

    # -- wiring ------------------------------------------------------------

    def _input_log_line(self) -> str:
        """The Session Log's line for the test's input (SPEC-input-selection-and-
        follow.md): pointer, selection, and whether gaze is recorded."""
        choice = self.input_choice
        text = (
            f"Input: pointer {'mouse' if self._pointer_is_mouse else 'gaze'}, "
            f"selection {choice.selection or 'none'}."
        )
        if not self._pointer_is_mouse or self.run_mode == PREVIEW:
            return text
        if self._gaze_recorded:
            return text + " Gaze is recorded alongside the mouse."
        return text + " No tracker: no gaze is recorded."

    def _wire_bar(self) -> None:
        bar = self.view.run_bar
        bar.pause_toggled.connect(self._set_paused)
        bar.skip_requested.connect(self._skip_trial)
        bar.quit_requested.connect(self._request_quit)

    def _resolve_target_size(self, screen: QScreen | None = None) -> None:
        """Turn the task config's ``target.size`` preset (``layout.size`` for
        scanning, SPEC-target-size-and-motion-paths.md S11.3) into ``radius_px``
        (S4.2), from the canvas's own screen, and record what was resolved.

        With no ``size`` key (an old YAML or profile) nothing happens and the
        explicit ``radius_px`` is used unchanged; with both, ``size`` wins.
        The resolved radius is in Qt logical px -- the unit the canvas draws
        and hit-tests in -- so the apparent size is right at any Windows scale.

        ``screen`` is the monitor the run will be shown on, when the caller
        knows it (the dashboard passes its window's screen); without one the
        canvas's own ``screen()`` is used. An embedded canvas is not yet in any
        window when this runs, so only the former is trustworthy on a
        multi-monitor setup.
        """
        task_cfg = self.config.get("task", {})
        if screen is None:
            screen = self.canvas.screen()
        scale = screen_scale(screen, self.config.get("app", {}))
        distance = viewing_distance_mm(self.config.get("app", {}))
        block = size_block(task_cfg)
        requested = (task_cfg.get(block) or {}).get("size")
        info = apply_target_size(task_cfg, scale, distance, block=block)
        if info is not None:
            self.metadata.target_size = info
            if str(requested).strip().lower() != info["preset"]:
                what = "icon size" if block == "layout" else "target size"
                self.recorder.log(f"Unknown {what} {requested!r}; using {DEFAULT_SIZE!r}.")
            self.recorder.log(target_size_log_line(info, scale))
        # Grid Click's cell gap (SPEC-grid-cell-gap.md S4.2), resolved against
        # the very same scale. No ``grid.gap`` (every other task, an old config
        # or profile) leaves everything alone: the standard board.
        gap_info = apply_grid_gap(task_cfg, scale, distance)
        if gap_info is not None:
            self.metadata.grid_gap = gap_info
            self.recorder.log(grid_gap_log_line(gap_info))

    def _install_key_handler(self) -> None:
        original = self.canvas.keyPressEvent
        original_release = self.canvas.keyReleaseEvent
        switch_keys = (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter)

        def handler(event):
            if event.key() in switch_keys:
                # Space / Enter are the switch too (H2) -- for a keyboard-type switch
                # interface -- on button down, once per press (a held key repeats, and
                # its auto-repeat is not a press). Under Dwell they do nothing.
                if self._is_switch and not event.isAutoRepeat():
                    self.switch.press()
            elif event.key() == Qt.Key.Key_Escape:
                # Esc is Quit, with the same question as the button (HC10): a
                # child at the keyboard must not end a recorded run.
                self._request_quit()
            else:
                original(event)

        def release_handler(event):
            if event.key() in switch_keys:
                if not event.isAutoRepeat():
                    self.switch.release()
            else:
                original_release(event)

        self.canvas.keyPressEvent = handler
        self.canvas.keyReleaseEvent = release_handler
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.canvas.setFocus()

    # -- operator actions --------------------------------------------------

    def _set_paused(self, paused: bool) -> None:
        """Pause or resume (SPEC-compass-task-flow.md 4C.6). The task stops its
        clocks and drops a trial in flight, to re-present it on resume; the tick
        keeps draining the raw queue but records nothing."""
        paused = bool(paused)
        if paused == self._paused:
            return
        t_ns = now_ns()
        self._paused = paused
        # A press made across a pause is never a selection (I5d): drop a waiting one,
        # and a held one, either way round.
        self.switch.reset()
        if paused:
            self._pause_interrupted = self.task.pause(t_ns)
            # The operator needs the cursor for the bar (I6).
            self.run_cursor.show()
        else:
            self.task.resume(t_ns)
            self._pause_interrupted = False
            # The operator's last click left it on the bar, where the child's next press
            # would land: hidden and parked on the canvas again (the next tick parks it).
            self._cursor_pending = self._hide_cursor
        self.canvas.set_paused(paused)
        self.view.run_bar.set_paused(paused)
        self._update_run_bar(t_ns)

    def _skip_trial(self) -> None:
        # Recorded as skipped, not as a timeout (SPEC-compass-task-flow.md 4C.6);
        # does nothing unless a trial is running (and never while paused).
        self.task.skip_trial(now_ns())

    @property
    def is_finished(self) -> bool:
        """Whether the run has ended and its files are written (``_shutdown`` ran)."""
        return self._shutdown_done

    def request_quit(self) -> None:
        """What a window close asks for (SPEC-audit-fixes.md H4): the same as Quit."""
        self._request_quit()

    def _may_close_window(self) -> bool:
        """The standalone window's close guard: true once the run is over; before that the
        X button asks the quit question like Alt-Q, and quitting ends the application."""
        if self._shutdown_done:
            return True
        self._request_quit()
        return False

    def _request_quit(self) -> None:
        """Quit, Alt-Q and Esc (4C.6). A recorded run pauses (the clock stops) and
        asks; Keep going resumes unless the operator had already paused, Quit test
        ends the run. A practice or a preview has nothing to lose and ends at once."""
        if self._shutdown_done or self._quit_pending:
            return
        if is_recorded(self.run_mode):
            self._quit_pending = True
            was_paused = self._paused
            self._set_paused(True)
            try:
                quit_it = self.confirm_quit(self.view, len(self.task.trials), len(self.task.targets))
            finally:
                self._quit_pending = False
            if not quit_it:
                if not was_paused:
                    self._set_paused(False)
                return
        self._shutdown(ended_by=ENDED_QUIT)

    def _display_trial_number(self) -> int:
        """The 1-based trial the bar names. A pause that interrupted a trial leaves
        the task one behind (that trial comes back on resume), so it is added back."""
        return self.task.trial_number + (1 if self._paused and self._pause_interrupted else 0)

    def _update_run_bar(self, t_ns: int) -> None:
        """The run bar status, and whether Skip trial can be pressed (4C.5)."""
        since = None if self._last_valid_ns is None else max(0.0, (t_ns - self._last_valid_ns) / 1e9)
        text, level = tracking_status(bool(self.client.is_connected()), since)
        preview = self.run_mode == PREVIEW
        mouse = self._pointer_is_mouse
        if mouse and not self._gaze_recorded:
            text = ""  # a Mouse run with no tracker has nothing to report on it
        status = run_status(
            self._display_trial_number(),
            len(self.task.targets),
            text,
            level,
            practice=self.run_mode == PRACTICE,
            paused=self._paused,
            preview=preview,
            mouse=mouse,
            # A Gaze test previewed on the mouse because the tracker was not ready (H4).
            tracker_not_ready=preview and mouse and not self.input_choice.is_mouse,
        )
        bar = self.view.run_bar
        bar.set_status(status)
        bar.set_skip_enabled(not self._paused and self.task.phase is Phase.WAIT_INPUT)

    def _check_canvas_resized(self, t_ns: int) -> None:
        """Emit CANVAS_RESIZED when the canvas size differs from the last tick.

        Done in the tick, not when a size is asked for: the new size only exists
        after Qt's layout pass. Physical px, same as _record_geometry()'s
        ``canvas_*`` (SPEC-display-scaling-cursor-accuracy.md S8.8).
        """
        if int(self.canvas.width()) <= 0 or int(self.canvas.height()) <= 0:
            return
        size = _canvas_physical(self.canvas)[:2]
        if self._last_canvas_size is None:
            self._last_canvas_size = size
            return
        if size != self._last_canvas_size:
            self._last_canvas_size = size
            self.recorder.record_event("CANVAS_RESIZED", t_ns, canvas_w=size[0], canvas_h=size[1])
            self.recorder.log(f"Canvas resized to {size[0]}x{size[1]}.")

    def _park_cursor(self) -> None:
        """Hide the OS cursor and park it on the canvas, once the canvas is on screen
        (a Gaze + Switch run, I6): at the start, and again after a resume. Retried each
        tick until the canvas is visible, since it is not yet when the run is built."""
        if self._cursor_pending and self.canvas.isVisible():
            self.run_cursor.hide_and_park()
            self._cursor_pending = False

    # -- main loop ---------------------------------------------------------

    def _sync_gaze_geometry(self) -> None:
        """Feed the task the real tracked-screen geometry (SPEC-gui-audit-
        2026-09-10.md item 5) so pointer conversion doesn't assume the
        canvas fills the tracked monitor -- the confirmed cause of gaze
        undershooting targets away from center (worst on whichever edge is
        furthest from the canvas's on-screen position).

        The geometry comes from the canvas's ``QScreen`` in Qt logical
        pixels, not from ``SCREEN_SIZE`` (physical): mixing the two broke
        the cursor at 125/150 % display scale (SPEC-display-scaling-cursor-
        accuracy.md D1). ``SCREEN_SIZE`` is only a sanity check, logged once
        per device-info query (D2).

        A no-op (``BaseTask`` keeps its today-identical canvas-relative
        fallback) whenever ``SCREEN_SIZE`` wasn't reported -- replay mode,
        an unanswered query, or before any connect has happened.
        """
        if self._pointer_is_mouse:
            # The mouse is normalized to the canvas itself, so there is no monitor
            # geometry to convert it by (a tracker recording alongside has its own).
            return
        info = self.client.device_info
        if info is None or not info.screen_width or not info.screen_height:
            return
        screen = self.canvas.screen()
        if screen is None:
            return
        geo = screen.geometry()
        if getattr(self, "_geometry_checked_info", None) is not info:
            self._geometry_checked_info = info
            dpr = screen.devicePixelRatio()
            if screen_size_mismatch(geo.width(), geo.height(), dpr, info.screen_width, info.screen_height):
                self.recorder.log(
                    f"Gazepoint SCREEN_SIZE {info.screen_width}x{info.screen_height} does not match the "
                    f"canvas's screen ({round(geo.width() * dpr)}x{round(geo.height() * dpr)} physical): "
                    "the canvas may not be on the monitor Gazepoint Control tracks."
                )
        canvas_origin = self.canvas.mapToGlobal(QPoint(0, 0))
        self.task.set_gaze_geometry(
            *gaze_geometry_from_screen(
                geo.x(), geo.y(), geo.width(), geo.height(), canvas_origin.x(), canvas_origin.y()
            )
        )

    def _record_geometry(self) -> None:
        """Persist the frames the recorded gaze maps onto (SPEC-gazepoint-
        analysis-export-parity.md S4.2), once, into ``metadata.json``.

        ``screen_*_px`` is the tracked monitor -- the only correct scale for
        any pixel metric derived from the stream; the canvas fields say where
        the task scene sat on it. Physical size comes from config when set,
        else the OS (EDID -- can be wrong, hence the override); viewing
        distance is config only, nothing measures it. Runs on the first tick
        where the canvas has a real size (a widget reports 0x0 or a
        pre-layout default at construction). In replay mode the monitor
        fields stay None -- there is no tracked screen to report.
        """
        if self.canvas.width() <= 0 or self.canvas.height() <= 0:
            return
        info = self.client.device_info
        app_cfg = self.config.get("app", {})
        meta = self.metadata
        # Canvas fields are physical px relative to the canvas's own QScreen
        # origin (S8.8) -- the same unit as ``screen_*_px``.
        canvas_w, canvas_h, offset_x, offset_y, dpr = _canvas_physical(self.canvas)
        if info is not None and info.screen_width and info.screen_height:
            meta.screen_width_px = info.screen_width
            meta.screen_height_px = info.screen_height
        elif self._pointer_is_mouse and not self._gaze_recorded and dpr is not None:
            # No tracker to report SCREEN_SIZE: the monitor is the one the canvas is on,
            # in the same physical px, so the report can still give degrees.
            geo = self.canvas.screen().geometry()
            meta.screen_width_px = round(geo.width() * dpr)
            meta.screen_height_px = round(geo.height() * dpr)
        if info is not None:
            # Already placeholder-filtered by the client (S24.1).
            meta.gazepoint_rate_hz = info.rate_hz
            meta.gazepoint_bus = info.bus
            meta.gazepoint_serial = info.serial
        meta.canvas_width_px = canvas_w
        meta.canvas_height_px = canvas_h
        meta.canvas_offset_x_px = offset_x
        meta.canvas_offset_y_px = offset_y
        if dpr is not None:
            meta.canvas_units = "physical"
        physical_w = app_cfg.get("screen_physical_width_mm")
        physical_h = app_cfg.get("screen_physical_height_mm")
        if physical_w is None or physical_h is None:
            screen = self.canvas.screen()
            if screen is not None:
                size_mm = screen.physicalSize()
                physical_w = physical_w if physical_w is not None else round(size_mm.width(), 1)
                physical_h = physical_h if physical_h is not None else round(size_mm.height(), 1)
        meta.screen_physical_width_mm = float(physical_w) if physical_w else None
        meta.screen_physical_height_mm = float(physical_h) if physical_h else None
        distance = app_cfg.get("viewing_distance_mm")
        meta.viewing_distance_mm = float(distance) if distance else None
        self._geometry_recorded = True
        scale_note = ""
        if dpr is not None and round(dpr * 100) != 100:
            scale_note = f" (physical px; Windows scale {round(dpr * 100)} %)"
        self.recorder.log(
            f"Geometry: monitor {meta.screen_width_px}x{meta.screen_height_px}px, canvas "
            f"{meta.canvas_width_px}x{meta.canvas_height_px}px at +{offset_x},+{offset_y}"
            f"{scale_note}, "
            f"physical {meta.screen_physical_width_mm}x{meta.screen_physical_height_mm}mm, "
            f"viewing distance {meta.viewing_distance_mm}mm."
        )
        display_line = self._record_display()
        if display_line:
            self.recorder.log(display_line)

    def _record_display(self) -> str:
        """Fill the display fields from the canvas's own screen (where the
        task actually ran, SPEC-display-standard-check.md S4.5) and return the
        one ``Display:`` session-log line ("" when there is no screen)."""
        screen = self.canvas.screen()
        if screen is None:
            return ""
        geo = screen.geometry()
        check = check_display(geo.width(), geo.height(), screen.devicePixelRatio())
        meta = self.metadata
        meta.display_width_px = check.width_px
        meta.display_height_px = check.height_px
        meta.display_scale_percent = check.scale_percent
        meta.display_standard = check.standard
        meta.display_refresh_hz = round(float(screen.refreshRate()), 1)
        text = f"Display: {check.width_px}x{check.height_px} at {check.scale_percent}%"
        if check.standard:
            return f"{text} (standard)."
        ack = ", acknowledged by operator" if meta.display_nonstandard_acknowledged else ""
        return f"{text} (NON-STANDARD{ack})."

    def _tick(self) -> None:
        t_ns = now_ns()
        if self._paused:
            # Paused (4C.6): the task is not updated and no gaze row is written. The
            # raw queue is still emptied and thrown away, so a long pause neither
            # overflows it nor replays as a burst on resume, and pause time (a child
            # looking away) never lowers the run's valid-gaze share.
            self.client.drain_raw()
            if self._is_switch and self.switch.consume_click():
                # A press while paused counts for nothing (I5d); it is logged.
                self.task.ignore_press(t_ns, "paused")
            self._update_run_bar(t_ns)
            return
        # Keep hit-testing in sync with whatever the canvas actually renders
        # at (fullscreen resolution, a resized window, ...) instead of the
        # configured screen_width_px/height_px default.
        self.task.set_screen_size(self.canvas.width(), self.canvas.height())
        self._sync_gaze_geometry()
        if not self._geometry_recorded:
            self._record_geometry()
        self._park_cursor()
        self._check_canvas_resized(t_ns)
        if self._save_all_gaze or self._save_eye_geometry:
            # Every raw <REC> since the last frame, at device rate -- the
            # per-frame gaze_stream.csv sample below is a different, coarser
            # view and stays as it was.
            for raw_t_ns, attrs in self.client.drain_raw():
                self.recorder.record_raw(raw_t_ns, attrs)
        pointer = self.eye.poll(t_ns)
        if self._is_switch:
            # The switch's press, once (a one-frame rising edge); judged by the task.
            pointer = Pointer(
                x=pointer.x, y=pointer.y, valid=pointer.valid, clicked=self.switch.consume_click()
            )

        sample = self.eye.latest_sample()
        if self._pointer_is_mouse:
            # The pointer is the mouse: its samples go to pointer_stream.csv, and what the
            # tracker saw alongside (if one is recording) to the gaze files (H4).
            if sample is not None:
                self.recorder.record_pointer(sample)
            sample = self.client.latest() if self._gaze_recorded else None
        fresh = self._is_fresh_gaze_sample(sample)
        if fresh and self.config.get("recording", {}).get("save_gaze_stream", True):
            self.recorder.record_gaze(sample)
        if fresh and self.client.is_live and not self._pointer_is_mouse:
            self._record_latency(sample.t_ns, t_ns)
        # Whether the *tracker* has gaze (the bar's "tracking" text): the pointer's own
        # validity for a gaze run, the alongside sample's for a Mouse run.
        gaze_valid = (sample is not None and sample.valid) if self._pointer_is_mouse else pointer.valid
        if gaze_valid:
            self._last_valid_ns = t_ns

        result = self.task.update(t_ns, pointer)
        # After set_screen_size above, so the scene (a grid's cell inset) is for
        # the same canvas size the task just fitted and hit-tested at.
        self._scene = self.task.scene_spec()

        if self._dropout_log is not None:
            self._dropout_log.observe(t_ns, pointer.valid, result.cursor_xy_norm)

        self.canvas.set_frame(
            target_xy_norm=result.target_xy_norm,
            # The effective radius (a grid cell can cap it below the configured
            # one), so the drawn circle and the hitbox agree (S4.3).
            target_radius_px=(result.target_radius_px if result.target else 90.0),
            # The task's own corrected canvas-normalized pointer, NOT the raw
            # monitor-normalized pointer.x/y -- feeding the raw value here was
            # the confirmed cause of the cursor silently vanishing off-center
            # (SPEC-gui-audit-2026-09-10.md S6).
            cursor_xy_norm=result.cursor_xy_norm,
            cursor_valid=pointer.valid,
            dwell_progress=result.dwell_progress,
            selectable=result.selectable,
            layout_slots=self.task.layout_slots,
            on_target=result.on_target,
            scene=self._scene,
            active_slot=(result.target.slot_index if result.target else -1),
        )

        self._update_run_bar(t_ns)

        if self.task.is_done:
            self._shutdown()

    def _is_fresh_gaze_sample(self, sample) -> bool:
        """Whether ``sample`` is one the gaze files do not hold yet, from a tracker that is
        connected (F3, SPEC-audit-fixes.md H6): the last sample is not written again while the
        loop runs faster than the device, nor once per tick after the link dropped."""
        if sample is None or not self.client.is_connected() or sample.t_ns == self._last_gaze_t_ns:
            return False
        self._last_gaze_t_ns = sample.t_ns
        return True

    def _record_session_end_quality(self) -> None:
        """Fill the measured-quality metadata fields (SPEC-gazepoint-analysis-
        export-parity.md S10.6.3) just before ``metadata.json`` is rewritten
        on close: the device rate from the raw file's count / time span (live
        sessions only) and
        the session median eye distance from ``eye_geometry.csv``."""
        meta = self.metadata
        gap_used = getattr(self.task, "gap_capped_px", None)
        if gap_used is not None and meta.grid_gap is not None:
            # The cell gap the live canvas capped (SPEC-grid-cell-gap.md H4);
            # the GAP_CAPPED event holds the same number at the moment it applied.
            meta.grid_gap["gap_px_used"] = round(gap_used, 1)
        if self.client.is_live:
            # Records / device-time span of the raw file, not the on-screen
            # meter (capped by the GUI frame rate) -- SPEC S10.6.9.
            self.recorder.flush_eye_geometry()
            self.recorder.flush_all_gaze()
            raw_name = EYE_GEOMETRY_FILENAME if self._save_eye_geometry else ALL_GAZE_FILENAME
            raw_path = self.recorder.session_dir / raw_name
            if self._save_eye_geometry or self._save_all_gaze:
                meta.measured_sample_rate_hz = measured_sample_rate_hz(raw_path)
        if self._save_eye_geometry:
            self.recorder.flush_eye_geometry()
            meta.measured_eye_distance_mm_median = median_eye_distance_mm(
                self.recorder.session_dir / EYE_GEOMETRY_FILENAME
            )

    def _record_latency(self, sample_t_ns: int, t_ns: int) -> None:
        summary = self._latency.add_sample(sample_t_ns, t_ns)
        if summary is not None:
            self.recorder.record_event(
                "LATENCY_SAMPLE",
                t_ns,
                latency_ms_mean=round(summary.mean_ms, 2),
                latency_ms_min=round(summary.min_ms, 2),
                latency_ms_max=round(summary.max_ms, 2),
                n_samples=summary.n_samples,
            )

    def _shutdown(self, ended_by: str | None = None) -> None:
        """End the run. Every file of a recorded run is on disk before anything is
        shown, so a crash at a run-end dialog loses nothing; ``on_finished`` then gets
        the :class:`~src.engine.run_result.RunResult`. ``ended_by`` is
        ``operator_quit`` for the quit flow, else derived (the task ran out of
        trials). Idempotent: the tick and a quit can both fire in one pass."""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.timer.stop()
        self._cursor_pending = False
        self.run_cursor.show()  # the cursor comes back with the run's end or quit (I6)
        if self._dropout_log is not None:
            # Flush a dropout still open at the end, so one that never
            # recovered is recorded rather than silently lost.
            self._dropout_log.close(now_ns())
        if is_recorded(self.run_mode):
            self._write_session_files(ended_by)
        if self._owns_client:
            self.client.stop()
        if self._embedded:
            if self._on_finished is not None:
                self._on_finished(self._run_result(ended_by))
        else:
            QApplication.quit()

    def _run_result(self, ended_by: str | None) -> RunResult:
        session_dir = self.recorder.session_dir if is_recorded(self.run_mode) else None
        finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        return run_result_from_task(
            self.run_mode, self.task, session_dir, finished_at, ended_by=ended_by
        )

    def _write_session_files(self, ended_by: str | None = None) -> None:
        """Everything a recorded run leaves on disk at its end. Skipped for a
        practice or preview run, which has nothing to write (NullRecorder).
        ``report.json`` is not built here: only a run the operator saves gets one
        (:func:`~src.engine.run_result.finish_run`, HD1)."""
        if self._save_all_gaze or self._save_eye_geometry:
            # Whatever arrived since the last tick; recorded unless the run ends
            # paused (the quit question), when it is pause time like the rest.
            for raw_t_ns, attrs in self.client.drain_raw():
                if not self._paused:
                    self.recorder.record_raw(raw_t_ns, attrs)
        trials_path = self.recorder.write_trials(self.task.trials)
        self.recorder.log(f"Wrote {len(self.task.trials)} trials -> {trials_path}")
        if self._save_all_gaze:
            # Saccade columns + fixations.csv are a post-pass (a fixation's
            # saccade describes the jump *into* it), scaled by the tracked
            # monitor -- never the canvas (SPEC S4.2). Without a reported
            # SCREEN_SIZE fall back to the configured default, and say so.
            app_cfg = self.config.get("app", {})
            width = self.metadata.screen_width_px or int(app_cfg.get("screen_width_px", 1920))
            height = self.metadata.screen_height_px or int(app_cfg.get("screen_height_px", 1080))
            if not self.metadata.screen_width_px:
                self.recorder.log(
                    f"SCREEN_SIZE unknown; saccade pixels scaled by configured {width}x{height}."
                )
            self.recorder.log(f"Saccade metrics scaled by {width}x{height}px.")
        # How the run ended, before close() so metadata.json carries it
        # (SPEC-compass-task-flow.md 4C.9). Anything but running out of trials is
        # the operator quitting.
        self.recorder.log(
            apply_outcome(
                self.metadata,
                self.task,
                now_ns(),
                ended_by,
                trial_number=self._display_trial_number(),
            )
        )
        # Host-clock time of all_gaze.csv TIME=0, after the last raw record was
        # written above, to align device-rate rows with the trial windows
        # (SPEC-compass-task-flow.md 4D.4-5).
        self.metadata.raw_clock_offset_ns = self.recorder.raw_clock_offset_ns
        self._record_session_end_quality()
        self.recorder.close()
        if self._save_all_gaze:
            finalize_all_gaze(self.recorder.session_dir, width, height)
        write_session_metrics(self.recorder.session_dir)


def run_gui(
    task_id: str,
    replay_path: str | None = None,
    subject_id: str = "P000",
    calibration_file: str | None = None,
    skip_task_settings_dialog: bool = False,
) -> int:
    app = QApplication.instance() or QApplication([])

    structural_overrides: dict | None = None
    if not skip_task_settings_dialog:
        # Structural/layout task params (grid size, radius, trial count, ...)
        # are collected here, before AssessmentApp/build_targets() run --
        # SPEC-live-settings-panel.md section 5.3. "Start task" with no
        # changes reproduces today's YAML-only behavior exactly.
        preview_config = load_task_config(task_id)
        dialog = TaskSettingsDialog(task_id, preview_config)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            print("Task launch cancelled.", file=sys.stderr)
            return 0
        structural_overrides = dialog.overrides()

    try:
        assessment = AssessmentApp(
            task_id=task_id,
            replay_path=replay_path,
            subject_id=subject_id,
            calibration_file=calibration_file,
            structural_overrides=structural_overrides,
        )
    except CalibrationFileError as exc:
        print(f"Calibration file error: {exc}", file=sys.stderr)
        return 2
    assessment.window.show()
    return app.exec()
