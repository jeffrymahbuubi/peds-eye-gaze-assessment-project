![[_nav.md]]

> **Dashboard part SUPERSEDED (SPEC-compass-task-flow.md, 2026-10-06):** inside the dashboard, settings move to the full configuration page (`task-config.md`). This dialog stays only for the standalone `--task X --gui` path (HB11) and now also shows Play hit sound / Play miss sound check boxes.

## Task settings dialog — target size presets and movement paths

> SPEC-target-size-and-motion-paths.md §4.5. The pre-launch dialog opened by **Run** on the Tasks page. Two new dropdown controls replace a px slider (Grid Click) or add a choice that today exists only in YAML (Follow & Click). All other rows (sliders with a number box) are unchanged. Numbers below are for a 24" 1920x1080 monitor at 650 mm.

---

::: grid-2 card

### A · Grid Click

Number of trials
[18___________________________]{type:number}

Target size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

Grid rows
[6____________________________]{type:number}

Grid cols
[6____________________________]{type:number}

|Will be shrunk to ≈ 111 px to fit a 6 x 6 grid (approximate)|{.warning}

[Start task]* [Cancel]{.outline}

### B · Follow & Click

Number of trials
[6____________________________]{type:number}

Target size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

Movement path
[Circular____________________v]
- Circular
- Horizontal ↔
- Vertical ↕
- Diagonal ↘ (top-left ↔ bottom-right)
- Diagonal ↙ (top-right ↔ bottom-left)

Selection window (ms)
[2500_________________________]{type:number}

[Start task]* [Cancel]{.outline}

:::

> **A — Target size:** replaces the old "Target radius (px)" slider for Grid Click only (Phase A). Each item names the preset, its visual angle, and the diameter on *this* monitor, so the operator can picture it. Default = the task YAML's `target.size` (Medium).
>
> **A — Shrink hint:** shown only when the chosen size is estimated not to fit the chosen rows x cols (in a 6 x 6 grid even Small is shrunk slightly: a cell fits ≈ 111 px on a ~1000 px tall canvas). It updates live when the size, rows or cols change, and is hidden otherwise. It is an estimate from the screen height; the real fit is applied per frame during the run (target + hitbox kept inside the cell) and the size actually used is saved per trial.
>
> **B — Movement path:** new; default = the task YAML's `motion.path` (Circular). Every straight path moves at the same on-screen speed (the live "Target speed" slider keeps its meaning). Phase B: Follow & Click's "Target radius (px)" slider is replaced by the same Target size combo (no hint: near the edge the path's turn-around points move inward, the size never changes).
>
> **Both:** the chosen values are recorded in the session's metadata and stored in / restored from a settings profile, like every other dialog value.

---

## Phase B — size presets for the other tasks (SPEC §11)

::: grid-2 card

### C · Static Click

Number of trials
[32___________________________]{type:number}

Target size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

[Start task]* [Cancel]{.outline}

### D · Scanning Search

Number of trials
[6____________________________]{type:number}

Icon size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

Number of icons
[8____________________________]{type:number}

|Icons will be shrunk to ≈ 202 px to fit 8 icons (approximate)|{.warning}

[Start task]* [Cancel]{.outline}

:::

> **C — Target size:** replaces "Target radius (px)". No hint: a target that would cross the canvas edge (e.g. Large on the top/bottom row) is moved inward instead, so the size is the same on every trial. The position actually used is saved per trial.
>
> **D — Icon size:** replaces "Icon radius (px)". The size is the *visible* icon, so a Medium icon looks exactly as big as a Medium circle in the other tasks. The hint appears only when the icons would overlap each other or the edge (Large, or many icons); all icons then shrink together, and a look at a neighbouring icon never counts as the target.
>
> **All four tasks:** no px radius control remains. "Jitter tolerance (px)" in the live Settings card is unchanged (out of scope).

---

## Grid Click — cell gap (SPEC-grid-cell-gap.md §4.5)

::: grid-2 card

### E · Grid Click, 3 x 3, Wide gap

Number of trials
[18___________________________]{type:number}

Target size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

Grid rows
[3____________________________]{type:number}

Grid cols
[3____________________________]{type:number}

Cell gap
[Wide — 1° (≈ 41 px)_________v]
- Standard
- Wide — 1° (≈ 41 px)
- Extra wide — 2° (≈ 82 px)

|Will be shrunk to ≈ 201 px to fit a 3 x 3 grid (approximate)|{.warning}

[Start task]* [Cancel]{.outline}

### F · Grid Click, 6 x 6, Extra wide gap (capped)

Number of trials
[18___________________________]{type:number}

Target size
[Medium — 5° (≈ 205 px)______v]
- Small — 3° (≈ 123 px)
- Medium — 5° (≈ 205 px)
- Large — 8° (≈ 328 px)

Grid rows
[6____________________________]{type:number}

Grid cols
[6____________________________]{type:number}

Cell gap
[Extra wide — 2° (≈ 82 px)___v]
- Standard
- Wide — 1° (≈ 41 px)
- Extra wide — 2° (≈ 82 px)

|Gap limited to ≈ 60 px and targets shrunk to ≈ 61 px to fit a 6 x 6 grid (approximate)|{.warning}

[Start task]* [Cancel]{.outline}

:::

> **Cell gap:** new row, Grid Click only, placed after Grid cols. Default = **Standard**, which is exactly today's board (gap = 12 % of a cell; ≈ 29 px on 3 x 3, ≈ 15 px on 6 x 6). Wide and Extra wide set the space between two neighbouring cells by visual angle, so it is the same px for every child on this monitor; each item shows its px.
>
> **Dead zone:** with Wide / Extra wide, a look into the gap selects no cell, even within the jitter tolerance; moving into the gap counts as leaving the target.
>
> **Hint:** recomputed when the gap, rows, cols or size change. The board's outer size stays the same, so a wider gap makes the cells (and possibly the target) smaller: E shows Medium shrunk slightly on 3 x 3. On dense grids the gap is limited to half a cell (F: 82 px wanted, ≈ 60 px used) and the hint says so; the run records it (`GAP_CAPPED` + a Log line).
>
> **Recorded:** the chosen gap goes into the session metadata and the Log ("Cell gap: Wide — 1° (≈41 px)") and is saved in / restored from a settings profile.

```
 Standard (today)                 Wide / Extra wide
 +--------+--------+              +-------+   +-------+
 | [cell] | [cell] |              | cell  |   | cell  |
 |  ( o ) |  ( o ) |              | ( o ) |   | ( o ) |
 +--------+--------+              +-------+   +-------+
 hit areas reach the cell edge            gap = no-hit zone
 and touch the neighbour's        +-------+   +-------+
                                  | cell  |   | cell  |
                                  +-------+   +-------+
```

---

### Movement paths (Follow & Click)

```
 Circular            Horizontal            Vertical            Diagonal TL-BR        Diagonal TR-BL
 +-----------+       +-----------+         +-----------+       +-----------+         +-----------+
 |   .---.   |       |           |         |     ^     |       | o         |         |         o |
 |  /     \  |       |           |         |     |     |       |   \       |         |       /   |
 | |   +   | |       | o<------->|         |     |     |       |     \     |         |     /     |
 |  \     /  |       |           |         |     |     |       |       \   |         |   /       |
 |   '---'   |       |           |         |     v     |       |         v |         | v         |
 +-----------+       +-----------+         +-----------+       +-----------+         +-----------+
 unchanged           y random/trial        x random/trial      corner to corner      corner to corner
                                                               (bounces back)        (bounces back)
```
