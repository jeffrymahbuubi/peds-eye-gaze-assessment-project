![[_nav.md]]

## Start Grid Click 1

> SPEC-compass-task-flow.md 4C.2–4C.4. Opened by Run Test on the Test List, always (R2). The nav is locked here, as during a run. Compass reference: `docs/compass/screenshots/07a-*.png`.

::: alert warning
Still needed before you can start: The tracker is not connected. Connect it on the Setup page. · No calibration yet. Calibrate on the Setup page.
:::

[Go to Setup]{.outline}

> **Blocker banner:** shown only when something is missing (the list comes from `SetupPage.run_blockers()`). Start and Practice are disabled while it shows. It is checked again every second, because the tracker can drop. It is hidden when there is nothing to fix.

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

Start records 18 trials. Check that the bottom bar says "tracking OK" before you begin.

:::

> The numbers (0.8 seconds, 8 seconds, 18 trials) come from this test's own configuration. The "small dot" sentence appears only when the gaze cursor is on, and the "ring" sentence only when the progress ring is on. Each task has its own four steps (SPEC 4C.3). **The text is read to children and needs clinician review before release.**

::: row
[Start]{.outline} [Practice]{.outline} [Cancel]{.outline}
:::

> There is no default button, so Enter starts nothing. Esc = Cancel, which goes back to the Test List.

Practice finished: 3 of 3 selected. You can practice again or press Start.

> This line appears only after a practice. Practice always returns to this page and can be repeated. Each repeat uses a new seed, so its targets differ from the recorded run.

::: alert info
Help: From this screen you can begin the test. You may also practice 3 targets first; practice is not recorded. Read the instructions aloud to the child.
:::
