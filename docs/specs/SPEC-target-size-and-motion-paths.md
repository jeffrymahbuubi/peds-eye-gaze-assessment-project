---
name: SPEC-target-size-and-motion-paths
title: Target size presets (Small/Medium/Large by visual angle), grid fit, and new Follow & Click paths
status: approved by the user 2026-10-06 (incl. hub decisions §4.4 speed, §4.4 corner diagonals, §4.2 size-wins, §5 phasing); wireframe next
created: 2026-10-06
last_updated: 2026-10-06
next_step: /spec-run — user approves wireframe docs/wireframes/task-settings.html, then implement Phase A + C
related:
  - SPEC-live-settings-panel.md (§4/§5.3 structural settings + TaskSettingsDialog; §10 settings profiles store the structural block)
  - SPEC-follow-moving-selection.md (selection window, attempts; unchanged here)
  - SPEC-diki-design-audit.md (§3.3 grid scene, §3.5 moving trail)
  - SPEC-gazepoint-analysis-export-parity.md (§4.2 physical size + viewing distance in metadata)
  - SPEC-display-scaling-cursor-accuracy.md (logical vs physical px)
  - SPEC-hud-hide-toggle.md (canvas resizes mid-run)
---

# SPEC-target-size-and-motion-paths — target size presets, grid fit, Follow & Click paths

**Status: APPROVED by the user 2026-10-06 (whole SPEC, incl. the four hub decisions). Wireframe of the dialog next (§4.5), then implementation of Phase A + C.**

**Created:** 2026-10-06
**Last updated:** 2026-10-06

## 1. Origin / what was asked

User, 2026-10-06, three objectives:

1. **Follow & Click (`follow_moving`)**: add target movements **Vertical**,
   **Horizontal**, **Diagonal** (from the top-left corner and from the
   top-right corner) as selectable options.
2. **Grid Click (`click_grid`)**: with rows = cols = 6 and the default target
   size, the target overflows its grid cell. Keep the target inside the cell.
3. **Target size as Small / Medium / Large** instead of px, because px gives
   no mental model of how big the target is. Start with the grid task, then
   extend to the other tasks. The size should follow the screen and stay
   usable for children's eyes.

Clarification asked by the user: does visual-angle sizing give every subject
a different target size? **No** — see §2 T1. The conversion uses only the
monitor's physical size and the fixed configured viewing distance (650 mm),
never anything measured from the child. Every subject on the same monitor
gets the identical pixel size; across monitors the *apparent* size stays the
same. The real per-sample eye distance is already recorded in
`eye_geometry.csv` for analysis, and the stimulus is deliberately NOT adapted
to it.

## 2. Decisions (chosen by the user 2026-10-06)

- **T1 — Size basis: visual angle.** Each preset is a fixed target
  *diameter* in degrees, converted to px from the monitor's physical width
  and `app.viewing_distance_mm` (default 650). Rejected: fraction of canvas
  height; fixed px per preset.
- **T2 — Presets: Small 3°, Medium 5°, Large 8°** (diameter). On a 24"
  1920x1080 monitor at 650 mm (≈ 40.9 px/°): S ≈ 123 px, M ≈ 205 px
  (≈ today's default radius 100), L ≈ 328 px across.
- **T3 — Grid fit: shrink target AND hitbox.** When the preset does not fit
  the cell, the target is drawn at the largest size that fits inside its
  cell, and the gaze hitbox (radius + jitter tolerance) is limited to the
  cell, so gaze on a neighbour cell never counts. The size actually used is
  saved per trial.
- **T4 — Diagonal as two separate options**: Diagonal ↘ (top-left ↔
  bottom-right) and Diagonal ↙ (top-right ↔ bottom-left).

## 3. Current code (as of `97d03e1`)

- `src/tasks/follow_moving.py:15-64` — `path` read from
  `motion.path` (YAML only, `configs/tasks/follow_moving.yaml` sets
  `circular`); `target_position` supports `circular` and, as the fallback,
  `horizontal` (triangle wave x 0.1↔0.9 at a per-trial random y in
  0.25-0.75). Speed = `speed_frac_per_s`, "fraction of screen width per
  second". No UI exposes `path`.
- `src/tasks/click_grid.py:21-74` — cells on a `margin_frac` 0.12 inset
  grid; `cell_w = cell_h_norm = 0.76 / cols|rows`. Radius is the fixed
  `target.radius_px` (YAML 100). Nothing relates the radius to the cell.
- **Overflow, measured:** cell height = 0.76 x canvas height / rows. At
  6 rows on a ~1000-1080 px tall canvas that is 127-137 px; the target is
  200 px across, and the hitbox (`radius + dwell.jitter_tolerance_px` 40,
  `base_task.py:320`) is 280 px across — it covers neighbouring cells.
- `src/ui/canvas.py` `_draw_grid_scene` — cell rect padded by
  `0.06 * min(cw, ch)`; `_draw_target` draws a circle of
  `target_radius_px`, fed by `app.py:856` from `TargetSpec.radius_px`.
- `src/ui/settings_registry.py:176-204` — `STRUCTURAL_SETTINGS`:
  `target.radius_px` (30-200 px) for click_static / click_grid /
  follow_moving; `layout.radius_px` for scanning. Kinds are `int`/`float`
  only; `TaskSettingsDialog` renders every one as a `SliderSpinRow`.
- Structural overrides are already recorded in
  `metadata.settings.structural` (`app.py:410`) and stored in settings
  profiles (`settings_profile.py`).
- Physical size: `app.py:770-781` reads `app.screen_physical_width_mm` or
  falls back to `QScreen.physicalSize()` (EDID), plus
  `app.viewing_distance_mm`; recorded in metadata, not used for stimuli.
- Hit-testing and drawing are in Qt **logical** px (canvas size), not
  physical px.

## 4. Design

### 4.1 Size presets — new pure module `src/engine/target_size.py` (no Qt)

```python
SIZE_PRESETS_DEG = {"small": 3.0, "medium": 5.0, "large": 8.0}  # diameter
DEFAULT_SIZE = "medium"
REFERENCE_MM_PER_PX = 531.4 / 1920   # 24" 16:9 1080p, the lab standard

def mm_per_logical_px(physical_width_mm, logical_screen_width_px) -> tuple[float, str]
    # returns (value, source); source "config" | "edid" | "fallback"
def radius_px_for(size: str, mm_per_px: float, viewing_distance_mm: float) -> float
    # diameter_mm = 2 * D * tan(deg/2); radius_px = diameter_mm / 2 / mm_per_px
```

- `mm_per_logical_px` = physical width (mm) / the **logical** width of the
  canvas's `QScreen.geometry()`. Logical, because the canvas paints and
  hit-tests in logical px; at 150 % Windows scale a logical px is 1.5
  physical px, and this keeps the apparent size right (§3 last bullet).
- Physical width source, in order: `app.screen_physical_width_mm` (config,
  "config") → `QScreen.physicalSize().width()` ("edid") → the reference
  monitor ("fallback"). A value is rejected as implausible (→ next source)
  when mm per physical px is outside 0.10-0.60 (EDID is sometimes 0 or
  bogus on projectors/TVs). Headless replay has no screen → "fallback".
- Unknown size name → `DEFAULT_SIZE`, logged.

### 4.2 Resolving the size into the run config

`AssessmentApp.__init__`, **before** `build_task` (`app.py:~491`):

1. If the task config has `target.size` (or, Phase B, `layout.size` for
   scanning), compute `radius_px_for(...)` with the canvas's screen and
   write it into `config["task"]["target"]["radius_px"]`. Tasks keep
   reading `radius_px` exactly as today, so `build_targets` code is
   unchanged for the size itself.
2. If no `size` key is present (old YAML, old profile), the explicit
   `radius_px` is used unchanged — backward compatible.
3. `size` wins when both are present (a saved profile can hold an old
   `target.radius_px` next to the new `target.size`).
4. Record in metadata (new additive field, `schema_version` not bumped,
   same convention as the other geometry fields):
   `target_size = {"preset": "medium", "diameter_deg": 5.0,
   "radius_px": 102.4, "mm_per_px": 0.2768, "mm_per_px_source": "edid",
   "viewing_distance_mm": 650}`; and one Session Log line, e.g.
   `Target size: Medium (5.0°) = 102 px radius (EDID 531x299 mm, 650 mm).`

### 4.3 Grid fit (T3) — runtime, because the canvas size changes

The canvas resizes mid-run (HUD hide/show, window resize), so the cap
cannot be baked in at `build_targets` time.

- `BaseTask` gets `effective_radius_px(target) -> float`, default
  `target.radius_px`. `ClickGridTask` overrides it:
  `min(target.radius_px, 0.5 * min(cell_w * screen_w, cell_h * screen_h) * (1 - 2 * 0.06))`
  — the same 0.06 padding the canvas uses for the cell rectangle, so the
  circle sits fully inside the drawn cell.
- `BaseTask` gets `hit_test(target, cx_px, cy_px, px, py) -> bool`,
  default today's `circle_contains(..., effective_radius + jitter, ...)`.
  `ClickGridTask` overrides it: the circle test **AND** the point lies
  inside the cell rectangle (unpadded cell bounds). The hitbox therefore
  never reaches a neighbour cell, but keeps the full jitter tolerance in
  the cell's corners.
- `FrameResult` gets `target_radius_px: float` (the effective radius this
  frame); `app.py:856` passes it to the canvas instead of
  `result.target.radius_px`. Dwell progress ring / instant-feedback ring
  scale from it automatically (they use `canvas.target_radius_px`).
- `TrialRecord.target_radius_px` = the effective radius **at trial start**
  (no new column). A mid-trial HUD toggle is already visible as a
  `CANVAS_RESIZED` event.
- When the cap applies at a trial start, record one `TARGET_SHRUNK` event
  per run (not per trial): `requested_px`, `used_px`, `rows`, `cols`.

### 4.4 Follow & Click paths (objective 1, T4)

`motion.path` values (string, stored as today):

| value | label in the dialog | movement (normalized canvas coords) |
|---|---|---|
| `circular` | Circular | unchanged (today's code) |
| `horizontal` | Horizontal ↔ | unchanged: x 0.1↔0.9, y random 0.25-0.75 per trial |
| `vertical` | Vertical ↕ | y 0.1↔0.9, x random 0.25-0.75 per trial |
| `diagonal_tlbr` | Diagonal ↘ (top-left ↔ bottom-right) | (0.1,0.1)↔(0.9,0.9) |
| `diagonal_trbl` | Diagonal ↙ (top-right ↔ bottom-left) | (0.9,0.1)↔(0.1,0.9) |

- All straight paths are a triangle wave (bounce) along their segment,
  starting at the segment's first end (top for vertical, the named top
  corner for diagonals). `TargetSpec.x_norm/y_norm` = that start point, so
  `trials.csv` `target_x/y` stay meaningful.
- **Same on-screen speed for every straight path (hub decision):**
  `speed_frac_per_s` keeps its meaning "fraction of canvas width per
  second" and is converted to px/s = `speed * screen_w`; each path moves at
  that px/s along its own segment. Without this, the same setting would
  cross the screen faster vertically (canvas is shorter) and on diagonals
  the speed would depend on aspect ratio — not comparable between paths.
  Horizontal is numerically identical to today. Circular is left as is
  (its speed is revolutions/s; out of scope).
- Diagonal endpoints are canvas corners in normalized coordinates, so the
  angle follows the canvas aspect ratio (≈ 29-31° from horizontal on
  a 16:9 screen, depending on whether the HUD is shown). Accepted; the trail already shows the path.
- Default remains the YAML's `circular`. Unknown value → `horizontal`
  (today's fallback), logged.

### 4.5 Task settings dialog — new `choice` kind

- `StructuralSetting` gets `kind = "choice"` and
  `choices: tuple[tuple[str, str], ...]` (value, label). The dialog renders
  a themed `QComboBox` for it; `overrides()` returns the value string.
- New entries:
  - `target.size` — "Target size" — Small / Medium / Large, `applies_to`
    **click_grid** in Phase A (Phase B: all target tasks, §5).
  - `motion.path` — "Movement path" — the five values of §4.4,
    `applies_to=("follow_moving",)`.
- `target.radius_px` is **removed from the dialog for click_grid** in
  Phase A (kept for click_static/follow_moving until Phase B).
- Each size item shows the size on this monitor, e.g. "Medium — 5° (≈205
  px)". For click_grid, a hint line under the combo appears when the
  chosen size is estimated not to fit the chosen rows/cols on this screen
  ("Will be shrunk to ≈ 115 px to fit a 6x6 grid"); the estimate uses the
  screen's available height and is labelled approximate (the real canvas
  size is only known once the run window is up).
- `initial_structural_values` returns the YAML's `target.size` (default
  `medium`) for the combo.
- **Wireframe gate:** this dialog change is UI work → wireframe in
  `docs/wireframes/` approved by the user before implementation.

### 4.6 Config files

- `configs/tasks/click_grid.yaml`: `target.size: medium`; `radius_px`
  removed (comment explains `size` and the legacy `radius_px` fallback).
- `configs/tasks/follow_moving.yaml`: `path:` comment lists the five
  values.
- `configs/default.yaml` is skip-worktree — **not touched**.

## 5. Scope / phases

- **Phase A (this round):** §4.1, §4.2, §4.3, §4.5 for **click_grid**,
  §4.6 click_grid.
- **Phase C (this round, independent of A):** §4.4 + its §4.5 dropdown +
  §4.6 follow_moving.
- **Phase B (later, after A is live-validated and the user says go):**
  `target.size` replaces `target.radius_px` in the dialog for click_static
  and follow_moving, and `layout.size` replaces `layout.radius_px` for
  scanning (scanning's slots also need a fit cap like §4.3 — to be
  designed then). Not part of this round's acceptance.
- Out of scope: circular-path speed semantics; per-subject distance
  adaptation (rejected, §1); changing `dwell.jitter_tolerance_px`.

## 6. Acceptance criteria

1. `radius_px_for` unit tests: 24"/1080p/650 mm → M ≈ 102 px radius
   (±1), S ≈ 61, L ≈ 164; at 150 % scale (logical width 1280) M ≈ 68 logical
   px radius, i.e. the same millimetres on screen; an implausible EDID
   width → the fallback source.
2. click_grid 6x6, Large, canvas 1500x1000: effective radius ≤ cell
   half-size minus padding; the drawn circle is inside the drawn cell.
3. click_grid hit-test: a pointer inside the circle+jitter but in a
   neighbour cell is NOT on target; a pointer in the cell corner within
   radius+jitter IS.
4. 3x3 Medium on 1080p: radius unchanged from the preset (no cap) —
   behaviour identical to today's default within ±3 px.
5. Old config/profile with only `target.radius_px` → that radius is used
   unchanged; config with both → `size` wins.
6. `metadata.json` has `target_size` (§4.2); `trials.csv`
   `target_radius_px` holds the effective radius; one `TARGET_SHRUNK`
   event when capping happened.
7. follow_moving: each of the five paths stays within [0.1, 0.9] on both
   axes; vertical/diagonals bounce at their ends; horizontal output is
   numerically identical to today for the same seed; px/s along the path
   is equal for horizontal, vertical and both diagonals (±1 %).
8. Dialog: click_grid shows a Target size combo (no px slider);
   follow_moving shows a Movement path combo; choices are saved to and
   restored from a settings profile.
9. Full pytest suite passes (no new failures vs. the pre-change baseline).
10. Live check with the user (qt-mcp, maximized window): 6x6 Large fits
    the cells; each of the four new paths runs; HUD hide/show during a
    grid run keeps the target inside the cell.

## 7. Plan

1. User approves this SPEC (§2-§6). Commit it.
2. Wireframe of the dialog (§4.5) → user approval → commit.
3. `spec-implementer`: Phase A + Phase C (one run, or two if the diff gets
   large — both touch `settings_registry.py` and the dialog).
4. Hub review vs §6 + pytest → live check with the user → commit/push on
   the user's OK → memory update.
5. Phase B: separate go from the user.

## 8. Impl log

(none yet)

## 9. Implementer open questions

(none yet)

## 10. Log

- **2026-10-06** — Objectives received. Code read at `97d03e1` (§3);
  overflow cause measured (6-row cell ≈ 127-137 px vs a 200 px target and
  a 280 px hitbox). Four decisions put to the user; the user first asked
  whether visual angle makes target size differ per subject — answered no
  (fixed monitor size + fixed 650 mm, never per-child; §1). User then
  chose T1 visual angle, T2 3°/5°/8°, T3 shrink target+hitbox, T4 two
  diagonal options. Hub decisions added: equal px/s across straight paths
  (§4.4), logical-px conversion (§4.1), EDID plausibility fallback (§4.1),
  `size` wins over `radius_px` (§4.2), Phase B deferred (§5). SPEC written;
  awaiting approval.
- **2026-10-06** — User approved the whole SPEC, including the four hub
  decisions (equal px/s across straight paths, corner-to-corner
  diagonals, `size` wins over `radius_px`, Phase B deferred). SPEC
  committed; wireframe of the Task settings dialog (§4.5) next.
- **2026-10-06** — Wireframe written and rendered:
  `docs/wireframes/task-settings.md` (+ `.html`, WTMH-themed via
  `tools/apply_wtmh_wireframe_theme.py`). Shows the Grid Click dialog
  (Target size combo with deg + px per item, shrink hint) and the Follow &
  Click dialog (Movement path combo, 5 values), plus an ASCII sketch of
  the five paths. Note found while drawing it: on a ~1000 px tall canvas a
  6x6 cell fits ≈ 111 px, so even Small (≈ 123 px) is shrunk slightly in
  6x6 — expected under T3. Wireframe committed; the user's look at it is
  the /spec-run wireframe gate.
