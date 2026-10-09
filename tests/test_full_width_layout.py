"""SPEC-design-system-phase2.md section 9, 2026-10-09 (user decisions after testing the try-all build,
empty space): Setup, Start, the Test List and the configuration page fill the window's width (no 1200 or 1500 px
column), Setup lays
its cards out in two independent columns (Subject over Display, Tracker over Calibration), and the configuration page's column C is titled "Gaze Pointer Settings".
Positions are compared relative to each other and to the page, never as a measured text width, so
they hold with the offscreen platform's fonts. Offscreen Qt."""

from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QWidget

from src.engine.calibration import CalibrationResult
from src.engine.config import load_task_config
from src.engine.display_check import check_display
from src.inputs.gazepoint_client import DeviceInfo
from src.ui import config_footer, config_form, page_layout
from src.ui.page_layout import CARD_GAP, PAGE_GUTTER, CardGrid, FlowLayout
from src.ui.setup_page import SetupPage
from src.ui.task_config_page import TaskConfigPage

QWIDGETSIZE_MAX = (1 << 24) - 1  # a widget with no maximum size set
WIDTHS = (1920, 1366)

PER_POINT = tuple(
    {
        "point": i,
        "target_x": 0.5,
        "target_y": 0.5,
        "left": {"x": 0.502, "y": 0.503, "valid": True},
        "right": {"x": 0.515, "y": 0.509, "valid": True},
    }
    for i in range(1, 6)
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def real_proportions(qapp):
    """The offscreen platform has no fonts and falls back to one about twice as wide as Segoe UI
    at 14 px (the display checkbox alone would be 756 px). A 7 px fallback has the proportions of
    the real one, so a half-width card can hold what it holds on screen."""
    old = qapp.font()
    font = QFont(old)
    font.setPixelSize(7)
    qapp.setFont(font)
    yield
    qapp.setFont(old)


def shown_setup(width: int, height: int = 1000, *, calibrated: bool = False, details: bool = False) -> SetupPage:
    page = SetupPage()
    page._client = SimpleNamespace(is_connected=lambda: True)
    page._apply_display_check(check_display(1920, 1080, 1.0))
    if calibrated:
        page._calibration_result = CalibrationResult(5, 12.0, True, per_point=PER_POINT)
        page._on_state_changed()
    page.resize(width, height)
    page.show()
    QApplication.processEvents()
    if details:
        page._on_toggle_details_clicked()
    for _ in range(3):
        QApplication.processEvents()
    return page


def rect_in(widget: QWidget, page: QWidget) -> QRect:
    return QRect(widget.mapTo(page, QPoint(0, 0)), widget.size())


# -- Setup: two columns of cards (section 9, 2026-10-09 (2); columns, not rows, after the live check) ---------------------------------------------------


def tracker_cell(page: SetupPage) -> QWidget:
    """The Tracker card with the rate-warning alert that sits under it."""
    return page.tracker_card.parentWidget()


def calibration_cell(page: SetupPage) -> QWidget:
    """The Calibration card with the calibration alert that sits under it."""
    return page.calibration_card.parentWidget()


@pytest.mark.parametrize("width", WIDTHS)
def test_two_cards_share_the_top_row_on_setup(qapp, width):
    page = shown_setup(width)
    subject, tracker = rect_in(page.subject_card, page), rect_in(page.tracker_card, page)
    assert subject.top() == tracker.top()  # both columns start at the same line, top-aligned
    assert subject.left() < tracker.left()  # Subject & Session Info | Tracker Connection
    display, calibration = rect_in(page.display_section, page), rect_in(page.calibration_card, page)
    assert display.left() == subject.left() and calibration.left() == tracker.left()
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_each_column_stacks_its_cards_without_waiting_for_the_other_column(qapp, width):
    """Subject over Display on the left, Tracker over Calibration on the right: a short card does
    not leave a hole for the tall one beside it (the live check of 2026-10-09)."""
    page = shown_setup(width)
    subject, display = rect_in(page.subject_card, page), rect_in(page.display_section, page)
    tracker, calibration = rect_in(tracker_cell(page), page), rect_in(calibration_cell(page), page)
    assert display.top() - subject.bottom() - 1 == CARD_GAP == 24  # straight under Subject
    assert calibration.top() - tracker.bottom() - 1 == CARD_GAP  # straight under Tracker
    assert calibration.top() < display.top()  # the right column is shorter above it, so it is higher
    assert tracker.height() < subject.height()
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_columns_are_of_equal_width_and_the_gap_is_the_same_across_and_down(qapp, width):
    page = shown_setup(width)
    scroll = page.findChild(QScrollArea, "wtmhSetupScroll")
    subject, tracker = rect_in(page.subject_card, page), rect_in(page.tracker_card, page)
    display, calibration = rect_in(page.display_section, page), rect_in(page.calibration_card, page)
    assert abs(subject.width() - tracker.width()) <= 1
    assert abs(display.width() - calibration.width()) <= 1
    assert subject.width() == display.width() and tracker.width() == calibration.width()
    # across: the gap between the two columns; down: the gap between two cards of a column
    assert tracker.left() - subject.right() - 1 == CARD_GAP == 24
    assert display.top() - subject.bottom() - 1 == CARD_GAP
    # together they span the cards' area, left edge at the gutter
    assert subject.left() == PAGE_GUTTER
    assert tracker.right() + 1 == PAGE_GUTTER + scroll.viewport().width()
    page.close()


def test_an_alert_stays_directly_under_its_card_and_moves_only_its_own_column(qapp):
    page = shown_setup(1920)
    display_top = rect_in(page.display_section, page).top()
    calibration_top = rect_in(page.calibration_card, page).top()
    page.rate_warning_label.setText("The tracker reports a rate below 150 Hz.")
    page.rate_warning_alert.setVisible(True)
    for _ in range(3):
        QApplication.processEvents()
    card, alert = rect_in(page.tracker_card, page), rect_in(page.rate_warning_alert, page)
    assert alert.top() - card.bottom() - 1 == 8  # directly under its card
    assert rect_in(page.calibration_card, page).top() > calibration_top  # Calibration moved down
    assert rect_in(page.display_section, page).top() == display_top  # the left column did not
    assert rect_in(page.calibration_card, page).top() - alert.bottom() - 1 == CARD_GAP
    page.close()


def test_the_tab_and_reading_order_is_subject_tracker_display_calibration(qapp):
    page = shown_setup(1920)
    chain, widget = [], page.subject_id_edit
    for _ in range(400):  # the focus chain, once round
        chain.append(widget)
        widget = widget.nextInFocusChain()
        if widget is page.subject_id_edit:
            break
    firsts = [
        chain.index(w)
        for w in (page.subject_id_edit, page.address_edit, page.display_ack_checkbox, page.point_count_spin)
    ]
    assert firsts == sorted(firsts)  # Subject, Tracker, Display, Calibration
    assert chain.index(page.notes_edit) < chain.index(page.address_edit)  # all of Subject before Tracker
    assert chain.index(page.connect_button) < chain.index(page.display_ack_checkbox)
    assert chain.index(page.display_ack_checkbox) < chain.index(page.do_calibration_button)
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_fields_keep_their_h4_widths_in_the_wider_cards(qapp, width):
    page = shown_setup(width)
    for field, expected in (
        (page.subject_id_edit, 320), (page.date_edit, 200), (page.sex_combo, 240),
        (page.address_edit, 320), (page.port_spin, 120), (page.point_count_spin, 100),
    ):
        assert field.width() == expected, type(field).__name__
    page.close()


def test_the_before_you_start_note_spans_both_columns_under_them(qapp):
    page = shown_setup(1920)
    scroll = page.findChild(QScrollArea, "wtmhSetupScroll")
    note = next(
        w for w in page.findChildren(QWidget)
        if w.layout() is not None and any(
            isinstance(lab, QLabel) and lab.text() == "Before You Start" for lab in w.findChildren(QLabel)
        ) and w.parentWidget() is scroll.widget()
    )
    assert note.width() == scroll.viewport().width()  # one row of its own, not a half-width cell
    below = max(rect_in(page.display_section, page).bottom(), rect_in(calibration_cell(page), page).bottom())
    assert rect_in(note, page).top() > below  # under both columns
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_setup_has_no_sideways_scroll_with_a_calibration_its_details_and_long_alerts(qapp, width):
    page = shown_setup(width, calibrated=True, details=True)
    info = DeviceInfo(model="Gazepoint GP3 HD", rate_hz=150, bus="USB 3", serial="123456789",
                      camera_width=640, camera_height=480, api_version="1.0")
    page._apply_device_info(info)
    page._set_calibration_alert("warning", "No calibration yet for this subject. " * 6)
    page.rate_warning_label.setText("The tracker reports a rate below 150 Hz. " * 6)
    page.rate_warning_alert.setVisible(True)
    for _ in range(3):
        QApplication.processEvents()
    scroll = page.findChild(QScrollArea, "wtmhSetupScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.widget().width() == scroll.viewport().width()  # the content never outgrew its area
    assert scroll.widget().minimumSizeHint().width() <= scroll.viewport().width()
    assert page.device_info_label.wordWrap() and page.calibration_alert_label.wordWrap()
    for card in (page.subject_card, page.tracker_card, page.calibration_card):
        assert rect_in(card, page).right() <= PAGE_GUTTER + scroll.viewport().width()
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_calibration_buttons_and_badge_stay_inside_their_card(qapp, width):
    page = shown_setup(width, calibrated=True)
    card = rect_in(page.calibration_card, page)
    for widget in (
        page.do_calibration_button, page.load_calibration_button, page.save_calibration_button,
        page.view_details_button, page.calibration_badge,
    ):
        box = rect_in(widget, page)
        assert card.left() < box.left() and box.right() < card.right(), widget.objectName() or type(widget).__name__
    page.close()


def test_the_calibration_buttons_wrap_onto_a_second_line_in_a_narrow_card(qapp):
    wide = shown_setup(1920)
    narrow = shown_setup(1150)
    wide_ys = {rect_in(b, wide).top() for b in (wide.do_calibration_button, wide.view_details_button)}
    narrow_ys = {rect_in(b, narrow).top() for b in (narrow.do_calibration_button, narrow.view_details_button)}
    assert len(wide_ys) == 1  # one row in a wide card
    assert len(narrow_ys) == 2  # wrapped in a narrow one
    card = rect_in(narrow.calibration_card, narrow)
    assert all(
        rect_in(b, narrow).right() < card.right()
        for b in (narrow.do_calibration_button, narrow.load_calibration_button, narrow.save_calibration_button,
                  narrow.view_details_button, narrow.calibration_badge)
    )
    assert narrow.findChild(QScrollArea, "wtmhSetupScroll").horizontalScrollBar().maximum() == 0
    wide.close()
    narrow.close()


def test_the_footer_has_no_cap_and_continue_is_at_the_right_edge(qapp):
    page = shown_setup(1920)
    footer = page.continue_button.parentWidget().parentWidget()
    assert footer.maximumWidth() == QWIDGETSIZE_MAX
    assert footer.width() == page.width() - 2 * PAGE_GUTTER
    assert rect_in(page.continue_button, page).right() + 1 == page.width() - PAGE_GUTTER
    page.close()


# -- the layout helpers --------------------------------------------------------------------------------------


def fixed_buttons(count: int, width: int = 100, height: int = 30) -> list[QPushButton]:
    buttons = []
    for i in range(count):
        button = QPushButton(f"b{i}")
        button.setFixedSize(width, height)
        buttons.append(button)
    return buttons


def test_a_flow_layout_wraps_when_the_width_runs_out_and_centres_each_line(qapp):
    host = QWidget()
    flow = FlowLayout(h_spacing=6, v_spacing=8)
    host.setLayout(flow)
    short = QPushButton("s")
    short.setFixedSize(100, 20)
    items = fixed_buttons(2) + [short]
    for item in items:
        flow.addWidget(item)
    assert flow.hasHeightForWidth()
    assert flow.heightForWidth(320) == 30  # 100 + 6 + 100 + 6 + 100 = 312 fits one line
    assert flow.heightForWidth(311) == 30 + 8 + 20  # the third wraps
    assert flow.minimumSize().width() == 100  # a narrow card is one button wide
    host.resize(250, 80)
    host.show()
    QApplication.processEvents()
    a, b, c = items
    assert (a.x(), b.x(), c.x()) == (0, 106, 0)
    assert a.y() == b.y() == 0 and c.y() == 38  # the second line starts at 30 + 8
    host.close()


def test_a_flow_layout_centres_a_short_item_on_its_line(qapp):
    host = QWidget()
    flow = FlowLayout()
    host.setLayout(flow)
    tall, short = fixed_buttons(1, height=40)[0], QPushButton("s")
    short.setFixedSize(60, 24)
    flow.addWidget(tall)
    flow.addWidget(short)
    host.resize(300, 60)
    host.show()
    QApplication.processEvents()
    assert tall.y() == 0 and short.y() == 8  # (40 - 24) / 2
    host.close()


def test_a_flow_layout_skips_hidden_widgets(qapp):
    host = QWidget()
    flow = FlowLayout()
    host.setLayout(flow)
    items = fixed_buttons(3)
    for item in items:
        flow.addWidget(item)
    host.resize(400, 60)
    host.show()
    items[1].hide()
    QApplication.processEvents()
    assert items[2].x() == items[0].x() + 100 + 6  # closes up over the hidden one
    host.close()


def test_a_card_grid_fills_two_columns_in_turn_and_puts_a_wide_one_under_both(qapp):
    host = QWidget()
    grid = CardGrid(host)
    heights = (80, 30, 40, 20, 50)
    cells = [QLabel(str(i)) for i in range(5)]
    for cell, height in zip(cells, heights, strict=True):
        cell.setFixedHeight(height)
    for cell in cells[:3]:
        grid.add_card(cell)  # left, right, left
    grid.add_wide(cells[3])
    grid.add_card(cells[4])  # a card after the wide one starts a new pair of columns
    grid.finish()
    host.resize(600, 400)
    host.show()
    QApplication.processEvents()
    first, second, third, wide, last = (rect_in(c, host) for c in cells)
    assert first.top() == second.top() == 0  # both columns start at the top
    assert first.left() == 0 and second.left() > first.left() and third.left() == first.left()
    assert abs(first.width() - second.width()) <= 1
    assert second.left() - first.right() - 1 == CARD_GAP
    assert third.top() - first.bottom() - 1 == CARD_GAP  # under the first, not level with the second
    assert wide.left() == 0 and wide.width() == 600 and wide.top() > third.bottom() and wide.top() > second.bottom()
    assert last.left() == 0 and last.top() > wide.bottom()
    assert page_layout.CARD_COLUMNS == 2
    host.close()


def test_a_card_grids_cards_are_reparented_in_the_order_they_are_added(qapp):
    host = QWidget()
    grid = CardGrid(host)
    cells = [QPushButton(str(i)) for i in range(4)]
    for cell in cells:
        grid.add_card(cell)
    host.show()
    chain, widget = [], cells[0]
    for _ in range(20):
        chain.append(widget)
        widget = widget.nextInFocusChain()
        if widget is cells[0]:
            break
    assert [chain.index(c) for c in cells] == sorted(chain.index(c) for c in cells)
    host.close()


def test_page_layout_has_no_width_cap_left():
    assert not hasattr(page_layout, "CONTENT_MAX_WIDTH")
    assert not hasattr(page_layout, "SCROLLBAR_GUTTER")
    assert not hasattr(page_layout, "content_column")


# -- the configuration page's column C title (section 9, 2026-10-09 (3)) --------------------------------------


@pytest.mark.parametrize("task_id", ["click_static", "click_grid", "follow_moving", "scanning"])
def test_the_configuration_page_titles_column_c_gaze_pointer_settings(qapp, task_id):
    page = TaskConfigPage(task_id, load_task_config(task_id))
    titles = [lab for lab in page.findChildren(QLabel) if lab.objectName() == "cfgAdvancedTitle"]
    assert [lab.text() for lab in titles] == ["Gaze Pointer Settings"]
    assert not any(lab.text() == "Advanced" for lab in page.findChildren(QLabel))
    # only the text changed: the object name, the cards under it and their order are as they were
    assert titles[0].objectName() == "cfgAdvancedTitle"


# -- the configuration page fills the window too (section 9, 2026-10-09, relayed by the hub) ---------------------


TASKS = ("click_static", "click_grid", "follow_moving", "scanning")


def shown_config(task_id: str, width: int, height: int = 1000) -> TaskConfigPage:
    page = TaskConfigPage(task_id, load_task_config(task_id))
    page.set_context(subject_id="TESTING", existing_test_names=[])
    page.load_values(test_name="Test 1")
    page.resize(width, height)
    page.show()
    for _ in range(3):
        QApplication.processEvents()
    return page


def test_the_configuration_page_has_no_width_cap_left(qapp):
    assert not hasattr(config_form, "CONTENT_MAX_WIDTH")
    page = shown_config("click_grid", 1920)
    assert page.scroll_area.widget().maximumWidth() == QWIDGETSIZE_MAX
    assert page.findChild(QWidget, "cfgFooter").maximumWidth() == QWIDGETSIZE_MAX
    assert list(inspect.signature(config_footer.centered_footer).parameters) == ["buttons", "message"]
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("task_id", TASKS)
def test_the_three_columns_share_the_window_width_equally(qapp, task_id, width):
    page = shown_config(task_id, width)
    scroll = page.scroll_area
    assert scroll.x() == PAGE_GUTTER and scroll.width() == page.width() - 2 * PAGE_GUTTER
    assert scroll.widget().width() == scroll.viewport().width()  # the columns use the whole viewport
    assert scroll.horizontalScrollBar().maximum() == 0
    lefts = sorted({rect_in(card, page).left() for card in page.cards.values()})
    assert len(lefts) == 3 and lefts[0] == PAGE_GUTTER  # three columns, the first at the gutter
    widths = {rect_in(card, page).width() for card in page.cards.values()}
    assert max(widths) - min(widths) <= 1  # equal
    last = max(rect_in(card, page).right() for card in page.cards.values())
    assert last + 1 == PAGE_GUTTER + scroll.viewport().width()  # and they reach the right gutter
    page.close()


@pytest.mark.parametrize("task_id", TASKS)
def test_wider_cards_are_not_taller(qapp, task_id):
    """The round-4 rule (column A fits a maximized 1920x1080 window without a scroll bar) holds
    because cards do not grow taller when they get wider."""
    narrow = shown_config(task_id, 1500)  # about the old 1500 px cap
    wide = shown_config(task_id, 1920)
    for card_id, card in narrow.cards.items():
        assert wide.cards[card_id].height() <= card.height(), card_id
    narrow.close()
    wide.close()


def test_the_footer_stays_centred_under_the_columns_when_the_page_is_wide(qapp):
    page = shown_config("click_grid", 1920)
    footer = page.findChild(QWidget, "cfgFooter")
    left = page.preview_button.mapTo(footer, QPoint(0, 0)).x()
    right = page.cancel_button.mapTo(footer, QPoint(page.cancel_button.width(), 0)).x()
    assert footer.width() == page.scroll_area.width()
    assert abs((left + right) / 2 - footer.width() / 2) <= 2
    page.close()
