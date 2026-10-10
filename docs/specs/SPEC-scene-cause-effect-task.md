---
name: SPEC-scene-cause-effect-task
title: A fifth test - an animated scene with 8 side buttons; a spoken prompt names the button; the selected object animates; gaze look-back to the effect is measured
status: draft 2026-10-10 - design written; hub decisions H1-H14 and questions S1-S8 (section 3) wait for the user
created: 2026-10-10
last_updated: 2026-10-10
next_step: the user approves H1-H14 and answers S1-S8; then step 1 (wireframes, the UI gate) and step 2 (style anchor art, needs the OpenRouter key)
related:
  - SPEC-grid3-calibration-parklife-feasibility.md (Part B feasibility, decisions U4, Q6-Q8)
  - docs/grid3/park-life/README.md (reference: layout, effects, timings, object regions - section 9)
  - SPEC-input-selection-and-follow.md (per-test pointer Gaze / Mouse and selection Dwell / Switch)
  - SPEC-target-size-and-motion-paths.md (sizes in degrees; 650 mm viewing distance)
  - SPEC-grid-cell-gap.md (cell gap as a dead zone)
  - SPEC-gazepoint-analysis-export-parity.md (all_gaze.csv, used for look-back)
---

# SPEC-scene-cause-effect-task - "Make it happen" scene test

**Status: draft 2026-10-10. Not approved. Branch `feature/compass-task-flow` at `9f160c4`.
Reference design is Smartbox Grid 3 "Park Life" page 2, adapted into a scored test. No
Smartbox art, sound or text is copied; all assets are our own (AI-generated, user-approved).**

## 1. Origin

- Feasibility study `SPEC-grid3-calibration-parklife-feasibility.md` Part B (2026-10-10): a Park
  Life-style test is feasible with no hardware unknowns.
- User decisions there:
  - U4: measure **prompted trials** (hit / miss / timeout) **and look-back to the effect**.
  - Q6: art is **AI-generated** through the user's `mcp-image-openrouter`, and the user checks every asset.
  - Q7: prompts in **English** first, Traditional Chinese later.
  - Q8: **page 2 scope only** (no sentence, chat or opinion pages).
- Why a new test: the four existing tests measure targeting with a neutral reward (glow + short
  sound). This test adds a large, contingent reward (the object the child chose comes alive) and a
  built-in gaze shift from the button at the screen edge back to the effect in the centre.

## 2. Current code (as of `9f160c4`)

- `src/engine/task_runner.py` `TASK_REGISTRY`: `click_static`, `click_grid`, `follow_moving`,
  `scanning`. Names and one-line descriptions in `src/engine/task_info.py` `TASK_INFO`.
- `src/tasks/base_task.py` `BaseTask`: one `TargetSpec` per trial, phases `READY`,
  `WAIT_INPUT`, `ITI`, `DONE` (also `SHOW_TARGET`, `RESULT` in the enum). `update()` hit-tests the
  pointer against **the target only**:
  - Dwell mode: `self.dwell.update(t_ns, on_target, ...)` accumulates only while on the target, so
    **a dwell on any other cell never completes and is never a miss**.
  - Switch mode: a press anywhere off the target is `MISS_CLICK` (attempts + 1); the trial goes on.
  - A trial ends on a hit or at `timeout_ms`; then the ITI (`inter_trial_interval_ms`).
- `ScanningTask` shows distractors (`scene_spec` mode `"icons"`) and rejects a look that is closer
  to another slot, but distractors are visual only.
- `ClickGridTask` draws a board (`scene_spec` mode `"grid"`); cell gap is a dead zone.
- `src/ui/canvas.py` `TaskCanvas.paintEvent` draws per `scene["mode"]`: `single`, `icons`, `grid`,
  `moving` (QPainter, no sprite or image layer support today). `burst()` draws hit particles.
- `src/app.py`: `QSoundEffect` WAV cues per theme (`configs/assets/sounds/forest_hit.wav`,
  `forest_miss.wav`, `space_*`), `_tick` driven by a `QTimer`; `scene_spec()` re-read each tick.
- Task configs: `configs/tasks/<task>.yaml` (`trials`, `timeout_ms`,
  `inter_trial_interval_ms`, `target.size` small / medium / large = 3 / 5 / 8 deg, `feedback.*`).
  Settings cards: `src/ui/settings_registry.py` (`applies_to=(...)` per task, `_CARDS`).
- Recording: events and trials through the recorder; per-sample gaze in `all_gaze.csv`; I-VT
  saccades in `src/data/saccades.py`; reports in `src/data/report_*.py` and `src/ui/report_*.py`.

## 3. Decisions

### 3.1 Already decided (user, 2026-10-10)

U4 prompted trials + look-back; Q6 AI art via `mcp-image-openrouter`, user approves each asset;
Q7 English first, Traditional Chinese later; Q8 page 2 scope only.

### 3.2 Hub proposals (need the user's approval)

| # | Proposal |
|---|---|
| H1 | Task id `scene_cause_effect`; display name **"Make It Happen"**; description "A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive. Cause and effect, with look-back." (S1 may rename it.) |
| H2 | Layout from Park Life page 2: a 7 x 5 grid of equal cells; the **scene** fills columns 1-5, rows 0-4; the **8 buttons** are columns 0 and 6, rows 1-4. Cells (0,0) and (6,0) stay empty (no Back button: the run bar already stops a test). |
| H3 | **One theme in v1: a park** with 8 objects and effects matching Park Life's kinds (section 4.4). Object identities are ours (S2 may change them). Button-to-object placement keeps Park Life's split: most buttons sit on the opposite side from their object (section 4.2). |
| H4 | **Prompt = spoken audio only** ("Make the balloons pop!"), played at trial start; the trial's response clock starts **at the end of the prompt audio**. No visual cue on the target button (a lit button would turn the test into Grid Click). S3 asks whether an optional visual cue setting is wanted. |
| H5 | **Any button can be selected** with the test's selection method. A completed dwell (or a switch press) on a **non-target button** is a `MISS_CLICK` (attempts + 1); the dwell resets and the trial goes on until a hit or the timeout, as in the existing tests. Looking at the scene or a gap selects nothing. |
| H6 | **Hit:** the target object's effect plays (section 4.4) together with its effect sound; no generic hit sound. **Miss:** the generic miss sound only; **no effect** for the wrong object (S4 asks whether the wrong object should animate instead). |
| H7 | **Timeout:** the trial ends unscored-as-hit (`timeout`); the target's effect then plays once as a model, flagged `modelled=true`, so the child still sees cause and effect. Look-back is still measured but reported separately from hit trials. (S5.) |
| H8 | **Trial count 16**: each of the 8 objects twice, shuffled, with the same object never twice in a row and left / right buttons balanced (8 each). Configurable `trials`, rounded to a multiple of 8. |
| H9 | **Timing:** `timeout_ms` 10000 (from the end of the prompt); the ITI after a trial = the effect duration (section 4.4) + `post_effect_ms` 1000, so the next prompt never starts during an effect. |
| H10 | **Look-back AOI** = the object's region in the scene (from the art's layer bounding box), padded by **1 deg** on each side (degrees via the existing px-to-deg geometry). The look-back window opens at effect start and closes at effect end + 500 ms. |
| H11 | **Look-back measures** per trial (definitions in section 4.6): `lookback` yes / no (at least 100 ms cumulative gaze inside the AOI in the window), `lookback_latency_ms` (effect start to the first valid sample inside the AOI), `lookback_dwell_ms` (cumulative time inside), `lookback_fraction` (inside time / window length). |
| H12 | **Button size:** set by the 7 x 5 grid on the canvas, not by the small / medium / large preset. The configuration page shows the resulting button size in degrees (read-only). Cell gap reuses `SPEC-grid-cell-gap.md` (standard / wide / extra wide). |
| H13 | **Prompt and effect audio are files** keyed by language: `configs/assets/scenes/park/audio/en/<object>.wav` and later `zh-TW/`. A task setting `language` (only `en` in v1). Prompts generated with `mcp-audio-openrouter` `generate_voice` or recorded (S6); every file approved by the user. |
| H14 | **Art layering:** one background image (scene without the 8 animated objects) plus one transparent PNG per object state and small extra sprites (bubbles, a pop burst, a fallen apple, a sparkle). All effects are drawn in code from these layers (move, rotate, scale, fade, colour shift), so no video and no per-frame drawings are needed. |

### 3.3 Questions for the user

| # | Question |
|---|---|
| S1 | Test name: "Make It Happen" (H1), or another name? |
| S2 | The 8 objects: keep Park Life's kinds (bike, seesaw, bubbles, swing, rainbow, cloud, balloons, apples) with our own drawings, or choose different objects? |
| S3 | Should there be an optional visual cue (the target button gently pulses) for children who cannot follow a spoken prompt? Default off. |
| S4 | After a miss: no effect (H6), or play the wrong object's effect (full cause and effect, but a reward for a wrong choice)? |
| S5 | After a timeout: play the target's effect as a model (H7), or nothing? |
| S6 | Prompt voice: generated speech (gpt-audio through `mcp-audio-openrouter`) or a recorded human voice? |
| S7 | Should gaze on the scene during the waiting phase (looking at the picture instead of the buttons) be reported as a measure? |
| S8 | Is the test part of the default test list for a new subject, or added only on request (Add test)? |

---

## 4. Design

### 4.1 Task model

- New `src/tasks/scene_cause_effect.py` `SceneCauseEffectTask(BaseTask)`.
- `build_targets()` returns 16 `TargetSpec`s (H8), each with `slot_index` = the button index 0-7 and
  the button centre as `x_norm` / `y_norm`. Button rectangles come from the 7 x 5 grid on the live
  canvas size (re-computed per frame, as `ClickGridTask` does).
- `scene_spec()` returns `{"mode": "scene", "theme": "park", "buttons": [...8 rects...],
  "scene_rect": ..., "effect": {...}|None}`; `effect` carries the object id, start time and
  duration while an effect plays, so the canvas can draw it.
- New phase use: after a hit or a timeout the task enters `RESULT` for the effect duration, then
  `ITI` for `post_effect_ms`. The prompt plays at the start of `WAIT_INPUT`; the response clock
  (`t_selectable_start_ns`) starts at the prompt end (`is_selectable` is false while the prompt plays).
- **Multi-button selection (H5)** needs a small base change, kept local to this task:
  - Dwell: one dwell machine per frame on **whichever button** the pointer is in (reset when the
    pointer changes button). Completion on the target = hit; on another button = `MISS_CLICK` with
    `selected_slot`.
  - Switch: the existing `_switch_press` path, plus `selected_slot` in the miss payload.
  - Both write `selected_object` into the event so the report can show what was chosen.

### 4.2 Layout and object placement (H2, H3)

Grid 7 x 5, equal cells. Buttons (column, row): left (0,1)-(0,4), right (6,1)-(6,4). Proposed
mapping, keeping Park Life's cross-screen split (README 9.2 / 9.4):

| Button | Object | Object region in the scene (fraction x / y of the scene, from Park Life; our art may differ) | Side of object vs button |
|---|---|---|---|
| L1 (0,1) | Balloons | 0.79-0.99 / 0.03-0.28 | opposite |
| L2 (0,2) | Rainbow | 0.45-0.77 / 0.12-0.36 | centre |
| L3 (0,3) | Seesaw | 0.51-0.74 / 0.33-0.52 | centre-right |
| L4 (0,4) | Apples | 0.05-0.45 / 0.08-0.72 | same |
| R1 (6,1) | Cloud | 0.43-0.83 / 0.00-0.14 | centre |
| R2 (6,2) | Bubbles | 0.47-0.59 / 0.65-0.95 | centre |
| R3 (6,3) | Bike | 0.36-0.47 / 0.42-0.63 | centre-left |
| R4 (6,4) | Swing | 0.00-0.29 / 0.51-0.97 | opposite |

The real AOIs (H10) come from our art's layer bounding boxes, stored in the scene manifest
(section 4.7), not from this table.

### 4.3 Trial flow

1. `WAIT_INPUT` starts: the prompt WAV plays; buttons are visible and idle; selection is blocked
   until the prompt ends (`PROMPT_START` / `PROMPT_END` events).
2. The child selects a button (dwell or switch). Wrong button: miss sound, `MISS_CLICK`, keep waiting.
3. Hit: `RESULT` phase; the effect plays with its sound (`EFFECT_START` / `EFFECT_END`,
   `modelled=false`). Timeout: the effect plays as a model (`modelled=true`, H7).
4. `ITI` for `post_effect_ms`; the scene is back to its idle picture; the next trial starts.

### 4.4 Effects (H14)

Durations follow the Park Life live measurements (README 9.3) and are per-object settings in the
scene manifest.

| Object | Effect, drawn from layers | Default duration |
|---|---|---|
| Bike | the bike sprite translates right along a path, leaves the scene, re-enters from the left, stops at its start | 4.0 s |
| Seesaw | the plank sprite (with both children) rotates about its pivot, about plus/minus 12 deg, 3 cycles | 2.0 s |
| Bubbles | the child sprite swaps to "blowing"; 6-10 bubble sprites rise and drift up-left, fading | 4.0 s |
| Swing | the seat sprite rotates about the top bar, damped, 2 cycles | 2.5 s |
| Rainbow | the rainbow bands cycle hue (or a sparkle sprite overlay) in place | 2.0 s |
| Cloud | the cloud translates left out of the scene, re-enters from the right, returns to start | 3.5 s |
| Balloons | each balloon sprite is replaced by a pop burst one after another, bare strings remain, then the balloons fade back in | 3.5 s |
| Apples | apple sprites fall with gravity onto the ground, then fade out while new apples fade in on the tree | 4.5 s |

Easing for all moves: ease-in-out. Animations run on the canvas tick (the existing `QTimer`), from
`scene["effect"]["t_start"]`, so they are paused with the test (pause stops the clock).

### 4.5 Rendering

- `TaskCanvas` gets a `"scene"` mode: draw the background pixmap scaled into `scene_rect`, then each
  object layer at its idle or animated transform, then the 8 buttons (rounded rectangles with the
  object's picture and its English label, design-system colours), then the dwell ring / cursor as
  today.
- Pixmaps are loaded once per run and cached scaled to the current canvas size.
- **Placeholder mode**: until the art is approved, each object is drawn as a labelled coloured shape
  so the engine, events and look-back can be built and tested without art.

### 4.6 Look-back measures (H10, H11)

Computed after the run from `all_gaze.csv` and the effect events (Qt-free module
`src/data/lookback.py`):

- Window W = [`EFFECT_START`, `EFFECT_END` + 500 ms].
- AOI = object bounding box (scene manifest, in scene fractions) mapped to canvas px with the
  canvas geometry recorded for the run, padded by 1 deg.
- `lookback_latency_ms` = time from `EFFECT_START` to the first valid gaze sample inside the AOI in
  W; empty if none.
- `lookback_dwell_ms` = sum of inter-sample intervals of valid samples inside the AOI in W.
- `lookback` = yes when `lookback_dwell_ms` is at least 100 ms.
- `lookback_fraction` = `lookback_dwell_ms` / length of W.
- Samples with invalid gaze are excluded; the trial reports `lookback_valid_fraction` (valid samples
  / all samples in W) so a trial with gaze loss is not read as "did not look".
- Mouse-pointer runs: look-back is computed from the recorded pointer and marked "pointer, not gaze".

### 4.7 Assets and the scene manifest

Folder `configs/assets/scenes/park/`:

- `background.png` (16:9 scene without the 8 objects), `objects/<object>_<state>.png` (transparent),
  `sprites/*.png` (bubble, pop burst, fallen apple, sparkle), `buttons/<object>.png` (button pictures).
- `audio/en/prompt_<object>.wav`, `audio/sfx/<object>.wav`.
- `scene.yaml`: per object the layer files, the pivot points, the bounding box in scene fractions
  (the AOI source), the effect parameters and duration, the button slot, the English label and
  prompt text.
- `ASSETS.md`: for every file the generating model, the prompt, the date and the user's approval
  (provenance for a clinical tool).

**Generation pipeline** (feasibility SPEC 7.2):

1. A style anchor: one full scene picture with `google/gemini-3-pro-image` (or Recraft V4 Styles), approved by the user.
2. The background and each object as a transparent PNG with a transparent-capable model (`openai/gpt-image-1-mini` or similar), with the anchor as a reference image.
3. Fallback: split the anchor into layers with `inclusionai/ming-image-0.1-design-layer`, or use a flat key colour plus local removal.
4. The user approves each file. If the user extends `mcp-image-openrouter` (transparent background, multi-image output), steps 2-3 run through the MCP; otherwise the fallback applies.

### 4.8 Configuration

`configs/tasks/scene_cause_effect.yaml`: `trials` 16, `timeout_ms` 10000, `post_effect_ms` 1000,
`scene` park, `language` en, `grid.gap` standard, `feedback.miss_sound` true, `visual_cue` false
(if S3 says yes). Settings registry entries `applies_to=("scene_cause_effect",)`; the per-test
pointer and selection settings apply as for the other tests.

### 4.9 Data and report

- Events (new kinds): `PROMPT_START`, `PROMPT_END`, `EFFECT_START`, `EFFECT_END` (with `object`,
  `modelled`); `MISS_CLICK` gains `selected_slot` / `selected_object`.
- Trial record adds: `prompt_object`, `button_side`, `selected_object` (on hit = prompt object),
  `rt_ms` from `PROMPT_END`, and the look-back fields.
- Report summary: hit rate, timeouts, misses (wrong button), median RT, look-back rate (hit trials;
  modelled trials separately), median look-back latency, results split by left / right button side.
- Per-trial table: trial, prompt object, side, result, selected object, attempts, RT, look-back,
  latency, dwell, valid fraction.

## 5. Implementation steps

| Step | Content | Needs |
|---|---|---|
| 1 | Wireframes: configuration card, run screen (scene + buttons), report page. **UI gate**: the user approves before code | - |
| 2 | Style anchor art + one object as a trial of the pipeline; the user approves the style | OpenRouter key |
| 3 | Engine: task class, multi-button selection, prompt / effect phases, events, trial fields; placeholder scene; pytest | - |
| 4 | Canvas `"scene"` mode with effects from layers (placeholders first) | step 3 |
| 5 | Look-back module + report rows; pytest on synthetic gaze | step 3 |
| 6 | Full art and audio; `ASSETS.md`; the user approves every file | step 2 |
| 7 | Live check with the user: Mouse + Dwell first (no device), then Gaze + Dwell and Gaze + Switch on the GP3 HD | steps 4-6; GP3 HD for the gaze part |

## 6. Acceptance criteria

- A1 The test appears in Add test with its name and description; a run of 16 trials completes with
  Mouse + Dwell and with Gaze + Dwell / Switch.
- A2 Each object is prompted exactly twice in 16 trials, never twice in a row, 8 left and 8 right.
- A3 Selection is blocked while the prompt plays; RT is measured from the prompt end.
- A4 A completed dwell or press on a wrong button records `MISS_CLICK` with the selected object and
  the trial continues; a hit plays the right effect; a timeout plays the modelled effect (if H7).
- A5 Every effect returns the scene to its idle picture before the next prompt.
- A6 Look-back values on a synthetic gaze file match hand-computed values (tests), including a gaze
  loss case.
- A7 The report shows the summary and the per-trial table (section 4.9), on screen and in the PDF.
- A8 Pause stops prompt timing and effects; resume continues them.
- A9 The canvas keeps its frame rate during effects (measure the tick interval during an effect).
- A10 Every shipped asset is listed in `ASSETS.md` with model, prompt and approval.

## 7. Log

- **2026-10-10** - Draft written from the feasibility SPEC (Part B, decisions U4, Q6-Q8), the Park
  Life analysis (`docs/grid3/park-life/README.md` section 9) and the code as of `9f160c4`.
  Grounded facts:
  - Dwell completes only on the target (`base_task.py` `update`), so H5 needs a multi-button dwell.
  - `canvas.py` has no image-layer mode, so a new `"scene"` mode is needed.
  - Sounds are `QSoundEffect` WAVs per theme.
  - Task configs live in `configs/tasks/*.yaml`.

  Hub proposals H1-H14 and questions S1-S8 wait for the user.
