"""What ``tools/pyinstaller/build_exe.py`` copies into the exe's ``configs/``.

The raw art and sound sources under ``assets/scenes/park/reference/`` (14 MB) are never read by the
app, so the bundle leaves them out; the scene's own pictures, sounds and ``scene.yaml`` stay.
Checks the ignore rule only; the real bundle is smoke-tested by hand (SPEC-compiled-release.md).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARK = REPO_ROOT / "configs" / "assets" / "scenes" / "park"


def _build_exe():
    spec = importlib.util.spec_from_file_location(
        "build_exe", REPO_ROOT / "tools" / "pyinstaller" / "build_exe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_folder_is_left_out_of_the_exe():
    ignore = _build_exe().CONFIG_IGNORE
    names = sorted(p.name for p in PARK.iterdir())
    assert "reference" in names
    assert ignore(str(PARK), names) & set(names) == {"reference"}


def test_per_machine_and_cache_files_are_still_left_out():
    ignore = _build_exe().CONFIG_IGNORE
    names = ["local_state.json", "__pycache__", "x.pyc", "default.yaml", "tasks"]
    assert ignore("configs", names) == {"local_state.json", "__pycache__", "x.pyc"}
