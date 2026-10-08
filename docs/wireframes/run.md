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
| Trial 4 of 18   (● Tracking OK)         [ Pause (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
+--------------------------------------------------------------------------------------+
   page-grey bar, 48 px, 16 px text; buttons 36 px with a grey border
```

Trial 4 of 18   |● Tracking OK|{.success}

> **Design system phases 1-2** (SPEC-design-system-phase1.md H9, phase2.md H8): the status is separate parts, no interpunct: "Trial 4 of 18", then (Mouse tests) "Mouse pointer", then the tracking state as a status badge with glyph + word: ● Tracking OK (green), ▲ No gaze for 3 s (amber), ■ Tracker disconnected (red). Full screen during a run (no OS title bar or taskbar) comes in phase 3.

[Pause (Alt-P)] [Skip trial] [Quit (Alt-Q)]

> **Status line, one line, updated every frame:**
> - ● Tracking OK: green badge.
> - ▲ No gaze for 3 s: amber badge. Shown only after 1 s without valid gaze, because single blink or saccade frames are normal. Before the first valid sample it reads "Waiting for gaze".
> - ■ Tracker disconnected: red badge.

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
| Paused   Trial 4 of 18                  [ Resume (Alt-P) ]  [ Skip trial ]  [ Quit (Alt-Q) ] |
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
| [PRACTICE]  Trial 2 of 3  (● Tracking OK)  [ Pause (Alt-P) ] [ Skip trial ] [ Quit (Alt-Q) ] |
+--------------------------------------------------------------------------------------+
   bar background pale amber (#FCF4D6); PRACTICE is a filled yellow chip (#F1C21B, ink text)
```

|PRACTICE|{.warning}   Trial 2 of 3   |● Tracking OK|{.success}

> The chip itself says "not recorded", so the words are gone.

> **Practice:**
> - Practice runs 3 trials and writes nothing.
> - Quit or Esc goes straight back to the Start page, with no dialog.
> - At its end the Start page shows "Practice finished: 3 of 3 selected."

---

### D · Preview (from the configuration page)

|PREVIEW|{.warning}   Trial 2 of 3   Mouse pointer

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
| Trial counter, hits/timeouts tally, progress bar | "Trial i of N" only (no score shown to the room) |
| Pause / Skip trial / End task | Pause (Alt-P) / Skip trial / Quit (Alt-Q) |
| Hide HUD button, H key | removed (nothing to hide) |
| 11 live sliders and check boxes | moved to the configuration page; nothing changes during a run |
| Settings profile card (save / reset) | replaced by named configurations on the configuration page |

> Esc during a recorded run = Quit with confirmation (user answer (d), 2026-10-06). It no longer ends the run at once. The dialogs are in `run-end.md`.
