---
name: SPEC-app-drawn-calibration
title: Grid 3-style calibration drawn by the app (own icons, glide, results map, Improve calibration) with Gazepoint Control's window as fallback
status: REVISION 4.9 (Hsieh feedback: slower Slow, no shrink) APPROVED 2026-10-22 (section 9 Q1, Q2, Q4 answered), wireframe drawn, awaiting the wireframe look (GATE 1); revision 4.8 IMPLEMENTED + LIVE-CHECKED 2026-10-14 (A14-A17 PASSED); first version `8db9e56`
created: 2026-10-13
last_updated: 2026-10-22
next_step: 4.9 - the user looks at the wireframe (calibration-window State 2, setup Speed list; GATE 1), then spec-implementer (plan step 10); still open from the first version: Fast-speed hold (A9), display scaling (A10), multi-monitor placement
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

**Status: revision 4.9 (Hsieh feedback) DESIGNED 2026-10-22, awaiting user approval (section 9, questions 1-4); revision 4.8 IMPLEMENTED and live-checked 2026-10-14 (A14-A17 passed); the first version is IMPLEMENTED 2026-10-13 (`8db9e56`). Still open: A9, A10, multi-monitor placement.**

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
| D9 | **Centre point first** (amends D5's order): C, TL, BR, TR, BL; the 9-point layout then adds the edge midpoints as before. Positions stay at 10 % / 90 % (user, 2026-10-14, 4.8). |
| D10 | **Check accuracy view after the results map** (a copy of Gazepoint Control's after-calibration window: target circles plus a live green gaze trail), opened by a **Check accuracy** button on the map (user, 2026-10-14, 4.8). |
| D11 | **One error measure for both screens:** the badge's mean error comes from `CALIB_RESULT` for the Gazepoint Control screen too, not from Control's `AVE_ERROR` (hub proposal from the 2026-10-14 data, agreed by the user 2026-10-14, 4.8). |
| D12 | **Slow gets slower** (amends D1 for Slow only): three presets stay, Normal and Fast keep their numbers. Slow's new pair is open (section 9, revision 4.9) (Hsieh's feedback, user 2026-10-22, 4.9 R4). |
| D13 | **No shrink:** the picture keeps its large size at every point, during the hold too (amends 4.1 step 3 and 4.3b's size table) (Hsieh's feedback, user 2026-10-22, 4.9 R5). |

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
     *Revision 4.9 R5 (D13) replaces the shrink: the icon settles at the point at its large size
     and holds still at that size.*
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

*Revision 4.9 R4 (D12): Slow becomes slower; the proposed pair is DELAY 2.5 s / TIMEOUT 1.5 s
(section 9, revision 4.9, question 1).*

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
- *Revision 4.9 R5 (D13) drops the Holding column: each preset is one constant size (the Gliding
  value), and the paragraph above no longer applies.*

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
  during the hold so the gaze can settle. (Kept by revision 4.9 R5; only the shrink goes.)

### 4.7 Recording

- `calibration.json` adds: `mode` (`app_drawn`, `control` for the operator's own choice of
  Gazepoint Control's window, or `control_fallback`), speed, DELAY, TIMEOUT,
  icon id, size, background, layout, per-point `score` and `error_deg`, and `improve_runs` (the
  number of re-runs before Back).
- `_diagnostics/calibration_timing.jsonl` adds per-point times (start, result, glide end, hold
  start) to verify the hold rule in 4.1.

### 4.8 Live-check revision (2026-10-14)

**Evidence.** On 2026-10-14 the user (as subject, GP3 HD, Slow speed, Large ball, white background)
ran 4 calibrations on each screen, saved as subjects `GRID3STYLE`, `GRID3STYLE-TEST-1..3`,
`GAZEPOINTSTYLE`, `GAZEPOINTSTYLE-TEST-1..3`. The same measure is used for both (per-point error from
`CALIB_RESULT`, `error_deg`, mean of both eyes):

| Run | Screen | Mean, 5 pts | 4 corners | Centre (its order) | Badge (as shown) |
|---|---|---|---|---|---|
| GRID3STYLE | App | 0.71 deg | 0.44 | 1.77 (5th) | 29.3 px (ours) |
| GRID3STYLE-TEST-1 | App | 0.87 | 0.54 | 2.17 (5th) | 35.9 px (ours) |
| GRID3STYLE-TEST-2 | App | 0.49 | 0.30 | 1.21 (5th) | 20.1 px (ours) |
| GRID3STYLE-TEST-3 | App | 0.66 | 0.41 | 1.65 (5th) | 27.3 px (ours) |
| **App, average** | | **0.68** | **0.42** | **1.70** | |
| GAZEPOINTSTYLE | Control | 0.56 | 0.35 | 1.41 (1st) | 37.7 px (Control's) |
| GAZEPOINTSTYLE-TEST-1 | Control | 0.29 | 0.18 | 0.74 (1st) | 43.2 px (Control's) |
| GAZEPOINTSTYLE-TEST-2 | Control | 0.45 | 0.28 | 1.12 (1st) | 31.5 px (Control's) |
| GAZEPOINTSTYLE-TEST-3 | Control | 0.50 | 0.31 | 1.25 (1st) | 19.5 px (Control's) |
| **Control, average** | | **0.45** | **0.28** | **1.13** | |

Findings:
- The centre is the weakest point on **both** screens; on the App screen it is amber in every run
  (what the user saw). Control's own window shows no score, so its weak centre was not visible.
- The App screen is about 0.2 deg worse overall: 0.68 vs 0.45 deg mean, 1.70 vs 1.13 deg at the
  centre. Its corners are further out (10/90 % vs Control's 15/85 %) and its centre comes last;
  Control's comes first.
- In every run the centre's estimate sits mostly **above** the target (dy -0.02 to -0.09 of the
  screen height).
- The badge numbers of the two screens are not comparable: the Control screen's badge is Control's
  own `AVE_ERROR`, which does not follow the per-point data (the best Control run, 0.29 deg, had
  the worst badge, 43.2 px).
- All runs are within the GP3 HD's rated 0.5-1 deg, so a live accuracy check (D10) is worth having.

**R1 - Centre first (D9).** `_APP_LAYOUT` order becomes C, TL, BR, TR, BL, then (9 points) top,
right, bottom, left midpoints. Positions unchanged. The icon still enters from the top-left corner,
so the first glide goes to the centre. The results map shows the points where they are; nothing
else changes. If the 4 + 4 re-runs (plan step 8) still show a clear gap, the next candidate is
moving the corners to 15/85 % (not part of this revision).

**R2 - One error measure (D11).** For the Gazepoint Control screen and the fallback, the badge's
`mean_error_px` is computed from `CALIB_RESULT` with `calibration_settings.mean_error_px`, the same
as the App screen; `valid` = any eye of any point valid. The per-point `score` / `error_deg` are
added to their `calibration.json` too (`annotate_result` for every mode). Control's `AVE_ERROR`
is still logged in `calibration_timing.jsonl` (as `control_ave_error_px`) for comparison but no
longer shown or saved as the result. When no `CALIB_RESULT` arrives (the old path's
`calib_result_never`), today's behaviour stays.

**R3 - Check accuracy view (D10).** A sixth state of the calibration window (App screen only),
a copy of Gazepoint Control's after-calibration window
(`resources/images/window-after-calibration.png`):
- Opened by a **Check accuracy** button on the results map (beside Show Monitor). Buttons in the
  view: **Repeat calibration** (= Improve calibration: full re-run, then the results map),
  **Results** (back to the map), **Done** (= Back: closes the window, keeps the result). Esc / X =
  Done.
- **Targets:** 11 circles in rows of 4-3-4 as Control draws them: centres at x 18 / 39 / 61 /
  82 % (top and bottom rows) and 29 / 50 / 71 % (middle row), y 18 / 50 / 82 %. Each is a thin
  ring with a small "+" at its centre; ring radius 3 deg (from the geometry, like the icon sizes).
  Ring and "+" use the background's contrast colour (dark on white/grey, light on black).
- **Live gaze trail:** the current point of gaze (the session's POG as recorded, with **no app
  smoothing**, so the view shows the calibration, not the cursor filter), drawn as small green
  circles for the samples of the last 1 s, joined by a thin green line; only valid samples. No
  gaze for 0.5 s: the trail fades out and the line "No gaze. Check the head position." appears.
- **Status lines** bottom left (green, like Control's): "Left eye: n of N points valid",
  "Right eye: n of N points valid", from `CALIB_RESULT`.
- The gaze stream is needed here: the reader thread is resumed after `CALIB_RESULT` (it is paused
  only around the run), and the view reads the latest samples from the client (no new socket).
- Not recorded: the view is a visual check only; `calibration.json` only adds
  `accuracy_checked: true|false` (whether the view was opened for the kept result; reset on
  Repeat / Improve).
- The Gazepoint Control screen is unchanged: Control shows its own window there.

### 4.9 Hsieh feedback revision (2026-10-22)

**Origin.** Hsieh, a clinical collaborator (`resources/hsieh/suggestion.txt`):

> "Calibration: It would be helpful if the speed of the moving path could be adjusted to a slower
> pace (in slow mode), giving children enough time to look at each target and complete the
> calibration properly. The pictures look nice, and it would be great if they could remain large
> throughout the process rather than shrinking when they reach the four corners."

User decisions, 2026-10-22:
- **U1 -> D12:** make the existing **Slow** preset slower. Three presets stay (Slow / Normal /
  Fast); only Slow's numbers change.
- **U2 -> D13:** the picture **stays large at every point, no shrink**. Hsieh saw it at the
  corners, but the code shrinks it at every point while Control samples. The icon keeps its large
  size during the hold too.

**Finding: today's Slow glides faster than Fast.** The glide is DELAY less the shrink and the
50 ms safety margin (`calibration_motion.schedule`). On the lab rig (24-inch, 1920 x 1080, 65 cm)
the longest leg of the 5-point order (TL -> BR and TR -> BL, about 41 deg) gives:

| Preset (DELAY / TIMEOUT) | Glide | Still before sampling | Mean speed, 41 deg leg | Peak (eased) |
|---|---|---|---|---|
| Slow 1.0 / 1.5 s (today) | 0.70 s | 0.30 s | 59 deg/s | 92 deg/s |
| Normal 0.8 / 1.0 s | 0.53 s | 0.27 s | 78 deg/s | 123 deg/s |
| Fast 1.8 / 0.4 s | 1.50 s | 0.30 s | 27 deg/s | 43 deg/s |

So Slow is slow only in its hold; the moving path Hsieh watched is the second fastest of the
three. The fix is mainly a longer DELAY. (The other legs: entry to C 25 deg, C -> TL 21 deg,
BR -> TR 20 deg.)

**R4 - Slower Slow (D12).** Proposed: **Slow = DELAY 2.5 s / TIMEOUT 1.5 s** (question 1).
- **DELAY (glide, no sampling) 1.0 -> 2.5 s.** With R5's settle (0.5 s cap, question 2) the glide
  is about 1.95 s: mean 21 deg/s on the longest leg (peak 33), about 10 deg/s on the short legs.
  The picture now moves clearly slower than with Normal or Fast, slow enough to follow with the
  eyes instead of jumping after it. Children with CP often have slower, less accurate pursuit and
  a longer delay before a saccade, so the gain is meant for them; Hsieh confirms on a child (plan
  step 13).
- **TIMEOUT (sampling) stays 1.5 s.** That is about 225 samples at 150 Hz and gave A17's 0.30 deg.
  A longer TIMEOUT asks the child to keep looking longer; it does not add time to *find* the
  target, which is what the feedback is about. It also keeps one variable fixed for the accuracy
  check (A21).
- **Still before sampling:** about 0.55 s (settle 0.5 s + the 50 ms margin), today 0.30 s.
- **Run time:** 4.0 s per point (plus 10-70 ms; the first point about 1 s more, seen 2026-10-13):
  5 points about 20 s (today 12.5 s), 9 points about 36 s (today 22.5 s).
- **Alternatives** (question 1):
  - **A: 3.0 / 1.5 s** - glide about 2.45 s, 17 deg/s mean; 4.5 s per point, 22.5 s / 40.5 s.
  - **B: 2.5 / 2.0 s** - the same glide, 0.5 s more looking while Control samples; 4.5 s per
    point, 22.5 s / 40.5 s.
  - Not recommended: 2.0 / 1.5 s - glide 1.45 s, hardly slower than Fast's (1.25-1.50 s).
- **Normal and Fast are unchanged** (U1). Fast's hold is still decided by A9.
- **Both screens** (4.3b): the Gazepoint Control screen and the fallback get the new Slow pair
  too; Control animates its own target over the longer DELAY.
- **API limits:** API 3.5 / 3.6 give only TIMEOUT > 0 and DELAY >= 0, no upper bound
  (`docs/gazepoints/synthesis/api-reference.md`, rows `CALIBRATE_TIMEOUT` / `CALIBRATE_DELAY`).
  The wait deadlines already scale with the pair (`calibration_run`: next point within
  `delay_s + timeout_s + grace_s`; `Calibration`: `max(10 s, n x per-point x 1.75)`), so nothing
  else changes. That Control accepts 2.5 s is checked live (A22).
- **Old and new Slow runs stay apart.** `calibration.json` already records `speed`, `delay_s` and
  `timeout_s` (`calibration_settings.record_for`; `RECORD_KEYS` in `calibration.py`), and
  `calibration_timing.jsonl` logs the pair. A Slow run before this revision has `delay_s` 1.0,
  after it 2.5. Analysis must use `delay_s`, not the name `"slow"`. `docs/DATA_SCHEMA.md` gets a
  line: "Slow was 1.0 / 1.5 s before revision 4.9".
- **Code:** `SPEEDS["slow"]` in `src/engine/calibration_settings.py` (line 50). The Setup label
  follows by itself (`calibration_settings_panel._speed_label`: "Slow (glide 2.5 s, hold 1.5 s)").

**R5 - No shrink (D13).**
- **`TargetMotion`** (`src/engine/calibration_motion.py`): the phases become **glide -> settle ->
  hold**. The settle takes the shrink's time slot at the end of DELAY: the icon is at the point,
  at full size, and its wobble fades to 0. The hold is unchanged (still, angle 0, until the next
  `CALIB_START_PT`), but now at the large size.
  - `PHASE_SHRINK` -> `PHASE_SETTLE`; `SHRINK_S_MAX` / `SHRINK_FRACTION` -> `SETTLE_S_MAX` /
    `SETTLE_FRACTION`; `schedule()` returns `(glide_s, settle_s)`. The hold rule (A1: hold no
    later than DELAY after the record) is unchanged.
  - `MotionSample.size` is removed: there is one size, so `sample()` no longer blends it.
  - **Settle cap 0.5 s** (today's shrink cap 0.25 s), fraction stays 0.3 (question 2). Normal is
    unchanged (its 0.225 s comes from the fraction). Fast: glide 1.50 -> 1.25 s, still 0.30 ->
    0.55 s. Slow (2.5 s): still 0.55 s. No run time is added: the still time comes out of the
    glide.
  - **Wobble:** the rule stays: +-8 deg while gliding, fading in the settle, 0 during the hold
    (the hold already returns angle 0.0). The eye gets a still target while Control samples.
- **Size:** `SIZES_DEG` becomes one diameter per preset: **Small 2.2, Normal 3.0, Large 4.0 deg**
  (today's gliding values). `icon_diameter_px(size, mm_per_px, viewing_distance_mm)` drops its
  `holding` argument, and `CalibrationStage.diameter_px()` returns that one size. The Target size
  setting (Small / Normal / Large) now means this constant size (question 4). On the lab rig:
  90 / 123 / 164 px (4.7 / 6.4 / 8.5 % of the width).
- **What Control measures does not change.** The icon's centre stays on CALX / CALY; Control
  assumes the gaze is there.
- **Knock-on effects:**
  - Results map (4.4): none (its circles are sized by `CIRCLE_FRACTION`).
  - Check accuracy (4.8 R3): none (3 deg rings, no icon).
  - Gazepoint Control screen and the fallback: none; Size never applied there (4.3b). Control's
    own target still shrinks in its own window.
  - Entry from the top-left corner: none; the icon already enters at the large size.
  - Corners: at 10 / 90 % the Large icon's radius (7.6 % of the height on the lab rig) fits
    inside the 10 % inset. On a smaller 1920 x 1080 screen (for example 14-inch) Large is about
    26 % of the height and is cut by the screen edge at the corner points, now also while Control
    samples. Accepted (question 4): the centre never moves, and the operator can pick Normal.
  - Diagnostics: `hold_painted` keeps its meaning (the first paint of the still hold); the
    timing log is unchanged.
  - Record: `calibration.json` adds **`size_deg`** (the drawn diameter, e.g. 4.0). A file without
    it is from before 4.9 (large while moving, small while sampling). `docs/DATA_SCHEMA.md` is
    updated.
  - Docstrings that say "shrinks" (`calibration_motion` module, `CalibrationStage.diameter_px`)
    are updated.
- **Tests that change:**
  - `tests/test_calibration_run.py`: `test_the_speed_presets_are_the_pairs_of_the_spec` (new Slow
    pair); `test_the_hold_starts_no_later_than_delay_after_each_record_with_a_fake_clock` (no
    `size == 0.0`; add DELAY 2.5 to its list).
  - `tests/test_calibration_window.py`:
    `test_the_icon_enters_from_the_corner_glides_to_each_point_and_holds_by_delay` (the hold is
    large); `test_the_icon_shrinks_before_the_hold_and_keeps_still_in_it` (becomes "settles,
    keeps its size, still in the hold"); `test_the_icon_is_drawn_at_the_degrees_of_its_size_preset`
    (one size in every phase); `test_a_larger_preset_draws_a_larger_icon` (only if
    `diameter_px` drops its `sample` argument).
  - `tests/test_calibration_settings.py`: `test_the_size_presets_are_the_degrees_of_the_spec`;
    `test_normal_is_about_6_percent_and_1_7_percent_of_the_width_on_the_lab_rig` (the 6 % only);
    `test_the_apparent_size_is_the_same_on_a_monitor_with_other_pixels` (signature);
    `test_the_record_holds_the_mode_speed_timing_icon_size_background_layout_and_improve_runs`
    (Slow pair, `size_deg`); `test_ease_runs_from_0_to_1_and_the_schedule_ends_before_delay`
    (settle; add 2.5).
  - The flow tests run on shortened `SPEEDS` (`quick` fixture), so they are not affected.

**Risk: a large target may lower accuracy.** Today's hold size (0.6-1.0 deg) is a small spot. A
4 deg picture lets the eye rest anywhere on it (an ear, a wing, an edge), up to about 2 deg from
the centre Control assumes. That can widen the fixation spread and raise the error. The settle
and the still hold help, and the icons are centred, but the size of the effect is unknown.
- **Measure (A21),** GP3 HD, user as subject, in **one sitting**, set-up as A17 (App screen,
  5 points, Large, ball, black): 4 runs with the old build (shrink, Slow 1.0 / 1.5 s, a worktree
  at the commit before 4.9) and 4 with the new build, **interleaved** (old, new, old, new, ...).
  One sitting, because sitting-to-sitting variation is as large as the effect (2026-10-14: the
  same build gave 0.68 and 0.39 deg). Reference: the 4.8 baseline, App 0.30 deg mean (corners
  0.19, centre 0.75; run means 0.23-0.39).
- **Pass:** the new mean is at most 0.15 deg above the old build's mean of the same sitting, and
  at most 0.5 deg. If it fails, 4 + 4 more runs at Normal (both builds) show whether the size or
  the slower glide is the cause.
- An adult who knows the task is not a child. The real test of "time to look" is a child session
  with Hsieh (plan step 13); it is logged here but is not an acceptance gate.
- **If it is worse:** no new setting (U2). The options for the user, decided after A21
  (question 3): (a) a small fixed dot at the icon's centre during the hold, drawn on the large
  picture (it stays large but gives the eye a centre); (b) accept the loss for Slow; (c) a slight
  shrink after all (against U2, listed only for completeness).

**Wireframe impact** (described here; the wireframe is updated at plan step 9, GATE 1):
- `docs/wireframes/calibration-window.md` State 2 (Hold): the box shows the large icon `(BEE)`
  still at the point, label "large, still (no shrink)" instead of "shrunk (~1.8 %), still"; the
  note "has shrunk to the small size and holds still" becomes "has arrived, stopped its wobble
  and holds still at the same large size". State 1 is unchanged.
- `docs/wireframes/setup.md` Speed list: "Slow (glide 2.5 s, hold 1.5 s)" (or the chosen pair).
  Target size keeps its three names (the combo shows names only; there is no tooltip). No new
  setting.

## 5. Scope

**In:**
- sections 4.1-4.7;
- the new speed/target/size/background settings;
- the Calibration screen choice replacing the show-window tick box (D6);
- the Start-test Calibrate button (D4);
- tests with a fake Control that sends `CAL` records (extend `tools/fake_gazepoint_server.py`);
- `DATA_SCHEMA.md`;
- revision 4.9: the slower Slow pair (R4) and the constant icon size (R5).

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
| A14 | (4.8 R1) The App screen sends the centre point first: 5 points C, TL, BR, TR, BL; 9 points then add top, right, bottom, left; the map still places each point at its position | unit test |
| A15 | (4.8 R2) For every mode the badge's mean error and `valid` come from `CALIB_RESULT`; `AVE_ERROR` only in the timing log; `calibration.json` has per-point `score` / `error_deg` for the Control screen too | unit test |
| A16 | (4.8 R3) Check accuracy opens from the map; 11 rings at the 4-3-4 positions; the trail shows the last 1 s of valid unsmoothed gaze from the client; no gaze for 0.5 s gives the hint; Repeat = full re-run, Results = map, Done / Esc / X = Back keeping the result; `accuracy_checked` recorded | unit test with the fake Control + fake gaze |
| A17 | (4.8) On the GP3 HD: 4 runs per screen again; App centre and mean error compared with Control's; the trail sits on the rings the user looks at | live, user as subject |
| A18 | (4.9 R4) `SPEEDS["slow"]` is the chosen pair; Normal and Fast are unchanged; the pair is sent for both screens, Control's own values are restored, and `delay_s` / `timeout_s` land in `calibration.json`; the Setup label shows the new pair | unit test with the fake Control |
| A19 | (4.9 R5) The icon has one diameter in glide, settle and hold, equal to its preset's degrees (2.2 / 3.0 / 4.0); it is still (angle 0) in the hold, and the hold starts no later than DELAY after the record for every preset, the new Slow included | unit test with a fake clock |
| A20 | (4.9 R5) The settle cap is applied (Normal's schedule unchanged, Fast's and Slow's still time as in 4.9); `calibration.json` has `size_deg`; `DATA_SCHEMA.md` lists `size_deg` and the old Slow pair | unit test + review |
| A21 | (4.9) On the GP3 HD, one sitting: 4 old-build and 4 new-build runs interleaved (App, 5 points, Slow, Large, ball, black); the new mean error is at most 0.15 deg above the old build's mean and at most 0.5 deg | live, user as subject |
| A22 | (4.9) On the GP3 HD: Control ACKs the new Slow DELAY / TIMEOUT and each point lasts DELAY + TIMEOUT + 10-70 ms (`calibration_timing.jsonl`); the picture stays large at every point, the corners included; the glide looks clearly slower than Normal and Fast | live, user as subject |

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
7. **DONE 2026-10-14 - Revision 4.8** (2026-10-14): wireframe states 4 and 6 DONE (user OK 2026-10-14); then implement R1-R3 (A14-A16), hub review, full pytest.
8. **DONE 2026-10-14 -** Live on the GP3 HD (A17): 4 + 4 runs with the user as subject, Check accuracy with real gaze; decide whether the corners move to 15/85 %.
9. **Revision 4.9:** the user answers section 9 (revision 4.9) questions 1, 2 and 4; then the wireframe (calibration-window.md state 2, setup.md Speed list). User GATE 1.
10. `spec-implementer` implements R4 and R5 (A18-A20) in its own worktree; no commit.
11. Hub review and the full pytest (A11).
12. Live on the GP3 HD with the user as subject (A21, A22); question 3 only if A21 fails. Commit on the user's OK.
13. Afterwards: a child session with Hsieh; the feedback is logged in section 10 (not a gate).

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

- **2026-10-14 - plan step 7: revision 4.8 R1-R3 (A14, A15, A16 by test) - `spec-implementer`, model `claude-sonnet-5-5`, worktree `calib-revision-48` at `0185c36`. No commit, nothing staged, no device, no app launch; `configs/default.yaml`, `configs/local_state.json`, the wireframe and `tools/fake_gazepoint_server.py` untouched.**
  - **R1 (D9):** `calibration_settings._APP_LAYOUT` is now C, TL, BR, TR, BL, then top, right, bottom, left; the positions are unchanged. Nothing else reads the order (the map takes each point's own `target_x/y`).
  - **R2 (D11):** `calibration_settings.annotate_result` now takes `mean_error_px` and `valid` from `CALIB_RESULT` for **every** mode (it was `app_drawn` only), via `mean_error_px()` and the new `any_eye_valid()` (also used by `calibration_run._result_from_calib_result`). The per-point `score` / `error_deg` were already added for every mode. A result with no per-point data (the `calib_result_never` path), or a call with no geometry, keeps what the run reported. `Calibration` (the Control-window path) is unchanged and still returns Control's `AVE_ERROR`; `run_calibration` -> `annotate` overrides it. In `calibration.py` the timing record's `mean_error_px` key is renamed `control_ave_error_px` (the same value, Control's summary); the `app_drawn` record keeps its `mean_error_px`.
  - **R3:** new `src/ui/calibration_check.py` (343 lines): `GazeTrail` (Qt-free: last 1 s of valid samples, silence timer, 0.5 s no-gaze threshold, 0.4 s fade), `CalibrationCheckView` (11 rings 4-3-4 at the 4.8 positions, "+" at each centre, radius 3 deg = `D x tan(3 deg) / mm_per_px` per logical px, contrast ink per background, hollow green circles joined by a thin line, eye lines or the "No gaze. Check the head position." hint, Repeat calibration / Results / Done), `ring_radius_px`, `eye_lines`. The view takes an injected `clock` and `gaze_source` (a callable returning the client's newest `GazeSample` or None), polls it on a 16 ms timer, draws `sample.x/y` (the recorded POG, no app smoothing) only when `valid` and only when `t_ns` is new; a sample already waiting when the view opens (the reader is paused around the run) is not counted. A bound-method source is held weakly (same reason as `HeadPositionPanel`). The window (`calibration_window.py`) gets `STATE_CHECK`, a **Check accuracy** button between Show Monitor and Back, `_open_check` / `_close_check`, `accuracy_checked()`; Repeat = `improveRequested`, Done = `backRequested`, Results = back to the map; Esc / x stay `cancelRequested`, which the flow already turns into Back off a running thread. `show_results(..., eyes=)` carries the per-eye counts (`calibration_settings.eye_counts` -> `EyeCounts`). `calibration_flow.py` takes `gaze_source`, passes `eyes=`, and writes `accuracy_checked` through the new `with_accuracy_checked`. `setup_page.py`: new `SetupPage.gaze_input()` (the client's `latest()`, None without a connected tracker) handed to the flow; no new socket, and the reader is already resumed after the run by `run_calibration`'s `streaming_paused`.
  - **Record:** `record_for` writes `accuracy_checked: false`, the flow sets it true when the view was opened; `RECORD_KEYS` carries it into `calibration.json` and back. `docs/DATA_SCHEMA.md`: `accuracy_checked`, `control_ave_error_px`, `mean_error_px` / `valid` / `score` for every mode, and the new `layout` order (a file from before 2026-10-14 has the centre last).
  - **Tests added/changed (44 more tests; 4354 in all):** new `tests/test_calibration_check.py` (28: rings, radius from the geometry, contrast colours, trail model, trail with fake clock and fake gaze, fade, no-gaze hint, eye lines, buttons, timer, weak source, window states); `test_calibration_flow.py` (+8: `gaze_input`, Check accuracy live gaze and Done recording, Results, Repeat = full re-run, Esc / x / close = Done, Show Monitor in both orders; the Control screen and the fallback report the `CALIB_RESULT` number; centre first end to end); `test_calibration_run.py` (+4: A15 for the Control screen and the fallback, no `CALIB_RESULT` keeps today's number, `control_ave_error_px` only in the log); `test_calibration_settings.py` (A14 order, A15 for every mode, `any_eye_valid` / `eye_counts`, `accuracy_checked`); `test_calibration.py` (the log key); `test_calibration_window.py` (the old "centre is point 5" assumption -> point 1); `tests/calibration_fixtures.py` (`FakeGaze`, `has_green`).
  - **pytest** (4 parallel shards, JUnit counts, run from the worktree with the `dev/.venv` python): **4354 tests, 4349 passed, 5 failed, all the known fresh-worktree baseline** (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`, `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults` x4: alpha 0.35 vs 0.22). `ruff check` on the changed files: only 4 pre-existing `UP017` (`timezone.utc`) warnings.
  - **Checked offscreen only:** the view rendered to a PNG on white and black backgrounds (rings, "+", trail, buttons in the tiers; the offscreen platform has no fonts, so the text shows as boxes). Not checked: the real look at 1920 x 1080 and 100 % (the lower ring row, y 82 %, is drawn under the bottom-left eye lines and the buttons, as in Control's own window), real gaze, the trail's colour on grey, the real REC rate feeding the trail (A17).
  - **Choices inside the SPEC (not deviations):** the fade is 0.4 s long, starting when the 0.5 s hint appears (the SPEC says only "fades out"); the trail and eye-line greens are `SUCCESS_TEXT` on white / grey and `#4CE06A` on black (stimulus colours, like the backgrounds); circles have radius 4 px and a 1.5 px line; ring line 2 px, "+" arm 9 px; Check accuracy is also offered while Show Monitor is up (section 9, answered: keep).
  - **Deviations from the SPEC:** none.
  - **2026-10-14 (follow-up, user's answers to section 9) - `claude-sonnet-5-5`:** `accuracy_checked` now describes the kept result: `CalibrationWindow.begin_run` resets it, so a run after Repeat / Improve starts false (4.8 R3, `DATA_SCHEMA.md` and the section 9 questions updated; tests: the window, the Repeat flow and the new `test_accuracy_checked_describes_the_kept_result_not_an_earlier_one`). Check accuracy during Show Monitor stays as built. Only `tests/test_calibration*.py` were run (the hub ran the full suite): 219 passed, 0 failed (+1 test: 4355 in all with the earlier full run).
  - **Left undone (the hub's):** A17 live on the GP3 HD (4 + 4 runs, the trail on the rings); the real-font look of the new button and eye lines; whether the corners move to 15/85 % (out of scope, decided after A17).

## 9. Open decisions (for the user)

All answered by the user 2026-10-13 and recorded in section 2: D1, D2, D3, D5 (first round), D4 and D6 (after a longer explanation).

Implementer open questions (all answered by the hub, 2026-10-13):

- **2026-10-13** - **Esc / x on the results map** (4.1 step 8, A4). *Answered:* it must not discard. On the results map and Show Monitor, Esc / x is Back and keeps the new result, because Control already holds the new calibration; during glide, hold and processing it still cancels. Applied in 4.1 step 8, A4 and `CalibrationFlow._on_cancel`.
- **2026-10-13** - **`calibration.show: false`.** *Answered:* accepted: any `show` value gives the App screen (no picture at all is no longer offered); `points` of the block still sets the Points default.
- **2026-10-13** - **`mode` for the operator's own choice of Gazepoint Control.** *Answered:* accepted: `"control"`; the values are `app_drawn | control | control_fallback` (4.2, 4.7, `docs/DATA_SCHEMA.md`).
- **2026-10-13** - **Which monitor is "the tracked monitor".** *Answered:* accepted for now: the screen the Setup window is on; multi-monitor placement is checked live (A10). Noted in 4.1 step 1.
- **2026-10-13** - **Fallback alert wording.** *Answered:* keep the 4.2 text (`calibration_run.FALLBACK_ALERT`); the hub aligns the wireframe.

Implementer open questions, revision 4.8 (2026-10-14; none blocked anything; both **answered by the user 2026-10-14**):

- **2026-10-14** - **Is Check accuracy offered while Show Monitor is up (wireframe state 5)?** Wireframe state 5 draws `[Improve calibration] [Hide Monitor] [Back]` with no Check accuracy button (state 5 was not touched by the revision), but state 4 and 4.8 R3 put the button on the results page, and the Show Monitor panel is only an overlay on that same page, so the button is still there and works: it takes the head panel away and opens the view (`CalibrationWindow._open_check`). *Answered:* keep as built; no change.
- **2026-10-14** - **`accuracy_checked` when the view was opened, then Repeat calibration, and Done without opening it again.** The first version read "whether the view was opened before Done" literally (true across Repeat / Improve). *Answered:* it must describe the **kept result**: `_accuracy_checked` is reset in `CalibrationWindow.begin_run`, so a run after Repeat / Improve starts false. Applied; 4.8 R3's wording is updated.

Revision 4.9 (2026-10-22; **open**, for the user; U1 and U2 are already decided and not re-asked):

- **2026-10-22** - **1. Slow's new pair (R4).** *Recommended:* DELAY 2.5 s / TIMEOUT 1.5 s (glide about 1.95 s, 21 deg/s mean on the longest leg; 5 points about 20 s, 9 points about 36 s). *Alternatives:* A 3.0 / 1.5 s (slowest glide, 17 deg/s; 22.5 s / 40.5 s); B 2.5 / 2.0 s (same glide, 0.5 s more sampling; 22.5 s / 40.5 s). Not recommended: 2.0 / 1.5 s (hardly slower than Fast's glide). *Answered 2026-10-22 by the user:* the recommendation, DELAY 2.5 s / TIMEOUT 1.5 s.
- **2026-10-22** - **2. Settle cap (R5).** *Recommended:* 0.5 s (today's shrink cap 0.25 s): about 0.55 s of still picture before Control samples on Slow and Fast; Normal unchanged; Fast's glide 1.50 -> 1.25 s; no run time added. *Alternative:* keep 0.25 s, so Normal and Fast do not change at all (Slow then has 0.30 s of still picture). *Answered 2026-10-22 by the user:* the recommendation, settle cap 0.5 s.
- **2026-10-22** - **3. If A21 shows the large target is less accurate.** *Recommended:* a small fixed dot at the icon's centre during the hold, on the large picture (no new setting). *Alternatives:* accept the loss for Slow; a slight shrink (against U2). Asked only if A21 fails.
- **2026-10-22** - **4. Target size = the one constant size (R5).** *Recommended:* Small / Normal / Large stay 2.2 / 3.0 / 4.0 deg (today's gliding sizes), and on small screens the cut edge of a Large icon at the corner points is accepted (the centre never moves; the operator can pick Normal). *Alternative:* cap the drawn size automatically at what fits the 10 % inset (twice the inset: 20 % of the screen height), so a Large icon on a 14-inch 1920 x 1080 screen (about 26 % of the height) is drawn at about 3.0 deg there; no new setting. *Answered 2026-10-22 by the user:* the recommendation, 2.2 / 3.0 / 4.0 deg, the cut edge on small screens is accepted.

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
- **2026-10-14** - First GP3 HD accuracy runs by the user (4 per screen, subjects GRID3STYLE* and GAZEPOINTSTYLE*): App screen 0.68 deg mean / 1.70 deg centre vs Control screen 0.45 / 1.13; the centre is the weakest point on both; the two badges use different measures (Control's `AVE_ERROR` vs ours). User decisions: D9 centre first, D10 a Check accuracy view (copy of Control's after-calibration window) after the results map. Hub proposal D11: one error measure (from `CALIB_RESULT`) for both screens. New section 4.8, acceptance A14-A17, plan steps 7-8. Next: the wireframe (GATE 1).
- **2026-10-14** - User approved the revision wireframe (calibration-window.md: state 2 order, state 4 Check accuracy button, new state 6) and agreed D11 (one error measure from `CALIB_RESULT` for both screens). Revision 4.8 APPROVED; next: implementation (plan step 7).
- **2026-10-14** - Revision 4.8 hub review: diff within scope, A14-A16 by test; hub full pytest (4 shards, JUnit) 4355 tests, 4350 passed, 5 failed = the known fresh-worktree baseline. Implementer section 9 questions answered by the user: Check accuracy stays available during Show Monitor; `accuracy_checked` describes the kept result (reset on Repeat / Improve).
- **2026-10-14** - Finding from all 16 earlier runs (both screens): `CALIB_RESULT`'s per-point estimates are the leftovers of Control's 5-point fit. Per axis they sum to zero, the 4 corners share one sign and the centre is about 4x the corners in the opposite direction. So with 5 points the centre always reads about 4x the corner error on either screen; it is not a weak centre. An 8-run check with the OLD build in the afternoon gave App 0.39 deg / Control 0.36 deg mean (the morning gap was sitting-to-sitting variation). The user keeps the per-point colours (Grid 3 style).
- **2026-10-14** - **Live check A17 PASSED** (revision build from worktree `calib-revision-48`, GP3 HD, user as subject, Slow / Large / ball / black background, subjects GRID3STYLE-R2-1..4 and GAZEPOINTSTYLE-R2-1..4 in that worktree's sessions): App screen 0.30 deg mean (corners 0.19, centre 0.75; run means 0.23-0.39) vs Control screen 0.46 (0.29, 1.14; 0.20-0.79). Centre first in every App run (A14). Control badges now from `CALIB_RESULT` (e.g. 8.2 px vs Control's own `AVE_ERROR` 17.4 px, logged as `control_ave_error_px`) (A15). Check accuracy opened in runs 1 and 3 (`accuracy_checked` true), run 4 used Repeat twice and recorded false for the kept result (A16). User: the green trail lands in the ring looked at, centre included. The saved App centres were all green (0.57-0.98 deg); the user saw 2 brown centres, probably in run 4's replaced runs. Committed on the user's OK.
- **2026-10-22** - Revision 4.9 DESIGNED from Hsieh's feedback (`resources/hsieh/suggestion.txt`: slower moving path in Slow, pictures stay large instead of shrinking at the corners). User decisions U1 (only Slow changes, D12) and U2 (no shrink at any point, D13). Finding from `calibration_motion.schedule`: today's Slow glides in 0.70 s (59 deg/s mean on the 41 deg leg), faster than Fast's 1.50 s. New section 4.9 (R4 Slow pair, proposed 2.5 / 1.5 s; R5 no shrink: glide -> settle -> hold at one size, settle cap 0.5 s, `size_deg` in `calibration.json`), forward notes in 4.1 step 3, 4.3b and 4.6, acceptance A18-A22, plan steps 9-13, section 9 questions 1-4. Design only: no code, wireframe or test changed. Next: the user answers questions 1, 2 and 4 and approves; then the wireframe (GATE 1).

- **2026-10-22** - Section 9 questions 1, 2 and 4 answered by the user (all three recommendations): Slow = DELAY 2.5 s / TIMEOUT 1.5 s; settle cap 0.5 s; Small / Normal / Large = 2.2 / 3.0 / 4.0 deg with the cut edge accepted on small screens. Question 3 is asked only if A21 fails. Next: the user approves 4.9, then the wireframe (plan step 9).- **2026-10-22** - The user APPROVED revision 4.9 ("approve, go ahead"). Plan step 9 wireframe drawn by the hub: `docs/wireframes/calibration-window.md` State 2 shows the large icon "large, still (no shrink)" and the note says it holds still at the same large size after a settle of at most 0.5 s; `docs/wireframes/setup.md` Speed list reads "Slow (glide 2.5 s, hold 1.5 s)"; both re-rendered with the WTMH theme. Waiting for the user's look (GATE 1).
