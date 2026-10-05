---
name: SPEC-display-scaling-cursor-accuracy
title: Gaze cursor accuracy degrades on 15"/13" 1920×1080 laptops
status: implemented (§8), unit-tested and live-validated at simulated 150/125 % and real 100 %; real-laptop test pending
created: 2026-09-30
last_updated: 2026-10-05
next_step: user tests on a real 125/150 % laptop (needs a source checkout or a rebuilt exe). The 150 % Tasks-page clipping is NOT fixed (responsive layout deferred to a later version); the operator-facing display warning is SPEC-display-standard-check.md
related:
  - SPEC-gui-audit-2026-09-10.md (item 5 introduced the regression)
  - SPEC-gazepoint-analysis-export-parity.md (§10 holds the device_pixel_ratio metadata backlog)
---

# SPEC-display-scaling-cursor-accuracy — Gaze cursor accuracy degrades on 15"/13" 1920×1080 laptops

**Status (2026-10-02): FIXED. §8 implemented, unit-tested, and
live-validated with the real GP3HD at simulated 150 % and 125 % and at real
100 % (see §8.6). Only the real-laptop test remains.**

**Original status: ROOT CAUSE CONFIRMED by user A/B test (evaluation only, no code
changed), 2026-09-30.** The user's hypothesis is **partly right**: the cursor
calculation *does* behave differently per screen. The cause is not the
physical screen size. It is the **Windows display scale** (100 % / 125 % /
150 %) that 24", 15" and 13" 1080p panels typically default to.
`_sync_gaze_geometry()` mixes Gazepoint's **physical** pixels with Qt's
**logical** pixels, which is exact at 100 % and wrong by a factor of the
scale otherwise. The 15" and 13.3" laptops set to 100 % became accurate
(§5 step 4, see the second log entry). §6.1 compares how other gaze software
handles scaling.

**Created:** 2026-09-30
**Last updated:** 2026-10-02

## 1. Origin / what was asked

User, 2026-09-30, after testing the v1.0.0 build (`SPEC-compiled-release.md`)
on three displays, all 1920×1080:

| Test | Display | Observed cursor accuracy |
|---|---|---|
| 1 | LG 24" desktop monitor (this PC) | accurate |
| 2 | 15" laptop | worse |
| 3 | 13" laptop | worse again |

Baseline held constant: subject-to-camera placement, and eye positioning
confirmed in Gazepoint Control (both eyes boxed green, depth dot centred,
140 Hz, USB3, IPD 63 mm; screenshot
`resources/images/gazepoint-control-testing.png`). Hypothesis to validate:
"even though all the resolution is 1920×1080 … the calculation of the cursor
is different for each screen size." Added later: "I didn't check the scale,
therefore it most likely differs for each screen." Scope is **evaluate the
cause, not implement**.

## 2. Verdict

| Candidate cause | Verdict | Size of effect |
|---|---|---|
| **A. Windows display scaling × mixed pixel units in `_sync_gaze_geometry()`** | **Primary cause. Confirmed by the user's 100 % A/B test (§5 step 4)** | 0 mm at 100 %; **43 mm** (125 %) / **72 mm** (150 %) at screen centre for *perfect* gaze. Cursor lands off-canvas toward the right and bottom |
| B. Same angular device error → more pixels on a denser panel | Real but minor, and unavoidable | ≤ 11 mm on the glass on every screen (0.5–1° at 65 cm). Smaller than the target hitbox everywhere |
| C. Physical screen size entering the cursor formula | **No.** Nothing in the pointer path reads mm, DPI or diagonal | 0 |
| D. Gazepoint's own tracking degrading | Not supported. `FPOGX/Y` are fractions of the tracked screen and do not depend on the scale | 0 (see §5 for how to confirm) |

## 3. The code path (as of `d2feca4` / tag `v1.0.0`)

Each frame, `src/app.py::_tick` calls `_sync_gaze_geometry()`
(`src/app.py:551-568`):

```python
info = self.client.device_info                      # SCREEN_SIZE from Gazepoint Control
canvas_origin = self.canvas.mapToGlobal(QPoint(0, 0))   # Qt LOGICAL px
offset_x = canvas_origin.x() - (info.screen_x or 0)
offset_y = canvas_origin.y() - (info.screen_y or 0)
self.task.set_gaze_geometry(info.screen_width, info.screen_height, offset_x, offset_y)
```

`BaseTask.pointer_to_canvas_px()` (`src/tasks/base_task.py:172-187`) then
computes

```
px = FPOGX × screen_width − offset_x
```

and compares that against target centres in canvas pixels
(`norm_to_px(tx, ty, self.screen_w, self.screen_h)`, `base_task.py:259`).
The canvas size comes from `set_screen_size(canvas.width(), canvas.height())`.
The drawn cursor uses the same conversion (`pointer_to_canvas_norm`), so the
cursor you see and the point hit-testing checks are wrong in the same way.
That is consistent with what the user saw.

Where each term comes from:

| Term | Source | Unit on a scaled display |
|---|---|---|
| `screen_width/height` | Gazepoint `SCREEN_SIZE` (API manual §3.14, "in pixels") | **physical** (1920×1080), *assumed, §5* |
| `offset_x/y` | `QWidget.mapToGlobal` | **logical** (device-independent px) |
| canvas `width()/height()`, targets, `radius_px`, `jitter_tolerance_px` | Qt widget geometry, config | **logical** |

The repo has no code that handles `devicePixelRatio`, `QT_SCALE_FACTOR` or
high-DPI settings (grep of `*.py`: zero matches). PySide6 6.x always enables
high-DPI scaling, so on a 150 % display every Qt coordinate is physical ÷ 1.5.

**Consequence:** at scale `s`, gaze truly at logical x `X` produces a cursor
at `X·s`. The error is `X·(s−1)`. It is zero at the screen's top-left corner
and grows linearly toward the bottom-right. That is why the 24" (almost
always 100 %) is exact and the 13" (typically 150 %) is worse than the 15"
(typically 125 %).

## 4. Evidence

### 4.1 Qt really does switch to logical pixels (measured on this PC)

`scratchpad/dpi_probe.py`, PySide6 6.11.2, the LG 24" (527×296 mm):

| `QT_SCALE_FACTOR` | `QScreen.geometry()` | `devicePixelRatio` |
|---|---|---|
| unset (Windows 100 %) | 1920×1080 | 1.0 |
| 1.25 | **1536×864** | 1.25 |
| 1.5 | **1280×720** | 1.5 |

`QT_SCALE_FACTOR` stands in for the Windows scale setting; Qt applies both
through the same `devicePixelRatio` mechanism.

### 4.2 The 24" sessions confirm scale 1.0 on the working screen

All six `compiled/PedsEyeGaze-1.0.0/sessions/2026-09-30_TEST_click_grid_run{1..6}/metadata.json`:
`screen 1920×1080`, `canvas 1640×957 at +0,+75`, `physical 527×296 mm`.
Canvas + operator column (280) = 1920. Logical and physical coincide, so
the mixed units cancel. That explains why test 1 was accurate. No laptop
sessions exist on this PC.

### 4.3 Simulation using the app's own conversion code

`scratchpad/dpi_cursor_sim.py` imports the real `BaseTask`, calls
`set_gaze_geometry()` exactly as `_sync_gaze_geometry()` does, and feeds it
a **perfect** gaze sample aimed at the target centre. Layout: the operator
column and header measured in §4.2, kept at the same logical size. Hitbox =
default `radius_px` 90 + `jitter_tolerance_px` 40 = 130 canvas px.

| Display (assumed scale) | Canvas (logical) | Top-left target | Centre | Right (0.85, 0.5) | Bottom-right |
|---|---|---|---|---|---|
| 24" @ 100 % | 1640×957 | 0 mm, hit | 0 mm, hit | 0 mm, hit | 0 mm, hit |
| 15.6" @ 125 % | 1256×741 | 15 mm, hit | **43 mm, miss** | **65 mm, off-canvas** | **72 mm, off-canvas** |
| 13.3" @ 150 % | 1000×597 | 26 mm, hit | **72 mm, miss** | **107 mm, off-canvas** | **119 mm, off-canvas** |

(mm are on the glass: logical error × scale × panel mm-per-physical-px.)
With the §6 on-canvas clamp from `SPEC-gui-audit-2026-09-10.md`, "off-canvas"
means the drawn cursor pins to the right or bottom edge.

**Predicted symptom signature** (use this to check against what the user
saw): the cursor is roughly right near the **top-left** of the screen. It
sits **below and to the right** of true gaze, more so the further you look
toward the bottom-right. It sticks to the right/bottom edge when you look
past about two-thirds of the way across. Targets on the right and bottom are
effectively unreachable.

### 4.4 Candidate B, quantified: why it is not the explanation

GP3 HD accuracy is **0.5–1° of visual angle**
(`docs/gazepoints/synthesis/gp3-hd-specifications.md`), at the vendor's 65 cm
operating distance. That is 5.7–11.3 mm on the glass on *any* screen. In
pixels it varies with pixel density:

| Display | mm / physical px | 0.5–1° error, physical px |
|---|---|---|
| 24" | 0.274 | 21–41 |
| 15.6" | 0.179 | 32–63 |
| 13.3" | 0.153 | 37–74 |

This is a real, inherent effect (about 1.8× more pixels on the 13"). But it
is capped at about 11 mm, stays well inside the 130-px hitbox on every
screen, and has no directional bias. Candidate A is 4–10× larger and always
points toward the bottom-right. Scaling also partly *offsets* B: at 150 %,
a 130-logical-px hitbox is 195 physical px ≈ 30 mm, close to the 24"'s
36 mm.

## 5. Assumption and how to settle it (no code needed) — settled 2026-09-30 by step 4

The whole of §3/§4.3 depends on **Gazepoint Control reporting `SCREEN_SIZE`
as 1920×1080 physical pixels on a 125/150 % display.** If Control were
DPI-unaware, Windows would hand it virtualized logical values (e.g.
1280×720). Then units would match and A would vanish. The vendor manual does
not say which. The observed laptop degradation strongly suggests physical,
but that is inference, not measurement.

Settle it on each laptop, in order of effort:

1. **Settings → System → Display → Scale** on the 15" and 13". Expect
   125 % / 150 %; 100 % on either would rule A out for that machine.
2. **Read the laptop sessions' `metadata.json`** (in the exe's
   `sessions/<run>/`). Confirmed if `screen_width_px` = 1920 while
   `canvas_width_px + canvas_offset_x_px + ~280 px column` ≈ 1920 ÷ scale
   (≈1536 or ≈1280). A reported `screen_width_px` of 1536/1280 refutes it.
3. **Control experiment:** on a laptop, enable Gazepoint Control's own
   *Gaze Pointer* after calibrating. If Control's pointer is accurate while
   ours drifts to the bottom-right, the device is fine and the fault is
   ours (A). If Control's pointer is *also* off, suspect D/calibration
   instead.
4. **Decisive A/B:** set a laptop to 100 % scale, re-run the same task.
   Accuracy should match the 24".

Also worth recording for each test: whether calibration was re-run on that
screen (Control calibrates the screen it is displayed on). Reusing a
calibration across displays is a separate confounder.

## 6. Fix direction (superseded by the decisions in §8)

- Put both sides in one unit system. The simplest option is to convert
  `SCREEN_SIZE` and `screen_x/y` to logical px with the tracked screen's
  `QScreen.devicePixelRatio()` before calling `set_gaze_geometry`.
  Alternatively, take the tracked screen's geometry from `QScreen` itself
  and use `SCREEN_SIZE` only to identify *which* screen. Choose after §5
  settles what Control reports. If Control reports logical, no fix is
  needed and the cause is elsewhere.
- Multi-monitor setups with *different* scales per monitor make the offset
  term harder. Test that case separately.
- `metadata.json` currently stores `screen_*_px` (physical) next to
  `canvas_*` (logical) with no scale field. Record `device_pixel_ratio` so
  sessions from scaled displays can be reinterpreted later. Saccade
  pixels/degrees (`SPEC-gazepoint-analysis-export-parity.md`) use the
  physical `screen_*` with normalized POG and are **not** affected.
- Regression test: a pure unit test of `pointer_to_canvas_px` with a
  simulated DPR of 1.25/1.5 (the §4.3 script is most of it).

### 6.1 How other gaze software handles scaling (added 2026-09-30)

The gaze a tracker sends is **already resolution- and size-independent**.
Gazepoint `FPOGX/Y`, Tobii's "Active Display Coordinate System"
(developer.tobiipro.com, *Coordinate systems*): `(0,0)` is the display's
top-left and `(1,1)` its bottom-right. Neither pixel resolution nor physical
size enters that number. Every app must then turn the fraction into a
position in *its own* window, and that one step is where scaling bites. The
usual approaches:

| Approach | Who | Scale-robust? |
|---|---|---|
| **Require 100 % scaling** | PsychoPy: "people will need to ensure desktop scaling is at 100 %" (GitHub psychopy#4119). A Tobii gaze-to-mouse project lists the same as a known issue: "Window's scale setting must be set at 1:1 or 100 %, otherwise gaze coordinates will be offset" (BenLeech/tobii-eye-mouse-control README) | No. Pushed onto the operator |
| **Fraction × the app's own window size, window full-screen** | `resources/diki` (colleague's app): `norm_to_px(pointer.x, pointer.y, self.screen_w, self.screen_h)` with `screen_w/h` = its canvas's own Qt size (`diki/tasks/base_task.py:149`, `diki/app.py:238`), canvas shown `showFullScreen()` (`diki/ui/main_window.py:34`). Both factors are logical, so the scale cancels | **Yes**, but only while the canvas covers the whole tracked screen |
| **The platform owns the mapping (system-wide display setup, gaze delivered as OS screen coordinates or as the Windows mouse cursor)** | The Tobii Dynavox stack (PCEye, I-Series): a one-time *Display setup* in Tobii Dynavox Eye Tracking settings picks the monitor the tracker is mounted on and aligns it to the screen (help.tobii.com, *Display setup*). Apps on top (Look to Learn, EyeFX, Gaze Viewer, TD Snap, Communicator) consume gaze from the Tobii engine or via Windows Control's gaze-driven mouse. The older EyeX SDK documents its gaze point "as pixel coordinates on the screen" (Tobii EyeX Developer's Guide C/C++). Windows itself delivers cursor/screen coordinates in each app's own DPI context | **Yes.** The individual app never does the fraction-to-pixels step, so it cannot get it wrong. Gazepoint's analogue is Control's own *Gaze Pointer* (drives the Windows cursor) |
| **All physical pixels, end to end** | **OptiKey** (open-source Windows eye-gaze keyboard/mouse, Gazepoint supported): gaze fraction × primary-screen size converted to physical px (`Static/Graphics.cs`: `SystemParameters.PrimaryScreenWidth × DpiX/96`), keys hit-tested with WPF `PointToScreen` (physical px). An OptiKey plugin ADR (yuanweize/OptiKey-ET5-Plugin, ADR-007, 2026) names this SPEC's exact symptom: "At 125% or 150% DPI, points drift or key hit detection misses". Primary monitor only | **Yes** |
| **Fraction × the tracked screen's geometry in one consistent unit** | What a DPI-aware app does. Either everything logical (the OS/toolkit's screen geometry) or everything physical (declare per-monitor DPI awareness, `SetProcessDpiAwareness(2)`, and use physical coordinates throughout) | **Yes**, and it also handles a canvas that is not full-screen |

**Where we sit:** this app used diki's approach until
`SPEC-gui-audit-2026-09-10.md` item 5. That item switched the pointer
conversion to Gazepoint's `SCREEN_SIZE`, which is needed because our canvas
is *not* full-screen (operator column, header). The switch introduced a
physical-pixel number into an otherwise logical calculation. It fixed the
side-column undershoot and made the conversion scale-sensitive at the same
time. The 24" at 100 % could not show the regression. The robust approach
is row 3: keep item 5's full-screen geometry, but take it from the
`QScreen` Qt already has for the tracked monitor (logical units, scale
applied automatically) or divide `SCREEN_SIZE` by that screen's
`devicePixelRatio()`.

**"Does the app know the current display config?"** Partly. At connect it
knows the resolution (`SCREEN_SIZE`); every frame it knows its window
position (`mapToGlobal`); and it already reads the panel's physical mm
(`QScreen.physicalSize()`, for `metadata.json`). It **never reads the scale
factor**, although Qt exposes it (`QScreen.devicePixelRatio()`, 1.0 / 1.25
/ 1.5 in §4.1). Physical screen size is not needed for the cursor at all,
since the fraction already accounts for it. It only matters for reporting
degrees of visual angle.

## 7. Open questions (re-triaged 2026-10-01; all closed 2026-10-02)

Evaluation questions. **The user closed all four as moot on 2026-10-02**:
none changes the fix, and the 100 % A/B test already proved the cause.

- ~~Actual Windows scale of the 15" and 13" laptops (§5 step 1).~~
  **Superseded** by the user's 100 % A/B test (§5 step 4, §9 second
  entry), which settled §5's assumption in practice. The original scale
  values were never read and are no longer needed.
- Exact diagonals: 15" vs 15.6", 13" vs 13.3". **Unanswered, cosmetic**:
  only changes §4's mm columns.
- Was calibration re-run on each laptop screen? **Unanswered.** Moot for the
  verdict (100 % scale alone fixed it), but record it in future tests.
- Which cursor was judged: ours on the task canvas, or Control's Gaze
  Pointer? **Assumed ours**, consistent with the 100 % fix (Control's pointer
  would not be affected by our code).

Implementation questions are **decided in §8** (D1–D4). Anything new the
implementer hits goes in §8.7, not here.

## 8. Implementation brief (D1–D4 chosen by the user 2026-10-02)

### 8.1 Goal

Make the drawn cursor and hit-testing correct at any Windows display scale
(100 / 125 / 150 %), keeping gui-audit item 5's full-screen-geometry
behaviour (canvas not full-screen: operator column + header).

### 8.2 Decisions (the user chose these 2026-10-02; do not re-open)

- **D1 — Source of the tracked-screen geometry: Qt, not `SCREEN_SIZE`.**
  Use the `QScreen` that hosts the canvas (`self.canvas.screen()`): its
  `geometry()` gives width, height and origin in Qt's **logical** global
  coordinates, the same space `mapToGlobal` returns. So:
  `gaze_w, gaze_h = geo.width(), geo.height()`;
  `offset = canvas.mapToGlobal(0,0) − geo.topLeft()`.
  Rejected: dividing `SCREEN_SIZE`/`screen_x/y` by `devicePixelRatio()`.
  It is equivalent on one monitor, but Gazepoint's `screen_x/y` are
  physical virtual-desktop coordinates, and Qt's logical global layout
  with mixed per-monitor scales is not a single division of those.
  The user chose D1 after the §6.1 comparison, including the OptiKey
  row: every scale-robust app keeps **one** pixel unit end to end.
  OptiKey uses all-physical; D1 is the all-logical mirror of that.
- **D2 — `SCREEN_SIZE` is only a sanity check.** If
  `round(geo.width() × dpr) ≠ screen_width` or the same for height
  (tolerance ±2 px), log **once per connect** via `self.recorder.log(...)`:
  the canvas is probably not on the monitor Gazepoint Control tracks.
  Still use the QScreen geometry. The existing no-op when `SCREEN_SIZE` is
  missing (replay, unanswered query) stays unchanged.
- **D3 — Mixed-scale multi-monitor is covered by D1** (all-logical, one
  screen). No extra work. Not live-tested; note it as untested in the
  Impl log.
- **D4 — Factor the arithmetic into a pure function** so it is unit-testable
  without a real `QScreen`, e.g. in `src/tasks/base_task.py` or a small
  helper module:
  `gaze_geometry_from_screen(screen_x, screen_y, screen_w, screen_h,
  canvas_global_x, canvas_global_y) -> (w, h, offset_x, offset_y)`.
  `_sync_gaze_geometry()` becomes a thin Qt wrapper around it.

### 8.3 Scope

In: `src/app.py::_sync_gaze_geometry()`, the new helper, new tests under
`tests/`.
Out (do NOT change):
- `_record_geometry()` / `metadata.json`. Its `screen_*_px` stays physical
  (correct for saccade px/degrees). Adding `device_pixel_ratio` is
  `SPEC-gazepoint-analysis-export-parity.md` §10. Note in the Impl log
  that its `canvas_offset_*` mixes units the same way, for that SPEC.
- `BaseTask.pointer_to_canvas_px` / `set_gaze_geometry` signatures,
  `calibration.py`, the replay path.

### 8.4 Acceptance criteria

1. Unit test: physical 1920×1080 at DPR 1.0 / 1.25 / 1.5 (logical
   1920×1080 / 1536×864 / 1280×720), the §4.2 layout scaled (canvas at
   logical +0,+75, operator column 280 logical px). A perfect gaze sample
   aimed at a target centre at (0.15,0.15), (0.5,0.5), (0.85,0.5),
   (0.85,0.85) of the canvas lands within 1 logical px of it, i.e. a hit
   at every DPR (the §4.3 table becomes all zeros).
2. Unit test: a secondary monitor with a non-zero origin (e.g. logical
   x = 1920) gives the same result.
3. DPR 1.0 output is identical to today's (no regression on the 24").
4. D2's mismatch warning fires once for a mismatched size, not every frame.
5. Full pytest: 223 + new tests passed, plus only the known local-config
   failure `test_config_merges_task_over_default`.

### 8.5 Validation

- pytest (above).
- **Live on this PC (24" at 100 %), simulating a scaled laptop:** launch
  the dashboard with `$env:QT_SCALE_FACTOR = "1.5"` (then `"1.25"`). Qt
  goes logical (§4.1) while Gazepoint `SCREEN_SIZE` stays 1920×1080
  physical, which is exactly the laptop condition. Real GP3HD + real
  subject, maximize via qt-mcp first. Look at the four corners and the
  centre: the cursor should sit on gaze, not drift bottom-right. Then
  repeat without `QT_SCALE_FACTOR` (regression check).
- Real 125/150 % laptop: user, after merge.

### 8.6 Impl log

(Implementer appends dated entries here: changes, test results,
deviations.)

- **2026-10-02 -- implemented by
  `claude-sonnet-5-5`.**
  Files changed: `src/tasks/base_task.py` (new pure helpers
  `gaze_geometry_from_screen()` and `screen_size_mismatch()`),
  `src/app.py` (`_sync_gaze_geometry()` now a thin wrapper using
  `self.canvas.screen().geometry()` in logical px; D2 mismatch log via
  `self.recorder.log` once per device-info object, i.e. per connect/refresh,
  tracked in `self._geometry_checked_info`; existing no-op when
  `SCREEN_SIZE` is missing kept; also no-op if `canvas.screen()` is None),
  new `tests/test_display_scaling.py` (24 tests: criteria 1-4, DPR
  1.0/1.25/1.5 x 4 target positions, secondary monitor at x=1920, DPR 1.0
  equals old output, mismatch tolerance, once-not-every-frame log).
  pytest: 247 passed, 1 failed (223 baseline + 24 new) (only the known local-config
  `test_config_merges_task_over_default`: 150 != 60).
  Deviations: none. D3 (mixed-scale multi-monitor) is untested, as
  planned. Live QT_SCALE_FACTOR validation (S8.5) not done (hub's job).
  Note for `SPEC-gazepoint-analysis-export-parity.md` S10:
  `_record_geometry()`'s `canvas_offset_*` mixes units the same way
  (logical `mapToGlobal` minus physical `screen_x/y`); left unchanged per
  S8.3.

- **2026-10-02 -- hub review + live validation (Opus hub).** Diff and the
  entry above checked against §8.4: all five criteria met. Hub reran pytest:
  **247 passed, 1 failed** (the known `test_config_merges_task_over_default`).
  Live, real GP3HD, the user as subject, dashboard maximized via qt-mcp,
  calibrated fresh each run, corners + centre checked by the user:

  | Run | Logical window | Session | Cursor (user) | D2 log |
  |---|---|---|---|---|
  | `QT_SCALE_FACTOR=1.5` | 1280×673 | `2026-10-02_DPI150_click_grid_run1` | on gaze | none (correct) |
  | `QT_SCALE_FACTOR=1.25` | 1536×807 | `2026-10-02_DPI125_click_grid_run1` | on gaze | none (correct) |
  | unset (100 %) | 1920×1009 | `2026-10-02_DPI100_click_grid_run1`/`run2` | on gaze | none (correct) |

  At 100 % the canvas sits at +0,+75, the same layout as §4.2, so the 24"
  is unchanged. Not tested: a real 125/150 % laptop (user, next) and D3
  mixed-scale monitors.

  Found during the live check, **not caused by this fix**:
  (1) at 150 % the Tasks page does not fit 673 logical px: card titles are
  clipped and the four card buttons lose their text. It fits at 125 %. A
  real 150 % laptop shows the same, so it needs its own item.
  (2) the `Geometry:` session-log line still mixes units ("monitor
  1920x1080px" physical, "canvas 1000x621px" logical): the
  `_record_geometry()` note above, for the export-parity SPEC §10.
  (3) `DPI100_click_grid_run2` logged a 268.8 px calibration error marked
  "valid", against 25-27 px in the other runs. That is the subject's
  calibration, not this fix.

### 8.7 Implementer open questions

(Implementer appends here, then stops and asks.)

### 8.8 Follow-up: canvas fields in `metadata.json` in physical px (APPROVED 2026-10-05; IMPLEMENTED + live-validated 2026-10-05)

Raised as `/spec-backlog` item #5 on 2026-10-05. §8.3 put
`_record_geometry()` out of scope and noted that its `canvas_offset_*` mixes
units. That is still true at `src/app.py:711-727` (as of `5687ba8`):
`canvas.mapToGlobal(0,0)` (Qt **logical**) minus `info.screen_x/y`
(Gazepoint **physical**). `canvas_width/height_px` are logical, while
`screen_*_px` (Gazepoint) and `display_*_px` (`check_display`) are
physical. At 100 % every value is correct. At 125/150 % the canvas fields
are off by the scale factor, and the offset is a mix of both units. Only
the metadata and the session log are wrong. The cursor and hit-testing
were fixed in §8 and are not touched here.

**User decision (2026-10-05, `AskUserQuestion`): all physical.** Every
pixel field in `metadata.json` uses one unit, Gazepoint's physical px, so
an analysis can use `FPOGX × screen_width_px − canvas_offset_x_px` directly
against `all_gaze.csv` at any scale.

#### 8.8.1 Design

- **Pure helper** (unit-testable without a real `QScreen`), next to
  `gaze_geometry_from_screen` (§8.2 D4):
  `canvas_geometry_physical(screen_x, screen_y, canvas_global_x,
  canvas_global_y, canvas_w, canvas_h, dpr) -> (w, h, offset_x, offset_y)`,
  with all inputs in Qt logical px and the result in physical px:
  `offset = round((canvas_global − screen_origin) × dpr)`,
  `w/h = round(canvas_w/h × dpr)`. The origin is the canvas's `QScreen`
  `geometry().topLeft()` (logical, the same as D1), **not**
  `info.screen_x/y`.
- `_record_geometry()` uses it for `canvas_width_px`,
  `canvas_height_px`, `canvas_offset_x_px` and `canvas_offset_y_px`. With no
  `QScreen`, keep today's raw logical values (this cannot happen with a
  shown canvas). `screen_*_px` (from `SCREEN_SIZE`), physical mm and
  viewing distance stay as they are. In replay the monitor fields stay
  `None` as today; the canvas fields use the same helper.
- **`CANVAS_RESIZED` events** (`_check_canvas_resized`,
  `SPEC-hud-hide-toggle.md` §4.4) record `canvas_w`/`canvas_h` in the
  same physical px. The change-detection compares physical sizes too, so
  the first-tick baseline matches `metadata.json`.
- **Session log `Geometry:` line**: print the physical values. When the
  scale is not 100 %, append "(physical px; Windows scale N %)" so the
  line is unambiguous.
- **`metadata.json` gains `canvas_units: "physical"`** (string, default
  `None`). A reader can then tell new sessions from older ones, whose
  canvas fields were logical (identical at 100 %).
- `docs/DATA_SCHEMA.md`: state that all geometry px fields are physical,
  explain `canvas_units`, and note that sessions without it recorded
  logical canvas values (only differs at 125/150 %).

#### 8.8.2 Scope

In: `src/app.py` (`_record_geometry`, `_check_canvas_resized`), the helper
module that holds `gaze_geometry_from_screen`, `src/data/schema.py`,
`docs/DATA_SCHEMA.md`, tests.
Out: `_sync_gaze_geometry` / `BaseTask` (cursor and hit-testing: §8 is
correct, do not touch), `pointer_to_canvas_px`, calibration, the
Results page, the responsive layout (deferred), `configs/`.

#### 8.8.3 Acceptance criteria

1. Helper unit tests at dpr 1.0 / 1.25 / 1.5: e.g. canvas 1640×957
   logical at global (0,75) on a screen at logical origin (0,0), dpr 1.5,
   gives (2460, 1436, 0, 112). Also a screen with a non-zero origin
   (second monitor).
2. At dpr 1.0, `_record_geometry()` output is identical to today's (test
   with a fake canvas and screen).
3. At dpr 1.5, `metadata.json` canvas fields equal the physical values,
   `canvas_units == "physical"`, and the `Geometry:` log line names the
   scale.
4. `CANVAS_RESIZED` carries physical sizes; at dpr 1.0 the events are
   unchanged.
5. A v1.0.0 `metadata.json` without `canvas_units` still loads.
6. Full pytest suite passes.
7. Live check (hub + user): one dashboard run at real 100 %, where the
   values must equal today's, and one at `QT_SCALE_FACTOR=1.5`, where the
   canvas fields must be ≈1.5× the logical size, with the offset y ≈ 1.5 ×
   the title/HUD height.

#### 8.8.4 Impl log (implementer appends here)

- **2026-10-05 -- implemented by `claude-sonnet-5-5`.**
  Files changed: `src/tasks/base_task.py` (new pure
  `canvas_geometry_physical()` next to `gaze_geometry_from_screen`),
  `src/app.py` (module-level `_canvas_physical(canvas)` wrapper used by
  `_record_geometry` and `_check_canvas_resized`; `Geometry:` line prints
  physical values and appends "(physical px; Windows scale N %)" when the
  scale is not 100 %; sets `canvas_units = "physical"` when a QScreen exists,
  otherwise falls back to raw logical values with `canvas_units` left None),
  `src/data/schema.py` (`canvas_units: str | None = None`),
  `docs/DATA_SCHEMA.md`, new `tests/test_canvas_geometry_physical.py` (11
  tests: criteria 1-3, 5, second monitor, replay, metadata.json round trip),
  plus a `test_canvas_resized_carries_physical_px_at_150_percent` test in
  `tests/test_hud_hide_toggle.py`. Existing fakes in
  `tests/test_display_check.py` and `tests/test_hud_hide_toggle.py` gained
  `topLeft` / `screen()` / `mapToGlobal` / `devicePixelRatio` stubs because
  the code under test now reads them.
  pytest (`-o addopts="" -q`): **324 passed** in 1:46 (313 baseline + 11 new;
  the known local-config failure did not appear in this run).
  Deviations: none. Not done: live check (criterion 7, hub + user).
  Note: Python `round()` is banker's rounding; the SPEC example
  (2460, 1436, 0, 112) matches it. A stray 0-byte file `original` sits in the
  repo root, not created by this task.

#### 8.8.5 Open questions (implementer writes here and returns)

## 9. Log

- **2026-09-30 — evaluated, via `/sparc:orchestrator`; no code changed.**
  Traced the pointer path (`app.py:551-568` → `base_task.py:142-187`).
  Found no DPI handling anywhere in the repo. Measured Qt's logical
  geometry at 1.0/1.25/1.5 on this PC (§4.1). Confirmed today's 24"
  sessions ran at scale 1.0 (§4.2). Simulated the error with the app's own
  `BaseTask` code (§4.3). Quantified the device-inherent density effect as
  secondary (§4.4). The verdict hinges on one unconfirmed assumption
  (`SCREEN_SIZE` physical on a scaled display), with four no-code ways to
  settle it (§5). The user's added note ("I didn't check the scale") is
  consistent with the primary cause. Probe scripts live in the session
  scratchpad only; they are not committed. Uncommitted, ask-before-commit.

- **2026-09-30, later — root cause CONFIRMED by the user's A/B test; §6.1
  added.** The user re-ran on the 15" and 13.3" laptops (both 1920×1080)
  with Windows scale set to **100 %**: "the cursor becomes accurate." That
  is §5 step 4, the decisive test. It confirms candidate A and settles §5's
  open assumption in practice (`SCREEN_SIZE` behaves as physical px). The
  user asked how comparable software handles scaling, and whether our app
  detects the display config. Answered in §6.1: `resources/diki` is
  scale-robust because it converts gaze with its own full-screen canvas
  size (both factors logical). PsychoPy and at least one Tobii tool instead
  require 100 % scaling. Our regression dates from
  `SPEC-gui-audit-2026-09-10.md` item 5. Still evaluation only, no code
  changed. The fix direction in §6 stands; a workaround until then is 100 %
  scaling on the test PC. Uncommitted, ask-before-commit.

- **2026-09-30, later still — the "similar software" was a Tobii Dynavox
  program, not diki.** The user clarified that the collaborator's
  scale-robust software ran on a Tobii Dynavox eye tracker (name not
  recalled). The row added to §6.1 explains it: in that ecosystem the
  platform does the screen mapping system-wide and apps receive gaze in
  screen/cursor coordinates, so no app-level fraction-to-pixel step exists
  to go wrong. The diki row stays as a second, independent example; it was
  never the software the user saw. That program's exact mechanism is
  unverified until it is named. Likely candidates for a pediatric gaze
  assessment on Tobii Dynavox: Gaze Viewer, Look to Learn, EyeFX / Sensory
  EyeFX. The conclusion is unchanged: our bug is the unit mix in
  `_sync_gaze_geometry()` (§3), fixable per §6 without operator
  configuration.

- **2026-09-30, end of day — follow-up Q&A findings; metadata items moved
  to a backlog.**
  - **Data validity of v1.0.0 sessions recorded at 125/150 %:** raw device
    data (`all_gaze.csv`, `fixations.csv`, `gaze_stream.csv`, pupils,
    saccades) is correct, because it is normalized and never passes
    through `pointer_to_canvas_px`. Everything that went through the
    broken conversion is invalid: hit/miss, on-target, dwell in
    `trials.csv`, and the task scores in `session_metrics.json`.
  - **Screen size after the fix:** at 100 % scale the layout is identical
    in proportion on every panel, but not in visual angle. At 65 cm the
    130-px hitbox *radius* is 35.7 mm on the 24" and 19.9 mm on the 13.3";
    a 1° tracker error uses 32 % vs 57 % of it. Task-performance metrics
    are therefore comparable only within one display setup. Screen
    fractions, pupils, blinks, fixation durations and saccade degrees are
    comparable across screens.
  - **User context:** clinical collection will normally use one fixed
    clinic screen.
  - **Backlog:** the proposed `metadata.json` additions
    (`device_pixel_ratio`, refresh rate) now live with the tracker
    rate/bus/serial and the new eye-geometry fields in
    `SPEC-gazepoint-analysis-export-parity.md` §10. The Setup-page
    "Display" check proposed in conversation is not yet a backlog item.
  - Still no code changed. This SPEC, including every entry above
    previously marked "uncommitted", is committed with this entry (see
    `git log -- docs/specs/SPEC-display-scaling-cursor-accuracy.md`).

- **2026-10-01 — YAML frontmatter added** (name, status, dates, next step,
  related SPECs). No content change; still no code changed.

- **2026-10-01, later — §7 re-triaged, §8 implementation brief added; Log
  renumbered §8 → §9.** The user noticed §7 still listed the evaluation
  questions as open while the questions that block implementation (which
  §6 option; mixed-scale monitors) were not listed anywhere. §7 now marks
  each question superseded/unanswered/assumed; §8 records decisions D1–D4
  (QScreen logical geometry, `SCREEN_SIZE` as a once-per-connect sanity
  check, pure helper for tests), scope, acceptance criteria and a
  `QT_SCALE_FACTOR` live check that reproduces the laptop condition on the
  24". Stale "unconfirmed" wording in §2/§5/§6 headings updated.

- **2026-10-02 — user decisions recorded; §8 approved for handoff.** Asked
  the user's preferences. D1 (Qt screen geometry, all-logical) chosen after
  a web comparison of other gaze software, added to §6.1: PsychoPy requires
  100 % scaling; **OptiKey** keeps everything in physical px (new row);
  Tobii Dynavox maps platform-side; diki is full-screen-logical. None
  requires a specific resolution. Gazepoint's own guide (blog "Understanding
  Screen Coordinates in Gazepoint Data", 2026-04-30) only gives
  `pixel = FPOGX × screen width` and does not mention scaling. D2 (log once
  per connect), §8.5 validation (simulate with `QT_SCALE_FACTOR` on the
  24"), and closing all of §7 as moot also chosen by the user. Committed
  and handed off to worktree `dpi-cursor-fix`.

- **2026-10-02, later — implementation route changed; §8 still not
  started.** The worktree handoff in the entry above never ran: launching
  it hit Claude Code's per-folder trust dialog, and a worktree session
  started in the repo folder lacks the top-level project's `/sparc:*`
  commands, agents and `.mcp.json` (no qt-mcp for §8.5). The user removed
  the `dpi-cursor-fix` worktree and branch and will implement §8 through a
  Sonnet 5.5 subagent launched from the Opus hub session instead. §8's
  content is unchanged. A background subagent cannot stop and ask, so for
  §8.7 it records the question and returns instead.

- **2026-10-02, later -- §8 implemented, reviewed, live-validated,
  committed.** The `spec-implementer` subagent (Sonnet 5.5) implemented D1-D4
  with 24 new tests and no open questions. The hub reviewed it, reran pytest,
  and ran the §8.5 live check with the user as subject: the cursor was on
  gaze at simulated 150 % and 125 % and at real 100 % (table in §8.6). The
  user approved the commit. Remaining: the real-laptop test, and a new item
  for the 150 % Tasks-page clipping.

- **2026-10-05 — §8.8 added and APPROVED (design only, not built).**
  `/spec-backlog` item #5: `_record_geometry()`'s canvas fields mix Qt
  logical and Gazepoint physical px. The user chose "all physical" via
  `AskUserQuestion` and approved the §8.8 text ("approve both, go ahead").
  Next: `spec-implementer` builds §8.8, then a live check at real 100 % and
  `QT_SCALE_FACTOR=1.5`.

- **2026-10-05, later — §8.8 IMPLEMENTED, reviewed, live-validated.**
  `spec-implementer` built it (log §8.8.4, no questions). Hub review: in
  scope, suite 324 / 0 at that point (362, then 365, after the next two
  fixes landed in the same tree). Live with the real GP3HD:
  `sessions/2026-10-05_UNITS100_click_static_run1` (real 100 %): canvas
  1640×957 at +0,+75, identical to before; `canvas_units: "physical"`;
  `CANVAS_RESIZED` 1920×957 / 1640×957.
  `..._UNITS150_click_static_run1` (`QT_SCALE_FACTOR=1.5`): canvas
  1500×932 at +0,+100 physical (= 1.5 × the logical window), log line
  "(physical px; Windows scale 150 %)", `CANVAS_RESIZED` 1920×932 /
  1500×932. Side note, not this fix: calibration error at simulated 150 %
  was 55.8 px against 21.3 px at 100 % (valid). Committed separately from
  `SPEC-ui-setup-task-selection.md` §25 and export-parity §10.6.10, which
  were validated in the same runs.
  Committed + pushed as `2d49f44`.
