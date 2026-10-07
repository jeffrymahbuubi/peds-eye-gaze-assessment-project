# docs/design: UI/UX design material

| File | Purpose |
|---|---|
| `ai-ish-research.md` | What makes a UI look AI-generated (tells T1-T11, with sources) and design systems that fit clinical desktop software |
| `current-design-inventory.md` | Today's informal design system: tokens, components, canvas theme, screenshot index |
| `fable-brief.md` | Task brief for the Fable UI/UX evaluation (Task A) and proposal (Task B) |
| `screenshots/` | Real-app captures of every page, 1920x1080 @ 100 % (2026-10-08; 01-20, see the inventory's §5 for which set each comes from) |
| `fable-evaluation.md`, `fable-proposal.md` | Fable's Task A evaluation and Task B proposal (accent changed to the WTMH logo blue by user decision, 2026-10-08, §2.2) |
| `design-system.html` | Visual reference page for the proposal's design system v1: token swatches with contrast ratios, type, spacing, live components, canvas, copy rules, phases. Opens from disk; also published as a private claude.ai artifact |

Wireframes (layout and wording) stay in `docs/wireframes/`.

## Refresh the kit before running Fable

The kit reflects the tree at commit **`c300411`** (refreshed 2026-10-08; the first set was taken
at `64692b3`, but before step 2 of SPEC-input-selection-and-follow.md had been applied to the
main tree, so pages 01/05/07/09 were re-captured and 17-20 added). Before a Fable run, check what
changed since then and refresh only what is affected:

1. `git diff --stat c300411 -- src/ui src/tasks src/data/report_*.py configs/themes docs/wireframes docs/specs`
   (also compare the screenshot timestamps with the commit times: a capture taken while a step
   still sat in a worktree predates code that the baseline commit already contains)
2. **Pages whose look or content changed** (e.g. the Input card, the Dwell card and Glow from
   SPEC-input-selection-and-follow.md; Follow the Target canvas and report; the Setup folder choice
   from SPEC-subject-data-layout.md): re-capture them.
   - Launch: `$env:QT_MCP_PROBE="1"; $env:QT_MCP_PORT="9142"; ..\.venv\Scripts\python.exe tools\qa\qa_harness.py`
     (deferred clicks, so modal dialogs can be driven by qt-mcp).
   - Capture: `tools\qa\capture_window.ps1 <NN-name>` (OS PrintWindow of the app window, safe if
     the user switches windows; a dialog: pass its title as the second argument; if `FindWindow`
     misses the dialog, enumerate the process's windows and PrintWindow the handle directly).
   - A canvas state that needs the mouse on the target (glow, rings): poll PrintWindow captures
     for the target colour at the known shape centres, `SetCursorPos` there, capture again (the
     maximized window's client area starts 8 px inside the capture).
   - Use a throwaway subject (e.g. `DESIGNQA`) and delete `sessions/_tests/DESIGNQA` and
     `sessions/_settings/DESIGNQA` (named configurations) afterwards; real reports come from an
     existing subject (e.g. P9REAL). Preview and Practice need no tracker.
   - Keep the file numbering; add new pages at the end (`17-…`).
3. `current-design-inventory.md`: update the tokens table if `wtmh_theme.py` changed, the
   component list, the canvas section, and the screenshot index + date; replace the "Note: these
   screenshots predate…" line.
4. `ai-ish-research.md`: re-score the "How this app scores today" table only if styling changed.
5. `fable-brief.md`: add any new page or constraint (e.g. switch users, Mouse tests) to §2/§3.
6. Write the new baseline commit here in place of `c300411`.
