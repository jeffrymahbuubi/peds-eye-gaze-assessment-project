![[_nav.md]]

## Test List for TESTING

> SPEC-compass-task-flow.md 4A.4. Replaces the old Tasks tab (`tasks.md`, superseded). The list is per subject and is read from disk every time this tab opens, so it is the same after an app restart. Compass reference: `docs/compass/screenshots/05-test-list.png`.

::: grid-2

### Tests

| Test Name | Task | Configuration | Status | Date Complete |
|---|---|---|---|---|
| **Grid Click 1** | **Grid Click** | **Standard** | **Not Done** | **—** |
| Static Click 1 | Static Click | Standard | Done | 2026-10-06 |
| Follow & Click 1 | Follow & Click | Slow path | Ended early (4/6) | 2026-10-06 |
| Scanning Search 1 | Scanning Search | Standard | Done · data missing | 2026-10-05 |
| **Grid Click 2** | **Grid Click** | **Large targets** | **Not Done** | **—** |

### {.right}

[Add New Test]{.outline}

[Configure Test]{.outline}

[Run Test]*

[View Report]{state:disabled}

[Copy Test]{.outline}

[Delete Test]{.outline}

:::

> **Selected row:** "Grid Click 1" (Not Done). The buttons on the right follow the matrix below. Disabled buttons stay visible and grey, never hidden.

| Selected | Add New Test | Configure Test | Run Test | View Report | Copy Test | Delete Test |
|---|---|---|---|---|---|---|
| nothing | on | off | off | off | off | off |
| Not Done | on | on | on | off | on | on |
| Done | on | off | off | on | on | on |
| Ended early | on | off | off | on | on | on |

> **Run Test is never disabled by Setup (R2).** It always opens the Start page, which lists anything still missing (tracker, calibration, ...) and disables Start/Practice there. View Report is off when the data folder is missing ("· data missing").

> **Table rules:**
> - Bold = not yet run.
> - Clicking a header sorts the table. Test Name sorts naturally, so "Grid Click 2" comes before "Grid Click 10".
> - The selection follows the test through a sort or reload.

> **Keyboard:**
> - Delete = Delete Test.
> - F2 or a double-click on Test Name = rename in place. This works in every state, including Done.
> - Enter or a double-click on another cell = Run Test (Not Done) or View Report (Done / Ended early).

---

[← Back to Setup / recalibrate](#)

Changes are saved automatically.

---

### Other states

::: card

**No Subject ID typed** (reached through the nav without Continue)

Enter a Subject ID in Setup.

> Table replaced by this line; every button is off; nothing is created on disk.

:::

::: card

**Subject with no tests yet**

No tests yet. Choose Add New Test.

:::

::: card

**Unreadable test file** (muted line under the table)

1 test file(s) could not be read and are hidden: sessions/_tests/TESTING

:::

---

## Modals & Dialogs

> Not visible on page load.

::: modal

## Add New Test

**Static Click**
One still target on an empty field — baseline look-and-select.

**Grid Click**
One cell of a visible board lights up — selection among candidates.

**Follow & Click**
The target travels; select it while it moves — smooth pursuit.

**Scanning Search**
Find the cued shape in a field of distractors — visual search.

How many
[1______]{type:number}

[Add]* [Cancel]

:::

> Add creates the tests with default names ("Grid Click 3", ...) at Standard settings, each with its own random seed, then selects the last one. A double-click on a task adds one. Nothing opens by itself.

::: modal

## Delete Test

Delete 'Static Click 1' from this list? Its recorded data in the sessions folder is kept.

[Delete]{variant:danger} [Keep]*

:::

> Cancel ("Keep") is the default button. The record moves to `_tests/SUBJECT/_deleted/`; session folders are never touched.

::: modal

## Rename (in place, F2)

Test Name
[Grid Click 1_______________________]

Another test of this subject already uses this name.

:::

> Names: 1–60 characters, unique per subject ignoring case and extra spaces (R10). The error text shows inline; Esc cancels.

> **Copy Test** (no dialog): a new unrun row is appended and selected. It has the same task, configuration and evaluator, a new random seed and empty notes. Its name is "Grid Click 3", or "Custom name (copy)" for a custom name.
