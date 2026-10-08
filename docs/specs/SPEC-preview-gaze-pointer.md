---
name: SPEC-preview-gaze-pointer
title: Preview follows the test's Input (real gaze when the tracker is ready); no gaze smoothing on a Mouse pointer
status: approved 2026-10-08 (user decisions P1-P3; hub decisions H1-H9 approved by the user)
created: 2026-10-08
last_updated: 2026-10-08
next_step: /spec-run after SPEC-design-system-phase2 is merged (both touch the configuration page and settings_registry)
related:
  - SPEC-compass-task-flow.md (U6, 4B.6 Preview Test: mouse-driven; this SPEC revises U6 for gaze tests)
  - SPEC-input-selection-and-follow.md (4.2 "Preview's pointer is always the mouse"; H4/H5 Mouse runs; revised here)
  - SPEC-design-system-phase2.md (reorders the configuration cards, H6; land it first)
---

# SPEC-preview-gaze-pointer: Preview with the test's own pointer

## 1. Origin

During testing on 2026-10-08 the user set a test's Input to **Gaze** on the configuration page,
pressed **Preview Test**, and the pointer was the mouse. This is the approved design
(SPEC-compass-task-flow U6; SPEC-input-selection-and-follow 4.2), not a bug. The user's intention
for Configure + Preview: *"let the therapist see how the configuration affects the testing
environment before running a real test."* With Input = Gaze, the gaze-related settings (Gaze
Smoothing and the rest) must be active in Preview; with Input = Mouse they need not be.

## 2. Current code (main `6d2b2cb`)

- `src/ui/config_flow.py` `_on_preview` (~line 237): always builds a `MouseGazeSource` and passes it
  as `client`; no calibration is passed; `run_mode="preview"`, at most 3 trials, `NullRecorder`.
- `src/app.py:313`: `self._pointer_is_mouse = self.input_choice.is_mouse or self.run_mode == PREVIEW`.
- `src/app.py:381`: a run with no preset calibration whose pointer is not the mouse **starts a fresh
  calibration**. A gaze Preview must never reach that branch.
- `src/app.py:426-440`: `EyeInput` smooths whichever pointer is active with
  `dwell.smoothing.enabled/alpha`, so today the **mouse is smoothed** in Preview (both Inputs) and in
  recorded/Practice Mouse runs.
- `src/ui/settings_registry.py` `_GREYED_BY` (~line 429): greys Dwell / progress ring / glow by
  `input.selection`; nothing is greyed by `input.pointer`, so the Gaze Smoothing card stays active
  for Mouse.
- `src/ui/run_flow.py` `_build` (~line 195): how Practice and recorded runs get the Setup tab's
  `client` and `calibration_result` (`setup.client`, `setup.calibration_result`,
  `setup.tracker_ready()` in `setup_page.py`).
- Run bar wording: `run_status_line(..., preview=True)` in `src/engine/tracking_status.py` gives
  `PREVIEW · Trial i/N · mouse pointer · nothing is recorded`.

## 3. Decisions

### 3.1 User decisions (2026-10-08)

| # | Decision |
|---|---|
| P1 | Preview of a test whose Input pointer = **Gaze**: use the **real tracker gaze when the tracker is connected and calibrated**; otherwise fall back to the mouse (with the gaze settings applied, as today), and the run bar says which. |
| P2 | Input pointer = **Mouse**: Gaze Smoothing is **off in every Mouse run** (Preview, Practice, recorded), and the Gaze Smoothing card is **greyed** on the configuration page while Input = Mouse. |
| P3 | Preview's purpose is to show the therapist how the configuration shapes the test environment before a real test. |

### 3.2 Hub decisions (approved by the user 2026-10-08)

- **H1 Which pointer.** Decided at Preview launch from the **unsaved form's** `input.pointer`
  (the values Preview already runs) and `setup.tracker_ready()`:
  Gaze + (connected, calibrated) = real gaze; Gaze + not ready = mouse fallback; Mouse = mouse.
  No change mid-run: if the tracker drops during a gaze Preview, the run bar shows the usual
  "no gaze" / "tracker disconnected" state, as in Practice.
- **H2 Real-gaze Preview wiring.** `_on_preview` passes the Setup tab's `client` and its
  `calibration_result` as `preset_calibration_result` (as `run_flow._build` does), so the
  `app.py:381` fresh-calibration branch is **never** reached from Preview. The Preview still
  records nothing (`NullRecorder`, `_gaze_recorded` stays False for PREVIEW), never dials the
  device, never starts streaming changes the Setup tab does not already allow.
- **H3 `app.py` rule.** The forced-mouse rule becomes explicit: `AssessmentApp` gets a
  `preview_pointer: "gaze" | "mouse" | None` (or the caller's equivalent) instead of
  `run_mode == PREVIEW` forcing the mouse. The mouse fallback keeps today's `MouseGazeSource`
  path exactly.
- **H4 Run bar wording** (`run_status_line`, preview): real gaze =
  `PREVIEW · Trial i/N · gaze pointer · nothing is recorded`; Gaze test on fallback =
  `PREVIEW · Trial i/N · mouse pointer (tracker not ready) · nothing is recorded`; Mouse test =
  today's `... · mouse pointer · ...`.
- **H5 Gaze + Switch Preview with real gaze**: the OS cursor is parked and hidden as in a recorded
  Gaze + Switch run (`_hide_cursor`, I6); Space / Enter / left click select.
- **H6 Smoothing off for a Mouse pointer (P2).** `EyeInput`'s `SmoothingConfig.enabled` is False
  whenever the **test's** pointer is Mouse (any run mode). A Gaze test on the mouse fallback in
  Preview keeps smoothing on (that is P1's "gaze settings applied"). `metadata.settings` keeps the
  configured values unchanged (they are the test's configuration); `session.log` of a recorded or
  Practice Mouse run gets one line `Gaze smoothing: off (mouse pointer).`
- **H7 Config page greying (P2).** `dwell.smoothing.enabled` and `dwell.smoothing.alpha` are greyed
  in place (never hidden, 4B.3) while `input.pointer` = Mouse. Alpha is greyed if **either** its
  `depends_on` check is off **or** the pointer is Mouse; the implementer makes the two rules
  combine rather than overwrite each other. Values are kept, not reset.
- **H8 No other change.** Preview still runs at most 3 trials, unsaved values, returns to the page
  exactly as it was; Practice and recorded runs are unchanged except H6. No new gate.
- **H9 Tests.** Preview pointer choice for the three cases (Gaze ready / Gaze not ready / Mouse),
  that a gaze Preview passes the Setup calibration and never calls the calibration routine, run bar
  wording of H4, smoothing disabled for a Mouse pointer in record / practice / preview and enabled
  for a Gaze test's mouse fallback, the greying of H7 incl. the alpha double rule, the session.log
  line. Existing tests updated, never deleted.

## 4. Design

No layout change. The only visible differences: the run bar wording of H4 and the Gaze Smoothing
card greyed for Mouse (same greyed style as the existing `greyed_by` controls). No wireframe gate.

## 5. Scope

**In:** H1-H9; `config_flow.py` (Preview launch), `app.py` (pointer rule, smoothing), `tracking_status.py`
(wording), `settings_registry.py` (greying), tests.
**Out:** recording anything from a Preview; Preview trial count or timing; changing Practice;
report changes; any design-system phase work.

## 6. Acceptance criteria

- **A1** Input = Gaze, tracker connected + calibrated: Preview's pointer is the real gaze; the bar
  says `gaze pointer`; Gaze Smoothing visibly applies; nothing is written under `sessions/`.
- **A2** Input = Gaze, tracker not connected or not calibrated: Preview runs on the mouse with
  smoothing on; the bar says `mouse pointer (tracker not ready)`; no calibration starts.
- **A3** Input = Mouse: Preview, Practice and recorded runs use the raw mouse (no smoothing); the
  Gaze Smoothing card is greyed while Input = Mouse and active again on Gaze, with values kept.
- **A4** A gaze Preview never starts a calibration and never changes the Setup tab's connection
  or calibration state.
- **A5** Full pytest green (except the known skip-worktree alpha checks); live check passes (§7).

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | SPEC approved by the user (DONE 2026-10-08) | user |
| 1 | spec-implementer in a worktree based on the merged design-system phase 2: H1-H9 | — |
| 2 | Hub review + full pytest; §9 questions | — |
| 3 | Live check: A2/A3 and the wiring of A1 with `tools/fake_gazepoint_server.py` (connected + calibrated); the real feel of A1 with the GP3 HD and the user as subject (optional, user's call) | user |
| 4 | Commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-08** — Drafted by the hub after the user reported that Preview with Input = Gaze used
  the mouse (by design, U6 / input-selection 4.2). User decisions P1 (real gaze if ready, else mouse
  with gaze settings), P2 (no smoothing for any Mouse run; grey the card), P3 (purpose). Found while
  drafting: the mouse is smoothed today in every run; a gaze run without a preset calibration
  starts a fresh one (`app.py:381`), so H2 passes the Setup calibration. Hub H1-H9 await approval.
  Queued after design-system phase 2 (shared files: settings_registry, configuration page).
- **2026-10-08** — The user approved H1-H9 as written. SPEC committed on `feature/compass-task-flow`. Next: /spec-run this SPEC after design-system phase 2 is merged.
