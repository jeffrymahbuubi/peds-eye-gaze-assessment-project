# Park scene assets: provenance

Provenance record for every file in this folder (SPEC-scene-cause-effect-task.md 4.7, A10).
Each file must have a row here with its generating model, prompt, date and the user's approval.

## Spoken prompts: `audio/en/prompt_<object>.wav`

- **Tool:** `mcp-audio-openrouter` `generate_voice` (user's own MCP server).
- **Model:** `openai/gpt-audio` via OpenRouter; voice `shimmer`; output WAV (24 kHz raw take).
- **Generated:** 2026-10-11 (tool timestamps 2026-10-10 17:00-17:01 UTC); one take per file.
- **Generation prompt** (identical for all 8 except `<SENTENCE>`):
  "You are a warm, friendly female teacher reading aloud to a young child. Speak slowly and very
  clearly, with a gentle, encouraging smile in your voice. Say exactly this sentence and nothing
  else, with no introduction and no extra words before or after: "<SENTENCE>""
- **Post-processing:** silence trimmed at -40 dB below each take's peak with 50 ms padding kept;
  5 ms fades in and out; voiced part matched to -20.0 dBFS RMS (peaks -4.2 to -7.9 dBFS);
  written as PCM 16-bit, 48 kHz, 2 channels (same format as `configs/assets/sounds/forest_hit.wav`).
- **Text check:** the generator's transcript and a local Whisper "small" transcription of each
  final file both match the sentence word for word.
- **Approved:** by the user, all 8, 2026-10-11.

| File | Sentence | Length (ms) | SHA-256 (first 12) |
|---|---|---|---|
| `prompt_balloons.wav` | Make the balloons pop! | 2390 | 48657b79879d |
| `prompt_rainbow.wav` | Make the rainbow sparkle! | 2980 | b14f13a1757b |
| `prompt_seesaw.wav` | Make the seesaw go up and down! | 3920 | 38914d0c9667 |
| `prompt_apples.wav` | Make the apples fall! | 2180 | 15047d915082 |
| `prompt_cloud.wav` | Make the cloud float away! | 3910 | d9153d9582d1 |
| `prompt_bubbles.wav` | Make the bubbles fly! | 3250 | 31706a1ba96a |
| `prompt_bike.wav` | Make the bike ride away! | 3720 | 013a1d026500 |
| `prompt_swing.wav` | Make the swing go! | 2520 | 72dfbd3ec0d1 |

## Images

- **Tool:** `mcp-image-openrouter` `generate_image` (user's own MCP server), `SKIP_PROMPT_ENHANCEMENT=true`
  set in the root `.mcp.json` (the result metadata still reads `contextMethod: structured_prompt`).
- **Model:** `google/gemini-3.1-flash-image` via OpenRouter (the tool's choice for `quality: "quality"`).
- **Pipeline (approved by the user 2026-10-11, SPEC step 2):** the style anchor is the reference image;
  each object is drawn alone on flat `#00FF00`, then keyed out locally with `tools/chroma_key.py`
  (cropped to the object; re-running it on the raw file gives a byte-identical result).

| File | What | Size (px) | Generated | Prompt | Approved | SHA-256 (first 12) |
|---|---|---|---|---|---|---|
| `reference/style_anchor.png` | 4:3 style anchor, the full park with all 8 objects (not shown in the test) | 1200 x 896 | 2026-10-11, tool file `park_style_anchor_v3.png` | P1 | user, 2026-10-11 | 375dd88b8334 |
| `reference/seesaw_key_raw.png` | seesaw on the green key, raw output | 1376 x 768 | 2026-10-11, tool file `park_seesaw_key_v1.png`, reference `style_anchor.png` | P2 | user, 2026-10-11 | a4d315926ce6 |
| `reference/seesaw_idle_trial.png` | seesaw layer (plank, both children, base), keyed and cropped from the raw file (step 2 trial; moved from `objects/seesaw_idle.png` in step 6, not used by the scene) | 1221 x 592 | 2026-10-11, `tools/chroma_key.py` | - | user, 2026-10-11 | 07efa7c07c00 |

**P1** (aspect 4:3): "Children's picture-book illustration of a sunny park, flat vector style with soft
gradients, clean dark outlines, bright friendly colours, simple shapes, no text, no signs, no letters.
Landscape 4:3 composition, eye-level view, green grass in the lower half, light blue sky in the upper
half. Exactly these elements and nothing else, each clearly separated with empty space around it: (1) top
left to middle left: a large apple tree with about six red apples, its trunk on the grass; (2) bottom left
corner: a wooden swing frame with one girl sitting on the swing; (3) centre left, middle height: a child
riding a small red bicycle, partly behind a round green bush; (4) top centre, near the upper edge: one
fluffy white cloud; (5) upper centre, below the cloud: a rainbow arc; (6) centre right, middle height: a
seesaw with one child sitting on each end; (7) bottom centre: a child standing and holding a bubble wand;
(8) top right corner: a bunch of five coloured balloons on strings tied to a short post. No other people,
no animals, no buildings, no slide, no pond, no path, no benches."

**P2** (aspect 16:9, reference image `style_anchor.png`, character consistency on): "Using exactly the
same illustration style as the reference image (flat vector, soft gradients, clean dark outlines, same
character design), draw ONLY the seesaw from the reference: the wooden plank with the girl sitting on the
left end and the boy sitting on the right end, and the blue triangular base under the middle. The plank is
perfectly horizontal. Nothing else: no grass, no ground, no shadow, no sky, no other objects. The whole
background is one flat, uniform pure green colour #00FF00 with no gradient and no texture. The seesaw is
centred with empty margin around it."

Note: the step 2 trial proved the key-colour pipeline. In step 6 the user approved a better route for the
scene itself: cut every object straight out of the approved anchor (below), so only one picture is redrawn.

## Images, step 6 (approved by the user 2026-10-11, batches 1-3)

**Route.** The anchor is edited into an empty background; every object layer is then cut out of the anchor
by its difference from that background (`tools/layer_extract.py`), so style and position are the anchor's
exactly. `tools/build_park_scene.py` builds every derived file below from `reference/style_anchor.png` +
`background.png` (+ the one redraw), deterministically; re-run it to rebuild. Check: background + shadow
layer + the 8 object layers recomposited match the anchor (median channel difference 2/255; 0.004 % of
pixels differ by more than 40). Generated pictures (same tool and model as above):

| File | What | Size (px) | Generated | Prompt | SHA-256 (first 12) |
|---|---|---|---|---|---|
| `background.png` | the anchor with the 8 objects removed (the bush stays in the background) | 2400 x 1792 | tool file `park_background_v1.png`, reference `style_anchor.png`, 2K | P3 | 01b34ca09b1a |
| `reference/background_nobush.png` | `background.png` with the bush removed (made for a bush front layer; not used: the bike stands in front of the bush in the approved anchor, user decision) | 2400 x 1792 | tool file `park_background_nobush_v1.png`, reference `background.png`, 2K | P4 | cd7cfac01a56 |
| `reference/bubbles_blowing_raw.png` | the one redraw: the bubble boy blowing (from his cut-out on `#00FF00`); keyed and fitted to the idle layer's box by the build | 576 x 768 | tool file `park_bubbles_blowing_v1.png` | P5 | 9f084c7ac214 |

**P3** (4:3, 2K): "Edit the reference image. Remove ALL people, the apple tree, the swing, the bicycle, the
seesaw, the bubble wand child, the cloud, the rainbow and the balloons with their post. Keep everything else
exactly as it is: the same light blue sky, the same green grass, the same horizon line at the same height,
the same flat vector style and colours, the same composition and framing. Where objects were removed,
continue the plain sky and plain grass naturally. Keep the round green bush that was behind the bicycle
exactly where it is. Do not add anything new: no trees, no people, no sun, no clouds, no text."

**P4** (4:3, 2K): "Edit the reference image. Remove the round green bush completely. Keep everything else
exactly as it is: the same light blue sky gradient, the same green grass, the same horizon line at the same
height, the same flat vector style and colours, the same framing. Where the bush was, continue the plain
grass naturally. Do not add anything."

**P5** (3:4, character consistency on; input = the idle cut-out scaled 3x on `#00FF00`): "Edit the reference
image. Change ONLY the boy's mouth and cheeks: he is now gently blowing into the bubble wand, with his lips
pursed into a small round "o" shape and his cheeks slightly puffed out. Keep everything else exactly
identical: the same boy, same size, same position, same pose, same arms and hands, same bubble wand, same
small bubbles, same eyes, eyebrows, hair, clothes, outlines, colours and flat vector style. Keep the whole
background the same flat pure green #00FF00. Do not add or move anything else." (The keyed silhouette
overlaps the idle pose 97 %.)

**Derived files** (all by `tools/build_park_scene.py`; positions in `scene.yaml`):

| File(s) | How | SHA-256 (first 12) |
|---|---|---|
| `objects/cloud.png`, `objects/rainbow.png`, `objects/bike.png` | cut out whole (cloud, rainbow: holes filled) | 9b0926aaf392, 6e43cdfb1fb9, 6125d870a40a |
| `objects/bubbles_child.png`, `objects/bubbles_child_blowing.png` | idle cut-out; the redraw keyed (`tools/chroma_key.py`) and fitted | 24fe422272aa, 7bed7f559fed |
| `objects/seesaw_plank.png`, `objects/seesaw_base.png` | split by the base polygon (wood stays with the plank); plank rebuilt behind the base; pivot = the bolt | 9e8edcd79da6, 69e4d18fdc63 |
| `objects/swing_seat.png`, `objects/swing_frame.png` | ropes + seat + girl / frame; the leg behind the seat end filled from the leg | eabe671b141a, 0252dfc41577 |
| `objects/balloon_1.png` ... `balloon_5.png`, `objects/balloons_strings.png` | split by hue (purple, blue, orange, yellow, red = pop order back to front), each with its own outline; strings + post | 6127bc745273, e93055a38388, d7c8b20ab2dd, 1713b35ef2c0, d3b95503e3df, 489d1297d367 |
| `objects/apple_1.png` ... `apple_7.png`, `objects/apples_tree.png` | apples by colour (1 px eroded); tree with the apple holes filled from the leaves | 6a235249efb4, 10987f12c6e1, 7f032ae361a7, 05bf2380f8a7, f954b66d2ad5, 501223bde006, 463062a29534, 2e8152a3ce9e |
| `objects/rainbow_tint_1.png`, `objects/rainbow_tint_2.png` | N4 tinted copies: 55 % toward white; hue turned 60 deg | 84d824f5015c, 1c51bd2d036b |
| `layers/shadows.png` | ground shadows (anchor = background x (1 - a)), none inside object layers, none for the bike | 2dd727f3618a |
| `blink/bike_rider.png`, `seesaw_girl`, `seesaw_boy`, `swing_girl`, `bubbles_boy` | N6 eyes-closed patches: pupils covered with the face's own skin colour + a lash line; only pixels near the eyes change (tested) | a0c6ff1554f2, 7127b5fbcc43, e46a0f6a7c32, 785e903369bc, b3bc4b1aa90c |
| `buttons/<object>.png` (8) | the whole objects, for the button pictures | 375fcca3dace (apples), 369e9eecea83 (balloons), 6125d870a40a (bike), 6fac2e055b2b (bubbles), 9b0926aaf392 (cloud), 6e43cdfb1fb9 (rainbow), 3f1b8b2a68e0 (seesaw), 35502b8719a0 (swing) |
| `scene.yaml` | the manifest (layers, pivots, effects, blinks), written by the hub from the build's output | a040041b8295 |

## Effect sounds: `audio/sfx/<object>.wav` (approved by the user 2026-10-11, all 8)

- **Tool:** `mcp-audio-openrouter` `generate_music`; **model** `google/lyria-3-clip-preview` via OpenRouter
  (user decision: a musical cue per object; the server has no sound-effect model). Raw cues (about 30 s, MP3
  44.1 kHz) kept in `reference/sfx_raw/<object>.mp3`.
- **Processing** (`tools/make_scene_sfx.py`): decoded with Qt Multimedia `QAudioDecoder` (bundled FFmpeg
  backend), leading silence trimmed (-40 dB below peak), cut to the effect's length from `scene.yaml`, fades
  5 ms in / 300 ms out, levelled to -22 dBFS RMS with peaks capped at -3 dBFS (rainbow -23.0 and apples
  -26.4 dBFS RMS, where the cap bit first), written PCM 16-bit, 48 kHz, 2 channels.
- **Every prompt** begins "Instrumental only, no vocals." and ends "Starts immediately on the first beat with
  no intro, ... suitable for young children."; the object-specific middle part is below.

| File | Length (ms) | Prompt (middle part) | Raw SHA-256 | WAV SHA-256 |
|---|---|---|---|---|
| `balloons.wav` | 3500 | Playful children's cartoon cue for balloons popping one after another: five bright pizzicato string plucks with a light pop-like woodblock hit on each, rising in pitch, then a soft cheerful glockenspiel twinkle (bouncy, around 120 BPM, light and friendly) | 8f0dba898b31 | 96101cfc5949 |
| `rainbow.wav` | 2000 | Magical children's cartoon cue for a rainbow that sparkles: a shimmering upward harp glissando with sparkling celesta and wind chimes, dreamy and wondrous, gentle (soft and warm) | ed08d49bca2e | 99a52c9ce0a6 |
| `seesaw.wav` | 2000 | Bouncy children's cartoon cue for a seesaw going up and down: a playful bassoon and tuba line hopping up and down an octave in a steady see-saw rhythm with light marimba, three up-down cycles, cheerful (around 100 BPM) | d9af8dafeab7 | 341671c1b52a |
| `apples.wav` | 4500 | Children's cartoon cue for apples falling from a tree: a descending xylophone run with soft plucky woodblock bonks like apples landing on grass, playful and light, a little tumbling rhythm (around 110 BPM) | c5534e9b4c1a | c6a8f9961ba6 |
| `cloud.wav` | 3500 | Gentle children's cartoon cue for a fluffy cloud floating away and drifting back: an airy breathy flute melody gliding slowly with soft string pad swells, light and dreamy like wind (slow, calm) | c54d95109316 | ef3755659234 |
| `bubbles.wav` | 4000 | Playful children's cartoon cue for blowing soap bubbles: soft bubbly synth bloops and plinky music-box notes floating upward, light pizzicato, whimsical and delicate (around 100 BPM, gentle) | d1c536e2a756 | 163f8c3559a1 |
| `bike.wav` | 4000 | Cheerful children's cartoon cue for a child riding a bicycle away and back: a bright bicycle bell ding-ding at the very start, then a quick perky clarinet and ukulele tune with a light trotting rhythm, zooming away and returning (around 130 BPM) | 3be7c4f5d511 | 96d3008e1df9 |
| `swing.wav` | 2500 | Gentle children's cartoon cue for a girl on a swing going back and forth: a swaying waltz in three-four time with soft accordion and glockenspiel, each phrase swooping up and down like a swing, two big swings slowing down (around 90 BPM, sweet and calm) | 75ab3ae39213 | fca438398cb0 |
