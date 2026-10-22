![[_nav.md]]

## Test List for TESTING — Direction A "Ledger"

> **Alternative A of 3** (Hsieh's feedback 2026-10-22: make the test list and the right-side buttons visually distinct from Compass). **Look only**: same elements, same order, same positions, same workflow as `test-list.md`; only the styling of the rows and the button column changes. **Design system unchanged**: uses tokens PANEL, PAGE, INK, TEXT_SECONDARY, TEXT_DISABLED, BORDER_SUBTLE, BORDER_STRONG, ROW_SELECTED, ACCENT, ACCENT_HOVER, ACCENT_SUBTLE, ACCENT_FOCUS, ACCENT_DISABLED_FILL, ACCENT_DISABLED_TEXT, DISABLED_FILL, DANGER, TYPE_BODY, TYPE_CAPTION, RADIUS, TABLE_ROW_HEIGHT, BUTTON_HEIGHT, the spacing scale (8, 16, 24) and the existing button tiers (primary, secondary, tertiary) and status badge. No new token, colour, font, size or radius.

> **One-line idea:** a quiet ledger. The table loses its spreadsheet chrome (grey header band, vertical grid lines) and reads as typeset rows under a thin rule; the seven buttons become one bordered **command panel** of full-width rows instead of seven floating boxes.

::: grid-2 card

### Tests

| Test Name | Task | Configuration | Status | Date Complete |
|---|---|---|---|---|
| **Grid Click 1** | Grid Click | Standard | ○ Not done | — |
| Static Click 1 | Static Click | Standard | ● Done | 2026-10-06 |
| Follow the Target 1 | Follow the Target | Slow path | ◐ Ended early 4/6 | 2026-10-06 |
| Scanning Search 1 | Scanning Search | Standard | ▲ Data missing | 2026-10-05 |
| Grid Click 2 | Grid Click | Large targets | ○ Not done | — |

> Selected row: **Grid Click 1** (ROW_SELECTED fill across the whole row; the bold here only marks the selection in this mockup, the real row is not bold). Header: caption size, TEXT_SECONDARY, no fill, a 1 px BORDER_STRONG rule under it. Rows: 40 px, horizontal BORDER_SUBTLE rules only, no vertical lines. Task and Configuration in TEXT_SECONDARY; Test Name, Status and Date in INK.

### Actions

[Add New Test]{.outline}

---

[Configure Test]{.outline}

[Run Test]*

[View Report]{.outline state:disabled}

---

[Copy Test]{.outline}

[■ Delete Test]{.outline}

---

[Open Subject Folder]{.outline}

:::

> **Command panel** (right): one PANEL card (1 px BORDER_SUBTLE, radius 4) holding the seven buttons as full-width rows in the existing order. Inside the panel every button except Run Test is the **tertiary** tier (text only, ACCENT, left-aligned, 40 px, hover ACCENT_SUBTLE); Run Test is the **primary** tier (ACCENT fill, white text, full width). Thin BORDER_SUBTLE separators split the panel into its four lifecycle groups: create (Add New Test) · act on the selected test (Configure, Run, View Report) · duplicate / remove (Copy, Delete) · the subject folder. The mockup above draws the rows as outlined buttons because wiremd has no tertiary style; read them as text-only rows with a left-aligned label.

> **Selected row:** "Grid Click 1" (Not done). The buttons follow the same matrix as `test-list.md` (nothing selected: only Add New Test on; Not Done: Configure, Run, Copy, Delete on; Done / Ended early: View Report, Copy, Delete on; Open Subject Folder on whenever the subject has a folder). Disabled rows stay visible: DISABLED_FILL fill with TEXT_DISABLED text (the existing disabled look), a disabled Run Test keeps the pale ACCENT_DISABLED_FILL / ACCENT_DISABLED_TEXT.

---

### What differs from Compass (element by element)

| Element | Compass (`05-test-list.png`, `14-test-list-states.png`) | Today (`test-list.md`) | Direction A |
|---|---|---|---|
| Header row | grey band, black 12 px labels, column separators | HEADER grey band, 14 px / 600 INK | **no band**: PANEL, 12 px / 600 TEXT_SECONDARY labels, 1 px BORDER_STRONG rule beneath; sort arrow ACCENT |
| Grid lines | full grid, black | full grid, BORDER_SUBTLE | **horizontal rules only** (BORDER_SUBTLE), no vertical lines |
| Row text | 12 px, bold = not run | 14 px, one colour | Test Name INK; Task and Configuration TEXT_SECONDARY; Date tabular figures right-aligned; status = badge |
| Selected row | saturated Windows blue, white text | ROW_SELECTED, INK text | ROW_SELECTED, INK text (unchanged) |
| Hover row | none | none | ACCENT_SUBTLE fill (its documented use: "hovered list row") |
| Button column | 7 equal white boxes, centred bold text, 3 px apart | 7 outlined blue boxes, 10 px apart, Run Test filled | **one bordered panel** of full-width text rows, left-aligned, separators between lifecycle groups, Run Test the only filled row |
| Disabled button | grey text in a white box | grey text on DISABLED_FILL | grey text on DISABLED_FILL row (unchanged look, now a row) |
| Delete Test | plain box | outlined, red square glyph | text row with the red square glyph (unchanged glyph) |

### States

| State | Row | Button row in the panel |
|---|---|---|
| Normal | PANEL fill, INK / TEXT_SECONDARY text | ACCENT text on PANEL (tertiary) · Run Test: white on ACCENT (primary) |
| Hover | ACCENT_SUBTLE fill | ACCENT_SUBTLE fill (tertiary) · Run Test: ACCENT_HOVER |
| Selected / pressed | ROW_SELECTED fill, INK text (13.62:1) | pressed = hover fill |
| Focus (keyboard) | table: 2 px ACCENT_FOCUS border (existing) | 2 px ACCENT_FOCUS border inside the row, nothing moves (existing focus rule) |
| Disabled | n/a (rows are never disabled) | TEXT_DISABLED on DISABLED_FILL · Run Test: ACCENT_DISABLED_TEXT on ACCENT_DISABLED_FILL |
| Done / Not done / Ended early / Data missing | the status badge as today (glyph + word) | View Report on only for Done / Ended early with data |

### Accessibility

- Text: INK on PANEL 18.10:1, TEXT_SECONDARY on PANEL 7.81:1 (header labels, Task, Configuration), INK on ROW_SELECTED 13.62:1, ACCENT on PANEL 6.08:1 (button rows), white on ACCENT 6.08:1 (Run Test), TEXT_DISABLED on DISABLED_FILL 3.81:1 (disabled, exempt). The header rule BORDER_STRONG on PANEL 3.32:1 (non-text, passes 3:1).
- Targets: rows 40 px tall; button rows 40 px tall and the full panel width (about 200 px), larger than today's 170 px boxes.
- Not colour-only: the status badge keeps glyph + word; a disabled row is both grey-filled and grey-text; Run Test is set apart by fill and position, not by colour alone; the selected row is a fill, and keyboard focus adds the 2 px border.
- Hover on a row is a convenience only; nothing depends on it.

### Implementation cost (PySide6)

- **Table: QSS only.** A `QHeaderView::section` rule for the test table (PANEL fill, TYPE_CAPTION, TEXT_SECONDARY, a 1 px BORDER_STRONG bottom border); `setShowGrid(False)` plus an item rule with a 1 px BORDER_SUBTLE bottom border and an item-hover rule with the ACCENT_SUBTLE fill; `QTableWidgetItem.setForeground(TEXT_SECONDARY)` for the Task and Configuration cells (`test_list_table.py`). Right-aligned tabular date: `setTextAlignment` on the Date items. No delegate work, no assets.
- **Buttons: QSS + a container.** Wrap the existing `column` layout in a `QFrame#wtmhCard` with spacing 0; set the six secondary buttons to the tertiary object name with `text-align: left` and `border-radius: 0`; three 1 px `QFrame` separators (BORDER_SUBTLE); Run Test keeps `wtmhPrimary` with `border-radius: 0`. `setMinimumWidth(170)` becomes the panel's width. About 40 lines in `test_list_page.py`, a few rules in `wtmh_theme.py` / `wtmh_controls.py`.
- Tests: the Test List phase-2 tests pin widths and tiers; the ones that read the object names of the six buttons need updating.

### Risk for operators who know Compass

- **Low to medium.** Labels, order, position and the greyed-out matrix are unchanged, so the muscle memory holds. The one thing to learn: the right column is a panel of rows, not boxes; the hover fill and the filled Run Test make the rows read as buttons. The table reads as "the same list, cleaner": the sort-by-header behaviour is unchanged, though a header without a fill advertises its clickability less (mitigation: the sort arrow in ACCENT, and a header-section hover rule with the ACCENT_SUBTLE fill).
- Deviation to confirm: proposal 2.5 "Tables" says header labels sit on the header fill. Direction A drops the fill (tokens only, but a different application). Fallback if the hub keeps the rule: keep the HEADER band and apply only the other changes (no vertical lines, secondary text, command panel).

> **Wireframe notes:** wiremd has no tertiary (text-only) button style, so the panel rows are drawn as outlined buttons; the real rows have no border of their own, only the separators. The card around each grid column stands for the panel border on the right; on the left it only frames the table (the real table has its own 1 px BORDER_SUBTLE frame and no card). The bold "Grid Click 1" marks the selected row in the mockup only. The retint pass (`tools/apply_wtmh_wireframe_theme.py`) still uses the older teal palette; the tokens named in this file are the design-system values of `src/ui/design_tokens.py` and are what the implementation uses.

---

[Back to Setup](#)

Changes are saved automatically.

> Footer, empty states, unreadable-file line, keyboard rules and all modals: unchanged, see `test-list.md`.
