---
name: SPEC-gaze-stability-and-positioning
title: Steadier gaze cursor (FPOG / APOG signal, One Euro filter) and a live head-position widget (Grid 3-style face + Close-Far bar)
status: IMPLEMENTED 2026-10-13 - parts A + B merged and committed (hub review, pytest 4164 passed, 5 known worktree-baseline failures); live check on the GP3 HD (plan step 5) pending
created: 2026-10-13
last_updated: 2026-10-13
next_step: implement 4.9 (G9-G11: Fixation removed, Assistive forces app smoothing off, card reworded) by spec-implementer; then finish the live comparison (App smoothing Simple 0.05 vs Adaptive 0.3/5.0 vs Gazepoint Assistive AAC 15/30) and set the winner as default
related:
  - SPEC-gaze-cursor-redesign.md (frozen pointer on invalid samples; cursor look)
  - SPEC-gui-audit-2026-09-10.md (alpha 0.22 chosen live)
  - SPEC-preview-gaze-pointer.md (Mouse pointer is never smoothed; Gaze Preview on the Start page)
  - SPEC-live-settings-panel.md (settings registry + profiles)
  - SPEC-gazepoint-analysis-export-parity.md (section 10.1: 3D eye position, eye_geometry.csv)
  - SPEC-grid3-calibration-parklife-feasibility.md (C17 track-status widget, probe P5 - this SPEC takes C17 over)
  - docs/calibration-video/README.md (Grid 3 track-status face, frames 02, 15-17, 33-35)
  - docs/gazepoints/sources/gazepoint-api.md (5.1 FPOG, 5.7 BPOG, 5.8 APOG, 3.22 AAC_FILTER, 5.11/5.12 eye position)
---

# SPEC-gaze-stability-and-positioning

**Status: IMPLEMENTED 2026-10-13 (parts A + B, hub-reviewed); the live check on the GP3 HD is pending.**

## 1. Origin

User, 2026-10-13:

1. They always set the gaze smoothing to the lowest value, 0.05, because 0.25 and above still
   look "shaky". The hub explained the cost: the plain running average (EMA) is steady only by
   being slow. At 150 Hz, 0.05 needs about 0.4 s to catch up 95 % of a gaze jump
   (about 1 s at 60 Hz on USB 2).
2. "Is smoothing alpha the only parameter for shakiness?" The hub found that the cursor follows
   Gazepoint's **raw best POG (`BPOG`)**, which has no filtering at all
   (`src/inputs/gazepoint_client.py:274`). Gazepoint's own manual says: "For most
   applications, use the FPOG which includes fixation filtering of the BPOG data"
   (API 5.7).
3. The user asked for a SPEC covering both remedies: a steadier gaze signal, and the One Euro
   filter.
4. The user also saw that the **green circle in Gazepoint Control** (the head-distance dot on
   the Close-Far bar, `resources/images/gazepoint-control-testing.png`) strongly affects how
   accurately gaze lands on a target. Our app has no such indicator. They want something like
   the **Grid 3 track-status widget** from the calibration video: a stylised face in a box that
   moves, tilts and resizes with the head, and turns green, orange or red.

### 1.1 "Does the Gazepoint API have a filter?" (answered)

Yes, two, and nothing else.

| Signal | Filter | Settable? |
|---|---|---|
| `BPOG` (today's cursor) | None. The average of the two eyes' POG. | - |
| `FPOG` | Gazepoint's internal **fixation filter**. The point holds steady within a fixation and jumps to the next fixation. `FPOGV` is 0 during saccades and blinks. | No. The fixation thresholds are not exposed in the API. |
| `APOG` (API 2.7+) | **Moving-window average of `FPOG`**, made for eye typing and Windows Eye Control. | Window length via `AAC_FILTER` (default 15 samples, about 0.1 s at 150 Hz). It is the same setting as Control's "Cursor Smoothing" slider, so it is **shared with Windows Eye Control on that PC**. |

The API has no adaptive (speed-dependent) filter. The One Euro filter (section 4.3) fills that
gap on our side.

## 2. Decisions (user, 2026-10-13)

- **G1 - Indicator placement:** the Setup page Calibration card, and the Start-test page.
  Not the run bar, and not the child's canvas.
- **G2 - Indicator look:** like the Grid 3 track-status widget: a face in a head box plus a
  Close-Far bar. The hub's feasibility verdict is in section 4.5.
- **G3 - Gaze signals offered:** `FPOG`, `APOG`, and the One Euro filter, next to today's
  `BPOG` + EMA.
- **G4 - Recording:** record the cursor signal too, as extra columns next to the raw data
  (section 4.4). The raw `BPOG` data and every metric derived from it stay unchanged.
- **G5 (Q1) - Defaults stay `best` + `ema`** until the live check picks a winner; the new signals
  and filter are opt-in.
- **G6 (Q2) - No "Eyes" view**; the face only.
- **G7 (Q3) - Restore `AAC_FILTER`** to Gazepoint's original value on disconnect and app close.
- **G8 (Q4) - Show the operator hint text** ("Move closer", "Good position", ...).
- **G9 (live check 2026-10-13) - Fixation (FPOG) is removed** from the choices: the user found it
  "jumpy" (it freezes during every eye movement, then jumps). A saved profile or config that still
  says `fixation` loads as Raw gaze with its own smoothing, and the session log notes the fallback.
- **G10 (live check 2026-10-13) - Assistive turns the app's smoothing off.** Assistive + any app
  smoothing "lags a lot" (two averages in a row). With Assistive, the app's smoothing is not
  applied, whatever the smoothing settings say, and its controls are greyed.
- **G11 - Two approaches, named as such.** The user's model: **App smoothing** = raw gaze (BPOG)
  plus our own filter (Simple or Adaptive); **Gazepoint Assistive** = Gazepoint's own filtered
  signal (APOG, tuned only by the AAC filter length). The card shows one radio "Cursor
  stabilisation" with those two choices (section 4.9).

## 3. Current code (as of `cbaa4c5`)

- `rec_to_sample` (`src/inputs/gazepoint_client.py:264`) builds one `GazeSample` from `BPOG`,
  falling back to `FPOG` when `BPOG` is invalid. That sample is both the **recorded** gaze
  (`gaze_stream.csv`, `x`/`y`) and the **pointer** input.
- `EyeInput.poll` (`src/inputs/eye_input.py:214`) runs the sample through `GazeSmoother`, a
  plain EMA (`dwell.smoothing.enabled` / `alpha`, default 0.22). It freezes the pointer and
  resets the average on an invalid sample.
- The 3D eye position (`LEYEX/Y/Z`, `REYEX/Y/Z`, metres from the camera focal point, plus the
  `LPUPILV`/`RPUPILV` validity flags) is already subscribed (`ENABLE_SEND_EYE_LEFT/RIGHT`,
  `gazepoint_client.py:75`). It is written to `eye_geometry.csv` but shown nowhere.
- `APOG` is not subscribed (`ENABLE_SEND_POG_AAC` is missing from `_ENABLE_RECORDS`).
  `AAC_FILTER` is never sent.
- The report's Detailed view redraws the gaze path by replaying the EMA over the recorded raw
  samples (`src/data/report_visual.py:53`, `SmoothParams`).
- The fake tracker (`tools/fake_gazepoint_server.py:94`) sends a fixed eye position
  (Z = 0.65 m) and no `APOG`.

## 4. Design

### 4.1 Gaze signal (new setting `dwell.pointer_signal`)

| Value | Label | Pointer source | Invalid when |
|---|---|---|---|
| `best` (default) | Raw gaze (BPOG) | `BPOG`, falling back to `FPOG` (exactly today) | both invalid |
| `fixation` | Fixation (FPOG) | `FPOG` only | `FPOGV` = 0 (also during every saccade) |
| `assistive` | Assistive (APOG) | `APOG` only | `APOGV` = 0 |

- `GazeSample` gains `pointer_x`, `pointer_y` and `pointer_valid`, filled from the chosen signal
  by the client. Its `x`/`y`/`valid` stay exactly as today (`BPOG`, then `FPOG`), so the
  recorded raw gaze and every metric derived from it are unchanged.
- `EyeInput.poll` drives the pointer from `pointer_*` and records from `x`/`y`, as now.
- The client always subscribes to `ENABLE_SEND_POG_AAC`, so a run can switch to `assistive`
  without reconnecting.
- **Saccade behaviour with `fixation` / `assistive`:** the invalid frames freeze the cursor (the
  existing path). The dwell's `hold_grace_ms` must bridge those gaps, so a dwell on one target is
  not reset by the small eye movements within it. This is acceptance criterion A4, checked live.
- Mouse pointer: unaffected. The setting is disabled when Pointer = Mouse, like smoothing today
  (`settings_registry.py:445`).

### 4.2 `AAC_FILTER` (new setting `dwell.aac_filter_samples`, shown only for `assistive`)

- Integer 1-60, default 15 (the device default).
- Sent as `<SET ID="AAC_FILTER" VALUE="n" />` when a run starts with `assistive`, and the ACK
  is logged.
- **Shared setting:** on connect, the client reads the current value
  (`<GET ID="AAC_FILTER" />`). On disconnect and app close it restores that value, so Windows
  Eye Control on the same PC keeps its own smoothing. User decision G7.

### 4.3 Smoothing type (new setting `dwell.smoothing.type`)

| Value | Label | Behaviour |
|---|---|---|
| `ema` (default) | Simple | Today's `GazeSmoother` with `alpha`. |
| `one_euro` | Adaptive (One Euro) | Casiez et al., CHI 2012. Per axis, a low-pass filter whose cutoff rises with speed: `cutoff = min_cutoff + beta * abs(speed)`. Steady when the eyes rest, fast when they jump. |

- One Euro parameters, shown only for `one_euro`:
  - `dwell.smoothing.min_cutoff_hz` (label "Steadiness"; lower = steadier). Starting default
    0.3 Hz (user decision 2026-10-13; it meets A3), range 0.05-5.
  - `dwell.smoothing.beta` (label "Responsiveness"; higher = less lag on jumps). Starting default
    5.0 (user decision 2026-10-13), range 0-10, in screen widths / heights per second: the filter
    runs on the monitor-normalised pointer that `EyeInput.poll` returns, the same space as the raw
    gaze (the task converts it to canvas coordinates afterwards). In fullscreen the two are the same.
  - The derivative cutoff is fixed at 1.0 Hz (the paper's recommendation; not a setting).
- The filter uses the real time between frames (`t_ns` from `poll`), not a fixed rate. It resets
  on an invalid sample, exactly as the EMA does.
- The smoothing type applies to whichever signal is chosen (4.1). Example: `FPOG` + One Euro.
- Both defaults are starting values to tune at the live check (plan step 5). The final defaults
  are written back here.
- `alpha` is disabled unless `ema` is selected. `min_cutoff_hz` and `beta` are disabled unless
  `one_euro` is selected. All smoothing settings stay disabled for Pointer = Mouse.

### 4.4 Recording (G4)

- `gaze_stream.csv` gains three trailing columns: `pointer_x`, `pointer_y` and `pointer_valid`.
  They hold the cursor position actually used for drawing and hit-testing (signal plus filter),
  canvas-normalised.
- The columns go **at the end**, so old readers that use column names keep working.
  `docs/DATA_SCHEMA.md` is updated.
- `metadata.json` (via the settings snapshot) records `pointer_signal`, `aac_filter_samples`
  (null unless `assistive`), `smoothing.type`, `alpha`, `min_cutoff_hz` and `beta`.
- **Report:** when `pointer_x`/`pointer_y` exist, the Detailed view draws the recorded pointer
  path instead of replaying the EMA. Older sessions keep the replay (`SmoothParams`). The
  report's config table shows a "Gaze signal" row and the existing "Gaze smoothing" row (user decision
  2026-10-13: the label stays "Gaze smoothing"; its text names the adaptive filter and its two settings).
- On a Mouse test the three pointer columns are blank: the mouse path is already in
  `pointer_stream.csv`, and a tracker recording alongside writes only the raw gaze.
- `all_gaze.csv` keeps its 62 Analysis columns. `APOG` is not added there.

### 4.5 Head-position widget: feasibility of the Grid 3 look (G2)

What the Grid 3 widget does (video README section 5, frames 02, 15-17, 33-35), and whether our
data supports it:

| Grid 3 behaviour | Our source | Feasible? |
|---|---|---|
| Face moves left/right/up/down in the box | Midpoint of (`LEYEX`,`LEYEY`) and (`REYEX`,`REYEY`), mapped onto the GP3 HD head box (35 x 22 cm, `gp3-hd-specifications.md`) | **Yes** |
| Face grows/shrinks with distance | Mean of `LEYEZ`/`REYEZ` (metres); operating range 50-80 cm | **Yes** |
| Face tilts (head roll) | `atan2` of the line from the left eye to the right eye in X/Y | **Yes** |
| Green / orange / red with a smile / flat / frown mouth | Our own rules (4.6). Grid 3's meaning is unlabelled (README section 8). | **Yes**, with our rules |
| Empty grey box + "No eyes detected" | Neither eye valid (`LPUPILV`/`RPUPILV` = 0) for more than 0.5 s | **Yes** |
| "Face" / "Eyes" view toggle | "Eyes" = two dots only | Yes, but **out of scope** (G6) |

Plus a **Close-Far bar** under the box, like Gazepoint Control: a dot on a 45-85 cm scale with
the 55-75 cm band shaded green, and the distance as text ("64 cm").

**Unknowns that only the device can settle (plan step 5, also feasibility probe P5):**
- the sign conventions of X/Y (which way is "left" and "up"), and whether the face should mirror
  the child (proposal: mirror, like a selfie camera, so the face moves the same way the child
  does for an operator sitting beside them);
- the Y value of a well-seated head. The camera sits below the screen, so "centred" is not
  Y = 0; it is measured and stored as a constant;
- the hints ("Move left", "Move up", ...) name the way to move **on the picture** (a face drawn
  right of centre gives "Move left"), so they follow `DISPLAY_X_SIGN` / `DISPLAY_Y_SIGN`, which are
  settled at probe P5 (accepted by the user, 2026-10-13);
- whether `LEYEZ` tracks real distance well enough. Check it with a tape measure at 50, 65 and
  80 cm.

The fake tracker gains a slow head drift (X/Y/Z, plus a 3-second "no eyes" gap every 20 s), so
the widget can be tested without the device.

### 4.6 Colour rules (proposal; tuned at the live check)

| State | Rule | Face | Hint text |
|---|---|---|---|
| Green | Both eyes valid, Z in 55-75 cm, face centre inside the inner 70 % of the box | Smile | "Good position" |
| Orange | Only one eye valid, or Z in 50-55 / 75-80 cm, or the centre in the outer 30 % band | Flat mouth | "Move back" (Z under 55 cm, too near the tracker) / "Move closer" (Z over 75 cm) / "Move left" / "Move right" / "Move up" / "Move down" (the largest fault first); "Only one eye seen" when one eye is the only fault |
| Red | Z under 50 or over 80 cm, or the centre outside the box | Frown | Same hints |
| No eyes | Neither eye valid for more than 0.5 s | Empty grey box | "No eyes detected" |

- The hint text is an addition (G8); Grid 3 shows none. It helps the operator. "Move left / right /
  up / down" name the way to move on the picture (4.5). "Only one eye seen" (the user's wording,
  2026-10-13) shows only when no position fault is larger; a fault's hint wins over it.
- The state is smoothed over about 0.3 s so the colour does not flicker at a boundary: a new colour
  or a new hint (the pair) shows only after it has held 0.3 s; the face and the distance follow the
  data at once. "No eyes detected" waits 0.5 s from the first frame without eyes.
- **Stale data:** eye data older than 1 s (`STALE_AFTER_S`) counts as no eyes, so a stopped or paused
  stream (calibration pauses the reader) never leaves a frozen face on screen. Accepted by the hub,
  2026-10-13.
- The widget is drawn with `QPainter` in the WTMH design tokens. Green, orange and red use the
  existing success, warning and danger tokens, never raw hex values.

### 4.7 Placement (G1)

- **Setup page, Calibration card:** the widget sits to the right of the calibration buttons
  (stacked under them in a narrow window). It is live whenever the tracker is connected; when not
  connected it shows "Tracker not connected". It updates at about 15 Hz from a `QTimer` on the
  GUI thread, reading the client's latest eye-position values (a new `latest_eye_position()`
  accessor, thread-safe like `latest()`).
- **Start-test page:** the same widget in the clinician area, for gaze tests only (hidden for
  Pointer = Mouse).
- **Never gates anything.** It is information for the operator; Do Calibration and Start stay as
  they are.
- **Recorded:** each run's `metadata.json` gets `head_position_at_start`:
  `{"state", "z_cm", "centre_x_cm", "centre_y_cm"}` at the moment Start is pressed. `state` is
  `green`, `orange`, `red`, `no_eyes` or `not_connected` (the one the operator sees); `z_cm` is the
  eye distance and `centre_x_cm` / `centre_y_cm` the eye midpoint's offset from the well-seated
  position on the device's X / Y axes, one decimal each, null when no eyes were measured. Null for a
  Mouse run. The full stream is already in `eye_geometry.csv`.

### 4.8 Settings registry and profiles

- The new keys join the existing "Gaze Smoothing" group (`settings_registry.py:469`), in this
  order: Gaze signal, AAC filter length, Smoothing on/off, Smoothing type, Alpha, Steadiness,
  Responsiveness.
- They are saved in settings profiles like every other key.
- An old profile without them loads as `best` + `ema`, so it behaves exactly as today.

### 4.9 Revision after the live check (G9-G11, 2026-10-13)

- **Card layout** (wireframes `task-config.md`, `choice-making.md`), top to bottom:
  1. **Cursor stabilisation** (radio): **App smoothing (raw gaze)** (default) / **Gazepoint
     Assistive (APOG)**. It stores `dwell.pointer_signal` as `best` / `assistive`, the same keys
     as before.
  2. **AAC filter length**: active only for Gazepoint Assistive.
  3. **Smoothing enabled**, **Smoothing type** (Simple / Adaptive), **Smoothing alpha**,
     **Steadiness**, **Responsiveness**: active only for App smoothing, with the same greying among
     themselves as before.
- **Fixation removed (G9):** `fixation` is no longer offered. `normalize_signal` maps `fixation`
  (an old profile, config or hand edit) to `best`, and the run's session log says "Gaze signal
  'fixation' is no longer offered; using App smoothing (raw gaze)." The FPOG code path in
  `pointer_from_rec` may stay as an internal function but is unreachable from settings.
- **Assistive forces the app's smoothing off (G10):** the smoother is built disabled for
  `assistive`, whatever `dwell.smoothing.enabled` says. The settings keep their saved values, so
  switching back to App smoothing restores them.
- **Recording and report:** `metadata.json` records the settings as saved, plus
  `smoothing_applied` (bool, false for Assistive). The report's "Gaze signal" row reads "App
  smoothing (raw gaze)" or "Gazepoint Assistive (APOG), AAC filter 15 samples". The "Gaze
  smoothing" row reads "Off (Gazepoint Assistive)" for Assistive runs; it is unchanged otherwise.
  Older sessions with `fixation` show "Fixation (FPOG), no longer offered".
- **Defaults unchanged:** App smoothing with Simple (G5), until the comparison of App smoothing
  (Simple 0.05 vs Adaptive 0.3 / 5.0) and Gazepoint Assistive (AAC 15 / 30) picks a winner.

## 5. Scope

**In:** sections 4.1-4.8; the fake tracker's `APOG` and head drift; `DATA_SCHEMA.md`;
`CLINICAL_DATA_REFERENCE.md` (one paragraph: the pointer columns are UI signals, not analysis
inputs); tests.

**Out:**
- the Eyes view (G6);
- any gate on head position;
- an indicator on the child's canvas or the run bar (G1);
- changing the recorded raw `x`/`y`;
- `APOG` in `all_gaze.csv`;
- the app-drawn calibration (its own SPEC; it will reuse this widget);
- changing the defaults before the live check.

## 6. Acceptance criteria

| # | Criterion | Checked by |
|---|---|---|
| A1 | `best` + `ema` with the same alpha gives the same pointer as before for any input stream | unit test against today's `GazeSmoother` |
| A2 | `fixation` / `assistive` drive the pointer from `FPOG` / `APOG`; the recorded `x`/`y` stay `BPOG` | unit test on `rec_to_sample` + recorder |
| A3 | One Euro: with synthetic 0.5 % jitter at rest, the pointer's spread is at most 1/4 of the EMA-0.35 spread; after a step jump, the pointer reaches 95 % in at most 0.15 s at 150 Hz | unit test |
| A4 | With `fixation`, a dwell on a target completes even though FPOGV drops to 0 during microsaccades shorter than `hold_grace_ms` | unit test + live |
| A5 | `AAC_FILTER` is sent on a run start with `assistive`, and the original value is restored on disconnect and close | unit test with the fake server + live log |
| A6 | `gaze_stream.csv` has `pointer_x/y/valid` at the end; old sessions still load in the report | unit test |
| A7 | The report draws the recorded pointer path when present, and the replay otherwise | unit test |
| A8 | The widget maps X/Y/Z to position, size and tilt; the colour follows 4.6; "No eyes detected" after 0.5 s | unit test on the pure model + offscreen paint test |
| A9 | The widget is live on Setup and Start-test (gaze tests only) and gates nothing | live |
| A10 | Old settings profiles load as `best` + `ema` | unit test |
| A11 | Full pytest stays green | hub rerun |
| A12 | The card offers only App smoothing / Gazepoint Assistive; `fixation` loads as `best` with a session-log note | unit test |
| A13 | With Assistive, the pointer is never smoothed by the app (same output with smoothing on or off) and the smoothing controls are greyed; switching back restores the saved values | unit test |
| A14 | Report rows and `smoothing_applied` follow 4.9 for best, assistive and an old fixation session | unit test |

## 7. Plan

1. **DONE 2026-10-13 - Wireframe** (`setup.md` Calibration card, `start-test.md` clinician area, the Gaze Smoothing
   card in `task-config.md` and `choice-making.md`). This is user GATE 1.
2. **DONE 2026-10-13 -** **Implement part A:** signals + `AAC_FILTER` + One Euro + recording + report + settings
   (4.1-4.4, 4.8).
3. **DONE 2026-10-13 -** **Implement part B:** head-position widget + fake tracker drift + metadata (4.5-4.7).
4. **DONE 2026-10-13 -** Hub review, then the full pytest.
5. **Live check on the GP3 HD, with the user as subject:**
   - probe P5: X/Y signs, the centred Y value, Z against a tape measure;
   - tune the 4.6 bands;
   - compare side by side on a Grid Click / Choice-making target: BPOG + EMA 0.05, FPOG,
     APOG 15, BPOG + One Euro, FPOG + One Euro;
   - write the chosen defaults back into this SPEC.
6. Commit (on the user's OK); the defaults are changed only on the user's word.

## 8. Impl log

### 2026-10-13 - Part A (4.1-4.4, 4.8; A1-A7, A10), spec-implementer, `claude-sonnet-5-5`

Worktree `gaze-stability-a` at `5a035d7`. Not committed, not staged.

**New source files**
- `src/inputs/gaze_signal.py` - the signal / smoothing-type names, labels, `AAC_FILTER` range, `pointer_from_rec`
  (BPOG / FPOG / APOG per record) and `apply_gaze_signal` (what a run start does to the tracker, returns the
  session-log lines).
- `src/inputs/one_euro.py` - `OneEuroFilter` (per axis, real `dt` from `t_ns`, `d_cutoff` fixed 1 Hz).
- `src/ui/gaze_settings.py` - the seven live settings of the Gaze Smoothing card, their greying rules and
  `gaze_live_values` (split out of `settings_registry.py`, which stays under 500 lines).

**Changed source files**
- `src/data/schema.py`, `src/data/recorder.py` - `GazeSample.pointer_x/y/valid`; `gaze_stream.csv` gets
  `pointer_x,pointer_y,pointer_valid` as its last three columns (blank when `None`).
- `src/inputs/gazepoint_client.py` - `rec_to_sample(attrs, t_ns, pointer_signal)`; always sends
  `ENABLE_SEND_POG_AAC`; `DeviceInfo.aac_filter` (GET on connect); `set_pointer_signal`, `set_aac_filter`,
  `restore_aac_filter` (called by `stop()`); the reader logs the `AAC_FILTER` ACK.
- `src/inputs/eye_input.py` - `SmoothingConfig.type/min_cutoff_hz/beta`; `GazeSmoother` delegates to the One Euro
  filter (needs `t_ns`); `EyeInput.poll` drives the pointer from `pointer_*` (falls back to `x/y/valid` where a
  source has none) with `t_ns`; the recorded raw sample is untouched.
- `src/app.py` - builds the smoother from the new settings, calls `apply_gaze_signal` for a gaze test (session
  log lines), and records the cursor (`_with_cursor`: canvas-normalized, from `task.pointer_to_canvas_norm`)
  in `gaze_stream.csv` for a gaze run (blank for a Mouse run).
- `src/ui/setup_page.py` (`release_tracker`), `src/ui/dashboard_window.py` (`closeEvent` calls it) - the
  `AAC_FILTER` restore on app close.
- `src/ui/setting_types.py` (`LiveSetting.choices`, kind `choice`), `src/ui/settings_registry.py`
  (`greyed_by` is now a tuple of `(key, value)` pairs; the card's seven controls in the wireframe order),
  `src/ui/config_form.py` (one greyed-when entry per pair), `src/ui/settings_snapshot.py`
  (`run_settings` records `dwell.aac_filter_samples` as `null` unless the signal is `assistive`).
- `src/data/report_eye.py` (`load_cursor_frames`), `src/data/report_cache.py` (the Detailed view draws the
  recorded cursor path when present, else the existing replay; `params.path.smoothing.enabled` is false then),
  `src/data/report_config.py` (new "Gaze signal" row; the "Gaze smoothing" row describes the adaptive filter;
  18 rows). `REPORT_VERSION` unchanged (5): an older folder gives the same report as before.
- `tools/fake_gazepoint_server.py` - APOGX/APOGY/APOGV (moving average of FPOG over the AAC window) when
  `ENABLE_SEND_POG_AAC` is on; ACKs `GET` / `SET` of `AAC_FILTER` (default 15, 1-60). The head drift is part B
  and was not done.
- `docs/DATA_SCHEMA.md`, `docs/CLINICAL_DATA_REFERENCE.md` (one paragraph: the pointer columns are UI signals,
  not analysis inputs).

**Tests added** (87): `tests/test_one_euro.py` (A1, A3), `tests/test_gaze_signal.py` (A2, A4, `apply_gaze_signal`),
`tests/test_aac_filter.py` (A5, A6, fake server socket, run recording), `tests/test_gaze_settings.py` (4.8, A10,
page greying), `tests/test_gaze_report.py` (A7, report rows, fake server). **Existing tests updated** for the
new rows / columns / greying shape: `test_settings_layout`, `test_input_settings`, `test_task_config_page`,
`test_preview_gaze_pointer`, `test_report_config`, `test_report_cache`, `test_report_page`,
`test_report_pdf_phase4`, `test_report_tables`, `test_follow_report`, `test_follow_run`, `test_eye_geometry`,
`test_run_settings_metadata`, `test_gazepoint_client`, `tests/report_fixtures.py` (the rig run now records
`dwell.pointer_signal: "best"`).

**pytest (full run, JUnit):** 4060 tests, 4055 passed, 5 failed, 0 errors. The 5 failures are exactly the known
fresh-worktree baseline (the skip-worktree `default.yaml`, alpha 0.35 vs 0.22): `test_config_flow::
test_a_new_test_opens_at_standard_with_the_task_defaults` and `test_task_config_page::
test_a_new_test_opens_with_standard_and_the_defaults` x4. No other failure. Not run: A8, A9 (part B), any
live check.

**Deviations from the SPEC:** none in behaviour. Four points the SPEC left open were implemented the
minimal way and are written up in section 9 as Q5-Q8 (A3 against the starting defaults, the report row
label, the pointer columns on a Mouse run, the units of `beta`); the hub answered all four the same day
(see below). Size note: `gazepoint_client.py` (856 lines),
`app.py` and `setup_page.py` were already over 500 lines before this change.

**Left undone:** nothing in scope. Not touched: `configs/default.yaml`, `configs/local_state.json`, the
wireframes (`docs/wireframes/report-summary.md` still shows 17 config rows; `task-config.md` and
`choice-making.md` draw Steadiness and Responsiveness at 1.0, now 0.3 and 5.0).

### 2026-10-13 (later) - hub answers to section 9 applied, `claude-sonnet-5-5`

- **Q5:** the One Euro starting defaults are now `min_cutoff_hz` 0.3 and `beta` 5.0 (`gaze_signal.py`
  constants, so `SmoothingConfig`, `OneEuroFilter` and the registry all follow). The A3 tests use the defaults
  (no test-only values); a new test pins the two numbers. SPEC 4.3 updated.
- **Q6:** label kept ("Gaze smoothing"); SPEC 4.4 now names both rows. **Q7:** one line added to 4.4.
  **Q8:** the 4.3 wording now says screen widths / heights per second.
- **pytest (full run after the change, JUnit):** 4061 tests, 4056 passed, 5 failed, 0 errors. The 5 failures
  are the same fresh-worktree baseline as above (alpha 0.35 vs 0.22: `test_config_flow` x1,
  `test_task_config_page` x4). No other failure.

### Part B - head-position widget (4.5-4.7; A8, A9 by test, A11) - 2026-10-13, claude-sonnet-5-5

Worktree `gaze-stability-b` (branch at `5a035d7`), nothing committed or staged.

**New files**
- `src/inputs/head_position.py` - the pure, Qt-free model. `EyePosition` (+ `eye_position_from_attrs`),
  `assess()` (eye XYZ -> face centre / scale / roll in the head box, the state green / orange /
  red / no eyes / not connected per 4.6, the hint text, the metadata dict) and `HeadPositionTracker`
  (0.3 s colour hold, 0.5 s no-eyes delay, instant not-connected). Every device-dependent constant
  is a named module constant commented "tuned at the live check (SPEC 4.5/4.6, probe P5)":
  `DISPLAY_X_SIGN`, `DISPLAY_Y_SIGN` (+1 = mirror view), `CENTRED_X_CM`, `CENTRED_Y_CM` (placeholder
  0.0, to be measured), `NOMINAL_EYE_SEPARATION_CM`, the Z / centre bands, `FACE_REFERENCE_CM`.
- `src/ui/head_position_widget.py` - `HeadPositionWidget` (QPainter): head box 35 : 22 with the inner
  70 % lighter, the egg face (smile / flat / frown) that moves, grows and tilts, the Close-Far bar
  (45-85 cm, 55-75 band in green, dot at the distance). Only design tokens (SUCCESS / WARNING /
  DANGER, HEADER, PAGE, PANEL, SLIDER_GROOVE, ...), no raw hex (a test greps the sources).
- `src/ui/head_position_panel.py` - `HeadPositionPanel`: "Head position" heading, the picture and
  one status line (the existing `StatusBadge`: circle / triangle / square + hint + distance); a
  `QTimer` at 67 ms (~15 Hz) that runs only while the panel is shown; `snapshot()` for the metadata.
- Tests: `tests/test_head_position.py` (55: model mapping, roll, states, hints, boundaries,
  largest-fault-first, one eye, no eyes / stale, tracker timing, client accessor incl. a live socket),
  `tests/test_head_position_widget.py` (28: painted pixels in the token colours, face moves / grows /
  tilts, mouth shapes, the bar, the panel and its timer), `tests/test_head_position_flow.py` (25:
  Setup and Start placement, Mouse hiding, gates nothing, `metadata.json`, the fake tracker's drift).

**Changed files (small, additive)**
- `src/inputs/gazepoint_client.py` - only `latest_eye_position()` (lock-protected like `latest()`),
  the `_latest_eye` field set in `_set_latest`, cleared in `_clear_latest`. `rec_to_sample`,
  `_ENABLE_RECORDS` and AAC handling are untouched.
- `tools/fake_gazepoint_server.py` - `head_pose(t)`: slow X / Y / Z / tilt drift and a 3 s no-eyes
  gap every 20 s (valid flags 0, positions zeros); `eye_geometry_attrs` takes an optional pose
  (default = the old still head, so its old test is unchanged). No APOG.
- `src/ui/page_layout.py` - `BesideRow` (side widget beside the main one, under it below 640 px).
- `src/ui/setup_page.py` - the panel in the Calibration card beside the buttons; `head_position_input()`.
- `src/ui/start_test_page.py` - the panel at the end of the clinician block, hidden for a Mouse
  test; `set_head_position_source()`, `head_position_at_start()`.
- `src/ui/run_flow.py` - hands the Start page the Setup page's source and passes the reading to the run.
- `src/app.py`, `src/data/schema.py` - `head_position_at_start` kwarg / `SessionMetadata` field
  (`{state, z_cm, centre_x_cm, centre_y_cm}`, null for Mouse / practice / older sessions).
- `docs/DATA_SCHEMA.md` - the `head_position_at_start` row.
- `tests/test_start_page_phase2.py` - one existing test only: its window is 1500 px tall instead of
  900 (the head-position block makes the Start text taller than 900 px, so a scroll bar took 14 px of
  the width the test measures).

**pytest** (JUnit, final run): `5 failed, 4077 passed` (4082 tests). The 5 failures are the known
baseline alpha 0.35 vs 0.22: `test_config_flow.py::test_a_new_test_opens_at_standard_with_the_task_defaults`
and the four `test_task_config_page.py::test_a_new_test_opens_with_standard_and_the_defaults[...]`.
108 tests added. `ruff check` is clean on every new and changed file except two pre-existing lines
(`src/app.py` import order, `socket.timeout` in the fake server).

**Decisions inside the SPEC, worth knowing**
- A first full run crashed with a Windows access violation in the garbage collector, caused by this
  part: `SetupPage` gave its bound method `head_position_input` to the panel it owns, a reference
  cycle between two Qt widgets. The panel now holds a bound-method source through
  `weakref.WeakMethod` (a regression test checks a `SetupPage` is freed by its last reference).
- Eye data older than `STALE_AFTER_S` = 1 s counts as no eyes (a paused or stopped stream must not
  leave a frozen green face; the reader is paused during calibration). Not in the SPEC.
- With one eye valid the face centre is that eye moved half of `NOMINAL_EYE_SEPARATION_CM` (6.3)
  toward where the other would be, so the face does not jump when an eye drops out; tilt is 0.
- The colour hold applies to the pair (state, hint): a new colour or a new hint shows only after
  0.3 s; the face and the distance follow the data at once. "No eyes" waits 0.5 s counted from the
  first frame without eyes; the first reading, the return from no eyes / not connected, and
  not connected itself show at once.
- The state saved in `head_position_at_start` is the one the operator sees (held), read as Start is
  pressed.
- The status line reuses `StatusBadge` (a pill) rather than a bare glyph + text line.
- The distance hint follows physics (too near the tracker = "Move back"), confirmed by the hub; the
  wireframe example was wrong (section 9).

**Deviations from the SPEC:** none of the decisions G1-G8. The four open questions of section 9
(one-eye hint text, the wireframe's "Move closer, 52 cm", what left/right is relative to, and the
shape of the offset in `head_position_at_start`) were answered by the hub the same day and applied:
the one-eye text is "Only one eye seen" (`HINT_ONE_EYE`), 4.5 / 4.6 / 4.7 are updated, the rest was
accepted as implemented.

**Left undone (hub / live check):** the constants above are starting values; X / Y signs, the
centred Y, the bands and the one-eye centre are for the live check (probe P5, A9). The fake
tracker's `HEAD_CENTRE_M` must be set to the measured centre (equal to `CENTRED_X_CM` / `CENTRED_Y_CM`).
Nothing was launched against the device or the GUI.

## 9. Open questions

Hub questions, all answered by the user 2026-10-13 (recorded as G5-G8 in section 2):

- **Q1** - Default until the live check: **keep `best` + `ema`** (G5).
- **Q2** - Grid 3's "Eyes" view: **left out** (G6).
- **Q3** - Restore `AAC_FILTER` on disconnect and close: **yes** (G7).
- **Q4** - Operator hint text: **yes** (G8).

Implementer questions (part A, none blocking; each was implemented the minimal way and needs a hub word).
**Answered by the hub / user 2026-10-13, all applied:** Q5 - change the starting defaults to 0.3 Hz / 5.0
(applied in code, tests and 4.3); Q6 - keep the "Gaze smoothing" label, add "Gaze signal" (4.4 updated);
Q7 - accepted, blank columns on a Mouse run (4.4 updated); Q8 - accepted, per screen width / height per
second (4.3 reworded); the AAC_FILTER restore note - accepted as documented. The text below is the
question as asked, with the numbers it was asked about.

- **2026-10-13 - Q5, A3 against the starting defaults.** The starting defaults (`min_cutoff_hz` 1.0,
  `beta` 1.0) do not meet acceptance A3 read literally. Simulated at 150 Hz with 0.5 % uniform or
  Gaussian jitter: the at-rest spread is 0.31-0.32 of the EMA-0.35 spread (A3 needs at most 0.25), and a
  0.5-wide step jump reaches 95 % in 0.17 s (A3 needs at most 0.15 s; a 0.3 jump takes 0.25 s). The unit
  test therefore uses `min_cutoff_hz` 0.3 and `beta` 5.0 (both inside the settings' ranges), which give
  a ratio of 0.19-0.23 and 95 % in 0.07 s for a 0.3 jump. The defaults were left as 4.3 says ("starting
  values to tune at the live check"). The hub decides whether to change the starting defaults (for
  example to 0.3 / 5.0) or to keep them and treat A3 as a statement about the filter's capability.
- **2026-10-13 - Q6, report row labels (4.4).** 4.4 asks for the rows "Gaze signal" and "Smoothing".
  The Test Configuration table already has a "Gaze smoothing" row (asserted by four tests and drawn in
  `docs/wireframes/report-summary.md`). I added a new row "Gaze signal" just before it and extended
  the existing row's text for the adaptive filter ("On, adaptive (One Euro), steadiness 1 Hz,
  responsiveness 1, jitter tolerance 40 px"), keeping the label "Gaze smoothing" and its default text
  byte-identical. The table is now 18 rows (Follow the Target 17, Choice-making 21). If "Smoothing" was
  meant as a rename, it is one string in `report_config.py` plus the four tests.
- **2026-10-13 - Q7, the pointer columns on a Mouse run.** 4.4 does not say what `pointer_x/y/valid`
  hold when the test's Pointer is Mouse and a tracker records alongside (the mouse path is already in
  `pointer_stream.csv`). They are left blank there, and the report keeps drawing the mouse path from
  `pointer_stream.csv`.
- **2026-10-13 - Q8, units of `beta`.** 4.3 gives `beta` in "canvas-normalised units per second". The
  filter runs on the pointer `EyeInput.poll` returns, which is monitor-normalized like the raw gaze
  (the task converts it to canvas coordinates afterwards), so `beta` is per screen width / height per
  second. The two agree when the canvas fills the tracked screen, as in fullscreen. The recorded
  `pointer_x/y` are canvas-normalized as 4.4 says.
- **2026-10-13 - Note, known limits of the `AAC_FILTER` restore (G7).** (a) The original value is read
  by each `GazepointClient` on its first connect. A second Connect (a new client) made while the first
  client still holds a value it changed reads that changed value as its "original": the Setup page then
  stops the first client, which restores the true one, but the new client later "restores" the changed one.
  This needs an Assistive run followed by a second Connect without a close in between; not guarded. (b) The restore runs on `stop()` (Disconnect, a replaced client, the standalone
  app's end) and on closing the dashboard window, as 4.2 asks; it does not run when a run ends, so
  between two runs the device keeps the last Assistive length. (c) A replayed fixture keeps the `best`
  signal and sends nothing.

Implementer questions (part B):

- **2026-10-13 (Part B, claude-sonnet-5-5) - hint for orange with one eye only.** ANSWERED
  (hub / user, 2026-10-13): the text is **"Only one eye seen"** (the user's choice); applied in
  `HINT_ONE_EYE` and 4.6. 4.6 says orange is
  "only one eye valid, or Z in 50-55 / 75-80 cm, or the centre in the outer 30 % band" and lists the
  six "Move ..." hints, but gives no text for orange caused by one eye alone (no position fault). I
  used **"One eye only"** (`HINT_ONE_EYE` in `src/inputs/head_position.py`) so the feature is
  complete; the wording is a placeholder for the hub or the user to confirm. When a position fault
  exists too, the fault's hint shows and the state is orange or red as usual.
- **2026-10-13 (Part B) - wireframe example "Move closer, 52 cm" contradicts the band.** ANSWERED
  (hub, 2026-10-13): the wireframe example was the hub's mistake; the physical meaning stays (under
  the band "Move back", over it "Move closer"). The hub fixes `setup.md` in the main checkout;
  `docs/wireframes` was not touched here. `setup.md`
  shows "Move closer, 52 cm" as an orange example, but 52 cm is under the 55 cm green limit (too near
  the tracker), so the operator must say "Move back". I implemented the physical meaning: Z under the
  green band gives **"Move back"**, Z over it gives **"Move closer"** (`HINT_TOO_CLOSE` /
  `HINT_TOO_FAR`, one-line swaps if the hub meant it the other way). The wireframe example text
  needs fixing.
- **2026-10-13 (Part B) - what "left/right/up/down" are relative to.** ANSWERED (hub, 2026-10-13):
  accepted, the hints follow the picture and the signs are settled at probe P5; one line added to 4.5. The hint names the way to
  move **on the picture** (the face drawn right of centre gives "Move left"). With the proposed
  mirror view that is also the child's own left, like a selfie camera. Whether the operator should
  say it that way, or the X/Y signs need to flip, is settled at the live check (probe P5) through
  `DISPLAY_X_SIGN` / `DISPLAY_Y_SIGN`; the hints follow the picture whichever way they are set.
- **2026-10-13 (Part B) - shape of `head_position_at_start`.** ANSWERED (hub, 2026-10-13): accepted;
  4.7 now names the four fields. 4.7 says "the state, Z in cm, and the
  centre offset in cm". I wrote `{"state", "z_cm", "centre_x_cm", "centre_y_cm"}` (the offset as two
  numbers on the device's X / Y axes, one decimal, null when no eyes were measured), documented in
  `DATA_SCHEMA.md`. Say if a single distance-from-centre number was meant instead.

## 10. Log

- **2026-10-13** - Draft written by the hub from the user's questions about cursor shakiness and
  the Gazepoint Control distance indicator. Decisions G1-G4 from the user (AskUserQuestion).
  Feasibility of the Grid 3 face widget checked against the calibration video frames and the
  Gazepoint API corpus: everything it shows can be built from data the app already subscribes
  to, except Gazepoint's sign conventions and the centred head Y, which need the device (probe
  P5).
- **2026-10-13** - User answered section 9 Q1-Q4 (all as proposed): defaults stay `best` + `ema`,
  no Eyes view, `AAC_FILTER` restored on disconnect/close, hint text shown. Recorded as G5-G8.
  Next: the wireframe (plan step 1).
- **2026-10-13** - Wireframe rendered (setup, start-test, task-config, choice-making) and approved by the user ("OK"); the SPEC is approved. Plan step 1 DONE. Next: part A by the spec-implementer.
- **2026-10-13** - Hub review and integration. Parts A (`gaze-stability-a`) and B (`gaze-stability-b`) were applied as patches on `c3f6c24` in the integration worktree `gaze-stability-int`. Conflicts (both sides additive) were resolved by keeping both: the imports in `gazepoint_client.py`, the fake tracker REC line (head drift + APOG), and the section 8 / 9 logs. Wireframes updated to the decisions (`task-config.md` Steadiness 0.3 / Responsiveness 5.0; `report-summary.md` "Gaze signal" row). Full pytest on the combined code (JUnit): 4169 tests, 4164 passed, 5 failed, 0 errors; the 5 are the known fresh-worktree baseline (skip-worktree `default.yaml`, alpha 0.35 vs 0.22). Acceptance A1-A3, A6-A8, A10, A11 pass by test; A4, A5, A9 pass by test and are also checked live. Accepted additions: the 1 s stale rule, the StatusBadge status line. Known limits: `gazepoint_client.py` is 856 lines (it, `app.py` and `setup_page.py` were over 500 before); the AAC restore edge case after a second Connect (section 9). Plan steps 2-4 DONE; committed on the user's OK; the live check (step 5) is pending.
- **2026-10-13** - Live check (plan step 5), user as subject on the GP3 HD, first finding: **Fixation (FPOG) is rejected** ("definitely no, it feels jumpy"). This is expected from 4.1: FPOG holds still during a fixation, is invalid during every saccade (the cursor freezes), then jumps to the next fixation. Fixation + Adaptive is ruled out with it. Remaining comparison: Raw + Simple 0.05 (baseline), Raw + Adaptive 0.3 / 5.0, Assistive AAC 15 / 30 with smoothing off.
- **2026-10-13** - Live check, second finding: **Assistive + app smoothing is rejected** ("lags a lot"). User decisions G9-G11 (section 2) and new section 4.9: Fixation removed (old values load as Raw), Assistive turns the app's smoothing off and greys it, and the card is reworded as two approaches, "App smoothing (raw gaze)" and "Gazepoint Assistive (APOG)". Acceptance A12-A14 added. Wireframe update approved by the user ("OK"); next: an implementer.
