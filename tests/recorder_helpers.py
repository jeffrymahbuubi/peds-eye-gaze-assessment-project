"""A recorder on a folder the test names itself (not a test module).

The tests of what the recorder *writes* do not care where the run folder sits, so they give
it ``<tmp>/<session_id>``. Where a run folder lives (``<subject>/runs/<task>/<date_time>``) is
tested in ``test_run_paths.py`` and ``test_recorder.py``."""

from __future__ import annotations

from pathlib import Path

from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata


def recorder_in(tmp_path: Path, metadata: SessionMetadata) -> SessionRecorder:
    """``SessionRecorder(metadata)`` writing to ``tmp_path / metadata.session_id``."""
    return SessionRecorder(metadata, session_dir=tmp_path / metadata.session_id)
