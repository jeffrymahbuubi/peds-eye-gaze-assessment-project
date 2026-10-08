---
name: SPEC-design-system-phase2
title: Design system v1, phase 2: status badges, alerts with glyphs, and page layout (operator UI)
status: approved 2026-10-08 (V1-V4 user decisions, H1-H12 hub decisions approved by the user)
created: 2026-10-08
last_updated: 2026-10-08
next_step: /spec-run step 2 (spec-implementer) once phase 1 is reviewed; wireframes approved 2026-10-08
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

## 2. Current code (commit `1d38819`; line numbers shift once phase 1 lands)

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

## 4. Design

The wireframes of step 1 (H11) are the design; they are drawn from proposal §3.1-§3.6 with the
changes of §3.1 and §3.2 above, and from the design page's component samples (badges, alerts, Test
List, Setup cards, run bar).

## 5. Scope

**In:** H1-H12; proposal §2.3 widths and spacing for the operator pages, §2.5 badges, alerts,
SliderSpinRow length, §3.1 S2-S6, §3.2 T1, T2, T4-T6, §3.3 A2 (focus already phase 1), §3.4 C1, C3-C5,
C7, §3.5 P1-P5, §3.6 R2.
**Out:** tokens, type, focus, disabled styling, copy strings (phase 1); canvas, themes, full screen
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

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Phase 1 implemented and reviewed (live check may be shared with this one) | — |
| 1 | Wireframes: setup, test-list, task-config, start-test, run, run-end (H11) — **DONE 2026-10-08, user-approved** | **WF gate** |
| 2 | spec-implementer in a worktree based on the phase-1 result: H1-H10, H12 | — |
| 3 | Hub review + full pytest; §9 questions | — |
| 4 | Live check, maximized 1920x1080: every page captured; Setup badges with `tools/fake_gazepoint_server.py` (connected, calibrated) and with no tracker; one Practice run for the run bar badge. Needs the user only for the final look, not as a gaze subject | user |
| 5 | Commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §2.3, §2.5, §3.1-§3.6 and §5.2 phase 2,
  while phase 1 is being implemented. User decisions V1-V4 (glyphs as the design page shows; Run
  Test the only primary; build the Setup badges and the Continue caption; reorder the configuration
  columns). Hub decisions H1-H12 proposed, awaiting approval. Note found while drafting: the
  proposal's Setup caption example lists tracker and calibration, which no longer block Continue
  (2026-10-07); H4 lists only `continue_blockers()`.
- **2026-10-08** — The user approved H1-H12 as written. SPEC committed on `feature/compass-task-flow`. Next: after the phase-1 review, /spec-run this SPEC from step 1 (wireframes).
- **2026-10-08** — Step 1: wireframes setup, test-list, task-config, start-test, run, run-end updated to V1-V4 and H1-H12 and rendered; the user approved them as drawn. Wireframe tool limits noted: alert kinds render as a teal label (no glyph tile), and the wireframe palette is the old one; the app colours come from phase 1. Next: step 2 after the phase-1 review.
