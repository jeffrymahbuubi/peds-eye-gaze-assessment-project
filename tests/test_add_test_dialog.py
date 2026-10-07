"""SPEC-compass-task-flow.md 4A.5 / HA2: the Add New Test dialog."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from src.engine.task_info import TASK_INFO
from src.engine.task_runner import TASK_REGISTRY
from src.ui.add_test_dialog import MAX_COUNT, AddTestDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_it_lists_the_four_tasks_with_their_names_and_descriptions(qapp):
    dialog = AddTestDialog()
    assert dialog.task_list.count() == len(TASK_REGISTRY) == 4
    for row, task_id in enumerate(TASK_REGISTRY):
        item = dialog.task_list.item(row)
        assert item.data(Qt.ItemDataRole.UserRole) == task_id
        name, description = TASK_INFO[task_id]
        label = dialog.task_list.itemWidget(item)
        assert isinstance(label, QLabel)
        assert f"<b>{name}</b>" in label.text() and description in label.text()


def test_nothing_is_chosen_at_first_so_add_is_off(qapp):
    dialog = AddTestDialog()
    assert dialog.choice() is None and not dialog.add_button.isEnabled()
    assert dialog.count() == 1  # "How many" starts at 1


def test_choosing_a_task_turns_add_on(qapp):
    dialog = AddTestDialog()
    dialog.select_task("click_grid")
    assert dialog.add_button.isEnabled()
    assert dialog.choice() == ("click_grid", 1)
    dialog.count_spin.setValue(4)
    assert dialog.choice() == ("click_grid", 4)


def test_how_many_runs_from_one_to_ten(qapp):
    dialog = AddTestDialog()
    assert (dialog.count_spin.minimum(), dialog.count_spin.maximum()) == (1, MAX_COUNT) == (1, 10)
    dialog.count_spin.setValue(99)
    assert dialog.count() == 10
    dialog.count_spin.setValue(0)
    assert dialog.count() == 1


def test_add_accepts_and_cancel_rejects(qapp):
    dialog = AddTestDialog()
    dialog.select_task("scanning")
    dialog.add_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    other = AddTestDialog()
    other.select_task("scanning")
    other.cancel_button.click()
    assert other.result() == QDialog.DialogCode.Rejected


def test_a_double_click_adds_one_whatever_the_count_says(qapp):
    dialog = AddTestDialog()
    dialog.count_spin.setValue(5)
    item = dialog.task_list.item(list(TASK_REGISTRY).index("follow_moving"))
    dialog.task_list.itemDoubleClicked.emit(item)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.choice() == ("follow_moving", 1)


def test_ask_returns_the_choice_or_none(qapp, monkeypatch):
    def accepted(self):
        self.select_task("click_static")
        self.count_spin.setValue(2)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(AddTestDialog, "exec", accepted)
    assert AddTestDialog.ask() == ("click_static", 2)
    monkeypatch.setattr(AddTestDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert AddTestDialog.ask() is None


def test_enter_does_not_add_by_accident(qapp):
    dialog = AddTestDialog()
    assert not dialog.add_button.autoDefault() and not dialog.cancel_button.autoDefault()
