"""SPEC-design-system-phase4.md H3, H5-H7, M-3, M-4: the report page's title and widths, the warning
alert, the legend's Scanpath line, the Detailed table (two-line headers, the 13 columns within
1,370 px, the Outcome badges, the selected row) and the minimum size of the selected trial's map
(it fills its column since the user's decision of 2026-10-09; ``test_report_map_fill.py`` holds that).

Offscreen Qt cannot measure text, so the width claims run on real Segoe UI (registered from the
Windows font folder for the module; skipped where it is missing). They are claims about column
widths, not about the window: the on-screen check is the live one.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QStyleFactory,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from src.data.report_cache import build_report
from src.ui.alert_box import AlertBox
from src.ui.design_tokens import (
    HEADER,
    PANEL,
    ROW_SELECTED,
    TABLE_ROW_HEIGHT,
    TYPE_BODY,
    TYPE_CAPTION,
    TYPE_DISPLAY,
    TYPE_HEADING,
)
from src.ui.frozen_table import BADGE_KIND_ROLE, FrozenColumnTable, two_lines
from src.ui.map_legend import (
    FOLLOW_LEGEND_ENTRIES,
    LEGEND_ENTRIES,
    NUMBERS_NOTE,
    POINTER_LEGEND_ENTRIES,
    POINTER_NUMBERS_NOTE,
    SCANPATH_NOTE,
    MapLegend,
)
from src.ui.report_format import SWITCH_TRIAL_COLUMNS, TRIAL_COLUMNS
from src.ui.report_format_follow import FOLLOW_TRIAL_COLUMNS
from src.ui.report_page import (
    EVALUATOR_EDIT_WIDTH,
    NAME_EDIT_WIDTH,
    NOTES_HEIGHT,
    SIDEBAR_WIDTH,
    ReportPage,
)
from src.ui.report_views import (
    EYE_COLUMN_WIDTHS,
    OUTCOME_KINDS,
    TABLE_MIN_ROWS,
    TRIAL_LEGEND,
)
from src.ui.target_map import MAP_MIN_SIZE
from src.ui.wtmh_theme import STYLESHEET
from tests import real_fonts
from tests.follow_fixtures import folder as follow_folder
from tests.report_ui_fixtures import SWITCH_META, SWITCH_PRESSES, folder_report

DETAILED_TABLE_MAX = 1370  # the room the Detailed table has at 1920 x 1080 (SPEC H7)
LEGEND_WIDTH = 880  # an arbitrary legend width for the stand-alone legend test


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))  # the dashboard's own style
    return app


@pytest.fixture(scope="module")
def segoe(qapp):
    yield from real_fonts.segoe_ui(qapp)


def themed_page(report, *, width=1920, height=1000, view="summary") -> tuple[QWidget, ReportPage]:
    """The page under the dashboard's sheet (as ``ReportFlow.open`` puts it), shown."""
    root = QWidget()
    root.setObjectName("wtmhDashboard")
    root.setStyleSheet(STYLESHEET)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    page = ReportPage()
    layout.addWidget(page)
    page.set_report(report, test_name="Grid Click 1")
    if view == "detailed":
        page.show_detailed()
    root.resize(width, height)
    root.show()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    return root, page


def switch_report(tmp_path):
    return folder_report(tmp_path, presses=SWITCH_PRESSES, **SWITCH_META)


# -- H6: the Summary page -------------------------------------------------------------------------------------


def test_the_test_name_stands_at_the_heading_step_under_the_page_title(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path))
    try:
        assert page.title_label.text() == "Summary Results" and page.test_name_label.text() == "Grid Click 1"
        for label in (page.title_label, page.test_name_label):
            label.ensurePolished()  # the sheet's font is resolved when a widget is polished
        assert page.title_label.font().pixelSize() == TYPE_DISPLAY
        assert page.test_name_label.objectName() == "wtmhSectionTitle"
        assert page.test_name_label.font().pixelSize() == TYPE_HEADING and page.test_name_label.font().weight() >= 600
        assert page.test_name_label.geometry().top() >= page.title_label.geometry().bottom()  # under it
        page.name_edit.setText("Renamed")  # it follows the field
        assert page.test_name_label.text() == "Renamed"
        page.name_edit.setText("   ")
        assert page.test_name_label.isHidden()
        page.show_detailed()
        assert page.title_label.text() == "Detailed Results"
    finally:
        root.close()


def test_the_test_name_label_shows_what_the_operator_typed_as_text_not_markup(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="<b>Bold</b> & co")
    assert page.test_name_label.text() == "<b>Bold</b> & co"
    assert page.test_name_label.textFormat() == Qt.TextFormat.PlainText


def test_the_name_and_evaluator_fields_and_the_notes_have_their_phase_4_sizes(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    assert (NAME_EDIT_WIDTH, EVALUATOR_EDIT_WIDTH, NOTES_HEIGHT, SIDEBAR_WIDTH) == (480, 320, 84, 460)
    assert page.name_edit.minimumWidth() == page.name_edit.maximumWidth() == 480
    assert page.evaluator_edit.minimumWidth() == page.evaluator_edit.maximumWidth() == 320
    assert page.notes_edit.minimumHeight() == page.notes_edit.maximumHeight() == 84


def test_the_summary_main_column_takes_the_whole_stack_width_and_the_sidebar_keeps_460(qapp, tmp_path):
    """The 1100 px cap of H6 is lifted (the user's decision of 2026-10-09: no empty space at the right)."""
    root, page = themed_page(folder_report(tmp_path), width=1920)
    try:
        assert page.summary.maximumWidth() > 1920  # no cap left
        assert page.summary.width() == page._stack.width() > 1100
        sidebar = page.config_table.parentWidget().parentWidget().parentWidget()
        assert sidebar.width() == 460
        assert page.summary.x() == 0
        assert page.summary.mapTo(page, page.summary.rect().topLeft()).x() >= sidebar.x() + 460
        assert page.detailed.maximumWidth() > 1100  # and the Detailed table has the room
        content = page.summary.widget()
        assert page.summary.table.width() == content.width() - 8  # the Summary table spans the column
    finally:
        root.close()


def test_the_eye_metrics_table_is_320_plus_320_px(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path))
    try:
        table = page.summary.eye_table
        assert EYE_COLUMN_WIDTHS == (320, 320)
        assert (table.columnWidth(0), table.columnWidth(1)) == (320, 320)
        assert table.width() == 640 + 2 * table.frameWidth()
        assert table.rowCount() == 10 and table.height() == table.maximumHeight()  # still as tall as its rows
    finally:
        root.close()


def test_the_early_end_banner_is_a_phase_2_warning_alert(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path, planned=18), test_name="Grid Click 1")
    page.show()
    assert isinstance(page.banner, AlertBox) and page.banner.kind() == "warning"
    assert page.banner.word() == "Warning:" and page.banner_label is page.banner.label
    assert page.banner_label.text() == "Ended early: 6 of 18 trials" and not page.banner.isHidden()
    page.set_report(folder_report(tmp_path / "b"), test_name="Second")
    assert page.banner.isHidden()


def test_a_low_gaze_quality_warning_is_the_same_alert(qapp, tmp_path):
    report = folder_report(tmp_path)
    report["quality"] = {"valid_share": 0.72, "warnings": [{"code": "low_valid_gaze", "text": "x"}]}
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    page.show()
    assert page.banner.kind() == "warning" and "72 % valid" in page.banner_label.text()


def test_the_summary_legend_has_no_tint_and_the_scanpath_line_and_the_detailed_one_does_not(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    assert "Scanpath: fixations joined in time order, all trials" == page.summary.legend.overlay_label.text()
    assert page.detailed.legend.overlay_label.isHidden()  # the selected trial's view has no overlay line


# -- H5 / D3: the legend sentence as two caption lines ------------------------------------------------------------


def test_the_selected_trials_legend_is_two_caption_lines_without_an_interpunct(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    label = page.detailed.trial_legend
    assert label.objectName() == "wtmhCaption" and label.text() == TRIAL_LEGEND
    first, second = label.text().split("\n")
    assert first and second and "·" not in label.text()
    assert "dark to light with time" in second and "numbered circles" in first
    page.set_report(build_report(follow_folder(tmp_path / "f")), test_name="Follow 1")
    assert page.detailed.trial_legend.text().count("\n") == 1 and "dashed grey where it was off it" in page.detailed.trial_legend.text()


def test_a_caption_label_is_12_px_in_the_dashboard_sheet(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed")
    try:
        page.detailed.trial_legend.ensurePolished()
        assert page.detailed.trial_legend.font().pixelSize() == TYPE_CAPTION
    finally:
        root.close()


# -- H7: the Detailed page ---------------------------------------------------------------------------------------


def test_the_map_of_the_selected_trial_is_never_smaller_than_720_by_405(qapp, tmp_path):
    """A page that is not shown has no room to give: the map is at its minimum (it grows with the
    column once the page has a size; see ``test_report_map_fill.py``)."""
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    page.show_detailed()
    assert MAP_MIN_SIZE == (720, 405)
    shown = page.detailed.map
    assert shown.width() == 720 and shown.height() >= 405  # the canvas's aspect (1640 x 957) is a little taller than 16:9
    assert shown.size() == shown.fill_size(0, 0)  # the minimum
    assert shown.minimumSize() == shown.maximumSize()
    assert shown.trial() == 0  # and it is the selected trial's


def test_two_lines_splits_a_label_at_the_space_that_makes_the_longer_line_shortest():
    assert two_lines("Reaction Time (s)") == "Reaction\nTime (s)"
    assert two_lines("Mean fix. dur. (s)") == "Mean fix.\ndur. (s)"
    assert two_lines("Mean peak vel. (deg/s)") == "Mean peak\nvel. (deg/s)"
    assert two_lines("Size (deg)") == "Size\n(deg)"
    assert two_lines("Trial Time (s)") == "Trial\nTime (s)"
    assert two_lines("Outcome") == "Outcome" and two_lines("") == ""  # one word: one line
    for label in (*TRIAL_COLUMNS, *SWITCH_TRIAL_COLUMNS, *FOLLOW_TRIAL_COLUMNS):
        lines = two_lines(label).split("\n")
        assert len(lines) <= 2 and " ".join(lines) == label  # never a word cut, never a third line


def test_the_detailed_headers_are_on_two_lines_and_the_columns_keep_their_words(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    table = page.detailed.table
    shown = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    assert shown[5] == "Reaction\nTime (s)" and shown[8] == "Mean fix.\ndur. (s)" and shown[3] == "Outcome"
    assert [label.replace("\n", " ") for label in shown] == list(TRIAL_COLUMNS)


def test_the_thirteen_columns_fit_1370_px_by_their_widths(qapp, segoe, tmp_path):
    """M-3 by column-width sum, on real Segoe UI (the live check measures the window): the sort
    arrow's room is in each width, and the Trial column stays the frozen one."""
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    page.show_detailed()
    table = page.detailed.table
    widths = [table.columnWidth(c) for c in range(table.columnCount())]
    assert len(widths) == 13
    assert sum(widths) == table.columns_width() <= DETAILED_TABLE_MAX - 2 * table.frameWidth()
    assert sum(widths) < 1250  # and with room to spare for a vertical scroll bar and a wider cell
    assert [table.frozen_view.isColumnHidden(c) for c in range(13)] == [False] + [True] * 12
    assert table.frozen_view.columnWidth(0) == widths[0]


@pytest.mark.parametrize("layout", ["switch", "follow", "no gaze"])
def test_the_other_layouts_fit_1370_px_too(qapp, segoe, tmp_path, layout):
    if layout == "switch":
        report = switch_report(tmp_path)
    elif layout == "follow":
        report = build_report(follow_folder(tmp_path))
    else:
        report = folder_report(tmp_path)
        report["session"]["gaze_recorded"] = False  # "not recorded" in the six eye columns
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    page.show_detailed()
    table = page.detailed.table
    assert table.columns_width() <= DETAILED_TABLE_MAX - 2 * table.frameWidth(), table.columnCount()


def test_at_1920_the_table_shows_its_columns_without_a_horizontal_scroll_bar(qapp, segoe, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed")
    try:
        table = page.detailed.table
        assert table.viewport().width() >= table.columns_width()
        assert table.horizontalScrollBar().maximum() == 0
        narrow = FrozenColumnTable(TRIAL_COLUMNS)  # and on a narrower one it still scrolls
        narrow.set_columns([two_lines(c) for c in TRIAL_COLUMNS])
        narrow.setRowCount(1)
        narrow.resize(600, 200)
        narrow.show()
        narrow.fit_columns()
        QCoreApplication.processEvents()
        assert narrow.horizontalScrollBar().maximum() > 0
    finally:
        root.close()


def test_a_two_line_header_is_as_high_in_the_frozen_column_as_beside_it(qapp, segoe, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed")
    try:
        table = page.detailed.table
        one_line = QFontMetrics(table.table_fonts()[1]).height()
        assert table.horizontalHeader().height() >= 2 * one_line  # two lines
        assert table.frozen_view.horizontalHeader().height() == table.horizontalHeader().height()
        assert table.frozen_view.geometry().height() >= table.viewport().height()
    finally:
        root.close()


def test_every_column_is_as_wide_as_its_widest_cell_or_header_line_plus_room(qapp, segoe, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    table = page.detailed.table
    body, header = QFontMetrics(table.table_fonts()[0]), QFontMetrics(table.table_fonts()[1])
    for c in range(table.columnCount()):
        lines = table.horizontalHeaderItem(c).text().split("\n")
        need = max(header.horizontalAdvance(line) for line in lines) + 18
        for r in range(table.rowCount()):
            badge = table.badge_at(r) if c == table.badge_column else None
            need = max(need, badge.width() + 18 if badge else body.horizontalAdvance(table.item(r, c).text()) + 18)
        assert table.columnWidth(c) >= need, c


# -- H7 / M-4: the Outcome badges ------------------------------------------------------------------------------------


def test_the_outcome_cells_are_status_badges_with_a_glyph_and_the_word(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    table = page.detailed.table
    assert table.badge_column == 3
    shown = [(table.badge_at(r).kind(), table.badge_at(r).text()) for r in range(table.rowCount())]
    assert shown == [
        ("done", "Hit"), ("disconnected", "Not selected"), ("done", "Hit"), ("skipped", "Skipped"),
        ("done", "Hit"), ("done", "Hit"),
    ]
    assert [table.item(r, 3).text() for r in range(6)] == [word for _kind, word in shown]  # the text is still there
    assert all(table.badge_at(r).look().glyph for r in range(6))  # a glyph and a word, never colour alone
    assert {table.badge_at(0).look().glyph, table.badge_at(1).look().glyph, table.badge_at(3).look().glyph} == {
        "circle", "square", "dashed"
    }


def test_the_badge_replaces_the_cell_text_on_screen_and_only_there(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    table = page.detailed.table
    option = QStyleOptionViewItem()
    delegate = table.itemDelegate()
    delegate.initStyleOption(option, table.model().index(0, 3))
    assert option.text == ""  # the badge says it
    delegate.initStyleOption(option, table.model().index(0, 4))
    assert option.text == table.item(0, 4).text()  # every other cell keeps its text


def test_an_outcome_the_report_could_not_tell_keeps_its_text_and_has_no_badge(qapp, tmp_path):
    report = folder_report(tmp_path)
    report["trials"][1]["outcome"] = None
    page = ReportPage()
    page.set_report(report, test_name="Grid Click 1")
    table = page.detailed.table
    assert table.badge_at(1) is None and table.item(1, 3).text() == "not recorded"
    option = QStyleOptionViewItem()
    table.itemDelegate().initStyleOption(option, table.model().index(1, 3))
    assert option.text == "not recorded"


def test_the_badges_follow_their_rows_when_the_table_is_sorted(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path), test_name="Grid Click 1")
    table = page.detailed.table
    for column in (3, 5, 0):  # by Outcome, by Reaction time, back to Trial
        table.sortRequested.emit(column)
        for r in range(table.rowCount()):
            badge = table.badge_at(r)
            assert badge is not None and badge.text() == table.item(r, 3).text(), (column, r)


def test_a_follow_report_shows_followed_and_not_followed_badges(qapp, tmp_path):
    page = ReportPage()
    page.set_report(build_report(follow_folder(tmp_path)), test_name="Follow 1")
    table = page.detailed.table
    assert table.badge_column == FOLLOW_TRIAL_COLUMNS.index("Outcome") == 2
    assert [(table.badge_at(r).kind(), table.badge_at(r).text()) for r in range(3)] == [
        ("done", "Followed"), ("done", "Followed"), ("disconnected", "Not followed"),
    ]
    assert set(OUTCOME_KINDS) == {"hit", "timeout", "skipped", "followed", "not_followed"}


def test_a_new_report_clears_the_old_badges(qapp, tmp_path):
    page = ReportPage()
    page.set_report(folder_report(tmp_path / "a"), test_name="Grid Click 1")
    page.set_report(build_report(follow_folder(tmp_path / "b")), test_name="Follow 1")
    table = page.detailed.table
    assert table.badge_column == 2
    assert all(table.item(r, 3).data(BADGE_KIND_ROLE) is None for r in range(table.rowCount()))  # the old Outcome column
    page.set_report(folder_report(tmp_path / "c"), test_name="Grid Click 1")
    assert table.badge_column == 3 and all(table.item(r, 2).data(BADGE_KIND_ROLE) is None for r in range(table.rowCount()))


# -- H7 / M-4: the selected row ------------------------------------------------------------------------------------


def test_the_selected_row_is_the_row_selected_fill_and_nothing_is_bold(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed")
    try:
        table = page.detailed.table
        table.selectRow(1)
        QCoreApplication.processEvents()
        image = table.viewport().grab().toImage()
        selected = table.visualRect(table.model().index(1, 4))
        other = table.visualRect(table.model().index(2, 4))
        edge = QColor(image.pixelColor(selected.right() - 3, selected.center().y()))
        assert edge.name().lower() == ROW_SELECTED.lower()  # the fill
        assert QColor(image.pixelColor(other.right() - 3, other.center().y())).name().lower() == PANEL.lower()
        option = QStyleOptionViewItem()
        option.state |= QStyleOptionViewItem.StateFlag.State_Selected if hasattr(
            QStyleOptionViewItem, "StateFlag"
        ) else option.state
        table.itemDelegate().initStyleOption(option, table.model().index(1, 4))
        assert not option.font.bold()  # bold was the only cue before
        assert table.font().pixelSize() == TYPE_BODY and not table.font().bold()
    finally:
        root.close()


def test_the_bold_selected_delegate_is_gone():
    import src.ui.frozen_table as frozen_table

    assert not hasattr(frozen_table, "_BoldSelectedDelegate")
    assert "font-weight: 700" not in frozen_table._STYLE and "bold" not in frozen_table._STYLE


# -- the header's empty area (the live check: a dark block right of the last column) ------------------------------


def dark_palette() -> QPalette:
    """What a dark Windows theme gives Fusion: the colours Qt paints a header's empty area with."""
    palette = QPalette()
    for role, colour in (
        (QPalette.ColorRole.Window, "#202020"), (QPalette.ColorRole.WindowText, "#FFFFFF"),
        (QPalette.ColorRole.Base, "#101010"), (QPalette.ColorRole.AlternateBase, "#202020"),
        (QPalette.ColorRole.Text, "#FFFFFF"), (QPalette.ColorRole.Button, "#303030"),
        (QPalette.ColorRole.ButtonText, "#FFFFFF"), (QPalette.ColorRole.Dark, "#050505"),
        (QPalette.ColorRole.Mid, "#101010"), (QPalette.ColorRole.Light, "#404040"),
        (QPalette.ColorRole.Midlight, "#303030"), (QPalette.ColorRole.Shadow, "#000000"),
    ):
        palette.setColor(role, QColor(colour))
    return palette


def empty_header_pixel(table: FrozenColumnTable) -> QColor:
    """The colour in the middle of the header's area to the right of its last section."""
    QCoreApplication.processEvents()
    head = table.horizontalHeader()
    assert head.length() + 40 < head.width(), (head.length(), head.width())  # there is an empty area
    image = table.grab().toImage()
    x = table.frameWidth() + head.length() + (head.width() - head.length()) // 2
    return image.pixelColor(x, table.frameWidth() + head.height() // 2)


def wide_table(columns=("Trial", "Reaction\nTime (s)", "Outcome")) -> FrozenColumnTable:
    table = FrozenColumnTable(columns)
    table.setRowCount(2)
    table.fit_columns()
    table.resize(max(1200, table.columns_width() + 600), 300)
    return table


def test_the_headers_empty_area_is_the_header_grey_not_the_palettes(qapp):
    """Qt paints the part of a header past its last section with the widget's own background,
    which is the palette's (near black in a dark theme): the style sheet names it."""
    for palette in (QPalette(), dark_palette()):
        table = wide_table()
        table.setPalette(palette)
        table.show()
        assert empty_header_pixel(table).name().lower() == HEADER.lower()
        table.close()


def test_without_the_header_rule_the_empty_area_takes_the_palettes_colour(qapp):
    """The bug itself, so the test above is not vacuous: the sheet minus its QHeaderView rule."""
    import re

    import src.ui.frozen_table as frozen_table

    without = re.sub(r"QTableView#reportTrialTable QHeaderView, [^{]*\{[^}]*\}\n", "", frozen_table._STYLE, count=1)
    assert without != frozen_table._STYLE
    table = wide_table()
    table.setStyleSheet(without)
    table.setPalette(dark_palette())
    table.show()
    assert empty_header_pixel(table).name().lower() != HEADER.lower()
    table.close()


def test_both_headers_of_the_report_table_have_the_background_rule():
    import src.ui.frozen_table as frozen_table

    sheet = " ".join(frozen_table._STYLE.split())
    assert (
        "QTableView#reportTrialTable QHeaderView, QTableView#reportTrialFrozen QHeaderView "
        f"{{ background: {HEADER}; border: none; }}"
    ) in sheet


@pytest.mark.parametrize("layout", ["selection", "switch", "follow"])
def test_every_layouts_detailed_table_has_no_dark_block_beside_its_header(qapp, segoe, tmp_path, layout):
    report = {
        "selection": lambda: folder_report(tmp_path),
        "switch": lambda: switch_report(tmp_path),
        "follow": lambda: build_report(follow_folder(tmp_path)),
    }[layout]()
    root, page = themed_page(report, view="detailed")
    try:
        table = page.detailed.table
        table.setPalette(dark_palette())
        QCoreApplication.processEvents()
        assert empty_header_pixel(table).name().lower() == HEADER.lower()
    finally:
        root.close()


# -- the Detailed table below the map, full width (the user's answer of 2026-10-09) ---------------------------------


def top_in(content: QWidget, widget: QWidget) -> int:
    return widget.mapTo(content, widget.rect().topLeft()).y()


def left_in(content: QWidget, widget: QWidget) -> int:
    return widget.mapTo(content, widget.rect().topLeft()).x()


def test_the_detailed_table_is_below_the_map_and_its_legend_at_the_full_width(qapp, segoe, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed")
    try:
        view = page.detailed
        content, table, trial_map = view.widget(), view.table, view.map
        title = next(w for w in view.findChildren(QLabel) if w.text() == "Trial-by-Trial Results")
        order = [view.selected_title, trial_map, view.line_label, view.trial_legend, title, table]
        tops = [top_in(content, w) for w in order]
        assert tops == sorted(tops) and len(set(tops)) == len(tops)  # top to bottom, in that order
        assert top_in(content, title) >= top_in(content, trial_map) + trial_map.height()  # under the map
        assert top_in(content, table) >= top_in(content, title) + title.height()  # its heading directly above it
        assert trial_map.width() >= MAP_MIN_SIZE[0] and trial_map.height() >= MAP_MIN_SIZE[1]  # at least the minimum
        assert left_in(content, table) == left_in(content, trial_map) == 0  # left-aligned, not beside the map
        assert table.width() == content.width() - 8 >= trial_map.width()  # the pane's width less its margin
    finally:
        root.close()


def test_the_legend_of_a_follow_detailed_view_is_above_the_table_too(qapp, segoe, tmp_path):
    root, page = themed_page(build_report(follow_folder(tmp_path)), view="detailed")
    try:
        view = page.detailed
        assert not view.legend.isHidden()
        content = view.widget()
        assert top_in(content, view.map) < top_in(content, view.legend) < top_in(content, view.table)
    finally:
        root.close()


def test_the_detailed_table_keeps_room_for_eight_rows_and_the_pane_scrolls(qapp, segoe, tmp_path):
    root, page = themed_page(folder_report(tmp_path), view="detailed", height=1000)  # a maximized 1080p window
    try:
        view, table = page.detailed, page.detailed.table
        assert TABLE_MIN_ROWS == 8
        assert table.minimumHeight() == table.height_for_rows(TABLE_MIN_ROWS)
        assert table.height() >= table.minimumHeight()
        assert table.viewport().height() >= TABLE_MIN_ROWS * TABLE_ROW_HEIGHT  # eight whole rows under the header
        bar = view.verticalScrollBar()
        assert bar.maximum() > 0  # the map, the legend and the table do not fit: the pane scrolls ...
        bar.setValue(bar.maximum())
        QCoreApplication.processEvents()
        assert table.mapTo(view.viewport(), table.rect().bottomLeft()).y() <= view.viewport().height()  # ... to all of it
    finally:
        root.close()


@pytest.mark.parametrize("layout", ["selection", "switch", "follow"])
def test_below_the_map_the_table_still_shows_every_column_without_a_horizontal_scroll_bar(
    qapp, segoe, tmp_path, layout
):
    """M-3 with the pane's own vertical scroll bar and, for twenty trials, the table's: the full
    width has room for the columns of every layout."""
    if layout == "follow":
        report = build_report(follow_folder(tmp_path))
    else:
        report = switch_report(tmp_path) if layout == "switch" else folder_report(tmp_path)
        base = report["trials"][0]
        report["trials"] = [dict(base, trial=i + 1) for i in range(20)]
    root, page = themed_page(report, view="detailed")
    try:
        table = page.detailed.table
        assert page.detailed.verticalScrollBar().maximum() > 0
        assert table.viewport().width() >= table.columns_width()
        assert table.horizontalScrollBar().maximum() == 0
    finally:
        root.close()


# -- H5, the user's answer of 2026-10-09: the legend's text is body size, and it still fits ------------------------


LEGEND_SETS = {
    "selection": (LEGEND_ENTRIES, NUMBERS_NOTE, SCANPATH_NOTE),
    "follow": (FOLLOW_LEGEND_ENTRIES, NUMBERS_NOTE, SCANPATH_NOTE),
    "pointer": (POINTER_LEGEND_ENTRIES, POINTER_NUMBERS_NOTE, ""),
}


def assert_nothing_clips(legend: MapLegend) -> None:
    box = legend.rect()
    assert legend.width() >= legend.minimumSizeHint().width() and legend.height() >= legend.minimumSizeHint().height()
    for label in (*legend.labels, legend.numbers_label, *([legend.overlay_label] if legend.overlay_label.text() else [])):
        assert label.width() >= label.sizeHint().width() and label.height() >= label.sizeHint().height(), label.text()
        assert box.contains(label.geometry()), label.text()


@pytest.mark.parametrize("which", list(LEGEND_SETS))
def test_the_legend_text_is_14_px_and_every_line_fits_its_box(qapp, segoe, which):
    entries, numbers, overlay = LEGEND_SETS[which]
    legend = MapLegend()
    legend.set_entries(entries, numbers, overlay)
    legend.setMaximumWidth(LEGEND_WIDTH)
    host = QWidget()
    host.setObjectName("wtmhDashboard")
    host.setStyleSheet(STYLESHEET)
    QVBoxLayout(host).addWidget(legend)
    host.resize(LEGEND_WIDTH + 20, 200)
    host.show()
    QCoreApplication.processEvents()
    try:
        for label in (*legend.labels, legend.numbers_label, *([legend.overlay_label] if overlay else [])):
            assert label.font().pixelSize() == TYPE_BODY == 14, label.text()
        assert legend.minimumSizeHint().width() < 700  # well inside the narrowest main column
        assert_nothing_clips(legend)
    finally:
        host.close()


@pytest.mark.parametrize("width", [1920, 1366])
def test_the_summary_legend_does_not_clip_at_body_size_on_a_wide_or_a_narrow_window(qapp, segoe, tmp_path, width):
    root, page = themed_page(folder_report(tmp_path), width=width, height=1000)
    try:
        legend = page.summary.legend
        assert not legend.overlay_label.isHidden()
        assert_nothing_clips(legend)
        assert legend.width() == page.summary.map.width()  # as wide as the map above it
    finally:
        root.close()
