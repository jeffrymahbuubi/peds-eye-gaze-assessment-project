"""SPEC-subject-data-layout.md H1, H5, H8, D4 revised (L3, L4, L5): one folder per subject."""

from __future__ import annotations

import json
import re

import pytest

from src.engine.calibration import calibration_timing_log_path
from src.engine.gaze_diagnostics import gaze_dropout_log_path
from src.engine.run_paths import new_run_dir
from src.engine.session_naming import safe_subject_dirname
from src.engine.settings_profile import save_settings_profile
from src.engine.subject_store import (
    FOLDER_MODE_ID,
    MAX_FOLDER_ID_LEN,
    SUBJECT_FILENAME,
    SYSTEM_DIRNAME,
    ensure_subject,
    find_subject,
    id_folder_name,
    known_subject_ids,
    list_subjects,
    output_root,
)
from src.engine.subject_tests import create_test, list_tests


def _record(folder) -> dict:
    return json.loads((folder.path / SUBJECT_FILENAME).read_text(encoding="utf-8"))


# -- output_root (H8) ---------------------------------------------------------------------


def test_output_root_reads_the_given_config_and_defaults_to_sessions():
    assert output_root({"recording": {"output_root": "data"}}) == "data"
    assert output_root({}) == "sessions"
    assert output_root({"recording": None}) == "sessions"


def test_output_root_without_a_config_is_the_default_configs():
    assert output_root() == "sessions"


# -- creating a subject folder (H1, H5) -------------------------------------------------------


def test_a_new_subject_gets_a_folder_with_subject_json(tmp_path):
    folder = ensure_subject(tmp_path, "  P9REAL ")
    assert folder.path == tmp_path / "P9REAL"
    assert folder.subject_id == "P9REAL"
    record = _record(folder)
    assert record["subject_id"] == "P9REAL" and record["folder_mode"] == FOLDER_MODE_ID == "id"
    assert re.match(r"\d{4}-\d{2}-\d{2}T", record["created_at"])
    assert set(record) == {"subject_id", "folder_mode", "created_at"}


def test_the_folder_has_no_subfolders_until_something_is_saved(tmp_path):
    ensure_subject(tmp_path, "P9REAL")
    assert sorted(p.name for p in (tmp_path / "P9REAL").iterdir()) == [SUBJECT_FILENAME]


def test_ana_then_ana_in_capitals_is_one_subject(tmp_path):
    first = ensure_subject(tmp_path, "Ana")
    second = ensure_subject(tmp_path, "ANA")
    assert second.path == first.path and second.subject_id == "Ana"  # verbatim as first typed
    assert [p.name for p in tmp_path.iterdir()] == ["Ana"]
    assert find_subject(tmp_path, "aNa").path == first.path


def test_a_blank_id_is_refused(tmp_path):
    with pytest.raises(ValueError):
        ensure_subject(tmp_path, "   ")
    assert list(tmp_path.iterdir()) == []


def test_the_folder_name_is_cut_at_40_characters(tmp_path):
    long_id = "x" * 70
    name = id_folder_name(long_id)
    assert name == safe_subject_dirname(long_id, MAX_FOLDER_ID_LEN)
    assert name.startswith("x" * 40) and re.search(r"~[0-9a-f]{6}$", name) and len(name) == 47
    assert ensure_subject(tmp_path, long_id).name == name


def test_two_long_ids_with_the_same_start_get_two_folders(tmp_path):
    a = ensure_subject(tmp_path, "x" * 70 + "a")
    b = ensure_subject(tmp_path, "x" * 70 + "b")
    assert a.path != b.path


@pytest.mark.parametrize("subject_id", ["..\\x", "A/B", "CON", "x.", "a" * 200, "_system", "_SYSTEM"])
def test_hostile_ids_make_one_folder_directly_under_the_root(tmp_path, subject_id):
    folder = ensure_subject(tmp_path, subject_id)
    assert folder.path.parent == tmp_path
    assert [p.name for p in tmp_path.iterdir()] == [folder.name]
    assert folder.name.casefold() != SYSTEM_DIRNAME


def test_system_is_reserved_and_never_listed_as_a_subject(tmp_path):
    folder = ensure_subject(tmp_path, "_system")
    assert folder.name != "_system" and folder.name.startswith("__system~")
    (tmp_path / SYSTEM_DIRNAME).mkdir()
    (tmp_path / SYSTEM_DIRNAME / SUBJECT_FILENAME).write_text(
        json.dumps({"subject_id": "ghost", "folder_mode": "id"}), encoding="utf-8"
    )
    assert known_subject_ids(tmp_path) == ["_system"]
    assert find_subject(tmp_path, "ghost") is None


def test_a_folder_without_subject_json_is_not_a_subject_and_is_not_adopted(tmp_path):
    (tmp_path / "Ana").mkdir()
    (tmp_path / "Ana" / "notes.txt").write_text("not ours", encoding="utf-8")
    assert find_subject(tmp_path, "Ana") is None and list_subjects(tmp_path) == []
    folder = ensure_subject(tmp_path, "Ana")
    assert folder.name == "Ana~2"  # the existing folder is left alone
    assert (tmp_path / "Ana" / "notes.txt").exists()


def test_a_broken_subject_json_is_not_a_subject(tmp_path):
    (tmp_path / "Ana").mkdir()
    (tmp_path / "Ana" / SUBJECT_FILENAME).write_text("{not json", encoding="utf-8")
    assert find_subject(tmp_path, "Ana") is None


def test_the_folder_is_found_by_subject_json_not_by_recomputing_the_name(tmp_path):
    (tmp_path / "renamed by hand").mkdir()
    (tmp_path / "renamed by hand" / SUBJECT_FILENAME).write_text(
        json.dumps({"subject_id": "Ana", "folder_mode": "id", "created_at": "x"}), encoding="utf-8"
    )
    assert find_subject(tmp_path, "ANA").name == "renamed by hand"
    assert ensure_subject(tmp_path, "Ana").name == "renamed by hand"


def test_a_missing_root_is_simply_no_subjects(tmp_path):
    assert list_subjects(tmp_path / "nope") == [] and known_subject_ids(tmp_path / "nope") == []
    assert find_subject(tmp_path / "nope", "Ana") is None


# -- the completer list (L4) ----------------------------------------------------------------------


def test_known_subject_ids_are_the_verbatim_ids_sorted(tmp_path):
    for subject_id in ("zoe", "Ana", "bob"):
        ensure_subject(tmp_path, subject_id)
    ensure_subject(tmp_path, "ANA")  # the same subject: not a second entry
    assert known_subject_ids(tmp_path) == ["Ana", "bob", "zoe"]


def test_known_subject_ids_lists_a_subject_that_only_has_a_test(tmp_path):
    create_test(tmp_path, "ONLY_TESTS", "click_static")
    assert known_subject_ids(tmp_path) == ["ONLY_TESTS"]


def test_known_subject_ids_ignores_loose_files(tmp_path):
    ensure_subject(tmp_path, "S1")
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
    assert known_subject_ids(tmp_path) == ["S1"]


# -- the folder is always the Subject ID (D4 revised 2026-10-08, L5) ----------------------------------


def test_a_new_subjects_folder_is_its_subject_id_and_no_code_is_assigned(tmp_path):
    folder = ensure_subject(tmp_path, "Maria Lopez")
    assert folder.name == "Maria Lopez" == id_folder_name("Maria Lopez")
    assert _record(folder)["folder_mode"] == "id"
    assert [p.name for p in tmp_path.iterdir()] == ["Maria Lopez"]  # no S-000N, no _system


def test_the_first_save_of_anything_never_makes_a_code_folder(tmp_path):
    create_test(tmp_path, "Maria Lopez", "click_grid")
    save_settings_profile(tmp_path, "Ana", "click_grid", {"dwell.threshold_ms": 900})
    new_run_dir(tmp_path, "Bob", "click_grid")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Ana", "Bob", "Maria Lopez"]
    assert list_tests(tmp_path, "maria lopez").tests  # found by the typed id


def test_subject_codes_json_is_neither_read_nor_written(tmp_path):
    counter = tmp_path / SYSTEM_DIRNAME / "subject_codes.json"
    counter.parent.mkdir()
    counter.write_text(json.dumps({"last": 7}), encoding="utf-8")
    folder = ensure_subject(tmp_path, "Ana")
    assert folder.name == "Ana"  # not S-0008
    assert json.loads(counter.read_text(encoding="utf-8")) == {"last": 7}  # left as it was
    other = tmp_path / "other"
    ensure_subject(other, "Bob")
    assert not (other / SYSTEM_DIRNAME).exists()


def test_an_old_code_folder_is_still_found_by_the_id_it_was_typed_with(tmp_path):
    # Left by a build that had the Anonymous code option: folder_mode "code" is ignored.
    (tmp_path / "S-0001").mkdir()
    (tmp_path / "S-0001" / SUBJECT_FILENAME).write_text(
        json.dumps({"subject_id": "Ana Maria", "folder_mode": "code", "created_at": "x"}), encoding="utf-8"
    )
    assert find_subject(tmp_path, "ANA MARIA").name == "S-0001"
    assert ensure_subject(tmp_path, "Ana Maria").name == "S-0001"
    assert known_subject_ids(tmp_path) == ["Ana Maria"]
    assert ensure_subject(tmp_path, "Bob").name == "Bob"  # a new subject still gets its ID


def test_a_subject_whose_id_looks_like_a_code_name_still_gets_that_name(tmp_path):
    assert ensure_subject(tmp_path, "S-0001").name == "S-0001"


# -- the stores write only inside the subject folder (L3, L8) -----------------------------------------


def test_every_store_writes_inside_the_subject_folder_and_no_old_folder_appears(tmp_path):
    root = tmp_path / "sessions"
    test = create_test(root, "P9REAL", "click_grid")
    save_settings_profile(root, "P9REAL", "click_grid", {"dwell.threshold_ms": 900}, name="Calm")
    calibration = ensure_subject(root, "P9REAL").calibrations / "calibration_5pt.json"
    calibration.parent.mkdir()
    calibration.write_text("{}", encoding="utf-8")
    run = new_run_dir(root, "P9REAL", "click_grid")
    (run / "trials.csv").write_text("x", encoding="utf-8")
    assert sorted(p.name for p in root.iterdir()) == ["P9REAL"]
    inside = sorted(p.relative_to(root / "P9REAL").parts[0] for p in (root / "P9REAL").iterdir())
    assert inside == ["calibrations", "runs", "settings", "subject.json", "tests"]
    assert (root / "P9REAL" / "tests" / f"{test.test_id}.json").is_file()
    for old in ("_tests", "_settings", "_calibrations", "_diagnostics"):
        assert not (root / old).exists()


def test_the_diagnostic_logs_are_machine_wide_under_system(tmp_path):
    assert calibration_timing_log_path(tmp_path) == tmp_path / "_system" / "diagnostics" / "calibration_timing.jsonl"
    assert gaze_dropout_log_path(tmp_path) == tmp_path / "_system" / "diagnostics" / "gaze_dropouts.jsonl"
    # No subject in the path, so they are the same file whoever is being tested.
    assert gaze_dropout_log_path(tmp_path) == gaze_dropout_log_path(tmp_path)
