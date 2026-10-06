![[_nav.md]]

## Task run screen — no HUD

> SPEC-compass-task-flow.md 4C.5–4C.7 (U5). Rewritten: the HUD side column (`OperatorPanel`), its live sliders and Hide HUD are removed. During a run, only a thin bottom bar remains. While Practice or a recorded run is showing, the dashboard title bar and nav are hidden, so the canvas fills the window above the bar. The child sees only the canvas. This supersedes SPEC-hud-hide-toggle.md.

---

### A · Recorded run

```
+--------------------------------------------------------------------------------------+
|                                                                                      |
|                                                                                      |
|                                                                                      |
|                          TASK CANVAS (stretch, whole window)                         |
|                                                                                      |
|                                   ( target )                                         |
|                                                                                      |
|                                      o  gaze cursor (if on in the configuration)     |
|                                                                                      |
|                                                                                      |
+--------------------------------------------------------------------------------------+
| Trial 4/18 · tracking OK                [ Pause (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
+--------------------------------------------------------------------------------------+
   light grey bar, about 44 px, status on the left, buttons centred
```

Trial 4/18 · |tracking OK|{.success}

[Pause (Alt-P)] [Skip trial] [Quit (Alt-Q)]

> **Status line, one line, updated every frame:**
> - "tracking OK": green.
> - "no gaze for 3 s": amber. Shown only after 1 s without valid gaze, because single blink or saccade frames are normal. Before the first valid sample it reads "waiting for gaze".
> - "tracker DISCONNECTED": red.

> **Bar buttons:**
> - Skip trial is enabled only while a target is waiting, not between trials and not while paused.
> - Alt-P and Alt-Q work from anywhere in the run screen.
> - After any click, focus goes back to the canvas, so Space (switch) keeps working.

---

### B · Paused

```
+--------------------------------------------------------------------------------------+
|                                                                                      |
|                                                                                      |
|                                       Paused                                         |
|                          (no target, no gaze cursor)                                 |
|                                                                                      |
|                                                                                      |
+--------------------------------------------------------------------------------------+
| Paused · Trial 4/18                     [ Resume (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
+--------------------------------------------------------------------------------------+
```

> **Pause:**
> - The clock stops.
> - A trial interrupted by the pause is not recorded. On Resume the same target is shown again with a fresh clock, so a long pause never causes a timeout.
> - Pause time is not counted in the valid-gaze share.

---

### C · Practice (amber bar)

```
+--------------------------------------------------------------------------------------+
|                          TASK CANVAS (same as a recorded run)                        |
+--------------------------------------------------------------------------------------+
| PRACTICE (not recorded) · Trial 2/3 · tracking OK   [ Pause (Alt-P) ] [ Skip trial ] [ Quit (Alt-Q) ] |
+--------------------------------------------------------------------------------------+
   bar background amber
```

|PRACTICE (not recorded)|{.warning} · Trial 2/3 · |tracking OK|{.success}

> **Practice:**
> - Practice runs 3 trials and writes nothing.
> - Quit or Esc goes straight back to the Start page, with no dialog.
> - At its end the Start page shows "Practice finished: 3 of 3 selected."

---

### D · Preview (from the configuration page)

PREVIEW · Trial 2/3 · mouse pointer · nothing is recorded

> **Preview:**
> - The mouse drives the gaze.
> - The bar always shows, so a Preview can never be mistaken for a recorded run.
> - Quit needs no confirmation.
> - See `task-config.md`.

---

### What happened to each HUD item

| HUD item (before) | Now |
|---|---|
| FPS / device Hz | removed (the sample rate is still computed from the raw file) |
| Gaze validity | the tracking state in the status line |
| Trial counter, hits/timeouts tally, progress bar | "Trial i/N" only (no score shown to the room) |
| Pause / Skip trial / End task | Pause (Alt-P) / Skip trial / Quit (Alt-Q) |
| Hide HUD button, H key | removed (nothing to hide) |
| 11 live sliders and check boxes | moved to the configuration page; nothing changes during a run |
| Settings profile card (save / reset) | replaced by named configurations on the configuration page |

> Esc during a recorded run = Quit with confirmation (user answer (d), 2026-10-06). It no longer ends the run at once. The dialogs are in `run-end.md`.
