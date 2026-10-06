---
title: "Compass 3.0.1 — Live Verification of the UI (2026-10-06)"
derived_from:
  - the installed Compass 3.0.1 (Windows 11, 1920x1080 at 100 %), driven and read on 2026-10-06
  - screenshots/09-*.png to screenshots/31-*.png (captured in that session)
  - Java Access Bridge control-tree dumps (kept outside the repo, see Method)
built: 2026-10-06
fidelity: >
  "Live" = read off the running app in this session, from a screenshot in screenshots/ or a
  control-tree dump. "Guide" = cites a heading in sources/compass-user-guide.md. Nothing is
  inferred beyond what an image or dump shows; anything not seen is marked "not captured".
---

# Compass 3.0.1 — Live Verification

## Purpose

[`ui-ux-patterns.md`](ui-ux-patterns.md) was written from the guide alone, and
[`ui-ux-screen-walkthrough.md`](ui-ux-screen-walkthrough.md) from 12 user screenshots of one Aim
run plus the guide. Both left questions open: guide-only screens, defaults the guide does not
state, and places where the guide and the screenshots disagree.

This file records what the real installed app showed when it was driven on 2026-10-06. It has
six parts:

- (a) corrections to the guide and to the two earlier files;
- (b) screens and dialogs documented for the first time;
- (c) the shipped configuration defaults of all eight tests;
- (d) the Start-screen instruction text of all eight tests;
- (e) what the results table averages over, checked with a run that had misses;
- (f) what is still unverified.

## Method

- **App:** Compass 3.0.1, maximised, on Windows 11 at 1920x1080, 100 % scaling.
- **Reading the controls:** Java Access Bridge was switched on for the user with
  `jabswitch -enable`. (Compass's bundled JDK 11 ignores `jre\lib\accessibility.properties`,
  which is the Java 8 location.) A .NET probe (JavaAutoNet) then read each screen's control
  tree: labels, check/radio state (`checked`), enabled state, text-field values and screen
  coordinates. The dumps are named `config-<test>`, `start-<test>`, `report-summary`,
  `dlg-setcolors` and `multi-report`. They are kept in the session scratchpad, **not in the
  repo**; the screenshots in this folder show the same screens.
- **Driving the app:** mouse clicks at the coordinates the bridge reported.
- **Data:** a throwaway client "Probe JabTest" (file `JabTestProbe.cms`), evaluator
  "QA Evaluator", comment "Automated evidence session 2026-10-06 not a real client". Not
  clinical data.
- **Limits of the bridge:**
  - The HTML instruction panes (Welcome, Start screens) come back empty, so their text was
    transcribed from the screenshots.
  - Combo-box values (Test Language, Scan Layout, Letter List, Word List and so on) are not
    exposed; they were read from the screenshots.
- Whitespace in transcribed text is normalised to single spaces; wording, case and punctuation
  are as shown.

---

## (a) Corrections

| # | Claim | Where | What the real app does | Evidence |
|---|---|---|---|---|
| 1 | The menubar cannot be seen in any screenshot | walkthrough intro | A **File / Edit / Tools / Help** menubar is on every main screen | `10`…`30` (any full-window shot); every JAB dump has a `menu bar` |
| 2 | The help bar is visible on three screens only | walkthrough intro, §2 | The yellow-bordered "Help:" bar is on **every** screen, including Welcome, and its text follows the control under the mouse or focus | `10-preferences.png` (Welcome), `11`, `13`, `14`, `15-*`, `16-*`, `21`, `22`, `30` |
| 3 | The Open dialog starts in My Documents, on the `.cms` filter | Guide *Open an Existing Client*; walkthrough §3.4 | It opens in the **last-used folder**, pre-fills the **last client's file name**, and **Files of type = "All Files"** | `12-open-dialog.png` |
| 4 | Save As (new client) saves in My Documents | Guide *How Compass Stores Client Information* | **Save in = last-used folder**; Files of type = "All Files"; default name `JabTestProbe.cms` (last + first name, as the guide says) | `11-save-as-new-client.png` |
| 5 | File dialogs are "standard OS" dialogs | walkthrough §3.4; patterns §8 | They are Java (Swing) file choosers drawn in the Windows look: places bar (Recent Items, Desktop, Documents, This PC, Network), Up / New Folder / View menu icons | `11`, `12` |
| 6 | The only separate windows are the file dialog and "Test Complete" | walkthrough §2 | Practice, a recorded run and Preview Test each open a **separate full-screen window titled with the test name** ("Aim 1", "Drag 1"). The Multi-Test Report is also a separate window | `20-practice-run.png`, `25-preview-drag.png`, `27-multi-report-p1.png` |
| 7 | Target Map marks look like bars, not circles | walkthrough §3.10 | The map box is about 1285 x 130 px (about 10:1) and the legend says "Green circles", so the circles are squashed into flat bars by the aspect ratio. Misses are red X; marks near the top edge are clipped | `21-summary-with-misses.png`, `21b-target-map-zoom.png` |
| 8 | The Start screen's Cancel is not in the guide | walkthrough §3.8 | **Start / Practice / Cancel** on all eight Start screens | `16-start-*.png`; dumps `start-*` |
| 9 | Trial extensions: email compass@kpronline.com | Guide *Trial Period and Registration* | The dialog says "For a trial extension, contact support@kpronline.com." | `09-register-dialog.png` |
| 10 | Menu, Letter, Word, Sentence button is "Text Style…" | Guide, each configuration section; patterns §3 | The label is **"Change Text Style..."** (Scan's is "Change Item Style...", as the guide says) | `15-config-menu/letter/word/sentence.png` |
| 11 | Scan Initiation default is Automatic | Guide *Scan Test Configuration*; patterns §4 | The Standard configuration shows **Manual** | `15-config-scan.png` |
| 12 | Scan Layout default is "Row/column Frequency (EARDF)" | Guide *Scan Test Configuration › Scan Layout*; patterns §4 | The combo shows **"Row-column Frequency 1"**. Whether this is the EARDF layout under another name was not checked (the list was not opened) | `15-config-scan.png` |
| 13 | Switch pause default is constant 1 s | patterns §4 (the guide gives both defaults without saying which mode is selected) | **Random** is selected, Min Pause 1, Max Pause 4 | `15-config-switch.png`; dump `config-switch` |
| 14 | Word List default "Set.2" | Guide *Word Test Configuration › Word List* | The combo shows **"Word Set 2"** | `15-config-word.png` |
| 15 | Drag trials / max time / pause "not stated" | patterns §4 | 12 trials, 30 s, 1 s, plus the full set in (c) | `15-config-drag.png`; dump `config-drag` |
| 16 | Edit Client Information buttons are "Save and Continue" / Cancel | Guide *Edit Client Information*; walkthrough §4 | **"Save & Continue"** / **"Cancel"**. It is a full screen, not a dialog | `30-edit-client-info.png` |
| 17 | After Quit: an option to save the partial data or discard | Guide *Running Tests* | Two dialogs: "Quit Test" (OK / Cancel), then a dialog titled **"Test Complete"** reading "Test Complete!" with only **Save Partial Results / Discard Results**. While they are open the Pause button reads **"Re-Start (Alt-P)"** | `23-quit-confirm.png`, `24-quit-save-partial.png` |
| 18 | Select Regions: at least one region must stay selected | Guide *Aim Test Configuration › Target Location* | Opened from a Standard (Percentage) configuration, **all six regions are unshaded**. Whether OK is refused with none shaded was not tested | `18-select-regions.png` |
| 19 | The multi-test speed graph shows "the average time the user required to select the targets" | report text itself; Guide *Multi-Test Reports* | The plotted Trial Time is the **All Aim Trials** mean, which **includes timed-out trials** (Aim 1: 2.13 s, not the 1.25 s of selected trials). See (e) | `27-multi-report-p1.png`, `27-multi-report-p3.png`, `21-summary-with-misses.png` |
| 20 | Multi-Test Report buttons: Previous / Next / Print / Save / Close | Guide *Multi-Test Reports* | Toolbar **Save / Print / Previous / "Page: n of 4" / Next / Close Report**; Previous is grey on page 1, Next grey on page 4 | `27-multi-report-p1.png`, `27-multi-report-p4.png` |

---

## (b) Newly documented screens and dialogs

### Registration — `09-register-dialog.png`
- Title "Register Compass 3.0".
- Row 1: **Free Trial** button, then "There are 29 days left in your free trial."
- Row 2: **Register...** button, then "Enter license code to receive unlimited use."
- Footer: "To purchase Compass 3.0, please visit www.kpronline.com. For a trial extension,
  contact support@kpronline.com."
- It appeared on every launch during the trial (hub notes). The Register... form (name, email,
  licence code per the guide) was not opened: **not captured**.

### Menubar (from the dumps and hub notes)
| Menu | Items |
|---|---|
| File | New Client, Open Client..., Save, Save As..., Print Report..., Exit |
| Edit | Cut, Copy, Paste |
| Tools | Edit Client Information..., Preferences... |
| Help | Compass Help, Overview, About |

- On Welcome, Save, Save As, Print Report and Edit Client Information are disabled.
- On the Test List, Save, Save As and Edit Client Information are enabled; Print Report is
  disabled.
- A hidden dialog "Quick Intro to Compass" exists in the tree (probably Help › Overview); it was
  not opened.

### Preferences — `10-preferences.png`
- Title "Compass Preferences". Two check boxes on **one row**, both **checked** by default:
  "Show welcome screen when Compass starts" and "Show tooltips". **OK / Cancel**.

### Save As / Open — `11-save-as-new-client.png`, `12-open-dialog.png`
- Save As: title "Save As", Save in = last-used folder, file name pre-selected
  (`JabTestProbe.cms`), Files of type "All Files", **Save / Cancel**. Help bar under it: "Help:
  Click to save new client information to a file and continue to the next step."
- Open: title "Choose a Client to Open", Look in = last-used folder (`compassclient`), file name
  pre-filled with the last client, Files of type "All Files", **Open / Cancel**.

### Choose Skill Test(s), several tests — `13-choose-tests-multiple.png`
- Double-click adds a test. Adding Aim twice gives "Aim 1" and "Aim 2". Rows are in the order
  added. "<< Remove Test" stays grey until a row in Tests to Add is selected.
- The help bar describes the test under the cursor: "Help: The Word test asks the user to copy
  a series of single words. Individual words are presented one at a time."

### Test List states — `14-test-list-states.png`
- Not-run rows are **bold**; run rows are regular weight. Date Complete reads "Oct 6, 2026" (no
  time) for a run test, "Not Done" otherwise.
- **A test saved after Quit looks exactly like a complete one** (Aim 2: date only, no marker).
- Button state, one not-run test selected (Aim 3): Add New Test, Configure Test, Run Test, Copy
  Test, Delete Test enabled; View Report and Multi-Test Report grey.
- One run test selected (hub notes): Configure Test and Run Test grey; View Report, Copy Test,
  Delete Test enabled.
- Two run Aim tests selected (Ctrl-click, `26-multi-evaluator-prompt.png` background): Add New
  Test, Multi-Test Report, Delete Test enabled; Configure, Run, View Report and **Copy Test** grey.
- **Save Client File** is grey right after a save and turns enabled after Copy Test or Delete
  Test (an unsaved change); File › Save follows the same rule (hub notes).

### Copy Test and Delete Test — `14-test-list-states.png`, `29-delete-confirm.png`
- Copy Test opens **no dialog**. The copy takes the **next number** ("Aim 3"), keeps the source's
  configuration ("Quick4"), is Not Done, is appended at the end and is selected. Help bar:
  "Help: Click to make an exact copy of the selected test, including its settings, and add it to
  the test list."
- Delete Test: dialog "Delete Test", question icon, "Are you sure you want to delete this
  test?", **Yes / No**. Help bar: "Help: Click to permanently remove the selected test from the
  client's list. You will be asked for confirmation."

### Set Colors (Aim) — `17-set-colors.png`
- Title **"Select Target and Background Colors"**.
- Three preset strips, each a circle on a full-width background: white on black, black on white,
  blue on light grey.
- A **Background** row and a **Targets** row of 12 swatches each (white, two greys, dark grey,
  black, red, orange, yellow, green, magenta, cyan, blue).
- **More Background Colors** and **More Target Colors** buttons (not in the guide).
- A **Preview** square showing the current choice (blue circle on white by default), then
  **OK / Cancel**.
- Help bar on the Set Colors… button: "Help: Click to define the colors of the targets and the
  background."

### Select Regions (Aim) — `18-select-regions.png`, `18b-select-regions-one.png`
- Title "Select Regions", text "Shaded regions indicate where targets will appear.".
- A **3 x 2** grid. All unshaded when first opened (see (a) #18). A clicked region turns solid
  blue. **OK / Cancel**.

### Configuration rename warning — `19-rename-warning.png`
- Changing Standard's values and pressing Save & Continue opens a modal **"Compass Warning"**:
  "Configuration settings have changed. Please change the configuration name." with **OK** only.
- There is no name field in it. The user types a new name into the Configuration Name combo and
  saves again (this session used "Quick4": 4 trials, 3 s maximum time).

### Practice — `20-practice-run.png`
- Runs in a separate full-screen window titled with the test name ("Aim 1"), white canvas,
  bottom strip **Pause (Alt-P) / Quit (Alt-Q)**. (No target is visible at the moment of
  capture.)
- After three trials it **returns to the Start screen with no dialog** (hub notes).

### Quit flow — `23-quit-confirm.png`, `24-quit-save-partial.png`
1. Alt-Q or Quit: modal **"Quit Test"**, "Are you sure you want to quit this test?", **OK /
   Cancel**. The Pause button now reads **"Re-Start (Alt-P)"**.
2. OK: modal titled **"Test Complete"**, "Test Complete!", **Save Partial Results / Discard
   Results**. There is no "Save and View Report" here.
3. Save Partial Results lists the test as run, with today's date (see Test List states).

### Preview Test (Drag) — `25-preview-drag.png`
- Same separate window ("Drag 1") and Pause / Quit strip.
- The Drag default shows a yellow **folder icon** as the target and a **trash can in a red
  frame** as the destination.
- Quitting a preview asks the same "Quit Test" confirmation, then **returns to the
  configuration screen** with no save dialog (hub notes).

### Multi-Test Report — `26-multi-evaluator-prompt.png`, `27-multi-report-p1..p4.png`, `28-close-report-prompt.png`
- First a modal **"Compass Multi-Test Report"**: "Please type in an evaluator name the way you
  would like to see it on the report (Optional)." The field is pre-filled ("QA Evaluator").
  **OK / Cancel**.
- Then a separate modal window "Compass Multi-Test Report" with the toolbar in (a) #20.
- Page contents (tests Aim 1 and Aim 2):

| Page | Contents |
|---|---|
| 1 | Title "Compass Comparison Report for Pointing Access - Aim Tests"; "Report Date: 10/6/26 4:54 PM"; "Client: Probe JabTest"; "Evaluator: QA Evaluator"; a **Description** paragraph naming the Aim test; **"A. Speed-Accuracy Graph for Aim Tests"** with its own Description, then a scatter chart "Speed-Accuracy for Aim Tests": y = "% of Error-free Trials" (0–100), x = "Average Trial Time (sec)", one point per test, legend by test name (Aim 1 blue square, Aim 2 red circle) |
| 2 | **"B. Accuracy Graph for Aim Tests"** (bar chart "Accuracy for Aim Tests", y "% of Error-free Trials") and **"C. Speed Graph for Aim Tests"** (bar chart "Speed for Aim Tests", y "Trial Time(sec)"), each with a Description |
| 3 | **"D. Table of Speed and Accuracy Data for Aim Tests"**: columns Test / % Error-free / Trial Time (sec); rows Aim 1 = 50 / 2.13, Aim 2 = 100 / 1.4 |
| 4 | **"E. Table of Configuration Settings for Aim Tests"**: one column per test, 17 rows: Test Name, Configuration Name, Input Device, Test Language, Number of Trials, Selection Method, Target Type, Target Size, Target Distance, Draw Path, Target Color, Background Color, Screen Coverage, Maximum Time, Pause Time, Feedback Style, Feedback Correct, Feedback Incorrect |

- Page 1's Description text: "This report illustrates how different factors affect the
  client's abilities to access the computer. Performance data were collected using the Aim test,
  provided by Compass software for access assessment. The Aim test asks the user to acquire
  targets with a pointing device. The user moves the cursor to each target and selects it."
- Aim 2 was saved after Quit; page 4 still lists its Number of Trials as **12** (the configured
  number, not the number run).
- **Close Report** asks "Do you want to save this report?" with a warning icon, **Yes / No /
  Cancel** (`28-close-report-prompt.png`). The save format was not captured.

### Edit Client Information — `30-edit-client-info.png`
- A full screen titled "Edit Client Information" with the new-client groups: Client Info (First
  Name, Middle Initial, Last Name), Evaluator Info (Evaluator Name), Comments. **Save & Continue
  / Cancel**.
- Help bar: "Help: On this screen, edit the client's name or additional information. This will
  not affect the file name used for the client."

### End Client Session — `31-end-session-prompt.png`
- Modal **"Close Client"**, question icon: "Are you sure you are done with this client?" /
  "Client file will be saved and closed, and you will be able to select another client."
  **Yes / No**.
- Help bar on the button: "Help: Click if you are done working with this client for now. You'll
  be given the option of opening a new client or quitting."

---

## (c) Verified configuration defaults (Standard configuration, all eight tests)

Shared by **all eight** (dumps `config-*`, screenshots `15-config-*.png`):

| Group | Control | Type | Default |
|---|---|---|---|
| (top) | Test Name | field | `<Test> 1` |
| (top) | Configuration Name | editable combo | `Standard` |
| (top) | Input Device | editable combo | `Not Specified` |
| (top) | Test Language | combo | `English` (screenshot) |
| (top) | Notes | multi-line field | empty |
| Feedback Options | Basic / Engaging | radio | **Basic** |
| Feedback Options › Correct Trials | None / Visual / Auditory / Both | radio | **Auditory** |
| Feedback Options › Incorrect Trials | None / Visual / Auditory / Both | radio | **Auditory** |
| Footer | Preview Test / Save & Continue / Cancel | buttons | — |

Help bar on every configuration screen: "Help: On this screen, you can change the configuration
settings for this test. To see what the new settings look like, click the 'Preview' button. When
you are done, click 'Save & Continue'." Menu, Scan, Letter, Word and Sentence say "for this
<Test> test" instead of "for this test". Note: the button the help refers to is labelled
"Preview Test".

Test-specific settings:

| Test | Group | Control | Type | Default |
|---|---|---|---|---|
| **Aim** | (top) | Number of Trials | field | 12 |
| | Target Types | Squares / Pictures / Icons | radio | **Squares** |
| | Selection Method | Click / Dwell / Double Click | radio | **Click** |
| | Selection Method | Dwell Time (sec) | field (disabled until Dwell) | 1.0 |
| | Target Size and Color | Small / Toolbar / Icon-Size / Large | check | **Icon-Size** only |
| | Target Size and Color | Set Colors... | button | blue on white (`17`) |
| | Target Location › Distance | Short / Medium / Long | check | **Medium + Long** |
| | Target Location › Screen Coverage | Percentage / Regions | radio | **Percentage** |
| | Target Location › Screen Coverage | Width / Height | fields | 100 / 100 |
| | Target Location › Screen Coverage | Select Regions... | button | disabled until Regions |
| | Target Location | Draw cursor path | check | off |
| | Timing | Maximum time per trial (sec) / Pause between trials (sec) | fields | 30 / 1 |
| **Drag** | (top) | Number of Trials | field | 12 |
| | Target Types | Squares / Pictures / Icons | radio | **Icons** |
| | Selection Method | Click / Dwell (no Double Click) | radio | **Click** |
| | Selection Method | Dwell Time (sec) | field (disabled until Dwell) | 1.0 |
| | Size and Color › Target Size | Small / Toolbar / Icon-Size / Large | check | **Icon-Size** only |
| | Size and Color › Destination Size | Same as Target / Large | radio | **Same as Target** |
| | Size and Color | Set Colors... | button | — |
| | Target Location | Distance, Screen Coverage, Draw cursor path | as Aim | Medium + Long; Percentage 100 / 100; off |
| | Timing | Maximum time / Pause | fields | 30 / 1 |
| **Menu** | (top) | Number of Trials | field | 8 |
| | Prompt | Target Item and Menu / Target Item Only | radio | **Target Item and Menu** |
| | Menu Complexity | 'Simple' Menubar (4 menus) / 'Typical' Menubar (8 menus) | radio | **'Typical' Menubar (8 menus)** |
| | Menu Complexity | Include Submenus | check | off |
| | — | Change Text Style... | button | not opened |
| | Timing | Maximum time / Pause | fields | 90 / 1 |
| **Scan** | (top) | Number of Trials | field | 8 |
| | (right column) | Scan Rate (sec) / Extra Delay (sec) | fields | 2.0 / 0.0 |
| | (right column) | Scan Initiation | combo | **Manual** |
| | (right column) | Scan Layout | combo | **Row-column Frequency 1** |
| | (right column) | Show Sentence | check | off |
| | (right column) | Loop Count | field | 1 |
| | — | Change Item Style... | button | not opened |
| | Timing | Maximum time / Pause | fields | 180 / 1 |
| **Switch** | (top) | Number of Trials | field | 8 |
| | Prompt Type | Set Colors... | button | not opened |
| | Prompt Type | Add Audio to Prompt | check | off |
| | Selection Method | Hits Required Per Trial | combo | 1 |
| | Selection Method | Hold Time (sec) | field | 0.0 |
| | Timing | Max Time per Trial (sec) | field | 30 |
| | Timing › Pause Time Between Trials | Constant / Random | radio | **Random** |
| | Timing | Min Pause (sec) / Max Pause (sec) | fields | 1 / 4 |
| **Letter** | (top) | Number of Trials | field | 8 |
| | (right column) | Letter List | combo | **All Letters** |
| | Letter Case | Upper Case / Lower Case | check | **Lower Case** only |
| | — | Change Text Style... | button | not opened |
| | Timing | Maximum time / Pause | fields | 30 / 1 |
| **Word** | (top) | Number of Trials | field | 8 |
| | (right column) | Word List | combo | **Word Set 2** |
| | (right column) | Allow Edits / Case Sensitive Scoring | check | **on** / off |
| | — | Change Text Style... | button | not opened |
| | Timing | Maximum time / Pause | fields | 120 / 1 |
| **Sentence** | (top) | Number of Trials | field | 4 |
| | (right column) | Sentence List | combo | **Sentence Set 2** |
| | (right column) | Allow Edits / Case Sensitive Scoring | check | **on** / off |
| | — | Change Text Style... | button | not opened |
| | Timing | Maximum time / Pause | fields | 300 / 1 |

Label differences worth knowing: Switch's timing labels are "Max Time per Trial (sec)" and
"Pause Time Between Trials:", where the other seven say "Maximum time per trial (sec)" and
"Pause between trials (sec)". Drag's size group is titled "Size and Color", Aim's "Target Size
and Color".

---

## (d) Start-screen instructions (all eight tests)

Every Start screen: title "Start <Test name>", a white instruction pane, footer **Start /
Practice / Cancel**, help bar "Help: Click to begin running the selected test." (dumps
`start-*`, screenshots `16-start-*.png`).

**Aim** (`16-start-aim.png`)
> Instructions for the Aim test:
> 1. A target will appear on the screen.
> 2. Move the mouse cursor to the target and select.
> 3. Continue until no more targets appear.
>
> NOTE: If you do not select a target within the available time, it will disappear, and the next target will be presented.
>
> To pause the test: Click the "Pause" button, or press ALT-P.
> To quit the test: Click the "Quit" button, or press ALT-Q.

**Drag** (`16-start-drag.png`)
> Instructions for the Drag test:
> 1. Two objects will appear on the screen: a target to move and a destination.
> 2. Move the mouse cursor over the target. Press and hold the mouse button.
> 3. Drag the target to the destination.
> 4. Continue until no more targets appear.
>
> NOTE: If you do not drag the target to the destination within the available time, it will disappear, and the next target and destination will be presented.
>
> To pause the test: Click the "Pause" button, or press ALT-P.
> To quit the test: Click the "Quit" button, or press ALT-Q.

**Menu** (`16-start-menu.png`)
> Instructions for the Menu test:
> 1. A menu item will be presented on the screen.
> 2. Find this item in one of the menus and select it.
> 3. Continue until no more menu items appear.
>
> NOTE: If you do not make a correct selection within the available time, a new menu item will be presented.
>
> To pause the test: Click the "Pause" button, or press ALT-P.
> To quit the test: Click the "Quit" button, or press ALT-Q.

**Scan** (`16-start-scan.png`)
> Instructions for the Scan test:
> 1. An item will be presented at the top of the screen.
> 2. Press the switch to begin scanning the rows of the matrix.
> 3. Try to select the item, by choosing it from the scanning matrix with your switch.
> 4. Continue until no more items appear.
>
> NOTE: The 'switch' means a mouse button or equivalent.
>
> NOTE: If you do not select the item within the available time, a new item will be presented.
>
> To pause the test: Click the "Pause" button, or press ALT-P.
> To quit the test: Click the "Quit" button, or press ALT-Q.

**Switch** (`16-start-switch.png`)
> Instructions for the Switch test:
> 1. When the prompt is presented, click the switch the number of times specified.
> 2. Wait until the next prompt is presented.
> 3. Continue until the test is complete.
>
> NOTE: The 'switch' means a mouse button or equivalent.
>
> NOTE: If you do not complete the required number of switch hits within the available time, the prompt will disappear, and the next prompt will be presented.
>
> To pause the test: Click the "Pause" button, or press ALT-P.
> To quit the test: Click the "Quit" button, or press ALT-Q.

**Letter** (`16-start-letter.png`)
> Instructions for the Letter test:
> 1. A letter will be presented on the screen.
> 2. Try to copy that letter.
> 3. Continue until no more letters appear.
>
> NOTE: If you do not type the letter within the available time, a new letter will be presented.
>
> To pause the test: Click the "Pause" button.
> To quit the test: Click the "Quit" button.

**Word** (`16-start-word.png`)
> Instructions for the Word test:
> 1. A word will be presented on the screen.
> 2. Try to copy that word exactly.
> 3. Hit the Enter key when you are done with the word.
> 4. Continue until no more words appear.
>
> NOTE: If you do not finish the word within the available time, a new word will be presented.
>
> To pause the test: Click the "Pause" button.
> To quit the test: Click the "Quit" button.

**Sentence** (`16-start-sentence.png`)
> Instructions for the Sentence test:
> 1. A sentence will be presented on the screen.
> 2. Try to copy that sentence exactly.
> 3. Hit the Enter key when you are done with the sentence.
> 4. Continue until no more sentences appear.
>
> NOTE: If you do not finish the sentence within the available time, a new sentence will be presented.
>
> To pause the test: Click the "Pause" button.
> To quit the test: Click the "Quit" button.

Observations:
- Only the three text-entry tests omit ALT-P / ALT-Q, matching the guide's list of tests that
  have the shortcuts *(Running Tests)*. Neither source says why.
- Scan step 2 says "Press the switch to begin scanning", which fits the **Manual** Scan
  Initiation default in (c), not the guide's "Automatic".

---

## (e) Results-table semantics, verified with misses

Run: Aim 1, configuration "Quick4" (4 trials, 3 s maximum time, otherwise Standard). The script
clicked two targets and let two time out (`21-summary-with-misses.png`,
`22-detailed-with-misses.png`, dump `report-summary`).

Detailed view (Target-by-Target Results):

| Target | Size | Distance | Correct? | Trial Time (sec) | Reaction Time (sec) | Entries | Clicks |
|---|---|---|---|---|---|---|---|
| 1 | Icon-Size | Medium | Yes | 1.46 | 0.09 | 1 | 1 |
| 2 | Icon-Size | Long | Yes | 1.04 | 0.93 | 1 | 1 |
| 3 | Icon-Size | Long | No | 3 | 0 | 0 | 0 |
| 4 | Icon-Size | Medium | No | 3.01 | 0 | 0 | 0 |

Summary of Results, and what each cell averages over:

| Row | % (N) | Trial Time | Reaction Time | Entries | Clicks | Averaged over |
|---|---|---|---|---|---|---|
| Error-free Target Selections | 50% (2/4) | 1.25 | 0.51 | 1 | 1 | trials 1–2 |
| All Targets Selected | 50% (2/4) | 1.25 | 0.51 | 1 | 1 | trials 1–2 (no extra clicks in this run, so equal to the row above) |
| Targets Not Selected | 50% (2/4) | 3.01 | *(blank)* | 0 | 0 | trials 3–4: (3 + 3.01) / 2 = 3.005 |
| All Aim Trials | 100% (4/4) | 2.13 | 0.51 | 0.5 | 0.5 | see below |

The **All Aim Trials** row does not use one rule for every column:
- **Trial Time** 2.13 = mean of **all four** trials ((1.46 + 1.04 + 3 + 3.01) / 4 = 2.1275).
- **Reaction Time** 0.51 = mean of the **two selected** trials only. The misses' 0 values are
  left out; including them would give 0.255.
- **Entries** and **Clicks** 0.5 = mean of **all four**, counting the misses' zeros.

Other facts from the same run:
- A miss shows Reaction Time **0** in the detailed table but a **blank** in the summary row.
- A timed-out trial's Trial Time can be at or just over the maximum (3 and 3.01 with a 3 s
  maximum), even with no target selected.
- Test Date on the report includes seconds ("Oct 6, 2026 4:49:56 PM"); the Test List shows the
  date only.
- The Evaluator field on the report is pre-filled from the client's evaluator name.
- The multi-test report takes **% Error-free** from the Error-free Target Selections row (50)
  and **Trial Time** from the All Aim Trials row (2.13), so timed-out trials raise the "speed"
  figure (`27-multi-report-p3.png`).
- The first target of both Aim 1 and Aim 2 appeared at the screen centre (hub notes). One run
  each is not enough to say whether target sequences are fixed or random.

Only Aim was checked this way. The other seven tests' results screens were not opened.

---

## (f) Still unverified or out of reach

| Topic | Status |
|---|---|
| Target order per test (fixed or random; same between Aim 1 and Aim 2?) | Not established; only the first target was compared |
| Engaging feedback (look and sound); Visual feedback | Not captured |
| The trial screens of Menu, Scan, Switch, Letter, Word, Sentence | Not captured (only Aim practice and Drag preview were run) |
| Results screens of the other seven tests | Not captured |
| Change Text Style..., Change Item Style..., Switch Set Colors..., Drag Set Colors... dialogs and their defaults (fonts, sizes, colours) | Not opened |
| Combo lists: Test Language, Input Device, Scan Layout, Scan Initiation, Letter List, Word List, Sentence List, Hits Required | Only the selected value was read |
| Register... form | Not opened |
| Help system (Compass Help, F1), Help › Overview ("Quick Intro to Compass"), About | Not opened |
| Print Report / Print output; Multi-Test Report Save format (RTF/PDF) | Not captured |
| Whether Alt-P / Alt-Q work in Letter, Word, Sentence | Not tested |
| A paused trial mid-run | Only seen while the Quit dialogs were open (button reads "Re-Start (Alt-P)") |
| Select Regions with none shaded and OK pressed | Not tested |
| Column-header sorting, Delete key, Ctrl-C table copy, tooltips | Not tested |
| Mac behaviour; conversion of client files from Compass 1.2 or earlier | Out of reach (Windows only, no old files) |
