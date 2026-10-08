"""Unit tests for the dashboard's Qt-free helpers (SPEC-ui-setup-task-selection.md).

The run-number helpers (``next_run_number``, ``next_session_id``) are gone: a run's folder is
made by ``new_run_dir`` (SPEC-subject-data-layout.md H2), tested in ``test_run_paths.py``."""

from __future__ import annotations

from src.engine.local_state import load_local_state, save_local_state


def test_local_state_roundtrip(tmp_path):
    path = tmp_path / "local_state.json"
    assert load_local_state(path) == {}
    save_local_state({"host": "26.113.49.235", "port": 4242}, path)
    assert load_local_state(path) == {"host": "26.113.49.235", "port": 4242}


def test_local_state_merges_rather_than_replaces(tmp_path):
    path = tmp_path / "local_state.json"
    save_local_state({"host": "127.0.0.1"}, path)
    save_local_state({"port": 4242}, path)
    assert load_local_state(path) == {"host": "127.0.0.1", "port": 4242}


def test_local_state_malformed_file_treated_as_empty(tmp_path):
    path = tmp_path / "local_state.json"
    path.write_text("not json", encoding="utf-8")
    assert load_local_state(path) == {}
