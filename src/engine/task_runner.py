"""Task registry + headless replay pipeline (plan sections 5.4, 6/Phase 2).

The registry maps task ids to task classes. :func:`run_headless_replay` runs a
full session against a recorded gaze fixture with no GUI and no threads, so the
whole "calibrate -> task -> export" loop is reproducible and testable — this is
the backbone of the ``--replay`` demo in :mod:`src.main`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..data.exporter import write_session_metrics
from ..data.recorder import SessionRecorder
from ..data.schema import GazeSample, SessionMetadata
from ..inputs.base import Pointer
from ..inputs.eye_input import DwellConfig, DwellSelector
from ..inputs.gazepoint_client import ReplayGazeSource
from ..tasks.base_task import BaseTask
from ..tasks.click_grid import ClickGridTask
from ..tasks.click_static import ClickStaticTask
from ..tasks.follow_moving import FollowMovingTask
from ..tasks.scanning import ScanningTask
from .config import load_task_config
from .input_choice import resolve_input
from .loop_rate import config_target_fps, resolve_target_fps
from .subject_store import replay_dir
from .target_size import (
    apply_grid_gap,
    apply_target_size,
    grid_gap_log_line,
    screen_scale,
    size_block,
    target_size_log_line,
    viewing_distance_mm,
)

TASK_REGISTRY: dict[str, type[BaseTask]] = {
    "click_static": ClickStaticTask,
    "click_grid": ClickGridTask,
    "follow_moving": FollowMovingTask,
    "scanning": ScanningTask,
}


def build_task(
    task_id: str,
    config: dict[str, Any],
    recorder: SessionRecorder | None = None,
    feedback=None,
    seed: int = 0,
    preroll_ms: float = 0.0,
) -> BaseTask:
    if task_id not in TASK_REGISTRY:
        raise KeyError(f"Unknown task '{task_id}'. Known: {sorted(TASK_REGISTRY)}")
    app_cfg = config.get("app", {})
    dwell_cfg = config.get("dwell", {})
    dwell = DwellSelector(
        DwellConfig(
            threshold_ms=float(dwell_cfg.get("threshold_ms", 800)),
            refractory_ms=float(dwell_cfg.get("refractory_ms", 500)),
        )
    )
    return TASK_REGISTRY[task_id](
        config=config,
        screen_width_px=int(app_cfg.get("screen_width_px", 1920)),
        screen_height_px=int(app_cfg.get("screen_height_px", 1080)),
        recorder=recorder,
        feedback=feedback,
        dwell=dwell,
        input_mode=resolve_input(config).mode,
        seed=seed,
        preroll_ms=preroll_ms,
    )


def run_headless_replay(
    task_id: str,
    replay_path: str | Path,
    subject_id: str = "REPLAY",
    session_id: str | None = None,
    output_root: str | Path = "sessions",
    config_root: str | Path | None = None,
    seed: int = 0,
    max_seconds: float = 600.0,
    feedback=None,
) -> dict[str, Any]:
    """Run a full session from a gaze fixture and write session artifacts.

    Writes to ``<output_root>/_system/replay/<session_id>`` (SPEC-subject-data-layout.md H11).
    Returns a dict with ``session_dir``, ``n_trials`` and summary counts.
    """
    config = load_task_config(task_id, config_root)
    # A number keeps its value; "auto"/missing is 60 (no live device here).
    fps, _ = resolve_target_fps(config_target_fps(config), None, False)
    dt_ns = int(1e9 / fps)

    source = ReplayGazeSource(replay_path, loop=True)

    # A replay has no screen: a target size preset resolves on the reference
    # monitor ("fallback", SPEC-target-size-and-motion-paths.md S4.1), exactly
    # as the GUI does when it has no physical width to go on.
    app_cfg = config.get("app", {})
    scale = screen_scale(None, app_cfg)
    task_cfg = config.get("task", {})
    size_info = apply_target_size(
        task_cfg, scale, viewing_distance_mm(app_cfg), block=size_block(task_cfg)
    )
    # Grid Click's cell gap, on the same reference monitor (SPEC-grid-cell-gap.md S4.2).
    gap_info = apply_grid_gap(task_cfg, scale, viewing_distance_mm(app_cfg))

    session_id = session_id or f"replay_{task_id}_{subject_id}"
    metadata = SessionMetadata(
        subject_id=subject_id,
        session_id=session_id,
        started_ns=0,
        input_mode=resolve_input(config).mode,
        tasks=[task_id],
        notes="headless replay",
        target_size=size_info,
        grid_gap=gap_info,
    )

    replay_folder = replay_dir(output_root) / session_id  # a replay is not a subject's data (H11)
    with SessionRecorder(metadata, session_dir=replay_folder) as recorder:
        task = build_task(task_id, config, recorder=recorder, feedback=feedback, seed=seed)
        recorder.log(f"Starting headless replay: task={task_id} fps={fps}")
        if size_info is not None:
            recorder.log(target_size_log_line(size_info, scale))
        if gap_info is not None:
            recorder.log(grid_gap_log_line(gap_info))

        max_frames = int(max_seconds * fps)
        save_gaze = config.get("recording", {}).get("save_gaze_stream", True)

        for frame in range(max_frames):
            t_ns = frame * dt_ns
            sample = source.sample_at(t_ns / 1e9)
            sample = GazeSample(
                t_ns=t_ns,
                x=sample.x,
                y=sample.y,
                valid=sample.valid,
                fixation_id=sample.fixation_id,
                fix_duration_s=sample.fix_duration_s,
                pupil_left=sample.pupil_left,
                pupil_right=sample.pupil_right,
            )
            if save_gaze:
                recorder.record_gaze(sample)
            pointer = Pointer(x=sample.x, y=sample.y, valid=sample.valid, clicked=False)
            task.update(t_ns, pointer)
            if task.is_done:
                break

        gap_used = getattr(task, "gap_capped_px", None)
        if gap_used is not None and gap_info is not None:
            gap_info["gap_px_used"] = round(gap_used, 1)  # metadata is rewritten on close
        trials_path = recorder.write_trials(task.trials)
        recorder.log(f"Wrote {len(task.trials)} trials -> {trials_path}")
        # Close explicitly (flushes gaze_stream.csv fully) so the metrics below
        # read complete files; the `with` block's own close() on exit is then
        # a no-op (SessionRecorder.close() guards on self._closed).
        recorder.close()
        metrics_path = write_session_metrics(recorder.session_dir)

        n_hits = sum(1 for tr in task.trials if tr.is_hit)
        n_timeouts = sum(1 for tr in task.trials if tr.is_timeout)
        return {
            "session_dir": str(recorder.session_dir),
            "trials_csv": str(trials_path),
            "session_metrics_path": str(metrics_path),
            "n_trials": len(task.trials),
            "n_hits": n_hits,
            "n_timeouts": n_timeouts,
        }
