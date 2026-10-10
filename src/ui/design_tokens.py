"""Design tokens of the operator UI (SPEC-design-system-phase1.md H1; ``docs/design/
fable-proposal.md`` 2.1-2.5, with the accent family of 2.2 in the WTMH lab blue).

Every colour, type size, radius and control size the style sheets use is named here, so a
sheet never holds a hex value of its own: :mod:`~src.ui.wtmh_theme` is the Qt style sheet
built from these, and the other modules that style a widget import the same names.
The report's Target Map, its legend and the PDF take the map and data-viz colours of
proposal 2.2 from here too (SPEC-design-system-phase4.md H1). Qt-free, so the contrast test
can read it headless.
"""

from __future__ import annotations

# -- colour: neutrals -------------------------------------------------------------------

INK = "#161616"  # all text
TEXT_SECONDARY = "#525252"  # helper text, captions, the "Not done" word
TEXT_DISABLED = "#6F6F6F"  # a disabled label or button, on DISABLED_FILL
PAGE = "#F4F4F4"  # the window background
PANEL = "#FFFFFF"  # cards, fields, tables, dialogs
BORDER_SUBTLE = "#E0E0E0"  # card edges, table grid lines (decorative only)
BORDER_STRONG = "#8D8D8D"  # field and control outlines, the disabled checked box fill
HEADER = "#E0E0E0"  # table header fill
DISABLED_FILL = "#E0E0E0"  # a disabled button, field or unchecked box
ROW_SELECTED = "#CFE2F1"  # the chosen table row
TITLE_BAR = "#12374A"  # the top bar
TITLE_BAR_TEXT = "#FFFFFF"

# -- colour: accent (the WTMH lab blue, one family, no gradient) --------------------------

ACCENT = "#1F669E"  # primary fill, secondary text and border, links, slider fill
ACCENT_HOVER = "#17507D"  # primary hover and pressed
ACCENT_FOCUS = "#2D7EB3"  # the 2 px focus border of every focusable control
ACCENT_SUBTLE = "#E3EEF7"  # accent badge, hovered list row, spin-box stepper
SLIDER_GROOVE = "#C6C6C6"  # the slider track
# A disabled primary button (Start, Run Test, Continue to Tests ...) keeps the accent family: the
# accent at 30 % over white, with a blue-grey text; every other disabled button is DISABLED_FILL
# grey (SPEC-design-system-phase2.md section 9, user decision 2026-10-09).
ACCENT_DISABLED_FILL = "#BCD1E2"
ACCENT_DISABLED_TEXT = "#385A76"

# -- colour: states (Carbon support set) -------------------------------------------------

DANGER = "#DA1E28"
DANGER_TEXT = "#A2191F"
DANGER_SUBTLE = "#FFF1F1"
SUCCESS = "#198038"
SUCCESS_TEXT = "#0E6027"
SUCCESS_SUBTLE = "#DEFBE6"
WARNING = "#BA4E00"
WARNING_TEXT = "#8A3800"
WARNING_SUBTLE = "#FCF4D6"
WARNING_CHIP = "#F1C21B"  # the filled PRACTICE / PREVIEW chip of the run bar

# -- colour: report map and data-viz (proposal 2.2, SPEC-design-system-phase4.md H1) -------------
# The heat ramp is not here: it stays the HSV ramp Gazepoint Analysis prints.

MAP_HIT_FILL = "#A7F0BA"  # the hit circle's fill; its digits are ink (13.63:1)
MAP_HIT_OUTLINE = "#198038"  # the hit circle's edge, the legend icon
MAP_MISS = "#DA1E28"  # the missed target's X and ring (its digits stay ink, on a white pill)
MAP_SKIPPED = "#6F6F6F"  # a skipped trial's dashed ring, the off-target stretch of a pointer path
MAP_SLOT = "#8D8D8D"  # the faint layout circle
MAP_PATH_DARK = "#1F669E"  # the selected trial's path at its start, the pointer on the target
MAP_PATH_LIGHT = "#2D7EB3"  # ... and at its end
MAP_FIXATION = "#1F669E"  # a fixation's ring and its number badge's outline
MAP_OVERLAY = "#1F669E"  # the Summary's Scanpath overlay, one colour for every trial (X1) ...
MAP_OVERLAY_ALPHA = 200  # ... at this alpha (of 255)
MAP_OVERLAY_ON_PANEL = "#4F87B3"  # MAP_OVERLAY at MAP_OVERLAY_ALPHA over PANEL, for the contrast row
MAP_SELECT = "#F2B705"  # the selection star (drawn with an ink outline)

# (foreground, background, minimum ratio) for every row of proposal 2.2 that has a ratio:
# 4.5 for text, 3 for a border or glyph; a disabled control only has to stay readable.
# The minimums are the proposal's figures (recomputed for the WTMH blue) less rounding.
CONTRAST_PAIRS: tuple[tuple[str, str, float], ...] = (
    (INK, PANEL, 18.10),
    (INK, PAGE, 16.45),
    (TEXT_SECONDARY, PANEL, 7.81),
    (TEXT_SECONDARY, PAGE, 7.10),
    (TEXT_SECONDARY, HEADER, 5.92),
    (TEXT_DISABLED, DISABLED_FILL, 3.81),
    (BORDER_SUBTLE, PANEL, 1.32),
    (BORDER_STRONG, PANEL, 3.32),
    (BORDER_STRONG, PAGE, 3.02),
    (INK, HEADER, 13.71),
    (INK, ROW_SELECTED, 13.62),
    (TITLE_BAR_TEXT, TITLE_BAR, 12.57),
    (PANEL, ACCENT, 6.08),
    (ACCENT, PANEL, 6.08),
    (ACCENT, PAGE, 5.53),
    (PANEL, ACCENT_HOVER, 8.47),
    (ACCENT_FOCUS, PANEL, 4.42),
    (ACCENT_FOCUS, PAGE, 4.02),
    (ACCENT, ACCENT_SUBTLE, 5.17),
    (ACCENT_DISABLED_TEXT, ACCENT_DISABLED_FILL, 4.62),  # the disabled primary's text, on its pale blue
    # The proposal prints 4.51, the teal-era figure; with the blue accent it is 3.56 (a track
    # is a non-text part, which needs 3:1).
    (SLIDER_GROOVE, ACCENT, 3.56),
    (PANEL, DANGER, 5.00),
    (DANGER, PANEL, 5.00),
    (DANGER_TEXT, DANGER_SUBTLE, 7.09),
    (DANGER_TEXT, PAGE, 7.08),
    (INK, DANGER_SUBTLE, 16.46),
    (PANEL, SUCCESS, 5.02),
    (SUCCESS, PANEL, 5.02),
    (SUCCESS_TEXT, SUCCESS_SUBTLE, 7.00),
    (SUCCESS_TEXT, PAGE, 7.02),
    (SUCCESS_TEXT, WARNING_SUBTLE, 7.00),
    (INK, SUCCESS_SUBTLE, 16.41),
    (WARNING, PANEL, 5.03),
    (WARNING, WARNING_SUBTLE, 4.56),
    (WARNING_TEXT, WARNING_SUBTLE, 7.20),
    (WARNING_TEXT, PAGE, 7.21),
    (INK, WARNING_SUBTLE, 16.42),
    (INK, WARNING_CHIP, 10.75),
    # Phase 1 additions that are not rows of the proposal's table: the white mark on the
    # disabled checked box (non-text, 3:1) and on the danger button's hover.
    (PANEL, BORDER_STRONG, 3.32),
    (PANEL, DANGER_TEXT, 7.79),
    # Report map and data-viz (proposal 2.2): the digits on a hit, then the marks on white. The
    # overlay is a non-text mark, which needs 3:1, as composited over the canvas.
    (INK, MAP_HIT_FILL, 13.63),
    (MAP_HIT_OUTLINE, PANEL, 5.02),
    (MAP_MISS, PANEL, 5.00),
    (MAP_SKIPPED, PANEL, 5.02),
    (MAP_SLOT, PANEL, 3.32),
    (MAP_PATH_DARK, PANEL, 6.08),
    (MAP_PATH_LIGHT, PANEL, 4.42),
    (MAP_FIXATION, PANEL, 6.08),
    (MAP_OVERLAY_ON_PANEL, PANEL, 3.85),
)

# -- type scale (proposal 2.1): the only sizes a sheet may use -------------------------------

FONT_FAMILY = "Segoe UI"
TYPE_DISPLAY = 28  # a page title; 700
TYPE_HEADING = 20  # a card or section title, a dialog heading; 600
TYPE_BODY_LARGE = 16  # read-aloud text, the run bar status, a banner's text
TYPE_BODY = 14  # everything else; the application font
TYPE_CAPTION = 12  # footnotes, helper lines, badges
TYPE_SCALE = (TYPE_CAPTION, TYPE_BODY, TYPE_BODY_LARGE, TYPE_HEADING, TYPE_DISPLAY)

# -- spacing (4 px base), radius, control sizes (all px) ----------------------------------

SPACING_SCALE = (4, 8, 12, 16, 24, 32, 48)
RADIUS = 4  # buttons, fields, cards and alerts; tables and the title bar have none
BORDER_WIDTH = 1
FOCUS_BORDER_WIDTH = 2  # the focus border of every focusable control
BUTTON_HEIGHT = 40
BUTTON_MIN_WIDTH = 96
FIELD_HEIGHT = 36
TABLE_ROW_HEIGHT = 40
INDICATOR_SIZE = 20  # a check box or radio button
STEPPER_WIDTH = 24  # a spin box's up / down column
SLIDER_GROOVE_PX = 4
SLIDER_HANDLE_PX = 20
RUN_BAR_HEIGHT = 48
RUN_BAR_BUTTON_HEIGHT = 36

