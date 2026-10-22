---
name: SPEC-test-list-visual-identity
title: "Test List: a look of our own for the test rows and the right-side buttons (look only, design system unchanged)"
status: DESIGNED 2026-10-22, awaiting the user's choice of direction (section 9)
created: 2026-10-22
last_updated: 2026-10-22
next_step: the user answers section 9 (Q1 direction, then the questions of that direction; GATE 1), then the chosen wireframe becomes docs/wireframes/test-list.md and spec-implementer runs plan step 3
related:
  - SPEC-compass-task-flow.md (4A.4: the Test List page, its buttons, enable matrix and keys)
  - SPEC-design-system-phase1.md (tokens, contrast table, H1)
  - SPEC-design-system-phase2.md (H5 / V2: table widths, button tiers, Delete glyph, the button column)
  - SPEC-design-system-phase4.md (map and data-viz tokens; nothing here touches them)
  - docs/design/fable-proposal.md (2.4 radius, 2.5 component rules)
  - docs/wireframes/test-list.md (today's page)
  - docs/wireframes/test-list-alt-a.md, test-list-alt-b.md, test-list-alt-c.md (the three directions, with .html renders)
---

# SPEC-test-list-visual-identity

**Status: DESIGNED 2026-10-22. Three directions drawn; awaiting the user's choice (section 9). No code changed.**

## 1. Origin

Hsieh (clinical collaborator), `resources/hsieh/suggestion.txt`, point 2, verbatim:

> "Test list display: Although we are using Compass as a reference, we could consider making the
> test list and the buttons on the right slightly more visually distinct from those in Compass, so
> that our interface has its own unique design."

Point 1 of the same file (calibration speed and picture size) is SPEC-app-drawn-calibration.md 4.9.

## 2. Decisions (user, 2026-10-22)

| # | Decision |
|---|---|
| D1 | **Look only.** Only the styling of the Test List rows and the right-side buttons changes. Same functions, same elements, same order, same layout logic, same workflow, same enable matrix. |
| D2 | **Design system unchanged.** Only existing tokens of `src/ui/design_tokens.py` and existing component styles. No new token, colour, font, size or radius. |
| D3 | **Brainstorm, then choose.** A Fable 5.1 design agent drew three alternative directions, each as a wiremd wireframe; the user chooses one (section 9). |

## 3. Current code (as of `b0833d2`, branch `feature/compass-task-flow`)

- `src/ui/test_list_page.py` (485 lines):
  - `_build` 202-284: title `wtmhPageTitle` (204-206); body row with 24 px spacing (209); the table
    `SubjectTestTable` named `wtmhTestTable` (216-228) with a vertical-header-only `_TABLE_STYLE` (82);
    a `QStackedWidget` with the empty-state frame `wtmhEmptyTable` (232-244); the muted unreadable
    and message lines (246-255).
  - Button column 257-272: a `QVBoxLayout`, spacing 10, top-aligned (`addStretch` at the end).
    Add New Test, Configure Test, View Report, Copy Test, Delete Test and Open Subject Folder are
    `wtmhGhost` (= secondary); Run Test is `wtmhPrimary`. Delete Test carries
    `glyph_icon(GLYPH_SQUARE, DANGER, TEXT_DISABLED)` at 12 px (266-267).
  - `_button` 302-308: `setMinimumWidth(170)`, `setAutoDefault(False)`.
  - Footer 274-284: Back to Setup (`wtmhTertiary`) and "Changes are saved automatically."
  - Sorting by header click 333-348 (the sort indicator is hidden until the first click);
    enable matrix `_update_buttons` 356-370.
- `src/ui/test_list_table.py` (209 lines): `OTHER_COLUMN_WIDTHS = (180, 200, 180, 140)` and
  `NAME_MIN_WIDTH = 240` (43-44); Test Name stretches, the rest `Fixed` (150-152); the Status cell is a
  `_BadgeCell` holding a `StatusBadge` (116-127, 195); keys in `keyPressEvent` (200).
- `src/ui/wtmh_theme.py` (309 lines): `button_rule` 67-115 (40 px, min 96, 14 px / 600, radius 4,
  hover fill, a 2 px focus border that moves nothing, the grey disabled look); the tier selectors
  118-129 (`wtmhGhost` is in `_SECONDARY`); the three tier rules 275-279; `QFrame#wtmhCard` 281-285.
- `src/ui/wtmh_controls.py` (342 lines), 319-341: every dashboard `QTableWidget` gets PANEL, a 1 px
  BORDER_SUBTLE frame, radius 0, BORDER_SUBTLE grid lines, a 2 px ACCENT_FOCUS focus border, and a
  `QHeaderView::section` with the HEADER fill, INK, 600. Only `#wtmhTestTable::item:selected` is
  test-list specific (ROW_SELECTED, INK). There is **no `::item:hover` rule**: rows have no hover.
- `src/ui/status_badge.py`: Not done = ring on HEADER, TEXT_SECONDARY; Done = filled circle on
  SUCCESS_SUBTLE; Ended early = half circle on WARNING_SUBTLE; Data missing = triangle on
  WARNING_SUBTLE (62-81); glyph 12 px.
- `src/ui/glyphs.py` (122 lines): seven painted shapes (circle, ring, half, triangle, square,
  dashed, info, 18-24), `glyph_pixmap(..., dpr)` 103, `glyph_icon(shape, color, disabled_color)` 116.
- `src/ui/design_tokens.py`: the tokens, `CONTRAST_PAIRS`, `RADIUS = 4` ("tables and the title bar
  have none"), `TABLE_ROW_HEIGHT = 40`, `BUTTON_HEIGHT = 40`. `ACCENT_SUBTLE` is documented as
  "accent badge, hovered list row".
- Tests that pin today's look: `tests/test_test_list_badges.py` (widths 215-275; the button column
  24 px right of the table, top-aligned, ending at the right gutter 277-294; empty-state frame
  297-312; tiers 316-345), `tests/test_design_tokens.py` (`SHEET_MODULES` 48, `SHEETS` 70, the
  table rule 436-447). `test_list_page.py` and `test_list_table.py` are **not** in `SHEET_MODULES`.

### 3.1 What looks like Compass today

Compared with `docs/compass/screenshots/05-test-list.png` and `14-test-list-states.png`:

- Same screen grammar: the title "Test List for <name>"; one full-width 5-column grid table with a
  grey header band and full grid lines (vertical and horizontal); one selected row as a fill; a
  vertical stack of equal-width text-only boxed buttons on the right; a footer below.
- Same button labels in the same order (Compass has Multi-Test Report in addition).
- Same table chrome: a framed white sheet, a header band, a grid.

Already ours: WTMH blue tiers (Run Test filled, the rest outlined in blue), status badges with
glyphs, 40 px rows at 14 px, the pale ROW_SELECTED with ink text (Compass: saturated blue, white
text), the button column top-aligned (Compass: centred vertically), the red Delete glyph.

## 4. Design

### 4.1 Rules common to every direction

- Seven buttons, same labels, same order, same enable matrix, same signals; disabled buttons stay
  visible. Table: same five columns, same widths (Test Name stretches), same sorting, rename (F2,
  double-click), Enter, Delete key, selection kept across reload and sort.
- The button column stays 24 px right of the table, top-aligned, ending at the right gutter.
- Tokens only, existing tiers (`wtmhPrimary`, secondary, `wtmhTertiary`), the existing card
  (`QFrame#wtmhCard`), the existing status badge. Any new QSS is **scoped to the Test List**
  (`#wtmhTestTable`, or an object name on the page), so the other dashboard tables keep the global
  rule of `wtmh_controls.py` 319-341.
- Unchanged: title, footer, empty states, unreadable-file line, message line, all dialogs, keys.

### 4.2 Direction A "Ledger" (`docs/wireframes/test-list-alt-a.md`)

Idea: a quiet ledger. The table loses its spreadsheet chrome; the seven buttons become one bordered
command panel of full-width rows.

- Table: no vertical grid lines, 1 px BORDER_SUBTLE horizontal rules; Task and Configuration in
  TEXT_SECONDARY, the rest INK; row hover ACCENT_SUBTLE; Date right-aligned, tabular figures. Header
  as drawn: no band (PANEL), 12 px / 600 TEXT_SECONDARY, 1 px BORDER_STRONG rule under it
  (fallback: keep the HEADER band, section 9 Q2).
- Buttons: one `QFrame#wtmhCard` (PANEL, 1 px BORDER_SUBTLE, radius 4), spacing 0. Six buttons in the
  tertiary tier (text only, ACCENT, left-aligned, hover ACCENT_SUBTLE), Run Test primary. Three
  BORDER_SUBTLE separators split four lifecycle groups: Add · Configure / Run / View Report ·
  Copy / Delete · Open Subject Folder. The wireframe sets `border-radius: 0` on the rows (section 9 Q5).
- Tokens: PANEL, PAGE, INK, TEXT_SECONDARY, TEXT_DISABLED, BORDER_SUBTLE, BORDER_STRONG,
  ROW_SELECTED, ACCENT, ACCENT_HOVER, ACCENT_SUBTLE, ACCENT_FOCUS, ACCENT_DISABLED_FILL,
  ACCENT_DISABLED_TEXT, DISABLED_FILL, DANGER, TYPE_BODY, TYPE_CAPTION, RADIUS, TABLE_ROW_HEIGHT,
  BUTTON_HEIGHT, spacing 8 / 16 / 24. **New assets: none.**
- Cost: QSS plus a container, about 40 lines in `test_list_page.py` and a few rules in the theme.

### 4.3 Direction B "Record cards" (`docs/wireframes/test-list-alt-b.md`)

Idea: every test is a record card, not a spreadsheet row; the right column becomes a "Selected
test" card that names what the buttons act on.

- Table: no frame, no sheet, no grid; viewport PAGE. Each row painted as one card (PANEL, 1 px
  BORDER_SUBTLE, radius 4, 40 px tall, 8 px of PAGE between cards; row section 48 px). Selected:
  ROW_SELECTED + 1 px ACCENT edge; hover ACCENT_SUBTLE; keyboard focus: 2 px ACCENT_FOCUS edge on
  the selected card. Header: floating labels, PAGE fill, 12 px / 600 TEXT_SECONDARY, no rule.
- Buttons: one `QFrame#wtmhCard` (24 px padding, 8 px between buttons, about 220 px wide). Heading:
  the selected test's name (`wtmhSectionTitle`, 20 px / 600) and its `StatusBadge`, or "No test
  selected" in TEXT_SECONDARY. The seven buttons full width, tiers unchanged.
- Tokens: as A plus PAGE as the list background, TYPE_HEADING, the card style. **New assets: none.**
  New text: the heading "No test selected" (a new string, not a new element type).
- Cost: a `QStyledItemDelegate` row painter, about 80-100 lines in `test_list_table.py`
  (`frozen_table.py` has the pattern); the card heading updated in `_update_buttons()`.

### 4.4 Direction C "Signal" (`docs/wireframes/test-list-alt-c.md`)

Idea: keep the grid operators know; give every button and every task a painted glyph.

- Table: HEADER band, 40 px rows and the BORDER_SUBTLE grid stay. Task cell: a 12 px ACCENT task
  glyph before the name (`QTableWidgetItem.setIcon`, Qt draws it, no delegate). Date right-aligned,
  tabular figures. Row hover ACCENT_SUBTLE.
- Buttons: tiers, order and width unchanged; each gets a 12 px action glyph in a 24 px slot and a
  left-aligned label. Glyph colour = the tier's text colour (ACCENT, white on Run Test, grey when
  disabled); Delete keeps its DANGER square.
- Tokens: as today plus SUCCESS_TEXT / WARNING_TEXT (badges, unchanged). **New assets, flagged:**
  11 painted glyphs in `src/ui/glyphs.py`: 7 actions (plus, sliders, play, document, two squares,
  folder; Delete reuses the square) and 4 tasks (Static Click, Grid Click, Follow the Target,
  Scanning Search). QPainter drawings, token colours only, no PNG. Cut-down variant: the 7 button
  glyphs only.
- Cost: about 150 lines of glyph drawing plus a test per shape; QSS `text-align: left` on the
  test-list buttons.

### 4.5 Comparison

| | A Ledger | B Record cards | C Signal |
|---|---|---|---|
| Distance from Compass | medium | large | small to medium |
| What carries the identity | the command panel; the grid gone | cards; the "Selected test" heading | glyphs on buttons and tasks |
| New assets | none | none | 11 painted glyphs (or 7) |
| Code | QSS + a container (~40 lines) | row delegate (~80-100) + card heading | glyphs (~150) + QSS + icons |
| Height for 5 rows | 200 px | 232 px | 200 px |
| Operator risk (knows Compass) | low to medium | medium ("a different app"; sorting less visible) | lowest |
| Existing tests to update | button geometry, tiers | button geometry, table frame, empty state | add icon tests only |
| `test_list_page.py` 500-line limit | at risk (485 now) | at risk (heading code) | safe (icons are one call each) |

### 4.6 Design-rule flags (fable-proposal 2.4 / 2.5, verified)

| Direction | Rule | Tension | Hub view |
|---|---|---|---|
| A | 2.5 Tables: "Header 14 px / 600 ink on header fill" | header without the band, at 12 px TEXT_SECONDARY | a real deviation; Q2 |
| A | 2.5 Buttons: "radius 4"; 2.4 radius 4 on buttons | the panel rows at radius 0 (not flagged by the brainstorm) | avoidable: keep radius 4 and 8 px panel padding; Q5 |
| A | 2.5 Buttons: tertiary "for Back to Setup" | six more tertiary buttons | an existing tier in a new place; acceptable |
| B | 2.4: tables radius 0, cards radius 4 | rows drawn as radius-4 cards | follows the card rule instead; acceptable if the user wants B |
| B | 2.5 Tables header rule | floating labels, no fill | as A |
| B | 2.4 "a card never holds a card" | the right card holds buttons and a badge | holds |
| C | 2.5 Status badges: painted glyphs are state shapes | action and task shapes join the glyph set | icons, not a token or style change; Q3 |
| A, C | 2.5 Tables: "Numeric columns right-aligned with tabular figures" | the right-aligned Date **follows** this rule | Q6: do it in any direction |

New contrast pairs (computed from the tokens; none is in `CONTRAST_PAIRS` yet):

| Pair | Ratio | Used by |
|---|---|---|
| INK on ACCENT_SUBTLE | 15.37 | row hover, all |
| TEXT_SECONDARY on ACCENT_SUBTLE | 6.64 | A, hovered Task / Configuration |
| TEXT_SECONDARY on ROW_SELECTED | 5.88 | A, selected Task / Configuration |
| ACCENT on ROW_SELECTED | 4.58 (non-text, 3:1) | B selected edge; C task glyph on the selected row |
| DANGER on ACCENT_SUBTLE | 4.25 (non-text, 3:1) | the Delete glyph on a hovered button (exists today, unlisted) |

### 4.7 Hub recommendation

**A, with the HEADER band kept (Q2) and the rows at radius 4 (Q5); C's seven button glyphs not now.**

- A puts the identity where Hsieh pointed: the right-side buttons. A single grouped command panel
  is the most visible break from Compass's seven loose boxes, at the lowest cost and with no assets.
- Keeping the HEADER band and radius 4 removes both of A's rule deviations. What stays different
  from Compass is still clear: no vertical lines, quieter secondary columns, hover, the panel.
- B goes beyond "slightly more distinct": the list stops reading as a table, sorting is less
  visible, and it needs the largest code change. Its one strong idea, naming the selected test
  above the buttons, could be a later SPEC.
- C alone changes the least: from across the room it is still the Compass grid with a button stack.
  Its button glyphs would sit well inside A's panel; add them later if the user still finds A too
  close to Compass after the live look.

### 4.8 Wireframes

- The three directions: `docs/wireframes/test-list-alt-{a,b,c}.md` with `.html` renders. Each has
  the element-by-element difference from Compass, states, accessibility, cost and risk.
- **Known tooling issue (out of scope):** `tools/apply_wtmh_wireframe_theme.py` still retints the
  renders to the older teal palette (`#1F7A9C`, lines 116, 239, 272), so the rendered colours are
  not the design-system blue. The token names in the `.md` files are authoritative.
- wiremd limits: no tertiary button (A draws outlined rows), no table of cards (B draws separate
  cards), Unicode stand-ins for C's glyphs.

## 5. Scope

**In:** the styling of the Test List table rows and header and of the seven right-side buttons, in
the chosen direction; the container around the buttons (A, B); the glyphs (C, if chosen); the
contrast rows; test updates; the chosen wireframe as `docs/wireframes/test-list.md`.

**Out:**
- any new token, colour, font, size or radius; any change to `button_rule` or the global table rule;
- the footer, the title, empty states, the unreadable-file and message lines, all dialogs (Add, Delete, rename editor);
- the enable matrix, sorting, keys, signals, column set and widths;
- other pages and other tables;
- the theme-script retint of `tools/apply_wtmh_wireframe_theme.py`.

## 6. Acceptance criteria

### 6.1 Any direction

| # | Criterion | Checked by |
|---|---|---|
| T1 | Functions unchanged: `tests/test_test_list_page.py` and `tests/test_test_list_actions.py` pass with no assertion changed (enable matrix, sort, rename, Enter, Delete key, open folder, reload, selection kept) | pytest |
| T2 | Same elements: title, five headers, seven buttons with today's labels in today's order, Back to Setup and the saved line; Run Test the only primary | pytest (existing tier test, its secondary set updated only if A turns them tertiary) |
| T3 | Tokens only: `test_list_page` and `test_list_table` (and `glyphs` for C) join `SHEET_MODULES` (no hex literal); every new sheet string joins `SHEETS` (token colours only, no gradient); font sizes on the type scale | `tests/test_design_tokens.py` |
| T4 | No new token: `design_tokens.py` differs only by new `CONTRAST_PAIRS` rows | hub `git diff` |
| T5 | Every new foreground/background pair (4.6) is a `CONTRAST_PAIRS` row and passes | `test_every_contrast_pair_meets_its_ratio_from_its_hex_values` |
| T6 | New rules scoped to the Test List; the other dashboard tables keep the global rule | `test_a_table_has_square_corners_a_header_fill_and_ink_header_text` unchanged and green |
| T7 | Layout at 1920 and 1366: four fixed widths kept, Test Name stretches, no sideways scroll; the right column (its container, if any) 24 px right of the table, top-aligned, ending at the right gutter | `tests/test_test_list_badges.py` (geometry tests point at the container where there is one) |
| T8 | Badges, 2 px focus border (nothing moves), disabled buttons visible and grey | existing badge and token tests |
| T9 | Screenshot comparison: window maximized at 1920x1080, 100 % scaling, a window capture (not a widget grab); states none selected, Not done, Done, Data missing, row hover, keyboard focus, empty list; beside `05-test-list.png` and today's page | hub, qt-mcp |
| T10 | Full pytest green except the known skip-worktree baseline; `ruff` clean; no file over 500 lines (`test_list_page.py` is 485: move the button column into a helper module if needed) | hub rerun |
| T11 | The user's live look, maximized | user |

### 6.2 Direction A

| # | Criterion |
|---|---|
| TA1 | Header per Q2: the HEADER band as today, or PANEL / 12 px / 600 TEXT_SECONDARY with a 1 px BORDER_STRONG rule |
| TA2 | No vertical grid lines; 1 px BORDER_SUBTLE between rows |
| TA3 | Task and Configuration cells TEXT_SECONDARY; Test Name and Date INK; Date right-aligned with tabular figures |
| TA4 | Row hover ACCENT_SUBTLE; selected row ROW_SELECTED with INK, as today |
| TA5 | The seven buttons inside one `QFrame#wtmhCard`, full width, in order; three BORDER_SUBTLE separators after Add, after View Report and after Delete; six tertiary rows left-aligned, Run Test primary; radius per Q5 |
| TA6 | Disabled rows: TEXT_DISABLED on DISABLED_FILL; disabled Run Test ACCENT_DISABLED_TEXT on ACCENT_DISABLED_FILL; 40 px rows |

### 6.3 Direction B

| # | Criterion |
|---|---|
| TB1 | A delegate paints each row as one card (PANEL, 1 px BORDER_SUBTLE, radius 4, 40 px, 8 px gap); no grid, no table frame; viewport PAGE |
| TB2 | Selected: ROW_SELECTED + 1 px ACCENT edge; hover ACCENT_SUBTLE; focus: 2 px ACCENT_FOCUS edge on the selected card |
| TB3 | Header: floating labels, clickable, sort arrow ACCENT, hover ACCENT_SUBTLE |
| TB4 | Right card: the selected test's name + badge, or "No test selected"; follows selection, sort, rename and reload |
| TB5 | The badge cell, the rename editor and the double-click / F2 still sit on the right row |
| TB6 | The empty states unchanged in text; shown as one card in the list area |

### 6.4 Direction C

| # | Criterion |
|---|---|
| TC1 | 7 action glyphs (or the cut-down set) and 4 task glyphs in `glyphs.py`, token colours only, sharp at dpr 1.0 / 1.25 / 1.5; one drawing test per shape |
| TC2 | Every right-side button has its icon (12 px, 24 px slot), a left-aligned label; the disabled icon is grey; Delete keeps the DANGER square |
| TC3 | Task cells carry the task glyph via `setIcon`; sorting by Task unchanged |
| TC4 | Row hover ACCENT_SUBTLE; Date right-aligned with tabular figures; HEADER band and grid as today |

## 7. Plan

1. **GATE 1 -** The user answers section 9: Q1 (direction) and the questions of that direction.
2. The chosen wireframe becomes `docs/wireframes/test-list.md` (updated with the answers: header,
   radius, glyphs); the other two per Q4. Hub commits the SPEC and wireframes on the user's OK.
3. `spec-implementer` in its own worktree. **Worktrees made by the Agent tool start from `main`:**
   the implementer first resets the worktree to `feature/compass-task-flow` (`git reset --hard
   feature/compass-task-flow` inside the new worktree, checked with `git log -1`), then implements
   section 4 for the chosen direction and section 6; appends to section 8; does not commit.
4. Hub review and the full pytest (T1-T10).
5. Live look by the user, window maximized (T9, T11). Commit on the user's OK; merge into
   `feature/compass-task-flow`; remove the worktree.

## 8. Impl log

### 2026-10-22 - Direction C "Signal" (worktree `testlist-c`, branch `testlist-c` at `11f4006`; not committed)

Implemented by `claude-sonnet-5-5` as `spec-implementer`, from the hub's brief and the user's decisions of
2026-10-22 (all 11 painted icons count as icons, Q3; right-aligned Date with tabular figures and a right-aligned
"Date Complete" header, Q6; grid, header band, widths and selected row as today; row hover ACCENT_SUBTLE).

**Files changed**
- `src/ui/glyphs.py` (122 -> 224 lines): `STATE_GLYPHS` (the old seven), `ACTION_GLYPHS` (plus, sliders, play,
  document, copy = two squares, folder), `TASK_GLYPHS` (task_static = dot in a ring, task_grid = 3 x 3 block, task_follow
  = path with arrow head, task_search = magnifier), `GLYPHS` = all three; the new shapes are drawn by
  `_draw_signal` on a 12 x 12 grid (1.5 px stroke at 12 px, whole-pixel squares for the grid, strokes centred on
  x.25 / x.75 so a 1.5 px line is one full pixel row and a half one). `glyph_pixmap(..., slot=0)`: a `slot` larger
  than the glyph makes a transparent `slot` x `slot` square with the glyph centred. `glyph_icon(..., slot=0)` now holds
  pixmaps at `ICON_DPRS` = 1.0 / 1.25 / 1.5 / 2.0 for Normal, Active and Selected (all the colour; so Qt does not tint
  a task glyph on a selected row) and Disabled (the disabled colour).
- `src/ui/test_list_style.py` (new, 68 lines): `TABLE_STYLE`, `BUTTON_STYLE` (`QPushButton { text-align: left; }`),
  `TASK_GLYPH` (task id -> shape), `style_action_button()`, `task_icon()`.
- `src/ui/test_list_page.py` (485 -> 492 lines): the seven `_button()` calls take their glyph (Delete keeps the DANGER
  square), `TABLE_STYLE` and `table.set_headers()` replace the local `_TABLE_STYLE` / `setHorizontalHeaderLabels`;
  docstring.
- `src/ui/test_list_table.py` (209 -> 275 lines): Task item icons (`setIcon`, `setIconSize(12 x 12)`), Date cells
  right-aligned with the `tnum` font, `set_headers()` (right-aligned Date label), `_RowDelegate` (row hover) with
  `SubjectTestTable.hover_row` / `viewportEvent`, `_on_sort_indicator()` (the `sortedByDate` property).
- `src/ui/design_tokens.py`: three new `CONTRAST_PAIRS` rows only: (INK, ACCENT_SUBTLE, 15.37), (ACCENT, ROW_SELECTED, 4.58),
  (DANGER, ACCENT_SUBTLE, 4.25). No new token, colour, font, size or radius.
- `tests/test_design_tokens.py`: `test_list_page`, `test_list_table`, `test_list_style` join `SHEET_MODULES`; the table and
  button sheets join `SHEETS`; one test for the three new pairs (+ the pairs the glyphs already sit on).
- `docs/specs/SPEC-test-list-visual-identity.md`: this entry and the open question in section 9.

**Tests added**: `tests/test_signal_glyphs.py` (69 collected: set, one sampled drawing test per new shape, corners empty,
colour, dpr 1.25 / 1.5 / 2.0, slot, icon modes and pixel ratios) and `tests/test_test_list_signal.py` (24 collected:
each button's icon pixel-identical to the expected glyph and colour in both states, the glyph colour equals the tier's
`color` in the dashboard sheet, painted glyph colour per state through the matrix, equal button widths, label starts
after the slot, focus moves neither glyph nor label, task icons per task / on a selected row / after a sort, Date and
header alignment and tabular figures, Date text and header end together, sort-arrow room, row hover across five
columns, selected row keeps its fill, hover survives a sort). Changed: `tests/test_design_tokens.py` (above).
No existing assertion was changed; T1 and the existing tier / geometry tests pass as they were.

**pytest** (worktree, full; counted from the progress lines, `-q` on top of `addopts = -q` hides the summary line): 4718 passed, 5 failed. The 5 are `tests/test_config_flow.py::test_a_new_test_opens_at_standard_with_the_task_defaults`
and `tests/test_task_config_page.py::test_a_new_test_opens_with_standard_and_the_defaults[click_static|click_grid|follow_moving|scanning]`
(`0.35 == 0.22`, the smoothing alpha of the committed `configs/default.yaml`): verified to fail identically on a clean
`git archive 11f4006` export, so they are not caused by this change (this clean worktree does not have the local
`default.yaml`, and `test_config_merges_task_over_default` passes here). After the final docstring edit of
`test_list_page.py` the focused set (`test_test_list_*`, `test_signal_glyphs`, `test_design_tokens`, `test_status_badge`)
was rerun: 387 passed (`387 passed in 42.19s`). `ruff check` is clean on every file touched (2 older findings remain in `calibration_flow.py`
and `report_page.py`, untouched). No file over 500 lines (`test_list_page.py` 492).

**Deviations from the wireframe / SPEC** (the look is as specified in each case)
1. **Row hover is painted by a small delegate, not by a QSS `::item:hover` rule.** `::item:hover` fills only the cell
   under the pointer, not the row (verified in a render). `_RowDelegate` paints ACCENT_SUBTLE under every cell of the
   hovered row, except the selected row, which keeps ROW_SELECTED; `hover_row` follows the viewport's hover events.
2. **The Date header has two sheet rules in `TABLE_STYLE`**: `padding-right: 11px` (8 px + the 3 px an item's text keeps
   from its cell edge) so the right-aligned label ends over the dates (measured: otherwise 4 px off), and 27 px while
   the list is sorted by Date, because the sort arrow sits at the right end of the section and overlapped the last
   letter of the right-aligned label (verified in a zoomed render). Scoped to the Test List table's own sheet.
3. **The 24 px slot is a 24 x 24 icon with the 12 px glyph centred**, so the glyph starts 22 px and the label about
   44 px from the button's left edge (1 px border + 15 px padding + 6 + 12 + 6 + Qt's 4 px icon-label gap). This keeps
   `QIcon.pixmap(12, 12)` of the Delete icon square, which the existing Delete test samples.
4. **The button column is about 19 px wider** (about 189 px; was 170) because the longest label, "Open Subject Folder",
   now sits after the slot ("or wider for the longest label" in the wireframe). The table gives that room up; all
   four fixed columns and the no-sideways-scroll rule still hold at 1920 and 1366 (existing width tests pass).
5. `glyph_icon` now holds four pixel ratios and the Active / Selected modes also for the existing Delete icon (it was
   dpr 1.0 only): sharper on a scaled display, no change at 100 %.
6. The wireframe's `task_glyph_pixmap()` is not a separate function: the task shapes go through the same `glyph_pixmap`
   / `glyph_icon` as every other glyph, and `task_icon()` (in `test_list_style.py`) builds the item icon.

**Left undone / for the hub**: Choice-making rows had no task glyph (section 9, implementer question; answered and done in the follow-up note below); the hub's live
look (T9, T11) and the screenshots; the renders I made offscreen with real Segoe UI (1500 and 1366 px, 100 % and
a 1.5 scale factor) looked right but are not the maximized 1920 x 1080 window capture T9 asks for. Pre-existing, not
touched: `glyph_pixmap()` with an unknown shape aborts the process (the `ValueError` leaves the painter active on the
pixmap), so the unknown-shape test calls `draw_glyph` on a `QImage`.

### 2026-10-22 (later) - Direction C follow-up: Choice-making task glyph

Answer to the section 9 question (user via the hub): a fifth task glyph. `claude-sonnet-5-5`, same worktree, not committed.
- `src/ui/glyphs.py` (224 -> 230 lines): `GLYPH_TASK_CHOICE` = a filled 5 px square (the one picked) beside an outlined
  5 px square (1.5 px stroke, 2 x 2 px hollow), vertically centred, same style, token colour, dpr-aware as the other four;
  `TASK_GLYPHS` has five shapes, `GLYPHS` 18. Two squares kept as the hub suggested: at 12 px a 1.5 px outline needs a
  5 px square to show its hole, so the squares are 5 px with a 1 px gap and take 0.5 .. 11.5 of the width (the other
  task glyphs take 1 .. 11), the filled one has half-covered edges like every 1.5 px stroke. Three small squares (the
  middle one larger) were tried and read worse.
- `src/ui/test_list_style.py` (68 -> 70 lines): `choice_making` -> `GLYPH_TASK_CHOICE` in `TASK_GLYPH`. The names of all
  five tasks now line up (checked in a 1500 px render).
- Tests: `tests/test_signal_glyphs.py` 69 -> 75 collected (a sampled drawing test for the new shape; it joins the
  corner, colour and dpr 1.25 / 1.5 / 2.0 parametrised tests; the set test now says 5 task shapes, 18 in all);
  `tests/test_test_list_signal.py` 24 -> 25 collected (Choice-making row has its glyph; every key of `TASK_INFO` has an
  entry in `TASK_GLYPH`, so a task added later cannot silently lose the alignment).
- Focused set (`test_test_list_badges`, `test_test_list_page`, `test_test_list_actions`, `test_test_list_signal`,
  `test_signal_glyphs`, `test_design_tokens`, `test_status_badge`): 394 passed. `ruff check` clean on the touched
  files. The full suite was not rerun for this follow-up (only glyph / task-icon code changed; the 5 pre-existing
  `0.35 == 0.22` config failures of the entry above are unaffected).

## 9. Open decisions (for the user)

- **Q1. Which direction?** A "Ledger", B "Record cards", C "Signal", or A + C's seven button glyphs.
  *Hub recommendation: A* (4.7): it changes the right-side buttons most visibly, needs no new asset,
  and is the cheapest. Glyphs can follow later if A still looks too close to Compass.
- **Q2. (if A) Keep or drop the grey HEADER band?** Dropping it is a deviation from proposal 2.5
  ("header labels on the header fill") and makes the clickable sort headers less obvious.
  *Hub recommendation: keep the band;* the rest of A carries the identity.
- **Q3. (if C or A + C) Do new painted glyphs count as icons within the unchanged design system?**
  They use only token colours and the existing glyph mechanism, but they add action and task shapes
  to a set that today holds state shapes only. *Hub recommendation: yes, icons, not a design-system
  change, provided they are drawn in `glyphs.py` at the existing 1.5 px stroke and token colours.*
- **Q4. What happens to the two unchosen wireframes?** (a) keep them as `test-list-alt-*.md`
  marked "not chosen" for the record, or (b) delete them. *Hub recommendation: (a), with a one-line
  "not chosen 2026-10-xx" note at the top of each, so Hsieh's question has its trail.*
- **Q5. (if A) Radius of the button rows inside the panel?** The wireframe sets radius 0; proposal
  2.5 gives buttons radius 4. *Hub recommendation: radius 4 with 8 px panel padding*, so the hover
  fill and the filled Run Test are rounded like every other button.
- **Q6. Right-aligned Date with tabular figures, in any direction?** Proposal 2.5 already asks for
  it ("Numeric columns right-aligned with tabular figures"); A and C include it, B does not say.
  *Hub recommendation: yes, in every direction* (the header label "Date Complete" right-aligned too).

### Implementer open questions (Direction C)

- **2026-10-22 - Choice-making has no task glyph.** The Task column gets four glyphs (Static Click, Grid
  Click, Follow the Target, Scanning Search), but `src/engine/task_info.py` has a fifth task,
  Choice-making, offered in Add New Test. Its rows have no icon, so its name starts about 18 px
  further left than the names in the other rows (visible in the 1500 px render). Not decided by the
  implementer; options: (a) a blank 12 px slot for tasks without a glyph, so every name lines up (about
  two lines in `SubjectTestTable.populate`); (b) a fifth painted glyph (a speaker, a hand ...); (c) leave
  it as it is. Only the Task cell of Choice-making rows is affected; the rest of direction C is done.
  **Answered 2026-10-22 (user, relayed by the hub): (b), add a fifth task glyph for Choice-making.** Done,
  see the follow-up note in section 8.

## 10. Log

- **2026-10-22** - SPEC drafted by the hub from Hsieh's point 2 and the Fable 5.1 brainstorm: three
  wireframes (`test-list-alt-a.md` Ledger, `-b.md` Record cards, `-c.md` Signal, with `.html`
  renders). Decisions D1-D3 recorded. Code claims checked against `b0833d2`; two flags added to
  the brainstorm's: A's radius-0 button rows (2.5) and the 500-line limit of `test_list_page.py`.
  Hub recommendation A with the HEADER band and radius 4. Awaiting the user's choice (section 9).
