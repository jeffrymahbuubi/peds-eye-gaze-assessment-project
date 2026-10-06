![[_nav.md]]

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
