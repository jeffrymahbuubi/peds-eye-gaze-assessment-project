---
name: SPEC-calibration-result-timeout
title: Calibrations after a task run lose CALIB_RESULT (reader-thread race)
status: complete — implemented, reviewed, live-validated with the real GP3HD (after a Gazepoint Control restart, §4.3); committed
created: 2026-10-05
last_updated: 2026-10-05
next_step: none
related:
  - SPEC-gui-audit-2026-09-10.md (§7 timing diagnostic, §9 retained-result fix and the elapsed-time fallback)
  - SPEC-result-logic.md (§8-§9 Calibration Details section; §12 live check where this was found)
  - SPEC-ui-setup-task-selection.md (§24.2 refresh_device_info's "not while streaming" guard)
---

# SPEC-calibration-result-timeout — calibrations after a task run lose `CALIB_RESULT`

**Status: DONE 2026-10-05. Two causes: the reader-thread race (§3, fixed by §4.1) and Gazepoint Control getting stuck after a calibration run from its own window (§4.3, vendor behaviour; operator hint added). Live-validated.**

## 1. Origin / what was reported

Found during `SPEC-result-logic.md` §12's live check (2026-10-05, real GP3HD,
user as subject, dashboard, subject `HUDTEST`). After a task had run, every
**Do Calibration** on the Setup page finished "valid", but **View Calibration
Details** showed "Per-point breakdown not available for this calibration."
The saved `sessions/_calibrations/HUDTEST/calibration_5pt.json` had
`"per_point": null`.

## 2. Evidence

`sessions/_diagnostics/calibration_timing.jsonl` (written by every
calibration, SPEC-gui-audit §7). All five calibrations on 2026-10-05:

| ts (UTC) | outcome | `CALIB_RESULT` at | stopped at | error |
|---|---|---|---|---|
| 06:48:54 | `calib_result_never` | never | 11.469 s | 33.1 |
| 06:49:20 | `calib_result_never` | never | 11.484 s | 7.21 |
| 06:49:47 | `calib_result_never` | never | 11.484 s | 31.37 |
| 06:54:50 | `calib_result_never` | never | 11.469 s | 24.87 |
| 06:55:33 | `calib_result_never` | never | 11.469 s | 18.64 |

11.47 s = `_min_calibration_s` (10.72 s) + `_CALIB_RESULT_GRACE_S` (0.75 s):
the elapsed-time fallback of `Calibration._poll_for_result`
(`src/engine/calibration.py:542-546`). For comparison, the last 2026-10-02
calibrations got `CALIB_RESULT` at ~10.3 s (`calib_result_after_ack`). Every
2026-10-05 calibration came after `click_static_run1` had already run in the
same dashboard process. (The repeated `8.42` values on 2026-09-16/17 are the
fake server's constant `AVE_ERROR`, not stale device data.)

## 3. Root cause (confirmed by experiment)

`Calibration.run()` reads the tracker socket directly (`_drain_socket`, then
`_poll_for_result`'s `recv()` loop), which is only safe while
`GazepointClient`'s background reader thread is **not** running. The code
states this rule in several places (`src/app.py:260` "Calibration must run
before start_streaming()", `_query_device_info`'s docstring, and
`refresh_device_info()` which raises `RuntimeError` while streaming,
`src/inputs/gazepoint_client.py:486`).

The dashboard breaks the rule. The Setup page owns one shared client for the
whole sitting. The first task run calls `client.start_streaming()`
(`src/app.py:297`) and nothing ever stops it, because `AssessmentApp` never
stops a client it does not own. From then on, **Do Calibration**
(`_CalibrationThread.run` → `Calibration.run`, `src/ui/setup_page.py:240`)
competes with the reader thread for every `recv()`. The reader parses only
`<REC>` lines and drops everything else, so whenever it wins the chunk that
holds the one-time, unprompted `<CAL ID="CALIB_RESULT" …>` push, the per-point
breakdown is lost. The calibration then waits for the elapsed-time fallback
and returns the last summary it happened to receive, with `per_point=None`.

**Experiment (hub, 2026-10-05, scratch script, not in repo).** A fake server
streams `REC` at 150 Hz after `ENABLE_SEND_DATA`, answers
`CALIBRATE_RESULT_SUMMARY`, and pushes one `CALIB_RESULT` 1.5 s after
`CALIBRATE_START`. 12 calibrations each:

| reader thread | `per_point` captured |
|---|---|
| not running (`connect()` only) | 12 / 12 |
| running (`start_streaming()` first) | 6 / 12 |

On the real device, with 150 Hz `REC` data and a ~10 s calibration, the
reader won 5 of 5.

**Impact.**
- Every Setup-page calibration done after a task run in the same dashboard
  sitting has `per_point: null` in its saved files (`calibration.json`,
  `_calibrations/<subject>/calibration_<n>pt.json`), and the Calibration
  Details table is empty. This cannot be recovered after the fact.
- The reported `mean_error_px` is **probably** this calibration's own value:
  the fallback reads the summary ~1 s after a real 5-point calibration
  (~10.3 s) ends, and the five values differ. This is not guaranteed: the
  reader can also swallow summary ACKs, and a calibration that runs longer
  than the fallback would return the retained previous result
  (SPEC-gui-audit §9). The fix removes the race, so the
  `CALIB_RESULT`-confirmed path is used again.
- Fresh-connect calibrations, and the standalone `--task X --gui` path
  (calibrates before `start_streaming`), are not affected.

## 4. Design (approved by the user 2026-10-05)

### 4.1 Pause the reader during calibration (user choice: "pause reader during calib")

- New `GazepointClient.pause_streaming() -> bool`: if the reader thread is
  running, set `_stop_event`, `join` it, and set `_thread = None`, **keeping
  the socket open**. Return whether it was running. No-op returning `False`
  when not streaming or in replay mode.
- Add a context manager `GazepointClient.streaming_paused()` that calls
  `pause_streaming()` and, on exit (also on exception), calls
  `start_streaming()` only if it was running before.
- `Calibration.run()` wraps everything that touches the socket (drain, SETs,
  `CALIBRATE_START`, `_poll_for_result`) in the client's
  `streaming_paused()`. Use `getattr` so test doubles without it still work.
  This protects every caller, not only the Setup page.
- The join must be bounded. The implementer checks the reader's `recv()`
  timeout (`_run_socket`, `_open_socket`). If the thread does not exit within
  the bound, log a warning, leave `_thread` set (do not start a second
  reader) and run the calibration anyway, which is today's behaviour. The
  calibration must never hang on the pause.
- `start_streaming()` already clears `_stop_event`. Resuming after the pause
  must give the same state as a fresh `start_streaming()`: `latest()` and
  `drain_raw()` keep working, and there is still only one reader thread.
- Not covered by this design: a disconnect/reconnect that happens during the
  pause. The reader is what reconnects; while paused the calibration's own
  `OSError` handling applies, as on a fresh connect. Note this in the code
  comment and do not build anything for it.

### 4.2 Say so when per-point details are missing (user choice: "say so in the alert")

- Setup-page alert after **Do Calibration** with a valid result and
  `result.per_point` empty:
  `Calibration measured — {n} points, mean error {e}px, valid. Per-point details were not received.`
  It is still a success alert, and the Continue gate is unchanged. Text only:
  no layout change, so no wireframe step.
- Session Log (`calibration_log_line`, `src/app.py`): when `cal.valid` and
  `not cal.per_point`, append ` Per-point details not available.` to the
  line, for both measured and loaded. That is true for both, since an older
  loaded file may also lack them.
- The Calibration Details empty-state text is unchanged.

### 4.3 Second cause: Gazepoint Control stuck after its own calibration (found by the user 2026-10-05)

The user isolated the cause that dominated the 2026-10-05 failures. If a
calibration is first run from **Gazepoint Control's own window**, Gazepoint
Control afterwards stops pushing `CALIB_RESULT` to API clients and answers
`CALIBRATE_RESULT_SUMMARY` instantly with its retained result
(`t_summary_satisfied_s` ≈ 0.03 s on every failed run). Our calibration then
always ends `calib_result_never` (5-point) or `poll_timeout` (6-point),
whether or not a task ran first. **Closing and reopening Gazepoint Control
clears it.** Confirmed by the timing log: the first calibration after the
restart (07:38:10 UTC) was `calib_result_before_ack`, with `CALIB_RESULT` at
10.33 s and the summary satisfied at 10.5 s.

This is vendor behaviour and cannot be fixed in our code. User decision
(2026-10-05, "add restart hint"): the §4.2 Setup alert text becomes
`Calibration measured — {n} points, mean error {e}px, valid. Per-point details were not received — if this repeats, close and reopen Gazepoint Control, then calibrate again.`
The Session Log note is unchanged. §4.1 (the race fix) stays: the race is
real (§3 experiment) and independent of this cause.

## 5. Scope

**In:** `src/inputs/gazepoint_client.py` (pause/resume + context manager),
`src/engine/calibration.py` (`run()` wraps socket use),
`src/ui/setup_page.py` (alert text), `src/app.py` (`calibration_log_line`
note), tests (`tests/test_calibration.py`, client tests, and
`tests/test_calibration_source.py` for the log line).

**Out:** the one-socket-owner redesign (rejected option); any change to the
fallback timing constants (`_min_calibration_s`, `_CALIB_RESULT_GRACE_S`);
re-creating `per_point` for already-saved files; Calibration Details layout;
`configs/default.yaml` and `configs/local_state.json` (off-limits).

## 6. Acceptance criteria

1. **Race test (must fail without the fix):** a loopback fake server streams
   `REC` continuously and pushes `CALIB_RESULT` during calibration. With the
   client already streaming, `Calibration.run()` captures `per_point` in
   **every** run of a repeated loop (e.g. 10/10; the unfixed code loses
   about half). Keep it fast with short `point_delay_s`/`point_timeout_s`.
   Show that it fails with the wrapping reverted.
2. After that calibration, the client is streaming again: exactly one reader
   thread, and `latest()` updates with new samples.
3. A client that was **not** streaming stays not streaming after
   `Calibration.run()`.
4. A calibration that raises or returns early (e.g. the `OSError` path)
   still resumes streaming.
5. The bounded-join path: a reader that cannot be stopped in time does not
   hang `Calibration.run()` (unit-level, simulated).
6. Alert text and Session Log note per §4.2, unit-tested.
7. Full pytest suite: 0 failures.
8. **Live check (hub + user, real GP3HD):** in one dashboard sitting, run a
   task first, then **Do Calibration** → `calibration_timing.jsonl` shows
   `calib_result_after_ack` (or `_before_ack`), not `_never`; **View
   Calibration Details** shows the table; the next task run streams normally
   (gaze cursor moves, `all_gaze.csv` has rows).

## 7. Plan

1. ~~Diagnosis + design + user decisions~~ DONE 2026-10-05 (§2-§4).
2. ~~`spec-implementer` builds §4 and meets §6.1-§6.7.~~ DONE 2026-10-05 (uncommitted).
3. ~~Hub review: diff vs §5, every §6 criterion, own full pytest run.~~ DONE (290 passed, 0 failed).
4. ~~Live check §6.8 with the user~~ DONE 2026-10-05: failed first (stuck Gazepoint Control, §4.3), passed after a Gazepoint Control restart; see §10.
5. ~~Commit + push after the user's OK; memory update.~~ DONE 2026-10-05.

## 8. Impl log

- **2026-10-05 — claude-sonnet-5-5.** Implemented §4, met §6.1-§6.7.
  - Files: `src/inputs/gazepoint_client.py` (`pause_streaming()`,
    `streaming_paused()`, `_PAUSE_JOIN_TIMEOUT_S = 2.0` — reader `recv()` times
    out at 1 s; on a timed-out join `_thread` stays set and the context manager
    only clears the pending stop event on resume, so no second reader),
    `src/engine/calibration.py` (`run()` wraps the new `_run_on_socket()` + poll
    in `streaming_paused` via `getattr`/`nullcontext`; socket is re-read inside
    the pause), `src/ui/setup_page.py` (new `calibration_measured_alert_text`),
    `src/app.py` (`calibration_log_line` note).
  - Tests added: 4 in `tests/test_calibration.py` (race 10/10 + resume/one
    reader/`latest()` advancing; non-streaming stays non-streaming; raise and
    `OSError` early-return resume; bounded join), 2 in
    `tests/test_calibration_source.py` (log note, alert text). Existing
    `VALID` fixture there now carries `per_point` so the old log-line
    assertions stay unchanged.
  - Revert check: with `run()`'s wrapping disabled the race test failed 3/3
    (lost at run 2, 5, 0); with the fix it passed in every run, repeated.
  - pytest (full, venv): `290 passed in 106.74s`; 0 failed (baseline 284).
  - Deviations: none. Left undone: live check §6.8 (hub + user).
- 2026-10-05 (claude-sonnet-5-5) §4.3 restart-hint text: changed the empty-
  `per_point` suffix in `calibration_measured_alert_text()`
  (`src/ui/setup_page.py`) to "... not received — if this repeats, close and
  reopen Gazepoint Control, then calibrate again."; updated the matching
  assertion in `tests/test_calibration_source.py` (no new tests). Session Log
  note in `src/app.py` unchanged.
  - pytest (full, venv): `290 passed in 107.31s`; 0 failed.
  - Deviations: none. Left undone: nothing.

## 9. Implementer open questions

## 10. Log

- **2026-10-05 — created; diagnosed; design approved.** Found in
  `SPEC-result-logic.md` §12's live check. Cause confirmed by a fake-server
  experiment (6/12 lost while streaming, 0/12 when not) and matched to the
  device timing log (5/5 `calib_result_never`, all after a task run in the
  same sitting). User decisions via `AskUserQuestion`: pause the reader
  during calibration (not a one-socket-owner rewrite); state missing
  per-point details in the Setup alert and the Session Log.

- **2026-10-05, later — §4 implemented, reviewed; live check FAILED.**
  `spec-implementer` (claude-sonnet-5-5, §8) built §4; hub review found
  the diff in scope and every §6.1-§6.7 criterion met, with the hub's own
  run at **290 passed, 0 failed** and the race tests passing on 3 extra
  runs. Live check §6.8 (real GP3HD, user as subject, subject `HUDTEST`):
  a task ran first (`click_static_run4` in the first launch, `run5` after
  a relaunch to clear a qt-mcp desync caused by the native file dialog),
  then **Do Calibration**. All three calibrations made with the fix in
  place still ended `calib_result_never` at 11.47 s:
  07:29:28 (66.26 px), 07:29:56 (24.97 px), 07:33:37 (236.31 px), all
  with `t_summary_satisfied_s` ≈ 0.03 (the retained previous result).
  **Conclusion: the reader-thread race is real (fake-server experiment)
  but is not the whole cause.** Gap in the §2 evidence: every 2026-10-05
  calibration came after a task run, none on a fresh connection, so "the
  device or Gazepoint Control is not sending `CALIB_RESULT` at all today"
  was never ruled out. On 2026-10-02 fresh-launch calibrations got it at
  ~10.3 s. The dashboard exited (code 0, no traceback) after the 07:33
  calibration; not yet established whether the user closed it. Also
  confirmed live: the §4.2 Session Log note (`click_static_run4`: "…
  valid. Per-point details not available."). **User chose to stop here.**
  The fix stays **uncommitted** in the working tree (`src/app.py`,
  `src/engine/calibration.py`, `src/inputs/gazepoint_client.py`,
  `src/ui/setup_page.py`, `tests/test_calibration.py`,
  `tests/test_calibration_source.py`, this SPEC). Next: a standalone raw
  capture (send the app's calibration commands, log every line the device
  sends for 20 s), first on a fresh connection and then with the data
  stream on. That decides whether `CALIB_RESULT` is sent at all, and §3/§4
  get revised from there.

- **2026-10-05, end — second cause found by the user; §4.3 added; live
  check PASSED; committed.** The user isolated what dominated the failures:
  after a calibration is run from Gazepoint Control's own window, Gazepoint
  Control stops pushing `CALIB_RESULT` to API clients. Our calibrations
  then end `calib_result_never` (also seen on a fresh connection, 07:36:06,
  and a 6-point `poll_timeout` at 07:36:46). Restarting Gazepoint Control
  clears it (§4.3). The user chose "add restart hint" for the Setup alert;
  implemented by `spec-implementer` (§8), and the hub reran **290 passed,
  0 failed**. Live, with Gazepoint Control restarted and the user's own
  dashboard launch running the fix: 07:38:10 `calib_result_before_ack`
  (fresh connection); `click_grid_run1` (07:42:18, 10,592 gaze rows), then
  Do Calibration at 07:42:38 → `calib_result_after_ack`, `CALIB_RESULT` at
  10.36 s, details table shown (user), which confirms the race fix with
  the stream on; then `scanning_run1` with 11,961 gaze rows and a moving
  cursor (user), which confirms the stream resumes. The failed 07:29-07:33
  live checks are explained by §4.3, not by the fix. Not exercised live:
  §6.5 bounded join (unit-tested only).
