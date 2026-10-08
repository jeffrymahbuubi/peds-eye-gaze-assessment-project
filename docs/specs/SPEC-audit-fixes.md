---
name: SPEC-audit-fixes
title: Fix the nine defects of the 2026-10-08 Fable bug audit (F1-F9)
status: approved 2026-10-09 (user decisions U1-U5; hub decisions H1-H12 approved by the user)
created: 2026-10-09
last_updated: 2026-10-09
next_step: /spec-run after SPEC-design-system-phase2 is merged, BEFORE SPEC-preview-gaze-pointer (both touch app.py)
related:
  - docs/audits/fable-bug-audit-2026-10-08.md (source: findings F1-F9 with file:line, repro output and fix directions)
  - SPEC-calibration-result-timeout.md (reader-thread race; §6.2 "exactly one reader thread")
  - SPEC-input-selection-and-follow.md (2026-10-07: Continue no longer waits for tracker/calibration, which made F1 reachable)
  - SPEC-subject-data-layout.md (H5 case-insensitive subjects, F6)
  - SPEC-preview-gaze-pointer.md (runs after this one)
---

# SPEC-audit-fixes: F1-F9 of the 2026-10-08 bug audit

## 1. Origin

The hub found a latent hazard on 2026-10-08 (`src/app.py:381` starts a fresh calibration for a gaze
run with no preset calibration; unreachable from the dashboard). The user asked a Fable agent to
audit the codebase for undiscovered bugs. The read-only audit at `b3e2f0f`
(`docs/audits/fable-bug-audit-2026-10-08.md`) found nine defects, eight confirmed by an offscreen
repro or a full trace. The hub spot-checked F1, F2 and F4 against the code. On 2026-10-09 the user
chose to fix **all nine** in one SPEC.

## 2. Current code (main `b3e2f0f`; re-grep, design phase 2 changes setup_page.py first)

The audit report has every `file:line`. In short:
- **F1** `setup_page.py` `_on_do_calibration_clicked` disables only its own button;
  `run_blockers()` / `continue_blockers()` ignore `_calibration_thread`; `run_flow._build` hands the
  shared client + the *old* result to the run; `app.py:415` `start_streaming()` starts a second
  reader inside the calibration's pause (`gazepoint_client.py` `start_streaming` checks only
  `_thread is None`; `streaming_paused.__exit__`).
- **F2** No `closeEvent` in `dashboard_window.py` / `main_window.py`; `trials.csv` and
  `metadata.json` are written only by `app._shutdown`; gaze CSVs flush every 60 rows.
- **F3** `gazepoint_client._on_disconnected` keeps `_latest` / `_last_raw_pog`; `app._tick` records
  it every tick as `valid=1`; `exporter.compute_fixation_saccade_metrics` counts duplicates.
- **F4** `setup_page._on_load_calibration_clicked` checks only the subject; alert says "valid."
  unconditionally; `app.py:408-413` auto-saves an invalid fresh calibration on the CLI path.
- **F5** Connect / Re-check / Load not guarded by the other threads; `_on_connect_succeeded`
  replaces `_client` without `stop()`.
- **F6** `setup_page.py` and `app.py:339` compare subject ids with `!=`; `subject_store.same_subject`
  is case-insensitive.
- **F7** Every in-run clock is `time.time_ns()`.
- **F8** `_ConnectThread` builds `GazepointClient()` with `enable=None`.
- **F9** `run_dir()` is created by the preset calibration save before steps that can raise.

## 3. Decisions

### 3.1 User decisions (2026-10-09)

| # | Decision |
|---|---|
| U1 | Fix **all nine** findings F1-F9 in this SPEC. |
| U2 | **F1/F5: lock all device actions while Connect or Do Calibration runs.** Connect, Test Connection, Re-check, Do Calibration, Load Calibration File and Continue to Tests are disabled until the thread ends; the Start page shows "Calibration in progress" as a blocker. A second Connect stops the old client first. |
| U3 | **F2: closing the window (X / Alt+F4) during a run asks the quit question**, the same as Quit (Alt-Q); if confirmed, the run ends normally, every file is written, then the window closes. **Plus crash safety:** `metadata.json` at the start, `trials.csv` appended after every trial. |
| U4 | **F4: refuse a calibration file marked `valid: false`**; the blocker stays; the CLI stops auto-saving invalid calibrations. |
| U5 | **Order:** this SPEC runs after design-system phase 2 is merged and **before** SPEC-preview-gaze-pointer. |

### 3.2 Hub decisions (approved by the user 2026-10-09)

- **H1 Busy predicate (F1, F5, U2).** `SetupPage._busy()` = any of `_connect_thread`,
  `_calibration_thread`, `_recheck_thread` is set. One `_refresh_enablement()` path disables the six
  controls of U2 while busy and restores the normal rules after. `run_blockers()` gains the item
  **"Calibration in progress (Setup page)."** while `_calibration_thread` is set, and **"Connecting
  to the tracker (Setup page)."** while `_connect_thread` is set; `continue_blockers()` gets the same
  two (so the Setup caption of design phase 2 lists them). The dashboard nav is not locked (Setup
  stays reachable to watch the progress).
- **H2 Client-level pause counter (F1 layer b).** `GazepointClient` keeps `_pause_depth`.
  `pause_streaming()` increments it (a nested pause returns True for "paused" and never reads the
  socket concurrently); `start_streaming()` while `_pause_depth > 0` only records "resume wanted";
  the outermost `streaming_paused.__exit__` starts the reader once. This keeps
  SPEC-calibration-result-timeout §6.2 ("exactly one reader thread") true in the
  start-inside-pause case. The hub's repro of the audit (`audit_a_client_race.py`, socketpair) is the
  model for the test.
- **H3 Old client on reconnect (F5).** `_on_connect_succeeded` calls `stop()` on the previous client
  (if any, and not the same object) before replacing it.
- **H4 Close during a run (F2, U3).** `DashboardWindow.closeEvent` (and `MainWindow.closeEvent` on
  the CLI path): while `flow` is RUN / PRACTICE / FINISHING, `event.ignore()` and route to the
  running `AssessmentApp._request_quit()`; when the run has finished and shut down, the window
  closes (the close request is remembered and re-issued after `on_finished`). PREVIEW: the quit is
  immediate (nothing is recorded), then the window closes. Outside a run: if a Setup thread is busy,
  wait for it (bounded, `QThread.wait` with a timeout and `requestInterruption`) so Qt never destroys
  a running `QThread`; then close.
- **H5 Crash safety (F2, U3).** `SessionRecorder.open()` writes `metadata.json` once (marked
  `"complete": false`); `close()` rewrites it (`"complete": true`). `trials.csv` gets its header at
  open and one row appended and flushed at each trial end (`_finish_trial`); `close()` no longer
  writes the whole table at once but keeps the final file byte-identical to today's for a normal
  run. Gaze/raw CSVs are flushed at every trial end too. A report of an incomplete run is out of
  scope (the folder simply keeps usable partial data, as `recorder.py:19-20` promises).
- **H6 Stale sample on disconnect (F3).** `_on_disconnected` and `stop()` clear `_latest` and
  `_last_raw_pog`; `app._tick` skips `record_gaze` / `_record_latency` when the client is not
  connected or `sample.t_ns` equals the last recorded stamp; `compute_fixation_saccade_metrics`
  de-duplicates on `t_ns` as `load_gaze_frames` does.
- **H7 Invalid calibration file (F4, U4).** `_on_load_calibration_clicked` raises the same
  `CalibrationFileError` path for `valid: false`, alert **"This calibration file is not valid. Run
  Do Calibration."**; the "valid." in the success alert comes from `result.valid`. `app.py`'s CLI
  path saves a fresh calibration only when `cal.valid`; `--calibration-file` with an invalid record
  fails fast like a subject mismatch.
- **H8 Subject match (F6).** `same_subject()` in both places (`setup_page`, `app.py`).
- **H9 Monotonic clock (F7).** One clock module (e.g. `src/engine/clock.py`): `now_ns()` =
  `wall_anchor_ns + (time.monotonic_ns() - mono_anchor_ns)`, anchored once per process. Every in-run
  `time.time_ns()` (app tick, base_task, eye_input dwell, entry_tracker, switch_select,
  follow_moving, the reader thread's receive stamp) uses it. Written timestamps stay in the same
  epoch-ns domain and format, so files, the analysis export golden tests and old sessions are
  unchanged; only a clock step during a run no longer shifts durations. `metadata.started_ns` and
  file names keep the real wall clock.
- **H10 Enable switches (F8).** `_ConnectThread` passes `load_default()["gazepoint"]["enable"]`
  (same as the CLI path); the comment at `app.py:362-366` is corrected.
- **H11 Orphan folder (F9).** If `AssessmentApp.__init__` raises after `run_dir()` created the
  folder, the folder is removed when it holds nothing but `calibration.json` (never anything else;
  shape-checked like `discard_session`). The comment at `app.py:320-321` becomes true.
- **H12 Tests.** One or more tests per finding, using the audit's repro scripts as the model
  (offscreen dashboard, a blocking `Calibration` stand-in, socketpair client): F1 Start/Continue
  blocked while calibrating + one reader inside a pause; F2 close during RUN asks and writes every
  file, `metadata.json` exists after open, `trials.csv` row per trial, normal-run files unchanged;
  F3 no stale rows after disconnect, metrics de-duplicated; F4 invalid file refused, CLI does not
  save an invalid fresh calibration; F5 second Connect stops the first client, controls disabled
  while busy; F6 `p001` loads a `P001` file; F7 a stepped `time.time_ns` does not move a dwell;
  F8 enable dict reaches the client; F9 failed build leaves no folder. Existing tests updated, never
  deleted; the analysis-export golden tests must stay byte-identical.

## 4. Design

No layout change. Visible differences only: disabled Setup controls while busy (existing disabled
style), the two new blocker sentences on the Start page / Setup caption, the F4 error alert, and the
quit question appearing on a window close during a run. No wireframe gate.

## 5. Scope

**In:** H1-H12 (F1-F9).
**Out:** the "already known" items of the audit report (vendor retained-result behaviour, AVE_ERROR
vs per-point banner, I-VT saccade counts, Keep-going drops the trial, etc.); reporting on an
incomplete run; any design-system or Preview change; new features.

## 6. Acceptance criteria

- **A1 (F1)** While Do Calibration runs, Start, Practice and Continue are blocked with "Calibration
  in progress"; a `start_streaming()` inside a pause never creates a second reader.
- **A2 (F5)** While any Setup thread runs, the six U2 controls are disabled; a second Connect stops
  the first client (no second socket, no orphan reconnect loop).
- **A3 (F2)** X / Alt+F4 during a recorded run shows the quit question; confirming writes
  `trials.csv` and `metadata.json` then closes; a killed process leaves `metadata.json` (complete:
  false) and every finished trial in `trials.csv`; a normal run's files are unchanged.
- **A4 (F3)** No gaze row is recorded while the tracker is disconnected; metrics count each sample
  once.
- **A5 (F4)** A `valid: false` file is refused with the H7 alert and the blocker stays.
- **A6 (F6-F9)** as H8-H11.
- **A7** Full pytest green (except the known skip-worktree alpha checks); analysis export goldens
  unchanged; live check passes (§7).

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | SPEC approved by the user (DONE 2026-10-09) | user |
| 1 | spec-implementer in a worktree based on the merged design-system phase 2: H1-H12 | — |
| 2 | Hub review + full pytest; §9 questions | — |
| 3 | Live check with `tools/fake_gazepoint_server.py`: Start blocked during Do Calibration; double Connect; X during a recorded Mouse run (quit question, files written); disconnect mid-run (stop the fake server) and no stale rows; load an invalid calibration file. Real GP3 HD optional (user's call) | user |
| 4 | Commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-09** — Drafted by the hub from `docs/audits/fable-bug-audit-2026-10-08.md` (Fable,
  read-only, at `b3e2f0f`; suite baseline 2792 collected, 2 skipped, exit 0). Hub spot-check:
  no `closeEvent` in src (F2), no `valid` check on load (F4), only the Do Calibration button guards
  the calibration thread (F1). User decisions U1-U5. Hub H1-H12 await approval.
- **2026-10-09** — The user approved H1-H12 as written. SPEC and the audit report committed on `feature/compass-task-flow`. Next: /spec-run this SPEC after design-system phase 2 is merged; SPEC-preview-gaze-pointer follows it.
