---
name: SPEC-design-system-phase2
title: Design system v1, phase 2: status badges, alerts with glyphs, and page layout (operator UI)
status: implemented + live-checked 2026-10-09 on branch design-phase2 (NOT merged); approved 2026-10-08 (V1-V4 user decisions, H1-H12 hub decisions approved by the user; H13 phase-1 carry-overs added by the user 2026-10-08)
created: 2026-10-08
last_updated: 2026-10-08
next_step: user's final look at the live-check captures, then merge branch design-phase2 into feature/compass-task-flow and push (user); committed on design-phase2 under the user's unattended-run authorization 2026-10-09
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
