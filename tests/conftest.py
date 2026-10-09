"""Suite-wide teardown for Qt tests. A test that shows a widget and fails (or only closes it) left the
C++ object alive until Python's garbage collector got to it, possibly in the middle of a later test's
``show()``/``processEvents()``: the intermittent segfault in ``test_muted_labels.py`` (2026-10-09).
After every test, close and delete every top-level widget, flush the deferred deletes and collect, so
no test inherits another's windows. Only ``qapp`` fixtures outlive a test, and they hold no widgets."""

from __future__ import annotations

import gc
import sys

import pytest


@pytest.fixture(autouse=True)
def _close_qt_widgets():
    yield
    if "PySide6.QtWidgets" not in sys.modules:  # a test that never touched Qt
        return
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    gc.collect()
