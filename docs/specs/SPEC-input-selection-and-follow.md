---
name: SPEC-input-selection-and-follow
title: Pointer (Gaze / Mouse) and Selection (Dwell / Switch) per test; Follow the Target without a click
status: approved 2026-10-07 (I1-I12, H1-H10)
created: 2026-10-07
last_updated: 2026-10-07
next_step: after the compass SPEC's P9c pass (step 0), /spec-run this SPEC on feature/compass-task-flow from step 1 (wireframes, WF gate)
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
| 0 | Parent SPEC P9c (V1-V5) implemented and checked first, so the report work below builds on it | — |
| 1 | Wireframes: `task-config` (Input card, renamed Dwell card, Glow, Follow timing), `report-summary` / `report-detailed` (Switch columns, Follow block), `start-test` (Mouse note) | **WF gate** |
| 2 | Engine: settings keys + registry/page data (H1, H3), `SwitchInput` canvas press, cursor park/hide, BaseTask switch rules + events + `clicks` / `click_errors`, pointer/recording split + `pointer_stream.csv` + run gate (H4, H5) | — |
| 3 | Follow: task rewrite (4.4), live metrics + columns, glow + end sound; analysis (`report_follow.py`: gain, catch-up saccades) + `report.json` block | — |
| 4 | UI: config page Input card, report tables/summary/map/legend + PDF for Switch and Follow, report_config labels | — |
| 5 | Review + live check A10 with the user and the switch; commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-07** — Created from the doctor's feedback (input method; Follow without a click),
  relayed by the user after the P9 real-device run. Compass guide read (Aim Selection Method,
  Clicks, Switch test). Parallel search on gaze + switch vs dwell and on smooth-pursuit metrics
  (§3.2). User decisions I1-I12 taken in this session (three rounds of questions). Hub decisions
  H1-H10 proposed, awaiting approval.
- **2026-10-07** — The user approved H1-H10 as written. SPEC committed on `feature/compass-task-flow`. Next: the compass SPEC's P9c pass (step 0), then step 1 here.
