# Current design inventory (2026-10-07, branch feature/compass-task-flow)

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
- Run: run bar (amber strip: status text + Pause / Skip trial / Quit) under the canvas.

## 4. Child-facing canvas (forest theme)

Mint background `#e8f5e9`; target red `#ff5252` drawn with a radial gradient and a white ring;
inactive scanning shapes in pale green; grid cells as rounded outlined boxes; follow target leaves a
fading trail; gaze cursor = small dark halo + white core; hit character = butterfly; hit/miss
sounds. Sizes are visual-angle based (3 / 5 / 8 deg).

## 5. Screenshots (`screenshots/`, real app, 1920x1080 @ 100 %, 2026-10-08)

| File | Page |
|---|---|
| 01-setup-empty | Setup (no subject, not connected) |
| 02-test-list-empty, 04-test-list, 12-test-list-with-done | Test List (empty, Not Done, Done rows) |
| 03-add-test-dialog | Add New Test dialog |
| 05-config-scanning, 07-config-follow, 09-config-grid | Configuration page per task |
| 06-run-scanning-preview, 08-run-follow-preview, 10-run-grid-preview | Task canvas (Preview, mouse) with run bar |
| 11-start-page-blocked | Start page with the blocker banner |
| 13-report-summary, 14-report-summary-lower, 15-report-detailed | Report (real run P9REAL: scanpath, legend, eye metrics, trial table) |
| 16-report-pdf-grid.pdf | PDF report (A4 portrait) |

Not captured (need a recorded run or an open dialog flow): Test Complete / quit / discard
dialogs, rename and configuration-save dialogs, calibration details. Their layout is in
`docs/wireframes/run-end.md` and `task-config.md`.

Note: these screenshots predate SPEC-input-selection-and-follow.md (Input card, Switch, Follow
the Target) and SPEC-subject-data-layout.md (Setup folder choice). Re-capture after those land if
the evaluation should include them.
