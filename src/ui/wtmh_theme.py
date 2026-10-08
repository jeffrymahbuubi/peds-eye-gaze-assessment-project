"""The Qt stylesheet of the Setup / Tests dashboard, built from the design tokens.

Every colour, size and radius comes from :mod:`~src.ui.design_tokens` (SPEC-design-system-
phase1.md H1-H9; ``docs/design/fable-proposal.md`` 2.1-2.5): this module holds the QSS and
no hex value of its own.

Scoped to ``QWidget#wtmhDashboard`` and its descendants only, so it can
never leak into ``TaskCanvas`` or an embedded ``TaskRunView`` -- Qt
stylesheets apply to the widget they're set on plus descendants, never
siblings.
"""

from __future__ import annotations

from .design_tokens import (
    ACCENT,
    ACCENT_FOCUS,
    ACCENT_HOVER,
    ACCENT_SUBTLE,
    BORDER_STRONG,
    BORDER_SUBTLE,
    BORDER_WIDTH,
    BUTTON_HEIGHT,
    BUTTON_MIN_WIDTH,
    DANGER,
    DANGER_SUBTLE,
    DANGER_TEXT,
    DISABLED_FILL,
    FOCUS_BORDER_WIDTH,
    HEADER,
    INK,
    PAGE,
    PANEL,
    RADIUS,
    SUCCESS,
    SUCCESS_SUBTLE,
    SUCCESS_TEXT,
    TEXT_DISABLED,
    TEXT_SECONDARY,
    TITLE_BAR,
    TITLE_BAR_TEXT,
    TYPE_BODY,
    TYPE_BODY_LARGE,
    TYPE_CAPTION,
    TYPE_DISPLAY,
    TYPE_HEADING,
    WARNING,
)
from .wtmh_controls import CONTROLS_STYLESHEET

# A control keeps its outer size when it takes the focus: the 1 px border becomes 2 px, so
# the padding and the minimum content size each give 1 px back (H6). QSS ``min-height`` is
# the size of the content box, inside border and padding.
_BORDER = BORDER_WIDTH
_FOCUS_BORDER = FOCUS_BORDER_WIDTH
_BUTTON_PAD_H = 16 - _BORDER  # "padding 0 16" counted from the outer edge
_BUTTON_MIN_H = BUTTON_HEIGHT - 2 * _BORDER
_BUTTON_MIN_W = BUTTON_MIN_WIDTH - 2 * (_BUTTON_PAD_H + _BORDER)


def _states(selectors: tuple[str, ...], state: str) -> str:
    return ",\n".join(f"{selector}{state}" for selector in selectors)


def button_rule(
    selectors: tuple[str, ...] | str,
    *,
    text: str,
    fill: str,
    border: str,
    hover_fill: str,
    hover_text: str | None = None,
) -> str:
    """One tier of the button family (H5): 40 px high, 96 px wide at least, 14 px / 600, a
    1 px border in the tier's colour, the hover fill, a 2 px focus border that moves
    nothing (``outline: 0`` keeps the native focus rectangle out of it: a white-fill button
    drew one inside the border, SPEC-design-system-phase2.md H13), and the same grey-on-grey
    disabled look for every tier (the primary never changes tier with its state)."""
    if isinstance(selectors, str):
        selectors = (selectors,)
    hover_text = hover_text or text
    return f"""
{_states(selectors, "")} {{
    color: {text};
    background: {fill};
    border: {_BORDER}px solid {border};
    border-radius: {RADIUS}px;
    min-height: {_BUTTON_MIN_H}px;
    min-width: {_BUTTON_MIN_W}px;
    padding: 0 {_BUTTON_PAD_H}px;
    font-size: {TYPE_BODY}px;
    font-weight: 600;
    outline: 0;
}}
{_states(selectors, ":hover")}, {_states(selectors, ":pressed")} {{
    color: {hover_text};
    background: {hover_fill};
    border-color: {hover_fill};
}}
{_states(selectors, ":focus")} {{
    border: {_FOCUS_BORDER}px solid {ACCENT_FOCUS};
    min-height: {_BUTTON_MIN_H - 2}px;
    padding: 0 {_BUTTON_PAD_H - 1}px;
}}
{_states(selectors, ":disabled")} {{
    color: {TEXT_DISABLED};
    background: {DISABLED_FILL};
    border-color: {DISABLED_FILL};
}}
"""


_PRIMARY = ("QPushButton#wtmhPrimary", "QPushButton#cfgSave")
# The configuration page's footer buttons carry fixed names for qt-mcp and tests (cfgSave,
# cfgPreview, cfgCancel, cfgReset -- SPEC-compass-task-flow.md 4B.1), so they join the tier
# rules by selector instead of taking the tier's object name.
_SECONDARY = (
    "QPushButton#wtmhSecondary",
    "QPushButton#wtmhGhost",
    "QPushButton#cfgPreview",
    "QPushButton#cfgCancel",
    "QPushButton#cfgReset",
)
_TERTIARY = ("QPushButton#wtmhTertiary",)


def _alert(name: str, border: str) -> str:
    return f"""QFrame#wtmhAlert{name} {{
    background: {PANEL};
    border: 1px solid {border};
}}
"""


def _badge(name: str, fill: str, text: str) -> str:
    return f"""QLabel#wtmhBadge{name}, QWidget#wtmhDashboard QLabel#wtmhBadge{name} {{
    background: {fill};
    color: {text};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: {TYPE_CAPTION}px;
    font-weight: 600;
}}
"""


_DASHBOARD_STYLESHEET = f"""
QWidget#wtmhDashboard {{ background: {PAGE}; color: {INK}; }}
QWidget#wtmhDashboard QLabel {{ color: {INK}; }}
QWidget#wtmhDashboard QCheckBox {{ color: {INK}; }}

QWidget#wtmhTitleBar {{ background: {TITLE_BAR}; }}
QWidget#wtmhTitleBar QLabel {{ color: {TITLE_BAR_TEXT}; }}
QLabel#wtmhBrandTitle {{ font-size: {TYPE_BODY_LARGE}px; font-weight: 600; }}

/* Setup page's card stack scrolls independently of the pinned "Continue to
   Tasks" footer (SPEC-ui-setup-task-selection.md S22) -- the scroll area and
   its viewport otherwise paint an opaque native background over the page's
   own {PAGE} tint. The configuration page's card grid
   (SPEC-compass-task-flow.md 4B.7) scrolls the same way, above its pinned
   footer. */
QScrollArea#wtmhSetupScroll, QScrollArea#wtmhSetupScroll > QWidget,
QScrollArea#wtmhConfigScroll, QScrollArea#wtmhConfigScroll > QWidget {{
    background: transparent;
    border: none;
}}

/* A control greyed in place (the configuration page's Smoothing alpha while
   Smoothing is off): the base rules colour labels, fields and slider handles the
   same whether or not they are enabled, so each has a disabled rule (H5, H7). */
QWidget#wtmhDashboard QLabel:disabled,
QWidget#wtmhDashboard QCheckBox:disabled,
QWidget#wtmhDashboard QRadioButton:disabled {{ color: {TEXT_DISABLED}; }}

/* Themed scrollbar (SPEC-ui-setup-task-selection.md S22.6): a slim, rounded thumb, no
   arrow buttons, transparent track -- every QScrollBar under wtmhDashboard (Setup's
   card scroll, a Notes box's internal scrollbar). */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 2px 2px 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_SECONDARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
    border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px 2px 2px 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    min-width: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_SECONDARY};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
    border: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

QPushButton#wtmhNavButton {{
    color: {TITLE_BAR_TEXT};
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: {RADIUS}px;
    padding: 6px 14px;
    font-weight: 600;
    outline: 0;
}}
QPushButton#wtmhNavButton:hover {{ background: rgba(255,255,255,0.16); }}
QPushButton#wtmhNavButton:focus {{ border: {_FOCUS_BORDER}px solid {TITLE_BAR_TEXT}; padding: 5px 13px; }}
QPushButton#wtmhNavButton[active="true"] {{
    background: rgba(255,255,255,0.08);
    border-bottom: 3px solid {TITLE_BAR_TEXT};
}}

/* The type scale (proposal 2.1): wtmhPageTitle is the display step, wtmhSectionTitle the
   heading step. margin-bottom gives every card title some breathing room before its
   first content row, in one shared rule instead of touching each card-builder call
   site. */
QLabel#wtmhPageTitle {{ font-size: {TYPE_DISPLAY}px; font-weight: 700; color: {INK}; }}
QLabel#wtmhSectionTitle {{
    font-size: {TYPE_HEADING}px;
    font-weight: 600;
    color: {INK};
    margin-bottom: 6px;
}}
/* Muted text (helper lines, hints, messages). The dashboard scope in the second selector is what
   makes it win: ``QWidget#wtmhDashboard QLabel`` above sets the ink colour with two type names and
   an id, which outweighs a bare ``QLabel#wtmhMuted`` (one type name and an id), so a muted label
   rendered in ink until phase 2. A disabled one stays the disabled grey. */
QLabel#wtmhMuted, QWidget#wtmhDashboard QLabel#wtmhMuted {{ color: {TEXT_SECONDARY}; }}
QWidget#wtmhDashboard QLabel#wtmhMuted:disabled {{ color: {TEXT_DISABLED}; }}
/* A caption (the type scale's smallest step, in text-secondary): the Setup footer's "Needs: ..."
   under a disabled Continue and the configuration page's "Changed from ..." line (SPEC-design-
   system-phase2.md H4, C4). The selector carries the dashboard scope so it outweighs the generic
   label colour above. */
QWidget#wtmhDashboard QLabel#wtmhCaption {{ font-size: {TYPE_CAPTION}px; color: {TEXT_SECONDARY}; }}
/* The configuration page's column C title (SPEC-design-system-phase2.md H6): the heading step,
   quieter than a card title. */
QWidget#wtmhDashboard QLabel#cfgAdvancedTitle {{
    font-size: {TYPE_HEADING}px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

/* Button tiers (H5): primary, secondary (the old ghost), tertiary (text only); the danger
   tier is the run-end dialogs' own (run_dialogs.py), built from the same button_rule. */
{button_rule(_PRIMARY, text=PANEL, fill=ACCENT, border=ACCENT, hover_fill=ACCENT_HOVER)}
{button_rule(_SECONDARY, text=ACCENT, fill=PANEL, border=ACCENT, hover_fill=ACCENT_SUBTLE)}
{button_rule(_TERTIARY, text=ACCENT, fill="transparent", border="transparent",
             hover_fill=ACCENT_SUBTLE)}

QFrame#wtmhCard {{
    background: {PANEL};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {RADIUS}px;
}}
/* The Test List's empty state: one line inside the same frame the table has (H5). */
QFrame#wtmhEmptyTable {{
    background: {PANEL};
    border: 1px solid {BORDER_SUBTLE};
}}

/* Alerts (H8): white, a 1 px border in the state colour, body-large ink text. These are the
   rules of the plain QFrame banners the report page and the standalone settings dialog still
   use; the operator pages' alerts are AlertBox widgets (alert_box.py, phase 2 H3), which
   style themselves with the glyph tile and the bold state word. */
QFrame#wtmhAlertInfo, QFrame#wtmhAlertWarning, QFrame#wtmhAlertSuccess, QFrame#wtmhAlertError {{
    border-radius: {RADIUS}px;
    padding: 4px;
}}
{_alert("Info", BORDER_STRONG)}{_alert("Warning", WARNING)}{_alert("Success", SUCCESS)}{_alert("Error", DANGER)}
QFrame#wtmhAlertInfo QLabel, QFrame#wtmhAlertWarning QLabel,
QFrame#wtmhAlertSuccess QLabel, QFrame#wtmhAlertError QLabel {{
    font-size: {TYPE_BODY_LARGE}px;
}}

{_badge("Neutral", HEADER, TEXT_SECONDARY)}{_badge("Success", SUCCESS_SUBTLE, SUCCESS_TEXT)}{_badge("Accent", ACCENT_SUBTLE, ACCENT)}{_badge("Danger", DANGER_SUBTLE, DANGER_TEXT)}
"""

STYLESHEET = _DASHBOARD_STYLESHEET + CONTROLS_STYLESHEET
