![[_nav.md]]

## Calibration window (App, Grid 3 style)

> SPEC-app-drawn-calibration.md 4.1-4.6. A frameless **full-screen window** on the tracked monitor, over the taskbar, opened by **Do Calibration** (Setup) or **Calibrate** (Start-test page) when "Calibration screen" = App. The nav bar above is only the wireframe's; the real window has none. Reference: the Grid 3 recording, `docs/calibration-video/frames/`. Five states, shown one after another below.

---

### State 1 · Glide (one point, DELAY seconds)

```text
+------------------------------------------------------------------------------+
|                                                                         x    |
|      (BEE)  . . . . .                                                        |
|                       . . . .                                                |
|                               . . . (bee)                                   |
|                                          glides, eased, large (~6 % width)  |
|                                          slow +/-8 deg wobble               |
|                                                                              |
|                                                                              |
|                                                                   (o) target |
+------------------------------------------------------------------------------+
```

> On each `CALIB_START_PT` the icon glides from where it is to the point's CALX/CALY (the first point: it enters from the top-left corner). Plain background (Setup's Background setting: white, black or grey); no text, no progress, **no sound**; only a faint close **x** top right (Esc does the same: cancel). The mouse cursor stays visible.

### State 2 · Hold (sampling, until CALIB_RESULT_PT)

```text
+------------------------------------------------------------------------------+
|                                                                         x    |
|                                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|                                                                   (b)        |
|                                                     shrunk (~1.8 %), still  |
+------------------------------------------------------------------------------+
```

> At most DELAY after the point started, the icon has shrunk to the small size and **holds still** until that point's `CALIB_RESULT_PT`, because Control samples gaze from then on. Order of the 5 points: top-left, bottom-right, top-right, bottom-left, centre, at 10 % / 90 % (9 points add the edge midpoints).

### State 3 · Processing

```text
+------------------------------------------------------------------------------+
|                                                                         x    |
|                                                                              |
|                                                                              |
|                         Processing calibration results                      |
|                                   o o o                                      |
|                                                                              |
|                                                                              |
|                                                                              |
+------------------------------------------------------------------------------+
```

> From the last point until `CALIB_RESULT` (usually under a second; Grid 3 shows about 2 s). Improve calibration is not available yet.

### State 4 · Results map

```text
+------------------------------------------------------------------------------+
|                                                                         x    |
|   +----------------------------------------------------------------------+   |
|   |  (77)                                                        (97)    |   |
|   |  thick amber ring                                                    |   |
|   |                                (96)                                  |   |
|   |                                                                      |   |
|   |  (98)                                                        (95)    |   |
|   +----------------------------------------------------------------------+   |
|        1 point needs attention. Check the head position, then Improve        |
|        calibration.                                                          |
|                                                                              |
|   [Improve calibration]   [Show Monitor]                           [Back]    |
+------------------------------------------------------------------------------+
```

> **Results map** (4.4, Q1, D2): a rectangle for the screen with one circle per point at its position. Each circle holds an integer score 0-100 = round(100 x max(0, 1 - error_deg / 3)), where the error is the per-point gaze error in degrees averaged over the valid eyes. Colours (design tokens): **green** 1 deg or less, **amber** up to 2 deg, **red** above 2 deg; a point with no valid eye is a grey circle with "-". Amber and red points get a thicker ring, and the line under the map counts them ("All points are good." when none). No overall score here; the Setup badge keeps "Calibrated, 5 points, 1.8°".
> **Improve calibration** (Q2): runs all points again (states 1-4); the new result replaces the old one. **Show Monitor**: state 5. **Back**: closes the window and returns to the page that opened it (Setup, or the Start-test page for Calibrate). There is no separate "accept": the last result is the one kept, as in Grid 3.

### State 5 · Show Monitor

```text
+------------------------------------------------------------------------------+
|                                                                         x    |
|   +-------------------------------+                                          |
|   |  +-------------------------+  |   results map stays behind,             |
|   |  |       .------.          |  |   dimmed                                |
|   |  |      ( o    o )         |  |                                          |
|   |  |      (   \__/ )         |  |                                          |
|   |  |       '------'          |  |                                          |
|   |  +-------------------------+  |                                          |
|   |  Close |---[==*==]---| Far    |                                          |
|   |  ● Good position, 64 cm       |                                          |
|   +-------------------------------+                                          |
|   [Improve calibration]   [Hide Monitor]                           [Back]    |
+------------------------------------------------------------------------------+
```

> The head-position widget from SPEC-gaze-stability-and-positioning (face in the head box, Close-Far bar, hint line), as a panel over the dimmed results map. The button toggles between **Show Monitor** and **Hide Monitor**. Typical use: a red or amber point, fix the seating with the face green, then Improve calibration.

---

### Fallback alert (shown on the opening page afterwards)

::: alert warning
▲ Warning: The app's calibration screen did not respond, so Gazepoint Control's own calibration was used.
:::

> 4.2: no `CAL` record within DELAY + 1 s (or a later point more than DELAY + TIMEOUT + 1 s late) closes the window, re-runs the calibration once with Control's own window, and shows this alert on Setup or the Start-test page. Logged to `_diagnostics/calibration_timing.jsonl` as `mode: control_fallback`.
