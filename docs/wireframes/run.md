![[_nav.md]]

## Task run view — HUD shown vs hidden

> SPEC-hud-hide-toggle.md. The doctor can hide the operator side column (the HUD) at any time during a task so it does not distract the child. Only the side column hides: the top nav bar, the gaze cursor and the title bar stay as they are.

---

### A · HUD shown (every app launch starts here)

```
+-------------------------------------------------------------------------------------+
| Setup | Tasks | Results                          (nav bar - unchanged)              |
+--------------------------------------------------------------+----------------------+
|                                                              | STATUS               |
|                                                              |  FPS 60 · 150 Hz     |
|                                                              | LIVE                 |
|                    TASK CANVAS (stretch)                     |  Trial 4/10 · Hits 3 |
|                                                              +----------------------+
|                          ( target )                          | CONTROLS             |
|                                                              |  [ Pause          ]  |
|                            o  gaze cursor                    |  [ Skip trial     ]  |
|                                                              |  [ End task       ]  |
|                                                              |  [ Hide HUD       ]  |  <- NEW
|                                                              +----------------------+
|                                                              | SETTINGS / PACING    |
|                                                              | SETTINGS PROFILE     |
|        width = window - 280 px                               |   280 px (fixed)     |
+--------------------------------------------------------------+----------------------+
```

#### Controls card (new button)

[Pause] [Skip trial] [End task]{variant:danger} [Hide HUD]

> **New:** "Hide HUD", below End task, same style as Pause / Skip. Tooltip: "Press H to show it again." The label never changes (the button is only seen while the HUD is shown).

---

### B · HUD hidden (after "Hide HUD" or the H key)

```
+-------------------------------------------------------------------------------------+
| Setup | Tasks | Results                          (nav bar - unchanged)              |
+-------------------------------------------------------------------------------------+
|                                                                                     |
|                                                                                     |
|                                                                                     |
|                         TASK CANVAS - full width                                    |
|                                                                                     |
|                                   ( target )   <- moved ~140 px right (H5)          |
|                                                                                     |
|                                     o  gaze cursor                                  |
|                                                                                     |
|                                                                                     |
|                                                                                     |
|        width = window (grows by 280 px)      no button, no hint drawn               |
+-------------------------------------------------------------------------------------+
```

> **Show again:** press **H** (the only way back once hidden). H also hides it. H works whether focus is on the canvas or on a panel control.
>
> **Still works while hidden:** Space / Enter (switch press) and Esc (end task). Pause / Skip are mouse-unreachable while hidden (accepted).
>
> **Takes effect immediately, even mid-trial.** Targets are stored as canvas fractions, so an on-screen target moves when the canvas widens (a centred target shifts ~140 px right). Hit-testing and the gaze cursor follow the new size on the next tick.
>
> **Remembered for the sitting:** if the HUD is hidden when a task ends, the next task in the same dashboard sitting starts hidden. A new app launch starts shown. Never saved to disk settings or profiles.
>
> **Recorded:** each toggle → `HUD_TOGGLED` event + log line ("HUD hidden by operator (trial 4)."); each canvas size change → `CANVAS_RESIZED` event + log line ("Canvas resized to 1920x1003."); metadata gets `hud_hidden_at_start` and `hud_toggle_count`.
