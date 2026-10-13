"""SPEC-gaze-stability-and-positioning.md 4.7 and acceptance A9 (the parts a test can check):
the head-position block sits in the Setup page's Calibration card and at the end of the Start
page's clinician text (gaze tests only, hidden for Pointer = Mouse), gates nothing, and the run's
``metadata.json`` records ``head_position_at_start``; and the fake tracker's head drift. The live
look is the hub's. Offscreen Qt, a scratch folder."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from src.data.schema import SessionMetadata
from src.engine.config import load_task_config
from src.inputs import head_position as hp
from src.inputs.gazepoint_client import parse_attrs
from src.inputs.head_position import EyePosition, HeadState, eye_position_from_attrs
from src.ui.dashboard_flow import Flow
from src.ui.page_layout import BesideRow
from src.ui.setup_page import SetupPage
from src.ui.start_test_page import StartTestPage
from tests.dashboard_fixtures import new_test
from tests.run_flow_fixtures import (
    close_run_window,
    configure_fast,
    make_run_window,
    open_start,
    start_run,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def eyes_at(z_cm=65.0, dx_cm=0.0, *, at=None):
    """Both eyes ``z_cm`` away and ``dx_cm`` off centre, received at ``at`` (default: just now)."""
    cx, cy, z = (hp.CENTRED_X_CM + dx_cm) / 100.0, hp.CENTRED_Y_CM / 100.0, z_cm / 100.0
    return EyePosition((cx - 0.03, cy, z), (cx + 0.03, cy, z), time.monotonic() if at is None else at)


class Tracker:
    """A connected tracker with the head-position accessor, its eyes the test's to change."""

    def __init__(self, eyes=None):
        self.eyes = eyes

    def is_connected(self):
        return True

    def latest_eye_position(self):
        return self.eyes() if callable(self.eyes) else self.eyes


# -- the Setup page's Calibration card (4.7) ---------------------------------------------------------------


def test_the_calibration_card_holds_the_head_position_panel_beside_the_buttons(qapp):
    page = SetupPage()
    panel = page.head_position_panel
    assert page.calibration_card.isAncestorOf(panel)
    # Beside the four buttons and the badge (one BesideRow holds both), not inside their line.
    row = panel.parentWidget()
    assert isinstance(row, BesideRow) and row.isAncestorOf(page.do_calibration_button)
    assert not panel.isAncestorOf(page.do_calibration_button)
    assert page.calibration_card.isAncestorOf(page.calibration_details_section)


def test_a_setup_page_goes_with_its_last_reference_not_with_the_garbage_collector(qapp):
    """The page hands its own bound method to the panel it owns. Held strongly that is a cycle
    between two Qt widgets, which the garbage collector tore down in an order that crashed PySide
    (an access violation in a later test); the panel holds a bound method weakly."""
    page = SetupPage()
    ref = weakref.ref(page)
    del page
    assert ref() is None


def test_setup_says_the_tracker_is_not_connected_until_there_is_one(qapp):
    page = SetupPage()
    assert page.head_position_input() == (False, None)
    assert page.head_position_panel.reading() is hp.NOT_CONNECTED
    assert page.head_position_panel.status_badge.text() == "Tracker not connected"
    page._client = SimpleNamespace(is_connected=lambda: False)
    assert page.head_position_input() == (False, None)  # the link is down: not the same as no eyes


def test_a_connected_tracker_gives_its_latest_eye_position_or_none_yet(qapp):
    page = SetupPage()
    position = eyes_at()
    page._client = Tracker(position)
    assert page.head_position_input() == (True, position)
    page._client = Tracker(None)
    assert page.head_position_input() == (True, None)  # connected, no REC yet: "No eyes"
    page._client = SimpleNamespace(is_connected=lambda: True)  # a client with no eye accessor
    assert page.head_position_input() == (True, None)
    page.head_position_panel.poll()
    assert page.head_position_panel.status_badge.text() == "No eyes detected"


def test_the_setup_panel_follows_the_clients_eyes(qapp):
    page = SetupPage()
    panel, now = page.head_position_panel, [0.0]
    panel._clock = lambda: now[0]
    tracker = Tracker(lambda: eyes_at(z_cm=tracker.z_cm, at=now[0]))
    tracker.z_cm = 65.0
    page._client = tracker
    panel.poll()
    assert panel.status_badge.text() == "Good position, 65 cm"
    tracker.z_cm = 45.0
    now[0] = 0.1
    panel.poll()
    assert panel.reading().state is HeadState.GREEN  # the colour waits 0.3 s
    now[0] = 0.5
    panel.poll()
    assert panel.reading().state is HeadState.RED
    assert panel.status_badge.text() == "Move back, 45 cm"


def test_the_setup_panel_gates_nothing(qapp):
    """Whatever the head does, Do Calibration, Continue and the Start gate are as they were."""
    page = SetupPage()
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    page._client = Tracker(eyes_at())
    page._calibration_result = object()
    page.head_position_panel.poll()
    baseline = (page.run_blockers(), page.can_continue(), page.do_calibration_button.isEnabled())
    for tracker_eyes in (eyes_at(z_cm=45.0), eyes_at(dx_cm=30.0), None, eyes_at(z_cm=65.0)):
        page._client.eyes = tracker_eyes
        page.head_position_panel.poll()
        assert (page.run_blockers(), page.can_continue(), page.do_calibration_button.isEnabled()) == baseline
    assert not [b for b in baseline[0] if "head" in b.lower() or "position" in b.lower()]


def test_the_beside_row_stacks_its_side_widget_in_a_narrow_window(qapp):
    main, side = QWidget(), QWidget()
    side.setFixedSize(240, 200)
    row = BesideRow(main, side, stack_below=640)
    row.resize(900, 300)
    row.show()
    qapp.processEvents()
    assert not row.stacked() and side.geometry().left() >= main.geometry().right()
    row.resize(500, 300)
    qapp.processEvents()
    assert row.stacked() and side.geometry().top() >= main.geometry().bottom()
    row.resize(900, 300)
    qapp.processEvents()
    assert not row.stacked()


# -- the Start page (4.7) ----------------------------------------------------------------------------------------


def start_page(pointer="gaze", task_id="click_grid", source=None):
    cfg = load_task_config(task_id)
    cfg["task"]["input"] = {"pointer": pointer, "selection": "dwell"}
    page = StartTestPage()
    page.set_head_position_source(source if source is not None else (lambda: (True, eyes_at())))
    page.set_test(test_name="Test 1", task_id=task_id, cfg=cfg)
    return page


def test_the_start_page_ends_the_clinician_text_with_the_head_position(qapp):
    page = start_page()
    layout = page._clinician_box_layout
    assert page.clinician_box.isAncestorOf(page.head_panel)
    assert layout.indexOf(page.head_panel) > layout.indexOf(page.clinician_layout)
    assert layout.indexOf(page.head_panel) == layout.count() - 1  # the last thing in the block
    assert not page.card.isAncestorOf(page.head_panel)  # not read aloud to the child
    assert page.head_panel.title_label.text() == "Head position"


def test_the_head_position_is_for_gaze_tests_only(qapp):
    gaze = start_page(pointer="gaze")
    assert not gaze.head_panel.isHidden()
    mouse = start_page(pointer="mouse")
    assert mouse.head_panel.isHidden()
    assert mouse.head_position_at_start() is None
    # The same page, given another test, follows that test.
    cfg = load_task_config("click_grid")
    cfg["task"]["input"] = {"pointer": "gaze", "selection": "dwell"}
    mouse.set_test(test_name="Test 2", task_id="click_grid", cfg=cfg)
    assert not mouse.head_panel.isHidden() and mouse.head_position_at_start() is not None
    cfg["task"]["input"] = {"pointer": "mouse", "selection": "dwell"}
    mouse.set_test(test_name="Test 3", task_id="click_grid", cfg=cfg)
    assert mouse.head_panel.isHidden()


def test_the_start_page_says_the_tracker_is_not_connected_without_a_source(qapp):
    page = StartTestPage()
    page.set_test(test_name="Test 1", task_id="click_grid", cfg=load_task_config("click_grid"))
    assert page.head_panel.status_badge.text() == "Tracker not connected"
    assert page.head_position_at_start()["state"] == "not_connected"


def test_the_start_page_timer_runs_only_while_it_is_shown(qapp):
    page = start_page()
    assert not page.head_panel._timer.isActive()
    page.show()
    assert page.head_panel._timer.isActive()
    page.hide()
    assert not page.head_panel._timer.isActive()


def test_the_start_page_head_position_gates_nothing(qapp):
    page = StartTestPage()
    page.set_blockers_provider(lambda: [])
    cfg = load_task_config("click_grid")
    page.set_test(test_name="Test 1", task_id="click_grid", cfg=cfg)
    for eyes in (eyes_at(z_cm=45.0), eyes_at(dx_cm=30.0), None):
        page.set_head_position_source(lambda eyes=eyes: (True, eyes))
        page.head_panel.poll()
        assert page.refresh_blockers() == []
        assert page.start_button.isEnabled() and page.practice_button.isEnabled()
    page.set_head_position_source(lambda: (False, None))  # not even a dropped tracker
    page.head_panel.poll()
    assert page.start_button.isEnabled() and page.practice_button.isEnabled()
    started = []
    page.startRequested.connect(lambda: started.append(1))
    page.start_button.click()
    assert started == [1]


def test_the_page_hands_the_run_the_reading_as_it_is_now(qapp):
    box = {"eyes": eyes_at(z_cm=65.0)}
    page = start_page(source=lambda: (True, box["eyes"]))
    assert page.head_position_at_start() == {
        "state": "green", "z_cm": 65.0, "centre_x_cm": 0.0, "centre_y_cm": 0.0,
    }
    box["eyes"] = None  # the eyes drop the instant Start is pressed (a blink, say)
    # The operator still sees green (no eyes shows only after 0.5 s), and that is what is recorded.
    assert page.head_position_at_start()["state"] == "green"


# -- metadata.json: head_position_at_start (4.7) ---------------------------------------------------------------------------


@pytest.fixture
def rig(qapp, tmp_path, monkeypatch):
    win, mouse, pointing = make_run_window(tmp_path, monkeypatch)
    yield win, mouse, pointing
    close_run_window(win)


def metadata_json(app) -> dict:
    return json.loads((app.recorder.session_dir / "metadata.json").read_text(encoding="utf-8"))


def test_start_records_the_head_position_in_the_runs_metadata(rig):
    win, mouse, _pointing = rig
    mouse.latest_eye_position = lambda: eyes_at(z_cm=64.0, dx_cm=2.0)  # the Setup tracker's eyes
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse)
    expected = {"state": "green", "z_cm": 64.0, "centre_x_cm": 2.0, "centre_y_cm": 0.0}
    assert app.metadata.head_position_at_start == expected
    assert metadata_json(app)["head_position_at_start"] == expected  # on disk from the first write


def test_a_red_or_missing_head_is_recorded_too_and_never_stops_the_run(rig):
    win, mouse, _pointing = rig
    mouse.latest_eye_position = lambda: eyes_at(z_cm=45.0)
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse)
    assert win.flow is Flow.RUN
    assert metadata_json(app)["head_position_at_start"]["state"] == "red"
    assert metadata_json(app)["head_position_at_start"]["z_cm"] == 45.0


def test_no_eyes_at_start_records_no_eyes_with_nulls(rig):
    win, mouse, _pointing = rig  # this mouse has no eye accessor: connected, nothing seen
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse)
    assert metadata_json(app)["head_position_at_start"] == {
        "state": "no_eyes", "z_cm": None, "centre_x_cm": None, "centre_y_cm": None,
    }


def test_a_mouse_test_shows_no_head_position_and_records_none(rig):
    win, mouse, _pointing = rig
    mouse.latest_eye_position = lambda: eyes_at()
    test = new_test(win)
    configure_fast(win, test, trials=1, input={"pointer": "mouse", "selection": "dwell"})
    page = open_start(win, test)
    assert page.head_panel.isHidden()
    app = start_run(win, mouse)
    assert app.metadata.head_position_at_start is None
    assert metadata_json(app)["head_position_at_start"] is None


def test_a_practice_run_is_given_no_head_position(rig):
    win, mouse, _pointing = rig
    mouse.latest_eye_position = lambda: eyes_at()
    test = new_test(win)
    configure_fast(win, test, trials=1)
    open_start(win, test)
    app = start_run(win, mouse, button="practice_button")
    assert app.run_mode == "practice" and app.metadata.head_position_at_start is None


def test_the_metadata_field_is_additive_and_an_older_file_loads(tmp_path: Path):
    meta = SessionMetadata(subject_id="P001", session_id="s", started_ns=0)
    assert meta.head_position_at_start is None and "head_position_at_start" in meta.to_dict()
    old = {"subject_id": "P001", "session_id": "old", "started_ns": 0, "schema_version": 1}
    (tmp_path / "metadata.json").write_text(json.dumps(old), encoding="utf-8")
    loaded = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert loaded.get("head_position_at_start") is None
    assert SessionMetadata(**old).head_position_at_start is None


# -- the fake tracker's head drift (4.5) -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake():
    path = Path(__file__).resolve().parents[1] / "tools" / "fake_gazepoint_server.py"
    spec = importlib.util.spec_from_file_location("_fake_gp_server_head", path)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["fake_gazepoint_server.py"]  # the module reads its port from argv
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


def parsed(fake, pose):
    """The eye attributes the fake sends for ``pose``, parsed the way the client does."""
    line = fake.eye_geometry_attrs(
        0.5, 0.5, {"ENABLE_SEND_EYE_LEFT", "ENABLE_SEND_EYE_RIGHT"}, pose
    )
    return parse_attrs(f"<REC {line}/>")[1]


def test_the_fake_starts_with_a_centred_head_at_65_cm(fake):
    left, right, valid = fake.head_pose(0.0)
    assert valid is True
    assert left[2] == right[2] == pytest.approx(0.65)
    assert (left[0] + right[0]) / 2 == pytest.approx(fake.HEAD_CENTRE_M[0])
    assert (left[1] + right[1]) / 2 == pytest.approx(fake.HEAD_CENTRE_M[1])


def test_the_fake_loses_the_eyes_for_3_s_every_20_s(fake):
    for start in (0.0, 20.0, 40.0):
        assert fake.head_pose(start + 16.9).eyes_valid is True
        assert fake.head_pose(start + 17.0).eyes_valid is False
        assert fake.head_pose(start + 19.9).eyes_valid is False
        assert fake.head_pose(start + 20.0).eyes_valid is True
    gap = parsed(fake, fake.head_pose(18.0))
    assert gap["LPUPILV"] == gap["RPUPILV"] == "0"
    assert float(gap["LEYEZ"]) == float(gap["REYEZ"]) == 0.0  # zeros, as a device sends them
    seen = parsed(fake, fake.head_pose(5.0))
    assert seen["LPUPILV"] == seen["RPUPILV"] == "1"


def test_a_gap_reads_as_no_eyes_in_the_model_and_the_client_parser(fake):
    attrs = parsed(fake, fake.head_pose(18.0))
    position = eye_position_from_attrs(attrs, 0.0)
    assert position.left is None and position.right is None
    assert hp.assess(position, 0.0) is hp.NO_EYES


def test_the_default_pose_is_the_old_still_head(fake):
    still = fake.eye_geometry_attrs(0.5, 0.5, {"ENABLE_SEND_EYE_LEFT", "ENABLE_SEND_EYE_RIGHT"})
    assert 'LEYEX="-0.03000" LEYEY="0.01000" LEYEZ="0.65000"' in still
    assert 'REYEX="0.03000" REYEY="0.01000" REYEZ="0.65000"' in still


def test_the_fakes_drift_passes_through_every_state_of_the_widget(fake, monkeypatch):
    # With the widget's centre where the fake's is, over a few minutes the head is green, orange
    # and red, and the gaps are "no eyes" (the widget's own rules, 4.6).
    monkeypatch.setattr(hp, "CENTRED_X_CM", fake.HEAD_CENTRE_M[0] * 100.0)
    monkeypatch.setattr(hp, "CENTRED_Y_CM", fake.HEAD_CENTRE_M[1] * 100.0)
    states, hints = set(), set()
    for step in range(0, 4 * 83 * 2):  # four Z periods, every half second
        pose = fake.head_pose(step * 0.5)
        reading = hp.assess(eye_position_from_attrs(parsed(fake, pose), 0.0), 0.0)
        states.add(reading.state)
        hints.add(reading.hint)
    assert states == {HeadState.GREEN, HeadState.ORANGE, HeadState.RED, HeadState.NO_EYES}
    assert {hp.HINT_TOO_CLOSE, hp.HINT_TOO_FAR, hp.HINT_LEFT, hp.HINT_RIGHT, hp.HINT_UP, hp.HINT_DOWN} <= hints


def test_the_fakes_head_tilts(fake, monkeypatch):
    rolls = []
    for step in range(0, 60 * 2):
        position = eye_position_from_attrs(parsed(fake, fake.head_pose(step * 0.5)), 0.0)
        if position.left and position.right:
            rolls.append(hp.assess(position, 0.0).roll_deg)
    assert max(rolls) > 5.0 and min(rolls) < -5.0

