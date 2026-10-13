---
name: SPEC-app-drawn-calibration
title: Grid 3-style calibration drawn by the app (own icons, glide, results map, Improve calibration) with Gazepoint Control's window as fallback
status: IMPLEMENTED 2026-10-13 - plan steps 3-4 DONE (hub-reviewed, pytest 4310: 4305 + 5 worktree baseline; device-free live check against real Gazepoint Control PASSED); GP3 HD accuracy check (A8, A9, A10) pending
created: 2026-10-13
last_updated: 2026-10-13
next_step: plan step 5 on the GP3 HD with the user as subject: P4 accuracy App vs Control screen per speed preset (Fast hold), A8-A10, Show Monitor with a real head; check why point 1 took ~1 s longer than DELAY + TIMEOUT
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

**Status: IMPLEMENTED 2026-10-13 (hub-reviewed, device-free check passed); the GP3 HD accuracy check is pending.**

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
   (C2, C10). The mouse cursor stays visible. The tracked monitor is the screen the Setup window
   is on (accepted 2026-10-13, hub answer); whether that is the monitor Control tracks on a
   multi-monitor PC is checked live (A10).
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
   until `CALIB_RESULT` (C11). The result (the scores, the map and the badge's mean error) comes
   from `CALIB_RESULT` only: `CALIBRATE_RESULT_SUMMARY` is retained state (feasibility 6.1) and is
   never asked for. A run is valid when any eye of any point was valid; the mean error in px is
   the mean over the valid eyes of every point.
6. Then the **results map** (4.4) appears in the same window.
7. **Back** closes the window and returns to Setup. The badge and details update exactly as
   today. **Improve calibration** re-runs all points (Q2). **Show Monitor** opens the
   head-position widget over the map (4.5).
8. **Esc / X** during a run (glide, hold or processing) cancels: it sends `CALIBRATE_START STATE="0"`,
   then `CALIBRATE_SHOW STATE="0"` to restore, and leaves the previous calibration state
   untouched. **On the results map (and Show Monitor) Esc / X is Back** and keeps the new result:
   Control already holds the new calibration, so discarding it would make the app disagree with
   the tracker (hub answer, 2026-10-13).

### 4.2 Fallback to Control's window (Q5)

- If no `CALIB_START_PT` arrives within DELAY + 1 s of `CALIBRATE_START`, or any later point is
  more than DELAY + TIMEOUT + 1 s late, the app:
  1. stops (`CALIBRATE_START STATE="0"`);
  2. closes its window;
  3. re-runs the calibration once with `CALIBRATE_SHOW STATE="1"`, which is exactly today's path;
  4. shows the alert "The app's calibration screen did not respond; Gazepoint Control's own
     calibration was used."
- The fallback and its reason are written to `_diagnostics/calibration_timing.jsonl`
  (`mode: app_drawn | control | control_fallback`; `control` is the operator's own choice of
  Gazepoint Control's window).
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

- `calibration.json` adds: `mode` (`app_drawn`, `control` for the operator's own choice of
  Gazepoint Control's window, or `control_fallback`), speed, DELAY, TIMEOUT,
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
| A4 | Esc/X during a run cancels, sends `CALIBRATE_START STATE="0"`, and leaves the old calibration and badge unchanged; on the results map (and Show Monitor) Esc/X is Back and keeps the new result | unit test |
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
2. **DONE 2026-10-13 - Icons:** generate 6, then the user approves them (they can be made in parallel with step 3).
3. **DONE 2026-10-13 -** Implement 4.1-4.5 and 4.7 with the fake Control.
4. **DONE 2026-10-13 -** Hub review and the full pytest.
5. Live on the GP3 HD, with the user as subject:
   - P4 (the speed presets against Control's own window);
   - A8-A10;
   - Show Monitor with the real head data.
6. Commit on the user's OK.

**Depends on:** SPEC-gaze-stability-and-positioning part B (the widget), for Show Monitor only.
Steps 1-4 can run before it.

## 8. Impl log

- **2026-10-13 - plan step 3 (4.1-4.7, A1-A7, A10a, A10b, A12, A13 by test) - `spec-implementer`, model `claude-sonnet-5-5`, worktree `calib-app-drawn` at `0b808b6`. No commit, nothing staged, no device, no app launch.**
  - **Engine (Qt-free, new):**
    - `src/engine/calibration_settings.py`: the settings (screen, points, speed, target, size, background), the speed pairs (D1), the size presets in degrees (4.3b), the Grid 3 layout (D5), icon paths, load/save per PC through the local state, `settings_from_config` (A12), the per-point score and band (Q1), `geometry_for_screen`, and the `calibration.json` record helpers (`record_for`, `with_improve_runs`, `annotate_result`).
    - `src/engine/calibration_motion.py`: `TargetMotion`, the icon's pose as a pure function of the clock (glide, shrink, hold, wobble); `schedule(delay)` guarantees the hold starts no later than `DELAY` after the record.
    - `src/engine/calibration_run.py`: `run_calibration()`: reads Control's DELAY/TIMEOUT, sends `CALIBRATE_SHOW 0`, the pair, `CLEAR`, `ADDPOINT` x N, `START`; reads the `CAL` records itself and hands `start_point` / `result_point` / `processing` / `fallback` events to the window; ignores a `PT` above the count; ends only on `CALIB_RESULT` (see the 2026-10-13 follow-up: the result comes from it alone); fallback to Control's window (4.2), Esc/X stop (`CALIBRATE_START 0`, `CALIBRATE_SHOW 0`), restore of DELAY/TIMEOUT, and the `calibration_timing.jsonl` record. The Control screen runs through the same function (the speed pair and the read/restore apply to both screens).
    - `src/engine/calibration.py` (additive): `CalibrationResult.record`, the record keys written into and read from `calibration.json`, and `Calibration(mode=, timing_extra=)` so its timing record says `mode` (`control` / `control_fallback`) and the fallback reason.
  - **UI (new):** `src/ui/calibration_stage.py` (icon drawing, processing text and dots), `calibration_map.py` (results map), `calibration_window.py` (frameless full-screen window, five states, Esc/x, Show Monitor reusing `HeadPositionPanel`), `calibration_flow.py` (window and runs, Improve = full re-run, Back, cancel, fallback outcome, window hold-time diagnostics), `calibration_settings_panel.py` (the Setup card's controls).
  - **UI (edited):** `src/ui/setup_page.py` (the point spin and the tick box replaced by the panel; `start_calibration()`, the thread and flow plumbing, settings saved per PC, `_busy()` includes the open window), `src/ui/start_test_page.py` (Calibrate button, fallback alert), `src/ui/run_flow.py` (Calibrate wiring).
  - **Tools/docs:** `tools/fake_gazepoint_server.py` answers a calibration with `CAL` records (timed by DELAY + TIMEOUT + 20 ms, honouring `CALIBRATE_SHOW/CLEAR/RESET/ADDPOINT/START`, GET/SET of `CALIBRATE_DELAY`/`TIMEOUT`; knobs `silent_runs`, `extra_result_pt`, `valid_eyes`, `eye_offset`); `docs/DATA_SCHEMA.md` (new "calibration.json" section and the timing-log fields; the file is `docs/DATA_SCHEMA.md`, not the repo root).
  - **Tests added (102):** `tests/test_calibration_run.py` (17: A1 order and hold rule, A2, A3, A4, A10a at the socket), `tests/test_calibration_settings.py` (35: A5, A7 record, A10b maths, A12), `tests/test_calibration_window.py` (30: states, glide and hold with a fake clock, sizes, Esc/x, results map colours, Show Monitor), `tests/test_calibration_flow.py` (20: the real thread against the fake Control from the Setup page and the Start page: A3, A4, A6, A7, A10b greying, A12, A13); helpers in `tests/calibration_fixtures.py`.
  - **Existing tests edited (intent unchanged):** `test_audit_setup.py`, `test_audit_close.py`, `test_preview_gaze_pointer.py` (their stand-ins for `Calibration` now run on the Gazepoint Control screen, the App screen being the new default), `test_full_width_layout.py` and `test_setup_phase2.py` (`point_count_spin` is now `points_combo`, a third-width field), `test_start_page_phase2.py` (the Start page has one more alert), `test_setup_subject_id.py` (the Calibration screen radios are not a "folder name choice").
  - **pytest** (4 parallel processes, JUnit counts): 4271 tests, 4266 passed, **5 failed, all the known baseline** (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`, `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults` x4: alpha 0.35 vs 0.22 from the local `default.yaml`). One extra failure of that run, `test_setup_subject_id::test_there_is_no_folder_name_choice_and_no_folder_line`, was caused by the new radio group and fixed (the test now ignores the Calibration screen radios); it passes.
  - **Choices inside the SPEC (not deviations):** the hold is scheduled up to 50 ms before `DELAY` ends (`min(50 ms, 25 % of DELAY)`), so the icon is still when Control's first sample is taken even if the record was read a few ms late; the glide then shrink split is `DELAY` minus that margin; the 9-point extras follow the old pool's order (top, right, bottom, left at 10 / 50 / 90 %); the background colours are white `#FFFFFF`, black `#000000`, grey `#808080` (not UI tokens: stimulus colours); (first version asked `CALIBRATE_RESULT_SUMMARY` once after `CALIB_RESULT`: replaced in the follow-up below;) `grace_s` and `result_wait_s` are 1 s and 5 s; the window opens on the Setup window's screen (see question 4); the window is parented to the Setup page so it stays above the dashboard.
  - **Deviations from the SPEC:** none.
  - **Left undone (the hub's):** A8, A9, A10 live on the GP3 HD (including the real Fast hold from probe P4); a look at the real fonts (the offscreen platform has no Segoe UI, so the digits on the map were checked by colour and position only); `tools/fake_gazepoint_server.py` is at 499 lines.

- **2026-10-13 (follow-up) - hub answers to the section 9 questions applied; `spec-implementer`, `claude-sonnet-5-5`; no commit.**
  - **The result comes from `CALIB_RESULT` only.** The first version asked `CALIBRATE_RESULT_SUMMARY` once after `CALIB_RESULT` and took `mean_error_px` (the badge's number) and `valid` from it, which is retained state (feasibility 6.1): fixed. `run_calibration()` no longer sends that query at all. For an app-drawn run `valid` is "any eye of any point valid" and `mean_error_px` is computed from `CALIB_RESULT` (`calibration_settings.mean_error_px`: mean over the valid eyes of every point, in monitor px, added by `annotate_result`); the scores and the map were already from `CALIB_RESULT`. With no `CALIB_RESULT` (5 s after the last point's DELAY + TIMEOUT) there is no result: the window closes and Setup says "Calibration did not produce a valid result". The Gazepoint Control screen and the fallback keep today's path and its own `AVE_ERROR`.
  - **Esc / x on the results map and Show Monitor is Back** (keeps the result, sends nothing); during a run it still cancels. `CalibrationFlow._on_cancel` decides; the `stop` hook and `stop_calibration()` are gone.
  - `mode: "control"` listed in 4.2, 4.7 and `docs/DATA_SCHEMA.md`; the tracked-monitor note is in 4.1 step 1.
  - **Tests:** 110 in the four calibration files (8 more): the summary is never asked for and the result and mean error come from `CALIB_RESULT`, no valid eye gives an invalid result with grey points, no `CALIB_RESULT` gives no result and no fallback, `mean_error_px` and the modes, Esc / x / window close on the map are Back, Esc during Show Monitor is Back, a no-valid-eye run through the window and Back.

## 9. Open decisions (for the user)

All answered by the user 2026-10-13 and recorded in section 2: D1, D2, D3, D5 (first round), D4 and D6 (after a longer explanation).

Implementer open questions (all answered by the hub, 2026-10-13):

- **2026-10-13** - **Esc / x on the results map** (4.1 step 8, A4). *Answered:* it must not discard. On the results map and Show Monitor, Esc / x is Back and keeps the new result, because Control already holds the new calibration; during glide, hold and processing it still cancels. Applied in 4.1 step 8, A4 and `CalibrationFlow._on_cancel`.
- **2026-10-13** - **`calibration.show: false`.** *Answered:* accepted: any `show` value gives the App screen (no picture at all is no longer offered); `points` of the block still sets the Points default.
- **2026-10-13** - **`mode` for the operator's own choice of Gazepoint Control.** *Answered:* accepted: `"control"`; the values are `app_drawn | control | control_fallback` (4.2, 4.7, `docs/DATA_SCHEMA.md`).
- **2026-10-13** - **Which monitor is "the tracked monitor".** *Answered:* accepted for now: the screen the Setup window is on; multi-monitor placement is checked live (A10). Noted in 4.1 step 1.
- **2026-10-13** - **Fallback alert wording.** *Answered:* keep the 4.2 text (`calibration_run.FALLBACK_ALERT`); the hub aligns the wireframe.

## 10. Log

- **2026-10-13** - Draft written by the hub from the feasibility study (verdicts C1-C19, probes
  P1-P3, answers Q1-Q8) on the user's request ("proceed all"), while
  SPEC-gaze-stability-and-positioning parts A and B are being implemented. Open: D1-D6, then the
  wireframe. Device probes P4/P5 are folded into plan step 5.
- **2026-10-13** - User answered D1 (speed presets as proposed), D2 (results map in the calibration window), D3 (bee, star, ball, fish, flower, car) and D5 (Grid 3 layout). D4 and D6: the user asked for more explanation first.
- **2026-10-13** - After the explanation, the user answered D4 (Calibrate button on the Start-test page, next to Practice) and D6 (replace the tick box with "Calibration screen: App / Gazepoint Control", default App). All open decisions are closed. Next: the wireframe.
- **2026-10-13** - The user asked whether Grid 3's Size and Speed can be set through the Gazepoint API. Answer: Speed yes (`CALIBRATE_DELAY` / `CALIBRATE_TIMEOUT`, proven by probe P3); Size no (no API command), but it is feasible because the app draws the target. The user accepted both (D7, D8): new section 4.3b with the preset values (Size in degrees), Speed also applies to the Gazepoint Control screen, and Control's DELAY/TIMEOUT are restored after a run. Acceptance A10a/A10b added. Wireframe approved; plan step 1 DONE; SPEC approved.
- **2026-10-13** - Plan step 2 DONE: six icons (bee, star, ball, fish, flower, car) generated with `mcp-image-openrouter` (`google/gemini-3.1-flash-image`, bee as the style anchor), keyed with `tools/chroma_key.py`, 384 x 384, in `configs/assets/calibration/` with `ASSETS.md`; raws in `reference/` (not shipped). Grid 3's own bee is compiled into its EyeGaze DLLs (no loose files) and is licensed art (U2), so it was not used. All six approved by the user.
- **2026-10-13** - Hub review, integration and device-free live check. Implemented by `calib-app-drawn` (Impl log section 8); hub answers to its Q1-Q5 applied (Esc/X on the results map = Back, `mode` app_drawn | control | control_fallback, tracked monitor = the Setup window's screen, checked live at A10). Hub review caught that the first version took the badge's mean error and validity from `CALIBRATE_RESULT_SUMMARY` (retained state, feasibility 6.1); fixed: the result comes from `CALIB_RESULT` only and the summary is never queried (test added). Combined with the gaze revision 4.9 on `0b808b6`; full pytest (JUnit) 4310 tests, 4305 passed, 5 failed = the known fresh-worktree baseline (skip-worktree `default.yaml`, alpha 0.35 vs 0.22). **Device-free live check** (app launched from the integration worktree with the qt-mcp probe, real Gazepoint Control on 4242 with the GP3 HD attached but no subject): Setup Calibration card and settings render as the wireframe; App calibration ran end to end (5 points, results map with grey "-" circles and "5 points need attention", no eyes), Show Monitor overlays the live head panel, Improve re-runs, Esc during a run cancels (`cancelled` after 2 points) and leaves Setup "Not calibrated". `calibration_timing.jsonl`: Control took DELAY 0.8 / TIMEOUT 1.0; points 2-5 lasted 1.83-1.87 s, point 1 2.77 s (about 1 s extra, harmless because the icon holds until `CALIB_RESULT_PT`; to watch on the device); the window record shows the hold painted at 0.75 s (max 0.766 s) of every point, before DELAY 0.8 s; `improve_runs` 2. After closing the app Control reported DELAY 0.50, TIMEOUT 1.50 (its own values, restored), `CALIBRATE_SHOW` 0, `AAC_FILTER` 15; app log clean. Not checked live: the fallback and the Gazepoint Control screen (kept off the real Control, which has stuck after its own-window calibration before; covered by tests with the fake Control), the Start-page Calibrate button (tests, A13), accuracy (A8, A9 need a subject). Committed on the user's overnight authorisation (commit if green, no push).
