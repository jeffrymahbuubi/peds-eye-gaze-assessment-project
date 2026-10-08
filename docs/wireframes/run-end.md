![[_nav.md]]

## Run end: Test complete, Quit, Discard

> **Design system phase 1** (SPEC-design-system-phase1.md, proposal R5): the dialog heading reads "Test complete" (no exclamation mark) at 20 px; danger buttons keep the red fill; nothing else changes.

> SPEC-compass-task-flow.md 4C.6 and 4C.8 (U8, U14). All dialogs are modal over the frozen canvas. Every file is already written to disk before any dialog appears, so a crash at a dialog loses nothing (the test then simply stays Not Done). Compass reference: `docs/compass/screenshots/07b-*.png`.

### Flow

```
Recorded run finishes ──→ [Test complete] ──Save──────────────→ Test List (row "Done", locked)
                              │──Save and View Report──→ Report (Summary)
                              └──Discard Results──→ [Discard confirm] ──Discard──→ Test List (row stays Not Done)

Quit / Alt-Q / Esc ──→ [Quit the test?] ──Keep going──→ run resumes
                              └──Quit test──→ c > 0: [Save the c completed trials?] ──Save partial──→ Test List ("Ended early (c/N)")
                                                                                    └──Discard──→ folder deleted, row stays Not Done
                                              c = 0: "No trials were completed, so nothing was saved."
```

---

## Modals & Dialogs

> Not visible on page load.

::: modal

## Test complete

Test complete

[Save]{.outline} [Save and View Report]* [Discard Results]{variant:danger}

:::

> Close or Esc = Save, so the default is never destructive. "Save" marks the test Done (dated) and locks it, then returns to the Test List with the row selected.

::: modal

## Discard results

Discard these results? This cannot be undone.

[Discard]{variant:danger} [Keep]*

:::

> Discard deletes the run's session folder permanently (U14), after strict safety checks on the path. The test stays Not Done and can be configured and run again.

::: modal

## Quit the test?

Quit the test? 7 of 18 trials are done.

[Quit test]{variant:danger} [Keep going]*

:::

> The run is paused while this dialog shows. "Keep going" resumes, unless the operator had already paused. A practice run never shows this dialog.

::: modal

## Save partial results

Save the 7 completed trials?

[Save partial results]* [Discard results]{variant:danger}

:::

> This is already the second step of a confirmed quit, so Discard here has no extra confirmation. Close or Esc = Save partial. A partial save shows "Ended early (7/18)" on the Test List and locks the test.

::: modal

## Nothing saved

No trials were completed, so nothing was saved.

[OK]*

:::

> Shown when Quit is confirmed before any trial finished. The empty run is discarded automatically.
