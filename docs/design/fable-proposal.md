# Fable UI/UX proposal (Task B)

Written 2026-10-08 by the Fable designer against tree `e753282` (branch feature/compass-task-flow),
answering `docs/design/fable-evaluation.md` (Task A). Sources: the brief, the research and inventory
files, screenshots 01-20, every wireframe, the theme and canvas code, the report code and the two
theme YAML files (list in §7). Contrast ratios are WCAG 2.2 relative-luminance ratios computed from the
hex values with a script; px values come from the QSS, the code or the 1920x1080 captures. The PDF
(16) could not be rendered here; its findings are taken from Task A §4.9 and `report_pdf.py`. Nothing
was run on the app.

## 0. Executive summary

1. **Direction: a clinical instrument look, built from IBM Carbon's tokens and the NHS content rules,
   delivered as a QSS token port.** No widget library. Segoe UI stays, the WTMH blue identity stays (user decision 2026-10-08, §2.2), but
   every size, colour and spacing becomes a named token that meets AA on its own background.
2. **One type scale (six steps, body 14 px)** replaces eight ad hoc sizes and the 12 px body the
   clinician reads standing beside a child (Task A §2.2, §6).
3. **State is never carried by tint or bold alone.** A status component (glyph + word) covers the
   Test List, Setup, the Start page, the run bar and the report's Outcome column (Task A §1.2, §4.2).
4. **Every state token measured here passes AA:** primary button 6.08:1, danger 5.00:1, success
   5.02:1, warning text 7.20:1, slider fill 4.51:1, run-bar button border 3.02:1, map digits 13.63:1
   (Task A §2.1 fails: 2.79, 3.18, 3.37, 2.20, 1.73, about 2.0).
5. **Each page gets one anchor and a content width** (Setup 1200 px, fields sized to content; Test
   List table 1200 px with its buttons beside it; Start page blocker as a Blocked block beside Go to
   Setup; report main column 1100 px) (Task A §1.1, T11).
6. **Canvas feedback ladder cue < on-target < success**, with a target at 4.43:1, a two-tone outline
   that follows the shape, distractors at 3.33:1 and a 500 ms success flash (Task A §5).
7. **Copy rules:** no em-dash labels, one date format (yyyy-MM-dd HH:mm), one vocabulary shared by the
   configuration page, the report and the PDF, with the exact replacement strings in §4.
8. **No new features.** The one behaviour change proposed is full screen during a run (hub-confirmed
   legitimate, §3.6); the Setup status badges exist only in the approved wireframe and are flagged.
9. **Four implementation phases**, each a SPEC step with acceptance checks: tokens + type + copy;
   components + page layout; canvas; report + PDF. A fifth, optional, covers the standalone dialog.
10. Files that change: `wtmh_theme.py`, `dialog_theme.py`, `run_bar.py`, `run_dialogs.py`,
    `dashboard_window.py` (base font), the page builders, `canvas.py`, `canvas_shapes.py`, both theme
    YAML files, `target_map_paint.py`, `map_legend.py`, `report_pdf.py`, `report_format.py`,
    `report_config.py`. Wireframes needing an update are marked in §3.

## 1. Direction

**Chosen: clinical instrument.** Carbon's visual grammar (flat surfaces, 4 px corners, one border
weight, a strict 4 px spacing grid, a type scale with few steps, tokens with roles, AA baked in)
reads as a measuring instrument rather than a dashboard template. That is what a therapist expects
from an assessment tool and what a printed report should look like. The NHS service manual
contributes what Carbon does not have: plain-language rules, field width by content length, error
and status wording for staff under time pressure. For the child the canvas keeps its own rules (§2.6);
no design system covers a gaze canvas, so those rules are derived from contrast and timing
measurements, not from a system.

Why not the others, for these two audiences:

| Runner-up | What it would give | Why not first |
|---|---|---|
| Fluent 2 via PySide6-Fluent-Widgets (GPLv3, allowed) | Native Windows 11 look familiar to clinic staff; ready widgets with focus and disabled states | Replaces every widget, not just the style: every page builder, the qt-mcp object names and about 2,480 tests are touched; the acrylic and rounded Fluent look is the "Windows settings app" template, generic in its own way; nothing for the canvas or the PDF |
| Fluent-Qt (MIT) | Lighter than the above | Young C++ project with bindings; the same rewrite risk with less community |
| NHS design system as the visual language too | Highest contrast, calmest | Web-first and low density: a 13-column trial table or a 17-row configuration table does not fit its spacing; Frutiger is licensed, so the type would be substituted anyway |
| Plain OS widgets (the Compass look, walkthrough §2) | Zero styling work | Loses the state system, the themed scrollbars and controls already fixed for dark-mode leaks (`dialog_theme.py`), and gives no control over contrast |
| Material 3 / shadcn | Nothing new | The source of tells T2, T3, T6, T7 (research §1) |

What stays from today: the page flow, the WTMH blue family as the single accent, Segoe UI (the Windows UI
font, so the app reads as native rather than as a web template), the amber practice bar, the run
bar's word + colour tracking state, the run-end dialog logic, the visual-angle sizing, the dwell and
switch logic, the shortcuts Alt-P, Alt-Q, Esc and H.

## 2. Design system v1

### 2.1 Type scale

Font: Segoe UI (already the Qt default on Windows; no bundling). Base font set once on the
QApplication with `QFont.setPixelSize(14)` (Qt style sheets do not inherit fonts to children, but the
application font propagates to every widget, including dialogs, the run bar and the canvas). Only the
larger roles get a QSS rule. Numbers in tables use tabular figures where Qt offers them.

| Step | Size / weight / line | Role | Replaces today |
|---|---|---|---|
| display | 28 px / 700 / 36 px | Page title: "Setup", "Test List for P9REAL", "Start Grid Click 1", "Summary Results" | 22 px `wtmhPageTitle` (01, 04, 11, 13) |
| heading | 20 px / 600 / 28 px | Card and section titles, dialog headings | 16 px `wtmhSectionTitle`, 17 px Start headings, 20 px `runDlgHeading` |
| body-large | 16 px / 400 / 24 px | Read-aloud text, the Start page's Blocked block, the run bar status, banner text | 15 px read-aloud (19), 13 px run bar (06), 12 px blocker (11) |
| body | 14 px / 400 / 20 px | Everything else: labels, fields, table cells, buttons (600), radio and check box text | 12 px body on every page (01-15) |
| caption | 12 px / 400 / 16 px | Footnotes, helper lines, "Changes are saved automatically.", badge text (600) | 11 px badges, 12 px footnotes |
| canvas | not in the scale | "Paused" at min(w, h) / 14, unchanged | `canvas.py` `_draw_paused` |

Rule: no size outside the scale; weight 600 only for headings, buttons and the status word; bold
never carries a state on its own (Task A §4.2, §4.8).

### 2.2 Colour tokens

Every token names its role, its intended background and the ratio it achieves there. AA is 4.5:1 for
text, 3:1 for large text, borders and glyphs. "exempt" marks disabled controls (WCAG 1.4.3 exception),
still kept at or above 3.8:1 so a greyed control stays readable (Task A §6 "close to invisible").

**User decision 2026-10-08: the accent family is the WTMH lab blue, not Fable's teal.** The accent is
#1F669E, the blue end of the WTMH logo ring (`resources/styling/wtmh_logo.png`, measured as the
20th-percentile luminance of its right-hand band); the focus colour is the logo's middle blue #2D7EB3.
Hover, subtle tint and the selected row are derived from the same hue, and the title bar keeps today's
navy #12374A. Every ratio below is recomputed for the new values; all still pass. The teal values they
replace are given in brackets.

Operator UI, neutrals:

| Token | Hex | On | Ratio | Role |
|---|---|---|---|---|
| ink | #161616 | white / page | 18.10 / 16.45 | all text |
| text-secondary | #525252 | white / page / table header | 7.81 / 7.10 / 5.92 | helper text, captions, "Not done" word |
| text-disabled | #6F6F6F | disabled fill #E0E0E0 | 3.81 (exempt) | disabled labels, buttons, spin boxes |
| page | #F4F4F4 | | | window background (replaces the teal-tinted #F5F9FB) |
| panel | #FFFFFF | | | cards, fields, tables, dialogs |
| border-subtle | #E0E0E0 | white | 1.32 | card edges, table grid lines (decorative only) |
| border-strong | #8D8D8D | white / page | 3.32 / 3.02 | field and control outlines, run-bar buttons, slider handle when disabled |
| header | #E0E0E0 | with ink | 13.71 | table header fill (was SOFT_ACCENT, the same as the selected row) |
| row-selected | #CFE2F1 | with ink | 13.62 | the chosen Test List row (now distinct from the header by hue) [was #CFE8E7] |
| title-bar | #12374A | white text | 12.57 | top bar, today's WTMH navy kept [was #0B3B3B] |

Accent (WTMH blue, one family, no gradient):

| Token | Hex | On | Ratio | Role |
|---|---|---|---|---|
| accent | #1F669E | white text on it / as text on white / on page | 6.08 / 6.08 / 5.53 | primary button fill, secondary button text and border, links, slider fill, nav underline |
| accent-hover | #17507D | white text | 8.47 | primary hover and pressed [was #004144] |
| accent-focus | #2D7EB3 | white / page | 4.42 / 4.02 | 2 px focus border on every focusable control (needs 3:1) [was #007D79] |
| accent-subtle | #E3EEF7 | with accent text | 5.17 | accent badge, "PREVIEW" chip when not amber [was #D9FBFB] |
| slider-groove | #C6C6C6 | under accent fill | 4.51 | slider track (was 2.20) |

State colours (Carbon support set):

| Token | Hex | On | Ratio | Role |
|---|---|---|---|---|
| danger | #DA1E28 | white text on it / as border on white | 5.00 / 5.00 | danger button fill, map miss X, error border |
| danger-text | #A2191F | red-10 #FFF1F1 / page | 7.09 / 7.08 | danger badge text, run bar "tracker DISCONNECTED" |
| danger-subtle | #FFF1F1 | with ink | 16.46 | danger badge fill, error banner fill |
| success | #198038 | white text on it / as border | 5.02 / 5.02 | success glyph, map hit outline |
| success-text | #0E6027 | green-10 #DEFBE6 / page / amber bar | 7.00 / 7.02 / 7.00 | success badge text, run bar "tracking OK" |
| success-subtle | #DEFBE6 | with ink | 16.41 | success badge fill |
| warning | #BA4E00 | white / yellow-10 | 5.03 / 4.56 | warning glyph and border |
| warning-text | #8A3800 | yellow-10 / page / amber bar | 7.20 / 7.21 / 7.20 | warning badge text, run bar "no gaze for 3 s" |
| warning-subtle | #FCF4D6 | with ink | 16.42 | warning banner fill, practice and preview run bar |
| warning-chip | #F1C21B | with ink | 10.75 | the filled PRACTICE / PREVIEW chip on the run bar |
| info | neutral: border-strong + ink | | | notes and help lines use no colour (colour only for meaning) |

Report map and data-viz:

| Token | Hex | On white | Role |
|---|---|---|---|
| map-hit-fill | #A7F0BA | ink digits 13.63 | hit circle fill (was success at alpha 150 with white digits, about 2.0) |
| map-hit-outline | #198038 | 5.02 | hit circle edge, legend icon |
| map-miss | #DA1E28 | 5.00 | X and its ring; digits stay ink on a white pill |
| map-skipped | #6F6F6F | 5.02 | dashed ring |
| map-slot | #8D8D8D | 3.32 | faint layout circle (was MUTED at alpha 90, below 3:1) |
| map-path-dark / light | #1F669E / #2D7EB3 | 6.08 / 4.42 | the selected trial's path, dark to light with time (the light end was #2B8CB0) |
| map-fixation | #1F669E | 6.08 | fixation ring and number badge outline |
| map-overlay | #1F669E at alpha 200 | 3.85 (composite #4F87B3; non-text, needs 3:1) | the Summary's Scanpath overlay, one colour for all trials (§3.8) |
| map-select | #F2B705 star with ink outline | | unchanged |
| heat | HSV blue-to-red ramp, alpha 0.15-0.80 | | unchanged: the ramp Gazepoint Analysis prints, which the clinicians already read |

### 2.3 Spacing scale

4 px base: 4, 8, 12, 16, 24, 32, 48. Page gutter 32; card padding 24; gap between a label and its
field 4; between fields 16; between cards 24; between a section title and its content 12; footer
height 64 with 16 px padding. Content widths: form pages 1200 px max, left-aligned; the configuration
page keeps its 1500 px three-column grid; the report sidebar keeps 460 px and the main column is
capped at 1100 px. Field width by content: Subject ID 320, date 200, Sex 240, Control Address 320,
Control Port 120, Point Count 100, Test Name 480, Evaluator 320, spin boxes 88, Notes three lines
(84 px, as the configuration page already does).

### 2.4 Radius and elevation

Radius 4 px on buttons, fields, cards and alerts; 0 px on tables and the title bar; full pill only on
status badges and chips. No shadows anywhere in the window; dialogs keep the OS shadow only. One
container level: a card never holds a card or an alert; alerts sit between cards at the page level.
Cards keep a 1 px border-subtle edge on the #F4F4F4 page and no fill tint.

### 2.5 Component rules

- **Buttons.** Height 40 px, min width 96, 14 px / 600, radius 4, padding 0 16. Primary: accent fill,
  white text; hover accent-hover; disabled fill #E0E0E0, text-disabled (same size and place, so the
  primary never changes tier with state, Task A §4.5). Secondary: white fill, 1 px accent border,
  accent text (today's ghost). Tertiary (text only, accent) for "Back to Setup". Danger: danger fill,
  white text, only in confirmations. Focus: 2 px accent-focus border with a 1 px white gap, drawn by
  explicit `:focus` rules on buttons, radios and check boxes (none exist today, §6.2).
- **Tables.** Header 14 px / 600 ink on header fill; rows 40 px; grid lines border-subtle; the
  selected row row-selected; sort indicator in accent. Status and Outcome cells hold a status badge,
  never bare text. Numeric columns right-aligned with tabular figures. Two-line headers are allowed
  ("Reaction" / "Time (s)") to narrow wide tables.
- **Forms.** Label above the field, 14 px / 400; fields 36 px tall, white, 1 px border-strong,
  radius 4; focus becomes 2 px accent-focus with the padding reduced by 1 px so the box does not move.
  Check box and radio indicators 20 px (WCAG 2.5.8: the drawn target meets 24 px with its 2 px
  margin); spin-box stepper column 24 px wide. A disabled control: fill #E0E0E0, border-strong,
  text-disabled, and a `QCheckBox::indicator:disabled` / `QRadioButton::indicator:disabled` rule
  (checked: grey fill, white mark) so a greyed-in-place box never keeps the accent blue (Task A §4.4, hub §8.7).
- **SliderSpinRow.** Slider 20 px handle, groove 4 px slider-groove, fill accent; length capped at
  240 px when the range has 10 steps or fewer (ticks shown), 360 px otherwise; spin box 88 px.
  Disabled: handle and fill border-strong (3.32:1 on white), groove unchanged.
- **Radio groups.** Group label 14 px / 600, options 14 px / 400, 8 px apart, descriptions after a
  colon in the same line and colour. Never a combo box for a choice of 3 to 5 (so `task-settings.md`
  and the configuration page share one grammar, Task A §4.10).
- **Alerts and banners.** White fill, 1 px border in the state colour (warning 5.03, danger 5.00,
  neutral border-strong 3.32), a 20 px glyph tile in the state colour at the left, a bold state word
  ("Blocked:", "Warning:", "Note:") then body text in ink at body-large. No left stripe, no tint fill
  (T5, T6). Warning and danger may use their subtle fill behind the glyph tile only.
- **Status badges.** Pill 24 px tall, 12 px / 600, glyph 12 px + word: Done (filled circle,
  success-subtle, success-text), Not done (hollow circle, header fill, text-secondary), Ended early
  (half circle, warning-subtle, warning-text, "Ended early 4/6"), Data missing (triangle,
  warning-subtle, warning-text), Disconnected (square, danger-subtle, danger-text), Connected /
  Calibrated (filled circle, success). Glyphs are painted 12 px pixmaps in a small helper, not font
  characters, so they cannot fall back to a missing glyph.
- **Dialogs.** 480 px min width, heading 20 px / 600, body 14 px, 24 px padding, buttons
  right-aligned in the order primary, secondary, danger; the safe answer stays the default and Esc
  (unchanged logic, `run_dialogs.py`). Lists inside dialogs: white, selected row row-selected.
- **Run bar.** 48 px tall; page fill for a recorded run, warning-subtle for Preview and Practice with
  a filled warning-chip reading PRACTICE or PREVIEW (ink, 10.75:1); then "Trial 4 of 18"; then the
  tracking state as glyph + word in success-text / warning-text / danger-text (7.0-7.2:1 on both
  fills). Buttons 36 px, border-strong (3.02:1 on the page fill), NoFocus as today.

### 2.6 Canvas rules (child-facing)

The ladder is **cue < on-target < success**, measured against the forest field #e8f5e9 (space in
brackets, against #0d1b2a). The theme YAML gains explicit keys for every colour the canvas draws, so
no colour is derived from `cursor_color` with an alpha any more.

| Element | Forest | Ratio on field | Space | Ratio |
|---|---|---|---|---|
| field | #e8f5e9 | | #0d1b2a | |
| target fill, flat (no radial gradient) | #D32F2F | 4.43 | #03a9f4 | 6.61 |
| target outline, two-tone: 3 px #102010 outside + 2 px white inside, following the shape path | #102010 | 15.10 (3.41 on the target) | white | 17.39 (2.63 on the target) |
| distractor fill, no outline | #5F8F66 | 3.33 | #4F6B85 | 3.13 |
| grid cell outline 2 px, fill white alpha 16 | #5F8F66 | 3.33 | #4F6B85 | 3.13 |
| on-target ring (one ring, r+10, 6 px, follows the shape) | #1b5e20 | 7.00 | #ffeb3b | 14.25 |
| dwell arc (r+16, 8 px): white core on a #102010 halo, like the cursor | white / #102010 | 1.12 / 15.10 (the halo carries it) | white | 17.39 |
| glow (Switch and Follow only): from the outline to r + 0.3 r, alpha 160 to 0, capped at half the distance to the nearest slot | #2E7D32 | 4.56 at its edge | #ffd54f | 12.33 |
| success: target fill turns to success colour for 500 ms, outline stays; 12 particles, 8 px, 500 ms | #2E7D32 | 4.56 | #ffd54f | 12.33 |
| unselectable target (Follow outside its window) | fill darker(180) as today, no outline, no glow | 7.28 | | |
| follow trail | target colour at alpha 40 max, width 0.2 r, 60 samples | 1.26 (deliberately faint: the target must be the brightest thing, Task A §5.4) | | |
| gaze cursor | unchanged (#102010 halo, white core, r 5 px) | | | |
| Paused | unchanged | 7.00 | | |

Timing: on-target ring appears on the first on-target frame and disappears on the first off-target
frame, no ramp; the dwell arc fills over threshold_ms as today; success lasts 500 ms, inside the
800 ms default inter-trial interval, so it never delays the next trial; nothing else moves. Shapes: the
outline, the on-target ring and the glow are built from `shape_path` at r + offset, so a square target
gets a square ring (Task A §5.2). The `character` key in both YAML files is read nowhere in `src/`
(§6.1) and is removed as part of the YAML change.

Why this ladder: the cue is strong in form (the only outlined, filled, saturated shape) and in
luminance against the field; red vs green distractors are 1.33:1 in luminance, so for a child with a
colour-vision deficiency the outline, not the hue, is the cue. The on-target ring is one ring in one
colour instead of three stacked rings in two (Task A §5.3). Success is the only event that changes the
target itself, so it is the loudest.

## 3. Concrete changes per page

Impact / effort are H, M, L. "Rule" names the §2 token or component; "Finding" cites Task A.
"Wireframe" marks a change to `docs/wireframes/`.

### 3.1 Setup (01)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| S1 | Body 14 px, title 28 px, card titles 20 px | H / L | §2.1 | §2.2, §6 | no |
| S2 | Content column 1200 px; Subject ID 320 px, date 200, Sex 240, Address 320, Port 120, Point Count 100; Continue to Tests 240 px right-aligned in the footer | H / M | §2.3 | §4.1 T11 | setup.md widths |
| S3 | "Not connected." becomes a status badge (Disconnected, danger) beside Connect; after connecting, Connected (success); Calibration card shows Not calibrated (warning) or Calibrated, 5 points, 1.8° (success) beside its buttons | H / M | §2.5 badges | §4.1 H1 | the wireframe's badge row is top-right; this proposal puts each badge in its card. Setup badges are in setup.md but not in code (hub §8.3): building them is a wireframe item, hub to confirm scope |
| S4 | The disabled Continue gets a caption under it listing what is missing ("Needs: tracker, calibration, Sex") | H / L | §2.1 caption, §4 copy | §4.1 H1 | setup.md |
| S5 | Display line: white alert with a success glyph, no stripe, not inside a card | M / L | §2.5 alerts | §4.1 T3+T5 | no |
| S6 | "No tracker connected: only Mouse tests can run." as a neutral alert with the Note glyph | M / L | §2.5 alerts | §4.1 | no |
| S7 | Date edit display format yyyy-MM-dd | M / L | §4 dates | §4.1 H4 | no |
| S8 | Primary button flat accent (no gradient); Do Calibration keeps primary tier when disabled | M / L | §2.5 buttons | §4.1, T2 | no |
| S9 | Focus rules on buttons, check box, radio | M / L | §2.5 | §6 | no |

### 3.2 Test List (02, 04, 12)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| T1 | Status column shows a status badge: Done, Not done, Ended early 4/6, Data missing | H / M | §2.5 badges | §4.2 medical rule | test-list.md (bold rule dropped) |
| T2 | Table max 1200 px; Test Name 420 px, Task 180, Configuration 200, Status 180, Date 140; the button column sits 24 px right of the table, top-aligned | H / M | §2.3 | §4.2 T11 | test-list.md layout |
| T3 | Header fill #E0E0E0, selected row #CFE2F1 | M / L | §2.2 | §4.2 H4 | no |
| T4 | Bold no longer marks Not done (the badge does) | M / L | §2.1 | §4.2 | yes (table rules) |
| T5 | Delete Test as a secondary button with the danger glyph; the dialog's Delete stays danger | L / L | §2.5 buttons | §4.2 H5 | no |
| T6 | "Back to Setup / recalibrate" as a tertiary button without the arrow character; empty state line sits inside the table frame with Add New Test beside it | L / L | §4 copy | §4.2 | test-list.md |

### 3.3 Add New Test dialog (03)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| A1 | Descriptions without em dashes (§4) | M / L | §4 | §4.3 | test-list.md modal |
| A2 | Heading 20 px, body 14, Add flat accent, focus ring on the list | L / L | §2.1, §2.5 | §4.3 | no |

### 3.4 Configuration page (05, 07, 09, 17)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| C1 | Column order by clinical weight: A = Test, Input, Target (or Icons); B = task card (Grid Layout / Motion / Icons count), Timing, Feedback; C = Dwell, Gaze Smoothing under a quieter "Advanced" group title in text-secondary | H / M | §2.3 | §4.4 T11 | task-config.md columns |
| C2 | Disabled-in-place controls: indicator:disabled rule, slider handle border-strong, spin fill #E0E0E0 with text-disabled | H / L | §2.5 forms | §4.4 H1/H4 | no |
| C3 | Sliders capped at 240 px for 10 steps or fewer (trials, icons, rows, cols) with ticks | M / L | §2.5 SliderSpinRow | §4.4 | no |
| C4 | "Modified from Standard" is a caption line reserved in the layout (always present, empty when unmodified) so the page does not shift | M / L | §2.1 caption | §4.4 H4 | no |
| C5 | Footer row centred under the three columns; Save & Continue flat accent | M / L | §2.5 buttons | §4.4 | task-config.md footer |
| C6 | Radio labels without em dashes: "Small (3°, about 124 px)" | M / L | §4 | §4.4 | task-config.md |
| C7 | Name dialog (18): heading 20 px, field 320 px | L / L | §2.5 dialogs | §4.4 | no |

### 3.5 Start page (11, 19)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| P1 | Blocker as a Blocked alert: danger glyph tile, bold "Blocked:", then one line per missing item at 16 px, Go to Setup as a secondary button inside the alert at its right edge, the alert 1200 px wide | H / M | §2.5 alerts, §2.1 body-large | §4.5 H1/H9 | start-test.md (list form) |
| P2 | Start is always the primary tier (disabled primary when blocked), Practice secondary, Cancel tertiary; the row sits directly under the card, left-aligned at the content edge | H / L | §2.5 buttons | §4.5 H4 | start-test.md |
| P3 | Card width 1200 px, read-aloud block in body-large on a white card, clinician block in body on the page (two surfaces, one anchor) | M / M | §2.3, §2.4 | §4.5 | start-test.md |
| P4 | Mouse note as a neutral alert with "No eye data will be recorded." in 600 | M / L | §2.5 alerts, §4 | §4.5 | no |
| P5 | The "Practice runs 3 targets" sentence appears once (clinician block); the help bar keeps its own sentence | L / L | §4 | §4.5 H8 | start-test.md |

### 3.6 Run screen and run bar (06, 08, 10, 20)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| R1 | Full screen during Practice, recorded runs and Preview: the dashboard window calls showFullScreen() when the run view is shown and showMaximized() when it is left, so the OS title bar and the taskbar leave the child's view (hub §8.1: legitimate) | H / L | §2.6 | §4.6, §5.7 | run.md already says "title bar hidden" |
| R2 | Run bar status: PRACTICE / PREVIEW chip, "Trial 3 of 3", tracking glyph + word | M / L | §2.5 run bar | §4.6 | run.md status line |
| R3 | Run bar buttons 36 px, border-strong | L / L | §2.5 | §4.6 | no |
| R4 | Canvas ladder of §2.6: flat target, two-tone shape outline, one on-target ring, halo arc, capped glow, 500 ms success, faint trail, 3.33:1 distractors and cells | H / M | §2.6 | §5.1-5.5, §5.8 | no (canvas is not wireframed) |
| R5 | Run-end dialogs (run-end.md): "Test Complete!" becomes "Test complete" at 20 px; danger buttons keep the danger fill; everything else unchanged | L / L | §2.5 dialogs, §4 | §4.6 | run-end.md copy |

### 3.7 Report Summary (13, 14)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| M1 | Hit circles map-hit-fill with ink digits; miss and skipped per §2.2 | H / L | §2.2 map | §4.7 clinical clarity | no |
| M2 | Scanpath overlay in one colour (map-overlay), dots 3 px, lines 1.5 px; the legend gains "Scanpath: fixations joined in time order, all trials"; per-trial colour lives in the Detailed view | H / L | §2.2 map | §4.7 | report-summary.md overlay note |
| M3 | Main column capped at 1100 px; Test Name 480 px, Evaluator 320 px; Eye Metrics table columns 320 + 320 px; Notes 84 px tall | H / M | §2.3 | §4.7 T11 | report-summary.md |
| M4 | Legend box white with border-subtle (no tint); table headers header fill | M / L | §2.2, §2.4 | §4.7 T6 | no |
| M5 | Title "Summary Results" without the colon, test name 20 px under it | L / L | §4 | §4.7 | report-summary.md title |
| M6 | Warning banner (early end, low gaze quality) per §2.5 with a warning glyph, not the Setup Display tint | M / L | §2.5 alerts | §4.7 | no |
| M7 | Vocabulary of the configuration rows per §4 | M / L | §4 | §4.7 H4 | report-summary.md rows |

### 3.8 Report Detailed (15)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| D1 | Two-line headers and 14 px tabular numbers so the 13 columns fit 1,370 px (about 105 px each) without a scrollbar; the Trial column stays frozen | H / M | §2.5 tables | §4.8 density | report-detailed.md header text |
| D2 | Outcome cell as a badge: Hit (success), Not selected (danger), Skipped (neutral); selected row by row-selected fill, not bold | H / L | §2.5 badges | §4.8 | report-detailed.md |
| D3 | Selected-trial map 720 x 405 px, fixation number badges at least 11 px; the legend sentence split into two caption lines | M / L | §2.2 map, §2.1 | §4.8 | no |

### 3.9 PDF (16, report_pdf.py)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| F1 | Body 9.5 pt, trial table 8 pt, definitions 8.5 pt | M / L | §2.1 (print) | §4.9 | no |
| F2 | Map marks and legend per §2.2 (the map image is painted by the same code, so M1 covers it); table headers header fill with ink text (13.71:1), replacing the teal tint | M / L | §2.2 | §4.9 | no |
| F3 | Eye Metrics table before the forced page break so page 1 is not 40 % blank; the map and its legend start page 2 as today | L / L | §2.3 | §4.9 | report-summary.md footer note |
| F4 | Date as yyyy-MM-dd HH:mm; title "Summary Results, <test name>"; empty fields print "none" instead of a lone dash | L / L | §4 | §4.9 | no |

### 3.10 Task-settings dialog (task-settings.md, standalone `--task X --gui` only)

| # | Change | Impact / effort | Rule | Finding | Wireframe |
|---|---|---|---|---|---|
| K1 | Radio groups instead of combo boxes for size, gap and path; the shrink hint as a warning alert line, not a pill | L / M | §2.5 radio groups, alerts | §4.10 | task-settings.md |

Priority order across pages, by impact per effort: S1, R1, C2, M1, M2, T1, P1, P2, D2 first; then S2,
T2, M3, C1, R4; then the rest.

## 4. Copy rules

1. **No em dash in any label, option or sentence.** Use a colon for a definition, a comma or
   parentheses for a qualifier, a full stop between sentences.
2. **One date format everywhere:** `yyyy-MM-dd` for dates, `yyyy-MM-dd HH:mm` (24-hour) when a time
   is shown. Setup's QDateEdit gets `setDisplayFormat("yyyy-MM-dd")` (it already stores that form,
   hub §8.9); the Test List already prints it; `report_format.started_text` changes from
   "Oct 7, 2026 5:09 PM" to "2026-10-07 17:09"; the PDF file name is already ISO.
3. **One vocabulary:** the configuration page is the source of truth, because the clinician sets the
   value there; the report and the PDF repeat its words. Units follow the value, not the label.
4. **No interpunct chains.** Facts are separate elements (chip, text, badge) or separate sentences.
5. **Status words are nouns or past participles, never exclamations:** "Test complete", "Blocked",
   "Not done".
6. **A page title names the object and has no colon:** "Summary Results", "Detailed Results".

Exact replacements (current strings quoted with the em dash written as [dash]):

| Where | Today | Proposed |
|---|---|---|
| Config, size radios (05, 07, 09) | "Small [dash] 3° (≈124 px)" | "Small (3°, about 124 px)" |
| Config, cell gap (09) | "Wide [dash] 1° (≈41 px)" | "Wide (1°, about 41 px)" |
| Config, Selection (05) | "Dwell [dash] keep looking at the target" | "Dwell: keep looking at the target" |
| Config, Selection (05) | "Switch [dash] look at the target, then press the switch" | "Switch: look at the target, then press the switch" |
| Config, motion (07) | "Diagonal ↘ (top-left ↔ bottom-right)" | "Diagonal, top-left to bottom-right" |
| Config, "Modified from "Standard"" (17) | | "Changed from Standard" |
| Add dialog (03) | "One still target on an empty field [dash] baseline look-and-select." | "One still target on an empty field. Baseline look and select." |
| Add dialog (03) | "One cell of a visible 3x3 board lights up [dash] selection among candidates." | "One cell of a visible board lights up. Selection among candidates." |
| Add dialog (03) | "The target travels; select it while it moves [dash] smooth pursuit." | "The target travels across the screen. Smooth pursuit." (Follow the Target wording) |
| Add dialog (03) | "Find the cued shape in a 2D field of distractors [dash] visual search." | "Find the cued shape among other shapes. Visual search." |
| Setup (01) | "Display: 1920x1080 at 100% scale [dash] recommended standard." | "Display 1920x1080 at 100 %: the recommended standard." |
| Start (19) | "Mouse test [dash] the tracker is not connected, so no eye data will be recorded." | "Mouse test. The tracker is not connected, so no eye data will be recorded." |
| Start (11) | "Still needed before you can start: The tracker is not connected. Connect it on the Setup page. · No calibration yet. ..." | "Blocked: " then one line per item: "The tracker is not connected (Setup page)." / "No calibration yet (Setup page)." / "Sex is not selected (Setup page)." |
| Run bar (06) | "PREVIEW · Trial 3/3 · mouse pointer · nothing is recorded" | chip "PREVIEW" + "Trial 3 of 3" + "Mouse pointer" (the chip itself means not recorded) |
| Run bar (20) | "PRACTICE (not recorded) · Trial 1/3 · mouse pointer" | chip "PRACTICE" + "Trial 1 of 3" + "Mouse pointer" |
| Run bar (run.md) | "Trial 4/18 · tracking OK" | "Trial 4 of 18" + badge "Tracking OK" |
| Report title (13) | "Summary Results:" | "Summary Results" |
| Report row (13) | "Maximum time per trial" | "Trial timeout" |
| Report row (13) | "Pause between trials" | "Inter-trial interval" |
| Report row (13) | "Trials (planned)" | "Number of trials" (planned count; the footnote already states presented vs planned) |
| Report row (13) | "Feedback: Sound on, sparkle on" | "Feedback: Hit sound on, miss sound on, glow off" (one on/off per Feedback check box the page shows; "sparkle" has no control on the page, so it is not reported) |
| Report row (13) | "Gaze cursor shown: Yes" | "Gaze cursor: Shown" / "Hidden" |
| Report row (13) | "Gaze smoothing: Smoothing α 0.22, jitter tolerance 40 px" | "Gaze smoothing: On, alpha 0.22, jitter tolerance 40 px" |
| Report row (13) | "Target size: Medium (5°), 103 px radius" | "Target size: Medium (5°, 207 px)" (diameter, as the page shows) |
| Report row (13) | "Selection: Dwell 0.8 s, refractory 0.5 s" | "Selection: Dwell, threshold 0.8 s, refractory 0.5 s" |
| Report, detailed line (15) | "Scan path 75.4 deg · 8 fixations · 32 saccades" | "Scan path 75.4°, 8 fixations, 32 saccades" |
| Run end (run-end.md) | "Test Complete!" | "Test complete" |
| Test List (04) | "← Back to Setup / recalibrate" | "Back to Setup" (recalibration is on that page) |
| Empty value, screen and PDF | a lone em dash character | "none" in text cells; the em dash stays only inside numeric table cells, where a word would misalign the column |

## 5. Implementation path in Qt

### 5.1 QSS token port vs a widget library

| Path | Licence | Effort | Risk | Verdict |
|---|---|---|---|---|
| QSS token port (keep PySide6 widgets, rewrite `wtmh_theme.py` around tokens) | none new | 4 SPEC steps | low: QSS quirks are known and documented in the file (PNG arrows, combo popup frame, focus rect); object names and the qt-mcp harness stay | **recommended** |
| PySide6-Fluent-Widgets | GPLv3 (allowed) | every page rebuilt | high: widget classes change, 2,480 tests and the qt-mcp object names touched; theme engine owns colours, so AA tuning fights the library; no help for the canvas, the map or the PDF | no |
| Fluent-Qt | MIT | as above plus bindings | higher: young project | no |

### 5.2 Phases (each one SPEC step; order matters, later phases use earlier tokens)

**Phase 1: tokens, type, copy.** Files: `wtmh_theme.py` (token table and QSS rewritten; alerts,
badges, buttons, tables, forms, SliderSpinRow, `:disabled` indicators, `:focus` rules),
`dialog_theme.py` (imports the new tokens), `run_dialogs.py` (danger tier from the token),
`run_bar.py` (chip, 48 px, tokens), `dashboard_window.py` (application font 14 px, next to the Fusion
call), `setup_page.py` (date display format), `report_format.py` (`started_text`, trial line),
`report_config.py` (row labels and values of §4), the label strings in `config_form.py`,
`add_test_dialog.py`, `start_test_page.py`, `test_list_page.py`, `task_info` texts.
Acceptance: every pair of §2.2 recomputed from the code's hex values passes; a grep of `src/ui` and
`src/data` for the em dash character finds only `DASH`; the application font is 14 px and page titles
28 px; Tab from Subject ID shows a visible focus on every control (live check, answers §6.2); a
disabled checked box is grey; dates read yyyy-MM-dd on Setup, Test List, report and PDF.

**Phase 2: components and page layout.** Wireframe gate first (setup.md, test-list.md,
task-config.md, start-test.md, run.md, run-end.md as marked in §3). Files: `setup_page.py`,
`test_list_page.py`, `config_form.py`, `task_config_page.py`, `start_test_page.py`,
`add_test_dialog.py`, a small status-badge helper (painted glyph + word), `run_bar.py` status parts.
Acceptance: content widths and field widths of §2.3 measured on the maximized window (not offscreen);
status badges in the Test List, Setup and the run bar show glyph + word; the Start page's Blocked block
lists items one per line with Go to Setup inside it; Start keeps its tier when disabled; the
configuration page's "Changed from Standard" line does not move the layout; no left stripes remain.

**Phase 3: canvas and run.** Files: `canvas.py` (flat fill, two-tone outline via `shape_path`, one
on-target ring, halo arc, glow cap and radius, success flash and particles, trail), `canvas_shapes.py`
(an offset-path helper), `configs/themes/forest.yaml` and `space.yaml` (new keys: `target_outline`,
`distractor`, `cell_outline`, `on_target`, `success`, `glow`; `character` removed), `dashboard_window.py`
(full screen while the run view shows). Acceptance: the ratios of §2.6 recomputed from the YAML; a
screenshot of each scene (single, grid, icons with square and triangle cued, moving) shows the outline
following the shape; the glow on an 8-icon field stays clear of the neighbours; success is visible for
500 ms in a frame capture; no title bar or taskbar in a run capture; Alt-P, Alt-Q, Esc, H unchanged;
the user as subject confirms the ladder on the real device.

**Phase 4: report and PDF.** Files: `target_map_paint.py` (marks, overlay colour, slot and path
colours, label sizes), `map_legend.py` (white box, overlay entry), `report_views.py` and
`report_page.py` (widths, Notes height, two-line headers, Outcome badge), `report_tables.py`,
`report_pdf.py` (sizes, header fill, block order, title, date). Acceptance: map digits 13.63:1 by
computation; a Summary capture with Scanpath on reads the trial numbers; the Detailed table shows 13
columns without a horizontal scrollbar at 1920x1080; the PDF's page 1 holds header, configuration,
summary and eye metrics; its labels equal the configuration page's by a string test over
`report_config.build_config_rows`.

**Phase 5 (optional): standalone dialog parity.** `task_settings_dialog.py` radio groups and the hint
line (§3.10). Acceptance: the same object names and values as today; one grammar with the page.

## 6. Hub-check answers (Task A §8.4, §8.5, §8.6) and limits

1. **§8.4 Hit character.** `character: butterfly` (forest) and `character: star` (space) are read
   nowhere: a search of `src/` for "character" finds only name-validation text. The key is dead and
   is removed in phase 3; wiring it would be a new feature and is not proposed.
2. **§8.5 Focus rectangle.** The dashboard installs Fusion (`dashboard_window.py:165`) and the QSS
   has no `:focus` rule for buttons, radios or check boxes and no `outline` property. Under a style
   sheet a button with a box rule draws its focus frame from the sheet's `outline`, so the expectation
   is no visible focus on those controls; this cannot be confirmed without the app and is the first
   live check of phase 1. Phase 1 adds explicit rules either way.
3. **§8.6 Glow footprint.** With 8 icons in the grid arrangement shrunk to about 202 px: drawn radius
   101 px, hit radius 129 px (ICON_DRAW_FRAC 0.78), centre distance about 230 px. Today's glow reaches
   r + max(28, 0.6 r) = 162 px, the neighbour's drawn edge is 128 px away, so the halo covers 34 px of
   the neighbour at alpha about 100, and 62 px of the neighbour's hit area. Hence the cap in §2.6:
   outer radius r + 0.3 r, and never more than half the distance to the nearest slot.
4. **Limits.** No ratio here was measured on a rendered frame; anti-aliasing and the radial gradient
   removal change edge pixels slightly. The PDF was judged from code and Task A. Nothing in this file
   changes until a SPEC written from it is approved.

## 7. Files read

`docs/design/fable-brief.md`, `fable-evaluation.md`, `ai-ish-research.md`,
`current-design-inventory.md`; screenshots 01-20 (16 by description); `docs/wireframes/_nav.md`,
`setup.md`, `test-list.md`, `task-config.md`, `start-test.md`, `run.md`, `run-end.md`,
`report-summary.md`, `report-detailed.md`, `task-settings.md`; `src/ui/wtmh_theme.py`,
`dialog_theme.py`, `canvas.py`, `canvas_shapes.py`, `canvas_cursor.py`, `run_bar.py`,
`run_dialogs.py`, `report_pdf.py`, `report_format.py`, `target_map_paint.py`, `map_legend.py`,
`slider_spin.py`; `src/data/report_config.py`; `src/engine/target_size.py`; object names and sizes
of `setup_page.py`, `task_config_page.py`, `config_form.py`, `test_list_page.py`,
`start_test_page.py`, `report_page.py`, `add_test_dialog.py`, `config_save_dialogs.py`,
`report_tables.py`, `report_views.py`, `dashboard_window.py`, `src/tasks/scanning.py`;
`configs/themes/forest.yaml`, `space.yaml`; `docs/specs/SPEC-compass-task-flow.md` §1-§3;
`docs/compass/synthesis/ui-ux-screen-walkthrough.md` §2, §5, §6.
