---
name: SPEC-grid-cell-gap
title: Grid Click — operator-set gap between cells (dead zone)
status: approved — G1-G3 + H1-H4 (user, 2026-10-06); wireframe next
created: 2026-10-06
last_updated: 2026-10-06
next_step: /spec-run (implementation); wireframe approved
related:
  - SPEC-target-size-and-motion-paths.md (size presets by visual angle, grid fit S4.3, Task settings choice kind S4.5)
  - SPEC-target-visual-fixes.md (running at the same time; touches canvas.py rings and the task YAML colours only)
---

# SPEC-grid-cell-gap — wider, operator-set gap between grid cells

**Status: approved 2026-10-06 (written at `b6803a6`): G1-G3 and hub decisions H1-H4. Wireframe approved 2026-10-06 (`docs/wireframes/task-settings.md`, sections E/F). Nothing implemented yet.**

## 1. Origin

Feedback the user received on the Grid Click task: the cells are too close
together; please make the gap wider. The user asked how to put this in the
Task settings.

## 2. Current code (as of `b6803a6`)

- `ClickGridTask.build_targets` (`src/tasks/click_grid.py`) tiles the grid
  span (`1 - 2 * grid.margin_frac`) into R x C cells **edge to edge**. Cell pitch
  = span / cols by span / rows.
- The canvas (`TaskCanvas._draw_grid_scene`) draws each cell inset by
  `CELL_PAD_FRAC` (0.06, hard-coded in `src/engine/target_size.py`) of the
  cell's smaller side. The visible gap between two drawn cells is therefore
  12 % of the smaller side. It is not a setting.
- Target fit: `fit_radius_px` caps the circle to the drawn (padded) cell.
- Hit test (`ClickGridTask.hit_test`): circle (effective radius + jitter
  tolerance, 40 px by default) AND inside the target's own **unpadded** cell.
  Once radius + 40 px reaches half the cell (e.g. 3x3 Medium, and every 6x6
  grid), the hit area runs to the cell edge, so two cells' hit areas touch:
  the drawn gap is visual only.

Measured on a 1920 x 957 canvas (HUD hidden), 41.4 px per degree on this
monitor at 650 mm (Medium 5° = 207 px):

| Grid | Cell pitch (px) | Visible gap today | in degrees |
|---|---|---|---|
| 3x3 | 486 x 242 | ≈ 29 px | ≈ 0.7° |
| 6x6 | 243 x 121 | ≈ 15 px | ≈ 0.35° |

The GP3 HD's accuracy is about 0.5-1°, more than the 6x6 gap.

## 3. Decisions

### Chosen by the user (2026-10-06)

- **G1 Dead zone:** gaze in the gap selects nothing; it is not part of any
  cell's hit area.
- **G2 Presets in degrees:** a new "Cell gap" choice in the Task settings
  dialog, like Target size: **Standard** (today's layout) / **Wide — 1°** /
  **Extra wide — 2°**, each item showing the px it comes to on this monitor.
  Same px for every child on a given monitor (monitor size + the fixed 650 mm,
  never the child's measured distance).
- **G3** SPEC drafted now, run after SPEC-target-visual-fixes is committed.

### Hub decisions (approved by the user 2026-10-06)

- **H1 Standard = exactly today.** `standard` keeps the `CELL_PAD_FRAC`
  drawing, fit and hit test unchanged (hit area clipped to the *unpadded*
  cell, as now). Earlier sessions stay comparable, and a config/profile
  without the new key behaves as before. Default = `standard`.
- **H2 What the gap is.** For Wide / Extra wide, the gap G (px) is the space
  between two neighbouring drawn cells. The grid's outer size
  (`margin_frac`) and cell pitch don't change. Each drawn cell is the pitch
  minus G (inset G / 2 on every side). The target circle is capped to the
  drawn cell (radius ≤ half its smaller side). G is never smaller than today's
  Standard gap for that grid, so "Wide" can never look narrower than
  "Standard" on a large 3x3 grid.
- **H3 Hit area = circle ∩ drawn cell.** For Wide / Extra wide the hit test
  clips to the *drawn* cell, not the pitch, so the gap belongs to no cell,
  even inside the jitter tolerance. Gaze entering the gap counts as leaving
  the target (the same dwell behaviour as leaving the target today).
- **H4 Cap on dense grids.** G is capped at 50 % of the pitch's smaller side,
  so a drawn cell never shrinks below half its pitch. Without a cap,
  Extra wide on 6x6 (83 px gap on a 121 px pitch) would leave a 38 px cell
  and a ≈ 19 px radius target. When capped, one `GAP_CAPPED` event and a Log
  line record wanted vs used px, the same pattern as `TARGET_SHRUNK`.

Effect on the 1920 x 957 canvas (target fit radius = half the drawn cell's
smaller side):

| Grid | Gap | G used (px) | Drawn cell (px) | Max target radius (px) |
|---|---|---|---|---|
| 3x3 | Standard | 29 | 457 x 213 | 106 |
| 3x3 | Wide 1° | 41 | 445 x 201 | 100 |
| 3x3 | Extra wide 2° | 83 | 403 x 159 | 79 |
| 6x6 | Standard | 15 | 228 x 106 | 53 |
| 6x6 | Wide 1° | 41 | 202 x 80 | 40 |
| 6x6 | Extra wide 2° | 60 (capped from 83) | 183 x 61 | 30 |

So a wider gap shrinks the targets on dense grids. The dialog's existing shrink
hint shows this before the run.

## 4. Design

### 4.1 `src/engine/target_size.py` (pure, no Qt)

- `GAP_PRESETS_DEG = {"standard": None, "wide": 1.0, "extra_wide": 2.0}`, names
  "Standard" / "Wide" / "Extra wide", `normalize_gap()` (unknown means
  `standard`), `GAP_CHOICES` for the registry.
- `gap_px_for(gap, mm_per_px, distance_mm)`: degrees to px with the same
  visual-angle maths as `radius_px_for` (None for `standard`).
- `grid_cell_geometry(pitch_w_px, pitch_h_px, gap)` returns the drawn cell
  w/h, the inset per side, the gap used and whether it was capped. This is
  the single source for drawing, fit, hit test and the dialog hint (the
  `CELL_PAD_FRAC` sharing pattern), so they cannot drift apart. `standard`
  returns today's numbers.
- `estimate_grid_fit_radius_px` gains a `gap_px` argument (default:
  standard).

### 4.2 Resolving the gap into the run config

`grid.gap` (preset name) in `configs/tasks/click_grid.yaml`, default
`standard`, with a comment. Resolved to `grid.gap_px` alongside the target
size, against the run's screen (same place and same `screen` argument as
`apply_target_size`, SPEC-target-size-and-motion-paths §4.2 / §9). Recorded in
`metadata.json`: `settings.structural` (`grid.gap`), plus `gap_deg`,
`gap_px` and, if capped, `gap_px_used` in the grid / target-size block. Session
Log line: "Cell gap: Wide — 1° (≈41 px)".

### 4.3 `ClickGridTask`

`effective_radius_px` and `hit_test` use `grid_cell_geometry` on the live pitch
(per frame: HUD hide/show resizes the canvas). For non-standard gaps the
`in_cell` test uses the drawn cell (H3). `scene_spec()` adds the per-side
inset in px (or normalized) so the canvas draws the same cell. One
`GAP_CAPPED` event per run when H4 applies.

### 4.4 `TaskCanvas._draw_grid_scene`

Uses the inset from `scene_spec` instead of computing `CELL_PAD_FRAC`
itself (standard gives the same number, so nothing visible changes).

### 4.5 Task settings dialog

`settings_registry.py`: new `StructuralSetting("grid.gap", "Cell gap",
"choice", applies_to=("click_grid",), choices=GAP_CHOICES,
default="standard")`, placed after Grid cols. `task_settings_dialog.py`: items
read "Standard", "Wide — 1° (≈41 px)", "Extra wide — 2° (≈83 px)". The
shrink hint also recalculates when the gap changes, and when H4 caps the gap
it says so, e.g. "Gap limited to ≈ 60 px and targets shrunk to ≈ 61 px to fit
a 6 x 6 grid (approximate)". Settings profiles save and restore the choice
like the other structural settings.

## 5. Scope

In: §4 only, click_grid only. Out: scanning / other tasks, margin_frac as a
setting, a free px slider, any change to the Standard layout or hit test,
jitter tolerance.

## 6. Acceptance criteria

1. `standard` (and a config/profile with no `grid.gap`): drawn cells, target
   fit, hit test and recorded data are identical to `b6803a6` (existing tests
   pass unchanged; a test pins the numbers).
2. `gap_px_for` gives 1° / 2° at 650 mm from the monitor's mm per px; the
   unit test uses known values.
3. `grid_cell_geometry`: G at least Standard, capped at 50 % of the smaller
   pitch, reports the cap; table §3 reproduced in a test (within 1 px).
4. Hit test, Wide: a point in the gap between two cells hits neither, even
   within the jitter tolerance of both targets. A point inside the drawn cell
   and within radius + jitter still hits.
5. Canvas draws the cell from the scene's inset (test on scene_spec, plus a
   live screenshot).
6. Dialog: "Cell gap" row on click_grid only, items with ≈px, hint updates on
   gap / rows / cols / size and mentions a cap. The choice carries over between
   runs and is saved/restored in settings profiles.
7. metadata + Log line + `GAP_CAPPED` as §4.2 / §4.3; HUD hide mid-run keeps
   the gap correct (re-evaluated on resize).
8. Full pytest passes (known `default.yaml`-drift failure excepted).

## 7. Plan

1. ~~User approves H1-H4 (and §4).~~ Done 2026-10-06.
2. DONE 2026-10-06. Wireframe: add the Cell gap row + capped hint to
   `docs/wireframes/task-settings.md`, GATE 1.
3. `/spec-run`: spec-implementer, hub review + pytest, live check against the
   fake server on port 4250 (3x3 and 6x6 at each gap, HUD hide mid-run), then
   real gaze with the user as subject (looking into the gap must not select).
   Commit/push on the user's OK.

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-06** — Feedback "grid cells too close, wider gap please"
  received via the user. Code read at `b6803a6`; visible gap measured
  (3x3 ≈ 29 px ≈ 0.7°, 6x6 ≈ 15 px ≈ 0.35°); found the drawn gap is visual
  only once radius + jitter reaches the cell edge. User chose G1 dead zone,
  G2 presets in degrees (Standard / Wide 1° / Extra wide 2°), G3 draft now.
  Hub decisions H1-H4 written; awaiting approval.
- **2026-10-06** — User approved H1-H4 as written. SPEC approved; wireframe
  (Cell gap row + capped hint) next, after SPEC-target-visual-fixes is committed.
- **2026-10-06** — Wireframe written (`docs/wireframes/task-settings.md`, new
  section E: 3x3 Wide with the shrink hint; F: 6x6 Extra wide with the capped-gap
  hint; dead-zone sketch) and approved by the user as is. Implementation next.
