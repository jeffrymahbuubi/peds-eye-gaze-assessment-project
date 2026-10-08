"""The phase-1 ``wtmhMuted`` bug, fixed in phase 2 by the user's decision (SPEC-design-system-
phase2.md section 9, 2026-10-09): ``QWidget#wtmhDashboard QLabel`` sets the ink colour with two
type names and an id, which outweighed ``QLabel#wtmhMuted``, so every muted label rendered in ink.
These tests pin the colour that really renders, by pixel and by the resolved palette, on the
dashboard sheet; and that no label that should be ink turned grey. Offscreen Qt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QStyleFactory, QVBoxLayout, QWidget

from src.engine.config import load_task_config
from src.engine.subject_tests import create_test
from src.ui import design_tokens as tokens
from src.ui.config_save_dialogs import ConfigNameDialog
from src.ui.report_page import ReportPage
from src.ui.setup_page import SetupPage
from src.ui.start_test_page import StartTestPage
from src.ui.task_config_page import TaskConfigPage
from src.ui.test_list_page import SubjectTestListPage
from src.ui.wtmh_theme import STYLESHEET
from tests.report_ui_fixtures import folder_report

SECONDARY_NAMES = {"wtmhMuted", "wtmhCaption", "cfgAdvancedTitle"}  # the labels the sheet greys


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))  # the dashboard's own style (run_dashboard)
    return app


def themed(*widgets: QWidget) -> QWidget:
    """A ``wtmhDashboard`` root with the sheet, as the dashboard's central widget is."""
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    layout = QVBoxLayout(root)
    for widget in widgets:
        layout.addWidget(widget)
    return root


def text_colour(label: QLabel) -> str:
    """The colour the label's text is drawn in: the resolved palette (after the sheet is applied)."""
    label.ensurePolished()
    return label.palette().color(QPalette.ColorRole.WindowText).name().lower()


def darkest_pixel(label: QLabel) -> str:
    image = label.grab().toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return min(pixels, key=lambda colour: colour.lightness()).name().lower()


def make_label(name: str, text: str = "Helper text") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


# -- the colour that renders --------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SECONDARY_NAMES))
def test_a_muted_label_renders_text_secondary_on_the_dashboard(qapp, name):
    label = make_label(name)
    root = themed(label)
    root.show()
    QApplication.processEvents()
    assert text_colour(label) == tokens.TEXT_SECONDARY.lower()
    assert darkest_pixel(label) == tokens.TEXT_SECONDARY.lower()  # and that is what is painted
    root.close()


@pytest.mark.parametrize("name", ["", "wtmhPageTitle", "wtmhSectionTitle"])
def test_other_labels_stay_ink(qapp, name):
    label = make_label(name)
    root = themed(label)
    root.show()
    QApplication.processEvents()
    assert text_colour(label) == tokens.INK.lower()
    assert darkest_pixel(label) == tokens.INK.lower()
    root.close()


def test_the_old_selector_alone_rendered_ink_which_is_what_these_tests_catch(qapp):
    """The phase-1 sheet, rebuilt: a bare ``QLabel#wtmhMuted`` loses to the dashboard's label rule."""
    old_sheet = STYLESHEET.replace("QLabel#wtmhMuted, QWidget#wtmhDashboard QLabel#wtmhMuted", "QLabel#wtmhMuted")
    assert old_sheet != STYLESHEET
    label = make_label("wtmhMuted")
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(old_sheet)
    QVBoxLayout(root).addWidget(label)
    root.show()
    assert text_colour(label) == tokens.INK.lower()  # the bug
    root.close()


def test_a_disabled_muted_label_is_the_disabled_grey_not_secondary(qapp):
    label = make_label("wtmhMuted")
    label.setEnabled(False)
    root = themed(label)
    root.show()
    QApplication.processEvents()
    assert text_colour(label) == tokens.TEXT_DISABLED.lower()
    root.close()


def test_a_muted_label_outside_the_dashboard_scope_is_still_secondary(qapp):
    """The bare ``QLabel#wtmhMuted`` selector stays, for a sheet used without the scope name."""
    label = make_label("wtmhMuted")
    root = QWidget()
    root.setStyleSheet(STYLESHEET)
    QVBoxLayout(root).addWidget(label)
    root.show()
    assert text_colour(label) == tokens.TEXT_SECONDARY.lower()
    root.close()


def test_the_title_bar_text_is_still_white(qapp):
    """``QWidget#wtmhTitleBar QLabel`` ties with the dashboard rule and wins by coming later."""
    bar = QWidget()
    bar.setObjectName("wtmhTitleBar")
    label = make_label("wtmhBrandTitle", "Pediatric Eye-Gaze Assessment")
    QVBoxLayout(bar).addWidget(label)
    root = themed(bar)
    root.show()
    assert text_colour(label) == tokens.TITLE_BAR_TEXT.lower()
    root.close()


# -- every page: the muted labels are grey and nothing else is -----------------------------------------------


def sweep(page: QWidget, where: str) -> list[tuple[str, str]]:
    """Check every label of ``page`` on the dashboard sheet; returns the grey ones as
    ``(object name, text)`` (the page is gone with its root when this returns)."""
    root = themed(page)
    root.show()
    QApplication.processEvents()
    grey = []
    for label in page.findChildren(QLabel):
        colour = text_colour(label)
        secondary = colour == tokens.TEXT_SECONDARY.lower()
        if label.objectName() in SECONDARY_NAMES and label.isEnabled():
            assert secondary, f"{where}: {label.objectName()} '{label.text()[:30]}' renders {colour}"
            grey.append((label.objectName(), label.text()))
        else:
            assert not secondary, f"{where}: '{label.text()[:30]}' ({label.objectName()!r}) turned grey"
    root.close()
    return grey


def test_setup_page(qapp):
    grey = sweep(SetupPage(), "Setup")
    names = {name for name, _text in grey}
    assert "wtmhMuted" in names and "wtmhCaption" in names  # the hint, the device line, the footer caption
    assert ("wtmhMuted", "Use a study code, not the child's name.") in grey


def test_test_list_page(qapp, tmp_path):
    root = tmp_path / "sessions"
    create_test(root, "TESTING", "click_grid")
    page = SubjectTestListPage()
    page.set_subject("TESTING", root)
    page.show_message("Could not do that.")
    grey = sweep(page, "Test List")
    assert ("wtmhMuted", "Could not do that.") in grey  # a muted line under the table
    assert ("wtmhMuted", "Changes are saved automatically.") in grey


def test_the_empty_test_list(qapp, tmp_path):
    page = SubjectTestListPage()
    page.set_subject("NOBODY", tmp_path / "sessions")
    assert ("wtmhMuted", "No tests yet. Choose Add New Test.") in sweep(page, "empty Test List")


def test_start_page(qapp):
    page = StartTestPage()
    cfg = load_task_config("click_grid")
    cfg["task"]["trials"] = 18
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    page.show_note("Could not start Grid Click 1: no.")
    grey = sweep(page, "Start")
    assert ("wtmhMuted", "Could not start Grid Click 1: no.") in grey


@pytest.mark.parametrize("task_id", ["click_grid", "follow_moving"])
def test_configuration_page(qapp, task_id):
    page = TaskConfigPage(task_id, load_task_config(task_id))
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name="Test 1")
    page._form.controls["trials"].setValue(7)  # the "Changed from ..." caption has text
    grey = sweep(page, f"configuration {task_id}")
    assert ("wtmhCaption", "Changed from Standard") in grey
    assert ("cfgAdvancedTitle", "Advanced") in grey
    assert any(name == "wtmhMuted" and "TESTING" in text for name, text in grey)  # the subtitle


def test_report_page(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    grey = sweep(page, "report")
    assert grey  # its muted lines (the plain-text helper lines of the sidebar and the metrics)


def test_the_save_as_dialog(qapp):
    dialog = ConfigNameDialog("Save these settings as:", "Custom 1")
    dialog.name_edit.setText("Standard")  # a name that is refused: the muted reason shows
    dialog.show()
    QApplication.processEvents()
    assert dialog.error_label.isVisible()
    assert text_colour(dialog.error_label) == tokens.TEXT_SECONDARY.lower()
    for label in (dialog.heading_label, dialog.intro_label):
        assert text_colour(label) == tokens.INK.lower()
    dialog.close()


def test_the_secondary_colour_is_readable_on_the_page_and_on_a_card():
    from tests.colour_helpers import contrast

    for background in (tokens.PAGE, tokens.PANEL):
        assert contrast(QColor(tokens.TEXT_SECONDARY), QColor(background)) >= 4.5
