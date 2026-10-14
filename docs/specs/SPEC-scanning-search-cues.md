---
name: SPEC-scanning-search-cues
title: "Scanning Search: shape-following dwell feedback, a Match the sample search mode, and an optional centre start dot"
status: APPROVED 2026-10-14 - S1-S8 user decisions, wireframe OK; implementation next
created: 2026-10-14
last_updated: 2026-10-14
next_step: plan step 2 (6 prompt WAVs, user approves each) in parallel with step 3 (spec-implementer)
related:
  - SPEC-scanning-task-design-port.md (the icon field, 6 shapes, layout slots)
  - SPEC-target-size-and-motion-paths.md (icon size in degrees, ICON_DRAW_FRAC, fit_icon_radius_px)
  - SPEC-scene-cause-effect-task.md (border-trace dwell P4, prompt WAV pipeline H13 / ASSETS.md, prompt_mode)
  - SPEC-design-system-phase3.md (DROPPED 2026-10-14: the sparkle burst and the target look stay)
---

# SPEC-scanning-search-cues

**Status: APPROVED 2026-10-14 (decisions S1-S8, wireframe OK).**

## 1. Origin

User feedback, 2026-10-14, after trying Scanning Search on the GP3 HD:

1. The icons are circles, squares, triangles, diamonds, hexagons and stars, but the selectable
   outline, the on-target ring and the dwell ring are always circles. Around a triangle this does
   not look good.
2. The child should get a cue for what to look at. The user asked whether that is better, or
   whether there is a better way to design the task.

**Hub analysis.** Today the target is the only icon drawn in colour: a red gradient fill. The other
icons are faint white shapes at alpha 64. The child is told to "look at the lit one". That is a
**pop-out** task. Colour alone gives the answer, so the shapes play no part, despite the
port SPEC's intent ("distinguishing by form"). The user chose to keep pop-out and add a real
shape-search mode as a setting.

## 2. Current code (as of `66b5643`)

- `src/tasks/scanning.py`: `ScanningTask.build_targets` places `n_icons` slots (`grid` default,
  `row`, `ring`). Shapes are fixed per slot (`icon_shapes = [i % 6 ...]`), and the target slot is
  drawn at random per trial. `hit_test` = the circle (effective radius + jitter) AND the nearest
  slot. `scene_spec()` = `{"mode": "icons", "slots", "shapes"}`.
- `src/ui/canvas.py`:
  - `_draw_icon_scene`: draws the distractors, faint `cursor_color` at alpha 64.
  - `_draw_target`: draws the target as a red radial gradient in its own shape, at `ICON_DRAW_FRAC`
    (0.78) of the hit radius. While selectable it adds a 4 px white **circle** at
    `_ring_base_radius() + 4`.
  - `_draw_instant_feedback`: a 5 px **circle** at r + 10.
  - `_draw_progress_ring`: an 8 px **arc** at r + 16, clockwise from 12 o'clock.
  - `_draw_glow`: a radial halo.
  - The particle burst on a hit: the "sparkles", which the user wants kept.
- `src/ui/canvas_shapes.py`: `shape_path(cx, cy, r, shape)` for `SHAPE_CIRCLE, SQUARE, TRIANGLE,
  DIAMOND, HEX, STAR` (0-5).
- `src/ui/scene_buttons.py:69`: `border_trace_path(rect, radius, fraction)` is Choice-making's
  border-trace dwell for rounded rectangles, clockwise from top centre.
- `configs/tasks/scanning.yaml`: `trials` 6, `timeout_ms` 10000, `layout.n_icons` 4 (2-8),
  `layout.size`, `layout.arrangement`, `layout.margin_frac`. The settings registry entries are
  `applies_to=("scanning",)` and appear in the **Icons** card of the test configuration page.

## 3. Decisions (user, 2026-10-14)

| # | Decision |
|---|---|
| S1 | **Dwell feedback follows the shape (option A).** The dwell progress is traced along the icon's own outline, offset outwards, clockwise from the top, closing when the dwell completes. The **on-target ring** and the **selectable outline** follow the shape too, at the same offsets as today. For a circle this looks exactly as today. |
| S2 | **Two search modes, as a setting** `search_mode` = `pop_out` (default, today's behaviour) / `match_sample`. |
| S3 | **Centre start dot as a setting** `start_dot` (tick box), **off by default**. |
| S4 | **Sample: centre, then corner.** In `match_sample` the sample shape is shown alone at the screen centre, then the field appears and the sample stays small at the top centre as a reminder for the rest of the trial. |
| S5 | **Spoken prompt.** A voice names the shape ("Find the star!"), one WAV per shape, made like the Choice-making prompts. The text "Find this!" is shown under the centre sample. |
| S6 | **Reshuffle each trial** in `match_sample`. The shapes move to new slots every trial, and the target's shape appears only once in the field. |
| S7 | **All icons bright, one colour** in `match_sample`. Every icon is drawn like today's target (the target colour, same gradient), so only the shape tells them apart. |
| S8 | **The sparkle burst and today's target look stay** in both modes (phase 3 was dropped). |

## 4. Design

### 4.1 Shape-following feedback (S1), every task

- **Paths.** A new helper `shape_outline_path(cx, cy, r, shape, offset)` returns the closed outline
  of `shape_path` grown outward by `offset` px. It is built with `QPainterPathStroker` (or by
  scaling about the centre for a convex shape; the star is concave, so stroker or
  offset-polygon). A second helper `trace_fraction(path, fraction)` returns the part of the path
  from its top-most point, clockwise, of `fraction` of its length. It uses
  `QPainterPath.percentAtLength` / `pointAtPercent` and is built like `border_trace_path`.
- **What changes:**
  - `_draw_target`'s selectable outline is `shape_outline_path(.., offset 4)`.
  - `_draw_instant_feedback` is `offset 10`.
  - `_draw_progress_ring` traces `offset 16` by `dwell_progress`.
  - Pen widths stay 4 / 5 / 8 px, round caps and joins.
- **Where.** The helpers are used for every target. For the circle targets of Static Click, Grid
  Click and Follow the Target the result is the same circle as today, which keeps one code path.
  The glow and the sparkle burst are unchanged.

### 4.2 Search mode `pop_out` (today)

Unchanged, apart from 4.1. With `start_dot` on, the start dot (4.4) comes first.

### 4.3 Search mode `match_sample` (S4-S7)

**One trial:**

1. With `start_dot` on: the start dot (4.4).
2. **Sample phase.**
   - The target's shape is drawn alone at the centre at the field's icon size, in the target
     colour, with "Find this!" under it (1.5 deg lettering, the Choice-making banner style).
   - The spoken prompt `prompt_<shape>.wav` plays.
   - The phase lasts `max(sample_ms, prompt length)`, with `sample_ms` 1500.
   - Selection is closed and the trial clock has not started.
3. **Search phase.**
   - The field appears: every icon is drawn bright in the target colour (S7).
   - The shapes are a fresh shuffle with the target's shape exactly once (S6).
   - The reminder sample sits at top centre at 50 % of the icon size, without the text. It never
     overlaps a slot: the layout's top margin keeps it clear; if a slot would overlap it, the
     reminder moves to the top-left corner.
   - `t_selectable_start_ns` and the timeout start when the field appears.
   - Only the target is selectable. The 4.1 outline marks it **only once the pointer is on it** (the
     on-target ring and the dwell trace). There is no selectable outline before that, because it
     would give the answer away.
4. A hit gives the sparkle burst and the hit sound, as today. A wrong icon gets no feedback beyond
   what pop-out gives today: dwell on it does not complete, and it is recorded as an attempt
   (4.6).

**Shuffle rules (S6):**
- Each trial draws a target shape from the 6 shapes, then gives the other `n_icons - 1` slots
  distinct other shapes where possible.
- With more than 6 icons, a distractor shape may repeat, but never the target's.
- Seeded by the run's RNG, so a run is reproducible.
- The target slot is drawn as today.

**Prompt audio:**
- Location: `configs/assets/scanning/audio/en/prompt_<shape>.wav` for circle, square, triangle,
  diamond, hexagon, star.
- Sentence: "Find the <shape>!".
- Made with the Choice-making pipeline: `mcp-audio-openrouter` `generate_voice`, `openai/gpt-audio`,
  voice `shimmer`, the same generation prompt, trim, fades and -20 dBFS RMS.
- Provenance in `configs/assets/scanning/ASSETS.md`. The user approves every file.
- A missing file falls back to `sample_ms` with no voice and a log line.

### 4.4 Centre start dot (S3)

- A small dot (1 deg, the cursor colour) appears at the screen centre before each trial's field
  (and before the sample, in `match_sample`).
- When the gaze (or the mouse in Mouse mode) has stayed within 2 deg of the dot for **300 ms**, the
  dot goes and the trial continues.
- If that does not happen within **5 s**, the trial continues anyway and records
  `start_dot_timeout: true`.
- Practice and Preview use it too. With a Switch selection, the dot still waits for gaze, not the
  switch.

### 4.5 Settings

- In the **Icons** card, under Number of icons:
  - **Search mode:** radio "Pop-out: the target is the coloured icon" / "Match the sample: find the
    shape shown first".
  - **Start each trial from the centre:** tick box.
- Registry entries `search_mode` and `start_dot`, `applies_to=("scanning",)`.
- Both are stored with the test, written to `metadata.json` `settings.structural`, and shown in the
  report's Test Configuration ("Search mode: Pop-out / Match the sample", "Centre start: On / Off").
- The default configuration (Standard) keeps `pop_out` and `start_dot` off, so existing tests and
  profiles behave as today.
- The Start-page instructions for Scanning follow `search_mode`. They are PLACEHOLDER text, like
  the others: Pop-out keeps today's text; Match the sample says "You will see and hear which shape
  to find. Then look at the same shape among the others."

### 4.6 Recording

- **Per trial:** `search_mode`, `target_shape` (name), `field_shapes` (slot order), and
  `start_dot_ms` (time to fixate the dot, or null on timeout) with `start_dot_timeout`. Reaction
  time stays measured from the field's appearance.
- **New events:**
  - `START_DOT_SHOWN` / `START_DOT_DONE` (`fixated` or `timeout`);
  - `SAMPLE_START` (`shape`, `duration_ms`, `duration_source` wav / default);
  - `FIELD_SHOWN`.
- `docs/DATA_SCHEMA.md` is updated.
- **Wrong-icon looks** in `match_sample`: the existing attempt count covers a completed dwell on a
  wrong icon. In addition, `first_icon_looked_at` (slot and shape of the first icon the pointer
  entered after the field appeared) is recorded per trial; it tells whether the child went
  straight to the match.

## 5. Scope

**In:** 4.1-4.6; the 6 prompt WAVs with `ASSETS.md`; tests; `DATA_SCHEMA.md`; the report's Test
Configuration rows.

**Out:**
- other languages (`zh-TW` later, the same folder layout);
- new shapes or picture icons;
- changing the target colour or look, the glow, or the sparkles (S8);
- `row` / `ring` arrangement changes;
- feedback on a wrong icon beyond today's.

## 6. Acceptance criteria

| # | Criterion | Checked by |
|---|---|---|
| C1 | For each of the 6 shapes the selectable outline, on-target ring and dwell trace follow the shape at offsets 4 / 10 / 16; the trace starts at the top-most point, runs clockwise and has the length fraction = dwell progress (±1 %); a circle renders as today | unit test (path maths) + offscreen render |
| C2 | `pop_out` with `start_dot` off behaves exactly as before (same trial sequence for a seed, same events) | unit test |
| C3 | `match_sample`: the sample phase shows the shape, plays the WAV, lasts max(1500 ms, WAV); selection is closed; the field then shows every icon bright, the target's shape exactly once, a fresh shuffle per trial, seeded | unit test with a fake clock |
| C4 | In `match_sample` no outline marks the target before the pointer is on it; the reminder never overlaps a slot | unit test + offscreen render |
| C5 | Start dot: 300 ms within 2 deg continues; 5 s without continues with `start_dot_timeout`; reaction time is measured from the field | unit test with a fake clock |
| C6 | Settings in the Icons card, stored with the test, in `metadata.json` and the report; Standard keeps today's behaviour | unit test |
| C7 | Events and per-trial fields of 4.6 recorded; `DATA_SCHEMA.md` updated | unit test |
| C8 | Live, the user as subject on the GP3 HD: both modes with and without the start dot; the shape-following dwell reads well round a triangle and a star; the prompts are clear | live |
| C9 | Full pytest green (except the known skip-worktree alpha checks) | hub rerun |

## 7. Plan

1. **DONE 2026-10-14 -** Wireframe: `docs/wireframes/scanning-search.md` (the run states) and the Icons card in
   `task-config.md`. User GATE 1.
2. Prompt WAVs: generate the 6, with the user's approval of each. This can run in parallel with
   step 3.
3. Implement 4.1-4.6 (`spec-implementer`, isolated worktree).
4. Hub review and the full pytest.
5. Live check C8 with the user as subject.
6. Commit on the user's OK.

## 8. Impl log

(empty)

## 9. Open decisions (for the user)

None open. The hub chose these defaults; they are easy to change:
- the sample phase 1500 ms;
- the start dot (1 deg, 2 deg radius, 300 ms, 5 s);
- the reminder at 50 % size;
- the prompt sentence "Find the <shape>!".

## 10. Log

- **2026-10-14** - Draft by the hub from the user's feedback. User decisions S1 (trace the shape's
  edge), S2 (both search modes as a setting, pop-out default), S3 (start dot as a setting, off by
  default), S4 (sample centre, then corner), S5 (spoken prompt + "Find this!"), S6 (reshuffle each
  trial), S7 (all icons bright, one colour), S8 (sparkles and target look stay, from the phase-3
  drop). Next: the wireframe.
- **2026-10-14** - User approved the wireframe (`scanning-search.md`, the Icons card in `task-config.md`) and the hub defaults of section 9. SPEC APPROVED; plan step 1 DONE. Next: the prompt WAVs (step 2) and the implementer (step 3), in parallel.
