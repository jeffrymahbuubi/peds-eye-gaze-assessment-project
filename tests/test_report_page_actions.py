"""The report page's edits and footer (SPEC-compass-task-flow.md 4D.2, 4D.8; AD11, AD12
on the page's side; the PDF itself is in test_report_pdf.py): Save & Continue, Cancel,
the Test Name rules, Print Report. Offscreen Qt; no modal dialog is opened (the PDF path
chooser is replaced)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import src.ui.report_page as report_page_module
from src.ui.report_format import pdf_default_name
from src.ui.report_page import SUMMARY, ReportPage
from tests.report_ui_fixtures import folder_report

REACTION_COLUMN = 5


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_page(tmp_path, *, planned=6, **kw) -> ReportPage:
    page = ReportPage()
    page.set_report(folder_report(tmp_path, planned=planned), test_name=kw.pop("test_name", "Grid Click 1"), **kw)
    page.show()
    QCoreApplication.processEvents()
    return page


def column(page: ReportPage, c: int) -> list[str]:
    table = page.detailed.table
    return [table.item(r, c).text() for r in range(table.rowCount())]


def shown_trials(page: ReportPage) -> list[str]:
    return column(page, 0)


# -- Save & Continue and Cancel (AD11) -----------------------------------------------------------------------


def test_save_emits_the_three_edited_fields_and_cancel_emits_nothing_else(qapp, tmp_path):
    page = make_page(tmp_path, evaluator="Dr. Lin", notes="old")
    saved, cancelled = [], []
    page.saved.connect(lambda *a: saved.append(a))
    page.cancelRequested.connect(lambda: cancelled.append(True))
    page.name_edit.setText("  Renamed test  ")
    page.evaluator_edit.setText(" Dr. Chen ")
    page.notes_edit.setPlainText("Good attention\nfor the first 10 trials")
    assert page.is_dirty()
    page.save_button.click()
    assert saved == [("Renamed test", "Dr. Chen", "Good attention\nfor the first 10 trials")]
    assert cancelled == []
    page.cancel_button.click()
    assert cancelled == [True] and len(saved) == 1


def test_cancel_does_not_save_and_the_edits_are_dropped_on_the_next_report(qapp, tmp_path):
    page = make_page(tmp_path, evaluator="Dr. Lin")
    saved = []
    page.saved.connect(lambda *a: saved.append(a))
    page.evaluator_edit.setText("someone else")
    page.cancel_button.click()
    assert saved == []
    page.set_report(folder_report(tmp_path / "again"), test_name="Grid Click 1", evaluator="Dr. Lin")
    assert page.evaluator_edit.text() == "Dr. Lin" and not page.is_dirty()


def test_a_clean_page_is_not_dirty_and_mark_clean_takes_the_current_values(qapp, tmp_path):
    page = make_page(tmp_path)
    assert not page.is_dirty()
    page.notes_edit.setPlainText("x")
    assert page.is_dirty()
    page.mark_clean()
    assert not page.is_dirty()
    page.notes_edit.setPlainText("")
    assert page.is_dirty()


def test_the_run_data_is_unchanged_by_editing_the_fields(qapp, tmp_path):
    page = make_page(tmp_path)
    before = (page.summary.table.texts(), column(page, 3), page.config_table.texts())
    page.name_edit.setText("Something else")
    page.notes_edit.setPlainText("notes")
    assert (page.summary.table.texts(), column(page, 3), page.config_table.texts()) == before


def test_collect_edits_trims_the_name_and_evaluator_only(qapp, tmp_path):
    page = make_page(tmp_path)
    page.name_edit.setText(" A ")
    page.evaluator_edit.setText(" B ")
    page.notes_edit.setPlainText(" C \n")
    assert page.collect_edits() == {"test_name": "A", "evaluator": "B", "notes": " C \n"}


@pytest.mark.parametrize(
    ("name", "fragment"),
    [("", "Enter a test name"), ("   ", "Enter a test name"), ("x" * 61, "at most 60"),
     ("grid click 2", "already exists")],
)
def test_save_is_disabled_for_a_bad_test_name_with_the_reason_in_the_footer(qapp, tmp_path, name, fragment):
    page = make_page(tmp_path)
    page.set_context(existing_test_names=["Grid Click 1", "Grid Click 2"])
    page.name_edit.setText(name)
    assert not page.save_button.isEnabled()
    assert fragment in page.footer_message.text()
    assert page.save_problem() is not None
    saved = []
    page.saved.connect(lambda *a: saved.append(a))
    page.save_button.click()  # disabled: nothing happens
    page._on_save()  # and the handler itself refuses
    assert saved == []


def test_the_tests_own_name_is_not_a_duplicate_and_a_fixed_name_enables_save_again(qapp, tmp_path):
    page = make_page(tmp_path)
    page.set_context(existing_test_names=["Grid Click 1", "Grid Click 2"])
    assert page.save_button.isEnabled() and page.footer_message.text() == ""  # its own name
    page.name_edit.setText("GRID CLICK 1")  # only the case changed
    assert page.save_button.isEnabled()
    page.name_edit.setText("Grid Click 2")
    assert not page.save_button.isEnabled()
    page.name_edit.setText("Grid Click 3")
    assert page.save_button.isEnabled() and page.footer_message.text() == ""


def test_the_enter_key_never_saves(qapp, tmp_path):
    page = make_page(tmp_path)
    saved = []
    page.saved.connect(lambda *a: saved.append(a))
    for button in (page.print_button, page.toggle_button, page.save_button, page.cancel_button):
        assert not button.autoDefault()
    QTest.keyClick(page.name_edit, Qt.Key.Key_Return)
    assert saved == []


def test_an_empty_page_has_save_disabled_and_nothing_selected(qapp):
    page = ReportPage()
    assert not page.save_button.isEnabled()
    assert page.selected_trial() is None and page.view_mode == SUMMARY


def test_a_report_with_no_trials_gives_an_empty_table_and_no_error(qapp):
    page = ReportPage()
    page.set_report({"session": {"task_id": "click_grid"}, "trials": []}, test_name="Nothing")
    assert page.detailed.table.rowCount() == 0 and page.selected_trial() is None
    assert page.detailed.selected_title.text() == "Selected trial"
    page.show_detailed()
    page.detailed.table.sortRequested.emit(1)  # sorting nothing is fine


def test_a_new_report_resets_the_view_the_sort_and_the_selection(qapp, tmp_path):
    page = make_page(tmp_path / "a")
    page.show_detailed()
    page.detailed.table.sortRequested.emit(REACTION_COLUMN)
    page.detailed.table.setCurrentCell(4, 0)
    page.set_report(folder_report(tmp_path / "b"), test_name="Second")
    assert page.view_mode == SUMMARY and page.selected_trial() == 0
    assert page.detailed.table.horizontalHeader().sortIndicatorSection() == -1
    assert shown_trials(page) == ["1", "2", "3", "4", "5", "6"]


# -- Print Report (AD12 on the page's side; the PDF itself is in test_report_pdf.py) -------------------------


def test_print_report_asks_for_a_path_starting_from_the_default_name_and_writes_the_pdf(qapp, tmp_path):
    page = make_page(tmp_path / "data")
    page.set_context(pdf_dir=tmp_path / "subject")
    asked, exported = [], []
    target = tmp_path / "out.pdf"

    def choose(default: str) -> str:
        asked.append(default)
        return str(target)

    page.choose_pdf_path = choose
    page.pdfExported.connect(exported.append)
    page.print_button.click()
    expected = pdf_default_name("Grid Click 1", page._report["session"]["started_ns"])
    assert asked == [str(tmp_path / "subject" / expected)]
    assert (tmp_path / "subject").is_dir()  # the reports folder is made when a PDF is first asked for
    assert target.read_bytes().startswith(b"%PDF")
    assert exported == [str(target)]
    assert str(target) in page.footer_message.text()


def test_print_report_without_a_folder_offers_just_the_file_name(qapp, tmp_path):
    page = make_page(tmp_path)
    asked = []
    page.choose_pdf_path = lambda default: asked.append(default) or ""
    page.print_button.click()
    assert asked == [pdf_default_name("Grid Click 1", page._report["session"]["started_ns"])]


def test_the_file_name_uses_the_name_typed_on_the_page(qapp, tmp_path):
    page = make_page(tmp_path)
    asked = []
    page.choose_pdf_path = lambda default: asked.append(default) or ""
    page.name_edit.setText("My renamed test")
    page.print_button.click()
    assert asked[0].endswith("_My renamed test.pdf") and "P001" not in asked[0]


def test_cancelling_the_file_chooser_writes_nothing(qapp, tmp_path):
    page = make_page(tmp_path / "data")
    exported = []
    page.pdfExported.connect(exported.append)
    page.choose_pdf_path = lambda default: ""
    page.print_button.click()
    assert exported == [] and not list((tmp_path).glob("*.pdf"))
    assert page.footer_message.text() == ""


def test_a_pdf_that_cannot_be_written_says_so_in_the_footer_and_does_not_crash(qapp, tmp_path):
    page = make_page(tmp_path / "data")
    exported = []
    page.pdfExported.connect(exported.append)
    page.choose_pdf_path = lambda default: str(tmp_path / "no" / "such" / "folder" / "r.pdf")
    page.print_button.click()
    assert exported == []
    assert page.footer_message.text().startswith("The PDF could not be written")
    page.name_edit.setText("typing clears the note")
    assert not page.footer_message.text().startswith("The PDF could not")


def test_the_pdf_is_made_from_the_edited_fields_and_the_targets_only_map(qapp, tmp_path, monkeypatch):
    page = make_page(tmp_path, evaluator="Dr. Lin", notes="old notes")
    page.summary.path_check.setChecked(True)
    page.summary.heat_check.setChecked(True)
    page.show_detailed()
    page.detailed.table.setCurrentCell(2, 0)  # the pane's trial must not leak into the PDF's map
    seen = {}

    def fake_export(path, report, **kwargs):
        seen.update(kwargs, path=path)
        return path

    monkeypatch.setattr(report_page_module, "export_report_pdf", fake_export)
    page.name_edit.setText("Edited name")
    page.evaluator_edit.setText("Dr. Chen")
    page.notes_edit.setPlainText("new notes")
    page.export_pdf(tmp_path / "x.pdf")
    assert (seen["test_name"], seen["evaluator"], seen["notes"]) == ("Edited name", "Dr. Chen", "new notes")
    image = seen["map_image"]
    assert image.width() == report_page_module.PDF_MAP_WIDTH_PX
    assert page.summary.map.overlays() == {"targets": True, "path": True, "heat": True}  # untouched
    assert page.summary.map.trial() is None and page.detailed.map.trial() == 2


def test_text_typed_by_the_operator_is_shown_as_typed_not_as_markup(qapp, tmp_path):
    page = ReportPage()
    report = folder_report(tmp_path)
    report["session"]["config_name"] = "<i>Big</i> & bold"
    page.set_report(report, test_name="T", subject="<b>S</b>")
    assert "&lt;b&gt;S&lt;/b&gt;" in page.subject_label.text()
    assert "&lt;i&gt;Big&lt;/i&gt; &amp; bold" in page.config_name_label.text()
    page.set_context(existing_test_names=["<b>x</b>"])
    page.name_edit.setText("<b>x</b>")
    assert page.footer_message.textFormat() == Qt.TextFormat.PlainText
    assert "<b>x</b>" in page.footer_message.text()  # the reason names the test, literally


# -- show_note: a line from the host (a failed save) -----------------------------------------------------


def test_the_host_can_put_a_line_in_the_footer_and_the_next_edit_clears_it(qapp, tmp_path):
    page = make_page(tmp_path)
    page.show_note("Could not save: disk full")
    assert page.footer_message.text() == "Could not save: disk full"
    assert page.save_button.isEnabled()  # a failed write does not stop another try
    page.notes_edit.setPlainText("typed again")
    assert page.footer_message.text() == ""


def test_a_test_name_problem_outranks_the_hosts_note(qapp, tmp_path):
    page = make_page(tmp_path)
    page.show_note("Could not save: disk full")
    page.name_edit.setText("")
    assert page.footer_message.text() != "Could not save: disk full"
    assert not page.save_button.isEnabled()
