"""SPEC-scene-cause-effect-task.md 4.9, W6, W4, S3, S7, acceptance A7: Choice-making's report on screen
and in the PDF -- the Summary of Results with its look-back columns, the two tables under it, the Scene
Map in place of the Target Map, the Trial-by-Trial table with its look-back and waiting-phase
columns, the Test Configuration rows and the PDF. Offscreen Qt: pixels are checked by colour and
nothing measures a size, except the PDF's page and column fit, which register the real Segoe UI
(see ``tests/real_fonts.py``) and skip where it is missing."""

from __future__ import annotations

import copy
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QCoreApplication, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.data.report_cache import build_report
from src.ui import report_pdf
from src.ui.design_tokens import MAP_FIXATION, MAP_HIT_FILL, MAP_HIT_OUTLINE, MAP_MISS
from src.ui.map_legend import CHOICE_LEGEND_ENTRIES, symbol_image
from src.ui.report_format import DASH, NOT_RECORDED, task_sentence
from src.ui.report_layout import (
    CHOICE,
    SELECTION,
    layout_kind,
    map_title,
    outcome_label,
    summary_aligns,
    summary_cells,
    summary_extra_tables,
    summary_header,
    summary_info,
    summary_note,
    targets_label,
    trial_aligns,
    trial_columns,
    trial_rows,
)
from src.ui.report_page import ReportPage
from src.ui.target_map import TargetMapWidget
from tests import real_fonts
from tests.choice_report_fixtures import choice_folder, choice_meta, main_trials
from tests.report_ui_fixtures import folder_report


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def fonts(qapp):
    yield from real_fonts.segoe_ui(qapp)


def _placeholder_report(tmp_path_factory, name: str, **kwargs):
    # Built once per module, so outside conftest's per-test pin: pin it to the placeholder scene here.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.tasks.choice_scene.ASSETS_ROOT", tmp_path_factory.getbasetemp() / "no_scene_assets")
        return build_report(choice_folder(tmp_path_factory.mktemp(name), main_trials(), **kwargs))


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    return _placeholder_report(tmp_path_factory, "gaze")


@pytest.fixture(scope="module")
def mouse_report(tmp_path_factory):
    return _placeholder_report(tmp_path_factory, "mouse", pointer=True)


def cells(report, c):
    return [row[c].text for row in trial_rows(report)]


# -- the layout ------------------------------------------------------------------------------------------


def test_a_choice_report_has_the_choice_layout_and_another_task_does_not(report, tmp_path):
    assert layout_kind(report) == CHOICE
    assert layout_kind(folder_report(tmp_path)) == SELECTION
    assert map_title(report) == "Scene Map" and map_title(folder_report(tmp_path / "x")) == "Target Map"
    assert targets_label(report) == "Buttons and objects"
    assert task_sentence(report) == "A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive."
    assert [outcome_label(report, o) for o in ("hit", "timeout", "skipped")] == ["Right", "Modelled", "Skipped"]
    assert outcome_label(folder_report(tmp_path / "y"), "hit") == "Hit"


def test_the_summary_of_results_has_the_four_rows_and_the_look_back_columns(report):
    assert summary_header(report) == (
        "", "% (N)", "Reaction Time (s)", "Wrong choices", "Looked back", "Look-back latency (s)",
    )
    assert len(summary_aligns(report)) == 6
    first, right, modelled, everything = summary_cells(report)
    # See test_choice_report: first choices 2 of 4 trials (median RT 1.5, look-back 2 of 2, median
    # latency 0.75 s), right choices 3 of 4 (2.0, 2 of 3), the modelled one (10.0, 1 of 1, 1.0 s).
    assert first == ["Right on the first choice", "50% (2/4)", "1.50", "0.0", "100% (2/2)", "0.75"]
    assert right[:3] == ["All right choices", "75% (3/4)", "2.00"] and right[4:] == ["67% (2/3)", "0.75"]
    assert modelled == ["Not chosen in time (modelled)", "25% (1/4)", "10.00", "0.0", "100% (1/1)", "1.00"]
    assert everything[:3] == ["All trials", "100% (4/4)", "2.50"] and everything[4:] == ["75% (3/4)", "1.00"]
    assert float(everything[3]) == pytest.approx(0.25, abs=0.06)


def test_the_tables_under_the_summary_are_by_button_side_and_while_choosing(report):
    side, wait = summary_extra_tables(report)
    assert (side.title, side.header) == ("By button side", ("Side", "Right choices", "Reaction Time (s)", "Looked back"))
    assert side.rows == [
        ["Left buttons", "50% (1/2)", "1.00", "100% (1/1)"],
        ["Right buttons", "100% (2/2)", "2.50", "50% (1/2)"],
    ]
    assert (wait.title, wait.header) == ("While choosing", ("Gaze on", "Share of the time to choose"))
    assert [r[0] for r in wait.rows] == ["Scene", "Buttons", "Elsewhere"]
    assert [r[1] for r in wait.rows] == ["28%", "60%", "12%"]  # 27.5, 60.0, 12.5 of 16 s
    assert "valid gaze only" in wait.note and "Valid gaze while choosing: 100 %" in wait.note


def test_the_trial_table_has_the_choice_and_look_back_columns_then_the_eye_ones(report):
    columns = trial_columns(report)
    assert columns[:12] == (
        "Trial", "Prompt", "Side", "Outcome", "Chosen", "Wrong choices", "Reaction Time (s)", "Looked back",
        "Look-back latency (s)", "Look-back time (s)", "Valid (%)", "Scene / Buttons / Else (%)",
    )
    assert columns[12:] == ("Fixations", "Saccades", "Pupil (mm)", "Pupil change (mm)")
    assert len(trial_aligns(report)) == len(columns) == len(trial_rows(report)[0])
    rows = trial_rows(report)
    assert [c.text for c in rows[0][:12]] == [
        "1", "Rainbow", "Left", "Right", "Rainbow", "0", "1.00", "Yes", "0.50", "1.00", "100", "40 / 60 / 0",
    ]
    # The bike: one wrong choice (the apples button, named in the tooltip), no look back, 100 % valid.
    assert [c.text for c in rows[1][:12]] == [
        "2", "Bike", "Right", "Right", "Bike", "1", "3.00", "No", DASH, "0.00", "100", "33 / 67 / 0",
    ]
    assert rows[1][5].tip == "Apples"
    # The timeout: modelled, nothing chosen, a look-back after the effect as a model.
    assert [c.text for c in rows[2][1:12]] == [
        "Balloons", "Left", "Modelled", DASH, "0", "10.00", "Yes", "1.00", "1.50", "100", "20 / 60 / 20",
    ]
    assert [c.text for c in rows[3][1:12]] == ["Seesaw", "Left", "Skipped"] + [DASH] * 8
    assert rows[4][7].text == "Yes" and rows[4][10].text == "83"  # 251 of 301 samples valid
    # The look-back column sorts yes before no; a dash has no key.
    assert (rows[0][7].key, rows[1][7].key, rows[3][7].key) == (1.0, 0.0, None)


def test_a_mouse_run_says_pointer_not_gaze_where_it_says_looked_back(mouse_report):
    assert summary_header(mouse_report)[4:] == ("Pointer back (not gaze)", "Pointer-back latency (s)")
    columns = trial_columns(mouse_report)
    assert columns[7:10] == ("Pointer back (not gaze)", "Pointer-back latency (s)", "Pointer-back time (s)")
    assert "Mouse run" in summary_info(mouse_report) and "not gaze" in summary_info(mouse_report)
    assert summary_extra_tables(mouse_report)[1].header[0] == "Pointer on"
    assert "Valid pointer while choosing" in summary_extra_tables(mouse_report)[1].note
    assert "Pointer back (not gaze)" in summary_note(mouse_report)
    # The figures are the pointer's; a Mouse test with no tracker has nothing in its eye columns.
    assert cells(mouse_report, 7)[:3] == ["Yes", "No", "Yes"]
    assert set(cells(mouse_report, 12)[:3]) == {NOT_RECORDED}


def test_the_visual_cue_is_marked_in_the_summary_and_the_configuration(tmp_path):
    meta = choice_meta(main_trials())
    meta["settings"]["structural"]["visual_cue"] = True
    cued = build_report(choice_folder(tmp_path, main_trials(), meta=meta))
    assert summary_info(cued) == "Visual cue was on: the target button pulsed."
    assert ("Visual cue", "On") in [tuple(r) for r in cued["config"]["rows"]]


def test_the_info_line_is_empty_for_a_normal_run_and_the_footnote_says_what_the_figures_are(report):
    assert summary_info(report) == ""
    note = summary_note(report)
    assert "1 skipped trial(s) excluded." in note
    assert "0.1 s on the animating object" in note and "plus 1°" in note and "medians" in note


def test_the_configuration_rows_name_the_scene_the_button_size_and_the_timing(report, tmp_path):
    rows = [tuple(r) for r in report["config"]["rows"]]
    labels = [label for label, _ in rows]
    assert "Target size" not in labels and "Trial timeout" not in labels and "Theme" not in labels
    assert dict(rows)["Task"] == "Choice-making"
    assert ("Button size", "6.6° x 5.2° cell, gap Standard") in rows
    assert ("Layout", "7×5 board, 8 buttons") in rows
    assert ("Time to choose", "10 s from the prompt end") in rows
    assert ("Pause after the animation", "1 s") in rows
    assert ("Scene", "Park, prompts in English") in rows
    assert ("Visual cue", "Off") in rows
    assert ("Idle animation", NOT_RECORDED) in rows  # until the canvas step writes it
    meta = choice_meta(main_trials(), idle_animation="blinks")
    blinking = build_report(choice_folder(tmp_path, main_trials(), meta=meta))
    assert ("Idle animation", "Blinks") in [tuple(r) for r in blinking["config"]["rows"]]


# -- the page ------------------------------------------------------------------------------------------------


def make_page(report):
    page = ReportPage()
    page.set_report(report, test_name="Choice-making 1")
    page.show()
    QCoreApplication.processEvents()
    return page


def test_the_summary_shows_the_scene_map_the_two_tables_and_the_choice_legend(qapp, report, tmp_path):
    page = make_page(report)
    summary = page.summary
    assert summary.map_title.text() == "Scene Map" and summary.targets_check.text() == "Buttons and objects"
    assert summary.table.cell_text(0, 0) == "Right on the first choice"
    assert [t.cell_text(0, 0) for t in summary.extra_tables] == ["Left buttons", "Scene"]
    assert summary.legend.entries() == list(CHOICE_LEGEND_ENTRIES)
    assert summary.info_label.isHidden()
    assert summary.map.model.choice is not None and summary.map.model.marks == [] and summary.map.model.slots == []
    page.set_report(folder_report(tmp_path))
    # Another report puts the Target Map and the four marks back, and the extra tables go.
    assert summary.map_title.text() == "Target Map" and summary.targets_check.text() == "Targets"
    assert summary.extra_tables == [] and summary.extra_box.count() == 0
    assert summary.map.model.choice is None and summary.map.model.marks


def test_the_detailed_view_lists_the_trials_with_the_look_back_columns(qapp, report):
    page = make_page(report)
    page.show_detailed()
    table = page.detailed.table
    assert table.rowCount() == 5 and table.columnCount() == 16
    assert [table.item(r, 3).text() for r in range(5)] == ["Right", "Right", "Modelled", "Skipped", "Right"]
    assert [table.badge_at(r).text() for r in range(5)] == ["Right", "Right", "Modelled", "Skipped", "Right"]
    assert table.item(1, 5).toolTip() == "Apples" and table.item(0, 5).toolTip() == ""
    assert page.detailed.map.model.choice is not None and page.selected_trial() == 0
    assert "look-back area" in page.detailed.trial_legend.text()
    # Sorting by Looked back puts the dash last in either direction.
    page.detailed.table.sortRequested.emit(7)
    assert [table.item(r, 7).text() for r in range(5)] == ["No", "Yes", "Yes", "Yes", DASH]


# -- the Scene Map ----------------------------------------------------------------------------------------------


def has_colour(image: QImage, colour: str, tolerance: int = 6) -> bool:
    """Is there an opaque pixel within ``tolerance`` per channel of ``colour``?"""
    want = QColor(colour)
    goal = (want.red(), want.green(), want.blue())
    for y in range(image.height()):
        for x in range(0, image.width(), 2):
            pixel = image.pixel(x, y)
            if pixel >> 24 == 255 and all(
                abs(((pixel >> shift) & 255) - g) <= tolerance for shift, g in zip((16, 8, 0), goal, strict=True)
            ):
                return True
    return False


def render(report, trial=None, overlays=None):
    widget = TargetMapWidget()
    widget.set_report(report)
    widget.set_trial(trial)
    return widget.render_to_image(QSize(1200, round(1200 / widget.aspect)), overlays or {"targets": True})


def test_the_whole_test_map_marks_right_choices_and_timeouts_on_the_buttons(qapp, report):
    image = render(report)
    assert has_colour(image, MAP_HIT_FILL) and has_colour(image, MAP_HIT_OUTLINE)  # right choices
    assert has_colour(image, MAP_MISS)  # the balloons that were not chosen in time
    assert has_colour(image, MAP_FIXATION)  # the dashed look-back areas
    # With Buttons and objects off nothing of the scene is drawn.
    assert not has_colour(render(report, overlays={"targets": False}), MAP_HIT_FILL)


def test_a_trial_map_colours_the_prompted_button_by_the_outcome(qapp, report):
    hit, timeout = render(report, 0), render(report, 2)
    assert has_colour(hit, MAP_HIT_FILL) and has_colour(hit, MAP_HIT_OUTLINE)
    assert not has_colour(timeout, MAP_HIT_FILL) and has_colour(timeout, MAP_MISS)


def test_a_trial_map_draws_the_gaze_during_the_animation_darker(qapp, report):
    plain = copy.deepcopy(report)
    plain["choice"]["trials"][0]["lookback_path"] = []
    assert render(report, 0) != render(plain, 0)
    assert report["choice"]["trials"][3]["lookback_path"] == []  # the skipped trial has none


def test_the_look_back_area_has_a_legend_icon(qapp):
    icon = symbol_image("aoi")
    assert has_colour(icon, MAP_FIXATION)


# -- the PDF ------------------------------------------------------------------------------------------------------


def page_of(doc, text):
    layout, height = doc.documentLayout(), doc.pageSize().height()
    block = doc.begin()
    while block.isValid():
        if block.text().strip() == text:
            return int(layout.blockBoundingRect(block).top() // height) + 1
        block = block.next()
    return None


def laid_out(report, qapp):
    widget = TargetMapWidget()
    widget.set_report(report)
    image = widget.render_to_image(QSize(1800, round(1800 / widget.aspect)), {"targets": True, "path": True})
    html = report_pdf.build_report_html(report, test_name="Choice-making 1", evaluator="Dr. Lin", notes="", map_image=image)
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    return html, report_pdf.laid_out_document(html, report_pdf.page_writer(buffer))


def test_the_pdf_has_the_tables_in_order_and_the_scene_map(qapp, report):
    html, _doc = laid_out(report, qapp)
    order = [html.index(s) for s in (
        "Summary of Results", "By button side", "While choosing", "Scene Map", "Eye Metrics", "Trial-by-Trial Results",
        "Definitions",
    )]
    assert order == sorted(order)
    assert "Target Map" not in html and "Right on the first choice" in html and "Left buttons" in html
    assert "Right choices (count)" in html and "Look-back area (object plus 1°)" in html
    assert "Numbers on a button = trials that ended that way" in html
    assert "Looked back: at least 0.1 s of valid gaze" in html


def test_the_pdf_scene_map_starts_page_2_and_page_1_holds_the_tables_above_it(qapp, fonts, report):
    _html, doc = laid_out(report, qapp)
    assert doc.pageCount() == 3
    assert [page_of(doc, t) for t in ("Test Configuration", "Summary of Results", "By button side", "While choosing")] == [1] * 4
    assert [page_of(doc, t) for t in ("Scene Map", "Eye Metrics", "Trial-by-Trial Results")] == [2, 2, 2]
    # Nothing of page 1 spills onto page 2: the last block before the map ends inside the page.
    layout, height = doc.documentLayout(), doc.pageSize().height()
    block, last = doc.begin(), None
    while block.isValid() and block.text().strip() != "Scene Map":
        last, block = block, block.next()
    assert layout.blockBoundingRect(last).bottom() <= height


@pytest.mark.parametrize("which", ["gaze", "mouse"])
def test_the_sixteen_column_trial_table_gets_room_for_every_word_at_a_readable_size(qapp, fonts, report, mouse_report, which):
    shown = report if which == "gaze" else mouse_report
    meter = report_pdf._Meter()
    rows = [[c.text for c in row] for row in trial_rows(shown)]
    fitting = [
        pt for pt in (8.0, 7.5, 7.0, 6.5)
        if report_pdf._column_widths(trial_columns(shown), rows, meter, pt) is not None
    ]
    assert fitting and min(fitting) >= report_pdf.TRIAL_TABLE_MIN_PT


def test_print_report_writes_the_pdf_of_a_choice_report(qapp, report, tmp_path):
    page = make_page(report)
    path = page.export_pdf(tmp_path / "choice.pdf")
    assert path.exists() and path.stat().st_size > 5000
    assert path.read_bytes()[:5] == b"%PDF-"
