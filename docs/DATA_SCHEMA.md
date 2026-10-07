# Data Schema

Each recorded run writes one folder under the output root (default
`sessions/`), named `<date>_<subject>_<task>_run<N>` (`N` counts that subject's
runs of that task on that day). Practice and preview runs write nothing:
only `run_mode: "record"` reaches disk.

```
sessions/2026-07-15_P001_click_static_run1/
  metadata.json      # subject + session + calibration + settings + outcome + schema_version
  session.log        # human-readable timeline
  gaze_stream.csv    # per-frame gaze samples (not written by a Mouse run with no tracker)
  pointer_stream.csv # per-frame mouse pointer (a Mouse run only)
  all_gaze.csv       # every raw <REC>, Gazepoint Analysis 62-column export layout
  fixations.csv      # one row per fixation, same layout (written at session close)
  eye_geometry.csv   # per raw <REC>: 3D eye position + per-eye POG (device rate)
  trials.csv         # one row per presented trial (analysis-ready)
  target_track.csv   # the moving target's path (follow_moving only)
  events.jsonl       # discrete events (TARGET_SHOWN, HIT, TIMEOUT, SKIPPED, PAUSED, ...)
  session_metrics.json  # rolled-up result (summary / fixation_saccade / saccades)
  report.json        # cache of the per-test report, written when the run is saved
```

Beside the run folders the output root holds the per-subject stores below.
`<subject>` is the Subject ID made safe as a folder name (characters illegal
on Windows replaced; an ordinary ID such as `P001` is unchanged); the verbatim
ID stays in `metadata.json` and in every test record.

```
sessions/
  _tests/<subject>/t_<10 hex>.json            # one file per planned test (the Test List)
  _tests/<subject>/_deleted/t_<10 hex>.json   # a deleted test's record is moved here
  _settings/<subject>/<task>/<date>_<time>.json   # saved named configurations
  _calibrations/<subject>/                    # saved calibrations (Setup)
```

All timestamps are **nanoseconds** (`time.time_ns()` domain, UTC-based). Divide
by `1e6` for milliseconds. Coordinates are **normalized** (0–1, origin
top-left) unless the field name ends in `_px`.

## metadata.json

| field | type | notes |
|-------|------|-------|
| `subject_id` | str | subject identifier |
| `session_id` | str | folder name |
| `started_ns` | int | session start |
| `schema_version` | int | currently `1`; loaders should tolerate change |
| `gazepoint_model` | str | e.g. `GP3HD` |
| `input_mode` | str | derived from the test's Pointer and Selection (`specs/SPEC-input-selection-and-follow.md` H1): `eye` (gaze + dwell), `gaze_switch` (gaze + switch), `switch` (mouse + switch), `mouse_dwell` (mouse + dwell), `mouse_follow` (mouse, Follow the Target) |
| `input_pointer` | str\|null | what moved the pointer: `gaze` or `mouse`; null on older sessions |
| `input_selection` | str\|null | how a target was selected: `dwell` or `switch`; null for Follow the Target (it has none) and on older sessions |
| `gaze_recorded` | bool\|null | whether a tracker recorded gaze into the run. False only for a Mouse run with no tracker (or an uncalibrated one): no `gaze_stream.csv`, `all_gaze.csv` or `eye_geometry.csv`, and the report's eye sections say "not recorded". Null on older sessions |
| `calibration_error_px` | float\|null | mean calibration error (data QC) |
| `calibration_points` | int\|null | 5 or 9 |
| `tasks` | list[str] | tasks run this session |
| `notes` | str | free text |
| `test_id` | str\|null | the Test List entry this run belongs to (`t_` + 10 hex); null for a standalone `--task X --gui` run and on older sessions |
| `test_name` | str\|null | that test's name when the run started |
| `seed` | int\|null | the random seed that drew the target order: the test's own seed (0-999999) for a dashboard run, `0` for a standalone run, null on older sessions. Same seed and same configuration give the same order |
| `run_mode` | str\|null | `"record"` (the only mode that reaches disk); null on older sessions |
| `config_name` | str\|null | the named configuration the run used (`"Standard"` or a saved name; also in `settings`); null for a standalone run |
| `planned_trials` | int\|null | trials the task would have presented (`len(targets)`) |
| `completed_trials` | int\|null | rows written to `trials.csv`, skipped ones included |
| `skipped_trials` | int\|null | trials the operator skipped |
| `interrupted_trials` | int\|null | trials that were running when the operator paused; each is dropped (never written) and re-presented fresh with the same `trial_id` |
| `pause_count` | int\|null | times the run was paused (the Quit question pauses the run too) |
| `outcome` | str\|null | `"completed"` (the task ran out of trials) or `"ended_early"`. There is no `"discarded"`: a discard deletes the whole folder |
| `ended_by` | str\|null | `"finished"` or `"operator_quit"` |
| `ended_ns` | int\|null | when the run ended |
| `layout_slots` | list[[x, y]]\|null | canvas-normalized centres of the task's fixed layout (grid cells, scanning icons), so a report can outline the empty slots; null for `click_static` and `follow_moving` |
| `raw_clock_offset_ns` | int\|null | host-clock time of `all_gaze.csv` `TIME=0`, so `t_ns = raw_clock_offset_ns + TIME * 1e9` puts a device-rate row on the trial clock; null when no raw file was written |
| `hitbox_margin_px` | float\|null | the run's `dwell.jitter_tolerance_px`, the margin added to the target radius to make the hitbox ("on target" for Follow the Target's time on target and for the first-fixation metric). Recorded for every task so a report can draw the hitbox; null on older sessions |
| `settings` | object\|null | everything the run was configured with; see below |

All of the rows from `test_id` on are additive and null on older sessions;
`schema_version` is deliberately not bumped for them.

### settings

The complete configuration the run used, written from the final merged config
(nothing can change during a run, so this is the whole story):

| key | type | notes |
|-----|------|-------|
| `config_name` | str\|null | `"Standard"` or the saved configuration's name; null for a standalone run |
| `live` | object | flat, keyed by dotted setting key: `dwell.threshold_ms`, `dwell.refractory_ms`, `dwell.jitter_tolerance_px`, `dwell.visual_cursor`, `dwell.progress_ring`, `dwell.instant_feedback`, `dwell.smoothing.enabled`, `dwell.smoothing.alpha`, `task.timeout_ms`, `task.inter_trial_interval_ms`, and `motion.speed_frac_per_s` for `follow_moving` only |
| `structural` | object | nested like the task's YAML block: one entry per control of the task (trial count, target size, grid rows / columns / gap, motion path, icon count and layout, ...), `feedback.hit_sound` / `feedback.miss_sound` where the task has them, plus `theme` and `feedback.particles` (recorded, not offered as controls) |

Sessions recorded before the Compass-style redesign may carry a partial or no
`settings` block, and may also hold `source`, `profile_saved_at` and
`profile_file` (where the settings came from); nothing reads those three. They
may also carry `hud_hidden_at_start` and `hud_toggle_count`, the metadata of
the operator HUD that no longer exists (see "Removed with the HUD" below).

## trials.csv

One row per trial that was presented: hit, timed out, or skipped. Trials the
run never reached are absent (`planned_trials` minus the row count), and a trial
dropped by a pause is not written (its re-presentation is).

| column | type | meaning |
|--------|------|---------|
| `trial_id` | int | 0-based index within the task |
| `task_id` | str | task identifier |
| `target_x`, `target_y` | float | target center, normalized |
| `target_radius_px` | float | hitbox radius |
| `t_target_shown_ns` | int | target onset |
| `t_first_gaze_on_target_ns` | int\|"" | first gaze inside hitbox |
| `t_click_ns` | int\|"" | selection time (blank if miss/timeout) |
| `t_end_ns` | int | trial end |
| `is_hit` | 0/1 | target selected |
| `is_timeout` | 0/1 | timed out |
| `attempts` | int | selections attempted (off-target switch presses count) |
| `t_selectable_start_ns` | int\|"" | first moment the target could be selected (equals `t_target_shown_ns` except in `follow_moving`) |
| `reaction_time_ms` | float\|"" | `t_click - t_target_shown` |
| `reaction_time_from_selectable_ms` | float\|"" | `t_click - t_selectable_start` (the meaningful one for `follow_moving`) |
| `time_to_first_fixation_ms` | float\|"" | `t_first_gaze_on_target - t_target_shown` |
| `is_skipped` | 0/1 | the operator skipped the trial: neither a hit nor a timeout (`is_hit` and `is_timeout` are 0, `t_click_ns` blank); `t_end_ns` is when the skip happened |
| `entries` | int | debounced entries of the gaze into the target's hit area (an exit counts only after the gaze stays off for the dwell `hold_grace_ms`, 120 ms by default); 0 when it never reached it. `time_to_first_fixation_ms` is the time of the first entry |
| `end_x`, `end_y` | float\|"" | where the target was at `t_end_ns`, canvas-normalized: equal to `target_x`/`target_y` for a static task, the live position for `follow_moving` (whose `target_x`/`target_y` is the start) |
| `slot_index` | int | which grid cell / scanning icon the target was, `-1` for a task with no fixed layout |
| `clicks` | int | switch presses counted while this trial's target was up (a press on button down, left mouse press on the canvas or Space / Enter); 0 for a Dwell test. Presses between trials, and presses within the refractory period of the previous counted one, are not counted (they are `SWITCH_IGNORED` events) |
| `click_errors` | int | how many of those presses were Click errors: off the target, or with no gaze (none valid within 150 ms, a blink); 0 for a Dwell test |
| `valid_ms` | float\|"" | Follow the Target only: milliseconds of the trial the pointer had a valid sample (a frame's span is capped at 250 ms, so a stall is not counted as tracking); blank for the other tasks |
| `on_target_ms` | float\|"" | Follow the Target only: milliseconds of those the pointer was inside the target's hitbox (radius plus `hitbox_margin_px`) at that frame; blank for the other tasks |
| `time_on_target_pct` | float\|"" | `100 * on_target_ms / valid_ms`; blank when `valid_ms` is 0 or for the other tasks |
| `mean_dist_px` | float\|"" | Follow the Target only: mean distance from the pointer to the target's centre over the valid frames, in canvas logical px; blank with none |

**Follow the Target rows** (`specs/SPEC-input-selection-and-follow.md` H6, H7, H9): nothing
is selected, so every trial lasts exactly `task.timeout_ms` ("Trial duration", default 10 s)
and ends by time. `is_hit` is **followed** (at least 50 % of the valid time on target),
`is_timeout` is always 0, `t_click_ns`, `attempts` and the click columns are blank or 0,
and `time_to_first_fixation_ms` is when the pointer first reached the target ("time to
find"). The four columns above are computed live from the smoothed pointer, per frame, so
a Mouse run with no tracker has them too. A folder whose `trials.csv` header has no
`on_target_ms` is an older Follow & Click run: `is_hit` there is a click on the target in its
selection window and `is_timeout` a trial that ran out.

Directly loadable with `pandas.read_csv` or R.

## gaze_stream.csv

One row per rendered frame.

| column | type | meaning |
|--------|------|---------|
| `t_ns` | int | capture time |
| `x`, `y` | float | gaze point, normalized |
| `valid` | 0/1 | tracker-reported validity |
| `fixation_id` | int\|"" | FPOGID (blank if not fixating) |
| `fix_duration_s` | float\|"" | fixation duration so far |
| `pupil_left`, `pupil_right` | float\|"" | pupil diameter (mm), v2 analysis |

## pointer_stream.csv

A Mouse run only (`input_pointer: "mouse"`; `specs/SPEC-input-selection-and-follow.md`
H4): the mouse pointer once per rendered frame, so the report can draw its path.
Columns `t_ns` (host clock, like `gaze_stream.csv`), `x`, `y` (canvas-normalized; a
value outside 0-1 is a mouse that left the canvas) and `valid` (1 while the pointer is
inside the canvas). The raw mouse, not the smoothed pointer the cursor dot shows. A
run with a tracker connected and calibrated also writes the gaze files; one without
writes only this (`gaze_recorded: false`).

## target_track.csv

`follow_moving` only: the moving target's position at about 20 Hz, so a report
can draw its path. Columns `t_ns` (host clock, like `trials.csv`), `trial`
(the 0-based `trial_id`) and `x`, `y` (canvas-normalized). A trial re-presented
after a pause repeats its `trial` id, so read a trial's rows within its own
`[t_target_shown_ns, t_end_ns]`. Other tasks write no such file.

## all_gaze.csv and fixations.csv

Gazepoint Analysis's own export layout, reproduced from the raw `<REC>`
stream so the session reads like an Analysis export (`gp3tools` etc.) —
`specs/SPEC-gazepoint-analysis-export-parity.md`. Off with
`recording.save_all_gaze: false`.

- **One row per `<REC>` received at device rate** (150 Hz on USB 3), not per
  rendered frame — so it has more rows than `gaze_stream.csv`.
- **62 columns in Analysis's order and spelling**: `MEDIA_ID`, `MEDIA_NAME`
  (the task id), `CNT`, `TIME(<recording start>)` (seconds from the first
  record), `TIMETICK(f=<Hz>)`, the FPOG/BPOG fields, cursor/keyboard/`USER`,
  pixel pupil (`LPCX`…`RPV`), blinks (`BKID`/`BKDUR`/`BKPMIN`), mm pupil
  (`LPMM`…`RPMMV`), biometrics (always 0 — the kit is not subscribed),
  `PIXS`/`PIXV`, `AOI` (always blank), `SACCADE_MAG`, `SACCADE_DIR`,
  `VID_FRAME` (always 0). Device values are written verbatim.
- **`SACCADE_MAG`/`SACCADE_DIR`** are filled at session close on each
  fixation's row: pixel distance and angle (0–360°, counter-clockwise from
  +x, screen-up positive) from the previous fixation's POG, scaled by the
  **tracked monitor** size in `metadata.json` (`screen_width_px` ×
  `screen_height_px`) — never by the canvas. Zero elsewhere.
- **`fixations.csv`** = the rows Analysis would export: the last `FPOGV=1`
  record of each `FPOGID`, excluding the recording's final record, with
  zero-duration fixations dropped. Both rules are golden-tested against a
  real Analysis v7.3.0 export (`tests/fixtures/gazepoint_analysis_sample/`).

Geometry fields in `metadata.json` (all additive, `null` when unknown):
`screen_width_px`/`screen_height_px` (tracked monitor, from `SCREEN_SIZE`),
`canvas_width_px`/`canvas_height_px`/`canvas_offset_x_px`/`canvas_offset_y_px`
(where the task scene sat on it), `screen_physical_width_mm`/`_height_mm`
(config, else the OS/EDID value), `viewing_distance_mm` (config). These let
`session_metrics.json`'s `saccades` block report amplitude in degrees of
visual angle as well as px.

All geometry px fields are **physical** pixels (Gazepoint's unit), so at any
Windows display scale `FPOGX × screen_width_px − canvas_offset_x_px` is the
gaze position inside the canvas. `canvas_offset_*` is relative to the origin of
the screen the canvas was on. `canvas_units` is `"physical"` for these
sessions; it is absent (`null`) on older sessions, whose `canvas_*` fields
were Qt logical px (identical to physical at 100 % scale, different only at
125/150 %). `CANVAS_RESIZED` events carry `canvas_w`/`canvas_h` in physical px
too.

## eye_geometry.csv

3D eye position and per-eye point of gaze, one row per raw `<REC>` at device
rate — the same rows as `all_gaze.csv`, joinable on `CNT` and aligned on
`TIME` (same session-relative seconds, same origin and rule). Off with
`recording.save_eye_geometry: false` (default on).
`specs/SPEC-gazepoint-analysis-export-parity.md` §10.6.

Columns, in order: `CNT`, `TIME`, `LEYEX`, `LEYEY`, `LEYEZ`, `LPUPILD`,
`LPUPILV`, `REYEX`, `REYEY`, `REYEZ`, `RPUPILD`, `RPUPILV`, `LPOGX`, `LPOGY`,
`LPOGV`, `RPOGX`, `RPOGY`, `RPOGV`.

- `*EYEX/Y/Z`: eye position relative to the camera focal point, **metres**
  (`LEYEZ` ≈ 0.65 means the eye is 65 cm from the camera); `*PUPILD`: pupil
  diameter in metres; `*PUPILV`: 1 when that eye's data is valid.
- `*POGX/Y`: that eye's point of gaze, screen fractions like `FPOG`/`BPOG`;
  `*POGV`: 1 when valid.
- Values are written as the device sent them; an attribute the device did
  not send (e.g. `--replay` fixtures, or a record disabled under
  `gazepoint.enable.eye_left`/`eye_right`/`pog_left`/`pog_right`) is an
  **empty cell**.
- Headless `--replay` (no GUI) writes neither this file nor `all_gaze.csv`.

## Device and quality fields in metadata.json

All additive and `null` when unknown (older sessions lack them):

| field | type | notes |
|-------|------|-------|
| `gazepoint_rate_hz` | int\|null | device sampling rate from `PRODUCT_ID` (60 vs 150 Hz) |
| `gazepoint_bus` | str\|null | e.g. `USB3` |
| `gazepoint_serial` | str\|null | `SERIAL_ID`; placeholder `0` becomes null |
| `display_refresh_hz` | float\|null | refresh rate of the canvas's screen, 0.1 Hz |
| `measured_sample_rate_hz` | float\|null | records ÷ device-time span of the raw file, `(n-1)/(TIME_last-TIME_first)` over `eye_geometry.csv` (or `all_gaze.csv` if only that is written), 0.1 Hz; live sessions only; null with fewer than 2 rows. Not the on-screen meter, which is capped by the GUI frame rate |
| `loop_fps` | int\|null | poll/render loop rate the app ran at, Hz (`specs/SPEC-ui-setup-task-selection.md` §25); null on older sessions and headless `--replay` |
| `loop_fps_source` | str\|null | `"config"` (explicit `app.target_fps` number), `"device"` (`target_fps: auto` on a live tracker, its `gazepoint_rate_hz`) or `"fallback"` (`auto` without a live known rate, or an invalid value: 60) |
| `measured_eye_distance_mm_median` | float\|null | median over `eye_geometry.csv` rows of the mean of the valid eyes' `*EYEZ` (valid = `*PUPILV` 1 and value > 0), mm, rounded to 1 mm; null with no valid rows. `viewing_distance_mm` (config) is still what degree maths uses |

## events.jsonl

One JSON object per line: `{"t_ns": ..., "kind": "...", ...payload}`.

| kind | payload | meaning |
|------|---------|---------|
| `TARGET_SHOWN` | `trial`, `x`, `y` | a trial's target appeared |
| `HIT`, `TIMEOUT`, `SKIPPED` | `trial` | how the trial ended |
| `FOLLOWED`, `NOT_FOLLOWED` | `trial`, `time_on_target_pct` | how a Follow the Target trial ended (instead of `HIT` / `TIMEOUT`): at least 50 % of the valid time on the target, or less. A skipped Follow trial is `SKIPPED` as everywhere |
| `MISS_CLICK` | `x`, `y`, `selectable`; a switch press adds `reason` (`"no_gaze"`) or `used_fallback` (true) when they apply | an off-target selection |
| `SWITCH_PRESS` | `trial`, `x`, `y`, `on_target`, `used_fallback`, and `reason` (`"no_gaze"`) when no valid pointer lay within 150 ms | one switch press counted while a target was up. `x`, `y` are the pointer the press was judged at; `used_fallback` is true when the pointer was invalid at the press (a blink) and the last valid one within 150 ms was used |
| `SWITCH_IGNORED` | `phase` (`iti`, `ready`, `done`, `paused` or `target`), `x`, `y`, and `reason` (`"refractory"`) for `phase` `target` | a switch press that counted for nothing: made while no target was up (between trials, before the first, after the last, or while paused), or, with a target up, within `dwell.refractory_ms` of the previous counted press of the same trial (the switch's debounce; the window restarts with each trial and an ignored press does not extend it). Not a click and not a Click error |
| `PAUSED` | `trial`, `interrupted` | the operator paused; `interrupted` is true if a trial was running |
| `TRIAL_INTERRUPTED` | `trial`, `reason`, `elapsed_ms` | the running trial was dropped by a pause |
| `RESUMED` | none | the pause ended |
| `CANVAS_RESIZED` | `canvas_w`, `canvas_h` | the canvas changed size mid-run (physical px) |
| `TARGET_INSET`, `TARGET_SHRUNK` | sizes and canvas | targets were moved inward or shrunk to fit the canvas |
| `LATENCY_SAMPLE` | `latency_ms_mean`, `_min`, `_max`, `n_samples` | gaze sample arrival to this app's frame, summarised over a window of frames |

### Removed with the HUD

The operator HUD was removed (SPEC-compass-task-flow.md 4C.7), and with it the
metadata fields `hud_hidden_at_start` and `hud_toggle_count` and the events
`HUD_TOGGLED`, `SETTING_CHANGED` and `SETTINGS_PROFILE_SAVED`. Nothing changes
during a run any more. Older sessions may still contain them; loaders should
ignore them.

## report.json

A cache of the per-test report (SPEC-compass-task-flow.md 4D): the numbers on
the Summary / Detailed pages and in the PDF. It is written when a run is saved
and rebuilt from the raw files when it is missing, unreadable or from another
`report_version`; the raw files stay the source of truth. The same folder always
gives byte-identical JSON. A figure a folder's files cannot give is `null`,
never 0, so an old folder degrades instead of failing. Every time stored here
and in the other data files stays in milliseconds (`mean_dur_ms`,
`fixation_duration_ms`, the `*_ms` parameters); only what a person reads, on the
pages and in the PDF, shows seconds.

| top-level key | contents |
|---------------|----------|
| `report_version` | `REPORT_VERSION` (currently `3`); a cache with another value is rebuilt |
| `params` | the analysis parameters used (`ivt` saccade detector, `entries` exit hold, `pupil`, `heat`, `path`), so the numbers are reproducible. `path` holds the gaze path's thinning (`min_step_deg`, `min_step_ms`, `split_gap_ms`, `max_points`, applied to the raw stream) and `smoothing` (`{enabled, alpha}`), the on-screen cursor's own filter the path is drawn through (`alpha` is the run's `dwell.smoothing.alpha`, 0.22 when none was recorded; `enabled: false` leaves the raw stream) |
| `session` | `session_id`, `task_id`, `subject`, `test_name`, `config_name`, `started_ns`, `planned_trials`, `completed_trials`, `outcome`, `n_rows`, `n_scored`, `n_skipped`, `n_not_presented`, `pointer`, `selection`, `gaze_recorded` (the three input facts of `metadata.json`; null on an older folder; `gaze_recorded: false` makes the Eye Metrics table say "not recorded" instead of a dash), and `sources` (which input files the folder had, so the UI can say why a value is shown as a dash; includes `pointer_stream`) |
| `geometry` | the monitor / canvas geometry the degree and pixel figures use, and `assumed_for_visuals` (true when the folder lacks the monitor size) |
| `config` | `rows`: the Test Configuration table, `[label, value]` pairs |
| `trials` | one object per `trials.csv` row: `trial` (1-based), `outcome` (`hit` / `timeout` / `skipped`), `size_deg`, `distance_deg`, `target` (`x`, `y`, `end_x`, `end_y`, radii, `slot`), `onset_ns`, `end_ns`, `attempts`, `error_free`, `trial_time_s`, `reaction_time_s`, `entries`, and the per-trial `fixations`, `saccades`, `pupil`, `scanpath` (the fixation centroids `[[x, y], ...]` in time order, canvas-normalized: the Summary map's path) and `path` (the whole gaze as polylines, thinned and smoothed with the cursor's filter: the Detailed view's path) |
| `summary` | `rows`: the Summary of Results table (error-free, all selected, not selected, all trials); `eye`: the Eye Metrics table |
| `map` | the Target Map: `aspect`, `slots`, `hit_tolerance_px`, `marks` and `note` |
| `heat` | the gaze heat map: `w`, `h`, `data` (empty when there was no gaze on the canvas, with `empty: true`) and `off_canvas_share` |
| `quality` | `valid_share`, `off_canvas_share` and `warnings` (`{code, text}` for the report's banner: `ended_early`, `low_valid_gaze`, `canvas_resized`) |
| `follow` | Follow the Target only (absent for the other tasks); see below |

A Follow the Target trial's `outcome` in `trials` is `followed` / `not_followed` (or `skipped`), read from `is_hit` when the `trials.csv` header has `on_target_ms`; the eye figures, the quality share and `n_scored` count those outcomes like `hit` / `timeout` for the other tasks. `map.hit_tolerance_px` is the run's `hitbox_margin_px`.

### follow

`{"legacy": true}` for a folder recorded as Follow & Click (no `on_target_ms` in its `trials.csv`),
which keeps its old report layout. Otherwise (`specs/SPEC-input-selection-and-follow.md` H7, H8):

| key | contents |
|-----|----------|
| `legacy` | `false` |
| `params` | the analysis parameters: `max_err_deg` (3, a sample further than this from the target is not pursuit), `bounce_excl_ms` (100, excluded around each direction reversal of the target), `min_usable_s` (0.5, less usable time than this gives no gain), `followed_pct` (50) |
| `path`, `speed_frac_per_s`, `trial_duration_s` | the motion path (`horizontal` / `vertical` / `diagonal_tlbr` / `diagonal_trbl` / `circular`), the target's speed (canvas widths per second), and the trial duration (median of the trials, seconds) |
| `gaze_available` | false for a Mouse run with no tracker: `pursuit_gain`, `catch_up_*` and `gain_usable_s` are then null (the pointer is still measured) |
| `hitbox_margin_px` | the margin the "on target" test used |
| `trials` | one object per `trials.csv` row, in order: `trial` (1-based), `outcome`, `followed` (null when skipped), `duration_s`, `valid_ms`, `on_target_ms`, `time_on_target_pct`, `mean_distance_px` and `mean_distance_deg` (to the target's centre), `time_to_find_s`, `valid_pct` (valid share of the trial), `pursuit_gain`, `gain_usable_s` (the seconds the gain was taken over), `catch_up_count`, `catch_up_per_s` (catch-up saccades per second of valid gaze) and `pointer_path` (the pointer as `[{"on": true / false / null, "pts": [[x, y], ...]}, ...]`: canvas-normalized polylines split where the pointer enters or leaves the hitbox of the moving target, thinned like the gaze path; from the raw gaze, or from `pointer_stream.csv` for a Mouse run) |
| `summary` | whole-test figures: `n_trials` (not skipped), `followed`, `time_on_target_pct` (`mean`, `min`, `max`), `mean_distance_deg`, `time_to_find_s`, `pursuit_gain` (median of the trials' gains) and `pursuit_gain_trials`, `catch_up_per_s` (all catch-ups over all valid gaze seconds), `valid_pct` |

**Pursuit gain** is the least-squares slope of the gaze position along the target's direction of
travel over 100 ms windows, divided by the target's speed; the trial's gain is the median over its
usable windows. A window is usable only if every sample in it is valid, not inside a saccade (the
existing I-VT detector, widened by one sample each side), within `max_err_deg` of the target and
more than `bounce_excl_ms` away from a reversal of the target. A circular path uses the tangent.
The target's position at the device rate is linearly interpolated from `target_track.csv`.
Under `min_usable_s` of usable time, the gain is null. **Catch-up saccades** are the saccades of
the existing detector falling inside the trial's valid gaze.

## Test store

The Tests tab keeps one JSON file per planned test, in
`sessions/_tests/<subject>/t_<10 hex>.json` (SPEC-compass-task-flow.md 4A.2).
One file per test means one bad file loses one test; the reader skips a file it
cannot parse. Delete is soft: the record is moved to `_deleted/`, and the run
folders are never touched. A record holds:

| field | type | notes |
|-------|------|-------|
| `schema_version` | int | currently `1` |
| `test_id` | str | `t_` + 10 hex, equal to the file name |
| `subject_id` | str | the verbatim Subject ID (the folder name is only a locator) |
| `name` | str | Test Name, 1-60 characters, unique per subject (case-insensitive) |
| `task_id` | str | `click_static` / `click_grid` / `follow_moving` / `scanning` |
| `created_at` | str | local time with its UTC offset |
| `origin` | str | `"created"` or `"copied"` |
| `configuration` | object | `{name, structural, live}`: a snapshot of the configuration, never a reference, so editing a saved configuration later cannot change an existing test |
| `notes`, `evaluator` | str | free text, edited on the report page |
| `seed` | int | 0-999999; a copy gets a new one |
| `status` | str | `"not_done"`, `"done"` or `"ended_early"`; a test that has run is locked |
| `completed_at` | str\|null | when the saved run finished |
| `planned_trials`, `completed_trials` | int\|null | copied from the saved run |
| `outcome` | str\|null | `"completed"` or `"ended_early"`; null while not done |
| `session_dir` | str\|null | the run folder's **name** under the output root, never an absolute path |

Saved named configurations live in `sessions/_settings/<subject>/<task>/`, one
file per save (`<date>_<time>.json`, never overwritten): `schema_version` (`2`),
`subject_id`, `task_id`, `name` (empty for an unnamed save), `saved_at`, `live`,
`structural` and `calibration` (the calibration the values were tuned under,
descriptive only). A name resolves to its newest file; older ones stay as
history. `"Standard"` is the task's own defaults: reserved, never stored.

## Versioning

`schema_version` is written into every `metadata.json`. Downstream loaders
should branch on it and tolerate older layouts (plan §8 risk mitigation).
Every field added since version 1 is additive and null on older sessions, so
`schema_version` has not been bumped; a loader should read named keys and
treat a missing one as unknown. `report.json` and the test records carry their
own versions (`report_version`, `schema_version`).
