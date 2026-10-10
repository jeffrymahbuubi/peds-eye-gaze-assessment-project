"""SPEC-design-system-phase2.md H13, Q9: the three bugs of the phase-1 live check, as far as a test
can see them. (1) No native focus rectangle inside a button's 2 px focus border: every QSS rule
of a focusable operator control says ``outline: 0`` (the rectangle itself is drawn by the
Windows platform style and does not appear offscreen, so the window capture of Q9 is the hub's).
(2) Tab leaves a multi-line edit instead of typing a tab. (3) The PRACTICE / PREVIEW chip of the
run bar is a fixed 24 px pill, centred (tested with the bar in ``test_run_bar.py``). Offscreen Qt."""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

from src.ui import design_tokens as tokens
from src.ui.report_page import ReportPage
from src.ui.run_dialogs import _DANGER_STYLE
from src.ui.setup_page import SetupPage
from src.ui.wtmh_theme import STYLESHEET, button_rule


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def block_of(sheet: str, selector: str) -> str:
    """The declarations of every rule (not a :hover or :focus state of it) whose selector list
    holds ``selector``, joined; comments are ignored."""
    sheet = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", sheet):
        if selector in [s.strip() for s in match.group(1).split(",")]:
            found.append(match.group(2))
    assert found, f"no rule for {selector}"
    return "\n".join(found)


# -- (1) outline: 0 -----------------------------------------------------------------------------------


def test_button_rule_takes_the_native_focus_rectangle_out_of_every_tier():
    rule = button_rule(("QPushButton#a", "QPushButton#b"), text="#000", fill="#fff", border="#000", hover_fill="#eee")
    for selector in ("QPushButton#a", "QPushButton#b"):
        base = block_of(rule, selector)
        assert "outline: 0;" in base
        assert "min-height" in base and "font-weight: 600" in base  # it is the tier's base rule
    # and the 2 px focus border it protects is still there
    assert f"border: {tokens.FOCUS_BORDER_WIDTH}px solid {tokens.ACCENT_FOCUS}" in rule


@pytest.mark.parametrize(
    "selector",
    [
        "QPushButton#wtmhPrimary", "QPushButton#cfgSave", "QPushButton#wtmhSecondary", "QPushButton#wtmhGhost",
        "QPushButton#cfgPreview", "QPushButton#cfgCancel", "QPushButton#cfgReset", "QPushButton#wtmhTertiary",
    ],
)
def test_every_button_tier_of_the_dashboard_sheet_says_outline_0(selector):
    assert "outline: 0;" in block_of(STYLESHEET, selector)


def test_the_run_end_dialogs_danger_tier_is_built_from_the_same_rule():
    assert "outline: 0;" in block_of(_DANGER_STYLE, "QPushButton#runDlgDanger")


@pytest.mark.parametrize(
    "selector",
    [
        "QPushButton#wtmhNavButton",
        "QWidget#wtmhDashboard QLineEdit", "QWidget#wtmhDashboard QComboBox", "QWidget#wtmhDashboard QDateEdit",
        "QWidget#wtmhDashboard QSpinBox", "QWidget#wtmhDashboard QDoubleSpinBox",
        "QWidget#wtmhDashboard QTextEdit", "QWidget#wtmhDashboard QPlainTextEdit",
        "QWidget#wtmhDashboard QCheckBox", "QWidget#wtmhDashboard QRadioButton",
        "QWidget#wtmhDashboard QSlider:horizontal", "QWidget#wtmhDashboard QTableWidget",
    ],
)
def test_every_other_focusable_control_of_the_sheet_says_outline_0_too(selector):
    assert "outline: 0;" in block_of(STYLESHEET, selector)


# -- (2) Tab in a multi-line edit ----------------------------------------------------------------------------


def test_every_multi_line_edit_of_the_operator_pages_lets_tab_through(qapp):
    setup = SetupPage()
    assert isinstance(setup.notes_edit, QTextEdit) and setup.notes_edit.tabChangesFocus()
    report = ReportPage()
    assert isinstance(report.notes_edit, QPlainTextEdit) and report.notes_edit.tabChangesFocus()
    # (the configuration page's Notes box is in test_config_page_phase2.py)


def test_no_operator_page_builds_a_multi_line_edit_without_it():
    """A new QTextEdit / QPlainTextEdit in an operator page file must come with setTabChangesFocus."""
    from pathlib import Path

    ui = Path(__file__).resolve().parents[1] / "src" / "ui"
    for name in ("setup_page.py", "config_form.py", "report_page.py", "start_test_page.py", "test_list_page.py"):
        source = (ui / name).read_text(encoding="utf-8")
        built = len(re.findall(r"=\s*Q(?:Plain)?TextEdit\(", source))
        assert source.count("setTabChangesFocus(True)") >= built, name
