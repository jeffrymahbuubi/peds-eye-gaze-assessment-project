"""The report's maps fill their column (SPEC-design-system-phase4.md section 9, the user's decision of
2026-10-09 after testing the try-all build: "empty space"): on the Summary and the Detailed tab the
Target Map is as wide as its column, at the canvas's aspect, never taller than the pane shows, never
below 720 x 405 px, and follows the window. The PDF's map and every mark are unchanged by it.

Every claim is a relation between sizes the widgets report (the map, the column, the pane's viewport,
the heading above the map), so none depends on the font and the module registers no font and sets no
application style: a font registered here would stay in Qt's font cache and change the text metrics
of tests that run later (the Setup page's width test). The on-screen look is the live check's.
"""

from __future__ import annotations

import gc
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.data.report_cache import build_report
from src.ui.report_page import ReportPage
from src.ui.report_views import CONTENT_RIGHT_MARGIN
from src.ui.target_map import MAP_MIN_SIZE, MARGIN, TargetMapWidget
from src.ui.wtmh_theme import STYLESHEET
from tests.follow_fixtures import folder as follow_folder
from tests.report_ui_fixtures import folder_report, synthetic_map_report

SIXTEEN_NINE = 16 / 9


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _release_the_windows(qapp):
    """Free this test's windows now and not at some later garbage collection, in the middle of another
    module's test (a window destroyed there can take a style sheet's cached rules with it)."""
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    QCoreApplication.processEvents()


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


def close_window(root: QWidget) -> None:
    root.close()
    root.deleteLater()


def sixteen_nine_report(tmp_path):
    report = folder_report(tmp_path)
    report["map"]["aspect"] = report["geometry"]["canvas_aspect"] = SIXTEEN_NINE
    return report


def canvas_ratio(size: QSize) -> float:
    """Width over height of the canvas inside a map widget of ``size`` (the margin taken off)."""
    return (size.width() - 2 * MARGIN) / (size.height() - 2 * MARGIN)


def column_width(view) -> int:
    """The room the view's content has: its width less a scroll bar and the layout's right margin."""
    return view.width() - view.verticalScrollBar().sizeHint().width() - CONTENT_RIGHT_MARGIN


# -- the size rule, on a bare map widget -------------------------------------------------------------------


def test_a_map_widens_with_the_room_it_is_given_and_keeps_16_9(qapp):
    widget = TargetMapWidget()  # no report: the default canvas, 16:9
    assert widget.aspect == pytest.approx(SIXTEEN_NINE)
    widths = []
    for room in (800, 1000, 1200, 1500, 1800):
        size = widget.fill_size(room, 5000)  # a pane that is tall enough: the width decides
        assert size.width() == room
        assert canvas_ratio(size) == pytest.approx(SIXTEEN_NINE, rel=0.005)
        widths.append(size.width())
    assert widths == sorted(widths) and len(set(widths)) == len(widths)


def test_a_map_never_gets_taller_than_the_height_it_is_given(qapp):
    widget = TargetMapWidget()
    for room in (450, 500, 600, 740, 900):
        size = widget.fill_size(5000, room)  # a column that is wide enough: the height decides
        assert room - 1 <= size.height() <= room  # it uses the room
        assert canvas_ratio(size) == pytest.approx(SIXTEEN_NINE, rel=0.005)


def test_a_map_in_a_room_smaller_than_the_minimum_gets_the_minimum(qapp):
    widget = TargetMapWidget()
    assert MAP_MIN_SIZE == (720, 405)
    for room in ((300, 200), (719, 404), (720, 300), (400, 2000), (0, 0), (-5, -5)):
        size = widget.fill_size(*room)
        assert size.width() >= 720 and size.height() >= 405, room
        assert canvas_ratio(size) == pytest.approx(SIXTEEN_NINE, rel=0.005), room
    assert widget.fill_size(100, 100) == QSize(720, widget.heightForWidth(720))  # 720 x 407, 405 less its margin rounding


def test_a_canvas_wider_than_16_9_keeps_its_aspect_and_its_minimum_height(qapp):
    report = synthetic_map_report()
    report["map"]["aspect"] = 2.2
    widget = TargetMapWidget()
    widget.set_report(report)
    size = widget.fill_size(100, 100)
    assert size.height() == 405 and size.width() > 720  # the height is what the minimum asks for
    assert canvas_ratio(size) == pytest.approx(2.2, rel=0.01)
    big = widget.fill_size(1800, 5000)
    assert big.width() == 1800 and canvas_ratio(big) == pytest.approx(2.2, rel=0.01)


def test_fit_within_gives_the_widget_that_fixed_size(qapp):
    widget = TargetMapWidget()
    widget.fit_within(1000, 5000)
    assert widget.size() == widget.minimumSize() == widget.maximumSize() == widget.fill_size(1000, 5000)
    widget.fit_within(1200, 5000)  # and again: it follows the room, up and down
    assert widget.width() == 1200
    widget.fit_within(900, 5000)
    assert widget.width() == 900


# -- on the report page ------------------------------------------------------------------------------------


@pytest.mark.parametrize("view", ["summary", "detailed"])
def test_the_map_widens_with_the_column_when_the_pane_is_tall_enough(qapp, tmp_path, view):
    report = folder_report(tmp_path)
    widths = []
    for window in (1500, 1700, 1920, 2200):
        root, page = themed_page(report, width=window, height=1700, view=view)  # tall: the width decides
        try:
            shown = getattr(page, view)
            assert shown.map.width() == column_width(shown), window  # it fills its column ...
            assert shown.map.x() == 0  # ... from its left edge
            assert canvas_ratio(shown.map.size()) == pytest.approx(shown.map.aspect, rel=0.005)
            widths.append(shown.map.width())
        finally:
            close_window(root)
    # the map grows by exactly what the window grows by (the sidebar and the margins stay as they are)
    assert [b - a for a, b in zip(widths, widths[1:], strict=False)] == [200, 220, 280]


@pytest.mark.parametrize("view", ["summary", "detailed"])
def test_the_map_keeps_exact_16_9_when_the_canvas_is_16_9(qapp, tmp_path, view):
    root, page = themed_page(sixteen_nine_report(tmp_path), width=1920, height=1700, view=view)
    try:
        shown = getattr(page, view).map
        assert shown.aspect == pytest.approx(SIXTEEN_NINE)
        assert canvas_ratio(shown.size()) == pytest.approx(SIXTEEN_NINE, rel=0.003)
        assert shown.canvas_rect().width() / shown.canvas_rect().height() == pytest.approx(SIXTEEN_NINE, rel=1e-3)
    finally:
        close_window(root)


@pytest.mark.parametrize("height", [1000, 1080])
def test_the_detailed_map_and_its_heading_are_in_view_without_scrolling(qapp, tmp_path, height):
    """The cap: the pane (a maximized 1080p window) shows the heading and the whole map at once."""
    root, page = themed_page(folder_report(tmp_path), height=height, view="detailed")
    try:
        view = page.detailed
        viewport = view.viewport().height()
        assert view.verticalScrollBar().value() == 0
        assert view.selected_title.y() >= 0
        bottom = view.map.y() + view.map.height()
        assert viewport - 2 <= bottom <= viewport  # as tall as the pane allows, and no taller
        assert view.map.width() < column_width(view)  # it is the height that held it back
    finally:
        close_window(root)


@pytest.mark.parametrize("height", [1000, 1080])
def test_the_summary_map_with_its_heading_and_switches_fits_the_pane(qapp, tmp_path, height):
    root, page = themed_page(folder_report(tmp_path), height=height)
    try:
        view = page.summary
        bar = view.verticalScrollBar()
        bar.setValue(min(view.map_title.y(), bar.maximum()))  # scrolled to the "Target Map" heading
        QCoreApplication.processEvents()
        top = bar.value()
        viewport = view.viewport().height()
        assert view.map_title.y() - top >= 0 and view.targets_check.y() - top >= 0  # the switches are in view
        bottom = view.map.y() + view.map.height() - top
        assert viewport - 2 <= bottom <= viewport  # the whole map is in view, filling the pane
        assert view.map.width() < column_width(view)
        assert view.map.width() > 880  # the old cap of the Summary's map
    finally:
        close_window(root)


@pytest.mark.parametrize("view", ["summary", "detailed"])
def test_the_map_keeps_the_minimum_when_the_window_is_small(qapp, tmp_path, view):
    root, page = themed_page(folder_report(tmp_path), width=1280, height=700, view=view)
    try:
        shown = getattr(page, view).map
        assert shown.width() >= MAP_MIN_SIZE[0] and shown.height() >= MAP_MIN_SIZE[1]
        assert shown.width() == 720  # the pane there is too small to ask for more
    finally:
        close_window(root)


@pytest.mark.parametrize("view", ["summary", "detailed"])
def test_the_map_follows_the_window_when_it_is_resized(qapp, tmp_path, view):
    root, page = themed_page(folder_report(tmp_path), width=1920, height=1000, view=view)
    try:
        shown = getattr(page, view).map
        first = shown.size()
        root.resize(1500, 900)
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        smaller = shown.size()
        assert smaller.width() < first.width() and smaller.height() < first.height()
        root.resize(1920, 1000)
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        assert shown.size() == first  # and back
    finally:
        close_window(root)


def test_a_second_report_with_another_aspect_resizes_the_map(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path), width=1920, height=1000)
    try:
        before = page.summary.map.size()
        page.set_report(sixteen_nine_report(tmp_path), test_name="Grid Click 1")
        QCoreApplication.processEvents()
        after = page.summary.map.size()
        assert canvas_ratio(after) == pytest.approx(SIXTEEN_NINE, rel=0.005)
        assert after != before  # 16:9 is wider than the first canvas, so the same height gives more width
        assert after.width() > before.width() or after.height() < before.height()
    finally:
        close_window(root)


def test_the_legends_are_as_wide_as_the_map_above_them(qapp, tmp_path):
    root, page = themed_page(folder_report(tmp_path), width=1920, height=1000)
    try:
        assert page.summary.legend.width() == page.summary.map.width() > 880
        root.resize(1500, 900)
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        assert page.summary.legend.width() == page.summary.map.width()
    finally:
        close_window(root)
    root, page = themed_page(build_report(follow_folder(tmp_path)), view="detailed")
    try:
        view = page.detailed
        assert not view.legend.isHidden()  # Follow the Target's pointer legend
        assert view.legend.width() == view.map.width()
    finally:
        close_window(root)


# -- nothing else moves ----------------------------------------------------------------------------------


def pixel(image: QImage, rect, x: float, y: float, dx: float = 0.0) -> QColor:
    """The pixel at canvas-normalized (x, y), nudged by dx px."""
    return image.pixelColor(round(rect.left() + x * rect.width() + dx), round(rect.top() + y * rect.height()))


@pytest.mark.parametrize("room", [(720, 407), (1100, 640), (1500, 870)])
def test_the_marks_sit_at_their_canvas_positions_at_any_map_size(qapp, room):
    """The map has no mouse handling; what it draws maps recorded canvas-normalized positions through
    :meth:`canvas_rect`, so a hit and a miss are at the same fraction of the canvas at every size."""
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    widget.fit_within(*room)
    image = widget.grab().toImage()
    rect = widget.canvas_rect()
    assert rect.width() / rect.height() == pytest.approx(widget.aspect, rel=1e-3)
    assert rect.width() == pytest.approx(widget.width() - 2 * MARGIN, abs=1.5) or rect.height() == pytest.approx(
        widget.height() - 2 * MARGIN, abs=1.5
    )  # the canvas fills the map: no bars left or right
    r_px = 0.05 * rect.width()  # both fixture targets have the radius 0.05 of the canvas width
    hit_in = pixel(image, rect, 0.65, 0.5, 0.6 * r_px)
    assert hit_in.green() > hit_in.red() + 30 and hit_in.green() > hit_in.blue() + 10  # the hit's green fill
    hit_out = pixel(image, rect, 0.65, 0.5, 1.8 * r_px)
    assert not (hit_out.green() > hit_out.red() + 30)  # and nothing green outside its circle
    ring = [pixel(image, rect, 0.3, 0.7, r_px + d) for d in range(-2, 3)]  # the miss's red ring, wherever the pen falls
    assert any(c.red() > c.green() + 60 and c.red() > c.blue() + 60 for c in ring)


def test_the_pdf_map_does_not_depend_on_the_size_the_map_has_on_screen(qapp):
    """``ReportPage.export_pdf`` renders the Summary map with ``render_to_image`` at the PDF's own
    size; the image is the same whatever size the widget has been given."""
    small, large = TargetMapWidget(), TargetMapWidget()
    for widget in (small, large):
        widget.set_report(synthetic_map_report())
    small.fit_within(100, 100)
    large.fit_within(2000, 2000)
    assert small.size() != large.size()
    size = QSize(1800, round(1800 / small.aspect))
    overlays = {"targets": True, "path": True}
    assert small.render_to_image(size, overlays) == large.render_to_image(size, overlays)
