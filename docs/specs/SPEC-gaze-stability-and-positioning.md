---
name: SPEC-gaze-stability-and-positioning
title: Steadier gaze cursor (FPOG / APOG signal, One Euro filter) and a live head-position widget (Grid 3-style face + Close-Far bar)
status: APPROVED 2026-10-13 - SPEC + wireframe approved by the user (G1-G8); plan step 1 DONE
created: 2026-10-13
last_updated: 2026-10-13
next_step: plan step 2 (implement part A: 4.1-4.4, 4.8) by spec-implementer
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

**Status: APPROVED 2026-10-13 (SPEC + wireframe). Branch `feature/compass-task-flow` at `cbaa4c5`.**

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
    1.0 Hz, range 0.05-5.
  - `dwell.smoothing.beta` (label "Responsiveness"; higher = less lag on jumps). Starting default
    1.0, range 0-10, in canvas-normalised units per second.
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
  report's config table shows "Gaze signal" and "Smoothing" rows.
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
- whether `LEYEZ` tracks real distance well enough. Check it with a tape measure at 50, 65 and
  80 cm.

The fake tracker gains a slow head drift (X/Y/Z, plus a 3-second "no eyes" gap every 20 s), so
the widget can be tested without the device.

### 4.6 Colour rules (proposal; tuned at the live check)

| State | Rule | Face | Hint text |
|---|---|---|---|
| Green | Both eyes valid, Z in 55-75 cm, face centre inside the inner 70 % of the box | Smile | "Good position" |
| Orange | Only one eye valid, or Z in 50-55 / 75-80 cm, or the centre in the outer 30 % band | Flat mouth | "Move closer" / "Move back" / "Move left" / "Move right" / "Move up" / "Move down" (the largest fault first) |
| Red | Z under 50 or over 80 cm, or the centre outside the box | Frown | Same hints |
| No eyes | Neither eye valid for more than 0.5 s | Empty grey box | "No eyes detected" |

- The hint text is an addition (G8); Grid 3 shows none. It helps the operator.
- The state is smoothed over about 0.3 s so the colour does not flicker at a boundary.
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
- **Recorded:** each run's `metadata.json` gets `head_position_at_start`: the state, Z in cm,
  and the centre offset in cm at the moment Start is pressed. The full stream is already in
  `eye_geometry.csv`.

### 4.8 Settings registry and profiles

- The new keys join the existing "Gaze Smoothing" group (`settings_registry.py:469`), in this
  order: Gaze signal, AAC filter length, Smoothing on/off, Smoothing type, Alpha, Steadiness,
  Responsiveness.
- They are saved in settings profiles like every other key.
- An old profile without them loads as `best` + `ema`, so it behaves exactly as today.

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

## 7. Plan

1. **DONE 2026-10-13 - Wireframe** (`setup.md` Calibration card, `start-test.md` clinician area, the Gaze Smoothing
   card in `task-config.md` and `choice-making.md`). This is user GATE 1.
2. **Implement part A:** signals + `AAC_FILTER` + One Euro + recording + report + settings
   (4.1-4.4, 4.8).
3. **Implement part B:** head-position widget + fake tracker drift + metadata (4.5-4.7).
4. Hub review, then the full pytest.
5. **Live check on the GP3 HD, with the user as subject:**
   - probe P5: X/Y signs, the centred Y value, Z against a tape measure;
   - tune the 4.6 bands;
   - compare side by side on a Grid Click / Choice-making target: BPOG + EMA 0.05, FPOG,
     APOG 15, BPOG + One Euro, FPOG + One Euro;
   - write the chosen defaults back into this SPEC.
6. Commit (on the user's OK); the defaults are changed only on the user's word.

## 8. Impl log

(empty)

## 9. Open questions

Hub questions, all answered by the user 2026-10-13 (recorded as G5-G8 in section 2):

- **Q1** - Default until the live check: **keep `best` + `ema`** (G5).
- **Q2** - Grid 3's "Eyes" view: **left out** (G6).
- **Q3** - Restore `AAC_FILTER` on disconnect and close: **yes** (G7).
- **Q4** - Operator hint text: **yes** (G8).

Implementer questions: (none yet)

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
