"""SPEC-subject-data-layout.md H6, D4, W1 (L4, L5): the Setup page's folder-name choice under
Subject ID. A new Subject ID offers ``Folder name: (*) Subject ID ( ) Anonymous code (S-000N)``;
an existing one shows one muted read-only line instead. Offscreen Qt, a scratch folder."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.engine.calibration import CalibrationResult
from src.engine.subject_store import ensure_subject
from src.ui.setup_page import SetupPage, _latest_subject_calibration
from src.ui.subject_folder_row import CODE_TOOLTIP


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the page's output root is the relative "sessions"
    return SetupPage()


def type_id(page, text):
    page.subject_id_edit.setText(text)
    return page.folder_row


def choice_shown(row) -> bool:
    return not row.choice.isHidden()


def line_shown(row) -> bool:
    return not row.folder_label.isHidden()


# -- the states -----------------------------------------------------------------------------------


def test_with_no_subject_id_nothing_shows(page):
    row = page.folder_row
    assert not choice_shown(row) and not line_shown(row)
    type_id(page, "   ")
    assert not choice_shown(row) and not line_shown(row)


def test_a_new_subject_id_shows_the_choice_with_subject_id_selected(page):
    row = type_id(page, "Maria")
    assert choice_shown(row) and not line_shown(row)
    assert row.id_radio.text() == "Subject ID" and row.id_radio.isChecked()
    assert row.code_radio.text() == "Anonymous code (S-0001)" and not row.code_radio.isChecked()
    assert page.folder_mode() == "id"


def test_the_code_label_and_tooltip_show_the_code_that_would_be_assigned(page):
    ensure_subject(page.output_root, "Early", "code")
    ensure_subject(page.output_root, "Second", "code")
    ensure_subject(page.output_root, "Third", "code")
    row = type_id(page, "Maria")
    assert row.code_radio.text() == "Anonymous code (S-0004)"
    assert row.code_radio.toolTip() == (
        "The folder is named S-0004 instead of the Subject ID, so Explorer and zip file names "
        "do not show it. The files inside still contain the Subject ID."
    )
    assert CODE_TOOLTIP.format(code="S-0004") == row.code_radio.toolTip()


def test_picking_anonymous_code_is_what_folder_mode_reports(page):
    row = type_id(page, "Maria")
    row.code_radio.setChecked(True)
    assert page.folder_mode() == "code" and not row.id_radio.isChecked()
    row.id_radio.setChecked(True)
    assert page.folder_mode() == "id"


def test_the_choice_is_kept_while_the_id_is_edited(page):
    row = type_id(page, "Mar")
    row.code_radio.setChecked(True)
    type_id(page, "Maria")
    assert row.code_radio.isChecked() and choice_shown(row)


def test_an_existing_subject_id_shows_one_read_only_line_instead(page):
    ensure_subject(page.output_root, "P9REAL")
    row = type_id(page, "P9REAL")
    assert line_shown(row) and not choice_shown(row)
    assert row.folder_label.text() == "Folder: P9REAL (Subject ID)"


def test_an_existing_anonymous_subject_shows_its_code(page):
    ensure_subject(page.output_root, "Early", "code")
    ensure_subject(page.output_root, "Second", "code")
    ensure_subject(page.output_root, "Maria", "code")
    row = type_id(page, "Maria")
    assert row.folder_label.text() == "Folder: S-0003 (Anonymous code)"
    assert not choice_shown(row)


def test_the_match_ignores_case_so_ana_and_ana_in_capitals_are_one_subject(page):
    ensure_subject(page.output_root, "Ana")
    row = type_id(page, "ANA")
    assert row.folder_label.text() == "Folder: Ana (Subject ID)" and not choice_shown(row)


def test_only_one_of_the_two_states_is_ever_visible(page):
    ensure_subject(page.output_root, "Known")
    row = page.folder_row
    for text in ("", "New", "Known", "known", "Newer", " "):
        type_id(page, text)
        assert not (choice_shown(row) and line_shown(row))


def test_leaving_a_known_id_for_a_new_one_brings_the_choice_back(page):
    ensure_subject(page.output_root, "Known")
    row = type_id(page, "Known")
    assert line_shown(row)
    type_id(page, "Someone else")
    assert choice_shown(row) and not line_shown(row)


# -- the first save of anything fixes the choice ------------------------------------------------------


def saved_page(page, subject, mode_code: bool):
    page._calibration_result = CalibrationResult(n_points=5, mean_error_px=10.0, valid=True)
    row = type_id(page, subject)
    if mode_code:
        row.code_radio.setChecked(True)
    page._on_state_changed()
    return row


def test_save_calibration_in_code_mode_makes_the_code_folder_and_fixes_the_choice(page, tmp_path):
    row = saved_page(page, "Maria Lopez", mode_code=True)
    page.save_calibration_button.click()
    folder = tmp_path / "sessions" / "S-0001"
    assert (folder / "calibrations" / "calibration_5pt.json").is_file()
    assert (folder / "subject.json").is_file()
    assert [p.name for p in (tmp_path / "sessions").iterdir() if p.name != "_system"] == ["S-0001"]
    assert not choice_shown(row) and row.folder_label.text() == "Folder: S-0001 (Anonymous code)"
    assert not any("maria" in p.name.casefold() for p in (tmp_path / "sessions").rglob("*"))  # L5


def test_save_calibration_in_the_default_mode_names_the_folder_after_the_id(page, tmp_path):
    row = saved_page(page, "P9REAL", mode_code=False)
    page.save_calibration_button.click()
    assert (tmp_path / "sessions" / "P9REAL" / "calibrations" / "calibration_5pt.json").is_file()
    assert row.folder_label.text() == "Folder: P9REAL (Subject ID)"
    assert page._subject_completer_model.stringList() == ["P9REAL"]


def test_saving_again_keeps_the_first_choice(page, tmp_path):
    row = saved_page(page, "Maria", mode_code=True)
    page.save_calibration_button.click()
    page._calibration_result = CalibrationResult(n_points=9, mean_error_px=12.0, valid=True)
    page.save_calibration_button.click()
    folder = tmp_path / "sessions" / "S-0001"
    assert sorted(p.name for p in (folder / "calibrations").iterdir()) == [
        "calibration_5pt.json",
        "calibration_9pt.json",
    ]
    assert row.folder_label.text() == "Folder: S-0001 (Anonymous code)"


def test_a_saved_calibration_is_found_again_by_the_typed_id(page):
    saved_page(page, "Maria", mode_code=True)
    page.save_calibration_button.click()
    found = _latest_subject_calibration(page.output_root, "MARIA")
    assert found is not None and found.parent.parent.name == "S-0001"


def test_a_save_that_cannot_be_written_says_so_and_changes_nothing(page, monkeypatch):
    saved_page(page, "Maria", mode_code=False)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("src.ui.setup_page.save_calibration_result", broken)
    page.save_calibration_button.click()
    assert "Could not save the calibration: disk full" in page.calibration_alert_label.text()
    assert page.folder_mode() == "id"


def test_the_completer_lists_the_ids_verbatim(page):
    ensure_subject(page.output_root, "Zoe")
    ensure_subject(page.output_root, "Ana Maria", "code")
    page.refresh_subject_completer()
    assert page._subject_completer_model.stringList() == ["Ana Maria", "Zoe"]
