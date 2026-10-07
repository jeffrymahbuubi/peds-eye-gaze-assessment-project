# Current design inventory (2026-10-07, refreshed 2026-10-08 at `c300411`, branch feature/compass-task-flow)

There is no **documented** design system. There is an informal one, built page by page while the
SPECs were implemented: a colour token list plus one stylesheet. This file lists what exists, so an
evaluator can judge it without reading all of `src/ui/`.

## 1. Where the styling lives

| File | What |
|---|---|
| `src/ui/wtmh_theme.py` (~500 lines) | "WTMH Clinical Teal" colour tokens + the app-wide QSS, scoped to `QWidget#wtmhDashboard` |
| `src/ui/dialog_theme.py` | Applies the same look to dialogs (fixes Windows dark-mode palette leaks, P9a FX1) |
| `src/ui/canvas.py`, `canvas_shapes.py` | Child-facing task canvas painting (QPainter): targets, cells, icons, gaze cursor, rings, particles |
| `src/ui/target_map_paint.py`, `map_legend.py` | Report Target Map + legend painting |
| `src/ui/report_pdf.py` | PDF report (QTextDocument HTML, A4 portrait) |
| `configs/themes/forest.yaml`, `space.yaml` | Canvas themes (background, target, cursor, particles, hit character, sounds); every task uses `forest` |
| `configs/assets/` | Icons (spin-box arrows as PNG), sounds |
| `docs/wireframes/*.md|html` | wiremd wireframes of every page (layout and wording reference, not visual design) |

## 2. Tokens (`wtmh_theme.py`)

| Token | Value | Use |
|---|---|---|
| ACCENT | `#1F7A9C` | focus, links, sliders |
| ACCENT_GRADIENT_START / END | `#2FA8C4` / `#1A6F95` | primary button horizontal gradient |
| TITLEBAR_BG / TITLEBAR_TEXT | `#12374A` / `#CFE6EE` | top bar |
| SOFT_ACCENT / SOFT_ACCENT_TEXT | `#DCF0F5` / `#0F5670` | table headers, selected rows, accent badges, info tints |
| BACKGROUND / PANEL_BG | `#F5F9FB` / `#FFFFFF` | page / cards |
| BORDER / CONTROL_BORDER | `#DBE6EC` / `#7B93A1` | card borders / control outlines |
| INK / MUTED | `#122B3A` / `#5C7684` | text / secondary text |
| DANGER / SUCCESS | `#E15353` / `#2F9E6E` | states |
| NEUTRAL_BADGE_BG | `#E6EDF1` | neutral badge |
| DISABLED_BG / BORDER / TEXT | `#E9EDF0` / `#CDD6DC` / `#6F808A` | disabled controls |
| BANNER_BORDER | `#8FB4C2` | info banner left border |
| WARNING_BG / WARNING_BORDER | `#FBF0DC` / `#D9A441` | warning banner, run bar |

No type, spacing, radius or elevation tokens: sizes are literals in the QSS
(font 11 / 15 / 16 / 22 px; radius 2 / 4 / 5 / 6 / 7 / 8 / 9 px; paddings 2-18 px).
Font: the Qt default on Windows (Segoe UI); no font is set.

## 3. Components (QSS object names)

- Shell: `wtmhDashboard`, `wtmhTitleBar`, `wtmhBrandTitle`, `wtmhNavButton` (1 · Setup / 2 · Tests).
- Text: `wtmhPageTitle` (22 px bold), `wtmhSectionTitle` (16 px), `wtmhMuted`.
- Containers: `wtmhCard` (white, rounded, bordered), `wtmhSetupScroll`, `wtmhConfigScroll`.
- Buttons: `wtmhPrimary` (gradient), `wtmhSecondary`, `wtmhGhost` (outline), disabled grey.
- Feedback: `wtmhAlertInfo / Success / Warning / Error` (tinted, left border), badges
  `wtmhBadgeAccent / Success / Danger / Neutral` (pill, 9 px radius, 11 px text).
- Data: `wtmhTestTable` (Test List), report tables (`FitTable`), `SliderSpinRow` (slider + spin box).
- Forms (configuration page): radio groups with a plain label above (`Pointer (what moves the
  pointer)`, `Selection (how a target is selected)`, icon size, cell gap, movement path); a
  control that does not apply to the chosen Selection is **greyed in place** (label, slider and
  spin box at the disabled colours, still laid out) rather than hidden (SPEC-input-selection
  4.1; screenshot 17).
- Notes (one-line, info style): the Setup page's "No tracker connected: only Mouse tests can run."
  above the Continue button (01), the Start page's "Mouse test — ..." line under the title (19).
- Run: run bar (amber strip: status text + Pause / Skip trial / Quit) under the canvas.
- Small dialogs (`dialog_theme.py`): Add New Test (03), "Save as a new configuration" name prompt
  (18): one sentence, one field, primary + ghost button, no icon.

## 4. Child-facing canvas (forest theme)

Mint background `#e8f5e9`; target red `#ff5252` drawn with a radial gradient and a white ring;
inactive scanning shapes in pale green; grid cells as rounded outlined boxes; follow target leaves a
fading trail; gaze cursor = small dark halo + white core; hit character = butterfly; hit/miss
sounds. Sizes are visual-angle based (3 / 5 / 8 deg).

Added by SPEC-input-selection-and-follow.md step 2 (`7b5ece6`, in the tree since the first
captures): **Glow on target**, a soft radial halo in the theme's particle colour (forest: green)
behind the target while the pointer is on it, drawn only under Switch selection (and, once step 3
lands, in Follow the Target); the instant on-target ring (dark green) draws on top of it
(screenshot 20). In a Gaze + Switch run the OS cursor is parked and hidden; in a Mouse run the OS
arrow is the pointer and the gaze cursor is drawn at it. The scanning target's white ring is
always a circle, also on the square, triangle and diamond shapes.

## 5. Screenshots (`screenshots/`, real app, 1920x1080 @ 100 %, 2026-10-08)

| File | Page | Captured |
|---|---|---|
| 01-setup-empty | Setup (no subject, not connected; the "only Mouse tests" note) | 2026-10-08 refresh |
| 02-test-list-empty, 04-test-list, 12-test-list-with-done | Test List (empty, Not Done, Done rows) | 2026-10-08 first set |
| 03-add-test-dialog | Add New Test dialog | first set |
| 05-config-scanning, 07-config-follow, 09-config-grid | Configuration page per task, default Gaze + Dwell (Input card, Dwell card, Glow) | refresh |
| 06-run-scanning-preview, 08-run-follow-preview, 10-run-grid-preview | Task canvas (Preview, mouse, Dwell) with run bar | first set |
| 11-start-page-blocked | Start page of a Gaze test with the blocker banner | first set |
| 13-report-summary, 14-report-summary-lower, 15-report-detailed | Report (real run P9REAL: scanpath, legend, eye metrics, trial table) | first set |
| 16-report-pdf-grid.pdf | PDF report (A4 portrait) | first set |
| 17-config-scanning-mouse-switch | Configuration page with Pointer = Mouse, Selection = Switch: dwell threshold and dwell ring greyed in place, "Modified from Standard" | refresh |
| 18-config-name-dialog | "Save as a new configuration" prompt (Save & Continue after changing Standard) | refresh |
| 19-start-page-mouse | Start page of a Mouse test: no blocker, the "Mouse test — the tracker is not connected..." note, switch wording in the read-aloud text | refresh |
| 20-run-scanning-switch-glow | Scanning practice under Mouse + Switch with the pointer on the target: green glow halo + dark instant ring, run bar "mouse pointer" | refresh |

Capture method: the first set is a screen grab of the maximized window (1920x1080, Windows
taskbar visible at the bottom); the refresh is an OS PrintWindow of the window
(`tools/qa/capture_window.ps1`, 1936x1048, the 8 px window frame included, no taskbar). Same
window size and scale in both.

Not captured (need a recorded run or an open dialog flow): Test Complete / quit / discard
dialogs, rename dialog, calibration details. Their layout is in `docs/wireframes/run-end.md` and
`task-config.md`.

State of the tree: the screenshots show `c300411`, which has SPEC-input-selection-and-follow.md
steps 1-2 (Input card, Switch, Mouse, Glow). **Step 3 (Follow the Target: Pointer-only Follow page
without the Dwell card, "Trial duration", no Selection window) is built but not merged**, so 07
and 08 still show Follow & Click with a Dwell card and a Selection window. Step 4 (report tables
for Switch and Follow) and SPEC-subject-data-layout.md (Setup folder choice) are not built. The
wireframes in `docs/wireframes/task-config.md` and `report-*.md` show the intended end state.
