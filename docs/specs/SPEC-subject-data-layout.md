---
name: SPEC-subject-data-layout
title: Per-subject data folders — one folder per child holding calibrations, settings, tests, runs and reports
status: done 2026-10-08 (D1-D6, H1-H13; D4 revised: no Anonymous code option)
created: 2026-10-07
last_updated: 2026-10-08
next_step: all steps DONE 2026-10-08 (step 6 removed the Anonymous code option); merged into feature/compass-task-flow; push is the user's
related:
  - SPEC-compass-task-flow.md (Test List store 4A, run end / Discard 4C.6, report + PDF 4D; branch feature/compass-task-flow, U17)
  - SPEC-input-selection-and-follow.md (adds pointer_stream.csv inside a run folder; built first)
  - SPEC-display-scaling-cursor-accuracy.md, SPEC-gazepoint-analysis-export-parity.md (run files whose names stay unchanged)
---

# SPEC-subject-data-layout — one folder per child

**Status: approved 2026-10-07 (D1-D6 user decisions, H1-H13 hub decisions approved by the user).
Branch `feature/compass-task-flow`. Built after SPEC-input-selection-and-follow.md, before the
v2.0.0 merge (D6).**

## 1. Origin

The user (2026-10-07): the output folder is cluttered. `sessions/` holds every run folder side by
side plus `_calibrations`, `_diagnostics`, `_settings` and `_tests`, so one child's data is spread
over four places. The user proposed one folder per subject:

```
Subject
 - diagnostics
 - settings
 - calibrations
 - tests
 - run
   click grid
   ..
   scanning
```

Four read-only agents worked on it in parallel: a code impact map, a refinement of the user's tree
(design A), a test-centric alternative (design B: one folder per test) and a conventions survey
(BIDS / BEP020 eye tracking, clinical tools, Windows path rules, privacy). Their findings are
condensed in §2 and §3.2.

## 2. Current code (impact map, 2026-10-07, feature branch after `1308891`; line numbers re-checked 2026-10-08 at `4cbbce0`)

- **Run folder** `sessions/<date>_<subject>_<task>_run<N>/`, flat under the root. The path is
  composed twice, independently: `src/app.py:322-327` (needed for `calibration.json` before the
  recorder exists) and `src/data/recorder.py:69`. `next_run_number` (`session_naming.py:63-79`)
  probes the root for the composite name; N resets daily.
- **Test record → run link:** `session_dir` (`subject_test_record.py:59`) stores the folder NAME
  only. `record_result` requires `folder.parent == output_root` (`subject_tests.py:390-392`).
  Readers join it onto the root (`report_flow.py:64`, `test_list_page.py:304`).
- **Discard guard** (`session_files.py:14, 53-61`): the folder must be a direct child of the root,
  match `^\d{4}-\d{2}-\d{2}_.+_run\d+$`, and hold plain files only.
- **Tests** `_tests/<subj>/t_<id>.json` (+ `_deleted/`): one indirection, `subject_tests_dir`
  (`subject_tests.py:101`).
- **Settings** `_settings/<subj>/<task>/<ts>.json` (+ legacy flat `<task>.json`):
  `subject_settings_dir` (`settings_profile.py:64`).
- **Calibrations** `_calibrations/<subj>/calibration_<n>pt.json`: `_subject_calibration_dir`
  (`setup_page.py:146-156`, a UI module, literal `"_calibrations"`).
- **Diagnostics** `_diagnostics/calibration_timing.jsonl`, `gaze_dropouts.jsonl`
  (`calibration.py:267`, `gaze_diagnostics.py:26`): machine-wide, **no subject field** in any line.
- **Subject list** for the Setup completer: `known_subject_ids` (`settings_profile.py:141-170`)
  unions the three `_` dirs; folder names, not the typed ids.
- **Output root** `recording.output_root: "sessions"` (`configs/default.yaml:77`), relative to the
  cwd (frozen exe: next to the exe). Read in three independent places: `app.py:322`,
  `dashboard_flow.py:71-74`, `setup_page.py` (4 call sites).
- **PDF** default `<run folder>/<Subject>_<Test name>_<date>.pdf` (`report_format.py:352-358`, `pdf_default_name`).
- **Subject → folder name:** `safe_subject_dirname` (`session_naming.py:30-60`): NFC, illegal
  characters to `_`, trailing dots/spaces stripped, cut at 80, device names prefixed, `~` + 6 hex
  of the SHA-1 when anything changed. Applied with and without `.strip()` in different callers.
- About 25 test files pin today's layout (§4 of the impact report: run naming, discard guard,
  `_tests`/`_settings`/`_calibrations`/`_diagnostics` literals, "nothing written" snapshots).
- On disk (2026-10-07, after U16): 9 runs (P9REAL 2, P9TEST 2, tesst 5), each linked by exactly
  one test record; leftovers of old subjects with no runs: `_calibrations/{DIKI, DISP150, DPI100,
  DPI150, HUDTEST, TESTING}`, `_settings/{DIKI, TESTING}`, `_tests/TESTING` (2 Not Done records).
  `sessions/` is gitignored.

## 3. Decisions

### 3.1 User decisions (2026-10-07, final)

| Id | Decision |
|---|---|
| D1 | **Layout A**, the user's tree refined: per subject `calibrations/`, `settings/`, `tests/`, `runs/<task>/<run>/`, plus `reports/` for the PDFs. Tests and run data stay in separate trees (not one folder per test). |
| D2 | **Diagnostics stay machine-wide**, in `sessions/_system/diagnostics/`, not per subject (the logs carry no subject and are analysed across all runs). |
| D3 | The Subject ID may be a pseudonym code **or** a child's real name; the app must not assume either. |
| D4 | ~~An "Anonymous code" folder option~~ **Revised 2026-10-08 (user, after the live check): no Anonymous code option.** A folder named `S-0001` while every page says the Subject ID would confuse clinicians. The subject folder is always the Subject ID. Setup shows a hint under Subject ID: "Use a study code, not the child's name." Privacy rests on the study's own codes. (Original D4: a subject's folder could be named `S-0001` instead of the Subject ID.) See step 6. |
| D5 | ~~Migration~~ **Revised 2026-10-08 (user): no migration.** All data in `sessions/` is test data. The old-layout folders (the 9 runs, `_calibrations`, `_settings`, `_tests`, `_diagnostics`) are deleted, **without a backup**, when this SPEC lands. No legacy-layout reading code stays in the app. Data written by the v1.0.0 exe is ignored. (Original D5: a one-time script moved the 9 runs of P9REAL, P9TEST and tesst and deleted the subjects with no run.) |
| D6 | Built **after** SPEC-input-selection-and-follow.md, **before** the v2.0.0 merge (both touch `recorder.py` / `app.py`). |

### 3.2 Research notes (agents, 2026-10-07)

- BIDS: `sub-<label>/[ses-<label>/]<datatype>/`; labels alphanumeric; raw vs `derivatives/`;
  optional `participants.tsv`. Full BIDS (BEP020 `.tsv.gz` per eye) is out of scope; nothing here
  blocks a later BIDS export.
- Windows: MAX_PATH 260 incl. drive and NUL; Explorer, zip and OneDrive still fail beyond it even
  with the registry key. Illegal `< > : " / \ | ? *`, device names, no trailing dot/space; paths are
  case-insensitive.
- Privacy: a real name in a folder or file name travels with every copy (HIPAA identifier 1; GDPR
  Recital 26 treats pseudonymised data as personal while a key exists). The layout can keep the id
  out of everything except the subject folder name and the JSON `subject_id` fields; a full
  de-identified export (rewriting `subject_id` inside files) is a separate tool, out of scope.
- Tobii Pro Lab precedent: per-participant zip export; recording to OneDrive/network drives is not
  supported. Machine logs belong outside participant data.

### 3.3 Hub decisions (approved by the user 2026-10-07)

- **H1 Tree.**
  ```
  sessions/
    _system/
      diagnostics/calibration_timing.jsonl, gaze_dropouts.jsonl
      replay/                    headless --replay output (today: sessions/replay_*)
    <subject folder>/            name per H5/H6
      subject.json
      calibrations/calibration_<n>pt.json
      settings/<task_id>/<YYYY-MM-DD_HH-MM-SS>.json
      tests/t_<id>.json          + tests/_deleted/
      runs/<task_id>/<YYYY-MM-DD_HHMM>/   the run files, names unchanged
      reports/<YYYY-MM-DD>_<test name>.pdf
  ```
  Task folders use the stable `task_id` (`click_static`, `click_grid`, `follow_moving`,
  `scanning`), not display names ("Follow & Click" is being renamed). `_system` is a reserved
  name; a subject typed `_system` gets a prefixed folder.
- **H2 Run folder name** `<YYYY-MM-DD>_<HHMM>` (local time at run start), `_2`, `_3` on a
  same-minute collision. Created with an atomic `mkdir` (no `exist_ok`), so two runs can never
  share a folder. No test name and no subject in it (renames would make it stale; privacy D3).
  Composed in ONE function (`new_run_dir`) used by both `app.py` and the recorder.
- **H3 `session_id`** becomes `<task_id>_<YYYY-MM-DD_HHMM>_<test_id>`: unique across subjects, no
  subject in it, so `session.log` ("Session started: …") and `report.json` no longer carry the id.
- **H4 Test record link.** `session_dir` is replaced by `run_dir`, a path **relative to the subject
  folder** (`runs/click_grid/2026-10-07_1432`). Record schema version +1. `record_result` checks the
  run lies under `<subject>/runs/`.
- **H5 Subject folder resolution.** `subject.json` = `{"subject_id": <as first typed>, "folder_mode":
  "id" | "code", "created_at": …}`. A folder is a subject folder only if it holds `subject.json`.
  The app finds a subject by scanning the root's `subject.json` files and matching `subject_id`
  case-insensitively (casefold); it never recomputes the folder name from the id. In mode `id` the
  folder name is `safe_subject_dirname(id.strip())` capped at **40** characters (+ `~hash` when
  changed), so "Ana" and "ANA" stay one subject (as on NTFS today). The Setup completer lists the
  `subject_id` values from `subject.json`, verbatim.
- **H6 Anonymous code (D4).** **Superseded 2026-10-08 by D4 revised and step 6: no code option; the Test List button below stays.** Original: On Setup, when the typed Subject ID is **new** (no matching
  `subject.json`), a choice appears: "Folder name: (•) Subject ID ( ) Anonymous code". Code = the
  next free `S-0001`, `S-0002`… (never reused). The choice is fixed when the subject's folder is
  created (first save of anything) and shown read-only afterwards ("Folder: S-0003"). The Test List
  gets an **"Open Subject Folder"** button (all modes) that opens the subject folder in Explorer.
  Limit, stated in the UI tooltip: the code hides the name from folder and zip names only; the
  files inside still hold the Subject ID.
- **H7 PDF.** Default folder `<subject>/reports/`; default name `<YYYY-MM-DD>_<test name>.pdf`
  (test name sanitised and cut at 50 characters); no subject in the file name. The operator can
  still choose another name/folder in the save dialog.
- **H8 One output root.** A single `output_root()` function (engine) used by `app.py`,
  `dashboard_flow.py` and `setup_page.py`; the three independent reads go.
- **H9 Path budget.** Before a recorded run starts, the app computes the longest path the run will
  write; if it exceeds **240** characters the run does not start and the Start page says "The data
  folder path is too long — move the program folder closer to the drive root." (Worst case with a
  100-character root: ~206 for run files, ~222 for the PDF.)
- **H10 Discard / Delete.** Discard deletes the run folder only if it lies at
  `<root>/<subject>/runs/<task_id>/<name>`, matches the H2 name pattern and holds plain files only
  (today's guard, re-anchored). Delete Test keeps today's behaviour: the record moves to
  `tests/_deleted/`; the run data stays.
- **H11 Diagnostics and replay** move to `_system/diagnostics/` and `_system/replay/` (D2); log
  lines stay without a subject.
- **H12 ~~Migration script~~ Dropped 2026-10-08 (D5 revised).** `tools/migrate_layout_v2.py` and
  `tests/test_migrate_layout.py` were written and rehearsed (§8), then deleted before the commit;
  the old-layout folders are deleted by hand instead.
- **H13 Docs.** README, `docs/DATA_SCHEMA.md` (layout section), the recorder/session_files
  docstrings, the "sessions folder" UI texts and `build_exe.py` BUILD_INFO describe the new tree.
  A v2.0.0 release note: the old layout is neither read nor migrated.

## 4. Design

§3.3 is the design. UI changes (both need a wireframe first):
- Setup page: the folder-name choice for a new Subject ID (H6), read-only "Folder: …" for an
  existing one.
- Test List: "Open Subject Folder" button (H6).
- Start page: the H9 path-too-long blocker line.

Wireframe-gate details (user OK 2026-10-08, `docs/wireframes/setup.md`, `test-list.md`, `start-test.md`):
- **W1 Setup:** **Superseded 2026-10-08 (step 6): the radio pair and the "Folder:" line are gone; a muted hint "Use a study code, not the child's name." sits under Subject ID.** Original: the "Folder name: (•) Subject ID ( ) Anonymous code (S-000N)" radio pair sits
  directly under Subject ID, shown only while the typed id matches no `subject.json`; the code
  label shows the code that would be assigned. Tooltip on "Anonymous code": "The folder is named
  S-000N instead of the Subject ID, so Explorer and zip file names do not show it. The files inside
  still contain the Subject ID." Existing subject: one read-only muted line "Folder: S-0003
  (Anonymous code)" / "Folder: P9REAL (Subject ID)" in its place.
- **W2 Test List:** "Open Subject Folder" (outline) is the last button of the right-hand column;
  enabled whenever the subject folder exists, independent of the row selection; disabled for a
  subject with nothing saved yet. Delete dialog text: "Its recorded data in the subject folder is
  kept." Unreadable-file line names `sessions/<subject folder>/tests`.
- **W3 Start:** the H9 line is an error alert, separate from the blocker banner. It disables
  **Start only; Practice stays enabled** (practice writes nothing). Evaluated when the page opens.

## 5. Scope

**In:** H1-H11, H13; tests re-anchored to the new layout.
**Out:** any migration of old-layout data (D5 revised); BIDS export; de-identified export tool; per-subject diagnostics; migrating v1.0.0 exe
data; renaming run files; changing what a run folder contains; network/OneDrive detection.

## 6. Acceptance criteria

- **L1** A recorded run writes only under `<root>/<subject>/runs/<task_id>/<YYYY-MM-DD_HHMM>/`;
  two runs in the same minute get distinct folders.
- **L2** Test records link runs by `run_dir`; View Report, the data-missing check and Discard work
  through it; Discard refuses any folder outside the H10 pattern.
- **L3** Settings, calibrations and tests of a subject live under its folder; nothing is written
  to `_calibrations`, `_settings`, `_tests` or `_diagnostics` any more.
- **L4** "Ana" then "ANA" resolve to the same subject folder; the completer shows the verbatim id.
- **L5** (revised 2026-10-08, step 6) A new subject's folder is its Subject ID, and Setup shows the hint "Use a study code, not the child's name."; Open Subject Folder opens it. Original: Anonymous code: a new subject in code mode gets `S-000N` (next free, never reused); no
  file or folder name under the root contains the Subject ID; Open Subject Folder opens it.
- **L6** PDF default = `<subject>/reports/<date>_<test name>.pdf`, no subject in the name.
- **L7** A root deep enough to push a run path over 240 characters blocks Start with the H9 text.
- **L8** Diagnostics append to `_system/diagnostics/`; Practice/Preview still write nothing.
- **L9** ~~Migration dry run~~ Dropped with H12 (D5 revised 2026-10-08).
- **L10** Full pytest green; README / DATA_SCHEMA updated.

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | SPEC-input-selection-and-follow.md done (D6) | — |
| 1 | Wireframes: `setup` (folder-name choice), `test-list` (Open Subject Folder), `start-test` (path blocker) — **DONE 2026-10-08** | **WF gate** |
| 2 | Engine: `output_root()`, subject resolver + `subject.json`, `new_run_dir`, `run_dir` link, stores re-anchored, discard guard, diagnostics/replay paths, path budget | — |
| 3 | UI: Setup choice, Test List button, PDF default, Start blocker, texts | — |
| 4 | ~~Migration script~~ **Dropped 2026-10-08** (D5 revised); on the user's OK after step 5, delete the old-layout folders in `sessions/` (no backup) | user |
| 5 | Review + live check (new subject in both modes, one recorded run, report + PDF, Discard); commit on the user's OK — **DONE 2026-10-08** (live check passed, shared with design-system phase 1) | user |
| 6 | **Remove the Anonymous code option (D4 revised 2026-10-08).** **DONE 2026-10-08.** Setup: drop the "Folder name" radio pair and the read-only "Folder: …" line (W1); add the muted hint "Use a study code, not the child's name." under Subject ID. Engine: the subject folder is always the sanitised Subject ID; no new `S-000N` code is assigned and `sessions/_system/subject_codes.json` is no longer written; `subject.json` keeps `folder_mode` (always `"id"`) so the schema does not change; `folder_mode=` plumbing to `create_test` / Save Calibration goes. The Test List's Open Subject Folder (W2) stays. L5 is replaced by: a new subject's folder is its Subject ID, and Setup shows the hint. Existing tests for code mode are updated or removed with the feature, the rest stay. | — |

## 8. Impl log

- **2026-10-08 — plan steps 2, 3 and the script of step 4 (spec-implementer, model `claude-sonnet-5-5`;
  worktree fast-forwarded to `f980939`; nothing committed or staged).**
  *pytest:* `5 failed, 2669 passed, 2 skipped in 416.00s (0:06:55)`. The 5 failures are the pre-existing "smoothing-alpha 0.22" checks
  (`test_task_config_page` x4, `test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`):
  this worktree has the committed `configs/default.yaml` (alpha 0.35), the lab machine's skip-worktree
  file is the one that agrees; they fail identically on `f980939` before any change here. The lab-machine
  baseline failure `test_config_merges_task_over_default` passes in this worktree.
  *New engine modules:* `src/engine/subject_store.py` (`output_root(config=None)`, `SubjectFolder`,
  `find_subject` / `list_subjects` / `ensure_subject`, `known_subject_ids` (moved here from
  `settings_profile`), `id_folder_name`, `next_subject_code`, `replace_with_retry`),
  `src/engine/run_paths.py` (`new_run_dir`, `make_session_id`, `relative_run_dir` / `resolve_run_dir`,
  `longest_run_path` / `path_budget_error`). UI: `src/ui/subject_folder_row.py` (W1),
  `src/ui/folder_opener.py` (W2: `QDesktopServices.openUrl(QUrl.fromLocalFile(...))`, both verified with
  qt-docs). Tool: `tools/migrate_layout_v2.py`.
  *Changed:* `session_naming.py` (`safe_subject_dirname(id, max_len=80)`; `next_run_number` /
  `next_session_id` removed), `session_files.py` (H10 guard), `subject_test_record.py` / `subject_tests.py`
  (`run_dir`, schema 2, `record_result` check, `run_folder_of`, `folder_mode=`), `settings_profile.py`,
  `calibration.py` / `gaze_diagnostics.py` (`_system/diagnostics`), `task_runner.py` (replay to
  `_system/replay`), `data/recorder.py` (`SessionRecorder(metadata, output_root, session_dir=None)`),
  `app.py`, `main.py` (help text), `run_result.py` (wording), UI: `setup_page.py`, `test_list_page.py`
  (+ `test_list_table.py`: the row filling moved into `SubjectTestTable.populate` to stay under 500 lines),
  `start_test_page.py`, `run_flow.py`, `report_flow.py`, `report_format.py`, `report_page.py`,
  `dashboard_flow.py` (`output_root_from_config` removed), `dashboard_window.py`. Docs: `README.md`,
  `docs/DATA_SCHEMA.md`, `docs/CLINICAL_DATA_REFERENCE.md`, recorder / session_files docstrings,
  `analysis/analyze_session.py` usage line, `tools/pyinstaller/build_exe.py` BUILD_INFO.
  *Tests:* 5 new files (`test_subject_store.py`, `test_run_paths.py`, `test_migrate_layout.py`,
  `test_setup_folder_row.py`, `test_start_path_blocker.py`: 116 tests) plus `tests/recorder_helpers.py`;
  new cases in `test_recorder`, `test_subject_tests`, `test_test_list_page`, `test_run_modes_app`,
  `test_report_format`, `test_dashboard_e2e`; about 40 existing files re-anchored to the new layout
  (`recorder_in(tmp_path, meta)` for the tests of what the recorder writes; `new_run_dir` for run folders;
  `run_dir` for `session_dir`; `test_session_files.py`, `test_safe_subject_dirname.py` rewritten for H10 / H5;
  the `next_run_number` / `next_session_id` tests went with the functions, the local-state tests of
  `test_dashboard_helpers.py` stay).
  *Design choices inside the spec (none changes a decision):*
  (1) A subject's store paths are `Path | None`: `subject_tests_dir`, `subject_settings_dir`,
  `settings_profile_dir` / `settings_profile_path` return `None` for a subject with no folder yet, and the
  list / load functions read that as "nothing". Writes (`create_test`, `save_settings_profile`, Save
  Calibration, `new_run_dir`) call `ensure_subject`, which makes the folder and `subject.json`. The folder
  name choice reaches it as `folder_mode=` (Setup radio -> `DashboardWindow._reload_tests` ->
  `SubjectTestListPage.set_subject(..., folder_mode)` -> `create_test`; Save Calibration passes it
  itself); an existing subject keeps its own mode whatever is passed.
  (2) "Never reused" (H6): besides scanning for `S-NNNN` folders, `ensure_subject` records the highest code
  issued in `_system/subject_codes.json`, so deleting `S-0003` by hand does not free the number.
  (3) `find_subject` always scans the `subject.json` files (a first version that tried the ID-named folder
  first returned the *typed* case on NTFS, `ANA` for `Ana`; a test caught it and the shortcut is gone).
  `SubjectTestListPage` looks the subject up once per reload.
  (4) `AssessmentApp` makes the run folder lazily (`run_dir()` closure): at the first thing that needs it
  (an auto-saved `calibration.json`, else the recorder), so a run that fails to start (e.g. the tracker
  refuses) leaves nothing behind, as before. `session_id` is built from it (H3); a practice / preview
  keeps its sentinel.
  (5) `record_result` accepts only `<subject>/runs/<task_id>/<YYYY-MM-DD_HHMM[_N]>` of that subject (the
  same shape H10's guard demands); `resolve_run_dir` returns `None` for any other `run_dir` text (no
  `..`, no drive, no extra depth), so a hand-edited record cannot point outside the subject folder.
  (6) `reports/` is made when Print Report first asks for a path (opening a report writes nothing).
  The PDF name part is cut so that name + `~hash` fits in 50 characters (`PDF_NAME_MAX`), which keeps the
  H9 PDF worst case (~222 with a 100-character root) true.
  (7) H9 numbers: worst case = max(run file, PDF) with the run name `YYYY-MM-DD_HHMM_9` (17), the longest
  run file `session_metrics.json` (a test pins it against every file the app writes), the real folder name of
  an existing subject or the ID-mode name of a new one, `os.path.abspath` of the root. 100-character root:
  206 for run files, 222 for the PDF, as in the spec. The Start page gets `set_path_error()`; Start is off,
  Practice is not; `RunFlow.open` sets it when the page opens.
  (8) `subject.json` and test-record writes retry a `PermissionError` a few times (`replace_with_retry`,
  moved from `subject_tests`), the same rule the record writes always had.
  (9) The legacy flat `settings/<task>.json` reader and the pre-S8 `calibration.json` name stay (file-name
  formats inside the new tree, not a legacy layout); the migration moves them untouched.
  *Migration script (`tools/migrate_layout_v2.py <sessions> [--apply]`):* dry run by default; `--apply`
  writes `<sessions>_backup_<stamp>.zip` beside the folder, verifies it (`testzip`, entry count), then
  moves. Aborts before anything moves on: unreadable / unusable `metadata.json` of any run, an unreadable
  test record of a *kept* subject, a name clash, a tree that already has `subject.json` next to old parts.
  Also handled: `replay_*` folders to `_system/replay`, a report PDF left in a run folder to
  `reports/<date>_<name>.pdf` (subject prefix dropped), a Done test whose run folder is gone gets
  `run_dir: null` and a warning, a deleted subject that ran tests gets a warning, unknown top-level
  entries are left and listed, a second `--apply` says "Nothing to migrate".
  *L9, rehearsed twice on a copy of the real `sessions/` (copied to a temp dir outside both repos; the
  real folder was only read, 141 files before and after):* the dry run lists **9 runs, 3 subjects kept
  (P9REAL, P9TEST, tesst), 6 deleted (DIKI, DISP150, DPI100, DPI150, HUDTEST, TESTING)**; `--apply` gives
  `P9REAL/`, `P9TEST/`, `tesst/`, `_system/diagnostics/` (141 - 13 deleted + 3 `subject.json` = 131
  files). The app engine then opens it: 16 tests (4 + 5 + 7, none unreadable), all 9 Done / Ended-early
  tests resolve their run folder and `load_or_build_report` returns their report, the 4 saved
  configurations of `tesst` and the 1 of `P9TEST` are listed, the P9REAL PDF sits in
  `P9REAL/reports/2026-10-07_Follow & Click 1.pdf`. **L9 holds.** The real `sessions/` has not been
  migrated: step 4's `--apply` is for the user's OK.
  *Deviations:* none. *Not done:* step 5 (live check, user OK, commit); BIDS, de-identified export,
  per-subject diagnostics (out of scope); no GUI launch, no device, no live test. The README's pytest
  line was updated to the clean-checkout count.
- **2026-10-08 — plan step 6, remove the Anonymous code option (spec-implementer, model
  `claude-sonnet-5-5`; worktree `design-phase1` at `4360537`; nothing committed or staged).**
  *pytest (full, venv, `-o addopts=""`):* `5 failed, 2785 passed, 2 skipped in 486.18s (0:08:06)`. The 5
  are the known smoothing-alpha 0.22-vs-0.35 checks of the committed config
  (`test_config_flow::test_a_new_test_opens_at_standard_with_the_task_defaults`,
  `test_task_config_page::test_a_new_test_opens_with_standard_and_the_defaults[click_static|click_grid|follow_moving|scanning]`);
  nothing else fails.
  *Engine:* `subject_store.py`: `ensure_subject(root, subject_id)` always claims `id_folder_name(id)` and
  writes `{"subject_id", "folder_mode": "id", "created_at"}`; removed `FOLDER_MODE_CODE`, `FOLDER_MODES`,
  `MODE_LABELS`, `CODE_COUNTER_FILENAME`, `next_subject_code`, `preview_folder_name`, the `_system/subject_codes.json`
  reader/writer (`_highest_code`, `_store_code`, `_counter_path`, `_code_name`), `SubjectFolder.label()` and
  `SubjectFolder.mode` (its only users were `label()` and the code option; `FOLDER_MODE_ID` stays as the value
  written). The reader ignores `folder_mode`, so an old `S-0001` folder with `"folder_mode": "code"` is still
  found by its `subject_id`. `folder_mode=` plumbing removed from `run_paths.new_run_dir`,
  `settings_profile.save_settings_profile`, `subject_tests.create_test` / `_save`.
  *UI:* `setup_page.py`: the `SubjectFolderRow` and `SetupPage.folder_mode()` are gone; a new
  `subject_id_hint` (`QLabel`, `objectName` `wtmhMuted`, the existing muted caption style, no new colour or
  size) with exactly "Use a study code, not the child's name." sits in its own form row directly under the
  Subject ID field (`form.addRow("", hint)`, so it lines up with the field), always shown; Save Calibration calls
  `ensure_subject(root, subject_id)`. `test_list_page.py`: `set_subject(subject_id, output_root)` and
  `create_test(...)` lose `folder_mode`; `dashboard_window.py::_reload_tests` stops passing it. Deleted
  `src/ui/subject_folder_row.py` (the whole widget was the radio pair + "Folder: ..." line). Open Subject Folder
  (W2) untouched.
  *Docs:* `docs/wireframes/setup.md` (radio pair, tooltip and "Folder: ..." line replaced by the hint line and
  one note), `docs/wireframes/test-list.md` (`sessions/S-0003` example dropped), `README.md` and
  `docs/DATA_SCHEMA.md` (tree, `folder_mode` is always `"id"`, `subject_codes.json` gone, study-code advice).
  The rendered `docs/wireframes/setup.html` still shows the old radio pair: not re-rendered, as instructed.
  *Tests (L5 replaced):* new `tests/test_setup_subject_id.py` replaces `tests/test_setup_folder_row.py`
  (deleted; most cases in it were about the radio pair / "Folder: ..." line or code mode; the ones that were not
  (Save Calibration makes `<id>/calibrations/...`, saving twice keeps one folder, the saved file is found by the
  typed ID, a failed save says so, the completer lists IDs verbatim) are carried over): 8 tests: hint text, style
  and place (the row right under the Subject ID field), hint always visible, no radio buttons / "Folder: ..."
  label / `folder_row` / `folder_mode` left, and a new subject's folder is its Subject ID with no `S-000N` and no
  `subject_codes.json`. `test_subject_store.py`: the "Anonymous code" section (8 tests, incl. the
  `preview_folder_name` one) and the mode-kept / unknown-mode tests replaced by 6 tests (blank ID refused; a new subject's folder is the ID and
  no code; first save of anything never makes a code folder, `subject_codes.json` neither read nor written; an
  old `S-0001` code folder is still found by its ID; an ID that looks like a code name gets that name);
  `test_subject_tests.py`, `test_test_list_page.py`, `test_run_paths.py`: the code-mode tests turned into
  "folder is the Subject ID" ones (Open Subject Folder still resolves the folder by the typed ID in any case).
  *Deviations:* none. *Left for the hub:* the SPEC's own §6 L5, §3.3 H6 and §4 W1 text still describe the
  Anonymous code (left untouched: decisions are the hub's); `docs/wireframes/setup.html` re-render; the old
  `sessions/S-0001` + `_system/subject_codes.json` from the live check are on disk and untouched (the app no
  longer reads the counter; the folder is still found by its `subject_id`). No GUI launch, no live test.

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-07** — Created from the user's request (cluttered `sessions/`). Four read-only agents
  (impact map, design A, design B, conventions research). The user chose layout A, machine-wide
  diagnostics, an Anonymous code option, deletion of the old no-run subjects incl. TESTING, no
  migration of v1.0.0 exe data, and building after the input-selection SPEC (D1-D6). Hub decisions
  H1-H13 proposed, awaiting approval.
- **2026-10-07** — The user approved H1-H13 as written. SPEC committed on `feature/compass-task-flow`. Next: after the input-selection SPEC, /spec-run this SPEC from step 1 (wireframes).
- **2026-10-08** — Step 1: wireframes `setup`, `test-list`, `start-test` updated (folder-name choice, Open Subject Folder, path blocker). The user approved them as drawn, incl. two hub choices: Practice stays enabled under the path blocker, and Open Subject Folder sits in the button column outside the row matrix (§4 W1-W3). Next: steps 2-3 with the spec-implementer.
- **2026-10-08** — Steps 2-4 implemented by the spec-implementer (§8), no §9 questions, no deviations. Hub review: scope matches H1-H13 and W1-W3, no legacy-layout reader left; L1-L8 and L10 covered by tests, L9 rehearsed on a copy only. Hub pytest in the worktree: 2669 passed, 5 failed, 2 skipped (2676); the 5 are the smoothing-alpha 0.22 checks, which fail because the worktree carries the committed `configs/default.yaml` (alpha 0.35) instead of the user's skip-worktree copy (0.22); not caused by this change. (`pyproject` addopts `-q` plus a second `-q` hides the count line: count from the progress output.) The user was not ready to be the subject; parked before step 4 `--apply` and the step 5 live check. Nothing committed.
- **2026-10-08** — **User: no migration** (all `sessions/` data is test data). D5 revised, H12 / L9 / step 4 dropped: `tools/migrate_layout_v2.py` and `tests/test_migrate_layout.py` deleted, README and DATA_SCHEMA no longer mention a migration. The old-layout folders are deleted without a backup when this SPEC lands. Ordering (user): steps 2-3 committed on the worktree branch (not merged, not pushed); design-system phase 1 is built on top of that commit, and the step 5 live check covers both.
- **2026-10-08** - Step 5 live check, shared with design-system phase 1, the user as subject on the real GP3 HD, app launched from worktree design-phase1 (phase 1 stacked on `1d38819`). Subject LIVECHK1 (Subject ID mode): `sessions/LIVECHK1/{subject.json, calibrations/calibration_5pt.json, settings/click_grid/, tests/, runs/click_grid/2026-10-08_1552/, reports/}`; the run folder holds all 11 files; `subject.json` folder_mode "id"; test record schema 2. One recorded Grid Click run (6 trials), report + PDF opened. Discard after a mid-run stop left no run folder. Subject TSET in Anonymous code mode got folder `S-0001` (`_system/subject_codes.json` written). Diagnostics stayed in `_system/diagnostics/`. **User decision after the check: remove the Anonymous code option** (a folder named S-0001 while every page shows the Subject ID would confuse clinicians); D4 revised, step 6 added. Not checked live: a path-budget blocker, Open Subject Folder.
- **2026-10-08** - Step 6 (D4 revised) implemented by the spec-implementer (§8): radio pair, "Folder:" line, `S-000N` codes and `subject_codes.json` removed; muted hint "Use a study code, not the child's name." under Subject ID; `subject.json` keeps `folder_mode` "id". Hub review: scope matches step 6, no code-mode reference left in `src/`; H6, W1 and L5 marked superseded; `docs/wireframes/setup.html` re-rendered. Hub pytest in the worktree: 2785 passed, 5 failed (known skip-worktree alpha checks), 2 skipped (12 code-mode tests removed or folded). Not seen live in the app (wireframe only). Committed on design-phase1 and merged into feature/compass-task-flow on the user's OK.
