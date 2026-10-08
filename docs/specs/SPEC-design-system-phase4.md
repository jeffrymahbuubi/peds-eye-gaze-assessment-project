---
name: SPEC-design-system-phase4
title: Design system v1, phase 4: report Summary, Detailed and PDF (map tokens, widths, Outcome badge, PDF order)
status: approved 2026-10-08 (X1 user decision, H1-H10 hub decisions approved by the user)
created: 2026-10-08
last_updated: 2026-10-08
next_step: /spec-run step 2 after phase 2 (wireframes approved 2026-10-08)
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
| 2 | spec-implementer: H1-H10 | — |
| 3 | Hub review + full pytest; §9 questions | — |
| 4 | Live check with the user (existing recorded runs; no subject needed) | user |
| 5 | Commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

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
