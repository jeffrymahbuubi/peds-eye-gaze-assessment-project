![[_nav.md]]

## Grid Click 1 Configuration

Grid Click · Subject TESTING

> SPEC-compass-task-flow.md 4B. A full page opened by Configure Test on the Test List. It replaces the Settings dialog inside the dashboard (the old dialog stays only for standalone `--task X --gui`, see `task-settings.md`). Shown: Grid Click in its Standard state. Compass reference: `docs/compass/screenshots/06-*.png`. The nav is locked while this page is open.

> Three columns of cards. **Column A:** Test, Feedback. **Column B:** Target, the task card (here Grid Layout), Timing. **Column C:** Selection (Dwell), Gaze Smoothing. Every number is a slider plus a spin box (the existing SliderSpinRow), shown here as a number box.

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

### C · Selection (Dwell)

Dwell threshold (ms)
[800___]{type:number}

Refractory period (ms)
[500___]{type:number}

Jitter tolerance (px)
[40____]{type:number}

:::

::: grid-3 card

### A · Feedback

- [x] Show gaze cursor
- [x] Show dwell progress ring
- [x] Show instant on-target ring
- [x] Play hit sound
- [x] Play miss sound

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

### C · Gaze Smoothing

- [x] Smoothing enabled

Smoothing alpha
[0.22__]{type:number}

Greyed (not hidden) while Smoothing enabled is off: the only dependent control.

:::

::: grid-3 card

### (column A ends)

—

### B · Timing

Trial timeout (ms)
[8000__]{type:number}

Inter-trial interval (ms)
[800___]{type:number}

### (column C ends)

—

:::

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
> - Column C: Selection (Dwell), then Gaze Smoothing.
> - At 1920x1080 @ 100 % nothing scrolls. At larger scaling the cards scroll and the footer stays visible.

### Task-specific cards

::: grid-3 card

### Static Click

Target card only (no task card). Defaults: 32 trials, timeout 8000, interval 800.

### Follow & Click — Motion

Movement path: (*) Circular ( ) Horizontal ( ) Vertical ( ) Diagonal ↘ ( ) Diagonal ↙ · Target speed (frac/s) 0.20 · Timing card gains "Selection window (ms) 2500".

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
