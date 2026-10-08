---
name: SPEC-design-system-phase1
title: Design system v1, phase 1: colour tokens, type scale, component QSS and copy rules (operator UI)
status: approved 2026-10-08 (U1-U6 user decisions, H1-H12 hub decisions approved by the user)
created: 2026-10-08
last_updated: 2026-10-08
next_step: /spec-run step 1 (spec-implementer in a worktree based on 1d38819 + this SPEC's commit)
related:
  - docs/design/fable-proposal.md (source: §2 design system v1, §4 copy rules, §5.2 phase 1)
  - docs/design/fable-evaluation.md (Task A findings the proposal cites)
  - docs/design/design-system.html (visual reference, WTMH blue; artifact https://claude.ai/artifact/URv8RdF44shQTphsYWxUCN)
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
| 0 | Data-layout steps 2-3 committed on `worktree-agent-a6726ce4bb2d33644` (U2); this SPEC committed on `feature/compass-task-flow` | user OK |
| 1 | spec-implementer in a new worktree based on the data-layout commit, with this SPEC's commit cherry-picked: H1-H12 | — |
| 2 | Hub review + full pytest; §9 questions to the user | — |
| 3 | Live check with the user (P7), together with the data-layout step 5 live check (one session, the user as subject) | user |
| 4 | On the user's OK: delete the old-layout folders in `sessions/` (no backup), merge data-layout then phase 1 into `feature/compass-task-flow`, push | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §5.2 phase 1 and §2.2 (WTMH blue). User
  decisions U1-U6 taken in this session (ordering stacked on data-layout, text-only copy, disabled
  checked #8D8D8D, "not recorded" for missing text values, no migration). Hub decisions H1-H12
  proposed, awaiting approval.
- **2026-10-08** — The user approved H1-H12 as written. Data-layout steps 2-3 committed `1d38819` (U2). SPEC committed on `feature/compass-task-flow`. Next: /spec-run step 1.
