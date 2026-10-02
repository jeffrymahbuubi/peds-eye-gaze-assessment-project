---
name: SPEC-hud-hide-toggle
title: Hide the operator HUD during a task (canvas expands)
status: design + wireframe approved by the user; not implemented
created: 2026-10-02
last_updated: 2026-10-02
next_step: spec-implementer implements §4–§6 (§7 step 3)
related:
  - SPEC-diki-design-audit.md (§8.10: OperatorPanel = HUD cards in its own side column; canvas-overlay approach rejected §8.9)
  - SPEC-live-settings-panel.md (§10.3 per-sitting carry pattern in DashboardWindow)
  - SPEC-display-standard-check.md (done, 9412a03; touched the same files)
---

# SPEC-hud-hide-toggle — hide the operator HUD during a task

**Status: design approved by the user 2026-10-02 (§2, plus the hub-chosen H key and §4.4 recording); wireframe approved (`docs/wireframes/run.md`); not implemented.**
The doctor can hide the operator side column (the HUD) at any time during a
task, so it does not distract the child, and bring it back the same way. When
hidden, the task canvas expands into the freed space.

**Created:** 2026-10-02
**Last updated:** 2026-10-02

## 1. Origin / what was asked

User, 2026-10-02, relaying doctor feedback: the HUD shown during a task may
distract the child. Request: be able to hide the HUD whenever the
doctor/user wants.

## 2. Decisions (chosen by the user 2026-10-02)

- **H1 — What hides: the operator side column only** (`OperatorPanel`: the
  Status/Live, Controls, Settings/Pacing and Settings-profile cards). The
  dashboard's top nav bar, the gaze cursor and the window title bar are NOT
  affected.
- **H2 — Canvas expands** into the freed 280 px column. (Rejected: keeping
  the canvas size fixed with a blank column.)
- **H3 — Toggle: key + button.** A "Hide HUD" button in the Controls card,
  plus a keyboard key that toggles both ways. Once hidden, the key is the
  only way back.
- **H4 — Remember for the sitting.** Every app launch starts shown. If the
  doctor hides it, later tasks in the same sitting start hidden too.
- **H5 — Takes effect immediately**, even mid-trial. The user accepted the
  consequence: because target positions are stored as canvas fractions and
  radii in px, a ~280 px widening moves an on-screen target (a centred
  target shifts ~140 px right), possibly while the child is fixating it.

Hub-chosen details (mechanical; the user may override at review): the key
(**H**), the button label, the recording fields/events in §4.4.

## 3. Current code (as of `9412a03`)

- `TaskRunView` (`src/ui/main_window.py:23`) = `QHBoxLayout`: `TaskCanvas`
  (stretch 1) + `OperatorPanel` (`setFixedWidth(280)`). Hiding the panel
  widget lets the canvas take the width with no layout code. `TaskRunView`
  is shared by the dashboard run and the standalone `--task X --gui`
  `MainWindow`.
- `OperatorPanel` (`src/ui/operator_panel.py:157`): Controls card has
  Pause / Skip trial / End task (`pause_toggled`, `skip_requested`,
  `end_requested` signals). Add the new button and signal here.
- Keys: `AssessmentApp._install_key_handler()` (`src/app.py:~485`)
  monkey-patches `canvas.keyPressEvent`: Space/Return/Enter = switch press,
  Esc = `_shutdown()`. It only works while the canvas has focus, and
  clicking a panel button moves focus off the canvas.
- Resize safety: `AssessmentApp._tick()` calls
  `task.set_screen_size(canvas.width(), canvas.height())` and
  `_sync_gaze_geometry()` **every tick** (`app.py:674-675`), so hit-testing
  and the gaze cursor follow a resize with no new code. `_record_geometry()`
  runs once on the first tick, so its `canvas_*` values describe the
  canvas **at task start** only.
- Per-sitting state: `DashboardWindow` already keeps in-memory per-sitting
  state (`_task_live_overrides`, `dashboard_window.py:~91`) and builds
  `AssessmentApp(...)` at `~394`. Follow that pattern.
- Recorder: `record_event(kind, t_ns, **payload)` → events stream;
  `log(message)` → session log (`src/data/recorder.py:140/149`).

## 4. Design

### 4.1 Hide/show mechanism

- `TaskRunView.set_hud_hidden(hidden: bool)` → `operator_panel.setVisible(not hidden)`;
  `hud_hidden` property; a `hud_hidden_changed = Signal(bool)`.
- After any toggle, give focus back to the canvas (`canvas.setFocus()`), so
  Space and Esc keep working, especially once the button that had focus is
  hidden.

### 4.2 Toggle controls (H3)

- **Button:** "Hide HUD" in the Controls card, below End task; emits a new
  `OperatorPanel.hide_requested` signal. Tooltip: "Press H to show it
  again." (The button is only ever seen while shown, so its label is fixed.)
- **Key H:** a `QShortcut(QKeySequence(Qt.Key_H), task_run_view)` with
  `Qt.WidgetWithChildrenShortcut` context, so it works whether focus is on
  the canvas or on a panel control. Do NOT add it to the canvas
  `keyPressEvent` patch (focus-dependent). Check H isn't already bound
  anywhere (`grep` for `Key_H` / shortcuts) before using it.
- While hidden, Pause/Skip/End are unreachable by mouse; Esc (end) and
  Space (switch) still work. This is accepted, not mitigated.

### 4.3 Sitting memory (H4)

- `DashboardWindow._hud_hidden: bool = False` (in-memory, never persisted to
  `local_state.json` or settings profiles).
- Pass it as a new `AssessmentApp(..., hud_hidden: bool = False)` kwarg,
  which applies it to `TaskRunView` before the first tick.
- Keep `_hud_hidden` in sync as the doctor toggles (connect to
  `hud_hidden_changed`), so the next run starts in the latest state, even if
  the run ended while hidden.
- Standalone `--task X --gui` always starts shown.

### 4.4 Recording (hub-chosen)

The canvas size can now change mid-run, so the record must say when:

- **On each toggle:** `record_event("HUD_TOGGLED", t_ns, hidden=<bool>, trial=<index or None>)`
  and one session-log line, e.g. `HUD hidden by operator (trial 4).` /
  `HUD shown by operator (trial 4).`
- **On any canvas size change** detected in `_tick` (compare to the last
  size seen; the first tick only sets the baseline):
  `record_event("CANVAS_RESIZED", t_ns, canvas_w=<int>, canvas_h=<int>)` and
  a log line `Canvas resized to 1920x1003.` Detect it in `_tick`, not in the
  toggle handler, because the new size only exists after Qt's layout pass.
  Same units as `_record_geometry()`'s `canvas_*` (do not change those
  units; see the export-parity SPEC §10).
- **`SessionMetadata`** (additive, no `schema_version` bump, same as the
  geometry block): `hud_hidden_at_start: bool | None` and
  `hud_toggle_count: int = 0`. Document in the field comment that `canvas_*`
  is the size at the first tick.

## 5. Scope

In: `src/ui/main_window.py`, `src/ui/operator_panel.py`,
`src/ui/dashboard_window.py`, `src/app.py`, `src/data/schema.py`, new tests,
and the wireframe (§7 step 1, hub).

Out (do NOT change):
- The top nav bar, gaze cursor, title bar / full-screen behaviour (H1).
- Target placement maths: no rescaling or freezing of targets on resize
  (H5 accepts the jump).
- Per-trial canvas-size columns in `trials.csv` (the `CANVAS_RESIZED`
  events are enough to rebuild px positions afterwards).
- `configs/default.yaml`, `local_state.json`, settings profiles, the Results page.

## 6. Acceptance criteria

1. The button and the H key both hide the panel; H shows it again. H works
   with focus on the canvas and with focus on a panel control. After a
   toggle, the canvas has focus (Space/Esc still work).
2. Hidden → canvas width grows by the panel width (280 px logical); shown →
   back to before. Hit-testing uses the new size on the next tick (existing
   per-tick `set_screen_size`).
3. Sitting memory: in `DashboardWindow`, a second run starts hidden if the
   HUD was hidden when the first ended; a fresh `DashboardWindow` starts
   shown; nothing is written to `local_state.json` or profiles.
4. Recording: each toggle → exactly one `HUD_TOGGLED` event and one log
   line; each real canvas size change → one `CANVAS_RESIZED` event (none
   when the size is unchanged); `metadata.json` has `hud_hidden_at_start`
   and `hud_toggle_count`; the standalone path gives
   `hud_hidden_at_start = False`.
5. Full pytest: the suite at that time plus the new tests pass, with only the
   known local-config failure `test_config_merges_task_over_default`.

## 7. Plan

1. **DONE 2026-10-02 — Wireframe (hub, mandatory first):** `docs/wireframes/run.md`/`.html`; the run view, shown vs hidden
   (Controls card with "Hide HUD"; full-width canvas). The user takes a look.
2. **DONE 2026-10-02 —** Commit this SPEC + wireframe (hub). (The display-check prerequisite is
   met: `9412a03`.)
3. Implement (spec-implementer, Sonnet 5.5): §4–§6, pytest, §8 Impl log;
   ambiguities go to §9. No commit.
4. Review (hub): diff + Impl log vs §6, rerun pytest.
5. Live check (hub + user, qt-mcp, maximized, real GP3HD): hide mid-trial
   with the button, show with H, hide with H; confirm the cursor stays on
   gaze and hits still register after the resize; run a second task in the
   same sitting and confirm it starts hidden; check events/log/metadata.
6. Commit, push, update memory.

## 8. Impl log

(Implementer appends dated entries here.)

## 9. Implementer open questions

(Implementer appends here, then stops and returns.)

## 10. Log

- **2026-10-02 — SPEC drafted.** User relayed doctor feedback that the
  in-task HUD may distract the child. Five questions answered: hide the side
  column only (H1), canvas expands (H2), key + button (H3), remember for the
  sitting (H4), takes effect immediately even mid-trial, accepting that the
  target can move (H5). The hub checked that hit-testing and the gaze mapping
  already re-sync every tick, so the resize is safe for scoring. The hub
  added `HUD_TOGGLED`/`CANVAS_RESIZED` recording because `_record_geometry()`
  only captures the start-of-run size.

- **2026-10-02, later — approved as written.** The user approved the SPEC
  as drafted, including the hub-chosen H key, the button label and the §4.4
  recording (`HUD_TOGGLED`/`CANVAS_RESIZED` events,
  `hud_hidden_at_start`/`hud_toggle_count`). Wireframe first (§7 step 1):
  the user looks at it, then the spec-implementer runs in the same session.
  The display-check prerequisite is met (`9412a03`).

- **2026-10-02, later — wireframe approved.** The hub drew the run view in
  `docs/wireframes/run.md` (+ rendered `run.html`): state A (HUD shown,
  "Hide HUD" under End task in the Controls card) and state B (HUD hidden,
  full-width canvas, nothing drawn in its place), as scaled block diagrams
  plus the §4 behaviour notes. The user approved it as drawn ("approved, go
  ahead"). Plan steps 1–2 done; next is step 3 (spec-implementer).
