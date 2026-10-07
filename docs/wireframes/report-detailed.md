![[_nav.md]]

## Detailed Results:

> SPEC-compass-task-flow.md 4D.2 and 4D.7. Same page as `report-summary.md`, switched with View Details / View Summary. The header, banner, left column (Test Configuration + Notes) and footer are identical, so they are shortened here. Compass reference: `docs/compass/screenshots/08b-*.png`.

::: grid-2

### Test Name

[Grid Click 1____________________________________]

### {.right}

Subject: **TESTING** · Test Date: **Oct 6, 2026 2:06 PM**

Evaluator
[Dr. Lin______________]

:::

::: layout {.sidebar-main}

::: sidebar

#### Test Configuration

Configuration Name: **Large targets**

> (same 17 rows as the Summary view)

#### Notes

[Good attention for the first 10 trials...]{rows:4}

:::

::: main

#### Trial-by-Trial Results

| Trial | Size (deg) | Distance (deg) | Outcome | Trial Time (s) | Reaction Time (s) | Entries | Fixations | Mean fix. dur. (s) | Saccades | Mean peak vel. (deg/s) | Pupil (mm) | Pupil change (mm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **4.4** | **—** | **Hit** | **1.10** | **0.30** | **1** | **3** | **0.25** | **3** | **70** | **3.6** | **+0.05** |
| 2 | 4.4 | 9.8 | Hit | 1.32 | 0.41 | 2 | 5 | 0.22 | 5 | 81 | 3.6 | +0.02 |
| 3 | 4.4 | 13.9 | Not selected | 8.00 | 0.95 | 3 | 14 | 0.30 | 13 | 77 | 3.7 | +0.11 |
| 4 | 4.4 | 9.8 | Skipped | — | — | — | — | — | — | — | — | — |
| 5 | 4.4 | 9.8 | Hit | 1.05 | 0.22 | 1 | 3 | 0.26 | 2 | 66 | 3.5 | -0.03 |

> **Table rules:**
> - The first row is selected when the page opens; the selected row is shown in bold.
> - Click any header to sort.
> - The Trial column stays frozen, and the table scrolls sideways below about 1500 px.
> - Skipped rows are greyed, with "—" metrics.
> - A partial run lists only the trials that were presented.
> - Size is the real drawn diameter, so it can be smaller than the preset when a grid cell capped it. Distance = the visual angle from the previous target.

> **Selection = Switch** (SPEC-input-selection-and-follow.md 4.5, added 2026-10-07): two columns after Entries, **Clicks** and **Click errors** (e.g. trial 2: 2 · 1). Not shown with Dwell.

#### Trial-by-Trial Results — Follow the Target

| Trial | Path | Outcome | Duration (s) | Time on target (%) | Mean distance (deg) | Time to find (s) | Pursuit gain | Catch-up sacc. (/s) | Valid (%) | Fixations | Saccades | Pupil (mm) | Pupil change (mm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **Circular** | **Followed** | **10.0** | **74** | **1.8** | **0.40** | **0.78** | **1.2** | **95** | **12** | **14** | **3.6** | **+0.03** |
| 2 | Circular | Followed | 10.0 | 81 | 1.5 | 0.35 | 0.81 | 1.0 | 97 | 9 | 11 | 3.6 | +0.01 |
| 3 | Circular | Not followed | 10.0 | 41 | 3.9 | 1.20 | 0.55 | 2.3 | 84 | 21 | 24 | 3.7 | +0.09 |

> Follow table: the follow metrics of the summary per trial, then the usual eye columns. Outcome = Followed / Not followed (on target ≥ 50 %). A Mouse run without the tracker shows "—" in the gain, catch-up and eye columns. Old Follow & Click sessions keep their old layout (H10).

#### Selected trial — Trial 1

```
+------------------------------------------------------------------+
|                                                                  |
|                  ⓢ onset                                         |
|                    \  1                                          |
|                     o----.                                       |
|                           \   2         .- - - - -.              |
|                            o-----------(   ●  3    )  ← target   |
|                                         '- - - - -'   + dashed   |
|                                               ★ selected  hitbox |
|      smoothed gaze path dark → light by time; circles = fixations|
|      size ∝ duration, numbered in order                          |
+------------------------------------------------------------------+
  Scan path 12.3 deg · 3 fixations · 3 saccades
```

> **Selected-trial map:**
> - It is the same map widget as on the Summary, showing one trial.
> - Up/Down keys move the selection, and the map follows.
> - For Follow the Target it draws the target's track during the trial plus the smoothed pointer path; samples off target are drawn lighter (legend: on target / off target).

:::

:::

---

::: row
[Print Report]{.outline} [View Summary]{.outline} [Save & Continue]* [Cancel]{.outline}
:::
