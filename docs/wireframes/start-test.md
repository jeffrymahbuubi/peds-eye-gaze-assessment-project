![[_nav.md]]

## Start Grid Click 1

> SPEC-compass-task-flow.md 4C.2–4C.4. Opened by Run Test on the Test List, always (R2). The nav is locked here, as during a run. Compass reference: `docs/compass/screenshots/07a-*.png`.

::: alert error
■ Blocked:

The tracker is not connected (Setup page).

No calibration yet (Setup page).

[Go to Setup]{.outline}

:::

> **Design system phase 2** (SPEC-design-system-phase2.md H7): the blocker is a danger alert box, 1200 px wide: a ■ glyph tile, the bold word "Blocked:", then **one missing item per line** at 16 px, and Go to Setup as a secondary button inside the alert at its right edge. No interpunct chain, no amber tint, no left stripe.

> **Blocker banner:** shown only when something is missing (the list comes from `SetupPage.run_blockers()`). Start and Practice are disabled while it shows. It is checked again every second, because the tracker can drop. It is hidden when there is nothing to fix.

::: alert error
■ Blocked: The data folder path is too long. Move the program folder closer to the drive root.
:::

> A separate danger alert box, without Go to Setup (phase 2 H7).

> **Path blocker** (SPEC-subject-data-layout.md H9): before a recorded run, the app works out the longest path the run will write (run files and the PDF). Over 240 characters, this line shows and **Start** is disabled. **Practice stays enabled**, because practice writes nothing. Checked when the page opens; a path cannot change while it is open. With today's layout it appears only when the program folder itself is about 130+ characters deep.

::: alert info
ⓘ Note: Mouse test. The tracker is not connected, so no eye data will be recorded.
:::

> **Mouse note** (SPEC-input-selection-and-follow.md H5, added 2026-10-07): shown only for a test with Pointer = Mouse, in place of the blocker banner. A Mouse test needs no tracker or calibration, so Start and Practice stay enabled. With the tracker connected (and calibrated) the line reads "Mouse test. Eye data will be recorded alongside." A Gaze test keeps the blocker banner above, unchanged.

::: card

### Read aloud to the child

**Instructions for the Grid Click test:**

1. The small dot on the screen shows where you are looking. A board of squares will appear on the screen.
2. One square will light up.
3. Look at the lit square and keep looking at it for about 0.8 seconds. A ring will fill up around it.
4. When it is selected, another square will light up. Continue until no more squares light up.

NOTE: If the square is not selected within 8 seconds, the next square will light up.

---

### For the clinician (not read aloud)

To pause the test: click the "Pause" button, or press ALT-P. To quit the test: click the "Quit" button, or press ALT-Q.

Practice runs 3 targets with these settings. Nothing is recorded. Repeat it as often as needed.

Start records 18 trials. Check that the bottom bar shows "Tracking OK" before you begin.

:::

> The numbers (0.8 seconds, 8 seconds, 18 trials) come from this test's own configuration. The "small dot" sentence appears only when the gaze cursor is on, and the "ring" sentence only when the progress ring is on. Each task has its own four steps (SPEC 4C.3). **The text is read to children and needs clinician review before release.**

> **Proposed read-aloud wording for the new input choices** (SPEC-input-selection-and-follow.md; proposal, to be confirmed at the wireframe gate):
> - **Selection = Switch**, step 3: "Look at the lit square, then press the button. The square glows while you are looking at it." (replaces the dwell/ring sentence; the "glows" part only when "Glow on target" is on)
> - **Pointer = Mouse**: step 1 becomes "Move the mouse to point at the screen." and "look at" becomes "point at" in the following steps.
> - **Follow the Target**: "1. A circle will appear and start to move across the screen. 2. Follow the moving circle with your eyes and keep looking at it while it moves. 3. The circle glows while you are looking at it. 4. After about 10 seconds a new circle will appear. Continue until no more circles appear." No NOTE line (nothing to select, so no timeout). 10 = this test's trial duration; the "glows" step only when "Glow on target" is on.

::: row
[Start]*{state:disabled} [Practice]{.outline} [Cancel]{.secondary}
:::

> **Button tiers** (phase 2 H7): Start is always the primary (filled) button, a disabled primary while blocked, so it never changes tier with state; Practice secondary (outlined); Cancel tertiary (text only). The row sits directly under the card, left-aligned at the content edge. The card is 1200 px: the read-aloud block at 16 px on white, the clinician block at 14 px on the page.

> There is no default button, so Enter starts nothing. Esc = Cancel, which goes back to the Test List.

Practice finished: 3 of 3 selected. You can practice again or press Start.

> This line appears only after a practice. Practice always returns to this page and can be repeated. Each repeat uses a new seed, so its targets differ from the recorded run.

::: alert info
ⓘ Note: From this screen you can begin the test. Read the instructions aloud to the child.
:::

> "Practice runs 3 targets" is said once, in the clinician block (phase 2 H7, proposal P5).
