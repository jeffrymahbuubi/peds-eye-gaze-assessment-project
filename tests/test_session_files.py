"""SPEC-compass-task-flow.md 4C.8 / HC6 / AC13 and SPEC-subject-data-layout.md H10 (L2):
``discard_session`` deletes one recorded run folder, and only that."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from src.engine.session_files import SessionDiscardError, discard_session
from src.engine.subject_store import ensure_subject

NAME = "2026-10-06_1200"
RUN = Path("P001") / "runs" / "click_grid" / NAME


def make_session(
    root: Path,
    relative: Path | str = RUN,
    files=("trials.csv", "metadata.json", "events.jsonl"),
) -> Path:
    """A run folder at ``root / relative``; the first part is made a real subject folder."""
    relative = Path(relative)
    ensure_subject(root, relative.parts[0])
    folder = root / relative
    folder.mkdir(parents=True, exist_ok=True)
    for f in files:
        (folder / f).write_text("x", encoding="utf-8")
    return folder


@pytest.fixture
def root(tmp_path) -> Path:
    r = tmp_path / "sessions"
    r.mkdir()
    return r


def snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in root.rglob("*")
    }


def test_deletes_the_run_folder_and_its_files(root):
    folder = make_session(root)
    assert discard_session(folder, root) == 3  # files removed
    assert not folder.exists()
    assert root.exists() and (root / "P001" / "subject.json").is_file()


def test_leaves_sibling_runs_and_the_subjects_other_data_alone(root):
    folder = make_session(root)
    make_session(root, Path("P001") / "runs" / "click_grid" / "2026-10-06_1200_2")
    make_session(root, Path("P001") / "runs" / "scanning" / NAME)
    make_session(root, Path("P002") / "runs" / "click_grid" / NAME)
    (root / "P001" / "tests").mkdir()
    (root / "P001" / "tests" / "t_0123456789.json").write_text("{}", encoding="utf-8")
    (root / "_system" / "diagnostics").mkdir(parents=True)
    (root / "_system" / "diagnostics" / "gaze_dropouts.jsonl").write_text("{}\n", encoding="utf-8")
    before = snapshot(root)
    discard_session(folder, root)
    after = snapshot(root)
    gone = set(before) - set(after)
    assert len(gone) == 4 and all(Path(k).parts[:4] == RUN.parts for k in gone)  # the folder + 3 files
    assert all(after[k] == before[k] for k in after)  # the rest is byte-identical


def test_accepts_a_string_path(root):
    folder = make_session(root)
    discard_session(str(folder), str(root))
    assert not folder.exists()


def test_the_minute_is_free_again_afterwards(root):
    from src.engine.run_paths import new_run_dir

    now = datetime(2026, 10, 6, 12, 0)
    folder = new_run_dir(root, "P001", "click_grid", now=now)
    assert folder.name == NAME
    discard_session(folder, root)
    assert new_run_dir(root, "P001", "click_grid", now=now).name == NAME


def test_a_collision_suffix_is_a_run_name_too(root):
    folder = make_session(root, Path("P001") / "runs" / "click_grid" / "2026-10-06_1200_3")
    assert discard_session(folder, root) == 3


def test_refuses_a_path_outside_the_root(root, tmp_path):
    outside = make_session(tmp_path / "elsewhere_root")  # a valid shape, wrong root
    with pytest.raises(SessionDiscardError):
        discard_session(outside, root)
    assert outside.exists()


def test_refuses_a_dotdot_escape(root, tmp_path):
    victim = make_session(tmp_path / "other")
    sneaky = root / ".." / "other" / RUN
    with pytest.raises(SessionDiscardError):
        discard_session(sneaky, root)
    assert victim.exists()


def test_refuses_the_root_a_subject_folder_and_the_levels_between(root):
    folder = make_session(root)
    for level in (root, root / "P001", root / "P001" / "runs", root / "P001" / "runs" / "click_grid"):
        with pytest.raises(SessionDiscardError):
            discard_session(level, root)
    assert (folder / "trials.csv").exists()


@pytest.mark.parametrize(
    "bad",
    [
        Path("P001") / "runs" / "click_grid" / "2026-10-06_P001_click_grid_run1",  # the old name
        Path("P001") / "runs" / "click_grid" / "latest",
        Path("P001") / "runs" / "click_grid" / "2026-10-06_12",  # not HHMM
        Path("P001") / "runs" / "click_grid" / "_2026-10-06_1200",
        Path("P001") / "runs" / "Click Grid" / NAME,  # not a task id
        Path("P001") / "runs" / NAME,  # no task level
        Path("P001") / "calibrations" / "click_grid" / NAME,  # not under runs/
        Path("P001") / "tests" / "click_grid" / NAME,
        Path("P001") / "runs" / "click_grid" / NAME / "inner",  # too deep
        Path("2026-10-06_P001_click_grid_run1"),  # the old flat layout, at the root
    ],
)
def test_refuses_a_folder_that_is_not_at_the_h10_pattern(root, bad):
    folder = make_session(root, bad)
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert folder.exists() and (folder / "trials.csv").exists()


def test_refuses_a_run_under_system(root):
    folder = make_session(root, Path("_system") / "runs" / "click_grid" / NAME)
    (root / "_system" / "subject.json").write_text("{}", encoding="utf-8")  # even then
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert folder.exists()


def test_refuses_a_run_whose_parent_is_not_a_subject_folder(root):
    folder = root / "not_a_subject" / "runs" / "click_grid" / NAME
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "trials.csv").write_text("x", encoding="utf-8")
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert (folder / "trials.csv").exists()


def test_refuses_a_folder_that_holds_a_subdirectory_and_deletes_nothing(root):
    folder = make_session(root)
    (folder / "plots").mkdir()
    (folder / "plots" / "a.png").write_text("x", encoding="utf-8")
    before = snapshot(root)
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert snapshot(root) == before  # aborted with no deletion at all


def test_refuses_a_folder_that_holds_a_symlink_and_deletes_nothing(root, tmp_path):
    folder = make_session(root)
    target = tmp_path / "precious.txt"
    target.write_text("keep me", encoding="utf-8")
    try:
        os.symlink(target, folder / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this machine")
    before = snapshot(root)
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert snapshot(root) == before
    assert target.read_text(encoding="utf-8") == "keep me"


def test_refuses_a_run_folder_that_is_itself_a_symlink(root, tmp_path):
    real = make_session(tmp_path / "real_place")
    ensure_subject(root, "P001")
    (root / "P001" / "runs" / "click_grid").mkdir(parents=True)
    link = root / RUN
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this machine")
    with pytest.raises(SessionDiscardError):
        discard_session(link, root)
    assert (real / "trials.csv").exists()


@pytest.mark.parametrize("linked", ["events.jsonl", NAME])
def test_a_link_is_refused_even_where_symlinks_cannot_be_made(root, monkeypatch, linked):
    """The same two refusals as above, with the link check simulated, so they are
    exercised on a machine that has no symlink privilege."""
    from src.engine import session_files

    folder = make_session(root)
    real = session_files._is_link
    monkeypatch.setattr(session_files, "_is_link", lambda p: p.name == linked or real(p))
    before = snapshot(root)
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert snapshot(root) == before


def test_a_missing_folder_is_an_error_not_a_silent_success(root):
    ensure_subject(root, "P001")
    with pytest.raises(SessionDiscardError):
        discard_session(root / RUN, root)


def test_a_plain_file_with_a_run_name_is_not_deleted(root):
    ensure_subject(root, "P001")
    (root / "P001" / "runs" / "click_grid").mkdir(parents=True)
    f = root / RUN
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SessionDiscardError):
        discard_session(f, root)
    assert f.exists()


def test_an_empty_run_folder_is_removed(root):
    folder = make_session(root, files=())
    assert discard_session(folder, root) == 0
    assert not folder.exists()
