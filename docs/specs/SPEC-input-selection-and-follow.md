---
name: SPEC-input-selection-and-follow
title: Pointer (Gaze / Mouse) and Selection (Dwell / Switch) per test; Follow the Target without a click
status: approved 2026-10-07 (I1-I12, H1-H10); step 1 wireframes APPROVED 2026-10-07 (W1-W2); step 2 (engine) DONE 2026-10-08; step 3 (Follow the Target) DONE 2026-10-08
created: 2026-10-07
last_updated: 2026-10-08
next_step: step 4 (UI: config page Input card display, report tables / summary / map / legend + PDF for Switch and Follow, report_config labels) with spec-implementer in the worktree `.claude/worktrees/agent-abd63029551e9614d` (fast-forwarded to the step-3 commit), then step 5 (review + live check A10 with the user and the switch)
related:
  - SPEC-compass-task-flow.md (parent redesign; configuration page 4B, run 4C, report 4D; P9c V1-V5 still open there and done FIRST)
  - SPEC-follow-moving-selection.md (the selection window this SPEC removes)
  - SPEC-target-size-and-motion-paths.md (follow paths, speed in px/s; unchanged)
  - SPEC-gazepoint-analysis-export-parity.md (all_gaze.csv, used for pursuit gain and catch-up saccades)
  - docs/compass/sources/compass-user-guide.md (Aim test "Selection Method", Switch test "Hold Time", "Clicks" column)
---

# SPEC-input-selection-and-follow — choose how the child points and selects; Follow without a click

**Status: approved 2026-10-07 (I1-I12 user decisions, H1-H10 hub decisions approved by the user). Branch `feature/compass-task-flow` (U17 of the parent SPEC). Lands before the
v2.0.0 merge, after the parent SPEC's P9c pass.**

## 1. Origin

Doctor's feedback, given to the user on 2026-10-07 after the P9 real-device run:

1. **Input method.** Children differ in how long they can hold their gaze on a target. Some
   cannot dwell long enough for a dwell selection, but they can look at the target and press a
   button. The doctor asks for a choice of input: Mouse, Gaze, and Click. "Click" comes from a
   mouse or from a separate switch, a round big-button device the doctor already uses. The user
   noted that Compass offers a per-test Input Device and Selection Method (Click / Dwell).
2. **Follow & Click.** What matters clinically is that the child follows the moving target, not
   the click. The user chose to remove the selection and keep only the following.

The user's switch was tested on this PC: it connects over USB and sends **only a left mouse
click**. It has no pointer movement and no keys.

## 2. Current code (as of `826edcc`)

- `input.mode` already exists (`configs/default.yaml`, read in `src/app.py:289`) with values
  `eye` | `gaze_switch` | `switch`. It is global, not per test, and is **not shown** on the
  configuration page (parent SPEC 4B, row "`input.mode` — Not exposed; `eye` only").
- `SwitchInput` (`src/inputs/switch_input.py`) is a rising-edge latch. Only **Space / Enter on the
  canvas** feed it (`AssessmentApp._install_key_handler`, `src/app.py:641`). A mouse left click on
  the canvas is not wired.
- In every mode the pointer comes from `self.eye.poll()` (gaze). Mode `switch` is labelled
  "Switch (mouse pointer)" in `report_config.py:26`, but no mouse source is attached in a recorded
  run. Only Preview uses `MouseGazeSource` (`src/inputs/mouse_gaze.py`, `config_flow.py:244`), and
  it replaces the *client*, so nothing is recorded.
- `BaseTask.update` (`src/tasks/base_task.py:444`): with `input_mode == "eye"` the dwell machine
  selects. Otherwise `pointer.clicked` is the selection, and an off-target click is already a
  `MISS_CLICK` event that counts as an attempt.
- `FollowMovingTask` (`src/tasks/follow_moving.py`) has a random **selection window** per trial
  (`motion.select_window_ms`, 2500 ms; `is_selectable`). A trial ends on a hit or on
  `timeout_ms` (12000).
- Configuration page cards (`settings_registry.py:422` `_CARDS`): "Selection (Dwell)" holds
  threshold, refractory and jitter tolerance. "Timing" holds `motion.select_window_ms` for follow.
- Saccades: I-VT at 50 deg/s on `all_gaze.csv` (`src/data/saccades.py`); `window_saccades` already
  cuts them per trial.

## 3. Decisions

### 3.1 User decisions (2026-10-07, final)

| Id | Decision |
|---|---|
| I1 | Two separate per-test settings, as in Compass: **Pointer** (what moves the pointer: Gaze or Mouse) and **Selection** (how a target is selected: Dwell or Switch). |
| I2 | Pointer = **Gaze or Mouse, chosen per test**. A Mouse test is a recorded test, e.g. a motor-access baseline. |
| I3 | Selection = **Dwell / Switch** only. No "Either", no Double Click. |
| I4 | The switch hardware sends a **left mouse click** and nothing else. No gamepad library. |
| I5 | Switch rules: (a) a press counts on **button down**; (b) gaze (pointer) on target at the press = **hit**, off target = **Click error**, and the trial continues; (c) if the gaze is invalid at the press (a blink), use the **last valid pointer within 150 ms**; (d) presses **between trials are ignored**; (e) the target **glows while the pointer is on it**, because there is no dwell ring. No Hold Time setting. |
| I6 | Click clash (the switch and the operator's mouse are the same "left click"): **a left press on the canvas = the switch; a press on the run bar = an operator action.** With Pointer = Gaze, the OS cursor is parked on the canvas and hidden at run start. |
| I7 | Pointer = Mouse does **not** need the tracker. If the tracker is connected (and calibrated), gaze is recorded alongside and the report shows the eye sections. Otherwise those show "not recorded". |
| I8 | Pointer applies to **all four tasks, including Follow** (Mouse Follow = a motor tracking test). Selection applies to the three selection tasks. |
| I9 | Follow has **no selection**: no click, no dwell, no selection window. The child only follows. |
| I10 | Follow feedback: the **target glows while the pointer is on it**, and a short sound plays at a trial's end when the target was followed for most of the trial (H6). |
| I11 | Follow metrics, per trial and in the summary: **Time on target %**, **Mean distance to target (deg)**, **Pursuit gain**, **Catch-up saccades (per s)**. |
| I12 | Follow is renamed **"Follow the Target"**. Each trial lasts a fixed **10 s** (setting 3-30 s). The task id stays `follow_moving`. This SPEC is separate from the compass SPEC but on the same branch. |

### 3.2 Research notes (parallel search, 2026-10-07)

- Gaze pointing plus a switch for the selection is an established AAC access method next to dwell.
  Tobii Dynavox names exactly these two ("Dwell" and "Switch: look at the item, then press a
  switch"). A published CP case used Compass with eye gaze + a jelly-bean knee switch
  (PMC9136588).
- Gaze + button click is faster than dwell, with higher throughput. Dwell has the fewest wrong
  selections but is slowest (Mutasim et al., ETRA '21). With dwell, the eyes must both point and
  select (the "Midas touch" problem). With a switch, the child can look freely, which is the
  doctor's reason.
- Compass Aim test: Selection Method = Click / Double Click / Dwell (1.0 s default). The
  **Clicks** column counts every click in the trial, and Click Errors counts clicks off the target.
  The Switch test ignores presses during the pause between trials. Its optional Hold Time was not
  taken (I5).
- Smooth pursuit is measured by **gain** (eye velocity ÷ target velocity), **catch-up saccades**
  and position error. Children's gains are lower than adults': about 0.63 at age 5-8, 0.85 at
  15-17; 0.84 horizontal / 0.68 vertical at 0.25 Hz. Vertical gain is lower and more variable.
  Saccades are removed before computing gain. So the report shows gain with a caution, not a
  pass/fail threshold (H8).

### 3.2a Wireframe-gate decisions (user, 2026-10-07)

- **W1 Read-aloud text** (Start page, `task_instructions.py`; still flagged for clinician review):
  - Selection = Switch, the "keep looking for about {dwell}{ring}" step becomes "Look at the lit
    square, then press the button." plus "The square glows while you are looking at it." when
    `feedback.target_glow` is on (per task: square / shape / circle as in today's text).
  - Pointer = Mouse: the "small dot shows where you are looking" step becomes "Move the mouse to
    point at the screen.", and "look at" becomes "point at" in the following steps.
  - Follow the Target: "A circle will appear and start to move across the screen." / "Follow the
    moving circle with your eyes and keep looking at it while it moves." / "The circle glows while
    you are looking at it." (only with glow on) / "After about {duration} a new circle will appear.
    Continue until no more circles appear." No NOTE line.
- **W2 Follow summary layout:** a 2-column Metric / Value table (Followed n of N, Time on target
  mean + range, Mean distance, Time to find target, Smooth-pursuit gain median + caption,
  Catch-up saccades per s, Valid pointer %), in place of the 4-row selection table. The Follow
  per-trial table = these metrics per trial, then the usual eye columns (Fixations, Saccades,
  Pupil, Pupil change). See `docs/wireframes/report-summary.md` / `report-detailed.md`.

### 3.3 Hub decisions (approved by the user 2026-10-07)

- **H1 Setting keys.** Per test: `input.pointer` = `gaze` | `mouse` (default `gaze`), and
  `input.selection` = `dwell` | `switch` (default `dwell`; absent for follow). They are stored in
  the test's configuration like any structural setting. The old global `input.mode` is derived
  and written to `metadata.input_mode` so `report_config.py` keeps working: gaze+dwell = `eye`,
  gaze+switch = `gaze_switch`, mouse+switch = `switch`, and **new** mouse+dwell = `mouse_dwell`.
  Follow writes `eye` or `mouse_follow`. New metadata fields: `input_pointer`, `input_selection`.
- **H2 What counts as the switch.** A left mouse press on the canvas (I4), **and also Space /
  Enter** (kept from today, for keyboard-type switch interfaces). With Pointer = Mouse, the mouse's
  own left button is the selection too, as in Compass's Click.
- **H3 Glow setting.** A new structural bool `feedback.target_glow` (default on) in the Feedback
  card. It is shown for Switch selection and for Follow. With Dwell, the existing progress ring is
  shown instead and the glow is hidden (the parent SPEC's greyed-in-place rule: greyed, not hidden,
  when Selection = Dwell).
- **H4 Mouse pointer architecture.** The pointer source and the recording client are separated.
  A Mouse run uses `MouseGazeSource` as the pointer. When the Setup tab's tracker is connected, it
  still records into the run (`all_gaze.csv`, `gaze_stream.csv`, pupil). Without a tracker, those
  files are absent and the report's eye sections say "not recorded". Pointer samples of a Mouse run
  go to a new `pointer_stream.csv` (`t_ns,x,y,valid`), so the gaze-path map can draw the mouse
  path.
- **H5 Run gate.** Pointer = Gaze: unchanged (connected and calibrated). Pointer = Mouse: Start and
  Practice are allowed with no tracker. The Start page shows one line: "Mouse test — the tracker is
  not connected, so no eye data will be recorded" (or "…eye data will be recorded alongside").
- **H6 Follow "followed".** A trial counts as **followed** when Time on target ≥ 50 %. This drives
  the end-of-trial sound (I10) and the report's Followed count. 50 % is a fixed constant in this
  version, named in the report's footnote.
- **H7 Follow pointer metrics come from the live pointer.** Time on target % and mean distance are
  counted **in the task, per frame**, from the same pointer and hit test that draw the glow:
  smoothed gaze, or the mouse. On target = the existing hitbox (target radius + jitter tolerance).
  Time on target % = on-target valid frame time ÷ valid frame time. Invalid frames (blinks, lost
  eye) are excluded and reported separately as Valid %. Distance is measured from the target centre
  in px and converted to degrees in the report with the session geometry.
- **H8 Follow eye metrics come from `all_gaze.csv`** (gaze only, so a Mouse Follow without a
  tracker shows "—").
  - **Catch-up saccades:** I-VT saccades (50 deg/s, existing) in the trial window, per second of
    valid data.
  - **Pursuit gain:** over the trial's samples with saccades removed (±1 sample padding) and the
    gaze within 3° of the target, take the gaze velocity component along the target's direction ÷
    the target speed. The trial value is the median. Samples within 100 ms of a bounce (direction
    reversal) are excluded. The circular path uses the tangent direction. The target position at
    device rate is recomputed from `target_track.csv` (20 Hz) by linear interpolation; between
    bounces the speed is constant. Fewer than 0.5 s of usable
    samples → "—". The report labels gain "smooth-pursuit gain (children's typical range about
    0.6-0.85; vertical lower)", with no pass/fail.
- **H9 Follow trial length.** `timeout_ms` is reused as the trial length and labelled
  **"Trial duration (s)"** on the follow page: default 10 s, 3-30 s, step 0.5 s. Every trial runs
  for its full duration. `motion.select_window_ms` is removed from the registry and the page. Old
  test configurations that still carry it load fine; the key is ignored.
- **H10 Old Follow & Click data.** The report builder keeps reading old follow sessions (with
  `is_hit` and no `on_target_ms` column) in the old layout, with no exception. No migration. Old
  sessions are handled by the parent SPEC's U16.

## 4. Design

### 4.1 Configuration page

- New card **"Input"**, first in column 2, above Selection:
  - **Pointer:** radio Gaze / Mouse (all tasks).
  - **Selection:** radio Dwell / Switch (static, grid, scanning; not follow).
- The card "Selection (Dwell)" is renamed **"Dwell"**. Its controls are greyed in place when
  Selection = Switch: threshold, and the progress ring check box in Feedback. Jitter tolerance and
  refractory stay active, because the hitbox and the debounce apply to the switch too.
- Feedback card: + "Glow on target" (H3), greyed when Selection = Dwell.
- Follow page:
  - The Timing card shows "Trial duration (s)" and the inter-trial interval. The selection window
    row is gone.
  - No Selection radio and no Dwell card (follow has nothing to select). The Pointer radio stays.
- V5 of the parent SPEC (seconds everywhere on screen) applies to every new label.

### 4.2 Switch selection at run time

- `TaskCanvas` gets a `mousePressEvent`: a left button press → `SwitchInput.press()`. It is
  active only while a run is on screen with Selection = Switch, or with Pointer = Mouse (H2). Other
  buttons are ignored. Presses on the run bar never reach the canvas, so they stay operator
  actions (I6).
- With Pointer = Gaze and Selection = Switch: at run start the OS cursor is moved to the canvas
  centre (`QCursor.setPos`) and the canvas cursor is set to `Qt.BlankCursor`. It is restored when
  the run ends, pauses or quits. On Pause the cursor is shown, so the operator can use the bar.
- `BaseTask.update` (click path, `input_selection == "switch"`):
  - Phase TARGET: the press is hit-tested with the current smoothed pointer. If that pointer is
    invalid, the last valid one within 150 ms is used (I5c). If there is none, the press is a
    **Click error** with `reason=no_gaze`.
  - Phase ITI / pre-roll / pause: the press is consumed and ignored (I5d). It is logged as
    `SWITCH_IGNORED` in events.jsonl, not counted.
  - Every counted press is an event: `SWITCH_PRESS` (`x, y, on_target, used_fallback`).
- Glow: the scene carries `on_target` while the pointer is on the target. The canvas draws a
  soft halo around the target (H3), the same drawing as Follow's glow.
- Preview and Practice use the test's Pointer and Selection. Preview's pointer is always the
  mouse, as now (its purpose); with Selection = Switch, a left click selects in Preview.

### 4.3 Mouse pointer at run time

- See H4/H5. The gaze cursor dot follows the pointer the same way: smoothed, when "Show gaze
  cursor" is on. In a Mouse run the OS cursor stays visible.
- Dwell with the mouse = hover dwell (today's Preview behaviour, now recordable).

### 4.4 Follow the Target

- `FollowMovingTask`:
  - `select_windows`, `is_selectable` and the click/dwell path are removed. It overrides the
    selection step so that a trial never "hits".
  - Each trial ends at `timeout_ms` (= trial duration) with `is_timeout` false and a new outcome
    `followed` / `not_followed` (H6).
- Per frame (TARGET phase), the task accumulates for the trial:
  - `valid_ms` — frames with a valid pointer
  - `on_target_ms` — of those, the frames on target (H7)
  - `dist_sum_px` and `dist_n` — the distance from the pointer to the target centre, valid frames
    only
- `trials.csv` gains the columns `valid_ms`, `on_target_ms`, `time_on_target_pct` and
  `mean_dist_px` (empty for the other tasks). `t_first_gaze_on_target_ns` stays: in the report it
  becomes "Time to find target (s)".
- Feedback: glow while on target (`feedback.target_glow`). At trial end, if followed, play the
  hit sound (`feedback.hit_sound` setting); otherwise silence. A miss sound is never used in
  Follow.
- The instruction text ("follow the moving target with your eyes") and the YAML title are
  updated. Display name: **Follow the Target**.

### 4.5 Report

- **Selection tasks with Switch:** new columns **Clicks** (presses counted in the trial) and
  **Click errors** (presses off target or with no gaze). Summary rows show their means. The
  "Selection" configuration row reads "Switch press (mouse/switch button), refractory 0.5 s".
  Reaction time (onset → first entry) and Error-free (U10, hit within the first entry) are
  unchanged. With Dwell, the Clicks columns are not shown.
- The "Input" configuration row shows Pointer + Selection, e.g. "Gaze (GP3 HD, 150 Hz) · Switch",
  or "Mouse · Dwell 0.8 s".
- **Follow the Target summary:**
  - Followed n/N (≥ 50 %)
  - Time on target % (mean, range)
  - Mean distance (deg)
  - Time to find target (s)
  - Pursuit gain (median, with the H8 caption)
  - Catch-up saccades /s
  - Valid %
- Follow per-trial table: the same columns per trial.
- Follow Target Map:
  - Summary: the path polyline with the fixation scanpath (parent V2).
  - Detailed per trial: the target track plus the smoothed pointer path, with the samples
    off target drawn lighter.
  - The legend (parent V1) gets "on target / off target" entries.
- Mouse runs:
  - The eye sections (saccades, pupil, eye metrics, fixation scanpath) show "not recorded" when no
    gaze was recorded.
  - The pointer path comes from `pointer_stream.csv`.
- The PDF follows the screen (parent V3: portrait).

### 4.6 Data

- `metadata.json`: `input_pointer`, `input_selection` (null for follow), `input_mode` (derived,
  H1), `gaze_recorded` (bool).
- `trials.csv`:
  - + `clicks` and `click_errors` (switch tasks; 0 for dwell)
  - + the follow columns (4.4)
- New `pointer_stream.csv` for Mouse runs (H4).
- `report.json`:
  - new `follow` block (per-trial + summary metrics, gain params `max_err_deg=3`,
    `bounce_excl_ms=100`, `min_usable_s=0.5`, `followed_pct=50`)
  - `clicks` / `click_errors` in the trial and summary rows
- Data files keep ms (parent V5).

## 5. Scope

**In:**
- Pointer + Selection settings and page controls.
- Switch via canvas left press and Space/Enter.
- Cursor park/hide, the blink fallback and the ignore-between-trials rule.
- Glow.
- Mouse-pointer recorded runs, with optional gaze recording, and the gate change.
- Follow without selection: duration, live metrics, gain/catch-up analysis, sound.
- Report/PDF additions.
- Tests.

**Out:**
- Gamepad/HID libraries.
- Telling the switch apart from the operator's mouse at device level (Windows raw input).
- Hold Time and Double Click.
- An "Either" selection mode.
- Two-switch or scanning-by-switch tasks.
- A pursuit pass/fail norm.
- Changing the parent's P9c items (done first, there).

## 6. Acceptance criteria

- **A1** The config page shows the Input card with Pointer for all four tasks and Selection for
  three (none for follow). The choices persist in the test's configuration and in named
  configurations.
- **A2** Selection = Switch, Pointer = Gaze:
  - a canvas left press with gaze on target selects
  - a press off target adds a Click error and the trial continues
  - a press during ITI is ignored
  - Space/Enter behave the same
  - the cursor is hidden on the canvas and comes back on Pause and at the end
- **A3** Blink fallback: a press with an invalid pointer and a valid on-target pointer 100 ms
  earlier is a hit. 200 ms earlier is a Click error (`no_gaze`).
- **A4** The glow shows only while the pointer is on the target (switch selection and follow), and
  the dwell ring is not drawn in switch mode.
- **A5** Pointer = Mouse:
  - runs and records with the tracker disconnected
  - `pointer_stream.csv` is written
  - `gaze_recorded` is false
  - the report's eye sections say "not recorded"
  - with the tracker connected, `all_gaze.csv` is written as well
- **A6** Follow:
  - every trial lasts exactly the trial duration (±1 frame)
  - there is no hit/selection path
  - `time_on_target_pct` from a synthetic pointer on the target half the time = 50 ± 1
  - the sound plays only on followed trials
- **A7** Pursuit gain on a synthetic trace that follows a constant-speed target at 0.8× speed (with
  noise) = 0.8 ± 0.05. Catch-up saccades per second are counted from injected saccades. Fewer than
  0.5 s usable gives "—".
- **A8** The report and PDF show the Switch columns (switch tasks only) and the Follow summary/table
  (follow only). Old follow sessions still open in the old layout without errors (H10).
- **A9** `metadata.input_mode` is derived as in H1, and `report_config` labels all of its values.
- **A10** Live, on the real device with the user's switch:
  - a Grid Click test with Gaze + Switch
  - a Grid Click test with Mouse + Dwell (tracker unplugged or not)
  - a Follow the Target test with Gaze
  - each recorded, saved and reported

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | Parent SPEC P9c (V1-V5) implemented and checked first, so the report work below builds on it. **P9c committed `6bad506` 2026-10-07; its live re-check is still open** (the user chose to go ahead) | — |
| 1 **DONE 2026-10-07** (approved) | Wireframes: `task-config` (Input card, renamed Dwell card, Glow, Follow timing), `report-summary` / `report-detailed` (Switch columns, Follow block), `start-test` (Mouse note) | **WF gate** |
| 2 **DONE 2026-10-08** | Engine: settings keys + registry/page data (H1, H3), `SwitchInput` canvas press, cursor park/hide, BaseTask switch rules + events + `clicks` / `click_errors`, pointer/recording split + `pointer_stream.csv` + run gate (H4, H5) | — |
| 3 | Follow: task rewrite (4.4), live metrics + columns, glow + end sound; analysis (`report_follow.py`: gain, catch-up saccades) + `report.json` block | — |
| 4 | UI: config page Input card, report tables/summary/map/legend + PDF for Switch and Follow, report_config labels | — |
| 5 | Review + live check A10 with the user and the switch; commit on the user's OK | user |

## 8. Impl log

- **2026-10-07 — step 2 (Engine), `claude-sonnet-5-5`.** Worktree note: the worktree branch was
  created at `main` (`c7e61cf`), not at `feature/compass-task-flow`; I fast-forwarded it to
  `d95e7f5` (`git merge --ff-only`, no commit, no branch change) before starting. Nothing is
  staged or committed.
  - **New modules.**
    `src/engine/input_choice.py` (Qt-free: `resolve_input`, `derive_input_mode`, `glow_active`,
    the mode helpers, and the two Setup blocker sentences a Mouse test drops);
    `src/tasks/switch_select.py` (`PointerTrace`, the 150 ms blink fallback, I5c);
    `src/inputs/no_tracker.py` (`NoTracker`, the recording client of a Mouse run with no tracker);
    `src/ui/run_cursor.py` (`RunCursor`: hide with `Qt.BlankCursor` and park with
    `QCursor.setPos(screen, point)`, both checked against the Qt docs);
    `src/ui/choice_lists.py` and `src/ui/canvas_cursor.py` (split out of `settings_registry.py`
    and `canvas.py` to keep them under 500 lines; names re-exported / imported back).
  - **Settings (H1, H3, A1 data).** `settings_registry.py`: structural `input.pointer` (every
    task), `input.selection` (static, grid, scanning), `feedback.target_glow` (bool, default on);
    the **Input** card is first in column index 2 (Follow: Pointer only), the card "Selection
    (Dwell)" is now **Dwell** (id stays `selection`); "Glow on target" sits in Feedback after the
    instant ring; `ConfigControl.greyed_by` carries 4.1's rules (threshold and ring greyed under
    Switch, glow greyed under Dwell; refractory and jitter stay active) and `config_form` /
    `task_config_page` apply it, greyed in place. Tooltips added. The values persist in a test's
    configuration and in named configurations like any structural setting.
  - **Derived mode (H1, A9).** `metadata.input_mode` is `eye` / `gaze_switch` / `switch` /
    `mouse_dwell` / `mouse_follow` from the pair; new `metadata.input_pointer`, `input_selection`
    (null for Follow), `gaze_recorded`. With no per-test `input` block (a standalone launch, a
    headless replay, a test stored before this) the old global `input.mode` still decides, so
    nothing that ran before changes; `build_task` and the replay pipeline use the same resolver.
    `report_config.py` labels all five values (a mouse mode names the tracker only when
    `gaze_recorded`).
  - **Switch rules (I5, A2, A3).** `TaskCanvas` has `mousePressEvent` (left button, only while
    `switch_press_enabled`) and signals `switchPressed` / `switchReleased` (release also on focus
    loss); Space / Enter feed the same `SwitchInput` on key down, auto-repeat ignored, only when
    Selection = Switch; `SwitchInput` got `reset()`; **the key release is now wired** (before,
    `SwitchInput` was never released, so only the first Space press of a run could count).
    `BaseTask`: `input_selection` derived from the mode; under Switch (or with no dwell selector)
    a press in the target phase is judged at this frame's pointer, else the last valid one within
    150 ms, else `no_gaze`; on target and selectable is a hit, anything else a Click error and
    the trial goes on (`clicks`, `click_errors`, `attempts`, `SWITCH_PRESS` with `x, y, on_target,
    used_fallback[, reason]`, and the existing `MISS_CLICK`); a press in the pre-roll, the pause
    between trials (judged in the phase the frame started in) or after the last trial, and a press
    while the run is paused, is `SWITCH_IGNORED` (`phase`) and not counted. `trials.csv` gains
    `clicks` and `click_errors` (after `slot_index`; 0 under Dwell).
  - **Cursor and glow (I6, A2, A4).** Gaze + Switch: at the first tick with the canvas on screen
    the OS cursor is parked at the canvas centre and hidden; shown on pause, quit and the end of
    the run; hidden and parked again on resume. Never for Dwell or a Mouse pointer. The glow is a
    soft radial halo in the theme's particle colour behind the target, drawn while the pointer is
    on a selectable target and `show_glow` (setting on and Switch or Follow); the dwell ring is
    forced off in a switch run.
  - **Mouse pointer and recording (H4, H5, A5).** `AssessmentApp(pointer_source=...)`: a Mouse
    run (and any Preview) reads a `MouseGazeSource` bound to the canvas; `client` is then only the
    tracker recording alongside, or a `NoTracker`. No calibration is started for a Mouse run
    without a preset (`calibration_source` "not run"). `SessionRecorder.open(gaze_stream=...)`,
    `open_pointer_stream()`, `record_pointer()` and the `NullRecorder` twins; `pointer_stream.csv`
    (`t_ns,x,y,valid`, raw mouse); no `gaze_stream.csv`, `all_gaze.csv`, `eye_geometry.csv` when
    there is no tracker. The monitor geometry is not applied to a mouse pointer; the run bar says
    "mouse pointer" and reports no tracker for a Mouse run with none. The report: `session.pointer`
    / `selection` / `gaze_recorded` / `sources.pointer_stream`, and the Eye Metrics table (page and
    PDF) says "not recorded" when `gaze_recorded` is false.
  - **Run gate and Start page (H5).** `StartTestPage` drops the tracker and calibration blockers
    for a Mouse test and shows the one-line note (three texts, see §9); `RunFlow._build` passes the
    Setup tracker only when it is connected and calibrated, and never refuses a Mouse test for a
    missing tracker; Gaze tests are gated exactly as before. `SetupPage.run_blockers` is
    unchanged apart from sharing its two sentences with `input_choice`.
  - **Read-aloud wording (W1).** Switch replaces the dwell step with "Look at the circle, then
    press the button." (square / "Find the bright shape, look at it, ..." per task) plus "The
    {noun} glows while you are looking at it." when the glow is on; Mouse replaces the dot
    sentence with "Move the mouse to point at the screen." and turns "look at" into "point at".
    Follow's own wording is step 3's.
  - **Docs.** `docs/DATA_SCHEMA.md` (pointer_stream.csv, metadata fields, trials columns, the two
    events, report session fields), `README.md` (feature bullet, test count).
  - **Tests added (231 net).** `test_input_choice.py` (H1 table, resolver, glow rule, blockers),
    `test_switch_rules.py` (A2/A3 on `BaseTask`, `PointerTrace`, `SwitchInput`),
    `test_input_settings.py` (A1 data: registry, Input / Dwell cards, greying, persistence,
    named configurations, the real page), `test_switch_run.py` (A2/A3/A4 through the app and the
    canvas: left press, off target, ITI, blink, Space/Enter, right button, run bar, pause, cursor
    park/hide/show, glow pixels, no dwell ring), `test_mouse_run.py` (A5/A9: no tracker, with a
    tracker, files, report text, derived modes, labels), `test_mouse_run_gate.py` (H5 on the page
    and the run flow, W1 wording), `test_pointer_stream.py` (recorder, schema, status line,
    `NoTracker`); shared rig `tests/input_run_fixtures.py`. Existing tests updated for the new
    columns / settings / cards (header order, `EXPECTED` card table, feedback dicts, the dialog's
    control set, report `sources`) and two fake-app namespaces given the new attributes.
  - **pytest (whole repo, worktree, offscreen):** `5 failed, 2364 passed, 2 skipped`. Baseline
    before my changes in the same worktree: `5 failed, 2133 passed, 2 skipped`. The same 5
    fail in both and none is mine: they assert the lab's local `dwell.smoothing.alpha` 0.22, and
    the worktree's committed `configs/default.yaml` says 0.35
    (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and the four
    `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[*]`);
    `test_config_merges_task_over_default` did not fail here. `ruff` is clean on the new files
    (the fixture-import `F811` is waived file-wide in the two app-level test modules).
  - **Deviations from the SPEC text:** none that change a decision; the readings in §9 ("decided,
    non-blocking") and the two OPEN questions there are the only places I went beyond or short of
    the wording.
  - **Not done (belongs to later steps or out of scope):** Follow's rewrite (4.4), `report_follow.py`
    and the `follow` block; `clicks` / `click_errors` in `report.json` trial and summary rows and
    the Switch columns on the page and PDF; the Input row's "Gaze · Switch" display format; the
    Follow page's removal of the Dwell card and the selection window (the old follow still selects
    by dwell, so its `dwell.*` controls stay); per-trial eye columns saying "not recorded";
    the clinician line "Check that the bottom bar says tracking OK" is unchanged for a Mouse test;
    nothing run on the real device or with the real switch (A10 is step 5). `app.py` (1231 lines)
    and `base_task.py` (751) were over 500 before and are larger now; a split is a refactor of its
    own.
- **2026-10-07 — step 2 addendum (the user's answers to the two OPEN §9 questions), `claude-sonnet-5-5`.**
  Same worktree, still step 2; nothing staged or committed. Both §9 items are marked RESOLVED
  and the six "decided" calls CONFIRMED by the user as built. This addendum **supersedes** the
  first entry where it says the refractory period does not gate presses and where it lists the
  Setup gate as unchanged.
  - **Refractory is the switch's debounce.** `BaseTask`: while a target is up, a press within
    `dwell.refractory_ms` of the previous **counted** press is ignored: no click, no Click error,
    no attempt, no `SWITCH_PRESS` or `MISS_CLICK`; it is logged `SWITCH_IGNORED` with
    `phase="target"`, `reason="refractory"` (and `x`, `y`). A press exactly `refractory_ms` after
    the last counts. Two readings the user's answer did not spell out, both the dwell's own
    behaviour: the window **restarts with each trial** (the dwell resets its refractory in
    `_start_trial`, and a quick first press on a new target must not be lost), and an **ignored
    press does not extend** the window. The value is the dwell selector's `refractory_ms` when the
    task has one (the app always builds one from the run's config, so the live setting applies),
    else `config["dwell"]["refractory_ms"]`, else 0 (a bare test task is not debounced). The control
    stays active under Switch and the report's "Switch press, refractory 0.5 s" row is unchanged.
    `ignore_press` gained `reason`. Docs: `DATA_SCHEMA.md` (`SWITCH_IGNORED` row, `clicks`),
    `README.md`. Tests (`test_switch_rules.py`, `test_switch_run.py`): a press at +0.3 s ignored
    and one at +0.6 s counted; a correct press 0.3 s after a Click error ignored; exactly +500 ms
    counts; an ignored press does not extend the window; the window restarts with each trial;
    the selector's value wins over the config; 0 debounces nothing; a bare task and a dwell run
    are untouched; the live setting through the app.
  - **Setup: Continue to Tests without a tracker.** `SetupPage.continue_blockers()` is
    `run_blockers()` minus the tracker and calibration sentences; `can_continue()` is "no
    continue blockers"; the Continue button no longer waits for either (its tooltip no longer asks
    for them). A new note above the button (`gaze_note`, the Start page's info style) reads
    "No tracker connected: only Mouse tests can run." (no client or a dropped link, named first
    whatever the calibration) or "Not calibrated: only Mouse tests can run." (connected, no
    calibration); hidden when both are fine. Texts and `gaze_only_note()` live in
    `input_choice.py`. `run_blockers()` itself is unchanged, so a gaze test stays blocked on its
    Start page by the same two sentences; Subject ID, Sex and the display-standard acknowledgement
    still gate Continue. `test_run_blockers.py`'s "run_blockers is empty iff can_continue" check
    became "continue_blockers is empty iff can_continue, which is subject and sex and display ok,
    and the two lists differ only by the tracker and calibration sentences". New
    `tests/test_setup_continue_without_tracker.py` (both notes, the enabled button, the other
    requirements, the dashboard going to the Test List with no tracker).
  - **Existing test adjusted:** `test_task_pipeline::test_hit_testing_uses_live_screen_size_not_config_default`
    presses twice a millisecond apart; it now sets `dwell.refractory_ms` to 0 (the new debounce
    would otherwise ignore the second press, as intended).
  - **pytest (whole repo, worktree, offscreen):** `5 failed, 2392 passed, 2 skipped` (the first
    entry's run was 2364 passed; +28 tests here). The 5 failures are exactly the same as the
    baseline and as before: the lab-local `dwell.smoothing.alpha` 0.22 checks against the
    worktree's committed `configs/default.yaml` (0.35), namely
    `test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and the four
    `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[*]`. ruff is clean on
    the files touched in this addendum.
- **2026-10-08 — step 3 (Follow the Target), `claude-sonnet-5-5`.** Same worktree, reset by the hub
  to `64692b3` (step 2 committed `7b5ece6`); nothing staged or committed. §4.4, I8-I12, H6-H9,
  A6, A7 and the data side of §4.5 / §4.6; the report page, PDF, summary tables and map legend are
  step 4 and untouched (`report.json` carries what they need, see below).
  - **Task (4.4, H6, H7, H9).** `FollowMovingTask` has `has_selection = False`: no select
    windows, no `is_selectable`, no dwell or click path. `BaseTask` got four small hooks the
    other tasks leave as they were (`_observe_frame`, `_end_by_time`, `_trial_cue`, `_end_event`)
    and a `has_selection` class flag; with it False a frame never produces a click or a hit and
    the trial ends at `timeout_ms`. Every frame, from the live smoothed pointer and the existing
    hitbox (`effective_radius_px + jitter_px`, the same test that draws the glow): `valid_ms`,
    `on_target_ms`, `dist_sum_px`, `dist_n` (an invalid frame adds nothing; one frame's span is
    capped at 250 ms so a stall is not counted as tracking). At the end `is_hit` = followed =
    at least 50 % of the valid time on target (`FOLLOWED_PCT`); no valid time at all is not
    followed. Events `FOLLOWED` / `NOT_FOLLOWED` (`trial`, `time_on_target_pct`) replace
    `HIT` / `TIMEOUT`; a skipped trial is `SKIPPED` as before. The hit sound (and particles) play
    only for a followed trial, at its end, at the target's end position; there is no miss sound
    anywhere in Follow. The target keeps moving for the whole duration (the trial length is exact
    to the frame: tested in the app at 3 s). Glow while on target: the canvas is told `on_target`.
  - **Data (4.6).** `trials.csv` gains `valid_ms`, `on_target_ms`, `time_on_target_pct`,
    `mean_dist_px` (after `click_errors`, blank for the other tasks); `time_to_first_fixation_ms`
    stays (the report's "time to find"). `metadata.hitbox_margin_px` (the run's
    `dwell.jitter_tolerance_px`) is new, for every task, so a report can redraw the hitbox.
  - **Settings (H9, I12).** `motion.select_window_ms` is gone from the registry and page (an old
    test or config that carries it loads, the key is read nowhere). `task.timeout_ms` on the
    Follow page is "Trial duration (s)": 3-30 s in 0.5 s steps (`_TASK_VARIANTS`, same key, so
    stored values, profiles and data files are unchanged), default 10 s in the YAML. The Timing
    card is trial duration + inter-trial interval. New `excludes` on both setting records ("every
    task but ..."): the dwell threshold, ring, instant ring, refractory, jitter tolerance, the miss
    sound and the Selection control are not offered on Follow (`TASKS_WITHOUT_SELECTION`), so the
    Follow page is Pointer only with no Dwell card; `AssessmentApp` builds no dwell UI for it
    (rings off, no refractory). `settings_registry.py` was 493 lines at `64692b3` and would have
    been 525: the two records moved to the new `src/ui/setting_types.py` (re-exported; 480 now).
  - **Wording (I11, W1).** Display name "Follow the Target" (`task_info`, YAML title
    "追視 / Follow the Target", report text); the read-aloud text is W1's Follow wording with
    `{timeout}` for the duration, the glow sentence dropped when the glow is off, "with the mouse"
    for a Mouse test; the practice result says "N of M followed".
  - **Analysis (4.5, H8, A7): `src/data/report_follow.py` (new, 468 lines).** `build_follow`
    returns the `follow` block (below). Pursuit gain per H8: saccades from the existing I-VT
    removed with one sample either side, gaze within 3 deg of the target (real degrees via the
    geometry), 100 ms around each bounce of the target excluded, circular uses the tangent (the
    direction is the chord of the interpolated track), target position at device rate by linear
    interpolation of `target_track.csv`, median per trial, under 0.5 s usable gives `None`. Catch-up
    saccades per second = the existing detector's saccades in the trial / valid gaze seconds.
    Both need `all_gaze.csv`; a Mouse run with no tracker gets `None` for them but still has
    time on target, distance, time to find and the pointer path (from `pointer_stream.csv`).
    `report.json` `follow`: `{"legacy": true}` for a folder whose `trials.csv` has no
    `on_target_ms` (H10, tested with a Follow & Click folder in the old layout), else `legacy`,
    `params` (`max_err_deg` 3, `bounce_excl_ms` 100, `min_usable_s` 0.5, `followed_pct` 50, plus
    the 100 ms velocity window and the 1-sample padding), `path`, `speed_frac_per_s`,
    `trial_duration_s`, `gaze_available`, `hitbox_margin_px`, `trials` (per trial: `outcome`,
    `followed`, `duration_s`, `valid_ms`, `on_target_ms`, `time_on_target_pct`, `mean_distance_px`
    and `_deg`, `time_to_find_s`, `valid_pct`, `pursuit_gain`, `gain_usable_s`, `catch_up_count`,
    `catch_up_per_s`, `pointer_path` = polylines `{on, pts}` split where the pointer enters or
    leaves the moving target's hitbox) and `summary` (the W2 rows: `followed`/`n_trials`,
    `time_on_target_pct` mean/min/max, `mean_distance_deg`, `time_to_find_s`, `pursuit_gain`
    median, `catch_up_per_s`, `valid_pct`). `trials[*].outcome` is `followed` / `not_followed`
    (counted as scored by the eye metrics, the quality share, `n_scored`); the config rows say
    "Trial duration" and drop the Selection row for Follow. `REPORT_VERSION` is now 3 (cached
    version-2 reports of Follow runs have the old shape and are rebuilt).
  - **Docs.** `docs/DATA_SCHEMA.md` (columns, the Follow rows paragraph, `FOLLOWED` /
    `NOT_FOLLOWED`, `hitbox_margin_px`, report version 3, the `follow` block and the gain
    definition), `README.md` (Follow bullet, speed section without the selection window, the test
    count).
  - **Tests added (83 new, `tests/test_follow_task.py` 34, `test_follow_analysis.py` 25,
    `test_follow_report.py` 14, `test_follow_run.py` 10; shared `tests/follow_fixtures.py`).**
    A6: exact duration, no hit path, 50 +/- 1 % on target from a synthetic pointer that is on the
    target half the time, sound only on followed trials, never a miss sound, glow, no rings, task
    through the app. A7: gain 0.8 +/- 0.05 across seeds on horizontal, vertical and circular
    paths, injected saccades counted, under 0.5 s usable is `None`, bounce and 3 deg rules, a Mouse
    run with no tracker. H10: an old Follow & Click folder builds a report with no exception.
    Existing tests updated for the removed select window / Dwell card / new columns / report
    version 3 (listed in the diff; each change is the removal or the new column, no assertion
    about other behaviour was loosened).
  - **pytest (whole repo, worktree, offscreen):** `5 failed, 2480 passed, 2 skipped` (2487
    collected; step-2 baseline in this worktree `5 failed, 2392 passed, 2 skipped`, so +88
    passed). The 5 failures are the same lab-local `dwell.smoothing.alpha` 0.22 checks against the
    worktree's committed `configs/default.yaml` (0.35): `test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`
    and the four `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[*]`.
    `ruff check src tests` reports only the 10 findings that were already there (import order in
    `app.py`, `datetime.UTC`, `zip(strict=)` in files I did not touch for those lines); the new and
    split files are clean. (One access violation in `start_test_page._fill` showed up once in a
    mixed subset run midway and did not recur alone or in the full run; noted, not explained.)
  - **Deviations from the SPEC text:** none that change a decision. Readings the SPEC left open are
    in §9 ("decided, non-blocking"). Over 500 lines before and after: `base_task.py` (now 828) and
    `app.py`, as in step 2.
  - **Not done (step 4 / step 5):** the report page and PDF tables for Follow and Switch, the
    summary rows on screen, the map legend entries and the Follow Target Map drawing, the
    "Clicks" columns on the report, the per-trial eye columns saying "not recorded"; no live run
    (A10 is step 5); nothing run on the device.

## 9. Implementer open questions

- **2026-10-08 (step 3) — CONFIRMED by the user 2026-10-08 as built; the hitbox margin stays
  fixed at 40 px (not a page control), recorded per run as `metadata.hitbox_margin_px`; if the
  doctor wants to tune it after the live check A10, it is a later small step (un-exclude the
  jitter control for Follow and place it on the Timing card).** The readings as the implementer
  listed them: decided, non-blocking; for the hub's review. Calls the SPEC does not
  spell out, each the least surprising reading:
  - *Followed is stored as `is_hit`.* 4.4 says "a new outcome `followed` / `not_followed`" with
    `is_timeout` false. `trials.csv` keeps its two flags: `is_hit` = followed, `is_timeout` = 0
    always, and the report derives `followed` / `not_followed` from them when the header has
    `on_target_ms`. An older Follow & Click folder (no such column) keeps `hit` / `timeout`.
  - *The hitbox margin of Follow is not settable.* The Dwell card is gone from the Follow page
    (including the jitter tolerance, which is the hitbox margin), so Follow's "on target" test
    uses the configured `dwell.jitter_tolerance_px` (40 px by default) and records it as
    `metadata.hitbox_margin_px`. If the clinician should tune it, the control would have to stay
    on the Follow page.
  - *Velocity for the gain is a 100 ms least-squares slope.* H8 says "gaze velocity component along
    the target's direction"; a difference of two samples would drown a 10 deg/s target in the
    device noise, so it is the slope over a 100 ms window centred on each kept sample, and the
    window must be entirely usable (no invalid or saccade sample in it). The target's velocity is
    the chord of the interpolated track over the same window.
  - *The 3 deg test is angular distance from the target's interpolated position at the sample.*
    Computed with the session geometry (`2 atan(d / 2D)`); a folder with no monitor size gives no
    gain.
  - *`valid_ms` caps one frame's span at 250 ms.* A stall (a long frame) is not counted as
    tracked time.
  - *A trial with no valid time is not followed* (`time_on_target_pct` blank) rather than an
    undefined percentage.
  - *`REPORT_VERSION` 3.* The new outcomes, the `follow` block and `hitbox_margin_px` change the
    cached shape; existing caches are rebuilt on open.
  - *The Follow Input row* reads "Eye gaze" for a gaze Follow (there is no Selection to name);
    the Selection row is dropped from its Test Configuration table (16 rows).

- **2026-10-07 (step 2) — RESOLVED 2026-10-07, user: "Yes, debounce". Built in the step-2
  addendum (§8): during a target, a press within `dwell.refractory_ms` of the previous counted
  press is ignored (not a click, not a Click error), logged `SWITCH_IGNORED` with
  `reason=refractory`; the control stays active under Switch and the report row is unchanged.**
  *Question as asked:* refractory as a switch debounce. 4.1 and the
  `task-config` wireframe say the Dwell card's **refractory** stays active under Switch "because
  the hitbox and the debounce apply to the switch too", and 4.5 shows "Switch press (mouse/switch
  button), refractory 0.5 s" in the report. But I5 and 4.2, which define the switch rules, say
  nothing about ignoring a press that comes within `refractory_ms` of the last one, and such a
  rule would also drop a correct press made right after a Click error (default 0.5 s). **What I
  built:** the jitter tolerance applies (it is the hitbox, `hit_test`); the refractory period does
  **not** gate presses, so every press made while the target is up counts. The control is still
  active on the page and still printed in the report row, as the SPEC says. **Needed:** either
  "refractory ignores presses (and logs `SWITCH_IGNORED reason=refractory`)" or "refractory is
  not applied to presses; grey it under Switch too" (that changes 4.1 and the wireframe).
- **2026-10-07 (step 2) — RESOLVED 2026-10-07, user: "Allow Continue without tracker". Built in
  the step-2 addendum (§8): "Continue to Tests" is enabled with no tracker and/or no
  calibration; the Setup page says "No tracker connected: only Mouse tests can run." or, for a
  connected but uncalibrated tracker, "Not calibrated: only Mouse tests can run."; gaze tests
  stay blocked on their Start page by the existing blockers; Subject ID, Sex and the
  display-standard acknowledgement still gate Continue.** *Question as asked:* the Setup gate
  still needs a tracker. H5 only
  relaxes **Start and Practice** for a Mouse test. The Setup page's own "Continue to Tests" gate
  (`SetupPage.can_continue`, the same blockers) still demands a connected, calibrated tracker, so a
  Mouse test with the tracker unplugged can only be reached if the tracker drops *after* Setup
  (the unit tests drive exactly that). A10 ("Grid Click with Mouse + Dwell, tracker unplugged or
  not") cannot be done on a PC with no tracker from a cold start. **Not changed** (outside H5's
  wording). **Needed:** whether Setup may continue without a tracker (e.g. a "Continue without a
  tracker (Mouse tests only)" choice) and, if so, what the Setup card says.
- **2026-10-07 (step 2) — decided, non-blocking; CONFIRMED by the user 2026-10-07 as built.**
  Small calls the SPEC does not spell out, each the least surprising reading:
  - *Resume re-parks the cursor.* 4.2 says the cursor is restored on pause/end/quit. After the
    operator clicks Resume on the bar the OS cursor sits on the bar, so the child's next switch
    press would land on Pause/Skip/Quit. I therefore hide and park it again on resume (the same
    as at run start).
  - *Left press enables the switch only when Selection = Switch.* 4.2 words it "with Selection =
    Switch, **or with Pointer = Mouse**". Under Mouse + Dwell a press would do nothing anyway (the
    dwell path ignores clicks), so I enable the canvas press for Selection = Switch only; the
    result is identical and no `SWITCH_*` event appears in a dwell run.
  - *Mouse sentence is always read.* W1: the "small dot" sentence becomes "Move the mouse to point
    at the screen." It is shown for every Mouse test, whether or not "Show gaze cursor" is on
    (the dot sentence is conditional on that setting; the child must be told to move the mouse
    either way). Follow's own wording is left for step 3, so a Mouse Follow only gets the first
    sentence and the "look at" to "point at" swap.
  - *Third Start-page note.* H5 gives two note texts. A tracker that is connected but **not
    calibrated** records no gaze (I7: "connected (and calibrated)"), so the note says "Mouse test
    — the tracker is not calibrated, so no eye data will be recorded." for that case.
  - *A Mouse run on a PC with no tracker takes the monitor size from the canvas's own screen*
    (`metadata.screen_width_px/height_px`, physical px), so the report can still give degrees;
    with a tracker the tracker's `SCREEN_SIZE` is used as before.
  - *The report's "not recorded"* is in the **Eye Metrics table** (`eye_rows`, so the PDF too).
    The per-trial eye columns (Fixations, Saccades, Pupil) still show "—" until step 4 reworks
    those tables; `report.json` carries `session.gaze_recorded` for that.

## 10. Log

- **2026-10-07** — Created from the doctor's feedback (input method; Follow without a click),
  relayed by the user after the P9 real-device run. Compass guide read (Aim Selection Method,
  Clicks, Switch test). Parallel search on gaze + switch vs dwell and on smooth-pursuit metrics
  (§3.2). User decisions I1-I12 taken in this session (three rounds of questions). Hub decisions
  H1-H10 proposed, awaiting approval.
- **2026-10-07** — The user approved H1-H10 as written. SPEC committed on `feature/compass-task-flow`. Next: the compass SPEC's P9c pass (step 0), then step 1 here.
- **2026-10-07** — Step 1 done: the hub updated the wireframes `task-config` (Input card, Dwell card, Glow on target, Follow timing), `start-test` (Mouse note, proposed read-aloud text), `report-summary` (Switch columns, Follow summary table, Mouse "not recorded") and `report-detailed` (Switch columns, Follow per-trial table, on/off-target path); rendered with wiremd. **The user approved them as is**, plus W1 (read-aloud wording) and W2 (Follow Metric/Value table) in §3.2a. P9c of the parent SPEC was committed first (`6bad506`) so these wireframes get their own commit. Next: steps 2-4 by spec-implementer.
- **2026-10-08** — Step 2 done by spec-implementer in an isolated worktree (§8, incl. the addendum), merged into the main tree by the hub. §9 resolved with the user: refractory = switch debounce (`SWITCH_IGNORED reason=refractory`), Setup may continue without a tracker (Mouse-only note), the six small calls confirmed. Hub review: in scope, A1 (data), A2, A3, A4, A5, A9 met by tests; pre-existing key-release bug fixed (only the first Space press used to count); `app.py` (1231) and `base_task.py` (786) remain over 500 lines (pre-existing, later cleanup). Hub full pytest in the main tree: **2397 passed, 2 skipped, 0 failed**. Committed on the user's OK with offscreen review only; live check A10 is step 5. Next: step 3 (Follow the Target).
- **2026-10-08** — Step 3 done by spec-implementer in the same worktree (§8), patched into the main tree by the hub (`git add -A` + `diff --cached --binary` + `git apply`). §9 step-3 readings taken to the user: **all confirmed as built; the 40 px hitbox margin stays fixed** (user decision, recorded per run as `metadata.hitbox_margin_px`). Hub review of every source diff and `report_follow.py`: `has_selection` + four BaseTask hooks leave the three selection tasks on their old path; per-frame accounting (invalid frames count for nothing, 250 ms frame cap, followed = 50 % of valid time, never a timeout); pursuit gain (saccades padded by one sample, whole 100 ms window clean, bounce exclusion, 3 deg limit, median, None under 0.5 s); legacy Follow & Click folders keep their old report (`on_target_ms` absent); `REPORT_VERSION` 3; `initial_live_values` still carries `dwell.jitter_tolerance_px` for every task, so the metadata field is always written. Hub full pytest in the main tree: **2487 collected, exit 0 (2485 passed, 2 skipped, 0 failed)**; the README's count stands. Committed on the user's OK; worktree fast-forwarded to the commit. The Fable design work (docs/design, `00a28bb`..`e81bdb6`) was done the same evening and has no code effect yet. Next: step 4.
