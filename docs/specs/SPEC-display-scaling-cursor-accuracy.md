# SPEC-display-scaling-cursor-accuracy — Gaze cursor accuracy degrades on 15"/13" 1920×1080 laptops

**Status: ROOT CAUSE CONFIRMED by user A/B test (evaluation only, no code
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
**Last updated:** 2026-09-30

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
| **A. Windows display scaling × mixed pixel units in `_sync_gaze_geometry()`** | **Primary cause (high confidence, one assumption unconfirmed, see §5)** | 0 mm at 100 %; **43 mm** (125 %) / **72 mm** (150 %) at screen centre for *perfect* gaze. Cursor lands off-canvas toward the right and bottom |
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

## 5. Unconfirmed assumption and how to settle it (no code needed)

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

## 6. Fix direction (not implemented, for the follow-up task)

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

## 7. Open questions

- Actual Windows scale of the 15" and 13" laptops (§5 step 1).
- Exact diagonals: 15" vs 15.6", 13" vs 13.3". This only changes the mm
  column, not the verdict.
- Was calibration re-run on each laptop screen?
- Which cursor was judged: ours on the task canvas (assumed), or Control's
  Gaze Pointer?

## 8. Log

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
