![[_nav.md]]

## Test List for TESTING — Direction C "Signal"

> **Alternative C of 3** (Hsieh's feedback 2026-10-22). **Look only**: same elements, same order, same positions, same workflow as `test-list.md`. **Design system unchanged**: uses tokens PANEL, PAGE, INK, TEXT_SECONDARY, TEXT_DISABLED, HEADER, BORDER_SUBTLE, ROW_SELECTED, ACCENT, ACCENT_HOVER, ACCENT_SUBTLE, ACCENT_FOCUS, ACCENT_DISABLED_FILL, ACCENT_DISABLED_TEXT, DISABLED_FILL, DANGER, SUCCESS_TEXT, WARNING_TEXT, TYPE_BODY, TYPE_CAPTION, RADIUS, TABLE_ROW_HEIGHT, BUTTON_HEIGHT, the existing button tiers, the status badge and the painted-glyph vocabulary of `glyphs.py`. No new token, colour, font, size or radius. **New assets, flagged:** eleven small painted glyphs (seven action glyphs for the buttons, four task glyphs for the Task column), drawn with QPainter in the same way as the existing state glyphs, coloured only with existing tokens.

> **One-line idea:** keep the grid Compass operators know, but give every row and every button a **signal**: a glyph. Task cells get a task glyph, the Status badge stays, and each right-side button carries a 12 px action glyph before its label, left-aligned, so the column reads as a toolbar rather than a stack of text boxes.

::: grid-2

### Tests

| Test Name | Task | Configuration | Status | Date Complete |
|---|---|---|---|---|
| Grid Click 1 | ▦ Grid Click | Standard | ○ Not done | — |
| Static Click 1 | ◎ Static Click | Standard | ● Done | 2026-10-06 |
| Follow the Target 1 | ➚ Follow the Target | Slow path | ◐ Ended early 4/6 | 2026-10-06 |
| Scanning Search 1 | ⌕ Scanning Search | Standard | ▲ Data missing | 2026-10-05 |
| Grid Click 2 | ▦ Grid Click | Large targets | ○ Not done | — |

### {.right}

[＋ Add New Test]{.outline}

[⚙ Configure Test]{.outline}

[▶ Run Test]*

[▤ View Report]{.outline state:disabled}

[⧉ Copy Test]{.outline}

[■ Delete Test]{.outline}

[▭ Open Subject Folder]{.outline}

:::

> **Table:** the HEADER band, the 40 px rows and the BORDER_SUBTLE grid stay as today (this direction keeps the Compass grid on purpose). What changes: the **Task cell** shows a 12 px task glyph in ACCENT before the name (one shape per task type: a dot in a ring for Static Click, a 3 × 3 block for Grid Click, an arrow path for Follow the Target, a magnifier for Scanning Search), the **Status badge** stays glyph + word, and the **Date** column is right-aligned with tabular figures. Selected row ROW_SELECTED; hover ACCENT_SUBTLE.

> **Buttons:** the existing tiers and order; every button gets a **12 px action glyph** in a fixed 24 px slot at the left and a **left-aligned label** (today: centred text, no glyph). Glyph colours are the tier's text colour: ACCENT on a secondary button, white on the primary Run Test, TEXT_DISABLED when disabled; Delete Test keeps the existing red square (DANGER) and is the only button whose glyph differs in colour from its label. Glyph shapes: plus (Add), sliders (Configure), play triangle (Run), document (View Report), two overlapping squares (Copy), the existing danger square (Delete), folder (Open Subject Folder). The mockup uses Unicode stand-ins; the real glyphs are painted pixmaps like the status glyphs, so they cannot fall back to a missing font character.

> **Selected row:** "Grid Click 1" (Not done). Button matrix as in `test-list.md`; disabled buttons stay visible with TEXT_DISABLED text and glyph on DISABLED_FILL.

---

### What differs from Compass (element by element)

| Element | Compass | Today (`test-list.md`) | Direction C |
|---|---|---|---|
| Header row | grey band | HEADER band, 14 px / 600 INK | unchanged (kept on purpose), sort arrow ACCENT |
| Grid lines | full grid | full grid, BORDER_SUBTLE | unchanged |
| Task cell | plain text ("Pointing") | plain text | **task glyph (ACCENT) + text** |
| Status | plain text, bold = not run | status badge | status badge (unchanged) |
| Date | plain text | plain text | right-aligned, tabular figures |
| Selected row | saturated blue, white text | ROW_SELECTED | ROW_SELECTED (unchanged) |
| Hover row | none | none | ACCENT_SUBTLE |
| Button column | text-only boxes, centred bold | outlined blue, centred, 170 px | **glyph + left-aligned label**, outlined blue, 170 px (or wider for the longest label) |
| Run Test | same box as the others | primary filled | primary filled with a white play glyph |
| Delete Test | plain box | red square glyph + centred text | red square glyph in the glyph slot + left-aligned text |

### States

| State | Row | Button |
|---|---|---|
| Normal | PANEL, INK text, task glyph ACCENT | secondary: ACCENT glyph + ACCENT text on PANEL, ACCENT border · Run Test: white glyph + white text on ACCENT |
| Hover | ACCENT_SUBTLE fill | ACCENT_SUBTLE (secondary) · ACCENT_HOVER (primary) |
| Selected / pressed | ROW_SELECTED, INK text, glyph stays ACCENT (6.08:1 on PANEL; on ROW_SELECTED 4.58:1, non-text) | pressed = hover |
| Focus (keyboard) | table: 2 px ACCENT_FOCUS border (existing) | 2 px ACCENT_FOCUS border (existing) |
| Disabled | n/a | TEXT_DISABLED glyph + text on DISABLED_FILL · Run Test: ACCENT_DISABLED_TEXT glyph + text on ACCENT_DISABLED_FILL · Delete Test: the square turns TEXT_DISABLED (existing `glyph_icon` disabled mode) |
| Done / Not done / Ended early / Data missing | status badge | View Report on only with data |

### Accessibility

- Text contrast unchanged from today: INK on PANEL 18.10:1, INK on HEADER 13.71:1, INK on ROW_SELECTED 13.62:1, ACCENT on PANEL 6.08:1, white on ACCENT 6.08:1, TEXT_DISABLED on DISABLED_FILL 3.81:1 (disabled, exempt).
- Glyphs are non-text marks (3:1 needed): ACCENT on PANEL 6.08:1, ACCENT on ACCENT_SUBTLE 5.17:1, white on ACCENT 6.08:1, DANGER on PANEL 5.00:1. The ACCENT task glyph on ROW_SELECTED is 4.58:1 (computed from the tokens; not a row of CONTRAST_PAIRS yet, so the implementer adds it).
- Not colour-only: every glyph sits next to its word (task name, button label, status word); the glyphs add a second channel and never replace text. Disabled = grey fill + grey text + grey glyph.
- Targets unchanged: 40 px rows, 40 px buttons at least 170 px wide.
- Tooltips on the task glyphs are not needed (the word is beside the glyph).

### Implementation cost (PySide6)

- **Table: small painting + QSS.** A `QIcon` on each Task item (`QTableWidgetItem.setIcon`, from a new `task_glyph_pixmap()` beside `glyph_pixmap()` in `glyphs.py`; Qt draws item icons natively, no delegate) with `setIconSize(QSize(12, 12))`; an item-hover rule with the ACCENT_SUBTLE fill; right-aligned tabular Date via `setTextAlignment` and the tabular-figures font `frozen_table.table_fonts()` already builds. Four new glyph drawings (about 60 lines), unit-tested like the existing seven.
- **Buttons: assets + QSS, low.** `setIcon(glyph_icon(shape, ACCENT, TEXT_DISABLED))` on the six secondary buttons (the pattern `delete_button` already uses) and a white/ACCENT_DISABLED_TEXT icon on Run Test; `text-align: left; padding-left: 12px` in the test-list button rules; `setIconSize(QSize(12, 12))`. Seven new action glyphs in `glyphs.py` (about 90 lines). Optional: `QIcon.Mode.Active` is not needed because hover keeps the glyph colour.
- Tests: glyph drawing tests (one per new shape), the button-tier tests unchanged, a test that each button has an icon.
- **Flag for the SPEC writer:** this is the only direction that adds assets (painted glyphs, no PNG files). They use existing tokens only, but they extend the glyph vocabulary of proposal 2.5 (today: state shapes only) with action and task shapes. The hub should confirm that is "icons", not "a design-system change".

### Risk for operators who know Compass

- **Lowest.** The grid, header, labels, order, widths and the greyed-out matrix are unchanged, so nothing has to be relearned; the glyphs only speed up scanning. The identity shift is real but modest: a toolbar of glyph + label buttons and task glyphs in the list are things Compass does not have, while the screen still reads as "the test list".
- Possible objection: eleven glyphs is a lot of new drawing to keep crisp at 100 / 125 / 150 % scaling (the existing `glyph_pixmap` handles `dpr`, so the mechanism exists). If the glyph set is cut, keep the seven button glyphs and drop the four task glyphs: the buttons carry most of the identity.

> **Wireframe notes:** the glyphs in the mockup (＋ ⚙ ▶ ▤ ⧉ ■ ▭, ▦ ◎ ➚ ⌕) are Unicode stand-ins for painted 12 px pixmaps; their exact drawings are the implementer's, at the stroke weight of `glyphs.py` (1.5 px at 12 px). wiremd centres button text, the real buttons are left-aligned with the glyph in a 24 px slot. The retint pass still uses the older teal palette; the token names in this file are the design-system values of `src/ui/design_tokens.py`.

---

[Back to Setup](#)

Changes are saved automatically.

> Footer, empty states, unreadable-file line, keyboard rules and all modals: unchanged, see `test-list.md`.
