---
name: SPEC-scanning-search-cues
title: "Scanning Search: shape-following dwell feedback, a Match the sample search mode, and an optional centre start dot"
status: DONE 2026-10-14 - implemented, hub-reviewed, live-checked by the user on the GP3 HD (S9 revision included); committed
created: 2026-10-14
last_updated: 2026-10-14
next_step: none (all plan steps done)
related:
  - SPEC-scanning-task-design-port.md (the icon field, 6 shapes, layout slots)
  - SPEC-target-size-and-motion-paths.md (icon size in degrees, ICON_DRAW_FRAC, fit_icon_radius_px)
  - SPEC-scene-cause-effect-task.md (border-trace dwell P4, prompt WAV pipeline H13 / ASSETS.md, prompt_mode)
  - SPEC-design-system-phase3.md (DROPPED 2026-10-14: the sparkle burst and the target look stay)
---

# SPEC-scanning-search-cues

**Status: DONE 2026-10-14 (decisions S1-S9; implemented, live-checked, committed).**

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
| S4 | **Sample: centre, then corner.** In `match_sample` the sample shape is shown alone at the screen centre, then the field appears and the sample stays small at the top centre as a reminder for the rest of the trial. **Revised 2026-10-14 after the live check (S9):** the reminder is now a setting, off by default. |
| S5 | **Spoken prompt.** A voice names the shape ("Find the star!"), one WAV per shape, made like the Choice-making prompts. The text "Find this!" is shown under the centre sample. |
| S6 | **Reshuffle each trial** in `match_sample`. The shapes move to new slots every trial, and the target's shape appears only once in the field. |
| S7 | **All icons bright, one colour** in `match_sample`. Every icon is drawn like today's target (the target colour, same gradient), so only the shape tells them apart. |
| S8 | **The sparkle burst and today's target look stay** in both modes (phase 3 was dropped). |
| S9 | **2026-10-14, after the live check: the reminder is a setting, off by default** (`sample_reminder`, tick box "Show the shape while searching", greyed for Pop-out). The user found that the small shape could draw the child's gaze away from the icons; the centre sample with "Find this!" and the spoken prompt are enough. |

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
   - Only with `sample_reminder` on (S9, off by default): the reminder sample sits at top centre at 50 % of the icon size, without the text. It never
     overlaps a slot: the layout's top margin keeps it clear; if a slot would overlap it, the
     reminder moves to the top-left corner.
   - `t_selectable_start_ns` and the timeout start when the field appears.
   - Only the target is selectable. The 4.1 outline marks it **only once the pointer is on it** (the
     on-target ring and the dwell trace). There is no selectable outline before that, because it
     would give the answer away.
4. A hit gives the sparkle burst and the hit sound, as today. A wrong icon gets no feedback at all:
   no sound, no ring or trace, no sparkle. Selecting it is counted as a **wrong selection** (4.6;
   user 2026-10-14): with a Dwell selection a completed dwell on it (the same threshold as the
   target's), with a Switch selection a press while the pointer is on it (a press on no icon is not
   one); the trial goes on until the target or the timeout. After a dwell's, the icon must be left
   before it can count again (the dwell's refractory and hold grace apply). Pop-out has none.

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
  - **Show the shape while searching:** tick box (`sample_reminder`, S9), off
    by default, greyed while the search mode is Pop-out.
  - **Start each trial from the centre:** tick box.
- Registry entries `search_mode` and `start_dot`, `applies_to=("scanning",)`.
- Both are stored with the test, written to `metadata.json` `settings.structural`, and shown in the
  report's Test Configuration ("Search mode: Pop-out / Match the sample", "Centre start: On / Off").
- The default configuration (Standard) keeps `pop_out` and `start_dot` off, so existing tests and
  profiles behave as today.
- The Start-page instructions for Scanning follow `search_mode`. They are PLACEHOLDER text, like
  the others: Pop-out keeps today's text; Match the sample says "You will see and hear which shape
  to find. Then look at the same shape among the others." With `start_dot` on, either mode's
  instructions begin with the PLACEHOLDER sentence "Each time, first look at the small dot in the
  middle." (user 2026-10-14).

### 4.6 Recording

- **Per trial:** `search_mode`, `target_shape` (name), `field_shapes` (slot order), and
  `start_dot_ms` (time to fixate the dot, or null on timeout) with `start_dot_timeout`. Reaction
  time stays measured from the field's appearance.
- **New events:**
  - `START_DOT_SHOWN` / `START_DOT_DONE` (`fixated` or `timeout`);
  - `SAMPLE_START` (`shape`, `duration_ms`, `duration_source` wav / default);
  - `FIELD_SHOWN`;
  - `WRONG_SELECTION` (`trial`, `slot`, `shape`, at its time; Match the sample).
- `docs/DATA_SCHEMA.md` is updated.
- **Wrong selections** in `match_sample` (user, 2026-10-14): selecting an icon that is not the
  target is recorded: per trial `wrong_selections` (a count, 0 when none) and `wrong_selection_shapes`
  (the shapes in order, `star;circle`), and a `WRONG_SELECTION` event. With a Dwell selection it is a
  completed dwell on the icon; with a Switch selection a press while the pointer is on it, which stays
  a `MISS_CLICK` and a click error as today (a press on no icon is not a wrong selection). Nothing
  changes on screen, and a dwell one is not an `attempts` / `click_errors` count. Pop-out has none.
- **First look** in `match_sample`: `first_icon_looked_at` (slot and shape of the first icon the
  pointer entered after the field appeared) is recorded per trial; it tells whether the child went
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
| C4 | In `match_sample` no outline marks the target before the pointer is on it; no reminder by default, and with `sample_reminder` on it never overlaps a slot | unit test + offscreen render |
| C5 | Start dot: 300 ms within 2 deg continues; 5 s without continues with `start_dot_timeout`; reaction time is measured from the field | unit test with a fake clock |
| C6 | Settings in the Icons card, stored with the test, in `metadata.json` and the report; Standard keeps today's behaviour | unit test |
| C7 | Events and per-trial fields of 4.6 recorded, wrong selections included (a completed dwell on a wrong icon, counted again only after leaving it, or a switch press while on one; none in pop-out); `DATA_SCHEMA.md` updated | unit test |
| C8 | Live, the user as subject on the GP3 HD: both modes with and without the start dot; the shape-following dwell reads well round a triangle and a star; the prompts are clear | live |
| C9 | Full pytest green (except the known skip-worktree alpha checks) | hub rerun |

## 7. Plan

1. **DONE 2026-10-14 -** Wireframe: `docs/wireframes/scanning-search.md` (the run states) and the Icons card in
   `task-config.md`. User GATE 1.
2. **DONE 2026-10-14 -** Prompt WAVs: generate the 6, with the user's approval of each (`5ca93ad`).
3. **DONE 2026-10-14 -** Implement 4.1-4.6 (`spec-implementer`, isolated worktree).
4. **DONE 2026-10-14 -** Hub review and the full pytest.
5. **DONE 2026-10-14 -** Live check C8 with the user as subject (revision S9 from it, re-checked).
6. **DONE 2026-10-14 -** Commit on the user's OK, merged into `feature/compass-task-flow`.

## 8. Impl log

### 2026-10-14 - spec-implementer (model `claude-sonnet-5-5`), sections 4.1-4.6, worktree `scanning-cues`

Implemented 4.1-4.6 for acceptance C1-C7. C8 (live check) and C9 (the hub's rerun) are not mine. No commit, no staging, no app launch, no device; `configs/default.yaml` and `configs/local_state.json` untouched.

**Files, new.**
- `src/ui/canvas_trace.py`: `shape_outline_path(cx, cy, r, shape, offset)` (the glyph grown outward by the offset: round at convex corners, mitred at the star's reflex ones, built from lines and arcs, clockwise, starting at the top-most point, the middle of a flat top), `trace_fraction(path, fraction)`, and the three drawers (`draw_selectable_outline` 4 px / offset 4, `draw_instant_ring` 5 px / 10, `draw_dwell_trace` 8 px / 16; round caps and joins).
- `src/ui/canvas_search.py`: the start dot, the sample (shape at the icon size plus "Find this!" through `scene_banner.draw_banner`, the Choice-making banner style, 1.5 deg lettering), Match the sample's bright field (every icon in today's target gradient) and the reminder.
- `src/tasks/search_cues.py` (Qt-free): the modes, the constants (1500 ms, 1 deg dot, 2 deg radius, 300 ms, 5 s, 50 %), `draw_field` (the S6 shuffle), `reminder_placement`, `prompt_wav_path`, `apply_search_cues` (sizes by visual angle, with its log line).
- `src/ui/scanning_settings.py`: the two registry entries.

**Files, changed.** `src/ui/canvas_shapes.py` (`shape_vertices`, `SQUARE_CORNER_FRAC`; `shape_path` draws exactly as before), `src/ui/canvas.py` (497 lines: the three rings call `canvas_trace`, the search stages `canvas_search`; the target gradient moved to `bright_gradient`), `src/tasks/scanning.py` (464 lines), `src/data/schema.py`, `src/data/report_config.py`, `src/ui/settings_registry.py`, `src/ui/config_widgets.py` (tooltips), `src/ui/task_instructions.py`, `src/ui/scene_audio.py` (`SearchAudio`), `src/app.py` (`apply_search_cues` in `_resolve_target_size`, `SearchAudio` next to `SceneAudio`), `configs/tasks/scanning.yaml` (`search_mode: pop_out`, `start_dot: false`, `sample_ms: 1500`), `docs/DATA_SCHEMA.md`.

**How it works.**
- The start dot and the sample are *pre-trial phases* of `ScanningTask` (`Phase.SHOW_TARGET`, state in `_Pre`); the trial (its `TrialRecord`, `t_target_shown_ns`, `t_selectable_start_ns`, the timeout, `TARGET_SHOWN`, `on_target_shown`) starts when the field appears, so reaction time is from the field and `BaseTask` is untouched. A pause during them drops them (voice cut) and they start over on resume; a switch press during them is `SWITCH_IGNORED` with `phase` `start_dot` / `sample`; `trial_number` names the trial being prepared.
- Pop-out draws no more from the RNG than before (same target slots for a seed), and its `scene_spec` is the three-key dict of before; `start_dot` off and `pop_out` leave frames, events and rows as they were (C2 is a test).
- Match the sample draws each trial's field in `build_targets` after the target slot, from the run's RNG. Wrong-icon looks: `first_icon_looked_at_*` (below).
- The prompt WAV length is read with `wav_duration_ms` from `<assets_root>/scanning/audio/<language>/prompt_<shape>.wav` (`ScanningTask.assets_root`, overridable like Choice-making's); a missing or unreadable file gives `sample_ms`, `duration_source` `default` and one session-log line. The tests never read the real folder; the six WAVs are the hub's.
- Events: `START_DOT_SHOWN`, `START_DOT_DONE` (`result` `fixated` / `timeout`, `elapsed_ms`), `SAMPLE_START` (`shape`, `duration_ms`, `duration_source`), `FIELD_SHOWN`. Trial fields: `search_mode`, `target_shape`, `field_shapes` (names joined by `|`, slot order), `start_dot_ms`, `start_dot_timeout`, `first_icon_looked_at_slot`, `first_icon_looked_at_shape`.

**Tests added.** `tests/test_canvas_trace.py` (path maths for all 6 shapes at offsets 4 / 10 / 16: distance to the glyph, start at the top, clockwise, trace length = progress within 1 %, circle outline, mitred star; rendered pixels: rings hug a triangle / star / square, a circle target is ringed as before, pen widths), `tests/test_scanning_search.py` (setting, S6 shuffle, C2, C3, timings with fake WAVs and the missing-file fallback, trial fields, first icon), `tests/test_scanning_start_dot.py` (C5, switch, pause, the reminder's place for every arrangement and two canvas sizes), `tests/test_scanning_settings.py` (C6: registry, Icons card, stored with the test, metadata, report rows, instructions), `tests/test_scanning_recording.py` (C7 through a real recorder, `DATA_SCHEMA.md` names every column and event), `tests/test_scanning_canvas.py` (render half of C4, sample / dot / field stages, `SearchAudio`, `GuiFeedback` forwarding). Updated for the new controls and columns: `tests/test_settings_layout.py`, `tests/test_config_page_phase2.py`, `tests/test_run_modes_app.py`, `tests/test_follow_task.py`, `tests/test_recording_additions.py`, `tests/test_run_engine.py`.

**pytest** (four shards of the whole `tests/` folder, venv `dev/.venv`, run from the worktree root with `PYTHONPATH=.` because the venv's editable install points at the main checkout): **4566 passed, 5 failed**, the 5 being the known fresh-worktree baseline (`test_config_flow.py::test_a_new_test_opens_at_standard_with_the_task_defaults` and `test_task_config_page.py::test_a_new_test_opens_with_standard_and_the_defaults` for click_static, click_grid, follow_moving and scanning: alpha 0.35 vs 0.22 in the skip-worktree `configs/default.yaml`). The four shard lines: `1197 passed`, `1308 passed`, `5 failed, 1039 passed`, `1022 passed`. 216 of them are new (`test_canvas_trace` 74, `test_scanning_search` 42, `test_scanning_start_dot` 41, `test_scanning_settings` 27, `test_scanning_recording` 18, `test_scanning_canvas` 14). `ruff check` is clean on every file I touched.

**Deviations from the SPEC: none in what it asks for.** Judgement calls inside it, all easy to change:
1. `trace_fraction` samples with `percentAtLength` / `pointAtPercent` as written, but `percentAtLength` costs about 60 us a call on a circle (a cold trace 3-8 ms), so `draw_dwell_trace` caches the sampled outline per position, radius and shape (warm: all three rings under 0.6 ms a frame).
2. `first_icon_looked_at` is two columns, `first_icon_looked_at_slot` and `first_icon_looked_at_shape`, recorded in Match the sample only (blank in Pop-out; extending it is a one-line change). "Entered" is the target's own hit area (radius plus the jitter margin, nearest slot), counting the field's first frame.
3. `start_dot_ms` is from the dot appearing to its going, the 300 ms hold included (blank on a timeout). `FIELD_SHOWN` is emitted in Match the sample only; in Pop-out with the start dot `TARGET_SHOWN` is the field.
4. The seven trial columns sit between `mean_dist_px` and `prompt_object`, so Choice-making's thirteen stay the last of the file; the four existing tests that pin the tail now include `SCANNING_COLUMNS`.
5. In Match the sample the selectable outline (white, offset 4) waits for the pointer like the on-target ring: the SPEC says no outline marks the target before the pointer is on it.
6. Not specified by the SPEC, kept as today: between trials the field stays on screen with the target's slot blank (Match the sample adds no reminder there); before the first trial Match the sample draws nothing.
7. The configuration page requires a tooltip on every control, so `CONFIG_TOOLTIPS` has two new entries; `sample_ms` is a YAML knob with no control.

**Left undone.** The six prompt WAVs and `ASSETS.md` (the hub's step 2); C8; the Start-page text for the centre dot (section 9, question 2).

### 2026-10-14 (follow-up) - the user's answers to the two section 9 questions (spec-implementer, `claude-sonnet-5-5`)

Implemented in the same worktree; no commit, no staging.

**Wrong selections (4.3 step 4, 4.6, C7), Match the sample only.**
- `WrongIconDwell` (`src/tasks/search_cues.py`) runs a dwell on whichever icon that is not the target the pointer is on, with the **target dwell's own `DwellConfig`** (threshold, refractory, hold grace); moving to another icon starts it over, and the dwell's refractory still applies after a count. After a completed one the icon is *locked* until a valid pointer has been off it for the hold grace, so one long look is one wrong selection; a blink neither counts nor unlocks.
- `ScanningTask._note_icons` (was `_note_first_icon`) feeds it with the frame's pointer **before** the frame's selection, like the first-icon note, so a trial that ends in that frame already has it in its row; the field's first frame counts too. It records on the `TrialRecord` `wrong_selections` (a count, 0 from the start of a Dwell trial) and `wrong_selection_shapes` (`star;circle`), and fires `WRONG_SELECTION` (`trial`, `slot`, `shape`, at the time it completed). Nothing is drawn or played, `FrameResult` and `scene_spec` are untouched, and `attempts` / `click_errors` are not changed (a wrong selection is not a click).
- Pop-out: no tracker, columns blank, no event. Switch selection: columns blank (question added to section 9). The two columns are the last two of `SCANNING_COLUMNS`, which is now **nine** columns long; `first_icon_looked_at_*` stays.
- SPEC wording updated: 4.3 step 4, 4.5, 4.6 (the new events list, "Wrong selections", "First look"), C7. `docs/DATA_SCHEMA.md`: the two columns, the event, the Scanning Search rows paragraph.

**The centre dot's sentence (4.5).** `task_instructions.py`: with `start_dot` on, the Scanning instructions of either search mode start with the PLACEHOLDER step "Each time, first look at the small dot in the middle."; it takes the gaze-dot sentence ("The small dot on the screen shows where you are looking.") with it, so the old first step follows without it and there is one more step. Mouse reads "Move the mouse to point at the screen. Each time, first point at the small dot in the middle." Off, or any other task: unchanged.

**Tests.** New `tests/test_scanning_wrong_selection.py` (21: the rule and the threshold, nothing on screen and no feedback, carrying on to the target and to the timeout, one long look counts once, the glance inside the grace and the 160 ms leave, the shapes in order, moving between icons, blink, the refractory, per-trial reset, a dwell already running when the field appears, pop-out, Switch, Mouse, a pause, the helper alone). Extended: `test_scanning_recording.py` (the nine columns, `WRONG_SELECTION` in the real `events.jsonl`, a recorded run with two wrong selections), `test_scanning_settings.py` (the dot sentence for both modes, cursor hidden, mouse, switch, off, other tasks), `test_scanning_search.py` (`make(refractory_ms=...)`), and the comments of the four tail-pinning tests ("nine").

**pytest** (four shards of the whole `tests/` folder, `PYTHONPATH=.`): **4598 passed, 5 failed**, the 5 being the same known baseline as before (`test_config_flow.py::test_a_new_test_opens_at_standard_with_the_task_defaults`; `test_task_config_page.py::test_a_new_test_opens_with_standard_and_the_defaults` for click_static, click_grid, follow_moving, scanning). The shard lines: `956 passed`, `1502 passed`, `1 failed, 1049 passed`, `4 failed, 1091 passed`. 248 tests are new in all (the 216 of the first entry plus 32). `ruff check` is clean on every file I touched; no file is over 500 lines (`scanning.py` 475, `canvas.py` 497).

**Supersedes in the entry above:** "seven trial columns" is nine; and the "left undone" Start-page text for the centre dot is done.

### 2026-10-14 (follow-up 2) - Switch presses count as wrong selections (spec-implementer, `claude-sonnet-5-5`)

`ScanningTask._switch_press` (override, calls `super()` first) counts a counted press made while the pointer is on an icon that is not the target: `wrong_selections` + 1, the shape appended, `WRONG_SELECTION` (`trial`, `slot`, `shape`); judged at the press point of the base rule (a blink's 150 ms fallback included), it stays a `MISS_CLICK` and a click error, a press on no icon or an ignored press does not count, and a Switch trial reads 0 from its start, not blank. The shared counting is `_count_wrong`. Pop-out unchanged. SPEC 4.3, 4.6, C7 and `DATA_SCHEMA.md` reworded; tests in `tests/test_scanning_wrong_selection.py`; pytest: **4607 passed, 5 failed** (the same 5 known baseline failures; shard lines `956 passed`, `1502 passed`, `1 failed, 1058 passed`, `4 failed, 1091 passed`; 257 tests are new in all), `ruff` clean, no file over 500 lines (`scanning.py` 497).

## 9. Open decisions (for the user)

None open. The hub chose these defaults; they are easy to change:
- the sample phase 1500 ms;
- the start dot (1 deg, 2 deg radius, 300 ms, 5 s);
- the reminder at 50 % size;
- the prompt sentence "Find the <shape>!".

### Implementer open questions

- **ANSWERED 2026-10-14 (user): (b), in Match the sample only, see 4.3 step 4, 4.6 and the follow-up in section 8.** **2026-10-14 - a wrong icon in Match the sample (4.3 step 4 against 4.6).** 4.3 says a dwell on a wrong icon "does not complete, and it is recorded as an attempt (4.6)", and 4.6 says "the existing attempt count covers a completed dwell on a wrong icon". Today a dwell only ever builds on the target (`on_target` is the target's hit area), so a dwell on a wrong icon never completes and nothing counts it; only a switch press off the target is an attempt (`MISS_CLICK`, `attempts`, `click_errors`). I changed nothing there and counted nothing new; the wrong-icon information is `first_icon_looked_at_slot` / `_shape`. Decide: (a) leave it as built, or (b) count a wrong-icon dwell (a dwell timer on whichever icon the pointer is on; a completed one is a `MISS_CLICK` and `attempts` + 1, still no feedback). (b) is new engine behaviour, so I did not start it.
- **ANSWERED 2026-10-14 (user): add "Each time, first look at the small dot in the middle." when `start_dot` is on, both modes; PLACEHOLDER text; done, see the follow-up in section 8.** **2026-10-14 - Start-page text for the centre dot.** 4.5 gives Start-page text for `search_mode` only. With `start_dot` on, the instructions say nothing about the dot the child sees before each trial. Not added. Decide whether to add a PLACEHOLDER step (for example "Look at the small dot in the middle of the screen first.").

- **ANSWERED 2026-10-14 (user): yes, a press on a wrong icon counts; see 4.3, 4.6 and the note in section 8.** **2026-10-14 - wrong selections with a Switch selection.** The answer counts a completed *dwell*. With a Switch there is
  no dwell: a press while looking at a wrong icon is already a `MISS_CLICK`, an `attempts` + 1 and a `click_errors` + 1,
  and I left `wrong_selections` / `wrong_selection_shapes` **blank** for a Switch test (0 would say "none happened"; it
  is not measured as a dwell). Decide whether a press on a wrong icon should also count as a wrong selection (and
  fire `WRONG_SELECTION`) so that both selection methods fill the two columns.

## 10. Log

- **2026-10-14** - Draft by the hub from the user's feedback. User decisions S1 (trace the shape's
  edge), S2 (both search modes as a setting, pop-out default), S3 (start dot as a setting, off by
  default), S4 (sample centre, then corner), S5 (spoken prompt + "Find this!"), S6 (reshuffle each
  trial), S7 (all icons bright, one colour), S8 (sparkles and target look stay, from the phase-3
  drop). Next: the wireframe.
- **2026-10-14** - User approved the wireframe (`scanning-search.md`, the Icons card in `task-config.md`) and the hub defaults of section 9. SPEC APPROVED; plan step 1 DONE. Next: the prompt WAVs (step 2) and the implementer (step 3), in parallel.
- **2026-10-14** - Live check by the user (scanning-cues worktree). One change asked for: the small reminder could pull the child's gaze away from the icons. User decision S9: the reminder becomes the setting `sample_reminder`, **off by default**, greyed for Pop-out (Icons card, under Search mode; report row "Sample reminder: On / Off"; `metadata.json` `settings.structural.sample_reminder`). Done by the hub: `scanning.py` (draws the reminder only when on), `scanning_settings.py` (setting + `SCANNING_GREYED_BY`), `settings_registry.py`, `config_widgets.py` (tooltip), `report_config.py`, `configs/tasks/scanning.yaml`, `DATA_SCHEMA.md`, wireframes; tests updated and added (default off, greyed for Pop-out, report row, metadata).
- **2026-10-14** - Hub rerun after S9: 4619 tests collected, the only failures the 5 known skip-worktree `default.yaml` checks; `ruff` clean. The user re-checked S9 live and asked to commit and merge. SPEC DONE.
