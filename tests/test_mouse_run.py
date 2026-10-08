"""SPEC-input-selection-and-follow.md H1, H4, 4.3, 4.6, I7 (acceptance A5, A9) through
``AssessmentApp``: a test with Pointer = Mouse runs and records with the tracker
disconnected (``pointer_stream.csv``, no gaze files, ``gaze_recorded`` false, the report's eye
sections say "not recorded") and, with a tracker connected, records its gaze alongside.
``input_mode`` is derived as H1 says and the report labels every value. Offscreen Qt; the mouse
is a ``MouseGazeSource`` with a stand-in cursor, the tracker another one."""

# The fixtures are imported from input_run_fixtures and then used by name.
# ruff: noqa: F811
from __future__ import annotations

import csv
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import src.app as app_module
from src.data.recorder import POINTER_STREAM_COLUMNS
from src.data.report_cache import build_report
from src.data.report_config import build_config_rows
from src.inputs.no_tracker import NoTracker
from src.ui.report_format import DASH, NOT_RECORDED, eye_rows
from src.ui.report_layout import trial_columns, trial_rows
from src.ui.report_page import ReportPage
from src.ui.report_pdf import build_report_html
from tests.input_run_fixtures import (  # noqa: F401  (fixtures)
    FIXTURE,
    events_of,
    finish_run,
    kinds,
    look_at_target,
    make_app,
    parked,
    qapp,
    tick,
    tick_until,
)

MOUSE_DWELL = {"pointer": "mouse", "selection": "dwell"}
MOUSE_SWITCH = {"pointer": "mouse", "selection": "switch"}
STANDALONE_FILES = ("pointer_stream.csv", "gaze_stream.csv", "all_gaze.csv", "eye_geometry.csv")


def files(app) -> set[str]:
    return {p.name for p in app.recorder.session_dir.iterdir()}


def metadata(app) -> dict:
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def csv_rows(path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def no_calibration(monkeypatch):
    """A Mouse run must never start a calibration: it would dial the (absent) tracker."""

    def boom(*args, **kwargs):
        raise AssertionError("a Mouse run started a calibration")

    monkeypatch.setattr(app_module, "Calibration", boom)


# -- A5: no tracker ----------------------------------------------------------------------


def test_a_mouse_run_with_no_tracker_needs_no_tracker_and_no_calibration(make_app, monkeypatch):
    no_calibration(monkeypatch)
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    assert isinstance(app.client, NoTracker) and not app._owns_client
    assert app._gaze_recorded is False and app._pointer_is_mouse is True
    assert app.metadata.calibration_source == "not run"
    assert (app.metadata.calibration_points, app.metadata.calibration_error_px) == (0, None)
    assert app.pointer_source is not app.client


def test_a_mouse_run_with_no_tracker_writes_the_pointer_stream_and_no_gaze_files(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    finish_run(app)
    assert files(app) >= {"pointer_stream.csv", "trials.csv", "metadata.json", "events.jsonl", "session.log"}
    assert not files(app) & {"gaze_stream.csv", "all_gaze.csv", "eye_geometry.csv"}
    rows = csv_rows(app.recorder.session_dir / "pointer_stream.csv")
    assert rows and list(rows[0]) == POINTER_STREAM_COLUMNS == ["t_ns", "x", "y", "valid"]
    assert {r["valid"] for r in rows} <= {"0", "1"} and "1" in {r["valid"] for r in rows}
    t = [int(r["t_ns"]) for r in rows]
    assert t == sorted(t)
    meta = metadata(app)
    assert meta["gaze_recorded"] is False
    assert (meta["input_mode"], meta["input_pointer"], meta["input_selection"]) == (
        "mouse_dwell", "mouse", "dwell",
    )
    assert meta["screen_width_px"] and meta["screen_height_px"]  # the canvas's own monitor, for degrees
    log = (app.recorder.session_dir / "session.log").read_text(encoding="utf-8")
    assert "Input: pointer mouse, selection dwell. No tracker: no gaze is recorded." in log
    assert "Connected to Gazepoint Control" not in log


def test_the_mouse_path_is_what_the_stream_holds(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1, live={"dwell.threshold_ms": 60000})
    tick(app, 2)
    app.pointing.at_norm(app.canvas, 0.25, 0.5)
    tick(app)
    app.pointing.at_norm(app.canvas, 0.75, 0.5)
    tick(app)
    app._shutdown()
    rows = csv_rows(app.recorder.session_dir / "pointer_stream.csv")
    xs = [float(r["x"]) for r in rows if r["valid"] == "1"]
    assert xs[-2:] == pytest.approx([0.25, 0.75], abs=0.01)


def test_the_mouse_is_the_pointer_and_dwell_is_a_hover(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    finish_run(app)
    row = csv_rows(app.recorder.session_dir / "trials.csv")[0]
    assert row["is_hit"] == "1" and (row["clicks"], row["click_errors"]) == ("0", "0")


def test_the_report_eye_sections_say_not_recorded(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    finish_run(app)
    report = build_report(app.recorder.session_dir)
    session = report["session"]
    assert (session["gaze_recorded"], session["pointer"], session["selection"]) == (False, "mouse", "dwell")
    assert session["sources"]["pointer_stream"] is True and session["sources"]["gaze_stream"] is False
    rows = eye_rows(report)
    assert rows and all(value == NOT_RECORDED == "not recorded" for _label, value in rows)
    assert dict(report["config"]["rows"])["Input"] == "Mouse, Dwell 0.3 s"  # no tracker named


def test_a_mouse_run_with_no_tracker_says_not_recorded_in_every_eye_cell_of_the_trial_table(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    finish_run(app)
    report = build_report(app.recorder.session_dir)
    columns = trial_columns(report)
    eye = [i for i, name in enumerate(columns) if name in ("Fixations", "Mean fix. dur. (s)", "Saccades",
           "Mean peak vel. (deg/s)", "Pupil (mm)", "Pupil change (mm)")]
    assert len(eye) == 6
    cells = trial_rows(report)[0]
    assert [cells[i].text for i in eye] == [NOT_RECORDED] * 6 and all(cells[i].key is None for i in eye)
    assert cells[0].text == "1" and cells[3].text == "Hit" and cells[4].text != DASH  # the rest is there
    page = ReportPage()
    page.set_report(report, test_name="Mouse 1")
    assert page.detailed.table.item(0, eye[0]).text() == NOT_RECORDED
    assert page.detailed.line_label.text() == "Eye data not recorded."
    assert not page.summary.path_check.isEnabled() and not page.summary.heat_check.isEnabled()
    assert build_report_html(report, test_name="T", evaluator="", notes="", map_image=None).count(
        f">{NOT_RECORDED}<"
    ) >= 6 + len(eye_rows(report))


def test_a_mouse_switch_run_reports_its_clicks_and_still_says_not_recorded(make_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    app = make_app(choice=MOUSE_SWITCH, client=None, trials=1)
    tick(app)
    look_at_target(app)
    tick(app)
    QTest.mouseClick(app.canvas, Qt.MouseButton.LeftButton)
    tick_until(app, lambda: app._shutdown_done)
    report = build_report(app.recorder.session_dir)
    assert (report["session"]["pointer"], report["session"]["selection"]) == ("mouse", "switch")
    assert report["trials"][0]["clicks"] == 1 and report["trials"][0]["click_errors"] == 0
    columns = trial_columns(report)
    assert columns[7:9] == ("Clicks", "Click errors") and len(columns) == 15
    cells = trial_rows(report)[0]
    assert [c.text for c in cells[7:9]] == ["1", "0"]
    assert [c.text for c in cells[9:]] == [NOT_RECORDED] * 6
    assert dict(report["config"]["rows"])["Input"] == "Mouse, Switch"


def test_a_mouse_switch_run_uses_the_mouses_left_button(make_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    app = make_app(choice=MOUSE_SWITCH, client=None, trials=1)
    assert app.input_mode == "switch" and app.canvas.switch_press_enabled
    tick(app)
    look_at_target(app)
    tick(app)
    assert app.task.trials == []  # pointing is not selecting
    QTest.mouseClick(app.canvas, Qt.MouseButton.LeftButton)
    tick(app)
    assert app.task.trials[0].is_hit and app.task.trials[0].clicks == 1
    assert len(kinds(app, "SWITCH_PRESS")) == 1
    assert not app.run_cursor.hidden  # the mouse is the pointer: its cursor must be seen
    assert app.metadata.input_mode == "switch"


def test_the_bar_says_mouse_pointer_and_does_not_report_a_missing_tracker(make_app):
    app = make_app(choice=MOUSE_DWELL, client=None, trials=1)
    tick(app, 3)
    text = app.view.run_bar.status_text()
    assert "Mouse pointer" in text and "tracker" not in text.lower() and "tracking" not in text.lower()
    assert text.startswith("Trial 1 of 1")


# -- with a tracker --------------------------------------------------------------------------


def test_a_mouse_run_with_a_tracker_records_the_gaze_alongside(make_app):
    app = make_app(choice=MOUSE_DWELL, trials=1)  # the default tracker: a second source
    assert app._gaze_recorded is True and app._pointer_is_mouse is True
    finish_run(app)
    assert files(app) >= {"pointer_stream.csv", "gaze_stream.csv", "all_gaze.csv", "eye_geometry.csv"}
    assert csv_rows(app.recorder.session_dir / "gaze_stream.csv")
    assert csv_rows(app.recorder.session_dir / "pointer_stream.csv")
    meta = metadata(app)
    assert meta["gaze_recorded"] is True and meta["input_mode"] == "mouse_dwell"
    report = build_report(app.recorder.session_dir)
    assert report["session"]["gaze_recorded"] is True and report["session"]["sources"]["gaze_stream"]
    assert all(value != NOT_RECORDED for _label, value in eye_rows(report))
    assert dict(report["config"]["rows"])["Input"].startswith("Mouse, gaze recorded (")
    assert dict(report["config"]["rows"])["Input"].endswith("), Dwell 0.3 s")


def test_the_run_uses_the_trackers_calibration_not_a_new_one(make_app, monkeypatch):
    no_calibration(monkeypatch)
    app = make_app(choice=MOUSE_DWELL, trials=1)  # a tracker with a preset calibration
    assert app.metadata.calibration_points == 5 and app.metadata.calibration_source != "not run"


def test_a_tracker_that_replays_a_file_is_recorded_alongside_too(make_app):
    app = make_app(choice=MOUSE_DWELL, trials=1, client=app_module.GazepointClient(replay_path=str(FIXTURE)))
    assert app._gaze_recorded is True
    tick(app, 3)
    app._shutdown()
    assert "gaze_stream.csv" in files(app) and "pointer_stream.csv" in files(app)


def test_a_gaze_run_writes_no_pointer_stream_and_records_gaze_as_before(make_app):
    app = make_app(choice={"pointer": "gaze", "selection": "dwell"}, trials=1)
    finish_run(app)
    assert "pointer_stream.csv" not in files(app) and "gaze_stream.csv" in files(app)
    meta = metadata(app)
    assert (meta["gaze_recorded"], meta["input_pointer"], meta["input_mode"]) == (True, "gaze", "eye")


# -- the mouse and the monitor geometry ---------------------------------------------------------------


def test_the_mouse_is_never_converted_by_the_trackers_monitor_geometry(make_app):
    app = make_app(choice=MOUSE_DWELL, trials=1)
    app.client.device_info = type("Info", (), {"screen_width": 1920, "screen_height": 1080,
                                               "screen_x": 0, "screen_y": 0, "rate_hz": 60,
                                               "bus": "", "serial": "", "tick_frequency": 1})()
    seen = []
    app.task.set_gaze_geometry = lambda *a: seen.append(a)
    app._sync_gaze_geometry()
    assert seen == []  # canvas-normalized already


# -- A9: the derived input_mode, and the labels -------------------------------------------------------------


@pytest.mark.parametrize(
    "choice, mode",
    [
        ({"pointer": "gaze", "selection": "dwell"}, "eye"),
        ({"pointer": "gaze", "selection": "switch"}, "gaze_switch"),
        ({"pointer": "mouse", "selection": "switch"}, "switch"),
        ({"pointer": "mouse", "selection": "dwell"}, "mouse_dwell"),
    ],
)
def test_metadata_input_mode_is_derived_from_the_two_choices(make_app, choice, mode):
    app = make_app(choice=choice, client=None if choice["pointer"] == "mouse" else "mouse", trials=1)
    assert app.input_mode == mode
    assert app.metadata.input_mode == mode == app.task.input_mode
    assert (app.metadata.input_pointer, app.metadata.input_selection) == (
        choice["pointer"], choice["selection"],
    )


@pytest.mark.parametrize("pointer, mode", [("gaze", "eye"), ("mouse", "mouse_follow")])
def test_follow_the_target_derives_eye_or_mouse_follow_and_has_no_selection(make_app, pointer, mode):
    app = make_app(
        "follow_moving", choice={"pointer": pointer}, trials=1,
        client=None if pointer == "mouse" else "mouse",
    )
    assert app.input_mode == mode
    assert app.metadata.input_selection is None and app.metadata.input_pointer == pointer


@pytest.mark.parametrize(
    "mode, label",
    [
        ("eye", "Gaze, Dwell"),
        ("gaze_switch", "Gaze, Switch"),
        ("switch", "Mouse, Switch"),
        ("mouse_dwell", "Mouse, Dwell"),
        ("mouse_follow", "Mouse"),
    ],
)
def test_report_config_labels_every_input_mode(mode, label):
    rows = dict(build_config_rows({}, {"input_mode": mode, "tasks": ["click_grid"]}))
    assert rows["Input"] == label  # no tracker named: nothing says gaze was recorded (nor the dwell time)


@pytest.mark.parametrize("mode", ["switch", "mouse_dwell", "mouse_follow"])
def test_a_mouse_mode_names_the_tracker_only_when_it_recorded(mode):
    meta = {"input_mode": mode, "gazepoint_model": "GP3HD", "gazepoint_rate_hz": 150, "tasks": ["click_grid"]}
    assert dict(build_config_rows({}, meta))["Input"] == dict(
        build_config_rows({}, {**meta, "gaze_recorded": False})
    )["Input"]
    assert "Mouse, gaze recorded (GP3HD, 150 Hz)" in dict(build_config_rows({}, {**meta, "gaze_recorded": True}))["Input"]


@pytest.mark.parametrize(
    "mode, selection",
    [("eye", "Dwell, threshold 0.8 s, refractory 0.5 s"), ("mouse_dwell", "Dwell, threshold 0.8 s, refractory 0.5 s"),
     ("gaze_switch", "Switch press (mouse/switch button), refractory 0.5 s"),
     ("switch", "Switch press (mouse/switch button), refractory 0.5 s")],
)
def test_the_selection_row_follows_the_mode(mode, selection):
    snapshot = {"live": {"dwell.threshold_ms": 800, "dwell.refractory_ms": 500}}
    assert dict(build_config_rows(snapshot, {"input_mode": mode}))["Selection"] == selection


# -- the not-recorded text -----------------------------------------------------------------------------------


def test_only_a_report_that_says_gaze_was_not_recorded_changes_its_eye_rows():
    base = {"summary": {"eye": {"fixations": {"count": 12, "mean_per_trial": 2.0}}}}
    plain = eye_rows(base)
    assert plain[0][1] == "12 (2.0 per trial)"
    for gaze_recorded in (None, True):  # an old folder, and a run with gaze
        assert eye_rows({**base, "session": {"gaze_recorded": gaze_recorded}}) == plain
    off = eye_rows({**base, "session": {"gaze_recorded": False}})
    assert [label for label, _v in off] == [label for label, _v in plain]
    assert {value for _l, value in off} == {NOT_RECORDED}
