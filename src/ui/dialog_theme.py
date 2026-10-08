"""The light theme of the dashboard's dialogs (SPEC-compass-task-flow.md 7.1, FX1).

``wtmh_theme.STYLESHEET`` colours the widgets it names; any other widget falls back to the
application palette, and on a machine in Windows dark mode that palette is dark (Qt follows
the OS colour scheme, and Fusion's ``standardPalette()`` follows it too, so
``run_dashboard``'s ``app.setPalette(style.standardPalette())`` is not a light palette
there). The Add New Test dialog's task list is such a widget: it painted near-black with the
theme's dark text on top of it.

A palette set on the dialog would not help: under a style sheet Qt does not propagate a
widget's palette to its children (``Qt::AA_UseStyleSheetPropagationInWidgetStyles``). What
colours a child is a rule in the sheet, so :func:`apply_dialog_theme` gives a dialog the
dashboard sheet plus the rules below for the item views a dialog may hold, whatever the OS
colour mode.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .design_tokens import BORDER_STRONG, INK, PAGE, PANEL, RADIUS, ROW_SELECTED
from .wtmh_theme import STYLESHEET

# Item views are the one kind of child the dashboard sheet does not colour (it styles tables
# and combo popups, more specifically, so those keep their own look). The first rule is the
# catch-all: any list, tree or table in a dialog gets a white base and dark text. The task
# list of the Add New Test dialog is then a white box with the chosen row in the row-selected blue.
# No ``::item`` padding: an item widget is laid out inside the item's padding box, so padding
# makes the widget shorter than the size hint the item was given and clips its last line (F6).
ITEM_VIEW_STYLESHEET = f"""
QWidget#wtmhDashboard QAbstractItemView {{ background: {PANEL}; color: {INK}; }}
QWidget#wtmhDashboard QListWidget {{
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS}px;
    outline: 0;
}}
QWidget#wtmhDashboard QListWidget::item {{ border-radius: {RADIUS}px; }}
QWidget#wtmhDashboard QListWidget::item:hover {{ background: {PAGE}; }}
QWidget#wtmhDashboard QListWidget::item:selected {{ background: {ROW_SELECTED}; color: {INK}; }}
"""


def apply_dialog_theme(dialog: QWidget, extra_style: str = "") -> None:
    """Make ``dialog`` a themed dashboard dialog: the scope name the sheet is written
    for, the dashboard sheet with the item-view rules, and ``extra_style`` (a rule only
    this dialog needs, scoped by object name)."""
    dialog.setObjectName("wtmhDashboard")
    dialog.setStyleSheet(STYLESHEET + ITEM_VIEW_STYLESHEET + extra_style)
