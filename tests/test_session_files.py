"""SPEC-compass-task-flow.md 4C.8 / HC6 / AC13: ``discard_session`` deletes one
recorded session folder, and only that."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.engine.session_files import SessionDiscardError, discard_session

NAME = "2026-10-06_P001_click_grid_run1"


def make_session(root: Path, name: str = NAME, files=("trials.csv", "metadata.json", "events.jsonl")) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
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


def test_deletes_the_session_folder_and_its_files(root):
    folder = make_session(root)
    assert discard_session(folder, root) == 3  # files removed
    assert not folder.exists()
    assert root.exists()


def test_leaves_sibling_sessions_and_other_folders_alone(root):
    folder = make_session(root)
    make_session(root, "2026-10-06_P001_click_grid_run2")
    make_session(root, "2026-10-06_P002_click_grid_run1")
    (root / "_settings").mkdir()
    (root / "_settings" / "keep.json").write_text("{}", encoding="utf-8")
    (root / "_tests").mkdir()
    before = snapshot(root)
    discard_session(folder, root)
    after = snapshot(root)
    gone = set(before) - set(after)
    assert len(gone) == 4 and all(Path(k).parts[0] == NAME for k in gone)  # the folder + 3 files
    assert all(after[k] == before[k] for k in after)  # the rest is byte-identical


def test_accepts_a_string_path(root):
    folder = make_session(root)
    discard_session(str(folder), str(root))
    assert not folder.exists()


def test_the_run_number_is_free_again_afterwards(root):
    from src.engine.session_naming import next_run_number

    folder = make_session(root)
    assert next_run_number(root, "P001", "click_grid", date_str="2026-10-06") == 2
    discard_session(folder, root)
    assert next_run_number(root, "P001", "click_grid", date_str="2026-10-06") == 1


def test_refuses_a_path_outside_the_root(root, tmp_path):
    outside = make_session(tmp_path / "elsewhere_root")  # a valid name, wrong parent
    (tmp_path / "elsewhere_root").mkdir(exist_ok=True)
    with pytest.raises(SessionDiscardError):
        discard_session(outside, root)
    assert outside.exists()


def test_refuses_a_nested_path_even_with_a_good_name(root):
    parent = make_session(root)
    nested_root = parent / "inner"
    nested = make_session(nested_root)
    with pytest.raises(SessionDiscardError):
        discard_session(nested, root)  # parent is not the root
    assert nested.exists()


def test_refuses_a_dotdot_escape(root, tmp_path):
    victim = make_session(tmp_path / "other")
    sneaky = root / ".." / "other" / NAME
    with pytest.raises(SessionDiscardError):
        discard_session(sneaky, root)
    assert victim.exists()


def test_refuses_the_root_itself(root):
    make_session(root)
    with pytest.raises(SessionDiscardError):
        discard_session(root, root)
    assert (root / NAME).exists()


@pytest.mark.parametrize(
    "bad_name",
    [
        "_settings",
        "_tests",
        "_diagnostics",
        "_calibrations",
        "2026-10-06_P001_click_grid",  # no _run<N>
        "P001_click_grid_run1",  # no date
        "2026-10-06__run1",  # no subject/task part
        "2026-10-06_P001_click_grid_runX",
        "latest",
        "_2026-10-06_P001_click_grid_run1",  # leading underscore
    ],
)
def test_refuses_a_folder_that_is_not_a_session_name(root, bad_name):
    folder = make_session(root, bad_name)
    with pytest.raises(SessionDiscardError):
        discard_session(folder, root)
    assert folder.exists() and (folder / "trials.csv").exists()


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


def test_refuses_a_session_folder_that_is_itself_a_symlink(root, tmp_path):
    real = make_session(tmp_path / "real_place")
    link = root / NAME
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
    with pytest.raises(SessionDiscardError):
        discard_session(root / NAME, root)


def test_a_plain_file_with_a_session_name_is_not_deleted(root):
    f = root / NAME
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SessionDiscardError):
        discard_session(f, root)
    assert f.exists()


def test_an_empty_session_folder_is_removed(root):
    folder = make_session(root, files=())
    assert discard_session(folder, root) == 0
    assert not folder.exists()
