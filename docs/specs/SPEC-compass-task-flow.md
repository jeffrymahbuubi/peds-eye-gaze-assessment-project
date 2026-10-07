---
name: SPEC-compass-task-flow
title: Compass-style task flow — per-subject Test List, configuration page, Preview/Practice, HUD-less run, per-test report
status: approved 2026-10-06 (U1-U17, R1-R12 and all per-part hub decisions); P1-P6 DONE 2026-10-06 (P6 wireframes approved); P7 DONE 2026-10-07; P8 DONE 2026-10-07 (offscreen review only; live checks in P9); P9 part 1 (fake server) DONE + P9a fixes FX1-FX5 DONE 2026-10-07; P9b (F6, P1-P4) DONE 2026-10-07; P9 part 2 (real device) RUN 2026-10-07 with findings V1-V5 = P9c (§7.1), Follow & Click AX5 not yet confirmed; implementation on branch feature/compass-task-flow
created: 2026-10-06
last_updated: 2026-10-07
next_step: the P9c spec-implementer pass (V1-V5, §7.1); then the P9c live re-check on the real device; the user's further feedback (input method, Follow without a click) is its own SPEC, SPEC-input-selection-and-follow.md, implemented on this branch after P9c and replacing the Follow & Click re-run (AX5 is re-checked there as Follow the Target); old-session deletion only on the user's explicit OK (U16); then the merge to main / v2.0.0 on the user's OK
related:
  - docs/compass/synthesis/ui-ux-screen-walkthrough.md (the Compass reference this SPEC adapts; screenshots in docs/compass/screenshots/)
  - docs/compass/synthesis/ui-ux-patterns.md (Compass patterns from the guide)
  - SPEC-ui-setup-task-selection.md (dashboard, Setup/Tasks tabs; Setup is unchanged here)
  - SPEC-live-settings-panel.md (live settings, settings profiles §10 — the HUD part is superseded here)
  - SPEC-result-logic.md (current Results tab — superseded here by the per-test report)
  - SPEC-gazepoint-analysis-export-parity.md (all_gaze.csv, fixations.csv, eye_geometry.csv used by the report)
  - SPEC-hud-hide-toggle.md (Hide HUD — removed here)
  - SPEC-target-size-and-motion-paths.md, SPEC-grid-cell-gap.md (options shown on the new configuration page)
---

# SPEC-compass-task-flow — Compass-style task flow

**Status: approved 2026-10-06. All decisions in §3 and in the per-part hub-decision lists are
approved. Implementation happens on branch `feature/compass-task-flow` only (U17). Every UI
phase needs an approved wireframe before implementation.**

## 1. Origin

The user wants to redesign everything after the Setup tab along the lines of Compass 3.0
(Koester Performance Research), documented in `docs/compass/` (guide corpus plus 12
screenshots of the real app, `b7401d3`). In the user's words (2026-10-06, condensed):

- The **Setup** window stays as it is.
- The **Tasks** window should work like Compass's Test List (`05-test-list.png`): it gives
  the clinician more freedom over tests and their configuration.
- Task settings are a **modal dialog** today. As settings grow, that gets hard to use.
  Settings should be a page like Compass's configuration screen (`06-aim-configuration.png`):
  the same kind of layout, but holding **our existing options**. Save/load of settings
  already exists and must be kept.
- **Results** should look like Compass's Summary and Detailed reports (`08a`, `08b`). The
  rows wanted are Error-free Target Selections, All Targets Selected, Targets Not Selected
  and All Trials. Doctors also asked for **gaze path, heat map, fixation duration, fixation
  count, saccade velocity and pupil dilation**. Also wanted: Compass's **Target Map** and the
  **Test Configuration** section showing the configuration used.
- Compass's **Preview Test** (on the configuration screen) lets the doctor see how a
  configuration looks. Its **Practice** button (on the Start screen) runs 3 practice targets
  and returns to the Start screen before the real test.

Note: the user said "v1.0.0". This SPEC is written against `main` at `b7401d3`, which is 47
commits after the `v1.0.0` tag. The features added since then (target-size presets, grid gap,
HUD hide, Display check, settings profiles) are the baseline.

## 2. Current state (research 2026-10-06, file:line in the reports)

Three read-only research passes were made. The facts below were checked against code.

**Tasks tab** (`src/ui/tasks_page.py`, `src/ui/dashboard_window.py`):
- Four fixed cards (Static Click, Grid Click, Follow & Click, Scanning Search) with Run /
  Settings / Load Settings / Analyze.
- State lives in four in-memory dicts keyed by `task_id`; nothing survives a restart.
- Run opens the modal `TaskSettingsDialog` (OK = "Start task"), then embeds an `AssessmentApp`
  in the window. A run always returns to Tasks.
- End task, Esc and normal completion all go through one `_shutdown()`. The card then says
  "Complete" even after an early end.
- Session folders are `<date>_<subject>_<task>_run<N>`, with the system date, and N resets
  daily.

**Settings:**
- *Live* settings (dwell, pacing, speed, …) are sliders in the operator panel (HUD) during a
  run, plus *structural* settings in the dialog (trials, size presets, grid rows/cols/gap,
  icon count, motion path, selection window). Some options are YAML-only (static positions,
  scanning arrangement, sound toggles, `input.mode`).
- Profiles live at `sessions/_settings/<subject>/<task>/<timestamp>.json` (schema_version 1,
  `live` + `structural` + `calibration`). They have no name. "Save for this subject" exists
  only in the HUD (an earlier user decision, S10.11).

**Recording:**
- Always on: `SessionRecorder` is created unconditionally and is used unguarded about 45
  times in `app.py`.
- The task's seed is always 0.
- No mouse input exists: `input.mode: switch` still takes its pointer from the gaze client.

**Data per run:**
- `trials.csv` has position, hit radius, onset / first-on-target / click / end times,
  `is_hit`, `is_timeout` and `attempts`.
- `metadata.json` has the target size, grid gap, geometry and display, and settings at the
  run's start.
- `session_metrics.json` has session-level fixation, saccade and pupil aggregates.
- The device-rate files are `all_gaze.csv`, `fixations.csv` and `eye_geometry.csv`.

**Not recorded today:**
- target entries;
- onset-to-first-look time;
- saccade velocity;
- per-trial pupil and its baseline;
- the planned trial count;
- the ended-early flag;
- skips (recorded as timeouts);
- pauses (they don't stop the trial clock);
- the moving target's position at selection or timeout (Follow & Click).

**Results tab:** four metric cards plus the session log, for the most recent run only. It has
no per-trial table, configuration table or charts.

**Known defects found by the research** (fixed by this redesign, because the per-task dicts go
away):
1. Changing the Subject ID doesn't clear carried values, dialog choices or the last session
   folder, so a second child can inherit the first child's tuning
   (`dashboard_window.py:304-310`).
2. Profile structural values apply to run 1 only (`:283-297`).
3. The Settings dialog doesn't pre-fill from the profile (`:202-210`).

**Gotcha for the eye metrics:** coordinate frames are mixed. Gaze is monitor-normalised,
targets are canvas-normalised, radius is in logical px, and canvas metadata is physical px.
Inter-fixation gaps are too short (median about one sample at 150 Hz) to compute saccade
velocity from amplitude/gap; I-VT on `all_gaze.csv` is needed.

## 3. Decisions

### 3.1 User decisions (2026-10-06 — final, do not re-ask)

| # | Decision |
|---|---|
| U1 | The **Setup** tab is unchanged. |
| U2 | The Tasks tab becomes a **per-subject Test List** like Compass `05`. It persists **across days** on disk, keyed by Subject ID, and reopens when the same ID is typed in Setup. |
| U3 | Tests are **instances**: the same task can be added several times with auto-numbered names, and tests can be renamed. A test is **locked after it runs** (no reconfigure, no re-run). **Copy Test** makes an identical unrun copy. **Delete Test** asks for confirmation. A status column shows each test's state. |
| U4 | Settings move from the modal dialog to a **full-page configuration screen** laid out like Compass `06`: titled group boxes, one page, footer **Preview Test / Save & Continue / Cancel**. It contains **our existing options only**. Saving and loading settings move here as a **named configuration**. |
| U5 | The **run screen has no HUD**. Its bottom bar holds **Pause (Alt-P), Skip trial, Quit (Alt-Q)** and a **one-line operator status** ("Trial 4/12 · tracking OK"), with no score or counters. Live sliders are removed from the run. The **gaze-cursor toggle** moves to the configuration page. Hide HUD goes away. A skipped trial is recorded as **skipped**, not as a timeout. |
| U6 | **Preview Test** is **mouse**-driven. It needs no tracker or calibration, records nothing, is abbreviated, and returns to the configuration page. |
| U7 | A **Start screen** ("Start <test>") comes before a recorded run, with English read-aloud instructions and **Start / Practice / Cancel**. **Practice** runs 3 trials with the same settings, driven by **gaze** (needs the tracker and a calibration), records nothing, and returns to the Start screen. |
| U8 | The run ends as in Compass: a **"Test Complete!"** dialog with Save / Save and View Report / Discard Results. **Quit** asks for confirmation, then offers Save partial / Discard. A partial run shows as **"Ended early (n/N)"**. A discarded run leaves the test **Not Done**. |
| U9 | Each test has its **own report**, opened from the Test List (View Report) and available across days. This replaces the most-recent-run Results tab. The report has a Compass-like header, a **Test Configuration** table, and a **Summary ⇄ Detailed** toggle. **Print Report** exports a PDF. **Out of scope:** Multi-Test Report and copying tables to the clipboard. |
| U10 | Summary rows: **Error-free Target Selections** (selected on the *first* gaze entry), **All Targets Selected**, **Targets Not Selected**, **All Trials**. Columns: **% (N)**, **Trial Time** (onset to selection), **Reaction Time** (onset to the *first gaze entry* into the target), **Entries**. |
| U11 | The doctors' metrics appear in the **Summary and per trial**: gaze path, heat map, fixation count, fixation duration, saccade velocity, pupil dilation. The Summary has a **Target Map** (green circle = hit, red X = miss, trial numbers) with overlay toggles for targets / gaze path / heat map, plus a whole-test eye-metrics table. The Detailed view adds per-trial metric columns; selecting a row shows that trial's gaze path. **Pupil dilation** = mean diameter (mm) plus the per-trial change from a pre-trial baseline. |
| U12 | New client-facing text is in **English only**. Traditional Chinese is a future feature. |
| U13 | A **new test starts at "Standard"** (the task defaults). The S10.3/S10.12 rules (the newest profile auto-applies; live values carry over between runs) are **retired**. To repeat a setup, use Copy Test or pick a saved Configuration Name. (Approves HA7 = HB5.) |
| U14 | **Discard Results permanently deletes** the session folder. It is guarded so only a session folder inside `sessions/` can be deleted. (Confirms HC6.) |
| U15 | **Target order differs per test**, as the user observed in Compass. Each test gets its own random seed, stored so the report can redraw it. Practice uses yet another seed. (Replaces HC1.) |
| U16 | **No import of old sessions.** The app is not in production yet, so the old session folders will be removed rather than imported. The hub deletes them only with the user's explicit OK at that moment (§7, P9), never as part of an implementer pass. (Drops HA12, 4A.10, AA17 and Part A step 8.) |
| U17 | **Branch.** This is a major update on v1.0.0, so it is implemented on its own branch, `feature/compass-task-flow` (created from `main` at `b7401d3`). The SPEC is committed there, every phase's commits go there, and `main` stays at the v1.x line. Small fixes needed on `main` meanwhile are merged into the branch, not the other way round. The branch is merged back (and released, e.g. as v2.0.0) only after P9 and the user's OK. Every implementation session must run `git switch feature/compass-task-flow` and confirm the branch before any edit. |

### 3.2 Hub decisions (approved by the user 2026-10-06)

Each part in §4 ends with its own hub decisions (HA*, HB*, HC*, HD*) and the reason for each.
The reconciliations below were made when merging the four drafts. **Where they conflict with a
part, they win.**

| # | Reconciliation | Overrides |
|---|---|---|
| R1 | **One set of names for run counts and outcome.** The test record and `metadata.json` both use `planned_trials`, `completed_trials` and `outcome` (`completed` / `ended_early`). Part A's `trials_planned` / `trials_completed` and Part D's `trials_planned` / `ended_early` are renamed to these. The test record's `status` stays `not_done` / `done` / `ended_early`. | 4A.2, 4A.3, 4D.1 X3 |
| R2 | **Run Test is not disabled by the Setup gate.** For a Not Done test it always opens the Start page, which lists the blockers and disables Start/Practice (HC2). Only the "Run Test" cell of Part A's matrix changes: the `run_blocked` asterisk and the "Run Test is off" half of AA16 are dropped. | 4A.4 matrix, HA13, AA16 |
| R3 | **Seed per test** (U15). The record gets `seed: int`, a random value in `[0, 999_999]` drawn when the test is created **and again on Copy Test**. The recorded run uses `test.seed`. Practice uses `1_000_000 + k` (HC1's practice rule kept) and Preview uses `PREVIEW_SEED` (HB8), so neither can reproduce a recorded order. `metadata.json` stores `seed`. | HC1, 4A.2, 4A.6 Copy |
| R4 | **Discard deletes** (U14): HC6 and `discard_session` exactly as 4C.8. The test-list store needs no `mark_discarded`: the record simply stays `not_done` (4A.7). Part C's `mark_saved(...)` is Part A's `record_result(...)`. | 4C.1 names |
| R5 | **No legacy import** (U16): 4A.10, HA12, AA17 and A's plan step 8 are void. Part D's builder still degrades gracefully on folders without the new fields (4D.9), for QA via the CLI. | 4A.10 |
| R6 | **The new `trials.csv` columns** are `is_skipped` (4C), plus `entries`, `end_x`, `end_y` and `slot_index` (4D.4). There is **no `outcome` column**: the report derives it from `is_hit` / `is_timeout` / `is_skipped` (resolves 4D X2). All columns are added in one commit. | 4D.1 X2 |
| R7 | **The configuration a run used** is `metadata.json -> settings = {config_name, live, structural}`, **complete** for the task (HB12; live values no longer change mid-run, 4C.7). There is no separate `config_snapshot.json` (resolves 4D X1). The report's configuration table reads `metadata.settings` plus the resolved fields already in metadata. | 4D.1 X1 |
| R8 | **Pre-roll:** a recorded run shows a blank canvas for **≥ 500 ms before trial 1** (recorded), so trial 1 has a pupil baseline (resolves 4D X4). Practice and Preview don't need it. | 4C.4/4C.5 |
| R9 | **The test record gains `evaluator: str`** (HD14). `notes` is one field shared by the configuration page (4B) and the report (4D). Name, evaluator and notes are editable in every state. | 4A.2, 4D.1 X5 |
| R10 | **Test Name rule:** 1–60 characters, unique per subject (case-insensitive), validated by `subject_tests.validate_test_name` everywhere. Part B's 40-character limit is replaced. Configuration Name keeps a 40-character limit. | 4B.2, 4B.3 |
| R11 | **Navigation:** the top nav becomes `1 · Setup / 2 · Tests`. "3 · Results" and `ResultsPage` are retired once the report ships (HD17). Nav is locked on every sub-page (configure, start, practice, run, report) through `DashboardWindow._set_nav_locked`. | 4A.7, HD17 |
| R12 | **Part names inside the drafts.** In §4, "4A" = Test List, "4B" = configuration page + Preview, "4C" = Start / Practice / run / run end, "4D" = report. A few sentences inside the parts still say "Part X". Read them through this mapping. | — |

## 4. Design

The four parts were drafted in parallel by research agents (2026-10-06), checked by the hub
against `b7401d3`, and merged here. `file:line` references are at `b7401d3`. §3.2 wins over
anything below.

## 4A. Per-subject Test List and its persistence

Verified against `b7401d3`. Paths are repo-relative. U1-U12 are taken as given.

### 4A.1 Scope and files

Replaces the Tasks tab (`src/ui/tasks_page.py`, 273 lines) and every per-task in-memory dict in `DashboardWindow`.

| File | Change |
|---|---|
| `src/engine/subject_tests.py` (new, Qt-free) | Test record, store, naming rules, action matrix, legacy import |
| `src/engine/task_info.py` (new, Qt-free) | `TASK_INFO` moved here from `tasks_page.py:29-34`; label "Grid Click (3×3)" becomes "Grid Click" (rows/cols are configurable). `results_page.py:41,194` re-imports it. |
| `src/engine/session_naming.py` | add `safe_subject_dirname()` (4A.9) |
| `src/ui/test_list_page.py` (new) | `SubjectTestListPage`, replaces `TasksPage` |
| `src/ui/add_test_dialog.py` (new) | `AddTestDialog` |
| `src/ui/dashboard_window.py` | delete `_task_overrides`, `_task_live_overrides`, `_task_selected_profile`, `_task_session_dirs` (`:78-101`), `_resolve_settings`, `_refresh_settings_badges`, Load Settings (`:214-374`). File is 535 lines today, over the 500 rule; this change shrinks it. |
| `src/data/schema.py`, `src/app.py` | `test_id` / `test_name` in metadata (4A.7) |
| `src/ui/wtmh_theme.py` | selected-row and bold styling for `QTableWidget` (`:427-445` is explicitly "read-only, no ::item states") |

Class names avoid a `Test*` prefix so pytest does not try to collect them when tests import them.

### 4A.2 On-disk model

```
<output_root>/_tests/<subject_dirname>/<test_id>.json          one file per test
<output_root>/_tests/<subject_dirname>/_deleted/<test_id>.json soft-deleted records (4A.6)
```

`output_root` is `recording.output_root` (same source as `setup_page.py:336`). Add `"_tests"` to the dirname tuple in `known_subject_ids` (`settings_profile.py:98`) so a subject that only has tests is offered by the Setup completer. `sessions/` is already gitignored (PHI).

Record (JSON, indent 2, UTF-8):
```
{ "schema_version": 1,
  "test_id": "t_3fa9c01b2e",          // "t_" + 10 hex, collision-checked against the folder
  "subject_id": "TESTING",            // verbatim, stripped; authoritative (folder name is only a locator)
  "name": "Grid Click 1",
  "task_id": "click_grid",
  "created_at": "2026-10-06T15:40:12+08:00",   // local time + offset, as settings_profile.py:270,283
  "origin": "created",                // created | copied | imported
  "configuration": {"name": "Standard", "structural": {}, "live": {}},
  "notes": "",
  "status": "not_done",               // not_done | done | ended_early
  "completed_at": null,               // local ISO, set by record_result
  "trials_planned": null, "trials_completed": null,
  "session_dir": null }               // folder NAME under output_root, never an absolute path
```

- **Configuration is a snapshot, never a reference.** `structural` and `live` have the same shapes as a settings profile (`settings_profile.py:279-287`), so `deep_merge` and `apply_live_values_to_config` keep working. Editing or deleting a saved configuration later cannot change an existing test. 4B owns the keys; readers ignore unknown ones, so no schema bump.
- **Standard means "task defaults".** Empty `structural`/`live` with name "Standard". Any other name carries a full snapshot written by 4B. This assumes 4B keeps the Compass rule that an edited Standard must be renamed on save.
- **What actually ran** is `metadata.json -> settings` of the linked session (`app.py:420-429`), not this record. The report's Test Configuration table (Part D) reads that.
- **Atomic writes.** There is no atomic writer in `src` today (`settings_profile.py:288`, `local_state.py:47`, `recorder.py:211` all use `write_text`). Add `_atomic_write_json(path, payload)`: write `<name>.tmp` in the same folder, flush + `os.fsync`, then `os.replace`; on `PermissionError` retry 5 times at 40 ms (antivirus/OneDrive on Windows); on final failure raise `TestStoreError`. The reader only reads `t_*.json`, so a stray `.tmp` is never listed.
- **Disk is the source of truth.** Every action writes first, then updates the table. A failed write shows a message ("Could not save <name>: <reason>. Nothing was changed.") and reloads from disk.
- **Reader is tolerant** (same rule as `settings_profile.py`): an unreadable or non-dict file, a missing `test_id`, or a `task_id` not in `TASK_REGISTRY` is skipped and counted. `list_tests` returns `TestListLoad(tests, unreadable: list[Path])`. A subject mismatch (casefold) with the requested ID is skipped silently, so two folders that sanitise to the same name can never mix. An unknown `status` reads as `done` if `session_dir` is set, else `not_done`.
- Unknown keys are dropped on rewrite. Acceptable: `sessions/` is per machine.

### 4A.3 Module API (`src/engine/subject_tests.py`)

```
@dataclass SubjectTest        # fields as the record above
list_tests(output_root, subject_id) -> TestListLoad            # sorted by (created_at, test_id)
create_test(output_root, subject_id, task_id, *, name=None, configuration=None) -> SubjectTest
copy_test(output_root, subject_id, test_id) -> SubjectTest
rename_test(output_root, subject_id, test_id, new_name) -> SubjectTest    # any state
update_test(output_root, subject_id, test_id, *, configuration=None, notes=None) -> SubjectTest
delete_test(output_root, subject_id, test_id) -> None                      # soft, 4A.6
record_result(output_root, subject_id, test_id, *, session_dir, trials_planned,
              trials_completed, completed_at=None) -> SubjectTest        # called by 4C on Save
next_default_name(task_id, existing_names) -> str
validate_test_name(name, existing_names, *, exclude=None) -> str | None  # error text or None
allowed_actions(test: SubjectTest | None, *, run_blocked: bool) -> frozenset[str]
import_legacy_sessions(output_root, subject_id) -> int                     # 4A.8
```

Lock rules live here, not only in the UI (defence in depth). `update_test(configuration=...)` and a second `record_result` raise `TestLockedError` unless `status == "not_done"`. Name and notes stay editable in every state (Compass lets the report edit both).

`record_result` sets `status = "done"` when `trials_completed >= trials_planned`, else `"ended_early"`. `completed_at` defaults to local now. `session_dir` is stored as `Path(session_dir).name` after checking its parent is `output_root`. 4C must supply `trials_planned` (`len(task.targets)`, `app.py:517,947`) and `trials_completed` (rows written to `trials.csv`, `app.py:1015`; skipped trials count as recorded).

### 4A.4 The Test List page (`SubjectTestListPage`)

Layout follows `05-test-list.png`. Title is "Test List for <Subject ID>". Inside the `wtmhDashboard` scope (reuse `STYLESHEET`).

- **Table** (`QTableWidget`, already themed at `wtmh_theme.py:430-445`, precedent `setup_page.py:719`). Single-row selection, no cell editing except the rename path. Attribute `self.table`, object name `wtmhTestTable`.

| # | Column | Content |
|---|---|---|
| 0 | Test Name | `name` (rename in place, 4A.6) |
| 1 | Task | `TASK_INFO` display name |
| 2 | Configuration | `configuration.name` |
| 3 | Status | `Not Done` / `Done` / `Ended early (7/12)`; suffix ` · data missing` if a done test's `session_dir` folder no longer exists |
| 4 | Date Complete | `YYYY-MM-DD` from `completed_at` (tooltip: full local time), or `—` |

- **Bold** on every cell of a `not_done` row (Compass: "rows for tests not yet run are bold").
- **Sorting:** header click sorts. Default is creation order. Test Name uses a natural key (digits as numbers, case-insensitive) via a `QTableWidgetItem` subclass with `__lt__`; Date Complete sorts on the ISO string with `—` first. Selection is held by `test_id`, so it survives sort and reload.
- **Right-hand button column**, vertically centred, `self.add_button`, `configure_button`, `run_button` (primary `wtmhPrimary`), `report_button`, `copy_button`, `delete_button` (others `wtmhGhost`). No Multi-Test Report button (U9 out of scope).

| Selected state | Add New Test | Configure Test | Run Test | View Report | Copy Test | Delete Test |
|---|---|---|---|---|---|---|
| nothing selected | on | off | off | off | off | off |
| Not Done | on | on | on* | off | on | on |
| Done | on | off | off | on | on | on |
| Ended early | on | off | off | on | on | on |

\* `Run Test` is also off while `run_blocked` is set. The dashboard passes the reason from Setup's missing-requirements list (`setup_page.py:1027`, make a public `missing_requirements()`), shown as the button tooltip: "Still needed: tracker connected; calibration." Viewing, adding, configuring, copying, deleting and reporting need no tracker. `View Report` is also off when the data folder is missing.
Disabled buttons stay visible and grey, never hidden (Compass principle 3).

- **Footer:** `← Back to Setup / recalibrate` (the existing `backToSetupRequested` behaviour, `tasks_page.py:212-215`) and a muted label "Changes are saved automatically." No End Client Session or Save Client File: there is no client file.
- **Keyboard:** Delete = Delete Test; Enter or double-click on any cell except Test Name = primary action (Run Test if Not Done, else View Report); F2 or double-click on Test Name = rename. Run leads to the Start screen (U7), so a stray double-click records nothing.
- **Empty states:** no Subject ID typed (the nav button reaches this tab without the Continue gate, `dashboard_window.py:163-166,175-181`): table replaced by "Enter a Subject ID in Setup." and every button off. A subject with no tests: "No tests yet. Choose Add New Test." If `TestListLoad.unreadable` is non-empty: a muted line "N test file(s) could not be read and are hidden: <folder>".
- **Signals out:** `configureRequested(test_id)`, `runRequested(test_id)`, `reportRequested(test_id)`, `backToSetupRequested()`. Add, Copy, Delete and rename are handled inside the page by calling `subject_tests`; they do not need the dashboard. `set_subject(subject_id, output_root)` reloads from disk; the dashboard calls it from `_on_continue_to_tasks` and `_go_to_tab(_TASKS_INDEX)` (a reload is a handful of tiny files).

### 4A.5 Add New Test: recommendation = small modal dialog

Compass needs a page because it has 8 tests in 3 families and a transfer list. We have 4 tasks and no families. A page adds a screen, a Back path and state for no gain; a bare menu hides the one-line descriptions clinicians use to choose.

`AddTestDialog`: a list of the 4 tasks (bold name, muted description from `TASK_INFO`), a "How many" spin box (1-10, default 1, matches Compass "same test several times"), and Add / Cancel. Double-click a task = Add one. On Add the page creates the tests with default names, selects and scrolls to the last one. Nothing opens automatically (Compass does not either).

New tests start from Standard (see HA7).

### 4A.6 Name, Copy, Delete semantics

- **Names.** Default `"<Task display name> <N>"` with the smallest free N for that task. Unique per subject, compared case-insensitively on the trimmed value. Rules: 1-60 characters, no control characters, not blank. Names are never used in folder names, so no filename restriction (PDF export sanitises its own file name). The same `validate_test_name` serves the in-list editor and 4B's Test Name field; both must show the returned text inline.
- **Rename** in place (F2) is allowed in every state, including Done: it is the only way to rename a locked test. The session's `metadata.json` keeps the name it had at run time; the report header uses the record's current name.
- **Copy Test** (any state): same `task_id` and a deep copy of `configuration`; `status = not_done`, `session_dir`/`completed_at`/trial counts empty, `notes` cleared, `origin = "copied"`, new id. Name: if the source name matches `<Task name> <digits>`, the next default number (copying "Grid Click 1" gives "Grid Click 2"); otherwise `"<name> (copy)"`, then `"(copy 2)"`. The copy is appended and selected.
- **Delete Test** (any state), always with a confirmation. Text for a Done test: "Delete '<name>' from this list? Its recorded data in the sessions folder is kept." Default button is Cancel; buttons read "Delete" and "Keep". The record is **moved** to `_deleted/`; recorded session folders are never touched. There is no restore command in v1 (copy the file back by hand). Not Done tests use the same path.

### 4A.7 Linking runs, results and reports

- Add to `SessionMetadata` (`schema.py:163`): `test_id: str | None = None`, `test_name: str | None = None` (additive, `schema_version` not bumped, same precedent as `settings`). `AssessmentApp.__init__` gets matching kwargs (default `None` so the standalone `--task X --gui` path is unchanged) and passes them at `app.py:397`. The dashboard passes the record's values.
- Run is started from the **record**, never from Setup's live field: `AssessmentApp(subject_id=test.subject_id, task_id=test.task_id, structural_overrides=test.configuration["structural"] or None, live_overrides=test.configuration["live"] or None, test_id=..., test_name=...)`. A defensive check refuses if `test.subject_id.casefold() != setup_page.subject_id().casefold()`.
- After the data is written, 4C's Save calls `record_result(...)`. Discard calls nothing (the test stays Not Done) and removes the discarded session folder (4C). Quit then Save partial calls `record_result` with `trials_completed < trials_planned`.
- View Report: `reportRequested(test_id)` -> dashboard loads the record, resolves `Path(output_root) / session_dir`, and opens Part D's report with `test.subject_id` (fixes the old Analyze bug that labelled an old session with the newly typed ID, `dashboard_window.py:490`).
- **Accepted gap:** between `recorder.close()` (`app.py:1031`) and the user pressing Save, a crash leaves an orphan folder and a Not Done test. The data is intact and carries `test_id` in `metadata.json`, so a later "rebuild from disk" tool is possible. Not built here.
- Nav buttons are disabled while any test sub-page (configure, start, run, report) is showing; each part calls one `DashboardWindow._set_nav_locked(bool)`. Today only the Setup button is disabled during a run (`dashboard_window.py:437`).

### 4A.8 Subject change and the leaking defect

Defect: `_on_subject_id_changed` clears only `_task_selected_profile` (`dashboard_window.py:304-310`); the other three dicts survive and "carried" beats the new subject's profile (`settings_profile.py:215-222`). Fix by construction: no per-subject or per-task state remains in `DashboardWindow`. The list is rebuilt from disk on every entry to the tab, and a run takes everything from its own record. `subjectIdChanged` (fires per keystroke, `setup_page.py:461`) is no longer connected to anything that does work. The Setup page and the Test List are never visible together, so no live re-bind is needed.

### 4A.9 Subject ID sanitising

There is none today (`settings_profile.py:47-59`, `setup_page.py:149`, `session_naming.py:30`): an ID such as `..\x` or `A/B` becomes a real path.

`safe_subject_dirname(subject_id) -> str`: NFC-normalise; replace each of `<>:"/\|?*` and control characters with `_`; strip trailing dots and spaces; prefix `_` if empty or a Windows device name (CON, PRN, AUX, NUL, COM1-9, LPT1-9, with or without an extension); cut at 80 characters. If the result differs from the input, append `~` + first 6 hex of SHA-1 of the original, so "A/B" and "A_B" never share a folder. **Ordinary IDs (letters, digits, space, `_ - .`, everything on disk today) come back unchanged**, so existing `_settings/` and `_calibrations/` folders still match. Use it in: `_tests`, `subject_settings_dir`, `_subject_calibration_dir`, and `next_run_number` (session folder names). `metadata.json` and the record keep the verbatim ID. Setup does not reject IDs (U1). Known limit: an ID with illegal characters shows in the completer as its sanitised folder name.

Windows paths are case-insensitive, so "jeffry" and "JEFFRY" share one list; the record keeps the ID as first typed.

### 4A.10 Legacy sessions — VOID (U16 / R5: no import; kept for the record)

About 60 folders from v1.0.0-era runs exist (`sessions/<date>_<subject>_<task>_run<N>`). Their `metadata.json` has `subject_id`, `tasks`, `started_ns`, `settings` (`app.py:397-429`) but no test id, planned count, or ended-early flag.

`import_legacy_sessions`: runs once, only when `_tests/<subject_dirname>/` does not yet exist. For each session folder whose `metadata.json` `subject_id` matches (casefold), create a record: `origin = "imported"`, `status = "done"`, `completed_at` from `started_ns`, `trials_completed` from `trials.csv` rows, `trials_planned = null`, `session_dir` = folder name, `configuration = {"name": "Imported", "structural": {}, "live": {}}`, names "<Task> N" in `started_ns` order. Old folders are never modified. Status text for these rows: "Done (imported)". Part D must tolerate their missing fields (no entries, no skips, no pupil baseline). A wrong import is harmless: Delete Test only removes the record.

#### Hub decisions proposed (user must approve)

- **HA1** One JSON file per test, not one list file per subject: failure is isolated to one test, no read-modify-write race, matches the per-file tolerant style of `settings_profile.py`.
- **HA2** Add New Test is a small modal dialog (4 tasks with descriptions, quantity spin), not a page or menu (4A.5).
- **HA3** Two columns, Status and Date Complete, instead of Compass's single mixed "Date Complete": sortable by either, and "Ended early (7/12)" has a home. Column "Task" replaces Family/Skill.
- **HA4** No Multi-Test Report, End Client Session or Save Client File; saving is automatic and the footer says so.
- **HA5** Single-row selection only; no multi-select delete.
- **HA6** Default name uses the smallest free number; names unique per subject, case-insensitive; rename in place allowed for every state, including Done.
- **HA7** A new test always starts from Standard (task defaults). The old "newest saved profile auto-applies" and "carry last run's values" rules (S10.3, S10.12) are retired: Copy Test and picking a named configuration on the Configure page replace them. This reverses earlier user decisions, so it needs an explicit yes.
- **HA8** Copy name = next number for auto-named tests, else "<name> (copy)"; notes are not copied.
- **HA9** Delete is soft: the record moves to `_deleted/`; recorded session data is never deleted by the app. Confirmation defaults to Cancel.
- **HA10** "Date Complete" is the system local time at save, not Setup's Assessment Date (which stays in `metadata.json`), so it reflects when the run happened.
- **HA11** Subject IDs are made path-safe by sanitising with a hash suffix, not rejected; applied to all four folder sites (4A.9).
- **HA12** Legacy sessions are imported once per subject (4A.10), as a separable last phase. Drop it if the answer to the open question is no.
- **HA13** The Test List is usable without tracker or calibration; only Run Test is gated, with the reason in its tooltip. Setup's Continue gate is unchanged.
- **HA14** The test record is created at Add time (not at first run), so the list survives before any run; the crash gap in 4A.7 is accepted.

#### Acceptance criteria

- **AA1** Create writes `<root>/_tests/<dirname>/<test_id>.json` with every field in 4A.2 and `schema_version` 1; `list_tests` returns it equal to what was written.
- **AA2** With `os.replace` forced to raise, the previous file is byte-identical, no `.tmp` is listed, and `TestStoreError` surfaces; a `PermissionError` on the first two attempts still succeeds.
- **AA3** Default names run "Grid Click 1", "Grid Click 2"; after deleting 1, the next add is "Grid Click 1". Rename to an existing name (any case, extra spaces) is rejected with text; blank and >60 characters are rejected.
- **AA4** Tests of subject A never appear for subject B. "jeffry" and "JEFFRY" load the same list.
- **AA5** `update_test(configuration=...)` and a second `record_result` raise `TestLockedError` for Done and Ended early; rename and notes succeed.
- **AA6** Copy of a Done test yields a new id, `not_done`, empty session/date/counts/notes, deep-equal configuration, the 4A.6 name; mutating the copy's configuration does not change the original.
- **AA7** Delete moves the record to `_deleted/`; the linked session folder and all its files are unchanged; the list no longer shows it.
- **AA8** `allowed_actions` equals the 4A.4 matrix for {none, not_done, done, ended_early} x {run_blocked false/true}, parametrised.
- **AA9** After recreating the page and `set_subject` with the same ID, the table is identical: Done shows its date, Ended early shows "Ended early (7/12)", Not Done rows are bold.
- **AA10** Switching Subject ID A -> B -> A: B's list contains none of A's tests; a run started for a B test receives B's subject id and B's configuration only; `DashboardWindow` has no `_task_overrides`, `_task_live_overrides`, `_task_selected_profile` or `_task_session_dirs`.
- **AA11** After a run started from a test, its `metadata.json` has `test_id` and `test_name`; after Save the record's `session_dir` equals that folder's name; View Report resolves it; a missing folder disables View Report and shows "data missing".
- **AA12** Header click on Test Name orders "Grid Click 2" before "Grid Click 10"; selection survives sort and reload.
- **AA13** IDs `..\x`, `A/B`, `CON`, `x.`, and 200 characters all map inside `<output_root>/_tests/`; "A/B" and "A_B" get different folders; `TESTING` still maps to `_settings/TESTING`.
- **AA14** A garbage `.json` in a subject folder: the others load, the page shows the "could not be read" line, no exception.
- **AA15** With an empty Subject ID the page shows the empty state, every button is off, and no file or folder is created.
- **AA16** With no tracker connected, Add, Configure, Copy, Delete and View Report work; Run Test is off with a "Still needed:" tooltip.
- **AA17** (if HA12) First open of a legacy subject creates one Done record per matching folder, ordered by start time; a second open creates none; folders are byte-unchanged.

#### Plan steps

Each step is one implementer pass. "WF" = needs an approved wireframe first.

1. **Path safety.** `safe_subject_dirname` plus the four call sites and tests (AA13). No UI. No WF.
2. **Task info.** Create `src/engine/task_info.py`, move `TASK_INFO`, fix the grid label, re-point `results_page.py`. No WF.
3. **Store.** `subject_tests.py` with atomic writer, names, lock rules, `allowed_actions`, tests (AA1-AA8, AA14). No WF.
4. **Metadata link.** `test_id`/`test_name` in `SessionMetadata` and `AssessmentApp`; test (AA11 first half). No WF.
5. **Wireframe** `docs/wireframes/test-list.md`: page, Add dialog, delete confirm, in-place rename, empty / blocked / unreadable states. **WF gate: user approval.** Replaces the stale `tasks.md`.
6. **Page.** `test_list_page.py`, `add_test_dialog.py`, theme styling, dashboard wiring, deletion of the old state and badge code. Until Parts B and C land, bridge: Configure opens the existing `TaskSettingsDialog` and stores its overrides into the record; Run uses the current embedded run (HUD still present) and, on finish, calls `record_result` with `len(task.targets)` / `len(task.trials)`. The bridge is deleted when B and C replace those flows. Tests AA9, AA10, AA12, AA15, AA16.
7. **Live check** with the user via qt-mcp, maximised: Add x3, rename, copy, delete, restart the app, switch subject. Real tracker only for Run gating.
8. **Legacy import** (HA12, optional, last). AA17.

#### Open questions

1. Do any real subjects recorded with v1.0.0 (or later) need to appear in the new Test List? If no, drop step 8 and HA12; if yes, import is needed before the first real sitting on the new build.

## 4B. Configuration page and Preview Test

Honours U1-U12. Paths relative to the repo; `file:line` at HEAD b7401d3. Layers: (L) = live registry, (S) = structural registry. The operator no longer sees that split: with the HUD gone (U5) every option is set on this page before the run and baked in at start.

### 4B.1 Page anatomy

Replaces the modal `TaskSettingsDialog` inside the dashboard (`dashboard_window.py:202-210`). New widget `TaskConfigPage` (`src/ui/task_config_page.py`) is a persistent page in the dashboard `QStackedWidget`. It is opened from Configure Test on the Test List; Save & Continue and Cancel both return to the Test List.

```
Grid Click 1 Configuration                       <- wtmhPageTitle; name = saved test name
Grid Click · Subject TESTING                     <- wtmhMuted
+- scroll area (wtmhConfigScroll) ----------------------------------------------------+
| COL A (identity, Feedback)   | COL B (what is shown, timing)  | COL C (how it selects) |
+----------------------------------------------------------------------------------------+
|  [ Preview Test ]   [ Save & Continue ]*   [ Cancel ]    footer-message (muted)          |  <- pinned, outside the scroll area
```

- Each group is a `wtmhCard` `QFrame` with a `wtmhSectionTitle` label, the dashboard convention (`task_settings_dialog.py:93-114`), not `QGroupBox` (no QSS for it in `wtmh_theme.py`).
- 3-column `QGridLayout`, left-aligned, content max width about 1500 px, equal column stretch (Compass 06 hugs the left; ours uses the width).
- Column A: **Test** card (Test Name, Configuration Name + line "Modified from Standard" + ghost [Reset to defaults], Number of Trials, Notes), then **Feedback** card.
- Column B: **Target** (or **Icons**) card, the task-specific card (**Grid Layout** / **Motion**), then **Timing**.
- Column C: **Selection (Dwell)** card, then **Gaze Smoothing** card.
- Widgets follow the Compass principle: one-of = radio buttons; any-combination or on/off = check boxes; numbers = the existing `SliderSpinRow` (`slider_spin.py:15`). Size is one-of by clinical design (SPEC-target-size §11.3 B1: one size per test), so it is a radio group, deliberately unlike Compass's multi-size check boxes.
- `objectName` convention for qt-mcp and tests: `cfg_` + key with dots as underscores (`cfg_dwell_threshold_ms`); radio items append the value (`cfg_target_size_small`). Fixed names: `cfgTestName`, `cfgConfigName`, `cfgNotes`, `cfgPreview`, `cfgSave`, `cfgCancel`, `cfgReset`.
- Tooltips: every control reuses `LiveSetting.tooltip` (`settings_registry.py:94-200`); structural controls get new plain-language tooltips (same convention).
- Not shown, by decision: Input Device and Test Language (no such options, U4, U12; the tracker is always the GP3 HD and is recorded automatically).

### 4B.2 Controls per task

Defaults come from the merged task config (`initial_live_values` `settings_registry.py:300-328`, `initial_structural_values` `:396-411`), never from registry fallbacks. Example trap: smoothing alpha is **0.22** in `default.yaml:37`, but the fallback `_SMOOTHING_DEFAULTS` says 0.35 (`settings_registry.py:280`).

#### Common to all four tasks

| Card | Control (label) | Widget | Key (layer) | Range / choices | Default |
|---|---|---|---|---|---|
| Test | Test Name | QLineEdit | test entry | 1-40 chars, unique per subject (case-insensitive) | "<Task> N" (Test List section) |
| Test | Configuration Name | editable QComboBox | config name (4B.4) | Standard + this subject's saved names | Standard |
| Test | Number of Trials | SliderSpinRow int | `trials` (S) | 1-60 step 1 | static 32, grid 18, follow 6, scanning 6 |
| Test | Notes | QPlainTextEdit | test entry | free text | empty |
| Feedback | Show gaze cursor | QCheckBox | `dwell.visual_cursor` (L, moved from HUD, U5) | on/off | on |
| Feedback | Show dwell progress ring | QCheckBox | `dwell.progress_ring` (L) | | on |
| Feedback | Show instant on-target ring | QCheckBox | `dwell.instant_feedback` (L) | | on |
| Feedback | Play hit sound | QCheckBox | `feedback.hit_sound` (S, **new bool kind**, HB3) | | on |
| Feedback | Play miss sound | QCheckBox | `feedback.miss_sound` (S, new) | | on |
| Selection (Dwell) | Dwell threshold (ms) | SliderSpinRow int | `dwell.threshold_ms` (L) | 300-2000 / 50 | 800 |
| Selection (Dwell) | Refractory period (ms) | SliderSpinRow int | `dwell.refractory_ms` (L) | 0-2000 / 50 | 500 |
| Selection (Dwell) | Jitter tolerance (px) | SliderSpinRow int | `dwell.jitter_tolerance_px` (L) | 0-100 / 5 | 40 (the only px control left, SPEC-target-size §11.2 B3) |
| Gaze Smoothing | Smoothing enabled | QCheckBox | `dwell.smoothing.enabled` (L) | | on |
| Gaze Smoothing | Smoothing alpha | SliderSpinRow float | `dwell.smoothing.alpha` (L) | 0.05-1.0 / 0.05 | 0.22; **greyed while Smoothing enabled is off** |
| Timing | Trial timeout (ms) | SliderSpinRow int | `task.timeout_ms` (L) | 1000-20000 / 500 | static 8000, grid 8000, follow 12000, scanning 10000 |
| Timing | Inter-trial interval (ms) | SliderSpinRow int | `task.inter_trial_interval_ms` (L) | 0-3000 / 100 | 800 / 800 / 1000 / 900 |

Units stay ms/px as in the registries: no conversion layer, stored values unchanged (HB2).

#### Task-specific

| Task | Card | Control | Widget | Key (layer) | Choices / range | Default |
|---|---|---|---|---|---|---|
| click_static | **Target** | Target size | radio x3, each "Small — 3° (≈123 px)" (px for this monitor, as `task_settings_dialog.py:180-197`) | `target.size` (S) | small / medium / large | medium |
| click_grid | **Target** | Target size | radio x3 | `target.size` (S) | same | medium |
| click_grid | **Grid Layout** | Grid rows | SliderSpinRow int | `grid.rows` (S) | 2-6 / 1 | 3 |
| click_grid | **Grid Layout** | Grid cols | SliderSpinRow int | `grid.cols` (S) | 2-6 / 1 | 3 |
| click_grid | **Grid Layout** | Cell gap | radio x3: Standard / Wide — 1° (≈41 px) / Extra wide — 2° (≈82 px) | `grid.gap` (S) | standard / wide / extra_wide | standard |
| click_grid | **Grid Layout** | amber hint (`wtmhAlertWarning`) | QLabel | not an option | recomputed on size/rows/cols/gap | hidden when it fits |
| follow_moving | **Target** | Target size | radio x3 | `target.size` (S) | same | medium |
| follow_moving | **Motion** | Movement path | radio x5 (labels from `MOTION_PATH_CHOICES`, `settings_registry.py:41-47`) | `motion.path` (S) | circular / horizontal / vertical / diagonal_tlbr / diagonal_trbl | circular (YAML wins over the registry's "horizontal") |
| follow_moving | **Motion** | Target speed (frac/s) | SliderSpinRow float | `motion.speed_frac_per_s` (L) | 0.05-1.0 / 0.05 | 0.20 |
| follow_moving | **Timing** (extra row) | Selection window (ms) | SliderSpinRow int | `motion.select_window_ms` (S) | 500-5000 / 100 | 2500 |
| scanning | **Icons** | Icon size (the visible icon) | radio x3 | `layout.size` (S) | small / medium / large | medium |
| scanning | **Icons** | Number of icons | SliderSpinRow int | `layout.n_icons` (S) | 2-8 / 1 | 4 |
| scanning | **Icons** | amber hint "Icons will be shrunk to ≈ N px to fit K icons" | QLabel | not an option | recomputed | hidden when it fits |

#### Currently YAML-only options (recommendations, HB3)

| Option | Recommendation | Why |
|---|---|---|
| `feedback.hit_sound`, `feedback.miss_sound` | **Expose** (above) | Sounds can overwhelm a sensory-sensitive child (`app.py:95-99`); they are read once at construction (`app.py:106-110`), so they are structural; `GuiFeedback` reads `config["task"]["feedback"]` (`app.py:508-509`). |
| `feedback.particles` | Not exposed | Dead key: nothing reads it; flag for removal in the Implementation notes. |
| `input.mode` | Not exposed | Compass's Input Device/Selection Method have no counterpart; `eye` only. |
| `target.positions`, `layout.arrangement`, `grid.margin_frac`, `layout.margin_frac`, `theme` | Not exposed | Design constants of the task, not clinical knobs; no new options (U4). |

Not-applicable controls are simply absent from that task's page (a page is per task). Within a page nothing is ever hidden, only greyed (4B.3).

### 4B.3 Dependent controls, validation, hints

- Greyed in place, never hidden: Smoothing alpha follows Smoothing enabled. That is the only dependency in our option set. Add new ones the same way (a `depends_on` field in the layout spec).
- Shrink hints reuse the dialog's logic (`task_settings_dialog.py:213-283`) via pure functions extracted into `src/engine/target_size.py` (`grid_fit_hint`, `icon_fit_hint`, next to `estimate_grid_geometry`), so the dialog and the page cannot disagree. The canvas estimate is the screen's available area, as in the dialog (`:164-172`).
- Validation, shown as a muted reason in the footer message while **Save & Continue is disabled** (state shown by enable/disable, Compass principle 3): Test Name empty, over 40 chars, or already used by another test of this subject; Configuration Name empty, over 40 chars, or "Standard" with modified values (see 4B.4).
- "Modified" line under Configuration Name: `Modified from "<name>"` once any value differs from the loaded configuration (uses the same comparison as the forced-rename rule).

### 4B.4 Configuration Name and stored configurations

**Concept.** A configuration is a named set of option values (live + structural) for one task, per subject (never global: SPEC-live-settings-panel §10.3 "protocol hazard"). **Standard** is the task's defaults, i.e. `configs/default.yaml` merged with `configs/tasks/<task>.yaml`; it is computed, never stored, and reserved (case-insensitive).

**Storage.** Same location and file-per-save rule as today (`settings_profile.py:56-59`, `:247-289`, S10.12.3): `sessions/_settings/<subject>/<task>/<local date>_<local time>.json`. Changes:
- New optional field `"name"`. `PROFILE_SCHEMA_VERSION` 1 -> **2** (`:42`): a v1 reader would still work (it ignores unknown keys), but v2 documents that `name` exists. `load_settings_profile_file` (`:130-139`) builds its return dict from a fixed key list, so it must add `"name"` or callers never see it.
- `save_settings_profile(..., name="")`; the `live` block holds only keys that apply to the task (`LiveSetting.applies`), no longer always all 11 (today it writes `motion.speed_frac_per_s` even for static tasks); `structural` is **complete** for the task (every control), no longer only the keys the dialog touched.
- Nothing is overwritten or deleted. A name resolves to its **newest** version by `saved_at` (the ordering `list_settings_profiles` already uses, `:142-175`); older versions stay on disk as history.
- New pure helper `list_named_configurations(output_root, subject, task) -> list[NamedConfig(name, saved_at, path, live, structural)]`: one entry per distinct effective name. A v1 file has no name, so its effective name is `Saved MM/DD HH:MM` (`format_saved_at`, `settings_registry.py:352-366`), keeping every old profile reachable. Combo order: Standard, then names newest-first.

**Behaviour.**
1. Opening a **new** test: Configuration Name = Standard, all values = defaults (HB5: no silent carry-over of the last child's tuning).
2. Selecting a name in the list loads **all** values from it; keys the file lacks fall back to defaults, unknown keys are ignored (`apply_live_values_to_config`, `settings_registry.py:369-393`; the legacy px-radius fallback in `_initial_structural_value` still applies). If the form has unsaved edits, ask "Replace your edits with configuration '<name>'?" first. Test Name and Notes are never touched.
3. Typing a text that is not in the list = a new name for the current values (no load).
4. **Save & Continue** always stores the snapshot in the test entry: `config = {"name", "live", "structural"}` (complete, task-applicable keys; the Test List and report sections read this). A profile file is **also** written when the name is not Standard and either the name is new or the values differ from its newest version.
   - Name = Standard and values differ from defaults: forced rename dialog ("Standard cannot be changed. Save these settings as:" + name field, default "Custom 1"); Cancel stays on the page.
   - Existing name and values differ: dialog "'<name>' already exists with different settings." [Update '<name>'] (new version file, same name) [Save under a new name...] [Cancel]. Earlier tests keep their own snapshots (U3), so nothing they ran under changes.
   - Standard and untouched: no file is written.
5. **Reset to defaults** (ghost button under Configuration Name): Configuration Name = Standard and every value = default; Test Name and Notes unchanged. Unsaved until Save & Continue.
6. No delete or rename action for configurations (kept from S10.12.3); a new name is the rename.
7. Locked tests: **Configure Test is disabled** on the Test List for a Done / Ended-early test (Compass; the config table lives in the report, U9), so the page has no read-only mode (HB7). Defensive guard only: before writing, Save re-reads the entry and, if its status is no longer Not Done, shows "This test has already been run and can't be changed." and writes nothing. A **Discarded** run leaves the test Not Done, so it can be reconfigured and re-run (U8).

**Retired by this section.** The HUD "Settings profile" card (Save for this subject, Reset to defaults, source line; `operator_panel.py:308-323`), the Tasks-card Load Settings file dialog (S10.12.4), the auto-apply-newest rule and the carried-live-values precedence (`resolve_settings_precedence`, `settings_profile.py:193-244`; S10.3) and the in-memory `_task_overrides` / `_task_live_overrides` / `_task_selected_profile` (research §1.7). A run's settings are its test entry's snapshot, which also removes the three defects in research §1.8 (subject-switch leak, structural values dropped on run 2, dialog not pre-filled). S10.11's worry (two Save buttons in two places) disappears because the HUD is gone: this page is the one place to save.

### 4B.5 Footer actions

| Button | Behaviour |
|---|---|
| **Preview Test** (ghost) | 4B.6. Always enabled (even when validation blocks Save). |
| **Save & Continue** (primary) | Validate, apply the 4B.4 rules, store the snapshot + name + notes in the test entry, return to the Test List. Disabled with a reason while invalid. |
| **Cancel** (ghost) | No edits: return at once. Edits present: confirm "Discard your changes?" [Discard] [Keep editing]. Writes nothing either way. |

Enter does not trigger Save (sliders and the notes box use Enter).

### 4B.6 Preview Test

Goal (U6): let the doctor see and feel the look of the current settings with the mouse, before the child sits down.

1. **Uses the unsaved form.** `TaskConfigPage.collect_values()` -> `{"live", "structural"}` (the same dicts a recorded run gets as `live_overrides` / `structural_overrides`). Nothing is written.
2. **Abbreviated:** `trials = min(3, configured)` (override on a copy, never written back, research §4); timings unchanged, so hover-dwell feels like the real test; a **different seed** (`PREVIEW_SEED`, a constant that is not 0) so the Preview does not show the real run's first targets (research §1.4).
3. **Mouse-driven:** a duck-typed gaze source `MouseGazeSource` (`src/inputs/mouse_gaze.py`) handed to `AssessmentApp` as `client`. Contract (research §3): `latest() -> GazeSample | None` (`src/data/schema.py:21`; x/y = the mouse position normalised to the canvas; `valid` only while the mouse is inside it), `is_connected() -> True`, `device_info = None`, `is_live = False`, `connect / start_streaming / stop / clear_raw` no-ops, `drain_raw() -> []`, plus `bind_canvas(canvas)`. The dashboard calls `bind_canvas(assessment.view.canvas)` right after constructing the app (the first tick only fires once control returns to the event loop; before binding `latest()` returns `None`, which `EyeInput.poll` already treats as an invalid centred pointer, `eye_input.py:214-258`). With `device_info is None` the task keeps its canvas-relative pointer conversion (`app.py:772-774`).
   Dwell by hover, rings, smoothing and sounds work exactly as with gaze. The OS pointer stays visible; the gaze-cursor dot follows the **smoothed** position on purpose (it shows the effect of the smoothing setting). Mouse outside the canvas freezes the dot (existing dropout behaviour).
4. **Records nothing:** `run_mode="preview"` + `NullRecorder` as defined in the run-lifecycle section (research §2.2 A). This section only requires: no `sessions/<id>` folder, no `calibration.json`, no `_diagnostics` line, no settings-profile write, no effect on run numbering, no card/test status change.
5. **No tracker, no calibration, no gate:** Preview skips `setup_page.can_continue()` and never touches `setup_page.client` (no `clear_raw`, no `stop`, no reader pause), so it works before Connect, with a tracker connected, and during a tracker fault. The preset-calibration branch is not taken; the stub calibration result is used (`calibration.py:370-381`).
6. **Embedded full window,** as recorded runs are (`dashboard_window.py:431-441`): the run view is added to the stack on top of the **still-alive** config page; the nav is locked as for any active run. The bottom bar is the U5 bar: [Pause (Alt-P)] [Skip trial] [Quit (Alt-Q)] + one status line `PREVIEW · Trial 2/3 · mouse pointer · nothing is recorded` (`PREVIEW · Paused` while paused). The bar cannot be hidden (Hide HUD is gone), so the Preview is never mistaken for a recorded run.
7. **Return:** Quit, Alt-Q, Esc or the last trial finishing all remove the run view and `setCurrentWidget(config_page)`. Quit needs **no confirmation** (nothing to save). The page object is never rebuilt, so every control, the scroll position and the dirty flag are exactly as before (HB9); `load_values()` must not run on show. After a natural finish the footer message reads "Preview finished. Nothing was recorded." until the next edit.
8. **Carry-over:** none. Preview never changes the test, its status, or any stored configuration.

### 4B.7 Size, scroll behaviour, theme (1920x1080 @ 100 %, the project display standard)

- Window is maximized (`dashboard_window.py:522-533`); the content area is about 976 px high (that file's own figure). Pinned footer about 56 px and the page title block about 70 px leave about 850 px for the cards.
- Estimated tallest column (follow_moving, column B): Target about 140 + Motion about 240 + Timing about 200 + gaps about 32 = about 610 px; column A about 570 px; column C about 340 px. So **no vertical scrollbar at 1920x1080 @100 %** for any task. Width: 3 columns at a minimum of about 420 px each.
- Estimates only: acceptance AB16 is checked live, because offscreen sizes understate by about 10 % (memory: never measure Qt sizes offscreen) and the check must screenshot the **window**, not a widget grab.
- Still wrapped in a `QScrollArea` so a smaller window or 125/150 % scaling scrolls instead of clipping (responsive reflow is deferred by SPEC-display-standard-check; the Setup page already warns). Rules from SPEC-ui-setup-task-selection §22: the scroll area is `wtmhConfigScroll` (new QSS next to `wtmhSetupScroll`, `wtmh_theme.py:71`); the Footer sits **outside** the scroll area (§22.3); after `setWidget()` call `scroll.viewport().setAutoFillBackground(False)` and `content.setAutoFillBackground(False)` (§22.5, else black bands in the card gaps); the app-wide scrollbar theme already applies under `wtmhDashboard` (§22.6); both scroll bars `AsNeeded`.
- Combo popup styling (`task_settings_dialog.py:199-211`) moves to a shared helper used by the page's one combo (Configuration Name).

---

#### Hub decisions proposed

- **HB1** Size, cell gap and movement path are **radio groups**, not combos. Why: 3-5 fixed options all visible at once is the Compass rule for one-of; stored values and keys are unchanged.
- **HB2** Units stay as in the registries (ms, px). Why: no conversion layer, no change to stored values or tests.
- **HB3** Expose `feedback.hit_sound` / `feedback.miss_sound` as two check boxes (needs a `kind="bool"` structural setting); expose nothing else YAML-only; do not wire the dead `feedback.particles`. Why: sensory-sensitive children; everything else is a task design constant.
- **HB4** No Input Device / Test Language fields. Why: no such options (U4, U12).
- **HB5** A new test starts at **Standard**; the "auto-apply newest profile" rule (S10.3) and live carry-over are retired. Repeating a test = Copy Test or picking a named configuration. Why: matches Compass and U3/U4; one visible choice instead of hidden state. **Reverses an earlier user decision, see Open questions.**
- **HB6** Named configurations = versioned files with a `name` field, schema v2, a name resolves to its newest version, old v1 files appear as "Saved MM/DD HH:MM". Why: keeps "never overwrite" (S10.12.3) and every existing profile.
- **HB7** Configure is disabled for locked tests; no read-only mode; save-time guard only. Why: Compass behaviour, one fewer code path; the report shows the config.
- **HB8** Preview = at most 3 trials, unchanged timings, different seed, no quit confirmation. Why: shows real dwell feel; nothing to protect.
- **HB9** Config page is a persistent widget; Preview is pushed on top and popped. Why: unsaved edits survive for free, no state serialisation.
- **HB10** Fixed 3-column grid in a scroll area with a pinned footer; no responsive reflow. Why: display standard is 1920x1080 @100 %; reflow is deferred.
- **HB11** Keep `TaskSettingsDialog` for the standalone `--task X --gui` path (`app.py:1044-1078`), but the dashboard stops using it. It needs a `bool` branch (a `QCheckBox`) because the new structural bool keys would otherwise be built as sliders. Why: avoids breaking the standalone path and `tests/test_task_settings_dialog.py`.
- **HB12** The test entry's snapshot is complete (every task-applicable key). Why: the report's Test Configuration table (U9) needs the full set, and a run must not depend on YAML drift.

#### Acceptance criteria

- **AB1** For each task the page contains exactly the controls of 4B.2 (a test over the registries: control set = registry keys for the task + name / config / notes), and no px target-radius control.
- **AB2** Every key in `live_settings_for_task` and `structural_settings_for_task` (plus the two feedback keys) has exactly one control, and none is hidden.
- **AB3** A new test opens with Standard and defaults equal to `initial_live_values` / `initial_structural_values` of the merged YAML; alpha shows 0.22.
- **AB4** `collect_values()` on an untouched page equals the defaults; its `structural` equals `TaskSettingsDialog.overrides()` for the same task and inputs, plus the feedback keys.
- **AB5** Unticking Smoothing enabled disables (not hides) Smoothing alpha and re-ticking re-enables it.
- **AB6** The grid and scanning hints show the same text as the dialog for the same inputs and hide when the preset fits.
- **AB7** Selecting a saved name loads all live + structural values; a profile missing a key gives that key's default; a dirty form asks before replacing.
- **AB8** Standard + changed values + Save & Continue opens the forced-rename dialog; "Standard" is refused; on success a profile file with `name` and `schema_version == 2` exists and the test entry holds `{name, live, structural}`.
- **AB9** Existing name + changed values prompts Update / Save as new / Cancel; Update adds a new version file, the old file is still present, and the combo shows one entry for that name with the newest values.
- **AB10** A v1 profile appears as "Saved MM/DD HH:MM" and loads; `load_settings_profile_file` returns `name == ""` for it and the name for v2.
- **AB11** Empty / over-long / duplicate (case-insensitive) Test Name, or empty Configuration Name, disables Save & Continue and shows the reason.
- **AB12** Cancel with edits asks first, without edits returns at once, and neither writes anything. Reset to defaults restores Standard + defaults and keeps Test Name and Notes.
- **AB13** Preview uses the **unsaved** values (change the size radio, do not save, preview shows it), runs `min(3, trials)` trials with a seed different from the recorded run's, and a hover of dwell-threshold length on the target scores a hit.
- **AB14** Preview creates nothing: a recursive listing of `sessions/` (including `_diagnostics`, `_settings`) before and after is identical.
- **AB15** Preview works with no tracker connected and no calibration; with a fake client on the Setup page, no `clear_raw` / `stop` / `drain_raw` call reaches it.
- **AB16** Esc, Quit and Alt-Q and natural finish all return to the page; `collect_values()` before and after are equal, scroll position retained; natural finish shows the "Preview finished" note.
- **AB17** At 1920x1080 @100 % maximized, a **window** screenshot of each of the 4 pages shows every card, no clipping, no vertical scrollbar, footer visible; `qt_layout_check` clean. At `QT_SCALE_FACTOR=1.5` the page scrolls and the footer stays pinned with Save & Continue reachable.
- **AB18** No black bands between cards (screenshot), scrollbar themed.
- **AB19** Saving a test whose stored status is no longer Not Done writes nothing and shows the message.
- **AB20** `feedback.hit_sound=false` in the snapshot results in no hit sound in `GuiFeedback`.

#### Plan steps (ordered)

1. **Wireframe first** (`/wireframe`, `docs/wireframes/task-config.md`, replaces `task-settings.md` for the dashboard): the 4 pages at 1920x1080 (Standard state), the modified/forced-rename dialog, the greyed alpha, and the Preview run bar. User approval gate.
2. `settings_registry.py`: structural `kind="bool"` for the two feedback keys (+ bool branch in `_initial_structural_value`); a pure `config_groups_for_task(task_id)` layout spec (cards, order, widget kind, `depends_on`). Test: AB1/AB2 over the registries. Keep the file under 500 lines (now 411).
3. `settings_profile.py`: `name`, schema v2, `list_named_configurations`, task-filtered `live`, complete `structural`. Tests (AB8-AB10 data part), extend `tests/test_settings_profile.py`.
4. `target_size.py`: extract `grid_fit_hint` / `icon_fit_hint`; `TaskSettingsDialog` calls them, gets the bool branch (HB11). Existing dialog tests must pass unchanged.
5. `task_config_page.py` + `wtmh_theme.py` QSS (`wtmhConfigScroll`): widgets, `collect_values` / `load_values`, dirty tracking, validation, signals `saveRequested(dict)`, `cancelRequested`, `previewRequested(dict)`. Offscreen tests: AB1-AB7, AB11, AB12.
6. `mouse_gaze.py` + tests (valid inside, invalid outside, normalisation, `bind_canvas`).
7. Dashboard wiring (**depends on the run-lifecycle section**: `run_mode`, `seed`, `NullRecorder`, the U5 bottom bar, and the Test List entry): Configure -> page; Preview -> `AssessmentApp(run_mode="preview", client=MouseGazeSource, ...)`; return handling; save rules of 4B.4.
8. Live validation via qt-mcp, window maximized first: AB13-AB19, once at `QT_SCALE_FACTOR=1.5`. Ask-before-commit gate as usual.

#### Open questions (user)

1. **HB5 reverses S10.3.** Today the newest saved profile for the child auto-applies on the next run. Under the Test List a new test would instead start at Standard (as Compass does), and you repeat a child's setup with Copy Test or by picking the configuration name. Confirm?

## 4C. Start page, Practice, run screen without HUD, run end

Repo `dev/peds-eye-gaze-assessment` at b7401d3. `file:line` verified against that tree. Test-store names (`mark_saved`, `Test.seed`, ...) are assumptions about Parts A/B; adapt to their final names.


### 4C.1 Flow and states

```
Test List --Run Test--> StartTestPage --Cancel--> Test List
                          |  ^
                 Practice |  | (always returns here; repeatable)
                          v  |
                      Practice run (3 trials, nothing recorded)
                          |
                 Start    +--> Recorded run --finished--> Test Complete! dialog
                                     |  Quit -> confirm -> Save partial / Discard
                                     v
                         Test List (row updated)  or  Report (Save and View Report)
```

- `DashboardWindow` gets one flow state `IDLE | START | PRACTICE | RUN | FINISHING`. `_go_to_tab` (`dashboard_window.py:175-177`, today `_active_assessment is not None`) refuses navigation in every state except `IDLE`, so the Start page is as locked as a run.
- The Start page is a page of `self.stack` (new `_START_INDEX`), not a mode of the run object. Practice and the recorded run each build a **new** `AssessmentApp` (research-run-lifecycle 2.4: never reuse one; the fresh `clear_raw()` at `app.py:440` is what keeps practice out of the real raw files).
- The test record needed from 4A: `test_id, name, task_id, config` (the structural + live values passed to `AssessmentApp`), `config_name`, `seed`, plus store calls `mark_saved(test_id, session_id, outcome, completed, planned, finished_at)` and `mark_discarded(test_id)`.

### 4C.2 Gate with a visible reason

- New `SetupPage.run_blockers() -> list[str]` beside `can_continue()` (`setup_page.py:347-356`); `can_continue()` becomes `not run_blockers()`, behaviour unchanged. Strings, in this order: "The tracker is not connected. Connect it on the Setup page." / "No calibration yet. Calibrate on the Setup page." / "Subject ID is empty." / "Assessment date is empty." / "Sex is not selected." / "The display is not 1920x1080 at 100 %. Tick the acknowledgement on the Setup page."
- Run Test **always opens** the Start page. If blockers exist: an amber banner at the top lists them with a "Go to Setup" button, and Start and Practice are disabled. The page re-evaluates on show, every 1 s while visible (the tracker can drop), and again inside the Start/Practice handlers (a stale enabled button still cannot launch). This replaces today's silent `return` at `dashboard_window.py:379-380`.

### 4C.3 Start screen (07a layout)

- Title "Start <test name>" (e.g. "Start Grid Click 1"). Large white panel; below it a centered row **Start / Practice / Cancel** (no default button; Esc = Cancel); a help bar: "Help: From this screen you can begin the test. You may also practice 3 targets first; practice is not recorded. Read the instructions aloud to the child."
- The panel has two blocks: "Read aloud to the child" (steps + NOTE) and "For the clinician" (not read aloud).
- Text comes from new Qt-free `src/ui/task_instructions.py`: `build_instructions(task_id, cfg, values) -> Instructions(heading, steps, note, clinician)`. `{dwell}` = dwell threshold formatted as seconds (800 -> "0.8 seconds", 1000 -> "1 second"), `{timeout}` = `task.timeout_ms` the same way, `{n}` = planned trials. Two optional clauses depend on the test's own settings: `{ring}` = " A ring will fill up around it." only when `dwell.progress_ring`; `{dot}` = a first sentence "The small dot on the screen shows where you are looking." only when `dwell.visual_cursor`. The YAML `instruction:` keys (Chinese, unread by `src/`) stay untouched for the future zh feature (U12).

Child text per task (heading "Instructions for the <task name> test:"; steps numbered; `{dot}` prefixes step 1):

```
Static Click
 1. A circle will appear on the screen.
 2. Look at the circle and keep looking at it for about {dwell}.{ring}
 3. When it is selected, the next circle will appear.
 4. Continue until no more circles appear.
 NOTE: If the circle is not selected within {timeout}, it will disappear and the next one will appear.

Grid Click
 1. A board of squares will appear on the screen.
 2. One square will light up.
 3. Look at the lit square and keep looking at it for about {dwell}.{ring}
 4. When it is selected, another square will light up. Continue until no more squares light up.
 NOTE: If the square is not selected within {timeout}, the next square will light up.

Follow & Click
 1. A circle will appear and start to move across the screen.
 2. Follow the moving circle with your eyes.
 3. When the circle becomes bright with a white ring, keep looking at it for about {dwell} to select it.{ring}
 4. Then a new circle will appear. Continue until no more circles appear.
 NOTE: If the circle is not selected within {timeout}, it will disappear and the next one will appear.

Scanning Search
 1. Several shapes will appear on the screen.
 2. One shape will light up bright. The others stay dim.
 3. Find the bright shape and keep looking at it for about {dwell}.{ring}
 4. When it is selected, a different shape will light up. Continue until no more shapes light up.
 NOTE: If the shape is not selected within {timeout}, the next shape will light up.
```

Clinician block (all tasks): "To pause the test: click the "Pause" button, or press ALT-P. To quit the test: click the "Quit" button, or press ALT-Q." / "Practice runs 3 targets with these settings. Nothing is recorded. Repeat it as often as needed." / "Start records {n} trials. Check that the bottom bar says "tracking OK" before you begin." The wording is read to children: it needs clinician review before release.

### 4C.4 Practice

- `AssessmentApp(..., run_mode="practice")`. `run_mode` is `record | practice | preview` (preview = Part B, mouse source; everything below that says "non-record" applies to it too). Call-site copy: `structural = {**test.structural, "trials": min(3, planned)}`; the test's own dicts are never mutated.
- **Seed.** `AssessmentApp` gains `seed: int = 0` forwarded to `build_task(..., seed=seed)` (`app.py:514`; `task_runner.py:50` already accepts it; today every run is seed 0, so a practice would replay the real run's first targets). Record run: `seed = test.seed` (default 0 = today's standardized sequence). Practice: `seed = 1_000_000 + k`, k = practice presses since the Start page opened, so it never equals a record seed (kept < 1_000_000) and differs on every repeat.
- **Recording guards** (all keyed on `run_mode != "record"`):
  1. `NullRecorder` (new, in `recorder.py`, ~40 lines) replaces `SessionRecorder` at `app.py:431-432`. Same surface as `SessionRecorder` (`open, open_all_gaze, open_eye_geometry, record_raw/gaze/event, log, write_trials, write_metadata, flush_*`, `close`; `session_dir = None`), all no-ops. The literal lines `self.client.clear_raw()` ... `self.recorder.open_all_gaze(` ... `self.recorder.open_eye_geometry()` stay in `__init__` in that order (source-order test `tests/test_eye_geometry.py:347-356`).
  2. No `session_dir.mkdir` / `save_calibration_result` (`app.py:319-320`, `:338-339`); `session_id` is the sentinel "practice", `next_session_id` is not scanned (`:267`).
  3. No `GazeDropoutLog` (`:546-554`).
  4. `_shutdown` skips `write_trials`, `_record_session_end_quality`, `finalize_all_gaze`, `write_session_metrics` (`:1015-1034`).
  5. The settings-profile save disappears with the HUD (4C.7), so nothing can persist the 3-trial override.
- End of practice: `on_finished(RunResult)` -> dashboard returns to the Start page and shows one line "Practice finished: 3 of 3 selected. You can practice again or press Start." Quit/Esc in practice returns to the Start page at once, with no dialog (nothing to lose). The in-memory `task.trials` feed the line only.
- Tracker: practice uses `setup_page.client` and the calibration result exactly like a recorded run (`embedded=True`, `_owns_client=False`, so it never stops the client).

### 4C.5 Run screen without HUD

- `OperatorPanel` (`operator_panel.py`, 518 lines) is deleted. `TaskRunView` (`main_window.py:27-83`) becomes a `QVBoxLayout`: `TaskCanvas` (stretch) + new `RunBar` (`src/ui/run_bar.py`, fixed ~44 px, light grey like 07b). `RunBar` signals: `pause_toggled(bool)`, `skip_requested()`, `quit_requested()`. Buttons: "Pause (Alt-P)" (becomes "Resume (Alt-P)"), "Skip trial", "Quit (Alt-Q)". Status label left, buttons centered. Alt-P and Alt-Q are `QShortcut`s on the view with `WidgetWithChildrenShortcut` (like the old `hud_shortcut`, `main_window.py:69-75`), not mnemonics. After any bar click the canvas regains focus so Space (switch) keeps working.
- While Practice or a recorded run is shown, the dashboard title bar is hidden (`_build_title_bar` result stored as `self.title_bar`), so the canvas fills the window above the bar; shown again at run end. The canvas is slightly larger than with the HUD; `_record_geometry` and `CANVAS_RESIZED` (`app.py:691-707`) still record whatever it is.
- Practice marker: in practice the bar background turns amber and the status starts "PRACTICE (not recorded)". The child sees only the canvas.
- **Status line** (one `QLabel`, updated every tick): `"[PRACTICE (not recorded) · ]Trial {i}/{N} · {tracking}"`, i = `trial_index+1` as in `app.py:943-947`, N = `len(task.targets)`. Tracking states from data already available:
  - `tracker DISCONNECTED` (red): `client.is_connected()` is False.
  - `no gaze for {s} s` (amber): connected, but no `pointer.valid` frame for `GAZE_LOST_AFTER_S = 1.0` s (`FPOGV` drops during saccades and blinks, so single invalid frames never show); `waiting for gaze` before the first valid sample.
  - `tracking OK` (green) otherwise.
  - Paused: `Paused · Trial {i}/{N}`.
  - A pure function `tracking_status(connected, seconds_since_valid) -> (text, level)` carries the rule so it is unit-testable.
- Skip is enabled only in `Phase.WAIT_INPUT` and not paused (today it silently does nothing during ITI). Paused canvas draws a calm centered "Paused" and no target or cursor (`TaskCanvas.set_paused`).

### 4C.6 Pause, Skip, Quit semantics

**Pause (Compass: stopwatch stops, interrupted trial not recorded).** New `BaseTask.pause(t_ns)` / `resume(t_ns)`:
- In `WAIT_INPUT`: the in-flight `_current` is discarded (never appended to `trials`), event `TRIAL_INTERRUPTED {trial, reason, elapsed_ms}`, `_trial_index -= 1`, phase `READY`. On resume the next `update()` runs `_start_trial` (`base_task.py:466`): the **same target (same position/cell/icon) is re-presented as a new trial with a fresh clock**, same `trial_id`. N is preserved and `trials.csv` stays contiguous. A pause of any length can no longer cause a timeout (today `_tick` returns at `app.py:879` but `t_ns` is wall-clock, so a long pause times the trial out on resume).
- In `ITI`: remaining ITI is kept (`_phase_deadline_ns += paused_ns` on resume).
- While paused, `_tick` does not call `task.update`; it still drains the raw queue and discards it (so the 10 000-record queue never overflows into a burst on resume, `gazepoint_client.py:588-607`), records **no** `gaze_stream` row, and shows the Paused canvas. Reason: pause time (child looking away) must not lower the run's valid-share. Events `PAUSED {t_ns, trial, interrupted}` / `RESUMED {t_ns}` mark the gap; `all_gaze.csv` `TIME` jumps by the pause length, which the report's velocity pass must treat as a break.
- Metadata: `pause_count`, `interrupted_trials`.

**Skip trial.** New `BaseTask.skip_trial(t_ns)` replaces the `_trial_start_ns = 0` hack (`app.py:678-680`): sets `TrialRecord.is_skipped = True`, finishes the trial through `_finish_trial` with no timeout flag, event `SKIPPED {trial}`. `_finish_trial` (`base_task.py:509`) calls `feedback.on_hit` for a hit, `on_miss` for a timeout, **nothing** for a skip (no miss sound, no particles). `trials.csv` gains column `is_skipped` (0/1; skipped rows have `is_hit=0, is_timeout=0`, `t_end_ns` set, `t_click_ns` blank). `summarize()` (`exporter.py:183-223`) adds `n_skipped`, and `hit_rate` uses trials minus skipped as denominator; `n_timeouts` no longer includes skips.

**Quit (Alt-Q, button, and Esc; Esc no longer ends the task instantly, `app.py:664-665`).**
1. Pause (clock stops) and show "Quit the test? {c} of {N} trials are done." [Quit test] [Keep going]. Keep going resumes (unless the operator had paused already). Practice skips this dialog.
2. On confirm: `_shutdown(ended_by="operator_quit")` writes every file exactly as at normal completion (the in-flight trial is dropped as today), then the dashboard asks "Save the {c} completed trials?" [Save partial results] [Discard results]. Window close/Esc = Save partial (never destructive by default).
3. `c == 0`: no choice is offered; the run is discarded automatically with a message "No trials were completed, so nothing was saved."

### 4C.7 What happens to each HUD feature

| HUD feature (today) | Fate |
|---|---|
| FPS and Device Hz labels (`operator_panel.py:215-226`) | Deleted. `_update_fps`, `_fps*`, `_device_rate` in `app.py` go; `measured_sample_rate_hz` is computed from the raw file at close (`app.py:969-977`), `LatencyTracker` / `LATENCY_SAMPLE` stay |
| Gaze validity label | Replaced by the status line tracking state |
| Trial counter, hit/timeout tally, progress bar (`:233-259`, `app.py:941-952`) | Counter becomes "Trial i/N" in the status line; tally and bar deleted (U5: no score) |
| Pause / Skip trial / End task buttons | Pause (Alt-P), Skip trial, Quit (Alt-Q) in `RunBar` |
| Hide HUD button, H key, `hud_hidden_changed`, `_hud_hidden` (`dashboard_window.py:96, 443-444`), `hud_hidden` ctor arg, `_on_hud_hidden_changed`, `HUD_TOGGLED`, `hud_hidden_at_start`, `hud_toggle_count` (`schema.py:222-223`) | Deleted, fields removed from `SessionMetadata` (old sessions simply have them). `CANVAS_RESIZED` stays |
| 11 live sliders / checkboxes (`_build_control`; keys in `settings_registry.py:94-200`) | Not on the run screen. They become the test's values on the Part B configuration page (`LIVE_SETTINGS` and `SliderSpinRow` are reused there). `_apply_setting` (`app.py:709-751`) and the `SETTING_CHANGED` events are deleted: nothing changes during a run, so `metadata.settings.live` is now the complete config of the run. Old sessions' `SETTING_CHANGED` events must still be tolerated by readers |
| "Show gaze cursor", progress ring, instant ring | Configuration page (U5); `AssessmentApp` still applies the three `canvas.show_*` flags at start (`app.py:393-395`) |
| Settings-profile card: source label, Save for this subject, Reset to defaults (`operator_panel.py:303-323`, `app.py:621-656`) | Deleted here. Save/load of a named configuration is Part B; its calibration note must come from `setup_page.calibration_result` since `calibration_snapshot()` (`app.py:609`) goes. `SETTINGS_PROFILE_SAVED` is no longer a run event |
| Carry-over of live values between runs, `_task_selected_profile` (`dashboard_window.py:85-101, 461-464`) | Deleted (S10.3 "run 1 tunes, run 2 collects" is gone with the sliders) |

Code and tests to remove: `src/ui/operator_panel.py`; `tests/test_hud_hide_toggle.py` (move its `_check_canvas_resized` tests to `tests/test_run_events.py`); HUD wireframe `docs/wireframes/run.md/.html` (rewritten); `SPEC-hud-hide-toggle.md` marked superseded; `tests/test_task_settings_dialog.py` is Part B's. Standalone `python -m src.main --task X --gui` keeps working: `MainWindow` hosts the same `TaskRunView`/`RunBar`, no Start page.

### 4C.8 Run end, outcome and discard

- `AssessmentApp.on_finished` now receives `RunResult(run_mode, outcome, ended_by, planned, completed, skipped, hits, session_dir | None, finished_at)`. `outcome = "completed"` iff `task.is_done`, else `"ended_early"`; `ended_by = "finished" | "operator_quit"`. Computed in `_shutdown` **before** `recorder.close()` so the metadata carries it. `_shutdown` stays idempotent (`app.py:1004-1006`) and still writes everything to disk before any dialog (a crash at the dialog loses nothing).
- **Test Complete! dialog** (07b): modal over the frozen canvas, title "Test Complete", text "Test Complete!", buttons **Save** / **Save and View Report** / **Discard Results**. Close/Esc = Save.
  - Save: `mark_saved(...)` (row becomes "Done <date>", test locked), back to the Test List with the row selected.
  - Save and View Report: Save, then the Part D report for the test (`open_report(test_id)`).
  - Discard Results: one confirmation "Discard these results? This cannot be undone." [Discard] [Keep]; then `discard_session`, `mark_discarded` (row stays "Not Done", unlocked, re-runnable), back to the Test List. The partial-run Discard (4C.6 step 2) has no extra confirmation: it is already the second step of a confirmed quit.
- Partial save: row shows "Ended early (c/N)" (c = rows in `trials.csv`, skipped included), test locked.
- **Discard = delete the session folder** (recommended over moving to `_discarded/`, HC6). New Qt-free `src/engine/session_files.py: discard_session(session_dir, output_root)`: resolves both paths; refuses unless `session_dir.parent == output_root`, the name matches `^\d{4}-\d{2}-\d{2}_.+_run\d+$`, it does not start with `_`, and every entry is a regular file (any subdirectory or symlink aborts with no deletion); then unlinks the files and `rmdir`s. The path is the one in the `RunResult`, never user text. The run number N becomes free again (`session_naming.py:17-30`). `sessions/_diagnostics/*` lines of that run remain (not subject-identifying).
- Orphans: if the app dies while the dialog is open, the folder stays on disk and the test stays "Not Done" (data is never lost; relinking is out of scope).

### 4C.9 Data contract added by this part

| Where | Field | Meaning |
|---|---|---|
| `trials.csv` / `TrialRecord` | `is_skipped` | 1 when the operator skipped (append at end of `csv_header`, `schema.py:140-159`) |
| `metadata.json` | `test_id`, `test_name`, `config_name`, `seed` | link back to the test and the stimulus order |
| | `planned_trials` (= `len(task.targets)`), `completed_trials`, `skipped_trials`, `interrupted_trials`, `pause_count` | closes research-results gaps 1d |
| | `outcome` (`completed`/`ended_early`), `ended_by`, `ended_ns` | no `discarded` value: a discard deletes the folder |
| `events.jsonl` | `PAUSED`, `RESUMED`, `TRIAL_INTERRUPTED`, `SKIPPED`; stops: `HUD_TOGGLED`, `SETTING_CHANGED`, `SETTINGS_PROFILE_SAVED` | additive; `schema_version` not bumped (as `schema.py` comments) |
| `session.log` | "Run completed: c of N trials." / "Run ended early by operator at trial i of N (c recorded)." | |

#### Hub decisions proposed

- **HC1 Seed:** record run keeps `seed = test.seed` (default 0, today's standardized order); practice uses `1_000_000 + k`. Why: practice must not preview the real targets, and changing the stimulus order is a protocol change nobody asked for.
- **HC2 Gate:** Run Test always opens the Start page; blockers shown as a banner with disabled Start/Practice. Why: instructions stay readable and the reason is visible, never a silent no-op.
- **HC3 Pause drops the in-flight trial and re-presents the same target as a fresh trial.** Why: Compass semantics, N and `trials.csv` stay contiguous, no new target generator needed.
- **HC4 No gaze recorded while paused (raw drained and discarded).** Why: pause time must not depress valid-share or create a replay burst.
- **HC5 Skip = `is_skipped` column, no miss feedback, excluded from the hit-rate denominator.** Why: U5 says skipped is not a timeout.
- **HC6 Discard deletes the folder (guarded) instead of moving it to `_discarded/`.** Why: Compass "discard", frees the run number, and a clinician's "discard" means gone; one function to switch later.
- **HC7 Dialog defaults:** Test Complete close/Esc = Save; Discard Results asks one confirmation; partial Discard does not; zero completed trials auto-discards. Why: nothing destructive by default.
- **HC8 Title bar hidden during Practice and Run.** Why: "full-window canvas" like Compass; nav is locked anyway.
- **HC9 Tracking status threshold 1.0 s; a disconnect only shows in the status line (no auto-pause).** Why: U5 asks for one line; auto-pause is a possible follow-up.
- **HC10 Esc = Quit with confirmation** (was an immediate end). Why: a child at the keyboard must not end a recorded run.
- **HC11 Instruction text in a Qt-free builder with dwell/timeout/ring/dot placeholders.** Why: it must match the configured test and be unit-testable; YAML Chinese keys stay for the later zh feature.
- **HC12 Practice end/quit returns to the Start page with a one-line result, no dialog.** Why: nothing is at stake.
- **HC13 Remove `hud_hidden_at_start` / `hud_toggle_count` from `SessionMetadata`.** Why: dead fields; readers already use named keys and old sessions lack newer keys anyway.

#### Acceptance criteria

- **AC1** Start page shows the test name, the task's steps with the test's real timeout and dwell, the clinician block, Start/Practice/Cancel and the help line. Unit test over 4 tasks x ring/dot on/off: no unreplaced `{`, 800 ms -> "0.8 seconds", 1000 ms -> "1 second".
- **AC2** With the tracker disconnected or no calibration, Start and Practice are disabled and the banner lists the `run_blockers()` texts; `run_blockers() == []` iff `can_continue()`; no Run Test press is a silent no-op.
- **AC3** Cancel returns to the Test List; no test state and no file on disk changes. Nav buttons do nothing while the Start page, Practice or a run is shown.
- **AC4** Practice runs exactly `min(3, planned)` trials. `sessions/` listing and file bytes are identical before and after (no new folder, no `_diagnostics` line, no `calibration.json`); the test's config dicts are deep-equal before and after; with seed 0 the practice target sequence differs from the record run's first 3 (click_static and click_grid).
- **AC5** Practice can be repeated (each time with a new seed); its end and its Quit both land on the Start page; the result line appears after a finished practice.
- **AC6** The `test_eye_geometry.py:347-356` source-order test still passes; new test: fake client with queued raw records, practice then record -> the record's `all_gaze.csv` starts at `TIME` 0 and holds only post-construction records.
- **AC7** Run screen: no `OperatorPanel` in the widget tree; bar holds Pause (Alt-P) / Skip trial / Quit (Alt-Q) and the status label; canvas width equals view width; title bar hidden during the run and shown after.
- **AC8** `tracking_status` tests: valid -> "tracking OK"; 3.2 s without valid gaze -> "no gaze for 3 s"; disconnected -> "tracker DISCONNECTED"; the full line "Trial 4/12 · tracking OK"; practice prefix; paused text.
- **AC9** Pause in `WAIT_INPUT`: no `trials.csv` row for the interrupted attempt, the same target returns with a fresh clock, final row count still N, `PAUSED/RESUMED/TRIAL_INTERRUPTED` events written, a pause longer than `timeout_ms` creates no timeout; pause in ITI keeps the remaining ITI; no `gaze_stream` or raw rows are written while paused.
- **AC10** Skip: row has `is_skipped=1, is_timeout=0, is_hit=0`; a feedback spy sees no `on_miss`/`on_hit`; `SKIPPED` event; the button is disabled in ITI and while paused; `summarize()` reports `n_skipped` and does not count it in `n_timeouts`.
- **AC11** Quit: the confirm dialog stops the clock and "Keep going" resumes; confirming writes all files with `outcome=ended_early`, `ended_by=operator_quit`, `planned/completed` correct, then Save partial / Discard; zero completed trials auto-discards; Esc triggers the same flow.
- **AC12** Normal completion writes `outcome=completed`, `completed_trials == planned_trials`; dialog buttons: Save -> row "Done <date>" and locked; Save and View Report -> report opens; Discard Results -> confirm, folder gone, row "Not Done", unlocked, run number reusable; partial save -> "Ended early (c/N)".
- **AC13** `discard_session` tests (tmp_path): refuses a path outside the root, a bad name, `_settings`, a folder containing a subdirectory or symlink; deletes only the target and leaves sibling sessions.
- **AC14** `grep` finds no `operator_panel`, `hud_hidden`, `HUD_TOGGLED`, `SETTING_CHANGED` emission or `_save_settings_profile` in `src/`; the whole suite is green; an old session folder containing those events still loads.
- **AC15** Standalone `--task X --gui --replay <fixture>` still runs to the end (offscreen) with `RunBar`.
- **AC16** New metadata fields serialize; a session folder without them still loads in `summarize`/report code.

#### Plan steps

1. **Engine, no UI (tests first):** `TrialRecord.is_skipped` + csv header; `BaseTask.pause/resume/skip_trial`, `_finish_trial` skip path; `seed` plumbing in `AssessmentApp`; `SessionMetadata` new fields and removal of the HUD fields; `summarize()` skip handling; `NullRecorder`; `discard_session`; `tracking_status`; `task_instructions.build_instructions`; `SetupPage.run_blockers`.
2. **[Wireframe first] `docs/wireframes/start-test.md` (07a), `run.md` rewrite (bar, paused, practice marker), `run-end.md` (Test Complete, Quit confirm, Save-partial/Discard, Discard confirm).** wiremd HTML, user approval before step 3.
3. `RunBar` + new `TaskRunView` + `TaskCanvas.set_paused`; delete `operator_panel.py`.
4. `AssessmentApp`: `run_mode`, guards of 4C.4, paused tick, quit flow, `RunResult`, `_shutdown` outcome fields; remove `_apply_setting`, profile save/reset, HUD handlers, fps/device-rate meters.
5. `StartTestPage` (banner, instructions, buttons, practice result line).
6. `DashboardWindow`: flow state, nav lock, title-bar hide, launch/finish handlers for practice and record (needs Part A/B test store).
7. End dialogs: `TestCompleteDialog`, quit confirm, partial choice, discard confirm; store updates; open report.
8. Cleanup: HUD tests, SPEC-hud-hide-toggle superseded note, README test count, `docs/DATA_SCHEMA.md` new fields.
9. Live check with the fake server and then the real tracker, user as subject: practice leaves `sessions/` untouched; pause mid-trial; skip; quit; complete; discard.

#### Open questions (user)

- **Q1** May a discarded session be **permanently deleted** under your research/consent policy, or must discarded data be kept (move to `sessions/_discarded/` instead)? HC6 assumes delete.
- **Q2** Should every subject get the **same target order** (today's seed 0, HC1) or a random order per test? HC1 keeps today's behaviour; it is a protocol choice, not a coding one.

## 4D. Per-test report (Summary / Detailed) and the analysis behind it

Repo = `dev/peds-eye-gaze-assessment`. Binding: U9-U12 (`decisions.md`). Evidence = file:line on `main` b7401d3 plus probes I ran on
real-device sessions (scripts in `scratchpad/D/probe*.py`; sessions `2026-10-05_EYEGEOM_click_grid_run1`, `..._TESTING_click_grid_run2/3`,
`..._EYEGEOM_click_static_run1`, `..._UNITS150_click_static_run1`, all GP3HD @150 Hz).

### 4D.1 Scope, inputs, cross-part dependencies

Part D = the Report page for ONE finished test, the Qt-free analysis behind it, and the few recording additions that analysis needs.
It replaces `ResultsPage` (`src/ui/results_page.py:56-253`, shows only the latest run, "Mean revisits" never filled `:131-134,246-247`).
Out of scope (U9): Multi-Test Report, clipboard copy. English only (U12).

Needed from other parts (names are assumptions; reconcile with draft-A/B/C):
- **X1** `config_snapshot.json` in the run folder = full merged effective config + Configuration Name (today `metadata.settings` is partial:
  no theme / feedback / scanning arrangement, research §5). With sliders gone (U5) the start-of-run snapshot is the whole truth.
- **X2** `trials.csv` gains `outcome` = `hit|timeout|skipped` (4C, U5) — **superseded by R6: no outcome column, derived from `is_skipped`**. D treats an absent column as derived from `is_hit/is_timeout`.
- **X3** `metadata.json`: `trials_planned`, `ended_early` (4C; **names per R1: `planned_trials`, `outcome`**; today planned N is only in `session.log`, research §1d).
- **X4** >= 500 ms of recorded blank before the first onset (4C's Start -> run hand-off; **adopted as R8**). Today the first trial has ~200 ms pre-roll
  (probe: baseline n=30 vs 45 samples), so trial 1's pupil baseline would be "—" otherwise.
- **X5** Test name, Evaluator, Notes persist in Part A's test record, NOT in the run folder (single source of truth). ReportPage emits
  `saved(name, evaluator, notes)`; the host writes it.
- **X6** After Part C the canvas size is constant per run (HUD gone). `CANVAS_RESIZED` events still exist (`app.py:691-706`); if any occurs
  the report shows a one-line warning "window was resized during the test; gaze overlay approximate".

### 4D.2 Report page layout (adapted from 08a / 08b)

Page = one QWidget in the dashboard stack, opened from the Test List "View Report" and from the Test Complete dialog "Save and View Report".
Compass left column / right column / footer kept; Compass "Input Device" drop-down dropped (we record `input_mode` + tracker).

| Zone | Content |
|---|---|
| Header | Title "Summary Results:" / "Detailed Results:". Editable **Test Name** (wide box; unique within the subject, validation by Part A). Right block: **Subject** (read-only), **Test Date** (`metadata.started_ns`, local time, "Oct 6, 2026 2:06 PM"), **Evaluator** (editable, optional). Banner under header when `ended_early` ("Ended early — 7 of 18 trials") or valid-gaze share < 80 % (reuse the existing floor, `results_page.py:200-206`). |
| Left column (both views) | **Test Configuration**: "Configuration Name: x" + Setting / Value table (4D.3). **Notes** multi-line box (editable). |
| Right, Summary | (1) one-sentence task description (per-task string, English). (2) **Summary of Results** table. (3) **Target Map** with overlay checkboxes. (4) **Eye Metrics** table (whole test). |
| Right, Detailed | **Trial-by-Trial Results** table (top ~55 %) + **selected-trial map** (bottom ~45 %, 4D.7). First row auto-selected. |
| Footer | **Print Report** / **View Details** (Detailed: **View Summary**) / **Save & Continue** / **Cancel**. Save persists the three editable fields and returns to the Test List; Cancel discards them and returns. Run data is never editable. |

**Summary of Results** (U10). Rows and columns:

| Row | Membership |
|---|---|
| Error-free Target Selections | `outcome=hit` and `entries==1` and `attempts==1` |
| All Targets Selected | `outcome=hit` (includes the row above) |
| Targets Not Selected | `outcome=timeout` |
| All Trials | hit + timeout (skipped excluded, HD5) |

Columns: **% (N)** = `x% (n/N)` with N = scored trials; **Trial Time (s)** = mean of `t_end−onset` for timeouts and `t_click−onset` for hits
(our stored `reaction_time_ms`, `schema.py:83-95`, is exactly Compass's Trial Time; timeouts show elapsed = max time like Compass);
**Reaction Time (s)** = mean of `t_first_gaze_on_target − onset` over trials where gaze ever entered (blank otherwise); **Entries** = mean `entries`.
No Clicks column (U10 omits it). Empty row -> "0% (0/N)" with blank measures (as 08a). A footnote under the table: "n skipped trial(s) excluded.
m planned trial(s) not presented." when applicable, and "Target area = drawn target + 40 px tolerance ring" (the hitbox, `base_task.py:298-307`).

**Reaction Time needs no new field.** `t_first_gaze_on_target_ns` (`base_task.py:391-392`) is the first frame the smoothed pointer is inside the
hitbox: exactly U10's "first gaze entry". It is stored today as `time_to_first_fixation_ms` (misleading name); the UI label becomes Reaction Time.
Probe check: re-deriving it offline from `gaze_stream.csv` (EMA + hitbox emulation) reproduced all 18 stored values to within 30 ms (<= 2 frames at that run's 60 Hz loop). Limitation, footnoted: if gaze already
rests on the new target's position at onset (repeated slot) the value is ~0.

**Eye Metrics** (whole test; U11), Label | Value:
Fixations (count; mean per trial) · Mean fixation duration (ms; median) · Saccades (count) · Mean saccade amplitude (deg) · Mean peak saccade velocity
(deg/s; max) · Scan-path length per trial (deg) · Mean pupil diameter (mm) · Mean pupil change from baseline (mm, %) · Valid gaze during trials (%) ·
Calibration error (deg, px; source measured/loaded). Gaze path and heat map are the map overlays, not table rows.

**Trial-by-Trial table** columns (all sortable by click; first column frozen; horizontal scroll below ~1500 px):
`Trial | Size (deg) | Distance (deg) | Outcome | Trial Time (s) | Reaction Time (s) | Entries | Fixations | Mean fix. dur. (ms) | Saccades | Mean peak vel. (deg/s) | Pupil (mm) | Pupil change (mm)`.
- Trial is 1-based (`trial_id` is 0-based, `schema.py:66`). Outcome = Hit / Not selected / Skipped / (Partial: not presented rows are not listed).
- Size = target diameter in deg from `target_radius_px` (per trial, may be smaller than the preset when a grid cell capped it, research §2) via
  `2*atan(r_mm / D)` with `r_mm = radius_px * mm_per_px` (`metadata.target_size.mm_per_px`; inverse of `target_size.py:192-201`). Scanning radius is the
  icon's hit radius (`target_size.py:67`); label stays "Size".
- Distance = visual angle between this target's start position and the previous presented target's start (canvas mm/px); trial 1 and follow_moving "—".
- Skipped rows: metrics "—", greyed.

### 4D.3 Test Configuration rows (17, like Compass; value "—" when the source is absent)

Built by pure `build_config_rows(snapshot, metadata) -> list[(label, value)]` (no Qt). Rows: Configuration name · Task · Input (eye / gaze+switch / switch;
tracker model + rate) · Trials (planned) · Selection (e.g. "Dwell 800 ms, refractory 500 ms") · Target size (preset + deg + px, plus "capped to X px" if
`TARGET_SHRUNK`) · Layout (grid RxC + gap preset; scanning n icons + arrangement; follow path + speed; static n positions) · Maximum time per trial ·
Pause between trials · Theme · Gaze cursor shown (U5) · Feedback (sound / sparkle) · Gaze smoothing + jitter tolerance · Display (res @ scale, standard
yes/no) · Viewing distance · Calibration (points, mean error, source) · Canvas (px).
Sources: snapshot X1 for what was requested; `metadata.json` for what resolved (`target_size`, `grid_gap`, `calibration_*`, geometry, `schema.py:194-257`).

### 4D.4 New recording (instrumentation that cannot be recovered after the fact)

1. **Entries** — live in `BaseTask.update`, new Qt-free `src/tasks/entry_tracker.py::EntryTracker`, driven by the same `on_target` that dwell uses
   (`base_task.py:389`), so the grid-cell clipping etc. apply. New `TrialRecord.entries: int` (0 if never) -> `trials.csv`. Rules:
   - Invalid frame (`pointer.valid` False): ignored entirely (does not exit, does not enter, does not advance the exit timer).
   - First valid on-target frame while "outside": `entries += 1`, state = inside.
   - Valid off-target frames while inside: exit commits only when the first such frame is >= `exit_hold_ms` (default = dwell hold-grace 120 ms,
     `eye_input.py:36`) old; an on-target frame before that cancels. Re-entry after a committed exit counts.
   - Evidence (EYEGEOM run, 18 trials, same hitbox + EMA emulation): naive rising edges with invalid=off 34 entries; invalid bridged 26; +100 ms hold 21;
     +200 ms hold 20. 120 ms sits on the plateau and equals the number the dwell already uses.
   - Optional events `TARGET_ENTER` / `TARGET_EXIT` (committed only; `trial`, `x`, `y`) for audit (port idea `resources/diki/tasks/base_task.py:161-177`
     with the debounce added; diki's version counts raw edges).
2. **Target position at the end** — `TrialRecord.end_x/end_y` (canvas-normalized target position at `t_end`, `target_position(target, elapsed)`); equals
   start for static tasks. Needed because follow_moving stores only the start (research §4). Plus **`target_track.csv`** (`t_ns,trial,x,y`, follow_moving only,
   written at ~20 Hz) so the path and gaze-vs-target can be drawn exactly; cost ~1.5 kB per trial. (HD12)
3. **`TrialRecord.slot_index`** (grid cell / scanning icon; already on `TargetSpec`, `base_task.py:93-102`, never written).
4. **`metadata.layout_slots`**: `[[x,y],...]` canvas-normalized slot centres at the first tick (`BaseTask.layout_slots`, set by click_grid `:58` and scanning `:76`) so
   the map can draw faint context outlines without re-reading task YAML.
5. **`metadata.raw_clock_offset_ns`** = host-clock time of `all_gaze.csv` `TIME=0`. `record_raw(t_ns, attrs)` already receives the host receive time
   (`recorder.py:142-157`; stamped at `gazepoint_client.py:632`) and throws it away. Keep a running `min(t_ns - time_s*1e9)` (O(1)); copy to metadata in
   `_record_session_end_quality` (`app.py:957`). Then `t_ns(record) = offset + TIME*1e9`. Why: `all_gaze.csv` has no host time, yet velocity/pupil need
   device-rate data aligned to trial windows. Measured on EYEGEOM (5127 matched records): host-minus-device offset spans -0.9..32.9 ms, median +4.3 ms, no drift
   (first/second half 4.0/4.4 ms), so min-latency is within ~5 ms of the median: far below a 300 ms baseline or a frame. Rejected: a `T_NS` column in
   `all_gaze.csv` (header is asserted equal to the vendor's 62 columns, `tests/test_analysis_export.py:51-52`); joining gaze_stream to all_gaze on
   (BPOGX,BPOGY,FPOGD) at read time (works, 99 % matched, but string-format dependent).
6. From 4C: `is_skipped`, `planned_trials`, `completed_trials`, `outcome` (R1, R6).

All additive; `SCHEMA_VERSION` stays 1 (same convention as `schema.py:174-257`). The two readers of `trials.csv` are `csv.DictReader`-based (`exporter.py:36-40`), so extra columns are safe.

### 4D.5 Analysis definitions (pure functions; units fixed)

**Geometry** (`src/data/report_geometry.py`). `Geometry.from_metadata(meta)` reads `screen_*_px`, `screen_physical_*_mm`, `viewing_distance_mm`
(`analysis_export._geometry_from_metadata`, `:407-421`), `canvas_*_px`, `canvas_offset_*_px`, `canvas_units`, `display_scale_percent`, `target_size.mm_per_px`.
- `monitor_to_canvas_norm(x, y) = ((x*screen_w − off_x)/canvas_w, (y*screen_h − off_y)/canvas_h)`; same maths as `base_task.py:240-266`. All four numbers in
  physical px (`canvas_units="physical"`) or all logical (older runs) — the ratio is unit-free, so mixed old/new files are fine. Gaze is monitor-normalized
  (`gazepoint_client.py:263-294`); targets (`trials.csv`) are canvas-normalized. Never mix the two frames without this function (research §0 trap).
- `angle_deg(p, q)` = per-axis mm then `2*atan(chord/(2D))` (`analysis_export.py:343-358`). `px_per_deg = D*tan(1°)/mm_per_px` (41.3 px on the 1920 / 527 mm / 650 mm rig).
- Canvas logical size (for target radius, which is logical px): `canvas_phys * 100 / display_scale_percent` when `canvas_units=="physical"`.

**Trial windows.** `[t_target_shown_ns, t_end_ns]` from `trials.csv`; skipped trials get no metrics.

**Entries / first-entry RT / error-free:** 4D.4-1 and 4D.2. All stored per trial; summary just averages.

**Fixations (vendor definition, from `gaze_stream.csv`).** FPOGID + cumulative FPOGD per frame (valid rows, de-duplicated on `t_ns`; 52 % of rows are repeats
at a 60 Hz loop: probe, 2727 of 5197 zero-dt). For each id seen in the window: `end_i` = last frame time in window, `dur = fix_duration_s` at that frame (cumulative, so
it is clipped at the trial end for free), `start = end − dur`. A fixation counts for the trial iff `onset <= start < t_end` (carry-in fixations belong to the previous
trial; this differs from `compute_trial_fixation_counts`, `exporter.py:158-180`, which counts carry-ins — leave that function alone, `session_metrics.json` unchanged).
Fixation position = mean x,y of its frames (canvas-norm). Vendor rule kept so counts agree with `fixations.csv`/Gazepoint Analysis (median 0.23 s, 1 % < 60 ms in the sample runs).
Per trial: count, mean duration (ms). Whole test: totals, mean, median over all trial fixations. Works for any session that has `gaze_stream.csv` (no all_gaze needed).

**Saccades — I-VT on `all_gaze.csv` (device rate)** (`src/data/saccades.py`, `detect_saccades(samples, geometry, params)`). `samples` = (t_s, BPOGX, BPOGY, BPOGV).
Do NOT use amplitude / inter-fixation gap (degenerate, research §3e). Parameters are defined in ms so they follow the measured rate:
1. Split into segments at invalid samples and at gaps > 75 ms; velocity is never computed across a segment boundary (blinks, FPOGV drops).
2. `dt` = median sample period; `m` = round(33 ms/dt) made odd (n if odd else n+1); `k` = max(1, round(20 ms/dt)). (150 Hz: m=5,k=3. 60 Hz: m=3,k=1.)
3. Running median of width `m` on x and y separately (window shrinks at segment edges).
4. `v_i = angle(p_{i−k}, p_{i+k}) / (t_{i+k} − t_{i−k})` in deg/s.
5. A saccade = run of **>= 2 consecutive** samples with `v >= 50 deg/s` and amplitude `angle(p_{first−k}, p_{last+k}) >= 0.5 deg`.
   Output: onset/offset time, amplitude (deg), **peak velocity** = max `v` in run, mean velocity = amplitude / duration.
6. A saccade belongs to a trial iff its onset is in the trial window (time via X5 `raw_clock_offset_ns`). Per trial: count, mean peak velocity, mean amplitude, scan-path length = sum of amplitudes.
- Why not the textbook 30 deg/s on raw samples: measured intra-fixation noise on this device is huge. Raw sample-to-sample velocity inside vendor fixations: p50 52, p95 203 deg/s;
  after median-3 + central difference p50 34, p95 134. With the proposed filter the intra-fixation p50/p95 are 17-20 / 53-70 deg/s (5 runs). A 30 deg/s threshold with light filtering (median-3, ±1 sample) finds ~800 "saccades" in 37 s
  (808 vs 127 vendor fixations), and still 308 with the proposed filter; 50 deg/s + >= 2 samples finds 113 / 215 / 186 saccades vs 126 / 219 / 205 vendor inter-fixation transitions (EYEGEOM grid / TESTING run3 / EYEGEOM static),
  median amplitude 2.9-3.0 deg, and against vendor transitions >= 1 deg recall 0.92, precision 0.85 (±80 ms match window). Counts agree within ~11 %, which is the only ground truth we have. Whole detection incl. CSV read: 0.26 s on a 12.5k-row file.
- Peak velocity is a **smoothed** peak (a 40 ms window attenuates it; median 70-75 deg/s on ~3 deg saccades vs ~200+ physiological). Label it "peak velocity (smoothed)" in the tooltip and PDF footnote; compare across children on the same device/rate only.
- 60 Hz path adapts (m=3, k=1) but is unvalidated on real 60 Hz data (no real 60 Hz run exists; LIVECHK runs are fake-server). Synthetic fixture covers it; real check deferred to the first 60 Hz session.

**Pupil** (from `all_gaze.csv`, `LPMM/RPMM` mm with `LPMMV/RPMMV`; the stored session mean in `exporter.py:137-154` ignores pupil validity, do not reuse).
- Valid sample: both eyes valid and each in [1.5, 9.0] mm; value = (L+R)/2. Both-eyes-only because L and R differ by ~0.2 mm (3.57 vs 3.80 mean on EYEGEOM) and mixing 1-eye/2-eye samples makes steps.
- Blink mask: drop valid samples within ±100 ms of any invalid sample.
- `pupil_mean` = mean over the trial window. `pupil_baseline` = mean over `[onset − 300 ms, onset)` (the inter-trial blank, ITI 800 ms default; use `min(300 ms, ITI)`); None if fewer than 50 % of the expected samples remain.
  `pupil_change = mean − baseline` (mm) and `%`. Probe on EYEGEOM: change spans −0.19..+0.18 mm across 18 trials (noise-level at this task length: the report must not over-interpret single trials; summary = mean of trial changes).
- Caveat footnoted: onset changes luminance (light reflex ~200 ms after onset), identical across trials of one test, so compare within a test, not across themes/tasks.

**Gaze path** (`gaze_paths(session)` from `gaze_stream.csv`, host-stamped, so no offset needed). Per trial: valid rows in the window, de-duplicated on `t_ns`, converted with `monitor_to_canvas_norm`.
Radial decimation: keep a point when >= 0.15 deg from the last kept or >= 100 ms since it; always keep first/last; cap 400 points (uniform stride). Start a new polyline segment at any gap > 150 ms or invalid run. Coordinates may lie outside [0,1] (off-canvas); keep them, clip at draw time.

**Heat map** (`heat_map(paths, geometry)`). Source: all valid de-duplicated gaze frames inside trial windows only (not ITI). Weight = time to next sample, capped at 100 ms. Bin onto a 96x54 grid over canvas-normalized [0,1]^2 (samples outside are counted into "off-canvas share" and excluded), then separable Gaussian blur with sigma = 1.0 deg (`px_per_deg / bin_px` per axis; radius 3 sigma), normalize so max = 1, round to 3 decimals, store in `report.json` (25 kB). Rendering = colour ramp, alpha proportional to value, values < 0.05 transparent. 1 deg ~ the device's accuracy (calibration error 21 px = 0.5 deg on EYEGEOM) plus fixation dispersion; one named constant to retune.

### 4D.6 Where and when it is computed

- Modules (all Qt-free, pure Python like the rest of `src/data`; `numpy` is a declared dependency but nothing in `src/` imports it, keep it that way for the frozen build): `report_geometry.py`, `saccades.py`, `report_metrics.py` (trial table, summary rows, fixations, pupil, config rows), `report_visual.py` (paths, heat map, map marks), `report_cache.py` (`build_report(session_dir) -> dict`, `load_or_build_report`). Each < 300 lines.
- **At run end** (HD1): in `AssessmentApp._shutdown` after `finalize_all_gaze`/`write_session_metrics` (`app.py:1030-1034`) call `build_report` -> `report.json` in the run folder. Also for "Save partial". The Test Complete dialog's "Save and View Report" then opens instantly. Discarded runs never compute it.
- **On open**: `load_or_build_report` reads `report.json`; if missing, unreadable, or `report_version != REPORT_VERSION` it rebuilds from the raw files and rewrites. Raw files stay the source of truth; the cache pins the algorithm version for reproducibility of clinical numbers. Cost measured: read + I-VT on a 12.5k-row `all_gaze.csv` in pure Python = 0.26 s; build off the UI thread only if > 300 ms is observed on a lazy rebuild.
- `report.json` shape (v1): `{report_version, params:{ivt,entries,pupil,heat,path}, session:{task_id,trials_planned,ended_early,started,subject}, geometry:{...}, trials:[{trial, outcome, size_deg, distance_deg, target:{x,y,end_x,end_y,radius_norm_x,slot}, trial_time_s, reaction_time_s, entries, fixations:{count,mean_dur_ms,items:[[x,y,dur_ms]]}, saccades:{count,mean_peak,max_peak,mean_amp_deg,scanpath_deg}, pupil:{mean_mm,baseline_mm,change_mm,change_pct}, path:[[[x,y],...]]}], summary:{rows,eye}, heat:{w,h,sigma_deg,data}, quality:{valid_share, off_canvas_share, warnings:[]}}`. Never contains personal data beyond the subject id already in the folder name.
- Dev CLI: `python -m src.data.report_cache <session_dir>` prints the JSON (QA on real folders; replaces the ad-hoc `analysis/analyze_session.py` plots, which are whole-monitor and not canvas-aligned, `analyze_session.py:70-78`).
- Time alignment per metric: fixations/path/heat use `gaze_stream.csv` host `t_ns` (same clock as `trials.csv`, `app.py:902-904`); saccades/pupil use `all_gaze.csv` device time + `raw_clock_offset_ns`.

### 4D.7 Target Map

- Frame: **canvas-normalized**, drawn in a panel with the canvas aspect ratio (`canvas_w/canvas_h`, `metadata.canvas_*`), so circles stay circles (08a draws a 4:1 box and the marks squash — walkthrough §3.10 "Differences"). Targets are canvas-normalized already; gaze goes through `monitor_to_canvas_norm`. The HUD toggle is gone after Part C, so the canvas size is constant for new runs; a mid-run resize shows the X6 warning.
- Marks (Targets overlay, default on): hit = filled green circle with the real radius (`target_radius_px / canvas_logical_w`); not selected = red X at the same size; skipped = grey dashed circle; trial number label. Several trials on one slot (a 3x3 grid with 18 trials reuses cells, the "3,9" collision in 08a): group by position within 0.5 radius, label "3, 9", draw each distinct outcome once with a small offset.
- Context (faint, always on with Targets): `metadata.layout_slots` outlines (grid cells, scanning icons) so empty cells are visible; click_static has none.
- Gaze path overlay (default off): per-trial polylines, thin, colour by trial index from a 6-colour cycle; Heat map overlay (default off): 4D.5 grid, alpha ramp. Legend line as in 08a.
- follow_moving: the target track polyline (from `target_track.csv`, faint) with the mark at `end_x,end_y`; click_static / grid / scanning use `target_x,y`.
- Detailed view pane: same widget, one trial: target ring (hitbox radius dashed), gaze path coloured dark -> light by time, fixation circles (radius proportional to duration) numbered in order, onset/selection markers, and a text line "Scan path 12.3 deg · 7 fixations · 6 saccades". Selecting a table row updates it; Up/Down keys work.
- Widget: custom `TargetMapWidget(QWidget)` painting with QPainter from the report dict (no per-sample QGraphicsItems). It exposes `render_to_image(size) -> QImage` for the PDF.

### 4D.8 Print Report (export PDF)

U9: Print Report = export PDF. Recommend **QTextDocument + QPdfWriter** (both in QtGui; no printer dialog, no QtPrintSupport): A4 landscape, 10 mm margins; HTML = header, configuration table, Summary table, Eye Metrics table, the Target Map rendered to a PNG data-URI (all three overlays off except Targets), then the Trial-by-Trial table (repeating header row), footnotes (definitions of Reaction Time / Entries / smoothed peak velocity / ±100 ms blink mask). `QFileDialog.getSaveFileName` default `<Subject>_<Test name>_<YYYY-MM-DD>.pdf` in the subject's folder. Note for QA: a native modal file dialog desyncs the qt-mcp probe (memory: qt-mcp tool reference), let the user click it.

### 4D.9 Old sessions

- All 47 existing folders predate the test list; Part A's list is built from new test records, so they do **not** appear (HD15). No import feature (out of scope).
- The builder is a pure folder reader, so QA can still open any old folder via the CLI or a debug entry. Degradation, all without exceptions: no `entries`/`end_x`/`slot_index` columns -> Entries "—", Error-free row "—" (not guessed), map uses `target_x/y`, follow_moving marks at the start position with note; no `all_gaze.csv` or no `raw_clock_offset_ns` -> saccade and pupil columns "—" (fixations, path, heat map still work from `gaze_stream.csv`); no `outcome` -> derived; no `trials_planned` -> N = rows, banner omitted; legacy `canvas_units=None` -> logical-px maths; missing `target_size` -> Size "—".

### 4D.10 Golden tests (synthetic fixtures; pytest, headless, `tests/test_report_*.py`)

- **G1 EntryTracker**: scripted (t, valid, on) sequences: single clean visit = 1; on/off flicker < 120 ms = 1; off for 200 ms then back = 2; invalid frames in the middle = 1; invalid 2 s while off then on = 1; never on = 0, `first_entry` None; first frame on = 1 at onset.
- **G2 Summary rows**: 8-trial table (3 error-free hits, 1 hit with entries=2, 1 hit with attempts=2, 1 timeout with entries=1, 1 timeout entries=0, 1 skipped) -> hand-computed `% (N)`, Trial/Reaction/Entries means; skipped excluded; empty row prints "0% (0/N)".
- **G3 Geometry**: monitor -> canvas with offset (0,75) and canvas 1640x957 on 1920x1080; round trip; physical vs logical units give identical norm; `px_per_deg` = 41.34 on the reference rig; radius -> diameter deg inverse of `radius_px_for` (5 deg preset round-trips).
- **G4 Saccades (I-VT)**: 150 Hz, fixation A, 5 deg ramp over 40 ms, fixation B -> exactly 1 saccade, amplitude 5±0.3 deg, peak within ±15 % of the analytic smoothed peak; deterministic ±0.3 deg jitter only -> 0 saccades; blink (invalid 100 ms) inside a fixation -> no saccade across the gap; same scenario at 60 Hz (m=3,k=1) -> 1 saccade; below-threshold 0.4 deg step -> rejected by the amplitude floor; clock-offset shift moves the saccade into the right trial window.
- **G5 Pupil**: constant 3.5 mm baseline, trial ramps to 3.8 -> change = mean−baseline; one-eye-invalid samples excluded; ±100 ms blink mask removes edge samples; baseline coverage < 50 % -> None; first trial with no pre-roll -> None.
- **G6 Fixations**: gaze_stream rows with ids and cumulative FPOGD: carry-in excluded, last fixation clipped at trial end, duplicate `t_ns` rows counted once, trial with zero fixations.
- **G7 Path decimation**: straight jittered line -> few points, endpoints kept, <= 400; 200 ms gap -> two segments; off-canvas points retained.
- **G8 Heat map**: one stationary sample at a known position -> peak bin there; total mass preserved (±edge loss < 1 %); duplicates not double-weighted; sigma conversion for two canvas aspect ratios; all samples off-canvas -> empty map + off-canvas share 1.0.
- **G9 Clock offset**: `record_raw` with jittered host times -> `raw_clock_offset_ns` equals the minimum; replay case (no device TIME) -> consistent.
- **G10 Cache**: `build_report` twice -> identical JSON; version bump triggers rebuild; legacy fixture folder (no new columns, no all_gaze) -> `None` fields and no exception; partial run (`trials_planned > rows`) -> banner flag.
- **G11 Live-trial entries**: extend the existing task pipeline test (`tests/test_task_pipeline.py`) with a scripted pointer that visits twice -> `trials.csv` `entries == 2`, `time_to_first_fixation_ms` unchanged.
- **G12 Qt smoke** (offscreen; never measure sizes offscreen, memory: feedback-never-measure-qt-sizes-offscreen): ReportPage populates from a fixture dict, toggles Summary/Detailed, selecting a row updates the pane; PDF export writes a file starting `%PDF` with size > 10 kB.

---

#### Hub decisions proposed

- **HD1 Compute at run end into versioned `report.json`; lazy rebuild on open.** Instant open, reproducible clinical numbers, raw files remain truth.
- **HD2 Entries debounce = ignore invalid frames; exit commits after 120 ms (the dwell hold-grace).** Measured: naive counting inflates 34 -> 20 on a real run.
- **HD3 Reaction Time = existing `t_first_gaze_on_target`; no new movement-onset field.** It is U10's definition; just relabel (`time_to_first_fixation_ms`).
- **HD4 Error-free = hit AND entries==1 AND attempts==1.** Entries alone satisfies U10 in eye mode; the attempts clause keeps switch modes honest.
- **HD5 Skipped trials excluded from every % denominator, shown greyed in Detailed, footnoted.** A skip is the operator's act, not the child's failure.
- **HD6 Fixations use the vendor FPOGID definition from `gaze_stream.csv`, assigned by start-in-trial, clipped at trial end.** Agrees with `fixations.csv`/Gazepoint Analysis; own I-VT fixations would give two competing "fixation" numbers.
- **HD7 I-VT: median 33 ms, velocity span ±20 ms, 50 deg/s, >= 2 samples, >= 0.5 deg amplitude (ms-defined).** Textbook 30 deg/s fails on this device's noise (data above); labelled "smoothed peak".
- **HD8 Align device-rate data via `metadata.raw_clock_offset_ns` (min-latency).** Cheap, exact enough (~5 ms), leaves the vendor-parity file untouched.
- **HD9 Pupil: both-eyes valid, 1.5-9 mm, ±100 ms blink mask, 300 ms baseline, >= 50 % coverage, mm and %.** Per-eye step artefacts avoided.
- **HD10 Heat map from trial windows only, time-weighted, 96x54 grid, sigma 1 deg, stored blurred.** Task-relevant, cheap to render.
- **HD11 Path decimation 0.15 deg / 100 ms, segments split at 150 ms gaps, cap 400 points.**
- **HD12 Record `end_x/end_y` for all tasks plus `target_track.csv` at 20 Hz for follow_moving.** A moving-target map and any pursuit reading need it; ~1.5 kB/trial.
- **HD13 Map in canvas-normalized frame at true aspect ratio, faint `layout_slots` context; PDF via QTextDocument + QPdfWriter, A4 landscape.** No printer dialog; both Qt-core.
- **HD14 Evaluator editable on the report (Setup stays unchanged, U1); name/evaluator/notes stored in the test record (Part A).** One source of truth.
- **HD15 Old sessions do not appear in the Test List; builder degrades gracefully for QA.**
- **HD16 Drop the Session Log panel and the 4-card Results layout; keep only the valid-share warning banner and a Data-quality row in Eye Metrics.** The log stays in the run folder.
- **HD17 Retire `ResultsPage` and the nav "3 · Results" once the Report ships (Part A owns the nav).**

#### Acceptance criteria

- **AD1** For a run folder written by the new code, `report.json` exists, has `report_version`, and re-running `build_report` yields byte-identical JSON.
- **AD2** `trials.csv` has `entries` (int >= 0), `end_x`, `end_y`, `slot_index`; every hit has `entries >= 1`; `time_to_first_fixation_ms` is unchanged for the same input.
- **AD3** G1 passes: invalid-frame dropouts and < 120 ms flicker never raise `entries`; a 200 ms excursion does.
- **AD4** Summary table on a scripted 8-trial fixture matches hand-computed values to 2 decimals (G2); Error-free <= All Selected <= All Trials always.
- **AD5** I-VT on the synthetic ramp finds 1 saccade (5±0.3 deg, peak within ±15 %); jitter-only finds 0; at 60 Hz also 1 (G4).
- **AD6** On the reference real session (`2026-10-05_EYEGEOM_click_grid_run1`, processed through the CLI against a re-recorded or join-estimated offset) detected saccades are within 25 % of vendor fixation count and median amplitude is 2-4 deg (sanity, not a golden).
- **AD7** Pupil per-trial change equals mean−baseline on the fixture; a trial without a valid baseline shows "—", never 0.
- **AD8** Target Map: marks sit at `target_x/y` of the canvas frame; a gaze sample at known monitor position lands at the expected canvas-normalized point for offset (0,75); aspect ratio equals metadata canvas aspect.
- **AD9** follow_moving report draws the target track and the mark at `end_x/end_y` (not the start).
- **AD10** Every metric column renders "—" (not 0, not an exception) for the legacy fixture folder (4D.9).
- **AD11** Report page: Summary opens first; View Details toggles to Detailed and back; selecting a trial row updates the pane; Save persists name/evaluator/notes via the host callback; Cancel does not; run data cells are read-only.
- **AD12** Print Report writes a valid PDF containing config, summary, eye metrics, map image and the full trial table; filename defaults as in 4D.8.
- **AD13** Opening a report for an 18-trial real run takes < 300 ms from click to painted page when `report.json` exists (measured live, not offscreen).
- **AD14** Banner shows "Ended early — n of N trials" for a partial run; a resized-canvas run shows the X6 warning.
- **AD15** Existing tests stay green (`exporter`, `analysis_export`, `recorder`, `task_pipeline`); `session_metrics.json` content unchanged.

#### Plan steps (ordered, implementer-sized)

1. **[wireframe-first]** wiremd wireframes `docs/wireframes/report-summary.md` and `report-detailed.md` (header, left column, summary table, map + toggles, eye table, detailed table + pane, footer), including the PDF page sketch; hub approval before any UI code.
2. **Recording additions** (4D.4): `EntryTracker` + `BaseTask` wiring + `TrialRecord` fields/`csv_header` + `end_x/end_y` + `slot_index` + `target_track.csv` writer (follow_moving) + `metadata.layout_slots` + `raw_clock_offset_ns` in recorder/app. Tests G1, G9, G11. Coordinate the `trials.csv` header change with 4C's `is_skipped` column in one commit (R6).
3. **Geometry + saccades** (`report_geometry.py`, `saccades.py`) with G3, G4.
4. **Trial metrics** (`report_metrics.py`: trial table, summary rows, fixations, pupil, config rows, quality) with G2, G5, G6.
5. **Visual data** (`report_visual.py`: paths, heat map, map marks) with G7, G8.
6. **Cache + hook** (`report_cache.py`, `_shutdown` call, CLI) with G10; run the CLI on 3 real folders and the fake-server session and record the numbers in the SPEC impl log (AD6 sanity).
7. **ReportPage + TargetMapWidget** per the approved wireframe; wire host callbacks (Part A); G12 smoke test. Live check with qt-mcp (maximize first, screenshot the window not widgets).
8. **Print Report** (4D.8), G12 PDF check.
9. **Live validation with the user** using a real subject-run and a fake-server run: compare entries and Reaction Time to what was seen on screen, check heat map / path / selected-trial pane, print a PDF. Update SPEC + memory.

#### Open questions

None blocking. Two points the hub may want the user to confirm when the SPEC is shown: (a) the evaluator field lives only on the report (U1 keeps Setup unchanged); (b) peak saccade velocity is shown as a smoothed value (HD7) and is comparable only across children on the same device and sample rate.

## 5. Scope

**In:**
- The per-subject Test List and its on-disk store (4A).
- The full-page configuration with named configurations and Preview (4B).
- The Start page, Practice, the HUD-less run screen with Pause / Skip / Quit and the status
  line, and the run-end dialogs with Discard (4C).
- The per-test report: Summary, Detailed, Target Map with gaze-path and heat-map overlays, eye
  metrics, PDF (4D).
- The recording additions those parts need (4C.9, 4D.4).
- Removal of `OperatorPanel`, `TasksPage`, `ResultsPage`, the Hide HUD feature and the
  per-task dicts in `DashboardWindow`.

**Out:**
- Multi-Test Report and copying tables to the clipboard (U9).
- Traditional Chinese text (U12).
- Importing old sessions (U16).
- New task options beyond today's (U4).
- Changes to the Setup tab (U1).
- Responsive layout below 1920x1080 @100 % (SPEC-display-standard-check; pages scroll instead).
- Auto-pause on tracker loss (HC9, a possible follow-up).

**Kept working:** the standalone `python -m src.main --task X --gui` path (HB11, AC15).

## 6. Acceptance criteria

The testable criteria are listed per part:
- **4A:** AA1–AA16. AA16 is amended by R2; AA17 is void (R5).
- **4B:** AB1–AB20. The Test Name length in AB11 follows R10.
- **4C:** AC1–AC16. AC4's seed clause follows R3: practice differs from the recorded order
  because it uses another seed.
- **4D:** AD1–AD15.

Cross-part criteria, added at the merge:

- **AX1** End-to-end on the fake server (port 4250):
  1. Add 2 Grid Click tests.
  2. Configure test 1 with a new named configuration.
  3. Preview it with the mouse.
  4. Start it, Practice, then Start.
  5. Pause, Skip once, then let it complete.
  6. Save and View Report.

  Expected:
  - the report shows the named configuration, 1 skipped trial excluded, and Entries and
    Reaction Time filled;
  - the Test List row reads "Done <date>" and is locked;
  - Copy Test gives an unrun copy with the same configuration and a **different seed**;
  - the subject's `sessions/` holds exactly one new run folder.
- **AX2** Restart the app and type the same Subject ID. The list, statuses and report open
  exactly as before the restart.
- **AX3** `grep` in `src/` finds no `OperatorPanel`, `TasksPage`, `ResultsPage`,
  `_task_overrides`, `_task_live_overrides`, `_task_selected_profile` or
  `_task_session_dirs`. The full pytest suite is green.
- **AX4** Every new page, screenshotted as a whole window, maximized at 1920x1080 @100 %
  (qt-mcp), shows no clipping and its footer is visible. Pages tall enough to need it scroll at
  `QT_SCALE_FACTOR=1.5`.
- **AX5** Real-device check with the user as subject: Practice, then a recorded Grid Click test
  and a Follow & Click test. Expected:
  - the report's Entries and Reaction Time match what was seen;
  - the gaze path and heat map overlay sit on the targets;
  - the pupil and saccade columns are filled;
  - the PDF opens.

## 7. Plan (phases)

Each phase is one or more `spec-implementer` passes (Sonnet 5.5, never commits). The hub reviews,
runs pytest, live-checks with the user, and commits on the user's OK. **WF** marks a gate where
a wiremd wireframe needs the user's approval first.

| Phase | Content (part steps) | WF | Depends on |
|---|---|---|---|
| P0 **DONE 2026-10-06** (`cf2183c`) | User approves this SPEC (§3.2 and the per-part hub decisions); the hub commits it | — | — |
| P1 **DONE 2026-10-06** (`6d21642`) | **Store and path safety:** `safe_subject_dirname` (A1); `task_info.py` (A2); `subject_tests.py` with `seed`, `evaluator`, R1 names (A3); `test_id` / `test_name` / `seed` in metadata (A4) | no | P0 |
| P2 **DONE 2026-10-06** (`b2691db`) | **Run engine, no UI:** `is_skipped`, `pause` / `resume` / `skip_trial`, seed plumbing, new metadata fields, `NullRecorder`, `run_mode`, `discard_session`, `tracking_status`, `task_instructions`, `run_blockers`, the R8 pre-roll (C1); `MouseGazeSource` (B6) | no | P1 |
| P3 **DONE 2026-10-06** (`b2691db`) | **Recording additions:** `EntryTracker`, `entries` / `end_x` / `end_y` / `slot_index`, `target_track.csv`, `layout_slots`, `raw_clock_offset_ns` (D2). The `trials.csv` header changes in the same commit as P2's `is_skipped` if possible (R6) | no | P2 |
| P4 **DONE 2026-10-06** (`f13091e`) | **Analysis modules:** geometry, saccades, trial metrics, visual data, cache + `_shutdown` hook + CLI (D3–D6); run the CLI on real folders and log the numbers | no | P3 |
| P5 **DONE 2026-10-06** (`29948ad`) | **Settings layer:** structural `bool` kind, `config_groups_for_task`, profile schema v2 with `name`, `list_named_configurations`, the extracted fit hints, the bool branch in `TaskSettingsDialog` (B2–B4) | no | P1 |
| P6 **DONE 2026-10-06** (`f9c979e`) | **Wireframes:** `test-list.md` (A5), `task-config.md` (B1), `start-test.md`, the `run.md` rewrite and `run-end.md` (C2), `report-summary.md` / `report-detailed.md` (D1). All replace stale `tasks.md`, `task-settings.md` (dashboard part) and `run.md` | **WF** | P0 (can run in parallel with P1–P5) |
| P7 **DONE 2026-10-07** (`5cfb52b`) | **Widgets:** `TaskConfigPage` (B5); `RunBar` + new `TaskRunView` + `TaskCanvas.set_paused`, deleting `operator_panel.py` (C3); `AssessmentApp` run modes and quit flow (C4); `StartTestPage` (C5); end dialogs (C7); `ReportPage` + `TargetMapWidget` (D7); Print Report (D8). Offscreen tests only | after P6 | P2–P6 |
| P8 **DONE 2026-10-07** (`b29df37`) | **Dashboard integration:** `SubjectTestListPage` + `AddTestDialog` (A6, no bridge needed); flow state and nav lock (C6); Configure / Preview / Run / Report wiring (B7); retire `TasksPage`, `ResultsPage`, nav "3 · Results"; cleanup (C8); README and `docs/DATA_SCHEMA.md` | after P6 | P7 |
| P9 **part 1 DONE 2026-10-07** (fake server; fixes P9a `dc1d025`, P9b `4f0145f`, §7.1); **part 2 RUN 2026-10-07** (findings V1–V5 = P9c, §7.1; Follow & Click re-run pending); **P9c OPEN** | **Live validation:** fake server (AX1–AX4, A7, B8), then the real device with the user as subject (C9, D9, AX5). Then, **only on the user's explicit OK at that moment**, delete the old pre-redesign session folders (U16). Memory update | — | P8 |

P1–P5 have no UI, so they can be reviewed and committed one by one before the wireframes.

### 7.1 P9 part 1 findings and the P9a fix pass (2026-10-07)

The fake-server half of P9 (AX1–AX4, A7, AB13–AB18, quit / discard / partial save) passed
with the findings below; the full results are in the §10 entry of 2026-10-07. **User decision
2026-10-07: fix all five now (P9a, one spec-implementer pass), the hub re-checks them live on
the fake server, then the real-device half of P9.** The theme vertical-header padding (§9
P8c point 1) is **kept as it is** (user, from a real-font screenshot: Test List rows ~30 px for
16 px text read well); the two local overrides stay.

| Id | Finding (seen live, 1920x1080 @100 % and `QT_SCALE_FACTOR=1.5`) | Fix wanted | Acceptance |
|---|---|---|---|
| FX1 | `AddTestDialog`'s task list (`addTestList`, rich-text `QLabel` item widgets) paints a near-black background, so the task names are unreadable (confirmed on an OS capture, not only `grab()`). The "Discard your changes?" `QMessageBox` draws its buttons dark grey too. Same family as the earlier dark-mode palette leak in dialogs. | Every dialog of the new flow (Add New Test, rename / config-name, Discard changes, quit question, partial save, Test Complete, Delete) renders on the light theme: light list/base background, readable text, themed buttons, whatever the Windows app colour mode. Fix it at the theme / dialog level, not per widget colour hacks. | An offscreen test pins the palette / stylesheet the dialogs get (e.g. `addTestList` base colour is light, item text dark); hub re-checks live with an OS capture. |
| FX2 | Report tables are too short with real fonts: Summary of Results shows 3 of its 4 rows ("All Trials" is cut), Eye Metrics loses its last row. Same at 1.5×. Likely `FitTable` (`src/ui/report_tables.py`) computes its height from offscreen metrics / a fixed row height instead of the real `rowHeight()` sum + header + frame. | `FitTable` height = header + every row's real height + frame, recomputed when fonts / scale / content change, so every row is fully visible with no inner scroll bar. Applies to all `FitTable`s (configuration, summary, eye metrics). | Test with a non-default font size that every row of each report `FitTable` lies inside the viewport; hub re-checks live at 100 % and 1.5×. |
| FX3 | Test List opens with a focus frame on row 1 but **no selection**, so every action button except Add is disabled while a row looks selected. | When the list opens or reloads, the selection matches the focus: select the last-used test if it is still listed, else the first row; with no tests, nothing. (4A.4: "the selection follows the test through a sort or reload".) | Test: open the page with tests, the current row is selected and the buttons follow the 4A.4 matrix for it. |
| FX4 | At Windows scaling ≠ 100 % the target-size / cell-gap hints on the configuration page show **logical** px ("Small — 3° (≈83 px)" at 1.5×, where the target is 124 physical px). `config_widgets.py:81,85`. | Show physical px (logical × device pixel ratio), matching the metadata's physical canvas units (SPEC-display-scaling §8.8). | Test: with a device pixel ratio of 1.5 the hint shows the physical value. |
| FX5 | The title-bar app name and nav labels are barely readable: `TitleBar` (P8a, `dashboard_flow.py`) is a plain `QWidget` subclass, so the `QWidget#wtmhTitleBar { background: #12374A }` rule does not paint (no `WA_StyledBackground`) and the light `TITLEBAR_TEXT` lands on the light page. | The title bar paints its navy background as designed (e.g. `setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)`), so the brand and nav text are readable. Verify the attribute name with qt-docs. | Test that the title bar has the styled-background attribute; hub screenshot live. |

**P9a DONE 2026-10-07** (`dc1d025`): FX1–FX5 verified live on the fake server at
100 % and 1.5× (OS-level captures), hub pytest 1997 passed / 2 skipped. The config page's
amber fit hint shows physical px too (§9 P9a point 3).

**P9b (user 2026-10-07, after the P9a live re-check; fix before the real-device half):**

| Id | Finding (OS capture, 100 % and 1.5×) | Fix wanted | Acceptance |
|---|---|---|---|
| F6 | Add New Test dialog: every task's grey description line (2nd line of the rich-text item) is clipped at the bottom; descenders of "empty", "lights up", "among" are cut. The list rows are shorter than the two-line label. | Each item is as tall as its label needs (size hint from the label's real height, re-measured on font/scale change), so both lines show in full. | Test: every item's height >= its label widget's `sizeHint().height()` (with a non-default font); hub re-checks live. |
| P1 | Disabled primary buttons (Run Test with no runnable row, Add before a task is picked) are pale cyan with dark-teal text and read as an enabled soft button. | A clearly "off" disabled look for `wtmhPrimary` (and `wtmhGhost`): neutral grey fill / border with muted grey text, distinct from every enabled state; contrast still legible. | Test pins the `:disabled` rules; hub screenshot. |
| P2 | Configuration page: the outline of an unchecked radio indicator is very faint (light grey on white), so the other choices barely show. | Darker indicator outline for unchecked radios (and check boxes, if they share the rule) inside the dashboard theme. | Hub screenshot at 100 %. |
| P3 | Report Target Map: the red X of a not-selected target is drawn across the trial number(s), so "6", "3", "1" are hard to read. | Numbers stay readable over the X (e.g. a small white badge behind the label, drawn after the X). | Offscreen paint test or pixel check; hub screenshot. |
| P4 | Detailed view, selected-trial map: the "S" start marker is ~8 px; the path lines cross the numbered fixation circles; the newest end of the path ramp is a very pale cyan on white. | A larger S marker (legible label), fixation number badges drawn above the path, and a darker light end of the time ramp so the whole path stays visible on white. | Hub screenshot. |

Scope of P9b: only F6 and P1–P4; same off-limits files as P9a. No app-wide palette (backlog).

**P9b DONE 2026-10-07** (`4f0145f`): all five verified live at 100 % and 1.5×; hub pytest 2029 passed / 2 skipped.

**P9c (user 2026-10-07, from the real-device half of P9; decisions taken with the user, fix
after the remaining real-device checks so later findings join the same pass):**

| Id | Finding (real GP3 HD, subject P9REAL, 1920x1080 @100 %) | Fix wanted (user decision) | Acceptance |
|---|---|---|---|
| V1 | The Target Map legend under the map ("Green circle = hit · red X = not selected · …") is small grey text with no highlight; hard to read. | A **symbol legend box**: light tinted box under the map; each symbol drawn as a small icon (green hit circle, red X, dashed skipped ring, faint layout circle) next to a short label, plus "Numbers = trials shown at that place"; body text size, dark text. Same legend in the PDF. | Test that the legend widget exists with its four entries; hub screenshot (app + PDF). |
| V2 | The gaze path draws the raw device gaze (every `gaze_stream.csv` sample, unsmoothed), so fixational tremor makes the Summary map a jumbled scribble. | **Summary map: a fixation scanpath** — one dot per fixation, joined by straight lines in time order, per trial colour as now. **Detailed per-trial view: the full path, smoothed** with the same filter as the on-screen gaze cursor (α from the run's `metadata.settings.live["dwell.smoothing.alpha"]`, 0.22 by default; unsmoothed if `dwell.smoothing.enabled` is false), keeping the numbered fixation circles. `report.json` carries both (new key for the scanpath; keep the raw path params documented). | Golden test: scanpath points = fixation centroids in order; smoothed path of a noisy synthetic trace has lower point-to-point jitter than raw; hub screenshot on the P9REAL session. |
| V3 | The PDF export is A4 landscape. | **A4 portrait**; the layout reflows (configuration, summary, map, eye metrics stacked) with no clipping. | Test on the page layout orientation; hub opens the PDF. |
| V4 | Add New Test dialog: the task rows sit tight against each other and the list leaves empty space at the bottom. | More spacing between task rows; the list fills the dialog's available height; a vertical scroll bar appears when more tasks exist than fit (future task types). | Test: item spacing > 0 and the list's vertical scroll policy is as-needed; hub screenshot. |
| V5 | Time values shown in "ms" are hard to read for most people. | **Every on-screen and PDF text shows seconds** (e.g. "Dwell 0.8 s, refractory 0.5 s"): configuration page labels/sliders, report tables and PDF, Start page, status lines, dialogs. **Data files keep ms** (CSV column names such as `reaction_time_ms`, JSON fields, `report.json` params) so analysis, vendor-parity exports and old sessions keep working. | `grep` for user-visible " ms" strings in `src/ui` finds none (comments/identifiers excepted); tests on the formatters; hub screenshot. |

Also seen, NOT in P9c scope (pre-existing, separate item): the Setup calibration banner's
"mean error 74px" is the vendor `AVE_ERROR` summary while the per-point breakdown shows
6–25 px; the two disagree on the page.

Scope of P9a: only FX1–FX5. Out of scope: anything else in §4, Setup's layout (U1), the
run canvas, data files. `configs/default.yaml` and `configs/local_state.json` are off-limits.

## 8. Impl log

### 2026-10-06 — P1 (A1-A4), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. `configs/default.yaml` and `configs/local_state.json` untouched.

**Files changed**
- `src/engine/session_naming.py`: `safe_subject_dirname()` (4A.9); `next_run_number` and `next_session_id` use it.
- `src/engine/settings_profile.py`: `subject_settings_dir` uses it; `TESTS_DIRNAME = "_tests"` added and listed in `known_subject_ids`.
- `src/ui/setup_page.py`: `_subject_calibration_dir` uses it (one line plus the import; a named A1 call site).
- `src/engine/task_info.py` (new): `TASK_INFO`, grid label now "Grid Click". `src/ui/tasks_page.py` and `src/ui/results_page.py` import it from there (the only UI edits).
- `src/engine/subject_tests.py` (new, 418 lines) and `src/engine/subject_test_record.py` (new, 211 lines): the store. See "Deviations / judgement calls" for the split.
- `src/data/schema.py`: `SessionMetadata.test_id`, `test_name`, `seed` (all default `None`).
- `src/app.py`: `AssessmentApp(test_id=None, test_name=None, seed=0)`; the three go into `SessionMetadata`, and `seed` is forwarded to `build_task`.
- Tests (new): `tests/test_safe_subject_dirname.py` (AA13), `tests/test_subject_tests.py` (AA1-AA3, R3, R9, R1, R4/R5, atomic writer, names), `tests/test_subject_tests_lifecycle.py` (AA4-AA8, AA14), `tests/test_task_info.py` (A2), `tests/test_session_test_link.py` (AA11 first half).

**What was done**
- A1: AA13 passes for `..\x`, `../x`, `A/B`, `CON`, `con.txt`, `x.`, `..`, blank, control characters, 200 characters, a decomposed accent; ordinary IDs (including `TESTING`) come back unchanged, so `_settings/TESTING` and `_calibrations/TESTING` still match.
- A2: done as written.
- A3: record fields = 4A.2 plus `evaluator` (R9), `seed` (R3), and R1's `planned_trials` / `completed_trials` / `outcome`. `status` stays `not_done` / `done` / `ended_early`. Seed is drawn in [0, 999_999] on create and again on Copy Test (the draw is repeated until it differs from the source's seed). Name, evaluator and notes are editable in every state; configuration and a second `record_result` raise `TestLockedError` unless Not Done. `validate_test_name` is 1-60 characters, no control characters, unique per subject case-insensitively on the trimmed value. No `mark_discarded` (R4), no legacy import (R5). `allowed_actions` has the 4A.4 matrix without the `run_blocked` asterisk (R2). Atomic writer: `.tmp` beside the target, flush + fsync, `os.replace` with 1 + 5 attempts at 40 ms on `PermissionError`, any `OSError` becomes `TestStoreError` and the temp file is removed. Tolerant reader: unreadable / non-dict / missing id / id differs from the file name / unknown task are skipped and counted; a subject mismatch (casefold) is skipped silently; an unknown status reads as done with a `session_dir`, else not done. Delete is a move into `_deleted/`.
- A4: a run started with `test_id`, `test_name`, `seed` writes all three to `metadata.json`; a standalone run writes `null`, `null`, `0`.

**Tests added:** 112 (`tests/test_safe_subject_dirname.py` 59, `tests/test_subject_tests.py` 24 + `_lifecycle.py` 22, `tests/test_task_info.py` 3, `tests/test_session_test_link.py` 4).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline before the change `728 passed in 117.44s`; after `840 passed in 124.02s`. No failures, so the known `test_config_merges_task_over_default` failure did not show up on this machine today.

**Deviations / judgement calls (none changes a SPEC decision)**
1. The store is split in two modules to respect the 500-line rule: `subject_test_record.py` (dataclass, parser, name rules) and `subject_tests.py` (errors, disk, actions). `subject_tests` re-exports every public name, so callers import only from `subject_tests`.
2. `allowed_actions(test)` takes no `run_blocked` parameter at all (R2 makes it meaningless). AA8 is therefore parametrised over the four selection states only.
3. `created_at` has microsecond precision, kept strictly increasing within the process. The 4A.2 example shows whole seconds, but the Add dialog creates up to 10 tests at once and `list_tests` sorts by `(created_at, test_id)`, so with seconds the order of tests created together would be decided by the random id.
4. `origin` is `created` or `copied` only (`imported` dropped with the legacy import, R5).
5. `AssessmentApp(seed=...)` is forwarded to `build_task` in P1, not only recorded, so `metadata.seed` cannot disagree with the order that was drawn. Default 0 is today's behaviour. P2's "seed plumbing" item for `AssessmentApp` is therefore already done; see §9.
6. Store functions raise `ValueError` (carrying the `validate_test_name` text) for a bad name, blank Subject ID, unknown task, non-dict configuration, bad trial counts, or a session folder that is not directly inside `output_root`. An unknown / missing / other-subject test id raises `TestStoreError`. The SPEC names only `TestStoreError` and `TestLockedError`.
7. A Copy Test name from a long custom name is truncated so that the suffix fits in 60 characters.
8. `next_session_id` also uses the safe name. Otherwise the run-number scan and the created folder would disagree for an unusual ID.
9. `TestStoreError`, `TestLockedError` and `TestListLoad` carry `__test__ = False` so pytest does not try to collect them.

**Noticed, not changed**
- `TASK_INFO["click_grid"]` description still says "a visible 3x3 board" (the SPEC names only the label).
- `run_headless_replay` (`src/engine/task_runner.py`, CLI `--replay` only) builds `replay_<task>_<subject>` from the raw `--subject`. It is not one of the four A1 call sites, so it still accepts an unsafe ID.

**Left undone:** nothing in A1-A4. A stray empty file `str` (an arrow in a tool input) appeared in the repo root during the run and was removed.

### 2026-10-06 — P2 (C1 engine + data side of `run_mode` + R8 pre-roll + B6), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged (the hub holds P2 and commits it with P3, R6). `configs/default.yaml` and `configs/local_state.json` untouched. Branch confirmed before the first edit.

**Files changed**
- `src/data/schema.py`: `TrialRecord.is_skipped` (last column of `csv_header` and `as_row`; no `outcome` column, R6); `SessionMetadata` gains `run_mode`, `config_name`, `planned_trials`, `completed_trials`, `skipped_trials`, `interrupted_trials`, `pause_count`, `outcome`, `ended_by`, `ended_ns` (all `None` by default, additive, `schema_version` stays 1).
- `src/tasks/base_task.py`: `pause(t_ns)` / `resume(t_ns)` / `skip_trial(t_ns)`, the `_finish_trial(skipped=...)` path, the pre-roll gate (`preroll_ms` ctor argument, `_preroll_over`), a defensive idle frame when `update` is called while paused, `pause_count` / `interrupted_trials` counters and a `trial_number` property.
- `src/data/exporter.py`: `summarize()` adds `n_skipped`; `hit_rate` is hits over (trials minus skipped); an older `trials.csv` without the column reads as 0 skips.
- `src/data/recorder.py`: `NullRecorder` (same public surface as `SessionRecorder`, every call a no-op, `session_dir = None`).
- `src/engine/run_mode.py` (new): `RECORD/PRACTICE/PREVIEW`, `validate_run_mode`, `is_recorded`, `run_seed` (record = the test's seed; practice = `1_000_000 + practice_index`; preview = `PREVIEW_SEED = 2_000_000`), `preroll_ms` (500 for a recorded run, else 0), `outcome_fields`, `outcome_log_line`, `apply_outcome`.
- `src/engine/session_files.py` (new): `discard_session(session_dir, output_root)` with every 4C.8 guard, `SessionDiscardError`.
- `src/engine/tracking_status.py` (new): `GAZE_LOST_AFTER_S = 1.0`, `tracking_status(connected, seconds_since_valid)`, `run_status_line(...)`.
- `src/ui/task_instructions.py` (new, Qt-free): `build_instructions(task_id, cfg, values=None)` returning `Instructions(heading, steps, note, clinician)`, `format_seconds`.
- `src/ui/setup_page.py`: `run_blockers()` (the six 4C.2 sentences, in that order); `can_continue()` is now `not self.run_blockers()`. No layout change.
- `src/inputs/mouse_gaze.py` (new): `MouseGazeSource` (4B.6.3 contract, `bind_canvas`, injectable `cursor_pos` for tests).
- `src/engine/task_runner.py`: `build_task(..., preroll_ms=0.0)` forwarded to the task (headless replay unchanged: 0).
- `src/app.py`: `AssessmentApp(run_mode="record", practice_index=0, config_name=None)`; run mode validated first; practice/preview get a sentinel session id (no run-number scan), a `NullRecorder`, no `session_dir.mkdir` / `calibration.json`, no calibration timing log, no `GazeDropoutLog`; `_shutdown` now calls the new `_write_session_files()` (the old body, plus `apply_outcome` before `recorder.close()`) for a recorded run only, then stops an owned client and calls `on_finished` as before; `metadata.run_mode`, `config_name` (also `settings.config_name`, R7); the Skip handler calls `task.skip_trial` instead of the `_trial_start_ns = 0` hack. The literal `clear_raw()` / `open_all_gaze(` / `open_eye_geometry()` lines and their order in `__init__` are untouched (the source-order test passes).
- Tests (new): `tests/test_run_engine.py` (24), `tests/test_run_mode.py` (26), `tests/test_session_files.py` (26, of which 2 skip where symlinks cannot be created; the same refusals are also tested with the link check simulated), `tests/test_tracking_status.py` (20), `tests/test_task_instructions.py` (48), `tests/test_run_blockers.py` (7), `tests/test_mouse_gaze.py` (22), `tests/test_run_modes_app.py` (20).

**What was done**
- AC9 (engine side): a pause in `WAIT_INPUT` drops the trial unrecorded, re-presents the same target with a fresh clock and the same `trial_id` (N and the csv stay contiguous), emits `TRIAL_INTERRUPTED {trial, reason, elapsed_ms}` and `PAUSED {trial, interrupted}` / `RESUMED`; a pause longer than `timeout_ms` creates no timeout; a pause in the ITI keeps the remaining ITI; a pause during the pre-roll does not eat it.
- AC10 (engine side): a skip sets `is_skipped`, leaves `is_hit` / `is_timeout` 0 and `t_click_ns` blank, plays neither hit nor miss feedback, emits `SKIPPED`; `summarize()` reports `n_skipped` and keeps it out of `n_timeouts`.
- AC4, AC6, AC16 and AB13/AB14 (data side) through `AssessmentApp`: a practice run leaves `sessions/` byte-identical (a folder with a finished run, `_diagnostics` and `_settings` in it), does not mutate the caller's dicts, uses `1_000_000 + k`; a practice then a record keep `all_gaze.csv` to the record run's own records and start it at `TIME 0`; a preview with a `MouseGazeSource` writes nothing, uses `PREVIEW_SEED`, and a mouse hover of the dwell length on the target scores a hit while a mouse off the canvas never does.
- R8: with `run_mode="record"` the first frame starts a 500 ms pre-roll; `TARGET_SHOWN` of trial 1 comes at least 500 ms after the first tick (tested with the real clock; the test fails with the pre-roll at 0). Practice and preview start trial 1 on the first tick. Gaze and raw records are recorded during the pre-roll because the app records before it calls `task.update`.
- 4C.9: the outcome fields are written at the end of a recorded run (`planned_trials` = `len(task.targets)`, `completed_trials` = rows in `trials.csv`, skipped included) with the two `session.log` lines.

**Tests added:** 193 (191 pass, 2 skip).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline before the change `840 passed in 125.17s`; after `1031 passed, 2 skipped in 130.75s`. No failures (`test_config_merges_task_over_default` did not show up on this machine today). `ruff` is clean on every new file and every changed region (the two findings left in changed files, `app.py` I001 and `exporter.py:115` B905, were there before).

**Deviations / judgement calls (none changes a SPEC decision)**
1. **Seed arguments.** `AssessmentApp` takes `practice_index` (k) and derives the seed from `run_mode` itself (`run_seed`), so the `seed` argument is ignored for practice and preview. 4C.4 reads as if the call site computes `1_000_000 + k`, 4B.7 passes no seed for a preview. If P8 should pass the seed instead, drop the `run_seed` line in `AssessmentApp.__init__`.
2. **"Blank" pre-roll.** The canvas shows no target for the pre-roll, with the persistent scene (grid cells, icons) drawn exactly as in the ITI, not an empty canvas. That makes trial 1's baseline the same screen as every later trial's ITI baseline. A fully empty canvas would be a `TaskCanvas` change (P7).
3. **HUD fields kept.** `hud_hidden_at_start` and `hud_toggle_count` stay in `SessionMetadata` (HC13 / 4C.9 removes them): `AssessmentApp`, `DashboardWindow` and `tests/test_hud_hide_toggle.py` still use them until P7 deletes the HUD. **Deferred to P7.**
4. **Pause is not wired into the app.** `AssessmentApp._set_paused` still only sets the old `_paused` flag (so the HUD's Pause button behaves as before, including the wall-clock timeout after a long pause). Wiring `task.pause` / `resume`, the paused tick (drain and discard the raw queue, no `gaze_stream` row) and the Paused canvas is the P7 paused-tick work (C4). `pause_count` / `interrupted_trials` are written to metadata (0 today). Skip *is* wired: the HUD's "Skip trial" button now records a skip, not a forced timeout (4C.6 says it replaces the hack).
5. **`outcome` / `ended_by` today.** Anything other than the task running out of trials (`task.is_done`) is written as `ended_early` / `operator_quit`, which is what End task and Esc are now. P7's quit flow (confirm, Save partial / Discard) does not change these values.
6. **`run_mode` value.** `metadata.run_mode` is `"record"` for a recorded run (4C.4's `record | practice | preview`); `metadata.config_name` is written both at top level (4C.9) and as `settings.config_name` (R7).
7. **Not in the SPEC text:** a `session.log` line "Pre-roll: 500 ms blank before trial 1." for recorded runs; `BaseTask.trial_number`; `apply_outcome`; `build_task(preroll_ms=...)`; `run_status_line` covers the record and practice wording of 4C.5 only, not the Preview wording of 4B.6.6 (that belongs with the Preview bar, P7/P8).
8. **File sizes.** `src/tasks/base_task.py` 526 to 639 lines (it was already over 500; the pause / skip / pre-roll code from 4C.6 and R8 is in it as the SPEC names `BaseTask.pause/resume/skip_trial`), `src/app.py` 1092 to 1135 (+43: the logic lives in `src/engine/run_mode.py`, `NullRecorder` and the helper `_write_session_files`), `src/ui/setup_page.py` 1124 to 1141. New files are all under 130 lines.
9. `discard_session` returns the number of files removed, raises `SessionDiscardError` (a `ValueError`) for a missing folder rather than succeeding silently, and also refuses Windows junctions.
10. `build_instructions(task_id, cfg, values=None)`: `cfg` is the merged run config (planned trials from `cfg["task"]["trials"]`, "all" if absent), `values` the live settings keyed as `initial_live_values`, partial or omitted (missing keys come from `cfg`). The `NOTE:` label is part of `note`; steps are unnumbered sentences (the page numbers them).

**Left undone (belongs to later phases):** the app-level paused tick and the Quit flow / `RunResult` / end dialogs (P7); removal of the HUD fields, handlers, live-settings code (P7); P3 recording additions (`entries`, `end_x`, `end_y`, `slot_index`, `target_track.csv`, `raw_clock_offset_ns`); no `StartTestPage`, dashboard wiring or wireframe. Five empty stray files named after Python return annotations (`BaseTask`, `FrameResult`, `None`, `bool`, `practice`) appeared in the repo root during the run (the arrow-in-tool-input quirk, here from code in edits) and were removed; `git status` shows only the files listed above.

### 2026-10-06 — P3 (4D.4 recording additions), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed before the first edit. P2's uncommitted changes were built on, not reverted (the hub commits P2 + P3 together, R6). `configs/default.yaml` and `configs/local_state.json` untouched. No live run, no app launch.

**Files changed**
- `src/tasks/entry_tracker.py` (new, 82 lines): `EntryTracker(exit_hold_ms)` with `entries`, `first_entry_ns`, `inside`, `reset()`, `update(t_ns, valid, on_target)` (returns `"enter"` / `"exit"` / `None`); `DEFAULT_EXIT_HOLD_MS = DwellConfig().hold_grace_ms` (120), so the hold is the dwell's own grace by construction.
- `src/tasks/target_track.py` (new, 31 lines): `TrackThrottle` (due on a trial's first frame, then every 50 ms = 20 Hz).
- `src/tasks/base_task.py` (639 to 672 lines): `records_target_track = False` class flag; an `EntryTracker` (hold from `dwell.config.hold_grace_ms`, else 120 ms) and a `TrackThrottle`; `_entries.update(t_ns, pointer.valid, on_target)` right after `on_target` is computed (before the dwell, so a hit frame is counted); both reset in `_start_trial`; `slot_index` set on the `TrialRecord` at trial start; `entries` and `end_x/end_y` (= `target_position(target, t_ns - trial start)`) set in `_finish_trial`, so they hold for hit, timeout and skip; `_record_track` helper.
- `src/tasks/follow_moving.py`: `records_target_track = True` (the only task that moves its target).
- `src/data/schema.py`: `TrialRecord.entries` (0), `end_x`, `end_y` (None, blank in the csv), `slot_index` (-1); `csv_header()` and `as_row()` append `entries, end_x, end_y, slot_index` after `is_skipped` (R6, no `outcome`); `SessionMetadata.layout_slots` and `raw_clock_offset_ns` (None, additive, `schema_version` stays 1).
- `src/data/recorder.py`: `TARGET_TRACK_FILENAME` / `TARGET_TRACK_COLUMNS` (`t_ns,trial,x,y`); `SessionRecorder.record_target_track` (file and header created by the first call, x/y rounded to 5 decimals, flushed every 60 rows and on close); running `min(t_ns - round(time_s * 1e9))` in `record_raw` and the `raw_clock_offset_ns` property; `NullRecorder` gets `record_target_track` (no-op) and `raw_clock_offset_ns` (None).
- `src/app.py` (1135 to 1143 lines): `metadata.layout_slots` (canvas-normalized `[[x, y], ...]`, 5 decimals, None for a task with no fixed layout) and `metadata.raw_clock_offset_ns`.
- Tests: new `tests/test_entry_tracker.py` (23, G1), `tests/test_recording_additions.py` (34: columns and defaults, older csv, target_track writer / throttle / `NullRecorder`, G9, `BaseTask` wiring, real click_grid / scanning slots, headless replay); `tests/test_task_pipeline.py` +2 (G11); `tests/test_run_modes_app.py` +6 (raw offset, layout slots for click_grid / scanning / click_static, follow_moving writes `target_track.csv` and a practice writes nothing). Two P2 assertions that said `is_skipped` was the last column were updated (`tests/test_run_engine.py` header test, renamed; `tests/test_run_modes_app.py` ended-run test).

**What was done**
- 4D.4-1: the debounce is exactly the SPEC's: an invalid frame is ignored (no enter, no exit, no timer); the first valid on-target frame while outside is an entry; valid off-target frames while inside commit the exit only when the first of them is at least `exit_hold_ms` old, and an on-target frame before that cancels it; a return after a committed exit is a new entry. `first_entry_ns` is the first valid on-target frame, so it equals `t_first_gaze_on_target_ns` and `time_to_first_fixation_ms` is unchanged (G11 asserts it for a trial that visits twice and for a flicker). In eye mode and in switch mode every hit has `entries >= 1` (the frame is counted before it is scored).
- 4D.4-2: `end_x/end_y` for all four tasks (equal to the start for the static ones); `target_track.csv` for follow_moving only, via the recorder, a no-op for `NullRecorder` (practice and preview write nothing, tested through `AssessmentApp`).
- 4D.4-3, 4D.4-4: `slot_index` per trial (-1 for click_static and follow_moving); `metadata.layout_slots`.
- 4D.4-5: `metadata.raw_clock_offset_ns`; G9 (jittered host times give exactly the minimum; replay without device `TIME` gives one consistent offset, within 5 ns of float rounding).
- G1, G9, G11 as listed in 4D.10, plus the extras above.

**Tests added:** 65 (23 + 34 + 2 + 6).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline after P2 `1031 passed, 2 skipped`; after `1096 passed, 2 skipped in 134.55s`. No failures. `ruff` is clean on every new and changed file except the `app.py` I001 import-order finding that was there before.

**Deviations / judgement calls (none changes a SPEC decision)**
1. `EntryTracker` is at `src/tasks/entry_tracker.py` (the path 4D.4-1 gives), not under `src/engine/`.
2. **The optional `TARGET_ENTER` / `TARGET_EXIT` events (4D.4-1) are not built.** `EntryTracker.update` already returns the committed transition, so adding them is a three-line change in `BaseTask.update`. They would change the event streams that several existing tests assert exactly. See §9.
3. `metadata.layout_slots` is set in `AssessmentApp.__init__` right after `build_task`, not at the first tick: the slots are constants of the task, so the values are identical, and `_record_geometry` is driven by seven existing tests with a `SimpleNamespace` app that has no `task`. See §9.
4. `raw_clock_offset_ns` is copied in `_write_session_files`, just before `_record_session_end_quality()`, not inside that method, because `tests/test_grid_cell_gap.py` calls it on a fake app without a recorder. Same moment, after the last raw record and before `recorder.close()` writes `metadata.json`.
5. Exit commit, read literally: only a *valid off-target frame* commits (the passage of time does not). So a visit followed by a valid off frame, then an invalid gap, then an on-target frame is one entry, however long the gap; and with a regular 10 ms frame stream an exit needs 13 consecutive off-target frames (the 13th is 120 ms after the first). Documented in the module docstring and tested.
6. `slot_index` is written as `-1` (the `TargetSpec` value) for a task with no fixed layout, not blank. `end_x/end_y` are always filled in `trials.csv` (only finished trials are written).
7. `target_track.csv` details for P4's reader: created by the first sample (so a follow_moving run that never shows a trial has none, like any older folder); a trial interrupted by a pause and re-presented repeats its `trial` id, so the reader windows on the trial's own `[t_target_shown_ns, t_end_ns]`; a later trial's first row is the frame after it starts (the ITI frame that starts a trial does not run the target code), so about 10 to 16 ms after `t_target_shown_ns`; the final position is `end_x/end_y`, not always a row.
8. `BaseTask._record_track` looks the writer up with `getattr`: several existing task tests pass a recorder double that has only `record_event` and `log`.
9. `base_task.py` grew 33 lines (to 672; it was already over 500) and `app.py` 8; the logic is in the two new modules.

**Left undone (belongs to later phases):** P4 analysis modules (geometry, saccades, trial metrics, visual data, cache, CLI), which are the readers of everything added here; the UI; HUD removal; pause wiring in the app. `docs/DATA_SCHEMA.md` and the README are P8. Three empty stray files named after Python annotations (`None`, `int`, `t_before,`; the arrow-in-tool-input quirk) appeared in the repo root during the run and were removed; `git status` shows only the files listed above.

### 2026-10-06 — P4 (4D plan steps 3-6: D3 geometry + saccades, D4 trial metrics, D5 visual data, D6 cache + hook + CLI), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed before the first edit. `configs/default.yaml` and `configs/local_state.json` untouched. No app launch, no live run. The real `sessions/` folders were not modified (see the AD6 check below: the CLI ran on copies in the scratchpad only, and a SHA-1 manifest of the five source folders is identical before and after).

**Files changed**
- `src/data/report_geometry.py` (new, 230 lines): `Geometry.from_metadata`, `monitor_to_canvas_norm` / `canvas_to_monitor_norm` (the `BaseTask` maths; unit-free ratio, so physical and logical-px folders both work), `angle_deg` / `canvas_angle_deg` (per-axis mm, `2*atan(chord/2D)`), `px_per_deg` (41.34 on the 1920 / 527 mm / 650 mm rig), `canvas_logical_size` (physical canvas times 100 / scale), `canvas_mm`, `radius_to_diameter_deg` (inverse of `target_size.radius_px_for`), `px_to_deg`, `for_visuals()` (reference-rig fallback, flagged `assumed`, used only for path thinning and the heat blur), `as_dict`. A value a folder lacks is `None` and the angle helpers then return `None`.
- `src/data/saccades.py` (new, 195 lines): `IvtParams` (50 deg/s, >= 2 samples, >= 0.5 deg, median 33 ms, span 20 ms, gap 75 ms), `detect_saccades(samples, geometry, params)`, `Saccade`, `filter_widths` (150 Hz: m=5, k=3; 60 Hz: m=3, k=1), `split_segments`, `window_saccades(saccades, clock_offset_ns, start_ns, end_ns)`. A pause gap is a break (any gap over 75 ms, like an invalid sample).
- `src/data/report_eye.py` (new, 274 lines): `GazeFrame` / `load_gaze_frames` (sorted, de-duplicated on `t_ns`, first wins) / `FrameIndex.window`, `trial_fixations` (vendor FPOGID rule, assigned by start, clipped at the trial end), `RawSample` / `load_raw_samples` (only the 8 columns the report reads) / `sample_period_s`, `PupilParams`, `pupil_series` (both eyes valid, 1.5-9 mm, +-100 ms blink mask), `trial_pupil` (mean, 300 ms or ITI baseline with >= 50 % coverage, change in mm and %).
- `src/data/report_metrics.py` (new, 286 lines): `trial_outcome` (derived from the three flags, R6), `format_pct_n`, `RawAnalysis` / `analyse_raw` (I-VT + pupil series, `None` without `all_gaze.csv` or `raw_clock_offset_ns`), `build_trials` (the per-trial dict, 4D.6 shape), `summary_rows` (the four U10 rows).
- `src/data/report_quality.py` (new, 137 lines): `eye_summary` (Eye Metrics, whole test), `gaze_valid_share`, `quality_block`, `frames_by_window`.
- `src/data/report_config.py` (new, 269 lines): `build_config_rows(snapshot, metadata, *, task_id, shrunk, geometry)` returning the 17 `(label, value)` rows, "—" for an absent source; `setting()` reader.
- `src/data/report_visual.py` (new, 315 lines): `gaze_path` (radial thinning 0.15 deg / 100 ms, split at 150 ms gaps and invalid frames, 400-point cap by uniform stride, off-canvas points kept), `heat_map` / `heat_grid` / `blur_grid` / `heat_sigma_bins` (96x54, sigma 1 deg per axis, time weights capped at 100 ms, separable Gaussian, max-normalized, 3 decimals), `map_marks` (grouping within half a radius, one mark per outcome, moving target at `end_x/end_y`), `load_target_track` / `trial_track` (windowed on the trial's own `[onset, end]`).
- `src/data/report_cache.py` (new, 314 lines): `REPORT_VERSION = 1`, `build_report`, `report_json` (compact, deterministic), `write_report` (temp file + `os.replace`), `write_report_safely`, `load_or_build_report`, `ReportError`, `summary_text`, the CLI `python -m src.data.report_cache <session_dir> [--summary] [--indent] [--write]` (read-only unless `--write`).
- `src/data/report_util.py` (new, 33 lines): `to_int`, `to_float`, `round_or_none`, `mean_or_none`.
- `src/app.py` (+5 lines): `from .data.report_cache import write_report_safely` and one call at the end of `_write_session_files` (after `write_session_metrics`). `_write_session_files` runs only for a recorded run, so practice and preview (NullRecorder) never reach it. A failure is logged, never raised.
- Tests (new): `tests/report_fixtures.py` (helpers, not a test module), `tests/test_report_geometry.py` (16, G3), `tests/test_report_saccades.py` (17, G4), `tests/test_report_eye.py` (23, G5 + G6 + readers), `tests/test_report_metrics.py` (29, G2 + trial table + quality), `tests/test_report_visual.py` (33, G7 + G8 + marks + track), `tests/test_report_config.py` (14, 4D.3), `tests/test_report_cache.py` (29, G10 + CLI). `tests/test_run_modes_app.py` +5 (recorded run leaves a `report.json` equal to a rebuild; operator-ended run gets the partial banner; practice and preview never build one; a failing build never breaks closing the run).

**What was done**
- 4D.5 and 4D.6 as written, plus the readers. The module list in 4D.6 is five files; there are nine, see judgement call 1.
- G2, G3, G4, G5, G6, G7, G8, G10 as listed in 4D.10, plus the extras in the file list. G4's clock-offset case is tested at both levels (`window_saccades`, and through `build_trials` with `raw_clock_offset_ns`). G1, G9, G11 were P3; G12 is P7.
- R1/R6/R7: the outcome is derived from `is_skipped` / `is_hit` / `is_timeout` (a row with none is `unknown`: listed, never scored); the configuration table reads `metadata.settings` plus the resolved facts in the rest of the metadata. U10: Error-free = a hit with `entries == 1` and `attempts == 1`; Reaction Time = onset to the first gaze entry (`t_first_gaze_on_target_ns`); Trial Time = onset to the click (hit) or to the end (timeout). Skipped trials show no metrics and stay out of every percentage.
- 4D.9: every missing input degrades to `None` ("—"), tested on a legacy fixture (no new columns, no `all_gaze.csv`, no geometry) and on real folders. `session.sources` says which inputs the folder had, so the UI can explain a "—".
- The hook writes `report.json` for "Save partial" too (it runs at every recorded run's end). A later Discard deletes the folder, report included.

**Tests added:** 166 (161 in the seven new files + 5 in `tests/test_run_modes_app.py`).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline after P3 `1096 passed, 2 skipped`; after `1262 passed, 2 skipped in 141.83s`. No failures. `ruff` is clean on every new file and on the changed region of `app.py`; the two findings left (`app.py` I001, `exporter.py:115` B905) were there before.

**AD6 sanity (CLI on copies; the real folders were not touched)**
Five real old-format folders were copied into the scratchpad: `2026-10-05_EYEGEOM_click_grid_run1` (click_grid, 18 trials), `2026-10-05_EYEGEOM_click_static_run1` (click_static, 32), `2026-10-05_HUDTEST_scanning_run1` (scanning, 6), `2026-10-06_LIVECHK02_follow_moving_run1` (follow_moving, 2; a fake-server recording that already existed, not a new session) and `2026-09-11_DIKI_click_grid_run1` (no geometry, no `all_gaze.csv`). The CLI wall time was 0.58 to 0.82 s per folder including Python start; `report.json` sizes would be 32 kB (follow_moving), 39 kB (scanning), 67 kB (click_grid) and 90 kB (click_static, 32 trials).
- **As they are (no `raw_clock_offset_ns`, as 4D.9 expects):** all five build without an exception. Entries "—", Error-free row "—" (0 % only for the follow_moving folder, which has no hit), Size "—" (no `target_size`), saccade and pupil columns "—" (`saccades=no`). Fixations, gaze path, heat map and valid share still work from `gaze_stream.csv`: click_grid 76 fixations (mean 4.2 per trial, mean 239.5 ms, median 190.9 ms), All Targets Selected 100 % (18/18), Trial Time 1.251 s, Reaction Time 0.310 s, valid gaze 100 %, calibration 21.31 px = 0.52 deg; click_static 92 fixations over 32 trials, Trial Time 1.192 s, Reaction Time 0.322 s; scanning 16 fixations over 6 trials; DIKI (no geometry) 144 fixations over 20 trials, valid gaze 88.4 %, calibration error in degrees "—", `assumed_for_visuals` true. Distance between targets (deg) is filled for the three folders with geometry (click_grid trial 2 to 18: 5.8 to 23.0 deg).
- **With a join-estimated offset, written into the COPIES' `metadata.json` only (scratch script: gaze_stream rows joined to `all_gaze.csv` on BPOGX, BPOGY, FPOGD; offset = the minimum host time minus TIME):** the join matched 100 % / 100 % / 99 % of the gaze rows on the three real recordings, and the median sits 5.2 / 4.2 / 4.3 ms above the minimum (95th percentile 10.0 / 7.7 / 8.7 ms), confirming HD8's min-latency estimate. Inside the trial windows: click_grid 76 saccades (mean amplitude 6.49 deg, mean smoothed peak 143.8 deg/s, max 510.7, scan path 27.4 deg per trial) and pupil mean 3.686 mm with per-trial change from -0.194 to +0.183 mm (mean -0.002 mm, 18 of 18 with a baseline), the same span as the 4D.5 probe; click_static 93 saccades vs 92 fixations, pupil change mean +0.018 mm (31 of 32 with a baseline); scanning 18 saccades vs 16 fixations.
- **AD6 proper (whole recording, I-VT on the full `all_gaze.csv`, scratch script, same copies):** click_grid 113 saccades vs 127 vendor fixation rows (-11 %), median amplitude 2.87 deg; click_static 188 vs 206 (-9 %), median 2.90 deg; scanning 185 vs 226 (-18 %), median 3.48 deg. All within the 25 % bound and the 2-4 deg median range; smoothed peak velocity median 74 / 75 / 92 deg/s. About 86 to 92 % of the vendor transitions of 1 deg or more have a detected saccade onset nearby (a rough match rule of mine, only a sanity figure). Reading `all_gaze.csv` took 60 to 126 ms and I-VT 31 to 44 ms for 5.5k to 12.5k rows.
- **Not done here:** the fake-server session (needs an app launch; P9). The real 60 Hz check stays deferred: no real 60 Hz recording exists.

**Deviations / judgement calls (none changes a SPEC decision)**
1. **More modules than 4D.6 lists.** Besides `report_geometry`, `saccades`, `report_metrics`, `report_visual` and `report_cache`, there are `report_eye.py` (readers, fixations, pupil), `report_quality.py` (eye summary, quality block), `report_config.py` (17 rows) and `report_util.py`. 4D.6 puts fixations, pupil, config rows and quality in `report_metrics`, but also says each module is under 300 lines; one file would be about 700. All are under 320 lines (`report_visual` 315, `report_cache` 314, the rest less), well inside the 500-line rule.
2. **`report.json` shape additions** to the 4D.6 v1 list, all additive: `session.{session_id, completed_trials, n_rows, n_scored, n_skipped, n_not_presented, sources}`, `config.rows`, a `map` block (`aspect`, `slots`, `marks`, `note`), per trial `onset_ns`, `end_ns`, `attempts`, `error_free`, and `track` (follow_moving only), `heat.{sigma_bins, total_s, off_canvas_share, empty}`, `geometry.assumed_for_visuals`, `quality.warnings` as `{code, text}` (codes `ended_early`, `low_valid_gaze`, `canvas_resized`). R1 names are used (`planned_trials`, `outcome`); there is no separate `ended_early` boolean: the banner flag is the `ended_early` warning (planned > rows, or outcome `ended_early`). An empty heat map has `data: []` and `empty: true` (not a list of zeros).
3. **Where the hook is.** In `_write_session_files` (called by `_shutdown` for a recorded run only), after `write_session_metrics`, through `write_report_safely`. See §9: this computes the report before any P7 Save/Discard dialog exists, so "discarded runs never compute it" (4D.6) cannot hold unless P7 moves the call.
4. **I-VT details the SPEC leaves open.** The running median shrinks symmetrically at segment edges (always an odd count); the velocity window is clamped (one-sided) at a segment edge; the amplitude is measured on the median-filtered positions; `onset_s` / `offset_s` are the first / last sample at or above the threshold and the mean velocity is amplitude over `offset - onset + one sample period`. A velocity of 0 is used where the window has no time span.
5. **Pupil details.** An unknown ITI (no setting) uses the 300 ms window; an ITI of 0 gives no baseline (no blank to measure). Expected sample count = window / median sample period of `all_gaze.csv`. The per-trial mean is over `[onset, end]` with no minimum count. The whole-test pupil mean and change are the means over trials.
6. **Fixation details.** A frame window is closed (`onset <= t <= end`); a fixation with no `FPOGD` is skipped; a carry-in boundary is `onset <= start < end` exactly as 4D.5. Frames are de-duplicated on `t_ns` before everything (first wins), the heat map and the valid share included.
7. **Quality definitions.** `valid_share` = valid frames over all de-duplicated gaze frames inside the scored (hit and timeout) trial windows; `off_canvas_share` is by time weight (from the heat map), not by sample count.
8. **Summary rows.** The Error-free row is `None` ("—") when any hit lacks `entries` or `attempts`; with no hit at all it is 0 % even on an old folder (nothing to guess). Skipped trials are included when finding "the previous presented target" for Distance; follow_moving has no Distance.
9. **Legacy `canvas_units = None`:** the canvas numbers are used as they are, in the unit-free ratio (4D.5). On a scaled-display folder written before `canvas_units` existed, the canvas fields were logical px while `screen_*_px` were physical, so the monitor-to-canvas mapping for such a folder is approximate; the 4D.9 note already limits those folders to raw gaze.
10. **Config rows read** `settings.live["dwell.*", "task.*", "motion.speed_frac_per_s"]` and `settings.structural` (`trials`, `grid`, `layout`, `motion`, `target`, and, for Theme and Feedback, `theme` and `feedback`). Old folders have none of the last two, so those rows read "—" there. See §9.
11. **CLI** is read-only by default (it prints; the brief's "real folders must not be modified" made `--write` opt-in) and has `--summary` and `--indent` extras.
12. The hook and report cache are not in the headless replay path (`run_headless_replay`), since 4D.6 names `_shutdown` only.

**Left undone (belongs to later phases):** `ReportPage`, `TargetMapWidget`, Print Report (P7); the fake-server session and the live timing of AD13 (P9); `docs/DATA_SCHEMA.md` and the README (P8). Stray empty files (annotation arrows in tool input) were checked for at the end; none are left in the repo root.

### 2026-10-06 — P5 (4B plan steps 2-4: B2 registry layout + bool kind, B3 profile schema v2 + named configurations, B4 fit hints + dialog bool branch), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`, tree clean at `f13091e`) before the first edit. `configs/default.yaml` and `configs/local_state.json` untouched. No app launch, no live run. The only UI file touched is the existing `TaskSettingsDialog` (HB11); no page, no dashboard wiring, no wireframe, no HUD change.

**Files changed**
- `src/ui/settings_registry.py` (411 to 485 lines). The brief wrote `src/engine/settings_registry.py`; the file has always been in `src/ui/` (about 20 imports and tests name it there), so it was edited in place.
  - `StructuralSetting.kind` gains `"bool"` and `default` is now `Any` (a string for a choice, a bool for a bool).
  - Two new entries, `feedback.hit_sound` ("Play hit sound") and `feedback.miss_sound` ("Play miss sound"), kind `bool`, default `True`, every task. `feedback.particles` stays unexposed.
  - `_initial_structural_value` gets the bool branch: the task config's value when it is a real bool, else the setting's default (so `"no"` or `0` read as the default, never as a falsy value).
  - New `ConfigControl`, `ConfigGroup`, `HINT_GRID_FIT` / `HINT_ICON_FIT` and the pure `config_groups_for_task(task_id)`: a table of the nine 4B.1 cards (Test, Feedback, Target, Icons, Grid Layout, Motion, Timing, Selection (Dwell), Gaze Smoothing) with column, hint, and control order; the controls are looked up in the live and structural registries plus the three page controls (`test.name`, `test.config_name`, `test.notes`). A key a task has no setting for is skipped and an empty card is dropped, so one table gives the four pages. Widget kind comes from the registry kind (`bool` check, `int` slider_int, `float` slider_float, `choice` radio, HB1); `dwell.smoothing.alpha` depends on `dwell.smoothing.enabled`. Each control carries its registry entry (`setting`) so the page needs no second lookup.
  - `format_saved_at` moved to `settings_profile.py` (see judgement call 2); the registry re-exports it, so every existing import still works.
- `src/engine/settings_profile.py` (298 to 433 lines).
  - `PROFILE_SCHEMA_VERSION = 2`; `STANDARD_CONFIG_NAME = "Standard"`, `CONFIG_NAME_MAX_LEN = 40`.
  - `load_settings_profile_file` returns `name` ("" for a v1 file, a save without a name, or a non-string).
  - `save_settings_profile(..., name="")` writes `name` and cuts `live` to the task's keys (`task_live_values`); `structural` is stored as given. A name `validate_config_name` refuses raises `ValueError` before anything is written.
  - `validate_config_name` (1-40 characters after trimming, no control characters, not "Standard" case-insensitively), `NamedConfig(name, saved_at, path, live, structural)`, `effective_config_name`, `list_named_configurations` (4B.4: one entry per effective name, newest first by each name's newest version; a v1 file or an unnamed save is `Saved MM/DD HH:MM` in local time, so every old profile stays reachable).
  - `format_saved_at` now lives here.
- `src/engine/target_size.py` (461 to 496 lines): `grid_fit_hint(rows, cols, canvas_w_px, canvas_h_px, wanted_radius_px, margin_frac=0.12, gap_px=None)` and `icon_fit_hint(n_icons, slots, canvas_w_px, canvas_h_px, wanted_radius_px)`, both returning the dialog's exact text or `None`.
- `src/ui/task_settings_dialog.py`: `_update_fit_hint` / `_update_icon_hint` call the two functions (a small `_show_hint` shows or hides the amber box); `_build_control` builds a `QCheckBox` for `kind="bool"`; `overrides()` returns it as a bool (`{"feedback": {"hit_sound": True, "miss_sound": True}}`). `fit_hint` and `fit_hint_label` keep their names and texts.
- `src/ui/settings_snapshot.py` (new, 90 lines, Qt-free): `settings_snapshot(task_id, config)`, `complete_settings(task_id, config, live, structural)` and `run_settings(task_id, config, config_name)`. This is the data side of "complete structural" and of the P4 carry-forward; see judgement call 4.
- Tests (new): `tests/test_settings_layout.py` (32: AB1, AB2, 4B.2 card/column/order per task, widget kinds, `depends_on`, bool kind and default), `tests/test_settings_snapshot.py` (27), `tests/test_fit_hints.py` (17: both pure functions, the dialog calling them, the bool branch, `overrides()` equals the snapshot's `structural` for all four tasks). Extended: `tests/test_settings_profile.py` (33 to 58 collected: name and schema v2, a v1 file, refused names, task-filtered live, the listing, AB8-AB10 data part).

**What was done**
- B2 as written, with `config_groups_for_task` as pure data: AB1 and AB2 are tests over the registries (control set = live keys + structural keys of the task + the three page keys, each exactly once, no `radius_px` key); the card contents and order of 4B.2 are pinned per task.
- B3 as written. Existing profile tests are untouched: `save_settings_profile` still stores `structural` as given (several existing tests pass a partial or flat block and read it back equal), so the *complete* block is produced by `complete_settings` and the caller passes it (the page's `collect_values()` in P7, or the snapshot function).
- B4 as written. The standalone dialog now shows the two sound toggles as check boxes (HB11).
- P4 carry-forward: `run_settings` returns `{"config_name", "live", "structural"}` for the final merged config, with `live["dwell.visual_cursor"]` (a registry live key), `structural.feedback.{hit_sound, miss_sound}` (registry bool keys) and, as read-only context, `structural.theme` (a name, resolved as `AssessmentApp` does) and `structural.feedback.particles` (the YAML's value, only when it is a bool). `report_config.py` and its tests are **unchanged**: the shape already matches, and `tests/test_settings_snapshot.py` feeds `run_settings` output to `build_config_rows` (Theme "Forest", Gaze cursor shown "Yes", Feedback "Sound on, sparkle on"; a changed block gives "Space", "No", "Sound miss only, sparkle on"). Not wired into a run (P8).

**Tests added:** 101 passing (32 + 27 + 17 + 25 in `test_settings_profile.py`).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline `1262 passed, 2 skipped`; after `1362 passed, 1 failed, 2 skipped in 144.63s`. The one failure is `tests/test_phase_b_sizes.py::test_click_grid_dialog_is_unchanged`, left **unedited on purpose** (§9, first P5 point): it pins the dialog's control set to the five pre-P5 keys, and exposing the two sound keys in the dialog (HB3 + HB11) adds `feedback.hit_sound` and `feedback.miss_sound`. Every other test passes unchanged, including all of `tests/test_task_settings_dialog.py`. `ruff` is clean on every new file and changed region; the two UP017 findings left in `settings_profile.py` (`timezone.utc`, lines 95 and 237) were there before.

**Deviations / judgement calls (none changes a SPEC decision)**
1. **Registry path.** `src/ui/settings_registry.py`, not `src/engine/` (see Files changed).
2. **`format_saved_at` moved** from `settings_registry.py` to `settings_profile.py` (re-exported from the registry). The v1 label `Saved MM/DD HH:MM` needs it, and the registry already imports `settings_profile`, so importing back from the registry would be circular. `settings_profile.py` has one function-level import, `live_settings_for_task` in `task_live_values`, for the same reason (engine reading the ui registry; commented in place).
3. **`icon_fit_hint` takes `slots`** (`scanning_layout_slots(...)` computed by the caller) instead of arrangement and margin: `src/tasks/scanning.py` imports `target_size.py`, so `target_size.py` cannot import it back. `target_size.py` is at 496 lines, so the two functions have short docstrings.
4. **New module `src/ui/settings_snapshot.py`** (not named in B2-B4). It is the only way to deliver "complete structural" without breaking the existing profile tests, and the way to make the P4 carry-forward real and testable. P8 can use `complete_settings` for the test entry and profile, and `run_settings` for `metadata.settings`.
5. **Names are compared case-insensitively** in `list_named_configurations` (like test names, R10, and "Standard" is reserved case-insensitively); the entry keeps the newest version's spelling. The SPEC does not say. One `.casefold()` in `list_named_configurations` if exact matching is wanted.
6. **`save_settings_profile` raises `ValueError`** for a non-empty name that fails `validate_config_name` (the SPEC puts that rule on the page, 4B.3). An empty name is allowed, which keeps the HUD's save and every existing caller working (the file then lists as `Saved MM/DD HH:MM`).
7. **A stored name that could not be chosen today** (hand-edited to "Standard", over 40 characters) is listed under its `Saved MM/DD HH:MM` label, so it neither shadows the computed Standard nor becomes unreachable. An unparseable `saved_at` is labelled `Saved <file stem>`.
8. **Not done from 4B.1:** the new plain-language tooltips for the structural controls (the registry has no tooltip field on `StructuralSetting`); that belongs with the page (B5, P7).

**Left undone (belongs to later phases):** `task_config_page.py`, QSS, dashboard wiring, the Standard/forced-rename/Update dialogs (P7, P8); wiring `complete_settings` / `run_settings` into a test entry or a run (P8); the stale pin in `test_click_grid_dialog_is_unchanged` (hub decision, §9). Three empty stray files named after annotations (`None`, `dict[str`, `str`; the arrow-in-tool-input quirk) appeared in the working directory `D:\RESEARCH ASSISTANT\50-Gaze-Point-Project` (the parent of the repo, not in it) and were removed; `git status` shows only the files listed above.

### 2026-10-06 — P7a (4B plan step 5: B5 `TaskConfigPage` + the `wtmhConfigScroll` QSS), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`, tree clean at `33a10f2`) before the first edit. `configs/default.yaml` and `configs/local_state.json` untouched. No app launch, no live run. Out of scope and not touched: dashboard wiring, `TasksPage` / `ResultsPage` / `OperatorPanel`, run bar / run view / Start page / end dialogs, report widgets, Preview launching.

**Files added**
- `src/ui/task_config_page.py` (481 lines): `TaskConfigPage(task_id, config, *, screen=None, parent=None)`. Signals `saveRequested(dict)`, `cancelRequested`, `previewRequested(dict)`. Public API: `set_context(subject_id=, existing_test_names=, named_configs=)`, `load_values(test_name=, notes=, config_name=, live=, structural=)`, `collect_values()` (`{"live", "structural"}`), `collect_entry()` (that plus `test_name`, `config_name`, `notes`; what `saveRequested` carries), `standard_values()`, `loaded_config_name()`, `is_modified()`, `is_dirty()`, `mark_clean()`, `save_problem()`, `show_note(text)`.
- `src/ui/config_form.py` (248): `ConfigForm`, the card grid built from `config_groups_for_task` (3 columns in a `QGridLayout`, a `wtmhCard` per group, one control per setting) and the amber shrink hint; builds only, connects nothing. Split out of the page to keep both under 500 lines.
- `src/ui/config_widgets.py` (182): `RadioChoice` (a one-of group of radio buttons, named `cfg_<key>_<value>`), `CONFIG_TOOLTIPS` (the new plain-language tooltips of the structural controls and the page's own fields), `ask_two_choice` (the themed two-button modal), and `estimated_canvas_px`, `choice_label`, `style_combo_popup` lifted unchanged from the dialog (4B.7: "moves to a shared helper").
- `tests/test_task_config_page.py` (71 tests).

**Files changed**
- `src/ui/wtmh_theme.py` (446 to 489 lines): `wtmhConfigScroll` joins the transparent scroll-area rule; `:disabled` rules (label, check, radio, spin boxes, slider) scoped to that scroll area so Smoothing alpha looks greyed and no other page changes; the first `QRadioButton` style (text in INK, round indicator, radial-gradient dot, no image asset); `cfgSave` / `cfgPreview` / `cfgCancel` / `cfgReset` added to the primary and ghost button rules (the SPEC fixes both these object names and the button tiers, and Qt styles by object name).
- `src/ui/task_settings_dialog.py`: `_estimated_canvas_px`, `_style_combo_popup` and the size/gap label logic of `_build_choice` now call the shared helpers (same output); the unused `BORDER` / `PANEL_BG` import dropped. No behaviour change: `tests/test_task_settings_dialog.py`, `test_fit_hints.py` and `test_phase_b_sizes.py` pass unchanged.

**What was done**
- AB1 / AB2: the page's control set is held against `live_settings_for_task` + `structural_settings_for_task` (plus the page's own fields) for all four tasks; no `radius` key; none hidden; the cards and their columns equal `config_groups_for_task`. Widget kind follows the layout spec (check, `SliderSpinRow`, radio).
- AB3 / AB4: a new page is Standard with `collect_values()` equal to `settings_snapshot` (alpha 0.22), and its `structural` equals `TaskSettingsDialog.overrides()` for all four tasks.
- AB5: unticking Smoothing enabled disables (never hides) the alpha control and its label; re-ticking restores it; a loaded configuration with smoothing off opens greyed.
- AB6: `fit_hint` / `fit_hint_label` show `grid_fit_hint` / `icon_fit_hint` text, compared to the dialog for five grid and four scanning states, hidden when the preset fits.
- AB7: picking a name from the list loads all values (`complete_settings`: a missing key is its default, an unknown key ignored); an unmodified form is not asked; a modified one asks "Replace your edits with configuration '<name>'?" and "Keep my edits" puts the box back as it was (including a typed name); typing a new name loads nothing. Test Name and Notes are never touched. A value a hand-edited file cannot give (a string for a number, a non-bool for a check, an unknown choice) shows the Standard default.
- AB11: Test Name empty / over 60 / duplicate (case-insensitive, via `validate_test_name`, the test's own name excluded) or Configuration Name empty / over 40 disables Save & Continue and shows the reason in the muted footer message; Preview stays enabled.
- AB12: Cancel with no edits emits `cancelRequested` at once; with edits it asks "Discard your changes?" first ("Keep editing" is the default button); neither writes anything (a test runs in an empty temp cwd). Reset to defaults gives Standard and the defaults and keeps Test Name and Notes; it does not ask.
- Also: the "Modified from "<loaded name>"" line, dirty tracking (`is_dirty()` against the state at the last `load_values()` / `mark_clean()`), `show_note()` (the "Preview finished" line, cleared by the next edit, outranked by a validation reason), `load_values()` never runs on show (HB9), Enter never saves (`autoDefault` off), a scroll area `wtmhConfigScroll` with both bars `AsNeeded`, autofill off on viewport and content, footer outside the scroll area, content max width 1500.
- One real-Qt test drives the themed question box (a timer clicks "Keep editing", then "Discard").

**Tests added:** 71 in `tests/test_task_config_page.py`.

**pytest** (`..\.venv\Scripts\python.exe -m pytest -o addopts=""`): baseline `1363 passed, 2 skipped`; after `1434 passed, 2 skipped in 146.75s`. `test_config_merges_task_over_default` passed here (no local-config failure). `ruff` is clean on every new and changed file (one pre-existing I001 in `dashboard_window.py`, untouched).

**Offscreen look (grab of the page in a `wtmhDashboard` root at 1920x976, no fonts):** the four pages render the cards in three columns; the tallest column is Grid Click's column B at about 654 px against an 840 px viewport, so no vertical scrollbar is expected (offscreen understates by about 10 %; AB17 is a live check). Radio dots, the greyed alpha row and the amber hint draw as intended.

**Deviations / judgement calls (none changes a SPEC decision)**
1. **4B.3 vs 4B.4 / AB8.** 4B.3 lists "Standard with modified values" among the reasons Save & Continue is disabled; 4B.4 point 4, AB8 and the approved wireframe say Save on Standard + changed values opens the forced-rename dialog. Both cannot hold, so Save stays **enabled** there and the dashboard shows the dialog (P8). Footer reasons are only Test Name and Configuration Name problems. See §9.
2. **`collect_values()` is exactly `{"live", "structural"}`** (4B.6, AB4); the Test Name, Configuration Name and Notes are in `collect_entry()`, which is what `saveRequested` carries. `previewRequested` carries `collect_values()` (no names, no notes).
3. **The 4B.4 save rules are not in the page** (forced rename, Update / Save under a new name, the profile file): they need the profile store and are plan step 7. The page's own modals are "Load configuration" and "Discard changes". It returns the Configuration Name as typed (trimmed); only a stored name of "Standard" in any case is normalised, at `load_values()`. The dashboard compares names case-insensitively and uses `standard_values()` for "values differ from Standard".
4. **"Unsaved edits" for the replace question means the option values differ from the loaded configuration** (what a load would overwrite); Test Name and Notes edits do not trigger it. Cancel's "edits" is the wider `is_dirty()` (name, notes, configuration name and values).
5. **The page title** ("<Test Name> Configuration") is set at `load_values()` from the saved test name, not updated as the name is typed (wireframe: "name = saved test name").
6. **Tooltips:** the structural controls' texts live in `CONFIG_TOOLTIPS` (`config_widgets.py`), not on `StructuralSetting`, to leave `settings_registry.py` (485 lines) alone. The wording is new and has had no clinical review.
7. **Labels are the registry's** ("Number of trials", "Gaze smoothing enabled"), not the wireframe's capitalisation. The shrink hint is the function's sentence ("Will be shrunk to ≈ N px to fit a R x C grid (approximate)"), not the wireframe's placeholder, because AB6 says "same text as the dialog". A radio group that is the only control of its card (Target) shows no label of its own, as in the wireframe.
8. **px figures and the canvas estimate are computed once, at construction,** from `screen` (default: the page's own screen). P8 should build the page on Configure (as it builds the dialog now) so the labels match the monitor.
9. **Not built (not in the SPEC):** a guard against the mouse wheel changing a slider or spin box while the wheel is meant to scroll the page (Qt default). At 125 / 150 % scaling, where the page scrolls, that can change a value by accident. See §9.

**Left undone (belongs to later phases):** dashboard wiring, the 4B.4 save dialogs and profile write, launching Preview, `MouseGazeSource` hookup (P8 / plan step 7); the live checks AB13-AB20 (P9). The two stray empty files made by arrow-like text in tool input (`QWidget`, `dict[str`) were deleted from the repo root; `git status` shows only the files listed above.

### 2026-10-06 — P7b (4C plan steps 3, 4, 5, 7: run bar and run view, `AssessmentApp` run flow, `StartTestPage`, end dialogs), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged (one `git rm --cached` was run by mistake and undone at once with `git reset -q HEAD -- src/ui/operator_panel.py`; the index is as it was). Branch confirmed (`feature/compass-task-flow`) before the first edit. P7a's uncommitted work (`task_config_page.py`, `config_form.py`, `config_widgets.py`, `wtmh_theme.py`, `task_settings_dialog.py`, `tests/test_task_config_page.py`) was not touched. `configs/default.yaml` and `configs/local_state.json` untouched. No app launch, no live run; offscreen Qt only.

**Files added**
- `src/ui/run_bar.py` (131 lines): `RunBar` (44 px; one status label on the left, Pause (Alt-P) / Skip trial / Quit (Alt-Q) centred). Signals `pause_toggled(bool)`, `skip_requested`, `quit_requested`. `set_status(line, tracking, level)` (the tracking part is coloured), `set_paused`, `set_skip_enabled`, `set_run_mode` (amber for practice and preview), `status_text()`. Own stylesheet by object name, so it looks the same in the dashboard and in the standalone window. The buttons take no focus.
- `src/ui/start_test_page.py` (286): `StartTestPage` (4C.2-4C.4, wireframe `start-test.md`). Signals `startRequested`, `practiceRequested(int)`, `cancelRequested`, `goToSetupRequested`. API: `set_blockers_provider(fn)`, `set_test(test_name=, task_id=, cfg=, values=)`, `set_practice_result(RunResult | None)`, `refresh_blockers()`, `blockers()`, `practice_count`.
- `src/ui/run_dialogs.py` (228): `TestCompleteDialog`, `SavePartialDialog`, `confirm_quit`, `confirm_discard`, `show_nothing_saved`, and `ask_run_end(result, parent, ...)` that walks them for one finished run and returns `save` / `save_and_view` / `discard`.
- `src/engine/run_result.py` (163, Qt-free): `RunResult`, `run_result_from_task`, `practice_result_text`, `FinishedRun`, and `finish_run(result, action, *, output_root, subject_id, test_id)`, the store side of the end dialogs (see "What was done").
- Tests (new): `tests/test_run_bar.py` (17), `tests/test_run_events.py` (4), `tests/test_run_finish.py` (16), `tests/test_run_dialogs.py` (20), `tests/test_start_test_page.py` (23), `tests/test_run_flow_app.py` (26).

**Files changed**
- `src/ui/main_window.py` (rewritten, 76 lines): `TaskRunView(theme, run_mode)` is a `QVBoxLayout` of `TaskCanvas` (stretch) + `RunBar`; Alt-P / Alt-Q are `QShortcut`s on the view (`WidgetWithChildrenShortcut`) that press the bar's buttons; every bar signal gives the focus back to the canvas. `MainWindow(theme, fullscreen, run_mode)`.
- `src/ui/canvas.py` (481 to 506 lines): `TaskCanvas.set_paused(bool)` and `paused`; a paused canvas draws the background and a centred "Paused" in the theme's ring colour, no target, layout or cursor; pausing drops the moving trail.
- `src/app.py` (1148 to 1105 lines). Removed: `_wire_operator`, `_apply_setting`, `_save_settings_profile`, `_reset_settings_to_defaults`, `calibration_snapshot`, `_on_hud_hidden_changed`, `_update_fps`, the `_fps*` and `_device_rate` meters, `_default_live_values`, the `hud_hidden` and `settings_calibration` constructor arguments, the `operator_panel` attribute, and the imports they needed. Added: `_wire_bar`, `_set_paused` (calls `task.pause` / `task.resume`, the canvas and the bar), the paused tick (the raw queue is drained and thrown away, no `gaze_stream` row, the task is not updated), `_request_quit` (Quit, Alt-Q and Esc; a recorded run pauses, asks through `self.confirm_quit(parent, completed, planned)`, and either resumes or shuts down; a practice or preview shuts down at once), `_update_run_bar` (status line and Skip enabled only in `WAIT_INPUT` and not paused), `_display_trial_number`, `_run_result`, `_shutdown(ended_by=None)`. `on_finished` now gets a `RunResult`. `_write_session_files(ended_by)` no longer calls `write_report_safely`; its final raw drain is discarded when the run ends paused.
- `src/engine/run_mode.py`: `ENDED_FINISHED` / `ENDED_QUIT`; `outcome_fields` and `apply_outcome` take an optional `ended_by`, and `apply_outcome` an optional `trial_number` for the log line.
- `src/engine/tracking_status.py`: `run_status_line(..., preview=False)` gives `PREVIEW · Trial i/N · mouse pointer · nothing is recorded` and `PREVIEW · Paused`.
- `src/data/schema.py`: `hud_hidden_at_start` and `hud_toggle_count` removed from `SessionMetadata` (HC13). Old `metadata.json` files that carry them are read by named key, so nothing breaks.
- `src/ui/dashboard_window.py` (minimal, kept importable and working until P8 replaces the flow): removed `_hud_hidden`, `_on_hud_hidden_changed`, the `hud_hidden=` and `settings_calibration=` arguments and the `hud_hidden_changed` connection; `_on_task_finished(self, _result=None)` takes the new `RunResult` argument and ignores it.
- Tests changed: `tests/test_run_engine.py` (the "HUD fields stay" test now says they are gone), `tests/test_run_modes_app.py` (`on_finished` lambdas take the result; the HUD metadata assertion; the report-hook tests, see below).

**Files deleted**
- `src/ui/operator_panel.py`.
- `tests/test_hud_hide_toggle.py` (12 tests): 3 `_check_canvas_resized` tests moved unchanged to `tests/test_run_events.py` (as 4C.7 says); 8 tests of the HUD itself (hide / show button, the H shortcut, panel width, the toggle signal, the dashboard's in-memory memory, the HUD_TOGGLED event, the log lines) and the one for the two metadata fields were removed because their subject no longer exists.
- Removed from `tests/test_run_modes_app.py` (4 functions, 5 collected tests; 3 collected tests added in their place): `test_a_recorded_run_leaves_a_report_json_equal_to_a_rebuild`, `test_an_operator_ended_run_gets_a_report_with_the_partial_banner`, `test_practice_and_preview_never_build_a_report` (x2) and `test_a_report_failure_never_breaks_closing_a_recorded_run`, because they tested the P4 hook at the run's end, which HD1 moves. Their content lives in `tests/test_run_finish.py` (cache equals a rebuild, partial banner, a report bug never undoes a save). New in their place: `test_a_recorded_run_does_not_build_a_report_json` and `test_practice_and_preview_never_build_a_report` (x2).

**What was done**
- Step 3 / AC7: no `OperatorPanel` anywhere in the tree; the canvas is as wide as the view and sits directly on the bar; the shortcut keys and context are tested.
- Step 4 / AC9-AC11: Pause drops the in-flight trial and re-presents the same target with a fresh clock (a 500 ms pause of a 300 ms trial gives no timeout), `PAUSED` / `TRIAL_INTERRUPTED` / `RESUMED` are in `events.jsonl`, the raw queue is drained and thrown away while paused and a final drain at shutdown is thrown away too, no gaze row is written. Skip is enabled only while a target waits. Quit, Alt-Q and Esc ask first (the clock is stopped while it is asked); "Keep going" resumes unless the operator had paused already; a confirmed quit writes every file with `outcome=ended_early`, `ended_by=operator_quit` and the right counts, the log names the trial the operator was on, and `on_finished` gets the `RunResult`. A practice or preview quits at once with no question. A second Esc / Quit while the question is open is ignored.
- Step 5 / AC1-AC3, AC5: the page reads the blockers on show, every second while visible, and inside the Start and Practice handlers (a stale enabled button cannot launch, tested). No default button, Esc is Cancel. The instructions come from `build_instructions` and follow the test's own settings. Each Practice press emits its own number (0, 1, 2, ...), so the dashboard can pass it as `practice_index`.
- Step 7 / AC12: the dialogs follow `run-end.md`; the safe answer is the default and what Esc gives. `ask_run_end` is the dialog order (no finished trial: say so and discard; completed: Test Complete!, Discard Results asks once and Keep brings it back; ended early: Save partial / Discard with no extra question). `finish_run` carries the choice out: **Save** links the test (`record_result`) then caches `report.json` (`write_report_safely`); **Save and View Report** does the same through `load_or_build_report` and hands the report back; **Discard** deletes the folder (`discard_session`) and leaves the test Not Done. **The report is built only after a Save, never for a discarded run** (the P4 carry-forward). A report failure never undoes a save.
- AC14: `grep` of `src/` for `operator_panel`, `hud_hidden`, `HUD_TOGGLED`, `SETTING_CHANGED`, `_save_settings_profile` finds only comments (below).
- AC15: the standalone window (`embedded=False`) runs a replay to the end with the run bar (test), and a dashboard Run was smoke-tested offscreen from a scratch directory (Run, a few ticks, Quit through the bar, the old `_on_task_finished` ran).

**Tests added:** 106 (17 + 4 + 16 + 20 + 23 + 26), plus 3 replacements in `tests/test_run_modes_app.py`.

**pytest** (`..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider`): baseline `1434 passed, 2 skipped`; after `1526 passed, 2 skipped in 153.05s`. No failures (`test_config_merges_task_over_default` passed here). 1434 - 12 (HUD file) - 5 (old report tests) + 106 + 3 = 1526. `ruff` is clean on every new and changed file except the two I001 import-order findings that were there before (`src/app.py`, `src/ui/dashboard_window.py`).

**Deviations / judgement calls (none changes a SPEC decision)**
1. **`finish_run` and `RunResult` live in `src/engine/run_result.py`**, not in a UI module, so the store side is Qt-free and testable. The brief said store updates may be exposed as functions; P8 calls `ask_run_end(...)` then `finish_run(...)`.
2. **`_shutdown(ended_by=...)`**: the SPEC's `ended_by="operator_quit"` is implemented as an optional argument that overrides the derived value (`finished` if the task ran out of trials, else `operator_quit`). The metadata values are the same as before.
3. **The quit question pauses through `task.pause`**, as 4C.6 says, so it counts in `pause_count` and, for a trial in flight, in `interrupted_trials` (a `PAUSED` and a `TRIAL_INTERRUPTED` event). See §9.
4. **Preview bar:** it is amber like practice (so a preview is never mistaken for a recorded run), and `run_status_line` has the preview wording of 4B.6.6 (P2 left it for this pass).
5. **`practiceRequested(int)`** carries the 0-based practice number; the page keeps the count since `set_test`. 4C.4 says k is "practice presses since the Start page opened".
6. **`TaskCanvas` "Paused" text** uses the theme's ring colour (`cursor_color`); the size is `max(24, min(w, h) / 14)` px. `canvas.py` is 506 lines (was 481; the SPEC names `set_paused` there).
7. **The quit dialog's parent is `AssessmentApp.view`**, and the question is a replaceable attribute (`app.confirm_quit`) so tests answer without a modal loop. The dashboard (P8) can leave it.
8. **Dialog styling:** the theme has primary and ghost tiers only, so the dialogs add one scoped `runDlgDanger` rule of their own (no change to `wtmh_theme.py`).
9. **Not changed:** `src/engine/sample_rate.py` and its tests stay (the module is no longer used by the app); the stale comments and docstrings that still say "OperatorPanel" / "HUD" in `settings_registry.py`, `slider_spin.py`, `tasks_page.py`, `task_settings_dialog.py`, `wtmh_theme.py`, `base_task.py`, `click_grid.py`, `click_static.py` and (the two inside the old flow) `dashboard_window.py` are comments only. P8's cleanup retires `tasks_page.py` and the dashboard flow with them.

**Left undone (belongs to P8)**
- All of `DashboardWindow` step 6: flow state, nav lock, title-bar hide, the launch and finish handlers, calling `ask_run_end` / `finish_run` and the report, `StartTestPage` wiring (blockers provider = `SetupPage.run_blockers`, `practiceRequested(k)` into `practice_index`, `set_practice_result(RunResult)`), and the old Tasks-tab Run flow's removal.
- `SubjectTestListPage` / `AddTestDialog`, README and `docs/DATA_SCHEMA.md` (HUD fields, `report.json` timing), `SPEC-hud-hide-toggle.md` superseded note, the wheel guard (resolved: P8).
- Live checks (P9). Stray empty files named after annotations (`None`, `QPushButton`, `QWidget`, `tuple[tuple[float`; the arrow-in-tool-input quirk) appeared in the repo root during the run and were deleted at the end; a blanket `taskkill /IM python.exe` was run once to stop a hung test (see §9).

### 2026-10-06 — P7c (4D plan steps 7 and 8: `ReportPage` + `TargetMapWidget`, Print Report / PDF), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`) before the first edit. P7a's and P7b's uncommitted work was not touched (no existing source or test file was edited; the only existing file changed is this SPEC). `configs/default.yaml` and `configs/local_state.json` untouched. No app launch, no live run, no analysis-module change. Offscreen Qt tests only; PDFs go to `tmp_path`. To look at the layout with real fonts (offscreen has none) a few throwaway scripts in the scratchpad grabbed the page and rendered the PDF to images with Qt's `windows` platform plugin; no application was started, and the one that called `show()` (the first run) flashed a window for about a second, later runs grab without showing.

**Files added**
- `src/ui/report_page.py` (372 lines): `ReportPage`. Signals `saved(name, evaluator, notes)`, `cancelRequested`, `pdfExported(path)`. API: `set_report(report, *, test_name=, evaluator=, notes=, subject=)`, `set_context(*, existing_test_names=, pdf_dir=)`, `show_summary()` / `show_detailed()` / `view_mode`, `collect_edits()`, `is_dirty()` / `mark_clean()`, `save_problem()`, `selected_trial()`, `export_pdf(path)`, and the replaceable `choose_pdf_path(default) -> str` (the `QFileDialog` is only the default). Header (Test Name, Subject, Test Date, Evaluator), banner, left column (Test Configuration table of the report's 17 rows + Notes), a `QStackedWidget` with the two views, footer Print Report / View Details (View Summary) / Save & Continue / Cancel.
- `src/ui/report_views.py` (285): `SummaryView` (task sentence, Summary of Results table + footnote, Target Map with Targets / Gaze path / Heat map switches, map notes, Eye Metrics table) and `DetailedView` (Trial-by-Trial table above the selected-trial map and its line); the scroll helpers.
- `src/ui/target_map.py` (146): `TargetMapWidget` (`set_report`, `set_overlays`, `set_trial`, `set_fit_to_width`, `canvas_rect`, `render_to_image(size, overlays=None)`), custom `QPainter`, no per-sample items. `src/ui/target_map_paint.py` (337): `MapModel`, `build_model`, `paint_map` (the drawing, shared by the screen and the PDF image), `heat_image`, `heat_colour`.
- `src/ui/frozen_table.py` (176): `FrozenColumnTable` (the Trial-by-Trial table: a second `QTableView` over the first column sharing the model and selection, vertical scroll in step, selected row bold, `sortRequested(col)` from either header).
- `src/ui/report_tables.py` (115): `FitTable` (read-only table sized to its rows, for the configuration, summary and eye tables).
- `src/ui/report_format.py` (265, Qt-free): every label and rounding of the page and the PDF (`summary_table`, `eye_rows`, `trial_cells`, `trial_line`, `banner_lines`, `summary_footnote`, `started_text`, `pdf_default_name`, the definitions and the one-sentence task descriptions).
- `src/ui/report_pdf.py` (229): `build_report_html`, `export_report_pdf(path, report, *, test_name, evaluator, notes, map_image)`.
- Tests (new): `tests/report_ui_fixtures.py` (helpers: a real run folder through `build_report`, and a small hand-written map report), `tests/test_report_format.py` (32), `tests/test_target_map.py` (42), `tests/test_frozen_table.py` (10), `tests/test_report_page.py` (25) + `tests/test_report_page_actions.py` (21), `tests/test_report_pdf.py` (18).

**What was done**
- 4D.2 / 4D.3 / AD11 / AD14: the page as in the two approved wireframes. Summary opens first with the first trial selected; View Details toggles; selecting a row (click, Up / Down) updates the pane's map, title and line; every header sorts (again to reverse, "—" cells always last, the selected trial stays selected); skipped rows are grey with "—"; Save emits the three fields and is disabled, with the reason in the footer, for a Test Name that breaks the R10 rules (the test's own name excluded); Cancel emits nothing but `cancelRequested`; the run's data is read-only; the banner shows the report's warnings ("Ended early — n of N trials", "Gaze data is low quality: 72 % valid", the resized-canvas warning).
- 4D.7 / AD8 / AD9: the map draws in the report's canvas-normalized frame at `map.aspect` (so circles stay circles): hit = green circle with the real radius, not selected = red X, skipped = dashed grey ring, report labels ("3, 9"), the faint `map.slots`, gaze paths in a 6-colour cycle (blue, orange, purple, brown, pink, teal: none green or red), the heat map as an alpha ramp (transparent under 0.05; an empty map draws nothing and says "No gaze on the canvas for the heat map"), the moving target's `track` and its mark at `end_x/end_y`. One trial: target ring (solid, outcome colour) + dashed hitbox ring, the path dark to light by time, fixation circles (radius grows with duration, numbered in order), `S` at the path's start and a star at its end for a hit.
- Carry-forward (P4 TODO 3): the widget reads the extra `report.json` keys as documented in the P4 entry: `map.{aspect, slots, marks, note}`, `heat.{w, h, data, empty}` (empty = `data: []`, `empty: true`, nothing is drawn), per-trial `track`, `path`, `fixations.items`, `geometry.{canvas_px, canvas_units, display_scale_percent, canvas_aspect, assumed_for_visuals}`, `quality.{warnings, valid_share}` and `session.{n_skipped, n_not_presented, task_id, config_name}`. A report that lacks a key degrades to an empty drawing or "—", never an exception. `geometry.assumed_for_visuals` shows a note under the map ("This run did not record the monitor's size, so the gaze path and heat map assume a standard monitor.").
- 4D.8 / AD12 / G12: Print Report writes an A4 landscape PDF (10 mm margins) with `QTextDocument` + `QPdfWriter`: header and banner, the Test Configuration table beside the Summary of Results, its footnote and the Eye Metrics (one page with real fonts), then the Target Map as one PNG data-URI (Targets only, 150 mm wide, on its own page), the Trial-by-Trial table with its `<thead>` row repeated on every page (`headerRowCount() == 1`, a 150-trial table spans pages), and the definitions. It is built from the page's current Test Name, Evaluator and Notes. It is written to `<name>.pdf.part` and moved into place with `os.replace`, so a failure (no folder, a locked file) raises `OSError`, leaves the earlier file as it was and no partial file; the page shows "The PDF could not be written: ..." in the footer, never a dialog or a crash. Default name `<Subject>_<Test name>_<YYYY-MM-DD>.pdf` (the test's own date).
- G12: the page populates from a real `build_report` fixture, toggles Summary / Detailed, a row selection updates the pane, and the PDF starts with `%PDF`, is > 10 kB, is A4 landscape when read back with QtPdf and spans at least two pages. AD10: a legacy folder (no new columns, no `all_gaze.csv`, no geometry) fills the page with "—" and exports.
- A bug the tests found in the first version of `FrozenColumnTable`: the overlay's width did not follow its column (the header still reports the old size while emitting `sectionResized`); it now uses the signal's new size.

**Tests added:** 148 (32 + 42 + 10 + 46 + 18).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider`): baseline `1526 passed, 2 skipped`; after `1674 passed, 2 skipped in 179.57s`. No failures (`test_config_merges_task_over_default` passed here). `ruff` is clean on every new file (the one finding in the tree is the I001 in `dashboard_window.py` that was there before).

**Deviations / judgement calls (none changes a SPEC decision)**
1. **More files than the SPEC names** (`report_views`, `report_tables`, `frozen_table`, `target_map_paint`, `report_format`, `report_pdf` beside `ReportPage` and `TargetMapWidget`), to stay under 500 lines and so the PDF and the page share one text.
2. **The Summary's percent is a whole number** (`61% (11/18)`, as the wireframe), built from `n` and `N`; `report.json`'s `pct_n` has one decimal (`61.1% (11/18)`). Presentation only; the report is unchanged. See §9.
3. **PDF: `<img>` as an in-document PNG data-URI, lengths in CSS px.** The layout scales every `px` length by the writer's dpi itself, so padding and the image width are written at 96 dpi and are not converted (a first version converted them and made rows three times too tall; found by rendering the PDF to an image with real fonts).
4. **The hitbox margin** for the dashed ring and the footnote is `report.map.hit_tolerance_px` when a report has it, else 40 px (the `dwell.jitter_tolerance_px` default). `report.json` has no such key today. See §9.
5. **Footer buttons** use the theme's `wtmhPrimary` / `wtmhGhost` tiers (no per-button object names, no change to `wtmh_theme.py`); tests reach them through attributes. The Save button's text is `Save && Continue` (one `&` shows; a single `&` becomes a mnemonic and eats the character). See §9 (P7a's page has the same slip).
6. **Row selection highlight and the vertical-header padding** are set by local style sheets (`FrozenColumnTable`, `FitTable`) because the theme's `QHeaderView::section` rule (padding 6 px 8 px) also applies to a hidden vertical header and makes every row 13 px taller than its text, and its `::item` rule leaves the selected row unpainted. No theme edit.
7. **Pane map and the Summary map are separate widgets** (each reads the report once). The Summary's map is capped at 880 px wide so a 1920 px window does not make it 800 px tall; the Summary scrolls on its own (Eye Metrics are below the map at 1920x1080).
8. **Names:** the Test Name is validated only against the names the host gives with `set_context(existing_test_names=...)`; without them only the length and character rules apply.

**Left undone (belongs to P8 / P9)**
- Everything named out of scope: `DashboardWindow` wiring, Test List, nav changes, retiring `ResultsPage`. The host calls: `ReportPage.set_report(load_or_build_report(test.session_dir), test_name=test.name, evaluator=test.evaluator, notes=test.notes)`, `set_context(existing_test_names=<all names of this subject>, pdf_dir=<folder>)`, connects `saved` to the test-record update and back to the Test List, `cancelRequested` back to the Test List, and locks the nav.
- Live checks (P9): the page at 1920x1080 and `QT_SCALE_FACTOR=1.5` with a real report (the frozen column, the horizontal scroll, the bold selected row, Up / Down), AD13 (< 300 ms to a painted page), a real PDF opened in a viewer, and the native save dialog (it desyncs the qt-mcp probe: let the user click it). The tooltips and the read-aloud text remain clinician-review items; the new report wording (task sentences, definitions) needs the same review.
- Five empty stray files made by arrow-like text in tool input (`0`, `None`, `dict[str`, `extent(0.2`, `int`) were deleted from the repo root at the end; `git status` shows only the files listed above and the SPEC.

### 2026-10-07 — P8a (4A plan step 6 without a bridge, 4C plan step 6 flow-state half, 4B plan step 7, wheel guard), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`, tree clean at `c94d9fd`) before the first edit. `configs/default.yaml`, `configs/local_state.json` and `sessions/` untouched. No app launch, no live run, no qt-mcp; offscreen Qt tests only (one throwaway grab of the Test List with the Windows platform plugin, to look at the layout with real fonts; nothing was shown). Out of scope and not touched: Start / Practice / recorded run wiring, `ask_run_end` / `finish_run`, `ReportPage`, `metadata.settings = run_settings(...)`, deleting `tasks_page.py` / `results_page.py` and the "3 · Results" nav, the AX3 comment cleanup, `canvas.py`, README, `docs/DATA_SCHEMA.md`.

**Files added (src/ui)**
- `test_list_page.py` (493 lines): `SubjectTestListPage`. Signals `configureRequested(test_id)`, `runRequested(test_id)`, `reportRequested(test_id)`, `backToSetupRequested`, `testsChanged`. API `set_subject(subject_id, output_root)` (reads from disk), `reload(select=)`, `selected_test()`, `select_test(id)`, `show_message(text)`, `row_texts()`, `start_rename()`. Table `wtmhTestTable` with the five columns of 4A.4, bold Not Done rows, header sort (Test Name natural, Date Complete with "—" first), selection and sort kept across a reload, the right-hand button column (`add_button` ... `delete_button`; Run Test primary), `← Back to Setup / recalibrate` and "Changes are saved automatically.", the three empty states, the "could not be read" line, "· data missing", Delete / F2 / Enter / double-click as in 4A.4. Add, Copy, Delete and rename are done in the page through `subject_tests`; each write is followed by a reload from disk and a failed one shows "Could not <action>: <reason>. Nothing was changed.".
- `test_list_table.py` (96): the column layout, `natural_key`, `status_text`, `date_cells`, `SortKeyItem` (a cell that sorts by a key), `SubjectTestTable` (Delete / F2 / Enter as signals). Split out only to keep the page under 500 lines.
- `add_test_dialog.py` (133): `AddTestDialog` (the four tasks with bold name and muted description, "How many" 1-10, Add / Cancel; double-click adds one; `AddTestDialog.ask(parent)`).
- `rename_editor.py` (110): `RenameEditor`, the in-place popup over the Test Name cell with the `validate_test_name` reason shown under the box as the name is typed.
- `dashboard_flow.py` (99): `Flow` (`IDLE`, `CONFIGURE`, `PREVIEW`, `START`, `PRACTICE`, `RUN`, `FINISHING`, `REPORT` with `locks_nav` and `hides_title_bar`), `TitleBar` (the brand strip and nav buttons, `set_active`, `set_locked`), `output_root_from_config()`, the tab indices.
- `config_flow.py` (289): `ConfigFlow`, the Configure / Save / Cancel / Preview controller (see "What was done").
- `config_save.py` (98, Qt-free): `decide_save(...)` and `next_custom_name(...)`, the 4B.4 rules as a pure decision.
- `config_save_dialogs.py` (111): `ask_config_name` (forced-rename and "Save under a new name", Save off until `validate_config_name` passes) and `ask_update_choice` (Update / Save under a new name... / Cancel).
- `wheel_guard.py` (52): `WheelGuard` event filter and `guard_wheel(widget, guard)`.

**Files changed**
- `src/ui/dashboard_window.py` (525 to 199 lines): rewritten around the Test List. Gone: `_task_overrides`, `_task_live_overrides`, `_task_selected_profile`, `_task_session_dirs`, `_resolve_settings`, `_refresh_settings_badges`, Load Settings, `_on_settings_requested`, the old `_on_run_requested` / `_on_task_finished` / `_on_analyze_requested`, `_active_assessment`, `_active_task_id`, the `subjectIdChanged` connection, the `TasksPage` import. New: `flow`, `output_root`, `title_bar`, `test_list_page`, `config_flow`, `set_flow(flow)`, `_set_nav_locked(bool)`, `_go_to_tab`, `show_tests(select=)`, and the two placeholders below. `run_dashboard()` is unchanged.
- `src/ui/config_form.py`: the slider rows are guarded (`guard_wheel`) where they are created.
- `src/ui/run_dialogs.py`: one public function, `ask_choice(parent, title, text, buttons, default, on_close)` over the existing private `_ChoiceDialog` (used by Delete Test and the "Configuration exists" question).
- `src/ui/wtmh_theme.py` (489 to 494): the selected-row rule of `QTableWidget#wtmhTestTable`.
- `tests/test_target_screen.py`: `test_dashboard_passes_its_own_screen_to_the_run` drove the removed `_on_run_requested`; it now drives Preview (`config_flow.AssessmentApp` is the one replaced) and asserts the same two things (`screen` is the window's, `embedded` is True).

**Tests added: 179.** `tests/test_test_list_page.py` (25), `test_test_list_actions.py` (31), `test_add_test_dialog.py` (8), `test_config_save.py` (18), `test_dashboard_flow.py` (36), `test_config_flow.py` (32), `test_config_preview.py` (16), `test_wheel_guard.py` (13, after the combo follow-up); shared helpers in `tests/dashboard_fixtures.py` and `tests/list_page_fixtures.py`.

**What was done**
- A6 / AA9, AA12, AA15, AA16: the page and dialog above; the table is identical after recreating the page and calling `set_subject` again (Done shows its date, Ended early shows "Ended early (7/12)", Not Done rows are bold); "Grid Click 2" sorts before "Grid Click 10" and the selection survives a sort and a reload; with no Subject ID the page shows "Enter a Subject ID in Setup.", every button (Add included) is off and nothing is created on disk; with no tracker connected Add, Configure, Copy, Delete and View Report work (Run Test is on for a Not Done test and the page knows nothing about the tracker, R2).
- AA10 / 4A.8: `DashboardWindow` holds no per-subject or per-task state. The list is re-read from disk on every entry to the tab (`_go_to_tab`, Continue, and every flow's return), so A, B, A shows each subject's own tests; typing in Subject ID changes nothing until the tab is opened. Configure looks the test up among the typed subject's tests, so another subject's id is "could not be found".
- C6 flow state and nav lock (R11): `set_flow` locks all three nav buttons for every state but `IDLE` (`_set_nav_locked` is the one lock) and hides the title bar while a canvas is on screen; `_go_to_tab` refuses while locked. Nav labels read `1 · Setup`, `2 · Tests`, `3 · Results`.
- B7 Configure: `ConfigFlow.open(test_id)` builds `TaskConfigPage(task_id, merged_config, screen=window.screen())` (on Configure, so the px figures match the monitor), `set_context(subject_id, existing_test_names=<all names of the subject>, named_configs=list_named_configurations(...))`, `load_values(test_name, notes, config_name, live, structural)` from the test's own snapshot, adds it to the stack on top and locks the nav. A test that is no longer Not Done is refused with the 4B.4 note; Configure is ignored while another flow is active.
- B7 Save & Continue (4B.4, AB8, AB9, AB19): the test is re-read first and a test that has run since gets "This test has already been run and can't be changed." and nothing is written; the name is re-validated with `validate_test_name`; `decide_save` then gives: Standard untouched (store, no file), edited Standard (forced rename, "Standard cannot be changed. Save these settings as:", default `Custom N`), a new name (profile file, no question), an existing name with the same values as its newest version (no question, no file), an existing name with other values (Update / Save under a new name... / Cancel; a name typed in the second case is decided again, so it can itself ask). A profile is written with `save_settings_profile(..., name=...)` from `complete_settings(...)` and the calibration of the Setup page (`{"error_px", "points"}` from `setup_page.calibration_result`, none if there is no calibration); the test entry gets `{"name", "live", "structural"}` (`complete_settings`, so complete and without theme / particles) and the notes through `update_test`, and a changed Test Name through `rename_test`. Cancelling a question stays on the page and writes nothing. A failed write shows "Could not save: <reason>" in the footer and stays on the page. Success removes the page and returns to the list with the test selected, and refreshes Setup's Subject-ID completer when a profile was written.
- B7 Cancel: the page already asks about edits (`Discard changes`); the flow just removes the page and returns to the list.
- B7 Preview (4B.6, AB13-AB16): `previewRequested(values)` runs `AssessmentApp(run_mode="preview", client=MouseGazeSource(), embedded=True, structural_overrides=<unsaved structural with trials = min(3, configured)>, live_overrides=<unsaved live>, screen=window.screen(), ...)`, binds the mouse source to the canvas, adds the run view on top of the still-alive page and sets `Flow.PREVIEW` (nav locked, title bar hidden). Quit, Alt-Q, Esc and the last trial all remove the view and show the page again; only a natural finish sets the footer note "Preview finished. Nothing was recorded."; `load_values()` is never called and nothing of `setup_page.client` is touched. A preview that cannot start puts "Preview could not start: <reason>" in the footer and stays on the page.
- Wheel guard: a slider or spin box without focus ignores the wheel (focus policy `StrongFocus`, because Qt's default `WheelFocus` would give it focus before the filter sees the event), so the event goes on to the scroll area. Applied to every slider row of the configuration page.
- Follow-up 2026-10-07 (user answer to the §9 wheel point): the Configuration Name combo is wheel-guarded too (`guard_wheel` now also covers combo boxes, `StrongFocus`; without the guard a wheel over it loaded a configuration at once), with 5 more tests in `tests/test_wheel_guard.py`, so 179 new tests in all.

**pytest** (`..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o addopts=""`): baseline `1675 passed, 2 skipped`; after `1854 passed, 2 skipped in 235.02s` (1675 + 179 new, after the combo follow-up; `test_config_merges_task_over_default` passed here). `ruff` is clean on every new and changed file in `src/ui` and the new tests.

**Deviations / judgement calls (none changes a SPEC decision)**
1. **Run Test and View Report are placeholders.** `DashboardWindow._on_run_requested` / `_on_report_requested` only put a muted line under the table ("Run Test is not connected yet (next step, P8b)." / "View Report is not connected yet (next step, P8c)."); the Start page, Practice, the recorded run, the finish handler and the report page plug in there. Nothing else was added for them.
2. **Nav and the old Results tab.** The buttons read `1 · Setup`, `2 · Tests`, `3 · Results` (R11 and the approved `_nav.md`). The Results tab and `ResultsPage` stay reachable, as the brief allows, but nothing populates them any more (Analyze was a `TasksPage` button), so they show their empty state. `src/ui/tasks_page.py` is left in the tree, unused by the dashboard, because `tests/test_task_info.py` imports it and P8b / P8c delete it.
3. **Title bar hidden during Preview and `FINISHING`.** The approved wireframe shows Preview full-window with the title bar hidden; HC8 says Practice and Run; `FINISHING` is included because 4C.8 puts the end dialogs over the frozen canvas. `Flow.hides_title_bar` is the one place to change it.
4. **A saved Standard is a complete snapshot.** 4A.2 says Standard is "empty structural / live"; 4B.4 point 4 and HB12 say Save & Continue always stores the complete snapshot. The latter wins, so an untouched Standard saved from the page is stored complete (and writes no profile file); a test that was never configured keeps the empty Standard until its first Save.
5. **Rename in place is a popup editor** (`RenameEditor`), not the table's own cell editor, so the reason from `validate_test_name` shows under the text box as the operator types (4A.6: both editors "must show the returned text inline"). Enter keeps a valid name; Esc or a click elsewhere cancels.
6. **Sorting is done by `sortItems` on a header click** (a key-based `__lt__` on `SortKeyItem`), not `setSortingEnabled(True)`, which would sort by column 0 at once and lose "default is creation order".
7. **Add dialog:** Add is off until a task is chosen (the dialog opens with nothing selected). The Delete confirmation adds "Its recorded data in the sessions folder is kept." only for a test that has a session folder (4A.6 words it for a Done test).
8. **Update compares with the newest version of the name**, as 4B.4 says, also when the test's own snapshot came from an older version of that name: opening Configure on such a test, changing only the notes and saving asks "'<name>' already exists with different settings."
9. **Not in the SPEC:** a `testsChanged` signal on the Test List (the dashboard uses it to refresh Setup's completer so a subject typed today is offered once it has a test); `ask_choice` in `run_dialogs.py`; the module split of `test_list_table.py`.
10. **Test files:** the page tests are split into `test_test_list_page.py` and `test_test_list_actions.py`, and the flow tests into `test_config_flow.py` and `test_config_preview.py`, to stay near the 500-line rule.

**Left undone (belongs to P8b / P8c)**
- P8b: `StartTestPage` in the stack (blockers provider = `setup_page.run_blockers`, `practiceRequested(k)` into `practice_index`, `set_practice_result`), Practice, the recorded run (`AssessmentApp(test_id, test_name, seed=test.seed, config_name, structural_overrides, live_overrides, ...)` built from the test record with the defensive subject check), `ask_run_end` + `finish_run` and their error handling, `metadata.settings = run_settings(...)`, `Flow.START` / `PRACTICE` / `RUN` / `FINISHING` transitions, and the `AssessmentApp.confirm_quit` / dashboard hand-off.
- P8c: `ReportPage` (one page, `set_report(load_or_build_report(...))`, `set_context(existing_test_names=, pdf_dir=<the run's session folder>)`, `saved` into `rename_test` / `update_test(notes=, evaluator=)`, `ReportError`), retiring `tasks_page.py`, `results_page.py` and "3 · Results", the AX3 grep (stale comments still name `OperatorPanel` / the old Tasks flow in `settings_registry.py`, `slider_spin.py`, `tasks_page.py`, `task_settings_dialog.py`, `wtmh_theme.py`, `run_dashboard()`'s comments and `setup_page.py`'s comment on `subjectIdChanged`), `canvas.py` (506 lines) under 500, README and `docs/DATA_SCHEMA.md`, the theme's vertical-header padding decision.
- Live checks (P9): AB13-AB19 on the real window (the page and Preview at 1920x1080 and `QT_SCALE_FACTOR=1.5`, the wheel guard with a real wheel, the table and the rename popup with real fonts, the two save questions and Delete Test with the real dialogs).

### 2026-10-07 — P8b (4C plan steps 6 and 7 launch / finish half, 4D plan step 7 host side, R7 and the P5 `metadata.settings` carry-forward, C8 retire), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`) before the first edit; P8a's uncommitted work was built on, not reverted. `configs/default.yaml`, `configs/local_state.json` and `sessions/` untouched (every test runs with a scratch folder as the working directory). No app launch, no live run, no qt-mcp; offscreen Qt only, a mouse standing in for the tracker. Out of scope and not touched (P8c): the stale "OperatorPanel" comments, `canvas.py` (506 lines), the theme's vertical-header padding, README, `docs/DATA_SCHEMA.md`, the SPEC-hud-hide-toggle superseded note.

**Files added**
- `src/ui/run_flow.py` (290 lines): `RunFlow`, the Run Test controller. `open(test_id)` shows the `StartTestPage` (`Flow.START`, `set_blockers_provider(setup_page.run_blockers)`, instructions built from the test's own merged config); `_on_practice(k)` and `_on_start()` each build a **new** `AssessmentApp` from the test record; `_on_practice_finished` returns to the Start page (`set_practice_result`); `_on_run_finished` is the run end (`Flow.FINISHING`, `ask_run_end`, `finish_run`, the four error types plus `OSError`, Save returns to the Test List with the row selected, Save and View Report hands the report to `ReportFlow`, Discard leaves the test Not Done).
- `src/ui/report_flow.py` (122): `ReportFlow`, the View Report controller (one `ReportPage` per open, nav locked via `Flow.REPORT`, `saved` into `rename_test` / `update_test(notes=, evaluator=)`, `cancelRequested` back to the list).
- Tests (new): `tests/run_flow_fixtures.py` (helpers: a dashboard whose Setup tracker is a `MouseGazeSource`, a driver that hovers targets and ticks a run by hand), `tests/test_run_flow.py` (35), `tests/test_run_flow_end.py` (20), `tests/test_report_flow.py` (19), `tests/test_run_settings_metadata.py` (14), `tests/test_dashboard_e2e.py` (1: AX1 and AX2).

**Files changed**
- `src/ui/dashboard_window.py` (193 lines): `RunFlow` and `ReportFlow` wired to `runRequested` / `reportRequested`; the two placeholders, `ResultsPage`, `results_nav_button` and the Results stack page gone; `show_setup()` added (the Start page's "Go to Setup").
- `src/ui/dashboard_flow.py`: `RESULTS_INDEX` and the "3 · Results" label gone (`NAV_LABELS` has two, `TitleBar.results_button` is gone); `find_test(window, test_id)` added, the one way every flow gets its test (re-read from disk, only the typed subject's).
- `src/ui/config_flow.py`: `_find` delegates to `find_test` (no behaviour change).
- `src/app.py`: `metadata.settings` is `{**run_settings(task_id, self.config, config_name), "source", "profile_saved_at", "profile_file"}`; `_structural_overrides` (its only reader) removed.
- `src/ui/settings_snapshot.py`: `merged_config(config, live, structural)` (what a run built from a stored configuration starts with; `complete_settings` now calls it), and `run_settings(..., config_name: str | None)` for the standalone launch's `None`.
- `src/ui/report_page.py`: `show_note(text)` (see judgement call 3).
- `src/data/report_quality.py`: one comment that named the deleted `results_page.py`.
- Tests changed: `tests/test_dashboard_flow.py` (two nav buttons, two-page stack, the "not connected yet" placeholder test removed, the "another subject's test" test now covers Configure, Run and Report, and three new tests: the AX3 grep of `src/` for `TasksPage`, `ResultsPage` and the four per-task dict names, the retired modules gone, `show_setup`), `tests/test_config_flow.py` and `tests/test_config_preview.py` (stack counts), `tests/test_task_info.py` (the shared-table test now names the Test List, Add dialog and configuration page), `tests/test_settings_snapshot.py` (+8), `tests/test_report_page_actions.py` (+2).

**Files deleted**
- `src/ui/tasks_page.py`, `src/ui/results_page.py`. Neither had a test file of its own; the tests that named them were the two above. No per-task dict was left in `DashboardWindow` (P8a removed them), and `TASK_INFO` is imported from `src/engine/task_info.py` everywhere. `TaskSettingsDialog` stays: the standalone `--task X --gui` path still uses it (HB11).

**What was done**
- Run Test (4C steps 6 and 7, R2, R11, HC8): Run Test always opens the Start page; the banner, the disabled Start / Practice, Cancel and Esc, and the instructions are the P7b page's own. Practice is `AssessmentApp(run_mode="practice", practice_index=k, structural_overrides=<copy with trials = min(3, the test's trials)>)`, so the test's own dicts are never touched (tested: deep-equal in memory and on disk) and nothing is written under `sessions/` (tested: byte-identical tree). Start is `AssessmentApp(run_mode="record", seed=test.seed, test_id, test_name, config_name, the stored structural and live values, client = setup_page.client, preset calibration and its source / file, the Setup page's date, sex, notes and display acknowledgement, screen = window.screen())`. The title bar is hidden for Practice, Run and Finishing, the nav is locked from the Start page on, and `FINISHING` stays hidden (user-confirmed).
- Defensive checks: before a launch the flow re-reads the test (a test that has run since, or whose Subject ID no longer matches the Setup field case-insensitively, ends the flow with the reason on the Test List); and a run never dials the device: with no `setup_page.client` it refuses (the Start page's own blockers make that unreachable in use).
- Run end (C7, AC11, AC12, HD1): `ask_run_end(result, window)` then `finish_run(result, action, output_root=window.output_root, subject_id=, test_id=)`. Tested: Save links the run and locks the test (row "Done <date>", Run / Configure off, `report.json` cached, metadata carries `test_id`, `test_name`, `seed`, `config_name`, `outcome`, `planned_trials`, `completed_trials`); Save and View Report opens the report with the Start page and run view gone; Discard deletes the folder, leaves the test Not Done and re-runnable, and the run number is free again; `write_report_safely` runs once for a Save and never for a Discard; a quit with trials done gives "Ended early (1/3)" or a discard, "Keep going" keeps the run, a quit before any trial shows "nothing saved" and discards; the end dialogs are asked in `Flow.FINISHING` with the title bar hidden over the run view.
- Store errors (AC12): `TestLockedError`, `TestStoreError`, `ValueError`, `SessionDiscardError` and `OSError` from `finish_run` end the flow back on the Test List with the test selected and Not Done, the run folder untouched, a line under the table and a modal "Results not saved" / "Results not discarded" (the reason, the folder name, "<test> stays Not Done"). A real `TestLockedError` (the test was saved from elsewhere meanwhile) and a refusing `discard_session` are tested through the real functions.
- `metadata.settings` (P5 carry-forward): the run's final merged config goes through `run_settings`, so the block is complete for the task (every live key, every structural key, `structural.theme`, `structural.feedback.{hit_sound, miss_sound, particles}`, `live["dwell.visual_cursor"]`) and the report's Test Configuration table reads it (tested for all four tasks, and `build_config_rows` on the written file gives Theme "Forest", the cursor and Feedback rows, the named configuration). `source` / `profile_saved_at` / `profile_file` are kept beside it with their constructor defaults.
- View Report (4D step 7 host side, P7c TODOs): `ReportPage.set_report(report, test_name=test.name, evaluator=test.evaluator, notes=test.notes, subject=test.subject_id)` and `set_context(existing_test_names=<all names of the subject>, pdf_dir=<the run's session folder>)`; the test's Subject ID labels the page, never the Setup field's (the old Analyze bug, 4A.7). `load_or_build_report` failures (`ReportError` or anything else) are said on the Test List, as are a test that has not run and a data folder that is gone. Save & Continue writes the name only if it changed and notes / evaluator only if they changed, then returns to the list with the test selected; a failed write shows "Could not save: <reason>" on the page and stays; Cancel writes nothing.
- AX1 / AX2 (`tests/test_dashboard_e2e.py`): two Grid Click tests added, test 1 configured with a new named configuration "Fast hover", previewed with the mouse, Practice (3 of 3), Start, Pause (the trial in flight is dropped and returns), one Skip, the rest selected by hovering, Save and View Report: the report names the configuration, the summary reads `100% (2/2)` with the skipped trial excluded and the footnote saying so, Reaction Time and Entries filled; the list row reads "Done <date>" and is locked; Copy Test gives an unrun copy with the same configuration and a different seed; `sessions/` holds exactly one run folder; a second `DashboardWindow` with the same Subject ID shows the same rows and opens the same report. The mouse records no device-rate rows, so the pupil and saccade columns are "—" in that run; the real device is P9.
- Host-side AC coverage: AC1-AC3 (Start page, blockers, Cancel, nav lock), AC4-AC5 (practice length, seed, nothing written, repeatable, result line, quit), AC7 (title bar hidden and back), AC11-AC12, AC16 (new metadata fields on disk); AC6, AC8-AC10, AC13-AC15 were covered by P2 / P7b and are unchanged. AA10, AA11 (both halves), AA14 through the flow, AA16 and AX3's grep (minus "OperatorPanel", P8c).

**Tests added: 103 net** (89 in the five new files, +8 `test_settings_snapshot.py`, +2 `test_report_page_actions.py`, +4 in `test_dashboard_flow.py` after removing the placeholder test and adding two parametrized names).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o addopts=""`): baseline `1854 passed, 2 skipped`; after `1957 passed, 2 skipped in 250.01s`. No failures (`test_config_merges_task_over_default` passed here). `ruff` is clean on every new and changed file except the I001 in `src/app.py` that was there before.

**Deviations / judgement calls (none changes a SPEC decision)**
1. **How a store error is shown:** a modal OK dialog (so a failed Save cannot go unnoticed) and the same text as the Test List's line under the table (so it stays after the dialog). The text, the title and the dialog (`RunFlow.tell`) are new English wording; `RunFlow.ask_end` and `tell` are replaceable attributes so tests answer without a modal loop (like `ConfigFlow.ask_new_name`).
2. **`OSError` is caught too**, beyond the four types the brief lists: `discard_session` unlinks files one at a time and Windows can refuse one that another program has open, which would otherwise leave the window stuck in `FINISHING` with the title bar hidden and the run view up.
3. **`ReportPage.show_note(text)` added** (P7c file, 4 lines, like `TaskConfigPage.show_note`): the host needs somewhere to say a Save failed.
4. **A run that cannot start ends the flow** (back to the Test List with "Could not start <name>: <reason>"): the Start page has no place for a message. The same for the defensive checks above.
5. **The Practice press runs the same checks as Start** (subject, test not run since): the flow is stale in both cases. It uses the freshly read test for the run.
6. **`merged_config` added to `settings_snapshot.py`** so the Start page's instructions and `complete_settings` share one merge; `AssessmentApp` keeps its own in-place merge.
7. **`ReportFlow` catches `Exception`, not only `ReportError`,** from `load_or_build_report` (`ReportError` is a `ValueError` and is tested): a report bug on View Report should say so, not crash a slot. `finish_run` already does the same after a Save.
8. **`page.setFocus()` on the Start page** (on open and after a practice) so Esc (Cancel) works without a click first.
9. **Test fixtures:** the run-flow tests use `MouseGazeSource` as the Setup page's tracker with `run_blockers` replaced (`win.blockers`), and `preroll_ms` set to 0, so a run takes a second or two; a recorded run with that source writes a header-only `all_gaze.csv`.

**Follow-up 2026-10-07 (user answers to the §9 P8b points 1, 3 and 5; points 2, 4 and 6 stay as built).** This supersedes the matching lines above (the files list for `src/app.py`, the store-error bullet, judgement calls 1 and 4, and the "provenance keys kept" sentence).
- **Point 1, dialog only.** A failed Save or Discard at run end is shown as the modal "Results not saved" / "Results not discarded" dialog and nothing else: the extra line under the Test List table is gone (`RunFlow._on_run_finished` now ends with `self.tell(...)`). The flow still returns to the Test List with the test selected and Not Done. Test changed: the store-error tests assert the list's line stays empty.
- **Point 3, stay on the Start page.** `StartTestPage.show_note(text)` added (a muted `message_label` under the practice line, like `TaskConfigPage` / `ReportPage`; cleared by the next Start or Practice press, by a practice result and by `set_test`). Every reason a run cannot start (an error from `AssessmentApp`, a test that has run since, a changed Subject ID, no tracker) now shows "Could not start <name>: <reason>" there; the flow stays in `Flow.START` with the nav locked and the title bar showing, Start and Practice stay usable and Cancel still goes back. `RunFlow._leave` no longer takes a message. Tests: the five "cannot start" tests now assert the note and that the operator can fix the cause (restore `AssessmentApp`, reconnect the tracker) and press Start or Practice again, plus a Cancel after a failed start; `test_start_test_page.py` +4.
- **Point 5, provenance dropped.** `metadata.settings` is exactly `run_settings(...)`: `{config_name, live, structural}`. `source`, `profile_saved_at` and `profile_file` and the `AssessmentApp` arguments `settings_source`, `settings_saved_at`, `settings_profile_file` (and their three attributes) are removed; `schema.py`'s comment on `settings` now says old sessions may still carry the three keys. Readers searched in `src/`, `tests/`, `tools/`, `analysis/` and the docs: **none read them** (`report_config.py`, `report_quality.py` and `report_format.py` read `calibration_source` / `cal["source"]`, a different thing); `run_gui` (standalone `--task X --gui`) never passed them, so that path is unchanged and its tests pass. Tests: `test_run_settings_metadata.py` now asserts the block equals `run_settings` exactly, the three keys are gone and the three arguments raise `TypeError` (17 tests, was 14).
  - **Left for P8c / the hub, found by that search:** `docs/DATA_SCHEMA.md` has no `settings` block at all today, so there is no wording to remove, but P8c's schema pass should document `settings = {config_name, live, structural}` (and that old sessions may also hold the three dropped keys); `SPEC-live-settings-panel.md` (lines about `profile_file` and `profile_saved_at`, S10.4 and S10.12) is historical and was left alone; `settings_profile.resolve_settings_precedence` (it returns its own `source` / `saved_at` dict) is now used by tests only, since the old Tasks-tab flow that called it is gone: it could be retired with its tests (`test_settings_profile.py`, `test_target_visual_fixes.py`, `test_task_settings_dialog.py`), not done here.
- **pytest after the follow-up:** `1965 passed, 2 skipped in 238.73s` (was 1957: +4 `test_start_test_page.py`, +1 `test_run_flow.py` net, +3 `test_run_settings_metadata.py` net). `ruff` clean on the changed files. One more stray empty file named after a type annotation (`AssessmentApp`) appeared in the repo root and was deleted.

**Left undone (belongs to P8c / P9)**
- P8c: the AX3 cleanup of "OperatorPanel" in comments (`settings_registry.py`, `slider_spin.py`, `task_settings_dialog.py`, `wtmh_theme.py`, `base_task.py`, `click_grid.py`, `click_static.py`, `run_dashboard()`'s comment, `setup_page.py`'s comment on `subjectIdChanged`), `canvas.py` under 500, the theme's vertical-header padding, README, `docs/DATA_SCHEMA.md`, the SPEC-hud-hide-toggle superseded note, and the stale wireframe notes (`tasks.md`, `results.md`).
- P9: the live checks (a real window, real dialogs, the native save dialog, the real device, the pupil and saccade columns, AX4, AX5). Stray empty files named after type annotations (`AssessmentApp`, `SubjectTest`, `None`; the arrow-in-tool-input quirk) appeared in the repo root while writing and were deleted at once; `git status` shows only the files listed above.

### 2026-10-07 — P8c (cleanup C8: AX3 comments, `canvas.py` under 500, dead code of the retired flow, README and `docs/DATA_SCHEMA.md`), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`) before the first edit; P8a's and P8b's uncommitted work was built on, not reverted. `configs/default.yaml`, `configs/local_state.json` and `sessions/` untouched. No app launch, no live run, no qt-mcp; offscreen Qt only. No behaviour change anywhere (comments, dead code, one file split, docs).

**1. AX3 and stale comments**
- `grep -rnE "OperatorPanel|TasksPage|ResultsPage|_task_overrides|_task_live_overrides|_task_selected_profile|_task_session_dirs" src --include=*.py` finds nothing (exit 1). Reworded, keeping what each comment explains: `dashboard_window.py` (the `showMaximized()` rationale now says the old HUD column was the reason and why maximizing is still right; the Fusion-style comment lost the `operator_panel.py` pointer), `settings_registry.py` (both groups are shown on the configuration page), `slider_spin.py` (docstring), `task_settings_dialog.py` ("the old HUD's cards"). `tests/test_dashboard_flow.py`'s AX3 test now includes `"OperatorPanel"` in its list and the "that cleanup is P8c's" comment is gone, so the grep is a permanent test.
- Other stale wording, comments and docstrings only: `wtmh_theme.py` (docstring: no `operator_panel.py`, "Setup/Tests"; the `wtmhResultsScroll` selector of the deleted Results page removed from the transparent-scroll-area rule, nothing referenced it; "2 · Tests"; the Session Log mention), `base_task.py` (2), `click_grid.py` (2) and `click_static.py` ("HUD hide/show" now "window resize": the canvas still resizes mid-run), `subject_tests.py` ("Tests tab"), `setup_page.py` (the `subjectIdChanged` comment: nothing listens today, see §9), `settings_profile.py` (`load_settings_profile`'s docstring no longer points at the Tasks page's Load Settings).
- Stale `.pyc`: the only one of a deleted module under `src/**/__pycache__` was `src/ui/__pycache__/operator_panel.cpython-312.pyc` (no `tasks_page` / `results_page` pyc existed); deleted. `sample_rate`'s pyc went with that module (below).

**2. `src/ui/canvas.py` 506 to 471 lines**, behaviour unchanged. The distractor glyph code (the six `_SHAPE_*` constants and `TaskCanvas._shape_path`) moved verbatim to the new `src/ui/canvas_shapes.py` (47 lines: `SHAPE_CIRCLE ... SHAPE_STAR`, `shape_path(cx, cy, r, shape)`); the two call sites in `_draw_icon_scene` and `_draw_target` call it directly. `canvas_module.ICON_DRAW_FRAC` is still importable (a test pins it); no test or other module used the moved names.

**3. Theme vertical-header padding: NOT changed** (the brief's "if unsure"). `QHeaderView::section:vertical { padding: 0; }` would change the row height of every `QTableWidget` under `wtmhDashboard` that has no local override: Setup's calibration-details table (Setup is out of scope, U1) and the Test List table (`wtmhTestTable`, which the user has not yet seen at real-font heights). That is about 13 px per row (P7c's figure), which cannot be judged offscreen (no fonts) and no existing test would catch. See §9 for the one-line change and what it would touch. `wtmh_theme.py` is 492 lines.

**4. Dead code of the retired flow (each checked with a grep of `src/` and `tools/` first; a helper scan over every top-level and method name in `src/` for names that nothing in `src/` or `tools/` uses)**
- `settings_profile.resolve_settings_precedence`: retired. Called only by the old `DashboardWindow` at `c94d9fd`. Its 7 own tests in `tests/test_settings_profile.py` removed (carried beats profile, profile applies, no profile is defaults, empty profile is defaults, structural-only profile, dialog choice outranks profile, structural survives carried) together with their `_profile` helper. Five other test files used it only as one step on the way to "profile, merged over the task YAML, into the dialog": `test_grid_cell_gap.py` (2 uses), `test_phase_b_sizes.py` (2), `test_target_visual_fixes.py` (1), `test_task_settings_dialog.py` (2). They test the dialog and the merge, not the function, so they were **rewritten, not removed**: the step is now `stored = load_settings_profile(...)["structural"]` and `deep_merge(config["task"], stored)` (and `profile["live"]` for the live values). One dropped assertion, `resolved["source"] == "profile"`, belonged to the retired function.
- `settings_registry.format_calibration` (the old Tasks page badge text): retired, with its 3 tests in `tests/test_settings_profile.py`. Dead since P8a.
- `settings_registry.format_saved_at` re-export (kept only so the old dashboard's import kept working): removed with its identity test in `tests/test_settings_layout.py` (and that file's two imports). `tests/test_settings_profile.py` now imports `format_saved_at` from `src.engine.settings_profile`, where it lives.
- `src/engine/sample_rate.py` (`SampleRateTracker`, the HUD's device-rate meter, unused since P7b removed the meter; P7b's entry said "stays"): retired with `tests/test_sample_rate.py` (4 tests). It is a HUD helper and nothing in `src/` or `tools/` named it; a `git checkout` restores both if wanted. The historical SPECs that mention it are untouched.
- Found, **not retired**, listed in §9: `settings_profile.load_settings_profile` (dead in `src/`, but 29 test lines use it as the read-back of a save); `SetupPage.subjectIdChanged` (no listener since P8a, Setup is out of scope); and names unused before this redesign began (so not made dead by it): `estimate_grid_fit_radius_px`, `GazepointClient.is_streaming`, `GazepointClient.iter_samples`, `exporter.load_events` / `load_gaze_df` / `load_trials_df`, `inputs.base.Rect` / `contains`.
- No unused module-level constant and no unused import (`ruff` F401 and F841 are clean across `src`, `tests` and `tools`).

**5. Tests left for the HUD and the old tabs.** Searched `tests/` for `operator_panel`, `tasks_page`, `results_page`, the Tasks page's signals and badges, `calibration_snapshot`, `_resolve_settings` and the per-task dicts: what is left are absence guards (`test_run_bar.py`, `test_run_events.py`, `test_run_flow_app.py`, `test_run_engine.py`, `test_dashboard_flow.py`), which are the acceptance tests of AC7, AC14 and AX3 and stay. Tests in `test_grid_cell_gap.py`, `test_phase_b_sizes.py` and `test_target_size.py` still carry `HUD` in a name or constant (`test_hud_hide_mid_run_...`, `HUD_SHOWN`, `HUD_HIDDEN`); they call `task.set_screen_size(...)` mid-run, which is the real behaviour a window resize still triggers, so they were kept as they are (renaming would only change their ids).

**6. Docs**
- `README.md`: the standalone `--gui` paragraph (operator right panel replaced by the run bar), the dashboard section rewritten as the seven-step flow (Setup, Tests list, Configure and Preview, Start and Practice, Run with Pause / Skip trial / Quit, Test Complete, Report with Print Report), the run-folder naming; no "HUD" / "Hide HUD" / "Results" text remains. The pytest line now says `1950 passed, 2 skipped`.
- `docs/DATA_SCHEMA.md` (CRLF kept): the folder layout (`<date>_<subject>_<task>_run<N>`, `target_track.csv`, `report.json`) and the output-root stores (`_tests`, `_tests/<subject>/_deleted`, `_settings`, `_calibrations`); `metadata.json` rows `test_id`, `test_name`, `seed`, `run_mode`, `config_name`, `planned_trials`, `completed_trials`, `skipped_trials`, `interrupted_trials`, `pause_count`, `outcome`, `ended_by`, `ended_ns`, `layout_slots`, `raw_clock_offset_ns`, `settings`; a `settings` section (`{config_name, live, structural}`, noting that older sessions may carry `source` / `profile_saved_at` / `profile_file`); `trials.csv` columns `is_skipped`, `entries`, `end_x`, `end_y`, `slot_index` (and the two columns the table already lacked, `t_selectable_start_ns` and `reaction_time_from_selectable_ms`, which are in the code's header); a `target_track.csv` section; the event kinds as a table; "Removed with the HUD" (`hud_hidden_at_start`, `hud_toggle_count`, `HUD_TOGGLED`, `SETTING_CHANGED`, `SETTINGS_PROFILE_SAVED`, the last three confirmed in the code at `cf2183c`); a `report.json` section (`REPORT_VERSION`, the ten top-level keys); a Test store section (the record's fields and the saved-configuration files). Names and shapes were read from `schema.py`, `recorder.py`, `run_mode.py`, `subject_test_record.py`, `settings_profile.py`, `settings_snapshot.py`, `report_cache.py`, `report_metrics.py`, `report_quality.py` and `base_task.py`, not from this SPEC.
- `docs/specs/SPEC-hud-hide-toggle.md` and `docs/specs/SPEC-result-logic.md`: a "superseded by SPEC-compass-task-flow.md" note under the title (the Results tab for the second, with what stays current). Their history sections are unchanged.

**Files changed:** `src/ui/canvas.py`, `src/ui/canvas_shapes.py` (new), `src/ui/dashboard_window.py`, `src/ui/settings_registry.py`, `src/ui/slider_spin.py`, `src/ui/task_settings_dialog.py`, `src/ui/setup_page.py` (comment), `src/ui/wtmh_theme.py`, `src/tasks/base_task.py`, `src/tasks/click_grid.py`, `src/tasks/click_static.py` (comments), `src/engine/settings_profile.py`, `src/engine/subject_tests.py`; deleted `src/engine/sample_rate.py` and `tests/test_sample_rate.py`; tests `test_dashboard_flow.py`, `test_settings_profile.py`, `test_settings_layout.py`, `test_grid_cell_gap.py`, `test_phase_b_sizes.py`, `test_target_visual_fixes.py`, `test_task_settings_dialog.py`; docs `README.md`, `docs/DATA_SCHEMA.md`, the two older SPECs and this one.

**Tests:** none added (cleanup). **15 retired:** 4 (`test_sample_rate.py`) + 3 (`format_calibration`) + 7 (`resolve_settings_precedence`) + 1 (`format_saved_at` re-export identity).

**pytest** (`..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o addopts=""`): baseline `1965 passed, 2 skipped`; after `1950 passed, 2 skipped in 236.53s` (1965 - 15). No failures (`test_config_merges_task_over_default` passed here). `ruff` is clean on every changed file in `src` and `tests` (the findings that remain in the tree, UP017 and the like, were there before).

**Deviations / judgement calls (none changes a SPEC decision)**
1. Retired `SampleRateTracker` although P7b's entry said it stays (judgement: the brief names "HUD helpers" and nothing uses it).
2. Rewrote, rather than removed, the dialog and config-merge tests that used `resolve_settings_precedence` as a step.
3. Removed the dead `wtmhResultsScroll` selector from the theme (a comment-class cleanup, no widget uses the name).
4. Added the two `trials.csv` columns the schema table already lacked, so the table matches the header.

**Left undone:** the theme padding rule (§9), `load_settings_profile` and the other unused-before-the-redesign names (§9), the wireframes `tasks.md` / `results.md` (already marked superseded in P6), and everything live (P9). Four stray empty files named after text in a failed shell command (`section`, `the`, `tuple[float`, a quoted `QDoubleSpinBox` fragment) appeared in the repo root and were deleted at once; `git status` shows only the files above.

### 2026-10-07 — P9a (FX1-FX5, §7.1), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged. Branch confirmed (`feature/compass-task-flow`) before the first edit. `configs/default.yaml`, `configs/local_state.json` and `sessions/` untouched; no app launch, no qt-mcp, no live run. Qt facts were checked with qt-docs and context7 (`Qt.WA_StyledBackground`: "Indicates the widget should be drawn using a styled background"; the Style Sheets Reference for QWidget: a subclass needs the attribute or a `paintEvent`; `QEvent::DevicePixelRatioChange` since Qt 6.6, the project's floor) and then **measured** with throw-away scripts in the session scratchpad: widgets built and `grab()`bed with the Windows platform but never shown (and with the `offscreen` platform plus a dark application palette), to get real fonts and this PC's dark colour scheme without putting anything on the desktop.

**FX5 (the title bar).** `TitleBar.__init__` sets `Qt.WidgetAttribute.WA_StyledBackground` (`src/ui/dashboard_flow.py`). Measured before and after: without it the bar grabs `#f5f9fb` (the page), with it `#12374a` (`TITLEBAR_BG`).

**FX4 (physical px in the size and gap labels).** `choice_label(..., dpr=1.0)` multiplies the diameter / gap by the device pixel ratio before rounding; new `screen_dpr(screen)` (`src/ui/config_widgets.py`) reads it (1.0 without a screen or for a ratio <= 0); `ConfigForm` takes `dpr` (default 1.0) and `TaskConfigPage` passes `screen_dpr(screen)`. The standalone `TaskSettingsDialog` passes no ratio and is unchanged (see §9). For the lab monitor the label reads the same number at 100 % and at 150 % (the panel's px), where it showed 82 at 150 % before.

**FX3 (selection at open).** `SubjectTestListPage.reload` now selects `keep` (the selected test before the reload, or the one the dashboard asks for) if it is still listed, else the first row as the table shows it (after a sort too), and nothing for an empty list; `select_test` also sets the current cell, so the focus frame and the selection are the same row and `_update_buttons` gives the 4A.4 matrix for that row. Three existing tests assumed "nothing is selected at open" and were changed: `test_with_nothing_selected_only_add_is_on` and `test_the_delete_key_with_nothing_selected_asks_nothing` now call `page.table.clearSelection()` first (the matrix row still holds for that state), and `test_a_message_is_cleared_by_the_next_selection` selects a second test (selecting the already-selected first row changes nothing). The page is 495 lines (three stray blank lines before the class removed).

**FX2 (report tables clipped).** Root cause found and reproduced with the real `ReportPage` and real fonts: `ReportFlow.open` builds the page, fills it **while it has no parent** (no theme sheet, so no 4 px item padding) and only then puts it in the dashboard; `FitTable.fit_height` ran once, at `set_rows`, so the table kept the unpadded height while its rows grew from about 17 to 20 px under the theme: Summary was 102 px tall where its 33 px header, 80 px of rows and the frame need 115 (viewport 67 for 80 px of rows, exactly the live screenshot), Eye Metrics 13 px short too. (It was not the font and not the scale: 100 % and 150 % measured the same.) `FitTable` (`src/ui/report_tables.py`) now: `fit_height` polishes the table and both headers first, resizes the rows, and takes **header height = `max(minimumHeight, sizeHint().height())`** (what `QTableView` really lays the header out at, not `height()` before the first layout) **+ the sum of `rowHeight` + the frame**; and `event()` calls `fit_height` again after Polish, StyleChange, FontChange, ParentChange, Show and DevicePixelRatioChange. After the change the same page measures Summary 135 px (4 rows of 25), Eye Metrics 285, configuration table 392, none clipped, at 100 % and 1.5x. (Rows are 25 px now, not the 20 px they were cut to in the screenshot: that is the theme's padding, as designed.)

**FX1 (dialogs on the light theme).** Findings: (a) this PC's colour scheme is Dark and Fusion's `standardPalette()` is dark here (Window `#323232`, Base `#242424`), so `run_dashboard`'s palette line does not give a light fallback; (b) `AddTestDialog`'s `QListWidget` has no rule in `STYLESHEET`, so its base was `#242424` under the theme's dark `INK` labels (reproduced offscreen with a dark application palette); (c) under a style sheet a dialog's own palette does **not** reach its children (measured), so a palette on the dialog would not have fixed (b); (d) I could not reproduce the dark `QMessageBox` (both renders showed the sheet applied), cause unknown (§9). Fix: new `src/ui/dialog_theme.py` (45 lines; `wtmh_theme.py` is untouched at 492): `ITEM_VIEW_STYLESHEET` (a catch-all `QAbstractItemView` rule, white base and dark text, plus a `QListWidget` rule: border, no focus outline, hover tint, chosen row `SOFT_ACCENT`) and `apply_dialog_theme(dialog, extra_style="")` (object name `wtmhDashboard` + `STYLESHEET` + the item-view rules + `extra_style`). Used by `AddTestDialog`, `_ChoiceDialog` (so Test Complete, Save partial, Discard, Quit, Nothing saved and Delete) and `ConfigNameDialog`. `ask_two_choice` (the configuration page's Discard-changes question) no longer builds a `QMessageBox`: it calls `ask_choice` with `("accept", ..)` / `("reject", ..)`, the safe answer as primary and default, Esc = reject; no `QMessageBox` is left in `src/ui`. The in-place rename popup needed nothing: under the dashboard's sheet its text box is `PANEL_BG` / `INK` on a dark palette (a test pins it). Not touched: the native Print Report file dialog (the OS draws it).

**Files changed:** `src/ui/dashboard_flow.py`, `src/ui/config_widgets.py`, `src/ui/config_form.py`, `src/ui/task_config_page.py`, `src/ui/test_list_page.py`, `src/ui/report_tables.py`, `src/ui/add_test_dialog.py`, `src/ui/run_dialogs.py`, `src/ui/config_save_dialogs.py`; new `src/ui/dialog_theme.py`, `tests/test_dialog_theme.py`, `tests/test_report_tables.py`; tests changed `tests/test_test_list_page.py` (+7, 1 edited), `tests/test_test_list_actions.py` (2 edited), `tests/test_task_config_page.py` (+3, the real-question test rewritten for the new dialog), `tests/test_dashboard_flow.py` (+2); this SPEC.

**Tests added (38):** `test_dialog_theme.py` 13 (the helper; a tree in a themed dialog; the Add list light with dark names and the soft-tint chosen row on a dark palette; five question dialogs light on a dark palette; the rename popup; `ask_two_choice` built on `ask_choice` with the safe default; the real question answered; no `QMessageBox` in `src/ui`); `test_report_tables.py` 13 (height = header + rows + frame; filled parentless then put under the theme, the live bug; a style change after filling; grow and shrink; each of six events refits; a larger font; the real `ReportPage` built before the dashboard, and after Detailed and back, all three tables fit); `test_test_list_page.py` 7 (FX3); `test_task_config_page.py` 3 (`choice_label`, `screen_dpr`, labels at 150 %); `test_dashboard_flow.py` 2 (the attribute; the navy pixel). Mutation checks (not committed): without the item-view rules the three Add-dialog tests fail, and with the old `fit_height` and no refit events nine FitTable tests fail, including the real-page one.

**pytest** (`..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o addopts=""`): baseline `1950 passed, 2 skipped`; after `1988 passed, 2 skipped in 288.62s` (1950 + 38 new; no failures, `test_config_merges_task_over_default` passed here). `ruff` clean on every changed file in `src/ui` and `tests`.

**Deviations from the SPEC:** none. (Judgement calls, all inside the FX text: the choice dialog replaces the `QMessageBox` rather than restyling it; FX4 is the labels as listed; FX3's "last-used" is the page's own selection, which the dashboard already carries through `show_tests(select=...)`.)

**Left undone / for the hub's live check:** the three §9 points (the app-wide palette, the unexplained dark message box, the shrink hint's px). Live: Add New Test at both scalings; Discard changes (Cancel on the configuration page after an edit); Delete, quit, partial save, Test Complete; the Test List opening with row 1 selected and the matrix buttons on; the configuration page labels at 150 % (should equal the 100 % figures); Summary, Eye Metrics and Test Configuration showing every row at 100 % and 150 %, also after View Details and back; the navy title bar with readable nav text. README's test count (`1950 passed`) is now stale. Five stray empty files named after text in tool input (`200,`, `None`, `clipped_by`, `dict[str`, `str`) and one more (`SubjectTest`) appeared in the repo root and were deleted at once.

**Addendum, 2026-10-07 (hub follow-up, §9 point 3 resolved by the user): the amber fit hint shows physical px too.** `grid_fit_hint` and `icon_fit_hint` (`src/engine/target_size.py`) got a last parameter `px_scale=1.0` that multiplies **only the px shown** (the gap, the shrunk target, the shrunk icon); the decision to show a hint, and the fit itself, stay in the logical px the run draws in, so a ratio never makes a hint appear or vanish. I put the scale inside the two functions rather than scaling their inputs on the UI side because the icon fit subtracts a fixed logical-px ring (`EDGE_RING_PX`), so scaled inputs would be inexact for Scanning; the grid maths is linear and would have been exact either way. `ConfigForm.update_hint` passes its device pixel ratio (the same one the size and gap labels use). The standalone `TaskSettingsDialog` passes nothing and is unchanged (default 1.0, its tests untouched); no app-wide palette was added. **Tests (+9):** `test_fit_hints.py` 3 (the figures of both hints scale; a ratio never decides whether a hint shows); `test_task_config_page.py` 6 (grid hint at 1.5 for three layouts: the same figures as the 100 % screen within 1 px and exactly `grid_fit_hint(..., 1.5)` of the logical canvas, not the logical figures; scanning hint for two layouts the same way; a fitting layout stays hidden). `SCALED_SCREEN` there now has the lab canvas (1920 x 1000 physical) as its available area. Mutation check: passing no ratio from the form fails the five hint tests. **pytest** (same command): `1997 passed, 2 skipped in 293.02s` (1988 + 9; no failures; run on the final code, with `target_size.py` at 498 lines). `ruff` clean on the changed files; `git status` shows only intended files.

### 2026-10-07 — P9b (F6, P1-P4, §7.1), claude-sonnet-5-5 (spec-implementer), branch `feature/compass-task-flow`

Nothing committed or staged; tree was clean at `dc1d025`. Branch confirmed before the first edit. `configs/default.yaml`, `configs/local_state.json` and `sessions/` untouched; no app launch, no qt-mcp, no live run, no app-wide palette. Qt facts checked with qt-docs / context7 (`QPainter.drawRoundedRect(QRectF, xRadius, yRadius)`, the `QListView` `::item` sub-control "supports the box model", `QEvent::DevicePixelRatioChange` since 6.6) and then measured with throw-away scripts in the scratchpad (widgets rendered to images with the Windows platform and real Segoe UI, never shown; plus offscreen).

**F6 (Add dialog rows clipped).** Root cause, and it was my FX1: `ITEM_VIEW_STYLESHEET` gave `QListWidget::item` `padding: 2px`, and an item widget is laid out inside the item's padding box, so every label was 4 px shorter than its own size hint (measured with real fonts: label 36 px in a 40 px row; offscreen 32 in 36), which cut the descenders of the grey second line. Fix in two parts. (1) `src/ui/dialog_theme.py`: no `::item` padding (the label's own 6 / 4 px margins are the spacing; the comment says why). (2) `src/ui/add_test_dialog.py`: the row label is now `_TaskRow` (a `QLabel` that emits `remeasure` after Polish, StyleChange, FontChange and DevicePixelRatioChange), and `AddTestDialog.fit_items()` sets each item's size hint to its label's `sizeHint()` after `ensurePolished()`; it runs at the end of `__init__`, on `remeasure` and on every `showEvent`. Measured after: label height = size hint = row height (40 px) at 100 % and at `QT_SCALE_FACTOR=1.5`, and a render shows both lines in full.

**P1 (disabled buttons).** `src/ui/wtmh_theme.py`: new constants `DISABLED_BG #E9EDF0`, `DISABLED_BORDER #CDD6DC`, `DISABLED_TEXT #6F808A` (text 3.5:1 on the fill, asserted >= 3). `wtmhPrimary` / `cfgSave` `:disabled` is now the grey fill with muted text (it was the pale cyan `SOFT_ACCENT` with dark-teal text); `wtmhGhost` / `cfgPreview` / `cfgCancel` / `cfgReset` `:disabled` is grey fill, grey border, muted text. No border is added to the primary tier, so a button does not change size when it turns off (a test pins equal size hints). `wtmhSecondary:disabled` was already a neutral grey and is untouched.

**P2 (unchecked outline).** New `CONTROL_BORDER #7B93A1` (3.2:1 on white; the old `BORDER` is 1.2:1) replaces `BORDER` in the `::indicator` rule of both `QRadioButton` and `QCheckBox` (they had the same rule); hover and checked states unchanged. `wtmh_theme.py` is 496 lines (the new rules replaced old lines in place).

**P3 (number over the X).** `src/ui/target_map_paint.py`: `_label` takes an optional `badge=(fill, outline)` and draws a white pill (the text's width and the digits' height plus `BADGE_PAD` = 0.25 of the font's pixel size) behind the text; `_paint_mark` passes it for a not-selected target only, after the X is drawn. Hits (white on green) and skipped (dashed ring) are unchanged. Small public helpers `fit_font`, `digits_height` and `badge_pill` hold the label's font and the pill's geometry, so the tests derive them rather than guess.

**P4 (selected-trial map).** (a) The S marker is `max(13 * unit, 10)` px in radius (was 8 design px) with a `max(17 * unit, 13)` px letter. (b) A fixation is an opaque white circle with the translucent tint over it, so the path (drawn before) never shows through, and its number sits on a white pill with an accent outline, drawn after the circle; a short fixation's number is no longer shrunk to its tiny circle (`max_width` floor 12 px). The path is still drawn first, so fixation badges and the S are above it. (c) `TRIAL_PATH_LIGHT` is `#2B8CB0` (was the pale `#8FD3E8`, 1.7:1 on white; now 3.8:1, asserted >= 3), still lighter than `TRIAL_PATH_DARK`. A render at 880 px shows the S, the numbered pills and the ramp. A fixation shorter than about 150 ms still has a 9 px number (the existing size floor) inside a pill bigger than its circle; the pill is what shows, so the circle's size no longer tells its duration for those.

**Files changed:** `src/ui/add_test_dialog.py`, `src/ui/dialog_theme.py`, `src/ui/wtmh_theme.py`, `src/ui/target_map_paint.py`; tests `tests/test_add_test_dialog.py` (+9), `tests/test_target_map.py` (+6; the fixation-size test now measures the span of non-white pixels, since the number badge in the middle is white), new `tests/test_theme_controls.py` (17), new helper `tests/colour_helpers.py` (WCAG contrast, shared with `test_target_map.py`); this SPEC.

**Tests added (32):** F6 9 (row height >= label hint, on-screen rectangle >= hint and label height >= hint at the default font and at 14 and 22 pt; four events each measure again; a re-shown dialog measures again; no item padding); P3/P4 6 (no X-red pixel left inside the digits' box, arms still shown past the pill; a hit label keeps its green disc; `_label` draws a badge only when asked; a fixation covers the path and its number sits on pure white; the S is a larger disc; the ramp's light end has >= 3:1 contrast and the drawn newest end >= 2.8); P1/P2 17 (disabled colours and contrast; the rules of all six disabled selectors; rendered fills of disabled primary and ghost equal and different from every enabled state; disabled text colour and unchanged size; the four fixed-name configuration buttons; indicator contrast and rule; a rendered unchecked radio and check box outline is dark; a checked box still fills with the accent). Mutation checks (not committed): item padding back fails the three F6 geometry tests; no badges plus the old ramp fails four map tests; the old disabled / indicator rules fail 13 theme tests.

**pytest** (`..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o addopts=""`): baseline `1997 passed, 2 skipped`; after `2029 passed, 2 skipped in 286.31s` (1997 + 32; no failures). `ruff` clean on `src/ui` and the changed tests. Every file under `src/` except the old `setup_page.py` is under 500 lines.

**Deviations from the SPEC:** none. Judgement calls inside the table: P2 also changes the check box (same rule, as the table allows); the fixation number badge is added for every fixation, not only crossed ones; the S letter and radius sizes and the new colours are my picks (the table gives no values).

**Left undone / for the hub's live check:** Add New Test at 100 % and 1.5x (both lines of every row in full); a disabled Run Test / Add / Delete Test / Cancel / Preview against an enabled one; the radio and check box outlines on the configuration page; the Summary map with a missed target, including a shared place such as "3,9"; the Detailed map's S, numbered fixations over the path, and the path's newest end on white (the PDF uses the same drawing). README's test count (`1950 passed`) is still stale.

## 9. Implementer open questions

**P9a (FX1-FX5), 2026-10-07 — none blocking; three points for the hub.** Details in the §8 P9a entry:
- **2026-10-07** — **FX1's root cause is the application palette, which this pass did not change.** On this PC (Windows colour scheme Dark) Fusion's `standardPalette()` is itself dark (Window `#323232`, Base `#242424`), so `run_dashboard()`'s `app.setPalette(style.standardPalette())` (commented "a real light default", S13) gives every widget the theme's sheet does not name a dark fallback. The dialogs are fixed with rules in their own sheet (`src/ui/dialog_theme.py`), because under a style sheet Qt does not pass a dialog's palette on to its children (measured: a tree widget in a dialog with a sheet and a light dialog palette stayed `#242424`). The same fallback would hit any other unstyled widget on any page. The theme-level cure is a light palette built from the theme colours, set app-wide in `run_dashboard`; Setup is U1-frozen and was tuned against the dark fallback, so I left it. Add that in a later pass, or leave it?
- **2026-10-07** — **I could not reproduce the dark `QMessageBox` offscreen or in a hidden (not shown) Windows-platform render:** both showed the theme applied (body `#f5f9fb`), so why the live box ignored the sheet is not explained. `ask_two_choice` now uses the dashboard's own choice dialog (`run_dialogs._ChoiceDialog`, the one your live Test Complete capture shows correct), and no `QMessageBox` is left in `src/ui` (a test pins that). Please look at Discard-changes live.
- **2026-10-07** — **FX4 covers the size and gap labels only (as listed).** The amber shrink hints ("≈ N px to fit", `grid_fit_hint` / `icon_fit_hint` in the engine) and the standalone `TaskSettingsDialog`'s labels still show logical px, so at 150 % the page's labels and its hint use different units. Making the hint physical too is small (scale the canvas, radius and gap by the ratio before calling the engine functions); say if you want it, and for the dialog.
- **Resolved 2026-10-07 (user + hub):** (1) The app-wide light palette is a **backlog follow-up, not part of P9a** (it touches every page, Setup included, and needs its own live check). (2) The hub checks Discard changes live. (3) **Make the config page's amber fit hint physical px too** (same page, one unit); the standalone `TaskSettingsDialog` stays as it is.

**P8c, 2026-10-07 — none blocking; five points for the hub.** Details in the §8 P8c entry:
- **2026-10-07** — **The theme's vertical-header padding was left as it is.** `QHeaderView::section` in `wtmh_theme.py` pads a hidden vertical header too, so every `QTableWidget` under `wtmhDashboard` without a local override has rows about 13 px taller than their text: Setup's calibration-details table and the Test List table (`FitTable` and `FrozenColumnTable` override it locally). The fix is one rule, `QWidget#wtmhDashboard QHeaderView::section:vertical { padding: 0; }`, and `wtmh_theme.py` has room (492 lines). It would shrink those two tables' rows, which cannot be checked offscreen and which no test pins, and Setup is out of scope. Add it in P9 after looking at the Test List with real fonts (the two local overrides then become redundant and can stay)?
- **2026-10-07** — **`settings_profile.load_settings_profile` is dead in `src/`** (the old dashboard was its only caller) but kept: 29 test lines use it as the read-back of `save_settings_profile`. Retiring it means pointing those tests at `load_settings_profile_file(list_settings_profiles(...)[0])`. Say if it should go.
- **2026-10-07** — **`SetupPage.subjectIdChanged` has no listener** since P8a (the dashboard re-reads the Subject ID whenever a flow opens). Left in place because Setup is out of scope; only its comment was corrected. Also: Setup's button still reads "Continue to Tasks" while the tab is now "2 · Tests" (U1: Setup unchanged), which the README repeats as the button's real label.
- **2026-10-07** — FYI, found by the dead-code scan and **not** made dead by this redesign (unused before it began), so left alone: `estimate_grid_fit_radius_px` (tests only), `GazepointClient.is_streaming` (tests only), `GazepointClient.iter_samples`, `exporter.load_events` / `load_gaze_df` / `load_trials_df`, `inputs.base.Rect` and `contains`.
- **2026-10-07** — FYI: `src/engine/sample_rate.py` and its test file were retired although P7b's entry said they stay (a HUD helper; nothing used it). `git checkout -- src/engine/sample_rate.py tests/test_sample_rate.py` restores them.
- **Resolved 2026-10-07 (user + hub):** (1) The theme padding is decided in P9 from a real-font screenshot of the Test List and Setup's calibration table — **decided 2026-10-07: kept as it is** (§7.1). (2) `load_settings_profile` stays (tests use it to read saves back). (3) **User: rename Setup's button to "Continue to Tests"**, a narrow label-only exception to U1. The hub changed `setup_page.py` (label + 3 comments), README and `docs/wireframes/setup.md` / `.html`. `subjectIdChanged` stays unconnected (U1). (4) The pre-existing unused names are left alone. (5) The `sample_rate.py` retirement is accepted.

**P8b, 2026-10-07 — none blocking; six points for the hub to confirm.** Details in the §8 P8b entry:
- **2026-10-07** — **A failed Save or Discard at the end of a run is shown twice:** a modal "Results not saved" / "Results not discarded" dialog, and the same text as the line under the Test List table. The SPEC says "show them" without saying how. Say if only one is wanted (the dialog is `RunFlow.tell`, the line is one `show_message` call in `_on_run_finished`).
- **2026-10-07** — **`OSError` is caught at the run end beside the four listed types.** `discard_session` unlinks file by file and Windows can refuse one that is open elsewhere; without it the window would stay in `FINISHING` (title bar hidden, run view up). Say if it should not.
- **2026-10-07** — **A run that cannot start ends the flow back on the Test List** with "Could not start <name>: <reason>" (an exception from `AssessmentApp`, a test that has run since, a changed Subject ID, no tracker): the Start page has no message area. The alternative is a `show_note` on `StartTestPage` so the operator stays on it.
- **2026-10-07** — **`ReportPage.show_note(text)` was added** (a P7c file) so a failed Save has somewhere to say so. Four lines, mirrors `TaskConfigPage.show_note`.
- **2026-10-07** — **`metadata.settings.source`, `profile_saved_at` and `profile_file` are still written** (as the brief said) but nothing passes the three `AssessmentApp` arguments any more (the old Tasks-tab flow set them), so every run now records `"defaults"`, `""`, `""`. The configuration's own name is in `settings.config_name`. Drop the three keys and arguments, or keep them for the standalone launch?
- **2026-10-07** — FYI, no action needed unless you want it: Print Report's default file name takes the subject from the report's metadata (`ReportPage.set_report(subject=...)` only labels the header), the same value as `test.subject_id` for any run recorded through the dashboard. The new English wording (the two dialog titles and texts, the "Could not start / open the report" lines) has had no clinician review, like the other client-facing text.
- **Resolved 2026-10-07 (user + hub):** (1) A failed Save/Discard is shown **as the dialog only**; the line under the Test List is removed. (3) A run that cannot start **stays on the Start page** with a `show_note` line, so the operator can fix the cause and press Start again. (5) **Drop** `settings.source`, `profile_saved_at` and `profile_file` and their `AssessmentApp` arguments; `config_name` plus the snapshot say what was used. Hub accepts (2) the `OSError` catch, (4) `ReportPage.show_note`, and (6) as built; the clinician review of the wording stays a release item.

**P8a, 2026-10-07 — none blocking; five points for the hub to confirm.** Details in the §8 P8a entry:
- **2026-10-07** — **The Configuration Name combo has the same wheel hazard the guard fixes, and is not guarded.** The resolved decision names sliders and spin boxes. A wheel over the combo (without focus) changes its selection and emits `activated`, which loads a configuration (it asks before replacing edits, but a clean form is replaced at once). Guarding it is one more `guard_wheel` call in `config_form.py` plus `StrongFocus`; say if it should be added.
- **2026-10-07** — The saved Standard is a complete snapshot (4B.4 / HB12 over 4A.2's "empty"); see judgement call 4. Say if an untouched Standard should be stored empty instead (then `_on_save` skips `complete_settings` for `STORE_STANDARD`).
- **2026-10-07** — The title bar is hidden for `FINISHING` as well as Preview / Practice / Run (call 3). P8b can drop `FINISHING` from `Flow.hides_title_bar` if the end dialogs should show the bar.
- **2026-10-07** — Run Test / View Report are placeholder messages until P8b / P8c, and the Results tab is reachable but empty until P8c removes it (calls 1 and 2). Say if the Results nav button should be hidden now.
- **2026-10-07** — The configuration-name questions (Save as a new configuration, Configuration exists) and the in-place rename have new English wording taken from the wireframes; like the other client-facing text they have had no clinician review.
- **Resolved 2026-10-07 (user):** (1) **guard the Configuration Name combo too** (added in P8a). (2) A saved Standard stays a complete snapshot, as built. (3) The title bar stays hidden in `FINISHING`, as built. (4) The Results button stays until P8b retires it. (5) The clinician review of the wording stays a release item.

**P7c, 2026-10-06 — none blocking; five points for the hub to confirm.** Details in the §8 P7c entry:
- **2026-10-06** — **"the subject's folder" for Print Report is not defined by the SPEC** (4D.8: "default `<Subject>_<Test name>_<YYYY-MM-DD>.pdf` in the subject's folder"). Run folders are `sessions/<date>_<subject>_<task>_run<N>/` and the test store is `sessions/_tests/<subject>/`; there is no per-subject report folder. The page therefore takes the folder from the host (`set_context(pdf_dir=...)`) and, when none is given, offers the bare file name (the native dialog then starts wherever it last was). P8 must pass one; say which (the test's own run folder, `sessions/_tests/<subject>/`, or a new `sessions/_reports/<subject>/`).
- **2026-10-06** — `report.json` has **no hit-tolerance value**, but the Summary footnote ("Target area = drawn target + 40 px tolerance ring", fixed text in 4D.2) and the selected-trial map's dashed hitbox ring need it, and `dwell.jitter_tolerance_px` is a live setting on the configuration page that can differ from 40. The UI reads an optional `map.hit_tolerance_px` and falls back to 40, so a run with another tolerance shows a wrong ring and footnote. A one-line addition to the `map` block in `report_cache.build_report` (from `metadata.settings.live["dwell.jitter_tolerance_px"]`) fixes it; I did not touch the analysis modules. Add it in P8?
- **2026-10-06** — Summary percentages are shown as whole numbers (`61% (11/18)`, the wireframe) while `report.json`'s `pct_n` has one decimal (`61.1% (11/18)`). Confirm the wireframe form is wanted (it is computed from `n` and `N`, so no analysis is duplicated).
- **2026-10-06** — **P7a slip, not touched:** `src/ui/task_config_page.py:267` has `self._button("Save & Continue", "cfgSave")`; in Qt a single `&` makes the next letter a mnemonic and the button shows "Save Continue" with an underlined C (Alt+C). It needs `"Save && Continue"` (then `button.text()` is `Save && Continue`, as in the report page, whose test pins it). `tests/test_task_config_page.py` may assert the text.
- **2026-10-06** — The PDF's file-name date is the **test's date** (`started_ns`), not the day it is printed, so the same report always gets the same name; and the new client-facing wording (the four task sentences, the definitions list, the banner and footnote text) is English and unreviewed by a clinician, like the 4C.3 instructions.
- **FYI for P8 / the theme:** the `QHeaderView::section` rule in `wtmh_theme.py` pads a hidden vertical header too, which inflates the rows of any `QTableWidget` under `wtmhDashboard` by about 13 px (the calibration breakdown on Setup probably has it). `FitTable` overrides it locally; a theme fix (`QHeaderView::section:vertical { padding: 0; }`) would cover all tables but changes other pages' row heights.
- **P8 TODOs from this pass:** build one `ReportPage` and call `set_report(...)` / `set_context(...)` as listed under "Left undone" in the §8 entry; catch `ReportError` from `load_or_build_report` and show it; give `pdf_dir`; on `saved` write name / evaluator / notes through `subject_tests.rename_test` and `update_test(notes=, evaluator=)` and return to the Test List; show the page with the nav locked (R11); the page's own `Print Report` needs no host code.
- **Resolved 2026-10-07 (user + hub):** the default PDF folder is **the run's session folder** (P8 passes it as `pdf_dir`). Whole-number percents and the test date in the PDF file name are kept as built. The clinician review of the new wording stays a release item. **Fixed by the hub:** (2) `report_cache.build_report` now writes `map.hit_tolerance_px` from the run's `dwell.jitter_tolerance_px` (`None` when absent, then the UI uses 40), with a test in `tests/test_report_cache.py`; `REPORT_VERSION` is unchanged because the UI falls back to 40 for an older cache. (4) P7a's button now reads `"Save && Continue"`. The theme's vertical-header padding fix is left for P8 to decide. Hub pytest after P7: 1675 passed, 2 skipped.

**P7b, 2026-10-06 — none blocking; four points for the hub to confirm.** Details in the §8 P7b entry:
- **2026-10-06** — the Quit question pauses the run through `BaseTask.pause`, as 4C.6 says, so **a "Keep going" answer is not neutral**: it adds one to `pause_count`, and if a trial was in flight that trial is dropped (`TRIAL_INTERRUPTED`, `interrupted_trials` +1) and comes back as a fresh trial with a new clock. A confirmed quit counts the same way (the in-flight trial was going to be dropped anyway). If a quit question should leave no trace, the task would need a way to pause without counting, which is a `BaseTask` change outside this pass.
- **2026-10-06** — `report.json` is no longer built when a recorded run ends (HD1 carry-forward, done as the hub asked). The standalone `--task X --gui` path has no Save step, so its runs have no `report.json` until a report is opened (`load_or_build_report` builds it then). Confirm this is acceptable.
- **2026-10-06** — in Test Complete! the Enter key presses **Save and View Report** (the wireframe's primary button) and Esc / close gives **Save**; Discard Results is never the default. Confirm Enter should open the report rather than only save.
- **2026-10-06** — a blanket `taskkill //F //IM python.exe` was run once to stop a hung test (an unsynchronised test timer); it ended every python process on the machine, not just the test's. If another session lost a test run, a qt-mcp probe or an MCP server around 22:35 local time, that is why. No file was affected. The hung test was rewritten to poll for the dialog.
- **P8 TODOs from this pass:** call `ask_run_end(result, parent)` then `finish_run(result, action, output_root=, subject_id=, test_id=)` from the finish handler (a `RunResult` with `run_mode == "record"`); catch what `finish_run` may raise (`TestLockedError`, `TestStoreError`, `ValueError`, `SessionDiscardError`) and show it, the data is then still on disk and the test stays Not Done; for a practice `RunResult` call `StartTestPage.set_practice_result(result)` and return to the Start page; pass `practiceRequested(k)` as `AssessmentApp(practice_index=k)`; set `StartTestPage.set_blockers_provider(setup_page.run_blockers)`; hide the title bar while a practice or recorded run shows; an old Run flow in `DashboardWindow` still works (offscreen smoke) but is to be retired.
- **Resolved 2026-10-06 (user):** all accepted as built. "Keep going" counts as a pause and re-presents an in-flight trial (4C.6 as written). Standalone runs build `report.json` on demand. In Test Complete!, Enter = Save and View Report and Esc = Save. **Hub P8 TODOs added at review:** `canvas.py` is 506 lines, trim it under 500; AX3 greps `src/` for `OperatorPanel`, and stale comments still name it (`dashboard_window.py`, `settings_registry.py`, `slider_spin.py`, `tasks_page.py`, `task_settings_dialog.py`, `wtmh_theme.py`), so clean them. Hub pytest after P7b: 1526 passed, 2 skipped.

**P7a, 2026-10-06 — none blocking; two points for the hub to confirm, one optional follow-up.** Details in the §8 P7a entry:
- **2026-10-06** — SPEC conflict resolved in favour of AB8 (judgement call 1): 4B.3 says Save & Continue is disabled for "Standard with modified values", 4B.4 / AB8 / the wireframe say it opens the forced-rename dialog. The page leaves Save enabled there. If 4B.3 was meant literally, the forced-rename dialog never opens and AB8 cannot pass, so it should be read as "see 4B.4". Confirm.
- **2026-10-06** — the structural controls' tooltips (`CONFIG_TOOLTIPS` in `src/ui/config_widgets.py`) are new plain-language text; a clinician should read them before release, like the 4C.3 instructions.
- **2026-10-06** — optional follow-up, not built: wheel events over a slider or spin box change its value while the page is scrolled (a clinician scrolling with the mouse at 125 / 150 % could alter a setting unnoticed). The usual fix is an event filter that ignores the wheel on a control without focus. Say if it should be added in P8.
- **P8 TODOs from this pass:** build the page on Configure (`TaskConfigPage(task_id, merged_config, screen=...)`), then `set_context(subject_id=..., existing_test_names=<all names of this subject>, named_configs=list_named_configurations(...))` and `load_values(test_name=..., notes=..., config_name=test.configuration["name"], live=..., structural=...)`; apply the 4B.4 rules on `saveRequested` (compare `entry["live"]` / `["structural"]` with `page.standard_values()` for the Standard rename, with the named configuration for Update / new name; call `mark_clean()` if the page stays); on Preview return call `page.show_note("Preview finished. Nothing was recorded.")` and never `load_values()`.
- **Resolved 2026-10-06 (user):** AB8 wins. 4B.3's "Save disabled for Standard with modified values" is read as "see 4B.4": Save stays enabled and opens the forced-rename dialog. **Wheel guard: yes, add in P8**: a slider or spin box without focus ignores the wheel, so the wheel only scrolls the page. Tooltips: they need a clinician's review, which stays a release item (like 4C.3). Hub pytest after P7a: 1434 passed, 2 skipped.

**P5, 2026-10-06 — one point needs a hub decision (a test is left red on purpose); the rest are for the hub to confirm.** Details in the §8 P5 entry:
- **2026-10-06 — NEEDS A DECISION.** `tests/test_phase_b_sizes.py::test_click_grid_dialog_is_unchanged` asserts `set(d._controls) == {"trials", "target.size", "grid.rows", "grid.cols", "grid.gap"}`. HB3 puts `feedback.hit_sound` and `feedback.miss_sound` in `STRUCTURAL_SETTINGS`, and HB11 gives `TaskSettingsDialog` a bool branch so it renders them, so the dialog now has seven controls and that assertion fails. "Existing dialog tests must pass unchanged" cannot hold together with HB3 + HB11 for this one assertion, so it was **not edited** and the suite shows 1 failure. Options: (A, recommended) add the two keys to the expected set, the same kind of one-line edit as the earlier "Plus the Cell gap choice" comment there; (B) keep the dialog from rendering bool settings (then the HB11 bool branch has no use, and the standalone `--task X --gui` path cannot switch the sounds). Every other existing test passes unchanged, `tests/test_task_settings_dialog.py` included.
- **2026-10-06** — the brief named `src/engine/settings_registry.py`; the file is `src/ui/settings_registry.py` and was edited there (the SPEC gives only the file name).
- **2026-10-06** — added beyond B2-B4 (judgement calls 2-4 in the §8 entry): `format_saved_at` moved to `settings_profile.py` (re-exported, to avoid an import cycle); new `src/ui/settings_snapshot.py` with `settings_snapshot`, `complete_settings` and `run_settings`; `icon_fit_hint` takes the icon `slots`.
- **2026-10-06** — configuration names are matched case-insensitively and `save_settings_profile` refuses an invalid or reserved name with `ValueError` (judgement calls 5-7). The SPEC puts those rules on the page only; both are one-line changes.
- **Carry-forward (P4 TODO 2), done on the data side:** `run_settings(task_id, merged_config, config_name)` returns the R7 block with `structural.theme`, `structural.feedback.{hit_sound, miss_sound, particles}` and `live["dwell.visual_cursor"]` in the shape `report_config.py` reads, and a test pins the agreement; `report_config.py` and its tests were not changed. **P8 TODO:** write `run_settings(...)` of the final merged config into `metadata.settings` (merged with the existing `source` / `profile_*` provenance keys if they stay), and store `complete_settings(...)` (no theme, no `particles`: they are not controls) as the test entry's `config` snapshot and in saved profiles. If `feedback.particles` is removed as the dead key (4B.2), drop the `particles` lines from `run_settings` and the sparkle part of the report's Feedback row together.
- **P7 TODO:** the page renders `config_groups_for_task(task_id)` and gets its fit-hint texts from `grid_fit_hint` / `icon_fit_hint` (the page computes the canvas estimate and, for scanning, the slots with `scanning_layout_slots`, as the dialog does). Structural controls still need their tooltips (4B.1).
- **Resolved 2026-10-06 (hub):** option A. HB3 + HB11 (approved) mean the standalone dialog shows the two sound check boxes, so the hub added both keys to the expected set in `test_click_grid_dialog_is_unchanged`. The other P5 points are accepted; case-insensitive configuration names match R10's rule for test names. The P7/P8 TODOs above carry forward. Hub pytest: 1363 passed, 2 skipped.

**P4, 2026-10-06 — none blocking.** Points for the hub to confirm (details in the §8 P4 entry):
- **2026-10-06** — the report is built inside `_write_session_files`, before any run-end dialog (judgement call 3). 4D.6 / HD1 say a discarded run never computes it. With the current structure it does (about 0.5 s on an 18-trial run, then the folder and its `report.json` are deleted on Discard). If that matters, P7 can call `write_report_safely` after the Test Complete dialog instead (and "Save partial" the same), at the cost of "Save and View Report" building on the spot (`load_or_build_report` already does that).
- **2026-10-06** — the Test Configuration rows read the complete configuration snapshot of R7 from `metadata.settings`, but no code writes the Theme, Feedback or gaze-cursor values there yet (judgement call 10). `report_config.py` looks for `structural.theme` (a name or `{name}`), `structural.feedback.{hit_sound, miss_sound, particles}` and `live["dwell.visual_cursor"]`, the shape of today's task YAML and live keys. When P5/P8 define the snapshot, they must write those keys there, or `report_config.py` is the one file to adapt (the tests in `tests/test_report_config.py` pin the current reading).
- **2026-10-06** — `report.json` carries more than the 4D.6 list (judgement call 2), and the empty heat map is `data: []` with `empty: true`. P7's `TargetMapWidget` should read them as documented there.
- **Resolved 2026-10-06 (hub), carried forward:** (1) **P7 TODO:** move `write_report_safely` after the Test Complete / Save-partial choice so a discarded run never builds it (HD1 as written); "Save and View Report" builds on the spot via `load_or_build_report`. (2) **P5/P8 TODO:** the run's `metadata.settings` snapshot must carry `structural.theme`, `structural.feedback.{hit_sound,miss_sound,particles}` and `live["dwell.visual_cursor"]` in the shape `report_config.py` reads. (3) **P7 TODO:** `TargetMapWidget` reads the extra `report.json` keys per the §8 P4 entry.

**P3, 2026-10-06 — none blocking.** Points for the hub to confirm (details in the §8 P3 entry):
- **2026-10-06** — the optional `TARGET_ENTER` / `TARGET_EXIT` audit events are not built (judgement call 2). Say if P4 or the report wants them; they would also have to be added to the tests that assert exact event lists.
- **2026-10-06** — `metadata.layout_slots` is set in `__init__` and `raw_clock_offset_ns` in `_write_session_files`, not at the exact places 4D.4-4 / 4D.4-5 name (judgement calls 3 and 4); same values, same moment for the file.
- **2026-10-06** — exit commit reads literally: a valid off-target frame must carry the 120 ms, an invalid gap never does (judgement call 5). If a long gap between two valid frames should also count as time, that is a one-line change in `EntryTracker.update` plus G1 cases.
- **Resolved 2026-10-06 (hub):** all three accepted. The optional audit events stay unbuilt (not needed by P4/4D). Call 5 is the 4D.4-1 rule as written.

**P2, 2026-10-06 — none blocking.** Points for the hub to confirm (details in the §8 P2 entry):
- **2026-10-06** — `AssessmentApp` derives the practice and preview seeds itself from `run_mode` (`practice_index` for k), instead of the caller passing them (judgement call 1).
- **2026-10-06** — the R8 pre-roll shows the ITI-style scene without a target, not a fully empty canvas (judgement call 2).
- **2026-10-06** — pause is not yet wired into `AssessmentApp` (P7), skip is (judgement call 4). The HUD fields stay until P7 (judgement call 3).
- **Resolved 2026-10-06:** hub accepts calls 1, 3 and 4. **User chose the between-trials (ITI) screen for the R8 pre-roll** (same brightness as every later baseline); R8's "blank canvas" means "no target". P2's commit is held and goes in with P3 (R6).

None blocking P1. Two points for the hub to confirm:
- **2026-10-06** — Copy Test carries the **evaluator** over to the copy. **User 2026-10-06: keep it, as implemented.** 4A.6 and U3 ("identical unrun copy") list only notes, status, session link, date and counts as cleared, so this is the literal reading. If copies should start with a blank evaluator, change `evaluator=source.evaluator` in `copy_test` (`src/engine/subject_tests.py`) and the one assertion in `tests/test_subject_tests_lifecycle.py`.
- **2026-10-06** — `AssessmentApp(seed=...)` already feeds `build_task` (judgement call 5 above). Confirm P2 should drop that item from its list rather than expect it still open.

Points the hub should still confirm with the user while reviewing (from the drafts, not blocking):
- (a) The Evaluator field exists only on the report (Setup is unchanged, U1). HD14.
- (b) Peak saccade velocity is a smoothed value (HD7). It can be compared only across children
  measured on the same device and sample rate.
- (c) The read-aloud instruction text in 4C.3 needs a clinician's review before release.
- (d) Esc during a recorded run becomes "Quit with confirmation" instead of an immediate end
  (HC10).

**User answers 2026-10-06 (final):** (a) yes, Evaluator only on the report; (b) OK, smoothed
peak velocity accepted with that comparability caveat; (c) noted, clinician review of the 4C.3
text stays a release item; (d) yes, Esc in a recorded run = Quit with confirmation.

**Hub 2026-10-06:** the P2 seed-plumbing item for `AssessmentApp` is done in P1 (`seed` already
reaches `build_task`); P2 keeps only the practice/preview seeds and the rest of C1.

## 10. Log

- **2026-10-06** — The SPEC was created. The user's request was based on the Compass walkthrough
  (`b7401d3`).
- **2026-10-06** — Three read-only research passes ran (Tasks/settings, run lifecycle,
  results data). Their reports are in the session scratchpad and are summarised in §2.
- **2026-10-06** — User decisions U1–U12 were gathered in three question rounds, plus U13–U16
  after the drafts.
- **2026-10-06** — Four parallel drafting agents wrote 4A–4D. The hub merged them, reconciled
  the names (R1–R12) and wrote the phase plan.
- **2026-10-06** — Compass automation was evaluated in the same session. AutoGenesis
  (pywinauto, UIA) can't see Compass's Java controls. A PowerShell screenshot plus
  coordinate-click loop works, and it is available if any Compass behaviour needs checking
  during the wireframe phase.
- **2026-10-06** — The user approved the SPEC (all hub decisions and R1–R12) and added U17: implement on a separate branch. The SPEC was committed on the new branch `feature/compass-task-flow`.
- **2026-10-06** — P1 (A1-A4) implemented by spec-implementer (§8). Hub review: in scope, AA1-AA8, AA11 first half, AA13 and the store part of AA14 covered by tests; hub pytest 840 passed, 0 failed (728 before). User answered §9 (a)-(d) and kept the evaluator on Copy Test. Committed on the feature branch on the user's OK. No live check: P1 has no UI.
- **2026-10-06** — P2 (C1 engine, data side of `run_mode`, R8 pre-roll, B6 `MouseGazeSource`) and P3 (4D.4 recording additions) implemented by spec-implementer (§8). Hub review: in scope; hub pytest after P2 1031 passed / 2 skipped, after P3 1096 passed / 2 skipped, 0 failed. User chose the ITI screen for the R8 pre-roll; hub accepted the other §9 points. Committed together (R6: all new `trials.csv` columns in one commit) on the user's OK. No live check: no UI; exercised live in P9.
- **2026-10-06** — P4 (D3-D6 analysis modules, report cache, CLI) implemented by spec-implementer (§8; the pass was cut off by a usage limit once and resumed). Hub review: in scope, no UI; hub pytest 1262 passed / 2 skipped, 0 failed. AD6 sanity ran on scratchpad copies of 5 real folders only (`sessions/` unchanged). §9 P4 points carried forward as P5/P7/P8 TODOs. Committed on the user's OK.
- **2026-10-06** — P5 (B2-B4 settings layer) implemented by spec-implementer (§8). Hub review: in scope; the only UI change is the standalone dialog's two sound check boxes (HB3/HB11). The hub updated `test_click_grid_dialog_is_unchanged` to expect them (§9 option A). Hub pytest 1363 passed / 2 skipped, 0 failed. Committed on the user's OK.
- **2026-10-06** — P6 wireframes written by the hub and **approved by the user**: `docs/wireframes/test-list.md`, `task-config.md`, `start-test.md`, `run.md` (rewritten, no HUD), `run-end.md`, `report-summary.md`, `report-detailed.md` (+ rendered `.html`). `_nav.md` is now `1 · Setup / 2 · Tests` (R11). `tasks.md`, `results.md` and the dashboard part of `task-settings.md` are marked superseded (kept for history; P8 retires those tabs). Wording follows the SPEC plus later decisions (R10 60-char names, R2, Esc = quit with confirmation, clinician-review flag on the read-aloud text). Known wiremd limits: alert boxes render as plain text (as in `setup.html`), and the Test List button column renders as a row.
- **2026-10-06** — Handoff audit: §7 rows now cite their commits (P0 `cf2183c`, P1 `6d21642`, P2+P3 `b2691db`, P4 `f13091e`, P5 `29948ad`, P6 `f9c979e`). Next: P7.
- **2026-10-07** — P7 was implemented in three spec-implementer passes (§8). P7a built `TaskConfigPage` (B5), P7b the RunBar, `TaskRunView`, AssessmentApp run modes, quit flow, `StartTestPage` and the end dialogs, with the HUD and `operator_panel.py` removed (C3-C5, C7), and P7c `ReportPage`, `TargetMapWidget` and Print Report (D7, D8). Hub review: in scope, with offscreen tests only. Hub pytest after each pass: 1434 / 1526 / 1674, plus 1 hub test, giving **1675 passed, 2 skipped**. The user answered every §9 point, and the hub fixed `map.hit_tolerance_px` and the `&&` label. No live check: that comes in P8/P9. One incident: an implementer ran a blanket `taskkill` of python.exe, which also killed the qt-mcp server. The brief now forbids it. Committed on the user's OK.
- **2026-10-07** — P8 was implemented in three spec-implementer passes (§8). P8a built the Test List page, the Add dialog, the flow state and nav lock, Configure/Preview with the 4B.4 save rules, and the wheel guard; the user added the Configuration Name combo to the guard. P8b built `RunFlow` (Start, Practice, recorded run, `ask_run_end` + `finish_run`) and `ReportFlow` (`pdf_dir` = the run folder), made `metadata.settings` = `run_settings(...)`, and deleted `TasksPage`, `ResultsPage` and the Results nav. The user chose: dialog-only error on a failed Save/Discard, staying on the Start page when a run can't start, and dropping `source` / `profile_saved_at` / `profile_file`. P8c covered the AX3 comment cleanup (now pinned by a test), `canvas.py` from 506 to 471 lines (`canvas_shapes.py`), dead code retired (15 tests), README, `DATA_SCHEMA.md`, and the superseded notes. The hub renamed Setup's "Continue to Tasks" to "Continue to Tests" (user). Hub pytest after each pass: 1854 / 1965 / **1950 passed, 2 skipped** (the drop is the 15 retired tests). Review: in scope, every AA/AB/AC host-side criterion and AX3 are covered by offscreen tests, and AX1/AX2 run offscreen with a mouse source. **No live check: the user chose to commit P8 and do the full live validation in P9.** Committed on the user's OK.
- **2026-10-07** — P9 part 1 (fake server, port 4250, subject `P9TEST`) run live by the hub through qt-mcp. qt-mcp could not drive the app's own modal dialogs (`exec()` wedges the probe), so the hub launched the dashboard through a scratchpad QA harness that defers the probe's clicks and key presses (`QTimer.singleShot(0)`); app code untouched. **Passed:** AX1 (2 Grid Click tests, named configuration "P9 Large" via the forced-rename dialog with "Standard" refused, Preview with the mouse, Practice records nothing, Start, Pause (TRIAL_INTERRUPTED + PAUSED + RESUMED in `events.jsonl`), Skip (SKIPPED, 1 trial excluded in the report), finish, Save and View Report; row Done and locked; Copy Test = same configuration, new seed 335763 vs 198295; one run folder); AX2 (restart, same Subject ID: list, statuses and report unchanged); AX3 (test-pinned); A7 (F2 rename incl. a Done test, case-insensitive duplicate refused, Delete to `_deleted/`, subject switch); AB13 (unsaved Small size used by Preview, mouse dwell scores hits), AB14 (`sessions/` listing identical after two Previews), AB16 (Esc and natural finish return to the page with values kept, "Preview finished" note), AB17/AB18 (4 configuration pages clean at 100 %, scroll with pinned footer at 1.5×), AX4 (Setup, Test List, Config, Start with the blocker banner, Report at 1.5×); quit with confirmation ("1 of 32 trials are done"), Discard deletes the run folder and leaves the test Not Done, Quit + "Save partial results" gives `ended_early` / `operator_quit` / 3 of 18 trials with `report.json`, row "Ended early (3/18)". Report checked: configuration table, Target Map with gaze path + heat map, Eye Metrics filled, Detailed view (frozen Trial column, skipped row, selected-trial pane). **Not tested:** AB15 (Preview with no tracker), the PDF export (native dialog; moved to part 2). **Findings FX1–FX5** (§7.1). User: fix all five now (P9a), then the real-device half; theme padding kept. Practice scored 0 of 3 on the fake server (its scripted gaze rarely dwells on a target): expected, not a defect. `configs/local_state.json` was set back to port 4242 after the run.
- **2026-10-07** — P9a (FX1–FX5, §7.1) implemented by spec-implementer (§8) plus the §9 follow-up (amber fit hint in physical px). Hub review: in scope, `wtmh_theme.py` untouched (new `dialog_theme.py`), largest file `target_size.py` 498 lines, no stray files. Hub pytest 1997 passed / 2 skipped, 0 failed (1950 before). Live re-check on the fake server through the QA harness with OS-level window captures (`PrintWindow`): FX1 (Add New Test list white with dark names, Discard changes themed), FX2 (Summary 4/4 rows, Eye Metrics 10/10, configuration 17/17, also after View Details and back; at 100 % and 1.5×), FX3 (Test List opens with row 1 selected, buttons per the matrix), FX4 (124/207/331 px labels at 1.5×, amber hint "≈ 218 px"), FX5 (navy title bar) all pass. The user asked for a readability review during the re-check; it found F6 (Add-dialog description clipping) and P1–P4 (disabled-button look, faint radio outlines, Target Map numbers under the X, selected-trial map markers). User: commit P9a, fix those as P9b, then the real-device half. README pytest count updated to 1997.
- **2026-10-07** — P9b (F6, P1–P4, §7.1) implemented by spec-implementer (§8). Hub review: in scope (theme rules, `AddTestDialog` row sizing, `target_map_paint.py`), `wtmh_theme.py` 496 lines, no stray files. Hub pytest 2029 passed / 2 skipped, 0 failed. Live re-check on the fake server with OS-level captures: F6 (both lines of every Add-dialog item in full at 100 % and 1.5×; the cause was P9a's own `::item` padding), P1 (disabled buttons grey and clearly off on Setup, Test List and the Add dialog), P2 (unchecked radio outlines visible), P3 (Target Map numbers on white badges over the X), P4 (S marker ~20 px, fixation numbers above the path, newest path end a visible teal) all pass; no new readability issue seen. Noted to the user: a fixation shorter than ~150 ms now shows its number badge larger than its circle. Committed on the user's OK; README pytest count 2029.
- **2026-10-07** — Handoff audit: §7 P9 row marks part 1 done (fixes P9a `dc1d025`, P9b `4f0145f`) and part 2 open; §7.1 cites both hashes; §9 P8c point 1 marked decided (padding kept). Next: P9 part 2 on the real GP3 HD with the user as subject.
- **2026-10-07** — P9 part 2 (real GP3 HD, SN 23309153, 150 Hz, Gazepoint Control on 4242; subject `P9REAL` = the user; dashboard through the QA harness, no app code changed). **Passed:** AB15 (before Connect, with no calibration: Test List reachable, Configure → Preview runs on the mouse, status "PREVIEW · mouse pointer · nothing is recorded", Esc back to the config page). Grid Click 1: Practice + recorded run, `2026-10-07_P9REAL_click_grid_run1`, 18/18 hits, Reaction Time mean 0.53 s, error-free 44 % (8/18), Entries mean 1.83, valid gaze 96 %, saccade and pupil data present, `report.json` written after Save. Follow & Click 1: recorded run `2026-10-07_P9REAL_follow_moving_run1` (6 trials, `target_track.csv` written) and **Print Report produced the PDF in the run folder** (`P9REAL_Follow & Click 1_2026-10-07.pdf`, user opened it). **Not confirmed:** AX5 for Follow & Click — only 2/6 selected and valid gaze 38 % (report warning "below the 80% floor" fired as designed): the device itself lost the right eye (RPV 12–50 % per trial, LPV ~90 %) and BPOGV fell 70 → 8 % over the run, so this is a tracking/setup problem, not an app defect; to be re-run via Copy Test. The Grid Click gaze path could not be judged against the targets because of the raw-gaze tremor (V2). **User findings V1–V5** (legend, gaze path, PDF portrait, Add-dialog spacing/scroll, seconds instead of ms) recorded as **P9c** in §7.1 with the user's decisions. Also seen (separate, pre-existing): the Setup calibration banner's "mean error 74px" (vendor `AVE_ERROR`) disagrees with the 6–25 px per-point breakdown on the same page. The user has further feedback on Follow & Click and on the current build to give before P9c is implemented; the live re-check (incl. the Follow & Click re-run) comes after P9c. Old pre-redesign sessions not deleted (U16 still open).
- **2026-10-07** — The user's further feedback (from the doctor) was collected. It did not go into P9c; it is a new SPEC, `SPEC-input-selection-and-follow.md` (approved). It adds per-test Pointer (Gaze/Mouse) and Selection (Dwell/Switch; the user's switch sends a left mouse click) and removes the click from Follow & Click (renamed Follow the Target; pursuit metrics). Order: P9c (V1-V5) first, then that SPEC. Because Follow loses its selection, the Follow & Click AX5 re-run is superseded by that SPEC's live check (A10).
