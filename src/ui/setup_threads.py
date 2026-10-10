"""Ending the Setup page's background threads before its window goes (SPEC-audit-fixes.md H4).

Connect, Test Connection, Re-check and Do Calibration each run on a ``QThread`` that is a child
of the :class:`~src.ui.setup_page.SetupPage`. Qt aborts the process ("QThread: Destroyed while
thread is still running") if one is destroyed while it runs, which closing the window during a
connect or a calibration would do. :func:`wait_for_threads` is what the window's close event
calls first.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from PySide6.QtCore import QThread

# Longest a window close waits in all. The slowest thread is a connect to an address that does
# not answer (a 5 s socket timeout plus the 0.5 s device-info query).
STOP_WAIT_MS = 10_000


def _running(thread: QThread | None) -> bool:
    if thread is None:
        return False
    try:
        return bool(thread.isRunning())
    except RuntimeError:  # the C++ object is already gone: it finished and was deleted
        return False


def wait_for_threads(threads: Iterable[QThread | None], timeout_ms: int = STOP_WAIT_MS) -> bool:
    """Ask each running thread to stop (``requestInterruption``) and wait for all of them,
    at most ``timeout_ms`` in total; return whether none is left running.

    ``requestInterruption`` only asks: a thread ends sooner if it looks at
    ``isInterruptionRequested``, and the Setup threads end on their own when their socket
    work does (the page closes the calibration's socket first, see
    :meth:`~src.ui.setup_page.SetupPage.stop_threads`).
    """
    running = [t for t in threads if _running(t)]
    for thread in running:
        thread.requestInterruption()
    deadline = time.monotonic() + timeout_ms / 1000.0
    for thread in running:
        thread.wait(max(0, int((deadline - time.monotonic()) * 1000)))
    return not any(_running(t) for t in running)
