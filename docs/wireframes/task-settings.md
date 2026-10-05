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

Target radius (px)
[100__________________________]{type:number}

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
> **B — Movement path:** new; default = the task YAML's `motion.path` (Circular). Every straight path moves at the same on-screen speed (the live "Target speed" slider keeps its meaning). Follow & Click still uses the px radius in this round — it moves to Small/Medium/Large in Phase B.
>
> **Both:** the chosen values are recorded in the session's metadata and stored in / restored from a settings profile, like every other dialog value.

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
