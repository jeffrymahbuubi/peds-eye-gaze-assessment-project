---
name: SPEC-compass-task-flow
title: Compass-style task flow — per-subject Test List, configuration page, Preview/Practice, HUD-less run, per-test report
status: approved 2026-10-06 (U1-U17, R1-R12 and all per-part hub decisions); not implemented; implementation on branch feature/compass-task-flow
created: 2026-10-06
last_updated: 2026-10-06
next_step: P1 on branch feature/compass-task-flow (check the branch out first; see U17)
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
| P0 | User approves this SPEC (§3.2 and the per-part hub decisions); the hub commits it | — | — |
| P1 | **Store and path safety:** `safe_subject_dirname` (A1); `task_info.py` (A2); `subject_tests.py` with `seed`, `evaluator`, R1 names (A3); `test_id` / `test_name` / `seed` in metadata (A4) | no | P0 |
| P2 | **Run engine, no UI:** `is_skipped`, `pause` / `resume` / `skip_trial`, seed plumbing, new metadata fields, `NullRecorder`, `run_mode`, `discard_session`, `tracking_status`, `task_instructions`, `run_blockers`, the R8 pre-roll (C1); `MouseGazeSource` (B6) | no | P1 |
| P3 | **Recording additions:** `EntryTracker`, `entries` / `end_x` / `end_y` / `slot_index`, `target_track.csv`, `layout_slots`, `raw_clock_offset_ns` (D2). The `trials.csv` header changes in the same commit as P2's `is_skipped` if possible (R6) | no | P2 |
| P4 | **Analysis modules:** geometry, saccades, trial metrics, visual data, cache + `_shutdown` hook + CLI (D3–D6); run the CLI on real folders and log the numbers | no | P3 |
| P5 | **Settings layer:** structural `bool` kind, `config_groups_for_task`, profile schema v2 with `name`, `list_named_configurations`, the extracted fit hints, the bool branch in `TaskSettingsDialog` (B2–B4) | no | P1 |
| P6 | **Wireframes:** `test-list.md` (A5), `task-config.md` (B1), `start-test.md`, the `run.md` rewrite and `run-end.md` (C2), `report-summary.md` / `report-detailed.md` (D1). All replace stale `tasks.md`, `task-settings.md` (dashboard part) and `run.md` | **WF** | P0 (can run in parallel with P1–P5) |
| P7 | **Widgets:** `TaskConfigPage` (B5); `RunBar` + new `TaskRunView` + `TaskCanvas.set_paused`, deleting `operator_panel.py` (C3); `AssessmentApp` run modes and quit flow (C4); `StartTestPage` (C5); end dialogs (C7); `ReportPage` + `TargetMapWidget` (D7); Print Report (D8). Offscreen tests only | after P6 | P2–P6 |
| P8 | **Dashboard integration:** `SubjectTestListPage` + `AddTestDialog` (A6, no bridge needed); flow state and nav lock (C6); Configure / Preview / Run / Report wiring (B7); retire `TasksPage`, `ResultsPage`, nav "3 · Results"; cleanup (C8); README and `docs/DATA_SCHEMA.md` | after P6 | P7 |
| P9 | **Live validation:** fake server (AX1–AX4, A7, B8), then the real device with the user as subject (C9, D9, AX5). Then, **only on the user's explicit OK at that moment**, delete the old pre-redesign session folders (U16). Memory update | — | P8 |

P1–P5 have no UI, so they can be reviewed and committed one by one before the wireframes.

## 8. Impl log

*(empty — filled by the implementer per phase)*

## 9. Implementer open questions

*(empty)*

Points the hub should still confirm with the user while reviewing (from the drafts, not blocking):
- (a) The Evaluator field exists only on the report (Setup is unchanged, U1). HD14.
- (b) Peak saccade velocity is a smoothed value (HD7). It can be compared only across children
  measured on the same device and sample rate.
- (c) The read-aloud instruction text in 4C.3 needs a clinician's review before release.
- (d) Esc during a recorded run becomes "Quit with confirmation" instead of an immediate end
  (HC10).

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
