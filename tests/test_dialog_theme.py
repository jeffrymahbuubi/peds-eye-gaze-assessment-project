"""SPEC-compass-task-flow.md 7.1, FX1: the dashboard's dialogs render on the light theme
whatever the Windows app colour mode.

A machine in Windows dark mode gives Qt a dark application palette, and a widget the theme's
style sheet does not name (the Add New Test task list) then paints near-black. The tests put
a dark application palette in place, build each dialog and look at what it really paints
(offscreen Qt: colours are real, glyphs are not, so only colours and pixels are checked).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QPushButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui import config_widgets
from src.ui.add_test_dialog import SPACING, AddTestDialog
from src.ui.config_save_dialogs import ConfigNameDialog
from src.ui.config_widgets import ask_two_choice
from src.ui.dialog_theme import ITEM_VIEW_STYLESHEET, apply_dialog_theme
from src.ui.rename_editor import RenameEditor
from src.ui.run_dialogs import (
    DANGER_TIER,
    GHOST,
    PRIMARY,
    SavePartialDialog,
    TestCompleteDialog,
    _ChoiceDialog,
)
from src.ui.wtmh_theme import BACKGROUND, INK, PANEL_BG, SOFT_ACCENT, STYLESHEET


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dark_mode(qapp):
    """What Qt hands every widget on a machine in Windows dark mode: a dark application
    palette (the values of Fusion's dark variant on the lab laptop)."""
    saved = QPalette(qapp.palette())
    dark = QPalette(saved)
    for role, color in (
        (QPalette.ColorRole.Window, "#323232"),
        (QPalette.ColorRole.Base, "#242424"),
        (QPalette.ColorRole.AlternateBase, "#2b2b2b"),
        (QPalette.ColorRole.Button, "#323232"),
        (QPalette.ColorRole.WindowText, "#ffffff"),
        (QPalette.ColorRole.Text, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#ffffff"),
    ):
        dark.setColor(role, QColor(color))
    qapp.setPalette(dark)
    yield dark
    qapp.setPalette(saved)


def lightness(color: QColor) -> int:
    return QColor(color).lightness()


def mean_lightness(image: QImage, left: int, top: int, width: int, height: int) -> float:
    """Mean lightness (0-255) of a rectangle of ``image``."""
    total = count = 0
    for y in range(top, top + height, 2):
        for x in range(left, left + width, 2):
            total += image.pixelColor(x, y).lightness()
            count += 1
    return total / count


def shown(widget: QWidget) -> QImage:
    widget.show()
    QApplication.processEvents()
    return widget.grab().toImage()


# -- the helper ---------------------------------------------------------------------------------


def test_apply_dialog_theme_sets_the_scope_name_and_the_sheets(qapp):
    dialog = QDialog()
    apply_dialog_theme(dialog, "QLabel#x { color: red; }")
    assert dialog.objectName() == "wtmhDashboard"
    sheet = dialog.styleSheet()
    assert sheet.startswith(STYLESHEET) and ITEM_VIEW_STYLESHEET in sheet
    assert sheet.endswith("QLabel#x { color: red; }")


def test_an_item_view_nobody_named_is_light_too_in_a_themed_dialog(qapp, dark_mode):
    """The catch-all rule: a tree (no rule of its own) is a white base, not the palette's."""
    dialog = QDialog()
    apply_dialog_theme(dialog)
    layout = QVBoxLayout(dialog)
    tree = QTreeWidget()
    layout.addWidget(tree)
    shown(dialog)
    assert tree.viewport().palette().color(tree.viewport().backgroundRole()) == QColor(PANEL_BG)


# -- the Add New Test dialog (the near-black list) --------------------------------------------------


def test_the_add_test_list_is_light_with_dark_names_on_a_dark_palette(qapp, dark_mode):
    dialog = AddTestDialog()
    dialog.select_task("click_grid")
    image = shown(dialog)
    task_list = dialog.task_list
    # The view's base colour, the colour its rows are painted on.
    viewport = task_list.viewport()
    assert viewport.palette().color(viewport.backgroundRole()) == QColor(PANEL_BG)
    # What it really paints: a light box, not near-black (near-black is mean lightness < 60).
    top_left = task_list.mapTo(dialog, task_list.rect().topLeft())
    assert mean_lightness(image, top_left.x() + 4, top_left.y() + 4, task_list.width() - 8,
                          task_list.height() - 8) > 200
    # The names are the theme's dark ink, not white on the dark base.
    for row in range(task_list.count()):
        label = task_list.itemWidget(task_list.item(row))
        assert label.palette().color(QPalette.ColorRole.WindowText) == QColor(INK)
    # The dialog itself is the page colour.
    assert image.pixelColor(2, 2) == QColor(BACKGROUND)


def test_the_chosen_add_test_row_is_the_soft_tint_not_the_dark_highlight(qapp, dark_mode):
    dialog = AddTestDialog()
    dialog.select_task("click_grid")
    image = shown(dialog)
    viewport = dialog.task_list.viewport()
    row = dialog.task_list.visualItemRect(dialog.task_list.currentItem())
    # A pixel inside the row's right-hand end (inside the visible part), away from the text. The
    # rows are spaced apart (V4): the row ends SPACING px before the viewport's edge.
    spot = viewport.mapTo(dialog, QPoint(viewport.width() - SPACING - 6, row.top() + 3))
    assert image.pixelColor(spot.x(), spot.y()) == QColor(SOFT_ACCENT)


# -- the other dialogs ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: _ChoiceDialog(None, "Q", "A question?", [("a", "Yes", PRIMARY), ("b", "No", GHOST)], "a", "b"),
        lambda: _ChoiceDialog(None, "Q", "Sure?", [("d", "Delete", DANGER_TIER), ("k", "Keep", PRIMARY)], "k", "k"),
        lambda: TestCompleteDialog(),
        lambda: SavePartialDialog(3),
        lambda: ConfigNameDialog("Save these settings as:", "Custom 1"),
    ],
    ids=["choice", "danger", "test-complete", "save-partial", "config-name"],
)
def test_every_question_dialog_is_light_on_a_dark_palette(qapp, dark_mode, make):
    dialog = make()
    image = shown(dialog)
    assert dialog.objectName() == "wtmhDashboard"
    assert image.pixelColor(2, 2) == QColor(BACKGROUND)
    assert mean_lightness(image, 0, 0, image.width(), image.height()) > 200
    # A button the theme leaves transparent (the ghost tier) shows the page colour, not
    # the dark grey of the application palette (the message box's buttons did).
    for button in dialog.findChildren(QPushButton, "wtmhGhost"):
        inside = button.mapTo(dialog, QPoint(8, button.height() // 2))
        assert lightness(image.pixelColor(inside.x(), inside.y())) > 200


def test_the_in_place_rename_popup_is_light_on_a_dark_palette_inside_the_dashboard(qapp, dark_mode):
    """The popup sits under the dashboard's sheet, which colours its text box."""
    page = QWidget()
    page.setObjectName("wtmhDashboard")
    page.setStyleSheet(STYLESHEET)
    editor = RenameEditor("Grid Click 1", ["Grid Click 1"], parent=page)
    editor.ensurePolished()
    editor.line_edit.ensurePolished()
    assert lightness(editor.palette().color(QPalette.ColorRole.Window)) > 200
    assert editor.line_edit.palette().color(QPalette.ColorRole.Base) == QColor(PANEL_BG)
    assert editor.line_edit.palette().color(QPalette.ColorRole.Text) == QColor(INK)


# -- the two-button question of the configuration page --------------------------------------------------------


def test_ask_two_choice_is_the_dashboards_choice_dialog_with_the_safe_answer_as_default(qapp, monkeypatch):
    calls = []

    def fake(parent, title, text, buttons, default, on_close):
        calls.append((parent, title, text, buttons, default, on_close))
        return "reject"

    monkeypatch.setattr(config_widgets, "ask_choice", fake)
    parent = QWidget()
    assert ask_two_choice(parent, "Discard changes", "Discard your changes?", "Discard", "Keep editing",
                          default_accept=False) is False
    assert calls[-1] == (
        parent, "Discard changes", "Discard your changes?",
        [("accept", "Discard", GHOST), ("reject", "Keep editing", PRIMARY)], "reject", "reject",
    )
    # The default is the primary button; Esc is always the reject answer.
    ask_two_choice(parent, "T", "Q", "Yes", "No")
    assert calls[-1][3:] == ([("accept", "Yes", PRIMARY), ("reject", "No", GHOST)], "accept", "reject")
    monkeypatch.setattr(config_widgets, "ask_choice", lambda *a: "accept")
    assert ask_two_choice(parent, "T", "Q", "Yes", "No") is True


def test_the_real_two_button_question_is_light_on_a_dark_palette_and_answers(qapp, dark_mode):
    seen = []

    def press():
        box = QApplication.activeModalWidget()
        if box is None:  # not open yet: look again shortly
            QTimer.singleShot(5, press)
            return
        image = box.grab().toImage()
        seen.append((type(box), image.pixelColor(2, 2), box.buttons["accept"].text()))
        box.buttons["accept"].click()

    QTimer.singleShot(0, press)
    assert ask_two_choice(None, "Delete", "Delete it?", "Delete", "Keep") is True
    assert len(seen) == 1
    kind, corner, accept_label = seen[0]
    assert kind is _ChoiceDialog and corner == QColor(BACKGROUND) and accept_label == "Delete"


def test_no_ui_module_uses_a_message_box():
    """The QMessageBox took none of the theme live (dark body, dark grey buttons), so the
    dashboard asks its questions with its own dialogs only."""
    ui = Path(__file__).resolve().parents[1] / "src" / "ui"
    users = [p.name for p in sorted(ui.glob("*.py")) if "QMessageBox" in p.read_text(encoding="utf-8")]
    assert users == []
