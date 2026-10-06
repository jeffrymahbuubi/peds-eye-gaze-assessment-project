---
title: "Compass 3.0 — UI/UX Patterns (synthesis)"
derived_from: sources/compass-user-guide.md
built: 2026-10-05
fidelity: derived — every statement traces to a heading in the source; no outside facts added
---

# Compass 3.0 — UI/UX Patterns

Objective of the corpus: a reference on **how the UI/UX of the Compass app is created**.

## Read this first — what the guide can and cannot tell you

The guide documents **behaviour**: what each screen shows, what each button does, which
defaults ship. It does **not** document **construction**: there is no layout grid, spacing,
widget toolkit, colour palette (beyond a few per-test defaults) or design rationale (beyond
short usability remarks). The few construction facts it does give are collected in
[§8](#8-platform-and-construction-facts). The 58 screenshots are not in this corpus, so every
layout statement below comes from prose alone — consult the PDF for anything visual.

**Verified values:** the running 3.0.1 app was checked on 2026-10-06. Where it differs from the
guide, this file now adds a short **Live** note; the evidence and the full defaults of all eight
tests are in [`ui-ux-live-verification.md`](ui-ux-live-verification.md).

**Citations** name a heading in [`sources/compass-user-guide.md`](../sources/compass-user-guide.md),
with `›` for nesting, e.g. *(Aim Test Configuration › Timing)*. Page numbers are not preserved.

## 1. Application map

```
Welcome ─Start Compass─► Choose an Action ─┬─ Create New Client ─► new-client form ─Save & Continue─►
 (skippable)                               │      Save As ─► Choose Skill Tests ─► Test List
                                           ├─ Open Existing Client ─► Open dialog ─► Test List
                                           └─ Quit Compass
Test List ─┬─ Configure Test ─► configuration screen ─(Preview Test | Save & Continue | Cancel)─► Test List
           ├─ Run Test ─► Start <test> screen ─┬─ Practice (3 trials, no data)
           │                                    └─ Start ─► trials (Pause/Re-Start, Quit)
           │                                         └─► Save | Save and View Report | Discard
           ├─ View Report ─► Summary ⇄ Details ─(Save & Continue | Cancel)─► Test List
           ├─ Multi-Test Report ─► separate, paginated window
           ├─ Copy Test · Add Test (► Choose Skill Tests) · Delete Test
           └─ End Client Session ─► Choose an Action          (Save Client File without leaving)
```

Sources: *Welcome to Compass*, *Choose an Action*, *Create a New Client*, *Open an Existing
Client*, *Choosing Skill Tests*, *Test List*, *Configuring Tests*, *Running Tests*, *Viewing
Results*, *Multi-Test Reports*.

- **Menubar** items named in the guide: `File/New Client`, `File/Open Client`, `File/Save`,
  `File/Save As`, `Edit/Copy` (or Ctrl-C), `Tools/Preferences`, `Tools/Edit Client
  Information`, `Help/Compass Help` (or F1) *(Create a New Client; Open an Existing Client; Test
  List; Viewing Results; Tailoring the Compass Interface; Getting Help)*. **Live:** the full
  menubar (including Print Report..., Exit, Cut/Paste, Help › Overview and About) is listed in
  live-verification (b).
- **The Welcome screen is optional.** A "Don't show this introduction screen in the future" box
  skips it; `Tools/Preferences › Show welcome screen when Compass starts` brings it back
  *(Welcome to Compass; Tailoring the Compass Interface)*.
- **One client = one file.** Test list, configurations and results all live in a single `.cms`
  file; every Save / Save & Continue writes it; cancelling or leaving a screen without saving
  leaves previously saved data unchanged *(How Compass Stores Client Information)*.

## 2. Reusable interaction patterns

| Pattern | What the guide describes | Where |
|---|---|---|
| **Test List as hub** | Choose Skill Tests, configuration screens and report screens all return to the Test List on Save & Continue / Cancel. | *Choosing Skill Tests*; *Aim Test Configuration*; *Viewing Results* |
| **State-dependent buttons** | The Test List buttons are bold when available and grey when not. View Report is grey for an unrun test; Configure Test is grey once a test has run; Run Test is grey once data are stored; Multi-Test Report is active only when two or more tests of the *same skill* are selected. The Save button is grey when nothing changed. | *Test List* |
| **Unrun tests stand out** | Information for tests that have not been run is shown in bold; rows sort by clicking a column heading. | *Test List* |
| **Immutable once run → copy** | A run test cannot be reconfigured or re-run; **Copy Test** duplicates it with identical configuration, so comparisons are like-for-like and only one setting need change. | *Test List*; *Configuring Tests* |
| **Names as labels** | Test names must be unique within a client file (default `Menu 1`, `Menu 2`…). Configuration names need not be unique, but one name must mean one set of settings; default `Standard`, and editing Standard forces a rename on save. Test names become the legend labels of multi-test reports. | *Configuring Tests*; *Multi-Test Reports* |
| **Safe trial running** | **Practice** (3 trials, otherwise same settings, no data, repeatable) and **Preview Test** (abbreviated, no data) before any recorded run; **Pause / Re-Start** (stopwatch stops); **Quit** asks for confirmation. On finishing: save, save and view, or discard — discarded tests stay "not completed" and can be re-run. | *Running Tests*; *Aim Test Configuration* |
| **Pause semantics** | After a pause a *new* trial is presented and the interrupted trial's data are not recorded (Sentence is the exception: the same sentence stays on screen). | *Running Tests* |
| **Confirm destructive actions** | Delete Test asks "are you sure"; Delete key and multi-select delete are supported. Quit asks for confirmation. | *Test List*; *Running Tests* |
| **Two-level results** | Summary view first; **View Details** / **View Summary** toggles. Both show the configuration, date/time and client; fields for input device, notes and evaluator. | *Viewing Results* |
| **Read-only data, editable context** | On report screens only Test Name, Input Device, Notes and Evaluator can be edited; Cancel exits without saving those edits but the performance data were already saved. | *Viewing Results*; *Aim Test Results* |
| **Conditional columns** | Columns appear only when meaningful: Net Errors is hidden when Allow Edits is off; Recovery Time is shown only for multi-hit Switch tests; Letter-by-Letter Target / Correct? appear only when Allow Edits is off. | *Word Test Results*; *Switch Test Results* |
| **Copy-out and export** | Any table can be selected (drag, or Shift + cursor keys) and copied (Edit/Copy, Ctrl-C); columns are resizable by dragging; reports print; multi-test reports save as RTF or PDF. | *Viewing Results*; *Multi-Test Reports* |
| **Record what the app cannot know** | Compass "will not know" the input device; the clinician sets it during configuration (best) or on the report. Default value `Not Specified`. | *Using Compass with Pointing Devices*; *Aim Test Configuration* |
| **Layered help** | Tool Tips (hover; toggle in Preferences) → Screen Tips (always shown in a help frame at the bottom of the window) → Help System (F1 / Help menu) → bundled PDF. | *Getting Help* |
| **Minimal preferences** | Only two: show the welcome screen, show tooltips. | *Tailoring the Compass Interface* |
| **Defaults first, then tailor** | Every test ships "reasonable" defaults for a wide range of clients; the configuration screen lets you preview look and feel before collecting data. | *Welcome to Compass!*; *Tips for Using Compass › 2* |

## 3. Anatomy of a configuration screen

Every test's configuration section lists settings in the same order, then test-specific groups:

1. **Test name** · 2. **Configuration name** · 3. **Input device** · 4. **Test Language** ·
5. **Notes** · 6. **Number of Trials** · 7. **Feedback Options** (Style; Correct Trials;
Incorrect Trials) · 8. *test-specific groups* · 9. **Timing** (Maximum Time per Trial; Pause
Between Trials) · 10. buttons **Preview Test**, **Save & Continue**, **Cancel**.

*(Aim, Menu, Scan, Switch, Letter, Word and Sentence Test Configuration; the Drag section defers
to Aim for the shared settings.)* The same three-button footer closes every one of them.

Appearance dialogs are opened from a button and share a structure — option panels, a
**Preview** area, **OK** / **Cancel**:

| Test | Button | Lets you change |
|---|---|---|
| Aim | **Set Colors…** | target and background colour (pre-set combinations of white / black / blue targets); ignored for icon and picture targets |
| Menu | **Text Style…** | font, style, size, text and background colour — **Windows only** |
| Scan | **Change Item Style…** | letter/image size, background, scanning-highlight and text colour, font |
| Switch | **Set Colors…** | prompt and background colour |
| Letter, Word, Sentence | **Text Style…** | font, style, size, text and background colour |

*(Aim Test Configuration › Target Size and Color; Menu Test Configuration; Scan Test
Configuration › Item Style; Switch Test Configuration › Prompt Type; Letter / Word / Sentence
Test Configuration › Text Style)*

**Live:** the Menu, Letter, Word and Sentence button is labelled **"Change Text Style..."**;
Aim's Set Colors dialog is titled "Select Target and Background Colors" and also has "More
Background Colors" / "More Target Colors" buttons (`screenshots/15-config-*.png`,
`17-set-colors.png`).

## 4. The eight tests at a glance

Families: **Pointing** (Aim, Drag, Menu), **Scanning** (Switch, Scan), **Text Entry** (Letter,
Word, Sentence) *(Skill Tests)*.

| Test | What the client sees / does | Selection or input options | Trials | Max time | Pause between | Other shipped defaults |
|---|---|---|---|---|---|---|
| **Aim** | One target at a time; move cursor in and select | Click (default), Double Click, Dwell (1.0 s) | 12 | 30 s | 1 s | Squares; Icon-Size; blue on white; Medium + Long distance; 100 % coverage; no cursor path |
| **Drag** | Target + destination pair; drag target to destination | Click (default, Live), Dwell (1.0 s, Live) | not stated in the Drag section; **Live: 12** | not stated; **Live: 30 s** | not stated; **Live: 1 s** | Icons (destination is a trashcan; pictures → a house); Icon-Size (Live); destination "Same as Target"; Medium + Long; 100 % coverage, no cursor path (Live) |
| **Menu** | Target item (and its menu) prompt; choose it from a menubar | any input device | 8 | 90 s | 1 s | Prompt = Target Item and Menu; Typical menubar (8 menus, 3–10 items); submenus off; bold 12, black on gray |
| **Scan** | Target item + scanning layout; single switch | automatic single-switch scanning only | 8 | 180 s | 1 s | scan rate 2 s; extra delay 0; initiation Automatic (**Live: Manual**); layout Row/column Frequency (EARDF) (**Live: combo reads "Row-column Frequency 1"**); loop count 1; Show Sentence off; bold 40, black on gray, yellow highlight |
| **Switch** | Visual prompt (neutral face → yellow smiley on hit) | left mouse button or emulating switch | 8 | 30 s | constant 1 s (or random 1–4 s) (**Live: Random is selected, 1–4 s**) | 1 hit required (2 or 3 available); hold time 0 s; audio prompt off |
| **Letter** | One target letter; type it | any keyboard / emulator | 8 | 30 s | 1 s | All Letters; lower case; bold 40, black on gray; scoring always case-sensitive |
| **Word** | Target word + entry box; Enter ends trial | any keyboard / emulator | 8 | 120 s | 1 s | Word List Set.2 (≈3rd grade) (**Live: label "Word Set 2"**); Allow Edits on; case-sensitive scoring off; bold 40, black on white |
| **Sentence** | Target sentence + entry box; Enter ends trial | any keyboard / emulator | 4 | 300 s | 1 s | Sentence Set 2 (≈3rd grade; 6 list options); Allow Edits on; case-sensitive scoring off; bold 30, black on white |

Feedback defaults, where stated (all but Drag): Style **Basic**; Correct Trials **Auditory**;
Incorrect Trials **Auditory** *(each test's Configuration › Feedback Options)*. **Live:** the
same for all eight, Drag included. Every other value in this table that is a control on the
configuration screen matched the live screens. Not checked live: font/colour defaults (bold 12,
bold 40 …, the style dialogs were not opened), Menu's "3–10 items", and Letter's always
case-sensitive scoring (`screenshots/15-config-*.png`; live-verification (c)).

Selected design details:

- **Aim / Drag screen coverage** can be a width/height percentage from screen centre or any
  combination of six selectable regions; conflicting settings (e.g. Long distance in one small
  region) are resolved on a best-effort basis, usually at a region corner *(Aim Test
  Configuration › Target Location)*.
- **Menu** keeps the target prompt toward the lower right so large fonts do not collide with
  drop-down menus *(Menu Test Overview)*.
- **Scan** has ten layouts: five letter matrices (alphabetical, three frequency-ordered,
  QWERTY), one 3×3 image matrix and four 2-/4-item word or image linear layouts; "space" is
  drawn as an underscore; selection happens on switch **press** *(Scan Test Configuration ›
  Scan Layout; Scan Test Overview)*. It supports only single-switch automatic scanning; for
  other scanning styles the guide recommends third-party scanning software plus a text-entry
  test *(Scan Test Configuration)*.
- **Word / Sentence** rate maths assumes 5 letters per word so lists of different word lengths
  stay comparable *(Word Test Configuration › Word List; Sentence Test Configuration ›
  Sentence List)*. **Allow Edits** off hides wrong keystrokes from the client to reduce
  distraction while still counting them *(same sections)*.

## 5. Results screens

Shared layout *(each "… Test Results" section)*: a **Summary of Results** table whose rows are
trial categories and whose first column is always **% (N)**, then per-test measures; a **detailed
view** with one row per trial; the same five buttons — Print Report, View Details, View Summary,
Save & Continue, Cancel.

| Test | Row categories | Measure columns |
|---|---|---|
| Aim | Error-free Target Selections · All Targets Selected · Targets Not Selected · All Aim Trials | Trial Time · Reaction Time · Entries · Clicks |
| Drag | Error-free Drags · All Drags Completed Successfully · Drags Not Completed · All Drag Trials | Trial Time · Click Errors · Drag Attempts |
| Menu | Error-free Menu Selections · All Items Selected Correctly · Incorrect Items Selected · No Item Selected Within Max Time · All Menu Trials | Trial Time · Correct Menus · Incorrect Menus |
| Scan | Correct Item Selected · Incorrect Item Selected · No Item Selected Within Max Time · All Trials | Trial Time · Timing Errors; plus an **Additional Results** table of eight scanning-error types and a total (Count, Correct Selections, Proportion) |
| Switch | Correct Trials · Incorrect Trials · No Switch Pressed · All Switch Trials | Trial Time · 1st Press Time · Release Time · Recovery Time · Switch Hits; plus a **Recommendations** table |
| Letter | Correct Letter Selected · Incorrect Letter Selected · No Key Pressed Within Max Time · All Letter Trials | Trial Time · Press Time · Duration |
| Word | Error-free Words · Words Correct by End of Trial · Incorrect Words · All Trials | Trial Time · Typing Speed (wpm) · Total Errors % · Net Errors % |
| Sentence | Error-free Sentences · Sentences Correct by End of Trial · Incorrect Sentences · All Trials | same as Word |

- **Target Map** (Aim, Drag): a drawing of the display; a green circle marks a successful trial,
  a red X an unsuccessful one, each labelled with its trial number. Aim circles are sized like the
  targets; Drag adds a line for the target's starting point. Its stated purpose is to expose
  screen areas where selection is harder *(Aim Test Results; Drag Test Results)*.
- **Detailed view for text entry** has two tables — per word/sentence and per keystroke
  *(Word Test Results; Sentence Test Results)*.
- **Recommendations** (Switch): suggested Scan Rate ≈ 1.5 × 1st Press Time; Extra Delay only
  from 2- and 3-hit tests, blank for 1-hit *(Switch Test Results)*.
- **Multi-test report** content: combined speed-accuracy profile; bar graphs for accuracy and
  for speed; a description of the variables behind each graph; a data table; each test's
  configuration. Shown in a separate window, page by page (Previous / Next), with Print, Save and
  Close; the file format defaults to RTF on Windows and PDF on Mac OS X *(Multi-Test Reports)*.

## 6. Feedback and motivation design

- **Style:** *Basic* (simple, direct) or *Engaging* (more stimulating, to hold interest); one style
  is used for every trial of a test. **Correct** and **Incorrect** trials each choose **None /
  Visual / Auditory / Both** *(each test's Configuration › Feedback Options)*.
- **What "Incorrect" means differs per test:** Aim — target not selected in time; Menu — a wrong
  menu item; Letter — a wrong letter; Word / Sentence — an incorrect entry at end of trial
  *(Feedback Options in each configuration section)*.
- **Switch:** the visual prompt is a neutral face that turns into a yellow smiley on a hit; in the
  default case a short "ding" plays and a "Wait…" message shows until the next prompt *(Switch
  Test Overview; What Was New in Version 2.1)*.
- **Engaging feedback and language:** vocal feedback uses the Test Language; in Aim only Engaging
  Feedback is affected by it *(Aim Test Configuration)*.
- **Making a test easier / more interesting** is a described tactic: pictures as targets, large
  targets, large destination, Engaging feedback *(Overview of Sample Scenarios › Task 6)*.

## 7. Accessibility, input-agnosticism and localisation

- **Input-method agnostic by design:** all tests can be run with alternative keyboards or
  pointing devices; the procedure is to set up the input method under assessment, then run a test
  with it *(Compass Accessibility)*. Compass accepts anything that emulates a mouse or keyboard,
  so devices are treated uniformly *(Using Compass with Pointing Devices; … Alternative
  Keyboards)*.
- **Clinician UI is meant to be accessible too:** navigation works by mouse or mouse emulator,
  keyboard or keyboard emulator *(Compass Accessibility)*.
- **Follows the OS rather than offering its own theme:** on Windows the "Message Box" font sets
  most text size; changes need a Compass restart; the Help system is not affected; display
  colour schemes and zoom are honoured; very large fonts may make screens illegible. Test
  configurations can override fonts, colours and timing *(Compass Accessibility; Operating System
  Settings; Tailoring the Compass Interface)*.
- **Known gap — screen readers:** NVDA works "to some extent"; Windows Narrator does not; Mac
  VoiceOver reads some elements but not all *(Compass Accessibility)*.
- **Localisation split:** the interface is English only; the *test materials*, menus and vocal
  feedback can be Arabic, English, French, Portuguese or Spanish per test *(International
  Languages and Compass)*. Windows Regional Options affect date/time formatting, and a client
  file created under one region may not open under another *(same section)*.

## 8. Platform and construction facts

The only statements about how the app is built:

- Runs on **Java** — "Java JRE 8" from v2.4, "Java 11" from v3.0 ("a major change internally")
  *(What was New in Version 2.4; What's New in Version 3.0)*.
- Since v2.0, **platform-specific look-and-feel** on Windows and Mac; earlier versions used a
  generic one because of problems with the Windows look-and-feel; "some gaps still exist"
  *(What Was New in Version 2.0 › Updated Look-and-Feel)*.
- A local **Java Access Bridge** is installed for Compass only, to support Windows screen readers
  *(What was New in Version 2.4)*.
- **File and dialogs:** standard OS file-management dialogs; default file location My Documents
  (Windows) or home directory (Mac) *(How Compass Stores Client Information; Open an Existing
  Client)*. **Live (Windows):** the dialogs are Java (Swing) file choosers in the Windows look,
  and they open in the last-used folder on "All Files" (`11-save-as-new-client.png`,
  `12-open-dialog.png`).
- **Registration:** a dialog on first run offers a 30-day free trial or registration (name,
  email, licence code) *(Trial Period and Registration)*.
- **Mac menubar limitation:** the standard Apple/Application menus stay active during a test and
  could not be removed by the developers *(Running Tests; Menu Test Overview)*.

## 9. How the UI evolved

| Version | UI-relevant change | Where |
|---|---|---|
| 1.2 | Scan test gets 7 layouts; Switch counts every hit in a trial | *What Was New in Version 1.2* |
| 2.0 | Multi-test reports; Mac OS X; new `.cms` format; simpler licensing; platform look-and-feel | *… Version 2.0* |
| 2.1 | Scan: more layouts, extra delay, initiation, loop count, type-a-sentence, error report. Switch: neutral/smiley face prompt, 1–3 hits, timing recommendations | *… Version 2.1* |
| 2.2 – 2.5 | Test materials in Spanish, Portuguese, Arabic; extra Sentence lists | *… Versions 2.2, 2.3, 2.5* |
| 2.4 | Java JRE 8; Access Bridge bundled | *… Version 2.4* |
| 3.0 | Java 11; Mac dictation timing fix | *What's New in Version 3.0* |

## 10. Traps and inconsistencies in the guide

Surfaced, not resolved — without the screenshots the true on-screen labels cannot be checked.
(Items the live app settled on 2026-10-06 carry a "Resolved live" note; evidence in
[`ui-ux-live-verification.md`](ui-ux-live-verification.md).)

1. **Scan layouts — overview vs configuration.** *Scan Test Overview* says "Two letter layouts are
   available: alphabetical and frequency-based"; *Scan Test Configuration* lists five letter
   matrices (alphabetical, three frequency-based, QWERTY) among ten layouts, and *Version 2.1*
   says letter layouts were added. The configuration section is more specific and fits the
   release notes; treat the overview sentence as stale.
2. **Word Test Results talks about Aim.** Its opening paragraph refers to "two or more Aim
   tests", "an Aim test" and "a single Aim test" — evidently copied from the Aim page
   *(Word Test Results)*.
3. **Button labels differ between sections.** "Add New Test" *(Choosing Skill Tests)* vs "Add Test"
   *(Test List)*; the "Save Client File" button vs "the **Save** button is grey" *(Test List)*;
   "Pause button / Quit button" vs "Pause Test button / Quit Test button" in the Letter, Word and
   Sentence overviews.
   *Resolved live 2026-10-06:* the real labels are "Add New Test" and "Save Client File"
   (`14-test-list-states.png`). In the Aim and Drag run windows the buttons read "Pause (Alt-P)"
   / "Quit (Alt-Q)" (`20`, `25`); the Letter/Word/Sentence Start screens say "Pause" / "Quit"
   button (`16-start-letter.png` etc.). Their run windows were not captured.
4. **Keyboard shortcuts are listed only for some tests.** Alt-P / Alt-Q are documented for Aim,
   Drag, Menu, Switch and Scan *(Running Tests)*; the Letter, Word and Sentence overviews mention
   buttons only. The guide does not say whether the shortcuts are absent there.
   *Partly resolved live 2026-10-06:* the app's own Start-screen instructions match the guide:
   ALT-P / ALT-Q for the five, buttons only for Letter, Word and Sentence (`16-start-*.png`).
   Whether the keys work in the text tests was not tested.
5. **"Quit" saves partial data as "completed".** Saving after Quit lists the test as completed
   *(Running Tests)*, but a partially entered sentence is not recorded *(Sentence Test
   Overview)*.
   *Resolved live 2026-10-06:* confirmed. After "Save Partial Results" the Test List shows only
   the date, exactly like a complete test, with no partial marker; the multi-test report lists
   its configured Number of Trials (12), not the number run (`14-test-list-states.png`,
   `24-quit-save-partial.png`, `27-multi-report-p4.png`).
6. **Trial Time can exceed Maximum Time** in Aim and Drag if the cursor is inside the target when
   time expires *(Aim Test Results; Drag Test Results)*.
   *Seen live 2026-10-06:* a timed-out Aim trial with no selection recorded 3.01 s against a 3 s
   maximum (`22-detailed-with-misses.png`), so a small overrun also occurs without the cursor in
   the target.
7. **Total Errors is unreliable with prediction or speech recognition**, because those tools
   insert backspaces that are counted; use Net Errors and Typing Speed instead *(Using Compass
   with Word Prediction; … Speech Recognition)*.
8. **The guide cannot tell which input device was used** unless the clinician records it; without
   it the results of two devices cannot be told apart *(Using Compass with Pointing Devices)*.
9. **Windows-only and Mac-only behaviour:** Menu Text Style is Windows only; BounceKeys and
   Enhance Pointer Precision are not available on Mac *(Menu Test Configuration; Operating System
   Settings)*.
10. **Old files are overwritten on conversion:** opening a v1.2-or-earlier file offers conversion,
    and saving overwrites the original — copy it first *(Open an Existing Client)*.
11. **Printing:** the Drag target map may not print correctly on some printers *(Drag Test
    Results)*.
12. **Version drift:** this is the 3.0 guide; the installer in the workspace is 3.0.1
    (see [INDEX.md](../INDEX.md)).
    *Resolved live 2026-10-06:* the 3.0.1 app differs from the guide in a few defaults and
    labels (Scan Initiation Manual, Switch pause Random, "Change Text Style...", file dialogs
    open in the last-used folder on "All Files", trial-extension email support@). Whether these
    are version changes or guide errors cannot be told. Full list: live-verification (a).
13. **Multi-test "speed" includes timeouts** (found live, not in the guide). The multi-test
    report's Trial Time is the All-trials mean, timed-out trials included, although its text
    says "the average time the user required to select the targets" (`27-multi-report-p3.png`;
    live-verification (e)).

## 11. Research basis the guide cites

- Text-entry error metrics (Total / Net Errors) follow Soukoreff & MacKenzie (2003), CHI 2003
  *(Word Test Results › Note on error rate calculations)*.
- Sentence lists derive from MacKenzie & Soukoreff (2003) phrase sets *(Sentence Test
  Configuration › Sentence List)*.
- The EARDF and EARDU frequency matrices roughly correspond to the Time Logical and TIC Logical
  matrices of Lesher et al. (1998) *(Scan Test Configuration › Scan Layout)*.
- The sample scenarios were taken from tasks Compass beta testers were asked to do *(Overview of
  Sample Scenarios)*.
- Development was led by Koester Performance Research with NIH STTR Phase I and II support
  *(Development Team)*.

## 12. Gaps — look elsewhere

Not in the guide: screen sizes and layout grid; spacing and typography beyond the stated test
defaults; colour palette for the application chrome; the widget toolkit and component structure;
a keyboard-navigation map beyond Alt-P, Alt-Q, F1, Delete and Ctrl-C; design rationale beyond
the remarks quoted above. Visuals — every screen — are in the PDF only.
