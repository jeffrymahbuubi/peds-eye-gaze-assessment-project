# Brief for the Fable UI/UX evaluation

Written 2026-10-07 by the hub. Hand this file to a Fable session/agent as its task. The user's
goal: the app is usable but looks "AI-ish"; Fable evaluates the current UI/UX and then proposes a
design direction and concrete improvements. **Fable proposes; nothing is changed until the user
approves a SPEC written from the proposal** (project workflow: SPEC, wireframe gate, implementer).

## 1. Context to read first (in this order)

1. `docs/design/ai-ish-research.md`: the AI-ish tells (T1-T11) with sources, and candidate design systems.
2. `docs/design/current-design-inventory.md`: today's tokens, components, canvas theme and the screenshot index.
3. `docs/design/screenshots/*.png` + `16-report-pdf-grid.pdf`: the real app (01-20; the
   inventory's §5 says which were refreshed on 2026-10-08 and what the tree does not yet show).
4. `docs/wireframes/*.md`: every page's layout and wording (incl. pages not in the screenshots).
5. `src/ui/wtmh_theme.py`, `src/ui/canvas.py`, `configs/themes/forest.yaml`: the code behind the look.
6. For the clinical context: `docs/specs/SPEC-compass-task-flow.md` §1-§3 (why the flow is
   Compass-like), `docs/compass/synthesis/ui-ux-screen-walkthrough.md` (the Compass reference app).

## 2. Users and constraints

- **Clinician / operator** (therapist, physician, research assistant): runs Setup, manages each
  child's Test List, configures tests, starts runs, reads reports and prints PDFs. Often working
  next to a child, so attention is split: the UI must be scannable at a glance and hard to misuse.
- **Child with cerebral palsy** (the subject): sees only the task canvas. Selects targets by eye
  gaze (dwell) or gaze + switch. Needs large, high-contrast targets, low clutter, clear but calm
  feedback, nothing that pulls the gaze away from the task.
- **Per-test input (SPEC-input-selection-and-follow.md, built 2026-10-08):** Pointer = Gaze or
  Mouse, Selection = Dwell or Switch, chosen on the configuration page (screenshots 05, 17). The
  switch is a USB big button that sends a left mouse click; Space/Enter count too. With Switch the
  target glows while the pointer is on it (20); the dwell threshold and ring are greyed in place.
  A Mouse test needs no tracker: Setup lets the clinician continue without one (01) and the Start
  page shows a note instead of the blocker (19). The clinician reads the switch or mouse wording
  aloud (19). Follow the Target (no selection, pursuit metrics) is built but not yet merged, so
  the Follow pages (07, 08) still show Follow & Click; judge Follow's config page by
  `docs/wireframes/task-config.md` where they differ.
- Platform: PySide6 Qt Widgets, Windows, 1920x1080 @ 100 % is the standard (scaling is warned on
  Setup). Licence: research / non-commercial, so GPL widget libraries are allowed.
- Scope (user, 2026-10-07): **operator UI and task canvas**.
- Fixed behaviour that the redesign must keep: page flow (Setup, Test List, Configure, Start,
  run, Test Complete, Report), the data shown, keyboard shortcuts (Alt-P / Alt-Q / Esc / H),
  visual-angle target sizing, dwell/switch logic.

## 3. Task A: evaluate (deliver first)

For every screenshot / wireframe page, report:
- **AI-ish tells** present (T1-T11 from the research file), each with where it shows.
- **Usability findings** by severity (critical / major / minor), using Nielsen's heuristics and
  medical-software practice (colour only for meaning; unmistakable feedback; error prevention;
  scannability under split attention), with the screenshot and the region.
- **Canvas findings** for the child: target contrast and salience, distractors, feedback timing
  and intensity, cursor visibility; the Switch glow and instant ring together (20); the circular
  white ring on non-circular scanning shapes (20, square at top right in 06).
- **Accessibility:** contrast ratios of text and state colours (WCAG 2.2 AA), target sizes,
  keyboard focus visibility.

Score each page 1-5 on: hierarchy, density fit, consistency, distinctiveness (not AI-ish),
clinical clarity. Put the table in `docs/design/fable-evaluation.md`.

## 4. Task B: propose (after the user has read Task A)

- **Direction:** pick one design direction (e.g. Carbon-based clinical instrument, Fluent-based
  native Windows, NHS-style calm healthcare, or a justified mix) and say why for these two
  audiences. Show the trade-offs of the runners-up.
- **Design system v1** for this app: type scale, colour tokens with roles (incl. state and
  data-viz colours for the report maps), spacing scale, radius/elevation rules, component
  rules (buttons, tables, forms, alerts, banners, badges, dialogs, run bar), canvas rules
  (target / cue / feedback / cursor colours per theme).
- **Concrete changes per page**, ranked by impact and effort, each mapped to the token or
  component rule it applies. Note anything that needs a wireframe change.
- **Implementation path in Qt:** QSS token port vs. a widget library (licence + effort), and
  which files change (`wtmh_theme.py`, `dialog_theme.py`, `canvas.py`, themes YAML,
  `report_pdf.py`).
Put it in `docs/design/fable-proposal.md`. Do not edit `src/` or the SPECs.

## 5. Rules

- Cite the screenshot file for every finding.
- Prefer measured statements (contrast ratio, px, count) to taste.
- No new features; this is the look and the UX of existing features.
- Language of the docs: English, plain, short sentences.
