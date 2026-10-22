"""SPEC-test-list-visual-identity.md, direction B "Record cards" (TB1-TB6, T3, T6, T7): the Test
List's rows are painted as cards (a PAGE background, no frame, no grid, 40 px cards 8 px apart,
the selected card ROW_SELECTED with an ACCENT edge, hover ACCENT_SUBTLE, keyboard focus a 2 px
ACCENT_FOCUS edge), the column labels float on PAGE with an ACCENT sort arrow, the Date is
right-aligned, and the buttons sit in a "Selected test" card whose heading follows the selection.
The page is put on the dashboard sheet, as the app has it. Offscreen Qt: the pixels sampled are
fills and edges, away from the text, so the missing offscreen fonts do not matter."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QHeaderView, QTableWidget, QVBoxLayout, QWidget

from src.engine.subject_tests import create_test, list_tests
from src.ui import design_tokens as tokens
from src.ui.test_list_row_cards import (
    CARD_GAP,
    EMPTY_STYLE,
    HEADER_HEIGHT,
    ROW_SECTION,
    TABLE_STYLE,
    CardHeader,
    CardRowDelegate,
    card_colours,
)
from src.ui.test_list_side_card import NO_SELECTION_TEXT, ElidedLabel
from src.ui.test_list_table import COL_DATE, COL_NAME, COL_STATUS, COL_TASK
from src.ui.wtmh_theme import STYLESHEET
from tests.list_page_fixtures import SUBJECT, done_test, page_for, select

PAGE, PANEL = tokens.PAGE.lower(), tokens.PANEL.lower()
EDGE, SELECTED, HOVER = tokens.BORDER_SUBTLE.lower(), tokens.ROW_SELECTED.lower(), tokens.ACCENT_SUBTLE.lower()
ACCENT, FOCUS = tokens.ACCENT.lower(), tokens.ACCENT_FOCUS.lower()
PROBE_X = 200  # inside the Test Name column (264 px wide at 1400 px offscreen), right of any name


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sessions"


def themed(page, width=1400, height=700) -> QWidget:
    """``page`` on the dashboard sheet, shown; the returned root owns it."""
    shell = QWidget()
    shell.setObjectName("wtmhDashboard")
    shell.setStyleSheet(STYLESHEET)
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(page)
    shell.resize(width, height)
    shell.show()
    QApplication.processEvents()
    return shell


def three_tests(root):
    first = create_test(root, SUBJECT, "click_grid", name="A first")
    second = done_test(root, "click_static", name="B second")
    third = done_test(root, "follow_moving", name="C third", planned=6, completed=4)
    return first, second, third


def shot(widget) -> QImage:
    return widget.grab().toImage()


def colour(image: QImage, x: int, y: int) -> str:
    return image.pixelColor(x, y).name().lower()


def column_at(table, row: int, x: int = PROBE_X) -> dict[int, str]:
    """The colours down one pixel column of ``row``'s section, by offset from its top."""
    image = shot(table.viewport())
    top = table.rowViewportPosition(row)
    return {dy: colour(image, x, top + dy) for dy in range(ROW_SECTION)}


def ink_extent(image: QImage, left: int, right: int, top: int, bottom: int) -> tuple[int, int]:
    """The leftmost and rightmost x of the dark pixels (text) inside the rectangle."""
    xs = [
        x
        for x in range(left, right)
        for y in range(top, bottom)
        if image.pixelColor(x, y).lightness() < 150
    ]
    return min(xs), max(xs)


def near(pixel: QColor, token: str, slack: int = 40) -> bool:
    want = QColor(token)
    return all(abs(a - b) <= slack for a, b in zip(pixel.getRgb()[:3], want.getRgb()[:3], strict=True))


# -- the pure part --------------------------------------------------------------------------------------


def test_card_colours_follow_the_state():
    assert card_colours(selected=False, hover=False, focused=False) == (tokens.PANEL, tokens.BORDER_SUBTLE, 1)
    assert card_colours(selected=False, hover=True, focused=False) == (tokens.ACCENT_SUBTLE, tokens.BORDER_SUBTLE, 1)
    assert card_colours(selected=True, hover=False, focused=False) == (tokens.ROW_SELECTED, tokens.ACCENT, 1)
    assert card_colours(selected=True, hover=True, focused=False) == (tokens.ROW_SELECTED, tokens.ACCENT, 1)
    assert card_colours(selected=True, hover=False, focused=True) == (tokens.ROW_SELECTED, tokens.ACCENT_FOCUS, 2)
    # the keyboard focus is shown on the selected card only
    assert card_colours(selected=False, hover=False, focused=True) == (tokens.PANEL, tokens.BORDER_SUBTLE, 1)


def test_the_row_section_is_the_card_plus_the_gap_and_both_are_tokens():
    assert (tokens.TABLE_ROW_HEIGHT, CARD_GAP, ROW_SECTION) == (40, 8, 48)
    assert CARD_GAP in tokens.SPACING_SCALE and HEADER_HEIGHT in tokens.SPACING_SCALE


def test_the_new_contrast_pairs_are_in_the_table():
    rows = {(fg, bg): minimum for fg, bg, minimum in tokens.CONTRAST_PAIRS}
    for pair in (
        (tokens.INK, tokens.ACCENT_SUBTLE),
        (tokens.TEXT_SECONDARY, tokens.ACCENT_SUBTLE),
        (tokens.ACCENT, tokens.ROW_SELECTED),
        (tokens.ACCENT_FOCUS, tokens.ROW_SELECTED),
        (tokens.DANGER, tokens.ACCENT_SUBTLE),
    ):
        assert pair in rows, pair


# -- TB1: the rows are cards ----------------------------------------------------------------------------------


def test_the_table_has_no_frame_no_grid_and_a_page_background(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    table = page.table
    assert table.frameShape() == QFrame.Shape.NoFrame and table.showGrid() is False
    assert [table.rowHeight(r) for r in range(3)] == [ROW_SECTION] * 3
    image = shot(table.viewport())
    below = table.rowViewportPosition(2) + ROW_SECTION + 20
    assert below < table.viewport().height()
    assert colour(image, PROBE_X, below) == PAGE  # under the last card: the page, not a white sheet
    assert colour(image, 0, below) == PAGE  # and no frame down the side
    shell.close()


def test_each_row_is_one_white_card_40_px_high_centred_in_its_section_with_a_subtle_edge(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    page.back_button.setFocus()
    page.table.clearSelection()
    QApplication.processEvents()
    for row in range(3):
        probe = column_at(page.table, row)
        gap = CARD_GAP // 2
        assert [probe[dy] for dy in range(gap)] == [PAGE] * gap, row  # half the gap above ...
        assert probe[gap] == EDGE and probe[gap + 39] == EDGE, row  # the 1 px edge, top and bottom
        assert {probe[dy] for dy in range(gap + 1, gap + 39)} == {PANEL}, row  # the card: 38 px of white
        assert [probe[dy] for dy in range(gap + 40, ROW_SECTION)] == [PAGE] * gap, row  # ... and below
    shell.close()


def test_a_card_spans_the_five_columns_and_has_rounded_corners(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    page.back_button.setFocus()
    page.table.clearSelection()
    QApplication.processEvents()
    table = page.table
    image = shot(table.viewport())
    top = table.rowViewportPosition(1) + CARD_GAP // 2
    mid = top + 20
    width = table.viewport().width()
    assert colour(image, 0, mid) == EDGE and colour(image, width - 1, mid) == EDGE  # the left and right edges
    for column in range(5):  # no seam where two cells meet
        x = table.columnViewportPosition(column)
        assert colour(image, x + 3, top + 3) == PANEL, column
    assert colour(image, 0, top) != EDGE  # the corner pixel is rounded off, not a square corner
    shell.close()


# -- TB2: selected, hover, keyboard focus -------------------------------------------------------------------------


def test_the_selected_card_is_row_selected_with_an_accent_edge_and_the_gap_stays_page(qapp, root):
    first, *_ = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    page.back_button.setFocus()
    select(page, first.test_id)
    QApplication.processEvents()
    assert not page.table.hasFocus()
    probe = column_at(page.table, 0)
    gap = CARD_GAP // 2
    assert probe[gap] == ACCENT and probe[gap + 39] == ACCENT
    assert {probe[dy] for dy in range(gap + 1, gap + 39)} == {SELECTED}
    # the view fills a selected cell with its own row colour first; the gap must still be the page
    assert [probe[dy] for dy in range(gap)] == [PAGE] * gap
    assert [probe[dy] for dy in range(gap + 40, ROW_SECTION)] == [PAGE] * gap
    other = column_at(page.table, 1)
    assert other[gap] == EDGE and {other[dy] for dy in range(gap + 1, gap + 39)} == {PANEL}
    shell.close()


def test_a_card_under_the_mouse_is_accent_subtle_and_leaving_clears_it(qapp, root):
    first, *_ = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    table = page.table
    page.back_button.setFocus()
    select(page, first.test_id)
    row_y = table.rowViewportPosition(1) + ROW_SECTION // 2
    QTest.mouseMove(table.viewport(), QPoint(PROBE_X, row_y))
    QApplication.processEvents()
    assert table.hover_row == 1
    hovered = column_at(table, 1)
    assert hovered[CARD_GAP // 2] == EDGE  # the edge is unchanged
    assert {hovered[dy] for dy in range(5, 43)} == {HOVER}
    assert {column_at(table, 2)[dy] for dy in range(5, 43)} == {PANEL}  # one row at a time
    # every cell of the row takes the fill, the badge's cell too
    image = shot(table.viewport())
    status_x = table.columnViewportPosition(COL_STATUS) + 150  # right of the badge
    assert colour(image, status_x, table.rowViewportPosition(1) + 20) == HOVER
    # a selected card keeps its fill under the mouse
    QTest.mouseMove(table.viewport(), QPoint(PROBE_X, table.rowViewportPosition(0) + 24))
    QApplication.processEvents()
    assert table.hover_row == 0 and {column_at(table, 0)[dy] for dy in range(5, 43)} == {SELECTED}
    QApplication.sendEvent(table.viewport(), QEvent(QEvent.Type.Leave))
    QApplication.processEvents()
    assert table.hover_row == -1
    assert {column_at(table, 1)[dy] for dy in range(5, 43)} == {PANEL}
    shell.close()


def test_the_keyboard_focus_is_a_2_px_focus_edge_on_the_selected_card_and_nothing_moves(qapp, root):
    first, *_ = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    table = page.table
    select(page, first.test_id)
    page.back_button.setFocus()
    QApplication.processEvents()
    plain = column_at(table, 0)
    before = (table.rowViewportPosition(0), table.viewport().geometry(), page.side_card.geometry())
    table.setFocus()
    QApplication.processEvents()
    assert table.hasFocus()
    focused = column_at(table, 0)
    gap = CARD_GAP // 2
    assert [focused[gap], focused[gap + 1], focused[gap + 38], focused[gap + 39]] == [FOCUS] * 4
    assert {focused[dy] for dy in range(gap + 2, gap + 38)} == {SELECTED}
    assert plain[gap] == ACCENT
    assert before == (table.rowViewportPosition(0), table.viewport().geometry(), page.side_card.geometry())
    assert {column_at(table, 1)[dy] for dy in range(5, 43)} == {PANEL}  # only the selected card
    page.back_button.setFocus()
    QApplication.processEvents()
    assert column_at(table, 0)[gap] == ACCENT  # and back to the 1 px edge
    shell.close()


# -- TB3: the header, floating labels -----------------------------------------------------------------------


def test_the_header_is_floating_labels_on_page_with_no_band_and_no_rule(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    header = page.table.horizontalHeader()
    assert isinstance(header, CardHeader) and header.height() == HEADER_HEIGHT
    assert header.sectionsClickable() and not header.isSortIndicatorShown()  # no arrow until the first click
    image = shot(header.viewport())
    for y in (0, HEADER_HEIGHT // 2 - 8, HEADER_HEIGHT - 1):  # top, upper middle, the bottom row: no rule
        assert colour(image, PROBE_X, y) == PAGE, y
    for section in range(5):
        x = header.sectionPosition(section) + header.sectionSize(section) - 2
        assert colour(image, x, HEADER_HEIGHT // 2) == PAGE, section  # no band, no separators
    shell.close()


def test_the_labels_are_left_aligned_but_the_date_label_is_right_aligned_like_its_cells(qapp, root):
    done_test(root, "click_static", name="B second", when="2026-10-06T12:00:00+00:00")
    done_test(root, "click_grid", name="A first", when="2026-10-07T12:00:00+00:00")
    page = page_for(root)
    shell = themed(page)
    table = page.table
    header = table.horizontalHeader()
    image = shot(header.viewport())
    name_left, _ = ink_extent(image, 0, header.sectionSize(COL_NAME), 0, HEADER_HEIGHT)
    assert abs(name_left - 16) <= 4  # the first label starts where the card's text does
    task = header.sectionPosition(COL_TASK)
    task_left, _ = ink_extent(image, task, task + header.sectionSize(COL_TASK), 0, HEADER_HEIGHT)
    assert abs(task_left - task - 8) <= 4
    date = header.sectionPosition(COL_DATE)
    date_end = date + header.sectionSize(COL_DATE)
    _, date_right = ink_extent(image, date, date_end, 0, HEADER_HEIGHT)
    assert abs(date_end - 16 - date_right) <= 6  # ... the Date label ends where its cells end
    # the cells: left-aligned text, the date flush right
    page.back_button.setFocus()
    table.clearSelection()  # (a selected card's accent edge is dark too)
    QApplication.processEvents()
    cells = shot(table.viewport())
    row_top = table.rowViewportPosition(0)
    _, cell_right = ink_extent(cells, date, date_end, row_top + 8, row_top + 40)
    assert abs(date_end - 16 - cell_right) <= 6
    cell_left, _ = ink_extent(cells, task, task + header.sectionSize(COL_TASK), row_top + 8, row_top + 40)
    assert abs(cell_left - task - 8) <= 4
    for row in range(table.rowCount()):
        assert table.item(row, COL_DATE).textAlignment() & Qt.AlignmentFlag.AlignRight
        assert not table.item(row, COL_TASK).textAlignment() & Qt.AlignmentFlag.AlignRight
    shell.close()


def test_a_label_under_the_mouse_is_accent_subtle(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    header = page.table.horizontalHeader()
    task = header.sectionPosition(COL_TASK)
    QTest.mouseMove(header.viewport(), QPoint(task + 20, HEADER_HEIGHT // 2))
    QApplication.processEvents()
    assert header.hover_section() == COL_TASK
    image = shot(header.viewport())
    assert colour(image, task + 4, HEADER_HEIGHT // 2) == HOVER
    assert colour(image, header.sectionPosition(COL_STATUS) + 4, HEADER_HEIGHT // 2) == PAGE
    QApplication.sendEvent(header.viewport(), QEvent(QEvent.Type.Leave))
    QApplication.processEvents()
    assert header.hover_section() == -1
    assert colour(shot(header.viewport()), task + 4, HEADER_HEIGHT // 2) == PAGE
    shell.close()


def arrow_rows(header, section: int) -> list[int]:
    """The y of every pixel in the section that is the accent colour (the sort arrow)."""
    image = shot(header.viewport())
    left = header.sectionPosition(section)
    return [
        y
        for x in range(left, left + header.sectionSize(section))
        for y in range(HEADER_HEIGHT)
        if near(image.pixelColor(x, y), tokens.ACCENT, 30)
    ]


def test_the_sort_arrow_is_accent_on_the_sorted_label_only_and_points_the_way_it_sorts(qapp, root):
    done_test(root, "click_static", name="B second")
    done_test(root, "click_grid", name="A first")
    page = page_for(root)
    shell = themed(page)
    header = page.table.horizontalHeader()
    assert all(arrow_rows(header, s) == [] for s in range(5))  # nothing before the first click
    header.sectionClicked.emit(COL_DATE)
    QApplication.processEvents()
    assert header.isSortIndicatorShown() and header.sortIndicatorSection() == COL_DATE
    rows = arrow_rows(header, COL_DATE)
    assert rows and all(arrow_rows(header, s) == [] for s in (COL_NAME, COL_TASK, COL_STATUS))
    middle = (min(rows) + max(rows)) / 2
    assert sum(y < middle for y in rows) < sum(y > middle for y in rows)  # ascending: the point is up
    header.sectionClicked.emit(COL_DATE)  # again: descending
    QApplication.processEvents()
    rows = arrow_rows(header, COL_DATE)
    middle = (min(rows) + max(rows)) / 2
    assert sum(y < middle for y in rows) > sum(y > middle for y in rows)  # the point is down
    shell.close()


# -- TB5: the badge, the editor and the keys still sit on the right row ----------------------------------------------


def test_the_badge_cell_is_still_centred_on_the_card(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    table = page.table
    for row in range(3):
        badge = table.badge_at(row)
        centre = badge.mapTo(table.viewport(), QPoint(0, badge.height() // 2)).y()
        card_centre = table.rowViewportPosition(row) + CARD_GAP // 2 + 20
        assert abs(centre - card_centre) <= 1, row
    shell.close()


def test_the_rename_editor_opens_over_the_selected_row(qapp, root):
    first, second, _ = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    select(page, second.test_id)
    editor = page.start_rename()
    row = page._row_of(second.test_id)
    cell = page.table.visualItemRect(page.table.item(row, COL_NAME))
    top_left = page.table.viewport().mapFromGlobal(editor.pos())
    assert cell.top() <= top_left.y() <= cell.bottom() and abs(top_left.x() - cell.left()) <= 4
    editor.cancel()
    shell.close()


# -- TB4: the "Selected test" card ------------------------------------------------------------------------------------


def test_the_card_holds_the_seven_buttons_in_order_under_a_heading(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page)
    card = page.side_card
    assert card.objectName() == "wtmhCard" and isinstance(card, QFrame)
    buttons = card.buttons
    assert [b.text() for b in buttons] == [
        "Add New Test", "Configure Test", "Run Test", "View Report", "Copy Test", "Delete Test",
        "Open Subject Folder",
    ]
    assert buttons == (
        page.add_button, page.configure_button, page.run_button, page.report_button, page.copy_button,
        page.delete_button, page.open_folder_button,
    )
    ys = [b.mapTo(card, QPoint(0, 0)).y() for b in buttons]
    assert ys == sorted(ys) and all(b.parentWidget() is card for b in buttons)
    assert ys[0] > card.name_label.mapTo(card, QPoint(0, 0)).y() + card.name_label.height()  # below the heading
    shell.close()


def test_the_card_has_24_px_padding_full_width_buttons_8_px_apart_and_sits_top_right(qapp, root):
    three_tests(root)
    page = page_for(root)
    shell = themed(page, 1920, 800)
    card = page.side_card
    inset = 1 + 24  # the 1 px edge and the padding
    for button in card.buttons:
        left = button.mapTo(card, QPoint(0, 0)).x()
        assert left == inset and button.width() == card.width() - 2 * inset, button.text()
        assert button.height() == tokens.BUTTON_HEIGHT
    tops = [b.mapTo(card, QPoint(0, 0)).y() for b in card.buttons]
    assert [tops[i + 1] - tops[i] - tokens.BUTTON_HEIGHT for i in range(6)] == [8] * 6
    assert card.mapTo(page, QPoint(0, 0)).y() == page.table.mapTo(page, QPoint(0, 0)).y()  # top-aligned
    assert card.mapTo(page, QPoint(card.width(), 0)).x() == page.width() - 32  # ends at the right gutter
    shell.close()


def test_the_heading_is_the_selected_tests_name_and_its_badge(qapp, root):
    first, second, third = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    card = page.side_card
    select(page, first.test_id)
    assert card.heading_text() == "A first" and card.name_label.isVisible()
    assert (card.badge.kind(), card.badge.text()) == ("not_done", "Not done") and card.badge.isVisible()
    assert card.name_label.objectName() == "wtmhSectionTitle"
    select(page, third.test_id)  # follows the selection
    assert card.heading_text() == "C third"
    assert (card.badge.kind(), card.badge.text()) == ("ended_early", "Ended early 4/6")
    select(page, second.test_id)
    assert (card.badge.kind(), card.badge.text()) == ("done", "Done")
    shell.close()


def test_with_no_selection_the_heading_says_so_in_secondary_text_and_the_buttons_do_not_move(qapp, root):
    first, *_ = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    card = page.side_card
    select(page, first.test_id)
    QApplication.processEvents()
    selected_tops = [b.mapTo(card, QPoint(0, 0)).y() for b in card.buttons]
    size = card.size()
    page.table.clearSelection()
    QApplication.processEvents()
    assert card.heading_text() == NO_SELECTION_TEXT == "No test selected"
    assert card.none_label.isVisible() and not card.name_label.isVisible() and not card.badge.isVisible()
    assert card.none_label.objectName() == "cfgAdvancedTitle"  # the heading step in TEXT_SECONDARY
    assert [b.mapTo(card, QPoint(0, 0)).y() for b in card.buttons] == selected_tops
    assert card.size() == size
    assert (card.add_button.isEnabled(), card.open_folder_button.isEnabled()) == (True, True)
    assert not any(b.isEnabled() for b in (card.configure_button, card.run_button, card.copy_button,
                                           card.delete_button, card.report_button))
    shell.close()


def test_a_blank_subject_says_no_test_selected_too(qapp, root):
    page = page_for(root, subject="")
    assert page.side_card.heading_text() == "No test selected"
    assert not page.side_card.badge.isVisible()


def test_the_heading_follows_a_sort_a_rename_and_a_reload(qapp, root):
    first, second, third = three_tests(root)
    page = page_for(root)
    shell = themed(page)
    card = page.side_card
    select(page, second.test_id)
    page.table.horizontalHeader().sectionClicked.emit(COL_TASK)  # a sort keeps the selection
    page.table.horizontalHeader().sectionClicked.emit(COL_TASK)
    QApplication.processEvents()
    assert page.selected_test().test_id == second.test_id and card.heading_text() == "B second"
    editor = page.start_rename()
    editor.line_edit.setText("Renamed here")
    assert editor.commit()
    assert card.heading_text() == "Renamed here"
    assert list_tests(root, SUBJECT).tests[1].name == "Renamed here"
    page.reload()
    assert card.heading_text() == "Renamed here"
    page._confirm_delete = lambda _test: True  # the dialog itself is tested in test_test_list_actions
    page.delete_button.click()
    assert page.selected_test() is not None and card.heading_text() == page.selected_test().name
    assert card.heading_text() != "Renamed here"
    shell.close()


def test_a_long_name_is_cut_with_an_ellipsis_and_does_not_widen_the_card(qapp, root):
    short = create_test(root, SUBJECT, "click_grid", name="Short")
    long_name = "A very long test name that goes on and on and on for the whole sixty chars"[:60]
    long_test = create_test(root, SUBJECT, "click_grid", name=long_name)
    page = page_for(root)
    shell = themed(page)
    card = page.side_card
    select(page, short.test_id)
    QApplication.processEvents()
    width, tops = card.width(), [b.mapTo(card, QPoint(0, 0)).y() for b in card.buttons]
    select(page, long_test.test_id)
    QApplication.processEvents()
    assert card.width() == width and [b.mapTo(card, QPoint(0, 0)).y() for b in card.buttons] == tops
    assert card.heading_text() == long_name  # the full name is kept ...
    assert card.name_label.text().endswith("…") and len(card.name_label.text()) < len(long_name)
    assert card.name_label.toolTip() == long_name  # ... and is the tooltip
    select(page, short.test_id)
    assert card.name_label.text() == "Short" and card.name_label.toolTip() == ""
    shell.close()


def test_an_elided_label_keeps_its_full_text(qapp):
    label = ElidedLabel("abcdefghij" * 10)
    label.resize(60, 24)
    label.show()
    QApplication.processEvents()
    assert label.full_text() == "abcdefghij" * 10 and label.text() != label.full_text()
    label.resize(2000, 24)
    QApplication.processEvents()
    assert label.text() == label.full_text()
    label.close()


# -- TB6: the empty states -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("subject", ["", "NOBODY"])
def test_the_empty_state_is_one_card_in_the_list_area(qapp, root, subject):
    page = page_for(root, subject=subject)
    shell = themed(page)
    assert page.center.currentIndex() == 1
    frame = page.empty_label.parentWidget()
    assert frame.objectName() == "wtmhEmptyTable" and frame.styleSheet() == EMPTY_STYLE
    assert frame.height() < 2 * tokens.TABLE_ROW_HEIGHT  # one card, a row's height, not a sheet to the bottom
    assert frame.height() >= tokens.TABLE_ROW_HEIGHT
    assert frame.width() == page.center.width()
    image = shot(frame)
    assert colour(image, frame.width() // 2, 0) == EDGE and colour(image, frame.width() // 2, 10) == PANEL
    assert colour(image, 0, 0) != EDGE  # rounded, like every card
    assert page.empty_label.text() == ("Enter a Subject ID in Setup." if not subject else "No tests yet. Choose Add New Test.")
    shell.close()


# -- T6: the other tables keep their look -------------------------------------------------------------------------------


def test_another_dashboard_table_keeps_the_frame_the_white_sheet_and_the_header_band(qapp):
    table = QTableWidget(2, 2)
    table.setHorizontalHeaderLabels(["One", "Two"])
    table.verticalHeader().hide()
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the focus border is the other rule, tested elsewhere
    shell = themed(table, 600, 300)
    image = shot(table)
    assert colour(image, 0, 0) == EDGE  # the 1 px frame, square corners
    assert colour(image, 300, 200) == PANEL  # the white sheet
    header = table.horizontalHeader()
    assert isinstance(header, QHeaderView) and not isinstance(header, CardHeader)
    assert colour(shot(header.viewport()), 2, 2) == tokens.HEADER.lower()
    assert table.showGrid() is True
    shell.close()


def test_the_card_look_is_scoped_to_the_test_list_by_its_own_sheet(qapp, root):
    assert "wtmhTestTable" in TABLE_STYLE and "wtmhEmptyTable" in EMPTY_STYLE
    assert "wtmhTestTable QHeaderView" not in STYLESHEET  # the global sheet keeps its one test-list rule
    page = page_for(root, subject="NOBODY")
    assert page.table.styleSheet() == TABLE_STYLE
    assert isinstance(page.table.itemDelegateForColumn(COL_STATUS), CardRowDelegate)
    assert page.table.itemDelegateForColumn(COL_STATUS) is not page.table.itemDelegateForColumn(COL_NAME)
