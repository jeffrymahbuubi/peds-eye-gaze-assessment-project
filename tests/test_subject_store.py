"""SPEC-subject-data-layout.md H1, H5, H6, H8 (L3, L4, L5): one folder per subject."""

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
    FOLDER_MODE_CODE,
    FOLDER_MODE_ID,
    MAX_FOLDER_ID_LEN,
    SUBJECT_FILENAME,
    SYSTEM_DIRNAME,
    ensure_subject,
    find_subject,
    id_folder_name,
    known_subject_ids,
    list_subjects,
    next_subject_code,
    output_root,
    preview_folder_name,
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
    assert folder.path == tmp_path / "P9REAL" and folder.mode == FOLDER_MODE_ID
    assert folder.subject_id == "P9REAL"
    record = _record(folder)
    assert record["subject_id"] == "P9REAL" and record["folder_mode"] == "id"
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


def test_an_existing_subject_keeps_the_mode_it_was_created_with(tmp_path):
    first = ensure_subject(tmp_path, "Ana", FOLDER_MODE_CODE)
    again = ensure_subject(tmp_path, "Ana", FOLDER_MODE_ID)
    assert again.path == first.path and again.mode == FOLDER_MODE_CODE


def test_a_blank_id_and_an_unknown_mode_are_refused(tmp_path):
    with pytest.raises(ValueError):
        ensure_subject(tmp_path, "   ")
    with pytest.raises(ValueError):
        ensure_subject(tmp_path, "Ana", "pseudonym")
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


# -- Anonymous code (H6, D4, L5) ------------------------------------------------------------------


def test_codes_count_up_from_s_0001(tmp_path):
    assert next_subject_code(tmp_path) == "S-0001"
    first = ensure_subject(tmp_path, "Ana", FOLDER_MODE_CODE)
    second = ensure_subject(tmp_path, "Bob", FOLDER_MODE_CODE)
    assert (first.name, second.name) == ("S-0001", "S-0002")
    assert next_subject_code(tmp_path) == "S-0003"


def test_a_code_subject_is_found_by_the_id_it_was_typed_with(tmp_path):
    folder = ensure_subject(tmp_path, "Ana Maria", FOLDER_MODE_CODE)
    assert find_subject(tmp_path, "ANA MARIA").path == folder.path
    assert known_subject_ids(tmp_path) == ["Ana Maria"]
    assert folder.mode == FOLDER_MODE_CODE and folder.label() == "Folder: S-0001 (Anonymous code)"


def test_a_code_is_never_reused_even_after_its_folder_is_deleted(tmp_path):
    import shutil

    ensure_subject(tmp_path, "Ana", FOLDER_MODE_CODE)
    shutil.rmtree(tmp_path / "S-0001")
    assert next_subject_code(tmp_path) == "S-0002"
    assert ensure_subject(tmp_path, "Bob", FOLDER_MODE_CODE).name == "S-0002"


def test_the_code_counter_lives_under_system_not_in_a_subject(tmp_path):
    ensure_subject(tmp_path, "Ana", FOLDER_MODE_CODE)
    assert (tmp_path / SYSTEM_DIRNAME / "subject_codes.json").is_file()
    assert [s.name for s in list_subjects(tmp_path)] == ["S-0001"]


def test_an_id_mode_subject_does_not_use_up_a_code(tmp_path):
    ensure_subject(tmp_path, "Ana")
    assert next_subject_code(tmp_path) == "S-0001"


def test_a_subject_whose_id_is_a_code_name_does_not_clash_with_a_real_code(tmp_path):
    ensure_subject(tmp_path, "S-0001")  # an ID that looks like a code, mode id
    coded = ensure_subject(tmp_path, "Ana", FOLDER_MODE_CODE)
    assert coded.name == "S-0002"  # S-0001 is taken, so the next free one


def test_in_code_mode_no_name_under_the_root_contains_the_subject_id(tmp_path):
    create_test(tmp_path, "Maria Lopez", "click_grid", folder_mode=FOLDER_MODE_CODE)
    assert list_tests(tmp_path, "maria lopez").tests  # still found by the typed id
    names = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")]
    assert names and not any("maria" in n.casefold() or "lopez" in n.casefold() for n in names)


def test_preview_folder_name_follows_the_choice(tmp_path):
    assert preview_folder_name(tmp_path, "Ana", FOLDER_MODE_ID) == "Ana"
    assert preview_folder_name(tmp_path, "Ana", FOLDER_MODE_CODE) == "S-0001"


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
