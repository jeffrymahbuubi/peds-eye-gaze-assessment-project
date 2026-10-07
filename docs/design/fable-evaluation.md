# Fable UI/UX evaluation (Task A)

Written 2026-10-08 by the Fable evaluator against tree `c300411` (branch feature/compass-task-flow).
Material: `docs/design/fable-brief.md`, `ai-ish-research.md`, `current-design-inventory.md`,
screenshots 01-20 and the PDF, every file in `docs/wireframes/`, the theme and canvas code
(`src/ui/wtmh_theme.py`, `dialog_theme.py`, `canvas.py`, `canvas_cursor.py`, `canvas_shapes.py`,
`run_bar.py`, `report_pdf.py`, `target_map_paint.py`, `configs/themes/forest.yaml`), SPEC-compass-task-flow.md
§1-§3 and the Compass walkthrough. Contrast ratios are WCAG 2.2 relative-luminance ratios computed
from the hex tokens; px values are read from the QSS or measured on the 1920x1080 captures.
Nothing here was tested on the running app.

## 1. Executive summary

1. **The layout ignores the workflow (T11) on every operator page.** Content is stretched to the full
   1920 px with equal-weight boxes: a 1,730 px Subject ID field (01), a 1,290 px Test Name column with
   the action buttons 1,250 px away from the rows (04), eight identical cards for a form whose three
   clinical choices sit beside engineering parameters (05/09), a report whose right 500 px are empty
   while its Notes box is 190 px tall (13). No page has a visual anchor.
2. **State is carried by pastel tint and font weight only.** The Start-page blocker, the most important
   line on that page, is a 12 px line on the palest fill with a 1.99:1 stripe (11); Done vs Not Done
   differs by bold alone (12); a disabled slider handle is 1.27:1 against white and a disabled check box
   keeps its full teal fill (17). Medical-software practice asks for unmistakable status.
3. **Measured accessibility gaps.** White text on the primary button's light gradient end is 2.79:1,
   DANGER badge text 3.77:1, SUCCESS badge 3.37:1, slider fill vs groove 2.20:1, map trial numbers on
   hit circles about 2.0:1, body text 12 px everywhere. Three state stripes are 1.88, 1.99 and 2.97:1.
4. **The canvas feedback hierarchy is inverted for the child.** Being on the target is loud (white ring +
   dark-green ring + green glow, 20) while success is quiet (eight 6 px dots at 2.10:1 for about 0.3 s).
   The red target on the mint field is a red/green pair at 2.84:1 luminance; the white ring is 1.12:1
   against the field, so on the square, triangle and diamond it half-vanishes (06). The Follow trail is
   brighter than its own target while the target is not selectable (08). The OS title bar and the
   Windows taskbar stay on screen during a run (06, 08).
5. **The copy is the strongest AI tell.** At least 20 em-dash labels across the pages, interpunct chains
   ("PREVIEW · Trial 3/3 · mouse pointer · nothing is recorded"), three date formats (10/8/2026,
   2026-10-07, Oct 7, 2026 5:09 PM), and three vocabulary mismatches between the configuration page and
   the report ("Inter-trial interval" vs "Pause between trials", "Trial timeout" vs "Maximum time per
   trial", "Glow on target" + "Play hit sound" vs "Sound on, sparkle on").

**Verdict.** The app is coherent and usable: one palette, one stylesheet, honest disabled states, a clear
page flow, good run-bar distinctness (amber practice bar, coloured tracking words at 4.2-5.1:1). But it
is generic: five tells are strong (T2, T3, T5, T6, T11), two mild (T1, T7). Pages score 3 on average;
the canvas and the report score lowest on clinical clarity. **Task B should prioritise, in order:** a
type scale and AA-checked state tokens (fixes 2 and 3 at once); one anchor and a content width per page
(fix 1); a status component with glyph + word for Test List, Setup, Start and the run bar; a canvas
feedback ladder (cue < on-target < success) and theme contrast rules; copy rules (no em-dash labels,
one date format, one vocabulary shared by configuration, report and PDF).

## 2. Measurements used below

### 2.1 Contrast ratios (WCAG 2.2; AA text 4.5:1, large text and UI components 3:1)

| Pair (foreground / background) | Ratio | AA |
|---|---|---|
| INK #122B3A / PANEL_BG #FFFFFF, / BACKGROUND #F5F9FB | 14.66, 13.84 | pass |
| MUTED #5C7684 / white, / BACKGROUND, / SOFT_ACCENT | 4.79, 4.53, 4.07 | pass, pass, **fail** |
| TITLEBAR_TEXT #CFE6EE / TITLEBAR_BG #12374A | 9.70 | pass |
| white / ACCENT_GRADIENT_START #2FA8C4 (left half of every primary button) | **2.79** | **fail** |
| white / ACCENT_GRADIENT_END #1A6F95, white / ACCENT #1F7A9C | 5.60, 4.86 | pass |
| SOFT_ACCENT_TEXT #0F5670 / SOFT_ACCENT #DCF0F5 (table headers) | 6.89 | pass |
| INK on info / warning / success fills | 12.44, 12.99, 12.94 | pass |
| DANGER #E15353 / white; DANGER / #FBE7E7 (danger badge, 11 px) | **3.77**, **3.18** | **fail** |
| white / SUCCESS #2F9E6E (success badge, 11 px); SUCCESS / white | **3.37** | **fail** |
| Stripe BANNER_BORDER / SOFT_ACCENT; WARNING_BORDER / WARNING_BG; SUCCESS / #E3F5EC | **1.88, 1.99, 2.97** | **fail** (3:1) |
| DISABLED_TEXT #6F808A / DISABLED_BG #E9EDF0 | 3.48 | exempt |
| CONTROL_BORDER #7B93A1 / white; card BORDER #DBE6EC / white | 3.22, 1.27 | pass, decorative |
| Slider fill #2FA8C4 / groove #DBE6EC; slider handle disabled #DBE6EC / white | **2.20**, **1.27** | **fail** |
| Focus border ACCENT / white (1 px) | 4.86 | pass, but 1 px |
| Run bar text #122b3a / grey #e9eef1, / amber #fbe3b0 | 12.54, 11.67 | pass |
| Run bar OK #1e7a53, WARN #8a5a00, ERROR #c0392b on grey / amber | 4.53/4.22, 5.07/4.72, 4.65/4.33 | pass |
| Run bar button border #b8c7cf / white | **1.73** | **fail** (3:1) |
| Map: white digits / hit circle (SUCCESS at alpha 150 over white, about #85C6AA) | **about 2.0** | **fail** |
| Canvas: target #ff5252 / field #e8f5e9 | **2.84** | **fail** (3:1) |
| Canvas: white ring / field; white ring / target | **1.12**, 3.19 | **fail**, pass |
| Canvas: cursor_color #1b5e20 (rings, Paused) / field; / target | 7.00, 2.47 | pass, fail |
| Canvas: glow and particles #66bb6a / field | **2.10** | **fail** |
| Canvas: grid cell outline (cursor_color alpha 38) / field; distractor (alpha 64) / field | **1.26**, **1.48** | **fail** |
| Canvas: unselectable target (darker 180, about #8e2d2d) / field | 7.28 | pass |

### 2.2 Sizes

| Element | Value | Source |
|---|---|---|
| Body, labels, table cells, footnotes | 12 px (Qt default 9 pt Segoe UI; no font set) | QSS, 01-15 |
| Badges 11 px; run bar 13 px; read-aloud 15 px; card titles 16 px; Start headings 17 px; dialog heading 20 px; page title 22 px | eight sizes, no scale | QSS, start_test_page, run_dialogs |
| Primary / ghost button height | about 32 px (8 px + line + 8 px); run bar buttons about 28 px | QSS, 06 |
| Check box indicator 15 px; radio indicator 14 px; slider handle 14 px; spin arrows 18 x about 15 px | all under the 24 x 24 px WCAG 2.5.8 minimum | QSS |
| Target diameters Small / Medium / Large | 3 / 5 / 8 deg = 124 / 207 / 331 px at 650 mm | 05 |
| Rings around a Medium target (r = 103 px) | white r+4 at 4 px; instant r+10 at 5 px; dwell arc r+16 at 8 px; glow out to r+62 px | canvas.py |
| Gaze cursor | ring radius 5 px, core 2 px, halo 5 px: about 15 px = 0.4 deg | canvas_cursor.py |
| Hit particles | 8 dots, 6 px radius, 20 frames (about 0.33 s at 60 Hz), alpha fading from 255 | canvas.py |
| Follow trail | up to 90 samples, radius up to 0.34 r, alpha up to 120 | canvas.py |

## 3. AI-ish tells across the app

| Tell | Present | Where (screenshot / file) |
|---|---|---|
| T1 type | Partly | Segoe UI default; eight sizes with no scale; body 12 px on every page (01-15) |
| T2 gradient | **Yes** | Every primary button: Connect (01), Add (03), Run Test (04), Save & Continue (05/09/13), Save (18), Start (19); radial gradient targets (06/10/20) |
| T3 cards on cards | **Yes** | Setup: 4 stacked cards + a banner inside a card (01); config: 8 cards, same 8 px radius and padding (05/07/09); Start: one 1,870 x 700 px card, about 70 % empty (11/19); report: table frame, map frame, tinted legend box (13/14) |
| T4 identical rows | Mild | Add New Test: four "bold title + one line" rows (03) |
| T5 coloured left stripe | **Yes** | 7 instances: Display success (01), tracker note (01), blocker (11), help bar (11/19), mouse note (19); stripes at 1.88-2.97:1 so they also fail to carry the state |
| T6 pastel state tints | **Yes** | info #DCF0F5, warning #FBF0DC, success #E3F5EC with the same INK text; table headers and the selected Test List row in the same SOFT_ACCENT (04); legend box tint (14) |
| T7 glow / shadows | Mild | OS dialog shadow (03, 18); radial target gradient; the Switch glow halo (20, functional) |
| T8 emoji / generic icons | No | No iconography at all except the logo and legend marks; status is words only |
| T9 all-caps labels, centred hero | No | "PREVIEW" / "PRACTICE" caps carry meaning (06, 20); "1 · Setup" interpunct numbering and interpunct chains are a related tic |
| T10 motion | No | None in the operator UI |
| T11 workflow-blind layout | **Yes** | Full-width fields (01), detached button column (02/04/12), equal-weight cards (05/09), empty card (11), blank right third (13/15), 2-column Eye Metrics table 1,370 px wide (14) |
| Copy tells (not in T1-T11 but named by the research as the text equivalent of T5) | **Yes** | Em-dash labels: 5 on 05, 7 on 09, 4 on 03, 1 each on 01/19/11; interpunct chains on 05, 06, 13, 19; "Summary Results:" / "Detailed Results:" trailing colons (Compass copy) |

## 4. Page by page

Severity: **critical** = can cause a wrong clinical action or lose data; **major** = slows or misleads
the clinician under split attention, or fails AA on a primary element; **minor** = polish.

### 4.1 Setup (01-setup-empty.png; wireframe setup.md)

Tells: T2 (Connect), T3 (four cards, banner in a card), T5 (two stripes), T6, T11 (full-width fields).

- **Major, H1 visibility.** "Continue to Tests" is disabled with no reason shown. The only state text is
  "Not connected." (plain, 12 px, under Connect) and "No tracker connected: only Mouse tests can run."
  which reads as permission to continue. The wireframe's Session / Tracker / Calibration badges and the
  "No calibration yet" alert are not on the screen (region: top right and the Calibration card).
- **Major, T11 / H8.** Subject ID (about 10 characters) is a 1,730 px field; Point Count (1-9) is a
  1,700 px spin box; the Continue button is 1,870 px wide and reads as a banner. Field width should
  hint at content length (NHS form rule).
- **Minor, H4.** Date reads "10/8/2026"; the Test List shows "2026-10-07"; the report shows
  "Oct 7, 2026 5:09 PM". Three formats.
- **Minor.** In the Calibration card the card's own action, Do Calibration, is the weakest button
  (disabled grey) beside an enabled ghost Load Calibration File; no state line says why.
- **Minor.** The Display card holds one line inside a stripe inside a card (T3 + T5 in 60 px of height).
- Accessibility: all text passes except the stripe (2.97:1); focus on fields is a 1 px border change.

### 4.2 Test List (02, 04, 12; wireframe test-list.md)

Tells: T2 (Run Test), T6 (header and selected row both SOFT_ACCENT), T11.

- **Major, H8 / T11.** Test Name column about 1,290 px for 15-character names; the four data columns
  are squeezed into the right 400 px; the six buttons float at y 430-675 while the table starts at
  y 140, so row 1 to Run Test is about 1,250 px (04). In the empty state (02) the hint "No tests yet.
  Choose Add New Test." sits top-left and the button 1,600 px to the right.
- **Major, medical status rule.** Status is a word in a table cell; Not Done differs from Done by bold
  only (12). "Ended early (4/6)" and "Done · data missing" (wireframe) will be plain text too. Under
  split attention the clinician needs a glyph or colour plus the word.
- **Minor, H4.** The selected row (04, row 4) uses the same #DCF0F5 as the header row, so the selection
  reads as a second header.
- **Minor, H5.** Delete Test is styled exactly like Copy Test (both ghost); the confirmation dialog
  carries the whole burden.
- **Minor.** "← Back to Setup / recalibrate" as a ghost button plus "Changes are saved automatically."
  at 12 px muted is fine; the arrow glyph in a button label is a template habit.

### 4.3 Add New Test dialog (03; test-list.md modals)

Tells: T4 (four identical rows), T7 (OS shadow), em-dashes in all four descriptions.

- **Minor.** 507 x 430 px dialog, white list, selected row in SOFT_ACCENT: clear. "How many" spin at
  70 px is the first correctly sized field in the app.
- **Minor, H6.** No default-task hint and no keyboard hint; the task list shows no focus ring in the
  capture (cannot verify).
- Accessibility: Add button text on the gradient's left half 2.79:1.

### 4.4 Configuration page (05 scanning, 07 follow, 09 grid, 17 mouse + switch; wireframe task-config.md)

Tells: T2 (Save & Continue), T3 (eight cards, one radius, one padding), T11 (equal weight), em-dashes
in every size, gap and selection label.

- **Major, T11 / H8.** Eight cards of equal size and weight. The three clinical choices (Pointer and
  Selection, Target size, Number of trials) sit beside Jitter tolerance and Smoothing alpha, which are
  engineering parameters. Input, the first thing a clinician decides, is the last card in reading order
  (top right). The grid uses 1,530 px of 1,920 and the bottom 250 px are empty (05).
- **Major, H1 / H4, greyed in place (17).** A disabled "Show dwell progress ring" keeps its full teal
  check; only the label turns MUTED (4.79:1 vs 14.66:1 for enabled). The disabled Dwell threshold
  slider's handle is #DBE6EC on white, 1.27:1, effectively invisible; its spin box text is MUTED on
  #E6EDF1 at 4.05:1. Disabled is not unmistakable.
- **Minor, H4.** The "Modified from Standard" line (17) inserts 24 px and pushes Reset to defaults and
  everything below it down; the footer stays, so the page shifts on a state change.
- **Minor.** Sliders are 370 px long for values with 3-9 meaningful steps (Number of icons, Grid rows);
  the slider fill is 2.20:1 against its groove.
- **Minor, H4.** Follow (07) still shows a Selection window and a Dwell card; per the wireframe the
  Follow page becomes Pointer-only with "Trial duration". The wireframe's amber "will be shrunk" hint is
  not in any capture (cannot judge).
- **Minor.** Footer Preview / Save & Continue / Cancel is left-aligned under column A while the content
  is three columns wide; Compass centres the footer row.
- Name dialog (18): 440 x 180 px, one sentence, one field, Save primary. Fine. The wireframe's
  "Configuration exists" and "Load configuration" dialogs follow the same pattern.

### 4.5 Start page (11 blocked, 19 mouse; wireframe start-test.md)

Tells: T3 (one giant card), T5 (blocker and help stripes), T6, T11 (70 % empty card).

- **Major, H1 / H9, medical alert rule.** The blocker (11) joins three missing items into one 12 px
  line on the palest fill with a 1.99:1 stripe; its Go to Setup button is 1,750 px to the right of the
  text; the disabled Start and Practice buttons are 770 px below the reason. The page's only decision
  depends on this line and it is the least visible element on it.
- **Major, H4.** When blocked (11) Start, Practice and Cancel are three identical grey buttons; when
  allowed (19) Start is the gradient primary. The primary action changes appearance with state, so the
  clinician cannot learn its place.
- **Minor.** The mouse note (19) "no eye data will be recorded" is a consequence the clinician must not
  miss; it has the same weight as the help line at the bottom.
- **Minor, H8.** The "Practice runs 3 targets" sentence appears twice on the page (clinician block and
  help bar).
- **Minor.** The read-aloud block at 15 px is the right anchor idea; it still shares colour and weight
  with the clinician block, so under split attention the eye has to re-find it.

### 4.6 Run screen and run bar (06, 08, 10, 20; wireframes run.md, run-end.md)

Operator side:
- **Good.** Amber bar for Preview and Practice vs grey for a recorded run; tracking words coloured and
  worded (4.2-5.1:1); buttons NoFocus so Space stays the switch; Alt-P / Alt-Q in the labels.
- **Major, child-facing.** The OS title bar with minimise / close is on screen in every run capture, and
  the Windows taskbar with about 25 coloured icons is visible in 06 and 08. The wireframe says the title
  bar is hidden. Whether the run is full screen is for the hub to check (§7).
- **Minor.** Run bar button border 1.73:1 against white; buttons about 28 px tall.
- **Minor.** The status chain "PREVIEW · Trial 3/3 · mouse pointer · nothing is recorded" is four facts
  in one 13 px line; the mode word is the one that matters and is not bigger than the rest.
- Run-end dialogs (wireframe only): Save default, danger variant on Discard and Quit test, Esc = Save.
  Correct error prevention. Heading 20 px bold. The dialogs are modal over the child's frozen canvas,
  which is inherent to a single-screen setup. "Test Complete!" with an exclamation is Compass copy.

Canvas findings are in §5.

### 4.7 Report, Summary (13, 14; wireframe report-summary.md)

Tells: T2, T6 (tinted headers and legend box), T11 (fixed 450 px sidebar, blank right 500 px).

- **Major, T11 / H8.** Test Name is a 1,550 px field; the Notes box is 190 px tall; the Eye Metrics
  table is two columns stretched to 1,370 px with a 1,170 px Value column (14); the right third of the
  page is empty while the map is 875 px.
- **Major, clinical clarity.** Target Map (13): white trial numbers on the green hit circles are about
  2.0:1; the scanpath draws 124 fixations as 4.5 px dots in a six-colour cycle, so each colour is reused
  three times over 18 trials and no legend maps colour to trial. The map is not readable at a glance; it
  is readable only by toggling Scanpath off.
- **Minor, H4.** Three label pairs differ from the configuration page: "Maximum time per trial" vs
  "Trial timeout (s)"; "Pause between trials" vs "Inter-trial interval (s)"; "Sound on, sparkle on" vs
  "Play hit sound" / "Glow on target" ("sparkle" exists nowhere on the configuration page).
- **Minor.** "Summary Results:" with a trailing colon as a page title (Compass copy).
- **Minor.** The warning banner for an early end or low gaze quality (wireframe) will use the same pale
  WARNING_BG as the Setup Display card, which is a success state elsewhere in tone.

### 4.8 Report, Detailed (15; wireframe report-detailed.md)

- **Major, density.** 13 columns at 12 px with a horizontal scrollbar already at 1,500 px (the "Pupil
  chan..." header is clipped). The wireframe adds Clicks and Click errors for Switch (15 columns) and a
  14-column Follow table. Outcome "Hit" / "Not selected" is text only.
- **Minor.** The selected-trial map is 560 x 280 px inside a 1,370 px column; its numbered fixation
  circles have about 8 px digits. The legend sentence under it is 12 px, one line, 1,150 px long.
- **Minor.** Selected row = bold, same device as Not Done in the Test List (bold means two things).

### 4.9 PDF (16-report-pdf-grid.pdf; report_pdf.py)

- **Major, data labelling.** The PDF title is "Summary Results: 2026-10-07_P9REAL_click_grid_run1", the
  run folder slug, while the screen (13) shows "Grid Click 1". A clinician's printout must carry the
  test name. Hub to check whether this capture predates the test-name parameter (§7).
- **Minor.** Page 1 ends about 40 % blank because the map forces a page break; page 3 holds 8 trial rows
  and the definitions. Trial table at 7.5 pt, body 8.5 pt, definitions 7.5 pt: small for A4.
- **Minor.** Map digits on green at about 2.0:1 will print worse than they display. Teal table headers
  are consistent with the screen (good).
- **Minor.** Evaluator and Notes print a lone dash character as "empty"; consistent with the screen.

### 4.10 Wireframe-only pages

- `task-settings.md` (standalone `--task X --gui` only): combo boxes where the configuration page uses
  radios, and warning pills for the shrink hint. Two visual grammars for the same settings (H4); low
  priority because the dashboard path is the clinical one.
- `results.md`, `tasks.md`: superseded; no finding.
- `run.md` states: Paused draws "Paused" in #1b5e20 at about 70 px on the mint field (7.0:1). A word
  the child may not read; neutral for the child, clear for the operator.

## 5. Canvas findings for the child (06, 08, 10, 20; canvas.py, forest.yaml)

1. **Target vs field is a red/green pair at 2.84:1 luminance.** #ff5252 on #e8f5e9 relies on hue, the
   pair most affected by colour-vision deficiency (about 8 % of boys) and the least useful for a child
   with cerebral visual impairment, which is common in CP. The radial gradient lightens the centre to
   about 2.47:1. (Major.)
2. **The white selectable ring is 1.12:1 against the field.** It reads only where it crosses red. On the
   circle it is a rim; on the square (06, top right) it is a circle inscribed in the square, touching the
   edge midpoints; on a triangle or diamond most of it would lie over mint and vanish. The brief's
   question is answered: the circular ring on non-circular shapes is both geometrically wrong and
   invisible where it leaves the shape. (Major.)
3. **On-target feedback is louder than success.** Under Dwell with defaults, three rings stack at r+4,
   r+10 and r+16 (white 4 px, dark green 5 px, dark green 8 px arc); the instant ring and the arc are the
   same colour 6 px apart, so the arc is indistinguishable from the ring until it has swept. Under Switch
   (20) the glow halo (#66bb6a, alpha 200 at the edge, out to r+62 px on a Medium target) and the dark
   ring say the same thing twice in one hue. Success is eight 6 px green dots at 2.10:1 for 0.33 s plus
   a sound; the theme's "character: butterfly" is not read by `canvas.py`. For a child the ladder should
   be cue < on-target < success; today it is on-target > cue > success. (Major.)
4. **Follow (08): the trail outshines the target.** Outside the selection window the target is darkened
   (about #8e2d2d) while the trail keeps the bright #ff5252 at alpha up to 120 and up to 0.34 r wide
   over 90 samples (about 900 px long in 08). The brightest thing on screen is where the target was,
   not where it is. (Major.)
5. **Distractors and cells are near-invisible.** Scanning distractors at 1.48:1 (06), grid cells at
   1.26:1 (10). Deliberately dim, but for low vision the "board" the Grid task is meant to show (SPEC
   S3.3) is not visible, and in Scanning the search set is barely a set.
6. **Gaze cursor** is about 15 px (0.4 deg): legible by its dark halo (measured in the SPEC), small
   enough not to occlude. Fine. A visible cursor can invite chasing; it is a configuration choice, so no
   finding beyond noting that "Show gaze cursor" defaults on.
7. **Chrome in the child's view.** OS title bar in every run capture; taskbar in 06 and 08. (Major; see
   §7.)
8. **Timing and intensity.** Hit particles 0.33 s; glow appears and disappears with on_target with no
   ramp; no motion elsewhere. Calm, as the brief wants; the issue is intensity order, not motion.

## 6. Accessibility summary

- **Text contrast.** Body and headings pass (12.4-14.7:1). Fails: white on the gradient's light half
  (2.79), DANGER badge (3.18 / 3.77), SUCCESS badge (3.37), MUTED on SOFT_ACCENT (4.07), map digits
  (about 2.0). Disabled text 3.48 is exempt but close to invisible against enabled text's 14.66.
- **Non-text contrast (1.4.11).** Fails: three stripes (1.88-2.97), slider fill (2.20), disabled slider
  handle (1.27), run bar button border (1.73), canvas target (2.84), white ring on field (1.12), glow
  (2.10), cells (1.26), distractors (1.48). Passes: control borders (3.22), focus border (4.86), nav
  underline (4.50), tracking words (4.2-5.1).
- **Target sizes (2.5.8, 24 x 24 px).** Buttons 28-32 px tall: pass. Check box 15 px, radio 14 px,
  slider handle 14 px, spin arrows 18 x 15 px: fail as drawn (the label extends the hit area of check
  boxes and radios; the spin box text field and keyboard are alternatives). Canvas targets 124-331 px
  (3-8 deg): pass by a wide margin; the gap dead zone of 41-83 px is wider than the 15 px cursor.
- **Keyboard focus (2.4.7).** Fields: 1 px border changes from #DBE6EC to #1F7A9C (visible, thin).
  Buttons, radios and check boxes have no `:focus` rule; whether Fusion still paints a dotted rectangle
  under the stylesheet is unverified (§7). Combo popup items suppress the focus rectangle on purpose, so
  the keyboard-focused item shows only through the hover tint. Run bar buttons are NoFocus by design.
- **Colour only for meaning.** Good: tracking state is word + colour. Weak: status by bold; disabled by
  label colour; three state tints with the same text and 2:1 stripes.
- **Text size.** 12 px body on a 1920x1080 clinic monitor for everything the clinician reads while
  standing beside a child, including the blocker and the report footnotes.

## 7. Scoring (1 = poor, 5 = strong)

| Page | Hierarchy | Density fit | Consistency | Distinctiveness | Clinical clarity | Evidence |
|---|---|---|---|---|---|---|
| Setup (01) | 2 | 2 | 4 | 2 | 2 | §4.1 |
| Test List (02, 04, 12) | 2 | 2 | 4 | 2 | 3 | §4.2 |
| Add New Test dialog (03) | 4 | 4 | 4 | 3 | 4 | §4.3 |
| Configuration page (05, 07, 09, 17) | 2 | 3 | 3 | 2 | 3 | §4.4 |
| Save-as-name dialog (18) | 4 | 4 | 4 | 3 | 4 | §4.4 |
| Start page (11, 19) | 2 | 2 | 3 | 2 | 2 | §4.5 |
| Run bar (06, 08, 10, 20; run.md) | 4 | 4 | 4 | 4 | 4 | §4.6 |
| Canvas, Scanning (06, 20) | 3 | 4 | 3 | 3 | 2 | §5 |
| Canvas, Follow (08) | 2 | 4 | 3 | 3 | 2 | §5 |
| Canvas, Grid (10) | 3 | 4 | 3 | 3 | 2 | §5 |
| Run-end dialogs (run-end.md) | 4 | 4 | 4 | 3 | 4 | §4.6 |
| Report Summary (13, 14) | 2 | 2 | 4 | 3 | 2 | §4.7 |
| Report Detailed (15) | 3 | 2 | 4 | 3 | 3 | §4.8 |
| PDF (16) | 3 | 3 | 4 | 3 | 2 | §4.9 |
| Task settings dialog (task-settings.md, standalone) | 3 | 3 | 2 | 3 | 3 | §4.10 |

Mean: hierarchy 2.9, density 3.1, consistency 3.6, distinctiveness 2.8, clinical clarity 2.8.

## 8. Findings the hub should check

1. **Full screen during a run.** Every run capture shows the OS title bar; 06 and 08 show the taskbar.
   Is the run window `showFullScreen()` or only maximised? The wireframe run.md says the title bar is
   hidden.
2. **PDF title.** 16 prints the run folder slug as the test name. Is this the P9REAL capture predating
   the `test_name` parameter of `export_report_pdf`, or a live defect?
3. **Setup status badges and calibration alert.** setup.md shows Session / Tracker / Calibration badges
   and a "No calibration yet" warning; 01 shows neither. Removed by decision, or shown only after
   Connect?
4. **Hit character.** forest.yaml sets `character: butterfly`; `canvas.py` never reads it. Is it drawn
   elsewhere, or is the entry dead?
5. **Focus rectangle on buttons, radios and check boxes.** No `:focus` rule in the QSS; verify on the
   running app whether Fusion paints one under the stylesheet, with Tab from Subject ID on Setup.
6. **Glow footprint in dense Scanning fields.** Glow reaches r + max(28, 0.6 r) px. With 8 icons shrunk
   to about 202 px (task-settings.md hint), does the halo overlap a neighbour's hit area visually?
7. **Disabled check box indicator.** 17 shows a teal-filled indicator on the greyed "Show dwell progress
   ring"; there is no `QCheckBox::indicator:disabled` rule. Confirm on the app that it is not a capture
   artefact.
8. **Report label vocabulary.** The three mismatches in §4.7 are in `report_format.py` (not read for this
   evaluation); confirm the strings before Task B proposes one vocabulary.
9. **Date formats.** Confirm the Setup date edit uses the OS locale (10/8/2026 here) while the Test List
   and report format dates in code; Task B needs to know which one is free to change.
