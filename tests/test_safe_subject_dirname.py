"""SPEC-compass-task-flow.md 4A.9 / AA13: a Subject ID can never escape its folder."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.engine.session_naming import next_run_number, next_session_id, safe_subject_dirname
from src.engine.settings_profile import (
    known_subject_ids,
    save_settings_profile,
    settings_profile_dir,
    subject_settings_dir,
)
from src.engine.subject_tests import create_test, subject_tests_dir
from src.ui.setup_page import _subject_calibration_dir

HOSTILE_IDS = [
    "..\\x",
    "../x",
    "A/B",
    "A\\B",
    "CON",
    "con",
    "con.txt",
    "COM1",
    "lpt9.log",
    "NUL ",
    "x.",
    "x..",
    "..",
    ".",
    "",
    " ",
    "a:b*c?d",
    '"q"<w>|e',
    "x\x00y\ttab\nnl",
    "a" * 200,
    " " * 100 + "x",
    "é",  # decomposed é
]

ORDINARY_IDS = ["TESTING", "P001", "Jeffry Lin", "a-b_c.d", "S 01", "子供01", "x" * 80]

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')


@pytest.mark.parametrize("subject_id", HOSTILE_IDS)
def test_hostile_ids_map_to_one_safe_folder_name(subject_id):
    name = safe_subject_dirname(subject_id)
    assert name and name not in (".", "..")
    assert not _ILLEGAL.search(name)
    assert not name.endswith((".", " "))
    assert name != subject_id  # anything that needed changing carries the hash suffix
    assert re.search(r"~[0-9a-f]{6}$", name)
    assert len(name) <= 88  # 80 + "_" prefix + "~" + 6 hex


@pytest.mark.parametrize("subject_id", HOSTILE_IDS)
def test_hostile_ids_stay_inside_the_tests_folder(tmp_path, subject_id):
    directory = subject_tests_dir(tmp_path, subject_id)
    assert directory.parent == tmp_path / "_tests"
    assert (tmp_path / "_tests").resolve() in directory.resolve().parents


def test_hostile_ids_really_create_one_folder_inside_the_tests_folder(tmp_path):
    for subject_id in ("..\\x", "A/B", "CON", "x.", "a" * 200):
        create_test(tmp_path, subject_id, "click_static")
    created = sorted(p.name for p in (tmp_path / "_tests").iterdir())
    assert len(created) == 5  # one folder each, nothing nested, nothing outside
    assert [p.name for p in tmp_path.iterdir()] == ["_tests"]


@pytest.mark.parametrize("subject_id", ORDINARY_IDS)
def test_ordinary_ids_come_back_unchanged(subject_id):
    assert safe_subject_dirname(subject_id) == subject_id


def test_existing_settings_and_calibration_folders_still_match(tmp_path):
    assert subject_settings_dir(tmp_path, "TESTING") == tmp_path / "_settings" / "TESTING"
    assert settings_profile_dir(tmp_path, "TESTING", "click_grid") == (
        tmp_path / "_settings" / "TESTING" / "click_grid"
    )
    assert _subject_calibration_dir(tmp_path, "TESTING") == tmp_path / "_calibrations" / "TESTING"
    assert next_session_id(tmp_path, "TESTING", "click_grid", date_str="2026-10-06") == (
        "2026-10-06_TESTING_click_grid_run1"
    )


def test_slash_and_underscore_do_not_share_a_folder():
    assert safe_subject_dirname("A_B") == "A_B"
    assert safe_subject_dirname("A/B") != "A_B"
    assert safe_subject_dirname("A/B") != safe_subject_dirname("A|B")  # both sanitise to A_B
    assert safe_subject_dirname("A/B") == safe_subject_dirname("A/B")  # and it is stable


def test_unicode_is_nfc_normalised():
    decomposed = "é"
    assert safe_subject_dirname("é") == "é"
    assert safe_subject_dirname(decomposed).startswith("é~")


def test_device_names_get_a_prefix():
    assert safe_subject_dirname("CON").startswith("_CON~")
    assert safe_subject_dirname("com3.txt").startswith("_com3.txt~")
    assert safe_subject_dirname("CONSOLE") == "CONSOLE"  # not a device name
    assert safe_subject_dirname("COM10") == "COM10"


def test_all_four_call_sites_use_the_safe_name(tmp_path):
    subject_id = "A/B"
    safe = safe_subject_dirname(subject_id)
    assert subject_tests_dir(tmp_path, subject_id) == tmp_path / "_tests" / safe
    assert subject_settings_dir(tmp_path, subject_id) == tmp_path / "_settings" / safe
    assert _subject_calibration_dir(tmp_path, subject_id) == tmp_path / "_calibrations" / safe

    (tmp_path / f"2026-10-06_{safe}_click_static_run1").mkdir()
    assert next_run_number(tmp_path, subject_id, "click_static", date_str="2026-10-06") == 2
    session_id = next_session_id(tmp_path, subject_id, "click_static", date_str="2026-10-06")
    assert session_id == f"2026-10-06_{safe}_click_static_run2"
    assert Path(tmp_path / session_id).parent == tmp_path


def test_settings_profile_for_a_hostile_id_lands_in_its_own_folder(tmp_path):
    path = save_settings_profile(tmp_path, "..\\x", "click_static", {"dwell.threshold_ms": 900})
    assert path.parent.parent.parent == tmp_path / "_settings"
    assert (tmp_path / "_settings").resolve() in path.resolve().parents


def test_known_subject_ids_also_lists_subjects_that_only_have_tests(tmp_path):
    create_test(tmp_path, "ONLY_TESTS", "click_static")
    assert known_subject_ids(tmp_path) == ["ONLY_TESTS"]
