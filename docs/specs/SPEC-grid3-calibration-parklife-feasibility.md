---
name: SPEC-grid3-calibration-parklife-feasibility
title: Feasibility study - Grid 3-style calibration (full replica, built-in icons) and a Park Life-style test on the GP3 HD app
status: feasibility done 2026-10-10 - Q1-Q8 answered (section 7.1); image tool wired, uses the audio server's key (already set), loads after a restart; probes P1-P3 PASSED without a device 2026-10-11 (section 6.1); P4-P5 wait for the GP3 HD
created: 2026-10-10
last_updated: 2026-10-11
next_step: none here - continued in SPEC-app-drawn-calibration.md (approved e587da4; probes P4-P5 folded into its live step) and SPEC-gaze-stability-and-positioning.md (C17/C18 head-position widget)
related:
  - docs/calibration-video/README.md (Grid 3 calibration recording, frame-timed)
  - docs/grid3/park-life/README.md (Park Life gridset offline analysis + live walk-through, section 9)
  - docs/gazepoints/synthesis/api-reference.md (Open Gaze API: CALIBRATE_*, CAL records)
  - SPEC-gp3hd-hardware-integration.md (gap A calibration flow; CALIBRATE_SHOW STATE=0 ACK only)
  - SPEC-gui-audit-2026-09-10.md (CALIB_RESULT is the only valid completion marker)
  - SPEC-target-size-and-motion-paths.md (target sizes in degrees)
  - SPEC-input-selection-and-follow.md (per-test pointer + selection)
---

# SPEC-grid3-calibration-parklife-feasibility - can the app do it?

**Status: feasibility done 2026-10-10, all questions answered (7.1). This is a feasibility study,
not an implementation SPEC. Verdicts are in sections 4.2 and 5.2. The custom icon (C4, C5) stays
unproven until the GP3 HD probe (section 6, P1-P5; P6 dropped with stepped mode) runs. Branch `feature/compass-task-flow` at `5b5cb91`.**

## 1. Origin

User request, 2026-10-10:

1. Is the gathered material enough for a feasibility study on the current software,
   especially the calibration? Extra fact from the user: in the Grid 3 calibration the "bee"
   target can be changed into another icon.
2. The goal is a feasibility study that later SPECs build on. Ask about anything unclear.

The material was gathered earlier the same day (commit `5b5cb91`):

- a frame-timed write-up of a Grid 3 eye-gaze calibration recording (`docs/calibration-video/`);
- an offline and a live analysis of the Grid 3 grid set "Park Life" (`docs/grid3/park-life/`).

## 2. Sources and how far they can be trusted

| Source | What it gives | Limits |
|---|---|---|
| Calibration video (`docs/calibration-video/README.md`) | Point layout, order, per-frame timing, target sizes, background change, results screen, "Improve calibration" behaviour | Tracker unknown; score formula, colour thresholds and sampling moment not visible |
| Smartbox / SET-BC public docs (web search 2026-10-10: Grid Pad 12 manual, hub.thinksmartbox.com "Eye gaze settings in Grid 3", SET-BC "Eye Gaze Calibration in Grid 3" 2024) | Target can be a **custom image or animated GIF**; number of points is configurable; **continuous** or **stepped** mode (a third person taps to move to the next point); results use **colour + number, green = best**; "Improve calibration" re-runs **all points that need it**, touching one point re-runs only that point; "Improve calibration" is for **"specific eye gaze cameras only"**; an eye-gaze monitor window helps with distance and angle | Secondary docs; no formula, no thresholds |
| Grid 3 on this PC (live, 2026-10-10) | Camera list: None, Alea, Evo, EyeTech, GazeFirst, Irisbond, Lumin-i, SeeTech, Smart Eye, Tobii, Vida. **No Gazepoint.** With camera = None the Calibration tile and its Settings are greyed out | Grid 3's own calibration cannot be run or inspected with the GP3 HD |
| Park Life (`docs/grid3/park-life/README.md` sections 1-9) | Pages, cells, commands, scene objects with positions, every action's animation, region and duration | Art, animation and sound files are vendor-encrypted; audio not recorded |
| Open Gaze API corpus (`docs/gazepoints/`) | `CALIBRATE_SHOW/START/TIMEOUT/DELAY/CLEAR/RESET/ADDPOINT`, `CALIBRATE_RESULT_SUMMARY`, `CAL` records `CALIB_START_PT`, `CALIB_RESULT_PT`, `CALIB_RESULT` | The manual does not say how Control behaves with its window hidden |
| Project history (SPECs, memory) | Control rejects calibrations with fewer than 4 points (SPEC-2026-09-02 item 7); `CALIB_RESULT` is the only trustworthy completion marker; Control can get stuck after its own-window calibration; `CALIBRATE_SHOW STATE="0"` was only ever ACKed, never used for a full run | |

## 3. Decisions already made (user, 2026-10-10)

| # | Decision |
|---|---|
| U1 | Calibration target fidelity: **full replica** of what Grid 3 shows (stimulus, settings page, results, improve, track-status widget). |
| U2 | Icons: a **built-in set** of our own child-friendly icons. No Smartbox art, no Browse button. |
| U3 | The study covers **both** calibration and Park Life. |
| U4 | Park Life measures: **prompted trials** (a cue names the button to choose; hit / miss / timeout) **and look-back to the effect** (does gaze go to the animated object after the selection). |
| U5 | GP3 HD not available now. The study marks the hidden-window calibration as unproven and gives a ready probe plan. |

---

## 4. Part A - Grid 3-style calibration on the GP3 HD

### 4.1 Current code (as of `5b5cb91`)

- `src/engine/calibration.py` `Calibration.run()` drives Gazepoint Control over the shared socket:
  `CALIBRATE_DELAY` / `CALIBRATE_TIMEOUT` (if set), `CALIBRATE_SHOW` (from `calibration.show`),
  point list via `CALIBRATE_RESET` (5 points) or `CALIBRATE_CLEAR` + `CALIBRATE_ADDPOINT`
  (other counts), then `CALIBRATE_START`. It polls `CALIBRATE_RESULT_SUMMARY` and waits for the
  one-time `CALIB_RESULT` push (`_CALIB_RESULT_GRACE_S = 0.75`).
- `CALIB_START_PT` / `CALIB_RESULT_PT` records are read and **ignored**
  (`calibration.py:597`).
- Layout pool `_CALIBRATION_POINT_POOL`: 5 points at the vendor 0.15 / 0.85 margins plus centre;
  9 points add the edge midpoints. Allowed counts 1-9 in code, but Control rejects fewer than 4.
- `configs/default.yaml` `calibration:` has `enabled`, `points` (5 or 9), `show` (default `true`),
  `timeout_s`, `delay_s`.
- The Setup page (`src/ui/setup_page.py`) shows a details table per point: target, left and right
  eye estimate, validity, "Error (px)". `per_point_errors_px()` computes the pixel error;
  `geometry.px_to_deg()` (used in `src/data/report_config.py:230`) converts pixels to degrees.
- The stimulus on screen today is **Gazepoint Control's own window**. The app draws nothing.

### 4.2 Requirement-by-requirement verdict

Verdicts: **YES** = possible with known API and code; **PROBE** = possible on paper, needs the
GP3 HD probe; **ADAPT** = the exact Grid 3 behaviour is impossible, a close substitute is possible;
**NO** = not possible.

| # | Grid 3 requirement (source) | Verdict | How / why |
|---|---|---|---|
| C1 | Calibration starts in one click from a settings page, no instruction screen (video s1) | YES | App UI only |
| C2 | Full-screen window over the taskbar, plain background, only a faint close "X" (video s2) | YES | App-drawn window (see C4) |
| C3 | 5 points at 10 % / 90 % insets, order TL, BR, TR, BL, C (video s2) | YES | `CALIBRATE_CLEAR` + 5 x `CALIBRATE_ADDPOINT` in that order. Note: the order Control runs the points in is not documented; the probe checks it (P2) |
| C4 | **Custom target picture** (user note; Smartbox docs: image or animated GIF), built-in set (U2) | **PROBE** | Control's own window cannot show another picture; the API has no setting for it. The app must draw the target itself with `CALIBRATE_SHOW STATE="0"` and place it at the `CALX`/`CALY` of each `CALIB_START_PT`. Unknown: does Control still calibrate and still send `CALIB_START_PT` / `CALIB_RESULT_PT` with its window hidden? (P1) |
| C5 | Target glides between points (eased), grows while moving, shrinks on arrival, holds small (video s2) | PROBE | The app animates during `CALIBRATE_DELAY` (animation time) and holds during `CALIBRATE_TIMEOUT` (sampling time). Depends on C4 and on the timing of the `CAL` records (P3) |
| C6 | Speed setting ("fast" = ~2.1-2.4 s per point, ~11 s per 5-point run) | YES / ADAPT | Speed maps to `CALIBRATE_DELAY` + `CALIBRATE_TIMEOUT`. Grid 3's hold is only ~0.2-0.35 s; Control's sampling time defaults to ~1.25 s. A Grid 3-fast hold may give a poor calibration; the probe measures quality at short timeouts (P4) |
| C7 | Target size setting, background colour setting (video s2, s4) | YES | App-drawn |
| C8 | Number of targets setting ("Five targets") | ADAPT | 4-9 points work (Control rejects fewer than 4). Grid 3 may offer 1-3 points; we cannot |
| C9 | Continuous vs **stepped** mode (operator taps to move on; Smartbox docs) | **NO as-is** | Control drives the point timing; the API has no "next point" command. A substitute (very long `CALIBRATE_TIMEOUT`, operator taps to skip) would still not let the operator decide when sampling starts. Proposed: drop, or test whether `CALIBRATE_START STATE="0"` mid-run plus a new run of the remaining points is usable (P6) - unlikely, because a new run replaces the calibration |
| C10 | No sound, mouse cursor visible (video s2) | YES | |
| C11 | "Processing calibration results" state with spinner, ~2 s, Improve disabled (video s3) | YES | Shown between the last `CALIB_RESULT_PT` and `CALIB_RESULT` |
| C12 | Results map: screen rectangle, one circle per point at its position, integer score, colour (video s3; docs: green = best) | YES / ADAPT | Layout is app UI. The **score must be our own**: Gazepoint gives per-point, per-eye gaze estimates (`CALIB_RESULT` `LX?/LY?/LV?/RX?/RY?/RV?`) and `AVE_ERROR` in pixels, not a 0-100 score. Proposed formula in 4.4; bands need the user / clinician (Q1) |
| C13 | One score per point, no per-eye split, no overall score (video s3) | YES | Our score combines both eyes. The per-eye table stays available on the Setup page |
| C14 | **"Improve calibration"**: re-run only weak points, recompute all (video s3, s7; docs) | **ADAPT** | The API cannot add new samples to the existing calibration. Any run replaces it, and runs below 4 points are rejected. Grid 3 itself only offers this for "specific eye gaze cameras". Options in 4.5 (Q2) |
| C15 | Touch one point on the results map to re-run only that point (docs) | NO | Same reason as C14 |
| C16 | "Back" leaves, no accept step; the camera keeps the calibration (video s3; docs) | YES | Control keeps the last calibration; the app already saves results per subject |
| C17 | "Show Monitor" / eye-gaze monitor window for distance and angle (video s3; docs) | YES | The client already supports eye position data (`ENABLE_SEND_EYE_LEFT/RIGHT`, `src/inputs/gazepoint_client.py:75`; `LEYEX/Y/Z`, `REYEX/Y/Z` in `eye_geometry.csv`, `src/data/analysis_export.py:91`). The probe confirms the 3D values are usable for a distance read-out (P5) |
| C18 | Live track-status face: moves, tilts and scales with the head; green / orange / red; "No eyes detected" (video s5) | YES / ADAPT | Position, scale (distance) and tilt (left vs right eye height) can come from the eye data. The **meaning of the colours is not documented**; we define our own (for example green = both eyes valid and distance in range). Q4 |
| C19 | A calibration can be started from inside a test (Grid 3 "Calibration" command) | YES | App flow decision (Q5) |

**Summary for Part A (19 requirements):**

- 10 are plainly feasible: C1, C2, C3, C7, C10, C11, C13, C16, C17, C19.
- 3 are feasible with one part adapted: C6 (hold time), C12 (our own score), C18 (our own colour meaning).
- 2 need a substitute: C8 (minimum 4 points), C14 (improve).
- 2 are not possible as Grid 3 does them: C9 (stepped mode), C15 (single-point re-run).
- 2 are PROBE: C4, C5. Everything that shows the custom icon (C4, C5) depends on **one unproven
behaviour**: Gazepoint Control calibrating with its window hidden while it tells the app where
and when to draw.

### 4.3 Proposed design for the app-drawn stimulus (for the later SPEC)

1. Send `CALIBRATE_SHOW STATE="0"`, `CALIBRATE_DELAY` (animation time), `CALIBRATE_TIMEOUT`
   (sampling time), `CALIBRATE_CLEAR`, then `CALIBRATE_ADDPOINT` x N, then `CALIBRATE_START`.
2. The app shows its own frameless full-screen window on the tracked screen.
3. On each `CALIB_START_PT` (`PT`, `CALX`, `CALY`): animate the icon from its current position to
   (`CALX`, `CALY`) x screen size, growing then shrinking, within `CALIBRATE_DELAY`.
4. Hold the small icon until `CALIB_RESULT_PT` for that point.
5. After the last point, show "Processing" until `CALIB_RESULT`, then the results map.
6. Fallback: if no `CAL` record arrives within `CALIBRATE_DELAY` + 1 s, stop and fall back to
   Control's own window (`CALIBRATE_SHOW STATE="1"`), so a calibration is never blocked.

Risks to check during the probe:

- Coordinates: `CALX`/`CALY` are fractions of **Control's** screen. The app window must be on the
  same monitor and use physical pixels (see the 2026-09-30 display-scaling fix: canvas metadata is
  in physical px).
- The socket is shared with the data stream; the existing pause around calibration
  (`calibration.py` reader pause) must also let the `CAL` records through to the drawing code.
- If the app window drops a frame at the moment sampling starts, the child may still be looking
  at the moving icon; the hold must start strictly at or before the sampling window.

### 4.4 Proposed per-point score (Q1)

- For point i: error_i = mean over the valid eyes of the distance from (`LX?`,`LY?`) and
  (`RX?`,`RY?`) to (`CALX?`,`CALY?`), in pixels (as `per_point_errors_px()` does today), then
  degrees with `geometry.px_to_deg()`.
- Score_i = round(100 x max(0, 1 - error_i / E_max)), with E_max a fixed angle (proposal 3 deg,
  so 0 deg = 100, 1.5 deg = 50). No valid eye: score 0, grey circle.
- Colour bands (proposal, to be confirmed): green = 1 deg or less, amber = above 1 and up to
  2 deg, red = above 2 deg or no valid eye.
- This keeps the Grid 3 look (one integer per point, colour) while the number has a clear
  meaning in degrees, which the report already uses.

### 4.5 "Improve calibration" options (Q2)

| Option | What happens | Pro | Con |
|---|---|---|---|
| I-A Full re-run | "Improve" repeats all points | Honest; simplest | Longer for the child (~11 s) |
| I-B Weak-point run of 4+ | Re-run the weak points padded to at least 4 (the weak ones plus their nearest neighbours) | Shorter, focuses on problem areas | The new run **replaces** the calibration; strong points now come only from the padding samples |
| I-C Keep the best | Every full run is kept for the session; "Improve" runs again and the app keeps whichever run scores better | Child effort never makes it worse | Control only holds the **last** run; keeping an older run would need it to be re-applied, which the API cannot do. Only usable if the better run is the newest |

Recommendation for the later SPEC: **I-A**, labelled "Improve calibration", and the results map
marks the weak points so the operator can fix positioning first.

### 4.6 Built-in icon set (U2)

- Our own art, several child-friendly icons (Grid 3 shows a cartoon bee on a white disc).
- PNG with transparency, or an animated sequence (Grid 3 allows animated GIF). Size is drawn in
  degrees (large ~5-6.5 % of the screen width while moving, small ~1.5-2 % at the hold, from the
  video), so the same icon works on any screen.
- Source of the art is open (Q6).

---

## 5. Part B - a Park Life-style test candidate

### 5.1 What the new test would be (from U4 and the Park Life analysis)

- **Screen:** a 7 x 5 grid like Park Life page 2. One animated scene in the centre (5 x 5 cells),
  8 buttons at the left and right edges. At 1920 x 1080 one button is ~274 x 216 px.
- **Prompted trial:** a cue names one button ("Make the balloons pop!"). The child selects with
  the per-test pointer and selection method (gaze or mouse; dwell or switch, as in
  SPEC-input-selection-and-follow). Correct button = hit, other button = miss, nothing within the
  time limit = timeout. These map to the existing hit / miss / timeout events.
- **Effect:** the selected object animates in the scene for ~1.5-4.5 s, then the scene resets
  (Park Life section 9.3: every action resets to the idle picture).
- **Look-back:** during the effect, the object's scene region is an area of interest. Measured:
  look-back yes / no, latency from effect start to the first gaze sample (or fixation) inside the
  region, and time inside the region during the effect.
- **Split attention is built in:** in Park Life most buttons are far from their objects (Balloons
  button far left, balloons top right; Swing button far right, swing girl bottom left), so the
  look-back is a real gaze shift across the screen.

### 5.2 Requirement-by-requirement verdict

| # | Requirement | Verdict | How / why |
|---|---|---|---|
| P-1 | 7 x 5 layout with a 5 x 5 scene and 8 edge buttons | YES | `ClickGridTask` already lays out cells via `scene_spec()` "grid" mode; a new task adds a scene area |
| P-2 | Prompt per trial (voice and/or visual cue) | YES | The app already plays WAV cues with `QSoundEffect` (`src/app.py`). Voice prompts need recorded or generated audio files (Q7) |
| P-3 | Selection by gaze dwell or switch, hit / miss / timeout | YES | `BaseTask.update` already handles dwell, switch and `MISS_CLICK` |
| P-4 | Scene picture + 8 animated objects | YES (cost) | Every effect in Park Life is a simple 2D move: translate (bike, cloud), rotate (seesaw, swing), scale or fade (balloons, bubbles, apples), colour cycle (rainbow). Drawable with Qt painting or `QPropertyAnimation` on separate sprite layers. Needs a new scene renderer mode in the canvas |
| P-5 | Art, animation frames, sounds | ADAPT | Smartbox assets are encrypted and licensed; we need our own art and sounds (Q6, Q7). This is the largest cost |
| P-6 | Effect after the selection, scene reset | YES | Timed in the task; the next trial starts after the reset |
| P-7 | Look-back metrics | YES | Gaze is already recorded per sample (`all_gaze.csv`); fixations and saccades already exist (`src/data/saccades.py`). Needs per-trial object regions in the trial metadata and a new metric function |
| P-8 | Object regions in scene coordinates | YES | Our own art defines them; Park Life's measured regions (README 9.2) are a layout reference |
| P-9 | Report rows for the new measures | YES | Existing report pipeline; new columns |
| P-10 | Words / sentences / chat layer (Park Life pages 3-5) | Out of scope unless Q8 says otherwise | |

**Summary for Part B:** no hardware unknowns. The gaze stream, selection and event model are all
validated. Feasible; the cost is content (art, animation, audio) plus a new scene renderer and
look-back metrics.

### 5.3 Design questions for the later SPEC (not blocking feasibility)

- Does the effect also play after a miss (the wrong object animates), or only after a hit?
- Is the time limit counted from the end of the prompt?
- How many trials, and is the prompted button order random or balanced across left / right?
- Does the animation run on the gaze canvas without lowering its frame rate? (Measure in the
  implementation SPEC; the latency fix measured 3.26 ms mean socket-to-consumption.)

---

## 6. Live probe plan for the GP3 HD (U5)

A standalone script (no app launch, same safe shape as the 2026-08-31 latency probe), with the
user as the subject. Each step logs every raw line from Control with a timestamp.

| # | Step | Pass when |
|---|---|---|
| P1 | `CALIBRATE_SHOW STATE="0"`, 5 points, `CALIBRATE_START`. Script draws a simple dot full-screen at each `CALIB_START_PT` | `CALIB_START_PT` and `CALIB_RESULT_PT` arrive for all 5 points, `CALIB_RESULT` arrives, and `VALID_POINTS` = 5 with the window hidden |
| P2 | Same, points added in the order TL, BR, TR, BL, C at 0.10 / 0.90 | `CALIB_START_PT` `PT` and `CALX`/`CALY` follow the order and values sent |
| P3 | Measure the time from `CALIB_START_PT` to `CALIB_RESULT_PT` per point, for two `CALIBRATE_DELAY` / `CALIBRATE_TIMEOUT` pairs | It matches DELAY + TIMEOUT within ~100 ms, so the app can time the glide and the hold |
| P4 | Grid 3-fast timing (DELAY ~1.8 s, TIMEOUT ~0.3 s) vs device default (0.5 s / 1.25 s) | Record `AVE_ERROR` and per-point error in degrees for both; decide the shortest usable hold |
| P5 | Read eye position data for 30 s while the subject moves closer / further / tilts | Values change as expected and are usable for the track-status face and distance |
| P6 | (Optional) `CALIBRATE_START STATE="0"` in the middle of a run | Record what Control does; confirms or rules out a stepped mode |

### 6.1 Results without a device (2026-10-11)

The user found that Gazepoint Control runs a calibration with **no GP3 HD attached**, so the
message-level probes P1-P3 were run against the running Control (port 4242, two calibrations,
window hidden). P4 and P5 need real eyes and still wait for the device.

| Probe | Result | Evidence |
|---|---|---|
| P1 | **PASS (message flow)** | `CALIBRATE_SHOW STATE="0"` ACKed. Each run: 5 `CALIB_START_PT`, 5 `CALIB_RESULT_PT`, 1 `CALIB_RESULT`. Mid-run screenshots show no Control calibration window. `VALID_POINTS` 0, `AVE_ERROR` 1510.04 and all eye values 0: meaningless without a camera. |
| P2 | **PASS** | `CALIB_START_PT` 1-5 = (0.1,0.1) (0.9,0.9) (0.9,0.1) (0.1,0.9) (0.5,0.5), the TL, BR, TR, BL, C order sent; `CALIB_RESULT` lists the same points. |
| P3 | **PASS, +10 to +70 ms per point** | DELAY 0.5 + TIMEOUT 1.5 = 2000 ms: 2050, 2057, 2069, 2053, 2058 ms. DELAY 1.8 + TIMEOUT 0.3 = 2100 ms: 2169, 2121, 2151, 2150, 2112 ms. Start to first point 37 / 73 ms; one point's result to the next start < 0.2 ms; whole run 10.32 / 10.84 s. |

Findings for `SPEC-app-drawn-calibration.md`:

- C4 and C5 are proven **at the message level**: the app can draw its own target at each
  `CALIB_START_PT` while Control's window stays hidden. Still unproven (needs the device): that a
  hidden-window calibration is valid (`VALID_POINTS` 5) and its accuracy with a short TIMEOUT (P4).
- No record marks the end of DELAY inside a point: the app times the glide itself (DELAY seconds
  after `CALIB_START_PT`), and must allow each point to run up to about 70 ms long.
- Control sent an extra `CALIB_RESULT_PT` `PT="6"` (no matching start) 62 ms after point 5 in the
  fast run; `CALIB_RESULT` still listed 5 points. Ignore any PT above the point count; only
  `CALIB_RESULT` ends a calibration.
- `CALIBRATE_RESULT_SUMMARY` returned the same `AVE_ERROR` after both runs (retained state): do not
  use it as the result.
- Control's current `CALIBRATE_TIMEOUT` is **1.50 s**, not the 1.25 s assumed in P4; settings were
  restored (SHOW 0, DELAY 0.50, TIMEOUT 1.50) and Control stayed responsive (18-30 ms replies).

Also check after P1-P6: Gazepoint Control is not left stuck (the known issue after its
own-window calibration), and the script restores `CALIBRATE_SHOW` to the config value.

---

## 7. Open questions for the user

| # | Question |
|---|---|
| Q1 | Per-point score: accept the degree-based 0-100 formula and the colour bands in 4.4, or should the clinician set them? |
| Q2 | "Improve calibration": option I-A (full re-run, recommended), I-B or I-C (4.5)? |
| Q3 | Stepped mode cannot be copied (C9). Drop it? |
| Q4 | Track-status face colours: what should green / orange / red mean (distance, both eyes found, centred)? |
| Q5 | Should the new calibration replace the Setup page calibration, sit next to it (with Control's window as a fallback), and also be startable from inside a test? |
| Q6 | Art for the icons and the Park Life-style scene: who makes it (our own drawing, commissioned, AI-generated and checked)? |
| Q7 | Prompt language and voice: Traditional Chinese, English, or both; recorded voice or generated speech files? |
| Q8 | Park Life-style test: only page 2 style (one-word prompt, effect, look-back), or also the sentence / chat layer? |

### 7.1 Answers (user, 2026-10-10)

| # | Answer |
|---|---|
| Q1 | **Proposed formula** (4.4): score = round(100 x max(0, 1 - error_deg / 3)); green up to 1 deg, amber up to 2 deg, red above 2 deg or no valid eye. |
| Q2 | **I-A full re-run.** The results map marks the weak points. |
| Q3 | **Drop stepped mode.** Continuous only; probe step P6 is no longer needed. |
| Q4 | **Distance + both eyes:** green = both eyes found and distance in the good range; orange = one eye lost or distance at the edge; red = out of range; grey = no eyes. |
| Q5 | **Replace, with fallback:** the app-drawn calibration replaces the Setup page calibration; Gazepoint Control's own window is used automatically only if the app-drawn run fails. |
| Q6 | **AI-generated art**, through the user's own MCP server `mcp-image-openrouter` (github.com/jeffrymahbuubi/openrouter-mcp, folder `mcp-image-openrouter`). It still has to be configured; the user provides the OpenRouter API key later. The model choice is researched with the Parallel search MCP (see the log). Every asset is checked by the user before it ships. |
| Q7 | **English** prompts for now; Traditional Chinese later (the design must allow a second language). |
| Q8 | **Page 2 style only:** prompt, selection, effect, look-back. No sentence or chat pages. |

### 7.2 AI art tooling (Q6 follow-up, researched 2026-10-10)

**Tool state.** `resources/mcp-tools/openrouter-mcp/mcp-image-openrouter/` (the user's repo, at
origin/main `0bfdbb0`):

- `npm install` and `npm run build` succeeded.
- `npm test`: 192 of 193 pass. The one failure is Windows-only: `security.test.ts` "should allow
  path within temp directory" expects `\tmp\test-image.png` and gets `D:\tmp\test-image.png`.
- The server is wired into the root `.mcp.json` as `mcp-image-openrouter`, the same way as
  `mcp-audio-openrouter`: `OPENROUTER_API_KEY` comes from `${OPENROUTER_API_KEY}` in the root
  `.env`, and `IMAGE_OUTPUT_DIR` is the tool's own `output/`.
- It starts cleanly without a key. The bundled skill is installed at `~/.claude/skills/image-generation/`.
- Live generation is untested: it waits for the user's key and a session restart.

**What the tool sends today.** `src/api/openrouterImageClient.ts` sends only `model`, `prompt`,
`n: 1`, `aspect_ratio`, `resolution` and `input_references`. Its native-parameter table knows only
Gemini models; other models get aspect ratio and size folded into the prompt. It does **not** send
`background` or `output_format`, so it cannot ask for a transparent PNG, and it keeps one image
per call.

**Models (OpenRouter public API `GET /api/v1/models?output_modalities=image` and
`/api/v1/images/models`, read 2026-10-10; 60 image models listed).**

| Need | Candidate | Why | Price (OpenRouter, 2026-10-10) |
|---|---|---|---|
| Style anchor, scene, drafts | `google/gemini-3-pro-image` (tool's `quality` tier) and `google/gemini-3.1-flash-image` (tool default) | Already supported natively by the tool; reference images (`input_references`) for keeping one style | output image $0.00012 / token (pro), $0.00006 / token (flash) |
| A consistent style across many assets | `recraft/recraft-v4-styles` (and `-pro`) | Built for "style it once, every image matches". Recraft's own blind test claims 92 % preference; that is a vendor claim, not independent | per-image pricing on Recraft endpoints |
| Transparent PNG icons and sprites (calibration icons, scene objects) | `openai/gpt-image-1-mini` (cheapest), `openai/gpt-image-2.5-flare`, `openai/gpt-5-image(-mini)`, `sourceful/riverflow-v2.5-pro` | The only models whose endpoint lists `background: transparent` (`openai/gpt-image-2` lists only auto / opaque) | gpt-image-1-mini output image $0.000008 / token; riverflow-v2.5-pro $0.13-0.17 / image |
| Split one finished scene into separate object layers for animation | `inclusionai/ming-image-0.1-design-layer` | Image-to-image layer decomposition: a flattened picture plus a layer plan gives N transparent RGBA layers (MIT licence, Hugging Face model card) | listed $0 via NovitaAI on OpenRouter (check before use) |
| Scalable vector icons | `recraft/recraft-v4.1-vector` / `-pro-vector` | SVG output | $0.08 / $0.30 per image |

**Recommended pipeline for the later SPEC.**

1. Make one style anchor with `gemini-3-pro-image` (or Recraft V4 Styles) and have the user approve it.
2. Make each calibration icon and each scene object as a transparent PNG with a transparent-capable
   model, using the anchor as `input_references`.
3. Make the scene background separately.
4. Fallback for object layers: split a full scene with `ming-image-0.1-design-layer`.

The user approves every asset (Q6).

**Gaps in the tool for that pipeline (the user's repo, so the user decides):**

- (a) Pass `background` and `output_format` through to transparent-capable models.
- (b) Save all returned images, not one, for the layer model.
- (c) Add native-parameter entries for the non-Gemini models.

Without (a), the fallback is to generate on a flat key colour and remove it locally (numpy and
PySide6 are already in `dev/.venv`).

## 8. Proposed follow-up SPECs

1. `SPEC-app-drawn-calibration.md` - after probe P1-P5 pass: C1-C8, C10-C14, C16-C19, icon set,
   score, results map, improve option, track-status widget, Control-window fallback.
2. `SPEC-scene-cause-effect-task.md` - the Park Life-style test: scene renderer, 8 effects,
   prompts, hit / miss / timeout, look-back metrics, report columns, assets.

The scene test does not depend on the probe and can be specified first.

## 9. Log

- **2026-10-10** - Study created. Inputs: commit `5b5cb91` (calibration video write-up and Park
  Life analysis with the live walk-through), the Open Gaze API corpus, `src/engine/calibration.py`
  and `configs/default.yaml` as of `5b5cb91`, Smartbox / SET-BC public docs (web search), and a
  live look at Grid 3 Settings > Access > Eye gaze > Camera (no Gazepoint in the list;
  calibration settings greyed out with camera None; dialog closed without saving). User
  decisions U1-U5 recorded (section 3). Verdicts: Part A 10 YES, 3 YES with an adapted part, 2 ADAPT,
  2 NO, 2 PROBE (custom icon C4, animation C5); Part B feasible with no hardware unknowns. Open: Q1-Q8, probe P1-P6.
- **2026-10-10 (later)** - The user answered Q1-Q8 (section 7.1):
  - proposed score formula;
  - full re-run for Improve;
  - stepped mode dropped (probe P6 no longer needed);
  - face colours = distance + both eyes;
  - the app-drawn calibration replaces Setup's, with a Control-window fallback;
  - AI art via the user's `mcp-image-openrouter`;
  - English prompts first;
  - page 2 scope only.
- Q6 follow-up done (section 7.2):
  - `mcp-image-openrouter` was built, tested (192 of 193 pass; one Windows-only path test fails), wired into the root `.mcp.json` and smoke-started without a key.
  - The bundled skill is installed.
  - Image models were compared from the OpenRouter public API. The tool cannot request transparent PNGs yet.
  - Live generation waits for the user's API key and a session restart.
- **2026-10-10 (end of session)** - Follow-up status:
  - `SPEC-scene-cause-effect-task.md` was written (`33fa68d`), approved (`84271e7`), and its step 1 wireframe approved (`16dc79a`).
  - The user said the image server uses the same OpenRouter key as the audio server, and that key is already in the root `.env`, so no new key is needed; the image tools load after a Claude Code restart.
  - Still open: image-tool gaps (section 7.2), probe P1-P5.
- **2026-10-11** - Probes P1-P3 run against Gazepoint Control with no device (the user found
  Control calibrates without one): all pass at the message level (section 6.1). New facts: extra
  `CALIB_RESULT_PT` PT 6, points run 10-70 ms long, no DELAY/TIMEOUT boundary record, stale result
  summary, Control TIMEOUT 1.50 s. P4-P5 still need the GP3 HD.
- **2026-10-13** - Follow-up SPECs written and approved: `SPEC-app-drawn-calibration.md` (`e587da4`; decisions D1-D8, incl. Speed via `CALIBRATE_DELAY`/`CALIBRATE_TIMEOUT` and Size drawn by the app) and `SPEC-gaze-stability-and-positioning.md` (`5a035d7`; it takes over C17/C18, the head-position widget). Probes P4-P5 move into those SPECs' live steps.
