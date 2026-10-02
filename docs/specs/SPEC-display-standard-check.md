---
name: SPEC-display-standard-check
title: Setup-page display check — recommend 1920×1080 at 100 % scale
status: design approved (§2), wireframe done (§7 step 1), not implemented
created: 2026-10-02
last_updated: 2026-10-02
next_step: user glances at docs/wireframes/setup.html (Display card), then the hub delegates §4–§6 to the spec-implementer subagent (§7 step 3)
related:
  - SPEC-display-scaling-cursor-accuracy.md (cursor fix 5199a05; found the 150 % Tasks-page clipping)
  - SPEC-gazepoint-analysis-export-parity.md (§10.3's device_pixel_ratio item is absorbed by §4.5 here)
  - SPEC-ui-setup-task-selection.md (Setup page, §22 scroll area, §24 USB2/60 Hz warning pattern)
---

# SPEC-display-standard-check — Setup-page display check (1920×1080 at 100 %)

**Status: design approved by the user (§2); wireframe done (`docs/wireframes/setup.md`, 2026-10-02); not implemented.** A new
"Display" card on the Setup page tells the operator (doctor/researcher)
whether the screen is the recommended **1920×1080 at 100 % Windows scale**.
If not, it warns, explains how to change it, and requires a tick-box
acknowledgement before Continue to Tasks enables. Every session records the
display it ran on.

**Created:** 2026-10-02
**Last updated:** 2026-10-02

## 1. Origin / what was asked

User, 2026-10-02, right after the cursor fix (`5199a05`) was live-validated:

1. Although the cursor is now correct at any scale, **1920×1080 at 100 %
   is the recommended display**. The Setup page should warn the user/doctor
   and recommend changing resolution and scale to that, because the GUI
   does not render properly at 150 %: the Tasks-page cards are squeezed
   (seen live, `SPEC-display-scaling-cursor-accuracy.md` §8.6, finding 1).
2. Purpose: rule out display resolution and scale as a factor during data
   collection, so data is **standardized across sessions**.
3. A responsive ("flex", web-style) layout for other screen sizes may come
   in a **later version — not this one**.

## 2. Decisions (chosen by the user 2026-10-02; do not re-open)

- **D1 — Warn + acknowledge.** When the display is non-standard, an amber
  warning shows, plus an unticked checkbox. Continue to Tasks stays disabled
  until it is ticked. Rejected: warn-only (too easy to ignore) and
  hard block (no way to run on a laptop that cannot do 1920×1080).
- **D2 — New "Display" card**, between *Tracker Connection* and
  *Calibration*, so the display is fixed before calibrating. It shows a green
  OK line when standard and the warning when not.
- **D3 — Record it.** Every session's `metadata.json` and session log store
  the physical resolution, the scale, a standard flag, and whether the
  operator acknowledged a non-standard display. This absorbs
  `SPEC-gazepoint-analysis-export-parity.md` §10.3's `device_pixel_ratio`
  item.

Hub-chosen details (mechanical, no user decision needed; the user may
override at wireframe review): the wording in §4.3, the re-check triggers
in §4.4, and the field names in §4.5.

## 3. Current code (as of `55d4c0d`)

- `src/ui/setup_page.py` (963 lines) builds four cards inside the
  `wtmhSetupScroll` scroll area (`_build_ui`, line ~295): subject, tracker,
  calibration, "Before You Start" (`_build_device_notice_card`). Continue to
  Tasks is a pinned footer button outside the scroll area.
- Warning pattern to copy: the USB2/60 Hz box in the tracker card,
  `rate_warning_alert` (`QFrame` `objectName="wtmhAlertWarning"` + a
  word-wrapped `QLabel`, hidden when not needed), with its text built by a
  pure module-level function `_format_rate_warning()`. Info boxes use
  `wtmhAlertInfo`. Check `wtmh_theme.py` for a success/OK style before
  inventing one.
- Gate: `SetupPage.can_continue()` (line ~283): connected + calibrated +
  subject ID + date + sex. `DashboardWindow` (`dashboard_window.py:189`)
  uses it for both the Continue button and the Tasks nav button, so one
  change covers both routes.
- Session start: `DashboardWindow` builds `AssessmentApp(...)` at
  `dashboard_window.py:394` and passes Setup values (`sex`, `notes`,
  `preset_calibration_result`, ...). `AssessmentApp._record_geometry()`
  (`src/app.py`) fills the geometry fields of `SessionMetadata` and writes
  the `Geometry:` session-log line once, on the first `_tick`.
- `SessionMetadata` (`src/data/schema.py:163`): geometry fields were added
  additively without bumping `schema_version`. Do the same here.
- No tests exist for `SetupPage` today.

## 4. Design

### 4.1 Detection (pure helper, no Qt)

New module `src/engine/display_check.py`:

```python
STANDARD_WIDTH_PX = 1920
STANDARD_HEIGHT_PX = 1080
STANDARD_SCALE_PERCENT = 100

@dataclass(frozen=True)
class DisplayCheck:
    width_px: int        # physical pixels
    height_px: int
    scale_percent: int   # round(devicePixelRatio * 100)
    standard: bool

def check_display(logical_w: float, logical_h: float, dpr: float) -> DisplayCheck
```

- Physical size = `round(logical × dpr)`; scale = `round(dpr × 100)`.
- `standard` = exactly 1920×1080 **and** 100 %. Both are required.
- The Qt caller passes the `QScreen` hosting the dashboard window:
  `self.window().screen()`, its `geometry()` and `devicePixelRatio()`.
  This is the same screen source the cursor fix uses (D1 there).
- `QT_SCALE_FACTOR` raises `devicePixelRatio()`, so it shows up as a
  non-100 % scale. That is intended, and it is how §7 validates this.
- Keep the constants in the module, not in `configs/default.yaml` (that
  file is skip-worktree and must not be edited or staged).

### 4.2 The Display card (D2)

Inserted in `_build_ui` between `_build_tracker_card()` and
`_build_calibration_card()`. Title: **Display**. Contents:

- **Standard:** one green/success line, e.g. "1920×1080 at 100 % scale —
  recommended standard." No checkbox.
- **Non-standard:** a `wtmhAlertWarning` box with the text in §4.3, and
  below it a checkbox (unticked by default) labelled
  *"Continue with this display anyway (recorded with the session)"*.

The card is always visible. It does not depend on the tracker being
connected.

### 4.3 Warning text (non-standard)

> This display is **{W}×{H} at {S} % scale**. The recommended standard for
> data collection is **1920×1080 at 100 %**. Other settings can make the
> task screens lay out incorrectly (for example squeezed task cards at
> 150 %), and sessions recorded on different displays are not directly
> comparable.
>
> To change it: Windows **Settings → System → Display**, set *Display
> resolution* to 1920×1080 and *Scale* to 100 %. This card updates
> automatically.

Build it in a pure function next to `_format_rate_warning()`, e.g.
`_format_display_warning(check: DisplayCheck) -> str` (empty string when
standard), so it is unit-testable.

### 4.4 Re-checking and the gate (D1)

- Re-run the check (and refresh the card) on: the Setup page's `showEvent`;
  the window's `QWindow.screenChanged` (moved to another monitor); and the
  current screen's geometry / DPI change signals (the user changes
  resolution or scale in Windows while the app is open). Reconnect the
  screen signals when the screen changes. **Verify the exact Qt 6 signal
  names with qt-docs** (`QScreen::geometryChanged`,
  `QScreen::logicalDotsPerInchChanged`, `QWindow::screenChanged`) before
  using them.
- `can_continue()` gains: `and (check.standard or acknowledged)`.
- If the display values change (any of W, H, S), **untick the
  acknowledgement**: the operator must accept the new non-standard display
  again. Becoming standard hides the checkbox and clears it.
- Ticking/unticking must re-evaluate the Continue button the same way the
  other Setup inputs already do (find and reuse that existing refresh path,
  do not add a second one).
- The acknowledgement is per sitting only. It is not saved to
  `local_state.json` or settings profiles.

### 4.5 Recording (D3)

Additive `SessionMetadata` fields (do not bump `schema_version`; same
reasoning as the geometry block):

| Field | Type | Meaning |
|---|---|---|
| `display_width_px` | `int \| None` | physical width of the screen the task ran on |
| `display_height_px` | `int \| None` | physical height |
| `display_scale_percent` | `int \| None` | Windows scale, `round(dpr × 100)` |
| `display_standard` | `bool \| None` | 1920×1080 at 100 % |
| `display_nonstandard_acknowledged` | `bool \| None` | operator ticked §4.2's box; `None` when not launched from the dashboard |

- Filled in `AssessmentApp` at session time, from the **canvas's** screen
  (where the task actually ran), alongside `_record_geometry()` and using
  `check_display()`. Not from the Setup page's earlier reading.
- The acknowledgement comes from Setup: a new optional
  `AssessmentApp(..., display_acknowledged: bool | None = None)` kwarg,
  passed by `DashboardWindow` at `dashboard_window.py:394`. The standalone
  `--task X --gui` path passes nothing (stays `None`).
- One session-log line next to `Geometry:`, e.g.
  `Display: 1920x1080 at 100% (standard).` or
  `Display: 1920x1080 at 150% (NON-STANDARD, acknowledged by operator).`
- With `display_scale_percent` recorded, the existing logical
  `canvas_*` / `canvas_offset_*` values become convertible to physical px
  afterwards. That unit mix itself is **not** changed here (§5).
- Add a one-line pointer in `SPEC-gazepoint-analysis-export-parity.md`
  §10.3 saying `device_pixel_ratio` is covered by this SPEC's §4.5.

## 5. Scope

In: `src/engine/display_check.py` (new), `src/ui/setup_page.py`,
`src/ui/dashboard_window.py` (pass the acknowledgement), `src/app.py`
(record + log), `src/data/schema.py` (fields), new tests, the one-line
pointer in the export-parity SPEC.

Out (do NOT change):
- Any responsive/flex layout, and the 150 % Tasks-page clipping itself
  (deferred to a later version, user decision §1.3).
- Changing Windows display settings from the app.
- The cursor maths (`_sync_gaze_geometry`, helpers from `5199a05`).
- The `_record_geometry()` physical/logical unit mix (§4.5 only makes it
  recoverable).
- `configs/default.yaml`, `local_state.json`, settings profiles.
- The Results page (no new row this round).

## 6. Acceptance criteria

1. `check_display()` unit tests: 1920×1080 @ dpr 1.0 → standard;
   1280×720 @ 1.5 → 1920×1080 at 150 %, non-standard; 1536×864 @ 1.25 →
   125 %, non-standard; 1366×768 @ 1.0 and 2560×1440 @ 1.0 → non-standard;
   rounding is stable for fractional logical sizes.
2. `_format_display_warning()` returns `""` when standard and a text that
   contains W, H, S and the "Settings → System → Display" path when not.
3. Gate: with everything else satisfied, `can_continue()` is False for a
   non-standard display until the box is ticked, True for a standard one
   with no box. A change in display values unticks the box.
4. Metadata: a session's `metadata.json` has the five §4.5 fields;
   `display_nonstandard_acknowledged` is `None` for the standalone path.
   The session log has exactly one `Display:` line.
5. Full pytest: 247 + new tests pass, with only the known local-config
   failure `test_config_merges_task_over_default`.

## 7. Plan for the next session

1. ~~**Wireframe (hub, mandatory first)**~~ **DONE 2026-10-02:**
   `docs/wireframes/setup.md` / `setup.html` now has the Display card in
   both states (A standard, B non-standard with the checkbox) and the
   updated Continue-gate note. The implementer builds against it.
2. ~~Commit the wireframe + this SPEC~~ **DONE 2026-10-02.** If the user's
   look at `setup.html` changes the wording, update §4.3 and the wireframe
   before step 3.
3. **Implement (spec-implementer subagent, Sonnet 5.5):** §4–§6, run pytest,
   append the §8 Impl log; ambiguities go to §9 and it returns. No commit.
4. **Review (hub):** diff + Impl log against §6, rerun pytest.
5. **Live check (hub + user, qt-mcp, maximized):** unset → green OK line,
   no checkbox, Continue gated only by the usual inputs;
   `QT_SCALE_FACTOR=1.5` → warning reads 1920×1080 at 150 %, Continue
   disabled until ticked; run a short task and confirm the five
   `metadata.json` fields and the `Display:` log line. Optional: change
   the real Windows scale while the app is open and confirm the card
   updates and the box unticks.
6. Commit (hub, explicit paths), push, update memory.

## 8. Impl log

(Implementer appends dated entries here: changes, test results,
deviations.)

## 9. Implementer open questions

(Implementer appends here, then stops and returns.)

## 10. Log

- **2026-10-02 — SPEC created; design approved.** After the cursor fix
  (`5199a05`) passed live at 150/125/100 %, the user asked for a Setup-page
  warning recommending 1920×1080 at 100 %, citing the squeezed Tasks-page
  cards at 150 % and the goal of standardized data. Three questions asked
  and answered: warn + acknowledge (D1), a new Display card between Tracker
  and Calibration (D2), and recording the display in each session (D3).
  Responsive layout is deferred to a later version by the user. Next:
  wireframe, then implementation (§7).

- **2026-10-02, later — wireframe done, SPEC committed.** On the user's
  instruction (wireframe first, then commit and push), the Display card was
  added to `docs/wireframes/setup.md` between Tracker Connection and
  Calibration, in both states, with the §4.3 text verbatim and the Continue
  gate note extended. Rendered with wiremd (`clean`) and checked by a
  Playwright full-page screenshot. Next: the user looks at `setup.html`,
  then §7 step 3.
