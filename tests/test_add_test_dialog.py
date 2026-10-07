"""SPEC-compass-task-flow.md 4A.5 / HA2: the Add New Test dialog."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QSizePolicy

from src.engine.task_info import TASK_INFO
from src.engine.task_runner import TASK_REGISTRY
from src.ui.add_test_dialog import MAX_COUNT, MAX_VISIBLE_ROWS, SPACING, AddTestDialog


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


# -- F6: every row is as tall as its label needs ----------------------------------------------------------------


def rows_of(dialog):
    return [(dialog.task_list.item(r), dialog.task_list.itemWidget(dialog.task_list.item(r)))
            for r in range(dialog.task_list.count())]


def shown_dialog(font_points: int | None = None) -> AddTestDialog:
    dialog = AddTestDialog()
    if font_points is not None:  # a non-default font on the dialog and on every row
        font = QFont(dialog.font())
        font.setPointSize(font_points)
        dialog.setFont(font)
        for _, label in rows_of(dialog):
            label.setFont(font)
    dialog.show()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    return dialog


@pytest.mark.parametrize("font_points", [None, 14, 22])
def test_every_row_is_as_tall_as_its_label_needs_and_nothing_squeezes_the_label(qapp, font_points):
    """The descenders of the grey line were cut because the row's padding made the label
    shorter than its own size hint. A row's height, its on-screen rectangle and the label's
    real height must all be at least what the label asks for."""
    dialog = shown_dialog(font_points)
    for item, label in rows_of(dialog):
        needs = label.sizeHint().height()
        assert item.sizeHint().height() >= needs
        assert dialog.task_list.visualItemRect(item).height() >= needs
        assert label.height() >= needs  # the label is laid out at its full height: both lines show


@pytest.mark.parametrize(
    "kind",
    [QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.DevicePixelRatioChange, QEvent.Type.Polish],
    ids=lambda kind: kind.name,
)
def test_a_change_of_font_style_or_scale_measures_the_rows_again(qapp, kind):
    dialog = shown_dialog()
    item, label = rows_of(dialog)[0]
    before = item.sizeHint().height()
    label.setText(label.text() + "<br>a third line<br>and a fourth line")  # the label now needs more
    assert label.sizeHint().height() > before
    QCoreApplication.sendEvent(label, QEvent(kind))
    assert item.sizeHint().height() == label.sizeHint().height() > before
    QCoreApplication.processEvents()
    assert label.height() >= label.sizeHint().height()


def test_a_dialog_that_is_shown_again_measures_the_rows_once_more(qapp):
    dialog = shown_dialog()
    item, label = rows_of(dialog)[1]
    dialog.hide()
    label.setText(label.text() + "<br>one more line")
    dialog.show()
    QCoreApplication.processEvents()
    assert item.sizeHint().height() == label.sizeHint().height()


def test_the_list_gives_its_items_no_padding_of_their_own(qapp):
    """The root cause of F6: an item widget is laid out inside the item's padding box."""
    from src.ui.dialog_theme import ITEM_VIEW_STYLESHEET

    assert "padding" not in ITEM_VIEW_STYLESHEET


# -- V4: spacing, a list that fills the dialog, a scroll bar only when needed (SPEC 7.1) ---------------


def test_the_rows_are_spaced_apart_and_the_list_scrolls_only_when_needed(qapp):
    dialog = AddTestDialog()
    assert SPACING > 0 and dialog.task_list.spacing() == SPACING > 0
    assert dialog.task_list.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    # never a horizontal bar: the list asks for its widest row, and a bar would eat height
    assert dialog.task_list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_neighbouring_rows_have_a_gap_between_them(qapp):
    dialog = shown_dialog()
    rects = [dialog.task_list.visualItemRect(item) for item, _ in rows_of(dialog)]
    gaps = [b.top() - a.bottom() - 1 for a, b in zip(rects, rects[1:], strict=False)]
    assert gaps and all(gap >= SPACING for gap in gaps)  # they used to touch (a gap of 0)


def test_the_list_takes_the_spare_height_of_the_dialog(qapp):
    dialog = shown_dialog()
    layout = dialog.layout()
    index = layout.indexOf(dialog.task_list)
    assert layout.stretch(index) == 1  # the only stretch: the list fills what is left
    assert dialog.task_list.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    before = dialog.task_list.height()
    dialog.resize(dialog.width(), dialog.height() + 150)
    QCoreApplication.processEvents()
    assert dialog.task_list.height() >= before + 140


def test_the_dialog_opens_just_tall_enough_for_the_rows_with_no_scroll_bar(qapp):
    """Four spaced rows used to be taller than the list's fixed 192 px preference (a scroll bar),
    and before the spacing they left empty space under the last one. The list now asks for its
    rows' height, so the dialog opens with all of them showing and nothing left over."""
    dialog = shown_dialog()
    lst = dialog.task_list
    assert lst.verticalScrollBar().maximum() == 0 and not lst.verticalScrollBar().isVisible()
    last = lst.visualItemRect(rows_of(dialog)[-1][0])
    assert lst.viewport().height() - last.bottom() <= 2 * SPACING + 2  # no empty band under the rows
    assert lst.sizeHint().height() >= sum(item.sizeHint().height() + 2 * SPACING for item, _ in rows_of(dialog))


def test_more_tasks_than_fit_scroll_and_the_scroll_bar_appears(qapp, monkeypatch):
    """A future task type: ten tasks do not all fit, so the list scrolls instead of growing."""
    import src.ui.add_test_dialog as module

    monkeypatch.setattr(module, "TASK_REGISTRY", {f"task_{n}": None for n in range(10)})
    dialog = shown_dialog()
    lst = dialog.task_list
    assert lst.count() == 10
    assert lst.verticalScrollBar().maximum() > 0 and lst.verticalScrollBar().isVisible()
    # it asked for MAX_VISIBLE_ROWS rows, not ten
    assert lst.sizeHint().height() < 8 * (lst.item(0).sizeHint().height() + 2 * SPACING)
    assert lst.sizeHint().height() >= MAX_VISIBLE_ROWS * (lst.item(0).sizeHint().height() + 2 * SPACING)
