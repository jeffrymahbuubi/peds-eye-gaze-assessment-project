![[_nav.md]]

## Scanning Search: run screens

> SPEC-scanning-search-cues.md. The task canvas during a Scanning Search trial (the nav bar above is only the wireframe's). Shapes: (O) circle, `[#]` square, /\ triangle, <> diamond, {H} hexagon, * star. Shown with 4 icons on the forest field. The run bar at the bottom is unchanged and left out here.

---

### Dwell feedback follows the shape (both modes, S1)

```text
     today (circle round a triangle)            new (traces the triangle)

            .-~~~~~~-.                                    /\
          /     /\     \                                 //\\
         |     /  \     |                               // /\ \\
         |    /____\    |                              // /  \ \\
          \            /                              // /____\ \\
            '-.____.-'                               //__________\\
                                                    progress runs along the
     dwell arc is a circle                          triangle's edge, clockwise
                                                    from the top
```

> The selectable outline (4 px, offset 4), the on-target ring (5 px, offset 10) and the dwell trace (8 px, offset 16) all follow the icon's own outline. The dwell trace starts at the top-most point and closes when the dwell completes, then the **sparkle burst** plays as today. A circle target looks exactly as before, so Static Click, Grid Click and Follow the Target do not change.

---

### Optional · Centre start dot (setting "Start each trial from the centre")

```text
+------------------------------------------------------------------------------+
|                                                                              |
|                                                                              |
|                                                                              |
|                                     .                                        |
|                                 small dot (1 deg)                            |
|                                                                              |
|                                                                              |
|                                                                              |
+------------------------------------------------------------------------------+
```

> Before each trial (and before the sample in Match the sample). When the gaze stays within 2 deg of the dot for 300 ms, the trial goes on; after 5 s it goes on anyway (recorded as a timeout). Off by default.

---

### Mode Pop-out (default, as today)

```text
+------------------------------------------------------------------------------+
|                                                                              |
|          ( faint O )                         ( faint [#] )                   |
|                                                                              |
|                                                                              |
|          ( faint * )                         ( RED /\ )  <- the target       |
|                                                                              |
|                                                                              |
+------------------------------------------------------------------------------+
```

> The target is the only icon in colour; the others are faint. Unchanged except the shape-following feedback.

---

### Mode Match the sample · 1 Sample phase

```text
+------------------------------------------------------------------------------+
|                                                                              |
|                                                                              |
|                                   /\                                         |
|                                  /  \      the target's shape, alone,        |
|                                 /____\     at the icon size, target colour   |
|                                                                              |
|                               Find this!                                     |
|                                                                              |
|                     (voice: "Find the triangle!")                            |
+------------------------------------------------------------------------------+
```

> Lasts 1.5 s or the length of the spoken prompt, whichever is longer. Nothing can be selected yet; the trial clock has not started.

### Mode Match the sample · 2 Search phase

```text
+------------------------------------------------------------------------------+
|                                                                              |
|                                                                              |
|          ( RED * )                           ( RED O )                       |
|                                                                              |
|                                                                              |
|          ( RED /\ )                          ( RED <> )                      |
|                                                                              |
+------------------------------------------------------------------------------+
```

> Every icon is drawn bright in the target colour, so only the shape tells them apart. The shapes are reshuffled every trial and the target's shape appears once. Nothing else is drawn. Only with the setting "Show the shape while searching" on (off by default; S9, 2026-10-14) does a half-size copy of the shape stay at top centre (top-left if a slot would overlap it). No outline marks the target until the gaze is on it; then the on-target ring and the dwell trace follow its shape. The trial clock and the timeout start when the field appears. A hit plays the sparkle burst and the hit sound as today.
