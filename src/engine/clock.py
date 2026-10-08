"""The clock every in-run duration is measured on (SPEC-audit-fixes.md H9, F7).

``time.time_ns()`` is the wall clock: Windows' time service steps it when the offset is
large, a laptop resumes with a corrected one, an operator fixes it by hand. A step in the
middle of a run would complete a dwell in progress, time a trial out at once and shift
every reaction time. :func:`now_ns` reads a clock that cannot step instead, anchored once
per process to the wall clock so its values stay in the same epoch-nanosecond domain as
before: ``trials.csv``, ``events.jsonl``, ``gaze_stream.csv`` and the analysis export keep
their format, and only a clock step during a run no longer shifts a duration.

``metadata.started_ns``, file names and the report's dates keep the real wall clock: they
say *when* a run happened, which is what the wall clock is for.

The monotonic source is ``time.perf_counter_ns``, not ``time.monotonic_ns``: on Windows
with Python 3.12 the latter is ``GetTickCount64`` (15.6 ms steps), which would put the
150 Hz reader's sample stamps on a 15.6 ms grid and equal stamps on distinct samples.
``perf_counter_ns`` is monotonic too and has a 100 ns step there.
"""

from __future__ import annotations

import time

# Read together, once, when the module is first imported (the process start in practice).
_WALL_ANCHOR_NS = time.time_ns()
_MONO_ANCHOR_NS = time.perf_counter_ns()


def now_ns() -> int:
    """Nanoseconds since the epoch as of the process start, advanced by a monotonic clock."""
    return _WALL_ANCHOR_NS + (time.perf_counter_ns() - _MONO_ANCHOR_NS)
