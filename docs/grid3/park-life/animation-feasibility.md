# Choice-making scene animation: feasibility (Qt-native vs premade / AI animation)

> **Status (2026-10-11):** research report by an Opus research agent, saved from the session
> scratchpad. The user's decisions taken from it are **N1-N6 in
> `docs/specs/SPEC-scene-cause-effect-task.md` section 3.6**, and they override the
> recommendations below where they differ: the look-back AOI **moves with the object** (N2, not
> the idle box); the rainbow uses **pre-tinted copies of the art** (N4, not code-drawn); idle
> blinks are on by default with a recorded setting (N3); no AI video in v1 (N1). The benchmark
> and QML probe scripts are in `animation-feasibility/` next to this file (they were
> `scratchpad/bench/` below).


Date: 2026-10-11. Research only, no repo files changed. Inputs read: `docs/specs/SPEC-scene-cause-effect-task.md`
(H14, 4.4, 4.5, 4.7, A5, A8, A9), `docs/grid3/park-life/README.md` (7.2, 9), `src/ui/canvas.py`, `src/app.py`
(loop timer). Labels: **[measured]** = run on this PC today, **[verified]** = checked in the venv or a primary
source, **[unverified]** = secondary source or not tested.

## 0. Answer in one paragraph

Everything the user listed, both the 8 action effects and the idle life, can be done **natively in Qt** with the
plan the SPEC already has (H14: layered transparent PNGs drawn with QPainter transforms from the existing canvas
tick). No premade animation is required. Grid 3 itself does the same thing: its Park Life scene is one still
picture plus a CreateJS sprite atlas with tweened parts, not a video (README 7.2, 9.1). AI video generation
**is** now available through the user's OpenRouter account (15 models accept a first and a last frame), but no
model returns alpha, no model guarantees an exact return to the idle picture (A5), the minimum clip length (2-4 s)
is longer than some effects, and outputs are not reproducible even with a seed. That makes video a poor main path
for a clinical tool. **Recommendation: Qt-native layered transforms (H14) as the only v1 path, plus two cheap
additions: (1) a "frame-sequence" step type in the effect engine, so a short pre-rendered PNG/WebP sequence can
replace a transform later if one effect looks poor, and (2) a blink-patch pipeline for idle blinks.** Lottie,
Rive, Spine and Live2D are not worth it here (details in section 4).

## 1. What was checked locally

| Item | Result |
|---|---|
| PySide6 version in `dev/.venv` | **6.11.2** [verified] |
| Importable modules | QtMultimedia, QtSvg, QtSvgWidgets, QtQuick, QtQuickWidgets, QtQml, QtOpenGL, QtOpenGLWidgets, QtWebEngineWidgets all import [verified] |
| Image read formats | bmp, gif, jpeg, png, svg, tga, tiff, **webp**, ... (no apng) [verified] |
| `QMovie.supportedFormats()` | **gif, webp** only (no APNG) [verified] |
| Qt Lottie | `Qt6Lottie.dll` and the `vectorimageformats/qlottievectorimage.dll` plugin ship in the wheel, but the QML module **`Qt.labs.lottieqt` is not installed** ("module is not installed"); `QtQuick.VectorImage` loads [verified, QML probe] |
| Multimedia backends | `ffmpegmediaplugin.dll` + `windowsmediaplugin.dll`, FFmpeg `avcodec-61` / `avformat-61` bundled [verified] |
| ffmpeg CLI on PATH | none (needed only for an offline video-to-frames step) [verified] |
| Canvas paint path | `TaskCanvas.paintEvent` repaints the whole canvas (QPainter, antialiasing) on every app tick; the tick is a `QTimer` at `1000 / loop_fps`, and `loop_fps` follows the device (150 Hz, or 60 on USB2) [verified, `src/app.py` ~L744, `configs/default.yaml` `target_fps: auto`] |

### 1.1 Paint benchmark [measured]

Script: `animation-feasibility/paint_bench.py`. Paints into a 1920 x 1080 ARGB32 QImage (raster engine, same as the
widget backing store on Windows; the window blit is **not** included): a 1400 x 1050 background, 10 transparent
object layers (150-560 px), 10 bubble sprites with opacity, a pre-tinted rainbow variant and 8 rounded buttons.
CPU: Intel Xeon E3-1231 v3 @ 3.4 GHz (2014 desktop).

| Case | ms / frame | Max fps |
|---|---|---|
| 1 layer moving (translate + rotate + scale), SmoothPixmapTransform on | 3.1 | ~320 |
| all 10 layers moving + bubbles + rainbow, SmoothPixmapTransform on | 5.9 | ~170 |
| same, smooth off | 3.6 / 5.7 | ~280 / ~175 |

Reading: one effect at a time costs about 3-4 ms per frame, which fits a 60 Hz budget (16.7 ms) easily and a
150 Hz budget (6.7 ms) with little room. A laptop CPU and the window blit are **not measured**. Two safe
mitigations for A9: (a) cache "background + all idle layers" as one pixmap per canvas size and draw only the
animated object(s) on top (cuts the per-frame cost to roughly one background blit + a few sprites), and/or
(b) let the scene repaint at most ~60 Hz even when the loop polls gaze at 150 Hz.

## 2. Per-effect table

"Qt-native method" uses QPainter `translate / rotate / scale / setOpacity` on cached pixmaps, driven by
`t = clock - effect.t_start` from the canvas tick (so pause freezes it, A8), with ease-in-out. "Premade?" says
whether a pre-rendered sequence is needed to look right.

| Effect (dur.) | Qt-native method | Premade needed? | Art needed | Risk |
|---|---|---|---|---|
| **Bike** rides off and back (4.0 s) | Translate the boy+bike layer along a path (polyline or QPainterPath `pointAtPercent`); clip to `scene_rect`; re-enter from the left; 1-2 px vertical bounce; optional wheel spin (wheel layers rotate) | No | boy-on-bike layer; optional 2 wheel layers; the **bush in front** as its own foreground layer so he rides "behind" it (README 9.3) | Low-medium: a rigid sliding cut-out reads as "paper"; the bounce + wheel spin fixes most of it. Path leaves the AOI (see 6) |
| **Seesaw** tilts (2.0 s) | Rotate the plank+2 children layer about the fulcrum pivot, +/-12 deg sine, 3 cycles, ending at exactly 0 | No | plank-with-both-children layer; fulcrum in the background | Low |
| **Bubbles** rise (4.0 s) | Swap the girl layer to the "blowing" state; 6-10 bubble sprites spawn at the wand, rise with sine drift up-left, grow, fade (or pop with a tiny burst); swap back | No (optional 2-3 still poses: wand down / up / blowing) | girl idle + girl blowing (same character, image edit of the idle layer); 1 bubble sprite (or draw bubbles in code: radial gradient + highlight) | Medium: the second pose must match the first exactly outside the arm/mouth (use the patch check in 3.2) |
| **Swing** swings (2.5 s) | Rotate the seat+girl+ropes layer about the top-bar pivot, damped sine, 2 cycles | No | swing frame (background) + seat-with-girl-and-ropes layer, pivot at the rope tops | Low |
| **Rainbow** colour-cycles (2.0 s) | Best: draw the rainbow **in code** (concentric QPainter arcs), then cycling the band colours is trivial and exact; alternative: 8-12 pre-tinted copies of the rainbow PNG (computed once at load, see benchmark) + a few sparkle sprites | No | none if drawn in code (style must match the art); otherwise rainbow layer + sparkle sprite | Low (code-drawn may look flatter than the AI art; test against the anchor) |
| **Cloud** drifts off and back (3.5 s) | Translate left out of `scene_rect`, wrap in from the right, settle at the start | No | cloud layer | Low |
| **Balloons** pop then reappear (3.5 s) | Per balloon in turn: hide the balloon, show a burst (code-drawn star lines or a burst sprite, scale up + fade in ~150 ms); bare strings stay; then all balloons fade back in | No | **each balloon as a separate layer** + a strings layer (the layer split must give single balloons) ; optional burst sprite | Low-medium (layer split quality) |
| **Apples** fall then regrow (4.5 s) | Apple sprites fall with gravity (y = y0 + 0.5 g t^2, small bounce), lie, fade; new apples scale/fade in at the crown positions | No | one apple sprite reused (slight random rotation/scale) at 10 crown positions from the manifest; tree without apples | Low |
| **Idle blinks** (every 2-6 s per character) | Draw an "eyes closed" patch over the eyes for ~120-150 ms (optionally a half-closed frame before/after); random interval per character, from the canvas clock | No | per character one small closed-eye patch (PNG crop), see 3.2 | Low-medium (consistency of the patch) |
| **Idle bobbing** (optional) | 1-2 px sine translate, 2-3 s period, per character phase | No | none | Low technically; **clinical risk**: idle motion draws gaze during the waiting phase (S7 `wait_scene_ms`). Grid 3 does blinks only (README 9.1). Keep off by default |

Result: **0 of 10 need premade animation.** Two would benefit from a few extra still poses (bubbles girl, optional
blink half-closed frame), which are image edits, not video.

## 3. Idle life (C)

### 3.1 Timing

- Per character an independent next-blink time `t_next = now + uniform(2, 6) s`; closed 120-150 ms (optional
  half-closed 40 ms either side). Driven by the same canvas clock, so pause freezes blinks too (A8).
- Blink events need not be logged for look-back, but the run metadata should record whether idle blinks/bobbing
  were on, because they can attract gaze (they are inside the scene, not inside a button).

### 3.2 Getting a consistent "eyes closed" variant (blink patch pipeline)

1. Take the approved transparent character layer as the **input image** of an edit request ("close the eyes,
   change nothing else"). Gemini image models (Nano Banana family) and `openai/gpt-image-1*` both support
   reference-based editing; Google documents character consistency as a strength but "may not always get it
   right" [S14, S15]. gpt-image edits also accept a **mask**, which limits the change to the eye area
   [unverified for the OpenRouter route; check the MCP's parameters].
2. **Diff** the edited image against the original (a few lines of Python). Accept only if all changed pixels lie
   inside a small box around the eyes; crop that box as `objects/<char>_blink.png` with its offset in
   `scene.yaml`. Everything outside the box is then pixel-identical to the idle art **by construction**, so a
   blink can never shift the face, colours or outline.
3. Fallback when the edit keeps changing other pixels: draw eyelids in code (skin-coloured ellipse + a line in
   the outline colour) at manifest eye positions. Less pretty, fully deterministic.
4. Same pipeline for the bubbles girl's "blowing" pose (box = arm + mouth).

## 4. Options compared

| | **A. Qt-native layered transforms (H14)** | **B. Lottie** | **C. Rigs: Spine / Rive / Live2D** | **D. AI image-to-video (OpenRouter)** | **E. AI sprite-sheet tools** | **F. Hybrid: A + frame-sequence slot** |
|---|---|---|---|---|---|---|
| Effort | Engine: moderate (one effect function per object, ~10 small functions); art: layer split | High: art must be rebuilt as vector shapes; Qt module missing (below) | High: manual rigging of every character in a paid/closed editor; no maintained Python runtime | Medium per clip, high for clean-up (crop, alpha/matting, endpoint fix, QA) | Medium; output styles are mostly pixel-art / game cycles | A + ~1 small step type |
| Quality | Good for rigid moves (Grid 3 level); limbs do not bend | Good for flat vector art; cannot use AI raster art | Best character motion (bending limbs) | Best "organic" motion, but whole-frame drift, 720p-1080p softness vs. a crisp still | Style mismatch risk with the scene | A, with a per-effect upgrade path |
| Pause (A8) | Exact: time comes from the canvas clock | Player pause API | Runtime-dependent | Exact only if frames are pre-decoded and indexed by the canvas clock; QMediaPlayer pause is asynchronous | Exact if played as frames | Exact |
| Frame rate (A9) | 3-6 ms/frame measured (1.1) | QPainter software raster too [S3] | GPU runtimes (Rive C++, Live2D OpenGL) do not draw into a QWidget QPainter canvas easily | Decoding 1080p per frame in Python is costly; pre-decoded frames are cheap | Cheap | Cheap |
| Exact reset (A5) | **Guaranteed**: final transform = identity, same pixmap | Guaranteed if authored so | Guaranteed if authored so | **Not guaranteed**: first/last-frame conditioning is guidance, not pixel identity [S6, S7]; needs a cross-fade to the still | Depends on the sheet | Guaranteed for A steps; sequence steps must end on a frame equal to idle (checked at load) |
| AOI / look-back | Exact: the effect's swept box is known analytically each frame | Manual | Manual | Must be measured from frame differences offline | Manual | Exact for A steps |
| PyInstaller | Nothing new (PNGs + YAML) | Qt.labs.lottieqt **not in the PySide6 wheel** [verified]; rlottie-python would be a new native dependency [S5] | New native runtime per tool | Frame sequences: nothing new (qwebp already ships); QMediaPlayer route: FFmpeg plugin (already in the wheel) | Nothing new | Nothing new |
| Licence | Code is ours | Qt Lottie is **GPLv3 or commercial** (not LGPL) [S1] | Spine runtimes need a paid Spine Editor licence (Pro $379) [S10, S11]; Rive runtimes MIT but C++ only [S12]; Live2D licence not checked | Per-provider output terms **unverified**; some routes add a watermark by default (Seedance `watermark`, Hailuo `aigc_watermark` passthrough parameters) [S8] | Per tool, **unverified** [S16] | Same as A |
| Provenance | One record per PNG; the motion is version-controlled code (reviewable, deterministic) | Per file | Per rig | Per clip: model, prompt, seed, plus every post-processing step; **not reproducible** even with a seed [S7] | Per sheet | One record per PNG and per sequence |
| Cost | Image generation only | Designer time | Licence + designer time | 8 effects x ~4 s x ~5 attempts at $0.03-0.17/s = about **$5-30** (from the live price list, section 5) plus clean-up time | Subscriptions | Image generation only |

### 4.1 Why not Lottie (B)

- PySide6 6.11.2 ships `Qt6Lottie.dll`, but `import Qt.labs.lottieqt` fails ("module is not installed") [verified].
  `QtQuick.VectorImage` can load Lottie at runtime [S2], but that is a Qt Quick item, so it would need a
  `QQuickWidget` stacked over the QPainter canvas (two render paths, z-order, gaze cursor above it).
- Qt's LottieAnimation supports **only shape layers** (no image layers) and no expressions [S3]; AI art is raster.
- Qt Lottie Animation is **GPLv3 or commercial** [S1], unlike the LGPL modules the app uses now.
- The Python route (rlottie-python renders a frame to a PIL image [S5]; qt-lottie wraps it for QML [S4]) adds
  native dependencies for no gain over A.

### 4.2 Why not Spine / Rive / Live2D (C)

- Spine: the official runtimes require a paid Spine Editor licence for anyone integrating them [S10, S11]; the only
  Python runtime is a 2013 pygame port [S9].
- Rive: runtimes are MIT, but the low-level runtime is C++ with GPU backends (D3D/GL/Vulkan) [S12]; there is no
  Python binding, so a custom build + binding would be needed.
- Live2D: a Python binding with a PySide6 + ModernGL example exists [S13]; every character would still need
  manual mesh rigging in the Cubism editor, and its SDK licence was not checked [unverified].
- None of the 8 effects needs bending limbs; rigid parts rotating about a pivot is enough (that is what Grid 3 does).

### 4.3 AI video (D): what is actually available

OpenRouter has had video generation since 2026-04-15 (`POST /api/v1/videos`, asynchronous, `frame_images` with
`first_frame` / `last_frame`, optional `seed`) [S6]. Live model list fetched today from
`https://openrouter.ai/api/v1/videos/models` [verified]:

| Model (accepts first + last frame) | Durations (s) | Resolutions | 4:3? | Seed | Price (as listed) |
|---|---|---|---|---|---|
| `google/veo-3.1-lite` | 4, 6, 8 | 720p, 1080p | no (16:9, 9:16) | yes | $0.03/s 720p no audio |
| `google/veo-3.1-fast` | 4, 6, 8 | 720p-4K | no | yes | $0.10/s no audio |
| `google/veo-3.1` | 4, 6, 8 | 720p-4K | no | yes | $0.20/s no audio |
| `kwaivgi/kling-v3.0-std` / `-pro` | 3-15 | 720p | no (1:1 ok) | no | $0.084 / $0.112 per s |
| `kwaivgi/kling-video-o1` | 5, 10 | 720p | no | no | $0.112/s |
| `alibaba/wan-2.7` | **2**-10 | 720p, 1080p | **yes** | yes | $0.10/s |
| `bytedance/seedance-2.0` / `-fast` / `-mini`, `-2.5`, `-1-5-pro` | 4-15 (2.5: 4-30) | 480p-4K | **yes** | yes | token-priced |
| `minimax/hailuo-3`, `hailuo-3-max` | 5-15 | 2K / 480p-768p | yes | no | $0.13 / $0.05-0.08 per s |
| `black-forest-labs/flux-3-video` | 5-20 | 720p, 1080p | yes | no | $0.17/s |

Others (Wan 3.0, Runway Gen-4.5, Grok Imagine, HappyHorse, Hailuo 2.3, HeyGen) accept only a first frame.

Problems for this task:

1. **No alpha.** All outputs are opaque MP4. Options: (a) generate the **whole scene** per effect (no alpha
   needed, but every other object, the blinking characters and the background may shimmer or drift during the
   clip, and the still-to-video switch shows a visible softness/colour jump), or (b) generate a **cropped region**
   and composite it with a feathered mask over the still (the region's background must match the still exactly),
   or (c) matte each frame (BiRefNet MIT; rembg code is MIT but some model weights are not; RobustVideoMatting is
   GPL) [S17, S18, S19], which flickers on cartoon outlines and needs hand QA. Native alpha video (Wan-Alpha) is
   text-to-video only, not first/last-frame conditioned [S20].
2. **No exact return (A5).** First/last-frame conditioning guides the clip but does not reproduce the still
   pixel-for-pixel; the endpoint frames must be cross-faded into the canonical still [S7].
3. **Minimum length.** Most routes start at 4-5 s; only Wan 2.7 goes down to 2 s. Seesaw (2 s) and Rainbow
   (1.5-2 s) would need trimming or speed-up.
4. **Not reproducible.** Alibaba states that a fixed seed does not guarantee the same output [S7]; Kling and
   Hailuo routes accept no seed at all [verified, model list]. For a clinical asset this means the clip file
   itself is the record, not the recipe.
5. **Playback in Qt.** QMediaPlayer + QVideoSink can feed frames to the canvas, but alpha video in Qt has a
   history of rendering a black background (Qt 6.3 report) [S21], and FFmpeg's native VP9 decoder ignores the
   alpha plane (libvpx is needed) [S22]. Not re-tested on 6.11 [unverified]. The robust route is offline: convert
   the approved clip to a numbered WebP/PNG frame sequence at build time and play it from the canvas clock.

### 4.4 AI sprite-sheet tools (E)

PixelLab, Spritesheets.ai, Spritix and similar turn one character image into walk/idle/attack sheets; most target
pixel art or game characters and their export formats and commercial terms vary [S16] [unverified per tool].
They do not fit a painted park scene better than image edits of our own layers.

## 5. Hybrid details (D in the brief, F in the table)

- Build the effect engine as a list of **steps** per object: `transform` (translate/rotate/scale/opacity with an
  easing curve and pivot), `swap` (show another state PNG for a time span), `particles` (bubbles, apples, burst)
  and `sequence` (play `sprites/<name>/0001.webp...` at N fps). All steps read the canvas clock (A8).
- v1 uses only `transform`, `swap`, `particles`. `sequence` is there so a single effect can later be upgraded
  with premade frames (hand-drawn, a few AI image-edit poses, or an AI clip converted offline) without changing
  the engine. A loader check rejects a sequence whose last frame differs from the idle layer (A5).
- Candidates for a later upgrade, only if the transform version looks poor in the user's review: the bubbles
  girl lifting the wand (2-3 poses), the balloon burst (3-4 frames). Neither needs video.

## 6. Notes for the SPEC (open points the user should decide)

1. **AOI for moving objects.** SPEC 4.6 uses the object's (idle) bounding box. Bike and Cloud leave that box
   (bike motion region 0.25-0.83 of the width, cloud 0.08-1.00, README 9.3). With transforms the swept area is
   known exactly, so the AOI could be the union of the object's boxes over the effect, or a moving AOI per sample.
   Decision needed: static idle box (current SPEC) vs swept box vs moving AOI.
2. **Idle motion default.** Blinks on, bobbing off (Grid 3 parity, least gaze distraction)? And record the setting
   in the run metadata.
3. **Rainbow drawn in code vs from the PNG.** Code makes colour cycling exact and cheap but must match the art style.
4. **Repaint rate.** Cap scene repaint at ~60 Hz (keep 150 Hz gaze polling), or pre-compose the idle scene, so A9
   holds on a slower laptop. Measure on the target laptop during an effect (A9 already asks for this).
5. **Extra art in the layer split:** single balloons + strings layer, bush as a foreground layer, swing/seesaw
   pivots, wheel layers (optional), blowing pose, blink patches. These should be added to the asset list in 4.7.
6. **AI video:** not recommended for v1. If the user still wants to try it, the cheapest test is
   `google/veo-3.1-lite` (720p, $0.03/s, but 16:9 only) or `alibaba/wan-2.7` (4:3, 2 s minimum, $0.10/s) on one
   cropped region (e.g. the bubbles girl) with the idle crop as both first and last frame, then judge the
   endpoint match and drift. Provider commercial-use terms must be checked before any clip ships.

## 7. Sources

- S1 Qt Lottie Animation overview (licence GPLv3/commercial; LottieAnimation uses the QPainter software
  renderer; VectorImage loads Lottie): https://doc.qt.io/qt-6/qtlottieanimation-index.html
- S2 qtlottieviewer example (VectorImage + LottieVectorImageController vs LottieAnimation):
  https://doc.qt.io/qt-6/qtlottieanimation-qtlottieviewer-example.html
- S3 LottieAnimation QML type ("Only Shape layer supported", expressions not supported):
  https://doc.qt.io/qt-6/qml-qt-labs-lottieqt-lottieanimation.html
- S4 qt-lottie (PyPI, rlottie-based QML component for PySide6): https://pypi.org/project/qt-lottie
- S5 rlottie-python (renders frames to Pillow images): https://pypi.org/project/rlottie-python
- S6 OpenRouter video generation docs (`/api/v1/videos`, `frame_images`, `seed`):
  https://openrouter.ai/docs/guides/overview/multimodal/video-generation ; announcement 2026-04-15:
  https://openrouter.ai/blog/announcements/video-generation ; live list: https://openrouter.ai/api/v1/videos/models
- S7 Alibaba Wan 2.2 first-and-last-frame API (fixed 5 s; fixed seed does not guarantee identical output):
  https://www.alibabacloud.com/help/en/model-studio/legacy-image-to-video-by-first-and-last-frame-api-reference
- S8 OpenRouter model list fields `allowed_passthrough_parameters` (watermark parameters), same live list as S6
- S9 spine-python (2013 pygame port): https://github.com/terrysimons/spine-python
- S10 Spine Editor License Agreement (section 2, runtimes need an editor licence):
  http://esotericsoftware.com/spine-editor-license
- S11 Spine purchase page (Professional $379, Enterprise above $500k revenue): https://esotericsoftware.com/spine-purchase
- S12 Rive runtimes (MIT) and C++ runtime backends: https://rive.app/docs/runtimes/getting-started ,
  https://rive.app/docs/runtimes/cpp/overview
- S13 live2d-py PySide6 + ModernGL example: https://github.com/EasyLive2D/live2d-py/blob/main/examples/main_pyside6_moderngl_qt.py
- S14 Gemini image generation (Nano Banana) cookbook, character consistency and editing:
  https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_Started_Nano_Banana.ipynb
- S15 Gemini Flash-Lite Image limitations ("may not always get it right"): https://deepmind.google/models/gemini-image/flash-lite/
- S16 AI sprite tools: https://www.pixellab.ai/ , https://www.spritesheets.ai/ai-sprite-generator , https://spritix.ai/
- S17 BiRefNet licence (MIT): https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE
- S18 rembg (code vs model-weight licences): https://github.com/danielgatis/rembg
- S19 RobustVideoMatting licence: https://github.com/PeterL1n/RobustVideoMatting/blob/master/LICENSE
- S20 Wan-Alpha (text-to-video with alpha): https://docs.comfy.org/tutorials/video/wan/wan-alpha
- S21 Qt Forum, QVideoSink shows black instead of alpha (Qt 6.3): https://forum.qt.io/topic/135651/qvideosink-doesn-t-handle-alpha-channel
- S22 FFmpeg ticket 8344 (native VP8/9 decoders do not decode alpha; libvpx does): https://trac.ffmpeg.org/ticket/8344
- S23 QMovie class (pause/setPaused, supportedFormats): https://doc.qt.io/qt-6/qmovie.html
- Deep-research landscape (first/last-frame models, Pika/Luma/Vidu routes outside OpenRouter, matting, Lottie AI
  tools), Parallel run `trun_c7ca0eb22bee4935bc5c6f646b6eb734`; its non-OpenRouter claims are **[unverified]**
  here (Pika 2.5 keyframes $0.04-0.06/s: https://dev.pika.art/models/pika/pikaframes/image-to-video ; LottieFiles
  Motion Copilot: https://lottiefiles.com/ai).
