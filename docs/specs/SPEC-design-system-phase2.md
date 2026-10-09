---
name: SPEC-design-system-phase2
title: Design system v1, phase 2: status badges, alerts with glyphs, and page layout (operator UI)
status: implemented + live-checked 2026-10-09 on branch design-phase2 (NOT merged); approved 2026-10-08 (V1-V4 user decisions, H1-H12 hub decisions approved by the user; H13 phase-1 carry-overs added by the user 2026-10-08)
created: 2026-10-08
last_updated: 2026-10-08
next_step: user merges design-phase2 into feature/compass-task-flow and pushes (then audit-fixes, preview-gaze-pointer, design-phase4); final-look items answered 2026-10-09 and fixed in round 4
related:
  - docs/design/fable-proposal.md (source: §2.3 spacing and widths, §2.5 components, §3.1-§3.6 per-page changes, §5.2 phase 2)
  - SPEC-design-system-phase1.md (tokens, type, component QSS, copy; this phase builds on it and needs its tokens)
  - docs/design/design-system.html (visual reference)
  - SPEC-subject-data-layout.md (its Start page path blocker and Test List Open Subject Folder button are kept as they are)
---

# SPEC-design-system-phase2: components and page layout

**Status: approved 2026-10-08. Branch: built on top of phase 1 (branch `design-phase1`, itself on the
subject-data-layout commit `1d38819`). Phase 2 of the five in fable-proposal §5.2.**

## 1. Origin

Phase 1 (`SPEC-design-system-phase1.md`) makes every colour and size a token and fixes the copy, but
moves nothing. Phase 2 is the part of fable-proposal §5.2 that changes **where things sit and how
state is shown**: status badges (glyph + word) in place of tinted or bold text, alerts with a glyph
tile and a state word, content and field widths, the Start page's Blocked block, the run bar's
tracking badge, the configuration page's column order, and slider length caps. The user asked for
this SPEC on 2026-10-08, while phase 1 is being implemented, and settled the four open points of the
design page that belong here (§3.1).

## 2. Current code (commit `1d38819`; phase 1 and data-layout step 6 landed `9bbb8c0`, so line numbers are stale: re-grep)

- Setup (`src/ui/setup_page.py`, 1199 lines, already over 500): page title `"1 · Setup"`;
  `tracker_status_label = QLabel("Not connected.")` (line 668); Continue to Tests carries a tooltip
  `"Still needed: ...; ...."` from `_missing_requirements()` (line 1186), no visible caption.
  `continue_blockers()` excludes the tracker and the calibration (user decision 2026-10-07: a Mouse
  test needs neither). No status badges in code; the approved `docs/wireframes/setup.md` shows a
  badge row.
- Test List (`test_list_page.py` 485 lines, `test_list_table.py` 129): side buttons all one tier;
  "← Back to Setup / recalibrate" (line 274); Not done rows marked by bold; status as text. The
  data-layout SPEC added Open Subject Folder as the last button of the column (its §4 W2).
- Configuration page (`config_form.py`, `task_config_page.py` 489, cards from `_CARDS` in
  `src/ui/settings_registry.py:437-451`): column 0 = Test, Feedback; 1 = Target, Icons, Grid Layout,
  Motion, Timing; 2 = Input, Dwell, Gaze Smoothing. `modified_label` is set to "" when unmodified, so
  the layout shifts.
- Start page (`start_test_page.py` 364): blocker banner `"Still needed before you can start: " +
  " · ".join(blockers)` (line 168) with Go to Setup; a separate path blocker line from the data-layout
  SPEC (H9, W3; Practice stays enabled under it).
- Run bar (`run_bar.py`): after phase 1, separate labels with the tracking state as coloured text
  (phase-1 H9); no glyph.
- Alerts / banners: after phase 1, white with a 1 px state border, no stripe (phase-1 H8); no glyph
  tile, no bold state word.
- Sliders (`SliderSpinRow` in `config_widgets.py`): stretch to the card width.

## 3. Decisions

### 3.1 User decisions (2026-10-08)

| # | Decision |
|---|---|
| V1 | Glyphs as the design page shows: **Not calibrated = warning triangle** (amber, like Data missing); **Skipped = dashed hollow ring**, neutral grey. Full set in H2. |
| V2 | Test List side buttons: **Run Test is the only primary**; Add New Test, Configure Test, View Report, Copy Test, Open Subject Folder are secondary; Delete Test is secondary with the red danger glyph (its confirmation dialog keeps the danger fill). |
| V3 | **Build the Setup status badges** (tracker: Disconnected / Connected beside Connect; calibration: Not calibrated / Calibrated, N points, E° beside Do Calibration) **and** a visible caption under the disabled Continue to Tests. |
| V4 | **Reorder the configuration page columns** by clinical weight (proposal §3.4 C1), with the Dwell and Gaze Smoothing column under an "Advanced" title. |

### 3.2 Hub decisions (approved by the user 2026-10-08)

- **H1 Badge helper.** New `src/ui/status_badge.py`: `StatusBadge(QWidget)` = a 24 px pill (radius
  12, padding 0 8), a 12 px glyph pixmap painted with `QPainter` (not a font character), 6 px gap,
  the word at caption 600. `set_state(kind, text)` where `kind` is one of `done, not_done,
  ended_early, data_missing, disconnected, connected, calibrated, not_calibrated, tracking_ok,
  no_gaze, tracker_disconnected, skipped`. Colours from the phase-1 tokens only. `accessibleName`
  = the word, so a screen reader and qt-mcp read the state.
- **H2 Glyph and colour per kind** (proposal §2.5 + V1):

  | Kind | Glyph | Fill / text |
  |---|---|---|
  | done, connected, calibrated, tracking_ok | filled circle | success-subtle / success-text |
  | not_done | hollow circle | header / text-secondary |
  | ended_early | half-filled circle, word "Ended early 4/6" | warning-subtle / warning-text |
  | data_missing, not_calibrated, no_gaze | triangle | warning-subtle / warning-text |
  | disconnected, tracker_disconnected | filled square | danger-subtle / danger-text |
  | skipped | dashed hollow circle | header / text-secondary |

- **H3 Alerts.** New `src/ui/alert_box.py`: `AlertBox(QFrame)` with a kind (`danger`, `warning`,
  `success`, `note`), a 20 px glyph tile (square / triangle / filled circle / "i" in a circle,
  painted), a bold state word ("Blocked:", "Warning:", "Note:"; none for success), body text at
  body-large, an optional action widget at the right edge. Every existing banner of Setup, the Start
  page and the configuration page becomes an `AlertBox`; no new banner is added. One container
  level: an alert never sits inside a card (proposal §2.4); where one does today, it moves to the
  page level directly above or below its card.
- **H4 Setup (V3, proposal §3.1 S2-S6).** Content column max 1200 px, left-aligned; field widths of
  §2.3 (Subject ID 320, date 200, Sex 240, Control Address 320, Control Port 120, Point Count 100).
  `tracker_status_label` is replaced by a `StatusBadge` beside Connect; the calibration card gets one
  beside Do Calibration ("Calibrated, 5 points, 1.8°" uses the measured mean error). The footer holds
  Continue to Tests (240 px, right-aligned) with a caption under it while disabled: **"Needs: " + the
  short names of `continue_blockers()`** (e.g. "Needs: Sex, display acknowledgement"). Because
  Continue does not wait for the tracker or the calibration (2026-10-07), the caption never lists
  them; the proposal's "Needs: tracker, calibration, Sex" example is outdated. The tooltip stays.
  Page title "Setup" (no "1 ·"). Display line and "No tracker connected" note as `AlertBox` success
  / note.
- **H5 Test List (V2, §3.2 T1, T2, T4-T6).** Table max 1200 px: Test Name 420, Task 180,
  Configuration 200, Status 180, Date 140; the button column 24 px right of the table, top-aligned.
  Status cells hold a `StatusBadge` (cell widget); bold no longer marks Not done. Tiers per V2.
  "Back to Setup" as a tertiary button without the arrow. Empty state: one line inside the table
  frame. Sorting by Status keeps working (sort key unchanged; the badge is a view).
- **H6 Configuration page (V4, §3.4 C1, C3-C5, C7).** `_CARDS` columns: **A (0)** = Test, Input,
  Target or Icons; **B (1)** = Grid Layout or Motion, Timing, Feedback; **C (2)** = Dwell, Gaze
  Smoothing, under a column title "Advanced" in heading size, text-secondary. Icons stays one card
  (size and count together) in column A, as scanning has no separate Target card. Sliders capped at
  240 px for 10 steps or fewer (with ticks), 360 px otherwise. The "Changed from ..." caption line
  is always present (empty text, fixed height) so nothing moves. Footer row centred under the three
  columns. Name dialog: heading 20 px, field 320 px. The 1500 px grid stays.
- **H7 Start page (§3.5 P1-P5).** The blocker becomes an `AlertBox` danger: "Blocked:" then one line
  per item at body-large, Go to Setup as a secondary button inside it at its right edge, 1200 px
  wide. Item wording per proposal §4: "The tracker is not connected (Setup page)." etc. The
  data-layout path blocker becomes a second `AlertBox` danger with its own text (no Go to Setup);
  Practice stays enabled under it (data-layout W3). Start is always primary (disabled primary when
  blocked), Practice secondary, Cancel tertiary, in one row under the card, left-aligned. Card 1200
  px; read-aloud block at body-large on a white card, clinician block at body on the page. The
  Mouse note as an `AlertBox` note with "No eye data will be recorded." at 600. "Practice runs 3
  targets" said once.
- **H8 Run bar (§3.6 R2).** The phase-1 tracking text becomes a `StatusBadge` (tracking_ok / no_gaze
  / tracker_disconnected). Nothing else changes.
- **H9 No behaviour change.** Every gate, enablement rule, signal and object name used by tests and
  qt-mcp stays; new widgets get object names (`wtmhStatusBadge`, `wtmhAlert`). Full screen during a
  run is phase 3.
- **H10 Run end.** `run_dialogs.py` already gets "Test complete" in phase 1; phase 2 only updates
  `docs/wireframes/run-end.md` to match. No code change there.
- **H11 Wireframes first (gate).** Update `docs/wireframes/` setup, test-list, task-config,
  start-test, run, run-end to the decisions above, render them, the user approves before any code.
- **H12 Tests.** New `tests/test_status_badge.py` (every kind: glyph shape by pixel sample, colours,
  accessibleName) and `tests/test_alert_box.py`; Setup caption from `continue_blockers()`; Test List
  status cells are badges and sorting still works; `_CARDS` column order; the "Changed from" line
  keeps its height when empty; Start blocker lists one item per line. Existing tests updated, never
  deleted.
- **H13 Phase-1 carry-overs (added 2026-10-08, user: "commit phase 1 as is, fix later").** Three
  bugs from the phase-1 live check: (1) a button with a white fill (Load Calibration File, the
  secondary/ghost tier) draws the native Windows focus rectangle inside its 2 px focus border when
  reached by Tab: `wtmh_theme.button_rule` gets `outline: 0` (as `dialog_theme` already has), and
  every other QSS-styled focusable control in the operator sheets is checked for the same; (2) Tab
  inside the Setup Notes `QTextEdit` types a tab character instead of moving focus:
  `setTabChangesFocus(True)` on it (and on any other multi-line edit in the operator pages); (3)
  the run bar's PRACTICE / PREVIEW chip has `min-height: 24px` and no maximum, so it stretches to
  the bar height: a fixed 24 px pill, centred vertically in the bar.

## 4. Design

The wireframes of step 1 (H11) are the design; they are drawn from proposal §3.1-§3.6 with the
changes of §3.1 and §3.2 above, and from the design page's component samples (badges, alerts, Test
List, Setup cards, run bar).

## 5. Scope

**In:** H1-H13; proposal §2.3 widths and spacing for the operator pages, §2.5 badges, alerts,
SliderSpinRow length, §3.1 S2-S6, §3.2 T1, T2, T4-T6, §3.3 A2 (focus already phase 1), §3.4 C1, C3-C5,
C7, §3.5 P1-P5, §3.6 R2.
**Out:** tokens, type, focus, disabled styling, copy strings (phase 1; except the H13 fixes); canvas, themes, full screen
(phase 3); report Summary / Detailed / PDF incl. the Outcome badge (phase 4, which reuses
`StatusBadge`); `task_settings_dialog.py` (phase 5); any new gate or feature.

## 6. Acceptance criteria

- **Q1** Widths of H4-H7 measured on the **maximized window** at 1920x1080 (window capture, never
  offscreen sizeHint), ±4 px.
- **Q2** Every status in the Test List, Setup and the run bar is a `StatusBadge` with glyph + word;
  no state is carried by bold or tint alone.
- **Q3** The Start page Blocked alert lists one item per line with Go to Setup inside it; the path
  blocker is a separate alert; Practice stays enabled under the path blocker only.
- **Q4** Start keeps the primary tier when disabled; Run Test is the only primary on the Test List.
- **Q5** The configuration page does not move when "Changed from ..." appears (pixel position of the
  first card unchanged); columns follow H6 for all four tasks.
- **Q6** No left stripe and no tinted banner remain; no alert sits inside a card.
- **Q7** Setup shows the caption "Needs: ..." exactly when Continue is disabled, with the
  `continue_blockers()` items.
- **Q8** Full pytest green (except the known skip-worktree alpha checks); live check passes (§7).
- **Q9** H13: Tab onto a white-fill button shows only the 2 px focus border (no inner native rectangle, window capture); Tab in Setup Notes moves to the next control; the PRACTICE chip is 24 px high and centred in the run bar.

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Phase 1 implemented and reviewed (DONE 2026-10-08, merged `f2376d3`) | — |
| 1 | Wireframes: setup, test-list, task-config, start-test, run, run-end (H11) — **DONE 2026-10-08, user-approved** | **WF gate** |
| 2 | spec-implementer in a worktree based on the phase-1 result: H1-H10, H12, H13 — **DONE 2026-10-09** (3 rounds) | — |
| 3 | Hub review + full pytest; §9 questions — **DONE 2026-10-09** | — |
| 4 | Live check, maximized 1920x1080: every page captured; Setup badges with `tools/fake_gazepoint_server.py` (connected, calibrated) and with no tracker; one Practice run for the run bar badge. Needs the user only for the final look, not as a gaze subject — **DONE 2026-10-09** (fake tracker, unattended) | user |
| 5 | Commit on the user's OK — committed on design-phase2 only (user authorization 2026-10-09); merge + push await the user | user |

## 8. Impl log

### 2026-10-08, step 2 (spec-implementer, claude-sonnet-5-5), worktree `design-phase2`, nothing committed

**Done:** H1-H10, H12, H13. H10: `docs/wireframes/run-end.md` already matches `run_dialogs.py`
("Test complete" at 20 px, danger fills kept), so it is unchanged and no code changed there.

**New modules** (`src/ui/`): `glyphs.py` (the painted glyph shapes), `status_badge.py` (H1, H2:
`StatusBadge`, 12 kinds, object name `wtmhStatusBadge`), `alert_box.py` (H3: `AlertBox`, object name
`wtmhAlert`, kind property, own style sheet), `page_layout.py` (the 1200 px column, `labeled()` fields,
the spacing and width constants), `setup_status.py` (the Setup "Needs: ..." names, the two badge states,
the calibration error in degrees), `config_footer.py` (the centred footer row).

**Changed:** `setup_page.py` (H4; 1190 to 1245 lines, the new widgets are in their own modules),
`test_list_table.py` and `test_list_page.py` (H5, V2), `settings_registry.py` (`_CARDS`, H6), `config_form.py`,
`task_config_page.py`, `slider_spin.py`, `config_save_dialogs.py` (H6, C7), `start_test_page.py` (H7),
`run_bar.py` (H8, H13.3), `wtmh_theme.py` and `wtmh_controls.py` (H13.1 `outline: 0`; a `wtmhCaption` rule, a
`cfgAdvancedTitle` rule, a `wtmhEmptyTable` rule), `report_page.py` (H13.2, one line), `engine/input_choice.py`
(the tracker and calibration blocker sentences, see below).

**Tests added** (7 files, all offscreen): `test_status_badge.py`, `test_alert_box.py`, `test_test_list_badges.py`,
`test_setup_phase2.py`, `test_start_page_phase2.py`, `test_config_page_phase2.py`, `test_phase1_carryovers.py`.
**Tests updated, none deleted:** `test_test_list_page.py` (no bold), `test_start_test_page.py`,
`test_start_path_blocker.py`, `test_mouse_run_gate.py`, `test_run_flow.py`, `test_run_blockers.py`,
`test_input_choice.py` (wording, two surfaces, `wtmhAlert` name), `test_run_bar.py` (tracking badge, chip),
`test_setup_subject_id.py` (hint under the field, no QFormLayout), `test_settings_layout.py`,
`test_input_settings.py`, `test_task_config_page.py` (card order, always-present "Changed from" line),
`test_design_tokens.py` and `test_copy_rules.py` (the new modules join the no-hex scan; the Start page no
longer holds an interpunct).

**pytest** (whole suite, from the worktree root): 5 failed, 2993 passed, 2 skipped (3000 collected; before any change: 5 failed, 2785 passed, 2 skipped; counted from the progress lines, since `addopts = -q` plus `-q` hides pytest's own summary line). The failures are the known
skip-worktree alpha checks only (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`
and the four `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`: this worktree's
`default.yaml` has alpha 0.35, the tests expect 0.22). Baseline before any change: the same 5.

**Deviations from the SPEC:** none of the decisions changed. Interpretations the hub should look at in the live check:

1. **Object names.** An `AlertBox` is `wtmhAlert` with a `kind` property (H3, H9), so the old `wtmhAlertInfo /
   Warning / Success / Error` names are gone from the Setup, Start and configuration pages;
   `test_start_path_blocker.py` pinned `wtmhAlertError` on `path_alert` and now checks `wtmhAlert` + `kind() ==
   "danger"`. The old rules stay in `wtmh_theme.py` for the two banners phase 4 and 5 own (report page,
   standalone settings dialog). `tracking_label` of the run bar keeps its name `runBarTracking` on the badge, and
   every `*_label` attribute pages exposed for their alerts (`banner_label`, `path_alert_label`, `mouse_note_label`,
   `display_ok_label`, `calibration_alert_label`, `fit_hint_label`, `gaze_note_label`, ...) still exists. The
   removed attribute is `tracker_status_label` (H4: replaced by `tracker_badge`); what the last attempt did
   ("Connecting...", "Unreachable: ...") is now `tracker_message_label` under the buttons.
2. **No alert inside a card (H3), so the Display section and "Before You Start" have no card**: a card would hold
   only its title. They are a section title, the alert and (Display) the acknowledgement box on the page, as the
   approved wireframe draws them. The rate-warning and calibration alerts sit directly under their cards in the
   page's scroll content; the calibration-details table stays inside the Calibration card (it is not an alert).
3. **Blocker wording (H7).** The tracker and calibration sentences in `engine/input_choice.py`, and the Subject ID,
   date and Sex ones, now end "(Setup page)." (proposal 4: "The tracker is not connected (Setup page)."); four test
   files pinned the old text and were updated. The display sentence keeps "Tick the acknowledgement on the Setup
   page." (see section 9).
4. **Help line (P5).** `HELP_TEXT` lost "Help:" and its practice sentence ("Practice runs 3 targets" is said once, in
   the clinician text); the alert's own word is "Note:".
5. **Columns 1200 px with the scroll bar beside them.** Setup and Start make their column 1210 px (1200 + the
   theme's 10 px scroll bar) and limit the scroll content and every page-level alert to 1200 px, so the cards are
   1200 px wide whether or not the bar shows. The Start page's button row stays pinned under the scroll area (as
   before, so a small or scaled window never clips Start): with short instructions at 1080 px there is empty
   page between the clinician text and the row, not "directly under the card".
6. **Test List table width.** Columns 420 / 180 / 200 / 180 / 140 are fixed; the table is 1122 px (columns + frame),
   widened by the scroll bar's width only while one shows. The Status item keeps its text and sort key (hidden
   under the badge by a delegate); a row whose run folder is gone shows "Data missing" whatever its status was
   (the badge tooltip has the full status). Qt moves a cell widget with its item when the table sorts (checked).
7. **Calibration badge unit.** "Calibrated, 5 points, 1.8°": the device's mean error is in screen px, so it is
   turned into visual angle with the same scale and viewing distance the configuration page uses for target sizes
   (`error_degrees`, divided by the device pixel ratio). Left out when the device gave no error.
8. **Spacing (2.3).** Done where it cannot cost vertical room: 32 px page gutter, 24 px card padding and gaps and 16 / 4
   px field gaps on Setup and Start, 32 px gutter on the Test List and configuration pages. The configuration page's
   vertical spacing and card padding are unchanged (the Advanced title and the alert boxes already add height; the
   no-scroll-at-1080 check is yours).
9. **Shared widget.** `SliderSpinRow` is also used by the standalone settings dialog (phase 5), which therefore
   gets the length caps, ticks and the 88 px spin box too.
10. **Report page.** H13.2 says "any other multi-line edit in the operator pages", so the report page's Notes box got
    `setTabChangesFocus(True)` (one line; nothing else in that file changed).
11. **H13.1 cannot be seen offscreen.** The native focus rectangle is drawn by the Windows platform style; offscreen
    Fusion paints none, with or without `outline: 0`. The tests pin the style sheet text (every button tier, the nav
    button, fields, text areas, check boxes, radios, sliders, tables); Q9's window capture is yours. `outline: 0` is
    in `button_rule` (so also the run-end dialogs' danger tier) and in the rules of the controls above.

**Finding, not fixed (phase 1):** `QLabel#wtmhMuted { color: TEXT_SECONDARY }` loses to `QWidget#wtmhDashboard QLabel
{ color: INK }` (the longer selector is more specific), so every `wtmhMuted` label renders in ink, not grey
(measured by pixel in a themed container). The new captions use a rule with the dashboard scope
(`wtmhCaption`, `cfgAdvancedTitle`) and render grey. Making `wtmhMuted` the same is a one-selector change in
`wtmh_theme.py`; I left it, it is phase-1 styling.

**Left undone:** the bold "No eye data will be recorded." of the Mouse note (section 9).

### 2026-10-09, round 2 (spec-implementer, claude-sonnet-5-5), same worktree, nothing committed

Answers of section 9 (2026-10-09) applied; no new open question.

1. **Mouse note, option (b).** `MOUSE_NOTE_NO_TRACKER` is now "Mouse test. The tracker is not connected." and
   `MOUSE_NOTE_NOT_CALIBRATED` "Mouse test. The tracker is not calibrated."; the new `MOUSE_NOTE_NO_EYE_DATA` is "No eye
   data will be recorded." `AlertBox` gained `set_emphasis(text)` / `emphasis()` / `emphasis_label` (object name
   `wtmhAlertEmphasis`, weight 600, a plain-text label under the text label, hidden when empty), so
   `mouse_note_label.text()` is the first sentence only and the second is its own label inside the note. The Start page
   shows the emphasis for the no-tracker and not-calibrated variants and hides it for "Mouse test. Eye data will be
   recorded alongside." (the one variant without the clause, unchanged). Tests updated, none deleted:
   `test_copy_rules.py`, `test_mouse_run_gate.py` (also checks the second sentence comes and goes with the tracker),
   `test_start_page_phase2.py`, `test_alert_box.py` (the label's weight is DemiBold, the text label's Normal; it sits
   under the text). Not touched: the sentence in `docs/wireframes/start-test.md` (line 31, and its html) still has the
   old one-sentence note; re-render when the wireframes are next updated.
2. **Blocker wording:** unchanged (approved).
3. **`wtmhMuted` specificity fixed** in `wtmh_theme.py`: the rule is now `QLabel#wtmhMuted, QWidget#wtmhDashboard
   QLabel#wtmhMuted { color: TEXT_SECONDARY }` (the bare selector stays for a sheet used without the scope name), plus
   `QWidget#wtmhDashboard QLabel#wtmhMuted:disabled` in TEXT_DISABLED (the scoped rule would otherwise outweigh the
   disabled-label rule). The dead `wtmhBadge*` label rules got the same scoped selector. Audit of every label colour rule of
   the sheet: `wtmhPageTitle` / `wtmhSectionTitle` set ink, the same as the generic rule, so nothing changes; the title
   bar (`QWidget#wtmhTitleBar QLabel`) ties with the generic rule and wins by coming later (white, test added); the
   disabled-label rule has a pseudo-class and wins; `wtmhCaption` and `cfgAdvancedTitle` (phase 2) already carried the
   scope; AlertBox and RunBar style themselves (a widget's own sheet beats an inherited one). `wtmhMuted` is the only
   rule that lost. New `tests/test_muted_labels.py` (19 tests): the colour that renders, by pixel sample and by the
   resolved palette, for `wtmhMuted`, `wtmhCaption`, `cfgAdvancedTitle` (TEXT_SECONDARY) and for plain, page-title and
   section-title labels (ink); a disabled muted label; the unscoped sheet; the title bar still white; the rebuilt old
   sheet renders ink (the bug); and a sweep of every label on the Setup, Test List (with and without tests), Start,
   configuration (two tasks) and report pages and the save-as dialog: a label named muted / caption / Advanced title is
   TEXT_SECONDARY, and no other label is (no ink label turned grey). The labels that are grey now: the Subject ID hint,
   the tracker message and device lines, the calibration-details empty line, the Test List message / unreadable /
   empty-state / "Changes are saved automatically." lines, the Start page practice and note lines, the configuration
   page subtitle and footer reason, the save-as dialog's reason, the report's plain-text helper lines, the rename
   editor's error line.

**pytest** (whole suite): 5 failed, 3015 passed, 2 skipped (3022 collected, counted from the progress lines). The 5 are
the known skip-worktree alpha checks, as in round 1 (2993 passed then; +22 now: 19 muted-label tests, 1 AlertBox
emphasis test, 2 Mouse-note tests).

### 2026-10-09, round 3 (spec-implementer, claude-sonnet-5-5), same worktree, nothing committed

**Defect (live check, Q1 / H4): Setup's "Continue to Tests" was 157 px wide, not 240.** Cause: the tiers' QSS `min-width`
(`button_rule`) replaces the minimum a widget's own `setFixedWidth` set, when the widget is polished, so the button kept only
its maximum (240) and the layout, which right-aligns it, gave it its text width. Offscreen it passed because the offscreen
font's text is wider than 240 px, and the round-1 test read the properties of an unstyled page. Fix (`setup_page.py`,
`page_layout.py`): the 240 px (`CONTINUE_WIDTH`) is now the width of a plain slot widget in the footer that the button fills,
right-aligned at the column's right edge with the "Needs: ..." caption under it; nothing else changed. Checked against the old
way: in a themed window a right-aligned `setFixedWidth(240)` button with a short label measures 96 px (minimum 96, maximum 240).
Tests (`test_setup_phase2.py`): the footer test now pins the 240 px slot, the 64 px height and the 1200 px width; two new
tests build the page under the dashboard's own sheet, show it and measure the button: 240 px for the real label and for a short
one (a narrower font than offscreen), its right edge on the column's right edge (32 + 1200), the caption under it with its right
edge on the button's, and still 240 px once Continue is enabled and the caption is gone.

**pytest** (whole suite): 5 failed, 3018 passed, 2 skipped (3025 collected, counted from the progress lines). The 5 are the known
skip-worktree alpha checks, as before (3015 passed in round 2; +3 now: the two Continue width cases and the caption test).

### 2026-10-09, fix round 4 (spec-implementer, claude-sonnet-5-5), same worktree, nothing committed

Fix round of the user's final-look answers (section 9, 2026-10-09 "after the unattended run"): (1) the configuration
page fits a maximized 1920x1080 window without a vertical scroll, (2) a disabled primary is a pale WTMH blue.

**1. Fit at 1080.** Measured with Segoe UI loaded into the offscreen platform (`QFontDatabase.addApplicationFont`,
Fusion, the app font of `apply_application_font`, a fake 1920x1032 screen so the shrink hints are hidden as they are
live): this reproduces the hub's live numbers exactly (Test 471, Input 225, Target 143, column A 871), so the figures
below are real-metric, not the 10 % understated fontless proxy. Column A (cards plus gaps), before then now:
click_static 871 to 696, click_grid 871 to 696, follow_moving 763 to 598, scanning 969 to 786 (Icons 241 to 217). Cards:
Test 471 to 344, Input 225 to 201, Target 143 to 127. The scroll viewport grows from 784 to 800 px (page margins and
spacing, below), so the slack is 104 px (static, grid), 202 px (follow), and **14 px for scanning**. Column B of click_grid
(the other tall one) is 780 before and 712 now with its shrink hint hidden; the hint, when a chosen grid does not fit, is a
89 px alert plus a gap and does scroll the page: that is a warning state, not the standard page. Changes:
- Test card (`config_form.py`): the "Changed from ..." caption is no longer on a row of its own: it sits at the right of
  the "Configuration Name" label's row (always present, fixed 20 px high, so Q5 holds: nothing moves when it appears) and
  [Reset to defaults] sits on the row of the box (the box takes the width, the button keeps its own: `Ignored` / `Fixed`
  size policies, so a 40-character saved name cannot squeeze it); Notes 84 to 56 px (two lines). `_add_config_extras` became
  `_name_field`. The caption is an `ElidedLabel` (`config_widgets.py`): it never asks for width, `text()` and the tooltip
  keep the whole text, the paint cuts it with an ellipsis, so a long name cannot widen the card. Not hidden when empty (the
  suggestion of the brief): the row it shares with the label has to be there anyway.
- Spacing, all on the 4 px scale (`SPACING_SCALE`): card padding 14 to 12 vertical (16 horizontal as before); a label
  4 px above its control (`LABEL_GAP`, it was 8); rows 8 apart; the title's own 6 px margin is the gap under it (it was
  6 + 8); radio buttons 4 apart (was 6); cards 12 apart in a column (was 16), columns still 16 apart; the page's margins
  20 to 16 above and below and its spacing 16 to 12 (`task_config_page.py`). The constants are in `config_form.py`
  (`CARD_PAD_V`, `ROW_GAP`, `CARD_GAP`, `COLUMN_GAP`) and `RADIO_GAP` in `config_widgets.py`.
- Nothing removed or hidden: the same controls, object names, signals and tooltips (`cfgConfigName`, `cfgReset`,
  `cfgNotes`, `wtmhCaption`, ...).

**2. Disabled primary.** New tokens `ACCENT_DISABLED_FILL #BCD1E2` (the accent at 30 % over white) and
`ACCENT_DISABLED_TEXT #385A76` (a blue-grey; **4.62:1** on the fill, the brief asked for 3:1; a `CONTRAST_PAIRS` row pins it).
`button_rule` takes `disabled_fill` / `disabled_text` (default: the phase-1 grey) and only the primary tier passes the pale
blue, so it applies to every `wtmhPrimary` and to `cfgSave`: Start, Run Test, Continue to Tests, Do Calibration, Connect, the
report's Save & Continue, the Add Test dialog, the settings dialog and the run-end dialogs' primaries. Secondary, tertiary,
the danger tier and the run bar's buttons keep the grey. The border takes the fill as before, so the button does not change
size. Clash with a SPEC rule: phase-1 H5 and proposal 2.5 say every disabled tier is #E0E0E0 / #6F6F6F; the user's answer
(section 9, 2026-10-09) is newer and names the primary, so I followed it; `docs/design/fable-proposal.md` 2.5 and
`docs/design/design-system.html` still show the grey disabled primary and were not edited.

**Tests added** (all offscreen): `test_config_page_phase2.py` (the column A budget per task and at least 110 px shorter than
before, the 690 px budget and no taller column for the three pages with a Target card, spacing on the scale, Notes 56 px,
the caption on the label row and Reset on the box's row, a 40-character name neither widening the card nor squeezing Reset,
`ElidedLabel`); `test_theme_controls.py` (the pale-blue rule text, the colour is the accent's hue and paler than the hover
tint, its contrast, the painted pixel of a disabled primary versus ghost and tertiary, and Start / Run Test / Continue /
Do Calibration of the real pages). **Tests updated, none deleted:** `test_theme_controls.py` (the three disabled-primary tests
and the fixed-name-buttons test now expect the pale blue for the primary and cfgSave and the grey for the rest);
`design_tokens.CONTRAST_PAIRS` gained one row, which `test_design_tokens.py` checks.

**pytest** (whole suite, from the worktree root, `-p no:cacheprovider -o addopts="" -q -rfE`): `5 failed, 3033 passed, 2
skipped in 647.43s` (3040 collected; 3018 passed before this round, +15 new tests). The 5 are the known skip-worktree alpha
checks (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and the four
`test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`), as in rounds 1 to 3.

**Deviations from the brief:** (a) the offscreen budget test pins 690 px for click_static, click_grid and follow_moving but
**720 px for scanning**: its offscreen sum is 716 (Icons is 76 px taller than Target), although its real column is 786 px
against the 800 px viewport; getting 716 under 690 would have meant cramping every card further. It is 176 px shorter than
before, so the "at least 110 px shorter" clause holds. (b) The caption is not hidden when empty; see above.
**For the live check:** scanning has only 14 px of slack, so look at it first; if it scrolls, the cheapest remaining
levers are the 12 px card gap (to 8) and the title margin (6), or moving Icons to column B, which is H6's decision and not
mine. `docs/wireframes/task-config.md` (and its html) still draw the caption and Reset on rows of their own and a taller Notes
box; not updated.

### 2026-10-09, fix round 5 (spec-implementer, claude-sonnet-5-5), same worktree, nothing committed

Fix round of the user's "empty space" decisions (section 9, last entry, 2026-10-09), which override H4 / H5 / H8 where they
conflict: (1) full width, (2) two cards per row on Setup, (3) the "Advanced" column title renamed.

**1. Full width.** `page_layout.py`: `CONTENT_MAX_WIDTH`, `SCROLLBAR_GUTTER` and `content_column()` are gone (no
`wtmhPageColumn` widget, no `content_column_widget` attribute, no trailing stretch); `page_frame(page)` gives a page a plain
`QVBoxLayout` with the 32 / 24 px margins and 16 px spacing. Users checked: `setup_page.py` and `start_test_page.py` (the only
two importers; `config_form.CONTENT_MAX_WIDTH` 1500 was a different constant, removed in round 5c below).
- Setup: the scroll area, the gaze note and the footer have no maximum width. Continue to Tests keeps its 240 px slot and sits at
  the right edge of the full-width footer (the window's right gutter), the "Needs:" caption under it. The scroll bar is the
  scroll area's own, beside the cards (the cards' area is the scroll area less the bar; tested).
- Start: the card, the scroll content and every alert (`banner`, `path_alert`, `mouse_note`, `help_bar`) have no maximum width; the
  buttons stay one row at the left.
- Test List: `TABLE_MAX_WIDTH`, `COLUMN_WIDTHS`, `fitted_width()`, `_fit_width()` and the table's fixed width are gone. Test Name is
  a `Stretch` column (never below `NAME_MIN_WIDTH` = 240 through the table's minimum width), Task 180 / Configuration 200 /
  Status 180 / Date 140 stay `Fixed` (`OTHER_COLUMN_WIDTHS`); the viewport scroll bar is absorbed by Test Name, so no column is cut.
  Body layout: the table side has stretch 1, the button column follows 24 px to its right with no trailing stretch, so it ends at
  the right gutter. The empty-state frame has no fixed width, it fills what the table would.

**2. Setup, two cards per row** (first built as grid rows; changed to independent columns in round 5b below). New
`CardGrid` in `page_layout.py`: two columns of equal stretch, top-aligned, 24 px (`CARD_GAP`) across and down, `add_card()` /
`add_wide()` / `finish()`. Order: Subject & Session Info | Tracker Connection (its rate-warning alert directly under it), Display |
Calibration (its alert under it), then Before You Start on a row of its own. New `FlowLayout(QLayout)` (same module): the Calibration card's four buttons and the badge wrap onto a second
line when the half-width card is narrower than they are, one row otherwise; `device_info_label` now wraps. Attributes added for
tests and the hub: `subject_card`, `tracker_card`, `calibration_card`, `display_section`, `card_grid`. Fields keep their H4 widths.
Measured with Segoe UI loaded into the offscreen platform and the dashboard sheet (scratchpad probe, not in the repo): at a
1920 wide window the cards are 900 px each, 24 px apart, four calibration buttons and the badge on one line; at 1366 the cards
are 623 px, the buttons wrap ("View Calibration Details" and the badge on the second line), no horizontal scroll bar at 1920,
1366 or 1280 (at 1920 and 1366 also with a calibration and the details table open; the long alerts are in the unit test).

**3. Rename.** `config_form.ADVANCED_TITLE` = "Gaze Pointer Settings" (the constant, `ADVANCED_COLUMN` and the object name
`cfgAdvancedTitle` keep their names: title text only). Comments in `config_form.py`, `settings_registry.py` and four test files
updated.

**Wireframes (text only, not rendered; the `.html` files are stale until the hub renders them):** `docs/wireframes/setup.md` (full
width, two cards per row, Before You Start across, footer at the right edge, Display placement), `test-list.md` (table fills the
window, Test Name stretches, buttons at the right side, empty frame), `start-test.md` (alert and card as wide as the page),
`task-config.md` (the title and the two `C ·` headings). `task-config.md` still draws Reset and the "Changed from" caption as in
round 3 (see round 4).

**Tests.** New `tests/test_full_width_layout.py` (22 tests; a 7 px fallback font fixture gives the offscreen platform the
proportions of Segoe UI 14 px, because its own fallback is about twice as wide and would make the display checkbox 756 px):
two cards share the top row at 1920 and 1366 (same top), equal widths and 24 px across = down (rewritten in round 5b), fields keep their
widths, Before You Start spans both columns, no sideways scroll with a calibration + details + long alerts, calibration buttons
inside their card at both widths, one row wide / wrapped narrow, the footer, `FlowLayout` (wrap, height for width, centring,
hidden items), `CardGrid`, the removed constants, and the column C title text on all four tasks. Updated, none deleted:
`test_setup_phase2.py` (footer without a cap, Continue at the page's right gutter, the page fills the window with the bar beside the
cards), `test_start_page_phase2.py` (buttons at the gutter, card and alerts as wide as the page at 1920 and 1366),
`test_test_list_badges.py` (columns: Test Name stretches and the rest keep their widths, no maximum at 1920 / 1366, only Test Name
grows with the window, many rows, buttons at the right side, the empty frame), `test_config_page_phase2.py` (title text),
`test_muted_labels.py`, and comments in `test_settings_layout.py`, `test_task_config_page.py`.

**pytest** (whole suite, from the worktree root, `-p no:cacheprovider -o addopts="" -q -rfE`): `5 failed, 3058 passed, 2 skipped in 627.88s (0:10:27)` (3065 collected; 3033 passed before this round, +25: the 22 new tests and +3 in `test_test_list_badges.py`, whose four width tests became seven, the parametrised no-maximum test counting twice). The 5 are the known skip-worktree alpha checks (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and the four `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`). After the last small edits (lint fixes, docstring rewraps) the ten test files this round touches or depends on were rerun: 369 passed.

**Deviations from the brief:** none of the decisions changed. Readings the hub should look at:
1. "Any other card after them flows the same way": Before You Start is a one-line note and not a card, so it is a row of its own
   across both columns (a half-width cell with an empty right half looked worse). `CardGrid.add_card()` would put a future card at the foot of the next column.
2. The optional one-card-per-row fallback below about 1100 px is **not** built (a resize-driven switch can flap when the vertical
   bar appears). Two columns work down to roughly a 1050 px window (the Tracker card needs 504 px: address 320 + port 120 + gap 16 +
   padding); narrower than that Setup would scroll sideways. I found no minimum window width set in `dashboard_window.py` or `main_window.py`.
3. At 1366 px the per-point calibration table (7 equal columns in a 573 px card) has 80 px columns: the position cells
   ("0.502, 0.503", about 77 px of text plus padding) and the longer headers are cut with an ellipsis. Not a page scroll; left as
   it was (sizing the narrow columns to their content gave the position columns no more room, so I reverted that try).
4. When the scroll bar shows, the cards end 10 px before the footer's right edge (the bar takes the room; the footer and the page-level
   alerts span the full width). The old 1210 px column hid this; it is not visible when the page does not scroll.
5. Spacing of the calibration buttons is 6 px across (as before) and 8 px between lines.

**Left undone:** the `.html` wireframes (hub renders); `docs/wireframes/task-config.md` round-4 drawing (Reset / caption rows).

**Round 5b (hub live check, same day): Setup is two independent columns, not grid rows.** The row height followed the taller card
(Subject about 443 px, Tracker about 200 px), leaving about 250 px empty under Tracker. `CardGrid` is now a `QVBoxLayout` holding a
`QHBoxLayout` of two equal-stretch `QVBoxLayout` columns (24 px between everything, a stretch at the foot of each column keeps the
cards at the top): Subject over Display on the left, Tracker over Calibration on the right, Before You Start across both under
them; each card's alert stays directly under it and moves only its own column. The column layouts are attached before any card is
added, so the cards are reparented in call order and Tab/reading order stays Subject, Tracker, Display, Calibration (pinned by a
test of the focus chain). Display stays a title plus an alert, not a card: making it one would put its alerts inside a card, which
H3 forbids, so it is not a one-line change. Tests in `tests/test_full_width_layout.py` updated (none deleted): the two-cards test now
checks the shared top row and the stacked columns, the equal-width / gap test measures the gap down inside a column, new tests for
an alert staying under its card, the Tab order, `CardGrid` unit tests (alternating columns, wide row, reparent order). Affected
files run only (no full suite): `test_full_width_layout.py` 27 passed. `docs/wireframes/setup.md` text updated, not rendered.

**Round 5c (new user decision, relayed by the hub): the configuration page is full width too.** `config_form.CONTENT_MAX_WIDTH` (1500) is
removed: the card grid has no maximum width, so the three columns (Test / Input / Target, the task cards, Gaze Pointer Settings)
share the viewport equally inside the 32 px gutters. `config_footer.centered_footer(buttons, message)` lost its `max_width`
argument: the footer row is as wide as the grid, the buttons still centred under the three columns, the reason text still to their
right. Nothing is moved or hidden; the round-4 rule holds: at a maximized 1920x1009 window with Segoe UI and the dashboard sheet
(scratchpad probe) none of the four tasks has a vertical or horizontal scroll bar, the cards are 600 px wide, and the card heights
are the round-4 ones (Test 344, Input 201, Target 127, Icons 217, Input 103 for Follow the Target); the budget tests pass
unchanged. Tests: `tests/test_full_width_layout.py` +14 (no cap left, three equal columns reaching both gutters at 1920 and 1366
for each of the four tasks, wider cards are not taller than at 1500 px for every card, the footer stays centred); updated, none
deleted: the footer test of `test_config_page_phase2.py` (full width instead of 1500) and the `maximumWidth() == 1500` line of
`test_the_cards_scroll_above_a_pinned_footer` in `test_task_config_page.py`. `docs/wireframes/task-config.md` text
updated, not rendered. Affected files run only (no full suite): every test file that touches the configuration page, the Setup page,
the Start page or the Test List (about 1100 tests in two runs): all pass except the 5 known alpha 0.22 vs 0.35 checks.

## 9. Implementer open questions

- **2026-10-08, Mouse note emphasis (H7 / P4).** H7 and the proposal ask for "No eye data will be recorded."
  at weight 600 inside the Mouse note. The notes are today one sentence each ("Mouse test. The tracker is not
  connected, so no eye data will be recorded.", fixed by phase-1 copy and pinned by `test_copy_rules` and
  `test_mouse_run_gate` as the label's whole text), so there is no separate sentence to bold, and a partial bold
  needs rich text, which would change `mouse_note_label.text()`. Not done: the Mouse note is a `note` `AlertBox` at
  the alert's body weight. Decision needed: (a) leave it, (b) split the copy into two sentences ("Mouse test. The
  tracker is not connected. No eye data will be recorded.") and bold the second with a second label, or (c) bold the
  clause with rich text and relax the two pinned tests.
- **2026-10-08, blocker wording beyond the three examples (H7).** Proposal 4 gives three items ("The tracker is not
  connected (Setup page).", "No calibration yet (Setup page).", "Sex is not selected (Setup page).") and H7 says
  "etc.". I applied the same "(Setup page)." ending to "Subject ID is empty" and "Assessment date is empty" and left
  the display item as it was ("The display is not 1920x1080 at 100 %. Tick the acknowledgement on the Setup page.",
  it already names the page and says what to do). The sentences are the constants in `setup_status.py` and
  `engine/input_choice.py`; changing one is a one-line edit plus its pinned test.

- **2026-10-09, user answers (hub).** (1) Mouse note: **option (b)**. Split the copy into "Mouse test. The tracker is
  not connected." and a second label "No eye data will be recorded." at weight 600, both inside the note `AlertBox`;
  update the pinned tests (`test_copy_rules`, `test_mouse_run_gate`) to the new copy (update, never delete). Apply the
  same split to every Mouse-note variant that ends in the no-eye-data clause. (2) Blocker wording: **approved as
  done** ("(Setup page)." ending on Subject ID / date / Sex; display sentence unchanged). (3) New, user decision:
  **fix the phase-1 `wtmhMuted` specificity bug in phase 2** (muted labels render in ink because
  `QWidget#wtmhDashboard QLabel` wins): one selector change in `wtmh_theme.py` so `QLabel#wtmhMuted` (and any other
  muted/secondary label rule with the same problem) renders TEXT_SECONDARY on the dashboard; a test that pins the
  winning rule (pixel sample or style-resolved colour on the dashboard). Check no label that should be ink turns grey.

- **2026-10-09, user answers after the unattended run (final look).** (1) The configuration page's column A
  (Test, Input, Target) must **fit a maximized 1920x1080 window without scrolling** (today it scrolls). No setting is
  removed or hidden behind a new control; tighten vertical spacing, margins and group padding (design tokens) until
  it fits, keeping the 8 px grid where possible. (2) A **disabled Start** (the primary button) shows a **pale WTMH
  blue** (ACCENT at reduced strength, text still readable), not the flat grey of a disabled Practice; other disabled
  buttons keep the phase-1 grey. Both are fix-round changes on branch design-phase2.

- **2026-10-09, user decisions after testing the try-all build (empty space).** The user prefers the full-width feel
  of `feature/compass-task-flow`; the phase-2 look itself is fine. Decided from live screenshots (hub scratchpad
  `layout_compare/`: A = feature branch, B = try-all, C = full-width prototype):
  (1) **Full width.** Setup, Start and Test List fill the window as in the feature branch, keeping the phase-2 look;
  this replaces the 1200 px left-aligned column of H4 / H5 / H8 (CONTENT_MAX_WIDTH, the fixed-width test table and
  TABLE_MAX_WIDTH). Test List: the Test Name column stretches, the button column sits at the right of the table.
  Continue to Tests sits at the right edge of the full-width footer.
  (2) **Setup: two cards per row.** Subject & Session Info beside Tracker Connection, Display beside Calibration;
  fields keep their H4 widths; the cards share the row equally. The page gets shorter.
  (3) **Rename the "Advanced" column title to "Gaze Pointer Settings"** (V4 / H6 title only; the cards inside and
  their greying rules are unchanged; note Dwell also applies to a Mouse run, only the smoothing keys grey on Mouse).
  To implement as a fix round on branch design-phase2; the wireframes setup / test-list / start-test / task-config
  need the same changes.

- **2026-10-09, user decision relayed by the hub (configuration page full width).** The configuration page also fills the
  window: drop the 1500 px `CONTENT_MAX_WIDTH` cap of `task_config_page` / `config_form`, so the three columns share the
  window width equally inside the page gutters; the footer row (Preview Test, Save & Continue, Cancel) follows the grid as
  before; slider rows may grow wider; no setting is moved or hidden; the round-4 rule (column A fits a maximized 1920x1080
  window without a vertical scroll, all four tasks) must still hold. This overrides "the 1500 px grid stays" (H6) and "the
  config page is NOT in scope" of the 2026-10-09 "empty space" entry above.

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §2.3, §2.5, §3.1-§3.6 and §5.2 phase 2,
  while phase 1 is being implemented. User decisions V1-V4 (glyphs as the design page shows; Run
  Test the only primary; build the Setup badges and the Continue caption; reorder the configuration
  columns). Hub decisions H1-H12 proposed, awaiting approval. Note found while drafting: the
  proposal's Setup caption example lists tracker and calibration, which no longer block Continue
  (2026-10-07); H4 lists only `continue_blockers()`.
- **2026-10-08** — The user approved H1-H12 as written. SPEC committed on `feature/compass-task-flow`. Next: after the phase-1 review, /spec-run this SPEC from step 1 (wireframes).
- **2026-10-08** — Step 1: wireframes setup, test-list, task-config, start-test, run, run-end updated to V1-V4 and H1-H12 and rendered; the user approved them as drawn. Wireframe tool limits noted: alert kinds render as a teal label (no glyph tile), and the wireframe palette is the old one; the app colours come from phase 1. Next: step 2 after the phase-1 review.
- **2026-10-08** - H13 added (user decision after the phase-1 live check: commit phase 1 as is, fix its three live-check bugs here): white-fill button focus shows the native focus rectangle, Tab trapped in Setup Notes, PRACTICE chip stretched to the bar height. Scope, Q9 and step 2 updated. Phase 1 is committed on branch design-phase1; step 2 starts from the merged result.
- **2026-10-09** — Steps 2-4 done. Implementer rounds: 1 (H1-H10, H12, H13), 2 (user §9 answers: Mouse note split with
  "No eye data will be recorded." at 600; blocker "(Setup page)." endings approved; phase-1 `wtmhMuted` specificity bug
  fixed), 3 (live-check defect: Continue to Tests was 157 px because the tier QSS `min-width` overrode `setFixedWidth`;
  now a 240 px slot). Hub pytest in the worktree: **3018 passed, 2 skipped, 5 failed** (the known skip-worktree alpha
  0.22-vs-0.35 checks, which fail in any fresh worktree and failed before this phase). Live check (fake tracker on
  4343 because Gazepoint Control held 4242; maximized 1920x1009 window captures): Setup widths, Disconnected/Connected and
  Not calibrated/"Calibrated, 5 points, 0.2°" badges, "Needs:" caption, Continue 240 px (after round 3), Q9 focus border
  without native rectangle, Tab out of Notes, Test List widths/badge/tiers/red Delete glyph, config column order +
  Advanced + slider caps + centred footer, Q5 no move on "Changed from Standard", Start Blocked alert with Go to Setup
  inside, run bar PRACTICE chip 24 px + Tracking OK badge: all pass. For the user's look (not defects): the config
  page's column A (Test, Input, Target) scrolls at 1080 px; a disabled Start looks the same grey as a disabled Practice
  (phase-1 disabled style). Not live-checked: the Mouse note (unit tests only). Hub re-rendered
  `docs/wireframes/start-test.{md,html}` for the split Mouse note. Committed on branch design-phase2 only (user's
  unattended-run authorization); merge and push await the user.
- **2026-10-09** — Round 4 for the user's final-look answers. (1) Column A of the configuration page fits a
  maximized 1920x1080 window: Reset to defaults beside the Configuration Name combo, the "Changed from" caption on the
  label's row (fixed 20 px, elided, Q5 holds), Notes 56 px, card spacing on the 4 px scale; nothing removed. (2) A
  disabled primary (`wtmhPrimary`, `cfgSave`) is pale WTMH blue (`ACCENT_DISABLED_FILL` #BCD1E2, text #385A76,
  4.62:1); other disabled tiers keep the grey. This supersedes the "every disabled tier grey" line of phase-1 H5 /
  fable-proposal §2.5 by the user's 2026-10-09 decision (those design docs are not edited). Hub pytest:
  **5 failed, 3033 passed, 2 skipped** (the known alpha checks). Live check (worktree code, maximized 1920x1009):
  the Scanning config page (tallest, column A 786 px) shows no scrollbar (viewport 800 px, content 800 px); a
  disabled Continue to Tests is pale blue. Not updated: `docs/wireframes/task-config.md` still draws Reset on its own
  row. Committed on branch design-phase2.
- **2026-10-09** — Round 5 (user feedback after testing the try-all build: empty space). Setup, Start, Test List
  and the configuration page fill the window (the 1200 px column, the fixed test table and the 1500 px config grid
  are gone); Setup stacks two independent columns (Subject over Display, Tracker over Calibration; Tab order
  Subject, Tracker, Display, Calibration); the config column title "Advanced" is now "Gaze Pointer Settings". Hub
  live check (maximized 1920x1009; screenshots in the hub scratchpad `layout_compare/E_final_*`): Setup has no
  gap under Tracker and Continue sits at the right edge; Test List stretches Test Name with the buttons at the right;
  the config page's three columns share the width with no vertical scroll (Grid Click). Hub pytest:
  **5 failed, 3077 passed, 2 skipped** (the known alpha checks). Wireframe .md text updated; the .html renders are
  not. Committed on branch design-phase2.
- **2026-10-09** — Test-suite hardening (user OK). The full suite segfaulted once at `tests/test_muted_labels.py:77`
  (`root.show(); QApplication.processEvents()`): a widget left alive by an earlier test was garbage-collected in
  the middle of a later test's event processing. New `tests/conftest.py`: an autouse teardown closes and
  `deleteLater()`s every top-level widget, flushes `DeferredDelete`, processes events and runs `gc.collect()`
  after each test (only `qapp` fixtures outlive a test, and they hold no widgets). No app code changed. Hub pytest:
  the muted-label, full-width and dashboard-flow files 3x clean (102 passed each); full suite **5 failed, 3077
  passed, 2 skipped** (the known alpha checks), no crash. Committed on branch design-phase2.
