"""SPEC-design-system-phase1.md H10-H12, P4-P6 (docs/design/fable-proposal.md section 4): the
copy rules of the operator UI.

* no em dash anywhere in ``src/ui``, ``src/data`` and ``src/engine/task_info.py`` (comments and
  docstrings included), except the two constants that hold the numeric-cell dash;
* one date format; the report's configuration labels and values; a missing value in a text cell
  reads "not recorded";
* no interpunct chain and no "Test Complete!" in what the changed modules say.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.data.report_config import build_config_rows
from src.data.report_util import DASH, NOT_RECORDED
from src.engine.target_size import GAP_CHOICES
from src.engine.task_info import TASK_INFO
from src.engine.tracking_status import LEVEL_WARN, run_status
from src.ui import report_format
from src.ui.choice_lists import (
    INPUT_SELECTION_CHOICES,
    MOTION_PATH_CHOICES,
    TARGET_SIZE_CHOICES,
)
from src.ui.config_widgets import choice_label
from src.ui.report_format import started_text, trial_line
from src.ui.setup_page import SetupPage, calibration_measured_alert_text
from src.ui.start_test_page import (
    MOUSE_NOTE_ALONGSIDE,
    MOUSE_NOTE_NO_EYE_DATA,
    MOUSE_NOTE_NO_TRACKER,
    MOUSE_NOTE_NOT_CALIBRATED,
)
from tests.report_fixtures import RIG_META

SRC = Path(__file__).resolve().parent.parent / "src"
EM_DASH = "—"
INTERPUNCT = "·"
# The only module that still holds an interpunct: the Test List's " · data missing", which is
# now only the hidden text of the Status item (the badge says it, phase 2). The Start page's
# blocker join went with the Blocked alert (phase 2 H7) and the map legend sentences were split
# into two caption lines without one (phase 4 D3).
INTERPUNCT_LATER = {"ui/test_list_table.py"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def scanned_files() -> list[Path]:
    return sorted((SRC / "ui").glob("*.py")) + sorted((SRC / "data").glob("*.py")) + [SRC / "engine" / "task_info.py"]


# -- P4: the em dash --------------------------------------------------------------------------------


def test_the_em_dash_is_only_in_the_two_dash_constants():
    found = []
    for path in scanned_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EM_DASH in line and not re.match(r'^(DASH|NO_DATE) = "' + EM_DASH + '"', line):
                found.append(f"{path.relative_to(SRC)}:{number}: {line.strip()}")
    assert found == []


def test_the_two_dash_constants_are_the_numeric_and_date_cell_dash():
    from src.ui.test_list_table import NO_DATE

    assert DASH == NO_DATE == EM_DASH
    assert report_format.DASH is DASH and report_format.NOT_RECORDED == NOT_RECORDED == "not recorded"


def test_no_interpunct_is_left_outside_the_module_that_keeps_one():
    found = {
        str(path.relative_to(SRC)).replace("\\", "/")
        for path in [*scanned_files(), SRC / "engine" / "tracking_status.py", SRC / "tasks" / "follow_moving.py"]
        if INTERPUNCT in path.read_text(encoding="utf-8")
    }
    assert found == INTERPUNCT_LATER


def test_no_exclamation_status_word_is_left():
    for path in sorted((SRC / "ui").glob("*.py")):
        assert "Test Complete!" not in path.read_text(encoding="utf-8"), path.name


@pytest.mark.parametrize(
    "flags",
    [
        {},
        {"practice": True},
        {"paused": True},
        {"preview": True},
        {"mouse": True},
        {"preview": True, "mouse": True, "tracker_not_ready": True},
    ],
)
def test_the_run_bar_status_has_no_interpunct(flags):
    assert INTERPUNCT not in run_status(3, 9, "No gaze for 3 s", LEVEL_WARN, **flags).line


# -- P5: dates --------------------------------------------------------------------------------------


def test_started_text_is_an_iso_date_and_a_24_hour_time():
    moment = datetime(2026, 10, 7, 17, 9)
    assert started_text(int(moment.timestamp() * 1e9)) == "2026-10-07 17:09"
    morning = datetime(2026, 1, 2, 3, 4)
    assert started_text(int(morning.timestamp() * 1e9)) == "2026-01-02 03:04"


@pytest.mark.parametrize("bad", [None, "x", True, 1e30])
def test_a_run_with_no_start_time_says_not_recorded(bad):
    assert started_text(bad) == NOT_RECORDED


def test_the_setup_date_field_shows_yyyy_mm_dd(qapp):
    page = SetupPage()
    assert page.date_edit.displayFormat() == "yyyy-MM-dd"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", page.date_edit.text())


# -- P6: the report's configuration rows -----------------------------------------------------------


def test_the_configuration_labels_and_values_are_the_proposal_section_4_ones():
    rows = dict(build_config_rows(RIG_META["settings"], RIG_META))
    assert list(rows)[3] == "Number of trials" and rows["Number of trials"] == "6"
    assert rows["Trial timeout"] == "8 s" and rows["Inter-trial interval"] == "0.8 s"
    assert rows["Gaze cursor"] == "Shown"
    assert rows["Feedback"] == "Hit sound on, miss sound on"
    assert rows["Gaze smoothing"] == "On, alpha 0.22, jitter tolerance 40 px"
    assert rows["Target size"] == "Medium (5°, 207 px)"
    assert rows["Selection"] == "Dwell, threshold 0.8 s, refractory 0.5 s"
    for old in ("Maximum time per trial", "Pause between trials", "Trials (planned)", "Gaze cursor shown"):
        assert old not in rows


def test_a_cursor_that_was_hidden_says_hidden():
    meta = {"settings": {"live": {"dwell.visual_cursor": False}, "structural": {}}}
    assert dict(build_config_rows(meta["settings"], meta))["Gaze cursor"] == "Hidden"


def test_glow_is_reported_with_the_other_feedback_check_boxes():
    meta = {"settings": {"live": {}, "structural": {"feedback": {"hit_sound": True, "miss_sound": False, "target_glow": False}}}}
    assert dict(build_config_rows(meta["settings"], meta))["Feedback"] == "Hit sound on, miss sound off, glow off"


def test_a_missing_text_value_reads_not_recorded_and_never_a_dash():
    rows = dict(build_config_rows(None, None))
    assert set(rows.values()) == {NOT_RECORDED}
    assert all(DASH not in value for value in rows.values())


def test_the_detailed_trial_line_is_commas_and_a_degree_sign():
    trial = {"saccades": {"scanpath_deg": 75.4, "count": 32}, "fixations": {"count": 8}}
    assert trial_line(trial) == "Scan path 75.4°, 8 fixations, 32 saccades"
    assert trial_line({"saccades": {}, "fixations": {"count": 1}}) == (
        "Scan path not recorded, 1 fixation, saccades not recorded"
    )


def test_the_report_header_dates_and_titles(qapp):
    from src.ui.report_page import ReportPage

    page = ReportPage()
    assert page.title_label.text() == "Summary Results"  # no colon (rule 6)
    assert NOT_RECORDED in page.date_label.text() and DASH not in page.date_label.text()


def test_the_pdf_header_has_the_title_without_a_colon_and_not_recorded_for_what_is_missing():
    from src.ui.report_pdf import build_report_html

    report = {"session": {"subject": "P001", "started_ns": None}, "config": {"rows": []}, "summary": {}, "trials": []}
    html = build_report_html(report, test_name="Grid Click 1", evaluator="", notes="", map_image=None)
    assert "Summary Results, Grid Click 1" in html and "Summary Results:" not in html
    assert f"Evaluator: <b>{NOT_RECORDED}</b>" in html
    assert re.search(rf'>Notes</p><p style="[^"]*">{NOT_RECORDED}</p>', html)  # the Notes text, a paragraph now
    assert EM_DASH not in html.split("<table")[0]  # the header block says words, not a lone dash


# -- the proposal section 4 table, text only -------------------------------------------------------


def test_the_size_and_gap_labels_have_their_degrees_and_the_pixels_inside_the_brackets():
    assert dict(TARGET_SIZE_CHOICES)["small"] == "Small (3°)"
    assert dict(GAP_CHOICES)["wide"] == "Wide (1°)" and dict(GAP_CHOICES)["standard"] == "Standard"
    assert choice_label("target.size", "small", "Small (3°)", 0.2745, 650.0) == "Small (3°, about 124 px)"
    assert choice_label("grid.gap", "wide", "Wide (1°)", 0.2745, 650.0) == "Wide (1°, about 41 px)"
    assert choice_label("grid.gap", "standard", "Standard", 0.2745, 650.0) == "Standard"


def test_the_selection_and_motion_choices_use_a_colon_and_words():
    assert dict(INPUT_SELECTION_CHOICES) == {
        "dwell": "Dwell: keep looking at the target",
        "switch": "Switch: look at the target, then press the switch",
    }
    paths = dict(MOTION_PATH_CHOICES)
    assert paths["diagonal_tlbr"] == "Diagonal, top-left to bottom-right"
    assert paths["diagonal_trbl"] == "Diagonal, top-right to bottom-left"


def test_the_task_descriptions_are_full_stops_not_dashes():
    assert TASK_INFO["click_static"][1] == "One still target on an empty field. Baseline look and select."
    assert TASK_INFO["click_grid"][1] == "One cell of a visible board lights up. Selection among candidates."
    assert TASK_INFO["follow_moving"][1] == (
        "The target travels across the screen. Follow it; nothing is selected. Smooth pursuit."
    )
    assert TASK_INFO["scanning"][1] == "Find the cued shape among other shapes. Visual search."


def test_the_mouse_notes_are_two_sentences():
    assert MOUSE_NOTE_ALONGSIDE == "Mouse test. Eye data will be recorded alongside."
    # (section 9, 2026-10-09: the clause "no eye data will be recorded" is a sentence of its own,
    # in its own label at weight 600)
    assert MOUSE_NOTE_NO_TRACKER == "Mouse test. The tracker is not connected."
    assert MOUSE_NOTE_NOT_CALIBRATED == "Mouse test. The tracker is not calibrated."
    assert MOUSE_NOTE_NO_EYE_DATA == "No eye data will be recorded."


class _Result:
    n_points = 5
    per_point = None


def test_the_setup_calibration_texts_use_a_colon_and_full_stops():
    text = calibration_measured_alert_text(_Result, "12px")
    assert text.startswith("Calibration measured: 5 points, mean error 12px, valid.")
    assert "Per-point details were not received. If this repeats, close and reopen" in text


def test_the_setup_display_line_says_the_recommended_standard_after_a_colon(qapp):
    from src.engine.display_check import check_display

    page = SetupPage()
    page._apply_display_check(check_display(1920, 1080, 1.0))
    assert page.display_ok_label.text() == "Display 1920×1080 at 100 %: the recommended standard."


def test_the_other_setup_texts_have_no_dash_and_read_as_sentences():
    source = (SRC / "ui" / "setup_page.py").read_text(encoding="utf-8")
    assert "No calibration yet for this subject. Run Do Calibration or" in source
    assert "(Read-only reminder: neither setting" in source
    assert "Move the data cable to a" in source
    assert "Calibration loaded: " in source and "Calibration saved for {subject_id} as {target_path.name}. " in source


def test_the_run_end_dialog_says_test_complete_without_a_bang(qapp):
    from src.ui.run_dialogs import TestCompleteDialog

    dialog = TestCompleteDialog()
    assert dialog.windowTitle() == "Test complete" and dialog.text_label.text() == "Test complete"


def test_the_standalone_settings_dialog_title_names_the_task_with_a_colon(qapp):
    from PySide6.QtWidgets import QLabel

    from src.engine.config import load_task_config
    from src.ui.task_settings_dialog import TaskSettingsDialog

    dialog = TaskSettingsDialog("click_grid", load_task_config("click_grid"))
    assert dialog.windowTitle() == "Task settings: Grid Click"
    titles = [label.text() for label in dialog.findChildren(QLabel) if label.objectName() == "wtmhSectionTitle"]
    assert titles == ["Task settings: Grid Click"]


def test_the_test_list_back_button_says_back_to_setup(qapp):
    from src.ui.test_list_page import SubjectTestListPage

    assert SubjectTestListPage().back_button.text() == "Back to Setup"


# -- A1: the interpuncts replaced in round 2 ------------------------------------------------------


def test_the_nav_labels_and_the_setup_title_have_no_number(qapp):
    from PySide6.QtWidgets import QLabel

    from src.ui.dashboard_flow import NAV_LABELS

    assert NAV_LABELS == ("Setup", "Tests")
    page = SetupPage()
    titles = [label.text() for label in page.findChildren(QLabel) if label.objectName() == "wtmhPageTitle"]
    assert titles == ["Setup"]


def test_the_device_lines_are_comma_separated():
    from src.inputs.gazepoint_client import DeviceInfo
    from src.ui.setup_page import _format_device_info

    info = DeviceInfo(model="GP3HD", rate_hz=150, bus="USB 3.0", serial="12345",
                      camera_width=640, camera_height=480, api_version="2.0")
    assert _format_device_info(info) == "Device: GP3HD, 150 Hz, USB 3.0, SN 12345\nCamera: 640\u00d7480, API v2.0"
    assert _format_device_info(DeviceInfo(model="GP3HD")) == "Device: GP3HD"
    assert _format_device_info(None) == ""


def test_the_configuration_subtitle_is_task_comma_subject(qapp):
    from src.engine.config import load_task_config
    from src.ui.task_config_page import TaskConfigPage

    page = TaskConfigPage("click_grid", load_task_config("click_grid"))
    page.set_context(subject_id="P1", existing_test_names=[])
    assert page.subtitle_label.text() == "Grid Click, subject P1"


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("eye", "Gaze (GP3HD, 150 Hz), Dwell 0.8 s"),
        ("gaze_switch", "Gaze (GP3HD, 150 Hz), Switch"),
        ("switch", "Mouse, Switch"),
        ("mouse_dwell", "Mouse, Dwell 0.8 s"),
    ],
)
def test_the_input_row_is_a_comma_not_an_interpunct(mode, expected):
    meta = {**RIG_META, "input_mode": mode}
    row = dict(build_config_rows(meta["settings"], meta))["Input"]
    assert row == expected and INTERPUNCT not in row


def test_the_pdf_header_facts_are_comma_separated_plain_text():
    from src.ui.report_pdf import build_report_html

    report = {"session": {"subject": "P001", "started_ns": None}, "config": {"rows": []}, "summary": {}, "trials": []}
    html = build_report_html(report, test_name="T", evaluator="Dr. Lin", notes="x", map_image=None)
    header = html.split("<h3", 1)[0]
    assert "Subject: <b>P001</b>, Test Date: <b>not recorded</b>, Evaluator: <b>Dr. Lin</b>" in header
    assert INTERPUNCT not in header and "&nbsp;" not in header


# -- A4: the path message and the motion-path words -------------------------------------------------


def test_the_path_too_long_message_is_two_sentences():
    from src.engine.run_paths import PATH_TOO_LONG_TEXT

    assert PATH_TOO_LONG_TEXT == (
        "The data folder path is too long. Move the program folder closer to the drive root."
    )


def test_the_report_names_a_motion_path_with_the_configuration_pages_exact_words():
    from src.tasks.follow_moving import MOTION_PATH_LABELS, PATHS

    assert dict(MOTION_PATH_CHOICES) == MOTION_PATH_LABELS and list(MOTION_PATH_LABELS) == list(PATHS)
    for path, label in MOTION_PATH_CHOICES:
        meta = {"settings": {"live": {}, "structural": {"motion": {"path": path}}}}
        layout = dict(build_config_rows(meta["settings"], meta, task_id="follow_moving"))["Layout"]
        assert layout == f"{label} path", (path, layout)
