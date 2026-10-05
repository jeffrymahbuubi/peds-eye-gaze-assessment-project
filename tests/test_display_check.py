"""SPEC-display-standard-check.md S6: the 1920x1080-at-100% display check, the
Setup-page warning text and Continue gate, and the per-session recording."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.app import AssessmentApp
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.engine.display_check import DisplayCheck, check_display
from src.ui.setup_page import SetupPage, _format_display_warning


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- S6.1 check_display ------------------------------------------------------


def test_standard_display():
    check = check_display(1920, 1080, 1.0)
    assert check == DisplayCheck(1920, 1080, 100, True)


@pytest.mark.parametrize(
    "lw,lh,dpr,expected",
    [
        (1280, 720, 1.5, (1920, 1080, 150)),
        (1536, 864, 1.25, (1920, 1080, 125)),
        (1366, 768, 1.0, (1366, 768, 100)),
        (2560, 1440, 1.0, (2560, 1440, 100)),
    ],
)
def test_nonstandard_displays(lw, lh, dpr, expected):
    check = check_display(lw, lh, dpr)
    assert (check.width_px, check.height_px, check.scale_percent) == expected
    assert check.standard is False


def test_rounding_is_stable_for_fractional_logical_sizes():
    # 1920 / 1.5 = 1280 exactly; 1079.6 x 1.0 must still round to 1080.
    assert check_display(1279.9999, 719.9999, 1.5) == check_display(1280, 720, 1.5)
    assert check_display(1920.4, 1079.6, 1.0).standard is True


# -- S6.2 warning text -------------------------------------------------------


def test_warning_empty_when_standard():
    assert _format_display_warning(check_display(1920, 1080, 1.0)) == ""


def test_warning_contains_values_and_settings_path():
    text = _format_display_warning(check_display(1280, 720, 1.5))
    assert "1920×1080 at 150%" in text
    assert "Settings → System → Display" in text
    assert "1920×1080 at 100%" in text


# -- S6.3 gate ---------------------------------------------------------------


def _ready_page(qapp) -> SetupPage:
    """A page with every other Continue condition satisfied."""
    page = SetupPage()
    page._client = SimpleNamespace(is_connected=lambda: True)
    page._calibration_result = object()
    page.subject_id_edit.setText("P001")
    page.sex_combo.setCurrentIndex(1)
    return page


def test_gate_standard_display_needs_no_box(qapp):
    page = _ready_page(qapp)
    page._apply_display_check(check_display(1920, 1080, 1.0))
    assert page.can_continue() is True
    assert page.continue_button.isEnabled()
    assert page.display_ack_checkbox.isHidden()
    assert page.display_acknowledged() is False


def test_gate_nonstandard_display_needs_box(qapp):
    page = _ready_page(qapp)
    page._apply_display_check(check_display(1280, 720, 1.5))
    assert not page.display_warning_alert.isHidden()
    assert page.can_continue() is False
    assert not page.continue_button.isEnabled()
    page.display_ack_checkbox.setChecked(True)
    assert page.can_continue() is True
    assert page.continue_button.isEnabled()
    assert page.display_acknowledged() is True


def test_display_change_unticks_box_and_standard_clears_it(qapp):
    page = _ready_page(qapp)
    page._apply_display_check(check_display(1280, 720, 1.5))
    page.display_ack_checkbox.setChecked(True)
    # Same values re-read (e.g. a showEvent): the box stays ticked.
    page._apply_display_check(check_display(1280, 720, 1.5))
    assert page.display_ack_checkbox.isChecked()
    # Different values: must be accepted again.
    page._apply_display_check(check_display(1536, 864, 1.25))
    assert not page.display_ack_checkbox.isChecked()
    assert page.can_continue() is False
    page.display_ack_checkbox.setChecked(True)
    page._apply_display_check(check_display(1920, 1080, 1.0))
    assert not page.display_ack_checkbox.isChecked()
    assert page.can_continue() is True


# -- S6.4 recording ----------------------------------------------------------


class _FakeRecorder:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        self.lines.append(message)


def _fake_app(width: int, height: int, dpr: float, ack: bool | None):
    geo = SimpleNamespace(width=lambda: width, height=lambda: height)
    screen = SimpleNamespace(
        geometry=lambda: geo,
        devicePixelRatio=lambda: dpr,
        refreshRate=lambda: 59.94,
        physicalSize=lambda: SimpleNamespace(width=lambda: 527.0, height=lambda: 296.0),
    )
    canvas = SimpleNamespace(
        width=lambda: width - 280,
        height=lambda: height - 75,
        screen=lambda: screen,
        mapToGlobal=lambda _p: SimpleNamespace(x=lambda: 0, y=lambda: 75),
    )
    app = SimpleNamespace(
        canvas=canvas,
        client=SimpleNamespace(device_info=None),
        config={"app": {}},
        metadata=SessionMetadata(
            subject_id="P001",
            session_id="s",
            started_ns=0,
            display_nonstandard_acknowledged=ack,
        ),
        recorder=_FakeRecorder(),
        _geometry_recorded=False,
    )
    app._record_display = lambda: AssessmentApp._record_display(app)
    return app


def test_record_geometry_writes_one_display_line_standard():
    app = _fake_app(1920, 1080, 1.0, False)
    AssessmentApp._record_geometry(app)
    display_lines = [m for m in app.recorder.lines if m.startswith("Display:")]
    assert display_lines == ["Display: 1920x1080 at 100% (standard)."]
    meta = app.metadata
    assert (meta.display_width_px, meta.display_height_px) == (1920, 1080)
    assert meta.display_scale_percent == 100
    assert meta.display_standard is True
    assert meta.display_nonstandard_acknowledged is False


def test_record_geometry_nonstandard_acknowledged():
    app = _fake_app(1280, 720, 1.5, True)
    AssessmentApp._record_geometry(app)
    display_lines = [m for m in app.recorder.lines if m.startswith("Display:")]
    assert display_lines == [
        "Display: 1920x1080 at 150% (NON-STANDARD, acknowledged by operator)."
    ]
    assert app.metadata.display_standard is False


def test_metadata_json_has_display_fields_and_standalone_ack_is_none(tmp_path):
    app = _fake_app(1920, 1080, 1.0, None)
    AssessmentApp._record_geometry(app)
    with SessionRecorder(app.metadata, output_root=tmp_path):
        pass
    data = json.loads((tmp_path / "s" / "metadata.json").read_text(encoding="utf-8"))
    assert data["display_width_px"] == 1920
    assert data["display_height_px"] == 1080
    assert data["display_scale_percent"] == 100
    assert data["display_standard"] is True
    assert data["display_nonstandard_acknowledged"] is None
    assert data["schema_version"] == SessionMetadata(subject_id="x", session_id="y", started_ns=0).schema_version
