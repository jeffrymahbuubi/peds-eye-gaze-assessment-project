# docs/design: UI/UX design material

| File | Purpose |
|---|---|
| `ai-ish-research.md` | What makes a UI look AI-generated (tells T1-T11, with sources) and design systems that fit clinical desktop software |
| `current-design-inventory.md` | Today's informal design system: tokens, components, canvas theme, screenshot index |
| `fable-brief.md` | Task brief for the Fable UI/UX evaluation (Task A) and proposal (Task B) |
| `screenshots/` | Real-app captures of every page, 1920x1080 @ 100 % (2026-10-08) |
| `fable-evaluation.md`, `fable-proposal.md` | Written later by Fable |

Wireframes (layout and wording) stay in `docs/wireframes/`.

## Refresh the kit before running Fable

The kit was captured at commit **`64692b3`** (2026-10-08). Before a Fable run, check what changed
since then and refresh only what is affected:

1. `git diff --stat 64692b3 -- src/ui src/tasks src/data/report_*.py configs/themes docs/wireframes docs/specs`
2. **Pages whose look or content changed** (e.g. the Input card, the Dwell card and Glow from
   SPEC-input-selection-and-follow.md; Follow the Target canvas and report; the Setup folder choice
   from SPEC-subject-data-layout.md): re-capture them.
   - Launch: `$env:QT_MCP_PROBE="1"; $env:QT_MCP_PORT="9142"; ..\.venv\Scripts\python.exe tools\qa\qa_harness.py`
     (deferred clicks, so modal dialogs can be driven by qt-mcp).
   - Capture: `tools\qa\capture_window.ps1 <NN-name>` (OS PrintWindow of the app window, safe if
     the user switches windows; a dialog: pass its title as the second argument).
   - Use a throwaway subject (e.g. `DESIGNQA`) and delete `sessions/_tests/DESIGNQA` afterwards;
     real reports come from an existing subject (e.g. P9REAL). Preview needs no tracker.
   - Keep the file numbering; add new pages at the end (`17-…`).
3. `current-design-inventory.md`: update the tokens table if `wtmh_theme.py` changed, the
   component list, the canvas section, and the screenshot index + date; replace the "Note: these
   screenshots predate…" line.
4. `ai-ish-research.md`: re-score the "How this app scores today" table only if styling changed.
5. `fable-brief.md`: add any new page or constraint (e.g. switch users, Mouse tests) to §2/§3.
6. Write the new baseline commit here in place of `64692b3`.
