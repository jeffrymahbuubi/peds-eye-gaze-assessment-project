"""The form controls of the dashboard stylesheet: fields, combo box and its popup, spin boxes,
check box and radio indicators, sliders and plain tables (SPEC-design-system-phase1.md H5-H7).

Split out of :mod:`~src.ui.wtmh_theme`, which appends :data:`CONTROLS_STYLESHEET` to its own
rules, so the two stay under the file-size limit. Every value is a token of
:mod:`~src.ui.design_tokens`; nothing here is a literal colour.
"""

from __future__ import annotations

from ..engine.config import CONFIG_ROOT
from .design_tokens import (
    ACCENT,
    ACCENT_FOCUS,
    ACCENT_SUBTLE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    BORDER_WIDTH,
    DISABLED_FILL,
    FIELD_HEIGHT,
    FOCUS_BORDER_WIDTH,
    HEADER,
    INDICATOR_SIZE,
    INK,
    PANEL,
    RADIUS,
    ROW_SELECTED,
    SLIDER_GROOVE,
    SLIDER_GROOVE_PX,
    SLIDER_HANDLE_PX,
    STEPPER_WIDTH,
    TEXT_DISABLED,
)

# S12 fix: Qt's QSS "zero-size box + border" triangle trick does not
# reliably render as a triangle for ::up-arrow/::down-arrow subcontrols in
# this Qt/PySide6 build -- confirmed via a pixel-level zoomed widget grab
# that it painted a solid filled rectangle instead, under both the default
# "windowsvista" style and "Fusion" (SPEC-ui-setup-task-selection.md S12).
# Real PNG assets (generated once via a scratch script, committed here) are
# the standard, actually-reliable fix. CONFIG_ROOT is already absolute
# (Path(__file__).resolve()...), so this path is never CWD-dependent --
# important because QSS `url()` on a stylesheet string (not loaded from a
# .qss file) resolves relative paths against the process's current working
# directory, not this module's location.
_ICONS_DIR = (CONFIG_ROOT / "assets" / "icons").as_posix()

# A control keeps its outer size when it takes the focus: the 1 px border becomes 2 px, so
# the padding and the minimum content size each give 1 px back (H6). QSS ``min-height`` is
# the size of the content box, inside border and padding.
_BORDER = BORDER_WIDTH
_FOCUS_BORDER = FOCUS_BORDER_WIDTH
_FIELD_PAD_H = 12 - _BORDER
_FIELD_MIN_H = FIELD_HEIGHT - 2 * _BORDER
_IND_BOX = INDICATOR_SIZE - 2 * _BORDER  # an indicator's content box inside its 1 px border
_DOT_BORDER = 6  # a checked radio: a thick ring round a white disc of INDICATOR_SIZE - 12 px
_DOT_BOX = INDICATOR_SIZE - 2 * _DOT_BORDER

_FIELDS = (
    "QWidget#wtmhDashboard QLineEdit",
    "QWidget#wtmhDashboard QComboBox",
    "QWidget#wtmhDashboard QDateEdit",
    "QWidget#wtmhDashboard QSpinBox",
    "QWidget#wtmhDashboard QDoubleSpinBox",
)
_TEXT_AREAS = ("QWidget#wtmhDashboard QTextEdit", "QWidget#wtmhDashboard QPlainTextEdit")

CONTROLS_STYLESHEET = f"""
/* Fields (H5): 36 px high, 1 px border-strong, radius 4; the focus border is 2 px accent-focus
   (H6). The single-line ones get their height from min-height, the text areas from
   their content. */
{",".join(_FIELDS)} {{
    background: {PANEL};
    color: {INK};
    border: {_BORDER}px solid {BORDER_STRONG};
    border-radius: {RADIUS}px;
    min-height: {_FIELD_MIN_H}px;
    max-height: {_FIELD_MIN_H}px;
    padding: 0 {_FIELD_PAD_H}px;
}}
{",".join(_TEXT_AREAS)} {{
    background: {PANEL};
    color: {INK};
    border: {_BORDER}px solid {BORDER_STRONG};
    border-radius: {RADIUS}px;
    padding: 5px {_FIELD_PAD_H}px;
}}
{",".join(f"{s}:focus" for s in _FIELDS)} {{
    border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS};
    min-height: {_FIELD_MIN_H - 2}px;
    max-height: {_FIELD_MIN_H - 2}px;
    padding: 0 {_FIELD_PAD_H - 1}px;
}}
{",".join(f"{s}:focus" for s in _TEXT_AREAS)} {{
    border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS};
    padding: 4px {_FIELD_PAD_H - 1}px;
}}
{",".join(f"{s}:disabled" for s in (*_FIELDS, *_TEXT_AREAS))} {{
    color: {TEXT_DISABLED};
    background: {DISABLED_FILL};
    border-color: {BORDER_STRONG};
}}

/* Custom chevron + dropdown chrome, replacing the native OS arrow
   (S11.1 critique point 4). Drawn via a real PNG asset (see _ICONS_DIR
   above) -- an earlier zero-size/border "CSS triangle" version rendered as
   a solid filled rectangle instead of a triangle in this Qt/PySide6 build
   (S12), so a real image is used instead of a QSS-only trick. */
QWidget#wtmhDashboard QComboBox {{ padding-right: {STEPPER_WIDTH}px; }}
QWidget#wtmhDashboard QComboBox:focus {{ padding-right: {STEPPER_WIDTH - 1}px; }}
QWidget#wtmhDashboard QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: {STEPPER_WIDTH}px;
    border-left: 1px solid {BORDER_SUBTLE};
}}
QWidget#wtmhDashboard QComboBox::down-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    image: url({_ICONS_DIR}/chevron-down.png);
    width: 16px;
    height: 16px;
    margin-right: 4px;
}}

/* The popup list is a separate top-level QAbstractItemView, not a
   layout-tree descendant of QWidget#wtmhDashboard -- Qt forwards a
   QComboBox's own effective stylesheet down into its popup, so this rule
   still needs to be declared here even though it never leaked in from the
   rules above. Without it the popup falls back to the OS/Qt default
   palette, which on this app's Windows setup renders white text on a white
   background (SPEC-ui-setup-task-selection.md S11.2 finding A -- the Sex
   dropdown bug). Same root-cause family as the QCheckBox fix in S10.

   S13: this rule alone only styles the QListView itself -- the native
   popup FRAME wrapping it (Qt's undocumented QComboBoxPrivateContainer,
   a QFrame with no public class/object-name selector) draws its own
   heavy default border independently, especially visible after S12's
   switch to the Fusion style. QSS can't reach that frame directly, so
   setup_page.py additionally calls
   ``sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)`` in code to
   remove the native frame decoration, leaving this rule's own border/
   radius as the only visible one. */
QWidget#wtmhDashboard QComboBox QAbstractItemView {{
    background: {PANEL};
    color: {INK};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS}px;
    padding: 4px;
    outline: none;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item {{
    padding: 9px 12px;
    border-radius: {RADIUS}px;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:hover {{
    background: {ACCENT_SUBTLE};
    outline: none;
    border: none;
}}
/* S16: an explicit transparent border (not just outline: none) --
   Fusion's own PE_FrameFocusRect primitive can still paint a bare focus
   outline around the current item on a fresh popup open even with
   outline suppressed; giving it a real border color to paint instead
   (rather than relying on outline suppression alone) is the fix being
   tried here -- verified live, see SPEC-ui-setup-task-selection.md
   §16.3 for the actual result. */
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:focus {{
    background: {ACCENT_SUBTLE};
    outline: 0;
    border: 1px solid transparent;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:selected {{
    background: {ROW_SELECTED};
    color: {INK};
    outline: none;
    border: none;
}}

/* Themed spin-box steppers, replacing native OS up/down arrows (S12).
   Arrows are real PNG assets (see _ICONS_DIR above), each given its own
   "padding"-origin, centered subcontrol box -- without an explicit
   subcontrol-origin/position, Qt falls back to its platform style's own
   tiny built-in icon-metric box, which would clip even a real image down
   small. A 1px border between up-button and down-button (previously
   absent) gives the visible separator the critique asked for. */
QWidget#wtmhDashboard QSpinBox::up-button, QWidget#wtmhDashboard QDoubleSpinBox::up-button,
QWidget#wtmhDashboard QSpinBox::down-button, QWidget#wtmhDashboard QDoubleSpinBox::down-button {{
    background: {ACCENT_SUBTLE};
    width: {STEPPER_WIDTH}px;
    border-left: 1px solid {BORDER_SUBTLE};
}}
QWidget#wtmhDashboard QSpinBox::up-button, QWidget#wtmhDashboard QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: {RADIUS - 1}px;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}
QWidget#wtmhDashboard QSpinBox::down-button, QWidget#wtmhDashboard QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: {RADIUS - 1}px;
}}
QWidget#wtmhDashboard QSpinBox::up-button:disabled, QWidget#wtmhDashboard QDoubleSpinBox::up-button:disabled,
QWidget#wtmhDashboard QSpinBox::down-button:disabled, QWidget#wtmhDashboard QDoubleSpinBox::down-button:disabled {{
    background: {DISABLED_FILL};
}}
QWidget#wtmhDashboard QSpinBox::up-arrow, QWidget#wtmhDashboard QDoubleSpinBox::up-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center;
    image: url({_ICONS_DIR}/spin-up.png);
    width: 12px;
    height: 12px;
}}
QWidget#wtmhDashboard QSpinBox::down-arrow, QWidget#wtmhDashboard QDoubleSpinBox::down-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center;
    image: url({_ICONS_DIR}/spin-down.png);
    width: 12px;
    height: 12px;
}}

/* Check box and radio indicators are {INDICATOR_SIZE} px outside (H5): QSS ``width`` / ``height`` are the
   content box, so each state subtracts its own border. A checked check box is the accent
   with the white mark (a PNG: QSS cannot draw one); a checked radio is the accent with a
   white dot, drawn as a thick border round a white disc (QSS has no other way). A
   disabled checked one is border-strong grey with the same white mark (U4), an unchecked
   disabled one the disabled fill with a border-strong outline (H7). The focus border
   is drawn inside the same {INDICATOR_SIZE} px, so nothing moves (H6). */
QWidget#wtmhDashboard QCheckBox::indicator, QWidget#wtmhDashboard QRadioButton::indicator {{
    width: {_IND_BOX}px;
    height: {_IND_BOX}px;
    border: {_BORDER}px solid {BORDER_STRONG};
    background: {PANEL};
}}
QWidget#wtmhDashboard QCheckBox::indicator {{ border-radius: {RADIUS}px; }}
QWidget#wtmhDashboard QRadioButton::indicator {{ border-radius: {INDICATOR_SIZE // 2}px; }}
QWidget#wtmhDashboard QCheckBox::indicator:hover, QWidget#wtmhDashboard QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}
QWidget#wtmhDashboard QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: {_BORDER}px solid {ACCENT};
    image: url({_ICONS_DIR}/checkmark.png);
}}
QWidget#wtmhDashboard QRadioButton::indicator:checked {{
    border: {_DOT_BORDER}px solid {ACCENT};
    width: {_DOT_BOX}px;
    height: {_DOT_BOX}px;
    background: {PANEL};
}}
QWidget#wtmhDashboard QCheckBox::indicator:focus, QWidget#wtmhDashboard QRadioButton::indicator:focus {{
    border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS};
    width: {_IND_BOX - 2}px;
    height: {_IND_BOX - 2}px;
}}
QWidget#wtmhDashboard QRadioButton::indicator:checked:focus {{
    border: {_DOT_BORDER}px solid {ACCENT_FOCUS};
    width: {_DOT_BOX}px;
    height: {_DOT_BOX}px;
}}
QWidget#wtmhDashboard QCheckBox::indicator:disabled, QWidget#wtmhDashboard QRadioButton::indicator:disabled {{
    border: {_BORDER}px solid {BORDER_STRONG};
    width: {_IND_BOX}px;
    height: {_IND_BOX}px;
    background: {DISABLED_FILL};
}}
QWidget#wtmhDashboard QCheckBox::indicator:checked:disabled {{
    background: {BORDER_STRONG};
    image: url({_ICONS_DIR}/checkmark.png);
}}
QWidget#wtmhDashboard QRadioButton::indicator:checked:disabled {{
    border: {_DOT_BORDER}px solid {BORDER_STRONG};
    width: {_DOT_BOX}px;
    height: {_DOT_BOX}px;
    background: {PANEL};
}}
QWidget#wtmhDashboard QRadioButton {{ color: {INK}; }}

/* Themed slider (H5), used by SliderSpinRow: a {SLIDER_GROOVE_PX} px groove, the accent fill, a
   {SLIDER_HANDLE_PX} px handle (a 1 px border inside the size; the focus border takes 1 px of the
   handle's fill). Disabled: the handle and the fill are border-strong. */
QWidget#wtmhDashboard QSlider:horizontal {{ min-height: {SLIDER_HANDLE_PX}px; }}
QWidget#wtmhDashboard QSlider::groove:horizontal {{
    height: {SLIDER_GROOVE_PX}px;
    background: {SLIDER_GROOVE};
    border-radius: {SLIDER_GROOVE_PX // 2}px;
}}
QWidget#wtmhDashboard QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: {SLIDER_GROOVE_PX // 2}px;
}}
QWidget#wtmhDashboard QSlider::handle:horizontal {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    width: {SLIDER_HANDLE_PX - 2}px;
    height: {SLIDER_HANDLE_PX - 2}px;
    margin: -{(SLIDER_HANDLE_PX - SLIDER_GROOVE_PX) // 2}px 0;
    border-radius: {SLIDER_HANDLE_PX // 2}px;
}}
QWidget#wtmhDashboard QSlider::handle:horizontal:focus {{
    border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS};
    width: {SLIDER_HANDLE_PX - 4}px;
    height: {SLIDER_HANDLE_PX - 4}px;
}}
QWidget#wtmhDashboard QSlider::handle:horizontal:disabled {{
    background: {BORDER_STRONG};
    border-color: {BORDER_STRONG};
}}
QWidget#wtmhDashboard QSlider::sub-page:horizontal:disabled {{ background: {BORDER_STRONG}; }}

/* Plain data tables (calibration per-point breakdown, results metric
   tables) -- SPEC-result-logic.md §8.1/§8.3. Read-only, so no ::item states
   for hover/selected are needed. A table has square corners (2.4); its header is the
   header fill with ink text at 600. */
QWidget#wtmhDashboard QTableWidget {{
    background: {PANEL};
    color: {INK};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 0px;
    gridline-color: {BORDER_SUBTLE};
}}
QWidget#wtmhDashboard QTableWidget:focus {{ border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS}; }}
QWidget#wtmhDashboard QTableWidget::item {{ padding: 4px 8px; }}
QWidget#wtmhDashboard QHeaderView::section {{
    background: {HEADER};
    color: {INK};
    border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 6px 8px;
    font-weight: 600;
}}
/* The Test List is the one selectable table (SPEC-compass-task-flow.md 4A.4): the chosen row. */
QWidget#wtmhDashboard QTableWidget#wtmhTestTable::item:selected {{
    background: {ROW_SELECTED};
    color: {INK};
}}
"""
