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
| `objects/seesaw_idle.png` | seesaw layer (plank, both children, base), keyed and cropped from the raw file | 1221 x 592 | 2026-10-11, `tools/chroma_key.py` | - | user, 2026-10-11 | 07efa7c07c00 |

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

Note: `objects/seesaw_idle.png` is the pipeline trial; for the effect (plank rotates about the pivot) it
is still one piece. Step 6 makes the plank + children and the base as separate layers.

## Effect sounds

None yet (step 6).
