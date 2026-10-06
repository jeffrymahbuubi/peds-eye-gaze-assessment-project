---
name: SPEC-target-visual-fixes
title: Follow-ups from target-size Phase B — dialog label visibility, scanning rings, target colour
status: complete — F2 a + F3 a implemented, reviewed, live-checked (fake server), committed `d1ff0ea`; F1 closed (not reproduced)
created: 2026-10-06
last_updated: 2026-10-06
next_step: none
related:
  - SPEC-target-size-and-motion-paths.md (§8 Phase B impl log, "Findings, not fixed" 1-3 — the origin of this SPEC)
  - SPEC-ui-setup-task-selection.md (§12-§13: Fusion style + light standardPalette for Windows dark mode)
  - SPEC-scanning-task-design-port.md (icon scene, ICON_DRAW_FRAC)
---

# SPEC-target-visual-fixes — three Phase B follow-ups

**Status: approved 2026-10-06 (written at `d7af777`): F1 a (close, no code), F2 a (rings around the drawn icon), F3 a (remove the dead colour keys). Implemented, reviewed (664 passed) and live-checked against the fake server 2026-10-06.**

## 1. Origin

The Phase B live check of SPEC-target-size-and-motion-paths.md (§8, Phase B
impl log) found three things it did not fix:

1. In the real Task settings dialog, the form labels and the shrink hint were
   almost invisible (light text on the white card), seen in an OS screen
   capture with Windows in dark mode.
2. Scanning draws its "selectable" outline and the instant and dwell rings at
   the *hit* radius (drawn icon / 0.78), so on a dense Large layout they touch
   the neighbouring icon.
3. Every task's target is drawn in the theme's `target_default` colour; the
   task YAML `target.color` is ignored.

The user asked for one small fix SPEC for all three, with finding 1 first,
because the operator sees it.

## 2. Findings, re-checked against the code at `d7af777`, and decisions

### F1 — dialog labels: NOT reproduced

Checked on this machine, which is in Windows dark mode: Qt's default palette
here is Window `#1e1e1e` / WindowText `#ffffff`.

- `src/ui/task_settings_dialog.py` gives the dialog the object name
  `wtmhDashboard` and `wtmh_theme.STYLESHEET`, whose rule
  `QWidget#wtmhDashboard QLabel { color: #122B3A }` covers every form label and
  the hint label. A probe that polishes each QLabel reports `#122b3a` (dark ink)
  in both the native `windows11` style and Fusion with the light palette.
- Real-screen captures (`QScreen.grabWindow` of the shown dialog, not
  `widget.grab()`) at Medium; from the dashboard (`DashboardWindow` parent,
  Fusion + light palette, same as `dashboard_window.main`) with click_grid
  6x6 Large; and scanning 8 icons Large (shrink hint visible): every
  label and the hint text are dark and fully readable.

So the dialog's styling is correct in both launch paths
(`DashboardWindow._on_settings_requested` and `app.run_gui`). The most likely
explanation for the Phase B capture is that it was taken while Windows was
still fading the new dialog window in. During that fade the whole window,
text included, is partly transparent. That is not certain.

**Decision F1 (user):**
- **a (recommended):** no code change. Close finding 1 as "not reproduced".
  If the user ever sees it themselves on screen (not in a capture), reopen it
  with a photo.
- **b:** defensive hardening anyway: give `TaskSettingsDialog` the light
  `QStyle.standardPalette()` explicitly, so it never depends on the caller
  having set the app palette. About 3 lines, plus a test that the labels'
  WindowText is dark under a dark app palette.

### F2 — scanning rings drawn at the hit radius

`src/ui/canvas.py`: `_draw_target` draws the selectable outline at `r + 4`,
`_draw_instant_feedback` at `r + 10` (pen 5), and `_draw_progress_ring` at
`r + 16` (pen 8), all with `r = target_radius_px`. In the `icons` scene that
is the hit radius; the icon itself is drawn at `r * ICON_DRAW_FRAC` (0.78).

`fit_icon_radius_px` (`src/engine/target_size.py`) caps the *drawn* icon at
0.44 x the smallest slot distance `d` (half of `d`, less 2 x `CELL_PAD_FRAC`).
That leaves a gap of 0.12 `d` between neighbouring icons. The hit radius is
0.44 `d` / 0.78 = 0.564 `d`, so even the selectable outline already reaches
past the neighbour's edge, which is at 0.56 `d`.

The hit test is the nearest slot (Phase B, §11.3), not a circle, so the
hit-radius circle the rings follow does not show the real hitbox either.

**Decision F2 (user):**
- **a (recommended):** in the `icons` scene only, the three rings are drawn
  around the *drawn* icon: base radius `r * ICON_DRAW_FRAC`, same +4 / +10 / +16
  offsets and pens. The furthest ring edge is then icon + 20 px, which is clear
  of the neighbour whenever 0.12 `d` > 20 px (`d` > 167 px). Measured in Phase B:
  8 icons Large has `d` ≈ 230 px (gap ≈ 27 px), 6 icons Large more. Other scenes
  (`single`, `grid`, `moving`) draw the target at the hit radius, so they are
  unchanged. Hit-testing and `TARGET_SHRUNK` / metadata are unchanged.
- **b:** leave it (cosmetic only).

### F3 — task YAML `target.color` is never read

`TaskCanvas.target_color` comes only from the theme's `target_default`
(`canvas.py:96`). Nothing in `src/` reads `target.color` or
`target.highlight_color`. Those keys have been in the four task YAMLs since
the initial commit (`4ced4d9`): click_grid `#4caf50` (green), click_static
`#ff5252`, follow_moving `#03a9f4` (blue), scanning `#9c27b0` (purple), and
`highlight_color` `#ffeb3b`. Every session recorded so far, and the
forest-theme unification, used the theme red `#ff5252` for every task.

**Decision F3 (user):**
- **a (recommended): remove the dead keys.** Delete `target.color` /
  `target.highlight_color` from the four task YAMLs. The theme stays the one
  source of the target colour. Nothing changes on screen, so stimuli stay
  identical to every session collected so far, and the config stops promising
  something it doesn't do. One more reason: on the forest background
  (`#e8f5e9`, light green), click_grid's green `#4caf50` would have much
  less contrast than the red.
- **b: honour the YAML colour.** `AssessmentApp` sets `canvas.target_color`
  from `task.target.color` when present, else the theme. Each task gets its
  own colour. This changes the stimulus against all earlier sessions, so the
  colour used would then be recorded in `metadata.json`. `highlight_color`
  stays unused (removed).

## 3. Scope

Only what F1-F3 choose. No other change to the dialog, the canvas, the hit
test or the recorded data (except the metadata field under F3 b).

## 4. Acceptance criteria (chosen: F1 a, F2 a, F3 a; the b lines are kept for the record only)

- **F1 a:** SPEC log records "not reproduced", with the evidence in §2. No code.
- **F1 b:** test: under a dark app palette, every QLabel in
  `TaskSettingsDialog` has a dark WindowText. Plus a live real-screen capture
  from the dashboard.
- **F2 a:** unit test on `TaskCanvas`: in the `icons` scene the three rings'
  radii are based on `target_radius_px * ICON_DRAW_FRAC`; in `single` / `grid`
  / `moving` they are unchanged. Live: scanning, 8 icons Large, a real-screen
  capture shows the selectable outline and dwell ring clear of the
  neighbouring icons.
- **F3 a:** the four YAMLs have no `target.color` / `highlight_color`. A grep of
  `configs/` and `src/` finds neither. The full pytest suite passes.
  Saved settings profiles that still contain these keys load without error.
- **F3 b:** test: the canvas colour follows `task.target.color`, with the theme
  as fallback; metadata records it. Live: each task shows its own colour.

## 5. Plan

1. ~~User picks F1 / F2 / F3.~~ Done 2026-10-06: F1 a, F2 a, F3 a.
2. DONE 2026-10-06. `/spec-run` this SPEC: spec-implementer implements the chosen items, the hub
   reviews and runs pytest. Live check against the fake server on port 4250
   (not 4242/4243, which Gazepoint Control holds). Commit and push on the
   user's OK.

No wireframe gate: F2 a only moves existing rings, F3 a has no visible effect,
and F1 has at most a palette call.

## 6. Impl log

- **2026-10-06** — Implemented F2 a and F3 a; F1 a is closed with no code
  (`task_settings_dialog.py` untouched). Model: `claude-sonnet-5-5` (spec-implementer).
  Not committed, not staged.
  - **Files changed:**
    - `src/ui/canvas.py`: new `TaskCanvas._ring_base_radius()`; the selectable
      outline (+4), `_draw_instant_feedback` (+10) and `_draw_progress_ring`
      (+16) now add their offset to it instead of to `target_radius_px`. Same
      offsets, same pens. It returns `target_radius_px * ICON_DRAW_FRAC` in the
      `icons` scene and `target_radius_px` in every other scene (`single`,
      `grid`, `moving`). Hit-testing, `TARGET_SHRUNK`, metadata and every other
      draw call are unchanged.
    - `configs/tasks/click_grid.yaml`: removed `target.color` and
      `target.highlight_color`.
    - `configs/tasks/click_static.yaml`: removed `target.color`.
    - `configs/tasks/follow_moving.yaml`: removed `target.color`.
    - `configs/tasks/scanning.yaml`: removed `target.color` and
      `target.highlight_color`; that left an empty `target:` section, deleted too
      (checked first: scanning reads its size and radius from `layout`, via
      `size_block`; `src/tasks/click_static.py`, `click_grid.py` and
      `follow_moving.py` read `target`, `scanning.py` does not).
    - `docs/specs/SPEC-target-visual-fixes.md`: this log only.
  - **Tests added:** new `tests/test_target_visual_fixes.py` (16 tests):
    ring base radius is the drawn icon in `icons` and the hit radius in
    `single` / `grid` / `moving`; a render test on the 800x600 canvas with the
    outline, instant ring and dwell ring all on, measuring the outermost lit
    pixel (97 px in `icons` vs 119 px with the old behaviour, hit radius 100,
    expected `base + 20`); the four task YAMLs (raw and through
    `load_task_config`) carry no `color` / `highlight_color` under `target`; a
    saved profile whose `live` and `structural` blocks still hold the two keys
    loads, resolves, deep-merges and builds all four tasks without error (the
    existing `test_unknown_keys_are_ignored` only covered live keys); and a scan
    that `configs/` and `src/` contain no `highlight_color`.
  - **Grep (F3 a):** `highlight_color` appears nowhere under `configs/`, `src/`,
    `tools/` or `tests/` except as a test literal in the new file. `target.color`
    / `["color"]` is not read anywhere in `src/`; `TaskCanvas.target_color` still
    comes only from the theme's `target_default`. `configs/default.yaml` (skip-
    worktree, not touched) has no colour keys under `target`.
  - **pytest** (`..\.venv\Scripts\python.exe -m pytest`, repo root):
    `664 passed in 116.09s`. The known `test_config_merges_task_over_default`
    failure did not appear on this machine's run.
  - **Deviations from the SPEC:** none. One reading to confirm in review:
    `_ring_base_radius()` uses the drawn icon radius only when the icons scene
    has a cued slot (`active_slot >= 0`), the same condition `_draw_target` uses
    to paint the icon silhouette; with no cued slot it paints a plain circle at
    the hit radius and the rings follow that. Scanning always sets `active_slot`
    whenever a target exists, so for scanning this is identical to "icons scene
    only"; it only matters for a hand-built icons scene with no `active_slot`.
  - **Not done / left for the hub:** the F2 a live real-screen capture (scanning,
    8 icons Large, rings clear of the neighbours) and the commit. No live test,
    no app launch.

## 7. Log

- **2026-10-06** — Drafted from the three Phase B findings. F1 investigated
  live on this machine (dark mode confirmed, labels readable in every
  launch path and with the hint shown): not reproduced. F2 / F3 causes
  confirmed in code. Awaiting user decisions.
- **2026-10-06** — User chose all three recommended options: **F1 a**
  (finding 1 closed as not reproduced, no code; reopen with an on-screen
  photo if seen again), **F2 a** (scanning rings around the drawn icon),
  **F3 a** (remove `target.color` / `target.highlight_color` from the four
  task YAMLs). SPEC approved; ready for /spec-run.
- **2026-10-06** — Implemented by spec-implementer (§6). Hub review: diff in
  scope (canvas.py `_ring_base_radius()`, four task YAMLs, new
  `tests/test_target_visual_fixes.py`); hub pytest **664 passed, 0 failed**
  (648 + 16). Accepted the disclosed reading: the drawn-icon base applies when
  the icons scene has a cued slot (`active_slot >= 0`), the same condition
  `_draw_target` uses for the silhouette; scanning always sets it.
  Live check vs the fake server on port 4250, session
  `2026-10-06_LIVECHK03_scanning_run1` (scanning, 8 icons, Large):
  `TARGET_SHRUNK` 212.3 to 129.6 hit px (unchanged from Phase B), metadata
  `preset: large`, `radius_of: icon`. On a real-screen capture, measured from
  the cued icon's centre: icon edge 102 px, selectable outline outer 107 px,
  neighbouring diamond tip 130 px (the old code put the outline at about 136
  px, over the diamond). The instant / dwell rings were not seen live (the fake
  gaze never landed on the cued icon); by calculation the dwell ring's outer
  edge is about 122 px, 8 px clear; covered by the render test. Target colour
  is still the theme red. F1 re-confirmed on the real screen: the dialog labels
  and the shrink hint are readable with Windows in dark mode. Not tested: real
  gaze. `local_state.json` restored to 127.0.0.1:4242. User approved commit + push.
