![[_nav.md]]

## Test List for TESTING — Direction B "Record cards"

> **Alternative B of 3** (Hsieh's feedback 2026-10-22). **Look only**: same elements, same order, same positions, same workflow as `test-list.md`. **Design system unchanged**: uses tokens PAGE, PANEL, INK, TEXT_SECONDARY, TEXT_DISABLED, BORDER_SUBTLE, BORDER_STRONG, ROW_SELECTED, ACCENT, ACCENT_HOVER, ACCENT_SUBTLE, ACCENT_FOCUS, ACCENT_DISABLED_FILL, ACCENT_DISABLED_TEXT, DISABLED_FILL, DANGER, TYPE_BODY, TYPE_CAPTION, TYPE_HEADING, RADIUS, TABLE_ROW_HEIGHT, BUTTON_HEIGHT, spacing 8 / 16 / 24, the card style (`QFrame#wtmhCard`), the existing button tiers and the status badge. No new token, colour, font, size or radius.

> **One-line idea:** every test is a **record card**, not a spreadsheet row. The rows sit as white cards on the PAGE background, 8 px apart, with the column labels floating above them; the right column becomes a **"Selected test" card** that names the test the buttons act on, so the greyed-out buttons explain themselves.

### Tests

| Test Name | Task | Configuration | Status | Date Complete |
|---|---|---|---|---|
| (column labels only: caption size, TEXT_SECONDARY, on the PAGE background, no band, no rule; a click still sorts) | | | | |

::: grid-2 card

### Grid Click 1

Grid Click · Standard · ○ Not done · —

|selected|{.primary}

### Selected test

**Grid Click 1** ○ Not done

[Add New Test]{.outline}

[Configure Test]{.outline}

[Run Test]*

[View Report]{.outline state:disabled}

[Copy Test]{.outline}

[■ Delete Test]{.outline}

[Open Subject Folder]{.outline}

:::

::: card

**Static Click 1** · Static Click · Standard · ● Done · 2026-10-06

:::

::: card

**Follow the Target 1** · Follow the Target · Slow path · ◐ Ended early 4/6 · 2026-10-06

:::

::: card

**Scanning Search 1** · Scanning Search · Standard · ▲ Data missing · 2026-10-05

:::

::: card

**Grid Click 2** · Grid Click · Large targets · ○ Not done · —

:::

> **Reading the mockup:** wiremd cannot draw a table whose rows are cards, so each row is a `card` block here and the first one shares the grid with the button card. In the real page the five columns stay aligned exactly as in `test-list.md` (Test Name stretches, Task 180, Configuration 200, Status 180, Date 140); each **row is painted as one card**: PANEL fill, 1 px BORDER_SUBTLE edge, radius 4, 40 px tall, 8 px of PAGE between cards, cell text 14 px INK, no grid lines at all. The table widget's own frame and background go away (background PAGE, no border), so the cards sit directly on the page like the Setup cards do.

> **Selected card:** ROW_SELECTED fill with a 1 px ACCENT edge (the first row above). **Hover:** ACCENT_SUBTLE fill, edge unchanged. **Keyboard focus:** the card's edge becomes 2 px ACCENT_FOCUS (the existing focus rule) instead of the whole table taking a focus border.

> **"Selected test" card (right):** the existing seven buttons in the existing order, full width inside one PANEL card (1 px BORDER_SUBTLE, radius 4, 24 px padding, 8 px between buttons). The card's heading is the selected test's name at the heading step (20 px / 600) with its status badge, or "No test selected" in TEXT_SECONDARY. Add New Test stays first and Open Subject Folder last, as today; they are inside the card for alignment only (both stay enabled whatever is selected). Secondary buttons keep the outlined tier; Run Test is the primary tier; Delete Test keeps its red square glyph. Nothing moves: the card sits 24 px to the right of the list, top-aligned, at the right gutter.

---

### What differs from Compass (element by element)

| Element | Compass | Today (`test-list.md`) | Direction B |
|---|---|---|---|
| Table frame | 1 px black frame, white sheet | 1 px BORDER_SUBTLE frame, PANEL sheet | **no frame, no sheet**: cards on the PAGE background |
| Header row | grey band with separators | HEADER band, 14 px / 600 INK | **floating labels**, 12 px / 600 TEXT_SECONDARY, no band; sort arrow ACCENT |
| Rows | 16 px tight lines, full grid | 40 px rows, full grid | **40 px cards 8 px apart**, radius 4, 1 px BORDER_SUBTLE edge, no grid lines |
| Row text | 12 px, bold = not run | 14 px INK | 14 px INK, Test Name only at weight 600 (a name, not a state) |
| Selected row | saturated blue, white text | ROW_SELECTED | ROW_SELECTED fill **+ 1 px ACCENT edge** |
| Hover row | none | none | ACCENT_SUBTLE fill |
| Button column | 7 loose boxes | 7 outlined boxes, Run Test filled | **one "Selected test" card** with a heading (test name + badge) and the 7 buttons full width inside |
| Button look | white box, bold centred text | outlined blue, 170 px | outlined blue, full card width (about 220 px), same tiers |
| Delete Test | plain box | outlined, red square glyph | unchanged |

### States

| State | Row card | Buttons |
|---|---|---|
| Normal | PANEL fill, BORDER_SUBTLE edge, INK text | secondary: ACCENT text, PANEL fill, ACCENT border · Run Test: white on ACCENT |
| Hover | ACCENT_SUBTLE fill, edge unchanged | ACCENT_SUBTLE fill (secondary) · ACCENT_HOVER (primary) |
| Selected | ROW_SELECTED fill, 1 px ACCENT edge, INK text; the card heading on the right repeats the name and badge | matrix as in `test-list.md` |
| Focus (keyboard) | 2 px ACCENT_FOCUS edge on the selected card, nothing moves | 2 px ACCENT_FOCUS border (existing) |
| Disabled | n/a | TEXT_DISABLED on DISABLED_FILL · Run Test: ACCENT_DISABLED_TEXT on ACCENT_DISABLED_FILL |
| No test selected | no card has the edge | heading "No test selected" in TEXT_SECONDARY; only Add New Test and Open Subject Folder on |
| Done / Not done / Ended early / Data missing | status badge, as today | View Report on only with data |

### Accessibility

- INK on PANEL 18.10:1 and on ROW_SELECTED 13.62:1; TEXT_SECONDARY on PAGE 7.10:1 (floating column labels, "No test selected"); ACCENT on PANEL 6.08:1 (secondary buttons, selected edge is non-text, 6.08:1); white on ACCENT 6.08:1; BORDER_SUBTLE on PAGE is decorative only (the card edge is not a cue: the selected card has the ACCENT edge and the fill).
- Targets: row cards 40 px tall, full list width; buttons 40 px tall and the full card width.
- Not colour-only: selection = fill + edge + the name repeated in the right card's heading (a third, textual cue, new in this direction); status = glyph + word; disabled = grey fill + grey text.
- The floating labels are still buttons for sorting; they show the ACCENT sort arrow and ACCENT_SUBTLE on hover so they are discoverable.

### Implementation cost (PySide6)

- **Table: a row delegate (custom painting), medium.** Keep `QTableWidget` (sorting, rename editor, Delete / F2 / Enter, selection all stay). `setShowGrid(False)`, viewport background PAGE, frame `NoFrame`, row height 48 (= TABLE_ROW_HEIGHT 40 + the 8 px gap, both tokens) and a `QStyledItemDelegate.paint` that draws, per row, a rounded PANEL rect from the first to the last column (rounded corners only on the outer cells, the 8 px gap left blank), then the text; ROW_SELECTED + ACCENT pen when selected, ACCENT_SUBTLE under the mouse (`QStyle.State_MouseOver`), 2 px ACCENT_FOCUS when the table has focus. The Status cell widget (`_BadgeCell`) keeps working. About 80-100 lines in `test_list_table.py`; `frozen_table.py` already shows the pattern of a delegate painting over cells.
- **Header: QSS only.** `QHeaderView::section` for the test table: PAGE fill, TYPE_CAPTION, TEXT_SECONDARY, no border.
- **Buttons: layout + QSS, low.** Wrap the column in a `QFrame#wtmhCard` with 24 px padding and 8 px spacing; add a `QLabel#wtmhSectionTitle` (name) and a `StatusBadge` on top, updated in `_update_buttons()` from `selected_test()`. No new assets.
- Tests: the phase-2 Test List tests that read widths, the table frame and the button geometry need updating; a new test for the heading text.

### Risk for operators who know Compass

- **Medium.** The list no longer looks like a grid, so the first impression is "a different app"; this is the strongest identity of the three. Sorting by the floating labels is less discoverable than a header band (mitigated by the sort arrow and hover). The "Selected test" heading reduces a known Compass confusion (why is View Report grey?) because the card says what is selected. The 8 px gaps cost height: 5 rows take 232 px instead of 200; a subject with 15+ tests scrolls a little sooner (the list already scrolls).
- Design-rule tension to confirm: proposal 2.4 gives tables radius 0 and cards radius 4. Here each row is drawn as a card (radius 4), which follows the card rule rather than the table rule; and 2.4 says "a card never holds a card": the right card holds buttons and a badge, not a card, so that holds.

> **Wireframe notes:** wiremd has no "table of cards", so the rows are separate `card` blocks and the first row sits in a `grid-2 card` with the "Selected test" card to keep the two columns side by side; in the real page all five rows align under the column labels and the right card is top-aligned next to the first row. The `|selected|` badge marks the selected card in the mockup only (the real cue is the ROW_SELECTED fill + ACCENT edge). The retint pass still uses the older teal palette; the token names in this file are the design-system values of `src/ui/design_tokens.py`.

---

[Back to Setup](#)

Changes are saved automatically.

> Footer, empty states ("Enter a Subject ID in Setup." / "No tests yet. Choose Add New Test." as one card in the list area), unreadable-file line, keyboard rules and all modals: unchanged, see `test-list.md`.
