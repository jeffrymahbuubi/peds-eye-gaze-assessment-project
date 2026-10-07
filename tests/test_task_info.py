"""SPEC-compass-task-flow.md 4A.1 (A2): TASK_INFO lives in the Qt-free engine package."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.engine.task_info import TASK_INFO
from src.engine.task_runner import TASK_REGISTRY


def test_task_info_covers_exactly_the_registered_tasks():
    assert set(TASK_INFO) == set(TASK_REGISTRY)
    for name, description in TASK_INFO.values():
        assert name.strip() and description.strip()


def test_grid_label_no_longer_claims_3x3():
    assert TASK_INFO["click_grid"][0] == "Grid Click"
    assert all("(3×3)" not in name for name, _ in TASK_INFO.values())


def test_ui_pages_share_the_engine_table():
    from src.ui import add_test_dialog, task_config_page, test_list_page

    assert test_list_page.TASK_INFO is TASK_INFO
    assert add_test_dialog.TASK_INFO is TASK_INFO
    assert task_config_page.TASK_INFO is TASK_INFO
