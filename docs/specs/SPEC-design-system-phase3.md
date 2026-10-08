---
name: SPEC-design-system-phase3
title: Design system v1, phase 3: canvas feedback ladder, theme colour keys and full screen during a run
status: approved 2026-10-08 (W1-W2 user decisions, H1-H10 hub decisions approved by the user)
created: 2026-10-08
last_updated: 2026-10-08
next_step: /spec-run after phase 2 (no wireframe gate: the canvas is not wireframed; live check with the user as subject)
related:
  - docs/design/fable-proposal.md (source: §2.6 canvas rules, §3.6 R1 and R4, §5.2 phase 3, §6.1 and §6.3)
  - docs/design/fable-evaluation.md §5 (canvas findings)
  - SPEC-design-system-phase1.md, SPEC-design-system-phase2.md (operator UI; this phase touches only the canvas and the window state)
  - SPEC-input-selection-and-follow.md (glow H3, Follow the Target selectable window, switch)
  - SPEC-target-size-and-motion-paths.md (S/M/L = 3/5/8 degrees, no px radius stored anywhere)
---

# SPEC-design-system-phase3: canvas and run

**Status: approved 2026-10-08. Built after phase 2 on the same branch line. Phase 3 of the five in
fable-proposal §5.2. This is the child-facing phase: its live check needs the user as subject on the
real GP3 HD.**

## 1. Origin

Task A (`fable-evaluation.md` §5) found the canvas feedback muddled: a radial-gradient target, a
white outline that is always a circle even round a square, up to three stacked rings in two colours,
a glow that reaches into the neighbouring icon, and a hit burst whose length depends on the frame
rate. The proposal (§2.6) replaces it with one ladder, **cue < on-target < success**, measured
against each theme's field, and (§3.6 R1) shows the run full screen so no OS chrome sits at the edge
of the child's view. The user asked for this SPEC on 2026-10-08 and settled its two open points (§3.1).

## 2. Current code (commit `1d38819`)

- `src/ui/canvas.py` (483 lines): `_draw_target` fills a `QRadialGradient` (lighter(130) centre) and,
  while selectable, draws a 4 px white **circle** at `_ring_base_radius() + 4` for every shape;
  unselectable = `target_color.darker(180)`. `_draw_instant_feedback`: a 5 px ring at r + 10 in
  `cursor_color`. `_draw_progress_ring` at r + 16. `_draw_glow`: radial halo from r to
  `r + max(28, 0.6 r)`, alpha 200, in `particle_color`. `_draw_particles`: 8 dots of 6 px that age
  **one step per paint** for 20 paints (frame-rate dependent). Layout slots and grid cells: outline in
  `cursor_color` at alpha 38, cell fill white alpha 16. Trail in the target colour, alpha up to 120.
- `src/ui/canvas_shapes.py`: `shape_path(cx, cy, r, shape)` for circle, square (rounded), triangle,
  diamond, hex, star.
- `configs/themes/forest.yaml` / `space.yaml` (9 lines each): `background`, `target_default`,
  `cursor_color`, `particle_color`, `character` (read nowhere in `src/`, proposal §6.1), `sounds`.
- `src/ui/dashboard_window.py:109` `set_flow`: hides the in-app title bar while
  `Flow.hides_title_bar` (PREVIEW, PRACTICE, RUN, FINISHING); the window itself stays maximized
  (`showMaximized()`, line 192), so the OS title bar and the taskbar stay visible during a run.
- `feedback.particles` is a recorded, unexposed setting (`settings_snapshot.py:92-101`).

## 3. Decisions

### 3.1 User decisions (2026-10-08)

| # | Decision |
|---|---|
| W1 | Unselectable target (Follow the Target outside its window): keep the code's rule, **`target_fill.darker(180)`, no outline, no glow** (9.73:1 on the forest field from #D32F2F; the proposal's 7.28 was measured from the old #ff5252). |
| W2 | **Full screen during a run** (Practice, Preview, recorded, and the run-end dialogs over the frozen canvas); back to maximized when the run view is left. |

Target size in px is not a decision here: sizes stay in degrees (3/5/8°) and px follow the measured
display (SPEC-target-size-and-motion-paths). The proposal's "Large about 331 px" is a derived label,
not a constant.

### 3.2 Hub decisions (approved by the user 2026-10-08)

- **H1 Theme keys.** Both YAML files gain explicit keys, with the values of proposal §2.6:

  | Key | forest | space |
  |---|---|---|
  | `target_default` | #D32F2F | #03a9f4 |
  | `target_outline` (outer / inner) | #102010 / #FFFFFF | #FFFFFF / (none) |
  | `distractor` | #5F8F66 | #4F6B85 |
  | `cell_outline` | #5F8F66 | #4F6B85 |
  | `on_target` | #1b5e20 | #ffeb3b |
  | `glow` | #2E7D32 | #ffd54f |
  | `success` | #2E7D32 | #ffd54f |

  `cursor_color` and `particle_color` stay for the gaze cursor and old readers; no canvas element
  derives its colour from them with an alpha any more. `character` is removed (dead key). A theme
  missing a new key falls back to today's derived colour, so an old custom theme still loads.
- **H2 Target.** Flat fill (no gradient). Two-tone outline that follows the shape: 3 px outer
  (#102010 forest / white space) and 2 px inner white (forest only), both stroked along
  `shape_path` of the target's drawn shape, offset outward. Drawn only while selectable (as today's
  outline). Unselectable per W1.
- **H3 Offset path helper.** `canvas_shapes.py` gains `offset_path(cx, cy, r, shape, d)` = the
  same shape at radius r + d (the shapes are radial, so scaling the radius is the offset). The
  outline, the on-target ring and the glow use it, so a square target gets a square ring.
- **H4 On-target ring.** One ring at r + 10, 6 px, `on_target` colour, following the shape; it
  appears on the first on-target frame and goes on the first off-target frame. It replaces
  `_draw_instant_feedback`'s ring; no second ring in another colour.
- **H5 Dwell arc.** At r + 16, 8 px: white core on a #102010 halo (like the cursor); fills over
  `threshold_ms` as today. Space: white, no halo.
- **H6 Glow.** Switch and Follow only (as today): from the outline to r + 0.3 r, alpha 160 to 0, in
  `glow`; outer radius capped at half the centre distance to the nearest slot (grid and icons
  scenes). The 28 px floor goes.
- **H7 Success.** On a hit the target fill turns `success` for **500 ms** (outline stays), measured
  with a monotonic clock, not paint counts; 12 particles of 8 px over the same 500 ms in `success`,
  drawn only when `feedback.particles` is true (today's rule). The flash itself always shows: it is
  the top of the ladder. 500 ms sits inside the 800 ms default inter-trial interval, so no trial
  starts later.
- **H8 Distractors, cells, trail.** Distractor fill `distractor`, no outline. Grid cell outline 2 px
  `cell_outline`, fill white alpha 16. Layout slots likewise. Follow trail in the target colour at
  alpha 40 max, width 0.2 r, 60 samples.
- **H9 Full screen (W2).** `DashboardWindow.set_flow` calls `showFullScreen()` when the new flow
  `hides_title_bar` and `showMaximized()` when it no longer does; modal run-end dialogs open over the
  full-screen window as today. Canvas geometry follows the widget size (hit-testing already does),
  and the display-scaling metadata stays in physical px. Alt-P, Alt-Q, Esc, H unchanged.
- **H10 Tests.** Ratios of §2.6 recomputed from the YAML values (new `tests/test_canvas_theme.py`);
  `offset_path` for every shape (bounding box grows by d); the outline / ring / glow paths are the
  target's shape (pixel samples on an offscreen render of each scene: single, grid, icons with
  square and triangle cued, moving; colour checks only, never sizes); success lasts 500 ms by a
  fake clock; glow outer radius never passes half the nearest-slot distance; `set_flow` toggles full
  screen; a theme without the new keys still renders.

## 4. Design

Proposal §2.6 table and the design page's canvas section are the design. No wireframe: the canvas
is not wireframed (proposal §3.6 R4).

## 5. Scope

**In:** H1-H10; `canvas.py`, `canvas_shapes.py`, both theme YAMLs, `dashboard_window.py` (window
state only).
**Out:** operator pages (phases 1-2); report map and PDF (phase 4); gaze cursor (unchanged);
sounds; task logic, timing, dwell and switch rules; the hit "character" feature (dropped dead key,
not built); any new setting on the configuration page.

## 6. Acceptance criteria

- **K1** Every ratio of proposal §2.6 recomputed from the YAML passes (±0.02); W1 = 9.73.
- **K2** A capture of each scene (single, grid, icons with a square and a triangle cued, moving)
  shows the outline and the on-target ring following the target's shape.
- **K3** On an 8-icon field the glow stays clear of the neighbours' drawn edges.
- **K4** Success is visible for 500 ms (±1 frame) in a frame capture and never delays the next trial.
- **K5** No OS title bar or taskbar in a run capture; the window is maximized again on the report
  and the Test List.
- **K6** Alt-P, Alt-Q, Esc, H unchanged; Practice and Preview still record nothing.
- **K7** The user, as subject on the real GP3 HD, confirms the ladder reads (cue, on-target,
  success) in Static Click, Grid Click, Follow the Target and Scanning Search.
- **K8** Full pytest green (except the known skip-worktree alpha checks).

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Phase 2 done | — |
| 1 | spec-implementer: H1-H10 | — |
| 2 | Hub review + full pytest; §9 questions | — |
| 3 | Live check with the user as subject on the real GP3 HD (K2-K7) | user |
| 4 | Commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-08** — Drafted by the hub from fable-proposal §2.6, §3.6 and §5.2 phase 3. User decisions
  W1 (unselectable stays darker(180), 9.73:1) and W2 (full screen during a run). Hub decisions H1-H10
  proposed, awaiting approval. Found while drafting: today's hit particles age per paint (frame-rate
  dependent), so H7 moves the burst and the flash to a clock.
- **2026-10-08** — The user approved H1-H10 as written. SPEC committed on `feature/compass-task-flow`.
