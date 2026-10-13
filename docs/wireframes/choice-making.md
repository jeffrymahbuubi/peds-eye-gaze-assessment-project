![[_nav.md]]

## Choice-making: configuration, run screen and report

> SPEC-scene-cause-effect-task.md step 1 (UI gate). The fifth test, offered in Add test only (S8). Three parts on this page: **A** the configuration page, **B** the run screen, **C** the report. Everything not shown here is the same as for the other tests: `task-config.md`, `run.md`, `run-end.md`, `report-summary.md`, `report-detailed.md`.

---

## A · Choice-making 1 Configuration

Choice-making, subject TESTING

> Same page and footer as `task-config.md`, same three columns. Changes for this test: **no Target card** (button size comes from the 7 x 5 grid, H12) and the task card is **Scene**. Column A: Test, Input. Column B: Scene, Timing, Feedback. Column C (Gaze Pointer Settings): Dwell, Gaze Smoothing.

::: grid-3 card

### A · Test

Test Name
[Choice-making 1_____________]

Configuration Name
[Standard_________________v]
- Standard
- Saved 10/12 10:05

Changed from Standard

[Reset to defaults]{.outline}

Number of Trials
[16____]{type:number}

Any number from 1 (W5). Objects are balanced as far as the count allows: object counts differ by at most 1, left and right by at most 1, never the same object twice in a row. 16 = each object twice.

Notes
[Child tired after lunch...]{rows:3}

### B · Scene

Scene
[Park_____________________v]
- Park

Prompt language
[English__________________v]
- English

Traditional Chinese is added later (Q7); the list has one item in v1.

Prompt
- (*) Voice
- ( ) Text
- ( ) Voice and text

Voice by default. Text shows the prompt sentence in a banner at the top of the scene (B1b) and works with no audio device; in Text mode the child can choose as soon as the text appears. The report marks the run's prompt mode (P1-P3).

- [ ] Visual cue: the target button gently pulses

Off by default (S3). When on, the report marks the run "Visual cue on".

Cell gap
- (*) Standard
- ( ) Wide (1°, about 41 px)
- ( ) Extra wide (2°, about 82 px)

Button size: 6.6° x 5.0° cell (about 274 x 206 px), read-only (H12).

### C · Gaze Pointer Settings: Dwell

Dwell threshold (s)
[0.8___]{type:number}

Refractory period (s)
[0.5___]{type:number}

Jitter tolerance (px)
[40____]{type:number}

A completed dwell on any button selects it; on a wrong button it counts as a wrong choice (H5).

:::

::: grid-3 card

### A · Input

Pointer (what moves the pointer)
- (*) Gaze
- ( ) Mouse

Selection (how a button is selected)
- (*) Dwell: keep looking at the button
- ( ) Switch: look at the button, then press the switch

### B · Timing

Time to choose (s)
[10____]{type:number}

Counted from the end of the spoken prompt (H9).

Pause after the animation (s)
[1.0___]{type:number}

The next prompt starts only after the animation and this pause.

### C · Gaze Pointer Settings: Gaze Smoothing

Gaze signal (what drives the cursor)
- (*) Raw gaze (BPOG)
- ( ) Fixation (FPOG)
- ( ) Assistive (APOG)

- [x] Smoothing enabled

Smoothing type
- (*) Simple
- ( ) Adaptive (One Euro)

Smoothing alpha
[0.22__]{type:number}

Same card as `task-config.md` (SPEC-gaze-stability-and-positioning.md 4.8); the greyed AAC filter length, Steadiness and Responsiveness rows are drawn there.

:::

::: grid-3 card

### (column A ends)

-

### B · Feedback

- [x] Show gaze cursor
- [x] Show dwell progress ring
- [x] Show instant on-target ring
- [x] Glow on the looked-at button
- [x] Play miss sound

No "Play hit sound": a correct choice plays the object's own animation and sound (H6). "Glow" is greyed while Selection = Dwell, as for the other tests; it follows the gaze, so it is not a cue.

### (column C ends)

-

:::

---

::: row
[Preview Test]{.outline} [Save & Continue]* [Cancel]{.secondary}
:::

> **Preview Test** runs 3 trials with the mouse, records nothing and plays the spoken prompts and the animations with their sounds (W7), so the operator can check the sound level before the child sits down.

> Defaults (H8, H9, section 4.8): 16 trials, 10 s to choose, 1.0 s pause, Park, English, visual cue off, Standard gap. Button size at 1920 x 1080 @ 100 %: canvas about 1920 x 1032, 41.4 px per degree.

---

## B · Run screen

> Same bar as `run.md` (48 px, Trial i of N, tracking badge, Pause / Skip trial / Quit). **The bar also shows the prompted object for the operator** ("Prompt: Balloons", W2), from the prompt start until the effect ends; between trials it is empty. The canvas is a 7 x 5 grid of equal cells: buttons in columns 0 and 6, rows 1-4; the scene fills columns 1-5 (H2). Cells (0,0) and (6,0) stay empty.

### B1 · Prompt playing (selection blocked)

```
+-------------+-----------------------------------------------------------+-------------+
|             |                                                           |             |
|  (empty)    |      cloud                                    balloons    |  (empty)    |
|             |                         rainbow                           |             |
+-------------+                                                           +-------------+
| [picture]   |                                                           | [picture]   |
| Balloons    |   apple tree               seesaw                         | Cloud       |
+-------------+                                                           +-------------+
| [picture]   |                                                           | [picture]   |
| Rainbow     |                     bike                                  | Bubbles     |
+-------------+                                                           +-------------+
| [picture]   |                                                           | [picture]   |
| Seesaw      |   swing                      girl with bubbles            | Bike        |
+-------------+                                                           +-------------+
| [picture]   |                                                           | [picture]   |
| Apples      |                    SCENE (park picture, about 4:3)        | Swing       |
+-------------+-----------------------------------------------------------+-------------+
| Trial 4 of 16   Prompt: Balloons   (● Tracking OK)   [ Pause (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
+---------------------------------------------------------------------------------------+
   Speaker: "Make the balloons pop!"  (audio only; nothing on the screen changes)
```

> **Prompt (H4, A3):** the spoken prompt plays at trial start. While it plays, the buttons are drawn normally, the dwell ring does not fill and a switch press does nothing. The 10 s to choose start when the prompt ends.

### B1b · Text prompt (Prompt = Text, or Voice and text)

```
+-------------+-----------------------------------------------------------+-------------+
|             |  +-----------------------------------------------------+  |             |
|  (empty)    |  |            Make the balloons pop!                   |  |  (empty)    |
|             |  +-----------------------------------------------------+  |             |
+-------------+      cloud          rainbow                  balloons     +-------------+
| [picture]   |                                                           | [picture]   |
| Balloons    |   apple tree               seesaw                         | Cloud       |
+-------------+                                                           +-------------+
|    ...      |                    SCENE (park picture)                   |    ...      |
+-------------+-----------------------------------------------------------+-------------+
| Trial 4 of 16   Prompt: Balloons   (● Tracking OK)   [ Pause (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
+---------------------------------------------------------------------------------------+
```

> **Text banner (P2):** a rounded caption strip across the top of the scene, large dark text on a light panel, the same sentence as the spoken prompt. The lettering is about 1.5° tall (about 60 px at 1920 x 1080, P6), on one line. It appears at the trial start and stays until the right choice or the timeout; it is hidden while the effect plays and between trials.
> **Timing (P3):** **Text:** no voice, selection is open at once, and the 10 s to choose start when the text appears. **Voice and text:** the voice plays as in B1 and blocks selection until it ends; the banner shows at the same time.

### B2 · Choosing

```
+----==>------+-----------------------------------------------------------+-------------+
| [picture]   |                                                           | [picture]   |
| Balloons    |      o gaze cursor on the Balloons button, border filling | Cloud       |
+-------------+                                                           +-------------+
```

> **Dwell progress (P4):** a thick accent line runs clockwise along the looked-at button's own rounded border, from top-centre back to top-centre (`====>` above is about 30 %). It stays on the button: nothing spills into the gap, the picture and the label stay clear. It replaces the circle ring, which overflowed the button by 16 px at the top and bottom. The thin instant outline (the moment the gaze lands) also lies inside the button's border now (P5).

> **Selection (H5):** a completed dwell (or a switch press) on any button selects it. **Right button:** the effect plays (B3). **Wrong button:** the miss sound, no animation (S4), the dwell ring resets and the trial goes on until the right choice or the 10 s run out. Gaze on the scene or in a gap selects nothing.

> **Visual cue on (S3):** from the prompt start until the choice or the timeout, the target button gently pulses (its border thickens and fades back, about once per second). Off by default.

### B3 · Effect playing

```
+-------------+-----------------------------------------------------------+-------------+
|             |                                               * pop! *    |             |
|             |                                               *  | |      |             |
+-------------+                                               strings     +-------------+
| [picture] ✓ |                                                           | [picture]   |
| Balloons    |       the chosen object animates in the scene;            | Cloud       |
+-------------+       everything else stays still                         +-------------+
```

> **Effect (section 4.4):** only the chosen object moves, with its own sound, for its set time (1.5-4.5 s). The selected button keeps a short highlight. The other buttons cannot be selected until the next prompt. The scene is back to its idle picture before the pause and the next prompt (A5).

> **Timeout (S5, H7):** after 10 s with no right choice the target's effect plays once anyway, as a model. It looks the same as B3 (the child still sees cause and effect); the report marks the trial "Modelled".

> **Pause** stops the prompt clock and freezes an animation mid-way; Resume continues it (A8). Skip trial ends the trial without an effect.

---

## C · Report

### C1 · Summary Results

> Same page, header, warning banner, left column and footer as `report-summary.md`. The left column's Test Configuration gains the rows below, and the main column shows the tables below in place of "Summary of Results" and "Target Map".

| Setting | Value |
|---|---|
| Task | Choice-making |
| Scene | Park, prompts in English |
| Prompt | Voice (or Text / Voice and text) |
| Visual cue | Off |
| Number of trials | 16 (each object twice; any number allowed) |
| Button size | 6.6° x 5.0° cell, gap Standard |
| Time to choose | 10.0 s from the prompt end |
| Pause after the animation | 1.0 s |

A spoken prompt names one of 8 buttons; the chosen object in the scene comes alive.

#### Summary of Results

| | % (N) | Reaction Time (s) | Wrong choices | Looked back | Look-back latency (s) |
|---|---|---|---|---|---|
| Right on the first choice | 56% (9/16) | 2.10 | 0.0 | 89% (8/9) | 0.42 |
| All right choices | 81% (13/16) | 2.85 | 0.4 | 85% (11/13) | 0.45 |
| Not chosen in time (modelled) | 19% (3/16) | 10.00 | 1.3 | 33% (1/3) | 0.80 |
| All trials | 100% (16/16) | 4.18 | 0.6 | 75% (12/16) | 0.47 |

Reaction Time = prompt end to the right choice. Wrong choices = completed selections on another button. Looked back = at least 0.1 s of gaze on the animating object (its area plus 1°) during the animation and 0.5 s after it. Latency = animation start to the first look. Modelled trials are counted apart.

#### By button side

| Side | Right choices | Reaction Time (s) | Looked back |
|---|---|---|---|
| Left buttons | 88% (7/8) | 2.60 | 86% (6/7) |
| Right buttons | 75% (6/8) | 3.15 | 83% (5/6) |

#### While choosing

| Gaze on | Share of the time to choose |
|---|---|
| Scene | 38% |
| Buttons | 52% |
| Elsewhere | 10% |

Measured from the prompt end to the choice or the timeout, valid gaze only (S7). Valid gaze while choosing: 92 %.

#### Scene Map

- [x] Buttons and objects
- [ ] Scanpath
- [ ] Heat map

```
+------------------------------------------------------------------------------+
| [ ]  |                                                             | [ ]     |
|------|   [- - cloud area - -]                     [- balloons -]   |---------|
| ●2   |                    [- - rainbow - -]                        | ●2      |
| Ball.|                                                             | Cloud   |
|------|  [- - apple tree - -]      [- seesaw -]                     |---------|
| ●1 X1|                                                             | ●2      |
| Rain.|                   [- bike -]                                | Bubbles |
|------|                                                             |---------|
| ●2   |  [- swing -]                  [- bubbles -]                 | ●1 X1   |
| Seesw|                                                             | Bike    |
|------|                                                             |---------|
| ●2   |                                                             | ●1 X1   |
| Apple|                                                             | Swing   |
+------------------------------------------------------------------------------+
```

> **Scene Map:** the canvas drawn at its aspect, the idle scene faint, each object's look-back area as a dashed box, each button with its marks: ● right choices (count), X not chosen in time (count). Scanpath and Heat map as in `report-summary.md`. A Mouse run draws the mouse path and labels look-back "pointer, not gaze" (section 4.6).

> **Visual cue on:** the Test Configuration row reads "Visual cue: On" and an info line above the summary says "Visual cue was on: the target button pulsed." **Mouse run:** the look-back columns keep their values but the header reads "Pointer back (not gaze)".

> Eye Metrics stay as in `report-summary.md`.

### C2 · Detailed Results

> Same page as `report-detailed.md`, switched with View Details. The selected-trial map shows the scene, the target button, the animating object's area and the gaze path during the trial, with the animation window drawn darker.

#### Trial-by-Trial Results

| Trial | Prompt | Side | Outcome | Chosen | Wrong choices | Reaction Time (s) | Looked back | Look-back latency (s) | Look-back time (s) | Valid (%) | Scene / Buttons / Else (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Balloons | Left | ● Right | Balloons | 0 | 1.80 | ● Yes | 0.38 | 1.90 | 97 | 30 / 62 / 8 |
| 2 | Bike | Right | ● Right | Bike | 1 | 3.40 | ● Yes | 0.51 | 1.20 | 94 | 45 / 48 / 7 |
| 3 | Rainbow | Left | ■ Modelled | — | 2 | 10.00 | ○ No | — | 0.00 | 88 | 55 / 30 / 15 |
| 4 | Swing | Right | ◌ Skipped | — | — | — | — | — | — | — | — |

> **Table rules:** as in `report-detailed.md` (first row selected, sortable, Trial frozen, skipped rows greyed). Outcome badges: ● Right (green), ■ Modelled (red, not chosen in time), ◌ Skipped. "Wrong choices" lists the wrong buttons in a tooltip (e.g. "Swing, Bike"). Looked back is always Yes / No (W4); the Valid (%) column beside it shows when gaze was lost. The usual eye columns (fixations, saccades, pupil) follow, as in `report-detailed.md`.

> **PDF:** the same tables in the same order; the Scene Map starts page 2, as the Target Map does today.
