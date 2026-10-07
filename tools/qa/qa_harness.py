"""Launch the dashboard for qt-mcp driving with deferred clicks and key presses.

qt-mcp's probe answers each click/key RPC only after the event is handled. A click that
opens a modal dialog (``QDialog.exec()``) would block that reply, so the probe stalls.
Here the real click/key is posted with ``QTimer.singleShot(0, ...)`` and the RPC returns
at once; the dialog's nested event loop then keeps serving later probe calls.

Run from the repo root (QA only, never shipped):
    $env:QT_MCP_PROBE="1"; $env:QT_MCP_PORT="9142"
    ..\\.venv\\Scripts\\python.exe tools\\qa\\qa_harness.py

Rules: never put a ``wait`` step in the same qt_batch as a click that opens a dialog, and
never batch-wait while a dialog may open on its own; poll with short calls instead.
"""

import runpy
import sys

from PySide6.QtCore import QTimer
from qt_mcp.probe import interactor as _interactor

_orig_click = _interactor.Interactor.click
_orig_key = _interactor.Interactor.key_press


def _click(self, *args, **kwargs):
    QTimer.singleShot(0, lambda: _orig_click(self, *args, **kwargs))
    return {"ok": True}


def _key(self, *args, **kwargs):
    QTimer.singleShot(0, lambda: _orig_key(self, *args, **kwargs))
    return {"ok": True}


_interactor.Interactor.click = _click
_interactor.Interactor.key_press = _key
sys.argv = ["src.main", "--dashboard"]
runpy.run_module("src.main", run_name="__main__")
