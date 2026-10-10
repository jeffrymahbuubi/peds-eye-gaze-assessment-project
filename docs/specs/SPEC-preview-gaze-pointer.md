---
name: SPEC-preview-gaze-pointer
title: Preview follows the test's Input (real gaze when the tracker is ready); no gaze smoothing on a Mouse pointer
status: implemented + live-checked (fake tracker) 2026-10-09 on branch preview-gaze-pointer (NOT merged)
created: 2026-10-08
last_updated: 2026-10-08
next_step: user merges design-phase2, audit-fixes, preview-gaze-pointer (in that order) and pushes; optional real-gaze feel of A1 with the GP3 HD
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
| 1 | spec-implementer in a worktree based on the merged design-system phase 2: H1-H9 (DONE 2026-10-09, worktree from audit-fixes d023556) | — |
| 2 | Hub review + full pytest; §9 questions (DONE 2026-10-09; §9 empty; one hub fix round) | — |
| 3 | Live check: A2/A3 and the wiring of A1 with `tools/fake_gazepoint_server.py` (connected + calibrated); the real feel of A1 with the GP3 HD and the user as subject (optional, user's call) (fake-tracker part DONE 2026-10-09, unattended run authorized by the user; GP3 HD feel still open) | user |
| 4 | Commit on the user's OK (DONE 2026-10-09: committed on side branch preview-gaze-pointer only, per the unattended-run authorization; no merge, no push) | user |

## 8. Impl log

- **2026-10-09** — Implemented H1-H9 in the worktree `preview-gaze-pointer` (based on `d023556`).
  Model: `claude-sonnet-5-5`. Nothing committed or staged; `configs/default.yaml` and
  `configs/local_state.json` untouched.
  - **Files changed:** `src/app.py` (new `preview_pointer` argument; pointer rule; H2 guard;
    smoothing off for a Mouse test; the session.log line; run bar flags), `src/ui/config_flow.py`
    (`_on_preview` decides from the unsaved form's `input.pointer` + `setup.tracker_ready()`),
    `src/engine/tracking_status.py` (`run_status`, new `tracker_not_ready` flag; the preview
    wording), `src/ui/settings_registry.py` (`_GREYED_BY` gets both smoothing controls),
    `src/ui/task_config_page.py` (`_refresh` now collects what any rule greys and sets each
    widget once, so the alpha is greyed if either its check box is off or the Pointer is Mouse),
    `src/ui/config_form.py` (comment only).
  - **Behaviour:** Gaze form + `tracker_ready()` both true: `client=setup.client`,
    `preset_calibration_result` / `_source` / `_file` from Setup, `preview_pointer="gaze"` (the
    `Calibration` branch and `GazepointClient` are never reached; `_gaze_recorded` stays False;
    NullRecorder). Any other case: `MouseGazeSource` bound to the canvas as before,
    `preview_pointer="mouse"` (a Mouse test never calls `tracker_ready()`, so the Setup client is
    not touched at all). `AssessmentApp` raises `ValueError` for a gaze Preview given no client or
    no calibration (H2 enforced, not just conventional) and for an unknown `preview_pointer`.
    Smoothing: `SmoothingConfig.enabled = configured and not input_choice.is_mouse` (the test's
    pointer, so a Gaze test on the fallback keeps it); `metadata.settings` unchanged; one
    `Gaze smoothing: off (mouse pointer).` line for a run whose test pointer is Mouse (it reaches
    session.log for a recorded run; a Practice or Preview NullRecorder discards it).
  - **Tests added:** new `tests/test_preview_gaze_pointer.py` (38 tests: wording through the app,
    pointer rule and H2 guards, Gaze+Switch cursor, smoothing off/on per run mode incl. a raw-vs-
    smoothed jump, session.log line, page greying incl. the alpha 2x2 matrix and values kept,
    Preview from the configuration page for ready / not connected / not calibrated / no tracker /
    Mouse test / unsaved-pointer-decides / Switch / cannot-start); `tests/test_tracking_status.py`
    +2; `tests/test_copy_rules.py` +1 parametrised case.
  - **Existing tests updated (none deleted):** `test_config_preview.py::
    test_preview_never_touches_the_setup_pages_client` (now a Mouse test, as a ready tracker means
    a gaze preview), `test_run_flow_app.py::test_a_preview_names_the_mouse_and_its_chip_says_
    nothing_is_recorded` (now a Mouse test), `test_input_settings.py::test_the_greying_rules_of_4_1`
    (smoothing entries; alpha is the one control with both rules) and `test_pointer_mouse_greys_
    nothing` (renamed `test_pointer_mouse_greys_only_the_two_smoothing_controls`).
  - **pytest** (`-p no:cacheprovider -o addopts="" -q -rfE`): `5 failed, 3116 passed, 2 skipped in
    549.21s`. The 5 failures are the known alpha 0.22 vs 0.35 ones
    (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults` and the 4
    `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[...]`). Two
    mutation checks (smoothing rule removed; alpha check-box rule removed) each fail the new tests.
  - **Deviations:**
    1. **H4 wording adapted to the current format.** §2 names `run_status_line` and the old
       `PREVIEW · Trial i/N · mouse pointer · nothing is recorded` line; the code (design-system
       phase 1 H9) is `run_status` with comma-separated facts and the chip meaning "nothing is
       recorded". The three cases are therefore `PREVIEW, Trial i of N, Gaze pointer, <tracking>`,
       `PREVIEW, Trial i of N, Mouse pointer (tracker not ready)` and `PREVIEW, Trial i of N,
       Mouse pointer`. The real-gaze one keeps the tracker's state text/colour (H1: "no gaze" /
       "tracker disconnected" as in Practice). `PREVIEW, Paused` is unchanged.
    2. `preview_pointer=None` in a Preview means the mouse (what every earlier caller and test
       relied on); the SPEC left that default open.
    3. Touched `task_config_page.py` and `config_form.py`, not in the §5 file list: the alpha
       double rule (H7) can only be combined where `_refresh` runs.
    4. `src/engine/run_mode.py`'s module docstring still calls a preview "the mouse-driven look at
       a configuration" (out of scope, left as is).
  - **Notes for review:** a gaze Preview calls `start_streaming()` (idempotent) on the Setup client
    and, while paused, `drain_raw()`, exactly as a Practice does; it does not call `clear_raw()` or
    `stop()`. While running unpaused it does not drain the client's raw queue (a bounded deque, and
    the next recorded run clears it at its start). The live check (§7 step 3) is not done.
  - **Left undone:** the live check with `tools/fake_gazepoint_server.py` and the GP3 HD.
- **2026-10-09 (second pass)** — Hub review fix: a gaze Preview while a Setup thread is busy.
  Model: `claude-sonnet-5-5`. SPEC-audit-fixes H1 locks Setup while a Connect, Test Connection,
  Re-check or Do Calibration thread owns the device socket, but the Config page stays reachable and
  `tracker_ready()` can still say (True, True) from an earlier calibration.
  - **Files changed:** `src/ui/setup_page.py` (new public `SetupPage.device_busy()`, a one-line
    wrapper over `_busy()`; `_busy` itself and its call sites are untouched, so no rename churn
    for the parallel branches), `src/ui/config_flow.py` (`_on_preview` treats a busy Setup as
    "tracker not ready": `tracker_ready()` is not even asked, so the client is not read; the
    Preview falls back to the mouse with the `(tracker not ready)` wording; module docstring),
    `tests/test_preview_gaze_pointer.py`.
  - **Tests added (6, in `test_preview_gaze_pointer.py`):** `device_busy()` is False idle and True
    for each of the three thread attributes; a Gaze test previewed during a real (stand-in)
    calibration thread, and during a real (stand-in) connect thread, gets the mouse with
    `PREVIEW, Trial 1 of 3, Mouse pointer (tracker not ready)`, never calls `Calibration`, and the
    Setup tracker records no `start_streaming` / `clear_raw` / `stop` / `connect`; after the thread
    is released the same test previews on the real gaze again (with the new client after a
    connect); a parametrised case over `_connect_thread` / `_recheck_thread` / `_calibration_thread`
    covers Test Connection and Re-check (they share the attributes). `save_local_state` is replaced
    in these tests, so `configs/local_state.json` is not written. A mutation check (busy rule
    removed) fails 5 of them.
  - **pytest** (same flags): `5 failed, 3122 passed, 2 skipped in 528.69s`; the 5 are the known
    alpha 0.22 vs 0.35 ones.
  - **Deviations:** none. Open questions: none.

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
- **2026-10-09** — Order changed by the user: SPEC-audit-fixes (Fable audit F1-F9) runs first, then this SPEC.
- **2026-10-09** — Hub review, during an unattended run the user authorized (side-branch commit
  only). Scope matches H1-H9. Accepted deviations: the H4 wording follows the run bar's
  comma format from phase 1 ("Gaze pointer", "Mouse pointer (tracker not ready)", "Mouse
  pointer"); `preview_pointer=None` means mouse; `task_config_page.py` and `config_form.py`
  touched (H7 needs the two greying rules combined in `_refresh`). Hub fix round: SPEC-audit-fixes
  H1 locks Setup during a connect or calibration, so a gaze Preview while a Setup thread runs now
  falls back to the mouse (`SetupPage.device_busy()`); 6 tests. Hub pytest: **5 failed, 3122
  passed, 2 skipped** (the 5 are the known skip-worktree alpha checks). Live check, worktree code,
  fake tracker on 4343: A2 Gaze test with no tracker shows "PREVIEW, Trial i of 3, Mouse pointer
  (tracker not ready)"; A3 Input = Mouse greys the Gaze Smoothing card in place, values kept
  (ticked, 0.35), active again on Gaze, and its Preview says "Mouse pointer"; A1 after Connect and
  Do Calibration, Gaze Preview says "Gaze pointer" with "Tracking OK", and the pointer follows the
  fake tracker's gaze, not the mouse; A4 no file written under `sessions/`, the fake server saw one
  CALIBRATE_START (Setup's own) and one connection that stayed open; busy rule: a Preview started
  during a second Do Calibration ran on the mouse with "(tracker not ready)". Not live:
  smoothing off in a Practice / recorded Mouse run and its `session.log` line (unit tests);
  the real-gaze feel of A1 on the GP3 HD (user's call). Committed on branch
  `preview-gaze-pointer` only.
