"""SPEC-subject-data-layout.md H2, H3, H4, H9 (L1, L7): where a run's folder is made and found."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import pytest

from src.data.analysis_export import ALL_GAZE_FILENAME, EYE_GEOMETRY_FILENAME, FIXATIONS_FILENAME
from src.data.recorder import POINTER_STREAM_FILENAME, TARGET_TRACK_FILENAME
from src.data.report_cache import REPORT_FILENAME
from src.engine.run_paths import (
    LONGEST_RUN_FILE_NAME,
    MAX_PATH_BUDGET,
    PATH_TOO_LONG_TEXT,
    PDF_NAME_MAX,
    RUN_NAME_RE,
    longest_run_path,
    make_session_id,
    new_run_dir,
    path_budget_error,
    relative_run_dir,
    resolve_run_dir,
)
from src.engine.subject_store import ensure_subject, id_folder_name

NOW = datetime(2026, 10, 7, 14, 32, 5)


# -- new_run_dir (H2, L1) -------------------------------------------------------------------------


def test_a_run_folder_is_under_the_subject_task_and_minute(tmp_path):
    run = new_run_dir(tmp_path, "P9REAL", "click_grid", now=NOW)
    assert run == tmp_path / "P9REAL" / "runs" / "click_grid" / "2026-10-07_1432"
    assert run.is_dir() and (tmp_path / "P9REAL" / "subject.json").is_file()
    assert RUN_NAME_RE.fullmatch(run.name)


def test_the_name_carries_no_subject_and_no_test_name(tmp_path):
    run = new_run_dir(tmp_path, "Maria Lopez", "scanning", now=NOW)
    assert run.name == "2026-10-07_1432"


def test_two_runs_in_the_same_minute_get_distinct_folders(tmp_path):
    names = [new_run_dir(tmp_path, "P1", "click_grid", now=NOW).name for _ in range(3)]
    assert names == ["2026-10-07_1432", "2026-10-07_1432_2", "2026-10-07_1432_3"]


def test_other_tasks_and_other_subjects_have_their_own_folders(tmp_path):
    a = new_run_dir(tmp_path, "P1", "click_grid", now=NOW)
    b = new_run_dir(tmp_path, "P1", "scanning", now=NOW)
    c = new_run_dir(tmp_path, "P2", "click_grid", now=NOW)
    assert (a.name, b.name, c.name) == ("2026-10-07_1432",) * 3
    assert len({a, b, c}) == 3


def test_ana_and_ana_in_capitals_share_a_runs_folder(tmp_path):
    a = new_run_dir(tmp_path, "Ana", "click_grid", now=NOW)
    b = new_run_dir(tmp_path, "ANA", "click_grid", now=NOW)
    assert a.parent == b.parent and b.name == "2026-10-07_1432_2"


def test_a_run_in_code_mode_lands_in_the_code_folder(tmp_path):
    run = new_run_dir(tmp_path, "Maria", "click_grid", folder_mode="code", now=NOW)
    assert run.parts[-4] == "S-0001"


def test_concurrent_runs_never_share_a_folder(tmp_path):
    ensure_subject(tmp_path, "P1")
    made: list[Path] = []
    lock = threading.Lock()

    def make():
        run = new_run_dir(tmp_path, "P1", "click_grid", now=NOW)
        with lock:
            made.append(run)

    threads = [threading.Thread(target=make) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(made)) == 8


@pytest.mark.parametrize("task_id", ["", "..", "a/b", "Click Grid", "../x", "click-grid"])
def test_a_task_id_that_is_not_one_is_refused(tmp_path, task_id):
    with pytest.raises(ValueError):
        new_run_dir(tmp_path, "P1", task_id, now=NOW)
    assert list(tmp_path.iterdir()) == []


# -- session id (H3) ----------------------------------------------------------------------------------


def test_the_session_id_has_task_time_and_test_but_no_subject(tmp_path):
    run = new_run_dir(tmp_path, "Maria Lopez", "click_grid", now=NOW)
    assert make_session_id("click_grid", run, "t_0123456789") == "click_grid_2026-10-07_1432_t_0123456789"
    assert make_session_id("click_grid", run, None) == "click_grid_2026-10-07_1432"
    assert "maria" not in make_session_id("click_grid", run, "t_0123456789").casefold()


# -- the link a test record keeps (H4) -----------------------------------------------------------------


def test_the_relative_path_is_posix_from_the_subject_folder(tmp_path):
    run = new_run_dir(tmp_path, "P1", "click_grid", now=NOW)
    subject = tmp_path / "P1"
    assert relative_run_dir(subject, run) == "runs/click_grid/2026-10-07_1432"
    assert resolve_run_dir(subject, "runs/click_grid/2026-10-07_1432") == run


def test_a_run_outside_runs_task_name_is_refused(tmp_path):
    subject = ensure_subject(tmp_path, "P1").path
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    deeper = subject / "runs" / "click_grid" / "2026-10-07_1432" / "x"
    deeper.mkdir(parents=True)
    badname = subject / "runs" / "click_grid" / "2026-10-07_P1_run1"
    badname.mkdir()
    flat = subject / "runs" / "2026-10-07_1432"
    flat.mkdir()
    for bad in (elsewhere, subject, subject / "runs", deeper, badname, flat):
        with pytest.raises(ValueError):
            relative_run_dir(subject, bad)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "runs",
        "runs/click_grid",
        "runs/click_grid/2026-10-07_1432/extra",
        "runs/../../x/2026-10-07_1432",
        "runs/click_grid/..",
        "../runs/click_grid/2026-10-07_1432",
        "/runs/click_grid/2026-10-07_1432",
        "C:/runs/click_grid/2026-10-07_1432",
        "runs/click_grid/2026-10-07_P1_run1",
        "tests/click_grid/2026-10-07_1432",
    ],
)
def test_a_run_dir_that_is_not_the_plain_shape_resolves_to_nothing(tmp_path, value):
    assert resolve_run_dir(tmp_path, value) is None


# -- the path budget (H9, L7) --------------------------------------------------------------------------


def test_the_longest_file_name_is_the_longest_the_run_writes():
    written = [
        "metadata.json", "session.log", "gaze_stream.csv", "trials.csv", "events.jsonl",
        "calibration.json", "session_metrics.json", ALL_GAZE_FILENAME, EYE_GEOMETRY_FILENAME,
        FIXATIONS_FILENAME, TARGET_TRACK_FILENAME, POINTER_STREAM_FILENAME, REPORT_FILENAME,
    ]
    assert max(len(n) for n in written) == len(LONGEST_RUN_FILE_NAME)


def test_the_worst_case_numbers_of_the_spec(tmp_path):
    name = id_folder_name("x" * 60)  # 47 characters
    assert len(name) == 47
    # With a 100-character root: ~206 for the run files, ~222 for the PDF (SPEC H9). The root
    # is made already absolute, so abspath leaves its length alone.
    absolute = "C:\\" + "r" * 97
    assert len(absolute) == 100
    assert longest_run_path(absolute, name, "follow_moving") == max(
        100 + 1 + 47 + 1 + 4 + 1 + 13 + 1 + 17 + 1 + 20,
        100 + 1 + 47 + 1 + 7 + 1 + PDF_NAME_MAX + len("2026-10-07_") + 4,
    )


def test_a_normal_root_has_room_to_spare(tmp_path):
    assert path_budget_error(tmp_path, "P9REAL", "click_grid") is None


def test_a_root_deep_enough_blocks_with_the_h9_text(tmp_path):
    deep = tmp_path / ("d" * 60) / ("e" * 60) / ("f" * 60) / ("g" * 60)
    assert len(str(deep)) > 240
    assert path_budget_error(deep, "P9REAL", "click_grid") == PATH_TOO_LONG_TEXT
    assert PATH_TOO_LONG_TEXT == (
        "The data folder path is too long — move the program folder closer to the drive root."
    )


def test_the_budget_is_240_and_counts_the_subject_folder(tmp_path):
    fixed = longest_run_path(tmp_path, "P9REAL", "click_grid")
    # Pad the root so the run path lands exactly on the budget, then one over.
    pad = MAX_PATH_BUDGET - fixed
    exact = tmp_path / ("p" * (pad - 1))
    assert longest_run_path(exact, "P9REAL", "click_grid") == MAX_PATH_BUDGET
    assert path_budget_error(exact, "P9REAL", "click_grid") is None
    over = tmp_path / ("p" * pad)
    assert longest_run_path(over, "P9REAL", "click_grid") == MAX_PATH_BUDGET + 1
    assert path_budget_error(over, "P9REAL", "click_grid") == PATH_TOO_LONG_TEXT


def test_an_existing_subjects_real_folder_name_is_measured(tmp_path):
    # A root of 140 characters: over the budget for a 47-character folder, under it for P9REAL.
    root = tmp_path / ("p" * (140 - len(str(tmp_path)) - 1))
    assert len(str(root)) == 140
    ensure_subject(root, "x" * 70)  # a 47-character folder name
    assert path_budget_error(root, "x" * 70, "follow_moving") == PATH_TOO_LONG_TEXT
    assert path_budget_error(root, "P9REAL", "click_grid") is None
