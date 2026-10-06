---
name: SPEC-target-visual-fixes
title: Follow-ups from target-size Phase B — dialog label visibility, scanning rings, target colour
status: approved — F1 a, F2 a, F3 a (user, 2026-10-06); not implemented
created: 2026-10-06
last_updated: 2026-10-06
next_step: /spec-run this SPEC (F2 a + F3 a; F1 closed, no code)
related:
  - SPEC-target-size-and-motion-paths.md (§8 Phase B impl log, "Findings, not fixed" 1-3 — the origin of this SPEC)
  - SPEC-ui-setup-task-selection.md (§12-§13: Fusion style + light standardPalette for Windows dark mode)
  - SPEC-scanning-task-design-port.md (icon scene, ICON_DRAW_FRAC)
---

# SPEC-target-visual-fixes — three Phase B follow-ups

**Status: approved 2026-10-06 (written at `d7af777`): F1 a (close, no code), F2 a (rings around the drawn icon), F3 a (remove the dead colour keys). Nothing implemented yet.**

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
2. `/spec-run` this SPEC: spec-implementer implements the chosen items, the hub
   reviews and runs pytest. Live check against the fake server on port 4250
   (not 4242/4243, which Gazepoint Control holds). Commit and push on the
   user's OK.

No wireframe gate: F2 a only moves existing rings, F3 a has no visible effect,
and F1 has at most a palette call.

## 6. Impl log

(empty)

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
