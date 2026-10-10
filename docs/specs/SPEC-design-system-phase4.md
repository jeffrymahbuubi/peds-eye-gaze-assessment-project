---
name: SPEC-design-system-phase4
title: Design system v1, phase 4: report Summary, Detailed and PDF (map tokens, widths, Outcome badge, PDF order)
status: implemented + live-checked (recorded runs) 2026-10-09 on branch design-phase4 (merged into feature/compass-task-flow 2026-10-10, dbf8dd9, and pushed); §9 look questions answered by the user 2026-10-09 and done in the fix round
created: 2026-10-08
last_updated: 2026-10-08
next_step: done; merged and pushed 2026-10-10 (merge dbf8dd9)
related:
  - docs/design/fable-proposal.md (source: §2.2 map and data-viz tokens, §3.7-§3.9, §5.2 phase 4)
  - SPEC-design-system-phase1.md (copy, dates, "not recorded"; LEGACY_REPORT_COLOURS frozen there until this phase)
  - SPEC-design-system-phase2.md (StatusBadge, reused for the Outcome column)
  - SPEC-gazepoint-analysis-export-parity.md (heat ramp stays the Gazepoint Analysis one)
---

# SPEC-design-system-phase4: report and PDF

**Status: approved 2026-10-08. Built after phase 2 (it reuses `StatusBadge`); independent of phase 3.
Phase 4 of the five in fable-proposal §5.2.**

## 1. Origin

Task A (`fable-evaluation.md` §4.7-§4.9) found the report hard to read at a clinician's distance:
white digits on a translucent green hit circle (about 2.0:1), layout slots below 3:1, one colour per
trial in the Summary scanpath clashing with the hit and miss marks, a Detailed table that needs a
horizontal scrollbar, bold as the only selected-row cue, and a PDF whose page 1 is 40 % blank. Phase
1 froze the map and PDF colours (`LEGACY_REPORT_COLOURS`) so this phase can change them together.
The user asked for this SPEC on 2026-10-08.

## 2. Current code (commit `1d38819`)

- `src/ui/target_map_paint.py` (450 lines): hit = `SUCCESS` pen + `SUCCESS` alpha 150 fill with
  white digits; miss = `DANGER` X, badge `DANGER` alpha 170; skipped = `MUTED` dashed; slots `MUTED`
  alpha 90 dashed; track `MUTED` alpha 120; Summary scanpath per trial from `PATH_COLOURS`
  (`_paint_scanpaths`, line 264); selected-trial path blended `#0F3D52` to `#2B8CB0`; fixation ring
  and badge `ACCENT`; heat ramp HSV (unchanged by design).
- `src/ui/target_map_follow.py` (94): Follow the Target on/off-target path colours from `MUTED`.
- `src/ui/map_legend.py` (186): legend box on `SOFT_ACCENT` tint.
- `src/ui/report_page.py` (381), `report_views.py` (346), `report_tables.py` (160),
  `frozen_table.py` (185): Summary and Detailed pages; main column uncapped; the Detailed trial
  table scrolls horizontally at 1920x1080; selected row by bold; Outcome as text.
- `src/ui/report_pdf.py` (241): HTML to PDF, fonts in pt; title `"Summary Results: <name>"`; Eye
  Metrics after the forced page break with the map; header fill `SOFT_ACCENT` with
  `SOFT_ACCENT_TEXT`.

## 3. Decisions

### 3.1 User decisions (2026-10-08)

| # | Decision |
|---|---|
| X1 | Summary map with Scanpath on: **one colour for all trials** (map-overlay #1F669E at alpha 200, dots 3 px, lines 1.5 px) and a legend line "Scanpath: fixations joined in time order, all trials". Per-trial colour lives only in the Detailed view's selected trial. |

### 3.2 Hub decisions (approved by the user 2026-10-08)

- **H1 Map tokens.** `design_tokens.py` gains the map and data-viz tokens of proposal §2.2
  (map-hit-fill #A7F0BA, map-hit-outline #198038, map-miss #DA1E28, map-skipped #6F6F6F, map-slot
  #8D8D8D, map-path-dark #1F669E, map-path-light #2D7EB3, map-fixation #1F669E, map-overlay #1F669E
  a200, map-select #F2B705 with ink outline) and their `CONTRAST_PAIRS` rows. `LEGACY_REPORT_COLOURS`
  and the old-name aliases of phase 1 are removed once nothing imports them.
- **H2 Marks (§3.7 M1).** Hit: map-hit-fill with a map-hit-outline edge and **ink digits**
  (13.63:1). Miss: map-miss X and ring; its number in ink on a white pill. Skipped: map-skipped
  dashed ring. Slots: map-slot dashed. The heat ramp stays (Gazepoint Analysis parity).
- **H3 Scanpath (X1, M2).** `_paint_scanpaths` draws every trial in map-overlay; the Detailed view's
  selected trial keeps a dark-to-light path (map-path-dark to map-path-light) and fixation number
  badges at least 11 px (D3).
- **H4 Follow the Target map.** On-target segments map-path-dark, off-target segments map-skipped,
  so the Follow report uses the same tokens (no `MUTED` alpha).
- **H5 Legend (M4).** White box with a border-subtle edge, no tint; the overlay entry of X1; caption
  size per phase 1; the selected-trial legend sentence split into two caption lines.
- **H6 Summary page (M3, M5, M6).** Main column capped at 1100 px (sidebar keeps 460); Test Name
  480 px, Evaluator 320 px; Eye Metrics table columns 320 + 320; Notes 84 px tall. Title "Summary
  Results" (phase 1 already removes the colon) with the test name at heading size under it. The
  early-end and low-gaze-quality banners become phase-2 `AlertBox` warnings.
- **H7 Detailed page (D1-D3).** Two-line headers ("Reaction" / "Time (s)") and 14 px tabular figures
  so the 13 columns fit about 1,370 px without a horizontal scrollbar at 1920x1080; the Trial
  column stays frozen. Outcome cells are a `StatusBadge`: Hit (done kind, word "Hit"), Not selected
  (disconnected kind's square, danger), Skipped (V1 dashed ring). The selected row by row-selected
  fill, not bold. Selected-trial map 720 x 405 px.
- **H8 PDF (§3.9 F1-F4).** Body 9.5 pt, trial table 8 pt, definitions 8.5 pt; table header fill
  #E0E0E0 with ink text (13.71:1); the map uses the same painter, so H2/H3 apply. **Block order:**
  header, configuration, summary, Eye Metrics on page 1; the forced break moves to before the Target
  Map, which starts page 2 with its legend. Title "Summary Results, <test name>"; date
  `yyyy-MM-dd HH:mm` (phase 1); a missing text value prints "not recorded" (phase-1 U5).
  **Added 2026-10-08 (user, after the phase-1 live check):** the title prints at 12 pt and the
  section headings (Test Configuration, Notes, Summary of Results, Target Map, Eye Metrics,
  Trial-by-Trial Results, Definitions) at 11 pt, all 600 weight; today they print at about 5 pt.
  A table header never breaks inside a word (today "Entries" prints as "Entrie / s"): the header
  wraps only at spaces, and a column is at least as wide as its longest header word.
- **H9 Labels.** The PDF's configuration labels equal the configuration page's (phase 1 already
  aligns them in `report_config`); a string test over `report_config.build_config_rows` holds it.
- **H10 Tests.** Ratios of the map tokens (P1-style); mark colours by pixel sample on an offscreen
  map render (colour only, never size); Summary scanpath is one colour; the Detailed table's 13
  columns fit 1,370 px by column-width sum; Outcome cells are badges; PDF HTML puts Eye Metrics
  before the first `page-break-before`; label equality test. Existing tests updated, never deleted.

## 4. Design

Proposal §3.7-§3.9 with X1 and H1-H10. Wireframe update (step 1): `report-summary.md` (overlay note,
title, widths, footer note on the PDF order) and `report-detailed.md` (two-line headers, Outcome
badges).

## 5. Scope

**In:** H1-H10; `target_map_paint.py`, `target_map_follow.py`, `map_legend.py`, `report_views.py`,
`report_page.py`, `report_tables.py`, `frozen_table.py`, `report_pdf.py`, `design_tokens.py` (map
tokens), `wtmh_theme.py` (alias removal).
**Out:** what the report computes (metrics, fixations, scanpaths, heat), the CSV exports, the report
cache format; operator pages (phases 1-2); canvas (phase 3); the standalone `--task X --gui` dialog (proposal phase 5, **dropped by the user 2026-10-08**: not needed).

## 6. Acceptance criteria

- **M-1** Map digits on a hit 13.63:1 by computation; every map token pair passes.
- **M-2** A Summary capture with Scanpath on reads every trial number; the overlay is one colour.
- **M-3** The Detailed table shows its 13 columns without a horizontal scrollbar at 1920x1080,
  maximized (window capture, not offscreen).
- **M-4** Outcome cells are badges with glyph + word; the selected row is shown by fill.
- **M-5** PDF page 1 holds header, configuration, summary and Eye Metrics; the map starts page 2.
- **M-6** PDF labels equal the configuration page's (string test); no lone em dash in a text field.
- **M-6b** The PDF HTML gives the title 12 pt and every section heading 11 pt; in a printed PDF
  no table header word is split across lines (the trial table's "Entries" read whole).
- **M-7** Full pytest green (except the known skip-worktree alpha checks); live check: one report
  of each task opened, Summary + Detailed captured, one PDF printed and read.

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Phase 2 done (StatusBadge, AlertBox) | — |
| 1 | Wireframes: report-summary, report-detailed (DONE 2026-10-08, user-approved) | **WF gate** |
| 2 | spec-implementer: H1-H10 (DONE 2026-10-09; one hub fix round) | — |
| 3 | Hub review + full pytest; §9 questions (DONE 2026-10-09; §9 interim = implementer defaults, user to decide) | — |
| 4 | Live check with the user (existing recorded runs; no subject needed) (hub part DONE 2026-10-09, unattended run authorized by the user; the user's final look still open) | user |
| 5 | Commit on the user's OK (DONE 2026-10-09: committed on side branch design-phase4 only, per the unattended-run authorization; no merge, no push) | user |

## 8. Impl log

### 2026-10-09, step 2 (spec-implementer, claude-sonnet-5-5), worktree `design-phase4`, nothing committed

**Done:** H1-H10 and X1, nothing outside §5. Every colour of the map, its legend and the PDF is a
`design_tokens` token; `LEGACY_REPORT_COLOURS` and the old-name aliases of `wtmh_theme.py` are gone (only
two tests imported the aliases: `test_dashboard_flow.py` now reads `TITLE_BAR` / `TITLE_BAR_TEXT`,
`test_design_tokens.py` checks that they are gone).

**Changed (`src/ui/`):** `design_tokens.py` (H1: 12 map tokens, 9 `CONTRAST_PAIRS` rows, the legacy block
removed), `wtmh_theme.py` (aliases removed), `target_map_paint.py` (H2, H3: opaque `MAP_HIT_FILL` with
`MAP_HIT_OUTLINE`, ink digits everywhere, miss ring and X in `MAP_MISS` with an ink-on-white pill edged
`MAP_MISS`, skipped `MAP_SKIPPED`, slots `MAP_SLOT`, the Summary scanpath in one colour `MAP_OVERLAY` at alpha
200 with 3 px dots and 1.5 px lines, `TRIAL_PATH_DARK / LIGHT` from the path tokens, fixation numbers at least
11 px), `target_map_follow.py` (H4: `FOLLOW_ON` = `MAP_PATH_DARK`, `FOLLOW_OFF` = `MAP_SKIPPED`, new `TRACK` =
`MAP_SLOT`), `map_legend.py` (H5: white box, `BORDER_SUBTLE` edge, radius 4, caption-size text, the Scanpath
line `SCANPATH_NOTE`, the PDF legend without the tint), `report_views.py` (H6, H7: Summary capped at 1100 px,
Eye Metrics 320 + 320, scanpath line in the legend, two-line headers, Outcome badges, 720 x 405 map, the legend
sentences as two caption lines without an interpunct), `report_page.py` (H6: test-name label at heading step
under the title, Test Name 480 / Evaluator 320 / Notes 84, banner is a warning `AlertBox`), `report_tables.py`
(`FitTable(column_widths=...)`), `frozen_table.py` (H7: 14 px tabular cells, semibold header, `two_lines()`,
`fit_columns()` / `columns_width()`, badge column API, bold delegate removed), `report_pdf.py` (H8, see below).

**Tests added (91 in all, none deleted):** `tests/real_fonts.py` (helper: registers the Windows Segoe UI files for
a module), `test_report_phase4.py` (28), `test_report_pdf_phase4.py` (24), plus tests in `test_target_map.py`,
`test_map_legend.py`, `test_frozen_table.py`, `test_report_tables.py`, `test_design_tokens.py`. **Updated:**
`test_target_map.py` (scanpath is one colour, marks by token), `test_map_legend.py`, `test_report_pdf.py` (section order,
heading elements), `test_report_page.py`, `test_report_follow_layout.py`, `test_report_switch_layout.py` (two-line
headers, the PDF's word joiners, the Follow off-target path read where it was drawn), `test_design_tokens.py`,
`test_copy_rules.py` (`report_views.py` no longer holds an interpunct; the test is renamed
`..._the_module_that_keeps_one`), `test_dashboard_flow.py`.

**pytest** (whole suite, from the worktree root): 5 failed, 3109 passed, 2 skipped (3116 collected). One earlier full run died with a Windows access violation in `tests/test_muted_labels.py:77` (`label.grab()`, a test no change of mine touches); two other full runs, a 1097-test run of `tests/test_[a-m]*.py` and five loops of the modules I changed before it all passed, so I could not reproduce it then; it came back later and its cause was found (next entry). Before any change: 5 failed, 3018 passed, 2 skipped. The 5 failures are the
known alpha 0.22-vs-0.35 checks (`test_config_flow` and four `test_task_config_page` cases). The analysis-export
golden tests are unchanged.

**What the root causes were (read before the live check):**
- *Headings at 5 pt.* A `<h2>` / `<h3>` is sized relative to the document's default font, which in the app is a
  **pixel-sized** 14 px font (`apply_application_font`); on the 300 dpi writer that is about 3 pt, times the tag's
  1.2 / 1.5. The pt size written on the tag is ignored. The title and headings are now `<p>` with explicit
  `font-size:12.0pt` / `11.0pt; font-weight:600`. Tested on the laid-out document under a 14 px application font.
- *"Entrie / s".* Qt squeezes the columns of a 13-column table to the width of their longest word with **no slack**
  (measured: cell 0.1 px wider than "Entries"), so any rounding cuts the last letter. Every table of 5+ columns
  now gets measured column widths (in the writer's own pixels) that leave each word 1.5 CSS px or more of room.
  Qt also breaks a line after "/" and "-", so "Mean peak vel. (deg/s)" came out "(deg/" over "s)": the header text
  carries a word joiner (U+2060) after each of them. The PDF's header cells therefore contain that invisible
  character (two tests strip it before comparing with the report's labels).
- *Page 1 did not fit.* At 9.5 pt the Eye Metrics ran 0.1 to 0.2 of a page onto page 2 in all three layouts.
  Cells now have 1 px above and below the text (the sides keep 3 px; one `<style>` rule) and the gaps between blocks
  are explicit (10 px above a heading, 4 px below a paragraph). The last Eye Metrics row starts at 0.89 (selection), 0.91
  (switch) and 0.93 (follow) of page 1; a long Notes text can still push the Eye Metrics over.

**Deviations from the SPEC:** none of the decisions changed. Interpretations, which the hub should look at (items 1 to
3 and two more questions are in section 9):
1. **Legend text at caption size** (H5 "caption size per phase 1"): 12 px, `LEGEND_STYLE`. It was body size (V1).
2. **The Scanpath line is on screen only.** The PDF map is Targets only, so its legend has no Scanpath line
   (`legend_html` takes no overlay note); on screen it shows when gaze was recorded.
3. **Colour of "Path of the target"** (the faint track line of Follow the Target and its legend icon): H4 only names the
   on / off pointer stretches. The track was `MUTED` at alpha 120 ("no MUTED alpha"), so it is `MAP_SLOT` (#8D8D8D)
   solid, 2 design px.
4. **The trial table's font** is chosen by fit: 8.0 pt (H8, F1) unless a layout's header words cannot all have room, then
   half a point smaller down to 6.5. This replaces the fixed `WIDE_TRIAL_TABLE_PT = 7.0` for 14+ columns: all of the
   selection (13), switch (15), follow (14) and no-gaze layouts measure at 8.0 pt.
5. **PDF banner:** the amber `WARNING_BG` becomes `WARNING_SUBTLE` (no other wording or glyph added).
6. **Detailed table columns** are set from the text (`fit_columns()`), not by Qt: a header's sort-arrow room is added
   to every section by Qt, as high as the header is, which two-line headers would have doubled. With real Segoe UI
   the columns measure 1145 px (13), 1286 (switch, 15), 1256 (follow, 14), 1192 (no gaze): all within 1,370 px, by
   column-width sum. **Not an on-screen claim**; the window is the hub's.
7. `target_map.py` (not in §5) still has one `QColor("#FFFFFF")` for the PDF image's surround; it is not scanned by
   the no-hex test, so I left it.
8. `banner_lines` text is unchanged (out of scope): the page reads "Warning: Ended early: 6 of 18 trials", the
   wireframe draws "Warning: Ended early, 7 of 18 trials.".

**Left undone:** the live check (step 4); the table's room beside the fixed map (section 9, 2).

**Verification I could do:** all by unit and offscreen tests with the Windows Segoe UI files registered (skipped if
absent); I also rendered the two recorded runs (`sessions/LIVECHK1`, `sessions/S-0001`, read only, `build_report` only,
nothing written there) to a PDF and to page images in a scratch folder: page 1 holds the header, configuration, summary
and Eye Metrics, page 2 starts with the map, "Entries" reads whole.

### 2026-10-09, after the hub's review (same implementer): the dark header block, and a crash I had introduced

**Dark block beside the header (hub's live check, Detailed, 1920 x 1009).** Qt paints the part of a
header past its last section with the widget's own background, which is the *palette's*: #202020 under a
dark palette (near black in the dark Windows theme), #EFEFEF under the default one, and neither is the
header grey. Fix, in `frozen_table.py`'s sheet: `QTableView#reportTrialTable QHeaderView,
QTableView#reportTrialFrozen QHeaderView { background: HEADER; border: none; }` (the sections already had
the rule; the header widget itself had none). Checked by pixel in the empty area under the default and a dark
palette: #E0E0E0 after, for the selection, Switch and Follow layouts (the frozen overlay's header is exactly its
column wide, so it has no empty area). Not stretched. Tests (6): `test_report_phase4.py` (the empty area under both
palettes, the same sheet minus the rule shows the palette colour so the test is not vacuous, both headers carry the
rule, the three layouts at 1920 on real Segoe UI). The `QHeaderView` rule is checked against the Qt style-sheet
reference (`QHeaderView` is a widget: the background property applies; the reference's own example styles only
`::section`) and by the pixel tests, which are the proof.

**A crash I had introduced.** Full runs died now and then with a Windows access violation (`label.grab()` in
`test_muted_labels`, `processEvents()` in `test_map_legend`, a `SetupPage` sweep): 8 of 12 runs of the first third of the suite
(`tests/test_[a-m]*.py`) on my tree and one-line variants of it, 0 of 5 on `HEAD` (and 2 of 5 full runs). Bisected with scratch copies: reverting the report-page cluster
(`frozen_table`, `report_views`, `report_page`, `report_tables`) to `HEAD` removed it (0 of 4); keeping them but putting **no
widget in the Outcome cells** removed it too (0 of 4). The cause was the `StatusBadge` I had set as a cell widget (through a
`QWidget` holder) in every Outcome cell of a table with a frozen overlay that shares its model; I could not narrow it further
than that (the table also sat in a Python reference cycle through its delegate, so the cyclic collector freed whole tables
at random moments, inside other widgets' events; that cycle is gone, and it was not the whole story: 1 of 4 runs still died
with it gone). Now:
- The Outcome badge is **painted by the table's delegate** (`_CellDelegate.paint`), with the widget's own drawing:
  `status_badge.py` (outside section 5, a behaviour-preserving refactor, `test_status_badge.py` unchanged and green) gained
  `paint_badge()` and `badge_width()`, which `StatusBadge.paintEvent` / `sizeHint` now call. The cell keeps its text (for
  the sort and for reading) and carries the badge's kind and word as item data; the delegate leaves the text out
  and paints the pill (a badge as a hidden widget rendered with `QWidget.render` was tried first: it painted in a
  viewport grab and not in a page grab, so it was dropped).
- `badge_at(row)` returns a small `BadgeCell` (`kind()`, `text()`, `look()`, `width()`), no widget. A kind that does
  not exist is refused in `set_badge`, not in a paint.
- Results: the first third of the suite, 4 parallel runs: 0 crashes; the whole suite, 2 parallel runs: 0 crashes. I cannot
  prove a flaky crash gone, but the rate went from 8 in 12 to 0 in 6 and the bisection points at the cause.

**Tests** (+8 since the first entry, 3124 collected): 6 for the header, in `test_frozen_table.py` the badge is
painted over the cell in its own colours with the row fill round it, and a kind that does not exist is refused;
`test_report_phase4.py` (badges read through `badge_at`, the sheet-resolved font assertions call `ensurePolished()` first,
which fixed a test that failed once in a full run) and `test_frozen_table.py` adapted. **pytest** (whole suite): 5 failed, 3117 passed, 2 skipped,
the known alpha 0.22-vs-0.35 checks only, in two parallel runs of the final tree.

**For the hub's look:** the PDFs of the LIVECHK1 Grid Click run and of `TESTING/runs/follow_moving/2026-10-08_1641`
(`build_report` only, real Segoe UI) are rendered to PNG pages in the scratchpad folder
`phase4_pdf` (`livechk1_grid_click_page1/2.png`, `testing_follow_moving_page1/2.png`, and the two `.pdf`). Both have two
pages; the Follow table's headers wrap to three lines in some columns ("Time on / target / (%)") because 14 columns
share the width: no word is split.

### 2026-10-09, look-answers fix round (spec-implementer, claude-sonnet-5-5), worktree `design-phase4`, nothing committed

The four answers of section 9 ("2026-10-09, user answers"), report files only. They supersede the interim defaults of the
first entry: its interpretations 1 (legend at caption size) and 2 (no Scanpath line in the PDF) and the open table-room
question; interpretation 3 (target path line `MAP_SLOT` solid) stands, as the user said.

1. **Detailed table below the map, full width.** In the code the table was *above* the map (one vertical stack, the table
   with stretch 1); it is now: "Selected trial: Trial N", the 720 x 405 map (unchanged), the scan-path line, the pointer legend
   (Follow only), the two caption lines, then "Trial-by-Trial Results" and the table, at the pane's full width
   (`content.width() - 8`, the layout's right margin). The pane scrolls vertically. **Minimum height chosen: 8 rows**
   (`TABLE_MIN_ROWS` in `report_views.py`; new `FrozenColumnTable.set_minimum_rows()` / `height_for_rows()`): header + 8 x 40 px
   + frame = 377 px on real Segoe UI (55 + 320 + 2), it was 200 px (about 3 rows). At 1920 x 1009 the pane scrolls (range 201 px
   for the Grid fixture, 318 for Follow) and the table shows 8 whole rows. A fixed 8, not min(8, rows): a 3-trial test shows
   some blank table body, as it did before whenever the pane was taller than its content. M-3 holds: no horizontal scroll bar
   at 1920 with the pane's vertical bar, and for 20 trials with the table's own too (selection, Switch, Follow).
2. **Legend text at body size.** `LEGEND_STYLE`: `TYPE_CAPTION` to `TYPE_BODY` (labels, Scanpath line and numbers note, 14 px).
   Measured on real Segoe UI: the legend's minimum width is 426 px (selection), 324 (Follow), 349 (pointer legend); nothing
   clips at 1920 and at 1366 wide; the box keeps its 880 px maximum. The selected trial's two caption lines under the map stay
   at caption size (they are not the legend box).
3. **PDF map has the scanpath.** `ReportPage.export_pdf` renders the map with `{"targets": True, "path": gaze_was_recorded(report)}`:
   the same `render_to_image` / `paint_map` / `_paint_scanpaths` as the screen, no second painter (a test compares the image
   pixel for pixel with the Summary map rendered with Targets and Scanpath on). `legend_html()` gets `overlay_note`;
   `build_report_html` passes `SCANPATH_NOTE` when gaze was recorded (no line without gaze), above the numbers note as on the
   screen. It is independent of the Summary's switches. Page 1 is unchanged, page 2 holds the map, the legend with its extra
   line and the table (two pages for the fixtures, as before).
4. **Follow the Target: off-target stretches dashed.** `target_map_follow.off_pen()`: `MAP_SKIPPED`, width 2 design px (as H4),
   dash 4 and gap 3 pen widths, **flat caps** (with the round caps `_pen` uses a gap this thin closes up). Used by
   `paint_pointer_runs` (screen and PDF, one code) and by the legend icon "Pointer off target"; on-target stretches and the
   target path line stay solid, colours and widths as H4.

**Changed:** `src/ui/report_views.py`, `src/ui/frozen_table.py`, `src/ui/map_legend.py`, `src/ui/report_pdf.py`,
`src/ui/report_page.py`, `src/ui/target_map_follow.py`, `src/ui/target_map_paint.py` (a docstring), `docs/wireframes/report-detailed.md`
(the order, the 8 rows, the legend size, the dashed off-target stretch).

**Tests (28 new, none deleted):** `test_report_phase4.py` 11 (order and full width, the Follow legend above the table, 8 rows and the
scrolling pane, no horizontal scroll bar for three layouts, the legend at 14 px and not clipped for three entry sets, the Summary
legend at 1920 and 1366), `test_report_pdf_phase4.py` 8 (the page's PDF map is the screen's pixels, whatever the switches say, no
scanpath and no legend line without gaze, the legend line on page 2 for three layouts, no line without a map, the blue read back
from the written file's page 2), `test_report_follow_layout.py` 5 (off dashed and on solid, dash and gap widths, the report's own
runs drawn dashed by the map, the legend icon dashed and the others solid, the target path line solid), `test_frozen_table.py` 3,
`test_map_legend.py` 1 (the PDF legend's Scanpath line in place). **Updated:** `test_map_legend.py` (body size instead of caption,
renamed `..._ink_body_text`; a comment), `test_report_page_actions.py` (the test renamed `..._and_the_whole_test_map`, with a docstring),
`test_report_pdf_phase4.py` (its `map_image()` helper now draws what the page draws).

**pytest** (whole suite, worktree root, one run): **5 failed, 3145 passed, 2 skipped** (3152 collected); the 5 are the known
alpha 0.22-vs-0.35 checks (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and four
`test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`); no crash. (Baseline before any change, the 9 report
test files: 249 passed.)

**Deviations from the SPEC:** none. **Looked at** (offscreen renders with real Segoe UI, not a window): the Detailed page at 1920 x 1009
for a Grid and a Follow report, scrolled to the end; the Follow map with an off-target stretch; PDF page 2 of a Grid and a Follow report.

**For the hub (not decided here):**
- The Follow caption under the selected trial's map (`FOLLOW_TRIAL_LEGEND` in `report_views.py`) still says the path is "light where it was
  off it"; it is a grey, thinner and now dashed line. Copy, not in the four answers, so unchanged (two tests quote the phrase). **Done in the
  follow-up below.**
- `docs/wireframes/report-summary.md` is out of this round's scope and now stale in two places: line 153 (Follow legend: "off target"
  as a light path) and line 188 (the PDF "map with Targets only"; it now has the scanpath and its legend line). **Done in the follow-up below.**
- Where an off-target stretch runs along the target's own path line (the old fixture does: the pointer follows the target's line), the
  gaps of the dashes show that line (`MAP_SLOT` #8D8D8D) instead of white, so dash against gap is a weak contrast there (#6F6F6F on #8D8D8D).
  The Summary map never draws pointer runs. Away from the target's line the dashes read clearly.
- Scratch images of the looks above are in this session's scratchpad (`detailed_follow.png`, `detailed_follow_bottom.png`, `follow_t2_720.png`,
  `pdf_grid_p2.png`, `pdf_follow_p2.png`).

**Follow-up (hub review, same day):** `FOLLOW_TRIAL_LEGEND` now says "solid dark blue where the pointer was on the target and dashed grey where it
was off it" (the two tests that quoted the old phrase, in `test_report_follow_layout.py` and `test_report_phase4.py`, updated), and
`report-summary.md` lines 153 and 188 say dashed grey and "the Targets, plus the Scanpath when gaze was recorded"; the dash gaps over the
`MAP_SLOT` line left as they are; affected tests only (`test_report_follow_layout`, `test_report_phase4`, `test_copy_rules`, `test_report_switch_layout`): 133 passed.

### 2026-10-09, map-fills-column fix round (spec-implementer, claude-sonnet-5-5), worktree `design-phase4`, nothing committed

The last entry of section 9 ("user decision after testing the try-all build (empty space)"), report files only. On screen the
target map of the **Summary** and of the **Detailed** tab now grows to fill its column, at the canvas's aspect, never taller than
the pane shows, never below 720 x 405 px, and follows the window. It replaces the fixed 720 x 405 of H7 on screen. The PDF is untouched.

**Changed:**
- `src/ui/target_map.py`: `MAP_MIN_SIZE = (720, 405)`; `fill_size(width, height)` (the largest widget size at the canvas's aspect within the room,
  never below the minimum) and `fit_within(width, height)` (sets that fixed size); `heightForWidth` shares `_height_for()`. `set_fit_to_width` stays
  (its tests are unchanged) but the report views no longer use it.
- `src/ui/report_views.py`: `fit_map(area, map, above, legends)` and, in both views, `resizeEvent` + `_fit_map()` (also called from `set_report`, the
  canvas's aspect may change). The width is the view's width less its frame, a vertical scroll bar (counted whether it shows or not, so the size never
  depends on the bar showing, no feedback loop) and the layout's right margin (`CONTENT_RIGHT_MARGIN = 8`); the height is the pane's viewport height less
  `above`. Removed: `MAP_MAX_WIDTH` (880), `SUMMARY_MAX_WIDTH` (1100, also `setMaximumWidth` on the Summary), `SELECTED_MAP_SIZE`. The Summary view now
  takes the whole stack width at 1920 (the Summary of Results table spans it); the map is left-aligned; the legend boxes (Summary, and the Follow
  pointer legend in Detailed) are as wide as the map above them (`setMaximumWidth(map.width())` in `fit_map`, as they were as wide as the 880 px map).
- `docs/wireframes/report-summary.md`, `report-detailed.md`: text only (the 1100 px cap, a "Size of the map" note in each, the 720 x 405 mentions).

**Measured** (offscreen, real Segoe UI registered, `Fusion`, under the dashboard sheet; not a window): Summary map x viewport at 1920 x 1009
1144 x 669 in 1382 x 738, at 1920 x 1080 1265 x 740 in 1382 x 809; Detailed 1192 x 697 and 1313 x 768. At 1920 the **height** holds the map back (the
column is 1374 wide), so about 240 px of the column stay empty at the map's right at 1080p; in a taller window the map is exactly the column wide.
1366 x 768 gives 731 x 428 and 779 x 456; 1280 x 700 the minimum 720 x 422.

**Hit-testing / mouse mapping:** the map has none (no mouse event, hover or tooltip in `target_map*.py`). It maps recorded canvas-normalized positions
to pixels through `canvas_rect()` (`_point()` = rect.left + x * rect.width) and every mark size is a fraction of `rect.width()` (`unit = rect.width() / 900`),
so it scales from the recorded canvas at any size; a test draws the fixture's hit and miss at three map sizes and reads them at the same canvas fractions.

**PDF:** `ReportPage.export_pdf` renders the Summary map with `render_to_image(QSize(1800, ...))`, which uses the image's own rectangle, not the widget's;
a test renders the same report from a 100 x 100 and a 2000 x 2000 fit and gets equal images. `report_pdf.py`, `test_report_pdf*.py` unchanged and green.

**Interpretations** (one place each, easy to change; also in section 9):
1. **Aspect.** The widget follows the recorded canvas's aspect (`map.aspect`: 16:9 for the standard canvas, 1640 x 957 for the fixtures), not a forced 16:9, as
   the Summary's map did before; with a 16:9 canvas the canvas rectangle is exactly 16:9. The 2 px margin of the widget (`MARGIN`) is taken off before the ratio.
2. **The height cap leaves room for the heading.** "Fits the visible height of its scroll pane" is taken as: the map's height is the pane's visible height less
   what sits above it in its group (Detailed: the "Selected trial" heading and one gap; Summary: the "Target Map" heading, the switches row and two gaps), so
   the heading (and the three switches) and the whole map are in view together. With the map as tall as the whole pane, the Detailed map (it is the first thing)
   would be cut at its bottom at scroll 0, which is the opposite of "no scrolling". The room is computed in `_fit_map()` of each view (3 lines each).
3. **Minimum.** 720 x 405 is the minimum widget size, at the canvas's aspect: 720 x 407 for a 16:9 canvas (the widget's 2 px margin), 720 x 422 for the fixtures'.
   A pane too small for it keeps the minimum and the page scrolls (the same as the old fixed size did).
4. **Not changed:** the Eye Metrics table stays 320 + 320 px (H6, M6) and Notes and the other fixed widths stay, so on a wide Summary the space at the right of
   the Eye Metrics table stays empty (the decision names the map).

**Tests** (23 new, none deleted): `tests/test_report_map_fill.py` (bare-widget rule: widens with the room and keeps 16:9, never taller than the room, minimum
for small and degenerate rooms, a wider-than-16:9 canvas, `fit_within`; on the page, for both views: widens with the column by exactly the window's growth,
exact 16:9 for a 16:9 canvas, heading and whole map in view for the Detailed at scroll 0 and for the Summary scrolled to its heading at 1000 and 1080, the
minimum in a small window, follows a resize and back, a second report with another aspect, legends as wide as the map; marks at the same canvas fractions
at three sizes; the PDF's image independent of the widget's size). **Updated:** `test_report_phase4.py` (the 1100 px test now says the column takes the stack
width and the Summary table spans it, the 720 x 405 test says "never smaller than", the order test no longer pins 720 x 405 or a table 600 px wider than the
map, the stand-alone legend test has its own width constant, the summary legend test says "as wide as the map"), `test_map_legend.py` (legend max width equals the
map's width), `test_report_page.py` (both maps are fixed-size, neither is height-for-width). The module registers no font and sets no application style on purpose
(see the pytest note).

**pytest** (whole suite, worktree root, `-p no:cacheprovider -o addopts=""`, two consecutive runs of the final tree): **5 failed, 3168 passed, 2 skipped** (3175
collected) both times; the 5 are the known alpha 0.22-vs-0.35 checks (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and four
`test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`), no crash. The touched files alone (`test_report_map_fill`, `test_report_phase4`,
`test_map_legend`, `test_report_page`, `test_target_map`): all passed. With the new module left out the suite was 5 failed, 3145 passed, 2 skipped.
**A sixth failure I had to chase:** the first versions of `test_report_map_fill.py` made full runs (not subsets, which passed) fail one more test, three times
`test_setup_phase2::test_the_page_is_one_column_1200_px_wide_with_the_scroll_bar_beside_it` (the page's content got a real font's metrics, 1196 px wide instead of
the offscreen em-wide 1200 the test relies on) with a version that registered Segoe UI and set Fusion like the neighbouring report modules, and once
`test_report_phase4::test_the_test_name_stands_at_the_heading_step_under_the_page_title` (the sheet's 28 px font not applied) with a font-free version. Neither is in
code this round changed (a leaked font / cached style-sheet state); I did not find the exact mechanism. What made it stop (two full runs clean after it): the module
registers no font and sets no application style (nothing here needs text metrics: every claim is a relation between sizes the widgets report), closes and
`deleteLater()`s each window, and an autouse fixture sends the deferred deletes and collects garbage after each test, so no window of this module is freed inside a later
module's test. Those two tests, and `test_muted_labels:77` which crashed one parallel run of mine without this module, are order-sensitive; watch them if a sixth
failure shows up after a merge.

**Deviations from the SPEC:** none of the decisions changed. Interpretation 2 (the heading's room) makes the Summary map up to 69 px and the Detailed map up to 41 px smaller
than "the whole pane height"; drop `above` to 0 in the two `_fit_map()` to get the literal reading.

**Left undone:** the live look (a maximized window at 1080p and a laptop width) is the hub's.

## 9. Implementer open questions

- **2026-10-09** (implementer) Two small calls the SPEC does not make. (a) The PDF legend has no Scanpath line, because
  the PDF's map is Targets only (the wireframe says "the same box in the PDF"); on screen the line shows when gaze was
  recorded. (b) The faint "Path of the target" line of Follow the Target (and its legend icon) was `MUTED` at alpha 120;
  H4 names only the on / off pointer stretches, so it is `MAP_SLOT` (#8D8D8D) solid. Say if either should differ.
- **2026-10-09** (implementer) Legend text size. H5 says "caption size per phase 1" without saying for what. I read it as
  the legend's labels and its notes at the type scale's caption step (12 px); the first version (V1, user) asked for
  body size so it would read without effort. One constant: `LEGEND_STYLE` in `map_legend.py` (`TYPE_CAPTION` to
  `TYPE_BODY` if body was meant). Decide at the live check.
- **2026-10-09** (implementer) Room for the Detailed table beside the fixed 720 x 405 px map. The pane's viewport is about
  690 px high at 1920 x 1080: the table's minimum height (200 px, unchanged) plus the map and the lines around it
  already make the pane scroll, and the table shows about three rows (header 55 px, rows 40 px; read from an offscreen
  render with real Segoe UI, not a window). The old 11:9 split gave the table more. SPEC H7 fixes the map size and not the table's; I did not change the table's minimum height.
  Decide: a higher minimum (the pane then scrolls further), the map smaller on a short window, or as it is.
- **2026-10-09** (implementer) Off-target pointer path (H4): `MAP_SKIPPED` #6F6F6F against `MAP_PATH_DARK` #1F669E have close
  luminance (0.16 and 0.12), so on / off differ by hue and width (3 vs 2 design px) only; the old comment promised "it
  reads without colour". Not changed (the SPEC names both tokens); look at a Follow report in grey scale at the live check.

- **2026-10-09, hub (unattended run).** All four items above are look questions and go to the user; interim = the implementer's defaults (table min height 200 px, legend at caption size, no Scanpath line in the PDF legend, target path line `MAP_SLOT` solid, on/off pointer stretches as H4). Screenshots: Detailed at 1920 shows about 3 rows beside the 720 x 405 map and the pane scrolls.

- **2026-10-09, user answers.** (1) Table room: the Detailed **table goes below the map, full width**; the map stays
  720 x 405 (H7). (2) Legend text at **body size** (`TYPE_BODY`). (3) The **PDF map draws the scanpath** (the same
  one-colour line as the screen Summary, X1) when gaze was recorded, and its legend then shows the Scanpath line, so app
  and PDF match. (4) Follow: **off-target pointer stretches are drawn dashed** (colours and widths as H4), so on / off
  read without colour; the legend icon for off-target is dashed too; target path line stays `MAP_SLOT` solid.
  (Hub note: the hub's question to the user wrongly said the colours were green / orange; the answer is about telling
  on from off without colour, which applies to the real tokens.)

- **2026-10-09, user decision after testing the try-all build (empty space).** The target map on the Summary and
  the Detailed tab **grows to fill its column**, keeping 16:9, capped so the whole map fits the visible height of the
  pane (no scrolling to see the map); it replaces the fixed 720 x 405 of H7 on screen. The PDF keeps its current size
  (user: "PDF OK, no comment"). The legend and the Detailed table follow below as now. To implement as a fix round on
  branch design-phase4.

- **2026-10-09** (implementer, map fills its column) Two look questions the decision does not settle; both are implemented with the default named and decide
  at the live check. (a) The map's height cap keeps the heading (Summary: heading + the three switches) in view with the whole map, so on a 1920 x 1009 window
  the Summary map is 1144 x 669 and the Detailed one 1192 x 697, which leaves about 240 px of the 1374 px column empty at their right; the literal reading (the
  map as tall as the whole pane) is 69 / 41 px taller, so about 118 / 70 px wider. Change: the `above` in `SummaryView._fit_map()` / `DetailedView._fit_map()`
  (`src/ui/report_views.py`), set it to 0. (b) The Eye Metrics table is still 320 + 320 px (H6), so the space at its right on a wide Summary stays empty; say if
  it should grow with the column too (`EYE_COLUMN_WIDTHS`, `FitTable(column_widths=...)`).

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §2.2 (map tokens), §3.7-§3.9 and §5.2
  phase 4. User decision X1 (one-colour Summary scanpath). Hub decisions H1-H10 proposed, awaiting
  approval. Note: the live check needs recorded runs in the new layout; the old test data is deleted
  when the data-layout SPEC lands, so new runs must be recorded first (the phase-3 live check
  produces them).
- **2026-10-08** — The user approved H1-H10 as written. SPEC committed on `feature/compass-task-flow`.
- **2026-10-08** — The user dropped the optional proposal phase 5 (standalone dialog parity): phase 4 is the last design-system phase. Step 1 wireframes (report-summary, report-detailed) drafted and rendered, awaiting the WF gate.
- **2026-10-08** - Step 1: the user approved the report-summary and report-detailed wireframes as drawn.
- **2026-10-08** - H8 extended and M-6b added (user decision after the phase-1 live check, PDF of a real Grid Click run): section headings print at about 5 pt and the trial table's "Entries" header splits as "Entrie / s"; neither comes from phase 1 (it changed only the PDF's wording). Title 12 pt, section headings 11 pt, header words never split.
- **2026-10-09** — Hub review, during the unattended run the user authorized (side-branch commit
  only). Scope matches H1-H10 and X1, report/PDF files only. Hub fix round: (1) the Detailed
  table's header painted the area right of the last section near-black (Qt fills it with the
  widget palette); a `QHeaderView` background rule in `frozen_table.py` fixes it for both tables,
  pixel-tested for selection, switch and follow. (2) Found by the implementer: a `StatusBadge`
  widget in every Outcome cell, beside the frozen overlay that shares the model, caused intermittent
  access violations in full runs (8 of 12); the delegate now paints the badge (`paint_badge()`,
  `badge_width()` in `status_badge.py`, outside §5; `badge_at(row)` returns a `BadgeCell`), 0
  crashes in 6 runs after. Hub pytest, two full runs: **5 failed, 3117 passed, 2 skipped** both
  times, no crash (the 5 are the known skip-worktree alpha checks). Live check on the copied
  LIVECHK1 Grid Click run, maximized 1920x1009: Summary marks, one-colour Scanpath (X1), white
  legend box with the Scanpath line, Eye Metrics 320 + 320; Detailed table fits with no horizontal
  scroll (M-3), two-line headers, painted Outcome badges, header blank right of the last column.
  PDF (rendered to PNG, LIVECHK1 Grid Click and a Follow run): title and headings at 12 / 11 pt,
  "Entries" whole, page 1 header through Eye Metrics, map on page 2. Not done: the user's final
  look and the §9 answers. Committed on branch `design-phase4` only.
- **2026-10-09** — Fix round for the user's §9 answers: the Detailed table below the 720 x 405 map at full width
  (minimum 8 rows); legend text at body size; the PDF map draws the one-colour scanpath (same paint code as the
  screen) and its legend lists it when gaze was recorded; Follow off-target pointer stretches dashed (screen, PDF,
  legend icon). Hub follow-up: `FOLLOW_TRIAL_LEGEND` copy and `report-summary.md` lines updated to match. Hub
  pytest: four full runs; three clean (**5 failed, 3145 passed, 2 skipped**, the known alpha checks), one ended in a
  native crash whose traceback was cut off; it ran while a second suite, the live app and a PDF render shared the PC.
  Not reproduced in three later runs with `-X faulthandler`; watch for it after the merge. Live check (worktree code,
  maximized 1920x1009, copied LIVECHK1): Detailed tab shows the table below the map at full width; PDF page 2 of
  LIVECHK1 Grid Click and TESTING Follow shows the scanpath and its legend line. Follow dashes checked in unit tests
  only (no recorded Follow trial with pointer runs on screen). Committed on branch design-phase4.
- **2026-10-09** — Fix round for the user's empty-space decision: the Summary and Detailed maps grow to fill
  their column at the recorded canvas aspect, capped so the heading and the whole map fit the pane's visible height,
  never below 720 x 405; the 1100 px Summary cap is gone (sidebar keeps 460). The PDF is unchanged (pinned by test).
  Hub live check (maximized 1920x1009, copied LIVECHK1): Summary map about 1144 x 669, Detailed about 1192 x 697;
  about 240 px stays empty right of the map, the price of 16:9 within the height. Hub pytest: two full runs; run 2
  **5 failed, 3168 passed, 2 skipped** (the known alpha checks); run 1 ended in an access violation inside
  `tests/test_muted_labels.py:77` (`root.show()` + `processEvents()`), a phase-2 test, the same place the implementer
  saw crash in a run without this round's tests: a test-suite object-lifetime flake, not this change; queued for a
  hardening fix. Committed on branch design-phase4.
- **2026-10-10** — Merged into feature/compass-task-flow by the hub at the user's request (merges f60a601, b3c71c2, c14c77f, dbf8dd9); full suite on the merged branch **3348 passed, 3 skipped**; pushed `6d2b2cb..dbf8dd9`. Side-branch worktree and branch removed.
