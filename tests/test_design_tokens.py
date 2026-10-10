"""SPEC-design-system-phase1.md H1-H9, H12, P1-P3: the design tokens, the sheets built from
them, the type scale, and the component sizes and states the style sheet gives.

Pinned three ways: the token module itself (contrast ratios from its hex values), the text of
the sheets (no hex of their own, no gradient, only type-scale sizes), and what a themed widget
really paints or measures (offscreen Qt: colours and fixed sizes are real, glyphs are not).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QFont, QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.engine.config import load_task_config
from src.ui import design_tokens as tokens
from src.ui import alert_box, dialog_theme, frozen_table, map_legend, run_bar, run_dialogs, wtmh_theme
from src.ui.dashboard_window import apply_application_font
from src.ui.design_tokens import CONTRAST_PAIRS, TYPE_SCALE
from src.ui.start_test_page import StartTestPage
from src.ui.wtmh_theme import STYLESHEET
from tests.colour_helpers import contrast

UI = Path(__file__).resolve().parent.parent / "src" / "ui"
# The operator-UI sheets (P2) and, since phase 4 (SPEC-design-system-phase4.md H1), the painters of the
# report map, its legend and the PDF.
SHEET_MODULES = (
    "wtmh_theme",
    "wtmh_controls",
    "dialog_theme",
    "run_bar",
    "run_dialogs",
    "config_widgets",
    "frozen_table",
    "rename_editor",
    # phase 2 (SPEC-design-system-phase2.md): the badge, the alert box and their helpers
    "alert_box",
    "status_badge",
    "glyphs",
    "page_layout",
    "setup_status",
    "config_footer",
    # phase 4 (SPEC-design-system-phase4.md): the report map, its legend and the PDF
    "target_map_paint",
    "target_map_follow",
    "map_legend",
    "report_pdf",
)
SHEETS = {
    "STYLESHEET": STYLESHEET,
    "run bar": run_bar._STYLESHEET,
    "run dialogs": run_dialogs._DANGER_STYLE,
    "item views": dialog_theme.ITEM_VIEW_STYLESHEET,
    "frozen table": frozen_table._STYLE,
    "alert box": alert_box.ALERT_STYLESHEET,
    "map legend": map_legend.LEGEND_STYLE,
}
HEX = re.compile(r"(?<![\w&])#[0-9A-Fa-f]{3,8}\b")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def token_values() -> set[str]:
    return {
        value.lower()
        for name, value in vars(tokens).items()
        if name.isupper() and isinstance(value, str) and HEX.fullmatch(value)
    }


# -- P1: the contrast table ------------------------------------------------------------------------


@pytest.mark.parametrize(("fg", "bg", "minimum"), CONTRAST_PAIRS)
def test_every_contrast_pair_meets_its_ratio_from_its_hex_values(fg, bg, minimum):
    ratio = contrast(QColor(fg), QColor(bg))
    assert ratio >= minimum - 0.02, (fg, bg, round(ratio, 2), minimum)
    assert ratio <= minimum + 0.02, (fg, bg, round(ratio, 2), minimum)  # the figure is the real one


def test_text_on_a_filled_token_is_aa_and_borders_are_at_least_3_to_1():
    exempt_fg = {tokens.BORDER_SUBTLE, tokens.TEXT_DISABLED}  # decorative, and a disabled control
    for fg, bg, _minimum in CONTRAST_PAIRS:
        if fg in exempt_fg:
            continue
        ratio = contrast(QColor(fg), QColor(bg))
        assert ratio >= 3.0, (fg, bg, ratio)
        text_on_fill = bg in {tokens.ACCENT, tokens.ACCENT_HOVER, tokens.DANGER, tokens.SUCCESS,
                              tokens.TITLE_BAR, tokens.DANGER_TEXT} and fg == tokens.PANEL
        text_colour = fg in {tokens.INK, tokens.TEXT_SECONDARY, tokens.DANGER_TEXT,
                             tokens.SUCCESS_TEXT, tokens.WARNING_TEXT}
        if text_on_fill or text_colour:
            assert ratio >= 4.5, (fg, bg, ratio)


def test_the_accent_family_is_the_wtmh_blue():
    assert (tokens.ACCENT, tokens.ACCENT_HOVER, tokens.ACCENT_FOCUS) == ("#1F669E", "#17507D", "#2D7EB3")
    assert (tokens.ACCENT_SUBTLE, tokens.ROW_SELECTED, tokens.SLIDER_GROOVE) == ("#E3EEF7", "#CFE2F1", "#C6C6C6")
    assert tokens.TITLE_BAR == "#12374A"


# -- P2: no hex and no gradient outside the token module -----------------------------------------


@pytest.mark.parametrize("module", SHEET_MODULES)
def test_a_sheet_module_has_no_hex_literal_of_its_own(module):
    source = (UI / f"{module}.py").read_text(encoding="utf-8")
    assert HEX.findall(source) == []


@pytest.mark.parametrize("name", SHEETS)
def test_a_built_sheet_has_only_token_colours_and_no_gradient(name):
    sheet = SHEETS[name]
    assert "gradient" not in sheet.lower()
    stray = {h.lower() for h in HEX.findall(sheet)} - token_values()
    assert stray == set(), stray


def test_the_map_and_data_viz_tokens_are_the_values_of_proposal_2_2():
    """SPEC-design-system-phase4.md H1."""
    assert (tokens.MAP_HIT_FILL, tokens.MAP_HIT_OUTLINE, tokens.MAP_MISS) == ("#A7F0BA", "#198038", "#DA1E28")
    assert (tokens.MAP_SKIPPED, tokens.MAP_SLOT) == ("#6F6F6F", "#8D8D8D")
    assert (tokens.MAP_PATH_DARK, tokens.MAP_PATH_LIGHT, tokens.MAP_FIXATION) == ("#1F669E", "#2D7EB3", "#1F669E")
    assert (tokens.MAP_OVERLAY, tokens.MAP_OVERLAY_ALPHA, tokens.MAP_SELECT) == ("#1F669E", 200, "#F2B705")
    assert tokens.MAP_PATH_DARK == tokens.ACCENT and tokens.MAP_PATH_LIGHT == tokens.ACCENT_FOCUS


def test_every_map_token_pair_is_in_the_contrast_table_and_the_digits_on_a_hit_are_13_63(qapp):
    """M-1: the digits on a hit are ink on map-hit-fill, 13.63:1 by computation; and every map mark
    that is drawn on the canvas has its row (the overlay is the composite over the canvas)."""
    rows = {(fg, bg): minimum for fg, bg, minimum in CONTRAST_PAIRS}
    assert rows[(tokens.INK, tokens.MAP_HIT_FILL)] == 13.63
    assert contrast(QColor(tokens.INK), QColor(tokens.MAP_HIT_FILL)) == pytest.approx(13.63, abs=0.01)
    for fg in (
        tokens.MAP_HIT_OUTLINE, tokens.MAP_MISS, tokens.MAP_SKIPPED, tokens.MAP_SLOT,
        tokens.MAP_PATH_DARK, tokens.MAP_PATH_LIGHT, tokens.MAP_FIXATION, tokens.MAP_OVERLAY_ON_PANEL,
    ):
        assert (fg, tokens.PANEL) in rows, fg
        assert contrast(QColor(fg), QColor(tokens.PANEL)) >= 3.0, fg  # a non-text mark: 3:1


def test_the_overlay_composite_is_the_overlay_at_alpha_200_over_the_canvas():
    overlay, panel = QColor(tokens.MAP_OVERLAY), QColor(tokens.PANEL)
    alpha = tokens.MAP_OVERLAY_ALPHA / 255
    blended = QColor(
        *(round(a * alpha + b * (1 - alpha)) for a, b in zip(overlay.getRgb()[:3], panel.getRgb()[:3], strict=True))
    )
    assert blended.name().upper() == tokens.MAP_OVERLAY_ON_PANEL == "#4F87B3"
    assert contrast(blended, panel) == pytest.approx(3.85, abs=0.01)


def test_the_legacy_report_colours_and_the_old_theme_names_are_gone():
    """SPEC-design-system-phase4.md H1: nothing imports them any more."""
    assert not hasattr(tokens, "LEGACY_REPORT_COLOURS") and not hasattr(tokens, "LegacyReportColours")
    for name in (
        "BACKGROUND", "PANEL_BG", "BORDER", "MUTED", "SOFT_ACCENT", "SOFT_ACCENT_TEXT", "TITLEBAR_BG",
        "TITLEBAR_TEXT", "NEUTRAL_BADGE_BG", "DISABLED_BG", "DISABLED_BORDER", "DISABLED_TEXT",
        "CONTROL_BORDER", "BANNER_BORDER", "WARNING_BG", "WARNING_BORDER",
        "ACCENT_GRADIENT_START", "ACCENT_GRADIENT_END",
    ):
        assert not hasattr(wtmh_theme, name), name
    for path in sorted(UI.glob("*.py")) + sorted((UI.parent.parent / "tests").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if path.name != "test_design_tokens.py":
            assert "LEGACY_REPORT_COLOURS" not in source, path.name


def test_the_painters_draw_with_the_map_tokens():
    from src.ui import target_map_follow, target_map_paint

    assert (target_map_follow.FOLLOW_ON, target_map_follow.FOLLOW_OFF) == (tokens.MAP_PATH_DARK, tokens.MAP_SKIPPED)
    assert target_map_follow.TRACK == tokens.MAP_SLOT
    assert target_map_paint.TRIAL_PATH_DARK.name().upper() == tokens.MAP_PATH_DARK
    assert target_map_paint.TRIAL_PATH_LIGHT.name().upper() == tokens.MAP_PATH_LIGHT
    assert tokens.PANEL in map_legend.LEGEND_STYLE and tokens.BORDER_SUBTLE in map_legend.LEGEND_STYLE


# -- P3: the type scale -----------------------------------------------------------------------------


def test_the_type_scale_is_12_14_16_20_28():
    assert TYPE_SCALE == (12, 14, 16, 20, 28)
    assert (tokens.TYPE_BODY, tokens.TYPE_DISPLAY, tokens.TYPE_HEADING) == (14, 28, 20)


@pytest.mark.parametrize("name", SHEETS)
def test_every_font_size_in_a_sheet_is_a_type_scale_value(name):
    sizes = {int(n) for n in re.findall(r"font-size:\s*(\d+)px", SHEETS[name])}
    assert sizes <= set(TYPE_SCALE), sizes


def test_every_font_size_in_the_ui_source_is_a_type_scale_name_or_value():
    """The inline sheets (the Start page) too: a literal px size is on the scale, or it is a
    token name. The canvas has its own sizes (it is not in the scale)."""
    for path in sorted(UI.glob("*.py")):
        if path.name.startswith("canvas") or path.name == "report_pdf.py":
            continue  # the canvas draws its own text; the PDF is in pt
        for literal, name in re.findall(r"font-size:\s*(?:(\d+)px|\{(\w+)\}px)", path.read_text(encoding="utf-8")):
            if literal:
                assert int(literal) in TYPE_SCALE, (path.name, literal)
            else:
                assert name in {"pixel_size"} or hasattr(tokens, name), (path.name, name)


def test_the_start_page_text_sizes_are_on_the_scale(qapp):
    page = StartTestPage()
    cfg = load_task_config("click_grid")
    cfg["task"]["trials"] = 6
    page.set_test(test_name="Grid Click 1", task_id="click_grid", cfg=cfg)
    sizes = set()
    for label in page.card.findChildren(QLabel):
        sizes.update(int(n) for n in re.findall(r"font-size:\s*(\d+)px", label.styleSheet()))
    assert sizes and sizes <= set(TYPE_SCALE), sizes
    assert 20 in sizes and 16 in sizes  # the heading and the read-aloud text


def test_the_page_title_is_28_px_and_the_section_title_20_px():
    title = re.search(r"QLabel#wtmhPageTitle\s*\{([^}]*)\}", STYLESHEET).group(1)
    section = re.search(r"QLabel#wtmhSectionTitle\s*\{([^}]*)\}", STYLESHEET).group(1)
    assert "font-size: 28px" in title and "font-weight: 700" in title
    assert "font-size: 20px" in section and "font-weight: 600" in section


def test_the_application_font_is_segoe_ui_at_14_px(qapp):
    before = QFont(qapp.font())
    try:
        apply_application_font(qapp)
        assert qapp.font().pixelSize() == 14 and qapp.font().family() == "Segoe UI"
    finally:
        qapp.setFont(before)


# -- H5-H7: sizes and states ------------------------------------------------------------------------


def themed_column(*widgets: QWidget) -> QWidget:
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    layout = QVBoxLayout(root)
    for widget in widgets:
        layout.addWidget(widget)
    root.resize(520, 60 + 50 * len(widgets))
    root.show()
    QCoreApplication.processEvents()
    return root


def tier(name: str, text: str = "OK", enabled: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.setEnabled(enabled)
    return button


@pytest.mark.parametrize("name", ["wtmhPrimary", "wtmhGhost", "wtmhSecondary", "wtmhTertiary", "cfgSave", "cfgPreview"])
def test_a_button_is_40_px_high_96_wide_at_least_and_keeps_its_size_in_focus(qapp, name):
    button = tier(name)
    root = themed_column(button)
    assert button.sizeHint().height() == tokens.BUTTON_HEIGHT == 40
    assert button.sizeHint().width() >= tokens.BUTTON_MIN_WIDTH == 96
    before = (button.sizeHint(), button.height())
    button.setFocus()
    QCoreApplication.processEvents()
    assert button.hasFocus()
    assert (button.sizeHint(), button.height()) == before  # the focus border takes from the padding
    assert root.isVisible()


@pytest.mark.parametrize("make", [QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox],
                         ids=["line edit", "combo box", "spin box", "double spin box"])
def test_a_single_line_field_is_36_px_high_and_keeps_its_size_in_focus(qapp, make):
    field = make()
    root = themed_column(field)
    assert field.height() == tokens.FIELD_HEIGHT == 36
    field.setFocus()
    QCoreApplication.processEvents()
    assert field.hasFocus() and field.height() == 36
    assert root.isVisible()


def test_the_indicators_are_20_px_in_every_state(qapp):
    boxes = [QCheckBox(""), QRadioButton("")]
    root = themed_column(*boxes)
    for box in boxes:
        for state in ("plain", "checked", "focus", "disabled"):
            box.setEnabled(state != "disabled")
            box.setChecked(state in ("checked", "disabled"))
            if state == "focus":
                box.setFocus()
            QCoreApplication.processEvents()
            assert box.sizeHint().height() == tokens.INDICATOR_SIZE == 20, (type(box).__name__, state)
    assert root.isVisible()


def test_a_slider_has_a_20_px_handle_on_a_4_px_groove(qapp):
    slider = QSlider(Qt.Orientation.Horizontal)
    root = themed_column(slider)
    from PySide6.QtWidgets import QStyle, QStyleOptionSlider

    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, slider)
    groove = slider.style().subControlRect(QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, slider)
    assert (handle.width(), handle.height(), groove.height()) == (20, 20, 4)
    assert slider.height() >= 20  # the handle is not clipped by the widget
    assert root.isVisible()


def colours(widget: QWidget, *, focused: bool = False) -> set[str]:
    """Every colour in a grab of ``widget``; without ``focused`` the first widget of a shown
    window (which Qt focuses) gives its focus up first."""
    if not focused:
        widget.clearFocus()
        QCoreApplication.processEvents()
    image: QImage = widget.grab().toImage()
    return {image.pixelColor(x, y).name().lower() for x in range(image.width()) for y in range(image.height())}


def darkest_lightness(widget: QWidget) -> int:
    image: QImage = widget.grab().toImage()
    return min(image.pixelColor(x, y).lightness() for x in range(image.width()) for y in range(image.height()))


@pytest.mark.parametrize("make", [QCheckBox, QRadioButton], ids=["check box", "radio"])
def test_a_disabled_checked_indicator_is_grey_not_the_accent_blue(qapp, make):
    box = make("")
    box.setChecked(True)
    box.setEnabled(False)
    root = themed_column(box)
    seen = colours(box)
    assert tokens.BORDER_STRONG.lower() in seen  # border-strong, U4
    assert tokens.ACCENT.lower() not in seen and tokens.ACCENT_FOCUS.lower() not in seen
    assert root.isVisible()


@pytest.mark.parametrize("make", [QCheckBox, QRadioButton], ids=["check box", "radio"])
def test_an_enabled_checked_indicator_is_the_accent_blue(qapp, make):
    box = make("")
    box.setChecked(True)
    root = themed_column(box)
    assert tokens.ACCENT.lower() in colours(box)
    assert root.isVisible()


@pytest.mark.parametrize("make", [QCheckBox, QRadioButton], ids=["check box", "radio"])
def test_a_disabled_unchecked_indicator_is_the_disabled_fill_with_a_strong_outline(qapp, make):
    box = make("")
    box.setEnabled(False)
    root = themed_column(box)
    assert tokens.DISABLED_FILL.lower() in colours(box)
    # the outline is border-strong (a circle's edge is anti-aliased, so "about")
    assert QColor(tokens.BORDER_STRONG).lightness() - 3 <= darkest_lightness(box) <= QColor(tokens.BORDER_STRONG).lightness() + 20
    assert root.isVisible()


@pytest.mark.parametrize(
    "make", [QCheckBox, QRadioButton, QLineEdit, QComboBox, QSpinBox, QPushButton],
    ids=["check box", "radio", "line edit", "combo box", "spin box", "button"],
)
def test_a_focused_control_shows_the_accent_focus_colour(qapp, make):
    widget = tier("wtmhPrimary") if make is QPushButton else make()
    root = themed_column(widget)
    widget.setFocus()
    QCoreApplication.processEvents()
    assert widget.hasFocus()
    assert tokens.ACCENT_FOCUS.lower() in colours(widget, focused=True)
    assert root.isVisible()


def test_every_focusable_control_class_has_a_focus_rule():
    for selector in (
        "QPushButton#wtmhPrimary:focus", "QPushButton#wtmhGhost:focus", "QPushButton#wtmhTertiary:focus",
        "QWidget#wtmhDashboard QLineEdit:focus", "QWidget#wtmhDashboard QComboBox:focus",
        "QWidget#wtmhDashboard QDateEdit:focus", "QWidget#wtmhDashboard QSpinBox:focus",
        "QWidget#wtmhDashboard QDoubleSpinBox:focus", "QWidget#wtmhDashboard QTextEdit:focus",
        "QWidget#wtmhDashboard QPlainTextEdit:focus", "QWidget#wtmhDashboard QCheckBox::indicator:focus",
        "QWidget#wtmhDashboard QRadioButton::indicator:focus", "QWidget#wtmhDashboard QSlider::handle:horizontal:focus",
    ):
        assert selector in STYLESHEET, selector
    assert STYLESHEET.count(tokens.ACCENT_FOCUS) >= 8


def test_a_disabled_slider_handle_is_border_strong(qapp):
    assert re.search(
        r"QSlider::handle:horizontal:disabled\s*\{[^}]*background:\s*" + tokens.BORDER_STRONG, STYLESHEET
    )


# -- H8: the banners -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "border"),
    [("Info", tokens.BORDER_STRONG), ("Warning", tokens.WARNING), ("Success", tokens.SUCCESS), ("Error", tokens.DANGER)],
)
def test_a_banner_is_white_with_a_one_px_border_in_its_state_colour(name, border):
    blocks = re.findall(rf"QFrame#wtmhAlert{name}\s*\{{([^}}]*)\}}", STYLESHEET)
    block = next(b for b in blocks if "background" in b)
    assert f"background: {tokens.PANEL}" in block and f"border: 1px solid {border}" in block
    assert "border-left" not in block


def test_no_banner_rule_has_a_left_stripe_or_a_tint():
    alert_rules = re.findall(r"QFrame#wtmhAlert\w+[^{]*\{[^}]*\}", STYLESHEET)
    assert alert_rules and all("border-left" not in rule for rule in alert_rules)


# -- the tables (H5) -------------------------------------------------------------------------------


def test_a_table_has_square_corners_a_header_fill_and_ink_header_text():
    table = re.search(r"QTableWidget\s*\{([^}]*)\}", STYLESHEET).group(1)
    header = re.search(r"QHeaderView::section\s*\{([^}]*)\}", STYLESHEET).group(1)
    assert "border-radius: 0px" in table
    assert f"background: {tokens.HEADER}" in header and f"color: {tokens.INK}" in header and "font-weight: 600" in header
    selected = re.search(r"wtmhTestTable::item:selected\s*\{([^}]*)\}", STYLESHEET).group(1)
    assert f"background: {tokens.ROW_SELECTED}" in selected


def test_a_focused_table_has_the_accent_focus_border():
    assert f"QTableWidget:focus {{ border: 2px solid {tokens.ACCENT_FOCUS}; }}" in STYLESHEET
    assert f"QTableView#reportTrialTable:focus {{ border: 2px solid {tokens.ACCENT_FOCUS}; }}" in frozen_table._STYLE


def test_the_table_row_is_40_px():
    assert tokens.TABLE_ROW_HEIGHT == 40
