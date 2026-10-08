"""Real Segoe UI metrics for the offscreen tests that must measure text (not a test module).

Offscreen Qt has no font database: every glyph is one em wide, so a width read from a text
measure says nothing about the screen or the printed page. These tests register the Windows
Segoe UI files for the length of a module, where the claim is about widths (the Detailed table's
thirteen columns, the words of a PDF table header); they skip where the files are missing.

A test module wraps :func:`segoe_ui` in a module-scoped fixture of its own (it needs the
module's ``qapp`` fixture).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase

WINDOWS_FONTS = Path("C:/Windows/Fonts")
SEGOE_UI_FILES = ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf")  # regular, bold, semibold


def load_segoe_ui() -> list[int]:
    """Register Segoe UI (regular, bold, semibold); the ids to hand to :func:`unload`, or
    an empty list when the files are not there."""
    paths = [WINDOWS_FONTS / name for name in SEGOE_UI_FILES]
    if not all(path.is_file() for path in paths):
        return []
    ids = [QFontDatabase.addApplicationFont(str(path)) for path in paths]
    if min(ids) < 0:
        unload(ids)
        return []
    return ids


def unload(ids: list[int]) -> None:
    for font_id in ids:
        if font_id >= 0:
            QFontDatabase.removeApplicationFont(font_id)


def application_font(pixel_size: int = 14) -> QFont:
    """What ``apply_application_font`` sets: Segoe UI at ``pixel_size`` px (the pixel-sized
    default font that made a PDF heading tag print at about 5 pt)."""
    font = QFont("Segoe UI")
    font.setPixelSize(pixel_size)
    return font


def segoe_ui(qapp):
    """The body of a module-scoped fixture: real Segoe UI as the application font at 14 px for
    the module (the test is skipped if the files are missing)::

        @pytest.fixture(scope="module")
        def segoe(qapp):
            yield from real_fonts.segoe_ui(qapp)
    """
    ids = load_segoe_ui()
    if not ids:
        pytest.skip("Segoe UI is not installed in C:/Windows/Fonts")
    previous = qapp.font()
    qapp.setFont(application_font())  # a pixel-sized default, as the app sets
    yield
    qapp.setFont(previous)
    unload(ids)
