"""SPEC-compass-task-flow.md 7.1, V1: the Target Map's symbol legend box (on the page and in
the PDF). Offscreen Qt; pixels are checked by colour class, never by size (no fonts offscreen)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.ui.map_legend import (
    ICON_PX,
    LEGEND_ENTRIES,
    NUMBERS_NOTE,
    LegendIcon,
    MapLegend,
    legend_html,
    symbol_image,
)
from src.ui.report_views import MAP_MAX_WIDTH, SummaryView
from src.ui.target_map import TargetMapWidget
from src.ui.target_map_paint import LEGEND_KINDS, paint_symbol
from src.ui.wtmh_theme import INK, SOFT_ACCENT, STYLESHEET
from tests.report_ui_fixtures import folder_report, synthetic_map_report


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def themed(widget: QWidget) -> QWidget:
    """``widget`` in a host that carries the dashboard's style sheet, as on the page."""
    host = QWidget()
    host.setObjectName("wtmhDashboard")
    host.setStyleSheet(STYLESHEET)
    QVBoxLayout(host).addWidget(widget)
    host.resize(760, 160)
    host.show()
    QApplication.processEvents()
    return host


def greenish(c: QColor) -> bool:
    return c.green() > c.red() + 30 and c.green() > c.blue() + 10


def reddish(c: QColor) -> bool:
    return c.red() > c.green() + 60 and c.red() > c.blue() + 60


def ink(image: QImage) -> list[tuple[int, int]]:
    return [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y).alpha() > 0]


# -- the entries ---------------------------------------------------------------------------------


def test_the_legend_has_exactly_the_four_marks_of_the_map(qapp):
    legend = MapLegend()
    assert [kind for kind, _ in legend.entries()] == ["hit", "timeout", "skipped", "slot"]
    assert tuple(kind for kind, _ in LEGEND_ENTRIES) == LEGEND_KINDS
    assert len(legend.icons) == len(legend.labels) == 4
    assert all(isinstance(icon, LegendIcon) for icon in legend.icons)


def test_each_entry_has_a_short_label_and_the_numbers_note_follows(qapp):
    legend = MapLegend()
    labels = [text for _, text in legend.entries()]
    assert all(labels) and len(set(labels)) == 4
    assert all(len(text) <= 40 for text in labels)  # short
    assert legend.numbers_label.text() == NUMBERS_NOTE == "Numbers = trials shown at that place"


def test_the_legend_sits_in_the_summary_under_the_map_and_replaces_the_grey_line(qapp, tmp_path):
    view = SummaryView()
    view.set_report(folder_report(tmp_path))
    assert isinstance(view.legend, MapLegend)
    layout = view.widget().layout()
    assert layout.indexOf(view.legend) == layout.indexOf(view.map) + 1  # directly under the map
    assert view.legend.maximumWidth() == MAP_MAX_WIDTH == view.map.maximumWidth()  # as wide as the map
    texts = " ".join(label.text() for label in view.findChildren(QLabel))
    assert "Green circle = hit" not in texts  # the old small grey line is gone


def test_the_legend_does_not_depend_on_the_overlay_switches(qapp, tmp_path):
    view = SummaryView()
    view.set_report(folder_report(tmp_path))
    for check in (view.targets_check, view.path_check, view.heat_check):
        check.setChecked(not check.isChecked())
    assert len(view.legend.entries()) == 4


# -- how it looks: a light tinted box, body size, dark text ---------------------------------------------


def test_the_box_is_a_light_tinted_frame_with_dark_body_text(qapp):
    legend = MapLegend()
    host = themed(legend)
    try:
        assert legend.objectName() == "mapLegend"
        assert SOFT_ACCENT.lower() in legend.styleSheet().lower()  # the light tint
        grabbed = legend.grab().toImage()
        corner = grabbed.pixelColor(grabbed.width() // 2, 4)  # the box's own background
        assert corner.name().lower() == SOFT_ACCENT.lower()
        for label in legend.labels + [legend.numbers_label]:
            assert label.palette().color(label.foregroundRole()).name().lower() == INK.lower()
            assert label.font().pointSizeF() == pytest.approx(legend.font().pointSizeF())  # body text size
            assert "font-size" not in label.styleSheet()
        assert "font-size" not in legend.styleSheet()
    finally:
        host.close()


def test_the_text_is_not_the_muted_grey_of_the_old_line(qapp):
    legend = MapLegend()
    host = themed(legend)
    try:
        for label in legend.labels + [legend.numbers_label]:
            assert label.objectName() != "wtmhMuted"
    finally:
        host.close()


# -- the icons are the map's own marks ----------------------------------------------------------------------


def test_each_icon_paints_its_mark(qapp):
    hit = symbol_image("hit", 96)
    centre = hit.pixelColor(48, 48)
    assert greenish(centre) and centre.alpha() > 0  # a filled green circle
    miss = symbol_image("timeout", 96)
    diagonal = [miss.pixelColor(48 + d, 48 + d) for d in range(-20, 21, 5)]
    assert any(reddish(c) and c.alpha() > 100 for c in diagonal)  # the red X's arm
    assert miss.pixelColor(48 + 15, 48).alpha() < 30  # between the arms: hollow
    skipped = symbol_image("skipped", 96)
    assert skipped.pixelColor(48, 48).alpha() == 0  # a ring, hollow inside
    assert any(skipped.pixelColor(x, 48).alpha() > 0 for x in range(0, 30))  # with a stroke
    assert not any(reddish(c) or greenish(c) for c in (skipped.pixelColor(x, 48) for x in range(96)))
    slot = symbol_image("slot", 96)
    assert slot.pixelColor(48, 48).alpha() == 0
    assert any(slot.pixelColor(x, 48).alpha() > 0 for x in range(0, 30))


def test_the_four_icons_are_four_different_pictures(qapp):
    images = [symbol_image(kind, 64) for kind in LEGEND_KINDS]
    assert len({bytes(image.constBits()) for image in images}) == 4


def test_an_icon_stays_inside_its_square_and_scales(qapp):
    for kind in LEGEND_KINDS:
        small = ink(symbol_image(kind, 40))
        assert small, kind
        xs, ys = [p[0] for p in small], [p[1] for p in small]
        assert min(xs) >= 0 and max(xs) <= 39 and min(ys) >= 0 and max(ys) <= 39
        big = ink(symbol_image(kind, 160))
        assert max(p[0] for p in big) - min(p[0] for p in big) > 2.5 * (max(xs) - min(xs))


def test_the_icon_widget_paints_with_the_same_code(qapp):
    icon = LegendIcon("hit")
    assert (icon.width(), icon.height()) == (ICON_PX, ICON_PX)
    grabbed = icon.grab().toImage()
    reference = QImage(ICON_PX, ICON_PX, grabbed.format())
    reference.fill(QColor("#F0F0F0"))
    painter = QPainter(reference)
    paint_symbol(painter, QRectF(0, 0, ICON_PX, ICON_PX), "hit")
    painter.end()
    assert greenish(grabbed.pixelColor(ICON_PX // 2, ICON_PX // 2))
    assert greenish(reference.pixelColor(ICON_PX // 2, ICON_PX // 2))


def test_a_hit_icon_is_the_map_marks_colour(qapp):
    """The icon is drawn by the map's own mark code, so it is the map's green."""
    widget = TargetMapWidget()
    widget.set_report(synthetic_map_report())
    image = widget.render_to_image(QSize(1000, 584), {"targets": True})
    rect = widget.canvas_rect(QRectF(image.rect()))
    on_map = image.pixelColor(round(rect.left() + 0.65 * rect.width()), round(rect.top() + 0.5 * rect.height() + 0.6 * 0.05 * rect.width()))
    in_legend = symbol_image("hit", 96).pixelColor(48, 48)
    assert greenish(on_map) and greenish(in_legend)
    assert abs(on_map.hue() - in_legend.hue()) < 12


# -- the PDF's copy --------------------------------------------------------------------------------------


def test_the_pdf_legend_has_the_same_entries_note_and_tint(qapp):
    html = legend_html(600)
    for _kind, label in LEGEND_ENTRIES:
        assert label in html
    assert NUMBERS_NOTE in html and SOFT_ACCENT in html
    assert html.count("data:image/png;base64,") == 4  # one icon per entry
    assert 'width="600"' in html  # as wide as the map above it


def test_without_a_width_the_pdf_legend_takes_the_full_text_width(qapp):
    assert 'width="100%"' in legend_html()


def test_the_pdf_legend_text_is_in_a_grid_free_box(qapp):
    """One outlined cell around an unbordered table: Qt draws a border around every cell of a
    bordered table, which would turn the legend into a grid."""
    html = legend_html()
    assert html.count('border="1"') == 1 and html.count('border="0"') == 1


def test_the_pdf_legend_is_laid_out_by_qt_with_every_entry(qapp):
    doc = QTextDocument()
    doc.setHtml(legend_html(500))
    text = doc.toPlainText()
    for _kind, label in LEGEND_ENTRIES:
        assert label in text
    assert NUMBERS_NOTE in text


# -- the entries can be replaced (Follow the Target has its own, SPEC-input-selection-and-follow.md 4.5) ----


def test_set_entries_replaces_the_icons_the_labels_and_the_note(qapp):
    legend = MapLegend()
    legend.set_entries((("hit", "Trial followed"), ("on", "Pointer on target"), ("track", "Path")), "Numbers = x")
    assert legend.entries() == [("hit", "Trial followed"), ("on", "Pointer on target"), ("track", "Path")]
    assert legend.numbers_label.text() == "Numbers = x"
    # no leftover widget of the first set is still a child: the box shows three entries, not seven
    assert len(legend.findChildren(LegendIcon)) == 3
    assert len([w for w in legend.findChildren(QLabel) if w.objectName().startswith("legendLabel_")]) == 3
    legend.set_entries(LEGEND_ENTRIES)
    assert [kind for kind, _ in legend.entries()] == ["hit", "timeout", "skipped", "slot"]
    assert legend.numbers_label.text() == NUMBERS_NOTE and len(legend.findChildren(LegendIcon)) == 4


def test_the_pdf_legend_uses_the_entries_it_is_given(qapp):
    html = legend_html(600, entries=(("hit", "Trial followed"), ("track", "Path of the target")))
    assert "Trial followed" in html and "Path of the target" in html and "Target selected (hit)" not in html
    assert html.count("data:image/png;base64,") == 2 and NUMBERS_NOTE in html
