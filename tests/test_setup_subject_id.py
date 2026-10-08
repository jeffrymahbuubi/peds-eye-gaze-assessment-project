"""SPEC-subject-data-layout.md D4 revised 2026-10-08, W1, step 6 (L4, L5): the Setup page's
Subject ID field. A muted hint under it asks for a study code, not the child's name; there is
no folder-name choice, so a new subject's folder is always its Subject ID. Offscreen Qt, a
scratch folder."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QRadioButton

from src.engine.calibration import CalibrationResult
from src.engine.subject_store import ensure_subject
from src.ui.setup_page import SetupPage, _latest_subject_calibration

HINT = "Use a study code, not the child's name."


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the page's output root is the relative "sessions"
    return SetupPage()


def type_id(page, text):
    page.subject_id_edit.setText(text)


def ready_to_save(page, subject):
    page._calibration_result = CalibrationResult(n_points=5, mean_error_px=10.0, valid=True)
    type_id(page, subject)
    page._on_state_changed()


def subject_folders(tmp_path):
    return sorted(p.name for p in (tmp_path / "sessions").iterdir() if p.name != "_system")


# -- the hint ---------------------------------------------------------------------------------------


def test_setup_shows_the_study_code_hint_under_subject_id(page):
    assert page.subject_id_hint.text() == HINT
    assert page.subject_id_hint.objectName() == "wtmhMuted"  # the existing muted caption style
    form = page.subject_id_edit.parentWidget().layout().findChild(QFormLayout)
    row, role = form.getWidgetPosition(page.subject_id_edit)
    assert form.getWidgetPosition(page.subject_id_hint) == (row + 1, role)


def test_the_hint_is_always_there_whatever_is_typed(page):
    for text in ("", "   ", "P9REAL", "Maria Lopez"):
        type_id(page, text)
        assert not page.subject_id_hint.isHidden()


def test_there_is_no_folder_name_choice_and_no_folder_line(page):
    assert page.findChildren(QRadioButton) == []
    texts = [label.text() for label in page.findChildren(QLabel)]
    assert not any("Anonymous" in t or "Folder name" in t or t.startswith("Folder:") for t in texts)
    assert not hasattr(page, "folder_row") and not hasattr(page, "folder_mode")
    ensure_subject(page.output_root, "Known")
    type_id(page, "Known")  # an existing subject gets no "Folder: ..." line either
    assert not any(label.text().startswith("Folder:") for label in page.findChildren(QLabel))


# -- a new subject's folder is its Subject ID (L5) ------------------------------------------------------


def test_save_calibration_for_a_new_subject_makes_the_folder_named_after_the_id(page, tmp_path):
    ready_to_save(page, "Maria Lopez")
    page.save_calibration_button.click()
    folder = tmp_path / "sessions" / "Maria Lopez"
    assert (folder / "calibrations" / "calibration_5pt.json").is_file()
    assert json.loads((folder / "subject.json").read_text(encoding="utf-8"))["folder_mode"] == "id"
    assert subject_folders(tmp_path) == ["Maria Lopez"]  # no S-000N
    assert not (tmp_path / "sessions" / "_system" / "subject_codes.json").exists()
    assert page._subject_completer_model.stringList() == ["Maria Lopez"]


def test_saving_again_uses_the_same_folder(page, tmp_path):
    ready_to_save(page, "Maria")
    page.save_calibration_button.click()
    page._calibration_result = CalibrationResult(n_points=9, mean_error_px=12.0, valid=True)
    page.save_calibration_button.click()
    folder = tmp_path / "sessions" / "Maria"
    assert sorted(p.name for p in (folder / "calibrations").iterdir()) == [
        "calibration_5pt.json",
        "calibration_9pt.json",
    ]
    assert subject_folders(tmp_path) == ["Maria"]


def test_a_saved_calibration_is_found_again_by_the_typed_id_in_any_case(page):
    ready_to_save(page, "Maria")
    page.save_calibration_button.click()
    found = _latest_subject_calibration(page.output_root, "MARIA")
    assert found is not None and found.parent.parent.name == "Maria"


def test_a_save_that_cannot_be_written_says_so(page, monkeypatch):
    ready_to_save(page, "Maria")

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("src.ui.setup_page.save_calibration_result", broken)
    page.save_calibration_button.click()
    assert "Could not save the calibration: disk full" in page.calibration_alert_label.text()


def test_the_completer_lists_the_ids_verbatim(page):
    ensure_subject(page.output_root, "Zoe")
    ensure_subject(page.output_root, "Ana Maria")
    page.refresh_subject_completer()
    assert page._subject_completer_model.stringList() == ["Ana Maria", "Zoe"]
