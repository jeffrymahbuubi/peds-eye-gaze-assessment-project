---
name: SPEC-subject-data-layout
title: Per-subject data folders — one folder per child holding calibrations, settings, tests, runs and reports
status: approved 2026-10-07 (D1-D6, H1-H13)
created: 2026-10-07
last_updated: 2026-10-08
next_step: READY (SPEC-input-selection-and-follow.md steps 1-4 landed `4cbbce0` 2026-10-08; only its device-bound live check A10 is open and does not touch these files): /spec-run this SPEC from step 1 (wireframes: Setup folder-name choice, Test List "Open Subject Folder", Start path blocker)
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
| D4 | An **"Anonymous code" folder option**: a subject's folder can be named `S-0001` instead of the Subject ID, so Explorer and zips never show the name. |
| D5 | **Migration:** a one-time script moves today's runs (P9REAL, P9TEST, tesst) and their records/settings/calibrations; every old subject with no run (DIKI, DISP150, DPI100, DPI150, HUDTEST, **TESTING incl. its 2 Not Done tests**) is deleted. No legacy-layout reading code stays in the app. Data written by the v1.0.0 exe (`compiled/PedsEyeGaze-1.0.0/sessions/`, other PCs) is **ignored**: not migrated. |
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
- **H6 Anonymous code (D4).** On Setup, when the typed Subject ID is **new** (no matching
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
- **H12 Migration script** `tools/migrate_layout_v2.py <sessions>`: dry run by default (prints
  every move and delete), `--apply` to execute; first writes a zip backup of `sessions/` beside it.
  Per D5: the 9 runs move to `<S>/runs/<task>/<date_HHMM>` (time from `metadata.started_ns`,
  `_2` on collisions); records rewritten `session_dir` to `run_dir` + schema bump; settings and
  calibrations moved; the P9REAL PDF moved to `reports/` without the subject prefix; `subject.json`
  written (mode `id`); `_diagnostics` to `_system/diagnostics`; the old subjects with no run
  deleted. Run files are not rewritten (migrated runs keep their old `session_id` string, display
  only). Any unreadable metadata aborts before anything moves. The script is committed, run once
  on the user's OK, and removed in the next commit (git history keeps it).
- **H13 Docs.** README, `docs/DATA_SCHEMA.md` (layout section), the recorder/session_files
  docstrings, the "sessions folder" UI texts and `build_exe.py` BUILD_INFO describe the new tree.
  A v2.0.0 release note: do not point a v1.0.0 exe at a migrated folder.

## 4. Design

§3.3 is the design. UI changes (both need a wireframe first):
- Setup page: the folder-name choice for a new Subject ID (H6), read-only "Folder: …" for an
  existing one.
- Test List: "Open Subject Folder" button (H6).
- Start page: the H9 path-too-long blocker line.

## 5. Scope

**In:** H1-H13; tests re-anchored to the new layout; the one-time migration of today's data.
**Out:** BIDS export; de-identified export tool; per-subject diagnostics; migrating v1.0.0 exe
data; renaming run files; changing what a run folder contains; network/OneDrive detection.

## 6. Acceptance criteria

- **L1** A recorded run writes only under `<root>/<subject>/runs/<task_id>/<YYYY-MM-DD_HHMM>/`;
  two runs in the same minute get distinct folders.
- **L2** Test records link runs by `run_dir`; View Report, the data-missing check and Discard work
  through it; Discard refuses any folder outside the H10 pattern.
- **L3** Settings, calibrations and tests of a subject live under its folder; nothing is written
  to `_calibrations`, `_settings`, `_tests` or `_diagnostics` any more.
- **L4** "Ana" then "ANA" resolve to the same subject folder; the completer shows the verbatim id.
- **L5** Anonymous code: a new subject in code mode gets `S-000N` (next free, never reused); no
  file or folder name under the root contains the Subject ID; Open Subject Folder opens it.
- **L6** PDF default = `<subject>/reports/<date>_<test name>.pdf`, no subject in the name.
- **L7** A root deep enough to push a run path over 240 characters blocks Start with the H9 text.
- **L8** Diagnostics append to `_system/diagnostics/`; Practice/Preview still write nothing.
- **L9** Migration dry run on a copy of today's `sessions/` lists exactly the 9 runs, 3 subjects
  kept, 6 subjects deleted; `--apply` on the copy gives a tree that the app opens with every
  P9REAL/P9TEST/tesst test and report intact.
- **L10** Full pytest green; README / DATA_SCHEMA updated.

## 7. Plan

| Step | Content | Gate |
|---|---|---|
| 0 | SPEC-input-selection-and-follow.md done (D6) | — |
| 1 | Wireframes: `setup` (folder-name choice), `test-list` (Open Subject Folder), `start-test` (path blocker) | **WF gate** |
| 2 | Engine: `output_root()`, subject resolver + `subject.json`, `new_run_dir`, `run_dir` link, stores re-anchored, discard guard, diagnostics/replay paths, path budget | — |
| 3 | UI: Setup choice, Test List button, PDF default, Start blocker, texts | — |
| 4 | Migration script (dry run on a copy, then `--apply` on the real `sessions/` only on the user's OK) | user |
| 5 | Review + live check (new subject in both modes, one recorded run, report + PDF, Discard); commit on the user's OK | user |

## 8. Impl log

(empty)

## 9. Implementer open questions

(empty)

## 10. Log

- **2026-10-07** — Created from the user's request (cluttered `sessions/`). Four read-only agents
  (impact map, design A, design B, conventions research). The user chose layout A, machine-wide
  diagnostics, an Anonymous code option, deletion of the old no-run subjects incl. TESTING, no
  migration of v1.0.0 exe data, and building after the input-selection SPEC (D1-D6). Hub decisions
  H1-H13 proposed, awaiting approval.
- **2026-10-07** — The user approved H1-H13 as written. SPEC committed on `feature/compass-task-flow`. Next: after the input-selection SPEC, /spec-run this SPEC from step 1 (wireframes).
