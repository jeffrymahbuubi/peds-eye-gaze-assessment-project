"""SPEC-test-list-visual-identity.md, direction C "Signal", on the Test List page (offscreen Qt):
every right-side button has its painted glyph in a 24 px slot with the label left-aligned after it,
every task has its glyph before its name, the Date column and its header are right-aligned with
tabular figures, a hovered row is filled across all five columns, and the sort arrow has room next to
the right-aligned Date label. Where a test measures ink it runs on the page inside the dashboard's own
sheet, with real Segoe UI (``tests/real_fonts.py``), and skips where the font is missing."""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QHoverEvent, QIcon, QImage
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.engine.subject_tests import create_test
from src.engine.task_info import TASK_INFO
from src.ui import design_tokens as tokens
from src.ui.glyphs import (
    GLYPH_COPY,
    GLYPH_DOCUMENT,
    GLYPH_FOLDER,
    GLYPH_PLAY,
    GLYPH_PLUS,
    GLYPH_SLIDERS,
    GLYPH_SQUARE,
    GLYPH_TASK_CHOICE,
    GLYPH_TASK_FOLLOW,
    GLYPH_TASK_GRID,
    GLYPH_TASK_SEARCH,
    GLYPH_TASK_STATIC,
    glyph_pixmap,
)
from src.ui.test_list_style import BUTTON_SLOT_PX, TASK_GLYPH, task_icon
from src.ui.test_list_table import COL_CONFIG, COL_DATE, COL_NAME, COL_STATUS, COL_TASK
from src.ui.wtmh_theme import STYLESHEET
from tests import real_fonts
from tests.list_page_fixtures import SUBJECT, done_test, page_for

# attribute of the page, the glyph, its colour while on, its colour while off
BUTTONS = (
    ("add_button", GLYPH_PLUS, tokens.ACCENT, tokens.TEXT_DISABLED),
    ("configure_button", GLYPH_SLIDERS, tokens.ACCENT, tokens.TEXT_DISABLED),
    ("run_button", GLYPH_PLAY, tokens.PANEL, tokens.ACCENT_DISABLED_TEXT),  # the primary: white on the accent
    ("report_button", GLYPH_DOCUMENT, tokens.ACCENT, tokens.TEXT_DISABLED),
    ("copy_button", GLYPH_COPY, tokens.ACCENT, tokens.TEXT_DISABLED),
    ("delete_button", GLYPH_SQUARE, tokens.DANGER, tokens.TEXT_DISABLED),  # the red square, as before
    ("open_folder_button", GLYPH_FOLDER, tokens.ACCENT, tokens.TEXT_DISABLED),
)
TASK_SHAPES = {
    "click_static": GLYPH_TASK_STATIC,
    "click_grid": GLYPH_TASK_GRID,
    "follow_moving": GLYPH_TASK_FOLLOW,
    "scanning": GLYPH_TASK_SEARCH,
    "choice_making": GLYPH_TASK_CHOICE,
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def fonts(qapp):
    yield from real_fonts.segoe_ui(qapp)


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sessions"


def four_tasks(root):
    """One test of each task with a glyph: Grid Click (not done), Static Click, Follow the Target,
    Scanning Search (done, with a date)."""
    create_test(root, SUBJECT, "click_grid", name="Grid Click 1")
    done_test(root, "click_static", name="Static Click 1", when="2026-10-06T12:00:00+00:00")
    done_test(root, "follow_moving", name="Follow the Target 1", when="2026-10-07T12:00:00+00:00")
    done_test(root, "scanning", name="Scanning Search 1", when="2026-10-05T12:00:00+00:00")


def themed(root, width: int = 1500):
    """The page inside the dashboard's sheet, shown: ``(shell, page)``."""
    shell = QWidget()
    shell.setObjectName("wtmhDashboard")
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    page = page_for(root)
    layout.addWidget(page)
    shell.setStyleSheet(STYLESHEET)
    shell.resize(width, 560)
    shell.show()
    for _ in range(3):
        QCoreApplication.processEvents()
    return shell, page


def settle():
    for _ in range(3):
        QCoreApplication.processEvents()


def row_of(page, name: str) -> int:
    return next(r for r in range(page.table.rowCount()) if page.table.item(r, COL_NAME).text() == name)


def hover(table, row: int | None) -> None:
    """The pointer on ``row`` (or off the table): the hover events Qt sends the viewport."""
    viewport = table.viewport()
    if row is None:
        QCoreApplication.sendEvent(viewport, QEvent(QEvent.Type.HoverLeave))
    else:
        point = QPointF(40, table.rowViewportPosition(row) + table.rowHeight(row) / 2)
        QCoreApplication.sendEvent(
            viewport,
            QHoverEvent(QEvent.Type.HoverMove, point, QPointF(viewport.mapToGlobal(point.toPoint())), QPointF(0, 0)),
        )
    settle()


def cell_sample(table, row: int, column: int, from_right: int = 4) -> str:
    """The colour of a pixel in ``column`` of ``row`` just inside the cell's right edge, where no text is."""
    image = table.viewport().grab().toImage()
    x = table.columnViewportPosition(column) + table.columnWidth(column) - from_right
    y = table.rowViewportPosition(row) + table.rowHeight(row) // 2
    return image.pixelColor(x, y).name().lower()


def ink_runs(image: QImage, x0: int, x1: int, y0: int, y1: int, background: QColor) -> list[tuple[int, int]]:
    """Runs ``(first, last)`` of columns in [x0, x1) holding a pixel clearly unlike ``background``."""
    def differs(c: QColor) -> bool:
        return abs(c.red() - background.red()) + abs(c.green() - background.green()) + abs(c.blue() - background.blue()) > 150

    columns = [x for x in range(x0, x1) if any(differs(image.pixelColor(x, y)) for y in range(y0, y1))]
    runs: list[tuple[int, int]] = []
    for x in columns:
        if runs and x == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], x)
        else:
            runs.append((x, x))
    return runs


# -- the buttons ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("attribute", "shape", "colour", "off"), BUTTONS)
def test_every_right_side_button_has_its_glyph_in_a_24_px_slot(qapp, root, attribute, shape, colour, off):
    page = page_for(root)
    button = getattr(page, attribute)
    assert not button.icon().isNull() and button.iconSize() == QSize(BUTTON_SLOT_PX, BUTTON_SLOT_PX) == QSize(24, 24)
    for mode, expected in ((QIcon.Mode.Normal, colour), (QIcon.Mode.Disabled, off)):
        drawn = button.icon().pixmap(QSize(24, 24), 1.0, mode).toImage()
        assert drawn == glyph_pixmap(shape, expected, 12, 1.0, 24).toImage(), (attribute, mode)


def test_the_seven_buttons_carry_seven_different_glyphs(qapp, root):
    page = page_for(root)
    images = [getattr(page, attribute).icon().pixmap(QSize(24, 24), 1.0, QIcon.Mode.Disabled).toImage() for attribute, *_ in BUTTONS]
    assert len({bytes(image.constBits()) for image in images}) == 7


def rule_colour(selector: str) -> str:
    """The ``color`` the dashboard's sheet gives ``selector`` (a selector as it appears in the sheet)."""
    body = re.search(rf"{re.escape(selector)}(?:,[^{{}}]*)?\{{([^}}]*)\}}", STYLESHEET).group(1)
    return re.search(r"(?<![-\w])color:\s*(#\w+)", body).group(1)


def test_a_glyph_takes_the_text_colour_of_its_tier_and_state_from_the_sheet():
    """The glyph colours of ``BUTTONS`` are the label colours the theme gives each tier."""
    assert rule_colour("QPushButton#wtmhGhost") == tokens.ACCENT
    assert rule_colour("QPushButton#wtmhGhost:disabled") == tokens.TEXT_DISABLED
    assert rule_colour("QPushButton#wtmhPrimary") == tokens.PANEL
    assert rule_colour("QPushButton#wtmhPrimary:disabled") == tokens.ACCENT_DISABLED_TEXT
    # hovered, a secondary button keeps its ACCENT label and the primary its white one, so neither glyph changes
    assert rule_colour("QPushButton#wtmhGhost:hover") == tokens.ACCENT
    assert rule_colour("QPushButton#wtmhPrimary:hover") == tokens.PANEL


def glyph_pixel(shell, button, x: int, y: int) -> str:
    """The colour painted at ``(x, y)`` of the 12 px glyph of ``button`` (its slot starts 16 px in, the glyph 6 px after)."""
    top_left = button.mapTo(shell, QPoint(0, 0))
    image = shell.grab().toImage()
    return image.pixelColor(top_left.x() + 16 + 6 + x, top_left.y() + (button.height() - 12) // 2 + y).name().lower()


def test_the_glyph_is_painted_in_the_label_colour_and_the_matrix_greys_it_with_the_label(qapp, root):
    four_tasks(root)
    shell, page = themed(root)
    select = lambda name: page.select_test(page.table.item(row_of(page, name), COL_NAME).data(Qt.ItemDataRole.UserRole))  # noqa: E731
    select("Grid Click 1")  # not done: Run Test on, View Report off
    settle()
    assert page.run_button.isEnabled() and not page.report_button.isEnabled()
    assert glyph_pixel(shell, page.run_button, 6, 6) == tokens.PANEL.lower()  # white on the accent
    assert glyph_pixel(shell, page.report_button, 5, 5) == tokens.TEXT_DISABLED.lower()
    assert glyph_pixel(shell, page.add_button, 5, 5) == tokens.ACCENT.lower()
    assert glyph_pixel(shell, page.delete_button, 6, 6) == tokens.DANGER.lower()
    select("Static Click 1")  # done: Run Test off, View Report on
    settle()
    assert not page.run_button.isEnabled() and page.report_button.isEnabled()
    assert glyph_pixel(shell, page.run_button, 6, 6) == tokens.ACCENT_DISABLED_TEXT.lower()  # the primary's pale blue
    assert glyph_pixel(shell, page.report_button, 5, 5) == tokens.ACCENT.lower()


def test_a_page_with_no_subject_greys_every_glyph(qapp, root):
    shell = QWidget()
    shell.setObjectName("wtmhDashboard")
    layout = QVBoxLayout(shell)
    page = page_for(root, subject="")
    layout.addWidget(page)
    shell.setStyleSheet(STYLESHEET)
    shell.resize(1500, 560)
    shell.show()
    settle()
    assert not any(getattr(page, attribute).isEnabled() for attribute, *_ in BUTTONS)
    assert glyph_pixel(shell, page.delete_button, 6, 6) == tokens.TEXT_DISABLED.lower()  # the red square greys too
    assert glyph_pixel(shell, page.run_button, 6, 6) == tokens.ACCENT_DISABLED_TEXT.lower()


def test_every_button_is_equally_wide_and_wide_enough_for_the_longest_label(qapp, fonts, root):
    shell, page = themed(root)
    buttons = [getattr(page, attribute) for attribute, *_ in BUTTONS]
    assert len({button.width() for button in buttons}) == 1
    assert buttons[0].width() >= 170
    assert all(button.sizeHint().width() <= button.width() for button in buttons)  # nothing is clipped


def left_ink(shell, button) -> list[tuple[int, int]]:
    """Ink runs along the middle of ``button``, inside its border: the glyph, then the label."""
    image = shell.grab().toImage()
    top_left = button.mapTo(shell, QPoint(0, 0))
    middle = top_left.y() + button.height() // 2
    background = QColor(tokens.PANEL)
    return [
        (a - top_left.x(), b - top_left.x())
        for a, b in ink_runs(image, top_left.x() + 4, top_left.x() + button.width() - 4, middle - 6, middle + 6, background)
    ]


def test_the_label_starts_after_the_slot_instead_of_in_the_middle(qapp, fonts, root):
    shell, page = themed(root)
    runs = left_ink(shell, page.add_button)
    glyph, label = runs[0], runs[1]
    # 1 px border + 15 px padding, then the 24 px slot with its 12 px glyph centred, then 4 px, then the label
    assert 20 <= glyph[0] and glyph[1] <= 32, runs
    assert 40 <= label[0] <= 50, runs  # left-aligned; centred it would start about 20 px further right
    # the labels of the shorter buttons start at the same x as the longest one's
    starts = {
        left_ink(shell, getattr(page, attribute))[1][0]
        for attribute in ("add_button", "configure_button", "open_folder_button")
    }
    assert max(starts) - min(starts) <= 3, starts


def test_the_focus_border_moves_neither_the_glyph_nor_the_label(qapp, fonts, root):
    shell, page = themed(root)
    before = left_ink(shell, page.add_button)
    page.add_button.setFocus()
    settle()
    assert page.add_button.hasFocus()
    assert left_ink(shell, page.add_button) == before


# -- the Task column --------------------------------------------------------------------------------------------


def test_each_task_has_its_glyph_before_its_name(qapp, root):
    four_tasks(root)
    page = page_for(root)
    assert TASK_GLYPH == TASK_SHAPES
    for name, task_id in (
        ("Grid Click 1", "click_grid"),
        ("Static Click 1", "click_static"),
        ("Follow the Target 1", "follow_moving"),
        ("Scanning Search 1", "scanning"),
    ):
        item = page.table.item(row_of(page, name), COL_TASK)
        drawn = item.icon().pixmap(QSize(12, 12), 1.0, QIcon.Mode.Normal).toImage()
        assert drawn == glyph_pixmap(TASK_SHAPES[task_id], tokens.ACCENT, 12).toImage(), task_id
    assert page.table.iconSize() == QSize(12, 12)


def test_choice_making_has_its_glyph_too_and_every_task_of_the_list_has_one(qapp, root):
    assert set(TASK_INFO) <= set(TASK_GLYPH)  # a task added later needs its glyph, or its names stop lining up
    create_test(root, SUBJECT, "choice_making", name="Choice-making 1")
    page = page_for(root)
    item = page.table.item(0, COL_TASK)
    assert item.text() == "Choice-making"
    drawn = item.icon().pixmap(QSize(12, 12), 1.0, QIcon.Mode.Normal).toImage()
    assert drawn == glyph_pixmap(GLYPH_TASK_CHOICE, tokens.ACCENT, 12).toImage()


def test_the_glyph_is_an_icon_and_the_cell_text_stays_the_task_name(qapp, root):
    four_tasks(root)
    page = page_for(root)
    assert sorted(row[COL_TASK] for row in page.row_texts()) == [
        "Follow the Target", "Grid Click", "Scanning Search", "Static Click",
    ]


def test_the_task_glyph_stays_the_accent_on_a_selected_row_and_a_task_without_one_has_no_icon(qapp):
    icon = task_icon("click_grid")
    selected = icon.pixmap(QSize(12, 12), 1.0, QIcon.Mode.Selected).toImage()
    assert selected == icon.pixmap(QSize(12, 12), 1.0, QIcon.Mode.Normal).toImage()  # Qt does not tint it
    assert selected.pixelColor(1, 1).name().lower() == tokens.ACCENT.lower()  # a solid corner square of the block
    assert task_icon("no_such_task") is None


def test_sorting_by_task_orders_by_the_name_and_the_glyphs_move_with_their_rows(qapp, root):
    four_tasks(root)
    page = page_for(root)
    page._on_header_clicked(COL_TASK)
    assert [row[COL_TASK] for row in page.row_texts()] == [
        "Follow the Target", "Grid Click", "Scanning Search", "Static Click",
    ]
    for row, task_id in enumerate(("follow_moving", "click_grid", "scanning", "click_static")):
        expected = glyph_pixmap(TASK_SHAPES[task_id], tokens.ACCENT, 12).toImage()
        assert page.table.item(row, COL_TASK).icon().pixmap(QSize(12, 12), 1.0).toImage() == expected


# -- the Date column ----------------------------------------------------------------------------------------------


def test_the_date_cells_and_their_header_are_right_aligned_with_tabular_figures(qapp, root):
    four_tasks(root)
    page = page_for(root)
    right = Qt.AlignmentFlag.AlignRight
    for row in range(page.table.rowCount()):
        item = page.table.item(row, COL_DATE)
        assert item.textAlignment() & right, row
        if hasattr(QFont, "Tag"):  # Qt 6.7+
            assert item.font().isFeatureSet(QFont.Tag("tnum")), row
        for column in (COL_NAME, COL_TASK, COL_CONFIG, COL_STATUS):  # the other columns are as they were
            assert not page.table.item(row, column).textAlignment() & right
    assert page.table.horizontalHeaderItem(COL_DATE).text() == "Date Complete"
    assert page.table.horizontalHeaderItem(COL_DATE).textAlignment() & right
    assert not page.table.horizontalHeaderItem(COL_NAME).textAlignment() & right


def test_the_date_text_and_its_header_end_at_the_columns_right_padding(qapp, fonts, root):
    four_tasks(root)
    shell, page = themed(root)
    table = page.table
    image = shell.grab().toImage()
    origin = table.viewport().mapTo(shell, QPoint(0, 0))
    right_edge = origin.x() + table.columnViewportPosition(COL_DATE) + table.columnWidth(COL_DATE)
    left_edge = right_edge - table.columnWidth(COL_DATE)
    row = row_of(page, "Static Click 1")
    middle = origin.y() + table.rowViewportPosition(row) + table.rowHeight(row) // 2
    text = ink_runs(image, left_edge + 2, right_edge - 2, middle - 6, middle + 6, QColor(tokens.PANEL))
    assert right_edge - 16 <= text[-1][1] <= right_edge - 8, (text, right_edge)  # the cell's padding, then the text
    assert text[0][0] > left_edge + 30  # and it is not stretched across the cell
    header_y = table.mapTo(shell, QPoint(0, 0)).y() + table.horizontalHeader().height() // 2
    label = ink_runs(image, left_edge + 2, right_edge - 2, header_y - 6, header_y + 6, QColor(tokens.HEADER))
    assert abs(label[-1][1] - text[-1][1]) <= 2, (label, text)  # the label ends where the dates end


def test_the_sort_arrow_has_room_beside_the_date_label_only_while_sorted_by_date(qapp, fonts, root):
    four_tasks(root)
    shell, page = themed(root)
    table, header = page.table, page.table.horizontalHeader()
    assert not header.property("sortedByDate")
    page._on_header_clicked(COL_DATE)
    settle()
    assert header.property("sortedByDate") is True
    image = shell.grab().toImage()
    origin = table.mapTo(shell, QPoint(0, 0))
    left_edge = origin.x() + table.frameWidth() + header.sectionViewportPosition(COL_DATE)
    right_edge = left_edge + header.sectionSize(COL_DATE)
    middle = origin.y() + header.height() // 2 + table.frameWidth()
    runs = ink_runs(image, left_edge + 2, right_edge - 2, middle - 8, middle + 8, QColor(tokens.HEADER))
    assert len(runs) >= 2 and runs[-1][1] - runs[-1][0] <= 12  # the arrow is the last, small run ...
    assert runs[-1][0] - runs[-2][1] >= 4, runs  # ... and it does not touch the label
    page._on_header_clicked(COL_TASK)  # sorted by another column: the Date label is back at the right edge
    settle()
    assert header.property("sortedByDate") is False


# -- the row hover --------------------------------------------------------------------------------------------------


def test_a_hovered_row_is_filled_across_all_five_columns_and_the_pointer_leaving_clears_it(qapp, root):
    four_tasks(root)
    shell, page = themed(root)
    table = page.table
    page.select_test(table.item(row_of(page, "Grid Click 1"), COL_NAME).data(Qt.ItemDataRole.UserRole))
    target = row_of(page, "Scanning Search 1")
    assert target != table.currentRow()
    hover(table, target)
    assert table.hover_row == target
    for column in range(5):
        assert cell_sample(table, target, column) == tokens.ACCENT_SUBTLE.lower(), column
    for other in range(table.rowCount()):
        if other not in (target, row_of(page, "Grid Click 1")):
            assert cell_sample(table, other, COL_NAME) == tokens.PANEL.lower(), other
    hover(table, None)
    assert table.hover_row == -1
    assert cell_sample(table, target, COL_NAME) == tokens.PANEL.lower()


def test_the_selected_row_keeps_its_fill_while_hovered(qapp, root):
    four_tasks(root)
    shell, page = themed(root)
    table = page.table
    selected = row_of(page, "Static Click 1")
    page.select_test(table.item(selected, COL_NAME).data(Qt.ItemDataRole.UserRole))
    settle()
    assert [cell_sample(table, selected, c) for c in range(5)] == [tokens.ROW_SELECTED.lower()] * 5
    hover(table, selected)
    assert [cell_sample(table, selected, c) for c in range(5)] == [tokens.ROW_SELECTED.lower()] * 5


def test_the_hover_follows_the_pointer_row_by_row_and_survives_a_sort(qapp, root):
    four_tasks(root)
    shell, page = themed(root)
    table = page.table
    hover(table, 1)
    assert cell_sample(table, 1, COL_NAME) == tokens.ACCENT_SUBTLE.lower()
    hover(table, 2)
    assert cell_sample(table, 1, COL_NAME) == tokens.PANEL.lower()
    assert cell_sample(table, 2, COL_NAME) == tokens.ACCENT_SUBTLE.lower()
    page._on_header_clicked(COL_TASK)  # the rows move, the pointer does not: row 2 is still the hovered one
    settle()
    assert table.hover_row == 2 and cell_sample(table, 2, COL_NAME) == tokens.ACCENT_SUBTLE.lower()
