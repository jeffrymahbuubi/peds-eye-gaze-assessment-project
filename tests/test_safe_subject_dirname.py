"""SPEC-compass-task-flow.md 4A.9 / AA13: a Subject ID can never escape its folder.
SPEC-subject-data-layout.md H5: the folder is the subject's own, capped at 40 characters."""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.engine.run_paths import new_run_dir
from src.engine.session_naming import safe_subject_dirname
from src.engine.settings_profile import (
    save_settings_profile,
    settings_profile_dir,
    subject_settings_dir,
)
from src.engine.subject_store import find_subject, id_folder_name
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


@pytest.mark.parametrize("subject_id", [i for i in HOSTILE_IDS if i.strip()])
def test_hostile_ids_stay_inside_their_own_subject_folder(tmp_path, subject_id):
    create_test(tmp_path, subject_id, "click_static")
    folder = find_subject(tmp_path, subject_id)
    assert folder.path.parent == tmp_path
    assert folder.path.resolve() in subject_tests_dir(tmp_path, subject_id).resolve().parents
    assert len(folder.name) <= 47  # 40 + "_" prefix + "~" + 6 hex


def test_hostile_ids_really_create_one_folder_each_directly_under_the_root(tmp_path):
    for subject_id in ("..\\x", "A/B", "CON", "x.", "a" * 200):
        create_test(tmp_path, subject_id, "click_static")
    assert len(list(tmp_path.iterdir())) == 5  # one folder each, nothing nested, nothing outside
    assert all((p / "subject.json").is_file() and (p / "tests").is_dir() for p in tmp_path.iterdir())


@pytest.mark.parametrize("subject_id", ORDINARY_IDS)
def test_ordinary_ids_come_back_unchanged(subject_id):
    assert safe_subject_dirname(subject_id) == subject_id


def test_the_cap_is_a_parameter_and_a_subject_folder_uses_40():
    assert safe_subject_dirname("x" * 50, 40).startswith("x" * 40 + "~")
    assert safe_subject_dirname("x" * 40, 40) == "x" * 40
    assert id_folder_name("x" * 80) == safe_subject_dirname("x" * 80, 40)
    assert id_folder_name("  P001  ") == "P001"


def test_the_stores_sit_inside_the_subject_folder(tmp_path):
    create_test(tmp_path, "TESTING", "click_grid")
    save_settings_profile(tmp_path, "TESTING", "click_grid", {"dwell.threshold_ms": 900})
    folder = tmp_path / "TESTING"
    assert subject_tests_dir(tmp_path, "TESTING") == folder / "tests"
    assert subject_settings_dir(tmp_path, "TESTING") == folder / "settings"
    assert settings_profile_dir(tmp_path, "TESTING", "click_grid") == folder / "settings" / "click_grid"
    assert _subject_calibration_dir(tmp_path, "TESTING") == folder / "calibrations"


def test_a_subject_with_no_folder_has_no_store_paths(tmp_path):
    assert subject_tests_dir(tmp_path, "NOBODY") is None
    assert subject_settings_dir(tmp_path, "NOBODY") is None
    assert settings_profile_dir(tmp_path, "NOBODY", "click_grid") is None
    assert _subject_calibration_dir(tmp_path, "NOBODY") is None


def test_all_the_stores_find_the_same_folder_for_a_hostile_id(tmp_path):
    subject_id = "A/B"
    create_test(tmp_path, subject_id, "click_static")
    safe = id_folder_name(subject_id)
    assert subject_tests_dir(tmp_path, subject_id) == tmp_path / safe / "tests"
    assert subject_settings_dir(tmp_path, subject_id) == tmp_path / safe / "settings"
    assert _subject_calibration_dir(tmp_path, subject_id) == tmp_path / safe / "calibrations"
    run = new_run_dir(tmp_path, subject_id, "click_static")
    assert run.parent.parent == tmp_path / safe / "runs"


def test_settings_profile_for_a_hostile_id_lands_in_its_own_folder(tmp_path):
    path = save_settings_profile(tmp_path, "..\\x", "click_static", {"dwell.threshold_ms": 900})
    folder = find_subject(tmp_path, "..\\x").path
    assert path.parent.parent.parent == folder  # <subject>/settings/<task>/<file>
    assert folder.resolve() in path.resolve().parents


def test_slash_and_underscore_do_not_share_a_folder():
    assert safe_subject_dirname("A_B") == "A_B"
    assert safe_subject_dirname("A/B") != "A_B"
    assert safe_subject_dirname("A/B") != safe_subject_dirname("A|B")  # both sanitise to A_B
    assert safe_subject_dirname("A/B") == safe_subject_dirname("A/B")  # and it is stable


def test_unicode_is_nfc_normalised():
    composed, decomposed = "é", "é"
    assert safe_subject_dirname(composed) == composed
    assert safe_subject_dirname(decomposed).startswith(composed + "~")


def test_device_names_get_a_prefix():
    assert safe_subject_dirname("CON").startswith("_CON~")
    assert safe_subject_dirname("com3.txt").startswith("_com3.txt~")
    assert safe_subject_dirname("CONSOLE") == "CONSOLE"  # not a device name
    assert safe_subject_dirname("COM10") == "COM10"
