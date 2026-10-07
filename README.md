# Pediatric Eye-Gaze Assessment Tool (v1.0.0)

兒童眼控電腦操作能力評估工具 — prototype.

A Windows-oriented tool for assessing children's eye-control computer operation
ability, designed to reduce the Compass floor effect for young beginners. It
supports **gaze dwell selection** (Gazepoint GP3HD) and **switch input**
(keyboard now, USB-HID/GPIO later), rich audiovisual feedback, and structured
data export for reliability/validity analysis.

See `../303bfbea-eye_gaze_assessment_v1_plan.md` for the full design plan.

## Highlights of this prototype

- **Runs with no eye tracker.** A deterministic *replay mode* reads a gaze
  fixture (`.jsonl`) so ~80% of development and all tests run headless.
- **Four tasks** implemented: `click_static`, `click_grid`, `follow_moving`,
  `scanning` (plan §5.5).
- **GUI-free core.** Inputs, dwell logic, task state machine, and data recording
  have no Qt dependency and are unit-tested. Only `src/ui/` and `src/app.py`
  import PySide6.
- **Therapist-editable YAML config** for target size, trial count, timeout,
  dwell threshold, theme (plan US-02).
- **Structured output** per session: `metadata.json`, `trials.csv`,
  `gaze_stream.csv`, `events.jsonl` (plan §5.7).
- **Pointer and Selection per test** (`docs/specs/SPEC-input-selection-and-follow.md`):
  the pointer is the child's **Gaze** or the **Mouse**; a target is selected by **Dwell** or
  by a **Switch**. The switch is a left mouse press on the canvas (the USB switch the lab uses
  sends exactly that) or Space / Enter, counted on button down and judged where the gaze is
  (a Click error off the target; a blink uses the last valid gaze within 150 ms; presses
  between trials are ignored; a press within the refractory period of the last counted one is
  debounced). With gaze and a switch the OS cursor is parked on the canvas and
  hidden. A Mouse test needs no tracker or calibration (Setup's Continue to Tests is allowed
  without them; gaze tests are held back on their own Start page). It writes `pointer_stream.csv`, and
  records gaze alongside when the tracker is connected and calibrated (`gaze_recorded` in
  `metadata.json` says which). `trials.csv` gains `clicks` and `click_errors`.
- **Follow the Target** (task id `follow_moving`, formerly Follow & Click): nothing is
  selected. Every trial lasts exactly the **Trial duration** (default 10 s, 3 to 30 s) and
  the child just keeps looking at the moving target; it glows while the pointer is on it.
  A trial is **followed** when the pointer was on the target at least 50 % of its valid time
  (`is_hit` in `trials.csv`; the hit sound plays only then, never a miss sound). Time on
  target, mean distance and valid time are counted live from the smoothed pointer
  (`trials.csv`: `valid_ms`, `on_target_ms`, `time_on_target_pct`, `mean_dist_px`). The
  report's `follow` block (`src/data/report_follow.py`) adds the smooth-pursuit gain and the
  catch-up saccades per second from the device-rate gaze; a Mouse run with no tracker has
  the first set only. An older Follow & Click folder still opens, with its old report layout.
- **The per-test report follows the test's input** (page and PDF): a Switch test adds **Clicks**
  and **Click errors** columns to the Summary of Results and the trial table; Follow the Target
  has a Metric / Value summary and its own trial columns, and its selected-trial map draws the
  pointer path dark on the target and light off it; a test with no gaze recorded says "not
  recorded" in its eye cells. The Configuration table's Input row reads like "Gaze (GP3HD,
  150 Hz) · Switch" or "Mouse · Dwell 0.8 s".

## Architecture

```
Presentation (PySide6)         src/ui/, src/app.py         [gui extra only]
        │
Task Engine ── Input Manager   src/tasks/, src/engine/, src/inputs/
        │
Data Recorder ── Storage       src/data/  → sessions/<id>/
```

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the data
contract in [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md).

## Install

Requires **Python >= 3.11** (see `pyproject.toml`); developed and tested on
**3.12** (pinned in `.python-version`).

```bash
# core (headless pipeline + tests) — no Qt needed
pip install -e ".[dev]"

# full GUI (Windows target)
pip install -e ".[gui,dev]"
```

### With `uv` (recommended — matches the dev environment exactly)

```bash
# uv reads .python-version automatically, so this creates a 3.12 venv
uv venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# core (headless pipeline + tests)
uv pip install -e ".[dev]"

# full GUI (Windows target)
uv pip install -e ".[gui,dev]"
```

If a specific machine doesn't have Python 3.12 installed, `uv venv --python 3.12`
will fetch and use it automatically without touching the system Python.

## Run the headless replay demo (no hardware)

```bash
# regenerate a fixture (optional — one per task is committed already)
python tools/make_replay_fixture.py --task click_static     # -> tests/fixtures/gaze_replay_click_static.jsonl
python tools/make_replay_fixture.py --task click_grid        # -> tests/fixtures/gaze_replay_click_grid.jsonl
python tools/make_replay_fixture.py --task scanning           # -> tests/fixtures/gaze_replay_scanning.jsonl
python tools/make_replay_fixture.py --task follow_moving      # -> tests/fixtures/gaze_replay_follow_moving.jsonl

# run a full "calibrate → task → export" loop against the fixture
python -m src.main --task click_static --replay tests/fixtures/gaze_replay_click_static.jsonl

# → sessions/replay_click_static_REPLAY/{trials.csv, gaze_stream.csv, ...}
```

Any of the four tasks works: `--task click_grid|follow_moving|scanning` — use
that task's own fixture (`gaze_replay_<task>.jsonl`) so the simulated gaze
actually lines up with that task's target layout. All four are generated
from the real task classes' own layout, not a hand-duplicated copy, so they
can never drift out of sync with `configs/tasks/*.yaml`.

**If a replay run shows nothing but timeouts, no hits at all:** check
`input.mode` in `configs/default.yaml` is `eye`, not `switch`. `switch` mode
requires an explicit mouse/keyboard click to register a hit — dwell-based
selection never runs at all, so a `--replay` fixture (which never sends a
click) can never hit regardless of how well it's built. `eye` is the
committed default; if your local copy differs, it's a `skip-worktree`d local
edit left over from switch-mode testing (see the section below), not
something wrong with the fixture or the replay pipeline.

## Run the GUI (needs the `gui` extra)

```bash
# with a paced replay (simulated tracker)
python -m src.main --task click_static --gui --replay tests/fixtures/gaze_replay_click_static.jsonl

# with a real Gazepoint GP3HD (Gazepoint Control running on 127.0.0.1:4242)
python -m src.main --task click_static --gui
```

A **task settings dialog** appears first, letting you adjust that task's
structural layout (grid size, target radius, icon count, trial count, ...)
before it starts — "Start task" with nothing changed reproduces the task's
YAML defaults exactly. Pass `--skip-task-settings` to skip straight to the
task (useful for scripted/automated launches).

The run screen is the task canvas with one thin **run bar** under it: a status
line (trial number, tracker state) and **Pause** (Alt-P), **Skip trial** and
**Quit** (Alt-Q; Esc does the same, and asks first). There is no operator side
panel and nothing changes mid-task: every setting is fixed before the run
starts (the dialog above) and recorded in the session's `metadata.json`
(`settings`, see `docs/DATA_SCHEMA.md`).

## Run the Setup/Task-selection dashboard (needs the `gui` extra)

```bash
python -m src.main --dashboard
```

A persistent window (SPEC-ui-setup-task-selection.md, and the Compass-style
test flow of SPEC-compass-task-flow.md) instead of one task per process, with
two tabs, **1 · Setup** and **2 · Tests**. Everything runs inside this one
window (no new window, no subprocess); the tracker connection and calibration
are reused across every test in the session.

1. **Setup.** Enter the Subject ID, connect to the tracker and calibrate once;
   **Continue to Tests** opens the Tests tab.
2. **Tests.** Each subject has their own Test List, saved on disk
   (`sessions/_tests/<subject>/`), so it is still there after a restart and
   whenever the same Subject ID is typed again. **Add New Test** (a task, 1-10
   copies), **Configure Test**, **Run Test**, **View Report**, **Copy Test**
   (an unrun copy with a new random target order) and **Delete Test**. A test
   is *Not Done*, *Done* with its date, or *Ended early*; once it has run it is
   locked.
3. **Configure.** A full page for the test's settings (task layout, target
   size, dwell, pacing, feedback). Settings are saved as named configurations
   (*Standard* is the task's own defaults, or any name you save, kept per
   subject and task). **Preview Test** plays a few trials driven by the mouse
   and records nothing; **Save & Continue** returns to the list.
4. **Start / Practice.** **Run Test** opens the Start page: the instructions to
   read aloud, the tracker state, and the reason if Start is disabled.
   **Practice** is a short throwaway round (up to 3 trials, nothing written,
   repeatable); **Start** runs and records the test.
5. **Run.** The canvas with the run bar's **Pause**, **Skip trial** and
   **Quit**. Quitting a recorded run asks first.
6. **Test Complete.** **Save**, **Save and View Report**, or **Discard
   Results** (deletes the run). A run ended early offers **Save partial
   results** or **Discard results**.
7. **Report.** Summary and Detailed views (summary of results, target map with
   a symbol legend, fixation scanpath and heat map, eye metrics, trial-by-trial
   table whose selected trial shows the gaze path smoothed like the on-screen
   cursor). Times read in seconds. **Print Report** writes an A4 portrait PDF, by
   default into the run's own folder. The Test Name, Evaluator and Notes are
   edited here.

Each recorded run is its own `<date>_<subject>_<task>_run<N>` folder under
`sessions/`, so a repeat of the same task by the same subject on the same day is
never overwritten; a discarded run leaves no folder. This is an additional
entry point alongside `--task ... --gui` above, not a replacement — the two
don't interact.

The Control Address field remembers the last host that connected
successfully on this machine (`configs/local_state.json`, gitignored — a
fresh machine defaults to `127.0.0.1`).

## Testing `--calibration-file` without a device

`--calibration-file PATH` skips a fresh calibration and reuses a previously
saved `calibration.json` (auto-written to `<session_dir>/calibration.json`
whenever a real calibration actually runs — see SPEC-2026-09-02.md item 7).
There are two things to test here, and only one needs a stand-in for the
device:

**Reusing a file (no device or fake server needed at all)** — `--replay`
never opens a socket, so a hand-written calibration file works directly:

```bash
python -m src.main --task click_static --gui \
  --replay tests/fixtures/gaze_replay_click_static.jsonl \
  --subject DEMO01 \
  --calibration-file path/to/calibration.json
```

`calibration.json`'s `subject_id` must match `--subject` exactly, or the app
hard-errors before opening any window. A minimal valid file:

```json
{"subject_id": "DEMO01", "n_points": 5, "mean_error_px": 8.0, "valid": true, "calibrated_at": "2026-01-01T00:00:00+00:00"}
```

**Auto-save from a real calibration** only happens when a live socket
actually completes a calibration handshake — `--replay` can never trigger
it. `tools/fake_gazepoint_server.py` stands in for Gazepoint Control just
well enough to exercise this:

```bash
# terminal 1
python tools/fake_gazepoint_server.py

# terminal 2 — temporarily point gazepoint.host at 127.0.0.1 first (see the
# skip-worktree section below), then run WITHOUT --replay:
python -m src.main --task click_static --gui --subject DEMO01
# → sessions/<date>_DEMO01_click_static/calibration.json should now exist

# reuse it on a later launch:
python -m src.main --task click_static --gui --subject DEMO01 \
  --calibration-file sessions/<date>_DEMO01_click_static/calibration.json
```

Point `gazepoint.host` back at the real device's address when done. The fake
server sends no gaze (`REC`) data, so the cursor stays "no gaze" — it's only
useful for the connect/calibrate handshake, not for a moving gaze signal
(use `--replay` with a `tools/make_replay_fixture.py` fixture for that).

## Editing a config file locally without it showing up in `git status`

During experimentation you'll often want to hand-edit a tracked config file
(`configs/default.yaml`, a task file under `configs/tasks/`, a theme, ...) to
try different settings, without every tweak becoming a pending change to
commit or accidentally get pushed. Git's `skip-worktree` flag does this: the
file stays fully tracked (so a fresh clone still gets it with real content),
but local edits are hidden from `git status`/`git diff`/`git add -A` until
you explicitly turn tracking back on.

```bash
# Start freely editing a file locally — its future edits won't show up in git status
git update-index --skip-worktree configs/default.yaml

# Confirm which files currently have it set (look for a leading "S")
git ls-files -v | grep '^S'

# When you DO want a change in this file to actually ship, turn tracking back
# on first, otherwise `git add`/`git commit` will silently ignore your edits
git update-index --no-skip-worktree configs/default.yaml
```

Works the same way for any other tracked config (`configs/tasks/click_static.yaml`,
`configs/themes/forest.yaml`, etc.) — just substitute the path.

**Caveats:**
- This is a **local, per-clone git setting** — it is not committed or shared.
  Set it again on any other machine (e.g. the other laptop) where you want
  the same free-editing behavior.
- It's easy to forget it's on. If you make a config change you *do* want to
  ship and `git status` doesn't show it, check `git ls-files -v | grep '^S'`
  first — the file is probably still marked skip-worktree.
- `configs/default.yaml` currently has this set (as of 2026-09-03), reverted
  to its last committed value (`calibration.enabled: true`) beforehand.

## Adjusting target speed and pacing between trials

A physician testing the tool asked whether the moving target can go slower,
and whether there can be more of a pause between targets. Both are already
configurable per task in `configs/tasks/*.yaml` — this just spells out where.

**How fast the `follow_moving` target moves**, in `follow_moving.yaml`:

```yaml
motion:
  speed_frac_per_s: 0.20   # fraction of screen width the target crosses per second
```

(There is no selection window any more: Follow the Target has nothing to select. A
`select_window_ms` key left in an old config file is ignored.)

Lower `speed_frac_per_s` (e.g. `0.10`) for a slower-moving target. This only
applies to `follow_moving` — the other three tasks show a stationary target
per trial, so there's no "movement speed" to tune for them.

**The pause between one target and the next**, in every task's YAML:

```yaml
inter_trial_interval_ms: 800   # click_static/click_grid: 800, scanning: 900, follow_moving: 1000
```

Raise this (e.g. to `1500`) for a longer breather between targets. There's no
separate "appear" animation — the next target simply pops in the instant this
interval elapses, so this pause is the only adjustable gap between targets.

**How long a trial waits before giving up** is a separate, also per-task
setting that may be worth checking at the same time:

```yaml
timeout_ms: 8000   # click_static default; varies per task (see each task's YAML)
```

For `follow_moving` the same `timeout_ms` is the **Trial duration**: how long every trial
lasts (10000 by default), not a limit.

Edit `configs/tasks/<task>.yaml` (or use the `git update-index --skip-worktree`
trick above to try values without them showing up as a pending change), then
re-run the task to feel the new pacing. Full diagnosis behind these settings:
`docs/specs/SPEC-2026-09-02.md`, item 5.

## Tests & lint

```bash
pytest        # 2545 passed, 2 skipped, all headless (offscreen Qt, no device) on the lab machine
              # (2540 passed in a clean checkout); the few tests that read the lab's own
              # skip-worktree configs/default.yaml (e.g.
              # test_config_merges_task_over_default, the smoothing-alpha 0.22 checks in
              # test_task_config_page / test_config_flow) only agree on the machine whose file
              # matches, see docs/specs
ruff check .
```

## Building the Windows executable

A one-folder, windowed PyInstaller build (`tools/pyinstaller/`), published to
`compiled/PedsEyeGaze-<version>/` plus a `.zip` next to it:

```bash
uv pip install --python .venv/Scripts/python.exe "pyinstaller>=6.10"   # once
python tools/pyinstaller/build_exe.py                                   # ~2 min, ~140 MB
```

What you get: `PedsEyeGaze.exe` (double-click → the dashboard; the `--gui`
and `--replay` modes still work as command-line flags), `configs/` next to
the exe (therapist-editable, the frozen app reads it from there — not from
`_internal/`), `sessions/` and `logs/` created beside the exe on first run
(a windowed exe has no console, so stdout/stderr and Qt messages go to
`logs/app-<timestamp>.log`), and `BUILD_INFO.txt` with the version, git
commit and dirty flag. Set `viewing_distance_mm` / `screen_physical_*_mm`
in the shipped `configs/default.yaml` per clinic PC if degrees-of-visual-angle
matter.

`tools/pyinstaller/auto-py-to-exe.json` is the same configuration for
`auto-py-to-exe` (Settings → Configuration → Import, launched from the repo
root); it cannot run the post-build copy of `configs/`, so do that by hand.
`compiled/` and `build/` are gitignored — the release tag (`v1.0.0`) is the
record of what was built.

## Analysis

`analysis/analyze_session.py` reads a session's `trials.csv`/`gaze_stream.csv`
and prints an RT summary + writes a gaze heatmap (see `docs/DATA_SCHEMA.md`).

## Development phases

Tracked in the plan (§6). This prototype covers Phase 0–3 core + the Phase 2
demo milestone ("calibrate → task → export") in headless form, plus the GUI
scaffold for Phase 3.
