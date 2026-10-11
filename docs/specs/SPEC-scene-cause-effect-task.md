---
name: SPEC-scene-cause-effect-task
title: A fifth test - an animated scene with 8 side buttons; a spoken prompt names the button; the selected object animates; gaze look-back to the effect is measured
status: approved 2026-10-10 (H1-H14 approved, S1-S8 answered, section 3.4); test name "Choice-making", task id choice_making
created: 2026-10-10
last_updated: 2026-10-11
next_step: steps 1-6 DONE (2026-10-11); next step 7 live check (Mouse + Dwell first, no device; then Gaze + Dwell / Switch on the GP3 HD)
related:
  - SPEC-grid3-calibration-parklife-feasibility.md (Part B feasibility, decisions U4, Q6-Q8)
  - docs/grid3/park-life/README.md (reference: layout, effects, timings, object regions - section 9)
  - SPEC-input-selection-and-follow.md (per-test pointer Gaze / Mouse and selection Dwell / Switch)
  - SPEC-target-size-and-motion-paths.md (sizes in degrees; 650 mm viewing distance)
  - SPEC-grid-cell-gap.md (cell gap as a dead zone)
  - SPEC-gazepoint-analysis-export-parity.md (all_gaze.csv, used for look-back)
---

# SPEC-scene-cause-effect-task - "Choice-making" scene test

**Status: approved 2026-10-10 (H1-H14 approved by the user; S1-S8 answered, section 3.4). The
test is called "Choice-making" (task id `choice_making`); the file keeps its original name.
Step 1 (wireframe) DONE `16dc79a` with the user's decisions W1-W7 (section 3.5). Branch
`feature/compass-task-flow`. Step 3 (engine) DONE 2026-10-11; animation decisions N1-N6 (section 3.6). Step 2 (style anchor + key-colour pipeline) DONE 2026-10-11. Steps 4 (canvas) and 5 (look-back + report) DONE 2026-10-11. Step 6 (art, sounds, scene.yaml) DONE 2026-10-11. Next: step 7 (live check).
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
| H1 | Task id **`choice_making`**; display name **"Choice-making"** (S1); description "A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive. Cause and effect, with look-back." (Originally proposed as `scene_cause_effect` / "Make It Happen"; changed by S1 and the user's approval.) |
| H2 | Layout from Park Life page 2: a 7 x 5 grid of equal cells; the **scene** fills columns 1-5, rows 0-4; the **8 buttons** are columns 0 and 6, rows 1-4. Cells (0,0) and (6,0) stay empty (no Back button: the run bar already stops a test). |
| H3 | **One theme in v1: a park** with 8 objects and effects matching Park Life's kinds (section 4.4). Object identities are ours (S2 may change them). Button-to-object placement keeps Park Life's split: most buttons sit on the opposite side from their object (section 4.2). |
| H4 | **Prompt = spoken audio only** ("Make the balloons pop!"), played at trial start; the trial's response clock starts **at the end of the prompt audio**. No visual cue on the target button by default (a lit button would turn the test into Grid Click). **Optional setting `visual_cue` (default off, S3):** the target button gently pulses from the prompt start until the selection or timeout; runs made with the cue are marked in the report. |
| H5 | **Any button can be selected** with the test's selection method. A completed dwell (or a switch press) on a **non-target button** is a `MISS_CLICK` (attempts + 1); the dwell resets and the trial goes on until a hit or the timeout, as in the existing tests. Looking at the scene or a gap selects nothing. |
| H6 | **Hit:** the target object's effect plays (section 4.4) together with its effect sound; no generic hit sound. **Miss:** the generic miss sound only; **no effect** for the wrong object (S4 asks whether the wrong object should animate instead). |
| H7 | **Timeout:** the trial ends unscored-as-hit (`timeout`); the target's effect then plays once as a model, flagged `modelled=true`, so the child still sees cause and effect. Look-back is still measured but reported separately from hit trials. (S5.) |
| H8 | **Trial count 16**: each of the 8 objects twice, shuffled, with the same object never twice in a row and left / right buttons balanced (8 each). Configurable `trials`, ~~rounded to a multiple of 8~~ any number (W5). |
| H9 | **Timing:** `timeout_ms` 10000 (from the end of the prompt); the ITI after a trial = the effect duration (section 4.4) + `post_effect_ms` 1000, so the next prompt never starts during an effect. |
| H10 | **Look-back AOI** = the object's region in the scene (from the art's layer bounding box), padded by **1 deg** on each side (degrees via the existing px-to-deg geometry). The look-back window opens at effect start and closes at effect end + 500 ms. |
| H11 | **Look-back measures** per trial (definitions in section 4.6): `lookback` yes / no (at least 100 ms cumulative gaze inside the AOI in the window), `lookback_latency_ms` (effect start to the first valid sample inside the AOI), `lookback_dwell_ms` (cumulative time inside), `lookback_fraction` (inside time / window length). **Added by S7:** during the waiting phase (prompt end to selection or timeout) the time with gaze on the scene, on the buttons and elsewhere (`wait_scene_ms`, `wait_buttons_ms`, `wait_other_ms`). |
| H12 | **Button size:** set by the 7 x 5 grid on the canvas, not by the small / medium / large preset. The configuration page shows the resulting button size in degrees (read-only). Cell gap reuses `SPEC-grid-cell-gap.md` (standard / wide / extra wide). |
| H13 | **Prompt and effect audio are files** keyed by language: `configs/assets/scenes/park/audio/en/<object>.wav` and later `zh-TW/`. A task setting `language` (only `en` in v1). Prompts are **generated speech** with `mcp-audio-openrouter` `generate_voice` (S6); every file approved by the user. |
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

### 3.4 Answers and approval (user, 2026-10-10)

| # | Answer |
|---|---|
| S1 | Name **"Choice-making"**; the user then approved the task id `choice_making` with H1-H14. |
| S2 | **Park Life kinds:** bike, seesaw, bubbles, swing, rainbow, cloud, balloons, apples, all drawn new. |
| S3 | **Yes, optional visual cue, default off** (setting `visual_cue`; report marks cued runs). |
| S4 | **No effect after a miss** (H6 as written). |
| S5 | **Model the effect after a timeout** (H7 as written). |
| S6 | **Generated speech** (gpt-audio through `mcp-audio-openrouter`), each file approved. |
| S7 | **Yes:** report time on scene / buttons / elsewhere during the waiting phase (added to H11, section 4.6). |
| S8 | **Add on request only:** available in Add test; the default test list for a new subject is unchanged. |
| H1-H14 | **Approved all** (as updated by S1-S8). |

### 3.5 Wireframe decisions (user, 2026-10-10, step 1)

Asked while reviewing `docs/wireframes/choice-making.md`; they amend the design below.

| # | Decision |
|---|---|
| W1 | **Scene is about 4:3** (columns 1-5 at full canvas height, about 1371 x 1032 px at 1920 x 1080). The background art is generated at 4:3 and fills that area (section 4.7). |
| W2 | **The run bar shows the prompted object** for the operator ("Prompt: Balloons") from the prompt start until the effect ends; empty between trials. |
| W3 | **Glow follows the gaze** in Switch mode (lights the looked-at button), greyed in Dwell mode, as in the other tests. |
| W4 | **Look-back is always Yes / No** in v1; the valid-sample fraction is shown beside it. Recorded alternative, **not built now**: show "low data" instead of No when under 50 % of the window's samples are valid, and leave those trials out of the look-back rate. |
| W5 | **Any number of trials** (not only multiples of 8). Balanced as far as the count allows: object counts differ by at most 1, left / right counts by at most 1, never the same object twice in a row. Default 16. Replaces H8's rounding to a multiple of 8. |
| W6 | **Scene Map** in the report in place of the Target Map: idle scene faint, each object's look-back AOI as a dashed box, right-choice and timeout counts on each button; Scanpath and Heat map overlays as today. |
| W7 | **Preview Test plays the prompts and the effects with sound** (3 trials, mouse, nothing recorded). |

### 3.6 Animation decisions (user, 2026-10-11)

From an animation feasibility study (Grid 3 Park Life has two kinds: the action effects and idle
eye blinks; README 9.1). Finding: every effect and the blinks can be drawn in Qt from layered
art (H14); Lottie (QML module missing, shape layers only, GPL), Spine / Rive / Live2D (no usable
Python runtime or hand rigging) and AI video (OpenRouter `/api/v1/videos`: opaque MP4, no exact
return to idle, not reproducible) are not needed. The user decided:

| # | Decision |
|---|---|
| N1 | **Layered Qt drawing only in v1** (H14). The effect engine is built from steps (transform, swap, particles, sequence); a "sequence" step can play a short pre-rendered PNG / WebP frame set on the canvas clock, so one effect can be upgraded later without an engine change. **No AI video in v1.** |
| N2 | **Look-back AOI moves with the object** for effects that leave the idle box (Bike, Cloud): the AOI is the object's box at each sample's time, from the same transform the canvas draws, padded 1 deg (section 4.6). |
| N3 | **Idle life between trials:** setting `idle_animation` = `off` / `blinks` / `blinks_bob`, **default `blinks`** (as Grid 3). Blinks: an eyes-closed patch swapped in for about 150 ms at random 2-6 s intervals per blinking character. The setting is written to the run metadata and marked in the report (like the visual cue). |
| N4 | **Rainbow** twinkle = a few pre-tinted copies of the rainbow art, cross-faded in code (keeps the art style). |
| N5 | **Frame rate (A9):** the idle scene is cached as one pixmap and the scene repaints are capped at about 60 Hz (the gaze loop keeps its own rate); measured on the target laptop in the live check. |
| N6 | **Extra art** (section 4.7): each balloon as its own layer plus a strings layer, the bush as a front layer, pivots for the swing and seesaw, optional bike wheels, the bubbles child's blowing pose, eyes-closed blink patches. A blink patch is accepted only if the edited image differs from the original inside the eye box alone; otherwise the eyelids are drawn in code. |

---

## 4. Design

### 4.1 Task model

- New `src/tasks/choice_making.py` `ChoiceMakingTask(BaseTask)`, registered as `choice_making`
  in `TASK_REGISTRY` and `TASK_INFO` ("Choice-making"); not added to the default test list (S8).
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

The run bar shows "Prompt: <object label>" from step 1 until the effect ends (W2).

### 4.4 Effects (H14)

Durations follow the Park Life live measurements (README 9.3) and are per-object settings in the
scene manifest.

| Object | Effect, drawn from layers | Default duration |
|---|---|---|
| Bike | the bike sprite translates right along a path, leaves the scene, re-enters from the left, stops at its start | 4.0 s |
| Seesaw | the plank sprite (with both children) rotates about its pivot, about plus/minus 12 deg, 3 cycles | 2.0 s |
| Bubbles | the child sprite swaps to "blowing"; 6-10 bubble sprites rise and drift up-left, fading | 4.0 s |
| Swing | the seat sprite rotates about the top bar, damped, 2 cycles | 2.5 s |
| Rainbow | cross-fade between pre-tinted copies of the rainbow art, in place (N4) | 2.0 s |
| Cloud | the cloud translates left out of the scene, re-enters from the right, returns to start | 3.5 s |
| Balloons | each balloon sprite is replaced by a pop burst one after another, bare strings remain, then the balloons fade back in | 3.5 s |
| Apples | apple sprites fall with gravity onto the ground, then fade out while new apples fade in on the tree | 4.5 s |

Easing for all moves: ease-in-out. Animations run on the canvas tick (the existing `QTimer`), from
`scene["effect"]["t_start"]`, so they are paused with the test (pause stops the clock).

Each effect is a list of steps (N1): `transform` (translate / rotate about a pivot / scale /
fade of one layer), `swap` (another state image), `particles` (bubbles, falling apples, pop
bursts) and `sequence` (a short frame set, unused in v1). Every effect ends on the identity
transform, so the scene is exactly the idle picture afterwards (A5).

**Idle life (N3):** with `idle_animation` `blinks` (default) each blinking character shows its
eyes-closed patch for about 150 ms at random 2-6 s intervals; `blinks_bob` adds a slow sine
bob of the balloons and the cloud; `off` is a still picture. Idle life runs only outside an
effect, on the canvas clock (pauses with the test), and is not logged per blink.

### 4.5 Rendering

- `TaskCanvas` gets a `"scene"` mode: draw the background pixmap scaled into `scene_rect`, then each
  object layer at its idle or animated transform, then the 8 buttons (rounded rectangles with the
  object's picture and its English label, design-system colours), then the dwell ring / cursor as
  today.
- Pixmaps are loaded once per run and cached scaled to the current canvas size.
- **Frame rate (N5):** the idle scene (background + idle layers) is cached as one pixmap and only
  the animated layers are drawn over it; scene repaints are capped at about 60 Hz while the gaze
  loop keeps its own rate (A9). A bench on this PC measured about 3.1 ms per frame for one effect.
- **Placeholder mode**: until the art is approved, each object is drawn as a labelled coloured shape
  so the engine, events and look-back can be built and tested without art.

### 4.6 Look-back measures (H10, H11)

Computed after the run from `all_gaze.csv` and the effect events (Qt-free module
`src/data/lookback.py`):

- Window W = [`EFFECT_START`, `EFFECT_END` + 500 ms].
- AOI = object bounding box (scene manifest, in scene fractions) mapped to canvas px with the
  canvas geometry recorded for the run, padded by 1 deg. For an effect that moves its object out
  of the idle box (Bike, Cloud) the AOI **moves with the object** (N2): at each sample's time
  the box is the object's box under the effect transform at that elapsed time, computed by the
  same Qt-free effect function the canvas uses.
- `lookback_latency_ms` = time from `EFFECT_START` to the first valid gaze sample inside the AOI in
  W; empty if none.
- `lookback_dwell_ms` = sum of inter-sample intervals of valid samples inside the AOI in W.
- `lookback` = yes when `lookback_dwell_ms` is at least 100 ms, otherwise no (always yes / no in
  v1, W4; the "low data under 50 % valid" alternative is recorded in W4, not built).
- `lookback_fraction` = `lookback_dwell_ms` / length of W.
- Samples with invalid gaze are excluded; the trial reports `lookback_valid_fraction` (valid samples
  / all samples in W) so a trial with gaze loss is not read as "did not look".
- Mouse-pointer runs: look-back is computed from the recorded pointer and marked "pointer, not gaze".
- Waiting-phase distribution (S7): over [`PROMPT_END`, selection or timeout], the cumulative time
  of valid samples inside `scene_rect` (`wait_scene_ms`), inside any button rectangle
  (`wait_buttons_ms`) and elsewhere on the canvas (`wait_other_ms`), plus the valid-sample fraction.

### 4.7 Assets and the scene manifest

Folder `configs/assets/scenes/park/`:

- `background.png` (4:3 scene without the 8 objects, W1), `objects/<object>_<state>.png` (transparent),
  `sprites/*.png` (bubble, pop burst, fallen apple, sparkle), `buttons/<object>.png` (button pictures).
- Extra layers (N6): each balloon as its own layer plus `balloons_strings`, the bush as a front
  layer (the bike rides behind it), pivots for the swing and the seesaw, optional bike wheels, the
  bubbles child's blowing pose, `rainbow_tint_<n>` copies (N4) and `blink/<character>.png`
  eyes-closed patches with their position (accepted only if the edit changed pixels inside the
  eye box alone).
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

`configs/tasks/choice_making.yaml`: `trials` 16, `timeout_ms` 10000, `post_effect_ms` 1000,
`scene` park, `language` en, `grid.gap` standard, `feedback.miss_sound` true, `visual_cue` false
(S3), `idle_animation` blinks (N3; off / blinks / blinks_bob). Settings registry entries `applies_to=("choice_making",)`; the per-test pointer and
selection settings apply as for the other tests. The test is offered in Add test only (S8).
`trials` accepts any number from 1, balanced as in W5. Preview Test plays the prompts and the
effects with sound (W7). Glow follows the gaze in Switch mode (W3). Layout of the page:
`docs/wireframes/choice-making.md` part A.

### 4.9 Data and report

- Events (new kinds): `PROMPT_START`, `PROMPT_END`, `EFFECT_START`, `EFFECT_END` (with `object`,
  `modelled`); `MISS_CLICK` gains `selected_slot` / `selected_object`.
- Trial record adds: `prompt_object`, `button_side`, `selected_object` (on hit = prompt object),
  `rt_ms` from `PROMPT_END`, and the look-back fields.
- Report summary: hit rate, timeouts, misses (wrong button), median RT, look-back rate (hit trials;
  modelled trials separately), median look-back latency, waiting-phase share on scene / buttons /
  elsewhere (S7), results split by left / right button side; a "visual cue on" marker when used (S3)
  and the idle-animation setting of the run (N3, also in `metadata.json`).
- Per-trial table: trial, prompt object, side, result, selected object, attempts, RT, look-back,
  latency, dwell, valid fraction, wait on scene / buttons / elsewhere.
- Scene Map in place of the Target Map (W6). Page layout: `docs/wireframes/choice-making.md` part C.

## 5. Implementation steps

| Step | Content | Needs |
|---|---|---|
| 1 | Wireframes: configuration card, run screen (scene + buttons), report page. **UI gate**: the user approves before code. **DONE 2026-10-10**: `docs/wireframes/choice-making.md`, approved with W1-W7 | - |
| 2 | Style anchor art (4:3, W1) + one object as a trial of the pipeline; the user approves the style. **DONE 2026-10-11**: `configs/assets/scenes/park/reference/style_anchor.png`, seesaw trial `objects/seesaw_idle.png`, key-colour pipeline with `tools/chroma_key.py` (section 7) | - |
| 3 | Engine: task class, multi-button selection, prompt / effect phases, events, trial fields; placeholder scene; pytest. **DONE 2026-10-11** (sections 8, 9) | - |
| 4 | Canvas `"scene"` mode with effects from layers (placeholders first), effect steps, idle life, cached scene + about 60 Hz repaint (N1, N3, N5). **DONE 2026-10-11** (sections 7, 8) | step 3 |
| 5 | Look-back module + report rows; pytest on synthetic gaze. **DONE 2026-10-11** (sections 7, 8; moving AOI wired by the hub) | step 3 |
| 6 | Full art and audio; `ASSETS.md`; the user approves every file. **DONE 2026-10-11** (section 7): layers cut from the anchor, `scene.yaml`, 8 Lyria effect cues | step 2 |
| 7 | Live check with the user: Mouse + Dwell first (no device), then Gaze + Dwell and Gaze + Switch on the GP3 HD | steps 4-6; GP3 HD for the gaze part |

## 6. Acceptance criteria

- A1 "Choice-making" appears in Add test (not in the default list) with its description; a run of 16 trials completes with
  Mouse + Dwell and with Gaze + Dwell / Switch.
- A2 Each object is prompted exactly twice in 16 trials, never twice in a row, 8 left and 8 right;
  for any other count, object counts and left / right counts each differ by at most 1 (W5).
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
- **2026-10-10 (later)** - The user answered S1-S8 and approved H1-H14 (section 3.4):
  - name "Choice-making", id `choice_making`;
  - Park Life object kinds;
  - optional visual cue, default off;
  - no effect after a miss;
  - modelled effect after a timeout;
  - generated speech;
  - waiting-phase gaze distribution reported;
  - Add test only.

  Updated H1, H4, H11, H13, sections 4.1, 4.6, 4.8, 4.9 and A1 to match. SPEC **approved**. Next: step 1 wireframes (UI gate).
- **2026-10-10 (step 1)** - Wireframe `docs/wireframes/choice-making.md` / `.html` drawn
  (configuration page, run screen in 3 states, summary and detailed report). Reviewing it, the user
  decided W1-W7 (section 3.5): 4:3 scene, prompt shown in the run bar, glow follows gaze, look-back
  always yes / no (50 % "low data" rule recorded as an alternative only), any trial count, Scene
  Map, Preview with sound. Updated H8, sections 4.3, 4.6, 4.7, 4.8, 4.9, A2 and the step 2 row
  (the OpenRouter key is already set: the image server shares the audio server's key; only a
  Claude Code restart is needed). The user then gave the final OK on the wireframe: **step 1 DONE**.
- **2026-10-11** - Step 3 engine implemented by `spec-implementer` in a worktree (section 8);
  the user answered its questions Q1-Q3 (section 9). The 8 English prompt WAVs were generated
  (gpt-audio, voice shimmer), approved by the user and placed in `configs/assets/scenes/park/audio/en/`
  with `ASSETS.md`. Image tool: the server's prompt enhancement rewrote both style-anchor tries
  (extra people, a sign); `SKIP_PROMPT_ENHANCEMENT=true` set in the root `.mcp.json`, step 2
  restarts after a Claude Code restart. Animation feasibility (Qt layers vs Lottie / Spine / AI
  video) done; the user decided N1-N6 (section 3.6): layered Qt only, moving AOI for Bike / Cloud,
  idle blinks on by default, tinted rainbow copies, cached scene + about 60 Hz repaint, extra art layers.
- **2026-10-11 (step 2)** - Style anchor and pipeline trial, by the hub with `mcp-image-openrouter`
  (`google/gemini-3.1-flash-image`). The third anchor try (`style_anchor.png`, 1200 x 896, about 4:3)
  follows the 8-object layout of section 4.2; the user approved the style. The image tool still cannot
  ask for a transparent background, so the pipeline is the key-colour fallback of 4.7 item 3: each object
  is drawn alone in the anchor's style (anchor as reference image) on flat `#00FF00` and keyed out
  locally by `tools/chroma_key.py` (PySide6 + numpy, cropped, despilled edges; no new dependency). Trial
  object: the seesaw, clean edges on light and dark; the user approved the pipeline (no extension of the
  image tool needed). Files and prompts in `configs/assets/scenes/park/ASSETS.md`. The seesaw trial is
  still one piece; step 6 makes the plank + children and the base as separate layers (N6). **Step 2
  DONE.** Steps 4 and 5 were delegated the same day to two implementers in separate worktrees; step 5
  takes an injectable `box_at(object_id, elapsed_ms)` and is wired to step 4's
  `choice_scene.object_box_at` by the hub after both merge (N2).
- **2026-10-11 (steps 4 and 5, hub review)** - Both implementers worked in parallel in separate worktrees
  (both again started at the old `c7e61cf` and fast-forwarded to `1173a03`). The user answered step 4's Q4
  (A: the picture stretches to fill `scene_rect`) and kept step 5's four readings S5-Q1 to S5-Q4 as built
  (section 9). The hub merged both on an integration branch; only the SPEC (both appended to sections 8 and
  9) and `tests/test_choice_making_setup.py` (auto-merged) overlapped. **N2 wiring (hub):**
  `report_choice.default_box_at(scene)` now returns `choice_scene.object_box_at` on the run's scene manifest
  (the build passes the run's `scene` setting); the placeholder manifest's boxes equal step 5's `IDLE_BOXES`
  exactly, so only Bike and Cloud change (their AOI moves during the effect); one test added. Cross-check:
  step 4 writes `idle_animation` to `metadata.json` `settings.structural`, which step 5's report reads, so
  the report's "not recorded" fallback is no longer reached for new runs. Shared-code changes are small and
  scene-mode only (run bar prompt line, a scene branch in the canvas, one argument in `src/app.py`). A 0-byte
  stray file `}` from the step 4 worktree was dropped. **pytest (hub, full, venv, integrated tree): 3754
  passed, 5 failed (3759 tests)**; the 5 are the known baseline (alpha 0.35 vs 0.22 in a worktree:
  `test_config_flow.py` 1, `test_task_config_page.py` 4); 3556 + 134 (step 4) + 68 (step 5) + 1 (hub) =
  3759. Acceptance: A5, A6, A8 covered by tests; A7 by tests (PDF fit checked with Segoe UI, not yet seen on
  a real screen); A9 offscreen only (tick median 16.0 ms, max 17.5 ms); A1 and the real A9 are step 7.
  Deviations accepted: "Wrong choices" column instead of "attempts" (wireframe), eye metrics on PDF page 2,
  medians for RT and latency, effect durations read from the manifest, 14 ms repaint cap. Left open:
  `docs/CLINICAL_DATA_REFERENCE.md` (the 13 new columns of steps 3 and 5), the page label "Glow on the
  looked-at button" (`settings_registry.py` at 499 lines), step 6 art and sounds, step 7 live check.
  Committed by the user's OK as two commits (step 4; step 5 + wiring + SPEC). **Steps 4 and 5 DONE.**
- **2026-10-11 (step 6, hub)** - Full art, scene manifest and effect sounds; every file approved by the user
  in three art batches and one sound batch. Provenance (models, prompts, processing, hashes) in
  `configs/assets/scenes/park/ASSETS.md`.
  - **Route (changed from 4.7's per-object redraw, user-approved):** the approved anchor was edited into an
    empty background (`background.png`, 2400 x 1792), and every object layer is cut straight out of the
    anchor by its difference from that background (`tools/layer_extract.py`), so style and position are the
    anchor's exactly; `tools/build_park_scene.py` derives all layers deterministically. Recomposited, the
    layers match the anchor (median 2/255; 0.004 % of pixels over 40). Only one picture was redrawn: the
    bubble boy's blowing pose (97 % silhouette overlap with the idle pose).
  - **Splits for the effects:** seesaw plank + children / base (plank rebuilt behind the base; pivot = bolt),
    swing ropes + seat + girl / frame (the leg behind the seat end filled), 5 balloons popping back to front
    (purple, blue, orange, yellow, red, so a pop always shows sky) + strings / post, 7 apples + the tree with
    their holes filled from the leaves, 2 rainbow tints (N4), a ground-shadow layer (no object ghosts; found
    by a motion check), and an eyes-closed patch per child made from the art (N6: only pixels near the eyes
    change; a test checks the patch border is untouched).
  - **Decisions:** the bike stands in front of the bush in the approved anchor, so the bush stays in the
    background and there is no bush front layer (user; N6's "bike rides behind the bush" superseded).
    Effect sounds are Lyria musical cues per object, not literal sound effects (user; the audio server has
    no sound-effect model), trimmed to each effect's length by `tools/make_scene_sfx.py` (Qt
    `QAudioDecoder`, no new dependency).
  - **`scene.yaml`** gives every object its layers, pivots, boxes (the art's bounding boxes, the look-back
    AOI source), blinks and effect steps; durations stay the 4.4 defaults. It loads with no warning, every
    picture exists, every effect ends at rest (A5), and only Bike and Cloud move their box (N2).
  - **Tests:** the real assets made 23 placeholder-based tests read the real scene. A suite-wide fixture in
    `tests/conftest.py` now pins every test to the placeholder scene unless it is marked `real_scene`
    (marker registered in `pyproject.toml`); the two module-scoped report fixtures pin themselves. New
    `tests/test_choice_park_scene.py` (26 tests, `real_scene`): file loads cleanly, all pictures present,
    every effect ends at rest, only Bike / Cloud boxes move and return, blink patches change only near the
    eyes, and the canvas draws the real scene and is pixel-exact idle again after each effect.
  - **Not checked here:** the scene on a real screen and the real frame rate with the real art (A9), the
    sounds through the app (both step 7).

## 8. Impl log

- **2026-10-10 - claude-sonnet-5-5 - step 3 (engine), implemented; uncommitted.** Sections 4.1, 4.2,
  4.3, 4.8 and, from 4.9, the events and the trial-record fields; W5 for the order. Nothing of
  steps 4-7 touched (no canvas drawing, no look-back, no report, no art, no audio, nothing under
  `configs/assets/`).
  - **Setup note.** The worktree I was given was at `c7e61cf` (77 commits behind
    `feature/compass-task-flow`, no SPEC file in it), not at `108b029` as briefed. I fast-forwarded the
    worktree's own throwaway branch to `108b029` (`git merge --ff-only`, clean tree, no commit of mine)
    and worked from there. Nothing else in git was touched.
  - **New files.**
    - `src/tasks/choice_layout.py`: the 7 x 5 board maths (button cells, drawn rect, hit area, scene rect,
      `button_at`), the 8 objects with their 4.4 default effect durations, `trial_order()` (W5),
      `DEFAULT_PROMPT_MS` (a placeholder, see section 9 Q1).
    - `src/tasks/choice_making.py`: `ChoiceMakingTask(BaseTask)`.
    - `src/ui/choice_settings.py`: the Choice-making registry entries and the Scene card.
    - `configs/tasks/choice_making.yaml`: the 4.8 defaults (16 trials, 10 s, 1 s pause, park, en, cue off,
      standard gap, miss sound on, hit sound off, theme forest).
    - `tests/test_choice_layout.py`, `tests/test_choice_making.py`, `tests/test_choice_making_setup.py`.
  - **Changed files.** `src/engine/task_runner.py` (registered), `src/engine/task_info.py` (name and
    description, H1), `src/data/schema.py` (4 trial columns), `src/ui/settings_registry.py` (adds the
    new entries; exactly 499 lines), `src/ui/task_instructions.py` (provisional Start-page wording, see
    D12), and four existing tests (see "Existing tests edited").
  - **How it works.**
    - `BaseTask` is untouched. `ChoiceMakingTask` has its own `update()` (the base one hit-tests the
      target only) and reuses the base helpers (pre-roll, pause frame, press debounce, `_switch_press`,
      `_finish_trial`, `skip_trial`, `pause`).
    - Dwell: one `DwellSelector` on whichever button the pointer is in, reset when the pointer moves to
      another button; it only runs after the prompt has ended. Switch: the base `_switch_press`
      (SWITCH_PRESS, `clicks`, `click_errors`) plus `selected_slot` and `selected_object` on the miss.
    - Flow: `WAIT_INPUT` (prompt plays, selection blocked, then the response window) then, on a hit or a
      timeout, `RESULT` for the effect duration (`EFFECT_START` at the selection, `EFFECT_END` at its
      end), then `ITI` for `post_effect_ms`, then the next trial; `DONE` only after the last effect and
      its pause. A skip has no effect, only the pause.
    - Events: `PROMPT_START` (trial, object, slot, side, duration_ms), `PROMPT_END`, `EFFECT_START`
      (trial, object, modelled, duration_ms), `EFFECT_END` (trial, object, modelled); `MISS_CLICK` gains
      `selected_slot` (-1 off every button) and `selected_object` (null off every button).
    - Trial fields (`trials.csv`, appended at the end of the header): `prompt_object`, `button_side`
      (`left` / `right`), `selected_object` (the prompt object on a hit, blank on a timeout or skip),
      `rt_ms` (ms from the END of the prompt to the hit, blank without one). `slot_index` is the button
      index 0-7; `t_selectable_start_ns` is exactly the prompt end, so
      `reaction_time_from_selectable_ms` equals `rt_ms`.
    - `scene_spec()` returns the 4.1 keys (`mode` scene, `theme`, `buttons`, `scene_rect`, `effect`);
      rectangles are `(x, y, w, h)` in canvas px, `effect` has `object`, `t_start`, `duration_ms`,
      `modelled` and `elapsed_ms` (as of the last frame, so a pause freezes it). The canvas ignores mode
      "scene" for now and, with `layout_slots` set to the 8 button centres, falls back to its dim
      outlines: it does not crash (no canvas change was made or run).
  - **Decisions I took (small, mechanical; the hub may overrule any of them).**
    - D1. `scene_spec()` carries three extra keys the decided behaviour needs: `prompt_object` (id from
      the prompt start to the effect end, for the run bar line of W2), `cue_slot` (the button to pulse
      while the visual cue is on, S3) and `hover_slot` (the button under the pointer, for the glow of W3
      and the dwell ring). The frame's `target_xy_norm` is None on purpose so the prompted button is not
      marked (H4); `FrameResult.target` and `slot_index` are set as usual.
    - D2. Cues: a wrong button plays the generic miss cue (`feedback.on_miss`), a hit plays no generic hit
      cue (H6), and a timeout plays no miss cue either (the modelled effect plays instead; 4.x does not say).
      `_trial_cue` is a no-op in this task.
    - D3. A switch press while gaze is on the scene, a gap or nowhere is a `MISS_CLICK` with
      `selected_slot` -1, like a press off the target in the other tests (it is still a counted press and a
      Click error). A dwell off every button never completes, so it selects nothing (H5).
    - D4. Pause during the prompt follows the base rule for a trial in flight: the trial is dropped
      (`TRIAL_INTERRUPTED`) and re-presented from its start on resume, so the prompt plays again; its old
      clock is gone. Pause during an effect keeps its elapsed time and resume continues it (A8).
    - D5. `PROMPT_END` and `EFFECT_END` carry their ideal times (start plus length), not the time of the
      frame that noticed them, so the log and the tests are exact to the ms.
    - D6. `entries` and `time_to_first_fixation_ms` count from the trial start (the prompt start), as for
      the other tasks, so a look at the right button during the prompt is kept; RT is from the prompt end.
    - D7. `TargetSpec.radius_px` is 0.0 (no configured radius; H12). `effective_radius_px` is the largest
      circle that fits a button, and that is what `trials.csv` records as `target_radius_px`.
    - D8. The cell gap works exactly as for Grid Click: `grid.gap` goes through the existing
      `apply_grid_gap`, a wide gap is a dead zone, and `GAP_CAPPED` and `gap_capped_px` are reported
      the same way.
    - D9. Registry: `post_effect_ms` is a LIVE setting `task.post_effect_ms` ("Pause after the
      animation (s)", 0-5 s); `task.timeout_ms` reads "Time to choose (s)" for this task through the
      existing `_TASK_VARIANTS`; "Inter-trial interval" and "Play hit sound" are excluded for it; "Cell
      gap" applies to it and sits in a new Scene card (Scene, Prompt language, Visual cue, Cell gap) that
      replaces Grid Click's Grid Layout card on this task's page. Which controls the page shows is
      therefore already data-driven; I wrote no widget code and did not run the page.
    - D10. The 4 trial columns are appended to the header for every task (blank for the other four), as
      the earlier column additions were; readers take columns by name, so older folders still load.
    - D11. `DEFAULT_PROMPT_MS = 2000` for every object until Q1 is answered.
    - D12. `task_instructions.py` needed an entry or the Start page would raise a KeyError for a test added
      with Add test (and ten parametrized tests over `TASK_INFO` would fail). I wrote a PROVISIONAL
      four-step text plus the NOTE line, and a switch step; it is child-facing wording and needs the
      clinician review the rest of that file already needs (section 9 Q3).
    - D13. The task's `title` and `instruction` in the YAML are English only (Q7: English first).
  - **Existing tests edited (not behaviour changes; each was pinned to the old task count, header tail or
    `grid.gap` scope).** `tests/test_add_test_dialog.py` (four tasks to five),
    `tests/test_recording_additions.py`, `tests/test_follow_task.py`, `tests/test_run_engine.py` and
    `tests/test_run_modes_app.py` (the trials.csv header tail now ends with the 4 new columns),
    `tests/test_seconds_display.py` (the registry's time keys plus `task.post_effect_ms`),
    `tests/test_grid_cell_gap.py` (`grid.gap` applies to `click_grid` and `choice_making`).
  - **Tests added.** `tests/test_choice_layout.py` (123), `tests/test_choice_making.py` (31),
    `tests/test_choice_making_setup.py` (12), `tests/test_choice_making_canvas.py` (1, offscreen Qt: the
    canvas paints every phase of a trial in mode "scene" without crashing): 167 new tests, covering A2 (16 trials: each object
    twice, 8 left and 8 right, never twice in a row, for 40 seeds; any count 1-70 balanced for 12 seeds),
    A3 (selection blocked during the prompt for dwell and switch, RT and timeout counted from the prompt
    end), A4 (wrong button by dwell and by switch, scene and gap select nothing, hit plays the right
    effect, timeout plays the modelled one, no effect for a wrong object), A5 (RESULT, EFFECT_END, the
    pause, then the next PROMPT_START; the scene idle at every later prompt in a 4-trial run), A8 (pause
    in the prompt and in an effect), skip, scene_spec, cue and hover, live canvas size, GAP_CAPPED,
    registration, config, registry and page layout, trials.csv columns. A mutation check (prompt gate
    disabled) failed 10 of them.
  - **pytest (full, venv, from the worktree):** `3452 passed, 5 failed` (3457 tests). Baseline before my
    changes in this worktree: `3274 passed, 5 failed` (3279 tests). The 5 are the same before and after:
    `test_a_new_test_opens_*` in `test_config_flow.py` (1) and `test_task_config_page.py` (4), alpha 0.35
    against the local 0.22 (this worktree has the committed `configs/default.yaml`, not the skip-worktree
    local one); `test_config_merges_task_over_default` passes here. The +178 passes are my 167 plus 11
    cases of existing tests parametrized over `TASK_REGISTRY` / `TASK_INFO` that now include
    `choice_making` (instructions, Start page, input choice, headless replay). `ruff` is clean on every
    file I touched.
  - **Deviations from the SPEC:** none beyond D1-D13 above (the extra `scene_spec` keys, the registry and
    page-card wiring, the provisional Start-page text and the 4 columns for all tasks were not spelled out).
  - **Left undone (by scope):** canvas drawing of mode "scene" and effects (step 4); the run bar line
    (W2), the glow and ring on the hovered button, the visual-cue pulse (step 4 reads `prompt_object`,
    `hover_slot`, `cue_slot`); sounds for the prompt and effects (Q2); look-back module and report
    (step 5); scene manifest, art and audio, `ASSETS.md` (step 6); live check (step 7);
    `docs/CLINICAL_DATA_REFERENCE.md` (the 4 new columns); the page label "Glow on the looked-at button"
    and "(how a button is selected)" of the wireframe (the registry labels are the other tests').

- **2026-10-11 - claude-sonnet-5-5 - follow-up: the user's answers to Q1-Q3 (section 9), implemented;
  uncommitted, same worktree.**
  - **Q1 = B, the prompt length is measured.**
    - `src/tasks/choice_layout.py`: `wav_duration_ms(path)` (Python `wave`, Qt-free; `None` for a missing,
      empty, non-PCM, truncated or unreadable file), `scene_audio_dir()`, `prompt_wav_path(scene, language,
      object_id, root)` = `<assets>/scenes/<scene>/audio/<language>/prompt_<object>.wav`, `effect_wav_path()`
      = `.../audio/sfx/<object>.wav`, and `ASSETS_ROOT` = `configs/assets` (read only).
    - `src/tasks/choice_making.py`: `ChoiceMakingTask.prompt_length(obj)` returns `(ms, "wav" or "default")`,
      measured once per object and run from the configured `scene` and `language`, else
      `DEFAULT_PROMPT_MS` (2000); `prompt_ms()` returns the ms. `PROMPT_START` carries the measured
      `duration_ms` and a new `duration_source` field (`wav` / `default`, my addition, so a run made with the
      fallback can be told apart). The WAVs do not exist yet, so the fallback is what runs today. Class
      attribute `assets_root` (default `ASSETS_ROOT`) lets a test point at a temp folder. Nothing under
      `configs/assets/` is created or changed.
  - **Q2 = A, the audio hooks.**
    - `src/engine/feedback.py`: three optional no-op methods on `FeedbackBus` (not abstract):
      `on_prompt(object_id)`, `on_effect(object_id, modelled)` and `on_stop_audio()` (my name for the stop
      hook). `NullFeedback` inherits them and records nothing, so its `events` and every other task are
      unchanged (a test runs a headless Static Click replay with a recording bus and sees no audio call).
    - The task calls them at `PROMPT_START` (`on_prompt`), at `EFFECT_START` (`on_effect`, `modelled` true
      after a timeout) and on every `pause()` and on a skipped trial (`on_stop_audio`; the skip is my
      addition: it would otherwise leave the prompt playing through the pause). A wrong button plays no
      effect sound. A bus without the hooks (a test double) is silent, via `getattr`.
    - `src/ui/scene_audio.py` (new, Qt): `SceneAudio` keeps one `QSoundEffect` per file that exists
      (prompts of the configured language, effect sounds from `sfx/`), loaded when the run is built, volume
      0.6 like the other cues; a missing file is silent. API checked in the Qt docs (qt-docs, Qt 6.12):
      `setSource(QUrl)`, `setVolume(float)`, `play()`, `stop()`, `isPlaying()`.
      `SceneAudio.from_task_config()` returns `None` unless the task config names a `scene`.
    - `src/app.py`: `GuiFeedback` takes an optional `scene_audio` (the constructor call of the other
      tasks is unchanged) and forwards the three hooks to it; the app builds it from the task config. No
      other app code changed.
    - Limits to know: a sound cannot be held and resumed, so a pause cuts it. An interrupted prompt plays
      again from its start with its trial (D4); an effect's animation continues after the pause without its
      sound. A new prompt first stops anything still playing.
  - **Q3.** The Start-page text stays as a placeholder; the comment in `src/ui/task_instructions.py` now
    says it is for clinician review together with the other four tests' texts.
  - **D2 confirmed:** no miss sound on a timeout, only the modelled effect with its own sound (unchanged).
  - **D11 and D12 of the first entry are superseded** by the above (the prompt length is no longer a
    constant; the Start-page text is a confirmed placeholder).
  - **Tests.** 27 new: `tests/test_choice_layout.py` +7 (paths, default root, `wav_duration_ms` measured, and
    missing / empty / garbage / folder / truncated), new `tests/test_choice_making_audio.py` (16: a prompt
    as long as its generated WAV, a length per object, fallback for a missing, unreadable or empty file,
    scene and language resolve the path, measured once, the hooks at prompt start / hit / timeout / wrong
    button / pause in a prompt / pause in an effect / skip, a bus without hooks, no other task calls
    them), `tests/test_choice_making_canvas.py` +4 (offscreen Qt: `SceneAudio` loads only existing files and
    is silent for the rest, with none at all, only a task with a scene gets audio, `GuiFeedback` forwards).
    The existing choice tests now point `assets_root` at a folder that never exists, so audio added to the
    repository later cannot change them. Files stay under 500 lines; `settings_registry.py` unchanged
    at 499; `ruff` clean on every file I touched or added (a pre-existing import-order warning in
    `src/app.py` is not mine).
  - **pytest (full, venv, from the worktree):** `3479 passed, 5 failed` (3484 tests; 194 new in all). The same
    5 baseline failures as before (alpha 0.35 against the local 0.22: `test_config_flow.py` 1,
    `test_task_config_page.py` 4); no other failure.
  - **Deviations:** none beyond the two small additions named above (`duration_source` on `PROMPT_START`,
    the stop on a skip). **Left undone:** the real prompt and effect audio files and the manifest
    (step 6); the canvas, run bar and look-back (steps 4 and 5).

- **2026-10-11 - claude-sonnet-5-5 - step 4 (canvas "scene" mode, effects, idle life, run bar line,
  `idle_animation`), implemented with PLACEHOLDER art; uncommitted.** Sections 4.4, 4.5, 4.7, 4.8 and
  N1, N3, N5 (and W2, W3); acceptance A5, A8, A9 and the canvas side of A1. Not touched: look-back
  (`src/data/lookback.py`), the report modules, `trials.csv` / the schema, anything under
  `configs/assets/`, the audio files, `settings_registry.py`, `configs/default.yaml`,
  `configs/local_state.json`.
  - **Setup note.** The worktree I was given was at `c7e61cf`; I fast-forwarded its own throwaway branch
    to `1173a03` (`git merge --ff-only`, clean tree) before anything else. No commit, no stage.
  - **New files.**
    - `src/tasks/choice_scene.py` (Qt-free, the public module): the model (`Layer`, `BlinkSpot`, `Track`,
      the steps `Transform` / `Swap` / `Sequence` / `Particles`, `Effect`, `ObjectSpec`, `SceneManifest`,
      `LayerState`, `ParticleState`), the evaluation (`ease`, `layer_state`, `object_layer_states`,
      `particles_at`, `transform_box`) and `load_manifest(scene, root)`. **`object_box_at(manifest,
      object_id, elapsed_ms, *, aspect=None) -> (x0, y0, x1, y1)`** is the function step 5 is wired to:
      scene fractions, pure and deterministic, the idle box outside the effect (before the start, at or
      after the end, NaN) and for an object that does not `follow` a layer, the box moved by the transform
      of the followed layer (Bike and Cloud only, N2) inside it; NOT clamped to the scene (while the
      Bike is off the picture the box lies outside 0..1); `aspect` (scene width / height) defaults to
      the manifest's 4:3 and only matters for rotation.
    - `src/tasks/choice_scene_defaults.py`: the built-in placeholder scene (the 4.2 boxes, the 4.4
      durations from `choice_layout.OBJECTS`, guessed pivots, 3 balloons + strings, 2 rainbow tint copies,
      3 apples, the swing seat and seesaw plank with pivots, a front bush, 5 blink spots, bob for the
      balloons and the cloud).
    - `src/tasks/choice_scene_io.py`: the `scene.yaml` reader; **the file format is documented in its
      module docstring** (step 6 writes `configs/assets/scenes/park/scene.yaml` to it). An object the
      file does not list, or a part of an object it leaves out (layers, effect, blink, bob, duration ...),
      keeps its built-in placeholder, so art can arrive object by object.
    - `src/tasks/choice_idle.py` (Qt-free): `IdleLife`, the blink / bob clock of N3.
    - `src/ui/scene_canvas.py` (`SceneView`, the renderer `TaskCanvas` delegates to), `src/ui/scene_buttons.py`
      (the eight buttons, glow, rings, cue pulse, selected highlight), `src/ui/scene_placeholders.py`
      (the labelled coloured shapes, faces and eyelids drawn in code).
    - Tests: `tests/test_choice_scene.py` (69), `tests/test_choice_idle.py` (8),
      `tests/test_choice_making_scene.py` (11), `tests/test_choice_scene_canvas.py` (38, offscreen Qt),
      `tests/test_choice_scene_app.py` (4, through `AssessmentApp`).
  - **Changed files.** `src/ui/canvas.py` (493 lines: a `SceneView`, `mode == "scene"` in `paintEvent`, the
    repaint cap and the idle clock reset in `set_frame` / `set_paused`), `src/tasks/choice_making.py` (the
    manifest, `idle_animation`, `prompt_label`, see D14), `src/ui/run_bar.py` + `src/engine/tracking_status.py`
    (the prompt fact), `src/app.py` (one argument to `run_status`), `src/ui/choice_settings.py` +
    `configs/tasks/choice_making.yaml` (`idle_animation`), and the existing tests `test_choice_making_setup.py`
    (the Scene card now has five controls; +3 tests), `test_run_bar.py` (+1), `test_choice_making_canvas.py`
    (docstring).
  - **How it works.**
    - *Effects (N1, 4.4).* A step names a layer and a window `[t0, t1]` of the 0..1 effect timeline.
      `transform` has tracks `dx` / `dy` (scene fractions of width / height), `rot` (degrees clockwise about
      the layer's pivot), `scale`, `alpha`: keys `(progress, value)` with an ease (`linear` / `in` /
      `out` / `in_out`) and, for swing and seesaw, a damped oscillation `(amplitude, cycles, damping)`.
      Of the transforms on one layer the latest to have started wins and holds its end value, so the
      Bike and the Cloud can leave the scene and come back from the other side; a step sets only the
      properties it names. `swap` shows another state image (the bubbles child "blowing"); `particles`
      are bubbles (rise, drift up and left, fade) and pop bursts, deterministic and all gone by the end of
      their window; `sequence` (a frame set) is evaluated but unused in v1. At `elapsed >= duration` every
      layer is at rest and there are no particles; the last step's end values are the rest values, so
      there is no jump (A5; tested for all eight objects and, pixel by pixel on the canvas, that the
      idle picture is back exactly once `scene["effect"]` is `None`).
    - *Renderer (4.5, N5).* Layers that do not animate are drawn once into pixmaps, split at the
      animating layers so the z order holds (the bike rides behind the bush); each frame blits them and
      draws only the animating layers (and the particles, and the idle blinks) over them, clipped to the
      scene. The cache is keyed by the animating layers and the scene size, keeps 4 keys, and is warmed
      when a prompt starts, so the first frame of an effect renders nothing. The scene sits on whole device
      pixels (a fractional origin made the live layers' antialiased edges differ from the cached picture's).
      `set_frame` still runs at the gaze loop's rate; it asks Qt for a repaint at most every 14 ms (about
      60 Hz, `scene_canvas.MIN_PAINT_S`); a loop at or below 60 Hz is never thinned.
    - *Idle life (N3).* `IdleLife`: per character a blink of 150 ms at random 2-6 s intervals, per bobbing
      object a slow sine. The renderer feeds it the time between canvas ticks (capped at 0.1 s), so it
      stops with a pause (no ticks) and is frozen during an effect; the eyelids are drawn in code over the
      placeholder faces (or the `image` patch of a blink spot, N6, when a manifest names one).
    - *Pictures.* A layer, the background, a button picture or a blink patch that names a file in the scene
      folder is drawn from it (scaled once, cached); a missing file falls back to the placeholder shape.
    - *Buttons.* Rounded rectangles in the design-system colours (white card, grey border, ink label, the
      object's coloured swatch until the art exists). While selection is open the looked-at button gets
      the glow (Switch only, `canvas.show_glow`, so greyed with Dwell, W3), the instant ring and the dwell
      ring (as in the other tests); nothing is lit while the prompt blocks selection. The cue button (S3)
      pulses its accent border about once a second; after a hit the chosen button keeps a highlight and a
      check mark for 1.2 s (B3 "short highlight"; none after a timeout).
    - *Run bar (W2).* `ChoiceMakingTask.prompt_label` (empty outside a prompt) goes to `run_status(prompt=...)`;
      the bar shows `Trial 4 of 16, Prompt: Balloons, ...` (own label `runBarPrompt`, right after the trial) in
      every run mode from the prompt start to the effect end; a pause drops it with the other live facts.
    - *Setting (N3, 4.8).* `idle_animation` (`off` / `blinks` / `blinks_bob`, default `blinks`) is in
      `configs/tasks/choice_making.yaml` and a `StructuralSetting` in `choice_settings.py` (a three-way
      radio group, Scene card, after the visual cue). Registered, so it is stored with the test, in
      `metadata.json` `settings.structural.idle_animation` (tested through `AssessmentApp` and the written
      file) and available to the report like `visual_cue`. An unknown value is `blinks` everywhere.
  - **Decisions I took (small; the hub may overrule any of them).**
    - D14. The engine reads the manifest, so one source says how long an effect lasts:
      `ChoiceMakingTask.manifest` (loaded once at the first trial, read only, a file that could not be
      used is logged once in the session log) and `effect_ms()` = the manifest's duration (the 4.4 default
      with no file). `scene_spec()` gained `idle_animation` and the task `prompt_label`. No selection
      logic changed.
    - D15. Scene fractions are fractions of `scene_rect` (4.5 literally); see section 9, Q4.
    - D16. Only Bike and Cloud have `follows` set (N2); the Seesaw box stays put although the plank turns
      about 12 deg (its corners stay inside the box plus the 1 deg pad). `follows` is a manifest field, so a
      later object only needs it in `scene.yaml`.
    - D17. A partial `scene.yaml` merges over the placeholders (above); `decor` is taken from the file only
      (the placeholder bush is not carried into a real scene).
    - D18. Repaint cap 14 ms (not 16.7 ms) so a 60 Hz loop with 16 ms timer ticks is not thinned to 30 Hz.
    - D19. The instant ring is drawn on any looked-at button (any button can be chosen), around its
      centre; the dwell ring is the circle of the other tests around the button, not an outline of its
      rectangle. Live check will tell whether either wants another look.
    - D20. The run bar line is also shown in a Preview (Preview plays the prompts, W7) and a Practice.
  - **A9 (indicative: offscreen Qt, this PC, 1920 x 1032 canvas, placeholder shapes).** Full `set_frame` +
    `grab()` per frame: idle picture median 7.2 ms; during the eight effects medians 8.6-10.7 ms, slowest
    frame 13.7 ms (`test_a9_the_paint_time_stays_small_during_every_effect`, bound 40 ms median and
    3 x idle + 5 ms). With the app's loop in miniature (a real 16 ms `QTimer` driving `set_frame` and a
    repaint during the bike effect for 1.2 s) the tick interval was median 16.0 ms, p95 17.1 ms, max 17.5 ms
    (`test_a9_the_tick_interval_holds_...`, bound median 40 ms, max 300 ms). The real measure on the target
    laptop (and with the real art, which is larger than these shapes) is the live check, step 7.
  - **pytest (full, venv, from the worktree):** `5 failed, 3685 passed in 751.17s` (3690 tests; 134 of them
    new: 130 in the five new files, +3 in `test_choice_making_setup.py`, +1 in `test_run_bar.py`). The 5
    failures are the known baseline ones, unchanged (alpha 0.35 against the local 0.22:
    `test_config_flow.py::test_a_new_test_opens_at_standard_with_the_task_defaults` and
    `test_task_config_page.py::test_a_new_test_opens_with_standard_and_the_defaults[...]` for the four
    other tasks); `test_config_merges_task_over_default` passes in this worktree; no other failure.
    `ruff` is clean on every file I touched or added (the pre-existing import-order warning in `src/app.py`
    is not mine). Files stay under 500 lines (`canvas.py` 493, `choice_scene.py` 472).
  - **Deviations from the SPEC:** none beyond D14-D20 above (the engine reading the manifest, the extra
    scene key and property, the cap constant).
  - **Left undone (by scope):** the real art, `scene.yaml` and sound files (steps 2 and 6; `configs/assets/`
    untouched); look-back and the report rows, including the report's marking of `idle_animation` (step 5);
    the page label "Glow on the looked-at button" for this task (it is in `settings_registry.py`, which is at
    499 lines); `docs/CLINICAL_DATA_REFERENCE.md`; the live check and the real A9 measurement (step 7).

- **2026-10-11 - claude-sonnet-5-5 - step 5 (look-back module and report), implemented; uncommitted.**
  Sections 4.6 and 4.9 (the look-back and waiting-phase fields, the summary, the per-trial table, the
  Scene Map), W4, W6, S7, N2 (the box provider), the idle-animation marker of N3; acceptance A6 and the
  data and screen / PDF sides of A7. Nothing of the canvas, the run bar, `src/tasks/choice_scene.py`,
  `src/ui/choice_settings.py`, `configs/tasks/choice_making.yaml`, art, audio, `configs/assets/` or the
  engine's selection logic was touched, and `src/app.py` was not edited.
  - **Setup note.** The worktree was at `c7e61cf`, not at `1173a03` as briefed. I fast-forwarded its own
    throwaway branch (`git merge --ff-only 1173a03`, clean tree, no commit of mine) and worked from there.
  - **New files.**
    - `src/data/lookback.py` (Qt-free): `Sample` / `SampleSeries`, `samples_from_raw` / `samples_from_frames`,
      `pad_norm` (1 deg as canvas fractions), `scene_box_to_canvas`, `aoi_at`, `Regions` / `board_regions` (the
      scene and the eight drawn buttons, with the run's cell gap), `Pauses`, `measure_lookback`,
      `measure_wait`, `LookbackParams` (1 deg, 500 ms, 100 ms, 100 ms), the `IDLE_BOXES` fallback constant
      (the 4.2 table) and `static_box_provider`.
    - `src/data/report_choice.py` (Qt-free): the `choice` block of `report.json` (per-trial figures,
      summary rows, by-side rows, pooled waiting shares, the eight buttons for the Scene Map),
      `choose_series` (which samples), `pause_spans`, `run_extras`, `default_box_at`, and
      `fill_trials_lookback` (the `trials.csv` columns).
    - `src/ui/report_format_choice.py` (Qt-free text of the summary, the two tables under it, the per-trial
      cells, the footnote, the PDF definitions) and `src/ui/target_map_choice.py` (the Scene Map drawing).
    - Tests: `tests/test_lookback.py` (20), `tests/test_choice_report.py` (29), `tests/test_choice_report_ui.py`
      (19), and the helper `tests/choice_report_fixtures.py` (a scripted 100 Hz gaze, the rows and events the
      task writes, a Gaze, Mouse, stream-only and no-gaze folder).
  - **Changed files.** `src/data/schema.py` (nine columns, `LOOKBACK_COLUMNS`), `src/data/report_cache.py`
    (`REPORT_VERSION` 5, the `choice` block, the columns written when the report is), `src/data/report_config.py`
    (Choice-making's rows), `src/data/report_geometry.py` (`canvas_cell_deg`), `src/ui/report_format.py`
    (`Cell.tip`, the task sentence), `src/ui/report_layout.py` (the `choice` layout and its helpers),
    `src/ui/report_views.py`, `src/ui/report_pdf.py`, `src/ui/map_legend.py`, `src/ui/target_map_paint.py`
    (498 lines; `_paint_slots` became `_paint_layout`); and tests pinned to the old header or version
    (`test_choice_making_setup`, `test_follow_task`, `test_recording_additions`, `test_run_engine`,
    `test_run_modes_app`: the header tail now ends with the nine columns; `test_follow_report`,
    `test_report_scanpath`: version 5;
    `test_report_cache`: the new top-level key). `ruff` is clean on every file I touched or added; every
    file is under 500 lines.
  - **How it works.**
    - **Window and AOI (4.6, H10, H11, N2).** W = [`EFFECT_START`, `EFFECT_END` + 500 ms] from the events. The
      AOI is the object's box (scene fractions, from `box_at(object_id, elapsed_ms)`) mapped to the canvas
      (the scene is columns 1-5 of the 7 x 5 board, full height) and grown by 1 deg of visual angle on every
      side (`distance * tan(1 deg)` over the canvas's size in mm, from the run's recorded geometry). `lookback`
      = at least 100 ms of valid samples inside; `latency` = effect start to the first valid sample inside;
      `dwell` = the summed intervals; `fraction` = dwell over the window; `valid_fraction` = valid samples over
      all samples of the window. Invalid samples are excluded from the first four. A hand-computed gaze-loss
      case is in the tests (`test_look_back_with_a_gaze_loss_in_the_window`: 251 samples, 20 lost, latency 300
      ms, dwell 1000 ms, fraction 0.4, valid 231 / 251).
    - **Waiting phase (S7).** Over [prompt end, choice or timeout] the valid time on the scene rectangle,
      inside any drawn button (the run's cell gap applied, as the canvas draws it) and elsewhere, plus the
      valid-sample share; pooled over the scored trials for the summary.
    - **Sources.** A Mouse run: `pointer_stream.csv`, marked `pointer_not_gaze` (header words "Pointer back
      (not gaze)"). A Gaze run: the device-rate `all_gaze.csv` on the host clock (`raw_clock_offset_ns`),
      else `gaze_stream.csv`. No stream: every look-back figure is None and the page says so.
    - **Modelled trials** (timeouts) are measured the same way but counted in their own row of the
      summary and marked `modelled` per trial (H7).
    - **Report.** Summary of Results (four rows: right on the first choice, all right choices, not chosen in
      time (modelled), all trials; columns % (N), Reaction Time, Wrong choices, Looked back, latency), "By
      button side", "While choosing", the Scene Map in place of the Target Map (idle scene faint as labelled
      placeholder shapes, each object's look-back area dashed, each button with the number of right choices
      and of not-in-time trials; Scanpath and Heat map as for any test; the selected trial shows the
      prompted button coloured by its outcome, the area, and the gaze during the animation thick and dark),
      the 16-column Trial-by-Trial table and the Test Configuration rows (button size in degrees with the
      gap, time to choose, pause after the animation, scene, visual cue, idle animation). On screen
      and in the PDF through the same `report_layout` functions.
    - **`trials.csv`.** Nine columns are appended (`lookback`, `lookback_latency_ms`, `lookback_dwell_ms`,
      `lookback_fraction`, `lookback_valid_fraction`, `wait_scene_ms`, `wait_buttons_ms`, `wait_other_ms`,
      `wait_valid_fraction`; blank for every other task). The task cannot know them, so
      `write_report_safely` (which `finish_run` calls for a saved run) rewrites the file with them filled,
      atomically; a folder opened for QA with `load_or_build_report` only gets them in the report.
  - **The injection point (N2).** `report_choice.default_box_at()` is the one place the boxes come from. It
    returns `static_box_provider(IDLE_BOXES)`, the 4.2 table as a constant marked `# INTEGRATION: wire to
    choice_scene.object_box_at`. To wire the canvas step in: return
    `lambda object_id, ms: object_box_at(manifest, object_id, ms)` (scene fractions, ms since the effect began
    on the canvas clock; I clamp it to the effect's length, so after the effect it is the object at rest).
    A synthetic moving box is tested in `test_lookback.py` (a moving AOI finds a look a static one misses) and the
    provider is shown to be the report's source in `test_choice_report.py`.
  - **Decisions I took (small; the hub may overrule any of them).**
    - D1. The four readings listed in section 9 (S5-Q1 to S5-Q4: the 100 ms cap on a sample's interval,
      "elsewhere" includes off-canvas gaze, first choice = `attempts == 1` and wrong choices = selections on
      a button, no sample = a dash).
    - D2. The per-trial table follows the wireframe (C2): **Wrong choices** (the count; the wrong buttons in
      the cell's tooltip) instead of 4.9's "attempts" (which stays in the data), and the four eye columns the
      Follow table has. The glyphs of the wireframe's Looked back column are not used: plain Yes / No.
    - D3. The summary's Reaction Time and latency are **medians** (as the brief says; the other tests' tables
      are means); the footnote says so. Reaction Time of a modelled trial = prompt end to the end of the time
      to choose.
    - D4. A pause: the paused spans (`PAUSED` / `RESUMED`) are out of every window, the effect clock for `box_at`
      does not run during one, and the window length for `fraction` is the active time. The task shifts the
      effect by the pause but logs `EFFECT_START` once, so the events alone cannot say this.
    - D5. Without the monitor's physical size or the viewing distance the 1 deg padding cannot be computed
      (a degree is never guessed): every look-back figure is None. The waiting phase needs only the canvas.
    - D6. `REPORT_VERSION` 4 to 5 (a new algorithm, so a cached v4 report of a Choice-making run, if any, is
      rebuilt).
    - D7. PDF: Choice-making's configuration and its two extra tables fill page 1, so its **Eye Metrics follow
      the Scene Map on page 2** (page 1 then holds everything above the map; 3 pages). The 16-column trial
      table fits with measured widths from 7.0 pt (Gaze) or 6.5 pt (Mouse, longer header words) with the real
      Segoe UI; the test registers the font and checks it.
    - D8. `idle_animation` is read from `metadata.json` (`idle_animation`), else the settings snapshot; absent
      it reads "not recorded". It is a Test Configuration row (with the visual cue); the line above the summary
      is only for the visual cue (S3) and a Mouse run.
    - D9. A skipped trial shows no figure (dashes) and counts no wrong choices (HD5).
  - **pytest (full, venv, from the worktree):** `3619 passed, 5 failed` (3624 tests; 68 of them new:
    `test_lookback.py` 20, `test_choice_report.py` 29, `test_choice_report_ui.py` 19). The 5 are the known
    baseline: `test_a_new_test_opens_*` in `test_config_flow.py` (1) and `test_task_config_page.py` (4), alpha
    0.35 against the local 0.22; no other failure. (The counts are from the progress dots of
    `pytest -q`: this checkout's run prints no final summary line.) A first full run had one more failure,
    `test_run_modes_app.py::test_an_ended_run_writes_how_it_ended`, which indexed the header from the end
    and is fixed.
  - **Deviations from the SPEC:** none beyond D2 (wireframe's "Wrong choices" for 4.9's "attempts") and D7 (Eye
    Metrics after the map in this test's PDF).
  - **Left undone (by scope):** wiring `object_box_at` into `default_box_at` (the hub, after step 4 merges);
    `docs/CLINICAL_DATA_REFERENCE.md` (the nine new columns, as step 3 left its four); step 4 writing
    `idle_animation` into `metadata.json`; no live check, no real-gaze run, and no look at the report on a real
    screen (offscreen Qt has no fonts, so only colours and the PDF's fit with the real Segoe UI were checked).

## 9. Open questions

Written by the step 3 implementer (2026-10-10, claude-sonnet-5-5). The engine builds and passes its
tests without these answered; each only changes one clearly marked place. **All three were answered by
the user on 2026-10-11 and are implemented** (answers below; section 8, follow-up entry).

- **Q1 - How does the engine learn how long a spoken prompt lasts?** The response clock, the timeout and
  `PROMPT_END` all start at the prompt's end (H4, H9), and the prompt WAVs do not exist yet. Today
  `ChoiceMakingTask.prompt_ms(obj)` returns the placeholder `DEFAULT_PROMPT_MS` (2000 ms) for every
  object. Options:
  - **A.** A per-object `prompt_ms` in `scene.yaml` (4.7), written when the WAVs are made (step 6) and read by a
    Qt-free manifest loader. Simple to test; the number can drift from the file if the audio is regenerated.
  - **B.** The engine measures each `prompt_<object>.wav` itself at build time (Python `wave`, no Qt), falling
    back to the placeholder when a file is missing. One source of truth (the file), nothing to keep in sync.
  - **C.** The app tells the task when playback ends (a Qt audio callback). Ties timing to the audio device,
    cannot be replayed headlessly, and a pause cannot hold it.
  - **Recommendation: B**, with the measured length written into `PROMPT_START` (already `duration_ms`).
    The effect durations stay in the manifest (4.4) either way.
  - **Answer (user, 2026-10-11): B.** The engine measures each `audio/en/prompt_<object>.wav` itself with
    Python `wave` (Qt-free, read only) and falls back to `DEFAULT_PROMPT_MS` (2000) when the file is missing or
    unreadable; the measured length goes into `PROMPT_START` `duration_ms`. The path is resolved from the
    configured scene and language. DONE, see section 8 (follow-up, 2026-10-11).
- **Q2 - How does the app play the prompt and effect sounds?** The feedback bus has only `target_shown`,
  `hit`, `miss` and `progress`, so the task has no way to ask for a sound. I added nothing. Options:
  - **A.** Two optional hooks with no-op defaults on `FeedbackBus` (`on_prompt(object_id)` and
    `on_effect(object_id, modelled)`), called by the task at `PROMPT_START` and `EFFECT_START`; `GuiFeedback`
    plays a cached `QSoundEffect` per file. Same pattern as the hit and miss cues; headless runs and
    `NullFeedback` are unaffected.
  - **B.** The app watches `scene_spec()` every tick and starts the sound when `prompt_object` or `effect`
    changes. No bus change, but the logic sits in `app.py` and the start can lag by one tick.
  - **C.** A separate audio object passed to the task next to `feedback`.
  - **Recommendation: A.** Whatever is chosen must also stop a playing sound on pause (A8), which
    `QSoundEffect.stop()` allows but `FeedbackBus` has no hook for yet.
  - **Answer (user, 2026-10-11): A.** Optional no-op hooks on `FeedbackBus` (`on_prompt(object_id)`,
    `on_effect(object_id, modelled)` and a stop hook for a pause), called by the task at `PROMPT_START`,
    `EFFECT_START` and on a pause; `GuiFeedback` plays a cached `QSoundEffect` per file that exists and does
    nothing when it is missing; `NullFeedback` and the headless runs are unaffected. DONE, see section 8
    (follow-up, 2026-10-11).
- **Q3 - Start-page wording for Choice-making.** I wrote a provisional text so the page works (D12):
  1. "[The small dot on the screen shows where you are looking.] A picture will appear on the screen, with
     buttons on each side."
  2. "You will hear which button to choose, for example "Make the balloons pop!""
  3. "Look at that button and keep looking at it for about 0.8 seconds. [A ring will fill up around it.]"
  4. "When it is selected, the picture will come alive. Continue until no more prompts are spoken."
  - NOTE: "If the button is not selected within 10 seconds, the picture will show what that button does
    and the next prompt will follow."
  - Switch version of step 3: "Look at that button, then press the switch. [The button glows while you are
    looking at it.]"
  - Question: approve it, or give the wording you want read to the child. **Recommendation:** keep it as a
    placeholder until the clinician review of all five tests' texts.
  - **Answer (user, 2026-10-11):** keep the provisional text as a placeholder, to be reviewed by a clinician
    together with the other four tests' texts. The code comment in `task_instructions.py` now says so.
- **Confirmed (user, 2026-10-11), D2 of section 8:** on a timeout there is no miss sound, only the modelled
  effect with its own sound.
- **2026-10-11 - Q4 (step 4 implementer, claude-sonnet-5-5), non-blocking: is the scene picture stretched to
  `scene_rect`, and are all scene fractions relative to it?** W1 says the scene is about 4:3 and the art is
  generated at 4:3 and "fills that area"; 4.5 says the background is "scaled into `scene_rect`". The step 3
  `scene_rect` is columns 1-5 at the full canvas height, which is 4:3 only on a 1920 x 1032 canvas
  (1920 x 1080 less the 48 px run bar: 1371 x 1032 = 1.329). Another canvas gives another aspect (1366 x 768:
  975 x 720 = 1.355, 2 % wider), so art drawn into `scene_rect` is stretched by a few percent there. I
  followed 4.5 literally and did not decide anything beyond it: the picture fills `scene_rect`, and every scene
  fraction (layer boxes, the look-back AOI source, particles) is a fraction of `scene_rect`, which is also what
  `object_box_at` returns (so the AOI maps to canvas px by `scene_rect` alone, as 4.6 says). Options:
  - **A (current).** Keep it: no distortion at the standard 1920 x 1080 display (the Setup Display card checks
    for it), a few percent stretch on others.
  - **B.** Letterbox: a 4:3 picture rectangle centred in `scene_rect`, all fractions relative to it; step 5 then
    maps the AOI through that rectangle and `choice_scene` gets a `picture_rect()` helper. No stretch anywhere,
    but empty bars at the sides on a wider canvas.
  - **Recommendation: A**, revisit after the live check on the laptop only if the stretch shows. Needed before
    step 5's AOI mapping is called final, because both read "scene fraction". The one function that would
    change is `SceneView._scene_rect` (and `object_box_at`'s `aspect` argument already takes the real aspect).
  - **Answer (user, 2026-10-11): A**, stretch to fill `scene_rect`; all scene fractions are fractions of
    `scene_rect`. Revisit only if the laptop live check shows the stretch. Nothing to change.
- **2026-10-11 - step 5 (look-back and report), claude-sonnet-5-5: four readings I took by default, none
  blocks anything; each is one clearly marked place, the hub may overrule.** The SPEC does not spell them
  out; the figures below depend on them, so they are listed here and not only in the Impl log.
  - **S5-Q1. A sample's interval.** 4.6 says "sum of inter-sample intervals of valid samples inside the
    AOI". Taken as: the time to the next sample of the stream, **at most 100 ms** (`LookbackParams.
    max_interval_ms`), cut at the window end and at the start of a pause. Without the cap a gap in the
    records (a tracker restart, a pause) would count as gaze. With no gap it changes nothing (device
    rate 6.7 ms, loop rate 16.7 ms).
  - **S5-Q2. "Elsewhere" in the waiting phase (S7).** Taken as everything valid that is neither on the
    scene nor on a drawn button: the empty corner cells, the gaps between buttons **and gaze off the
    canvas**, so the three shares add up to 100 % of the valid time (the wireframe's 38 / 52 / 10).
    The alternative, "elsewhere on the canvas" only, would leave off-canvas gaze in no row.
  - **S5-Q3. "Right on the first choice" and "Wrong choices".** First choice = a hit with
    `attempts == 1` (no earlier selection or press of any kind, as the existing Error-free row).
    Wrong choices = the `MISS_CLICK`s with `selected_slot >= 0` (a completed selection on another
    button, as the wireframe defines it); a switch press that landed on no button (`-1`) is an attempt, not
    a wrong choice. So a trial can have attempts 2 and wrong choices 0.
  - **S5-Q4. No sample in the window.** A trial whose look-back window holds no gaze or pointer sample at
    all gets `lookback` = None (a dash), not "No": W4 keeps the report to Yes / No for trials with data,
    and 4D.9 forbids a 0 where nothing was recorded. A window with samples that are all invalid is "No"
    with `lookback_valid_fraction` 0.
  - **Answer (user, 2026-10-11): all four kept as built** (100 ms cap; "elsewhere" includes off-canvas gaze;
    wrong choices = selections on another button, first choice = `attempts == 1`; no samples = a dash).
    Nothing to change.
