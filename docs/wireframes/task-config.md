![[_nav.md]]

## Grid Click 1 Configuration

Grid Click · Subject TESTING

> SPEC-compass-task-flow.md 4B. A full page opened by Configure Test on the Test List. It replaces the Settings dialog inside the dashboard (the old dialog stays only for standalone `--task X --gui`, see `task-settings.md`). Shown: Grid Click in its Standard state. Compass reference: `docs/compass/screenshots/06-*.png`. The nav is locked while this page is open.

> Three columns of cards. **Column A:** Test, Feedback. **Column B:** Target, the task card (here Grid Layout), Timing. **Column C:** Input, Dwell, Gaze Smoothing. Every number is a slider plus a spin box (the existing SliderSpinRow), shown here as a number box.

> SPEC-input-selection-and-follow.md 4.1 (added 2026-10-07): the **Input** card (Pointer + Selection), the card "Selection (Dwell)" renamed **Dwell**, and "Glow on target" in Feedback. Shown: Gaze + Dwell, the default.

::: grid-3 card

### A · Test

Test Name
[Grid Click 1_________________]

Configuration Name
[Standard_________________v]
- Standard
- Large targets
- Saved 10/05 14:12

Modified from "Standard"

[Reset to defaults]{.outline}

Number of Trials
[18____]{type:number}

Notes
[Child tired after lunch...]{rows:3}

### B · Target

- ( ) Small — 3° (≈123 px)
- (*) Medium — 5° (≈205 px)
- ( ) Large — 8° (≈328 px)

### C · Input

Pointer (what moves the pointer)
- (*) Gaze
- ( ) Mouse

Selection (how a target is selected)
- (*) Dwell — keep looking at the target
- ( ) Switch — look at the target, then press the switch

Pointer is on every task. Selection is on Static Click, Grid Click and Scanning Search; Follow the Target has none.

:::

::: grid-3 card

### A · Feedback

- [x] Show gaze cursor
- [x] Show dwell progress ring
- [x] Show instant on-target ring
- [x] Glow on target
- [x] Play hit sound
- [x] Play miss sound

"Show dwell progress ring" is greyed while Selection = Switch. "Glow on target" (default on) is greyed while Selection = Dwell, as here.

### B · Grid Layout

Grid rows
[3_____]{type:number}

Grid cols
[3_____]{type:number}

Cell gap
- (*) Standard
- ( ) Wide — 1° (≈41 px)
- ( ) Extra wide — 2° (≈82 px)

Amber hint when it does not fit: "Targets will be shrunk to about 180 px to fit a 3x3 grid with this gap."

### C · Dwell

Dwell threshold (s)
[0.8___]{type:number}

Refractory period (s)
[0.5___]{type:number}

Jitter tolerance (px)
[40____]{type:number}

While Selection = Switch only "Dwell threshold" is greyed. Refractory and jitter tolerance stay active: the hitbox and the debounce apply to the switch too.

:::

::: grid-3 card

### (column A ends)

—

### B · Timing

Trial timeout (s)
[8_____]{type:number}

Inter-trial interval (s)
[0.8___]{type:number}

### C · Gaze Smoothing

- [x] Smoothing enabled

Smoothing alpha
[0.22__]{type:number}

Greyed (not hidden) while Smoothing enabled is off: the only dependent control.

:::

> **State: Selection = Switch** (same page, nothing moves or disappears): the Input card shows "(*) Switch"; in Feedback "Show dwell progress ring" is greyed and "Glow on target" is active; in Dwell only the threshold is greyed.

> **State: Pointer = Mouse:** nothing extra is greyed. Dwell with the mouse = hover dwell. With Selection = Switch, the mouse's own left button is the switch.

---

::: row
[Preview Test]{.outline} [Save & Continue]* [Cancel]{.outline}   Test Name is already used by another test of this subject.
:::

> **Footer** (pinned under the scroll area, always visible):
> - **Preview Test** is always enabled. It runs 3 trials with the mouse and records nothing.
> - **Save & Continue** is disabled while invalid, and the muted text beside it gives the reason.
> - **Cancel** asks first if there are edits.
> - Enter never saves.

> **Layout:**
> - Column A: Test, then Feedback.
> - Column B: Target, then the task card (Grid Layout / Motion / Icons), then Timing.
> - Column C: Input, then Dwell, then Gaze Smoothing.
> - At 1920x1080 @ 100 % nothing scrolls. At larger scaling the cards scroll and the footer stays visible.

### Task-specific cards

::: grid-3 card

### Static Click

Target card only (no task card). Defaults: 32 trials, timeout 8000, interval 800.

### Follow the Target — Motion

Movement path: Circular (selected) / Horizontal / Vertical / Diagonal ↘ / Diagonal ↙ · Target speed (frac/s) 0.20.

Input card: Pointer only, no Selection radio. No Dwell card. Feedback: gaze cursor, "Glow on target", hit sound (plays at the end of a followed trial); no dwell progress ring, no miss sound. Timing card: "Trial duration (s) 10" (3–30, step 0.5) and the inter-trial interval; no selection window.

### Scanning Search — Icons

Icon size Small / (*) Medium / Large · Number of icons 4 · amber hint "Icons will be shrunk to ≈ N px to fit K icons" when needed.

:::

---

### Preview Test (run screen with the Preview bar)

```
+--------------------------------------------------------------------------------------+
|                                                                                      |
|                                                                                      |
|                        TASK CANVAS (full window, title bar hidden)                   |
|                                                                                      |
|                                 ( target )        ↖ OS mouse pointer visible         |
|                                     o  smoothed gaze dot follows the mouse           |
|                                                                                      |
+--------------------------------------------------------------------------------------+
| PREVIEW · Trial 2/3 · mouse pointer · nothing is recorded                            |
|                   [ Pause (Alt-P) ]   [ Skip trial ]   [ Quit (Alt-Q) ]              |
+--------------------------------------------------------------------------------------+
```

> Preview uses the unsaved form values, 3 trials and its own seed (never the real run's first targets). It needs no tracker or calibration. Quit, Esc or the last trial returns to this page exactly as it was, and the footer then reads "Preview finished. Nothing was recorded."

---

## Modals & Dialogs

> Not visible on page load.

::: modal

## Save as a new configuration

Standard cannot be changed. Save these settings as:

[Custom 1_________________________]

[Save]* [Cancel]

:::

::: modal

## Configuration exists

'Large targets' already exists with different settings.

[Update 'Large targets']* [Save under a new name...] [Cancel]

:::

::: modal

## Load configuration

Replace your edits with configuration 'Large targets'?

[Replace]* [Keep my edits]

:::

::: modal

## Discard changes

Discard your changes?

[Discard]{variant:danger} [Keep editing]*

:::

> Each configuration is a named set of values per subject and task. A name always loads its newest saved version. Nothing is ever deleted or overwritten. Earlier tests keep their own copy of the settings they ran with.
