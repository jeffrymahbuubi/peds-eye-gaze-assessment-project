---
name: SPEC-app-drawn-calibration
title: Grid 3-style calibration drawn by the app (own icons, glide, results map, Improve calibration) with Gazepoint Control's window as fallback
status: APPROVED 2026-10-13 - SPEC + wireframe approved by the user (D1-D8); plan step 1 DONE
created: 2026-10-13
last_updated: 2026-10-13
next_step: plan step 2 (icons) and step 3 (implementation), after SPEC-gaze-stability-and-positioning parts A and B are merged (shared Setup / Start-test files)
related:
  - SPEC-grid3-calibration-parklife-feasibility.md (verdicts C1-C19, probes P1-P3 PASSED 6.1, answers Q1-Q8 7.1)
  - SPEC-gaze-stability-and-positioning.md (head-position widget, reused here as "Show Monitor")
  - docs/calibration-video/README.md (frame-timed Grid 3 calibration, observable requirements checklist)
  - SPEC-gui-audit-2026-09-10.md (CALIB_RESULT is the only valid completion marker)
  - SPEC-calibration-result-timeout.md (reader-thread race, _diagnostics/calibration_timing.jsonl)
  - SPEC-display-scaling-cursor-accuracy.md (physical px on scaled displays)
  - SPEC-scene-cause-effect-task.md (art + chroma-key pipeline, reused for the icons)
---

# SPEC-app-drawn-calibration

**Status: APPROVED 2026-10-13 (SPEC + wireframe). Branch `feature/compass-task-flow` at `5a035d7`.**

## 1. Origin

- The feasibility study (2026-10-10) asked whether the app can copy Grid 3's eye-gaze calibration
  on the GP3 HD. User decision U1 asked for a **full replica**: the stimulus, settings, results,
  Improve calibration, and the track-status widget. U2 asked for a **built-in set of our own
  icons**.
- Probes P1-P3 (2026-10-11, Gazepoint Control without a camera) proved the message flow. With
  `CALIBRATE_SHOW STATE="0"`, Control hides its window and still sends `CALIB_START_PT` /
  `CALIB_RESULT_PT` / `CALIB_RESULT` in the order and at the positions sent. Each point lasts
  DELAY + TIMEOUT, plus 10-70 ms.
- On 2026-10-13 the user asked the hub to draft this SPEC in parallel with
  SPEC-gaze-stability-and-positioning.

## 2. Decisions already made (feasibility 7.1, user 2026-10-10)

| # | Decision |
|---|---|
| Q1 | Per-point score = round(100 x max(0, 1 - error_deg / 3)). Green when the error is 1 deg or less, amber up to 2 deg, red above 2 deg or with no valid eye. |
| Q2 | "Improve calibration" = **full re-run** (I-A). The results map marks the weak points. |
| Q3 | **No stepped mode.** Continuous only. |
| Q4 | Track-status colours = distance + both eyes. Now defined in SPEC-gaze-stability-and-positioning 4.6. |
| Q5 | The app-drawn calibration **replaces** the Setup page calibration. Control's own window is used automatically only if the app-drawn run fails. |
| Q6 | **AI-generated icons** (image MCP, then a flat key colour + `tools/chroma_key.py`). The user approves every icon. |
| Q7 | English text now; the design must allow Traditional Chinese later. Calibration itself is silent (C10). |
| D1 | **Speed presets** (glide / hold): Slow 1.0 / 1.5 s, Normal 0.8 / 1.0 s, Fast 1.8 / 0.4 s. The final Fast hold is confirmed by probe P4 (user, 2026-10-13). |
| D2 | **Results map in the full-screen calibration window**, Grid 3 style (user, 2026-10-13). |
| D3 | **Icons: bee, star, ball, fish, flower, car** (user, 2026-10-13). |
| D4 | **Calibrate button on the Start-test page**, next to Practice (C19). It runs the same calibration and returns to the Start page; the new result replaces the subject's calibration for later tests (user, 2026-10-13). |
| D5 | **Grid 3 layout:** 10 % / 90 % insets in the order TL, BR, TR, BL, C; the 9-point layout adds the edge midpoints at 10 / 50 / 90 % (user, 2026-10-13). |
| D6 | **The "Show calibration window" tick box becomes a choice "Calibration screen: App (Grid 3 style) / Gazepoint Control"**, default App. The automatic fallback (4.2) stays (user, 2026-10-13). |
| D7 | **Speed is set through the Gazepoint API** (`CALIBRATE_DELAY` = glide, `CALIBRATE_TIMEOUT` = hold), as in 4.3b (user, 2026-10-13). |
| D8 | **Size is drawn by the app**: the API has no target-size command, so it applies to the App screen only (4.3b) (user, 2026-10-13). |

## 3. Current code (as of `5a035d7`)

- `src/engine/calibration.py` `Calibration.run()`:
  - sends DELAY/TIMEOUT (if set), `CALIBRATE_SHOW` (from `calibration.show`), and the points via
    `CALIBRATE_RESET` (5) or `CLEAR` + `ADDPOINT`;
  - then sends `CALIBRATE_START`, polls, and waits for the one-time `CALIB_RESULT`;
  - reads `CALIB_START_PT` / `CALIB_RESULT_PT` and **ignores** them.
- Point pool: 5 points at the vendor 0.15 / 0.85 margins plus the centre. The 9-point layout adds
  the edge midpoints. Control rejects fewer than 4 points.
- Setup Calibration card: point count, a "Show calibration window" tick box, Do Calibration,
  Load Calibration File, View Calibration Details (a per-point, per-eye table with "Error (px)"),
  and the badge "Calibrated, 5 points, 1.8°".
- Control's own window is the only stimulus today; the app draws nothing.

## 4. Design

### 4.1 Flow

1. **Do Calibration** on Setup opens a frameless full-screen **calibration window** on the tracked
   monitor, covering the taskbar. It has a plain background and a faint close "X" top right
   (C2, C10). The mouse cursor stays visible.
2. The engine sends `CALIBRATE_SHOW STATE="0"`, `CALIBRATE_DELAY` and `CALIBRATE_TIMEOUT` (from the
   speed, D1), `CALIBRATE_CLEAR`, `ADDPOINT` x N (D5 layout and order), then `CALIBRATE_START`.
3. On each `CALIB_START_PT` (PT, CALX, CALY), the window animates the icon from its current spot
   to (CALX, CALY):
   - eased glide for DELAY seconds, large while moving (about 5-6.5 % of the screen width);
   - then it shrinks to the small size (about 1.5-2 %) and **holds still** until that point's
     `CALIB_RESULT_PT`. The hold must start no later than DELAY after `CALIB_START_PT`, because
     sampling begins then (feasibility 4.3 risk).
   - Before the first point, the icon enters from the top-left corner (video).
4. A `CALIB_RESULT_PT` whose PT is above the point count is ignored (feasibility 6.1).
5. After the last point, the window shows "**Processing calibration results**" with a spinner
   until `CALIB_RESULT` (C11).
6. Then the **results map** (4.4) appears in the same window.
7. **Back** closes the window and returns to Setup. The badge and details update exactly as
   today. **Improve calibration** re-runs all points (Q2). **Show Monitor** opens the
   head-position widget over the map (4.5).
8. **Esc / X** cancels at any point: it sends `CALIBRATE_START STATE="0"`, then
   `CALIBRATE_SHOW STATE="0"` to restore, and leaves the previous calibration state untouched.

### 4.2 Fallback to Control's window (Q5)

- If no `CALIB_START_PT` arrives within DELAY + 1 s of `CALIBRATE_START`, or any later point is
  more than DELAY + TIMEOUT + 1 s late, the app:
  1. stops (`CALIBRATE_START STATE="0"`);
  2. closes its window;
  3. re-runs the calibration once with `CALIBRATE_SHOW STATE="1"`, which is exactly today's path;
  4. shows the alert "The app's calibration screen did not respond; Gazepoint Control's own
     calibration was used."
- The fallback and its reason are written to `_diagnostics/calibration_timing.jsonl`
  (`mode: app_drawn | control_fallback`).
- The **"Show calibration window" tick box is replaced** by the setting "Calibration screen":
  **App (Grid 3 style)** (default) or **Gazepoint Control** (D6). With Gazepoint Control, the run
  is exactly today's path (`CALIBRATE_SHOW STATE="1"`), and none of 4.1's window, 4.4's map or
  4.6's icons apply; the Setup details table still updates. Calibrating with no picture at all
  (today's unticked box) is no longer offered.

### 4.3 Settings (C6, C7, C8)

The settings sit on the Setup Calibration card, above Do Calibration:

| Setting | Values | Default |
|---|---|---|
| Calibration screen | App (Grid 3 style) / Gazepoint Control (D6) | App |
| Points | 5 / 9 (Control rejects fewer than 4; Grid 3's 1-3 are not offered) | 5 |
| Speed | Slow / Normal / Fast (D1) | Normal |
| Target | Built-in icon set, a picker with thumbnails (D3) | the first icon |
| Target size | Small / Normal / Large (4.3b) | Normal |
| Background | White / Black / Grey | White |

- All of these are saved per PC (in local state, like the Control address) and written into
  `calibration.json` with each result.

### 4.3b How Speed and Size reach the calibration (D7, D8)

**Speed: Gazepoint API.** Each preset is a pair sent before `CALIBRATE_START`:

| Preset | `CALIBRATE_DELAY` (glide, before sampling) | `CALIBRATE_TIMEOUT` (hold, sampling) | About 5 points |
|---|---|---|---|
| Slow | 1.0 s | 1.5 s | 12.5 s |
| Normal | 0.8 s | 1.0 s | 9 s |
| Fast | 1.8 s | 0.4 s (confirmed or raised at probe P4) | 11 s |

- API 3.5 and 3.6: TIMEOUT > 0 and DELAY >= 0, both read/write floats. Probe P3 measured each
  point at DELAY + TIMEOUT + 10-70 ms.
- The same pair applies to the **Gazepoint Control** screen too, so Speed stays active for both
  screens. *This corrects the wireframe note that greyed Speed for Control; the wireframe is fixed
  to match.*
- Before the run, the engine reads Control's current DELAY and TIMEOUT (`GET`), and restores them
  afterwards. The same rule as AAC_FILTER in the other SPEC: other software on the PC keeps its
  settings.
- Fast has the accuracy risk: a short hold gives Control fewer samples per point. A9 compares each
  preset's mean error with Control's default on the GP3 HD. If Fast is more than 0.3 deg worse,
  its hold is raised (0.6 s, then 0.8 s) and the value is written back here.

**Size: drawn by the app.** The Open Gaze API has no command for the target's size or look
(Control's only option is hand-placed `CalibPoint<n>.png` files in `Documents\Gazepoint`, which
the app does not use). So Size, Target and Background apply to the **App** screen only and are
greyed for Gazepoint Control.

- Sizes are in **degrees of visual angle**, converted to pixels with the existing geometry
  (`viewing_distance_mm`, screen mm per px), so the icon looks the same on any monitor:

| Preset | Gliding (large) | Holding (small) |
|---|---|---|
| Small | 2.2 deg | 0.6 deg |
| Normal | 3.0 deg | 0.8 deg |
| Large | 4.0 deg | 1.0 deg |

- At 1920 x 1080 on a 24-inch screen at 65 cm, Normal is about 6 % and 1.6 % of the screen width,
  matching Grid 3's measured ~5-6.5 % and ~1.5-2 %.
- The hold size stays small on purpose: it is the point the child must fixate, and Control
  assumes the gaze is on the point's centre. Size never changes what Control measures; it changes
  only what the child sees.

### 4.3a Calibrate from the Start-test page (D4, C19)

- A **Calibrate** button sits next to Practice (secondary tier). It is shown for gaze tests only
  and is enabled while the tracker is connected.
- It runs the same calibration with the Setup card's settings (4.3), including the results map,
  Improve calibration and Show Monitor. **Back** returns to the Start page, not to Setup.
- The result replaces the subject's calibration for every later test in the sitting, exactly as
  a Setup calibration does, and the Setup badge updates.
- If the Start page was blocked only by "No calibration yet", a successful calibration clears the
  blocker (it is re-checked every second already).
- The Calibrate button is not offered during Practice or a run.

### 4.4 Results map (C12, C13)

- The screen shows a rectangle for the monitor with one circle per point at its position. Each
  circle holds its 0-100 integer score (Q1), coloured green, amber or red (design tokens). A
  point with no valid eye shows a grey circle with "-".
- The error is measured as today (`per_point_errors_px`), converted with `geometry.px_to_deg()`,
  and averaged over the valid eyes.
- There is no overall score on the map, as in Grid 3. The Setup badge keeps "5 points, 1.8°".
- **Weak points** (amber or red) get a thicker ring. The line under the map reads
  "2 points need attention. Check the head position, then Improve calibration." (Q2)
- Buttons: **Improve calibration** (bottom left), **Show Monitor** (next to it), **Back** (bottom
  right).

### 4.5 Show Monitor (C17, C18)

- It shows the head-position widget from SPEC-gaze-stability-and-positioning (face, Close-Far
  bar, hint) as a panel over the results map. Show Monitor toggles it.
- This SPEC depends on that widget (part B of that SPEC).

### 4.6 Icons (C4, U2, Q6)

- Six static icons (D3). They are made with the existing scene-art pipeline: image MCP on #00FF00,
  then `tools/chroma_key.py` to transparent PNG.
- They are stored in `configs/assets/calibration/`, next to the scene art in `configs/assets/scenes/park/`, with an `ASSETS.md` source record like the scene's. The user
  approves each one.
- A gentle motion keeps the icon interesting: a slow wobble of ±8° while gliding, and still
  during the hold so the gaze can settle.

### 4.7 Recording

- `calibration.json` adds: `mode` (`app_drawn` or `control_fallback`), speed, DELAY, TIMEOUT,
  icon id, size, background, layout, per-point `score` and `error_deg`, and `improve_runs` (the
  number of re-runs before Back).
- `_diagnostics/calibration_timing.jsonl` adds per-point times (start, result, glide end, hold
  start) to verify the hold rule in 4.1.

## 5. Scope

**In:**
- sections 4.1-4.7;
- the new speed/target/size/background settings;
- the Calibration screen choice replacing the show-window tick box (D6);
- the Start-test Calibrate button (D4);
- tests with a fake Control that sends `CAL` records (extend `tools/fake_gazepoint_server.py`);
- `DATA_SCHEMA.md`.

**Out:**
- stepped mode (Q3);
- touch-a-point re-run (C15, not possible);
- fewer than 4 points (C8);
- calibrating during a run (the Start-test button, D4, is before a run only);
- a sound during calibration;
- animated GIF icons;
- the head-position widget itself (the other SPEC).

## 6. Acceptance criteria

| # | Criterion | Checked by |
|---|---|---|
| A1 | With the fake Control, a 5-point run draws the icon at each CALX/CALY in the sent order, and the hold starts no later than DELAY after each `CALIB_START_PT` | unit test with a fake clock |
| A2 | Extra `CALIB_RESULT_PT` above the point count is ignored; only `CALIB_RESULT` ends the run | unit test |
| A3 | No `CAL` record within DELAY + 1 s triggers the fallback: a Control-window run, an alert, and a diagnostics record | unit test |
| A4 | Esc/X cancels, sends `CALIBRATE_START STATE="0"`, and leaves the old calibration and badge unchanged | unit test |
| A5 | Scores and colours follow Q1 for known per-eye errors; no valid eye gives grey "-" | unit test |
| A6 | Improve calibration re-runs all points and replaces the result; `improve_runs` counts | unit test |
| A7 | Settings persist per PC and land in `calibration.json` | unit test |
| A8 | On the GP3 HD: a hidden-window run gives `VALID_POINTS` = N, and accuracy matches Control's own window within 0.3 deg mean error (probe P4) | live, user as subject |
| A9 | On the GP3 HD: the speed presets give a usable calibration; the Fast hold is chosen from P4 | live |
| A10a | Speed presets send the DELAY/TIMEOUT pairs of 4.3b for both screens; Control's own values are read before and restored after | unit test with the fake Control |
| A10b | Size presets draw the icon at the 4.3b degrees (px from the geometry); Size/Target/Background are greyed for Gazepoint Control | unit test |
| A10 | Display scaling 125 % / 150 %: the icon lands on Control's point (physical px) | live or offscreen with a scale factor |
| A11 | Full pytest stays green | hub rerun |
| A12 | Calibration screen = Gazepoint Control runs today's path; App is the default; the old `calibration.show` value maps to the new setting (`true` -> App) | unit test |
| A13 | The Start-test Calibrate button (gaze tests only) runs the calibration, Back returns to the Start page, and the blocker clears on success | unit test + live |

## 7. Plan

1. **DONE 2026-10-13 - Wireframe:** the Setup Calibration card settings (with the Calibration screen choice); the Start-test Calibrate button; the calibration window states (glide, hold,
   processing, results map, Show Monitor). User GATE 1.
2. Icons: generate 6, then the user approves them (they can be made in parallel with step 3).
3. Implement 4.1-4.5 and 4.7 with the fake Control.
4. Hub review and the full pytest.
5. Live on the GP3 HD, with the user as subject:
   - P4 (the speed presets against Control's own window);
   - A8-A10;
   - Show Monitor with the real head data.
6. Commit on the user's OK.

**Depends on:** SPEC-gaze-stability-and-positioning part B (the widget), for Show Monitor only.
Steps 1-4 can run before it.

## 8. Impl log

(empty)

## 9. Open decisions (for the user)

All answered by the user 2026-10-13 and recorded in section 2: D1, D2, D3, D5 (first round), D4 and D6 (after a longer explanation).

Implementer questions: (none yet)

## 10. Log

- **2026-10-13** - Draft written by the hub from the feasibility study (verdicts C1-C19, probes
  P1-P3, answers Q1-Q8) on the user's request ("proceed all"), while
  SPEC-gaze-stability-and-positioning parts A and B are being implemented. Open: D1-D6, then the
  wireframe. Device probes P4/P5 are folded into plan step 5.
- **2026-10-13** - User answered D1 (speed presets as proposed), D2 (results map in the calibration window), D3 (bee, star, ball, fish, flower, car) and D5 (Grid 3 layout). D4 and D6: the user asked for more explanation first.
- **2026-10-13** - After the explanation, the user answered D4 (Calibrate button on the Start-test page, next to Practice) and D6 (replace the tick box with "Calibration screen: App / Gazepoint Control", default App). All open decisions are closed. Next: the wireframe.
- **2026-10-13** - The user asked whether Grid 3's Size and Speed can be set through the Gazepoint API. Answer: Speed yes (`CALIBRATE_DELAY` / `CALIBRATE_TIMEOUT`, proven by probe P3); Size no (no API command), but it is feasible because the app draws the target. The user accepted both (D7, D8): new section 4.3b with the preset values (Size in degrees), Speed also applies to the Gazepoint Control screen, and Control's DELAY/TIMEOUT are restored after a run. Acceptance A10a/A10b added. Wireframe approved; plan step 1 DONE; SPEC approved.
