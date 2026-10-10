"""The recorder that records nothing, for a practice or preview run (SPEC-compass-task-flow.md
4C.4). Split out of :mod:`src.data.recorder` to keep that file short; ``recorder`` re-exports it,
so ``from src.data.recorder import NullRecorder`` still works."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import GazeSample, SessionMetadata, TrialRecord


class NullRecorder:
    """A recorder that records nothing (SPEC-compass-task-flow.md 4C.4).

    Stands in for :class:`SessionRecorder` in a practice or preview run, which
    must leave no trace on disk: the same surface, every call a no-op, no
    session directory (``session_dir`` is ``None``). Lets the run code call the
    recorder unguarded, as it does for a real one.
    """

    def __init__(self, metadata: SessionMetadata | None = None) -> None:
        self.metadata = metadata
        self.session_dir: Path | None = None

    def __enter__(self) -> NullRecorder:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def open(self, *, gaze_stream: bool = True) -> None:
        return None

    def open_all_gaze(self, media_name: str, tick_frequency: int | None) -> None:
        return None

    def open_eye_geometry(self) -> None:
        return None

    def open_pointer_stream(self) -> None:
        return None

    def record_pointer(self, sample: GazeSample) -> None:
        return None

    def flush_eye_geometry(self) -> None:
        return None

    def flush_all_gaze(self) -> None:
        return None

    def record_raw(self, t_ns: int, attrs: dict[str, str]) -> None:
        return None

    @property
    def raw_clock_offset_ns(self) -> int | None:
        return None

    def record_target_track(self, t_ns: int, trial: int, x: float, y: float) -> None:
        return None

    def record_gaze(self, sample: GazeSample) -> None:
        return None

    def record_event(self, kind: str, t_ns: int, **payload: Any) -> None:
        return None

    def log(self, message: str) -> None:
        return None

    def record_trial(self, trial: TrialRecord) -> None:
        return None

    def write_trials(self, trials: list[TrialRecord]) -> None:
        return None

    def write_metadata(self, complete: bool | None = None) -> None:
        return None

    @property
    def trials_recorded(self) -> int:
        return 0

    def close(self) -> None:
        return None

    def abort(self) -> None:
        return None
