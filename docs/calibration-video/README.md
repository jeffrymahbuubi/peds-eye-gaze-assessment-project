# Grid 3 eye-gaze calibration: screen-recording reference

Source video: `resources/hsieh/Videos/Calibration 2026-04-07 09-42-35-69.mp4`

| Property | Value |
|---|---|
| Duration | 72.888 s |
| Resolution | 2880 x 1800 (whole Windows desktop) |
| Frame rate | variable; 1689 frames, about 23 fps on average. The recorder drops frames while the screen is static, so some gaps of 0.3 to 1.0 s exist |
| Audio | AAC, 48 kHz, stereo. Sound is present only from 33.0 to 34.5 s (see section 6) |
| Recorded | 2026-04-07 09:42:36 local time (from the file metadata and the on-screen clock) |
| Recorder | "Screen Recorder by Sandpiper Studio" (its window is visible at 0 s and 72.5 s) |
| Software | Smartbox Grid 3 (desktop tile "GRID 3 (Win 10)", grid set "朋笛中文") |

All times are video-relative `t_ms`. All pixel values are in video pixels (2880 x 1800).
"TL / TR / C / BL / BR" means top-left / top-right / centre / bottom-left / bottom-right.

## How this was captured

- Ran talkthrough `process_media` once (job `002d3d1bad5705dd`, no `metadata_errors`). This gave 76 keyframes, OCR and the transcript.
- Decoded **every** video frame (PyAV) and tracked the calibration target on the plain white or black screen. For each frame this gave the target's centre and bounding-box size. All dwell and travel timings below come from this per-frame track.
- Built contact sheets at 250 to 500 ms steps for every transition, and extracted native-resolution crops into `frames/`.
- Read all on-screen text from native-resolution crops. The talkthrough OCR was used only as a cross-check.

---

## 1. Phase timeline

Two full 5-point calibrations were recorded. After each one, the user ran "Improve calibration" once. Between the two full runs, the user changed the calibration background from white to black.

| t (s) | Phase | What is on screen / what the user does | Frame |
|---|---|---|---|
| 0.000 - 2.07 | Entry | Grid 3 "Eye gaze" settings page (Settings > Access > Eye gaze). The "Calibration" tile is highlighted. The track-status box says "No eyes detected". | [01](frames/01_t000000_eye-gaze-page.png), [02](frames/02_t001000_track-status-no-eyes.png) |
| ~2.1 - 2.59 | Start | The user clicks the "Calibration" tile. There is no instruction screen and no positioning screen before the stimulus. | |
| 2.589 | **Run 1 starts** | A full-screen white window covers the whole desktop, including the taskbar. A faint grey "X" is in the top-right corner. | |
| 2.666 | | The target (bee image) appears at the extreme top-left corner (centre at about 26,27; about 53 px wide). It grows while it glides to the first point. | [03](frames/03_t002666_run1-target-appears.png) |
| 3.93 - 13.48 | Run 1: 5 points | TL, then BR, TR, BL, C (timing in section 2). | [04](frames/04_t003962_run1-target-large-TL.png), [05](frames/05_t004600_run1-target-small-TL.png), [06](frames/06_t005807_run1-target-moving.png), [07](frames/07_t013430_run1-target-small-center.png) |
| 13.476 | Run 1 ends | The last frame shows the small target at C. | |
| 13.554 | Window closes | For one frame, the underlying "Eye gaze" page shows. | [08](frames/08_t013554_eye-gaze-flash-after-run1.png) |
| 13.81 - ~15.7 | Processing | The "Calibration" page shows "Processing calibration results" and a spinning-dots indicator. "Improve calibration" is greyed out (disabled). "Show Monitor" and "Back" are enabled. Duration is about 2 s. | [09](frames/09_t014524_processing.png) |
| 15.770 | **Result screen 1** | Scores 77 / 97 / 96 / 97 / 96 (layout in section 3). | [10](frames/10_t015770_results1.png) |
| ~17.19 | User choice | The user clicks "Improve calibration". | |
| 17.313 | **Improve run 1** | The full-screen white window opens again. The mouse cursor is visible on it. The target enters from the top-left corner, already large. | [11](frames/11_t017440_improve1-start.png) |
| 18.62 - 19.44 | | **Only the TL point** is shown (arrives at 18.622, minimum size at 19.222, ends at 19.443). TL was the lowest-scoring point (77). | [12](frames/12_t019411_improve1-small-TL.png) |
| 19.934 | | The result page appears again for about 0.1 s, still showing the **old** scores (77 ...). | [13](frames/13_t019934_old-results-flash.png) |
| 20.07 - 21.1 | Processing | "Processing calibration results" again. | |
| 22.291 | **Result screen 2** | Scores 95 / 97 / 96 / 98 / 95. The mouse hovers over "Improve calibration" (light-blue hover state), but the user does not click it. | [14](frames/14_t022291_results2.png) |
| ~24.5 - 25.0 | Exit to Eye gaze | The user clicks "Back". The "Eye gaze" page now shows a live face icon that changes colour: orange at 25.0, green at 25.5, red at 26.4. | [15](frames/15_t025003_eye-gaze-face-orange.png), [16](frames/16_t025524_eye-gaze-face-green.png), [17](frames/17_t026447_eye-gaze-face-red.png) |
| ~26.4 - 27.79 | Calibration settings | The user clicks "Settings" under the Calibration tile. The calibration settings page fades in. | [18](frames/18_t027787_calibration-settings.png) |
| 28.8 - 31.45 | Settings change | The user opens the "Background" colour picker (29.0 to 30.4) and picks **black**. | [19](frames/19_t030128_background-colour-picker.png), [20](frames/20_t031451_settings-black-background.png) |
| ~32.4 | | The user clicks "OK". All settings dialogs close. | |
| 32.43 - 36.0 | Grid 3 home | The Grid 3 home screen (grid-set tiles) shows. Speech audio plays at 33.0 to 34.5 (section 6). | [21](frames/21_t032558_grid3-home.png) |
| 36.11 | Re-entry | The user opens the Grid 3 "Menu" and clicks "Settings (F10)". | [22](frames/22_t036113_grid3-menu.png) |
| 36.46 - 37.6 | | The "Access" page shows. The user clicks "Eye gaze". | [23](frames/23_t036457_access-page.png) |
| 38.0 - ~38.9 | | The "Eye gaze" page shows a red face. The user clicks the "Calibration" tile. | [24](frames/24_t038001_eye-gaze-before-run2.png) |
| 39.005 | **Run 2 starts** | Full-screen **black** window. The target appears at the top-left corner (about 48,48; 96 px wide) and grows while it glides to TL. | [25](frames/25_t039067_run2-target-appears.png) |
| 40.34 - 50.13 | Run 2: 5 points | Same order: TL, BR, TR, BL, C. | [26](frames/26_t040338_run2-target-large-TL.png), [27](frames/27_t041029_run2-target-small-TL.png) |
| 50.156 | Window closes | For one frame, the "Eye gaze" page shows (red face). | |
| 50.33 - ~52.1 | Processing | "Processing calibration results". | |
| 52.241 | **Result screen 3** | Scores 88 / 97 / 94 / 96 / 94. | [28](frames/28_t052241_results3.png) |
| ~53.8 | User choice | The user clicks "Improve calibration". | |
| 53.939 | **Improve run 2** | The black full-screen window opens. **Only TL** is shown (TL arrives at 55.250, minimum size at 55.859, ends at 55.982). TL was again the lowest-scoring point (88). | [29](frames/29_t054000_improve2-start.png) |
| 56.015 | | Old result scores flash briefly, then "Processing" shows (56.3 to ~57.0). | [30](frames/30_t056015_old-results-flash2.png) |
| 57.076 | **Result screen 4** | Scores 93 / 98 / 95 / 96 / 95. "Improve calibration" is in the hover state (light blue). | [31](frames/31_t057076_results4.png) |
| ~59.3 | Exit | The user clicks "Back". The "Eye gaze" page shows, with the live face orange, then green. | [32](frames/32_t059835_eye-gaze-after-results4.png) |
| 60.1 - 71.4 | Track status | The face icon changes between green (60 to 63), orange (64 to 65, 68), red (66 to 67, 69) and an empty grey box (70.4). At 71.4 it shows "No eyes detected". | [33](frames/33_t064233_face-orange.png), [34](frames/34_t066279_face-red.png), [35](frames/35_t071394_no-eyes-detected.png) |
| 72.49 - 72.89 | End | The recorder window comes to the front (00:01:12). The recording ends. | [36](frames/36_t072494_end.png) |

## 2. Calibration stimulus

### Points and layout

| Item | Observed |
|---|---|
| Number of points | 5 (the settings page says "Five targets") |
| Positions (centre, video px) | TL (288, 178), TR (2592, 178), C (1440, 898), BL (288, 1618), BR (2592, 1618) |
| As a fraction of the screen | x = 0.10 / 0.50 / 0.90 of the width; y = 0.10 / 0.50 / 0.90 of the height. The corners are inset 10 % from each edge. |
| Order (both full runs) | **TL, BR, TR, BL, C**. The paths between points are diagonal, vertical, diagonal, diagonal. |
| Improve-run order | Only TL was shown (the single lowest-scoring point in both cases). |
| Start position | The target first appears at the extreme top-left screen corner. In full runs it starts small. In improve runs it is already large, then it glides to the first point. |

### Target look

| Item | Observed |
|---|---|
| Image | A cartoon bee ("Custom image" target style; the bee also shows as the dropdown icon). On the black background, the image has a **white circular disc** behind the bee. On the white background, the disc is invisible. |
| Large size (while moving) | Run 1 (white): bee bounding box about 147 x 154 px (about 5.1 % of the screen width). Run 2 (black): disc about 186-188 px across (about 6.5 % of the screen width). |
| Small size (end of shrink) | About 44 x 47 px for the bee on white. About 56 px for the disc on black (about 1.9 % of the screen width). The shrink ratio is about 3.3 : 1. |
| Size setting | "Size - normal" (slider in the middle) |
| Background | Run 1 and improve run 1: white. Run 2 and improve run 2: black (changed by the user in the settings). |
| Other screen content | Only a faint "X" close mark in the top-right corner (about 2780, 50). The mouse cursor stays visible (seen during improve run 1). There is no text, counter or progress indicator. |
| Animation | The target **glides** smoothly between points: it eases out of the old point and eases into the new point. It does not jump. It **grows** to the large size in the first ~0.4 s of each move. It **shrinks** to the small size only after it arrives. There is no visible pulsing or rotation. The bee image keeps the same orientation. |
| Sound | None during any calibration run (the audio track is silent there). |

### Timing (from the per-frame track, ±60 ms frame spacing)

| Run | Point | Arrives (ms) | Reaches min size (ms) | Starts leaving (ms) |
|---|---|---|---|---|
| 1 (white) | TL | 3932 | 4525 | <= 5130 (frame gap 4784 - 5130) |
| | BR | 6464 | 6961 | 7241 |
| | TR | 8579 | 9114 | 9366 |
| | BL | 10700 | 11264 | 11517 |
| | C | 12802 | 13307 | run ends 13476 |
| Improve 1 | TL | 18622 | 19222 | run ends 19443 |
| 2 (black) | TL | 40338 | 40936 | <= 41665 (frame gap 41154 - 41665) |
| | BR | 42990 | 43581 | 43798 |
| | TR | 45115 | 45698 | 45902 |
| | BL | 47233 | 47797 | 48142 |
| | C | 49438 | 50029 | run ends 50125 |
| Improve 2 | TL | 55250 | 55859 | run ends 55982 |

Derived phase lengths per point:

| Phase | Duration |
|---|---|
| Shrink (after arrival, large to small) | about 0.5 - 0.6 s |
| Hold at small size | about 0.2 - 0.35 s. The first point may be longer (up to ~0.6 s), but frame gaps hide the exact end. |
| Travel to the next point (grow + glide) | about 1.2 - 1.35 s |
| Full cycle per point | about 2.1 - 2.4 s |
| Whole 5-point run (window open to close) | 10.9 s (run 1), 11.1 s (run 2) |
| Single-point improve run | about 2.0 - 2.1 s |
| Window close to scores shown | about 2.3 s (run 1), 2.1 s (run 2) |

The settings say "Speed - fast" (the slider is near the right end). These timings are for that speed.
The video does not show **when** within the shrink/hold the tracker samples gaze. It also does not show whether the run waits for fixation: every point took about the same time, so no waiting is visible.

## 3. Results UI

| Item | Observed |
|---|---|
| Container | The "Calibration" page inside the Grid 3 settings dialog, with a back-arrow title. A grey-bordered rectangle stands for the screen. |
| Per-point display | One filled **green circle per calibration point**, placed at the matching position in the screen rectangle (corners plus centre). Inside each circle is a white integer score. |
| Score scale | Integers. Values seen: 77 to 98. This looks like a 0-100 scale, but 100 or a low value never appears, so the scale is not confirmed. |
| Colour coding | Every circle was the same green, including the score 77. The video does not show whether low scores turn amber or red. |
| Per eye | No. There is one score per point, with no left/right split. |
| Overall rating | **None.** There is no overall score, no text verdict ("good" / "poor") and no accept prompt. |
| Buttons | "Improve calibration" (bottom left), "Show Monitor" (next to it), "Back" (bottom right). The window also has maximise and close buttons. |
| Processing state | "Processing calibration results" plus a spinner. "Improve calibration" is disabled while processing. |
| Accept | There is no separate accept button. The user leaves with "Back". The video does not show whether the result is saved automatically. |
| Recalibrate single points | Yes, indirectly. "Improve calibration" re-ran **only the lowest-scoring point** (TL) without asking which point to use. No point-picker UI appeared. After the improve run, **all five** scores changed, including points that were not re-shown (see section 7). |
| "Show Monitor" | Never clicked, so its function is not visible. |

### The four score sets (verified at native resolution)

Order: TL / TR / C / BL / BR.

| # | t (ms) | Background | Produced by | TL | TR | C | BL | BR |
|---|---|---|---|---|---|---|---|---|
| 1 | 15770 | white | full 5-point run 1 | **77** | 97 | 96 | 97 | 96 |
| 2 | 22291 | white | improve run 1 (TL only) | **95** | 97 | 96 | 98 | 95 |
| 3 | 52241 | black | full 5-point run 2 | **88** | 97 | 94 | 96 | 94 |
| 4 | 57076 | black | improve run 2 (TL only) | **93** | 98 | 95 | 96 | 95 |

These match the earlier quick look (77/97/96/97/96, 95/97/96/98/95, 88/97/94/96/94, 93/98/95/96/95), read in TL, TR, C, BL, BR order.

## 4. On-screen text (verbatim, in order of first appearance)

Grid 3 UI language is English. The grid sets and Windows are in Traditional Chinese.

**Eye gaze page (0 s)** — [01](frames/01_t000000_eye-gaze-page.png)
- Title: "Eye gaze"
- "Camera" / "Change which eye gaze camera to use."
- "Calibration" / "Calibrate to improve eye gaze accuracy." / button "Settings"
- "Activation" / "Settings for highlighting and activating cells."
- "Computer control" / "Configure access to Windows and other programs."
- Radio buttons: "Face" (selected) / "Eyes"
- Track-status box: "No eyes detected"
- Buttons: "OK", "Cancel"
- Left navigation: "朋笛中文", "Access", "Speech", "Writing", "Symbols", "Accounts", "Contacts", "Web", "Phone", "Data control", "Devices", "Grid", "Environment control"

**Calibration screens (2.6 s and later)**: no text, except a faint "X" in the top-right corner.

**Processing (13.8 s)** — [09](frames/09_t014524_processing.png): "Calibration", "Processing calibration results", "Improve calibration" (disabled), "Show Monitor", "Back"

**Results (15.8 s)** — [10](frames/10_t015770_results1.png): "Calibration", the score numbers, "Improve calibration", "Show Monitor", "Back"

**Calibration settings (27.8 s)** — [18](frames/18_t027787_calibration-settings.png)
- Title "Calibration"
- Left column heading "Calibration": dropdown "Five targets"; dropdown "Continuous calibration"; slider label "Speed - fast" with "-" / "+"
- Right column heading "Target Style": dropdown "Custom image" (bee icon); "Target" with button "Browse..."; colour dropdown "Background"; slider label "Size - normal" with "-" / "+"
- Button: "OK"
- Colour picker (30.1 s): a swatch grid and a "Find" (eyedropper) button

**Grid 3 menu (36.1 s)** — [22](frames/22_t036113_grid3-menu.png): "Menu", "Add grid sets", "Arrange grid sets F11", "Share grid sets", "Remote editing", "Users", "Settings F10", "Help F1"

**Access (36.5 s)** — [23](frames/23_t036457_access-page.png)
- "Access"
- "Pointer" / "Activate cells using a mouse or head pointer."
- "Touch" / "Activate cells using a touch screen."
- "Eye gaze" / "Activate cells using an eye tracker."
- "Voice" / "Activate cells by speaking. Voice activation is not in use."
- "Switches" / "Activate cells or lists of commands using switches."
- Buttons: "OK", "Cancel"

**Other (not Grid 3 calibration)**
- Recorder: "Screen Recorder by Sandpiper Studio", "00:00:00", "00 / 00" … "00:01:12", "6.0MB / 0.9TB"
- Notification toast: "Notification", "Recording Start--- ( 2026-04-07 09-42-35-69.mp4 )"
- Desktop and grid tiles: "GRID 3 (Win 10)", "Smartbox", "分類選單", "中文寫說板", "中文PODD(demo)"
- Taskbar: "搜尋", "英" / "中", "上午 09:42", "2026/4/7"

## 5. Device, SDK and settings hints

| Hint | Observed |
|---|---|
| Tracker name or model | **Not visible anywhere.** The "Camera" tile ("Change which eye gaze camera to use.") was never opened. The visible taskbar tray ([37](frames/37_t000000_taskbar-tray.png)) has no tracker icon. Hidden tray icons (behind "^") were not expanded. The video cannot tell a Tobii from an Irisbond or any other tracker. |
| Sample rate / SDK | Not shown. |
| Track-status widget | It is on the "Eye gaze" page (right side), with a "Face" / "Eyes" radio (Face selected). In Face mode, a stylised face icon moves, tilts and changes size with the user's head. It has two eye dots and a mouth that changes between a smile and a flat or frowning line. Colours seen: **green, orange, red**. An empty grey box and the text "No eyes detected" show when no user is seen. The meaning of each colour (distance? position?) is not labelled on screen. The "Eyes" mode was never selected. |
| Positioning step before calibration | None. Calibration starts straight from the Eye gaze page. The track-status widget is only on the settings page. |
| Calibration settings in force | "Five targets", "Continuous calibration", "Speed - fast", Target Style "Custom image" (bee), "Size - normal", Background white, then black. |
| Display | 2880 x 1800 desktop capture. The physical size and Windows scaling are unknown. |

## 6. Spoken audio

- The only sound in the whole file is from 33.0 to 34.5 s, while the Grid 3 home screen is shown after the settings were closed.
- Whisper (small model, zh) transcript, t 32750 to 34750 ms: "写说图文沟通版。" This is low-confidence ASR. It is most likely Grid 3's speech output reading a grid-set name. The tile "中文寫說板" is on screen, but the exact source is not certain.
- There is **no narration, and no calibration sound or voice prompt**. All four calibration runs are silent.

## 7. Why there are four result screens

They are **not** the same screen revisited. Each one follows a new gaze collection:

1. Full 5-point run on a white background → screen 1.
2. "Improve calibration" → one-point run (TL, the 77) → screen 2. TL rose to 95. The points that were not re-shown also changed slightly (BL 97→98, BR 96→95). So the whole result is recomputed after an improve run, not just the one point.
3. The user changed the background to black, then ran a new full 5-point run → screen 3. Its scores do not carry over from screen 2: TL is 88, not 95. So it is a fresh calibration.
4. "Improve calibration" → one-point run (TL, the 88) → screen 4. TL rose to 93 (TR 97→98, C 94→95, BR 94→95).

Before screens 2 and 4, the previous scores flash for about 0.1 s, then "Processing calibration results" shows ([13](frames/13_t019934_old-results-flash.png), [30](frames/30_t056015_old-results-flash2.png)). A quick look could mistake this for an extra result screen.

Inference, not directly shown: "Improve calibration" seems to pick the lowest-scoring point(s) automatically. With only two examples, each with one clearly worst point, we cannot tell whether it re-runs one point, every point under a threshold, or something else.

## 8. Gaps the video cannot resolve

- The tracker make/model, SDK and sample rate.
- The colour thresholds for result circles (all observed scores, 77 to 98, were green), and the score formula and range.
- What "Show Monitor" does, the other options in "Five targets" and "Continuous calibration", and what "Continuous calibration" means.
- Whether the target waits for a stable fixation or runs on a fixed timer. Every point here took about the same time.
- When within each point's shrink/hold the gaze samples are taken.
- What the green / orange / red face colours mean.
- Whether "Back" saves or accepts the latest calibration. No confirmation text is shown.

---

## Observable requirements for a re-implementation

This checklist lists only what the video shows. It makes no claim about any specific tracker or API.

**Entry and flow**
- [ ] Calibration starts with one click from a settings page. There is no instruction screen and no separate positioning screen first.
- [ ] A separate settings page offers: number of targets ("Five targets"), calibration mode ("Continuous calibration"), speed slider ("Speed - fast"), target style ("Custom image" with "Browse..."), background colour picker, and target size slider ("Size - normal").
- [ ] The background colour is user-selectable (white and black are shown) and applies to the next run.
- [ ] A live track-status widget (stylised face that moves, tilts and resizes with the head; green / orange / red; "No eyes detected" when absent; "Face" / "Eyes" view toggle) sits next to the calibration entry point.

**Stimulus**
- [ ] It is a full-screen window covering the taskbar, plain uniform background, with only a faint close "X" in the top-right corner. There is no text or progress indicator.
- [ ] 5 targets at (10 %, 10 %), (90 %, 90 %), (90 %, 10 %), (10 %, 90 %), (50 %, 50 %) of the screen, shown in that order (TL, BR, TR, BL, C).
- [ ] The target is a custom image (a cartoon bee; a white disc is visible on a dark background). Its large size is about 5-6.5 % of the screen width and its small size about 1.5-2 %.
- [ ] The target enters from the top-left screen corner, then glides smoothly (eased) between points. It does not jump.
- [ ] At each point: it shrinks large to small in about 0.5-0.6 s, holds small for about 0.2-0.35 s, then grows while gliding about 1.2-1.35 s to the next point. That is about 2.1-2.4 s per point and about 11 s for 5 points at "fast" speed.
- [ ] No sound plays during calibration.
- [ ] The mouse cursor is not hidden.

**After the run**
- [ ] The window closes, and a "Processing calibration results" state with a spinner shows for about 2 s. "Improve calibration" is disabled during this state.
- [ ] Results page: a rectangle stands for the screen, with one filled circle per point at its position, and a white integer score in each circle (observed 77-98, apparently 0-100).
- [ ] One score per point. There is no per-eye split, no overall score and no verdict text.
- [ ] The buttons are "Improve calibration", "Show Monitor" and "Back".
- [ ] "Improve calibration" re-runs only the weakest point (the same stimulus, about 2 s), then recomputes and shows scores for **all** points.
- [ ] "Improve calibration" can be repeated from any result screen. A new full run replaces the earlier results; scores do not carry over.
- [ ] The user leaves with "Back". There is no explicit accept or confirm step.
