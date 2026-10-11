"""Suite-wide fixtures. Choice-making tests run on the placeholder scene unless marked ``real_scene``.

Teardown for Qt tests. A test that shows a widget and fails (or only closes it) left the
C++ object alive until Python's garbage collector got to it, possibly in the middle of a later test's
``show()``/``processEvents()``: the intermittent segfault in ``test_muted_labels.py`` (2026-10-09).
After every test, close and delete every top-level widget, flush the deferred deletes and collect, so
no test inherits another's windows. Only ``qapp`` fixtures outlive a test, and they hold no widgets."""

from __future__ import annotations

import gc
import sys

import pytest


@pytest.fixture(autouse=True)
def _placeholder_choice_scene(request, monkeypatch, tmp_path_factory):
    """Pin every test to Choice-making's built-in placeholder scene: the scene loader's default
    folder and the task's asset folder point at an empty folder, so the real art and its scene.yaml
    (configs/assets/scenes/park/) cannot change tests written for the placeholder. A test marked
    ``real_scene`` sees the real assets."""
    if request.node.get_closest_marker("real_scene"):
        yield
        return
    empty = tmp_path_factory.getbasetemp() / "no_scene_assets"
    monkeypatch.setattr("src.tasks.choice_scene.ASSETS_ROOT", empty)
    monkeypatch.setattr("src.tasks.choice_making.ChoiceMakingTask.assets_root", empty)
    yield


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
