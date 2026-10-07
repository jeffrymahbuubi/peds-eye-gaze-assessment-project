"""SPEC-compass-task-flow.md 7.1, V5: every on-screen and PDF text shows seconds, never
milliseconds, while the data files keep milliseconds (CSV columns, JSON fields, stored
settings). The formatters, the slider rows, the registry labels, the report texts, and a scan of
the UI source for any user-visible " ms" string left."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel, QSpinBox

from src.data.report_util import ms_to_seconds, seconds_text
from src.engine.config import load_task_config
from src.ui.report_format import (
    DASH,
    DEFINITIONS,
    TRIAL_COLUMNS,
    eye_rows,
    seconds_figure,
    trial_cells,
)
from src.ui.settings_registry import (
    LIVE_SETTINGS,
    MS_PER_S,
    STRUCTURAL_SETTINGS,
    initial_live_values,
    live_settings_for_task,
)
from src.ui.slider_spin import SliderSpinRow, display_decimals
from src.ui.task_config_page import TaskConfigPage
from src.ui.task_settings_dialog import TaskSettingsDialog
from tests.report_ui_fixtures import folder_report

SRC = Path(__file__).resolve().parents[1] / "src"
# (Follow the Target's selection window is gone: it has nothing to select.)
TIME_KEYS = (
    "dwell.threshold_ms", "dwell.refractory_ms", "task.timeout_ms", "task.inter_trial_interval_ms",
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- the formatters ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ms", "text"),
    [
        (800, "0.8 s"), (500, "0.5 s"), (8000, "8 s"), (120, "0.12 s"), (1000, "1 s"),
        (300, "0.3 s"), (100, "0.1 s"), (0, "0 s"), (12500, "12.5 s"), (233.4, "0.233 s"),
        (800.0, "0.8 s"), ("800", "0.8 s"), (-500, "-0.5 s"),
    ],
)
def test_seconds_text_is_compact_seconds(ms, text):
    assert seconds_text(ms) == text


@pytest.mark.parametrize("bad", [None, "", "x", True, False, [], {}])
def test_seconds_text_dashes_what_is_not_a_number(bad):
    assert seconds_text(bad) == "—"
    assert seconds_text(bad, dash="n/a") == "n/a"
    assert ms_to_seconds(bad) is None


def test_seconds_text_never_prints_ms_and_limits_the_decimals():
    assert "ms" not in seconds_text(123456)
    assert seconds_text(1234.5678, digits=2) == "1.23 s"
    assert seconds_text(1234.5678, digits=0) == "1 s"


def test_ms_to_seconds_divides_by_a_thousand():
    assert ms_to_seconds(800) == 0.8 and ms_to_seconds("1500") == 1.5 and ms_to_seconds(0) == 0.0


@pytest.mark.parametrize(
    ("ms", "digits", "text"),
    [(233.4, 2, "0.23"), (800, 2, "0.80"), (1000, 1, "1.0"), (45.6, 3, "0.046"), (None, 2, DASH),
     ("x", 2, DASH), (True, 2, DASH)],
)
def test_seconds_figure_is_seconds_to_fixed_decimals_with_no_unit(ms, digits, text):
    assert seconds_figure(ms, digits) == text


# -- the report's texts ------------------------------------------------------------------------------


def test_the_fixation_duration_column_says_seconds_and_shows_seconds(tmp_path):
    report = folder_report(tmp_path)
    assert "Mean fix. dur. (s)" in TRIAL_COLUMNS and not any("(ms)" in c for c in TRIAL_COLUMNS)
    column = TRIAL_COLUMNS.index("Mean fix. dur. (s)")
    trial = report["trials"][0]
    stored = trial["fixations"]["mean_dur_ms"]
    cell = trial_cells(trial)[column]
    assert stored > 100  # the data file still holds milliseconds
    assert cell.text == f"{stored / 1000:.2f}" and float(cell.text) < 5
    assert cell.key == pytest.approx(stored / 1000)  # sorts by the seconds shown


def test_a_trial_without_fixation_time_dashes_that_cell():
    cells = trial_cells({"fixations": {"count": None, "mean_dur_ms": None}})
    assert cells[TRIAL_COLUMNS.index("Mean fix. dur. (s)")].text == DASH
    assert cells[TRIAL_COLUMNS.index("Mean fix. dur. (s)")].key is None


def test_the_eye_metric_duration_reads_in_seconds(tmp_path):
    report = folder_report(tmp_path)
    duration = dict(eye_rows(report))["Mean fixation duration"]
    stored = report["summary"]["eye"]["fixation_duration_ms"]
    assert duration == f"{stored['mean'] / 1000:.2f} s (median {stored['median'] / 1000:.2f} s)"
    assert "ms" not in duration
    report["summary"]["eye"]["fixation_duration_ms"] = {"mean": 250.0, "median": None}
    assert dict(eye_rows(report))["Mean fixation duration"] == "0.25 s"
    report["summary"]["eye"]["fixation_duration_ms"] = {"mean": None, "median": None}
    assert dict(eye_rows(report))["Mean fixation duration"] == DASH


def test_the_definitions_use_seconds():
    text = " ".join(DEFINITIONS)
    assert not re.search(r"\bms\b", text)
    assert "0.12 s" in text and "0.3 s" in text and "0.1 s" in text


def test_every_report_row_and_cell_of_a_real_report_is_free_of_ms(tmp_path):
    report = folder_report(tmp_path)
    shown = [f"{label} {value}" for label, value in report["config"]["rows"]]
    shown += [f"{label} {value}" for label, value in eye_rows(report)]
    shown += [cell.text for trial in report["trials"] for cell in trial_cells(trial)]
    shown += list(TRIAL_COLUMNS)
    assert not [text for text in shown if re.search(r"\bms\b", text)]


def test_the_report_json_keeps_its_milliseconds(tmp_path):
    """The data keeps ms: the stored field names and parameters are unchanged."""
    report = folder_report(tmp_path)
    assert "mean_dur_ms" in report["trials"][0]["fixations"]
    assert "fixation_duration_ms" in report["summary"]["eye"]
    assert report["params"]["entries"] == {"exit_hold_ms": 120.0}
    assert "min_step_ms" in report["params"]["path"] and "weight_cap_ms" in report["params"]["heat"]
    assert "blink_mask_ms" in report["params"]["pupil"] and "baseline_ms" in report["params"]["pupil"]
    assert "reaction_time_s" in report["trials"][0]  # the report's own times were always seconds


# -- the registry and the slider rows -------------------------------------------------------------------


def test_every_time_setting_is_labelled_in_seconds_and_shown_divided_by_a_thousand():
    timed = [s for s in (*LIVE_SETTINGS, *STRUCTURAL_SETTINGS) if s.key.endswith("_ms")]
    assert {s.key for s in timed} == set(TIME_KEYS)
    for setting in timed:
        assert setting.label.endswith("(s)") and "ms" not in setting.label, setting.key
        assert setting.display_divisor == MS_PER_S == 1000.0
    for setting in (*LIVE_SETTINGS, *STRUCTURAL_SETTINGS):
        assert "(ms)" not in setting.label
        if not setting.key.endswith("_ms"):
            assert setting.display_divisor == 1.0, setting.key  # nothing else is rescaled


def test_the_stored_ranges_defaults_and_keys_are_still_in_milliseconds():
    by_key = {s.key: s for s in (*LIVE_SETTINGS, *STRUCTURAL_SETTINGS)}
    assert (by_key["dwell.threshold_ms"].min, by_key["dwell.threshold_ms"].max) == (300, 2000)
    assert by_key["task.timeout_ms"].step == 500
    # Follow the Target's trial duration: 3-30 s in half-second steps (SPEC H9), same key, still ms.
    duration = next(s for s in live_settings_for_task("follow_moving") if s.key == "task.timeout_ms")
    assert (duration.label, duration.min, duration.max, duration.step) == (
        "Trial duration (s)", 3000, 30000, 500,
    )
    assert duration.display_divisor == 1000.0
    live = initial_live_values(load_task_config("click_static"))
    assert live["dwell.threshold_ms"] >= 300 and isinstance(live["dwell.threshold_ms"], int)
    assert live["task.timeout_ms"] >= 1000  # a thousand times the number a person reads


@pytest.mark.parametrize(
    ("step", "divisor", "decimals"),
    [(50, 1000.0, 2), (100, 1000.0, 1), (500, 1000.0, 1), (1000, 1000.0, 0), (5, 1000.0, 3), (1, 1.0, 0)],
)
def test_the_readout_has_the_decimals_its_step_needs(step, divisor, decimals):
    assert display_decimals(step, divisor) == decimals


def test_a_slider_row_with_a_divisor_shows_seconds_and_speaks_milliseconds(qapp):
    row = SliderSpinRow("int", 300, 2000, 50, 800, display_divisor=1000.0)
    spin = row._spin
    assert isinstance(spin, QDoubleSpinBox)
    assert (spin.value(), spin.minimum(), spin.maximum(), spin.singleStep()) == (0.8, 0.3, 2.0, 0.05)
    assert spin.decimals() == 2 and spin.text() == "0.80"
    assert row.value() == 800 and isinstance(row.value(), int)  # the stored unit, an int
    seen: list = []
    row.valueChanged.connect(seen.append)
    spin.setValue(1.25)  # the operator types seconds ...
    assert row.value() == 1250 and seen == [1250] and isinstance(seen[0], int)  # ... the app gets ms
    assert row._slider.value() == round((1250 - 300) / 50)
    row._slider.setValue(0)  # the slider's left end is the minimum, 0.3 s
    assert spin.value() == 0.3 and seen[-1] == 300
    row.setValue(2000)
    assert spin.value() == 2.0 and row.value() == 2000


def test_a_slider_row_without_a_divisor_is_what_it_was(qapp):
    row = SliderSpinRow("int", 0, 100, 5, 50)
    assert isinstance(row._spin, QSpinBox) and row.value() == 50 and row._spin.value() == 50
    fl = SliderSpinRow("float", 0.0, 1.0, 0.05, 0.5)
    assert isinstance(fl._spin, QDoubleSpinBox) and fl._spin.decimals() == 2 and fl.value() == 0.5


def test_the_time_rows_of_the_page_show_seconds_and_collect_milliseconds(qapp):
    config = load_task_config("click_static")
    page = TaskConfigPage("click_static", config, screen=None)
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name="Static 1")
    live = initial_live_values(config)
    for key in TIME_KEYS:
        row = page._form.controls[key]
        assert row._spin.value() == pytest.approx(live[key] / 1000.0)
        assert row.value() == live[key]  # milliseconds underneath
    page._form.controls["dwell.threshold_ms"]._spin.setValue(1.5)
    values = page.collect_values()
    assert values["live"]["dwell.threshold_ms"] == 1500
    assert isinstance(values["live"]["dwell.threshold_ms"], int)


def test_follows_trial_duration_row_shows_seconds_and_collects_milliseconds(qapp):
    config = load_task_config("follow_moving")
    page = TaskConfigPage("follow_moving", config, screen=None)
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name="Follow 1")
    row = page._form.controls["task.timeout_ms"]
    assert row._spin.value() == pytest.approx(10.0)  # the shipped default, 10 s
    assert row.value() == 10000
    row._spin.setValue(12.5)
    assert page.collect_values()["live"]["task.timeout_ms"] == 12500
    row._spin.setValue(99.0)  # clamped to the 30 s maximum
    assert page.collect_values()["live"]["task.timeout_ms"] == 30000


def test_the_labels_on_the_page_say_seconds(qapp):
    page = TaskConfigPage("click_static", load_task_config("click_static"), screen=None)
    text = " | ".join(label.text() for label in page.findChildren(QLabel))
    for label in ("Dwell threshold (s)", "Refractory period (s)", "Trial timeout (s)",
                  "Inter-trial interval (s)"):
        assert label in text
    assert "(ms)" not in text
    follow = TaskConfigPage("follow_moving", load_task_config("follow_moving"), screen=None)
    follow_text = " | ".join(label.text() for label in follow.findChildren(QLabel))
    assert "Trial duration (s)" in follow_text and "Inter-trial interval (s)" in follow_text
    assert "Trial timeout (s)" not in follow_text and "(ms)" not in follow_text


def test_no_structural_setting_is_a_time_any_more_so_the_dialog_rescales_nothing(qapp):
    # The selection window was the only one; the dialog (standalone launch) has no seconds rows.
    assert not [s for s in STRUCTURAL_SETTINGS if s.key.endswith("_ms")]
    dialog = TaskSettingsDialog("follow_moving", load_task_config("follow_moving"))
    assert "motion.select_window_ms" not in dialog._controls
    assert "motion" in dialog.overrides() and "select_window_ms" not in dialog.overrides()["motion"]


# -- nothing user-visible says ms ------------------------------------------------------------------------


def _strings(path: Path):
    """The string constants of a module that a person could read: every constant but the
    docstrings (comments are not in the syntax tree at all)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value


UNIT_MS = re.compile(r"(?<![A-Za-z_.])ms(?![A-Za-z_])|\dms\b|\(ms\)|millisecond", re.IGNORECASE)


def test_no_user_visible_string_in_the_ui_says_ms():
    """The acceptance grep of V5: ``src/ui`` (comments and identifiers aside) and the report's
    configuration rows have no " ms" in a string."""
    files = sorted((SRC / "ui").glob("*.py")) + [SRC / "data" / "report_config.py"]
    found = [
        f"{path.relative_to(SRC)}:{line}: {text!r}"
        for path in files
        for line, text in _strings(path)
        if UNIT_MS.search(text)
    ]
    assert found == []


def test_the_scan_would_see_a_real_ms_string(tmp_path):
    sample = tmp_path / "x.py"
    sample.write_text('"""A docstring with 800 ms."""\nLABEL = "Dwell (ms)"\nOK = "dwell.threshold_ms"\n'
                      'F = f"{n} ms"\n', encoding="utf-8")
    hits = [text for _line, text in _strings(sample) if UNIT_MS.search(text)]
    assert hits == ["Dwell (ms)", " ms"]  # the docstring and the key are not user-visible text
