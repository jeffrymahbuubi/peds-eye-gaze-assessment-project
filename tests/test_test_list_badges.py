"""SPEC-design-system-phase2.md H5, H12, V2 (Q2, Q4): the Test List's Status cells are status
badges (glyph + word) over items that keep their text and sort key, so sorting still works;
bold marks nothing; the table fills the window, Test Name stretching and the other columns keeping their widths; Run Test is the only primary button, Delete
Test carries the danger glyph and Back to Setup is tertiary. Offscreen Qt."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from src.engine.subject_tests import (
    STATUS_ENDED_EARLY,
    create_test,
    delete_test,
    list_tests,
    run_folder_of,
)
from src.ui.status_badge import StatusBadge
from src.ui.test_list_table import (
    COL_NAME,
    COL_STATUS,
    NAME_MIN_WIDTH,
    OTHER_COLUMN_WIDTHS,
    status_badge_state,
)
from tests.list_page_fixtures import SUBJECT, done_test, page_for

QWIDGETSIZE_MAX = (1 << 24) - 1  # a widget with no maximum size set


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sessions"


def four_states(root):
    """One test in each state of H5: Not done, Done, Ended early 7/12, Data missing."""
    not_done = create_test(root, SUBJECT, "click_grid", name="A not done")
    done = done_test(root, "click_static", name="B done")
    early = done_test(root, "follow_moving", name="C early", planned=12, completed=7)
    missing = done_test(root, "scanning", name="D missing")
    return not_done, done, early, missing


def badges(page) -> dict[str, tuple[str, str]]:
    """Test name to the ``(kind, word)`` of its Status badge."""
    table = page.table
    out = {}
    for row in range(table.rowCount()):
        badge = table.badge_at(row)
        assert isinstance(badge, StatusBadge), row
        out[table.item(row, COL_NAME).text()] = (badge.kind(), badge.text())
    return out


# -- the state of a row ------------------------------------------------------------------------------


def test_the_badge_state_of_each_status(qapp, root):
    not_done, done, early, missing = four_states(root)
    page = page_for(root)
    tests = page._tests
    assert status_badge_state(tests[not_done.test_id]) == ("not_done", "Not done")
    assert status_badge_state(tests[done.test_id]) == ("done", "Done")
    assert status_badge_state(tests[early.test_id]) == ("ended_early", "Ended early 7/12")
    assert status_badge_state(tests[missing.test_id], True) == ("data_missing", "Data missing")
    assert status_badge_state(tests[early.test_id], True) == ("data_missing", "Data missing")
    assert tests[early.test_id].status == STATUS_ENDED_EARLY


def test_an_ended_early_record_without_counts_says_just_that(qapp, root):
    early = done_test(root, "follow_moving", planned=12, completed=7)
    test = page_for(root)._tests[early.test_id]
    assert status_badge_state(replace(test, completed_trials=None)) == ("ended_early", "Ended early")
    assert status_badge_state(replace(test, planned_trials=None)) == ("ended_early", "Ended early")


def test_every_status_cell_is_a_badge_with_glyph_and_word(qapp, root):
    four_states(root)
    run_folder_of(root, done_test_of(root, "D missing")).rmdir()
    page = page_for(root)
    assert badges(page) == {
        "A not done": ("not_done", "Not done"),
        "B done": ("done", "Done"),
        "C early": ("ended_early", "Ended early 7/12"),
        "D missing": ("data_missing", "Data missing"),
    }
    for row in range(page.table.rowCount()):
        badge = page.table.badge_at(row)
        assert badge.accessibleName() == badge.text() and badge.objectName() == "wtmhStatusBadge"


def done_test_of(root, name):
    return next(t for t in list_tests(root, SUBJECT).tests if t.name == name)


def test_the_items_keep_their_text_and_the_badge_hides_it(qapp, root):
    four_states(root)
    page = page_for(root)
    assert [row[COL_STATUS] for row in page.row_texts()] == [
        "Not Done", "Done", "Ended early (7/12)", "Done",
    ]
    assert page.table.itemDelegateForColumn(COL_STATUS) is not page.table.itemDelegateForColumn(COL_NAME)


def test_the_badge_tooltip_is_the_full_status_without_an_interpunct(qapp, root):
    four_states(root)
    run_folder_of(root, done_test_of(root, "D missing")).rmdir()
    page = page_for(root)
    tips = {name: page.table.badge_at(row).toolTip() for row, name in enumerate(names_of(page))}
    assert tips == {
        "A not done": "Not Done",
        "B done": "Done",
        "C early": "Ended early (7/12)",
        "D missing": "Done, data missing",
    }
    assert not any("·" in tip for tip in tips.values())


def names_of(page):
    return [row[COL_NAME] for row in page.row_texts()]


def test_bold_marks_nothing(qapp, root):
    four_states(root)
    page = page_for(root)
    for row in range(page.table.rowCount()):
        assert {page.table.item(row, c).font().bold() for c in range(5)} == {False}


def test_a_badge_is_centred_in_its_row_and_a_click_on_it_selects_the_row(qapp, root):
    four_states(root)
    page = page_for(root)
    page.resize(1400, 700)
    page.show()
    QApplication.processEvents()
    table = page.table
    for row in range(table.rowCount()):
        badge = table.badge_at(row)
        cell = table.visualRect(table.model().index(row, COL_STATUS))
        centre = badge.mapTo(table.viewport(), QPoint(0, badge.height() // 2)).y()
        assert abs(centre - cell.center().y()) <= 1, row
        assert badge.mapTo(table.viewport(), QPoint(0, 0)).x() >= cell.left()  # indented, inside the cell
    assert badge.parentWidget().testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    page.close()


def test_reloading_with_fewer_tests_leaves_no_stray_badges(qapp, root):
    not_done, done, early, missing = four_states(root)
    page = page_for(root)
    assert len(page.table.findChildren(StatusBadge)) == 4
    delete_test(root, SUBJECT, early.test_id)
    delete_test(root, SUBJECT, missing.test_id)
    page.reload()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert page.table.rowCount() == 2
    assert len(page.table.findChildren(StatusBadge)) == 2
    assert set(badges(page)) == {"A not done", "B done"}


# -- sorting still works ------------------------------------------------------------------------------------


def test_sorting_by_status_keeps_working_and_the_badges_follow_their_rows(qapp, root):
    four_states(root)
    page = page_for(root)
    page.resize(1400, 700)
    page.show()
    QApplication.processEvents()
    expected = {name: pair for name, pair in badges(page).items()}
    page.table.horizontalHeader().sectionClicked.emit(COL_STATUS)
    QApplication.processEvents()
    texts = [row[COL_STATUS] for row in page.row_texts()]
    assert texts == sorted(texts, key=str.casefold)  # the sort key is the status text, as before
    assert badges(page) == expected  # every name still has its own badge
    # and each badge sits at its own row
    table = page.table
    for row in range(table.rowCount()):
        cell = table.visualRect(table.model().index(row, COL_STATUS))
        centre = table.badge_at(row).mapTo(table.viewport(), QPoint(0, 12)).y()
        assert cell.top() <= centre <= cell.bottom()
    page.table.horizontalHeader().sectionClicked.emit(COL_STATUS)  # again: reversed
    QApplication.processEvents()
    texts = [row[COL_STATUS] for row in page.row_texts()]
    assert texts == sorted(texts, key=str.casefold, reverse=True)
    assert badges(page) == expected
    page.close()


def test_the_selection_and_a_reload_keep_the_badges(qapp, root):
    not_done, *_ = four_states(root)
    page = page_for(root)
    page.select_test(not_done.test_id)
    page.reload()
    assert page.selected_test().test_id == not_done.test_id
    assert badges(page)["A not done"] == ("not_done", "Not done")


# -- widths and placement (H5, Q1: the values are set in code) ---------------------------------------------


def test_the_other_columns_keep_the_widths_of_h5_and_test_name_stretches(qapp, root):
    four_states(root)
    page = page_for(root)
    header = page.table.horizontalHeader()
    assert OTHER_COLUMN_WIDTHS == (180, 200, 180, 140)  # Task, Configuration, Status, Date
    assert [header.sectionSize(c) for c in range(1, 5)] == [180, 200, 180, 140]
    assert [header.sectionResizeMode(c).name for c in range(5)] == ["Stretch"] + ["Fixed"] * 4
    assert page.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


@pytest.mark.parametrize("width", [1920, 1366])
def test_the_table_has_no_maximum_width_and_fills_the_window(qapp, root, width):
    four_states(root)
    page = page_for(root)
    assert page.table.maximumWidth() == QWIDGETSIZE_MAX  # no TABLE_MAX_WIDTH any more
    page.resize(width, 700)
    page.show()
    QApplication.processEvents()
    buttons_left = page.add_button.mapTo(page, QPoint(0, 0)).x()
    table_left = page.table.mapTo(page, QPoint(0, 0)).x()
    assert table_left == 32
    assert table_left + page.table.width() + 24 == buttons_left  # the table runs up to the button column
    header = page.table.horizontalHeader()
    # the other four columns keep their widths, Test Name takes the rest of the viewport
    assert [header.sectionSize(c) for c in range(1, 5)] == [180, 200, 180, 140]
    assert header.sectionSize(COL_NAME) == page.table.viewport().width() - sum(OTHER_COLUMN_WIDTHS)
    assert header.sectionSize(COL_NAME) > 420 or width < 1500  # wider than before at 1920
    page.close()


def test_a_wider_window_widens_only_the_test_name_column(qapp, root):
    four_states(root)
    page = page_for(root)
    sizes = {}
    for width in (1366, 1920):
        page.resize(width, 700)
        page.show()
        QApplication.processEvents()
        header = page.table.horizontalHeader()
        sizes[width] = [header.sectionSize(c) for c in range(5)]
    assert sizes[1920][1:] == sizes[1366][1:] == [180, 200, 180, 140]
    assert sizes[1920][COL_NAME] - sizes[1366][COL_NAME] == 1920 - 1366
    assert sizes[1366][COL_NAME] >= NAME_MIN_WIDTH
    page.close()


def test_many_rows_leave_the_four_fixed_columns_whole_and_test_name_gives_up_the_scroll_bar(qapp, root):
    for n in range(40):
        create_test(root, SUBJECT, "click_grid", name=f"Grid Click {n + 1}")
    page = page_for(root)
    page.resize(1500, 500)
    page.show()
    for _ in range(4):
        QApplication.processEvents()
    assert page.table.verticalScrollBar().maximum() > 0  # the list scrolls
    header = page.table.horizontalHeader()
    assert [header.sectionSize(c) for c in range(1, 5)] == [180, 200, 180, 140]  # no column is cut
    assert sum(header.sectionSize(c) for c in range(5)) == page.table.viewport().width()  # and no sideways scroll
    assert page.table.horizontalScrollBar().maximum() == 0
    page.close()


def test_the_button_column_is_24_px_right_of_the_table_at_the_windows_right_side_and_top_aligned(qapp, root):
    four_states(root)
    page = page_for(root)
    page.resize(1600, 700)
    page.show()
    QApplication.processEvents()
    table_left = page.table.mapTo(page, QPoint(0, 0))
    gap = page.add_button.mapTo(page, QPoint(0, 0)).x() - (table_left.x() + page.table.width())
    assert gap == 24
    assert page.add_button.mapTo(page, QPoint(0, 0)).y() == table_left.y()  # top-aligned
    # the column is the right side of the page: its widest button ends at the right gutter
    right = max(
        b.mapTo(page, QPoint(b.width(), 0)).x()
        for b in (page.add_button, page.configure_button, page.run_button, page.report_button,
                  page.copy_button, page.delete_button, page.open_folder_button)
    )
    assert right == page.width() - 32
    page.close()


def test_the_empty_state_is_one_line_inside_a_frame_that_follows_the_tables_width(qapp, root):
    page = page_for(root)  # a subject with no tests
    assert page.center.currentIndex() == 1
    frame = page.empty_label.parentWidget()
    assert isinstance(frame, QFrame) and frame.objectName() == "wtmhEmptyTable"
    assert frame.maximumWidth() == QWIDGETSIZE_MAX  # no fixed width
    for width in (1920, 1366):
        page.resize(width, 700)
        page.show()
        QApplication.processEvents()
        # the frame takes the room the table takes: from the left gutter up to 24 px before the buttons
        assert frame.width() == page.center.width()
        assert frame.width() == page.add_button.mapTo(page, QPoint(0, 0)).x() - 24 - 32
    assert page.empty_label.text() == "No tests yet. Choose Add New Test."


# -- the button tiers (V2, Q4) ---------------------------------------------------------------------------------


def test_run_test_is_the_only_primary_button_and_the_others_are_secondary(qapp, root):
    four_states(root)
    page = page_for(root)
    side = [
        page.add_button, page.configure_button, page.run_button, page.report_button,
        page.copy_button, page.delete_button, page.open_folder_button,
    ]
    assert [b.objectName() for b in side if b.objectName() == "wtmhPrimary"] == ["wtmhPrimary"]
    assert page.run_button.objectName() == "wtmhPrimary"
    assert {b.objectName() for b in side if b is not page.run_button} == {"wtmhGhost"}  # secondary
    primaries = [b for b in page.findChildren(QPushButton) if b.objectName() == "wtmhPrimary"]
    assert primaries == [page.run_button]


def test_delete_test_is_secondary_with_the_red_danger_glyph(qapp, root):
    four_states(root)
    page = page_for(root)
    button = page.delete_button
    assert button.text() == "Delete Test" and button.objectName() == "wtmhGhost"
    assert not button.icon().isNull() and isinstance(button.icon(), QIcon)
    on = button.icon().pixmap(12, 12, QIcon.Mode.Normal).toImage()
    off = button.icon().pixmap(12, 12, QIcon.Mode.Disabled).toImage()
    assert on.pixelColor(6, 6).name().lower() == "#da1e28"  # the danger token
    assert off.pixelColor(6, 6).name().lower() != "#da1e28"  # greyed with the button


def test_back_to_setup_is_a_tertiary_button_without_an_arrow(qapp, root):
    page = page_for(root)
    assert page.back_button.text() == "Back to Setup"
    assert page.back_button.objectName() == "wtmhTertiary"
