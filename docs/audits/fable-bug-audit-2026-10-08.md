# Bug audit, 2026-10-08 (Fable 5.1)

Read-only audit of `dev/peds-eye-gaze-assessment` at `feature/compass-task-flow` `b3e2f0f`
(the `.claude/worktrees/` copies were ignored). Trigger: the hub's finding that
`src/app.py:381` can start a fresh device calibration for any gaze run built without a
preset calibration; the question was whether more hidden paths of that kind exist.

Method: every module under `src/` that touches the device, the run lifecycle, the recorder
or the report was read end to end; each candidate was traced to a concrete operator
sequence and, where possible, reproduced offscreen with the venv Python (scripts in the
session scratchpad, `scratchpad/audit/audit_[a-e]_*.py`; none touches a device or a port).
No code, test or config file was changed. The suite was run once as a baseline (see the
end).

Confidence: **CONFIRMED** = reproduced by a snippet, or a fully traced synchronous path
with no timing dependence; **PLAUSIBLE** = traced, but depends on a condition that could
not be reproduced here.

## Summary

| ID | Severity | Area | Title | Confidence |
|----|----------|------|-------|------------|
| F1 | high | device / calibration lifecycle | Start, Practice and a Mouse-with-tracker run can begin while Do Calibration is still running on the shared client; the run restarts the reader the calibration paused and records against the previous calibration | CONFIRMED |
| F2 | high | data integrity / run lifecycle | No close guard: closing the window (X, Alt+F4) during a recorded run loses `trials.csv` and `metadata.json` entirely; both are written only at `_shutdown` | CONFIRMED |
| F3 | medium | data integrity | After a tracker disconnect mid-run the stale last sample is recorded once per tick as `valid=1`; `session_metrics.json` and `LATENCY_SAMPLE` are inflated (the report de-duplicates, `report.json` is not) | CONFIRMED |
| F4 | medium | calibration gate | Load Calibration File accepts a `valid: false` record, announces it as "valid." and clears the calibration blocker; such files are auto-written by the CLI path for a timed-out calibration | CONFIRMED |
| F5 | medium | device lifecycle / threads | Connect, Re-check and Load are live while a calibration or connect thread runs: a second Connect orphans the first client (socket + reader left running), a Re-check during calibration reads the same socket | CONFIRMED |
| F6 | low | calibration gate | Calibration-file subject match is case-sensitive while the subject store is case-insensitive (H5): a file saved as `P001` is refused for `p001` | CONFIRMED |
| F7 | low | time base | Every run clock is `time.time_ns()` (wall clock): a system clock step mid-run shifts every dwell, timeout, reaction time and trial window | PLAUSIBLE |
| F8 | low | device config | The dashboard's Connect ignores `gazepoint.enable.*` from `default.yaml` (every field on); only the CLI path honours it | CONFIRMED |
| F9 | low | data integrity | A gaze run whose `AssessmentApp.__init__` fails after `calibration.json` was written leaves an orphan run folder with no metadata | CONFIRMED |

Stray state noted while auditing, not a code finding: two empty files `0` and `cell.left()`
appeared in the project root `D:\RESEARCH ASSISTANT\50-Gaze-Point-Project\` at 22:01 and
22:02 local time (before this audit's repro runs; other agents were active). Left in place.

## Findings

### F1 (high, CONFIRMED). A run can start while Do Calibration is still polling the device

**Where.**
`src/ui/setup_page.py:922-937` (`_on_do_calibration_clicked` disables only the Do
Calibration button and starts `_CalibrationThread`), `setup_page.py:357-381`
(`run_blockers` never looks at `_calibration_thread`), `setup_page.py:383-391`
(`continue_blockers` drops the tracker and calibration blockers; Continue is allowed since
the 2026-10-07 decision), `src/ui/run_flow.py:200-233` (`_build` hands the Setup tab's
`client` and its current `calibration_result` to the run), `src/app.py:415`
(`self.client.start_streaming()` unconditionally), `src/inputs/gazepoint_client.py:523-529`
(`start_streaming` only checks `_thread is None`, which is exactly the state
`pause_streaming` leaves behind, 545-553), `gazepoint_client.py:555-569`
(`streaming_paused.__exit__` sees a `_thread` and assumes it is the reader that failed to
stop, so it only clears the stop event), `src/engine/calibration.py:400-405, 450-612`
(the poller reads the same socket), `setup_page.py:939-956` (`_on_calibration_finished`
replaces or clears the result whenever the thread ends).

**Scenario.** A valid calibration exists (loaded, or measured earlier in the sitting). The
operator presses Do Calibration (5 points about 10 s, 9 points longer; with "Show
calibration window" unticked nothing is visible on the task monitor), then Continue to
Tests (enabled), Run Test, Start or Practice (both enabled: `run_blockers()` is empty).
`_build` passes the shared `GazepointClient`, whose reader is paused by the calibration,
plus the **old** `CalibrationResult`. `AssessmentApp.__init__` calls `start_streaming()`,
which starts a new reader on the socket the calibration poller is reading. The run
begins while Gazepoint Control is still in calibration (`CALIBRATE_CLEAR`/`RESET` +
`CALIBRATE_START` were sent at `calibration.py:426-429`). The same holds for a Mouse test
while the tracker is connected and "calibrated" (the tracker is handed in to record
alongside, `run_flow.py:202-207`).

**Evidence.**
`audit_b_start_during_calibration.py` (offscreen dashboard, a `Calibration` stand-in that
blocks in its QThread where the real one polls):
```
calibration thread running: True
Setup alert: Calibrating…
Continue to Tests enabled while calibrating: True
run_blockers() while calibrating: []
flow: Flow.START | Start enabled: True | Practice enabled: True
calibration handed to a run now would be the OLD one: CalibrationResult(n_points=5, mean_error_px=20.0, valid=True, ...) measured
after the calibration thread finished: calibration_result = None | alert: Calibration did not produce a valid result. ...
```
`audit_a_client_race.py` (client level, a socketpair):
```
pause: was_streaming = True | reader1 alive = False | _thread = None
control: with the pause intact the poller sees: b'<CAL ID="CALIB_RESULT" ...
start_streaming() inside the pause: new reader alive = True
now the poller sees: b'' (the second reader consumed CALIB_RESULT)
after the pause: stop_event set = False | reader2 still running = True
```

**Impact.** The gaze recorded for the first seconds (or the whole run, if the operator is
quick) comes from a device whose calibration is being replaced: `metadata.json` says
`calibration_source` = measured/loaded with the old point count and error, `session.log`
says the same, and nothing marks the run. The calibration's own `CALIBRATE_RESULT_SUMMARY`
ACKs and `CALIB_RESULT` push are consumed by the run's reader (they are not `REC`, so the
reader drops them), so the calibration ends `poll_timeout` / invalid and
`_on_calibration_finished` **clears** the Setup result after the run; a calibration that
does complete replaces the result the run was recorded under. With "Show calibration
window" ticked the Control window also sits over the task canvas. This is the class of
defect the audit was asked for: the device state changes under a run with no record of it.

**Fix direction.** Two layers, both small. (a) `SetupPage`: expose "calibration in progress"
as a blocker in `run_blockers()` *and* `continue_blockers()` (or disable Continue, Connect,
Re-check, Load and the nav while `_calibration_thread` / `_connect_thread` /
`_recheck_thread` is set). (b) `GazepointClient`: make the pause explicit and counted
(`_pause_depth`), so `start_streaming()` during a pause only records "resume wanted" and
`streaming_paused.__exit__` is the one that starts the reader; a nested
`pause_streaming()` increments the depth. The §6.2 acceptance of
SPEC-calibration-result-timeout ("exactly one reader thread") should get a test for the
`start_streaming()`-inside-the-pause case.

### F2 (high, CONFIRMED). Closing the window during a recorded run loses the trial table and the metadata

**Where.** `src/ui/dashboard_window.py:57-152` and `src/ui/main_window.py:59-77` define no
`closeEvent`; `src/app.py:1125-1149` (`_shutdown`) is the only caller of
`_write_session_files`; `src/data/recorder.py:303-318` (`write_trials`, `write_metadata`)
are called only from `app.py:1169` and `recorder.py:327` (`close()`); `recorder.py:94`
flushes the gaze and raw CSVs every 60 rows. `grep closeEvent|aboutToQuit src/` finds
nothing. The brand title bar is hidden during a run (HC8) but the OS frame with its close
button is not.

**Scenario.** Any recorded run (Flow.RUN) and the operator clicks the window's X, presses
Alt+F4, or the process dies (Windows update, crash). `QApplication.exec()` returns when
the last window closes; `_shutdown` never runs.

**Evidence.** `audit_c_close_mid_run.py` (record mode, 40 ticks, then the app object is
dropped as the process exit would):
```
run folder: ...\sessions\P001\runs\click_grid\2026-10-08_2209
  metadata.json      MISSING        0 bytes
  trials.csv         MISSING        0 bytes
  events.jsonl       present      220 bytes
  session.log        present      534 bytes
  gaze_stream.csv    present        0 bytes
  all_gaze.csv       present        0 bytes
  calibration.json   present      168 bytes
```

**Impact.** The whole trial table of the run is lost (nothing reconstructs it from
`events.jsonl`), `metadata.json` (subject, test id, settings, geometry, calibration) is
never written, and up to 59 buffered gaze rows per CSV are lost. The test stays Not Done,
the folder is an orphan that `build_report` refuses (`ReportError`, no `trials.csv`) and
the Discard guard would delete if ever pointed at it. The recorder's own docstring
(`recorder.py:19-20`) promises "a crash mid-session still leaves usable partial data";
for the two files the report depends on it does not.

**Fix direction.** (a) A `closeEvent` on `DashboardWindow` (and `MainWindow`) that, while
`flow` is RUN / PRACTICE / PREVIEW / FINISHING, either ignores the event or routes it
through `AssessmentApp._request_quit` so the quit question and `_shutdown` run. (b) Make
the recorder crash-tolerant: write `metadata.json` once at `open()` and again at `close()`;
append each `TrialRecord` to `trials.csv` in `_finish_trial` (or at least flush the CSVs
on every trial end). (c) `QThread` children of `SetupPage` (`setup_page.py:840-846,
927-937`) should be stopped or waited for in that same `closeEvent`; today a close during
Connect or Do Calibration destroys a running `QThread` (Qt aborts with "QThread: Destroyed
while thread is still running").

### F3 (medium, CONFIRMED). A disconnect mid-run records the stale sample as valid once per tick

**Where.** `src/inputs/gazepoint_client.py:664-671` (`_on_disconnected` keeps `_latest` and
`_last_raw_pog`), `src/inputs/eye_input.py:232-238` (`poll` forces the pointer invalid
when `is_connected()` is False) versus `eye_input.py:206-212` (`latest_sample` returns the
cached sample unchanged), `src/app.py:1037-1047` (`record_gaze(sample)` and
`_record_latency` whenever `sample is not None`), `src/data/exporter.py:97-115`
(`compute_fixation_saccade_metrics` counts every row). The report loader de-duplicates on
`t_ns` (`src/data/report_eye.py:37-61`), so `report.json` is unaffected.

**Scenario.** Gazepoint Control is closed, crashes, or the USB link drops during a
recorded gaze run. HC9 says the run continues (it does, with "Tracker disconnected" on the
bar). Every tick until reconnect writes the last sample again: same `t_ns`, same x/y,
`valid=1`.

**Evidence.** `audit_d_disconnect_rows.py`:
```
tick 0: pointer.valid=False  recorded sample: t_ns=1993333383 valid=True
tick 1: pointer.valid=False  recorded sample: t_ns=1993333383 valid=True
session_metrics.json fixation_saccade (150 real rows + 1500 repeats):
{'n_samples': 1650, 'valid_ratio': 0.9909, 'effective_rate_hz': 1661.07, 'n_fixations': 6}
real rows alone would give: n_samples=150, valid_ratio=0.9, effective_rate_hz~150
```

**Impact.** `session_metrics.json` (written at the end of every run, `app.py:1204`)
over-reports `n_samples`, `valid_ratio` and `effective_rate_hz` for the run, and the
`LATENCY_SAMPLE` events (`app.py:1113-1123`) carry the growing age of the stale sample.
`gaze_stream.csv` itself carries thousands of identical rows that any reader without the
report's de-duplication (notebooks, `analysis/`) will count. The same applies to a
`GazepointClient` whose socket is never reconnected (Control not restarted).

**Fix direction.** Clear `_latest` and `_last_raw_pog` in `_on_disconnected` (and in
`stop()`), and in `_tick` skip `record_gaze` / `_record_latency` when
`not self.client.is_connected()` or when `sample.t_ns` equals the last recorded stamp.
`exporter.compute_fixation_saccade_metrics` could also de-duplicate on `t_ns` like
`load_gaze_frames` does.

### F4 (medium, CONFIRMED). An invalid calibration file passes the gate and is labelled "valid."

**Where.** `src/ui/setup_page.py:1001-1024` (`_on_load_calibration_clicked` checks only
the subject id; the alert at 1021-1023 says "valid." unconditionally),
`src/engine/calibration.py:148-179` (`load_calibration_result` has no validity check),
`src/app.py:408-413` (the CLI path auto-saves any non-stub fresh calibration, including a
`poll_timeout` result with `valid=False`, `calibration.py:615-626`), `app.py:394-395` (a
preset is re-saved into every run folder, so a bad record propagates).

**Scenario.** A `--task X --gui` launch whose calibration times out writes
`runs/<task>/<stamp>/calibration.json` with `"valid": false`. Later, on the dashboard,
Load Calibration File is pointed at that run folder (or any hand-copied file).

**Evidence.** `audit_e_setup_page_gates.py` part 1:
```
loaded result: CalibrationResult(n_points=5, mean_error_px=None, valid=False, per_point=None)
alert text: Calibration loaded: 5 points, mean error n/a, valid.
calibration blocker present: False | run_blockers: []
```

**Impact.** A gaze test runs with no measured calibration behind it while the Setup page,
the Start page, `session.log` ("Calibration loaded ... invalid or unmeasured" is written,
but nothing blocks) and `metadata.calibration_source = "loaded"` all read as calibrated.

**Fix direction.** Refuse `valid=False` in `_on_load_calibration_clicked` (same
`CalibrationFileError` path as a subject mismatch), do not auto-save an invalid fresh
calibration in `app.py:408-413`, and derive the alert wording from `result.valid`.

### F5 (medium, CONFIRMED). Connect / Re-check / Load stay enabled while a calibration or connect thread runs

**Where.** `src/ui/setup_page.py:831-846` (`_on_connect_clicked` guards only
`_connect_thread`, not `_client` or `_calibration_thread`), `setup_page.py:848-857`
(`_on_connect_succeeded` replaces `_client` and never calls `stop()` on the previous one),
`setup_page.py:868-878` (`_on_recheck_device_info_clicked` guards only `_recheck_thread`),
`src/inputs/gazepoint_client.py:486-510` (`refresh_device_info` uses `streaming_paused`,
which inside another caller's pause returns `was_streaming=False` and reads the socket),
`gazepoint_client.py:673-687` (an orphaned client keeps reconnecting every second and
re-sending every `ENABLE_SEND_*`).

**Evidence.** `audit_e_setup_page_gates.py` part 3 and `audit_a_client_race.py` part A2:
```
connect button enabled while connected: True
client is second: True | first.stop() called: False
pause_streaming() from the second caller returns: False (... reads the socket concurrently)
```

**Impact.** A second Connect (a common reflex after a "Connection failed" or a hang)
leaves the first socket and its reader alive for the rest of the process: two TCP clients
on Gazepoint Control, a second reconnect loop, duplicate `ENABLE_SEND_*` traffic, and
memory held by a 10,000-record queue nobody drains. A Re-check pressed during Do
Calibration competes with the poller for `CALIB_RESULT` and the summary ACKs (the same
loss as F1, smaller window). Pressing Load Calibration File during Do Calibration sets a
loaded result that the finishing thread then overwrites or clears.

**Fix direction.** One `_busy()` predicate (`any of the three threads is set`) that
disables Connect, Test Connection, Re-check, Do Calibration, Load and Continue together;
`_on_connect_succeeded` stops the previous client before replacing it. The client-level
pause counter of F1 covers the Re-check case regardless of the UI.

### F6 (low, CONFIRMED). Calibration-file subject match is case-sensitive

**Where.** `src/ui/setup_page.py:1004` and `src/app.py:339` compare `saved.subject_id !=
subject_id`; `src/engine/subject_store.py:112-114` (`same_subject`) and SPEC-subject-data-
layout H5 make `P001` and `p001` one subject with one folder.

**Evidence.** `audit_e_setup_page_gates.py` part 2:
```
same_subject('P001','p001') = True | Load for 'p001': Calibration file subject_id 'P001' does not match Subject ID 'p001'
```

**Impact.** A calibration saved for the subject on one day cannot be reused when the ID
is typed in another case the next day, although every other store treats it as the same
child; the operator re-calibrates or gives up. No wrong data.

**Fix direction.** Use `same_subject` in both places.

### F7 (low, PLAUSIBLE). Wall-clock time base for every in-run duration

**Where.** `src/app.py:1003` (`t_ns = time.time_ns()` per tick), `src/tasks/base_task.py:5`
("All timing is in nanoseconds (`time.time_ns` domain)"), `src/inputs/eye_input.py:130-175`
(dwell), `src/tasks/entry_tracker.py`, `src/tasks/switch_select.py`,
`src/tasks/follow_moving.py:125` (frame time, capped at 250 ms), the reader thread's
sample stamps `gazepoint_client.py:662`.

**Scenario.** Windows time service (w32time) steps the clock when the offset exceeds its
slew threshold, a VM or laptop resumes, or an operator corrects the clock during a run.

**Impact.** A forward step completes a dwell in progress or times the trial out at once,
every reaction time and trial window in `trials.csv` shifts by the step, and the
`raw_clock_offset_ns` alignment (`recorder.py:222-224`, a running minimum) is pulled to
the earliest offset seen. Not reproduced here (no clock was stepped); listed because a
clinical timing tool should not depend on it.

**Fix direction.** `time.monotonic_ns()` for every in-run clock, one wall-clock anchor in
`metadata.started_ns`; the device-TIME alignment then uses the monotonic receive time.

### F8 (low, CONFIRMED by trace). The dashboard's Connect ignores `gazepoint.enable.*`

**Where.** `src/ui/setup_page.py:213` builds `GazepointClient()` with `enable=None`
(every record on, `gazepoint_client.py:408-409`); `src/app.py:367` passes
`gp_cfg.get("enable")` on the CLI path only. `configs/default.yaml:55-74` documents the
switches as something a therapist can set.

**Impact.** Turning a field off in YAML has no effect on the dashboard, the only path the
clinic uses; the app comment at `app.py:362-366` says the opposite. No wrong data (extra
fields are recorded, never missing ones).

**Fix direction.** `_ConnectThread` takes `enable` from `load_default()` and passes it on.

### F9 (low, CONFIRMED by trace). An orphan run folder when the run fails to build after the calibration save

**Where.** `src/app.py:327-330` (`run_dir()` makes the folder on first use),
`app.py:394-395` (the preset calibration is saved there before anything else),
`app.py:514-614` (the recorder, the view and `build_task` come after and can raise:
`build_task` for a stored structural value a task rejects, an `OSError` opening a file),
`src/ui/run_flow.py:234-236` (the exception is shown as "Could not start" and the Start
page stays). The comment at `app.py:320-321` claims a run that fails to start leaves no
empty folder behind.

**Impact.** `runs/<task>/<stamp>/` with only `calibration.json`; the next run in the same
minute becomes `<stamp>_2`; nothing lists, reports or discards the orphan. Cosmetic for
the data, confusing for whoever reads the folder.

**Fix direction.** Make the folder when the recorder opens (write `calibration.json`
through the recorder), or wrap the rest of `__init__` so a failure after `run_dir()`
removes a folder that holds only `calibration.json`.

## Already known (not re-reported)

- Gazepoint Control answers `CALIBRATE_RESULT_SUMMARY` with the retained previous
  calibration from the moment `CALIBRATE_START` is sent, and `CALIB_RESULT` is sometimes
  never pushed (vendor behaviour; restart hint): SPEC-gui-audit-2026-09-10 §9,
  SPEC-calibration-result-timeout §4.3 and §10.
- The Setup banner's "mean error 74px" (vendor `AVE_ERROR`) disagrees with the 6-25 px
  per-point breakdown on the same page: SPEC-compass-task-flow §10, 2026-10-07 entry.
- I-VT saccade counts implausibly high on real data (568 saccades vs 124 fixations, peak
  1623 deg/s; device noise passes the 50 deg/s threshold): SPEC-compass-task-flow §10,
  2026-10-07 P9c in-app check, "worth its own item".
- "Keep going" at the quit question counts as a pause and drops the in-flight trial
  (accepted as built): SPEC-compass-task-flow §9, P7b.
- Report path smoothing per distinct sample, not per tick (accepted): §9 P9c.
- Standalone `TaskSettingsDialog` labels in logical px at 150 % (accepted): §9 P9a FX4;
  app-wide light palette: §9 P9a backlog.
- Standalone `--task X --gui` `MainWindow` clipping: SPEC-live-settings-panel §10.10.4.
- Follow the Target hitbox margin fixed at 40 px (user decision):
  SPEC-input-selection-and-follow §9 step 3.
- Open live checks that only the user can do: A10 (input-selection step 5), the real-gaze
  grid check (SPEC-target-size-and-motion-paths), the real-gaze dead-zone check
  (SPEC-grid-cell-gap).

## Checked, no bug found

- **`src/app.py:381` (fresh calibration for a gaze run without a preset).** Unreachable
  from the dashboard: `StartTestPage._on_start` (`start_test_page.py:344-348`) re-reads
  `run_blockers()` and returns on any; the chain `startRequested` to `RunFlow._on_start`
  to `_ready()` to `_build()` to `AssessmentApp(...)` is one synchronous call in one
  event-loop turn, so a gaze test always arrives with `tracker` and `calibration` both
  set; a Mouse test with an unready tracker gets `client=None`, hence `NoTracker` and the
  stub branch (`app.py:354-360, 381-385`). Only the CLI path (`app.py:1230`) reaches the
  fresh branch, as intended. The one way round it is F1 (the thread still in flight hands
  over a *stale but non-None* result, so the branch is still not taken; the harm is
  elsewhere).
- **Calibration state between the Start-page check and the run build.** Same synchronous
  chain; the only writers of `SetupPage._calibration_result` are the queued
  `_on_calibration_finished` slot and the Setup-page buttons, neither of which can
  interleave inside that call. Sound, except for the in-flight thread (F1).
- **Preview.** Always the mouse (`app.py:313`), `client=MouseGazeSource`
  (`config_flow.py:244-257`), `NullRecorder`, `_gaze_recorded=False`, no `clear_raw`, no
  folder, no timing log, `_owns_client=False` so `_shutdown` never stops anything. It
  never touches `setup_page.client`.
- **Practice.** `NullRecorder`, the shared client is only `clear_raw()`-ed and
  `start_streaming()`-ed (a no-op when the reader runs; see F1 when it does not); no
  folder, no `calibration.json`, no diagnostics (`app.py:404, 656-664`).
- **Run folder uniqueness / overwrites.** `new_run_dir` uses `mkdir()` without
  `exist_ok` (`run_paths.py:71-78`); `record_result` refuses a second result
  (`subject_tests.py:393-394`); `discard_session` resolves and shape-checks the path and
  refuses links and sub-folders (`session_files.py:27-77`). `report.json` and the PDF are
  written to a temp name and `os.replace`d.
- **Pause / Skip / Quit re-entrancy.** `_quit_pending` and `_shutdown_done` guard the quit
  (`app.py:794-812`); `skip_trial` only acts in `WAIT_INPUT` and never while paused
  (`base_task.py:715-723`); the quit and run-end dialogs are application-modal, so Alt-P /
  Alt-Q / Esc and the bar are blocked while they show; the timer is stopped before
  `on_finished` fires (`app.py:1134`). Quit while already paused keeps the pause on "Keep
  going" (`app.py:808-811`).
- **Double Start / double Run Test.** The second `_on_start` finds `flow is not START`
  and returns (`run_flow.py:149`); `RunFlow.open` returns unless `IDLE`.
- **Switch input.** Space/Enter auto-repeat ignored, release re-arms, focus loss releases,
  a press while paused or between trials is logged and never counted, the refractory
  debounce restarts per trial (`app.py:735-757`, `canvas.py:145-162`,
  `base_task.py:492-540, 639-648`).
- **Settings merge.** `merged_config` and `AssessmentApp.__init__` apply structural then
  live in the same order (`settings_snapshot.py:55-69`, `app.py:292-304`); unknown keys are
  ignored; `complete_settings` fills every registry key so a stored configuration never
  depends on a later YAML change; names compare case-insensitively; `decide_save` keeps
  Standard unstored. `metadata.settings` is the final merged config (`app.py:512`).
- **Units.** Canvas metadata in physical px with `canvas_units="physical"`
  (`app.py:92-106, 931-953`); `Geometry.canvas_logical_size` converts back by
  `display_scale_percent` (`report_geometry.py:147-154`); target radius, hitbox margin and
  Follow distances stay in logical px end to end; the Mouse pointer stream is
  canvas-normalised and converted to monitor-normalised on load
  (`report_eye.py:64-86`); `raw_clock_offset_ns` is the minimum host-minus-device offset
  (`recorder.py:213-224`). No mismatch found.
- **Report arithmetic on empty input.** `format_pct_n`, `summary_rows`,
  `eye_summary.pooled`, `heat_map`, `build_follow`, `pursuit_gain`, `trial_pupil`,
  `measured_sample_rate_hz` and `median_eye_distance_mm` all guard zero counts; an empty
  run is discarded by `ask_run_end` before any report.
- **Subject switch between flows.** Every flow re-reads the test by id under the subject
  typed in Setup (`dashboard_flow.find_test`), `_ready()` re-checks the subject, and the
  report page carries the test's own subject (`report_flow.py:85`).
- **Output root.** `AssessmentApp` reads `recording.output_root` from the merged task
  config while the window reads `default.yaml` only; a task YAML `overrides:` block that
  set it would make `record_result` refuse the run ("Results not saved"). No shipped YAML
  sets it (`configs/tasks/click_static.yaml:8` has it commented out). Note only.

## What was not checked

- Nothing was run against the real GP3 HD or port 4242; whether Gazepoint Control streams
  `REC` during its own calibration, and what the POG values look like then, is from the
  API corpus and the SPEC history, not measured in this audit.
- F7 (clock step) was not reproduced.
- The compiled exe's close path (`prepare_frozen_environment`, `src/main.py:42-73`) was
  not exercised; F2 is traced on the source path and applies to both.
- No qt-mcp live drive; every UI repro is offscreen.

## Baseline

Full suite, venv Python, this checkout, 2026-10-08 22:11 local: 2792 collected, exit code
0, 2 skipped, no failure in the progress output (the known `alpha 0.22 vs 0.35` failures
did not fire on this machine). Nothing in `src/`, `tests/` or `configs/` was touched; the
only new path is `docs/audits/`.
