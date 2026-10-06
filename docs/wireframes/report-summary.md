![[_nav.md]]

## Summary Results:

> SPEC-compass-task-flow.md 4D.2–4D.3 and 4D.7–4D.8 (U9–U11). It opens from View Report on the Test List, or from "Save and View Report" in the Test Complete dialog. It replaces the old Results tab (`results.md`, superseded). The numbers come from `report.json`, which P4 built at the end of the run. The nav is locked while the report shows. Compass reference: `docs/compass/screenshots/08a-*.png`.

::: grid-2

### Test Name

[Grid Click 1____________________________________]

### {.right}

Subject: **TESTING** · Test Date: **Oct 6, 2026 2:06 PM**

Evaluator
[Dr. Lin______________]

:::

::: alert warning
Ended early — 7 of 18 trials.
:::

> The banner shows only for an early-ended run, or when valid gaze during trials is under 80 % ("Gaze data is low quality: 72 % valid").

::: layout {.sidebar-main}

::: sidebar

#### Test Configuration

Configuration Name: **Large targets**

| Setting | Value |
|---|---|
| Configuration name | Large targets |
| Task | Grid Click |
| Input | Eye (dwell) · GP3 HD 150 Hz |
| Trials (planned) | 18 |
| Selection | Dwell 800 ms, refractory 500 ms |
| Target size | Large — 8° (328 px), capped to 180 px |
| Layout | Grid 3x3, gap Standard |
| Maximum time per trial | 8.0 s |
| Pause between trials | 0.8 s |
| Theme | Forest |
| Gaze cursor shown | Yes |
| Feedback | Hit sound, miss sound |
| Gaze smoothing | On, alpha 0.22 · jitter 40 px |
| Display | 1920x1080 @ 100 % (standard) |
| Viewing distance | 600 mm |
| Calibration | 9 points, 0.6° mean, measured |
| Canvas | 1920x1036 px |

#### Notes

[Good attention for the first 10 trials...]{rows:4}

:::

::: main

One cell of a visible board lights up; the child selects it by looking at it.

#### Summary of Results

| | % (N) | Trial Time (s) | Reaction Time (s) | Entries |
|---|---|---|---|---|
| Error-free Target Selections | 61% (11/18) | 1.12 | 0.28 | 1.0 |
| All Targets Selected | 89% (16/18) | 1.25 | 0.31 | 1.3 |
| Targets Not Selected | 11% (2/18) | 8.00 | 0.95 | 2.5 |
| All Trials | 100% (18/18) | 2.00 | 0.36 | 1.4 |

1 skipped trial(s) excluded. Target area = drawn target + 40 px tolerance ring. Reaction Time = onset to the first gaze entry; about 0 if the gaze already rested on the new target's place.

#### Target Map

- [x] Targets
- [ ] Gaze path
- [ ] Heat map

```
+------------------------------------------------------------------+
|   .- - -.        .- - -.        .- - -.                          |
|  (  1,10 )      (   2   )      (  X 5  )     faint = grid cells  |
|   '- - -'        '- - -'        '- - -'                          |
|   .- - -.        .- - -.        .- - -.     ● hit (real radius)  |
|  (  3, 9 )      (  ● 4  )      (   6   )     X not selected      |
|   '- - -'        '- - -'        '- - -'     ◌ skipped (dashed)   |
|   .- - -.        .- - -.        .- - -.                          |
|  (   7   )      (   8   )      (  ◌ 11 )     drawn at the canvas |
|   '- - -'        '- - -'        '- - -'      aspect ratio        |
+------------------------------------------------------------------+
  Legend: ● hit   X not selected   ◌ skipped   numbers = trials on that cell
```

> **Overlays:**
> - Gaze path draws each trial's path in a 6-colour cycle.
> - Heat map is an alpha ramp over the whole test.
> - Follow & Click also shows the target's track as a faint line, with the mark at its end position.

#### Eye Metrics

| Metric | Value |
|---|---|
| Fixations | 76 (4.2 per trial) |
| Mean fixation duration | 240 ms (median 210) |
| Saccades | 76 |
| Mean saccade amplitude | 2.9° |
| Mean peak saccade velocity | 74 deg/s (max 180) |
| Scan-path length per trial | 12.3° |
| Mean pupil diameter | 3.6 mm |
| Mean pupil change from baseline | +0.04 mm (+1.1 %) |
| Valid gaze during trials | 94 % |
| Calibration error | 0.6° (24 px), measured |

> Peak saccade velocity is a smoothed value (accepted 2026-10-06). Compare it only between children measured on the same device and sample rate. Old sessions without the new fields show "—".

:::

:::

---

::: row
[Print Report]{.outline} [View Details]{.outline} [Save & Continue]* [Cancel]{.outline}
:::

> **Footer:**
> - **Save & Continue** keeps Test Name, Evaluator and Notes (the only editable fields), then returns to the Test List.
> - **Cancel** drops those edits.
> - **Print Report** exports a PDF (A4 landscape) to `TESTING_Grid Click 1_2026-10-06.pdf` in the subject's folder. The PDF holds the header, configuration, both tables, the map with Targets only, the Trial-by-Trial table and the definitions.
> - The run data itself is never editable.
