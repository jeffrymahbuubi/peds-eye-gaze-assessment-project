"""SPEC-gazepoint-analysis-export-parity.md S10.6: eye_geometry.csv, the new
ENABLE_SEND_* records, the metadata device/quality fields and the fake server."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from src.data.analysis_export import (
    ALL_GAZE_COLUMNS,
    EYE_GEOMETRY_COLUMNS,
    median_eye_distance_mm,
    read_all_gaze,
    rec_to_eye_geometry_row,
)
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata
from src.inputs.gazepoint_client import GazepointClient

from .test_gazepoint_client import _wait_until, fake_server  # noqa: F401  (fixture)

_EXPECTED_HEADER = [
    "CNT", "TIME", "LEYEX", "LEYEY", "LEYEZ", "LPUPILD", "LPUPILV",
    "REYEX", "REYEY", "REYEZ", "RPUPILD", "RPUPILV",
    "LPOGX", "LPOGY", "LPOGV", "RPOGX", "RPOGY", "RPOGV",
]


def _metadata() -> SessionMetadata:
    return SessionMetadata(subject_id="P001", session_id="s_eye", started_ns=0)


def _rec(cnt: int, t: float, **extra: str) -> dict[str, str]:
    attrs = {"CNT": str(cnt), "TIME": f"{t:.5f}", "FPOGX": "0.5", "FPOGY": "0.5", "FPOGV": "1"}
    attrs.update(extra)
    return attrs


def _eye(lz: str | None, lv: str = "1", rz: str | None = None, rv: str = "1") -> dict[str, str]:
    out: dict[str, str] = {}
    if lz is not None:
        out.update(LEYEX="-0.03", LEYEY="0.01", LEYEZ=lz, LPUPILD="0.003", LPUPILV=lv)
    if rz is not None:
        out.update(REYEX="0.03", REYEY="0.01", REYEZ=rz, RPUPILD="0.003", RPUPILV=rv)
    return out


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


# -- S10.6.1 / criterion 1: enable resolution ------------------------------


def test_missing_new_enable_keys_default_on(fake_server):  # noqa: F811
    client = GazepointClient(enable={"time": True, "pog_fix": True})  # no eye_*/pog_* keys
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert _wait_until(lambda: "ENABLE_SEND_DATA" in fake_server.received_text())
        sent = fake_server.received_text()
        for record_id in (
            "ENABLE_SEND_EYE_LEFT", "ENABLE_SEND_EYE_RIGHT",
            "ENABLE_SEND_POG_LEFT", "ENABLE_SEND_POG_RIGHT",
        ):
            assert f'ID="{record_id}" STATE="1"' in sent, record_id
    finally:
        client.stop()


@pytest.mark.parametrize(
    ("key", "record_id"),
    [
        ("eye_left", "ENABLE_SEND_EYE_LEFT"),
        ("eye_right", "ENABLE_SEND_EYE_RIGHT"),
        ("pog_left", "ENABLE_SEND_POG_LEFT"),
        ("pog_right", "ENABLE_SEND_POG_RIGHT"),
    ],
)
def test_explicit_false_suppresses_each_new_record(fake_server, key, record_id):  # noqa: F811
    client = GazepointClient(enable={key: False})
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert _wait_until(lambda: "ENABLE_SEND_DATA" in fake_server.received_text())
        sent = fake_server.received_text()
        assert record_id not in sent
        # The other three new records and an unrelated old one are still on.
        assert sent.count("ENABLE_SEND_EYE_") + sent.count("ENABLE_SEND_POG_LEFT") + sent.count(
            "ENABLE_SEND_POG_RIGHT"
        ) == 3
        assert 'ID="ENABLE_SEND_COUNTER"' in sent
    finally:
        client.stop()


def test_existing_keys_behave_as_before(fake_server):  # noqa: F811
    """An explicit false on an old key still suppresses it and the old
    explicit trues still go out (the dict now only *overrides* defaults)."""
    client = GazepointClient(enable={"time": True, "pog_best": False, "cursor": True})
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert _wait_until(lambda: "ENABLE_SEND_DATA" in fake_server.received_text())
        sent = fake_server.received_text()
        assert 'ID="ENABLE_SEND_TIME"' in sent
        assert 'ID="ENABLE_SEND_CURSOR"' in sent
        assert "ENABLE_SEND_POG_BEST" not in sent
    finally:
        client.stop()


# -- S10.6.2 / criteria 2, 3: eye_geometry.csv ------------------------------


def _record(tmp_path: Path, recs: list[dict[str, str]], *, all_gaze: bool = True) -> Path:
    meta = _metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        if all_gaze:
            rec.open_all_gaze(media_name="click_static", tick_frequency=1000)
        rec.open_eye_geometry()
        for i, attrs in enumerate(recs):
            rec.record_raw(i * 10_000_000, attrs)
    return tmp_path / meta.session_id


def test_eye_geometry_header_rows_cnt_and_time_match_all_gaze(tmp_path: Path):
    recs = [
        _rec(0, 100.00, **_eye("0.65", rz="0.66"), LPOGX="0.4", LPOGY="0.5", LPOGV="1"),
        _rec(1, 100.01, **_eye("0.65")),  # right eye + POG attrs absent
        _rec(2, 100.02),  # nothing eye-related
    ]
    session_dir = _record(tmp_path, recs)
    header, rows = _read_csv(session_dir / "eye_geometry.csv")
    assert header == _EXPECTED_HEADER
    assert list(EYE_GEOMETRY_COLUMNS) == _EXPECTED_HEADER

    _gaze_header, gaze_rows = read_all_gaze(session_dir / "all_gaze.csv")
    assert len(rows) == len(gaze_rows) == 3
    for eye_row, gaze_row in zip(rows, gaze_rows):
        assert eye_row["CNT"] == gaze_row["CNT"]
        assert eye_row["TIME"] == gaze_row["TIME"]
    assert [r["TIME"] for r in rows] == ["0.00000", "0.01000", "0.02000"]  # session-relative

    assert rows[0]["LEYEZ"] == "0.65" and rows[0]["REYEZ"] == "0.66"
    assert rows[0]["LPOGX"] == "0.4" and rows[0]["RPOGX"] == ""
    # Missing attributes are empty cells, never invented zeros.
    assert rows[1]["REYEZ"] == "" and rows[1]["LPOGV"] == ""
    assert all(rows[2][c] == "" for c in _EXPECTED_HEADER[2:])


def test_eye_geometry_uses_t_ns_when_device_time_absent(tmp_path: Path):
    recs = [{"CNT": "0"}, {"CNT": "1"}]
    session_dir = _record(tmp_path, recs)
    _h, rows = _read_csv(session_dir / "eye_geometry.csv")
    _gh, gaze_rows = read_all_gaze(session_dir / "all_gaze.csv")
    assert [r["TIME"] for r in rows] == ["0.00000", "0.01000"]
    assert [r["TIME"] for r in rows] == [r["TIME"] for r in gaze_rows]


def test_eye_geometry_works_without_all_gaze(tmp_path: Path):
    session_dir = _record(tmp_path, [_rec(0, 5.0), _rec(1, 5.1)], all_gaze=False)
    assert not (session_dir / "all_gaze.csv").exists()
    _h, rows = _read_csv(session_dir / "eye_geometry.csv")
    assert [r["TIME"] for r in rows] == ["0.00000", "0.10000"]


def test_not_opened_means_no_file(tmp_path: Path):
    meta = _metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.open_all_gaze(media_name="x", tick_frequency=1)
        rec.record_raw(0, _rec(0, 1.0))
    assert not (tmp_path / meta.session_id / "eye_geometry.csv").exists()


def test_all_gaze_layout_and_gaze_stream_header_unchanged(tmp_path: Path):
    session_dir = _record(tmp_path, [_rec(0, 1.0)])
    gaze_header, _rows = read_all_gaze(session_dir / "all_gaze.csv")
    assert len(gaze_header) == len(ALL_GAZE_COLUMNS) == 62
    assert not any(c in gaze_header for c in ("LEYEZ", "LPOGX"))
    stream_header = (session_dir / "gaze_stream.csv").read_text(encoding="utf-8").splitlines()[0]
    assert stream_header == "t_ns,x,y,valid,fixation_id,fix_duration_s,pupil_left,pupil_right"


def test_rec_to_eye_geometry_row_formats_time():
    row = rec_to_eye_geometry_row({"CNT": "7", "LEYEZ": "0.7"}, time_s=1.234567)
    assert row[0] == "7" and row[1] == "1.23457" and row[4] == "0.7"
    assert len(row) == len(EYE_GEOMETRY_COLUMNS)


# -- S10.6.3 / criterion 4: measured eye distance --------------------------


def _write_geometry(tmp_path: Path, recs: list[dict[str, str]]) -> Path:
    session_dir = _record(tmp_path, recs, all_gaze=False)
    return session_dir / "eye_geometry.csv"


def test_median_distance_means_valid_eyes_then_medians_rows(tmp_path: Path):
    path = _write_geometry(
        tmp_path,
        [
            _rec(0, 1.0, **_eye("0.60", rz="0.70")),  # both valid -> 0.65
            _rec(1, 1.1, **_eye("0.80", lv="0", rz="0.62")),  # left invalid -> 0.62
            _rec(2, 1.2, **_eye("0.64", rz="0.00")),  # right value 0 -> left only 0.64
            _rec(3, 1.3, **_eye("0.50", lv="0", rz="0.90", rv="0")),  # none valid -> skipped
            _rec(4, 1.4),  # no eye attrs -> skipped
        ],
    )
    # per-row: 0.65, 0.62, 0.64 -> median 0.64 m -> 640 mm
    assert median_eye_distance_mm(path) == 640.0


def test_median_distance_even_count_and_rounding(tmp_path: Path):
    path = _write_geometry(
        tmp_path, [_rec(0, 1.0, **_eye("0.6004")), _rec(1, 1.1, **_eye("0.6015"))]
    )
    assert median_eye_distance_mm(path) == 601.0  # 600.95 mm -> 601


def test_median_distance_none_when_no_valid_rows_or_no_file(tmp_path: Path):
    path = _write_geometry(
        tmp_path, [_rec(0, 1.0, **_eye("0.65", lv="0")), _rec(1, 1.1)]
    )
    assert median_eye_distance_mm(path) is None
    assert median_eye_distance_mm(tmp_path / "nope.csv") is None


def test_metadata_has_new_optional_fields_default_none():
    meta = _metadata()
    for name in (
        "gazepoint_rate_hz", "gazepoint_bus", "gazepoint_serial",
        "display_refresh_hz", "measured_sample_rate_hz", "measured_eye_distance_mm_median",
    ):
        assert getattr(meta, name) is None
        assert name in meta.to_dict()
    assert "device_pixel_ratio" not in {f.name for f in fields(meta)}


def test_metadata_json_round_trips_new_fields(tmp_path: Path):
    meta = _metadata()
    meta.gazepoint_rate_hz = 150
    meta.gazepoint_bus = "USB3"
    meta.measured_eye_distance_mm_median = 640.0
    with SessionRecorder(meta, output_root=tmp_path):
        pass
    data = json.loads((tmp_path / meta.session_id / "metadata.json").read_text(encoding="utf-8"))
    assert data["gazepoint_rate_hz"] == 150
    assert data["gazepoint_bus"] == "USB3"
    assert data["gazepoint_serial"] is None
    assert data["measured_eye_distance_mm_median"] == 640.0


# -- criterion 5: v1.0.0 metadata still loads ------------------------------


def test_v1_metadata_without_new_fields_still_loads(tmp_path: Path):
    from src.data.analysis_export import compute_saccade_metrics

    v1 = {
        "subject_id": "P001", "session_id": "old", "started_ns": 0, "schema_version": 1,
        "screen_width_px": 1920, "screen_height_px": 1080,
        "screen_physical_width_mm": 527.0, "screen_physical_height_mm": 296.0,
        "viewing_distance_mm": 650.0,
    }
    (tmp_path / "metadata.json").write_text(json.dumps(v1), encoding="utf-8")
    loaded = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert loaded.get("gazepoint_rate_hz") is None
    assert loaded.get("measured_eye_distance_mm_median") is None
    assert compute_saccade_metrics(tmp_path, loaded)["n_saccades"] == 0
    # And it maps onto the dataclass (unknown-new-field-free) as well.
    known = {f.name for f in fields(SessionMetadata)}
    assert SessionMetadata(**{k: v for k, v in v1.items() if k in known}).gazepoint_serial is None


# -- S10.6.4: fake server ---------------------------------------------------


@pytest.fixture(scope="module")
def fake_server_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "fake_gazepoint_server.py"
    spec = importlib.util.spec_from_file_location("_fake_gp_server", path)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["fake_gazepoint_server.py"]  # the module reads its port from argv
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


def test_fake_server_emits_only_the_enabled_records(fake_server_module):
    attrs = fake_server_module.eye_geometry_attrs
    assert attrs(0.5, 0.5, set()) == ""
    left = attrs(0.5, 0.5, {"ENABLE_SEND_EYE_LEFT", "ENABLE_SEND_POG_LEFT"})
    assert 'LEYEZ="0.65000"' in left and 'LPUPILV="1"' in left and 'LPOGV="1"' in left
    assert "REYE" not in left and "RPOG" not in left
    everything = attrs(
        0.5, 0.5,
        {"ENABLE_SEND_EYE_LEFT", "ENABLE_SEND_EYE_RIGHT",
         "ENABLE_SEND_POG_LEFT", "ENABLE_SEND_POG_RIGHT"},
    )
    parsed = dict(__import__("re").findall(r'(\w+)="([^"]*)"', everything))
    assert set(parsed) == set(EYE_GEOMETRY_COLUMNS) - {"CNT", "TIME"}
    assert float(parsed["LPOGX"]) < 0.5 < float(parsed["RPOGX"])


# -- S10.6.9: pre-run records, and the measured device rate ------------------


def test_clear_raw_drops_pre_run_records_from_both_files(fake_server, tmp_path: Path):  # noqa: F811
    """Records queued from Connect onwards (before the run) must not reach
    all_gaze.csv / eye_geometry.csv: the run's first record is row 0."""
    client = GazepointClient(reconnect_interval_s=0.1)
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    try:
        fake_server.wait_for_connection()
        for x in (0.1, 0.2):
            fake_server.send_rec(x, 0.5)  # "Setup" records
        assert _wait_until(lambda: len(client._raw_queue) >= 2)
        client.clear_raw()  # what AssessmentApp does as the run starts recording
        assert client.drain_raw() == []
        for x in (0.7, 0.8):
            fake_server.send_rec(x, 0.5)  # the run's records
        assert _wait_until(lambda: len(client._raw_queue) >= 2)
        meta = _metadata()
        with SessionRecorder(meta, output_root=tmp_path) as rec:
            rec.open_all_gaze(media_name="x", tick_frequency=1)
            rec.open_eye_geometry()
            for t_ns, attrs in client.drain_raw():
                rec.record_raw(t_ns, attrs)
        session_dir = tmp_path / meta.session_id
        _h, gaze_rows = read_all_gaze(session_dir / "all_gaze.csv")
        _h2, eye_rows = _read_csv(session_dir / "eye_geometry.csv")
        assert [r["FPOGX"] for r in gaze_rows] == ["0.7", "0.8"]
        assert len(eye_rows) == 2 and eye_rows[0]["TIME"] == "0.00000"
    finally:
        client.stop()


def test_app_clears_raw_queue_before_opening_the_raw_files():
    import inspect

    from src.app import AssessmentApp

    src = inspect.getsource(AssessmentApp.__init__)
    assert src.index("self.client.clear_raw()") < src.index("self.recorder.open_all_gaze(")
    assert src.index("self.client.clear_raw()") < src.index("self.recorder.open_eye_geometry()")


def test_measured_sample_rate_is_records_over_time_span(tmp_path: Path):
    from src.data.analysis_export import measured_sample_rate_hz

    # 151 records at 150 Hz: 150 intervals over 1.0 s.
    recs = [_rec(i, 50.0 + i / 150.0) for i in range(151)]
    session_dir = _record(tmp_path, recs)
    assert measured_sample_rate_hz(session_dir / "eye_geometry.csv") == 150.0
    # all_gaze.csv carries the TIME(<start>) header suffix; same answer.
    assert measured_sample_rate_hz(session_dir / "all_gaze.csv") == 150.0


def test_measured_sample_rate_none_for_too_few_rows_or_missing_file(tmp_path: Path):
    from src.data.analysis_export import measured_sample_rate_hz

    one = _record(tmp_path, [_rec(0, 1.0)])
    assert measured_sample_rate_hz(one / "eye_geometry.csv") is None
    assert measured_sample_rate_hz(tmp_path / "nope.csv") is None
