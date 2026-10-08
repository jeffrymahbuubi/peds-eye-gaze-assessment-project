---
name: SPEC-design-system-phase1
title: Design system v1, phase 1: colour tokens, type scale, component QSS and copy rules (operator UI)
status: implemented 2026-10-08 (live check passed with three carry-over bugs moved to phase 2 by the user); committed on branch design-phase1
created: 2026-10-08
last_updated: 2026-10-08
next_step: step 4 (on the user's OK) delete the old-layout folders in sessions/, merge data-layout then phase 1 into feature/compass-task-flow, push (user pushes)
related:
  - docs/design/fable-proposal.md (source: §2 design system v1, §4 copy rules, §5.2 phase 1)
  - docs/design/fable-evaluation.md (Task A findings the proposal cites)
  - docs/design/design-system.html (visual reference, WTMH blue)
  - SPEC-subject-data-layout.md (implemented, committed on its worktree branch, not merged; phase 1 is stacked on it, U2)
---

# SPEC-design-system-phase1: tokens, type, copy

**Status: approved 2026-10-08. Branch `feature/compass-task-flow` for this document; the code is built
on top of the subject-data-layout commit (U2). Phase 1 of the five in fable-proposal §5.2. Phases
2-5 each get their own SPEC later.**

## 1. Origin

The user finds the UI "AI-ish" (gradient buttons, cards on cards, left-stripe banners, pastel tints,
no type scale). A Fable model evaluated it (Task A, `docs/design/fable-evaluation.md`) and proposed a
design system (Task B, `docs/design/fable-proposal.md`): IBM Carbon tokens plus NHS content rules,
ported into the existing Qt style sheet, with no widget library. The user accepted the direction,
replaced Fable's teal with the WTMH lab blue (#1F669E, committed `66a3c3b`), and on 2026-10-08 asked
for the phase-1 SPEC.

Phase 1 changes **how things look and read, not where they sit**: every colour and size becomes a
named token, the type scale replaces eight ad hoc sizes, components get their QSS sizes and states,
and the copy rules of proposal §4 replace today's strings. Layout, status badges and the canvas are
later phases.

## 2. Current code (worktree `agent-a6726ce4bb2d33644`, data-layout diff applied, 2026-10-08)

- `src/ui/wtmh_theme.py` (496 lines): ~25 hex constants (`ACCENT #1F7A9C`, gradients
  `ACCENT_GRADIENT_START/END`, `SOFT_ACCENT`, `BACKGROUND #F5F9FB`, `BORDER`, `INK #122B3A`, `MUTED`,
  `DANGER #E15353`, `SUCCESS #2F9E6E`, `WARNING_BG`, `BANNER_BORDER`, disabled triple, ...) and one
  `STYLESHEET` f-string scoped to `QWidget#wtmhDashboard`. One `qlineargradient` (line 184,
  primary button). No `:focus` rule for buttons, radios or check boxes; no `indicator:disabled` rule.
- Importers of the old constant names: `dialog_theme.py`, `add_test_dialog.py`, `config_widgets.py`,
  `dashboard_window.py`, `frozen_table.py`, `rename_editor.py`, `run_dialogs.py`, `setup_page.py`,
  `task_settings_dialog.py`, `report_views.py`, and the report/PDF painters `map_legend.py`,
  `report_pdf.py`, `target_map_paint.py`, `target_map_follow.py` (phase 4 files).
- `src/ui/run_bar.py`: own sheet with hard-coded `#122b3a`, 13 px; one rich-text status label fed a
  whole line such as `Trial 4/18 · tracking OK`.
- `src/ui/dashboard_window.py:165-180`: Fusion style + `standardPalette()`; no application font set.
- `src/ui/setup_page.py:555`: `QDateEdit` without `setDisplayFormat`.
- `src/ui/report_format.py:341` `started_text`: `Oct 6, 2026 2:06 PM`.
- `src/data/report_config.py`: report row labels and values (`Trials (planned)`, `Maximum time per
  trial`, `Pause between trials`, `Gaze cursor shown`, `Sound on, sparkle on`, `Smoothing α 0.22`,
  `Dwell 0.8 s`), `DASH = "—"`.
- Em dash `—`: 45 lines in `src/ui`, `src/data`, `src/engine/task_info.py`. User-visible ones:
  `choice_lists.py` (size and selection radios), `task_info.py` (4 task descriptions),
  `setup_page.py` (6 calibration / display / USB texts), `start_test_page.py` (3 Mouse notes),
  `report_views.py:327` ("Selected trial — Trial N"), `report_quality.py:116` ("Ended early — ..."),
  `task_settings_dialog.py:78,117` (title), `report_page.py` / `report_pdf.py` titles end in ":".
  The rest are comments and docstrings, plus the `DASH` / `NO_DATE` constants.
- `src/ui/task_config_page.py:380`: `Modified from "<name>"`. `run_dialogs.py:124`: `Test Complete!`.

## 3. Decisions

### 3.1 User decisions (2026-10-08)

| # | Decision |
|---|---|
| U1 | Direction: fable-proposal §1-§2 (Carbon tokens + NHS content rules, QSS token port, no widget library, Segoe UI). Accent = WTMH blue **#1F669E** family of proposal §2.2, not teal. |
| U2 | Ordering: subject-data-layout steps 2-3 are committed on their worktree branch (not merged, not pushed); phase 1 is built **on top of that commit**. One live check with the user covers both SPECs. |
| U3 | Copy scope: phase 1 does every **text-only** replacement of proposal §4 plus the run-bar PRACTICE / PREVIEW chip. The Start page "Blocked:" block and the glyph status badges (incl. the run bar's "Tracking OK" badge) move to phase 2 with the badge helper. |
| U4 | A **disabled checked** check box / radio: fill **#8D8D8D** (border-strong), white mark (closes the design page's "disabled-checked grey" gap). |
| U5 | A missing value in a **text** cell or row reads **"not recorded"** (not Fable's "none"); the em dash stays only in numeric table cells. |
| U6 | No migration of old data (data-layout SPEC D5 revised); unrelated to phase 1 except that it unblocked U2. |

The other open gaps of the design page (Large target px, Not calibrated / Skipped glyphs,
unselectable-target ratio, Test List side-button tiers) belong to phases 2-3 and are decided in
their SPECs.

### 3.2 Hub decisions (approved by the user 2026-10-08)

- **H1 Token module.** New `src/ui/design_tokens.py` holds every token of proposal §2.1-§2.5 as a
  named constant (colours of §2.2 operator UI, accent and state tables; type steps; spacing 4-48;
  radius; control heights) plus a `CONTRAST_PAIRS` table: `(fg token, bg token, minimum ratio)` for
  every row of §2.2 with a ratio. `wtmh_theme.py` imports it and keeps only the QSS (keeps both
  files under 500 lines). Map / data-viz tokens of §2.2 are **not** added yet (phase 4).
- **H2 Old constant names.** The old names stay importable from `wtmh_theme.py` for one release as
  aliases. Operator-UI importers (`dialog_theme`, `add_test_dialog`, `config_widgets`,
  `frozen_table`, `rename_editor`, `run_dialogs`, `setup_page`, `task_settings_dialog`,
  `report_views` text colours) are switched to the new token names. The four phase-4 painters
  (`map_legend`, `report_pdf`, `target_map_paint`, `target_map_follow`) keep today's hex values,
  frozen in a `LEGACY_REPORT_COLOURS` block, so the map and PDF do not change until phase 4.
- **H3 Accent family.** Exactly the hex values of proposal §2.2 (WTMH blue): accent #1F669E, hover
  #17507D, focus #2D7EB3, subtle #E3EEF7, row-selected #CFE2F1, slider-groove #C6C6C6, title bar
  #12374A. **No gradient anywhere** (the `qlineargradient` and `ACCENT_GRADIENT_*` go).
- **H4 Type scale.** Application font `QFont("Segoe UI")` with `setPixelSize(14)` set once in
  `dashboard_window.py` next to the Fusion call. QSS rules only for the larger roles: page title
  28 px / 700 (`wtmhPageTitle`), heading 20 px / 600 (`wtmhSectionTitle`, Start headings,
  `runDlgHeading`), body-large 16 px (read-aloud text, run-bar status, banner text), caption 12 px
  (footnotes, helper lines, badges: today's 11 px goes). The title-bar brand (15 px) becomes 16 px.
  No `font-size` in any sheet outside the scale (grep check, §6).
- **H5 Components (QSS only, no new widgets).** Per proposal §2.5: buttons 40 px / min 96 / 600 /
  radius 4 in primary, secondary, tertiary and danger tiers, disabled = #E0E0E0 fill + #6F6F6F
  text in the same place; fields 36 px, 1 px border-strong, radius 4; tables: header #E0E0E0 14 px /
  600, rows 40 px, selected row row-selected; check box / radio indicators 20 px; spin-box stepper
  24 px; SliderSpinRow groove 4 px slider-groove, fill accent, 20 px handle, disabled handle
  border-strong. Slider **length caps** (240 / 360 px) are layout and move to phase 2.
- **H6 Focus.** Explicit `:focus` rules on buttons, radios, check boxes, fields, combo boxes, spin
  boxes and sliders: 2 px accent-focus border, padding reduced by 1 px so nothing moves. Whether
  Qt draws the "1 px white gap" of §2.5 is checked live; if QSS cannot draw it, the 2 px border
  alone is accepted (4.42:1 on white).
- **H7 Disabled indicators.** `QCheckBox::indicator:disabled` and `QRadioButton::indicator:disabled`
  rules: unchecked = #E0E0E0 fill + border-strong; checked = #8D8D8D fill + white mark (U4). The
  check box reuses the existing white `configs/assets/icons/checkmark.png` (QSS cannot draw a mark);
  the radio's dot is the indicator's inner border as today.
- **H8 Alerts, phase-1 part.** The banner QSS loses its left stripe and tint: white fill, 1 px
  border in the state colour (warning #BA4E00, danger #DA1E28, neutral border-strong), body-large
  ink text. The 20 px glyph tile and the bold state word are phase 2 (badge helper).
- **H9 Run bar.** 48 px tall, token colours, body-large status. The status line is split into
  separate labels: a filled warning-chip (#F1C21B, ink) reading PRACTICE or PREVIEW (only in
  those modes), then "Trial 4 of 18", then "Mouse pointer" when the pointer is the mouse, then the
  tracking state as plain text ("Tracking OK", "No gaze for 3 s", "Tracker disconnected") in
  success-text / warning-text / danger-text. No interpunct. The glyph badge comes in phase 2.
  Buttons 36 px, border-strong, NoFocus as today. Practice / preview bar fill warning-subtle.
- **H10 Dates.** `yyyy-MM-dd` everywhere a date shows, `yyyy-MM-dd HH:mm` (24 h) with a time:
  Setup `QDateEdit.setDisplayFormat("yyyy-MM-dd")`, `report_format.started_text` ->
  "2026-10-07 17:09", report header and PDF use `started_text`. The Test List already prints ISO.
- **H11 Em dash.** Every em dash in `src/ui`, `src/data` and `src/engine/task_info.py` goes,
  comments and docstrings included, so the acceptance grep is exact. Remaining: the `DASH` constant
  of `report_config.py`/`report_format.py` and `NO_DATE` of `test_list_table.py`, used **only** in
  numeric / date table cells. Text cells and report rows that used `DASH` read "not recorded"
  (U5). Replacements: the §4 table of the proposal, plus the strings it did not list:

  | Where | Today | Phase 1 |
  |---|---|---|
  | Setup, calibration result | "Calibration measured — N points, mean error E, valid." | "Calibration measured: N points, mean error E, valid." |
  | Setup, per-point details | "Per-point details were not received — if this repeats, close and ..." | "Per-point details were not received. If this repeats, close and ..." |
  | Setup, no calibration | "No calibration yet for this subject — run Do Calibration or ..." | "No calibration yet for this subject. Run Do Calibration or ..." |
  | Setup, read-only reminder | "(Read-only reminder — neither setting ..." | "(Read-only reminder: neither setting ..." |
  | Setup, calibration saved / loaded | "Calibration saved for S as F — ..." / "Calibration loaded — N points ..." | "Calibration saved for S as F. ..." / "Calibration loaded: N points ..." |
  | Setup, USB note | "... 150 Hz on a USB 3.0 connection — move the data cable ..." | "... 150 Hz on a USB 3.0 connection. Move the data cable ..." |
  | Start, Mouse notes (3) | "Mouse test — eye data will be recorded alongside." etc. | "Mouse test. Eye data will be recorded alongside." etc. |
  | Report, selected trial | "Selected trial — Trial 4" | "Selected trial: Trial 4" |
  | Report quality | "Ended early — 4/6 trials" | "Ended early: 4 of 6 trials" |
  | Standalone dialog title | "Task settings — click_grid" | "Task settings: Grid Click" |
  | Config, "Modified from" line | `Modified from "Standard"` | "Changed from Standard" (the loaded configuration's name, no quotes) |
  | Follow task description | "The target travels; follow it — nothing to select — smooth pursuit." | "The target travels across the screen. Follow it; nothing is selected. Smooth pursuit." |

- **H12 Tests.** New `tests/test_design_tokens.py`: computes the WCAG ratio of every
  `CONTRAST_PAIRS` row from the hex values and checks its minimum; checks that no `#` hex literal in
  the operator-UI sheets is outside the token module (except `LEGACY_REPORT_COLOURS`); checks that
  every `font-size` in the sheets is a type-scale value. New `tests/test_copy_rules.py`: the em-dash
  grep of H11; `started_text` format; the report row labels and values of proposal §4; no "Test
  Complete!" or `·` in user-visible strings of the changed modules. Existing tests that pin old
  strings, colours or sizes are updated, not deleted.

## 4. Design

No layout change: no widget moves, no page gains or loses a control (layout is phase 2). Expected
visible effect: blue flat buttons, grey page #F4F4F4 with white cards, darker ink, larger text,
visible focus, AA-passing state colours, ISO dates, the copy of §3.2 H11 and proposal §4. Because
the body grows from 12 to 14 px and titles from 22 to 28 px, some pages may get taller; the
Setup and configuration pages already scroll. Clipping is a phase-1 defect only if a control or
text is cut off at 1920x1080 maximized; spacing that merely looks loose is phase 2.

No wireframe gate: phase 1 adds no widget and moves none (proposal §3 marks wireframe updates for
phase 2).

## 5. Scope

**In:** H1-H12; proposal §2.1, §2.2 (operator UI, accent, state tables), §2.4 radius, §2.5 sizes and
states, §4 rules 1-6 and the text-only replacements (U3, U5).
**Out:** page layout, content widths, field widths and spacing (§2.3: phase 2); status badges, glyph
tiles, the Start page Blocked block (phase 2); canvas and themes YAML (phase 3); report map, PDF
colours, report widths (phase 4); `task_settings_dialog.py` radio groups (phase 5, only its title
string is in H11); full screen during a run (phase 3); any new feature.

## 6. Acceptance criteria

- **P1** `test_design_tokens.py`: every `CONTRAST_PAIRS` row meets its ratio, computed from the
  code's hex values (proposal §2.2 numbers, ±0.02).
- **P2** No gradient and no hex colour outside `design_tokens.py` in the operator-UI sheets
  (`wtmh_theme`, `dialog_theme`, `run_bar`, `run_dialogs`, `config_widgets`, `frozen_table`,
  `rename_editor`); `LEGACY_REPORT_COLOURS` is the only exception.
- **P3** The application font is 14 px; page titles 28 px; every `font-size` in a sheet is 12, 14,
  16, 20 or 28 px.
- **P4** A grep of `src/ui`, `src/data` and `src/engine/task_info.py` for `—` finds only the `DASH`
  and `NO_DATE` definitions; no `·` in a user-visible string of the changed modules.
- **P5** Dates read `yyyy-MM-dd` on Setup (date of birth), the Test List, the report header and the
  PDF; times as `HH:mm` 24 h.
- **P6** Report rows use the proposal §4 labels and values; a missing text value reads "not
  recorded".
- **P7** Live, maximized at 1920x1080: Tab from Subject ID shows a visible focus on every control of
  Setup, the Test List, the configuration page and the Start page; a disabled checked box (Mouse +
  Switch configuration, screenshot 17) is #8D8D8D, not blue; the run bar shows the PRACTICE chip in
  a practice run; no text or control is cut off on any page (window capture, not offscreen).
- **P8** Full pytest green (except the known skip-worktree alpha checks, if run on a clean
  checkout).

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Data-layout steps 2-3 committed on `worktree-agent-a6726ce4bb2d33644` (U2); this SPEC committed on `feature/compass-task-flow` (DONE) | user OK |
| 1 | spec-implementer in a new worktree based on the data-layout commit, with this SPEC's commit cherry-picked: H1-H12 (DONE, rounds 1-2) | — |
| 2 | Hub review + full pytest; §9 questions to the user (DONE 2026-10-08) | — |
| 3 | Live check with the user (P7), together with the data-layout step 5 live check (one session, the user as subject) (DONE 2026-10-08; three bugs moved to phase 2 H13) | user |
| 4 | On the user's OK: delete the old-layout folders in `sessions/` (no backup), merge data-layout then phase 1 into `feature/compass-task-flow`, push | user |

## 8. Impl log

- **2026-10-08, claude-sonnet-5-5 (spec-implementer), plan step 1 (H1-H12), worktree `design-phase1`.**
  Not committed, not staged; `configs/default.yaml` and `configs/local_state.json` untouched; no app
  launch, no live test. The WTMH blue values come from `git show 66a3c3b:docs/design/fable-proposal.md`
  (this worktree's own copy of the proposal predates that commit and still carries the teal values; it
  also lacks `docs/design/design-system.html`).

  **New modules.** `src/ui/design_tokens.py` (H1: every colour, the type scale, spacing, radius, border
  widths, control sizes, `CONTRAST_PAIRS`, `LEGACY_REPORT_COLOURS`); `src/ui/wtmh_controls.py` (the
  fields / combo / spin / indicator / slider / table half of the dashboard sheet, split out because the
  new sheet did not fit `wtmh_theme.py` under 500 lines; `wtmh_theme.STYLESHEET` is the two halves joined).

  **Source files changed.**
  - Theme and tokens: `src/ui/wtmh_theme.py` (rewritten around tokens, 292 lines; old names kept as
    aliases; `ACCENT_GRADIENT_*` and `ACCENT_RGB` removed; `button_rule()` builds every button tier:
    primary, secondary = the old ghost and `wtmhSecondary`, tertiary `wtmhTertiary`; the danger tier is
    built from the same rule in `run_dialogs.py`), `dialog_theme.py`, `frozen_table.py`,
    `rename_editor.py`, `config_widgets.py`, `run_dialogs.py`, `add_test_dialog.py`, `report_views.py`
    (text colours), `setup_page.py` (popup colours), `start_test_page.py` (inline sheet sizes now
    type-scale tokens: 20 / 16 / 16 / 14), `dashboard_window.py` (`apply_application_font`: Segoe UI at
    14 px, called next to the Fusion call).
  - Phase-4 painters kept on today's colours through `LEGACY_REPORT_COLOURS`: `map_legend.py`,
    `report_pdf.py`, `target_map_paint.py`, `target_map_follow.py` (only their import lines and a frozen
    constant block changed; the PDF header copy and the date also changed, see below).
  - Run bar (H9): `run_bar.py` (48 px, token sheet, five labels: chip, pause marker, trial, pointer,
    tracking; buttons 36 px), `src/engine/tracking_status.py` (`RunStatus` and `run_status()` replace
    `run_status_line`; the tracking texts are now "Tracking OK" / "No gaze for 3 s" / "Waiting for gaze" /
    "Tracker disconnected"), `src/app.py` (`_update_run_bar` builds a `RunStatus`: 9 lines).
  - Copy (H10, H11, proposal 4): `src/data/report_util.py` (the single `DASH` / `NOT_RECORDED`
    definitions), `report_config.py` (rows: "Number of trials", "Trial timeout", "Inter-trial interval",
    "Gaze cursor: Shown/Hidden", "Feedback: Hit sound on, miss sound on, glow off", "Gaze smoothing: On,
    alpha 0.22, ...", "Target size: Medium (5°, 207 px)", "Selection: Dwell, threshold 0.8 s, ...";
    "not recorded" for every missing value), `report_quality.py` ("Ended early: 4 of 6 trials"),
    `report_metrics.py`, `report_cache.py`, `report_follow.py`, `report_geometry.py`, `exporter.py`
    (dashes in code or comments), `ui/report_format.py` (`started_text` "2026-10-07 17:09" /
    "not recorded"; `trial_line` "Scan path 75.4°, 8 fixations, 32 saccades"; the Outcome text cell says
    "not recorded"), `report_format_follow.py` (Outcome and Path text cells), `report_page.py` and
    `report_pdf.py` (titles without a colon, PDF title "Summary Results, <test name>", Subject / Test Date /
    Configuration Name / Evaluator / Notes say "not recorded"), `src/engine/task_info.py`,
    `src/engine/target_size.py` (the gap choices only: "Wide (1°)"), `choice_lists.py`,
    `config_widgets.py` (`choice_label` puts the px inside the brackets: "Small (3°, about 124 px)"),
    `task_settings_dialog.py` ("Task settings: Grid Click"), `task_config_page.py` and `config_form.py`
    ("Changed from Standard"), `setup_page.py` (date field `yyyy-MM-dd`, the 6 sentences, the Display line
    "Display 1920×1080 at 100 %: the recommended standard.", numeric calibration cells use `DASH`),
    `start_test_page.py` (3 Mouse notes), `run_dialogs.py` ("Test complete", heading 20 px / 600),
    `report_views.py` ("Selected trial: Trial 4"), `test_list_page.py` ("Back to Setup"), `canvas.py`
    (one comment, see section 9).
  - 40 px table rows: `frozen_table.py`, `test_list_page.py`, `setup_page.py` (details table),
    `report_tables.py` (non-compact `FitTable`).

  **Tests.** Added `tests/test_design_tokens.py` (contrast of every `CONTRAST_PAIRS` row, no hex / no
  gradient / token colours only in the sheets, the type scale, the application font, button 40 px and
  field 36 px and indicator 20 px and slider handle 20 px in every state, focus colour per control class,
  disabled checked box / radio grey, banners, tables) and `tests/test_copy_rules.py` (the em-dash grep of
  H11, interpunct-free modules, dates, report rows, proposal 4 strings): 137 tests between them. Updated 29
  existing test files (they pinned old strings, colours, the 44 px bar, `run_status_line`, `DASH` in
  report_config); none deleted; `test_run_bar.py` and `test_tracking_status.py` gained 7 tests.
  **pytest** (`-o addopts=`, venv, worktree, full run at the end): **5 failed, 2792 passed, 2 skipped in
  361 s** (2799 tests). The 5 failures are the known worktree ones (committed `configs/default.yaml`, smoothing alpha 0.35 vs 0.22):
  `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults` x4 and
  `test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`. Baseline before my
  changes in this worktree: the same 5 failed, 2648 passed, 2 skipped (2655 tests), so +144 tests.

  **Decisions inside the SPEC's room (no SPEC text overridden).**
  - Radio buttons: a checked radio is the accent disc with a white dot, drawn as a 6 px border round a
    white disc, because P2 forbids any gradient and QSS has no other way (today's dot used a
    `qradialgradient`). The disabled checked radio is the same in border-strong grey (U4). Look at it live.
  - Indicator sizes: QSS `width` / `height` are the content box, so each state subtracts its own border to
    keep the outer 20 px (measured offscreen, checked and focused included).
  - Focus: buttons, fields, text areas, combos, spin boxes, check box / radio indicators, slider handle and
    (added for P7) `QTableWidget` / the report trial table get a 2 px accent-focus border; sizes are kept
    by giving 1 px back from padding / `min-height` (button 40 px and field 36 px measured identical with
    and without focus). Spin boxes and date edits also carry `max-height` = the field height (a QSpinBox
    otherwise sizes itself 39 px). The "1 px white gap" of 2.5 is not drawn (QSS cannot); check it live.
  - Nav buttons: the active underline is white, not accent (accent blue on the #12374A bar is 1.9:1). The
    title-bar text is white (proposal: "white text").
  - Danger button hover and pressed use `danger-text` #A2191F (the proposal has no danger-hover token).
  - Scroll bar thumb: border-strong, hover text-secondary (the translucent accent thumb needed `ACCENT_RGB`).
  - `wtmhTertiary` is defined but no button uses it yet (which button is which tier is phase 2: the Test
    List side buttons; "Back to Setup" keeps `wtmhGhost`).
  - `DASH` is now defined once, in `src/data/report_util.py`, so data modules need no `ui` import;
    `report_format.DASH` / `NOT_RECORDED` re-export it, and `report_config.py` no longer has a `DASH`
    (every one of its uses was a text row). P4's grep finds only `report_util.py:DASH` and
    `test_list_table.py:NO_DATE`.
  - "not recorded" went into text places only: the config rows, Subject / Date / Configuration Name /
    Evaluator / Notes, the Outcome and Path text cells, the "Scan path / fixations / saccades not
    recorded" phrases. The Eye Metrics rows and the Follow Metric / Value rows hold figures and kept the
    dash (section 9, question 2).
  - Slider groove ratio: `#C6C6C6` under the accent is 3.56:1, not the 4.51 the proposal prints (the
    teal-era figure; a track needs 3:1). `CONTRAST_PAIRS` holds 3.56, so P1's "proposal number, +-0.02"
    cannot hold for that one row.
  - Two contrast rows beyond the proposal's table: white on border-strong (the disabled checked mark,
    3.32) and white on `danger-text` (the danger hover, 7.79).

  **Deviations from the SPEC:** none that change a hub decision. What touches files the SPEC lists as out
  of scope or leaves open is in section 9 (the `canvas.py` comment, `app.py`, `target_size.py`).
  **Left undone:** every interpunct outside the run bar and the detailed trial line; the Start page
  Blocked block; badges and glyph tiles (phase 2, as scoped). Live check P7 is the hub's.

- **2026-10-08, round 2, claude-sonnet-5-5 (spec-implementer): the §9 answers A1-A4.** Not committed, not
  staged, no app launch, configs untouched.
  - **A1 (interpuncts replaced).** `dashboard_flow.NAV_LABELS` = ("Setup", "Tests") and its docstring;
    Setup page title "Setup"; `_format_device_info` joins with ", " ("Device: GP3HD, 150 Hz, USB 3.0,
    SN 12345" / "Camera: 640×480, API v2.0"); configuration subtitle "Grid Click, subject P1"
    (`task_config_page.py`); report Input row "Gaze (GP3HD, 150 Hz), Switch" / "Mouse, Dwell 0.8 s"
    (`report_config._input_row`); PDF header "Subject: P001, Test Date: ..., Evaluator: ..." (commas, no
    `&nbsp;`). Left as answered: the Start blocker join, `DATA_MISSING`, the map legend sentences
    (`start_test_page.py`, `test_list_table.py`, `report_views.py` are now the only files with an
    interpunct; `tests/test_copy_rules.py` pins exactly those three).
  - **A2, A3:** no change.
  - **A4.** `src/engine/run_paths.py` `PATH_TOO_LONG_TEXT` = "The data folder path is too long. Move the
    program folder closer to the drive root." The motion-path words now live once, as
    `MOTION_PATH_LABELS` in `src/tasks/follow_moving.py`; `choice_lists.MOTION_PATH_CHOICES` is built from
    it and `report_config` uses it in place of `_MOTION_PATHS`, so the report's Layout row reads the page's
    exact labels, arrows included: "Horizontal ↔ path, 20% of the width per second", "Diagonal,
    top-left to bottom-right path, ..." (the trailing word "path" and the rest of the row are unchanged).
    Not changed: `report_format_follow.PATH_LABELS` ("Diagonal TL-BR", a short label for the Follow
    trial table's narrow Path column; say if it should use the full words too), and the Session Log /
    calibration log lines.
  - **Tests.** `tests/test_copy_rules.py` extended (nav labels and the Setup title, device lines,
    subtitle, Input row per mode, PDF header, the path message, the report's path words against the
    page's; the interpunct scan now covers every module of `src/ui`, `src/data`, `task_info.py`,
    `tracking_status.py` and `follow_moving.py` and expects exactly the three later-phase files). Updated
    the pinning tests in `test_config_flow`, `test_task_config_page`, `test_dashboard_flow`,
    `test_mouse_run`, `test_report_cache`, `test_report_config`, `test_report_switch_layout`,
    `test_run_paths`, `test_start_path_blocker`. The CONTRAST_PAIRS slider-groove row already holds 3.56.
  - **pytest** (venv, full run): **5 failed, 2797 passed, 2 skipped in 424 s** (2804 tests; the same 5
    known worktree failures: smoothing alpha 0.35 vs 0.22).

## 9. Implementer open questions

- **2026-10-08, interpuncts the SPEC gives no replacement for (P4 / H12 / copy rule 4).** P4 says "no
  interpunct in a user-visible string of the changed modules", but H11 and proposal 4 list replacements only
  for the run bar and the detailed trial line (both done). I did not choose replacements for the rest and
  left them in place: `src/ui/dashboard_flow.py:33` nav labels "1 · Setup" / "2 · Tests" and
  `setup_page.py:414` title "1 · Setup" (several tests pin them); `src/ui/test_list_table.py:26`
  `DATA_MISSING = " · data missing"` (Test List status text, phase-2 badges); `setup_page.py:97-99`
  "Device: GP3HD · 150 Hz · ..." and "Camera: ..."; `task_config_page.py:302` "Grid Click · Subject P1";
  `start_test_page.py:168` the blockers joined with " · " (the phase-2 Blocked block);
  `report_views.py:73-81` the two map legend sentences (phase 4, D3); `report_pdf.py:121-122` the header
  facts "&nbsp;·&nbsp;"; `src/data/report_config.py:113-115` the Input row "Gaze (GP3HD, 150 Hz) · Switch"
  / "Mouse · Dwell 0.8 s" (pinned by 4 tests). `tests/test_copy_rules.py` therefore pins the
  interpunct-free modules only (`tracking_status`, `run_bar`, `run_dialogs`, `choice_lists`,
  `report_format`, `report_format_follow`). Say which to replace and with what (a comma is the obvious one).
- **2026-10-08, dash vs "not recorded" for figures.** The Eye Metrics rows and the Follow summary rows are
  label / value rows with left-aligned figures. I read them as figures (numeric cells) and kept the dash:
  the code and its tests deliberately tell a Mouse test with no tracker ("not recorded") from a legacy
  folder or a figure that could not be built (dash), and `EYE_NOTE` explains the dash. If U5 should reach
  them, the places are `eye_rows()` and `follow_summary_rows()` and their tests.
- **2026-10-08, row height of the compact report tables.** H5 says table rows are 40 px. I applied it to
  the Test List, the Trial-by-Trial table, the Setup details table and the non-compact `FitTable`s, but
  not to the `compact=True` Test Configuration table of the Report sidebar (17 rows would be about 680 px
  of a scrolling sidebar, pushing Notes off screen; `compact` exists to stop that). Confirm, or drop
  `compact` and take 40 px.
- **2026-10-08, files outside the scope lists that I touched.** `src/ui/canvas.py` (one comment, two em
  dashes, because P4's grep covers `src/ui`; no code), `src/app.py` (the run bar's status call, 9 lines,
  needed for H9), `src/engine/target_size.py` (the `GAP_CHOICES` label only: proposal 4 lists the cell-gap
  radios; the Session Log line at :313 "Cell gap: Wide — 1° (≈41 px)" is unchanged).
- **2026-10-08, em dashes outside P4's grep that are still user-visible or logged.**
  `src/engine/run_paths.py:41` ("The data folder path is too long — move the program folder ..."), the
  calibration log lines at `src/app.py:196-199`, `target_size.py:308-313`, and comments in `src/inputs`,
  `src/tasks`, `src/engine/task_runner.py`. Not touched (outside `src/ui`, `src/data`, `task_info.py`).
- **2026-10-08, vocabulary not in the table.** The report's Layout row for Follow the Target still says
  "Diagonal (top-left to bottom-right) path" (`report_config._MOTION_PATHS`) while the configuration page
  now says "Diagonal, top-left to bottom-right". Same for "Horizontal ↔" / "Vertical ↕" on the page. Not
  in proposal 4's table, so unchanged.
- **2026-10-08, P5 names a "date of birth" field.** The Setup page has no such field; its only date is
  "Assessment Date", which now shows `yyyy-MM-dd`.

**Answers (user, 2026-10-08, via the hub):**
- **A1 Interpuncts: fix now, except the phase-2/4 ones.** Nav labels "Setup" / "Tests" and the Setup page
  title "Setup" (no number, as the approved phase-2 wireframes show); Setup device lines "Device: GP3HD,
  150 Hz, ..." / "Camera: ..." with commas; configuration subtitle "Grid Click, subject P1"; report Input
  row "Gaze (GP3HD, 150 Hz), Switch" / "Mouse, Dwell 0.8 s"; PDF header facts separated by commas (or
  separate lines, whichever reads as plain sentences). **Left for later:** the Start blocker join (phase 2
  Blocked block), Test List " · data missing" (phase-2 badge), the map legend sentences (phase 4).
  Extend `tests/test_copy_rules.py` to the newly fixed modules; update the pinning tests.
- **A2 Dash vs "not recorded":** keep the dash in the Eye Metrics and Follow-summary rows (figures; the
  dash means "could not be computed", "not recorded" means "no tracker"). No change.
- **A3 Compact report table:** keep `compact=True` rows for the Report sidebar's Test Configuration table.
  No change.
- **A4 Leftovers:** accept the three touches (`canvas.py` comment, `app.py` run-bar status call,
  `target_size.py` gap label). Also fix the user-visible `run_paths.py:41` message ("The data folder path
  is too long. Move the program folder closer to the drive root.") and make the report's motion-path words
  (`report_config._MOTION_PATHS`, incl. "Horizontal ↔" / "Vertical ↕" if they reach the report) match the
  configuration page's labels exactly. Log lines in `app.py` / `target_size.py` stay as they are.
- **Hub notes:** P5's "date of birth" was a SPEC error (the field is Assessment Date): accepted as done.
  P1's slider-groove row: the proposal's 4.51 was a teal-era figure; 3.56:1 (non-text, needs 3:1) is the
  correct value for #C6C6C6 under #1F669E and is accepted. White nav underline (accent on navy is 2.07:1)
  accepted.

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §5.2 phase 1 and §2.2 (WTMH blue). User
  decisions U1-U6 taken in this session (ordering stacked on data-layout, text-only copy, disabled
  checked #8D8D8D, "not recorded" for missing text values, no migration). Hub decisions H1-H12
  proposed, awaiting approval.
- **2026-10-08** — The user approved H1-H12 as written. Data-layout steps 2-3 committed `1d38819` (U2). SPEC committed on `feature/compass-task-flow`. Next: /spec-run step 1.
- **2026-10-08** — Step 1 implemented by spec-implementer (claude-sonnet-5-5) in worktree `design-phase1`, uncommitted: section 8 has the log, section 9 the open questions (interpunct replacements, dash vs not recorded for figures, compact table rows). Full pytest: 5 failed (known), 2792 passed, 2 skipped.
- **2026-10-08** — Round 2 (A1-A4) implemented by spec-implementer (claude-sonnet-5-5) in worktree `design-phase1`, uncommitted: interpuncts replaced except the three later-phase ones, path message and motion-path words aligned. Full pytest: 5 failed (known), 2797 passed, 2 skipped.
- **2026-10-08** - Hub review after rounds 1-2: scope matches H1-H12 plus the A1-A4 answers; out-of-scope touches (canvas.py comment, app.py run-bar call, target_size.py gap label, follow_moving.py MOTION_PATH_LABELS) accepted by the user; P1-P6 and P8 covered by tests; hub pytest in the worktree 2797 passed, 5 failed (known skip-worktree alpha checks), 2 skipped. The Follow trial table's short Path labels (Diagonal TL-BR) stay until phase 4. PARKED before the P7 live check: the device is not ready; the live check is shared with the data-layout step 5. Nothing committed.
- **2026-10-08** - Step 3 live check with the user as subject on the real GP3 HD (GP3HD 150 Hz, SN 23309153), maximized 1920x1080, app launched from this worktree; the user drove most pages by hand (qt-mcp lost the window after the modal Add Test dialog and while the window was minimized). P7: Tab focus visible on Setup, the Test List, the configuration page and the Start page; run bar shows the PRACTICE chip in a practice run; one recorded Grid Click run (6 trials) and its report + PDF read `yyyy-MM-dd HH:mm` and "not recorded" (P5, P6). Hub pytest in the worktree before the check: 2797 passed, 5 failed (known skip-worktree alpha checks), 2 skipped. Three bugs found, all moved to phase 2 (SPEC-design-system-phase2 H13) by the user's choice ("commit as is, fix later"): (1) buttons with a white fill draw the native Windows focus rectangle inside the 2 px focus border (no `outline: 0` in `button_rule`); (2) Tab inside the Setup Notes `QTextEdit` types a tab instead of moving focus (`metadata.json` notes held ten tab characters); (3) the PRACTICE chip has `min-height: 24px` but no maximum, so it stretches to the bar height. Not checked: the disabled checked box #8D8D8D under Mouse + Switch (covered by `test_design_tokens.py::test_a_disabled_checked_indicator_is_grey_not_the_accent_blue`). The PDF's tiny section headings and the "Entrie s" header break predate phase 1 and were added to SPEC-design-system-phase4 H8. Phase 1 committed on branch design-phase1.
